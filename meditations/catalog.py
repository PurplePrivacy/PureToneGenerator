"""Guided meditation catalog.

Each entry maps a CLI name to metadata used by pure_tone for guided meditation sessions.
Meditations are numbered for easy selection with --mindfulness N.
"""

MEDITATION_CATALOG = {
    # ── Buddhism ──
    "buddhist-breath-metta": {
        "number": 1,
        "title": "Buddhist Breath & Metta Meditation",
        "author": "Thanissaro Bhikkhu",
        "language": "en",
        "voice": "Samantha",
        "category": "Buddhism",
    },
    "metta": {
        "number": 2,
        "title": "Lovingkindness (Metta) Meditation",
        "author": "Palouse Mindfulness",
        "language": "en",
        "voice": "Samantha",
        "category": "Buddhism",
    },
    "vipassana": {
        "number": 3,
        "title": "Vipassana Insight Meditation",
        "author": "Traditional",
        "language": "en",
        "voice": "Samantha",
        "category": "Buddhism",
    },
    "anapanasati": {
        "number": 4,
        "title": "Anapanasati Sutta — 16 Steps of Breath",
        "author": "Majjhima Nikaya 118 (tr. Thanissaro Bhikkhu)",
        "language": "en",
        "voice": "Samantha",
        "category": "Buddhism",
    },
    "loving-kindness": {
        "number": 5,
        "title": "Loving-Kindness Meditation",
        "author": "Greater Good Science Center, UC Berkeley",
        "language": "en",
        "voice": "Samantha",
        "category": "Buddhism",
    },
    "impermanence": {
        "number": 6,
        "title": "Contemplation of Impermanence",
        "author": "Traditional Buddhist",
        "language": "en",
        "voice": "Samantha",
        "category": "Buddhism",
    },
    "tonglen": {
        "number": 7,
        "title": "Tonglen Compassion Practice",
        "author": "Tibetan Buddhist Tradition",
        "language": "en",
        "voice": "Samantha",
        "category": "Buddhism",
    },
    # ── Yoga ──
    "yoga-nidra": {
        "number": 8,
        "title": "Yoga Nidra in Nature",
        "author": "Jennie Wadsten / YogaLeela",
        "language": "en",
        "voice": "Samantha",
        "category": "Yoga",
    },
    "yoga-nidra-relaxation": {
        "number": 9,
        "title": "Yoga Nidra for Deep Relaxation",
        "author": "Yin and Meditation",
        "language": "en",
        "voice": "Samantha",
        "category": "Yoga",
    },
    "chakra": {
        "number": 10,
        "title": "Guided Chakra Meditation",
        "author": "Do-Meditation",
        "language": "en",
        "voice": "Samantha",
        "category": "Yoga",
    },
    "chakra-awareness": {
        "number": 11,
        "title": "Chakra Awareness Meditation",
        "author": "Traditional Yoga",
        "language": "en",
        "voice": "Samantha",
        "category": "Yoga",
    },
    "savasana": {
        "number": 12,
        "title": "Guided Savasana Relaxation",
        "author": "Vedic Yoga Academy",
        "language": "en",
        "voice": "Samantha",
        "category": "Yoga",
    },
    "prana-breath": {
        "number": 13,
        "title": "Pranayama Breath Meditation",
        "author": "Traditional Yoga",
        "language": "en",
        "voice": "Samantha",
        "category": "Yoga",
    },
    # ── Mindfulness ──
    "body-scan": {
        "number": 14,
        "title": "Body Scan Meditation",
        "author": "Yoga Jala",
        "language": "en",
        "voice": "Samantha",
        "category": "Mindfulness",
    },
    "mindful-breathing": {
        "number": 15,
        "title": "Guided Mindfulness Breathing",
        "author": "Do-Meditation",
        "language": "en",
        "voice": "Samantha",
        "category": "Mindfulness",
    },
    "mindful-breathing-va": {
        "number": 16,
        "title": "Mindful Breathing (VA Public Domain)",
        "author": "Shilagh Mirgain, PhD / US Veterans Health",
        "language": "en",
        "voice": "Samantha",
        "category": "Mindfulness",
    },
    "breath-awareness": {
        "number": 17,
        "title": "Breath Awareness Meditation",
        "author": "Traditional Mindfulness",
        "language": "en",
        "voice": "Samantha",
        "category": "Mindfulness",
    },
    "present-moment": {
        "number": 18,
        "title": "Present Moment Awareness",
        "author": "Traditional Mindfulness",
        "language": "en",
        "voice": "Samantha",
        "category": "Mindfulness",
    },
}

# Number-to-name lookup
MEDITATION_BY_NUMBER = {m["number"]: name for name, m in MEDITATION_CATALOG.items()}

MEDITATION_CATEGORIES = [
    "Buddhism",
    "Yoga",
    "Mindfulness",
]
