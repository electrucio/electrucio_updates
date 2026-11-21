#!/usr/bin/env python3
"""Iguala la sonoridad de los renders, para compararlos sin que mande el volumen.

    python3 tools/ltspice/loudness_match.py

Lee guitar_amplifier/renders/*.wav y escribe las versiones igualadas en
guitar_amplifier/renders/loudness_matched/.  Los originales no se tocan.

**Esto es lo contrario de lo que hacen los renders.**  Alli todos llevan el
MISMO factor, a proposito, para que la diferencia de volumen entre
configuraciones sea real y audible: con los dos diodos puestos el ampli suena
12 dB mas flojo, y eso es parte de lo que hace el recortador.  Aqui se anula
esa diferencia justamente para poder juzgar el TIMBRE sin que la sonoridad
decida por el oido, que es lo que pasa cuando comparas dos cosas y una suena
mas fuerte.  Hacen falta las dos versiones; no son intercambiables.

La medida es la de la norma (ITU-R BS.1770 / EBU R128), no el valor eficaz a
secas: filtro K, bloques de 400 ms solapados al 75 %, puerta absoluta a -70
LUFS y puerta relativa a -10 LU.  El eficaz pelado se deja enganar por el
contenido grave, y aqui las configuraciones difieren justo en el espectro.

El objetivo es -18 LUFS, pero se baja en bloque si con eso algun fichero se
pasara de -1 dBFS de pico: igualar sonoridad no vale de nada si el resultado
recorta en el reproductor.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from render_audio import rd_wav, wr_wav                         # noqa: E402

SRC = ROOT / "guitar_amplifier" / "renders"
DST = SRC / "loudness_matched"
TARGET_LUFS = -18.0
PEAK_CEILING_DB = -1.0

# Filtro K de BS.1770 a 48 kHz: realce de agudos y paso alto.
SHELF_B = np.array([1.53512485958697, -2.69169618940638, 1.19839281085285])
SHELF_A = np.array([1.0, -1.69065929318241, 0.73248077421585])
HPF_B = np.array([1.0, -2.0, 1.0])
HPF_A = np.array([1.0, -1.99004745483398, 0.99007225036621])


def biquad(x, b, a):
    y = np.zeros_like(x)
    x1 = x2 = y1 = y2 = 0.0
    for i, xi in enumerate(x):
        yi = b[0]*xi + b[1]*x1 + b[2]*x2 - a[1]*y1 - a[2]*y2
        y[i] = yi
        x2, x1 = x1, xi
        y2, y1 = y1, yi
    return y


def lufs(x, sr):
    """Sonoridad integrada con puerta, en LUFS.  Mono, G = 1."""
    if sr != 48000:
        raise SystemExit(f"el filtro K de aqui es de 48 kHz y el fichero va a {sr}")
    y = biquad(biquad(x.astype(np.float64), SHELF_B, SHELF_A), HPF_B, HPF_A)
    win, hop = int(0.4 * sr), int(0.1 * sr)
    if len(y) < win:
        raise SystemExit("fichero mas corto que un bloque de 400 ms")
    z = np.array([np.mean(y[i:i+win] ** 2)
                  for i in range(0, len(y) - win + 1, hop)])
    z = np.maximum(z, 1e-20)
    l = -0.691 + 10 * np.log10(z)
    keep = l > -70.0                                   # puerta absoluta
    if not keep.any():
        return float("-inf")
    gamma = -0.691 + 10 * np.log10(z[keep].mean()) - 10.0   # puerta relativa
    keep &= l > gamma
    if not keep.any():
        return float("-inf")
    return float(-0.691 + 10 * np.log10(z[keep].mean()))


def main() -> None:
    files = sorted(SRC.glob("*.wav"))
    if not files:
        raise SystemExit(f"no hay .wav en {SRC}")
    DST.mkdir(parents=True, exist_ok=True)

    rows = []
    for f in files:
        x, sr = rd_wav(f)
        L = lufs(x, sr)
        pk = float(np.abs(x).max())
        rows.append([f, x, sr, L, pk])
        print(f"  {f.name:<22} {L:7.2f} LUFS   pico "
              f"{20*np.log10(max(pk, 1e-12)):6.2f} dBFS", flush=True)

    # un objetivo comun, bajado si al subir alguno se pasara del techo
    target = TARGET_LUFS
    for _, _, _, L, pk in rows:
        if pk <= 0:
            continue
        peak_db = 20 * np.log10(pk) + (target - L)
        if peak_db > PEAK_CEILING_DB:
            target -= peak_db - PEAK_CEILING_DB
    if target != TARGET_LUFS:
        print(f"\nobjetivo bajado de {TARGET_LUFS:.1f} a {target:.2f} LUFS "
              f"para que nada pase de {PEAK_CEILING_DB:.0f} dBFS")

    print(f"\n{'fichero':<22} {'ganancia':>9} {'pico final':>12}")
    for f, x, sr, L, pk in rows:
        g = 10 ** ((target - L) / 20.0)
        y = x * g
        wr_wav(DST / f.name, y, sr, bits=24)
        print(f"  {f.name:<22} {20*np.log10(g):+8.2f} dB "
              f"{20*np.log10(max(np.abs(y).max(), 1e-12)):+8.2f} dBFS")
    print(f"\n{len(rows)} ficheros a {target:.2f} LUFS en\n{DST}")


if __name__ == "__main__":
    main()
