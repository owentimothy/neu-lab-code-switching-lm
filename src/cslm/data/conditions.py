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


# Conditions a mixed-morpheme review row is allowed to remain in. Within-word
# language mixing is contested, so such rows are withheld from the clean
# monolingual baselines and from MonoCont, and kept CsCont-only for now.
_MIXED_MORPHEME_ALLOWED_CONDITIONS: frozenset[str] = frozenset({"CsCont"})


def condition_candidates_for_row(
    language_category: str,
    *,
    needs_review_mixed_morpheme: bool = False,
    include_neutral_or_bivalent: bool = False,
) -> list[str]:
    """Row-aware condition candidates, layering per-row policy over the category map.

    Starts from :func:`condition_candidates_for_category` (unchanged for ordinary
    rows) and then, when ``needs_review_mixed_morpheme`` is set, withholds the row
    from ``EnglishMono``, ``SpanishMono``, and ``MonoCont`` — leaving ``CsCont``
    only. This filter can only *remove* conditions, never add them, so a row whose
    category already yields no candidates stays excluded.
    """
    candidates = condition_candidates_for_category(
        language_category,
        include_neutral_or_bivalent=include_neutral_or_bivalent,
    )
    if needs_review_mixed_morpheme:
        candidates = [c for c in candidates if c in _MIXED_MORPHEME_ALLOWED_CONDITIONS]
    return candidates
