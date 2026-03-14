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
    # Se ha ajustado para capturar nombres de variables con guiones bajos (como vq4c_ripple)
    meas_pattern = re.compile(r'^(\w+):\s+.*?=\s*([+-]?\d+(?:\.\d+)?(?:e[+-]\d+)?)(?:\s+FROM.*)?$', re.IGNORECASE)
    fourier_node_pattern = re.compile(r'Fourier components of (V\([^)]+\)|I\([^)]+\))', re.IGNORECASE)
    thd_pattern = re.compile(r'Total Harmonic Distortion:\s+([0-9.]+)\%')
    step_pattern = re.compile(r'^Step Information:\s+(.*)$', re.IGNORECASE)

    current_fourier_node = None

    # 1. Parse the .log file
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

    # 2. Parse the .net file for static parameters
    net_file = filepath[:-4] + '.net'
    if os.path.exists(net_file):
        param_pattern = re.compile(r'^\.param\s+(\w+)\s*=\s*([+-]?\d+(?:\.\d+)?(?:e[+-]\d+)?)', re.IGNORECASE)
        try:
            with open(net_file, 'r', encoding='utf-16-le', errors='replace') as f:
                for line in f:
                    match = param_pattern.search(line.strip())
                    if match:
                        params_data[match.group(1).lower()] = float(match.group(2))
        except:
            pass # Si el .net no está en UTF-16, saltar silenciosamente

    print_report(meas_data, thd_data, params_data, step_info)

def print_report(meas, thd, params, step_info):
    """Formats and prints the parsed data into a friendly dashboard."""
    
    print("\n" + "="*105)
    print("🎸 GUITAR PREAMP SIMULATION REPORT (BJT BOOTSTRAP VERSION)")
    print("="*105)

    # --- 0. SIMULATION PARAMETERS ---
    print("\n[ 0. SIMULATION PARAMETERS ]")
    print("-" * 105)
    if step_info: print(f"  • Active Step : {step_info}")
    if params:
        print(f"  • Drive: {params.get('drive','N/A'):>4} | Bass: {params.get('bass','N/A'):>4} | Treble: {params.get('treble','N/A'):>4} | Vol: {params.get('vol','N/A'):>4}")
        print(f"  • Input: {params.get('in_amplitude','N/A')}V @ {params.get('in_freq','N/A')}Hz")

    # --- 1. BIAS & TRUE HEADROOM ANALYSIS ---
    print("\n[ 1. BIAS & TRUE HEADROOM ANALYSIS ]")
    print("-" * 105)
    print(f"  {'Node':<15} | {'Floor':>6} | {'Ceil.':>6} | {'Ideal':>6} || {'Min (V)':>7} | {'Mean DC':>7} | {'Max (V)':>7} || {'%Neg Used':>9} | {'%Pos Used':>9}")
    print("  " + "-" * 103)

    v_supply = 15.0 # Voltaje de alimentación [cite: 13]
    v_q2e = meas.get('vq2e_mean', 13.94) 
    v_q1e = meas.get('vq1e_mean', 3.08)
    v_q3e = meas.get('vq3e_mean', 0.65)

    nodes = [
        ("Buffer Base",  "vq5b", 0.0,   v_supply), # Monitoreo de entrada del buffer [cite: 13]
        ("Buffer Emit.", "vq5e", 0.0,   v_supply), # Monitoreo de salida del buffer [cite: 13]
        ("Q1 Base",      "vq1b", 0.0,   v_q2e),    #[cite: 16]
        ("Q2 Coll.",     "vq2c", v_q1e, v_q2e),    #[cite: 21]
        ("Q3 Base",      "vq3b", 0.0,   v_q2e),    #[cite: 27]
        ("Q3C / Q4B",    "vq3c", v_q3e, v_q2e),    #[cite: 31]
        ("Q4 Emit.",     "vq4e", 0.0,   v_q2e)     #[cite: 33]
    ]

    for label, key, floor, ceiling in nodes:
        v_min, v_mean, v_max = meas.get(f'{key}_min'), meas.get(f'{key}_mean'), meas.get(f'{key}_max')
        
        if all(isinstance(x, float) for x in [v_min, v_mean, v_max]):
            ideal_dc = (floor + ceiling) / 2.0
            neg_swing, pos_swing = v_mean - v_min, v_max - v_mean
            neg_hr, pos_hr = v_mean - floor, ceiling - v_mean
            pct_neg = max(0, min(100, (neg_swing / neg_hr) * 100)) if neg_hr > 0 else 100
            pct_pos = max(0, min(100, (pos_swing / pos_hr) * 100)) if pos_hr > 0 else 100
            
            print(f"  {label:<15} | {floor:>5.2f}V | {ceiling:>5.2f}V | {ideal_dc:>5.2f}V || {v_min:>7.3f} | {v_mean:>7.3f} | {v_max:>7.3f} || {pct_neg:>8.1f}% | {pct_pos:>8.1f}%")
        else:
            print(f"  {label:<15} | {floor:>5.2f}V | {ceiling:>5.2f}V |  N/A  || {'N/A':>7} | {'N/A':>7} | {'N/A':>7} || {'N/A':>9} | {'N/A':>9}")
    
    print("\nCurrent Draw & Power Consumption:")
    iq5 = abs(meas.get('iq5_bias', 0)) * 1000
    iq1 = abs(meas.get('iq1_bias', 0)) * 1000
    iq3 = abs(meas.get('iq3_bias', 0)) * 1000
    
    print(f"  • Input Buffer Bias (Q5) : {iq5:>7.3f} mA")
    print(f"  • Q1/Q2 Stage Bias       : {iq1:>7.3f} mA")
    print(f"  • Q3 Stage Bias          : {iq3:>7.3f} mA")
    print(f"  • Total Power Draw       : {meas.get('power_total_mw', 0):>7.3f} mW")
    print(f"  • Power Rail Ripple      : {meas.get('vq4c_ripple', 0)*1000:>7.3f} mV")

    # --- 2. AC SIGNAL LEVELS ---
    print("\n[ 2. AC SIGNAL LEVELS (RMS & Peak-to-Peak) ]")
    print("-" * 105)
    ac_nodes = [
        ("Input", "vin"), 
        ("Buffer Base", "vq5b"),
        ("Buffer Out", "vq5e"),
        ("Tone In", "vtonein"),
        ("Tone Out", "vtoneout"),
        ("Final Out", "vout")
    ]
    
    for label, key in ac_nodes:
        v_min, v_max, v_rms = meas.get(f'{key}_min'), meas.get(f'{key}_max'), meas.get(f'{key}_rms')
        if isinstance(v_min, float) and isinstance(v_max, float):
            v_pp = v_max - v_min
            f_rms = f"{v_rms:>7.3f} Vrms" if isinstance(v_rms, float) else "    N/A Vrms"
            print(f"  • {label:<12}: {f_rms} | {v_pp:>7.3f} Vp-p")

    # --- 3. GAIN STAGING ---
    print("\n[ 3. GAIN STAGING ]")
    print("-" * 105)
    print(f"  • Buffer Gain (Q5)      : {meas.get('gain_buffer', 0):>7.3f}x")
    print(f"  • Stage 1 (Q1/Q2) Gain  : {meas.get('gain_stage1', 0):>7.3f}x")
    print(f"  • Tone Stack Loss       : {meas.get('tone_loss_db', 0):>7.3f} dB")
    print(f"  • Stage 2 (Q3) Gain     : {meas.get('gain_stage2', 0):>7.3f}x")
    print(f"  • Overall Voltage Gain  : {meas.get('voltage_gain', 0):>7.3f}x ({20*math.log10(max(1e-3, meas.get('voltage_gain',1))):.2f} dB)" if 'math' in globals() else f"  • Overall Voltage Gain  : {meas.get('voltage_gain', 0):>7.3f}x")

    # --- 4. IMPEDANCES ---
    print("\n[ 4. IMPEDANCES ]")
    print("-" * 105)
    zin = meas.get('zin_large', 0)
    # Formateo dinámico para Megaohmios o Kiloohmios
    zin_str = f"{zin/1e6:>7.2f} MΩ" if zin >= 1e6 else f"{zin/1e3:>7.1f} kΩ"
    
    print(f"  • Input Impedance (Zin) : {zin_str} (Target: >1MΩ for high-fidelity)")
    print(f"  • Stage 1 Output Z      : {meas.get('zout_stage1', 0)/1e3:>7.2f} kΩ")
    print(f"  • Stage 2 Input Z       : {meas.get('zin_stage2', 0)/1e3:>7.2f} kΩ")
    print(f"  • Pedal Output Z        : {meas.get('zout_eff', 0)/1e3:>7.2f} kΩ")

    # --- 5. TOTAL HARMONIC DISTORTION ---
    print("\n[ 5. TOTAL HARMONIC DISTORTION (THD) ]")
    print("-" * 105)
    for node, thd_val in thd.items():
        print(f"  • {node:<12} : {thd_val:>8.4f} %")
    
    print("="*105 + "\n")

if __name__ == "__main__":
    import math # Necesario para el cálculo de dB en el reporte
    log_file = "redesign_15v.log" 
    parse_ltspice_log(log_file)