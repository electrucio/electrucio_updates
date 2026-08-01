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
