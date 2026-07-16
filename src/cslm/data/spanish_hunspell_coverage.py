"""Synthetic-testable Spanish coverage boundary for a local Hunspell checker.

The adapter answers only: "how many already-normalized lexical tokens did the
injected checker accept?"  It does not load RLA-ES, launch a process, normalize
tokens, parse CALLHOME, validate language, mark rows clean, or route conditions.

The checker is dependency-injected so ordinary tests use invented tokens and a
fake in-memory implementation.  A concrete local/offline Hunspell transport and
an approved private resource bundle remain separate future gates.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from cslm.data.lexical_coverage import (
    COVERAGE_OUTCOME_ORDER,
    COVERAGE_OUTCOMES,
    check_coverage_fields,
    coverage_fields_from_membership,
)


class SpanishHunspellCoverageError(RuntimeError):
    """Base class for every direct-Hunspell coverage boundary failure."""


class SpanishHunspellInputError(SpanishHunspellCoverageError):
    """The caller did not supply valid already-normalized lexical tokens."""


class SpanishHunspellUnavailableError(SpanishHunspellCoverageError):
    """The injected local checker is absent or failed operationally."""


class SpanishHunspellProtocolError(SpanishHunspellCoverageError):
    """The checker did not return exactly one Boolean per supplied token."""


class SpanishHunspellChecker(Protocol):
    """Narrow private dependency: immutable tokens in, Boolean decisions out."""

    def check_tokens(self, normalized_tokens: tuple[str, ...]) -> Sequence[bool]: ...


@dataclass(frozen=True)
class SpanishHunspellCoverageResult:
    """One input's Spanish lexical coverage, represented by counts only."""

    outcome: str
    n_tokens: int
    n_covered: int
    n_uncovered: int

    def __post_init__(self) -> None:
        check_coverage_fields(
            self.outcome,
            self.n_tokens,
            self.n_covered,
            self.n_uncovered,
        )


def _validate_normalized_tokens(normalized_tokens: object) -> tuple[str, ...]:
    """Validate transport-safe token structure without changing any token."""
    if isinstance(normalized_tokens, (str, bytes, bytearray)) or not isinstance(
        normalized_tokens, Sequence
    ):
        raise SpanishHunspellInputError(
            "normalized_tokens must be a sequence of strings"
        )
    prepared: list[str] = []
    for token in normalized_tokens:
        if not isinstance(token, str):
            raise SpanishHunspellInputError("every token must be a string")
        if not token:
            raise SpanishHunspellInputError("tokens must not be empty")
        if any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in token):
            raise SpanishHunspellInputError(
                "tokens must not contain whitespace or control characters"
            )
        prepared.append(token)
    return tuple(prepared)


def _validate_membership_response(
    response: object,
    *,
    expected_count: int,
) -> tuple[bool, ...]:
    if isinstance(response, (str, bytes, bytearray)) or not isinstance(
        response, Sequence
    ):
        raise SpanishHunspellProtocolError(
            "checker response must be a sequence of booleans"
        )
    if len(response) != expected_count:
        raise SpanishHunspellProtocolError(
            "checker response length must equal token count"
        )
    if any(type(value) is not bool for value in response):
        raise SpanishHunspellProtocolError(
            "checker response must contain only booleans"
        )
    return tuple(response)


@dataclass(frozen=True, slots=True, init=False)
class SpanishHunspellCoverageEvaluator:
    """Reusable evaluator around one injected private local checker.

    The checker is hidden from ``repr`` and cannot be reassigned.  Construction
    validates only the narrow callable interface; approval of a concrete local
    Hunspell transport belongs to the later execution gate.
    """

    _checker: SpanishHunspellChecker = field(repr=False)

    def __init__(self, checker: SpanishHunspellChecker) -> None:
        if not callable(getattr(checker, "check_tokens", None)):
            raise SpanishHunspellUnavailableError(
                "checker must provide a callable check_tokens method"
            )
        object.__setattr__(self, "_checker", checker)

    def evaluate_tokens(
        self,
        normalized_tokens: Sequence[str],
    ) -> SpanishHunspellCoverageResult:
        """Evaluate already-normalized tokens without retaining or returning them."""
        prepared = _validate_normalized_tokens(normalized_tokens)
        if prepared:
            try:
                raw_membership = self._checker.check_tokens(prepared)
            except Exception:
                raise SpanishHunspellUnavailableError(
                    "local checker failed without producing a result"
                ) from None
            membership = _validate_membership_response(
                raw_membership,
                expected_count=len(prepared),
            )
        else:
            membership = ()

        outcome, n_tokens, n_covered, n_uncovered = (
            coverage_fields_from_membership(membership)
        )
        return SpanishHunspellCoverageResult(
            outcome=outcome,
            n_tokens=n_tokens,
            n_covered=n_covered,
            n_uncovered=n_uncovered,
        )


def compute_spanish_hunspell_coverage(
    normalized_tokens: Sequence[str],
    *,
    checker: SpanishHunspellChecker,
) -> SpanishHunspellCoverageResult:
    """One-shot wrapper around :class:`SpanishHunspellCoverageEvaluator`."""
    return SpanishHunspellCoverageEvaluator(checker).evaluate_tokens(normalized_tokens)


__all__ = [
    "COVERAGE_OUTCOME_ORDER",
    "COVERAGE_OUTCOMES",
    "SpanishHunspellChecker",
    "SpanishHunspellCoverageError",
    "SpanishHunspellCoverageEvaluator",
    "SpanishHunspellCoverageResult",
    "SpanishHunspellInputError",
    "SpanishHunspellProtocolError",
    "SpanishHunspellUnavailableError",
    "compute_spanish_hunspell_coverage",
]
