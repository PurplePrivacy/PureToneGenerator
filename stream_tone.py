import numpy as np
import sounddevice as sd
import signal
import sys
import argparse
import soundfile as sf
import datetime
import hashlib
from queue import Queue, Full
import threading
import time

# ============================
# CONFIG
# ============================

# Argument parser
parser = argparse.ArgumentParser(description="Pure tone streaming generator")
parser.add_argument("--freq", type=float, default=528, help="Frequency in Hz (e.g., 432, 528, 639)")
parser.add_argument("--save-audio", action="store_true", help="Save 1 hour FLAC file instead of realtime streaming")
parser.add_argument("--iso", action="store_true", help="Enable isochronic mode (volume pulse)")
parser.add_argument("--pulse", type=float, default=40, help="Isochronic pulse frequency in Hz")
parser.add_argument("--abs", action="store_true", help="Enable alternating bilateral stimulation")
parser.add_argument("--abs-speed", type=str, default="medium", choices=["slow", "medium", "fast"], help="ABS speed: slow, medium, fast")
parser.add_argument("--hrv", action="store_true", help="Enable HRV (Heart-Rate Variability) breath pacing")
parser.add_argument("--hrv-style", type=str, default="A", choices=["A", "B", "C"], help="HRV pacing style: A, B, or C")
parser.add_argument("--fade-long", action="store_true", help="Enable long-term fade-to-silence cultivation (~30min)")
parser.add_argument("--full", action="store_true", help="Enable full stack: HRV + ISO + ABS + long fade")
parser.add_argument("--integrity", action="store_true", help="Print a rolling SHA-256 hash of the internally generated audio stream (proof-of-generation)")
parser.add_argument("--integrity-interval", type=float, default=1.0, help="Seconds between integrity hash updates (default: 1.0)")
parser.add_argument("--disable-inputs", action="store_true",
                    help="Force output-only operation (no audio input paths)")
parser.add_argument("--pure", action="store_true",
                    help="Pure sine safe mode (no modulation, no noise, no bursts)")
parser.add_argument("--lockdown", action="store_true",
                    help="Maximum safety preset: pure + disable-inputs + integrity")
parser.add_argument("--latency", type=str, default="high", choices=["low", "high"],
                    help="Audio latency mode (default: high). Use high to reduce crackling.")
parser.add_argument("--blocksize", type=int, default=1024,
                    help="Audio blocksize in frames (default: 1024). Increase to reduce crackling.")
parser.add_argument("--breath-bar", action="store_true",
                    help="Show a live breathing bar in the terminal (HRV mode only)")
parser.add_argument("--breath-cue", type=str, default="none", choices=["none", "bell", "drum", "tick"],
                    help="Play a cue at HRV inhale/exhale transitions: none|bell|drum|tick (default: none)")
parser.add_argument("--breath-cue-vol", type=float, default=0.25,
                    help="Breath cue volume multiplier (default: 0.25)")
args = parser.parse_args()

frequency = args.freq       # active frequency
save_audio = args.save_audio
iso_mode = args.iso
pulse_freq = args.pulse
abs_mode = args.abs
abs_speed = args.abs_speed
hrv_mode = args.hrv
hrv_style = args.hrv_style
fade_long = args.fade_long
full_mode = args.full
integrity_mode = args.integrity
integrity_interval = args.integrity_interval

disable_inputs = args.disable_inputs
pure_mode = args.pure
lockdown_mode = args.lockdown
latency_mode = args.latency
blocksize = args.blocksize
breath_bar = args.breath_bar
breath_cue = args.breath_cue
breath_cue_vol = args.breath_cue_vol

# full-mode auto enables all major features
if full_mode:
    iso_mode = True
    abs_mode = True
    hrv_mode = True
    fade_long = True

# LOCKDOWN MODE: maximum safety preset
if lockdown_mode:
    pure_mode = True
    disable_inputs = True
    integrity_mode = True

# PURE SAFE MODE: absolute minimal signal path
if pure_mode:
    iso_mode = False
    abs_mode = False
    hrv_mode = False
    fade_long = False

# map speed keyword to Hz
if abs_speed == "slow":
    abs_rate = 0.5
elif abs_speed == "fast":
    abs_rate = 3.0
else:
    abs_rate = 1.5

# HRV style mapping
if hrv_style == "A":    # ~11s cycle
    hrv_rate = 1.0 / 11.0
elif hrv_style == "B":  # ~10.5s cycle
    hrv_rate = 1.0 / 10.5
else:                   # ~12s cycle
    hrv_rate = 1.0 / 12.0

# long-term fade duration
long_fade_seconds = 1800.0  # 30 minutes

sample_rate = 44100        # CD quality
amplitude = 0.20          # to avoid clipping
fade_seconds = 1           # duration of fade-in
channels = 2               # stereo identical

# ============================
# STREAM STATE (shared by callback + UI)
# ============================

phase = 0.0
fade_samples = int(fade_seconds * sample_rate)
current_sample = 0
hrv_phase = 0.0

# ============================
# HRV BREATH CUE (SYNTH)
# ============================

hrv_last_phase_name = None  # "INHALE" or "EXHALE"

# Precompute cue waveforms (mono) at sample_rate
_cue_tick_len = int(0.03 * sample_rate)   # 30ms
_cue_bell_len = int(0.18 * sample_rate)   # 180ms
_cue_drum_len = int(0.12 * sample_rate)   # 120ms

# Tick: short click with fast decay (high frequency)
_tick_t = np.arange(_cue_tick_len) / sample_rate
tick_cue = np.sin(2 * np.pi * 1800 * _tick_t) * np.exp(-_tick_t * 80)

# Bell: two partials with exponential decay (soft buddhist-like ding)
_bell_t = np.arange(_cue_bell_len) / sample_rate
bell_cue = (0.7 * np.sin(2 * np.pi * 880 * _bell_t) + 0.3 * np.sin(2 * np.pi * 1320 * _bell_t)) * np.exp(-_bell_t * 18)

# Drum: low thump + a touch of noise, fast decay
_drum_t = np.arange(_cue_drum_len) / sample_rate
drum_cue = (np.sin(2 * np.pi * 110 * _drum_t) * np.exp(-_drum_t * 28)) + (0.15 * np.random.uniform(-1, 1, _cue_drum_len) * np.exp(-_drum_t * 40))

def _select_cue():
    if breath_cue == "tick":
        return tick_cue
    if breath_cue == "bell":
        return bell_cue
    if breath_cue == "drum":
        return drum_cue
    return None

# ============================
# AUDIO HARDENING (SAFE)
# ============================

if disable_inputs:
    # OutputStream is output-only by design.
    # We intentionally do NOT touch sd.default.device to avoid CoreAudio crashes.
    print("🔒 Audio hardening: output-only stream (no input paths).")

if pure_mode:
    print("🛡 Pure mode enabled: single sine wave, no modulation, no noise.")

if lockdown_mode:
    print("🔐 LOCKDOWN active: pure + output-only + integrity proof.")

# ============================
# STOP HANDLER
# ============================

def handle_interrupt(sig, frame):
    print("\n🛑 Stopping cleanly...")
    sd.stop()
    try:
        integrity_queue.put_nowait(None)
    except Exception:
        pass
    print("")
    sys.exit(0)

signal.signal(signal.SIGINT, handle_interrupt)

# ============================
# INTEGRITY (PROOF-OF-GENERATION) LOGGER
# ============================

integrity_queue = Queue(maxsize=8)
_integrity_last_emit = 0.0

def integrity_worker():
    """
    Consumes audio chunks (float32 mono) and prints a rolling SHA-256 digest.
    This helps verify the stream is generated internally and remains consistent.
    """
    hasher = hashlib.sha256()
    counter = 0
    while True:
        item = integrity_queue.get()
        if item is None:
            break
        hasher.update(item)
        counter += 1
        # Print every chunk (already rate-limited by interval)
        digest = hasher.hexdigest()[:16]
        print(f"[integrity] rolling_sha256={digest} chunks={counter}")

integrity_thread = None
if 'integrity_mode' in globals() and integrity_mode:
    integrity_thread = threading.Thread(target=integrity_worker, daemon=True)
    integrity_thread.start()

# ============================
# BREATHING BAR (TERMINAL UI)
# ============================

def breathing_bar_worker():
    """
    Simple terminal UI to visualize HRV inhale/exhale pacing.
    Runs in a background thread and never touches the audio callback.
    """
    global hrv_phase
    if not hrv_mode:
        return

    bar_width = 28
    update_hz = 10.0
    sleep_s = 1.0 / update_hz

    cycle = 1.0 / hrv_rate
    half = cycle / 2.0

    while True:
        # Derive current position in HRV cycle from hrv_phase (frames)
        pos = (hrv_phase / sample_rate) % cycle
        if pos < half:
            phase_name = "INHALE"
            frac = pos / half
        else:
            phase_name = "EXHALE"
            frac = (pos - half) / half

        filled = int(frac * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)
        sys.stdout.write(f"\r🫁 {phase_name} |{bar}| {int(frac*100):3d}%   ")
        sys.stdout.flush()

        time.sleep(sleep_s)

breath_thread = None
if breath_bar:
    breath_thread = threading.Thread(target=breathing_bar_worker, daemon=True)
    breath_thread.start()

# If saving audio instead of streaming
if save_audio:
    print(f"💾 Saving 1-hour FLAC at {frequency} Hz...")

    duration_seconds = 3600  # 1 hour
    total_samples = int(sample_rate * duration_seconds)
    t = np.linspace(0, duration_seconds, total_samples, endpoint=False)
    wave = amplitude * (np.sin(2 * np.pi * frequency * t) +
                    0.25 * np.sin(2 * np.pi * frequency * 2 * t) +
                    0.1 * np.sin(2 * np.pi * frequency * 3 * t))
    if iso_mode:
        pulse_wave = 0.5 * (1 + np.sin(2 * np.pi * pulse_freq * t))
        wave *= pulse_wave

    if hrv_mode:
        hrv_env = 0.5 * (1.0 + np.sin(2 * np.pi * hrv_rate * t))
        wave *= hrv_env

    if fade_long:
        long_fade = 1.0 - np.clip(t / long_fade_seconds, 0.0, 1.0)
        wave *= long_fade

    # apply fade in/out
    fade_samples = int(fade_seconds * sample_rate)
    fade_in_curve = np.linspace(0.0, 1.0, fade_samples)
    fade_out_curve = np.linspace(1.0, 0.0, fade_samples)
    wave[:fade_samples] *= fade_in_curve
    wave[-fade_samples:] *= fade_out_curve

    if abs_mode:
        left_env = 0.5 * (1 + np.sin(2 * np.pi * abs_rate * t))
        right_env = 1 - left_env
        left_wave = wave * left_env
        right_wave = wave * right_env
        stereo = np.column_stack([left_wave, right_wave])
    else:
        stereo = np.column_stack([wave, wave])  # L == R

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{int(frequency)}Hz_{timestamp}.flac"

    sf.write(filename, stereo, sample_rate, format="FLAC")
    print(f"✔ Saved {filename}")
    sys.exit(0)

def audio_callback(outdata, frames, time, status):
    global phase, current_sample
    global hrv_phase

    t = (np.arange(frames) + phase) / sample_rate
    wave = amplitude * np.sin(2 * np.pi * frequency * t)
    if iso_mode:
        pulse = 0.5 * (1 + np.sin(2 * np.pi * pulse_freq * t))
        wave *= pulse

    # HRV breath pacing
    if hrv_mode:
        t_hrv = (np.arange(frames) + hrv_phase) / sample_rate
        hrv_env = 0.5 * (1.0 + np.sin(2 * np.pi * hrv_rate * t_hrv))
        wave *= hrv_env
        hrv_phase += frames

        # Breath cue: play a short sound on phase transitions (inhale<->exhale)
        global hrv_last_phase_name
        if breath_cue != "none":
            cycle = 1.0 / hrv_rate
            half = cycle / 2.0

            # Determine current phase name based on hrv_phase AFTER increment
            pos = (hrv_phase / sample_rate) % cycle
            phase_name = "INHALE" if pos < half else "EXHALE"

            if hrv_last_phase_name is None:
                hrv_last_phase_name = phase_name
            elif phase_name != hrv_last_phase_name:
                cue = _select_cue()
                if cue is not None:
                    L = min(frames, len(cue))
                    wave[:L] += (cue[:L] * breath_cue_vol)
                hrv_last_phase_name = phase_name

    # fade-in curve
    if current_sample < fade_samples:
        fade_factor = np.linspace(current_sample / fade_samples,
                                  (current_sample + frames) / fade_samples,
                                  frames)
        wave *= fade_factor

    # long fade-to-silence
    if fade_long:
        elapsed_seconds = current_sample / sample_rate
        if elapsed_seconds < long_fade_seconds:
            long_factor = 1.0 - (elapsed_seconds / long_fade_seconds)
        else:
            long_factor = 0.0
        wave *= long_factor

    current_sample += frames
    phase += frames

    # Integrity: periodically hash the internally generated audio (pre-gain, pre-stereo)
    if integrity_mode:
        now_sec = current_sample / sample_rate
        global _integrity_last_emit
        if (now_sec - _integrity_last_emit) >= integrity_interval:
            _integrity_last_emit = now_sec
            # Use a mono float32 view of the internal wave; convert to bytes for hashing
            try:
                chunk_bytes = np.asarray(wave, dtype=np.float32).tobytes()
                integrity_queue.put_nowait(chunk_bytes)
            except Full:
                # If the logger lags, drop chunks rather than blocking audio
                pass
            except Exception:
                pass

    gain = 5.0  # global output gain multiplier

    if abs_mode:
        left_env = 0.5 * (1 + np.sin(2 * np.pi * abs_rate * t))
        right_env = 1 - left_env
        left_wave = wave * left_env * gain
        right_wave = wave * right_env * gain
        outdata[:] = np.column_stack([left_wave, right_wave])
    else:
        outdata[:] = np.column_stack([wave * gain, wave * gain])


# ============================
# START STREAM
# ============================

print(f"🎧 Streaming real-time tone at {frequency} Hz (Ctrl-C to stop)")
print("Press Ctrl-C to stop.\n")
print(f"Audio settings: latency={latency_mode}, blocksize={blocksize}\n")
if breath_bar and hrv_mode:
    print("Breathing bar: enabled (HRV)\n")
elif breath_bar and not hrv_mode:
    print("Breathing bar: requested, but HRV is disabled (no-op)\n")
if hrv_mode and breath_cue != "none":
    print(f"Breath cue: {breath_cue} (vol={breath_cue_vol})\n")

with sd.OutputStream(
    samplerate=sample_rate,
    channels=channels,
    callback=audio_callback,
    dtype="float32",
    blocksize=blocksize,
    latency=latency_mode
):
    signal.pause()  # wait forever until interrupted