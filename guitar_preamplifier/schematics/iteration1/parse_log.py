import re
import os

def parse_ltspice_log(filepath):
    """Parses an LTspice .log file and extracts key measurements."""
    
    if not os.path.exists(filepath):
        print(f"Error: Could not find the file '{filepath}'")
        return

    meas_data = {}
    thd_data = {}
    params_data = {}
    step_info = ""
    
    # Regex patterns
    meas_pattern = re.compile(r'^(\w+):\s+.*?=\s*([+-]?\d+(?:\.\d+)?(?:e[+-]\d+)?)(?:\s+FROM.*)?$', re.IGNORECASE)
    fourier_node_pattern = re.compile(r'Fourier components of (V\([^)]+\)|I\([^)]+\))', re.IGNORECASE)
    thd_pattern = re.compile(r'Total Harmonic Distortion:\s+([0-9.]+)\%')
    step_pattern = re.compile(r'^Step Information:\s+(.*)$', re.IGNORECASE)

    current_fourier_node = None

    # 1. Parse the .log file
    with open(filepath, 'r', encoding='utf-16-le', errors='replace') as f:
        for line in f:
            line = line.strip()
            
            # Check if this is a stepped simulation
            step_match = step_pattern.match(line)
            if step_match:
                step_info = step_match.group(1)
            
            # Parse .meas variables
            meas_match = meas_pattern.match(line)
            if meas_match:
                key = meas_match.group(1).lower()
                value = float(meas_match.group(2))
                meas_data[key] = value
                continue
                
            # Track which node the Fourier analysis is currently looking at
            node_match = fourier_node_pattern.search(line)
            if node_match:
                current_fourier_node = node_match.group(1).upper()
                continue
                
            # Extract THD for the current node
            if current_fourier_node:
                thd_match = thd_pattern.search(line)
                if thd_match:
                    thd_data[current_fourier_node] = float(thd_match.group(1))
                    current_fourier_node = None 

    # 2. Parse the .net file for static parameters (drive, tone, etc.)
    net_file = filepath[:-4] + '.net'
    if os.path.exists(net_file):
        # Matches: .param drive=0.5 or .param drive = 0.5
        param_pattern = re.compile(r'^\.param\s+(\w+)\s*=\s*([+-]?\d+(?:\.\d+)?(?:e[+-]\d+)?)', re.IGNORECASE)
        with open(net_file, 'r', encoding='utf-16-le', errors='replace') as f:
            for line in f:
                match = param_pattern.search(line.strip())
                if match:
                    params_data[match.group(1).lower()] = float(match.group(2))

    print_report(meas_data, thd_data, params_data, step_info)

def print_report(meas, thd, params, step_info):
    """Formats and prints the parsed data into a friendly dashboard."""
    
    print("\n" + "="*95)
    print("🎸 GUITAR PREAMP SIMULATION REPORT")
    print("="*95)

    # --- 0. SIMULATION PARAMETERS ---
    print("\n[ 0. SIMULATION PARAMETERS ]")
    print("-" * 95)
    if step_info:
        print(f"  • Active Step : {step_info}")
    
    if params:
        print(f"  • Drive       : {params.get('drive', 'N/A')}")
        print(f"  • Bass        : {params.get('bass', 'N/A')}")
        print(f"  • Treble      : {params.get('treble', 'N/A')}")
        print(f"  • Volume      : {params.get('vol', 'N/A')}")
        print(f"  • Input Ampl. : {params.get('in_amplitude', 'N/A')} V")
        print(f"  • Input Freq  : {params.get('in_freq', 'N/A')} Hz")
    else:
        print("  • No explicit numeric .param definitions found in .net file.")

    # --- 1. BIAS & TRUE HEADROOM ANALYSIS ---
    print("\n[ 1. BIAS & TRUE HEADROOM ANALYSIS ]")
    print("-" * 95)
    print("  * Note: 'Floor' and 'Ceiling' represent the physical clipping limits of your topology.")
    print("  * 'Ideal DC' is the exact midpoint for maximum symmetrical headroom before clipping.")
    print(f"\n  {'Node':<11} | {'Floor':>6} | {'Ceil.':>6} | {'Ideal':>6} || {'Min (V)':>7} | {'Mean DC':>7} | {'Max (V)':>7} || {'%Neg Used':>9} | {'%Pos Used':>9}")
    print("  " + "-" * 93)

    v_q1e = meas.get('vq1e_mean', 4.33)  
    v_q2e = meas.get('vq2e_mean', 13.98) 
    v_q3e = meas.get('vq3e_mean', 1.28)  

    nodes = [
        ("Q1 Base",   "vq1b", 0.0,   v_q2e),
        ("Q2 Coll.",  "vq2c", v_q1e, v_q2e),
        ("Q3 Base",   "vq3b", 0.0,   v_q2e),
        ("Q3 Emit.",  "vq3e", 0.0,   v_q2e),
        ("Q3C / Q4B", "vq3c", v_q3e, v_q2e), 
        ("Q4 Emit.",  "vq4e", 0.0,   v_q2e)
    ]

    for label, key, floor, ceiling in nodes:
        v_min  = meas.get(f'{key}_min', 'N/A')
        v_mean = meas.get(f'{key}_mean', 'N/A')
        v_max  = meas.get(f'{key}_max', 'N/A')
        
        ideal_dc = (floor + ceiling) / 2.0
        
        if isinstance(v_min, float) and isinstance(v_mean, float) and isinstance(v_max, float):
            neg_swing = v_mean - v_min
            pos_swing = v_max - v_mean
            
            neg_headroom = v_mean - floor
            pos_headroom = ceiling - v_mean
            
            pct_neg = max(0, min(100, (neg_swing / neg_headroom) * 100)) if neg_headroom > 0 else 100
            pct_pos = max(0, min(100, (pos_swing / pos_headroom) * 100)) if pos_headroom > 0 else 100
            
            f_neg = f"{pct_neg:>8.1f}%"
            f_pos = f"{pct_pos:>8.1f}%"
        else:
            f_neg, f_pos = "N/A", "N/A"

        f_ideal = f"{ideal_dc:>5.2f}V"
        f_min   = f"{v_min:>7.3f}" if isinstance(v_min, float) else f"{v_min:>7}"
        f_mean  = f"{v_mean:>7.3f}" if isinstance(v_mean, float) else f"{v_mean:>7}"
        f_max   = f"{v_max:>7.3f}" if isinstance(v_max, float) else f"{v_max:>7}"
        
        print(f"  {label:<11} | {floor:>5.2f}V | {ceiling:>5.2f}V | {f_ideal} || {f_min} | {f_mean} | {f_max} || {f_neg} | {f_pos}")
    
    print("\nCurrent Draw & Power:")
    iq1 = abs(meas.get('iq1_bias', 0)) * 1000
    iq3 = abs(meas.get('iq3_bias', 0)) * 1000
    print(f"  • Q1/Q2 Stage Bias Curr : {iq1:>7.3f} mA")
    print(f"  • Q3 Stage Bias Curr    : {iq3:>7.3f} mA")
    print(f"  • Total Power Draw      : {meas.get('power_total_mw', 'N/A'):>7.3f} mW")
    
    print("\nWaveform Symmetry (1.000 is perfectly symmetrical):")
    print(f"  • At Diodes (Tone In)   : {meas.get('clip_symmetry_diodes', 'N/A'):>7.3f}")
    print(f"  • Final Output          : {meas.get('clip_symmetry_out', 'N/A'):>7.3f}")

    # --- 2. AC SIGNAL LEVELS ---
    print("\n[ 2. AC SIGNAL LEVELS (Unbiased/AC-Coupled Nodes) ]")
    print("-" * 95)
    print(f"  {'Node':<15} | {'Min (V)':>10} | {'Mean DC':>10} | {'Max (V)':>10} | {'RMS (V)':>10} | {'Vp-p (V)':>10}")
    print("  " + "-" * 76)

    ac_nodes = [
        ("Input (IN)", "vin"),
        ("Mid In", "vmidin"),
        ("Tone In", "vtonein"),
        ("Tone Out", "vtoneout"),
        ("Final Out", "vout")
    ]

    for label, key in ac_nodes:
        v_min  = meas.get(f'{key}_min', 'N/A')
        v_mean = meas.get(f'{key}_mean', 'N/A')
        v_max  = meas.get(f'{key}_max', 'N/A')
        v_rms  = meas.get(f'{key}_rms', 'N/A')

        if isinstance(v_min, float) and isinstance(v_max, float):
            v_pp = v_max - v_min
            f_pp = f"{v_pp:>10.3f}"
        else:
            f_pp = "       N/A"

        f_min  = f"{v_min:>10.3f}" if isinstance(v_min, float) else f"{v_min:>10}"
        f_mean = f"{v_mean:>10.3f}" if isinstance(v_mean, float) else f"{v_mean:>10}"
        f_max  = f"{v_max:>10.3f}" if isinstance(v_max, float) else f"{v_max:>10}"
        f_rms  = f"{v_rms:>10.3f}" if isinstance(v_rms, float) else f"{v_rms:>10}"

        print(f"  {label:<15} | {f_min} | {f_mean} | {f_max} | {f_rms} | {f_pp}")

    # --- 3. GAIN STAGING ---
    print("\n[ 3. GAIN STAGING ]")
    print("-" * 95)
    print(f"  • Stage 1 (Q1/Q2) Gain  : {meas.get('gain_stage1', 'N/A'):>7.3f}x")
    loss_db = meas.get('tone_loss_db', 0)
    print(f"  • Tone Stack Loss       : {loss_db:>7.3f} dB")
    print(f"  • Stage 2 (Q3) Gain     : {meas.get('gain_stage2', 'N/A'):>7.3f}x")
    print(f"  • Overall Voltage Gain  : {meas.get('voltage_gain', 'N/A'):>7.3f}x")

    # --- 4. IMPEDANCES ---
    print("\n[ 4. IMPEDANCES ]")
    print("-" * 95)
    zin = meas.get('zin_large', 0) / 1000
    z1 = meas.get('zout_stage1', 0) / 1000
    z2_in = meas.get('zin_stage2', 0) / 1000
    zout = meas.get('zout_eff', 0) / 1000
    
    print(f"  • Input Impedance       : {zin:>7.1f} kΩ  (Target: >250kΩ for guitar)")
    print(f"  • Stage 1 Output Z      : {z1:>7.1f} kΩ  (Drives tone stack)")
    print(f"  • Stage 2 Input Z       : {z2_in:>7.1f} kΩ  (Loads the tone stack)")
    print(f"  • Pedal Output Impedance: {zout:>7.1f} kΩ  (Drives amp/JLH1969)")

    # --- 5. TOTAL HARMONIC DISTORTION ---
    print("\n[ 5. TOTAL HARMONIC DISTORTION (THD) ]")
    print("-" * 95)
    for node, thd_val in thd.items():
        print(f"  • {node:<10} : {thd_val:>8.4f} %")
    
    print("="*95 + "\n")

if __name__ == "__main__":
    # Change this to your actual log file name
    log_file = "redesign_15v.log" 
    parse_ltspice_log(log_file)