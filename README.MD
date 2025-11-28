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

---

## Installation

From the project root:

```bash
python -m venv .venv
source .venv/bin/activate          # on macOS / Linux
# .venv\Scripts\activate           # on Windows (PowerShell or CMD)

pip install --upgrade pip
pip install numpy sounddevice soundfile
```

You may need to grant audio output permissions to your terminal / VS Code on macOS.

---

## CLI Options

```bash
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
```

### HRV Styles

- **A** – Symmetric breathing (**default**)  
  _In 5.5s / Out 5.5s_ → ~11s cycle (classic HRV coherence)

- **B** – Parasympathetic bias  
  _In 4s / Out 6.5s_ → longer exhales for deeper relaxation

- **C** – Deep meditative  
  _In 6s / Out 6s_ → very slow, suited for deep calm sessions

---

## Basic Usage

### 1. Simple pure tone

```bash
python stream_tone.py --freq 432
```

### 2. Isochronic focus tone

```bash
python stream_tone.py --freq 528 --iso --pulse 40
```

### 3. ABS Hemisphere Balancing

```bash
python stream_tone.py --freq 432 --abs --abs-speed medium
```

### 4. Iso + ABS combined

```bash
python stream_tone.py --freq 396 --iso --pulse 10 --abs --abs-speed slow
```

---

## HRV Breath Pacing

### Default HRV Mode (Style A)

```bash
python stream_tone.py --freq 432 --hrv
```

This applies a smooth 0.1 Hz–ish envelope (about 11 second cycles) to gently guide your breathing without thinking about it.

### Change HRV mode

```bash
# Parasympathetic bias (longer exhale)
python stream_tone.py --freq 432 --hrv --hrv-style B

# Deep meditative
python stream_tone.py --freq 528 --hrv --hrv-style C
```

### HRV + Iso + ABS

```bash
python stream_tone.py --freq 432 --hrv --iso --pulse 30 --abs --abs-speed slow
```

---

## Long-Term Silence Cultivation

The `--fade-long` flag smoothly fades the stream toward silence over ~30 minutes (1800 seconds).  
This is useful if you want to:

- train being at peace with silence  
- let the nervous system unhook slowly from sound  
- end a session gently without a hard stop

### Example

```bash
python stream_tone.py --freq 528 --hrv --hrv-style A --fade-long
```

You’ll feel the tone gradually recede while breath pacing remains coherent.

---

## Full Stack Mode

`--full` enables:

- Isochronic mode (`--iso`)
- ABS (`--abs`)
- HRV (`--hrv`)
- Long fade (`--fade-long`)

in a single flag.

### Example

```bash
python stream_tone.py --freq 528 --full
```

This is a very rich stimulation stack:
- breathing guided,
- hemispheres alternating,
- tone pulsed,
- slowly fading into silence.

---

## Personal Favorites

Some curated presets that feel especially good:

### 1. Deep Body Resonance + Iso + ABS  *(personal favorite)*

```bash
python stream_tone.py --freq 44 --iso --pulse 528 --abs --abs-speed medium
```

Very low carrier with a high-rate iso pulse & ABS – strong, physical, and intense.

---

### 2. HRV Breath Pacing + Iso + ABS

```bash
python stream_tone.py --freq 432 --hrv --iso --pulse 30 --abs --abs-speed slow
```

Great for calming the system while still feeling “awake.”

---

### 3. Silence Cultivation + Smooth HRV

```bash
python stream_tone.py --freq 528 --hrv --hrv-style A --fade-long
```

Starts as a clear, coherent tone and slowly dissolves into silence.  
Ideal for closing the day or decompressing after stress.

---

### 4. Full Stack Session

```bash
python stream_tone.py --freq 528 --full
```

Everything enabled:
- HRV breath pacing
- Isochronic pulsing
- ABS hemisphere alternation
- Long-term fade-out

Use at comfortable volumes and give yourself time to feel the shift.

---

## Saving a 1-Hour FLAC

To generate a 1-hour file you can loop later (e.g., on an offline player):

```bash
python stream_tone.py --freq 528 --iso --pulse 40 --abs --abs-speed medium --hrv --save-audio
```

This will create:

```text
528Hz_YYYYMMDD_HHMMSS.flac
```

in the current directory.

---

## Safety Notes

- Always keep volume at a **comfortable** level.
- If you feel dizzy, anxious, or overloaded, stop the stream and rest.
- For trauma history or strong sensitivity, start with:
  ```bash
  python stream_tone.py --freq 432 --hrv --hrv-style A
  ```
  at low volume and gradually adjust.

This tool is here to help you **take sound back** as something that serves you, not something used against you.

---