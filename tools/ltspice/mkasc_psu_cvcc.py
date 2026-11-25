#!/usr/bin/env python3
"""Genera powersupply/psu_cvcc/psu_cvcc.asc con una disposicion de lectura.

Criterio de colocacion (el mismo que usa la hoja de TI en sus figuras de
aplicacion): la señal va de IZQUIERDA a DERECHA.

    RED -> TRAFOS -> SELECTOR -> PUENTE -> DEPOSITO -> LM317HV -> SALIDA

Los tres transformadores estan a la MISMA x, apilados en vertical, porque sus
secundarios van en serie y asi la cadena de tomas se lee de arriba abajo.  La
referencia y el lazo de corriente van en una banda inferior, debajo del
regulador, que es donde atacan.  El modelo termico y las directivas .meas estan
apartados del dibujo: no son circuito, son instrumentacion.

Se conecta por ETIQUETAS DE RED (flags), no por hilos largos: cada pin lleva un
tramo corto de hilo y su etiqueta.  No hay cruces y el netlist es inequivoco.

    python3 tools/ltspice/mkasc_psu_cvcc.py
    python3 tools/ltspice/asc2net.py powersupply/psu_cvcc/psu_cvcc.asc --diff ref.net
    python3 tools/ltspice/asc2svg.py powersupply/psu_cvcc/psu_cvcc.asc -o psu.svg
"""
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "powersupply/psu_cvcc/psu_cvcc.asc"

# ====================================================== DIVISOR DE TENSION ====
# El pote de tension ya NO es un multivuelta de instrumentacion: son dos potes
# de panel corrientes en serie, grueso + fino.  Lo que lo hace posible es el
# sumidero de carga minima (bloque 5b): con el puesto, R1 deja de tener que dar
# la carga minima del chip y puede subir, que es lo que permite que el pote sea
# de valor alto y disipe poco.
#
#   Vout = 1,25 * (R2c + R2f) / R1        P(pote) = Vmax^2 / (R2c + R2f)
#
# El fino cubre R2F/(R2C+R2F) del recorrido: con 1k sobre 11k son 3,7 V en 270
# grados, o sea 14 mV/grado, equivalente a un multivuelta de 10 vueltas.
R2_COARSE = 10000           # pote grueso, lineal, >=0,25 W (136 mW)
R2_FINE = 1000              # pote fino, lineal, cualquiera (14 mW)
R2_TOTAL = R2_COARSE + R2_FINE

# R1 lleva el ajuste de fondo de escala, NO el pote (al reves que el TP1 del
# P223).  Con potes de panel de +-20 % hay que poder corregir en los DOS
# sentidos, y subir R1 baja el fondo de escala sin gastar recorrido de pote.
# Margen necesario para +-20 % sobre 11k: 272..407 ohm.
R1_FIX = 270                # fijo
R1_TRIM = 70                # TP1 (recorrido 0..150) en su posicion nominal
R1_TOTAL = R1_FIX + R1_TRIM

# Sumidero de carga minima (Q1 del ESP Project 223).  Base al rail de -5 V,
# emisor por Re al BRUTO de -17 V: asi Re es grande y acota la corriente si el
# transistor se va en corto, y la corriente no ensucia el rail de -5 V, que es
# la referencia de alterna de Cadj.
RE_MIN = 1300               # 11,4 V / 1k3 = 8,8 mA
VNRAW = -17                 # bruto del auxiliar, antes del 79L05

# Cadj: el condensador del pin ADJ, que es el compromiso rizado/velocidad.  La
# fig. 21 de TI usa 10 uF para 80 dB de rechazo, pero el LM317HV solo saca
# ~50 uA por ADJ y toda SUBIDA de la salida depende de cargarlo a traves de R1,
# asi que su valor fija la velocidad del lazo entero.  Medido con
# tools/ltspice/barrido_cadj.py: la velocidad va LINEAL con Cadj y el rizado
# solo con su RAIZ CUADRADA, y del ultimo decalaje (1 uF -> 10 uF) salen solo
# 11,3 dB a cambio de 11x mas lento.  Con 1 uF el rizado se queda en 2 mV p-p,
# que es lo que especifican las comerciales, y el establecimiento baja de 174 a
# 15,6 ms.  Silicon Chip, con el mismo chip, usa 100 nF por este mismo motivo.
CADJ = "1u"                 # 10u en las versiones anteriores a 2026-11-25

# Filtro CRC del deposito, como el del ESP Project 223 (2x2200 uF con 1 ohm/5 W
# entre ellos).  Al bajar Cadj se perdieron 11,3 dB de rechazo; esto los compra
# otra vez en el RAIL en vez de en el lazo, asi que no cuesta velocidad.  El
# precio es I*R de margen de dropout y el calor en la resistencia, y el reparto
# entre R y C2 es una eleccion: el mismo polo se consigue con poca R y mucha C
# (menos caida, mas dinero) o al reves.  Medido con barrido_crc.py.
# FILTRO CRC: NO VA EN LA SIMULACION, pero SI deben quedar sus pads en la placa.
#
# Partir el deposito con una resistencia (10.000 uF - R - C2) compra atenuacion
# del rizado del rail donde es barata, en vez de en el lazo.  Medido con
# barrido_crc.py: la atenuacion depende SOLO del producto R*C, y da 11,1 dB con
# 4,7 ms y 17,2 dB con 10 ms, con cualquier reparto entre R y C.
#
# Por que no esta montado:
#   - el rizado sin el ya es 1,98 mV p-p, DENTRO de los 2 mV que especifican las
#     comerciales (Rigol DP832, Korad, HP E3610A);
#   - y sobre todo, ese 1,98 mV es un numero del MODELO, que topa en ~50-61 dB
#     de rechazo donde el chip real hace 80 dB (§8.4.2).  La incertidumbre son
#     ~20 dB y el filtro compra 11-17: **el efecto cabe dentro del error de la
#     medida con la que se juzga**.  El dato que decide la compra no esta en la
#     simulacion, esta en el polimetro de la unidad construida.
#
# Que dejar en la placa: pads para Rcrc en serie en el rail (con un puente de
# 0 ohm de serie) y para Cbulk2 en paralelo a la entrada del regulador.  Si al
# medir el rizado sale alto, se sueldan.  Cuesta IxR de margen de dropout, o sea
# ~1 V a plena corriente con 1 ohm, y el techo util de cada toma baja otro tanto.
# Combinaciones medidas, por si hace falta elegir deprisa:
#   1 ohm   + 10.000 uF -> 17,2 dB, 0,26 mV, 1,34 V de caida, 1,8 W
#   1 ohm   +  4.700 uF -> 11,1 dB, 0,48 mV, 1,34 V de caida, 1,8 W
#   2,2 ohm +  4.700 uF -> 17,5 dB, 0,25 mV, 2,95 V de caida y 4,0 W (se calienta)

# offsets de pin en R0, por simbolo, en orden de SpiceOrder
PINS = {
    "res":     [(16, 16), (16, 96)],
    "cap":     [(16, 0),  (16, 64)],
    "ind":     [(16, 16), (16, 96)],
    "diode":   [(16, 0),  (16, 64)],
    "voltage": [(0, 16),  (0, 96)],
    "bi":      [(0, 0),   (0, 80)],
    "bv":      [(0, 16),  (0, 96)],
    "npn":     [(64, 0),  (0, 48), (64, 96)],
    "sw":      [(0, 16),  (0, 96), (-48, 80), (-48, 32)],
    "LM317HV": [(0, 48),  (64, 0), (-64, 0)],
    "LM358":   [(-32, 16), (-32, -16), (0, -32), (0, 32), (32, 0)],
    "TL431ED": [(0, -64), (0, 64), (-48, 40)],
}
# hacia donde sale el tramo de hilo de cada pin, vector unitario en R0
LEAD = {
    "res":     [(0, -1), (0, 1)],
    "cap":     [(0, -1), (0, 1)],
    "ind":     [(0, -1), (0, 1)],
    "diode":   [(0, -1), (0, 1)],
    "voltage": [(0, -1), (0, 1)],
    "bi":      [(0, -1), (0, 1)],
    "bv":      [(0, -1), (0, 1)],
    "npn":     [(0, -1), (-1, 0), (0, 1)],
    "sw":      [(0, -1), (0, 1), (-1, 0), (-1, 0)],
    "LM317HV": [(0, 1), (1, 0), (-1, 0)],
    "LM358":   [(-1, 0), (-1, 0), (0, -1), (0, 1), (1, 0)],
    "TL431ED": [(0, -1), (0, 1), (-1, 0)],
}
ROT = {
    "R0":   lambda x, y: (x, y),
    "R90":  lambda x, y: (-y, x),
    "R180": lambda x, y: (-x, -y),
    "R270": lambda x, y: (y, -x),
    "M0":   lambda x, y: (-x, y),
    "M90":  lambda x, y: (-y, -x),
    "M180": lambda x, y: (x, -y),
    "M270": lambda x, y: (y, x),
}
LEADLEN = 32

wires, flags, syms, texts, draws = [], [], [], [], []

# Cada bloque funcional acumula los puntos que ocupa; al final se le pinta un
# recuadro punteado con su titulo.  El marco no se descuadra al mover piezas.
blocks: "dict[str, list]" = {}
cur = [None]


def block(title):
    cur[0] = title
    blocks.setdefault(title, [])


def _touch(x, y):
    if cur[0] is not None:
        blocks[cur[0]].append((x, y))


def place(sym, x, y, name, value, nets, rot="R0", lead=LEADLEN, window3=None):
    """Coloca `sym` en (x,y) con giro `rot`, y etiqueta cada pin."""
    syms.append(f"SYMBOL {sym} {x} {y} {rot}")
    if window3 is not None:
        syms.append(f"WINDOW 3 {window3} Left 2")
    syms.append(f"SYMATTR InstName {name}")
    if value is not None:
        syms.append(f"SYMATTR Value {value}")
    _touch(x - 40, y - 24)
    _touch(x + 64, y + 128)                      # sitio del texto del valor
    for (dx, dy), (lx, ly), net in zip(PINS[sym], LEAD[sym], nets):
        rx, ry = ROT[rot](dx, dy)
        rlx, rly = ROT[rot](lx, ly)
        px, py = x + rx, y + ry
        ex, ey = px + rlx * lead, py + rly * lead
        wires.append(f"WIRE {px} {py} {ex} {ey}")
        flags.append(f"FLAG {ex} {ey} {net}")
        _touch(ex - 8, ey - 24)
        _touch(ex + 9 * len(net), ey + 24)


def label(x, y, s):
    texts.append(f"TEXT {x} {y} Left 2 ;{s}")


def directive(x, y, s):
    texts.append(f"TEXT {x} {y} Left 2 !{s}")


def line(x1, y1, x2, y2):
    draws.append(f"LINE Normal {x1} {y1} {x2} {y2}")


# =============================================================== 1. LA RED ====
# A la izquierda del todo.  Los tres primarios estan SIEMPRE conectados a la
# red: el selector no enchufa transformadores, elige cuantos secundarios entran
# en serie.
block("1. RED 230 Vca")
place("voltage", -320, 640, "V1", "SINE(0 325 50)", ["LIVE", "NEUTRAL"])
place("res", -160, 640, "Rgnd", "1G", ["NEUTRAL", "0"])
label(-380, 900, "Rgnd solo ata el neutro")
label(-380, 940, "a la masa del simulador.")

# ================================================== 2. LOS TRES TRAFOS ========
# Misma x, apilados en vertical.  Primario a x=TXP, secundario a x=TXS.
# Secundarios en serie de arriba abajo: TAP3 -> TAP2 -> TAP1 -> ACLO.
block("2. TRES TRANSFORMADORES ~13 Vrms - SECUNDARIOS EN SERIE")
TXP, TXS, TSTEP = 480, 720, 560
for k, (a, b) in enumerate([("TAP3", "TAP2"), ("TAP2", "TAP1"), ("TAP1", "ACLO")]):
    n, y0 = k + 1, 160 + k * TSTEP
    place("res", TXP, y0 - 176, f"RF{n}", "0.5m", ["LIVE", f"LP{n}"])
    place("ind", TXP, y0, f"Lp{n}", "50", [f"LP{n}", f"NP{n}"])
    place("res", TXP, y0 + 176, f"Rp{n}", "70", [f"NP{n}", "NEUTRAL"])
    place("ind", TXS, y0, f"Ls{n}", "160m", [a, f"NS{n}"])
    place("res", TXS, y0 + 176, f"Rs{n}", "0.18", [f"NS{n}", b])
    line(600, y0 + 8, 600, y0 + 104)             # nucleo, entre los dos devanados
    line(616, y0 + 8, 616, y0 + 104)
    label(184, y0 + 40, f"TRAFO {n}")
    _touch(160, y0 + 24)

# ============================================ 3. SELECTOR MANUAL DE TOMAS =====
# Rotativo 1P3T break-before-make: cada polo a la altura de su toma.
block("3. SELECTOR MANUAL 1P3T (break-before-make)")
SX = 1240
for k, y in enumerate([1280, 720, 160]):         # S_T1 abajo, S_T3 arriba
    n = 3 - k
    place("sw", SX, y - 56, f"S_T{n}", "SWMAN", [f"TAP{n}", "ACHI", f"SEL{n}", "0"])
    place("voltage", SX - 260, y - 56, f"V_S{n}", f"{{12*(TAP=={n})}}",
          [f"SEL{n}", "0"])
label(950, 1420, "V_S1..3 = el mando del rotativo.")
label(950, 1460, "Solo uno cierra a la vez.")
_touch(950, 1470)

# ============================================== 4. PUENTE Y DEPOSITO ==========
block("4. PUENTE Y DEPOSITO")
BX1, BX2, BY = 1740, 1940, 900
place("diode", BX1, BY,       "D_B4", "1N5408", ["0", "ACLO"],    rot="R180")
place("diode", BX1, BY - 200, "D_B1", "1N5408", ["ACLO", "VRAW"], rot="R180")
place("diode", BX2, BY,       "D_B3", "1N5408", ["0", "ACHI"],    rot="R180")
place("diode", BX2, BY - 200, "D_B2", "1N5408", ["ACHI", "VRAW"], rot="R180")
place("cap", 1540, 660, "Csnub", "0.1u", ["ACHI", "NSNUB"])
place("res", 1540, 840, "Rsnub", "100",  ["NSNUB", "ACLO"])
label(1440, 1060, "amortiguador del secundario")
_touch(1440, 1070)
place("cap", 2160, 640, "Cbulk", "10000u", ["VRAW", "0"])
place("res", 2300, 640, "Rbleed", "10k",   ["VRAW", "0"])
place("cap", 2440, 640, "Cin",   "0.1u",   ["VRAW", "0"])
label(2100, 1060, "EN LA PLACA: dejar pads para un filtro CRC (Rcrc en serie en")
label(2100, 1100, "el rail con puente de 0 ohm, Cbulk2 en paralelo a la entrada).")
label(2100, 1140, "NO va montado: el rizado sin el ya esta dentro de spec comercial")
label(2100, 1180, "y la mejora cabe dentro del error del modelo.  Se decide MIDIENDO")
label(2100, 1220, "la unidad construida.  Valores medidos, en el README.")
_touch(2100, 1230)

# ================================================ 5. REGULADOR (fig. 16) ======
block("5. LM317HV:  Vout = 1,25*(R2c+R2f)/R1  (0 V con el pote a cero)")
UX, UY = 2720, 560
place("LM317HV", UX, UY, "U1", None, ["VADJ", "VOUT", "VRAW"])
place("res", UX + 180, 560, "R1", str(R1_FIX), ["VOUT", "VR1T"])
# OJO: LTspice antepone la inicial del prefijo cuando el InstName no
# empieza por ella, asi que en el netlist TP1 se llama RTP1 (ver .meas).
place("res", UX + 180, 720, "TP1", str(R1_TRIM), ["VR1T", "VADJ"])
place("res", UX + 180, 900, "R2c", f"R=max(V(VSET)*{R2_COARSE},0.1)",
      ["VADJ", "VMIDP"])
place("res", UX + 180, 1080, "R2f", f"R=max(V(VSETF)*{R2_FINE},0.1)",
      ["VMIDP", "VNREF"])
place("cap", UX + 340, 900, "Cadj", CADJ, ["VADJ", "VNEG"])
place("cap", UX + 480, 560, "Cout", "10u", ["VOUT", "0"])
place("cap", UX + 500, 900, "Cout_hf", "100n", ["VOUT", "0"])
label(UX - 60, 460, f"R2c+R2f = dos potes de PANEL en serie ({R2_COARSE//1000}k"
                    f" grueso + {R2_FINE} fino), {40.5**2/R2_TOTAL*1000:.0f} mW en total.")
label(UX - 60, 420, "R2 a VNREF = VRTN - 1,25 (cero a 0 V).  Cadj a -5 V (S.Chip): 80 dB (fig. 21).")
label(UX - 60, 380, f"R1+TP1 = {R1_TOTAL} ohm fija la ESCALA, no la carga minima:"
                    f" de eso se encarga Q_min.")
label(UX - 60, 340, "TP1 ajusta el fondo de escala (potes de panel: +-20 %).  Subirla lo baja.")
label(UX - 60, 1240, "Dos mandos independientes: VSET mueve el grueso y VSETF el fino.")
label(UX - 60, 1280, "Lo que ve el circuito es la SUMA de los dos.")
_touch(UX - 70, 330)
_touch(UX - 70, 1290)

# ============================= 5b. SUMIDERO DE CARGA MINIMA (Q1 del P223) =====
# El LM317 es un regulador FLOTANTE: no tiene pata de masa, asi que su corriente
# de reposo sale obligatoriamente por OUT, y el elemento de paso interno solo
# puede empujar, nunca absorber.  Sin un consumo minimo en la salida la tension
# se va hacia arriba.  El datasheet pide hasta 12 mA a 60 V de diferencial.
#
# Antes lo daba R1 (1,25/120 = 10,4 mA), pero esa misma R1 fija la corriente del
# divisor y por tanto la potencia del pote: un solo componente con dos trabajos
# incompatibles.  Q_min los separa y es lo que permite usar potes de panel.
#
# POR QUE UN SUMIDERO Y NO UN BLEEDER: una resistencia da Vout/R, o sea MENOS
# corriente cuanto mas baja es la salida, y el caso peor es justo salida baja
# con diferencial alto.  El sumidero da la misma corriente a cualquier Vout.
#
# POR QUE EL EMISOR VA AL BRUTO DE -17 V Y LA BASE AL RAIL DE -5 V:
#   - necesita margen para seguir trabajando con la salida en 0 V (el emisor se
#     queda en -5,6 V, o sea 5,6 V de Vce);
#   - sobre Re caen 11,4 V en vez de 0,6, asi que Re es 1k3 en vez de 75 ohm.
#     Si el transistor se va en CORTO colector-emisor, la corriente de fallo la
#     acota Re: 44 mA y 2,5 W en Re, en vez de 607 mA y 27 W.  Re de 3 W, y a
#     ser posible fusible;
#   - el rail de -5 V solo da la corriente de BASE (~45 uA), asi que sigue
#     limpio: es la referencia de alterna de Cadj.
block("5b. SUMIDERO DE CARGA MINIMA - lo que libera al pote (Q1 del P223)")
SX, SY = 4060, 1590
place("res", SX - 160, SY - 40, "Rb_min", "1k", ["VNEG", "BMIN"])
place("npn", SX, SY, "Q_min", "QNPN", ["VOUT", "BMIN", "EMIN"])
place("res", SX + 160, SY - 40, "Re_min", str(RE_MIN), ["EMIN", "VNRAW"])
label(SX - 200, SY + 260, f"Q_min = BD139 (TO-126): {11.4/RE_MIN*1000:.1f} mA,"
                          f" {(40.5+5.6)*11.4/RE_MIN:.2f} W en el peor caso.")
label(SX - 200, SY + 300, f"Re_min {RE_MIN} ohm / 3 W: acota el fallo en corto a"
                          f" {57.5/RE_MIN*1000:.0f} mA y {57.5**2/RE_MIN:.1f} W.")
label(SX - 200, SY + 340, "Con el, la carga minima ya no depende de R1 ni del pote.")
_touch(SX - 210, SY + 350)

# ==================================== 6. DIODOS DE PROTECCION (fig. 15) =======
block("6. DIODOS DE PROTECCION - obligatorios con Vout > 25 V (fig. 15)")
place("diode", 2260, 1300, "D_REV", "1N5408", ["0", "VOUT"])
place("diode", 2460, 1300, "D_IN",  "1N5408", ["VOUT", "VRAW"])
place("diode", 2660, 1300, "D_ADJ", "1N4148", ["VADJ", "VOUT"])

# =============================================== 7. SALIDA Y SHUNT (fig. 32) ==
block("7. SALIDA")
OX = 3440
place("res", OX, 640, "Rload", "R=limit(V(LOAD),0.01,1Meg)", ["VOUT", "VRTN"])
place("voltage", OX + 340, 640, "Vload", "100", ["LOAD", "0"])
place("res", OX, 900, "Rshunt", "0.33", ["VRTN", "0"])
place("res", OX, 1300, "Rfilt", "1k", ["VRTN", "SENSE"])
place("cap", OX + 160, 1300, "Cfilt", "100n", ["SENSE", "0"])
label(OX - 20, 1240, "shunt en el RETORNO (fig. 32) -> SENSE al lazo")
_touch(OX - 30, 1230)

# ============================== 8. REFERENCIA Y CONSIGNA DE CORRIENTE =========
block("8. REFERENCIA 2,5 V Y CONSIGNA DE CORRIENTE")
RY = 1980
place("voltage", 1440, RY, "Vaux", "12", ["VCC", "0"])
place("res", 1640, RY, "Rref", "2k2", ["VCC", "VREF25"])
place("TL431ED", 1830, RY + 80, "ref", None, ["VREF25", "0", "VREF25"])
place("cap", 1980, RY, "Cref", "100n", ["VREF25", "0"])
place("res", 2180, RY, "Rset", "22k", ["VREF25", "ISET"])
place("res", 2320, RY, "Rpot_i", "R=V(ISETADJ)*4700", ["ISET", "0"])
place("cap", 2320, RY + 220, "Cpot_i", "100n", ["ISET", "0"])
label(1400, RY + 280, "Vaux = trafo auxiliar de 1,5 VA + puente + 7812")
label(1400, RY + 320, "0..0,44 V en ISET  ->  limite de 0 a 1,33 A")
_touch(1400, RY + 330)

# ================================= 9. LAZO DE CORRIENTE (fig. 31 + fig. 32) ===
block("9. LAZO DE CORRIENTE - el operacional tira de ADJ (fig. 31 + 32)")
CY = 1980
place("LM358", 2760, CY, "U2", None, ["SENSE", "CCIN", "VCC", "VNEG", "CCOUT"])
place("res", 2620, CY + 220, "Rint", "10k", ["CCIN", "ISET"])
place("cap", 2800, CY + 220, "Cint", "1u", ["CCOUT", "CCIN"])
place("res", 2960, CY, "Rb", "4k7", ["CCOUT", "CCB"])
place("res", 2960, CY + 220, "Rbe", "10k", ["CCB", "VNEG"])
place("npn", 3140, CY, "Qcc", "QNPN", ["VADJ", "CCB", "VNEG"])
label(2620, CY + 460, "Integrador a 16 Hz. Mientras no limita, CCOUT=0 y Qcc esta cortado.")
label(2620, CY + 500, "Qcc: BC546 (Vceo 65 V). Su colector ve VADJ, hasta 40 V.")
label(2620, CY + 540, "Emisor y Rbe en VNEG (-5 V): con ellos en la referencia, Qcc se satura.")
_touch(2620, CY + 510)

# ======================================= 8b. REFERENCIA NEGATIVA =============
# Es lo que permite bajar a 0 V: el chip mantiene OUT-ADJ = 1,25 V, asi que
# para que OUT llegue a cero, ADJ tiene que poder bajar a -1,25 V.  La pata de
# referencia del LM337 va a VRTN (al BORNE), no a masa, para que la caida del
# shunt siga compensada.  De propina, el lazo de CC ya no tiene suelo: mantiene
# la consigna hasta el cortocircuito franco.
block("8b. REFERENCIA NEGATIVA - permite 0 V y CC hasta el corto franco")
NY = 2520
place("voltage", 1440, NY, "Vneg",  "-5",   ["VNEG", "0"])
place("voltage", 1240, NY, "Vnraw", str(VNRAW), ["VNRAW", "0"])
place("bv",      1640, NY, "Bnref", "V=V(VRTN)-1.25", ["VNREF", "0"])
place("res",     1840, NY, "Rnbleed", "220", ["0", "VNREF"])
label(1400, NY + 240, "Vnraw = bruto del auxiliar (-17 V), ANTES del 79L05: el retorno de Q_min.")
label(1400, NY + 280, "Vneg  = -5 V del auxiliar (79L05), V- del LM358 y base de Q_min.")
label(1400, NY + 320, "Bnref = LM337 a -1,25 V (como el P223): pata de referencia en VRTN.")
label(1400, NY + 360, "Su corriente vuelve al COMUN, no por el shunt: tension Y corriente exactas.")
label(1400, NY + 400, "Rnbleed 220 ohm (el valor del P223) le da su carga minima.")
label(1400, NY + 440, "Qcc NO tira contra esta referencia sino contra los -5 V (como Silicon")
label(1400, NY + 480, "Chip): contra -1,25 se satura y pierde el CC en un corto franco.")
_touch(1400, NY + 490)

# ================================================ 10. MANDOS DEL PANEL ========
block("10. MANDOS")
MX2 = 3560
place("voltage", MX2, 1980, "Vset", "0.5", ["VSET", "0"])
place("voltage", MX2 + 180, 1980, "Vsetf", "0.5", ["VSETF", "0"])
place("voltage", MX2 + 360, 1980, "Visetadj", "1", ["ISETADJ", "0"])
label(MX2 - 40, 2260, f"Vset 0..1 = pote GRUESO, 0..{R2_COARSE} ohm")
label(MX2 - 40, 2300, f"Vsetf 0..1 = pote FINO, 0..{R2_FINE} ohm" f"  ({1.25*R2_FINE/R1_TOTAL:.1f} V de recorrido)")
label(MX2 - 40, 2340, "Visetadj 0..1 = pote de corriente 0..4k7")
_touch(MX2 - 40, 2350)

# ============================ MODELO TERMICO (fuera del circuito) =============
block("MODELO TERMICO - no es circuito, es instrumentacion (1 V = 1 C)")
TY2 = 2900
place("voltage", 0, TY2, "Vamb", "25", ["AMB", "0"])
place("res", 200, TY2, "Rth_sa", "2", ["TSINK", "AMB"])
place("cap", 380, TY2, "Cth_sa", "20", ["TSINK", "AMB"])
place("res", 560, TY2, "Rth_js", "2.3", ["Tj", "TSINK"])
place("cap", 740, TY2, "Cth_js", "0.02", ["Tj", "TSINK"])
place("bi", 940, TY2, "Bheat",
      "I=limit((V(VRAW)-V(VOUT))*abs(I(Rshunt)+I(R1)+Ic(Q_min)),0,500)", ["AMB", "Tj"],
      window3="24 104")
label(0, TY2 + 300, "Rth_js 2,3 C/W (TO-220) + Rth_sa 2 C/W (disipador).")
_touch(0, TY2 + 310)
block(None)

# ==================================== DIRECTIVAS (fuera del circuito) =========
DX, DY = -400, 3360
label(DX, DY - 60, "=== DIRECTIVAS ===")
directive(DX, DY, ".param TAP=2")
directive(DX, DY + 32, ".model SWMAN SW(Ron=10m Roff=1G Vt=6 Vh=2 level=2)")
directive(DX, DY + 64, "K1 Lp1 Ls1 0.999\\nK2 Lp2 Ls2 0.999\\nK3 Lp3 Ls3 0.999")
directive(DX, DY + 160, ".global Tj")
directive(DX, DY + 192,
          ".model 1N5408 D(Is=63.0n Rs=14.1m Bv=1000 Ibv=10u Cjo=53p M=0.333 N=1.30 Eg=1.11)")
directive(DX, DY + 224,
          ".model 1N4148 D(Is=2.52n Rs=0.568 N=1.752 Cjo=4p M=0.4 tt=20n Iave=200m Vpk=75)")
directive(DX, DY + 256,
          ".model QNPN NPN(IS=1e-14 BF=200 VAF=100 RB=10 RC=1 CJE=11p CJC=4p TF=1n)")
directive(DX, DY + 288, ".lib LM317HV.sub\\n.lib TL431ED.sub\\n.lib LM358.sub")
directive(DX, DY + 384, ".ic V(Tj)=25 V(TSINK)=25")
directive(DX, DY + 416, ".options reltol=1e-3 abstol=1u vntol=1u")
directive(DX, DY + 448, ".tran 0 1.5 0 100u startup uic")

label(DX + 900, DY, "psu_cvcc - Fuente lineal DIY con LM317HV, CV y CC ajustables")
label(DX + 900, DY + 32, "Circuitos de aplicacion de TI SNVS773D rev D.")
label(DX + 900, DY + 64, "Protecciones de sobrecorriente, cortocircuito y")
label(DX + 900, DY + 96, "sobretemperatura: las NATIVAS del chip.")
label(DX + 900, DY + 160, "uic NO es opcional: sin el, el .op sale NaN.")
label(DX + 900, DY + 192, "Los detalles estan en el README del directorio.")
label(DX + 900, DY + 256, "OJO 1: el pote llega a 40,6 V en cualquier toma. Con TAP=1 o")
label(DX + 900, DY + 288, "TAP=2, pasado el tope, el regulador entra en DROPOUT.")
label(DX + 900, DY + 352, "OJO 2: en TAP=3, en vacio y con la red a 253 V, el diferencial")
label(DX + 900, DY + 384, "llega a 59,1 V contra los 60 V del MAXIMO ABSOLUTO (8.3.2).")
label(DX + 900, DY + 416, "NO bajar del 20 % del pote estando en TAP=3.  Decision tomada")
label(DX + 900, DY + 448, "a sabiendas: tres devanados de 13 V no caben con margen.")

# ====================================== INSTRUMENTACION (fuera del circuito) ==
# Se reparte en columnas automaticamente para que no se pisen los textos: las
# lineas largas (las de potencia sumada) van aparte, a lo ancho.
MX, MY = 1700, 3360
label(MX, MY - 60, "=== INSTRUMENTACION: los resultados salen en el .log (Ctrl+L) ===")

M = "{TM1} TO {TM2}"
MEAS = [
    ".param TM1=1.2 TM2=1.5",
    f".meas TRAN Vout_dc      AVG V(VOUT,VRTN)           FROM {M}",
    f".meas TRAN Vout_pp      PP  V(VOUT,VRTN)           FROM {M}",
    f".meas TRAN Vout_min     MIN V(VOUT,VRTN)           FROM {M}",
    f".meas TRAN Vout_pico    MAX V(VOUT,VRTN)           FROM 0 TO {{TM2}}",
    f".meas TRAN Iout_dc      AVG I(Rshunt)              FROM {M}",
    f".meas TRAN Iload_dc     AVG I(Rload)               FROM {M}",
    f".meas TRAN I_div        AVG I(R2c)                 FROM {M}",
    f".meas TRAN Iout_pp      PP  I(Rshunt)              FROM {M}",
    f".meas TRAN Vraw_dc      AVG V(VRAW)                FROM {M}",
    f".meas TRAN Vraw_pp      PP  V(VRAW)                FROM {M}",
    f".meas TRAN Headroom     MIN V(VRAW)-V(VOUT)        FROM {M}",
    ".meas TRAN Rechazo_dB   PARAM 20*log10(Vraw_pp/max(Vout_pp,1n))",
    f".meas TRAN Vadj_dc      AVG V(VADJ)                FROM {M}",
    f".meas TRAN Vnref_dc     AVG V(VNREF)               FROM {M}",
    f".meas TRAN Vref_2v5     AVG V(VREF25)              FROM {M}",
    f".meas TRAN V_iset       AVG V(ISET)                FROM {M}",
    f".meas TRAN V_sense      AVG V(SENSE)               FROM {M}",
    f".meas TRAN CCout        AVG V(CCOUT)               FROM {M}",
    f".meas TRAN Ic_Qcc       AVG Ic(Qcc)                FROM {M}",
    ".meas TRAN En_CC        PARAM if(Ic_Qcc>1m,1,0)",
    ".meas TRAN Ilim_A       PARAM V_iset/0.33",
    f".meas TRAN I_aux        AVG -I(Vaux)               FROM {M}",
    f".meas TRAN Ipk_diodo    MAX I(D_B2)                FROM {M}",
    f".meas TRAN Irms_sec     RMS I(Rs3)                 FROM {M}",
    f".meas TRAN Tj_med       AVG V(Tj)                  FROM {M}",
    f".meas TRAN Tj_max       MAX V(Tj)                  FROM 0 TO {{TM2}}",
    f".meas TRAN Tsink        AVG V(TSINK)               FROM {M}",
    ".meas TRAN Margen_Tj    PARAM 125-Tj_max",
    f".meas TRAN P_LM317      AVG (V(VRAW)-V(VOUT))*(I(Rshunt)+I(R1)+Ic(Q_min)) FROM {M}",
    f".meas TRAN P_LM317_pk   MAX (V(VRAW)-V(VOUT))*(I(Rshunt)+I(R1)+Ic(Q_min)) FROM {M}",
    f".meas TRAN P_Rshunt     AVG V(VRTN)*I(Rshunt)      FROM {M}",
    f".meas TRAN P_R1         AVG V(VOUT,VR1T)*I(R1)     FROM {M}",
    f".meas TRAN P_TP1        AVG V(VR1T,VADJ)*I(RTP1)   FROM {M}",
    f".meas TRAN P_R2c        AVG V(VADJ,VMIDP)*I(R2c)   FROM {M}",
    f".meas TRAN P_R2f        AVG V(VMIDP,VNREF)*I(R2f)  FROM {M}",
    f".meas TRAN I_min        AVG Ic(Q_min)              FROM {M}",
    ".meas TRAN I_minload    PARAM I_div+I_min",
    f".meas TRAN P_Q_min      AVG V(VOUT,EMIN)*Ic(Q_min) FROM {M}",
    f".meas TRAN P_Re_min     AVG V(EMIN,VNRAW)*I(Re_min) FROM {M}",
    f".meas TRAN Vce_Q_min    MAX V(VOUT,EMIN)           FROM 0 TO {{TM2}}",
    f".meas TRAN P_Rbleed     AVG V(VRAW)*I(Rbleed)      FROM {M}",
    f".meas TRAN P_Rsnub      AVG V(NSNUB,ACLO)*I(Rsnub) FROM {M}",
    f".meas TRAN P_Rfilt      AVG V(VRTN,SENSE)*I(Rfilt) FROM {M}",
    f".meas TRAN P_Rref       AVG V(VCC,VREF25)*I(Rref)  FROM {M}",
    f".meas TRAN P_Rset       AVG V(VREF25,ISET)*I(Rset) FROM {M}",
    f".meas TRAN P_Rpot_i     AVG V(ISET)*I(Rpot_i)      FROM {M}",
    f".meas TRAN P_Rb         AVG V(CCOUT,CCB)*I(Rb)     FROM {M}",
    f".meas TRAN P_Rbe        AVG V(CCB,VNEG)*I(Rbe)     FROM {M}",
    f".meas TRAN P_Qcc        AVG V(VADJ,VNEG)*Ic(Qcc)   FROM {M}",
    f".meas TRAN P_Rint       AVG V(CCIN,ISET)*I(Rint)   FROM {M}",
    f".meas TRAN P_Rnbleed    AVG V(VNREF)*I(Rnbleed)    FROM {M}",
    # --- tension de pico sobre cada condensador, arranque incluido ---------
    f".meas TRAN Vc_bulk      MAX abs(V(VRAW))           FROM 0 TO {{TM2}}",
    f".meas TRAN Vc_in        MAX abs(V(VRAW))           FROM 0 TO {{TM2}}",
    f".meas TRAN Vc_snub      MAX abs(V(ACHI,NSNUB))     FROM 0 TO {{TM2}}",
    f".meas TRAN Vc_adj       MAX abs(V(VADJ,VNEG))      FROM 0 TO {{TM2}}",
    f".meas TRAN Vc_out       MAX abs(V(VOUT))           FROM 0 TO {{TM2}}",
    f".meas TRAN Vc_filt      MAX abs(V(SENSE))          FROM 0 TO {{TM2}}",
    f".meas TRAN Vc_ref       MAX abs(V(VREF25))         FROM 0 TO {{TM2}}",
    f".meas TRAN Vc_pot_i     MAX abs(V(ISET))           FROM 0 TO {{TM2}}",
    f".meas TRAN Vc_int_max   MAX V(CCOUT,CCIN)          FROM 0 TO {{TM2}}",
    f".meas TRAN Vc_int_min   MIN V(CCOUT,CCIN)          FROM 0 TO {{TM2}}",
    # --- semiconductores ---------------------------------------------------
    f".meas TRAN Vce_Qcc      MAX V(VADJ,VNEG)           FROM 0 TO {{TM2}}",
    f".meas TRAN Ipk_D_REV    MAX abs(I(D_REV))          FROM 0 TO {{TM2}}",
    f".meas TRAN Ipk_D_IN     MAX abs(I(D_IN))           FROM 0 TO {{TM2}}",
    f".meas TRAN Ipk_D_ADJ    MAX abs(I(D_ADJ))          FROM 0 TO {{TM2}}",
]
LARGAS = [
    f".meas TRAN P_puente     AVG V(ACLO,VRAW)*I(D_B1)+V(ACHI,VRAW)*I(D_B2)"
    f"-V(ACHI)*I(D_B3)-V(ACLO)*I(D_B4) FROM {M}",
    f".meas TRAN P_sec        AVG V(NS1,TAP2)*I(Rs1)+V(NS2,TAP1)*I(Rs2)"
    f"+V(NS3,ACLO)*I(Rs3) FROM {M}",
    f".meas TRAN P_prim       AVG V(NP1,NEUTRAL)*I(Rp1)+V(NP2,NEUTRAL)*I(Rp2)"
    f"+V(NP3,NEUTRAL)*I(Rp3) FROM {M}",
]
COLW, ROWS = 860, 13
for i in range(0, len(MEAS), ROWS):
    directive(MX + (i // ROWS) * COLW, MY, "\\n".join(MEAS[i:i + ROWS]))
directive(MX, MY + ROWS * 32 + 64, "\\n".join(LARGAS))

# ================================================= recuadros de cada bloque ===
for title, pts in blocks.items():
    if title is None or not pts:
        continue
    x1 = min(p[0] for p in pts) - 40
    y1 = min(p[1] for p in pts) - 80
    x2 = max(p[0] for p in pts) + 40
    y2 = max(p[1] for p in pts) + 40
    draws.append(f"RECTANGLE Normal {x1} {y1} {x2} {y2} 2")
    texts.append(f"TEXT {x1 + 24} {y1 + 28} Left 2 ;{title}")

# ===================================================================== salida =
body = ["Version 4", "SHEET 1 4600 4400"]
body += wires + flags + syms + texts + draws
OUT.write_text("\n".join(body) + "\n", encoding="ascii")
print(f"escrito {OUT}")
print(f"  {len([s for s in syms if s.startswith('SYMBOL')])} simbolos, "
      f"{len(wires)} hilos, {len(flags)} etiquetas, {len(draws)} trazos, "
      f"{len(texts)} textos")
