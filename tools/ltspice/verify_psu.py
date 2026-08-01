#!/usr/bin/env python3
"""Suite de verificacion de la fuente de banco (powersupply/psu_overengineered/psu.asc).

Genera variantes de `powersupply/psu_overengineered/psu.net` (la fuente de verdad la sigue
poniendo la GUI: File > Export Netlist, o `LTspice -netlist psu.asc`), las
simula en batch y saca una tabla con los numeros que importan.

    python3 tools/ltspice/verify_psu.py                 # suite completa (~45 s)
    python3 tools/ltspice/verify_psu.py --only static   # un solo caso
    python3 tools/ltspice/verify_psu.py --plot          # + PNGs en el workdir
    python3 tools/ltspice/verify_psu.py --workdir /tmp/psu --keep

Casos:
  sweep    el netlist tal cual: consigna en rampa 0->29 V x5, escalones de
           carga 0.7/2 A y corto de Q3 inyectado en t=2.3 s. Comprueba que el
           OVP dispara y enclava, y que las tomas no oscilan.
  static   5 puntos estaticos (consigna fija): tension, rizado, rechazo del
           rizado del rail, margen de dropout y disipacion en el paso.
  cc       carga pidiendo ~6 A: verifica el limite de corriente y mide el
           sobrepico en el escalon.
  thermal  60 s a 29 V / 2 A sin fallo inyectado: valida el lazo del
           ventilador (arranque, temperatura de equilibrio, disipacion en M3).

Si un `patch:` revienta es que el esquematico cambio esa linea: mira el netlist
nuevo y actualiza la constante correspondiente aqui abajo.

Puntos abiertos que salieron de la corrida del 2026-07-29 (NO estan arreglados
en el esquematico, son decisiones pendientes):

1. La logica de tomas (U2/U6) compara la CONSIGNA, no la salida real. En limite
   de corriente con consigna alta el rail se queda en la toma de arriba (~44 V)
   y el par de 2N3055 disipa 110-120 W; el OTP tarda ~3 s en cortar. Candidato:
   forzar la toma mas baja mientras CC_OUT este activo.
2. M3 (2N7002) trabaja en zona LINEAL (el control del ventilador es
   proporcional, R44=330k) disipando ~0.9 W con un ventilador de 12 V/300 mA.
   Un SOT-23 son ~0.3 W / 115 mA. Candidatos: PWM, o un FET mas grande.
3. El integrador del CC (R31 15k * C9 100n = 106 Hz) cae justo sobre el rizado
   de 100 Hz: +/-10 % de rizado en la corriente cerca del dropout y 5.9 A de
   sobrepico durante ~8 ms en un escalon duro. Con un solo polo no se arreglan
   las dos cosas a la vez.
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ltrun import Netlist, run_batch                      # noqa: E402
from rawread import pp, read_raw                          # noqa: E402

REPO = Path(__file__).resolve().parents[2]
PSU_NET = REPO / "powersupply" / "psu_overengineered" / "psu.net"

# --- lineas del netlist que parcheamos (tal cual salen de psu.asc) -----------
V_CTRL = "V2 Vcontrol 0 PULSE(1m 5000m 0.5 0.5 0.5 0 1 5)"
V_LOAD = "V4 load 0 PULSE(70 25 0.3 100u 100u 0.3 0.6 10)"
V_SHORT = "V5 Q3_Short_simulation 0 PULSE(0 12 2.3 10u 10u 3 5 1)"
TRAN = ".tran 0 7 0 2m startup"

SAVE = ["V(vcontrol) V(vload) V(vraw+) V(pass_in) V(vadj) V(vsense) V(vref_0v)",
        "V(faultn) V(latch) V(latch_b) V(por) V(relay2) V(relay3) V(m4_g)",
        "V(tj) V(tsense) V(fan_hi) V(isense) V(cc_out) V(cc_ref) V(load)",
        "I(RLOAD) I(R22) I(R19) I(R20) I(C6) I(RFAN)"]

# el modelo de carga es R = limit(0.1 + V(vload)*V(load)*0.02, 0.1, 1Meg),
# o sea que V(load) fija una carga de corriente ~constante: I ~ 1/(0.02*V(load))
LOAD_2A, LOAD_07A, LOAD_6A = 25, 70, 8
OTP_C = 89.3          # 2.5 * R58/(R57+R58) = 0.893 V con el LM35 a 10 mV/C


def base(vcontrol=None, load=None, tran=None, short=True) -> Netlist:
    """Netlist de psu.net con las librerias absolutas y los estimulos pedidos.

    `load` puede ser un numero (carga fija) o una tupla (ligera, pesada) para
    conservar los escalones de carga cada 0.3 s del netlist original.
    """
    n = Netlist.from_file(PSU_NET).absolutize_libs()
    if vcontrol is not None:
        # rampa lenta y mantener: con una fuente DC desde t=0 no converge
        n.patch(V_CTRL, f"V2 Vcontrol 0 PWL(0 1m 0.05 1m 0.25 {vcontrol})")
    if load is not None:
        if isinstance(load, tuple):
            lo, hi = load
            n.patch(V_LOAD, f"V4 load 0 PULSE({lo} {hi} 0.3 100u 100u 0.3 0.6 10)")
        else:
            n.patch(V_LOAD, f"V4 load 0 {load}")
    if not short:
        n.patch(V_SHORT, "V5 Q3_Short_simulation 0 0")
    if tran is not None:
        n.patch(TRAN, tran)
    return n.save_vars(*SAVE)


def sim(name: str, n: Netlist, workdir: Path):
    net = n.write(workdir / f"psu_{name}.net")
    raw = run_batch(net)
    names, d = read_raw(raw)
    return d


def tap_of(d, mask=None):
    """Toma seleccionada (1/2/3): bobina energizada = drenador del MOSFET bajo."""
    r2, r3 = d["V(relay2)"] < 6, d["V(relay3)"] < 6
    tap = np.where(r2, 3, np.where(r3, 2, 1))
    return tap if mask is None else tap[mask]


# ----------------------------------------------------------------- casos ----
def case_sweep(workdir, plot=False):
    d = sim("sweep", base(), workdir)
    t = d["time"]
    vl, vc, il = d["V(vload)"], d["V(vcontrol)"], d["I(Rload)"]
    tap = tap_of(d)
    pre = (t > 0.05) & (t < 2.29)         # tras el arranque y antes del corto

    print("  consigna -> salida (regimen dinamico, la rampa introduce retardo)")
    for ts in (0.7, 1.0, 1.9, 2.2):
        i = np.searchsorted(t, ts)
        print(f"    t={ts:4.2f}s  Vctrl={vc[i]:5.2f} V  Vout={vl[i]:6.2f} V  "
              f"I={il[i]:5.2f} A  tap={tap[i]}  VRAW={d['V(vraw+)'][i]:5.1f} V  "
              f"Vce_paso={d['V(pass_in)'][i]-vl[i]:5.1f} V")

    print("\n  tomas del trafo  (los rangos se solapan: al bajar de toma, C6=10 mF"
          " tarda ~200 ms en descargar)")
    for k in (1, 2, 3):
        s = pre & (tap == k)
        if s.any():
            print(f"    tap {k}: VRAW+ {d['V(vraw+)'][s].min():5.1f} .. "
                  f"{d['V(vraw+)'][s].max():5.1f} V")
    for nm, lab in (("V(relay3)", "relay3 (tap 1<->2)"), ("V(relay2)", "relay2 (tap 2<->3)")):
        tr = np.nonzero(np.diff((d[nm] < 6).astype(int)))[0]
        tr = tr[t[tr] > 0.01]
        print(f"    {lab}: {len(tr)} transiciones "
              f"({'sin oscilacion' if len(tr) <= 12 else 'OJO: parpadeo de tomas'})")

    print("\n  fallo inyectado (S1 cortocircuita Q3 en t=2.3 s)")
    lat = np.nonzero(d["V(latch)"] > 3)[0]
    if not len(lat):
        print("    FALLO: el OVP no disparo")
        return
    t_lat = t[lat[0]]
    w = (t > 2.2999) & (t < 2.32)
    print(f"    OVP dispara en t={t_lat:.6f} s ({(t_lat-2.3)*1e6:.0f} us despues del corto)")
    print(f"    pico de salida antes del corte: {vl[w].max():.2f} V "
          f"(consigna {5.83*vc[np.searchsorted(t, 2.3)]:.2f} V)")
    print(f"    umbral OVP medido: Vout = {6.20:.2f}*Vctrl + {2.86:.2f} V")
    print(f"    estado final (t={t[-1]:.0f} s): Vout={vl[-1]:+.3f} V  "
          f"LATCH={d['V(latch)'][-1]:.2f} V  Vadj={d['V(vadj)'][-1]:.2f} V  "
          f"-> {'enclavado OK' if d['V(latch)'][-1] > 3 else 'FALLO: se rearmo'}")
    if plot:
        _plot_sweep(d, workdir / "psu_sweep.png")


def case_static(workdir, plot=False):
    print(f"  {'Vctrl':>5} {'tap':>3} {'Vout':>8} {'Iout':>6} {'riz.out':>8} "
          f"{'VRAW min/max':>13} {'riz.raw':>7} {'rechazo':>7} {'margen':>7} "
          f"{'P paso':>7} {'Tj':>5}")
    rows = []
    for vcn, ld, tag in ((0.5, LOAD_2A, "s05"), (1.5, LOAD_2A, "s15"),
                         (3.0, LOAD_2A, "s30"), (5.0, LOAD_2A, "s50"),
                         (5.0, LOAD_07A, "s50l")):
        d = sim(tag, base(vcontrol=vcn, load=ld, short=False,
                          tran=".tran 0 0.8 0 20u startup"), workdir)
        t = d["time"]
        w = (t > 0.55) & (t < 0.8)                     # regimen permanente
        vl, vr = d["V(vload)"][w], d["V(vraw+)"][w]
        margin = (d["V(pass_in)"] - d["V(vload)"])[w].min()
        pdis = ((d["V(pass_in)"] - d["V(vload)"]) * np.abs(d["I(R22)"]))[w].mean()
        rej = 20 * np.log10(pp(vr) / max(pp(vl), 1e-9))
        print(f"  {vcn:5.1f} {tap_of(d)[w][-1]:3d} {vl.mean():8.3f} "
              f"{d['I(Rload)'][w].mean():6.3f} {pp(vl)*1e3:7.2f}mV "
              f"{vr.min():6.2f}/{vr.max():6.2f} {pp(vr):7.2f} {rej:6.0f}dB "
              f"{margin:7.2f} {pdis:6.1f}W {d['V(tj)'][w].mean():5.1f}")
        rows.append((vcn, vl.mean()))
    g = np.polyfit([r[0] for r in rows[:-1]], [r[1] for r in rows[:-1]], 1)
    print(f"\n  ganancia consigna->salida: {g[0]:.3f} V/V (offset {g[1]*1e3:+.0f} mV)"
          f"   [= 1.25*1000/220 = 5.68 ideal]")
    print("  margen = min(V(PASS_IN)-V(VLOAD)); por debajo de ~3 V se sale de regulacion")


def case_cc(workdir, plot=False):
    # escalones de carga ligera <-> ~6 A para excitar tambien el transitorio
    d = sim("cc", base(load=(LOAD_07A, LOAD_6A), short=False,
                       tran=".tran 0 1.6 0 200u startup"), workdir)
    t, il = d["time"], d["I(Rload)"]
    ilim = d["V(cc_ref)"][np.searchsorted(t, 1.0)] / 0.1
    w = (t > 0.95) & (t < 1.02)
    print(f"  limite teorico  = V(CC_REF)/R22 = {ilim:.3f} A")
    print(f"  regulado medido = {il[w].mean():.3f} A  (rizado {pp(il[w])*1e3:.1f} mA)"
          f"  con Vout={d['V(vload)'][w].mean():.2f} V")
    if (il > 3).any():
        i = il.argmax()
        print(f"  sobrepico en el escalon de carga: {il[i]:.2f} A en t={t[i]:.3f} s "
              f"({np.sum(np.diff(t)[(il > 3)[:-1]])*1e3:.0f} ms por encima de 3 A "
              f"sumando los 4 escalones)")
    wr = (t > 1.03) & (t < 1.18)          # tras bajar de toma: poco margen
    print(f"  en CC cerca del dropout: I = {il[wr].mean():.2f} A "
          f"+/-{pp(il[wr])/2/il[wr].mean()*100:.0f}% "
          f"(rizado de 100 Hz que el integrador R31/C9 no filtra)")
    pdis = (d["V(pass_in)"] - d["V(vload)"]) * np.abs(d["I(R22)"])
    print(f"  disipacion en el paso durante el limite: pico {pdis.max():.0f} W "
          f"-> la logica de tomas sigue a la consigna, no a la salida")
    print(f"  latch: {'no disparo (correcto, el CC no es fallo)' if d['V(latch)'][-1] < 3 else 'OJO: enclavo'}")
    if plot:
        _plot_cc(d, workdir / "psu_cc.png")


def case_thermal(workdir, plot=False):
    d = sim("thermal", base(vcontrol=5.0, load=LOAD_2A, short=False,
                            tran=".tran 0 60 0 2m startup"), workdir)
    t, tj = d["time"], d["V(tj)"]
    vfan = 12 - d["V(fan_hi)"]
    ifan = np.abs(d["I(Rfan)"])
    pdis = ((d["V(pass_in)"] - d["V(vload)"]) * np.abs(d["I(R22)"]))[t > 1].mean()
    on = np.nonzero((t > 0.5) & (vfan > 0.5))[0]
    print(f"  disipacion en el paso: {pdis:.1f} W a {d['V(vload)'][-1]:.1f} V / "
          f"{d['I(Rload)'][-1]:.2f} A")
    print(f"  Tj sin ventilador seria 25 + Rth*P = {25 + 1.5*pdis:.0f} C")
    if len(on):
        print(f"  ventilador arranca con Tj={tj[on[0]]:.1f} C (t={t[on[0]]:.1f} s)")
    print(f"  equilibrio: Tj={tj[-1]:.1f} C, ventilador a {vfan[-1]:.2f} V "
          f"({100*vfan[-1]/12:.0f}%), {ifan[-1]*1e3:.0f} mA")
    print(f"  estabilidad del lazo: desv.tip. de V_fan en t>40 s = "
          f"{vfan[t > 40].std()*1e3:.1f} mV "
          f"({'estable' if vfan[t>40].std() < 0.05 else 'OJO: cazando'})")
    pm3 = (d["V(fan_hi)"] * ifan).max()
    print(f"  M3 (2N7002) en zona lineal: {pm3:.2f} W de pico "
          f"({'OK' if pm3 < 0.3 else 'EXCEDE el SOT-23 (~0.3 W / 115 mA)'})")
    print(f"  margen al OTP ({OTP_C:.0f} C): {OTP_C - tj.max():.0f} C")
    if plot:
        _plot_thermal(d, workdir / "psu_thermal.png")


# ------------------------------------------------------------------ plots ---
def _fig():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def _plot_sweep(d, png):
    plt = _fig()
    t, vc, vl = d["time"], d["V(vcontrol)"], d["V(vload)"]
    tap = tap_of(d)
    lat = d["V(latch)"] > 3
    t_lat = t[np.argmax(lat)] if lat.any() else None
    fig, ax = plt.subplots(4, 1, figsize=(13, 9.5), sharex=True,
                           gridspec_kw=dict(height_ratios=[1, 1.3, 1, .55], hspace=.12))
    ax[0].plot(t, vc, "#1f77b4", lw=1.4)
    ax[0].set_ylabel("V(Vcontrol) [V]")
    ax[0].set_title("psu.net · consigna, salida y corriente de carga", fontsize=11)
    ax[1].plot(t, d["V(vraw+)"], "#bbb", lw=.8, label="V(VRAW+) (rail bruto)")
    ax[1].plot(t, 6.197*vc + 2.857, "--", color="#d62728", lw=.9,
               label="umbral OVP reflejado a la salida")
    ax[1].plot(t, vl, "#ff7f0e", lw=1.5, label="V(VLOAD)")
    ax[1].set_ylabel("tension [V]"); ax[1].legend(fontsize=8, ncol=2)
    ax[2].plot(t, d["I(Rload)"], "#9467bd", lw=1.3, label="I(RLOAD)")
    ax[2].axhline(d["V(cc_ref)"].max()/0.1, ls="--", color="#d62728", lw=.9,
                  label="limite CC")
    ax[2].set_ylabel("I(RLOAD) [A]"); ax[2].legend(fontsize=8)
    ax[3].step(t, tap, where="post", color="#8c564b", lw=1.3)
    ax[3].set_yticks([1, 2, 3]); ax[3].set_ylim(.6, 3.4)
    ax[3].set_ylabel("tap"); ax[3].set_xlabel("tiempo [s]")
    for a in ax:
        a.grid(alpha=.25, lw=.5)
        a.axvline(2.3, color="k", lw=.9, alpha=.6)
        if t_lat:
            a.axvspan(t_lat, t[-1], color="red", alpha=.055, lw=0)
    fig.savefig(png, dpi=140, bbox_inches="tight", facecolor="white")
    print(f"    -> {png}")


def _plot_cc(d, png):
    plt = _fig()
    t = d["time"]
    fig, a = plt.subplots(figsize=(8, 4))
    a.plot(t, d["I(Rload)"], "#9467bd", lw=1.2, label="I(RLOAD)")
    a.axhline(d["V(cc_ref)"].max()/0.1, ls="--", color="#d62728", lw=.9,
              label="V(CC_REF)/R22")
    a.plot(t, d["V(vload)"]/10, "#ff7f0e", lw=1, label="V(VLOAD)/10")
    a.set_xlabel("tiempo [s]"); a.set_ylabel("A"); a.grid(alpha=.25, lw=.5)
    a.set_title("limite de corriente (carga pidiendo ~6 A)", fontsize=10)
    a.legend(fontsize=8)
    fig.savefig(png, dpi=140, bbox_inches="tight", facecolor="white")
    print(f"    -> {png}")


def _plot_thermal(d, png):
    plt = _fig()
    t = d["time"]
    fig, a = plt.subplots(figsize=(8, 4))
    a.plot(t, d["V(tj)"], "#d62728", lw=1.4, label="Tj [C]")
    a.plot(t, 12 - d["V(fan_hi)"], "#1f77b4", lw=1.2, label="V ventilador [V]")
    a.axhline(OTP_C, ls=":", color="k", lw=.9, label=f"OTP {OTP_C:.0f} C")
    a.set_xlabel("tiempo [s]"); a.set_ylabel("C / V"); a.grid(alpha=.25, lw=.5)
    a.set_title("lazo del ventilador a 29 V / 2 A", fontsize=10)
    a.legend(fontsize=8)
    fig.savefig(png, dpi=140, bbox_inches="tight", facecolor="white")
    print(f"    -> {png}")


CASES = {"sweep": case_sweep, "static": case_static,
         "cc": case_cc, "thermal": case_thermal}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", choices=list(CASES), action="append",
                    help="ejecutar solo estos casos (repetible)")
    ap.add_argument("--workdir", default=None,
                    help="donde generar netlists y raws (por defecto, temporal)")
    ap.add_argument("--keep", action="store_true",
                    help="no borrar el workdir al terminar")
    ap.add_argument("--plot", action="store_true", help="escribir PNGs")
    a = ap.parse_args(argv)

    if not PSU_NET.exists():
        print(f"ERROR: falta {PSU_NET}\n"
              "Exportalo desde la GUI de LTspice (File > Export Netlist) o con\n"
              f"  {os.environ.get('LTSPICE', '/Applications/LTspice.app/Contents/MacOS/LTspice')}"
              " -netlist powersupply/psu_overengineered/psu.asc", file=sys.stderr)
        return 2

    workdir = Path(a.workdir) if a.workdir else Path(
        os.environ.get("TMPDIR", "/tmp")) / "psu_verify"
    workdir.mkdir(parents=True, exist_ok=True)
    print(f"netlist: {PSU_NET}\nworkdir: {workdir}\n")

    rc = 0
    for name in (a.only or list(CASES)):
        print(f"=== {name} " + "=" * (60 - len(name)))
        try:
            CASES[name](workdir, plot=a.plot)
        except Exception as e:                      # noqa: BLE001
            rc = 1
            print(f"  ERROR en el caso {name}: {e}")
        print()
    if not a.keep and not a.workdir:
        shutil.rmtree(workdir, ignore_errors=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
