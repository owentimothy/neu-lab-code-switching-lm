# CALLHOME Clean-Admission Policy

## Status
- **Docs-only policy note.** No screening/promotion code, no parser run on real
  files, no aggregate outputs committed.
- No transcript excerpts, header values, participant names, speaker IDs, or
  filenames appear here.
- No condition JSONL, no tokenization, no training.
- Defines *when* a CALLHOME row may be promoted from `needs_review` to `clean`;
  the implementation is a later, separately reviewed PR.
- Permission state: **Decision B** (see `docs/callhome_ground_rules.md`) —
  aggregate-only, non-transcript summaries may be committed with citation/license
  notes; transcript-bearing outputs remain blocked.

## Purpose
`clean` is the only screening outcome that makes a CALLHOME row eligible for a
monolingual training condition (`EnglishMono`, `SpanishMono`, `MonoCont`). It is
therefore the single most consequential label in the CALLHOME pipeline: a `clean`
row is data a model will actually train on. This note defines an explicit,
reviewable gate for that promotion so rows never become `clean` accidentally.

It complements the existing policies: `docs/callhome_monolingual_screening.md`
(screening categories), `docs/callhome_projection_policy.md` (provenance and
condition mapping), and the screening scaffold/heuristics that currently produce
outcomes and reason codes.

## Why clean admission needs a separate gate
The current screening heuristics are **conservative structural-only** — they
detect parser warnings and empty/non-lexical rows, but they do **not** perform
real language identification. Structural cleanliness ("this row has lexical
content and no warnings") is necessary but **not sufficient** for monolinguality:
a structurally clean row could still contain the other language, a borrowing, or
a code-switch.

Because `clean` directly opens the door to training data, promotion must be gated
by an explicit rule rather than emerging as a side effect of "not blocked and not
flagged." The gate keeps two questions distinct:

- *Is this row structurally usable?* (current heuristics), versus
- *Is this row confidently monolingual in its source language?* (requires
  future source-language validation, not yet implemented).

Only the second question licenses `clean`.

## Current state: zero automatic clean rows
By design, the pipeline today admits **zero** rows to `clean`. A recent local,
aggregate-only dry run over CALLHOME behaved exactly as intended: essentially all
language-containing rows landed in `needs_review` (dominated by
`default_unscreened`), a small fraction were `excluded` as `empty_or_nonlexical`,
a small number carried `parser_warning`, and **no** rows were `clean` — so
condition-candidate counts for `EnglishMono`, `SpanishMono`, and `MonoCont` were
all zero.

This zero-clean state is the correct baseline: with no real language validation
implemented, admitting nothing to training is the safe default. The exact counts
are kept out of this note (Decision B; describe the *type* of result, not a
specific run).

## Clean admission rule
A CALLHOME row may be promoted to `clean` **only if all** of the following hold:

1. It comes from a **supported CALLHOME source directory**: `eng` or `spa`.
2. It has **lexical content** (not empty/non-lexical).
3. It has **no parser warnings** (utterance-level or folded transcript-level).
4. It has **no empty/non-lexical signal**.
5. It has **no possible-foreign-material / possible-code-switching signal**.
6. It has **no unsupported language label**.
7. It **passes whatever future source-language validation we implement** (the
   currently-missing monolinguality check).

Structural cleanliness alone (conditions 1–6) is **necessary but not
sufficient**. Condition 7 — actual source-language validation — is the load-
bearing requirement, and it does not exist yet. Therefore, until condition 7 is
implemented and reviewed, **no row satisfies the rule** and the correct number of
`clean` rows remains zero.

Explicitly: **do not make a lexical row `clean` merely because it comes from
`eng/` or `spa/`.** Source directory establishes the *expected* language; it does
not verify the *actual* language of the row.

## Blocking conditions
Rows meeting any blocking condition are **excluded** and can never be `clean`:

- **Empty / non-lexical** (`empty_or_nonlexical`) → `excluded`.
- **Unsupported language label** (`unsupported_language_label`) → `excluded`.

## Review conditions
Rows meeting any review condition stay **`needs_review`** and can never be
`clean` while the condition holds:

- **Parser warning** (`parser_warning`, including a folded transcript-level
  warning) → `needs_review`.
- **Possible foreign material / possible code-switching**
  (`ambiguous_foreign_material`, `possible_code_switching`) → `needs_review`.
- **Default unscreened** (`default_unscreened`) — no positive clean evidence yet
  → `needs_review`. This is where structurally-fine, unvalidated rows sit today.

## Condition eligibility implications
Promotion to `clean` interacts with condition sourcing exactly as the projection
policy specifies:

- **Clean CALLHOME English** rows may feed **`EnglishMono`** and **`MonoCont`**.
- **Clean CALLHOME Spanish** rows may feed **`SpanishMono`** and **`MonoCont`**.
- **CALLHOME rows must never feed `CsCont`.** `CsCont` is **Bangor-sourced
  only**; row-level language compatibility is not the same as final condition
  sourcing.
- Non-`clean` rows (`needs_review`, `excluded`) are eligible for **no** condition.

Because clean count is currently zero, all three monolingual conditions currently
draw **no** rows from CALLHOME — the intended state until condition 7 exists.

## Safety constraints
- This is a **docs-only** PR; do not implement automatic clean promotion.
- Do not run parsers/screeners on real CALLHOME files as part of this PR.
- Do not quote or print transcript text, header values, participant names,
  speaker IDs, or filenames.
- Raw CALLHOME transcripts, ZIP archives, and transcript-bearing JSONL remain
  **gitignored / never committed**.
- Only **aggregate-only, non-transcript** summaries may be committed, under the
  documented Decision B restrictions.
- Do not create condition JSONL, tokenize, or train in this PR.

## Out of scope
- The **source-language validation method** itself (condition 7) — which
  language-ID or monolinguality signal will be used, and its thresholds.
- Handling of borrowings vs. live switches, and the resolution policy for
  `possible_code_switching` rows.
- Any change to the screening heuristics, projection, or diagnostics code.
- Sampling proportions, train/dev/test splitting, tokenizer choice.
- Building `EnglishMono` / `SpanishMono` / `MonoCont` datasets or condition JSONL.
- Any Bangor / `CsCont` logic.

## Future implementation plan
When implementation begins (a **separate**, reviewed PR):

1. Implement condition 7 (source-language validation) behind an explicit,
   opt-in signal — **synthetic-tested first**, with unit tests proving that
   `clean` is returned only when conditions 1–7 all hold and never on structural
   cleanliness alone.
2. Run a **local, aggregate-only dry run** on the gitignored CALLHOME files,
   keeping any per-row output local/gitignored.
3. **Review the aggregate counts** (how many rows would become `clean`, by
   source and reason) **before** any condition JSONL is created.
4. Only after that review, and only if the counts look right, proceed to
   condition-dataset construction under the existing sourcing invariants
   (CALLHOME → monolingual conditions only; Bangor → `CsCont` only).

Until step 3 is reviewed, automatic clean promotion stays **disabled** and the
`clean` count stays zero.
