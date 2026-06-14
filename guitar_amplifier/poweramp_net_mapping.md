# Power amp net mapping: KiCad PCB ↔ LTspice simulation

Correlation between the power-amp PCB netlist (recovered from `poweramp BOM.html`,
an InteractiveHtmlBom export with `--include-nets`, board "poweramp" dated
2026-06-04) and the full-system LTspice netlist
`guitar_amplifier/ltspice/AudioAmpCompl-40W.net` (pickup + preamp + PSU +
power amp + speaker model).

**Result: the power-amp block matches the PCB 1:1.** Same refs (Q1–Q7, R1–R19,
R26, C2–C12, C14, C3, D10, RV1, RV2), same values, same topology. Only the
auto-generated node names differ (KiCad names a net after the first pad,
LTspice after a transistor pin or `N0xx`).

See also: `poweramp_netlist.cir` (standalone SPICE netlist extracted from the BOM).

## Node correspondence table

| LTspice node | KiCad net (ibom)       | poweramp_netlist.cir | Description |
|--------------|------------------------|----------------------|-------------|
| `Q6C`        | `/POW`                 | `VCC`                | Main supply rail (V2 in sim, VCC1 connector on PCB) |
| `N008`       | `/POW1`                | `VCC_F1`             | After R26 (47Ω), filtered by C14 (1000µ) |
| `N009`       | `/POW2`                | `VCC_F2`             | After R2 (1k), filtered by C3 (3µ3); front-end supply |
| `N017`       | `Net-(PREAMP1-Pin_1)`  | `IN`                 | Power-amp input (after C1; C1 is OFF-board) |
| `Q1B`        | `Net-(Q1-B)`           | `Q1_B`               | Q1 base |
| `Q2B`        | `Net-(Q1-C)`           | `Q1_C`               | Q1 collector = Q2 base |
| `Q1E`        | `Net-(Q1-E)`           | `Q1_E`               | Q1 emitter |
| `FEEDBACK`   | `Net-(C4-Pad2)`        | `FB`                 | Feedback node (C4/R4/R19/RV1) |
| `Q2C`        | `Net-(Q2-C)`           | `Q2_C`               | VAS collector |
| `N024`       | `Net-(C7-Pad1)`        | `LAG`                | R11 (220) / C7 (330p) junction |
| `Q3C`        | `Net-(Q3-C)`           | `Q3_C`               | Top of bias spreader, drives Q4 via R12 |
| `Q3B`        | `Net-(Q3-B)`           | `Q3_B`               | RV2 wiper (bias adjust) |
| `N010`       | `Net-(R7-Pad2)`        | `BIAS_T`             | R7 (2k2) → RV2 end |
| `N011`       | `Net-(R8-Pad1)`        | `BIAS_B`             | RV2 end → R8 (1k) |
| `BOOTSTRAP`  | `Net-(C8-Pad1)`        | `BOOT`               | Bootstrapped VAS load (R9/R10/C8) |
| `Q4B`        | `Net-(Q4-B)`           | `Q4_B`               | Q4 base |
| `Q6B`        | `Net-(Q4-E)`           | `Q4_E`               | Q4 emitter = Q6 base |
| `Q6E`        | `Net-(Q6-E)`           | `Q6_E`               | Q6 emitter → R16 (0.5) |
| `Q7B`        | `Net-(Q5-C)`           | `Q5_C`               | Q5 collector = Q7 base |
| `Q5E`        | `Net-(D10-K)`          | `D10_K`              | Q5 emitter = D10 cathode |
| `Q7C`        | `Net-(D10-A)`          | `D10_A`              | Q7 collector = D10 anode = R17 |
| `PRE_SPEAKER`| `Net-(C10-Pad1)`       | `OUT`                | Output node before coupling cap C10 (3300µ) |
| `SPEAKER`    | `Net-(SPEAKER1-Pin_1)` | `SPK`                | After C10; speaker + R19 (2k2) feedback take-off |
| `N015`       | `Net-(C9-Pad2)`        | `ZOB`                | Zobel midpoint (C9 100n / R18 10) |
| `0`          | `0`                    | `0`                  | Ground |

## PCB ↔ simulation boundary (connectors)

| PCB connector (JST XH 2p) | Pin 1 ↔ LTspice node | What attaches in the sim |
|---------------------------|----------------------|--------------------------|
| `PREAMP1`  | `N017`    | Preamp output via C1 (1µ). **C1 is NOT on the power-amp PCB** — it must live on the preamp board, or the preamp output must already be AC-coupled. |
| `SPEAKER1` | `SPEAKER` | Duncan vint30 speaker model (R27/R28/L4/C15/R29/C16/L5/R30/L6, nodes `0002`–`0004`). |
| `VCC1`     | `Q6C`     | V2, an ideal 15V debug source. The transformer/rectifier PSU block (V4, K1·L1–L3, D1–D4, C13 → `N002`/`VRAW+`) currently powers ONLY the preamp (R47/R51); `VRAW+` has no counterpart on this PCB. |

All connector pin 2s = ground (`0`). H1/H2 are mounting holes, unconnected.

## Blocks in the LTspice file with NO counterpart on this PCB

- Pickup model: V6 (`PICKUP_IN`), L7 (2.2H), R58, R60–R62, C32/C34 → `PICKUP_OUT`
- Preamp: Q8, Q10, Q11, Q12, tone stack (C19/C20, R37/R43/R45/R46…),
  diode clippers D5–D9, pots P1 (bass), P2 (treble), P3 (master vol, log),
  P4 (drive, revlog)
- PSU: V4 (325V 50Hz mains), transformer K1 (L1/L2/L3), bridge D1–D4,
  C13 (10000µ), R24/R25/R31 → `VRAW+`/`N002`

## Simulation-only artifacts / small differences

- `R20`, `R21`, `R59` (1GΩ to ground): DC-path helpers for the sim, not real parts.
- `C1` (1µ input coupling): in sim only, off-board (see boundary table).
- RV1 (250k, wiper tied to FEEDBACK end — same wiring on PCB, pads 1+2 on FB,
  pad 3 to Q1_B): sim uses `wiper=.54` → effective ≈135k between Q1B and
  FEEDBACK. `poweramp_netlist.cir` models it at full 250k.
  Purpose per schematic note: adjust so OUTPUT (PRE_SPEAKER) sits at VCC/2.
- RV2 (1k bias trimmer): sim uses `wiper=.037` (near one end);
  `poweramp_netlist.cir` assumes a 50/50 split.
  Purpose per schematic note: adjust for 40 mA quiescent current through R16/R17.
- `Q3*`: the PCB footprint reference literally contains an asterisk
  (leftover annotation marker in KiCad); it is plain `Q3` in LTspice.
- The LTspice file is UTF-16 encoded.
- 2SD896 (Q6/Q7) is an NPN Darlington; the LTspice file defines its own
  `.MODEL 2SD896` (and an unused `2SB776` PNP) — prefer those over the rough
  placeholders in `poweramp_netlist.cir`.

## How the PCB netlist was recovered

`poweramp BOM.html` embeds `var pcbdata = JSON.parse(LZString.decompressFromBase64("…"))`.
Decoding that blob yields footprints with per-pad net names (the BOM was generated
with InteractiveHtmlBom's `--include-nets`). Per the ibom source
(InteractiveHtmlBom/ecad/kicad.py): pads are serialized sorted lexicographically
by pad name (so array order = pad number for these 1–3 pin parts), `pin1` flags
the pad named "1", and `net` comes from `pad.GetNetname()`.
