# Monolingual Corpus Sourcing Plan

## Status
- Planning only.
- No ingestion.
- No downloads committed.
- No training.
- No condition JSONL.

## Why this matters
`MonoCont` and `CsCont` differ, by design, in **code-switching exposure** — that
is the primary difference we want the `CsCont` vs `MonoCont` contrast to
reflect. CALLHOME supplies the monolingual material; controlled CALLHOME
monolingual filler may also appear in future `CsCont`, while genuine
code-switched evidence is sourced primarily from **Bangor Miami**, which is
spontaneous, adult, turn-based bilingual **conversation**. If `MonoCont` (and
the `EnglishMono` / `SpanishMono` anchors) were sourced from written news,
Wikipedia, books, or web crawl, then any measured difference could reflect
**genre / register / modality** (spoken vs written, spontaneous vs edited,
conversational vs expository) rather than code-switching exposure. The
monolingual corpora must therefore be matched to Bangor's register as closely
as possible, and English and Spanish must be matched to **each other** in
collection method so the two monolingual halves are comparable.

## Target register
Desired properties for the English and Spanish monolingual sources:
- **spoken / transcribed** language (not written-first text)
- **informal / conversational** style
- **adult speakers** where possible
- **turn-based dialogue** (multi-party conversation)
- **spontaneous** or minimally scripted
- **natural disfluencies** preserved where possible (false starts, fillers,
  repairs) — consistent with the Bangor projection's "preserve, don't delete"
  stance
- English and Spanish corpora **as parallel as possible in collection method**
  (ideally the same collection protocol across both languages)
- **not child-directed** speech unless explicitly justified
- **not** news / Wikipedia / books / web crawl as the primary source

## Primary candidate pair
**Recommend CALLHOME English + CALLHOME Spanish** (LDC telephone-speech
conversational corpora).

- **Why it matches the register**: CALLHOME is unscripted, spontaneous,
  **adult**, turn-based telephone **conversation** between family members /
  close friends — informal register with natural disfluencies. Crucially, the
  English and Spanish editions share the **same collection protocol** (LDC
  CALLHOME telephone-call design), giving strong cross-language symmetry, which
  is exactly what the `MonoCont` English/Spanish halves need.
- **Likely advantages**:
  - Spoken, spontaneous, adult, conversational — close to Bangor's modality.
  - English/Spanish collected the same way → comparable halves.
  - Transcribed with turn structure; parseable into utterance-level rows.
  - Well-known, documented, widely cited (comparability with prior work).
- **Likely limitations**:
  - **Telephone** dyadic calls vs Bangor's **in-person** interaction — some
    channel/modality mismatch (audio bandwidth, two-party vs multi-party).
  - Monolingual by design, but Spanish CALLHOME includes some US-Spanish
    speakers who may code-switch or borrow — needs a light monolingual screen
    (reuse the Bangor-style language-labeling ideas) before use as a *clean*
    monolingual baseline.
  - Moderate size (tens of calls per language) — may need to size-match Bangor.
  - Transcription conventions differ from Bangor CG-words → separate parser.
- **Access / licensing questions**:
  - CALLHOME is distributed by the **LDC** and typically requires an LDC license
    / membership; some portions are mirrored via **TalkBank**. Need to confirm
    which we can access (see Open questions).
  - Confirm redistribution terms; assume raw transcripts are **not**
    committable, mirroring the Bangor policy (raw gitignored; only aggregates
    committed).
- **Transcript availability**: Yes — CALLHOME ships transcripts (not just
  audio). We need the **transcripts**, not the audio, for this project.
- **Format**: LDC CALLHOME transcripts exist in LDC's own transcript format;
  TalkBank hosts CHAT / CA-CHAT reformatted versions for some CALLHOME data.
  **To confirm**: which format we can obtain (LDC `.txt` transcript vs TalkBank
  CHAT). Format choice drives parser design and how cleanly it maps to
  `UtteranceRow`.
- **Mapping to conditions**:
  - `EnglishMono` = CALLHOME English
  - `SpanishMono` = CALLHOME Spanish
  - `MonoCont` = CALLHOME English + CALLHOME Spanish
  - future `CsCont` monolingual filler may use CALLHOME material already
    selected for the corresponding MonoCont component
  - genuine code-switched evidence for `CsCont` is sourced primarily from
    Bangor Miami

The shared-material requirement is
`CsCont-English-Monolingual-Filler ⊆ MonoCont-English` and
`CsCont-Spanish-Monolingual-Filler ⊆ MonoCont-Spanish`; a future builder must
not independently sample another CALLHOME filler inventory. CALLHOME never
counts as genuine code-switched or mixed-language evidence and cannot satisfy
overall, intrasentential, or intersentential switching quotas.

## Backup candidates

### Fisher English + Fisher Spanish
- **Language**: English; Spanish (Fisher Spanish is Caribbean/US telephone
  Spanish).
- **Modality / register**: spontaneous **telephone conversation**, adult,
  topic-prompted; similar channel to CALLHOME but larger and more topic-guided.
- **Size**: large (hundreds/thousands of calls) — more data than CALLHOME.
- **Access / license**: **LDC**, licensed.
- **Fit to Bangor**: good modality (spoken, spontaneous, adult, conversational);
  English/Spanish collected under comparable Fisher protocols → reasonable
  symmetry. Slightly more topic-prompted than Bangor's free interaction.
- **Risks**: topic prompting reduces "free conversation" naturalness; size
  asymmetry vs Bangor; licensing/access; separate parser.

### Santa Barbara Corpus of Spoken American English (SBCSAE) — English-only backup
- **Language**: English only.
- **Modality / register**: face-to-face and phone **spontaneous** American
  English conversation, adult, multi-party — arguably closer to Bangor's
  **in-person** modality than telephone corpora.
- **Size**: ~60 recordings/transcripts (modest).
- **Access / license**: distributed via **TalkBank / LDC**; relatively
  accessible.
- **Fit to Bangor**: strong register/modality fit for English.
- **Risks**: **English-only** — needs a matched Spanish partner; pairing it with
  a differently-collected Spanish corpus would **break English/Spanish
  symmetry**, so only use if a comparable Spanish in-person corpus is found.

### Spanish spoken-conversation backups (to identify later)
- Candidates to evaluate: **CALLFRIEND Spanish**, regional spoken corpora
  (e.g. **PRESEEA** sociolinguistic interviews, **Corpus del Español** spoken
  subsets, **Ameresco** American Spanish conversation).
- **Fit / risks**: interviews (PRESEEA) are semi-structured, not free
  conversation; regional/national variety must be chosen with US-Spanish /
  Caribbean register in mind to stay comparable to Bangor Miami's Spanish.
- Document language, modality, size, access, fit, and risks for each **when a
  concrete candidate is chosen**.

## Corpora to avoid as primary baselines
- **Wikipedia** — written, expository, edited; wrong modality.
- **News** — written/broadcast, edited, formal register.
- **Common Crawl / OSCAR** — web crawl, mixed/unknown register, heavily written.
- **Books** — written, edited, literary.
- **Subtitles (e.g. OpenSubtitles)** — scripted dialogue, not spontaneous;
  translationese and timing artifacts.
- **CHILDES / child-directed speech** — developmental / child-directed register;
  a **speaker-population and register mismatch** with Bangor's adult
  conversation.

Reason: each introduces a **genre/register/modality** or **developmental**
mismatch that would confound the `CsCont` vs `MonoCont` contrast — the very
thing this sourcing plan exists to prevent.

## Selection criteria
Score each candidate (and the English/Spanish pairing) on:
- **spoken / conversational match** to Bangor
- **English/Spanish collection symmetry** (same protocol across languages)
- **adult speaker match**
- **spontaneous interaction** (vs scripted / prompted / interview)
- **transcript availability** (transcripts, not just audio)
- **license / access feasibility** (LDC vs TalkBank; redistribution terms)
- **preprocessing burden** (format complexity; distance from CG-words)
- **compatibility with the existing `UtteranceRow` projection** (can it map to
  utterances, tokens, token language labels, speaker/turn metadata?)

## Open questions
- Can we access **CALLHOME through TalkBank**, or do we need an **LDC**
  license / NYU institutional access?
- Are **transcripts downloadable** in a format we can parse (LDC transcript vs
  TalkBank CHAT / CA-CHAT)?
- Are there **restrictions on committing aggregate summaries** (assume raw stays
  uncommitted; confirm aggregate counts are permitted, as with Bangor)?
- Should we **downsample English to match Spanish** size (or match Bangor size)?
- Should `MonoCont` **preserve naturalistic proportions** or **balance
  English/Spanish** exposure? (Ties into the deferred balancing decision in
  `docs/condition_dataset_policy.md`.)
- How should we **split monolingual corpora by conversation / speaker** to avoid
  leakage (mirroring the conversation-level split rule for Bangor)?
- Do the chosen Spanish corpora need a **monolingual screen** to remove
  incidental code-switching / borrowing before use as a clean baseline?
