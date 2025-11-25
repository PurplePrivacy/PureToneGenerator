import argparse
import numpy as np
import sounddevice as sd
import sys
import soundfile as sf
import datetime

parser = argparse.ArgumentParser(description="Stream a pure tone to the audio output.")
parser.add_argument("--freq", type=float, default=528, help="Frequency of the tone in Hz")
parser.add_argument("--save-audio", action="store_true", help="Save 1 hour WAV file instead of realtime streaming")
parser.add_argument("--iso", action="store_true", help="Enable isochronic mode (volume pulse)")
parser.add_argument("--pulse", type=float, default=40, help="Isochronic pulse frequency in Hz")
args = parser.parse_args()

frequency = args.freq
save_audio = args.save_audio
iso_mode = args.iso
pulse_freq = args.pulse

sample_rate = 44100
amplitude = 0.1
fade_seconds = 0.05

# If saving audio instead of streaming
if save_audio:
    print(f"💾 Saving 1-hour WAV at {frequency} Hz...")

    duration_seconds = 3600  # 1 hour
    total_samples = int(sample_rate * duration_seconds)
    t = np.linspace(0, duration_seconds, total_samples, endpoint=False)
    wave = amplitude * np.sin(2 * np.pi * frequency * t)
    if iso_mode:
        pulse_wave = 0.5 * (1 + np.sin(2 * np.pi * pulse_freq * t))
        wave *= pulse_wave

    # apply fade in/out
    fade_samples = int(fade_seconds * sample_rate)
    fade_in_curve = np.linspace(0.0, 1.0, fade_samples)
    fade_out_curve = np.linspace(1.0, 0.0, fade_samples)
    wave[:fade_samples] *= fade_in_curve
    wave[-fade_samples:] *= fade_out_curve

    stereo = np.column_stack([wave, wave])  # L == R

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{int(frequency)}Hz_{timestamp}.flac"

    sf.write(filename, stereo, sample_rate, format="FLAC")
    print(f"✔ Saved {filename}")
    sys.exit(0)

print(f"🎧 Streaming real-time tone at {frequency} Hz (Ctrl-C to stop)")

def callback(outdata, frames, time, status):
    t = (callback.t0 + np.arange(frames)) / sample_rate
    wave = amplitude * np.sin(2 * np.pi * frequency * t)
    if iso_mode:
        pulse = 0.5 * (1 + np.sin(2 * np.pi * pulse_freq * ((np.arange(frames) + callback.t0) / sample_rate)))
        wave *= pulse
    outdata[:] = np.column_stack([wave, wave])
    callback.t0 += frames
callback.t0 = 0

try:
    with sd.OutputStream(channels=2, callback=callback, samplerate=sample_rate):
        while True:
            sd.sleep(1000)
except KeyboardInterrupt:
    print("\nStopped by user")
# PureTones – Real-Time & Isochronic Tone Generator

This project provides a **pure tone generator** that can:

- Stream mathematically clean sine waves in real time
- Optionally apply **isochronic modulation** (volume pulses) for brainwave entrainment
- Save **1-hour stereo FLAC** tracks that you can loop in any player

The core script is: `stream_tone.py`.

---

## Features

- 🎧 **Real-time streaming** to your audio output (no files required)
- 🧠 **Isochronic mode**: pulsed volume modulation at a chosen frequency
- 💾 **1-hour FLAC export** via `--save-audio`
- 🎚 **Stereo identical channels** (L = R) for a stable sound field
- 🌊 Soft fade-in on streaming and fade-in/out on saved tracks

---

## Requirements

Create and activate a virtual environment, then install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install numpy sounddevice soundfile
```

If you already have a `requirements.txt`, you can also run:

```bash
pip install -r requirements.txt
```

---

## Basic Usage

From the project directory (with venv activated):

```bash
python stream_tone.py --freq 528
```

This will:

- Stream a **pure 528 Hz** sine wave
- Use **stereo identical output** (L = R)
- Apply a short fade-in to avoid clicks at the start

Press `Ctrl-C` to stop streaming.

---

## CLI Options

`stream_tone.py` supports the following flags:

```bash
--freq FLOAT      Frequency in Hz (e.g., 432, 528, 639)
--save-audio      Save a 1-hour FLAC file instead of real-time streaming
--iso             Enable isochronic mode (volume pulse modulation)
--pulse FLOAT     Isochronic pulse frequency in Hz (default: 40)
--abs             Enable alternating bilateral stimulation (ABS)
--abs-speed STR   ABS speed: slow | medium | fast (default: medium)
```

### 2b. Alternating Bilateral Stimulation

```bash
python stream_tone.py --freq 528 --abs
```

Medium ABS (1.5 Hz) is default.
Slow example:

```bash
python stream_tone.py --freq 528 --abs --abs-speed slow
```

### Examples

### 1. Pure Tone Streaming

```bash
python stream_tone.py --freq 432
```

### 2. Isochronic Streaming (Gamma-like, 40 Hz)

```bash
python stream_tone.py --freq 528 --iso --pulse 40
```

This will:

- Generate a 528 Hz carrier tone
- Modulate its volume at 40 Hz (isochronic pulses)
- Stream the result to your audio output in real time

### 3. Save 1-Hour FLAC (Pure Tone)

```bash
python stream_tone.py --freq 528 --save-audio
```

This will create a FLAC file in the current directory:

```text
528Hz_YYYYMMDD_HHMMSS.flac
```

(Example: `528Hz_20250311_221145.flac`)

### 4. Save 1-Hour FLAC (Isochronic)

```bash
python stream_tone.py --freq 528 --iso --pulse 40 --save-audio
```

This will generate a **1-hour stereo isochronic track** (528 Hz carrier, 40 Hz pulses) and save it as FLAC.

---

## Suggested Frequencies

Some commonly used pure-tone frequencies (for convenience only):

| Frequency | Label          | Common Intent (non-medical)        |
|----------:|----------------|-------------------------------------|
|  396 Hz   | Release fear   | Emotional grounding                 |
|  417 Hz   | Change         | Clearing emotional blocks           |
|  432 Hz   | Harmony        | Focus, natural resonance            |
|  528 Hz   | Transformation | “Love” / heart-centered clarity        |
|  639 Hz   | Connection     | Relationships, empathy, joy         |
|  741 Hz   | Clarity        | Intuition, mental clarity           |
|  852 Hz   | Insight        | Inner peace, spiritual awareness    |

> These associations are **experiential / traditional**, not medical claims.

---

## Tips for Listening

- For **highest purity**, prefer **wired headphones** or good speakers.
- Bluetooth (especially AirPods) may introduce artifacts with pure continuous tones; 
  isochronic mode (`--iso`) usually survives better over Bluetooth than a static sine wave.
- Start with moderate volume and adjust gradually.
- For focus: try `--freq 432` or `--freq 528 --iso --pulse 40`.
- For calm: try `--freq 432 --iso --pulse 10`.

---

## Safety Note

This tool is for **relaxation, focus, and experimentation** only. It is **not** a medical device and should not be used as a substitute for professional care. If you experience discomfort, stop listening and lower volume, change frequency, or discontinue use.

---

## License / Attribution

Use and modify this script for your own personal audio experiments. If you integrate it into a larger project, a small attribution like `"Based on PureTones generator"` is appreciated.

### Combined Isochronic + ABS

```bash
python stream_tone.py --freq 528 --iso --pulse 40 --abs --abs-speed medium
```