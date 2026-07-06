import json
import os
import subprocess
import sys

from cslm.data.diagnostics import build_corpus_summary
from cslm.data.schema import UtteranceRow


def _rows():
    return [
        UtteranceRow(
            utterance_id="a",
            text="hello world",
            source="test",
            conversation_id="c1",
            speaker_id="s1",
            split="train",
            language_category="en_only",
            condition_candidates=["EnglishMono", "MonoCont", "CsCont"],
        ),
        UtteranceRow(
            utterance_id="b",
            text="hola mundo",
            source="test",
            conversation_id="c1",
            speaker_id="s2",
            split="train",
            language_category="es_only",
            condition_candidates=["SpanishMono", "MonoCont", "CsCont"],
        ),
        UtteranceRow(
            utterance_id="c",
            text="I want quiero coffee",
            source="test",
            conversation_id="c2",
            speaker_id="s1",
            split="dev",
            language_category="cs_within_utterance",
            condition_candidates=["CsCont"],
        ),
        UtteranceRow(
            utterance_id="d",
            text="[noise]",
            source="test",
            conversation_id="c2",
            speaker_id="s2",
            split="test",
            language_category="metadata_or_noise",
            condition_candidates=[],
        ),
    ]


def _summary():
    return build_corpus_summary(
        _rows(), corpus_name="unit", data_sources=["unit_test"], seed=0
    )


def test_basic_counts():
    summary = _summary()
    assert summary.n_utterances == 4
    assert summary.n_conversations == 2
    assert summary.counts_by_category["en_only"] == 1
    assert summary.counts_by_category["es_only"] == 1
    assert summary.counts_by_category["cs_within_utterance"] == 1
    assert summary.counts_by_category["metadata_or_noise"] == 1
    assert summary.counts_by_category["neutral_or_bivalent"] == 0


def test_denominators_are_not_conflated():
    summary = _summary()
    assert summary.n_language_containing_utterances == 3
    assert summary.pct_of_all_utterances["cs_within_utterance"] == 25.0
    assert round(summary.pct_of_language_containing_utterances["cs_within_utterance"], 2) == 33.33


def test_pct_of_language_containing_excludes_non_language_categories():
    summary = _summary()
    assert set(summary.pct_of_language_containing_utterances.keys()) == {
        "en_only",
        "es_only",
        "cs_within_utterance",
    }


def test_exclusion_reasons_and_counts():
    summary = _summary()
    assert summary.exclusion_reasons == {"metadata_or_noise": 1}
    assert summary.n_excluded_utterances == 1


def test_word_token_count():
    summary = _summary()
    assert summary.n_word_tokens == 2 + 2 + 4 + 1


def test_token_count_totals():
    summary = _summary()
    # "hello world"(2) "hola mundo"(2) "I want quiero coffee"(4) "[noise]"(1 word, 2 punct)
    assert summary.total_word_tokens_excluding_punctuation == 9
    assert summary.n_word_tokens == summary.total_word_tokens_excluding_punctuation
    assert summary.total_punctuation_tokens == 2
    assert summary.total_tokens_including_punctuation == 11
    assert summary.total_english_word_tokens == 4  # hello, I, want, coffee
    assert summary.total_spanish_word_tokens == 2  # hola, quiero
    assert summary.total_neutral_bivalent_word_tokens == 0  # no eng&spa tokens
    assert summary.total_other_word_tokens == 3  # world, mundo, noise
    # word tokens split cleanly across the four word buckets, with unknown/
    # other tokens kept separate from bivalent (eng&spa) tokens
    assert (
        summary.total_english_word_tokens
        + summary.total_spanish_word_tokens
        + summary.total_neutral_bivalent_word_tokens
        + summary.total_other_word_tokens
    ) == summary.total_word_tokens_excluding_punctuation


def test_switch_transitions():
    summary = _summary()
    assert summary.en_to_es_transitions == 1
    assert summary.es_to_en_transitions == 1
    assert summary.total_switch_transitions == 2


def test_condition_candidate_counts():
    summary = _summary()
    assert summary.condition_candidate_counts == {
        "EnglishMono": 1,
        "SpanishMono": 1,
        "MonoCont": 2,
        "CsCont": 3,
    }


def test_split_counts():
    summary = _summary()
    assert summary.split_counts == {"train": 2, "dev": 1, "test": 1}


def test_to_flat_row_contains_expected_keys():
    flat = _summary().to_flat_row()
    assert flat["n_utterances"] == 4
    assert flat["count__cs_within_utterance"] == 1
    assert flat["condition__CsCont"] == 3
    assert flat["split__train"] == 2


def test_to_flat_row_omits_pct_lang_for_excluded_categories():
    flat = _summary().to_flat_row()
    assert "pct_lang__metadata_or_noise" not in flat
    assert "pct_lang__cs_within_utterance" in flat


def test_pct_of_language_containing_key_order_is_fixed():
    summary = _summary()
    assert list(summary.pct_of_language_containing_utterances.keys()) == [
        "en_only",
        "es_only",
        "cs_within_utterance",
    ]


def test_exclusion_reasons_key_order_is_fixed():
    rows = _rows() + [
        UtteranceRow(
            utterance_id="e",
            text="Maria Netflix.",
            source="test",
            conversation_id="c3",
            speaker_id="s1",
            split="train",
            language_category="neutral_or_bivalent",
            condition_candidates=[],
        ),
        UtteranceRow(
            utterance_id="f",
            text="...",
            source="test",
            conversation_id="c3",
            speaker_id="s2",
            split="train",
            language_category="punctuation_or_empty",
            condition_candidates=[],
        ),
    ]
    summary = build_corpus_summary(rows, corpus_name="unit", data_sources=["unit_test"], seed=0)
    # Order must follow the canonical ALL_CATEGORIES order, not insertion or
    # hash order, so that JSON/CSV output is stable across interpreter runs.
    assert list(summary.exclusion_reasons.keys()) == [
        "neutral_or_bivalent",
        "punctuation_or_empty",
        "metadata_or_noise",
    ]


def test_to_flat_row_key_order_is_stable_across_calls():
    flat_a = _summary().to_flat_row()
    flat_b = _summary().to_flat_row()
    assert list(flat_a.keys()) == list(flat_b.keys())


def _inter_row(uid, *, language_category, speaker_id, is_switch, direction, same_speaker):
    return UtteranceRow(
        utterance_id=uid,
        text="placeholder",
        source="test",
        conversation_id="c1",
        speaker_id=speaker_id,
        split="train",
        language_category=language_category,
        condition_candidates=[],
        is_inter_sentential_switch_from_previous=is_switch,
        inter_sentential_switch_direction_from_previous=direction,
        same_speaker_as_previous=same_speaker,
    )


def test_inter_sentential_switch_counts_and_speaker_split():
    rows = [
        _inter_row(
            "a", language_category="en_only", speaker_id="s1",
            is_switch=None, direction=None, same_speaker=None,  # first utterance
        ),
        _inter_row(
            "b", language_category="es_only", speaker_id="s1",
            is_switch=True, direction="eng_to_spa", same_speaker=True,  # same speaker
        ),
        _inter_row(
            "c", language_category="en_only", speaker_id="s2",
            is_switch=True, direction="spa_to_eng", same_speaker=False,  # cross speaker
        ),
        _inter_row(
            "d", language_category="en_only", speaker_id="s2",
            is_switch=False, direction=None, same_speaker=True,  # no switch
        ),
    ]
    summary = build_corpus_summary(rows, corpus_name="unit", data_sources=["u"], seed=0)
    assert summary.total_inter_sentential_switches == 2
    assert summary.inter_sentential_switches_eng_to_spa == 1
    assert summary.inter_sentential_switches_spa_to_eng == 1
    assert summary.inter_sentential_switches_same_speaker == 1
    assert summary.inter_sentential_switches_cross_speaker == 1


def test_intra_and_inter_sentential_switches_are_separate():
    # The default _rows() have one intra-sentential CS utterance and no
    # inter-sentential switch flags set, so the two diagnostic families are
    # reported independently.
    summary = _summary()
    assert summary.total_switch_transitions == 2  # intra, from the cs utterance
    assert summary.total_inter_sentential_switches == 0  # inter, none flagged


def test_leakage_diagnostics_report_zero_for_conversation_level_splits():
    clean_rows = [
        UtteranceRow(
            utterance_id="a", text="hi", source="t", conversation_id="c1",
            speaker_id="s1", split="train", language_category="en_only",
            condition_candidates=[],
        ),
        UtteranceRow(
            utterance_id="b", text="hey", source="t", conversation_id="c1",
            speaker_id="s2", split="train", language_category="en_only",
            condition_candidates=[],
        ),
        UtteranceRow(
            utterance_id="c", text="hola", source="t", conversation_id="c2",
            speaker_id="s1", split="test", language_category="es_only",
            condition_candidates=[],
        ),
    ]
    clean = build_corpus_summary(clean_rows, corpus_name="unit", data_sources=["u"], seed=0)
    assert clean.n_conversation_ids == 2
    assert clean.n_conversation_ids_spanning_multiple_splits == 0


def test_leakage_diagnostics_flag_conversations_spanning_splits():
    leaky_rows = [
        UtteranceRow(
            utterance_id="a", text="hi", source="t", conversation_id="c1",
            speaker_id="s1", split="train", language_category="en_only",
            condition_candidates=[],
        ),
        UtteranceRow(
            utterance_id="b", text="hey", source="t", conversation_id="c1",
            speaker_id="s1", split="test", language_category="en_only",
            condition_candidates=[],
        ),
    ]
    leaky = build_corpus_summary(leaky_rows, corpus_name="unit", data_sources=["u"], seed=0)
    assert leaky.n_conversation_ids == 1
    assert leaky.n_conversation_ids_spanning_multiple_splits == 1


def test_duplicate_diagnostics_count_repeated_ids_and_texts():
    rows = [
        UtteranceRow(
            utterance_id="dup", text="hello world", source="t", conversation_id="c1",
            speaker_id="s1", split="train", language_category="en_only",
            condition_candidates=[],
        ),
        UtteranceRow(
            utterance_id="dup", text="hello world", source="t", conversation_id="c1",
            speaker_id="s1", split="train", language_category="en_only",
            condition_candidates=[],
        ),
        UtteranceRow(
            utterance_id="unique", text="hello world", source="t", conversation_id="c1",
            speaker_id="s1", split="train", language_category="en_only",
            condition_candidates=[],
        ),
    ]
    summary = build_corpus_summary(rows, corpus_name="unit", data_sources=["u"], seed=0)
    assert summary.n_duplicate_utterance_ids == 1  # "dup" appears twice
    assert summary.n_duplicate_utterance_texts == 1  # "hello world" appears 3x -> 1 repeated value


def test_to_flat_row_contains_new_diagnostic_keys():
    flat = _summary().to_flat_row()
    for key in (
        "total_tokens_including_punctuation",
        "total_word_tokens_excluding_punctuation",
        "total_english_word_tokens",
        "total_spanish_word_tokens",
        "total_neutral_bivalent_word_tokens",
        "total_other_word_tokens",
        "total_punctuation_tokens",
        "total_inter_sentential_switches",
        "inter_sentential_switches_eng_to_spa",
        "inter_sentential_switches_spa_to_eng",
        "inter_sentential_switches_same_speaker",
        "inter_sentential_switches_cross_speaker",
        "n_conversation_ids",
        "n_conversation_ids_spanning_multiple_splits",
        "n_duplicate_utterance_ids",
        "n_duplicate_utterance_texts",
    ):
        assert key in flat


def test_key_order_is_stable_across_hash_seeds():
    """Regression test for the frozenset-iteration-order bug.

    Categories were previously stored in frozensets and iterated directly to
    build serialized dicts; frozenset iteration order depends on
    PYTHONHASHSEED, so JSON/CSV column order could silently change between
    process runs. Run the summary in two subprocesses with different hash
    seeds and assert the emitted key order is identical.
    """
    script = (
        "import json\n"
        "from cslm.data.diagnostics import build_corpus_summary\n"
        "from cslm.data.schema import UtteranceRow\n"
        "rows = [\n"
        "    UtteranceRow(utterance_id='a', text='hello world', source='t', "
        "conversation_id='c1', speaker_id='s1', split='train', "
        "language_category='en_only', condition_candidates=['EnglishMono']),\n"
        "    UtteranceRow(utterance_id='b', text='hola mundo', source='t', "
        "conversation_id='c1', speaker_id='s2', split='train', "
        "language_category='es_only', condition_candidates=['SpanishMono']),\n"
        "    UtteranceRow(utterance_id='c', text='I want quiero coffee', source='t', "
        "conversation_id='c2', speaker_id='s1', split='dev', "
        "language_category='cs_within_utterance', condition_candidates=['CsCont']),\n"
        "    UtteranceRow(utterance_id='d', text='[noise]', source='t', "
        "conversation_id='c2', speaker_id='s2', split='test', "
        "language_category='metadata_or_noise', condition_candidates=[]),\n"
        "]\n"
        "summary = build_corpus_summary(rows, corpus_name='unit', "
        "data_sources=['unit_test'], seed=0)\n"
        "print(json.dumps(list(summary.to_flat_row().keys())))\n"
    )
    outputs = []
    for hashseed in ("1", "42"):
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            env={**os.environ, "PYTHONHASHSEED": hashseed},
            check=True,
        )
        outputs.append(json.loads(result.stdout))
    assert outputs[0] == outputs[1]
