# Simular LTspice desde la línea de comandos (macOS)

Herramientas para simular en batch, sin abrir la GUI, y post-procesar los
resultados con numpy. Pensado para que cualquier sesión nueva (o cualquier
chat) pueda reproducir las medidas sin tener que redescubrir las trampas.

```
tools/ltspice/
├── rawread.py      lector de ficheros .raw (binarios, .tran y .ac)
├── ltrun.py        preparar un netlist y lanzar LTspice en batch
├── verify_psu.py   suite de verificación de powersupply/psu_overengineered/psu.asc
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

### `.meas` vs post-proceso

Para un número suelto, `.meas` es más corto y sale en el `.log`
(`.meas TRAN vout_pp PP V(out) FROM 4m TO 5m` — sin `FROM/TO` incluye el
transitorio de arranque y la medida no vale). Para lo demás —mínimos en ventana
deslizante, integrar tiempo por encima de un umbral, contar transiciones de
relé, KCL en un nodo, RMS en ventana— sale antes con numpy sobre el `.raw`.

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
