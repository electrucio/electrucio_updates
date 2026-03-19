import re
import os
import math

def parse_ltspice_log(filepath):
    """Parses an LTspice .log file and extracts key measurements."""

    if not os.path.exists(filepath):
        print(f"Error: Could not find the file '{filepath}'")
        return

    meas_data = {}
    thd_data = {}
    step_info = ""

    meas_pattern = re.compile(r'^(\w+):\s+.*?=\s*([+-]?\d+(?:\.\d+)?(?:e[+-]\d+)?)(?:\s+FROM.*)?$', re.IGNORECASE)
    fourier_node_pattern = re.compile(r'Fourier components of (V\([^)]+\)|I\([^)]+\))', re.IGNORECASE)
    thd_pattern = re.compile(r'Total Harmonic Distortion:\s+([0-9.]+)\%')
    step_pattern = re.compile(r'^Step Information:\s+(.*)$', re.IGNORECASE)

    current_fourier_node = None

    with open(filepath, 'r', encoding='utf-16-le', errors='replace') as f:
        for line in f:
            line = line.strip()

            step_match = step_pattern.match(line)
            if step_match:
                step_info = step_match.group(1)

            meas_match = meas_pattern.match(line)
            if meas_match:
                key = meas_match.group(1).lower()
                value = float(meas_match.group(2))
                meas_data[key] = value
                continue

            node_match = fourier_node_pattern.search(line)
            if node_match:
                current_fourier_node = node_match.group(1).upper()
                continue

            if current_fourier_node:
                thd_match = thd_pattern.search(line)
                if thd_match:
                    thd_data[current_fourier_node] = float(thd_match.group(1))
                    current_fourier_node = None

    print_report(meas_data, thd_data, step_info)

def print_report(meas, thd, step_info):
    """Formats and prints the parsed data into a friendly dashboard."""

    print("\n" + "="*105)
    print("🎸 GUITAR PREAMP SIMULATION REPORT (RED CIRCUITS DESIGN)")
    print("="*105)

    if step_info:
        print(f"\n  • Active Step : {step_info}")

    # --- 1. BIAS POINTS ---
    print("\n[ 1. BIAS POINTS (DC Operating Points) ]")
    print("-" * 105)
    print(f"  {'Node':<15} | {'Min (V)':>9} | {'Mean DC (V)':>11} | {'Max (V)':>9}")
    print("  " + "-" * 55)

    bias_nodes = [
        ("Q1 Base",  "vq1b"),
        ("Q2 Coll.", "vq2c"),
        ("Q3 Base",  "vq3b"),
        ("Q3 Emit.", "vq3e"),
    ]
    for label, key in bias_nodes:
        v_min  = meas.get(f'{key}_min')
        v_mean = meas.get(f'{key}_mean')
        v_max  = meas.get(f'{key}_max')
        if all(isinstance(x, float) for x in [v_min, v_mean, v_max]):
            print(f"  {label:<15} | {v_min:>9.4f} | {v_mean:>11.4f} | {v_max:>9.4f}")
        else:
            print(f"  {label:<15} | {'N/A':>9} | {'N/A':>11} | {'N/A':>9}")

    # --- 2. AC SIGNAL LEVELS ---
    print("\n[ 2. AC SIGNAL LEVELS (RMS & Peak-to-Peak) ]")
    print("-" * 105)
    ac_nodes = [
        ("Input (in)",   "vin"),
        ("Mid In",       "vmidin"),
        ("Tone In",      "vtonein"),
        ("Tone Out",     "vtoneout"),
        ("Output (out)", "vout"),
    ]
    for label, key in ac_nodes:
        v_min = meas.get(f'{key}_min')
        v_max = meas.get(f'{key}_max')
        v_rms = meas.get(f'{key}_rms')
        if isinstance(v_min, float) and isinstance(v_max, float):
            v_pp = v_max - v_min
            rms_str = f"{v_rms:>7.4f} Vrms" if isinstance(v_rms, float) else "     N/A Vrms"
            print(f"  • {label:<16}: {rms_str} | {v_pp:>7.4f} Vp-p")

    # --- 3. GAIN & VOLTAGE TRANSFER ---
    print("\n[ 3. GAIN & VOLTAGE TRANSFER ]")
    print("-" * 105)
    vgain = meas.get('voltage_gain')
    if isinstance(vgain, float) and vgain > 0:
        print(f"  • Overall Voltage Gain  : {vgain:>7.4f}x  ({20*math.log10(vgain):>6.2f} dB)")
    else:
        print(f"  • Overall Voltage Gain  : N/A")

    vin_rms  = meas.get('vin_rms')
    vout_rms = meas.get('vout_rms')
    if isinstance(vin_rms, float) and isinstance(vout_rms, float) and vin_rms > 0:
        calc_gain = vout_rms / vin_rms
        print(f"  • Gain (RMS ratio)      : {calc_gain:>7.4f}x  ({20*math.log10(calc_gain):>6.2f} dB)")

    clip_sym = meas.get('clip_symmetry')
    if isinstance(clip_sym, float):
        print(f"  • Clip Symmetry (Vout+/Vout-) : {clip_sym:.6f}  (1.0 = perfect)")

    # --- 4. IMPEDANCES ---
    print("\n[ 4. IMPEDANCES ]")
    print("-" * 105)
    zin = meas.get('zin_large')
    if isinstance(zin, float):
        zin_str = f"{zin/1e6:>7.2f} MΩ" if zin >= 1e6 else f"{zin/1e3:>7.1f} kΩ"
        print(f"  • Input Impedance (Zin)    : {zin_str}")

    zout_s1 = meas.get('zout_stage1')
    if isinstance(zout_s1, float):
        print(f"  • Stage 1 Output Z         : {zout_s1/1e3:>7.2f} kΩ")

    zout_eff = meas.get('zout_eff')
    if isinstance(zout_eff, float):
        print(f"  • Output Impedance (Zout)  : {zout_eff/1e3:>7.2f} kΩ")

    # --- 5. CLIPPING DIODES ---
    print("\n[ 5. CLIPPING DIODES ]")
    print("-" * 105)
    idiodes = meas.get('idiodes_peak')
    p_clip  = meas.get('p_clipping')
    if isinstance(idiodes, float):
        print(f"  • Diode Peak Current       : {idiodes*1e9:>8.4f} nA")
    if isinstance(p_clip, float):
        print(f"  • Clipping Power (avg)     : {p_clip*1e9:>8.4f} nW")

    # --- 6. TOTAL HARMONIC DISTORTION ---
    print("\n[ 6. TOTAL HARMONIC DISTORTION (THD) ]")
    print("-" * 105)
    if thd:
        for node, thd_val in thd.items():
            print(f"  • {node:<18} : {thd_val:>8.5f} %")
    else:
        print("  No THD data found.")

    print("\n" + "="*105 + "\n")

if __name__ == "__main__":
    log_file = os.path.join(os.path.dirname(__file__), "red_circuits_design.log")
    parse_ltspice_log(log_file)
