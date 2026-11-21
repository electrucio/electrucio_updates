# Medir la estabilidad del 40W en el banco

Receta para repetir en el aparato lo que `tools/ltspice/stability.py` midió en
el modelo, y para buscar lo que el modelo **no puede** ver: las oscilaciones
que nacen del cableado y del trazado de la placa, como la de 600 kHz que ya
apareció una vez en este amplificador.

Valores simulados, para comparar al final:

| carga | sobrepico simulado |
|---|---|
| 8 Ω resistivos | 7,1 % |
| altavoz real | 7,0 % |
| 8 Ω + 2,2 µF | 23,2 % |
| altavoz + 2,2 µF | 25,4 % |

---

## 0. Material

- Generador de funciones con cuadrada hasta 20 kHz y flancos por debajo de
  100 ns (cualquiera moderno los tiene).
- Osciloscopio con FFT.
- Sonda ×10 **con su muelle de masa corto**. Si no lo tienes, suelda 1 cm de
  hilo rígido al anillo de masa de la punta.
- Resistencia de 8 Ω / 100 W.
- Condensador **de película** (MKT o MKP) de 2,2 µF / 100 V como mínimo.
  **Electrolítico no**: en bornes del altavoz no hay continua, así que vería
  alterna pura en inversa medio ciclo; y sobre todo, por encima de su
  autorresonancia deja de ser capacitivo justo en la banda que interesa, con
  lo que el ensayo pasaría sin haber ensayado nada.
- Un jack con las puntas cortocircuitadas.
- La lámpara en serie, para el primer encendido tras cualquier cambio.

## 1. Preparación: la sonda

**Esto decide si la medida vale o no.** Dos cosas, en este orden:

1. **Compensa la sonda** en el calibrador del osciloscopio antes de nada. Una
   sonda ×10 descompensada redondea o sobrepasa las cuadradas por su cuenta, y
   te vas a pasar la tarde midiendo su error en vez del del amplificador.
2. **Usa el muelle de masa, no el cocodrilo.** El cable de cocodrilo forma una
   espira de varios centímetros cuadrados que capta y radia a la vez; a cientos
   de kHz puede pintar un timbrado inexistente o provocar uno que no estaba.

Ancho de banda del osciloscopio: **completo** para buscar oscilaciones,
**limitado a 20 MHz** para medir sobrepico (si no, el ruido engorda el pico).

Mide siempre en **los bornes de salida del amplificador**, cuelgues lo que
cuelgues de ellos.

## 2. Prueba A — oscilación espontánea (sin señal)

La que habría cazado el problema de 600 kHz. Es la más importante de todas.

```
entrada      jack cortocircuitado
carga        resistencia de 8 Ω
sonda        bornes de salida, acoplo CA, sensibilidad alta
osciloscopio ancho de banda COMPLETO, FFT activa, persistencia si la tiene
```

Y ahora **barre despacio, por todo su recorrido y uno a uno**: ganancia,
volumen, graves, agudos. Repite el barrido con las cuatro combinaciones de los
conmutadores de diodos (U1 y U2, fuera/fuera, dentro/fuera, fuera/dentro,
dentro/dentro).

Las oscilaciones casi nunca están en todo el rango: dependen de la impedancia
que ve el lazo, que cambia con la posición de los potes. Una que sólo exista
entre el 60 % y el 70 % del volumen es perfectamente normal, y mirando sólo en
los topes no se ve.

**Anota:** si aparece algo, su frecuencia y en qué posiciones exactas.

## 3. Prueba B — respuesta al escalón

La comparable con la simulación. Condiciones exactas:

```
generador    cuadrada 20 kHz, ~40 mVpp al jack
mandos       ganancia al MÍNIMO, volumen al MÁXIMO
             agudos al MÁXIMO, graves al MÍNIMO
diodos       ambos conmutadores FUERA
salida       ajusta el generador hasta leer ~4,8 Vpp en la salida
osciloscopio acoplo CC, ancho de banda 20 MHz
```

**Ajusta por la salida, no por la entrada.** Los 40 mVpp son lo que pedía el
modelo; tus potes y tolerancias no son los suyos.

**Por qué 20 kHz y no 1 kHz:** con los graves al mínimo y los acoplos, el techo
de una cuadrada de 1 kHz se desploma entre flancos, y lo que medirías como
sobrepico sería esa caída. Probado en el modelo: salían 1360 %.

**Por qué 4,8 Vpp:** tiene que estar lejos del recorte. Cerca del techo la
saturación se come el pico y el amplificador parece mejor de lo que es.
Comprueba que la cuadrada tiene los techos planos, no comprimidos.

Si el generador no baja limpiamente a 40 mVpp, mete un divisor resistivo 10:1
en el jack (1 kΩ en serie, 110 Ω a masa). La entrada es de 1 MΩ, así que no lo
carga, y la impedancia de fuente resultante se parece más a una guitarra que
los 50 Ω del generador.

### Qué medir

Con cursores, sobre el flanco de subida:

```
Vbase    nivel antes del flanco
Vfinal   nivel asentado, unos 15-20 µs después
Vmax     el pico más alto

sobrepico % = (Vmax - Vfinal) / (Vfinal - Vbase) x 100
```

Si hay timbrado, anota también su frecuencia (mide el periodo entre dos
máximos consecutivos).

No te fíes de la medida automática de "overshoot" del osciloscopio sin
comprobar contra qué referencia la calcula; con cursores sabes lo que haces.

### Las cuatro cargas, en este orden

1. **Resistencia de 8 Ω sola.** La referencia.
2. **Resistencia + 2,2 µF en paralelo.** El ensayo de tortura. Si el ampli se
   pone raro o calienta, pon 1-2 Ω en serie con el condensador; es una variante
   aceptada, pero dilo al publicar porque cambia el resultado.
3. **Altavoz con su cable, en la caja.** Breve. La sonda sigue en los bornes
   del amplificador.
4. **Altavoz + 2,2 µF.** El peor caso.

> ⚠️ Una cuadrada de 20 kHz no es comida para un altavoz de guitarra. A 4,8 Vpp
> son 0,7 W y es inofensivo, pero hazlo **breve** y nunca a potencia alta: no
> vas a oír casi nada y es fácil olvidarse de que está sonando.

## 4. Prueba C — zona de cruce

En clase AB cada transistor conduce medio ciclo, y cerca del paso por cero la
etapa se pasa el testigo de uno a otro con los dos casi cortados. Ahí cambia
bruscamente la ganancia de lazo, y es donde salen las ráfagas.

```
generador    seno 1 kHz, salida a media potencia (unos 10-15 Vpp)
carga        resistencia de 8 Ω
osciloscopio acoplo CA, sensibilidad vertical ALTA
             disparo en el paso por cero de la salida
             base de tiempos expandida: unos pocos µs alrededor del cruce
```

Buscas un escalón o muesca (distorsión de cruce) y un pelotazo de alta
frecuencia montado encima.

**Hazlo en frío y repítelo en caliente**, porque el reposo de este
amplificador cae de 40 a 15 mA al calentarse, y menos reposo es una zona de
cruce peor.

## 5. Prueba D — salida del recorte

Al recortar, el transistor amplificador de tensión se satura y almacena carga
en su base. Al salir del recorte tarda en desaturarse, y durante ese rato el
lazo está fuera de juego.

```
generador    seno 1 kHz, nivel hasta RECORTE DURO
carga        resistencia de 8 Ω
osciloscopio disparo en la esquina donde la onda ABANDONA la meseta
             base de tiempos expandida ahí
```

Buscas que la salida se quede pegada al techo, que dé un salto al despegarse,
o que suelte una ráfaga. El modelo dice que este amplificador no lo hace, pero
es justo lo que el trazado puede cambiar.

## 6. Prueba E — en caliente

Veinte o treinta minutos a potencia media, y repites **la prueba A** (barrido
sin señal) y **la prueba B** con la resistencia. Hay osciladores que sólo
existen calientes.

## 7. Seguridad

- Lámpara en serie en el primer encendido tras cualquier cambio.
- Si encuentras una oscilación mantenida, **córtala enseguida**: un
  amplificador oscilando a cientos de kHz disipa mucho más que en servicio
  normal, y los 2SD896 no avisan antes de romperse.
- Vigila el disipador con la mano durante las pruebas largas.

## 8. Hoja de resultados

```
SOBREPICO (cuadrada 20 kHz, salida 4,8 Vpp, ganancia min, volumen max,
           agudos max, graves min, diodos fuera)

carga                      sobrepico   timbrado   simulado
8 ohm                         ____ %   ____ kHz     7,1 %
8 ohm + 2,2 uF                ____ %   ____ kHz    23,2 %
altavoz + cable               ____ %   ____ kHz     7,0 %
altavoz + 2,2 uF              ____ %   ____ kHz    25,4 %

OSCILACION ESPONTANEA (entrada en corto, barrido de los cuatro mandos,
                       cuatro combinaciones de diodos)

  [ ] nada encontrado
  [ ] encontrada a ______ kHz, con ___________________________

ZONA DE CRUCE          frio: ____________   caliente: ____________
SALIDA DEL RECORTE     ____________________________________________
EN CALIENTE            ____________________________________________
```
