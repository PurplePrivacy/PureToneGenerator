#!/usr/bin/env bash
# ============================================================================
# Resonance — Voice Setup Script
# ============================================================================
# Installs the macOS voices needed for audiobook and affirmation features.
#
# Required voices:
#   - Alex     (English, high quality) — used for English audiobooks
#   - Thomas   (French)                — used for French audiobooks + affirmations
#   - Daniel   (English)               — used for English affirmations
#   - Samantha (English)               — used for breath cue voice mode
#
# Optional voices (used by --peace-lang fr):
#   - Jacques  (French)
#   - Nicolas  (French)
#
# Usage:
#   chmod +x setup_voices.sh
#   ./setup_voices.sh
# ============================================================================

set -e

echo ""
echo "Resonance — Voice Setup"
echo "======================="
echo ""

# Check we're on macOS
if [[ "$(uname)" != "Darwin" ]]; then
    echo "Error: This script requires macOS (uses the 'say' command for TTS)."
    echo "On Linux, you would need espeak or festival instead."
    exit 1
fi

# List of required voices
REQUIRED_VOICES=("Alex" "Thomas" "Daniel" "Samantha")
OPTIONAL_VOICES=("Jacques" "Nicolas")

check_voice() {
    local voice="$1"
    # Check if voice is available by trying to list it
    if say -v "?" 2>/dev/null | grep -q "^${voice} "; then
        return 0
    else
        return 1
    fi
}

echo "Checking installed voices..."
echo ""

MISSING_REQUIRED=()
MISSING_OPTIONAL=()

for voice in "${REQUIRED_VOICES[@]}"; do
    if check_voice "$voice"; then
        echo "  [OK] $voice"
    else
        echo "  [--] $voice (not installed)"
        MISSING_REQUIRED+=("$voice")
    fi
done

echo ""
for voice in "${OPTIONAL_VOICES[@]}"; do
    if check_voice "$voice"; then
        echo "  [OK] $voice (optional)"
    else
        echo "  [--] $voice (optional, not installed)"
        MISSING_OPTIONAL+=("$voice")
    fi
done

echo ""

if [ ${#MISSING_REQUIRED[@]} -eq 0 ] && [ ${#MISSING_OPTIONAL[@]} -eq 0 ]; then
    echo "All voices are installed. You're ready to go!"
    echo ""
    exit 0
fi

if [ ${#MISSING_REQUIRED[@]} -gt 0 ]; then
    echo "Missing required voices: ${MISSING_REQUIRED[*]}"
    echo ""
    echo "To install them:"
    echo ""
    echo "  1. Open System Settings (or System Preferences on older macOS)"
    echo "  2. Go to: Accessibility > Spoken Content > System Voice > Manage Voices..."
    echo "     (On older macOS: Accessibility > Speech > System Voice > Customize...)"
    echo "  3. Search for and download each missing voice:"
    for voice in "${MISSING_REQUIRED[@]}"; do
        echo "     - $voice"
    done
    echo ""
    echo "  Tip: For Alex, download the 'Enhanced' or 'Premium' version for best quality."
    echo "  The premium Alex voice is ~800 MB but sounds significantly better."
    echo ""
fi

if [ ${#MISSING_OPTIONAL[@]} -gt 0 ]; then
    echo "Missing optional voices: ${MISSING_OPTIONAL[*]}"
    echo "  (These are only needed for --peace-lang fr with specific voice options)"
    echo ""
fi

echo "After installing voices, re-run this script to verify:"
echo "  ./setup_voices.sh"
echo ""
