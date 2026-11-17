#!/usr/bin/env python3
"""Lector de ficheros .raw de LTspice (binarios, .tran y .ac).

Formato: cabecera en UTF-16LE hasta el marcador "Binary:\\n", y despues los
datos empaquetados. En .tran el tiempo es float64 y el resto float32,
intercalados por punto temporal. En .ac son pares complejos de 128 bits.

Uso como libreria:
    from rawread import read_raw
    names, d = read_raw("psu.raw")
    t, vout = d["time"], d["V(vload)"]

Uso desde la linea de comandos (lista las variables disponibles):
    python3 rawread.py psu.raw
"""
from __future__ import annotations

import re
import sys

import numpy as np

_MARKER = "Binary:\n".encode("utf-16-le")


def read_raw(path):
    """Devuelve (names, data) con data[name] -> np.ndarray.

    names[0] es la variable independiente ("time" en .tran, "frequency" en .ac).
    """
    blob = open(path, "rb").read()
    i = blob.find(_MARKER)
    if i < 0:
        raise ValueError(f"{path}: no encuentro el marcador 'Binary:' "
                         "(¿es un .raw en ASCII, o se guardo con -ascii?)")
    header = blob[:i].decode("utf-16-le", "replace")
    data = blob[i + len(_MARKER):]

    npoints = int(re.search(r"No\. Points:\s*(\d+)", header).group(1))
    nvars = int(re.search(r"No\. Variables:\s*(\d+)", header).group(1))
    flags = re.search(r"Flags:\s*(.*)", header).group(1).lower()

    names = []
    for line in header.splitlines():
        m = re.match(r"\s*(\d+)\s+(\S+)\s+(\S+)", line)
        if m and len(names) < nvars and m.group(1) == str(len(names)):
            names.append(m.group(2))
    if len(names) != nvars:
        raise ValueError(f"{path}: lei {len(names)} nombres de {nvars} variables")

    if "complex" in flags:                      # .ac
        arr = np.frombuffer(data, dtype=np.complex128, count=npoints * nvars)
        arr = arr.reshape(npoints, nvars)
        return names, {n: arr[:, k] for k, n in enumerate(names)}

    # .tran / .dc: variable independiente float64, resto float32
    dt = np.dtype([("x", "<f8")] + [(f"v{k}", "<f4") for k in range(nvars - 1)])
    rec = np.frombuffer(data, dtype=dt, count=npoints)
    # Con un `tstart` en el .tran, LTspice guarda el tiempo RELATIVO a el y
    # pone el desplazamiento en la cabecera.  Sin sumarlo, un `.tran 0 4.6 3.75`
    # devuelve tiempos de 0 a 0.85 y cualquier medida en tiempo absoluto sale
    # desplazada, en silencio.
    m = re.search(r"Offset:\s*([-\d.eE+]+)", header)
    offset = float(m.group(1)) if m else 0.0
    # LTspice marca los puntos comprimidos poniendo el bit de signo del tiempo
    out = {names[0]: np.abs(rec["x"]) + offset}
    for k in range(nvars - 1):
        out[names[k + 1]] = rec[f"v{k}"].astype(np.float64)
    return names, out


def read_log(path):
    """Devuelve el texto de un .log de LTspice (viene en UTF-16LE)."""
    return open(path, "rb").read().decode("utf-16-le", "replace")


def pp(a):
    """Pico a pico (np.ptp desaparecio del ndarray en numpy 2)."""
    return float(np.ptp(np.asarray(a)))


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 1
    names, d = read_raw(argv[1])
    x = d[names[0]]
    print(f"{len(x)} puntos, {len(names)} variables, "
          f"{names[0]} = {x[0]:.6g} .. {x[-1]:.6g}")
    for n in names[1:]:
        v = d[n]
        print(f"  {n:<22} min={np.min(v):12.5g}  max={np.max(v):12.5g}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
