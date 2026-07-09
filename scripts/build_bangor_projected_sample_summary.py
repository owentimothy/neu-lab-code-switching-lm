#!/usr/bin/env python
"""Dry-run: aggregate diagnostics over the PROJECTED two-file Bangor sample.

Run from the repo root:

    python scripts/build_bangor_projected_sample_summary.py

Reads (read-only, never modified):
    data/raw/bangor/cgwords/herring1_cgwords.tsv
    data/raw/bangor/cgwords/herring2_cgwords.tsv

Writes (aggregate-only, no transcript / tokens / per-utterance rows):
    outputs/corpus_summaries/bangor_projected_sample_summary.json
    outputs/corpus_summaries/bangor_projected_sample_summary.csv

Processes only the two named sample files. It does not glob the full corpus,
train anything, or write per-utterance JSONL.
"""

from __future__ import annotations

from cslm.data.bangor_cgwords import group_utterances, parse_cgwords_file
from cslm.data.bangor_project import project_utterances
from cslm.data.bangor_sample_diagnostics import (
    build_projected_sample_summary,
    flatten_projected_sample_summary,
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
    summary = build_projected_sample_summary(
        rows,
        n_files=len(SAMPLE_FILES),
        n_source_word_rows=n_source_word_rows,
    )

    summary_json_path = (
        root / "outputs" / "corpus_summaries" / "bangor_projected_sample_summary.json"
    )
    summary_csv_path = (
        root / "outputs" / "corpus_summaries" / "bangor_projected_sample_summary.csv"
    )
    write_summary_json(summary, summary_json_path)
    write_summary_csv(flatten_projected_sample_summary(summary), summary_csv_path)

    print(
        f"Projected {summary['n_source_word_rows']} source word rows from "
        f"{summary['n_files']} file(s) into {summary['n_projected_utterance_rows']} rows"
    )
    print(f"Checks: {summary['checks']}")
    print(f"Wrote {summary_json_path.relative_to(root)}")
    print(f"Wrote {summary_csv_path.relative_to(root)}")


if __name__ == "__main__":
    main()
