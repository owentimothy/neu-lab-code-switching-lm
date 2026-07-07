#!/usr/bin/env python
"""Dry-run: ingest ONLY the two Bangor CG-words sample files.

Run from the repo root:

    python scripts/build_bangor_cgwords_sample.py

Reads (read-only, never modified):
    data/raw/bangor/cgwords/herring1_cgwords.tsv
    data/raw/bangor/cgwords/herring2_cgwords.tsv

Writes:
    data/processed/bangor_sample/bangor_cgwords_sample.jsonl
    outputs/corpus_summaries/bangor_cgwords_sample_summary.json
    outputs/corpus_summaries/bangor_cgwords_sample_summary.csv

This deliberately processes only the two named sample files. It does not glob
the full 56-file corpus, sample conditions, or train anything.
"""

from __future__ import annotations

import json

from cslm.data.bangor_cgwords import (
    flatten_ingestion_summary,
    group_utterances,
    parse_cgwords_file,
    summarize_ingestion,
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

    results = []
    all_utterances = []
    for name in SAMPLE_FILES:
        parsed = parse_cgwords_file(cgwords_dir / name)
        utterances = group_utterances(parsed.words)
        results.append((parsed, utterances))
        all_utterances.extend(utterances)

    jsonl_path = (
        root / "data" / "processed" / "bangor_sample" / "bangor_cgwords_sample.jsonl"
    )
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    with jsonl_path.open("w", encoding="utf-8") as f:
        for utterance in all_utterances:
            f.write(json.dumps(utterance.to_dict(), ensure_ascii=False))
            f.write("\n")

    summary = summarize_ingestion(results)
    summary_json_path = (
        root / "outputs" / "corpus_summaries" / "bangor_cgwords_sample_summary.json"
    )
    summary_csv_path = (
        root / "outputs" / "corpus_summaries" / "bangor_cgwords_sample_summary.csv"
    )
    write_summary_json(summary, summary_json_path)
    write_summary_csv(flatten_ingestion_summary(summary), summary_csv_path)

    print(
        f"Parsed {summary['n_word_rows']} word rows from {summary['n_files']} file(s); "
        f"skipped {summary['n_skipped_footer_lines']} footer line(s)"
    )
    print(f"Grouped into {summary['n_utterances']} utterances")
    print(f"Wrote {jsonl_path.relative_to(root)}")
    print(f"Wrote {summary_json_path.relative_to(root)}")
    print(f"Wrote {summary_csv_path.relative_to(root)}")


if __name__ == "__main__":
    main()
