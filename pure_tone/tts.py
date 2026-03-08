"""TTS rendering: voice synthesis, unified renderer, audiobook renderer."""

import numpy as np
import subprocess
import tempfile
import os
import re
import sys
import time
import soundfile as sf

from .constants import (
    VOICE_ALIASES, SAMPLE_RATE, AUDIOBOOK_LOOK_AHEAD, AUDIOBOOK_PAGE_SIZE,
    WR_PATTERN, WR_SLNC_CYCLE_EN, WR_LANG_MULT_FR, GLUE_WORDS,
    PUNCT_PAUSE_BASE,
)


def render_voice(text, voice, rate, sample_rate, tts_lock, trim_silence=False):
    """Render a single affirmation via macOS say. Returns float32 numpy array or None.
    If trim_silence=True, strips leading/trailing silence (for audiobook continuity)."""
    say_voice = VOICE_ALIASES.get(voice, voice)
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".aiff", delete=False)
        tmp.close()
        with tts_lock:
            subprocess.run(
                ["say", "-v", say_voice, "-r", str(rate), "-o", tmp.name, text],
                check=True, timeout=15,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
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
        if sr != sample_rate:
            n_in = len(data)
            n_out = int(n_in * sample_rate / sr)
            if n_out > 0:
                indices = np.linspace(0, len(data) - 1, n_out)
                data = np.interp(indices, np.arange(len(data)), data).astype(np.float32)
        data = data - np.mean(data)
        peak = np.max(np.abs(data)) if len(data) > 0 else 0.0
        if peak > 0.01:
            gain = min(0.85 / peak, 3.0)
            data = data * gain
        if trim_silence and len(data) > 0:
            threshold = 0.003
            above = np.where(np.abs(data) > threshold)[0]
            if len(above) > 0:
                pad = int(0.08 * sample_rate)
                start = max(0, above[0] - pad)
                end = min(len(data), above[-1] + pad)
                data = data[start:end]
        fade_n = min(int(0.025 * sample_rate), len(data) // 4)
        if fade_n > 0:
            data[:fade_n] *= (1 - np.cos(np.linspace(0, np.pi, fade_n))) / 2
            data[-fade_n:] *= (1 + np.cos(np.linspace(0, np.pi, fade_n))) / 2
        return data.astype(np.float32)
    except Exception:
        return None


def unified_renderer_thread(g):
    """Single background thread that renders all voice messages sequentially.
    Claude-peace messages are rendered first (phase-ordered, needed earliest).
    Restore-peace messages follow."""
    total_claude = len(g.CLAUDE_PEACE_MESSAGES) if g.claude_peace else 0
    unique_peace = list(dict.fromkeys(g.PEACE_MESSAGES)) if g.restore_peace else []
    total_peace = len(unique_peace)
    total = total_claude + total_peace
    done = 0

    def _progress():
        if g.breath_bar_start_time is not None:
            return
        sys.stdout.write(f"\r  Rendering voices: {done}/{total}   ")
        sys.stdout.flush()

    tts_cache = {}
    for i, (voice, text) in enumerate(g.CLAUDE_PEACE_MESSAGES if g.claude_peace else []):
        cache_key = (voice, text)
        if cache_key in tts_cache:
            g.claude_rendered[i] = tts_cache[cache_key]
        else:
            arr = render_voice(text, voice, rate=130, sample_rate=g.sample_rate, tts_lock=g.tts_lock)
            if arr is not None:
                tts_cache[cache_key] = arr
                g.claude_rendered[i] = arr
        done += 1
        _progress()
    g.claude_render_done = True

    for msg in unique_peace:
        arr = render_voice(msg, g.peace_voice, rate=140, sample_rate=g.sample_rate, tts_lock=g.tts_lock)
        if arr is not None:
            g.peace_rendered[msg] = arr
        done += 1
        _progress()
    g.peace_render_done = True

    if g.breath_bar_start_time is None:
        sys.stdout.write(f"\r  Rendering voices: {done}/{total} complete.                              \n")
        sys.stdout.flush()


def _inject_word_rhythm(text, lang):
    """Inject [[slnc]] tags into text for word-rhythm pacing. Returns modified text."""
    lang_mult = WR_LANG_MULT_FR if lang == 'fr' else 1.0
    slnc_cycle = [int(m * lang_mult) for m in WR_SLNC_CYCLE_EN]
    slnc_idx = 0

    words = text.split()
    if len(words) <= 3:
        return text

    cyc = 0
    cnt = 0
    target = WR_PATTERN[0]
    out = []
    for wi, ww in enumerate(words):
        out.append(ww)
        if re.search(r'[.!?;:]$', ww):
            cnt = 0
            cyc = (cyc + 1) % len(WR_PATTERN)
            target = WR_PATTERN[cyc]
            continue
        cnt += 1
        if cnt >= target and wi < len(words) - 1:
            bare = re.sub(r'[,\-]+$', '', ww).lower()
            next_bare = re.sub(r'[,\-]+$', '', words[wi + 1]).lower()
            if bare not in GLUE_WORDS and next_bare not in GLUE_WORDS:
                out.append(f'[[slnc {slnc_cycle[slnc_idx]}]]')
                slnc_idx = (slnc_idx + 1) % len(slnc_cycle)
                cnt = 0
                cyc = (cyc + 1) % len(WR_PATTERN)
                target = WR_PATTERN[cyc]
    return ' '.join(out)


def _extend_audio_gaps(arr, tts_text, lang, sample_rate, word_gap_mult, reading_rhythm):
    """Find silences in rendered audio and stretch them based on punctuation context."""
    win_ms = 10
    win_n = int(win_ms / 1000 * sample_rate)
    min_gap = int((0.200 if reading_rhythm else 0.025) * sample_rate)
    max_ext = int(1.000 * sample_rate)

    rhythm_scores = None
    if reading_rhythm:
        lang_mult = WR_LANG_MULT_FR if lang == 'fr' else 1.0
        punct_ms = {k: int(v * lang_mult) for k, v in PUNCT_PAUSE_BASE.items()}
        words = tts_text.split()
        total_chars = max(sum(len(w) + 1 for w in words), 1)
        pause_map = []
        char_pos = 0
        for wi_idx, w in enumerate(words):
            char_pos += len(w) + 1
            frac = char_pos / total_chars
            if frac > 0.95:
                continue
            punct_m = re.search(r'([,;:!?\.\-\u2014\u2013])$', w)
            if punct_m:
                pause_map.append((frac, punct_ms.get(punct_m.group(1), 150)))
        rhythm_scores = pause_map
        max_added = int(4.0 * sample_rate)

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
            if gap_end - gap_start >= min_gap:
                gaps.append((gap_start, gap_end))
            in_gap = False

    total_samp = len(arr)
    tol = 2.0 * (60.0 / 170) / max(total_samp / sample_rate, 0.1)
    tol = max(tol, 0.05)

    added_total = 0
    used_punct = set()
    for gs, ge in reversed(gaps):
        gap_dur = ge - gs
        if rhythm_scores is not None and rhythm_scores:
            gap_frac = (gs + ge) / 2 / total_samp
            best_ms = 0
            best_dist = 1.0
            best_idx = -1
            for pi, (pf, pms) in enumerate(rhythm_scores):
                if pi in used_punct:
                    continue
                d = abs(pf - gap_frac)
                if d < best_dist:
                    best_dist = d
                    best_ms = pms
                    best_idx = pi

            if best_dist <= tol and best_idx >= 0:
                used_punct.add(best_idx)
                extra = min(int(best_ms / 1000 * sample_rate), max_ext)
            elif gap_dur >= int(0.150 * sample_rate):
                extra = int(0.070 * sample_rate)
            else:
                continue
            if added_total + extra > max_added:
                continue
            added_total += extra
        else:
            extra = min(int(gap_dur * word_gap_mult), max_ext)
        if extra < int(0.020 * sample_rate):
            continue
        margin = min(int(0.015 * sample_rate), gap_dur // 4)
        safe_start = gs + margin
        safe_end = ge - margin
        if safe_start >= safe_end:
            continue
        mid = (safe_start + safe_end) // 2
        xf_n = min(int(0.005 * sample_rate), mid, len(arr) - mid)
        if xf_n > 1:
            xf_out = np.linspace(1.0, 0.0, xf_n, dtype=np.float32)
            xf_in = np.linspace(0.0, 1.0, xf_n, dtype=np.float32)
            left = arr[:mid].copy()
            right = arr[mid:].copy()
            left[-xf_n:] *= xf_out
            right[:xf_n] *= xf_in
            arr = np.concatenate([left, np.zeros(extra, dtype=np.float32), right])
        else:
            arr = np.concatenate([arr[:mid], np.zeros(extra, dtype=np.float32), arr[mid:]])
    return arr


def audiobook_renderer_thread(g):
    """Rolling renderer: pre-renders a look-ahead buffer of audiobook sentences."""
    if g.claude_peace or g.restore_peace:
        while not (g.claude_render_done and g.peace_render_done):
            time.sleep(0.5)
    total = len(g.audiobook_sentences)
    if total == 0:
        g.audiobook_done = True
        return
    ab_tts_cache = {}
    while True:
        while g.audiobook_next_render < total:
            if g.audiobook_next_render - g.audiobook_play_idx > AUDIOBOOK_LOOK_AHEAD:
                time.sleep(0.5)
                continue
            voice, text = g.audiobook_sentences[g.audiobook_next_render]
            tts_text = text
            if g.reading_rhythm and not g.audiobook_no_gaps:
                tts_text = _inject_word_rhythm(text, g.ab_lang)
            cache_key = (voice, tts_text)
            if cache_key in ab_tts_cache:
                arr = ab_tts_cache[cache_key]
            else:
                arr = render_voice(tts_text, voice, rate=g.ab_rate,
                                   sample_rate=g.sample_rate, tts_lock=g.tts_lock,
                                   trim_silence=True)
                if arr is not None:
                    ab_tts_cache[cache_key] = arr
            if arr is not None and g.reading_rhythm and not g.audiobook_no_gaps:
                arr = _extend_audio_gaps(arr, tts_text, g.ab_lang, g.sample_rate,
                                         g.audiobook_word_gap, g.reading_rhythm)
            if arr is not None:
                g.audiobook_rendered[g.audiobook_next_render] = arr
            else:
                g.audiobook_rendered[g.audiobook_next_render] = np.zeros(int(0.05 * g.sample_rate), dtype=np.float32)
            g.audiobook_next_render += 1
            for idx in list(g.audiobook_rendered):
                if idx < g.audiobook_play_idx - 2:
                    del g.audiobook_rendered[idx]
        g.audiobook_done = True
        if not g.audiobook_loop:
            return
        while g.audiobook_done:
            time.sleep(0.5)
