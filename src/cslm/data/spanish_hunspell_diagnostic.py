"""Synthetic-only orchestration and streaming aggregation for Spanish coverage.

This module answers one narrow engineering question: *given an iterable of
already-constructed utterance objects and one injected coverage evaluator, what
are the corpus-level counts?*  It is the missing seam between the shared
normalization policy, the Spanish coverage adapter, and the language-neutral
coverage arithmetic — all three of which already exist and are reused verbatim.

What it deliberately is **not**:

- it does not read CALLHOME, Bangor, RLA-ES, a bundle, or any other file;
- it does not construct a checker, transport, container, or process;
- it does not tokenize or normalize anything itself (:func:`lexical_tokens` owns
  that rule for every consumer);
- it does not screen, filter, validate, clean, promote, route, or split a row;
- it does not emit, print, or serialize output anywhere.

The evaluator is dependency-injected and has **no default**, so ordinary tests
supply invented utterances and fake in-memory evaluators.  A real runner over
real data remains a separate, later, separately approved gate.

Counting semantics are fixed by
``docs/spanish_direct_hunspell_coverage_contract.md``: the traversal unit is one
utterance occurrence, the counting unit is one normalized lexical-token
occurrence, duplicates are counted repeatedly, unique-type counting is
prohibited, and there is no threshold, rate, or row-level decision.  Coverage is
descriptive only: it cannot establish language, monolinguality, or the absence of
code-switching, and it cannot control condition eligibility.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Final, Protocol

from cslm.data.callhome_lexicon_normalization import lexical_tokens
from cslm.data.lexical_coverage import COVERAGE_OUTCOME_ORDER, check_coverage_fields
from cslm.data.spanish_hunspell_coverage import SpanishHunspellCoverageResult

# Fixed metadata.  These are module constants, never constructor parameters, so a
# caller cannot relabel an aggregate as a different diagnostic or resource.
SCHEMA_VERSION: Final[str] = "spanish_lexical_coverage.aggregate.v1"
DIAGNOSTIC_NAME: Final[str] = "callhome_spanish_rla_es_general_coverage"
DIAGNOSTIC_STATUS: Final[str] = "complete"
RESOURCE_ID: Final[str] = "spanish_rla_es_v2_9_general"
RESOURCE_ROLE: Final[str] = "broad_pan_regional_lexical_coverage_only"

#: Exact public field order of the aggregate mapping (metadata, then counts).
AGGREGATE_FIELD_ORDER: Final[tuple[str, ...]] = (
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
)

#: Conservative whole-object small-cell rule for a *later* external release.
MINIMUM_RELEASABLE_POSITIVE_COUNT: Final[int] = 10

# Fixed, non-sensitive failure text.  No utterance, token, identifier, path,
# count, or underlying exception may ever appear in a raised message.
_RUN_FAILURE_MESSAGE: Final[str] = (
    "synthetic spanish lexical coverage diagnostic failed"
)
_RELEASE_WITHHELD_MESSAGE: Final[str] = (
    "aggregate withheld by the minimum-count release policy"
)
_AGGREGATE_INVALID_MESSAGE: Final[str] = "aggregate state failed its invariant check"

# Sentinel for "attribute absent", so a missing field never needs an ``except``
# block that would chain a foreign exception onto ours.
_MISSING: Final = object()


class SpanishDiagnosticError(RuntimeError):
    """Base class for every synthetic Spanish coverage diagnostic failure."""


class SpanishDiagnosticRunError(SpanishDiagnosticError):
    """Traversal or injected-dependency failure, reported without any detail."""


class SpanishDiagnosticReleaseWithheldError(SpanishDiagnosticError):
    """The complete aggregate is withheld by the minimum-count release policy."""


class SpanishDiagnosticUtterance(Protocol):
    """Structural minimum an utterance must provide: its raw main-tier text.

    Declared structurally rather than by importing a corpus type, so this module
    has no dependency on any transcript reader.
    """

    raw_main_tier_text: str


class SpanishCoverageEvaluator(Protocol):
    """Injected boundary: normalized tokens in, one content-free result out."""

    def evaluate_tokens(
        self,
        normalized_tokens: tuple[str, ...],
    ) -> SpanishHunspellCoverageResult: ...


def _check_aggregate_state(
    aggregate: SpanishLexicalCoverageAggregate,
) -> dict[str, int]:
    """Revalidate a whole aggregate and return its ordered outcome counts.

    Called at each approved mapping, serialization, and release boundary —
    :attr:`SpanishLexicalCoverageAggregate.results_by_outcome`,
    :meth:`SpanishLexicalCoverageAggregate.to_dict`, and
    :func:`require_releasable_aggregate` — not only at construction:
    ``frozen=True`` stops ordinary assignment but not ``object.__setattr__``, so
    an aggregate can be forced into an inconsistent state after it was validated.
    Reading one scalar field directly does not pass through here.  A single fixed
    message is used for every failure, so the error itself reveals neither which
    invariant broke nor any count.
    """
    outcome_counts = aggregate._outcome_counts
    if type(outcome_counts) is not tuple or len(outcome_counts) != len(
        COVERAGE_OUTCOME_ORDER
    ):
        raise ValueError(_AGGREGATE_INVALID_MESSAGE)

    scalars = (
        aggregate.n_utterances_total,
        aggregate.n_utterances_with_lexical_tokens,
        aggregate.n_tokens_total,
        aggregate.n_covered_total,
        aggregate.n_uncovered_total,
    )
    for value in scalars + outcome_counts:
        # ``type(...) is not int`` rejects ``bool``: a flag must never be counted.
        if type(value) is not int or value < 0:
            raise ValueError(_AGGREGATE_INVALID_MESSAGE)

    by_outcome = dict(zip(COVERAGE_OUTCOME_ORDER, outcome_counts, strict=True))
    n_all_covered = by_outcome["all_covered"]
    n_has_uncovered = by_outcome["has_uncovered"]

    if sum(outcome_counts) != aggregate.n_utterances_total:
        raise ValueError(_AGGREGATE_INVALID_MESSAGE)
    if aggregate.n_utterances_with_lexical_tokens != n_all_covered + n_has_uncovered:
        raise ValueError(_AGGREGATE_INVALID_MESSAGE)
    if aggregate.n_covered_total + aggregate.n_uncovered_total != (
        aggregate.n_tokens_total
    ):
        raise ValueError(_AGGREGATE_INVALID_MESSAGE)

    # Implied by the per-utterance invariants: an ``all_covered`` utterance
    # contributes at least one covered token, a ``has_uncovered`` utterance at
    # least one uncovered token, and each token-bearing utterance at least one
    # token.  These can only reject a fabricated aggregate.
    if aggregate.n_tokens_total < aggregate.n_utterances_with_lexical_tokens:
        raise ValueError(_AGGREGATE_INVALID_MESSAGE)
    if aggregate.n_covered_total < n_all_covered:
        raise ValueError(_AGGREGATE_INVALID_MESSAGE)
    if aggregate.n_uncovered_total < n_has_uncovered:
        raise ValueError(_AGGREGATE_INVALID_MESSAGE)

    # The status constant is ``complete``, so an empty population is not a
    # completed diagnostic.  A population whose utterances all yield no retained
    # lexical tokens *is* structurally valid.
    if aggregate.n_utterances_total <= 0:
        raise ValueError(_AGGREGATE_INVALID_MESSAGE)

    return by_outcome


@dataclass(frozen=True, slots=True)
class SpanishLexicalCoverageAggregate:
    """Immutable corpus-level counts for one completed synthetic diagnostic.

    The public schema exposes the three outcome counts **only** under
    ``results_by_outcome``.  They are therefore held in one private immutable
    tuple ordered by :data:`COVERAGE_OUTCOME_ORDER` and excluded from ``repr``:
    public scalar aliases would be a second, unapproved public schema for the
    same numbers.  Metadata is not stored at all — it is served from module
    constants and so cannot be overridden per instance.

    There is deliberately no coverage rate.  A rate would need a denominator
    choice, and a zero-token population has no defensible one.

    :attr:`results_by_outcome`, :meth:`to_dict`, and
    :func:`require_releasable_aggregate` revalidate the whole object before
    exposing or releasing aggregate state, so a post-construction mutation
    cannot produce a mapping or pass the release guard.  Reading one scalar
    field directly returns it unvalidated; the mapping, serialization, and
    release boundaries are where the invariants are enforced.
    """

    n_utterances_total: int
    n_utterances_with_lexical_tokens: int
    n_tokens_total: int
    n_covered_total: int
    n_uncovered_total: int
    _outcome_counts: tuple[int, ...] = field(repr=False)

    def __post_init__(self) -> None:
        _check_aggregate_state(self)

    @property
    def schema_version(self) -> str:
        return SCHEMA_VERSION

    @property
    def diagnostic_name(self) -> str:
        return DIAGNOSTIC_NAME

    @property
    def diagnostic_status(self) -> str:
        return DIAGNOSTIC_STATUS

    @property
    def resource_id(self) -> str:
        return RESOURCE_ID

    @property
    def resource_role(self) -> str:
        return RESOURCE_ROLE

    @property
    def results_by_outcome(self) -> Mapping[str, int]:
        """Read-only outcome counts in the shared fixed outcome order."""
        return MappingProxyType(_check_aggregate_state(self))

    def to_dict(self) -> dict[str, object]:
        """Return the aggregate in the exact public field order, counts only."""
        by_outcome = _check_aggregate_state(self)
        return {
            "schema_version": SCHEMA_VERSION,
            "diagnostic_name": DIAGNOSTIC_NAME,
            "diagnostic_status": DIAGNOSTIC_STATUS,
            "resource_id": RESOURCE_ID,
            "resource_role": RESOURCE_ROLE,
            "n_utterances_total": self.n_utterances_total,
            "n_utterances_with_lexical_tokens": self.n_utterances_with_lexical_tokens,
            # A fresh mapping per call: mutating it cannot reach the aggregate.
            "results_by_outcome": by_outcome,
            "n_tokens_total": self.n_tokens_total,
            "n_covered_total": self.n_covered_total,
            "n_uncovered_total": self.n_uncovered_total,
        }


@dataclass(slots=True)
class _StreamingCounters:
    """Running integer counters — the diagnostic's entire retained state.

    No per-utterance result, token, membership decision, or identifier is kept,
    so peak memory does not grow with the population size.
    """

    n_utterances_total: int = 0
    n_all_covered: int = 0
    n_has_uncovered: int = 0
    n_no_lexical_tokens: int = 0
    n_tokens_total: int = 0
    n_covered_total: int = 0
    n_uncovered_total: int = 0

    def add(self, result: SpanishHunspellCoverageResult) -> None:
        """Fold one result into the counters, then let the caller discard it."""
        # Exact type, not ``isinstance``: a subclass could override the count
        # attributes to smuggle unvalidated values past the shared arithmetic.
        if type(result) is not SpanishHunspellCoverageResult:
            raise ValueError("evaluator must return a SpanishHunspellCoverageResult")
        # Defensive revalidation: the result validated itself at construction, but
        # a frozen dataclass can still be mutated through ``object.__setattr__``.
        check_coverage_fields(
            result.outcome,
            result.n_tokens,
            result.n_covered,
            result.n_uncovered,
        )
        self.n_utterances_total += 1
        if result.outcome == "all_covered":
            self.n_all_covered += 1
        elif result.outcome == "has_uncovered":
            self.n_has_uncovered += 1
        else:
            self.n_no_lexical_tokens += 1
        self.n_tokens_total += result.n_tokens
        self.n_covered_total += result.n_covered
        self.n_uncovered_total += result.n_uncovered

    def build(self) -> SpanishLexicalCoverageAggregate:
        """Materialize the immutable aggregate, re-checking every invariant."""
        counts_by_outcome = {
            "all_covered": self.n_all_covered,
            "has_uncovered": self.n_has_uncovered,
            "no_lexical_tokens": self.n_no_lexical_tokens,
        }
        return SpanishLexicalCoverageAggregate(
            n_utterances_total=self.n_utterances_total,
            n_utterances_with_lexical_tokens=self.n_all_covered + self.n_has_uncovered,
            n_tokens_total=self.n_tokens_total,
            n_covered_total=self.n_covered_total,
            n_uncovered_total=self.n_uncovered_total,
            # Built through the shared vocabulary, never by position.
            _outcome_counts=tuple(
                counts_by_outcome[outcome] for outcome in COVERAGE_OUTCOME_ORDER
            ),
        )


def _raw_main_tier_text(utterance: SpanishDiagnosticUtterance) -> str | None:
    """Read the one field this diagnostic needs, without echoing its value."""
    # ``getattr`` with a sentinel rather than ``try``/``except AttributeError``:
    # raising from inside a handler would chain the foreign exception onto ours.
    raw = getattr(utterance, "raw_main_tier_text", _MISSING)
    if raw is _MISSING:
        raise ValueError("utterance must expose raw_main_tier_text")
    if raw is not None and not isinstance(raw, str):
        raise ValueError("raw_main_tier_text must be a string or None")
    return raw


def run_spanish_hunspell_coverage_diagnostic(
    utterances: Iterable[SpanishDiagnosticUtterance],
    *,
    evaluator: SpanishCoverageEvaluator,
) -> SpanishLexicalCoverageAggregate:
    """Stream every supplied utterance into one immutable aggregate.

    "Run" means one in-memory pass: no process is started and nothing is read
    from disk or written anywhere.  Per utterance the traversal calls
    :func:`lexical_tokens` exactly once, the injected ``evaluator`` exactly once,
    folds the returned result into integer counters, and then discards it.

    ``utterances`` may be any iterable, including a one-shot generator; it is
    iterated exactly once and is never measured, indexed, or materialized.

    **Every** supplied utterance is processed.  There is no screening, clean,
    validation, source, condition, or eligibility filter here, and adding one
    would silently change the diagnostic's denominator.

    Failure is atomic: any traversal, normalization, evaluator, or invariant
    failure aborts the whole diagnostic with a fixed
    :class:`SpanishDiagnosticRunError`, returning no aggregate and exposing no
    partial counts.  The failing exception is neither re-raised, stored, copied,
    nor chained: the fixed error is raised *after* the handler has exited, so it
    carries no ``__cause__`` and no ``__context__`` through which a token,
    utterance, identifier, or path could still be reached.  ``KeyboardInterrupt``
    and ``SystemExit`` propagate as the very same object, so the caller stays
    interruptible.
    """
    counters = _StreamingCounters()
    # ``None`` is the whole failure record: no exception, message, type, or
    # traceback from the failing dependency survives the handler.
    aggregate: SpanishLexicalCoverageAggregate | None = None
    try:
        # Inside the boundary: probing a hostile dependency can itself raise, and
        # that exception must not escape unwrapped either.
        if not callable(getattr(evaluator, "evaluate_tokens", None)):
            raise ValueError("evaluator must provide a callable evaluate_tokens method")
        if isinstance(utterances, (str, bytes, bytearray)):
            raise ValueError("utterances must be an iterable of utterance objects")
        for utterance in utterances:
            # Normalization is owned by the shared policy module, not here.
            tokens = tuple(lexical_tokens(_raw_main_tier_text(utterance)))
            counters.add(evaluator.evaluate_tokens(tokens))
            # ``tokens`` and the result go out of scope on the next iteration.
        aggregate = counters.build()
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        aggregate = None
    if aggregate is None:
        # Raised outside the handler, so the active exception is already cleared.
        raise SpanishDiagnosticRunError(_RUN_FAILURE_MESSAGE)
    return aggregate


def _corpus_derived_counts(
    aggregate: SpanishLexicalCoverageAggregate,
    by_outcome: Mapping[str, int],
) -> tuple[int, ...]:
    """Every count in the aggregate that is derived from the population."""
    return (
        aggregate.n_utterances_total,
        aggregate.n_utterances_with_lexical_tokens,
        aggregate.n_tokens_total,
        aggregate.n_covered_total,
        aggregate.n_uncovered_total,
        *by_outcome.values(),
    )


def require_releasable_aggregate(
    aggregate: SpanishLexicalCoverageAggregate,
) -> SpanishLexicalCoverageAggregate:
    """Whole-object small-cell guard for a *possible later* external release.

    This is a policy seam only: passing the guard authorizes no output, and this
    module has no way to emit one.  The rule is conservative and whole-object —
    if **any** corpus-derived count is positive but below
    :data:`MINIMUM_RELEASABLE_POSITIVE_COUNT`, the entire aggregate is withheld.
    A zero is permitted (it reveals no small cell), and the fixed metadata
    constants do not participate.

    The object is revalidated first: an aggregate mutated after construction is
    withheld rather than released.  Every withheld path raises the identical
    fixed :class:`SpanishDiagnosticReleaseWithheldError` with no ``__cause__``
    and no ``__context__``, and returns no partial, redacted, or rounded object.

    Returns the *same, unmodified* aggregate when eligible.  It mutates nothing,
    serializes nothing, and prints nothing.
    """
    # Fail closed: anything that is not exactly this aggregate type is withheld.
    if type(aggregate) is not SpanishLexicalCoverageAggregate:
        raise SpanishDiagnosticReleaseWithheldError(_RELEASE_WITHHELD_MESSAGE)

    by_outcome: dict[str, int] | None = None
    try:
        by_outcome = _check_aggregate_state(aggregate)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception:
        by_outcome = None
    if by_outcome is None:
        # Raised outside the handler: the invariant failure is not chained on.
        raise SpanishDiagnosticReleaseWithheldError(_RELEASE_WITHHELD_MESSAGE)

    for count in _corpus_derived_counts(aggregate, by_outcome):
        if 0 < count < MINIMUM_RELEASABLE_POSITIVE_COUNT:
            raise SpanishDiagnosticReleaseWithheldError(_RELEASE_WITHHELD_MESSAGE)
    return aggregate


__all__ = [
    "AGGREGATE_FIELD_ORDER",
    "DIAGNOSTIC_NAME",
    "DIAGNOSTIC_STATUS",
    "MINIMUM_RELEASABLE_POSITIVE_COUNT",
    "RESOURCE_ID",
    "RESOURCE_ROLE",
    "SCHEMA_VERSION",
    "SpanishCoverageEvaluator",
    "SpanishDiagnosticError",
    "SpanishDiagnosticReleaseWithheldError",
    "SpanishDiagnosticRunError",
    "SpanishDiagnosticUtterance",
    "SpanishLexicalCoverageAggregate",
    "require_releasable_aggregate",
    "run_spanish_hunspell_coverage_diagnostic",
]
