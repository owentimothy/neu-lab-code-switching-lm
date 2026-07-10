#!/usr/bin/env python
"""DISABLED, aggregate-only dry-run scaffold for local CALLHOME lexicon validation.

This is a **script stub only**. It defines the *shape* of a future local-only
aggregate dry run (see ``docs/callhome_lexicon_dry_run_plan.md``) without wiring
anything real. Concretely, this script:

* is a **local-only** dry-run scaffold; it takes **explicit local paths only**,
* performs **no downloads** and no network access,
* commits **no real resources** (no lexicon files, no derived wordlists),
* emits **no CALLHOME text** — output is **aggregate-only** counts,
* is **disabled / unwired**: it does not run a real dry run, does not parse real
  CALLHOME, does not load real lexicons, and is **not** imported by
  ``scripts/summarize_callhome_projection_local.py``,
* enables **no clean promotion**,
* creates **no condition JSONL**,
* performs **no tokenization for dataset creation and no model training**.

The only executable behavior here is a safe refusal: without an explicit opt-in
flag the CLI prints a message and processes nothing, and even with the opt-in the
real path is intentionally unimplemented (it raises). The reusable piece is the
pure :func:`summarize_dry_run` aggregator, which turns **synthetic** projected
rows and validation decisions into counts only — never transcript-bearing fields.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field

from cslm.data.callhome_project import CallhomeProjectedRow
from cslm.data.callhome_projection_diagnostics import summarize_projected_rows
from cslm.data.callhome_source_validation import CallhomeSourceValidationDecision
from cslm.data.callhome_source_validation_diagnostics import (
    summarize_source_validation_decisions,
)

# Shown when the CLI is invoked without the explicit opt-in. No data is touched.
_REFUSAL_MESSAGE = (
    "Refusing to run: this is a DISABLED dry-run scaffold. No real CALLHOME data "
    "is parsed, no lexicons are loaded, and nothing is written. Real local dry-run "
    "wiring is intentionally not implemented here; it must be added later in a "
    "separate, explicitly approved PR. See docs/callhome_lexicon_dry_run_plan.md."
)


@dataclass
class DryRunValidationSummary:
    """Aggregate, non-transcript summary of a (future) local lexicon dry run.

    Every field is an integer or a ``dict[str, int]`` keyed by safe fixed labels
    (source tags, screening outcomes, condition names, validation status/method/
    reason labels). No transcript text, token strings, speaker ids/refs, source
    file refs, filenames, media ids, or header values can appear here.
    """

    total_rows: int
    rows_by_source: dict[str, int] = field(default_factory=dict)
    rows_by_screening_outcome: dict[str, int] = field(default_factory=dict)
    structurally_eligible_rows: int = 0
    validation_status_counts: dict[str, int] = field(default_factory=dict)
    validation_method_counts: dict[str, int] = field(default_factory=dict)
    validation_reason_counts: dict[str, int] = field(default_factory=dict)
    # Rows *eligible for* each monolingual condition (EnglishMono / SpanishMono /
    # MonoCont). CsCont never appears — CALLHOME is monolingual-sourced only, and
    # the underlying projection diagnostics reject any CsCont candidate.
    potential_condition_candidates: dict[str, int] = field(default_factory=dict)
    n_blocked_from_all_conditions: int = 0

    def to_dict(self) -> dict[str, object]:
        """JSON-compatible view: integers and dicts of integers only."""
        return {
            "total_rows": self.total_rows,
            "rows_by_source": dict(self.rows_by_source),
            "rows_by_screening_outcome": dict(self.rows_by_screening_outcome),
            "structurally_eligible_rows": self.structurally_eligible_rows,
            "validation_status_counts": dict(self.validation_status_counts),
            "validation_method_counts": dict(self.validation_method_counts),
            "validation_reason_counts": dict(self.validation_reason_counts),
            "potential_condition_candidates": dict(self.potential_condition_candidates),
            "n_blocked_from_all_conditions": self.n_blocked_from_all_conditions,
        }


def summarize_dry_run(
    rows: list[CallhomeProjectedRow],
    validation_decisions: list[CallhomeSourceValidationDecision],
) -> DryRunValidationSummary:
    """Aggregate **synthetic** projected rows + validation decisions into counts.

    Pure and side-effect-free. Delegates to the existing aggregate-only
    diagnostics, which enforce the CALLHOME invariants first — in particular any
    row carrying a ``CsCont`` (or other non-monolingual) condition candidate
    raises before any count is produced, so CsCont can never be counted here.

    ``structurally_eligible_rows`` is a final-outcome-based count of rows not
    ``excluded`` by screening (an upper bound on clean eligibility); it does not
    re-derive per-reason structural checks, which are not available on a projected
    row. No transcript-bearing value is read or emitted.
    """
    projection = summarize_projected_rows(rows)
    validation = summarize_source_validation_decisions(validation_decisions)

    excluded = projection.rows_by_screening_outcome.get("excluded", 0)
    return DryRunValidationSummary(
        total_rows=projection.n_rows,
        rows_by_source=dict(projection.rows_by_source),
        rows_by_screening_outcome=dict(projection.rows_by_screening_outcome),
        structurally_eligible_rows=projection.n_rows - excluded,
        validation_status_counts=dict(validation.decisions_by_validated_status),
        validation_method_counts=dict(validation.decisions_by_validation_method),
        validation_reason_counts=dict(validation.decisions_by_reason_code),
        potential_condition_candidates=dict(projection.rows_by_condition_candidate),
        n_blocked_from_all_conditions=projection.n_blocked_from_all_conditions,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    """CLI *shape* for a future local dry run (arguments only; nothing runs)."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--callhome-root",
        default=None,
        help="Future: local CALLHOME root with eng/ and spa/ (gitignored). Unused here.",
    )
    parser.add_argument(
        "--english-lexicon",
        default=None,
        help="Future: explicit local path to an approved English lexicon. Unused here.",
    )
    parser.add_argument(
        "--spanish-lexicon",
        default=None,
        help="Future: explicit local path to an approved Spanish lexicon. Unused here.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Future: local path for aggregate-only output (gitignored). Unused here.",
    )
    parser.add_argument(
        "--allow-real-dry-run",
        action="store_true",
        help="Opt-in for the future real dry run. Not implemented; raises if set.",
    )
    return parser


def run_real_dry_run(args: argparse.Namespace) -> None:
    """Placeholder for the future local-only real dry run — intentionally absent.

    Real wiring (loading approved local lexicons, applying validation to real
    CALLHOME rows) must be added in a separate, explicitly approved PR. Until
    then this raises rather than doing anything, so no real dry run can run from
    this stub.
    """
    raise NotImplementedError(
        "The real local CALLHOME lexicon dry run is not implemented in this stub. "
        "It must be added in a separate, explicitly approved PR that wires the "
        "loader/validator over local resources. No real dry run runs here."
    )


def main(argv: list[str] | None = None) -> int:
    """Refuse by default; even when opted in, the real path is unimplemented."""
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if not args.allow_real_dry_run:
        print(_REFUSAL_MESSAGE)
        return 0
    # Explicit opt-in still hits the unimplemented placeholder (raises).
    run_real_dry_run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
