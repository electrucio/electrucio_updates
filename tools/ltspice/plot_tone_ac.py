#!/usr/bin/env python3
"""Genera la figura de respuesta en frecuencia vs bass/treble del 40W.

Mide el AMPLIFICADOR SOLO: preamp + etapa de potencia, con carga resistiva de
7.5 ohm, y sin el pickup ni el modelo de altavoz.  La figura va rotulada en
INGLES, en estilo de hoja de caracteristicas.

    python3 tools/ltspice/plot_tone_ac.py -o /tmp/fig      # PNG + SVG + JSON
    python3 tools/ltspice/plot_tone_ac.py --scale 4        # PNG mas grande
    python3 tools/ltspice/plot_tone_ac.py --no-png         # solo vectorial

Dos exclusiones, hechas de dos maneras distintas a proposito:

* El PICKUP se DIVIDE, no se quita.  En un .ac todo es lineal, asi que
  V(SPEAKER)/V(PICKUP_OUT) es el amplificador atacado desde su entrada real y
  CON la carga del pickup puesta (~111k y 620 pF), que es lo que hay cuando
  enchufas una guitarra.  Quitarlo del netlist cambiaria esa carga.
* El ALTAVOZ si se SUSTITUYE, por 7.5 ohm resistivos: su impedancia no es un
  factor que se pueda dividir fuera, porque interactua con la impedancia de
  salida del amplificador.  Cambiarlo por carga muerta es lo que hace un banco.
  El condensador de salida C10 (3300 uF) NO se toca: es parte del ampli.

El netlist `AudioAmpCompl-40W.net` NO esta versionado: en un clon limpio hay que
exportarlo una vez desde la GUI (`File > Export Netlist`).

Salidas:
    tone_ac.png     la figura rasterizada (Chrome headless), lista para publicar
    tone_ac.svg     la misma figura en vectorial
    tone_ac.json    los datos (frecuencia + las 25 curvas) para otros usos
"""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_tone_ac import Bench, db                      # noqa: E402

POS = (0.0, 0.25, 0.5, 0.75, 1.0)
SWEEP = ".ac dec 60 5 2Meg"
F_LO, F_HI = 10.0, 1e6             # ventana de la figura
DB_LO, DB_HI = -30.0, 45.0

# TREBLE es una variable ORDINAL, asi que la rampa va ordenada (frio -> caliente)
# y desaturada, para que parezca instrumento y no arcoiris.
TREBLE_LIGHT = ("#3a5199", "#2f7f96", "#5d8a3e", "#b5762a", "#a83a34")
# BASS va por grosor de trazo, que tambien es ordinal y no gasta color
BASS_W = (1.1, 1.45, 1.85, 2.3, 2.8)
BASS_A = (0.55, 0.68, 0.82, 0.92, 1.0)

PAL_LIGHT = dict(bg="#ffffff", ink="#14181f", muted="#5a626f",
                 grid="#ccd2dc", minor="#e8ebf0", frame="#8d95a3")


# --------------------------------------------------------------------- datos
def collect(workdir: Path) -> dict:
    b = Bench(workdir, sweep=SWEEP, dummy_load=True)
    print(f"simulando {len(POS)**2} combinaciones ({SWEEP}, carga 7.5 ohm)...")
    curves, f = {}, None
    for bs in POS:
        for tr in POS:
            s = b.ac(bass=bs, treble=tr)
            if f is None:
                f = s.f
            elif not np.array_equal(f, s.f):
                raise AssertionError("los barridos no comparten el eje de f")
            curves[f"{bs:g}|{tr:g}"] = np.round(db(s.amp), 3).tolist()
    ref = b.ac(bass=0.5, treble=0.5)
    _, _, fp, dp = ref.corners(ref.amp)
    y = db(ref.amp)
    k1k = int(np.argmin(np.abs(f - 1000)))
    thr, kp = y[k1k] - 3.0, int(np.argmax(y))
    f_hi3 = next((float(np.interp(thr, [y[j + 1], y[j]], [f[j + 1], f[j]]))
                  for j in range(kp, len(y) - 1) if y[j + 1] < thr), None)
    f_lo3 = next((float(np.interp(thr, [y[j - 1], y[j]], [f[j - 1], f[j]]))
                  for j in range(k1k, 0, -1) if y[j - 1] < thr), None)
    return {
        "f": np.round(f, 4).tolist(),
        "pos": list(POS),
        "curves": curves,
        "meta": {
            "sweep": SWEEP,
            "peak_db": round(dp, 2), "peak_hz": round(fp, 0),
            "db_1k": round(float(y[k1k]), 2),
            "f_hi_3db": None if f_hi3 is None else round(f_hi3, 0),
            "f_lo_3db": None if f_lo3 is None else round(f_lo3, 1),
        },
    }


# ----------------------------------------------------------------------- SVG
class Ax:
    """Ejes log-x / lineal-y."""

    def __init__(self, x0, y0, w, h):
        self.x0, self.y0, self.w, self.h = x0, y0, w, h
        self.lf0, self.lf1 = math.log10(F_LO), math.log10(F_HI)
        self.d0, self.d1 = DB_LO, DB_HI

    def x(self, f):
        return self.x0 + self.w * (math.log10(f) - self.lf0) / (self.lf1 - self.lf0)

    def y(self, d):
        return self.y0 + self.h * (1 - (d - self.d0) / (self.d1 - self.d0))

    def path(self, f, ydb):
        """Polilinea recortada a la ventana, con un punto por pixel escaso."""
        pts, last = [], -9e9
        for fi, di in zip(f, ydb):
            if fi < F_LO * 0.9 or fi > F_HI * 1.1:
                continue
            px = self.x(fi)
            if px - last < 0.6 and pts:
                continue
            last = px
            yy = self.y(max(min(di, self.d1 + 5), self.d0 - 5))
            pts.append(f"{px:.1f},{yy:.1f}")
        return "M" + "L".join(pts)


def fmt_hz(f):
    if f >= 1e6:
        return f"{f/1e6:g}M"
    return f"{f/1000:g}k" if f >= 1000 else f"{f:g}"


def ticks(ax):
    out = []
    d = int(math.floor(ax.lf0))
    while d <= math.ceil(ax.lf1):
        for m in range(1, 10):
            f = m * 10.0 ** d
            if 10 ** ax.lf0 - 1e-9 <= f <= 10 ** ax.lf1 + 1e-9:
                out.append((ax.x(f), fmt_hz(f) if m == 1 else None))
        d += 1
    return out


def grid(ax, pal):
    g = []
    for x, lab in ticks(ax):
        g.append(f'<line x1="{x:.1f}" y1="{ax.y0}" x2="{x:.1f}" y2="{ax.y0+ax.h}" '
                 f'stroke="{pal["grid"] if lab else pal["minor"]}" stroke-width="1"/>')
        # marca exterior, como en un instrumento
        g.append(f'<line x1="{x:.1f}" y1="{ax.y0+ax.h}" x2="{x:.1f}" '
                 f'y2="{ax.y0+ax.h+(6 if lab else 3)}" stroke="{pal["frame"]}" '
                 f'stroke-width="1"/>')
        if lab:
            g.append(f'<text x="{x:.1f}" y="{ax.y0+ax.h+24}" class="tick" '
                     f'text-anchor="middle">{lab}</text>')
    for dv in range(int(ax.d0), int(ax.d1) + 1, 5):
        y, major = ax.y(dv), dv % 10 == 0
        g.append(f'<line x1="{ax.x0}" y1="{y:.1f}" x2="{ax.x0+ax.w}" y2="{y:.1f}" '
                 f'stroke="{pal["grid"] if major else pal["minor"]}" '
                 f'stroke-width="1"/>')
        g.append(f'<line x1="{ax.x0-(6 if major else 3)}" y1="{y:.1f}" '
                 f'x2="{ax.x0}" y2="{y:.1f}" stroke="{pal["frame"]}" '
                 f'stroke-width="1"/>')
        if major:
            g.append(f'<text x="{ax.x0-12}" y="{y+4:.1f}" class="tick" '
                     f'text-anchor="end">{dv:+d}</text>')
    return "".join(g)


def legend(ax, pal, colors):
    """Recuadro dentro del grafico, abajo a la izquierda.

    Va ahi y no arriba porque con la ventana hasta 1 MHz la esquina superior
    izquierda ya no esta libre: la curva bass=0 / treble=100 % sube hasta
    +34.9 dB por debajo de los 750 Hz y el recuadro la tapaba.  Relleno opaco,
    para que no atenue nada si algun dia vuelve a solaparse.
    """
    w, h = 392, 70
    x, y = ax.x0 + 16, ax.y0 + ax.h - 16 - h
    g = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{pal["bg"]}" '
         f'stroke="{pal["grid"]}"/>']
    for r, (kind, label) in enumerate((("t", "TREBLE"), ("b", "BASS"))):
        ry = y + 25 + r * 28
        g.append(f'<text x="{x+12}" y="{ry+4}" class="lgl">{label}</text>')
        for i, v in enumerate(POS):
            cx = x + 86 + i * 60
            if kind == "t":
                g.append(f'<line x1="{cx}" y1="{ry}" x2="{cx+18}" y2="{ry}" '
                         f'stroke="{colors[i]}" stroke-width="2.6"/>')
            else:
                g.append(f'<line x1="{cx}" y1="{ry}" x2="{cx+18}" y2="{ry}" '
                         f'stroke="{pal["ink"]}" stroke-width="{BASS_W[i]}" '
                         f'stroke-opacity="{BASS_A[i]}"/>')
            g.append(f'<text x="{cx+23}" y="{ry+4}" class="lgv">'
                     f'{v*100:.0f}%</text>')
    return "".join(g)


def build_svg(data, pal, colors, width=1240):
    M = data["meta"]
    ax = Ax(110, 60, width - 110 - 42, 566)
    height = 700
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
         f'width="100%" style="display:block;width:100%;height:auto" role="img" '
         f'aria-label="Small-signal frequency response of a 40 W guitar amplifier '
         f'for 25 combinations of bass and treble control position">']
    s.append(f'''<style>
    .cond{{font:400 12.5px "IBM Plex Mono",ui-monospace,monospace;fill:{pal['muted']};letter-spacing:.06em}}
    .tick{{font:400 14px "IBM Plex Mono",ui-monospace,monospace;fill:{pal['muted']};font-variant-numeric:tabular-nums}}
    .axl{{font:500 13px "IBM Plex Mono",ui-monospace,monospace;fill:{pal['ink']};letter-spacing:.12em}}
    .lgl{{font:500 12px "IBM Plex Mono",ui-monospace,monospace;fill:{pal['muted']};letter-spacing:.1em}}
    .lgv{{font:400 12.5px "IBM Plex Mono",ui-monospace,monospace;fill:{pal['ink']};font-variant-numeric:tabular-nums}}
    </style>''')

    # ---- cabecera
    s.append(f'<text x="110" y="32" class="cond">DRIVE 0% &#183; VOLUME 100% '
             f'&#183; RAIL 48.88 V &#183; TNOM 27 &#176;C &#183; '
             f'{M["sweep"].replace(".ac ", "").upper()} &#183; '
             f'LTSPICE 17.2.4 BATCH</text>')

    # ---- grafico
    s.append(grid(ax, pal))
    out = []
    for i, bs in enumerate(POS):
        for j, tr in enumerate(POS):
            k = f"{bs:g}|{tr:g}"
            out.append(
                f'<path d="{ax.path(data["f"], data["curves"][k])}" fill="none" '
                f'stroke="{colors[j]}" stroke-width="{BASS_W[i]}" '
                f'stroke-opacity="{BASS_A[i]}" stroke-linejoin="round" '
                f'stroke-linecap="round" class="c" data-k="{k}" '
                f'data-b="{bs:g}" data-t="{tr:g}"/>')
    s.append("".join(out))
    s.append(f'<rect x="{ax.x0}" y="{ax.y0}" width="{ax.w}" height="{ax.h}" '
             f'fill="none" stroke="{pal["frame"]}"/>')
    s.append(legend(ax, pal, colors))
    # rotulos de eje a la manera de una hoja de caracteristicas: el de ganancia
    # girado a la izquierda, el de frecuencia centrado debajo
    cy = ax.y0 + ax.h / 2
    s.append(f'<text x="44" y="{cy:.0f}" class="axl" text-anchor="middle" '
             f'transform="rotate(-90 44 {cy:.0f})">GAIN (dB)</text>')
    s.append(f'<text x="{ax.x0+ax.w/2:.0f}" y="{ax.y0+ax.h+48}" class="axl" '
             f'text-anchor="middle">FREQUENCY (Hz)</text>')

    s.append("</svg>")
    return "".join(s), {
        "x0": ax.x0, "y0": ax.y0, "w": ax.w, "h": ax.h,
        "f_lo": F_LO, "f_hi": F_HI, "d_lo": DB_LO, "d_hi": DB_HI,
        "vw": width, "vh": height,
    }


# ------------------------------------------------------------------- PNG
CHROME = os.environ.get(
    "CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def rasterize(svg: str, png: Path, w: int, h: int, scale: float = 2.5) -> Path:
    """SVG -> PNG con Chrome headless.

    Va por Chrome porque es lo unico que hay en este equipo capaz de rasterizar
    SVG (no hay rsvg-convert, ni cairosvg, ni PIL), y porque asi las IBM Plex
    salen de Google Fonts aunque no esten instaladas en el sistema.  Sin red y
    sin las fuentes locales, el texto cae al sans/mono del sistema y la figura
    sigue siendo valida, solo cambia la tipografia.
    """
    if not Path(CHROME).exists():
        raise RuntimeError(f"no encuentro Chrome en {CHROME} "
                           "(exporta CHROME=/ruta/al/binario)")
    wrapper = png.with_suffix(".render.html")
    wrapper.write_text(
        '<!doctype html><html><head><meta charset="utf-8">'
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
        'family=IBM+Plex+Sans:wght@400;500;600&'
        'family=IBM+Plex+Sans+Condensed:wght@500;600&'
        'family=IBM+Plex+Mono:wght@400;500;600&display=block">'
        '<style>html,body{margin:0;padding:0;background:#fff}'
        f'#w{{width:{w}px}}</style></head><body><div id="w">{svg}</div>'
        '</body></html>', encoding="utf-8")
    subprocess.run(
        [CHROME, "--headless", "--disable-gpu", "--hide-scrollbars",
         f"--force-device-scale-factor={scale}",
         f"--window-size={w},{h}", "--virtual-time-budget=6000",
         f"--screenshot={png}", wrapper.resolve().as_uri()],
        capture_output=True, timeout=180)
    wrapper.unlink(missing_ok=True)
    if not png.exists():
        raise RuntimeError(f"Chrome no genero {png}")
    return png


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-o", "--out", default=str(Path.cwd()),
                    help="directorio de salida (por defecto: el actual)")
    ap.add_argument("--workdir", help="donde dejar netlists y raws")
    ap.add_argument("--no-png", action="store_true",
                    help="no rasterizar, solo el SVG")
    ap.add_argument("--scale", type=float, default=2.5,
                    help="factor de escala del PNG (2.5 -> 3100 px de ancho)")
    a = ap.parse_args()

    from verify_tone_ac import NET
    if not NET.exists():
        sys.exit(f"no encuentro {NET}\n"
                 "no esta versionado: exportalo desde la GUI de LTspice "
                 "(File > Export Netlist)")

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    data = collect(Path(a.workdir) if a.workdir else out / "_sim")

    (out / "tone_ac.json").write_text(json.dumps(data), encoding="utf-8")
    svg, geom = build_svg(data, PAL_LIGHT, TREBLE_LIGHT)
    (out / "tone_ac.svg").write_text(svg, encoding="utf-8")
    M = data["meta"]
    print(f"  pico {M['peak_db']:+.2f} dB a {M['peak_hz']:.0f} Hz, "
          f"{M['db_1k']:+.2f} dB a 1 kHz, -3 dB a {M['f_hi_3db']/1000:.0f} kHz")
    print(f"  -> {out/'tone_ac.svg'}")
    print(f"  -> {out/'tone_ac.json'}")
    if not a.no_png:
        png = rasterize(svg, out / "tone_ac.png",
                        geom["vw"], geom["vh"], a.scale)
        print(f"  -> {png}  ({geom['vw']*a.scale:.0f} x "
              f"{geom['vh']*a.scale:.0f} px)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
