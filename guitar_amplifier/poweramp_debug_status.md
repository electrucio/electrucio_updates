# Power amp — estado de depuración y puesta a punto

Etapa de potencia de [AudioAmpCompl-40W](guitar_amplifier/ltspice/AudioAmpCompl-40W.asc)
(cuasi‑complementaria, single‑supply, salida acoplada por C10). PCB fresada en CNC,
transistores/disipador reutilizados. Mapeo de nets en `poweramp_net_mapping.md`,
visor en `poweramp_xview.html` (abre con `#net=NOMBRE`).

## Topología (recordatorio)
- Entrada PNP Q1 (BC556B) + VAS Q2 (BD139) + spreader/Vbe‑mult Q3 (BD139).
- Salida cuasi‑comp: superior EF2 = Q4(BD139)+Q6(2SD896); inferior CFP = Q5(BD140)+Q7(2SD896).
- D10 = diodo de Baxandall (equilibra mitades). R16/R17 = 0,47 Ω emisor.
- RV1 = midpoint (250k). RV2 = bias (1k). **C1 de entrada NO está en esta placa.**
- 2SD896 = NPN **simple** (triple‑diffused, 100V/7A/40W), complementario 2SB776.

## Fallos encontrados y arreglados
1. **Viruta CNC**: `PRE_SPEAKER`↔masa → midpoint clavado a 0 V. (limpiada)
2. **Viruta CNC**: en la red de bias (base de Q3) → Q3 sin conducir, runaway. (limpiada)
3. **Viruta CNC**: `Q2C`↔masa → VAS muerto, salida abajo, RV1 sin efecto. (limpiada)
4. **R7 2k2 → 4k7**: el modelo SPICE del 2SD896 (IS=1e‑11) da Vbe optimista; los
   transistores reales piden más tensión de spreader. Con R7=4k7 el spreader llega
   a ~4 V y el punto de 40 mA queda a media vuelta de RV2 (buena resolución).
   (R8 se dejó en 1k.)
- ⚠️ NO cortocircuitar la entrada a masa (sin C1 en placa, mete R1=1k en base de Q1).
- Ruido de **100 kHz** = fuente de banco **conmutada** (no es del ampli; con la PSU
  lineal real desaparece). Mejor desacoplar VCC en placa al medir.

## Estado actual (verificado)
- Servo DC OK: midpoint `PRE_SPEAKER` = 7,5 V (a 15 V) / 15 V (a 30 V).
- Ganancia **×30** (262 mV RMS in → 7,84 V RMS out). Coincide con sim (~32).
- Bias: R17 ≈ 19 mV (40 mA, inferior), R16 ≈ 14 mV (30 mA, superior). Asimetría
  residual del cuasi‑comp, aceptable.
- **Q3 montado en el disipador** (del revés, reutilizado) → compensación térmica OK,
  sin runaway. Disipador 43 °C tras 15 min. R9/R10 a ~82 °C (aceptable; si son
  1/4 W, subir a 1 W).
- Potencia: **~7,7 W RMS limpios** sobre dummy 8 Ω/100 W a **30 V** (P = Vrms²/R).
  Máx antes de recorte a 30V/8Ω ≈ 10,5 W. Los 40 W del diseño necesitan ~50 V (PSU real).

## TAREA PENDIENTE — oscilación
- **~660 kHz** montada **solo en los semiciclos superiores** (positivos) de la onda,
  con carga y a 30 V.
- **Causa identificada:** **solo Q3 va con cables largos** al disipador (el resto de
  transistores tienen patillas cortas). Q3 (spreader) alimenta el driver superior Q4
  vía `Q3C`/R12 → la inductancia de esos cables está en la rama de drive de la mitad
  superior → oscila cuando esa mitad conduce (semiciclo positivo). Además la rama del
  Vbe‑mult se vuelve inductiva/resonante en HF y capta la salida. ~660 kHz cuadra.
  (NO son los transistores de salida — esos tienen leads cortos.)
- **Fix (en orden):**
  1. **Trenzar los 3 cables de Q3** (`Q3C`,`Q3B`,`Q2C`) muy apretados y alejarlos del
     cableado de salida. Reduce inductancia y captación. Suele bastar.
  2. **Ferrita o R serie ~10–47 Ω** en el cable de `Q3C` (y/o `Q2C`) → amortigua el LC.
  3. Asegurar **C6 (10n) cruzando el spreader EN LA PLACA** (`Q3C`–`Q2C`); reforzar
     con otro 100 n si hace falta.
  4. Acortar los cables de Q3 lo posible.
  5. General: desacoplo local 100 nF+electrolítico en VCC de salida; cap Miller ~100–470 pF
     C‑B en Q4 o subir C6 si persiste.
- No dejar oscilando mucho rato a 30 V (calienta drivers/salida).

## Procedimiento de ajuste final (tras matar la oscilación)
1. RV2 al mínimo → encender (con límite de corriente).
2. RV1 → midpoint = VCC/2.
3. RV2 → 40 mA (~19 mV en R16 *y* R17), calentar 10–15 min, reverificar (debe
   estabilizarse/bajar, no subir).
4. Señal: cruce por cero limpio a bajo nivel; recorte **simétrico** al máximo;
   sin pelusa HF bajo carga.
