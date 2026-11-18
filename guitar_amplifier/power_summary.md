# Quasimod 40W — maximum output power

1 kHz sine, 8 Ω load, treble at maximum, bass at minimum, volume at maximum.

|                    | Measured           | Simulated          |
|--------------------|--------------------|--------------------|
| Max clean sine     | 12.5 Vrms · 19.5 W | 12.8 Vrms · 20.5 W |
| Max distorted sine | 17.4 Vrms · 37.8 W | 17.5 Vrms · 38.3 W |

*Clean* means below 1% THD. The simulated figures come from
`ltspice/quasimod_guitar_amplifier.asc` driven from the real mains chain, not
from a stiff DC rail — see the note below, it is the whole point.

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
gain 0.2 with 1.2 Vpp at the jack. Beyond that, the waveform reaching the
output stage turns spiky rather than square, so it loses RMS even though its
amplitude stays pinned at ~41 Vpp:

| gain | input  | output    | power  | THD    |
|------|--------|-----------|--------|--------|
| 0.20 | 1.20 V | 17.50 Vrms | 38.3 W | 31.7% |
| 0.50 | 1.00 V | 16.25 Vrms | 33.0 W | 47.0% |
| 0.50 | 4.00 V | 15.18 Vrms | 28.8 W | 104.7% |

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
