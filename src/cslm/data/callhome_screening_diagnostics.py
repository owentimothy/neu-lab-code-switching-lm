"""Aggregate-only diagnostics for CALLHOME screening decisions.

Summarizes a list of :class:`cslm.data.callhome_screening.CallhomeScreeningDecision`
into **counts only** — decisions by outcome and by reason code. Every output is
aggregate and non-transcript: the decisions' ``notes`` (and any other free text)
are never read or emitted here. This is what Decision B permits committing (see
``docs/callhome_ground_rules.md``).

The module intentionally **writes no files** and exposes **no real-data CLI**.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from cslm.data.callhome_screening import (
    REASON_CODES,
    SCREENING_OUTCOMES,
    CallhomeScreeningDecision,
)

# Ordered tuples (not sets): iteration order fixes the key order of serialized
# dicts, and frozenset order is not stable across runs. Both are asserted below
# to cover the authoritative frozensets, so drift is caught at import time.
OUTCOME_ORDER: tuple[str, ...] = ("clean", "needs_review", "excluded")
REASON_CODE_ORDER: tuple[str, ...] = (
    "source_language_expected",
    "ambiguous_foreign_material",
    "possible_code_switching",
    "parser_warning",
    "empty_or_nonlexical",
    "unsupported_language_label",
    "default_unscreened",
)

assert set(OUTCOME_ORDER) == set(SCREENING_OUTCOMES), "OUTCOME_ORDER drift"
assert set(REASON_CODE_ORDER) == set(REASON_CODES), "REASON_CODE_ORDER drift"


def _check_decision_invariants(decisions: list[CallhomeScreeningDecision]) -> None:
    """Raise on any decision with an unknown outcome, empty/unknown reasons.

    The decision class already guards these at construction; re-checking here
    protects the aggregate output from decisions mutated after construction.
    """
    for decision in decisions:
        if decision.outcome not in SCREENING_OUTCOMES:
            raise ValueError(f"unknown screening outcome: {decision.outcome!r}")
        if not decision.reason_codes:
            raise ValueError("reason_codes must not be empty")
        unknown = set(decision.reason_codes) - REASON_CODES
        if unknown:
            raise ValueError(f"unknown reason codes: {sorted(unknown)}")


@dataclass
class CallhomeScreeningSummary:
    """Aggregate, non-transcript summary of screening decisions."""

    n_decisions: int
    decisions_by_outcome: dict[str, int] = field(default_factory=dict)
    # A decision may carry several reason codes, so these buckets overlap and
    # their sum can exceed ``n_decisions`` by design.
    decisions_by_reason_code: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """Nested, JSON-compatible view (aggregate counts only)."""
        return {
            "n_decisions": self.n_decisions,
            "decisions_by_outcome": dict(self.decisions_by_outcome),
            "decisions_by_reason_code": dict(self.decisions_by_reason_code),
        }


def summarize_screening_decisions(
    decisions: list[CallhomeScreeningDecision],
) -> CallhomeScreeningSummary:
    """Aggregate screening decisions into counts, enforcing invariants first."""
    _check_decision_invariants(decisions)

    outcome_counts: Counter[str] = Counter(d.outcome for d in decisions)
    reason_counts: Counter[str] = Counter()
    for decision in decisions:
        reason_counts.update(decision.reason_codes)

    decisions_by_outcome = {
        outcome: outcome_counts.get(outcome, 0) for outcome in OUTCOME_ORDER
    }
    decisions_by_reason_code = {
        code: reason_counts.get(code, 0) for code in REASON_CODE_ORDER
    }

    return CallhomeScreeningSummary(
        n_decisions=len(decisions),
        decisions_by_outcome=decisions_by_outcome,
        decisions_by_reason_code=decisions_by_reason_code,
    )


def flatten_screening_summary(summary: CallhomeScreeningSummary) -> dict[str, int]:
    """Flatten to a single scalar-valued row (aggregate counts only).

    Every value is an ``int`` count; no ``notes`` or transcript-bearing field
    can appear.
    """
    flat: dict[str, int] = {"n_decisions": summary.n_decisions}
    for outcome in OUTCOME_ORDER:
        flat[f"outcome__{outcome}"] = summary.decisions_by_outcome.get(outcome, 0)
    for code in REASON_CODE_ORDER:
        flat[f"reason__{code}"] = summary.decisions_by_reason_code.get(code, 0)
    return flat
