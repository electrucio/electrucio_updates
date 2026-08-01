#!/usr/bin/env python3
"""Suite de verificacion de powersupply/psu_cvcc/psu_cvcc.net.

    python3 tools/ltspice/verify_psu_cvcc.py            # todo (~2 min)
    python3 tools/ltspice/verify_psu_cvcc.py --only cc
    python3 tools/ltspice/verify_psu_cvcc.py --keep --workdir /tmp/psu2

Casos:
  cv     recorrido del pote de tension y rango util de cada toma
  load   regulacion de carga, rizado de salida y rechazo del rizado del rail
  cc     recorrido del pote de corriente y transicion CV->CC
  short  cortocircuito franco por toma: diferencial, corriente y temperatura

Dos trampas del netlist que conviene no redescubrir:

1. El netlist lleva `uic` a proposito.  Sin el, el .op no converge (Gmin y
   source stepping fallan, el pseudo-transitorio devuelve NaN y el transitorio
   entero sale NaN).  Lo que lo hace irresoluble es el lazo de CC colgado del
   pin ADJ.
2. Para medir CC hace falta MARGEN DE RAIL.  Si la consigna de tension esta
   por encima de lo que da la toma, el regulador esta en dropout y el lazo de
   corriente ni se activa: se mide la carga, no el limite.  Por eso los casos
   de CC usan TAP=2 con el pote de tension al 90 %.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ltrun import Netlist, run_batch                      # noqa: E402
from rawread import read_raw                              # noqa: E402

REPO = Path(__file__).resolve().parents[2]
PSU = REPO / "powersupply" / "psu_cvcc"
NET = PSU / "psu_cvcc.net"

SAVE = ("V(vout) V(vraw) V(vadj) V(sense) V(iset) V(ccout) V(tj) V(tsink)",
        "I(Rshunt) I(R1)")

# el pote de corriente: 2v5 -> 22k -> pote(4k7) -> masa, y shunt de 0,33 ohm
def iset_teorico(frac, vref=2.5065):
    rp = frac * 4700
    return (vref * rp / (22000 + rp)) / 0.33


class Bench:
    def __init__(self, workdir: Path):
        self.w = workdir
        self.w.mkdir(parents=True, exist_ok=True)

    def run(self, tag, tap=2, vset=1.0, iset=1.0, load=100, tend=1.2, step="100u"):
        n = Netlist.from_file(NET).absolutize_libs([PSU])
        n.patch(".param TAP=2", f".param TAP={tap}")
        n.patch("Vset     VSET 0 1", f"Vset     VSET 0 {vset}")
        n.patch("Visetadj ISETADJ 0 1", f"Visetadj ISETADJ 0 {iset}")
        n.patch("Vload    LOAD 0 100", f"Vload    LOAD 0 {load}")
        n.patch(".tran 0 1.5 0 100u startup uic",
                f".tran 0 {tend} 0 {step} startup uic")
        n.save_vars(*SAVE)
        d = read_raw(run_batch(n.write(self.w / f"{tag}.net")))[1]
        return d, d["time"] > tend * 0.85


def case_cv(b: Bench):
    print("== CV: recorrido del pote de tension (TAP=3, carga 100 ohm) ==")
    print(f"  {'pote':>6}{'R2':>8}{'Vout':>9}{'teorico':>10}{'error':>8}")
    for vs in (0.02, 0.1, 0.3, 0.5, 0.7, 1.0):
        d, m = b.run(f"cv_{vs}", tap=3, vset=vs)
        v = np.median(d["V(vout)"][m])
        th = 1.25 * (1 + vs * 3900 / 120) + 50e-6 * vs * 3900
        print(f"  {vs*100:5.0f}%{vs*3900:7.0f}R{v:8.2f}V{th:9.2f}V"
              f"{(v-th)/max(th,1)*100:7.1f}%")

    print("\n== Rango util de cada toma (pote al maximo, carga 100 ohm) ==")
    print(f"  {'TAP':>4}{'VRAW+':>9}{'Vout max':>10}{'I(R1)':>9}{'Tj':>7}")
    for tap in (1, 2, 3):
        d, m = b.run(f"cv_tap{tap}", tap=tap, vset=1.0, step="20u")
        print(f"  {tap:>4}{np.median(d['V(vraw)'][m]):8.1f}V"
              f"{np.median(d['V(vout)'][m]):9.2f}V"
              f"{np.median(np.abs(d['I(R1)'])[m])*1e3:8.1f}mA"
              f"{np.median(d['V(tj)'][m]):6.1f}C")


def case_load(b: Bench):
    print("== Regulacion de carga y rizado (TAP=2, Vout ~21,5 V) ==")
    base = None
    for rl in (1000, 100, 47, 22):
        d, m = b.run(f"ld_{rl}", tap=2, vset=0.5, load=rl, step="20u")
        v = np.median(d["V(vout)"][m])
        i = np.median(np.abs(d["I(Rshunt)"])[m])
        rip = d["V(vout)"][m].max() - d["V(vout)"][m].min()
        rrip = d["V(vraw)"][m].max() - d["V(vraw)"][m].min()
        base = base if base is not None else v
        print(f"  {rl:5}R  I={i:6.3f}A  Vout={v:7.3f}V  desv={((v-base)/base*100):+6.3f}%"
              f"  rizado={rip*1e3:6.2f}mV  rechazo={20*np.log10(rrip/max(rip,1e-9)):5.1f}dB")
    print("  (el rechazo real es mejor: 80 dB segun el datasheet con 10 uF en ADJ.")
    print("   Aqui lo limita el ancho de banda del modelo conductual del LM317HV.)")


def case_cc(b: Bench):
    print("== CC: recorrido del pote de corriente (TAP=2, pote de tension al 90 %) ==")
    print(f"  {'pote':>6}{'Iset':>10}{'Rcarga':>8}{'I':>10}{'Vout':>8}{'error':>8}")
    for ia, rl in ((0.05, 220), (0.1, 100), (0.2, 47), (0.4, 22), (0.7, 10), (1.0, 4.7)):
        d, m = b.run(f"cc_{ia}", tap=2, vset=0.9, iset=ia, load=rl, tend=2.0, step="200u")
        i = np.median(np.abs(d["I(Rshunt)"])[m])
        ith = iset_teorico(ia)
        print(f"  {ia*100:5.0f}%{ith*1e3:9.1f}m{rl:7}R{i*1e3:9.1f}m"
              f"{np.median(d['V(vout)'][m]):7.2f}V{(i-ith)/ith*100:7.1f}%")

    print("\n== Transicion CV->CC (TAP=2, Vout pedido 21,5 V, Iset al maximo) ==")
    print(f"  {'Rcarga':>8}{'I':>9}{'Vout':>9}  modo{'P(317)':>10}")
    for rl in (100, 47, 22, 15, 10, 4.7, 2):
        d, m = b.run(f"tr_{rl}", tap=2, vset=0.5, iset=1.0, load=rl)
        i = np.median(np.abs(d["I(Rshunt)"])[m])
        v = np.median(d["V(vout)"][m])
        p = np.median(((d["V(vraw)"] - d["V(vout)"]) * np.abs(d["I(Rshunt)"]))[m])
        mode = "CC" if np.median(d["V(ccout)"][m]) > 0.5 else "CV"
        print(f"  {rl:7}R{i:8.3f}A{v:8.2f}V  {mode}{p:9.1f}W")


def case_short(b: Bench):
    print("== Cortocircuito franco (0,2 ohm), Iset al maximo, 5 s ==")
    print(f"  {'TAP':>4}{'Vin-Vout':>10}{'I':>8}{'P':>8}{'Tj':>8}   veredicto")
    for tap in (1, 2, 3):
        d, m = b.run(f"sh_{tap}", tap=tap, vset=0.5, load=0.2, tend=5, step="200u")
        dif = np.median((d["V(vraw)"] - d["V(vout)"])[m])
        i = np.median(np.abs(d["I(Rshunt)"])[m])
        tj = np.median(d["V(tj)"][m])
        v = "OK" if dif < 60 else "*** >60 V, MAXIMO ABSOLUTO ***"
        if tj > 125:
            v += " / el apagado termico cortaria"
        print(f"  {tap:>4}{dif:9.1f}V{i:7.2f}A{dif*i:7.1f}W{tj:7.1f}C   {v}")


CASES = {"cv": case_cv, "load": case_load, "cc": case_cc, "short": case_short}


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
