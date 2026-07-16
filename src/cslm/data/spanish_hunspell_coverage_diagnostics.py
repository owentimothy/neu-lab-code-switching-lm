"""Aggregate-only diagnostics for Spanish direct-Hunspell coverage results.

Real-data summaries remain local and uncommitted until the exact output schema
receives its separate privacy review.  This module writes nothing and provides no
corpus or resource interface.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from cslm.data.lexical_coverage import COVERAGE_OUTCOME_ORDER, check_coverage_fields
from cslm.data.spanish_hunspell_coverage import SpanishHunspellCoverageResult


def _check_result_invariants(
    results: list[SpanishHunspellCoverageResult],
) -> None:
    for result in results:
        check_coverage_fields(
            result.outcome,
            result.n_tokens,
            result.n_covered,
            result.n_uncovered,
        )


@dataclass
class SpanishHunspellCoverageSummary:
    """Aggregate corpus-level counts with no token or row breakdown."""

    n_results: int
    results_by_outcome: dict[str, int] = field(default_factory=dict)
    n_tokens_total: int = 0
    n_covered_total: int = 0
    n_uncovered_total: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "n_results": self.n_results,
            "results_by_outcome": dict(self.results_by_outcome),
            "n_tokens_total": self.n_tokens_total,
            "n_covered_total": self.n_covered_total,
            "n_uncovered_total": self.n_uncovered_total,
        }


def summarize_spanish_hunspell_coverage_results(
    results: list[SpanishHunspellCoverageResult],
) -> SpanishHunspellCoverageSummary:
    """Aggregate results only after defensively rechecking every invariant."""
    _check_result_invariants(results)
    outcome_counts: Counter[str] = Counter(result.outcome for result in results)
    results_by_outcome = {
        outcome: outcome_counts.get(outcome, 0)
        for outcome in COVERAGE_OUTCOME_ORDER
    }
    return SpanishHunspellCoverageSummary(
        n_results=len(results),
        results_by_outcome=results_by_outcome,
        n_tokens_total=sum(result.n_tokens for result in results),
        n_covered_total=sum(result.n_covered for result in results),
        n_uncovered_total=sum(result.n_uncovered for result in results),
    )


def flatten_spanish_hunspell_coverage_summary(
    summary: SpanishHunspellCoverageSummary,
) -> dict[str, int]:
    """Return one stable scalar-only aggregate row."""
    flat: dict[str, int] = {"n_results": summary.n_results}
    for outcome in COVERAGE_OUTCOME_ORDER:
        flat[f"outcome__{outcome}"] = summary.results_by_outcome.get(outcome, 0)
    flat["n_tokens_total"] = summary.n_tokens_total
    flat["n_covered_total"] = summary.n_covered_total
    flat["n_uncovered_total"] = summary.n_uncovered_total
    return flat
