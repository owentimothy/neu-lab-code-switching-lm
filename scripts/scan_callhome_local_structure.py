#!/usr/bin/env python
"""LOCAL-ONLY, content-free structural scan of CALLHOME `.cha` files.

Run from the repo root:

    python scripts/scan_callhome_local_structure.py
    python scripts/scan_callhome_local_structure.py --json

Reads local, GITIGNORED folders only:
    data/raw/callhome/eng/*.cha
    data/raw/callhome/spa/*.cha

Prints STRUCTURE ONLY — file/utterance/warning counts, header KEYS, dependent
tier PREFIXES, and media/timing presence. It never prints utterance text, header
values, participant names, speaker IDs, or filenames.

Per CALLHOME ground-rules Decision C, this script does NOT write any committed
output. `--json` prints a safe structural summary to stdout only (never saved).
Do not redirect its output into tracked files.
"""

from __future__ import annotations

import argparse
import json

from cslm.data.callhome_structure_scan import (
    flatten_structure_summary,
    scan_callhome_transcripts,
)
from cslm.utils.paths import project_root

LANGUAGE_DIRS = ("eng", "spa")


def _print_human(summary) -> None:
    # Structural facts only; header KEYS and tier PREFIXES are format markers,
    # not content.
    print(f"[{summary.language_label}]")
    print(f"  files scanned          : {summary.n_files}")
    print(f"  transcripts parsed     : {summary.n_transcripts_parsed}")
    print(f"  utterances             : {summary.n_utterances}")
    print(f"  parser warnings (count): {summary.n_parser_warnings}")
    print(f"  files w/ @Languages    : {summary.n_files_with_languages_header}")
    print(f"  files w/ @Media        : {summary.n_files_with_media_header}")
    print(f"  files w/ dependent tiers: {summary.n_files_with_dependent_tiers}")
    print(f"  utterances w/ media_id : {summary.n_utterances_with_media_id}")
    media_present = (
        summary.n_files_with_media_header > 0
        or summary.n_utterances_with_media_id > 0
        or "%snd" in summary.dependent_tier_prefix_counts
        or "%mov" in summary.dependent_tier_prefix_counts
    )
    print(f"  media/timing present   : {media_present}")
    print(f"  header keys            : {sorted(summary.header_key_counts)}")
    print(f"  dependent tier prefixes: {sorted(summary.dependent_tier_prefix_counts)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print a safe structural summary as JSON to stdout (never saved).",
    )
    args = parser.parse_args()

    root = project_root()
    base = root / "data" / "raw" / "callhome"
    if not base.exists():
        print("No local CALLHOME data found at data/raw/callhome/ — nothing to scan.")
        return

    summaries = []
    for label in LANGUAGE_DIRS:
        lang_dir = base / label
        if not lang_dir.exists():
            print(f"[{label}] directory missing — skipped.")
            continue
        paths = sorted(lang_dir.glob("*.cha"))
        if not paths:
            print(f"[{label}] no .cha files found — skipped.")
            continue
        summaries.append(scan_callhome_transcripts(paths, language_label=label))

    if not summaries:
        print("No CALLHOME .cha files found under data/raw/callhome/{eng,spa}/.")
        return

    if args.json:
        print(json.dumps([flatten_structure_summary(s) for s in summaries], indent=2))
    else:
        for summary in summaries:
            _print_human(summary)


if __name__ == "__main__":
    main()
