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

En [`docs/`](docs/) está la investigación en foros de la que salió el
planteamiento (tomas en el transformador, límite ajustable con potenciómetro, y
por qué no se usó ninguna de las topologías alternativas), y la referencia del
artículo de Silicon Chip, que es de pago y no se versiona.

| | |
|---|---|
| Tensión | **0 – 40,5 V**, dos potes de panel en serie: 10k grueso + 1k fino |
| Corriente | límite ajustable 80 mA – 1,34 A, pote de 4k7, **mantenido hasta el corto franco** |
| Tomas | 3, selección **manual** con rotativo 1P3T |
| Protecciones | las **nativas** del chip: límite de corriente con plegado SOA, cortocircuito y apagado térmico |

## De dónde sale cada parte

| bloque | referencia |
|---|---|
| Regulador ajustable con R1/R2 | fig. 16, §9.2.1 |
| Condensador en ADJ para el rechazo de rizado | fig. 21, §9.2.5 (la idea; el **valor** se midió aparte, ver más abajo) |
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
| **Sumidero de carga mínima** (su Q8/Q9, ~6 mA) | «In a fixed voltage application, a resistor would be adequate, **but not in this case**. To ensure a minimum current is sunk across the full voltage range, a constant current configuration with a pair of BC546 transistors is used» |

El sumidero tiene **precedente doble**: es a la vez el Q8/Q9 de Silicon Chip y
el Q1 del P223, y los dos llegan a él por el mismo razonamiento que está escrito
en el bloque 5b del esquemático.

**Del ESP Project 223 de Rod Elliott:**

| detalle | por qué lo hace él |
|---|---|
| **LM337 a −1,25 V** como referencia del extremo bajo del divisor | es su manera de llegar a 0 V: el chip mantiene OUT−ADJ = 1,25 V, así que ADJ tiene que poder bajar a −1,25 V |
| Resistencia de **220 Ω** en la referencia negativa | le garantiza su carga mínima |
| Trimmer en serie con el pote para el fondo de escala | hace que el dial del panel signifique algo |
| **Depósito partido en CRC** (él: 2 × 2200 µF con 1 Ω/5 W en medio) | es su «mínimo recomendado» de filtrado. Aquí **no va montado**, pero sus pads sí: ver abajo |

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

### En qué nos separamos de cada uno

Copiar la topología no es copiar el diseño. Las diferencias importan tanto como
los parecidos, y además explican casi todo lo que se ve en [`curvas/`](curvas/).

**De TI**: seguimos sus figuras más literalmente que ninguna de las dos fuentes
publicadas —somos los únicos que montamos la 32 tal cual—, y lo único que
añadimos es hacer el límite ajustable con el TL431.

**De Silicon Chip**, tres diferencias grandes:

| ellos | nosotros | consecuencia |
|---|---|---|
| Controlan ADJ **activamente** con dos operacionales: «a phenomenal amount of gain in the control loop, which is handy to have for fast response, but needs to be carefully controlled to avoid oscillation» | La tensión la fija un **divisor resistivo pasivo**; solo hay operacional en el lazo de corriente | Ellos compran velocidad y pagan compensación. Nosotros compramos estabilidad incondicional y pagamos velocidad |
| `Cadj` de **100 nF**: «the LM317HV only sources about 10 µA out of its ADJ pin, meaning its output **can only rise by 1 V per millisecond**» | `Cadj` de **1 µF** (eran 10 µF hasta que se midió el compromiso) | Ellos siguen siendo 10× más rápidos al subir; nosotros conservamos 11 dB más de rechazo |
| Sensan la corriente en **alta** con un INA282 (ganancia 50, shunt de 15 mΩ) | En **baja**, con la fig. 32 y un BC546 | Más barato y más simple; nos ahorra la pieza que el handoff daba por imprescindible |
| Refuerzan con Q4–Q7 hasta **8 A**, 500 VA, dos ventiladores con NTC | **1,34 A** y tres tomas a mano | Es otro aparato |
| Sus mandos son **potes lineales de 10k de 24 mm corrientes**, porque allí los potes solo dividen una referencia | El pote de tensión **es** el divisor de realimentación | De ahí toda la cuenta de `Vmax²/R2` de más abajo |

**Del P223**, la diferencia principal es dónde va el limitador:

| él | nosotros |
|---|---|
| Limitador **antes** del regulador, en la línea de entrada, disparado por la Vbe de un transistor, con **rangos fijos** (33 mA / 330 mA / máx.) porque un pote ahí da un rango corto | Limitador **después**, en el retorno de la salida, y **continuo** de 32 mA a 1,34 A |
| Trimmer en serie con el pote | Trimmer en `R1`: con potes de panel de ±20 % hay que corregir en los dos sentidos, y subir `R1` baja el fondo sin gastar recorrido |
| Relé de salida con 2,5 s de retardo por un sobreimpulso de ~4 V al encender | Medido 0 mV en los ajustes altos; no hace falta |
| Dos canales en serie/paralelo | Uno |

**De los foros** no salió circuito, salieron criterios: el presupuesto térmico de
~10 W por TO-220 (de donde salen las tomas), medir los escalones con flancos de
1 µs, el aviso de que los relés en las tomas se sueldan con la corriente de carga
de los condensadores, y el «nunca pongas el pote en serie con la carga».

### Lo que deliberadamente no es

Media explicación del diseño son los caminos que no se tomaron:

- el clásico **0-30V/0-3A discreto** (Audioguru, Smart Kit 1138) y los diseños de
  **xavier60 / JuanGg** en EEVblog: operacionales + transistor de paso. Más
  rápidos y escalables, pero te quedas sin las protecciones nativas del chip;
- los **35 V / 4 A de Greg Jolley**, que es el estado del arte del DIY discreto
  —publica 2 µs de recuperación con 15 % de sobreimpulso, y con medidas reales,
  o sea **tres órdenes de magnitud más rápido que esto**—;
- el **LM723**, que era el camino de los 80;
- el **LT3080/LT3081**, el «hazlo con un chip mejor»;
- y el módulo **RuiDeng**, el «no lo hagas».

### El resumen, para cuando haya que contarlo

Es un diseño derivado de los **circuitos de aplicación de TI**, construido
literalmente sobre las figuras 16, 21, 15, 31 y 32 del SNVS773D, con dos fuentes
publicadas como precedente de cada decisión que el datasheet no cubre: la de
**45 V / 8 A de Silicon Chip** (misma topología y misma familia de chip, de donde
salen el raíl negativo, el sumidero de carga mínima y media docena de valores) y
el **Project 223 de Rod Elliott** (de donde sale la referencia de −1,25 V que
permite llegar a 0 V). No hay ninguna decisión sin precedente en una de esas
tres, salvo una: hacer ajustable el límite de la figura 32 comparando el shunt
contra una referencia de TL431. Frente a Silicon Chip es el mismo circuito
simplificado —un décimo de la corriente, control de tensión pasivo en vez de dos
lazos activos, sensado en baja en vez de un INA282— a cambio de ser lo bastante
simple como para estar caracterizado entero. Frente al P223 es su mitad baja con
un limitador distinto: continuo y en el retorno, en vez de por rangos y en la
entrada.

## Lista de componentes

**Potencia**
- 3 transformadores de ~13 Vrms, secundarios en serie
- SW1 rotativo 1P3T **break-before-make**, + snubber 0,1 µF / 100 Ω
- Puente 1N5408 ×4 (o KBU8M), bleeder 10 k / 1 W en el lado del rectificador
- **Un** depósito de 10.000 µF / 63 V
- **Pads reservados para un filtro CRC** (`Rcrc` en serie en el raíl con un
  puente de 0 Ω, `Cbulk2` en paralelo a la entrada del regulador). **No van
  montados**, y el porqué está en «¿Hace falta el filtro CRC?» más abajo
- 0,1 µF en la entrada del regulador (§8.4.1)
- **LM317HV en TO-220**, con disipador de ≤2 °C/W y aislador de mica
- R1 = 270 Ω + **TP1, trimmer de 150 Ω** en serie. Fija la **escala**, no la
  carga mínima: `Vout = 1,25·(R2c+R2f)/R1`, y con 340 Ω el fondo cae en 40,5 V.
  TP1 absorbe la tolerancia de los potes (±20 % en los de panel) y el error de
  ganancia del Iadj; **subirlo baja el fondo de escala**, que es el sentido en
  el que hay que corregir porque el Iadj de la pieza real deja la salida alta
- R2 = **dos potes de panel corrientes en serie**: `R2c` 10k de grueso + `R2f`
  1k de fino. Disipan **139 mW y 14 mW** a fondo de escala, así que valen un
  24 mm de 0,25 W y cualquier cosa, respectivamente. El fino cubre 1k/11k del
  recorrido, o sea 3,7 V en 270°: **14 mV por grado, lo mismo que un
  multivuelta de 10 vueltas**. Los dos con el cursor unido al extremo libre.
  Vuelven a la **referencia de −1,25 V**, que a su vez se referencia al
  **borne** (`VRTN`), no a masa, para que la caída del shunt quede dentro del
  lazo
- **`Q_min` = BD139 en TO-126** + `Rb_min` 1k a −5 V + `Re_min` 1k3 / 3 W al
  bruto de −17 V: el sumidero de carga mínima, que es **lo que permite que los
  potes sean de panel**. Da 8,6 mA constantes, los mismos a 40 V que a 0 V.
  Disipa 404 mW. Es el Q1 del ESP Project 223
- C_ADJ = **1 µF / 63 V, y de film** (va al raíl de −5 V, así que ve Vout + 5;
  a 1 µF ya no hace falta electrolítico, que es mejor ESR y mejor vida),
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
  carga mínima (disipa 164 mW desde que el divisor solo pide 3,6 mA: en TO-92
  ya entra holgado). Es la referencia del extremo bajo del divisor, así que su precisión
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

`Vout = 1,25 · R2/R1 + Iadj · R2` (la ecuación 1 de TI), medido en el borne,
TAP=3, carga de 100 Ω:

| pote | R2 | teórico | medido | error |
|---|---|---|---|---|
| 0 % | 0 Ω | 0 V | **−0,002 V** | — |
| 1 % | 110 Ω | 0,410 V | 0,404 V | −5 mV |
| 3 % | 330 Ω | 1,230 V | 1,227 V | −2 mV |
| 10 % | 1k1 | 4,099 V | 4,107 V | +8 mV |
| 50 % | 5k5 | 20,496 V | 20,535 V | +40 mV |
| 100 % | 11k | 40,991 V | **41,007 V** | **+16 mV (0,04 %)** |

Lo que queda es un **offset de milivoltios**, no un error de ganancia, y encima
cambia de signo por el camino: negativo hasta los 2 V y positivo a partir de
ahí. **El peor error relativo por encima de 1 V es del 0,25 %.** El cero es cero
de verdad: −2 mV con los potes al mínimo.

Estas cifras mejoraron al sustituir la fuente conductual de la referencia
negativa por el **LM337 de verdad** (modelo de TI) el 25-11-2026: el peor error
relativo pasó de 0,83 % a 0,25 % y el offset de fondo de escala de +28 a
+16 mV. No es mérito del diseño: el modelo de TI da −1,262 V en vez de −1,250
clavados, o sea el ~1 % de desvío típico de la pieza, y ese desvío cae justo en
contra del sesgo positivo que tenía el divisor. Con otra unidad podría caer a
favor.

Ojo con las tablas de este tipo en versiones anteriores de este README: daban
un error de ganancia de −0,9 % que no era del diseño sino de `LM317HV.sub`, que
tenía la fuente del pin ADJ con el signo invertido y **restaba** `Iadj·R2` en
vez de sumarlo. Corregido el 25-11-2026; el modelo lleva la historia escrita.

El fondo de escala se va a 41,0 V contra los 40,5 V nominales, que es
precisamente para lo que está `TP1`: el `Iadj·R2` de la pieza real deja la
salida alta, y subir `R1` la baja.

### Regulación de carga

De vacío (1 kΩ) a la corriente máxima de cada ajuste. `Zo` es la impedancia de
salida:

| ajuste | vacío | con carga | I | caída | regulación | Zo |
|---|---|---|---|---|---|---|
| 0,5 V | 0,497 V | 0,494 V | 0,49 A | 2,4 mV | **0,48 %** | 4,9 mΩ |
| 5 V | 5,049 V | 5,045 V | 0,51 A | 3,4 mV | **0,07 %** | 6,9 mΩ |
| 20 V | 20,193 V | 20,182 V | 0,92 A | 11,1 mV | **0,05 %** | 12,4 mΩ |
| fondo | 41,018 V | 40,996 V | 0,87 A | 21,6 mV | **0,05 %** | 26,0 mΩ |

**Esta tabla es una cota pesimista, no una medida.** Empeoró al poner el LM337
real (antes: 0,09 / 0,03 / 0,04 / 0,05 %), y el empeoramiento se explica entero
por un término del modelo de TI, `V(OUT)/(V(OUT)−V(ADJ))`, que da por hecho que
`ADJ` anda cerca de masa. Aquí `ADJ` va al **borne**, así que sube con la caída
del shunt y ese cociente mete 7 mV de deriva en la referencia por los 0,44 V de
recorrido. Las cuentas cuadran en los cuatro ajustes, pero el término es
matemáticamente sospechoso —va a singularidad—, así que lo más probable es que
la pieza real sea mejor que esto. Está todo explicado en la cabecera de
[`LM337_N_TRANS.LIB`](LM337_N_TRANS.LIB), y se decide midiendo.

Para comparar, la única cifra publicada de las tres fuentes de referencia:
Silicon Chip declara **<0,5 %** en su fuente de 30 V / 2 A. Del P223 no hay dato
de regulación de carga. Esto sale de sensar en el borne; con el divisor a masa
serían 0,33 V de caída a 1 A, o sea un 1,7 % a 20 V.

### Regulación de línea

Red a ±10 %, TAP=2, 20 V, 22 Ω:

| red | VRAW | Vout | rizado |
|---|---|---|---|
| 207 V | 27,9 V | 20,176 V | 1,97 mV |
| 230 V | 31,4 V | 20,182 V | 2,00 mV |
| 253 V | 34,9 V | 20,188 V | 2,03 mV |

**11,9 mV** en total = 0,059 %, que sobre los 7 V que se mueve el raíl son
0,008 %/V. El datasheet promete 0,01 %/V típico (§7.5).

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
| carga 0,2 → 0,9 A (en CV) | −234 mV | **0,66 ms** |
| carga 0,9 → 0,2 A (en CV) | +237 mV | **0,72 ms** |
| carga que cruza a CC | −160 mV | 120 ms |
| vuelta de CC a CV | +1 mV | **18,9 ms** |
| consigna 20 V → 0,5 V | −511 mV | **3,1 ms** |
| consigna 0,5 V → 20 V | +1 mV | **25,1 ms** |

**Sin oscilación en ningún caso.** Los 3,8 ms del escalón de carga en CV son del
orden de los 2 ms que mide Silicon Chip quitando 4 A a 25 V, y con menos
desviación (225 mV contra ~500 mV), aunque ellos mueven 4 A y aquí son 0,7.

Los ~105 ms de la entrada en CC son el integrador de 16 Hz, puesto a propósito
lejos de los 100 Hz del rectificador. Silicon Chip reconoce la misma pega en su
fuente: su CC es lento y un escalón le hace pasar de 7 A con el límite en 5.

La asimetría bajada/subida es la misma que ellos describen y buscan: la salida
puede **caer** deprisa, que es lo que importa en una sobrecarga, y sube despacio
porque `Cadj` se carga a través de R1.

**De dónde sale esta velocidad, que no siempre fue así.** Subir R1 a 340 Ω para
poder usar potes de panel triplicó la constante `R1·Cadj` y el escalón de carga
se fue a 3,79 ms con una cola de ~100 ms. La solución no fue deshacerlo sino
**bajar `Cadj` de 10 µF a 1 µF** —medido en el barrido de más abajo—, que lo dejó
en **0,66 ms**, 5,7× más rápido, y de propina quitó el sobreimpulso de arranque.

**Lo que se paga es rizado**: 1,98 mV a 1 A contra los 0,54 mV de antes. Se queda
dentro de los 2 mV p-p de las comerciales, pero sin margen, y por eso la placa
lleva los pads del filtro CRC: si la unidad construida mide alto, se sueldan dos
componentes y se recupera. El razonamiento de por qué no van montados ya está en
[«¿Hace falta el filtro CRC?»](#hace-falta-el-filtro-crc).

**Lo que no mejora es la entrada en CC** (120 ms), y es correcto: esa la fija el
integrador `Rint·Cint` a 16 Hz, no `Cadj`. Son dos constantes de tiempo distintas
y aquí se ve cuál manda en cada cosa. **Las curvas de [`curvas/`](curvas/)
enseñan la forma completa**, que es lo que un número de establecimiento esconde.

Rizado en régimen, sin escalón:

| caso | rizado salida | rizado raíl | rechazo |
|---|---|---|---|
| vacío | 0,12 mV | 33 mV | 48,9 dB |
| 1 A | **1,98 mV** | 632 mV | 50,1 dB |
| 0 V | 0,02 mV | 16 mV | 56,5 dB |
| en CC | 1,77 mV | 866 mV | 53,8 dB |

Ese 1,98 mV a 1 A es el precio de bajar `Cadj`, y está **dentro** de los 2 mV p-p
que especifican las comerciales. Si en la unidad construida sale alto, los pads
del filtro CRC están en la placa: ver [«¿Hace falta el filtro
CRC?»](#hace-falta-el-filtro-crc).

### Arranque

El P223 acabó poniendo un relé de salida con 2,5 s de retardo por un
sobreimpulso de ~4 V al encender. Aquí, medido:

| ajuste | Vout | pico | sobreimpulso |
|---|---|---|---|
| 20 V | 20,203 V | 20,203 V | **0 mV** |
| fondo | 41,020 V | 41,021 V | **1 mV** |
| 0,5 V | 0,509 V | 0,509 V | **0 mV** |
| 0 V | 0,004 V | 0,004 V | **0 mV** |

**Ya no hay sobreimpulso en ningún ajuste.** Con `Cadj` de 10 µF el ajuste a
0,5 V daba 724 mV (un 142 % sobre medio voltio) porque el condensador arrancaba
descargado y ADJ se pasaba mientras se cargaba. Con 1 µF sigue a la consigna y el
sobreimpulso desaparece: fue un regalo del cambio que no estaba previsto. Sale de que `Cadj` arranca descargado y ADJ se pasa
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

### Ningún pote lleva corriente de carga, y el de tensión lleva poca

Es el fallo clásico del LM317 como regulador de corriente —el pote en serie con
la carga, que se quema— y ese no lo tiene ninguno de los dos. El de tensión
**es** el divisor de realimentación, así que sí lleva su corriente, pero con el
sumidero puesto esa corriente ya puede ser pequeña. Medido:

| escenario | R2c grueso | R2f fino | pote de corriente | shunt |
|---|---|---|---|---|
| fondo en vacío | 139 mW | 14 mW | 0,0 mW | 1 mW |
| 20 V a 1 A | 65 mW | 7 mW | 0,0 mW | 353 mW |
| corto, límite máx | 0 mW | 0 mW | 0,0 mW | 590 mW |

El de corriente solo divide los 2,5 V del TL431: microamperios, y da igual lo
que esté haciendo la fuente. Ese se compra en cualquier sitio, y un **taper
logarítmico** es mejor que uno lineal porque expande el extremo bajo, que es
donde cuesta ajustar.

Para el de tensión, la cuenta que importa es ésta:

    P(pote) = Vmax² / R2        (no depende de R1 ni de la carga)

41,0² / 11.000 = **153 mW**, repartidos 91/9 entre grueso y fino. Con el 3k9
original eran 420 mW, y de ahí salía la necesidad de un multivuelta de
instrumentación de 2 W.

**Lo que impedía subir el pote no era la potencia, era la carga mínima.** R1
hacía dos trabajos a la vez: fijar la corriente del divisor (y por tanto la
potencia del pote) y dar la carga mínima del regulador. Dos requisitos
incompatibles en un solo componente:

| divisor | I divisor | Vout máx | P en el pote | carga mínima |
|---|---|---|---|---|
| 100 Ω + 3k3 | 12,5 mA | 41,1 V | 513 mW | sobra |
| 120 Ω + 3k9 (el diseño anterior) | 10,4 mA | 40,5 V | 420 mW | justa |
| 240 Ω + 7k5 (el valor de las figuras de TI) | 5,2 mA | 38,7 V | 200 mW | **insuficiente** |
| **340 Ω + 11k** (este diseño, con `Q_min`) | **3,6 mA** | **40,5 V** | **145 mW** | la da `Q_min` |

La regulación de carga, la de línea y el lazo de CC salen **idénticos** en los
cuatro casos. Lo único que cambiaba era la corriente mínima, y el datasheet
pide hasta **12 mA a 60 V de diferencial**, que es la condición de la toma alta
a 0 V. `Rbleed` no ayuda: está en el raíl bruto, para descargar los 10.000 µF
al apagar.

**`Q_min` desempareja las dos funciones.** Con él, R1 solo fija la escala y el
pote puede ser de valor alto. Medido: 3,6 mA del divisor + 8,6 mA del sumidero
= **12,3 mA en todo el recorrido**, por encima del caso peor del datasheet, y
sin depender de dónde esté el mando. Por qué un sumidero y no un bleeder: una
resistencia daría `Vout/R`, o sea menos corriente cuanto más baja es la salida,
que es justo al revés de lo que hace falta.

Lo que se paga por subir R1:

- **el error de ganancia del Iadj pasa de 0,5 % a 1,4 %**, porque vale
  `Iadj·R1/1,25` y R1 ha subido de 120 a 340 Ω. Es un error de ganancia
  constante en todo el recorrido, así que TP1 lo corrige entero; lo que queda
  es su deriva, unos 55 mV sobre 40 V en el peor caso;
- **un componente caliente más**: 395 mW en el TO-126 del sumidero. Ya no es
  verdad que el LM317HV sea el único que necesita algo de disipación, aunque
  un TO-126 al aire con 395 mW va sobrado;
- **un modo de fallo nuevo**: si `Q_min` se va en corto colector-emisor, la
  corriente la acota `Re_min`. Con los 1k3 al bruto de −17 V son 44 mA y 2,5 W
  en la resistencia; con la versión ingenua (75 Ω contra el raíl de −5 V)
  habrían sido 607 mA y 27 W. De ahí que `Re_min` sea de 3 W y convenga que
  sea fusible.

**Lo que `Q_min` NO arregla: el máximo absoluto del diferencial.** La regla de
no bajar del 20 % del pote en TAP=3 sigue en pie, porque no viene de la carga
mínima sino de los 59,1 V contra los 60 V del máximo absoluto del chip.

Al cablearlo, **cursor unido al extremo que no se usa**, que es la práctica
estándar al usar un pote como reóstato: así un cursor sucio deja la pista en
circuito en vez de dejar R2 al aire. Importa, porque R2 abierto manda la salida
al tope del raíl.

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
| `Q_min` BD139 | 0,40 W | T3 vacío | TO-126, al aire |
| R2c pote grueso 10k | 0,14 W | T3 vacío | 0,25 W vale |
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
| `Q_min` (sumidero) | BD139 | **404 mW** | T3 en vacío | **TO-126**, ver abajo |
| `R2c` (pote grueso) | 10k | **139 mW** | T3 en vacío | pote de panel de **0,25 W** |
| `Re_min` | 1k3 | 98 mW | T3 en vacío | **3 W**, por el fallo en corto |
| `R2f` (pote fino) | 1k | 13 mW | T3 en vacío | cualquiera |
| `Rbleed` | 10k | **349 mW** | T3 en vacío | **1 W** |
| `Rref` | 2k2 | 41 mW | T1 en vacío | 0,25 W |
| `R1` + `TP1` | 270 + 150 Ω | 5 mW | T2 en corto | 0,25 W |
| `Rnbleed` | 220 Ω | 7 mW | T1 en vacío | 0,25 W |
| `Rsnub` | 100 Ω | 0,2 mW | — | 0,5 W (por el pico de conmutación, no por la media) |
| `Rset`, `Rpot_i`, `Rint`, `Rb`, `Rbe`, `Rfilt` | — | <1 mW | — | 0,25 W de las normales |

Solo tres resistencias se salen de 1/4 W, y las tres por motivos distintos: el
shunt por el corto, y el pote de tensión y el bleeder porque **trabajan en
vacío con el raíl alto**, que es la condición que uno no mira.

El pote de tensión es el único de los tres que no se resuelve comprando una
resistencia más gorda; tiene sección propia más abajo.

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

- **`Qcc` no disipa lo que parece.** Su corriente no son los 3,6 mA del
  divisor, sino la *diferencia* entre esos 3,6 mA y lo que sigue pasando por
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
| **79L05** | −5 V | 6 mA (LM358 + el emisor de `Qcc` + 45 µA de la base de `Q_min`) | **87 mW** | no |
| **LM337** | −1,25 V | 9 mA (divisor 3,6 + sangrador 5,7) | **164 mW** | no, en TO-92 ya entra |

El LM337 en TO-92 (LM337L) se queda ahora en 164 mW de unos 600 mW nominales
—antes eran 292 mW, con el divisor pidiendo 10,4 mA— así que entra sin
discusión. Aun así, en TO-220 cuesta lo mismo y es la pieza de la que depende
el cero de tu escala de tensión, que además deriva con la temperatura. Que esté
fría es gratis.

**Resumen: el único componente que necesita disipador es el LM317HV.** El
sumidero `Q_min` disipa 404 mW y pide un **TO-126**, pero al aire: no es
disipador, es encapsulado. Todo lo demás, al aire sin más.

**El `.asc` lo genera un script.** `tools/ltspice/mkasc_psu_cvcc.py` tiene los
valores del divisor y del sumidero en un bloque de constantes al principio
(`R2_COARSE`, `R2_FINE`, `R1_FIX`, `R1_TRIM`, `RE_MIN`): cambiar de potes es
tocar dos números y volver a generarlo. `verify_psu_cvcc.py` lleva las mismas
constantes y hay que mantenerlas en paralelo.

## Instrumentación

El esquemático lleva **68 directivas `.meas`** que salen en el `.log` (Ctrl+L
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

## Curvas

Los números de arriba dicen *cuánto*; las curvas dicen *qué forma tiene*, que es
lo que esconde un tiempo de establecimiento. Se generan con:

```bash
python3 tools/ltspice/curvas_psu_cvcc.py --png
```

Salen en [`curvas/`](curvas/) (ignorado por git: material derivado del `.asc`).
Nueve escenarios, cada uno con la **tensión en el borne arriba y la corriente en
la carga abajo**, nunca en el mismo eje:

| figura | qué enseña |
|---|---|
| `01_escalon_carga_cv` | escalón 100 → 22 → 100 Ω dentro de CV |
| `02_escalon_a_cc` | escalón que cruza a CC y vuelve |
| `03_corto_caliente` | cortocircuito con la fuente dando tensión, y recuperación |
| `04_mando_tension_brusco` | consigna 20 V → 0,5 V → 20 V de golpe |
| `05_mando_fino` | solo el mando fino, de un extremo al otro |
| `06_mando_corriente_brusco` | límite 1,34 A → 0,3 A → 1,34 A estando en CC |
| `07_arranque` | arranque desde cero con tres consignas |
| `08_extremos_mandos` | los dos potes al mínimo y al máximo, en vacío y con carga |
| `09_escala_de_los_mandos` | el grueso contra el fino: tres curvas separadas 3,7 V |

La tensión que se pinta es `V(VOUT) − V(VRTN)`, la del borne, no contra masa: la
caída del shunt está dentro del lazo y lo que ve la carga es la diferencia.

## ¿Hace falta el filtro CRC?

Partir el depósito con una resistencia (`10.000 µF — Rcrc — Cbulk2`) compra
atenuación del rizado **en el raíl**, donde es barata, en vez de en el lazo,
donde cuesta velocidad. Es lo que hace el P223 con sus 2 × 2200 µF y 1 Ω. Aquí
los pads están reservados y **el filtro no va montado**. Las dos razones:

1. **El rizado sin él ya está dentro de spec comercial.** 1,98 mV p-p contra los
   2 mV p-p que especifican Rigol, Korad y el HP E3610A.
2. **Y sobre todo: la mejora cabe dentro del error de la medida.** Ese 1,98 mV es
   un número del *modelo*, que topa en ~50 dB de rechazo donde el chip real hace
   80 dB (§8.4.2). La incertidumbre son casi 20 dB y el filtro compra 11–17 dB.
   **El dato que decide la compra no está en la simulación, está en el
   polímetro de la unidad construida.**

Medido con `barrido_crc.py`, por si al medir el rizado real hace falta montarlo.
La atenuación depende **solo del producto `R·C`** —verificado con cinco
combinaciones distintas de R y C que dan el mismo resultado a igual producto—:

| R | C2 | atenúa | rizado | caída a 1,34 A | P(R) |
|---|---|---|---|---|---|
| 1 Ω | 10.000 µF | 17,2 dB | 0,26 mV | 1,34 V | 1,8 W |
| 1 Ω | 4.700 µF | 11,1 dB | 0,48 mV | 1,34 V | 1,8 W |
| 2,2 Ω | 4.700 µF | 17,5 dB | 0,25 mV | 2,95 V | **4,0 W** |
| 0,47 Ω | 22.000 µF | 17,5 dB | 0,23 mV | 0,63 V | 0,85 W |

Tres cosas que el barrido deja claras:

- **La resistencia paga en voltios linealmente y en vatios al cuadrado.** Subirla
  para ahorrar capacidad es el peor de los dos ejes: a 2,2 Ω son 4 W, más que lo
  que disipa el regulador en un punto de trabajo normal, o sea que la resistencia
  pasaría a ser el componente más caliente de la caja. **1 Ω es el techo** de lo
  que permite el presupuesto de dropout.
- **No empeora los picos del puente** (4,07 → 4,09 A): el segundo depósito queda
  aislado del rectificador por la propia resistencia.
- **Cuesta techo útil.** Con 1 Ω, el margen en el techo de banda a plena
  corriente cae a 2,03 V, por debajo del dropout del chip, así que montarlo
  obliga a bajar ~1 V el techo declarado de cada toma. A carga ligera no se nota.

Y un efecto colateral a favor, si algún día se monta: **suaviza el acantilado del
dropout 8×**. Pasado el techo de una toma, el rizado de salida baja de 125–248 mV
a 16–32 mV.

## Contra las fuentes comerciales

La pregunta honesta es si esto compite con una fuente de banco de catálogo. La
respuesta es que en régimen sí y en transitorio no, y por mucho.

| | **psu_cvcc** (simulado) | HP/Agilent E3610A | Rigol DP832 | Korad KA3005P |
|---|---|---|---|---|
| Rango | 0–40,5 V / 1,34 A | 0–8 V/3 A ó 0–35 V/0,85 A | 0–30 V / 3 A ×2 | 0–30 V / 5 A |
| Regulación de carga | **0,05 %** (11,1 mV a 20 V, cota pesimista) | <0,01 % + 2 mV | <0,01 % + 2 mV | ≤0,01 % + 2 mV |
| Regulación de línea | **0,059 %** a ±10 % de red | 0,01 % | <0,01 % + 2 mV | — |
| Rizado de salida | **2,00 mV p-p** (solo 100 Hz, simulado) | <200 µV rms, <2 mV p-p | <350 µV rms, <2 mV p-p | ≤1–2 mV rms |
| **Recuperación ante escalón** | **0,66 ms** | **<50 µs a ±10 mV** | **<50 µs a ±15 mV** | sin dato |
| Exactitud de corriente | 0,10 % peor, 0,00–0,05 % típico | — | <0,01 % + 250 µA | ≤0,1 % + 5 mA |
| CC de 10 Ω al corto | **0,00 mA de desviación** | — | — | — |
| Bajada sin carga | **3,1 ms** | **2,5 s** (down-programming) | — | ~100 ms |
| Sobreimpulso al arrancar | **0 mV** en todos los ajustes | — | — | — |
| OVP | **no hay** | sí | sí | sí |

### Dónde gana

1. **El rizado de 100 Hz, justo en el límite.** 1,98 mV p-p contra los 2 mV p-p
   que especifican todas, o sea que empatamos y sin margen. Pero el número de ellas es **20 Hz – 20 MHz
   medido en un instrumento real** y el nuestro es **100 Hz en una simulación**:
   no dice nada del ruido de alta frecuencia ni de lo que capte el cableado. Y
   los 61 dB de rechazo son una propiedad del modelo conductual, no del chip (el
   real hace 80 dB). **Esto solo se cierra midiendo la unidad construida.**
2. **El CC como fuente de corriente**: 0,00 mA de desviación de 10 Ω al corto
   franco, tres décadas de carga. Mérito de la referencia negativa.
3. **La bajada de tensión.** El E3610A tarda **2,5 s** en bajar de 100 % a 0,1 %
   sin carga; esto, 10 ms. La asimetría está invertida respecto a ellas: somos
   rápidos bajando y lentos subiendo, y bajar deprisa es lo que protege la carga.
4. **El rango**: 0–40,5 V de un tirón, contra los dos rangos excluyentes del
   E3610A o los 30 V del DP832.

### Dónde pierde, y por cuánto

1. **Recuperación ante escalón: 13 veces peor.** 0,66 ms contra los 50 µs de
   ellas. Sigue siendo el eje más flojo, pero ya no son tres órdenes de
   magnitud: eran 3,8 ms + 100 ms de cola antes de bajar `Cadj`.
2. **Regulación de carga y de línea: 2–6 veces peor**, pero en el mismo orden.
   Para taller es irrelevante.
3. **Extremo bajo de la escala de corriente**: el offset del LM358 (2–7 mV) son
   6–21 mA de error a 80 mA de consigna. Se arregla con un OP07.
4. **No hay OVP**, y todas lo llevan.
5. **Resolución y repetibilidad**: ellas ponen 1 mV y lo recuerdan; aquí hay
   13 mV por grado de muñeca y un voltímetro.

### Lo que habría que replantear

**1. `Cadj`: HECHO, de 10 µF a 1 µF.** Era el cambio con mejor relación
beneficio/coste de todo el diseño y era, además, la única decisión tomada a ciegas
—un valor copiado de una figura del datasheet sin comprobar lo que costaba—. El
razonamiento era:

- esos 10 µF estaban ahí **solo** por el rechazo de rizado de la fig. 21;
- el rizado medido ya es **4 veces mejor** que el que especifican las
  comerciales, así que sobra margen;
- cuestan **100× en velocidad de subida**, que es justo el eje donde peor
  quedamos;
- **Silicon Chip, con el mismo chip y la misma topología, pone 100 nF** y publica
  «menos de 1 ms y nunca más de 200 mV del setpoint» con un escalón de 4 A.
  Aquí son 3,8 ms y 225 mV con 0,7 A.

**Medido** con `python3 tools/ltspice/barrido_cadj.py`. Establecimiento a
**±10 mV** del valor final, el mismo criterio que el E3610A de Keysight:

| `Cadj` | rizado a 1 A | rechazo | caída del escalón | establece | subida 0,5→20 V |
|---|---|---|---|---|---|
| 10 µF (el valor anterior) | 0,54 mV | 61,4 dB | −255 mV | 173,6 ms | 412 ms |
| 3,3 µF | 0,81 mV | 57,8 dB | −232 mV | 54,3 ms | 135 ms |
| **1 µF (este diseño)** | **1,97 mV** | **50,1 dB** | **−232 mV** | **15,6 ms** | **40 ms** |
| 470 nF | 3,59 mV | 44,8 dB | −232 mV | 7,2 ms | 19 ms |
| 100 nF | 6,72 mV | 39,4 dB | −232 mV | 1,6 ms | 4 ms |

Tres cosas que decide esta tabla:

1. **El compromiso no es simétrico, y por eso bajar `Cadj` es buen negocio.** La
   velocidad va **lineal** con `Cadj` (100× menos capacidad → 108× más rápido) y
   el rizado va con su **raíz cuadrada** (100× menos capacidad → solo 12,5× más
   rizado). Cada factor que le quitas te devuelve el factor entero en velocidad
   y solo su raíz en rizado.
2. **Los 10 µF no compran nada en la magnitud del transitorio**: la caída es
   −232 mV con cualquier valor (−255 mV con 10 µF, o sea que incluso la empeoran
   un poco). Solo deciden **cuánto dura la cola**. La caída la fijan la
   impedancia de salida y el lazo interno del chip, no este condensador.
3. **100 nF da 1,6 ms**, y Silicon Chip publica «menos de 1 ms» con ese mismo
   valor. El modelo y su medida concuerdan, lo cual da confianza en la columna.

**Pero ojo con la columna del rizado: es optimista arriba.** El rechazo del
modelo conductual topa en ~61 dB mientras que el chip real hace 80 dB con 10 µF
(§8.4.2). O sea que la fila de 10 µF está infravalorada y la penalización real
por bajar la capacidad es **mayor** que la que mide este barrido. La conclusión
cualitativa aguanta —la velocidad sigue siendo lineal— pero el valor hay que
elegirlo con margen, no al borde.

Con eso, **470 nF queda descartado** (3,59 mV ya se sale de los 2 mV p-p que
especifican las comerciales) y la elección quedó entre 3,3 µF y 1 µF.

**Decidido: 1 µF.** Multiplica la velocidad por 11 y deja el rizado en 1,97 mV,
dentro de lo que especifican las comerciales. Pesa a favor que esa cifra es la
del modelo, que topa en 61 dB cuando el chip real hace 80 dB: el rizado real será
menor en todas las filas de la tabla. Y de propina, a 1 µF el condensador puede
ser de **film** en vez de electrolítico.

Por qué no se arregla por el otro lado, subiendo el depósito: el rechazo va en dB
y la capacidad compra rizado lineal, así que compensar los 11,3 dB que se pierden
al bajar a 1 µF pediría **36.700 µF**, casi cuatro latas. Y el depósito ya es la
pieza más estresada del diseño —5,33 A de pico por diodo y 2,38 A RMS en el
secundario por 1 A de continua—: un condensador más grande no baja el rizado por
arte de magia, lo baja cargándose en un pulso **más corto y más alto**, así que
esos picos y las pérdidas en el cobre (4,67 W) empeorarían, y la corriente de
arranque pediría NTC o relé. Lo eficiente es comprar el rechazo con un **filtro
CRC** como el del P223, y por eso están sus pads en la placa aunque no vaya
montado: ver [«¿Hace falta el filtro CRC?»](#hace-falta-el-filtro-crc) más
abajo.

Y un aviso para no venderlo de más: **ni siquiera con 100 nF se llega a las
comerciales**. Pasaríamos de ~3500× a ~30× de distancia de los 50 µs. Lo que
queda es estructural: divisor pasivo más el lazo interno del propio chip.

**2. El integrador de CC a 16 Hz.** Es deliberado —lejos de los 100 Hz del
rectificador— y por eso el límite tarda ~100 ms. Silicon Chip tiene la misma pega
(su CC se pasa a 7 A con el límite en 5) pero se recupera en unos pocos
milisegundos porque su lazo tiene muchísima más ganancia. Antes de tocar la
frecuencia hay que **medir la ganancia de lazo con una sonda de Tian**: subir el
ancho de banda a ciegas en un lazo sin medir es como se llega a una oscilación.

**3. El OVP: menos urgente de lo que parece.** Es cierto que es el único modo de
fallo sin cubrir, pero eso es una afirmación sobre *cobertura*, no sobre riesgo, y
conviene no confundirlas:

- la probabilidad es baja: el chip se protege solo contra las tres cosas que lo
  matan en corto —sobrecorriente, SOA y temperatura—, y el cuarto estrés, el
  diferencial, lo acota la regla de TAP=3, no un OVP;
- **la consecuencia ya la acota el selector de tomas.** Si el regulador falla en
  corto, la carga ve el raíl de la toma que tengas puesta: 16,5 V en TAP=1,
  33 V en TAP=2, 50 V en TAP=3. Como la toma se elige por disipación, probando
  un circuito de 5 V estarás en TAP=1 y el fallo pone 16,5 V, no 50. El caso
  feo —salida baja con toma alta— es justo el que ya está prohibido por otras
  razones. Una comercial lleva OVP en parte **porque es de un solo rango**: allí
  un fallo siempre vale fondo de escala;
- y un crowbar **añade su propio modo de fallo**: un SCR que dispara por ruido o
  por dV/dt deja un corto franco permanente hasta que abre el fusible, que aquí
  está en el **primario**. Esa interacción hay que diseñarla, no solo añadir tres
  piezas.

O sea: es lo que pondría si fuera a dejar la fuente conectada sin vigilancia a
algo caro, no la casilla que falta para competir.

**4. Lo que NO hay que replantear**: las tomas a mano, el sensado en baja, el
control de tensión pasivo y el rango de 1,34 A. Son las decisiones que hacen esto
construible y caracterizable, y ninguna aparece en la lista de problemas.

Fuentes de las cifras comerciales: [datasheet de la serie HP
E3600](https://cse.sc.edu/~adowney2/resources/data_sheets/HP_E3600_series_datasheet.pdf),
[manual del Agilent
E3611A](https://www.ecb.torontomu.ca/guides/instrument-manuals/Agilent-HP_E3611A_User.pdf),
[hoja de la serie Rigol
DP800](https://cdn.shopify.com/s/files/1/0268/7746/0673/files/DP800_Series.pdf) y
[datasheet de la serie Korad
KA3000](https://www.welectron.com/mediafiles/datasheets/korad/Korad_KA3000_Series_Datasheet-Web.pdf).

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
banda limita el rechazo de rizado medido; el real son 80 dB con 10 µF en ADJ
(§8.4.2) contra los 61 dB que da el modelo. Esto importa al elegir `Cadj`: la
columna de rechazo del barrido es **pesimista**, así que el rizado real de este
diseño es mejor que el 1,97 mV que figura en la tabla.

**`LM358.sub`** también es conductual. Se usa en vez del OP747 de `ADI.lib`
porque la pieza que pide el diseño es un LM358 (alimentación simple, modo
común de entrada que incluye masa) y porque el macromodelo del OP747 no
converge en este circuito. No modela el offset de entrada: con los 2–7 mV
típicos del LM358 real, a 80 mA de consigna (26 mV en el shunt) cuenta con un
error del 8–25 %. Si quieres precisión en el extremo bajo, pon un OP07.
