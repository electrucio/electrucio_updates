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

## Las cinco trampas del CLI

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
scoop de medios      148-302 Hz segun treble, hasta 22 dB bajo el estante de 5 kHz
interaccion          la stack a 1 kHz va de -36.3 dB (bass=0/treble=0) a
                     -3.8 dB (bass=0/treble=1): los dos controles NO son
                     independientes
```

### La figura

> **El netlist no está versionado.** Igual que `psu_cvcc.net`, el
> `AudioAmpCompl-40W.net` está en `.gitignore`: en un clon limpio hay que
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
2. **No hay pote de medios**: `R44 = 100 Ω` fijo. Es un Marshall con el mid a
   cero, así que el scoop es profundo y no ajustable — es la explicación de los
   −10 dB que se come la stack.

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
