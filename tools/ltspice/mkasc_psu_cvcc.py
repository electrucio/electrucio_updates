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

CONVENCIONES DE DIBUJO (se van aplicando bloque a bloque; las que ya estan
hechas son la 4, la 5 y la 9):

1. ALINEAR ANTES DE RUTEAR.  Si un camino necesita codos, casi siempre es que
   el componente esta a la altura equivocada: se mueve la pieza para que su pin
   caiga al nivel del destino y el hilo sale recto.  Mirar a que distancia del
   origen cae cada pin (la base de un npn cae 48 por debajo, p. ej.).
2. MASAS AL MISMO NIVEL, cada una con su propio hilo hasta alli.  Colgando de
   un rail comun los pies NO pueden quedar alineados, porque el cuerpo de un
   condensador mide 64 y el de una resistencia 96.
3. La masa de un bloque cuelga del CENTRO de su rail inferior, no de la esquina.
4. ETIQUETAS solo para: railes de alimentacion, lo que cruza a otro bloque, y
   los puntos de prueba que usan las .meas.  UNA por red; las demas sobran en
   cuanto hay hilo.
5. Si una etiqueta queda pegada a otra, se saca el hilo con wire() hasta donde
   haya sitio y se pone alli con tag().  Pasa con pines vecinos (las dos patas
   de un operacional estan a 32 una de otra).
6. Nada de diagonales: wire() revienta si un tramo no es H o V.
7. DESPUES DE CADA BLOQUE, comprobar que el netlist no se ha movido:
       python3 tools/ltspice/asc2net.py <asc> --diff referencia.net
   Tiene que decir EQUIVALENTES.  Es lo que hace seguro iterar en el dibujo.

Lo que todavia no esta cableado se conecta por ETIQUETAS DE RED: cada pin lleva
un tramo corto de hilo y su etiqueta.  Es inequivoco y no tiene cruces, pero hay
que leer cadenas de texto para saber que va con que.

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
VREF_NEG = "VREF_-1v25"       # el nodo dice su valor: -1,25 V bajo VRTN
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
    "LM337":   [(0, 48),  (64, 0), (-64, 0)],
    "LM358":   [(-32, 16), (-32, -16), (0, -32), (0, 32), (32, 0)],
    "TL431ED": [(0, -64), (0, 64), (-48, 40)],
    # Rotativo 1P3T de Bordodynov.  Pin 1 = comun (derecha); 2, 3 y 4 = las
    # tres posiciones (izquierda), que conducen con SET=1, 2 y 3; 5 = "P", el
    # nodo de mando, que el modelo pone a SET voltios con una 100k interna.
    "1P3T_":   [(48, 0), (-32, -32), (-48, 0), (-32, 32), (0, -64)],
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
    "LM337":   [(0, 1), (1, 0), (-1, 0)],
    "LM358":   [(-1, 0), (-1, 0), (0, -1), (0, 1), (1, 0)],
    "TL431ED": [(0, -1), (0, 1), (-1, 0)],
    "1P3T_":   [(1, 0), (-1, 0), (-1, 0), (-1, 0), (0, -1)],
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


def wire(*pts):
    """Hilo por los puntos dados, segmento a segmento.

    Solo admite tramos HORIZONTALES o VERTICALES: una diagonal en LTspice
    conecta igual pero se lee fatal, asi que es mejor que reviente aqui y se
    ponga el codo a mano.  Los puntos se cuentan para el recuadro del bloque.
    """
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        assert x1 == x2 or y1 == y2, f"tramo diagonal {(x1, y1)}->{(x2, y2)}"
        wires.append(f"WIRE {x1} {y1} {x2} {y2}")
        _touch(x1, y1)
        _touch(x2, y2)


def tag(pt, net):
    """Etiqueta de red suelta en (x, y), para el final de un hilo propio.

    Lo que permite ALEJAR una etiqueta del componente: en vez de dejarla pegada
    al pin, se tira un hilo hasta donde haya sitio y se etiqueta alli.  Es la
    diferencia entre que se lea y que choque con el nombre y el valor de la
    pieza de al lado.
    """
    flags.append(f"FLAG {pt[0]} {pt[1]} {net}")
    _touch(pt[0] - 8, pt[1] - 24)
    _touch(pt[0] + 9 * len(net), pt[1] + 24)
    return pt


def place(sym, x, y, name, value, nets, rot="R0", lead=LEADLEN, window3=None):
    """Coloca `sym` en (x,y) con giro `rot` y devuelve el extremo de cada pin.

    `nets` lleva un nombre de red por pin, en orden de SpiceOrder.  Un **None**
    en vez de nombre deja ese pin SIN etiqueta: el tramo corto se dibuja igual,
    pero la conexion la hace quien llama con wire(), que es lo que convierte
    esto en un esquematico de verdad en vez de en un netlist dibujado.

    Devuelve la lista de extremos (x, y) en el mismo orden, para cablearlos.
    """
    syms.append(f"SYMBOL {sym} {x} {y} {rot}")
    if window3 is not None:
        syms.append(f"WINDOW 3 {window3} Left 2")
    syms.append(f"SYMATTR InstName {name}")
    if value is not None:
        syms.append(f"SYMATTR Value {value}")
    _touch(x - 40, y - 24)
    _touch(x + 64, y + 128)                      # sitio del texto del valor
    extremos = []
    for (dx, dy), (lx, ly), net in zip(PINS[sym], LEAD[sym], nets):
        rx, ry = ROT[rot](dx, dy)
        rlx, rly = ROT[rot](lx, ly)
        px, py = x + rx, y + ry
        ex, ey = px + rlx * lead, py + rly * lead
        wires.append(f"WIRE {px} {py} {ex} {ey}")
        extremos.append((ex, ey))
        if net is None:                      # lo cablea quien llama
            _touch(ex - 8, ey - 8)
            _touch(ex + 8, ey + 8)
            continue
        flags.append(f"FLAG {ex} {ey} {net}")
        _touch(ex - 8, ey - 24)
        _touch(ex + 9 * len(net), ey + 24)
    return extremos


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
# V1 subida 64 y Rgnd bajada: asi el neutro sale a y=704, que es una altura
# libre de punta a punta (a 768 chocaba con la etiqueta "TRAFO 2"), y Rgnd
# cuelga DEL HILO de neutro en vez de estar unida solo por la etiqueta, que es
# lo unico que hacia este bloque.
v1 = place("voltage", -320, 576, "V1", "SINE(0 325 50)", ["LIVE", "NEUTRAL"])
rgnd = place("res", -160, 720, "Rgnd", "1G", [None, "0"])
label(-380, 1000, "Rgnd solo ata el neutro")
label(-380, 1040, "a la masa del simulador.")
_touch(-390, 1050)

# ================================================== 2. LOS TRES TRAFOS ========
# Misma x, apilados en vertical.  Primario a x=TXP, secundario a x=TXS.
# Secundarios en serie de arriba abajo: TAP3 -> TAP2 -> TAP1 -> ACLO.
block("2. TRES TRANSFORMADORES ~13 Vrms EN SERIE + SELECTOR DE TOMAS 1P3T")
TXP, TXS, TSTEP = 480, 720, 560
# Cada transformador es una cadena en serie por lado: LIVE - RF - Lp - Rp -
# NEUTRAL arriba, y la toma de arriba - Ls - Rs - la de abajo en el secundario.
# Cableadas, se ven como cadenas; con etiquetas habia que emparejar textos.
#
# Que se queda etiquetado y por que:
#   LIVE / NEUTRAL  railes de red, alimentan los tres transformadores
#   NP{n} / NS{n}   los miden P_prim y P_sec
#   TAP3 / TAP2 / TAP1 / ACLO  cruzan al selector y al puente
#   LP{n}           no lo usa nadie, pero se QUEDA: quitarlo renombra el nodo
#                   a N00x y entonces el --diff deja de poder demostrar que el
#                   cambio es solo cosmetico.  Seis etiquetas invisibles no
#                   valen perder esa garantia.
#
# Las tomas se etiquetan UNA sola vez, en el pie de cada Rs; la cabeza del Ls
# siguiente va sin etiqueta porque el hilo ya la trae.
colas, red = [], []
for k, (arriba, abajo) in enumerate([("TAP3", "TAP2"), (None, "TAP1"),
                                     (None, "ACLO")]):
    n, y0 = k + 1, 160 + k * TSTEP
    rf = place("res", TXP, y0 - 176, f"RF{n}", "0.5m", [None, f"LP{n}"])
    lp = place("ind", TXP, y0, f"Lp{n}", "50", [None, f"NP{n}"])
    rp = place("res", TXP, y0 + 176, f"Rp{n}", "70", [None, None])
    ls = place("ind", TXS, y0, f"Ls{n}", "160m", [arriba, f"NS{n}"])
    rs = place("res", TXS, y0 + 176, f"Rs{n}", "0.18", [None, abajo])
    wire(rf[1], lp[0])                    # primario: RF -> Lp
    wire(lp[1], rp[0])                    # primario: Lp -> Rp  (nodo NP)
    wire(ls[1], rs[0])                    # secundario: Ls -> Rs (nodo NS)
    line(600, y0 + 8, 600, y0 + 104)      # nucleo, entre los dos devanados
    line(616, y0 + 8, 616, y0 + 104)
    label(184, y0 + 40, f"TRAFO {n}")
    _touch(160, y0 + 24)
    colas.append((rs[1], ls[0]))
    red.append((rf[0], rp[1]))            # (cabeza LIVE, pie NEUTRAL) del primario

# LOS DOS BUSES DE RED, uno a CADA LADO de la columna de primarios.  Es lo que
# evita que se crucen: las tomas de LIVE (-32, 528, 1088) y las de NEUTRAL
# (464, 1024, 1584) van intercaladas en altura, asi que con los dos buses al
# mismo lado cada derivacion de uno cruzaria el bus del otro tres veces.  Con
# NEUTRAL a la izquierda (x=400) y LIVE a la derecha (x=560, en el hueco que
# queda antes del nucleo), no se cruza ni un hilo.
XN, XL = 400, 560
wire(*[(XN, y) for y in (464, 704, 1024, 1584)])   # bus de neutro (704 = la acometida)
wire(*[(XL, y) for y in (-32, 528, 1088)])         # bus de fase
for live, neutro in red:
    wire((XL, live[1]), live)             # bus de fase -> cabeza del primario
    wire((XN, neutro[1]), neutro)         # pie del primario -> bus de neutro

# Y la cadena entre transformadores: el pie de un secundario con la cabeza del
# siguiente.  Son los nodos TAP2 y TAP1, y es lo que hace VISIBLE que los tres
# secundarios van en serie, que era lo unico que no se leia de este bloque.
for (pie, _), (_, cabeza) in zip(colas, colas[1:]):
    wire(pie, cabeza)

# ============================================ 3. SELECTOR MANUAL DE TOMAS =====
# UN rotativo de verdad, el 1P3T_ de Alexander Bordodynov, en vez de tres
# interruptores sueltos con tres fuentes de mando.  Es una sola pieza, se lee
# como el rotativo del panel, y su SET sale directo de nuestro .param TAP.
#
# Va ESPEJADO (M180) a proposito: sus posiciones 1, 2 y 3 salen de arriba abajo,
# pero en la pila de transformadores TAP3 esta ARRIBA.  Sin espejar, los tres
# hilos se cruzarian.
# SIN block() propio: el abanico de las tomas cruza hasta la columna de
# secundarios, asi que los dos marcos se solapaban 128 x 1506.  Cableados, los
# transformadores y el selector son un solo conjunto funcional y comparten
# recuadro.
SX, SY = 1240, 704
# Ron=10m a proposito, NO el 1u que trae por defecto: es la resistencia de
# contacto de un rotativo real, y es lo que tenia el modelo SWMAN anterior.  Con
# 1u el rail sale 0,1-0,2 V mas alto porque el interruptor deja de frenar los
# picos de carga del deposito, que llegan a 5 A.
# Las tres posiciones van SIN etiqueta: el hilo ya trae la toma, y la etiqueta
# vive en la cadena de secundarios, que es donde significa algo.  ACHI si se
# queda: es la salida del selector y cruza al puente y al amortiguador.
sel = place("1P3T_", SX, SY, "SW1", "SET={TAP} Ron=10m",
            ["ACHI", None, None, None, "PSEL"], rot="M180")

# Las tres tomas se abren en abanico desde la columna de secundarios hasta el
# rotativo, cada una por su carril vertical para que no se crucen.  La de en
# medio sale recta porque el rotativo esta puesto justo a su altura.
# Los tres hilos arrancan de un EXTREMO de la cadena, no de un punto cualquiera
# en medio de un tramo: colas[k] = (pie del Rs, cabeza del Ls) de cada
# transformador, o sea los nodos de las tomas.  Enganchar a mitad de un hilo
# conecta en LTspice pero asc2net no lo ve, y el --diff lo canto (TAP1 -> N001).
tap3, tap2, tap1 = colas[0][1], colas[1][1], colas[1][0]
wire(tap3, (1000, tap3[1]), (1000, SY - 32), sel[3])
wire(tap2, sel[2])                                 # recto: el rotativo esta a su altura
wire(tap1, (1060, tap1[1]), (1060, SY + 32), sel[1])
label(950, 1480, "SET sale del .param TAP: 1, 2 o 3.")
label(950, 1520, "PSEL es el nodo de mando interno del modelo.")
_touch(950, 1530)

# ============================================== 4. PUENTE Y DEPOSITO ==========
block("4. PUENTE Y DEPOSITO")
# BY 856 y no 900: asi el rail de VRAW cae en y=560, que es EXACTAMENTE la
# altura del pin IN del LM317.  El hilo entre bloques sale recto, sin codo.
BX1, BX2, BY = 1740, 1940, 856
# Un puente no se puede dibujar en ROMBO aqui: LTspice solo gira de 90 en 90 y
# un rombo pide diodos a 45.  La forma canonica cuando no hay diagonales son DOS
# RAMAS y DOS RAILES: cada rama lleva dos diodos apuntando hacia arriba y su
# juntura intermedia es una entrada de alterna; el rail de arriba junta los dos
# catodos (VRAW) y el de abajo los dos anodos (masa).  Se lee igual de bien y
# ademas deja los dos nodos de alterna a la vista.
# LAS DOS RAMAS VAN CAMBIADAS DE SITIO respecto a antes: la de ACHI pasa a ser
# la IZQUIERDA.  El motivo es el hilo que viene del selector: su nodo estaba en
# la rama lejana, y cualquier hilo recto hasta alla tiene que pasar por encima
# del nodo de la otra rama, o sea cortocircuitarlas.  Con ACHI cerca, el hilo
# del selector entra recto.
# Los NOMBRES se mueven con la rama (D_B2/D_B3 a la izquierda, D_B1/D_B4 a la
# derecha) para que el netlist salga identico: que rama se dibuje a que lado es
# arbitrario, pero perder el --diff por eso no.
db2 = place("diode", BX1, BY - 200, "D_B2", "1N5408", [None, "VRAW"], rot="R180")
db3 = place("diode", BX1, BY,       "D_B3", "1N5408", [None, None], rot="R180")
db1 = place("diode", BX2, BY - 200, "D_B1", "1N5408", [None, None], rot="R180")
db4 = place("diode", BX2, BY,       "D_B4", "1N5408", [None, None], rot="R180")

# El deposito se alinea al rail de VRAW, que pasa por la cabeza de las tres
# piezas: con el condensador a 636 y la resistencia a 620 los extremos caen
# todos a la misma altura (las alturas de los simbolos no son iguales, de ahi
# los dos numeros distintos).  Abajo cada uno lleva su propia masa, que es lo
# habitual en los desacoplos y evita un rail inferior larguisimo.
cbulk = place("cap", 2160, 592, "Cbulk", "10000u", [None, None])
rbleed = place("res", 2300, 576, "Rbleed", "10k", [None, None])
cin = place("cap", 2440, 592, "Cin", "0.1u", [None, None])

# Las dos junturas de alterna.  El hueco util de cada rama va de 688 a 760 (lo
# que dejan los dos cuerpos), asi que la toma se puede poner a cualquier altura
# de ahi dentro: ACHI a 704, que es la altura a la que sale el selector, y ACLO
# a 744, para que las dos tomas se distingan y no parezcan un solo hilo.
ACHI_PT = (db2[0][0], 704)
ACLO_PT = (db1[0][0], 744)
wire(db3[1], ACHI_PT, db2[0])             # rama izquierda: la juntura es ACHI
wire(db4[1], ACLO_PT, db1[0])             # rama derecha: la juntura es ACLO
# ACLO sale un poco hacia fuera: su origen esta abajo del todo (el pie del
# tercer secundario) y asi la etiqueta queda fuera del cuerpo de los diodos.
wire(ACLO_PT, (2020, 744))
tag((2020, 744), "ACLO")
wire(db2[1], db1[1], cbulk[0], rbleed[0], cin[0])   # rail de VRAW

# MASAS AL MISMO NIVEL.  Colgando del mismo rail de arriba, los pies NO pueden
# quedar alineados: el cuerpo de un condensador mide 64 y el de una resistencia
# 96.  Asi que cada masa baja con su propio hilo hasta GND_Y y el simbolo de
# tierra se pone alli con tag().  La del puente cuelga del CENTRO del rail
# inferior, que es como se dibuja un puente, en vez de colgar de la esquina.
GND_Y = 1000
medio = ((db3[0][0] + db4[0][0]) // 2, db3[0][1])
wire(db3[0], medio, db4[0])               # rail de masa, partido en el centro
for pie in (medio, cbulk[1], rbleed[1], cin[1]):
    wire(pie, (pie[0], GND_Y))
    tag((pie[0], GND_Y), "0")

# Bajado para que su cabeza caiga EN el hilo de ACHI (y=704) en vez de colgar
# 76 mas arriba unido solo por etiqueta.
csnub = place("cap", 1540, 736, "Csnub", "0.1u", [None, None])
rsnub = place("res", 1540, 848, "Rsnub", "100",  ["NSNUB", "ACLO"])
wire(csnub[1], rsnub[0])                  # la juntura RC del amortiguador
label(1440, 1060, "amortiguador del secundario")
_touch(1440, 1070)
label(2100, 1060, "EN LA PLACA: dejar pads para un filtro CRC (Rcrc en serie en")
label(2100, 1100, "el rail con puente de 0 ohm, Cbulk2 en paralelo a la entrada).")
label(2100, 1140, "NO va montado: el rizado sin el ya esta dentro de spec comercial")
label(2100, 1180, "y la mejora cabe dentro del error del modelo.  Se decide MIDIENDO")
label(2100, 1220, "la unidad construida.  Valores medidos, en el README.")
_touch(2100, 1230)

# ================================================ 5. REGULADOR (fig. 16) ======
block("5. LM317HV:  Vout = 1,25*(R2c+R2f)/R1  (0 V con el pote a cero)")
UX, UY = 2720, 560
# --- el divisor, dibujado como la escalera que es -------------------------
# Primer bloque cableado con HILOS en vez de solo con etiquetas.  Las etiquetas
# se quedan: VOUT y VRAW cruzan a otros bloques, y VR1T / VADJ / VMIDP / VREF_-1v25
# son puntos de PRUEBA que usan las .meas de potencia (igual que los TP1-TP6 de
# Silicon Chip).  Los hilos no cambian el netlist -unen pines que ya estaban en
# la misma red-, solo hacen visible la topologia en vez de dejarla implicita en
# que dos cadenas de texto coincidan.
#
# La geometria esta elegida para que los extremos COINCIDAN y no haga falta ni
# un codo de mas:  OUT del chip y la patilla de arriba de R1 quedan a la misma
# altura, y el pie de cada resistencia cae justo sobre la cabeza de la
# siguiente, asi que VADJ y VMIDP son junturas de verdad.
# OUT y ADJ van sin etiqueta: el hilo los lleva a la escalera, donde R1 y TP1
# ya ponen VOUT y VADJ.  Dos etiquetas de la misma red en el mismo nodo no
# aportan nada y ensucian.
u1 = place("LM317HV", UX, UY, "U1", None, [None, None, "VRAW"])
r1 = place("res", UX + 180, 576, "R1", str(R1_FIX), ["VOUT", "VR1T"])
# OJO: LTspice antepone la inicial del prefijo cuando el InstName no
# empieza por ella, asi que en el netlist TP1 se llama RTP1 (ver .meas).
tp1 = place("res", UX + 180, 744, "TP1", str(R1_TRIM), [None, "VADJ"])
r2c = place("res", UX + 180, 888, "R2c", f"R=max(V(VSET)*{R2_COARSE},0.1)",
            [None, "VMIDP"])
r2f = place("res", UX + 180, 1032, "R2f", f"R=max(V(VSETF)*{R2_FINE},0.1)",
            [None, "VREF_-1v25"])
# Cadj va DEBAJO de U1, en el hueco que deja el chip, no a la derecha de la
# escalera: alli chocaba con Cout_hf y con el texto del valor de R2c.
cadj = place("cap", UX + 40, 904, "Cadj", CADJ, [None, "VNEG"])

wire(r1[1], (r1[1][0], tp1[0][1]))       # R1 -> TP1  (la red VR1T)
wire(tp1[1], r2c[0])                     # TP1 -> R2c (la red VADJ)
wire(r2c[1], r2f[0])                     # R2c -> R2f (la red VMIDP)
# El hilo de ADJ baja, recoge a Cadj por el camino y sigue hasta VADJ.  Se
# parte en dos tramos para que los extremos COINCIDAN en la patilla de Cadj y
# la juntura sea explicita, en vez de depender de que un extremo caiga encima
# de otro hilo.
wire(u1[0], (u1[0][0], cadj[0][1]), cadj[0])
# Los dos de salida, uno al lado del otro y colgando del MISMO rail: estaban
# unidos solo por etiqueta y Cout_hf 340 unidades mas abajo, asi que no se veia
# que van en paralelo.  Sus pies caen ya al mismo nivel, sin hilo de mas.
cout = place("cap", UX + 380, 592, "Cout", "10u", [None, "0"])
couthf = place("cap", UX + 500, 592, "Cout_hf", "100n", [None, "0"])
label(UX - 60, 400, f"R2c+R2f = dos potes de PANEL en serie ({R2_COARSE//1000}k"
                    f" grueso + {R2_FINE} fino), {40.5**2/R2_TOTAL*1000:.0f} mW en total.")
label(UX - 60, 360, "R2 a VREF_-1v25 = VRTN - 1,25 (cero a 0 V).  Cadj a -5 V (S.Chip): 80 dB (fig. 21).")
label(UX - 60, 320, f"R1+TP1 = {R1_TOTAL} ohm fija la ESCALA, no la carga minima:"
                    f" de eso se encarga Q_min.")
label(UX - 60, 280, "TP1 ajusta el fondo de escala (potes de panel: +-20 %).  Subirla lo baja.")
# --- los tres diodos de proteccion (fig. 15) ------------------------------
# Ya no son un bloque aparte colgando de un bus de VOUT.  Aquel dibujo hacia
# visible la DIRECCION de cada uno, pero no QUE protege cada uno, que es lo que
# de verdad hay que leer.  Cada diodo se pone en paralelo con la pieza que
# salva, y entonces la direccion se deduce sola:
#   D_IN   puentea el chip por encima: cuando la entrada se va a cero, Cout
#          tiene que descargarse por ahi y no hacia atras por el paso.
#   D_REV  en paralelo con Cout: clava la salida si la carga la empuja bajo cero.
#   D_ADJ  en paralelo con R1+TP1: por ahi se descarga Cadj.
# D_REV encaja JUSTO en el hueco de Cout (los dos miden 128 de pata a pata), asi
# que no necesita ni un hilo: nace en el rail y muere en la fila de masas.
din = place("diode", 2752, 484, "D_IN", "1N5408", [None, None], rot="R90")
dadj = place("diode", 3052, 748, "D_ADJ", "1N4148", [None, None], rot="R180")
drev = place("diode", 3192, 656, "D_REV", "1N5408", ["0", None], rot="R180")

# El rail de VOUT, con los puntos de los que cuelgan.  D_IN baja por los dos
# extremos del chip: a la derecha en 2860 y a la izquierda en el propio pin IN.
wire(u1[1], (2860, 560), r1[0], (3036, 560), cout[0], drev[1], couthf[0])
wire((3036, 560), dadj[1])                # rail -> catodo de D_ADJ
wire((2860, 560), (2860, 500), din[0])    # rail -> anodo de D_IN
wire(din[1], (2624, 500), u1[2])          # catodo de D_IN -> el pin IN
# Y VADJ se estira hasta D_ADJ.  De paso deja el nodo asomado en x=3036, que es
# por donde subira el colector de Qcc.
wire(cadj[0], tp1[1], (3036, 872), dadj[0])

label(UX - 60, 1320, "Los tres diodos son la fig. 15: obligatorios con Vout > 25 V.")
label(UX - 60, 1240, "Dos mandos independientes: VSET mueve el grueso y VSETF el fino.")
label(UX - 60, 1280, "Lo que ve el circuito es la SUMA de los dos.")
_touch(UX - 70, 270)
_touch(UX - 70, 1330)

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
# Movido a la derecha: a 4060 se solapaba con la salida (bloque 7) y con los
# mandos (10).  Con la hoja ensanchada a 5200 cabe holgado.
# Dibujado como lo que es: un sumidero de corriente.  La columna VOUT ->
# colector -> emisor -> Re_min -> VNRAW es el camino de los 8,8 mA, y Rb_min
# entra por la izquierda a fijar la base.  Asi se lee que la corriente la pone
# Re_min contra los -17 V, no el transistor.
SX, SY = 4400, 1590
rb = place("res", SX - 224, SY + 64, "Rb_min", "1k", ["VNEG", None],
           rot="R270")
q = place("npn", SX, SY, "Q_min", "QNPN", ["VOUT", None, None])
re_ = place("res", SX + 48, SY + 208, "Re_min", str(RE_MIN), [None, "VNRAW"])

wire(rb[1], q[1])                         # Rb_min -> base
tag(rb[1], "BMIN")
# El hilo va partido a proposito: la etiqueta solo engancha en un EXTREMO de
# tramo, no a mitad (convencion 5).
emin = (q[2][0], q[2][1] + 32)
wire(q[2], emin, re_[0])                  # emisor -> Re_min
tag(emin, "EMIN")                         # nodo de las .meas de potencia

# Las notas, bajo la columna: a media altura las cruzaba Re_min.
NOTA = SY + 420
label(SX - 224, NOTA, f"Q_min = BD139 (TO-126): {11.4/RE_MIN*1000:.1f} mA,"
                      f" {(40.5+5.6)*11.4/RE_MIN:.2f} W en el peor caso.")
label(SX - 224, NOTA + 40, f"Re_min {RE_MIN} ohm / 3 W: acota el fallo en corto a"
                           f" {57.5/RE_MIN*1000:.0f} mA y {57.5**2/RE_MIN:.1f} W.")
label(SX - 224, NOTA + 80, "Con el, la carga minima ya no depende de R1 ni del pote.")
_touch(SX - 234, NOTA + 90)

# =============================================== 7. SALIDA Y SHUNT (fig. 32) ==
block("7. SALIDA")
OX = 3440
# La columna de la derecha es el camino de la corriente de carga: entra por
# VOUT, baja por la carga hasta el BORNE (VRTN) y vuelve a masa por el shunt.
# Asi se ve de un vistazo que el shunt esta en el RETORNO y no en el positivo,
# que es la figura 32 del datasheet y la razon de que el divisor vuelva al
# borne.  El filtro de sensado sale en horizontal del propio borne.
# Subido 64: asi la cabeza de Rload cae en y=560, el rail de VOUT.
rload = place("res", OX, 576, "Rload", "R=limit(V(LOAD),0.01,1Meg)",
              [None, "VRTN"])
rshunt = place("res", OX, 836, "Rshunt", "0.33", [None, None])
# window3 mueve la ventana del VALOR: girada, LTspice la pone encima del
# nombre y sale "Rfil1k".  Las coordenadas son del marco del simbolo y se
# giran con el, asi que para bajarla 40 en pantalla con R270 hay que pedir
# (-40, 0), porque R270 lleva (a,b) a (b,-a).
rfilt = place("res", OX + 32, 778, "Rfilt", "1k", [None, "SENSE"],
              rot="R270", window3="-40 0")
cfilt = place("cap", OX + 144, 794, "Cfilt", "100n", [None, None])
vload = place("voltage", OX + 340, 576, "Vload", "100", ["LOAD", None])

# El borne se parte en el punto donde sale el sensado, para que los tres
# extremos coincidan ahi en vez de colgar uno a mitad de hilo.
borne = (rload[1][0], rfilt[0][1])
wire(rload[1], borne, rshunt[0])          # carga -> BORNE -> shunt
wire(borne, rfilt[0])                     # BORNE -> filtro de sensado
wire(rfilt[1], cfilt[0])                  # SENSE -> Cfilt

# Masas al mismo nivel, cada una con su hilo (convencion 2).
GND_SAL = 1140
for pie in (rshunt[1], cfilt[1], vload[1]):
    wire(pie, (pie[0], GND_SAL))
    tag((pie[0], GND_SAL), "0")
label(OX - 20, 1240, "shunt en el RETORNO (fig. 32) -> SENSE al lazo")
_touch(OX - 30, 1230)

# ============================== 8. REFERENCIA Y CONSIGNA DE CORRIENTE =========
block("8. REFERENCIA 2,5 V Y CONSIGNA DE CORRIENTE")
RY = 1980
# Dibujado con la forma que tiene: una REFERENCIA PARALELO (Rref alimenta al
# TL431 desde VCC y la pata de referencia vuelve al catodo) y, colgando de sus
# 2,5 V, el DIVISOR de la consigna (Rset arriba, el pote abajo, ISET en medio).
# En horizontal, como estaba, no se distinguia una cosa de la otra.
RX = 1640
vaux = place("voltage", 1440, RY, "Vaux", "12", ["VCC", None])
rref = place("res", RX, RY, "Rref", "2k2", [None, "VREF_2v5"])
tl = place("TL431ED", RX + 16, RY + 224, "ref", None, [None, None, None])
cref = place("cap", RX + 160, RY + 160, "Cref", "100n", [None, None])
rset = place("res", 2180, RY + 144, "Rset", "22k", [None, None])
rpot = place("res", 2180, RY + 304, "Rpot_i", "R=V(ISETADJ)*4700",
             ["ISET", None])
cpot = place("cap", 2340, RY + 304, "Cpot_i", "100n", [None, None])

wire(vaux[0], rref[0])                    # +12 V hasta Rref
wire(rref[1], tl[0])                      # Rref -> catodo del TL431
wire(tl[0], cref[0], rset[0])             # el rail de los 2,5 V
wire(tl[2], (tl[2][0], tl[0][1]), tl[0])  # la pata de referencia, al catodo
wire(rset[1], rpot[0])                    # divisor: la juntura es ISET
wire(rset[1], cpot[0])                    # ISET -> su condensador de panel

# Masas al mismo nivel (convencion 2).  Vaux es instrumentacion y lleva la suya
# justo debajo, para no arrastrar un hilo de 400 unidades por todo el bloque.
GND_REF = RY + 500
for pie in (tl[1], cref[1], rpot[1], cpot[1]):
    wire(pie, (pie[0], GND_REF))
    tag((pie[0], GND_REF), "0")
tag(vaux[1], "0")
label(1400, GND_REF + 60, "Vaux = trafo auxiliar de 1,5 VA + puente + 7812")
label(1400, GND_REF + 100, "0..0,44 V en ISET  ->  limite de 0 a 1,33 A")
_touch(1400, GND_REF + 110)
_touch(1400, RY + 330)

# ================================= 9. LAZO DE CORRIENTE (fig. 31 + fig. 32) ===
block("9. LAZO DE CORRIENTE - el operacional tira de ADJ (fig. 31 + 32)")
# 2060 y no 1980: Cint, al puentear el operacional por arriba, hizo crecer el
# bloque hacia los diodos.  CX se corrio 100 a la derecha para que la etiqueta
# ISET no choque con el texto del valor de Rpot_i, que se sale de su bloque.
CX, CY = 2860, 2060
# Segundo bloque cableado.  Dibujado como el integrador que es: Rint entra por
# la pata inversora y Cint PUENTEA el operacional por encima, de la salida de
# vuelta a esa misma pata.  Asi se ve de un vistazo que es un integrador y no
# hay que deducirlo de que "CCIN" aparezca en tres sitios.
#
# Giros: R90 deja el pin 1 a la DERECHA y R270 a la izquierda.  Importa porque
# el orden de los pines es el del netlist y no se puede cambiar: Rint quiere
# CCIN a la derecha (R90) y Rb quiere CCOUT a la izquierda (R270).
#
# Se quedan las etiquetas de CCIN, CCOUT y CCB porque son puntos de prueba de
# las .meas (V(CCOUT), P_Rb, P_Rbe, P_Rint, Vc_int); las duplicadas se van.
# Todo cuelga de (CX, CY) para poder mover el bloque entero de una pieza.
#
# ALINEACION: la base de Qcc se coloca a la MISMA altura que la salida del
# operacional (de ahi el CY-48 del transistor, porque su pin de base cae 48 por
# debajo de su origen).  Asi el camino salida -> Rb -> base es una recta y no
# hacen falta los dos codos que habia antes.
qcc = place("npn", CX + 340, CY - 48, "Qcc", "QNPN", ["VADJ", "CCB", "VNEG"])
rb = place("res", CX + 180, CY + 16, "Rb", "4k7", [None, None], rot="R270")
u2 = place("LM358", CX, CY, "U2", None, [None, "CCIN", "VCC", "VNEG", "CCOUT"])
rint = place("res", CX - 80, CY - 32, "Rint", "10k", [None, "ISET"], rot="R90")
cint = place("cap", CX + 32, CY - 160, "Cint", "1u", [None, None], rot="R90")
rbe = place("res", CX + 292, CY + 128, "Rbe", "10k", [None, "VNEG"])

# Rint y la pata inversora se tocan extremo con extremo, igual que Rb y la base
# de Qcc: por eso no hay hilo entre ellos.
wire(cint[0], u2[4])                      # Cint -> salida del operacional
wire(cint[1], u2[1])                      # Cint -> pata inversora (CCIN)
wire(u2[4], rb[0])                        # salida -> Rb, en linea recta
wire(qcc[1], rbe[0])                      # base de Qcc -> Rbe

# La pata NO inversora llevaba su etiqueta pegada a la inversora, a 32 de
# distancia, y en el GUI de LTspice las dos se pisaban.  Se saca el hilo por
# debajo y se etiqueta donde hay sitio.
# Baja hasta CY+320 y no CY+112: el hilo que llega del borne entra por la
# derecha, y a la altura de antes cruzaba el hilo base-Rbe de Qcc (x=3168).
# Por debajo de Rbe no hay nada que cruzar.
sense = (u2[0][0], CY + 320)
wire(u2[0], sense)
tag(sense, "SENSE")
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
# Bajado de 2520 a 2800: el bloque 8 crece hacia aqui y no puede subir,
# porque encima tiene los diodos de proteccion.
NY = 2800
# AQUI ESTABA Bnref, una fuente conductual V=V(VRTN)-1.25.  Ahora esta el
# LM337 de verdad, que es lo que lleva el P223: ADJ atado a VRTN y OUT dando
# VRTN - 1,25 V.  El modelo es el de TI (ver LM337.sub y LM337_N_TRANS.LIB).
# Se dibuja como la cadena que es: el bruto de -17 V entra por IN, sale por OUT
# a la izquierda del bleeder, y ADJ cuelga hacia abajo hasta su etiqueta.
# Igual que el LM317, NO TIENE PATA DE MASA: su corriente sale por IN.
nneg = place("voltage", 1240, NY, "Vneg",  "-5",   ["VNEG", None])
nraw = place("voltage", 1440, NY, "Vnraw", str(VNRAW), ["VNRAW", None])
lm337 = place("LM337", 1700, NY - 16, "U3", None, [None, None, None])
# Girada 180: asi su pin 1 queda abajo (a masa) y el 2 arriba (a la
# referencia), que es el orden que ya tenia el netlist.
nble = place("res",     1976, NY + 112, "Rnbleed", "220", [None, VREF_NEG],
             rot="R180")

wire(nraw[0], lm337[2])                   # el bruto de -17 V entra por IN
wire(lm337[1], nble[1])                   # OUT -> el bleeder, su carga minima
tag(lm337[0], "VRTN")                     # la referencia va al BORNE, no a masa

GND_NEG = NY + 200
for pie in (nneg[1], nraw[1], nble[0]):
    wire(pie, (pie[0], GND_NEG))
    tag((pie[0], GND_NEG), "0")
label(1400, NY + 240, "Vnraw = bruto del auxiliar (-17 V), ANTES del 79L05: el retorno de Q_min.")
label(1400, NY + 280, "Vneg  = -5 V del auxiliar (79L05), V- del LM358 y base de Q_min.")
label(1400, NY + 320, "U3 = LM337 a -1,25 V (como el P223): pata de referencia en VRTN.")
label(1400, NY + 360, "Su corriente vuelve al COMUN, no por el shunt: tension Y corriente exactas.")
label(1400, NY + 400, "Rnbleed 220 ohm (el valor del P223) le da su carga minima.")
label(1400, NY + 440, "Qcc NO tira contra esta referencia sino contra los -5 V (como Silicon")
label(1400, NY + 480, "Chip): contra -1,25 se satura y pierde el CC en un corto franco.")
_touch(1400, NY + 490)

# ================================================ 10. MANDOS DEL PANEL ========
block("10. MANDOS")
# MOVIDOS de (3560, 1980) a aqui: estaban justo en el pasillo vertical que
# necesita SENSE para bajar del borne al operacional.  Son tres fuentes ideales
# sin topologia, asi que el bloque que se mueve es este y no el lazo.
MX2 = 4160
# Los tres son cursores de pote, no se conectan entre si: lo unico que hay que
# cablear es su retorno.  Un pie cada una y los tres triangulos al mismo nivel.
MY2 = 2560
mandos = [place("voltage", MX2 + 180 * i, MY2, n, v, [red, None])
          for i, (n, v, red) in enumerate([("Vset", "0.5", "VSET"),
                                           ("Vsetf", "0.5", "VSETF"),
                                           ("Visetadj", "1", "ISETADJ")])]
GND_MAN = MY2 + 200
for m in mandos:
    wire(m[1], (m[1][0], GND_MAN))
    tag((m[1][0], GND_MAN), "0")
label(MX2 - 40, MY2 + 280, f"Vset 0..1 = pote GRUESO, 0..{R2_COARSE} ohm")
label(MX2 - 40, MY2 + 320, f"Vsetf 0..1 = pote FINO, 0..{R2_FINE} ohm" f"  ({1.25*R2_FINE/R1_TOTAL:.1f} V de recorrido)")
label(MX2 - 40, MY2 + 360, "Visetadj 0..1 = pote de corriente 0..4k7")
_touch(MX2 - 40, MY2 + 370)

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

# ======================= CONEXIONES ENTRE BLOQUES =============================
# Van DESPUES de block(None) a proposito: _touch no hace nada fuera de un
# bloque, asi que estos hilos no inflan ningun recuadro.  Si se dibujaran dentro
# del bloque de origen, la caja crecaria hasta el bloque de destino y los dos
# marcos se solaparian.  Las etiquetas de rail se quedan igual (convencion 4):
# el hilo hace visible el camino, la etiqueta sigue nombrando la red.
#
# El CAMINO DE POTENCIA, de izquierda a derecha y todo a la misma altura:
#   deposito --VRAW--> IN | LM317 | OUT --VOUT--> borne
# Las dos alturas estan elegidas para que estos dos tramos sean RECTOS: por eso
# el puente subio 44 y el bloque de salida 64.
wire(cin[0], u1[2])                       # deposito -> IN del regulador
wire(couthf[0], rload[0])                 # salida del regulador -> la carga
#
# La ENTRADA DE ALTERNA: del comun del rotativo a la rama de ACHI, recta y
# recogiendo de paso la cabeza del amortiguador.
wire(sel[0], csnub[0], ACHI_PT)           # selector -> amortiguador -> puente
#
# LA ACOMETIDA, de la red a los dos buses.  El neutro entra recto a su altura.
# La fase tiene que ir POR ENCIMA de todo: su bus es el de la derecha, asi que
# si entrase en horizontal cruzaria el bus de neutro y, peor, cortocircuitaria
# la columna de primarios por el medio.  Subir por fuera y bajar al primer
# transformador no cruza nada.
wire(v1[1], rgnd[0], (XN, 704))           # neutro -> Rgnd -> bus de neutro
wire(v1[0], (v1[0][0], -120), (XL, -120), (XL, -32))      # fase, por arriba
#
# EL LAZO DE CORRIENTE recoge sus dos entradas de dos sitios distintos:
#   - la CONSIGNA sale del divisor del bloque 8, justo al lado: sube por el
#     hueco que queda a la derecha de Cpot_i y entra a la altura exacta de
#     Rint, que es la de la pata inversora.  Un solo codo.
#   - el SENSADO viene del borne, que esta en la otra punta de la hoja y 1600
#     unidades mas arriba.  Baja por el pasillo de x=3700 (de ahi que los
#     mandos se hayan mudado) y entra por debajo del lazo.  Dos codos, que
#     son los que cuesta cruzar la hoja entera.
wire(cpot[0], (2356, 2044), rint[1])      # divisor de consigna -> Rint
wire(cfilt[0], (3700, cfilt[0][1]), (3700, sense[1]), sense)   # borne -> pata no inversora
#
# Y LA SALIDA del lazo: el colector de Qcc hasta el VADJ del regulador.  Sube
# 1108 unidades con UN SOLO codo, y eso solo es posible porque D_ADJ se mudo
# al bloque 5: su anodo deja el nodo VADJ asomado en x=3036, a la altura
# buena.  Con el bloque de diodos aparte habia que rodear el regulador por la
# izquierda con tres codos.  La etiqueta se queda en los DOS extremos: es el
# hilo mas largo de la hoja y conviene saber que es donde aterriza.
wire(qcc[0], (3264, 872), (3036, 872))    # Qcc tira de ADJ

# ==================================== DIRECTIVAS (fuera del circuito) =========
DX, DY = -400, 3360
label(DX, DY - 60, "=== DIRECTIVAS ===")
directive(DX, DY, ".param TAP=2")
directive(DX, DY + 32, ".lib 1P3T_.sub\\n.lib LM337.sub")
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
    f".meas TRAN Vnref_dc     AVG V(VREF_-1v25)               FROM {M}",
    f".meas TRAN Vref_2v5_dc  AVG V(VREF_2v5)              FROM {M}",
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
    f".meas TRAN P_R2f        AVG V(VMIDP,VREF_-1v25)*I(R2f)  FROM {M}",
    f".meas TRAN I_min        AVG Ic(Q_min)              FROM {M}",
    ".meas TRAN I_minload    PARAM I_div+I_min",
    f".meas TRAN P_Q_min      AVG V(VOUT,EMIN)*Ic(Q_min) FROM {M}",
    f".meas TRAN P_Re_min     AVG V(EMIN,VNRAW)*I(Re_min) FROM {M}",
    f".meas TRAN Vce_Q_min    MAX V(VOUT,EMIN)           FROM 0 TO {{TM2}}",
    f".meas TRAN P_Rbleed     AVG V(VRAW)*I(Rbleed)      FROM {M}",
    f".meas TRAN P_Rsnub      AVG V(NSNUB,ACLO)*I(Rsnub) FROM {M}",
    f".meas TRAN P_Rfilt      AVG V(VRTN,SENSE)*I(Rfilt) FROM {M}",
    f".meas TRAN P_Rref       AVG V(VCC,VREF_2v5)*I(Rref)  FROM {M}",
    f".meas TRAN P_Rset       AVG V(VREF_2v5,ISET)*I(Rset) FROM {M}",
    f".meas TRAN P_Rpot_i     AVG V(ISET)*I(Rpot_i)      FROM {M}",
    f".meas TRAN P_Rb         AVG V(CCOUT,CCB)*I(Rb)     FROM {M}",
    f".meas TRAN P_Rbe        AVG V(CCB,VNEG)*I(Rbe)     FROM {M}",
    f".meas TRAN P_Qcc        AVG V(VADJ,VNEG)*Ic(Qcc)   FROM {M}",
    f".meas TRAN P_Rint       AVG V(CCIN,ISET)*I(Rint)   FROM {M}",
    f".meas TRAN P_Rnbleed    AVG V(VREF_-1v25)*I(Rnbleed)    FROM {M}",
    # --- tension de pico sobre cada condensador, arranque incluido ---------
    f".meas TRAN Vc_bulk      MAX abs(V(VRAW))           FROM 0 TO {{TM2}}",
    f".meas TRAN Vc_in        MAX abs(V(VRAW))           FROM 0 TO {{TM2}}",
    f".meas TRAN Vc_snub      MAX abs(V(ACHI,NSNUB))     FROM 0 TO {{TM2}}",
    f".meas TRAN Vc_adj       MAX abs(V(VADJ,VNEG))      FROM 0 TO {{TM2}}",
    f".meas TRAN Vc_out       MAX abs(V(VOUT))           FROM 0 TO {{TM2}}",
    f".meas TRAN Vc_filt      MAX abs(V(SENSE))          FROM 0 TO {{TM2}}",
    f".meas TRAN Vc_ref       MAX abs(V(VREF_2v5))         FROM 0 TO {{TM2}}",
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
cajas = {}
for title, pts in blocks.items():
    if title is None or not pts:
        continue
    x1 = min(p[0] for p in pts) - 40
    y1 = min(p[1] for p in pts) - 80
    x2 = max(p[0] for p in pts) + 40
    y2 = max(p[1] for p in pts) + 40
    cajas[title] = (x1, y1, x2, y2)
    draws.append(f"RECTANGLE Normal {x1} {y1} {x2} {y2} 2")
    texts.append(f"TEXT {x1 + 24} {y1 + 28} Left 2 ;{title}")

# ===================================================================== salida =
body = ["Version 4", "SHEET 1 5200 4400"]
body += wires + flags + syms + texts + draws
OUT.write_text("\n".join(body) + "\n", encoding="ascii")
# Los recuadros NO deben tocarse: dos bloques encima se leen fatal y es el
# fallo mas facil de cometer al mover piezas, porque el marco se recalcula solo
# a partir de lo que hay dentro.  Mejor que avise aqui que descubrirlo mirando.
solapes = []
_items = list(cajas.items())
for i, (ta, (ax1, ay1, ax2, ay2)) in enumerate(_items):
    for tb, (bx1, by1, bx2, by2) in _items[i + 1:]:
        ox = min(ax2, bx2) - max(ax1, bx1)
        oy = min(ay2, by2) - max(ay1, by1)
        if ox > 0 and oy > 0:
            solapes.append((ox, oy, ta.split(".")[0], tb.split(".")[0]))

# Y los CRUCES de hilos, que es lo otro que se pide de un esquematico legible.
# Un cruce estricto -un tramo horizontal que atraviesa uno vertical sin que el
# punto sea extremo de ninguno de los dos- no conecta nada en LTspice, pero se
# lee mal y casi siempre significa que algo esta mal colocado.  Es mas facil
# arreglarlo aqui que descubrirlo mirando el dibujo.
_seg = [tuple(map(int, w.split()[1:5])) for w in wires]
_hor = [(min(a, c), max(a, c), b) for a, b, c, d in _seg if b == d]
_ver = [(a, min(b, d), max(b, d)) for a, b, c, d in _seg if a == c]
cruces = sorted({(x, y) for x0, x1, y in _hor for x, y0, y1 in _ver
                 if x0 < x < x1 and y0 < y < y1})

print(f"escrito {OUT}")
print(f"  {len([s for s in syms if s.startswith('SYMBOL')])} simbolos, "
      f"{len(wires)} hilos, {len(flags)} etiquetas, {len(draws)} trazos, "
      f"{len(texts)} textos")
if solapes:
    print(f"  AVISO: {len(solapes)} pares de bloques se solapan:")
    for ox, oy, ta, tb in sorted(solapes, reverse=True):
        print(f"    {ox:>5} x {oy:<5} entre el bloque {ta} y el {tb}")
else:
    print("  recuadros: ningun solape")
# Y el INVENTARIO de lo que falta por conectar: que railes siguen cruzando de
# bloque a bloque solo porque dos etiquetas coinciden.  No es un error -un rail
# etiquetado es legitimo (convencion 4)- pero es la lista de candidatos a la
# siguiente vuelta, y distingue los que ya tienen hilo de los que no.  Para
# saberlo hay que UNIR los extremos de los hilos: dos etiquetas de la misma red
# pueden estar ya cableadas entre si (SENSE, ISET) y entonces no cuentan.
_par = {}


def _find(a):
    _par.setdefault(a, a)
    while _par[a] != a:
        _par[a] = _par[_par[a]]
        a = _par[a]
    return a


for _w in wires:
    _x1, _y1, _x2, _y2 = map(int, _w.split()[1:5])
    _par[_find((_x1, _y1))] = _find((_x2, _y2))

_flag = {}
for _f in flags:
    _, _x, _y, _net = _f.split(None, 3)
    _flag.setdefault(_net, []).append((int(_x), int(_y)))


def _bloque(x, y):
    for _t, (_a, _b, _c, _d) in cajas.items():
        if _a <= x <= _c and _b <= y <= _d:
            return _t.split(".")[0]
    return "-"


sueltos = []
for _net, _pts in _flag.items():
    if _net == "0" or len(_pts) < 2:
        continue
    _bl = sorted({_bloque(x, y) for x, y in _pts})
    if len(_bl) > 1 and len({_find(_p) for _p in _pts}) > 1:
        sueltos.append((_net, _bl))
if sueltos:
    print(f"  por conectar: {len(sueltos)} railes cruzan de bloque por etiqueta")
    for _net, _bl in sorted(sueltos):
        print(f"    {_net:8} entre {' '.join(_bl)}")

if cruces:
    print(f"  AVISO: {len(cruces)} cruces de hilos:")
    for x, y in cruces:
        print(f"    ({x}, {y})")
else:
    print("  hilos: ningun cruce")
