#!/usr/bin/env python3
"""Caracterizacion de powersupply/psu_cvcc como fuente de laboratorio.

    python3 tools/ltspice/caracteriza_psu_cvcc.py
    python3 tools/ltspice/caracteriza_psu_cvcc.py --only escalon

`verify_psu_cvcc.py` es la suite de regresion: comprueba que el diseño sigue
haciendo lo que hacia.  Esto es otra cosa: mide los parametros con los que se
juzga una fuente de banco, los mismos que publican Silicon Chip, Rod Elliott
(ESP P223) y los hilos de EEVblog, para poder compararse con ellos.

  tension     exactitud de la tension en todo el recorrido, extremos incluidos
  carga       regulacion de carga e impedancia de salida en CV
  linea       regulacion de linea (red a 207 / 230 / 253 V)
  corriente   exactitud de la corriente, extremos incluidos
  cc_carga    regulacion de carga en CC: de 10 ohm a 0,01 ohm
  escalon     estabilidad: escalon de carga y de consigna, oscilacion
  arranque    sobreimpulso al encender
  proteccion  sobrecarga, cortocircuito, maximo absoluto y temperatura
  potes       cuanta potencia lleva cada pote y que hay que comprar

El criterio de cada veredicto esta escrito al lado del numero.  Donde no hay
criterio objetivo se imprime el dato y se calla.
"""
from __future__ import annotations

import argparse
import functools
import shutil
import sys
from pathlib import Path

import numpy as np

print = functools.partial(__builtins__.print, flush=True) \
    if hasattr(__builtins__, 'print') else print

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_psu_cvcc as V                                # noqa: E402

OK, MAL, OJO = "OK", "*** MAL ***", "ojo"


def vteorica(frac):
    """Vout de la carga con la referencia de -1,25 V: 1,25*R2/R1."""
    r2 = frac * V.R2_TOTAL
    return 1.25 * r2 / V.R1_TOTAL + 50e-6 * r2


def iteorica(frac):
    return V.iset_teorico(frac)


def borne(d):
    """Tension en el borne a lo largo del tiempo: V(VOUT) - V(VRTN)."""
    return d["V(vout)"] - d["V(vrtn)"]


# ----------------------------------------------------------------- secciones
def sec_tension(b):
    print("== 1. REGULACION DE TENSION: recorrido del pote, extremos incluidos ==")
    print("   TAP=3 (la unica toma donde el pote no puede meter al chip en")
    print("   dropout), carga de 100 ohm.  El error es contra 1,25*R2/R1.\n")
    print(f"   {'pote':>6}{'R2':>9}{'teorico':>10}{'medido':>10}"
          f"{'error':>9}{'error':>9}")
    print(f"   {'':6}{'':9}{'':10}{'':10}{'mV':>9}{'%':>9}")
    peor = 0.0
    for vs in (0.0, 0.01, 0.03, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0):
        d, m, q = b.run(f"t_{vs}", tap=3, vset=vs, iset=1.0, load=100)
        th, me = vteorica(vs), q["vout_dc"]
        err = me - th
        pct = 100 * err / th if th > 0.05 else float("nan")
        if th > 1:
            peor = max(peor, abs(pct))
        print(f"   {vs*100:5.0f}%{vs*V.R2_TOTAL:8.0f}R{th:9.3f}V{me:9.3f}V"
              f"{err*1000:8.0f}m{pct:8.2f}%")
    print(f"\n   Peor error relativo por encima de 1 V: {peor:.2f} %")
    print(f"   Veredicto: {OK if peor < 2 else OJO} "
          f"(una fuente de banco decente esta en el 1-2 %; el P223 pide")
    print("   trimmer para el fondo de escala, y aqui pasaria lo mismo)")


def sec_carga(b):
    print("== 2. REGULACION DE CARGA en los extremos de tension ==")
    print("   De vacio (1 kohm) a la corriente maxima que admite cada ajuste.")
    print("   Zo = dV/dI es la impedancia de salida.\n")
    print(f"   {'ajuste':>10}{'vacio':>10}{'con carga':>11}{'I':>9}"
          f"{'caida':>9}{'reg':>9}{'Zo':>10}")
    # el fondo de escala solo cabe en TAP=3: en TAP=2 el rail son 33 V y
    # pedirle 40 lo mete en dropout, que mediria el dropout y no la regulacion
    for nombre, vs, rl, tap in (("0,5 V", 0.0123, 1.0, 2),
                                ("5 V", 0.1231, 10.0, 2),
                                ("20 V", 0.4923, 22.0, 2),
                                ("fondo", 1.0, 47.0, 3)):
        _, _, q0 = b.run(f"c0_{vs}", tap=tap, vset=vs, iset=1.0, load=1000)
        _, _, q1 = b.run(f"c1_{vs}", tap=tap, vset=vs, iset=1.0, load=rl)
        v0, v1 = q0["vout_dc"], q1["vout_dc"]
        i0, i1 = abs(q0["iload_dc"]), abs(q1["iload_dc"])
        dv, di = v0 - v1, i1 - i0
        reg = 100 * dv / v0 if v0 > 0.01 else float("nan")
        print(f"   {nombre:>10}{v0:9.3f}V{v1:10.3f}V{i1:8.3f}A"
              f"{dv*1000:8.1f}m{reg:8.2f}%{dv/max(di,1e-9)*1000:9.1f}m")
    print("\n   Referencia publicada: Silicon Chip 30 V/2 A declara <0,5 % de")
    print("   regulacion de carga y <8 mV RMS a 2 A.  Del P223 no hay cifra")
    print("   publicada de regulacion de carga.")


def sec_linea(b):
    print("== 3. REGULACION DE LINEA: red a 207 / 230 / 253 V (+-10 %) ==")
    print("   TAP=2, pote al 50 %, 22 ohm de carga.\n")
    print(f"   {'red':>8}{'VRAW':>9}{'Vout':>10}{'margen':>9}{'rizado':>10}")
    vs = []
    for vrms in (207, 230, 253):
        d, m, q = b.run(f"l_{vrms}", tap=2, vset=0.4923, iset=1.0, load=22,
                        vred=round(vrms * 1.4142, 1))
        vs.append(q["vout_dc"])
        print(f"   {vrms:6} V{q['vraw_dc']:8.1f}V{q['vout_dc']:9.3f}V"
              f"{q['headroom']:8.2f}V{q['vout_pp']*1e3:9.2f}mV")
    dv = max(vs) - min(vs)
    print(f"\n   Variacion total: {dv*1000:.1f} mV sobre {vs[1]:.2f} V "
          f"= {100*dv/vs[1]:.3f} %")
    print(f"   Veredicto: {OK if 100*dv/vs[1] < 0.1 else OJO} "
          "(el datasheet promete 0,01 %/V tipico)")


def sec_corriente(b):
    print("== 4. REGULACION DE CORRIENTE: recorrido del pote, extremos incluidos ==")
    print("   TAP=2 con 2,2 ohm de carga, que fuerza CC en todo el recorrido.\n")
    print(f"   {'pote':>6}{'consigna':>11}{'medido':>10}{'error':>9}"
          f"{'error':>8}{'Vout':>9}  modo{'ventana':>9}")
    peor = 0.0
    # El integrador recupera del windup a (ISET-SENSE)/(Rint*Cint) voltios por
    # segundo.  Con la consigna al 2 % el error son 10 mV y eso es 1 V/s, asi
    # que tarda segundos en asentarse: hay que darle ventana o se mide el
    # transitorio.  Es lento, no inestable.
    for ia in (0.02, 0.05, 0.1, 0.2, 0.4, 0.6, 0.8, 1.0):
        largo = ia <= 0.05
        d, m, q = b.run(f"i_{ia}", tap=2, vset=0.5, iset=ia, load=2.2,
                        tend=8.0 if largo else 2.0, step="200u",
                        meas_from=7.5 if largo else 1.7)
        th, me = iteorica(ia), abs(q["iload_dc"])
        err = me - th
        pct = 100 * err / th
        peor = max(peor, abs(pct))
        print(f"   {ia*100:5.0f}%{th*1000:9.1f}mA{me*1000:8.1f}mA"
              f"{err*1000:8.2f}mA{pct:7.2f}%{q['vout_dc']:8.3f}V"
              f"  {'CC' if q['en_cc'] else 'CV'}"
              f"{8.0 if largo else 2.0:7.0f} s")
    print(f"\n   Peor error: {peor:.2f} %")
    print(f"   Veredicto: {OK if peor < 2 else OJO}")


def sec_cc_carga(b):
    print("== 5. CC: regulacion de carga, de 10 ohm al corto franco ==")
    print("   Con la consigna al 40 % (598 mA), bajando la carga hasta 0,01 ohm.")
    print("   Una fuente de corriente de verdad no cambia su corriente.\n")
    print(f"   {'carga':>9}{'I':>10}{'Vout':>10}{'P(317)':>9}  modo")
    base = None
    for rl in (10, 4.7, 2.2, 1.0, 0.33, 0.1, 0.05, 0.01):
        d, m, q = b.run(f"ccl_{rl}", tap=2, vset=0.5, iset=0.4, load=rl,
                        tend=2.0, step="200u", meas_from=1.7)
        i = abs(q["iload_dc"])
        if base is None:
            base = i
        print(f"   {rl:8}R{i*1000:9.1f}mA{q['vout_dc']*1000:9.1f}mV"
              f"{q['p_lm317']:8.1f}W  {'CC' if q['en_cc'] else 'CV'}")
    print(f"\n   Consigna: {iteorica(0.4)*1000:.1f} mA.  "
          f"Desviacion de 10 ohm a 0,01 ohm: "
          f"{abs(i-base)*1000:.2f} mA")
    print("   Referencia: Silicon Chip 45 V/8 A reconoce que su CC es lento y")
    print("   que un escalon le hace pasar de 7 A con el limite en 5 A.")


def _escalon(d, t0, t1, nombre, unidad="V"):
    """Caida/sobreimpulso y tiempo de establecimiento de un escalon."""
    t, v = d["time"], borne(d)
    antes = v[(t > t0 - 0.02) & (t < t0 - 0.001)]
    despues = v[(t > t1 - 0.02) & (t < t1 - 0.001)]
    if antes.size == 0 or despues.size == 0:
        print(f"   {nombre}: sin datos en la ventana")
        return
    v0, v1 = float(np.median(antes)), float(np.median(despues))
    tr = (t >= t0) & (t < t1)
    vt = v[tr]
    pico = float(np.min(vt)) if v1 < v0 + 1e-9 else float(np.max(vt))
    desv = pico - v1
    # establecimiento: ultimo instante fuera del 1 % del valor final
    banda = max(abs(v1) * 0.01, 2e-3)
    fuera = np.where(np.abs(vt - v1) > banda)[0]
    ts = (t[tr][fuera[-1]] - t0) if fuera.size else 0.0
    print(f"   {nombre}: {v0:.3f} -> {v1:.3f} {unidad}, "
          f"pico {pico:.3f} {unidad} ({desv*1000:+.0f} m{unidad} de desviacion), "
          f"establece en {ts*1e3:.2f} ms")
    return ts, desv


def sec_escalon(b):
    print("== 6. ESTABILIDAD: escalon de carga y de consigna ==")
    print("   Flancos de 1 us, mucho mas rapidos que la fuente, que es lo que")
    print("   piden los hilos de EEVblog para que la medida valga.\n")

    print("  --- escalon de carga dentro de CV: 100 ohm -> 22 ohm -> 100 ohm ---")
    pwl = "PWL(0 100 0.5 100 0.500001 22 0.62 22 0.620001 100)"
    d, m, q = b.run("e_carga", tap=2, vset=0.4923, iset=1.0, load=pwl,
                    tend=0.72, tstart=0.45, step="5u", meas_from=0.68)
    _escalon(d, 0.5, 0.62, "bajada (0,2 -> 0,9 A)")
    _escalon(d, 0.62, 0.72, "subida (0,9 -> 0,2 A)")

    print("\n  --- escalon de carga que cruza a CC: 100 ohm -> 10 ohm ---")
    pwl = "PWL(0 100 0.5 100 0.500001 10 0.62 10 0.620001 100)"
    d, m, q = b.run("e_cc", tap=2, vset=0.4923, iset=1.0, load=pwl,
                    tend=0.72, tstart=0.45, step="5u", meas_from=0.68)
    _escalon(d, 0.5, 0.62, "entrada en CC")
    _escalon(d, 0.62, 0.72, "salida de CC")

    print("\n  --- escalon de consigna de tension (como el Scope9 de SC) ---")
    # OJO: hay que mover los DOS mandos.  Si solo se mueve el grueso, el fino
    # se queda donde estaba y pone un suelo (0,4923 del pote fino son 2,3 V),
    # asi que el escalon no llega a 0,5 V y la medida miente.
    pwl_v = ("PWL(0 0.4923 0.5 0.4923 0.500001 0.0123"
             " 0.62 0.0123 0.620001 0.4923)")
    pat = [("Vset VSET 0 0.4923", f"Vset VSET 0 {pwl_v}"),
           ("Vsetf VSETF 0 0.4923", f"Vsetf VSETF 0 {pwl_v}")]
    d, m, q = b.run("e_vset", tap=2, vset=0.4923, iset=1.0, load=22,
                    tend=0.72, tstart=0.45, step="5u", meas_from=0.68,
                    patches=pat)
    _escalon(d, 0.5, 0.62, "20 V -> 0,5 V (bajada)")
    _escalon(d, 0.62, 0.72, "0,5 V -> 20 V (subida)")
    print("\n   Silicon Chip mide en su fuente ~0,5 V de sobreimpulso y")
    print("   establecimiento en 2 ms quitando 4 A a 25 V; G. Jolley, 15 % de")
    print("   sobreimpulso recuperado en 2 us.  Lo esperable aqui es un lazo")
    print("   mas lento: el integrador de CC esta en 16 Hz a proposito.")

    print("\n  --- oscilacion en regimen (sin escalon) ---")
    print("   Rizado de salida contra el de 100 Hz del rectificador.  Si")
    print("   hubiera oscilacion, el contenido fuera de 100 Hz lo delataria.\n")
    print(f"   {'caso':>14}{'rizado out':>12}{'rizado rail':>13}{'rechazo':>10}")
    for nombre, vs, rl in (("vacio", 0.4923, 1000), ("1 A", 0.4923, 22),
                           ("0 V", 0.0, 100), ("en CC", 0.4923, 10)):
        d, m, q = b.run(f"osc_{nombre}".replace(" ", ""), tap=2, vset=vs,
                        iset=1.0, load=rl, step="20u")
        print(f"   {nombre:>14}{q['vout_pp']*1e3:11.2f}mV"
              f"{q['vraw_pp']*1e3:12.0f}mV{q.get('rechazo_db', 0):9.1f}dB")


def sec_arranque(b):
    print("== 7. ARRANQUE: sobreimpulso al encender ==")
    print("   El P223 llego a poner un rele de salida con 2,5 s de retardo por")
    print("   un sobreimpulso de ~4 V al encender.  Aqui, medido:\n")
    print(f"   {'TAP':>4}{'ajuste':>9}{'Vout':>10}{'pico':>10}"
          f"{'sobreimpulso':>14}")
    for tap, vs, nombre in ((2, 0.4923, "20 V"), (3, 1.0, "fondo"),
                            (2, 0.0123, "0,5 V"), (2, 0.0, "0 V")):
        d, m, q = b.run(f"a_{tap}_{vs}", tap=tap, vset=vs, iset=1.0, load=100)
        pico, dc = q["vout_pico"], q["vout_dc"]
        print(f"   {tap:>4}{nombre:>9}{dc:9.3f}V{pico:9.3f}V"
              f"{(pico-dc)*1000:12.0f} mV")


def sec_proteccion(b):
    print("== 8. PROTECCIONES: sobrecarga y cortocircuito ==")
    print("   Corto franco de 0,01 ohm en las tres tomas, con el limite de")
    print("   corriente al maximo y al minimo.  Las dos condiciones que matan")
    print("   el chip son el diferencial (60 V de maximo absoluto, §8.3.2) y")
    print("   la temperatura de union (125 C).\n")
    print(f"   {'TAP':>4}{'limite':>9}{'I':>9}{'Vin-Vout':>10}{'P':>8}"
          f"{'Tj reg':>9}   veredicto")
    for tap in (1, 2, 3):
        for ia, nombre in ((1.0, "max"), (0.05, "min")):
            d, m, q = b.run(f"p_{tap}_{ia}", tap=tap, vset=0.5, iset=ia,
                            load=0.01, tend=2.0, step="200u", meas_from=1.7)
            dif = q["vraw_dc"] - q["vout_dc"]
            tj = V.TAMB + q["p_lm317"] * V.RTH_TOTAL
            ver = OK if dif < 60 else "*** >60 V ABSOLUTO ***"
            if tj > V.TJ_MAX:
                ver += " / corta el apagado termico"
            print(f"   {tap:>4}{nombre:>9}{q['iout_dc']:8.3f}A{dif:9.1f}V"
                  f"{q['p_lm317']:7.1f}W{tj:8.0f}C   {ver}")
    print("\n   Sobrecarga progresiva (TAP=2, 20 V pedidos, limite al maximo):\n")
    print(f"   {'carga':>8}{'I':>9}{'Vout':>9}  modo{'P(317)':>9}{'Tj reg':>9}")
    for rl in (100, 47, 22, 15, 10, 4.7, 2.2, 1.0):
        d, m, q = b.run(f"sob_{rl}", tap=2, vset=0.4923, iset=1.0, load=rl)
        tj = V.TAMB + q["p_lm317"] * V.RTH_TOTAL
        print(f"   {rl:7}R{q['iout_dc']:8.3f}A{q['vout_dc']:8.2f}V"
              f"  {'CC' if q['en_cc'] else 'CV'}{q['p_lm317']:8.1f}W{tj:8.0f}C")


def sec_potes(b):
    print("== 9. POTENCIA EN LOS POTENCIOMETROS ==")
    print("   El fallo clasico del LM317 como regulador de corriente es el pote")
    print("   en serie con la carga; ese no esta.  El de TENSION es el divisor de")
    print("   realimentacion, asi que lleva la corriente del divisor siempre, pero")
    print("   con Q_min dando la carga minima esa corriente ya puede ser pequena.\n")
    print(f"   {'escenario':>16}{'R2c grueso':>14}{'R2f fino':>12}"
          f"{'pote I':>11}{'shunt':>10}")
    for nombre, kw in (("fondo en vacio", dict(tap=3, vset=1.0, load=1000)),
                       ("20 V a 1 A", dict(tap=2, vset=0.4923, load=19)),
                       ("corto, lim max", dict(tap=2, vset=0.5, load=0.01)),
                       ("0 V en vacio", dict(tap=2, vset=0.0, load=1000))):
        d, m, q = b.run(f"pot_{nombre[:5]}".replace(" ", ""), iset=1.0, **kw)
        print(f"   {nombre:>16}{q['p_r2c']*1000:11.1f} mW"
              f"{q['p_r2f']*1000:9.1f} mW{q['p_rpot_i']*1000:8.1f} mW"
              f"{q['p_rshunt']*1000:7.0f} mW")
    pt = 40.5 ** 2 / V.R2_TOTAL
    print(f"\n   P(pote) = Vmax^2/R2 = 40,5^2/{V.R2_TOTAL} = {pt*1000:.0f} mW en total,")
    print(f"   repartidos {V.R2_COARSE/V.R2_TOTAL*100:.0f}/{V.R2_FINE/V.R2_TOTAL*100:.0f}")
    print("   entre grueso y fino.  No depende de la carga: la corriente del")
    print("   divisor la fija R1, y es la misma en vacio, a 1 A y en un corto.")
    print("   El pote de corriente solo divide los 2,5 V del TL431: microamperios.")
    print(f"   Veredicto: {OK} - los dos de PANEL y corrientes.  Lo que lo permite")
    print("   es Q_min: sin el, R1 tendria que dar la carga minima del chip y")
    print("   el pote volveria a necesitar 420 mW.  Ver el README.")


def sec_esfuerzos(b):
    print("== 10. ESFUERZO DE CADA COMPONENTE (para comprarlos bien) ==")
    print("   Todo con la red a 253 V, que es el peor caso de tension, y")
    print("   recorriendo las tres tomas en vacio / a 1 A / en corto.")
    print("   Las tensiones son de PICO e incluyen el arranque.\n")

    casos = []
    for tap, vmax in ((1, 0.356), (2, 0.767), (3, 1.0)):
        casos += [(f"T{tap} vacio", dict(tap=tap, vset=vmax, load=1000000)),
                  (f"T{tap} 1 A",   dict(tap=tap, vset=vmax, load=round(vmax*40.6))),
                  (f"T{tap} corto", dict(tap=tap, vset=vmax, load=0.01))]
    peor = {}
    for nombre, kw in casos:
        d, m, q = b.run("es_" + nombre.replace(" ", "_"), iset=1.0, vred=357.8,
                        tend=2.0, step="200u", meas_from=1.7, **kw)
        for k, v in q.items():
            if k.startswith(("vc_", "p_", "ipk_", "vce_")):
                if abs(v) > abs(peor.get(k, (0, ""))[0]):
                    peor[k] = (v, nombre)

    print("  CONDENSADORES - tension de pico que ve cada uno\n")
    print(f"  {'ref':>10}{'valor':>10}{'pico':>9}{'escenario':>12}   compra")
    CAPS = [("vc_bulk", "Cbulk", "10000 uF", "63 V, y mide 2,5 veces el pico"),
            ("vc_in", "Cin", "0,1 uF", "63 V ceramico o film"),
            ("vc_snub", "Csnub", "0,1 uF", "FILM de 100 V+ (va en alterna)"),
            ("vc_adj", "Cadj", "10 uF", "63 V (cuelga del rail de -5 V)"),
            ("vc_out", "Cout", "10 uF", "63 V"),
            ("vc_filt", "Cfilt", "100 nF", "cualquiera, 16 V sobra"),
            ("vc_ref", "Cref", "100 nF", "cualquiera, 16 V sobra"),
            ("vc_pot_i", "Cpot_i", "100 nF", "cualquiera, 16 V sobra")]
    for k, ref, val, compra in CAPS:
        v, donde = peor.get(k, (0, "-"))
        print(f"  {ref:>10}{val:>10}{v:8.1f}V{donde:>12}   {compra}")
    vmax = peor.get("vc_int_max", (0, "-"))
    vmin = peor.get("vc_int_min", (0, "-"))
    print(f"  {'Cint':>10}{'1 uF':>10}{vmin[0]:+7.1f} a {vmax[0]:+.1f} V"
          f"      BIPOLAR: film, NO tantalo")

    print("\n  RESISTENCIAS - potencia media en el peor escenario\n")
    print(f"  {'ref':>10}{'valor':>9}{'peor':>10}{'escenario':>12}   compra")
    RES = [("p_rshunt", "Rshunt", "0,33", "2 W, hilo bobinado"),
           ("p_r2c", "R2c (pote grueso)", "10k", "0,25 W"),
           ("p_r2f", "R2f (pote fino)", "1k", "0,125 W"),
           ("p_q_min", "Q_min (sumidero)", "BD139", "1,25 W"),
           ("p_re_min", "Re_min", "1k3", "3 W"),
           ("p_rbleed", "Rbleed", "10k", "1 W"),
           ("p_rsnub", "Rsnub", "100", "0,5 W"),
           ("p_r1", "R1", "270", "0,25 W"),
           ("p_tp1", "TP1", "150", "0,25 W"),
           ("p_rref", "Rref", "2k2", "0,25 W"),
           ("p_rset", "Rset", "22k", "0,125 W"),
           ("p_rpot_i", "Rpot_i", "4k7", "0,25 W (pote normal)"),
           ("p_rint", "Rint", "10k", "0,125 W"),
           ("p_rb", "Rb", "4k7", "0,125 W"),
           ("p_rbe", "Rbe", "10k", "0,125 W"),
           ("p_rnbleed", "Rnbleed", "220", "0,25 W"),
           ("p_rfilt", "Rfilt", "1k", "0,125 W")]
    for k, ref, val, compra in RES:
        v, donde = peor.get(k, (0, "-"))
        print(f"  {ref:>10}{val:>9}{v*1000:8.1f}mW{donde:>12}   {compra}")

    print("\n  SEMICONDUCTORES\n")
    print(f"  {'ref':>10}{'esfuerzo':>22}{'escenario':>12}")
    for k, ref, u in (("p_lm317", "LM317HV", "W"), ("p_qcc", "Qcc", "W"),
                      ("vce_qcc", "Qcc, Vce de pico", "V"),
                      ("ipk_diodo", "puente, pico por diodo", "A"),
                      ("ipk_d_rev", "D_REV, pico", "A"),
                      ("ipk_d_in", "D_IN, pico", "A"),
                      ("ipk_d_adj", "D_ADJ, pico", "A")):
        v, donde = peor.get(k, (0, "-"))
        print(f"  {ref:>10}{v:17.3f} {u:>3}{donde:>12}")


SECCIONES = {
    "tension": sec_tension, "carga": sec_carga, "linea": sec_linea,
    "corriente": sec_corriente, "cc_carga": sec_cc_carga,
    "escalon": sec_escalon, "arranque": sec_arranque,
    "esfuerzos": sec_esfuerzos,
    "proteccion": sec_proteccion, "potes": sec_potes,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=sorted(SECCIONES))
    ap.add_argument("--workdir")
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()

    wd = Path(a.workdir) if a.workdir else Path("/tmp/psu_cvcc_caract")
    b = V.Bench(wd)
    try:
        for name in ([a.only] if a.only else list(SECCIONES)):
            SECCIONES[name](b)
            print()
    finally:
        if not a.keep and not a.workdir:
            shutil.rmtree(wd, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
