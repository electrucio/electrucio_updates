# psu_cvcc — fuente lineal DIY con LM317HV, CV + CC ajustables

Tercer diseño de la serie, y el que está pensado para construir. Hecho
**desde cero**: no deriva de [`../psu_overengineered/`](../psu_overengineered/)
ni de [`../psu_simple/`](../psu_simple/). Se ciñe a los circuitos de aplicación
de **TI SNVS773D rev D** (LM117HV/LM317HV, sept. 2015); no lleva nada que no
esté en el datasheet.

| | |
|---|---|
| Tensión | 1,25 – 41,7 V, pote de 3k9 |
| Corriente | límite ajustable 80 mA – 1,34 A, pote de 4k7 |
| Tomas | 3, selección **manual** con rotativo 1P3T |
| Protecciones | las **nativas** del chip: límite de corriente con plegado SOA, cortocircuito y apagado térmico |

## De dónde sale cada parte

| bloque | referencia |
|---|---|
| Regulador ajustable con R1/R2 | fig. 16, §9.2.1 |
| 10 µF en ADJ para el rechazo de rizado | fig. 21, §9.2.5 |
| Diodos D_ADJ y D_IN | fig. 15, §8.4.2 y §11.1 |
| Límite de corriente: shunt en el retorno + NPN que tira de ADJ | fig. 32, §9.2.16 |
| Operacional atacando la base de ese NPN | fig. 31, §9.2.15 |

Lo único que añade el diseño sobre la figura 32 es hacer el límite
**ajustable**: la figura 32 lo fija por Vbe (0,6 A con 1 Ω) y no se puede
bajar sin poner un shunt enorme. Comparando el shunt contra una referencia
ajustable de un TL431, el rango va de 80 mA a 1,34 A con un shunt de 0,33 Ω.

## Lista de componentes

**Potencia**
- 3 transformadores de ~13 Vrms, secundarios en serie
- SW1 rotativo 1P3T **break-before-make**, + snubber 0,1 µF / 100 Ω
- Puente 1N5408 ×4 (o KBU8M), C 10.000 µF / 63 V, bleeder 10 k / 1 W
- 0,1 µF en la entrada del regulador (§8.4.1)
- **LM317HV en TO-220**, con disipador de ≤2 °C/W y aislador de mica
- R1 = 120 Ω (fija 10,4 mA de carga mínima permanente)
- R2 = pote 3k9 / 1 W (disipa 0,42 W a fondo de escala)
- C_ADJ = 10 µF tántalo, C_OUT = 10 µF tántalo
- D_ADJ 1N4148 (ADJ→OUT), D_IN 1N5408 (OUT→IN), D_REV 1N5408 (masa→OUT)
- Fusible de primario

**Control**
- Shunt 0,33 Ω / 1 W en el retorno, filtro 1 k / 100 nF
- TL431 + 2k2 → referencia de 2,5 V
- LM358 (medio), integrador 10 k / 1 µF → esquina a 16 Hz
- Consigna de corriente: 22 k + pote 4k7
- NPN pequeño (BC547/2N3904) + 4k7 y 10 k de base

**Auxiliar**
- Transformador pequeño de 1,5 VA / 12 V + puente + 7812 → **+12 V** para el
  control. No se puede sacar del raíl principal: entre TAP=1 y TAP=3 va de 16
  a 50 V, y un resistor+zener dimensionado para dar corriente a 16 V disiparía
  ~2,4 W a 50 V.

## Medido en simulación

Reproducible con `python3 tools/ltspice/verify_psu_cvcc.py`.

**Tensión.** `Vout = 1,25·(1 + R2/120) + Iadj·R2`. Linealidad dentro del 0,9 %
del valor teórico en todo el recorrido del pote.

| toma | VRAW+ | Vout máx |
|---|---|---|
| TAP=1 | 16,5 V | 14,5 V |
| TAP=2 | 33,3 V | 31,3 V |
| TAP=3 | 49,9 V | 41,7 V (tope del pote) |

**Regulación de carga y rizado** (TAP=2, 21,5 V):

| carga | I | Vout | desviación | rizado |
|---|---|---|---|---|
| 1000 Ω | 21 mA | 21,489 V | — | 0,06 mV |
| 22 Ω | 0,962 A | 21,481 V | −0,034 % | 0,83 mV |

**Corriente.** Error 0,0 % en todo el recorrido del pote:

| pote | consigna | medido |
|---|---|---|
| 5 % | 80,3 mA | 80,3 mA |
| 20 % | 311,2 mA | 311,3 mA |
| 70 % | 988,1 mA | 988,1 mA |
| 100 % | 1337,0 mA | 1337,1 mA |

Transición CV→CC limpia: con 21,5 V pedidos y el límite a 1,34 A, entra en CC
por debajo de 16 Ω de carga.

**Cortocircuito franco** (0,2 Ω, 5 s):

| toma | Vin−Vout | I | P | Tj |
|---|---|---|---|---|
| TAP=1 | 11,8 V | 2,19 A | 25,8 W | 111 °C |
| TAP=2 | 28,2 V | 1,64 A | 46,1 W | 163 °C → corta el apagado térmico |
| TAP=3 | 47,3 V | 0,84 A | 39,6 W | 147 °C → corta el apagado térmico |

Ningún diferencial pasa de los 60 V del máximo absoluto. §8.3.2 avisa de que
superarlos destruye el chip, y en TO-220 lo típico es que reviente el
encapsulado.

## El rizado depende del margen de raíl, y el salto es brusco

Es lo primero con lo que te vas a topar. El LM317HV necesita ~2 V de caída
para regular; por debajo entra en dropout y **la salida copia el rizado del
raíl 1:1**. Medido a TAP=2:

| pote | pedido | Vout | margen | rizado salida | rechazo |
|---|---|---|---|---|---|
| 100 % | 42,1 V | 31,28 V | 2,01 V | **246 mV** | **0,0 dB** |
| 80 % | 33,9 V | 31,27 V | 2,01 V | **248 mV** | **0,0 dB** |
| 70 % | 29,8 V | 29,56 V | 3,68 V | 0,3 mV | 57,1 dB |
| 50 % | 21,7 V | 21,49 V | 12,18 V | 0,3 mV | 56,8 dB |

No hay zona intermedia: o tienes 3 V de margen y el rizado son décimas de
milivoltio, o no lo tienes y sale el rizado entero del condensador. **Regla:
`VRAW_min − Vout ≥ 3 V`.** Por eso el `.asc` viene con `Vset=0.5`; con
`Vset=1` en TAP=2 arranca en dropout y parece que el diseño es malo.

A plena corriente el raíl cae ~1,5 V más, así que el techo útil de cada toma
con 1 A es menor que en vacío: 11 V en TAP=1, 27 V en TAP=2, 39 V en TAP=3.

## ¿Qué pasa si cortocircuito la salida?

No se rompe. El límite de corriente, la protección SOA y el apagado térmico
están para esto; TI describe la combinación como *"blowout proof"* (§3). Y el
dato que de verdad importa: en ninguna toma el diferencial llega a los 60 V
del máximo absoluto (47 V en el peor caso, TAP=3). Esa —y no la
temperatura— es la condición que destruye el chip, y §8.3.2 avisa de que en
TO-220 lo típico es que reviente el encapsulado.

Simulado, aplicando un corto franco con la fuente en régimen:

| toma | P en corto | Tj a 1,2 s | Tj a 30 s | corta a los |
|---|---|---|---|---|
| TAP=1 | 26,0 W | 108 °C | 122 °C | **no corta nunca** |
| TAP=2 | 46,2 W | 155 °C | 190 °C | 2,8 s |
| TAP=3 | 39,4 W | 139 °C | 169 °C | 17,5 s |

En TAP=2 y TAP=3 el chip se apaga, se enfría, vuelve a arrancar y se vuelve a
apagar: ciclado térmico. Ruidoso y feo, pero es justo para lo que está.

**El caso incómodo es TAP=1**, que es el que no parece peligroso: ahí no corta
nunca. Se queda indefinidamente disipando 26 W con la unión a 122 °C, justo
por debajo del máximo de 125 °C, y el disipador a ~77 °C. Sobrevive, pero es
el único escenario en que la fuente aguanta un corto para siempre sin
quejarse, calentando todo lo que tenga al lado.

Lo que sí puede sufrir en un corto sostenido:

- **Rshunt**, el único componente sin protección en ese camino: 2,19² × 0,33 =
  1,58 W en TAP=1. Con uno de 1 W se quema. **De 3 W.**
- **El electrolítico de 10.000 µF**, si va pegado al disipador. A 77–118 °C la
  vida útil se desploma. Sepáralo.

El puente y los transformadores van sobrados: 3 W entre los cuatro diodos.

## Disipación: peor caso de cada componente

`verify_psu_cvcc.py --only power` recorre 12 escenarios (las tres tomas ×
vacío / 1 A / salida mínima a 1 A / cortocircuito) y saca el peor caso de
cada componente:

| componente | peor caso | escenario | veredicto |
|---|---|---|---|
| LM317HV | 46,3 W | T2 corto | corta el apagado térmico, ver arriba |
| Puente (4 diodos) | 3,05 W | T1 corto | 1N5408 de sobra |
| **Rshunt 0,33** | **1,58 W** | T1 corto | **ponlo de 3 W** |
| R2 pote 3k9 | 0,42 W | T3 vacío | 1 W vale |
| Rbleed 10k | 0,29 W | T3 vacío | 1 W vale |
| resto | <0,05 W | | 1/8 W vale |

Y el dato de dimensionado que más fácilmente muerde: **el pico por cada diodo
del puente es de 7,13 A y el RMS por el secundario 3,52 A** para 1 A de
continua a la salida. Es el factor de forma normal de un rectificador con
condensador a la entrada (~3,5×), pero significa que los transformadores hay
que dimensionarlos para eso, no para 1 A.

## Instrumentación

El esquemático lleva **41 directivas `.meas`** que salen en el `.log` (Ctrl+L
en la GUI): tensión y corriente de salida con su rizado, rizado y mínimo del
raíl, margen de dropout, rechazo en dB, todos los nodos del lazo de control,
si está en CV o en CC, la disipación de cada componente uno por uno, el pico
por los diodos, el RMS por el secundario y las temperaturas.

Dos trampas al añadir medidas propias:

- **`.meas` solo ve lo que `.save` haya guardado.** Un `.save` parcial hace
  que cualquier medida que toque una corriente no listada devuelva 0 sin
  avisar. Por eso la suite no usa `.save`.
- **La constante térmica del modelo son 40 s**, así que la Tj al final de un
  transitorio de 1,5 s no es la de régimen. El peor caso se calcula:
  `Tj = 25 + P · 4,3`.

## Cuatro cosas que hay que saber

**El límite de corriente tiene un suelo de 1,25 V.** El NPN no puede llevar
ADJ por debajo de masa, así que la salida no baja de ~1,35 V. El límite se
respeta mientras la carga permita esa tensión, o sea **Rcarga > 1,35 V /
Iset**. Por debajo (un corto franco) el lazo se satura y toma el relevo el
limitador interno del chip, que además se pliega con el diferencial: 2,2 A
con Vin−Vout ≤ 15 V y 0,3 A a 60 V (tabla 7.5). Es la consecuencia directa de
no tener referencia negativa.

**Elige la toma por disipación, no por tensión.** Es lo único que hace el
selector manual. Regla para quedarse por debajo de ~15 W a 1 A con un
disipador de 2 °C/W: TAP=1 para 1,25–14 V, TAP=2 para 14–31 V, TAP=3 para
31–42 V. Con la toma equivocada (salida baja, toma alta) el TO-220 disipa
40 W y acaba cortando por temperatura.

**El selector tiene que ser break-before-make.** Uno make-before-break
cortocircuita un devanado al pasar de posición. Conmuta con la salida
descargada: cortar 160 mH con corriente hace arco en los contactos.

**No hay OVP.** Si el regulador falla en corto, la carga ve el raíl entero
(hasta 50 V). Es el único modo de fallo que no cubre nada, y las protecciones
nativas del chip no lo cubren por definición. Si en algún momento quieres
taparlo, lo clásico son tres componentes: zener + SCR + fusible.

## Esquemático

`psu_cvcc.asc` genera un netlist equivalente a `psu_cvcc.net`: mismos 68
componentes, mismos nodos, mismos valores, y la simulación coincide hasta
1e-4. Trae sus tres símbolos (`LM317HV.asy`, `LM358.asy`, `TL431ED.asy`).

Está conectado por **etiquetas de red**, no por hilos largos: cada pin lleva
un tramo corto y una etiqueta. Es feo comparado con un esquemático routeado a
mano, pero no tiene cruces y el netlist que sale es inequívoco. Reordenar los
bloques en la GUI es trivial y no cambia el netlist.

**En este equipo `LTspice -netlist psu_cvcc.asc` no funciona**: abre ventana y
se queda ahí, y lo mismo pasa con `psu_overengineered/psu.asc`, que la GUI
abre sin problema. O sea que es el binario, no el fichero. Para netlistar sin
GUI está `tools/ltspice/asc2net.py`, que además compara contra un netlist de
referencia:

```bash
python3 tools/ltspice/asc2net.py powersupply/psu_cvcc/psu_cvcc.asc --diff powersupply/psu_cvcc/psu_cvcc.net
```

Desde la GUI, `File > Export Netlist` sigue funcionando.

## Notas de simulación

**El netlist lleva `uic` a propósito.** Sin él el `.op` no converge: fallan
Gmin stepping y source stepping, el pseudo-transitorio "encuentra" un punto
que sale NaN y el transitorio entero hereda el NaN. Lo que lo hace
irresoluble es el lazo de CC colgado del pin ADJ. Con `uic` + `startup` se
arranca de cero con las fuentes en rampa, que es además lo que pasa de verdad
al dar tensión.

**Para medir CC hace falta margen de raíl.** Si la consigna de tensión está
por encima de lo que da la toma, el regulador está en dropout y el lazo de
corriente ni se activa: se mide la carga, no el límite.

**`LM317HV.sub`** es un modelo conductual escrito a partir del datasheet,
porque el `LT317A.sub` que trae LTspice viene cifrado y, siendo la pieza de
40 V, deja de regular por encima (con 50 V de entrada saca 2,98 V en vez de
1,25). Contrastado contra LT317A donde LT317A es válido coincide dentro del
1 %. No modela el apagado térmico, así que `V(Tj)` es informativo. Su ancho de
banda limita el rechazo de rizado medido a 55–58 dB; el real son 80 dB con los
10 µF en ADJ (§8.4.2).

**`LM358.sub`** también es conductual. Se usa en vez del OP747 de `ADI.lib`
porque la pieza que pide el diseño es un LM358 (alimentación simple, modo
común de entrada que incluye masa) y porque el macromodelo del OP747 no
converge en este circuito. No modela el offset de entrada: con los 2–7 mV
típicos del LM358 real, a 80 mA de consigna (26 mV en el shunt) cuenta con un
error del 8–25 %. Si quieres precisión en el extremo bajo, pon un OP07.
