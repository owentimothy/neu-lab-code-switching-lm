import pytest

from cslm.data.diagnostics import build_corpus_summary
from cslm.data.toy_corpus import SOURCE_NAME, build_toy_rows


def test_build_toy_rows_covers_all_seven_categories():
    rows = build_toy_rows(seed=0)
    categories = {row.language_category for row in rows}
    assert categories == {
        "en_only",
        "es_only",
        "cs_within_utterance",
        "neutral_or_bivalent",
        "punctuation_or_empty",
        "mixed_or_uncertain",
        "metadata_or_noise",
    }
    assert len(rows) == 18
    assert all(row.source == SOURCE_NAME for row in rows)


def test_build_toy_rows_is_deterministic():
    rows_a = build_toy_rows(seed=0)
    rows_b = build_toy_rows(seed=0)
    assert [r.to_dict() for r in rows_a] == [r.to_dict() for r in rows_b]


def test_default_condition_candidate_counts():
    rows = build_toy_rows(seed=0)
    summary = build_corpus_summary(
        rows, corpus_name="toy", data_sources=[SOURCE_NAME], seed=0
    )
    assert summary.condition_candidate_counts == {
        "EnglishMono": 4,
        "SpanishMono": 4,
        "MonoCont": 8,
        "CsCont": 11,
    }
    assert summary.cs_intra_sentential_count == 3
    assert summary.n_excluded_utterances == 7


def test_splits_partition_all_rows():
    rows = build_toy_rows(seed=0)
    splits = [row.split for row in rows]
    assert sorted(set(splits)) == ["dev", "test", "train"]
    assert len(splits) == 18


def test_splits_are_conversation_level():
    rows = build_toy_rows(seed=0)
    split_by_conversation: dict[str, str] = {}
    for row in rows:
        expected = split_by_conversation.setdefault(row.conversation_id, row.split)
        assert row.split == expected, (
            f"conversation {row.conversation_id!r} split across multiple splits"
        )


def test_every_split_has_a_language_containing_utterance():
    """Every split must contain at least one en_only/es_only/cs_within_utterance
    row so that diagnostics and downstream sampling have real language signal
    in train, dev, and test, not just excluded categories."""
    rows = build_toy_rows(seed=0)
    language_containing = {"en_only", "es_only", "cs_within_utterance"}
    for split in ("train", "dev", "test"):
        split_categories = {row.language_category for row in rows if row.split == split}
        assert split_categories & language_containing, (
            f"split {split!r} has no language-containing utterance"
        )


@pytest.mark.parametrize(
    "train_frac, dev_frac",
    [
        (0.5, 0.25),
        (0.25, 0.5),
        (0.5, 0.3),
    ],
)
def test_non_default_split_fractions_still_guarantee_language_content(train_frac, dev_frac):
    rows = build_toy_rows(seed=0, train_frac=train_frac, dev_frac=dev_frac)
    language_containing = {"en_only", "es_only", "cs_within_utterance"}
    for split in ("train", "dev", "test"):
        split_categories = {row.language_category for row in rows if row.split == split}
        assert split_categories & language_containing, (
            f"split {split!r} has no language-containing utterance"
        )


@pytest.mark.parametrize(
    "train_frac, dev_frac",
    [
        (0.9, 0.05),  # rounds dev down to 0 of 4 language-containing conversations
        (0.95, 0.025),  # rounds both dev and test down to 0
        (0.9, 0.3),  # fractions overlap, leaving no room for test
        (0.4, 0.4),  # rounds test down to 0
    ],
)
def test_split_fractions_that_cannot_guarantee_language_content_raise(train_frac, dev_frac):
    with pytest.raises(ValueError, match="language-containing"):
        build_toy_rows(seed=0, train_frac=train_frac, dev_frac=dev_frac)


def _rows_by_id():
    return {row.utterance_id: row for row in build_toy_rows(seed=0)}


def test_first_utterance_in_conversation_has_null_previous_fields():
    rows = _rows_by_id()
    # u001 is the first utterance in conv01.
    first = rows["u001"]
    assert first.utterance_index == 0
    assert first.previous_utterance_id is None
    assert first.previous_speaker_id is None
    assert first.previous_language_category is None
    assert first.same_speaker_as_previous is None
    assert first.is_inter_sentential_switch_from_previous is None
    assert first.inter_sentential_switch_direction_from_previous is None


def test_previous_utterance_metadata_is_derived_from_conversation_order():
    rows = _rows_by_id()
    # Within conv01 the order is u001, u002, u004, u005 (u003 belongs to conv02).
    u002 = rows["u002"]
    assert u002.utterance_index == 1
    assert u002.previous_utterance_id == "u001"
    assert u002.previous_speaker_id == "spk1"
    assert u002.previous_language_category == "en_only"
    assert u002.same_speaker_as_previous is False  # u001 spk1 -> u002 spk2

    u004 = rows["u004"]
    assert u004.utterance_index == 2
    assert u004.previous_utterance_id == "u002"
    assert u004.previous_language_category == "en_only"


def test_inter_sentential_switch_flags_on_toy_rows():
    rows = _rows_by_id()
    # u004 (es_only) follows u002 (en_only) in conv01 -> eng_to_spa switch.
    assert rows["u004"].is_inter_sentential_switch_from_previous is True
    assert rows["u004"].inter_sentential_switch_direction_from_previous == "eng_to_spa"
    # u005 (es_only) follows u004 (es_only) -> no switch, but well-defined.
    assert rows["u005"].is_inter_sentential_switch_from_previous is False
    assert rows["u005"].inter_sentential_switch_direction_from_previous is None
    # u008 (cs) follows u007 (cs) -> not well-defined.
    assert rows["u008"].is_inter_sentential_switch_from_previous is None


def test_needs_review_flags_set_only_for_code_switched_utterances():
    for row in build_toy_rows(seed=0):
        is_cs = row.language_category == "cs_within_utterance"
        assert row.needs_review_borrowing is is_cs
        assert row.needs_review_matrix_language is is_cs
        assert row.needs_review_equivalence is is_cs
        # Review-only heuristic values themselves are never auto-assigned.
        assert row.borrowing_status is None
        assert row.matrix_language_heuristic is None
        assert row.equivalence_heuristic is None


def test_token_fields_populated_and_consistent_on_toy_rows():
    for row in build_toy_rows(seed=0):
        assert len(row.token_language_labels) == len(row.tokens)
        assert row.n_tokens_including_punctuation == len(row.tokens)
        assert row.n_word_tokens_excluding_punctuation == (
            row.n_english_word_tokens
            + row.n_spanish_word_tokens
            + row.n_neutral_bivalent_word_tokens
            + row.n_other_word_tokens
        )
        # eng&spa (neutral/bivalent) and other tokens are never conflated: a
        # word token counts toward at most one of the two buckets.
        assert "other" not in row.token_language_labels or row.n_other_word_tokens > 0


def test_monolingual_toy_words_are_labeled_eng_or_spa_not_other():
    rows = {row.utterance_id: row for row in build_toy_rows(seed=0)}
    # u002 previously labeled common English words ("I", "go", "for") as other;
    # they must now be eng, leaving no other-labeled tokens in this en_only row.
    u002 = rows["u002"]
    assert u002.n_other_word_tokens == 0
    assert "other" not in u002.token_language_labels
    # u006 ("...muy...") is es_only; "muy" must be spa, not other.
    u006 = rows["u006"]
    assert u006.n_other_word_tokens == 0


def test_toy_summary_covers_both_switch_directions_and_speaker_types():
    rows = build_toy_rows(seed=0)
    summary = build_corpus_summary(
        rows, corpus_name="toy", data_sources=[SOURCE_NAME], seed=0
    )
    # Both inter-sentential directions are exercised...
    assert summary.inter_sentential_switches_eng_to_spa >= 1
    assert summary.inter_sentential_switches_spa_to_eng >= 1
    # ...and both speaker types.
    assert summary.inter_sentential_switches_same_speaker >= 1
    assert summary.inter_sentential_switches_cross_speaker >= 1
