# cs-lm-integrated-syntax

## Repo layout

- `src/cslm/` — package source code.
  - `src/cslm/utils/` — shared utilities (e.g. `paths.py` for project-root resolution).
- `configs/` — configuration files, split by concern:
  - `configs/data/`, `configs/model/`, `configs/train/`, `configs/probes/`
- `data/` — datasets, split by processing stage:
  - `data/raw/`, `data/interim/`, `data/processed/`, `data/toy/`
- `notebooks/` — exploratory notebooks.
- `scripts/` — standalone entry-point scripts.
- `tests/` — pytest test suite.
- `outputs/` — generated artifacts (e.g. `outputs/corpus_summaries/`).

This is currently a skeleton: no model training, probe scoring, or analysis
logic has been implemented yet. The one exception is the toy corpus-
classification pipeline described below, which uses synthetic data only.

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check .
```

## Toy corpus build

`src/cslm/data/` contains the reusable corpus-classification logic:

- `schema.py` — the `UtteranceRow` data schema.
- `classify.py` — a toy heuristic classifier that assigns each utterance a
  `language_category` (`en_only`, `es_only`, `cs_within_utterance`,
  `neutral_or_bivalent`, `punctuation_or_empty`, `mixed_or_uncertain`,
  `metadata_or_noise`).
- `conditions.py` — maps each `language_category` to its eligible
  `condition_candidates` (`EnglishMono`, `SpanishMono`, `MonoCont`, `CsCont`).
- `diagnostics.py` — computes the corpus summary diagnostics required by
  `CLAUDE.md` (counts, percentages against distinct denominators, split
  composition, code-switch transition counts, condition-candidate counts).
- `toy_corpus.py` — synthetic fixture utterances covering all seven
  categories, with deterministic train/dev/test split assignment.
- `io.py` — JSONL / JSON / CSV read-write helpers.

This pipeline only ever runs on synthetic toy data — it does not touch the
real Bangor Miami corpus.

To run the toy corpus build from the repo root:

```bash
python scripts/build_toy_corpus.py
```

This writes:

- `data/processed/toy/utterances.jsonl` — classified toy utterances.
- `outputs/corpus_summaries/toy_condition_summary.json` — full corpus summary.
- `outputs/corpus_summaries/toy_condition_summary.csv` — flattened summary row.

### Utterance schema fields

Each row in `utterances.jsonl` carries the core classification fields plus the
metadata the real Bangor Miami preprocessing will need. The extra fields are
still populated from synthetic toy data only:

- **Token-level annotations**: `raw_text`, `clean_text` (both equal to `text`
  in the toy pipeline; the real pipeline may set `clean_text` to a normalized
  form distinct from `raw_text`/`text`), `tokens`, and `token_language_labels`
  (one label per token). The token labels are:
  - `eng` — English word token.
  - `spa` — Spanish word token.
  - `eng&spa` — bivalent word token (equally valid English/Spanish in
    isolation, e.g. `no`, `a`, `me`).
  - `neutral` — language-neutral word token (proper names, interjections, e.g.
    `Maria`, `Netflix`, `okay`).
  - `punct` — punctuation / symbol token.
  - `other` — unknown / out-of-vocabulary word token.
- **Token-count diagnostics**: `n_tokens_including_punctuation`,
  `n_word_tokens_excluding_punctuation`, `n_english_word_tokens`,
  `n_spanish_word_tokens`, `n_neutral_bivalent_word_tokens`,
  `n_other_word_tokens`, `n_punctuation_tokens`.
  `n_neutral_bivalent_word_tokens` counts `neutral` **and** `eng&spa` word
  tokens together (the language-neutral/bivalent bucket). Only genuinely
  unknown / out-of-vocabulary word tokens (labeled `other`) go in
  `n_other_word_tokens`; they are never folded into the neutral/bivalent
  bucket, so word tokens split cleanly as
  `n_english + n_spanish + n_neutral_bivalent + n_other`. When token-level
  annotations are present, `UtteranceRow` validates that these stored counts
  agree with `token_language_labels`.
- **Ordered-conversation metadata**: `utterance_index`,
  `previous_utterance_id`, `previous_speaker_id`, `previous_language_category`,
  `same_speaker_as_previous`. All `previous_*` fields (and
  `same_speaker_as_previous`) are `null` for the first utterance in a
  conversation.
- **Inter-sentential switch fields**:
  `is_inter_sentential_switch_from_previous` and
  `inter_sentential_switch_direction_from_previous` (`eng_to_spa` /
  `spa_to_eng`), derived from ordered utterances and kept strictly separate
  from the within-utterance (intra-sentential) switch diagnostics. These are
  `null` when a switch is not well-defined (no previous utterance, or either
  utterance lacks a clear dominant language, e.g. code-switched utterances).
- **Review-only heuristic fields**: `borrowing_status`,
  `matrix_language_heuristic`, `equivalence_heuristic`, each paired with a
  `needs_review_*` boolean.

### Aggregate diagnostics

The corpus summary adds aggregate token totals
(`total_tokens_including_punctuation`,
`total_word_tokens_excluding_punctuation`, `total_english_word_tokens`,
`total_spanish_word_tokens`, `total_neutral_bivalent_word_tokens`,
`total_other_word_tokens`, `total_punctuation_tokens`), inter-sentential
switch counts
(`total_inter_sentential_switches`, `inter_sentential_switches_eng_to_spa`,
`inter_sentential_switches_spa_to_eng`,
`inter_sentential_switches_same_speaker`,
`inter_sentential_switches_cross_speaker`), and leakage/duplicate diagnostics
(`n_conversation_ids`, `n_conversation_ids_spanning_multiple_splits`,
`n_duplicate_utterance_ids`, `n_duplicate_utterance_texts`).

Note: `n_word_tokens` now means word tokens **excluding** punctuation (an alias
of `total_word_tokens_excluding_punctuation`).

**How aggregates are computed.** The token-count totals are **summed from each
row's stored per-row token-count fields**, not recomputed from text with the toy
annotator. This preserves gold token-level labels on real corpus rows instead of
overwriting them with heuristic labels. A row that carries no stored token
annotation (empty `tokens`) falls back to annotating its `clean_text`.
Likewise, intra-sentential switch transitions
(`en_to_es_transitions`, `es_to_en_transitions`, `total_switch_transitions`) are
derived from each code-switched row's `token_language_labels` (counting only
`eng`↔`spa` transitions); rows with no stored labels fall back to the toy
text-based counter applied to `clean_text` — never the raw `text`. These
intra-sentential counts are kept strictly separate from the inter-sentential
switch counts.

### Review-only heuristic fields are placeholders

The `borrowing_status`, `matrix_language_heuristic`, and
`equivalence_heuristic` fields are **placeholders for later human
adjudication**. The toy pipeline never assigns them an automatic value (they
stay `null`); it only sets the paired `needs_review_*` flag to `true` for
code-switched utterances to mark what will need review. Do not treat these
fields as ground truth — in particular, automatically assigned equivalence
labels must not be used as ground truth when evaluating switch-site
constraints.
