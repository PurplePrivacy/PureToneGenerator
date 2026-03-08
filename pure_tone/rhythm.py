"""Prosodic analysis and audio gap refinement for audiobook reading rhythm.

This module replaces the legacy flat word-position rhythm with a linguistically-aware
six-pass prosodic engine. It produces a ProsodyPlan describing where pauses should go
and at what duration, then refine_audio_gaps() splices silence into the rendered NumPy
audio at those positions.

No [[slnc]] tags are injected — Enhanced/neural macOS voices produce artifacts with them
(see commit 7d5c45d). All pause insertion happens post-TTS in NumPy space.
"""

import re
import math
from dataclasses import dataclass, field

import numpy as np


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class PausePoint:
    word_index: int
    level: int
    duration_ms: int
    reason: str


@dataclass
class ProsodyPlan:
    words: list
    pause_points: list = field(default_factory=list)
    is_paragraph_initial: bool = False
    is_dialogue: bool = False
    is_short: bool = False
    sentence_length_class: str = "medium"
    total_pause_ms: int = 0


# ---------------------------------------------------------------------------
# Prosodic hierarchy — duration ranges per level (ms)
# ---------------------------------------------------------------------------

LEVEL_RANGES = {
    0: (0, 0),
    1: (80, 150),
    2: (150, 300),
    3: (300, 500),
}

# Aggregate caps by sentence length class
LENGTH_CAPS = {
    "short": 0,
    "medium": 2000,
    "long": 4000,
    "very_long": 6000,
}

# ---------------------------------------------------------------------------
# Language data
# ---------------------------------------------------------------------------

FR_CLAUSE_PAUSE_MULT = 1.20
FR_PHRASE_PAUSE_MULT = 1.10

EN_COORDINATING = frozenset({"and", "but", "or", "yet", "so", "nor"})
FR_COORDINATING = frozenset({"et", "mais", "ou", "ni", "car", "or", "donc"})

EN_SUBORDINATING = frozenset({
    "because", "although", "though", "while", "since", "unless", "when",
    "whenever", "where", "wherever", "after", "before", "until", "if",
    "whereas", "whether", "once", "as",
})
FR_SUBORDINATING = frozenset({
    "puisque", "quoique", "lorsque", "quand", "comme", "si",
})
# Multi-word French conjunctions — first word triggers, rest are part of unit
FR_MULTIWORD_CONJ_STARTS = {
    "parce": "que", "bien": "que", "afin": "de", "tandis": "que",
    "alors": "que", "avant": "que", "après": "que", "pour": "que",
    "sans": "que", "dès": "que", "depuis": "que", "pendant": "que",
}

EN_RELATIVES = frozenset({"who", "whom", "which", "that", "where", "whose"})
FR_RELATIVES = frozenset({"qui", "que", "dont", "où", "lequel", "laquelle",
                           "lesquels", "lesquelles", "duquel", "auquel"})

# Archaic English extensions
ARCHAIC_SUBORDINATING = frozenset({
    "whilst", "ere", "lest", "whence", "wherefore", "albeit", "howbeit",
})
ARCHAIC_RELATIVES = frozenset({
    "whereof", "wherein", "whereupon", "whither", "hither", "thither",
})

EN_SENTENCE_ADVERBS = frozenset({
    "however", "therefore", "indeed", "moreover", "furthermore", "nevertheless",
    "nonetheless", "meanwhile", "otherwise", "consequently", "accordingly",
    "finally", "certainly", "perhaps", "clearly", "naturally", "obviously",
})
FR_SENTENCE_ADVERBS = frozenset({
    "cependant", "néanmoins", "toutefois", "pourtant", "effectivement",
    "certes", "évidemment", "naturellement", "certainement", "finalement",
    "également", "autrement", "désormais",
})

EN_PREPOSITIONS = frozenset({
    "in", "on", "at", "by", "for", "with", "from", "into", "through",
    "during", "before", "after", "above", "below", "between", "under",
    "about", "against", "among", "around", "behind", "beneath", "beside",
    "beyond", "near", "toward", "towards", "upon", "within", "without",
    "across", "along", "outside", "inside", "over", "throughout",
})
FR_PREPOSITIONS = frozenset({
    "dans", "sur", "sous", "avec", "sans", "pour", "par", "entre",
    "vers", "chez", "devant", "derrière", "avant", "après", "pendant",
    "depuis", "contre", "parmi", "autour", "environ", "envers",
    "malgré", "selon", "durant",
})

# Function words for breath-group split heuristic
EN_FUNCTION_WORDS = frozenset({
    "a", "an", "the", "of", "to", "in", "on", "at", "by", "for",
    "is", "it", "or", "as", "and", "but", "this", "that", "with",
    "from", "into", "her", "his", "its", "our", "my", "your", "their",
    "we", "he", "she", "they", "was", "are", "were", "has", "had",
    "been", "will", "would", "could", "should", "can", "may", "not",
})
FR_FUNCTION_WORDS = frozenset({
    "le", "la", "les", "un", "une", "de", "du", "des", "à", "en",
    "au", "aux", "et", "ou", "par", "pour", "sur", "est", "ce", "se",
    "ne", "qui", "que", "son", "sa", "ses", "il", "elle", "on",
    "nous", "vous", "je", "tu", "ni", "si", "y", "dont", "dans",
    "mais", "car", "pas", "ces", "cette",
})

# French liaison: don't pause between word ending in s/t/n/z/x and vowel-initial next word
_FR_LIAISON_ENDINGS = frozenset("stnzx")
_FR_VOWEL_STARTS = re.compile(r'^[aeéèêëiïîoôuùûüyâàæœh]', re.IGNORECASE)

DIALOGUE_MARKERS = frozenset({'"', '\u201c', '\u201d', '\u00ab', '\u00bb',
                               '\u2018', '\u2019'})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bare(word):
    """Strip trailing punctuation and lowercase."""
    return re.sub(r'[,;:!?\.\-\u2014\u2013\u201c\u201d\u00ab\u00bb"\']+$', '', word).lower()


def _trailing_punct(word):
    """Return the trailing punctuation character, or empty string."""
    m = re.search(r'([,;:!?\.\-\u2014\u2013])$', word)
    return m.group(1) if m else ''


def _has_dialogue(words):
    """Check if the sentence contains dialogue markers."""
    text = ' '.join(words)
    for marker in DIALOGUE_MARKERS:
        if marker in text:
            return True
    return False


def _classify_length(n_words):
    if n_words <= 6:
        return "short"
    elif n_words <= 15:
        return "medium"
    elif n_words <= 30:
        return "long"
    else:
        return "very_long"


def _is_fr_liaison(word, next_word):
    """Check if a French liaison would occur between word and next_word."""
    bare_w = _bare(word)
    if not bare_w:
        return False
    if bare_w[-1] in _FR_LIAISON_ENDINGS and _FR_VOWEL_STARTS.match(_bare(next_word)):
        return True
    return False


def _get_lang_sets(lang, is_archaic):
    """Return the language-specific word sets."""
    if lang == 'fr':
        coord = FR_COORDINATING
        subord = FR_SUBORDINATING
        rels = FR_RELATIVES
        adverbs = FR_SENTENCE_ADVERBS
        preps = FR_PREPOSITIONS
        func = FR_FUNCTION_WORDS
    else:
        coord = EN_COORDINATING
        subord = EN_SUBORDINATING | (ARCHAIC_SUBORDINATING if is_archaic else frozenset())
        rels = EN_RELATIVES | (ARCHAIC_RELATIVES if is_archaic else frozenset())
        adverbs = EN_SENTENCE_ADVERBS
        preps = EN_PREPOSITIONS
        func = EN_FUNCTION_WORDS
    return coord, subord, rels, adverbs, preps, func


# ---------------------------------------------------------------------------
# Six-pass analysis
# ---------------------------------------------------------------------------

def _set_pause(pauses, word_index, level, duration_ms, reason):
    """Set or upgrade a pause at word_index (after that word)."""
    if word_index in pauses:
        existing = pauses[word_index]
        if level > existing.level:
            pauses[word_index] = PausePoint(word_index, level, duration_ms, reason)
        elif level == existing.level and duration_ms > existing.duration_ms:
            existing.duration_ms = duration_ms
            existing.reason = reason
    else:
        pauses[word_index] = PausePoint(word_index, level, duration_ms, reason)


def _pass1_punctuation(words, pauses):
    """Pass 1: Scan for trailing punctuation and assign pause levels."""
    for i, w in enumerate(words[:-1]):  # skip last word
        p = _trailing_punct(w)
        if p == ',':
            _set_pause(pauses, i, 2, 0, "comma")
        elif p in (';', ':'):
            _set_pause(pauses, i, 3, 0, "semicolon_colon")
        elif p in ('\u2014', '\u2013', '-'):
            # Check for parenthetical dash pair
            level = 2
            text_after = ' '.join(words[i+1:])
            if re.search(r'[\u2014\u2013\-]', text_after):
                level = 3
            _set_pause(pauses, i, level, 0, "dash")


def _pass2_clauses(words, pauses, lang, coord, subord, rels):
    """Pass 2: Detect clause boundaries via conjunctions and relatives."""
    bare_words = [_bare(w) for w in words]
    n = len(words)

    # Track multi-word French conjunctions to skip internal pauses
    skip_indices = set()
    if lang == 'fr':
        for i, bw in enumerate(bare_words):
            if bw in FR_MULTIWORD_CONJ_STARTS and i + 1 < n:
                expected = FR_MULTIWORD_CONJ_STARTS[bw]
                if bare_words[i + 1] == expected:
                    skip_indices.add(i + 1)

    for i, bw in enumerate(bare_words):
        if i in skip_indices or i == 0:
            continue

        # Coordinating conjunctions
        if bw in coord and i < n - 1:
            prev_punct = _trailing_punct(words[i - 1]) if i > 0 else ''
            if prev_punct == ',':
                _set_pause(pauses, i - 1, 2, 0, "coord_conj_after_comma")
            else:
                # Count words since last pause
                words_since = 0
                for j in range(i - 1, -1, -1):
                    if j in pauses:
                        break
                    words_since += 1
                if words_since >= 4:
                    _set_pause(pauses, i - 1, 1, 0, "coord_conj")

        # Subordinating conjunctions
        elif bw in subord and i < n - 1:
            if i > 0:
                _set_pause(pauses, i - 1, 2, 0, "subord_conj")

        # Relative pronouns
        elif bw in rels and i < n - 1:
            prev_punct = _trailing_punct(words[i - 1]) if i > 0 else ''
            if prev_punct == ',':
                _set_pause(pauses, i - 1, 2, 0, "nonrestrictive_rel")
            else:
                _set_pause(pauses, i - 1, 1, 0, "relative")


def _pass3_phrases(words, pauses, lang, adverbs, preps):
    """Pass 3: Prepositional phrases and sentence adverbs."""
    bare_words = [_bare(w) for w in words]
    n = len(words)

    # Sentence adverbs
    for i, bw in enumerate(bare_words):
        if bw in adverbs:
            if i < n - 1:
                _set_pause(pauses, i, 2, 0, "sentence_adverb")

    # Prepositional phrases of 3+ words after word 4
    for i, bw in enumerate(bare_words):
        if i < 4 or i >= n - 2:
            continue
        if bw in preps and i - 1 not in pauses:
            # Check if prep starts a phrase of 3+ words before next pause/end
            phrase_len = 1
            for j in range(i + 1, min(i + 6, n)):
                if j in pauses or _trailing_punct(words[j]) in (',', ';', ':'):
                    break
                phrase_len += 1
            if phrase_len >= 3:
                _set_pause(pauses, i - 1, 1, 0, "prep_phrase")


def _pass4_dialogue(words, pauses):
    """Pass 4: Insert pauses at dialogue boundaries."""
    for i, w in enumerate(words):
        for marker in DIALOGUE_MARKERS:
            if marker in w:
                if w.startswith(marker) and i > 0:
                    _set_pause(pauses, i - 1, 2, 0, "dialogue_open")
                if w.endswith(marker) and i < len(words) - 1:
                    _set_pause(pauses, i, 2, 0, "dialogue_close")
                break


def _pass5_breath_groups(words, pauses, lang, preps, func):
    """Pass 5: Break up long spans without pauses."""
    max_span = 12 if lang == 'fr' else 8
    n = len(words)
    bare_words = [_bare(w) for w in words]

    pause_indices = sorted(pauses.keys())
    boundaries = [-1] + pause_indices + [n - 1]

    for bi in range(len(boundaries) - 1):
        start = boundaries[bi] + 1
        end = boundaries[bi + 1]
        span = end - start
        if span < max_span:
            continue
        # Find best break point
        best = None
        best_priority = 99
        mid = (start + end) // 2

        for j in range(start + 2, end - 1):
            bw = bare_words[j]
            # Priority 1: before a preposition
            if bw in preps and best_priority > 1:
                best = j - 1
                best_priority = 1
            # Priority 2: content-word → function-word transition
            elif bw in func and bare_words[j - 1] not in func and best_priority > 2:
                best = j - 1
                best_priority = 2

        # Priority 3: geometric middle
        if best is None:
            best = mid

        if best not in pauses:
            _set_pause(pauses, best, 1, 0, "breath_group")


def _pass6_position(pauses, n_words, is_paragraph_initial):
    """Pass 6: Sentence position adjustments."""
    if not pauses:
        return
    sorted_indices = sorted(pauses.keys())

    # First pause: +20% onset lengthening
    first = pauses[sorted_indices[0]]
    first.duration_ms = int(first.duration_ms * 1.20) if first.duration_ms else first.duration_ms

    # Last pause before final 3 words: +15% pre-final lengthening
    for idx in reversed(sorted_indices):
        if idx < n_words - 3:
            pauses[idx].duration_ms = int(pauses[idx].duration_ms * 1.15) if pauses[idx].duration_ms else pauses[idx].duration_ms
            break

    # Paragraph-initial: upgrade first pause by one level
    if is_paragraph_initial and sorted_indices:
        first = pauses[sorted_indices[0]]
        if first.level < 3:
            first.level += 1
            first.reason += "+para"


# ---------------------------------------------------------------------------
# Duration assignment
# ---------------------------------------------------------------------------

def _assign_durations(pauses, rng, lang, sentence_index):
    """Assign concrete ms durations within each level's range, with variety."""
    # Slow sine modulation (~5-sentence breathing cycle)
    cycle_mod = 0.10 * math.sin(2 * math.pi * sentence_index / 5.0)

    lang_mult = 1.0
    if lang == 'fr':
        lang_mult = FR_PHRASE_PAUSE_MULT

    for pp in pauses.values():
        lo, hi = LEVEL_RANGES[pp.level]
        if lo == 0 and hi == 0:
            pp.duration_ms = 0
            continue
        base = lo + rng.random() * (hi - lo)
        base *= (1.0 + cycle_mod)
        base *= lang_mult
        # French clause-level pauses get extra boost
        if lang == 'fr' and pp.level >= 2 and pp.reason.startswith(("subord", "coord")):
            base *= FR_CLAUSE_PAUSE_MULT / FR_PHRASE_PAUSE_MULT  # net FR_CLAUSE_PAUSE_MULT
        pp.duration_ms = int(base)


# ---------------------------------------------------------------------------
# French liaison protection
# ---------------------------------------------------------------------------

def _remove_liaison_pauses(words, pauses, lang):
    """Remove pauses where French liaison would occur."""
    if lang != 'fr':
        return
    to_remove = []
    for idx in pauses:
        if idx < len(words) - 1:
            if _is_fr_liaison(words[idx], words[idx + 1]):
                to_remove.append(idx)
    for idx in to_remove:
        del pauses[idx]


# ---------------------------------------------------------------------------
# Main analysis entry point
# ---------------------------------------------------------------------------

def analyze_sentence(text, lang, is_paragraph_initial=False, is_archaic=False,
                     rng=None, sentence_index=0):
    """Analyze a sentence and produce a ProsodyPlan.

    Args:
        text: Raw sentence text (no [[slnc]] tags).
        lang: 'en' or 'fr'.
        is_paragraph_initial: True if this sentence starts a new paragraph.
        is_archaic: True for archaic English texts (extended word sets).
        rng: numpy RandomState for deterministic duration variety.
        sentence_index: Index of sentence in the book (for breathing-cycle modulation).

    Returns:
        ProsodyPlan with pause points and metadata.
    """
    if rng is None:
        rng = np.random.RandomState(42)

    words = text.split()
    n = len(words)
    length_class = _classify_length(n)
    is_short = length_class == "short"
    has_dlg = _has_dialogue(words)

    plan = ProsodyPlan(
        words=words,
        is_paragraph_initial=is_paragraph_initial,
        is_dialogue=has_dlg,
        is_short=is_short,
        sentence_length_class=length_class,
    )

    if is_short:
        return plan

    coord, subord, rels, adverbs, preps, func = _get_lang_sets(lang, is_archaic)

    pauses = {}  # word_index -> PausePoint

    _pass1_punctuation(words, pauses)
    _pass2_clauses(words, pauses, lang, coord, subord, rels)
    _pass3_phrases(words, pauses, lang, adverbs, preps)
    if has_dlg:
        _pass4_dialogue(words, pauses)
    _pass5_breath_groups(words, pauses, lang, preps, func)

    # Assign durations before position pass (so position adjustments scale real values)
    _assign_durations(pauses, rng, lang, sentence_index)

    _pass6_position(pauses, n, is_paragraph_initial)

    # French liaison protection
    _remove_liaison_pauses(words, pauses, lang)

    # Aggregate cap
    cap = LENGTH_CAPS.get(length_class, 4000)
    total = sum(pp.duration_ms for pp in pauses.values())
    if total > cap and cap > 0:
        scale = cap / total
        for pp in pauses.values():
            pp.duration_ms = int(pp.duration_ms * scale)
        total = sum(pp.duration_ms for pp in pauses.values())

    plan.pause_points = sorted(pauses.values(), key=lambda p: p.word_index)
    plan.total_pause_ms = total
    return plan


# ---------------------------------------------------------------------------
# Audio gap refinement (post-TTS NumPy space)
# ---------------------------------------------------------------------------

def refine_audio_gaps(arr, plan, sample_rate):
    """Splice silence into rendered audio based on ProsodyPlan.

    Detects existing silence gaps via windowed RMS, matches them to pause points
    by fractional position, and extends gaps to meet planned durations.
    Uses cosine crossfades for smooth insertion.

    Args:
        arr: float32 numpy array of rendered audio.
        plan: ProsodyPlan from analyze_sentence().
        sample_rate: Audio sample rate (e.g. 44100).

    Returns:
        Modified float32 numpy array with pauses inserted.
    """
    if not plan.pause_points or plan.is_short:
        return arr

    # RMS silence detection — 10ms windows, 5% threshold, 60ms minimum gap
    # These values are battle-tested (see commit 351976f — fixes consonant clipping)
    win_ms = 10
    win_n = int(win_ms / 1000 * sample_rate)
    min_gap_samples = int(0.060 * sample_rate)

    n_wins = len(arr) // win_n
    if n_wins <= 2:
        return arr

    trimmed = arr[:n_wins * win_n].reshape(n_wins, win_n)
    rms = np.sqrt(np.mean(trimmed ** 2, axis=1))
    thresh = np.median(rms) * 0.05

    is_sil = rms < thresh
    gaps = []
    in_gap = False
    gap_start = 0
    for wi in range(len(is_sil)):
        if is_sil[wi] and not in_gap:
            gap_start = wi * win_n
            in_gap = True
        elif not is_sil[wi] and in_gap:
            gap_end = wi * win_n
            if gap_end - gap_start >= min_gap_samples:
                gaps.append((gap_start, gap_end))
            in_gap = False

    if not gaps:
        return arr

    # Match gaps to pause points by fractional position
    total_samp = len(arr)
    word_count = len(plan.words)
    tol = max(0.08, 2.0 / word_count)

    # Build fractional positions for each pause point
    # Approximate: pause after word i → fraction = (i+1) / word_count
    pp_fracs = []
    for pp in plan.pause_points:
        frac = (pp.word_index + 1) / word_count
        pp_fracs.append((frac, pp))

    # Match each gap to nearest pause point
    used_pp = set()
    gap_assignments = []  # (gap_start, gap_end, planned_duration_ms)

    for gs, ge in gaps:
        gap_frac = (gs + ge) / 2 / total_samp
        best_pp = None
        best_dist = 1.0
        best_idx = -1
        for pi, (pf, pp) in enumerate(pp_fracs):
            if pi in used_pp:
                continue
            d = abs(pf - gap_frac)
            if d < best_dist:
                best_dist = d
                best_pp = pp
                best_idx = pi
        if best_dist <= tol and best_pp is not None and best_idx >= 0:
            used_pp.add(best_idx)
            gap_assignments.append((gs, ge, best_pp.duration_ms))

    if not gap_assignments:
        return arr

    # Adaptive total cap
    max_added = int(plan.total_pause_ms / 1000 * sample_rate * 1.3)
    added_total = 0

    # Process gaps in reverse order to preserve indices
    for gs, ge, planned_ms in reversed(gap_assignments):
        gap_dur_samples = ge - gs
        planned_samples = int(planned_ms / 1000 * sample_rate)

        # Only extend if detected gap is shorter than planned
        extra = planned_samples - gap_dur_samples
        if extra <= 0:
            continue

        # Cap check
        if added_total + extra > max_added:
            extra = max(0, max_added - added_total)
            if extra <= 0:
                continue

        added_total += extra

        # Safety margins (15ms — proven in commit 351976f)
        margin = min(int(0.015 * sample_rate), gap_dur_samples // 4)
        safe_start = gs + margin
        safe_end = ge - margin
        if safe_start >= safe_end:
            continue
        mid = (safe_start + safe_end) // 2

        # Cosine crossfade (8ms — smoother than linear, proven in commit 7d5c45d)
        xf_n = min(int(0.008 * sample_rate), mid, len(arr) - mid)
        if xf_n > 1:
            xf_out = (1 + np.cos(np.linspace(0, np.pi, xf_n))) / 2
            xf_in = (1 - np.cos(np.linspace(0, np.pi, xf_n))) / 2
            xf_out = xf_out.astype(np.float32)
            xf_in = xf_in.astype(np.float32)
            left = arr[:mid].copy()
            right = arr[mid:].copy()
            left[-xf_n:] *= xf_out
            right[:xf_n] *= xf_in
            arr = np.concatenate([left, np.zeros(extra, dtype=np.float32), right])
        else:
            arr = np.concatenate([arr[:mid], np.zeros(extra, dtype=np.float32), arr[mid:]])

    return arr
