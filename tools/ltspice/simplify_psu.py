#!/usr/bin/env python3
"""Deriva psu_simple/psu_simple.net desde psu_overengineered/psu.net.

Genera el DISENO 2 (poda del original).  El diseno 3, hecho desde cero, esta
en powersupply/psu_cvcc/ y no se deriva de nada: se escribe a mano.

Cada borrado va como patch() explicito: si el esquematico cambia esa linea,
esto revienta en vez de aplicarse a medias.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ltrun import Netlist

SRC = Path(__file__).resolve().parents[2] / "powersupply/psu_overengineered/psu.net"
DST = Path(__file__).resolve().parents[2] / "powersupply/psu_simple/psu_simple.net"

n = Netlist.from_file(SRC)


def drop(*lines):
    for l in lines:
        n.patch(l + "\n", "")


# ---------------------------------------------------------------- 1) tomas
# control de reles: 2 comparadores, 2 MOSFET, divisores, histeresis, flybacks
drop("XU3 VCC RELAY2 NC_01 NC_02 VACpos N015 VACpos N013 NC_03 NC_04 Relay_2A2B Tfly=2m",
     "XU4 VCC RELAY3 NC_05 NC_06 N015 N025 N015 N023 NC_07 NC_08 Relay_2A2B Tfly=2m",
     "XU2 N009 N006 VCC 0 N007 LM339 LM339",
     "XU6 N004 N001 VCC 0 N002 LM339 LM339",
     "R1 VCC N001 68k", "R2 N001 N006 20k", "R6 N006 0 13k",
     "R7 N007 N009 330k", "R8 N002 N004 330k",
     "M1 RELAY2 N003 0 0 2N7002", "M2 RELAY3 N008 0 0 2N7002",
     "R9 VCC N003 10k", "R10 VCC N008 10k",
     "R11 N009 Vcontrol 10k", "R12 N004 Vcontrol 10k",
     "D1 RELAY2 VCC 1N4148", "D2 RELAY3 VCC 1N4148",
     "R32 N008 N007 470", "R33 N003 N002 470")

# snubbers y zeners por devanado: existian por el corte inductivo del rele
drop("C3 N013 N016 0.33u", "R24 N016 N023 100",
     "C4 N023 N028 0.33u", "R25 N028 N025 100",
     "C5 N025 N033 0.33u", "R26 N033 VACneg 100",
     "D5 N013 N020 BZX84C30VLY", "D6 N023 N020 BZX84C30VLY",
     "D7 N023 N029 BZX84C30VLY", "D8 N025 N029 BZX84C30VLY",
     "D9 N025 N034 BZX84C30VLY", "D10 VACneg N034 BZX84C30VLY")

# selector manual (rotativo 1P3T, break-before-make) + un unico snubber
n.add("* --- selector manual de tomas: .param TAP = 1 | 2 | 3 --------------",
      ".param TAP=2",
      ".model SWMAN SW(Ron=10m Roff=1G Vt=6 Vh=2 level=2)",
      "S_TAP1 N025 VACpos TAP_SEL1 0 SWMAN",
      "S_TAP2 N023 VACpos TAP_SEL2 0 SWMAN",
      "S_TAP3 N013 VACpos TAP_SEL3 0 SWMAN",
      "V_TAP1 TAP_SEL1 0 {12*(TAP==1)}",
      "V_TAP2 TAP_SEL2 0 {12*(TAP==2)}",
      "V_TAP3 TAP_SEL3 0 {12*(TAP==3)}",
      "C3 VACpos N016 0.33u",
      "R24 N016 VACneg 100")

# ------------------------------------------------- 2) solo LM317, sin banco
drop("Q1 PASS_IN N005 N012 0 2N3055", "R21 VLOAD N005 220",
     "R19 VLOAD N012 0.47", "Q3 PASS_IN N005 N010 0 2N3055",
     "R20 VLOAD N010 0.47", "Q5 N005 N010 VLOAD 0 2N2222",
     "R29 N005 N017 10", "C1 VLOAD N010 220n",
     "Q4 N017 N021 PASS_IN 0 BD140")
# R28 sensaba la corriente del 317 para excitar Q4; ya no hace falta
n.patch("R28 N021 PASS_IN 10", "R28 N021 PASS_IN 1m")
# el fallo inyectado ya no es "se cortocircuita Q3" sino "se cortocircuita el 317"
n.patch("S1 N010 PASS_IN Q3_Short_simulation 0 MYSW",
        "S1 VLOAD PASS_IN Q3_Short_simulation 0 MYSW")

# ----------------------------------------------- 3) fuera referencia negativa
drop("XU12 -1.25V 0 N035 LT317A", "V6 N035 -1.25V 5", "R43 0 -1.25V 220")
n.patch("R17 Vadj -1.25V R = V(Vcontrol) * 1000", "R17 Vadj 0 R = V(Vcontrol) * 1000")
n.patch("XU8 ISENSE CC_IN VCC -1.25V CC_OUT OP747", "XU8 ISENSE CC_IN VCC 0 CC_OUT OP747")
n.patch("Q6 Vadj LATCH_B -1.25V 0 BD139", "Q6 Vadj LATCH_B 0 0 BD139")
n.patch("R56 LATCH_B -1.25V 2k2", "R56 LATCH_B 0 2k2")
n.patch("R47 -1.25V CC_B 10k", "R47 0 CC_B 10k")
n.patch("Q2 Vadj CC_B -1.25V 0 BD139", "Q2 Vadj CC_B 0 0 BD139")

# ------------------------------------------------------- LM317HV en vez de 317
# el LT317A.sub que trae LTspice viene cifrado y, siendo la pieza de 40 V, deja
# de regular por encima: con 50 V de entrada saca 2,98 V en vez de 1,25 V.
n.patch("XU1 Vadj VLOAD N021 LT317A", "XU1 Vadj VLOAD N021 LM317HV")
n.patch(".lib LT317A.sub", ".lib LM317HV.sub")
# corriente minima de carga: el datasheet pide hasta 12 mA a 60 V de diferencial
# y R16=220 solo daba 5,7 mA.  100 ohm dan 12,5 mA.  R17 se escala para mantener
# el mismo rango de salida (pote de 2k2 en vez de 5k).
n.patch("R16 VLOAD Vadj 220", "R16 VLOAD Vadj 100")
n.patch("R17 Vadj 0 R = V(Vcontrol) * 1000", "R17 Vadj 0 R = V(Vcontrol) * 470")

# ------------------------------------------------------------ recalibraciones
# OVP: la salida sube 1,25 V para la misma consigna -> subir VREF_0V otro tanto
n.patch("R46 2v5 VREF_0V 39k", "R46 2v5 VREF_0V 27k")
# CC: 2,5 A no tiene sentido con un 317 solo. 1,0 A = 0,1 V sobre R22.
n.patch("R23 2v5 CC_REF 9k", "R23 2v5 CC_REF 24k")
# OTP: con un TO-220 la union esta ~5 C/W por encima del disipador
n.patch("R57 2v5 OTP_REF 18k", "R57 2v5 OTP_REF 27k")     # 0,676 V -> 67,6 C

# ------------------------------------------------------------- codigo muerto
# bloque contiguo: zener de disparo 1N4752A + subckt SCR (crowbar abandonado)
i = n.text.index("* ---------- Zener de disparo")
j = n.text.index(".ends\n", n.text.index(".model PSCR")) + len(".ends\n")
assert "subckt SCR" in n.text[i:j] and "D1N4752A" in n.text[i:j], n.text[i:j][:200]
n.text = n.text[:i] + n.text[j:]
n.patch(".model IRF4905 VDMOS(pchan Vds=-55 Ron=0.02 Qg=180n Vto=-3.8 Kp=25 Rs=5m "
        "Rd=10m Rg=3 Cgdmax=2n Cgdmin=0.5n Cgs=3.4n Cjo=1n Is=10p mfg=IR)\n", "")
n.patch(";XSENS VCC Tsense 0 LM35\n", "")
n.patch(".lib Relay_2A2B.sub\n", "")

# perfil de carga acorde al nuevo amperaje: 0,3 A / 1,0 A
n.patch("V4 load 0 PULSE(70 25 0.3 100u 100u 0.3 0.6 10)",
        "V4 load 0 PULSE(167 50 0.3 100u 100u 0.3 0.6 10)")

HEADER = """* psu_simple - LM317 solo, tomas manuales, sin referencia negativa
* -----------------------------------------------------------------------------
* Derivado de psu_overengineered/psu.asc.  Tres simplificaciones:
*   1. Conmutacion de tomas por reles  -> selector manual (.param TAP=1|2|3).
*   2. Banco de paso  -> solo el LM317HV, que se autoprotege.
*   3. Referencia de -1,25 V  -> masa.
* Los detalles, los numeros medidos y las contrapartidas estan en el README
* del directorio.  Regenerar con: python3 tools/ltspice/simplify_psu.py
* -----------------------------------------------------------------------------"""
n.text = n.text.replace("* /Users/emolina/git/electrucio_updates/powersupply/psu.asc",
                        HEADER)
DST.write_text(n.text, encoding="ascii")
print(f"escrito {DST}  ({len(n.text.splitlines())} lineas)")
for tok in ("-1.25V", "Relay_2A2B", "RELAY2", "subckt SCR", "IRF4905"):
    print(f"  {tok:14} restan {n.text.count(tok)}")
