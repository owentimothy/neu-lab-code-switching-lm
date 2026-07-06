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

This is currently a skeleton: no corpus processing, model training, probe
scoring, or analysis logic has been implemented yet.

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check .
```
