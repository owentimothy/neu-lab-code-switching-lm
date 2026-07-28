# CALLHOME Monolingual Screening Policy

## Status
- **Docs-only policy note.** No screening code, no parser run on real files.
- No transcript excerpts, header values, participant names, or speaker IDs
  appear here or are produced by this PR.
- No condition JSONL, no tokenization, no training.
- Defines *what should eventually count* as clean monolingual material; the
  implementation is a later PR.
- Permission state: **Decision B** (see `docs/callhome_ground_rules.md`,
  TalkBank/CABank response 2026-07-09) — aggregate-only, non-transcript
  summaries may be committed with citation/license notes; transcript-bearing
  outputs remain blocked.

## Purpose
CALLHOME English and CALLHOME Spanish are the primary candidate monolingual
corpora for the `EnglishMono`, `SpanishMono`, and `MonoCont` conditions, and may
also supply controlled monolingual filler to a future `CsCont` condition.
Before writing any screening code, we need an explicit, reviewable policy for
deciding which CALLHOME rows are annotation-clean monolingual material — so
that eligibility decisions are principled and auditable rather than emergent
from code.

This note defines the **screening categories** and the **core rule** that keeps
the monolingual conditions genuinely monolingual, while not over-pruning normal
spoken-conversation phenomena.

## Core experimental rule
The monolingual conditions must contain **monolingual material only**:

- **CALLHOME English** clean rows may feed **`EnglishMono`** and the **English
  side of `MonoCont`**, and may later serve as English monolingual filler in
  `CsCont`.
- **CALLHOME Spanish** clean rows may feed **`SpanishMono`** and the **Spanish
  side of `MonoCont`**, and may later serve as Spanish monolingual filler in
  `CsCont`.
- **`MonoCont`** is English-monolingual + Spanish-monolingual material
  concatenated, with **no genuine code-switched utterances**.
- CALLHOME rows are never genuine code-switched evidence and cannot satisfy
  overall, intrasentential, or intersentential code-switched exposure quotas.

**Sourcing is not the same as row-level language.** Bangor Miami `en_only` and
`es_only` rows do **not** feed the monolingual conditions, because Bangor is
**bilingual-interaction sourced**. Bangor remains the primary current source of
genuine code-switched evidence for `CsCont`; other separately audited
code-switching sources may be considered later. A row being monolingual at the
token level does not make it monolingual *in provenance*; the monolingual
conditions draw only from the dedicated monolingual corpora (CALLHOME), never
from Bangor. Row-level language compatibility ≠ final condition sourcing.

## Screening categories
Each CALLHOME row will eventually be assigned to exactly one screening outcome.
Rows are **never silently discarded**: excluded and flagged rows must be counted
with reasons in the (aggregate-only) diagnostics.

### 1. Clean monolingual row
A row whose linguistic content is unambiguously in a single target language
(all English, or all Spanish), with no cross-language syntax.
- **Disposition:** eligible for the matching monolingual condition
  (`EnglishMono` / `SpanishMono`), the matching side of `MonoCont`, and
  corresponding future `CsCont` monolingual-filler candidacy. Filler must be
  drawn from material already selected for the matching `MonoCont` side.

### 2. Acceptable conversational material
Normal spoken-conversation phenomena that do **not** compromise monolinguality
and must **not** automatically disqualify a row:
- filled pauses / hesitation markers,
- backchannels and continuers,
- repairs, self-corrections, and false starts,
- repetitions,
- proper names used naturally within one language.

- **Disposition:** treated as clean monolingual material (category 1) for
  sourcing purposes. These are *features* of spontaneous speech, not defects;
  removing them would bias the register away from Bangor's conversational
  register. (Surface normalization of some of these — e.g. filled pauses to a
  neutral label — is a downstream projection concern, not a screening
  exclusion.)

### 3. Flagged but not automatically excluded
Material that is neither clearly clean nor clearly code-switching, and should be
**flagged for later human/heuristic review** rather than auto-included or
auto-excluded:
- ambiguous borrowings vs. live switches,
- isolated foreign words,
- names that could read as foreign-language insertions,
- quoted speech in the other language,
- metalinguistic mentions (a word *mentioned* rather than *used*).

- **Disposition:** carry a `needs_review` flag; **not** auto-admitted to clean
  monolingual conditions and **not** auto-excluded. Do not silently classify
  contested phenomena. Resolution policy (include / exclude / down-weight) is a
  later decision, recorded before any such row enters a condition.

### 4. Excluded from clean monolingual conditions
Material that would break the monolinguality of the target condition:
- clear English–Spanish code-switching (intra- or inter-sentential),
- mixed-language syntax within the row,
- rows whose language cannot be reliably resolved to a single target language.

- **Disposition:** excluded from `EnglishMono`, `SpanishMono`, and `MonoCont`.
  Genuine code-switching found incidentally in CALLHOME is not admitted as
  `CsCont` evidence or credited toward any switching quota; it is excluded here
  and counted with a reason. Excluded rows are never silently dropped.

## Safety constraints
- Do **not** run parsers/screeners on real CALLHOME files as part of this PR.
- Do **not** print or paste transcript excerpts, header values, participant
  names, or speaker IDs — here or in any committed output.
- Do **not** create condition JSONL or any transcript-bearing output.
- Do **not** tokenize or train.
- Raw CALLHOME transcripts, ZIP archives, and transcript-bearing JSONL remain
  **gitignored / never committed**.
- Only **aggregate-only, non-transcript** summaries may be committed, and only
  under the documented TalkBank/CABank Decision B restrictions (no transcript
  text, no header values, no participant names, no speaker IDs; with required
  citation/license notes).

## Out of scope
- Any screening/classification **implementation**.
- The exact heuristics or language-ID method used to assign categories.
- The final inclusion/exclusion policy for **category 3 (flagged)** rows.
- Tokenizer choice, sampling proportions, and train/dev/test splitting.
- Building `EnglishMono` / `SpanishMono` / `MonoCont` datasets.
- Detailed future `CsCont` composition, budgets, or filler selection.

## Next implementation step
When implementation begins (a **separate** future PR), the first safe step is a
**local-only, aggregate-only screening dry run**:
- run the (existing synthetic-tested) CALLHOME parser locally on gitignored raw
  files,
- assign each row a screening category from this policy,
- emit **counts only** per category and per condition-eligibility, with
  exclusion/flag reasons — **no transcript-bearing rows**,
- keep any per-row output **local/gitignored**; commit only the aggregate,
  non-transcript summary under Decision B with citation/license notes.

This preserves the invariant that monolingual conditions are sourced only from
CALLHOME clean rows, that CALLHOME never counts as genuine code-switched
evidence, and that only aggregate, non-transcript artifacts ever enter the
repository. The current CALLHOME pilot builder constructs no `CsCont` artifact.
