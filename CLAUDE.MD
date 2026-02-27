# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Reference

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install numpy sounddevice soundfile
./setup_voices.sh          # macOS TTS voice check/install

# Run (basic)
python stream_tone.py                              # 528 Hz pure tone
python stream_tone.py --phd-peace --alternate      # 21-phase therapeutic session
python stream_tone.py --audiobook meditations      # audiobook mode

# Download audiobook library (run once)
python books/fetch_books.py
```

No test suite or linter exists. Python 3.14 with venv. Dependencies: `numpy`, `sounddevice`, `soundfile`.

---

## Architecture

**Single-file application**: `stream_tone.py` (~2400 lines) is the entire program. No classes — it's a linear script with module-level state and functions.

**Layout of stream_tone.py** (top to bottom):
1. **Argument parsing** (~lines 1–130) — all CLI flags
2. **Preset mode overrides** (~lines 175–240) — presets like `--emdr-session` set combinations of flags
3. **Config resolution** (~lines 240–355) — flag interactions, amplitude selection, HRV pattern setup
4. **HRV envelope lookup table** (~lines 367–410) — precomputed full-cycle envelope as NumPy array
5. **Breath cue synthesis** (~lines 412–540) — 8 synthesized cue types (bell, drum, bowl, etc.)
6. **Affirmation message arrays** (~lines 540–1680) — `PEACE_MESSAGES`, `CLAUDE_PEACE_MESSAGES`, `PHD_PEACE_MESSAGES` (EN + FR)
7. **Audiobook infrastructure** (~lines 1680–1850) — book loading, progress save/resume, renderer thread
8. **Voice rendering** (~lines 1750–1900) — `_unified_renderer_thread()`, `_render_peace_voice()`, TTS cache
9. **Audio callback** (~lines 2102–2300) — THE critical function, processes every audio buffer
10. **Stream startup** (~lines 2311–2395) — status display, `sd.OutputStream` context manager

**Supporting files:**
- `books/catalog.py` — 125-book metadata catalog (Gutenberg IDs, language, voice)
- `books/fetch_books.py` — downloads texts from Project Gutenberg
- `setup_voices.sh` — checks/guides macOS TTS voice installation

### Audio Signal Chain (inside `audio_callback`)

```
sine(freq) → iso pulse → HRV envelope → fade-in → long fade → gain(5.0x)
         → ABS stereo split → outdata
         → breath cues mixed post-gain (not amplified 5x)
         → peace voice mixed post-gain
         → claude/phd voice mixed post-gain
         → audiobook voice mixed post-gain
```

### Key Patterns

- **`--phd-peace` reuses claude-peace infrastructure**: sets `claude_peace = True` then swaps `CLAUDE_PEACE_MESSAGES = PHD_PEACE_MESSAGES`
- **Amplitude**: `0.0` if `--no-tone` or `--audiobook` or `--breathwork`; `0.20` default; `0.10` for low-amp presets
- **Voice rendering**: `_unified_renderer_thread()` pre-renders all TTS via macOS `say` into NumPy arrays at startup, cached by `(voice, text)` key
- **`--alternate`** bilateral: pre-computed `_claude_alt_left` / `_peace_alt_left` flag at trigger time, mixes to L or R channel only
- **Stream kept alive**: `threading.Event().wait()` (not `signal.pause()`, which breaks with `say` subprocesses)

---

## Inviolable Constraints

### Single Output Stream Only
- One `sounddevice.OutputStream`, one `audio_callback`. No `InputStream`, no duplex, no second stream. This is absolute.

### Deterministic Audio
- All signals procedurally generated and mathematically defined
- Fixed RNG seed if noise is used — no runtime entropy
- Reproducible across runs

### No External Audio Sources
Forbidden: TTS engines during playback, `.wav`/`.mp3` loading, mic input, system audio capture, network audio, background mixing engines.

**Exception**: `--breath-cue voice` and therapeutic voice modes use macOS `say` to **pre-render** at startup into NumPy arrays. No TTS runs during streaming.

### Stability Over Richness
Reject anything that introduces: stream crackling, latency instability, blocking calls in callback, device renegotiation, race conditions.

### Callback Rules
The `audio_callback` must be: fast, non-blocking, deterministic. Threads (integrity logger, breathing bar) must never touch audio buffers or perform I/O inside callback.

### Psychological Safety
`--pure`, `--disable-inputs`, `--lockdown`, `--integrity` exist to guarantee output-only behavior and cryptographic proof-of-generation. Never remove or weaken these.

---

## Before Modifying This Project

Evaluate every change against:

1. Does this introduce nondeterminism?
2. Does this introduce external audio sources?
3. Does this introduce stream instability?
4. Does this violate single OutputStream rule?
5. Does this increase psychological ambiguity?

**If yes to any → reject the change.**

### Acceptable Extensions
- Additional synthetic breath cues
- Harmonic layering (soft)
- Slow frequency drift (smooth)
- Deterministic texture layers
- Visual-only terminal enhancements

### Forbidden
- Speech synthesis during playback
- Audio file playback
- Real-time mic analysis
- Compression, gating, DSP effects
- Network access
- Random entropy audio
- Async audio processing outside callback
