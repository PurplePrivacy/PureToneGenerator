import numpy as np
import sounddevice as sd
import signal
import sys
import argparse

# ============================
# CONFIG
# ============================

# Argument parser
parser = argparse.ArgumentParser(description="Pure tone streaming generator")
parser.add_argument("--freq", type=float, default=528, help="Frequency in Hz (e.g., 432, 528, 639)")
args = parser.parse_args()

frequency = args.freq       # active frequency
sample_rate = 44100        # CD quality
amplitude = 0.25           # to avoid clipping
fade_seconds = 1           # duration of fade-in
channels = 2               # stereo identical

# ============================
# STOP HANDLER
# ============================

def handle_interrupt(sig, frame):
    print("\n🛑 Stopping cleanly...")
    sd.stop()
    sys.exit(0)

signal.signal(signal.SIGINT, handle_interrupt)

# ============================
# STREAM GENERATOR
# ============================

phase = 0.0
fade_samples = fade_seconds * sample_rate
current_sample = 0


def audio_callback(outdata, frames, time, status):
    global phase, current_sample

    t = (np.arange(frames) + phase) / sample_rate
    wave = amplitude * np.sin(2 * np.pi * frequency * t)

    # fade-in curve
    if current_sample < fade_samples:
        fade_factor = np.linspace(current_sample / fade_samples,
                                  (current_sample + frames) / fade_samples,
                                  frames)
        wave *= fade_factor

    current_sample += frames
    phase += frames

    stereo = np.column_stack([wave, wave])  # L == R identical
    outdata[:] = stereo


# ============================
# START STREAM
# ============================

print(f"🎧 Streaming real-time tone at {frequency} Hz (Ctrl-C to stop)")
print("Press Ctrl-C to stop.\n")

with sd.OutputStream(
    samplerate=sample_rate,
    channels=channels,
    callback=audio_callback,
    dtype="float32"
):
    signal.pause()  # wait forever until interrupted