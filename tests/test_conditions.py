import pytest

from cslm.data.conditions import condition_candidates_for_category


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
