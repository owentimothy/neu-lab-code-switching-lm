import pytest

from cslm.data.schema import UtteranceRow


def _make_row(**overrides):
    fields = dict(
        utterance_id="u001",
        text="Hello there.",
        source="toy_synthetic_v1",
        conversation_id="conv01",
        speaker_id="spk1",
        split="train",
        language_category="en_only",
        condition_candidates=["EnglishMono", "MonoCont", "CsCont"],
    )
    fields.update(overrides)
    return UtteranceRow(**fields)


def test_valid_row_round_trips_to_dict():
    row = _make_row()
    d = row.to_dict()
    assert d["utterance_id"] == "u001"
    assert d["condition_candidates"] == ["EnglishMono", "MonoCont", "CsCont"]


def test_empty_utterance_id_rejected():
    with pytest.raises(ValueError):
        _make_row(utterance_id="")


def test_invalid_split_rejected():
    with pytest.raises(ValueError):
        _make_row(split="validation")


def test_invalid_language_category_rejected():
    with pytest.raises(ValueError):
        _make_row(language_category="not_a_category")


def test_invalid_condition_candidate_rejected():
    with pytest.raises(ValueError):
        _make_row(condition_candidates=["NotACondition"])


def test_raw_and_clean_text_default_to_text():
    row = _make_row(text="Hello there.")
    assert row.raw_text == "Hello there."
    assert row.clean_text == "Hello there."


def test_explicit_raw_and_clean_text_are_preserved():
    row = _make_row(raw_text="Hello  there .", clean_text="Hello there.")
    assert row.raw_text == "Hello  there ."
    assert row.clean_text == "Hello there."


def test_token_language_labels_length_mismatch_rejected():
    with pytest.raises(ValueError, match="token_language_labels length"):
        _make_row(tokens=["Hello", "there"], token_language_labels=["eng"])


def test_invalid_token_language_label_rejected():
    with pytest.raises(ValueError, match="invalid token_language_labels"):
        _make_row(tokens=["Hello"], token_language_labels=["english"])


def test_invalid_inter_sentential_direction_rejected():
    with pytest.raises(ValueError, match="inter_sentential_switch_direction"):
        _make_row(inter_sentential_switch_direction_from_previous="en2es")


def test_to_dict_includes_new_schema_fields():
    row = _make_row(
        tokens=["Hello"],
        token_language_labels=["eng"],
        n_tokens_including_punctuation=1,
        n_word_tokens_excluding_punctuation=1,
        n_english_word_tokens=1,
        utterance_index=0,
        needs_review_borrowing=True,
    )
    d = row.to_dict()
    for key in (
        "raw_text",
        "clean_text",
        "tokens",
        "token_language_labels",
        "n_tokens_including_punctuation",
        "n_word_tokens_excluding_punctuation",
        "n_english_word_tokens",
        "n_spanish_word_tokens",
        "n_neutral_bivalent_word_tokens",
        "n_other_word_tokens",
        "n_punctuation_tokens",
        "utterance_index",
        "previous_utterance_id",
        "previous_speaker_id",
        "previous_language_category",
        "same_speaker_as_previous",
        "is_inter_sentential_switch_from_previous",
        "inter_sentential_switch_direction_from_previous",
        "borrowing_status",
        "needs_review_borrowing",
        "matrix_language_heuristic",
        "needs_review_matrix_language",
        "equivalence_heuristic",
        "needs_review_equivalence",
    ):
        assert key in d
    assert d["tokens"] == ["Hello"]
    assert d["needs_review_borrowing"] is True
    assert d["borrowing_status"] is None
