import pytest

from cslm.data.classify import (
    annotate_tokens,
    classify_utterance,
    inter_sentential_switch,
    switch_transitions,
    switch_transitions_from_labels,
    token_language_labels,
    tokenize,
)
from cslm.data.schema import TOKEN_LANGUAGE_LABELS


@pytest.mark.parametrize(
    ("text", "expected_category"),
    [
        ("Hello, how are you doing today?", "en_only"),
        ("I want to go to the store for some coffee.", "en_only"),
        ("Hola, como estas hoy?", "es_only"),
        ("Quiero un cafe por favor.", "es_only"),
        ("I want una empanada please.", "cs_within_utterance"),
        ("Hola friend, are you going to la fiesta?", "cs_within_utterance"),
        ("Maria Netflix.", "neutral_or_bivalent"),
        ("Okay Juan.", "neutral_or_bivalent"),
        ("...", "punctuation_or_empty"),
        ("", "punctuation_or_empty"),
        ("Xyzzy blorp fnord.", "mixed_or_uncertain"),
        ("[laughs]", "metadata_or_noise"),
        ("SPEAKER1:", "metadata_or_noise"),
    ],
)
def test_classify_utterance(text, expected_category):
    assert classify_utterance(text) == expected_category


def test_switch_transitions_counts_en_to_es_and_es_to_en():
    en_to_es, es_to_en = switch_transitions("I want una empanada please.")
    # known-language sequence: i(en) want(en) una(es) empanada(es) please(en)
    assert en_to_es == 1
    assert es_to_en == 1


def test_switch_transitions_zero_for_monolingual_text():
    en_to_es, es_to_en = switch_transitions("Hello, how are you doing today?")
    assert (en_to_es, es_to_en) == (0, 0)


def test_tokenize_splits_words_and_single_punctuation():
    assert tokenize("Hello, café.") == ["Hello", ",", "café", "."]


def test_token_language_labels_length_matches_tokens():
    tokens = tokenize("I want una empanada please.")
    labels = token_language_labels(tokens)
    assert len(labels) == len(tokens)
    assert set(labels) <= TOKEN_LANGUAGE_LABELS


def test_token_language_labels_values():
    tokens = tokenize("Hello, café.")
    assert token_language_labels(tokens) == ["eng", "punct", "spa", "punct"]


def test_token_language_labels_marks_bivalent_words():
    # "no", "me", "a" are in the toy bivalent list; "gusta" is unknown -> other.
    tokens = tokenize("No me gusta a.")
    assert token_language_labels(tokens) == ["eng&spa", "eng&spa", "other", "eng&spa", "punct"]


def test_token_language_labels_marks_neutral_words():
    # Proper names / interjections in the neutral list are 'neutral', not 'other'.
    tokens = tokenize("Maria Netflix okay.")
    assert token_language_labels(tokens) == ["neutral", "neutral", "neutral", "punct"]


def test_annotate_tokens_counts_neutral_as_neutral_bivalent_not_other():
    # Issue 2 regression: neutral proper names count toward the neutral/bivalent
    # bucket, never 'other'.
    ann = annotate_tokens("Maria Netflix.")
    assert ann.n_neutral_bivalent_word_tokens == 2
    assert ann.n_other_word_tokens == 0
    assert "other" not in ann.token_language_labels


def test_annotate_tokens_neutral_and_bivalent_share_bucket():
    # 'no' is bivalent (eng&spa); 'Maria' is neutral; both feed neutral/bivalent.
    ann = annotate_tokens("No Maria.")
    assert ann.n_neutral_bivalent_word_tokens == 2
    assert ann.n_other_word_tokens == 0


def test_switch_transitions_from_labels_counts_eng_spa_only():
    # Non eng/spa labels (punct, neutral, eng&spa, other) are ignored.
    labels = ["eng", "eng", "spa", "spa", "eng", "punct"]
    assert switch_transitions_from_labels(labels) == (1, 1)


def test_switch_transitions_from_labels_skips_non_language_labels():
    # neutral/other/eng&spa between eng and spa must not create phantom switches.
    labels = ["eng", "neutral", "other", "eng&spa", "spa"]
    assert switch_transitions_from_labels(labels) == (1, 0)


def test_annotate_tokens_counts_on_code_switched_example():
    ann = annotate_tokens("I want una empanada please.")
    assert ann.n_tokens_including_punctuation == 6
    assert ann.n_word_tokens_excluding_punctuation == 5
    # i, want, please
    assert ann.n_english_word_tokens == 3
    assert ann.n_spanish_word_tokens == 2  # una, empanada
    assert ann.n_neutral_bivalent_word_tokens == 0
    assert ann.n_other_word_tokens == 0
    assert ann.n_punctuation_tokens == 1


def test_annotate_tokens_separates_other_from_neutral_bivalent():
    # "no"/"me" are bivalent (eng&spa); "gusta" is unknown -> other. The two
    # must land in different buckets, not be conflated.
    ann = annotate_tokens("No me gusta café, gracias.")
    assert ann.n_neutral_bivalent_word_tokens == 2  # no, me
    assert ann.n_other_word_tokens == 1  # gusta
    assert ann.n_spanish_word_tokens == 2  # café, gracias
    assert ann.n_english_word_tokens == 0


def test_annotate_tokens_word_totals_are_consistent():
    ann = annotate_tokens("No me gusta café, gracias.")
    assert ann.n_word_tokens_excluding_punctuation == (
        ann.n_english_word_tokens
        + ann.n_spanish_word_tokens
        + ann.n_neutral_bivalent_word_tokens
        + ann.n_other_word_tokens
    )
    assert ann.n_tokens_including_punctuation == (
        ann.n_word_tokens_excluding_punctuation + ann.n_punctuation_tokens
    )


@pytest.mark.parametrize(
    ("previous_category", "current_category", "expected"),
    [
        (None, "en_only", (None, None)),  # first utterance
        ("en_only", "es_only", (True, "eng_to_spa")),
        ("es_only", "en_only", (True, "spa_to_eng")),
        ("en_only", "en_only", (False, None)),
        ("es_only", "es_only", (False, None)),
        ("cs_within_utterance", "en_only", (None, None)),  # no clear dominant prev
        ("en_only", "cs_within_utterance", (None, None)),  # no clear dominant curr
        ("neutral_or_bivalent", "es_only", (None, None)),
    ],
)
def test_inter_sentential_switch(previous_category, current_category, expected):
    assert inter_sentential_switch(previous_category, current_category) == expected
