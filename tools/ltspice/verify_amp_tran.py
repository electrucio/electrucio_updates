#!/usr/bin/env python3
"""Caracterizacion en el dominio del tiempo del amplificador de 40 W.

    python3 tools/ltspice/verify_amp_tran.py                    # todo
    python3 tools/ltspice/verify_amp_tran.py --only trim
    python3 tools/ltspice/verify_amp_tran.py --only power --plot -o /tmp/fig
    python3 tools/ltspice/verify_amp_tran.py --as-drawn          # sin ajustar

Casos:
  trim        PRIMERO SIEMPRE.  Corriente de reposo real y ajuste de los dos
              trimmers: RV2 -> 40 mA por R16/R17, RV1 -> salida en VRAW/2.
  power       barrido de nivel: THD contra potencia, potencia al 1 % y al 10 %
              de THD, techo y simetria de recorte, rendimiento.
  distortion  barrido del pote de drive, con la THD medida por separado en
              TONE_IN, PREAMP_OUT y SPEAKER para saber QUIEN distorsiona.
              Perfil de armonicos e IMD de dos tonos.
  stability   onda cuadrada con carga resistiva y con 220 nF / 2.2 uF:
              slew rate, sobrepico y oscilacion.  Es lo unico que ve el margen
              de fase; un .ac en lazo cerrado no puede.
  supply      con la red REAL: sag del rail en una rafaga y zumbido de 100 Hz
              a plena potencia.

EL ORDEN IMPORTA.  `trim` corre siempre el primero y los demas casos usan los
cursores que resuelve, salvo con --as-drawn.  Caracterizar la distorsion de un
amplificador mal polarizado no mide el diseno, mide el error de ajuste.

Dos cosas que conviene no redescubrir:

1. QUITAR LOS 4 s DE ARRANQUE.  El .tran del esquematico tarda 64 s porque
   espera hasta t=4 s: el rail sale de la red y en DC una SINE con offset 0
   vale 0 V.  Anadiendo `V_RAW` y matando V4, el .op converge y ES el estado
   estacionario, asi que el .tran arranca ya polarizado.  De 64 s a ~1-2 s.
   Para el sag y el zumbido hace falta la red de verdad, y ahi si se pagan
   los 4 s: son los unicos casos lentos.
2. LA FFT DE UN .tran.  La salida esta muestreada de forma NO uniforme, asi
   que hay que remuestrear (np.interp) sobre una rejilla uniforme y coger un
   numero ENTERO de periodos; asi el fundamental cae exactamente en un bin y
   no hace falta ventana.  Y `.options plotwinsize=0` es obligatorio: con la
   compresion de LTspice la FFT es basura.

El netlist quasimod_guitar_amplifier.net no esta versionado: exportalo una vez desde
la GUI con File > Export Netlist.
"""
from __future__ import annotations

import argparse
import math
import re
import shutil
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ltrun import Netlist, run_batch                            # noqa: E402
from rawread import read_log, read_raw                          # noqa: E402
from svgplot import (Ax, decade_ticks, frame, grid, linear_ticks,  # noqa: E402
                     rasterize)
from verify_tone_ac import NET, AMP, SPEAKER_MODEL, R_LOAD, TRAN, VSRC  # noqa: E402

VRAW_DC = 50.11                # V, rail real en reposo con carga resistiva,
                               # medido por el caso `supply`.  Los 48.88 V
                               # de antes eran con el modelo Vint30 puesto.
IQ_TARGET_MA = 40.0            # lo que pide el esquematico por R16/R17
MAINS = "V4 N004 N005 SINE(0 325 50) Rser=0.1"
RV2 = "XRV2 N010 N011 Q3B linear_pot Rtot=1K wiper=.037"
RV1 = "XRV1 Q1B FEEDBACK FEEDBACK linear_pot Rtot=250K wiper=.54"
RV2_AS_DRAWN, RV1_AS_DRAWN = 0.037, 0.54

# Con .save el raw baja de ~19 MB a ~1 MB por corrida.  La lista tiene que
# cubrir TODO lo que miden los casos: si falta un nodo, no es que salga mal,
# es que no esta.
SAVE = ("V(PICKUP_IN) V(PICKUP_OUT) V(TONE_IN) V(PREAMP_OUT) V(PRE_SPEAKER) "
        "V(SPEAKER) V(N002) V(Q6C) V(N019) V(N024) V(N018) V(N026)",
        "I(R27) I(R16) I(R17)")

# EL SUELO DE THD LO PONE reltol, no el remuestreo ni el paso maximo.  Medido
# sobre una salida en clase A pura (THD real ~0): con el reltol por defecto el
# suelo es 0.038 %, y con esto baja a 0.0038 %.  Cambiar n de la FFT de 1024 a
# 32768 o el paso de 1 us a 0.2 us no mueve nada.  Por debajo de ~0.01 % no hay
# que creerse ningun numero.
TOL = ".options reltol=1e-5 vntol=1e-6 abstol=1e-12"
THD_FLOOR = 0.0038             # %, medido con TOL puesto

# el conector en serie con C1: inyecta en la entrada de la etapa de potencia
# sin romper la carga ni la polarizacion que ve el preamp
C1 = "C1 N017 PREAMP_OUT 1u"

# EL RECORTADOR, TAL COMO ESTA DIBUJADO DESDE EL 2026-08-27.
#
# El .asc ya trae el mod de bias: cada ramal baja a masa por un 10 uF con su
# resistencia de sangrado EN PARALELO, no por un cable.  Antes de esa fecha D6
# iba directo a masa y D8 salia de masa, y los nombres de nodo eran otros
# (N022/N021).  Si vuelven a cambiar, esto casca a gritos en el patch, que es
# lo que se quiere: no hay forma de medir "tal como esta" a ciegas.
#
#   positivo:  TONE_IN -> D5 -> N019 -> D6 -> N024 -> (C36 || R41) -> masa
#   negativo:  masa -> (C35 || R63) -> N026 -> D8 -> N023 -> D9 -> N018
#                                                          -> D7 -> TONE_IN
#
# Dos diodos en el semiciclo positivo (~1.35 V de umbral) y tres en el negativo
# (~1.95 V): el recortador es asimetrico por diseno.
POS_LEG = ("D5 TONE_IN N019 1N4148", "D6 N019 N024 1N4148")
NEG_LEG = ("D7 N018 TONE_IN 1N4148", "D9 N023 N018 1N4148",
           "D8 N026 N023 1N4148")

# Por ramal: su grupo C||R, el diodo de retorno, como queda ese diodo cuando el
# conmutador manda el ramal a masa, y el nombre de la resistencia de sangrado.
POS_BIAS = (("C36 N024 0 10u", "R41 N024 0 2k2"),
            "D6 N019 N024 1N4148", "D6 N019 0 1N4148", "R41")
NEG_BIAS = (("C35 N026 0 10u", "R63 N026 0 2k2"),
            "D8 N026 N023 1N4148", "D8 0 N023 1N4148", "R63")

# Los tres estados de cada conmutador de 3 posiciones:
#
#   "gnd"   retorno directo a masa: el recorte duro clasico.  Se quitan C y R y
#           el diodo de retorno se lleva a masa.  Umbral FIJO.
#   "open"  ramal fuera: ese semiciclo no recorta en el preamp.  Se quitan los
#           diodos Y su grupo C||R, que si no queda flotando.
#   "bias"  tal como esta dibujado.  El condensador coge una continua
#           proporcional al nivel (rectificador de pico) que SE SUMA al umbral:
#           el recorte se aparta segun lo fuerte que toques.
#
# `clip_r` cambia el valor de las DOS resistencias de sangrado a la vez.  Es un
# tiempo de release, tau = R*C: 2k2 -> 22 ms, 10k -> 100 ms, 22k -> 220 ms.
# CADA RAMAL LLEVA SU RESISTENCIA, que es lo dibujado y lo correcto: con una
# puente entre los dos condensadores los ramales quedan acoplados y los
# conmutadores dejan de ser independientes -- a nivel bajo, cuando solo conduce
# el positivo, la puente arrastra el nodo del negativo y le INVIERTE el bias.
# Y la constante de tiempo se parte a la mitad, porque los dos 10 uF quedan en
# serie.  `clip_bridge` existe solo para poder volver a ensenar eso.
LEG_MODES = ("gnd", "open", "bias")


# ------------------------------------------------------------------ utilidades
def _num(txt, pattern):
    m = re.search(pattern, txt, re.M | re.I)
    return float(m.group(1)) if m else None


def spectrum(t, y, f0, cycles=10, t_end=None, n=None):
    """Espectro de una ventana de `cycles` periodos ENTEROS acabada en `t_end`.

    Periodos enteros -> el tono de frecuencia k*f0/cycles cae exacto en el bin
    k y no hace falta ventana.  El remuestreo uniforme es obligatorio: la
    salida de un .tran no lo esta.
    """
    if (t_end or t[-1]) - cycles / f0 < t[0]:
        raise ValueError(f"no hay {cycles} ciclos de {f0} Hz antes de {t_end}")
    _, yu = uniform(t, y, f0, cycles, t_end, n)
    return np.abs(np.fft.rfft(yu - yu.mean())) * 2.0 / len(yu)


def harmonics(t, y, f0, cycles=10, nh=10, t_end=None):
    """(fundamental, [h1..hn], THD) por FFT sobre periodos enteros."""
    amp = spectrum(t, y, f0, cycles, t_end)
    hs = [float(amp[cycles * k]) for k in range(1, nh + 1)
          if cycles * k < len(amp)]
    fund = hs[0]
    thd = math.sqrt(sum(h * h for h in hs[1:])) / fund if fund > 0 else 0.0
    return fund, hs, thd


def uniform(t, y, f0, cycles=10, t_end=None, n=None):
    """Remuestrea `cycles` periodos enteros sobre una rejilla uniforme.

    OBLIGATORIO antes de cualquier media, RMS o FFT.  La salida de un .tran
    esta muestreada de forma NO UNIFORME: LTspice concentra puntos donde la
    senal cambia deprisa.  Un np.mean o un np.sqrt(np.mean(y**2)) sobre las
    muestras crudas pesa de mas esas zonas, y el resultado depende de como
    haya convergido el paso, no de la senal.  Con esto se median potencias no
    monotonas: 620 mV de entrada daban MENOS potencia que 500 mV.
    """
    win = cycles / f0
    t_end = t[-1] if t_end is None else t_end
    n = n or (1 << int(math.ceil(math.log2(cycles * 64))))
    tu = (t_end - win) + np.arange(n) * (win / n)
    return tu, np.interp(tu, t, y)


def rms(y):
    """RMS de una senal YA remuestreada uniforme (ver `uniform`)."""
    return float(np.sqrt(np.mean(np.square(y))))


class Bench:
    """Genera variantes del netlist y las simula.  Cachea por etiqueta."""

    def __init__(self, workdir: Path, rv1=RV1_AS_DRAWN, rv2=RV2_AS_DRAWN,
                 vraw=VRAW_DC, mains=False, dummy_load=True,
                 clip=("gnd", "gnd"), clip_r="2k2", clip_bridge=None):
        self.w = workdir
        self.w.mkdir(parents=True, exist_ok=True)
        self.rv1, self.rv2, self.vraw = rv1, rv2, vraw
        self.mains, self.dummy_load = mains, dummy_load
        for m in clip:
            if m not in LEG_MODES:
                raise ValueError(f"cada ramal debe ser uno de {LEG_MODES}")
        self.clip, self.clip_r = tuple(clip), clip_r
        # `clip_bridge` sustituye las dos resistencias a masa por UNA entre los
        # dos condensadores.  Solo tiene sentido con los dos ramales en bias, y
        # los acopla: dejan de ser independientes.
        self.clip_bridge = clip_bridge

    # ---------------------------------------------------------------- netlist
    def _base(self, rv1=None, rv2=None, load_cap=None, params=None) -> Netlist:
        n = Netlist.from_file(NET).absolutize_libs([AMP])
        n.drop_re(r"\s*\.meas\s+tran\b", 80)
        n.drop_re(r"\s*\.four\b", 7)
        if self.mains:
            # la cadena de red tal cual: es la unica forma de ver sag y zumbido
            pass
        else:
            # rail firme y red apagada -> el .op es el estado estacionario y el
            # .tran arranca ya polarizado, sin los 4 s de carga del deposito
            n.add(f".param vraw={self.vraw}", "V_RAW N002 0 {vraw}")
            n.patch(MAINS, "V4 N004 N005 0 Rser=0.1")
        if self.dummy_load:
            for line in SPEAKER_MODEL:
                n.patch(line + "\n", "")
            n.patch(R_LOAD, "R27 0 SPEAKER 7.5")
            if load_cap:                     # prueba de tortura de estabilidad
                n.add(f"C_LOAD SPEAKER 0 {load_cap}")
        n.patch(RV2, RV2.replace("wiper=.037",
                                 f"wiper={self.rv2 if rv2 is None else rv2}"))
        n.patch(RV1, RV1.replace("wiper=.54",
                                 f"wiper={self.rv1 if rv1 is None else rv1}"))
        for mode, leg, (cr, ret, ret_gnd, rname) in (
                (self.clip[0], POS_LEG, POS_BIAS),
                (self.clip[1], NEG_LEG, NEG_BIAS)):
            if mode == "open":
                for line in (*leg, *cr):        # los diodos Y su C||R
                    n.patch(line + "\n", "")
            elif mode == "gnd":
                for line in cr:                 # fuera el bias
                    n.patch(line + "\n", "")
                n.patch(ret, ret_gnd)           # y el retorno, a masa
            elif self.clip_r != "2k2":          # bias con otro release
                r = next(x for x in cr if x.startswith(rname))
                n.patch(r, r.replace(" 2k2", f" {self.clip_r}"))
        if self.clip_bridge and self.clip == ("bias", "bias"):
            # las dos a masa fuera, una sola entre los condensadores
            for cr in (POS_BIAS[0], NEG_BIAS[0]):
                n.patch(cr[1] + "\n", "")
            n.add(f"R_CLIPX N024 N026 {self.clip_bridge}")
        for k, v in (params or {}).items():
            # el netlist YA declara drive/bass/treble/vol/in_amplitude, asi que
            # hay que sustituir la linea; anadir otra es "Duplicate definitions"
            n.drop_re(rf"\s*\.param\s+{k}\b", 1)
            n.add(f".param {k}={v}")
        return n

    # -------------------------------------------------------------------- .op
    def op(self, tag="op", **kw) -> dict:
        n = self._base(**kw).patch(TRAN, ".op")
        log = run_batch(n.write(self.w / f"{tag}.net")).with_suffix(".log")
        txt = read_log(log)
        out = {}
        for m in re.finditer(r"^([VI])\((\w+)\):?\s+([-\d.eE+]+)", txt, re.M):
            out[f"{m.group(1).lower()}({m.group(2).lower()})"] = float(m.group(3))
        if not out:
            raise RuntimeError(f"el .op de {tag} no devolvio nada: {log}")
        return out

    # ------------------------------------------------------------------ .tran
    def tran(self, tag, src, tstop, maxstep="1u", tstart=0.0, extra=(),
             inject=None, **kw):
        """Simula y devuelve (t, dict de senales).  `src` sustituye a V6."""
        n = self._base(**kw)
        n.patch(VSRC, src)
        if inject:
            inject_power_stage(n, inject)
        n.patch(TRAN, f".tran 0 {tstop} {tstart} {maxstep}")
        n.save_vars(*SAVE)
        if not self.mains:
            n.save_vars("I(V_RAW)")
        if extra:
            n.add(*extra)
        names, d = read_raw(run_batch(n.write(self.w / f"{tag}.net")))
        low = {k.lower(): v for k, v in d.items()}
        return low[names[0].lower()], low


def sine(amp, freq, node="PICKUP_IN"):
    return f"V6 {node} 0 SINE(0 {amp} {freq})"


def burst(amp, freq, t1, t2, node="PICKUP_IN"):
    """Rafaga: silencio, tono, silencio.  Hace falta una fuente behavioural."""
    return (f"B6 {node} 0 V=if(time>{t1} & time<{t2}, "
            f"{amp}*sin(2*pi*{freq}*time), 0)")


def square(amp, freq, node="PICKUP_IN", edge="100n"):
    per = 1.0 / freq
    return (f"V6 {node} 0 PULSE({-amp} {amp} 0 {edge} {edge} "
            f"{per/2:.9g} {per:.9g})")


def inject_power_stage(n: Netlist, spec: str):
    """Mete una fuente en SERIE con C1, a la entrada de la etapa de potencia.

    Para probar la estabilidad hay que atacar el lazo de potencia directamente:
    si se entra por la guitarra, la tone stack redondea el flanco y lo que se
    mide es la stack, no el margen de fase.  Poniendo la fuente en serie con el
    condensador de acoplo, el preamp sigue viendo su carga y su polarizacion.
    """
    n.patch(C1, "C1 N017 NINJ 1u")
    n.add(f"V_INJ NINJ PREAMP_OUT {spec}")
    return n


# ---------------------------------------------------------------- los trimmers
def solve_wiper(b: Bench, kind, probe, target, tol=2e-4, iters=20):
    """Biseccion sobre el cursor de un trimmer.

    Devuelve (cursor, valor) o (None, (extremo_lo, extremo_hi)) si el objetivo
    no esta dentro del rango del trimmer, que seria un hallazgo de diseno y no
    un fallo del script.  El sentido se deduce de los extremos, no se supone.
    """
    f = lambda w: probe(b.op(f"sv_{kind}", **{kind: round(w, 6)}))  # noqa: E731
    lo, hi = 0.0, 1.0
    flo, fhi = f(lo), f(hi)
    if (flo - target) * (fhi - target) > 0:
        return None, (flo, fhi)
    for _ in range(iters):
        if hi - lo < tol:
            break
        mid = 0.5 * (lo + hi)
        fm = f(mid)
        if (flo - target) * (fm - target) <= 0:
            hi, fhi = mid, fm
        else:
            lo, flo = mid, fm
    w = 0.5 * (lo + hi)
    return w, f(w)


def iq_ma(o):
    return o["i(r16)"] * 1000.0


def offset(o, vraw):
    return o["v(pre_speaker)"] - vraw / 2.0


def case_trim(b: Bench, plot=False, out=None):
    print("== Los dos trimmers: reposo y centrado de salida ==")
    print("   El esquematico pide 40 mA por R16/R17 (RV2) y la salida en")
    print("   VRAW/2 (RV1).  Se resuelve con .op, no con .tran: con el rail")
    print("   firme el punto de operacion ES el estado estacionario, y cuesta")
    print("   0.15 s en vez de 64 s.\n")

    o0 = b.op("as_drawn", rv1=RV1_AS_DRAWN, rv2=RV2_AS_DRAWN)
    print(f"   Tal como esta dibujado (RV2={RV2_AS_DRAWN:g}, RV1={RV1_AS_DRAWN:g}):")
    print(f"     I(R16) = {o0['i(r16)']*1000:6.2f} mA     "
          f"I(R17) = {o0['i(r17)']*1000:6.2f} mA")
    print(f"     salida = {o0['v(pre_speaker)']:6.3f} V      "
          f"offset = {offset(o0, b.vraw)*1000:+7.1f} mV")
    print(f"     La medida anterior de 762 mA era senal, no reposo: el .op no")
    print(f"     tiene senal por definicion.\n")
    print("   R16 y R17 NO son iguales, y no es un error: por R14 (56 ohm, de")
    print("   la base de Q6 a la salida) se cuelan ~10 mA que entran en el nodo")
    print("   sin pasar por R16.  El reposo del par de salida es el de R16.\n")

    # dos pasadas: los dos lazos interactuan debilmente
    rv2, iq = solve_wiper(b, "rv2", iq_ma, IQ_TARGET_MA)
    if rv2 is None:
        print(f"   RV2: los 40 mA NO son alcanzables.  El trimmer va de "
              f"{iq[0]:.1f} a {iq[1]:.1f} mA.  Es el RANGO lo que esta mal.")
    else:
        b.rv2 = rv2
        rv1, off = solve_wiper(b, "rv1", lambda o: offset(o, b.vraw), 0.0)
        if rv1 is not None:
            b.rv1 = rv1
        rv2, iq = solve_wiper(b, "rv2", iq_ma, IQ_TARGET_MA)
        b.rv2 = rv2
        o1 = b.op("solved")
        print(f"   Resuelto:  RV2 = {b.rv2:.4f}  ({b.rv2*100:.2f} % de giro)"
              f"   -> I(R16) = {o1['i(r16)']*1000:.2f} mA")
        print(f"              RV1 = {b.rv1:.4f}  ({b.rv1*100:.2f} % de giro)"
              f"   -> offset  = {offset(o1, b.vraw)*1000:+.1f} mV")
        d2 = (iq_ma(b.op("s2", rv2=b.rv2 + 0.01))
              - iq_ma(b.op("s2", rv2=b.rv2 - 0.01))) / 2.0
        d1 = (offset(b.op("s1", rv1=b.rv1 + 0.01), b.vraw)
              - offset(b.op("s1", rv1=b.rv1 - 0.01), b.vraw)) / 2.0 * 1000
        print(f"\n   Sensibilidad en el punto de ajuste, que es lo que se nota")
        print(f"   en el banco al girar el trimmer:")
        print(f"     RV2: {d2:+.2f} mA por cada 1 % de giro")
        print(f"     RV1: {d1:+.1f} mV por cada 1 % de giro")
        print(f"\n   Movimiento respecto a lo dibujado: RV2 "
              f"{(b.rv2-RV2_AS_DRAWN)*100:+.2f} puntos, RV1 "
              f"{(b.rv1-RV1_AS_DRAWN)*100:+.2f} puntos.")

    # --- barridos, para ver el rango y la pendiente
    ws = [i / 20 for i in range(21)]
    cur = {"rv2": [(w, iq_ma(b.op("sw2", rv2=w))) for w in ws],
           "rv1": [(w, offset(b.op("sw1", rv1=w), b.vraw) * 1000) for w in ws]}
    r2 = [v for _, v in cur["rv2"]]
    r1 = [v for _, v in cur["rv1"]]
    print(f"\n   Rango de RV2: {min(r2):.1f} .. {max(r2):.1f} mA"
          f"   (objetivo {IQ_TARGET_MA:.0f} mA "
          f"{'DENTRO' if min(r2) <= IQ_TARGET_MA <= max(r2) else 'FUERA'})")
    print(f"   Rango de RV1: {min(r1):+.0f} .. {max(r1):+.0f} mV"
          f"   (objetivo 0 mV "
          f"{'DENTRO' if min(r1) <= 0 <= max(r1) else 'FUERA'})")

    # --- verificacion: el .op y el .tran tienen que dar el mismo reposo
    t, d = b.tran("verify_iq", "V6 PICKUP_IN 0 0", "40m", maxstep="10u")
    m = t > 30e-3
    iq_tran = float(np.mean(d["i(r16)"][m])) * 1000
    o1 = b.op("solved")
    print(f"\n   Verificacion .op vs .tran (entrada a cero, ventana 30-40 ms):")
    print(f"     .op {o1['i(r16)']*1000:.3f} mA   .tran {iq_tran:.3f} mA   "
          f"{abs(iq_tran - o1['i(r16)']*1000):.3f} mA de diferencia"
          f"{'   OK' if abs(iq_tran - o1['i(r16)']*1000) < 0.5 else '   <-- OJO'}")
    if plot and out:
        # barrido fino donde pasan las cosas: con 21 puntos de 0 a 1 caen tres
        # dentro del margen util de RV2 y la figura no dice nada
        fine = {
            "rv2": [(w, iq_ma(b.op("fw2", rv2=w)))
                    for w in (i * 0.12 / 40 for i in range(41))],
            "rv1": [(w, offset(b.op("fw1", rv1=w), b.vraw) * 1000)
                    for w in (0.45 + i * 0.2 / 40 for i in range(41))],
        }
        _plot_trim(fine, b, out)
    return cur


# --------------------------------------------------------- potencia y recorte
LEVELS = (0.003, 0.006, 0.012, 0.025, 0.05, 0.1, 0.2, 0.35, 0.5, 0.75, 1.1)
R_SPK = 7.5


def _sweep_level(b: Bench, levels=LEVELS, freq=1000.0, tstop="80m",
                 maxstep="2u", cycles=10):
    """Barrido de nivel a 1 kHz.  Devuelve una lista de dicts por punto.

    La ventana es larga a proposito: con recorte asimetrico aparece una
    componente de continua que carga C10 (3300 uF con 7.5 ohm = 25 ms de
    constante), y hasta que no se asienta la forma de onda no es la definitiva.
    """
    out = []
    for a in levels:
        t, d = b.tran(f"lv{a:g}", sine(a, freq), tstop, maxstep=maxstep,
                      extra=(TOL,))
        v = d["v(speaker)"]
        _, seg = uniform(t, v, freq, cycles)
        seg = seg - float(np.mean(seg))
        _, irail = uniform(t, np.abs(d["i(v_raw)"]), freq, cycles)
        fund, hs, thd = harmonics(t, v, freq, cycles=cycles)
        out.append(dict(a=a, fund=fund, hs=hs, thd=thd * 100,
                        vrms=rms(seg), pout=rms(seg) ** 2 / R_SPK,
                        vmax=float(seg.max()), vmin=float(seg.min()),
                        irail=float(np.mean(irail))))
    return out


def _at_thd(pts, target):
    """Potencia interpolada donde la THD cruza `target` %, en log-log."""
    for p, q in zip(pts, pts[1:]):
        if p["thd"] <= target <= q["thd"] and p["pout"] > 0:
            f = ((math.log10(target) - math.log10(p["thd"]))
                 / (math.log10(q["thd"]) - math.log10(p["thd"])))
            return 10 ** (math.log10(p["pout"])
                          + f * (math.log10(q["pout"]) - math.log10(p["pout"])))
    return None


def case_power(b: Bench, plot=False, out=None):
    print("== Potencia, recorte y THD contra nivel ==")
    print(f"   1 kHz sobre {R_SPK} ohm resistivos, potes al 50 %, drive 0.")
    print(f"   Suelo numerico de la THD: {THD_FLOOR:.4f} % (lo pone reltol).")
    print(f"   Por debajo de ~0.01 % no hay que creerse el numero.\n")
    pts = _sweep_level(b)
    print(f"   {'Vin':>8}{'Vout pico':>11}{'Vrms':>9}{'Pout':>10}"
          f"{'THD':>10}{'+pico':>9}{'-pico':>9}{'simetria':>10}")
    for p in pts:
        sym = abs(p["vmax"] / p["vmin"]) if p["vmin"] else float("nan")
        flag = "  <-- suelo" if p["thd"] < THD_FLOOR * 3 else ""
        print(f"   {p['a']*1000:6.0f}mV{p['fund']:10.2f}V{p['vrms']:8.2f}V"
              f"{p['pout']:9.2f}W{p['thd']:9.3f}%{p['vmax']:+8.2f}V"
              f"{p['vmin']:+8.2f}V{sym:9.3f}{flag}")

    p1, p10 = _at_thd(pts, 1.0), _at_thd(pts, 10.0)
    print()
    print(f"   Potencia al  1 % de THD: "
          f"{f'{p1:.1f} W' if p1 else 'fuera del barrido'}")
    print(f"   Potencia al 10 % de THD: "
          f"{f'{p10:.1f} W' if p10 else 'fuera del barrido'}   "
          f"(el 10 % es el criterio con el que se anuncian los amplis)")
    top = pts[-1]
    teor = b.vraw / 2 - 3.5
    print(f"\n   Techo de recorte: {top['vmax']:+.2f} / {top['vmin']:+.2f} V "
          f"contra {teor:+.1f} V teoricos (VRAW/2 menos 3.5 V de perdidas)")
    print(f"   Asimetria de recorte: {abs(top['vmax']/top['vmin']):.3f} "
          f"({100*(abs(top['vmax']/top['vmin'])-1):+.1f} %).  Un recorte "
          f"asimetrico genera armonicos PARES,")
    print(f"   que es justo lo que se le pide a un ampli de guitarra.")
    pin = b.vraw * top["irail"]
    print(f"\n   Rendimiento en el punto mas alto: {top['pout']:.1f} W de salida "
          f"contra {pin:.1f} W del rail = {100*top['pout']/pin:.0f} %"
          f"   (maximo teorico de clase AB: 78.5 %)")
    if plot and out:
        _plot_power(pts, out)
    return pts


# ------------------------------------------------- quien distorsiona, y como
DRIVES = (0.0, 0.25, 0.5, 0.75, 1.0)


def case_distortion(b: Bench, plot=False, out=None):
    print("== Quien distorsiona: el recortador del preamp o la etapa de potencia ==")
    print("   100 mVp a 1 kHz (el in_amplitude del esquematico), potes al 50 %.")
    print("   La THD se mide en tres sitios de la cadena, asi que se ve DONDE")
    print("   nace cada punto de distorsion.\n")
    print(f"   {'drive':>7}{'TONE_IN':>10}{'PREAMP_OUT':>13}{'SPEAKER':>11}"
          f"{'Vout pico':>12}{'ganancia':>11}")
    prof = []
    for dv in DRIVES:
        t, d = b.tran(f"dr{dv:g}", sine(0.1, 1000), "80m", maxstep="2u",
                      extra=(TOL,), params={"drive": dv})
        r = {}
        for node in ("tone_in", "preamp_out", "speaker"):
            r[node] = harmonics(t, d[f"v({node})"], 1000.0, cycles=10)
        fund = r["speaker"][0]
        print(f"   {dv*100:5.0f}%{r['tone_in'][2]*100:9.3f}%"
              f"{r['preamp_out'][2]*100:12.3f}%{r['speaker'][2]*100:10.3f}%"
              f"{fund:11.2f}V{20*math.log10(fund/0.1):10.1f}dB")
        prof.append((dv, r["speaker"][1], fund))

    print("\n   Perfil de armonicos en el altavoz, en dB bajo el fundamental.")
    print("   H2/H3 es lo que decide el caracter: si domina el par, calido; si")
    print("   domina el impar, aspero.")
    print(f"   {'drive':>7}{'H2':>9}{'H3':>9}{'H4':>9}{'H5':>9}{'H2/H3':>10}")
    for dv, hs, fund in prof:
        db_ = [20 * math.log10(max(h, 1e-12) / hs[0]) for h in hs[:5]]
        ratio = hs[1] / hs[2] if hs[2] > 0 else float("inf")
        print(f"   {dv*100:5.0f}%" + "".join(f"{x:8.1f}dB" for x in db_[1:5])
              + f"{ratio:10.2f}")

    # --- IMD de dos tonos.  82.5 y 1320 Hz comparten periodo (1320 = 16 x 82.5),
    #     asi que una ventana de N periodos de 82.5 Hz contiene periodos enteros
    #     de los dos y no hay desparramo.
    f1, f2, cyc = 82.5, 1320.0, 10
    src = (f"B6 PICKUP_IN 0 V=0.05*(sin(2*pi*{f1}*time)+sin(2*pi*{f2}*time))")
    t, d = b.tran("imd", src, "200m", maxstep="2u", extra=(TOL,))
    amp = spectrum(t, d["v(speaker)"], f1, cyc, n=1 << 14)
    k2 = int(round(f2 / (f1 / cyc)))
    d1 = int(round(f1 / (f1 / cyc)))
    carrier = amp[k2]
    side = [amp[k2 + s * d1] for s in (-2, -1, 1, 2)]
    imd = math.sqrt(sum(x * x for x in side)) / carrier * 100
    print(f"\n   IMD de dos tonos, {f1:g} Hz + {f2:g} Hz a partes iguales")
    print(f"   (mi bajo y mi agudo de la guitarra; para acordes dice mas que la THD):")
    print(f"     portadora de {f2:g} Hz: {carrier:.4f} V")
    for s, v in zip((-2, -1, 1, 2), side):
        print(f"     {f2 + s*f1:7.1f} Hz: {v:.6f} V  "
              f"({20*math.log10(max(v,1e-12)/carrier):+6.1f} dB)")
    print(f"     IMD total = {imd:.3f} %")
    if plot and out:
        _plot_harmonics(prof, out)
    return prof


# -------------------------------------------------------- estabilidad al escalon
def edge_metrics(t, y, t_edge, half):
    """Metricas de un flanco de subida que empieza en `t_edge`.

    El nivel de llegada se toma de una ventana FIJA de 25-45 us tras el flanco,
    no de una fraccion de la meseta.  Si se toma al final de la meseta, a 1 kHz
    el condensador de salida (3300 uF) ya ha caido y el sobrepico sale inflado:
    medido asi daba 3.2 % a 1 kHz contra 0.1 % a 10 kHz, y no era el ampli, era
    la ventana.
    """
    a0, a1 = min(0.5 * half, 25e-6), min(0.9 * half, 45e-6)
    pre = (t > t_edge - half * 0.3) & (t < t_edge - half * 0.02)
    post = (t > t_edge + a0) & (t < t_edge + a1)
    lo, hi = float(np.mean(y[pre])), float(np.mean(y[post]))
    span = hi - lo
    seg = (t >= t_edge) & (t <= t_edge + half)
    ts, ys = t[seg], y[seg]

    def cross(frac):
        lvl = lo + span * frac
        k = np.argmax(ys >= lvl) if span > 0 else np.argmax(ys <= lvl)
        return float(ts[k])

    t10, t90 = cross(0.1), cross(0.9)
    slew = float(np.max(np.abs(np.diff(ys) / np.diff(ts))))
    peak = float(np.max(ys))
    over = 100.0 * (peak - hi) / span if span else float("nan")
    # frecuencia del rizado: cruces por cero del residuo tras el pico
    after = ts > ts[int(np.argmax(ys))]
    r = ys[after] - hi
    zc = np.where(np.diff(np.sign(r)))[0]
    fring = (0.5 / np.mean(np.diff(ts[after][zc]))
             if len(zc) > 2 else float("nan"))
    return dict(lo=lo, hi=hi, span=span, tr=t90 - t10, slew=slew / 1e6,
                over=over, fring=fring)


def case_stability(b: Bench, plot=False, out=None):
    print("== Estabilidad: respuesta al escalon ==")
    print("   La cuadrada se inyecta EN SERIE con C1, o sea a la entrada de la")
    print("   etapa de potencia.  Si se entra por la guitarra, la tone stack")
    print("   redondea el flanco y se mide la stack, no el margen de fase.")
    print("   Las cargas capacitivas son la prueba de tortura: cuanto mas")
    print("   sobrepico anaden, menos margen de fase queda.\n")
    print(f"   {'carga':>14}{'f':>8}{'salida':>10}{'subida':>10}"
          f"{'slew rate':>13}{'sobrepico':>12}{'rizado':>11}")
    traces = []
    # 2.2 nF es el valor de tortura de un operacional; sobre 7.5 ohm no carga
    # nada (72 ohm de reactancia a 1 MHz).  Para una etapa de potencia los
    # valores clasicos son cientos de nF y microfaradios.
    for cap, lbl in ((None, "7.5 ohm"), ("0.22u", "7.5R || 220nF"),
                     ("2.2u", "7.5R || 2.2uF")):
        for f in (1000.0, 10000.0):
            per = 1.0 / f
            # amplitud moderada a proposito: con 0.35 V el pico positivo se
            # acercaba al techo de recorte y el sobrepico salia contaminado
            spec = (f"PULSE(-0.15 0.15 0 100n 100n {per/2:.9g} {per:.9g})")
            t, d = b.tran(f"sq{lbl[:3]}{f:g}", "V6 PICKUP_IN 0 0",
                          f"{5*per:.9g}", maxstep=f"{per/4000:.9g}",
                          inject=spec, load_cap=cap, extra=(TOL,))
            m = edge_metrics(t, d["v(speaker)"], 3 * per, per / 2)
            print(f"   {lbl:>14}{f/1000:6.0f}k{m['span']:9.2f}V"
                  f"{m['tr']*1e6:9.2f}us{m['slew']:11.2f}V/us"
                  f"{m['over']:11.1f}%"
                  + (f"{m['fring']/1e3:8.0f}kHz" if np.isfinite(m["fring"])
                     else f"{'sin':>12}"))
            traces.append((lbl, f, t, d["v(speaker)"], m))
    print("\n   Un sobrepico creciente al meter el condensador es la senal de")
    print("   margen de fase escaso: la carga capacitiva anade retardo dentro")
    print("   del lazo.  Sin oscilacion mantenida, el ampli es estable.")
    if plot and out:
        _plot_square(traces, out)
    return traces


# ------------------------------------------------------- sag y zumbido de red
def case_supply(b: Bench, plot=False, out=None):
    print("== Sag del rail y zumbido, con la fuente REAL ==")
    print("   Aqui NO vale el rail ideal: el sag sale de R22 (15 ohm de")
    print("   primario), R23 (0.5 ohm de secundario) y los 10000 uF de C13.")
    print("   Por eso este caso paga los 4 s de carga del deposito.\n")
    rb = Bench(b.w, rv1=b.rv1, rv2=b.rv2, mains=True, dummy_load=True)
    t1, t2 = 4.0, 4.3
    # la rafaga tiene que RECORTAR: si el ampli va holgado, el rail puede caer
    # sin que la salida se entere y no se ve compresion ninguna.  1.1 Vp es el
    # nivel al que el barrido de potencia ya daba recorte franco.
    t, d = rb.tran("sag", burst(1.1, 1000.0, t1, t2), "4.6", maxstep="20u",
                   tstart="3.75")
    rail, spk = d["v(n002)"], d["v(speaker)"]

    def mean_win(a, bnd, y=None):
        """Media en una ventana.  El rail lleva varios voltios de rizado a
        100 Hz, asi que muestrearlo en un instante no dice nada: hay que
        promediar un numero entero de ciclos."""
        y = rail if y is None else y
        m = (t >= a) & (t <= bnd)
        return float(np.mean(y[m]))

    win = (t > t1) & (t < t2)
    v_idle = mean_win(t1 - 0.04, t1 - 0.005)
    v_min = float(rail[win].min())
    v_end = mean_win(t2 - 0.04, t2 - 0.005)
    print(f"   Rail en reposo antes de la rafaga:  {v_idle:6.2f} V   "
          f"(media de 2 ciclos de rizado, no un instante)")
    print(f"   Minimo instantaneo en la rafaga:    {v_min:6.2f} V   "
          f"({v_min - v_idle:+.2f} V)")
    print(f"   Media al final de la rafaga:        {v_end:6.2f} V   "
          f"({v_end - v_idle:+.2f} V de sag)")
    v_fin, dt_fin = mean_win(4.56, 4.58), 4.57 - t2
    frac = (v_fin - v_end) / (v_idle - v_end) if v_idle != v_end else 1.0
    tau = -dt_fin / math.log(max(1 - frac, 1e-6)) if frac < 1 else 0.0
    print(f"   Recuperacion: {frac*100:.0f} % en {dt_fin*1000:.0f} ms"
          f"  ->  constante de tiempo ~{tau*1000:.0f} ms")
    print(f"   Recuperar cuesta MUCHO mas que caer.  Tocando seguido el rail no")
    print(f"   vuelve arriba entre notas, asi que el sag no es un efecto de")
    print(f"   ataque: es un estado en el que se queda el amplificador.")

    def env(a, bnd):
        _, seg = uniform(t, spk, 1000.0, int((bnd - a) * 1000), t_end=bnd)
        return float(np.max(np.abs(seg - np.mean(seg))))
    # las dos ventanas evitan el arranque de la rafaga: lo que se compara es
    # regimen contra regimen, no el transitorio de ataque
    e0, e1 = env(t1 + 0.03, t1 + 0.06), env(t2 - 0.06, t2 - 0.03)
    print(f"\n   Salida en recorte al empezar la rafaga: {e0:.2f} V pico")
    print(f"   Al final, con el rail caido:            {e1:.2f} V pico"
          f"   ({20*math.log10(e1/e0):+.2f} dB)")
    print(f"   El techo de recorte lo pone el rail, asi que el sag se traduce")
    print(f"   directo en compresion.  Es el tacto tipico de un ampli con una")
    print(f"   fuente blanda, y aqui son {v_idle - v_end:.1f} V de caida.")

    hum_idle = spectrum(t, spk, 50.0, 10, t_end=t1 - 0.005)
    hum_load = spectrum(t, spk, 50.0, 10, t_end=t2 - 0.005)
    print(f"\n   Zumbido de 100 Hz en el altavoz:")
    print(f"     en reposo:        {hum_idle[20]*1000:8.3f} mV")
    print(f"     a plena potencia: {hum_load[20]*1000:8.3f} mV"
          f"   ({20*math.log10(hum_load[20]/max(hum_idle[20],1e-12)):+.1f} dB)")
    print(f"   Medirlo en reposo no vale de nada: el rizado del deposito crece")
    print(f"   con la corriente, asi que el zumbido peor es el de plena carga.")
    if abs(v_idle - VRAW_DC) > 0.5:
        print(f"\n   AVISO: el rail real en reposo son {v_idle:.2f} V, y el modo")
        print(f"   banco usa VRAW_DC = {VRAW_DC:.2f} V.  Son {v_idle-VRAW_DC:+.2f} V,")
        print(f"   o sea {abs(v_idle-VRAW_DC)/2:.2f} V de techo de recorte que los")
        print(f"   demas casos NO estan contando.  Pasa --vraw {v_idle:.2f} para")
        print(f"   cuadrarlos.")
    if plot and out:
        _plot_sag(t, rail, spk, t1, t2, out)
    return t, rail, spk


# --------------------------------------------------------------------- figuras
PAL = dict(bg="#ffffff", ink="#14181f", muted="#5a626f",
           grid="#ccd2dc", minor="#e8ebf0", frame="#8d95a3")
SER = ("#3a5199", "#a83a34", "#5d8a3e", "#b5762a", "#2f7f96")

STYLE = """
.h1{{font:600 21px "IBM Plex Sans Condensed","IBM Plex Sans",sans-serif;fill:{ink}}}
.cond{{font:400 12px "IBM Plex Mono",ui-monospace,monospace;fill:{muted};letter-spacing:.06em}}
.tick{{font:400 13px "IBM Plex Mono",ui-monospace,monospace;fill:{muted};font-variant-numeric:tabular-nums}}
.axl{{font:500 12px "IBM Plex Mono",ui-monospace,monospace;fill:{ink};letter-spacing:.12em}}
.lgv{{font:400 12px "IBM Plex Mono",ui-monospace,monospace;fill:{ink}}}
.ann{{font:400 12px "IBM Plex Sans",system-ui,sans-serif;fill:{muted};
  paint-order:stroke;stroke:{bg};stroke-width:4px;stroke-linejoin:round}}
"""


def _svg(w, h, title, cond, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'width="100%" style="display:block;width:100%;height:auto">'
            f'<style>{STYLE.format(**PAL)}</style>'
            f'<text x="70" y="34" class="h1">{title}</text>'
            f'<text x="70" y="56" class="cond">{cond}</text>'
            f'{body}</svg>')


def _emit(svg, name, w, h, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}.svg").write_text(svg, encoding="utf-8")
    rasterize(svg, out / f"{name}.png", w, h)
    print(f"   -> {out / f'{name}.png'}")


def _axlabels(ax, xl, yl):
    cy = ax.y0 + ax.h / 2
    return (f'<text x="{ax.x0+ax.w/2:.0f}" y="{ax.y0+ax.h+48}" class="axl" '
            f'text-anchor="middle">{xl}</text>'
            f'<text x="{ax.x0-52:.0f}" y="{cy:.0f}" class="axl" '
            f'text-anchor="middle" transform="rotate(-90 {ax.x0-52:.0f} '
            f'{cy:.0f})">{yl}</text>')


def _plot_trim(cur, b, out: Path):
    w, h = 1240, 470
    body = []
    for k, (key, xlim, ylim, ystep, xl, yl, tgt, sol) in enumerate((
            ("rv2", (0, 0.12), (0, 100), 10, "RV2 WIPER (fraction)",
             "I(R16) (mA)", IQ_TARGET_MA, b.rv2),
            ("rv1", (0.45, 0.65), (-3000, 3000), 500, "RV1 WIPER (fraction)",
             "OUTPUT OFFSET (mV)", 0.0, b.rv1))):
        ax = Ax(110 + k * 600, 92, 460, 300, xlim, ylim)
        xs = [x for x, _ in cur[key]]
        ys = [y for _, y in cur[key]]
        body.append(grid(ax, PAL, linear_ticks(
            ax, (xlim[1] - xlim[0]) / 4, (xlim[1] - xlim[0]) / 20,
            fmt=lambda v: f"{v:.3g}"), ystep=ystep, ymajor=ystep,
            yfmt=lambda v: f"{v:g}"))
        body.append(f'<line x1="{ax.x0}" y1="{ax.y(tgt):.1f}" '
                    f'x2="{ax.x0+ax.w}" y2="{ax.y(tgt):.1f}" stroke="{SER[1]}" '
                    f'stroke-dasharray="4 3"/>')
        body.append(f'<path d="{ax.path(xs, ys)}" fill="none" stroke="{SER[0]}" '
                    f'stroke-width="2.2"/>')
        if xlim[0] <= sol <= xlim[1]:
            body.append(f'<line x1="{ax.x(sol):.1f}" y1="{ax.y0}" '
                        f'x2="{ax.x(sol):.1f}" y2="{ax.y0+ax.h}" '
                        f'stroke="{SER[1]}" stroke-dasharray="4 3"/>')
            body.append(f'<circle cx="{ax.x(sol):.1f}" cy="{ax.y(tgt):.1f}" '
                        f'r="4" fill="{SER[1]}"/>')
            body.append(f'<text x="{ax.x(sol)+8:.0f}" y="{ax.y0+20:.0f}" '
                        f'class="ann">setpoint = {sol:.4f}</text>')
        body.append(frame(ax, PAL) + _axlabels(ax, xl, yl))
    _emit(_svg(w, h, "Trimmer adjustment: quiescent current and output offset",
               "DC OPERATING POINT &#183; ZERO INPUT &#183; 7.5 &#937; LOAD",
               "".join(body)), "trim", w, h, out)


def _plot_power(pts, out: Path):
    w, h = 1240, 560
    ax = Ax(110, 92, 1060, 390, (0.001, 40), (-4, 2), xlog=True)   # y = log10(THD)
    body = [grid(ax, PAL, decade_ticks(ax, fmt=lambda v: f"{v:g}"),
                 ystep=1, ymajor=1,
                 yfmt=lambda v: f"{10**v:g}")]
    xs = [p["pout"] for p in pts if p["pout"] > 0]
    ys = [math.log10(max(p["thd"], 1e-4)) for p in pts if p["pout"] > 0]
    body.append(f'<path d="{ax.path(xs, ys)}" fill="none" stroke="{SER[0]}" '
                f'stroke-width="2.4" stroke-linejoin="round"/>')
    for x, y in zip(xs, ys):
        body.append(f'<circle cx="{ax.x(x):.1f}" cy="{ax.y(y):.1f}" r="3.2" '
                    f'fill="{SER[0]}"/>')
    for lvl, lbl in ((1.0, "1 %"), (10.0, "10 %")):
        yy = ax.y(math.log10(lvl))
        body.append(f'<line x1="{ax.x0}" y1="{yy:.1f}" x2="{ax.x0+ax.w}" '
                    f'y2="{yy:.1f}" stroke="{SER[1]}" stroke-dasharray="4 3"/>')
        p = _at_thd(pts, lvl)
        if p:
            body.append(f'<circle cx="{ax.x(p):.1f}" cy="{yy:.1f}" r="4" '
                        f'fill="{SER[1]}"/>')
            body.append(f'<text x="{ax.x(p):.0f}" y="{yy-10:.0f}" class="ann" '
                        f'text-anchor="middle">{p:.1f} W at {lbl}</text>')
    floor = ax.y(math.log10(THD_FLOOR))
    body.append(f'<line x1="{ax.x0}" y1="{floor:.1f}" x2="{ax.x0+ax.w}" '
                f'y2="{floor:.1f}" stroke="{PAL["muted"]}" '
                f'stroke-dasharray="2 4"/>')
    body.append(f'<text x="{ax.x0+8:.0f}" y="{floor-8:.0f}" class="ann">'
                f'numerical floor of the simulation ({THD_FLOOR:.4f} %)</text>')
    body.append(frame(ax, PAL) + _axlabels(ax, "OUTPUT POWER (W)", "THD (%)"))
    _emit(_svg(w, h, "Distortion versus output power",
               "1 kHz &#183; 7.5 &#937; RESISTIVE &#183; TONE CONTROLS AT 50% "
               "&#183; DRIVE 0%", "".join(body)), "thd_vs_power", w, h, out)


def _plot_harmonics(prof, out: Path):
    w, h = 1240, 500
    ax = Ax(110, 92, 1060, 330, (-0.5, len(prof) * 6 - 0.5), (-100, 0))
    body = [grid(ax, PAL, [], ystep=10, ymajor=20, yfmt=lambda v: f"{v:g}")]
    for i, (dv, hs, _) in enumerate(prof):
        for k in range(1, 5):
            db_ = 20 * math.log10(max(hs[k], 1e-12) / hs[0])
            x0 = ax.x(i * 6 + k - 1) - 14
            body.append(f'<rect x="{x0:.1f}" y="{ax.y(db_):.1f}" width="28" '
                        f'height="{ax.y0+ax.h-ax.y(db_):.1f}" '
                        f'fill="{SER[(k-1) % len(SER)]}" fill-opacity="0.85"/>')
            body.append(f'<text x="{x0+14:.0f}" y="{ax.y(db_)-6:.0f}" '
                        f'class="ann" text-anchor="middle">H{k+1}</text>')
        body.append(f'<text x="{ax.x(i*6+1.5):.0f}" y="{ax.y0+ax.h+24:.0f}" '
                    f'class="tick" text-anchor="middle">drive {dv*100:.0f}%</text>')
    body.append(frame(ax, PAL)
                + _axlabels(ax, "", "HARMONIC LEVEL (dB re fundamental)"))
    _emit(_svg(w, h, "Harmonic profile versus drive",
               "1 kHz &#183; 100 mVp INPUT &#183; MEASURED AT THE SPEAKER NODE",
               "".join(body)), "harmonics", w, h, out)


def _plot_square(traces, out: Path):
    w, h = 1240, 530
    body, n = [], 3
    for i, (lbl, f, t, y, m) in enumerate([x for x in traces if x[1] == 1000.0]):
        per = 1.0 / f
        t0 = 3 * per - per * 0.1
        # El .op de una PULSE usa V1, no la media, asi que al arrancar la
        # cuadrada el condensador de salida (3300 uF, 25 ms) se pasa varios ms
        # cargandose y los dos niveles no salen simetricos respecto a cero.
        # No afecta a las medidas (todas son locales al flanco), pero para la
        # figura hay que centrar el trazo en su propio nivel medio.
        mid = (m["lo"] + m["hi"]) / 2
        lim = max(8.0, m["span"] * 0.75)
        ax = Ax(110 + i * 380, 110, 300, 300, (0, per * 0.6), (-lim, lim))
        sel = (t >= t0) & (t <= t0 + per * 0.6)
        body.append(grid(ax, PAL, linear_ticks(
            ax, per * 0.2, per * 0.05, fmt=lambda v: f"{v*1e6:.0f}"),
            ystep=2, ymajor=4, yfmt=lambda v: f"{v:g}"))
        body.append(f'<path d="{ax.path(t[sel]-t0, y[sel]-mid)}" fill="none" '
                    f'stroke="{SER[0]}" stroke-width="1.8"/>')
        body.append(frame(ax, PAL))
        body.append(f'<text x="{ax.x0+6}" y="{ax.y0-10}" class="lgv">{lbl}</text>')
        body.append(f'<text x="{ax.x0+6}" y="{ax.y0+ax.h+48}" class="ann">'
                    f'{m["tr"]*1e6:.2f} us &#183; {m["slew"]:.2f} V/us '
                    f'&#183; {m["over"]:.1f} % overshoot</text>')
        if i == 0:
            body.append(_axlabels(ax, "", "OUTPUT (V, AC-COUPLED)"))
    body.append(f'<text x="620" y="490" class="axl" text-anchor="middle">'
                f'TIME AFTER THE EDGE (us)</text>')
    _emit(_svg(w, h, "Step response into resistive and capacitive loads",
               "1 kHz SQUARE INJECTED IN SERIES WITH C1 (POWER STAGE INPUT)",
               "".join(body)), "square_response", w, h, out)


def _plot_sag(t, rail, spk, t1, t2, out: Path):
    w, h = 1240, 520
    ax = Ax(110, 92, 1060, 340, (3.9, 4.6), (20, 55))
    body = [grid(ax, PAL, linear_ticks(ax, 0.1, 0.025,
                                       fmt=lambda v: f"{v:.2f}"),
                 ystep=5, ymajor=10, yfmt=lambda v: f"{v:g}")]
    a, bnd = ax.x(t1), ax.x(t2)
    body.append(f'<rect x="{a:.1f}" y="{ax.y0}" width="{bnd-a:.1f}" '
                f'height="{ax.h}" fill="{PAL["ink"]}" fill-opacity="0.05"/>')
    body.append(f'<text x="{(a+bnd)/2:.0f}" y="{ax.y0+20:.0f}" class="ann" '
                f'text-anchor="middle">300 ms burst at full power</text>')
    sel = (t >= 3.9) & (t <= 4.6)
    body.append(f'<path d="{ax.path(t[sel], np.abs(spk[sel]))}" fill="none" '
                f'stroke="{SER[2]}" stroke-width="0.7" stroke-opacity="0.55"/>')
    body.append(f'<path d="{ax.path(t[sel], rail[sel])}" fill="none" '
                f'stroke="{SER[0]}" stroke-width="1.6"/>')
    body.append(f'<text x="{ax.x0+ax.w-8:.0f}" y="{ax.y(51):.0f}" class="ann" '
                f'text-anchor="end">rail V(N002)</text>')
    body.append(f'<text x="{ax.x0+ax.w-8:.0f}" y="{ax.y(24):.0f}" class="ann" '
                f'text-anchor="end">|V(SPEAKER)|</text>')
    body.append(frame(ax, PAL) + _axlabels(ax, "TIME (s)", "VOLTS"))
    _emit(_svg(w, h, "Rail sag and recovery under a full-power burst",
               "REAL MAINS SUPPLY &#183; 15 &#937; PRIMARY &#183; 10000 &#181;F "
               "RESERVOIR &#183; 7.5 &#937; LOAD", "".join(body)),
          "rail_sag", w, h, out)


CASES = {"trim": case_trim, "power": case_power, "distortion": case_distortion,
         "stability": case_stability, "supply": case_supply}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", choices=list(CASES), action="append")
    ap.add_argument("--workdir")
    ap.add_argument("-o", "--out", default="/tmp/amp_tran",
                    help="donde dejar las figuras")
    ap.add_argument("--plot", action="store_true")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--as-drawn", action="store_true",
                    help="no ajustar los trimmers: medir tal cual esta")
    ap.add_argument("--vraw", type=float, default=VRAW_DC)
    a = ap.parse_args()

    if not NET.exists():
        sys.exit(f"no encuentro {NET}\n"
                 "no esta versionado: exportalo desde la GUI de LTspice "
                 "(File > Export Netlist)")
    work = Path(a.workdir) if a.workdir else Path("/tmp/amp_tran_sim")
    out = Path(a.out)
    b = Bench(work, vraw=a.vraw)
    print(f"netlist: {NET}")
    print(f"workdir: {work}   rail de banco: {a.vraw} V")
    print(f"trimmers: {'TAL COMO ESTAN DIBUJADOS' if a.as_drawn else 'se ajustan primero'}\n")
    try:
        names = a.only or list(CASES)
        # trim va siempre delante: los demas casos usan los cursores que resuelve
        if not a.as_drawn and "trim" not in names:
            print("(ajustando los trimmers antes de medir; --as-drawn los deja"
                  " como estan)\n")
            case_trim(b)
            print()
        for name in names:
            if name == "trim" and a.as_drawn:
                continue
            CASES[name](b, plot=a.plot, out=out)
            print()
    finally:
        if not a.keep and not a.workdir:
            shutil.rmtree(work, ignore_errors=True)
        else:
            print(f"(netlists y raws en {work})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
