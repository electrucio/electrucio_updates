#!/usr/bin/env python3
"""Curvas de lo que ve la CARGA en powersupply/psu_cvcc, en SVG.

`verify_psu_cvcc.py` dice si el diseno cumple y `caracteriza_psu_cvcc.py` da los
numeros con los que compararse con otras fuentes.  Esto es la tercera pata: las
FORMAS DE ONDA.  Hay cosas que un numero no cuenta -si un escalon vuelve por
arriba o por abajo, si la entrada en CC tiene codo, cuanto dura el tramo en el
que la carga ve una tension que no pediste- y que en una grafica se ven solas.

    python3 tools/ltspice/curvas_psu_cvcc.py                # todas
    python3 tools/ltspice/curvas_psu_cvcc.py --only corto
    python3 tools/ltspice/curvas_psu_cvcc.py --png          # ademas rasteriza

Las figuras salen en powersupply/psu_cvcc/curvas/ (ignorado por git: es
material derivado y se rehace con este script).

CRITERIO DE LAS GRAFICAS
  - Tension y corriente NUNCA comparten eje: son magnitudes distintas y un eje
    doble hace que cualquier cruce parezca un suceso.  Van en dos paneles
    apilados con el mismo eje de tiempos.
  - La tension es la del BORNE, V(VOUT)-V(VRTN), no V(VOUT) contra masa: la
    caida del shunt esta dentro del lazo y lo que ve la carga es la diferencia.
  - Las series se etiquetan sobre la propia curva ademas de con color.
  - La escala de tiempos arranca justo antes del suceso: el arranque de la
    fuente (1,5 s de transitorio) taparia cualquier detalle de 2 ms.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from svgplot import Ax, frame, grid, linear_ticks, rasterize   # noqa: E402
from verify_psu_cvcc import Bench, R1_TOTAL, R2_COARSE, R2_FINE  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "powersupply/psu_cvcc/curvas"

# Misma paleta y mismas clases que verify_amp_tran.py, para que las figuras del
# repo se parezcan entre si.
PAL = dict(bg="#ffffff", ink="#14181f", muted="#5a626f",
           grid="#ccd2dc", minor="#e8ebf0", frame="#8d95a3")
SER = ("#3a5199", "#a83a34", "#5d8a3e", "#b5762a", "#2f7f96")
STYLE = """
.h1{{font:600 21px "IBM Plex Sans Condensed","IBM Plex Sans",sans-serif;fill:{ink}}}
.cond{{font:400 12px "IBM Plex Mono",ui-monospace,monospace;fill:{muted};letter-spacing:.06em}}
.tick{{font:400 13px "IBM Plex Mono",ui-monospace,monospace;fill:{muted};font-variant-numeric:tabular-nums}}
.axl{{font:500 12px "IBM Plex Mono",ui-monospace,monospace;fill:{ink};letter-spacing:.12em}}
.lgv{{font:400 12px "IBM Plex Mono",ui-monospace,monospace;fill:{ink}}}
.ann{{font:400 12px "IBM Plex Sans",system-ui,sans-serif;fill:{muted};
  paint-order:stroke;stroke:{bg};stroke-width:4px;stroke-linejoin:round}}
.lbl{{font:600 12px "IBM Plex Mono",ui-monospace,monospace;
  paint-order:stroke;stroke:{bg};stroke-width:4px;stroke-linejoin:round}}
"""

W, H = 1240, 760
PAD_L, PAD_R = 110, 150


def borne(d):
    """Lo que ve la carga: la diferencia entre bornes, no V(VOUT) a masa."""
    return d["V(vout)"] - d["V(vrtn)"]


def icarga(d):
    """Corriente por la carga, en amperios y positiva al salir de la fuente."""
    return np.abs(d["I(Rload)"])


def _axlabels(ax, xl, yl):
    return (f'<text x="{ax.x0 + ax.w / 2:.0f}" y="{ax.y0 + ax.h + 46:.0f}" '
            f'class="axl" text-anchor="middle">{xl}</text>'
            f'<text class="axl" text-anchor="middle" transform="translate('
            f'{ax.x0 - 72:.0f},{ax.y0 + ax.h / 2:.0f}) rotate(-90)">{yl}</text>')


def _svg(title, cond, body, h=H):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {h}" '
            f'width="100%" style="display:block;width:100%;height:auto">'
            f'<style>{STYLE.format(**PAL)}</style>'
            f'<rect width="{W}" height="{h}" fill="{PAL["bg"]}"/>'
            f'<text x="{PAD_L - 40}" y="34" class="h1">{title}</text>'
            f'<text x="{PAD_L - 40}" y="56" class="cond">{cond}</text>'
            f'{body}</svg>')


def _nice(lo, hi, n=6):
    """Limites redondos que contienen [lo, hi], y el paso de rejilla."""
    if hi - lo < 1e-9:
        hi = lo + 1.0
    span = hi - lo
    raw = span / n
    mag = 10 ** np.floor(np.log10(raw))
    for mult in (1, 2, 2.5, 5, 10):
        if raw <= mult * mag:
            step = mult * mag
            break
    lo2 = np.floor(lo / step) * step
    hi2 = np.ceil(hi / step) * step
    return float(lo2), float(hi2), float(step)


def _yticks(lo, hi, step):
    """(valor, es_mayor) cada medio paso, mayores cada paso.  Admite decimales."""
    out, k = [], 0
    n = int(round((hi - lo) / (step / 2)))
    for k in range(n + 1):
        v = lo + k * step / 2
        out.append((v, k % 2 == 0))
    return out


def panel(y0, h, xlim, series, ylabel, xlabel=None, xstep=None, anot=()):
    """Un panel: eje de tiempos comun, una magnitud, varias series."""
    # Limites ROBUSTOS.  Un corto franco descarga Cout en microsegundos y mete
    # un pico de decenas de amperios que dura cuatro puntos: con min/max a pelo,
    # ese pico aplasta toda la grafica y no se ve ni el regimen.  Se encuadra el
    # cuerpo de la señal y el pico real se ANOTA, que no es lo mismo que
    # esconderlo.
    vals = np.concatenate([ys for _, _, ys in series])
    lo_r, hi_r = (float(v) for v in np.percentile(vals, [0.2, 99.8]))
    lo_t, hi_t = float(np.min(vals)), float(np.max(vals))
    margen = 0.08 * max(hi_r - lo_r, 1e-6)
    lo, hi, step = _nice(lo_r - margen, hi_r + margen)
    picos = []
    if hi_t > hi + 0.5 * step:
        picos.append(f"pico real {hi_t:+.1f}")
    if lo_t < lo - 0.5 * step:
        picos.append(f"minimo real {lo_t:+.1f}")
    ax = Ax(PAD_L, y0, W - PAD_L - PAD_R, h, xlim, (lo, hi))

    xt = linear_ticks(ax, xstep, xstep / 2,
                      fmt=lambda v: f"{v:g}") if xstep else []
    out = [grid(ax, PAL, xt, yvals=_yticks(lo, hi, step),
                yfmt=lambda v: f"{v:g}")]
    etiquetas = []
    for i, (lab, xs, ys) in enumerate(series):
        col = SER[i % len(SER)]
        out.append(f'<path d="{ax.path(xs, ys)}" fill="none" stroke="{col}" '
                   f'stroke-width="2" stroke-linejoin="round"/>')
        # etiqueta directa al final de la curva: la identidad no es solo color
        j = int(np.argmin(np.abs(xs - ax.xmax * 0.999)))
        etiquetas.append([ax.y(ys[j]) + 4, lab, col])
    # Curvas que acaban juntas (o encima) dejarian las etiquetas pisadas y no se
    # leeria ninguna: se separan 16 px manteniendo el orden vertical.
    etiquetas.sort(key=lambda e: e[0])
    for k in range(1, len(etiquetas)):
        if etiquetas[k][0] - etiquetas[k - 1][0] < 16:
            etiquetas[k][0] = etiquetas[k - 1][0] + 16
    for y, lab, col in etiquetas:
        out.append(f'<text x="{ax.x0 + ax.w + 10:.0f}" y="{y:.0f}" '
                   f'class="lbl" fill="{col}">{lab}</text>')
    for xa, texto in anot:
        out.append(f'<line x1="{ax.x(xa):.1f}" y1="{ax.y0}" '
                   f'x2="{ax.x(xa):.1f}" y2="{ax.y0 + ax.h}" '
                   f'stroke="{PAL["muted"]}" stroke-width="1" '
                   f'stroke-dasharray="4 4"/>'
                   f'<text x="{ax.x(xa) + 6:.0f}" y="{ax.y0 + 16}" '
                   f'class="ann">{texto}</text>')
    if picos:
        out.append(f'<text x="{ax.x0 + ax.w - 8:.0f}" y="{ax.y0 + 18:.0f}" '
                   f'class="ann" text-anchor="end">'
                   f'fuera de escala: {", ".join(picos)}</text>')
    out.append(frame(ax, PAL))
    out.append(_axlabels(ax, xlabel or "", ylabel))
    return "".join(out)


def figura(nombre, titulo, cond, t0, t1, series_v, series_i, anot=()):
    """Dos paneles apilados: tension arriba, corriente abajo."""
    _, _, xstep = _nice(t0, t1, 8)
    body = panel(96, 280, (t0, t1), series_v, "VOLTIOS EN EL BORNE",
                 xstep=xstep, anot=anot)
    body += panel(452, 240, (t0, t1), series_i, "AMPERIOS EN LA CARGA",
                  xlabel="TIEMPO (ms)", xstep=xstep, anot=anot)
    svg = _svg(titulo, cond, body)
    p = OUT / f"{nombre}.svg"
    p.write_text(svg, encoding="utf-8")
    print(f"  {p.relative_to(OUT.parents[2])}")
    return p


def figura_mando(nombre, titulo, cond, curvas, xlabel, ylabel):
    """Una sola magnitud contra la posicion de un mando (no contra el tiempo)."""
    xs_all = np.concatenate([x for _, x, _ in curvas])
    body = panel(96, 480, (float(np.min(xs_all)), float(np.max(xs_all))),
                 curvas, ylabel)
    # el eje X aqui es % de recorrido, no tiempo: lo rotulo a mano
    ax = Ax(PAD_L, 96, W - PAD_L - PAD_R, 480,
            (float(np.min(xs_all)), float(np.max(xs_all))), (0, 1))
    for v in np.linspace(ax.xmin, ax.xmax, 6):
        body += (f'<text x="{ax.x(v):.0f}" y="{96 + 480 + 24}" class="tick" '
                 f'text-anchor="middle">{v:.0f}</text>')
    body += (f'<text x="{ax.x0 + ax.w / 2:.0f}" y="{96 + 480 + 58}" '
             f'class="axl" text-anchor="middle">{xlabel}</text>')
    svg = _svg(titulo, cond, body, h=660)
    p = OUT / f"{nombre}.svg"
    p.write_text(svg, encoding="utf-8")
    print(f"  {p.relative_to(OUT.parents[2])}")
    return p


# =========================================================== los escenarios ===
# vset para una tension dada, con la escala nueva (1,25*R2/R1 + Iadj*R2)
def vs_de(volts):
    r2 = volts / (1.25 / R1_TOTAL + 50e-6)
    return min(r2 / (R2_COARSE + R2_FINE), 1.0)


V20 = vs_de(20.0)


def esc_carga(b):
    """Escalon de carga dentro de CV, ida y vuelta."""
    pwl = "PWL(0 100 0.5 100 0.500001 22 0.62 22 0.620001 100)"
    d, _, _ = b.run("c_carga", tap=2, vset=V20, iset=1.0, load=pwl,
                    tend=0.72, tstart=0.49, step="2u", meas_from=0.7)
    t = (d["time"] - 0.5) * 1e3
    return figura(
        "01_escalon_carga_cv",
        "Escalon de carga dentro de CV",
        "TAP=2 - 20 V de consigna - 100 ohm -> 22 ohm -> 100 ohm, flancos de 1 us",
        -8, 220,
        [("V borne", t, borne(d))], [("I carga", t, icarga(d))],
        anot=[(0, "carga ON"), (120, "carga OFF")])


def esc_cc(b):
    """Escalon de carga que cruza a CC y vuelve."""
    pwl = "PWL(0 100 0.5 100 0.500001 10 0.75 10 0.750001 100)"
    d, _, _ = b.run("c_cc", tap=2, vset=V20, iset=1.0, load=pwl,
                    tend=0.95, tstart=0.49, step="5u", meas_from=0.9)
    t = (d["time"] - 0.5) * 1e3
    return figura(
        "02_escalon_a_cc",
        "Escalon de carga que cruza a corriente constante",
        "TAP=2 - 20 V de consigna, limite al maximo - 100 ohm -> 10 ohm -> 100 ohm",
        -10, 450,
        [("V borne", t, borne(d))], [("I carga", t, icarga(d))],
        anot=[(0, "entra en CC"), (250, "vuelve a CV")])


def esc_corto(b):
    """Cortocircuito en caliente, con la fuente dando tension."""
    pwl = "PWL(0 22 0.5 22 0.500001 0.01 0.8 0.01 0.800001 22)"
    d, _, _ = b.run("c_corto", tap=2, vset=V20, iset=1.0, load=pwl,
                    tend=1.05, tstart=0.49, step="5u", meas_from=1.0)
    t = (d["time"] - 0.5) * 1e3
    return figura(
        "03_corto_caliente",
        "Cortocircuito en caliente y recuperacion",
        "TAP=2 - 20 V de consigna, limite al maximo - 22 ohm -> 0,01 ohm -> 22 ohm",
        -10, 550,
        [("V borne", t, borne(d))], [("I carga", t, icarga(d))],
        anot=[(0, "corto"), (300, "se quita")])


def esc_mando_v(b):
    """Cambio brusco del pote de tension (los dos mandos a la vez)."""
    pat = [(f"Vset VSET 0 {V20}",
            f"Vset VSET 0 PWL(0 {V20} 0.5 {V20} 0.500001 0.012"
            f" 0.75 0.012 0.750001 {V20})"),
           (f"Vsetf VSETF 0 {V20}",
            f"Vsetf VSETF 0 PWL(0 {V20} 0.5 {V20} 0.500001 0.012"
            f" 0.75 0.012 0.750001 {V20})")]
    d, _, _ = b.run("c_mandov", tap=2, vset=V20, iset=1.0, load=22,
                    tend=1.0, tstart=0.49, step="5u", meas_from=0.95,
                    patches=pat)
    t = (d["time"] - 0.5) * 1e3
    return figura(
        "04_mando_tension_brusco",
        "Cambio brusco de la consigna de tension",
        "TAP=2 - 22 ohm de carga - 20 V -> 0,5 V -> 20 V, de golpe",
        -10, 490,
        [("V borne", t, borne(d))], [("I carga", t, icarga(d))],
        anot=[(0, "baja"), (250, "sube")])


def esc_mando_fino(b):
    """Solo el mando FINO, que es el que se usa para afinar."""
    pat = [("Vsetf VSETF 0 " + str(V20),
            "Vsetf VSETF 0 PWL(0 " + str(V20) + " 0.5 " + str(V20)
            + " 0.500001 0 0.7 0 0.700001 1)")]
    d, _, _ = b.run("c_mandof", tap=2, vset=V20, iset=1.0, load=22,
                    tend=0.95, tstart=0.49, step="5u", meas_from=0.9,
                    patches=pat)
    t = (d["time"] - 0.5) * 1e3
    return figura(
        "05_mando_fino",
        "Solo el mando fino: de un extremo al otro",
        f"TAP=2 - grueso fijo - el fino cubre {1.25 * R2_FINE / R1_TOTAL:.1f} V "
        "de los 41 V de escala",
        -10, 440,
        [("V borne", t, borne(d))], [("I carga", t, icarga(d))],
        anot=[(0, "fino al minimo"), (200, "fino al maximo")])


def esc_mando_i(b):
    """Cambio brusco del limite de corriente estando en CC."""
    pat = [("Visetadj ISETADJ 0 1.0",
            "Visetadj ISETADJ 0 PWL(0 1 0.5 1 0.500001 0.22"
            " 0.9 0.22 0.900001 1)")]
    d, _, _ = b.run("c_mandoi", tap=2, vset=V20, iset=1.0, load=10,
                    tend=1.25, tstart=0.49, step="5u", meas_from=1.2,
                    patches=pat)
    t = (d["time"] - 0.5) * 1e3
    return figura(
        "06_mando_corriente_brusco",
        "Cambio brusco del limite de corriente, en CC",
        "TAP=2 - 10 ohm de carga (fuerza CC) - limite 1,34 A -> 0,3 A -> 1,34 A",
        -20, 740,
        [("V borne", t, borne(d))], [("I carga", t, icarga(d))],
        anot=[(0, "baja el limite"), (400, "lo sube")])


def esc_arranque(b):
    """Arranque desde cero con tres consignas distintas."""
    sv, si = [], []
    for lab, vs in (("fondo", 1.0), ("20 V", V20), ("0,5 V", 0.012)):
        d, _, _ = b.run(f"c_arr_{lab[:3]}".replace(" ", ""), tap=2, vset=vs,
                        iset=1.0, load=100, tend=0.6, step="20u",
                        meas_from=0.55)
        t = d["time"] * 1e3
        sv.append((lab, t, borne(d)))
        si.append((lab, t, icarga(d)))
    return figura(
        "07_arranque",
        "Arranque desde cero, tres consignas",
        "TAP=2 - 100 ohm de carga - desde el instante de dar tension",
        0, 600, sv, si)


def esc_extremos(b):
    """Los dos mandos en sus extremos, en vacio y con carga."""
    sv, si = [], []
    casos = (("min, vacio", 0.0, 0.0, 1e6), ("min, 22 ohm", 0.0, 0.0, 22),
             ("max, vacio", 1.0, 1.0, 1e6), ("max, 22 ohm", 1.0, 1.0, 22))
    for lab, vs, vf, rl in casos:
        d, _, _ = b.run(f"c_ext_{lab[:3]}{rl:.0f}".replace(" ", ""), tap=3,
                        vset=vs, vsetf=vf, iset=1.0, load=rl, tend=0.6,
                        step="20u", meas_from=0.55)
        t = d["time"] * 1e3
        sv.append((lab, t, borne(d)))
        si.append((lab, t, icarga(d)))
    return figura(
        "08_extremos_mandos",
        "Extremos del recorrido de los mandos",
        "TAP=3 - los dos potes al minimo y al maximo, en vacio y con 22 ohm",
        0, 600, sv, si)


def esc_escala(b):
    """Vout contra la posicion del grueso, para tres posiciones del fino."""
    curvas = []
    for lab, vf in (("fino 0 %", 0.0), ("fino 50 %", 0.5), ("fino 100 %", 1.0)):
        xs, ys = [], []
        for vs in np.linspace(0, 1, 7):
            d, _, q = b.run(f"c_esc_{vf}_{vs:.1f}", tap=3, vset=float(vs),
                            vsetf=vf, iset=1.0, load=1000, tend=0.8,
                            step="50u", meas_from=0.7)
            xs.append(vs * 100)
            ys.append(q.get("vout_dc", float(np.median(borne(d)[-50:]))))
        curvas.append((lab, np.array(xs), np.array(ys)))
    return figura_mando(
        "09_escala_de_los_mandos",
        "La escala: grueso contra fino",
        "TAP=3 - en vacio - las tres curvas se separan "
        f"{1.25 * R2_FINE / R1_TOTAL:.1f} V, que es el recorrido del fino",
        curvas, "POSICION DEL POTE GRUESO (% de recorrido)",
        "VOLTIOS EN EL BORNE")


ESCENARIOS = {
    "carga": esc_carga,
    "cc": esc_cc,
    "corto": esc_corto,
    "mando_v": esc_mando_v,
    "mando_fino": esc_mando_fino,
    "mando_i": esc_mando_i,
    "arranque": esc_arranque,
    "extremos": esc_extremos,
    "escala": esc_escala,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=sorted(ESCENARIOS))
    ap.add_argument("--png", action="store_true",
                    help="rasteriza cada SVG a PNG con Chrome")
    ap.add_argument("--workdir")
    ap.add_argument("--keep", action="store_true",
                    help="no borrar el directorio de trabajo (son cientos de MB)")
    a = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    # Mismo patron que verify_psu_cvcc.py: ruta FIJA y rmtree al salir.  Un
    # transitorio de 1 s con paso de 5 us y 80 variables son cientos de megas de
    # .raw, y nueve escenarios por pasada; con tempfile.mkdtemp() sin borrar,
    # unas cuantas tandas llenan el disco (paso el 2026-11-25: 11 GB).
    wd = Path(a.workdir) if a.workdir else Path("/tmp/psu_cvcc_curvas")
    b = Bench(wd)
    try:
        quiere = [a.only] if a.only else list(ESCENARIOS)
        print(f"escenarios: {', '.join(quiere)}\n")
        hechas = []
        for nombre in quiere:
            print(f"-- {nombre}")
            hechas.append(ESCENARIOS[nombre](b))

        if a.png:
            print("\nrasterizando:")
            for p in hechas:
                png = rasterize(p.read_text(encoding="utf-8"),
                                p.with_suffix(".png"), W, H)
                print(f"  {png.name}")
        print(f"\n{len(hechas)} figuras en {OUT}")
    finally:
        if not a.keep and not a.workdir:
            shutil.rmtree(wd, ignore_errors=True)


if __name__ == "__main__":
    main()
