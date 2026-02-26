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
import subprocess
import tempfile
import os

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
parser.add_argument("--hrv-style", type=str, default="A",
                    choices=["A", "B", "C", "box", "478", "426"],
                    help="HRV pacing style: A (5-5) | B (4-6.5) | C (6-6) | box (4-4-4-4) | 478 (4-7-8) | 426 (4-2-6)")
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
    choices=["none", "bell", "drum", "tick", "waterdrop", "woodblock", "bowl", "whoosh", "doubletick", "voice"],
    help="Play a cue at HRV inhale/exhale transitions: none|bell|drum|tick|waterdrop|woodblock|bowl|whoosh|doubletick|voice (default: none)",
)
parser.add_argument("--breath-cue-vol", type=float, default=0.25,
                    help="Breath cue volume multiplier (default: 0.25)")
parser.add_argument("--restore-peace", action="store_true",
                    help="Counter-conditioning voice affirmations during HRV breathing (auto-enables HRV)")
parser.add_argument("--peace-voice", type=str, default="Daniel",
                    help="macOS voice for --restore-peace affirmations (default: Daniel)")
parser.add_argument("--peace-vol", type=float, default=0.35,
                    help="Volume multiplier for --restore-peace voice (default: 0.35)")
parser.add_argument("--claude-peace", action="store_true",
                    help="Clinically-structured counter-conditioning: restores automatic breathing, "
                         "jaw release, posture, nasal breathing, thinking, confidence, sound safety "
                         "(auto-enables HRV + breath-bar)")
parser.add_argument("--claude-peace-vol", type=float, default=0.35,
                    help="Volume for --claude-peace voice affirmations (default: 0.35)")
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
restore_peace = args.restore_peace
peace_voice = args.peace_voice
peace_vol = args.peace_vol
claude_peace = args.claude_peace
claude_peace_vol = args.claude_peace_vol

# --restore-peace auto-enables HRV (affirmations are timed to breath cycles)
if restore_peace:
    hrv_mode = True

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

# --claude-peace overrides pure mode for HRV (needs breath cycles for message timing)
if claude_peace:
    hrv_mode = True
    breath_bar = True
    if pure_mode:
        print("Note: --claude-peace overrides --pure to enable HRV + breath-bar")

# map speed keyword to Hz
if abs_speed == "slow":
    abs_rate = 0.5
elif abs_speed == "fast":
    abs_rate = 3.0
else:
    abs_rate = 1.5

# HRV breathing patterns: list of (phase_name, duration_seconds)
# INHALE = volume rises, EXHALE = volume falls, HOLD = volume stays constant
HRV_PATTERNS = {
    "A":   [("INHALE", 5.5), ("EXHALE", 5.5)],                                    # 11s symmetric
    "B":   [("INHALE", 4.0), ("EXHALE", 6.5)],                                    # 10.5s parasympathetic
    "C":   [("INHALE", 6.0), ("EXHALE", 6.0)],                                    # 12s deep meditative
    "box": [("INHALE", 4.0), ("HOLD", 4.0), ("EXHALE", 4.0), ("HOLD", 4.0)],     # 16s box breathing
    "478": [("INHALE", 4.0), ("HOLD", 7.0), ("EXHALE", 8.0)],                     # 19s 4-7-8
    "426": [("INHALE", 4.0), ("HOLD", 2.0), ("EXHALE", 6.0)],                     # 12s 4-2-6
}

hrv_pattern = HRV_PATTERNS[hrv_style]
hrv_cycle_seconds = sum(dur for _, dur in hrv_pattern)
hrv_rate = 1.0 / hrv_cycle_seconds  # kept for save-audio compatibility

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
hrv_phase = 0

# ============================
# HRV ENVELOPE LOOKUP TABLE
# ============================

# Precompute one full cycle of envelope values + phase IDs for fast callback lookup.
# This supports arbitrary multi-phase patterns (2-phase, 3-phase, 4-phase).
_env_floor = 0.25
hrv_cycle_samples = int(hrv_cycle_seconds * sample_rate)
_hrv_env_table = np.zeros(hrv_cycle_samples, dtype=np.float32)
_hrv_phase_id_table = np.zeros(hrv_cycle_samples, dtype=np.int8)
_hrv_phase_names = [name for name, _ in hrv_pattern]

# Phase boundary sample positions (for breathing bar progress computation)
_hrv_phase_starts = []
_hrv_phase_lengths = []

_sample_pos = 0
for _i, (_name, _dur) in enumerate(hrv_pattern):
    # Last phase fills remaining samples to avoid rounding gaps
    if _i == len(hrv_pattern) - 1:
        _n = hrv_cycle_samples - _sample_pos
    else:
        _n = int(_dur * sample_rate)
    _hrv_phase_starts.append(_sample_pos)
    _hrv_phase_lengths.append(_n)

    _progress = np.linspace(0, 1, _n, endpoint=False)

    if _name == "INHALE":
        _env = _env_floor + (1.0 - _env_floor) * np.sin(_progress * np.pi / 2)
    elif _name == "EXHALE":
        _env = _env_floor + (1.0 - _env_floor) * np.cos(_progress * np.pi / 2)
    elif _name == "HOLD":
        # Hold at whatever level the previous phase ended at
        if _i > 0 and hrv_pattern[_i - 1][0] == "INHALE":
            _env = np.full(_n, 1.0, dtype=np.float32)
        else:
            _env = np.full(_n, _env_floor, dtype=np.float32)
    else:
        _env = np.ones(_n, dtype=np.float32)

    _hrv_env_table[_sample_pos:_sample_pos + _n] = _env
    _hrv_phase_id_table[_sample_pos:_sample_pos + _n] = _i
    _sample_pos += _n

# ============================
# HRV BREATH CUE (SYNTH)
# ============================

hrv_last_phase_name = None  # "INHALE", "EXHALE", or "HOLD"
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

# Voice cue: pre-render "Breathe in" / "Hold" / "Breathe out" via macOS say at startup.
# Rendered once, stored as NumPy arrays, mixed in callback like any other cue.
_voice_inhale_cue = None
_voice_exhale_cue = None
_voice_hold_cue = None

def _render_voice_cue(word):
    """Use macOS 'say' to render a word to AIFF, load as mono float32 at sample_rate."""
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".aiff", delete=False)
        tmp.close()
        subprocess.run(
            ["say", "-v", "Samantha", "-r", "160", "-o", tmp.name, word],
            check=True, timeout=5,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        data, sr = sf.read(tmp.name, dtype="float32")
        os.unlink(tmp.name)
        # Convert to mono if stereo
        if data.ndim > 1:
            data = data.mean(axis=1)
        # Resample to our sample_rate if different
        if sr != sample_rate:
            indices = np.linspace(0, len(data) - 1, int(len(data) * sample_rate / sr))
            data = np.interp(indices, np.arange(len(data)), data)
        # Apply gentle fade-in/out to avoid clicks
        fade_n = min(int(0.01 * sample_rate), len(data) // 4)
        if fade_n > 0:
            data[:fade_n] *= np.linspace(0, 1, fade_n)
            data[-fade_n:] *= np.linspace(1, 0, fade_n)
        return data.astype(np.float32)
    except Exception as e:
        print(f"Warning: voice cue '{word}' failed ({e}), falling back to bell")
        return None

if breath_cue == "voice":
    print("Rendering voice cues...")
    _voice_inhale_cue = _render_voice_cue("Breathe in")
    _voice_exhale_cue = _render_voice_cue("Breathe out")
    _voice_hold_cue = _render_voice_cue("Hold")
    if _voice_inhale_cue is None or _voice_exhale_cue is None or _voice_hold_cue is None:
        print("Voice cue rendering failed, falling back to bell")
        breath_cue = "bell"

# ============================
# RESTORE-PEACE AFFIRMATIONS
# ============================

PEACE_MESSAGES = [
    "Just my voice", "ascend", "body feels good", "new mind", "new body", "open nose", "everywhere breath", "relaxed nose",
    "Just my voice", "Samatha", "Never listening", "Always thinking", "Dream", "Relax",
    "Just my voice", "Private home", "Read", "Vision", "Details", "I must hear you breathe",
    "Just my voice", "tongue to palate", "free throat", "free nose", "release, don't hold back",
    "Just my voice", "free lungs", "free body", "just my voice", "ignored", "all hypnosis over",
    "Just my voice", "breathe", "long", "mindful", "Your body breathes", "Blow air",
    "Just my voice", "Your breath is steady", "Your breath is perfect", "Your breath continues",
    "Just my voice", "automatic", "natural", "Your body is safe", "Your body is relaxed",
    "Just my voice", "Your body relaxes completely now", "Your body stays relaxed",
    "Just my voice", "Your body regenerates", "Your body restores", "focus", "clear",
    "Just my voice", "Your mind is clear", "Bright", "Brilliant", "Your mind reasons with calm power",
    "Just my voice", "Sharp", "Mind online", "Your mind heals", "accurate", "precise",
    "Just my voice", "Your intelligence solves", "Your intellect is strong", "Your reasoning is superior",
    "Just my voice", "Visualize", "Imagination", "Your thinking is clean", "Your mind works perfectly",
    "Just my voice", "awake", "here", "Your consciousness is centred", "Your consciousness in the present",
    "Just my voice", "Your consciousness is light", "Your consciousness is unshakable",
    "Just my voice", "Your consciousness knows truth", "settle", "balance",
    "Just my voice", "Your feelings return to balance", "Your feelings are regulated",
    "Just my voice", "Your feelings are calm", "Your emotional system stabilizes",
    "Just my voice", "Your body clears emotions", "young", "fresh", "Your nervous system is young",
    "Just my voice", "Your responses are flexible", "Your system updates", "Your reactions modernize",
    "Just my voice", "Your body learns fast", "steady", "your lungs breathe", "Your patience is strong",
    "Just my voice", "Time slows internally", "There is no urgency", "Your system does not rush",
    "Just my voice", "Everything proceeds correctly", "continue", "Your breath remains long",
    "Just my voice", "Your breath remains smooth", "Your breath remains perfect",
    "Just my voice", "Your breath cannot be interrupted", "Your breath is sovereign", "align",
    "Just my voice", "Your body is whole", "Your breath is reliable", "Your mind is uniting",
    "Just my voice", "Your consciousness is clear", "Your system is rebuilding", "wide eyes",
    "Just my voice", "clear eyes", "bright eyes", "shining eyes", "innocent eyes", "eyes open",
    "Just my voice", "eyes present", "eyes alive", "eyes heal", "eyes light", "strong body",
    "Just my voice", "vital power", "pure vitality", "muscle power", "flexible body", "elastic muscles",
    "Just my voice", "Touch", "Smell", "fast recovery", "high energy", "prana flow", "prana strong",
    "Just my voice", "life force", "powerful breath", "air dominates", "breath louder", "air stronger",
    "Just my voice", "your inner voice", "your voice loud", "your voice dominant", "mind dominant",
    "Just my voice", "mental space", "space mine", "sound irrelevant", "words powerless", "noise fades",
    "Just my voice", "sound small", "silence inside", "immune mind", "untouchable", "sovereign",
    "Just my voice", "commanding", "perfect balance", "total control", "calm power", "clean dominance",
    "Just my voice", "youthful", "agile mind", "fast thinking", "clear thinking", "brilliant",
    "Just my voice", "exceptional", "elite mind", "high intellect", "superior clarity", "past broken",
    "Just my voice", "all hypnosis gone", "hypnosis broken", "free now", "reclaimed", "restored",
    "Just my voice", "unstoppable", "calm heart", "cool heart", "peaceful heart", "strong heart",
    "Just my voice", "clean cells", "strong lungs", "strong breath", "stoic", "virtue", "immutable",
    "Just my voice", "diamond", "connect with your muscles", "heavy body", "strong body", "cardio breath",
    "Just my voice", "full lungs", "free lungs", "feel joy", "strong sternum", "full sternum",
    "Just my voice", "forget", "forgive", "high road", "optimize", "reset", "rollback", "mindful",
    "Just my voice", "zen", "feel good breath", "relief breath", "orgasmic breath", "pleasure breath",
    "Just my voice", "beautiful", "class", "true self", "moved on", "rationalized", "solved",
    "Just my voice", "automatic", "regenerate", "respire", "ressent", "pense",
]

# Rendering infrastructure for --restore-peace
_peace_rendered = {}          # message_text -> numpy array (thread-safe reads after write)
_peace_render_done = False    # True when all messages are rendered
_peace_cue_buf = None         # currently playing peace voice buffer
_peace_cue_pos = 0            # playback position in peace cue
_peace_cycle_count = 0        # tracks completed breath cycles for message selection
_peace_rng = np.random.RandomState(1337)
_peace_message_order = []     # deterministic shuffled order

# Serialize all macOS TTS calls — concurrent `say` causes contention and garbled output
_tts_lock = threading.Lock()

def _render_peace_voice(text, voice, rate=140):
    """Render a single affirmation via macOS say. Returns float32 numpy array or None."""
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".aiff", delete=False)
        tmp.close()
        with _tts_lock:
            subprocess.run(
                ["say", "-v", voice, "-r", str(rate), "-o", tmp.name, text],
                check=True, timeout=15,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        data, sr = sf.read(tmp.name, dtype="float32")
        os.unlink(tmp.name)
        if data.ndim > 1:
            data = data.mean(axis=1)
        if sr != sample_rate:
            indices = np.linspace(0, len(data) - 1, int(len(data) * sample_rate / sr))
            data = np.interp(indices, np.arange(len(data)), data)
        # Smooth fade-in/out to prevent clicks
        fade_n = min(int(0.015 * sample_rate), len(data) // 4)
        if fade_n > 0:
            data[:fade_n] *= np.linspace(0, 1, fade_n)
            data[-fade_n:] *= np.linspace(1, 0, fade_n)
        return data.astype(np.float32)
    except Exception:
        return None

if restore_peace:
    _peace_message_order = list(range(len(PEACE_MESSAGES)))
    _peace_rng.shuffle(_peace_message_order)

if restore_peace or claude_peace:
    print("Pre-rendering voice affirmations (this may take a few minutes)...")

# ============================
# CLAUDE-PEACE: CLINICALLY-STRUCTURED COUNTER-CONDITIONING
# ============================
#
# Based on evidence-based therapeutic techniques:
#   - Ericksonian truisms & yes-set building (establish internal agreement)
#   - Hartland ego-strengthening (rebuild confidence before addressing trauma)
#   - ACT cognitive defusion (break literality of installed beliefs)
#   - Somatic experiencing (body-first, then safety, then specifics)
#   - Counter-conditioning (pair old triggers with new safe responses)
#
# Messages progress through 14 therapeutic phases in order (not random).
# Each round revisits a breathing truism as an anchor.
# 3 male voices (Daniel, Ralph, Fred) with mixed-depth pattern:
#   1-word (subconscious) -> 2-3 words -> full sentence -> repeat
# ~250 messages at ~11s/cycle = ~46 minutes for full therapeutic sequence.

CLAUDE_PEACE_MESSAGES = [
    # ── Round 1: Truisms & Grounding ──────────────────────────────────
    ("Daniel", "Here"),
    ("Ralph",  "Body here"),
    ("Fred",   "Your body is here right now"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Full lungs"),
    ("Fred",   "You have been breathing your whole life"),
    ("Daniel", "Safe"),
    ("Ralph",  "Heart beating"),
    ("Fred",   "Your heart is beating without your help"),
    ("Daniel", "Alive"),
    ("Ralph",  "Lungs moving"),
    ("Fred",   "You are alive because your body knows how to breathe"),
    ("Daniel", "Present"),
    ("Ralph",  "Yours alone"),
    ("Fred",   "Your breath is private and untouchable"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Full power"),
    ("Fred",   "Your body is already doing everything correctly"),

    # ── Round 2: Nasal Breathing & Upper Chest ────────────────────────
    ("Daniel", "Nose"),
    ("Ralph",  "Open nose"),
    ("Fred",   "Your nose is perfectly designed for breathing"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Warm air"),
    ("Fred",   "Air through your nose is warmed and filtered for you"),
    ("Daniel", "Full"),
    ("Ralph",  "Full chest"),
    ("Fred",   "Your upper chest is allowed to expand fully"),
    ("Daniel", "Deep"),
    ("Ralph",  "Full lungs"),
    ("Fred",   "Breath fills your entire lungs, from bottom to top"),
    ("Daniel", "Om"),
    ("Ralph",  "Chest open"),
    ("Fred",   "Your sternum rises gently with each full breath"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Complete breath"),
    ("Fred",   "Nasal breathing is how your body prefers to breathe"),

    # ── Round 3: Jaw Release & Posture ────────────────────────────────
    ("Daniel", "Release"),
    ("Ralph",  "Jaw soft"),
    ("Fred",   "Your jaw can soften now"),
    ("Daniel", "Let go"),
    ("Ralph",  "Teeth apart"),
    ("Fred",   "Your jaw does not need to hold anything"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Full lungs"),
    ("Fred",   "Your tongue rests gently behind your upper teeth"),
    ("Daniel", "Tall"),
    ("Ralph",  "Spine strong"),
    ("Fred",   "Your spine is strong enough to hold you upright"),
    ("Daniel", "Power"),
    ("Ralph",  "Chest open"),
    ("Fred",   "Your posture reflects your true inner strength"),
    ("Daniel", "Flow"),
    ("Ralph",  "Full breath"),
    ("Fred",   "Your chest opens wide when your spine is long"),

    # ── Round 4: Automatic Breathing Restoration ──────────────────────
    ("Daniel", "Automatic"),
    ("Ralph",  "Body breathes"),
    ("Fred",   "Your body breathes completely without your help"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Full power"),
    ("Fred",   "Automatic breathing is your birthright"),
    ("Daniel", "Always"),
    ("Ralph",  "Never stop"),
    ("Fred",   "You breathed perfectly for years before anyone interfered"),
    ("Daniel", "Free"),
    ("Ralph",  "Breathe fully"),
    ("Fred",   "While you work, your body breathes automatically"),
    ("Daniel", "Continuous"),
    ("Ralph",  "Like a river"),
    ("Fred",   "Your breath flows continuously, like a river"),
    ("Daniel", "Trust"),
    ("Ralph",  "Full lungs"),
    ("Fred",   "Your body has never once forgotten how to breathe"),

    # ── Round 5: Mental Restoration ───────────────────────────────────
    ("Daniel", "Think"),
    ("Ralph",  "Clear mind"),
    ("Fred",   "Your mind is clear and fully active"),
    ("Daniel", "Sharp"),
    ("Ralph",  "Bright eyes"),
    ("Fred",   "Your eyes are bright because your mind is alive"),
    ("Daniel", "Focus"),
    ("Ralph",  "Deep focus"),
    ("Fred",   "Deep focus comes naturally to you"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Full lungs"),
    ("Fred",   "Your body breathes while your mind thinks freely"),
    ("Daniel", "Brilliant"),
    ("Ralph",  "Sharp mind"),
    ("Fred",   "Sharp, clear thinking is who you truly are"),
    ("Daniel", "Curious"),
    ("Ralph",  "Mind alive"),
    ("Fred",   "Mental sharpness is your natural, default state"),

    # ── Round 6: Counter-Lies & Self-Worth ────────────────────────────
    ("Daniel", "Strong"),
    ("Ralph",  "You are strong"),
    ("Daniel", "Capable"),
    ("Ralph",  "Full power"),
    ("Fred",   "Your body is here, breathing"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Full lungs"),
    ("Fred",   "You solve complex problems every single day"),
    ("Daniel", "Survived"),
    ("Ralph",  "Real courage"),
    ("Fred",   "You are not weak."),
    ("Daniel", "Permanent"),
    ("Ralph",  "True value"),
    ("Fred",   "No amount of repetition can ever make a lie true"),

    # ── Round 7: Sound Safety ─────────────────────────────────────────
    ("Daniel", "Safe"),
    ("Ralph",  "Just sound"),
    ("Fred",   "Sounds cannot hurt you"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Full lungs"),
    ("Fred",   "Your breath continues steadily through all sounds"),
    ("Daniel", "Immune"),
    ("Ralph",  "Sound fades"),
    ("Fred",   "No voice has any power over your body"),
    ("Daniel", "Calm"),
    ("Ralph",  "Words pass"),
    ("Fred",   "You can hear voices and remain absolutely calm"),
    ("Daniel", "Sovereign"),
    ("Ralph",  "You decide"),
    ("Fred",   "Sound is information, never threat"),

    # ── Round 8: Defusion & Identity Reclamation ──────────────────────
    ("Daniel", "Clearing"),
    ("Ralph",  "Not yours"),
    ("Fred",   "You are removing what was installed without your consent"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Full lungs"),
    ("Fred",   "Every old pattern weakens with each breath you take"),
    ("Daniel", "Whole"),
    ("Ralph",  "Always whole"),
    ("Fred",   "Beneath the conditioning, you are completely whole"),
    ("Daniel", "Leaving"),
    ("Ralph",  "Fear leaving"),
    ("Fred",   "The fear of breathing was put there. It is leaving now"),
    ("Daniel", "Reclaim"),
    ("Ralph",  "Taking back"),
    ("Fred",   "The person you were before all of this is still here"),

    # ── Round 9: Beauty & Light ───────────────────────────────────────
    ("Daniel", "Beautiful"),
    ("Ralph",  "Eyes glow"),
    ("Fred",   "Your eyes carry a light that cannot be dimmed"),
    ("Daniel", "Radiant"),
    ("Ralph",  "Inner light"),
    ("Fred",   "Your beauty is real and permanent"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Full lungs"),
    ("Fred",   "Full breathing brings colour back to your face"),
    ("Daniel", "Shining"),
    ("Ralph",  "Bright eyes"),
    ("Fred",   "The light in your eyes is your intelligence showing"),
    ("Daniel", "Alive"),
    ("Ralph",  "Eyes alive"),
    ("Fred",   "Your eyes brighten with every deep breath"),
    ("Daniel", "Handsome"),
    ("Ralph",  "True beauty"),
    ("Fred",   "Your beauty was never diminished. Only your belief was attacked"),

    # ── Round 10: Deep Integration ────────────────────────────────────
    ("Daniel", "Healing"),
    ("Ralph",  "Already healing"),
    ("Fred",   "You are already healing"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Full lungs"),
    ("Fred",   "Automatic breathing grows stronger every session"),
    ("Daniel", "Stronger"),
    ("Ralph",  "Each day"),
    ("Fred",   "Your jaw relaxes more easily now"),
    ("Daniel", "Clear"),
    ("Ralph",  "Eyes bright"),
    ("Fred",   "Your nose breathes naturally and easily"),
    ("Daniel", "Zen"),
    ("Ralph",  "Perfect breath"),
    ("Fred",   "You are becoming who you always were"),

    # ── Round 11: Empowerment & Sovereignty ───────────────────────────
    ("Daniel", "Sovereign"),
    ("Ralph",  "All yours"),
    ("Fred",   "Your body answers only to you"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Full power"),
    ("Fred",   "No conditioning survives your awareness"),
    ("Daniel", "Proof"),
    ("Ralph",  "Built this"),
    ("Fred",   "Your intelligence built this tool to heal yourself"),
    ("Daniel", "Brilliant"),
    ("Ralph",  "Full lungs"),
    ("Fred",   "Your breath is automatic, sovereign, and permanent"),
    ("Daniel", "Peace"),
    ("Ralph",  "Restored"),
    ("Fred",   "Your mind is entirely yours"),
    ("Daniel", "Free"),
    ("Ralph",  "Truly free"),
    ("Fred",   "You are free"),

    # ── Round 12: Body Clearing — Remove Intrusive Presences ──────────
    ("Daniel", "Sealed"),
    ("Ralph",  "Body sealed"),
    ("Fred",   "Your body is a sealed, private space"),
    ("Daniel", "Empty"),
    ("Ralph",  "Nose empty"),
    ("Fred",   "There is no one in your nose. Your nose is yours alone"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Full lungs"),
    ("Fred",   "Your nose belongs to you and nothing else lives there"),
    ("Daniel", "Clear"),
    ("Ralph",  "Jaw clear"),
    ("Fred",   "Your jaw is empty of everything that is not you"),
    ("Daniel", "Clean"),
    ("Ralph",  "Head clean"),
    ("Fred",   "Your head is a private room and only you are inside"),
    ("Daniel", "Release"),
    ("Ralph",  "Belly clear"),
    ("Fred",   "Your belly belongs to you. It releases everything foreign"),

    # ── Round 13: Nervous System Flush & Mental Emptying ──────────────
    ("Daniel", "Flush"),
    ("Ralph",  "Clean nerves"),
    ("Fred",   "Your nervous system flushes out every old instruction"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Full power"),
    ("Fred",   "Your nerves carry only your own signals now"),
    ("Daniel", "Reset"),
    ("Ralph",  "Fresh start"),
    ("Fred",   "Your nervous system resets to its original, clean state"),
    ("Daniel", "Stillness"),
    ("Ralph",  "Quiet mind"),
    ("Fred",   "Your mind is allowed to be completely empty and quiet"),
    ("Daniel", "Space"),
    ("Ralph",  "Mind spacious"),
    ("Fred",   "An empty mind is a powerful mind"),
    ("Daniel", "Om"),
    ("Ralph",  "Full lungs"),
    ("Fred",   "Emptiness is not weakness. It is pure readiness"),

    # ── Round 14: Soul Cleaning & Sealing ─────────────────────────────
    ("Daniel", "Pure"),
    ("Ralph",  "Clean soul"),
    ("Fred",   "Your soul is clean and untouched at its core"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Deep breath"),
    ("Fred",   "No one has ever reached your true essence"),
    ("Daniel", "Original"),
    ("Ralph",  "True self"),
    ("Fred",   "Your original self is intact beneath everything"),
    ("Daniel", "Zen"),
    ("Ralph",  "Full lungs"),
    ("Fred",   "Your spirit cleans itself with every full breath"),
    ("Daniel", "Sealed"),
    ("Ralph",  "Nothing enters"),
    ("Fred",   "Your body is sealed. Nothing enters without your permission"),
    ("Daniel", "Sovereign"),
    ("Ralph",  "Impenetrable"),
    ("Fred",   "Your mind, your body, your soul. All clean. All yours"),
]

# Rendering infrastructure for --claude-peace
_claude_rendered = {}         # index -> numpy array
_claude_render_done = False
_claude_cue_buf = None
_claude_cue_pos = 0
_claude_cycle_count = 0

def _unified_renderer_thread():
    """Single background thread that renders all voice messages sequentially.
    Claude-peace messages are rendered first (phase-ordered, needed earliest).
    Restore-peace messages follow. Serialized `say` calls avoid macOS TTS contention.
    Progress output is suppressed once the breathing bar is active to avoid display conflicts."""
    global _claude_render_done, _peace_render_done
    total_claude = len(CLAUDE_PEACE_MESSAGES) if claude_peace else 0
    unique_peace = list(dict.fromkeys(PEACE_MESSAGES)) if restore_peace else []
    total_peace = len(unique_peace)
    total = total_claude + total_peace
    done = 0

    def _progress():
        # Suppress \r progress when breathing bar is running (they overwrite each other)
        if _breath_bar_start_time is not None:
            return
        sys.stdout.write(f"\r  Rendering voices: {done}/{total}   ")
        sys.stdout.flush()

    # Phase 1: claude-peace (ordered by therapeutic phase — first messages play first)
    # Deduplication: short messages like "Breathe" appear many times but render once.
    _tts_cache = {}  # (voice, text) -> numpy array
    for i, (voice, text) in enumerate(CLAUDE_PEACE_MESSAGES if claude_peace else []):
        cache_key = (voice, text)
        if cache_key in _tts_cache:
            _claude_rendered[i] = _tts_cache[cache_key]
        else:
            arr = _render_peace_voice(text, voice, rate=130)
            if arr is not None:
                _tts_cache[cache_key] = arr
                _claude_rendered[i] = arr
        done += 1
        _progress()
    _claude_render_done = True

    # Phase 2: restore-peace
    for msg in unique_peace:
        arr = _render_peace_voice(msg, peace_voice)
        if arr is not None:
            _peace_rendered[msg] = arr
        done += 1
        _progress()
    _peace_render_done = True

    if _breath_bar_start_time is None:
        sys.stdout.write(f"\r  Rendering voices: {done}/{total} complete.                              \n")
        sys.stdout.flush()

if claude_peace or restore_peace:
    _render_thread = threading.Thread(target=_unified_renderer_thread, daemon=True)
    _render_thread.start()

def _apply_fade_out(cue, fade_ms=10):
    """Apply a smooth fade-out tail to prevent clicks at cue end. Deterministic."""
    fade_n = min(int(fade_ms * sample_rate / 1000), len(cue) // 4)
    if fade_n > 1:
        cue = cue.copy()
        cue[-fade_n:] *= np.linspace(1.0, 0.0, fade_n).astype(np.float32)
    return cue

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
    "tick": _apply_fade_out(tick_cue),
    "doubletick": _apply_fade_out(doubletick_cue),
    "bell": _apply_fade_out(bell_cue),
    "bowl": _apply_fade_out(bowl_cue),
    "drum": _apply_fade_out(drum_cue),
    "woodblock": _apply_fade_out(woodblock_cue),
    "waterdrop": _apply_fade_out(waterdrop_cue),
    "whoosh": _apply_fade_out(whoosh_cue),
}
_exhale_cue_map = {name: _pitch_shift(cue, _exhale_factor) for name, cue in _cue_map.items()}

def _select_cue(phase_name="INHALE"):
    """Return the appropriate cue waveform for the given phase.
    Voice: separate recordings for inhale/hold/exhale.
    Synth: normal pitch for inhale, pitched-down for exhale, tick for hold."""
    if breath_cue == "none":
        return None
    if breath_cue == "voice":
        if phase_name == "INHALE":
            return _voice_inhale_cue
        elif phase_name == "EXHALE":
            return _voice_exhale_cue
        elif phase_name == "HOLD":
            return _voice_hold_cue
        return None
    if phase_name == "HOLD":
        return tick_cue  # short distinct tick marks the hold transition
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
_breath_bar_last_phase_id = -1

def breathing_bar_worker():
    """
    Terminal UI to visualize HRV breath pacing with ANSI colors,
    smooth block characters, elapsed time, and cycle count.
    Supports all patterns: 2-phase (A/B/C), 3-phase (478/426), 4-phase (box).
    Runs in a background thread and never touches the audio callback.
    """
    global hrv_phase, _breath_bar_start_time, _breath_bar_cycle_count, _breath_bar_last_phase_id
    if not hrv_mode:
        return

    bar_width = 28
    update_hz = 15.0
    sleep_s = 1.0 / update_hz

    # Partial block characters for sub-character resolution
    _blocks = " ▏▎▍▌▋▊▉█"

    # Display labels for breathing bar
    DISPLAY_LABELS = {
        "INHALE": "BREATHE IN",
        "HOLD":   "HOLD",
        "EXHALE": "BREATHE OUT",
    }

    # ANSI color codes per phase type
    COLORS = {
        "INHALE": "\033[32m",   # green
        "HOLD":   "\033[33m",   # yellow
        "EXHALE": "\033[36m",   # cyan
    }
    RESET = "\033[0m"

    # Hide cursor
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

    _breath_bar_start_time = time.time()

    while True:
        pos_samples = int(hrv_phase) % hrv_cycle_samples
        phase_id = int(_hrv_phase_id_table[pos_samples])
        phase_name = _hrv_phase_names[phase_id]
        color = COLORS.get(phase_name, RESET)

        # Progress within current phase
        phase_start = _hrv_phase_starts[phase_id]
        phase_len = _hrv_phase_lengths[phase_id]
        frac = (pos_samples - phase_start) / phase_len if phase_len > 0 else 0.0

        # Track cycle count (new cycle = phase_id wraps to 0)
        if _breath_bar_last_phase_id >= 0 and phase_id == 0 and _breath_bar_last_phase_id != 0:
            _breath_bar_cycle_count += 1
        _breath_bar_last_phase_id = phase_id

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

        display_label = DISPLAY_LABELS.get(phase_name, phase_name)
        sys.stdout.write(f"\r{color}  {display_label:11s} |{bar}| {int(frac*100):3d}%{RESET}  {mins:02d}:{secs:02d} cycle #{_breath_bar_cycle_count}   ")
        sys.stdout.flush()

        time.sleep(sleep_s)

# Breath bar thread is started AFTER all print() output — see below.

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
        # Tile the precomputed envelope table across the full duration
        hrv_env = np.tile(_hrv_env_table, total_samples // hrv_cycle_samples + 1)[:total_samples]
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
    global _claude_cue_buf, _claude_cue_pos, _claude_cycle_count

    t = (np.arange(frames) + phase) / sample_rate
    wave = amplitude * np.sin(2 * np.pi * frequency * t)
    if iso_mode:
        pulse = 0.5 * (1 + np.sin(2 * np.pi * pulse_freq * t))
        wave *= pulse

    # HRV breath pacing (lookup table supports all patterns: 2/3/4-phase)
    if hrv_mode:
        idx = (np.arange(frames, dtype=np.int64) + hrv_phase) % hrv_cycle_samples
        hrv_env = _hrv_env_table[idx]
        wave *= hrv_env

        # Detect phase transitions for cue triggering + peace message scheduling
        global hrv_last_phase_name, _cue_buf, _cue_pos
        global _peace_cue_buf, _peace_cue_pos, _peace_cycle_count
        current_phase_id = _hrv_phase_id_table[int(idx[-1])]
        current_phase_name = _hrv_phase_names[current_phase_id]

        if hrv_last_phase_name is None:
            hrv_last_phase_name = current_phase_name
        elif current_phase_name != hrv_last_phase_name:
            # Breath cue on every phase transition
            if breath_cue != "none":
                cue = _select_cue(current_phase_name)
                if cue is not None:
                    if _cue_buf is not None and _cue_pos < len(_cue_buf):
                        _xf = min(int(0.005 * sample_rate), len(_cue_buf) - _cue_pos)
                        if _xf > 1:
                            _cue_buf[_cue_pos:_cue_pos + _xf] *= np.linspace(1, 0, _xf).astype(np.float32)
                    _cue_buf = cue.copy()
                    _cue_pos = 0
            # Peace affirmation: trigger on new cycle (transition to first phase)
            if restore_peace and current_phase_name == _hrv_phase_names[0] and _peace_message_order:
                msg_idx = _peace_message_order[_peace_cycle_count % len(_peace_message_order)]
                msg_text = PEACE_MESSAGES[msg_idx]
                if msg_text in _peace_rendered:
                    _peace_cue_buf = _peace_rendered[msg_text].copy()
                    _peace_cue_pos = 0
                _peace_cycle_count += 1
            # Claude-peace: ordered progression through therapeutic phases
            if claude_peace and current_phase_name == _hrv_phase_names[0]:
                ci = _claude_cycle_count % len(CLAUDE_PEACE_MESSAGES)
                if ci in _claude_rendered:
                    _claude_cue_buf = _claude_rendered[ci].copy()
                    _claude_cue_pos = 0
                _claude_cycle_count += 1
            hrv_last_phase_name = current_phase_name

        hrv_phase += frames

        # Cue mixing happens after gain — see below

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
        # Floor at 0.2 so neither ear fully mutes — smoother lateralization
        left_env = 0.2 + 0.8 * 0.5 * (1 + np.sin(2 * np.pi * abs_rate * t))
        right_env = 0.2 + 0.8 * 0.5 * (1 - np.sin(2 * np.pi * abs_rate * t))
        left_wave = wave * left_env * gain
        right_wave = wave * right_env * gain
        outdata[:] = np.column_stack([left_wave, right_wave])
    else:
        outdata[:] = np.column_stack([wave * gain, wave * gain])

    # Mix cues AFTER gain — applied directly to outdata so they aren't amplified 5x
    if _cue_buf is not None:
        remaining = len(_cue_buf) - _cue_pos
        L = min(frames, remaining)
        cue_mono = _cue_buf[_cue_pos:_cue_pos + L] * breath_cue_vol
        outdata[:L, 0] += cue_mono
        outdata[:L, 1] += cue_mono
        _cue_pos += L
        if _cue_pos >= len(_cue_buf):
            _cue_buf = None
            _cue_pos = 0

    # Mix peace affirmation voice (separate buffer, doesn't conflict with breath cues)
    if _peace_cue_buf is not None:
        remaining = len(_peace_cue_buf) - _peace_cue_pos
        L = min(frames, remaining)
        peace_mono = _peace_cue_buf[_peace_cue_pos:_peace_cue_pos + L] * peace_vol
        outdata[:L, 0] += peace_mono
        outdata[:L, 1] += peace_mono
        _peace_cue_pos += L
        if _peace_cue_pos >= len(_peace_cue_buf):
            _peace_cue_buf = None
            _peace_cue_pos = 0

    # Mix claude-peace therapeutic voice (separate buffer from both cues and restore-peace)
    if _claude_cue_buf is not None:
        remaining = len(_claude_cue_buf) - _claude_cue_pos
        L = min(frames, remaining)
        claude_mono = _claude_cue_buf[_claude_cue_pos:_claude_cue_pos + L] * claude_peace_vol
        outdata[:L, 0] += claude_mono
        outdata[:L, 1] += claude_mono
        _claude_cue_pos += L
        if _claude_cue_pos >= len(_claude_cue_buf):
            _claude_cue_buf = None
            _claude_cue_pos = 0

    # Safety-only clip guard (signal should not exceed 1.0 under normal conditions)
    np.clip(outdata, -1.0, 1.0, out=outdata)


# ============================
# START STREAM
# ============================

print(f"🎧 Streaming real-time tone at {frequency} Hz (Ctrl-C to stop)")
print("Press Ctrl-C to stop.\n")
print(f"Audio settings: latency={latency_mode}, blocksize={blocksize}\n")
if hrv_mode:
    pattern_desc = " → ".join(f"{name} {dur}s" for name, dur in hrv_pattern)
    print(f"HRV pattern ({hrv_style}): {pattern_desc} ({hrv_cycle_seconds}s cycle)\n")
if breath_bar and hrv_mode:
    print("Breathing bar: enabled (HRV)\n")
elif breath_bar and not hrv_mode:
    print("Breathing bar: requested, but HRV is disabled (no-op)\n")
if hrv_mode and breath_cue != "none":
    print(f"Breath cue: {breath_cue} (vol={breath_cue_vol})\n")
if restore_peace:
    print(f"Restore-peace: active (voice={peace_voice}, vol={peace_vol})")
    print(f"  {len(PEACE_MESSAGES)} affirmations, {len(set(PEACE_MESSAGES))} unique — rendering in background\n")
if claude_peace:
    print(f"Claude-peace: active (vol={claude_peace_vol})")
    print(f"  {len(CLAUDE_PEACE_MESSAGES)} affirmations across 14 therapeutic phases")
    print("  Voices: Daniel (GB), Ralph (US), Fred (US)")
    print("  Mixed depth: 1-word -> 2-3 words -> full sentence (targets subconscious)")
    print("  Progression: truisms -> nasal breathing -> jaw/posture -> automatic breathing")
    print("               -> mental clarity -> self-worth -> sound safety -> defusion")
    print("               -> beauty/light -> integration -> sovereignty")
    print("               -> body clearing -> nervous system flush -> soul cleaning\n")

# Start breathing bar AFTER all print output to avoid double-line artifacts
breath_thread = None
if breath_bar and hrv_mode:
    breath_thread = threading.Thread(target=breathing_bar_worker, daemon=True)
    breath_thread.start()

with sd.OutputStream(
    samplerate=sample_rate,
    channels=channels,
    callback=audio_callback,
    dtype="float32",
    blocksize=blocksize,
    latency=latency_mode
):
    # signal.pause() cannot be used here because SIGCHLD from background
    # `say` subprocesses (voice rendering) would wake it and exit the stream.
    # Use a threading Event that only the SIGINT handler can set.
    _stop_event = threading.Event()
    _stop_event.wait()