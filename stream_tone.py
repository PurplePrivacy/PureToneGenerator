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
parser.add_argument(
    "--breath-cue",
    type=str,
    default="none",
    choices=["none", "bell", "drum", "tick", "waterdrop", "woodblock", "bowl", "whoosh", "doubletick"],
    help="Play a cue at HRV inhale/exhale transitions: none|bell|drum|tick|waterdrop|woodblock|bowl|whoosh|doubletick (default: none)",
)
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
_cue_buf = None     # the full cue waveform currently playing (or None)
_cue_pos = 0        # how far we've played into it

# Precompute cue waveforms (mono) at sample_rate.
# Use a fixed RNG seed so cues are deterministic (no randomness from run to run).
_rng = np.random.RandomState(1337)

_cue_tick_len = int(0.03 * sample_rate)       # 30ms
_cue_bell_len = int(0.40 * sample_rate)       # 400ms
_cue_drum_len = int(0.20 * sample_rate)       # 200ms
_cue_water_len = int(0.25 * sample_rate)      # 250ms
_cue_wood_len = int(0.06 * sample_rate)       # 60ms
_cue_bowl_len = int(0.60 * sample_rate)       # 600ms
_cue_whoosh_len = int(0.50 * sample_rate)     # 500ms
_cue_double_len = int(0.10 * sample_rate)     # 100ms total (2 short ticks)

# Tick: short click with fast decay (high frequency)
_tick_t = np.arange(_cue_tick_len) / sample_rate
tick_cue = np.sin(2 * np.pi * 1800 * _tick_t) * np.exp(-_tick_t * 80)

# Double-tick: two tiny ticks separated by 50ms
_double_t = np.arange(_cue_double_len) / sample_rate
doubletick_cue = np.zeros(_cue_double_len, dtype=np.float32)
# first tick
t1 = np.arange(_cue_tick_len) / sample_rate
doubletick_cue[:_cue_tick_len] += (np.sin(2 * np.pi * 1800 * t1) * np.exp(-t1 * 80)).astype(np.float32)
# second tick (shifted)
shift = int(0.05 * sample_rate)
end2 = min(shift + _cue_tick_len, _cue_double_len)
t2 = np.arange(end2 - shift) / sample_rate
doubletick_cue[shift:end2] += (np.sin(2 * np.pi * 1800 * t2) * np.exp(-t2 * 80)).astype(np.float32)

# Bell: inharmonic partials with exponential decay (soft buddhist-like ding)
_bell_t = np.arange(_cue_bell_len) / sample_rate
bell_cue = (0.50 * np.sin(2 * np.pi * 880 * _bell_t)
            + 0.25 * np.sin(2 * np.pi * 1320 * _bell_t)
            + 0.12 * np.sin(2 * np.pi * 1760 * _bell_t)
            + 0.08 * np.sin(2 * np.pi * 2640 * _bell_t)
            + 0.05 * np.sin(2 * np.pi * 3520 * _bell_t)) * np.exp(-_bell_t * 10)

# Bowl: singing bowl partials with slow decay (spacious, sustained)
_bowl_t = np.arange(_cue_bowl_len) / sample_rate
bowl_cue = (0.50 * np.sin(2 * np.pi * 440 * _bowl_t)
            + 0.25 * np.sin(2 * np.pi * 660 * _bowl_t)
            + 0.15 * np.sin(2 * np.pi * 880 * _bowl_t)
            + 0.10 * np.sin(2 * np.pi * 1100 * _bowl_t)) * np.exp(-_bowl_t * 4)

# Drum: low thump + body resonance + tiny deterministic noise, fast decay
_drum_t = np.arange(_cue_drum_len) / sample_rate
drum_noise = _rng.uniform(-1, 1, _cue_drum_len) * np.exp(-_drum_t * 40)
drum_cue = (0.7 * np.sin(2 * np.pi * 110 * _drum_t) * np.exp(-_drum_t * 22)
            + 0.3 * np.sin(2 * np.pi * 55 * _drum_t) * np.exp(-_drum_t * 15)
            + 0.10 * drum_noise)

# Woodblock: short damped tone (tight, percussive, no broadband noise)
_wood_t = np.arange(_cue_wood_len) / sample_rate
woodblock_cue = np.sin(2 * np.pi * 520 * _wood_t) * np.exp(-_wood_t * 60)

# Waterdrop: wide descending chirp with decay (pleasant "plink")
_water_t = np.arange(_cue_water_len) / sample_rate
f0, f1 = 1600.0, 600.0
k = (f1 - f0) / (_cue_water_len / sample_rate)
water_phase = 2 * np.pi * (f0 * _water_t + 0.5 * k * _water_t**2)
waterdrop_cue = np.sin(water_phase) * np.exp(-_water_t * 18)

# Whoosh: multi-pass low-passed deterministic noise with slow fade (subtle air cue)
_whoosh_t = np.arange(_cue_whoosh_len) / sample_rate
whoosh_noise = _rng.uniform(-1, 1, _cue_whoosh_len).astype(np.float32)
# 3-pass 1-pole low-pass for smoother texture
alpha = 0.02
whoosh_lp = np.zeros_like(whoosh_noise)
for _pass in range(3):
    src = whoosh_noise if _pass == 0 else whoosh_lp.copy()
    whoosh_lp[0] = src[0] * alpha
    for i in range(1, len(src)):
        whoosh_lp[i] = whoosh_lp[i-1] + alpha * (src[i] - whoosh_lp[i-1])
whoosh_env = np.sin(np.pi * np.clip(_whoosh_t / (_cue_whoosh_len / sample_rate), 0, 1))  # smooth in/out
whoosh_cue = whoosh_lp * whoosh_env * 0.6

def _pitch_shift(cue, factor):
    """Resample a cue to shift pitch by factor (>1 = higher). Deterministic."""
    n = len(cue)
    new_n = int(n / factor)
    if new_n < 2:
        return cue
    indices = np.linspace(0, n - 1, new_n)
    return np.interp(indices, np.arange(n), cue)

# Pre-compute exhale variants (pitched down to 0.85x) for inhale/exhale distinction
_exhale_factor = 0.85
_cue_map = {
    "tick": tick_cue,
    "doubletick": doubletick_cue,
    "bell": bell_cue,
    "bowl": bowl_cue,
    "drum": drum_cue,
    "woodblock": woodblock_cue,
    "waterdrop": waterdrop_cue,
    "whoosh": whoosh_cue,
}
_exhale_cue_map = {name: _pitch_shift(cue, _exhale_factor) for name, cue in _cue_map.items()}

def _select_cue(phase_name="INHALE"):
    """Return the appropriate cue waveform. Exhale uses a lower-pitched variant."""
    if breath_cue == "none":
        return None
    if phase_name == "EXHALE":
        return _exhale_cue_map.get(breath_cue)
    return _cue_map.get(breath_cue)

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
    # Restore cursor visibility
    sys.stdout.write("\033[?25h")
    sys.stdout.flush()
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

_breath_bar_start_time = None
_breath_bar_cycle_count = 0
_breath_bar_last_phase = None

def breathing_bar_worker():
    """
    Terminal UI to visualize HRV inhale/exhale pacing with ANSI colors,
    sinusoidal fill, smooth block characters, elapsed time, and cycle count.
    Runs in a background thread and never touches the audio callback.
    """
    global hrv_phase, _breath_bar_start_time, _breath_bar_cycle_count, _breath_bar_last_phase
    if not hrv_mode:
        return

    bar_width = 28
    update_hz = 15.0
    sleep_s = 1.0 / update_hz

    cycle = 1.0 / hrv_rate
    half = cycle / 2.0

    # Partial block characters for sub-character resolution
    _blocks = " ▏▎▍▌▋▊▉█"

    # ANSI color codes
    GREEN = "\033[32m"
    CYAN = "\033[36m"
    RESET = "\033[0m"

    # Hide cursor
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

    _breath_bar_start_time = time.time()

    while True:
        # Derive current position in HRV cycle from hrv_phase (frames)
        pos = (hrv_phase / sample_rate) % cycle
        if pos < half:
            phase_name = "INHALE"
            linear_frac = pos / half
            color = GREEN
        else:
            phase_name = "EXHALE"
            linear_frac = (pos - half) / half
            color = CYAN

        # Sinusoidal fill: map linear progress through sin() to match the auditory envelope
        frac = np.sin(linear_frac * np.pi / 2)

        # Track cycle count
        if _breath_bar_last_phase is not None and _breath_bar_last_phase == "EXHALE" and phase_name == "INHALE":
            _breath_bar_cycle_count += 1
        _breath_bar_last_phase = phase_name

        # Smooth bar with partial block characters
        fill_exact = frac * bar_width
        full_blocks = int(fill_exact)
        remainder = fill_exact - full_blocks
        partial_idx = int(remainder * (len(_blocks) - 1))
        bar = "█" * full_blocks
        if full_blocks < bar_width:
            bar += _blocks[partial_idx]
            bar += " " * (bar_width - full_blocks - 1)

        # Elapsed time
        elapsed = time.time() - _breath_bar_start_time
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)

        sys.stdout.write(f"\r{color}  {phase_name:6s} |{bar}| {int(frac*100):3d}%{RESET}  {mins:02d}:{secs:02d} cycle #{_breath_bar_cycle_count}   ")
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
    if pure_mode:
        wave = amplitude * np.sin(2 * np.pi * frequency * t)
    else:
        wave = amplitude * (np.sin(2 * np.pi * frequency * t)
                            + 0.25 * np.sin(2 * np.pi * frequency * 2 * t)
                            + 0.10 * np.sin(2 * np.pi * frequency * 3 * t))
    if iso_mode:
        pulse = 0.5 * (1 + np.sin(2 * np.pi * pulse_freq * t))
        wave *= pulse

    # HRV breath pacing
    if hrv_mode:
        t_hrv = (np.arange(frames) + hrv_phase) / sample_rate
        hrv_env = 0.5 * (1.0 + np.sin(2 * np.pi * hrv_rate * t_hrv))
        wave *= hrv_env
        hrv_phase += frames

        # Breath cue: trigger on phase transitions, play across multiple callbacks
        global hrv_last_phase_name, _cue_buf, _cue_pos
        if breath_cue != "none":
            cycle = 1.0 / hrv_rate
            half = cycle / 2.0

            # Determine current phase name based on hrv_phase AFTER increment
            pos = (hrv_phase / sample_rate) % cycle
            phase_name = "INHALE" if pos < half else "EXHALE"

            if hrv_last_phase_name is None:
                hrv_last_phase_name = phase_name
            elif phase_name != hrv_last_phase_name:
                # Transition detected — start new cue playback
                cue = _select_cue(phase_name)
                if cue is not None:
                    _cue_buf = cue.copy()
                    _cue_pos = 0
                hrv_last_phase_name = phase_name

        # Mix ongoing cue into wave (spans multiple callbacks)
        if _cue_buf is not None:
            remaining = len(_cue_buf) - _cue_pos
            L = min(frames, remaining)
            wave[:L] += (_cue_buf[_cue_pos:_cue_pos + L] * breath_cue_vol)
            _cue_pos += L
            if _cue_pos >= len(_cue_buf):
                _cue_buf = None
                _cue_pos = 0

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

    # Soft clip guard: prevent harsh digital clipping from harmonics + cues + gain
    np.clip(outdata, -1.0, 1.0, out=outdata)


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