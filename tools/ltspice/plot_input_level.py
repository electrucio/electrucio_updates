#!/usr/bin/env python3
"""La senal de guitarra que entra al modelo, en milivoltios y segundos.

    python3 tools/ltspice/plot_input_level.py

Escribe guitar_amplifier/quasimod_input.{svg,png}.

Existe porque "1.5 Vpp" es verdad y enganosa a la vez: es el pico mas alto de
todo el corte, y el resto del tiempo la guitarra esta muy por debajo.  Lo que
gobierna lo que se oye es el eficaz, no ese pico, y la distancia entre los dos
-- el factor de cresta -- es justo lo que distingue una guitarra de un tono de
prueba.  Por eso la curva de THD se hace con 700 mVpp de senoidal y no con
1.5: esa senoidal tiene el MISMO eficaz que estos acordes.

Se dibuja la envolvente (minimo y maximo por columna de pixeles) y no la onda
muestra a muestra: son 887.000 muestras para 700 pixeles, asi que trazarlas
todas da un borron negro y un SVG de varios megas.
"""
from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from svgplot import Ax, frame, grid, linear_ticks, rasterize       # noqa: E402

AUDIO = ROOT / "junk/guitar_preamplifier/audios"
DRY = AUDIO / "dry_guitar_44100_selection.wav"
OUT = ROOT / "guitar_amplifier" / "quasimod_input"
PEAK_MV = 750.0                  # el mismo de render_audio.py
PAL = dict(bg="#ffffff", ink="#14181f", muted="#5a626f",
           grid="#ccd2dc", minor="#e8ebf0", frame="#8d95a3")
COL = "#3a5199"


def read(path):
    with wave.open(str(path)) as w:
        n, sr, ch, sw = (w.getnframes(), w.getframerate(),
                         w.getnchannels(), w.getsampwidth())
        raw = w.readframes(n)
    a = np.frombuffer(raw, "<i2").astype(np.float64) / 32768.0
    if ch > 1:
        a = a.reshape(-1, ch)[:, 0]
    return a, sr


def main() -> None:
    a, sr = read(DRY)
    v = a * (PEAK_MV / np.abs(a).max())        # en mV
    t_end = len(v) / sr
    rms = float(np.sqrt(np.mean(v * v)))
    pk = float(np.abs(v).max())
    crest = 20 * np.log10(pk / rms)

    w, h = 900, 420
    ax = Ax(84, 108, 766, 236, (0, t_end), (-800, 800))
    cols = 766
    edges = np.linspace(0, len(v), cols + 1).astype(int)
    lo = np.array([v[edges[i]:edges[i + 1]].min() for i in range(cols)])
    hi = np.array([v[edges[i]:edges[i + 1]].max() for i in range(cols)])
    xs = np.linspace(0, t_end, cols)

    pts = [f"{ax.x(x):.1f},{ax.y(y):.1f}" for x, y in zip(xs, hi)]
    pts += [f"{ax.x(x):.1f},{ax.y(y):.1f}" for x, y in zip(xs[::-1], lo[::-1])]

    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
         f'viewBox="0 0 {w} {h}"><rect width="{w}" height="{h}" '
         f'fill="{PAL["bg"]}"/>',
         f'''<style>
  .cond{{font:400 12px "IBM Plex Mono",ui-monospace,monospace;fill:{PAL['muted']};letter-spacing:.05em}}
  .tick{{font:400 13px "IBM Plex Mono",ui-monospace,monospace;fill:{PAL['muted']};font-variant-numeric:tabular-nums}}
  .axl{{font:500 12px "IBM Plex Mono",ui-monospace,monospace;fill:{PAL['ink']};letter-spacing:.14em}}
  .ann{{font:500 11px "IBM Plex Sans",system-ui,sans-serif}}
</style>''']
    s.append(f'<text x="84" y="34" class="cond" fill="{PAL["ink"]}">'
             f'GUITAR SIGNAL AT THE INPUT JACK, AS FED TO THE MODEL</text>')
    s.append(f'<text x="84" y="56" class="cond">peak {pk:.0f} mV '
             f'({2*pk/1000:.1f} Vpp) &#183; rms {rms:.0f} mV &#183; '
             f'crest factor {crest:.1f} dB</text>')
    s.append(grid(ax, PAL, linear_ticks(ax, 2, 1, fmt=lambda x: f"{x:g}"),
                  ystep=100, ymajor=200, yfmt=lambda y: f"{y:g}"))
    s.append(frame(ax, PAL))
    s.append(f'<polygon points="{" ".join(pts)}" fill="{COL}" '
             f'fill-opacity=".85" stroke="none"/>')
    for y, lab in ((rms, "rms"), (-rms, None)):
        s.append(f'<line x1="{ax.x0}" y1="{ax.y(y):.1f}" x2="{ax.x0+ax.w}" '
                 f'y2="{ax.y(y):.1f}" stroke="#a83a34" stroke-width="1.2" '
                 f'stroke-dasharray="5 4"/>')
        if lab:
            s.append(f'<text x="{ax.x0+ax.w-6:.0f}" y="{ax.y(y)-7:.1f}" '
                     f'class="ann" fill="#a83a34" text-anchor="end">'
                     f'rms {rms:.0f} mV</text>')
    cy = ax.y0 + ax.h / 2
    s.append(f'<text x="28" y="{cy:.0f}" class="axl" text-anchor="middle" '
             f'transform="rotate(-90 28 {cy:.0f})">mV</text>')
    s.append(f'<text x="{ax.x0 + ax.w/2:.0f}" y="{ax.y0+ax.h+52}" class="axl" '
             f'text-anchor="middle">SECONDS</text>')
    s.append("</svg>")
    svg = "".join(s)
    OUT.with_suffix(".svg").write_text(svg, encoding="utf-8")
    rasterize(svg, OUT.with_suffix(".png"), w, h, scale=2.4)
    print(f"pico {pk:.0f} mVp ({2*pk:.0f} mVpp), rms {rms:.1f} mV, "
          f"cresta {crest:.1f} dB, {t_end:.2f} s")
    pcts = np.percentile(np.abs(v), [50, 90, 99])
    print("percentiles de |v|: " + "  ".join(
        f"p{p}={x:.0f} mV" for p, x in zip((50, 90, 99), pcts)))
    print(OUT.with_suffix(".png"))


if __name__ == "__main__":
    main()
