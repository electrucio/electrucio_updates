#!/usr/bin/env python3
"""Dibujar un .asc de LTspice en SVG, sin abrir la GUI.

Sirve para revisar la DISPOSICION de un esquematico (que no se solapen bloques,
que el flujo se lea de izquierda a derecha) sin tener que abrir LTspice y hacer
una captura a mano.  No pretende ser fiel al pixel: pinta los primitivos de los
.asy (LINE / RECTANGLE / CIRCLE / ARC), los hilos, las etiquetas y los textos.

    python3 tools/ltspice/asc2svg.py esquema.asc -o esquema.svg
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

from asc2net import ROT, parse_asc

LIBSYM = Path.home() / "Library/Application Support/LTspice/lib/sym"


def read_text(path: Path) -> str:
    blob = path.read_bytes()
    if blob[:2] == b"\xff\xfe" or blob.count(b"\x00") > len(blob) // 4:
        return blob.decode("utf-16-le", "replace").lstrip("﻿")
    return blob.decode("utf-8", "replace")


def load_shape(name: str, local: Path):
    """Primitivos, pines y anclajes de texto (WINDOW) de un .asy."""
    rel = name.replace("\\", "/") + ".asy"
    for d in (local, LIBSYM):
        p = d / rel
        if p.exists():
            break
    else:
        return [], [], {}
    prims, pins, win = [], [], {}
    for line in read_text(p).splitlines():
        t = line.split()
        if not t:
            continue
        k = t[0].upper()
        try:
            if k == "LINE":
                prims.append(("line", [int(v) for v in t[2:6]]))
            elif k == "RECTANGLE":
                prims.append(("rect", [int(v) for v in t[2:6]]))
            elif k == "CIRCLE":
                prims.append(("circ", [int(v) for v in t[2:6]]))
            elif k == "ARC":
                prims.append(("arc", [int(v) for v in t[2:6]]))
            elif k == "PIN":
                pins.append((int(t[1]), int(t[2])))
            elif k == "WINDOW":
                win[int(t[1])] = (int(t[2]), int(t[3]))
        except ValueError:
            pass
    return prims, pins, win


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def render(path: Path) -> str:
    wires, flags, insts, _ = parse_asc(path)
    local = path.parent
    out, xs, ys = [], [], []

    def note(x, y):
        xs.append(x)
        ys.append(y)

    # ---- hilos
    for x1, y1, x2, y2 in wires:
        out.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                   f'stroke="#0a0" stroke-width="2"/>')
        note(x1, y1)
        note(x2, y2)

    # ---- simbolos
    for it in insts:
        prims, pins, win = load_shape(it["sym"], local)
        rot = ROT[it["rot"]]
        ox, oy = it["x"], it["y"]

        def tr(x, y):
            rx, ry = rot(x, y)
            return ox + rx, oy + ry

        for kind, v in prims:
            if kind == "line":
                a = tr(v[0], v[1])
                b = tr(v[2], v[3])
                out.append(f'<line x1="{a[0]}" y1="{a[1]}" x2="{b[0]}" y2="{b[1]}" '
                           f'stroke="#0a0" stroke-width="2"/>')
                note(*a)
                note(*b)
            elif kind in ("rect", "circ", "arc"):
                a = tr(v[0], v[1])
                b = tr(v[2], v[3])
                x0, y0 = min(a[0], b[0]), min(a[1], b[1])
                w, h = abs(a[0] - b[0]), abs(a[1] - b[1])
                if kind == "rect":
                    out.append(f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" '
                               f'fill="none" stroke="#0a0" stroke-width="2"/>')
                else:
                    out.append(f'<ellipse cx="{x0 + w / 2}" cy="{y0 + h / 2}" '
                               f'rx="{max(w / 2, 1)}" ry="{max(h / 2, 1)}" '
                               f'fill="none" stroke="#0a0" stroke-width="2"/>')
                note(x0, y0)
                note(x0 + w, y0 + h)
        for px, py in pins:
            a = tr(px, py)
            out.append(f'<circle cx="{a[0]}" cy="{a[1]}" r="3" fill="#0a0"/>')
        name = it["name"] or ""
        val = it["value"] or ""
        nx, ny = tr(*win[0]) if 0 in win else (ox + 24, oy - 6)
        out.append(f'<text x="{nx}" y="{ny}" font-size="16" '
                   f'fill="#00d" font-family="monospace">{esc(name)}</text>')
        note(nx + 9 * len(name), ny)
        if val:
            vx, vy = tr(*win[3]) if 3 in win else (ox + 24, oy + 116)
            out.append(f'<text x="{vx}" y="{vy}" font-size="14" '
                       f'fill="#666" font-family="monospace">{esc(val)}</text>')
            note(vx + 8 * len(val), vy)

    # ---- etiquetas de red
    for x, y, name in flags:
        if name == "0":
            out.append(f'<path d="M{x - 12},{y} L{x + 12},{y} M{x - 7},{y + 6} '
                       f'L{x + 7},{y + 6} M{x - 2},{y + 12} L{x + 2},{y + 12}" '
                       f'stroke="#000" stroke-width="2" fill="none"/>')
        else:
            out.append(f'<text x="{x + 5}" y="{y - 4}" font-size="15" '
                       f'fill="#a00" font-family="monospace">{esc(name)}</text>')
            out.append(f'<circle cx="{x}" cy="{y}" r="3" fill="#a00"/>')
        note(x, y)

    # ---- primitivos dibujados en la propia hoja (marcos, nucleos)
    for raw in read_text(path).splitlines():
        t = raw.split()
        if not t:
            continue
        if t[0] == "LINE":
            x1, y1, x2, y2 = (int(v) for v in t[2:6])
            out.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
                       f'stroke="#000" stroke-width="2"/>')
            note(x1, y1)
            note(x2, y2)
        elif t[0] == "RECTANGLE":
            x1, y1, x2, y2 = (int(v) for v in t[2:6])
            out.append(f'<rect x="{min(x1, x2)}" y="{min(y1, y2)}" '
                       f'width="{abs(x2 - x1)}" height="{abs(y2 - y1)}" fill="none" '
                       f'stroke="#999" stroke-width="2" stroke-dasharray="8 6"/>')
            note(x1, y1)
            note(x2, y2)

    # ---- textos (comentarios y directivas)
    for raw in read_text(path).splitlines():
        if not raw.startswith("TEXT"):
            continue
        t = raw.split(None, 5)
        x, y = int(t[1]), int(t[2])
        body = t[5] if len(t) > 5 else ""
        col = "#008" if body.startswith("!") else "#444"
        for i, ln in enumerate(body[1:].split("\\n")):
            out.append(f'<text x="{x}" y="{y + i * 18}" font-size="15" '
                       f'fill="{col}" font-family="monospace">{esc(ln)}</text>')
            note(x + 9 * len(ln), y + i * 18)
        note(x, y)

    pad = 80
    x0, y0 = min(xs) - pad, min(ys) - pad
    w, h = max(xs) - x0 + pad, max(ys) - y0 + pad
    # lienzo cuadrado: los visores que generan miniaturas cuadradas (qlmanage)
    # recortan el lado largo en vez de encajarlo
    side = max(w, h)
    x0 -= (side - w) // 2
    y0 -= (side - h) // 2
    w = h = side
    head = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0} {y0} {w} {h}" '
            f'width="{w}" height="{h}"><rect x="{x0}" y="{y0}" width="{w}" '
            f'height="{h}" fill="#fff"/>')
    return head + "\n".join(out) + "</svg>"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("asc")
    ap.add_argument("-o", "--output", default=None)
    a = ap.parse_args()
    svg = render(Path(a.asc))
    dest = Path(a.output or Path(a.asc).with_suffix(".svg"))
    dest.write_text(svg, encoding="utf-8")
    print(f"escrito {dest}")


if __name__ == "__main__":
    main()
