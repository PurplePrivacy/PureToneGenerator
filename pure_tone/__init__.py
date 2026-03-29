"""Resonance — Therapeutic Audio Engine.

pure_tone package: modularized from stream_tone.py.
"""

import signal
import threading
import sounddevice as sd

from . import cli, config, cues, tts, callback, ui


def main():
    """Entry point for the Resonance audio engine."""
    args = cli.build_parser().parse_args()
    cli.apply_presets(args)

    # Early exit: audiobook catalog display
    if args.audiobook_list:
        config.show_audiobook_list()
        return

    # Early exit: mindfulness meditation catalog display
    if args.mindfulness_list:
        config.show_mindfulness_list()
        return

    # Initialize config + state
    g = config.init(args)

    # Early exit: save FLAC file
    if g.save_audio:
        config.save_audio_file(g)
        return

    # Build cue waveforms
    cues.build_cues(g)

    # Start renderer threads
    if g.claude_peace or g.restore_peace:
        t = threading.Thread(target=tts.unified_renderer_thread, args=(g,), daemon=True)
        t.start()

    if g.audiobook_mode:
        t = threading.Thread(target=tts.audiobook_renderer_thread, args=(g,), daemon=True)
        t.start()

    # Start integrity worker
    if g.integrity_mode:
        t = threading.Thread(target=callback.integrity_worker, args=(g,), daemon=True)
        t.start()

    # Audio hardening / mode messages + status display
    ui.print_status(g)

    # Setup interrupt handler
    signal.signal(signal.SIGINT, lambda sig, frame: ui.handle_interrupt(sig, frame, g))

    # Start breathing bar AFTER all print output
    if g.breath_bar and g.hrv_mode:
        t = threading.Thread(target=ui.breathing_bar_worker, args=(g,), daemon=True)
        t.start()

    # Create callback and start stream
    cb = callback.make_callback(g)

    with sd.OutputStream(
        samplerate=g.sample_rate,
        channels=g.channels,
        callback=cb,
        dtype="float32",
        blocksize=g.blocksize,
        latency=g.latency_mode,
    ):
        threading.Event().wait()
