"""Tests for the aggregate English SCOWL coverage diagnostics.

Synthetic results only. The summary must be corpus-level and content-free: no
source, file, conversation, speaker, row, or per-token breakdown, and no way for
an input token string to appear in the aggregate output.
"""

from __future__ import annotations

from dataclasses import fields

import pytest

from cslm.data.english_scowl_coverage import EnglishCoverageResult
from cslm.data.english_scowl_coverage_diagnostics import (
    EnglishCoverageSummary,
    flatten_english_coverage_summary,
    summarize_english_coverage_results,
)


def _result(outcome, n_tokens, n_covered):
    return EnglishCoverageResult(
        outcome=outcome,
        n_tokens=n_tokens,
        n_covered=n_covered,
        n_uncovered=n_tokens - n_covered,
    )


def test_empty_input_yields_zeroed_stable_summary():
    s = summarize_english_coverage_results([])
    assert s.n_results == 0
    assert s.results_by_outcome == {
        "all_covered": 0,
        "has_uncovered": 0,
        "no_lexical_tokens": 0,
    }
    assert (s.n_tokens_total, s.n_covered_total, s.n_uncovered_total) == (0, 0, 0)


def test_counts_by_outcome_and_totals():
    results = [
        _result("all_covered", 3, 3),
        _result("has_uncovered", 4, 1),
        _result("no_lexical_tokens", 0, 0),
        _result("all_covered", 2, 2),
    ]
    s = summarize_english_coverage_results(results)
    assert s.n_results == 4
    assert s.results_by_outcome == {
        "all_covered": 2,
        "has_uncovered": 1,
        "no_lexical_tokens": 1,
    }
    assert s.n_tokens_total == 9
    assert s.n_covered_total == 6
    assert s.n_uncovered_total == 3


def test_outcome_key_order_is_stable():
    s = summarize_english_coverage_results([_result("has_uncovered", 2, 1)])
    assert list(s.results_by_outcome) == ["all_covered", "has_uncovered", "no_lexical_tokens"]


def test_to_dict_and_flatten_are_aggregate_only():
    results = [_result("all_covered", 2, 2), _result("has_uncovered", 3, 1)]
    s = summarize_english_coverage_results(results)

    d = s.to_dict()
    assert d == {
        "n_results": 2,
        "results_by_outcome": {"all_covered": 1, "has_uncovered": 1, "no_lexical_tokens": 0},
        "n_tokens_total": 5,
        "n_covered_total": 3,
        "n_uncovered_total": 2,
    }

    flat = flatten_english_coverage_summary(s)
    assert flat == {
        "n_results": 2,
        "outcome__all_covered": 1,
        "outcome__has_uncovered": 1,
        "outcome__no_lexical_tokens": 0,
        "n_tokens_total": 5,
        "n_covered_total": 3,
        "n_uncovered_total": 2,
    }


def test_summary_has_only_corpus_level_fields():
    names = {f.name for f in fields(EnglishCoverageSummary)}
    assert names == {
        "n_results",
        "results_by_outcome",
        "n_tokens_total",
        "n_covered_total",
        "n_uncovered_total",
    }
    # No source / file / conversation / speaker / row / per-token breakdown.
    for banned in ("by_source", "by_file", "by_conversation", "by_speaker", "rows", "tokens_by"):
        assert not any(banned in n for n in names)


def test_mutated_result_with_bad_outcome_is_rejected():
    good = _result("all_covered", 1, 1)
    object.__setattr__(good, "outcome", "syn_forged_outcome")
    with pytest.raises(ValueError):
        summarize_english_coverage_results([good])


def test_mutated_result_with_inconsistent_counts_is_rejected():
    good = _result("all_covered", 2, 2)
    object.__setattr__(good, "n_covered", 1)  # now 1 + 0 != 2
    with pytest.raises(ValueError):
        summarize_english_coverage_results([good])


@pytest.mark.parametrize(
    "attr,value",
    [
        # all_covered mutated into every contradictory shape.
        ("outcome", "no_lexical_tokens"),  # counts (2,2,0) are not all zero
        ("outcome", "has_uncovered"),      # n_uncovered == 0 contradicts has_uncovered
        ("n_covered", True),               # bool count rejected
        ("n_tokens", 2.0),                 # float count rejected
        ("n_uncovered", -1),               # negative count rejected
    ],
)
def test_defensive_recheck_mirrors_full_invariants(attr, value):
    # Start from a valid all_covered result, then mutate one field to violate an
    # invariant; the aggregate re-check must reject it (mirroring construction).
    good = _result("all_covered", 2, 2)  # counts (2, 2, 0)
    object.__setattr__(good, attr, value)
    with pytest.raises(ValueError):
        summarize_english_coverage_results([good])
