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
