"""Conservative structural heuristics feeding the CALLHOME screening scaffold.

Converts a :class:`cslm.data.callhome_chat.CallhomeUtterance` into the safe
boolean signals that :func:`cslm.data.callhome_screening.screen_utterance`
accepts. The heuristics **may read the utterance text in memory** to decide the
booleans, but they never print it, return it, or store it in any diagnostic —
only booleans and (downstream) safe reason codes leave this layer.

Scope is deliberately narrow and conservative:

* ``has_parser_warning`` — derived from the utterance's recorded warnings.
* ``is_empty_or_nonlexical`` — True only when the main tier has **no** lexical
  content (empty/whitespace, or only punctuation / CHAT residue markers). When
  in doubt the heuristic leaves it False, so nothing is excluded without cause.
* ``has_possible_foreign_material`` and ``explicit_clean_override`` are **never**
  inferred here (no real language ID yet); they stay False unless a controlled
  caller overlays them.
"""

from __future__ import annotations

import string
from dataclasses import dataclass

from cslm.data.callhome_chat import CallhomeTranscript, CallhomeUtterance
from cslm.data.callhome_screening import CallhomeScreeningDecision, screen_utterance

# CHAT residue that carries no lexical content.
_RESIDUE_TOKENS: frozenset[str] = frozenset({"xxx", "yyy", "www", "0"})
_CHAT_TERMINATORS: frozenset[str] = frozenset(
    {"+/.", "+//.", "+...", "+..?", "++", "+^", "+<", "+/?"}
)


def _token_is_lexical(token: str) -> bool:
    """True if a whitespace-delimited token carries lexical (alphabetic) content."""
    t = token.strip()
    if not t:
        return False
    if t.lower() in _RESIDUE_TOKENS or t in _CHAT_TERMINATORS:
        return False
    if t.startswith("&"):  # CHAT non-word / paralinguistic (e.g. &=laughs, &-uh)
        return False
    if (t.startswith("[") and t.endswith("]")) or (t.startswith("(") and t.endswith(")")):
        return False  # scoped code / pause marker
    # A token with at least one alphabetic character (after trimming surrounding
    # punctuation) is treated as lexical.
    return any(ch.isalpha() for ch in t.strip(string.punctuation))


def _has_lexical_content(text: str | None) -> bool:
    """True if ``text`` contains at least one lexical token. Reads text in memory only."""
    if not text or not text.strip():
        return False
    return any(_token_is_lexical(tok) for tok in text.split())


@dataclass
class CallhomeScreeningSignals:
    """Safe boolean signals for :func:`screen_utterance`. All default False."""

    has_parser_warning: bool = False
    has_possible_foreign_material: bool = False
    is_empty_or_nonlexical: bool = False
    explicit_clean_override: bool = False


def infer_screening_signals(
    utterance: CallhomeUtterance,
    *,
    language_label: str,
) -> CallhomeScreeningSignals:
    """Infer conservative structural signals from an utterance.

    Only ``has_parser_warning`` and ``is_empty_or_nonlexical`` are inferred. No
    foreign-material or clean signal is ever inferred here. ``language_label`` is
    accepted for interface stability and future language-aware inference; it is
    not used by the current structural heuristics.
    """
    return CallhomeScreeningSignals(
        has_parser_warning=bool(utterance.parser_warnings),
        is_empty_or_nonlexical=not _has_lexical_content(utterance.raw_main_tier_text),
        has_possible_foreign_material=False,
        explicit_clean_override=False,
    )


def screen_utterance_with_heuristics(
    utterance: CallhomeUtterance,
    *,
    language_label: str,
    explicit_clean_override: bool = False,
    has_possible_foreign_material: bool = False,
    has_parser_warning: bool = False,
) -> CallhomeScreeningDecision:
    """Infer structural signals, overlay controlled signals, and screen.

    ``explicit_clean_override`` and ``has_possible_foreign_material`` are supplied
    by the caller (tests / future controlled use); they are overlaid on top of
    the inferred structural signals before delegating to :func:`screen_utterance`,
    which keeps the conservative precedence (exclude > review > clean > default).

    ``has_parser_warning`` is an extra overlay (OR-ed with the utterance's own
    recorded warnings) so callers can fold in a **transcript-level** warning that
    is not attached to any single utterance. It is a boolean only — no warning
    text is passed, stored, or printed.
    """
    signals = infer_screening_signals(utterance, language_label=language_label)
    return screen_utterance(
        utterance,
        language_label=language_label,
        has_parser_warning=has_parser_warning or signals.has_parser_warning,
        has_possible_foreign_material=(
            has_possible_foreign_material or signals.has_possible_foreign_material
        ),
        is_empty_or_nonlexical=signals.is_empty_or_nonlexical,
        explicit_clean_override=explicit_clean_override or signals.explicit_clean_override,
    )


def build_screening_decisions_by_turn(
    transcript: CallhomeTranscript,
    *,
    language_label: str,
    overrides_by_turn: dict[int, dict[str, bool]] | None = None,
) -> dict[int, CallhomeScreeningDecision]:
    """Return ``turn_index -> CallhomeScreeningDecision`` using the heuristics.

    ``overrides_by_turn`` optionally maps a turn index to the controlled overlay
    signals (``explicit_clean_override`` / ``has_possible_foreign_material``).
    Only those two keys are read from each overlay.

    A **transcript-level** parser warning (``transcript.parser_warnings``
    non-empty) is folded into every turn's decision as ``has_parser_warning``,
    since such warnings are recorded on the transcript rather than on individual
    utterances and would otherwise be undercounted. Only the boolean presence is
    used — no warning text is read, stored, or printed.
    """
    overrides_by_turn = overrides_by_turn or {}
    transcript_has_warning = bool(transcript.parser_warnings)
    decisions: dict[int, CallhomeScreeningDecision] = {}
    for utterance in transcript.utterances:
        overlay = overrides_by_turn.get(utterance.turn_index, {})
        decisions[utterance.turn_index] = screen_utterance_with_heuristics(
            utterance,
            language_label=language_label,
            explicit_clean_override=overlay.get("explicit_clean_override", False),
            has_possible_foreign_material=overlay.get(
                "has_possible_foreign_material", False
            ),
            has_parser_warning=transcript_has_warning,
        )
    return decisions


def build_screening_outcomes_by_turn(
    transcript: CallhomeTranscript,
    *,
    language_label: str,
    overrides_by_turn: dict[int, dict[str, bool]] | None = None,
) -> dict[int, str]:
    """Return ``turn_index -> outcome`` for :func:`project_transcript`."""
    decisions = build_screening_decisions_by_turn(
        transcript,
        language_label=language_label,
        overrides_by_turn=overrides_by_turn,
    )
    return {turn: decision.outcome for turn, decision in decisions.items()}
