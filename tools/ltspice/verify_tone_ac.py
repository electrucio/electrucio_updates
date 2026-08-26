#!/usr/bin/env python3
"""Barrido AC del 40W: respuesta en frecuencia en funcion de `bass` y `treble`.

    python3 tools/ltspice/verify_tone_ac.py                    # todo (~10 s)
    python3 tools/ltspice/verify_tone_ac.py --only fan_treble --plot
    python3 tools/ltspice/verify_tone_ac.py --only matrix --workdir /tmp/tone --keep

Casos:
  bias        el .op con el que se linealiza, contra el punto de operacion que
              midio el transitorio. ES LA PUERTA: si esto no cuadra, el resto
              del barrido esta linealizando otro circuito.
  fan_treble  treble 0..1 con bass fijo: el abanico clasico de agudos
  fan_bass    bass 0..1 con treble fijo
  matrix      los 5x5, reducidos a tabla de escalares

LA TRAMPA GORDA: EL RAIL NO ES UNA FUENTE.

`.ac` linealiza alrededor del punto de operacion DC, y en este esquematico el
rail sale de la red: V4 SINE(0 325 50) -> trafo de 3 devanados (L1/L2/L3 +
K1 0.99) -> puente D1..D4 -> C13 de 10000 uF -> N002 -> R31 (shunt de 1 mOhm)
-> Q6C.  En DC una SINE con offset 0 VALE 0 V, asi que el .op nativo tiene el
amplificador SIN ALIMENTACION: todos los transistores en corte y el barrido
entero sin sentido.  (Es tambien por lo que el .tran del esquematico espera
hasta t_start = 4 s antes de medir.)

Se arregla anadiendo una fuente DC en N002 (`V_RAW`).  Es una adicion pura, no
hay que quitar nada: la cadena de red se queda puesta y es inerte, porque en DC
la SINE vale 0 y en AC V4 no lleva especificacion `AC` (es un corto a masa), con
el puente en inversa a 48.9 V (el 1N5408 tiene Bv=1000, no rompe).  Y como entra
por el shunt R31 que ya existe, I(V_RAW) da la corriente de rail gratis.

Ojo tambien:

1. `uic` NO sirve aqui: es solo para .tran.  `.ac` exige un .op de verdad.
   No hace falta: con el rail firme, Direct Newton converge de primeras.
2. Hay que TIRAR las 84 `.meas tran` y las 7 `.four` del esquematico.  Necesitan
   datos de transitorio; en un .ac solo inundan el log de fallos.
3. Con `AC 1` en V6, V(PICKUP_IN) == 1 exactamente, asi que V(SPEAKER) *ES* la
   funcion de transferencia del sistema.  No hay que dividir por nada.
4. El .ac es PEQUENA SENAL: los diodos D5..D9 del recortador se linealizan (en
   reposo estan en corte, no molestan), pero esto no dice NADA del caracter de
   recorte.  Para eso, .tran.
5. No hay pote de medios, y el scoop lo fija C20 (470n), no R44.  Barriendo
   cada componente: R44 de 100 a 2200 ohm mueve 0.02 dB (es irrelevante, la
   rama de C20 shunta en paralelo y domina), mientras que C20 de 47n a 1u lleva
   el scoop de 0 a 22.6 dB.  El elemento de medios de esta stack es un
   CONDENSADOR a masa, no la resistencia de mid de una FMV clasica.
6. Todo lo que mide esta suite es con drive=0, que es la ganancia MINIMA: el
   pote de drive (XP4) da +18.6 dB mas a 1 kHz.

La fuente de verdad es `AudioAmpCompl-40W.net`, exportado de la GUI, y NO esta
versionado (esta en .gitignore, igual que psu_cvcc.net): en un clon limpio hay
que exportarlo una vez con `File > Export Netlist` antes de usar esto.

Aqui NO vale asc2net.py, que es lo que usa la suite de psu_cvcc: el .asc pone
varias etiquetas sobre la misma red (`VRAW+` donde el netlist exportado dice
`Q6C`, `Q12C` donde dice `Q10E`) y cada herramienta elige un representante
distinto, asi que el --diff sale lleno de diferencias que solo son alias.
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

REPO = Path(__file__).resolve().parents[2]
AMP = REPO / "guitar_amplifier" / "ltspice"
NET = AMP / "AudioAmpCompl-40W.net"

VRAW_DC = 48.88            # V, media del rail medida en el .tran de 4.2 s
AC_SWEEP = ".ac dec 100 10 100k"

# El modelo de altavoz (un Vint30, https://www.duncanamps.com/spice/loudspeakers/
# vint30.inc).  R27 es la resistencia de continua; el resto son dos celdas RLC
# paralelo que hacen la resonancia del cono y la subida de la bobina movil.
# Sustituirlo por 7.5 ohm resistivos es medir el ampli con carga muerta, que es
# lo que hace un banco.  C10 (3300 uF) NO se toca: el condensador de salida es
# parte del amplificador y fija el corte de graves (6.4 Hz con 7.5 ohm).
SPEAKER_MODEL = ("R28 0003 0002 12.5", "L4 0003 0002 20m", "C15 0003 0002 250u",
                 "R29 0004 0003 0.5", "C16 0004 0003 50u", "L5 0004 0003 100u",
                 "R30 0 0004 20", "L6 0 0004 100u")
R_LOAD = "R27 0002 SPEAKER 7.5"

# --- lineas del netlist que parcheamos (tal cual salen del .net exportado) ---
TRAN = ".tran {step} {t_stop} {t_start} {step}"
VSRC = "V6 PICKUP_IN 0 SINE(0 {in_amplitude} {in_freq})"
P_TREBLE = ".param treble=0.5"
P_BASS = ".param bass=0.5"

# Punto de operacion de referencia: lo midio parse_log.py sobre el .tran de
# 4.2 s (2026-08-26).  Si el .op del barrido no reproduce esto, el .ac esta
# linealizando otro circuito y no hay que creerse ni un numero.
OP_REF = {
    "q6c":         (48.88,  "rail (VRAW+)"),
    "pre_speaker": (24.701, "punto medio de salida"),
    "vcc":         (50.0,   "rail del preamp"),
    "q1b":         (21.08,  "base del par de entrada"),
    "q6b":         (25.31,  "base del Darlington superior"),
    "q11b":        (11.98,  "base del seguidor de salida"),
    "q11e":        (11.35,  "emisor del seguidor"),
    "q12e":        (28.01,  "emisor de la etapa 1"),
}

# A 1 kHz con bass=treble=0.5, drive=0, vol=1, el .tran de hoy midio esto por
# relacion pico-a-pico.  Es la prueba del algodon entre .ac y .tran.
TRAN_REF_1K = {"stack": 0.3126, "sys": 32.157}

FAN = (0.0, 0.25, 0.5, 0.75, 1.0)


# ----------------------------------------------------------------- utilidades
def _pick(names, want):
    """Busca una variable del raw sin importar mayusculas."""
    for n in names:
        if n.lower() == want.lower():
            return n
    raise KeyError(f"{want} no esta en el raw ({names})")


def db(x):
    return 20.0 * np.log10(np.maximum(np.abs(x), 1e-30))


class Sweep:
    """Un barrido .ac ya leido: frecuencia + las transferencias que interesan."""

    def __init__(self, raw: Path):
        names, d = read_raw(raw)
        self.f = np.abs(d[names[0]]).astype(float)
        v = lambda k: d[_pick(names, k)]            # noqa: E731
        self.stack = v("V(tone_out)") / v("V(tone_in)")   # la tone stack in situ
        self.sys = v("V(speaker)") / v("V(pickup_in)")    # guitarra -> altavoz
        # El pickup NO se quita del circuito: se DIVIDE.  En un .ac todo es
        # lineal, asi que V(SPEAKER)/V(PICKUP_OUT) es la respuesta del
        # amplificador solo, atacado desde su entrada real y CON la carga del
        # pickup puesta (R60||R61||R62||R52 ~ 111k y C34+C32 = 620 pF), que es
        # lo que hay cuando enchufas una guitarra de verdad.  Quitarlo a mano
        # cambiaria esa carga; dividirlo no, y ademas deja ver cuanto aportaba.
        self.pickup = v("V(pickup_out)") / v("V(pickup_in)")   # solo la pastilla
        self.amp = v("V(speaker)") / v("V(pickup_out)")        # solo el ampli
        self.pre = v("V(preamp_out)") / v("V(pickup_out)")

    def at(self, H, hz):
        """|H| interpolado en escala log de frecuencia."""
        return float(np.interp(np.log10(hz), np.log10(self.f), np.abs(H)))

    def db_at(self, H, hz):
        return 20.0 * np.log10(max(self.at(H, hz), 1e-30))

    def notch(self, lo=60.0, hi=4000.0, margin=2):
        """Scoop de medios de la stack: (frecuencia, dB en el fondo).

        Devuelve (None, None) si el minimo cae en el borde de la ventana: eso
        no es un notch, es la pendiente de un paso-bajo.  Pasa con treble=0,
        donde la via de agudos esta cortada y no hay estante arriba contra el
        que medir profundidad ninguna.
        """
        m = (self.f >= lo) & (self.f <= hi)
        y = db(self.stack[m])
        k = int(np.argmin(y))
        if k < margin or k > len(y) - 1 - margin:
            return None, None
        return float(self.f[m][k]), float(y[k])

    def corners(self, H, drop=3.0):
        """(f_lo, f_hi, f_pico, dB_pico) a -`drop` dB del PICO.

        OJO: si el pico es una resonancia (la del pickup esta a ~4 kHz), la
        banda que sale describe la resonancia, no el circuito.  Y este ampli
        tiene un notch de 13 dB a 200 Hz metido dentro de la banda, asi que un
        solo numero de "-3 dB" no lo describe.  Usar con cabeza.
        """
        y = db(H)
        k = int(np.argmax(y))
        thr = y[k] - drop
        lo = hi = float("nan")
        for j in range(k, 0, -1):
            if y[j - 1] < thr:
                lo = float(np.interp(thr, [y[j - 1], y[j]],
                                     [self.f[j - 1], self.f[j]]))
                break
        for j in range(k, len(y) - 1):
            if y[j + 1] < thr:
                hi = float(np.interp(thr, [y[j + 1], y[j]],
                                     [self.f[j + 1], self.f[j]]))
                break
        return lo, hi, float(self.f[k]), float(y[k])


class Bench:
    """Prepara variantes del netlist y las simula."""

    def __init__(self, workdir: Path, vraw: float = VRAW_DC,
                 sweep: str = AC_SWEEP, dummy_load: bool = False):
        self.w = workdir
        self.w.mkdir(parents=True, exist_ok=True)
        self.vraw = vraw
        self.sweep = sweep
        self.dummy_load = dummy_load
        self._cache: dict[tuple, Sweep] = {}

    def _base(self) -> Netlist:
        n = Netlist.from_file(NET).absolutize_libs([AMP])
        # el rail, que es lo que hace posible el .ac (ver docstring)
        n.add(f".param vraw={self.vraw}", "V_RAW N002 0 {vraw}")
        # excitacion AC.  `AC 1` es ignorado por .tran, asi que no molesta a nadie
        n.patch(VSRC, VSRC + " AC 1")
        # instrumentacion de transitorio: no aplica a un .ac
        n.drop_re(r"\s*\.meas\s+tran\b", 80)
        n.drop_re(r"\s*\.four\b", 7)
        if self.dummy_load:
            # fuera el modelo de altavoz, dentro 7.5 ohm a masa.  Cada linea va
            # como patch() explicito: si el esquematico cambia el modelo, esto
            # revienta en vez de dejar nodos colgando.
            for line in SPEAKER_MODEL:
                n.patch(line + "\n", "")
            n.patch(R_LOAD, "R27 0 SPEAKER 7.5")
        return n

    def op(self) -> dict[str, float]:
        """Resuelve solo el punto de operacion y lo devuelve nodo -> voltios."""
        n = self._base().patch(TRAN, ".op")
        log = run_batch(n.write(self.w / "op.net")).with_suffix(".log")
        out = {}
        for m in re.finditer(r"^V\((\w+)\):?\s+([-\d.eE+]+)",
                             read_log(log), re.M):
            out[m.group(1).lower()] = float(m.group(2))
        return out

    def ac(self, bass: float, treble: float) -> Sweep:
        key = (round(bass, 4), round(treble, 4))
        if key in self._cache:
            return self._cache[key]
        tag = f"ac_b{key[0]:g}_t{key[1]:g}".replace(".", "")
        n = self._base()
        n.patch(TRAN, self.sweep)
        n.patch(P_BASS, f".param bass={bass}")
        n.patch(P_TREBLE, f".param treble={treble}")
        # NO se usa .save.  Un raw de .ac son 1.5 MB (401 puntos x 238 nodos),
        # asi que sale mas a cuenta guardarlo todo que descubrir a mitad del
        # analisis que falta un nodo.  Mismo criterio que verify_psu_cvcc.py.
        n.add(".options plotwinsize=0")
        s = Sweep(run_batch(n.write(self.w / f"{tag}.net")))
        self._cache[key] = s
        return s


# --------------------------------------------------------------------- casos
def case_bias(b: Bench, plot=False):
    print("== La puerta: el .op con el que se linealiza el .ac ==")
    print("   El rail de este esquematico sale de la red, y en DC una SINE con")
    print("   offset 0 vale 0 V.  Sin la fuente V_RAW, el .ac linealizaria un")
    print("   amplificador apagado.  Aqui se comprueba que con ella el punto de")
    print("   operacion es el MISMO que midio el transitorio de 4.2 s.\n")
    op = b.op()
    print(f"  {'nodo':<14}{'.op':>10}{'.tran':>10}{'error':>9}   que es")
    peor = 0.0
    for k, (ref, desc) in OP_REF.items():
        got = op.get(k)
        if got is None:
            print(f"  V({k:<11}) {'AUSENTE':>19}")
            peor = float("inf")
            continue
        err = got - ref
        peor = max(peor, abs(err))
        flag = "" if abs(err) < 0.15 else "   <-- OJO"
        print(f"  V({k:<11}){got:10.3f}{ref:10.3f}{err:+9.3f}   {desc}{flag}")
    print(f"\n  Peor desviacion: {peor:.3f} V", end="")
    print("  -> el .ac es de fiar" if peor < 0.15 else
          "  -> NO te creas el barrido")

    # Vbe de los transistores de salida, que es lo que fija el reposo
    vbe = op.get("q6b", 0) - op.get("q6e", 0)
    print(f"  Vbe(Q6) = {vbe*1000:.0f} mV   (el .tran midio 545 mV con senal "
          "encima, asi que en reposo tiene que salir algo mas alto)")


def hz(x):
    """Frecuencia en Hz o kHz, o '-' si no hay."""
    if x is None or not np.isfinite(x):
        return "-"
    return f"{x/1000:.1f}k" if x >= 1000 else f"{x:.0f}"


def _row_hdr():
    return (f"  {'pos':>5}|{'100Hz':>9}{'1kHz':>9}{'5kHz':>9}"
            f"{'notch':>9}{'fondo':>9}  |{'50Hz':>9}{'1kHz':>9}{'10kHz':>9}")


def _row(pos, s: Sweep):
    nf, nd = s.notch()
    return (f"  {pos:>5}|{s.db_at(s.stack, 100):+9.2f}"
            f"{s.db_at(s.stack, 1000):+9.2f}{s.db_at(s.stack, 5000):+9.2f}"
            f"{hz(nf):>9}{('%+.2f' % nd) if nd is not None else '-':>9}  |"
            f"{s.db_at(s.amp, 50):+9.2f}{s.db_at(s.amp, 1000):+9.2f}"
            f"{s.db_at(s.amp, 10000):+9.2f}")


def _fan(b: Bench, swept: str, fixed_val: float, plot: bool, workdir: Path):
    other = "treble" if swept == "bass" else "bass"
    print(f"== Abanico de {swept.upper()} (con {other}={fixed_val}) ==")
    print("   Bloque izquierdo: la tone stack, |V(TONE_OUT)/V(TONE_IN)| en dB.")
    print("   Medida EN SITIO, con su impedancia de fuente real (R35 470 Ohm) y")
    print("   su carga real (C21 -> Q11B).  Es un cociente entre dos nodos que")
    print("   estan los dos DETRAS del pickup, asi que el pickup no la toca.")
    print("   Bloque derecho: el amplificador solo, |V(SPEAKER)/V(PICKUP_OUT)|,")
    print("   con el pickup dividido fuera (ver el caso `pickup`).\n")
    print(_row_hdr())
    curvas = []
    for v in FAN:
        kw = {swept: v, other: fixed_val}
        s = b.ac(**kw)
        print(_row(f"{v:g}", s))
        curvas.append((v, s))
    d100 = curvas[-1][1].db_at(curvas[-1][1].stack, 100) - \
        curvas[0][1].db_at(curvas[0][1].stack, 100)
    d5k = curvas[-1][1].db_at(curvas[-1][1].stack, 5000) - \
        curvas[0][1].db_at(curvas[0][1].stack, 5000)
    print(f"\n  Recorrido del pote de {swept}: {d100:+.1f} dB a 100 Hz, "
          f"{d5k:+.1f} dB a 5 kHz")
    if plot:
        _plot_fan(curvas, swept, other, fixed_val, workdir)
    return curvas


def case_fan_treble(b: Bench, plot=False):
    _fan(b, "treble", 0.5, plot, b.w)


def case_fan_bass(b: Bench, plot=False):
    _fan(b, "bass", 0.5, plot, b.w)


def case_matrix(b: Bench, plot=False):
    print("== Matriz 5x5: los dos potes a la vez ==")
    print("   El vicio clasico de la tone stack pasiva: los controles NO son")
    print("   independientes.  Mira la esquina de abajo a la izquierda.\n")
    print("  |H_stack| a 1 kHz, en dB     (filas: bass, columnas: treble)")
    print("        " + "".join(f"{t:>9g}" for t in FAN))
    tabla = {}
    for bs in FAN:
        fila = []
        for tr in FAN:
            s = b.ac(bass=bs, treble=tr)
            tabla[(bs, tr)] = s
            fila.append(s.db_at(s.stack, 1000))
        print(f"  {bs:>5g} " + "".join(f"{x:+9.2f}" for x in fila))

    print("\n  Profundidad del scoop de medios, en dB bajo el estante de 5 kHz")
    print("        " + "".join(f"{t:>9g}" for t in FAN))
    for bs in FAN:
        fila = []
        for tr in FAN:
            s = tabla[(bs, tr)]
            _, nd = s.notch()
            fila.append(None if nd is None else s.db_at(s.stack, 5000) - nd)
        print(f"  {bs:>5g} " + "".join(
            (f"{x:9.2f}" if x is not None else f"{'-':>9}") for x in fila))

    print("\n  Ganancia total del sistema a 1 kHz (pickup -> altavoz), en dB")
    print("        " + "".join(f"{t:>9g}" for t in FAN))
    for bs in FAN:
        print(f"  {bs:>5g} " + "".join(
            f"{tabla[(bs, tr)].db_at(tabla[(bs, tr)].sys, 1000):+9.2f}"
            for tr in FAN))

    peor = min(tabla.items(), key=lambda kv: kv[1].db_at(kv[1].stack, 1000))
    mejor = max(tabla.items(), key=lambda kv: kv[1].db_at(kv[1].stack, 1000))
    print(f"\n  Rango de la stack a 1 kHz: "
          f"{peor[1].db_at(peor[1].stack, 1000):+.2f} dB en "
          f"bass={peor[0][0]:g}/treble={peor[0][1]:g}  ..  "
          f"{mejor[1].db_at(mejor[1].stack, 1000):+.2f} dB en "
          f"bass={mejor[0][0]:g}/treble={mejor[0][1]:g}")
    if plot:
        _plot_matrix(tabla, b.w)


def case_pickup(b: Bench, plot=False):
    """Cuanto de la respuesta del sistema es el pickup y cuanto el ampli."""
    print("== Cuanto colorea el pickup ==")
    print("   El modelo de pastilla es V6 -> L7 2.2 H -> R58 5.8k -> PICKUP_OUT,")
    print("   cargado con R60||R61||R62||R52 (~111k) y C34+C32 = 620 pF: un")
    print("   paso-bajo de 2o orden resonante.  En un .ac todo es lineal, asi que")
    print("   NO hace falta quitarlo del circuito: se DIVIDE.\n")
    s = b.ac(bass=0.5, treble=0.5)
    print(f"  {'Hz':>8}{'pickup':>10}{'ampli':>10}{'sistema':>10}{'stack':>10}")
    for f in (20, 50, 100, 200, 500, 1000, 2000, 4000, 5000,
              10000, 20000, 50000):
        print(f"  {f:>8}{s.db_at(s.pickup, f):+10.2f}{s.db_at(s.amp, f):+10.2f}"
              f"{s.db_at(s.sys, f):+10.2f}{s.db_at(s.stack, f):+10.2f}")

    fp = float(s.f[int(np.argmax(db(s.pickup)))])
    dp = s.db_at(s.pickup, fp)
    print(f"\n  El pickup es plano ({s.db_at(s.pickup, 20):+.2f} dB a 20 Hz, "
          f"{s.db_at(s.pickup, 1000):+.2f} dB a 1 kHz) y solo aporta")
    print(f"  {dp - s.db_at(s.pickup, 1000):+.2f} dB de resonancia a {fp:.0f} Hz."
          "  Por arriba cae rapido: "
          f"{s.db_at(s.pickup, 10000):+.1f} dB a 10 kHz,")
    print(f"  {s.db_at(s.pickup, 20000):+.1f} dB a 20 kHz.  O sea que NO es lo "
          "que da forma a la banda de audio.")

    a1k = s.db_at(s.amp, 1000)
    print(f"\n  Lo que si la da es el propio amplificador:")
    print(f"    el hundimiento de {a1k - s.db_at(s.amp, 200):.1f} dB a 200 Hz "
          "(bajo el nivel de 1 kHz) es la")
    print( "    tone stack, no el pickup: mira la columna 'stack'")
    print(f"    y por arriba NO RUEDA: {s.db_at(s.amp, 20000):+.2f} dB a 20 kHz "
          f"y {s.db_at(s.amp, 50000):+.2f} dB a 50 kHz,")
    print(f"    contra {a1k:+.2f} dB a 1 kHz.  Con ganancia plena a 50 kHz, el")
    print( "    unico que limita la banda por arriba es el pickup.  En un "
           "cuasi-complementario")
    print( "    eso es un punto a mirar: margen de fase y filtrado de entrada.")

    print(f"\n  Conclusion: no hay que hacer skip del pickup.  |H_stack| es un")
    print( "  cociente entre dos nodos que estan los dos detras de el, asi que "
           "las")
    print( "  tablas de bass/treble no cambian ni un dB.  Y para el sistema, "
           "dividirlo")
    print( "  fuera es mejor que quitarlo: sale la respuesta del ampli con la "
           "carga")
    print( "  del pickup puesta (que es la real) y ademas se ve cuanto aportaba.")


def case_crosscheck(b: Bench, plot=False):
    print("== Prueba del algodon: el .ac contra el .tran ==")
    print("   Los dos analisis tienen que coincidir en el punto que ya medimos")
    print("   con el transitorio de 4.2 s: 1 kHz, bass=0.5, treble=0.5.\n")
    s = b.ac(bass=0.5, treble=0.5)
    for k, ref, H in (("tone stack ", TRAN_REF_1K["stack"], s.stack),
                      ("sistema    ", TRAN_REF_1K["sys"], s.sys)):
        got = s.at(H, 1000)
        err = 100 * (got / ref - 1)
        print(f"  {k}  .ac {got:9.4f}   .tran {ref:9.4f}   {err:+6.2f} %"
              f"{'  OK' if abs(err) < 1 else '  <-- NO CUADRA'}")
    lo, hi, fp, dp = s.corners(s.sys)
    print(f"\n  Sistema completo: pico {dp:+.2f} dB a {fp:.0f} Hz.  Ese pico es"
          " la resonancia del")
    print(f"  pickup (L7 2.2 H con C34 500 p + C32 120 p), no del amplificador:"
          " el caso")
    print( "  `pickup` lo separa.  Una banda a -3 dB referida a un pico "
           "resonante no")
    print(f"  describe el ampli, asi que aqui solo se da el pico. "
          f"(a -3 dB: {hz(lo)} .. {hz(hi)} Hz)")


# ------------------------------------------------------------------- graficas
_MPL_WARNED = []


def _mpl():
    """matplotlib si esta instalado; None y un aviso una sola vez si no."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        return plt
    except ImportError:
        if not _MPL_WARNED:
            _MPL_WARNED.append(1)
            print("  (--plot pide matplotlib y no esta instalado; "
                  "solo tablas.  `pip3 install matplotlib`)")
        return None


def _plot_fan(curvas, swept, other, fixed_val, workdir):
    plt = _mpl()
    if plt is None:
        return
    fig, ax = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
    cmap = plt.get_cmap("viridis")
    for i, (v, s) in enumerate(curvas):
        c = cmap(i / max(len(curvas) - 1, 1))
        ax[0].semilogx(s.f, db(s.stack), color=c, lw=1.6, label=f"{swept}={v:g}")
        ax[1].semilogx(s.f, db(s.sys), color=c, lw=1.6)
    ax[0].set_ylabel("tone stack, dB\nV(TONE_OUT)/V(TONE_IN)")
    ax[0].set_title(f"Abanico de {swept} ({other}={fixed_val})")
    ax[0].legend(fontsize=8)
    ax[1].set_ylabel("sistema, dB\nV(SPEAKER)/V(PICKUP_IN)")
    ax[1].set_xlabel("Hz")
    for a in ax:
        a.grid(True, which="both", alpha=0.3)
    out = workdir / f"fan_{swept}.png"
    fig.tight_layout()
    fig.savefig(out, dpi=110)
    plt.close(fig)
    print(f"  -> {out}")


def _plot_matrix(tabla, workdir):
    plt = _mpl()
    if plt is None:
        return
    fig, axes = plt.subplots(1, len(FAN), figsize=(16, 4),
                             sharex=True, sharey=True)
    cmap = plt.get_cmap("viridis")
    for a, bs in zip(axes, FAN):
        for i, tr in enumerate(FAN):
            s = tabla[(bs, tr)]
            a.semilogx(s.f, db(s.stack), lw=1.4,
                       color=cmap(i / (len(FAN) - 1)), label=f"t={tr:g}")
        a.set_title(f"bass={bs:g}")
        a.grid(True, which="both", alpha=0.3)
        a.set_xlabel("Hz")
    axes[0].set_ylabel("tone stack, dB")
    axes[-1].legend(fontsize=7)
    out = workdir / "matrix.png"
    fig.tight_layout()
    fig.savefig(out, dpi=110)
    plt.close(fig)
    print(f"  -> {out}")


CASES = {"bias": case_bias, "crosscheck": case_crosscheck,
         "pickup": case_pickup,
         "fan_treble": case_fan_treble, "fan_bass": case_fan_bass,
         "matrix": case_matrix}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", choices=list(CASES), action="append")
    ap.add_argument("--workdir")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--plot", action="store_true")
    ap.add_argument("--vraw", type=float, default=VRAW_DC,
                    help="tension DC del rail para el .op (V)")
    ap.add_argument("--sweep", default=AC_SWEEP,
                    help=f"directiva de barrido (por defecto: {AC_SWEEP!r})")
    ap.add_argument("--dummy-load", action="store_true",
                    help="cambia el modelo de altavoz por 7.5 ohm resistivos")
    a = ap.parse_args()

    if not NET.exists():
        sys.exit(f"no encuentro {NET}\n"
                 "exportalo desde la GUI: File > Export Netlist")

    work = Path(a.workdir) if a.workdir else Path(
        "/tmp") / "tone_ac"
    b = Bench(work, vraw=a.vraw, sweep=a.sweep, dummy_load=a.dummy_load)
    print(f"netlist: {NET}")
    print(f"workdir: {work}   rail: {a.vraw} V   {a.sweep}")
    print(f"carga:   {'7.5 ohm resistivos' if a.dummy_load else 'modelo Vint30'}\n")
    try:
        for name in (a.only or list(CASES)):
            CASES[name](b, plot=a.plot)
            print()
    finally:
        if not a.keep and not a.workdir:
            shutil.rmtree(work, ignore_errors=True)
        elif a.keep or a.workdir:
            print(f"(netlists y raws en {work})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
