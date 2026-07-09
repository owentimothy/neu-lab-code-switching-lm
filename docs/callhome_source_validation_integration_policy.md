# CALLHOME Source-Validation Integration Policy

## Status
- **Docs-only policy note.** No code changes, no parser run on real files, no
  aggregate outputs committed.
- No transcript excerpts, header values, participant names, speaker IDs, or
  filenames appear here.
- No condition JSONL, no tokenization, no training.
- Defines *how* the existing source-validation scaffold will eventually be wired
  into the pipeline; the integration itself is a later, separately reviewed PR.
- Permission state: **Decision B** (see `docs/callhome_ground_rules.md`) —
  aggregate-only, non-transcript summaries may be committed with citation/license
  notes; transcript-bearing outputs remain blocked.

## Purpose
The source-validation scaffold (`src/cslm/data/callhome_source_validation.py`)
now exists, but it is **not** wired into the local real-data pipeline. Before it
is, we need an explicit, reviewable plan for *where* it plugs in and *what
invariants must hold*, so that integrating it never accidentally promotes real
rows to `clean`. This note is the contract for that future wiring.

It builds directly on `docs/callhome_clean_admission_policy.md` (the 7-condition
clean gate) and `docs/callhome_projection_policy.md` (provenance and condition
sourcing).

## Current implementation state
- Source validation is represented as a **scaffold only**:
  `CallhomeSourceValidationDecision`, `default_source_validation`,
  `explicit_source_validation`, `is_structurally_eligible_for_clean`, and
  `combine_screening_and_validation` exist and are synthetic-tested.
- **No real language identification is implemented.** The only way to obtain a
  positive validation is the explicit, controlled `explicit_source_validation`.
- The scaffold is **not** called by the local real-data summary script; the
  current pipeline (parse → structural screening → projection → aggregate
  diagnostics) is unchanged and admits **zero** rows to `clean`.

## Integration invariant
The overriding invariant for any integration PR:

> Wiring source validation into the pipeline must **not** change the default
> outcome of any real row. With `default_source_validation`, aggregate local
> `clean` must remain **zero**.

Corollaries:
- **Source directory is expected language, not verified language.** A row living
  under `eng/` or `spa/` establishes the *expected* language only; it never, by
  itself, constitutes validation.
- Structural cleanliness remains **necessary but not sufficient** for `clean`.
- The only path to `clean` is a *positive* source-language validation, which does
  not exist automatically today.

## Intended future data flow
Source validation slots in **after** structural screening and **before**
projection, so projection consumes a single final outcome:

```
CallhomeUtterance
  → structural screening heuristics
  → CallhomeScreeningDecision
  → source-language validation
  → CallhomeSourceValidationDecision
  → combine_screening_and_validation
  → final screening outcome
  → projection
  → aggregate diagnostics
  → later condition dataset construction
```

`combine_screening_and_validation` is the single join point: structural screening
decides eligibility, validation decides confidence, and the combiner produces the
final outcome that projection turns into condition candidates.

## Default behavior
- `default_source_validation(language_label)` returns a decision with
  `is_validated=False` (`validation_method="not_validated"`).
- Under the default, `combine_screening_and_validation` returns:
  - `excluded` for rows screening already excluded,
  - `needs_review` for every structurally-eligible-but-unvalidated row.
- Therefore the default integration produces **no `clean` rows** — the required
  zero-clean baseline. Default-unscreened rows remain `needs_review` unless a
  positive validation exists.

## Explicit validation behavior
- `explicit_source_validation(language_label)` returns `is_validated=True`
  (`validation_method="explicit_override"`).
- It is **only** for tests and future controlled use — a deliberate, opt-in
  assertion that a row is monolingual in its source language. It is **not**
  produced by any automatic path, and the local script must never call it.
- A future *real* validation method would be a new, reviewed producer of positive
  validation decisions; until then, explicit override is the sole positive signal.

## Clean admission interaction
A row can reach `clean` **only when all** of these hold (consistent with the
clean-admission policy):

- structural screening is **eligible** (`is_structurally_eligible_for_clean`),
- source validation is **positive** (`is_validated=True`),
- **no** `parser_warning`,
- **no** `possible_code_switching` / `ambiguous_foreign_material`,
- **no** `empty_or_nonlexical`,
- **no** `unsupported_language_label`.

Consequences the combiner enforces:
- **`parser_warning` and `possible_code_switching` cannot be rescued by
  validation** — they keep the row at `needs_review` even when `is_validated=True`.
- **Excluded rows remain excluded** (`empty_or_nonlexical`,
  `unsupported_language_label`); validation cannot un-exclude them.
- **Default-unscreened rows remain `needs_review`** until a positive validation
  exists; only then does the structurally-clean row become `clean`.

## Condition eligibility implications
Final outcomes map to conditions exactly as the projection policy specifies:

- **Clean CALLHOME English** rows may eventually feed **`EnglishMono`** and
  **`MonoCont`**.
- **Clean CALLHOME Spanish** rows may eventually feed **`SpanishMono`** and
  **`MonoCont`**.
- **CALLHOME rows must never feed `CsCont`.** `CsCont` is **Bangor-sourced
  only**; row-level language compatibility is not the same as final condition
  sourcing.
- `needs_review` and `excluded` rows are eligible for **no** condition.

Because the default keeps `clean` at zero, all three monolingual conditions draw
**no** rows from CALLHOME until validation is deliberately enabled and reviewed.

## Safety constraints
- This is a **docs-only** PR; do not edit code or wire in validation.
- Do not run parsers/screeners/validators on real CALLHOME files as part of this
  PR.
- Do not quote or print transcript text, header values, participant names,
  speaker IDs, or filenames.
- The local real-data summary script must **not change behavior** until
  validation is deliberately enabled in a separate PR.
- Raw CALLHOME transcripts, ZIP archives, and transcript-bearing JSONL remain
  **gitignored / never committed**.
- Only **aggregate-only, non-transcript** summaries may be committed, under the
  documented Decision B restrictions. Do not commit real aggregate counts in this
  note.
- Do not create condition JSONL, tokenize, or train in this PR.

## Out of scope
- The **real source-language validation method** — which language-ID or
  monolinguality signal will produce positive validations, and its thresholds.
- Any change to screening heuristics, projection, or diagnostics code.
- The resolution policy for `possible_code_switching` / borrowing rows.
- Sampling proportions, train/dev/test splitting, tokenizer choice.
- Building `EnglishMono` / `SpanishMono` / `MonoCont` datasets or condition JSONL.
- Any Bangor / `CsCont` logic.

## Future implementation plan
When integration begins (a **separate**, reviewed PR):

1. **First integration PR keeps default validation as `not_validated`** and wires
   `combine_screening_and_validation` into the pipeline after structural
   screening and before projection. It must **prove, via a local aggregate-only
   dry run, that `clean` remains zero** — behavior-preserving by construction.
2. Any **future positive validation method** must be:
   - **synthetic-tested first** (unit tests proving `clean` only when all clean
     conditions hold, and never on structural cleanliness or source directory
     alone), then
   - exercised in a **local, aggregate-only dry run** (per-row output stays
     local/gitignored), then
   - **reviewed** on its aggregate counts (how many rows would become `clean`,
     by source and reason) **before** any condition JSONL is created.
3. Only after that review, and only if the counts look right, proceed to
   condition-dataset construction under the existing sourcing invariants
   (CALLHOME → monolingual conditions only; Bangor → `CsCont` only).

Until step 2's review, positive validation stays disabled and the CALLHOME
`clean` count stays zero.
