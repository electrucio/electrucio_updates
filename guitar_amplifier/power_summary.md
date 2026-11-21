# Quasimod 40W — maximum output power

1 kHz sine, 8 Ω load, treble at maximum, bass at minimum, volume at maximum.

|                    | Measured           | Simulated          |
|--------------------|--------------------|--------------------|
| Max clean sine     | 12.5 Vrms · 19.5 W | 14.2 Vrms · 25.2 W |
| Max distorted sine | 17.4 Vrms · 37.8 W | 17.5 Vrms · 38.3 W |

## Conditions

Common to all four figures: 1 kHz sine into an 8 Ω resistive load, treble at
maximum, bass at minimum, volume at maximum, clipping diodes switched out.

**Max clean sine** — gain at minimum, output below 1% THD. Measured with
410 mVpp at the input jack: 35.7 Vpp at the load, supply at 46.6 V. Simulated
with 470 mVpp at the jack and the gain pot at 0.20, which is the model value
that corresponds to the real pot's mechanical minimum — the taper is reverse
log, so its bottom stop is not zero.

*Corrected.* This figure used to read 20.9 W. That came from a transient that
had not settled: 0.9 s is enough to charge the reservoir but not enough for
the 3300 µF output coupling capacitor and the bias network, and the leftover
drift showed up as distortion. With 2 s of settling the sub-1% limit moves to
14.2 Vrms. The measured column is unchanged.

Most of the remaining difference is the output midpoint, which sits about 2 V
below centre on the real board and clips one half-cycle early. Forcing the
model to the same midpoint costs it 2.8 Vpp and brings it to 22.1 W, so the
bias point explains roughly 55% of the gap and not all of it. See
`simulated_measurements.md`.

**Max distorted sine** — the highest RMS the amplifier will deliver at any
setting. Measured with 1 Vpp at the jack and gain near 0.5, heavily clipped on
the scope, supply sagging to 45.0 V. Simulated with 1.2 Vpp at the jack and
gain at 0.20, at 31.7% THD.

Simulated figures come from `ltspice/quasimod_guitar_amplifier.asc` driven from
the mains transformer calibrated against the bench, not from a stiff DC rail.
That distinction is not a detail — see the last section.

## It is a 20 W amplifier

The clean figure is the honest one. The ratio between the two rows is 1.94,
and that is not a coincidence: when a sine is clipped until it becomes a
square wave its RMS goes from Vpeak/√2 to Vpeak, so it grows by √2 and the
power, which goes with the square, doubles. At 37.8 W the amplifier is
essentially at the square-wave limit and has nothing left to give — the
amplitude is pinned by the rail and only the filling of the waveform keeps
growing.

So the "40 W" in the name is the square-wave rating of a 20 W amplifier. The
difference between the two rows is distortion, not useful power.

## Past a point, more gain means less power

The distorted figure is the highest RMS the amplifier can deliver at *any*
setting, and it is not reached at the end of the gain pot. It happens around
gain 0.2-0.35, and it is flat between those two. Beyond that the waveform
reaching the output stage turns spiky rather than square, so it loses RMS even
though its amplitude stays pinned around 40 Vpp — 7 W of output traded for
60 points of THD:

| gain | input  | output     | power  | THD   |
|------|--------|------------|--------|-------|
| 0.20 | 1.20 V | 17.54 Vrms | 38.5 W | 37.3% |
| 0.35 | 0.90 V | 17.52 Vrms | 38.4 W | 35.7% |
| 0.50 | 1.00 V | 17.09 Vrms | 36.5 W | 51.3% |
| 0.50 | 4.00 V | 15.88 Vrms | 31.5 W | 98.3% |

*(These were measured again after the settling time was corrected; the
previous version of this table was a few per cent low for the same reason the
clean figure was.)*

## Simulate the supply, not a battery

An earlier version of this comparison used a stiff 46.6 V DC rail and
concluded the real output stage was losing about twice as much as the model —
5.45 V per side against 2.5 V. That conclusion was wrong, and the cause was
the method: a stiff rail does not exist. At that current the real supply sags,
and once the transformer is simulated properly (`K1 = 0.994`, `L2 = 0.281H`,
calibrated against 51.2 V unloaded and 46.6 V at 36 Vpp) the model's clean
ceiling drops from 41.4 Vpp to the 35–37 Vpp actually measured.

There is no anomalous loss in the output stage. There was a simulation fed by
a perfect power supply.

What is left, once the supply is simulated properly *and* the transient is
allowed to settle, is a 4.4 Vpp shortfall against the model. Most of it — 2.8
Vpp, about 3 W — is the bias point rather than the transistors: the midpoint
is 2 V off centre, and forcing the model to the same offset reproduces that
much of the loss and no more. The rest is inside the tolerance of the
measurement and of the output transistor models.
