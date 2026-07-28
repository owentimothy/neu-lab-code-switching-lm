# CALLHOME Projection Policy

## Status
- Projection policy for the synthetic-only scaffold in
  `src/cslm/data/callhome_project.py`. No parser run on real files.
- No transcript excerpts, header values, participant names, or speaker IDs
  appear here or are produced by this PR.
- No condition JSONL, no tokenization, no training.
- Defines how source-faithful CALLHOME parser objects are projected into the
  current pre-tokenization row scaffold and constrains later projection work.
- Permission state: **Decision B** (see `docs/callhome_ground_rules.md`,
  TalkBank/CABank response 2026-07-09) — aggregate-only, non-transcript
  summaries may be committed with citation/license notes; transcript-bearing
  outputs remain blocked.

## Purpose
`src/cslm/data/callhome_chat.py` parses CALLHOME `.cha` files in a
**source-faithful** way only. Before we can build monolingual conditions we need
a principled, reviewable plan for turning those parser objects into
**experiment-facing rows** compatible with the `UtteranceRow` concept already
used for Bangor — while preserving provenance and honoring the screening and
permission rules. This note defines that plan so implementation choices are
made deliberately, not emergently in code.

## Source-faithful parsing vs. projection
These are two distinct layers, kept separate (mirroring the Bangor
`bangor_cgwords.py` → `bangor_project.py` split):

- **Parsing layer** (`callhome_chat.py`, exists): preserves CHAT headers, main
  speaker tiers, dependent tiers, nullable language, `media_id`, and parser
  warnings **verbatim**. It does **not** tokenize, clean, language-label tokens,
  project, or judge condition eligibility.
- **Projection layer** (`callhome_project.py`, synthetic-only): consumes parser objects and
  produces experiment-facing rows with derived fields, screening outcomes, and
  provenance. It performs no re-parsing.

`CallhomeTranscript` and `CallhomeUtterance` are **not training rows** and must
never be treated as such. Projection is the only path from parser objects to
condition-eligible rows.

## Input object
Projection consumes the existing source-faithful objects:

- `CallhomeTranscript`: `conversation_id`, `source_file`, `headers`
  (key → list of values), ordered `utterances`, `parser_warnings`.
- `CallhomeUtterance`: `conversation_id`, `source_file`, `speaker_id`,
  `turn_index`, `raw_main_tier_text`, `dependent_tiers` (list of
  `CallhomeTier(prefix, value)`), nullable `language`, nullable `media_id`,
  `parser_warnings`.

Projection reads these; it does not mutate them.

## Output row concept
Projection should produce **experiment-facing row objects compatible with the
existing `UtteranceRow` concept** used for Bangor (same field vocabulary:
`utterance_id`, `source`, `conversation_id`, `speaker_id`, `language_category`,
`condition_candidates`, token/count fields, provenance/ordering fields, nullable
`needs_review_*` heuristics).

However, CALLHOME may need its **own projection module first** (e.g.
`callhome_project.py`), analogous to `bangor_project.py`, rather than forcing
CALLHOME structure through the Bangor projector. The two corpora differ (CHAT
tiers + `%mor` vs. Bangor CG-words with per-token langids), so a dedicated
CALLHOME projector that *emits* `UtteranceRow`-compatible rows keeps the schema
shared while letting each source own its extraction logic. Whether the emitted
type is `UtteranceRow` directly or a CALLHOME-local row that maps onto it is an
implementation decision for the later PR; the **shared schema/vocabulary** is
the invariant.

## Field mapping plan
Indicative mapping from CALLHOME parser objects to `UtteranceRow`-style fields
(final details deferred to implementation):

**Provenance (must be preserved):**
- `source` ← corpus family + language directory, e.g. `callhome_eng` /
  `callhome_spa` (records that this is CALLHOME and which language side).
- `conversation_id` ← `CallhomeUtterance.conversation_id`.
- `utterance_index` / turn ordering ← `CallhomeUtterance.turn_index`.
- `speaker_id` ← safe, **de-identified** speaker reference (see Safety
  constraints) — not a raw CHAT participant code that could identify a person.
- `source_file` reference ← retained in **safe form** (e.g. a stable hashed or
  index-based id), not a path that leaks participant identity, and never
  committed in transcript-bearing output.

**Ordering / context:**
- `previous_utterance_id`, `previous_speaker_id`, `same_speaker_as_previous`,
  `utterance_index` ← derived from ordered `utterances` within a transcript
  (same pattern as Bangor inter-sentential context).

**Language / content (deferred, screening-gated):**
- `language_category` ← for CALLHOME, expected to resolve to `en_only` or
  `es_only` for clean rows; anything with genuine cross-language syntax is
  handled by screening (below), not silently labeled.
- `tokens`, `token_language_labels`, `text`/`raw_text`/`clean_text`, and the
  `n_*` count fields ← produced by the projection/tokenization step **later**;
  these are transcript-bearing and stay local/gitignored.
- `%mor` and other dependent tiers ← available as a POS/morphology signal for
  later probe work; **not** projected into committed output in this PR.

**Heuristic/nullable fields:**
- `needs_review_*` flags ← used to carry screening ambiguity (borrowings,
  isolated foreign words, etc.); never auto-resolved.

`condition_candidates` is **not** filled from row language alone — see next
section.

## Screening-policy interaction
Projection must attach or support the monolingual screening outcomes defined in
`docs/callhome_monolingual_screening.md`:

- **Clean CALLHOME English** rows may feed **`EnglishMono`**, the **English
  side of `MonoCont`**, and may later serve as controlled **English
  monolingual filler** in `CsCont`.
- **Clean CALLHOME Spanish** rows may feed **`SpanishMono`**, the **Spanish
  side of `MonoCont`**, and may later serve as controlled **Spanish
  monolingual filler** in `CsCont`.
- Any future CALLHOME filler row must be selected from the corresponding
  `MonoCont-English` or `MonoCont-Spanish` material. Filler is not independently
  sampled from the wider eligible CALLHOME inventory.
- **Flagged** material (ambiguous borrowings, isolated foreign words,
  name-like insertions, quoted speech, metalinguistic mentions) carries a
  `needs_review` flag and is **neither auto-admitted nor auto-excluded**.
- **Clear code-switching found incidentally in CALLHOME** is **excluded and
  counted**, not admitted as filler or code-switched evidence.

**Evidence invariant:** CALLHOME is an annotation-screened monolingual source.
Its explicit future `CsCont` roles represent monolingual filler only. CALLHOME
cannot count toward the overall code-switched exposure quota, the
intrasentential switching quota, or the intersentential switching quota.
Genuine code-switched evidence comes from separately audited code-switching
sources; Bangor remains the primary current source. The current CALLHOME pilot
builder does not construct or emit `CsCont`.

## Safety constraints
- Do **not** run the parser/projector on real CALLHOME files in this PR.
- Do **not** print or paste transcript excerpts, header values, participant
  names, or speaker IDs — here or in any committed output.
- **Raw utterance text and transcript-bearing JSONL must not be committed.**
- Any transcript-bearing row output (projected rows with `text`/`tokens`) must
  remain **local / gitignored**.
- `speaker_id` and any `source_file` reference in projected rows must be carried
  in **de-identified / safe form**; raw participant codes are treated as
  potentially identifying and are not committed.
- **Aggregate-only projection diagnostics** may be committed under Decision B
  **only if** they contain no transcript text, no header values, no participant
  names, and no speaker IDs (counts, category tallies, condition-eligibility
  tallies, exclusion/flag reasons).

## Out of scope
- Any projection **implementation** or tokenization.
- The tokenizer/vocabulary choice (shared-tokenizer rule applies later).
- Language-ID / token-labeling method and disfluency normalization details.
- Final inclusion/exclusion policy for **flagged** rows.
- Sampling proportions and train/dev/test splitting.
- Building `EnglishMono` / `SpanishMono` / `MonoCont` datasets or condition
  JSONL.
- Any Bangor projection logic or future `CsCont` construction, budgeting, or
  filler selection.

## Future implementation plan
When implementation begins (a **separate** future PR):

1. Add a dedicated CALLHOME projection module (e.g. `callhome_project.py`) that
   consumes `CallhomeTranscript`/`CallhomeUtterance` and emits
   `UtteranceRow`-compatible rows, with **synthetic-only** unit tests first.
2. Attach screening outcomes (from `docs/callhome_monolingual_screening.md`) and
   provenance (`source=callhome_eng`/`callhome_spa`, conversation id, turn
   index, de-identified speaker + safe source-file reference).
3. Derive ordering/context fields from ordered utterances within a transcript.
4. Run a **local-only** projection dry run on gitignored raw files, keeping any
   transcript-bearing rows **local/gitignored**.
5. Emit **aggregate-only, non-transcript** diagnostics (per-category and
   per-condition-eligibility counts, exclusion/flag reasons) and commit only
   those, under Decision B with the required citation/license notes.

This preserves the invariants that CALLHOME supplies annotation-screened
monolingual material (including explicit future filler candidacy), CALLHOME
never supplies code-switched evidence, and only aggregate, non-transcript
artifacts ever enter the repository.
