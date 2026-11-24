# psu_cvcc — fuente lineal DIY con LM317HV, CV + CC ajustables

Tercer diseño de la serie, y el que está pensado para construir. Hecho
**desde cero**: no deriva de [`../psu_overengineered/`](../psu_overengineered/)
ni de [`../psu_simple/`](../psu_simple/). Se ciñe a los circuitos de aplicación
de **TI SNVS773D rev D** (LM117HV/LM317HV, sept. 2015). Lo que no sale de ahí
viene de dos diseños publicados que usan esta misma topología —LM317HV como
elemento de control y operacionales tirando del pin ADJ—: la fuente de
**45 V / 8 A de Silicon Chip** (oct. 2019) y el **ESP Project 223 de Rod
Elliott**. **No hay ninguna decisión de diseño sin precedente en una de esas
tres fuentes**; la tabla de abajo dice de cuál sale cada una.

| | |
|---|---|
| Tensión | **0 – 40,5 V**, pote de 3k9 |
| Corriente | límite ajustable 80 mA – 1,34 A, pote de 4k7, **mantenido hasta el corto franco** |
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
| 0,1 µF a la entrada del regulador | §8.4.1 |

**De la fuente de 45 V / 8 A de Silicon Chip:**

| detalle | por qué lo hacen ellos |
|---|---|
| El divisor vuelve al **borne**, no a masa | sensan en el lado de la carga del shunt «para que la fuente compense automáticamente su caída» |
| `Cadj` referido al raíl de **−5 V** | su condensador de ADJ va al mismo raíl contra el que tiran sus transistores, no a masa |
| El transistor que tira de ADJ trabaja contra **−5 V** | ese raíl existe «para que ADJ pueda bajar de masa», y vale igual para el 0 V y para que el límite de corriente sea efectivo |
| 100 nF en paralelo con `Cout` | su electrolítico de salida es pequeño **a propósito**, para limitar la descarga en un corto y por velocidad |
| 100 nF del cursor del pote de corriente a masa | baja la impedancia de una línea de mando que va al panel y capta ruido que acabaría en la salida |
| `Qcc` = BC546, no 2N3904 | eligen el BC546 porque su colector llega a ver ~50 V |

**Del ESP Project 223 de Rod Elliott:**

| detalle | por qué lo hace él |
|---|---|
| **LM337 a −1,25 V** como referencia del extremo bajo del divisor | es su manera de llegar a 0 V: el chip mantiene OUT−ADJ = 1,25 V, así que ADJ tiene que poder bajar a −1,25 V |
| Resistencia de **220 Ω** en la referencia negativa | le garantiza su carga mínima |
| Trimmer en serie con el pote para el fondo de escala | hace que el dial del panel signifique algo |

Lo único que añade el diseño sobre la figura 32 es hacer el límite
**ajustable**: la figura 32 lo fija por Vbe (0,6 A con 1 Ω) y no se puede
bajar sin poner un shunt enorme. Comparando el shunt contra una referencia
ajustable de un TL431, el rango va de 80 mA a 1,34 A con un shunt de 0,33 Ω.

### Las dos funciones del raíl negativo, separadas

Es la única parte donde hay que combinar los dos diseños en vez de copiar uno:

- La **referencia del divisor** son −1,25 V exactos (P223). Eso pone el cero de
  la escala en `R2 = 0` y no se pierde ni recorrido de pote ni fondo de escala.
- El **emisor de `Qcc`** va a −5 V (Silicon Chip). Contra la referencia de
  −1,25 V el transistor se satura y la salida no puede bajar de su Vce(sat):
  con 0,2 Ω de carga eso son 380 mA, y el lazo de corriente pierde el control
  justo en un cortocircuito. Medido en simulación antes de separarlo.

`Vout = 1,25 · R2 / R1`, con el divisor referido a `VRTN − 1,25 V`.

## Lista de componentes

**Potencia**
- 3 transformadores de ~13 Vrms, secundarios en serie
- SW1 rotativo 1P3T **break-before-make**, + snubber 0,1 µF / 100 Ω
- Puente 1N5408 ×4 (o KBU8M), C 10.000 µF / 63 V, bleeder 10 k / 1 W
- 0,1 µF en la entrada del regulador (§8.4.1)
- **LM317HV en TO-220**, con disipador de ≤2 °C/W y aislador de mica
- R1 = 120 Ω (fija 10,4 mA de carga mínima permanente)
- R2 = pote 3k9 / 1 W (disipa 0,42 W a fondo de escala), vuelve a la
  **referencia de −1,25 V**, que a su vez se referencia al **borne** (`VRTN`),
  no a masa, para que la caída del shunt quede dentro del lazo
- C_ADJ = 10 µF / **63 V** (va al raíl de −5 V, así que ve Vout + 5),
  C_OUT = 10 µF tántalo **+ 100 nF cerámico en paralelo**
- D_ADJ 1N4148 (ADJ→OUT), D_IN 1N5408 (OUT→IN), D_REV 1N5408 (masa→OUT)
- Fusible de primario **+ varistor (MOV) de 275 Vca en el primario**, porque la
  toma alta trabaja a 0,9 V del máximo absoluto del chip con la red en su tope

**Control**
- Shunt 0,33 Ω **/ 2 W** en el retorno, filtro 1 k / 100 nF (en régimen son
  0,59 W, porque el lazo de CC limita a 1,34 A en vez de dejar al chip soltar
  sus 2,19 A; los 2 W son por el transitorio de ~120 ms que tarda en cerrar)
- TL431 + 2k2 → referencia de 2,5 V
- LM358 (medio), integrador 10 k / **1 µF de film** → esquina a 16 Hz. El
  condensador del integrador ve de −5,4 a 0 V: un tántalo se invertiría
- Consigna de corriente: 22 k + pote 4k7, **+ 100 nF del cursor a masa**
  (Silicon Chip: baja la impedancia de la línea de mando, que va al panel)
- NPN **BC546** + 4k7 y 10 k de base, con el **emisor en el raíl de −5 V**.
  No vale un 2N3904: su colector cuelga de VADJ y ve hasta 40 V, y el 2N3904
  son 40 V de Vceo (el BC547, 45). El BC546 son 65 V, y es el que usa Silicon
  Chip por este mismo motivo
- **LM337 en TO-220** a −1,25 V con su pata de referencia en `VRTN`, + 220 Ω de
  carga mínima (disipa 292 mW: en TO-92 entraría, pero caliente). Es la referencia del extremo bajo del divisor, así que su precisión
  aparece 1:1 en la salida: un 1 % son 12 mV de offset en el cero

**Auxiliar**

No se puede sacar del raíl principal: entre TAP=1 y TAP=3 va de 16 a 50 V, y un
resistor+zener dimensionado para dar corriente a 16 V disiparía ~2,4 W a 50 V.

- Un devanado de **12 Vca** propio, con **dos rectificadores de media onda** en
  sentidos opuestos (2 × 1N4007) y el extremo del devanado como común:
  **±17 V** brutos. Un solo devanado da los dos raíles; el puente completo
  plegaría el semiciclo negativo y perdería el que hace falta
- **1000 µF / 35 V en cada raíl** (±17 V, hasta ±19 V con la red alta). Media
  onda son 50 Hz, el doble de rizado que con puente: `I/(f·C)` = 0,3 V con los
  15 mA del control, que el 7812 y el LM337 se comen sin despeinarse
- **7812** → +12 V para el TL431 y el V+ del LM358
- **79L05** → −5 V para el V− del LM358, el emisor de `Qcc` y `Cadj`
  (Silicon Chip usa un regulador para su −5 V, no un zener: ese raíl es la
  referencia de alterna de `Cadj`, así que tiene que estar limpio)
- **LM337** colgado del −17 V → los −1,25 V de la referencia del divisor

Con dos unidades para una fuente simétrica: **un solo transformador auxiliar con
dos secundarios independientes** (2 × 12 V, 4 hilos), un secundario por unidad.
Compartir un devanado uniría los dos comunes y las unidades dejarían de flotar;
apiladas, eso cortocircuita la salida de la de abajo.

## Medido en simulación

Dos scripts, con dos propósitos distintos:

- `python3 tools/ltspice/verify_psu_cvcc.py` — suite de **regresión**: comprueba
  que el diseño sigue haciendo lo que hacía.
- `python3 tools/ltspice/caracteriza_psu_cvcc.py` — **caracterización**: mide los
  parámetros con los que se juzga una fuente de banco, los mismos que publican
  Silicon Chip y Rod Elliott, para poder compararse con ellos.

### Exactitud de la tensión

`Vout = 1,25 · R2/120`, medido en el borne, TAP=3, carga de 100 Ω:

| pote | teórico | medido | error |
|---|---|---|---|
| 0 % | 0 V | **0,006 V** | — |
| 1 % | 0,408 V | 0,411 V | +0,77 % |
| 3 % | 1,225 V | 1,223 V | −0,12 % |
| 10 % | 4,082 V | 4,064 V | −0,45 % |
| 50 % | 20,410 V | 20,268 V | −0,69 % |
| 100 % | 40,820 V | 40,461 V | −0,88 % |

El error crece de forma monótona con el ajuste: es error de **ganancia**, no de
offset, así que un trimmer en serie con R2 lo corrige entero (es lo que hace el
P223 con su TP1). Y el cero es cero de verdad: 6 mV con el pote al mínimo.

### Regulación de carga

De vacío (1 kΩ) a la corriente máxima de cada ajuste. `Zo` es la impedancia de
salida:

| ajuste | vacío | con carga | I | caída | regulación | Zo |
|---|---|---|---|---|---|---|
| 0,5 V | 0,502 V | 0,502 V | 0,50 A | 0,4 mV | **0,09 %** | 0,9 mΩ |
| 5 V | 4,992 V | 4,991 V | 0,50 A | 1,5 mV | **0,03 %** | 3,1 mΩ |
| 20 V | 19,930 V | 19,922 V | 0,91 A | 7,4 mV | **0,04 %** | 8,4 mΩ |
| fondo | 40,471 V | 40,453 V | 0,86 A | 18,7 mV | **0,05 %** | 22,8 mΩ |

Para comparar, la única cifra publicada de las tres fuentes de referencia:
Silicon Chip declara **<0,5 %** en su fuente de 30 V / 2 A. Del P223 no hay dato
de regulación de carga. Esto sale de sensar en el borne; con el divisor a masa
serían 0,33 V de caída a 1 A, o sea un 1,7 % a 20 V.

### Regulación de línea

Red a ±10 %, TAP=2, 20 V, 22 Ω:

| red | VRAW | Vout | rizado |
|---|---|---|---|
| 207 V | 27,6 V | 19,916 V | 0,76 mV |
| 230 V | 31,1 V | 19,922 V | 0,78 mV |
| 253 V | 34,6 V | 19,928 V | 0,79 mV |

**11,9 mV** en total = 0,060 %, que sobre los 7 V que se mueve el raíl son
0,009 %/V. El datasheet promete 0,01 %/V típico (§7.5).

### Exactitud de la corriente

TAP=2 con 2,2 Ω de carga, que fuerza CC en todo el recorrido:

| pote | consigna | medido | error |
|---|---|---|---|
| 2 % | 32,3 mA | 32,4 mA | +0,12 % |
| 5 % | 80,3 mA | 80,3 mA | +0,05 % |
| 20 % | 311,2 mA | 311,3 mA | +0,01 % |
| 40 % | 598,0 mA | 598,0 mA | +0,01 % |
| 100 % | 1337,0 mA | 1337,1 mA | 0,00 % |

El desvío es un offset fijo de +40 a +50 µA en todo el recorrido (corriente del
pin ADJ y de entrada del operacional), despreciable salvo en el extremo.

**Pero el asiento es lento en la parte baja de la escala, y mucho.** Con la
consigna al 2 %, a los 2 s entrega 1,55 mA y no llega a los 32,35 mA hasta
pasados **unos 4 s**. Durante ese rato la salida está pegada a cero y entrega
*menos* de lo pedido, nunca más.

La causa no es saturación contra un raíl, es la **banda muerta** que tiene que
cruzar la salida del operacional, y se ve midiendo dónde se para en cada modo:

| modo | CCOUT | Ic(Qcc) |
|---|---|---|
| CV, sin limitar | −4,980 V (pegado a su raíl) | 0 mA |
| CC al 40 % | −3,733 V | 9,7 mA |
| CC al 100 % | −3,760 V | 8,9 mA |

Entre «Qcc cortado» y «Qcc gobernando» hay **1,25 V**, que es el Vbe dividido
por la relación de `Rb`/`Rbe`. El integrador cruza esa banda a
`(ISET − SENSE) / (Rint·Cint)` voltios por segundo: 44 V/s con la consigna al
100 % (decenas de ms) y **1,07 V/s con la consigna al 2 %** (más de un segundo
solo en cruzarla, más lo que se haya pasado en el arranque).

**Un diodo anti-windup sobre `Cint` no lo arregla**, aunque lo parezca: probado
en simulación, con y sin él sale exactamente lo mismo (1,55 mA a los 2 s,
32,3 mA a los 4 s). El integrador nunca se enrolla por encima de `V(CCIN)+0,6`
—lo más lejos que llega es −2,05 V—, así que el diodo no llega a conducir nunca.

Y los dos únicos botones que tocarían la banda muerta tampoco valen: subir la
relación `Rbe/Rb` no baja de ~0,7 V (es un Vbe), y acelerar el integrador
bajando `Rint` o `Cint` llevaría la esquina del lazo de los 16 Hz actuales a los
100 Hz del rectificador, que es exactamente el problema que tiene
`../psu_overengineered/`. Así que es inherente a esta topología: se documenta y
ya está. La pega está en el sentido seguro.

### CC como fuente de corriente

Consigna al 40 % (598 mA), bajando la carga hasta el corto franco:

| carga | 10 Ω | 1 Ω | 0,1 Ω | 0,05 Ω | 0,01 Ω |
|---|---|---|---|---|---|
| I | 598,0 mA | 598,0 mA | 598,0 mA | 598,0 mA | 598,0 mA |
| Vout | 5,98 V | 598 mV | 59,8 mV | 29,9 mV | 6,0 mV |

**0,00 mA de desviación en tres décadas de carga.** Esto es lo que compra el
raíl de −5 V: con el emisor de `Qcc` en la referencia de −1,25 V, el transistor
se satura y la corriente se dispara a 380 mA con 0,2 Ω.

### Estabilidad

Escalones con flancos de 1 µs, que es lo que piden los hilos de EEVblog para que
la medida valga:

| escalón | desviación | establece en |
|---|---|---|
| carga 0,2 → 0,9 A (en CV) | −231 mV | 2,26 ms |
| carga 0,9 → 0,2 A (en CV) | +231 mV | 2,32 ms |
| carga que cruza a CC | −251 mV | 120 ms |
| vuelta de CC a CV | +25 mV | 61 ms |
| consigna 20 V → 0,5 V | 0 mV | 4,0 ms |
| consigna 0,5 V → 20 V | +82 mV | 76 ms |

**Sin oscilación en ningún caso.** Los 2,3 ms del escalón de carga en CV son del
orden de los 2 ms que mide Silicon Chip quitando 4 A a 25 V, y con menos
desviación (231 mV contra ~500 mV), aunque ellos mueven 4 A y aquí son 0,7.

Los 120 ms de la entrada en CC son el integrador de 16 Hz, puesto a propósito
lejos de los 100 Hz del rectificador. Silicon Chip reconoce la misma pega en su
fuente: su CC es lento y un escalón le hace pasar de 7 A con el límite en 5.

La asimetría bajada/subida (4 ms contra 76 ms) es la misma que ellos describen y
buscan: la salida puede **caer** deprisa, que es lo que importa en una
sobrecarga, y sube despacio porque `Cadj` se carga a través de R1.

Rizado en régimen, sin escalón:

| caso | rizado salida | rizado raíl | rechazo |
|---|---|---|---|
| vacío | 0,06 mV | 31 mV | 54,7 dB |
| 1 A | 0,78 mV | 623 mV | 58,1 dB |
| 0 V | 0,02 mV | 14 mV | 56,5 dB |
| en CC | 1,04 mV | 865 mV | 58,4 dB |

### Arranque

El P223 acabó poniendo un relé de salida con 2,5 s de retardo por un
sobreimpulso de ~4 V al encender. Aquí, medido:

| ajuste | Vout | pico | sobreimpulso |
|---|---|---|---|
| 20 V | 19,927 V | 19,927 V | 0 mV |
| fondo | 40,461 V | 40,462 V | 0 mV |
| 0,5 V | 0,502 V | 1,185 V | **683 mV** |
| 0 V | 0,005 V | 0,005 V | 0 mV |

En los ajustes altos no hay sobreimpulso. En **0,5 V sí: 683 mV**, que sobre
medio voltio es un 136 %. Sale de que `Cadj` arranca descargado y ADJ se pasa
mientras se carga. No llega a los 4 V del P223 y no necesita su relé, pero la
costumbre de taller sigue valiendo: ajusta la tensión antes de conectar la
carga.

### Protecciones

Corto franco de 0,01 Ω en las tres tomas, con el límite al máximo y al mínimo:

| toma | límite | I | Vin−Vout | P | Tj régimen | |
|---|---|---|---|---|---|---|
| TAP=1 | máx | 1,337 A | 14,0 V | 18,3 W | 104 °C | aguanta indefinidamente |
| TAP=1 | mín | 0,080 A | 16,7 V | 1,5 W | 32 °C | ni se entera |
| TAP=2 | máx | 1,337 A | 29,8 V | 39,5 W | 195 °C | corta el apagado térmico |
| TAP=2 | mín | 0,080 A | 34,6 V | 3,1 W | 38 °C | ni se entera |
| TAP=3 | máx | **0,829 A** | 47,7 V | 39,4 W | 194 °C | corta el apagado térmico |
| TAP=3 | mín | 0,080 A | 52,4 V | 4,8 W | 45 °C | ni se entera |

Tres cosas que leer de esa tabla:

1. **En TAP=3 el límite que manda no es el tuyo, es el del chip.** Pides 1,337 A
   y salen 0,829: a 47 V de diferencial el plegado SOA interno no da más. Las
   protecciones nativas siguen acotando por encima de la consigna, que era el
   requisito de partida.
2. **Con el límite bajo, el problema térmico desaparece.** Los 39 W y el ciclado
   térmico solo aparecen con el pote de corriente a fondo. A 80 mA la unión no
   pasa de 45 °C en ninguna toma. El límite de corriente, bien puesto, *es* la
   protección térmica.
3. **El diferencial no llega a los 60 V** del máximo absoluto en ninguno de
   esos casos: 52,4 V en el peor. Esa —y no la temperatura— es la condición que
   destruye el chip, y §8.3.2 avisa de que en TO-220 lo típico es que reviente
   el encapsulado. Pero hay un caso peor que no es un corto: ver abajo.

Sobrecarga progresiva (TAP=2, 20 V pedidos, límite al máximo):

| carga | 100 Ω | 22 Ω | 15 Ω | 10 Ω | 4,7 Ω | 1 Ω |
|---|---|---|---|---|---|---|
| I | 0,199 A | 0,906 A | 1,328 A | 1,337 A | 1,337 A | 1,337 A |
| Vout | 19,93 V | 19,92 V | 19,92 V | 13,37 V | 6,28 V | 1,34 V |
| modo | CV | CV | CV | **CC** | CC | CC |
| Tj | 37 °C | 68 °C | 79 °C | 118 °C | 159 °C | 187 °C |

La transición CV→CC cae en 15 Ω y es limpia. Por debajo de 10 Ω la unión se va
por encima de los 125 °C y acaba cortando: es el precio de trabajar a tensión
baja con la toma alta, y por eso la regla de bajar de toma antes de bajar la
tensión.

### El caso que de verdad puede romper el chip: TAP=3 en vacío

Con los transformadores reales (13,0 V en vacío, 0,40 Ω de resistencia de
fuente, medidos en el banco y clavados por el modelo), tres devanados en serie
dan un raíl de **59,1 V** con la red en su tope legal de 253 V. Con la salida en
cero, ese es el diferencial completo sobre el chip:

| pote (TAP=3, red a 253 V, sin carga) | Vout | diferencial | margen |
|---|---|---|---|
| 0 % | 0,01 V | **59,1 V** | **0,9 V** |
| 10 % | 4,07 V | 55,0 V | 5,0 V |
| 20 % | 8,12 V | 51,0 V | 9,0 V |
| 30 % | 12,18 V | 46,9 V | 13,1 V |
| 50 % | 20,28 V | 38,8 V | 21,2 V |
| 100 % | 40,49 V | 18,6 V | 41,4 V |

**Decisión tomada a sabiendas:** se mantienen los tres devanados, con la regla
de **no bajar del 20 % del pote estando en TAP=3**. La alternativa evaluada era
dejar la toma alta en dos devanados (0–31 V, 39,1 V de diferencial en el peor
caso, 21 V de margen); se descartó por conservar el rango hasta 40,5 V.

No es una decisión sin precedente: la fuente de Silicon Chip alimenta su
LM317HV con un raíl de **57 V** y lleva la salida hasta 0 V, o sea que también
trabaja a 3 V del máximo absoluto.

Lo que sí conviene añadir, porque es lo único de esta condición que no está en
tu mano: un **varistor (MOV) en el primario**. El +10 % de la red lo gestionas
tú con el mando; un pico de red, no.

### Los potenciómetros no llevan potencia

Es el fallo clásico del LM317 como regulador de corriente —el pote en serie con
la carga, que se quema— y aquí no lo tiene ninguno de los dos:

| escenario | R2 (tensión) | pote de corriente | shunt |
|---|---|---|---|
| fondo en vacío | 420 mW | 0,0 mW | 1 mW |
| 20 V a 1 A | 207 mW | 0,0 mW | 363 mW |
| corto, límite máx | 0 mW | 0,0 mW | 590 mW |

R2 lleva los 10,4 mA del divisor, no la corriente de carga: 420 mW de peor caso
en un pote de 1 W. El de corriente solo divide los 2,5 V del TL431:
microamperios. **Ninguno de los dos necesita ser bobinado**, que era el
requisito.

## El rizado depende del margen de raíl, y el salto es brusco

Es lo primero con lo que te vas a topar. El LM317HV necesita ~2 V de caída
para regular; por debajo entra en dropout y **la salida copia el rizado del
raíl 1:1**. Y como el pote llega hasta 40,6 V en cualquier posición del
selector, en las tomas bajas es fácil pedirle más de lo que puede dar.

**Hasta dónde puedes subir el pote sin caer en dropout** (carga ligera):

| toma | devanados | VRAW+ | pote máximo | Vout máx | por encima de eso |
|---|---|---|---|---|---|
| TAP=1 | uno | 16,5 V | ~30 % | 12,1 V | 121 mV de rizado, 0 dB |
| TAP=2 | dos | 33,3 V | ~70 % | 28,3 V | 246 mV de rizado, 0 dB |
| TAP=3 | tres | 49,9 V | **100 %** | 40,5 V | **no llega a dropout** |

En TAP=3 el pote no puede meterte en dropout: al máximo todavía quedan 9,2 V de
margen. En TAP=1 y TAP=2 sí, y el salto es brusco:

| toma | pote | Vout | margen | rizado salida | rechazo |
|---|---|---|---|---|---|
| TAP=2 | 80 % | 31,17 V | 2,01 V | **247 mV** | **0,0 dB** |
| TAP=2 | 70 % | 28,31 V | 4,89 V | 0,3 mV | 57,1 dB |
| TAP=1 | 50 % | 14,45 V | 2,01 V | **123 mV** | **0,0 dB** |
| TAP=1 | 30 % | 12,13 V | 4,35 V | 0,2 mV | 56,4 dB |

No hay zona intermedia: o tienes 3 V de margen y el rizado son décimas de
milivoltio, o no lo tienes y sale el rizado entero del condensador. **Regla:
`VRAW_min − Vout ≥ 3 V`.** Por eso el `.asc` viene con `Vset=0.5` (20,3 V); con
`Vset=1` en TAP=2 arranca en dropout y parece que el diseño es malo.

Ojo al leer la columna del rizado del raíl: crece con la toma (121 / 247 /
314 mV) **porque crece la corriente**, no por la toma en sí. Estas medidas son
con una carga fija de 100 Ω, así que a más tensión de salida más corriente.
El rizado del raíl es `I / (2·f·C)` y no depende de la tensión.

A plena corriente el raíl cae ~1,5 V más, así que el techo útil de cada toma
con 1 A es menor que en vacío: 11 V en TAP=1, 27 V en TAP=2, 39 V en TAP=3.

## ¿Qué pasa si cortocircuito la salida?

Las cifras están arriba, en **Protecciones**. El resumen: no se rompe, y con la
referencia negativa puesta **el que manda en un corto es tu pote de corriente**,
no el límite interno del chip. Eso cambia las dos cosas que sufrían:

- **Rshunt.** Antes, en un corto en TAP=1 el chip soltaba sus 2,19 A y el shunt
  disipaba 1,58 W. Ahora el lazo lo clava en 1,337 A y son **0,59 W**. Uno de
  1 W vale; de 2 W por el transitorio de ~120 ms que tarda el lazo en cerrar,
  durante el cual puede ver los 1,58 W de antes.
- **El electrolítico de 10.000 µF**, si va pegado al disipador. Con el disipador
  a 60-70 °C la vida útil se desploma. Sepáralo.

Y lo que no cambia: en ninguna toma el diferencial llega a los **60 V** del
máximo absoluto (52,4 V en el peor caso). Esa —y no la temperatura— es la
condición que destruye el chip, y §8.3.2 avisa de que en TO-220 lo típico es que
reviente el encapsulado. TI describe la combinación de límite de corriente,
plegado SOA y apagado térmico como *"blowout proof"* (§3).

## Disipación: peor caso de cada componente

`verify_psu_cvcc.py --only power` recorre 12 escenarios (las tres tomas ×
vacío / 1 A / salida mínima a 1 A / cortocircuito) y saca el peor caso de cada
componente:

| componente | peor caso | escenario | nominal |
|---|---|---|---|
| **LM317HV** | **41,9 W** | T3, 2 V a 1 A | 20 W → corta el apagado térmico |
| Puente (4 diodos) | 1,78 W | T2 corto | 1N5408 de sobra |
| Rshunt 0,33 | 0,59 W | T1 corto | **1 W vale, 2 W con margen** |
| R2 pote 3k9 | 0,42 W | T3 vacío | 1 W vale |
| Rbleed 10k | 0,29 W | T3 vacío | 1 W vale |
| resto | <0,05 W | | 1/8 W vale |

**El peor caso ya no es el cortocircuito, es usar la fuente.** Con la referencia
negativa, un corto queda limitado por tu pote (39 W en el peor caso, TAP=2 a
fondo), mientras que pedir **2 V a 1 A en TAP=3** son 41,9 W, porque ahí el chip
se come los 45 V de diferencia. Dicho de otro modo: la fuente aguanta mejor un
accidente que un uso descuidado del selector de tomas. De ahí la regla de bajar
de toma antes de bajar la tensión.

Y el dato de dimensionado que más fácilmente muerde: **el pico por cada diodo
del puente es de 5,33 A y el RMS por el secundario 2,38 A** en el peor caso de
la matriz. Es el factor de forma normal de un rectificador con condensador a la
entrada, y significa que los transformadores hay que dimensionarlos para eso: a
12 V son unos **29 VA por devanado**, no los 12 VA que sugeriría 1 A × 12 V. Los
de 50 W van cómodos.

## Esfuerzo de cada componente: qué comprar exactamente

`caracteriza_psu_cvcc.py --only esfuerzos` recorre las tres tomas en vacío / a
1 A / en corto **con la red a 253 V**, que es el peor caso de tensión, y saca el
peor esfuerzo de cada pieza. Las tensiones son de pico e incluyen el arranque.

### Condensadores

| ref | valor | pico medido | qué comprar |
|---|---|---|---|
| `Cbulk` | 10.000 µF | 59,1 V | **63 V**. Mídelo al recibirlo: a 2,5 V del nominal no hay sitio para sorpresas |
| `Cin` | 0,1 µF | 59,1 V | 63 V, cerámico o film |
| `Csnub` | 0,1 µF | **60,1 V en alterna** | **film de 250 Vca (clase X2)**. Va en serie con `Rsnub` a través del secundario: trabaja en alterna, no en continua. Un cerámico de 63 V aquí es un error |
| `Cadj` | 10 µF | 44,5 V | **63 V**. Cuelga del raíl de −5 V, así que ve Vout + 5 |
| `Cout` | 10 µF | 40,8 V | 63 V (50 V es el mínimo) |
| `Cout_hf` | 100 nF | 40,8 V | 63 V cerámico |
| `Cint` | 1 µF | **−5,4 a 0,0 V** | **film**, no tántalo: se queda justo en el límite de invertirse |
| `Cfilt`, `Cref`, `Cpot_i` | 100 nF | <2,6 V | cualquiera, 16 V sobra |

Los dos que más fácilmente se compran mal son `Csnub` (que hay que pedir como
condensador de red, no de continua) y `Cint` (que un tántalo de 1 µF parece la
elección obvia y es la equivocada).

### Resistencias

| ref | valor | peor caso | escenario | qué comprar |
|---|---|---|---|---|
| `Rshunt` | 0,33 Ω | **590 mW** | T1 en corto | **2 W**, hilo bobinado |
| `R2` (pote de tensión) | 3k9 | **420 mW** | T3 en vacío | **1 W** |
| `Rbleed` | 10k | **349 mW** | T3 en vacío | **1 W** |
| `Rref` | 2k2 | 41 mW | T1 en vacío | 0,25 W |
| `R1` | 120 Ω | 13 mW | T2 en corto | 0,25 W |
| `Rnbleed` | 220 Ω | 7 mW | T1 en vacío | 0,25 W |
| `Rsnub` | 100 Ω | 0,2 mW | — | 0,5 W (por el pico de conmutación, no por la media) |
| `Rset`, `Rpot_i`, `Rint`, `Rb`, `Rbe`, `Rfilt` | — | <1 mW | — | 0,25 W de las normales |

Solo tres resistencias se salen de 1/4 W, y las tres por motivos distintos: el
shunt por el corto, y el pote de tensión y el bleeder porque **trabajan en
vacío con el raíl alto**, que es la condición que uno no mira.

### Semiconductores

| ref | esfuerzo medido | ¿disipador? |
|---|---|---|
| **LM317HV** | **44,2 W** en el peor caso | **sí, ≤2 °C/W y aislador de mica.** Es el único |
| `Qcc` (BC546) | **128 mW**, con Vce de pico de **44,5 V** | no. TO-92 de 500 mW, con 4× de margen |
| Puente (1N5408 ×4) | 5,47 A de pico, 0,67 A de media por diodo | no. 3 A continuos y 200 A de pico |
| `D_REV`, `D_IN` (1N5408) | ~0 A en operación normal | no. Son diodos de fallo |
| `D_ADJ` (1N4148) | ~0 A | no |
| TL431 | 11 mW | no |
| LM358 | 34 mW | no |

Dos cosas que se ven aquí y conviene saber:

- **`Qcc` no disipa lo que parece.** Su corriente no son los 10,4 mA del
  divisor, sino la *diferencia* entre esos 10,4 mA y lo que sigue pasando por
  R2, porque R2 sigue conduciendo mientras ADJ no esté en el suelo. El producto
  `Vce · Ic` tiene un máximo analítico en Vout ≈ 18 V que vale 126 mW, y medido
  salen 128. Con un TO-92 sobra.
- **Los 44,5 V de pico de `Qcc` justifican el BC546.** Un BC547 son 45 V de
  Vceo: habría quedado medio voltio por debajo del máximo absoluto, y un 2N3904
  (40 V) directamente fuera.

### Los reguladores del auxiliar

No están en la simulación —el auxiliar se modela como fuente ideal—, así que
esto es a mano, con el raíl bruto en su peor caso (13,0 V de devanado × 1,414 −
0,7 de un diodo = 17,7 V a 230 V, **19,5 V a 253 V**):

| regulador | salida | corriente | disipación | ¿disipador? |
|---|---|---|---|---|
| **7812** | +12 V | 10 mA (TL431 4,3 + LM358 2 + margen) | **75 mW** | no |
| **79L05** | −5 V | 13 mA (LM358 + los 10,4 mA del emisor de `Qcc`) | **189 mW** | no, TO-92 va justo pero entra |
| **LM337** | −1,25 V | 16 mA (divisor 10,4 + sangrador 5,7) | **292 mW** | no, pero **en TO-220**, no en TO-92 |

El LM337 en TO-92 (LM337L) se quedaría en 292 mW de unos 600 mW nominales:
entra, pero caliente. En TO-220 son 292 mW de 2 W al aire y ni se entera; vale
lo mismo y es la pieza de la que depende el cero de tu escala de tensión, que
además deriva con la temperatura. Que esté fría es gratis.

**Resumen: el único componente que necesita disipador en toda la fuente es el
LM317HV.** Todo lo demás, al aire.

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
disipador de 2 °C/W: TAP=1 para 0–12 V, TAP=2 para 12–28 V, TAP=3 para
28–40,5 V. Con la toma equivocada (salida baja, toma alta) el TO-220 disipa
42 W y acaba cortando por temperatura. A plena corriente la regla es más
estricta, porque hay que quedarse por debajo de ~20 W:

| toma | a 1,34 A, Vout mínimo sin pasar de 20 W |
|---|---|
| TAP=1 | cualquiera: 15 V × 1,34 A = 20 W es el tope |
| TAP=2 | ≥ 16 V |
| TAP=3 | ≥ 32 V |

**El selector tiene que ser break-before-make.** Uno make-before-break
cortocircuita un devanado al pasar de posición. Conmuta con la salida
descargada: cortar 160 mH con corriente hace arco en los contactos.

**No hay OVP.** Si el regulador falla en corto, la carga ve el raíl entero
(hasta 50 V). Es el único modo de fallo que no cubre nada, y las protecciones
nativas del chip no lo cubren por definición. Si en algún momento quieres
taparlo, lo clásico son tres componentes: zener + SCR + fusible.

## Esquemático

`psu_cvcc.asc` genera un netlist equivalente a `psu_cvcc.net`: mismos 70
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
