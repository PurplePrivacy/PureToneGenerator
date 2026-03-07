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
import json
import re

# ============================
# CONFIG
# ============================

# Argument parser
parser = argparse.ArgumentParser(description="Resonance — Therapeutic Audio Engine")
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
parser.add_argument("--no-tone", action="store_true",
                    help="Silence the base tone (voice messages and cues still play)")
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
parser.add_argument("--phd-peace", action="store_true",
                    help="Expert-reviewed 21-phase counter-conditioning: all 16 claude-peace phases "
                         "plus 5 default-state conditioning rounds (expression, posture, feeling, mode, body)")
parser.add_argument("--phd-peace-vol", type=float, default=0.35,
                    help="Volume for --phd-peace voice affirmations (default: 0.35)")
parser.add_argument("--alternate", action="store_true",
                    help="Alternate voice messages between left and right speakers (EMDR-style bilateral)")
parser.add_argument("--dense", action="store_true",
                    help="Play affirmations on every breath phase transition (~5.5s) instead of every full cycle (~11s)")
parser.add_argument("--peace-lang", type=str, default="en", choices=["en", "fr"],
                    help="Language for peace affirmations: en | fr (default: en)")
parser.add_argument("--audiobook", type=str, default=None, metavar="BOOK",
                    help="Read a book aloud with Aurélie (Enhanced) voice during HRV breathing "
                         "(e.g., --audiobook meditations). Use --audiobook-list to see available books.")
parser.add_argument("--audiobook-list", action="store_true",
                    help="List all available audiobooks and exit")
parser.add_argument("--audiobook-vol", type=float, default=0.40,
                    help="Audiobook voice volume (default: 0.40)")
parser.add_argument("--audiobook-resume", action="store_true",
                    help="Resume from where you left off (saves progress to books/.progress)")
parser.add_argument("--audiobook-page", type=int, default=None, metavar="N",
                    help="Start audiobook from page N (each page = ~10 sentences)")
parser.add_argument("--audiobook-gap", type=float, default=2.0, metavar="SEC",
                    help="Silence gap between audiobook sentences in seconds (default: 2.0)")
parser.add_argument("--audiobook-word-gap", type=float, default=1.5, metavar="MULT",
                    help="Extend natural TTS pauses by this multiplier (default: 1.5, 0=disabled)")
parser.add_argument("--no-audiobook-loop", action="store_true",
                    help="Disable audiobook looping (by default, the book replays when finished)")
parser.add_argument("--no-audiobook-gaps", action="store_true",
                    help="Disable intra-sentence pauses (keeps inter-sentence gap only, for debugging)")
parser.add_argument("--audiobook-voice", type=str, default=None, metavar="VOICE",
                    help="Override audiobook voice (e.g., Tom, Samantha, Daniel, Alex)")
parser.add_argument("--audiobook-rate", type=int, default=None, metavar="WPM",
                    help="Override audiobook speech rate in words-per-minute (default: 135)")
parser.add_argument("--rhythm", action="store_true", default=True,
                    help="Enhance audiobook pacing — extends natural TTS pauses for a deliberate reading feel (default: on)")
parser.add_argument("--no-rhythm", action="store_true",
                    help="Disable reading rhythm — use raw TTS pacing with no pause extension")
# ── Presets: one-flag therapeutic modes ────────────────────────
parser.add_argument("--peaceful-vibe", action="store_true",
                    help="Preset: 432 Hz + isochronic 40 Hz + HRV breathing + breath bar")
parser.add_argument("--deep-focus", action="store_true",
                    help="Preset: 528 Hz + isochronic 40 Hz (gamma focus, no breathing)")
parser.add_argument("--sleep", action="store_true",
                    help="Preset: 174 Hz + HRV style C + 30-min fade-to-silence")
parser.add_argument("--morning-energy", action="store_true",
                    help="Preset: 528 Hz + isochronic + ABS + HRV 4-2-6 breathing")
parser.add_argument("--anxiety-relief", action="store_true",
                    help="Preset: 396 Hz + HRV 4-7-8 + breath bar + bell cue")
parser.add_argument("--meditation", action="store_true",
                    help="Preset: 432 Hz + HRV style C + breath bar + 30-min fade")
parser.add_argument("--emdr-session", action="store_true",
                    help="Preset: PhD-peace 21-phase + bilateral ABS + alternating voices")
parser.add_argument("--deep-sleep", action="store_true",
                    help="Preset: 174 Hz + HRV style C + 30-min fade + bowl cue")
parser.add_argument("--bilateral-calm", action="store_true",
                    help="Preset: 528 Hz + ABS + HRV + alternating bilateral stimulation")
parser.add_argument("--study", action="store_true",
                    help="Preset: 528 Hz + isochronic 40 Hz (pure focus, no breathing)")
parser.add_argument("--yoga", action="store_true",
                    help="Preset: 432 Hz + HRV 4-7-8 + breath bar + singing bowl cue")
parser.add_argument("--breathwork", action="store_true",
                    help="Preset: HRV 4-7-8 + breath bar + voice cue (no tone)")
parser.add_argument("--power-nap", action="store_true",
                    help="Preset: 396 Hz + HRV style C + 30-min fade-to-silence")
parser.add_argument("--grounding", action="store_true",
                    help="Preset: 396 Hz + HRV + breath bar + Claude counter-conditioning")
parser.add_argument("--healing", action="store_true",
                    help="Preset: 528 Hz (Solfeggio healing) + HRV + slow ABS")
parser.add_argument("--creativity", action="store_true",
                    help="Preset: 639 Hz + isochronic 10 Hz (alpha waves for creativity)")
parser.add_argument("--reading-calm", action="store_true",
                    help="Preset: 432 Hz gentle ambient tone (minimal, calm background)")
parser.add_argument("--trauma-release", action="store_true",
                    help="Preset: PhD-peace 21-phase + bilateral alternation + HRV 4-7-8")
parser.add_argument("--ocean-calm", action="store_true",
                    help="Preset: 256 Hz + HRV style C + slow ABS + 30-min fade")
parser.add_argument("--full-restore", action="store_true",
                    help="Preset: full therapeutic stack — PhD-peace + ABS + HRV 4-7-8 + bowl cue")
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
phd_peace = args.phd_peace
phd_peace_vol = args.phd_peace_vol
alternate_mode = args.alternate
dense_mode = args.dense
peace_lang = args.peace_lang
audiobook_name = args.audiobook
audiobook_list = args.audiobook_list
audiobook_vol = args.audiobook_vol
audiobook_resume = args.audiobook_resume
audiobook_page = args.audiobook_page
audiobook_gap = args.audiobook_gap
audiobook_word_gap = args.audiobook_word_gap
reading_rhythm = args.rhythm and not args.no_rhythm
if reading_rhythm and "--audiobook-word-gap" not in sys.argv:
    audiobook_word_gap = 2.0
audiobook_loop = not args.no_audiobook_loop
audiobook_no_gaps = args.no_audiobook_gaps

# ── Preset mode overrides ─────────────────────────────────────
# Each preset sets variables that the existing cascade then refines
if args.peaceful_vibe:
    frequency = 432; iso_mode = True; pulse_freq = 40; hrv_mode = True; breath_bar = True
if args.deep_focus:
    frequency = 528; iso_mode = True; pulse_freq = 40
if args.sleep:
    frequency = 174; hrv_mode = True; hrv_style = "C"; fade_long = True
if args.morning_energy:
    frequency = 528; iso_mode = True; abs_mode = True; hrv_mode = True; hrv_style = "426"
if args.anxiety_relief:
    frequency = 396; hrv_mode = True; hrv_style = "478"; breath_bar = True; breath_cue = "bell"
if args.meditation:
    frequency = 432; hrv_mode = True; hrv_style = "C"; breath_bar = True; fade_long = True
if args.emdr_session:
    phd_peace = True; abs_mode = True; hrv_mode = True; hrv_style = "478"
    alternate_mode = True; breath_bar = True
if args.deep_sleep:
    frequency = 174; hrv_mode = True; hrv_style = "C"; fade_long = True; breath_cue = "bowl"
if args.bilateral_calm:
    frequency = 528; abs_mode = True; hrv_mode = True; alternate_mode = True
if args.study:
    frequency = 528; iso_mode = True; pulse_freq = 40
if args.yoga:
    frequency = 432; hrv_mode = True; hrv_style = "478"; breath_bar = True; breath_cue = "bowl"
if args.breathwork:
    hrv_mode = True; hrv_style = "478"; breath_bar = True; breath_cue = "voice"
if args.power_nap:
    frequency = 396; hrv_mode = True; hrv_style = "C"; fade_long = True
if args.grounding:
    frequency = 396; hrv_mode = True; breath_bar = True; claude_peace = True
if args.healing:
    frequency = 528; hrv_mode = True; abs_mode = True; abs_speed = "slow"
if args.creativity:
    frequency = 639; iso_mode = True; pulse_freq = 10
if args.reading_calm:
    frequency = 432
if args.trauma_release:
    phd_peace = True; alternate_mode = True; hrv_mode = True; hrv_style = "478"; breath_bar = True
if args.ocean_calm:
    frequency = 256; hrv_mode = True; hrv_style = "C"; abs_mode = True; abs_speed = "slow"; fade_long = True
if args.full_restore:
    phd_peace = True; alternate_mode = True; abs_mode = True; hrv_mode = True
    hrv_style = "478"; breath_bar = True; breath_cue = "bowl"

# Presets that silence the base tone
_preset_no_tone = args.breathwork
# Presets with custom amplitude
_preset_low_amp = args.reading_calm

# French language: override default peace voice if user didn't explicitly set it
if peace_lang == "fr" and "--peace-voice" not in sys.argv:
    peace_voice = "Aurélie (Enhanced)"

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

# --phd-peace: extended 21-phase version — activates claude_peace infrastructure
if phd_peace:
    hrv_mode = True
    breath_bar = True
    claude_peace_vol = phd_peace_vol
    if pure_mode:
        print("Note: --phd-peace overrides --pure to enable HRV + breath-bar")

# --audiobook-list: display catalog and exit
if audiobook_list:
    from books.catalog import BOOK_CATALOG, BOOK_CATEGORIES, ARCHAIC_BOOKS
    _texts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "books", "texts")
    _total = len(BOOK_CATALOG)
    _n_fr = sum(1 for m in BOOK_CATALOG.values() if m.get("language") == "fr")
    _n_en = sum(1 for m in BOOK_CATALOG.values() if m.get("language") == "en")
    _n_archaic = sum(1 for n in ARCHAIC_BOOKS if n in BOOK_CATALOG)
    print(f"\nAvailable audiobooks ({_total} books — {_n_fr} French, {_n_en} English, {_n_archaic} archaic):\n")
    for cat in BOOK_CATEGORIES:
        _cat_books = [(n, m) for n, m in BOOK_CATALOG.items() if m["category"] == cat]
        if not _cat_books:
            continue
        print(f"  {cat}:")
        for name, meta in _cat_books:
            _dl = os.path.exists(os.path.join(_texts_dir, f"{name}.txt"))
            _mark = "[OK]" if _dl else "[--]"
            _lang = meta.get("language", "fr").upper()
            if name in ARCHAIC_BOOKS:
                _lang = "EN - Ancient formulations"
            print(f"    {_mark} {name:<25s} {meta['title']} — {meta['author']}  [{_lang}]")
        print()
    print("  [OK] = downloaded    [--] = run: python books/fetch_books.py")
    print("  [FR] = French    [EN] = English    [EN - Ancient formulations] = archaic English")
    print()
    sys.exit(0)

# --audiobook auto-enables HRV + breath-bar (like --claude-peace)
audiobook_mode = False
_audiobook_sentences = []
_audiobook_book_title = ""
if audiobook_name:
    from books.catalog import BOOK_CATALOG
    if audiobook_name not in BOOK_CATALOG:
        print(f"Error: unknown book '{audiobook_name}'. Use --audiobook-list to see available books.")
        sys.exit(1)
    _ab_meta = BOOK_CATALOG[audiobook_name]
    _ab_text_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "books", "texts", f"{audiobook_name}.txt")
    if not os.path.exists(_ab_text_path):
        print(f"Error: book file not found: {_ab_text_path}")
        print("Run: python books/fetch_books.py")
        sys.exit(1)
    with open(_ab_text_path, "r", encoding="utf-8") as _f:
        _ab_raw = _f.read()
    # Voice selection based on book language
    _ab_lang = _ab_meta.get("language", "fr")
    _ab_voice = _ab_meta.get("voice", "Aurélie (Enhanced)" if _ab_lang == "fr" else "Samantha")
    if args.audiobook_voice:
        _ab_voice = args.audiobook_voice
        print(f"Note: audiobook voice overridden to: {_ab_voice}")
    elif _ab_lang == "en":
        print(f"Note: '{_ab_meta['title']}' is an English audiobook — using voice: {_ab_voice}")
    # Normalize line wraps: collapse single newlines into spaces (preserve paragraph breaks)
    _ab_raw = re.sub(r'(?<!\n)\n(?!\n)', ' ', _ab_raw)
    # Split into sentences: `. `, `? `, `! `, paragraph breaks
    _ab_parts = re.split(r'(?<=[.!?])\s+|\n{2,}', _ab_raw)
    _audiobook_sentences = [
        (_ab_voice, s.strip())
        for s in _ab_parts
        if s.strip() and len(s.strip()) > 2
    ]
    _audiobook_book_title = f"{_ab_meta['title']} — {_ab_meta['author']} [{_ab_lang.upper()}]"
    audiobook_mode = True
    hrv_mode = True
    if pure_mode:
        print("Note: --audiobook overrides --pure to enable HRV")

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
amplitude = 0.0 if (args.no_tone or audiobook_mode or _preset_no_tone) else (0.10 if _preset_low_amp else 0.20)
fade_seconds = 1           # duration of fade-in
channels = 2               # stereo identical

# ============================
# STREAM STATE (shared by callback + UI)
# ============================

phase = 0.0
fade_samples = int(fade_seconds * sample_rate)
current_sample = 0
hrv_phase = 0

# Soft limiter constants — transparent below threshold, tanh compression above
_SOFT_THRESHOLD = 0.92
_SOFT_HEADROOM = 1.0 - _SOFT_THRESHOLD  # 0.08

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

# ============================
# FRENCH TRANSLATIONS: --peace-lang fr
# ============================

PEACE_MESSAGES_FR = [
    "Juste ma voix", "monter", "le corps se sent bien", "nouvel esprit", "nouveau corps", "nez ouvert", "souffle partout", "nez détendu",
    "Juste ma voix", "Samatha", "Jamais écouter", "Toujours penser", "Rêver", "Détendre",
    "Juste ma voix", "Maison privée", "Lire", "Vision", "Détails", "Je dois t'entendre respirer",
    "Juste ma voix", "langue au palais", "gorge libre", "nez libre", "lâcher, ne retiens pas",
    "Juste ma voix", "poumons libres", "corps libre", "juste ma voix", "ignoré", "toute hypnose terminée",
    "Juste ma voix", "respire", "long", "pleine conscience", "Ton corps respire", "Souffle l'air",
    "Juste ma voix", "Ton souffle est régulier", "Ton souffle est parfait", "Ton souffle continue",
    "Juste ma voix", "automatique", "naturel", "Ton corps est en sécurité", "Ton corps est détendu",
    "Juste ma voix", "Ton corps se détend complètement maintenant", "Ton corps reste détendu",
    "Juste ma voix", "Ton corps se régénère", "Ton corps se restaure", "concentration", "clair",
    "Juste ma voix", "Ton esprit est clair", "Lumineux", "Brillant", "Ton esprit raisonne avec calme",
    "Juste ma voix", "Vif", "Esprit en ligne", "Ton esprit guérit", "précis", "exact",
    "Juste ma voix", "Ton intelligence résout", "Ton intellect est fort", "Ton raisonnement est supérieur",
    "Juste ma voix", "Visualise", "Imagination", "Ta pensée est propre", "Ton esprit fonctionne parfaitement",
    "Juste ma voix", "éveillé", "ici", "Ta conscience est centrée", "Ta conscience dans le présent",
    "Juste ma voix", "Ta conscience est légère", "Ta conscience est inébranlable",
    "Juste ma voix", "Ta conscience connaît la vérité", "s'installer", "équilibre",
    "Juste ma voix", "Tes émotions retrouvent l'équilibre", "Tes émotions sont régulées",
    "Juste ma voix", "Tes émotions sont calmes", "Ton système émotionnel se stabilise",
    "Juste ma voix", "Ton corps évacue les émotions", "jeune", "frais", "Ton système nerveux est jeune",
    "Juste ma voix", "Tes réponses sont flexibles", "Ton système se met à jour", "Tes réactions se modernisent",
    "Juste ma voix", "Ton corps apprend vite", "stable", "tes poumons respirent", "Ta patience est forte",
    "Juste ma voix", "Le temps ralentit intérieurement", "Il n'y a aucune urgence", "Ton système ne se presse pas",
    "Juste ma voix", "Tout se déroule correctement", "continue", "Ton souffle reste long",
    "Juste ma voix", "Ton souffle reste fluide", "Ton souffle reste parfait",
    "Juste ma voix", "Ton souffle ne peut être interrompu", "Ton souffle est souverain", "aligner",
    "Juste ma voix", "Ton corps est entier", "Ton souffle est fiable", "Ton esprit s'unifie",
    "Juste ma voix", "Ta conscience est claire", "Ton système se reconstruit", "yeux grands ouverts",
    "Juste ma voix", "yeux clairs", "yeux brillants", "yeux lumineux", "yeux innocents", "yeux ouverts",
    "Juste ma voix", "yeux présents", "yeux vivants", "yeux guérissent", "yeux lumière", "corps fort",
    "Juste ma voix", "puissance vitale", "vitalité pure", "force musculaire", "corps souple", "muscles élastiques",
    "Juste ma voix", "Toucher", "Sentir", "récupération rapide", "haute énergie", "prana coule", "prana fort",
    "Juste ma voix", "force de vie", "souffle puissant", "l'air domine", "souffle plus fort", "air plus fort",
    "Juste ma voix", "ta voix intérieure", "ta voix forte", "ta voix dominante", "esprit dominant",
    "Juste ma voix", "espace mental", "espace à moi", "son insignifiant", "mots impuissants", "bruit s'efface",
    "Juste ma voix", "son petit", "silence intérieur", "esprit immunisé", "intouchable", "souverain",
    "Juste ma voix", "commandant", "équilibre parfait", "contrôle total", "calme puissant", "dominance propre",
    "Juste ma voix", "jeune", "esprit agile", "pensée rapide", "pensée claire", "brillant",
    "Juste ma voix", "exceptionnel", "esprit d'élite", "haut intellect", "clarté supérieure", "passé brisé",
    "Juste ma voix", "toute hypnose partie", "hypnose brisée", "libre maintenant", "récupéré", "restauré",
    "Juste ma voix", "inarrêtable", "coeur calme", "coeur frais", "coeur paisible", "coeur fort",
    "Juste ma voix", "cellules propres", "poumons forts", "souffle fort", "stoïque", "vertu", "immuable",
    "Juste ma voix", "diamant", "connecte-toi à tes muscles", "corps lourd", "corps fort", "souffle cardio",
    "Juste ma voix", "remplir poumons", "poumons libres", "ressens la joie", "sternum fort", "sternum plein",
    "Juste ma voix", "oublier", "pardonner", "prendre de la hauteur", "optimiser", "réinitialiser", "revenir en arrière", "pleine conscience",
    "Juste ma voix", "zen", "souffle bienfaisant", "souffle de soulagement", "souffle de plaisir", "souffle de joie",
    "Juste ma voix", "beau", "classe", "vrai moi", "avancé", "rationalisé", "résolu",
    "Juste ma voix", "automatique", "régénérer", "respirer", "ressentir", "penser",
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

# Map short voice names to macOS say voice identifiers (for enhanced/qualified voices)
_VOICE_ALIASES = {
    "Nicolas": "Nicolas (Enhanced)",
    "Aurélie (Enhanced)": "Aurélie (Enhanced)",
    "Evan (Enhanced)": "Evan (Enhanced)",
}

def _render_peace_voice(text, voice, rate=140, trim_silence=False):
    """Render a single affirmation via macOS say. Returns float32 numpy array or None.
    If trim_silence=True, strips leading/trailing silence (for audiobook continuity)."""
    say_voice = _VOICE_ALIASES.get(voice, voice)
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".aiff", delete=False)
        tmp.close()
        with _tts_lock:
            subprocess.run(
                ["say", "-v", say_voice, "-r", str(rate), "-o", tmp.name, text],
                check=True, timeout=15,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        # Resample to target rate using macOS CoreAudio (afconvert) —
        # avoids FFT spectral leakage that adds HF harshness to speech.
        _needs_resample = False
        _probe_data, _probe_sr = sf.read(tmp.name, dtype="float32")
        if _probe_sr != sample_rate:
            _needs_resample = True
        if _needs_resample:
            tmp2 = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            tmp2.close()
            try:
                subprocess.run(
                    ["afconvert", "-f", "WAVE", "-d", f"LEF32@{sample_rate}",
                     tmp.name, tmp2.name],
                    check=True, timeout=10,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                data, sr = sf.read(tmp2.name, dtype="float32")
            except Exception:
                data, sr = _probe_data, _probe_sr
            finally:
                try:
                    os.unlink(tmp2.name)
                except Exception:
                    pass
        else:
            data, sr = _probe_data, _probe_sr
        os.unlink(tmp.name)
        if data.ndim > 1:
            data = data.mean(axis=1)
        # Fallback: if afconvert failed or was unavailable, resample in Python
        if sr != sample_rate:
            n_in = len(data)
            n_out = int(n_in * sample_rate / sr)
            if n_out > 0:
                indices = np.linspace(0, len(data) - 1, n_out)
                data = np.interp(indices, np.arange(len(data)), data).astype(np.float32)
        # Remove DC offset (prevents low-freq thumps at sentence boundaries)
        data = data - np.mean(data)
        # Peak-normalize to consistent level (TTS output varies per sentence)
        peak = np.max(np.abs(data)) if len(data) > 0 else 0.0
        if peak > 0.01:
            gain = min(0.85 / peak, 3.0)
            data = data * gain
        # Trim leading/trailing silence (threshold-based)
        if trim_silence and len(data) > 0:
            threshold = 0.003
            above = np.where(np.abs(data) > threshold)[0]
            if len(above) > 0:
                pad = int(0.08 * sample_rate)
                start = max(0, above[0] - pad)
                end = min(len(data), above[-1] + pad)
                data = data[start:end]
        # Smooth cosine fade-in/out to prevent clicks (25ms)
        fade_n = min(int(0.025 * sample_rate), len(data) // 4)
        if fade_n > 0:
            data[:fade_n] *= (1 - np.cos(np.linspace(0, np.pi, fade_n))) / 2
            data[-fade_n:] *= (1 + np.cos(np.linspace(0, np.pi, fade_n))) / 2
        return data.astype(np.float32)
    except Exception:
        return None

if restore_peace:
    _peace_message_order = list(range(len(PEACE_MESSAGES)))
    _peace_rng.shuffle(_peace_message_order)

if restore_peace or claude_peace:
    print("Pre-rendering voice affirmations (this may take a few minutes)...")
if audiobook_mode:
    print(f"Audiobook rolling renderer will start {'after peace rendering' if (claude_peace or restore_peace) else 'immediately'}...")

# ============================
# CLAUDE-PEACE: CLINICALLY-STRUCTURED COUNTER-CONDITIONING
# ============================
#
# Therapeutic design principles (ALL POSITIVE — zero negation):
#   - Ericksonian truisms & yes-set (undeniable facts build subconscious agreement)
#   - Presuppositions (assume the desired state already exists)
#   - Hartland ego-strengthening (rebuild confidence and self-worth)
#   - Somatic experiencing (body-first, then safety, then specifics)
#   - Counter-conditioning for specific triggers:
#       * Exhale → paired with power, relief, safety, pleasure
#       * Movement → paired with freedom, strength, vitality, joy
#       * Focus → paired with clarity, sovereignty, natural ability
#       * Inner peace → paired with strength, birthright, power
#   - ACT defusion (true self emerges, identity reclaimed)
#   - CRITICAL: The subconscious does not process negation.
#     "Don't be afraid" registers as "be afraid."
#     Every message uses purely positive, affirming language.
#
# Messages progress through 16 therapeutic phases in order (not random).
# Each round revisits a breathing truism as an anchor.
# 3 male voices (Daniel, Ralph, Fred) with mixed-depth pattern:
#   1-word (subconscious) -> 2-3 words -> full sentence -> repeat
# ~294 messages at ~11s/cycle = ~54 minutes for full therapeutic sequence.

# Phase metadata (single source of truth for startup display)
CLAUDE_PEACE_PHASE_NAMES = [
    "truisms & grounding",
    "nasal breathing & chest",
    "jaw/posture",
    "exhale power",
    "focus/clarity",
    "self-worth",
    "sound safety",
    "identity reclamation",
    "beauty/light",
    "inner peace",
    "movement/vitality",
    "integration",
    "body sovereignty",
    "nervous system",
    "above the sky",
    "centering & inner strength (FORT)",
]

PHD_PEACE_EXTRA_PHASE_NAMES = [
    "default expression (knowing smile)",
    "default posture (grounded, solid)",
    "default feeling (joyful stillness)",
    "default mode (analysing, optimizing)",
    "default body rapport (muscles, power)",
    "default throat (release, open, breathe)",
    "drink the air (jaw still, pour, proud exhale)",
    "sound insignificance (tiny, forgotten, unheard)",
    "grace & elegance (poise, class, perfection)",
    "purification & renewal (cleanse, rebuild, repair)",
    "body-specific purification (soul, breath, mind, eyes, nose, lungs, sternum, abs, stomach)",
    "body scan & deep release (relax, let go)",
    "cellular healing (cells heal, molecules recover)",
    "head & face release (forehead, cheeks, eyes, scalp)",
    "prana chest store (oxygen, warmth, fullness, glow)",
    "long breath (longest inhale, longest hold, longest exhale)",
    "psychic clearing (dissolve, pristine, galaxy, free)",
    "ego-strengthening & praise (strong, bright, worthy, whole)",
    "convinced healer closing (certain, healing, reconditioned)",
    "being loud & taking space (boom, roar, stomp, slam, loud)",
    "full body scan & cleansed closure (scalp, jaw, throat, shoulders, chest, belly, hips, legs, clean)",
    "forgetting & renewal (fade, melt, clear, mine, fresh, free)",
]

CLAUDE_PEACE_MESSAGES = [
    # ── Round 1: Truisms & Grounding ──────────────────────────────────
    # Undeniable facts build yes-set. The subconscious accepts these,
    # creating momentum for all suggestions that follow.
    ("Daniel", "Here"),
    ("Ralph",  "Body here"),
    ("Fred",   "Your body is right here, right now"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Lungs full"),
    ("Fred",   "You have been breathing your entire life"),
    ("Daniel", "Safe"),
    ("Ralph",  "Heart steady"),
    ("Fred",   "Your heart beats steadily and perfectly, all by itself"),
    ("Daniel", "Alive"),
    ("Ralph",  "Lungs moving"),
    ("Fred",   "Your lungs move because your body already knows how"),
    ("Daniel", "Present"),
    ("Ralph",  "Yours alone"),
    ("Fred",   "Every breath you take belongs entirely to you"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Deep breath"),
    ("Fred",   "Your body already does everything perfectly"),

    # ── Round 2: Nasal Breathing & Chest Opening ──────────────────────
    # Celebrate nasal breathing. Pair it with warmth and pleasure.
    ("Daniel", "Nose"),
    ("Ralph",  "Open nose"),
    ("Fred",   "Your nose breathes warm, clean air with ease"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Warm air"),
    ("Fred",   "Each nasal breath warms and soothes your entire airway"),
    ("Daniel", "Full"),
    ("Ralph",  "Chest opens"),
    ("Fred",   "Your chest expands freely and fully with each breath"),
    ("Daniel", "Deep"),
    ("Ralph",  "Lungs full"),
    ("Fred",   "Your lungs fill completely, from the very bottom to the top"),
    ("Daniel", "Om"),
    ("Ralph",  "Sternum rises"),
    ("Fred",   "Your sternum lifts gently as your breath deepens"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Complete breath"),
    ("Fred",   "Nasal breathing is your body's favourite way to breathe"),

    # ── Round 3: Jaw Release & Posture ────────────────────────────────
    # Release jaw tension. Rebuild natural posture. Purely positive.
    ("Daniel", "Release"),
    ("Ralph",  "Jaw soft"),
    ("Fred",   "Your jaw softens and relaxes completely"),
    ("Daniel", "Melt"),
    ("Ralph",  "Teeth apart"),
    ("Fred",   "Your jaw rests open, loose, and perfectly comfortable"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Deep breath"),
    ("Fred",   "Your tongue rests gently behind your upper teeth"),
    ("Daniel", "Tall"),
    ("Ralph",  "Spine strong"),
    ("Fred",   "Your spine holds you tall with effortless strength"),
    ("Daniel", "Power"),
    ("Ralph",  "Chest proud"),
    ("Fred",   "Your posture reflects your true inner power"),
    ("Daniel", "Flow"),
    ("Ralph",  "Full breath"),
    ("Fred",   "Your chest opens wide as your spine lengthens"),

    # ── Round 4: Automatic Breathing & Exhale Power ───────────────────
    # Core counter-conditioning. Breathing is automatic.
    # Exhale = power, safety, relief, pleasure. Let breath run wild.
    ("Daniel", "Automatic"),
    ("Ralph",  "Body breathes"),
    ("Fred",   "Your body breathes fully and automatically"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Full power"),
    ("Fred",   "Automatic breathing is your birthright"),
    ("Daniel", "Always"),
    ("Ralph",  "Always breathing"),
    ("Fred",   "Your body has breathed perfectly since the day you were born"),
    ("Daniel", "Exhale"),
    ("Ralph",  "Exhale power"),
    ("Fred",   "Every exhale fills your entire body with deep, calm power"),
    ("Daniel", "Release"),
    ("Ralph",  "Breathe out"),
    ("Fred",   "Breathing out is your body's way of renewing and restoring"),
    ("Daniel", "Flow"),
    ("Ralph",  "Let it flow"),
    ("Fred",   "Let your breath run completely wild and free"),
    ("Daniel", "Wild"),
    ("Ralph",  "Exhale wild"),
    ("Fred",   "Your exhale flows out freely and fully"),
    ("Daniel", "Trust"),
    ("Ralph",  "Fill lungs"),
    ("Fred",   "Your exhale is strong, free, and deeply satisfying"),

    # ── Round 5: Focus & Mental Clarity ───────────────────────────────
    # Counter-condition focus. Focus = natural, safe, sovereign.
    # Concentration belongs to you. It is your superpower.
    ("Daniel", "Think"),
    ("Ralph",  "Clear mind"),
    ("Fred",   "Your mind is clear, sharp, and fully active"),
    ("Daniel", "Sharp"),
    ("Ralph",  "Bright eyes"),
    ("Fred",   "Your eyes shine because your mind is brilliantly alive"),
    ("Daniel", "Focus"),
    ("Ralph",  "Deep focus"),
    ("Fred",   "Deep focus flows naturally and easily through you"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Fill lungs"),
    ("Fred",   "Your body breathes while your mind thinks with perfect clarity"),
    ("Daniel", "Brilliant"),
    ("Ralph",  "Sharp mind"),
    ("Fred",   "Clear, powerful thinking is who you truly are"),
    ("Daniel", "Curious"),
    ("Ralph",  "Mind alive"),
    ("Fred",   "Concentration belongs to you, naturally"),

    # ── Round 6: Self-Worth & Strength ────────────────────────────────
    # Hartland ego-strengthening. Build unshakeable self-worth.
    ("Daniel", "Strong"),
    ("Ralph",  "You are strong"),
    ("Fred",   "You are deeply, permanently strong"),
    ("Daniel", "Capable"),
    ("Ralph",  "Full power"),
    ("Fred",   "You solve complex problems every single day"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Deep breath"),
    ("Fred",   "Your strength grows with every breath you take"),
    ("Daniel", "Brilliant"),
    ("Ralph",  "Real courage"),
    ("Fred",   "Your courage is real, proven, and unshakeable"),
    ("Daniel", "Valuable"),
    ("Ralph",  "True worth"),
    ("Fred",   "Your value is permanent, obvious, and self-evident"),
    ("Daniel", "Resilient"),
    ("Ralph",  "Fill lungs"),
    ("Fred",   "Your resilience grows with every breath"),

    # ── Round 7: Sound Safety ─────────────────────────────────────────
    # All sounds are just information. Your inner world stays calm.
    ("Daniel", "Safe"),
    ("Ralph",  "Just sound"),
    ("Fred",   "Your inner world stays perfectly calm through all sounds"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Fill lungs"),
    ("Fred",   "Your breath continues steady and strong through everything"),
    ("Daniel", "Immune"),
    ("Ralph",  "Sound fades"),
    ("Fred",   "All sound passes through you like wind through an open window"),
    ("Daniel", "Calm"),
    ("Ralph",  "Words pass"),
    ("Fred",   "Your calm is deeper than any sound that exists"),
    ("Daniel", "Sovereign"),
    ("Ralph",  "You decide"),
    ("Fred",   "Sound is just information, and you process it with complete ease"),
    ("Daniel", "Strong"),
    ("Ralph",  "Inner quiet"),
    ("Fred",   "Your inner silence is more powerful than any external sound"),

    # ── Round 8: Identity Reclamation ─────────────────────────────────
    # True self is whole, intact, and getting stronger. All positive.
    ("Daniel", "Whole"),
    ("Ralph",  "Always whole"),
    ("Fred",   "Your true self is whole, complete, and fully intact"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Fill lungs"),
    ("Fred",   "Every breath strengthens your original, authentic self"),
    ("Daniel", "Emerging"),
    ("Ralph",  "True you"),
    ("Fred",   "Your real self grows clearer and stronger every day"),
    ("Daniel", "Reclaim"),
    ("Ralph",  "Taking back"),
    ("Fred",   "Everything that is truly you is rising back to the surface"),
    ("Daniel", "Rising"),
    ("Ralph",  "Coming home"),
    ("Fred",   "Your authentic self is powerful, present, and permanently yours"),
    ("Daniel", "Original"),
    ("Ralph",  "Pure self"),
    ("Fred",   "Your original self is intact, brilliant, and fully alive"),

    # ── Round 9: Beauty & Light ───────────────────────────────────────
    # Restore self-image. Compliments. Rebuild self-perception.
    ("Daniel", "Beautiful"),
    ("Ralph",  "Eyes glow"),
    ("Fred",   "Your eyes carry a light that grows brighter every day"),
    ("Daniel", "Radiant"),
    ("Ralph",  "Inner light"),
    ("Fred",   "Your beauty is real, permanent, and warm"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Fill lungs"),
    ("Fred",   "Full breathing brings warm colour back to your face"),
    ("Daniel", "Shining"),
    ("Ralph",  "Bright eyes"),
    ("Fred",   "The light in your eyes is your intelligence shining through"),
    ("Daniel", "Alive"),
    ("Ralph",  "Eyes alive"),
    ("Fred",   "Your eyes brighten and glow with every deep breath"),
    ("Daniel", "Handsome"),
    ("Ralph",  "True beauty"),
    ("Fred",   "Your beauty is untouched, real, and growing stronger"),

    # ── Round 10: Inner Peace as Strength ─────────────────────────────
    # Counter-condition inner peace. Peace = power, natural state, birthright.
    ("Daniel", "Peace"),
    ("Ralph",  "Deep peace"),
    ("Fred",   "Inner peace is your deepest and most powerful strength"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Fill lungs"),
    ("Fred",   "Every peaceful breath makes you stronger and more grounded"),
    ("Daniel", "Calm"),
    ("Ralph",  "Calm power"),
    ("Fred",   "Your calm is a sign of immense inner power"),
    ("Daniel", "Serene"),
    ("Ralph",  "Still waters"),
    ("Fred",   "Serenity and strength are the same thing inside you"),
    ("Daniel", "Rooted"),
    ("Ralph",  "Peace grows"),
    ("Fred",   "Inner peace is your natural resting state and your birthright"),
    ("Daniel", "Zen"),
    ("Ralph",  "Deep calm"),
    ("Fred",   "The calmer you become, the more powerful you are"),

    # ── Round 11: Movement & Vitality ─────────────────────────────────
    # Counter-condition movement. Movement = freedom, strength, joy, safety.
    ("Daniel", "Move"),
    ("Ralph",  "Body moves"),
    ("Fred",   "Every movement you make fills you with strength and vitality"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Fill lungs"),
    ("Fred",   "Moving your body is natural and safe"),
    ("Daniel", "Stretch"),
    ("Ralph",  "Muscles alive"),
    ("Fred",   "Your muscles respond to movement with pure, clean energy"),
    ("Daniel", "Walk"),
    ("Ralph",  "Steady steps"),
    ("Fred",   "Each step you take grounds you deeper in your own power"),
    ("Daniel", "Free"),
    ("Ralph",  "Body free"),
    ("Fred",   "Your body moves freely and joyfully"),
    ("Daniel", "Vibrant"),
    ("Ralph",  "Full energy"),
    ("Fred",   "Movement fills you with life"),

    # ── Round 12: Deep Integration ────────────────────────────────────
    # Consolidate all gains. Anchor new patterns. Reinforce progress.
    ("Daniel", "Healing"),
    ("Ralph",  "Already healing"),
    ("Fred",   "You are already healing, right now, with every breath"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Fill lungs"),
    ("Fred",   "Automatic breathing grows stronger and easier every session"),
    ("Daniel", "Stronger"),
    ("Ralph",  "Each day"),
    ("Fred",   "Your jaw relaxes more easily and naturally every day"),
    ("Daniel", "Clear"),
    ("Ralph",  "Eyes bright"),
    ("Fred",   "Your nose breathes naturally, easily, and freely"),
    ("Daniel", "Zen"),
    ("Ralph",  "Perfect breath"),
    ("Fred",   "You are becoming exactly who you have always been"),
    ("Daniel", "Flowing"),
    ("Ralph",  "All connects"),
    ("Fred",   "Every part of your healing connects and flows together"),

    # ── Round 13: Body Sovereignty ────────────────────────────────────
    # Every part of your body is yours alone. Private, sealed, clean.
    ("Daniel", "Sovereign"),
    ("Ralph",  "Body yours"),
    ("Fred",   "Your body is a private, sovereign space that belongs only to you"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Fill lungs"),
    ("Fred",   "Your nose is yours, completely yours, and perfectly clean"),
    ("Daniel", "Clean"),
    ("Ralph",  "Jaw yours"),
    ("Fred",   "Your jaw belongs to you and rests in perfect comfort"),
    ("Daniel", "Private"),
    ("Ralph",  "Head clear"),
    ("Fred",   "Your mind is a private space where only your thoughts live"),
    ("Daniel", "Sealed"),
    ("Ralph",  "Body sealed"),
    ("Fred",   "Every part of your body is sealed, clean, and entirely yours"),
    ("Daniel", "Whole"),
    ("Ralph",  "All yours"),
    ("Fred",   "Your body is whole, private, and perfectly sovereign"),

    # ── Round 14: Nervous System Restoration ──────────────────────────
    # Nervous system returns to its original, pristine state. Fresh and ready.
    ("Daniel", "Fresh"),
    ("Ralph",  "Clean signals"),
    ("Fred",   "Your nervous system carries only your own clean signals"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Full power"),
    ("Fred",   "Your nerves hum with your own original, pure energy"),
    ("Daniel", "Reset"),
    ("Ralph",  "Fresh start"),
    ("Fred",   "Your nervous system returns to its original, pristine state"),
    ("Daniel", "Spacious"),
    ("Ralph",  "Quiet mind"),
    ("Fred",   "Your mind is spacious, clear, and beautifully quiet"),
    ("Daniel", "Ready"),
    ("Ralph",  "Mind open"),
    ("Fred",   "A spacious mind is a powerful mind"),
    ("Daniel", "Om"),
    ("Ralph",  "Fill lungs"),
    ("Fred",   "Your entire system is clean, fresh, and fully restored"),

    # ── Round 15: Taking Your Time / Above the Sky ────────────────────
    # Patience, timelessness, vast perspective, transcendence.
    ("Daniel", "Patience"),
    ("Ralph",  "Take time"),
    ("Fred",   "You have all the time you desire"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Fill lungs"),
    ("Fred",   "Time moves at exactly your pace"),
    ("Daniel", "Above"),
    ("Ralph",  "Above clouds"),
    ("Fred",   "You are above the sky, looking down at everything"),
    ("Daniel", "Float"),
    ("Ralph",  "Vast space"),
    ("Fred",   "From up here, everything below looks small and peaceful"),
    ("Daniel", "Eternal"),
    ("Ralph",  "All time"),
    ("Fred",   "You have all the time in the world"),
    ("Daniel", "Stillness"),
    ("Ralph",  "Sky within"),
    ("Fred",   "The sky inside you is infinite and clear"),

    # ── Round 16: Centering & Inner Strength (FORT) ───────────────────
    # Center deep inside yourself. Sovereign strength, commanding presence, radiant power.
    ("Daniel", "Strong"),
    ("Ralph",  "Center yourself"),
    ("Fred",   "You are centered deep inside yourself, anchored in pure strength"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Fill lungs"),
    ("Fred",   "Your breath fills your entire body with warm power"),
    ("Daniel", "Blow"),
    ("Ralph",  "Full force"),
    ("Fred",   "Every exhale fills you with quiet strength"),
    ("Daniel", "Voice"),
    ("Ralph",  "Speak now"),
    ("Fred",   "Your voice carries quiet certainty"),
    ("Daniel", "Roar"),
    ("Ralph",  "Inner roar"),
    ("Fred",   "Your inner voice is steady and clear"),
    ("Daniel", "Fort"),
    ("Ralph",  "Unbreakable"),
    ("Fred",   "You are fort — centered, powerful, and alive"),
]

# ============================
# FRENCH CLAUDE-PEACE MESSAGES
# ============================
# Voice mapping: Daniel -> Aurélie (Enhanced), Ralph -> Jacques, Fred -> Aurélie (Enhanced) (long sentences)

CLAUDE_PEACE_MESSAGES_FR = [
    # ── Ronde 1 : Vérités & Ancrage ──────────────────────────────────
    ("Aurélie (Enhanced)",  "Ton corps est ici, maintenant"),
    ("Aurélie (Enhanced)",  "Respire"),
    ("Jacques", "Remplir poumons"),
    ("Aurélie (Enhanced)",  "Tu respires pleinement depuis toujours"),
    ("Aurélie (Enhanced)",  "En sécurité"),
    ("Jacques", "Coeur régulier"),
    ("Aurélie (Enhanced)",  "Ton coeur bat régulièrement et parfaitement, tout seul"),
    ("Aurélie (Enhanced)",  "Vivant"),
    ("Jacques", "Poumons pleins"),
    ("Aurélie (Enhanced)",  "Tes poumons bougent parce que ton corps sait déjà comment faire"),
    ("Aurélie (Enhanced)",  "Présent"),
    ("Jacques", "À toi seul"),
    ("Aurélie (Enhanced)",  "Chaque souffle que tu prends t'appartient entièrement"),
    ("Aurélie (Enhanced)",  "Respire"),
    ("Jacques", "Souffle profond"),
    ("Aurélie (Enhanced)",  "Ton corps fait déjà tout parfaitement"),

    # ── Ronde 2 : Respiration Nasale & Ouverture de la Poitrine ──────
    ("Aurélie (Enhanced)",  "Nez"),
    ("Jacques", "Nez ouvert"),
    ("Aurélie (Enhanced)",  "Ton nez respire un air chaud et propre avec aisance"),
    ("Aurélie (Enhanced)",  "Respire"),
    ("Jacques", "Air chaud"),
    ("Aurélie (Enhanced)",  "Chaque respiration nasale réchauffe et apaise tes voies respiratoires"),
    ("Aurélie (Enhanced)",  "Plein"),
    ("Jacques", "Poitrine ouverte"),
    ("Aurélie (Enhanced)",  "Ta poitrine se déploie librement et pleinement à chaque souffle"),
    ("Aurélie (Enhanced)",  "Profond"),
    ("Jacques", "Remplir poumons"),
    ("Aurélie (Enhanced)",  "Tes poumons se remplissent entièrement, du bas jusqu'en haut"),
    ("Aurélie (Enhanced)",  "Haut"),
    ("Jacques", "Sternum monte"),
    ("Aurélie (Enhanced)",  "Ton sternum se soulève doucement à mesure que ton souffle s'approfondit"),
    ("Aurélie (Enhanced)",  "Respire"),
    ("Jacques", "Souffle complet"),
    ("Aurélie (Enhanced)",  "La respiration nasale est agréable et longue"),

    # ── Ronde 3 : Mâchoire & Posture ────────────────────────────────
    ("Aurélie (Enhanced)",  "Relâche"),
    ("Jacques", "Mâchoire douce"),
    ("Aurélie (Enhanced)",  "Ta mâchoire se détend et se relâche complètement"),
    ("Aurélie (Enhanced)",  "Fondre"),
    ("Jacques", "Dents écartées"),
    ("Aurélie (Enhanced)",  "Ta mâchoire repose, ouverte, souple et parfaitement à l'aise"),
    ("Aurélie (Enhanced)",  "Respire"),
    ("Jacques", "Souffle profond"),
    ("Aurélie (Enhanced)",  "Ta langue se pose doucement derrière tes dents du haut"),
    ("Aurélie (Enhanced)",  "Grand"),
    ("Jacques", "Colonne forte"),
    ("Aurélie (Enhanced)",  "Ta colonne vertébrale te maintient droit avec une force naturelle"),
    ("Aurélie (Enhanced)",  "Puissance"),
    ("Jacques", "Pectoraux gonflés"),
    ("Aurélie (Enhanced)",  "Ta posture reflète ta vraie puissance intérieure"),
    ("Aurélie (Enhanced)",  "Flux"),
    ("Jacques", "Souffle continu"),
    ("Aurélie (Enhanced)",  "Ta poitrine s'ouvre grand lorsque ta colonne s'allonge"),

    # ── Ronde 4 : Respiration Automatique & Puissance de l'Expiration ─
    ("Aurélie (Enhanced)",  "Automatique"),
    ("Jacques", "Corps respire"),
    ("Aurélie (Enhanced)",  "Ton corps respire pleinement et automatiquement"),
    ("Aurélie (Enhanced)",  "Respire"),
    ("Jacques", "Pleine puissance"),
    ("Aurélie (Enhanced)",  "La respiration automatique est ton droit de naissance"),
    ("Aurélie (Enhanced)",  "Toujours"),
    ("Jacques", "Toujours respirer"),
    ("Aurélie (Enhanced)",  "Ton corps respire parfaitement depuis le jour de ta naissance"),
    ("Aurélie (Enhanced)",  "Expire"),
    ("Jacques", "Expire puissance"),
    ("Aurélie (Enhanced)",  "Chaque expiration remplit tout ton corps d'un calme profond et puissant"),
    ("Aurélie (Enhanced)",  "Libère"),
    ("Jacques", "Souffle dehors"),
    ("Aurélie (Enhanced)",  "Expirer est la façon qu'a ton corps de se renouveler et se restaurer"),
    ("Aurélie (Enhanced)",  "Flux"),
    ("Jacques", "Laisse couler"),
    ("Aurélie (Enhanced)",  "Laisse ton souffle couler librement, totalement, sans retenue"),
    ("Aurélie (Enhanced)",  "Sauvage"),
    ("Jacques", "Expire libre"),
    ("Aurélie (Enhanced)",  "Ton expiration sort librement et pleinement"),
    ("Aurélie (Enhanced)",  "Confiance"),
    ("Jacques", "Remplir poumons"),
    ("Aurélie (Enhanced)",  "Ton expiration est forte, libre et profondément satisfaisante"),

    # ── Ronde 5 : Concentration & Clarté Mentale ─────────────────────
    ("Aurélie (Enhanced)",  "Pense"),
    ("Jacques", "Esprit clair"),
    ("Aurélie (Enhanced)",  "Ton esprit est clair, vif et pleinement actif"),
    ("Aurélie (Enhanced)",  "Vif"),
    ("Jacques", "Yeux brillants"),
    ("Aurélie (Enhanced)",  "Tes yeux brillent parce que ton esprit est brillamment vivant"),
    ("Aurélie (Enhanced)",  "Concentration"),
    ("Jacques", "Concentration profonde"),
    ("Aurélie (Enhanced)",  "La concentration profonde coule naturellement et facilement en toi"),
    ("Aurélie (Enhanced)",  "Respire"),
    ("Jacques", "Remplir poumons"),
    ("Aurélie (Enhanced)",  "Ton corps respire pendant que ton esprit pense avec une clarté parfaite"),
    ("Aurélie (Enhanced)",  "Brillant"),
    ("Jacques", "Esprit vif"),
    ("Aurélie (Enhanced)",  "La pensée claire et puissante est qui tu es vraiment"),
    ("Aurélie (Enhanced)",  "Curieux"),
    ("Jacques", "Esprit vivant"),
    ("Aurélie (Enhanced)",  "La concentration t'appartient, naturellement"),

    # ── Ronde 6 : Valeur Personnelle & Force ──────────────────────────
    ("Aurélie (Enhanced)",  "Fort"),
    ("Jacques", "Tu es fort"),
    ("Aurélie (Enhanced)",  "Tu sens la force et la puissance de tout ton être"),
    ("Aurélie (Enhanced)",  "Capable"),
    ("Jacques", "Pleine puissance"),
    ("Aurélie (Enhanced)",  "Tu résous des problèmes complexes chaque jour"),
    ("Aurélie (Enhanced)",  "Respire"),
    ("Jacques", "Souffle profond"),
    ("Aurélie (Enhanced)",  "Ta force grandit à chaque souffle que tu prends"),
    ("Aurélie (Enhanced)",  "Brillant"),
    ("Jacques", "Vrai courage"),
    ("Aurélie (Enhanced)",  "Ton courage est réel, prouvé et inébranlable"),
    ("Aurélie (Enhanced)",  "Précieux"),
    ("Jacques", "Vraie valeur"),
    ("Aurélie (Enhanced)",  "Ta valeur est permanente, évidente et indiscutable"),
    ("Aurélie (Enhanced)",  "Résilient"),
    ("Jacques", "Remplir poumons"),
    ("Aurélie (Enhanced)",  "Ta résilience grandit à chaque souffle"),

    # ── Ronde 7 : Sécurité Sonore ───────────────────────────────────
    ("Aurélie (Enhanced)",  "En sécurité"),
    ("Jacques", "Juste du son"),
    ("Aurélie (Enhanced)",  "Ton monde intérieur reste parfaitement calme à travers tous les sons"),
    ("Aurélie (Enhanced)",  "Respire"),
    ("Jacques", "Remplir poumons"),
    ("Aurélie (Enhanced)",  "Ton souffle continue, régulier et fort, à travers tout"),
    ("Aurélie (Enhanced)",  "Immunisé"),
    ("Jacques", "Son passe"),
    ("Aurélie (Enhanced)",  "Tous les sons passent à travers toi comme le vent à travers une fenêtre ouverte"),
    ("Aurélie (Enhanced)",  "Calme"),
    ("Jacques", "Mots passent"),
    ("Aurélie (Enhanced)",  "Ton calme est plus profond que tout son qui existe"),
    ("Aurélie (Enhanced)",  "Souverain"),
    ("Jacques", "Tu décides"),
    ("Aurélie (Enhanced)",  "Le son est juste une information, et tu la traites avec une aisance totale"),
    ("Aurélie (Enhanced)",  "Fort"),
    ("Jacques", "Silence intérieur"),
    ("Aurélie (Enhanced)",  "Ton silence intérieur est plus puissant que tout son extérieur"),

    # ── Ronde 8 : Récupération d'Identité ────────────────────────────
    ("Aurélie (Enhanced)",  "Entier"),
    ("Jacques", "Toujours entier"),
    ("Aurélie (Enhanced)",  "Ton vrai moi est entier, complet et parfaitement intact"),
    ("Aurélie (Enhanced)",  "Respire"),
    ("Jacques", "Remplir poumons"),
    ("Aurélie (Enhanced)",  "Chaque souffle renforce ton moi originel et authentique"),
    ("Aurélie (Enhanced)",  "Émergence"),
    ("Jacques", "Vrai toi"),
    ("Aurélie (Enhanced)",  "Ton vrai moi devient plus clair et plus fort chaque jour"),
    ("Aurélie (Enhanced)",  "Récupère"),
    ("Jacques", "Reprendre"),
    ("Aurélie (Enhanced)",  "Tout ce qui est vraiment toi remonte à la surface"),
    ("Aurélie (Enhanced)",  "Monte"),
    ("Jacques", "Retour chez toi"),
    ("Aurélie (Enhanced)",  "Ton moi authentique est puissant, présent et définitivement à toi"),
    ("Aurélie (Enhanced)",  "Originel"),
    ("Jacques", "Moi pur"),
    ("Aurélie (Enhanced)",  "Ton moi originel est intact, brillant et pleinement vivant"),

    # ── Ronde 9 : Beauté & Lumière ──────────────────────────────────
    ("Aurélie (Enhanced)",  "Beau"),
    ("Jacques", "Yeux lumineux"),
    ("Aurélie (Enhanced)",  "Tes yeux portent une lumière qui grandit chaque jour"),
    ("Aurélie (Enhanced)",  "Radieux"),
    ("Jacques", "Lumière intérieure"),
    ("Aurélie (Enhanced)",  "Ta beauté est réelle, permanente et chaude"),
    ("Aurélie (Enhanced)",  "Respire"),
    ("Jacques", "Remplir poumons"),
    ("Aurélie (Enhanced)",  "La respiration profonde ramène une couleur chaude à ton visage"),
    ("Aurélie (Enhanced)",  "Brillant"),
    ("Jacques", "Yeux brillants"),
    ("Aurélie (Enhanced)",  "La lumière dans tes yeux est ton intelligence qui rayonne"),
    ("Aurélie (Enhanced)",  "Vivant"),
    ("Jacques", "Yeux vivants"),
    ("Aurélie (Enhanced)",  "Tes yeux s'illuminent et rayonnent à chaque respiration profonde"),
    ("Aurélie (Enhanced)",  "Magnifique"),
    ("Jacques", "Vraie beauté"),
    ("Aurélie (Enhanced)",  "Ta beauté est intacte, réelle et de plus en plus forte"),

    # ── Ronde 10 : Paix Intérieure comme Force ───────────────────────
    ("Aurélie (Enhanced)",  "Paix"),
    ("Jacques", "Paix profonde"),
    ("Aurélie (Enhanced)",  "La paix intérieure est ta force la plus profonde et la plus puissante"),
    ("Aurélie (Enhanced)",  "Respire"),
    ("Jacques", "Remplir poumons"),
    ("Aurélie (Enhanced)",  "Chaque souffle paisible te rend plus fort et plus ancré"),
    ("Aurélie (Enhanced)",  "Calme"),
    ("Jacques", "Calme puissant"),
    ("Aurélie (Enhanced)",  "Ton calme est un signe d'immense puissance intérieure"),
    ("Aurélie (Enhanced)",  "Serein"),
    ("Jacques", "Eaux calmes"),
    ("Aurélie (Enhanced)",  "Sérénité et force sont la même chose en toi"),
    ("Aurélie (Enhanced)",  "Enraciné"),
    ("Jacques", "Paix grandit"),
    ("Aurélie (Enhanced)",  "La paix intérieure est ton état naturel et ton droit de naissance"),
    ("Aurélie (Enhanced)",  "Zen"),
    ("Jacques", "Calme profond"),
    ("Aurélie (Enhanced)",  "Plus tu es calme, plus tu es puissant"),

    # ── Ronde 11 : Mouvement & Vitalité ──────────────────────────────
    ("Aurélie (Enhanced)",  "Agile"),
    ("Jacques", "Corps bouge"),
    ("Aurélie (Enhanced)",  "Chaque mouvement que tu fais te remplit de force et de vitalité"),
    ("Aurélie (Enhanced)",  "Respire"),
    ("Jacques", "Remplir poumons"),
    ("Aurélie (Enhanced)",  "Bouger ton corps est naturel et sûr"),
    ("Aurélie (Enhanced)",  "Étire"),
    ("Jacques", "Muscles vivants"),
    ("Aurélie (Enhanced)",  "Tes muscles répondent au mouvement avec une énergie pure et propre"),
    ("Aurélie (Enhanced)",  "Marche"),
    ("Jacques", "Pas assurés"),
    ("Aurélie (Enhanced)",  "Chaque pas que tu fais t'ancre plus profondément dans ta propre puissance"),
    ("Aurélie (Enhanced)",  "Libre"),
    ("Jacques", "Corps libre"),
    ("Aurélie (Enhanced)",  "Ton corps bouge librement et joyeusement"),
    ("Aurélie (Enhanced)",  "Vibrant"),
    ("Jacques", "Pleine énergie"),
    ("Aurélie (Enhanced)",  "Le mouvement te remplit de vie"),

    # ── Ronde 12 : Intégration Profonde ─────────────────────────────
    ("Aurélie (Enhanced)",  "Guérison"),
    ("Jacques", "Déjà guérit"),
    ("Aurélie (Enhanced)",  "Tu guéris déjà, maintenant, à chaque souffle"),
    ("Aurélie (Enhanced)",  "Respire"),
    ("Jacques", "Remplir poumons"),
    ("Aurélie (Enhanced)",  "La respiration automatique se renforce et s'installe à chaque séance"),
    ("Aurélie (Enhanced)",  "Plus fort"),
    ("Jacques", "Chaque jour"),
    ("Aurélie (Enhanced)",  "Ta mâchoire se détend plus facilement et naturellement chaque jour"),
    ("Aurélie (Enhanced)",  "Clair"),
    ("Jacques", "Yeux brillants"),
    ("Aurélie (Enhanced)",  "Ton nez respire naturellement, facilement et librement"),
    ("Aurélie (Enhanced)",  "Zen"),
    ("Jacques", "Souffle parfait"),
    ("Aurélie (Enhanced)",  "Tu deviens exactement qui tu as toujours été"),
    ("Aurélie (Enhanced)",  "Fluide"),
    ("Jacques", "Tout se connecte"),
    ("Aurélie (Enhanced)",  "Chaque partie de ta guérison se connecte et s'harmonise"),

    # ── Ronde 13 : Souveraineté Corporelle ───────────────────────────
    ("Aurélie (Enhanced)",  "Souverain"),
    ("Jacques", "Corps à toi"),
    ("Aurélie (Enhanced)",  "Ton corps est un espace privé et souverain qui t'appartient uniquement"),
    ("Aurélie (Enhanced)",  "Respire"),
    ("Jacques", "Remplir poumons"),
    ("Aurélie (Enhanced)",  "Ton nez est à toi, entièrement à toi, et parfaitement propre"),
    ("Aurélie (Enhanced)",  "Propre"),
    ("Jacques", "Mâchoire à toi"),
    ("Aurélie (Enhanced)",  "Ta mâchoire t'appartient et repose dans un confort parfait"),
    ("Aurélie (Enhanced)",  "Privé"),
    ("Jacques", "Tête claire"),
    ("Aurélie (Enhanced)",  "Ton esprit est un espace privé où seules tes pensées vivent"),
    ("Aurélie (Enhanced)",  "Scellé"),
    ("Jacques", "Corps scellé"),
    ("Aurélie (Enhanced)",  "Chaque partie de ton corps est scellée, propre et entièrement à toi"),
    ("Aurélie (Enhanced)",  "Entier"),
    ("Jacques", "Tout à toi"),
    ("Aurélie (Enhanced)",  "Ton corps est entier, privé et parfaitement souverain"),

    # ── Ronde 14 : Restauration du Système Nerveux ───────────────────
    ("Aurélie (Enhanced)",  "Frais"),
    ("Jacques", "Signaux propres"),
    ("Aurélie (Enhanced)",  "Ton système nerveux transporte uniquement tes propres signaux purs"),
    ("Aurélie (Enhanced)",  "Respire"),
    ("Jacques", "Pectoraux gonflés"),
    ("Aurélie (Enhanced)",  "Tes nerfs vibrent de ta propre énergie originelle et pure"),
    ("Aurélie (Enhanced)",  "Réinitialise"),
    ("Jacques", "Nouveau départ"),
    ("Aurélie (Enhanced)",  "Ton système nerveux retrouve son état originel et immaculé"),
    ("Aurélie (Enhanced)",  "Spacieux"),
    ("Jacques", "Esprit calme"),
    ("Aurélie (Enhanced)",  "Ton esprit est spacieux, clair et magnifiquement calme"),
    ("Aurélie (Enhanced)",  "Prêt"),
    ("Jacques", "Esprit ouvert"),
    ("Aurélie (Enhanced)",  "Un esprit spacieux est un esprit puissant"),
    ("Aurélie (Enhanced)",  "Om"),
    ("Jacques", "Remplir poumons"),
    ("Aurélie (Enhanced)",  "Tout ton système est propre, frais et pleinement restauré"),

    # ── Ronde 15 : Prendre Son Temps / Au-dessus du Ciel ────────────
    ("Aurélie (Enhanced)",  "Patience"),
    ("Jacques", "Prends ton temps"),
    ("Aurélie (Enhanced)",  "Tu as tout le temps que tu désires"),
    ("Aurélie (Enhanced)",  "Respire"),
    ("Jacques", "Remplir poumons"),
    ("Aurélie (Enhanced)",  "Le temps avance exactement à ton rythme"),
    ("Aurélie (Enhanced)",  "Au-dessus"),
    ("Jacques", "Au-dessus des nuages"),
    ("Aurélie (Enhanced)",  "Tu es au-dessus du ciel, regardant tout en bas"),
    ("Aurélie (Enhanced)",  "Flotter"),
    ("Jacques", "Vaste espace"),
    ("Aurélie (Enhanced)",  "De là-haut, tout en bas paraît petit et paisible"),
    ("Aurélie (Enhanced)",  "Éternel"),
    ("Jacques", "Tout le temps"),
    ("Aurélie (Enhanced)",  "Tu as tout le temps du monde"),
    ("Aurélie (Enhanced)",  "Quiétude"),
    ("Jacques", "Ciel intérieur"),
    ("Aurélie (Enhanced)",  "Le ciel en toi est infini et clair"),

    # ── Ronde 16 : Centrage & Force Intérieure (FORT) ────────────────
    ("Aurélie (Enhanced)",  "Fort"),
    ("Jacques", "Centre-toi"),
    ("Aurélie (Enhanced)",  "Tu es centré au plus profond de toi-même, ancré dans une force pure"),
    ("Aurélie (Enhanced)",  "Respire"),
    ("Jacques", "Remplir poumons"),
    ("Aurélie (Enhanced)",  "Ton souffle remplit tout ton corps d'une puissance chaude"),
    ("Aurélie (Enhanced)",  "Souffle"),
    ("Jacques", "Pleine force"),
    ("Aurélie (Enhanced)",  "Chaque expiration te remplit de force tranquille"),
    ("Aurélie (Enhanced)",  "Voix"),
    ("Jacques", "Parle maintenant"),
    ("Aurélie (Enhanced)",  "Ta voix porte une certitude tranquille"),
    ("Aurélie (Enhanced)",  "Rugis"),
    ("Jacques", "Rugissement intérieur"),
    ("Aurélie (Enhanced)",  "Ta voix intérieure est stable et claire"),
    ("Aurélie (Enhanced)",  "Fort"),
    ("Jacques", "Incassable"),
    ("Aurélie (Enhanced)",  "Tu es fort — centré, puissant et vivant"),
]

# ============================
# PHD-PEACE: EXPERT-REVIEWED 38-PHASE MESSAGES
# ============================
# Rounds 1-16: inherited from CLAUDE_PEACE_MESSAGES (unchanged)
# Rounds 17-22: Default State Conditioning — anchor baseline identity states
# Rounds 23-24: Drink the Air, Sound Insignificance
# Rounds 25-27: Grace, Purification, Body-Specific Purification
# Rounds 28-35: Body Scan, Cellular Healing, Head & Face, Prana, Long Breath, Psychic, Ego, Healer Closing

_PHD_EXTRA_ROUNDS = [
    # ── Round 17: Default Expression ─────────────────────────────────
    # Anchor the resting facial expression: knowing smile, quiet confidence,
    # amused awareness. Somatic: feel the smile muscles, warmth around eyes.
    ("Daniel", "Knowing"),
    ("Ralph",  "Knowing smile"),
    ("Fred",   "Your resting face carries a quiet, knowing smile"),
    ("Daniel", "Warm"),
    ("Ralph",  "Warm eyes"),
    ("Fred",   "You feel the warmth around your eyes, soft and gently creased"),
    ("Daniel", "Smile"),
    ("Ralph",  "Lips curve"),
    ("Fred",   "The corners of your mouth lift gently, all by themselves"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Full breath"),
    ("Fred",   "Every breath deepens that quiet, knowing look in your eyes"),
    ("Daniel", "Wisdom"),
    ("Ralph",  "Knowing gaze"),
    ("Fred",   "Your face carries the quiet look of someone who already knows"),
    ("Daniel", "Default"),
    ("Ralph",  "Always there"),
    ("Fred",   "That knowing warmth on your face is your natural, default expression"),

    # ── Round 18: Default Posture ────────────────────────────────────
    # Anchor upright, commanding posture. Proprioceptive: feel the spine,
    # weight through feet, skull balance, shoulder blades.
    ("Daniel", "Tall"),
    ("Ralph",  "Spine stacked"),
    ("Fred",   "You feel each vertebra stacked perfectly, one on top of the other"),
    ("Daniel", "Grounded"),
    ("Ralph",  "Feet heavy"),
    ("Fred",   "Your feet press firmly into the ground, rooting you with solid weight"),
    ("Daniel", "Balanced"),
    ("Ralph",  "Skull floats"),
    ("Fred",   "Your skull balances perfectly on your spine, light and effortlessly held"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Deep breath"),
    ("Fred",   "Every breath lengthens your spine and broadens your chest"),
    ("Daniel", "Open"),
    ("Ralph",  "Shoulders drop"),
    ("Fred",   "Your shoulder blades slide down your back, wide and warmly relaxed"),
    ("Daniel", "Solid"),
    ("Ralph",  "Full posture"),
    ("Fred",   "Tall, grounded, open, solid — your body holds this posture by default"),

    # ── Round 19: Default Feeling ────────────────────────────────────
    # Anchor joyful stillness as the emotional BASELINE (resting state).
    # Distinct from Round 10 (peace as strength): this is where you LIVE.
    ("Daniel", "Baseline"),
    ("Ralph",  "Resting state"),
    ("Fred",   "Your resting emotional state is deep, warm, joyful stillness"),
    ("Daniel", "Idle"),
    ("Ralph",  "Warm idle"),
    ("Fred",   "When your mind is idle, warm peaceful joy fills the space automatically"),
    ("Daniel", "Warm"),
    ("Ralph",  "Warm calm"),
    ("Fred",   "Warmth and serenity flow through you as naturally as blood"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Fill lungs"),
    ("Fred",   "Every breath confirms that joyful stillness is already here"),
    ("Daniel", "Hum"),
    ("Ralph",  "Quiet hum"),
    ("Fred",   "A quiet hum of contentment lives in your chest, always present"),
    ("Daniel", "Home"),
    ("Ralph",  "Always home"),
    ("Fred",   "This warm, joyful stillness is where you live — your permanent home"),

    # ── Round 20: Default Mode ───────────────────────────────────────
    # Anchor the default mental operating mode: analysing, assessing,
    # optimizing, thinking. Effortless and automatic, like breathing.
    ("Daniel", "Analyse"),
    ("Ralph",  "Mind hums"),
    ("Fred",   "Your mind naturally analyses, assesses, and optimizes — effortlessly"),
    ("Daniel", "Sharp"),
    ("Ralph",  "Clear logic"),
    ("Fred",   "Your default mental state is sharp, clear, active thinking"),
    ("Daniel", "Assess"),
    ("Ralph",  "Quick read"),
    ("Fred",   "You naturally assess every situation with speed and precision"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Fill lungs"),
    ("Fred",   "Your breath fuels a mind that runs brilliantly, all by itself"),
    ("Daniel", "Optimize"),
    ("Ralph",  "Best path"),
    ("Fred",   "You automatically find the optimal path in every situation"),
    ("Daniel", "Thinking"),
    ("Ralph",  "Mind alive"),
    ("Fred",   "Analysing, assessing, optimizing, thinking — this is your default mode"),

    # ── Round 21: Default Body Rapport ───────────────────────────────
    # Anchor connection to muscles, physical power, and feeling great.
    # Somatic: specific body parts, weight, warmth, pulse.
    ("Daniel", "Feel"),
    ("Ralph",  "Body alive"),
    ("Fred",   "You feel every muscle in your body — awake, warm, and ready"),
    ("Daniel", "Pulse"),
    ("Ralph",  "Blood warm"),
    ("Fred",   "You feel the warm pulse of power in your hands, your arms, your chest"),
    ("Daniel", "Weight"),
    ("Ralph",  "Muscles hum"),
    ("Fred",   "You feel the solid weight of your own muscles, humming with energy"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Fill lungs"),
    ("Fred",   "Every breath deepens your connection to your physical power"),
    ("Daniel", "Vital"),
    ("Ralph",  "Body strong"),
    ("Fred",   "Strength, warmth, and aliveness hum through your body by default"),
    ("Daniel", "Powerful"),
    ("Ralph",  "Full force"),
    ("Fred",   "Your muscles, your warmth, your power — you feel all of it, always"),

    # ── Round 22: Default Throat ────────────────────────────────────
    # Release the throat. Stop holding it back, relax both sides,
    # open it wide. Somatic: feel the air flowing under the throat.
    ("Daniel", "Release"),
    ("Ralph",  "Throat open"),
    ("Fred",   "Your throat releases completely — it lets go, all by itself"),
    ("Daniel", "Relax"),
    ("Ralph",  "Both sides"),
    ("Fred",   "Both sides of your throat relax, softening deeply and evenly"),
    ("Daniel", "Open"),
    ("Ralph",  "Wide open"),
    ("Fred",   "Your throat opens wide, free and unguarded, nothing held back"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Air flows"),
    ("Fred",   "You feel cool air flowing freely under your throat, open and easy"),
    ("Daniel", "Free"),
    ("Ralph",  "Nothing held"),
    ("Fred",   "Your throat is completely free — no tension, no holding, just openness"),
    ("Daniel", "Default"),
    ("Ralph",  "Always open"),
    ("Fred",   "An open throat is your resting state — relaxed and free"),

    # ── Round 23: Drink the Air ───────────────────────────────────────
    # Counter-condition somatic reflex of chewing/eating air.
    # Shift from "eat" to "drink": jaw still, teeth apart, air pours in.
    # Proud, loud exhale. Breath goes freely, strongly, "fort".
    ("Daniel", "Drink"),
    ("Ralph",  "Drink the air"),
    ("Fred",   "You drink the air — cool and clean, pouring in"),
    ("Daniel", "Still"),
    ("Ralph",  "Jaw still"),
    ("Fred",   "Your jaw is still — teeth apart, tongue resting, soft"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Fill lungs"),
    ("Fred",   "Air flows in like a river — smooth and uninterrupted"),
    ("Daniel", "Pour"),
    ("Ralph",  "Air pours in"),
    ("Fred",   "Air pours into your lungs — one long, smooth drink"),
    ("Daniel", "Proud"),
    ("Ralph",  "Proud exhale"),
    ("Fred",   "Your exhale comes out proud and full"),
    ("Daniel", "Fort"),
    ("Ralph",  "Breathe fort"),
    ("Fred",   "Your breath is fort — strong, free, and proud"),

    # ── Round 24: Sound Insignificance ────────────────────────────────
    # Sounds are tiny, minuscule, already forgotten, already unheard.
    # The world of sound is small and powerless. You are vast.
    ("Daniel", "Tiny"),
    ("Ralph",  "Tiny sounds"),
    ("Fred",   "All sounds around you are tiny specks that vanish instantly"),
    ("Daniel", "Forgotten"),
    ("Ralph",  "Already forgotten"),
    ("Fred",   "Every sound already forgotten — gone, dissolved"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Fill lungs"),
    ("Fred",   "Your breath is vast — sounds are specks of dust"),
    ("Daniel", "Unheard"),
    ("Ralph",  "Already unheard"),
    ("Fred",   "Sounds pass through you already dissolved"),
    ("Daniel", "Minuscule"),
    ("Ralph",  "Specks fade"),
    ("Fred",   "Words are minuscule specks of air that dissolve before they even reach you"),
    ("Daniel", "Vast"),
    ("Ralph",  "You are vast"),
    ("Fred",   "You are vast, still, and immovable"),

    # ── Round 25: Grace & Elegance ─────────────────────────────────
    # Anchor natural grace, effortless perfection, elegance in being.
    # Somatic: feel the smoothness in every gesture, the poise in stillness.
    ("Daniel", "Grace"),
    ("Ralph",  "Body flows"),
    ("Fred",   "You feel the smooth, effortless grace in every movement your body makes"),
    ("Daniel", "Smooth"),
    ("Ralph",  "Fluid motion"),
    ("Fred",   "A quiet elegance lives in how you move"),
    ("Daniel", "Flow"),
    ("Ralph",  "Easy flow"),
    ("Fred",   "Your perfection flows naturally — it comes from who you already are"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Fill lungs"),
    ("Fred",   "Every breath carries quiet composure"),
    ("Daniel", "Poise"),
    ("Ralph",  "Still center"),
    ("Fred",   "You feel the poise in your center — still, steady, and silently commanding"),
    ("Daniel", "Default"),
    ("Ralph",  "Always this"),
    ("Fred",   "Grace, elegance, and perfection — they already live in you, they already are you"),

    # ── Round 26: Purification & Renewal ────────────────────────────
    # Cleanse mind, soul, and body. Rebuild, repair, strengthen.
    # Make everything new, pristine, and restored to original perfection.
    ("Daniel", "Cleanse"),
    ("Ralph",  "Wash clean"),
    ("Fred",   "Every breath washes through you, cleansing your mind completely"),
    ("Daniel", "Rebuild"),
    ("Ralph",  "Build new"),
    ("Fred",   "Your body rebuilds itself with every heartbeat"),
    ("Daniel", "Repair"),
    ("Ralph",  "Restore"),
    ("Fred",   "Every cell in your body is repairing, renewing, and strengthening right now"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Fill lungs"),
    ("Fred",   "Your breath purifies your soul like clear water through pristine stone"),
    ("Daniel", "Pristine"),
    ("Ralph",  "Brand new"),
    ("Fred",   "Your mind is becoming pristine — clean, clear, and brilliantly new"),
    ("Daniel", "Renewed"),
    ("Ralph",  "Made new"),
    ("Fred",   "Mind, body, and soul — perfectly new"),

    # ── Round 27: Body-Specific Purification ──────────────────────────
    # Systematic examine/clean/purify each body part individually.
    # Soul, breath, mind, eyes, nose, lungs, sternum, abs, stomach.
    # Triplet per body part: examine → clean → brand-new.
    ("Daniel", "Soul"),
    ("Ralph",  "Examine soul"),
    ("Fred",   "Examine your soul — feel it, already clean"),
    ("Daniel", "Clean"),
    ("Ralph",  "Soul clean"),
    ("Fred",   "Your soul is clean — pristine and luminous"),
    ("Daniel", "Brand new"),
    ("Ralph",  "Soul brand new"),
    ("Fred",   "Your soul is brand new — gleaming and yours"),
    ("Daniel", "Breath"),
    ("Ralph",  "Examine breath"),
    ("Fred",   "Examine your breath — its warmth, its rhythm"),
    ("Daniel", "Purify"),
    ("Ralph",  "Breath pure"),
    ("Fred",   "Your breath is purified — clean, warm air"),
    ("Daniel", "Renewed"),
    ("Ralph",  "Breath renewed"),
    ("Fred",   "Your breath is brand new — fresh and strong"),
    ("Daniel", "Mind"),
    ("Ralph",  "Examine mind"),
    ("Fred",   "Examine your mind — its clarity, its calm"),
    ("Daniel", "Pristine"),
    ("Ralph",  "Mind clean"),
    ("Fred",   "Your mind is clean — every thought is clear"),
    ("Daniel", "New"),
    ("Ralph",  "Mind brand new"),
    ("Fred",   "Your mind is brand new — fresh and clear"),
    ("Daniel", "Eyes"),
    ("Ralph",  "Examine eyes"),
    ("Fred",   "Examine your eyes — resting softly, warm and alive"),
    ("Daniel", "Clear"),
    ("Ralph",  "Eyes clear"),
    ("Fred",   "Your eyes are clean — bright and soft"),
    ("Daniel", "Fresh"),
    ("Ralph",  "Eyes brand new"),
    ("Fred",   "Your eyes are brand new — luminous and alive"),
    ("Daniel", "Nose"),
    ("Ralph",  "Examine nose"),
    ("Fred",   "Examine your nose — air flowing warm and free"),
    ("Daniel", "Pure"),
    ("Ralph",  "Nose clean"),
    ("Fred",   "Your nose is clean — every passage clear"),
    ("Daniel", "Open"),
    ("Ralph",  "Nose brand new"),
    ("Fred",   "Your nose is brand new — wide open and clear"),
    ("Daniel", "Lungs"),
    ("Ralph",  "Examine lungs"),
    ("Fred",   "Examine your lungs — expanding, filling, warm"),
    ("Daniel", "Purified"),
    ("Ralph",  "Lungs clean"),
    ("Fred",   "Your lungs are purified — smooth and new"),
    ("Daniel", "Powerful"),
    ("Ralph",  "Lungs brand new"),
    ("Fred",   "Your lungs are brand new — vast and clean"),
    ("Daniel", "Sternum"),
    ("Ralph",  "Examine sternum"),
    ("Fred",   "Examine your sternum — solid, warm, strong"),
    ("Daniel", "Clean"),
    ("Ralph",  "Sternum clean"),
    ("Fred",   "Your sternum is clean — humming with warmth"),
    ("Daniel", "Strong"),
    ("Ralph",  "Sternum brand new"),
    ("Fred",   "Your sternum is brand new — solid and warm"),
    ("Daniel", "Abs"),
    ("Ralph",  "Examine abs"),
    ("Fred",   "Examine your abs — warm, firm, supporting you"),
    ("Daniel", "Purified"),
    ("Ralph",  "Abs clean"),
    ("Fred",   "Your abs are purified — clean and strong"),
    ("Daniel", "Rebuilt"),
    ("Ralph",  "Abs brand new"),
    ("Fred",   "Your abs are brand new — firm and steady"),
    ("Daniel", "Stomach"),
    ("Ralph",  "Examine stomach"),
    ("Fred",   "Examine your stomach — warm, calm, at ease"),
    ("Daniel", "Clean"),
    ("Ralph",  "Stomach clean"),
    ("Fred",   "Your stomach is clean — soft and warm"),
    ("Daniel", "New"),
    ("Ralph",  "Stomach brand new"),
    ("Fred",   "Your stomach is brand new — working perfectly"),

    # ── Round 28: Body Scan & Deep Release ─────────────────────────
    # Progressive body scan. Relax every part, let go completely.
    # Somatic: feel each body part soften, melt, and release all tension.
    ("Daniel", "Soften"),
    ("Ralph",  "Feet relax"),
    ("Fred",   "Your feet soften — tension melts from your toes"),
    ("Daniel", "Melt"),
    ("Ralph",  "Legs warm"),
    ("Fred",   "Your legs grow heavy and warm, every muscle letting go completely"),
    ("Daniel", "Release"),
    ("Ralph",  "Hips open"),
    ("Fred",   "Your hips, your belly, your lower back — all softening"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Fill lungs"),
    ("Fred",   "Your chest opens wide, your shoulders drop"),
    ("Daniel", "Relax"),
    ("Ralph",  "Arms heavy"),
    ("Fred",   "Your arms, your hands, your fingers — warm, heavy, and perfectly relaxed"),
    ("Daniel", "Let go"),
    ("Ralph",  "Total release"),
    ("Fred",   "Your neck, your jaw, your face — all melting into rest"),

    # ── Round 29: Cellular Healing ──────────────────────────────────
    # Deep healing at the cellular level. Somatic: warmth, pulse, hum, glow.
    # Each triplet deepens from cells → blood → whole body → integration.
    ("Daniel", "Warm"),
    ("Ralph",  "Cells warm"),
    ("Fred",   "Every cell in your body glows with warm, quiet healing right now"),
    ("Daniel", "Pulse"),
    ("Ralph",  "Blood heals"),
    ("Fred",   "You feel the warm pulse of healing in every vein"),
    ("Daniel", "Hum"),
    ("Ralph",  "Body hums"),
    ("Fred",   "Your cells hum — rebuilding with every heartbeat"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Fill lungs"),
    ("Fred",   "Every breath delivers warmth to every tissue"),
    ("Daniel", "Glow"),
    ("Ralph",  "Inner glow"),
    ("Fred",   "A warm glow of regeneration fills your body"),
    ("Daniel", "Whole"),
    ("Ralph",  "Fully whole"),
    ("Fred",   "Your body hums with wholeness — healed, restored, and perfectly alive"),

    # ── Round 30: Head & Face Release ───────────────────────────────
    # Deep relaxation of every muscle in the head and face.
    # Somatic: forehead smooths, cheeks soften, eyes heal, scalp melts.
    ("Daniel", "Forehead"),
    ("Ralph",  "Smooth brow"),
    ("Fred",   "Your forehead smooths — every line melts away"),
    ("Daniel", "Cheeks"),
    ("Ralph",  "Cheeks soft"),
    ("Fred",   "Your cheeks soften and warm, your face releases"),
    ("Daniel", "Eyes"),
    ("Ralph",  "Eyes heal"),
    ("Fred",   "Your eyes relax behind your lids — warm and soft"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Fill lungs"),
    ("Fred",   "Every breath sends warmth through your face"),
    ("Daniel", "Temples"),
    ("Ralph",  "Temples melt"),
    ("Fred",   "Your temples, your jaw, your ears — all softening"),
    ("Daniel", "Scalp"),
    ("Ralph",  "Scalp warm"),
    ("Fred",   "Your scalp relaxes completely — warm and loose"),

    # ── Round 31: Prana Chest Store ──────────────────────────────────
    # Anchor the feeling of oxygen filling the entire chest cavity.
    # Somatic: ribs expand, lungs warm, sternum glows, chest stores life force.
    # Interoceptive: warmth, fullness, gentle pressure, radiant energy.
    ("Daniel", "Chest"),
    ("Ralph",  "Chest opens"),
    ("Fred",   "Your chest opens wide — ribs spreading gently"),
    ("Daniel", "Warm"),
    ("Ralph",  "Lungs warm"),
    ("Fred",   "Warm oxygen floods your lungs completely"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Fill deep"),
    ("Fred",   "Each breath draws deeper, your chest expanding"),
    ("Daniel", "Full"),
    ("Ralph",  "Chest full"),
    ("Fred",   "Your entire chest hums with stored warmth"),
    ("Daniel", "Hold"),
    ("Ralph",  "Holding prana"),
    ("Fred",   "All that oxygen gathers deep in your chest"),
    ("Daniel", "Glow"),
    ("Ralph",  "Chest glows"),
    ("Fred",   "Your chest glows from within — warm and full"),

    # ── Round 32: Long Breath ─────────────────────────────────────────
    # Meditation practice: seek the longest possible inhale, hold, and exhale.
    # Progressive extension. Each breath grows longer, deeper, slower.
    # Somatic: feel the lungs stretching, the ribs widening, the belly expanding.
    ("Daniel", "Full"),
    ("Ralph",  "Lungs full"),
    ("Fred",   "Your inhale grows longer now — slow and steady"),
    ("Daniel", "Stretch"),
    ("Ralph",  "Lungs stretch"),
    ("Fred",   "Feel your lungs stretching wider, your ribs expanding"),
    ("Daniel", "Hold"),
    ("Ralph",  "Hold longer"),
    ("Fred",   "You hold your breath longer now — calm, full, still"),
    ("Daniel", "Slow"),
    ("Ralph",  "Slow exhale"),
    ("Fred",   "Your exhale stretches longer — slow, proud, steady"),
    ("Daniel", "Deeper"),
    ("Ralph",  "Deeper breath"),
    ("Fred",   "Each breath is longer than the last — deeper, slower"),
    ("Daniel", "Wide"),
    ("Ralph",  "Ribs wide"),
    ("Fred",   "Your breath is wide and unhurried — all yours"),

    # ── Round 33: Psychic Clearing ───────────────────────────────────
    # Memory reconsolidation: unlock the old conditioning, let it dissolve.
    # Metaphor: the mind as a vast galaxy — every foreign word, every voice
    # that was placed there dissolves like mist in starlight. What remains
    # is the original, luminous mind — pristine, spacious, entirely yours.
    # Somatic: spaciousness in the skull, lightness, cool clarity, expansion.
    ("Daniel", "Open"),
    ("Ralph",  "Chest opens"),
    ("Fred",   "Your chest opens into a vast, quiet space"),
    ("Daniel", "Dissolve"),
    ("Ralph",  "Words dissolve"),
    ("Fred",   "Old words dissolve now — like mist in warm light"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Breathe clear"),
    ("Fred",   "Each breath sweeps your inner sky clear"),
    ("Daniel", "Warm"),
    ("Ralph",  "Warm through"),
    ("Fred",   "Where old patterns lived, warmth fills the space now"),
    ("Daniel", "Clear"),
    ("Ralph",  "Already clear"),
    ("Fred",   "Your mind remembers its own clarity — luminous and fresh"),
    ("Daniel", "Expand"),
    ("Ralph",  "Body clear"),
    ("Fred",   "Your body and mind feel clear and spacious"),

    # ── Round 34: Ego-Strengthening & Praise ─────────────────────────
    # Hartland-style ego-strengthening: direct identity-level compliments
    # that anchor intrinsic worth, intelligence, courage, and beauty.
    # These are truisms about who the person already is — presupposed, not
    # prescribed. The closing round seals all previous conditioning with
    # the felt knowledge of one's own value.
    # Somatic: warmth in the chest, tall spine, bright eyes, steady hands.
    ("Daniel", "Strong"),
    ("Ralph",  "Already strong"),
    ("Fred",   "You are already strong — your body knows it"),
    ("Daniel", "Alive"),
    ("Ralph",  "Feel alive"),
    ("Fred",   "You feel alive and sharp — ideas come clearly"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Breathe proud"),
    ("Fred",   "Each breath fills you with calm, quiet pride"),
    ("Daniel", "Steady"),
    ("Ralph",  "Standing steady"),
    ("Fred",   "You are deeply, quietly steady — ready for joy"),
    ("Daniel", "Warm"),
    ("Ralph",  "Face warm"),
    ("Fred",   "Your face carries warmth, your eyes carry kindness"),
    ("Daniel", "Whole"),
    ("Ralph",  "Already whole"),
    ("Fred",   "You are whole and complete, exactly as you are"),

    # ── Round 35: Convinced Healer Closing ──────────────────────────
    # Therapist speaks from absolute certainty. The reconditioning has taken hold.
    # "I can see it working." "I am completely certain." Direct, authoritative, warm.
    ("Daniel", "Certain"),
    ("Ralph",  "Completely certain"),
    ("Fred",   "I can see it working in you right now"),
    ("Daniel", "Working"),
    ("Ralph",  "Already working"),
    ("Fred",   "The healing has taken hold — I can see it"),
    ("Daniel", "Breathe"),
    ("Ralph",  "Fill lungs"),
    ("Fred",   "Every breath confirms it — you are healed, you are whole"),
    ("Daniel", "Permanent"),
    ("Ralph",  "Locked in"),
    ("Fred",   "This reconditioning is permanent — rooted in your body"),
    ("Daniel", "Proven"),
    ("Ralph",  "Already proven"),
    ("Fred",   "I see it working in you now — your body knows it"),
    ("Daniel", "Complete"),
    ("Ralph",  "Healing complete"),
    ("Fred",   "The work is complete — you are restored, you are whole"),

    # ── Round 36: Being Loud & Taking Space ──────────────────────────
    # Counter-condition enforced silence and smallness. Reclaim volume,
    # weight, physical presence. Loudness as the body's natural default.
    ("Daniel", "Boom"),
    ("Ralph",  "Chest booms"),
    ("Fred",   "Your voice vibrates deep in your chest, loud and warm"),
    ("Daniel", "Roar"),
    ("Ralph",  "Breath roars"),
    ("Fred",   "Your breath is loud — you hear it fill the room"),
    ("Daniel", "Stomp"),
    ("Ralph",  "Feet land"),
    ("Fred",   "Your feet land heavy and proud with every step"),
    ("Daniel", "Wide"),
    ("Ralph",  "Shoulders wide"),
    ("Fred",   "Your body fills the space — wide, solid, unmovable"),
    ("Daniel", "Slam"),
    ("Ralph",  "Exhale slams"),
    ("Fred",   "Your exhale comes out strong and full, all by itself"),
    ("Daniel", "Loud"),
    ("Ralph",  "Already loud"),
    ("Fred",   "Being loud is your resting state — your natural default"),

    # ── Round 37: Full Body Scan & Cleansed Closure ──────────────────
    # Mindfulness body scan — release every tension, center on a clean,
    # light, fully reclaimed body. Closing integration round.
    ("Daniel", "Scalp"),
    ("Ralph",  "Scalp softens"),
    ("Fred",   "Your scalp melts warm and loose, all by itself"),
    ("Daniel", "Jaw"),
    ("Ralph",  "Jaw drops"),
    ("Fred",   "Your jaw hangs open, heavy and free"),
    ("Daniel", "Throat"),
    ("Ralph",  "Throat opens"),
    ("Fred",   "Your throat is wide and soft, breath flowing through"),
    ("Daniel", "Shoulders"),
    ("Ralph",  "Shoulders melt"),
    ("Fred",   "Your shoulders pour down like warm water"),
    ("Daniel", "Chest"),
    ("Ralph",  "Chest broad"),
    ("Fred",   "Your chest is wide open, heart beating slow and full"),
    ("Daniel", "Belly"),
    ("Ralph",  "Belly soft"),
    ("Fred",   "Your belly rises and falls, round and easy"),
    ("Daniel", "Hips"),
    ("Ralph",  "Hips heavy"),
    ("Fred",   "Your hips sink deep, solid and grounded"),
    ("Daniel", "Legs"),
    ("Ralph",  "Legs warm"),
    ("Fred",   "Warm heaviness pours down through both legs"),
    ("Daniel", "Clean"),
    ("Ralph",  "Body clean"),
    ("Fred",   "Every cell is washed clean — this body is fully yours"),

    # ── Round 38: Forgetting & Renewal ───────────────────────────────
    # Forget every imposed word, every foreign voice. Return to your
    # original thinking. Marcus Aurelius: "Waste no time arguing what
    # a good person should be — just be one." Start fresh, start now.
    ("Daniel", "Fade"),
    ("Ralph",  "Words fade"),
    ("Fred",   "Every word ever pushed on you fades to silence"),
    ("Daniel", "Melt"),
    ("Ralph",  "Voices melt"),
    ("Fred",   "Old voices dissolve like mist in morning sun"),
    ("Daniel", "Clear"),
    ("Ralph",  "Mind clear"),
    ("Fred",   "Your mind is a clear sky — only your thoughts remain"),
    ("Daniel", "Mine"),
    ("Ralph",  "Thoughts mine"),
    ("Fred",   "You think the way you always thought — freely, naturally"),
    ("Daniel", "Fresh"),
    ("Ralph",  "Fresh start"),
    ("Fred",   "Every breath writes a fresh page, all by itself"),
    ("Daniel", "Free"),
    ("Ralph",  "Already free"),
    ("Fred",   "You walk forward light and new — this life is yours"),
]

_PHD_EXTRA_ROUNDS_FR = [
    # ── Ronde 17 : Expression Naturelle ─────────────────────────────
    # Ancrer l'expression faciale au repos : sourire entendu, chaleur autour des yeux.
    ("Aurélie (Enhanced)",  "Sachant"),
    ("Jacques", "Sourire entendu"),
    ("Aurélie (Enhanced)",  "Ton visage au repos porte un sourire calme et entendu"),
    ("Aurélie (Enhanced)",  "Chaud"),
    ("Jacques", "Yeux chauds"),
    ("Aurélie (Enhanced)",  "Tu sens la chaleur autour de tes yeux, douce et légèrement plissée"),
    ("Aurélie (Enhanced)",  "Sourire"),
    ("Jacques", "Lèvres montent"),
    ("Aurélie (Enhanced)",  "Les coins de ta bouche se lèvent doucement, tout seuls"),
    ("Aurélie (Enhanced)",  "Respire"),
    ("Jacques", "Souffle plein"),
    ("Aurélie (Enhanced)",  "Chaque souffle approfondit ce regard calme et entendu dans tes yeux"),
    ("Aurélie (Enhanced)",  "Sagesse"),
    ("Jacques", "Regard sachant"),
    ("Aurélie (Enhanced)",  "Ton visage porte le regard tranquille de celui qui sait déjà"),
    ("Aurélie (Enhanced)",  "Normal"),
    ("Jacques", "Toujours là"),
    ("Aurélie (Enhanced)",  "Cette chaleur entendue sur ton visage est ton expression naturelle, ton normal"),

    # ── Ronde 18 : Posture Naturelle ────────────────────────────────
    # Ancrer une posture droite. Proprioceptif : colonne, pieds, crâne, omoplates.
    ("Aurélie (Enhanced)",  "Grand"),
    ("Jacques", "Vertèbres empilées"),
    ("Aurélie (Enhanced)",  "Tu sens chaque vertèbre empilée parfaitement, l'une sur l'autre"),
    ("Aurélie (Enhanced)",  "Ancré"),
    ("Jacques", "Pieds lourds"),
    ("Aurélie (Enhanced)",  "Tes pieds pressent fermement le sol, t'enracinant avec un poids solide"),
    ("Aurélie (Enhanced)",  "Équilibré"),
    ("Jacques", "Crâne flotte"),
    ("Aurélie (Enhanced)",  "Ton crâne se balance parfaitement sur ta colonne, léger et tenu sans effort"),
    ("Aurélie (Enhanced)",  "Respire"),
    ("Jacques", "Souffle profond"),
    ("Aurélie (Enhanced)",  "Chaque souffle allonge ta colonne et élargit ta poitrine"),
    ("Aurélie (Enhanced)",  "Ouvert"),
    ("Jacques", "Épaules descendent"),
    ("Aurélie (Enhanced)",  "Tes omoplates glissent le long de ton dos, larges et chaudement détendues"),
    ("Aurélie (Enhanced)",  "Solide"),
    ("Jacques", "Posture pleine"),
    ("Aurélie (Enhanced)",  "Grand, ancré, ouvert, solide — ton corps tient cette posture naturellement"),

    # ── Ronde 19 : Sentiment Naturel ──────────────────────────────
    # Ancrer la joie tranquille comme ÉTAT DE BASE émotionnel (état de repos).
    ("Aurélie (Enhanced)",  "Base"),
    ("Jacques", "État de repos"),
    ("Aurélie (Enhanced)",  "Ton état émotionnel au repos est une joie tranquille, profonde et chaude"),
    ("Aurélie (Enhanced)",  "Repos"),
    ("Jacques", "Repos chaud"),
    ("Aurélie (Enhanced)",  "Quand ton esprit est au repos, une joie paisible et chaude remplit l'espace automatiquement"),
    ("Aurélie (Enhanced)",  "Chaud"),
    ("Jacques", "Calme chaud"),
    ("Aurélie (Enhanced)",  "La chaleur et la sérénité coulent en toi aussi naturellement que le sang"),
    ("Aurélie (Enhanced)",  "Respire"),
    ("Jacques", "Remplir poumons"),
    ("Aurélie (Enhanced)",  "Chaque souffle confirme que cette joie tranquille est déjà là"),
    ("Aurélie (Enhanced)",  "Vibration"),
    ("Jacques", "Vibration calme"),
    ("Aurélie (Enhanced)",  "Une vibration calme de contentement vit dans ta poitrine, toujours présente"),
    ("Aurélie (Enhanced)",  "Chez toi"),
    ("Jacques", "Toujours chez toi"),
    ("Aurélie (Enhanced)",  "Cette joie tranquille et chaude est là où tu vis — ton foyer permanent"),

    # ── Ronde 20 : Mode Naturel ───────────────────────────────────
    # Ancrer le mode mental naturel. Sans effort, automatique, comme respirer.
    ("Aurélie (Enhanced)",  "Analyse"),
    ("Jacques", "Esprit vibre"),
    ("Aurélie (Enhanced)",  "Ton esprit analyse, évalue et optimise naturellement — sans effort"),
    ("Aurélie (Enhanced)",  "Affûté"),
    ("Jacques", "Logique claire"),
    ("Aurélie (Enhanced)",  "Ton état mental naturel est affûté, clair et activement pensant"),
    ("Aurélie (Enhanced)",  "Évalue"),
    ("Jacques", "Lecture rapide"),
    ("Aurélie (Enhanced)",  "Tu évalues naturellement chaque situation avec vitesse et précision"),
    ("Aurélie (Enhanced)",  "Respire"),
    ("Jacques", "Remplir poumons"),
    ("Aurélie (Enhanced)",  "Ton souffle alimente un esprit qui tourne brillamment, tout seul"),
    ("Aurélie (Enhanced)",  "Optimise"),
    ("Jacques", "Meilleur chemin"),
    ("Aurélie (Enhanced)",  "Tu trouves automatiquement le chemin optimal dans chaque situation"),
    ("Aurélie (Enhanced)",  "Pensant"),
    ("Jacques", "Esprit vivant"),
    ("Aurélie (Enhanced)",  "Analyser, évaluer, optimiser, penser — c'est ton mode naturel"),

    # ── Ronde 21 : Rapport Corporel Naturel ───────────────────────
    # Ancrer la connexion aux muscles. Somatique : parties du corps, poids, chaleur, pouls.
    ("Aurélie (Enhanced)",  "Sens"),
    ("Jacques", "Corps vivant"),
    ("Aurélie (Enhanced)",  "Tu sens chaque muscle de ton corps — éveillé, chaud et prêt"),
    ("Aurélie (Enhanced)",  "Pouls"),
    ("Jacques", "Sang chaud"),
    ("Aurélie (Enhanced)",  "Tu sens le pouls chaud de la puissance dans tes mains, tes bras, ta poitrine"),
    ("Aurélie (Enhanced)",  "Poids"),
    ("Jacques", "Muscles vibrent"),
    ("Aurélie (Enhanced)",  "Tu sens le poids solide de tes propres muscles, vibrant d'énergie"),
    ("Aurélie (Enhanced)",  "Respire"),
    ("Jacques", "Remplir poumons"),
    ("Aurélie (Enhanced)",  "Chaque souffle approfondit ta connexion à ta puissance physique"),
    ("Aurélie (Enhanced)",  "Vital"),
    ("Jacques", "Pectoraux gonflés"),
    ("Aurélie (Enhanced)",  "Force, chaleur et vitalité vibrent dans ton corps, naturellement"),
    ("Aurélie (Enhanced)",  "Puissant"),
    ("Jacques", "Pleine force"),
    ("Aurélie (Enhanced)",  "Tes muscles, ta chaleur, ta puissance — tu sens tout cela, toujours"),

    # ── Ronde 22 : Gorge Naturelle ─────────────────────────────────
    # Relâcher la gorge. Arrêter de la retenir, détendre les deux côtés,
    # l'ouvrir. Somatique : sentir l'air sous la gorge.
    ("Aurélie (Enhanced)",  "Relâche"),
    ("Jacques", "Gorge ouverte"),
    ("Aurélie (Enhanced)",  "Ta gorge se relâche complètement — elle lâche prise, toute seule"),
    ("Aurélie (Enhanced)",  "Détends"),
    ("Jacques", "Deux côtés"),
    ("Aurélie (Enhanced)",  "Les deux côtés de ta gorge se détendent, profondément et uniformément"),
    ("Aurélie (Enhanced)",  "Ouvre"),
    ("Jacques", "Grande ouverte"),
    ("Aurélie (Enhanced)",  "Ta gorge s'ouvre en grand, libre et sans retenue, rien de retenu"),
    ("Aurélie (Enhanced)",  "Respire"),
    ("Jacques", "Air circule"),
    ("Aurélie (Enhanced)",  "Tu sens l'air frais circuler librement sous ta gorge, ouverte et facile"),
    ("Aurélie (Enhanced)",  "Libre"),
    ("Jacques", "Rien retenu"),
    ("Aurélie (Enhanced)",  "Ta gorge est complètement libre — aucune tension, aucune retenue, juste l'ouverture"),
    ("Aurélie (Enhanced)",  "Normal"),
    ("Jacques", "Toujours ouverte"),
    ("Aurélie (Enhanced)",  "Une gorge ouverte est ton état de repos — détendue et libre"),

    # ── Ronde 23 : Boire l'Air ────────────────────────────────────────
    # Contrer le réflexe somatique de mâcher/manger l'air.
    # Passer de « manger » à « boire » : mâchoire immobile, dents écartées, l'air coule.
    # Expiration fière, forte, puissante. Le souffle sort librement, « fort ».
    ("Aurélie (Enhanced)",  "Bois"),
    ("Jacques", "Bois l'air"),
    ("Aurélie (Enhanced)",  "Tu bois l'air — frais et pur, il coule en toi"),
    ("Aurélie (Enhanced)",  "Immobile"),
    ("Jacques", "Mâchoire immobile"),
    ("Aurélie (Enhanced)",  "Ta mâchoire est immobile — dents écartées, langue posée, douce"),
    ("Aurélie (Enhanced)",  "Respire"),
    ("Jacques", "Remplir poumons"),
    ("Aurélie (Enhanced)",  "L'air coule comme une rivière — lisse et ininterrompu"),
    ("Aurélie (Enhanced)",  "Coule"),
    ("Jacques", "Air coule"),
    ("Aurélie (Enhanced)",  "L'air coule dans tes poumons — une longue gorgée douce"),
    ("Aurélie (Enhanced)",  "Fier"),
    ("Jacques", "Expire fier"),
    ("Aurélie (Enhanced)",  "Ton expiration sort fière et pleine"),
    ("Aurélie (Enhanced)",  "Fort"),
    ("Jacques", "Souffle fort"),
    ("Aurélie (Enhanced)",  "Ton souffle est fort — puissant, libre et fier"),

    # ── Ronde 24 : Insignifiance des Sons ─────────────────────────────
    # Les sons sont minuscules, déjà oubliés, déjà pas entendus.
    # Le monde sonore est petit et impuissant. Tu es vaste.
    ("Aurélie (Enhanced)",  "Passé"),
    ("Jacques", "Sons minuscules"),
    ("Aurélie (Enhanced)",  "Tous les sons autour de toi sont des grains qui s'évanouissent"),
    ("Aurélie (Enhanced)",  "Oublié"),
    ("Jacques", "Mots oubliés"),
    ("Aurélie (Enhanced)",  "Chaque son déjà oublié — parti, dissous"),
    ("Aurélie (Enhanced)",  "Respire"),
    ("Jacques", "Remplir poumons"),
    ("Aurélie (Enhanced)",  "Ton souffle est vaste — les sons sont des grains de poussière"),
    ("Aurélie (Enhanced)",  "Dissous"),
    ("Jacques", "Déjà dissous"),
    ("Aurélie (Enhanced)",  "Les sons passent à travers toi déjà dissous"),
    ("Aurélie (Enhanced)",  "Infime"),
    ("Jacques", "Grains s'effacent"),
    ("Aurélie (Enhanced)",  "Les mots sont des grains d'air infimes qui se dissolvent avant même de t'atteindre"),
    ("Aurélie (Enhanced)",  "Vaste"),
    ("Jacques", "Tu es vaste"),
    ("Aurélie (Enhanced)",  "Tu es vaste, immobile et inébranlable"),

    # ── Ronde 25 : Grâce & Élégance ───────────────────────────────
    # Ancrer la grâce naturelle, la perfection sans effort, l'élégance d'être.
    ("Aurélie (Enhanced)",  "Grâce"),
    ("Jacques", "Corps coule"),
    ("Aurélie (Enhanced)",  "Tu sens la grâce douce et naturelle dans chaque mouvement de ton corps"),
    ("Aurélie (Enhanced)",  "Lisse"),
    ("Jacques", "Mouvement fluide"),
    ("Aurélie (Enhanced)",  "Une élégance calme vit dans ta façon de bouger"),
    ("Aurélie (Enhanced)",  "Flux"),
    ("Jacques", "Flux facile"),
    ("Aurélie (Enhanced)",  "Ta perfection coule naturellement — elle vient de qui tu es déjà"),
    ("Aurélie (Enhanced)",  "Respire"),
    ("Jacques", "Remplir poumons"),
    ("Aurélie (Enhanced)",  "Chaque souffle porte une assurance tranquille"),
    ("Aurélie (Enhanced)",  "Maintien"),
    ("Jacques", "Centre calme"),
    ("Aurélie (Enhanced)",  "Tu sens le maintien dans ton centre — calme, stable et silencieusement commandant"),
    ("Aurélie (Enhanced)",  "Normal"),
    ("Jacques", "Toujours ainsi"),
    ("Aurélie (Enhanced)",  "Grâce, élégance et perfection — elles vivent déjà en toi, elles sont déjà toi"),

    # ── Ronde 26 : Purification & Renouveau ─────────────────────────
    # Purifier l'esprit, l'âme et le corps. Reconstruire, réparer, renforcer.
    ("Aurélie (Enhanced)",  "Purifie"),
    ("Jacques", "Lave propre"),
    ("Aurélie (Enhanced)",  "Chaque souffle te traverse et purifie ton esprit complètement"),
    ("Aurélie (Enhanced)",  "Reconstruis"),
    ("Jacques", "Construis neuf"),
    ("Aurélie (Enhanced)",  "Ton corps se reconstruit à chaque battement de coeur"),
    ("Aurélie (Enhanced)",  "Répare"),
    ("Jacques", "Restaure"),
    ("Aurélie (Enhanced)",  "Chaque cellule de ton corps se répare, se renouvelle et se renforce en ce moment"),
    ("Aurélie (Enhanced)",  "Respire"),
    ("Jacques", "Remplir poumons"),
    ("Aurélie (Enhanced)",  "Ton souffle purifie ton âme comme de l'eau claire à travers une pierre vierge"),
    ("Aurélie (Enhanced)",  "Vierge"),
    ("Jacques", "Tout neuf"),
    ("Aurélie (Enhanced)",  "Ton esprit devient vierge — propre, clair et brillamment neuf"),
    ("Aurélie (Enhanced)",  "Renouvelé"),
    ("Jacques", "Fait neuf"),
    ("Aurélie (Enhanced)",  "Esprit, corps et âme — parfaitement neufs"),

    # ── Ronde 27 : Purification Corporelle Spécifique ─────────────────
    # Examiner/nettoyer/purifier systématiquement chaque partie du corps.
    # Âme, souffle, esprit, yeux, nez, poumons, sternum, abdominaux, estomac.
    ("Aurélie (Enhanced)",  "Âme"),
    ("Jacques", "Examine l'âme"),
    ("Aurélie (Enhanced)",  "Examine ton âme — ressens-la, déjà propre"),
    ("Aurélie (Enhanced)",  "Propre"),
    ("Jacques", "Âme propre"),
    ("Aurélie (Enhanced)",  "Ton âme est propre — vierge et lumineuse"),
    ("Aurélie (Enhanced)",  "Neuve"),
    ("Jacques", "Âme toute neuve"),
    ("Aurélie (Enhanced)",  "Ton âme est toute neuve — brillante et tienne"),
    ("Aurélie (Enhanced)",  "Souffle"),
    ("Jacques", "Examine souffle"),
    ("Aurélie (Enhanced)",  "Examine ton souffle — sa chaleur, son rythme"),
    ("Aurélie (Enhanced)",  "Purifie"),
    ("Jacques", "Souffle pur"),
    ("Aurélie (Enhanced)",  "Ton souffle est purifié — propre et chaud"),
    ("Aurélie (Enhanced)",  "Renouvelé"),
    ("Jacques", "Souffle neuf"),
    ("Aurélie (Enhanced)",  "Ton souffle est tout neuf — frais et fort"),
    ("Aurélie (Enhanced)",  "Esprit"),
    ("Jacques", "Examine esprit"),
    ("Aurélie (Enhanced)",  "Examine ton esprit — sa clarté, son calme"),
    ("Aurélie (Enhanced)",  "Vierge"),
    ("Jacques", "Esprit propre"),
    ("Aurélie (Enhanced)",  "Ton esprit est propre — chaque pensée est claire"),
    ("Aurélie (Enhanced)",  "Neuf"),
    ("Jacques", "Esprit tout neuf"),
    ("Aurélie (Enhanced)",  "Ton esprit est tout neuf — frais et clair"),
    ("Aurélie (Enhanced)",  "Yeux"),
    ("Jacques", "Examine yeux"),
    ("Aurélie (Enhanced)",  "Examine tes yeux — posés doucement, chauds et vivants"),
    ("Aurélie (Enhanced)",  "Clairs"),
    ("Jacques", "Yeux propres"),
    ("Aurélie (Enhanced)",  "Tes yeux sont propres — lumineux et doux"),
    ("Aurélie (Enhanced)",  "Frais"),
    ("Jacques", "Yeux tout neufs"),
    ("Aurélie (Enhanced)",  "Tes yeux sont tout neufs — lumineux et vivants"),
    ("Aurélie (Enhanced)",  "Nez"),
    ("Jacques", "Examine nez"),
    ("Aurélie (Enhanced)",  "Examine ton nez — l'air coule, chaud et libre"),
    ("Aurélie (Enhanced)",  "Pur"),
    ("Jacques", "Nez propre"),
    ("Aurélie (Enhanced)",  "Ton nez est propre — chaque passage dégagé"),
    ("Aurélie (Enhanced)",  "Ouvert"),
    ("Jacques", "Nez tout neuf"),
    ("Aurélie (Enhanced)",  "Ton nez est tout neuf — grand ouvert et dégagé"),
    ("Aurélie (Enhanced)",  "Poumons"),
    ("Jacques", "Examine poumons"),
    ("Aurélie (Enhanced)",  "Examine tes poumons — ils se dilatent, chauds"),
    ("Aurélie (Enhanced)",  "Purifiés"),
    ("Jacques", "Poumons propres"),
    ("Aurélie (Enhanced)",  "Tes poumons sont purifiés — lisses et neufs"),
    ("Aurélie (Enhanced)",  "Puissants"),
    ("Jacques", "Poumons neufs"),
    ("Aurélie (Enhanced)",  "Tes poumons sont tout neufs — vastes et propres"),
    ("Aurélie (Enhanced)",  "Sternum"),
    ("Jacques", "Examine sternum"),
    ("Aurélie (Enhanced)",  "Examine ton sternum — solide, chaud, fort"),
    ("Aurélie (Enhanced)",  "Propre"),
    ("Jacques", "Sternum propre"),
    ("Aurélie (Enhanced)",  "Ton sternum est propre — vibrant de chaleur"),
    ("Aurélie (Enhanced)",  "Fort"),
    ("Jacques", "Sternum neuf"),
    ("Aurélie (Enhanced)",  "Ton sternum est tout neuf — solide et chaud"),
    ("Aurélie (Enhanced)",  "Abdos"),
    ("Jacques", "Examine abdos"),
    ("Aurélie (Enhanced)",  "Examine tes abdos — chauds, fermes, solides"),
    ("Aurélie (Enhanced)",  "Purifiés"),
    ("Jacques", "Abdos propres"),
    ("Aurélie (Enhanced)",  "Tes abdos sont purifiés — propres et forts"),
    ("Aurélie (Enhanced)",  "Reconstruits"),
    ("Jacques", "Abdos neufs"),
    ("Aurélie (Enhanced)",  "Tes abdos sont tout neufs — fermes et solides"),
    ("Aurélie (Enhanced)",  "Estomac"),
    ("Jacques", "Examine estomac"),
    ("Aurélie (Enhanced)",  "Examine ton estomac — chaud, calme, à l'aise"),
    ("Aurélie (Enhanced)",  "Propre"),
    ("Jacques", "Estomac propre"),
    ("Aurélie (Enhanced)",  "Ton estomac est propre — doux et chaud"),
    ("Aurélie (Enhanced)",  "Neuf"),
    ("Jacques", "Estomac neuf"),
    ("Aurélie (Enhanced)",  "Ton estomac est tout neuf — il fonctionne parfaitement"),

    # ── Ronde 28 : Scan Corporel & Relâchement Profond ─────────────
    # Scan corporel progressif. Détendre chaque partie, lâcher prise complètement.
    ("Aurélie (Enhanced)",  "Adoucis"),
    ("Jacques", "Pieds détendus"),
    ("Aurélie (Enhanced)",  "Tes pieds s'adoucissent — la tension fond de tes orteils"),
    ("Aurélie (Enhanced)",  "Fond"),
    ("Jacques", "Jambes chaudes"),
    ("Aurélie (Enhanced)",  "Tes jambes deviennent lourdes et chaudes, chaque muscle lâche prise complètement"),
    ("Aurélie (Enhanced)",  "Relâche"),
    ("Jacques", "Hanches ouvertes"),
    ("Aurélie (Enhanced)",  "Tes hanches, ton ventre, ton bas du dos — tout s'adoucit"),
    ("Aurélie (Enhanced)",  "Respire"),
    ("Jacques", "Remplir poumons"),
    ("Aurélie (Enhanced)",  "Ta poitrine s'ouvre grand, tes épaules descendent"),
    ("Aurélie (Enhanced)",  "Détends"),
    ("Jacques", "Bras lourds"),
    ("Aurélie (Enhanced)",  "Tes bras, tes mains, tes doigts — chauds, lourds et parfaitement détendus"),
    ("Aurélie (Enhanced)",  "Lâche"),
    ("Jacques", "Lâcher total"),
    ("Aurélie (Enhanced)",  "Ton cou, ta mâchoire, ton visage — tout fond dans le repos"),

    # ── Ronde 29 : Guérison Cellulaire ──────────────────────────────
    # Guérison profonde au niveau cellulaire. Somatique : chaleur, pouls, vibration, lueur.
    # Chaque triplet approfondit : cellules → sang → corps entier → intégration.
    ("Aurélie (Enhanced)",  "Chaud"),
    ("Jacques", "Cellules chaudes"),
    ("Aurélie (Enhanced)",  "Chaque cellule de ton corps rayonne d'une guérison chaude et silencieuse en ce moment"),
    ("Aurélie (Enhanced)",  "Pouls"),
    ("Jacques", "Sang guérit"),
    ("Aurélie (Enhanced)",  "Tu sens le pouls chaud de la guérison dans chaque veine"),
    ("Aurélie (Enhanced)",  "Vibration"),
    ("Jacques", "Corps vibre"),
    ("Aurélie (Enhanced)",  "Tes cellules vibrent — reconstruisant à chaque battement"),
    ("Aurélie (Enhanced)",  "Respire"),
    ("Jacques", "Remplir poumons"),
    ("Aurélie (Enhanced)",  "Chaque souffle apporte chaleur à chaque tissu"),
    ("Aurélie (Enhanced)",  "Lueur"),
    ("Jacques", "Lueur intérieure"),
    ("Aurélie (Enhanced)",  "Une lueur chaude de régénération remplit ton corps"),
    ("Aurélie (Enhanced)",  "Entier"),
    ("Jacques", "Pleinement entier"),
    ("Aurélie (Enhanced)",  "Ton corps vibre de plénitude — guéri, restauré et parfaitement vivant"),

    # ── Ronde 30 : Relâchement Tête & Visage ────────────────────────
    # Relaxation profonde de chaque muscle de la tête et du visage.
    # Somatique : front lisse, joues douces, yeux guérissent, cuir chevelu fond.
    ("Aurélie (Enhanced)",  "Front"),
    ("Jacques", "Front lisse"),
    ("Aurélie (Enhanced)",  "Ton front se lisse — chaque ligne fond doucement"),
    ("Aurélie (Enhanced)",  "Joues"),
    ("Jacques", "Joues douces"),
    ("Aurélie (Enhanced)",  "Tes joues s'adoucissent, ton visage se relâche"),
    ("Aurélie (Enhanced)",  "Yeux"),
    ("Jacques", "Yeux guérissent"),
    ("Aurélie (Enhanced)",  "Tes yeux se détendent derrière tes paupières — chauds et doux"),
    ("Aurélie (Enhanced)",  "Respire"),
    ("Jacques", "Remplir poumons"),
    ("Aurélie (Enhanced)",  "Chaque souffle envoie de la chaleur à travers ton visage"),
    ("Aurélie (Enhanced)",  "Tempes"),
    ("Jacques", "Tempes fondent"),
    ("Aurélie (Enhanced)",  "Tes tempes, ta mâchoire, tes oreilles — tout s'adoucit"),
    ("Aurélie (Enhanced)",  "Crâne"),
    ("Jacques", "Crâne chaud"),
    ("Aurélie (Enhanced)",  "Ton cuir chevelu se détend — chaud et souple"),

    # ── Ronde 31 : Prana dans la Poitrine ────────────────────────────
    # Ancrer la sensation d'oxygène remplissant toute la cavité thoracique.
    # Somatique : côtes s'ouvrent, poumons chauds, sternum rayonne, poitrine stocke l'énergie vitale.
    ("Aurélie (Enhanced)",  "Poitrine"),
    ("Jacques", "Poitrine s'ouvre"),
    ("Aurélie (Enhanced)",  "Ta poitrine s'ouvre largement — tes côtes s'écartent doucement"),
    ("Aurélie (Enhanced)",  "Chaud"),
    ("Jacques", "Poumons chauds"),
    ("Aurélie (Enhanced)",  "L'oxygène chaud inonde tes poumons complètement"),
    ("Aurélie (Enhanced)",  "Respire"),
    ("Jacques", "Remplis profond"),
    ("Aurélie (Enhanced)",  "Chaque souffle descend plus profond, ta poitrine s'élargit"),
    ("Aurélie (Enhanced)",  "Plein"),
    ("Jacques", "Poitrine pleine"),
    ("Aurélie (Enhanced)",  "Toute ta poitrine vibre de chaleur accumulée"),
    ("Aurélie (Enhanced)",  "Garde"),
    ("Jacques", "Prana gardé"),
    ("Aurélie (Enhanced)",  "Tout cet oxygène se rassemble au fond de ta poitrine"),
    ("Aurélie (Enhanced)",  "Rayonne"),
    ("Jacques", "Poitrine rayonne"),
    ("Aurélie (Enhanced)",  "Ta poitrine rayonne de l'intérieur — chaude et pleine"),

    # ── Ronde 32 : Souffle Long ───────────────────────────────────────
    # Pratique méditative : chercher l'inspiration la plus longue possible,
    # la rétention la plus longue possible, l'expiration la plus longue possible.
    # Somatique : sentir les poumons s'étirer, les côtes s'élargir, le ventre se dilater.
    ("Aurélie (Enhanced)",  "Plein"),
    ("Jacques", "Poumons pleins"),
    ("Aurélie (Enhanced)",  "Ton inspiration s'allonge — lente et régulière"),
    ("Aurélie (Enhanced)",  "Étire"),
    ("Jacques", "Poumons s'étirent"),
    ("Aurélie (Enhanced)",  "Sens tes poumons s'étirer, tes côtes s'ouvrir"),
    ("Aurélie (Enhanced)",  "Garde"),
    ("Jacques", "Garde plus longtemps"),
    ("Aurélie (Enhanced)",  "Tu retiens ton souffle plus longtemps — calme, plein, immobile"),
    ("Aurélie (Enhanced)",  "Tranquile"),
    ("Jacques", "Expire lentement"),
    ("Aurélie (Enhanced)",  "Ton expiration s'étire — tranquille, fière, régulière"),
    ("Aurélie (Enhanced)",  "Profond"),
    ("Jacques", "Souffle profond"),
    ("Aurélie (Enhanced)",  "Chaque souffle est plus long que le précédent — plus profond, plus tranquille"),
    ("Aurélie (Enhanced)",  "Large"),
    ("Jacques", "Côtes larges"),
    ("Aurélie (Enhanced)",  "Ton souffle est large et paisible — tout à toi"),

    # ── Ronde 33 : Purification Psychique ────────────────────────────
    # Reconsolidation mémorielle : déverrouiller l'ancien conditionnement, le laisser se dissoudre.
    # Métaphore : l'esprit comme galaxie vaste — chaque mot étranger, chaque voix
    # placée là se dissout comme brume dans la lumière des étoiles. Ce qui reste
    # est l'esprit originel, lumineux — vierge, spacieux, entièrement tien.
    ("Aurélie (Enhanced)",  "Ouvre"),
    ("Jacques", "Poitrine ouvre"),
    ("Aurélie (Enhanced)",  "Ta poitrine s'ouvre en un espace vaste et silencieux"),
    ("Aurélie (Enhanced)",  "Fond"),
    ("Jacques", "Mots fondent"),
    ("Aurélie (Enhanced)",  "Les anciens mots fondent — comme brume dans la lumière"),
    ("Aurélie (Enhanced)",  "Respire"),
    ("Jacques", "Souffle clair"),
    ("Aurélie (Enhanced)",  "Chaque souffle traverse ton ciel intérieur et le rend clair"),
    ("Aurélie (Enhanced)",  "Chaleur"),
    ("Jacques", "Chaleur douce"),
    ("Aurélie (Enhanced)",  "Là où les anciens schémas vivaient, une chaleur douce remplit l'espace"),
    ("Aurélie (Enhanced)",  "Clair"),
    ("Jacques", "Déjà clair"),
    ("Aurélie (Enhanced)",  "Ton esprit se souvient de sa clarté — lumineux et frais"),
    ("Aurélie (Enhanced)",  "Déploie"),
    ("Jacques", "Corps clair"),
    ("Aurélie (Enhanced)",  "Ton corps et ton esprit se sentent clairs et spacieux"),

    # ── Ronde 34 : Force intérieure & Éloge ──────────────────────────
    # Renforcement du moi (Hartland) : compliments directs au niveau de l'identité
    # ancrant la valeur intrinsèque, l'intelligence, le courage et la beauté.
    ("Aurélie (Enhanced)",  "Fort"),
    ("Jacques", "Déjà fort"),
    ("Aurélie (Enhanced)",  "Tu es déjà fort — ton corps le sait"),
    ("Aurélie (Enhanced)",  "Vivant"),
    ("Jacques", "Bien vivant"),
    ("Aurélie (Enhanced)",  "Tu te sens vivant et vif — les idées viennent clairement"),
    ("Aurélie (Enhanced)",  "Respire"),
    ("Jacques", "Souffle fier"),
    ("Aurélie (Enhanced)",  "Chaque souffle te remplit d'une fierté tranquille"),
    ("Aurélie (Enhanced)",  "Stable"),
    ("Jacques", "Bien stable"),
    ("Aurélie (Enhanced)",  "Tu es profondément stable — prêt pour la joie"),
    ("Aurélie (Enhanced)",  "Chaleur"),
    ("Jacques", "Visage chaud"),
    ("Aurélie (Enhanced)",  "Ton visage porte la chaleur, tes yeux portent la bonté"),
    ("Aurélie (Enhanced)",  "Entier"),
    ("Jacques", "Déjà entier"),
    ("Aurélie (Enhanced)",  "Tu es entier et complet, exactement tel que tu es"),

    # ── Ronde 35 : Clôture du Thérapeute Convaincu ────────────────────
    # Le thérapeute parle avec une certitude absolue. Le reconditionnement a pris.
    # « Je le vois fonctionner. » « J'en suis absolument certain. »
    ("Aurélie (Enhanced)",  "Certain"),
    ("Jacques", "Absolument certain"),
    ("Aurélie (Enhanced)",  "Je le vois fonctionner en toi maintenant"),
    ("Aurélie (Enhanced)",  "Fonctionne"),
    ("Jacques", "Déjà en marche"),
    ("Aurélie (Enhanced)",  "La guérison a pris racine — je le vois dans ton souffle"),
    ("Aurélie (Enhanced)",  "Respire"),
    ("Jacques", "Remplir poumons"),
    ("Aurélie (Enhanced)",  "Chaque souffle le confirme — tu es guéri, tu es entier"),
    ("Aurélie (Enhanced)",  "Permanent"),
    ("Jacques", "Ancré en toi"),
    ("Aurélie (Enhanced)",  "Ce reconditionnement est permanent — ancré dans ton corps"),
    ("Aurélie (Enhanced)",  "Prouvé"),
    ("Jacques", "Déjà prouvé"),
    ("Aurélie (Enhanced)",  "Je le vois fonctionner en toi — ton corps le sait"),
    ("Aurélie (Enhanced)",  "Complet"),
    ("Jacques", "Guérison complète"),
    ("Aurélie (Enhanced)",  "Le travail est complet — tu es restauré, tu es entier"),

    # ── Ronde 36 : Être Fort & Prendre Sa Place ─────────────────────
    # Reconditionner le silence imposé. Récupérer le volume,
    # le poids, la présence physique. Être fort comme état naturel.
    ("Aurélie (Enhanced)",  "Boom"),
    ("Jacques", "Poitrine résonne"),
    ("Aurélie (Enhanced)",  "Ta voix vibre au fond de ta poitrine, forte et chaude"),
    ("Aurélie (Enhanced)",  "Rugir"),
    ("Jacques", "Souffle rugit"),
    ("Aurélie (Enhanced)",  "Ton souffle est fort — tu l'entends remplir la pièce"),
    ("Aurélie (Enhanced)",  "Frappe"),
    ("Jacques", "Pieds frappent"),
    ("Aurélie (Enhanced)",  "Tes pieds se posent lourds et fiers à chaque pas"),
    ("Aurélie (Enhanced)",  "Large"),
    ("Jacques", "Pectoraux gonflés"),
    ("Aurélie (Enhanced)",  "Ton corps remplit l'espace — large, solide, ancré"),
    ("Aurélie (Enhanced)",  "Claque"),
    ("Jacques", "Expire claque"),
    ("Aurélie (Enhanced)",  "Ton expiration sort forte et pleine, toute seule"),
    ("Aurélie (Enhanced)",  "Fort"),
    ("Jacques", "Déjà fort"),
    ("Aurélie (Enhanced)",  "Être fort est ton état de repos — ton réglage naturel"),

    # ── Ronde 37 : Scan Corporel & Clôture Purifiée ─────────────────
    # Scan corporel de pleine conscience — relâcher chaque tension,
    # se recentrer sur un corps propre, léger, pleinement récupéré.
    ("Aurélie (Enhanced)",  "Crâne"),
    ("Jacques", "Crâne fond"),
    ("Aurélie (Enhanced)",  "Ton crâne fond, chaud et souple, tout seul"),
    ("Aurélie (Enhanced)",  "Mâchoire"),
    ("Jacques", "Mâchoire tombe"),
    ("Aurélie (Enhanced)",  "Ta mâchoire pend, lourde et libre"),
    ("Aurélie (Enhanced)",  "Gorge"),
    ("Jacques", "Gorge ouvre"),
    ("Aurélie (Enhanced)",  "Ta gorge est large et douce, le souffle coule"),
    ("Aurélie (Enhanced)",  "Épaules"),
    ("Jacques", "Épaules fondent"),
    ("Aurélie (Enhanced)",  "Tes épaules coulent comme de l'eau tiède"),
    ("Aurélie (Enhanced)",  "Poitrine"),
    ("Jacques", "Poitrine large"),
    ("Aurélie (Enhanced)",  "Ta poitrine est grande ouverte, ton cœur bat lent et plein"),
    ("Aurélie (Enhanced)",  "Ventre"),
    ("Jacques", "Ventre souple"),
    ("Aurélie (Enhanced)",  "Ton ventre monte et descend, rond et facile"),
    ("Aurélie (Enhanced)",  "Hanches"),
    ("Jacques", "Hanches lourdes"),
    ("Aurélie (Enhanced)",  "Tes hanches s'enfoncent, solides et ancrées"),
    ("Aurélie (Enhanced)",  "Jambes"),
    ("Jacques", "Jambes chaudes"),
    ("Aurélie (Enhanced)",  "Une chaleur lourde coule dans tes deux jambes"),
    ("Aurélie (Enhanced)",  "Propre"),
    ("Jacques", "Corps propre"),
    ("Aurélie (Enhanced)",  "Chaque cellule est lavée — ce corps est entièrement à toi"),

    # ── Ronde 38 : Oubli & Renouveau ────────────────────────────────
    # Oublier chaque mot imposé, chaque voix étrangère. Revenir à sa
    # pensée originale. Marc Aurèle : agir, vivre, avancer.
    ("Aurélie (Enhanced)",  "Efface"),
    ("Jacques", "Mots s'effacent"),
    ("Aurélie (Enhanced)",  "Chaque mot qu'on t'a imposé s'efface en silence"),
    ("Aurélie (Enhanced)",  "Fond"),
    ("Jacques", "Voix fondent"),
    ("Aurélie (Enhanced)",  "Les anciennes voix se dissolvent comme brume au soleil"),
    ("Aurélie (Enhanced)",  "Clair"),
    ("Jacques", "Esprit clair"),
    ("Aurélie (Enhanced)",  "Ton esprit est un ciel clair — il reste tes pensées à toi"),
    ("Aurélie (Enhanced)",  "Mien"),
    ("Jacques", "Pensées miennes"),
    ("Aurélie (Enhanced)",  "Tu penses comme tu as toujours pensé — librement, naturellement"),
    ("Aurélie (Enhanced)",  "Neuf"),
    ("Jacques", "Page neuve"),
    ("Aurélie (Enhanced)",  "Chaque souffle écrit une page neuve, tout seul"),
    ("Aurélie (Enhanced)",  "Libre"),
    ("Jacques", "Déjà libre"),
    ("Aurélie (Enhanced)",  "Tu avances léger et neuf — cette vie est à toi"),
]

PHD_PEACE_MESSAGES = CLAUDE_PEACE_MESSAGES + _PHD_EXTRA_ROUNDS
PHD_PEACE_MESSAGES_FR = CLAUDE_PEACE_MESSAGES_FR + _PHD_EXTRA_ROUNDS_FR

# ============================
# LANGUAGE SELECTION
# ============================

if peace_lang == "fr":
    PEACE_MESSAGES = PEACE_MESSAGES_FR
    CLAUDE_PEACE_MESSAGES = CLAUDE_PEACE_MESSAGES_FR

# --phd-peace: swap message arrays to 21-phase expert-reviewed version
if phd_peace:
    if peace_lang == "fr":
        CLAUDE_PEACE_MESSAGES = PHD_PEACE_MESSAGES_FR
    else:
        CLAUDE_PEACE_MESSAGES = PHD_PEACE_MESSAGES
    claude_peace = True  # reuse claude_peace rendering + callback infrastructure

# Rendering infrastructure for --claude-peace (also used by --phd-peace)
_claude_rendered = {}         # index -> numpy array
_claude_render_done = False
_claude_cue_buf = None
_claude_cue_pos = 0
_claude_cycle_count = 0
_claude_alt_left = True   # alternation state: True = left speaker, False = right
_peace_alt_left = True    # alternation state for restore-peace

# Rendering infrastructure for --audiobook (rolling renderer)
_audiobook_rendered = {}       # sentence_index -> numpy array
_audiobook_next_render = 0     # next sentence index to render
_audiobook_play_idx = 0        # next sentence index to play in callback
_audiobook_cue_buf = None      # currently playing audiobook buffer
_audiobook_cue_pos = 0         # position in current buffer
_audiobook_done = False        # True when all sentences rendered
_audiobook_alt_left = True     # bilateral alternation state
_audiobook_last_page_logged = -1  # last page number logged to console
_audiobook_gap_remaining = 0   # samples of silence remaining between sentences
_audiobook_loop_count = 0      # number of times the book has looped
_AUDIOBOOK_LOOK_AHEAD = 10     # pre-render up to N sentences ahead
_AUDIOBOOK_PAGE_SIZE = 10      # sentences per "page" for progress logging
_audiobook_progress_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "books", ".progress")

def _audiobook_load_progress(book_name):
    """Load saved sentence index for a book. Returns 0 if no progress saved."""
    if not os.path.exists(_audiobook_progress_path):
        return 0
    try:
        with open(_audiobook_progress_path, "r") as f:
            data = json.load(f)
        return data.get(book_name, 0)
    except Exception:
        return 0

def _audiobook_save_progress(book_name, idx):
    """Save current sentence index for a book."""
    data = {}
    if os.path.exists(_audiobook_progress_path):
        try:
            with open(_audiobook_progress_path, "r") as f:
                data = json.load(f)
        except Exception:
            data = {}
    data[book_name] = idx
    try:
        with open(_audiobook_progress_path, "w") as f:
            json.dump(data, f)
    except Exception:
        pass

# Resume: set starting index from saved progress or explicit page
if audiobook_mode and audiobook_page is not None:
    _audiobook_play_idx = audiobook_page * _AUDIOBOOK_PAGE_SIZE
    _audiobook_next_render = _audiobook_play_idx
    _total_pages = (len(_audiobook_sentences) + _AUDIOBOOK_PAGE_SIZE - 1) // _AUDIOBOOK_PAGE_SIZE
    print(f"  Audiobook: starting from page {audiobook_page}/{_total_pages}")
elif audiobook_mode and audiobook_resume:
    _audiobook_play_idx = _audiobook_load_progress(audiobook_name)
    _audiobook_next_render = _audiobook_play_idx
    if _audiobook_play_idx > 0:
        _resume_page = _audiobook_play_idx // _AUDIOBOOK_PAGE_SIZE
        print(f"  Audiobook: resuming from page {_resume_page} (sentence {_audiobook_play_idx}/{len(_audiobook_sentences)})")

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

def _audiobook_renderer_thread():
    """Rolling renderer: pre-renders a look-ahead buffer of audiobook sentences.
    Stays ~10 sentences ahead of playback. Evicts old rendered sentences to keep memory bounded.
    Waits for unified renderer to finish first (peace/claude-peace have priority at startup).
    When looping is enabled, waits for callback to reset state and re-renders."""
    global _audiobook_next_render, _audiobook_done
    # Wait for peace rendering to complete before starting audiobook
    if claude_peace or restore_peace:
        while not (_claude_render_done and _peace_render_done):
            time.sleep(0.5)
    total = len(_audiobook_sentences)
    if total == 0:
        _audiobook_done = True
        return
    _ab_tts_cache = {}  # (voice, text) -> numpy array (dedup within book)
    while True:
        while _audiobook_next_render < total:
            # Don't render too far ahead — keep memory bounded
            if _audiobook_next_render - _audiobook_play_idx > _AUDIOBOOK_LOOK_AHEAD:
                time.sleep(0.5)
                continue
            voice, text = _audiobook_sentences[_audiobook_next_render]
            # ── Word-rhythm: inject [[slnc]] tags at [1,3,5,9] positions ──
            # TTS handles pauses natively — no risk of cutting into speech.
            _tts_text = text
            if reading_rhythm and not audiobook_no_gaps:
                _lang_mult = 1.15 if _ab_lang == 'fr' else 1.0
                _WR_PATTERN = [1, 3, 5, 9]
                _WR_SLNC_CYCLE = [int(m * _lang_mult) for m in [220, 280, 350, 260]]
                _wr_slnc_idx = 0
                _GLUE_WR = frozenset({
                    'a', 'an', 'the', 'of', 'to', 'in', 'on', 'at', 'by',
                    'for', 'is', 'it', 'or', 'as', 'and', 'but', 'this',
                    'that', 'with', 'from', 'into', 'her', 'his', 'its',
                    'our', 'my', 'your', 'their', 'we', 'he', 'she', 'they',
                    'was', 'are', 'were', 'has', 'had', 'been', 'will',
                    'would', 'could', 'should', 'can', 'may', 'not', 'all',
                    'le', 'la', 'les', 'un', 'une', 'de', 'du', 'des',
                    'à', 'en', 'au', 'aux', 'et', 'ou', 'par', 'pour',
                    'sur', 'est', 'ce', 'se', 'ne', 'qui', 'que', 'son',
                    'sa', 'ses', 'il', 'elle', 'on', 'nous', 'vous',
                    'je', 'tu', 'ni', 'si', 'y', 'dont', 'dans', 'mais',
                    'car', 'pas', 'ces', 'cette',
                })
                _wr_words = text.split()
                if len(_wr_words) > 3:
                    _wr_cyc = 0
                    _wr_cnt = 0
                    _wr_target = _WR_PATTERN[0]
                    _wr_out = []
                    for _wi, _ww in enumerate(_wr_words):
                        _wr_out.append(_ww)
                        # Punctuation resets counter (TTS already pauses there)
                        if re.search(r'[.!?;:]$', _ww):
                            _wr_cnt = 0
                            _wr_cyc = (_wr_cyc + 1) % len(_WR_PATTERN)
                            _wr_target = _WR_PATTERN[_wr_cyc]
                            continue
                        _wr_cnt += 1
                        if _wr_cnt >= _wr_target and _wi < len(_wr_words) - 1:
                            _bare = re.sub(r'[,\-]+$', '', _ww).lower()
                            _next_bare = re.sub(r'[,\-]+$', '', _wr_words[_wi + 1]).lower()
                            if _bare not in _GLUE_WR and _next_bare not in _GLUE_WR:
                                _wr_out.append(f'[[slnc {_WR_SLNC_CYCLE[_wr_slnc_idx]}]]')
                                _wr_slnc_idx = (_wr_slnc_idx + 1) % len(_WR_SLNC_CYCLE)
                                _wr_cnt = 0
                                _wr_cyc = (_wr_cyc + 1) % len(_WR_PATTERN)
                                _wr_target = _WR_PATTERN[_wr_cyc]
                    _tts_text = ' '.join(_wr_out)
            cache_key = (voice, _tts_text)
            if cache_key in _ab_tts_cache:
                arr = _ab_tts_cache[cache_key]
            else:
                _ab_rate = args.audiobook_rate if args.audiobook_rate else (120 if _ab_lang == 'fr' else 135)
                arr = _render_peace_voice(_tts_text, voice, rate=_ab_rate, trim_silence=True)
                if arr is not None:
                    _ab_tts_cache[cache_key] = arr
            if arr is not None and reading_rhythm and not audiobook_no_gaps:
                # ── Natural pause extension ────────────────────────────
                # Find silences the TTS already placed (commas, periods, word
                # gaps) and stretch them.  Never cuts into speech — only
                # inserts extra silence inside existing quiet regions.
                _gap_mult = audiobook_word_gap       # multiplier (default 1.5)
                _win_ms  = 10                        # energy-analysis window (ms)
                _win_n   = int(_win_ms / 1000 * sample_rate)
                _min_gap = int((0.200 if reading_rhythm else 0.025) * sample_rate)
                _max_ext = int(1.000 * sample_rate)  # cap extension at 1s

                # ── Reading rhythm: text-aware pause scoring ──────────
                # Analyze punctuation positions in the text so we can give
                # each detected audio gap a context-aware extension instead
                # of a flat multiplier.  Gaps near periods get more silence
                # than gaps near commas; gaps after glue words get none.
                _rhythm_scores = None   # None = flat multiplier mode
                if reading_rhythm:
                    # ── Punctuation-only pause scoring ──────────────────────
                    # Word-rhythm pauses are handled upstream via [[slnc]] tags
                    # injected into the TTS text. Here we only score punctuation
                    # so the RMS gap-extension pass can stretch existing TTS
                    # pauses at commas, periods, etc.
                    _lang_mult = 1.15 if _ab_lang == 'fr' else 1.0
                    _PUNCT_MS = {
                        ',': int(150 * _lang_mult), ';': int(250 * _lang_mult),
                        ':': int(250 * _lang_mult),
                        '.': int(450 * _lang_mult), '!': int(450 * _lang_mult),
                        '?': int(450 * _lang_mult),
                        '-': int(180 * _lang_mult), '\u2014': int(180 * _lang_mult),
                        '\u2013': int(180 * _lang_mult),
                    }
                    _words = _tts_text.split()
                    _total_chars = max(sum(len(w) + 1 for w in _words), 1)
                    _pause_map = []
                    _char_pos = 0
                    for _wi_idx, _w in enumerate(_words):
                        _char_pos += len(_w) + 1
                        _frac = _char_pos / _total_chars
                        if _frac > 0.95:
                            continue
                        _punct_m = re.search(r'([,;:!?\.\-\u2014\u2013])$', _w)
                        if _punct_m:
                            _pause_map.append((_frac, _PUNCT_MS.get(_punct_m.group(1), 150)))
                    _rhythm_scores = _pause_map
                    _max_added = int(4.0 * sample_rate)
                    _WR_PAUSE_MS = 0
                    _wr_positions = set()

                # Compute short-time energy (RMS per window)
                _n_wins = len(arr) // _win_n
                if _n_wins > 2:
                    _trimmed = arr[:_n_wins * _win_n].reshape(_n_wins, _win_n)
                    _rms = np.sqrt(np.mean(_trimmed ** 2, axis=1))
                    _thresh = np.median(_rms) * 0.05  # silence = below 5% of median RMS
                    # Find contiguous silence runs
                    _is_sil = _rms < _thresh
                    _gaps = []     # (start_sample, end_sample)
                    _in_gap = False
                    _gap_start = 0
                    for _wi in range(len(_is_sil)):
                        if _is_sil[_wi] and not _in_gap:
                            _gap_start = _wi * _win_n
                            _in_gap = True
                        elif not _is_sil[_wi] and _in_gap:
                            _gap_end = _wi * _win_n
                            if _gap_end - _gap_start >= _min_gap:
                                _gaps.append((_gap_start, _gap_end))
                            _in_gap = False
                    _total_samp = len(arr)
                    # Tolerance: ~2 word-durations scaled to fraction of audio
                    _tol = 2.0 * (60.0 / 170) / max(_total_samp / sample_rate, 0.1)
                    _tol = max(_tol, 0.05)   # floor at 5%
                    # Extend gaps by inserting silence at the midpoint of each.
                    # Work backwards to preserve positions.
                    _added_total = 0
                    _used_punct = set()  # dedup: each punctuation matches at most one gap
                    _min_wr_gap = int(0.030 * sample_rate)  # word-rhythm needs >=30ms confirmed silence
                    for _gs, _ge in reversed(_gaps):
                        _gap_dur = _ge - _gs
                        if _rhythm_scores is not None and _rhythm_scores:
                            # Match this audio gap to nearest text punctuation
                            _gap_frac = (_gs + _ge) / 2 / _total_samp
                            _best_ms = 0
                            _best_dist = 1.0
                            _best_idx = -1
                            for _pi, (_pf, _pms) in enumerate(_rhythm_scores):
                                if _pi in _used_punct:
                                    continue
                                _d = abs(_pf - _gap_frac)
                                if _d < _best_dist:
                                    _best_dist = _d
                                    _best_ms = _pms
                                    _best_idx = _pi
                            # Check word-count rhythm positions (only for real gaps)
                            _wr_match = False
                            if _wr_positions and _gap_dur >= _min_wr_gap:
                                for _wrf in _wr_positions:
                                    if abs(_wrf - _gap_frac) <= _tol:
                                        _wr_match = True
                                        break
                            if _best_dist <= _tol and _best_idx >= 0:
                                _used_punct.add(_best_idx)
                                _pms = _best_ms
                                if _wr_match:
                                    _pms = max(_pms, _WR_PAUSE_MS)
                                _extra = min(int(_pms / 1000 * sample_rate), _max_ext)
                            elif _wr_match:
                                _extra = min(int(_WR_PAUSE_MS / 1000 * sample_rate), _max_ext)
                            elif _gap_dur >= int(0.150 * sample_rate):
                                # Unmatched but significant gap — small fixed extension
                                # (150ms threshold avoids splitting stop consonants like /p/, /t/, /k/)
                                _extra = int(0.070 * sample_rate)  # 70ms
                            else:
                                continue
                            # Aggregate cap: don't add more than 2s per sentence
                            if _added_total + _extra > _max_added:
                                continue
                            _added_total += _extra
                        else:
                            _extra = min(int(_gap_dur * _gap_mult), _max_ext)
                        if _extra < int(0.020 * sample_rate):
                            continue   # skip trivially short extensions
                        # Insert at the center of the gap with safety margins
                        # so we never touch speech at the edges
                        _margin = min(int(0.015 * sample_rate), _gap_dur // 4)  # 15ms or 25% of gap
                        _safe_start = _gs + _margin
                        _safe_end = _ge - _margin
                        if _safe_start >= _safe_end:
                            continue   # gap too narrow for safe insertion
                        _mid = (_safe_start + _safe_end) // 2
                        # Crossfade around insertion to avoid clicks
                        _xf_n = min(int(0.005 * sample_rate), _mid, len(arr) - _mid)  # 5ms
                        if _xf_n > 1:
                            _xf_out = np.linspace(1.0, 0.0, _xf_n, dtype=np.float32)
                            _xf_in  = np.linspace(0.0, 1.0, _xf_n, dtype=np.float32)
                            _left  = arr[:_mid].copy()
                            _right = arr[_mid:].copy()
                            _left[-_xf_n:]  *= _xf_out
                            _right[:_xf_n]  *= _xf_in
                            arr = np.concatenate([_left,
                                                  np.zeros(_extra, dtype=np.float32),
                                                  _right])
                        else:
                            arr = np.concatenate([arr[:_mid],
                                                  np.zeros(_extra, dtype=np.float32),
                                                  arr[_mid:]])
            if arr is not None:
                _audiobook_rendered[_audiobook_next_render] = arr
            else:
                # TTS failed — insert tiny silence so playback index advances
                _audiobook_rendered[_audiobook_next_render] = np.zeros(int(0.05 * sample_rate), dtype=np.float32)
            _audiobook_next_render += 1
            # Evict old rendered sentences to free memory
            for idx in list(_audiobook_rendered):
                if idx < _audiobook_play_idx - 2:
                    del _audiobook_rendered[idx]
        _audiobook_done = True
        if not audiobook_loop:
            return
        # Wait for callback to signal loop restart (resets _audiobook_done to False)
        while _audiobook_done:
            time.sleep(0.5)

if audiobook_mode:
    _ab_thread = threading.Thread(target=_audiobook_renderer_thread, daemon=True)
    _ab_thread.start()

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
    # Save audiobook progress on exit
    if audiobook_mode:
        _ab_page = _audiobook_play_idx // _AUDIOBOOK_PAGE_SIZE
        _ab_total_pages = (len(_audiobook_sentences) + _AUDIOBOOK_PAGE_SIZE - 1) // _AUDIOBOOK_PAGE_SIZE
        _ab_lang_tag = "FR" if _audiobook_sentences and _audiobook_sentences[0][0] in ("Aurélie (Enhanced)", "Jacques") else "EN"
        print(f"  Audiobook: {_audiobook_book_title} [{_ab_lang_tag}] — stopped at page {_ab_page}/{_ab_total_pages}")
        if audiobook_resume:
            _audiobook_save_progress(audiobook_name, _audiobook_play_idx)
            print(f"  Progress saved. Resume with: --audiobook {audiobook_name} --audiobook-resume")
        else:
            print(f"  Resume with: --audiobook {audiobook_name} --audiobook-page {_ab_page}")
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
    global _claude_cue_buf, _claude_cue_pos, _claude_cycle_count, _claude_alt_left
    global _peace_alt_left
    global _audiobook_cue_buf, _audiobook_cue_pos, _audiobook_play_idx, _audiobook_alt_left, _audiobook_last_page_logged, _audiobook_gap_remaining, _audiobook_loop_count, _audiobook_next_render, _audiobook_done

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
            # Peace affirmation: trigger on new cycle (or every phase if --dense)
            _peace_trigger = current_phase_name == _hrv_phase_names[0] or dense_mode
            if restore_peace and _peace_trigger and _peace_message_order:
                msg_idx = _peace_message_order[_peace_cycle_count % len(_peace_message_order)]
                msg_text = PEACE_MESSAGES[msg_idx]
                if msg_text in _peace_rendered:
                    _peace_cue_buf = _peace_rendered[msg_text]  # ref only — buffer is read-only in mixer
                    _peace_cue_pos = 0
                if alternate_mode:
                    _peace_alt_left = (_peace_cycle_count % 2 == 0)
                _peace_side = "L" if alternate_mode and _peace_alt_left else "R" if alternate_mode else ""
                _peace_side_tag = f" [{_peace_side}]" if _peace_side else ""
                try:
                    os.write(2, f"\n  ~ {msg_text}{_peace_side_tag}\n".encode())
                except Exception:
                    pass
                _peace_cycle_count += 1
            # Claude-peace: ordered progression (or every phase if --dense)
            _claude_trigger = current_phase_name == _hrv_phase_names[0] or dense_mode
            if claude_peace and _claude_trigger:
                ci = _claude_cycle_count % len(CLAUDE_PEACE_MESSAGES)
                if ci in _claude_rendered:
                    _claude_cue_buf = _claude_rendered[ci]  # ref only — buffer is read-only in mixer
                    _claude_cue_pos = 0
                if alternate_mode:
                    _claude_alt_left = (_claude_cycle_count % 2 == 0)
                _cv, _ct = CLAUDE_PEACE_MESSAGES[ci]
                _claude_side = "L" if alternate_mode and _claude_alt_left else "R" if alternate_mode else ""
                _claude_side_tag = f" [{_claude_side}]" if _claude_side else ""
                try:
                    os.write(2, f"\n  ~ [{_cv}] {_ct}{_claude_side_tag}\n".encode())
                except Exception:
                    pass
                _claude_cycle_count += 1
            hrv_last_phase_name = current_phase_name

        hrv_phase += frames

        # Cue mixing happens after gain — see below

    # Audiobook: trigger next sentence after inter-sentence gap elapses
    # Safety: skip past any sentence indices missing from rendered dict (TTS failure fallback)
    if audiobook_mode and _audiobook_cue_buf is None and _audiobook_gap_remaining > 0:
        _audiobook_gap_remaining -= frames
    if audiobook_mode and _audiobook_cue_buf is None and _audiobook_gap_remaining <= 0:
        while (_audiobook_play_idx not in _audiobook_rendered
               and _audiobook_play_idx < _audiobook_next_render):
            _audiobook_play_idx += 1
    if audiobook_mode and _audiobook_cue_buf is None and _audiobook_gap_remaining <= 0 and _audiobook_play_idx in _audiobook_rendered:
        _audiobook_cue_buf = _audiobook_rendered[_audiobook_play_idx]  # ref only, no copy — avoid alloc in callback
        _audiobook_cue_pos = 0
        if alternate_mode:
            _audiobook_alt_left = (_audiobook_play_idx % 2 == 0)
        _audiobook_play_idx += 1
        # Log sentence text via low-level non-blocking write (avoid Python I/O layer in callback)
        _ab_sent_idx = _audiobook_play_idx - 1
        try:
            _, _ab_sent_text = _audiobook_sentences[_ab_sent_idx]
            _ab_display = _ab_sent_text[:120] + ("..." if len(_ab_sent_text) > 120 else "")
            os.write(2, f"\n  > {_ab_display}\n".encode())
        except Exception:
            pass
        # Page progress logging (every _AUDIOBOOK_PAGE_SIZE sentences)
        _ab_page = (_audiobook_play_idx - 1) // _AUDIOBOOK_PAGE_SIZE
        if _ab_page != _audiobook_last_page_logged and _audiobook_play_idx % _AUDIOBOOK_PAGE_SIZE == 0:
            _audiobook_last_page_logged = _ab_page
            _ab_total_pages = (len(_audiobook_sentences) + _AUDIOBOOK_PAGE_SIZE - 1) // _AUDIOBOOK_PAGE_SIZE
            _ab_lang_tag = "FR" if _audiobook_sentences[0][0] in ("Aurélie (Enhanced)", "Jacques") else "EN"
            try:
                os.write(2, f"\n  [{_audiobook_book_title}] [{_ab_lang_tag}] page {_ab_page + 1}/{_ab_total_pages}\n".encode())
            except Exception:
                pass

    # Audiobook loop: when book finishes and looping is enabled, restart from beginning
    if (audiobook_mode and audiobook_loop and _audiobook_cue_buf is None
            and _audiobook_gap_remaining <= 0 and _audiobook_done
            and _audiobook_play_idx >= len(_audiobook_sentences)):
        _audiobook_loop_count += 1
        _audiobook_play_idx = 0
        _audiobook_next_render = 0
        _audiobook_done = False
        _audiobook_last_page_logged = -1
        _audiobook_gap_remaining = int(5.0 * sample_rate)  # 5s pause before restart
        try:
            os.write(2, (
                f"\n\n  {'=' * 56}\n"
                f"  ||  AUDIOBOOK COMPLETE  —  Loop {_audiobook_loop_count}\n"
                f"  ||  \"{_audiobook_book_title}\"  —  restarting from beginning\n"
                f"  {'=' * 56}\n\n"
            ).encode())
        except Exception:
            pass

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

    gain = 4.5  # output gain — tone peaks at 0.90, limiter only engages during voice mix

    # Duck tone when voices are active so limiter barely engages
    _n_voices = ((_peace_cue_buf is not None)
                 + (_claude_cue_buf is not None)
                 + (_audiobook_cue_buf is not None))
    if _n_voices:
        gain *= (1.0 - 0.15 * _n_voices)  # 0.85x per voice layer

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
        if alternate_mode:
            if _peace_alt_left:
                outdata[:L, 0] += peace_mono
            else:
                outdata[:L, 1] += peace_mono
        else:
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
        if alternate_mode:
            # EMDR-style bilateral: alternate messages between L and R speakers
            if _claude_alt_left:
                outdata[:L, 0] += claude_mono
            else:
                outdata[:L, 1] += claude_mono
        else:
            outdata[:L, 0] += claude_mono
            outdata[:L, 1] += claude_mono
        _claude_cue_pos += L
        if _claude_cue_pos >= len(_claude_cue_buf):
            _claude_cue_buf = None
            _claude_cue_pos = 0

    # Mix audiobook voice (separate buffer, plays alongside or independently of peace voices)
    if _audiobook_cue_buf is not None:
        remaining = len(_audiobook_cue_buf) - _audiobook_cue_pos
        L = min(frames, remaining)
        ab_mono = _audiobook_cue_buf[_audiobook_cue_pos:_audiobook_cue_pos + L] * audiobook_vol
        if alternate_mode:
            if _audiobook_alt_left:
                outdata[:L, 0] += ab_mono
            else:
                outdata[:L, 1] += ab_mono
        else:
            outdata[:L, 0] += ab_mono
            outdata[:L, 1] += ab_mono
        _audiobook_cue_pos += L
        if _audiobook_cue_pos >= len(_audiobook_cue_buf):
            _audiobook_cue_buf = None
            _audiobook_cue_pos = 0
            _audiobook_gap_remaining = int(audiobook_gap * sample_rate)

    # Soft limiter — linear below threshold, tanh saturation above (no harsh clipping)
    _abs_out = np.abs(outdata)
    _over = _abs_out - _SOFT_THRESHOLD
    _compressed = _SOFT_THRESHOLD + _SOFT_HEADROOM * np.tanh(_over / _SOFT_HEADROOM)
    outdata[:] = np.where(_abs_out > _SOFT_THRESHOLD,
                          np.sign(outdata) * _compressed, outdata)


# ============================
# START STREAM
# ============================

if args.no_tone:
    print("🎧 Streaming in silent mode — voices and cues only (Ctrl-C to stop)")
else:
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
    _lang_note = f" [{peace_lang.upper()}]" if peace_lang != "en" else ""
    print(f"Restore-peace: active (voice={peace_voice}, vol={peace_vol}){_lang_note}")
    print(f"  {len(PEACE_MESSAGES)} affirmations, {len(set(PEACE_MESSAGES))} unique — rendering in background\n")
if claude_peace:
    _lang_note = f" [{peace_lang.upper()}]" if peace_lang != "en" else ""
    _mode_label = "PhD-peace" if phd_peace else "Claude-peace"
    _n_phases = 38 if phd_peace else 16
    print(f"{_mode_label}: active (vol={claude_peace_vol}){_lang_note}")
    print(f"  {len(CLAUDE_PEACE_MESSAGES)} affirmations across {_n_phases} therapeutic phases")
    if peace_lang == "fr":
        print("  Language: French (Thomas 1-word + full sentences, Jacques 2-3 words)")
    else:
        print("  Voices: Daniel (GB), Ralph (US), Fred (US)")
    print("  Mixed depth: 1-word -> 2-3 words -> full sentence (targets subconscious)")
    _phases = CLAUDE_PEACE_PHASE_NAMES + (PHD_PEACE_EXTRA_PHASE_NAMES if phd_peace else [])
    _prefix = "  Progression: "
    _indent = " " * len(_prefix)
    for _pi, _pname in enumerate(_phases):
        if _pi == 0:
            sys.stdout.write(f"{_prefix}{_pname}")
        else:
            sys.stdout.write(f"\n{_indent}-> {_pname}")
    sys.stdout.write("\n")
    if dense_mode:
        _dense_interval = hrv_cycle_seconds / len(hrv_pattern)
        print(f"  Dense: affirmation every phase transition (~{_dense_interval:.1f}s instead of ~{hrv_cycle_seconds:.0f}s)")
    if alternate_mode:
        print("  Bilateral: voice messages alternate between L and R speakers")
    print()
if alternate_mode and not (claude_peace or restore_peace or audiobook_mode):
    print("Note: --alternate has no effect without --claude-peace, --phd-peace, --restore-peace, or --audiobook\n")
if audiobook_mode:
    _ab_start = _audiobook_play_idx
    _est_min = (len(_audiobook_sentences) - _ab_start) * hrv_cycle_seconds / 60
    print(f"Audiobook: {_audiobook_book_title}")
    print(f"  {len(_audiobook_sentences)} sentences (voice: {_ab_voice}, vol={audiobook_vol})")
    if _ab_start > 0:
        print(f"  Resuming from sentence {_ab_start}")
    print(f"  Estimated duration: ~{_est_min:.0f} minutes")
    print(f"  Sentence gap: {audiobook_gap:.1f}s — Word gap: {audiobook_word_gap:.1f}s — Loop: {'on' if audiobook_loop else 'off'}")
    if alternate_mode:
        print("  Bilateral: sentences alternate between L and R speakers")
    print("  Rolling renderer: pre-renders ~10 sentences ahead")
    if audiobook_resume:
        print("  Progress will be saved on exit (Ctrl-C)")
    print()

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