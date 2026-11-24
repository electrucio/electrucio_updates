# Material de contexto del `psu_cvcc`

Lo que había **antes** del diseño: la investigación de la que salió. No es
documentación del circuito —eso está en [`../README.md`](../README.md)— sino el
rastro de cómo se llegó a él, para no volver a recorrer caminos ya descartados.
Aquí están también las referencias que no se pueden versionar, con lo que hace
falta para conseguirlas.

## El artículo de Silicon Chip — *no está en el repo*

«45 V, 8 A Bench Power Supply to build», *Silicon Chip*, octubre de 2019,
29 páginas:
<https://www.siliconchip.com.au/Issue/2019/October/45V%2C+8A+Bench+Power+Supply+to+build>

Es una de las **tres referencias primarias** del diseño, junto con el datasheet
TI SNVS773D y el [ESP Project 223](https://sound-au.com/project223.htm); de ella
salen el divisor que vuelve al borne, el `Cadj` referido al raíl negativo, el
`Qcc` contra −5 V, los 100 nF en paralelo con `Cout` y la elección de BC546. La
tabla de [`../README.md`](../README.md) dice qué detalle sale de dónde.

El PDF es de pago y lleva marca de agua con los datos del comprador, así que
está en el `.gitignore`: se compra en la web de la revista y se deja en
`docs/silicon_chip_45v_8a.pdf`, que es la ruta que el `.gitignore` espera.
Mientras tanto, **el README de arriba es autosuficiente**: cita cada detalle
que se tomó del artículo y por qué lo hacen ellos, sin necesidad de abrirlo.

## `chats/handoff_fuente_laboratorio.md`

Sesión de investigación del 23–24 de noviembre de 2026 (Claude Cowork): 14
mensajes, con resumen estructurado, transcripción completa y un índice de ~60
enlaces (hilos de EEVblog, element14, diyAudio, artículos de ESP y Silicon
Chip, el PDF de Greg Jolley, el GitHub de JuanGg). **El índice de enlaces de la
Parte 3 es lo más reutilizable del fichero.**

Lo que ya estaba decidido ahí y sigue en pie:

- lineal pura, nada de conmutada ni híbrida;
- LM317 / LM317HV como elemento de paso, con el diseño ajustado a lo que el
  encapsulado puede disipar (10–11 W sostenidos en TO-220, no los 20 W de Rod
  Elliott);
- **tomas en el transformador** para repartir ese calor, con la tabla de
  corriente máxima según número de tomas;
- límite de corriente ajustable con potenciómetro, no por rangos fijos.

Y en qué se separó el diseño final de lo que proponía el handoff:

| el handoff proponía | `psu_cvcc` hace |
|---|---|
| rango V/I sin fijar | 0 – 40,5 V, límite 80 mA – 1,34 A |
| partir del P223 y modificarlo | diseño desde cero sobre los circuitos de aplicación del datasheet; del P223 solo quedan la referencia de −1,25 V con LM337 y el trimmer de fondo de escala |
| dos canales de 0–25 V, en serie para 50 V | un canal, LM317HV, 3 tomas con rotativo 1P3T |
| INA282 + operacional + 2N7000 a ADJ | shunt de 0,33 Ω en el retorno + LM358 + BC546, que son las figuras 31 y 32 del datasheet; el TL431 pone la consigna |
| limitador en la entrada del regulador (como el P223) | limitador en el retorno de la salida |
| conmutar tomas con relés y comparador | selección manual, break-before-make |

Los «siguientes pasos» 3 y 4 de su Parte 1 (capturar el esquema y simularlo)
son exactamente lo que son `psu_cvcc.asc` y la sección «Medido en simulación»
del README.

## `chats/chat_lm317_cv_cc.txt`

Conversación anterior, la que abre el tema: si el LM317 puede regular tensión y
corriente a la vez, por qué en los foros dicen que es difícil y qué recomiendan
en su lugar. Conserva valor por el problema que plantea —el potenciómetro de
ajuste llevando toda la corriente de la carga— que es justo lo que resuelven
las figuras 31 y 32 del datasheet y lo que mide la sección «El pote de corriente
no lleva nada; el de tensión sí» del README.

El resto de su contenido está **superado**: da por hecho que haría falta un
potenciómetro bobinado de potencia, habla de poner dos LM317 en cascada
(perdiendo 6–7 V) y acaba recomendando o el clásico 0-30V/0-3A discreto, o un
LM723, o comprar un módulo RuiDeng. Ninguna de las tres es el camino que se
siguió.
