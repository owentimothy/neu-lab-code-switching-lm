import pytest

from cslm.data.classify import classify_utterance, switch_transitions


@pytest.mark.parametrize(
    ("text", "expected_category"),
    [
        ("Hello, how are you doing today?", "en_only"),
        ("I want to go to the store for some coffee.", "en_only"),
        ("Hola, como estas hoy?", "es_only"),
        ("Quiero un cafe por favor.", "es_only"),
        ("I want quiero some coffee cafe please.", "cs_within_utterance"),
        ("Hola friend, how are you como estas?", "cs_within_utterance"),
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
    en_to_es, es_to_en = switch_transitions("I want quiero some coffee cafe please.")
    # known-language sequence: want(en) quiero(es) some(en) coffee(en) cafe(es) please(en)
    assert en_to_es == 2
    assert es_to_en == 2


def test_switch_transitions_zero_for_monolingual_text():
    en_to_es, es_to_en = switch_transitions("Hello, how are you doing today?")
    assert (en_to_es, es_to_en) == (0, 0)
