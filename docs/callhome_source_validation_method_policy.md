# CALLHOME Source-Validation Method Policy

## Status
- **Docs-only policy note.** No code changes, no parser run on real files, no
  aggregate outputs committed.
- No transcript excerpts, tokens, header values, participant names, speaker IDs,
  or filenames appear here.
- No condition JSONL, no tokenization, no training.
- Defines what a *future* automatic source-language validation method must
  satisfy **before** any CALLHOME row may become `clean`. The method itself is
  not implemented here.
- Permission state: **Decision B** (see `docs/callhome_ground_rules.md`) —
  aggregate-only, non-transcript summaries may be committed with citation/license
  notes; transcript-bearing outputs remain blocked.

## Purpose
`clean` is the only screening outcome that admits a CALLHOME row into a
monolingual training condition. Per `docs/callhome_clean_admission_policy.md` and
`docs/callhome_source_validation_integration_policy.md`, structural cleanliness is
**necessary but not sufficient**; a row may only be promoted to `clean` once it
also passes **source-language validation**. This note defines what such a
validator must *prove*, which signals are *allowed*, which shortcuts are
*forbidden*, and the review gates that must clear before positive validation is
ever enabled. It is a contract for the future validator, not an implementation.

## Current state
- The pipeline is wired end to end: parse → structural screening → **default**
  source validation (`not_validated`) → projection → aggregate diagnostics.
- The **default keeps every CALLHOME row `not_validated`**, so no row is
  promoted to `clean` and all monolingual condition-candidate counts are zero.
  (The specific run counts are not reproduced here, per Decision B; the *type* of
  result is: zero `clean`, zero condition candidates, zero `validated`.)
- The only positive validation that exists is `explicit_source_validation`, a
  controlled, opt-in signal for **tests / future controlled use only**. There is
  **no real language identification** yet, and the real-data script never calls
  the explicit path.
- A **synthetic-only deterministic lexicon-validation scaffold**
  (`src/cslm/data/callhome_lexicon_validation.py`) now exists as a first candidate
  method (allowed signal: deterministic lexicon-based validation). It validates
  against **caller-provided** lexicons only — it loads no real lexical resources
  and hardcodes no real vocabulary — and it is **not** wired into the real-data
  script. It therefore does not change real CALLHOME behavior; `clean` stays zero.
  Enabling it for real data still requires the review gates below.

## Why source validation is needed
Expected source language comes from the CALLHOME **directory label** (`eng` /
`spa`), but the directory label states only the *expected* language — it does not
*verify* the actual language of any given utterance. A CALLHOME transcript can
contain other-language material, borrowings, or incidental code-switching that
the directory label does not capture, and structural screening (parser warnings,
empty/non-lexical detection) does not check language at all. Without an explicit
validation step, promoting rows to `clean` would silently assume "in `eng/`,
therefore English," which is exactly the assumption this policy forbids.

## What source validation must prove
A positive validation must mean, for a single utterance:

> **This utterance is confidently monolingual in the expected source language.**

Two things must both hold: the utterance is monolingual (not mixed / not
code-switched / not other-language), **and** that single language is the expected
one for its source directory. Anything short of confident monolinguality in the
expected language is **not** a positive validation.

## Allowed positive validation signals
A future automatic validator **must be conservative and prefer false negatives
over false positives** (it is far better to leave a genuinely-clean row at
`needs_review` than to admit a mixed row to training). Signals that *could* be
acceptable, subject to the review gates below:

- **Deterministic lexicon-based validation** using documented English/Spanish
  lexical resources (transparent, inspectable, reproducible).
- **A reviewed language-ID model used locally only** (weights/inference stay
  local; no transcript data leaves the machine; consistent with corpus terms).
- **Agreement between multiple validators** (e.g. lexicon + model must concur),
  raising the confidence bar for a positive.
- **Manual / adjudicated validation** for a small sample, **if permitted by
  corpus restrictions** and kept local.

Each of these produces a positive validation only when it clears the confidence
bar; disagreement or low confidence defaults back to `not_validated`.

## Disallowed shortcuts
Positive validation must **never** be inferred from any of the following:

- **Source directory alone.** `eng/` or `spa/` is expected, not verified.
- **Lexical content alone.** "Has words" does not mean "monolingual in the
  expected language."
- **Rescuing review/blocking rows.** Validation must **not** convert to `clean`:
  - `parser_warning` rows,
  - `possible_code_switching` / `ambiguous_foreign_material` rows,
  - `empty_or_nonlexical` rows,
  - `unsupported_language_label` rows.

These remain `needs_review` (review reasons) or `excluded` (blocking reasons)
regardless of validation. Validation can only ever act on rows that are already
structurally eligible.

## Interaction with structural screening
Validation sits **after** structural screening and is combined via
`combine_screening_and_validation` (see the integration policy). The division of
labor is fixed:

- **Structural screening** decides eligibility (excluded vs. structurally
  eligible) and never emits `clean`.
- **Source validation** decides confidence for already-eligible rows.
- A row becomes `clean` **only when** it is structurally eligible **and**
  positively validated. `excluded` stays `excluded`; a structurally-eligible but
  unvalidated row stays `needs_review`; and no review/blocking reason can be
  rescued by validation.

## Interaction with condition eligibility
Promotion maps to conditions exactly as the projection policy specifies:

- **Validated clean CALLHOME English** rows may feed **`EnglishMono`** and
  **`MonoCont`**.
- **Validated clean CALLHOME Spanish** rows may feed **`SpanishMono`** and
  **`MonoCont`**.
- **CALLHOME rows never feed `CsCont`.** `CsCont` is **Bangor-sourced only**;
  row-level language compatibility is not the same as final condition sourcing.
- `needs_review` and `excluded` rows are eligible for **no** condition.

## Required diagnostics before enabling clean admission
Any validator must produce only **content-free** decisions with these fields:

- `is_validated` (bool),
- `expected_language` (`eng` / `spa`),
- `validation_method` (safe label),
- `reason_codes` (safe labels only).

**No transcript text, tokens, filenames, speaker identifiers, refs, or free
notes may be written into validation outputs.** Validation **diagnostics** must
likewise report **aggregate counts only**:

- `validated` vs `not_validated`,
- validation-method counts,
- reason-code counts,
- source-level counts, if that breakdown is later added.

These aggregate diagnostics (never per-row transcript-bearing output) are what a
reviewer inspects before any clean promotion is enabled.

## Review gates
Before any CALLHOME row is admitted to `clean`, the validator must pass, in
order:

1. **Synthetic unit tests** — proving `clean` only when all clean conditions
   hold, and never on source directory or lexical content alone.
2. **Local aggregate-only dry run** — on the gitignored CALLHOME files, with any
   per-row output kept local/gitignored.
3. **Human review of aggregate counts** — how many rows would become `clean`, by
   source, method, and reason.
4. **Explicit approval to enable clean promotion** — a deliberate decision to
   turn on positive validation.

Until gate 4 is cleared, positive validation stays disabled and the CALLHOME
`clean` count stays zero.

## Out of scope
- Implementing any real validation method, language-ID model, or lexicon.
- Choosing thresholds, confidence levels, or specific lexical resources.
- The resolution policy for borrowings vs. live switches.
- **Condition JSONL construction** — remains out of scope.
- Sampling proportions, train/dev/test splitting, tokenizer choice.
- **Model training** — remains out of scope.
- Any Bangor / `CsCont` logic.

## Future implementation sequence
When a validator is eventually built (a **separate**, reviewed PR or PRs):

1. Implement a conservative validator behind an explicit, opt-in signal — one of
   the allowed positive signals above — producing only content-free decisions.
2. Cover it with **synthetic unit tests** (gate 1).
3. Run a **local aggregate-only dry run** (gate 2) and emit aggregate-only
   validation diagnostics.
4. **Review the aggregate counts** (gate 3) and obtain **explicit approval**
   (gate 4) before enabling clean promotion.
5. Only then proceed — under the existing sourcing invariants (CALLHOME →
   monolingual conditions only; Bangor → `CsCont` only) — toward condition-dataset
   construction, which remains out of scope here.

Until this sequence completes and is approved, every CALLHOME row stays
`not_validated` and the `clean` count stays zero.
