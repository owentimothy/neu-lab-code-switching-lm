# Condition Dataset Policy

## Status
- Branch: condition-dataset-planning
- Scope: documentation + a sample-only **aggregate** condition manifest.
- No model training.
- No full-corpus processing (two-file sample only).
- No transcript-bearing condition JSONL written or committed.

## Two layers that must not be conflated

Building condition datasets involves two distinct questions:

1. **Row-level eligibility** — what a projected `UtteranceRow` is *structurally
   compatible* with, recorded in its `condition_candidates` by the projection
   (`conditions.py`).
2. **Final experimental sourcing** — which corpus actually **feeds** each
   condition in the real experiment.

Eligibility is necessary but not sufficient: a row can be *eligible* for a
condition and still not be *sourced* into it.

## Row-level eligibility (unchanged from the projection)

- `en_only` → structurally compatible with English-style monolingual content
  (`EnglishMono`, `MonoCont`, `CsCont`).
- `es_only` → structurally compatible with Spanish-style monolingual content
  (`SpanishMono`, `MonoCont`, `CsCont`).
- `cs_within_utterance` → `CsCont` only.
- **mixed-morpheme review rows** (`needs_review_mixed_morpheme=True`) →
  `CsCont` only (withheld from `EnglishMono` / `SpanishMono` / `MonoCont`).
- `metadata_or_noise`, `punctuation_or_empty`, `mixed_or_uncertain`,
  `neutral_or_bivalent` → **excluded by default** (no conditions).

## Final experimental sourcing (the decision)

**Use dedicated monolingual corpora for `EnglishMono`, `SpanishMono`, and
`MonoCont`. Bangor is not a source for those conditions.**

| Condition | Final source |
|---|---|
| `EnglishMono` | dedicated **English monolingual** corpus |
| `SpanishMono` | dedicated **Spanish monolingual** corpus |
| `MonoCont` | dedicated **English + Spanish monolingual** corpora (no within-utterance CS, no mixed-morpheme review rows) |
| `CsCont` | controlled CALLHOME monolingual filler shared with `MonoCont`, plus genuine code-switched evidence sourced primarily from **Bangor** |

**Rationale.** Bangor is a bilingual interaction corpus, so even its
monolingual-looking (`en_only` / `es_only`) utterances arise in a
code-switching context. Using them as the *final* `EnglishMono` / `SpanishMono`
/ `MonoCont` source would contaminate the monolingual and no-CS baselines. The
key interpretive contrast (`CsCont` vs `MonoCont`) stays clean only if the
mono/no-CS conditions come from genuinely monolingual corpora.

Consequently, **Bangor's role in the final experiment is genuine
code-switched-evidence contribution**, including the separately audited
language categories appropriate to that evidence. The many Bangor
`en_only`/`es_only` rows that are *eligible* for the mono conditions at the row
level are deliberately **not** used as their final source.

## CsCont component roles

`CsCont` may include controlled CALLHOME monolingual filler plus a separately
measured genuine code-switched component sourced primarily from Bangor.
CALLHOME filler must satisfy
`CsCont-English-Monolingual-Filler ⊆ MonoCont-English` and
`CsCont-Spanish-Monolingual-Filler ⊆ MonoCont-Spanish`; it must not be sampled
as an independent CALLHOME inventory. CALLHOME cannot count as genuine
code-switched or mixed-language evidence and cannot satisfy overall,
intrasentential, or intersentential switching quotas. Final component
proportions and token budgets remain deferred.

## Exclusions

`metadata_or_noise`, `punctuation_or_empty`, and `mixed_or_uncertain` never
enter any condition. `neutral_or_bivalent` is excluded **by default** (it may be
opted in later via an explicit inclusion policy, never silently).

## Sampling

- Default to **naturalistic** sampling for now: preserve observed corpus
  proportions.
- This PR does **not** oversample, balance, or target fixed proportions.
- Report **realized proportions only** (with explicit denominators: of all rows
  vs of CsCont rows).
- Balancing / oversampling (`balanced_or_oversampled`) is a **future explicit
  policy decision**, at which point both target and realized proportions must be
  reported.

## The sample manifest (what this PR ships)

`scripts/build_bangor_condition_manifest.py` +
`src/cslm/data/condition_manifest.py` produce an **aggregate manifest** over the
two-file projected sample. It reports:

- row-level `condition_candidates` counts (eligibility);
- the sample-specific Bangor code-switched-evidence contribution, broken down
  by language category;
- the count of Bangor rows *eligible* for the mono conditions but **not** used
  as their final source (making the eligibility/sourcing gap explicit);
- realized proportions (naturalistic);
- invariant checks (below).

It writes aggregate JSON/CSV only. It **does not** write final training
datasets or any per-utterance text/tokens, and `writes_training_datasets` is
`False`.

## Invariant checks (asserted by the manifest + tests)

- `monocont_excludes_cs_within_utterance`
- `monocont_excludes_mixed_morpheme_review`
- `mixed_morpheme_rows_cscont_only`
- `cscont_includes_en_es_cs_rows`
- `excluded_categories_have_no_conditions`
- `neutral_bivalent_excluded_by_default`

## Out of scope (future PRs)

- Writing real condition **JSONL** datasets (transcript-bearing; gitignored).
- Acquiring / wiring the dedicated English and Spanish monolingual corpora for
  `EnglishMono` / `SpanishMono` / `MonoCont`.
- Train/dev/test split assignment at the conversation level (leakage-free); the
  sample is currently all one split.
- Balancing / oversampling and target-proportion policy.
- Shared tokenizer / vocabulary across conditions (kept identical across
  conditions per project rules).
- Switch-site localization diagnostics (separate deferred PR).
