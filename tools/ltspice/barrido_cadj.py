#!/usr/bin/env python3
"""Barrido de Cadj en psu_cvcc: rizado contra velocidad de recuperacion.

Cadj es la unica pieza del diseño elegida copiando un valor de una figura del
datasheet (la 21 de TI, para el rechazo de rizado) sin comprobar lo que cuesta.
Y cuesta: el LM317HV solo saca ~50 uA por el pin ADJ, asi que toda SUBIDA de la
salida depende de cargar ese condensador a traves de R1.  Silicon Chip, con el
mismo chip y la misma topologia, pone 100 nF y lo razona explicitamente: «its
output can only rise by 1V per millisecond».  Nosotros ponemos 10 uF.

Esto mide los dos lados del compromiso de una vez, para poder decidir con datos:

    python3 tools/ltspice/barrido_cadj.py

El criterio de establecimiento son +-10 mV del valor final, que es EL MISMO que
usa Keysight en el E3610A («output recovery to within 10 mV»), para que la
comparacion con las comerciales sea directa y no de manga ancha.
"""
from __future__ import annotations

import sys
import shutil
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

from verify_psu_cvcc import Bench, R1_TOTAL, R2_COARSE, R2_FINE   # noqa: E402

CADJ_DEFECTO = "1u"                # debe seguir a mkasc_psu_cvcc.py
VALORES = ["10u", "3.3u", "1u", "470n", "100n"]
BANDA = 10e-3                      # +-10 mV, el criterio de Keysight


def borne(d):
    return d["V(vout)"] - d["V(vrtn)"]


def vs_de(volts):
    r2 = volts / (1.25 / R1_TOTAL + 50e-6)
    return min(r2 / (R2_COARSE + R2_FINE), 1.0)


V20 = vs_de(20.0)


def establece(d, t0, t1, banda=BANDA):
    """(desviacion de pico, tiempo hasta entrar en banda) tras el flanco en t0."""
    t, v = d["time"], borne(d)
    fin = v[(t > t1 - 0.02) & (t < t1 - 0.001)]
    if fin.size == 0:
        return float("nan"), float("nan")
    vf = float(np.median(fin))
    tr = (t >= t0) & (t < t1)
    vt, tt = v[tr], t[tr]
    pico = float(vt[np.argmax(np.abs(vt - vf))]) - vf
    fuera = np.where(np.abs(vt - vf) > banda)[0]
    return pico, (tt[fuera[-1]] - t0) if fuera.size else 0.0


def main():
    # Ruta fija y limpieza al salir, como verify_psu_cvcc.py: los .raw de
    # cada corrida son cientos de MB.
    wd = Path("/tmp/psu_cvcc_cadj")
    b = Bench(wd)
    try:
        _barrido(b)
    finally:
        shutil.rmtree(wd, ignore_errors=True)


def _barrido(b):
    print("== BARRIDO DE Cadj: lo que cuesta el rechazo de rizado ==")
    print("   TAP=2, 20 V de consigna.  Establecimiento a +-10 mV del valor")
    print("   final, el mismo criterio que el E3610A de Keysight.\n")
    print(f"   {'Cadj':>6}{'rizado':>10}{'rechazo':>10}"
          f"{'escalon de carga':>22}{'subida 0,5->20 V':>20}")
    print(f"   {'':>6}{'(1 A)':>10}{'':>10}"
          f"{'caida':>11}{'a +-10mV':>11}{'a +-10mV':>20}")

    filas = []
    for c in VALORES:
        pat = [(f"Cadj VADJ VNEG {CADJ_DEFECTO}", f"Cadj VADJ VNEG {c}")]

        # 1) rizado en regimen a 1 A
        _, _, q = b.run(f"r_{c}", tap=2, vset=V20, iset=1.0, load=22,
                        step="20u", patches=pat)
        riz, rech = q["vout_pp"] * 1e3, q.get("rechazo_db", 0)

        # 2) escalon de carga dentro de CV, 100 -> 22 ohm
        pwl = "PWL(0 100 0.5 100 0.500001 22 0.9 22)"
        d, _, _ = b.run(f"e_{c}", tap=2, vset=V20, iset=1.0, load=pwl,
                        tend=0.9, tstart=0.49, step="5u", meas_from=0.85,
                        patches=pat)
        caida, ts_carga = establece(d, 0.5, 0.9)

        # 3) subida de consigna, el caso peor de este condensador
        pats = pat + [(f"Vset VSET 0 {V20}",
                       f"Vset VSET 0 PWL(0 0.012 0.5 0.012 0.500001 {V20})"),
                      (f"Vsetf VSETF 0 {V20}",
                       f"Vsetf VSETF 0 PWL(0 0.012 0.5 0.012 0.500001 {V20})")]
        d, _, _ = b.run(f"s_{c}", tap=2, vset=V20, iset=1.0, load=22,
                        tend=1.2, tstart=0.49, step="20u", meas_from=1.15,
                        patches=pats)
        _, ts_subida = establece(d, 0.5, 1.2)

        filas.append((c, riz, rech, caida * 1e3, ts_carga * 1e3,
                      ts_subida * 1e3))
        print(f"   {c:>6}{riz:9.2f}mV{rech:9.1f}dB"
              f"{caida*1e3:10.0f}mV{ts_carga*1e3:10.1f}ms"
              f"{ts_subida*1e3:19.0f}ms")

    print("\n   Referencias para juzgarlo:")
    print("     - comerciales: <2 mV p-p de rizado y <50 us a +-10 mV")
    print("     - Silicon Chip con 100 nF: <1 ms y <200 mV con un escalon de 4 A")
    print("     - el datasheet pide los 10 uF para 80 dB de rechazo (fig. 21),")
    print("       pero el modelo conductual del LM317HV topa antes: lo que mide")
    print("       esta columna es el modelo, no el chip.")
    base = filas[0]
    print(f"\n   Coste de los 10 uF frente a 100 nF: el rizado empeora "
          f"{filas[-1][1] / base[1]:.1f}x y la subida mejora "
          f"{base[5] / max(filas[-1][5], 1e-9):.0f}x.")


if __name__ == "__main__":
    main()
