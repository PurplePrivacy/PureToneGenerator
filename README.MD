# PureTones – Real-Time Brainwave & Breath Tone Generator

PureTones is a small Python tool that generates **pure tones for focus, healing, breath regulation, and relaxation**.

It works entirely **offline**, generating audio mathematically in real time and sending it directly to your output device (e.g. AirPods Max).  
No files are streamed, no microphone is used, and nothing external is mixed in.

---

## Features

- 🔊 Real-time tone streaming (sine + gentle harmonics)
- 🎧 Stereo output (L = R or ABS alternation)
- 🧠 Isochronic modulation (`--iso --pulse`)
- 🧬 ABS – Alternating Bilateral Stimulation (`--abs`)
- 💓 HRV breathing pacing (`--hrv --hrv-style`)
- 🌫 Long-term fade-to-silence cultivation (`--fade-long`)
- 🧱 Full-stack preset (`--full`)
- 💾 Optional 1-hour **FLAC** export (`--save-audio`)
- 🛡 Pure safe mode (`--pure`)
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
--hrv-style STR      HRV pacing style: A | B | C (default: A)

--fade-long          Enable long-term fade-to-silence cultivation
--full               Enable full stack: HRV + ISO + ABS + long fade

--pure               Pure sine safe mode (no modulation)
--disable-inputs     Output-only hardening (no audio input paths)
--integrity          Print rolling SHA-256 of generated samples
--integrity-interval Seconds between integrity prints (default: 1.0)
--lockdown           Maximum safety preset: pure + disable-inputs + integrity


⸻

HRV Styles
	•	A – Symmetric breathing (default)
In 5.5s / Out 5.5s → ~11s cycle (classic HRV coherence)
	•	B – Parasympathetic bias
In 4s / Out 6.5s → longer exhales for deeper relaxation
	•	C – Deep meditative
In 6s / Out 6s → very slow, suited for deep calm sessions

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

Safety Notes
	•	Always keep volume at a comfortable level.
	•	If you feel dizzy, anxious, or overloaded, stop the stream and rest.
	•	For trauma history or strong sensitivity, start with:

python stream_tone.py --freq 432 --hrv --hrv-style A

at low volume and gradually adjust.

This tool is here to help you take sound back as something that serves you, not something used against you.

⸻


```
