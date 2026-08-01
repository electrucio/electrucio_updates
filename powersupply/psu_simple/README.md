# psu_simple — fuente lineal DIY con LM317HV

Simplificación de [`../psu_overengineered/`](../psu_overengineered/) para uso
DIY en audio. Se generó con:

```bash
python3 tools/ltspice/simplify_psu.py
```

que deriva `psu_simple.net` desde `psu_overengineered/psu.net` mediante
parches explícitos: si el esquemático original cambia una de las líneas que
toca, el script revienta en vez de aplicarse a medias.

## Qué se quitó (~40 componentes)

1. **Conmutación de tomas por relés → selector manual.** Fuera XU2, XU6, XU3,
   XU4, M1, M2, D1, D2, R1, R2, R6–R12, R32, R33 y los snubbers/zeners por
   devanado. En el netlist el selector es `.param TAP=1|2|3`.
2. **Banco de paso → solo el regulador**, que se autoprotege. Fuera Q1, Q3
   (2N3055), Q4, Q5, R19, R20, R21, R29, C1; R28 pasa a ser un hilo.
3. **Referencia de −1,25 V → masa.** Fuera XU12, V6, R43.

Y el código muerto del crowbar de tiristor (`SCR`, `D1N4752A`, `IRF4905`).

## Qué se conserva

OVP con seguimiento, OTP, latch, POR, disyuntor serie M4, lazo de corriente
constante, control de ventilador y las protecciones de un diodo (D4, D15,
D17, D16).

## Recalibraciones

| | de | a | por qué |
|---|---|---|---|
| R16 | 220 Ω | **100 Ω** | corriente mínima de carga: el datasheet pide hasta 12 mA a 60 V de diferencial y 220 Ω solo daban 5,7 mA. Ahora 12,5 mA. R17 (pote) se escala de 5 kΩ a 2,2 kΩ para mantener el rango |
| R46 | 39 kΩ | **27 kΩ** | sin el raíl negativo la salida sube 1,25 V para la misma consigna; el margen del OVP caía de 3,2 V a 1,8 V |
| R23 | 9 kΩ | **24 kΩ** | el CC estaba a 2,5 A, por encima de lo que da el regulador. Ahora 1,0 A |
| R57 | 18 kΩ | **27 kΩ** | OTP de 89,3 → 67,6 °C: todo el calor pasa ahora por una sola lengüeta |

## Medido en simulación

| toma | VRAW+ | salida en regulación | corto: Vin−Vout / I |
|---|---|---|---|
| TAP=1 | 16,0 V | 1,25 – 14,1 V | 12,1 V / 2,19 A |
| TAP=2 | 33,3 V | 1,25 – 30,5 V | 28,5 V / 1,63 A |
| TAP=3 | 50,4 V | 1,25 – 30,6 V | 47,5 V / 0,83 A |

`VLOAD = 5,839·Vcontrol + 1,261`. CC a 1,005 A con carga resistiva. OVP
dispara 20 µs tras un corto entrada-salida del regulador, enclava y corta M4.
Margen del OVP: 3,2 V por encima de la nominal en las tres tomas.

## Tres cosas que hay que saber

**TAP=3 no aporta nada tal como está.** El pote llega a 2,35 kΩ, que topa la
salida en 30,6 V — lo mismo que da TAP=2. La tercera toma solo añade
disipación. Para aprovecharla harían falta ~3,9 kΩ de pote (≈48 V de salida).

**El CC perdió el suelo.** Sin el raíl negativo, Q2 no puede llevar `Vadj` por
debajo de masa y la salida no baja de ~1,3 V. El lazo solo regula mientras
`Rcarga > 1,3 V / I_límite`; por debajo actúa el limitador interno del
regulador, que además se pliega con el diferencial (2,2 A a 15 V, 0,3 A a
60 V, tabla 7.5 del datasheet).

**El selector tiene que ser break-before-make.** Uno make-before-break
cortocircuita un devanado al pasar de posición. Queda un único snubber RC en
la entrada del puente en vez de los tres por devanado, así que conmuta con la
salida descargada: cortar 160 mH con corriente hace arco.

## LM317HV.sub

`LT317A.sub`, el modelo que trae LTspice, viene cifrado y —siendo la pieza de
40 V— **deja de regular por encima de esa tensión**: con 50 V de entrada saca
2,98 V en vez de 1,25, y 9,4 V con carga ligera. Cualquier simulación de la
toma alta con él da resultados falsos.

`LM317HV.sub` es un modelo conductual escrito a partir de TI SNVS773D rev D:
Vref 1,25 V, 50 µA en ADJ, dropout ~2 V, y límite de corriente con plegado SOA
interpolado entre los dos puntos que da la tabla 7.5. Contrastado contra
LT317A donde LT317A es válido (Vin < 40 V) coincide dentro del 1 %.

No modela apagado térmico, corriente mínima de carga, deriva con temperatura
ni ruido. Su lazo es más lento que el real, así que muestra un pico de arranque
de ~4,7 V a consigna mínima que la pieza real no tiene; no llega a enclavar el
OVP, pero no te fíes de ese transitorio.
