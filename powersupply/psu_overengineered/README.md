# psu_overengineered — fuente de banco 0–29 V / 2,5 A

El diseño original. Fuente lineal ajustable con LM317, par de transistores de
paso 2N3055, conmutación automática de tomas del secundario por relés,
limitación de corriente en lazo cerrado y un bus de fallo enclavado.

Se conserva tal cual como referencia. Los otros dos diseños de la serie son
[`../psu_simple/`](../psu_simple/) (una poda de este) y
[`../psu_cvcc/`](../psu_cvcc/) (hecho desde cero, el que se va a construir).

Fuente de verdad: `psu.asc` (GUI de LTspice). `psu.net` se exporta con
`File > Export Netlist` o `LTspice -netlist psu.asc`.

## Bloques

| bloque | componentes |
|---|---|
| Red y transformador | 3 primarios acoplados (K3/K4/K5), secundarios de 160 mH en serie |
| Conmutador de tomas | XU2, XU6 (LM339), XU3, XU4 (relés 2A2B), M1, M2, snubbers y zeners por devanado |
| Rectificación | puente D11–D14, C6 10.000 µF, bleeder 4k7 |
| Disyuntor serie | M4 (IRF9540N), Q7 (MMBTA42), D16 |
| Banco de paso | Q1 ∥ Q3 (2N3055) con ballast 0,47 Ω, driver Q4 (BD140), limitador local Q5 |
| Regulación | XU1 (LM317) + raíl de −1,25 V (XU12) para llegar a 0 V |
| Lazo de corriente | shunt 0,1 Ω, XU8 (OP747) como integrador, Q2 |
| Protecciones | OVP con seguimiento, OTP, latch, POR, D4/D15/D17 |
| Ventilador | LM35 + XU11 (OP747), control proporcional lineal sobre M3 |

## Números medidos

Tomas: VRAW+ = 15,4 / 32,0 / 48,5 V, conmutando a 9,18 V y 23,36 V de salida.
Transferencia `VLOAD = 5,803·Vcontrol − 0,025`. CC a 2,512 A. OVP dispara
3,1–4,5 V por encima de la nominal, en 44 µs, y enclava.

**Cuidado con R53.** El divisor de sensado del OVP (R35/R36) está en paralelo
con R53, que realimenta el latch. Con el latch en reposo el ratio efectivo no
es 1/11 sino ≈1/20,2, y de eso depende que el OVP no dispare en operación
normal. Tocar R35, R36 o R53 por separado rompe la protección.

## Puntos abiertos

1. La lógica de tomas compara la **consigna**, no la salida. En límite de
   corriente con consigna alta el raíl se queda arriba y el par de 2N3055
   disipa 119 W hasta que el OTP corta, ~3 s después.
2. M3 (2N7002, SOT-23) trabaja en zona lineal disipando ~0,9 W. Un SOT-23 son
   ~0,3 W.
3. El integrador del CC (R31·C9 ≈ 106 Hz) cae sobre el rizado de 100 Hz:
   ±10 % de rizado en CC cerca del dropout y 5,9 A de sobrepico en un escalón.

## Código muerto

`.subckt SCR`, `.model D1N4752A` e `.model IRF4905` no se instancian: son los
restos de un crowbar de tiristor que sustituyó el disyuntor M4.

## Simular

```bash
python3 tools/ltspice/verify_psu.py
```
