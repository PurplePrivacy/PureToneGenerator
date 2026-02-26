# CLAUDE.MD

## PureToneGenerator – Architecture, Constraints & Safety Contract

This document defines the architectural, technical, and behavioral contract of the PureToneGenerator project.

It is intended for AI code reviewers (Claude, GPT, etc.) and human maintainers.

The goal is to preserve:

- Deterministic audio generation
- Architectural simplicity
- Stability (no stream breakage)
- Psychological safety
- Zero ambiguity in signal origin

---

# 1. Project Overview

PureToneGenerator is a real-time audio synthesis tool written in Python.

It generates:

- Pure sine tones
- Optional HRV breath envelopes
- Optional isochronic modulation
- Optional alternating bilateral stimulation (ABS)
- Optional breath transition cues (fully synthesized)

The audio is:

- Generated mathematically
- Mixed entirely in-memory
- Sent directly to a single `sounddevice.OutputStream`
- Never read from disk
- Never read from input devices
- Never streamed externally

This project is **intentionally minimalistic and deterministic**.

---

# 2. Core Architectural Principles

## 2.1 Single Output Stream Only

The program must:

- Use `sounddevice.OutputStream`
- Never use `InputStream`
- Never use duplex `Stream`
- Never mix external audio engines
- Never spawn a second audio stream

All audio must be produced inside the single `audio_callback`.

This rule is absolute.

---

## 2.2 Deterministic Audio

All audio signals must be:

- Procedurally generated
- Mathematically defined
- Reproducible across runs

If noise is used:

- It must use a fixed RNG seed
- It must not depend on runtime entropy

This prevents ambiguity and ensures reproducibility.

---

## 2.3 No External Audio Sources

The following are strictly forbidden:

- TTS engines (e.g., macOS `say`)
- OS voice synthesis
- Loading `.wav`, `.aiff`, `.mp3`
- Background audio playback
- External libraries that mix audio independently
- System audio capture

The program must never:

- Play external files
- Record microphone input
- Depend on OS audio routing

---

## 2.4 Stability Over Richness

If a feature introduces:

- Stream crackling
- Latency instability
- Blocking calls
- Device renegotiation
- Race conditions

It must be rejected.

Sound quality and stability are prioritized over complexity.

---

# 3. Audio Design

## 3.1 Base Tone

- Single sine oscillator
- Sample rate: 44100 Hz
- Amplitude capped to avoid clipping
- Optional harmonic layers (if ever added) must remain soft

No distortion effects allowed.

---

## 3.2 HRV Envelope

- Sinusoidal amplitude envelope
- Frequency defined by `hrv_style`
- Smooth modulation only
- No hard edges

This guides breathing gently.

---

## 3.3 Isochronic Modulation

- Implemented via smooth sine-based amplitude modulation
- Must avoid square waves or hard clipping

No abrupt on/off gating.

---

## 3.4 ABS (Alternating Bilateral Stimulation)

- Smooth sine-based stereo crossfade
- No abrupt L/R switching

---

## 3.5 Breath Cues

Breath cues:

- Are synthesized at startup
- Stored as NumPy arrays
- Mixed directly into the output buffer (after gain)
- Never loaded from file at runtime

All synthesized cues must:

- Use exponential decay envelopes
- Avoid broadband harsh noise
- Avoid clipping
- Be deterministic

### Voice cue exception (`--breath-cue voice`)

The `voice` cue uses macOS `say` (Samantha voice) to **pre-render** "inhale" and "exhale"
at startup into NumPy arrays. Once rendered, they are mixed in the callback identically
to any other cue. This is opt-in only, for users who need explicit verbal breathing guidance.

- Rendered once at startup via subprocess (not during playback)
- Stored as float32 NumPy arrays
- Mixed inside the single audio callback
- No TTS engine runs during streaming
- Falls back to bell cue if rendering fails

---

# 4. Security & Psychological Safety Model

This project intentionally includes:

- `--pure`
- `--disable-inputs`
- `--lockdown`
- `--integrity`

These exist to:

- Remove ambiguity
- Guarantee output-only behavior
- Provide cryptographic proof-of-generation

Claude must not:

- Remove or weaken these guarantees
- Introduce hidden signal paths
- Introduce nondeterministic audio sources

---

# 5. Threading Rules

Allowed threads:

- Integrity logger
- Breathing bar (UI only)

Threads must:

- Never touch audio buffers directly
- Never block the audio callback
- Never perform I/O inside callback

The audio callback must remain:

- Fast
- Non-blocking
- Deterministic

---

# 6. Forbidden Changes

Claude must reject suggestions that introduce:

- Speech synthesis
- Audio file playback
- Real-time mic analysis
- Background mixing engines
- Async audio processing outside callback
- Compression, gating, DSP effects
- Network access
- Random entropy audio

This tool is not a DAW.
It is not a meditation app with voice narration.
It is a deterministic tone generator.

---

# 7. Acceptable Extensions

Future extensions must:

- Remain purely mathematical
- Be mixed inside the existing callback
- Not introduce new audio streams
- Not introduce blocking calls
- Not compromise determinism

Examples of acceptable features:

- Additional synthetic breath cues
- Harmonic layering (soft)
- Slow frequency drift (smooth)
- Deterministic texture layers
- Visual-only terminal enhancements

---

# 8. Performance Constraints

Default audio stability settings:

- Latency: high
- Blocksize: 1024+

Bluetooth must be considered unstable at low latency.

Audio must prioritize smooth playback over responsiveness.

---

# 9. Design Philosophy

This tool exists to provide:

- Predictable sound
- Controlled auditory experience
- Calm, stable signal
- Zero ambiguity

Complexity is the enemy.
Determinism is the goal.

---

# 10. If You (Claude) Modify This Project

Before suggesting changes, evaluate:

1. Does this introduce nondeterminism?
2. Does this introduce external audio sources?
3. Does this introduce stream instability?
4. Does this violate single OutputStream rule?
5. Does this increase psychological ambiguity?

If yes to any → reject the change.

---

# 11. Summary

PureToneGenerator is:

- Deterministic
- Single-stream
- Output-only
- Procedural
- Stable-first
- Psychologically conservative

It is intentionally constrained.

Those constraints are features.

---

End of CLAUDE.MD
