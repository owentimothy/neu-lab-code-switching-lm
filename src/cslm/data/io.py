"""Read/write helpers for utterance JSONL files and corpus summary reports."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from cslm.data.schema import UtteranceRow


def write_utterances_jsonl(rows: list[UtteranceRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row.to_dict(), ensure_ascii=False))
            f.write("\n")


def read_utterances_jsonl(path: Path) -> list[UtteranceRow]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(UtteranceRow(**json.loads(line)))
    return rows


def write_summary_json(summary_dict: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(summary_dict, f, indent=2, ensure_ascii=False)
        f.write("\n")


def write_summary_csv(flat_row: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(flat_row.keys()))
        writer.writeheader()
        writer.writerow(flat_row)
