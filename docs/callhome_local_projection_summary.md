# CALLHOME Local Projection Summary

## Status
- Local-only tooling; commits **code and synthetic tests only**.
- No real CALLHOME-derived summaries committed (aggregate-only summaries are
  permitted under **Decision B**, but generated outputs stay local/uncommitted
  for this PR — see `docs/callhome_ground_rules.md`).
- No raw `.cha` files, no ZIP archives, no transcript excerpts committed.
- No condition JSONL, no tokenization, no training.

## What this adds
- `scripts/summarize_callhome_projection_local.py` — a **local-only** CLI that
  runs the full pipeline (`callhome_chat` parse → `callhome_screening_heuristics`
  screen → **combine with default (`not_validated`) source validation**
  (`callhome_source_validation`) → `callhome_project` project →
  `callhome_projection_diagnostics` + `callhome_screening_diagnostics` summarize)
  over the gitignored `data/raw/callhome/{eng,spa}/` folders and prints
  **aggregate counts only**: a projection summary (total rows, rows by source, by
  screening outcome, by condition candidate, `n_needs_review`,
  `n_blocked_from_all_conditions`) and a screening summary (decisions by outcome,
  decisions by reason code).
- `tests/test_summarize_callhome_projection_local.py` — **synthetic-only** tests
  over temporary fake CALLHOME directories; no real files are read.

## Screening behavior
Screening is **conservative structural-only** (parser warnings and
empty/non-lexical rows); it is **not** real language ID
(`docs/callhome_monolingual_screening.md`). Structural decisions are then
combined with the **default source-language validation** (`not_validated`), which
never marks a row validated — so the CLI never auto-marks a row `clean`
(source directory alone is *expected* language, not *verified* language; see
`docs/callhome_source_validation_integration_policy.md`). Consequently lexical
rows stay `needs_review` / `default_unscreened` (admitted to no condition), and
punctuation-/residue-only rows are `excluded` / `empty_or_nonlexical`. The
`clean` path requires positive source validation (only `explicit_source_validation`
in unit tests today) and is **never** exercised by this CLI.

## Safety design
- Output contains **no** utterance text, tokens, header values, participant
  names, raw speaker ids, raw filenames, `speaker_ref`, or `source_file_ref` —
  only aggregate counts.
- CALLHOME rows are **never** eligible for `CsCont` (Bangor-sourced only); the
  diagnostics layer enforces this invariant.
- Real CALLHOME files stay **local / gitignored** under `data/raw/callhome/`.
- The script **writes no files** and takes no `--output` flag; its stdout is an
  aggregate, non-transcript summary. Do not redirect it into a tracked file, and
  do not commit generated summaries.

## Usage (local only)
```
python scripts/summarize_callhome_projection_local.py
python scripts/summarize_callhome_projection_local.py --root path/to/callhome
```
Missing roots or language directories are handled without error; missing roots
report **zero counts**, while available language directories are summarized
normally.

(No real projection results are reproduced in this note, by design.)
