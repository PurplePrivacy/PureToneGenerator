"""Audio callback and integrity worker."""

import os
import hashlib
import numpy as np
from queue import Full

from .constants import (
    OUTPUT_GAIN, VOICE_DUCK_FACTOR, SOFT_THRESHOLD, SOFT_HEADROOM,
    AUDIOBOOK_PAGE_SIZE,
)
from .cues import select_cue


def integrity_worker(g):
    """Consumes audio chunks and prints a rolling SHA-256 digest."""
    hasher = hashlib.sha256()
    counter = 0
    while True:
        item = g.integrity_queue.get()
        if item is None:
            break
        hasher.update(item)
        counter += 1
        digest = hasher.hexdigest()[:16]
        print(f"[integrity] rolling_sha256={digest} chunks={counter}")


def make_callback(g):
    """Create and return the audio_callback closure over g."""

    def audio_callback(outdata, frames, time, status):
        t = (np.arange(frames) + g.phase) / g.sample_rate
        wave = g.amplitude * np.sin(2 * np.pi * g.frequency * t)
        if g.iso_mode:
            pulse = 0.5 * (1 + np.sin(2 * np.pi * g.pulse_freq * t))
            wave *= pulse

        # HRV breath pacing
        if g.hrv_mode:
            idx = (np.arange(frames, dtype=np.int64) + g.hrv_phase) % g.hrv_cycle_samples
            hrv_env = g.hrv_env_table[idx]
            wave *= hrv_env

            current_phase_id = g.hrv_phase_id_table[int(idx[-1])]
            current_phase_name = g.hrv_phase_names[current_phase_id]

            if g.hrv_last_phase_name is None:
                g.hrv_last_phase_name = current_phase_name
            elif current_phase_name != g.hrv_last_phase_name:
                # Breath cue on every phase transition
                if g.breath_cue != "none":
                    cue = select_cue(g, current_phase_name)
                    if cue is not None:
                        if g.cue_buf is not None and g.cue_pos < len(g.cue_buf):
                            xf = min(int(0.005 * g.sample_rate), len(g.cue_buf) - g.cue_pos)
                            if xf > 1:
                                g.cue_buf[g.cue_pos:g.cue_pos + xf] *= np.linspace(1, 0, xf).astype(np.float32)
                        g.cue_buf = cue.copy()
                        g.cue_pos = 0

                # Peace affirmation trigger
                peace_trigger = current_phase_name == g.hrv_phase_names[0] or g.dense_mode
                if g.restore_peace and peace_trigger and g.peace_message_order:
                    msg_idx = g.peace_message_order[g.peace_cycle_count % len(g.peace_message_order)]
                    msg_text = g.PEACE_MESSAGES[msg_idx]
                    if msg_text in g.peace_rendered:
                        g.peace_cue_buf = g.peace_rendered[msg_text]
                        g.peace_cue_pos = 0
                    if g.alternate_mode:
                        g.peace_alt_left = (g.peace_cycle_count % 2 == 0)
                    peace_side = "L" if g.alternate_mode and g.peace_alt_left else "R" if g.alternate_mode else ""
                    peace_side_tag = f" [{peace_side}]" if peace_side else ""
                    try:
                        os.write(2, f"\n  ~ {msg_text}{peace_side_tag}\n".encode())
                    except Exception:
                        pass
                    g.peace_cycle_count += 1

                # Claude-peace trigger — two modes:
                # PHD-peace: sample-counter with progressive deepening gaps + exhale alignment
                # Regular claude-peace: phase-transition trigger (original behavior)
                if g.claude_peace and g.claude_gap_schedule:
                    # PHD-peace: handled below via sample counter (not phase transition)
                    pass
                elif g.claude_peace:
                    claude_trigger = current_phase_name == g.hrv_phase_names[0] or g.dense_mode
                    if claude_trigger:
                        _fire_claude_message(g)
                g.hrv_last_phase_name = current_phase_name

            g.hrv_phase += frames

        # PHD-peace / full-hypnosis / accelerated: sample-counter trigger with exhale alignment
        if g.claude_peace and g.claude_gap_schedule:
            ci = g.claude_cycle_count % len(g.CLAUDE_PEACE_MESSAGES)
            if ci in g.claude_rendered and g.current_sample >= g.claude_next_trigger_sample:
                # Full-hypnosis: reshuffle when all messages have been played
                if g.full_hypnosis and g.claude_cycle_count > 0 and ci == 0:
                    from .config import reshuffle_full_hypnosis
                    reshuffle_full_hypnosis(g)
                    try:
                        os.write(2, "\n  === FULL HYPNOSIS: all sections complete \u2014 reshuffling ===\n\n".encode())
                    except Exception:
                        pass
                _fire_claude_message(g)
                # Compute next trigger time using gap schedule
                ci = g.claude_cycle_count  # already incremented by _fire
                n_msgs = len(g.CLAUDE_PEACE_MESSAGES)
                if ci < n_msgs or g.full_hypnosis:
                    sched_idx = min(ci, len(g.claude_gap_schedule) - 1)
                    gap_cycles, jitter_max = g.claude_gap_schedule[sched_idx]
                    jitter = g.claude_gap_rng.random() * jitter_max
                    total_cycles = gap_cycles + jitter
                    gap_samples = int(total_cycles * g.hrv_cycle_samples)
                    # Align to next exhale phase + delay
                    g.claude_next_trigger_sample = g.current_sample + gap_samples + g.claude_exhale_delay_samples

        # Audiobook: trigger next sentence after inter-sentence gap elapses
        if g.audiobook_mode and g.audiobook_cue_buf is None and g.audiobook_gap_remaining > 0:
            g.audiobook_gap_remaining -= frames
        if g.audiobook_mode and g.audiobook_cue_buf is None and g.audiobook_gap_remaining <= 0:
            while (g.audiobook_play_idx not in g.audiobook_rendered
                   and g.audiobook_play_idx < g.audiobook_next_render):
                g.audiobook_play_idx += 1
        if (g.audiobook_mode and g.audiobook_cue_buf is None
                and g.audiobook_gap_remaining <= 0
                and g.audiobook_play_idx in g.audiobook_rendered):
            g.audiobook_cue_buf = g.audiobook_rendered[g.audiobook_play_idx]
            g.audiobook_cue_pos = 0
            if g.alternate_mode:
                g.audiobook_alt_left = (g.audiobook_play_idx % 2 == 0)
            g.audiobook_play_idx += 1
            ab_sent_idx = g.audiobook_play_idx - 1
            try:
                _, ab_sent_text = g.audiobook_sentences[ab_sent_idx]
                ab_display = ab_sent_text[:120] + ("..." if len(ab_sent_text) > 120 else "")
                os.write(2, f"\n  > {ab_display}\n".encode())
            except Exception:
                pass
            ab_page = (g.audiobook_play_idx - 1) // AUDIOBOOK_PAGE_SIZE
            if ab_page != g.audiobook_last_page_logged and g.audiobook_play_idx % AUDIOBOOK_PAGE_SIZE == 0:
                g.audiobook_last_page_logged = ab_page
                ab_total_pages = (len(g.audiobook_sentences) + AUDIOBOOK_PAGE_SIZE - 1) // AUDIOBOOK_PAGE_SIZE
                ab_lang_tag = "FR" if g.audiobook_sentences[0][0] in ("Aurélie (Enhanced)", "Jacques") else "EN"
                try:
                    os.write(2, f"\n  [{g.audiobook_book_title}] [{ab_lang_tag}] page {ab_page + 1}/{ab_total_pages}\n".encode())
                except Exception:
                    pass

        # Audiobook loop
        if (g.audiobook_mode and g.audiobook_loop and g.audiobook_cue_buf is None
                and g.audiobook_gap_remaining <= 0 and g.audiobook_done
                and g.audiobook_play_idx >= len(g.audiobook_sentences)):
            g.audiobook_loop_count += 1
            g.audiobook_play_idx = 0
            g.audiobook_next_render = 0
            g.audiobook_done = False
            g.audiobook_last_page_logged = -1
            g.audiobook_gap_remaining = int(5.0 * g.sample_rate)
            try:
                os.write(2, (
                    f"\n\n  {'=' * 56}\n"
                    f"  ||  AUDIOBOOK COMPLETE  —  Loop {g.audiobook_loop_count}\n"
                    f"  ||  \"{g.audiobook_book_title}\"  —  restarting from beginning\n"
                    f"  {'=' * 56}\n\n"
                ).encode())
            except Exception:
                pass

        # Fade-in
        if g.current_sample < g.fade_samples:
            fade_factor = np.linspace(g.current_sample / g.fade_samples,
                                      (g.current_sample + frames) / g.fade_samples,
                                      frames)
            wave *= fade_factor

        # Long fade-to-silence
        if g.fade_long:
            elapsed_seconds = g.current_sample / g.sample_rate
            if elapsed_seconds < g.long_fade_seconds:
                long_factor = 1.0 - (elapsed_seconds / g.long_fade_seconds)
            else:
                long_factor = 0.0
            wave *= long_factor

        g.current_sample += frames
        g.phase += frames

        # Integrity
        if g.integrity_mode:
            now_sec = g.current_sample / g.sample_rate
            if (now_sec - g.integrity_last_emit) >= g.integrity_interval:
                g.integrity_last_emit = now_sec
                try:
                    chunk_bytes = np.asarray(wave, dtype=np.float32).tobytes()
                    g.integrity_queue.put_nowait(chunk_bytes)
                except Full:
                    pass
                except Exception:
                    pass

        gain = OUTPUT_GAIN
        # Duck tone when voices are active
        n_voices = ((g.peace_cue_buf is not None)
                    + (g.claude_cue_buf is not None)
                    + (g.audiobook_cue_buf is not None))
        if n_voices:
            gain *= (1.0 - VOICE_DUCK_FACTOR * n_voices)

        if g.abs_mode:
            left_env = 0.2 + 0.8 * 0.5 * (1 + np.sin(2 * np.pi * g.abs_rate * t))
            right_env = 0.2 + 0.8 * 0.5 * (1 - np.sin(2 * np.pi * g.abs_rate * t))
            left_wave = wave * left_env * gain
            right_wave = wave * right_env * gain
            outdata[:] = np.column_stack([left_wave, right_wave])
        else:
            outdata[:] = np.column_stack([wave * gain, wave * gain])

        # Mix cues AFTER gain
        if g.cue_buf is not None:
            remaining = len(g.cue_buf) - g.cue_pos
            L = min(frames, remaining)
            cue_mono = g.cue_buf[g.cue_pos:g.cue_pos + L] * g.breath_cue_vol
            outdata[:L, 0] += cue_mono
            outdata[:L, 1] += cue_mono
            g.cue_pos += L
            if g.cue_pos >= len(g.cue_buf):
                g.cue_buf = None
                g.cue_pos = 0

        # Mix peace voice
        _mix_voice(outdata, frames, g, 'peace_cue_buf', 'peace_cue_pos',
                   g.peace_vol, g.alternate_mode, 'peace_alt_left')

        # Mix claude-peace voice
        _mix_voice(outdata, frames, g, 'claude_cue_buf', 'claude_cue_pos',
                   g.claude_peace_vol, g.alternate_mode, 'claude_alt_left')

        # Mix audiobook voice
        _mix_voice_audiobook(outdata, frames, g)

        # Soft limiter
        abs_out = np.abs(outdata)
        over = abs_out - SOFT_THRESHOLD
        compressed = SOFT_THRESHOLD + SOFT_HEADROOM * np.tanh(over / SOFT_HEADROOM)
        outdata[:] = np.where(abs_out > SOFT_THRESHOLD,
                              np.sign(outdata) * compressed, outdata)

    return audio_callback


def _fire_claude_message(g):
    """Load the next claude-peace message into the playback buffer."""
    ci = g.claude_cycle_count % len(g.CLAUDE_PEACE_MESSAGES)
    if ci in g.claude_rendered:
        g.claude_cue_buf = g.claude_rendered[ci]
        g.claude_cue_pos = 0
    if g.alternate_mode:
        g.claude_alt_left = (g.claude_cycle_count % 2 == 0)
    cv, ct = g.CLAUDE_PEACE_MESSAGES[ci]
    claude_side = "L" if g.alternate_mode and g.claude_alt_left else "R" if g.alternate_mode else ""
    claude_side_tag = f" [{claude_side}]" if claude_side else ""
    try:
        os.write(2, f"\n  ~ [{cv}] {ct}{claude_side_tag}\n".encode())
    except Exception:
        pass
    g.claude_cycle_count += 1


def _mix_voice(outdata, frames, g, buf_attr, pos_attr, vol, alternate, alt_attr):
    """Mix a voice layer into outdata. Shared helper for peace/claude voices."""
    buf = getattr(g, buf_attr)
    if buf is None:
        return
    pos = getattr(g, pos_attr)
    remaining = len(buf) - pos
    L = min(frames, remaining)
    mono = buf[pos:pos + L] * vol
    if alternate:
        if getattr(g, alt_attr):
            outdata[:L, 0] += mono
        else:
            outdata[:L, 1] += mono
    else:
        outdata[:L, 0] += mono
        outdata[:L, 1] += mono
    pos += L
    if pos >= len(buf):
        setattr(g, buf_attr, None)
        setattr(g, pos_attr, 0)
    else:
        setattr(g, pos_attr, pos)


def _mix_voice_audiobook(outdata, frames, g):
    """Mix audiobook voice into outdata and handle gap timing."""
    if g.audiobook_cue_buf is None:
        return
    remaining = len(g.audiobook_cue_buf) - g.audiobook_cue_pos
    L = min(frames, remaining)
    mono = g.audiobook_cue_buf[g.audiobook_cue_pos:g.audiobook_cue_pos + L] * g.audiobook_vol
    if g.alternate_mode:
        if g.audiobook_alt_left:
            outdata[:L, 0] += mono
        else:
            outdata[:L, 1] += mono
    else:
        outdata[:L, 0] += mono
        outdata[:L, 1] += mono
    g.audiobook_cue_pos += L
    if g.audiobook_cue_pos >= len(g.audiobook_cue_buf):
        g.audiobook_cue_buf = None
        g.audiobook_cue_pos = 0
        g.audiobook_gap_remaining = int(g.audiobook_gap * g.sample_rate)
