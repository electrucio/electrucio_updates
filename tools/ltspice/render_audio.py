#!/usr/bin/env python3
"""Pasa un WAV de guitarra por el amplificador simulado y lo pone en un altavoz.

    python3 tools/ltspice/render_audio.py --dur 8 -o /tmp/renders

El audio lo procesa LTSPICE, muestra a muestra: el recortador de diodos, el
recorte de la etapa de potencia, el sag del rail y el zumbido de 100 Hz son los
del circuito, no un modelo aparte.  Lo unico que se hace fuera de LTspice es
convolucionar con la respuesta al impulso del bafle, que es acustica y no
electrica.

Cuatro trampas, todas verificadas a mano:

1. `.wave` RECORTA A +-1 V.  Es formato WAV: fondo de escala es 1.0.  Una
   senoide de 5 V sale a 1.0 pelada.  Por eso la salida va por `B_WOUT`, que
   divide por `OUT_SCALE` antes de escribir, y se multiplica de vuelta al leer.
2. El WAV de entrada es un DI: la respuesta del pickup YA esta en la grabacion.
   Si se inyectase en PICKUP_IN se aplicaria el modelo de pickup del netlist
   por segunda vez.  Se inyecta en PICKUP_OUT, que es la entrada real del ampli,
   y se deja V6 a cero.
3. Se captura a 192 kHz y se decima a 48 kHz con un filtro de verdad.  Escribir
   directo a 48 kHz plegaria los armonicos de recorte, que llegan muy arriba.
4. Modo RED, no banco: con `V_RAW` continuo no hay sag ni zumbido, y los dos se
   oyen.  El precio son 4 s de arranque del deposito, asi que se le PREPENDEN
   4 s de silencio al WAV de entrada y el `.tran` guarda a partir de ahi.

El bafle es una IR de 48 kHz; el altavoz electrico es el modelo de impedancia
del netlist, no 7.5 ohm muertos.  Hay un solapamiento conocido y aceptado: la
IR incluye la respuesta del altavoz medida acusticamente, que en parte sale de
su propia impedancia.  Es lo que hace todo el mundo que usa IRs.
"""
from __future__ import annotations

import argparse
import shutil
import struct
import sys
import time
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ltrun import run_batch                                     # noqa: E402
from verify_amp_tran import Bench, VRAW_DC                      # noqa: E402
from verify_tone_ac import NET, VSRC                            # noqa: E402

AUDIO = (Path(__file__).resolve().parents[2]
         / "junk/guitar_preamplifier/audios")
DRY = AUDIO / "dry_guitar_44100_selection.wav"
IR = AUDIO / "SL_112_Fender_DR_A.wav"

SIM_SR = 192_000        # captura sobremuestreada, para no plegar armonicos
OUT_SR = 48_000         # el de la IR: asi no hay que remuestrear la IR
MAXSTEP = "2u"          # 500 kHz de resolucion en el solver
WARMUP = 4.0            # s de arranque del deposito en modo red
OUT_SCALE = 32.0        # V a fondo de escala del .wave (el ampli da ~+-22 V)
LPF_HZ = 20_000.0       # esquina del antialias antes de decimar

# El pico del corte es 0.3235 en fondo de escala.  Con `peak_mv` = 320 el
# factor es ~1, o sea que el WAV se toma como si fueran voltios de pickup.
# Referencias medidas en este mismo circuito: 50 mVp = single coil suave,
# 150 mVp = normal, 300-600 mVp = puas fuertes.
PEAK_MV = 320.0


# ------------------------------------------------------------------- WAV a pelo
def rd_wav(path: Path) -> tuple[np.ndarray, int]:
    """Lee un WAV PCM mono de 16 o 24 bits a float en [-1, 1)."""
    with wave.open(str(path)) as w:
        if w.getnchannels() != 1:
            raise ValueError(f"{path.name}: se esperaba mono")
        sw, sr, raw = w.getsampwidth(), w.getframerate(), w.readframes(
            w.getnframes())
    if sw == 2:
        a = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 2**15
    elif sw == 3:
        b = np.frombuffer(raw, dtype=np.uint8).reshape(-1, 3).astype(np.int32)
        # el byte alto va con signo; los otros dos sin signo
        a = (b[:, 0] | b[:, 1] << 8
             | b[:, 2].astype(np.int8).astype(np.int32) << 16) / 2**23
    else:
        raise ValueError(f"{path.name}: {sw*8} bits sin soporte")
    return a.astype(np.float64), sr


def wr_wav(path: Path, y: np.ndarray, sr: int, bits: int = 24) -> Path:
    """Escribe un WAV PCM mono.  Recorta a fondo de escala por seguridad."""
    y = np.clip(y, -1.0, 1.0 - 2.0**-23)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(bits // 8)
        w.setframerate(sr)
        if bits == 16:
            w.writeframes((y * 2**15).astype("<i2").tobytes())
        else:
            q = np.rint(y * 2**23).astype(np.int32)
            b = np.empty((len(q), 3), dtype=np.uint8)
            b[:, 0] = q & 0xFF
            b[:, 1] = (q >> 8) & 0xFF
            b[:, 2] = (q >> 16) & 0xFF
            w.writeframes(b.tobytes())
    return path


# ------------------------------------------------------------------- DSP minimo
def resample(y: np.ndarray, sr_in: int, sr_out: int,
             lpf: float = LPF_HZ) -> np.ndarray:
    """Decima por FFT con antialias.

    Hay que filtrar ANTES de tirar bins: el ampli en recorte duro genera
    armonicos muy por encima de 24 kHz y si se decima a pelo se pliegan dentro
    de la banda audible, donde se oyen como aspereza que el circuito no tiene.
    La rampa de `lpf` a Nyquist es un coseno alzado, no un muro, para no
    meter timbre de la propia ventana.
    """
    n_in = len(y)
    n_out = int(round(n_in * sr_out / sr_in))
    X = np.fft.rfft(y)
    f = np.arange(len(X)) * sr_in / n_in
    nyq = sr_out / 2.0
    ramp = np.clip((f - lpf) / (nyq - lpf), 0.0, 1.0)
    X *= 0.5 * (1.0 + np.cos(np.pi * ramp))
    return np.fft.irfft(X[: n_out // 2 + 1], n_out) * (n_out / n_in)


def convolve(y: np.ndarray, ir: np.ndarray) -> np.ndarray:
    n = 1 << int(np.ceil(np.log2(len(y) + len(ir) - 1)))
    return np.fft.irfft(np.fft.rfft(y, n) * np.fft.rfft(ir, n),
                        n)[: len(y) + len(ir) - 1]


# --------------------------------------------------------------------- el render
def build(bench: Bench, wav_in: Path, wav_out: Path, tstop: float,
          gain: float, tag: str, drive: float, vol: float) -> Path:
    """Netlist listo para simular: WAV dentro, WAV fuera."""
    n = bench._base(params={"drive": drive, "vol": vol})
    n.patch(VSRC, "V6 PICKUP_IN 0 0")     # el modelo de pickup queda inerte
    n.patch(".options plotwinsize=0\n", "")   # el .raw no interesa: pesa GB
    n.drop_re(r"\s*\.tran\b", 1)
    n.add(
        f"V_WAV NWAV 0 wavefile={wav_in} chan=0",
        # DI: se entra por la salida del pickup, no por sus bobinas
        f"E_IN PICKUP_OUT 0 NWAV 0 {gain:.6f}",
        f"B_WOUT WOUT 0 V=V(SPEAKER)/{OUT_SCALE}",
        f".wave {wav_out} 24 {SIM_SR} V(WOUT)",
        ".save V(SPEAKER)",
        f".tran 0 {tstop:.4f} {WARMUP} {MAXSTEP}",
    )
    return n.write(bench.w / f"{tag}.net")


def render(bench: Bench, wav_in: Path, tstop: float, gain: float,
           tag: str, drive: float, vol: float) -> np.ndarray:
    """Simula y devuelve la tension en el altavoz, en VOLTIOS, a SIM_SR."""
    out = bench.w / f"{tag}_sim.wav"
    out.unlink(missing_ok=True)
    net = build(bench, wav_in, out, tstop, gain, tag, drive, vol)
    t0 = time.time()
    run_batch(net, timeout=7200)
    if not out.exists():
        raise RuntimeError(f"LTspice no escribio {out}")
    y, sr = rd_wav(out)
    if sr != SIM_SR:
        raise AssertionError(f"{out.name} salio a {sr} Hz, no a {SIM_SR}")
    print(f"    {time.time()-t0:6.1f} s de CPU, {len(y)/sr:.2f} s de audio, "
          f"pico {np.abs(y).max()*OUT_SCALE:6.2f} V", flush=True)
    if np.abs(y).max() > 0.999:
        print(f"    OJO: {tag} toco el fondo de escala del .wave, "
              f"sube OUT_SCALE", flush=True)
    return y * OUT_SCALE


CONFIGS = [
    # etiqueta         drive  ramal+   ramal-   sangrado (None = 2k2 dibujado)
    ("clean_d0",         0.0, "gnd",  "gnd",  None),
    ("stock_d50",        0.5, "gnd",  "gnd",  None),
    ("stock_d100",       1.0, "gnd",  "gnd",  None),
    ("nodiodes_d50",     0.5, "open", "open", None),
    ("nodiodes_d100",    1.0, "open", "open", None),
    ("bias_d50",         0.5, "bias", "bias", None),
    ("bias_d100",        1.0, "bias", "bias", None),
    ("bias_d100_r22k",   1.0, "bias", "bias", "22k"),
    ("halfwave_d100",    1.0, "gnd",  "open", None),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-o", "--out", default="renders")
    ap.add_argument("--dur", type=float, default=8.0,
                    help="segundos de audio a procesar (0 = el corte entero)")
    ap.add_argument("--skip", type=float, default=0.0,
                    help="segundos a saltar del principio del corte")
    ap.add_argument("--peak-mv", type=float, default=PEAK_MV,
                    help="a que pico de pickup, en mV, se mapea el WAV")
    ap.add_argument("--clip-r", default="2k2",
                    help="resistencia de sangrado de los ramales en bias")
    ap.add_argument("--vol", type=float, default=1.0,
                    help="master (0-1).  OJO: por encima de 0.85 la etapa de "
                         "potencia recorta y aplasta las diferencias entre "
                         "conmutadores, de +2.8 dB a +1.0 dB.  Medido.")
    ap.add_argument("--only", nargs="*", help="solo estas configuraciones")
    a = ap.parse_args()

    if not NET.exists():
        sys.exit(f"no encuentro {NET}: exportalo desde la GUI de LTspice")
    for f in (DRY, IR):
        if not f.exists():
            sys.exit(f"no encuentro {f}")

    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    work = out / "_sim"
    work.mkdir(exist_ok=True)

    dry, sr_dry = rd_wav(DRY)
    i0 = int(a.skip * sr_dry)
    dry = dry[i0:] if a.dur <= 0 else dry[i0: i0 + int(a.dur * sr_dry)]
    dur = len(dry) / sr_dry
    peak = float(np.abs(dry).max())
    gain = (a.peak_mv / 1000.0) / peak

    # 4 s de silencio delante: el deposito carga mientras no suena nada
    pad = np.concatenate([np.zeros(int(WARMUP * sr_dry)), dry])
    wav_in = work / "in_padded.wav"
    wr_wav(wav_in, pad, sr_dry, bits=16)
    tstop = WARMUP + dur

    ir, sr_ir = rd_wav(IR)
    if sr_ir != OUT_SR:
        sys.exit(f"la IR esta a {sr_ir} Hz y esperaba {OUT_SR}")

    print(f"corte: {dur:.2f} s, pico {peak:.4f} FS -> {a.peak_mv:.0f} mVp "
          f"(x{gain:.3f})")
    print(f"bafle: {IR.name}, {len(ir)/sr_ir*1000:.0f} ms a {sr_ir} Hz")
    print(f"rail : modo red, {WARMUP:.0f} s de arranque + {dur:.2f} s "
          f"utiles, paso {MAXSTEP}")
    print(f"master: vol={a.vol:.2f}" + ("  (OJO: la etapa de potencia recorta "
          "y aplasta las diferencias)" if a.vol > 0.9 else "") + "\n")

    cfgs = [c for c in CONFIGS if not a.only or c[0] in a.only]
    results, rows = {}, []
    for tag, drive, cp, cn, rcfg in cfgs:
        cr = rcfg or a.clip_r
        print(f"  {tag:16s} drive={drive*100:3.0f}%  clip=({cp},{cn})"
              + (f"  sangrado={cr}" if "bias" in (cp, cn) else ""), flush=True)
        b = Bench(work, mains=True, dummy_load=False, clip=(cp, cn),
                  clip_r=cr)
        v = render(b, wav_in, tstop, gain, tag, drive, a.vol)
        v48 = resample(v, SIM_SR, OUT_SR)
        v48 -= v48.mean()                       # por si queda continua
        results[tag] = convolve(v48, ir)
        vrms = float(np.sqrt(np.mean(np.square(v48))))
        rows.append((tag, drive, f"{cp}/{cn}", float(np.abs(v48).max()),
                     vrms, vrms**2 / 7.5))

    # un solo factor para TODOS: asi la diferencia de volumen entre
    # configuraciones se conserva y se puede comparar de verdad
    k = 0.891 / max(float(np.abs(y).max()) for y in results.values())
    for tag, y in results.items():
        wr_wav(out / f"{tag}.wav", y * k, OUT_SR)

    dry48 = resample(np.concatenate([dry, np.zeros(len(dry) // 20)]),
                     sr_dry, OUT_SR)
    d = convolve(dry48, ir)
    wr_wav(out / "ref_dry_cab.wav", d * (0.891 / np.abs(d).max()), OUT_SR)

    print(f"\n{'config':17s} {'drive':>6s} {'clip':>10s} {'Vpico':>8s} "
          f"{'Vrms':>7s} {'W(7.5)':>8s}")
    for tag, drive, clip, vp, vr, pw in rows:
        print(f"{tag:17s} {drive*100:5.0f}% {clip:>10s} {vp:8.2f} "
              f"{vr:7.2f} {pw:8.2f}")
    print(f"\n{len(results)+1} ficheros en {out}")
    print(f"normalizados con el MISMO factor ({k:.4f}), o sea que las "
          f"diferencias de volumen son reales")
    return 0


if __name__ == "__main__":
    sys.exit(main())
