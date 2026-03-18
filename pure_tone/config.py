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
    HRV_PATTERNS, AUDIOBOOK_PAGE_SIZE, RHYTHM_SEED,
    HYPNOTIC_GAP_SCHEDULE, HYPNOTIC_EXHALE_DELAY,
    ACCELERATED_GAP_SCHEDULE,
    CLAUDE_PEACE_SECTION_SIZES_FR, PHD_EXTRA_SECTION_SIZES,
    EGO_BOOST_SECTION_SIZE,
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


def show_mindfulness_list():
    """Display the mindfulness meditation catalog and exit."""
    from meditations.catalog import MEDITATION_CATALOG, MEDITATION_CATEGORIES
    texts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "meditations", "texts")
    total = len(MEDITATION_CATALOG)
    print(f"\nAvailable guided meditations ({total}):\n")
    for cat in MEDITATION_CATEGORIES:
        cat_items = [(n, m) for n, m in MEDITATION_CATALOG.items() if m["category"] == cat]
        if not cat_items:
            continue
        cat_items.sort(key=lambda x: x[1]["number"])
        print(f"  {cat}:")
        for name, meta in cat_items:
            dl = os.path.exists(os.path.join(texts_dir, f"{name}.txt"))
            mark = "[OK]" if dl else "[--]"
            lang = meta.get("language", "en").upper()
            num = meta["number"]
            author = meta.get("author", "")
            print(f"    {mark} {num:>2}. {name:<25s} {meta['title']} — {author}  [{lang}]")
        print()
    print("  Select by number:  python pure_tone.py --mindfulness 1")
    print("  Select by name:    python pure_tone.py --mindfulness body-scan")
    print("  Play all (loop):   python pure_tone.py --mindfulness-loop")
    print("  With bilateral:    python pure_tone.py --mindfulness 1 --alternate")
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
    g.ego_boost = args.ego_boost
    g.ego_boost_vol = args.ego_boost_vol
    g.full_hypnosis = args.full_hypnosis
    g.full_hypnosis_vol = args.full_hypnosis_vol
    g.alternate_mode = args.alternate
    g.dense_mode = args.dense
    g.accelerated_mode = args.accelerated
    g.peace_lang = args.peace_lang
    g.audiobook_name = args.audiobook
    g.audiobook_vol = args.audiobook_vol
    g.audiobook_resume = args.audiobook_resume
    g.audiobook_page = args.audiobook_page
    g.audiobook_gap = args.audiobook_gap
    g.audiobook_word_gap = args.audiobook_word_gap
    g.reading_rhythm = args.rhythm and not args.no_rhythm
    g.flat_read = args.flat_read
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

    # --ego-boost: dithyrambic ego-strengthening — activates claude_peace infrastructure
    if g.ego_boost:
        g.hrv_mode = True
        g.breath_bar = True
        g.claude_peace_vol = g.ego_boost_vol
        if g.pure_mode:
            print("Note: --ego-boost overrides --pure to enable HRV + breath-bar")

    # --full-hypnosis: combined PHD + ego-boost + body purification, shuffled sections
    if g.full_hypnosis:
        g.hrv_mode = True
        g.breath_bar = True
        g.claude_peace_vol = g.full_hypnosis_vol
        if g.pure_mode:
            print("Note: --full-hypnosis overrides --pure to enable HRV + breath-bar")

    # ── Audiobook loading ──
    g.audiobook_mode = False
    g.mindfulness_mode = False
    g.audiobook_sentences = []
    g.audiobook_book_title = ""
    g.ab_voice = ""
    g.ab_lang = "fr"
    g.ab_rate = 135

    # ── Mindfulness meditation loading ──
    _mindfulness_names = []
    if args.mindfulness_loop:
        if g.audiobook_name:
            print("Error: --mindfulness-loop and --audiobook are mutually exclusive.")
            sys.exit(1)
        from meditations.catalog import MEDITATION_CATALOG, MEDITATION_BY_NUMBER
        # Build ordered list of all meditations by number
        for num in sorted(MEDITATION_BY_NUMBER.keys()):
            _mindfulness_names.append(MEDITATION_BY_NUMBER[num])
    elif args.mindfulness:
        if g.audiobook_name:
            print("Error: --mindfulness and --audiobook are mutually exclusive.")
            sys.exit(1)
        from meditations.catalog import MEDITATION_CATALOG, MEDITATION_BY_NUMBER
        med_input = args.mindfulness
        # Support selection by number
        try:
            med_num = int(med_input)
            if med_num not in MEDITATION_BY_NUMBER:
                print(f"Error: meditation #{med_num} does not exist. Use --mindfulness-list to see available options.")
                sys.exit(1)
            _mindfulness_names.append(MEDITATION_BY_NUMBER[med_num])
        except ValueError:
            if med_input not in MEDITATION_CATALOG:
                print(f"Error: unknown meditation '{med_input}'. Use --mindfulness-list to see available options.")
                sys.exit(1)
            _mindfulness_names.append(med_input)

    if _mindfulness_names:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        g.audiobook_para_initial = set()
        sent_idx = 0
        titles = []
        for med_name in _mindfulness_names:
            med_meta = MEDITATION_CATALOG[med_name]
            med_text_path = os.path.join(base_dir, "meditations", "texts", f"{med_name}.txt")
            if not os.path.exists(med_text_path):
                print(f"Error: meditation file not found: {med_text_path}")
                sys.exit(1)
            with open(med_text_path, "r", encoding="utf-8") as f:
                med_raw = f.read()
            lang = med_meta.get("language", "en")
            voice = med_meta.get("voice", "Samantha" if lang == "en" else "Aurélie (Enhanced)")
            if args.mindfulness_voice:
                voice = args.mindfulness_voice
            # Set language from first meditation
            if not titles:
                g.ab_lang = lang
                g.ab_voice = voice
            med_normalized = re.sub(r'(?<!\n)\n(?!\n)', ' ', med_raw)
            paragraphs = re.split(r'\n{2,}', med_normalized)
            for para in paragraphs:
                sentences = re.split(r'(?<=[.!?])\s+', para)
                first_in_para = True
                for s in sentences:
                    s = s.strip()
                    if not s or len(s) <= 2:
                        continue
                    if first_in_para:
                        g.audiobook_para_initial.add(sent_idx)
                        first_in_para = False
                    g.audiobook_sentences.append((voice, s))
                    sent_idx += 1
            titles.append(med_meta["title"])
        if args.mindfulness_voice:
            print(f"Note: meditation voice overridden to: {args.mindfulness_voice}")
        if len(titles) == 1:
            g.audiobook_book_title = titles[0]
        else:
            g.audiobook_book_title = f"Guided Meditations ({len(titles)} sessions)"
        g.audiobook_name = _mindfulness_names[0]
        g.audiobook_mode = True
        g.mindfulness_mode = True
        g.no_tone = True  # No tone by default for mindfulness
        g.hrv_mode = True
        g.breath_bar = True
        if g.pure_mode:
            print("Note: --mindfulness overrides --pure to enable HRV")
        g.ab_rate = 135

    if g.audiobook_name and not g.mindfulness_mode:
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
        ab_raw_normalized = re.sub(r'(?<!\n)\n(?!\n)', ' ', ab_raw)
        paragraphs = re.split(r'\n{2,}', ab_raw_normalized)
        g.audiobook_para_initial = set()
        sent_idx = 0
        for para in paragraphs:
            sentences = re.split(r'(?<=[.!?])\s+', para)
            first_in_para = True
            for s in sentences:
                s = s.strip()
                if not s or len(s) <= 2:
                    continue
                if first_in_para:
                    g.audiobook_para_initial.add(sent_idx)
                    first_in_para = False
                g.audiobook_sentences.append((g.ab_voice, s))
                sent_idx += 1
        g.audiobook_book_title = f"{ab_meta['title']} — {ab_meta['author']} [{g.ab_lang.upper()}]"
        g.audiobook_mode = True
        g.hrv_mode = True
        if g.pure_mode:
            print("Note: --audiobook overrides --pure to enable HRV")
        g.ab_rate = args.audiobook_rate if args.audiobook_rate else (120 if g.ab_lang == 'fr' else 135)

    # Prosodic rhythm state
    g.rhythm_rng = np.random.RandomState(RHYTHM_SEED)
    if g.audiobook_name:
        from books.catalog import ARCHAIC_BOOKS
        g.audiobook_is_archaic = g.audiobook_name in ARCHAIC_BOOKS
    else:
        g.audiobook_is_archaic = False

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

    if g.ego_boost:
        g.CLAUDE_PEACE_MESSAGES = messages.EGO_BOOST_MESSAGES_FR
        g.peace_lang = "fr"  # ego-boost is French-only
        g.claude_peace = True

    if g.full_hypnosis:
        g.peace_lang = "fr"  # full-hypnosis is French (ego-boost is FR-only)
        # Split PHD-peace FR into sections
        phd_msgs = messages.PHD_PEACE_MESSAGES_FR
        phd_section_sizes = CLAUDE_PEACE_SECTION_SIZES_FR + PHD_EXTRA_SECTION_SIZES
        phd_sections = _split_sections(phd_msgs, phd_section_sizes)
        # Split ego-boost FR into sections (uniform size)
        ego_msgs = messages.EGO_BOOST_MESSAGES_FR
        ego_sections = [ego_msgs[i:i + EGO_BOOST_SECTION_SIZE]
                        for i in range(0, len(ego_msgs), EGO_BOOST_SECTION_SIZE)]
        # Combine all sections
        g.full_hypnosis_sections = phd_sections + ego_sections
        # Shuffle and flatten
        g.section_rng = np.random.RandomState(RHYTHM_SEED + 99)
        _shuffle_and_flatten(g)
        g.claude_peace = True
        g.phd_peace = True  # enable hypnotic rhythm

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

    # Hypnotic timing (phd-peace progressive deepening)
    g.claude_next_trigger_sample = 0
    _uses_hypnotic = g.phd_peace or g.ego_boost or g.full_hypnosis
    g.claude_exhale_delay_samples = int(HYPNOTIC_EXHALE_DELAY * g.sample_rate) if _uses_hypnotic else 0
    if g.accelerated_mode:
        g.claude_gap_schedule = ACCELERATED_GAP_SCHEDULE
        g.claude_exhale_delay_samples = int(HYPNOTIC_EXHALE_DELAY * g.sample_rate)
    elif _uses_hypnotic:
        g.claude_gap_schedule = HYPNOTIC_GAP_SCHEDULE
    else:
        g.claude_gap_schedule = []
    g.claude_gap_rng = np.random.RandomState(RHYTHM_SEED + 7)

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


def _split_sections(messages, section_sizes):
    """Split a flat message list into sections based on size list."""
    sections = []
    pos = 0
    for size in section_sizes:
        sections.append(messages[pos:pos + size])
        pos += size
    if pos < len(messages):
        sections.append(messages[pos:])
    return sections


def _shuffle_and_flatten(g):
    """Shuffle sections and flatten into g.CLAUDE_PEACE_MESSAGES."""
    order = list(range(len(g.full_hypnosis_sections)))
    g.section_rng.shuffle(order)
    flat = []
    for i in order:
        flat.extend(g.full_hypnosis_sections[i])
    g.CLAUDE_PEACE_MESSAGES = flat
    g.full_hypnosis_section_order = order


def reshuffle_full_hypnosis(g):
    """Re-shuffle sections and rebuild message list + rendered audio mapping.
    Called from callback when all messages have been played."""
    # Build audio cache by (voice, text) key from existing rendered
    audio_cache = {}
    for idx, buf in g.claude_rendered.items():
        if idx < len(g.CLAUDE_PEACE_MESSAGES):
            msg = g.CLAUDE_PEACE_MESSAGES[idx]
            audio_cache[msg] = buf
    # Reshuffle
    _shuffle_and_flatten(g)
    # Rebuild rendered dict for new order
    g.claude_rendered = {}
    for i, msg in enumerate(g.CLAUDE_PEACE_MESSAGES):
        if msg in audio_cache:
            g.claude_rendered[i] = audio_cache[msg]
    g.claude_render_done = True


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
