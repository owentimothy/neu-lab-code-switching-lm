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
  runs the existing pipeline (`callhome_chat` parse → `callhome_project` project
  → `callhome_projection_diagnostics` summarize) over the gitignored
  `data/raw/callhome/{eng,spa}/` folders and prints **aggregate counts only**:
  total rows, rows by source, rows by screening outcome, rows by condition
  candidate, `n_needs_review`, and `n_blocked_from_all_conditions`.
- `tests/test_summarize_callhome_projection_local.py` — **synthetic-only** tests
  over temporary fake CALLHOME directories; no real files are read.

## Screening default
Real monolingual screening (`docs/callhome_monolingual_screening.md`) is not
implemented yet, so **every projected row defaults to `needs_review`** and is
admitted to no condition. Tests may inject a synthetic screening function to
exercise the clean path; the CLI itself always uses the conservative default.

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
A missing root or missing language directory reports **zero counts** rather than
erroring.

(No real projection results are reproduced in this note, by design.)
