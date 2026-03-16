# Resonance — Therapeutic Audio Engine

Your personal sound therapist, running entirely on your machine. No cloud, no microphone, no external audio — just pure mathematics turned into healing sound.

---

### What You Get

**Scientifically-Grounded Breathing** — 6 HRV breath pacing patterns (box breathing, 4-7-8, and more) with a live terminal breathing bar and 8 handcrafted audio cues (singing bowl, bell, woodblock...) to guide every inhale and exhale.

**Therapeutic Voice Sessions** — Up to 500+ counter-conditioning affirmations across 27 expert-reviewed phases, covering somatic restoration, nervous system regulation, identity reclamation, default-state conditioning, grace, purification, body scan, and cellular healing. Available in English and French with Amelie positive reinforcement voice.

**EMDR-Style Bilateral Stimulation** — Smooth alternating left/right audio for bilateral processing. Combine with voice alternation (`--alternate`) for full EMDR-inspired sessions where affirmations move between ears.

**Solfeggio & Focus Frequencies** — Tunable from 174 Hz (grounding) to 852 Hz (clarity), with optional 40 Hz gamma isochronic pulses for deep focus and study.

**739-Book Audiobook Library** — Listen to Marcus Aurelius, Dostoyevsky, Hugo, Voltaire, Jules Verne, H.G. Wells, Proust, Balzac, Austen, Dickens, Shakespeare, Herodotus, Gibbon, Michelet, and 700+ more classics read aloud during your sessions. 277 French, 462 English — covering philosophy, sci-fi, fantasy, classics, history, and personal improvement. Page tracking, resume support, and real-time subtitles.

**Intelligent Reading Rhythm** — Audiobooks play with text-aware pacing by default: punctuation-sensitive pause hierarchy (periods > semicolons > commas), word-count breath pauses at natural intervals, and glue-word protection to keep articles attached to their nouns. Disable with `--no-rhythm` for raw TTS speed.

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

# Voice setup (macOS — required for TTS to work)
./scripts/setup_voices.sh
```

**Voice requirement:** Resonance uses macOS built-in TTS voices. You **must** download the required voices before running audiobooks or therapeutic voice modes. Go to **System Settings > Accessibility > Spoken Content > System Voice > Manage Voices** and install:
- **English:** Ava (Premium), Daniel, Samantha
- **French:** Audrey (Premium), Thomas, Jacques, Nicolas

Run `./scripts/setup_voices.sh` to check what's missing. Premium voices (~800 MB each) sound significantly better for audiobook listening.

```bash
# Download audiobook library (739 books, run once)
python books/fetch_books.py
```

---

## Preset Modes (One-Flag Therapeutic Sessions)

The fastest way to get started — each preset combines optimal settings:

```bash
# Calm ambient tone with HRV breathing and isochronic pulse
python pure_tone.py --peaceful-vibe

# Pure gamma focus (no breathing, just 528 Hz + 40 Hz isochronic)
python pure_tone.py --deep-focus

# Study mode (same as deep-focus)
python pure_tone.py --study

# 432 Hz meditation with slow breathing and 30-min fade
python pure_tone.py --meditation

# Fall asleep: 174 Hz + slow breathing + 30-min fade
python pure_tone.py --sleep

# Deep sleep with singing bowl cues
python pure_tone.py --deep-sleep

# 4-7-8 breathing for anxiety relief with bell cues
python pure_tone.py --anxiety-relief

# Morning energy: 528 Hz + isochronic + bilateral + fast breathing
python pure_tone.py --morning-energy

# 4-7-8 yoga breathing with singing bowl
python pure_tone.py --yoga

# Breathwork only (no tone, just voice-guided 4-7-8 breathing)
python pure_tone.py --breathwork

# 528 Hz Solfeggio healing + slow bilateral stimulation
python pure_tone.py --healing

# 639 Hz alpha-wave creativity boost
python pure_tone.py --creativity

# Gentle 432 Hz ambient for reading
python pure_tone.py --reading-calm

# 30-min power nap with gradual fade
python pure_tone.py --power-nap

# 528 Hz bilateral calm with alternating stimulation
python pure_tone.py --bilateral-calm

# 256 Hz ocean calm: slow ABS + slow breathing + 30-min fade
python pure_tone.py --ocean-calm

# Grounding: 396 Hz + HRV + Claude counter-conditioning
python pure_tone.py --grounding

# Full EMDR session: PhD-peace 21-phase + bilateral + alternating voices
python pure_tone.py --emdr-session

# Trauma release: PhD-peace + bilateral alternation + 4-7-8 breathing
python pure_tone.py --trauma-release

# Full therapeutic stack: everything enabled
python pure_tone.py --full-restore
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
--ego-boost          25-round dithyrambic ego-strengthening (French, Aurélie only)
--ego-boost-vol      Ego-boost volume (default: 0.35)
--alternate          EMDR-style bilateral voice alternation (L/R)
--dense              Affirmation every phase (~5.5s) instead of per cycle (~11s)
--peace-lang STR     Language: en | fr (default: en)
```

### Audiobook
```
--audiobook BOOK     Read a book aloud (e.g., --audiobook meditations)
--audiobook-list     List all 739 available audiobooks and exit
--audiobook-vol FL   Voice volume (default: 0.40)
--audiobook-voice V  Override TTS voice (default: Ava (Premium) for EN, Audrey (Premium) for FR)
--audiobook-rate WPM Override speech rate in words-per-minute (default: 135)
--audiobook-resume   Resume from saved position
--audiobook-page N   Start from page N (each page = 10 sentences)
--audiobook-gap FL   Silence between sentences in seconds (default: 3.0)
--no-rhythm          Disable reading rhythm — use raw TTS pacing with no pause extension
--no-audiobook-gaps  Disable all inter-sentence gaps
--no-audiobook-loop  Don't loop the book when finished
```

#### Reading Rhythm (enabled by default)

Audiobooks play with intelligent pacing that mimics a skilled human narrator:

- **Punctuation-aware pauses** — periods get 450ms, semicolons/colons 250ms, commas 150ms, dashes 180ms. French text gets a 15% multiplier for naturally longer phrasing.
- **Word-count breath pauses** — 1-second micro-silences are inserted at word positions 1, 3, 5, 9 (cycling within each sentence), creating a natural breathing cadence.
- **Cycling character thresholds** — additional pause points at 12, 18, 25 character intervals (cycling) for even pacing density.
- **Glue-word protection** — articles, prepositions, and short connectors (EN + FR) are never orphaned from their noun. "The" won't be separated from "book."
- **Aggregate cap** — no more than 2 seconds of added silence per sentence, preventing over-extension on long sentences.
- **Safe insertion** — pauses are only placed in confirmed silent regions (5% RMS threshold, 60ms minimum gap), with 15ms safety margins and 5ms crossfades to prevent any speech clipping.

To disable rhythm and use raw TTS output:
```bash
python pure_tone.py --audiobook meditations --no-rhythm
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
--creativity         639 Hz + iso 10 Hz (alpha waves)
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

## Audiobook Mode (739 Books — 277 French, 462 English)

Listen to public domain classics read aloud during sessions. Voice is auto-selected by language: **Ava (Premium)** for English, **Audrey (Premium)** for French. Base tone is silenced automatically. Reading rhythm is enabled by default for natural, narrator-like pacing.

### Setup

```bash
# Download books from Project Gutenberg (run once)
python books/fetch_books.py

# List all available books
python pure_tone.py --audiobook-list
```

### Usage

```bash
# Listen to Meditations by Marcus Aurelius (rhythm enabled by default)
python pure_tone.py --audiobook meditations

# French literature with bilateral alternation
python pure_tone.py --audiobook candide --alternate

# Resume from where you left off
python pure_tone.py --audiobook miserables --audiobook-resume

# Jump to a specific page
python pure_tone.py --audiobook miserables --audiobook-page 42

# Raw TTS pacing (no rhythm enhancement)
python pure_tone.py --audiobook meditations --no-rhythm

# Custom speech rate (default: 135 WPM)
python pure_tone.py --audiobook meditations --audiobook-rate 170

# Override TTS voice
python pure_tone.py --audiobook meditations --audiobook-voice "Alex"
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

### Book Library (739 books)

**Philosophy & Wisdom:**
- `meditations` — Meditations (Marcus Aurelius) [EN - Ancient formulations]
- `enchiridion` — The Enchiridion (Epictetus) [EN - Ancient formulations]
- `golden-sayings-epictetus` — Golden Sayings of Epictetus [EN - Ancient formulations]
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
- `dhammapada` — Dhammapada [EN - Ancient formulations]
- `bhagavad-gita` — Bhagavad-Gita [EN]
- `bushido` — Bushido, the Soul of Japan (Nitobe) [EN]
- `bible` — The Bible, KJV [EN]
- `coran` — The Quran (tr. Rodwell) [EN - Ancient formulations]
- `prince` — The Prince (Machiavelli) [EN]
- `contrat-social` — The Social Contract (Rousseau) [EN]
- `oracle-manuel` — The Art of Controversy (Schopenhauer) [EN]
- `bien-mal` — Beyond Good and Evil (Nietzsche) [EN]
- `rubaiyat` — Rubaiyat of Omar Khayyam [EN]
- `amitie` — Treatises on Friendship and Old Age (Cicero) [EN]

**French Philosophy:**
- `essais` — Essais (Montaigne) [FR]
- `discours-methode` — Discours de la methode (Descartes) [FR]
- `pensees` — Pensees (Pascal) [EN]
- `zarathoustra` — Ainsi parlait Zarathoustra (Nietzsche) [FR]
- `traite-tolerance` — Traite sur la tolerance (Voltaire) [FR]
- `entretiens-confucius` — Les quatre livres (Confucius) [FR]
- `imitation` — L'Imitation de Jesus-Christ [FR]

**Classical Literature:**
- `odyssee` — L'Odyssee (Homere) [FR]
- `iliade` — L'Iliade (Homere) [FR]
- `eneide` — The Aeneid (Virgil) [EN - Ancient formulations]
- `metamorphoses` — The Metamorphoses (Ovid) [EN]
- `nature-choses` — On the Nature of Things (Lucretius) [EN]

**French Literature:**
- `candide` — Candide (Voltaire) [FR]
- `fables` — Les Fables (La Fontaine) [FR]
- `fleurs-mal` — Les Fleurs du mal (Baudelaire) [FR]
- `miserables` — Les Miserables (Hugo) [FR]
- `monte-cristo` — Le Comte de Monte-Cristo (Dumas) [FR]
- `trois-mousquetaires` — Les Trois Mousquetaires (Dumas) [FR]
- `cyrano` — Cyrano de Bergerac (Rostand) [FR]
- `madame-bovary` — Madame Bovary (Flaubert) [FR]
- `rouge-et-noir` — Le rouge et le noir (Stendhal) [FR]
- `chartreuse-de-parme` — La Chartreuse de Parme (Stendhal) [FR]
- `eugenie-grandet` — Eugenie Grandet (Balzac) [FR]
- `germinal` — Germinal (Zola) [FR]
- `nana` — Nana (Zola) [FR]
- `assommoir` — L'Assommoir (Zola) [FR]
- `therese-raquin` — Therese Raquin (Zola) [FR]
- `notre-dame-de-paris` — Notre-Dame de Paris (Hugo) [FR]
- `homme-qui-rit` — L'homme qui rit (Hugo) [FR]
- `quatrevingt-treize` — Quatrevingt-Treize (Hugo) [FR]
- `dame-aux-camelias` — La dame aux camelias (Dumas fils) [FR]
- `liaisons-dangereuses` — Les liaisons dangereuses (Laclos) [FR]
- `grand-meaulnes` — Le Grand Meaulnes (Alain-Fournier) [FR]
- `fantome-opera` — Le Fantome de l'Opera (Leroux) [FR]
- `arsene-lupin` — Arsene Lupin (Leblanc) [FR]
- `petite-fadette` — La petite Fadette (Sand) [FR]
- `a-rebours` — A rebours (Huysmans) [FR]
- `du-cote-de-chez-swann` — Du cote de chez Swann (Proust) [FR]

**Jules Verne:**
- `tour-du-monde` — Le tour du monde en 80 jours [FR]
- `voyage-centre-terre` — Voyage au centre de la Terre [FR]
- `vingt-mille-lieues` — Vingt mille lieues sous les mers [FR]
- `ile-mysterieuse` — L'ile mysterieuse [FR]
- `de-la-terre-a-la-lune` — De la terre a la lune [FR]

**French Theatre & Poetry:**
- `avare` — L'Avare (Moliere) [FR]
- `don-juan` — Don Juan (Moliere) [FR]
- `hernani` — Hernani (Hugo) [FR]
- `alcools` — Alcools (Apollinaire) [FR]
- `poesies-rimbaud` — Poesies completes (Rimbaud) [FR]
- `verlaine-oeuvres` — Oeuvres completes (Verlaine) [FR]
- `legende-des-siecles` — La Legende des siecles (Hugo) [FR]
- `boule-de-suif` — Boule de Suif (Maupassant) [FR]
- `le-horla` — Le Horla (Maupassant) [FR]
- `contes-de-perrault` — Contes du temps passe (Perrault) [FR]
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
- `leaves-of-grass` — Leaves of Grass (Whitman) [EN - Ancient formulations]
- `songs-innocence` — Songs of Innocence and Experience (Blake) [EN - Ancient formulations]

**Spiritual Wisdom:**
- `imitation-christ-en` — The Imitation of Christ (Thomas a Kempis) [EN - Ancient formulations]
- `confessions-augustine` — Confessions of St. Augustine [EN - Ancient formulations]
- `prophet-gibran` — The Prophet (Kahlil Gibran) [EN]
- `gospel-buddha` — The Gospel of Buddha (Paul Carus) [EN - Ancient formulations]
- `gitanjali` — Gitanjali (Tagore) [EN]
- `sadhana` — Sadhana (Tagore) [EN]
- `songs-kabir` — Songs of Kabir (Tagore tr.) [EN]
- `paradise-lost` — Paradise Lost (Milton) [EN - Ancient formulations]
- `divine-comedy` — The Divine Comedy (Dante) [EN - Ancient formulations]
- `pilgrim-progress` — The Pilgrim's Progress (Bunyan) [EN - Ancient formulations]

**Literature on the Human Condition:**
- `crime-punishment` — Crime and Punishment (Dostoyevsky) [EN]
- `brothers-karamazov` — The Brothers Karamazov (Dostoyevsky) [EN]
- `anna-karenina` — Anna Karenina (Tolstoy) [EN]
- `war-and-peace` — War and Peace (Tolstoy) [EN]
- `death-ivan-ilyich` — The Death of Ivan Ilyich (Tolstoy) [EN]
- `resurrection-tolstoy` — Resurrection (Tolstoy) [EN]
- `tale-two-cities` — A Tale of Two Cities (Dickens) [EN]

**French Classics:**
- `caracteres` — Les Caracteres (La Bruyere) [FR]
- `maximes` — Maximes (La Rochefoucauld) [FR]
- `reveries-promeneur` — Les Reveries du promeneur solitaire (Rousseau) [FR]
- `lettres-persanes` — Lettres persanes (Montesquieu) [FR]
- `esprit-des-lois` — De l'esprit des lois (Montesquieu) [FR]
- `princesse-cleves` — La Princesse de Cleves (Lafayette) [FR]
- `jacques-fataliste` — Jacques le Fataliste (Diderot) [FR]
- `neveu-rameau` — Le Neveu de Rameau (Diderot) [FR]
- `manon-lescaut` — Manon Lescaut (Abbe Prevost) [FR]
- `colomba` — Colomba (Merimee) [FR]
- `adolphe` — Adolphe (Benjamin Constant) [FR]
- `zadig` — Zadig (Voltaire) [FR]
- `micromegas` — Micromegas (Voltaire) [FR]
- `une-vie` — Une Vie (Maupassant) [FR]
- `pierre-et-jean` — Pierre et Jean (Maupassant) [FR]
- `bel-ami` — Bel-Ami (Maupassant) [FR]

**Yoga & Breath Science:**
- `science-of-breath` — The Hindu-Yogi Science of Breath (Yogi Ramacharaka) [EN]
- `raja-yoga` — A Series of Lessons in Raja Yoga (Yogi Ramacharaka) [EN]
- `gnani-yoga` — A Series of Lessons in Gnani Yoga (Yogi Ramacharaka) [EN]
- `yoga-sutras` — The Yoga Sutras of Patanjali (tr. Johnston) [EN]
- `upanishads` — The Upanishads (tr. Swami Paramananda) [EN]
- `autobiography-yogi` — Autobiography of a Yogi (Yogananda) [EN]
- `jnana-yoga` — Jnana Yoga (Swami Vivekananda) [EN]
- `light-of-asia` — The Light of Asia (Sir Edwin Arnold) [EN - Ancient formulations]

**Mindfulness & Presence:**
- `presence-of-god` — The Practice of the Presence of God (Brother Lawrence) [EN]
- `light-on-path` — Light on the Path (Mabel Collins) [EN]
- `heavenly-life` — The Heavenly Life (James Allen) [EN]
- `zen-buddhism` — Essays in Zen Buddhism (D.T. Suzuki) [EN]
- `buddhas-path-virtue` — The Buddha's Path of Virtue (Dhammapada) [EN]
- `kybalion` — The Kybalion (Three Initiates) [EN]
- `edinburgh-lectures` — Edinburgh Lectures on Mental Science (Troward) [EN]

**Mental Power & New Thought:**
- `dynamic-thought` — Dynamic Thought (Atkinson) [EN]
- `thought-culture` — Thought-Culture (Atkinson) [EN]
- `your-mind` — Your Mind and How to Use It (Atkinson) [EN]
- `memory-atkinson` — Memory: How to Develop, Train, and Use It (Atkinson) [EN]
- `hidden-power` — The Hidden Power (Troward) [EN]
- `science-getting-rich` — The Science of Getting Rich (Wattles) [EN]
- `science-being-well` — The Science of Being Well (Wattles) [EN]
- `mystic-christianity` — Mystic Christianity (Atkinson) [EN]

**Stoic & Contemplative Wisdom:**
- `discourses-epictetus` — Discourses of Epictetus [EN]
- `wisdom-destiny` — Wisdom and Destiny (Maeterlinck) [EN]
- `treasure-humble` — The Treasure of the Humble (Maeterlinck) [EN]

**French Mindfulness & Wisdom:**
- `sagesse-destinee` — La sagesse et la destinee (Maeterlinck) [FR]
- `tresor-humbles` — Le tresor des humbles (Maeterlinck) [FR]
- `sentiers-montagne` — Les sentiers dans la montagne (Maeterlinck) [FR]
- `aphorismes-sagesse` — Aphorismes sur la sagesse dans la vie (Schopenhauer) [FR]

Use `--audiobook-list` for the full catalog of 739 books including Sci-Fi, Fantasy, English Classics, Philosophy, History, Personal Improvement, and more.

### Series Reading Order

For books that are part of a series, read them in this order:

**Barsoom Series** (Edgar Rice Burroughs) [EN]:
`princess-of-mars` -> `gods-of-mars` -> `warlord-of-mars` -> `thuvia-maid-of-mars` -> `chessmen-of-mars` -> `master-mind-of-mars` -> `fighting-man-of-mars`

**Pellucidar Series** (Edgar Rice Burroughs) [EN]:
`at-earths-core` -> `pellucidar` -> `tanar-of-pellucidar`

**Lensman Series** (E.E. "Doc" Smith) [EN]:
`triplanetary` -> `first-lensman` -> `galactic-patrol` -> `gray-lensman` -> `second-stage-lensman` -> `children-of-the-lens` -> `vortex-blaster`

**Oz Series** (L. Frank Baum) [EN]:
`wonderful-wizard-of-oz` -> `marvelous-land-of-oz` -> `ozma-of-oz` -> `dorothy-and-wizard-in-oz` -> `road-to-oz` -> `emerald-city-of-oz` -> `patchwork-girl-of-oz` -> `tik-tok-of-oz` -> `scarecrow-of-oz` -> `rinkitink-in-oz` -> `lost-princess-of-oz` -> `tin-woodman-of-oz` -> `magic-of-oz` -> `glinda-of-oz`

**Andrew Lang Fairy Books** [EN]:
`blue-fairy-book` -> `red-fairy-book` -> `green-fairy-book` -> `yellow-fairy-book` -> `pink-fairy-book` -> `grey-fairy-book` -> `violet-fairy-book` -> `crimson-fairy-book` -> `brown-fairy-book` -> `orange-fairy-book` -> `olive-fairy-book` -> `lilac-fairy-book`

**Les Trois Mousquetaires** (Alexandre Dumas) [FR]:
`trois-mousquetaires` -> `vingt-ans-apres` -> `vicomte-bragelonne-1` -> `vicomte-bragelonne-2` -> `vicomte-bragelonne-3` -> `vicomte-bragelonne-4`

**Le Comte de Monte-Cristo** (Alexandre Dumas) [FR]:
`monte-cristo` -> `monte-cristo-2` -> `monte-cristo-3` -> `monte-cristo-4`

**La Reine Margot** (Alexandre Dumas) [FR]:
`reine-margot-1` -> `reine-margot-2`

**A la recherche du temps perdu** (Marcel Proust) [FR]:
`du-cote-de-chez-swann` -> `jeunes-filles-1` -> `jeunes-filles-2` -> `jeunes-filles-3` -> `guermantes-1` -> `guermantes-2` -> `guermantes-3` -> `sodome-gomorrhe-1` -> `sodome-gomorrhe-2` -> `prisonniere-proust` -> `albertine-disparue-1` -> `albertine-disparue-2` -> `temps-retrouve-1` -> `temps-retrouve-2`

**La Comedie humaine** (Honore de Balzac) [FR]:
`comedie-humaine-1` through `comedie-humaine-16` (volumes 1-8, 9-12, 15-16)

**Les Rougon-Macquart** (Emile Zola) [FR] — suggested reading:
`la-curee` -> `ventre-paris` -> `conquete-plassans` -> `faute-abbe-mouret` -> `son-excellence-rougon` -> `assommoir` -> `page-amour` -> `nana` -> `pot-bouille` -> `bonheur-dames` -> `germinal` -> `loeuvre-zola` -> `la-terre` -> `le-reve-zola` -> `bete-humaine` -> `argent-zola` -> `la-debacle` -> `docteur-pascal`

**Les Miserables** (Victor Hugo) [FR]:
`miserables` -> `miserables-cosette` -> `miserables-3-marius` -> `miserables-4-idylle` -> `miserables-5-valjean`

**Decline and Fall of the Roman Empire** (Edward Gibbon) [EN]:
`decline-fall-rome-1` -> `decline-fall-rome-2` -> `decline-fall-rome-3`

**Histoire de la Revolution francaise** (Adolphe Thiers) [FR]:
`revolution-francaise-thiers-1` through `revolution-francaise-thiers-7`

**Histoire des Croisades** (Joseph Francois Michaud) [FR]:
`histoire-croisades-michaud-1` through `histoire-croisades-michaud-6`

**Memoires d'Outre-Tombe** (Chateaubriand) [FR]:
`memoires-outre-tombe-1` through `memoires-outre-tombe-5`

---

## Therapeutic Voice Modes

### Claude-Peace (16-Phase Counter-Conditioning)

~290 affirmations across 16 therapeutic phases using evidence-based techniques from clinical hypnotherapy, ACT, somatic experiencing, and ego-strengthening research. Three male voices (Daniel, Ralph, Fred) alternate for diverse, calm authority.

Phases: Truisms & Grounding -> Nasal Breathing -> Jaw Release -> Automatic Breathing -> Focus & Clarity -> Self-Worth -> Sound Safety -> Identity Reclamation -> Beauty & Light -> Inner Peace -> Movement & Vitality -> Deep Integration -> Body Sovereignty -> Nervous System -> Above the Sky -> Centering & Inner Strength

```bash
python pure_tone.py --claude-peace --disable-inputs
```

### PhD-Peace (27-Phase Expert-Reviewed)

Extends claude-peace with 11 additional rounds (17-27): Default Expression, Default Posture, Default Feeling, Default Mode, Default Body Rapport, Default Throat, Grace & Elegance, Purification & Renewal, Body Scan & Deep Release, Cellular Healing, Head & Face Release. 500+ affirmations, ~90 minutes at 11s/cycle. French version includes Amelie positive reinforcement voice ("c'est bien", "comme ca", "voila").

```bash
# Full PhD-peace with bilateral alternation
python pure_tone.py --phd-peace --alternate --disable-inputs

# French language
python pure_tone.py --phd-peace --peace-lang fr --alternate --disable-inputs
```

### Ego-Boost (25-Round Dithyrambic Ego-Strengthening)

150 epic French affirmations delivered by Aurélie (Enhanced) — a single warm female voice celebrating every dimension of who you are. Designed as intensive counter-therapy for years of being talked down: pure, over-the-top praise that makes you feel like a living god while you sleep.

25 rounds escalating from warm to transcendent: Physical Beauty -> Intelligence -> Precision -> Virtue -> Strength -> Charisma -> Grace -> Creativity -> Worth -> Confidence -> Warmth -> Mastery -> Desirability -> Humor -> Leadership -> Authenticity -> Body Power -> Emotional Depth -> Success -> Sovereignty -> Aliveness -> Legacy -> Radiance -> Abundance -> Apotheosis.

Same hypnotic timing as PhD-peace: exhale-triggered delivery (0.8s into parasympathetic peak), progressive inter-message gaps that deepen as the session progresses, and 115 WPM speech rate for slow, hypnotic absorption.

```bash
# Basic ego-boost session
python pure_tone.py --ego-boost --alternate --disable-inputs

# With bilateral stimulation for deeper processing
python pure_tone.py --ego-boost --alternate --abs --disable-inputs

# Sleep mode: ego-boost + 30-min fade (fall asleep a god, wake up knowing it)
python pure_tone.py --ego-boost --alternate --disable-inputs --fade-long --freq 174
```

### Restore-Peace (Custom Affirmations)

~170 affirmations covering breathing restoration, mental clarity, autonomy, grounding, and counter-conditioning.

```bash
python pure_tone.py --freq 432 --hrv --restore-peace --breath-bar --breath-cue bowl
```

---

## Voice Setup (macOS)

Resonance uses macOS `say` for TTS. Run the setup script to check required voices:

```bash
./scripts/setup_voices.sh
```

**Required voices:**
- **Ava (Premium)** (English) — audiobooks + affirmations
- **Audrey (Premium)** (French) — French audiobooks + affirmations
- **Daniel** (English) — affirmations
- **Samantha** (English) — breath cue voice mode

**To install voices manually:**
1. System Settings -> Accessibility -> Spoken Content -> System Voice -> Manage Voices
2. Search for and download: Ava (Premium), Audrey (Premium), Daniel, Samantha

The Premium voices (~800 MB each) sound significantly better for audiobook listening.

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
- For trauma sensitivity, start with: `python pure_tone.py --freq 432 --hrv` at low volume
- This tool exists to help you take sound back as something that serves you
