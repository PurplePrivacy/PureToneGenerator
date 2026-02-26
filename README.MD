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
- 🧠 Clinically-structured therapeutic counter-conditioning (`--claude-peace`) — 16-phase restoration with 3 male voices, mixed-depth messaging
- 🎓 Expert-reviewed 21-phase counter-conditioning (`--phd-peace`) — all claude-peace phases plus 5 default-state conditioning rounds
- 👂 EMDR-style bilateral voice alternation (`--alternate`) — messages alternate between left and right speakers
- ⚡ Dense affirmation mode (`--dense`) — one message per breath phase instead of per full cycle
- 🌫 Long-term fade-to-silence cultivation (`--fade-long`)
- 🧱 Full-stack preset (`--full`)
- 📖 Audiobook mode — 50 French public domain books read by Thomas voice during HRV sessions (`--audiobook`)
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
--phd-peace          Expert-reviewed 21-phase counter-conditioning (auto-enables HRV + breath-bar)
--phd-peace-vol FL   PhD-peace voice volume (default: 0.35)
--alternate          Alternate voice messages between L and R speakers (EMDR-style bilateral)
--dense              Affirmation every breath phase (~5.5s) instead of every full cycle (~11s)
--peace-lang STR     Language for peace affirmations: en | fr (default: en)

--audiobook BOOK     Read a book aloud during HRV breathing (e.g., --audiobook meditations)
--audiobook-list     List all 50 available audiobooks and exit
--audiobook-vol FL   Audiobook voice volume (default: 0.40)
--audiobook-resume   Resume from saved position (progress saved on Ctrl-C)

--latency STR        Audio latency: low | high (default: high)
--blocksize INT      Audio blocksize in frames (default: 1024)

--no-tone            Silence the base tone (voice messages and cues still play)
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

~290 affirmations are organized into 16 therapeutic phases that follow established clinical sequencing (body-first, then safety, then specifics, then clearing and sealing).

Messages use a mixed-depth pattern designed to reach the subconscious:
	•	1-word messages — direct, primal (e.g., "Breathe", "Safe", "Om")
	•	2-3 word phrases — slightly more context (e.g., "Full lungs", "Body here")
	•	Full sentences — conscious reinforcement (e.g., "Your body breathes completely without your help")

This pattern repeats throughout each phase, so both the subconscious and conscious mind receive the message.

All messages use purely positive language (zero negation). The subconscious does not process "not" — so every suggestion affirms what IS true, rather than denying what is false.

Phase 1 — Truisms & Grounding
Undeniable facts ("You have been breathing your entire life") build a yes-set. The subconscious accepts these, creating momentum for all suggestions that follow.

Phase 2 — Nasal Breathing & Chest Opening
Celebrate nasal breathing. Pair it with warmth, pleasure, and ease. Chest expands freely.

Phase 3 — Jaw Release & Posture
Jaw softens and melts. Spine holds you tall. All positive framing — "your jaw relaxes" rather than "your jaw doesn't need to hold."

Phase 4 — Automatic Breathing & Exhale Power
Core counter-conditioning. Breathing is automatic. Exhale = power, relief, renewal, satisfaction. Includes reminders to let breath flow wild and free — release all holding.

Phase 5 — Focus & Mental Clarity
Counter-condition focus. Concentration is your natural superpower. Deep focus flows easily. Your mind thinks with perfect clarity.

Phase 6 — Self-Worth & Strength
Hartland ego-strengthening. You are strong, capable, brilliant, resilient. Your value is permanent and self-evident.

Phase 7 — Sound Safety
Your inner world stays calm through all sounds. Sound passes through you like wind. Your inner silence is more powerful than any external sound.

Phase 8 — Identity Reclamation
Your true self is whole, intact, and rising. Everything that is truly you comes back to the surface. Your original self is brilliant and alive.

Phase 9 — Beauty & Light
Restore self-image. Eyes carry light. Beauty is real, permanent, and growing stronger. Compliments and warmth.

Phase 10 — Inner Peace as Strength
Counter-condition inner peace. Peace is your deepest power. Calm is strength. Serenity is your natural resting state and birthright.

Phase 11 — Movement & Vitality
Counter-condition movement. Every movement fills you with strength. Your body moves freely, joyfully, with complete sovereignty. Movement is your birthright.

Phase 12 — Deep Integration
Consolidate all gains. Healing connects and flows together. You become exactly who you have always been.

Phase 13 — Body Sovereignty
Every part of your body is yours alone. Private, sealed, clean, and sovereign.

Phase 14 — Nervous System Restoration
Your nervous system carries only your own pure signals. Returns to its original, pristine state. Mind is spacious and powerful.

Phase 15 — Taking Your Time / Above the Sky
Patience, timelessness, vast perspective. You are above the sky. Everything below looks small and peaceful.

Phase 16 — Centering & Inner Strength (FORT)
Center deep inside yourself. Breathe powerfully. Your voice is loud, commanding, dominant. You define yourself with one word: STRONG.

Three male voices (Daniel, Ralph, Fred) alternate across messages, creating a sense of diverse, calm authority. Breathing emphasis ("Breathe", "Full lungs", "Full power") is woven into every phase.

At ~11 seconds per HRV cycle, the full sequence takes ~54 minutes. After completion, it cycles back to Phase 1 for reinforcement — each pass deepens the counter-conditioning.

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

French Language Support

Use --peace-lang fr to switch all peace affirmations (both --restore-peace and --claude-peace) to French. French voices are mapped from the English defaults:
	•	Daniel → Thomas (fr_FR)
	•	Ralph → Jacques (fr_FR)
	•	Fred → Nicolas Enhanced (fr_CA)

When --peace-lang fr is set:
	•	--restore-peace defaults to Thomas (instead of Daniel) unless --peace-voice is explicitly set
	•	--breath-cue voice remains in English (Samantha) regardless of language setting

Examples:

# French claude-peace
python stream_tone.py --freq 432 --claude-peace --peace-lang fr --disable-inputs

# French restore-peace
python stream_tone.py --freq 432 --hrv --hrv-style B --restore-peace --peace-lang fr --breath-bar --disable-inputs

Differences from --restore-peace

	•	--restore-peace: User-defined messages, single voice, random order
	•	--claude-peace: Clinically-structured messages, 3 male voices, ordered therapeutic progression, mixed-depth pattern

Both can technically run simultaneously (separate audio buffers), but using one at a time is recommended.

⸻

PhD-Peace Mode (Expert-Reviewed 21-Phase Counter-Conditioning)

The --phd-peace flag extends claude-peace with 5 additional "default state conditioning" rounds (17–21) that anchor your baseline identity states. All 384 messages were reviewed by an expert agent prompted as a PhD in clinical hypnosis, Ericksonian therapy, EMDR, counter-conditioning, and somatic experiencing.

This mode includes all 16 original claude-peace phases plus:

Phase 17 — Default Expression: "I Know Something You Don't"
Anchor the resting facial expression: knowing smile, quiet confidence, amused awareness. Somatic: feel the smile muscles, the eyes, the face at rest.

Phase 18 — Default Posture: Straight, Solemn, Dignity, Dominance
Anchor upright, commanding posture as the natural resting state. Proprioceptive: spine, shoulders, chest, jaw — all aligned with power.

Phase 19 — Default Feeling: Joyful Stillness, Inner Peace
Reinforce inner peace as the default emotional baseline. Presuppose it's already the natural state, not something to achieve.

Phase 20 — Default Mode: Analysing, Assessing, Optimizing, Thinking
Anchor the default mental operating mode: always scanning, processing, optimizing. Natural intelligence as the resting state.

Phase 21 — Default Body Rapport: Feeling Great, Connected to Muscles & Power
Anchor deep connection to the physical body as the default. Strength, vitality, power — always present.

Total: 384 affirmations across 21 phases (~70 minutes at 11s/cycle). After completion, cycles back to Phase 1 for reinforcement.

Example

python stream_tone.py --freq 432 --hrv --hrv-style B --phd-peace --breath-cue bowl --disable-inputs

With EMDR-style bilateral voice alternation (each message alternates between left and right speaker):

python stream_tone.py --freq 432 --hrv --hrv-style B --phd-peace --alternate --breath-cue bowl --disable-inputs

The --alternate flag works with --claude-peace, --phd-peace, and --restore-peace. It creates bilateral auditory stimulation by sending each successive voice message to alternating ears.

Dense mode (--dense) doubles the affirmation rate by triggering on every breath phase transition (~5.5s) instead of every full cycle (~11s). This cuts the full sequence from ~70 minutes to ~35 minutes:

python stream_tone.py --phd-peace --dense --alternate --no-tone --disable-inputs

All options can be combined freely:

# Voices only, dense, bilateral, French
python stream_tone.py --phd-peace --dense --alternate --no-tone --peace-lang fr --disable-inputs

# With background tone and bowl cue
python stream_tone.py --freq 432 --phd-peace --dense --alternate --breath-cue bowl --disable-inputs

# Original 16-phase claude-peace, dense bilateral
python stream_tone.py --claude-peace --dense --alternate --no-tone --disable-inputs

# Restore-peace with dense bilateral
python stream_tone.py --freq 432 --hrv --restore-peace --dense --alternate --breath-bar --disable-inputs

The --claude-peace flag (16 phases, 294 messages) remains available separately for the original therapeutic sequence.

⸻

Audiobook Mode (50 French Public Domain Books)

The --audiobook flag reads a full public domain book aloud during HRV breathing sessions using the French Thomas voice. Books are stored as local text files and rendered sentence-by-sentence using a rolling TTS renderer.

Setup

# Download all 50 books from Project Gutenberg (run once)
python books/fetch_books.py

# List available books
python stream_tone.py --audiobook-list

How It Works
	•	A rolling renderer pre-renders ~10 sentences ahead of playback
	•	Each sentence is triggered at HRV breath cycle transitions
	•	If a sentence is still playing when a new cycle starts, it continues — no interruption
	•	Memory stays bounded: only ~12 rendered sentences in memory at once
	•	Uses the same TTS pipeline as claude-peace (macOS say → NumPy array)

Available Books (50)

Stoic Philosophy (5):
	•	meditations — Méditations (Marc Aurèle)
	•	enchiridion — Manuel d'Épictète
	•	lettres-lucilius — Lettres à Lucilius (Sénèque)
	•	brievete-vie — De la brièveté de la vie (Sénèque)
	•	tranquillite — De la tranquillité de l'âme (Sénèque)

Greek Philosophy (7):
	•	republique — La République (Platon)
	•	apologie — Apologie de Socrate (Platon)
	•	banquet — Le Banquet (Platon)
	•	phedon — Phédon (Platon)
	•	phedre — Phèdre (Platon)
	•	gorgias — Gorgias (Platon)
	•	ethique-nicomaque — Éthique à Nicomaque (Aristote)

Eastern Philosophy (5):
	•	art-guerre — L'Art de la guerre (Sun Tzu)
	•	tao-te-king — Tao Te King (Lao Tseu)
	•	dhammapada — Dhammapada (Bouddha)
	•	bhagavad-gita — Bhagavad-Gita
	•	entretiens-confucius — Les Entretiens (Confucius)

Japanese Wisdom (2):
	•	cinq-anneaux — Le Livre des cinq anneaux (Musashi)
	•	bushido — Bushido, l'âme du Japon (Nitobe)

Religious Texts (2):
	•	bible — La Sainte Bible (Louis Segond)
	•	coran — Le Coran (Kasimirski)

French Philosophy (6):
	•	essais — Essais (Montaigne)
	•	discours-methode — Discours de la méthode (Descartes)
	•	pensees — Pensées (Pascal)
	•	prince — Le Prince (Machiavel)
	•	contrat-social — Du contrat social (Rousseau)
	•	oracle-manuel — L'Oracle manuel (Gracián)

German Philosophy (3):
	•	zarathoustra — Ainsi parlait Zarathoustra (Nietzsche)
	•	art-raison — L'Art d'avoir toujours raison (Schopenhauer)
	•	bien-mal — Par-delà le bien et le mal (Nietzsche)

French Literature (8):
	•	candide — Candide (Voltaire)
	•	fables — Les Fables (La Fontaine)
	•	fleurs-mal — Les Fleurs du mal (Baudelaire)
	•	miserables — Les Misérables (Hugo)
	•	monte-cristo — Le Comte de Monte-Cristo (Dumas)
	•	trois-mousquetaires — Les Trois Mousquetaires (Dumas)
	•	cyrano — Cyrano de Bergerac (Rostand)
	•	petit-prince — Le Petit Prince (Saint-Exupéry)

Classical Literature (5):
	•	odyssee — L'Odyssée (Homère)
	•	iliade — L'Iliade (Homère)
	•	eneide — L'Énéide (Virgile)
	•	metamorphoses — Les Métamorphoses (Ovide)
	•	nature-choses — De la nature des choses (Lucrèce)

Roman Wisdom (2):
	•	amitie — De l'amitié (Cicéron)
	•	vieillesse — De la vieillesse (Cicéron)

Persian & Eastern Poetry (2):
	•	rubaiyat — Les Rubáiyát (Omar Khayyám)
	•	masnavi — Le Masnavi (Rûmî)

Spiritual Classics (3):
	•	ecclesiaste — L'Ecclésiaste (Salomon)
	•	proverbes — Les Proverbes de Salomon
	•	imitation — L'Imitation de Jésus-Christ (Thomas a Kempis)

Examples

# Listen to Meditations while breathing
python stream_tone.py --freq 432 --audiobook meditations --audiobook-vol 0.40

# Audiobook only, no tone, with bilateral alternation
python stream_tone.py --audiobook bible --alternate --no-tone --disable-inputs

# Resume from where you left off
python stream_tone.py --audiobook meditations --audiobook-resume --no-tone

# Combine with claude-peace therapeutic affirmations
python stream_tone.py --freq 432 --claude-peace --audiobook meditations --no-tone

# Dense mode with bowl cue
python stream_tone.py --freq 432 --audiobook candide --dense --breath-cue bowl --disable-inputs

Progress & Resume

When using --audiobook-resume, the current sentence position is saved to books/.progress on Ctrl-C. Re-running with --audiobook-resume picks up exactly where you left off.

⸻

Safety Notes
	•	Always keep volume at a comfortable level.
	•	If you feel dizzy, anxious, or overloaded, stop the stream and rest.
	•	For trauma history or strong sensitivity, start with:

python stream_tone.py --freq 432 --hrv --hrv-style A

at low volume and gradually adjust.

This tool is here to help you take sound back as something that serves you, not something used against you.

⸻

 python stream_tone.py --claude-peace --peace-lang fr --breath-bar --disable-inputs --no-tone   

```
