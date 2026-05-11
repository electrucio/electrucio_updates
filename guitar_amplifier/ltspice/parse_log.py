#!/usr/bin/env python3
"""
LTspice .log parser for the 40W quasi-complementary guitar amp.

Surfaces every relevant metric: bias health, headroom, distortion,
gains in V/V and dB, output power, PSRR, hum, transient response,
and consolidates findings into actionable warnings.

Usage:
    python3 parse_log.py [logfile]            # default: AudioAmpCompl-40W.log
    python3 parse_log.py path/to/sim.log
"""

import re
import os
import sys
import math


# ====================================================================
# DESIGN CONSTANTS — adjust if your topology / target spec changes
# ====================================================================

R_LOAD_NOMINAL    = 7.5    # Ω, speaker impedance for resistive power calc
NOMINAL_POWER_W   = 40     # W, design target into R_LOAD_NOMINAL
NOMINAL_BIAS_MA   = 40     # mA, output stage idle current per device target
RAIL_LOSS_V       = 3.5    # V, estimated total Vsat + Vbe drops on each rail (for clean-clip ceiling estimate)
DIODE_CLIP_THRESH = (1.35, -1.95)  # (positive, negative) volts, asymmetric clipper at TONE_IN


# ====================================================================
# PARSER — reads .meas results, Fourier blocks, sim metadata
# ====================================================================

def parse_ltspice_log(filepath):
    """Return {'meas','thd','fourier_mains','fourier_signal','meta'} or None."""
    if not os.path.exists(filepath):
        print(f"❌ File not found: {filepath}")
        return None

    meas, thd = {}, {}
    fourier_mains, fourier_signal = {}, {}    # node → {harmonic_freq_int: |magnitude|}
    failed_meas = []
    elapsed_s = None

    # Patterns
    meas_with_colon  = re.compile(r'^(\w+):\s+.*?=\s*([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)(?:\s+FROM.*)?$')
    meas_no_colon    = re.compile(r'^(\w+)=\s*([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)(?:\s+FROM.*)?$')
    fourier_header   = re.compile(r'Fourier components of V\(([^)]+)\)', re.IGNORECASE)
    harmonic_row     = re.compile(r'^\s*(\d+)\s+([0-9.eE+-]+)\s+([0-9.eE+-]+)')
    thd_row          = re.compile(r'Total Harmonic Distortion:\s+([0-9.eE+-]+)\s*%')
    elapsed_row      = re.compile(r'Total elapsed time:\s+([0-9.]+)')
    fail_row         = re.compile(r"Measurement '(\w+)' FAIL'ed", re.IGNORECASE)

    # Read with encoding fallback (LTspice on Mac writes UTF-16-LE)
    raw = None
    for enc in ('utf-16-le', 'utf-16', 'utf-8'):
        try:
            with open(filepath, 'r', encoding=enc) as f:
                raw = f.read()
            # Heuristic: a successful decode shouldn't have null chars left over
            if '\x00' not in raw[:200]:
                break
        except (UnicodeError, UnicodeDecodeError):
            raw = None
    if raw is None:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            raw = f.read()

    current_node = None
    current_base = None      # fundamental freq of the active Fourier block

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue

        em = elapsed_row.search(line)
        if em:
            elapsed_s = float(em.group(1))
            continue

        fm = fail_row.search(line)
        if fm:
            failed_meas.append(fm.group(1))
            continue

        # Fourier block start (resets state)
        nm = fourier_header.search(line)
        if nm:
            current_node = nm.group(1).lower()
            current_base = None
            continue

        # Inside a Fourier block?
        if current_node:
            hm = harmonic_row.match(line)
            if hm:
                hnum = int(hm.group(1))
                freq = float(hm.group(2))
                mag  = abs(float(hm.group(3)))
                if hnum == 1:
                    current_base = freq
                if current_base is None:
                    continue
                bucket = fourier_mains if abs(current_base - 50) < 1 else fourier_signal
                bucket.setdefault(current_node, {})[int(round(freq))] = mag
                continue

            tm = thd_row.search(line)
            if tm:
                # Only capture THD for the SIGNAL fundamental (ignore mains-block "THD")
                if current_base is not None and abs(current_base - 50) > 1:
                    thd[current_node] = float(tm.group(1))
                continue
            # Allow .meas lines to appear interleaved — fall through to general patterns

        m = meas_with_colon.match(line) or meas_no_colon.match(line)
        if m:
            meas[m.group(1).lower()] = float(m.group(2))

    return {
        'meas': meas,
        'thd': thd,
        'fourier_mains': fourier_mains,
        'fourier_signal': fourier_signal,
        'meta': {'elapsed_s': elapsed_s, 'failed': failed_meas},
    }


# ====================================================================
# HELPERS
# ====================================================================

def db(x):
    """Linear ratio → dB, or None if non-positive/None."""
    if x is None or x <= 0:
        return None
    return 20 * math.log10(x)


def fmt(v, w=8, p=4, na='N/A'):
    return f"{v:>{w}.{p}f}" if isinstance(v, (int, float)) else f"{na:>{w}}"


def assess_vbe(vb, ve, polarity):
    """Return (vbe, status) — health classification."""
    if vb is None or ve is None:
        return None, "❓ N/A"
    vbe = vb - ve
    if polarity == 'NPN':
        if   0.45 <= vbe <= 0.75: return vbe, "✅ Active"
        elif 0.75 <  vbe <= 0.85: return vbe, "⚠️ Near sat"
        elif vbe > 0.85:          return vbe, "❌ Saturated"
        elif vbe < 0.40:          return vbe, "❌ Cutoff"
        else:                     return vbe, "⚠️ Sub-thresh"
    else:  # PNP
        if   -0.75 <= vbe <= -0.45: return vbe, "✅ Active"
        elif -0.85 <= vbe <  -0.75: return vbe, "⚠️ Near sat"
        elif vbe < -0.85:           return vbe, "❌ Saturated"
        elif vbe > -0.40:           return vbe, "❌ Cutoff"
        else:                       return vbe, "⚠️ Sub-thresh"


def hr(char='─', n=110):
    return char * n


# ====================================================================
# REPORT — one section per physical concern
# ====================================================================

def report(parsed):
    if parsed is None:
        return

    M    = parsed['meas']
    THD  = parsed['thd']
    F50  = parsed['fourier_mains']
    FSIG = parsed['fourier_signal']
    META = parsed['meta']
    warnings = []

    print("\n" + "═" * 110)
    print("🎸 40W QUASI-COMPLEMENTARY GUITAR AMP — SIMULATION REPORT")
    print("═" * 110)

    # ---- 0. METADATA --------------------------------------------------------
    print(f"\n[ 0. SIMULATION CONTEXT ]")
    print(hr())
    elapsed = META.get('elapsed_s')
    print(f"  Sim runtime        : {elapsed:.2f} s" if elapsed else "  Sim runtime        : N/A")
    print(f"  Measurements parsed: {len(M)}")
    print(f"  THD blocks captured: {len(THD)}    (signal-fundamental Fourier blocks)")
    print(f"  Mains blocks       : {len(F50)}    (50 Hz Fourier blocks)")
    failed = META.get('failed', [])
    if failed:
        print(f"  ❌ Failed .meas    : {len(failed)}")
        for name in failed:
            print(f"       - {name}")
        warnings.append(f"{len(failed)} .meas statements FAILed — check directives file")

    # ---- 1. POWER SUPPLY ----------------------------------------------------
    print(f"\n[ 1. POWER SUPPLY (VRAW) ]")
    print(hr())
    vraw    = M.get('vraw_mean', 0) or 0
    ripple  = M.get('vraw_ripple', 0) or 0
    print(f"  VRAW (main rail)         : {vraw:7.2f} V")
    print(f"  VRAW ripple (p-p)        : {ripple*1000:7.2f} mV   ({(ripple/vraw*100 if vraw else 0):.3f}% of rail)")
    if ripple > 0.5:
        warnings.append(f"VRAW ripple {ripple*1000:.0f} mV — verify reservoir cap sizing")

    # ---- 2. DC OPERATING POINTS ---------------------------------------------
    print(f"\n[ 2. DC OPERATING POINTS — TRANSISTOR HEALTH ]")
    print(hr())

    # (display name, polarity, V_b key, V_e key | None means GND, role)
    transistors = [
        ("Q12 BC546B",  'NPN', 'vq12b_mean', 'vq12e_mean', "Preamp stage 1 (cascode)"),
        ("Q8  BC546B",  'NPN', 'vq8b_mean',  'vq8e_mean',  "Preamp stage 1 (input)"),
        ("Q10 BC556B",  'PNP', 'vq10b_mean', 'vq10e_mean', "Preamp stage 2 PNP"),
        ("Q11 BC546B",  'NPN', 'vq11b_mean', 'vq11e_mean', "Output buffer (post-tone)"),
        ("Q1  BC556B",  'PNP', 'vq1b_mean',  'vq1e_mean',  "Power amp input pair"),
        ("Q2  BD139",   'NPN', 'vq2b_mean',   None,        "VAS (emitter at GND)"),
        ("Q6  2SD896",  'NPN', 'vq6b_mean',  'vq6e_mean',  "Output upper (Darlington)"),
        ("Q7  2SD896",  'NPN', 'vq7b_mean',   None,        "Output lower (Sziklai, E=GND)"),
    ]
    print(f"  {'Transistor':<13} | {'V_b':>7} | {'V_e':>7} | {'V_be':>7} | {'Status':<14} | Role")
    print("  " + "─" * 108)
    for name, pol, kb, ke, role in transistors:
        vb = M.get(kb)
        ve = 0.0 if ke is None else M.get(ke)
        vbe, status = assess_vbe(vb, ve, pol)
        # Sziklai exception: Q7 lower-output Vbe is set by Q5 feedback, can sit <0.45V at idle
        if name.startswith("Q7") and vbe is not None and 0.30 < vbe < 0.45:
            status = "✅ Sziklai idle"
        print(f"  {name:<13} | {fmt(vb,7,2)} | {fmt(ve,7,2)} | {fmt(vbe,7,3)} | {status:<14} | {role}")
        if vbe is not None and not name.startswith("Q7"):
            if pol == 'NPN' and vbe > 0.85:
                warnings.append(f"{name}: Vbe={vbe:.2f} V suggests saturation")
            if pol == 'PNP' and vbe < -0.85:
                warnings.append(f"{name}: Vbe={vbe:.2f} V suggests saturation")

    # ----- Output stage bias -------------------------------------------------
    iq6 = (M.get('iq_r16_real', M.get('iq6_bias', 0)) or 0) * 1000
    iq7 = (M.get('iq_r17_real', M.get('iq7_bias', 0)) or 0) * 1000
    iq_avg = M.get('iq_through_output', (abs(iq6) + abs(iq7)) / 2)
    pickup_max = M.get('vpickup_in_max', 0) or 0
    pickup_min = M.get('vpickup_in_min', 0) or 0
    pickup_pp  = pickup_max - pickup_min
    signal_present = pickup_pp > 1e-4

    print(f"\n  Output stage current:")
    print(f"    I(R16) Q6 path         : {iq6:7.2f} mA")
    print(f"    I(R17) Q7 path         : {iq7:7.2f} mA")
    print(f"    Average               : {iq_avg:7.2f} mA   (target ~{NOMINAL_BIAS_MA} mA)")
    print(f"    Asymmetry (R17 − R16) : {iq7 - iq6:+7.2f} mA   (structural for quasi-complementary)")
    if signal_present:
        print(f"    ⚠️ Signal present ({pickup_pp*1000:.1f} mVp-p at PICKUP_IN) — these readings include")
        print(f"       signal current, not pure quiescent. Re-run with in_amplitude=0 for true bias.")
    elif iq_avg > 60:
        warnings.append(f"True quiescent Iq={iq_avg:.0f} mA — verify RV2 trim")

    # ----- Output midpoint (RV1 trim hint) -----------------------------------
    pre_spk_mean = M.get('vpre_speaker_mean')
    if pre_spk_mean is not None and vraw > 0:
        ideal = vraw / 2
        offset = pre_spk_mean - ideal
        marker = "✅" if abs(offset) < 0.5 else ("⚠️" if abs(offset) < 1.5 else "❌")
        print(f"\n  Output DC midpoint (PRE_SPEAKER): {pre_spk_mean:.3f} V")
        print(f"    Ideal (VRAW/2)                 : {ideal:.3f} V")
        print(f"    Offset                          : {offset:+.3f} V  {marker}")
        if abs(offset) > 1.0:
            warnings.append(f"PRE_SPEAKER offset {offset:+.2f} V → re-trim RV1")

    # ----- Vbe-multiplier voltage (derived) ----------------------------------
    vq2c = M.get('vq2c_mean')
    vq6b = M.get('vq6b_mean')
    if vq2c is not None and vq6b is not None:
        v_stack = vq6b - vq2c
        print(f"\n  Output Vbe stack (V(Q6B) − V(Q2C)) : {v_stack:.3f} V")
        print(f"    Carries Vbe_Q4 + Vbe_Q6 + Vbe_Q5 + I·R12 + I·R13 — sets quiescent")
        print(f"    Tune via RV2 if quiescent is off-target")

    # ----- Per-device idle dissipation ---------------------------------------
    if not signal_present and iq_avg < 200 and vraw > 0:
        p_dev = (iq_avg / 1000) * (vraw / 2)
        print(f"\n  Idle dissipation per output device : ~{p_dev:.2f} W (Q6, Q7)")
        print(f"    Heatsink must handle 2× this + signal-driven dissipation at full power")

    # ---- 3. SIGNAL HEADROOM -------------------------------------------------
    print(f"\n[ 3. SIGNAL LEVELS — PEAK / RMS / HEADROOM ]")
    print(hr())

    # (label, key_prefix, dc_floor, dc_ceiling) — None disables headroom check
    nodes = [
        ("PICKUP_IN",     "vpickup_in",   None, None),
        ("TONE_IN",       "vtone_in",     None, None),
        ("TONE_OUT",      "vtone_out",    None, None),
        ("Q11B (buf in)", "vq11b",        None, None),
        ("Q11E (buf out)","vq11e",        0.7,  vraw - 0.5 if vraw else None),
        ("PREAMP_OUT",    "vpreamp_out",  None, None),
        ("PRE_SPEAKER",   "vpre_speaker", RAIL_LOSS_V, vraw - RAIL_LOSS_V if vraw else None),
        ("SPEAKER (AC)",  "vspeaker",     -(vraw/2 - RAIL_LOSS_V) if vraw else None,
                                          +(vraw/2 - RAIL_LOSS_V) if vraw else None),
    ]
    print(f"  {'Node':<16} | {'Vmin':>9} | {'Vmean':>9} | {'Vmax':>9} | {'Vrms':>9} | {'Vp-p':>8} | {'Crest':>5} | Headroom (neg/pos)")
    print("  " + "─" * 108)
    for label, key, floor, ceil in nodes:
        vmin = M.get(f'{key}_min')
        vmax = M.get(f'{key}_max')
        vmean = M.get(f'{key}_mean')
        vrms  = M.get(f'{key}_rms')
        if vmin is None or vmax is None:
            print(f"  {label:<16} | (no data)")
            continue
        if vmean is None:
            vmean = (vmax + vmin) / 2
        vpp = vmax - vmin

        # AC RMS, then crest factor of the AC component
        crest_s = f"{'N/A':>5}"
        if vrms is not None and vrms > 1e-9:
            ac_var = max(0, vrms**2 - vmean**2)
            ac_rms = math.sqrt(ac_var)
            if ac_rms > 1e-9:
                vpeak = max(abs(vmax - vmean), abs(vmean - vmin))
                crest_s = f"{vpeak/ac_rms:>5.2f}"

        # Headroom utilization
        hr_s = ""
        if floor is not None and ceil is not None and ceil > floor:
            neg_room = vmean - floor
            pos_room = ceil  - vmean
            neg_used = (vmean - vmin) / neg_room * 100 if neg_room > 0 else 999
            pos_used = (vmax - vmean) / pos_room * 100 if pos_room > 0 else 999
            worst = max(neg_used, pos_used)
            mark = "❌" if worst > 95 else ("⚠️" if worst > 80 else "✅")
            hr_s = f"{neg_used:>5.1f}% ↓ / {pos_used:>5.1f}% ↑  {mark}"
            if worst > 95:
                warnings.append(f"{label}: headroom {worst:.0f}% used — clipping likely")

        print(f"  {label:<16} | {fmt(vmin,9,4)} | {fmt(vmean,9,4)} | {fmt(vmax,9,4)} | {fmt(vrms,9,4)} | {fmt(vpp,8,4)} | {crest_s} | {hr_s}")

    # ---- 4. GAIN STAGING ----------------------------------------------------
    print(f"\n[ 4. GAIN STAGING — V/V & dB ]")
    print(hr())
    gains = [
        ("Stage 1 preamp (PICKUP→TONE_IN)",       'gain_pre_stage1'),
        ("Tone stack ratio (TONE_IN→TONE_OUT)",   'tonestack_loss'),
        ("Q11 buffer transparency",               'buffer_gain_q11'),
        ("Master volume (P3) attenuation",        'mastervol_atten'),
        ("Stage 2 combined (TONE_OUT→PREAMP_OUT)",'gain_pre_stage2'),
        ("──────────────────────────────────",     None),
        ("Total preamp (PICKUP→PREAMP_OUT)",      'gain_total_preamp'),
        ("Power amp (PREAMP_OUT→SPEAKER)",        'gain_poweramp'),
        ("System total (PICKUP→SPEAKER)",         'gain_system_total'),
    ]
    print(f"  {'Stage':<42} | {'Linear':>10} | {'dB':>10}")
    print("  " + "─" * 70)
    for label, key in gains:
        if key is None:
            print(f"  {label}")
            continue
        g = M.get(key)
        if g is None:
            print(f"  {label:<42} | {'N/A':>10} | {'N/A':>10}")
        else:
            d = db(g)
            d_s = f"{d:>+8.2f} dB" if d is not None else f"{'N/A':>10}"
            print(f"  {label:<42} | {g:>10.4f} | {d_s}")

    # Sanity check: Stage1 × ToneStack × Stage2 should equal total preamp
    g1 = M.get('gain_pre_stage1'); gt = M.get('tonestack_loss')
    g2 = M.get('gain_pre_stage2'); gtot = M.get('gain_total_preamp')
    if all(x is not None for x in [g1, gt, g2, gtot]) and gtot > 0:
        computed = g1 * gt * g2
        err = abs(computed - gtot) / gtot * 100
        mark = "✅" if err < 5 else "⚠️"
        print(f"\n  Sanity: Stage1 × ToneStack × Stage2 = {computed:.4f} vs reported total = {gtot:.4f}  {mark} (Δ {err:.1f}%)")

    # ---- 5. OUTPUT POWER ----------------------------------------------------
    print(f"\n[ 5. OUTPUT POWER ]")
    print(hr())
    vspk_rms = M.get('vspeaker_rms', 0) or 0
    vspk_max = M.get('vspeaker_max', 0) or 0
    vspk_min = M.get('vspeaker_min', 0) or 0
    p_meas   = M.get('speaker_rms_power', 0) or 0
    vspk_pk  = max(abs(vspk_max), abs(vspk_min))
    p_calc   = (vspk_rms ** 2) / R_LOAD_NOMINAL if vspk_rms else 0

    print(f"  V(SPEAKER) RMS                    : {vspk_rms:7.4f} V")
    print(f"  V(SPEAKER) peak                   : {vspk_pk:7.4f} V")
    print(f"  P_out (resistive {R_LOAD_NOMINAL}Ω calc)      : {p_calc:7.4f} W")
    print(f"  P_out (.meas with reactive load)  : {p_meas:7.4f} W")
    if NOMINAL_POWER_W:
        print(f"  Fraction of nominal {NOMINAL_POWER_W}W           : {p_calc/NOMINAL_POWER_W*100:6.2f} %")

    # ---- VRAW supply power (the realistic one) -------------------------------
    # Single-supply class-AB: only the upper output device pulls from VRAW.
    # I_VRAW(t) ≈ I_q + max(0, I_load(t))  →  averaged over a sine cycle:
    #   I_VRAW_avg ≈ I_q + I_pk / π     where I_pk = V_pk_speaker / R_load
    #
    # If signal is contaminating Iq6 (signal_present), fall back to nominal
    # design target NOMINAL_BIAS_MA so the idle term doesn't double-count.
    if vraw > 0:
        if signal_present:
            iq_for_calc = NOMINAL_BIAS_MA / 1000   # use design target — measured iq6 is signal-contaminated
            iq_source = f"design target {NOMINAL_BIAS_MA} mA (measured Iq6 contaminated by signal)"
        else:
            iq_for_calc = abs(iq6) / 1000
            iq_source = f"measured I(R16) = {iq6:.1f} mA"

        i_pk_load = vspk_pk / R_LOAD_NOMINAL
        i_signal_avg = i_pk_load / math.pi
        i_vraw_avg = iq_for_calc + i_signal_avg
        p_vraw = vraw * i_vraw_avg
        p_idle_only = vraw * iq_for_calc
        p_signal_extra = vraw * i_signal_avg

        print(f"\n  ─── VRAW supply consumption (estimated) ───")
        print(f"  Idle current (upper half from VRAW): {iq_for_calc*1000:6.2f} mA   [{iq_source}]")
        print(f"  Signal-driven avg current (I_pk/π) : {i_signal_avg*1000:6.2f} mA")
        print(f"  Total avg current from VRAW        : {i_vraw_avg*1000:6.2f} mA")
        print(f"  P_VRAW idle component              : {p_idle_only:6.2f} W")
        print(f"  P_VRAW signal component            : {p_signal_extra:6.2f} W")
        print(f"  P_VRAW TOTAL                       : {p_vraw:6.2f} W")
        if p_vraw > 0.1 and p_calc > 0.001:
            eff = p_calc / p_vraw * 100
            print(f"  Efficiency (P_out / P_VRAW)        : {eff:5.1f} %   (class-AB max ~78.5% at full clip)")

    if vraw > 0:
        v_pk_clean = vraw/2 - RAIL_LOSS_V
        p_max_clean = (v_pk_clean ** 2) / 2 / R_LOAD_NOMINAL
        i_pk_clean = v_pk_clean / R_LOAD_NOMINAL
        p_vraw_at_clean = vraw * (NOMINAL_BIAS_MA/1000 + i_pk_clean/math.pi)
        eff_at_clean = p_max_clean / p_vraw_at_clean * 100
        print(f"\n  ─── At theoretical clean-clip ceiling ───")
        print(f"  Max clean P_out (Vraw/2 − {RAIL_LOSS_V}V) : {p_max_clean:6.2f} W")
        print(f"  P_VRAW at clean clip               : {p_vraw_at_clean:6.2f} W")
        print(f"  Efficiency at clean clip           : {eff_at_clean:5.1f} %")
        if p_calc > 0.01:
            print(f"  Headroom remaining from current op : {p_max_clean/p_calc:.1f}× before clip")

    print(f"\n  📖 For an exact (vs. estimated) P_VRAW, add a 0V sense source in series with the")
    print(f"     reservoir cap output and measure: .meas tran I_VRAW_avg AVG I(V_sense)")
    print(f"     then: .meas tran P_VRAW_avg PARAM Vraw_mean * abs(I_VRAW_avg)")

    # ---- 6. DISTORTION ------------------------------------------------------
    print(f"\n[ 6. DISTORTION (signal-frequency Fourier) ]")
    print(hr())
    print(f"  THD by node:")
    for node in ['preamp_out', 'pre_speaker', 'speaker']:
        t = THD.get(node)
        if t is None:
            print(f"    {node.upper():<14} : {'N/A':>9}")
        else:
            mark = "✅ clean" if t < 0.5 else ("⚠️ moderate" if t < 5 else "❗ heavy")
            print(f"    {node.upper():<14} : {t:>8.4f} %   {mark}")

    sym_pre = M.get('clip_sym_preamp', 0) or 0
    sym_pwr = M.get('clip_sym_power', 0) or 0
    print(f"\n  Symmetry (1.000 = perfectly symmetric):")
    print(f"    Preamp                       : {sym_pre:.4f}   ({(sym_pre-1)*100:+.2f}% asymmetry)")
    print(f"    Power amp                    : {sym_pwr:.4f}   ({(sym_pwr-1)*100:+.2f}% asymmetry)")

    pk_pos = M.get('vtone_in_pk_pos', 0) or 0
    pk_neg = M.get('vtone_in_pk_neg', 0) or 0
    pos_thr, neg_thr = DIODE_CLIP_THRESH
    pos_engaged = pk_pos > pos_thr
    neg_engaged = pk_neg < neg_thr
    print(f"\n  Diode clipper at TONE_IN:")
    print(f"    Positive peak {pk_pos:+7.3f} V  (threshold {pos_thr:+.2f} V)  {'❗ ENGAGED' if pos_engaged else '✅ off'}")
    print(f"    Negative peak {pk_neg:+7.3f} V  (threshold {neg_thr:+.2f} V)  {'❗ ENGAGED' if neg_engaged else '✅ off'}")

    # Top non-fundamental harmonics at SPEAKER
    spk_h = FSIG.get('speaker', {})
    if spk_h:
        # Detect fundamental as the lowest non-zero freq in the dict
        freqs_sorted = sorted(spk_h.keys())
        fund_freq = freqs_sorted[0] if freqs_sorted else None
        fund_mag = spk_h.get(fund_freq, 0) if fund_freq else 0
        if fund_mag > 0:
            print(f"\n  Top harmonics at SPEAKER (rel. to {fund_freq} Hz fundamental {fund_mag:.4e} V):")
            harmonics_only = {f: m for f, m in spk_h.items() if f != fund_freq}
            top = sorted(harmonics_only.items(), key=lambda x: -x[1])[:5]
            for f, m in top:
                rel_pct = m / fund_mag * 100
                rel_db  = db(m / fund_mag)
                print(f"    {f:>6} Hz : {m:.4e} V  ({rel_pct:7.4f}% / {rel_db:+6.1f} dBc)")

    # ---- 7. TRANSIENT RESPONSE ---------------------------------------------
    print(f"\n[ 7. TRANSIENT RESPONSE ]")
    print(hr())
    rt = M.get('rise_time')
    ft = M.get('fall_time')
    def fmt_time(t):
        if t is None: return "      N/A"
        if t < 0:     return f"{t*1e6:+8.1f} µs  ⚠️ negative — input wasn't a square wave"
        return f"{t*1e6:8.2f} µs   →  BW ≈ {0.35/t/1e3:.1f} kHz"
    print(f"  Rise time (10%–90%) : {fmt_time(rt)}")
    print(f"  Fall time (90%–10%) : {fmt_time(ft)}")
    print(f"\n  📖 For a stability check, drive PICKUP_IN with a small square wave")
    print(f"     (e.g. PULSE(-0.05 0.05 0 1u 1u 0.5m 1m)) and look for clean edges with no ringing.")

    # ---- 8. PSU NOISE / HUM -------------------------------------------------
    print(f"\n[ 8. POWER-SUPPLY NOISE / HUM (50 Hz harmonics) ]")
    print(hr())
    print(f"  All values in mV (absolute Fourier magnitude). PSRR = 20·log10(VRAW / PREAMP_OUT).\n")
    print(f"  {'Freq':>6} | {'VRAW (mV)':>12} | {'PREAMP_OUT (mV)':>16} | {'SPEAKER (mV)':>14} | PSRR (preamp)")
    print("  " + "─" * 90)
    for f in [50, 100, 150, 200, 250, 300]:
        v_raw = F50.get('n002', {}).get(f, 0) * 1000
        v_pre = F50.get('preamp_out', {}).get(f, 0) * 1000
        v_spk = F50.get('speaker', {}).get(f, 0) * 1000
        psrr_s = ""
        if v_raw > 1e-6 and v_pre > 1e-9:
            psrr_db = 20 * math.log10(v_raw / v_pre)
            psrr_s = f"{psrr_db:>+6.1f} dB"
        print(f"  {f:>4} Hz | {v_raw:>12.4f} | {v_pre:>16.6f} | {v_spk:>14.4f} | {psrr_s}")

    # Hum SNR at speaker (signal RMS / 100Hz hum)
    hum_at_spk_v = F50.get('speaker', {}).get(100, 0)
    if hum_at_spk_v > 1e-12 and vspk_rms > 1e-9:
        snr = 20 * math.log10(vspk_rms / hum_at_spk_v)
        mark = "✅" if snr > 70 else ("⚠️" if snr > 50 else "❌")
        print(f"\n  Hum SNR at SPEAKER (signal_rms / 100Hz hum) : {snr:+6.1f} dB  {mark}")
        if snr < 60:
            warnings.append(f"Hum SNR only {snr:.0f} dB at SPEAKER — verify supply filtering")

    # ---- 9. NOTES & WARNINGS ------------------------------------------------
    print(f"\n[ 9. NOTES, CAVEATS & WARNINGS ]")
    print(hr())
    print(f"  📖 Impedances (Zin, Zout) are NOT derivable from transient .meas alone.")
    print(f"     Add an .ac sweep + AC source at PICKUP_IN, measure I(R52) for Zin,")
    print(f"     and a load-step transient with V_test in series with the speaker for Zout.")
    print()
    if not warnings:
        print(f"  ✅ No issues detected.")
    else:
        for i, w in enumerate(warnings, 1):
            print(f"  ⚠️ [{i}] {w}")

    print("\n" + "═" * 110 + "\n")


# ====================================================================
# ENTRY
# ====================================================================

if __name__ == "__main__":
    log_file = sys.argv[1] if len(sys.argv) > 1 else "AudioAmpCompl-40W.log"
    parsed = parse_ltspice_log(log_file)
    if parsed:
        report(parsed)
