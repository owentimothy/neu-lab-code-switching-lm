import pytest

from cslm.data.conditions import (
    condition_candidates_for_category,
    condition_candidates_for_row,
)


@pytest.mark.parametrize(
    ("category", "expected"),
    [
        ("en_only", ["EnglishMono", "MonoCont", "CsCont"]),
        ("es_only", ["SpanishMono", "MonoCont", "CsCont"]),
        ("cs_within_utterance", ["CsCont"]),
        ("neutral_or_bivalent", []),
        ("punctuation_or_empty", []),
        ("mixed_or_uncertain", []),
        ("metadata_or_noise", []),
    ],
)
def test_default_condition_candidates(category, expected):
    assert condition_candidates_for_category(category) == expected


def test_neutral_or_bivalent_included_only_with_explicit_policy():
    assert condition_candidates_for_category("neutral_or_bivalent") == []
    included = condition_candidates_for_category(
        "neutral_or_bivalent", include_neutral_or_bivalent=True
    )
    assert included == ["MonoCont", "CsCont"]


def test_unknown_category_raises():
    with pytest.raises(ValueError):
        condition_candidates_for_category("not_a_category")


def test_row_aware_matches_category_when_not_flagged():
    # Without the mixed-morpheme flag, the row helper equals the category map.
    for category in ("en_only", "es_only", "cs_within_utterance", "neutral_or_bivalent"):
        assert condition_candidates_for_row(category) == condition_candidates_for_category(
            category
        )


def test_mixed_morpheme_rows_withheld_from_mono_and_monocont():
    # en_only frame with a mixed-morpheme token -> CsCont only.
    assert condition_candidates_for_row(
        "en_only", needs_review_mixed_morpheme=True
    ) == ["CsCont"]
    assert condition_candidates_for_row(
        "es_only", needs_review_mixed_morpheme=True
    ) == ["CsCont"]
    assert "EnglishMono" not in condition_candidates_for_row(
        "en_only", needs_review_mixed_morpheme=True
    )
    assert "MonoCont" not in condition_candidates_for_row(
        "es_only", needs_review_mixed_morpheme=True
    )


def test_mixed_morpheme_filter_only_removes_never_adds():
    # A category that yields no conditions stays empty even when flagged.
    assert condition_candidates_for_row(
        "mixed_or_uncertain", needs_review_mixed_morpheme=True
    ) == []
    assert condition_candidates_for_row(
        "metadata_or_noise", needs_review_mixed_morpheme=True
    ) == []
