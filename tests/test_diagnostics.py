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
