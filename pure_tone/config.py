"""Configuration resolution, state initialization, and audiobook loading."""

import os
import re
import sys
import json
import threading
import numpy as np
from queue import Queue

from .constants import (
    SAMPLE_RATE, CHANNELS, FADE_SECONDS, LONG_FADE_SECONDS,
    HRV_PATTERNS, AUDIOBOOK_PAGE_SIZE,
    build_hrv_tables,
)


class G:
    """Container for all runtime configuration and mutable state."""
    pass


def show_audiobook_list():
    """Display the audiobook catalog and exit."""
    from books.catalog import BOOK_CATALOG, BOOK_CATEGORIES, ARCHAIC_BOOKS
    texts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "books", "texts")
    total = len(BOOK_CATALOG)
    n_fr = sum(1 for m in BOOK_CATALOG.values() if m.get("language") == "fr")
    n_en = sum(1 for m in BOOK_CATALOG.values() if m.get("language") == "en")
    n_archaic = sum(1 for n in ARCHAIC_BOOKS if n in BOOK_CATALOG)
    print(f"\nAvailable audiobooks ({total} books — {n_fr} French, {n_en} English, {n_archaic} archaic):\n")
    for cat in BOOK_CATEGORIES:
        cat_books = [(n, m) for n, m in BOOK_CATALOG.items() if m["category"] == cat]
        if not cat_books:
            continue
        print(f"  {cat}:")
        for name, meta in cat_books:
            dl = os.path.exists(os.path.join(texts_dir, f"{name}.txt"))
            mark = "[OK]" if dl else "[--]"
            lang = meta.get("language", "fr").upper()
            if name in ARCHAIC_BOOKS:
                lang = "EN - Ancient formulations"
            print(f"    {mark} {name:<25s} {meta['title']} — {meta['author']}  [{lang}]")
        print()
    print("  [OK] = downloaded    [--] = run: python books/fetch_books.py")
    print("  [FR] = French    [EN] = English    [EN - Ancient formulations] = archaic English")
    print()
    sys.exit(0)


def init(args):
    """Initialize all configuration and mutable state from parsed args. Returns G instance."""
    g = G()

    # Store raw args for later checks
    g.args = args

    # ── Config from args ──
    g.frequency = args.freq
    g.save_audio = args.save_audio
    g.iso_mode = args.iso
    g.pulse_freq = args.pulse
    g.abs_mode = args.abs
    g.abs_speed = args.abs_speed
    g.hrv_mode = args.hrv
    g.hrv_style = args.hrv_style
    g.fade_long = args.fade_long
    g.full_mode = args.full
    g.integrity_mode = args.integrity
    g.integrity_interval = args.integrity_interval
    g.disable_inputs = args.disable_inputs
    g.pure_mode = args.pure
    g.lockdown_mode = args.lockdown
    g.latency_mode = args.latency
    g.blocksize = args.blocksize
    g.breath_bar = args.breath_bar
    g.breath_cue = args.breath_cue
    g.breath_cue_vol = args.breath_cue_vol
    g.restore_peace = args.restore_peace
    g.peace_voice = args.peace_voice
    g.peace_vol = args.peace_vol
    g.claude_peace = args.claude_peace
    g.claude_peace_vol = args.claude_peace_vol
    g.phd_peace = args.phd_peace
    g.phd_peace_vol = args.phd_peace_vol
    g.alternate_mode = args.alternate
    g.dense_mode = args.dense
    g.peace_lang = args.peace_lang
    g.audiobook_name = args.audiobook
    g.audiobook_vol = args.audiobook_vol
    g.audiobook_resume = args.audiobook_resume
    g.audiobook_page = args.audiobook_page
    g.audiobook_gap = args.audiobook_gap
    g.audiobook_word_gap = args.audiobook_word_gap
    g.reading_rhythm = args.rhythm and not args.no_rhythm
    if g.reading_rhythm and "--audiobook-word-gap" not in sys.argv:
        g.audiobook_word_gap = 2.0
    g.audiobook_loop = not args.no_audiobook_loop
    g.audiobook_no_gaps = args.no_audiobook_gaps
    g.no_tone = args.no_tone

    # Presets that silence the base tone / set low amplitude
    _preset_no_tone = args.breathwork
    _preset_low_amp = args.reading_calm

    # French language: override default peace voice if user didn't explicitly set it
    if g.peace_lang == "fr" and "--peace-voice" not in sys.argv:
        g.peace_voice = "Aurélie (Enhanced)"

    # --restore-peace auto-enables HRV
    if g.restore_peace:
        g.hrv_mode = True

    # full-mode auto enables all major features
    if g.full_mode:
        g.iso_mode = True
        g.abs_mode = True
        g.hrv_mode = True
        g.fade_long = True

    # LOCKDOWN MODE
    if g.lockdown_mode:
        g.pure_mode = True
        g.disable_inputs = True
        g.integrity_mode = True

    # PURE SAFE MODE
    if g.pure_mode:
        g.iso_mode = False
        g.abs_mode = False
        g.hrv_mode = False
        g.fade_long = False

    # --claude-peace overrides pure mode for HRV
    if g.claude_peace:
        g.hrv_mode = True
        g.breath_bar = True
        if g.pure_mode:
            print("Note: --claude-peace overrides --pure to enable HRV + breath-bar")

    # --phd-peace: extended version — activates claude_peace infrastructure
    if g.phd_peace:
        g.hrv_mode = True
        g.breath_bar = True
        g.claude_peace_vol = g.phd_peace_vol
        if g.pure_mode:
            print("Note: --phd-peace overrides --pure to enable HRV + breath-bar")

    # ── Audiobook loading ──
    g.audiobook_mode = False
    g.audiobook_sentences = []
    g.audiobook_book_title = ""
    g.ab_voice = ""
    g.ab_lang = "fr"
    g.ab_rate = 135

    if g.audiobook_name:
        from books.catalog import BOOK_CATALOG
        if g.audiobook_name not in BOOK_CATALOG:
            print(f"Error: unknown book '{g.audiobook_name}'. Use --audiobook-list to see available books.")
            sys.exit(1)
        ab_meta = BOOK_CATALOG[g.audiobook_name]
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        ab_text_path = os.path.join(base_dir, "books", "texts", f"{g.audiobook_name}.txt")
        if not os.path.exists(ab_text_path):
            print(f"Error: book file not found: {ab_text_path}")
            print("Run: python books/fetch_books.py")
            sys.exit(1)
        with open(ab_text_path, "r", encoding="utf-8") as f:
            ab_raw = f.read()
        g.ab_lang = ab_meta.get("language", "fr")
        g.ab_voice = ab_meta.get("voice", "Aurélie (Enhanced)" if g.ab_lang == "fr" else "Samantha")
        if args.audiobook_voice:
            g.ab_voice = args.audiobook_voice
            print(f"Note: audiobook voice overridden to: {g.ab_voice}")
        elif g.ab_lang == "en":
            print(f"Note: '{ab_meta['title']}' is an English audiobook — using voice: {g.ab_voice}")
        ab_raw = re.sub(r'(?<!\n)\n(?!\n)', ' ', ab_raw)
        ab_parts = re.split(r'(?<=[.!?])\s+|\n{2,}', ab_raw)
        g.audiobook_sentences = [
            (g.ab_voice, s.strip())
            for s in ab_parts
            if s.strip() and len(s.strip()) > 2
        ]
        g.audiobook_book_title = f"{ab_meta['title']} — {ab_meta['author']} [{g.ab_lang.upper()}]"
        g.audiobook_mode = True
        g.hrv_mode = True
        if g.pure_mode:
            print("Note: --audiobook overrides --pure to enable HRV")
        g.ab_rate = args.audiobook_rate if args.audiobook_rate else (120 if g.ab_lang == 'fr' else 135)

    # ABS rate
    if g.abs_speed == "slow":
        g.abs_rate = 0.5
    elif g.abs_speed == "fast":
        g.abs_rate = 3.0
    else:
        g.abs_rate = 1.5

    # ── Audio constants ──
    g.sample_rate = SAMPLE_RATE
    g.channels = CHANNELS
    g.fade_seconds = FADE_SECONDS
    g.long_fade_seconds = LONG_FADE_SECONDS
    g.amplitude = 0.0 if (g.no_tone or g.audiobook_mode or _preset_no_tone) else (0.10 if _preset_low_amp else 0.20)
    g.fade_samples = int(g.fade_seconds * g.sample_rate)

    # ── HRV tables ──
    g.hrv_pattern = HRV_PATTERNS[g.hrv_style]
    g.hrv_cycle_seconds = sum(dur for _, dur in g.hrv_pattern)
    g.hrv_rate = 1.0 / g.hrv_cycle_seconds
    (g.hrv_env_table, g.hrv_phase_id_table, g.hrv_phase_names,
     g.hrv_phase_starts, g.hrv_phase_lengths, g.hrv_cycle_samples) = build_hrv_tables(g.hrv_pattern, g.sample_rate)

    # ── Messages (import here to avoid circular deps) ──
    from . import messages
    g.PEACE_MESSAGES = messages.PEACE_MESSAGES
    g.CLAUDE_PEACE_MESSAGES = messages.CLAUDE_PEACE_MESSAGES

    if g.peace_lang == "fr":
        g.PEACE_MESSAGES = messages.PEACE_MESSAGES_FR
        g.CLAUDE_PEACE_MESSAGES = messages.CLAUDE_PEACE_MESSAGES_FR

    if g.phd_peace:
        if g.peace_lang == "fr":
            g.CLAUDE_PEACE_MESSAGES = messages.PHD_PEACE_MESSAGES_FR
        else:
            g.CLAUDE_PEACE_MESSAGES = messages.PHD_PEACE_MESSAGES
        g.claude_peace = True

    # ── Mutable state ──
    g.phase = 0.0
    g.current_sample = 0
    g.hrv_phase = 0
    g.hrv_last_phase_name = None

    # Cue state
    g.cue_buf = None
    g.cue_pos = 0

    # Peace state
    g.peace_rendered = {}
    g.peace_render_done = False
    g.peace_cue_buf = None
    g.peace_cue_pos = 0
    g.peace_cycle_count = 0
    g.peace_rng = np.random.RandomState(1337)
    g.peace_message_order = []
    g.peace_alt_left = True

    if g.restore_peace:
        g.peace_message_order = list(range(len(g.PEACE_MESSAGES)))
        g.peace_rng.shuffle(g.peace_message_order)

    # Claude state
    g.claude_rendered = {}
    g.claude_render_done = False
    g.claude_cue_buf = None
    g.claude_cue_pos = 0
    g.claude_cycle_count = 0
    g.claude_alt_left = True

    # Audiobook state
    g.audiobook_rendered = {}
    g.audiobook_next_render = 0
    g.audiobook_play_idx = 0
    g.audiobook_cue_buf = None
    g.audiobook_cue_pos = 0
    g.audiobook_done = False
    g.audiobook_alt_left = True
    g.audiobook_last_page_logged = -1
    g.audiobook_gap_remaining = 0
    g.audiobook_loop_count = 0
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    g.audiobook_progress_path = os.path.join(base_dir, "books", ".progress")

    # Resume audiobook
    if g.audiobook_mode and g.audiobook_page is not None:
        g.audiobook_play_idx = g.audiobook_page * AUDIOBOOK_PAGE_SIZE
        g.audiobook_next_render = g.audiobook_play_idx
        total_pages = (len(g.audiobook_sentences) + AUDIOBOOK_PAGE_SIZE - 1) // AUDIOBOOK_PAGE_SIZE
        print(f"  Audiobook: starting from page {g.audiobook_page}/{total_pages}")
    elif g.audiobook_mode and g.audiobook_resume:
        g.audiobook_play_idx = audiobook_load_progress(g.audiobook_progress_path, g.audiobook_name)
        g.audiobook_next_render = g.audiobook_play_idx
        if g.audiobook_play_idx > 0:
            resume_page = g.audiobook_play_idx // AUDIOBOOK_PAGE_SIZE
            print(f"  Audiobook: resuming from page {resume_page} (sentence {g.audiobook_play_idx}/{len(g.audiobook_sentences)})")

    # Integrity
    g.integrity_queue = Queue(maxsize=8)
    g.integrity_last_emit = 0.0

    # Breathing bar
    g.breath_bar_start_time = None
    g.breath_bar_cycle_count = 0
    g.breath_bar_last_phase_id = -1

    # TTS lock
    g.tts_lock = threading.Lock()

    if g.restore_peace or g.claude_peace:
        print("Pre-rendering voice affirmations (this may take a few minutes)...")
    if g.audiobook_mode:
        print(f"Audiobook rolling renderer will start {'after peace rendering' if (g.claude_peace or g.restore_peace) else 'immediately'}...")

    return g


def audiobook_load_progress(progress_path, book_name):
    """Load saved sentence index for a book. Returns 0 if no progress saved."""
    if not os.path.exists(progress_path):
        return 0
    try:
        with open(progress_path, "r") as f:
            data = json.load(f)
        return data.get(book_name, 0)
    except Exception:
        return 0


def audiobook_save_progress(progress_path, book_name, idx):
    """Save current sentence index for a book."""
    data = {}
    if os.path.exists(progress_path):
        try:
            with open(progress_path, "r") as f:
                data = json.load(f)
        except Exception:
            data = {}
    data[book_name] = idx
    try:
        with open(progress_path, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


def save_audio_file(g):
    """Render 1 hour of audio to FLAC and exit."""
    import soundfile as sf
    import datetime

    print(f"Saving 1-hour FLAC at {g.frequency} Hz...")

    duration_seconds = 3600
    total_samples = int(g.sample_rate * duration_seconds)
    t = np.linspace(0, duration_seconds, total_samples, endpoint=False)
    wave = g.amplitude * (np.sin(2 * np.pi * g.frequency * t) +
                          0.25 * np.sin(2 * np.pi * g.frequency * 2 * t) +
                          0.1 * np.sin(2 * np.pi * g.frequency * 3 * t))
    if g.iso_mode:
        pulse_wave = 0.5 * (1 + np.sin(2 * np.pi * g.pulse_freq * t))
        wave *= pulse_wave

    if g.hrv_mode:
        hrv_env = np.tile(g.hrv_env_table, total_samples // g.hrv_cycle_samples + 1)[:total_samples]
        wave *= hrv_env

    if g.fade_long:
        long_fade = 1.0 - np.clip(t / g.long_fade_seconds, 0.0, 1.0)
        wave *= long_fade

    fade_samples = int(g.fade_seconds * g.sample_rate)
    fade_in_curve = np.linspace(0.0, 1.0, fade_samples)
    fade_out_curve = np.linspace(1.0, 0.0, fade_samples)
    wave[:fade_samples] *= fade_in_curve
    wave[-fade_samples:] *= fade_out_curve

    if g.abs_mode:
        left_env = 0.5 * (1 + np.sin(2 * np.pi * g.abs_rate * t))
        right_env = 1 - left_env
        left_wave = wave * left_env
        right_wave = wave * right_env
        stereo = np.column_stack([left_wave, right_wave])
    else:
        stereo = np.column_stack([wave, wave])

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{int(g.frequency)}Hz_{timestamp}.flac"

    sf.write(filename, stereo, g.sample_rate, format="FLAC")
    print(f"Saved {filename}")
    sys.exit(0)
