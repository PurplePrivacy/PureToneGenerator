# Resonance — macOS Setup Guide

A step-by-step guide to get Resonance running on your Mac. No programming experience needed.

---

## What You Need

- A Mac running macOS 12 (Monterey) or later
- An internet connection (for initial setup only — Resonance itself is 100% offline)
- Headphones recommended for bilateral stimulation modes

---

## Step 1: Open Terminal

1. Press **Cmd + Space** to open Spotlight
2. Type **Terminal** and press Enter
3. A window with a command line will appear — this is where you'll type commands

---

## Step 2: Install Python

macOS may already have Python, but we need a recent version.

**Option A — Check if Python 3 is already installed:**

```bash
python3 --version
```

If you see `Python 3.x.x` (3.10 or higher), skip to Step 3.

**Option B — Install Python via Homebrew:**

If you don't have Python 3, install Homebrew first (a package manager for macOS):

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Then install Python:

```bash
brew install python
```

---

## Step 3: Download Resonance

```bash
cd ~/Desktop
git clone https://github.com/PurplePrivacy/PureToneGenerator.git
cd PureToneGenerator
```

This creates a `PureToneGenerator` folder on your Desktop.

---

## Step 4: Set Up the Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install numpy sounddevice soundfile
```

---

## Step 5: Install Voices (for therapeutic modes)

```bash
chmod +x setup_voices.sh
./setup_voices.sh
```

If any voices are missing, the script will tell you how to install them:
1. Open **System Settings**
2. Go to **Accessibility > Spoken Content > System Voice > Manage Voices**
3. Download the listed voices (Alex, Thomas, Daniel, Samantha)

---

## Step 6: Run Resonance

**Try a simple session first:**

```bash
python stream_tone.py --peaceful-vibe
```

You should hear a calm tone with breathing pacing. Press **Ctrl+C** to stop.

**Try a therapeutic session:**

```bash
python stream_tone.py --phd-peace --alternate --no-tone --disable-inputs
```

**Try an audiobook:**

```bash
python books/fetch_books.py          # Download library (run once)
python stream_tone.py --audiobook meditations
```

---

## Running Resonance Again Later

Every time you want to use Resonance:

```bash
cd ~/Desktop/PureToneGenerator
source .venv/bin/activate
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
| Full therapeutic EMDR | `python stream_tone.py --emdr-session` |
| Audiobook | `python stream_tone.py --audiobook meditations` |

See the full list of 20 presets with `python stream_tone.py --help`.

---

## Need Help?

If you get stuck at any step, you can paste the error message into any AI assistant (ChatGPT, Claude, Gemini) and ask for help. They can walk you through troubleshooting specific to your system.

You can also open an issue at: https://github.com/PurplePrivacy/PureToneGenerator/issues
