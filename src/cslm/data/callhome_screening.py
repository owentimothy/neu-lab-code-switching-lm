"""Conservative CALLHOME monolingual screening scaffold (synthetic-tested).

This is **not** a language-ID system. It decides a screening *outcome* for a
CALLHOME utterance from **explicit, caller-provided safe signals only** (booleans
and the language label), never by inspecting transcript content. Real language
identification is deferred; until it exists, the honest default for every row is
``needs_review`` (nothing is admitted to a monolingual condition).

Outcomes and their downstream meaning follow ``docs/callhome_monolingual_screening.md``:

* ``clean``        — unambiguously single-language; may feed the monolingual
  conditions. Only returned on an **explicit** clean signal with no
  review/blocking signal present.
* ``needs_review`` — ambiguous or unscreened; neither admitted nor excluded.
* ``excluded``     — cannot be clean monolingual material (empty/non-lexical, or
  an unsupported language).

Reason codes are a small, fixed vocabulary of **safe labels** — they carry no
transcript text. ``notes`` is optional and must likewise never contain
transcript text (it is for short internal labels only).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from cslm.data.callhome_chat import CallhomeTranscript, CallhomeUtterance
from cslm.data.callhome_project import SCREENING_OUTCOMES

# Language directories screening understands (mirrors callhome_project sources).
SUPPORTED_LANGUAGE_LABELS: frozenset[str] = frozenset({"eng", "spa"})

# Safe, content-free reason codes. No transcript text is ever stored as a reason.
REASON_CODES: frozenset[str] = frozenset(
    {
        "source_language_expected",
        "ambiguous_foreign_material",
        "possible_code_switching",
        "parser_warning",
        "empty_or_nonlexical",
        "unsupported_language_label",
        "default_unscreened",
    }
)

_DEFAULT_OUTCOME = "needs_review"


@dataclass
class CallhomeScreeningDecision:
    """A screening outcome plus safe, content-free reason codes."""

    outcome: str
    reason_codes: list[str] = field(default_factory=list)
    notes: str | None = None  # short internal label only; never transcript text

    def __post_init__(self) -> None:
        if self.outcome not in SCREENING_OUTCOMES:
            raise ValueError(f"unknown screening outcome: {self.outcome!r}")
        if not self.reason_codes:
            raise ValueError("reason_codes must not be empty")
        unknown = set(self.reason_codes) - REASON_CODES
        if unknown:
            raise ValueError(f"unknown reason codes: {sorted(unknown)}")


def default_decision() -> CallhomeScreeningDecision:
    """The conservative default: ``needs_review`` / ``default_unscreened``."""
    return CallhomeScreeningDecision(
        outcome=_DEFAULT_OUTCOME, reason_codes=["default_unscreened"]
    )


def screen_utterance(
    utterance: CallhomeUtterance,
    *,
    language_label: str,
    has_parser_warning: bool = False,
    has_possible_foreign_material: bool = False,
    is_empty_or_nonlexical: bool = False,
    explicit_clean_override: bool = False,
) -> CallhomeScreeningDecision:
    """Screen one utterance from explicit safe signals only (no content read).

    Conservative precedence: an unsupported language or empty/non-lexical row is
    ``excluded``; any parser warning or possible foreign material forces
    ``needs_review``; ``clean`` is returned **only** on an explicit clean
    override with no review/blocking signal; otherwise the default
    ``needs_review``/``default_unscreened`` applies.

    ``has_parser_warning`` is OR-ed with the utterance's own recorded warnings
    (a count-derived boolean, not content).
    """
    if language_label not in SUPPORTED_LANGUAGE_LABELS:
        return CallhomeScreeningDecision(
            outcome="excluded", reason_codes=["unsupported_language_label"]
        )

    warning = has_parser_warning or bool(utterance.parser_warnings)

    exclude_reasons: list[str] = []
    review_reasons: list[str] = []

    if is_empty_or_nonlexical:
        exclude_reasons.append("empty_or_nonlexical")
    if has_possible_foreign_material:
        review_reasons.extend(["ambiguous_foreign_material", "possible_code_switching"])
    if warning:
        review_reasons.append("parser_warning")

    if exclude_reasons:
        # Excluded is most severe; keep any review reasons too for completeness.
        return CallhomeScreeningDecision(
            outcome="excluded", reason_codes=exclude_reasons + review_reasons
        )
    if review_reasons:
        return CallhomeScreeningDecision(
            outcome="needs_review", reason_codes=review_reasons
        )
    if explicit_clean_override:
        return CallhomeScreeningDecision(
            outcome="clean", reason_codes=["source_language_expected"]
        )
    return default_decision()


def build_screening_by_turn(
    transcript: CallhomeTranscript,
    *,
    language_label: str,
    signals_by_turn: dict[int, dict[str, bool]] | None = None,
) -> dict[int, str]:
    """Build a ``turn_index -> outcome`` map for :func:`project_transcript`.

    Every turn defaults to ``needs_review``. ``signals_by_turn`` optionally maps
    a turn index to a dict of the safe boolean signals accepted by
    :func:`screen_utterance` (for synthetic/test or future controlled use); a
    turn's own recorded parser warnings are always folded in automatically.
    """
    signals_by_turn = signals_by_turn or {}
    outcomes: dict[int, str] = {}
    for utterance in transcript.utterances:
        signals = dict(signals_by_turn.get(utterance.turn_index, {}))
        decision = screen_utterance(
            utterance, language_label=language_label, **signals
        )
        outcomes[utterance.turn_index] = decision.outcome
    return outcomes
