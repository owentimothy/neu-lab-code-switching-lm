"""English SCOWL lexical-*coverage* diagnostic (not source-language validation).

This module answers a deliberately narrow, honest question about a single
utterance:

    "Are this utterance's normalized lexical tokens present in the approved
    English SCOWL word list?"

It does **not** answer "is this utterance monolingual English?". That stronger,
verdict-shaped claim belongs to source-language validation
(:mod:`cslm.data.callhome_lexicon_validation`), which needs the *other* language's
lexicon to be safe. English coverage has no cross-language guard, so it reports
coverage and claims nothing about monolinguality.

Consequences of that scope, enforced by construction:

* the result type carries **only counts and one fixed outcome label** — never
  ``is_validated``, a ``clean`` signal, a condition, a validation method/reason,
  transcript text, tokens, a path, or a free-form note;
* nothing here produces a :class:`CallhomeSourceValidationDecision`, calls
  ``combine_screening_and_validation``, promotes a row, or routes a condition;
* the module imports **no** loader-invoking code — loading the approved bundle
  is the eventual local runner's explicit responsibility, never this module's.

Two layers:

* :func:`compute_english_coverage` — a **pure** comparison over caller-supplied,
  already-normalized tokens and an already-normalized lexicon set. It normalizes
  nothing and loads nothing, and it carries **no approved-resource guarantee**:
  the lexicon argument is trusted verbatim.
* :class:`EnglishScowlCoverageEvaluator` — the **production** layer. Constructed
  from a genuine :class:`ApprovedEnglishScowl`, it normalizes and validates the
  approved lexicon **exactly once** at construction, then reuses it for every
  utterance. Both layers share one internal counting core
  (:func:`_count_coverage`), so membership counting is never duplicated and
  per-utterance work is proportional only to that utterance's token count.
"""

from __future__ import annotations

from collections.abc import Sequence, Set
from dataclasses import dataclass, field

from cslm.data.callhome_chat import CallhomeUtterance
from cslm.data.callhome_lexicon_normalization import lexical_tokens, normalize_lexicon
from cslm.data.english_scowl_resource import ApprovedEnglishScowl

# The three fixed coverage outcomes. An ordered tuple (not a set) so downstream
# aggregate diagnostics can rely on a stable serialized key order.
COVERAGE_OUTCOME_ORDER: tuple[str, ...] = (
    "all_covered",
    "has_uncovered",
    "no_lexical_tokens",
)
COVERAGE_OUTCOMES: frozenset[str] = frozenset(COVERAGE_OUTCOME_ORDER)


class EnglishCoverageError(RuntimeError):
    """Base class for every English SCOWL coverage failure."""


class EnglishCoverageInputError(EnglishCoverageError):
    """The token input is not a sequence of strings."""


class EnglishCoverageLexiconError(EnglishCoverageError):
    """The lexicon is empty/invalid, or an approved bundle was not supplied."""


def _check_coverage_fields(
    outcome: object, n_tokens: object, n_covered: object, n_uncovered: object
) -> None:
    """Raise ``ValueError`` unless the four fields form a self-consistent result.

    Shared by :meth:`EnglishCoverageResult.__post_init__` and the aggregate
    diagnostics' defensive re-check so both enforce the *identical* invariant.
    Counts must be **exact, non-negative ints** — ``type(x) is int`` rejects
    both booleans (a subclass of ``int``) and floats. The outcome label must
    agree exactly with the counts.
    """
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
    else:  # has_uncovered
        if not (n_tokens > 0 and n_uncovered > 0):
            raise ValueError("has_uncovered requires n_tokens > 0 and n_uncovered > 0")


@dataclass(frozen=True)
class EnglishCoverageResult:
    """One utterance's English lexical coverage. Content-free: counts only.

    It records how many normalized lexical tokens were present in the approved
    English lexicon, and nothing that could reconstruct the tokens themselves.
    There is deliberately **no** ``is_validated``, ``clean``, condition,
    validation-method, validation-reason, text, token, path, or note field.

    Invariants (see :func:`_check_coverage_fields`): counts are exact,
    non-negative ints (booleans and floats rejected), ``n_covered + n_uncovered
    == n_tokens``, and the outcome agrees exactly with the counts.
    """

    outcome: str  # one of COVERAGE_OUTCOME_ORDER
    n_tokens: int
    n_covered: int
    n_uncovered: int

    def __post_init__(self) -> None:
        _check_coverage_fields(self.outcome, self.n_tokens, self.n_covered, self.n_uncovered)


def _validate_prepared_lexicon(lexicon: object) -> None:
    """Verify a set-like lexicon is non-empty and holds only non-empty strings.

    This is the **whole-lexicon** scan (cost proportional to the lexicon size).
    Its frequency differs by API:

    * :func:`compute_english_coverage` runs it **once per call**, because that
      function validates whatever caller-supplied set it is handed each time;
    * :class:`EnglishScowlCoverageEvaluator` runs it **once, during construction**,
      on the prepared lexicon, and **never again during per-utterance
      evaluation** (``evaluate_utterance`` calls only :func:`_count_coverage`).

    Messages are fixed and **never echo a lexicon member**.
    """
    if not isinstance(lexicon, Set):
        raise EnglishCoverageLexiconError("normalized_lexicon must be a set of strings")
    if not lexicon:
        raise EnglishCoverageLexiconError("normalized_lexicon must not be empty")
    for entry in lexicon:
        if not isinstance(entry, str):
            raise EnglishCoverageLexiconError("normalized_lexicon must contain only strings")
        if not entry:
            raise EnglishCoverageLexiconError(
                "normalized_lexicon must not contain empty strings"
            )


def _count_coverage(
    normalized_tokens: Sequence[str], prepared_lexicon: Set[str]
) -> EnglishCoverageResult:
    """Validate token structure, count membership, build the checked result.

    The **shared internal counting core**. It **assumes ``prepared_lexicon`` has
    already passed :func:`_validate_prepared_lexicon`** and therefore never scans
    lexicon members — its cost is proportional only to ``len(normalized_tokens)``.
    Both :func:`compute_english_coverage` and
    :meth:`EnglishScowlCoverageEvaluator.evaluate_utterance` route through here, so
    the membership-counting logic exists in exactly one place.
    """
    if isinstance(normalized_tokens, (str, bytes, bytearray)):
        raise EnglishCoverageInputError(
            "normalized_tokens must be a sequence of strings, not a string or bytes"
        )
    if not isinstance(normalized_tokens, Sequence):
        raise EnglishCoverageInputError("normalized_tokens must be a sequence of strings")

    n_covered = 0
    for token in normalized_tokens:
        if not isinstance(token, str):
            raise EnglishCoverageInputError("every token must be a string")
        if token in prepared_lexicon:
            n_covered += 1

    n_tokens = len(normalized_tokens)
    n_uncovered = n_tokens - n_covered
    if n_tokens == 0:
        outcome = "no_lexical_tokens"
    elif n_uncovered == 0:
        outcome = "all_covered"
    else:
        outcome = "has_uncovered"

    return EnglishCoverageResult(
        outcome=outcome,
        n_tokens=n_tokens,
        n_covered=n_covered,
        n_uncovered=n_uncovered,
    )


def compute_english_coverage(
    normalized_tokens: Sequence[str],
    *,
    normalized_lexicon: Set[str],
) -> EnglishCoverageResult:
    """Compare already-normalized tokens against an already-normalized lexicon.

    Pure and total: it **normalizes nothing**, **loads nothing**, and trusts
    ``normalized_lexicon`` verbatim — it therefore carries **no approved-resource
    guarantee**. Callers that need the approved bundle must use
    :class:`EnglishScowlCoverageEvaluator`.

    Both arguments must already have passed through
    :mod:`cslm.data.callhome_lexicon_normalization`. This function validates the
    caller-supplied lexicon (:func:`_validate_prepared_lexicon`) and then delegates
    the token validation and membership counting to the shared core
    (:func:`_count_coverage`); it only counts set membership and never alters a
    token.

    Fails closed: an empty/non-set lexicon or a non-string/empty-string member is
    rejected (``EnglishCoverageLexiconError``, value never echoed); a
    ``str``/``bytes``/``bytearray`` token sequence or a non-``str`` token element
    is rejected (``EnglishCoverageInputError``).
    """
    _validate_prepared_lexicon(normalized_lexicon)
    return _count_coverage(normalized_tokens, normalized_lexicon)


@dataclass(frozen=True, slots=True, init=False)
class EnglishScowlCoverageEvaluator:
    """Reusable coverage evaluator over the **approved** English SCOWL lexicon.

    Construction preserves the approved-resource trust boundary: ``approved_scowl``
    must be an **exact** :class:`ApprovedEnglishScowl` (the type only
    :func:`cslm.data.english_scowl_resource.load_approved_english_scowl` can
    produce), so an arbitrary set — or a subclass forged to look approved — is
    rejected.

    Construction does the expensive work **exactly once**: it normalizes the
    approved entries, runs the full prepared-lexicon validation, and stores the
    result as an immutable exact ``frozenset``. Each :meth:`evaluate_utterance`
    then calls the shared prepared-lexicon counting core, so per-utterance cost is
    proportional only to that utterance's retained token count — the lexicon is
    never re-normalized or re-scanned. The evaluator **does not load the bundle**;
    obtaining the ``ApprovedEnglishScowl`` is the caller's explicit responsibility.

    The instance is frozen and slotted, and the prepared lexicon is hidden from
    ``repr`` — the representation exposes no path, provenance, hash, or entry.
    """

    _lexicon: frozenset[str] = field(repr=False)

    def __init__(self, approved_scowl: ApprovedEnglishScowl) -> None:
        # Exact type, not ``isinstance``: a subclass could override ``entries`` to
        # smuggle in an unapproved lexicon while looking approved.
        if type(approved_scowl) is not ApprovedEnglishScowl:
            raise EnglishCoverageLexiconError(
                "approved_scowl must be an ApprovedEnglishScowl produced by the loader"
            )
        # Normalize once, then validate the prepared lexicon once. Stored as an
        # exact frozenset via object.__setattr__ (the instance is frozen).
        prepared = frozenset(normalize_lexicon(approved_scowl.entries))
        _validate_prepared_lexicon(prepared)
        object.__setattr__(self, "_lexicon", prepared)

    def evaluate_utterance(self, utterance: CallhomeUtterance) -> EnglishCoverageResult:
        """Coverage of one utterance against the prepared approved lexicon.

        Reuses the once-normalized, once-validated lexicon and calls the shared
        counting core directly — no re-normalization and no whole-lexicon scan.
        """
        tokens = lexical_tokens(utterance.raw_main_tier_text)
        return _count_coverage(tokens, self._lexicon)
