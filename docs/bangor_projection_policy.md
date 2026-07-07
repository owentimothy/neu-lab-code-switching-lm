# Bangor CG-words → UtteranceRow projection policy

Status: agreed policy captured before implementing the
`BangorUtterance → UtteranceRow` projection. No code accompanies this note.

This note deliberately avoids verbatim Bangor transcript text and corpus proper
names; token classes are described abstractly by their source `langid` / `auto`
pattern.

## 1. Source-faithful layer vs. experiment-facing layer

Two layers are kept strictly separate:

- **Source-faithful layer** — `BangorWord` and `BangorUtterance`. These preserve
  the original CG-words export verbatim: surface, `location`, `speaker`,
  `filename`, `utterance_id`, and the original `langid` (including
  `eng&spa+eng`, `eng+spa`, `999`, `www`). This layer is never mutated by
  projection, and nothing is deleted from it.
- **Experiment-facing layer** — `UtteranceRow`. This is the *projected*
  representation used for conditions, diagnostics, and (later) training. It may
  apply normalization and policy decisions that the source layer does not.

The bridge between the layers is **`source_token_language_labels`**: a per-token
list on `UtteranceRow` that stores the original Bangor `langid` for each token,
parallel to the normalized `token_language_labels`. Normalization is therefore
always **lossless and auditable** — the raw label rides alongside the projected
one.

## 2. Schema extensions

The projection requires a bounded, backward-compatible extension of
`UtteranceRow`:

- **New token labels** in `TOKEN_LANGUAGE_LABELS`:
  - `mixed_morpheme`
  - `metadata`
- **New token-count fields:**
  - `n_mixed_morpheme_word_tokens`
  - `n_metadata_tokens`
- **New fields:**
  - `source_token_language_labels` (nullable; raw Bangor `langid` per token,
    validated to match token length when present; no controlled vocabulary)
  - `needs_review_mixed_morpheme` (bool, default `False`)

The count reconciliation in the schema is updated so that:

- `n_word_tokens_excluding_punctuation` =
  `eng + spa + neutral_bivalent + other + mixed_morpheme`
- `n_tokens_including_punctuation` =
  `n_word_tokens_excluding_punctuation + n_punctuation_tokens + n_metadata_tokens`

`metadata` is counted as neither a word token nor punctuation.

## 3. Mixed-morpheme policy

Applies to source labels with within-word `+` mixing (`eng+spa`, `spa+eng`,
`eng&spa+eng`), normalized to the token label `mixed_morpheme`.

- `mixed_morpheme` is **not** collapsed into `other`.
- `metadata` is **not** collapsed into `other` or `punct`.
- `mixed_morpheme` tokens **do not** create ordinary `eng ↔ spa` switch
  transitions (only `eng`/`spa` labels contribute to transition sequences).
- `mixed_morpheme` tokens **do not** automatically promote a row to
  `cs_within_utterance`.
- Rows carrying `needs_review_mixed_morpheme = true` are **withheld from
  `EnglishMono`, `SpanishMono`, and `MonoCont` by default**, to keep the
  monolingual and no-code-switching conditions clean of contested within-word
  mixing.
- Default condition assignment for such rows is therefore **`CsCont` only**, or
  **excluded pending later human review** — never a clean monolingual or
  `MonoCont` baseline.

## 4. Metadata / `www` policy

- A **`www` surface maps to `metadata` regardless of the source `langid`**
  (the export sometimes mislabels the redaction marker as bivalent). The surface
  check wins.
- **Metadata-only rows receive no model-training condition candidates**
  (`condition_candidates = []`); redacted / non-consenting speech never enters a
  training condition.
- Metadata tokens count toward `n_tokens_including_punctuation` but **not**
  toward `n_word_tokens_excluding_punctuation` — they are not linguistic word
  material.
- Metadata-only rows are **projected, not silently dropped**, so they remain in
  the exclusion diagnostics with a recorded reason.

## 5. Disfluency / interactional-token policy

Applies to nonlexical filled pauses and backchannels (the `um`-type and
`mmhm`-type class), which in the export typically carry `langid = eng` with an
`auto` gloss ending in `.IM`.

- **Preserve the source `langid`** in `source_token_language_labels`; **do not
  overwrite Bangor annotations**.
- For the projected `token_language_labels`, **neutralize a conservative,
  curated list** of nonlexical filled pauses / backchannels to `neutral`.
- **Do not** map these to `other` (they are known material) or `metadata` (they
  are spoken material, unlike `www`).
- **Do not blanket-neutralize every `.IM` token.** `.IM` may be used only to
  surface candidates for the curated list. Some interjections are
  language-specific and analytically meaningful and must remain `eng` / `spa`.
- Neutralized disfluencies **do not** create ordinary `eng ↔ spa` switch
  transitions.
- Neutralized disfluencies **should not be the sole reason** an utterance
  becomes `cs_within_utterance`.
- If **real lexical English and real lexical Spanish remain after
  neutralization**, the row is **still `cs_within_utterance`**.
- **Filler-only / backchannel-only rows should not enter clean model-training
  conditions by default** (all-`neutral` + punctuation → `neutral_or_bivalent`
  → no condition candidates unless an explicit inclusion policy is set).
- **`neutralize_disfluencies` defaults ON** for the experiment-facing
  projection. The projected `language_category` is re-derived from the
  post-neutralization labels so labels and category always agree; the
  source-faithful `BangorUtterance` category is retained for audit.

## 6. Performance / competence distinction

- **Do not delete** false starts, repetitions, repairs, filled pauses, or
  backchannels from the source corpus.
- **Naturalistic training data preserves dialogue structure** — removing
  disfluency by default would create an edited corpus and could shift switch
  positions, utterance length, and syntactic context. Manage disfluency through
  annotation and condition eligibility, not deletion.
- **Probe stimuli are clean and controlled**, so performance noise does not
  contaminate competence measurements.
- **Later**, build **optional lightly filtered views** (fillers/backchannels
  removed) for sensitivity analysis only — derived from the preserved source,
  never replacing it.

## 7. Tests required before / with implementation

- Source `langid`s are preserved in `source_token_language_labels`.
- `mixed_morpheme` tokens are projected and counted
  (`n_mixed_morpheme_word_tokens`).
- `metadata` tokens are projected and counted (`n_metadata_tokens`).
- A `www` surface is handled as `metadata` regardless of source `langid`.
- Disfluency tokens are neutralized in projected `token_language_labels` but
  preserved in `source_token_language_labels`.
- Filler-only / backchannel-only rows receive no condition candidates.
- `needs_review_mixed_morpheme` rows are withheld from `EnglishMono`,
  `SpanishMono`, and `MonoCont`.
- Neutralized fillers do not create `eng ↔ spa` switch transitions.
- Rows with real lexical English + Spanish remain `cs_within_utterance` after
  neutralization.
- The toy word-list classifier is never used on Bangor rows.
