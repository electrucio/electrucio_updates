#!/usr/bin/env python3
"""Estabilidad del 40W: sobrepico y timbrado con una onda cuadrada y carga
capacitiva, barriendo el condensador de compensacion C11.

    python3 tools/ltspice/stability.py            # desde el JSON
    python3 tools/ltspice/stability.py --resim    # vuelve a simular

Por que se mide asi y no con un diagrama de Bode del lazo: este amplificador
tiene DOS caminos de realimentacion en paralelo -- R5 (4k7) desde PRE_SPEAKER
al emisor de Q1, y R19 (2k2) desde SPEAKER al nodo FEEDBACK -- y los dos
llegan al mismo emisor. Romper solo uno deja el otro cerrado y la "ganancia de
lazo" que sale no significa nada (probado: daba 6.5 dB en banda media, que es
absurdo). Romper el punto comun, el emisor de Q1, exige inyeccion doble de
Tian porque alli la impedancia hacia atras y hacia delante son del mismo orden.

El sobrepico con escalon es la misma informacion y ademas se mide en el banco
con un generador de cuadrada, que es lo que importa aqui. La equivalencia con
el margen de fase de un sistema de segundo orden es la de siempre:

    sobrepico   5%  ->  ~69 grados       25%  ->  ~40 grados
               10%  ->  ~59 grados       35%  ->  ~33 grados
               15%  ->  ~52 grados       50%  ->  ~22 grados

Es una equivalencia aproximada: vale como lectura del margen, no como medida.

OJO: hay que medir LEJOS del recorte. Con la salida cerca del techo el
sobrepico sale mucho menor de lo que es, porque la saturacion se come el pico.
"""
from __future__ import annotations

import json
import math
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bench                                                    # noqa: E402
from ltrun import Netlist, run_batch                            # noqa: E402
from rawread import read_raw                                    # noqa: E402
from svgplot import (Ax, decade_ticks, frame, grid,             # noqa: E402
                     linear_ticks, rasterize)

OUT = HERE.parents[1] / "guitar_amplifier" / "quasimod_stability"
OUT_LOAD = HERE.parents[1] / "guitar_amplifier" / "quasimod_stability_load"
WAVE_C11 = "330p"                        # el que esta montado
WAVE_LOADS = ("none", "100n", "470n", "2.2u")
WAVE_CASES = (("8 OHM", "none", False), ("8 OHM + 2.2U", "2.2u", False),
              ("SPEAKER MODEL", "none", True),
              ("SPEAKER + 2.2U", "2.2u", True))

# La cuadrada va a 20 kHz, no a 1 kHz, y no es un capricho: con los graves al
# minimo y los condensadores de acoplo, el techo de una cuadrada de 1 kHz se
# desploma entre flanco y flanco, y entonces el "sobrepico" que se mide es la
# caida, no el timbrado.  A 20 kHz la caida en los 25 us de observacion es
# despreciable y el timbrado de 145 kHz sigue sobradamente resuelto.
FREQ = 20000.0
TD = 0.20e-3             # arranque: con el rail firme el .op ya es el reposo
EDGE = TD + 2 / FREQ     # el flanco que se analiza
AMP = 0.040              # V de pico en el jack; se calibra para ~4 Vpp
VRAW = 50.11
RLOAD = 8.0
STEP = "5n"              # el timbrado esta en 145 kHz: 0.5 us no lo resuelve
C11_LINE = "C11 Q2C Q2B 330p"
VSRC = "V6 PICKUP_IN 0 SINE(0 {in_amplitude} {in_freq})"

C11S = ("220p", "330p", "470p", "680p")
LOADS = ("none", "10n", "22n", "47n", "100n", "220n", "470n", "1u", "2.2u",
         "4.7u")
TABLE_LOADS = ("none", "100n", "470n", "2.2u")   # la tabla, mas corta
COL = {"220p": "#3a5199", "330p": "#a83a34", "470p": "#5d8a3e",
       "680p": "#b5762a"}
PAL = dict(bg="#ffffff", ink="#14181f", muted="#5a626f",
           grid="#ccd2dc", minor="#e8ebf0", frame="#8d95a3")


def farads(v):
    """'470n' -> 4.7e-7.  'none' -> None."""
    if v == "none":
        return None
    mult = {"p": 1e-12, "n": 1e-9, "u": 1e-6}[v[-1]]
    return float(v[:-1]) * mult


def build(work, tag, c11, cload, speaker=False):
    n = Netlist.from_file(bench.NET).absolutize_libs([bench.AMP])
    n.drop_re(r"\s*\.meas\s+tran\b", 80)
    n.drop_re(r"\s*\.four\b", 7)
    n.add(f".param vraw={VRAW}", "V_RAW N002 0 {vraw}")
    n.patch(bench.MAINS, "V4 N004 N005 0 Rser=0.1")
    extra = "" if cload == "none" else f"\nC_LOAD SPEAKER 0 {cload}"
    if speaker:
        # el altavoz tal y como esta dibujado: resonancia, bobina y todo
        if extra:
            n.patch(bench.R_LOAD, bench.R_LOAD + extra)
    else:
        for line in bench.SPEAKER_MODEL:
            n.patch(line + "\n", "")
        n.patch(bench.R_LOAD, f"R27 0 SPEAKER {RLOAD}{extra}")
    n.patch(bench.U1, bench.U1.replace("Status=0.5", "Status=0"))
    n.patch(bench.U2, bench.U2.replace("Status=0.5", "Status=0"))
    n.patch(C11_LINE, f"C11 Q2C Q2B {c11}")
    half = 0.5 / FREQ
    n.patch(VSRC, f"V6 PICKUP_IN 0 0\nV_STEP PICKUP_OUT 0 "
                  f"PULSE(0 {AMP} {TD:g} 20n 20n {half:g} {1/FREQ:g})")
    n.patch(".param drive=1", ".param drive=0.2")
    n.patch(".param vol=1.0", ".param vol=1.0")
    n.patch(".param treble=0.5", ".param treble=1.0")
    n.patch(".param bass=0.5", ".param bass=0.0")
    n.patch(".tran {step} {t_stop} {t_start} {step}",
            f".tran {STEP} {EDGE + 2.2/FREQ:g} 0 {STEP}")
    n.add(".options reltol=1e-5 vntol=1e-6 abstol=1e-12",
          ".save V(SPEAKER)")
    return n.write(work / f"{tag}.net")


def analyse(raw):
    """Sobrepico (%) y frecuencia del timbrado (Hz) del ultimo flanco de subida."""
    names, d = read_raw(str(raw))
    t = np.asarray(d["time"]).real
    v = np.asarray(d["V(speaker)"]).real
    edge = EDGE + 20e-9
    i0 = int(np.searchsorted(t, edge))
    i1 = int(np.searchsorted(t, edge + 0.45 / FREQ))
    w, tw = v[i0:i1], t[i0:i1]
    if len(w) < 50:
        return None
    base = float(v[int(np.searchsorted(t, edge - 5e-6)):i0].mean())
    settled = float(w[int(len(w) * 0.75):].mean())
    swing = settled - base
    if abs(swing) < 1e-3:
        return None
    peak = float(w.max() if swing > 0 else w.min())
    over = 100.0 * (peak - settled) / swing
    # timbrado: cruces por el valor asentado en los primeros 60 us
    k = int(np.searchsorted(tw, tw[0] + 20e-6))
    x = w[:k] - settled
    sg = np.signbit(x)
    cross = tw[:k][1:][sg[1:] != sg[:-1]]
    ring = 1.0 / (2 * float(np.mean(np.diff(cross)))) if len(cross) > 2 else 0.0
    # tiempo de subida 10-90 %
    lo = base + 0.1 * swing
    hi = base + 0.9 * swing
    try:
        t10 = tw[np.argmax(w >= lo)] if swing > 0 else tw[np.argmax(w <= lo)]
        t90 = tw[np.argmax(w >= hi)] if swing > 0 else tw[np.argmax(w <= hi)]
        rise = float(t90 - t10)
    except ValueError:
        rise = 0.0
    return dict(over=over, ring=ring, rise=rise, swing=swing, settled=settled)


def wave(raw, span=18e-6, n=420):
    """Respuesta al escalon alrededor del flanco, normalizada a 0-100 %.

    Se remuestrea a una rejilla uniforme porque LTspice da paso variable y la
    curva saldria con la densidad de puntos del solver, no con la del tiempo.
    """
    names, d = read_raw(str(raw))
    t = np.asarray(d["time"]).real
    v = np.asarray(d["V(speaker)"]).real
    i0 = int(np.searchsorted(t, EDGE))
    base = float(v[int(np.searchsorted(t, EDGE - 5e-6)):i0].mean())
    i1 = int(np.searchsorted(t, EDGE + 0.45 / FREQ))
    settled = float(v[int(i0 + (i1 - i0) * 0.75):i1].mean())
    swing = settled - base
    grid_t = np.linspace(-2e-6, span, n)
    y = np.interp(EDGE + grid_t, t, v)
    return (grid_t * 1e6).tolist(), (100 * (y - base) / swing).tolist()


# La figura del post lleva solo las dos trazas con el altavoz de verdad: la
# carga muerta de 8 ohm se simula igual, porque la tabla la usa, pero dibujar
# cuatro curvas para decir que dos de ellas se solapan no ayuda a nadie.
PLOT_CASES = (("SPEAKER MODEL", "#3a5199", "its own speaker",
               (5.4, 124.0, "end", True)),
              ("SPEAKER + 2.2U", "#a83a34",
               "speaker + 2.2 uF, the conventional torture load",
               (7.6, 128.0, "start", False)))


def draw_wave(traces) -> str:
    """Respuesta al escalon con los 330p montados, contra su carga real."""
    w, h = 840, 540
    ax = Ax(88, 132, 706, 300, (-2, 18), (-10, 135))
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
         f'viewBox="0 0 {w} {h}"><rect width="{w}" height="{h}" '
         f'fill="{PAL["bg"]}"/>',
         f'''<style>
  .cond{{font:400 12px "IBM Plex Mono",ui-monospace,monospace;fill:{PAL['muted']};letter-spacing:.05em}}
  .tick{{font:400 13px "IBM Plex Mono",ui-monospace,monospace;fill:{PAL['muted']};font-variant-numeric:tabular-nums}}
  .axl{{font:500 12px "IBM Plex Mono",ui-monospace,monospace;fill:{PAL['ink']};letter-spacing:.14em}}
  .lgl{{font:500 11px "IBM Plex Mono",ui-monospace,monospace;fill:{PAL['ink']};letter-spacing:.08em}}
  .ann{{font:500 12px "IBM Plex Sans",system-ui,sans-serif}}
  .sub{{font:400 11px "IBM Plex Sans",system-ui,sans-serif;fill:{PAL['muted']}}}
</style>''']
    s.append(f'<text x="88" y="34" class="cond" fill="{PAL["ink"]}">'
             f'C11 = 330pF &#183; 20Khz square &#183; output ~4.8 Vpp &#183; '
             f'gain 0.20</text>')
    s.append(f'<text x="88" y="56" class="cond">STEP RESPONSE AT THE SPEAKER, '
             f'NORMALISED TO THE SETTLED LEVEL</text>')
    lx = 88
    for key, col, lab, _ in PLOT_CASES:
        s.append(f'<line x1="{lx}" y1="84" x2="{lx+26}" y2="84" '
                 f'stroke="{col}" stroke-width="2.8" stroke-linecap="round"/>')
        s.append(f'<text x="{lx+34}" y="88" class="lgl">{lab.upper()}</text>')
        lx += 48 + len(lab) * 7.0
    s.append(grid(ax, PAL, linear_ticks(ax, 2, 1, fmt=lambda v: f"{v:g}"),
                  ystep=10, ymajor=50, yfmt=lambda v: f"{v:g}"))
    s.append(frame(ax, PAL))
    s.append(f'<line x1="{ax.x0}" y1="{ax.y(100):.1f}" x2="{ax.x0+ax.w}" '
             f'y2="{ax.y(100):.1f}" stroke="{PAL["frame"]}" stroke-width="1" '
             f'stroke-dasharray="4 4"/>')
    for key, col, _, (tx, ty, anchor, leader) in PLOT_CASES:
        if key not in traces:
            continue
        tt, yy = traces[key]
        s.append(f'<path d="{ax.path(tt, yy)}" fill="none" stroke="{col}" '
                 f'stroke-width="2.6" stroke-linejoin="round"/>')
        k = max(range(len(yy)), key=lambda n: yy[n])
        px, py = ax.x(tt[k]), ax.y(yy[k])
        s.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="5" '
                 f'fill="{PAL["bg"]}"/>')
        s.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3.2" fill="{col}"/>')
        lxp, lyp = ax.x(tx), ax.y(ty)
        if leader:
            s.append(f'<line x1="{lxp:.1f}" y1="{lyp+4:.1f}" '
                     f'x2="{px:.1f}" y2="{py-6:.1f}" stroke="{col}" '
                     f'stroke-width="1" opacity=".65"/>')
        s.append(f'<text x="{lxp:.1f}" y="{lyp:.1f}" class="ann" '
                 f'text-anchor="{anchor}" fill="{col}">'
                 f'{yy[k]-100:.1f} % overshoot</text>')
    for n, line in enumerate((
            "Damped, not oscillating: each rebound is a fraction of the "
            "one before, and both are flat by 18 us.",
            "2.2 uF is a test load, not a cable \u2014 speaker cable runs "
            "about 100 pF per metre, so a 3 m lead is some 300 pF.")):
        s.append(f'<text x="88" y="{ax.y0+ax.h+76+n*17}" class="sub">'
                 f'{line}</text>')
    cy = ax.y0 + ax.h / 2
    s.append(f'<text x="32" y="{cy:.0f}" class="axl" text-anchor="middle" '
             f'transform="rotate(-90 32 {cy:.0f})">% OF FINAL VALUE</text>')
    s.append(f'<text x="{ax.x0 + ax.w/2:.0f}" y="{ax.y0 + ax.h + 50}" '
             f'class="axl" text-anchor="middle">'
             f'MICROSECONDS AFTER THE EDGE</text>')
    s.append("</svg>")
    return "".join(s)


def phase_margin(over):
    """Margen de fase equivalente de un segundo orden, en grados."""
    if over <= 0:
        return 90.0
    z = -math.log(over / 100.0) / math.sqrt(math.pi**2 + math.log(over/100.0)**2)
    return math.degrees(math.atan2(
        2 * z, math.sqrt(math.sqrt(1 + 4 * z**4) - 2 * z**2)))


def simulate():
    work = Path(tempfile.mkdtemp(prefix="stab_"))
    print(f"simulando {len(C11S)*len(LOADS)} puntos en {work}")
    rows = []
    for c11 in C11S:
        for cl in LOADS:
            net = build(work, f"s_{c11}_{cl}", c11, cl)
            run_batch(net, timeout=900)
            r = analyse(net.with_suffix(".raw"))
            if r is None:
                print(f"  {c11:>5} {cl:>5}  sin flanco utilizable")
                continue
            r.update(c11=c11, cload=cl)
            rows.append(r)
            print(f"  C11={c11:>5}  carga={cl:>5}  sobrepico {r['over']:5.1f}%"
                  f"  timbrado {r['ring']/1000:6.1f} kHz"
                  f"  subida {r['rise']*1e6:5.2f} us", flush=True)
    return rows


def table(rows):
    out = ["ESTABILIDAD  (cuadrada de 20 kHz, salida ~4.8 Vpp, lejos del recorte)",
           "",
           "              sobrepico %        margen de fase equivalente, grados",
           "  C11     " + "".join(f"{c:>8}" for c in TABLE_LOADS)
           + "   " + "".join(f"{c:>8}" for c in TABLE_LOADS)]
    for c11 in C11S:
        sel = {r["cload"]: r for r in rows if r["c11"] == c11}
        a = "".join(f"{sel[c]['over']:8.1f}" if c in sel else "       -"
                    for c in TABLE_LOADS)
        b = "".join(f"{phase_margin(sel[c]['over']):8.0f}" if c in sel
                    else "       -" for c in TABLE_LOADS)
        out.append(f"  {c11:<6}{a}   {b}")
    out.append("")
    out.append("  subida 10-90% con carga resistiva, y timbrado donde lo hay")
    for c11 in C11S:
        sel = [r for r in rows if r["c11"] == c11 and r["cload"] == "none"]
        if sel:
            out.append(f"  {c11:<6} {sel[0]['ring']/1000:7.1f} kHz"
                       f"   {sel[0]['rise']*1e6:6.2f} us")
    return "\n".join(out)


def fmt_c(v):
    """Etiqueta de un eje de capacidad en faradios."""
    return f"{v*1e9:g}n" if v < 1e-6 else f"{v*1e6:g}u"


def draw(rows) -> str:
    w, h = 840, 520
    pts = {c: sorted(((farads(r["cload"]), r["over"]) for r in rows
                      if r["c11"] == c and r["cload"] != "none"))
           for c in C11S}
    ymax = max(y for v in pts.values() for _, y in v) * 1.12
    ax = Ax(88, 112, 706, 322, (1e-8, 5e-6), (0, ymax), xlog=True)
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
         f'viewBox="0 0 {w} {h}"><rect width="{w}" height="{h}" '
         f'fill="{PAL["bg"]}"/>',
         f'''<style>
  .cond{{font:400 12px "IBM Plex Mono",ui-monospace,monospace;fill:{PAL['muted']};letter-spacing:.05em}}
  .tick{{font:400 13px "IBM Plex Mono",ui-monospace,monospace;fill:{PAL['muted']};font-variant-numeric:tabular-nums}}
  .axl{{font:500 12px "IBM Plex Mono",ui-monospace,monospace;fill:{PAL['ink']};letter-spacing:.14em}}
  .lgl{{font:500 11px "IBM Plex Mono",ui-monospace,monospace;fill:{PAL['ink']};letter-spacing:.08em}}
  .ann{{font:400 11px "IBM Plex Sans",system-ui,sans-serif}}
</style>''']
    s.append(f'<text x="88" y="34" class="cond" fill="{PAL["ink"]}">'
             f'20Khz square &#183; output ~4.8 Vpp &#183; 8 ohm plus the '
             f'capacitance on the X axis</text>')
    s.append(f'<text x="88" y="56" class="cond">STEP OVERSHOOT vs CAPACITIVE '
             f'LOAD, FOR FOUR VALUES OF THE COMPENSATION CAP C11</text>')
    lx = 88
    for c in C11S:
        lab = f"C11 = {c}" + (" (AS BUILT)" if c == "330p" else "")
        s.append(f'<line x1="{lx}" y1="82" x2="{lx+26}" y2="82" '
                 f'stroke="{COL[c]}" stroke-width="2.6" '
                 f'stroke-linecap="round"/>')
        s.append(f'<text x="{lx+34}" y="86" class="lgl">{lab}</text>')
        lx += 48 + len(lab) * 7.3
    s.append(grid(ax, PAL, decade_ticks(ax, fmt=fmt_c), ystep=5, ymajor=10,
                  yfmt=lambda v: f"{v:g}"))
    s.append(frame(ax, PAL))
    for c in C11S:
        xs = [x for x, _ in pts[c]]
        ys = [y for _, y in pts[c]]
        lw = 3.0 if c == "330p" else 1.9
        s.append(f'<path d="{ax.path(xs, ys)}" fill="none" '
                 f'stroke="{COL[c]}" stroke-width="{lw}" '
                 f'stroke-linejoin="round" stroke-linecap="round"/>')
    cy = ax.y0 + ax.h / 2
    s.append(f'<text x="32" y="{cy:.0f}" class="axl" text-anchor="middle" '
             f'transform="rotate(-90 32 {cy:.0f})">OVERSHOOT %</text>')
    s.append(f'<text x="{ax.x0 + ax.w/2:.0f}" y="{ax.y0 + ax.h + 58}" '
             f'class="axl" text-anchor="middle">CAPACITIVE LOAD</text>')
    s.append("</svg>")
    return "".join(s)


def simulate_waves():
    """Respuesta al escalon con el C11 montado, carga muerta y altavoz real."""
    work = Path(tempfile.mkdtemp(prefix="stabw_"))
    out = {}
    for label, cl, spk in WAVE_CASES:
        tag = f"w_{cl}_{int(spk)}"
        net = build(work, tag, WAVE_C11, cl, speaker=spk)
        run_batch(net, timeout=900)
        out[label] = wave(net.with_suffix(".raw"))
        print(f"  {label:<16} sobrepico {max(out[label][1]) - 100:5.1f} %",
              flush=True)
    return out


def main():
    js = OUT.with_suffix(".json")
    jw = OUT.with_name(OUT.name + "_wave").with_suffix(".json")
    resim = "--resim" in sys.argv
    if resim or not js.exists():
        js.write_text(json.dumps(simulate(), indent=1), encoding="utf-8")
    if resim or not jw.exists():
        jw.write_text(json.dumps(simulate_waves(), indent=1), encoding="utf-8")
    rows = json.loads(js.read_text(encoding="utf-8"))
    traces = json.loads(jw.read_text(encoding="utf-8"))
    print()
    print(table(rows))

    svg = draw_wave(traces)
    OUT.with_suffix(".svg").write_text(svg, encoding="utf-8")
    rasterize(svg, OUT.with_suffix(".png"), 840, 540, scale=2.4)
    svg2 = draw(rows)
    OUT_LOAD.with_suffix(".svg").write_text(svg2, encoding="utf-8")
    rasterize(svg2, OUT_LOAD.with_suffix(".png"), 840, 520, scale=2.4)
    print()
    print(OUT.with_suffix(".png"), "  <- respuesta al escalon")
    print(OUT_LOAD.with_suffix(".png"), "  <- sobrepico contra carga")


if __name__ == "__main__":
    main()
