#!/usr/bin/env python3
"""Suite de verificacion de powersupply/psu_cvcc.

    python3 tools/ltspice/verify_psu_cvcc.py             # todo
    python3 tools/ltspice/verify_psu_cvcc.py --only power
    python3 tools/ltspice/verify_psu_cvcc.py --keep --workdir /tmp/psu2

Casos:
  cv      recorrido del pote de tension y rango util de cada toma
  ripple  rizado y rechazo en funcion del MARGEN DE RAIL (el fallo tipico)
  cc      recorrido del pote de corriente y transicion CV->CC
  short   cortocircuito franco por toma
  power   matriz de escenarios con la disipacion de CADA componente y el peor
          caso de cada uno.  Es lo que evita sorpresas al montarlo.

EL ESQUEMATICO ES LA FUENTE DE VERDAD.  Esta suite netlista `psu_cvcc.asc` en
cada arranque con `asc2net.py`, asi que el netlist no puede desincronizarse.
Ojo: al abrir el .asc en la GUI, LTspice sobrescribe `psu_cvcc.net` con su
propia exportacion; por eso ese fichero esta en .gitignore y no se usa aqui.

Tres trampas que conviene no redescubrir:

1. El netlist lleva `uic` a proposito.  Sin el, el .op no converge (Gmin y
   source stepping fallan, el pseudo-transitorio devuelve NaN y el transitorio
   entero sale NaN).  Lo que lo hace irresoluble es el lazo de CC colgado del
   pin ADJ.
2. Para medir CC hace falta MARGEN DE RAIL.  Si la consigna de tension esta
   por encima de lo que da la toma, el regulador esta en dropout y el lazo de
   corriente ni se activa: se mide la carga, no el limite.
3. El modelo termico tiene una constante de tiempo de 40 s (Cth_sa 20 x
   Rth_sa 2), asi que la Tj al final de un transitorio de 1,5 s NO es la de
   regimen.  El peor caso se calcula analiticamente:
   Tj = Tamb + P * (Rth_js + Rth_sa) = 25 + P * 4,3.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ltrun import Netlist, run_batch                      # noqa: E402
from rawread import read_log, read_raw                    # noqa: E402
from asc2net import build_netlist                         # noqa: E402

REPO = Path(__file__).resolve().parents[2]
PSU = REPO / "powersupply" / "psu_cvcc"
ASC = PSU / "psu_cvcc.asc"

RTH_TOTAL = 2.3 + 2.0          # union -> disipador -> ambiente, C/W
TAMB = 25.0
TJ_MAX = 125.0                 # LM317HV, tabla 7.3 del datasheet

# NO se usa .save: `.meas` solo ve las variables guardadas, asi que un .save
# parcial devuelve 0 en cualquier medida que toque una corriente no listada.
# Con 41 medidas repartidas por todo el circuito sale mas a cuenta guardarlo
# todo y desactivar la compresion de la forma de onda.

MEAS_RE = re.compile(r"^\s*(\w+)\s*[:=].*?=\s*([-\d.eE+]+)")


def iset_teorico(frac, vref=2.5065):
    rp = frac * 4700
    return (vref * rp / (22000 + rp)) / 0.33


class Bench:
    """Netlista el .asc una vez y genera variantes a partir de ahi."""

    def __init__(self, workdir: Path):
        self.w = workdir
        self.w.mkdir(parents=True, exist_ok=True)
        lines, directives, problems = build_netlist(ASC)
        for p in problems:
            print(f"  aviso del esquematico: {p}", file=sys.stderr)
        self.base = ("* generado desde psu_cvcc.asc\n"
                     + "\n".join(lines + directives) + "\n.end\n")
        self.src = self.w / "_base.net"
        self.src.write_text(self.base, encoding="ascii")

    def run(self, tag, tap=2, vset=0.5, iset=1.0, load=100, tend=1.5,
            step="100u", meas_from=1.2, tstart=0, vred=325, patches=(),
            vsetf=None):
        n = Netlist.from_file(self.src).absolutize_libs([PSU])
        n.patch(".param TAP=2", f".param TAP={tap}")
        n.patch("Vset VSET 0 0.5", f"Vset VSET 0 {vset}")
        # el fino sigue al grueso salvo que se pida otra cosa: asi un
        # vset=X solo sigue significando "X de fondo de escala"
        n.patch("Vsetf VSETF 0 0.5",
                f"Vsetf VSETF 0 {vset if vsetf is None else vsetf}")
        n.patch("Visetadj ISETADJ 0 1", f"Visetadj ISETADJ 0 {iset}")
        n.patch("Vload LOAD 0 100", f"Vload LOAD 0 {load}")
        n.patch(".param TM1=1.2 TM2=1.5", f".param TM1={meas_from} TM2={tend}")
        if vred != 325:
            n.patch("V1 LIVE NEUTRAL SINE(0 325 50)",
                    f"V1 LIVE NEUTRAL SINE(0 {vred} 50)")
        for a, b in patches:
            n.patch(a, b)
        n.patch(".tran 0 1.5 0 100u startup uic",
                f".tran 0 {tend} {tstart} {step} startup uic")
        n.add(".options plotwinsize=0")
        net = n.write(self.w / f"{tag}.net")
        raw = run_batch(net)
        d = read_raw(raw)[1]
        m = d["time"] > meas_from
        return d, m, self.measures(net.with_suffix(".log"))

    @staticmethod
    def measures(log: Path) -> dict:
        out = {}
        for line in read_log(log).splitlines():
            mm = MEAS_RE.match(line)
            if mm:
                try:
                    out[mm.group(1).lower()] = float(mm.group(2))
                except ValueError:
                    pass
        return out


# --- escala del divisor (debe seguir a mkasc_psu_cvcc.py) -------------------
R2_COARSE, R2_FINE = 10000, 1000
R2_TOTAL = R2_COARSE + R2_FINE
R1_TOTAL = 340                      # R1 270 + TP1 a 70


# Formula de TI (SNVS773D, ec. 1) con la referencia de -1,25 V abajo:
#
#     Vout = 1,25 * R2/R1  +  Iadj * R2
#
# El termino de Iadj es un error de GANANCIA constante en todo el recorrido,
# porque como fraccion de la lectura vale Iadj*R1/1,25: 1,4 % con R1 = 340
# (eran 0,5 % con R1 = 120).  Deja la salida ALTA, y TP1 lo corrige entero
# subiendo R1.  Lo que queda es su deriva, unos 55 mV sobre 40 V.
IADJ_GANANCIA = 50e-6 * R1_TOTAL / 1.25          # 0,0136 = 1,4 %


def vout_teorico(frac):
    """Vout con la referencia de -1,25 V: 1,25*R2/R1 + Iadj*R2 (formula de TI)."""
    r2 = frac * R2_TOTAL
    return 1.25 * r2 / R1_TOTAL + 50e-6 * r2


# --------------------------------------------------------------------- casos
def case_cv(b: Bench):
    print("== CV: recorrido del pote de tension (TAP=3, carga 100 ohm) ==")
    print(f"  {'pote':>6}{'R2':>8}{'Vout':>9}{'teorico':>10}{'error':>8}")
    for vs in (0.02, 0.1, 0.3, 0.5, 0.7, 1.0):
        d, m, q = b.run(f"cv_{vs}", tap=3, vset=vs)
        v = q.get("vout_dc", float(np.median(d["V(vout)"][m])))
        th = vout_teorico(vs)
        print(f"  {vs*100:5.0f}%{vs*R2_TOTAL:7.0f}R{v:8.2f}V{th:9.2f}V"
              f"{(v-th)/max(th,1)*100:7.1f}%")

    print("\n== Rango util de cada toma (pote al maximo, carga 100 ohm) ==")
    print(f"  {'TAP':>4}{'VRAW+':>9}{'Vout':>9}{'margen':>9}{'rizado':>10}")
    for tap in (1, 2, 3):
        d, m, q = b.run(f"cv_tap{tap}", tap=tap, vset=1.0, step="20u")
        print(f"  {tap:>4}{q['vraw_dc']:8.1f}V{q['vout_dc']:8.2f}V"
              f"{q['headroom']:8.2f}V{q['vout_pp']*1e3:9.1f}mV")


def case_ripple(b: Bench):
    print("== Rizado y rechazo en funcion del margen de rail, en las TRES tomas ==")
    print("   El fallo tipico: el pote llega a 42 V en cualquier posicion del")
    print("   selector, asi que en las tomas bajas es facil pedir mas de lo que")
    print("   dan.  Ahi el regulador entra en dropout y la salida COPIA el rizado.")
    print("   El rizado del rail crece con la CORRIENTE (carga fija de 100 ohm),")
    print("   no con la toma: es I/(2*f*C) y no depende de la tension.")
    limites = {}
    for tap, nombre in ((1, "un devanado"), (2, "dos devanados"), (3, "tres devanados")):
        print(f"\n  --- TAP={tap} ({nombre}) ---")
        print(f"  {'pote':>6}{'pedido':>9}{'Vout':>9}{'margen':>9}"
              f"{'rizado out':>12}{'rizado rail':>12}{'rechazo':>10}")
        maxpote = None
        for vs in (1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.3, 0.15):
            d, m, q = b.run(f"rp{tap}_{vs}", tap=tap, vset=vs, step="20u")
            ped = vout_teorico(vs)
            seco = q["headroom"] < 2.5
            if not seco and maxpote is None:
                maxpote = (vs, q["vout_dc"])
            print(f"  {vs*100:5.0f}%{ped:8.1f}V{q['vout_dc']:8.2f}V"
                  f"{q['headroom']:8.2f}V{q['vout_pp']*1e3:11.1f}mV"
                  f"{q['vraw_pp']*1e3:11.0f}mV{q['rechazo_db']:9.1f}dB"
                  f"{'  <-- DROPOUT' if seco else ''}")
        limites[tap] = maxpote
    print("\n  Pote maximo sin caer en dropout (carga ligera):")
    for tap, mp in limites.items():
        if mp is None:
            print(f"    TAP={tap}: ninguna posicion es segura")
        elif mp[0] >= 1.0:
            print(f"    TAP={tap}: el 100 % -> {mp[1]:.1f} V.  El pote NO puede "
                  f"meterte en dropout en esta toma.")
        else:
            print(f"    TAP={tap}: hasta ~{mp[0]*100:.0f} % -> {mp[1]:.1f} V")


def case_cc(b: Bench):
    print("== CC: recorrido del pote de corriente (TAP=2, pote de tension 90 %) ==")
    print(f"  {'pote':>6}{'Iset':>10}{'Rcarga':>8}{'I shunt':>10}"
          f"{'I carga':>10}{'Vout':>8}{'error':>8}")
    for ia, rl in ((0.05, 220), (0.1, 100), (0.2, 47), (0.4, 22), (0.7, 10), (1.0, 4.7)):
        d, m, q = b.run(f"cc_{ia}", tap=2, vset=0.9, iset=ia, load=rl, tend=2.0,
                        step="200u", meas_from=1.7)
        # El lazo regula la corriente del SHUNT, y por el shunt vuelve tambien el
        # divisor R1/R2 (que ahora acaba en VRTN).  Lo que recibe la carga es la
        # consigna menos I(R2) = (Vout-1,25)/R2, que NO es un offset fijo: son
        # 10,4 mA con el pote de tension a fondo y menos con el regulador
        # replegado en CC.  Siempre limita algo ANTES de la consigna.
        i, il, ith = q["iout_dc"], abs(q["iload_dc"]), iset_teorico(ia)
        print(f"  {ia*100:5.0f}%{ith*1e3:9.1f}m{rl:7}R{i*1e3:9.1f}m{il*1e3:9.1f}m"
              f"{q['vout_dc']:7.2f}V{(il-ith)/ith*100:7.1f}%")

    print("\n== Transicion CV->CC (TAP=2, 21,5 V pedidos, Iset al maximo) ==")
    print(f"  {'Rcarga':>8}{'I':>9}{'Vout':>9}  modo{'P(317)':>10}")
    for rl in (100, 47, 22, 15, 10, 4.7, 2):
        d, m, q = b.run(f"tr_{rl}", tap=2, vset=0.5, iset=1.0, load=rl)
        print(f"  {rl:7}R{q['iout_dc']:8.3f}A{q['vout_dc']:8.2f}V"
              f"  {'CC' if q['en_cc'] else 'CV'}{q['p_lm317']:9.1f}W")


def case_short(b: Bench):
    print("== Cortocircuito franco (0,2 ohm), Iset al maximo ==")
    print(f"  {'TAP':>4}{'Vin-Vout':>10}{'I':>8}{'P':>8}{'Tj regimen':>12}   veredicto")
    for tap in (1, 2, 3):
        d, m, q = b.run(f"sh_{tap}", tap=tap, vset=0.5, load=0.2)
        dif = q["vraw_dc"] - q["vout_dc"]
        tj = TAMB + q["p_lm317"] * RTH_TOTAL
        v = "OK" if dif < 60 else "*** >60 V, MAXIMO ABSOLUTO ***"
        if tj > TJ_MAX:
            v += " / corta el apagado termico"
        print(f"  {tap:>4}{dif:9.1f}V{q['iout_dc']:7.2f}A{q['p_lm317']:7.1f}W"
              f"{tj:11.0f}C   {v}")


# --- disipacion --------------------------------------------------------------
# clave de .meas -> (etiqueta, potencia nominal del componente que pondria yo)
COMPONENTES = [
    ("p_lm317",  "LM317HV (TO-220 + disipador)",   20.0),   # tabla 7.5
    ("p_r2c",    "R2c pote grueso de panel 10k",    0.25),
    ("p_r2f",    "R2f pote fino de panel 1k",       0.125),
    ("p_q_min",  "Q_min BD139 (TO-126)",            1.25),
    ("p_re_min", "Re_min 1k3 (3 W por el fallo)",   3.0),
    ("p_rshunt", "Rshunt 0,33 (2 W por el transitorio)", 2.0),
    ("p_rbleed", "Rbleed 10k",                      1.0),
    ("p_puente", "puente rectificador (4 diodos)",  4.0),
    ("p_r1",     "R1 270",                          0.25),
    ("p_tp1",    "TP1 trimmer 150",                 0.25),
    ("p_rref",   "Rref 2k2",                        0.25),
    ("p_rsnub",  "Rsnub 100",                       0.5),
    ("p_rfilt",  "Rfilt 1k",                        0.125),
    ("p_rset",   "Rset 22k",                        0.125),
    ("p_rpot_i", "Rpot_i pote de corriente 4k7",    0.25),
    ("p_rb",     "Rb 4k7",                          0.125),
    ("p_rbe",    "Rbe 10k",                         0.125),
    ("p_qcc",    "Qcc NPN pequeno",                 0.35),
]

# El vset de los casos "a 1 A" esta elegido para que quede margen de rail con
# la carga puesta: a plena corriente el rail cae y se pierde ~1,5 V de rango.
# vset = Vout / 40,4, porque la escala es Vout = 1,25*R2/R1 con R2 = vset*11000
# y R1 = 340.  Estos vset se eligieron con la escala anterior (40,625): la
# diferencia es del 0,5 %, irrelevante para lo que miden (margen de rail).
ESCENARIOS = [
    ("T1 max vacio", 1, 0.356, 100000),   # 14,5 V, el techo de la toma
    # Estos dos escenarios prueban el TECHO de cada banda a 1 A, que es donde
    # la regla de los 3 V de margen y la de los 20 W se cruzan.  Si algun dia se
    # monta el filtro CRC hay que bajarlos ~1 V por el I*R: con 1 ohm se quedan
    # en 2,03 V de margen, por debajo del dropout del chip.
    ("T1 11V 1A",    1, 0.271, 11),
    ("T1 2V 1A",     1, 0.049, 2),
    ("T1 corto",     1, 0.271, 0.2),
    ("T2 max vacio", 2, 0.767, 100000),   # 31,2 V
    ("T2 27V 1A",    2, 0.665, 27),
    ("T2 2V 1A",     2, 0.049, 2),
    ("T2 corto",     2, 0.665, 0.2),
    ("T3 max vacio", 3, 1.000, 100000),   # 40,6 V
    ("T3 39V 1A",    3, 0.960, 39),
    ("T3 2V 1A",     3, 0.049, 2),
    ("T3 corto",     3, 0.960, 0.2),
]


def case_power(b: Bench):
    print("== Matriz de escenarios: disipacion por componente ==\n")
    filas = {}
    for name, tap, vset, load in ESCENARIOS:
        _, _, q = b.run("pw_" + name.replace(" ", "_"), tap=tap, vset=vset, load=load)
        filas[name] = q
        print(f"  {name:13} Vout={q['vout_dc']:6.2f}V  I={q['iout_dc']:6.3f}A  "
              f"margen={q['headroom']:6.2f}V{'!' if q['headroom']<2.5 else ' '} "
              f"{'CC' if q['en_cc'] else 'CV'}  "
              f"P(317)={q['p_lm317']:6.2f}W  "
              f"Tj_reg={TAMB + q['p_lm317']*RTH_TOTAL:4.0f}C")

    print("\n  Peor caso de cada componente en toda la matriz:\n")
    print(f"  {'componente':34}{'peor':>9}{'escenario':>16}{'nominal':>10}")
    print("  " + "-" * 74)
    for key, etiqueta, nominal in COMPONENTES:
        peor, donde = 0.0, ""
        for name, q in filas.items():
            v = abs(q.get(key, 0.0))
            if v > peor:
                peor, donde = v, name
        marca = ""
        if peor > nominal:
            marca = "   *** EXCEDE ***"
        elif peor > 0.6 * nominal:
            marca = "   (al 60 %+)"
        print(f"  {etiqueta:34}{peor:8.3f}W{donde:>16}{nominal:9.2f}W{marca}")

    ipk = max(q.get("ipk_diodo", 0) for q in filas.values())
    irms = max(q.get("irms_sec", 0) for q in filas.values())
    tjmax = max(TAMB + q["p_lm317"] * RTH_TOTAL for q in filas.values())
    peor_tj = max(filas, key=lambda k: filas[k]["p_lm317"])
    psec = max(abs(q.get("p_sec", 0)) for q in filas.values())
    pprim = max(abs(q.get("p_prim", 0)) for q in filas.values())
    print(f"\n  Perdidas en el cobre de los trafos (no son componentes que compres):")
    print(f"    secundarios {psec:5.2f} W   primarios {pprim:5.2f} W")
    print("\n  Corriente y temperatura:")
    print(f"    pico por diodo del puente : {ipk:6.2f} A  "
          f"(1N5408: 3 A continuos, 200 A de pico)")
    print(f"    RMS por el secundario     : {irms:6.2f} A")
    print(f"    Tj de regimen, peor caso  : {tjmax:6.0f} C en '{peor_tj}' "
          f"(maximo {TJ_MAX:.0f} C)")
    if tjmax > TJ_MAX:
        print("    -> ahi corta el apagado termico del chip, que es justo para lo")
        print("       que esta.  No es un fallo, pero no dejes la fuente asi.")


CASES = {"cv": case_cv, "ripple": case_ripple, "cc": case_cc,
         "short": case_short, "power": case_power}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=sorted(CASES))
    ap.add_argument("--workdir")
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()

    wd = Path(a.workdir) if a.workdir else Path("/tmp/psu_cvcc_verify")
    b = Bench(wd)
    try:
        for name in ([a.only] if a.only else list(CASES)):
            CASES[name](b)
            print()
    finally:
        if not a.keep and not a.workdir:
            shutil.rmtree(wd, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
