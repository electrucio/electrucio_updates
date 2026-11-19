#!/usr/bin/env python3
"""Banco de medida sobre quasimod_guitar_amplifier: un .tran por punto.

Parchea el netlist del 40W para fijar cada mando y cada condicion, lo corre en
batch y devuelve los armonicos y las .meas. `run()` es la unica funcion que se
suele llamar desde fuera; `thd_split()` separa el THD en par e impar, que para
una guitarra es mas informativo que el total.

    import bench
    bench.PROBES = ("SPEAKER",)
    r = bench.run(work, amp=0.35, drive=0.5, u1=0, u2=0,
                  treble=0.5, bass=0.5, vol=0.5, rload=8.0, vraw=50.0)
    total, par, impar = bench.thd_split(r["SPEAKER"])

Dos decisiones que importan al leer los resultados:

- `mains=False` (lo normal) sustituye la cadena de red por una continua rigida
  de `vraw` voltios. Tarda 3 s en vez de 80 y vale para todo lo que no dependa
  de la regulacion. Para potencia maxima o caida de rail hace falta
  `mains=True`, y entonces `settle` tiene que ser 0,8 s o mas: cargar los
  10000 uF desde cero lleva cientos de milisegundos y con los 30 ms por
  defecto se mide el transitorio de arranque, no el regimen permanente.
- `drive=0` es el cero del parametro, no el tope mecanico del mando. El pote
  es logaritmico inverso y el minimo real del aparato cae en **drive 0,20**.
  Ver guitar_amplifier/power_summary.md.

PROBES es constante de modulo: se reasigna antes de llamar a run() para elegir
que nodos llevan .four y .meas, porque cada uno cuesta tiempo y tamano de .raw.

NECESITA el .net generado por LTspice, que esta en el .gitignore. Este build no
sabe netlistar en batch (`-netlist` abre ventana y se queda ahi), asi que hay
que abrir el .asc en la GUI una vez. asc2net.py genera un netlist equivalente
pero numera los nodos anonimos de otra forma, y los parches de aqui van contra
los nombres de LTspice, asi que no sirve como sustituto.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "guitar_amplifier/ltspice"))
from ltrun import Netlist, run_batch                      # noqa: E402
from parse_log import parse_ltspice_log                   # noqa: E402

AMP = ROOT / "guitar_amplifier/ltspice"
NET = AMP / "quasimod_guitar_amplifier.net"
if not NET.exists():                                      # pragma: no cover
    raise SystemExit(
        f"falta {NET}\n"
        "Esta en el .gitignore y lo genera LTspice. Abre el .asc en la GUI y\n"
        "File > Export Netlist, o simplemente corre una simulacion: el .net\n"
        "aparece al lado. `LTspice -netlist` NO funciona en batch en este build.")
MAINS = "V4 N004 N005 SINE(0 325 50) Rser=0.1"
SPEAKER_MODEL = ("R28 0003 0002 12.5", "L4 0003 0002 20m", "C15 0003 0002 250u",
                 "R29 0004 0003 0.5", "C16 0004 0003 50u", "L5 0004 0003 100u",
                 "R30 0 0004 20", "L6 0 0004 100u")
R_LOAD = "R27 0002 SPEAKER 7.5"
U1 = "XU1 N023 NC_01 0 NC_02 SPDT Status=0.5"      # ramal POSITIVO (D5+D6)
U2 = "XU2 N024 NC_03 0 NC_04 SPDT Status=0.5"      # ramal NEGATIVO (D8)
PROBES = ("PICKUP_OUT", "Q12E", "Q10C", "TONE_IN", "TONE_OUT", "PREAMP_OUT", "SPEAKER")
NHARM = 20

# resistencias reales del aparato (fuera: modelo de trafo, de altavoz y dummies)
SKIP = {"R20", "R21", "R59",              # 1G de cuelgue
        "R22", "R23", "R25",              # modelo del trafo
        "R28", "R29", "R30",              # modelo del altavoz
        "R24"}                            # ESR del deposito


def _val(v):
    """Valor SPICE a ohmios: 2k2, 4K7, 10Meg, 1G, 0.5, 470."""
    m = re.match(r"(?i)^([0-9.]+)\s*(meg|[kmgr])?([0-9]*)$", v)
    if not m:
        return None
    base, suf, frac = m.group(1), (m.group(2) or "").lower(), m.group(3)
    mult = {"": 1.0, "r": 1.0, "k": 1e3, "meg": 1e6, "m": 1e6, "g": 1e9}[suf]
    x = float(base + ("." + frac if frac else "")) if suf in ("", "r") and not frac \
        else float(base) + (float("0." + frac) if frac else 0.0)
    return x * mult


def resistors(text):
    out = {}
    for line in text.splitlines():
        m = re.match(r"^(R\d+)\s+\S+\s+\S+\s+(\S+)\s*$", line.strip())
        if not m:
            continue
        v = _val(m.group(2))
        if v is not None:
            out[m.group(1)] = v
    return out


def build(work, tag, amp, drive, u1, u2, freq=1000.0, periods=20, settle=30e-3,
          mains=False, vraw=45.0, rload=8.0, speaker_model=False,
          treble=0.5, bass=0.5, vol=1.0, mains_v=325.0, rpow=False,
          tight=True, patches=()):
    n = Netlist.from_file(NET).absolutize_libs([AMP])
    n.drop_re(r"\s*\.meas\s+tran\b", 80)
    n.drop_re(r"\s*\.four\b", 7)
    if mains:
        if mains_v != 325.0:
            n.patch(MAINS, MAINS.replace("325", f"{mains_v:g}"))
    else:
        n.add(f".param vraw={vraw}", "V_RAW N002 0 {vraw}")
        n.patch(MAINS, "V4 N004 N005 0 Rser=0.1")
    if not speaker_model:
        for line in SPEAKER_MODEL:
            n.patch(line + "\n", "")
        n.patch(R_LOAD, f"R27 0 SPEAKER {rload}")
    for o, nw in patches:
        n.patch(o, nw)
    n.patch(U1, U1.replace("Status=0.5", f"Status={u1}"))
    n.patch(U2, U2.replace("Status=0.5", f"Status={u2}"))
    n.patch(".param in_amplitude = 0.1 ; 150 mVp = nuestro target P90",
            f".param in_amplitude = {amp}")
    n.patch(".param drive=1", f".param drive={drive}")
    n.patch(".param in_freq=1000", f".param in_freq={freq:g}")
    n.patch(".param treble=0.5", f".param treble={treble}")
    n.patch(".param bass=0.5", f".param bass={bass}")
    n.patch(".param vol=1.0", f".param vol={vol}")
    n.patch(".tran {step} {t_stop} {t_start} {step}",
            f".tran {1/(freq*2000):g} {settle + periods/freq:g} {settle:g} "
            f"{1/(freq*2000):g}")
    if tight:
        n.add(".options reltol=1e-5 vntol=1e-6 abstol=1e-12")
    for p in PROBES:
        n.add(f".four {freq:g} {NHARM} {periods} V({p})")
    for p in PROBES:
        n.add(f".meas tran {p}_rms RMS V({p})", f".meas tran {p}_max MAX V({p})",
              f".meas tran {p}_min MIN V({p})")
    n.add(".meas tran P_SPK AVG abs(V(SPEAKER)*I(R27))",
          ".meas tran VRAW_AVG AVG V(N002)", ".meas tran VRAW_MIN MIN V(N002)")
    rs = {}
    if rpow:
        rs = {k: v for k, v in resistors(n.text).items() if k not in SKIP}
        for name in rs:
            n.add(f".meas tran I{name} RMS I({name})")
    n.add(".save " + " ".join(f"V({p})" for p in PROBES) + " I(R27) V(N002)"
          + ("" if not rs else " " + " ".join(f"I({k})" for k in rs)))
    return n.write(work / f"{tag}.net"), rs


def harmonics(log, node):
    p = parse_ltspice_log(str(log))
    h = p["fourier_signal"].get(node.lower(), {})
    if not h:
        return {}
    f0 = min(h)
    return {int(round(f / f0)): v for f, v in h.items()}


def thd_split(h):
    if not h or 1 not in h or h[1] == 0:
        return (None, None, None)
    f = h[1]
    ev = sum(v * v for k, v in h.items() if k > 1 and k % 2 == 0) ** 0.5
    od = sum(v * v for k, v in h.items() if k > 1 and k % 2 == 1) ** 0.5
    return (100 * (ev * ev + od * od) ** 0.5 / f, 100 * ev / f, 100 * od / f)


def run(work, **kw):
    net, rs = build(work, **kw)
    run_batch(net, timeout=900)
    log = net.with_suffix(".log")
    out = {p: harmonics(log, p) for p in PROBES}
    out["meas"] = parse_ltspice_log(str(log))["meas"]
    out["rpow"] = {k: out["meas"].get(f"i{k.lower()}", 0) ** 2 * v
                   for k, v in rs.items()}
    return out
