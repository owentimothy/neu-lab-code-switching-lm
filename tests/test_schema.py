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
