"""Synthetic tests for the Spanish direct-Hunspell coverage boundary.

Only invented ``syn_*`` tokens and fake in-memory checkers are used.  No process,
resource, CALLHOME, Bangor, ignored file, or private log is accessed.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields

import pytest

from cslm.data import spanish_hunspell_coverage as coverage
from cslm.data.spanish_hunspell_coverage import (
    SpanishHunspellCoverageEvaluator,
    SpanishHunspellCoverageResult,
    SpanishHunspellInputError,
    SpanishHunspellProtocolError,
    SpanishHunspellUnavailableError,
    compute_spanish_hunspell_coverage,
)


class _SyntheticChecker:
    def __init__(self, accepted=()):
        self.accepted = frozenset(accepted)
        self.calls: list[tuple[str, ...]] = []

    def check_tokens(self, normalized_tokens):
        self.calls.append(normalized_tokens)
        return tuple(token in self.accepted for token in normalized_tokens)


def test_all_covered():
    checker = _SyntheticChecker({"syn_casa", "syn_hablo"})
    result = compute_spanish_hunspell_coverage(
        ["syn_casa", "syn_hablo"], checker=checker
    )
    assert result.outcome == "all_covered"
    assert (result.n_tokens, result.n_covered, result.n_uncovered) == (2, 2, 0)


def test_has_uncovered():
    checker = _SyntheticChecker({"syn_casa"})
    result = compute_spanish_hunspell_coverage(
        ["syn_casa", "syn_fuera"], checker=checker
    )
    assert result.outcome == "has_uncovered"
    assert (result.n_tokens, result.n_covered, result.n_uncovered) == (2, 1, 1)


def test_no_lexical_tokens_does_not_call_dependency():
    checker = _SyntheticChecker()
    result = compute_spanish_hunspell_coverage([], checker=checker)
    assert result.outcome == "no_lexical_tokens"
    assert (result.n_tokens, result.n_covered, result.n_uncovered) == (0, 0, 0)
    assert checker.calls == []


def test_adapter_does_not_normalize_tokens():
    checker = _SyntheticChecker({"syn_casa"})
    result = compute_spanish_hunspell_coverage(["Syn_Casa"], checker=checker)
    assert result.outcome == "has_uncovered"
    assert checker.calls == [("Syn_Casa",)]


def test_checker_receives_one_immutable_tuple_once():
    checker = _SyntheticChecker({"syn_uno"})
    evaluator = SpanishHunspellCoverageEvaluator(checker)
    evaluator.evaluate_tokens(["syn_uno", "syn_dos"])
    assert checker.calls == [("syn_uno", "syn_dos")]
    assert isinstance(checker.calls[0], tuple)


@pytest.mark.parametrize("bad_tokens", ["syn_text", b"syn_text", bytearray(b"x")])
def test_string_or_bytes_input_fails_closed(bad_tokens):
    with pytest.raises(SpanishHunspellInputError):
        compute_spanish_hunspell_coverage(
            bad_tokens,
            checker=_SyntheticChecker(),
        )


@pytest.mark.parametrize(
    "bad_tokens",
    [
        ["syn_ok", 7],
        [""],
        ["syn two"],
        ["syn\ttwo"],
        ["syn\ntwo"],
        ["syn\x00two"],
        ["syn\x7ftwo"],
    ],
)
def test_invalid_token_element_or_transport_shape_fails_closed(bad_tokens):
    with pytest.raises(SpanishHunspellInputError) as excinfo:
        compute_spanish_hunspell_coverage(
            bad_tokens,
            checker=_SyntheticChecker(),
        )
    assert "syn" not in str(excinfo.value)


@pytest.mark.parametrize("checker", [None, object(), lambda: None])
def test_missing_checker_interface_fails_closed(checker):
    with pytest.raises(SpanishHunspellUnavailableError):
        SpanishHunspellCoverageEvaluator(checker)


def test_dependency_failure_is_wrapped_without_private_value():
    class _Failing:
        def check_tokens(self, normalized_tokens):
            raise RuntimeError("syn_private_token and private path")

    evaluator = SpanishHunspellCoverageEvaluator(_Failing())
    with pytest.raises(SpanishHunspellUnavailableError) as excinfo:
        evaluator.evaluate_tokens(["syn_private_token"])
    message = str(excinfo.value)
    assert "syn_private_token" not in message
    assert "path" not in message


@pytest.mark.parametrize(
    "response",
    [
        "true",
        b"true",
        [True],
        [True, 1],
        [True, None],
        (value for value in [True, False]),
    ],
)
def test_malformed_checker_response_fails_closed(response):
    class _Malformed:
        def check_tokens(self, normalized_tokens):
            return response

    evaluator = SpanishHunspellCoverageEvaluator(_Malformed())
    with pytest.raises(SpanishHunspellProtocolError):
        evaluator.evaluate_tokens(["syn_uno", "syn_dos"])


def test_result_has_exactly_four_content_free_fields():
    assert {item.name for item in fields(SpanishHunspellCoverageResult)} == {
        "outcome",
        "n_tokens",
        "n_covered",
        "n_uncovered",
    }


def test_result_and_evaluator_repr_hide_tokens_and_checker():
    checker = _SyntheticChecker({"syn_private"})
    evaluator = SpanishHunspellCoverageEvaluator(checker)
    result = evaluator.evaluate_tokens(["syn_private", "syn_unknown"])
    assert repr(evaluator) == "SpanishHunspellCoverageEvaluator()"
    assert "syn_private" not in repr(result)
    assert "syn_unknown" not in repr(result)


def test_result_has_no_validation_clean_condition_or_routing_fields():
    result = compute_spanish_hunspell_coverage(
        ["syn_uno"], checker=_SyntheticChecker({"syn_uno"})
    )
    for name in (
        "is_validated",
        "validation_method",
        "reason_codes",
        "clean",
        "condition_candidates",
        "expected_language",
    ):
        assert not hasattr(result, name)


def test_result_is_frozen():
    result = compute_spanish_hunspell_coverage(
        ["syn_uno"], checker=_SyntheticChecker({"syn_uno"})
    )
    with pytest.raises(FrozenInstanceError):
        result.n_tokens = 99


def test_evaluator_checker_cannot_be_reassigned():
    evaluator = SpanishHunspellCoverageEvaluator(_SyntheticChecker())
    with pytest.raises(FrozenInstanceError):
        evaluator._checker = _SyntheticChecker()


def test_module_has_no_corpus_resource_process_or_routing_imports():
    for name in (
        "CallhomeUtterance",
        "ApprovedEnglishScowl",
        "ApprovedSpanishResource",
        "subprocess",
        "lexical_tokens",
        "normalize_token",
        "CallhomeSourceValidationDecision",
        "combine_screening_and_validation",
    ):
        assert not hasattr(coverage, name)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"outcome": "all_covered", "n_tokens": 2, "n_covered": 2, "n_uncovered": 0},
        {"outcome": "has_uncovered", "n_tokens": 2, "n_covered": 1, "n_uncovered": 1},
        {
            "outcome": "no_lexical_tokens",
            "n_tokens": 0,
            "n_covered": 0,
            "n_uncovered": 0,
        },
    ],
)
def test_valid_results_construct(kwargs):
    assert SpanishHunspellCoverageResult(**kwargs).outcome == kwargs["outcome"]


@pytest.mark.parametrize(
    "bad",
    [
        {"outcome": "all_covered", "n_tokens": True, "n_covered": True, "n_uncovered": 0},
        {"outcome": "all_covered", "n_tokens": 2.0, "n_covered": 2, "n_uncovered": 0},
        {"outcome": "has_uncovered", "n_tokens": 1, "n_covered": -1, "n_uncovered": 2},
        {"outcome": "all_covered", "n_tokens": 3, "n_covered": 2, "n_uncovered": 0},
        {"outcome": "syn_bad", "n_tokens": 1, "n_covered": 1, "n_uncovered": 0},
        {"outcome": "all_covered", "n_tokens": 0, "n_covered": 0, "n_uncovered": 0},
        {"outcome": "has_uncovered", "n_tokens": 2, "n_covered": 2, "n_uncovered": 0},
        {
            "outcome": "no_lexical_tokens",
            "n_tokens": 1,
            "n_covered": 1,
            "n_uncovered": 0,
        },
    ],
)
def test_contradictory_result_rejected(bad):
    with pytest.raises(ValueError):
        SpanishHunspellCoverageResult(**bad)
