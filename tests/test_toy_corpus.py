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
