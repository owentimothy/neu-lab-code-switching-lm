#!/usr/bin/env python
"""Dry-run: aggregate condition manifest over the PROJECTED two-file Bangor sample.

Run from the repo root:

    python scripts/build_bangor_condition_manifest.py

Reads (read-only, never modified):
    data/raw/bangor/cgwords/herring1_cgwords.tsv
    data/raw/bangor/cgwords/herring2_cgwords.tsv

Writes (aggregate-only; no transcript / tokens / per-utterance rows):
    outputs/corpus_summaries/bangor_condition_manifest.json
    outputs/corpus_summaries/bangor_condition_manifest.csv

Processes only the two named sample files. It does NOT write final condition
training datasets, glob the full corpus, or train anything.
"""

from __future__ import annotations

from cslm.data.bangor_cgwords import group_utterances, parse_cgwords_file
from cslm.data.bangor_project import project_utterances
from cslm.data.condition_manifest import (
    build_condition_manifest,
    flatten_condition_manifest,
)
from cslm.data.io import write_summary_csv, write_summary_json
from cslm.utils.paths import project_root

SAMPLE_FILES = (
    "herring1_cgwords.tsv",
    "herring2_cgwords.tsv",
)


def main() -> None:
    root = project_root()
    cgwords_dir = root / "data" / "raw" / "bangor" / "cgwords"

    all_utterances = []
    n_source_word_rows = 0
    for name in SAMPLE_FILES:
        parsed = parse_cgwords_file(cgwords_dir / name)
        n_source_word_rows += len(parsed.words)
        all_utterances.extend(group_utterances(parsed.words))

    rows = project_utterances(all_utterances)
    manifest = build_condition_manifest(
        rows,
        n_files=len(SAMPLE_FILES),
        n_source_word_rows=n_source_word_rows,
    )

    json_path = root / "outputs" / "corpus_summaries" / "bangor_condition_manifest.json"
    csv_path = root / "outputs" / "corpus_summaries" / "bangor_condition_manifest.csv"
    write_summary_json(manifest, json_path)
    write_summary_csv(flatten_condition_manifest(manifest), csv_path)

    print(
        f"Projected {manifest['n_projected_utterance_rows']} rows from "
        f"{manifest['n_files']} file(s); Bangor CsCont contribution="
        f"{manifest['bangor_cscont_contribution']['n_rows']} rows"
    )
    print(f"Checks: {manifest['checks']}")
    print(f"Wrote {json_path.relative_to(root)}")
    print(f"Wrote {csv_path.relative_to(root)}")


if __name__ == "__main__":
    main()
