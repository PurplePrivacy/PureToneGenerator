"""Breath cue waveform synthesis."""

import numpy as np
import subprocess
import tempfile
import os
import soundfile as sf

from .constants import EXHALE_PITCH_FACTOR


def _apply_fade_out(cue, sample_rate, fade_ms=10):
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


def render_voice_cue(word, sample_rate):
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
        if data.ndim > 1:
            data = data.mean(axis=1)
        if sr != sample_rate:
            indices = np.linspace(0, len(data) - 1, int(len(data) * sample_rate / sr))
            data = np.interp(indices, np.arange(len(data)), data)
        fade_n = min(int(0.01 * sample_rate), len(data) // 4)
        if fade_n > 0:
            data[:fade_n] *= np.linspace(0, 1, fade_n)
            data[-fade_n:] *= np.linspace(1, 0, fade_n)
        return data.astype(np.float32)
    except Exception as e:
        print(f"Warning: voice cue '{word}' failed ({e}), falling back to bell")
        return None


def build_cues(g):
    """Synthesize all breath cue waveforms and store them on g."""
    sr = g.sample_rate
    rng = np.random.RandomState(1337)

    tick_len = int(0.03 * sr)
    bell_len = int(0.40 * sr)
    drum_len = int(0.20 * sr)
    water_len = int(0.25 * sr)
    wood_len = int(0.06 * sr)
    bowl_len = int(0.60 * sr)
    whoosh_len = int(0.50 * sr)
    double_len = int(0.10 * sr)

    # Tick
    t = np.arange(tick_len) / sr
    tick_cue = np.sin(2 * np.pi * 1800 * t) * np.exp(-t * 80)

    # Double-tick
    doubletick_cue = np.zeros(double_len, dtype=np.float32)
    t1 = np.arange(tick_len) / sr
    doubletick_cue[:tick_len] += (np.sin(2 * np.pi * 1800 * t1) * np.exp(-t1 * 80)).astype(np.float32)
    shift = int(0.05 * sr)
    end2 = min(shift + tick_len, double_len)
    t2 = np.arange(end2 - shift) / sr
    doubletick_cue[shift:end2] += (np.sin(2 * np.pi * 1800 * t2) * np.exp(-t2 * 80)).astype(np.float32)

    # Bell
    t = np.arange(bell_len) / sr
    bell_cue = (0.50 * np.sin(2 * np.pi * 880 * t)
                + 0.25 * np.sin(2 * np.pi * 1320 * t)
                + 0.12 * np.sin(2 * np.pi * 1760 * t)
                + 0.08 * np.sin(2 * np.pi * 2640 * t)
                + 0.05 * np.sin(2 * np.pi * 3520 * t)) * np.exp(-t * 10)

    # Bowl
    t = np.arange(bowl_len) / sr
    bowl_cue = (0.50 * np.sin(2 * np.pi * 440 * t)
                + 0.25 * np.sin(2 * np.pi * 660 * t)
                + 0.15 * np.sin(2 * np.pi * 880 * t)
                + 0.10 * np.sin(2 * np.pi * 1100 * t)) * np.exp(-t * 4)

    # Drum
    t = np.arange(drum_len) / sr
    drum_noise = rng.uniform(-1, 1, drum_len) * np.exp(-t * 40)
    drum_cue = (0.7 * np.sin(2 * np.pi * 110 * t) * np.exp(-t * 22)
                + 0.3 * np.sin(2 * np.pi * 55 * t) * np.exp(-t * 15)
                + 0.10 * drum_noise)

    # Woodblock
    t = np.arange(wood_len) / sr
    woodblock_cue = np.sin(2 * np.pi * 520 * t) * np.exp(-t * 60)

    # Waterdrop
    t = np.arange(water_len) / sr
    f0, f1 = 1600.0, 600.0
    k = (f1 - f0) / (water_len / sr)
    water_phase = 2 * np.pi * (f0 * t + 0.5 * k * t**2)
    waterdrop_cue = np.sin(water_phase) * np.exp(-t * 18)

    # Whoosh
    t = np.arange(whoosh_len) / sr
    whoosh_noise = rng.uniform(-1, 1, whoosh_len).astype(np.float32)
    alpha = 0.02
    whoosh_lp = np.zeros_like(whoosh_noise)
    for _pass in range(3):
        src = whoosh_noise if _pass == 0 else whoosh_lp.copy()
        whoosh_lp[0] = src[0] * alpha
        for i in range(1, len(src)):
            whoosh_lp[i] = whoosh_lp[i-1] + alpha * (src[i] - whoosh_lp[i-1])
    whoosh_env = np.sin(np.pi * np.clip(t / (whoosh_len / sr), 0, 1))
    whoosh_cue = whoosh_lp * whoosh_env * 0.6

    # Build cue maps
    g.tick_cue = tick_cue
    g.cue_map = {
        "tick": _apply_fade_out(tick_cue, sr),
        "doubletick": _apply_fade_out(doubletick_cue, sr),
        "bell": _apply_fade_out(bell_cue, sr),
        "bowl": _apply_fade_out(bowl_cue, sr),
        "drum": _apply_fade_out(drum_cue, sr),
        "woodblock": _apply_fade_out(woodblock_cue, sr),
        "waterdrop": _apply_fade_out(waterdrop_cue, sr),
        "whoosh": _apply_fade_out(whoosh_cue, sr),
    }
    g.exhale_cue_map = {name: _pitch_shift(cue, EXHALE_PITCH_FACTOR) for name, cue in g.cue_map.items()}

    # Voice cues (rendered via macOS say)
    g.voice_inhale_cue = None
    g.voice_exhale_cue = None
    g.voice_hold_cue = None

    if g.breath_cue == "voice":
        print("Rendering voice cues...")
        g.voice_inhale_cue = render_voice_cue("Breathe in", sr)
        g.voice_exhale_cue = render_voice_cue("Breathe out", sr)
        g.voice_hold_cue = render_voice_cue("Hold", sr)
        if g.voice_inhale_cue is None or g.voice_exhale_cue is None or g.voice_hold_cue is None:
            print("Voice cue rendering failed, falling back to bell")
            g.breath_cue = "bell"


def select_cue(g, phase_name="INHALE"):
    """Return the appropriate cue waveform for the given phase."""
    if g.breath_cue == "none":
        return None
    if g.breath_cue == "voice":
        if phase_name == "INHALE":
            return g.voice_inhale_cue
        elif phase_name == "EXHALE":
            return g.voice_exhale_cue
        elif phase_name == "HOLD":
            return g.voice_hold_cue
        return None
    if phase_name == "HOLD":
        return g.tick_cue
    if phase_name == "EXHALE":
        return g.exhale_cue_map.get(g.breath_cue)
    return g.cue_map.get(g.breath_cue)
