#!/usr/bin/env python3
"""Barrido del filtro CRC del deposito: cuanto rechazo compra y a que precio.

Al bajar Cadj de 10 uF a 1 uF se perdieron 11,3 dB de rechazo.  El CRC los
compra otra vez, pero en el RAIL en vez de en el lazo, asi que no cuesta
velocidad.  Lo que si cuesta es margen de dropout (I*R) y calor.

El reparto entre R y C2 es una eleccion libre para un mismo polo: poca R y mucha
C cuesta dinero y volumen; mucha R y poca C cuesta voltios y vatios.  Esto mide
las dos caras a la vez, porque la aritmetica de un polo RC no sabe tres cosas:

  - si el rechazo del regulador COMPONE con la atenuacion del filtro (el 1 ohm
    tambien sube la impedancia de fuente que ve la entrada, lo cual suele
    AYUDAR, asi que puede salir mejor de lo calculado);
  - que le hace de verdad a la caida del rail y por tanto al margen de dropout;
  - si mueve los picos del puente, que ya estan en 5,33 A con 1 A de continua.

    python3 tools/ltspice/barrido_crc.py
"""
from __future__ import annotations

import sys
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from verify_psu_cvcc import Bench, R1_TOTAL, R2_COARSE, R2_FINE   # noqa: E402

R_DEF, C_DEF = "1", "10000u"           # deben seguir a mkasc_psu_cvcc.py

# (R, C2) -> el polo es 1/(2*pi*R*C).  Incluye el caso SIN filtro como linea
# base, puenteando la resistencia con un valor despreciable.
COMBOS = [
    ("0.001", "22000u", "todo en un bloque"),
    ("0.22",  "22000u", "polo 33 Hz"),
    ("0.47",  "10000u", "polo 34 Hz"),
    ("0.47",  "22000u", "polo 15 Hz"),
    ("1",     "10000u", "polo 16 Hz"),
    ("1",     "22000u", "polo 7 Hz"),
]


def vs_de(volts):
    r2 = volts / (1.25 / R1_TOTAL + 50e-6)
    return min(r2 / (R2_COARSE + R2_FINE), 1.0)


V20 = vs_de(20.0)


def main():
    # Ruta fija y limpieza al salir, como verify_psu_cvcc.py: los .raw de
    # cada corrida son cientos de MB.
    wd = Path("/tmp/psu_cvcc_crc")
    b = Bench(wd)
    try:
        _barrido(b)
    finally:
        shutil.rmtree(wd, ignore_errors=True)


def _barrido(b):
    print("== BARRIDO DEL FILTRO CRC: rechazo contra margen y calor ==")
    print("   TAP=2, 20 V de consigna, 22 ohm de carga (~0,92 A).\n")
    print(f"   {'R':>6}{'C2':>8}{'':>20}{'rizado':>9}{'rechazo':>9}"
          f"{'atenua':>9}{'caida':>8}{'P(R)':>8}{'margen':>9}{'pico D':>8}")

    for r, c, nota in COMBOS:
        pat = [(f"Rcrc VRAW1 VRAW {R_DEF}", f"Rcrc VRAW1 VRAW {r}"),
               (f"Cbulk2 VRAW 0 {C_DEF}", f"Cbulk2 VRAW 0 {c}")]
        _, _, q = b.run(f"crc_{r}_{c}", tap=2, vset=V20, iset=1.0, load=22,
                        step="20u", patches=pat)
        print(f"   {r:>6}{c:>8}{nota:>20}"
              f"{q['vout_pp']*1e3:8.2f}mV"
              f"{q.get('rechazo_db', 0):8.1f}dB"
              f"{q.get('atenua_db', 0):8.1f}dB"
              f"{q.get('vcrc_dc', 0):7.2f}V"
              f"{q.get('p_rcrc', 0):7.2f}W"
              f"{q['headroom']:8.2f}V"
              f"{q.get('ipk_diodo', 0):7.2f}A")

    print("\n   La primera fila NO es la linea base del diseño: con la R")
    print("   puenteada son los 32.000 uF juntos, o sea 3,2x la capacidad")
    print("   original.  La base real (10.000 uF solos) da 1,98 mV, asi que")
    print("   triplicar capacidad compra 3,2x y la resistencia otro 2,6x mas.")
    print("\n   'atenua' es lo que quita el propio filtro (VRAW1 p-p contra")
    print("   VRAW p-p); 'rechazo' es lo que anade el regulador encima.")
    print("   'margen' tiene que quedarse por encima de 3 V: es la regla del")
    print("   diseño (2 V de dropout del chip + 1 V para el valle del rizado).")
    print("   A 1,34 A la caida y la potencia escalan x1,46 sobre estas cifras.")


if __name__ == "__main__":
    main()
