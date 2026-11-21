#!/usr/bin/env python3
"""Reparto de potencia del 40W: cuanto llega al altavoz y cuanto se queda por
el camino, barriendo la entrada desde casi nada hasta recorte duro.

    python3 tools/ltspice/power_budget.py            # redibuja desde el JSON
    python3 tools/ltspice/power_budget.py --resim    # vuelve a simular

Escribe guitar_amplifier/quasimod_power.{json,svg,png} y la tabla por consola.

La pregunta que contesta no es "cuanta potencia da" -- eso ya esta en
power_summary.md -- sino "cuanto aguanta cada pieza". Y ahi hay una trampa
clasica de la clase AB: **el maximo de disipacion de los transistores de
salida NO esta a maxima potencia**. A tope de senal Q6 y Q7 estan saturados,
con mucha corriente pero poca tension encima, y disipan poco; el peor momento
cae a media excursion, donde coinciden tension y corriente altas.

Condiciones: 1 kHz, carga de 8 ohm, agudos al maximo, graves al minimo,
volumen al tope, ganancia 0.20 (el minimo mecanico real del pote) y los
recortadores FUERA, que es cuando mas lejos llega la etapa de potencia.

Se simula con la RED de verdad, no con una continua rigida, y eso cuesta 0.9 s
de arranque por punto. Vale la pena: con un rail firme de 50 V el ampli parece
dar 50 W, porque la fuente ideal no se entera de que le estan pidiendo 5 A.
Con la red simulada los vatios son los mismos que publica power_summary.md.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from svgplot import Ax, frame, grid, linear_ticks, rasterize       # noqa: E402

OUT = ROOT / "guitar_amplifier" / "quasimod_power"

FREQ = 1000.0
RLOAD = 8.0
VRAW = 50.0
MAINS = True          # la red de verdad: asi los vatios cuadran con power_summary.md
# 2.0 s, no 0.9.  Verificado contra el punto distorsionado de power_summary.md
# (1.2 Vpp, ganancia 0.20): con 0.9 s salen 16.42 Vrms / 33.7 W y con 2.0 s
# salen 17.54 / 38.5, que son los que ya estaban publicados.  Los 0.8 s que
# bastan para cargar el deposito NO bastan para el aparato entero: con la
# etapa recortando, el acoplo de salida de 3300 uF y la red de polarizacion
# tardan mas, y a 0.9 s se esta midiendo todavia un transitorio.  Cuesta el
# doble por punto y no es negociable.
SETTLE = 2.0
DRIVE = 0.20
TONE = dict(treble=1.0, bass=0.0, vol=1.0)
AMPS = [0.02, 0.04, 0.06, 0.08, 0.10, 0.13, 0.16, 0.19, 0.205, 0.22,
        0.25, 0.30, 0.40, 0.60, 0.90]

# Limites de catalogo, TODOS con la capsula a 25 grados: es el numero de la
# primera pagina, y a 25 grados no esta ninguna capsula de este aparato.  La
# columna "usa %" dice margen sobre el papel, no sobre la realidad; para la
# realidad hay que derrateear con la curva Pc-Tc y la resistencia termica del
# disipador.  El 2SD896 son 70 W (Sanyo/ISC/onsemi coinciden), y su pareja
# 2SB776 esta catalogada justo para "AF 40 W output applications", que es de
# donde sale el 40 del nombre de este ampli.
RATING = {"Q6": 70.0, "Q7": 70.0,        # 2SD896, TO-3PN, 100 V / 7 A
          "Q4": 12.5, "Q5": 12.5,        # BD139/BD140, TO-126
          "Q2": 12.5, "Q3": 12.5,
          "Q1": 0.5, "Q8": 0.5, "Q10": 0.5, "Q11": 0.5, "Q12": 0.5}
# R16/R17 (0.5 ohm en los emisores) no llevan limite aqui: depende de la que
# este montada en la placa.  Se publica lo que disipan y punto.
R_WATCH = ("R16", "R17", "R9", "R47", "R51")
PAL = dict(bg="#ffffff", ink="#14181f", muted="#5a626f",
           grid="#ccd2dc", minor="#e8ebf0", frame="#8d95a3")


def simulate() -> list:
    import bench
    bench.PROBES = ("SPEAKER",)
    work = Path(tempfile.mkdtemp(prefix="power_budget_"))
    print(f"simulando {len(AMPS)} puntos en {work}")
    rows = []
    for a in AMPS:
        r = bench.run(work, tag=f"p_{a}", amp=a, drive=DRIVE, u1=0, u2=0,
                      freq=FREQ, rload=RLOAD, vraw=VRAW, qpow=True, rpow=True,
                      mains=MAINS, settle=SETTLE, **TONE)
        thd, even, odd = bench.thd_split(r["SPEAKER"])
        m = r["meas"]
        rows.append(dict(amp=a, pspk=m["p_spk"], prail=m.get("p_rail", 0.0),
                         vrail=m.get("vraw_avg", 0.0),
                         vrms=m["speaker_rms"], thd=thd or 0.0,
                         q=r["qpow"], r=r["rpow"]))
        print(f"  {a*2000:5.0f} mVpp -> {m['p_spk']:6.2f} W altavoz, "
              f"Q6 {r['qpow']['Q6']:5.2f} W, Q7 {r['qpow']['Q7']:5.2f} W, "
              f"THD {thd or 0:5.1f}%", flush=True)
    return rows


def table(rows) -> str:
    out = []
    out.append("REPARTO DE POTENCIA  (1 kHz, 8 ohm, red simulada, sin diodos)")
    out.append("")
    out.append("  entrada   altavoz    Q6      Q7    resto   fuente   rend   rail   THD")
    out.append("   mVpp        W        W       W       W       W       %      V      %")
    for d in rows:
        q = d["q"]
        pair = q["Q6"] + q["Q7"]
        rest = sum(q.values()) - pair + sum(d["r"].values()) - d["pspk"]
        prail = abs(d["prail"])
        eff = 100 * d["pspk"] / prail if prail else 0.0
        out.append(f"  {d['amp']*2000:6.0f}  {d['pspk']:8.2f} {q['Q6']:7.2f} "
                   f"{q['Q7']:7.2f} {rest:7.2f} {prail:7.2f} "
                   f"{eff:6.1f} {d.get('vrail', 0.0):6.1f} {d['thd']:6.1f}")
    worst = max(rows, key=lambda d: d["q"]["Q6"] + d["q"]["Q7"])
    out.append("")
    out.append(f"peor caso para la pareja de salida: {worst['amp']*2000:.0f} mVpp "
               f"de entrada, {worst['pspk']:.1f} W al altavoz")
    out.append("")
    out.append("MARGEN EN EL PEOR CASO")
    out.append("")
    out.append("  pieza    disipa W   limite W   usa %")
    for name, lim in RATING.items():
        p = worst["q"].get(name)
        if p is None:
            continue
        out.append(f"  {name:<8} {p:9.3f} {lim:10.1f} {100*p/lim:7.1f}")
    out.append("")
    out.append("  resistencias que mas disipan en el peor caso, en W")
    top = sorted(((v, k) for k, v in worst["r"].items() if k != "R27"),
                 reverse=True)[:6]
    for v, k in top:
        out.append(f"  {k:<8} {v:9.3f}")
    return "\n".join(out)


def draw(rows) -> str:
    """Solo la disipacion de la pareja de salida contra la potencia entregada.

    La potencia al altavoz NO se dibuja aqui aunque sea tentador: llega a 36 W
    y la disipacion no pasa de 13, asi que compartir eje aplasta justo la
    curva que se quiere ensenar.
    """
    w, h = 820, 500
    xs = [d["pspk"] for d in rows]
    q6 = [d["q"]["Q6"] for d in rows]
    q7 = [d["q"]["Q7"] for d in rows]
    pair = [a + b for a, b in zip(q6, q7)]
    ax = Ax(84, 108, 700, 310, (0, max(xs) * 1.04), (0, max(pair) * 1.12))
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
    s.append(f'<text x="84" y="34" class="cond" fill="{PAL["ink"]}">'
             f'1Khz &#183; Load 8 ohm &#183; no clipping diodes &#183; '
             f'mains supply simulated</text>')
    s.append(f'<text x="84" y="56" class="cond">HEAT IN THE OUTPUT PAIR vs '
             f'POWER DELIVERED TO THE SPEAKER</text>')
    series = ((pair, "Q6 + Q7", "#a83a34", 2.8),
              (q6, "Q6", "#3a5199", 1.5), (q7, "Q7", "#5d8a3e", 1.5))
    lx = 84
    for _, lab, col, _ in series:
        s.append(f'<line x1="{lx}" y1="80" x2="{lx+26}" y2="80" stroke="{col}" '
                 f'stroke-width="2.6" stroke-linecap="round"/>')
        s.append(f'<text x="{lx+34}" y="84" class="lgl">{lab}</text>')
        lx += 52 + len(lab) * 7.3
    s.append(grid(ax, PAL, linear_ticks(ax, 5, 2.5), ystep=1, ymajor=2,
                  yfmt=lambda v: f"{v:g}"))
    s.append(frame(ax, PAL))
    for ys, _, col, lw in series:
        s.append(f'<path d="{ax.path(xs, ys)}" fill="none" stroke="{col}" '
                 f'stroke-width="{lw}" stroke-linejoin="round"/>')
    i = max(range(len(pair)), key=lambda k: pair[k])
    px, py = ax.x(xs[i]), ax.y(pair[i])
    s.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="5.5" fill="{PAL["bg"]}"/>')
    s.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3.6" fill="#a83a34"/>')
    s.append(f'<text x="{px+12:.1f}" y="{py-6:.1f}" class="ann" fill="#a83a34">'
             f'worst case: {pair[i]:.1f} W of heat at only {xs[i]:.1f} W out'
             f'</text>')
    cy = ax.y0 + ax.h / 2
    s.append(f'<text x="30" y="{cy:.0f}" class="axl" text-anchor="middle" '
             f'transform="rotate(-90 30 {cy:.0f})">WATTS DISSIPATED</text>')
    s.append(f'<text x="{ax.x0 + ax.w/2:.0f}" y="{ax.y0 + ax.h + 56}" '
             f'class="axl" text-anchor="middle">POWER AT THE SPEAKER (W)</text>')
    s.append("</svg>")
    return "".join(s)


# --- lo que se come el altavoz ---------------------------------------------
# Un altavoz de guitarra convierte en sonido un 1-5 % de lo que recibe: el
# resto calienta la bobina.  O sea que "potencia entregada" y "disipacion en
# el altavoz" son practicamente el mismo numero, y es el que hay que comparar
# con los vatios de catalogo del altavoz.  Pero OJO con medirlo sobre 8 ohm
# muertos: la impedancia real sube con la frecuencia y en la resonancia, asi
# que la potencia que de verdad entra depende mucho del tono que se toque.
SPK_FREQS = (82.0, 220.0, 440.0, 1000.0, 2000.0)


def speaker_table(amp=0.32):
    """Potencia en el altavoz contra frecuencia, carga muerta y modelo real."""
    import bench
    bench.PROBES = ("SPEAKER",)
    work = Path(tempfile.mkdtemp(prefix="spk_"))
    out = ["", "LO QUE ENTRA EN EL ALTAVOZ  (entrada fija de "
           f"{amp*2000:.0f} mVpp, ganancia {DRIVE})", "",
           "  Hz     8 ohm muertos W    modelo de impedancia W"]
    for f in SPK_FREQS:
        row = []
        for model in (False, True):
            r = bench.run(work, tag=f"s{f:.0f}_{int(model)}", amp=amp,
                          drive=DRIVE, u1=0, u2=0, freq=f, rload=RLOAD,
                          vraw=VRAW, mains=MAINS, settle=SETTLE,
                          speaker_model=model, **TONE)
            row.append(r["meas"]["p_spk"])
        out.append(f"  {f:6.0f} {row[0]:15.2f} {row[1]:24.2f}")
        print(out[-1], flush=True)
    return "\n".join(out)


def main() -> None:
    js = OUT.with_suffix(".json")
    if "--resim" in sys.argv or not js.exists():
        js.write_text(json.dumps(simulate(), indent=1), encoding="utf-8")
    rows = json.loads(js.read_text(encoding="utf-8"))
    print()
    print(table(rows))
    svg = draw(rows)
    OUT.with_suffix(".svg").write_text(svg, encoding="utf-8")
    rasterize(svg, OUT.with_suffix(".png"), 820, 500, scale=2.4)
    if "--speaker" in sys.argv:
        print(speaker_table())


if __name__ == "__main__":
    main()
