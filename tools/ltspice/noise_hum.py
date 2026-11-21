#!/usr/bin/env python3
"""Lo que se oye con la guitarra en silencio: siseo (.noise) y zumbido (.tran).

    python3 tools/ltspice/noise_hum.py

Son dos cosas distintas y se miden distinto, y esa es media explicacion:

- El **siseo** es aleatorio: ruido termico de las resistencias (4kTR) y de
  disparo de las uniones (2qI). Se saca con `.noise`, que linealiza alrededor
  del punto de operacion y cuesta 0.08 s. El `.raw` trae la contribucion de
  CADA dispositivo por separado, asi que se puede repartir la culpa.
- El **zumbido** es determinista: es el rizado del deposito colandose en la
  senal. El `.noise` no lo ve en absoluto. Hace falta la red simulada y un
  `.tran` largo, y se mide como el armonico de 100 Hz en el altavoz.

Dos salvedades, dichas antes de que nadie pregunte:

1. Ningun modelo de este netlist trae `KF`/`AF`, asi que **no hay ruido 1/f**.
   Resulta no importar: el 98 % de la potencia de ruido de este ampli esta por
   encima de 2 kHz, y el 1/f vive por debajo de 1 kHz.
2. El ruido referido a la entrada NO se integra: la ganancia se desploma en
   los extremos de la banda, `inoise` se dispara al dividir por ella y la
   integral se la comen los bordes donde el ampli ya no amplifica. Se da como
   el ruido de salida dividido por la ganancia en banda media.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bench                                                   # noqa: E402
from ltrun import Netlist, run_batch                           # noqa: E402
from parse_log import parse_ltspice_log                        # noqa: E402
from rawread import read_raw                                   # noqa: E402

BAND = (20.0, 20000.0)
SETTINGS = (("vol 1.0", 1.0, 0.5), ("vol 0.5", 0.5, 0.5),
            ("vol 0.25", 0.25, 0.5))


def noise_run(work, tag, vol, drive, u1=0, u2=0, vraw=50.0, rload=8.0):
    """Un .noise con el rail firme. Devuelve (f, onoise, inoise, gain, por_pieza)."""
    n = Netlist.from_file(bench.NET).absolutize_libs([bench.AMP])
    n.drop_re(r"\s*\.meas\s+tran\b", 80)
    n.drop_re(r"\s*\.four\b", 7)
    n.add(f".param vraw={vraw}", "V_RAW N002 0 {vraw}")
    n.patch(bench.MAINS, "V4 N004 N005 0 Rser=0.1")
    for line in bench.SPEAKER_MODEL:
        n.patch(line + "\n", "")
    n.patch(bench.R_LOAD, f"R27 0 SPEAKER {rload}")
    n.patch(bench.U1, bench.U1.replace("Status=0.5", f"Status={u1}"))
    n.patch(bench.U2, bench.U2.replace("Status=0.5", f"Status={u2}"))
    n.patch(".param drive=1", f".param drive={drive}")
    n.patch(".param vol=1.0", f".param vol={vol}")
    n.patch(".tran {step} {t_stop} {t_start} {step}",
            ".noise V(SPEAKER) V6 dec 25 10 100k")
    p = n.write(work / f"{tag}.net")
    run_batch(p, timeout=300)
    names, d = read_raw(str(p.with_suffix(".raw")))
    f = np.asarray(d["frequency"]).real
    per = {k: np.asarray(d[k]).real for k in names
           if k not in ("frequency", "gain", "V(onoise)", "V(inoise)")
           and "." not in k}
    return (f, np.asarray(d["V(onoise)"]).real, np.asarray(d["V(inoise)"]).real,
            np.abs(np.asarray(d["gain"]).real), per)


def integ(f, v, band=BAND):
    m = (f >= band[0]) & (f <= band[1])
    return float(np.sqrt(np.trapezoid(np.asarray(v)[m] ** 2, f[m])))


def hum_run(work, tag, amp, vol, settle=2.0):
    """Zumbido: red de verdad, senal a 1 kHz y un .four aparte a 50 Hz.

    La senal de prueba va a 1 kHz y NO a 50: a 50 Hz el rizado de 100 cae
    justo encima del segundo armonico de la propia senal y deja de poderse
    distinguir una cosa de la otra.  La ventana son 100 ms, que son 5 periodos
    de 50 Hz, los que necesita el .four del zumbido.

    **El asentamiento son 2 s y no 0.9**, por la misma razon que en
    power_budget.py pero con una consecuencia mas vistosa: a 0.9 s el
    condensador de salida de 3300 uF sigue cargandose, y esa deriva lenta el
    analisis de Fourier la reparte como componente de 50 Hz.  Salian 1.299 mV
    a 50 Hz, MAS que los 0.480 de 100, lo cual es imposible en una fuente con
    puente completo.  Con 2 s los 50 Hz caen a 0.027 mV y los 100 se quedan
    donde estaban.  Si alguna vez vuelve a aparecer un 50 Hz grande aqui, el
    primer sospechoso es el tiempo de asentamiento, no el transformador.
    """
    bench.PROBES = ("SPEAKER",)
    bench.NHARM = 10
    net, _, _ = bench.build(work, tag=tag, amp=amp, drive=0.5, u1=0, u2=0,
                            freq=1000.0, periods=100, settle=settle,
                            mains=True, rload=8.0, treble=0.5, bass=0.5,
                            vol=vol)
    txt = net.read_text(encoding="ascii")
    assert "\n.end" in txt, "el netlist no acaba en .end"
    net.write_text(txt.replace("\n.end", "\n.four 50 10 5 V(SPEAKER)\n.end"),
                   encoding="ascii")
    run_batch(net, timeout=1800)
    p = parse_ltspice_log(str(net.with_suffix(".log")))
    return (p["fourier_mains"].get("speaker", {}),
            p["fourier_signal"].get("speaker", {}), p["meas"])


def main() -> None:
    work = Path(tempfile.mkdtemp(prefix="noise_hum_"))
    print(f"trabajando en {work}\n")

    print("SISEO  (.noise, 20 Hz - 20 kHz, 8 ohm, sin diodos, tono plano)")
    print()
    print("  mandos    salida uV   ganancia   entrada uV   S/N dB(*)")
    first = None
    for label, vol, drive in SETTINGS:
        f, on, inz, g, per = noise_run(work, f"n_{vol}", vol, drive)
        tot = integ(f, on)
        gmid = float(np.interp(1000.0, f, g))
        iref = tot / gmid if gmid else float("nan")
        snr = 20 * np.log10(0.1 / iref) if iref else float("nan")
        print(f"  {label:<9} {tot*1e6:9.1f} {gmid:10.2f} {iref*1e6:12.2f} "
              f"{snr:9.1f}")
        if first is None:
            first = (f, on, per, tot)
    print()
    print("  (*) con un pickup entregando 100 mVp")
    print()

    f, on, per, tot = first
    print("  de donde sale, a volumen maximo:")
    rank = sorted(((integ(f, v), k) for k, v in per.items()), reverse=True)
    print()
    print("    pieza     uV     %")
    for v, k in rank[:6]:
        print(f"    {k[2:-1].upper():<8} {v*1e6:6.1f} {100*v*v/tot**2:5.1f}")
    print()
    for lo, hi, lab in ((20, 200, "20-200 Hz"), (200, 2000, "200-2k"),
                        (2000, 20000, "2k-20k")):
        print(f"    {lab:<10} {integ(f, on, (lo, hi))*1e6:6.1f} uV")
    print()

    print("ZUMBIDO  (red simulada, 100 Hz en el altavoz)")
    print()
    print("  condicion          50 Hz mV  100 Hz mV  200 Hz mV   dB bajo la senal")
    for i, (label, amp, vol) in enumerate((("reposo, vol max", 0.0, 1.0),
                                           ("reposo, vol min", 0.0, 0.1),
                                           ("plena potencia", 0.205, 1.0))):
        f50, fsig, m = hum_run(work, f"h{i}", amp, vol)
        h100 = f50.get(100, 0.0)
        sig = fsig.get(1000, 0.0)
        rel = (f"{20 * np.log10(h100 / sig):17.1f}"
               if amp and h100 and sig else f"{'-':>17}")
        print(f"  {label:<18} {f50.get(50, 0.0)*1e3:8.3f} {h100*1e3:10.3f} "
              f"{f50.get(200, 0.0)*1e3:10.3f} {rel}")


if __name__ == "__main__":
    main()
