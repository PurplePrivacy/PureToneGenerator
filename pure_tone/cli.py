"""Argument parsing and preset overrides."""

import argparse


def build_parser():
    """Build and return the argparse parser with all ~90 flags."""
    parser = argparse.ArgumentParser(description="Resonance — Therapeutic Audio Engine")
    parser.add_argument("--freq", type=float, default=528, help="Frequency in Hz (e.g., 432, 528, 639)")
    parser.add_argument("--save-audio", action="store_true", help="Save 1 hour FLAC file instead of realtime streaming")
    parser.add_argument("--iso", action="store_true", help="Enable isochronic mode (volume pulse)")
    parser.add_argument("--pulse", type=float, default=40, help="Isochronic pulse frequency in Hz")
    parser.add_argument("--abs", action="store_true", help="Enable alternating bilateral stimulation")
    parser.add_argument("--abs-speed", type=str, default="medium", choices=["slow", "medium", "fast"], help="ABS speed: slow, medium, fast")
    parser.add_argument("--hrv", action="store_true", help="Enable HRV (Heart-Rate Variability) breath pacing")
    parser.add_argument("--hrv-style", type=str, default="A",
                        choices=["A", "B", "C", "box", "478", "426"],
                        help="HRV pacing style: A (5-5) | B (4-6.5) | C (6-6) | box (4-4-4-4) | 478 (4-7-8) | 426 (4-2-6)")
    parser.add_argument("--fade-long", action="store_true", help="Enable long-term fade-to-silence cultivation (~30min)")
    parser.add_argument("--full", action="store_true", help="Enable full stack: HRV + ISO + ABS + long fade")
    parser.add_argument("--integrity", action="store_true", help="Print a rolling SHA-256 hash of the internally generated audio stream (proof-of-generation)")
    parser.add_argument("--integrity-interval", type=float, default=1.0, help="Seconds between integrity hash updates (default: 1.0)")
    parser.add_argument("--disable-inputs", action="store_true",
                        help="Force output-only operation (no audio input paths)")
    parser.add_argument("--pure", action="store_true",
                        help="Pure sine safe mode (no modulation, no noise, no bursts)")
    parser.add_argument("--no-tone", action="store_true",
                        help="Silence the base tone (voice messages and cues still play)")
    parser.add_argument("--lockdown", action="store_true",
                        help="Maximum safety preset: pure + disable-inputs + integrity")
    parser.add_argument("--latency", type=str, default="high", choices=["low", "high"],
                        help="Audio latency mode (default: high). Use high to reduce crackling.")
    parser.add_argument("--blocksize", type=int, default=1024,
                        help="Audio blocksize in frames (default: 1024). Increase to reduce crackling.")
    parser.add_argument("--breath-bar", action="store_true",
                        help="Show a live breathing bar in the terminal (HRV mode only)")
    parser.add_argument(
        "--breath-cue",
        type=str,
        default="none",
        choices=["none", "bell", "drum", "tick", "waterdrop", "woodblock", "bowl", "whoosh", "doubletick", "voice"],
        help="Play a cue at HRV inhale/exhale transitions: none|bell|drum|tick|waterdrop|woodblock|bowl|whoosh|doubletick|voice (default: none)",
    )
    parser.add_argument("--breath-cue-vol", type=float, default=0.25,
                        help="Breath cue volume multiplier (default: 0.25)")
    parser.add_argument("--restore-peace", action="store_true",
                        help="Counter-conditioning voice affirmations during HRV breathing (auto-enables HRV)")
    parser.add_argument("--peace-voice", type=str, default="Daniel",
                        help="macOS voice for --restore-peace affirmations (default: Daniel)")
    parser.add_argument("--peace-vol", type=float, default=0.35,
                        help="Volume multiplier for --restore-peace voice (default: 0.35)")
    parser.add_argument("--claude-peace", action="store_true",
                        help="Clinically-structured counter-conditioning: restores automatic breathing, "
                             "jaw release, posture, nasal breathing, thinking, confidence, sound safety "
                             "(auto-enables HRV + breath-bar)")
    parser.add_argument("--claude-peace-vol", type=float, default=0.35,
                        help="Volume for --claude-peace voice affirmations (default: 0.35)")
    parser.add_argument("--phd-peace", action="store_true",
                        help="Expert-reviewed 49-phase counter-conditioning: 16 claude-peace phases "
                             "plus 33 extended rounds (body purification, ego-strengthening, identity reclamation)")
    parser.add_argument("--phd-peace-vol", type=float, default=0.35,
                        help="Volume for --phd-peace voice affirmations (default: 0.35)")
    parser.add_argument("--ego-boost", action="store_true",
                        help="Dithyrambic ego-strengthening: 25 rounds of epic French compliments "
                             "celebrating beauty, intelligence, virtue, strength, charisma — "
                             "single Aurélie voice, same hypnotic timing as PHD-peace")
    parser.add_argument("--ego-boost-vol", type=float, default=0.35,
                        help="Volume for --ego-boost voice affirmations (default: 0.35)")
    parser.add_argument("--full-hypnosis", action="store_true",
                        help="Combined PHD-peace + ego-boost + body purification sections, "
                             "randomized section order (resets when all sections played)")
    parser.add_argument("--full-hypnosis-vol", type=float, default=0.35,
                        help="Volume for --full-hypnosis voice affirmations (default: 0.35)")
    parser.add_argument("--alternate", action="store_true",
                        help="Alternate voice messages between left and right speakers (EMDR-style bilateral)")
    parser.add_argument("--dense", action="store_true",
                        help="Play affirmations on every breath phase transition (~5.5s) instead of every full cycle (~11s)")
    parser.add_argument("--accelerated", action="store_true",
                        help="Rapid-fire affirmations with random intervals (~2-4s) — faster than --dense")
    parser.add_argument("--peace-lang", type=str, default="en", choices=["en", "fr"],
                        help="Language for peace affirmations: en | fr (default: en)")
    parser.add_argument("--audiobook", type=str, default=None, metavar="BOOK",
                        help="Read a book aloud with Aurélie (Enhanced) voice during HRV breathing "
                             "(e.g., --audiobook meditations). Use --audiobook-list to see available books.")
    parser.add_argument("--audiobook-list", action="store_true",
                        help="List all available audiobooks and exit")
    parser.add_argument("--audiobook-vol", type=float, default=0.40,
                        help="Audiobook voice volume (default: 0.40)")
    parser.add_argument("--audiobook-resume", action="store_true",
                        help="Resume from where you left off (saves progress to books/.progress)")
    parser.add_argument("--audiobook-page", type=int, default=None, metavar="N",
                        help="Start audiobook from page N (each page = ~10 sentences)")
    parser.add_argument("--audiobook-gap", type=float, default=2.0, metavar="SEC",
                        help="Silence gap between audiobook sentences in seconds (default: 2.0)")
    parser.add_argument("--audiobook-word-gap", type=float, default=1.5, metavar="MULT",
                        help="Extend natural TTS pauses by this multiplier (default: 1.5, 0=disabled)")
    parser.add_argument("--no-audiobook-loop", action="store_true",
                        help="Disable audiobook looping (by default, the book replays when finished)")
    parser.add_argument("--no-audiobook-gaps", action="store_true",
                        help="Disable intra-sentence pauses (keeps inter-sentence gap only, for debugging)")
    parser.add_argument("--audiobook-voice", type=str, default=None, metavar="VOICE",
                        help="Override audiobook voice (e.g., Tom, Samantha, Daniel, Alex)")
    parser.add_argument("--audiobook-rate", type=int, default=None, metavar="WPM",
                        help="Override audiobook speech rate in words-per-minute (default: 135)")
    parser.add_argument("--rhythm", action="store_true", default=True,
                        help="Enhance audiobook pacing — extends natural TTS pauses for a deliberate reading feel (default: on)")
    parser.add_argument("--no-rhythm", action="store_true",
                        help="Disable reading rhythm — use raw TTS pacing with no pause extension")
    parser.add_argument("--flat-read", action="store_true",
                        help="Use the legacy flat reading rhythm (static word-position cycling) instead of prosodic analysis")
    # Presets
    parser.add_argument("--peaceful-vibe", action="store_true",
                        help="Preset: 432 Hz + isochronic 40 Hz + HRV breathing + breath bar")
    parser.add_argument("--deep-focus", action="store_true",
                        help="Preset: 528 Hz + isochronic 40 Hz (gamma focus, no breathing)")
    parser.add_argument("--sleep", action="store_true",
                        help="Preset: 174 Hz + HRV style C + 30-min fade-to-silence")
    parser.add_argument("--morning-energy", action="store_true",
                        help="Preset: 528 Hz + isochronic + ABS + HRV 4-2-6 breathing")
    parser.add_argument("--anxiety-relief", action="store_true",
                        help="Preset: 396 Hz + HRV 4-7-8 + breath bar + bell cue")
    parser.add_argument("--meditation", action="store_true",
                        help="Preset: 432 Hz + HRV style C + breath bar + 30-min fade")
    parser.add_argument("--emdr-session", action="store_true",
                        help="Preset: PhD-peace 21-phase + bilateral ABS + alternating voices")
    parser.add_argument("--deep-sleep", action="store_true",
                        help="Preset: 174 Hz + HRV style C + 30-min fade + bowl cue")
    parser.add_argument("--bilateral-calm", action="store_true",
                        help="Preset: 528 Hz + ABS + HRV + alternating bilateral stimulation")
    parser.add_argument("--study", action="store_true",
                        help="Preset: 528 Hz + isochronic 40 Hz (pure focus, no breathing)")
    parser.add_argument("--yoga", action="store_true",
                        help="Preset: 432 Hz + HRV 4-7-8 + breath bar + singing bowl cue")
    parser.add_argument("--breathwork", action="store_true",
                        help="Preset: HRV 4-7-8 + breath bar + voice cue (no tone)")
    parser.add_argument("--power-nap", action="store_true",
                        help="Preset: 396 Hz + HRV style C + 30-min fade-to-silence")
    parser.add_argument("--grounding", action="store_true",
                        help="Preset: 396 Hz + HRV + breath bar + Claude counter-conditioning")
    parser.add_argument("--healing", action="store_true",
                        help="Preset: 528 Hz (Solfeggio healing) + HRV + slow ABS")
    parser.add_argument("--creativity", action="store_true",
                        help="Preset: 639 Hz + isochronic 10 Hz (alpha waves for creativity)")
    parser.add_argument("--reading-calm", action="store_true",
                        help="Preset: 432 Hz gentle ambient tone (minimal, calm background)")
    parser.add_argument("--trauma-release", action="store_true",
                        help="Preset: PhD-peace 21-phase + bilateral alternation + HRV 4-7-8")
    parser.add_argument("--ocean-calm", action="store_true",
                        help="Preset: 256 Hz + HRV style C + slow ABS + 30-min fade")
    parser.add_argument("--full-restore", action="store_true",
                        help="Preset: full therapeutic stack — PhD-peace + ABS + HRV 4-7-8 + bowl cue")
    return parser


def apply_presets(args):
    """Apply preset mode overrides to the parsed args namespace. Mutates args in place."""
    if args.peaceful_vibe:
        args.freq = 432; args.iso = True; args.pulse = 40; args.hrv = True; args.breath_bar = True
    if args.deep_focus:
        args.freq = 528; args.iso = True; args.pulse = 40
    if args.sleep:
        args.freq = 174; args.hrv = True; args.hrv_style = "C"; args.fade_long = True
    if args.morning_energy:
        args.freq = 528; args.iso = True; args.abs = True; args.hrv = True; args.hrv_style = "426"
    if args.anxiety_relief:
        args.freq = 396; args.hrv = True; args.hrv_style = "478"; args.breath_bar = True; args.breath_cue = "bell"
    if args.meditation:
        args.freq = 432; args.hrv = True; args.hrv_style = "C"; args.breath_bar = True; args.fade_long = True
    if args.emdr_session:
        args.phd_peace = True; args.abs = True; args.hrv = True; args.hrv_style = "478"
        args.alternate = True; args.breath_bar = True
    if args.deep_sleep:
        args.freq = 174; args.hrv = True; args.hrv_style = "C"; args.fade_long = True; args.breath_cue = "bowl"
    if args.bilateral_calm:
        args.freq = 528; args.abs = True; args.hrv = True; args.alternate = True
    if args.study:
        args.freq = 528; args.iso = True; args.pulse = 40
    if args.yoga:
        args.freq = 432; args.hrv = True; args.hrv_style = "478"; args.breath_bar = True; args.breath_cue = "bowl"
    if args.breathwork:
        args.hrv = True; args.hrv_style = "478"; args.breath_bar = True; args.breath_cue = "voice"
    if args.power_nap:
        args.freq = 396; args.hrv = True; args.hrv_style = "C"; args.fade_long = True
    if args.grounding:
        args.freq = 396; args.hrv = True; args.breath_bar = True; args.claude_peace = True
    if args.healing:
        args.freq = 528; args.hrv = True; args.abs = True; args.abs_speed = "slow"
    if args.creativity:
        args.freq = 639; args.iso = True; args.pulse = 10
    if args.reading_calm:
        args.freq = 432
    if args.trauma_release:
        args.phd_peace = True; args.alternate = True; args.hrv = True; args.hrv_style = "478"; args.breath_bar = True
    if args.ocean_calm:
        args.freq = 256; args.hrv = True; args.hrv_style = "C"; args.abs = True; args.abs_speed = "slow"; args.fade_long = True
    if args.full_restore:
        args.phd_peace = True; args.alternate = True; args.abs = True; args.hrv = True
        args.hrv_style = "478"; args.breath_bar = True; args.breath_cue = "bowl"
