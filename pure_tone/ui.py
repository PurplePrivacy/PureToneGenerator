"""Terminal UI: breathing bar, status display, interrupt handler."""

import sys
import time
import sounddevice as sd

from .constants import (
    CLAUDE_PEACE_PHASE_NAMES, PHD_PEACE_EXTRA_PHASE_NAMES,
    AUDIOBOOK_PAGE_SIZE,
)
from .config import audiobook_save_progress


def handle_interrupt(sig, frame, g):
    """SIGINT handler — clean shutdown with audiobook progress save."""
    sys.stdout.write("\033[?25h")
    sys.stdout.flush()
    print("\nStopping cleanly...")
    if g.audiobook_mode:
        ab_page = g.audiobook_play_idx // AUDIOBOOK_PAGE_SIZE
        ab_total_pages = (len(g.audiobook_sentences) + AUDIOBOOK_PAGE_SIZE - 1) // AUDIOBOOK_PAGE_SIZE
        ab_lang_tag = "FR" if g.audiobook_sentences and g.audiobook_sentences[0][0] in ("Aurélie (Enhanced)", "Jacques") else "EN"
        print(f"  Audiobook: {g.audiobook_book_title} [{ab_lang_tag}] — stopped at page {ab_page}/{ab_total_pages}")
        if g.audiobook_resume:
            audiobook_save_progress(g.audiobook_progress_path, g.audiobook_name, g.audiobook_play_idx)
            print(f"  Progress saved. Resume with: --audiobook {g.audiobook_name} --audiobook-resume")
        else:
            print(f"  Resume with: --audiobook {g.audiobook_name} --audiobook-page {ab_page}")
    sd.stop()
    try:
        g.integrity_queue.put_nowait(None)
    except Exception:
        pass
    print("")
    sys.exit(0)


def breathing_bar_worker(g):
    """Terminal UI to visualize HRV breath pacing with ANSI colors."""
    if not g.hrv_mode:
        return

    bar_width = 28
    update_hz = 15.0
    sleep_s = 1.0 / update_hz

    blocks = " \u258f\u258e\u258d\u258c\u258b\u258a\u2589\u2588"

    DISPLAY_LABELS = {
        "INHALE": "BREATHE IN",
        "HOLD":   "HOLD",
        "EXHALE": "BREATHE OUT",
    }

    COLORS = {
        "INHALE": "\033[32m",
        "HOLD":   "\033[33m",
        "EXHALE": "\033[36m",
    }
    RESET = "\033[0m"

    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

    g.breath_bar_start_time = time.time()

    while True:
        pos_samples = int(g.hrv_phase) % g.hrv_cycle_samples
        phase_id = int(g.hrv_phase_id_table[pos_samples])
        phase_name = g.hrv_phase_names[phase_id]
        color = COLORS.get(phase_name, RESET)

        phase_start = g.hrv_phase_starts[phase_id]
        phase_len = g.hrv_phase_lengths[phase_id]
        frac = (pos_samples - phase_start) / phase_len if phase_len > 0 else 0.0

        if g.breath_bar_last_phase_id >= 0 and phase_id == 0 and g.breath_bar_last_phase_id != 0:
            g.breath_bar_cycle_count += 1
        g.breath_bar_last_phase_id = phase_id

        fill_exact = frac * bar_width
        full_blocks = int(fill_exact)
        remainder = fill_exact - full_blocks
        partial_idx = int(remainder * (len(blocks) - 1))
        bar = "\u2588" * full_blocks
        if full_blocks < bar_width:
            bar += blocks[partial_idx]
            bar += " " * (bar_width - full_blocks - 1)

        elapsed = time.time() - g.breath_bar_start_time
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)

        display_label = DISPLAY_LABELS.get(phase_name, phase_name)
        sys.stdout.write(f"\r{color}  {display_label:11s} |{bar}| {int(frac*100):3d}%{RESET}  {mins:02d}:{secs:02d} cycle #{g.breath_bar_cycle_count}   ")
        sys.stdout.flush()

        time.sleep(sleep_s)


def print_status(g):
    """Print startup status display."""
    if g.disable_inputs:
        print("Audio hardening: output-only stream (no input paths).")

    if g.pure_mode:
        print("Pure mode enabled: single sine wave, no modulation, no noise.")

    if g.lockdown_mode:
        print("LOCKDOWN active: pure + output-only + integrity proof.")

    if g.no_tone:
        print("Streaming in silent mode — voices and cues only (Ctrl-C to stop)")
    else:
        print(f"Streaming real-time tone at {g.frequency} Hz (Ctrl-C to stop)")
    print("Press Ctrl-C to stop.\n")
    print(f"Audio settings: latency={g.latency_mode}, blocksize={g.blocksize}\n")
    if g.hrv_mode:
        pattern_desc = " -> ".join(f"{name} {dur}s" for name, dur in g.hrv_pattern)
        print(f"HRV pattern ({g.hrv_style}): {pattern_desc} ({g.hrv_cycle_seconds}s cycle)\n")
    if g.breath_bar and g.hrv_mode:
        print("Breathing bar: enabled (HRV)\n")
    elif g.breath_bar and not g.hrv_mode:
        print("Breathing bar: requested, but HRV is disabled (no-op)\n")
    if g.hrv_mode and g.breath_cue != "none":
        print(f"Breath cue: {g.breath_cue} (vol={g.breath_cue_vol})\n")
    if g.restore_peace:
        lang_note = f" [{g.peace_lang.upper()}]" if g.peace_lang != "en" else ""
        print(f"Restore-peace: active (voice={g.peace_voice}, vol={g.peace_vol}){lang_note}")
        print(f"  {len(g.PEACE_MESSAGES)} affirmations, {len(set(g.PEACE_MESSAGES))} unique — rendering in background\n")
    if g.claude_peace:
        lang_note = f" [{g.peace_lang.upper()}]" if g.peace_lang != "en" else ""
        mode_label = "PhD-peace" if g.phd_peace else "Claude-peace"
        n_phases = 38 if g.phd_peace else 16
        print(f"{mode_label}: active (vol={g.claude_peace_vol}){lang_note}")
        print(f"  {len(g.CLAUDE_PEACE_MESSAGES)} affirmations across {n_phases} therapeutic phases")
        if g.peace_lang == "fr":
            print("  Language: French (Thomas 1-word + full sentences, Jacques 2-3 words)")
        else:
            print("  Voices: Daniel (GB), Ralph (US), Fred (US)")
        print("  Mixed depth: 1-word -> 2-3 words -> full sentence (targets subconscious)")
        phases = CLAUDE_PEACE_PHASE_NAMES + (PHD_PEACE_EXTRA_PHASE_NAMES if g.phd_peace else [])
        prefix = "  Progression: "
        indent = " " * len(prefix)
        for pi, pname in enumerate(phases):
            if pi == 0:
                sys.stdout.write(f"{prefix}{pname}")
            else:
                sys.stdout.write(f"\n{indent}-> {pname}")
        sys.stdout.write("\n")
        if g.dense_mode:
            dense_interval = g.hrv_cycle_seconds / len(g.hrv_pattern)
            print(f"  Dense: affirmation every phase transition (~{dense_interval:.1f}s instead of ~{g.hrv_cycle_seconds:.0f}s)")
        if g.alternate_mode:
            print("  Bilateral: voice messages alternate between L and R speakers")
        print()
    if g.alternate_mode and not (g.claude_peace or g.restore_peace or g.audiobook_mode):
        print("Note: --alternate has no effect without --claude-peace, --phd-peace, --restore-peace, or --audiobook\n")
    if g.audiobook_mode:
        ab_start = g.audiobook_play_idx
        est_min = (len(g.audiobook_sentences) - ab_start) * g.hrv_cycle_seconds / 60
        print(f"Audiobook: {g.audiobook_book_title}")
        print(f"  {len(g.audiobook_sentences)} sentences (voice: {g.ab_voice}, vol={g.audiobook_vol})")
        if ab_start > 0:
            print(f"  Resuming from sentence {ab_start}")
        print(f"  Estimated duration: ~{est_min:.0f} minutes")
        print(f"  Sentence gap: {g.audiobook_gap:.1f}s — Word gap: {g.audiobook_word_gap:.1f}s — Loop: {'on' if g.audiobook_loop else 'off'}")
        if g.alternate_mode:
            print("  Bilateral: sentences alternate between L and R speakers")
        print("  Rolling renderer: pre-renders ~10 sentences ahead")
        if g.audiobook_resume:
            print("  Progress will be saved on exit (Ctrl-C)")
        print()
