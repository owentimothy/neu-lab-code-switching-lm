"""Language-neutral invariants for content-free lexical coverage results.

This module owns only fixed outcome labels and arithmetic over Boolean membership
decisions.  It never sees a lexicon, resource path, transcript, language label,
condition, validation decision, or routing state.
"""

from __future__ import annotations

from collections.abc import Sequence

COVERAGE_OUTCOME_ORDER: tuple[str, ...] = (
    "all_covered",
    "has_uncovered",
    "no_lexical_tokens",
)
COVERAGE_OUTCOMES: frozenset[str] = frozenset(COVERAGE_OUTCOME_ORDER)


def check_coverage_fields(
    outcome: object,
    n_tokens: object,
    n_covered: object,
    n_uncovered: object,
) -> None:
    """Require exact non-negative counts and an outcome that agrees with them."""
    for name, value in (
        ("n_tokens", n_tokens),
        ("n_covered", n_covered),
        ("n_uncovered", n_uncovered),
    ):
        if type(value) is not int:
            raise ValueError(f"{name} must be an int")
        if value < 0:
            raise ValueError(f"{name} must be non-negative")
    if n_covered + n_uncovered != n_tokens:
        raise ValueError("n_covered + n_uncovered must equal n_tokens")
    if outcome not in COVERAGE_OUTCOMES:
        raise ValueError(f"unknown coverage outcome: {outcome!r}")
    if outcome == "no_lexical_tokens":
        if not (n_tokens == 0 and n_covered == 0 and n_uncovered == 0):
            raise ValueError("no_lexical_tokens requires all counts to be zero")
    elif outcome == "all_covered":
        if not (n_tokens > 0 and n_uncovered == 0 and n_covered == n_tokens):
            raise ValueError(
                "all_covered requires n_tokens > 0, n_uncovered == 0, and "
                "n_covered == n_tokens"
            )
    elif not (n_tokens > 0 and n_uncovered > 0):
        raise ValueError("has_uncovered requires n_tokens > 0 and n_uncovered > 0")


def coverage_fields_from_membership(
    membership: Sequence[bool],
) -> tuple[str, int, int, int]:
    """Convert one exact Boolean per token into fixed outcome/count fields."""
    if isinstance(membership, (str, bytes, bytearray)) or not isinstance(
        membership, Sequence
    ):
        raise ValueError("membership must be a sequence of booleans")
    if any(type(value) is not bool for value in membership):
        raise ValueError("membership must contain only booleans")

    n_tokens = len(membership)
    n_covered = sum(membership)
    n_uncovered = n_tokens - n_covered
    if n_tokens == 0:
        outcome = "no_lexical_tokens"
    elif n_uncovered == 0:
        outcome = "all_covered"
    else:
        outcome = "has_uncovered"
    check_coverage_fields(outcome, n_tokens, n_covered, n_uncovered)
    return outcome, n_tokens, n_covered, n_uncovered
