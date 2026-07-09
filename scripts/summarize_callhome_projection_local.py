#!/usr/bin/env python
"""LOCAL-ONLY, aggregate-only projection summary for CALLHOME `.cha` files.

Runs the existing parser -> projector -> diagnostics pipeline over local,
GITIGNORED CALLHOME files and prints **aggregate counts only**. It never prints
utterance text, tokens, header values, participant names, raw speaker ids, raw
filenames, ``speaker_ref``, or ``source_file_ref``.

Run from the repo root (defaults to the gitignored data/raw/callhome/):

    python scripts/summarize_callhome_projection_local.py
    python scripts/summarize_callhome_projection_local.py --root path/to/callhome

Expects language subdirectories ``eng/`` and ``spa/`` under the root. Real
screening is not implemented yet, so **every projected row defaults to
``needs_review``** (nothing is admitted to a condition) unless a test supplies a
synthetic screening function. Per Decision B this script **writes no files**;
its stdout is an aggregate, non-transcript summary only. Do not redirect it into
a tracked file, and do not commit generated summaries.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path

from cslm.data.callhome_chat import parse_chat_file
from cslm.data.callhome_project import CallhomeProjectedRow, project_transcript
from cslm.data.callhome_projection_diagnostics import (
    CallhomeProjectionSummary,
    summarize_projected_rows,
)
from cslm.utils.paths import project_root

LANGUAGE_DIRS: tuple[str, ...] = ("eng", "spa")

# A screening function maps (language_label, conversation_id, turn_index) to a
# screening outcome. The real screening step is not implemented, so the default
# marks every row needs_review; tests may inject a synthetic function.
ScreeningFn = Callable[[str, str, int], str]


def default_screening(language_label: str, conversation_id: str, turn_index: int) -> str:
    """Default screening: admit nothing until real screening exists."""
    return "needs_review"


def collect_projected_rows(
    root: Path,
    *,
    screening_fn: ScreeningFn = default_screening,
) -> list[CallhomeProjectedRow]:
    """Parse and project every ``.cha`` under ``root/{eng,spa}`` into rows.

    Files that fail to parse are skipped (never surfaced). Returns projected
    rows only; no transcript-bearing content is retained.
    """
    rows: list[CallhomeProjectedRow] = []
    for label in LANGUAGE_DIRS:
        lang_dir = root / label
        if not lang_dir.exists():
            continue
        for path in sorted(lang_dir.glob("*.cha")):
            try:
                transcript = parse_chat_file(path)
            except (OSError, UnicodeDecodeError, ValueError):
                continue
            screening_by_turn = {
                utt.turn_index: screening_fn(
                    label, transcript.conversation_id, utt.turn_index
                )
                for utt in transcript.utterances
            }
            rows.extend(
                project_transcript(
                    transcript,
                    language_label=label,
                    screening_by_turn=screening_by_turn,
                )
            )
    return rows


def summarize_local_projection(
    root: Path,
    *,
    screening_fn: ScreeningFn = default_screening,
) -> CallhomeProjectionSummary:
    """Collect projected rows under ``root`` and return an aggregate summary.

    A missing root or missing language directories yield an all-zero summary
    (with stable keys) rather than an error.
    """
    rows = collect_projected_rows(root, screening_fn=screening_fn)
    return summarize_projected_rows(rows)


def format_summary_lines(summary: CallhomeProjectionSummary) -> list[str]:
    """Render the summary as aggregate-count lines (no transcript content)."""
    lines = [
        f"total rows                    : {summary.n_rows}",
        "rows by source:",
    ]
    for source, count in summary.rows_by_source.items():
        lines.append(f"  {source:<24}: {count}")
    lines.append("rows by screening outcome:")
    for outcome, count in summary.rows_by_screening_outcome.items():
        lines.append(f"  {outcome:<24}: {count}")
    lines.append("rows by condition candidate:")
    for cond, count in summary.rows_by_condition_candidate.items():
        lines.append(f"  {cond:<24}: {count}")
    lines.append(f"n_needs_review                : {summary.n_needs_review}")
    lines.append(
        f"n_blocked_from_all_conditions : {summary.n_blocked_from_all_conditions}"
    )
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="CALLHOME root containing eng/ and spa/ (default: data/raw/callhome).",
    )
    args = parser.parse_args()

    root = args.root if args.root is not None else project_root() / "data" / "raw" / "callhome"

    if not root.exists():
        print(f"No local CALLHOME root found (expected eng/ and spa/ under {root.name}/).")
        print("Reporting zero counts.")

    summary = summarize_local_projection(root)
    for line in format_summary_lines(summary):
        print(line)


if __name__ == "__main__":
    main()
