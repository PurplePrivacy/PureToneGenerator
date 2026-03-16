"""Named constants and lookup tables."""

import numpy as np

# Audio
SAMPLE_RATE = 44100
CHANNELS = 2
FADE_SECONDS = 1
LONG_FADE_SECONDS = 1800.0

# Output gain — tone peaks at 0.90, limiter only engages during voice mix
OUTPUT_GAIN = 4.5
# Duck tone per active voice layer
VOICE_DUCK_FACTOR = 0.15
# HRV envelope floor
ENV_FLOOR = 0.25

# Soft limiter — transparent below threshold, tanh compression above
SOFT_THRESHOLD = 0.92
SOFT_HEADROOM = 1.0 - SOFT_THRESHOLD  # 0.08

# Exhale cue pitch shift
EXHALE_PITCH_FACTOR = 0.85

# Prosodic rhythm RNG seed (deterministic across runs)
RHYTHM_SEED = 42

# HRV breathing patterns: list of (phase_name, duration_seconds)
HRV_PATTERNS = {
    "A":   [("INHALE", 5.5), ("EXHALE", 5.5)],
    "B":   [("INHALE", 4.0), ("EXHALE", 6.5)],
    "C":   [("INHALE", 6.0), ("EXHALE", 6.0)],
    "box": [("INHALE", 4.0), ("HOLD", 4.0), ("EXHALE", 4.0), ("HOLD", 4.0)],
    "478": [("INHALE", 4.0), ("HOLD", 7.0), ("EXHALE", 8.0)],
    "426": [("INHALE", 4.0), ("HOLD", 2.0), ("EXHALE", 6.0)],
}

# Voice aliases — map short names to macOS say voice identifiers
VOICE_ALIASES = {
    "Nicolas": "Nicolas (Enhanced)",
    "Aurélie (Enhanced)": "Aurélie (Enhanced)",
    "Evan (Enhanced)": "Evan (Enhanced)",
}

# Per-voice TTS rates for claude/phd-peace (WPM)
# Aurélie slowed to 115 for hypnotic delivery; Jacques stays crisp at 130 for bridge phrases
CLAUDE_PEACE_VOICE_RATES = {
    "Aurélie (Enhanced)": 115,
    "Thomas": 130,
    "Jacques": 130,
}
CLAUDE_PEACE_DEFAULT_RATE = 130

# Hypnotic gap schedule — progressive deepening (gap_cycles, jitter_max_cycles)
# Messages trigger further apart as the session deepens, per Ericksonian pacing
HYPNOTIC_GAP_SCHEDULE = [
    # Rounds 1-12: rapport building — 1 cycle, minimal jitter
    (1.0, 0.15),
    (1.0, 0.15),
    (1.0, 0.15),
    (1.0, 0.15),
    (1.0, 0.15),
    (1.0, 0.15),
    (1.0, 0.15),
    (1.0, 0.15),
    (1.0, 0.15),
    (1.0, 0.15),
    (1.0, 0.15),
    (1.0, 0.15),
    # Rounds 13-20: transition — 1.0-1.5 cycles
    (1.1, 0.25),
    (1.2, 0.25),
    (1.25, 0.30),
    (1.3, 0.30),
    (1.35, 0.35),
    (1.4, 0.35),
    (1.45, 0.40),
    (1.5, 0.40),
    # Rounds 21-34: deepening — 1.5-2.0 cycles
    (1.55, 0.40),
    (1.6, 0.40),
    (1.65, 0.45),
    (1.7, 0.45),
    (1.75, 0.45),
    (1.8, 0.45),
    (1.85, 0.50),
    (1.9, 0.50),
    (1.9, 0.50),
    (1.95, 0.50),
    (1.95, 0.50),
    (2.0, 0.50),
    (2.0, 0.50),
    (2.0, 0.50),
    # Rounds 35-43: integration/deep trance — 2.0-3.0 cycles
    (2.2, 0.50),
    (2.3, 0.50),
    (2.4, 0.50),
    (2.5, 0.50),
    (2.6, 0.50),
    (2.7, 0.50),
    (2.8, 0.50),
    (2.9, 0.50),
    (3.0, 0.50),
]

# Exhale onset delay for hypnotic delivery (seconds)
# Messages fire 0.8s into exhale phase when parasympathetic response is fully engaged
HYPNOTIC_EXHALE_DELAY = 0.8

# Audiobook
AUDIOBOOK_LOOK_AHEAD = 10
AUDIOBOOK_PAGE_SIZE = 10

# Word-rhythm injection
WR_PATTERN = [1, 3, 5, 9]
WR_SLNC_CYCLE_EN = [220, 280, 350, 260]
WR_LANG_MULT_FR = 1.15

GLUE_WORDS = frozenset({
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

# Punctuation pause durations (ms) — base values before language multiplier
PUNCT_PAUSE_BASE = {
    ',': 150, ';': 250, ':': 250,
    '.': 450, '!': 450, '?': 450,
    '-': 180, '\u2014': 180, '\u2013': 180,
}

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
    "voice & thought sovereignty (reclaim, own, original, mine)",
    "breath & body reclamation (ancient, autonomous, uncoupled)",
    "sleep clearing & snap-out (sealed, private, awake, shed)",
    "loud voice & loud exhale (boom, thunder, noise, heard)",
    "audible breath & lung apex (hear me, longest breath, top of lungs)",
    "free belly (soft, warm, rises, falls, happy, pure)",
    "solar plexus (sternum, radiance, golden light, power center)",
    "lungs purification (full, free, vast, strong, clean)",
    "mind & brain (clear, free, sharp, peaceful, luminous)",
    "nose purification (open, ample, automatic, clean, yours)",
    "heart purification (strong, free, warm, yours, pure)",
    "inner voice & thought sovereignty (loud, free, dominant, limitless, sovereign)",
]

# Section sizes for splitting flat message lists into rounds (full-hypnosis shuffling)
CLAUDE_PEACE_SECTION_SIZES = [18] * 3 + [24] + [18] * 12       # 16 rounds, 294 total (EN)
CLAUDE_PEACE_SECTION_SIZES_FR = [16] + [18] * 2 + [24] + [18] * 12  # 16 rounds, 292 total (FR)
PHD_EXTRA_SECTION_SIZES = [18] * 10 + [81] + [18] * 9 + [27] + [18] * 3 + [24] + [18] * 9  # 34 rounds (27 orig + 7 new)
EGO_BOOST_SECTION_SIZE = 6                                      # uniform: 25 × 6 = 150

# Accelerated gap schedule — tight, random intervals (gap_cycles, jitter_max_cycles)
# ~2-4s between messages with unpredictable timing
ACCELERATED_GAP_SCHEDULE = [
    (0.25, 0.25),
    (0.25, 0.25),
    (0.25, 0.25),
    (0.30, 0.25),
    (0.30, 0.25),
    (0.30, 0.30),
    (0.30, 0.30),
    (0.35, 0.30),
    (0.35, 0.30),
    (0.35, 0.30),
]

EGO_BOOST_PHASE_NAMES = [
    "physical beauty & attractiveness",
    "intelligence & mental sharpness",
    "accuracy & precision",
    "virtue & moral character",
    "strength & resilience",
    "charisma & social magnetism",
    "grace & elegance",
    "creativity & vision",
    "worth & value",
    "confidence & self-assurance",
    "warmth & kindness",
    "competence & mastery",
    "sexual attractiveness & magnetism",
    "humor & wit",
    "leadership & command",
    "authenticity & uniqueness",
    "body power & physical capability",
    "emotional depth & maturity",
    "success & achievement",
    "sovereignty & independence",
    "sensory richness & aliveness",
    "legacy & impact",
    "purity & radiance",
    "abundance & completeness",
    "transcendence & apotheosis",
]


def build_hrv_tables(hrv_pattern, sample_rate):
    """Precompute one full cycle of HRV envelope values + phase IDs.

    Returns (env_table, phase_id_table, phase_names, phase_starts, phase_lengths, cycle_samples).
    """
    cycle_seconds = sum(dur for _, dur in hrv_pattern)
    cycle_samples = int(cycle_seconds * sample_rate)
    env_table = np.zeros(cycle_samples, dtype=np.float32)
    phase_id_table = np.zeros(cycle_samples, dtype=np.int8)
    phase_names = [name for name, _ in hrv_pattern]
    phase_starts = []
    phase_lengths = []

    pos = 0
    for i, (name, dur) in enumerate(hrv_pattern):
        if i == len(hrv_pattern) - 1:
            n = cycle_samples - pos
        else:
            n = int(dur * sample_rate)
        phase_starts.append(pos)
        phase_lengths.append(n)

        progress = np.linspace(0, 1, n, endpoint=False)
        if name == "INHALE":
            env = ENV_FLOOR + (1.0 - ENV_FLOOR) * np.sin(progress * np.pi / 2)
        elif name == "EXHALE":
            env = ENV_FLOOR + (1.0 - ENV_FLOOR) * np.cos(progress * np.pi / 2)
        elif name == "HOLD":
            if i > 0 and hrv_pattern[i - 1][0] == "INHALE":
                env = np.full(n, 1.0, dtype=np.float32)
            else:
                env = np.full(n, ENV_FLOOR, dtype=np.float32)
        else:
            env = np.ones(n, dtype=np.float32)

        env_table[pos:pos + n] = env
        phase_id_table[pos:pos + n] = i
        pos += n

    return env_table, phase_id_table, phase_names, phase_starts, phase_lengths, cycle_samples
