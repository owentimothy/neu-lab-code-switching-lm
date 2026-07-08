import cslm.data.classify as classify_module
from cslm.data.bangor_cgwords import BangorUtterance, BangorWord
from cslm.data.bangor_project import project_utterance, project_utterances
from cslm.data.io import read_utterances_jsonl, write_utterances_jsonl


def _bw(location, surface, langid, *, speaker="AAA", filename="conv", utt=1):
    return BangorWord(
        word_id=location,
        utterance_id=utt,
        location=location,
        surface=surface,
        auto="",
        fix="",
        eng="",
        com="",
        speaker=speaker,
        langid=langid,
        filename=filename,
        clause="",
        clauseno="",
    )


def _utt(pairs, *, speaker="AAA", filename="conv", utt=1):
    """Build a BangorUtterance from (surface, langid) pairs."""
    words = [
        _bw(i + 1, s, lang, speaker=speaker, filename=filename, utt=utt)
        for i, (s, lang) in enumerate(pairs)
    ]
    return BangorUtterance(
        conversation_id=filename,
        source_utterance_id=utt,
        utterance_id=f"{filename}_{utt:06d}",
        speaker_id=speaker,
        words=words,
    )


def test_projection_preserves_raw_langids():
    bu = _utt([("MIXED_STEM_s", "eng&spa+eng"), ("the", "eng"), (".", "999")])
    row = project_utterance(bu)
    assert row.source_token_language_labels == ["eng&spa+eng", "eng", "999"]
    assert row.token_language_labels == ["mixed_morpheme", "eng", "punct"]
    # tokens (surfaces) are carried through in order.
    assert row.tokens == ["MIXED_STEM_s", "the", "."]


def test_www_projects_to_metadata_regardless_of_langid():
    bu = _utt([("www", "eng&spa"), (".", "999")])
    row = project_utterance(bu)
    assert row.token_language_labels == ["metadata", "punct"]
    assert row.source_token_language_labels == ["eng&spa", "999"]
    assert row.n_metadata_tokens == 1
    assert row.n_word_tokens_excluding_punctuation == 0
    assert row.language_category == "metadata_or_noise"
    assert row.condition_candidates == []


def test_mixed_morpheme_projects_and_counts():
    bu = _utt([("MIXED_STEM_s", "eng&spa+eng"), ("the", "eng"), ("boss", "eng"), (".", "999")])
    row = project_utterance(bu)
    assert row.n_mixed_morpheme_word_tokens == 1
    assert row.n_english_word_tokens == 2
    assert row.needs_review_mixed_morpheme is True
    assert row.language_category == "en_only"


def test_mixed_morpheme_row_is_cscont_only():
    # English-frame mixed row.
    en_row = project_utterance(
        _utt([("NAME_STEM_s", "eng&spa+eng"), ("cousin", "eng"), (".", "999")])
    )
    assert en_row.condition_candidates == ["CsCont"]
    for withheld in ("EnglishMono", "SpanishMono", "MonoCont"):
        assert withheld not in en_row.condition_candidates

    # Spanish-frame mixed row.
    es_row = project_utterance(
        _utt([("yo", "spa"), ("MIXEDWORD", "eng+spa"), (".", "999")])
    )
    assert es_row.language_category == "es_only"
    assert es_row.condition_candidates == ["CsCont"]


def test_disfluency_neutralized_but_source_preserved():
    bu = _utt([("um", "eng"), ("good", "eng"), (".", "999")])
    row = project_utterance(bu)
    assert row.token_language_labels == ["neutral", "eng", "punct"]
    # Source langid is untouched by neutralization.
    assert row.source_token_language_labels == ["eng", "eng", "999"]
    assert row.language_category == "en_only"


def test_neutralized_filler_does_not_create_code_switch():
    # spa + eng-filler + punct would look like CS pre-neutralization; the filler
    # is neutralized so the row stays Spanish-only and no eng label survives.
    bu = _utt([("sí", "spa"), ("um", "eng"), (".", "999")])
    row = project_utterance(bu)
    assert "eng" not in row.token_language_labels
    assert row.language_category == "es_only"


def test_disfluency_only_row_not_training_candidate():
    bu = _utt([("um", "eng"), ("uh", "eng"), (".", "999")])
    row = project_utterance(bu)
    assert row.token_language_labels == ["neutral", "neutral", "punct"]
    assert row.language_category == "neutral_or_bivalent"
    assert row.condition_candidates == []


def test_real_lexical_english_and_spanish_remain_cs():
    bu = _utt([("the", "eng"), ("casa", "spa"), (".", "999")])
    row = project_utterance(bu)
    assert row.language_category == "cs_within_utterance"
    assert row.condition_candidates == ["CsCont"]


def test_neutralize_disfluencies_off_is_passthrough():
    bu = _utt([("um", "eng"), (".", "999")])
    row = project_utterance(bu, neutralize_disfluencies=False)
    assert row.token_language_labels == ["eng", "punct"]
    assert row.language_category == "en_only"


def test_toy_classifier_is_not_used_on_bangor_rows(monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("toy classifier must not run on Bangor rows")

    monkeypatch.setattr(classify_module, "classify_utterance", _boom)
    monkeypatch.setattr(classify_module, "annotate_tokens", _boom)
    monkeypatch.setattr(classify_module, "token_language_labels", _boom)

    row = project_utterance(_utt([("the", "eng"), ("casa", "spa"), (".", "999")]))
    assert row.language_category == "cs_within_utterance"


def test_ordered_and_inter_sentential_metadata():
    u1 = _utt([("the", "eng"), (".", "999")], speaker="AAA", utt=1)
    u2 = _utt([("casa", "spa"), (".", "999")], speaker="AAA", utt=2)
    u3 = _utt([("dog", "eng"), (".", "999")], speaker="BBB", utt=3)
    rows = project_utterances([u1, u2, u3])

    assert [r.utterance_index for r in rows] == [0, 1, 2]
    assert rows[0].previous_utterance_id is None
    assert rows[0].is_inter_sentential_switch_from_previous is None

    assert rows[1].previous_utterance_id == "conv_000001"
    assert rows[1].previous_language_category == "en_only"
    assert rows[1].same_speaker_as_previous is True
    assert rows[1].is_inter_sentential_switch_from_previous is True
    assert rows[1].inter_sentential_switch_direction_from_previous == "eng_to_spa"

    assert rows[2].same_speaker_as_previous is False
    assert rows[2].is_inter_sentential_switch_from_previous is True
    assert rows[2].inter_sentential_switch_direction_from_previous == "spa_to_eng"


def test_projected_rows_round_trip_through_jsonl(tmp_path):
    rows = project_utterances(
        [
            _utt([("MIXED_STEM_s", "eng&spa+eng"), ("the", "eng"), (".", "999")], utt=1),
            _utt([("www", "eng&spa"), (".", "999")], utt=2),
        ]
    )
    path = tmp_path / "projected.jsonl"
    write_utterances_jsonl(rows, path)
    reloaded = read_utterances_jsonl(path)
    assert [r.to_dict() for r in reloaded] == [r.to_dict() for r in rows]
    assert reloaded[0].source_token_language_labels == ["eng&spa+eng", "eng", "999"]
    assert reloaded[0].needs_review_mixed_morpheme is True
