# AI-assisted redesign of a guitar preamplifier

I am not an expert on electronics. My actual background includes a PhD in digital audio processing, and my daily job involves software engineering, machine learning, signal processing... but no electronics at all. However, I recently realized I really enjoy learning about analog electronics, so here I am.

In this article, I explain how I have been experimenting with an AI agent to understand and adapt an existing guitar preamplifier to my requirements. I used AI for three main purposes:

* Understand an baseline existing design
* Brainstorm improvements suggestions
* Introduce changes in the existing design with verifiable metrics, using LTSpice simulation

[![Guitar preamplifier design from RedCircuits.com](https://www.dropbox.com/scl/fi/j1w2b3latuc1dzcs9ssm6/ia_usage_schema.png?rlkey=hmgm9mjfw24pbcfbxjxyl2l60&st=0qr6pca7&raw=1)](https://www.dropbox.com/scl/fi/j1w2b3latuc1dzcs9ssm6/ia_usage_schema.png?rlkey=hmgm9mjfw24pbcfbxjxyl2l60&st=0qr6pca7&raw=1)

I have learned a lot during the process, so I hope it can be inspiring for other people too. I invite any expert to provide feedback that help to improve the approach.

# 1. My requirements
Let's assume these are my requirements for a guitar amplifier.
* ✅ Input suitable for a standard guitar pickup
* ✅ Output suitable for a standard power amplifier
* ✅ Power voltage 0-15V
* ✅ Four knobs: Drive, Bass, Treble, Volume
* ✅ This is not a lab exercise: it has to work in real-world
* ✅ Discrete parts only, no op-amps.

# 2. Starting point: a schematic from redcircuits.com

For my exercise, I've used this project as a starting point: https://www.redcircuits.com/Page65.htm

[![Guitar preamplifier design from RedCircuits.com](https://www.redcircuits.com/GuitarPre.GIF)](https://www.redcircuits.com/GuitarPre.GIF)

Is this design enough for us?
* ❓ Input suitable for a standard guitar pickup
* ❓ Output suitable for a standard power amplifier
* ❌ Power voltage 0-15V
* ❌ Four knobs: Drive, Bass, Treble, Volume
* ❓ Properly designed, it should work as expected
* ✅ Discrete parts only, no op-amps.

Let's investigate if my requirements are met, with the help of LTSpice and Gemini.

## 2.1. LTSpice simulation

Let's begin with a simulation of the existing preamplifier: **does it work?**

### 2.1.1. Transient analysis using a 0.5 Vpeak, 1 kHz sine wave
According to [Rod Elliot](https://sound-au.com/articles/guitar-voltage.htm), a value of 0.5 Vpeak is rather high for guitar pickups, but still realistic for some models, so we will use this input amplitude in our analysis.

[![LTSpice simulation circuit](https://www.dropbox.com/scl/fi/t5rb5kocnawi6e06ufliy/original_design.png?rlkey=wdgznctyiu3kggrhhqcorpruo&st=g417y9ij&raw=1)](https://www.dropbox.com/scl/fi/t5rb5kocnawi6e06ufliy/original_design.png?rlkey=wdgznctyiu3kggrhhqcorpruo&st=g417y9ij&raw=1)

After running this simulation, for `drive=0` (and the rest of parameters as shown in the figure) we get these results in our `.log` file:
| Node | Vmean | Vmin | Vmax | %THD |
| :--- | :--- | :--- | :--- | :--- |
| **V(in)** | 0.00 | -0.50 | 0.50 | 0.00% |
| **V(q1b)** | 2.50 | 2.12 | 2.88 | 0.00% |
| **V(q2c)** | 32.53 | 25.78 | 39.29 | 0.02% |
| **V(mid_in)** | 0.00 | -6.76 | 6.75 | 0.02% |
| **V(tone_in)** | 0.00 | -6.42 | 6.42 | 0.02% |
| **V(tone_out)**| 0.00 | -2.10 | 2.10 | 0.02% |
| **V(q3b)** | 27.57 | 25.47 | 29.67 | 0.02% |
| **V(q3e)** | 26.92 | 24.82 | 29.01 | 0.03% |
| **V(out)** | 0.00 | -2.09 | 2.09 | 0.03% |

If we activate the distortion (`drive=1`):
| Node | Vmean | Vmin | Vmax | %THD |
| :--- | :--- | :--- | :--- | :--- |
| **V(in)** | 0.00 | -0.50 | 0.50 | 0.00% |
| **V(q1b)** | 2.50 | 2.13 | 2.88 | 1.48% |
| **V(q2c)** | 32.81 | 27.56 | 39.13 | 9.16% |
| **V(mid_in)** | 0.00 | -5.21 | 6.32 | 9.16% |
| **V(tone_in)** | 0.00 | -3.09 | 3.35 | 23.26% |
| **V(tone_out)**| 0.00 | -1.73 | 1.74 | 33.37% |
| **V(q3b)** | 27.57 | 25.84 | 29.31 | 33.37% |
| **V(q3e)** | 26.92 | 25.19 | 28.65 | 33.37% |
| **V(out)** | 0.00 | -1.73 | 1.73 | 33.37% |

On on the other hand:
* Input impedance is 285kΩ 
* Output impedance is 10kΩ

Some preliminary conclusion about how well this design meets my requirements:

### AC analysis: frequency response
Using a python script and `spicelib`, with the help of Gemini, I used `matplotlib` to create a beautiful plot that illustrates what happens with our preamplifier when you modify `bass` and `treble` controls. We will ignore `brightness` control.

[![LTSpice simulation circuit](https://www.dropbox.com/scl/fi/cmu691a0sbsxga6ana50k/original_design_ac_analysis.png?rlkey=8c12vp7o72heztxzauc2l2je4&st=0nr1ze2u&raw=1)](https://www.dropbox.com/scl/fi/cmu691a0sbsxga6ana50k/original_design_ac_analysis.png?rlkey=8c12vp7o72heztxzauc2l2je4&st=0nr1ze2u&raw=1)

Not sure if this frequency response will produce a beautiful sound, but it is clearly working more or less as expected for both `bass` and `treble` controls.

## 2.2. Understanding it
So far, the results provided by the previous analysis look good, and Gemini a priori says the design is properly done. Now, let's spend some time understanding each part of the circuit. This might help in later stages, and is a good learning exercise.

### 2.2.1. The input stage

I know how to analyze basic transistor circuits, but I am not familiar with this specific topology, so I need some help to understand the key aspects of it. I iterated with Gemini:

> 1. The "Direct-Coupled Feedback Pair" (specifically an NPN-PNP pair)
This is the practical, schematic-level name.
> "Direct-Coupled" means there is no blocking capacitor between the collector of Q1 and the base of Q2. They are directly wired together.
> "Feedback Pair" means the two transistors operate as a single functional block bound by a global feedback loop.
> 2. The "Two-Stage Voltage-Series Feedback Amplifier"
This is the formal, academic name used in university physics and engineering books.
> "Voltage" means the feedback network (R7) is sampling the voltage at the output node (Q2's collector).
> "Series" means that the feedback is being injected into the emitter of Q1, which places it in series with the input signal arriving at the base.

After some iterations, I was able to find that **Two-Transistor Series-Feedback Gain Stages** is the right keyword for this topology:

[
![LTSpice simulation circuit](https://www.dropbox.com/scl/fi/94ttidc72mrazcleyqloo/input_stage.png?rlkey=q7omij2o7z7nnz9tlv7lpa17b&st=ipkadute&raw=1)](https://www.dropbox.com/scl/fi/94ttidc72mrazcleyqloo/input_stage.png?rlkey=q7omij2o7z7nnz9tlv7lpa17b&st=ipkadute&raw=1)

I also wonder... why are we adding C3 here?

>In electronics literature, this specific component is universally known as a **Miller compensation capacitor** (or sometimes a **dominant-pole compensation capacitor**).
> Because your circuit uses global negative feedback (R7 and R8), there is a danger that at very high (radio) frequencies, natural phase shifts inside the transistors will turn that _negative_ feedback into _positive_ feedback, causing the amplifier to violently oscillate. C3 intentionally uses the "Miller Effect" to roll off the high-frequency gain of Q2, keeping the amplifier stable.

Ok, let's believe this.

**DC analysis**

After some iteration, I also understood the key aspects of this topology to perform a DC analysis (after opening all capacitors). If we do a rough approximation (ignoring $I_{2b}$, ignoring the effect of R4 on the voltage divider...):

* $V_{be}$ voltages are constant ~0.65v, so we know $V_{R6} = 0.65$v.
* Since we know $V_{2b}$, we can know $I_{R6} = 0.65 / 2k2 = 295$µA, which is very similar to $I_{1c}$.
* As we know $I_{1c}$, we can know $I_{1b}$, since $I_{1b} = I_{1c}/\beta_{1} =295 / 344 = 0.86$µA.
* As we know $I_{1b}$ we can know the voltage in $R4$: $V_{R4} = I_{1b} R4 = 0.86 \cdot 10^{-6} \cdot 220 \cdot 10^{3} = 0.19$V. We can then subtract the voltage in R4 to the voltage produced by the divider made of R3 and R5, and compute $V_{1b} = 57.08 \cdot \frac{33k}{(680k + 33k)} - 0.19=2.45$v.
* Then we can compute $V_{1e} = V_{1b} - 0.6 = 2.45 - 0.6 = 1.85$, and then we can compute $I_{R8} = 1.85 / 330 = 5.6$mA.
* $I_{R8} = I_{1e} + I_{2c}$. We know that $I_{1e} \approx I_{1c} = 295$µA, so we can estimate $I_{2c} = 5.6 - 0.295 = 5.3$mA.
* $V_{R7} = I_{2c} \cdot R7 = 5.3 \cdot 5k6 \approx 30$v, so $V_{2c} = 30 + 1.85 \approx 32$v. In LTSpice we get 32.52v instead of 32v because of the approximations mentioned before.

**Some considerations about AC analysis**

For AC analysis, we put our voltage supply to ground, and we consider all coupling and decoupling capacitors as close circuits, but what about Miller capacitor C3? Gemini suggests to treat it as an open circuit because we are interested in the audio bandwidth, and its reactance for these frequencies is very high.

Gemini says:
> When you strip away all the DC bias components, what you are left with is a textbook **Non-Inverting Operational Amplifier** made of discrete parts.

And it says that the amplification factor of a non-inverting op. amp is $$A_v \approx 1 + \frac{R_7}{R_8} \approx 17.97$$
In LTSpice I get $17.7$, so I guess it is correct as an approximation. Let's go on.

### 2.2.2. The Middle: Dynamic Clipping and Tone Control

Let's go with the middle part. 
[
![LTSpice simulation circuit](https://www.dropbox.com/scl/fi/odon4j8sfq4g9190pmovh/mid_section.png?rlkey=veno2uyohjmntyv2w71qc609v&st=orjwo7no&raw=1)](https://www.dropbox.com/scl/fi/odon4j8sfq4g9190pmovh/mid_section.png?rlkey=veno2uyohjmntyv2w71qc609v&st=orjwo7no&raw=1)

Again: I'll ask Gemini to find references in well-known literature to understand the design used in this schematic.

> This is a fantastic schematic to dig into. You've zeroed in on the exact heart of the preamplifier where the "character" and "feel" of the guitar tone are forged.
Here is the breakdown of the specific topologies used for the clipping and tone control stages, along with the common names you'll find in electronics and amp-design literature.
> ### 1. The Clipping Stage: Self-Biasing / Dynamic Clipper
>**Components involved:** P4, D1, D2, C5, C6, R11.
> In standard guitar pedal or preamp literature, this is known as a **Self-Biasing Clipper**, **Dynamic Diode Clipper**, or **RC-Biased Clipper**.
> 
> **How it works:**
> -   **Standard Hard Clipping:** Usually, anti-parallel diodes are connected directly to ground. When the signal exceeds the diode's forward voltage (about 0.2V-0.3V for the BAT46 Schottky diodes used here), it clips the wave completely flat. This sounds very harsh and buzzy ("solid-state" sounding). 
> -   **The Dynamic Twist:** In this circuit, the diodes do not go directly to ground. D1 connects to C5, and D2 connects to C6. When a loud signal hits and a diode conducts, it charges its respective capacitor. 
> -   **The Tube Emulation Effect:** As C5 and C6 charge up, they introduce a DC bias voltage that essentially _raises_ the clipping threshold for the next wave. The harder you play, the higher the threshold pushes back. As the note decays, the capacitors discharge through R11, lowering the threshold again.
> -   **The Result:** This creates a dynamic, "rubbery" feel that responds to pick attack, commonly referred to as "sag." It is a well-known solid-state technique used to emulate the asymmetrical duty-cycle shift and grid-clipping characteristics of an overdriven 12AX7 vacuum tube. P4 acts as a variable series resistor to control how hard the signal hits this network, essentially acting as a "Drive" or "Shape" control.

I used a guitar recording as input in V1 (`wavefile="../../audios/dry_guitar_5s.wav"`), and I was able to observe the behavior described by Gemini: the capacitors create a envelope follower, so the bias of the diode clipping is dynamic, allowing more dynamics than just the two diodes to ground.

[![LTSpice simulation circuit](https://www.dropbox.com/scl/fi/yhxxy8udxd9mcev8ydf6c/diode_clipping.png?rlkey=qc2tp5xac8xxkljlwtw6s1m2b&st=l90wm55s&raw=1
)](https://www.dropbox.com/scl/fi/yhxxy8udxd9mcev8ydf6c/diode_clipping.png?rlkey=qc2tp5xac8xxkljlwtw6s1m2b&st=l90wm55s&raw=1
)

I have been investigating if this is a standard way of applying distortion in pedals or guitar preamps, but it does not seem to be very common. I found similar topologies for envelope followers, and I also found information about similar approaches in existing designs.

In "Solid-State Guitar Amplifiers" by Teemu Kyttälä, I was able to find references to a circuit that behaves similarly:

[
![LTSpice simulation circuit](https://www.dropbox.com/scl/fi/iqkzpvlrjy71ldfnn4fuv/Captura-de-pantalla-2026-03-01-a-las-0.47.20.png?rlkey=vm43ao2m3bhmilke0z7lggwcb&st=xosj3dhl&raw=1)](https://www.dropbox.com/scl/fi/iqkzpvlrjy71ldfnn4fuv/Captura-de-pantalla-2026-03-01-a-las-0.47.20.png?rlkey=vm43ao2m3bhmilke0z7lggwcb&st=xosj3dhl&raw=1)

However, I did not find any existing diode clipper design exactly as ours in the documentation I checked.

> ### 2. The Tone Control: The James Tone Network
> **Components involved:** C7, R12, P2 (Treble), P1 (Bass), R14, R15, R13, C9.
> 
> In literature, this specific topology is historically and technically known as the **James Tone Network** (created by E.J. James in 1949). However, in the guitar community, it is almost universally (and slightly incorrectly) referred to as a **Passive Baxandall** tone stack.
>
>**How it works:**
>
>-   Unlike the classic "FMV" (Fender/Marshall/Vox) tone stack which is highly interactive and naturally has a massive mid-scoop, the James network is designed to be much flatter and more independent.
>    
>-   **Treble Path:** The high frequencies pass through C7 and are controlled by P2.
>   
>-   **Bass Path:** The low frequencies are blocked by C7 but pass through R12 to be controlled by P1.
>    
> -   **Characteristics:** It provides genuine bass and treble _cut and boost_ relative to the baseline insertion loss of the circuit. If you set both P1 and P2 to 50% (as hinted by the `.param pos2=0.5` and `pos3=0.5` tags), you will get a relatively flat frequency response. The addition of R14, R15, and C9 in this specific variation acts as a shaping network to set the exact crossover frequency and control the midrange behavior between the two pots.
> 
> It looks like a very thoughtfully designed solid-state preamp aimed at capturing tube-like dynamics rather than just raw distortion.

Not sure what is true and what is not, but let's investigate more.

#### Clipper
With the indications of Gemini, and some experimentation with LTSpice, I see what it is doing. I have been searching for other schematics using this specific design, but I couldn't find it. I found similar approaches for "envelope followers", but not this exact design for a distortion stage.

In "Solid-State Guitar Amplifiers" by Teemu Kyttälä, I was able to find references to a circuit that behaves similarly:

[
![LTSpice simulation circuit](https://www.dropbox.com/scl/fi/iqkzpvlrjy71ldfnn4fuv/Captura-de-pantalla-2026-03-01-a-las-0.47.20.png?rlkey=vm43ao2m3bhmilke0z7lggwcb&st=xosj3dhl&raw=1)](https://www.dropbox.com/scl/fi/iqkzpvlrjy71ldfnn4fuv/Captura-de-pantalla-2026-03-01-a-las-0.47.20.png?rlkey=vm43ao2m3bhmilke0z7lggwcb&st=xosj3dhl&raw=1)

I asked Gemini to explain to me the difference between this "Crowhurst's Fuzz" and the one our preamplifier is using: Apparently, using a single capacitor vs. two capacitors affects to the symmetry of the output signal: with two capacitors, the clipping threshold evolves differently for negative semi-cycles and positive semi-cycles, unlike in the case of using a single capacitor.

In any case: in LTSpice it seems to work, so I consider it is ok so far.
**Note:** in the original design, my P4 is a switch. I initially added this P4 as an attempt to create a continuous drive control. I changed this later.

[
![LTSpice simulation circuit](https://www.dropbox.com/scl/fi/h2dz986vr9escm36jblce/Captura-de-pantalla-2026-03-01-a-las-1.48.09.png?rlkey=7bti5we25o91telmk0tc3t9md&st=0r2cit1o&raw=1)](https://www.dropbox.com/scl/fi/h2dz986vr9escm36jblce/Captura-de-pantalla-2026-03-01-a-las-1.48.09.png?rlkey=7bti5we25o91telmk0tc3t9md&st=0r2cit1o&raw=1)

[
![LTSpice simulation circuit](https://www.dropbox.com/scl/fi/f1pf78xywvad4prpcui9j/Captura-de-pantalla-2026-03-01-a-las-1.47.53.png?rlkey=0bzod6tuzu7d16f39p94l0u1o&st=dextp8j6&raw=1)](https://www.dropbox.com/scl/fi/f1pf78xywvad4prpcui9j/Captura-de-pantalla-2026-03-01-a-las-1.47.53.png?rlkey=0bzod6tuzu7d16f39p94l0u1o&st=dextp8j6&raw=1)

#### Tone control
Let's remember again our tone stack.

[
![LTSpice simulation circuit](https://www.dropbox.com/scl/fi/kuxyosqga2e4kmazmw1hs/Captura-de-pantalla-2026-03-01-a-las-2.31.31.png?rlkey=1tnkazyndzyrf71b1u1tgz06y&st=0cygbmdh&raw=1)](https://www.dropbox.com/scl/fi/kuxyosqga2e4kmazmw1hs/Captura-de-pantalla-2026-03-01-a-las-2.31.31.png?rlkey=1tnkazyndzyrf71b1u1tgz06y&st=0cygbmdh&raw=1)

I have been reviewing some books, and all the topologies shown in https://www.guitarscience.net/tsc/james_2.htm, but I didn't find my exact topology. The most similar one is the James Tone Stack "Passive / Single Bass Capacitor":

[
![LTSpice simulation circuit](https://www.dropbox.com/scl/fi/3uqhm2lyrnx169q2ykbwy/Captura-de-pantalla-2026-03-01-a-las-2.37.37.png?rlkey=kjurrd9yesf3pid7cdwfw1ow5&st=jcr4lvtz&raw=1)](https://www.dropbox.com/scl/fi/3uqhm2lyrnx169q2ykbwy/Captura-de-pantalla-2026-03-01-a-las-2.37.37.png?rlkey=kjurrd9yesf3pid7cdwfw1ow5&st=jcr4lvtz&raw=1)

But it is not exactly the same! $C_B$ is not present in our design, and R3 (which in our case would be R14) is not connected to the same node.

Maybe we should use a standard tone stack design? We will see later in our analysis about AC sweeps. So far, I think the understanding of the tone control stage is enough.

### 2.2.3. The Output Stage: Bootstrapped Buffer (Q3)
[
![LTSpice simulation circuit](https://www.dropbox.com/scl/fi/qdp1kq2qeb2buow3725yo/Captura-de-pantalla-2026-03-01-a-las-3.16.42.png?rlkey=eiuddh5uxhp7hvnbzcpjj7o7p&st=z7gjvrnx&raw=1)](https://www.dropbox.com/scl/fi/qdp1kq2qeb2buow3725yo/Captura-de-pantalla-2026-03-01-a-las-3.16.42.png?rlkey=eiuddh5uxhp7hvnbzcpjj7o7p&st=z7gjvrnx&raw=1)

> Based on the schematic provided, you are looking at a classic **Bootstrapped Emitter Follower** (also known as a Common Collector amplifier) circuit.
> 
> Here is a detailed breakdown of the topology and the specific role of each component.
> ### **Circuit Topology: The Bootstrapped Emitter Follower**
> The core of this circuit is the NPN transistor configured as an emitter follower. In a standard emitter follower, the input is applied to the base, the output is taken from the emitter, and the voltage gain is approximately 1 (unity). Its primary purpose is to act as a **buffer**: it provides a very high input impedance and a low output impedance, allowing you to drive a heavier load without loading down the previous stage.
>
>However, a standard biasing network (like a simple voltage divider) normally lowers the overall input impedance. This circuit solves that using a clever technique called **bootstrapping** (via C11 and R18), which artificially inflates the input impedance to a much higher value.
>
>---
>
>### **Role of the Components**
>
>#### **1. Power Supply & Decoupling**
>
>* **V2 (60V):** The main DC power supply for this stage.
>* **R21 ($330\Omega$) & C13 ($220\mu F$):** These form an RC low-pass filter (often called a decoupling or "RC snubber" network). They filter out high-frequency noise and power supply ripples from the 60V rail, providing a clean, quiet 57.08V DC supply to the transistor's collector.
>#### **2. The Active Component**
>
>* **Q3 (BC546B):** An NPN bipolar junction transistor (BJT) acting as the current buffer. It amplifies the current of the input signal while keeping the voltage level essentially the same (minus the base-emitter voltage drop, $V_{BE} \approx 0.65V$).
>
>#### **3. DC Biasing Network**
>
>These components establish the steady state (DC quiescent operating point) of the transistor so it stays in its active region to amplify AC signals without clipping.
>
>* **R17 ($100k\Omega$) & R19 ($100k\Omega$):** These form a voltage divider that sets an intermediate DC voltage (28.22V) at the junction between them.
>* **R20 ($10k\Omega$):** The emitter load resistor. It sets the quiescent DC current flowing through the transistor. Because the emitter sits at about 26.9V, the current is roughly $I_E = \frac{26.9V}{10k\Omega} \approx 2.7mA$.
>
>#### **4. The Bootstrapping Network (The Clever Part)**
>
>* **R18 ($100k\Omega$):** Provides the actual DC bias current to the base of Q3 from the R17/R19 voltage divider.
>* **C11 ($10\mu F$):** **The bootstrap capacitor.** This is the secret sauce of this topology. It connects the emitter output back to the junction of R17, R18, and R19.
>* **How it works:** Because the emitter follower has a voltage gain of almost 1, the AC voltage at the emitter is nearly identical to the AC voltage at the base. C11 feeds this AC voltage back to the bottom of R18. Consequently, both ends of R18 are bouncing up and down with the exact same AC signal.
>* If there is no AC voltage *difference* across R18, there is no AC current flowing through it. By Ohm's law, if a resistor draws no AC current, its effective AC resistance appears to be near infinity. This prevents the biasing network from lowering the input impedance of the amplifier.
>
>#### **5. Signal Coupling & Output**
>
>* **C10 ($10\mu F$):** The input coupling capacitor. It blocks any incoming DC voltage from messing up the delicate bias of the base, but allows the AC audio/signal to pass through.
>* **C12 ($10\mu F$):** The output coupling capacitor. It strips away the large 26.9V DC offset at the emitter, allowing only the AC signal to pass to the next stage.
>* **P3a & P3b (Potentiometer, $10k\Omega$ total):** This acts as an output volume control or attenuator. The `.param pos4=0.00001` indicates that the wiper (the `OUT` node) is currently set extremely low, meaning it's heavily attenuating the signal right now in your simulation.

---

Quite clear! I searched a bit more about this "bootstrapping", and it seems Gemini was totally right about it.

[
![LTSpice simulation circuit](https://www.dropbox.com/scl/fi/ldesm1puw3dznlmccbswx/Captura-de-pantalla-2026-03-01-a-las-3.33.27.png?rlkey=yzlwbvrgn6lbkck5a7zw0hr0p&st=r9r7bi2v&raw=1)](https://www.dropbox.com/scl/fi/ldesm1puw3dznlmccbswx/Captura-de-pantalla-2026-03-01-a-las-3.33.27.png?rlkey=yzlwbvrgn6lbkck5a7zw0hr0p&st=r9r7bi2v&raw=1)

[
![LTSpice simulation circuit](https://www.dropbox.com/scl/fi/7p5xlqxnkde86ktb84x49/Captura-de-pantalla-2026-03-01-a-las-3.33.34.png?rlkey=cnsaehmuwysndf10ge7f9ucor&st=pr3mwtbv&raw=1)](https://www.dropbox.com/scl/fi/7p5xlqxnkde86ktb84x49/Captura-de-pantalla-2026-03-01-a-las-3.33.34.png?rlkey=cnsaehmuwysndf10ge7f9ucor&st=pr3mwtbv&raw=1)

# 3. Adapting the design to my requirements
There are two main changes we want to introduce in the design:

* Use a power supply of 15V instead of 60V
* Use a "drive" potentiometer to control the level of distortion, instead of a switch.

## 3.1. Adapting the power supply
Gemini:
> At 60V, the R3 (680k) and R5 (33k) voltage divider provides about 2.6V to the base of Q1, which centers Q2's collector nicely at ~32.5V.If we apply a 15V supply without changing R3, that divider will only provide about 0.67V to the base. Q1 will barely turn on, and the amplifier will stop working.
> We need to recalculate R3 to provide the correct bias for a 15V supply. To find the new value for R3, we calculate the required base voltage to center Q2's collector at ~7.5V ($V_{supply} / 2$). Taking into account the base-emitter drops and the current through R8 and R7, we need about 1.15V at the base of Q1.Using the voltage divider formula:$$V_{base} = V_{supply} \times \frac{R5}{R3 + R5}$$$$1.15 = 15 \times \frac{33k}{R3 + 33k}$$Solving this gives us an R3 value of approximately 390kΩ.
> Action: Replace R3 (680kΩ) with a 390kΩ resistor. (A 330kΩ or 470kΩ will also work, but 390kΩ keeps the collector perfectly centered).
> What About the Rest of the Circuit?
Fortunately, the rest of the circuit is incredibly robust and requires zero changes to run on 15V.

[
![LTSpice simulation circuit](https://www.dropbox.com/scl/fi/e8k1ggv7m1aep7yrz5pm1/Captura-de-pantalla-2026-02-28-a-las-16.54.48.png?rlkey=pce0hn0ku36tdngaiab0fphz1&st=5gs6ctq2&raw=1)](https://www.dropbox.com/scl/fi/e8k1ggv7m1aep7yrz5pm1/Captura-de-pantalla-2026-02-28-a-las-16.54.48.png?rlkey=pce0hn0ku36tdngaiab0fphz1&st=5gs6ctq2&raw=1)

I changed the resistor R3 to 390KΩ, and indeed it is close to be working perfectly for 15V. In practice, R3 and/or R5 should be a potentiometer for perfect adjusting of the bias.

## 4.2. Using a "drive" potentiometer, instead of a switch

# 4. AI-suggested improvements on the original design


Now for the interesting part: **can I improve this design with the help of Gemini**?

**⚠️Disclaimer:** In my experience with AI tools, the more you know about a topic, the more mistakes you catch in the AI's output. In this case, I'm not spotting many errors (which makes me a bit suspicious). It's likely because I'm not an expert in this specific field. I've double-checked everything as much as possible, but a true expert might approach this entirely differently. I'll walk you through my results, and leave it up to you to draw your own conclusions.

## 4.1. AI-criticism of the design
I began with a picture of the schematic, plus this prompt: *You are an expert designer of guitar preamplifiers, and I want you to be very critical this design. I want to you to suggest possible issues, even if it is not sure they are issues. Just brainstorm about things that could be improved in this design, based on your expertise.*

Here I try to catch eventual issues for later investigation. I can not say if there are more relevant issues that were not captured by the AI, but it suggested many points. For example: the AI didn't mention it, but at some point I would like to understand why the tone stack doesn't really fit any existing well-known design, and whether we should stick to well-known designs.

After some iterations, these are the issues found by the AI, together with proposed solutions.
>Here is a consolidated summary of the potential issues we've identified in your preamplifier design, broken down by stage.
>
>Think of this as your punch list for the next revision.
>
>### 1. The Input Stage
>
>-   **Issue:** Loading of Passive Pickups
>   
>    -   **Summary:** The AC input impedance is dominated by R4 (220kΩ). This is too low for standard passive guitar pickups and will dull the high-end sparkle (treble bleed).
>        
>    -   **Approach:** Increase the input impedance to at least 1MΩ. Change R4 to 1MΩ or 2.2MΩ, and recalculate the R3/R5 voltage divider to maintain the ~1.1V base bias for Q1.
>        
>-   **Issue:** Oversized Input Coupling Capacitor
>    
>    -   **Summary:** C1 is a 10µF electrolytic cap. This sets the bass cutoff way below the human hearing range (~0.07Hz), which wastes headroom on subsonic frequencies and can introduce leakage noise.
>        
>    -   **Approach:** Replace C1 with a high-quality 22nF or 47nF film capacitor. This will filter out subsonic rumble while preserving all the usable bass frequencies of a guitar.
>        
>
>### 2. The Gain Block (Q1 & Q2)
>
>-   **Issue:** Lack of Headroom
>    
>    -   **Summary:** The stage has a voltage gain of ~26. With hot pickups, the signal will easily try to swing beyond your 15V power supply, causing harsh, unmusical transistor clipping before it ever reaches your diode network.
>        
>    -   **Approach:** Lower the gain by increasing the value of R8, or add an input trim/attenuator before the stage to keep the signal within the 15V rails.
>        
>-   **Issue:** DC Instability
>    
>    -   **Summary:** The feedback network (R7, R8) is fully DC-coupled. The bias point will drift with temperature changes and rely heavily on the exact hFE of the specific transistors you use.
>        
>    -   **Approach:** Add a large DC-blocking capacitor (e.g., 22µF or 47µF) in series with R8 to ground. This forces the DC gain to 1, stabilizing the bias point, while maintaining your AC gain.
>        
>
>### 3. The Dynamic Clipping Network
>
>-   **Issue:** Blocking Distortion ("Farty" Decay)
>    
>    -   **Summary:** The self-biasing concept is great, but 10µF for C5 and C6 creates a time constant that is too slow. The shifting DC baseline will cause a sputtering, gating effect as the guitar note decays, rather than a smooth tube-like sag.
>        
>    -   **Approach:** Reduce C5 and C6 to 1µF or 470nF for faster, more musical tracking. You can then fine-tune the release time by adjusting R11.
>        
>-   **Issue:** "Drive" Control (P4) Impedance Mismatch
>    
>    -   **Summary:** P4 sits in series with the signal path. Turning up the drive drastically increases the series resistance, creating a massive voltage divider with the tone stack. You will lose volume and alter your EQ curve every time you adjust the drive.
>        
>    -   **Approach:** Do not use P4 as a series resistor. Instead, place the drive control in the feedback loop of the Q1/Q2 gain stage, or put a high-impedance buffer _between_ the clipping network and the tone stack.
>        
>
>### 4. The Tone Stack
>
>-   **Issue:** Heavy Loading
>    
>    -   **Summary:** The 10kΩ potentiometers (P1, P2) present a very low impedance load to the clipping stage, draining signal energy and negatively interacting with the clipping behavior.
>        
>    -   **Approach:** Scale the impedance up. Swap P1 and P2 for 100kΩ or 250kΩ potentiometers. To keep the exact same EQ frequency response, divide the values of the associated capacitors (C7, C9) by the same factor of 10 or 25.
>        
>
>### 5. Output Buffer & Power Delivery
>
>-   **Issue:** Buffer Biasing and AC Loading
>    
>    -   **Summary:** Q3's emitter sits at roughly 4.4V DC, meaning the waveform will clip asymmetrically on the negative swing. Furthermore, P3 (Master Volume) is only 1kΩ, placing a heavy load on the buffer and limiting output swing.
 >       
>    -   **Approach:** Adjust the R17/R18/R19 network to center Q3's emitter voltage at exactly 7.5V (half of your 15V supply) for maximum headroom. Change P3 to a 10kΩ or 50kΩ potentiometer.
>        
>-   **Issue:** Power Supply Vulnerability (Motorboating)
>    
>    -   **Summary:** Running this high-gain preamp directly off the exact same 15V rail as a current-hungry Class A power amp with zero decoupling is a recipe for low-frequency oscillation (motorboating) and hum.
>        
>    -   **Approach:** Add an RC decoupling filter specifically for the preamp. Place a 100Ω resistor in series with the 15V line feeding the preamp, followed by a 100µF or 220µF capacitor to ground.

Interesting points. Let's address them one by one, we are not hurried.
## 4.2. Loading of Passive Pickups
Let's measure the input impedance with LTSpice.
[
![LTSpice simulation circuit](https://www.dropbox.com/scl/fi/by9msdgu6abrwwqzgstu1/Captura-de-pantalla-2026-03-01-a-las-13.06.49.png?rlkey=mrry1c3ixb5vcpevzkxjson0z&st=rs5mheyy&raw=1)](https://www.dropbox.com/scl/fi/by9msdgu6abrwwqzgstu1/Captura-de-pantalla-2026-03-01-a-las-13.06.49.png?rlkey=mrry1c3ixb5vcpevzkxjson0z&st=rs5mheyy&raw=1)

We know that $Z_{in} = V_{in} / I_{in} = V_{in} / I_{R1}$. In LTSpice we check that, when $V_{in}$ is 150mV, $I_{R1}$ is 550nA, so $Z_{in}$ is ~273kΩ.

**What is the recommended input impedance for a guitar preamplifier?**

Gemini insists it is >1MΩ, but I want to find explicit references about it, and it is not able to refer the exact paragraph of the books that say that. I did something different: I loaded a few well-known PDF reference books (like "Solid-State Guitar Amplifiers" by Teemu Kyttälä to [NotebookLM](https://notebooklm.google.com/), which is designed to answer questions using only the uploaded materials, and then I asked it to find concrete paragraphs mentioning this ">1MΩ" suggestion.

[
![LTSpice simulation circuit](https://www.dropbox.com/scl/fi/6opfu2csuw2gyl0gv9ikn/Captura-de-pantalla-2026-03-01-a-las-13.38.28.png?rlkey=ez3752ad9jdoygok1h422y20k&st=nqecl5bg&raw=1)](https://www.dropbox.com/scl/fi/6opfu2csuw2gyl0gv9ikn/Captura-de-pantalla-2026-03-01-a-las-13.38.28.png?rlkey=ez3752ad9jdoygok1h422y20k&st=nqecl5bg&raw=1).

[
![LTSpice simulation circuit](https://www.dropbox.com/scl/fi/8wbmc780wq9h1kmfk688n/Captura-de-pantalla-2026-03-01-a-las-13.44.34.png?rlkey=8acfmo54byyef29f2dvjegbdu&st=7tkhd6lf&raw=1)](https://www.dropbox.com/scl/fi/8wbmc780wq9h1kmfk688n/Captura-de-pantalla-2026-03-01-a-las-13.44.34.png?rlkey=8acfmo54byyef29f2dvjegbdu&st=7tkhd6lf&raw=1).

Ok, so it is true: >1MΩ is better.

How do I increase my input gain? Apparently, just increasing R4 from 220kΩ to 1MΩ might be problematic because the base current would be too low to keep a reasonable bias setting. So it seems using a JFET input stage is a better option:
>The Solution: A "Low-Capacitance" JFET Buffer
To fix your 275 kΩ impedance issue without destroying your headroom, we should use a JFET Source Follower (Unity Gain Buffer). It will provide a massive 1 MΩ to 5 MΩ input impedance, it won't add unwanted gain, and we can specifically design it to have ultra-low input capacitance to preserve your pickup's resonant frequency, exactly as your book excerpt suggests.

After some iteration, this is what I got:
[
![LTSpice simulation circuit](https://www.dropbox.com/scl/fi/peo9dh4dnbv8lffu29r8i/Captura-de-pantalla-2026-03-01-a-las-20.09.40.png?rlkey=j0fntpttj1186awvr1dmoj8k1&st=tu48fvxj&raw=1)](https://www.dropbox.com/scl/fi/peo9dh4dnbv8lffu29r8i/Captura-de-pantalla-2026-03-01-a-las-20.09.40.png?rlkey=j0fntpttj1186awvr1dmoj8k1&st=tu48fvxj&raw=1)

Indeed, now $V_{IN} / I_{C1}$ in LTSpice provides 1MΩ of input impedance. Apparently, such a high input impedance sometimes can produce an antenna effect, so some kind of grounded shielding (a Faraday cage) is recommended. We will take this into account during the mounting stage.

## 4.3. Oversized Coupling Capacitors
In the new input stage, we have replaced $C_{out}$ (previously C1 of 10µF) by 1µF. 
> in audio engineering we usually evaluate this by looking at the high-pass filter cutoff frequency ($f_c$) created by the capacitor and the input resistance of the next stage. The formula is:
>
>$$f_c = \frac{1}{2 \pi R C}$$
>
>For a guitar, the lowest fundamental note (Low E) is roughly 82 Hz. We generally want our coupling capacitors to set a cutoff frequency around **5 Hz to 20 Hz**. Anything lower than that passes useless subsonic rumble, eats up headroom, and forces you to use electrolytic capacitors (which are noisy and degrade signal quality compared to film capacitors).
>
>Looking at your updated schematic, **yes, several of your coupling capacitors are significantly oversized.** Here is the breakdown of which ones are perfectly fine, and which ones you should shrink.
>### 1. The "Perfectly Sized" Capacitors
>
>Leave these exactly as they are:
>
>-   **`C1` (22nF):** With your new $1\text{ M}\Omega$ `R_gate`, this sets your input cutoff at $\approx 7.2\text{ Hz}$. It is mathematically perfect.
>    
>-   **`C2` (47µF):** This is a power supply decoupling/bias filter capacitor. It is not in the signal path. Its job is to shunt AC noise to ground, so bigger is better here.
>    
>-   **`C3` (47pF):** Standard Miller capacitor for high-frequency stability.
>    
>-   **`C11` (10µF):** The bootstrapping capacitor. Because it needs to act as a perfect AC short across the $10\text{ k}\Omega$ resistor (`R18`) down to the lowest frequencies, 10µF is the correct value here.
>    
>-   **`C7` (15nF) & `C9` (470nF):** These are tone stack capacitors. Their values dictate your EQ curve, not DC blocking, so we don't judge them by the same headroom rules.
>### 2. The "Oversized" Signal Coupling Capacitors
>
>These capacitors are passing the audio signal between stages, but they are much larger than they need to be. By shrinking them, you can replace cheap electrolytics with high-quality film capacitors (WIMA, KEMET, etc.), which will drastically clean up your tone.
>
>-   **`C_out` (1µF):** This couples the JFET to `Q1`. The input impedance of the `Q1` stage is dominated by `R4` ($220\text{ k}\Omega$). Using the formula, a 1µF cap gives a cutoff of $\approx 0.7\text{ Hz}$.
>    
>    -   _Recommendation:_ Drop this to **100nF** or **220nF** (film).
>        
>-   **`C4` (10µF):** This couples `Q2` to the clipping stage. The load it drives is roughly `R9` ($47\text{ k}\Omega$). With 10µF, your cutoff is $\approx 0.33\text{ Hz}$.
 >   
 >   -   _Recommendation:_ Drop this to **470nF** or **1µF** (film).
 >       
>-   **`C10` (10µF):** This couples the Tone Stack to the Output Buffer. Because `Q3` is bootstrapped, its input impedance is incredibly high (likely $>500\text{ k}\Omega$). 10µF gives a cutoff of roughly $0.03\text{ Hz}$.
>    
>    -   _Recommendation:_ Drop this to **100nF** or **220nF** (film).

Sounds reasonable, I will apply these changes.

More comments:
>### 3. The "Oddball" Capacitor: `C12` (10µF)
>
>This is the output capacitor feeding your Master Volume (`P3a/b`).
>
>Normally, a 10µF cap at the very end of a preamp is considered massively oversized. _However_, because you chose a **$1\text{ k}\Omega$** potentiometer for your Master Volume, the load is incredibly heavy.
>
>$$f_c = \frac{1}{2 \pi (1000) (10 \times 10^{-6})} \approx 15.9\text{ Hz}$$
>
>Because your pot value is so small, you actually _need_ that big 10µF capacitor just to let the bass frequencies out! If you ever change that Master Volume pot to a standard $10\text{ k}\Omega$ or $50\text{ k}\Omega$ value (which I highly recommend so you stop stressing the `Q3` buffer), you should shrink `C12` down to 1µF.

Maybe 1KΩ as output impedance is unnecesarily small? In case I modify this, I'll need to revisit the value of C12.

More comments:
>### 4. The Clipping Capacitors: `C5` & `C6` (10µF)
>
>We discussed these earlier. They aren't oversized for frequency response, but they are oversized for **timing**. At 10µF, the charge/discharge time constant with `R11` ($4.7\text{ k}\Omega$) is so slow that it will cause sputtering "blocking distortion" as the guitar notes decay.
>
>-   _Recommendation:_ Drop these to **470nF** or **1µF** to get a faster, snappier overdrive response.

It seems to be a matter of taste, but we will take this into consideration in case the distortion sounds ugly.

## 4.4. Lack of Headroom
It seems my input gain is too high (~26), because I was using R8=220Ω lately, and it might be easy that the input voltages from the guitar pickups are amplified beyond my 15V headroom.

This is highly related with the documentation here: https://sound-au.com/articles/guitar-voltage.htm, concretely this paragraph:

> With a maximum average output of 128mV RMS (with the peak at just under 1V), a preamp with too much initial gain will distort readily, and it's not affected by the preamp's volume control. On the other hand, an average level of 29mV RMS means that you need more gain than you might have thought. In general, the _maximum_ gain for the first stage should be no more than 20 (26dB) for a 'solid state' preamp

So yeah: it seems 26 is too much. Taking into consideration Rod Elliot's measurements, let's set the gain such that the clipping start for input peaks of 0.8V. I will play with R8 and R5 to achieve this, playing with the gain and the bias point little by little.
[
![LTSpice simulation circuit](https://www.dropbox.com/scl/fi/hphrp03nq2pn3107ddpr5/Captura-de-pantalla-2026-03-01-a-las-21.46.08.png?rlkey=kej26qqkd32hmr4yqr9b4jnhc&st=kwg427jy&raw=1)](https://www.dropbox.com/scl/fi/hphrp03nq2pn3107ddpr5/Captura-de-pantalla-2026-03-01-a-las-21.46.08.png?rlkey=kej26qqkd32hmr4yqr9b4jnhc&st=kwg427jy&raw=1)

## 4.4. DC Instability
Let's remember the issue and the solution suggested by Gemini:
> The feedback network (R7, R8) is fully DC-coupled. The bias point will drift with temperature changes and rely heavily on the exact hFE of the specific transistors you use. The solution suggested by Gemini is adding a DC-blocking capacitor (e.g. 10µF) in series with R8 to ground. This forces DC gain to 1, stabilizing the bias point, while maintaining your AC gain.

Well, this was catastrophic. After some iteration, Gemini apologized:

> I owe you a massive engineering apology: **My previous advice to put a DC-blocking capacitor in series with R8 was wrong for this specific circuit.** That advice is a golden rule for Op-Amps and standard amplifiers, but I overlooked a critical detail about your specific `Q1/Q2` Sziklai topology.
>
>Why adding a cap to R8 will break your circuit
>
>In a standard op-amp, the negative input doesn't need a DC path to ground to function. But in your discrete circuit, `R8` isn't just setting the feedback gain; **it is the only path to ground for Q1's emitter current.** If you put a 47µF capacitor in series with `R8`, you block DC completely. Without a DC path to ground, `Q1` cannot turn on. The bias will collapse entirely, and the amplifier will go completely silent.
>
>I gave you a generic textbook solution that actively breaks your specific design. Good catch!

Just another evidence that you should not blindly trust what the AI says.

## 4.5. Blocking Distortion (“Farty” Decay)
> Issue: Blocking Distortion (“Farty” Decay)
>
>Summary: The self-biasing concept is great, but 10µF for C5 and C6 creates a time constant that is too slow. The shifting DC baseline will cause a sputtering, gating effect as the guitar note decays, rather than a smooth tube-like sag.
>
>Approach: Reduce C5 and C6 to 1µF or 470nF for faster, more musical tracking. You can then fine-tune the release time by adjusting R11.

As I mentioned before, I guess this is something that can be evaluated only by listening. Good to know these values might be the reason of an eventual ugly distortion, but I will leave the original values by now.
## 4.6. “Drive” Control & Tone stack impedances issues
Gemini suggested two possible issues, that are quite related:

> -   **Summary:**  P4 sits in series with the signal path. Turning up the drive drastically increases the series resistance, creating a massive voltage divider with the tone stack. You will lose volume and alter your EQ curve every time you adjust the drive.
>
>-   **Approach:**  Do not use P4 as a series resistor. Instead, place the drive control in the feedback loop of the Q1/Q2 gain stage, or put a high-impedance buffer  _between_  the clipping network and the tone stack.

I think Gemini got it wrong here: P4 is not in series with the signal. 

>-   **Summary:**  The 10kΩ potentiometers (P1, P2) present a very low impedance load to the clipping stage, draining signal energy and negatively interacting with the clipping behavior.
>    
>-   **Approach:**  Scale the impedance up. Swap P1 and P2 for 100kΩ or 250kΩ potentiometers. To keep the exact same EQ frequency response, divide the values of the associated capacitors (C7, C9) by the same factor of 10 or 25.

It suggests that using 10kΩ potentiometers might be reducing the voltage at the input of the diodes, but I don't really see this in LTSpice. I don't really understand how to measure the negative impact of what it says.

I will leave this more detailed analysis for the last part of my article, using PySPICE and an appropriate script with sweeps, and audio simulations using a real guitar recording.

## 4.7. Output Buffer Biasing and AC Loading
> -   **Issue:**  Buffer Biasing and AC Loading
>   
>-   **Summary:**  Q3’s emitter sits at roughly 4.4V DC, meaning the waveform will clip asymmetrically on the negative swing. Furthermore, P3 (Master Volume) is only 1kΩ, placing a heavy load on the buffer and limiting output swing.
>    
>-   **Approach:**  Adjust the R17/R18/R19 network to center Q3’s emitter voltage at exactly 7.5V (half of your 15V supply) for maximum headroom. Change P3 to a 10kΩ or 50kΩ potentiometer.

Ok, adjusting the bias of Q3 makes sense, using mostly R19. In LTSpice I see it is easy to adjust.

About P3, the reason I chose 1kΩ is because my power amplifier has an input impedance of around 50kΩ, and I wanted to comply with the 1:10 rule:

[
![LTSpice simulation circuit](https://www.dropbox.com/scl/fi/5iy0tczomwlyfmiil7jrs/Captura-de-pantalla-2026-03-01-a-las-23.07.47.png?rlkey=0k7fuwdzgxeucday477yzwab6&st=vrajc0fg&raw=1)](https://www.dropbox.com/scl/fi/5iy0tczomwlyfmiil7jrs/Captura-de-pantalla-2026-03-01-a-las-23.07.47.png?rlkey=0k7fuwdzgxeucday477yzwab6&st=vrajc0fg&raw=1)

But I guess, I can upload it a bit up to 5kΩ.

## 4.8. Power Supply Vulnerability (Motorboating)
>-   **Issue:** Power Supply Vulnerability (Motorboating)
>    
>    -   **Summary:** Running this high-gain preamp directly off the exact same 15V rail as a current-hungry Class A power amp with zero decoupling is a recipe for low-frequency oscillation (motorboating) and hum.
>        
>    -   **Approach:** Add an RC decoupling filter specifically for the preamp. Place a 100Ω resistor in series with the 15V line feeding the preamp, followed by a 100µF or 220µF capacitor to ground.

At the moment, I have been considering the voltage supply as a fixed stable value. Later, when I connect the different modules (power supply, preamplifier, and power amplifier), I will take these aspects into account. Good to know about this "Motorboating" concept anyway.

## 4.9. Summary of changes
* Addition of a JFET high-impedance input buffer
* Reduce size of capacitors in order to avoid amplifying very low frequencies
* Fine-tuning of input gain in order to avoid clipping loud signals from guitar pickup

**Pending**: detailed analysis of the mid section (diode clipper and tone control).

# 5. Detailed evaluation of diode clipper and tone control

After all the suggestions from Gemini, and after a double check with books and existing documentation, I have doubts about the implementation of the mid section of my design, which contains both the diode clipper and the tone stack.

**What do I want to check?**

* **How does the preamplifier sound, especially the diode clipper in different situations?** We will adjust the values of the components by listening to the result using a real guitar recording.
* **Does the drive control reduces very significantly the amplitude of the output signal?** Applying drive should contribute to a perceptually louder signal, not the opposite. We should be able to use the full dynamic range in the output even when drive is applied.
* **Does the drive control affects in an uncontrolled way to the tone stack filtering?** The tone control should not be strongly affected by the activation of the drive module.
* **Does the tone control works properly?** I am surprised it is similar to some existing topologies (like the James Tone stack), but it is not exactly the same one. We should double check it is not an error in the implementation. Maybe it would make sense to just use one of the well-known topologies.
## Wavfiles in LTSpice
Using a voltage source 

## Implementing the design in PySPICE
I will use Google Collab for this step: it allows good reproducibility, since the whole virtual machine has to be set up for each execution, and it leaves all code in a single place.

I used to Gemini to generate my "Hello world" with my preamplifier code. Concretely, I did this in my prompt:

* I attached a screenshot of the schematic
* I attached the netlist taken from LTSpice (as part of the prompt)
* I attached my files `standard.bjt`, `standard.dio`, `standard.jft` (they were part of LTSpice installation), so that it uses exactly the same models as LTSpice.
* I used this prompt:
```text
<netlist paste>
---
I want to implement this circuit in PySPICE, in a google collab. My first cell is:
!apt-get update
!apt-get install -y libngspice0-dev
!apt-get install -y ngspice
!pip install PySpice

Check my netlist, and the provided models of transistors and diodes.
Run a simulation of transient, and plot using matplotlib Vin and Vout. I want to check it has the same result as my LTSpice simulation.
Also, provides the operating points of the nodes that have been displayed in the image provided.
```

I got this program:
```Python
import matplotlib.pyplot as plt
import numpy as np
from PySpice.Spice.Netlist import Circuit
from PySpice.Unit import *

# =======================================================================
# 1. Device Models
# =======================================================================
def inject_device_models(circuit):
    """Injects required BJT, JFET, and Diode models into the circuit."""
    circuit.model('1N4148', 'D', IS=2.52e-9, RS=0.568, N=1.752, CJO=4e-12, M=0.4, TT=20e-9)

    circuit.model('BC546B', 'NPN', IS=2.39e-14, NF=1.008, ISE=3.55e-15, NE=1.541, BF=294.3,
                  IKF=0.1357, VAF=63.2, NR=1.004, ISC=6.27e-14, NC=1.243, BR=7.946, IKR=0.1144,
                  VAR=25.9, RB=1, IRB=1.00e-06, RBM=1, RE=0.4683, RC=0.85, XTB=0, EG=1.11,
                  XTI=3, CJE=1.36e-11, VJE=0.65, MJE=0.3279, TF=4.39e-10, XTF=120, VTF=2.643,
                  ITF=0.7495, PTF=0, CJC=3.73e-12, VJC=0.3997, MJC=0.2955, XCJC=0.6193,
                  TR=1.00e-32, CJS=0, VJS=0.75, MJS=0.333, FC=0.9579)

    circuit.model('BC556B', 'PNP', IS=3.83e-14, NF=1.008, ISE=1.22e-14, NE=1.528, BF=344.4,
                  IKF=0.08039, VAF=21.11, NR=1.005, ISC=2.85e-13, NC=1.28, BR=14.84, IKR=0.047,
                  VAR=32.02, RB=1, IRB=1.00e-06, RBM=1, RE=0.6202, RC=0.5713, XTB=0, EG=1.11,
                  XTI=3, CJE=1.23e-11, VJE=0.6106, MJE=0.378, TF=5.60e-10, XTF=3.414, VTF=5.23,
                  ITF=0.1483, PTF=0, CJC=1.08e-11, VJC=0.1022, MJC=0.3563, XCJC=0.6288,
                  TR=1.00e-32, CJS=0, VJS=0.75, MJS=0.333, FC=0.8027)

    circuit.model('2N3819', 'NJF', BETA=1.304e-3, BETATCE=-0.5, RD=1, RS=1, LAMBDA=2.25e-3,
                  VTO=-3, VTOTC=-2.5e-3, IS=33.57e-15, ISR=322.4e-15, N=1, NR=2, XTI=3,
                  ALPHA=311.7e-6, VK=243.6, CGD=1.6e-12, M=0.3622, PB=1, FC=0.5,
                  CGS=2.414e-12, KF=9.882e-18, AF=1)


# =======================================================================
# 2. Circuit Construction
# =======================================================================
def build_guitar_preamp(pos1=1.0, pos2=0.5, pos3=0.5, pos4=0.00001, 
                        v_in_amp=0.3, v_in_freq=1000):
    """
    Builds the guitar preamp circuit with parameterized potentiometer positions.
    Returns a configured PySpice Circuit object.
    """
    circuit = Circuit('Guitar Preamp')
    inject_device_models(circuit)

    # Power and Signal Sources
    circuit.V('2', 'VCC', circuit.gnd, 15@u_V)
    circuit.SinusoidalVoltageSource('1', 'IN', circuit.gnd, amplitude=v_in_amp@u_V, frequency=v_in_freq@u_Hz)

    # Stage 1: JFET Input Buffer
    circuit.C('1', 'IN', 'N007', 22@u_nF)
    circuit.R('_gate', 'N007', circuit.gnd, 1@u_MΩ)
    circuit.R('_stop', 'N007', 'N008', 10@u_kΩ)
    circuit.J('1', 'VCC', 'N008', 'N010', model='2N3819')
    circuit.R('_source', 'N010', circuit.gnd, 10@u_kΩ)
    circuit.C('_out', 'N010', 'Q1B', 100@u_nF)

    # Stage 2: Gain Stage and Bias
    circuit.R('3', 'VCC', 'N004', 390@u_kΩ)
    circuit.R('5', 'N004', circuit.gnd, 48.2@u_kΩ)
    circuit.R('4', 'N004', 'Q1B', 220@u_kΩ)
    circuit.C('2', 'N004', circuit.gnd, 47@u_uF)
    circuit.BJT('1', 'Q1C', 'Q1B', 'Q1E', model='BC546B')
    circuit.R('8', 'Q1E', circuit.gnd, 560@u_Ω)
    circuit.R('6', 'VCC', 'Q1C', 2.2@u_kΩ)
    circuit.BJT('2', 'Q2C', 'Q1C', 'VCC', model='BC556B')
    circuit.C('3', 'Q2C', 'Q1C', 47@u_pF)
    circuit.R('7', 'Q2C', 'Q1E', 5.6@u_kΩ)

    # Tone Control / Clipping Network
    circuit.C('4', 'Q2C', 'MID_IN', 470@u_nF)
    circuit.R('10', 'MID_SIGNAL', 'MID_IN', 470@u_Ω)
    circuit.R('9', 'MID_IN', circuit.gnd, 47@u_kΩ)
    
    # P4: Drive Control
    circuit.R('P4', 'MID_SIGNAL', 'N006', 100e3 * pos1)

    circuit.Diode('1', 'P002', 'N006', model='1N4148')
    circuit.Diode('2', 'N006', 'P003', model='1N4148')
    circuit.Diode('3', 'N013', 'P002', model='1N4148')
    circuit.Diode('4', 'P003', 'N014', model='1N4148')
    circuit.C('5', 'N013', circuit.gnd, 10@u_uF)
    circuit.C('6', 'N014', circuit.gnd, 10@u_uF)
    circuit.R('11', 'N014', 'N013', 4.7@u_kΩ)

    circuit.R('12', 'MID_SIGNAL', 'N005', 10@u_kΩ)
    circuit.C('7', 'MID_SIGNAL', 'N001', 15@u_nF)

    # P1: Tone Control A
    circuit.R('P1a', 'N005', 'N011', 10e3 * pos2)
    circuit.R('P1b', 'N011', 'N015', 10e3 * (1 - pos2))
    circuit.R('14', 'N012', 'N011', 47@u_Ω)
    circuit.C('9', 'N012', circuit.gnd, 470@u_nF)
    circuit.R('13', 'N015', circuit.gnd, 100@u_Ω)

    # P2: Tone Control B
    circuit.R('P2a', 'N001', 'N003', 10e3 * pos3)
    circuit.R('P2b', 'N003', 'P001', 10e3 * (1 - pos3))
    circuit.R('15', 'P001', 'N012', 47@u_Ω)

    # Stage 3: Output Buffer
    circuit.C('10', 'N003', 'Q3B', 100@u_nF)
    circuit.R('17', 'VCC', 'N002', 10@u_kΩ)
    circuit.R('18', 'N002', 'Q3B', 10@u_kΩ)
    circuit.R('19', 'N002', circuit.gnd, 13.45@u_kΩ)
    circuit.BJT('3', 'VCC', 'Q3B', 'Q3E', model='BC546B')
    circuit.R('20', 'Q3E', circuit.gnd, 1@u_kΩ)
    circuit.C('11', 'Q3E', 'N002', 10@u_uF) 

    # P3: Output Volume Potentiometer
    circuit.C('12', 'N009', 'Q3E', 10@u_uF)
    circuit.R('P3a', 'N009', 'OUT', max(1e3 * pos4, 1e-3)) # Guard against 0 ohms
    circuit.R('P3b', 'OUT', circuit.gnd, max(1e3 * (1 - pos4), 1e-3))

    return circuit


# =======================================================================
# 3. Simulation Execution
# =======================================================================
def run_op_analysis(circuit):
    """Executes an Operating Point analysis and logs key node voltages."""
    simulator = circuit.simulator(temperature=27, nominal_temperature=27)
    analysis_op = simulator.operating_point()

    print("--- DC Operating Points ---")
    nodes_to_check = {
        'J1 Source (N010)': 'N010',
        'Bias R3/R4/R5 (N004)': 'N004',
        'Q1 Base (Q1B)': 'Q1B',
        'Q1 Collector (Q1C)': 'Q1C',
        'Q1 Emitter (Q1E)': 'Q1E',
        'Q2 Collector (Q2C)': 'Q2C',
        'Bias Q3 (N002)': 'N002',
        'Q3 Base (Q3B)': 'Q3B',
        'Q3 Emitter (Q3E)': 'Q3E'
    }

    for label, node in nodes_to_check.items():
        # Added [0] to safely extract scalar and avoid DeprecationWarning
        val = float(analysis_op[node][0])
        unit = "V"
        if abs(val) < 1:
            val *= 1000
            unit = "mV"
        print(f"{label:22s}: {val:.4f} {unit}")
        
    return analysis_op

def run_transient_analysis(circuit, step_time=10@u_us, end_time=20@u_ms):
    """Executes a Transient analysis and returns the results."""
    simulator = circuit.simulator(temperature=27, nominal_temperature=27)
    return simulator.transient(step_time=step_time, end_time=end_time)


# =======================================================================
# 4. Visualization
# =======================================================================
def plot_transient(analysis_tran, title='Guitar Preamp Transient Response'):
    """Plots Vin and Vout from a transient analysis."""
    plt.figure(figsize=(12, 6))

    time_ms = np.array(analysis_tran.time) * 1000
    vin = np.array(analysis_tran['IN'])
    vout = np.array(analysis_tran['OUT'])

    plt.plot(time_ms, vin, label='Vin (IN)', color='#1f77b4')
    plt.plot(time_ms, vout, label='Vout (OUT)', color='#ff7f0e')

    plt.title(title)
    plt.xlabel('Time [ms]')
    plt.ylabel('Voltage [V]')
    plt.legend(loc='upper right')
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.tight_layout()
    plt.show()


# =======================================================================
# Main Execution Block
# =======================================================================
if __name__ == '__main__':
    # 1. Build the circuit with default parameters
    my_preamp = build_guitar_preamp(pos1=1.0, pos2=0.5, pos3=0.5, pos4=0.00001)

    # 2. Run Operating Point Check
    run_op_analysis(my_preamp)

    # 3. Run Transient Simulation
    tran_results = run_transient_analysis(my_preamp)

    # 4. Plot Results
    plot_transient(tran_results)
```

After pasting this code in my Google Collab notebook, I got this:

[
![LTSpice simulation circuit](https://www.dropbox.com/scl/fi/dp8j1rj2dlg3b4ctr34gx/Captura-de-pantalla-2026-03-02-a-las-12.59.35.png?rlkey=jorx48j3ipnmpqid9pry0filz&st=xkydacv8&raw=1)](https://www.dropbox.com/scl/fi/dp8j1rj2dlg3b4ctr34gx/Captura-de-pantalla-2026-03-02-a-las-12.59.35.png?rlkey=jorx48j3ipnmpqid9pry0filz&st=xkydacv8&raw=1)

Which is consistent with the values I get from LTSpice.

