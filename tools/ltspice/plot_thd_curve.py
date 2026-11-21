#!/usr/bin/env python3
"""Curva de THD par e impar contra ganancia, para las cuatro combinaciones de
recortadores, con las impresiones de oido del autor anotadas encima.

    python3 tools/ltspice/plot_thd_curve.py            # redibuja desde el JSON
    python3 tools/ltspice/plot_thd_curve.py --resim    # vuelve a simular (~90 s)

Escribe guitar_amplifier/quasimod_thd.{json,svg,png}. El JSON es la fuente de
la figura: mientras exista, dibujar es instantaneo y no toca LTspice.

El nivel de entrada, 700 mVpp, no es arbitrario: es la senoidal que tiene el
mismo valor eficaz que los acordes medidos con la guitarra (230 mV RMS). Lo que
equipara un tono de prueba a material real es el RMS y no el pico, porque el
pico solo manda durante los pocos milisegundos del ataque mientras que el resto
de la nota, que es lo que se juzga, lo gobierna el eficaz. Con el pico ocurre
esto: una senoidal a los 1,6 Vpp de un acorde da 23,9% de THD con la ganancia a
0,5, donde la guitarra suena limpia. Esa diferencia es factor de cresta, 3 dB
de una senoidal contra unos 18 de un acorde.

Ojo con "both" a ganancia 0,5: ahi la distorsion es casi toda impar (38,1%
contra 9,6% de par), asi que leer solo la continua de esa serie engana y hay
que mirar tambien la discontinua.

NECESITA el .net de LTspice para --resim; ver la cabecera de bench.py.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from svgplot import Ax, frame, grid, linear_ticks, rasterize   # noqa: E402

OUT = ROOT / "guitar_amplifier" / "quasimod_thd"

# --- condiciones del barrido ------------------------------------------------
AMP_PP = 0.700                 # Vpp en el jack: mismo RMS que los acordes
FREQ = 1000.0
RLOAD = 8.0
VRAW = 50.0                    # continua rigida; a vol 0,5 el rail casi no cae
TONE = dict(treble=0.5, bass=0.5, vol=0.5)
DRIVES = [round(0.1 * i, 1) for i in range(11)]
SERIES = (("none", "NO DIODES", "#3a5199", 0, 0),
          ("u1", "U1 ONLY 1.3 V", "#5d8a3e", 1, 0),
          ("u2", "U2 ONLY 0.63 V", "#b5762a", 0, 1),
          ("both", "BOTH", "#a83a34", 1, 1))

PAL = dict(bg="#ffffff", ink="#14181f", muted="#5a626f",
           grid="#ccd2dc", minor="#e8ebf0", frame="#8d95a3")


def simulate() -> dict:
    """Un .tran por (combinacion, ganancia). Tarda cerca de 90 s."""
    import bench
    bench.PROBES = ("SPEAKER",)
    work = Path(tempfile.mkdtemp(prefix="thd_curve_"))
    print(f"simulando {len(SERIES) * len(DRIVES)} puntos en {work}")
    data = {}
    for key, _, _, u1, u2 in SERIES:
        data[key] = []
        for d in DRIVES:
            r = bench.run(work, tag=f"{key}_{d}", amp=AMP_PP / 2, drive=d,
                          u1=u1, u2=u2, freq=FREQ, rload=RLOAD, vraw=VRAW,
                          **TONE)
            total, even, odd = bench.thd_split(r["SPEAKER"])
            data[key].append(dict(drive=d, thd=total or 0.0, even=even or 0.0,
                                  odd=odd or 0.0,
                                  vrms=r["meas"]["speaker_rms"]))
            print(f"  {key:>5} {d:>4} -> {data[key][-1]['thd']:6.2f}%")
    return data


def draw(data: dict) -> str:
    w, h = 980, 660
    ax = Ax(92, 126, 856, 418, (0, 1), (0, 92))
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
         f'viewBox="0 0 {w} {h}"><rect width="{w}" height="{h}" '
         f'fill="{PAL["bg"]}"/>',
         f'''<style>
  .cond{{font:400 12px "IBM Plex Mono",ui-monospace,monospace;fill:{PAL['muted']};letter-spacing:.05em}}
  .tick{{font:400 13px "IBM Plex Mono",ui-monospace,monospace;fill:{PAL['muted']};font-variant-numeric:tabular-nums}}
  .axl{{font:500 12px "IBM Plex Mono",ui-monospace,monospace;fill:{PAL['ink']};letter-spacing:.14em}}
  .lgl{{font:500 11px "IBM Plex Mono",ui-monospace,monospace;fill:{PAL['ink']};letter-spacing:.08em}}
  .lgn{{font:400 11px "IBM Plex Mono",ui-monospace,monospace;fill:{PAL['muted']};letter-spacing:.08em}}
</style>''']

    s.append(f'<text x="92" y="32" class="cond" fill="{PAL["ink"]}">'
             f'{AMP_PP * 1000:g}mVpp @ {FREQ / 1000:g}Khz input &#183; '
             f'Load {RLOAD:g} ohm &#183; Bass {TONE["bass"]} '
             f'Treble {TONE["treble"]} Volume {TONE["vol"]}</text>')
    s.append(f'<text x="92" y="54" class="cond">HARMONIC DISTORTION AT THE '
             f'SPEAKER, SPLIT INTO EVEN AND ODD</text>')

    lx = 92
    for _, label, col, _, _ in SERIES:
        s.append(f'<line x1="{lx}" y1="78" x2="{lx + 28}" y2="78" '
                 f'stroke="{col}" stroke-width="2.6" stroke-linecap="round"/>')
        s.append(f'<text x="{lx + 36}" y="82" class="lgl">{label}</text>')
        lx += 44 + len(label) * 7.3
    s.append(f'<text x="92" y="102" class="lgn">SOLID = EVEN HARMONICS '
             f'&#183; DASHED = ODD HARMONICS</text>')

    s.append(grid(ax, PAL, linear_ticks(ax, 0.2, 0.1), ystep=5, ymajor=10,
                  yfmt=lambda v: f"{v:g}"))
    s.append(frame(ax, PAL))

    for key, _, col, _, _ in SERIES:
        rows = data[key]
        xs = [p["drive"] for p in rows]
        s.append(f'<path d="{ax.path(xs, [p["even"] for p in rows])}" '
                 f'fill="none" stroke="{col}" stroke-width="2.3" '
                 f'stroke-linejoin="round" stroke-linecap="round"/>')
        s.append(f'<path d="{ax.path(xs, [p["odd"] for p in rows])}" '
                 f'fill="none" stroke="{col}" stroke-width="1.6" '
                 f'stroke-linejoin="round" stroke-dasharray="5 4"/>')

    cy = ax.y0 + ax.h / 2
    s.append(f'<text x="34" y="{cy:.0f}" class="axl" text-anchor="middle" '
             f'transform="rotate(-90 34 {cy:.0f})">THD %</text>')
    s.append(f'<text x="{ax.x0 + ax.w / 2:.0f}" y="{ax.y0 + ax.h + 58}" '
             f'class="axl" text-anchor="middle">GAIN</text>')
    s.append("</svg>")
    return "".join(s)


def main() -> None:
    js = OUT.with_suffix(".json")
    if "--resim" in sys.argv or not js.exists():
        js.write_text(json.dumps(simulate(), indent=1), encoding="utf-8")
    data = json.loads(js.read_text(encoding="utf-8"))
    svg = draw(data)
    OUT.with_suffix(".svg").write_text(svg, encoding="utf-8")
    rasterize(svg, OUT.with_suffix(".png"), 980, 660, scale=2.4)
    for ext in ("json", "svg", "png"):
        print(OUT.with_suffix("." + ext))


if __name__ == "__main__":
    main()
