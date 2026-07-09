# CALLHOME Local Structure Scan

## Status
- Local-only tooling; commits **code and synthetic tests only**.
- No real CALLHOME-derived summaries committed (see Decision C in
  `docs/callhome_ground_rules.md`).
- No raw `.cha` files, no ZIP archives, no transcript excerpts committed.
- No projection, no condition datasets, no training.

## What this adds
- `src/cslm/data/callhome_structure_scan.py` — aggregates **structural facts
  only** from parsed `CallhomeTranscript` objects: file / utterance / warning
  counts, header **keys** (never values), dependent-tier **prefixes** (never
  values), and media/timing presence. The module **writes no files**.
- `scripts/scan_callhome_local_structure.py` — a **local-only** CLI that scans
  the gitignored `data/raw/callhome/{eng,spa}/` folders and prints structure-only
  facts to stdout (optional `--json`, never saved).
- `tests/test_callhome_structure_scan.py` — **synthetic-only** tests; no real
  files are read.

## Safety design
- Output contains **no** utterance text, header values, participant names, or
  speaker IDs — only counts, header keys, and tier prefixes.
- Real CALLHOME files stay **local / gitignored** under `data/raw/callhome/`.
- Under **Decision C**, CALLHOME-derived aggregate summaries are **not
  committed**. Real scan outputs remain **local/uncommitted** until TalkBank
  aggregate-summary permission is confirmed (which would allow moving to
  Decision B).
- The script does not write committed outputs; any local JSON is for inspection
  only and must not be redirected into tracked files.

## Usage (local only)
```
python scripts/scan_callhome_local_structure.py
python scripts/scan_callhome_local_structure.py --json
```
If no local files are present, the script prints a short message and exits
without error.

(No real scan results are reproduced in this note, by design.)
