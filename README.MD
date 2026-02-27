# Resonance — Therapeutic Audio Engine

Your personal sound therapist, running entirely on your machine. No cloud, no microphone, no external audio — just pure mathematics turned into healing sound.

---

### What You Get

**Scientifically-Grounded Breathing** — 6 HRV breath pacing patterns (box breathing, 4-7-8, and more) with a live terminal breathing bar and 8 handcrafted audio cues (singing bowl, bell, woodblock...) to guide every inhale and exhale.

**Therapeutic Voice Sessions** — Up to 384 counter-conditioning affirmations across 21 expert-reviewed phases, covering somatic restoration, nervous system regulation, identity reclamation, and default-state conditioning. Available in English and French.

**EMDR-Style Bilateral Stimulation** — Smooth alternating left/right audio for bilateral processing. Combine with voice alternation (`--alternate`) for full EMDR-inspired sessions where affirmations move between ears.

**Solfeggio & Focus Frequencies** — Tunable from 174 Hz (grounding) to 852 Hz (clarity), with optional 40 Hz gamma isochronic pulses for deep focus and study.

**125-Book Audiobook Library** — Listen to Marcus Aurelius, Dostoyevsky, Hugo, Voltaire, the Bhagavad-Gita, and 120 more classics read aloud during your sessions. 66 French, 59 English. Page tracking, resume support, and real-time subtitles.

**20 One-Flag Presets** — From `--sleep` to `--emdr-session` to `--morning-energy`, each preset is a complete therapeutic session in a single command. No configuration needed.

**30-Minute Fade-to-Silence** — Gradual volume dissolution for sleep, meditation, or power naps. Fall asleep to sound; wake up to silence.

**FLAC Export** — Save any session as a 1-hour lossless audio file for offline listening.

---

### Untamperable by Design

Every sample that reaches your ears is **mathematically computed in-process**:

- **Single output stream only** — one `sounddevice.OutputStream`, no input, no duplex
- **No external audio sources** — no file playback, no network audio
- **No input devices** — microphone access is architecturally impossible
- **Deterministic** — fixed RNG seed, reproducible across runs
- **Cryptographic integrity proof** (`--integrity`) — rolling SHA-256 of every buffer
- **Lockdown mode** (`--lockdown`) — pure sine + output-only + integrity combined

---

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install numpy sounddevice soundfile

# Voice setup (macOS — checks required TTS voices)
./setup_voices.sh

# Download audiobook library (125 books, run once)
python books/fetch_books.py
```

---

## Preset Modes (One-Flag Therapeutic Sessions)

The fastest way to get started — each preset combines optimal settings:

```bash
# Calm ambient tone with HRV breathing and isochronic pulse
python stream_tone.py --peaceful-vibe

# Pure gamma focus (no breathing, just 528 Hz + 40 Hz isochronic)
python stream_tone.py --deep-focus

# Study mode (same as deep-focus)
python stream_tone.py --study

# 432 Hz meditation with slow breathing and 30-min fade
python stream_tone.py --meditation

# Fall asleep: 174 Hz + slow breathing + 30-min fade
python stream_tone.py --sleep

# Deep sleep with singing bowl cues
python stream_tone.py --deep-sleep

# 4-7-8 breathing for anxiety relief with bell cues
python stream_tone.py --anxiety-relief

# Morning energy: 528 Hz + isochronic + bilateral + fast breathing
python stream_tone.py --morning-energy

# 4-7-8 yoga breathing with singing bowl
python stream_tone.py --yoga

# Breathwork only (no tone, just voice-guided 4-7-8 breathing)
python stream_tone.py --breathwork

# 528 Hz Solfeggio healing + slow bilateral stimulation
python stream_tone.py --healing

# 639 Hz alpha-wave creativity boost
python stream_tone.py --creativity

# Gentle 432 Hz ambient for reading
python stream_tone.py --reading-calm

# 30-min power nap with gradual fade
python stream_tone.py --power-nap

# 528 Hz bilateral calm with alternating stimulation
python stream_tone.py --bilateral-calm

# 256 Hz ocean calm: slow ABS + slow breathing + 30-min fade
python stream_tone.py --ocean-calm

# Grounding: 396 Hz + HRV + Claude counter-conditioning
python stream_tone.py --grounding

# Full EMDR session: PhD-peace 21-phase + bilateral + alternating voices
python stream_tone.py --emdr-session

# Trauma release: PhD-peace + bilateral alternation + 4-7-8 breathing
python stream_tone.py --trauma-release

# Full therapeutic stack: everything enabled
python stream_tone.py --full-restore
```

---

## All CLI Options

### Core Audio
```
--freq FLOAT         Frequency in Hz (e.g., 174, 396, 432, 528, 639)
--no-tone            Silence the base tone (voice messages and cues still play)
--save-audio         Save a 1-hour FLAC file instead of streaming
--latency STR        Audio latency: low | high (default: high)
--blocksize INT      Audio blocksize in frames (default: 1024)
```

### Modulation
```
--iso                Enable isochronic mode (volume pulse)
--pulse FLOAT        Isochronic pulse frequency in Hz (default: 40)
--abs                Enable alternating bilateral stimulation (ABS)
--abs-speed STR      ABS speed: slow | medium | fast (default: medium)
```

### HRV Breathing
```
--hrv                Enable HRV breath pacing mode
--hrv-style STR      A | B | C | box | 478 | 426 (default: A)
--breath-cue STR     Cue at transitions: bell|bowl|drum|tick|waterdrop|woodblock|whoosh|doubletick|voice
--breath-cue-vol FL  Breath cue volume (default: 0.25)
--breath-bar         Show live breathing bar in terminal
--fade-long          30-minute fade-to-silence
--full               Full stack: HRV + ISO + ABS + long fade
```

### Therapeutic Voice
```
--restore-peace      Counter-conditioning affirmations (auto-enables HRV)
--peace-voice STR    macOS voice for affirmations (default: Daniel)
--peace-vol FLOAT    Voice volume (default: 0.35)
--claude-peace       16-phase clinical counter-conditioning
--claude-peace-vol   Claude-peace volume (default: 0.35)
--phd-peace          21-phase expert-reviewed counter-conditioning
--phd-peace-vol      PhD-peace volume (default: 0.35)
--alternate          EMDR-style bilateral voice alternation (L/R)
--dense              Affirmation every phase (~5.5s) instead of per cycle (~11s)
--peace-lang STR     Language: en | fr (default: en)
```

### Audiobook
```
--audiobook BOOK     Read a book aloud (e.g., --audiobook meditations)
--audiobook-list     List all 125 available audiobooks and exit
--audiobook-vol FL   Voice volume (default: 0.40)
--audiobook-resume   Resume from saved position
--audiobook-page N   Start from page N (each page = 10 sentences)
```

### Preset Modes
```
--peaceful-vibe      432 Hz + iso 40 Hz + HRV + breath bar
--deep-focus         528 Hz + iso 40 Hz (gamma focus)
--study              528 Hz + iso 40 Hz (pure focus)
--sleep              174 Hz + HRV C + 30-min fade
--deep-sleep         174 Hz + HRV C + 30-min fade + bowl cue
--morning-energy     528 Hz + iso + ABS + HRV 4-2-6
--anxiety-relief     396 Hz + HRV 4-7-8 + breath bar + bell cue
--meditation         432 Hz + HRV C + breath bar + 30-min fade
--yoga               432 Hz + HRV 4-7-8 + breath bar + bowl cue
--breathwork         HRV 4-7-8 + voice cue (no tone)
--healing            528 Hz + HRV + slow ABS
--creativity         639 Hz + iso 10 Hz (alpha waves
--reading-calm       432 Hz gentle ambient
--power-nap          396 Hz + HRV C + 30-min fade
--bilateral-calm     528 Hz + ABS + HRV + alternating
--ocean-calm         256 Hz + HRV C + slow ABS + 30-min fade
--grounding          396 Hz + HRV + Claude counter-conditioning
--emdr-session       PhD-peace + bilateral ABS + alternating voices
--trauma-release     PhD-peace + bilateral + HRV 4-7-8
--full-restore       Full stack: PhD-peace + ABS + HRV 4-7-8 + bowl cue
```

### Safety
```
--pure               Pure sine mode (no modulation)
--disable-inputs     Output-only hardening
--integrity          Rolling SHA-256 integrity proof
--integrity-interval Seconds between integrity prints (default: 1.0)
--lockdown           Maximum safety: pure + disable-inputs + integrity
```

---

## HRV Breathing Styles

**Simple (2-phase):**
- **A** — Symmetric (5.5s in / 5.5s out) — classic HRV coherence
- **B** — Parasympathetic (4s in / 6.5s out) — deeper relaxation
- **C** — Deep meditative (6s in / 6s out) — very slow, deep calm

**Controlled (with hold phases):**
- **box** — Box breathing (4-4-4-4) — stress control
- **478** — 4-7-8 breathing (4s in / 7s hold / 8s out) — relaxation technique
- **426** — 4-2-6 breathing (4s in / 2s hold / 6s out) — calm focus

---

## Audiobook Mode (125 Books — 66 French, 59 English)

Read a full public domain book aloud during sessions. Voice is auto-selected by language (Thomas for French, Alex for English). Base tone is silenced automatically.

### Setup

```bash
# Download books from Project Gutenberg (run once)
python books/fetch_books.py

# List all available books
python stream_tone.py --audiobook-list
```

### Usage

```bash
# Listen to Meditations by Marcus Aurelius
python stream_tone.py --audiobook meditations

# French literature with bilateral alternation
python stream_tone.py --audiobook candide --alternate

# Resume from where you left off
python stream_tone.py --audiobook miserables --audiobook-resume

# Jump to a specific page
python stream_tone.py --audiobook miserables --audiobook-page 42
```

### Real-Time Text Display

The current sentence is logged to the console as it plays, so you can follow along if you miss a word:

```
  > Marcus Aurelius began each morning by telling himself...
  > The happiness of your life depends upon the quality of your thoughts.
```

### Page Tracking & Resume

Every 10 sentences, page progress is logged. On Ctrl-C, you get a resume command:

```
  [Candide — Voltaire [FR]] page 5/120
  Resume with: --audiobook candide --audiobook-page 5
```

With `--audiobook-resume`, progress is auto-saved and restored between sessions.

### Book Library (125 books)

**Philosophy & Wisdom:**
- `meditations` — Meditations (Marcus Aurelius) [EN]
- `enchiridion` — The Enchiridion (Epictetus) [EN]
- `golden-sayings-epictetus` — Golden Sayings of Epictetus [EN]
- `lettres-lucilius` — Minor Dialogues (Seneca) [EN]
- `republique` — The Republic (Plato) [EN]
- `apologie` — Apology (Plato) [EN]
- `banquet` — Symposium (Plato) [EN]
- `phedon` — Phaedo (Plato) [EN]
- `phedre` — Phaedrus (Plato) [EN]
- `gorgias` — Gorgias (Plato) [EN]
- `ethique-nicomaque` — Nicomachean Ethics (Aristotle) [EN]
- `art-guerre` — The Art of War (Sun Tzu) [EN]
- `tao-te-king` — Tao Te Ching (Lao Tzu) [EN]
- `dhammapada` — Dhammapada [EN]
- `bhagavad-gita` — Bhagavad-Gita [EN]^
- `bushido` — Bushido, the Soul of Japa^^n (Nitobe) [EN]
- `bible` — The Bible, KJV [EN]^^
- `coran` — The Quran (tr. Rodwell) [EN]
- `prince` — The Prince (Machiavelli) [EN]
- `contrat-social` — The Social Contract (Rousseau) [EN]
- `oracle-manuel` — The Art of Controversy (Schopenhauer) [EN]
- `bien-mal` — Beyond Good and Evil (Nietzsche) [EN]
- `rubaiyat` — Rubaiyat of Omar Khayyam [EN]
- `amitie` — Treatises on Friendship and Old Age (Cicero) [EN]

**French Philosophy:**
- `essais` — Essais (Montaigne) [FR]
- `discours-methode` — Discours de la méthode (Descartes) [FR]
- `pensees` — Pensées (Pascal) [EN]
- `zarathoustra` — Ainsi parlait Zarathoustra (Nietzsche) [FR]
- `traite-tolerance` — Traité sur la tolérance (Voltaire) [FR]
- `entretiens-confucius` — Les quatre livres (Confucius) [FR]
- `imitation` — L'Imitation de Jésus-Christ [FR]

**Classical Literature:**qsd
- `odyssee` — L'Odyssée (Homère) [FR]
- `iliade` — L'Iliade (Homère) [FR]
- `eneide` — The Aeneid (Virgil) [EN]
- `metamorphoses` — The Metamorphoses (Ovid) [EN]
- `nature-choses` — On the Nature of Things (Lucretius) [EN]

**French Literature:**
- `candide` — Candide (Voltaire) [FR]
- `fables` — Les Fables (La Fontaine) [FR]
- `fleurs-mal` — Les Fleurs du mal (Baudelaire) [FR]
- `miserables` — Les Misérables (Hugo) [FR]
- `monte-cristo` — Le Comte de Monte-Cristo (Dumas) [FR]
- `trois-mousquetaires` — Les Trois Mousquetaires (Dumas) [FR]
- `cyrano` — Cyrano de Bergerac (Rostand) [FR]
- `madame-bovary` — Madame Bovary (Flaubert) [FR]
- `rouge-et-noir` — Le rouge et le noir (Stendhal) [FR]
- `chartreuse-de-parme` — La Chartreuse de Parme (Stendhal) [FR]
- `eugenie-grandet` — Eugénie Grandet (Balzac) [FR]
- `germinal` — Germinal (Zola) [FR]
- `nana` — Nana (Zola) [FR]
- `assommoir` — L'Assommoir (Zola) [FR]
- `therese-raquin` — Thérèse Raquin (Zola) [FR]
- `notre-dame-de-paris` — Notre-Dame de Paris (Hugo) [FR]
- `homme-qui-rit` — L'homme qui rit (Hugo) [FR]
- `quatrevingt-treize` — Quatrevingt-Treize (Hugo) [FR]
- `dame-aux-camelias` — La dame aux camélias (Dumas fils) [FR]
- `liaisons-dangereuses` — Les liaisons dangereuses (Laclos) [FR]
- `grand-meaulnes` — Le Grand Meaulnes (Alain-Fournier) [FR]
- `fantome-opera` — Le Fantôme de l'Opéra (Leroux) [FR]
- `arsene-lupin` — Arsène Lupin (Leblanc) [FR]
- `petite-fadette` — La petite Fadette (Sand) [FR]
- `a-rebours` — À rebours (Huysmans) [FR]
- `du-cote-de-chez-swann` — Du côté de chez Swann (Proust) [FR]

**Jules Verne:**
- `tour-du-monde` — Le tour du monde en 80 jours [FR]
- `voyage-centre-terre` — Voyage au centre de la Terre [FR]
- `vingt-mille-lieues` — Vingt mille lieues sous les mers [FR]
- `ile-mysterieuse` — L'île mystérieuse [FR]
- `de-la-terre-a-la-lune` — De la terre à la lune [FR]

**French Theatre & Poetry:**
- `avare` — L'Avare (Molière) [FR]
- `don-juan` — Don Juan (Molière) [FR]
- `hernani` — Hernani (Hugo) [FR]
- `alcools` — Alcools (Apollinaire) [FR]
- `poesies-rimbaud` — Poésies complètes (Rimbaud) [FR]
- `verlaine-oeuvres` — Oeuvres complètes (Verlaine) [FR]
- `legende-des-siecles` — La Légende des siècles (Hugo) [FR]
- `boule-de-suif` — Boule de Suif (Maupassant) [FR]
- `le-horla` — Le Horla (Maupassant) [FR]
- `contes-de-perrault` — Contes du temps passé (Perrault) [FR]
- `lettres-de-mon-moulin` — Lettres de mon moulin (Daudet) [FR]

**Mindfulness & Self-Improvement:**
- `walden` — Walden (Thoreau) [EN]
- `as-a-man-thinketh` — As a Man Thinketh (James Allen) [EN]
- `way-of-peace` — The Way of Peace (James Allen) [EN]
- `self-help-smiles` — Self-Help (Samuel Smiles) [EN]
- `how-to-live-24h` — How to Live on 24 Hours a Day (Bennett) [EN]
- `power-concentration` — The Power of Concentration (Dumont) [EN]
- `problems-philosophy` — The Problems of Philosophy (Russell) [EN]
- `varieties-religious` — The Varieties of Religious Experience (James) [EN]
- `pragmatism` — Pragmatism (William James) [EN]

**Transcendentalism & Nature:**
- `emerson-essays` — Essays, First Series (Emerson) [EN]
- `nature-emerson` — Nature (Emerson) [EN]
- `civil-disobedience` — On Civil Disobedience (Thoreau) [EN]
- `leaves-of-grass` — Leaves of Grass (Whitman) [EN]
- `songs-innocence` — Songs of Innocence and Experience (Blake) [EN]

**Spiritual Wisdom:**
- `imitation-christ-en` — The Imitation of Christ (Thomas a Kempis) [EN]
- `confessions-augustine` — Confessions of St. Augustine [EN]
- `prophet-gibran` — The Prophet (Kahlil Gibran) [EN]
- `gospel-buddha` — The Gospel of Buddha (Paul Carus) [EN]
- `gitanjali` — Gitanjali (Tagore) [EN]
- `sadhana` — Sadhana (Tagore) [EN]
- `songs-kabir` — Songs of Kabir (Tagore tr.) [EN]
- `paradise-lost` — Paradise Lost (Milton) [EN]
- `divine-comedy` — The Divine Comedy (Dante) [EN]
- `pilgrim-progress` — The Pilgrim's Progress (Bunyan) [EN]

**Literature on the Human Condition:**
- `crime-punishment` — Crime and Punishment (Dostoyevsky) [EN]
- `brothers-karamazov` — The Brothers Karamazov (Dostoyevsky) [EN]
- `anna-karenina` — Anna Karenina (Tolstoy) [EN]
- `war-and-peace` — War and Peace (Tolstoy) [EN]
- `death-ivan-ilyich` — The Death of Ivan Ilyich (Tolstoy) [EN]
- `resurrection-tolstoy` — Resurrection (Tolstoy) [EN]
- `tale-two-cities` — A Tale of Two Cities (Dickens) [EN]

**French Classics (New):**
- `caracteres` — Les Caractères (La Bruyère) [FR]
- `maximes` — Maximes (La Rochefoucauld) [FR]
- `reveries-promeneur` — Les Rêveries du promeneur solitaire (Rousseau) [FR]
- `lettres-persanes` — Lettres persanes (Montesquieu) [FR]
- `esprit-des-lois` — De l'esprit des lois (Montesquieu) [FR]
- `princesse-cleves` — La Princesse de Clèves (Lafayette) [FR]
- `jacques-fataliste` — Jacques le Fataliste (Diderot) [FR]
- `neveu-rameau` — Le Neveu de Rameau (Diderot) [FR]
- `manon-lescaut` — Manon Lescaut (Abbé Prévost) [FR]
- `colomba` — Colomba (Mérimée) [FR]
- `adolphe` — Adolphe (Benjamin Constant) [FR]
- `zadig` — Zadig (Voltaire) [FR]
- `micromegas` — Micromégas (Voltaire) [FR]
- `une-vie` — Une Vie (Maupassant) [FR]
- `pierre-et-jean` — Pierre et Jean (Maupassant) [FR]
- `bel-ami` — Bel-Ami (Maupassant) [FR]

---

## Therapeutic Voice Modes

### Claude-Peace (16-Phase Counter-Conditioning)

~290 affirmations across 16 therapeutic phases using evidence-based techniques from clinical hypnotherapy, ACT, somatic experiencing, and ego-strengthening research. Three male voices (Daniel, Ralph, Fred) alternate for diverse, calm authority.

Phases: Truisms & Grounding → Nasal Breathing → Jaw Release → Automatic Breathing → Focus & Clarity → Self-Worth → Sound Safety → Identity Reclamation → Beauty & Light → Inner Peace → Movement & Vitality → Deep Integration → Body Sovereignty → Nervous System → Above the Sky → Centering & Inner Strength

```bash
python stream_tone.py --claude-peace --disable-inputs
```

### PhD-Peace (21-Phase Expert-Reviewed)

Extends claude-peace with 5 additional default-state conditioning rounds (17-21): Default Expression, Default Posture, Default Feeling, Default Mode, Default Body Rapport. 384 affirmations, ~70 minutes at 11s/cycle.

```bash
# Full PhD-peace with bilateral alternation
python stream_tone.py --phd-peace --alternate --disable-inputs

# Dense mode (double speed, ~35 min)
python stream_tone.py --phd-peace --dense --alternate --no-tone --disable-inputs

# French language
python stream_tone.py --phd-peace --peace-lang fr --alternate --disable-inputs
```

### Restore-Peace (Custom Affirmations)

~170 affirmations covering breathing restoration, mental clarity, autonomy, grounding, and counter-conditioning.

```bash
python stream_tone.py --freq 432 --hrv --restore-peace --breath-bar --breath-cue bowl
```

---

## Voice Setup (macOS)

Resonance uses macOS `say` for TTS. Run the setup script to check required voices:

```bash
./setup_voices.sh
```

**Required voices:**
- **Alex** (English) — ^s + affirmations
- **Thomas** (French) — French audiobooks + affirmations
- **Daniel** (English) — affirmations
- **Samantha** (English) — breath cue voice mode

**To install voices manually:**
1. System Settings → Accessibility → Spoken Content → System Voice → Manage Voices
2. Search for and download: Alex (Enhanced/Premium), Thomas, Daniel, Samantha

The Premium Alex voice (~800 MB) sounds significantly better for audiobook listening.

---

## Recommended Frequencies

| Goal | Frequencies | Example |
|------|------------|---------|
| Grounding & Safety | 174, 432 Hz | `--freq 174 --pure` |
| Emotional Release | 396, 417 Hz | `--freq 396 --hrv --hrv-style B` |
| Coherence & Calm | 432, 528 Hz | `--freq 432 --hrv` |
| Focus & Clarity | 639, 741, 852 Hz | `--freq 639 --iso --pulse 10` |
| Gamma Entrainment | Any + 40 Hz pulse | `--freq 528 --iso --pulse 40` |

---

## Safety Notes

- Keep volume at a comfortable level
- If you feel dizzy, anxious, or overloaded — stop and rest
- For trauma sensitivity, start with: `python stream_tone.py --freq 432 --hrv` at low volume
- This tool exists to help you take sound back as something that serves y ou
