#!/usr/bin/env python
"""LOCAL-ONLY, aggregate-only projection + screening summary for CALLHOME `.cha`.

Runs the full local pipeline over GITIGNORED CALLHOME files:

    parse (callhome_chat)
      -> screen with conservative heuristics (callhome_screening_heuristics)
      -> combine with default (not_validated) source validation
         (callhome_source_validation)
      -> project using the final outcomes (callhome_project)
      -> aggregate projection + screening diagnostics

and prints **aggregate counts only**. It never prints utterance text, tokens,
header values, participant names, raw speaker ids, raw filenames, ``speaker_ref``,
``source_file_ref``, or screening ``notes``.

Run from the repo root (defaults to the gitignored data/raw/callhome/):

    python scripts/summarize_callhome_projection_local.py
    python scripts/summarize_callhome_projection_local.py --root path/to/callhome

Expects language subdirectories ``eng/`` and ``spa/`` under the root. Screening
is conservative structural-only (parser warnings, empty/non-lexical rows) — it is
**not** real language ID, so no row is auto-marked ``clean`` and lexical rows
stay ``needs_review``. Per Decision B this script **writes no files**; its stdout
is an aggregate, non-transcript summary only. Do not redirect it into a tracked
file, and do not commit generated summaries.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from cslm.data.callhome_chat import parse_chat_file
from cslm.data.callhome_project import CallhomeProjectedRow, project_transcript
from cslm.data.callhome_projection_diagnostics import (
    CallhomeProjectionSummary,
    summarize_projected_rows,
)
from cslm.data.callhome_screening import CallhomeScreeningDecision
from cslm.data.callhome_screening_diagnostics import (
    CallhomeScreeningSummary,
    summarize_screening_decisions,
)
from cslm.data.callhome_screening_heuristics import build_screening_decisions_by_turn
from cslm.data.callhome_source_validation import (
    combine_screening_and_validation,
    default_source_validation,
)
from cslm.utils.paths import project_root

LANGUAGE_DIRS: tuple[str, ...] = ("eng", "spa")


@dataclass
class LocalCallhomeSummaries:
    """The aggregate projection and screening summaries for a local scan."""

    projection: CallhomeProjectionSummary
    screening: CallhomeScreeningSummary


def collect_rows_and_decisions(
    root: Path,
) -> tuple[list[CallhomeProjectedRow], list[CallhomeScreeningDecision]]:
    """Parse, screen, validate, and project every ``.cha`` under ``root/{eng,spa}``.

    Structural screening heuristics produce a per-turn ``CallhomeScreeningDecision``;
    each is combined with the **default** (``not_validated``) source-language
    validation via ``combine_screening_and_validation`` to yield the final
    outcome that drives projection. Because the default never validates, no row
    becomes ``clean`` here (source directory alone is not verification). This wires
    in the validation join point while preserving the zero-clean baseline.

    ``explicit_source_validation`` is deliberately **not** used in this real-data
    script. Files that fail to parse are skipped (never surfaced). Returns
    projected rows and structural screening decisions only — no transcript-bearing
    content is retained.
    """
    rows: list[CallhomeProjectedRow] = []
    decisions: list[CallhomeScreeningDecision] = []
    for label in LANGUAGE_DIRS:
        lang_dir = root / label
        if not lang_dir.exists():
            continue
        # One content-free default validation per language directory. Reused
        # across turns; it never marks a row validated.
        validation = default_source_validation(label)
        for path in sorted(lang_dir.glob("*.cha")):
            try:
                transcript = parse_chat_file(path)
            except (OSError, UnicodeDecodeError, ValueError):
                continue
            turn_decisions = build_screening_decisions_by_turn(
                transcript, language_label=label
            )
            outcomes = {
                turn: combine_screening_and_validation(decision, validation)
                for turn, decision in turn_decisions.items()
            }
            rows.extend(
                project_transcript(
                    transcript, language_label=label, screening_by_turn=outcomes
                )
            )
            decisions.extend(turn_decisions.values())
    return rows, decisions


def summarize_local(root: Path) -> LocalCallhomeSummaries:
    """Collect rows + decisions under ``root`` and return aggregate summaries.

    A missing root or missing language directories yield all-zero summaries
    (with stable keys) rather than an error.
    """
    rows, decisions = collect_rows_and_decisions(root)
    return LocalCallhomeSummaries(
        projection=summarize_projected_rows(rows),
        screening=summarize_screening_decisions(decisions),
    )


def format_summary_lines(summaries: LocalCallhomeSummaries) -> list[str]:
    """Render both summaries as aggregate-count lines (no transcript content)."""
    proj = summaries.projection
    scr = summaries.screening

    lines = [
        "== projection summary ==",
        f"total rows                    : {proj.n_rows}",
        "rows by source:",
    ]
    for source, count in proj.rows_by_source.items():
        lines.append(f"  {source:<24}: {count}")
    lines.append("rows by screening outcome:")
    for outcome, count in proj.rows_by_screening_outcome.items():
        lines.append(f"  {outcome:<24}: {count}")
    lines.append("rows by condition candidate:")
    for cond, count in proj.rows_by_condition_candidate.items():
        lines.append(f"  {cond:<24}: {count}")
    lines.append(f"n_needs_review                : {proj.n_needs_review}")
    lines.append(f"n_blocked_from_all_conditions : {proj.n_blocked_from_all_conditions}")

    lines.append("")
    lines.append("== screening summary ==")
    lines.append(f"total decisions               : {scr.n_decisions}")
    lines.append("decisions by outcome:")
    for outcome, count in scr.decisions_by_outcome.items():
        lines.append(f"  {outcome:<24}: {count}")
    lines.append("decisions by reason code:")
    for code, count in scr.decisions_by_reason_code.items():
        lines.append(f"  {code:<26}: {count}")
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

    summaries = summarize_local(root)
    for line in format_summary_lines(summaries):
        print(line)


if __name__ == "__main__":
    main()
