import numpy as np
import sounddevice as sd
import signal
import sys
import argparse
import soundfile as sf
import datetime

# ============================
# CONFIG
# ============================

# Argument parser
parser = argparse.ArgumentParser(description="Pure tone streaming generator")
parser.add_argument("--freq", type=float, default=528, help="Frequency in Hz (e.g., 432, 528, 639)")
parser.add_argument("--save-audio", action="store_true", help="Save 1 hour WAV file instead of realtime streaming")
parser.add_argument("--iso", action="store_true", help="Enable isochronic mode (volume pulse)")
parser.add_argument("--pulse", type=float, default=40, help="Isochronic pulse frequency in Hz")
args = parser.parse_args()

frequency = args.freq       # active frequency
save_audio = args.save_audio
iso_mode = args.iso
pulse_freq = args.pulse
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
    if iso_mode:
        pulse = 0.5 * (1 + np.sin(2 * np.pi * pulse_freq * t))
        wave *= pulse

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