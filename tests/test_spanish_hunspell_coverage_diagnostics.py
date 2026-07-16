"""Synthetic tests for aggregate Spanish direct-Hunspell diagnostics."""

from __future__ import annotations

from dataclasses import fields

import pytest

from cslm.data.spanish_hunspell_coverage import SpanishHunspellCoverageResult
from cslm.data.spanish_hunspell_coverage_diagnostics import (
    SpanishHunspellCoverageSummary,
    flatten_spanish_hunspell_coverage_summary,
    summarize_spanish_hunspell_coverage_results,
)


def _result(outcome, n_tokens, n_covered):
    return SpanishHunspellCoverageResult(
        outcome=outcome,
        n_tokens=n_tokens,
        n_covered=n_covered,
        n_uncovered=n_tokens - n_covered,
    )


def test_empty_input_yields_zeroed_stable_summary():
    summary = summarize_spanish_hunspell_coverage_results([])
    assert summary.n_results == 0
    assert summary.results_by_outcome == {
        "all_covered": 0,
        "has_uncovered": 0,
        "no_lexical_tokens": 0,
    }
    assert (
        summary.n_tokens_total,
        summary.n_covered_total,
        summary.n_uncovered_total,
    ) == (0, 0, 0)


def test_counts_by_outcome_and_totals():
    results = [
        _result("all_covered", 3, 3),
        _result("has_uncovered", 4, 1),
        _result("no_lexical_tokens", 0, 0),
        _result("all_covered", 2, 2),
    ]
    summary = summarize_spanish_hunspell_coverage_results(results)
    assert summary.results_by_outcome == {
        "all_covered": 2,
        "has_uncovered": 1,
        "no_lexical_tokens": 1,
    }
    assert summary.n_results == 4
    assert summary.n_tokens_total == 9
    assert summary.n_covered_total == 6
    assert summary.n_uncovered_total == 3


def test_outcome_order_and_flatten_schema_are_stable():
    summary = summarize_spanish_hunspell_coverage_results(
        [_result("has_uncovered", 2, 1)]
    )
    assert list(summary.results_by_outcome) == [
        "all_covered",
        "has_uncovered",
        "no_lexical_tokens",
    ]
    assert flatten_spanish_hunspell_coverage_summary(summary) == {
        "n_results": 1,
        "outcome__all_covered": 0,
        "outcome__has_uncovered": 1,
        "outcome__no_lexical_tokens": 0,
        "n_tokens_total": 2,
        "n_covered_total": 1,
        "n_uncovered_total": 1,
    }


def test_to_dict_is_aggregate_only():
    summary = summarize_spanish_hunspell_coverage_results(
        [_result("all_covered", 1, 1)]
    )
    assert summary.to_dict() == {
        "n_results": 1,
        "results_by_outcome": {
            "all_covered": 1,
            "has_uncovered": 0,
            "no_lexical_tokens": 0,
        },
        "n_tokens_total": 1,
        "n_covered_total": 1,
        "n_uncovered_total": 0,
    }


def test_summary_has_only_corpus_level_fields():
    names = {item.name for item in fields(SpanishHunspellCoverageSummary)}
    assert names == {
        "n_results",
        "results_by_outcome",
        "n_tokens_total",
        "n_covered_total",
        "n_uncovered_total",
    }
    for banned in (
        "by_source",
        "by_file",
        "by_conversation",
        "by_speaker",
        "rows",
        "tokens_by",
    ):
        assert not any(banned in name for name in names)


def test_mutated_result_with_bad_outcome_is_rejected():
    result = _result("all_covered", 1, 1)
    object.__setattr__(result, "outcome", "syn_forged")
    with pytest.raises(ValueError):
        summarize_spanish_hunspell_coverage_results([result])


def test_mutated_result_with_inconsistent_counts_is_rejected():
    result = _result("all_covered", 2, 2)
    object.__setattr__(result, "n_covered", 1)
    with pytest.raises(ValueError):
        summarize_spanish_hunspell_coverage_results([result])
