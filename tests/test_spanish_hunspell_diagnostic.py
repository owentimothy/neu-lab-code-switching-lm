"""Synthetic tests for the Spanish coverage diagnostic orchestration boundary.

Only invented ``syn_*`` utterances and fake in-memory evaluators are used.  No
process, container, resource, CALLHOME, Bangor, ignored file, or private log is
accessed.  The only file any test opens is this repository's own module source,
for the structural import check.
"""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from cslm.data import spanish_hunspell_diagnostic as diagnostic
from cslm.data.callhome_chat import CallhomeUtterance
from cslm.data.callhome_lexicon_normalization import lexical_tokens
from cslm.data.spanish_hunspell_coverage import (
    SpanishHunspellCoverageEvaluator,
    SpanishHunspellCoverageResult,
)
from cslm.data.spanish_hunspell_diagnostic import (
    AGGREGATE_FIELD_ORDER,
    DIAGNOSTIC_NAME,
    DIAGNOSTIC_STATUS,
    MINIMUM_RELEASABLE_POSITIVE_COUNT,
    RESOURCE_ID,
    RESOURCE_ROLE,
    SCHEMA_VERSION,
    SpanishDiagnosticReleaseWithheldError,
    SpanishDiagnosticRunError,
    SpanishLexicalCoverageAggregate,
    require_releasable_aggregate,
    run_spanish_hunspell_coverage_diagnostic,
)

# Invented tokens only; none of these are real CALLHOME or RLA-ES material.
_ACCEPTED = frozenset({"syn_casa", "syn_hablo", "syn_uno", "syn_dos"})

# Fixed public failure text, restated here so a silent message change is caught.
_RUN_FAILURE_TEXT = "synthetic spanish lexical coverage diagnostic failed"
_RELEASE_WITHHELD_TEXT = "aggregate withheld by the minimum-count release policy"

# Invented "sensitive" fragments a leaking failure path would expose.
_SECRET_FRAGMENTS = (
    "syn_secret_token",
    "syn_secret_utterance",
    "/syn/private/bundle/es",
    "syn_conv_99.cha",
)
_SECRET = " ".join(_SECRET_FRAGMENTS)


# --------------------------------------------------------------------------- #
# Synthetic fixtures.
# --------------------------------------------------------------------------- #


class _SyntheticChecker:
    """Fake private checker: membership against an invented accepted set."""

    def __init__(self, accepted=_ACCEPTED):
        self.accepted = frozenset(accepted)

    def check_tokens(self, normalized_tokens):
        return tuple(token in self.accepted for token in normalized_tokens)


class _RecordingEvaluator:
    """Real coverage arithmetic behind a call-recording facade.

    Retains every token tuple, so it is used only where a test genuinely needs
    to inspect what the orchestration handed over.
    """

    def __init__(self, accepted=_ACCEPTED):
        self._inner = SpanishHunspellCoverageEvaluator(_SyntheticChecker(accepted))
        self.calls: list[tuple[str, ...]] = []

    def evaluate_tokens(self, normalized_tokens):
        self.calls.append(normalized_tokens)
        return self._inner.evaluate_tokens(normalized_tokens)


class _CountingEvaluator:
    """Constant-space evaluator: one integer counter, no retained history.

    Used for the long-population test, where a recording evaluator would make
    the *test* consume population-sized memory and so could not substantiate the
    orchestration's constant-space claim.
    """

    def __init__(self, accepted=_ACCEPTED):
        self._inner = SpanishHunspellCoverageEvaluator(_SyntheticChecker(accepted))
        self.calls = 0

    def evaluate_tokens(self, normalized_tokens):
        self.calls += 1
        return self._inner.evaluate_tokens(normalized_tokens)


class _ScriptedEvaluator:
    """Returns caller-supplied objects, so invalid results can be exercised."""

    def __init__(self, results):
        self._results = list(results)
        self.calls = 0

    def evaluate_tokens(self, normalized_tokens):
        self.calls += 1
        return self._results.pop(0)


class _RaisingEvaluator:
    """Raises a chosen exception instance on the nth call (0-indexed)."""

    def __init__(self, error, *, on_call=0):
        self._error = error
        self._on_call = on_call
        self.calls = 0

    def evaluate_tokens(self, normalized_tokens):
        self.calls += 1
        if self.calls - 1 == self._on_call:
            raise self._error
        return SpanishHunspellCoverageResult(
            outcome="no_lexical_tokens", n_tokens=0, n_covered=0, n_uncovered=0
        )


def _utterance(text, *, turn_index=0):
    return CallhomeUtterance(
        conversation_id="syn_conv_01",
        source_file="syn_conv_01.cha",
        speaker_id="SYN",
        turn_index=turn_index,
        raw_main_tier_text=text,
    )


def _run(texts, *, evaluator=None):
    evaluator = evaluator if evaluator is not None else _RecordingEvaluator()
    aggregate = run_spanish_hunspell_coverage_diagnostic(
        (_utterance(text, turn_index=i) for i, text in enumerate(texts)),
        evaluator=evaluator,
    )
    return aggregate, evaluator


def _aggregate(**overrides):
    """A valid aggregate whose every count is zero or at least ten."""
    fields = {
        "n_utterances_total": 30,
        "n_utterances_with_lexical_tokens": 20,
        "n_tokens_total": 100,
        "n_covered_total": 60,
        "n_uncovered_total": 40,
        # Ordered by COVERAGE_OUTCOME_ORDER: all_covered, has_uncovered, none.
        "_outcome_counts": (10, 10, 10),
    }
    fields.update(overrides)
    return SpanishLexicalCoverageAggregate(**fields)


def _mutated(aggregate, **changes):
    """Force post-construction state past ``frozen=True``, as an attacker would."""
    for name, value in changes.items():
        object.__setattr__(aggregate, name, value)
    return aggregate


# --------------------------------------------------------------------------- #
# Core traversal.
# --------------------------------------------------------------------------- #


def test_single_all_covered_utterance():
    aggregate, _ = _run(["syn_casa syn_hablo ."])
    assert aggregate.n_utterances_total == 1
    assert aggregate.n_utterances_with_lexical_tokens == 1
    assert aggregate.results_by_outcome["all_covered"] == 1
    assert (
        aggregate.n_tokens_total,
        aggregate.n_covered_total,
        aggregate.n_uncovered_total,
    ) == (2, 2, 0)


def test_single_partly_uncovered_utterance():
    aggregate, _ = _run(["syn_casa syn_desconocido ."])
    assert aggregate.results_by_outcome["has_uncovered"] == 1
    assert aggregate.n_utterances_with_lexical_tokens == 1
    assert (
        aggregate.n_tokens_total,
        aggregate.n_covered_total,
        aggregate.n_uncovered_total,
    ) == (2, 1, 1)


def test_utterance_with_no_lexical_tokens():
    aggregate, evaluator = _run(["xxx ."])
    assert aggregate.results_by_outcome["no_lexical_tokens"] == 1
    assert aggregate.n_utterances_total == 1
    assert aggregate.n_utterances_with_lexical_tokens == 0
    assert aggregate.n_tokens_total == 0
    # The utterance is still traversed and still evaluated: it is not skipped.
    assert evaluator.calls == [()]


def test_mixed_outcomes_across_multiple_utterances():
    aggregate, _ = _run(
        [
            "syn_casa syn_hablo .",
            "syn_uno syn_desconocido .",
            "xxx .",
            "syn_dos .",
        ]
    )
    assert aggregate.n_utterances_total == 4
    assert dict(aggregate.results_by_outcome) == {
        "all_covered": 2,
        "has_uncovered": 1,
        "no_lexical_tokens": 1,
    }
    assert aggregate.n_utterances_with_lexical_tokens == 3
    assert (
        aggregate.n_tokens_total,
        aggregate.n_covered_total,
        aggregate.n_uncovered_total,
    ) == (5, 4, 1)


def test_duplicate_tokens_are_counted_repeatedly():
    aggregate, _ = _run(["syn_casa syn_casa syn_casa ."])
    # Occurrence counting, not unique-type counting.
    assert aggregate.n_tokens_total == 3
    assert aggregate.n_covered_total == 3
    assert aggregate.n_utterances_total == 1


def test_repeated_utterance_objects_are_counted_repeatedly():
    utterance = _utterance("syn_casa syn_desconocido .")
    aggregate = run_spanish_hunspell_coverage_diagnostic(
        iter([utterance, utterance, utterance]),
        evaluator=_RecordingEvaluator(),
    )
    assert aggregate.n_utterances_total == 3
    assert aggregate.results_by_outcome["has_uncovered"] == 3
    assert (aggregate.n_tokens_total, aggregate.n_uncovered_total) == (6, 3)


def test_input_order_does_not_change_totals():
    texts = ["syn_casa syn_hablo .", "syn_uno syn_desconocido .", "xxx ."]
    forward, _ = _run(texts)
    reverse, _ = _run(list(reversed(texts)))
    assert forward.to_dict() == reverse.to_dict()


def test_every_supplied_utterance_is_processed():
    texts = ["syn_casa .", "xxx .", "syn_desconocido .", "&uh", "syn_dos ."]
    aggregate, evaluator = _run(texts)
    assert aggregate.n_utterances_total == len(texts)
    assert len(evaluator.calls) == len(texts)


def test_no_screening_or_eligibility_attribute_is_consulted():
    class _SingleFieldUtterance:
        def __init__(self, text):
            self.raw_main_tier_text = text

        def __getattr__(self, name):  # pragma: no cover - only fires on failure
            raise AssertionError(f"diagnostic must not consult {name!r}")

    aggregate = run_spanish_hunspell_coverage_diagnostic(
        iter([_SingleFieldUtterance("syn_casa ."), _SingleFieldUtterance("xxx .")]),
        evaluator=_RecordingEvaluator(),
    )
    assert aggregate.n_utterances_total == 2


# --------------------------------------------------------------------------- #
# Normalization ownership.
# --------------------------------------------------------------------------- #


def test_orchestration_delegates_to_shared_lexical_tokens(monkeypatch):
    seen: list[str | None] = []

    def _spy(text):
        seen.append(text)
        return lexical_tokens(text)

    monkeypatch.setattr(diagnostic, "lexical_tokens", _spy)
    texts = ["syn_casa .", "xxx ."]
    aggregate, _ = _run(texts)
    # Exactly one shared-normalization call per utterance, on the raw main tier.
    assert seen == texts
    assert aggregate.n_utterances_total == 2


@pytest.mark.parametrize(
    "text",
    [
        "SYN_CASA syn_Hablo .",
        "¿syn_casa? ¡syn_hablo!",
        "syn_casa xxx yyy www 0 &uh [syn_code] (syn_paren) syn_hablo",
        "syn_café syn_cafe",
        "",
    ],
)
def test_normalization_matches_shared_policy_exactly(text):
    _, evaluator = _run([text])
    # The diagnostic introduces no normalization of its own: what the evaluator
    # receives is exactly what the shared policy produces.
    assert evaluator.calls == [tuple(lexical_tokens(text))]


def test_none_main_tier_text_is_handled_by_shared_policy():
    aggregate, evaluator = _run([None])
    assert evaluator.calls == [()]
    assert aggregate.results_by_outcome["no_lexical_tokens"] == 1


# --------------------------------------------------------------------------- #
# Streaming.
# --------------------------------------------------------------------------- #


def test_one_shot_generator_is_accepted():
    def _population():
        yield _utterance("syn_casa .")
        yield _utterance("syn_desconocido .")

    aggregate = run_spanish_hunspell_coverage_diagnostic(
        _population(), evaluator=_RecordingEvaluator()
    )
    assert aggregate.n_utterances_total == 2


def test_iterable_is_consumed_exactly_once():
    class _CountingIterable:
        def __init__(self, items):
            self._items = tuple(items)
            self.iter_calls = 0

        def __iter__(self):
            self.iter_calls += 1
            return iter(self._items)

    population = _CountingIterable([_utterance("syn_casa ."), _utterance("xxx .")])
    aggregate = run_spanish_hunspell_coverage_diagnostic(
        population, evaluator=_RecordingEvaluator()
    )
    assert population.iter_calls == 1
    assert aggregate.n_utterances_total == 2


def test_length_and_indexing_are_never_required():
    class _NoLengthNoIndexIterable:
        def __init__(self, items):
            self._items = tuple(items)

        def __iter__(self):
            return iter(self._items)

        def __len__(self):  # pragma: no cover - only fires on failure
            raise AssertionError("len() must not be used")

        def __getitem__(self, index):  # pragma: no cover - only fires on failure
            raise AssertionError("indexing must not be used")

    aggregate = run_spanish_hunspell_coverage_diagnostic(
        _NoLengthNoIndexIterable([_utterance("syn_casa ."), _utterance("syn_dos .")]),
        evaluator=_RecordingEvaluator(),
    )
    assert aggregate.n_utterances_total == 2


def test_long_population_streams_with_a_constant_space_evaluator():
    utterance = _utterance("syn_casa syn_desconocido .")

    def _population(n):
        for _ in range(n):
            yield utterance

    evaluator = _CountingEvaluator()
    aggregate = run_spanish_hunspell_coverage_diagnostic(
        _population(5000), evaluator=evaluator
    )
    assert aggregate.n_utterances_total == 5000
    assert aggregate.n_tokens_total == 10000
    assert aggregate.results_by_outcome["has_uncovered"] == 5000
    assert evaluator.calls == 5000
    # The evaluator retains one integer, not a per-call token history, so the
    # whole run — orchestration and fake alike — is constant-space.
    assert not any(
        isinstance(value, (list, tuple, dict, set))
        for value in vars(evaluator).values()
    )


def test_evaluator_failure_aborts_at_the_failing_utterance():
    evaluator = _RaisingEvaluator(RuntimeError("syn_secret_token"), on_call=1)
    with pytest.raises(SpanishDiagnosticRunError):
        _run(["syn_casa .", "syn_dos .", "syn_uno ."], evaluator=evaluator)
    # Aborted at the failing utterance; the rest is never evaluated.
    assert evaluator.calls == 2


def test_missing_evaluator_interface_fails_closed():
    with pytest.raises(SpanishDiagnosticRunError):
        run_spanish_hunspell_coverage_diagnostic(iter([]), evaluator=object())


def test_utterance_without_main_tier_text_fails_closed():
    with pytest.raises(SpanishDiagnosticRunError):
        run_spanish_hunspell_coverage_diagnostic(
            iter([object()]), evaluator=_RecordingEvaluator()
        )


@pytest.mark.parametrize("population", ["syn_casa .", b"syn_casa", bytearray(b"syn")])
def test_string_or_bytes_population_fails_closed(population):
    with pytest.raises(SpanishDiagnosticRunError):
        run_spanish_hunspell_coverage_diagnostic(
            population, evaluator=_RecordingEvaluator()
        )


# --------------------------------------------------------------------------- #
# Result integrity: one exact public schema.
# --------------------------------------------------------------------------- #


def test_metadata_constants_are_exact_and_not_caller_supplied():
    assert SCHEMA_VERSION == "spanish_lexical_coverage.aggregate.v1"
    assert DIAGNOSTIC_NAME == "callhome_spanish_rla_es_general_coverage"
    assert DIAGNOSTIC_STATUS == "complete"
    assert RESOURCE_ID == "spanish_rla_es_v2_9_general"
    assert RESOURCE_ROLE == "broad_pan_regional_lexical_coverage_only"
    with pytest.raises(TypeError):
        SpanishLexicalCoverageAggregate(
            schema_version="syn_forged",
            n_utterances_total=1,
            n_utterances_with_lexical_tokens=0,
            n_tokens_total=0,
            n_covered_total=0,
            n_uncovered_total=0,
            _outcome_counts=(0, 0, 1),
        )


def test_scalar_outcome_aliases_are_not_a_second_public_schema():
    aggregate, _ = _run(["syn_casa syn_desconocido .", "xxx ."])
    rendering = repr(aggregate)
    payload = aggregate.to_dict()
    for alias in ("n_all_covered", "n_has_uncovered", "n_no_lexical_tokens"):
        assert not hasattr(aggregate, alias)
        assert alias not in dir(aggregate)
        assert alias not in rendering
        assert alias not in payload
    # The counts stay available under the one approved public key.
    assert dict(aggregate.results_by_outcome) == {
        "all_covered": 0,
        "has_uncovered": 1,
        "no_lexical_tokens": 1,
    }
    assert payload["results_by_outcome"] == dict(aggregate.results_by_outcome)


def test_ordinary_repr_exposes_no_outcome_state():
    aggregate, _ = _run(["syn_casa syn_desconocido .", "xxx ."])
    rendering = repr(aggregate)
    assert rendering.startswith("SpanishLexicalCoverageAggregate(")
    for banned in ("_outcome_counts", "all_covered", "has_uncovered", "outcome"):
        assert banned not in rendering


def test_aggregate_schema_field_order_and_nested_outcome_order():
    aggregate, _ = _run(["syn_casa syn_desconocido ."])
    payload = aggregate.to_dict()
    assert list(payload) == list(AGGREGATE_FIELD_ORDER)
    assert list(payload) == [
        "schema_version",
        "diagnostic_name",
        "diagnostic_status",
        "resource_id",
        "resource_role",
        "n_utterances_total",
        "n_utterances_with_lexical_tokens",
        "results_by_outcome",
        "n_tokens_total",
        "n_covered_total",
        "n_uncovered_total",
    ]
    assert list(payload["results_by_outcome"]) == [
        "all_covered",
        "has_uncovered",
        "no_lexical_tokens",
    ]
    assert list(aggregate.results_by_outcome) == list(payload["results_by_outcome"])
    assert payload == {
        "schema_version": SCHEMA_VERSION,
        "diagnostic_name": DIAGNOSTIC_NAME,
        "diagnostic_status": DIAGNOSTIC_STATUS,
        "resource_id": RESOURCE_ID,
        "resource_role": RESOURCE_ROLE,
        "n_utterances_total": 1,
        "n_utterances_with_lexical_tokens": 1,
        "results_by_outcome": {
            "all_covered": 0,
            "has_uncovered": 1,
            "no_lexical_tokens": 0,
        },
        "n_tokens_total": 2,
        "n_covered_total": 1,
        "n_uncovered_total": 1,
    }


def test_aggregate_exposes_no_rate_row_or_provenance_field():
    aggregate, _ = _run(["syn_casa ."])
    payload = aggregate.to_dict()
    for banned in (
        "coverage_rate",
        "cleanup_confirmed",
        "no_raw_content_emitted",
        "filename",
        "conversation",
        "speaker",
        "row_id",
        "tokens",
        "sample",
        "example",
        "path",
        "hash",
        "container",
        "notice",
        "provenance",
        "stderr",
        "traceback",
        "notes",
        "is_validated",
        "clean",
        "condition_candidates",
        "routing",
    ):
        assert banned not in payload
        assert not hasattr(aggregate, banned)
    assert not any("rate" in name for name in dir(aggregate))


def test_aggregate_is_frozen_and_outcome_mapping_is_read_only():
    aggregate, _ = _run(["syn_casa ."])
    with pytest.raises(FrozenInstanceError):
        aggregate.n_tokens_total = 99
    with pytest.raises(TypeError):
        aggregate.results_by_outcome["all_covered"] = 99
    # ``to_dict`` hands back a fresh mapping; mutating it cannot reach the object.
    payload = aggregate.to_dict()
    payload["results_by_outcome"]["all_covered"] = 99
    assert aggregate.results_by_outcome["all_covered"] == 1


@pytest.mark.parametrize(
    "overrides",
    [
        # Booleans must not pass as counts.
        {"n_utterances_total": True},
        {"_outcome_counts": (True, 10, 10)},
        {"n_tokens_total": True},
        # Non-int counts.
        {"n_tokens_total": 100.0},
        {"n_covered_total": "60"},
        # Negative counts.
        {"n_utterances_total": -1},
        {"_outcome_counts": (-10, 10, 30), "n_utterances_total": 30},
        # Structurally invalid private outcome state.
        {"_outcome_counts": [10, 10, 10]},
        {"_outcome_counts": (10, 20)},
        {"_outcome_counts": (10, 10, 10, 0)},
        # Outcome/utterance reconciliation.
        {"_outcome_counts": (10, 10, 11)},
        {"n_utterances_with_lexical_tokens": 21},
        # Token reconciliation.
        {"n_covered_total": 59},
        # Implied minimums.
        {"n_tokens_total": 15, "n_covered_total": 10, "n_uncovered_total": 5},
        # A complete diagnostic cannot have an empty population.
        {
            "n_utterances_total": 0,
            "n_utterances_with_lexical_tokens": 0,
            "n_tokens_total": 0,
            "n_covered_total": 0,
            "n_uncovered_total": 0,
            "_outcome_counts": (0, 0, 0),
        },
    ],
)
def test_inconsistent_aggregate_is_rejected(overrides):
    with pytest.raises(ValueError):
        _aggregate(**overrides)


def test_empty_utterance_population_is_rejected():
    with pytest.raises(SpanishDiagnosticRunError):
        run_spanish_hunspell_coverage_diagnostic(
            iter([]), evaluator=_RecordingEvaluator()
        )


def test_all_no_token_population_is_valid_without_inventing_a_rate():
    aggregate, _ = _run(["xxx .", "&uh", "[syn_code]", "0"])
    assert aggregate.n_utterances_total == 4
    assert aggregate.n_utterances_with_lexical_tokens == 0
    assert dict(aggregate.results_by_outcome) == {
        "all_covered": 0,
        "has_uncovered": 0,
        "no_lexical_tokens": 4,
    }
    assert (
        aggregate.n_tokens_total,
        aggregate.n_covered_total,
        aggregate.n_uncovered_total,
    ) == (0, 0, 0)
    assert "coverage_rate" not in aggregate.to_dict()


def test_mutated_inconsistent_utterance_result_is_rejected():
    result = SpanishHunspellCoverageResult(
        outcome="all_covered", n_tokens=2, n_covered=2, n_uncovered=0
    )
    object.__setattr__(result, "n_covered", 1)
    with pytest.raises(SpanishDiagnosticRunError):
        _run(["syn_casa syn_hablo ."], evaluator=_ScriptedEvaluator([result]))


def test_forged_utterance_result_type_is_rejected():
    class _ForgedResult:
        outcome = "all_covered"
        n_tokens = 2
        n_covered = 2
        n_uncovered = 0

    with pytest.raises(SpanishDiagnosticRunError):
        _run(["syn_casa syn_hablo ."], evaluator=_ScriptedEvaluator([_ForgedResult()]))


# --------------------------------------------------------------------------- #
# Defensive revalidation of mutated aggregates.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "changes",
    [
        # Outcome totals no longer reconcile.
        {"_outcome_counts": (10, 10, 11)},
        # Token totals no longer reconcile.
        {"n_covered_total": 61},
        # A Boolean is not a count.
        {"n_tokens_total": True},
        # A negative count.
        {"n_uncovered_total": -40},
        # Structurally invalid private outcome state.
        {"_outcome_counts": (10, 10, "10")},
        {"_outcome_counts": [10, 10, 10]},
        {"_outcome_counts": (10, 20)},
        {"_outcome_counts": None},
    ],
)
def test_mutated_aggregate_is_rejected_by_mapping_serialization_and_release_boundaries(
    changes,
):
    aggregate = _mutated(_aggregate(), **changes)
    # ``frozen=True`` did not prevent the mutation, so the mapping,
    # serialization, and release boundaries each revalidate before exposing it.
    with pytest.raises(ValueError):
        aggregate.results_by_outcome
    with pytest.raises(ValueError):
        aggregate.to_dict()
    with pytest.raises(SpanishDiagnosticReleaseWithheldError) as excinfo:
        require_releasable_aggregate(aggregate)
    error = excinfo.value
    assert error.args == (_RELEASE_WITHHELD_TEXT,)
    assert error.__cause__ is None
    assert error.__context__ is None


def test_mutated_aggregate_validation_message_is_fixed_and_valueless():
    aggregate = _mutated(_aggregate(), n_covered_total=61)
    with pytest.raises(ValueError) as excinfo:
        aggregate.to_dict()
    rendering = str(excinfo.value)
    assert rendering == "aggregate state failed its invariant check"
    for value in ("61", "100", "40", "30", "20", "10"):
        assert value not in rendering


def test_consistent_mutation_into_a_small_cell_is_withheld_not_invalidated():
    # Still internally consistent (25 == 10 + 10 + 5), so it still serializes ...
    aggregate = _mutated(
        _aggregate(), _outcome_counts=(10, 10, 5), n_utterances_total=25
    )
    assert dict(aggregate.results_by_outcome) == {
        "all_covered": 10,
        "has_uncovered": 10,
        "no_lexical_tokens": 5,
    }
    # ... but the small positive cell withholds the entire object.
    with pytest.raises(SpanishDiagnosticReleaseWithheldError):
        require_releasable_aggregate(aggregate)


# --------------------------------------------------------------------------- #
# Failure privacy.
# --------------------------------------------------------------------------- #


def _source_evaluator_interface(monkeypatch):
    """Attribute lookup on a hostile evaluator raises before any traversal."""

    class _HostileEvaluator:
        def __getattr__(self, name):
            raise RuntimeError(_SECRET)

    return lambda: run_spanish_hunspell_coverage_diagnostic(
        iter([_utterance("syn_casa .")]), evaluator=_HostileEvaluator()
    )


def _source_iterable_acquisition(monkeypatch):
    class _HostileIterable:
        def __iter__(self):
            raise RuntimeError(_SECRET)

    return lambda: run_spanish_hunspell_coverage_diagnostic(
        _HostileIterable(), evaluator=_RecordingEvaluator()
    )


def _source_iterator_traversal(monkeypatch):
    def _population():
        yield _utterance("syn_casa .")
        raise RuntimeError(_SECRET)

    population = _population()
    return lambda: run_spanish_hunspell_coverage_diagnostic(
        population, evaluator=_RecordingEvaluator()
    )


def _source_utterance_attribute(monkeypatch):
    class _HostileUtterance:
        @property
        def raw_main_tier_text(self):
            raise RuntimeError(_SECRET)

    return lambda: run_spanish_hunspell_coverage_diagnostic(
        iter([_HostileUtterance()]), evaluator=_RecordingEvaluator()
    )


def _source_normalization(monkeypatch):
    def _exploding(text):
        raise RuntimeError(_SECRET)

    monkeypatch.setattr(diagnostic, "lexical_tokens", _exploding)
    return lambda: run_spanish_hunspell_coverage_diagnostic(
        iter([_utterance("syn_casa .")]), evaluator=_RecordingEvaluator()
    )


def _source_evaluator_execution(monkeypatch):
    return lambda: run_spanish_hunspell_coverage_diagnostic(
        iter([_utterance("syn_casa .")]),
        evaluator=_RaisingEvaluator(RuntimeError(_SECRET)),
    )


def _source_mutated_result(monkeypatch):
    result = SpanishHunspellCoverageResult(
        outcome="all_covered", n_tokens=2, n_covered=2, n_uncovered=0
    )
    object.__setattr__(result, "n_covered", 1)
    return lambda: run_spanish_hunspell_coverage_diagnostic(
        iter([_utterance("syn_casa syn_hablo .")]),
        evaluator=_ScriptedEvaluator([result]),
    )


def _source_aggregate_build(monkeypatch):
    # An empty population is not a *complete* diagnostic, so the aggregate's own
    # invariant check is the failing step.
    return lambda: run_spanish_hunspell_coverage_diagnostic(
        iter([]), evaluator=_RecordingEvaluator()
    )


@pytest.mark.parametrize(
    "make_call",
    [
        _source_evaluator_interface,
        _source_iterable_acquisition,
        _source_iterator_traversal,
        _source_utterance_attribute,
        _source_normalization,
        _source_evaluator_execution,
        _source_mutated_result,
        _source_aggregate_build,
    ],
    ids=[
        "evaluator_interface",
        "iterable_acquisition",
        "iterator_traversal",
        "utterance_attribute",
        "normalization",
        "evaluator_execution",
        "mutated_result",
        "aggregate_build",
    ],
)
def test_every_wrapped_failure_is_fixed_and_context_free(make_call, monkeypatch):
    call = make_call(monkeypatch)
    with pytest.raises(SpanishDiagnosticRunError) as excinfo:
        call()
    error = excinfo.value
    assert error.args == (_RUN_FAILURE_TEXT,)
    assert str(error) == _RUN_FAILURE_TEXT
    # ``raise ... from None`` alone would leave the original reachable through
    # ``__context__``; the fixed error is raised outside the handler instead.
    assert error.__cause__ is None
    assert error.__context__ is None
    for rendering in (str(error), repr(error), str(error.args)):
        for fragment in _SECRET_FRAGMENTS:
            assert fragment not in rendering


def test_release_withheld_failure_is_context_free_for_a_non_aggregate():
    with pytest.raises(SpanishDiagnosticReleaseWithheldError) as excinfo:
        require_releasable_aggregate(object())
    error = excinfo.value
    assert error.args == (_RELEASE_WITHHELD_TEXT,)
    assert error.__cause__ is None
    assert error.__context__ is None


@pytest.mark.parametrize("interrupt_type", [KeyboardInterrupt, SystemExit])
def test_evaluator_interrupt_propagates_as_the_same_object(interrupt_type):
    interrupt = interrupt_type()
    with pytest.raises(interrupt_type) as excinfo:
        _run(["syn_casa ."], evaluator=_RaisingEvaluator(interrupt))
    # Not merely the same class: the exact instance, unwrapped and unchained.
    assert excinfo.value is interrupt
    assert excinfo.value.__cause__ is None
    assert excinfo.value.__context__ is None


@pytest.mark.parametrize("interrupt_type", [KeyboardInterrupt, SystemExit])
def test_iterator_interrupt_propagates_as_the_same_object(interrupt_type):
    interrupt = interrupt_type()

    def _population():
        yield _utterance("syn_casa .")
        raise interrupt

    with pytest.raises(interrupt_type) as excinfo:
        run_spanish_hunspell_coverage_diagnostic(
            _population(), evaluator=_RecordingEvaluator()
        )
    assert excinfo.value is interrupt
    assert excinfo.value.__cause__ is None
    assert excinfo.value.__context__ is None


# --------------------------------------------------------------------------- #
# Release guard.
# --------------------------------------------------------------------------- #


def test_minimum_positive_public_count_is_ten():
    assert MINIMUM_RELEASABLE_POSITIVE_COUNT == 10


def test_all_positive_counts_at_least_ten_are_releasable():
    aggregate = _aggregate()
    assert require_releasable_aggregate(aggregate) is aggregate


def test_zero_counts_are_permitted():
    aggregate = _aggregate(
        n_utterances_total=10,
        n_utterances_with_lexical_tokens=0,
        n_tokens_total=0,
        n_covered_total=0,
        n_uncovered_total=0,
        _outcome_counts=(0, 0, 10),
    )
    assert require_releasable_aggregate(aggregate) is aggregate


@pytest.mark.parametrize("small", list(range(1, MINIMUM_RELEASABLE_POSITIVE_COUNT)))
def test_a_single_small_positive_count_withholds_the_whole_object(small):
    aggregate = _aggregate(
        n_utterances_total=20 + small,
        _outcome_counts=(10, 10, small),
    )
    with pytest.raises(SpanishDiagnosticReleaseWithheldError):
        require_releasable_aggregate(aggregate)


def test_withheld_guard_returns_no_partial_object_and_does_not_mutate():
    aggregate = _aggregate(n_utterances_total=21, _outcome_counts=(10, 10, 1))
    before = aggregate.to_dict()
    with pytest.raises(SpanishDiagnosticReleaseWithheldError) as excinfo:
        require_releasable_aggregate(aggregate)
    error = excinfo.value
    assert not hasattr(error, "aggregate")
    assert aggregate.to_dict() == before


def test_withheld_error_text_is_fixed_and_carries_no_counts():
    aggregate = _aggregate(n_utterances_total=27, _outcome_counts=(10, 10, 7))
    with pytest.raises(SpanishDiagnosticReleaseWithheldError) as excinfo:
        require_releasable_aggregate(aggregate)
    error = excinfo.value
    assert error.args == (_RELEASE_WITHHELD_TEXT,)
    for rendering in (str(error), repr(error)):
        for count in ("27", "7", "100", "60", "40"):
            assert count not in rendering


def test_guard_fails_closed_on_a_non_aggregate_object():
    class _ForgedAggregate:
        n_utterances_total = 30
        n_utterances_with_lexical_tokens = 20
        n_tokens_total = 100
        n_covered_total = 60
        n_uncovered_total = 40
        _outcome_counts = (10, 10, 10)

    with pytest.raises(SpanishDiagnosticReleaseWithheldError):
        require_releasable_aggregate(_ForgedAggregate())


def test_release_guard_is_separate_from_aggregate_construction():
    # A completed aggregate below the threshold is still constructible: the guard
    # governs release only, never whether the diagnostic may be computed.
    aggregate, _ = _run(["syn_casa ."])
    assert aggregate.n_utterances_total == 1
    with pytest.raises(SpanishDiagnosticReleaseWithheldError):
        require_releasable_aggregate(aggregate)


# --------------------------------------------------------------------------- #
# Scope boundaries.
# --------------------------------------------------------------------------- #


def test_module_exposes_no_process_resource_corpus_or_routing_symbols():
    for name in (
        "HunspellContainerPipeTransport",
        "SpanishHunspellPipeChecker",
        "run_bounded",
        "supervise",
        "BoundedRun",
        "hardened_container_argv",
        "pipe_stream_container_argv",
        "subprocess",
        "docker",
        "os",
        "Path",
        "open",
        "CallhomeUtterance",
        "parse_chat_lines",
        "ApprovedEnglishScowl",
        "load_approved_english_scowl",
        "CallhomeSourceValidationDecision",
        "combine_screening_and_validation",
        "UtteranceRow",
        "build_condition_manifest",
        "CONDITIONS",
        "train_tokenizer",
        "train_model",
        "run_probe",
        "submit_job",
    ):
        assert not hasattr(diagnostic, name)


def test_module_imports_no_process_container_corpus_or_filesystem_module():
    tree = ast.parse(Path(diagnostic.__file__).read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    forbidden = {
        "subprocess",
        "os",
        "os.path",
        "pathlib",
        "shutil",
        "socket",
        "tempfile",
        "threading",
        "signal",
        "docker",
        "cslm.data.hunspell_container",
        "cslm.data.hunspell_pipe_stream",
        "cslm.data.hunspell_pipe_transport",
        "cslm.data.hunspell_process_supervision",
        "cslm.data.spanish_hunspell_pipe_checker",
        "cslm.data.callhome_chat",
        "cslm.data.callhome_screening",
        "cslm.data.callhome_source_validation",
        "cslm.data.conditions",
        "cslm.data.condition_manifest",
        "cslm.data.english_scowl_resource",
        "cslm.data.io",
        "cslm.paths",
    }
    assert not (imported & forbidden)
    # Only the three already-reviewed shared boundaries are reused.
    assert {name for name in imported if name.startswith("cslm")} == {
        "cslm.data.callhome_lexicon_normalization",
        "cslm.data.lexical_coverage",
        "cslm.data.spanish_hunspell_coverage",
    }


def test_module_defines_no_default_evaluator_checker_or_resource():
    signature_defaults = run_spanish_hunspell_coverage_diagnostic.__kwdefaults__
    # ``evaluator`` is keyword-only and has no default: injection is mandatory.
    assert not signature_defaults
    for name in dir(diagnostic):
        assert "default_evaluator" not in name
        assert "default_checker" not in name
