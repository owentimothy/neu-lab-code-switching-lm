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


def test_consistent_token_counts_accepted():
    row = _make_row(
        tokens=["Hola", "Maria", "."],
        token_language_labels=["spa", "neutral", "punct"],
        n_tokens_including_punctuation=3,
        n_word_tokens_excluding_punctuation=2,
        n_spanish_word_tokens=1,
        n_neutral_bivalent_word_tokens=1,  # neutral counts toward neutral/bivalent
        n_punctuation_tokens=1,
    )
    assert row.n_neutral_bivalent_word_tokens == 1


def test_inconsistent_word_token_count_rejected():
    with pytest.raises(ValueError, match="n_english_word_tokens"):
        _make_row(
            tokens=["Hello", "world"],
            token_language_labels=["eng", "other"],
            n_tokens_including_punctuation=2,
            n_word_tokens_excluding_punctuation=2,
            n_english_word_tokens=2,  # labels say only 1 eng
            n_other_word_tokens=0,
        )


def test_inconsistent_neutral_bivalent_count_rejected():
    # neutral + eng&spa must both feed n_neutral_bivalent_word_tokens.
    with pytest.raises(ValueError, match="n_neutral_bivalent_word_tokens"):
        _make_row(
            tokens=["Maria", "no"],
            token_language_labels=["neutral", "eng&spa"],
            n_tokens_including_punctuation=2,
            n_word_tokens_excluding_punctuation=2,
            n_neutral_bivalent_word_tokens=1,  # should be 2
        )


def test_inter_sentential_switch_true_requires_previous_utterance_id():
    with pytest.raises(ValueError, match="previous_utterance_id is None"):
        _make_row(
            is_inter_sentential_switch_from_previous=True,
            inter_sentential_switch_direction_from_previous="eng_to_spa",
            previous_language_category="en_only",
            same_speaker_as_previous=True,
            previous_utterance_id=None,
        )


def test_inter_sentential_switch_true_requires_same_speaker_flag():
    with pytest.raises(ValueError, match="same_speaker_as_previous"):
        _make_row(
            is_inter_sentential_switch_from_previous=True,
            inter_sentential_switch_direction_from_previous="eng_to_spa",
            previous_utterance_id="u000",
            previous_language_category="en_only",
            same_speaker_as_previous=None,
        )


def test_inter_sentential_switch_true_requires_direction():
    with pytest.raises(ValueError, match="direction"):
        _make_row(
            is_inter_sentential_switch_from_previous=True,
            inter_sentential_switch_direction_from_previous=None,
            previous_utterance_id="u000",
            previous_language_category="en_only",
            same_speaker_as_previous=True,
        )


def test_mixed_morpheme_and_metadata_labels_accepted():
    # mixed_morpheme is a word token; metadata is neither word nor punctuation.
    row = _make_row(
        tokens=["tagueé", "www", "."],
        token_language_labels=["mixed_morpheme", "metadata", "punct"],
        n_tokens_including_punctuation=3,
        n_word_tokens_excluding_punctuation=1,
        n_mixed_morpheme_word_tokens=1,
        n_metadata_tokens=1,
        n_punctuation_tokens=1,
        needs_review_mixed_morpheme=True,
    )
    assert row.n_mixed_morpheme_word_tokens == 1
    assert row.n_metadata_tokens == 1
    assert row.needs_review_mixed_morpheme is True


def test_inconsistent_mixed_morpheme_count_rejected():
    with pytest.raises(ValueError, match="n_mixed_morpheme_word_tokens"):
        _make_row(
            tokens=["tagueé", "the"],
            token_language_labels=["mixed_morpheme", "eng"],
            n_tokens_including_punctuation=2,
            n_word_tokens_excluding_punctuation=2,
            n_english_word_tokens=1,
            n_mixed_morpheme_word_tokens=0,  # should be 1
        )


def test_metadata_excluded_from_word_tokens():
    with pytest.raises(ValueError, match="n_word_tokens_excluding_punctuation"):
        _make_row(
            tokens=["www"],
            token_language_labels=["metadata"],
            n_tokens_including_punctuation=1,
            n_word_tokens_excluding_punctuation=1,  # metadata is not a word token
            n_metadata_tokens=1,
        )


def test_source_token_language_labels_length_mismatch_rejected():
    with pytest.raises(ValueError, match="source_token_language_labels length"):
        _make_row(
            tokens=["Hola", "."],
            token_language_labels=["spa", "punct"],
            source_token_language_labels=["spa"],  # too short
            n_tokens_including_punctuation=2,
            n_word_tokens_excluding_punctuation=1,
            n_spanish_word_tokens=1,
            n_punctuation_tokens=1,
        )


def test_source_token_language_labels_round_trip_via_to_dict():
    row = _make_row(
        tokens=["Ana's", "."],
        token_language_labels=["mixed_morpheme", "punct"],
        source_token_language_labels=["eng&spa+eng", "999"],
        n_tokens_including_punctuation=2,
        n_word_tokens_excluding_punctuation=1,
        n_mixed_morpheme_word_tokens=1,
        n_punctuation_tokens=1,
        needs_review_mixed_morpheme=True,
    )
    d = row.to_dict()
    assert d["source_token_language_labels"] == ["eng&spa+eng", "999"]
    assert d["n_mixed_morpheme_word_tokens"] == 1
    assert d["n_metadata_tokens"] == 0
    assert d["needs_review_mixed_morpheme"] is True
    # Reconstructing from the dict preserves all new fields.
    rebuilt = UtteranceRow(**d)
    assert rebuilt.source_token_language_labels == ["eng&spa+eng", "999"]
    assert rebuilt.needs_review_mixed_morpheme is True


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
        "source_token_language_labels",
        "n_tokens_including_punctuation",
        "n_word_tokens_excluding_punctuation",
        "n_english_word_tokens",
        "n_spanish_word_tokens",
        "n_neutral_bivalent_word_tokens",
        "n_other_word_tokens",
        "n_mixed_morpheme_word_tokens",
        "n_punctuation_tokens",
        "n_metadata_tokens",
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
        "needs_review_mixed_morpheme",
    ):
        assert key in d
    assert d["tokens"] == ["Hello"]
    assert d["needs_review_borrowing"] is True
    assert d["borrowing_status"] is None
