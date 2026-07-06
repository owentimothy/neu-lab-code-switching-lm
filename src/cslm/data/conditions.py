"""Mapping from ``language_category`` to eligible model-condition candidates.

See the "Condition-candidate rules" section of CLAUDE.md for the source of
truth this module implements.
"""

from __future__ import annotations

_CATEGORY_TO_CONDITIONS: dict[str, list[str]] = {
    "en_only": ["EnglishMono", "MonoCont", "CsCont"],
    "es_only": ["SpanishMono", "MonoCont", "CsCont"],
    "cs_within_utterance": ["CsCont"],
    "neutral_or_bivalent": [],
    "punctuation_or_empty": [],
    "mixed_or_uncertain": [],
    "metadata_or_noise": [],
}

# Applied only when include_neutral_or_bivalent=True. Neutral/bivalent text
# contains no genuine code-switch, so it is never made CsCont-only.
_NEUTRAL_INCLUSION_POLICY: list[str] = ["MonoCont", "CsCont"]


def condition_candidates_for_category(
    language_category: str,
    *,
    include_neutral_or_bivalent: bool = False,
) -> list[str]:
    """Map a ``language_category`` to its eligible ``condition_candidates``.

    ``include_neutral_or_bivalent`` is the explicit inclusion policy switch
    required by CLAUDE.md: neutral/bivalent utterances are excluded by
    default and only made eligible when a caller opts in.
    """
    if language_category not in _CATEGORY_TO_CONDITIONS:
        raise ValueError(f"unknown language_category: {language_category!r}")
    if language_category == "neutral_or_bivalent" and include_neutral_or_bivalent:
        return list(_NEUTRAL_INCLUSION_POLICY)
    return list(_CATEGORY_TO_CONDITIONS[language_category])
