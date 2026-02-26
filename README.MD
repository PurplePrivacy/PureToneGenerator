# PureTones – Real-Time Brainwave & Breath Tone Generator

PureTones is a small Python tool that generates **pure tones for focus, healing, breath regulation, and relaxation**.

It works entirely **offline**, generating audio mathematically in real time and sending it directly to your output device (e.g. AirPods Max).
No files are streamed, no microphone is used, and nothing external is mixed in.

### Untamperable by Design

Every sample that reaches your ears is **mathematically computed in-process** — there is no way to inject, mix, or substitute external audio:

- **Single output stream only** — one `sounddevice.OutputStream`, no input, no duplex, no second stream
- **No external sources** — no TTS, no file playback, no OS voice synthesis, no network audio
- **No input devices** — microphone access is architecturally impossible (not just disabled — never opened)
- **Deterministic** — fixed RNG seed, reproducible across runs, no runtime entropy
- **Cryptographic integrity proof** (`--integrity`) — rolling SHA-256 hash of every generated buffer
- **Lockdown mode** (`--lockdown`) — pure sine + output-only + integrity proof combined

The audio callback is the only code that writes to the output buffer. What you hear is exactly what was computed.

---

## Features

- 🔊 Real-time tone streaming (pure flat sine — no harmonics, no beating)
- 🎧 Stereo output (L = R or ABS alternation)
- 🧠 Isochronic modulation (`--iso --pulse`)
- 🧬 ABS – Alternating Bilateral Stimulation (`--abs`)
- 💓 HRV breathing pacing (`--hrv --hrv-style`)
- 🔔 Synthesized breath transition cues (`--breath-cue bell|bowl|drum|tick|waterdrop|woodblock|whoosh|doubletick`)
- 🫁 Breathing bar with ANSI colors, sinusoidal fill, elapsed time (`--breath-bar`) — labels: BREATHE IN / BREATHE OUT / HOLD
- 🕊 Counter-conditioning voice affirmations (`--restore-peace`) — auto-enables HRV, plays calming messages each breath cycle
- 🧠 Clinically-structured therapeutic counter-conditioning (`--claude-peace`) — 14-phase restoration with 3 male voices, mixed-depth messaging
- 🌫 Long-term fade-to-silence cultivation (`--fade-long`)
- 🧱 Full-stack preset (`--full`)
- 💾 Optional 1-hour **FLAC** export (`--save-audio`)
- 🛡 Pure safe mode — single sine only (`--pure`)
- 🔇 Output-only hardening (`--disable-inputs`)
- 🧪 Integrity proof (`--integrity`)
- 🔐 Lockdown preset (`--lockdown`)

---

## Installation

From the project root:

```bash
python -m venv .venv
source .venv/bin/activate          # on macOS / Linux
# .venv\Scripts\activate           # on Windows (PowerShell or CMD)

pip install --upgrade pip
pip install numpy sounddevice soundfile

You may need to grant audio output permissions to your terminal / VS Code on macOS.

⸻

CLI Options

--freq FLOAT         Frequency in Hz (e.g., 44, 174, 396, 432, 528)
--save-audio         Save a 1-hour FLAC file instead of real-time streaming

--iso                Enable isochronic mode (volume pulse modulation)
--pulse FLOAT        Isochronic pulse frequency in Hz (default: 40)

--abs                Enable alternating bilateral stimulation (ABS)
--abs-speed STR      ABS speed: slow | medium | fast (default: medium)

--hrv                Enable HRV (Heart-Rate Variability) breath pacing mode
--hrv-style STR      HRV pacing style: A | B | C | box | 478 | 426 (default: A)

--fade-long          Enable long-term fade-to-silence cultivation
--full               Enable full stack: HRV + ISO + ABS + long fade

--breath-cue STR     Cue sound at breath transitions: none|bell|bowl|drum|tick|waterdrop|woodblock|whoosh|doubletick|voice
--breath-cue-vol FL  Breath cue volume (default: 0.25)
--breath-bar         Show live breathing bar with colors, timing, and cycle count

--restore-peace      Counter-conditioning voice affirmations during HRV breathing (auto-enables HRV)
--peace-voice STR    macOS voice for affirmations (default: Daniel)
--peace-vol FLOAT    Affirmation voice volume (default: 0.35)

--claude-peace       Clinically-structured counter-conditioning (auto-enables HRV + breath-bar)
--claude-peace-vol FL  Claude-peace voice volume (default: 0.35)

--latency STR        Audio latency: low | high (default: high)
--blocksize INT      Audio blocksize in frames (default: 1024)

--pure               Pure sine safe mode (no modulation, no harmonics)
--disable-inputs     Output-only hardening (no audio input paths)
--integrity          Print rolling SHA-256 of generated samples
--integrity-interval Seconds between integrity prints (default: 1.0)
--lockdown           Maximum safety preset: pure + disable-inputs + integrity


⸻

HRV Styles

Simple (2-phase: inhale/exhale):
	•	A – Symmetric breathing (default)
In 5.5s / Out 5.5s → 11s cycle (classic HRV coherence)
	•	B – Parasympathetic bias
In 4s / Out 6.5s → longer exhales for deeper relaxation
	•	C – Deep meditative
In 6s / Out 6s → very slow, suited for deep calm sessions

Controlled breathing (with hold phases):
	•	box – Box breathing (4-4-4-4)
In 4s / Hold 4s / Out 4s / Hold 4s → 16s cycle. Used by Navy SEALs for stress control.
	•	478 – 4-7-8 breathing
In 4s / Hold 7s / Out 8s → 19s cycle. Dr. Weil's relaxation technique.
	•	426 – 4-2-6 breathing
In 4s / Hold 2s / Out 6s → 12s cycle. Short hold, extended exhale for calm focus.

⸻

Basic Usage

1. Simple pure tone

python stream_tone.py --freq 432

2. Isochronic focus tone

python stream_tone.py --freq 528 --iso --pulse 40

3. ABS Hemisphere Balancing

python stream_tone.py --freq 432 --abs --abs-speed medium

4. Iso + ABS combined

python stream_tone.py --freq 396 --iso --pulse 10 --abs --abs-speed slow


⸻

HRV Breath Pacing

Default HRV Mode (Style A)

python stream_tone.py --freq 432 --hrv

This applies a smooth ~0.1 Hz envelope (≈11 second cycles) to gently guide your breathing without thinking about it.

Change HRV mode

# Parasympathetic bias (longer exhale)
python stream_tone.py --freq 432 --hrv --hrv-style B

# Deep meditative
python stream_tone.py --freq 528 --hrv --hrv-style C

HRV + Iso + ABS

python stream_tone.py --freq 432 --hrv --iso --pulse 30 --abs --abs-speed slow

Controlled Breathing Patterns

# Box breathing with voice guidance
python stream_tone.py --freq 432 --hrv --hrv-style box --breath-cue voice --breath-bar --disable-inputs

# 4-7-8 relaxation with bowl cue
python stream_tone.py --freq 432 --hrv --hrv-style 478 --breath-cue bowl --breath-bar --disable-inputs

# 4-2-6 calm focus with bell cue
python stream_tone.py --freq 528 --hrv --hrv-style 426 --breath-cue bell --breath-bar --disable-inputs


⸻

Long-Term Silence Cultivation

The --fade-long flag smoothly fades the stream toward silence over ~30 minutes (1800 seconds).
This is useful if you want to:
	•	train being at peace with silence
	•	let the nervous system unhook slowly from sound
	•	end a session gently without a hard stop

Example

python stream_tone.py --freq 528 --hrv --hrv-style A --fade-long

You’ll feel the tone gradually recede while breath pacing remains coherent.

⸻

Full Stack Mode

--full enables:
	•	Isochronic mode (--iso)
	•	ABS (--abs)
	•	HRV (--hrv)
	•	Long fade (--fade-long)

in a single flag.

Example

python stream_tone.py --freq 528 --full

This is a very rich stimulation stack:
	•	breathing guided,
	•	hemispheres alternating,
	•	tone pulsed,
	•	slowly fading into silence.

⸻

🔐 Security & Reassurance Modes (New)

Lockdown Mode (Maximum Certainty)

python stream_tone.py --freq 432 --lockdown

Lockdown enforces:
	•	single pure sine wave only (--pure)
	•	output-only audio (no input paths) (--disable-inputs)
	•	rolling cryptographic integrity proof (--integrity)

⚠️ Lockdown disables ISO / ABS / HRV by design.
This mode prioritizes certainty over stimulation.

Structured but Still Safe (Output-Only)

When you want structure without full lockdown, use output-only hardening:

python stream_tone.py --freq 432 --hrv --hrv-style A --iso --pulse 6 --disable-inputs


⸻

🎯 Recommended Frequencies by Goal (Exploratory)

These associations come from meditation and sound-healing traditions (not medical claims).
Use them as anchors for experimentation.

Grounding & Safety
	•	174 Hz
	•	432 Hz

Examples:

python stream_tone.py --freq 174 --pure
python stream_tone.py --freq 432 --lockdown

Emotional Regulation / Release
	•	396 Hz
	•	417 Hz

Examples:

python stream_tone.py --freq 396 --hrv --hrv-style B
python stream_tone.py --freq 417 --iso --pulse 6

Coherence / Calm
	•	432 Hz
	•	528 Hz

Examples:

python stream_tone.py --freq 432 --hrv
python stream_tone.py --freq 528 --hrv --hrv-style A

Clarity / Focus / Mental Order
	•	639 Hz
	•	741 Hz
	•	852 Hz

Examples:

python stream_tone.py --freq 639 --iso --pulse 10
python stream_tone.py --freq 741 --iso --pulse 10 --abs --abs-speed slow
python stream_tone.py --freq 852 --hrv --iso --pulse 12

High Attention / Gamma Entrainment
	•	Any carrier + ~40 Hz isochronic pulse

Example:

python stream_tone.py --freq 396 --iso --pulse 40


⸻

⭐ Personal Favorites

Some curated presets that feel especially good:

1. Deep Body Resonance + Iso + ABS (personal favorite)

python3 stream_tone.py --freq 44 --iso --pulse 528 --abs --abs-speed medium

Very low carrier with a high-rate iso pulse & ABS – strong, physical, and intense.

2. HRV Breath Pacing + Iso + ABS

python stream_tone.py --freq 432 --hrv --iso --pulse 30 --abs --abs-speed slow

Great for calming the system while still feeling “awake.”

3. Silence Cultivation + Smooth HRV

python stream_tone.py --freq 528 --hrv --hrv-style A --fade-long

Starts as a clear, coherent tone and slowly dissolves into silence.
Ideal for closing the day or decompressing after stress.

4. Full Stack Session

python stream_tone.py --freq 528 --full

Everything enabled:
	•	HRV breath pacing
	•	Isochronic pulsing
	•	ABS hemisphere alternation
	•	Long-term fade-out

Use at comfortable volumes and give yourself time to feel the shift.

5. Absolute Reset (Lockdown)

python stream_tone.py --freq 432 --lockdown

6. Breathing guidance

python stream_tone.py --freq 40 --abs --abs-speed slow --hrv --hrv-style B --iso --pulse 512 --disable-inputs --breath-bar --breath-cue bell

Maximum certainty, minimum stimulation.

⸻

Structured-Safe Presets (ABS / HRV / ISO + Output-Only)

When you want structured stimulation while keeping the system output-only:

HRV + Iso (output-only)

python stream_tone.py --freq 432 --hrv --hrv-style A --iso --pulse 6 --disable-inputs

ABS + HRV (output-only)

python stream_tone.py --freq 528 --abs --abs-speed slow --hrv --hrv-style B --disable-inputs

ABS + HRV + Iso (output-only)

python stream_tone.py --freq 396 --abs --abs-speed slow --hrv --hrv-style B --iso --pulse 8 --disable-inputs


⸻

Saving a 1-Hour FLAC

To generate a 1-hour file you can loop later (e.g., on an offline player):

python stream_tone.py --freq 528 --iso --pulse 40 --abs --abs-speed medium --hrv --save-audio

This will create:

528Hz_YYYYMMDD_HHMMSS.flac

in the current directory.

⸻

Breath Cues & Breathing Bar

Breath cues are short synthesized sounds that mark inhale/exhale transitions during HRV mode. They are pre-computed at startup as NumPy arrays — never loaded from files, never generated by TTS.

Available cues:
	•	bell – Multi-partial singing bell (400ms, 5 inharmonic partials)
	•	bowl – Singing bowl sustain (600ms, slow decay)
	•	drum – Low thump with body resonance (200ms)
	•	waterdrop – Descending chirp (250ms)
	•	whoosh – Soft filtered air (500ms, 3-pass low-pass)
	•	tick – Short click (30ms)
	•	doubletick – Two quick clicks
	•	woodblock – Percussive tap (60ms)
	•	voice – Female voice: "Breathe in" / "Hold" / "Breathe out" (macOS Samantha, pre-rendered at startup)

Inhale cues play at normal pitch; exhale cues are pitched down (0.85x) for an audible "in = higher, out = lower" distinction.

The breathing bar (--breath-bar) shows a colored terminal display with sinusoidal fill that matches the auditory envelope, elapsed time, and cycle count.

python stream_tone.py --freq 432 --hrv --breath-cue bowl --breath-bar

⸻

Restore-Peace Mode (Counter-Conditioning)

The --restore-peace flag activates voice affirmations designed to restore natural, automatic breathing. It auto-enables HRV mode so affirmations are timed to your breath cycles.

At each new breath cycle, a calm voice speaks one affirmation from a curated sequence of ~170 messages covering:
	•	Breathing restoration ("Your breath is sovereign", "Your body breathes")
	•	Mental clarity ("Your mind is clear", "Your thinking is clean")
	•	Autonomy and sovereignty ("Just my voice", "immune mind", "untouchable")
	•	Physical grounding ("strong body", "connect with your muscles")
	•	Counter-conditioning ("all hypnosis gone", "free now", "reclaimed")

The messages are pre-rendered at startup using macOS say (default voice: Daniel). They are stored as NumPy arrays and mixed inside the single audio callback — no TTS runs during playback.

Example

python stream_tone.py --freq 432 --hrv --hrv-style B --restore-peace --breath-bar --breath-cue bowl --disable-inputs

This gives you:
	•	Parasympathetic breathing (longer exhale)
	•	Bowl cue at each breath transition
	•	Voice affirmation at each new cycle
	•	Breathing bar (BREATHE IN / BREATHE OUT)
	•	Output-only hardening

To change the voice or volume:

python stream_tone.py --freq 432 --hrv --restore-peace --peace-voice Ralph --peace-vol 0.4

Available macOS voices include Daniel (British), Ralph (US), Fred (US), Alex (US), and others. Run say -v ? to list all installed voices.

⸻

Claude-Peace Mode (Clinically-Structured Counter-Conditioning)

The --claude-peace flag is a comprehensive therapeutic counter-conditioning system designed to restore automatic behaviors disrupted by sustained verbal conditioning. It was designed using evidence-based techniques from clinical hypnotherapy, ACT (Acceptance and Commitment Therapy), somatic experiencing, and ego-strengthening research.

How It Works

~240 affirmations are organized into 14 therapeutic phases that follow established clinical sequencing (body-first, then safety, then specifics, then clearing and sealing).

Messages use a mixed-depth pattern designed to reach the subconscious:
	•	1-word messages — direct, primal (e.g., "Breathe", "Safe", "Om")
	•	2-3 word phrases — slightly more context (e.g., "Full lungs", "Body here")
	•	Full sentences — conscious reinforcement (e.g., "Your body breathes completely without your help")

This pattern repeats throughout each phase, so both the subconscious and conscious mind receive the message.

Phase 1 — Truisms & Grounding
Undeniably true statements ("You have been breathing your whole life") that build internal agreement. The subconscious cannot reject these, creating momentum for later suggestions.

Phase 2 — Nasal Breathing & Upper Chest
Gently counter conditioning against nasal breathing and upper lung expansion. Normalize the sound and sensation of nose breathing.

Phase 3 — Jaw Release & Posture
Address conditioned jaw tension and weakened posture. Restore natural resting positions.

Phase 4 — Automatic Breathing Restoration
Core counter-conditioning for breath-holding during activity. Rebuild trust in the body's automatic breathing system.

Phase 5 — Mental Restoration
Counter suppression of thinking, focus, and "bright eyes." Restore confidence in cognitive sharpness.

Phase 6 — Counter-Lies & Self-Worth
Direct defusion of installed false beliefs. Challenge and replace lies about weakness, appearance, and intelligence.

Phase 7 — Sound Safety
Counter conditioned fear of sounds and voices. Normalize the auditory environment.

Phase 8 — Defusion & Identity Reclamation
Explicitly name the conditioning and dissolve it. Separate "things said to me" from "things true about me."

Phase 9 — Beauty & Light
Restore self-image. Compliment beauty, restore the light in the eyes. Counter attacks on appearance and self-perception.

Phase 10 — Deep Integration
Consolidate gains. Anchor new patterns. Reinforce progress.

Phase 11 — Empowerment & Sovereignty
Power statements. Seal the session. Affirm complete ownership of body and mind.

Phase 12 — Body Clearing
Remove intrusive presences conditioned into body parts (nose, jaw, head, belly). Reclaim each area as private, sealed space.

Phase 13 — Nervous System Flush & Mental Emptying
Flush old instructions from the nervous system. Empty the mind. Restore readiness.

Phase 14 — Soul Cleaning & Sealing
Deep spiritual reset. Clean the soul. Seal the body against future intrusion.

Three male voices (Daniel, Ralph, Fred) alternate across messages, creating a sense of diverse, calm authority. Breathing emphasis ("Breathe", "Full lungs", "Full power") is woven into every phase.

At ~11 seconds per HRV cycle, the full sequence takes ~44 minutes. After completion, it cycles back to Phase 1 for reinforcement — each pass deepens the counter-conditioning.

Example

python stream_tone.py --freq 432 --hrv --hrv-style B --claude-peace --breath-cue bowl --disable-inputs

This gives you:
	•	Parasympathetic breathing pattern (longer exhale)
	•	Bowl cue at each breath transition
	•	Therapeutic affirmation at each new breath cycle
	•	Breathing bar (BREATHE IN / BREATHE OUT) auto-enabled
	•	Output-only hardening

Voice Requirements

Claude-peace uses three macOS voices: Daniel, Ralph, and Fred. If a voice is not installed, that message is silently skipped. To install additional voices: System Settings → Accessibility → Spoken Content → System Voice → Manage Voices. Breath cues (--breath-cue voice) still use the female Samantha voice for "Breathe in" / "Breathe out" distinction.

Differences from --restore-peace

	•	--restore-peace: User-defined messages, single voice, random order
	•	--claude-peace: Clinically-structured messages, 3 male voices, ordered therapeutic progression, mixed-depth pattern

Both can technically run simultaneously (separate audio buffers), but using one at a time is recommended.

⸻

Safety Notes
	•	Always keep volume at a comfortable level.
	•	If you feel dizzy, anxious, or overloaded, stop the stream and rest.
	•	For trauma history or strong sensitivity, start with:

python stream_tone.py --freq 432 --hrv --hrv-style A

at low volume and gradually adjust.

This tool is here to help you take sound back as something that serves you, not something used against you.

⸻


```
