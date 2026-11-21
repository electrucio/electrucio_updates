# Simular LTspice desde la línea de comandos (macOS)

Herramientas para simular en batch, sin abrir la GUI, y post-procesar los
resultados con numpy. Pensado para que cualquier sesión nueva (o cualquier
chat) pueda reproducir las medidas sin tener que redescubrir las trampas.

```
tools/ltspice/
├── rawread.py      lector de ficheros .raw (binarios, .tran y .ac)
├── ltrun.py        preparar un netlist y lanzar LTspice en batch
├── asc2net.py      netlistar un .asc sin abrir la GUI
├── asc2svg.py      dibujar un .asc en SVG, para revisar la disposición
├── mkasc_psu_cvcc.py    generar psu_cvcc.asc con una disposición de lectura
├── simplify_psu.py      derivar psu_simple.net podando psu.net
├── verify_psu.py   suite de verificación de powersupply/psu_overengineered/psu.asc
├── verify_psu_cvcc.py   ídem de powersupply/psu_cvcc/
├── verify_tone_ac.py    barrido AC del 40W: respuesta vs bass/treble
├── plot_tone_ac.py      la figura de ese barrido (PNG + SVG + JSON)
├── verify_amp_tran.py   caracterización del 40W en el dominio del tiempo
├── render_audio.py      pasar un WAV de guitarra por el amplificador simulado
├── svgplot.py           primitivos de dibujo en SVG + rasterizado con Chrome
└── README.md
```

Requisitos: LTspice 17.2.4 para macOS en `/Applications/LTspice.app`
(o `export LTSPICE=/ruta/al/binario`), Python 3 con `numpy`, y `matplotlib`
solo si usas `--plot`.

## Arranque rápido

```bash
# 1) suite completa de la fuente (~50 s, 8 simulaciones)
python3 tools/ltspice/verify_psu.py

# 2) un caso concreto, conservando netlists/raws y con gráficas
python3 tools/ltspice/verify_psu.py --only thermal --workdir /tmp/psu --plot --keep

# 3) simular un netlist cualquiera y listar sus variables
python3 tools/ltspice/ltrun.py powersupply/psu_overengineered/psu.net /tmp/mi_sim
```

## Las trece trampas

Todas están ya resueltas dentro de `ltrun.py`, pero conviene conocerlas:

1. **El netlist va como último argumento.** `LTspice -ascii -b f.net` funciona;
   `LTspice -b -ascii f.net` falla con `Can't find input deck "-ascii"`.
2. **Hay que desactivar el sandbox del shell.** Sandboxeado el proceso muere con
   exit 144 y no escribe ni el `.log`. Con Claude Code: `dangerouslyDisableSandbox`.
3. **`-b` solo traga netlists, no `.asc`.** Este build trata cualquier fichero
   como netlist y muere con `Fatal Error: Multiple instances of "Flag"`.
   Para obtener el `.net`: `File > Export Netlist` en la GUI, o
   `LTspice -netlist psu.asc` (ojo: sobrescribe `psu.net` si ya existe).
4. **Los `.lib` relativos no se resuelven.** La GUI busca en
   `~/Library/Application Support/LTspice/lib/{sub,cmp}/`; el CLI no.
   `Netlist.absolutize_libs()` los convierte a ruta absoluta.
5. **Los netlists y logs salen en UTF-16LE**, y los exportados por la GUI llevan
   caracteres no-ASCII (`0.33µ`, `R§F1`) que rompen cualquier cadena de
   herramientas de texto. `Netlist.from_file()` detecta la codificación y
   translitera (`µ`→`u`, `R§F1`→`RF1`); para leer un `.log` a mano:
   `iconv -f UTF-16LE -t UTF-8 psu.log`.

6. **Un `.ac` necesita un `.op` que valga.** Si el raíl del circuito sale de la
   red en vez de una fuente, el `.op` nativo NO sirve: en DC una `SINE(0 325 50)`
   **vale 0 V**, así que `.ac` lineariza un amplificador apagado y todo el barrido
   sale sin sentido. Se arregla añadiendo una fuente DC en el nodo del raíl —
   adición pura, no hay que quitar la cadena de red: en DC es inerte y en AC la
   fuente de red no lleva especificación `AC`, o sea que es un corto a masa.
   `uic` **no** es una salida: es solo para `.tran`. Ver
   `verify_tone_ac.py`, que hace exactamente esto sobre el 40W.

7. **Con `tstart`, LTspice guarda el tiempo RELATIVO a él** y pone el
   desplazamiento en `Offset:` de la cabecera del `.raw`. Un
   `.tran 0 4.6 3.75 20u` devuelve tiempos de 0 a 0.85: si no sumas el offset,
   cualquier medida en tiempo absoluto sale desplazada **en silencio**.
   `read_raw()` ya lo suma; era un fallo suyo hasta 2026-08-27.
8. **Nada de medias, RMS ni FFT sobre las muestras crudas de un `.tran`.**
   Están muestreadas de forma **no uniforme**: LTspice concentra puntos donde
   la señal cambia deprisa, así que un `np.mean` o un
   `sqrt(mean(y**2))` sobre ellas pesa de más esas zonas y el resultado depende
   de cómo haya convergido el paso, no de la señal. Con esto medí potencias
   **no monótonas** —620 mV de entrada daban menos potencia que 500— hasta que
   comparé con el valor teórico de una senoide conocida: 14.26 V medidos contra
   14.264 V esperados una vez remuestreado. `uniform()` en `verify_amp_tran.py`
   hace el remuestreo; `harmonics()` y `spectrum()` ya lo llevan dentro.
9. **El suelo de THD lo pone `reltol`.** Medido sobre una salida en clase A
   pura (distorsión real ≈ 0): con el `reltol` por defecto el suelo es
   **0.038 %**, y con `.options reltol=1e-5 vntol=1e-6 abstol=1e-12` baja a
   **0.0038 %**. Cambiar el número de puntos de la FFT de 1024 a 32768, o el
   paso máximo de 1 µs a 0.2 µs, **no mueve nada**. Por debajo de ~0.01 % no
   hay que creerse ningún número.

10. **Una senoide NO predice lo que hace una guitarra.** Es la trampa más cara
    de todas, porque no falla: da un número correcto de otra cosa. Una senoide
    tiene **3 dB** de factor de cresta y una grabación de guitarra **18 dB**, así
    que al mismo pico la guitarra tiene **~15 dB menos de RMS**. Medido sobre
    `dry_guitar_44100_selection.wav`: a "150 mVp" la senoide da 106 mV de RMS y
    la guitarra 21.6 mV. Consecuencia práctica: un recortador de diodos que con
    senoide de 300 mVp da 0.7 % de THD, con guitarra de 300 mVp de pico solo
    conduce el **2.4 % del tiempo**. Si el objetivo es un nivel realista, hay
    que fijar un **percentil de picos locales** (`.param in_amplitude` documenta
    150 mVp de P90), no el pico absoluto: para el corte citado eso son 174 mVp
    de pico absoluto, ganancia 0.537.
11. **`.wave` recorta a ±1 V.** Es formato WAV: fondo de escala es 1.0.
    Verificado con una senoide de 5 V, que sale a 1.000 pelada. Para escribir la
    salida de un amplificador de ±22 V hay que dividir con una fuente
    behavioural antes (`B_WOUT WOUT 0 V=V(SPEAKER)/32`) y multiplicar de vuelta
    al leer. Sin eso el WAV es un cuadrado perfecto y parece que el circuito
    distorsiona muchísimo. Ver `render_audio.py`.
12. **El recorte de abajo tapa el carácter de arriba.** Con dos etapas no
    lineales en serie, medir la de arriba con la de abajo saturada da la
    diferencia equivocada. Medido en el 40W con senoide de 320 mVp, comparando
    el retorno del recortador a masa contra el retorno por bias:

    | `vol` | pico/techo | bias − gnd | sin diodos − gnd |
    |---|---|---|---|
    | 0.30 – 0.70 | 3 – 45 % | **+2.76 dB** | **+5.37 dB** |
    | 0.85 | 86 % | +2.60 | +4.22 |
    | 1.00 | 101 % | **+1.04** | **+1.49** |

    La diferencia es constante hasta que el pico alcanza el techo del raíl, y
    ahí se derrumba a un tercio. O sea que **el master por encima de 0.85 borra
    el recorrido del preamp entero**. Para caracterizar el preamp hay que
    dejarle margen a la etapa de potencia; para caracterizar la etapa de
    potencia, inyectar en serie con `C1` (`inject_power_stage()`).
13. **Los nombres de nodo del `.net` siguen al `.asc`, y cambian sin avisar.**
    El 2026-08-27 el esquemático pasó de `D6 N022 0` a `D6 N019 N024` al añadir
    el mod de bias (`C35`/`C36` de 10 µF y `R41`/`R63` de 2k2). Cualquier script
    que parchee el recortador por nombre de nodo mide el circuito equivocado, o
    peor: un modo que "no parchea nada" (el `gnd` de `verify_amp_tran.py`)
    cambia de significado en silencio, porque "tal como está dibujado" ya no es
    lo mismo. Los tres modos son ahora parches **explícitos**, y `Netlist.patch`
    casca a gritos si no encuentra el texto. Es la única defensa.

Extra: **la primera línea de un netlist SPICE es el título**, no una instrucción.
Si escribes uno a mano, empieza con un comentario `*` o perderás el primer
componente. Y si un netlist depende de un estímulo con rampa lenta, sustituirlo
por una fuente DC puede reventar la convergencia
(`Time step too small; initial timepoint`): usa `PWL` en vez de un valor fijo.

## Recetas

### Parchear un netlist sin cambios silenciosos

`patch()` revienta si el texto no aparece exactamente el número de veces
esperado, así que un cambio en el esquemático se nota inmediatamente en vez de
aplicarse a medias:

```python
from ltrun import Netlist, run_batch
from rawread import read_raw

n = Netlist.from_file("powersupply/psu_overengineered/psu.net").absolutize_libs()
n.patch(".tran 0 7 0 2m startup", ".tran 0 0.8 0 20u startup")
n.patch("V4 load 0 PULSE(70 25 0.3 100u 100u 0.3 0.6 10)", "V4 load 0 25")
n.save_vars("V(vload) V(vraw+)", "I(RLOAD) I(R22)")     # + plotwinsize=0

raw = run_batch(n.write("/tmp/sim/prueba.net"))
names, d = read_raw(raw)
t, vout = d["time"], d["V(vload)"]
```

### Mantener los `.raw` pequeños

Sin `.save` y sin paso máximo, un `.tran 0 8` de la fuente genera **210 MB** y
tarda 30 s. Con `.save` de los nodos que interesan, `.options plotwinsize=0` y
un paso máximo razonable baja a 2–3 MB y 3 s. `save_vars()` pone las dos cosas.

Cuidado con el paso máximo: con `2m` el rizado de 100 Hz queda *aliaseado*
(5 puntos por ciclo). Para medir rizado o margen de dropout hace falta `20u`.

### Barridos de un valor

El parser no lee raws escalonados (`.step`), así que en vez de eso se generan N
netlists y se comparan:

```python
for r28 in (10, 22, 47):
    n = Netlist.from_file(PSU_NET).absolutize_libs()
    n.patch("R28 N021 PASS_IN 10", f"R28 N021 PASS_IN {r28}").save_vars(...)
    d = read_raw(run_batch(n.write(work / f"r28_{r28}.net")))[1]
```

### Barrido AC de dos parámetros

`read_raw()` **ya lee raws de `.ac`**: detecta `Flags: complex` y devuelve
`np.complex128`, así que una sola corrida da todos los nodos como fasores y de
ahí salen todas las funciones de transferencia que quieras sin volver a simular.

Con `AC 1` en la fuente de entrada, `V(entrada) ≡ 1` y **el nodo de salida *es*
la función de transferencia**: no hay que dividir por nada.

```python
n = Netlist.from_file(NET).absolutize_libs()
n.add(".param vraw=48.88", "V_RAW N002 0 {vraw}")          # el rail (ver trampa 6)
n.patch(VSRC, VSRC + " AC 1")
n.patch(".tran {step} {t_stop} {t_start} {step}", ".ac dec 100 10 100k")
n.drop_re(r"\s*\.meas\s+tran\b", 80)                      # no aplican a un .ac
n.drop_re(r"\s*\.four\b", 7)
```

Un `.ac` de este amplificador (132 componentes, 401 puntos de frecuencia) tarda
**0.02 s**, contra los 64 s del `.tran` de 4.2 s. Las 31 corridas de
`verify_tone_ac.py` son 2.4 s en total, así que aquí no hace falta ni pensar en
optimizar: N netlists y a correr.

Y hay que **cruzar el `.ac` con el `.tran`**: a la frecuencia de la senoide del
transitorio los dos análisis tienen que dar la misma ganancia. En el 40W cuadran
al 0.02 %, y eso es lo que permite fiarse del resto del barrido.

Ojo: `.ac` es **pequeña señal**. Los recortadores de diodos se linearizan (en
reposo están en corte, no molestan), pero un `.ac` no dice nada del carácter de
recorte. Para eso, `.tran`.

### `.meas` vs post-proceso

Para un número suelto, `.meas` es más corto y sale en el `.log`
(`.meas TRAN vout_pp PP V(out) FROM 4m TO 5m` — sin `FROM/TO` incluye el
transitorio de arranque y la medida no vale). Para lo demás —mínimos en ventana
deslizante, integrar tiempo por encima de un umbral, contar transiciones de
relé, KCL en un nodo, RMS en ventana— sale antes con numpy sobre el `.raw`.

## La suite transitoria del 40W: `verify_amp_tran.py`

Lo que el `.ac` no puede ver: recorte, distorsión, estabilidad y sag. Cinco
casos, **90 s la suite entera**.

```bash
python3 tools/ltspice/verify_amp_tran.py --plot -o /tmp/fig
python3 tools/ltspice/verify_amp_tran.py --only trim
python3 tools/ltspice/verify_amp_tran.py --as-drawn      # sin ajustar
```

**`trim` corre siempre primero y los demás casos usan los cursores que
resuelve.** Caracterizar la distorsión de un amplificador mal polarizado no
mide el diseño, mide el error de ajuste.

### Lo que hace viable la suite

El `.tran` del esquemático tarda **64 s** porque espera hasta `t = 4 s`: el raíl
sale de la red y en DC una `SINE(0 325 50)` vale 0 V. Con la misma fuente `V_RAW`
del barrido AC y `V4` apagada, el `.op` **es** el estado estacionario y el
`.tran` arranca ya polarizado — comprobado: 47 µV de diferencia entre t = 0 y el
`.op`, y 1.25 mV de deriva en 50 ms. **De 64 s a 1-2 s por corrida.**

Para el **sag** y el **zumbido** hace falta la red de verdad (`R22` = 15 Ω de
primario, `C13` de 10000 µF), y ahí sí se pagan los 4 s: son los únicos casos
lentos.

Los trimmers se resuelven por **bisección sobre `.op`**, que cuesta 0.15 s, no
por transitorios. Verificado contra un `.tran` asentado: 0.016 mA de diferencia.

Referencia de lo medido el 2026-08-27:

```
trimmers      tal como esta dibujado: 37.4 mA por R16, +259 mV de offset.
              Los 762 mA de la medida vieja eran SENAL, no reposo.
              Resuelto: RV2 = 0.0358 -> 39.98 mA ; RV1 = 0.5500 -> -0.1 mV
              R16 y R17 difieren ~10 mA: se cuelan por R14 (56 ohm de la base
              de Q6 a la salida) sin pasar por R16.  KCL cierra.
potencia      Depende de DONDE se mida, y la diferencia es enorme:
                etapa de potencia sola (inyectando en serie con C1)
                    34.2 W al 1 % de THD ; 42.3 W al 10 %
                cadena completa, drive 0, rail firme de 50.11 V
                    7.2 W al 1 % ; 15.8 W al 10 %
                cadena completa, fuente REAL, tono sostenido
                    6.9 W al 1 % ; 15.5 W al 10 % ; 20.4 W maximo (44 % THD)
              La diferencia entre 34 W y 7 W es ENTERA del recortador de
              diodos del preamp: el ampli puede dar 34 W limpios, pero el
              preamp no deja pasar mas de 7 W sin recortar.
              Recorte en +22.60/-21.99 V ; asimetria +2.8 % ; rendimiento 61 %
drive         NO cambia el techo: 23.8 W con el pote a 0 y 22.4 W a fondo.
              Solo cambia la entrada necesaria (3.5 V contra 0.35 V) y quien
              recorta.  A fondo da MENOS porque el recortador se come el
              fundamental (la cresta se queda en 1.65-1.86: no llega a
              cuadrada, el recorte es blando y la tone stack lo filtra).
distorsion    THD de fondo 0.026-0.029 % entre 0.17 y 0.69 W.  A partir de
              drive 75 % el que recorta es el PREAMP: TONE_IN 14.8 % y 28.2 %
              contra 20.9 % y 39.0 % en el altavoz.  H2/H3 = 6.3 a drive 0
              (calido), 0.50 al 50 % (aspero), 1.54 al 100 %.
              IMD de dos tonos (82.5 + 1320 Hz, 50 mV cada uno): 0.015 %
estabilidad   slew rate 2.4 V/us ; subida 3.5 us ; sobrepico 0.3 % con carga
              resistiva, 0.7 % con 220 nF y 15.1 % con 2.2 uF, con un rizado
              de 145 kHz.  Sin oscilacion mantenida: estable, con margen
              justo.  OJO: hay que medirlo LEJOS del recorte; con la salida
              cerca del techo el sobrepico salia 2 % en vez de 15 %.
sag           rail 50.11 V en reposo -> 44.63 V al final de una rafaga de
              300 ms a plena potencia.  5.5 V de caida, salida comprimida
              -0.64 dB.  Recuperacion: 82 % en 270 ms, constante ~159 ms.
              Recuperar cuesta mucho mas que caer.
zumbido       100 Hz en el altavoz: 0.465 mV en reposo, 23.1 mV a plena
              potencia (+33.9 dB).  Medirlo en reposo no vale de nada.
```

Cuatro puntos abiertos que salen de aquí:

1. **El "40 W" es real, pero solo en la etapa de potencia.** Inyectando
   directamente en la entrada del ampli, da **34.2 W al 1 % de THD y 42.3 W al
   10 %** sobre 7.5 Ω. La cadena completa da 7.2 W y 15.8 W, y la diferencia es
   entera del recortador de diodos del preamp. Para un ampli de guitarra eso no
   es un defecto —de ahí sale el overdrive—, pero hay que decir cuál de los dos
   números se está dando. *(Corregido: antes decía aquí que el 40 W no existía;
   era consecuencia del RMS sobre muestras crudas de la trampa 8 y de medir a
   través del preamp.)*
2. **`RV2` es inajustable en la práctica**: −11.9 mA por cada 1 % de giro, y
   todo el rango útil (0 a 92 mA) cabe en el 8 % del recorrido, con los 40 mA
   en el 3.6 %. En un trimmer de una vuelta son 13 grados. Habría que reducir
   el pote y meter resistencias fijas para que el margen quede repartido.
3. **15 % de sobrepico con 2.2 µF** y un rizado de 145 kHz. No oscila, pero el
   margen de fase es justo, y encaja con que el amplificador siga plano hasta
   100 kHz.
4. **El raíl real en reposo son 50.11 V**, no los 48.88 V que usa el modo
   banco. Es 0.6 V de techo de recorte que los demás casos no cuentan; se
   corrige con `--vraw 50.11`.

## La suite del 40W: `verify_tone_ac.py`

Barre `bass` y `treble` en `.ac` y saca la respuesta de la tone stack medida
*en sitio* (`V(TONE_OUT)/V(TONE_IN)`, con su impedancia de fuente y su carga
reales) y la del sistema completo (`V(SPEAKER)`, que incluye la resonancia del
pickup).

```bash
python3 tools/ltspice/verify_tone_ac.py                    # todo, ~2.5 s
python3 tools/ltspice/verify_tone_ac.py --only fan_treble --plot
python3 tools/ltspice/verify_tone_ac.py --only matrix --workdir /tmp/tone --keep
```

| caso | qué hace |
|---|---|
| `bias` | vuelca el `.op` con el que se lineariza y lo compara con el punto de operación que midió el `.tran`. **Es la puerta**: si no cuadra, el `.ac` está linearizando otro circuito |
| `crosscheck` | `.ac` contra `.tran` a 1 kHz con los potes al medio |
| `pickup` | separa pickup / amplificador / sistema (ver abajo) |
| `fan_treble` / `fan_bass` | un pote de 0 a 1 con el otro fijo |
| `matrix` | los 5×5, en tres tablas de escalares |

### El pickup se divide, no se quita

En un `.ac` todo es lineal, así que para saber qué parte de la respuesta es el
modelo de pastilla (`V6` → `L7` 2.2 H → `R58` 5.8k → `PICKUP_OUT`, cargado con
~111k y `C34+C32` = 620 pF) basta con **dividir**:

```python
pickup = V(PICKUP_OUT) / V(PICKUP_IN)      # solo la pastilla
amp    = V(SPEAKER)    / V(PICKUP_OUT)     # solo el amplificador
sys    = V(SPEAKER)    / V(PICKUP_IN)      # todo
```

Es mejor que quitarlo del netlist por dos razones: `amp` sale **con la carga del
pickup puesta** (que es la real cuando enchufas una guitarra), y además se ve
cuánto aportaba. Y `stack` es un cociente entre dos nodos que están los dos
detrás del pickup, así que el pickup **no puede** afectarlo: las tablas de
bass/treble no cambian ni un dB.

Cuidado con `corners()`: da la banda a −3 dB **del pico**, y si el pico es una
resonancia (la del pickup, a ~4 kHz), la banda que sale describe la resonancia y
no el circuito. Este amplificador además tiene un hundimiento de 13 dB a 200 Hz
metido dentro de la banda, así que un solo número de «−3 dB» no lo describe.

Referencia de lo medido el 2026-08-26 (`bass=treble=0.5`, `drive=0`, `vol=1`):

```
punto de operacion   rail 48.88 V, punto medio 24.699 V (ideal 24.442) ;
                     coincide con el .tran dentro de 25 mV
1 kHz                stack -10.10 dB, sistema +30.15 dB
                     (el .tran midio 0.3126 y 32.157 -> 0.02 % de error)
pickup               plano de 20 Hz a 1 kHz (-0.5 .. -0.1 dB), +3.9 dB de
                     resonancia a 3890 Hz, y luego cae: -13 dB a 10 k,
                     -26 dB a 20 k.  NO es lo que da forma a la banda de audio.
ampli solo           +25.4 dB a 50 Hz, +17.3 dB a 200 Hz (el notch de la stack),
                     +30.3 dB a 1 kHz, +33.9 dB a 20 kHz Y +33.8 dB A 50 kHz
recorrido de treble  -3.4 dB a 100 Hz, +38.4 dB a 5 kHz.  A treble=0 el ampli
                     rueda de verdad (-2.7 dB a 10 kHz); a treble=1, +40 dB
recorrido de bass    +13.7 dB a 100 Hz, 0.0 dB a 5 kHz (no toca los agudos)
recorrido de drive   +18.6 dB a 1 kHz (XP4, revlog de 1k en el emisor de Q8):
                     +30.3 dB con el pote a cero, +48.9 dB a fondo.  OJO: todas
                     las demas medidas de aqui son con drive=0, que es la
                     ganancia MINIMA.  El recorte de la etapa de potencia
                     (~20.9 Vp con el rail a 48.9 V) llega hacia drive=78 %.
scoop de medios      148-302 Hz segun treble, hasta 22 dB bajo el estante de 5 kHz
interaccion          la stack a 1 kHz va de -36.3 dB (bass=0/treble=0) a
                     -3.8 dB (bass=0/treble=1): los dos controles NO son
                     independientes
```

### La figura

> **El netlist no está versionado.** Igual que `psu_cvcc.net`, el
> `quasimod_guitar_amplifier.net` está en `.gitignore`: en un clon limpio hay que
> exportarlo una vez desde la GUI (`File > Export Netlist`) antes de usar
> `verify_tone_ac.py` o `plot_tone_ac.py`. Aquí **no** vale `asc2net.py`: el
> `.asc` pone varias etiquetas sobre la misma red (`VRAW+` donde el netlist
> exportado dice `Q6C`, `Q12C` donde dice `Q10E`) y cada herramienta elige un
> representante distinto, así que el `--diff` sale lleno de diferencias que solo
> son alias de nodo.

`plot_tone_ac.py` saca la figura de las 25 combinaciones, rotulada en inglés y en
estilo de hoja de características: `V(SPEAKER)/V(PICKUP_OUT)` sobre **7.5 Ω
resistivos**, o sea el amplificador solo, sin pickup y sin el modelo de altavoz.

```bash
python3 tools/ltspice/plot_tone_ac.py -o /tmp/fig     # PNG + SVG + JSON
python3 tools/ltspice/plot_tone_ac.py --scale 4       # PNG mas grande
```

Rasteriza con **Chrome headless**, que es lo único en este equipo capaz de
convertir SVG a PNG (no hay `rsvg-convert`, ni `cairosvg`, ni PIL, ni
matplotlib). De paso, así las IBM Plex salen de Google Fonts aunque no estén
instaladas; sin red, el texto cae al sans/mono del sistema y la figura sigue
siendo válida.

Dos cosas que salieron de aquí y **no** están resueltas en el esquemático:

1. **El amplificador no rueda por arriba**: ganancia plena (+33.8 dB) a 50 kHz.
   Lo único que limita la banda por arriba es el pickup. En un cuasi-complementario
   con `2SD896`/`2SB776` eso es un punto a mirar: margen de fase y filtrado de
   entrada.
2. **No hay pote de medios, y el scoop lo fija `C20`, no `R44`.** Medido
   barriendo cada componente por separado:

   | componente | 100 Ω → 2.2 k / 47 n → 1 µ | efecto |
   |---|---|---|
   | `R44` (100 Ω) | 100 → 2200 Ω | **0.02 dB.** Irrelevante |
   | `R45` (47 Ω) | 47 → 4700 Ω | +3.8 dB a 1 kHz, scoop igual |
   | `C20` (470 n) | 47 n → 1 µ | **scoop de 0 a 22.6 dB**, notch ∅ → 146 Hz |
   | `R43` (10 k) | 2.2 k → 22 k | ±5 dB a 100 Hz, notch 315 → 152 Hz |

   O sea que el elemento de medios de esta stack es un **condensador** a masa
   (`C20`, desde el nodo que une el extremo del pote de agudos con el cursor de
   graves), no la resistencia de mid de una FMV clásica. `R44` queda enmascarada
   porque la rama de `C20` shunta en paralelo con ella y domina.

   Consecuencia práctica: **cambiar `R44` no da un control de medios.** Un pote
   en serie con `C20` solo compra +2.6 dB a 1 kHz y 3.2 dB menos de scoop
   (medido, 0 → 2.2 k), porque la rama del pote de graves hacia `R44` sigue
   shuntando. Lo que sí voltea el carácter es el **valor de `C20`**: 150 n / 470 n
   / 1 µ en un conmutador rotativo dan tres voces útiles sin ningún pote.

3. **El pote de agudos funciona como control de volumen.** Con los agudos a
   cero el nivel de 1 kHz se cae **23.8 dB**: no es «menos agudos», es «mucho
   más bajo», y deja el mando inútil por debajo del 25 %. Pasa porque con el
   cursor abajo la salida se apoya justo encima del shunt de `C20`. `R45` es el
   suelo, y subirlo lo arregla:

   | `R45` | treble=0 | treble=100 % | recorrido |
   |---|---|---|---|
   | 47 Ω (actual) | +12.4 dB | +36.2 dB | 23.8 dB |
   | 1 k | +16.4 dB | +36.6 dB | 20.2 dB |
   | **2.2 k** | **+22.3 dB** | +37.1 dB | **14.8 dB** |
   | 4.7 k | +27.9 dB | +37.7 dB | 9.9 dB |

   Con 2.2 k se recuperan 9.9 dB en el extremo malo y quedan 14.8 dB de
   recorrido, más o menos lo que da un Marshall. Es cambiar una resistencia.

4. **Ganancia unidad en el preamp con los mandos al centro y drive a cero:**
   los +10.05 dB de la etapa 1 los cancelan exactos los −10.10 dB de la stack.
   Es una coincidencia, no un margen: toda la ganancia vive en el pote de drive
   y en la etapa de potencia, así que las tone controls no tienen holgura que
   dar. Subir `R45` ataca justo esto.

## La suite de la fuente

`verify_psu.py` genera variantes de `powersupply/psu_overengineered/psu.net` y saca los números.
El netlist es la fuente de verdad y **no está versionado**: si falta, expórtalo
desde la GUI (`File > Export Netlist`) o con `LTspice -netlist psu.asc`.

| caso | qué hace | qué comprueba |
|---|---|---|
| `sweep` | el netlist tal cual: consigna en rampa 0→29 V ×5, escalones de carga 0.7/2 A, corto de Q3 inyectado en t=2.3 s | que el OVP dispara (~44 µs) y enclava, y que las tomas no oscilan |
| `static` | 5 puntos con consigna fija, paso de 20 µs | tensión, rizado de salida, rechazo del rizado del raíl, margen de dropout, disipación en el paso |
| `cc` | carga pidiendo ~6 A con escalones | límite de corriente (2.51 A), sobrepico del escalón, disipación durante el límite |
| `thermal` | 60 s a 29 V / 2 A sin fallo inyectado | lazo del ventilador: arranque, temperatura de equilibrio, estabilidad, disipación en M3 |

Referencia de lo medido el 2026-07-29 (para detectar regresiones tras tocar el
esquemático):

```
static:   ganancia consigna->salida 5.826 V/V ; rizado de salida <0.1 mV ;
          rechazo del rizado del rail 83-87 dB ; margen de dropout 4.2-19 V ;
          disipacion en el paso 9-28 W
sweep:    OVP dispara 44 us tras el corto, pico de 17.7 V, enclavado hasta el final ;
          10 transiciones por rele en 5 ciclos (sin parpadeo)
cc:       limite 2.512 A (teorico 2.511) ; sobrepico 5.92 A en el escalon ;
          +/-10 % de rizado en CC cerca del dropout ; 119 W de pico en el paso
thermal:  28.2 W -> Tj 48.1 C con ventilador al 61 % (67 C sin ventilador) ;
          lazo estable (3.4 mV) ; M3 disipa 0.90 W (excede el SOT-23)
```

Los tres puntos abiertos que salieron de ahí (lógica de tomas durante el límite
de corriente, M3 infradimensionado, ancho de banda del lazo CC) están anotados
en la cabecera de `verify_psu.py`.

## La curva de THD del 40W: `bench.py` + `plot_thd_curve.py`

```bash
python3 tools/ltspice/plot_thd_curve.py            # redibuja desde el JSON
python3 tools/ltspice/plot_thd_curve.py --resim    # vuelve a simular (~90 s)
```

Escribe `guitar_amplifier/quasimod_thd.{json,svg,png}`. El JSON es la fuente de
la figura y va versionado, así que redibujar no toca LTspice: sólo `--resim`
simula, y es lo único que necesita el `.net`.

`bench.py` es el banco: parchea el netlist del 40W para fijar cada mando y cada
condición, lo corre en batch y devuelve armónicos y `.meas`. `thd_split()`
separa el THD en par e impar, que para una guitarra dice más que el total.

### Las condiciones no son arbitrarias

**700 mVpp de entrada** es la senoidal con el mismo valor eficaz que los
acordes medidos con la guitarra (230 mV RMS). Lo que equipara un tono de prueba
a material real es el RMS, no el pico: el pico sólo manda durante el ataque,
mientras que el resto de la nota —lo que se juzga— lo gobierna el eficaz. Con
el pico sale disparatado: una senoidal a los 1,6 Vpp de un acorde da 23,9 % de
THD con la ganancia a 0,5, donde la guitarra suena limpia. Esa diferencia es
factor de cresta, 3 dB de una senoidal contra unos 18 de un acorde.

**`drive=0` no es el mínimo del aparato.** El pote es logarítmico inverso y el
tope mecánico de abajo cae en `drive 0,20`; a esa altura la pista ya ha bajado
a 479 Ω de los 1000. Un quinto de vuelta se come la mitad de la resistencia.

**Volumen a 0,5** deja la etapa de potencia fuera de recorte, así que la curva
enseña sólo lo que hacen el drive y los recortadores. Con el volumen al tope se
mezclarían dos mecanismos y no se podría leer ninguno.

### La trampa del rail rígido

`mains=False` sustituye la cadena de red por una continua de `vraw` voltios:
3 s por punto en vez de 80. Vale para todo lo que no dependa de la regulación,
y la curva de THD es de ésas, porque a volumen 0,5 el rail apenas cae.

Para potencia máxima o caída de rail **no vale**, y la diferencia no es
cosmética: con un rail rígido a 46,6 V el modelo llega limpio a 41,4 Vpp y el
aparato real se queda en 35,7, lo que lleva a culpar a la etapa de salida de
perder el doble de lo debido. Con la red simulada el rail se hunde solo y el
techo baja a los 35-37 Vpp medidos. No había pérdida anómala; había una fuente
perfecta. Con `mains=True`, `settle` tiene que ser **0,8 s o más**: cargar los
10000 µF lleva cientos de milisegundos y con los 30 ms por defecto se mide el
arranque, no el régimen permanente.

### Por qué el `.net` va versionado

Los parches van contra los nombres de nodo que genera LTspice (`N004`, `N023`,
`0002`...), así que hace falta **su** netlist y no otro. Este build no sabe
netlistar en batch — `-netlist` abre ventana y se queda ahí — y `asc2net.py`
numera los nodos anónimos de otra forma, de modo que no sirve de sustituto.
Ignorar el `.net`, como se hace con el resto de artefactos, dejaba la curva
irreproducible sin pasar por la GUI, así que éste es la excepción y va en el
repo.

La contrapartida: al abrir el `.asc` en LTspice, el `.net` se reescribe y
reaparece como modificado aunque sea equivalente. Si el diff es sólo
renumeración de nodos anónimos, se descarta sin más.

## Lo que se mide sin tocar el aparato: `power_budget.py`, `stability.py`, `noise_hum.py`

Tres análisis que no estaban y que no necesitan banco. Los tres se apoyan en
`bench.py`, no en `verify_amp_tran.py`, **y eso no es una preferencia de
estilo**: la suite vieja ya no corre contra este netlist. Modela el recortador
como `D5/D6/D7/D9` con `C36/R41` y `C35/R63` a masa, que es como estaba antes
de que los ramales pasaran por los conmutadores `XU1`/`XU2`. Al primer
`_base()` revienta con *`'C36 N024 0 10u' aparece 0 veces`*. Arreglarla es un
trabajo aparte; mientras tanto, lo que se necesitaba de ella se ha rehecho.

### `power_budget.py`: dónde se queda la potencia

Barre la entrada de 40 mVpp a 1.8 Vpp y mide, en cada punto, lo que llega al
altavoz y lo que disipa **cada** transistor, cada resistencia y cada diodo.

La disipación de un BJT no es `I(Qx)`: tiene tres patas y hay que sumar las
dos uniones, `V(c,e)·Ic + V(b,e)·Ib`. Dos trampas al medirlo:

1. **`Ic()`/`Ib()` tienen que estar en el `.save`** o el `.meas` sale
   `FAIL'ed` y el valor se lee como 0. Silencioso y muy fácil de no ver: la
   tabla sale entera, con ceros.
2. **`V(x,0)` y `V(0)` no son expresiones válidas.** Q7 y Q2 tienen el emisor
   a masa, así que su medida hay que escribirla `V(Q7C)` a secas. Si no, esos
   dos —y Q7 es uno de los de salida— salen a cero mientras el resto funciona.

Va en modo RED, no con continua rígida. Con un rail firme de 50 V el ampli
aparenta dar 50 W, porque una fuente ideal no se entera de que le están
pidiendo 5 A.

**Y el arranque son 2 s, no 0.8.** Esto se me escapó y la tabla entera salió
mal una vez. Los 0.8 s de la trampa del depósito son los que tarda en cargarse
`C13`, y son correctos *para el depósito*. El aparato entero tarda más: con la
etapa de salida recortando, el acoplo de salida de 3300 µF y la red de
polarización siguen moviéndose mucho después. Medido contra el punto
distorsionado de `power_summary.md`, que ya estaba publicado:

```
  settle   Vrms      W      THD
    0.9   16.42   33.70   29.7%     <- transitorio, 12 % por debajo
    2.0   17.54   38.47   37.3%     <- regimen permanente, y cuadra
```

Con 0.9 s no se está midiendo el amplificador, se está midiendo cómo llega a
serlo. Cuesta el doble por punto y no es negociable.

Dos más, pequeñas, de la misma tabla:

- `R27` es la carga, no una pieza: sale del ranking de resistencias porque ya
  tiene su propia columna. Y como un altavoz de guitarra convierte en sonido
  un 1-5 % de lo que recibe, esa columna **es** la disipación de la bobina.
- `I(V4)` sale con el signo del generador. El `abs()` va fuera del `.meas`, no
  dentro: dentro falsea la media, fuera sólo arregla el signo.

### `stability.py`: sobrepico y margen, barriendo C11

**Por qué no hay diagrama de Bode del lazo.** Este amplificador tiene dos
caminos de realimentación en paralelo: `R5` (4k7) desde `PRE_SPEAKER` al
emisor de Q1, y `R19` (2k2) desde `SPEAKER` al nodo `FEEDBACK`, que llega al
mismo emisor por `C4`. Romper sólo uno deja el otro cerrado y lo que sale no
es la ganancia de lazo: medido así daba **6.5 dB en banda media**, que para un
ampli con ~48 de ganancia en lazo cerrado es absurdo. El punto común es el
emisor de Q1, y ahí la impedancia hacia atrás (~47 Ω, que es `R4`) y hacia
delante (`re` de Q1, del mismo orden) son comparables, así que no vale ni
inyección de tensión ni de corriente: haría falta la doble inyección de Tian.

El sobrepico con escalón lleva la misma información, **y además se mide en el
banco con un generador de cuadrada**. La cuadrada va a 20 kHz y no a 1 kHz: con
los graves al mínimo, el techo de una cuadrada de 1 kHz se desploma entre
flanco y flanco, y entonces lo que se mide como «sobrepico» es la caída. Con
1 kHz salían 1360 %.

### `noise_hum.py`: siseo y zumbido, que no son lo mismo

El siseo es aleatorio y sale del `.noise` en 0.08 s, con la contribución de
cada dispositivo por separado en el `.raw`. El zumbido es determinista —el
rizado del depósito colándose en la señal— y el `.noise` **no lo ve**: hace
falta la red simulada y un `.tran` largo.

Tres cosas que costaron un rato:

- **El ruido referido a la entrada no se integra.** La ganancia se desploma en
  los extremos de la banda, `inoise` se dispara al dividir por ella y la
  integral se la comen los bordes donde el ampli ya no amplifica: salían
  39.7 µV cuando la cifra buena es 14.5. Se da como ruido de salida partido
  por la ganancia en banda media.
- **El `.four` del zumbido lo separa `parse_log`**, que mete los bloques de
  50 Hz en `fourier_mains` y con la frecuencia absoluta como clave, no con el
  índice de armónico. `fourier_signal` sale vacío y parece que no ha medido.
- **La señal de prueba del zumbido va a 1 kHz, no a 50.** A 50 Hz el rizado de
  100 cae justo encima del segundo armónico de la propia señal.

Y una que afecta a cualquier medida de potencia con la red simulada:
`AVG(abs(V·I))` sobre el secundario **no es** la potencia media. Con
rectificador de condensador la corriente va y viene, y el `abs()` dentro de la
media cuenta como consumo la energía que el depósito devuelve al secundario:
daban 14 W en reposo. Va sin `abs()` dentro.
