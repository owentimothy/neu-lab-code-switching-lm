#!/usr/bin/env python
"""Build the toy corpus: classify synthetic utterances and write diagnostics.

Run from the repo root:

    python scripts/build_toy_corpus.py

Writes:
    data/processed/toy/utterances.jsonl
    outputs/corpus_summaries/toy_condition_summary.json
    outputs/corpus_summaries/toy_condition_summary.csv
"""

from __future__ import annotations

from cslm.data.diagnostics import build_corpus_summary
from cslm.data.io import write_summary_csv, write_summary_json, write_utterances_jsonl
from cslm.data.toy_corpus import SOURCE_NAME, build_toy_rows
from cslm.utils.paths import project_root

SEED = 0


def main() -> None:
    root = project_root()
    rows = build_toy_rows(seed=SEED)

    utterances_path = root / "data" / "processed" / "toy" / "utterances.jsonl"
    write_utterances_jsonl(rows, utterances_path)

    summary = build_corpus_summary(
        rows,
        corpus_name="toy",
        data_sources=[SOURCE_NAME],
        seed=SEED,
    )

    summary_json_path = root / "outputs" / "corpus_summaries" / "toy_condition_summary.json"
    summary_csv_path = root / "outputs" / "corpus_summaries" / "toy_condition_summary.csv"
    write_summary_json(summary.to_dict(), summary_json_path)
    write_summary_csv(summary.to_flat_row(), summary_csv_path)

    print(f"Wrote {len(rows)} utterances to {utterances_path.relative_to(root)}")
    print(f"Wrote summary to {summary_json_path.relative_to(root)}")
    print(f"Wrote summary to {summary_csv_path.relative_to(root)}")


if __name__ == "__main__":
    main()
