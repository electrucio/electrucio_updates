#!/usr/bin/env python3
"""Primitivos para dibujar graficas en SVG, sin dependencias.

Existe porque en este equipo no hay matplotlib, ni cairosvg, ni PIL: la unica
forma de sacar una figura es escribir el SVG a mano y rasterizarlo con Chrome.
Lo usan plot_tone_ac.py (ejes log-log) y verify_amp_tran.py (ejes lineales, en
el dominio del tiempo).

    ax = Ax(110, 60, 1088, 566, (10, 1e6), (-30, 45), xlog=True)
    svg = grid(ax, PAL, decade_ticks(ax))
    svg += f'<path d="{ax.path(f, db)}" fill="none" stroke="#333"/>'
    rasterize(svg_completo, Path("fig.png"), 1240, 700)

El estilo (clases CSS `tick`, `axl`, ...) lo pone quien llama: aqui solo se
generan las geometrias.
"""
from __future__ import annotations

import math
import os
import subprocess
from pathlib import Path

CHROME = os.environ.get(
    "CHROME", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


class Ax:
    """Un sistema de ejes: X lineal o logaritmico, Y siempre lineal."""

    def __init__(self, x0, y0, w, h, xlim, ylim, xlog=False):
        self.x0, self.y0, self.w, self.h = x0, y0, w, h
        self.xlog = xlog
        self.a0, self.a1 = ((math.log10(xlim[0]), math.log10(xlim[1]))
                            if xlog else (xlim[0], xlim[1]))
        self.d0, self.d1 = ylim

    def x(self, v):
        u = math.log10(v) if self.xlog else v
        return self.x0 + self.w * (u - self.a0) / (self.a1 - self.a0)

    def y(self, d):
        return self.y0 + self.h * (1 - (d - self.d0) / (self.d1 - self.d0))

    @property
    def xmin(self):
        return 10 ** self.a0 if self.xlog else self.a0

    @property
    def xmax(self):
        return 10 ** self.a1 if self.xlog else self.a1

    def path(self, xs, ys):
        """Polilinea recortada a la ventana, con un punto por pixel escaso.

        El recorte en Y es un CLAMP con margen, no un descarte: si se tirasen
        los puntos que se salen, la curva entraria y saldria del marco por
        sitios equivocados.
        """
        lo, hi = self.xmin * 0.9, self.xmax * 1.1
        pts, last = [], -9e9
        for xv, yv in zip(xs, ys):
            if xv < lo or xv > hi:
                continue
            px = self.x(xv)
            if px - last < 0.6 and pts:
                continue
            last = px
            py = self.y(max(min(yv, self.d1 + 5), self.d0 - 5))
            pts.append(f"{px:.1f},{py:.1f}")
        return "M" + "L".join(pts)


def fmt_hz(f):
    if f >= 1e6:
        return f"{f/1e6:g}M"
    return f"{f/1000:g}k" if f >= 1000 else f"{f:g}"


def decade_ticks(ax, fmt=fmt_hz):
    """(x, etiqueta o None) de las marcas de un eje logaritmico."""
    out = []
    d = int(math.floor(ax.a0))
    while d <= math.ceil(ax.a1):
        for m in range(1, 10):
            v = m * 10.0 ** d
            if 10 ** ax.a0 - 1e-9 <= v <= 10 ** ax.a1 + 1e-9:
                out.append((ax.x(v), fmt(v) if m == 1 else None))
        d += 1
    return out


def linear_ticks(ax, major, minor=None, fmt=lambda v: f"{v:g}"):
    """Idem para un eje lineal: etiqueta cada `major`, marca fina cada `minor`."""
    step = minor or major
    out, k = [], math.ceil(ax.a0 / step - 1e-9)
    while k * step <= ax.a1 + 1e-9:
        v = k * step
        r = v / major
        out.append((ax.x(v), fmt(v) if abs(r - round(r)) < 1e-9 else None))
        k += 1
    return out


def grid(ax, pal, xticks, ystep=5, ymajor=10, yfmt=lambda v: f"{v:+g}"):
    """Rejilla, marcas exteriores y etiquetas de los dos ejes.

    Las marcas salen HACIA FUERA del marco, como en un instrumento: 6 px las
    mayores, 3 px las finas.
    """
    g = []
    for x, lab in xticks:
        g.append(f'<line x1="{x:.1f}" y1="{ax.y0}" x2="{x:.1f}" y2="{ax.y0+ax.h}" '
                 f'stroke="{pal["grid"] if lab else pal["minor"]}" stroke-width="1"/>')
        g.append(f'<line x1="{x:.1f}" y1="{ax.y0+ax.h}" x2="{x:.1f}" '
                 f'y2="{ax.y0+ax.h+(6 if lab else 3)}" stroke="{pal["frame"]}" '
                 f'stroke-width="1"/>')
        if lab:
            g.append(f'<text x="{x:.1f}" y="{ax.y0+ax.h+24}" class="tick" '
                     f'text-anchor="middle">{lab}</text>')
    for dv in range(int(ax.d0), int(ax.d1) + 1, ystep):
        y, major = ax.y(dv), dv % ymajor == 0
        g.append(f'<line x1="{ax.x0}" y1="{y:.1f}" x2="{ax.x0+ax.w}" y2="{y:.1f}" '
                 f'stroke="{pal["grid"] if major else pal["minor"]}" '
                 f'stroke-width="1"/>')
        g.append(f'<line x1="{ax.x0-(6 if major else 3)}" y1="{y:.1f}" '
                 f'x2="{ax.x0}" y2="{y:.1f}" stroke="{pal["frame"]}" '
                 f'stroke-width="1"/>')
        if major:
            g.append(f'<text x="{ax.x0-12}" y="{y+4:.1f}" class="tick" '
                     f'text-anchor="end">{yfmt(dv)}</text>')
    return "".join(g)


def frame(ax, pal):
    return (f'<rect x="{ax.x0}" y="{ax.y0}" width="{ax.w}" height="{ax.h}" '
            f'fill="none" stroke="{pal["frame"]}"/>')


def rasterize(svg: str, png: Path, w: int, h: int, scale: float = 2.5) -> Path:
    """SVG -> PNG con Chrome headless.

    Va por Chrome porque es lo unico que hay en este equipo capaz de rasterizar
    SVG, y porque asi las IBM Plex salen de Google Fonts aunque no esten
    instaladas.  Sin red y sin las fuentes locales, el texto cae al sans/mono
    del sistema y la figura sigue siendo valida, solo cambia la tipografia.
    """
    png = Path(png)
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
