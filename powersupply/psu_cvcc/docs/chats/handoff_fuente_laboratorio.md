# Fuente de alimentación de laboratorio DIY — handoff completo para Claude Code

Sesión de investigación con Claude (Cowork), 23–24 de noviembre de 2026.

Este fichero contiene:

1. **Parte 1 — Resumen estructurado** (decisiones, datos clave y siguientes pasos).
2. **Parte 2 — Transcripción completa** de todos los mensajes del chat: cada pregunta del usuario y cada respuesta
   de Claude, literales y con todos sus enlaces. Lo único que cambia es el formato: los encabezados internos de
   las respuestas se han bajado de nivel para que no choquen con la estructura de este fichero.
3. **Parte 3 — Índice de todos los enlaces**: los citados en las respuestas y el resto de páginas consultadas
   durante la investigación.

No se incluyen los resultados internos de las herramientas (búsquedas y lecturas de páginas), solo los mensajes
que se intercambiaron; las páginas leídas aparecen en la Parte 3.

---

# Parte 1 — Resumen estructurado

## 1. Estado actual y decisiones

- **Tipo:** lineal pura (sin conmutada). Descartadas por ahora la híbrida y la conmutada.
- **Rango V/I objetivo:** todavía SIN definir (pendiente).
- **Camino elegido por ahora:** opción 1 = basada en LM317 / LM317HV, adaptando el diseño a lo que puede
  disipar el regulador. Base candidata: **ESP Project 223 de Rod Elliott**.
- **Límite de corriente:** se quiere ajustar con **potenciómetro**. Propuesta: sustituir el limitador por
  transistor del P223 por **INA282 + operacional + MOSFET pequeño (2N7000) tirando de ADJ**, como la fuente
  30 V / 2 A de Silicon Chip.
- Se estudió también la opción 3 (operacionales + transistor de paso discreto); queda como alternativa si se
  necesitan ≥1,5 A en todo el rango.

## 2. Topologías consideradas

| # | Topología | Pros | Contras |
|---|---|---|---|
| 1 | Regulador integrado (LM317/LM338, LT3080/LT3081) | Pocas piezas, protección térmica/SOA interna | ~1,5 A por chip, ~10 W reales por TO-220, límite de corriente impreciso |
| 2 | LM723 + 2N3055 | Clásica, documentada | Límite de corriente poco preciso |
| 3 | Operacionales (lazos CV y CC unidos por diodos) + transistor de paso | Escalable, CC preciso, la más recomendada en foros | Estabilidad del lazo, hay que diseñar protecciones |
| 4 | Topología HP/Harrison flotante (E3610A, E3620A) | Probada comercialmente | Más compleja; necesita alimentación auxiliar aislada |

Opinión de Tim (T3sl4co1l, EEVblog): no dudaría en usar lineal; no se pueden poner LM317 en paralelo
directamente; prefiere transistores bipolares con realimentación desde la salida; seguidor de emisor "difícil de batir".

## 3. Opción 1: LM317 / LM317HV adaptado a su disipación

### Datos de datasheet
- LM317 (onsemi): RθJC = 5 °C/W en TO-220; diferencia entrada-salida máx. 40 V. La lengüeta va a la SALIDA (aislar).
- TI: Tj recomendada 0–125 °C. Límite de corriente: ≥1,5 A solo con Vin−Vout ≤ 15 V; a 40 V: 0,15 A mín / 0,4 A típ.
- LM317HV: hasta 60 V de diferencia; límite ~0,3 A típ a 60 V; corriente mínima de carga hasta 12 mA (a 60 V).
- Caída mínima (dropout) LM317 ~2,25 V típ.

### Presupuesto térmico (estimación propia)
(125 °C − 60 °C disipador) / (5 + 1 °C/W aislante) ≈ **10–11 W por LM317** de forma sostenida (≈8 W con margen).
Rod Elliott usa como máximo del encapsulado ~20 W.

### Corriente máxima según tomas del transformador (estimación, 10 W, 5 V de margen, tomas equiespaciadas)

| Rango | Sin tomas | 2 tomas | 3 tomas | 4 tomas | 6 tomas |
|---|---|---|---|---|---|
| 0–30 V (LM317) | 0,29 A | 0,44 A | 0,60 A | 0,73 A | 0,92 A |
| 0–50 V (LM317HV) | 0,18 A | 0,31 A | 0,43 A | 0,53 A | 0,71 A |

### Ideas para adaptarse
1. Aceptar el límite (P223: canales de 0–25 V, rangos de corriente).
2. Conmutar tomas: manual (como el botón RANGE del HP E3610A) o relés con comparador e histéresis.
   Ojo: la corriente de carga de los condensadores suelda relés → conmutar cuando V trafo < V condensador.
   Truco: dos secundarios iguales en serie/paralelo con un relé = 2 tomas (xavier60).
3. Repartir el calor (el total no cambia): resistencia en serie antes del LM317; pre-regulador lineal de
   seguimiento (2.º LM317 o Darlington+zener); varios reguladores en paralelo con resistencias de reparto
   (mejor LT3080/LT3081, diseñados para ello).
4. Limitar la corriente según disipación: rangos, microcontrolador que mida Vin/Vout/I, termostato + corte térmico.

### ESP Project 223 (Rod Elliott)
- 2 canales 0–25 V / 1,5 A, LM317T como elemento de paso; serie = 0–50 V, paralelo = 0–25 V / 3 A.
- LM337 da −1,25 V de referencia para llegar a 0 V; Q1 sumidero ~6 mA (R4) para regular sin carga.
- Potenciómetro doble 10k + trimmer TP1 1k para fijar 25 V a fondo.
- Entrada sin regular ~35 V (inferido). Filtro: 2 × 2200 µF con 1 Ω/5 W entre ellos (mínimo recomendado).
- Limitador de corriente ANTES del regulador (línea de entrada): transistor sensor Q2 (~540 mV) → Q3 tira de ADJ a −1,25 V.
  Rangos 33 mA / 330 mA / máx. C10 = 10 nF añadido porque oscilaba.
- Relé de salida retardado ~2,5 s (evita sobreimpulso de ~4 V al encender). Aux 12/24 V con BD139 desde uno de los +35 V.
- Ventilador con NTC y MOSFET. Rod: no es más barato que una comercial; 5 V a 1 A ≈ 30 W en el regulador.

### Adaptar el P223 a LM317HV
- **Mismos 0–25 V (más margen):** cambio directo (mismo patillaje y Vref). Subir sumidero Q1 a 10–12 mA (R4).
- **0–50 V por canal:** entrada ≤ ~55 V incl. red alta y vacío; solo ~0,2–0,3 A a baja tensión sin tomas;
  cambiar a más tensión: condensadores (63–80 V), Q1, Q2/Q3 del limitador, red de ajuste/TP1, aux del BD139
  (mejor devanado aparte), resistencias de 220 Ω de la referencia negativa, medidores. >60 V DC ya no es seguro al tacto.
- **Si se quieren 50 V:** usar el modo serie del P223 (0–50 V / 1,5 A con LM317 normales). Cambiar de modo con la
  tensión al mínimo; desajuste entre canales hasta ~0,5 V.

### Límite de corriente con potenciómetro
- NO: potenciómetro en serie con la carga (lleva toda la corriente).
- En el P223 tal cual: potenciómetro como divisor sobre la resistencia de medida → rango corto
  (caída máx. / 0,54 V, p. ej. ~3,7:1 con 2 V) y deriva ~−2 mV/°C. Combinable con rangos.
- Recomendado: shunt pequeño + INA282 (ganancia 50, modo común −14…+80 V) + operacional comparando con la tensión
  del potenciómetro + 2N7000 a ADJ, con compensación (Silicon Chip 30 V/2A usa 100 nF y 1 µF). Es lento (ms).
  Cada canal necesita su propia alimentación auxiliar (los canales flotan).
- Potenciómetro multivuelta o grueso+fino; resistencia del cursor a masa para que un fallo dé el mínimo;
  botón "CC SET" para ver el límite sin cortocircuitar.

## 4. Opción 3 (alternativa): notas clave
- Diseños: xavier60/JuanGg (EEVblog, GitHub con esquemas/PCB/firmware); xavier60 versión LM324 hasta 5 A;
  Greg Jolley (35 V/4 A, análisis completo en LTspice y medidas); Blackdog (±3 mV con escalón 0,5→2 A).
- Estabilidad: compensar con C de realimentación + R en serie; anti-windup (diodo); condensador de salida 47–100 µF
  (<1 µF difícil); resistencias de base pequeñas; operacionales lentos y fiables (LM358/LM324/TLC072; evitar TL081).
- Verificación: LTspice (ganancia de lazo con sonda Tian/Middlebrook, margen >40°) + escalón de carga con MOSFET
  (flancos ≥5× más rápidos que la fuente); probar CV, CC y transiciones, con cargas resistivas/capacitivas/inductivas.
- PCB: lazo de potencia corto; picos de carga de condensadores solo entre puente y condensadores; masa de control
  unida en un solo punto; Kelvin en el shunt; realimentación desde bornes; cables cortos a transistores de paso;
  desacoplos 100 nF + electrolítico; footprints de reserva para compensación; pull-down en salida del operacional CV.

## 5. Diseños construidos y medidos
- Silicon Chip 45 V / 8 A (2019): lineal; 3 mV de rizado a 25 V/4 A; CC lento (casi 7 A con límite 5 A unos ms).
- Silicon Chip 30 V / 2 A (2022): LM317 + PNP; <0,5 % regulación de carga; <8 mV RMS a 2 A.
- G. Jolley: escalón 10 Ω → 2 µs, 15 % sobreimpulso, sin oscilación; CC 0,74 A durante 6 µs con límite 0,5 A.
- xavier60/JuanGg y Blackdog: construidas, pocas medidas formales.

## 6. Siguientes pasos propuestos
1. Fijar especificaciones: rango de tensión, corriente máxima, nº de canales, control manual o por microcontrolador.
2. Elegir nº de tomas / transformador con la tabla de la sección 3.
3. Capturar el esquema del P223 modificado (LM317 o LM317HV + limitador INA282/op-amp/2N7000) en KiCad.
4. Simular en LTspice: arranque, escalones de carga, transición CV↔CC, estabilidad del lazo de corriente.
5. BOM con tensiones nominales revisadas y cálculo térmico del disipador.

---

# Parte 2 — Transcripción completa del chat

## Mensaje 1 — Usuario

Busca en internet, en foros de electrónica DIY (tipo eevblog) ideas para construir una fuente de alimentación DIY capaz de regular voltaje y corriente. Por ahora no quiero limitarme a voltajes o corrientes concretas, simplemente a ver qué se comenta. Usa chrome plugin para hacer las búsquedas más fácilmente, si fuera necesario.

## Respuesta 1 — Claude

He revisado sobre todo EEVblog y también element14, All About Circuits y algunos artículos técnicos que citan esos hilos. No me hizo falta Chrome porque las páginas se podían leer directamente.

#### Las arquitecturas que más se proponen

**1. Lineal pura** (LM723 + 2N3055, LM317, o amplificadores operacionales con transistor de paso)
- Es la clásica: da poco ruido y es fácil de entender.
- Su problema es el calor. A baja tensión y mucha corriente, el transistor de paso disipa decenas de vatios. En element14 calculaban unos 90 W por canal a 6 A.
- La solución habitual es la **conmutación de tomas del transformador** con relés según la tensión de salida.
- Advertencia que se repite: si el relé falla, los transistores pueden cruzarse y dejar pasar toda la tensión sin regular a la carga. Además hay que revisar el SOA (zona de operación segura) del transistor, no solo la disipación.

**2. Híbrida: pre-regulador conmutado con seguimiento + post-regulador lineal** (la más recomendada hoy)
- Un convertidor buck (o buck-boost) mantiene su salida 1–3 V por encima de la salida final, y la etapa lineal hace el CC/CV y limpia el rizado.
- Ejemplos citados:
  - El vídeo EEVblog #329 de Dave sobre el pre-regulador con seguimiento.
  - El proyecto EEZ H24005/BB3 (0–50 V / 3 A, MOSFET de canal N y lazos con amplificadores operacionales).
  - La placa de demostración de Analog Devices: LT8612 + 2×LT3081, 0–24 V / 3 A, sin disipador ni ventilador según el artículo.
  - El diseño de 40 V / 5 A de Silicon Chip.
- Pegas que se comentan: ruido y EMI del conmutado (hacen falta filtros LC con amortiguación y blindaje), estabilidad del lazo de seguimiento y calor en las bobinas.

**3. Pre-regulador con SCR/triac** (el estilo HP/Agilent E3620A/E3630)
- Está muy probado en equipos comerciales, pero para potencias pequeñas lo consideran excesivo, y mete ruido en la red.

**4. Módulos conmutados ya hechos** (Riden RD6006, DPS5005, XL4016, LTC3780)
- Son baratos y dan mucha potencia, pero tienen bastante ruido: en el hilo del RD6006 se citan 30–50 mV pico a pico.
- Un usuario combina un XL4016 con una etapa lineal detrás y dice conseguir menos de 1 mV RMS.

#### Temas de diseño CC/CV que salen una y otra vez

- **El condensador de salida es el enemigo del CC.** Las fuentes comerciales llevan 100–1000 µF. Al limitar corriente, la carga acumulada en ese condensador puede matar un LED o un circuito delicado. Kleinstein (uno de los foreros más expertos) defiende que con un lazo rápido basta con un condensador de salida mucho más pequeño; en simulación vio que funcionaba con unos 1 µF.
- **Bajar la tensión rápido:** se usa un "down-programmer", es decir, un sumidero de corriente fijo en la salida. La fuente de Blackdog consume unos 50 mA continuamente para que la salida baje deprisa cuando no hay carga.
- **Transición CC↔CV:** hay que evitar el "windup" del integrador, porque produce sobreimpulsos. Kleinstein propone un único integrador con selección de error por diodos, como hacen los SMU.
- **Llegar a 0 V de verdad:** hace falta un rail negativo para los operacionales o el regulador (unos −5 V en el diseño de Analog Devices).
- **Montaje:** masa en estrella, sensado remoto, cables cortos al transistor de paso para que no oscile, y protección térmica.
- **Arranque:** la alimentación auxiliar tiene que estar lista antes que la etapa de potencia. Si llega tarde, hay sobreimpulso en la salida, como le pasó al autor del EEZ.

#### Advertencias y opiniones generales

- **El kit chino "0–30 V 2 mA–3 A"** tiene fallos conocidos: los TL081 trabajan por encima de sus 36 V máximos, el transformador de 24 VAC no llega a 30 V / 3 A y hay resistencias subdimensionadas. Existe una versión corregida de Audioguru (con TLE2141, entre otros cambios).
- **Diseños que se recomiendan estudiar o clonar:**
  - La topología HP 62xx / E3620A.
  - La fuente de Blackdog. Un forero la llama el único diseño amateur que ha visto funcionar bien tal cual está dibujado.
- **¿Construir o comprar?** Muchos opinan que una fuente de segunda mano (HP, TTi, Agilent) sale más barata. Construirla tiene sentido sobre todo para aprender.

Lo que más se repite como buen punto de partida es la opción híbrida, con lazos CC/CV hechos con amplificadores operacionales y un condensador de salida pequeño. Si quieres, puedo pasarlo a un documento o profundizar en una de estas opciones.

**Fuentes:**
- [EEVblog – DIY programmable dual channel bench PSU 0-50V/3A](https://eevblog.com/forum/projects/diy-programmable-dual-channel-bench-psu-0-50v3a)
- [EEVblog – Switching Lab supply design](https://eevblog.com/forum/projects/switching-lab-supply-design/25)
- [EEVblog – DIY Scalable Bench Power Supply Design](https://eevblog.com/forum/projects/bench-power-supply-design/msg477284)
- [EEVblog – fast CC/CV power supply again](https://www.eevblog.com/forum/projects/fast-cccv-power-supply-again/?wap2)
- [EEVblog – How does Blackdog's PSU work](https://eevblog.com/forum/beginners/how-does-blackdog_s-psu-work)
- [EEVblog – What circuit is best (two linear bench PS)](https://www.eevblog.com/forum/projects/what-circuit-is-best-(two-linear-bench-ps-and-know-how)/msg1957315/)
- [EEVblog – LM324 Power Supply with variable voltage and current](https://www.eevblog.com/forum/beginners/lm324-power-supply-with-variable-voltage-and-current/msg4110283/)
- [EEVblog – Linear lab power supply (JuanGg)](https://eevblog.com/forum/projects/linear-lab-power-supply)
- [EEVblog – 0-30V, 0-3A PSU, versión de Audioguru](https://eevblog.com/forum/beginners/0-30v-0-3a-psu-audiogurus-version/msg2232978)
- [EEVblog – Hilo del Riden RD6006](https://eevblog.com/forum/testgear/ruideng-riden-rd6006-dc-power-supply/5)
- [EEVblog #329 – Tracking Pre-Regulator](https://www.eevblog.com/forum/blog/eevblog-329-tracking-pre-regulator-ltspice-simulation-part-2/msg135509/)
- [element14 – DIY Lab PSU: what to choose?](https://community.element14.com/technologies/test-and-measurement/f/forum/39482/diy-lab-psu-or-bench-power-supply-what-to-choose)
- [Analog Devices – High Performance Portable DC Bench Power Supply](https://www.analog.com/en/resources/technical-articles/high-performance-portable-dc-bench-power-supply.html)
- [Silicon Chip – 40V Switchmode/Linear Bench Supply](https://www.siliconchip.com.au/Issue/2014/May/40V+Switchmode-Linear+Bench+Power+Supply%2C+Pt.2)
- [All About Circuits – Smartkit 0-30V troubleshooting](https://forum.allaboutcircuits.com/threads/smartkit-1138-0-30v-3a-power-supply-troubleshooting.190142/)

## Mensaje 2 — Usuario

Quiero una lineal pura. Vamos a ver qué cosas se proponen

## Respuesta 2 — Claude

Para una fuente lineal pura, lo que más se recomienda es un único transistor de paso controlado por dos lazos con amplificadores operacionales (uno de tensión y otro de corriente). El gran problema que hay que resolver es el calor, y la solución habitual es conmutar tomas del transformador.

#### Topologías que se proponen (de más simple a más profesional)

**1. Con regulador integrado** (LM317/LM338, LT3080)
- Es lo más sencillo. Dave (EEVblog #221) empieza con un LM317 y acaba usando un LT3080, que sí llega a 0 V.
- Con un LM317, para llegar a 0 V hace falta un rail negativo de unos −1,25 V.
- Algunos montan dos reguladores en serie, uno para corriente y otro para tensión. Kleinstein, uno de los foreros más expertos de EEVblog, opina que eso no aporta nada y sí da problemas.

**2. LM723 + 2N3055**
- Es el diseño clásico, y quedan miles funcionando. Se aconseja como primer proyecto.
- Su limitación de corriente es aceptable para una fuente de banco, pero poco precisa.

**3. Amplificadores operacionales + transistor de paso discreto** (la opción más recomendada para un proyecto serio)
- Un lazo controla la tensión y otro la corriente. Los dos actúan sobre el mismo transistor a través de diodos, y manda el que pida menos salida.
- Diseños de referencia:
  - **xavier60** (hilo de JuanGg, un forero español): LM358/TLC072, referencia TL431, Darlington BD137 + TIP35C y resistencia de medida en el lado negativo. Ha sido muy depurado en el foro.
  - **Blackdog**: referencia LT1021 y transistores 2SA1943/2SC5200, con un sumidero de corriente de unos 50 mA en la salida. Un forero lo considera el único diseño amateur que funciona bien tal cual está dibujado.
  - **National LB-28**: 0–25 V / 10 A con LM308 + LM101A y siete LM395 en paralelo. Evita a propósito un condensador grande en la salida.
  - **El kit chino 0–30 V**, pero solo en la versión corregida de Audioguru.

**4. Topología "Harrison" / HP flotante** (HP 62xx, Agilent E3610A/E3620A)
- Toda la electrónica de control va referida al terminal positivo de salida y tiene su propia alimentación auxiliar aislada.
- Ventajas que se citan:
  - La resistencia de medida va en la línea positiva y no necesita amplificador diferencial.
  - Es fácil de estabilizar en todo el rango de tensión.
  - La transición entre limitación de corriente y tensión fija es limpia gracias a los diodos.
- Es el diseño que más se recomienda clonar.

#### Detalles de los lazos que salen en los hilos

- **Saturación del lazo que no manda (windup):** mientras la fuente limita corriente, el lazo de tensión se satura, y al salir de la limitación aparece un pico de tensión. xavier60 lo evita con un diodo (D8). David Hess propone usar OTA (LM13700) o controladores con dos amplificadores (AP4310, TL103W).
- **Sumidero de corriente en la salida:** hace que la tensión baje rápido cuando no hay carga. Lo usan Blackdog, el LB-28 y xavier60.
- **Condensador de salida pequeño:** un forero lo bajó de 470 a 47 µF reajustando el lazo. Según Kleinstein, 100 µF es factible y bajar de unos 1 µF es difícil.
- **Montaje:** masa en estrella y una sola unión entre el negativo de salida y la masa de control.
- **Llegar a 0 V:** basta un rail negativo pequeño para los operacionales (Rod Elliott propone unos −1,2 V).

#### El gran problema: la disipación

En el peor caso las cifras son grandes: Rod Elliott calcula 250 W con 50 V × 5 A, y el LB-28 llega a 300 W.

**Conmutación de tomas del transformador**
- Lo normal es usar relés gobernados por un comparador con histéresis, como hacen las Mastech HY-3020.
- El punto débil es el relé: la corriente de carga del condensador puede soldar los contactos. A un forero le pasó en diciembre de 2025.
- Soluciones que se proponen:
  - Conmutar solo cuando la tensión del transformador está por debajo de la del condensador.
  - Poner un relé de estado sólido en paralelo durante el cambio.
  - Usar un MOSFET con un diodo Schottky (diseño de Blackdog, que Kleinstein califica de simple y bueno).
  - Usar tiristores en el rectificador.
- Los transformadores con varias tomas son difíciles de encontrar. Se propone rebobinar un toroidal o usar varios transformadores.

**Transistor de paso**
- Se prefieren los bipolares: 2N3055, TIP35C, MJL3281A.
- Los MOSFET modernos fallan en uso lineal por un tipo de embalamiento térmico (efecto Spirito). Si se usan, que sean planares antiguos (IRFP240) o MOSFET específicos para uso lineal (IXYS), que son caros.
- El límite real es la zona de operación segura (SOA), no la potencia nominal.

**Resto del montaje**
- Disipador grande, ventilador con termostato y corte térmico.
- La corriente continua que se puede sacar es solo un 50–65 % de la nominal en alterna del transformador.
- Para el condensador del rectificador se citan unos 4.700–6.800 µF por amperio de salida.

**Consejo general:** partir de un diseño ya probado, construir por etapas (primero transformador y rectificador, luego un canal) y no pedir demasiado rango; Rod Elliott sugiere quedarse en unos ±25 V. Tanto Rod Elliott como Bob Pease insisten en que comprar sale más barato, y que construirla merece la pena para aprender.

Si me das un rango aproximado de tensión y corriente, puedo comparar 2–3 de estos diseños con más detalle.

**Fuentes:**
- [EEVblog – Linear lab power supply (JuanGg/xavier60)](https://eevblog.com/forum/projects/linear-lab-power-supply/msg2044945) y [página 350](https://eevblog.com/forum/projects/linear-lab-power-supply/350)
- [EEVblog – How does Blackdog's PSU work](https://eevblog.com/forum/beginners/how-does-blackdog_s-psu-work)
- [EEVblog – CC/CV Benchtop Power Supply Topology Question](https://eevblog.com/forum/projects/cccv-benchtop-power-supply-topology-question/msg5647051)
- [EEVblog – My Project: Modern Linear Power Supply (2025)](https://www.eevblog.com/forum/projects/my-project-modern-linear-power-supply/)
- [EEVblog – Preregulation of a linear bench PSU](https://www.eevblog.com/forum/projects/preregulation-of-a-linear-bench-psu/msg2072110/)
- [EEVblog – Transistor vs MOSFET for linear power supply](https://www.eevblog.com/forum/beginners/transistor-vs-mosfet-for-linear-power-supply/msg2018209)
- [EEVblog – LM324 Power Supply with variable voltage and current](https://www.eevblog.com/forum/beginners/lm324-power-supply-with-variable-voltage-and-current/msg4110283/)
- [EEVblog #221 – Lab Power Supply Design Part 1](https://www.eevblog.com/2011/11/28/eevblog-221-lab-power-supply-design-part-1/)
- [EEVblog – 0-30V, 0-3A PSU, versión de Audioguru](https://eevblog.com/forum/beginners/0-30v-0-3a-psu-audiogurus-version/msg2232978)
- [All About Circuits – HP E3610A Power Supply Design Logic](https://forum.allaboutcircuits.com/threads/hp-e3610a-power-supply-design-logic.186813/)
- [National LB-28 – General Purpose Power Supply](https://xdevs.com/doc/_Magazines/LB-28.pdf)
- [Rod Elliott (ESP) – Bench Power Supplies, Buy or Build?](https://sound-au.com/articles/bench-supply.htm)
- [element14 – Auto Tap Selection experiment](https://community.element14.com/members-area/personalblogs/b/john-wiltrout-s-blog/posts/experimenting-with-auto-tap-selection-for-a-future-power-supply-build)
- [Electronic Design – The Spirito Effect](https://www.electronicdesign.com/technologies/power/article/21795492/the-spirito-effect-improved-my-designand-i-didnt-even-know-it)

## Mensaje 3 — Usuario

qué diseño es el que se recomienda clonar en 4.? me das un enlace?

## Respuesta 3 — Claude

El que se recomienda es el **Agilent (HP) E3620A**. Lo propone un forero en el hilo ["What circuit is best (two linear bench PS and know-how)"](https://www.eevblog.com/forum/projects/what-circuit-is-best-(two-linear-bench-ps-and-know-how)/msg1957315/), donde dice que él clonaría ese modelo. En el mismo hilo también se cita la serie HP 62xx como un diseño de los años 60 muy depurado.

Pero el E3620A no te sirve tal cual, porque **la corriente no se ajusta desde el panel**. Tiene dos salidas de 0–25 V / 1 A con un límite fijo de corriente que solo se cambia con un ajuste interno. Según su manual, usa Darlingtons 2N6056 como transistores de paso, y unos triacs eligen la toma del transformador según la tensión de salida.

Para lo que tú quieres, la referencia más útil de la misma familia es la **serie E361xA** (E3610A/E3611A/E3612A). Tiene mandos de tensión y de corriente en el panel y dos rangos; por ejemplo, el E3610A da 0–8 V / 3 A o 0–15 V / 2 A. De esta serie salía la explicación del control flotante que te resumí en el punto 4. Ahí mezclé dos cosas: esa explicación era del E3610A, mientras que la recomendación de clonar era del E3620A.

Enlaces:

- **Manual de servicio del E3620A:** [xdevs.com](https://xdevs.com/doc/HP_Agilent_Keysight/HP%20E3620A%20Operating%20%26%20Service.pdf). Incluye la explicación del funcionamiento.
- **Hilo de EEVblog con los esquemas del E3620A:** [en este hilo](https://www.eevblog.com/forum/testgear/agilent-e3620a-power-supply-no-schematic-available-says-agilent-support/) un forero adjuntó el manual con esquemas, después de que Agilent dijera que no los tenía disponibles.
- **Manual del E3610A/E3611A/E3612A:** [aquí](https://www.ecb.torontomu.ca/guides/instrument-manuals/Agilent-HP_E3611A_User.pdf).
- **Explicación del circuito del E3610A:** [en All About Circuits](https://forum.allaboutcircuits.com/threads/hp-e3610a-power-supply-design-logic.186813/).

No he podido comprobar si los PDF traen escaneadas las páginas de los esquemas. Los manuales dicen que van al final, pero solo pude leer el texto, y el servidor de xdevs me bloqueó la descarga directa.

## Mensaje 4 — Usuario

compara ventajas e inconvenientes 1. vs 3.

## Respuesta 4 — Claude

La 1 es más sencilla y difícil de romper, pero tiene techos de corriente y tensión y un límite de corriente poco preciso. La 3 es más complicada, pero es la que permite un CC/CV de verdad, y por eso la usan casi todos los diseños que se discuten en los foros.

| | **1. Regulador integrado** (LM317/LM338, LT3080/LT3081) | **3. Amplificadores operacionales + transistor de paso** |
|---|---|---|
| **Complejidad** | Muy pocas piezas. Es difícil que salga mal. | Más piezas. El trazado de la placa y la compensación de los lazos importan mucho. |
| **Protecciones** | El chip ya trae protección térmica y de sobrecarga, así que es casi indestructible. El LB-28 usaba LM395 justo por eso. | No trae ninguna. El límite de calor del transistor (SOA), el corte térmico y los fusibles los tienes que diseñar tú. |
| **Corriente máxima** | Cada chip da poco: 1,1 A el LT3080, 1,5 A el LM317 y el LT3081, 5 A el LM338. Para más hay que poner varios en paralelo. | La que quieras, con varios transistores en paralelo con resistencias de emisor. |
| **Tensión máxima** | La limita el chip, a unos 35–40 V entre entrada y salida. | La limitan el transistor y la alimentación de los operacionales. Con una alimentación auxiliar flotante, tipo HP, no hay techo práctico. |
| **Llegar a 0 V** | El LM317 necesita un rail negativo de −1,25 V. El LT3080/3081 sí llega a 0 V, con una pequeña carga mínima en la salida. | Fácil, con un rail negativo pequeño para los operacionales. |
| **Precisión del límite de corriente** | Es el punto débil. Con un transistor que mide la caída en una resistencia, el límite es blando y cambia con la temperatura. Con un segundo LM317 en serie como fuente de corriente se añade caída de tensión, y Kleinstein lo ve sin ventajas y con problemas. El LT3081, con su patilla de límite de corriente, es la mejor opción dentro de este grupo. | Preciso, porque un lazo con operacional compara la caída en la resistencia de medida con una referencia. Se ajusta desde casi 0 mA y es fácil poner un LED que indique cuándo está limitando. |
| **Transición CC↔CV** | Depende del chip y no se puede ajustar. | Se puede afinar con anti-windup y la compensación, pero también puede salir mal (picos y oscilaciones, como se vio en el hilo de xavier60). |
| **Condensador de salida y velocidad** | El chip impone sus condensadores mínimos para ser estable. | Puedes diseñar para un condensador de salida pequeño y un límite de corriente rápido. |
| **Calor** | Todo se concentra en una cápsula TO-220. Con poca tensión de salida y mucha corriente, salta la protección térmica, y eso molesta en una fuente de banco. | Se reparte entre varios transistores grandes (TO-3P, TO-264). Disipa lo mismo, pero se gestiona mejor. |
| **Caída de tensión mínima (dropout)** | De 2–3 V en el LM317. Unos 1,3 V en el LT3080, o 0,35 V si su control se alimenta aparte. | Depende del diseño, de 1 a 2 V. El de xavier60 se queda en 1 V a 5 A. |
| **Control digital** | Posible, con un DAC en la patilla SET o ADJ, aunque limitado. | Natural: basta con poner un DAC en las referencias de tensión y corriente. |
| **Depuración** | Casi no hace falta. | Conviene tener osciloscopio y simular antes en LTspice. |

La disipación es la misma en ambas, porque las dos son lineales. Conmutar tomas del transformador ayuda igual en las dos.

**Cuándo elegir cada una:**
- **La 1**, si te basta con algo modesto (hasta 1,5–3 A y unos 0–30 V) y un límite de corriente que proteja sin ser preciso. La variante más recomendable es el LT3081, con dos en paralelo como en el diseño de Analog Devices pero alimentados desde un transformador.
- **La 3**, si quieres un CC ajustable y fiable, más de 3 A o más tensión, o control por microcontrolador. Para empezar, conviene copiar un diseño ya depurado, como el de xavier60 o la versión de Audioguru del kit de 0–30 V.

Si me dices hacia dónde te inclinas, te busco esquemas concretos de esa opción.

## Mensaje 5 — Usuario

vamos con la 3., aunque me da miedo la inestabilidad de la realimentación...

## Respuesta 5 — Claude

Es normal tenerle miedo: en los foros todos coinciden en que la estabilidad es la parte difícil. Bram ("Blackdog") dice que lo más importante de una fuente lineal es el margen de fase del lazo. Pero hay método para controlarla, y xavier60 terminó su hilo diciendo que esta topología, bien hecha, funciona bien.

#### Por qué oscila

- **Cada etapa añade retraso de fase:** el operacional, el transistor excitador y el de paso. Bram calcula que un operacional solo tiene unos 60° de margen y que los transistores de potencia se comen parte. Por eso un operacional rápido no basta para tener una buena fuente.
- **El condensador de salida y la carga:** su ESR (resistencia interna) y su ESL (inductancia) cambian la fase. En una variante del diseño de Audioguru, la simulación de iMo dio solo 15° de margen con carga capacitiva, que es muy poco.
- **La transición entre limitar corriente y regular tensión:** el lazo que no manda se satura. Al cambiar de modo eso no produce oscilación, pero sí picos.
- **Montaje:** cables largos hasta los transistores de paso, masas mal unidas y, si usas MOSFET, la capacidad de puerta, que complica la estabilidad.

#### Qué se hace para evitarlo

- **Compensar el lazo:** condensador de realimentación en el operacional (Bram dice que sin él casi seguro oscila) y condensadores de adelanto de fase, como en el diseño de Greg Jolley. Kleinstein propone añadir una resistencia en serie con el condensador de realimentación, porque da un punto más de ajuste.
- **Sobre el condensador de salida hay debate:**
  - Kleinstein: suele hacer falta uno con algo de ESR para estabilizar.
  - David Hess: necesitarlo es señal de que la compensación está mal hecha.
  - En la práctica se usan 47–100 µF; por debajo de 1 µF es difícil que sea estable.
- **En la etapa de potencia:** resistencias entre base y emisor, resistencias en serie con la base y condensadores de desacoplo junto a los transistores (David Hess, Rod Elliott).
- **Operacionales lentos y fiables:** LM358/LM324 o TLC072 funcionan bien. El TL081 se desaconseja: invierte la fase cerca de sus límites de entrada y tiene un límite de alimentación bajo.
- **Anti-saturación:** un diodo que impide que el lazo de tensión se sature mientras se limita corriente. La versión final de xavier60 toma la realimentación del lazo de tensión del punto donde se unen los diodos de los dos lazos.

#### Cómo comprobar que es estable antes de fiarte

1. **Simula en LTspice.** Haz dos cosas:
   - Escalones de carga en el tiempo.
   - Ganancia de lazo con la sonda de Tian/Middlebrook (vienen ejemplos con LTspice: LoopGain.asc) para medir el margen de fase. Una guía de Analog Devices pide más de 40°.

   Prueba en vacío y con cargas resistivas, capacitivas (de 1 µF a 1000 µF) e inductivas (cable largo).
2. **En el banco, escalón de carga:** un MOSFET que conecta y desconecta una resistencia, con flancos al menos 5 veces más rápidos que la respuesta de la fuente (consejo de Tim). Mira la salida con el osciloscopio:
   - Sin oscilaciones amortiguadas: buen margen.
   - Varios ciclos de oscilación: margen pobre.

   Jolley midió con este método 2 µs de subida y un 15 % de sobreimpulso, sin oscilación.
3. **Prueba todos los modos:** regulando tensión, limitando corriente y en las transiciones entre ambos, a varias tensiones de salida, porque el margen cambia con el punto de trabajo.

#### Diseños con esquema para no partir de cero

- **xavier60 / JuanGg (el más depurado en EEVblog):** 2 canales de 30 V / 0,5 A con control por microcontrolador. JuanGg publicó esquemas, PCB y firmware en [GitHub](https://github.com/Juan-Gg/Linear-lab-bench-power-supply/tree/master) (yo no pude abrir el repositorio, pero es el enlace que él da en el hilo). El desarrollo está en el [hilo de EEVblog](https://eevblog.com/forum/projects/linear-lab-power-supply).
- **xavier60 en versión de más corriente:** el [hilo "LM324 Power Supply"](https://www.eevblog.com/forum/beginners/lm324-power-supply-with-variable-voltage-and-current/msg4110283/), con TIP35C, conmutación de tomas y hasta 5 A. xavier60 sigue respondiendo allí.
- **Greg Jolley:** [diseño de 35 V / 4 A](https://gregjolley.github.io/media/JolleyGS_design_low_noise_high_performance_linear_power_supply.pdf) con todo el análisis de estabilidad en LTspice y medidas reales. Muy útil para aprender el método aunque no lo copies.
- **Blackdog:** [hilo de EEVblog](https://eevblog.com/forum/beginners/how-does-blackdog_s-psu-work). Bram midió unos ±3 mV de desviación con un escalón de carga de 0,5 a 2 A.

Mi recomendación es partir del diseño de xavier60, simularlo en LTspice tal cual antes de tocar nada y validarlo con el escalón de carga.

¿Qué rango aproximado de tensión y corriente tienes en mente? Con eso puedo ver cuál de estos diseños se adapta mejor y qué habría que cambiar.

**Fuentes:**
- [EEVblog – How does Blackdog's PSU work (pág. 2)](https://eevblog.com/forum/beginners/how-does-blackdog_s-psu-work/25)
- [EEVblog – Linear lab power supply, versión final de xavier60](https://eevblog.com/forum/projects/linear-lab-power-supply/msg2409717)
- [EEVblog – 0-30V 0-3A PSU, versión de Audioguru (análisis de iMo)](https://eevblog.com/forum/beginners/0-30v-0-3a-psu-audiogurus-version/50)
- [G. Jolley – Benchtop linear power supply: design, construction and characterisation](https://gregjolley.github.io/media/JolleyGS_design_low_noise_high_performance_linear_power_supply.pdf)
- [Analog Devices – Control Loop Simulation Done the Easy Way](https://www.analog.com/en/resources/technical-articles/control-loop-simulation-done-the-easy-way.html)
- [Frank Wiedmann – Loop gain simulation (sonda para LTspice)](https://sites.google.com/site/frankwiedmann/loopgain)
- [Blog de JuanGg – Linear lab power supply](https://juangg-projects.blogspot.com/2019/05/linear-lab-power-supply.html)

## Mensaje 6 — Usuario

y a la hora de crear la PCB: qué tener en cuenta para evitar oscilaciones?

## Respuesta 6 — Claude

En los foros se repite mucho que, en una fuente lineal, la mitad de la estabilidad depende del montaje. El principio de fondo es que las corrientes grandes no pasen por donde el circuito de control "mide". Esto es lo más citado:

#### 1. Masas y caminos de corriente (lo más importante)

- **Dibuja primero el lazo de potencia y hazlo corto y grueso:** transformador → puente rectificador → condensadores de filtro → transistor de paso → resistencia de medida de corriente → bornes de salida → y vuelta.
- **Los picos de carga de los condensadores de filtro tienen que quedarse entre el puente y los condensadores:**
  - Lleva el puente directamente a las patas de los condensadores.
  - Saca la alimentación del regulador de las patas de los condensadores, no de un punto intermedio.
  - Si esos picos pasan por la masa de referencia, meten ruido modulado (aviso habitual en diyAudio).
- **La masa de control entra en contacto con la de potencia en un solo punto.** La masa de control es la de la referencia de tensión, la parte baja del divisor de tensión y los operacionales. xavier60 insiste en una única conexión entre el negativo de salida y esa masa, y reforzó la pista con hilo de cobre de 0,8 mm.
- **Plano de masa:** se puede usar en la zona de control, pero sin que las corrientes de potencia pasen por debajo. Si hace falta, abre ranuras en el plano para forzar por dónde va la corriente. Un plano "por todas partes" sin pensar en las corrientes se critica mucho.
- **Conexión Kelvin en la resistencia de medida:** las pistas que leen su caída salen de sus propios pads y no comparten cobre con la pista de potencia. En el diseño de JuanGg, llevar la masa del operacional de corriente al lado negativo de esa resistencia arregló una transición tensión→corriente sucia.
- **Lo auxiliar no puede devolver su corriente por la resistencia de medida ni por la masa de referencia.** Microcontrolador, display y ventilador llevan su propio regulador y su propio retorno (Kleinstein).
- **La realimentación de tensión se toma directamente en los bornes de salida**, con su propia pista, o con sensado remoto si lo quieres.

#### 2. Etapa de potencia y cableado

- **Cables cortos hasta los transistores de paso.** Es uno de los consejos que recibió JuanGg. Si van fuera de la placa, en el disipador:
  - Trenza los cables de base y emisor.
  - Pon el excitador cerca del transistor de paso.
  - Coloca las resistencias de base y de emisor junto al transistor, no en la placa.
- **Resistencias de base: valores pequeños, de decenas a cientos de ohmios.** Cortan oscilaciones de alta frecuencia, pero si son grandes añaden retraso de fase y empeoran el lazo. Así se lo explicó audioguru2 a un forero que las había puesto de 100 kΩ. Hero999 recuerda que la etapa de salida más estable es un seguidor de emisor.
- **Desacoplos locales:** un condensador de 100 nF cerámico o de película más un electrolítico, junto al colector de los transistores de paso y en los pines de alimentación de cada operacional. Kleinstein explica que el pequeño es necesario porque los electrolíticos rinden mal a alta frecuencia.
- **El condensador de salida va pegado a los bornes**, con conexiones cortas, porque su ESR y su inductancia forman parte del lazo.

#### 3. Zona de control

- **Los componentes de compensación van pegados a los pines del operacional**, con los nodos de realimentación cortos y lejos de las pistas de potencia, del puente y del transformador. Son nodos de alta impedancia y captan zumbido.
- **Transformador y cableado de red lejos de la placa de control.** JuanGg cambió a un transformador toroidal porque el campo del anterior le hacía temblar la imagen del osciloscopio.
- **Los cables a los potenciómetros del panel actúan como antenas.** Trénzalos y pon un pequeño filtro RC en la entrada del operacional, como hace el diseño LB-28 con su referencia.

#### 4. Prepara la placa para depurar

- **Huecos de reserva:**
  - Footprints libres para condensadores de compensación extra (en paralelo con la realimentación, entre base y emisor).
  - Resistencias de 0 Ω que luego puedas cambiar por resistencias de base.
  - Un sitio para una red RC en la salida.

  Jolley dejó previsto quitar un condensador si aparecía oscilación en la placa real.
- **Puntos de prueba** en la salida de los dos operacionales, en la resistencia de medida y en la salida, con sitio para la punta de masa corta del osciloscopio.
- **Ojo con los zócalos:** a JuanGg se le soltaron los operacionales y la salida subió de golpe a 30 V. Si los usas, que sean buenos, o suelda.
- **Resistencia que lleve a masa la salida del operacional de tensión:** xavier60 vio que su TLC072 dejaba la salida flotando cuando la alimentación de control caía por debajo de unos 3 V, y la fuente quedaba sin control.
- **Distancias de seguridad** en toda la parte conectada a la red.

Cuando tengas el esquema o un primer layout, si me lo pasas lo reviso con esta lista.

**Fuentes:**
- [EEVblog – Linear lab power supply (xavier60/JuanGg)](https://eevblog.com/forum/projects/linear-lab-power-supply/msg2044945) y [página 350](https://eevblog.com/forum/projects/linear-lab-power-supply/350)
- [EEVblog – My Project: Modern Linear Power Supply](https://www.eevblog.com/forum/projects/my-project-modern-linear-power-supply/)
- [Electronics-Lab – New Power Supply II (oscilación y resistencias de base)](https://www.electronics-lab.com/forums/threads/new-power-supply-ii.311133/)
- [G. Jolley – Benchtop linear power supply](https://gregjolley.github.io/media/JolleyGS_design_low_noise_high_performance_linear_power_supply.pdf)
- [National LB-28 – General Purpose Power Supply](https://xdevs.com/doc/_Magazines/LB-28.pdf)
- [diyAudio – Unregulated PSU, picos de carga por la masa de referencia](https://www.diyaudio.com/community/threads/my-first-ever-pcb-board-unregulated-psu-for-a-two-gainclones.57984)
- [Maxim AN2997 – Layout de reguladores (masas de referencia, divisor y condensador de salida)](https://www.scribd.com/document/489646010/AN2997)
- [All About Circuits – Low-side current sensing: layout tips (Kelvin)](https://www.allaboutcircuits.com/technical-articles/using-single-ended-amplifiers-in-low-side-current-sensing-error-sources-and-layout-tips/)

## Mensaje 7 — Usuario

De todos estos hilos: donde se presenta una fuente construida y medida que funciona bien?

## Respuesta 7 — Claude

Ningún hilo de EEVblog publica una hoja de medidas completa como la de una fuente comercial. Las fuentes construidas con más datos medidos están en una revista (Silicon Chip) y en el documento de Greg Jolley. Entre los foros, la mejor documentada como "construida y funcionando" es la de xavier60/JuanGg.

#### Con medidas publicadas

**1. Silicon Chip, fuente lineal de 45 V / 8 A (Tim Blythman, octubre–diciembre de 2019)**
- **Medidas** (capturas de osciloscopio en el artículo, a 25 V / 4 A):
  - Rizado en la salida de 3 mV, que ya es el ruido de fondo de la sonda.
  - Al conectar la carga, la salida no se separa más de 200 mV y se estabiliza en menos de 1 ms.
  - Al quitarla, sube 0,5 V y se recupera en 2 ms.
  - Prueba térmica: 300 W continuos, con el disipador estable a 77 °C.
- **Topología:** es enteramente lineal. Un LM317HV hace de regulador de control, cuatro transistores FJA4313 llevan la corriente, dos operacionales cierran los lazos de tensión y corriente, y un INA282 mide la corriente.
- **Pega:** el límite de corriente es lento. En un escalón de carga, con el límite a 5 A, la corriente llegó a casi 7 A antes de corregirse en unos milisegundos.
- **Disponibilidad:** la revista vende la PCB y kits de piezas. El artículo completo es de pago; en la web solo hay una vista previa.
- [Parte 1 en Silicon Chip](https://www.siliconchip.com.au/Issue/2019/October/45V%2C+8A+Bench+Power+Supply+to+build)

**2. Greg Jolley, documento de diseño y medidas**
- **Es el que mejor mide el comportamiento de los lazos:**
  - Con un escalón de carga sobre 10 Ω: subida en unos 2 µs, 15 % de sobreimpulso y sin oscilaciones.
  - Con el límite de corriente a 0,5 A: picos de 0,74 A durante unos 6 µs.
  - Ruido medido: coincide con el cálculo, salvo por debajo de unos 5 kHz, donde es algo mayor.
- **Pega:** él mismo dice que es un trabajo en curso, no un aparato terminado.
- [PDF](https://gregjolley.github.io/media/JolleyGS_design_low_noise_high_performance_linear_power_supply.pdf)

**3. Silicon Chip, fuente de 30 V / 2 A (octubre de 2022)**
- **Medidas:** regulación de carga mejor del 0,5 % y ruido inferior a 8 mV RMS (50 mV pico a pico) a 2 A.
- **Pega:** es más sencilla (LM317 reforzado con un transistor PNP) y el ruido es discreto para ser lineal.
- [Artículo](https://siliconchip.com.au/Issue/2022/October/30V+2A+Bench+Supply%2C+Part+1)

#### En foros: construidas y funcionando, pero con pocas medidas

**4. xavier60 / JuanGg (EEVblog), la opción 3 más contrastada**
- **Construida dos veces:** el prototipo de xavier60 y la fuente de JuanGg, de dos canales de 30 V / 0,5 A, terminada con caja.
- **Datos sueltos:** rizado de pocos mV, lazo compensado para responder en unos 3 µs y una caída mínima de 1 V a 5 A en la versión de potencia de xavier60.
- **Lo más útil:** en el hilo aparecen problemas reales y cómo se arreglaron. Por ejemplo, oscilaba al limitar a pocos miliamperios, y el lazo de tensión se saturaba al pasar de limitar corriente a regular tensión.
- **Pega:** no hay una tabla de especificaciones medidas.
- [Hilo](https://eevblog.com/forum/projects/linear-lab-power-supply) y [GitHub](https://github.com/Juan-Gg/Linear-lab-bench-power-supply/tree/master)

**5. Blackdog (Bram)**
- **Construida.** Con un escalón de carga de 0,5 a 2 A, la salida se mueve unos ±3 mV. Tim la considera el único diseño amateur que ha visto funcionar tal cual está dibujado.
- **Pega:** hay pocas medidas, y Tim puso en duda una prueba a 9,5 A. El desarrollo original está en neerlandés, en circuitsonline.
- [Hilo de EEVblog](https://eevblog.com/forum/beginners/how-does-blackdog_s-psu-work)

#### Las que no cuentan como "probadas"

- **"Modern Linear Power Supply" de B0B45 (2025), 36 V / 5 A:** está construida, pero sigue en pruebas y se le soldó un relé.
- **Versión mejorada del kit de 0–30 V (Audioguru):** la han montado muchos, pero en los hilos hay problemas sin resolver y ninguna medida.
- **Circuitos del artículo de Rod Elliott:** él mismo avisa de que no están construidos ni probados. Su Project 223 sí lo está, pero es de tipo 1 (con LM317) y casi sin medidas.

Si quieres algo reproducible con resultados conocidos, la de 45 V / 8 A de Silicon Chip es la más completa, aunque está a medio camino entre la opción 1 y la 3. Si quieres seguir con la opción 3 pura, lo mejor es partir de xavier60/JuanGg y usar el documento de Jolley como guía para medirla tú.

## Mensaje 8 — Usuario

éste Tim… es forero?

## Respuesta 8 — Claude

Sí, es un forero de EEVblog. Su usuario es **T3sl4co1l** y firma como Tim. Es "Super Contributor", con más de 22.000 mensajes, y en su perfil indica que es de EE. UU. y que su especialidad es la electrónica analógica, el diseño de PCB y la compatibilidad electromagnética. Lleva una pequeña consultora de diseño llamada Seven Transistor Labs.

Es de los foreros con más criterio técnico en EEVblog, y por eso pesa su opinión sobre la fuente de Blackdog. También aparecía en el hilo sobre la fuente conmutada, proponiendo filtros de salida, y fue quien explicó cómo hacer bien la prueba de escalón de carga.

## Mensaje 9 — Usuario

y que opina el de las diferentes opciones?

## Respuesta 9 — Claude

Tim no da un veredicto único: sus opiniones están repartidas en hilos de 2014 a 2024. Juntándolas, defiende la lineal, se fía poco de los reguladores integrados y cree que una conmutada puede funcionar bien, aunque es difícil hacerla limpia. Encaja bastante con tu elección de la opción 3.

#### Lineal frente a conmutada, en general

- Dice que, "hablando como ingeniero profesional", no dudaría en usar un regulador lineal en cualquier aplicación. Reserva la conmutada para cuando importa la eficiencia.
- Para él la seguridad no depende de la topología, sino de las protecciones: un circuito "crowbar" que cortocircuita la salida si se dispara la tensión, y enclavamientos.

#### Opción 1: reguladores integrados

Es la que peor parada sale:
- A un forero que montó varios LM317 en paralelo le dijo que los reguladores no se pueden conectar en paralelo así.
- Le recomendó quitarlos y usar transistores bipolares de potencia normales, con la realimentación tomada en la salida.
- Si hace falta más corriente, propone un Darlington alimentado desde la tensión sin regular, o varios transistores en paralelo con resistencias de emisor, y resistencias de base si oscila.

#### Opción 3: operacionales + transistor de paso (la tuya)

- **Etapa de salida:** el seguidor de emisor es "difícil de batir" por lo fácil que es de usar. El par Sziklai (un transistor de cada tipo combinado) no es lo mejor para la estabilidad.
- **Transistores bipolares:** por debajo de unos 30 V, pocos sufren el fallo por puntos calientes (segunda ruptura), así que a esas tensiones casi no hay que preocuparse.
- **MOSFET:** no tiene problema en usarlos si la curva de zona segura (SOA) lo permite, pero en uso lineal "la oscilación y el coeficiente de temperatura son grandes preocupaciones".
  - Con un MOSFET como seguidor, la resistencia de fuente fija la ganancia máxima del transistor y ayuda a la estabilidad, así que cuanto mayor, mejor. De paso da protección frente a cortocircuitos.
- **Compensación:**
  - Poner una resistencia en serie con el condensador de realimentación.
  - Filtrar la entrada no inversora del operacional.
  - Probar valores en un rango amplio (10 k, 100 k, 1 M y varios condensadores), no uno solo.
- **Condensador de salida:** si la etapa de salida es lenta, ve razonable usar "cientos de µF".

#### Híbrida (conmutada + lineal)

No está en contra, pero avisa de que es más difícil de lo que parece:
- El conmutado es la parte lenta del conjunto, y siempre queda algo de su ruido en la salida.
- El transistor que hace que el conmutado siga a la etapa lineal añade ganancia al lazo y puede volverlo inestable.
- Los controladores baratos salen caros: con un 34063 se ahorran céntimos en el chip y se gastan euros en bobinas y condensadores enormes para filtrarlo. El LM2596 le parece razonable, aunque regula flojo.
- Prefiere controladores que tengan accesible el pin del amplificador de error, para poder ajustar la compensación.

#### Conmutada pura

- Cree que es viable: una conmutada "puede ser bastante ágil", y su límite fundamental está en el filtro de salida.
- Usaría control por corriente media y dimensionaría el filtro según la tensión y la corriente máximas de la fuente.
- El ruido de alta frecuencia se puede controlar con filtros y blindaje, pero reconoce que hacerlo bien requiere años de experiencia.

#### Control digital

- Le parece bien que un microcontrolador fije las referencias con un DAC y lea las medidas con un ADC: es seguro y fiable, aunque lento.
- No lo quiere dentro del lazo de regulación, porque no reaccionaría a tiempo ante un cortocircuito o un pico de entrada.
- También se burló de usar un relé dentro del lazo para cambiar entre modo de tensión y de corriente.

**Fuentes:**
- [EEVblog – 0-350V 0.2A Bench Power Supply (pág. 11)](https://www.eevblog.com/forum/projects/looking-for-yours-opinions!-hv-stabilized-power-supply/250/)
- [EEVblog – My analog 0-12V 3A benchtop power supply](https://www.eevblog.com/forum/projects/my-analog-1-25-12v-3a-benchtop-power-supply/)
- [EEVblog – DIY power supply stability](https://www.eevblog.com/forum/projects/diy-power-supply-stability/)
- [EEVblog – Power supply topology, will it work? (pág. 3)](https://www.eevblog.com/forum/projects/power-supply-topology-will-it-work-(control-theory-stability)/50/)
- [EEVblog – Is 550uF too big for a power supply that has CC limit?](https://eevblog.com/forum/projects/is-550uf-too-big-for-a-power-supply-that-has-cc-limit)
- [EEVblog – Mixed linear and switch-mode topology in a lab power supply?](https://www.eevblog.com/forum/projects/mixed-linear-and-switch-mode-topology-in-a-lab-power-supply/25/)
- [EEVblog – Switching Lab supply design](https://eevblog.com/forum/projects/switching-lab-supply-design)

## Mensaje 10 — Usuario

volvamos a las ideas basadas en 1., donde nos adaptamos a la potencia disipada por el LM317 o LM317HV

## Respuesta 10 — Claude

Con un solo LM317 se pueden sacar de forma sostenida unos 10 W de calor, así que todo el diseño gira en torno a mantener (Vin − Vout) × I por debajo de esa cifra.

#### Cuánto calor aguanta un LM317

- Según el datasheet de onsemi, el encapsulado TO-220 tiene 5 °C/W entre el chip y la lengüeta. A eso se suma alrededor de 1 °C/W del aislante, que es obligatorio porque la lengüeta está conectada a la salida.
- Con el disipador a 60 °C y el chip a 125 °C (el máximo recomendado por TI), salen unos 10–11 W. Si quieres margen, cuenta con unos 8 W.
- **El límite interno de corriente también baja con la diferencia de tensión:**
  - Solo garantiza 1,5 A mientras Vin − Vout no pase de 15 V.
  - Con 40 V de diferencia, el mínimo cae a 0,15 A (0,4 A típico).
  - El LM317HV admite hasta 60 V de diferencia, pero a 60 V da unos 0,3 A típicos.

#### Cuánta corriente sale según el número de tomas del transformador

He hecho el cálculo con 10 W por regulador, 5 V de margen entre entrada y salida (para la caída mínima y el rizado) y tomas repartidas por igual. Es una estimación aproximada, no una medida:

| Rango de salida | Sin tomas | 2 tomas | 3 tomas | 4 tomas | 6 tomas |
|---|---|---|---|---|---|
| 0–30 V (LM317) | 0,29 A | 0,44 A | 0,60 A | 0,73 A | 0,92 A |
| 0–50 V (LM317HV) | 0,18 A | 0,31 A | 0,43 A | 0,53 A | 0,71 A |

Con un solo LM317, 1,5 A en todo el rango no es realista. Para eso hay que repartir el calor (punto 3 de la lista siguiente).

#### Ideas que se proponen

**1. Aceptar el límite y diseñar a su medida: Project 223 de Rod Elliott**
- Dos canales de 0–25 V con LM317, un LM337 que da una referencia de −1,25 V para llegar a 0 V y un sumidero de 6 mA para que regule sin carga.
- La limitación de corriente es por rangos conmutables: 30 mA, 300 mA o el máximo.
- El propio Rod avisa de que sacar 5 V a 1 A supone unos 30 W en el regulador. Por eso recomienda una fuente de 5 V aparte, un disipador de túnel y ventilador.

**2. Conmutar tomas: la palanca principal**
- **Con un conmutador manual de rango**, como el botón RANGE del HP E3610A, te evitas los problemas de los relés.
- **Automático con relés y un comparador con histéresis.** Ojo: la corriente de carga de los condensadores puede soldar los contactos. Se recomienda conmutar cuando la tensión del transformador esté por debajo de la del condensador.
- **Truco barato:** con un transformador de dos secundarios iguales, un relé que los pone en serie o en paralelo te da 2 tomas sin transformador especial. Así lo hace xavier60.
- **Bonus:** al mantener la diferencia baja, el LM317 conserva su límite de corriente completo.

**3. Repartir el calor**

El calor total es el mismo; estas ideas solo lo mueven de sitio.
- **Una resistencia de potencia (o una bombilla) en serie antes del LM317.** Se queda con parte de la caída cuando la corriente es alta. A cambio, quita margen de tensión justo a corriente máxima, y eso limita la tensión de salida máxima con carga.
- **Un pre-regulador lineal que sigue a la salida.** Puede ser un segundo LM317, o un Darlington con un zener, como propone un forero en diyAudio para un LM317HV de 0–50 V. Mantiene la entrada del LM317 unos 5 V por encima de la salida y se come el resto de la caída en un encapsulado más grande. Funciona, pero ese transistor acaba haciendo el trabajo duro, así que ya estás a medio camino de la opción 3.
- **Varios LM317 en paralelo.** Tim avisa de que no se pueden unir directamente. Con resistencias de reparto en cada salida funciona más o menos, pero la tolerancia de la referencia (1,20–1,30 V) hace que repartan mal. Si vas por este camino, los LT3080/LT3081 están diseñados para ponerse en paralelo.

**4. Limitar la corriente según lo que puede disipar**
- Rangos de corriente como los de Rod Elliott.
- Un microcontrolador que mida Vin, Vout e I y baje el límite de corriente (o avise) si se pasa del presupuesto de calor. xavier60 hace algo parecido: un LED parpadea si pides más corriente de la que puede dar el transformador.
- Termostato con ventilador y un corte térmico, como en la fuente de 30 V / 2 A de Silicon Chip.
- El LM317 se protege solo y no se quema, pero cuando se calienta corta la salida, y en una fuente de banco eso molesta.

#### En resumen

Con un LM317 y 2–3 tomas, lo realista es 0–30 V a 0,5–0,6 A; con 4–6 tomas te acercas a 1 A. Si necesitas 1,5 A o más, lo que hace falta para repartir el calor (un pre-regulador con transistor gordo) te deja prácticamente en la opción 3.

**Fuentes:**
- [onsemi – Datasheet LM317 (5 °C/W en TO-220)](https://www.onsemi.com/download/data-sheet/pdf/lm317-d.pdf)
- [TI – Datasheet LM317](https://www.ti.com/lit/ds/symlink/lm317.pdf) y [LM317HV](https://www.ti.com/document-viewer/LM317HV/datasheet/specifications)
- [ESP – Project 223, fuente doble 0–25 V con LM317](https://sound-au.com/project223.htm)
- [ESP – Power Supply Pre-Regulator Techniques](https://sound-au.com/articles/preregulators.htm)
- [All About Circuits – Heating problem in LM317 (resistencia en serie)](https://forum.allaboutcircuits.com/threads/heating-problem-in-lm317.123245/)
- [diyAudio – Problems with my power supply (LM317HV de 0–50 V)](https://www.diyaudio.com/community/threads/problems-with-my-power-supply.35105)
- [EEVblog – My analog 0-12V 3A benchtop power supply (opinión de Tim)](https://www.eevblog.com/forum/projects/my-analog-1-25-12v-3a-benchtop-power-supply/)
- [EEVblog – My Project: Modern Linear Power Supply (relés soldados)](https://www.eevblog.com/forum/projects/my-project-modern-linear-power-supply/)
- [Silicon Chip – 30V 2A Bench Supply](https://siliconchip.com.au/Issue/2022/October/30V+2A+Bench+Supply%2C+Part+1)

## Mensaje 11 — Usuario

se podría adaptar el 223 de rod elliott a un lm317hv?

## Respuesta 11 — Claude

Sí. El LM317HV tiene las mismas patillas y la misma referencia de 1,25 V que el LM317, así que entra en la placa sin cambios. Lo que haya que tocar depende de para qué lo quieras.

#### Caso 1: mismos 0–25 V, solo para tener más margen

Es casi un cambio directo, y tiene sentido. Rod no da la tensión sin regular, pero el texto sugiere unos 35 V. El LM317 normal admite como máximo 40 V entre entrada y salida, y en vacío, con la red alta y la salida en cortocircuito, se puede acercar a ese límite. El HV admite hasta 60 V.

Lo único que conviene revisar es la corriente mínima de carga. El LM317HV puede necesitar hasta 12 mA con diferencias altas (dato de TI a 60 V), y el sumidero Q1 de Rod está calculado para unos 6 mA. Para ir sobrado, sube ese sumidero a 10–12 mA cambiando R4.

#### Caso 2: subir cada canal a unos 0–50 V

Se puede, pero ya no es cambiar una pieza:

- **El calor manda.** Con unos 55 V de entrada y la salida cerca de 0 V, el regulador ve casi 55 V de diferencia:
  - Con mi estimación de ~10 W reales por encapsulado, salen unos 0,18 A.
  - Con los 20 W que da Rod como máximo del encapsulado, unos 0,36 A.
  - Además, el propio LM317HV baja su límite interno a unos 0,3 A típicos con esa diferencia.

  En la práctica es una fuente de 0,2–0,3 A a baja tensión, salvo que añadas conmutación de tomas.
- **No pases de unos 55 V de entrada sin regular**, contando la red alta y el pico en vacío, para no superar los 60 V de diferencia cuando la salida esté en 0 V.
- **Componentes que hay que recalcular o cambiar a más tensión:**
  - Condensadores de filtro y de salida: de 63–80 V.
  - El transistor del sumidero Q1 y los dos transistores del limitador de corriente (Q2 y Q3). El limitador va en la línea de entrada, así que verán toda la tensión.
  - La red de ajuste de tensión: el trimmer TP1 tiene que llegar a fondo de escala en 50 V.
  - La alimentación auxiliar del relé y el ventilador: el BD139 bajaría de unos 55 V a 12/24 V y se calentaría mucho más. Mejor un devanado aparte.
  - Las resistencias de 220 Ω de la referencia negativa, si salen del mismo devanado, porque con más tensión el zener disipará más.
  - Los medidores de tensión: el fondo de escala o la resistencia en serie.
- **Seguridad:** por encima de 60 V en continua deja de considerarse tensión segura al tacto. Dos canales de 50 V en serie darían 100 V.

#### Caso 3: si lo que quieres son 50 V, el 223 ya los da

El diseño de Rod permite poner los dos canales en serie, lo que da 0–50 V a 1,5 A. Cada LM317 normal sigue viendo como mucho unos 35 V de diferencia y el calor se reparte entre los dos. Los avisos de Rod para este modo:
- Cambiar entre serie y paralelo siempre con la tensión al mínimo.
- Los dos canales no siguen exactamente igual: puede haber hasta 0,5 V de diferencia entre ellos.

Si buscas robustez con los mismos 25 V, el HV es un buen cambio. Si buscas 50 V, usa el modo serie del 223 antes que meter el HV, que exige rehacer media fuente y deja muy poca corriente a baja tensión.

**Fuentes:**
- [ESP – Project 223](https://sound-au.com/project223.htm)
- [TI – Datasheet LM317HV](https://www.ti.com/document-viewer/LM317HV/datasheet/specifications)
- [TI – Datasheet LM317](https://www.ti.com/lit/ds/symlink/lm317.pdf)
- [onsemi – Datasheet LM317](https://www.onsemi.com/download/data-sheet/pdf/lm317-d.pdf)

## Mensaje 12 — Usuario

para regular la corriente, no puedo usar un potenciometro?

## Respuesta 12 — Claude

Sí, pero el potenciómetro tiene que fijar un umbral o una tensión de referencia, nunca llevar la corriente de carga. Según dónde lo pongas, funciona mal o funciona bien.

#### Lo que no conviene

**Usar el potenciómetro como resistencia de medida**, en serie con la carga, o en el típico LM317 montado como fuente de corriente (con R = 1,25 V / I). Ahí el potenciómetro lleva toda la corriente de la carga, y un potenciómetro normal no aguanta eso: el cursor se quema o mete ruido. Haría falta un reostato bobinado de potencia, que además añade caída de tensión.

#### En el 223 tal cual: funciona, pero con poco recorrido

El limitador de Rod dispara cuando la resistencia de medida cae unos 0,54 V, que es lo que necesita el transistor para empezar a conducir. Puedes poner un potenciómetro como divisor sobre esa resistencia, de modo que el transistor vea solo una parte de la caída. El problema es el recorrido:

- **Rango corto:** el rango ajustable es la caída máxima que aceptes dividida por 0,54 V. Si aceptas como mucho 2 V de caída, solo cubres unas 3,7 veces (por ejemplo, de 0,4 a 1,5 A). Por eso Rod usa rangos fijos (33 mA, 330 mA y máximo) en lugar de un potenciómetro.
- **Deriva con la temperatura:** ese umbral de 0,54 V baja unos 2 mV/°C, así que el límite se mueve al calentarse. Rod también avisa de que el limitador oscilaba hasta que añadió C10.

Se puede combinar: conmutador de rangos más un potenciómetro de ajuste fino dentro de cada rango, aunque quedarán huecos entre rangos.

#### La forma buena: amplificador de medida + operacional

Así lo hace la fuente de 30 V / 2 A de Silicon Chip, que también usa un LM317:
- Una resistencia de medida pequeña (20 mΩ) y un amplificador de corriente INA282 con ganancia 50, que da 1 V por amperio.
- Un operacional compara esa tensión con la que fija el potenciómetro.
- Al pasarse del límite, el operacional activa un pequeño MOSFET (2N7000) que tira de la patilla ADJ del LM317 hacia abajo.
- Lleva condensadores de compensación (100 nF y 1 µF) para que no oscile.

Resultado: un solo potenciómetro de casi 0 al máximo, preciso y estable con la temperatura. El INA282 admite tensiones de −14 a +80 V en sus entradas, así que se puede poner en el mismo sitio que el limitador de Rod, en la línea de entrada.

Su pega es que es lento: el límite actúa en milisegundos, no en microsegundos. Para proteger lo que conectas basta, pero un LED delicado puede sufrir. La fuente de 45 V / 8 A de Silicon Chip, que limita de forma parecida, llegó a dar casi 7 A con el límite en 5 A durante unos milisegundos.

**Para meterlo en el 223:** sustituyes el limitador de transistores (Q2/Q3) por el INA282 + operacional + MOSFET hacia ADJ. El rail de −1,25 V que ya existe sirve para que el MOSFET lleve la salida hasta 0. Como los dos canales flotan entre sí, cada uno necesita su propia alimentación auxiliar para el operacional y el INA282.

#### Consejos para el potenciómetro

- **Multivuelta (10 vueltas), o uno grueso más uno fino.** Con un potenciómetro lineal normal de 0 a 1,5 A, ajustar 20 mA es casi imposible. Otra opción es dejar un conmutador ×0,1 junto al potenciómetro.
- **Que un fallo del cursor dé el mínimo, no el máximo.** Pon una resistencia del cursor a masa para que, si pierde contacto, la referencia caiga a 0 y la corriente al mínimo. Es el mismo riesgo que con el potenciómetro de tensión, donde un cursor que falla puede dejar pasar toda la tensión de entrada a la salida.
- **Un botón para ver el límite fijado**, como el "CC SET" del HP E3610A, que muestra en el amperímetro la corriente límite sin tener que cortocircuitar la salida. Basta con conmutar el medidor a la tensión del potenciómetro.

**Fuentes:**
- [ESP – Project 223](https://sound-au.com/project223.htm)
- [Silicon Chip – 30V 2A Bench Supply, Part 1](https://siliconchip.com.au/Issue/2022/October/30V+2A+Bench+Supply%2C+Part+1)
- [Silicon Chip – 45V 8A Bench Power Supply](https://www.siliconchip.com.au/Issue/2019/October/45V%2C+8A+Bench+Power+Supply+to+build)
- [TI – INA282](https://www.ti.com/product/INA282)
- [Digi-Key – LM317 Design Guide (fallo del cursor)](https://forum.digikey.com/t/lm317-voltage-regulator-design-guide-output-equation-common-pitfalls-and-practical-tips/61877)
- [Manual HP/Agilent E3610A–E3612A (botón CC SET)](https://www.ecb.torontomu.ca/guides/instrument-manuals/Agilent-HP_E3611A_User.pdf)

## Mensaje 13 — Usuario

quiero pasarle todo este chat a una sesión de claude code: como lo hago?

## Respuesta 13 — Claude

Claude Code no tiene acceso a esta conversación, así que hay que llevarle el contexto. Hay dos maneras:

**1. Opción oficial: exportar la tarea**
1. En esta tarea, abre el menú y elige **"Download task data"**.
2. Descomprime la descarga y abre esa carpeta en Claude Code.
3. Ejecuta `/port-task-data`.

La ayuda de Claude solo lo describe para los planes Pro, Max y Ultra, así que puede que en tu cuenta de BMAT no aparezca. Tampoco aclara si funciona con tareas que se ejecutan en la nube, como esta.

**2. Opción segura: un resumen en Markdown**
Ya te he preparado **HANDOFF_fuente_laboratorio.md**, que lo tienes en los archivos de esta conversación. Recoge las decisiones tomadas, los datos de los datasheets, mis cálculos de corriente según las tomas del transformador, los detalles del Project 223 y su adaptación al LM317HV, el límite de corriente con potenciómetro, los diseños medidos, los siguientes pasos y todos los enlaces.

Para usarlo:
1. Descárgalo y ponlo en la carpeta del proyecto.
2. En Claude Code, escribe algo como: `Lee @HANDOFF_fuente_laboratorio.md y ayúdame con el paso 1 de "Siguientes pasos"`.
3. Si quieres que lo cargue solo en cada sesión, renómbralo a `CLAUDE.md` (o pega su contenido dentro de uno que ya tengas).

Si conectas la carpeta del proyecto desde la app de escritorio ("Add folder"), te lo guardo ahí directamente.

## Mensaje 14 — Usuario

El resumen debe contener todos los mensajes del chat que hemos hablado y todos los links. Es decir, debe contener todo.

## Respuesta 14 — Claude

(Respuesta: este mismo fichero, reescrito con la transcripción completa y el índice de enlaces.)

---

# Parte 3 — Índice de todos los enlaces

## A. Enlaces citados en las respuestas

### Hilos de EEVblog
- DIY programmable dual channel bench PSU 0-50V/3A (EEZ H24005): https://eevblog.com/forum/projects/diy-programmable-dual-channel-bench-psu-0-50v3a
- Switching Lab supply design (pág. 1): https://eevblog.com/forum/projects/switching-lab-supply-design
- Switching Lab supply design (pág. 2): https://eevblog.com/forum/projects/switching-lab-supply-design/25
- DIY Scalable Bench Power Supply Design: https://eevblog.com/forum/projects/bench-power-supply-design/msg477284
- fast CC/CV power supply again: https://www.eevblog.com/forum/projects/fast-cccv-power-supply-again/?wap2
- How does Blackdog's PSU work: https://eevblog.com/forum/beginners/how-does-blackdog_s-psu-work
- How does Blackdog's PSU work (pág. 2): https://eevblog.com/forum/beginners/how-does-blackdog_s-psu-work/25
- What circuit is best (two linear bench PS and know-how): https://www.eevblog.com/forum/projects/what-circuit-is-best-(two-linear-bench-ps-and-know-how)/msg1957315/
- LM324 Power Supply with variable voltage and current: https://www.eevblog.com/forum/beginners/lm324-power-supply-with-variable-voltage-and-current/msg4110283/
- Linear lab power supply (JuanGg/xavier60): https://eevblog.com/forum/projects/linear-lab-power-supply
- Linear lab power supply (msg2044945): https://eevblog.com/forum/projects/linear-lab-power-supply/msg2044945
- Linear lab power supply (pág. 350): https://eevblog.com/forum/projects/linear-lab-power-supply/350
- Linear lab power supply (versión final de xavier60): https://eevblog.com/forum/projects/linear-lab-power-supply/msg2409717
- 0-30V, 0-3A PSU, versión de Audioguru: https://eevblog.com/forum/beginners/0-30v-0-3a-psu-audiogurus-version/msg2232978
- 0-30V, 0-3A PSU, versión de Audioguru (análisis de iMo): https://eevblog.com/forum/beginners/0-30v-0-3a-psu-audiogurus-version/50
- Hilo del Riden RD6006: https://eevblog.com/forum/testgear/ruideng-riden-rd6006-dc-power-supply/5
- EEVblog #329 – Tracking Pre-Regulator: https://www.eevblog.com/forum/blog/eevblog-329-tracking-pre-regulator-ltspice-simulation-part-2/msg135509/
- EEVblog #221 – Lab Power Supply Design Part 1: https://www.eevblog.com/2011/11/28/eevblog-221-lab-power-supply-design-part-1/
- CC/CV Benchtop Power Supply Topology Question: https://eevblog.com/forum/projects/cccv-benchtop-power-supply-topology-question/msg5647051
- My Project: Modern Linear Power Supply (2025): https://www.eevblog.com/forum/projects/my-project-modern-linear-power-supply/
- Preregulation of a linear bench PSU: https://www.eevblog.com/forum/projects/preregulation-of-a-linear-bench-psu/msg2072110/
- Transistor vs MOSFET for linear power supply: https://www.eevblog.com/forum/beginners/transistor-vs-mosfet-for-linear-power-supply/msg2018209
- Agilent E3620A, esquemas adjuntos: https://www.eevblog.com/forum/testgear/agilent-e3620a-power-supply-no-schematic-available-says-agilent-support/
- 0-350V 0.2A Bench Power Supply (pág. 11, Tim): https://www.eevblog.com/forum/projects/looking-for-yours-opinions!-hv-stabilized-power-supply/250/
- My analog 0-12V 3A benchtop power supply (Tim): https://www.eevblog.com/forum/projects/my-analog-1-25-12v-3a-benchtop-power-supply/
- DIY power supply stability (Tim): https://www.eevblog.com/forum/projects/diy-power-supply-stability/
- Power supply topology, will it work? (pág. 3, Tim): https://www.eevblog.com/forum/projects/power-supply-topology-will-it-work-(control-theory-stability)/50/
- Is 550uF too big for a power supply that has CC limit? (Tim): https://eevblog.com/forum/projects/is-550uf-too-big-for-a-power-supply-that-has-cc-limit
- Mixed linear and switch-mode topology in a lab power supply? (Tim): https://www.eevblog.com/forum/projects/mixed-linear-and-switch-mode-topology-in-a-lab-power-supply/25/

### Otros foros
- element14 – DIY Lab PSU: what to choose?: https://community.element14.com/technologies/test-and-measurement/f/forum/39482/diy-lab-psu-or-bench-power-supply-what-to-choose
- element14 – Auto Tap Selection experiment: https://community.element14.com/members-area/personalblogs/b/john-wiltrout-s-blog/posts/experimenting-with-auto-tap-selection-for-a-future-power-supply-build
- All About Circuits – Smartkit 0-30V troubleshooting: https://forum.allaboutcircuits.com/threads/smartkit-1138-0-30v-3a-power-supply-troubleshooting.190142/
- All About Circuits – HP E3610A Power Supply Design Logic: https://forum.allaboutcircuits.com/threads/hp-e3610a-power-supply-design-logic.186813/
- All About Circuits – Heating problem in LM317: https://forum.allaboutcircuits.com/threads/heating-problem-in-lm317.123245/
- Electronics-Lab – New Power Supply II: https://www.electronics-lab.com/forums/threads/new-power-supply-ii.311133/
- diyAudio – Unregulated PSU (picos de carga por la masa de referencia): https://www.diyaudio.com/community/threads/my-first-ever-pcb-board-unregulated-psu-for-a-two-gainclones.57984
- diyAudio – Problems with my power supply (LM317HV 0–50 V): https://www.diyaudio.com/community/threads/problems-with-my-power-supply.35105

### Diseños, artículos y revistas
- ESP Project 223 (Rod Elliott): https://sound-au.com/project223.htm
- ESP – Bench Power Supplies, Buy or Build?: https://sound-au.com/articles/bench-supply.htm
- ESP – Power Supply Pre-Regulator Techniques: https://sound-au.com/articles/preregulators.htm
- Silicon Chip – 40V Switchmode/Linear Bench Supply (2014): https://www.siliconchip.com.au/Issue/2014/May/40V+Switchmode-Linear+Bench+Power+Supply%2C+Pt.2
- Silicon Chip – 45V 8A Bench Power Supply (2019): https://www.siliconchip.com.au/Issue/2019/October/45V%2C+8A+Bench+Power+Supply+to+build
- Silicon Chip – 30V 2A Bench Supply, Part 1 (2022): https://siliconchip.com.au/Issue/2022/October/30V+2A+Bench+Supply%2C+Part+1
- National LB-28 – General Purpose Power Supply: https://xdevs.com/doc/_Magazines/LB-28.pdf
- Analog Devices – High Performance Portable DC Bench Power Supply: https://www.analog.com/en/resources/technical-articles/high-performance-portable-dc-bench-power-supply.html
- Analog Devices – Control Loop Simulation Done the Easy Way: https://www.analog.com/en/resources/technical-articles/control-loop-simulation-done-the-easy-way.html
- G. Jolley – Benchtop linear power supply: https://gregjolley.github.io/media/JolleyGS_design_low_noise_high_performance_linear_power_supply.pdf
- Frank Wiedmann – Loop gain simulation (LTspice): https://sites.google.com/site/frankwiedmann/loopgain
- Blog de JuanGg – Linear lab power supply: https://juangg-projects.blogspot.com/2019/05/linear-lab-power-supply.html
- GitHub de JuanGg (esquemas, PCB, firmware): https://github.com/Juan-Gg/Linear-lab-bench-power-supply/tree/master
- Electronic Design – The Spirito Effect: https://www.electronicdesign.com/technologies/power/article/21795492/the-spirito-effect-improved-my-designand-i-didnt-even-know-it
- Maxim AN2997 – Layout de reguladores: https://www.scribd.com/document/489646010/AN2997
- All About Circuits – Low-side current sensing: layout tips: https://www.allaboutcircuits.com/technical-articles/using-single-ended-amplifiers-in-low-side-current-sensing-error-sources-and-layout-tips/
- Digi-Key – LM317 Design Guide: https://forum.digikey.com/t/lm317-voltage-regulator-design-guide-output-equation-common-pitfalls-and-practical-tips/61877

### Manuales y datasheets
- Manual de servicio HP/Agilent E3620A: https://xdevs.com/doc/HP_Agilent_Keysight/HP%20E3620A%20Operating%20%26%20Service.pdf
- Manual HP/Agilent E3610A–E3612A: https://www.ecb.torontomu.ca/guides/instrument-manuals/Agilent-HP_E3611A_User.pdf
- onsemi – Datasheet LM317: https://www.onsemi.com/download/data-sheet/pdf/lm317-d.pdf
- TI – Datasheet LM317: https://www.ti.com/lit/ds/symlink/lm317.pdf
- TI – Datasheet LM317HV: https://www.ti.com/document-viewer/LM317HV/datasheet/specifications
- TI – INA282: https://www.ti.com/product/INA282

## B. Otras páginas consultadas o encontradas durante la investigación (no citadas en las respuestas)

### Leídas durante la investigación
- EEVblog – LM324 Power Supply (pág. 1): https://eevblog.com/forum/beginners/lm324-power-supply-with-variable-voltage-and-current
- EEVblog – how to design fast bench supply with CC and CV: https://eevblog.com/forum/projects/how-to-design-fast-bench-supply-with-cc-and-cv
- Electro-Tech-Online – Linear power supplies: theory and circuits: https://electro-tech-online.com/articles/linear-power-supplies-theory-circuits.794
- Electronics-Lab – 0-30V 0-3A Latest Data: https://www.electronics-lab.com/forums/threads/0-30v-0-3a-latest-data.311066/page-4
- Circuits Online – Ontwikkeling van de NA-01 Lab Voeding (Blackdog, neerlandés): https://www.circuitsonline.net/forum/view/110029
- TI – LM317HV (página de producto): https://www.ti.com/product/lm317hv
- Ayuda de Claude – Cowork en Pro/Max/Ultra (Download task data, /port-task-data): https://support.claude.com/en/articles/15520349
- Claude Code – Use Claude Code on the web (teleport): https://code.claude.com/docs/en/claude-code-on-the-web

### Encontradas en búsquedas y usadas como contexto
- EEVblog – 0-70V, 0-5A Lab Power Supply Design (tomas): https://eevblog.com/forum/projects/0-70v-0-5a-lab-power-supply-design
- EEVblog – psu tap switching question (Mastech HY-3020): https://www.eevblog.com/forum/beginners/psu-tap-swiping-question/
- EEVblog – DIY 0-30V 0-3A ...Again: https://eevblog.com/forum/beginners/diy-0-30v-0-3a-again
- EEVblog – Banggood PSU Enhancements: https://www.eevblog.com/forum/beginners/bangood-psu-enhancements/msg1203475/
- EEVblog – EEVblog #1265 $53 360W Lab Bench PSU (RD6006): https://eevblog.com/forum/blog/eevblog-1265-$53-360w-lab-bench-psu!/msg2804540
- EEVblog – PSU Constant Current response timing comparison: https://eevblog.com/forum/testgear/psu-constant-current-response-timing-comparison/msg4904153
- EEVblog – fast CC/CV power supply take two: https://www.eevblog.com/forum/projects/fast-cccv-power-supply-take-two
- EEVblog – Voltage regulator in current feedback topology: https://eevblog.com/forum/projects/voltage-regulator-in-current-feedback-topology/msg5095815
- EEVblog – Very Low Noise Preregulator for Benchtop Power Supply: https://eevblog.com/forum/projects/very-low-noise-preregulator-for-benchtop-power-supply
- EEVblog – Simplistic Pre-Regulator (zero crossing): https://eevblog.com/forum/projects/simplistic-pre-regulator-(tracking-mains-zero-crossing-detecting)
- EEVblog – Any good examples of using a switching regulator as a preregulator for an LDO?: https://www.eevblog.com/forum/projects/any-good-examples-of-using-a-switching-regulator-as-a-preregulator-for-an-ldo/
- EEVblog #222 – Lab Power Supply Design Part 2: https://www.eevblog.com/2011/11/29/eevblog-222-lab-power-supply-design-part-2/
- Electro-Tech-Online – LM723 PSU with 0V lowest voltage (tomas): https://electro-tech-online.com/threads/lm723-psu-with-0v-lowest-voltage.148899
- Keysight (Watt's Up blog) – Early power supply SCR preregulator: https://wattsup-powersupply.blogspot.com/2013/05/more-on-early-power-supply-preregulator.html
- Circuit Cellar – Thyristor Preregulator: https://circuitcellar.com/resources/quickbits/thyristor-preregulator/
- hackaday.io – EEZ SMPS pre-regulator: https://hackaday.io/project/9491-diy-programmable-scpi-bench-power-supply/log/37418-smps-pre-regulator-is-assembled-and-tested
- Hackster – DIY Programmable SCPI Bench Power Supply (EEZ): https://www.hackster.io/prasimix/diy-programmable-scpi-bench-power-supply-5e59d5
- Analog Devices – CN-0508 (buck + 2×LT3081): https://www.analog.com/en/resources/reference-designs/circuits-from-the-lab/cn0508.html
- Silicon Chip – Programmable Hybrid Lab Supply with WiFi (2021): https://siliconchip.com.au/Issue/2021/May/Programmable+Hybrid+Lab+Supply+with+WiFi+%E2%80%93+Part+1
- Elektor – Professional lab power supply: https://www.elektormagazine.com/news/circuit-professional-lab-power-supply
- fcerbell – Linear Bench Power Supply 30V 3A (LM723): https://fcerbell.github.io/LinearBenchPowerSupply30V3A
- EEPower – Understanding linear MOSFETs: https://eepower.com/technical-articles/understanding-linear-mosfets-and-their-applications/

