# Resonance — Windows Setup Guide

A step-by-step guide to get Resonance running on Windows. No programming experience needed.

---

## What You Need

- Windows 10 or 11
- An internet connection (for initial setup only — Resonance itself is 100% offline)
- Headphones recommended for bilateral stimulation modes

---

## Step 1: Install Python

1. Go to https://www.python.org/downloads/
2. Click the big **Download Python** button
3. Run the installer
4. **Important:** Check the box that says **"Add Python to PATH"** before clicking Install
5. Click **Install Now**

To verify, open **Command Prompt** (search for `cmd` in the Start menu) and type:

```
python --version
```

You should see `Python 3.x.x`.

---

## Step 2: Install Git

1. Go to https://git-scm.com/download/win
2. Download and run the installer
3. Accept all default options

---

## Step 3: Download Resonance

Open **Command Prompt** and type:

```
cd %USERPROFILE%\Desktop
git clone https://github.com/PurplePrivacy/PureToneGenerator.git
cd PureToneGenerator
```

This creates a `PureToneGenerator` folder on your Desktop.

---

## Step 4: Set Up the Environment

```
python -m venv .venv
.venv\Scripts\activate
pip install numpy sounddevice soundfile
```

If `sounddevice` fails to install, you may need to install the Microsoft Visual C++ Redistributable:
https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist

---

## Step 5: Run Resonance

**Try a simple session first:**

```
python stream_tone.py --peaceful-vibe
```

You should hear a calm tone with breathing pacing. Press **Ctrl+C** to stop.

**Try a preset for sleep:**

```
python stream_tone.py --sleep
```

**Try an audiobook:**

```
python books/fetch_books.py
python stream_tone.py --audiobook meditations
```

---

## Note on Voice Features

The therapeutic voice modes (`--phd-peace`, `--claude-peace`, `--restore-peace`) currently use macOS text-to-speech for voice rendering and are **not available on Windows**. All tone-based features (pure tones, HRV breathing, bilateral stimulation, isochronic modulation, breath cues, audiobooks, FLAC export) work fully on Windows.

Windows voice support is on the roadmap.

---

## Running Resonance Again Later

Every time you want to use Resonance:

1. Open **Command Prompt**
2. Type:

```
cd %USERPROFILE%\Desktop\PureToneGenerator
.venv\Scripts\activate
python stream_tone.py --peaceful-vibe
```

---

## Quick Preset Reference

| What you want | Command |
|---|---|
| Calm ambient tone | `python stream_tone.py --peaceful-vibe` |
| Deep focus / study | `python stream_tone.py --deep-focus` |
| Fall asleep | `python stream_tone.py --sleep` |
| Anxiety relief | `python stream_tone.py --anxiety-relief` |
| Morning energy | `python stream_tone.py --morning-energy` |
| Meditation | `python stream_tone.py --meditation` |
| Audiobook | `python stream_tone.py --audiobook meditations` |

See the full list of 20 presets with `python stream_tone.py --help`.

---

## Need Help?

If you get stuck at any step, you can paste the error message into any AI assistant (ChatGPT, Claude, Gemini) and ask for help. They can walk you through troubleshooting specific to your system.

You can also open an issue at: https://github.com/PurplePrivacy/PureToneGenerator/issues
