# Medir la estabilidad térmica del 40W

La pregunta es una sola: **¿qué le pasa a la corriente de reposo de la etapa
de salida cuando el amplificador se calienta?** Hay tres respuestas posibles y
sólo una es peligrosa.

| lo que hace el reposo | qué significa |
|---|---|
| **sube y no para** | compensación insuficiente → embalamiento térmico. Destruye transistores. |
| sube y se estabiliza | compensación justa. Vigilar, pero vive. |
| **baja** | sobrecompensación. Seguro, pero gana distorsión de cruce en caliente. |

Este amplificador está en el tercer caso, y eso ya se sabe: medido en el
banco, el reposo cae de **40 mA en frío a unos 15 mA en caliente**. O sea que
no hay riesgo de embalamiento. Lo que hay que medir es **cuánto** cae, cuánto
tarda, y qué cuesta en distorsión.

---

## Lo que predice el modelo

LTspice no simula autocalentamiento, pero sí admite `temp=` por instancia, así
que se puede poner a temperatura sólo lo que está atornillado al disipador
(Q3, Q4, Q5, Q6, Q7) y dejar D10 al aire, que es la situación real:

```
                     D10 AL AIRE (como está)    D10 EN EL DISIPADOR
  T disipador      R16        R17                R16        R17
      25 C        46.5 mA    56.6 mA            44.7 mA    54.8 mA
      40 C        30.9       40.1               41.2       50.7
      55 C        19.2       27.4               38.4       47.2
      70 C        11.3       18.7               36.2       44.4
      85 C         6.7       13.0               34.6       42.2
```

Dos cosas salen de ahí:

1. **Con D10 al aire el reposo se desploma**: de 46 a 11 mA entre 25 y 70 °C.
   Concuerda con los 40 → 15 mA medidos, así que el modelo captura el efecto.
2. **Atornillar D10 al disipador lo arreglaría casi del todo**: 36 mA a 70 °C
   en vez de 11. La caída pasa del 76 % al 19 %.

El punto medio no se mueve con la temperatura (25,70 → 25,71 V), así que esto
es un asunto de reposo y de distorsión de cruce, no de recorte.

Las medidas de abajo sirven para confirmar o desmentir esta predicción.

---

## 1. Material

- Multímetro con escala de 200 mV (40 mA por 0,5 Ω son 20 mV).
- Termómetro: termopar tipo K o un infrarrojo. Si es infrarrojo, pega un
  trocito de cinta aislante mate en el disipador y apunta ahí, que el aluminio
  pulido engaña a los IR.
- Resistencia de 8 Ω / 100 W y generador, como en las pruebas de estabilidad.
- Un cronómetro.

## 2. Cómo se lee el reposo

Sin señal, la corriente por **R16** (0,5 Ω, entre Q6E y PRE_SPEAKER) y por
**R17** (0,5 Ω, entre PRE_SPEAKER y Q7C) es la de reposo de cada mitad:

```
I = V_medida / 0,5     →     20 mV = 40 mA
```

**Mide las dos, no sólo una.** No son iguales: parte de la corriente se cuela
por R14 (56 Ω de la base de Q6 a la salida) sin pasar por R16, así que R17
lee entre 8 y 10 mA más. El modelo lo reproduce.

Es una medida flotante —ninguno de los dos extremos está a masa—, así que el
multímetro de mano va perfecto.

## 3. Prueba A — curva de calentamiento desde frío

La fundamental.

```
amplificador  frío de verdad: apagado varias horas
entrada       jack cortocircuitado, SIN señal
carga         resistencia de 8 Ω conectada
```

Enciendes y anotas, **cada minuto durante los primeros 10 y luego cada cinco
hasta los 45**:

- tensión en R16 y en R17
- temperatura del disipador
- temperatura ambiente

Sin señal el aparato disipa poco, así que esto te da la deriva térmica propia
del reposo, que es la más lenta y la que marca el punto de partida.

## 4. Prueba B — la prueba de verdad: después de potencia

Esta es la que distingue un amplificador sano de uno que se va a romper, y es
la que **no** se hace sólo con el aparato en reposo.

```
1. Desde el estado estabilizado de la prueba A, mete seno de 1 kHz
   y ajusta hasta leer 27 Vpp en la carga (9,7 Vrms, 11,7 W).

   ¿Por qué ahí y no a tope? Porque es donde los transistores de salida
   más disipan: 13,2 W de calor con sólo 11,7 W llegando a la carga.
   A plena potencia disipan MENOS de 5 W. El peor caso térmico está a
   volumen intermedio, no a tope.

   El máximo es plano, así que no hace falta clavarlo: entre 22 y 33 Vpp
   la pareja sigue por encima de 12,5 W.

     22 Vpp ( 7,7 W al altavoz)  ->  12,8 W de calor
     27 Vpp (11,7 W)             ->  13,2 W   <- el peor caso
     33 Vpp (16,5 W)             ->  12,6 W
     42 Vpp (22,1 W)             ->  11,0 W

   Coincide con la teoría de clase B: con 23,5 V de riel por lado sobre
   8 ohm, el maximo cae en V_pico = 2·Vcc/pi = 15,0 V (29,9 Vpp) y
   P = Vcc²/(pi²·R) = 7,0 W por transistor.  El modelo da 6,4 y 6,8 W
   a 27,4 Vpp; la diferencia es el riel, que en la teoría es fijo y aquí
   cae a 47 V bajo carga.

2. Déjalo así 15-20 minutos, vigilando la temperatura del disipador.

3. QUITA LA SEÑAL de golpe y mira el reposo INMEDIATAMENTE,
   anotándolo cada 10 segundos durante los dos primeros minutos.
```

El paso 3 es el crítico. Justo al quitar la señal las uniones están calientes
pero el disipador va por detrás; si el reposo **salta hacia arriba** en esos
primeros segundos, ahí tienes la firma del embalamiento, aunque luego se
calme. Si baja o se queda, estás en el caso seguro.

> ⚠️ No lo dejes solo. Si el reposo empieza a subir sin parar, apaga.

## 5. Prueba C — resistencia térmica real del disipador

Aprovechando la prueba B: con los 12 W de salida, los transistores disipan
unos 13 W. Anota la temperatura del disipador estabilizada y la ambiente:

```
Rth = (T_disipador - T_ambiente) / 13 W
```

Estimaste 2 °C/W por la geometría. Si sale cerca, tu estimación era buena; si
sale bastante más, es que el montaje (aislantes, pasta, flujo de aire) está
pesando más de lo previsto, y eso es un resultado publicable por sí solo.

## 6. Prueba D — qué cuesta en distorsión

El reposo cayendo de 40 a 15 mA significa más distorsión de cruce. Para
ponerle número:

```
1. En frío, seno de 1 kHz a BAJA potencia (1 W, unos 2,8 Vrms).
   Mide la THD, o si no tienes medidor, mira el cruce por cero con el
   osciloscopio en alterna y mucha sensibilidad vertical, y fotografíalo.

2. Repite exactamente igual después de la prueba B, con el aparato caliente.

3. Compara.
```

A baja potencia es donde la distorsión de cruce manda; a potencia alta queda
tapada. Por eso 1 W y no más.

## 7. Prueba E — opcional: el experimento de D10

Si quieres cerrar el asunto que ya mencionas en el artículo: atornilla D10 al
disipador —o simplemente pégalo con un poco de pasta térmica y cinta, que para
una prueba basta— y repite las pruebas A y B.

El modelo dice que el reposo en caliente debería subir de ~11 a ~36 mA. Es una
predicción falsable y barata de comprobar, y si sale, tienes un hallazgo de
diseño con medida antes y después.

## 8. Hoja de resultados

```
PRUEBA A — calentamiento en reposo

  min    R16 (mV)   R17 (mV)   T disip.   T amb.
   0      ______     ______     ______    ______
   1      ______     ______     ______
   2      ______     ______     ______
   5      ______     ______     ______
  10      ______     ______     ______
  20      ______     ______     ______
  30      ______     ______     ______
  45      ______     ______     ______

PRUEBA B — después de 15-20 min a ~12 W

  seg    R16 (mV)   R17 (mV)   T disip.
   0      ______     ______     ______
  10      ______     ______
  30      ______     ______
  60      ______     ______
 120      ______     ______

  [ ] el reposo NO sube al quitar la señal   -> seguro
  [ ] el reposo SUBE al quitar la señal      -> revisar la compensación

PRUEBA C — Rth = (____ - ____) / 13 W = ____ °C/W   (estimado: 2)

PRUEBA D — distorsión de cruce a 1 W
  frío:      THD ____ %     caliente: THD ____ %

PRUEBA E — D10 en el disipador (opcional)
  reposo en caliente, antes: ____ mA     después: ____ mA
  (el modelo predice ~11 mA -> ~36 mA)
```
