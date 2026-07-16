"""Aggregate-only diagnostics for English SCOWL coverage results.

Summarizes a list of
:class:`cslm.data.english_scowl_coverage.EnglishCoverageResult` into **corpus-level
counts only**. Every output is aggregate and non-transcript: no utterance text,
tokens, source tag, filename, conversation id, speaker id, or per-row breakdown
appears here.

The summary is deliberately **flat and corpus-level** — there is no source,
file, conversation, speaker, row, or per-token breakdown. This is a privacy
choice, not an omission: a finely sliced count can single out one row, so the
schema stays coarse (see the reconstructive-risk note below).

**Decision B privacy status:** these aggregate categories are *new* — they are
**not** among the aggregate examples reviewed for commit in
``docs/callhome_ground_rules.md``. Until a separate Decision B per-output privacy
review approves this exact schema (confirming it is aggregate-only,
non-transcript, non-reconstructive, and identifier-free, and addressing
low-cardinality cells), any summary computed over **real** CALLHOME data remains
**local and uncommitted**. This module writes no files and exposes no real-data
CLI; only synthetic results appear in tests.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from cslm.data.english_scowl_coverage import (
    COVERAGE_OUTCOME_ORDER,
    EnglishCoverageResult,
    _check_coverage_fields,
)


def _check_result_invariants(results: list[EnglishCoverageResult]) -> None:
    """Raise on any result whose outcome/counts are inconsistent.

    ``EnglishCoverageResult`` guards these at construction; re-checking here with
    the **same** shared invariant (:func:`_check_coverage_fields`) protects the
    aggregate output from a result mutated after construction. Importing the
    shared underscore helper across these two modules mirrors the existing
    ``callhome_source_validation`` / ``…_diagnostics`` pattern.
    """
    for result in results:
        _check_coverage_fields(
            result.outcome, result.n_tokens, result.n_covered, result.n_uncovered
        )


@dataclass
class EnglishCoverageSummary:
    """Aggregate, corpus-level, content-free summary of coverage results."""

    n_results: int
    results_by_outcome: dict[str, int] = field(default_factory=dict)
    n_tokens_total: int = 0
    n_covered_total: int = 0
    n_uncovered_total: int = 0

    def to_dict(self) -> dict[str, object]:
        """Nested, JSON-compatible view (aggregate counts only)."""
        return {
            "n_results": self.n_results,
            "results_by_outcome": dict(self.results_by_outcome),
            "n_tokens_total": self.n_tokens_total,
            "n_covered_total": self.n_covered_total,
            "n_uncovered_total": self.n_uncovered_total,
        }


def summarize_english_coverage_results(
    results: list[EnglishCoverageResult],
) -> EnglishCoverageSummary:
    """Aggregate coverage results into corpus-level counts, invariants first."""
    _check_result_invariants(results)

    outcome_counts: Counter[str] = Counter(r.outcome for r in results)
    results_by_outcome = {
        outcome: outcome_counts.get(outcome, 0) for outcome in COVERAGE_OUTCOME_ORDER
    }

    return EnglishCoverageSummary(
        n_results=len(results),
        results_by_outcome=results_by_outcome,
        n_tokens_total=sum(r.n_tokens for r in results),
        n_covered_total=sum(r.n_covered for r in results),
        n_uncovered_total=sum(r.n_uncovered for r in results),
    )


def flatten_english_coverage_summary(summary: EnglishCoverageSummary) -> dict[str, int]:
    """Flatten to a single scalar-valued row (aggregate counts only)."""
    flat: dict[str, int] = {"n_results": summary.n_results}
    for outcome in COVERAGE_OUTCOME_ORDER:
        flat[f"outcome__{outcome}"] = summary.results_by_outcome.get(outcome, 0)
    flat["n_tokens_total"] = summary.n_tokens_total
    flat["n_covered_total"] = summary.n_covered_total
    flat["n_uncovered_total"] = summary.n_uncovered_total
    return flat
