import json
import subprocess
import sys

import pytest

from cslm.data.bangor_cgwords import BangorUtterance, BangorWord
from cslm.data.bangor_project import project_utterances
from cslm.data.bangor_sample_diagnostics import (
    build_projected_sample_summary,
    flatten_projected_sample_summary,
)
from cslm.utils.paths import project_root

# Keys that would indicate transcript-bearing content leaked into the summary.
FORBIDDEN_KEYS = frozenset(
    {
        "text",
        "raw_text",
        "clean_text",
        "tokens",
        "surfaces",
        "token_language_labels",
        "source_token_language_labels",
        "langids",
    }
)

SAMPLE_DIR = project_root() / "data" / "raw" / "bangor" / "cgwords"
HERRING1 = SAMPLE_DIR / "herring1_cgwords.tsv"
HERRING2 = SAMPLE_DIR / "herring2_cgwords.tsv"


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


def _sample_rows():
    utts = [
        _utt([("the", "eng"), (".", "999")], utt=1),  # en_only
        _utt([("yo", "spa"), ("MIXEDWORD", "eng+spa"), (".", "999")], utt=2),  # es_only + mixed
        _utt([("www", "eng&spa"), (".", "999")], utt=3),  # metadata_or_noise
        _utt([("um", "eng"), ("bueno", "spa"), (".", "999")], utt=4),  # es_only, um neutralized
        _utt([("the", "eng"), ("casa", "spa"), (".", "999")], utt=5),  # cs_within_utterance
    ]
    n_source_word_rows = sum(len(u.words) for u in utts)
    rows = project_utterances(utts)
    return rows, n_source_word_rows


def _summary():
    rows, n_source = _sample_rows()
    return build_projected_sample_summary(rows, n_files=1, n_source_word_rows=n_source)


def _all_keys(obj):
    keys = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(k)
            keys |= _all_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            keys |= _all_keys(v)
    return keys


def test_summary_has_no_text_or_tokens_fields():
    summary = _summary()
    assert _all_keys(summary) & FORBIDDEN_KEYS == set()
    # And the flattened CSV row is likewise free of transcript-bearing columns.
    flat = flatten_projected_sample_summary(summary)
    assert set(flat.keys()) & FORBIDDEN_KEYS == set()


def test_checks_pass_on_projected_rows():
    summary = _summary()
    assert summary["checks"] == {
        "mixed_morpheme_rows_cscont_only": True,
        "metadata_rows_have_no_conditions": True,
        "source_label_length_alignment_ok": True,
    }


def test_counts_reconcile():
    s = _summary()
    word_buckets = (
        s["total_english_word_tokens"]
        + s["total_spanish_word_tokens"]
        + s["total_neutral_bivalent_word_tokens"]
        + s["total_other_word_tokens"]
        + s["total_mixed_morpheme_word_tokens"]
    )
    assert word_buckets == s["total_word_tokens_excluding_punctuation"]
    assert (
        s["total_word_tokens_excluding_punctuation"]
        + s["total_punctuation_tokens"]
        + s["total_metadata_tokens"]
    ) == s["total_tokens_including_punctuation"]
    # Every source word row becomes exactly one token in the projection.
    assert s["total_tokens_including_punctuation"] == s["n_source_word_rows"]


def test_mixed_and_metadata_row_counts():
    s = _summary()
    assert s["n_needs_review_mixed_morpheme_rows"] == 1
    assert s["n_metadata_or_noise_rows"] == 1
    assert s["counts_by_language_category"]["metadata_or_noise"] == 1
    # Mixed row is es_only frame -> CsCont only, never Mono baselines.
    assert s["condition_candidate_counts"]["CsCont"] >= 1


def test_neutralized_disfluency_count():
    s = _summary()
    assert s["n_neutralized_disfluency_tokens"] == 1  # the "um" filler


def test_ordinary_switch_counts_only_from_eng_spa():
    s = _summary()
    # Only the cs row (the/casa) contributes an ordinary eng->spa transition.
    assert s["ordinary_eng_to_spa_switch_count"] == 1
    assert s["ordinary_spa_to_eng_switch_count"] == 0
    assert s["ordinary_token_switch_count"] == 1
    assert s["n_rows_with_ordinary_token_switches"] == 1


def test_todo_note_present_and_flat_row_omits_it():
    s = _summary()
    assert "three" in s["switch_site_localization_todo"]
    flat = flatten_projected_sample_summary(s)
    assert "switch_site_localization_todo" not in flat


# --- Script-level tests over the real two-file sample ----------------------

_REAL_FILES = pytest.mark.skipif(
    not (HERRING1.exists() and HERRING2.exists()),
    reason="Bangor CG-words sample files not present",
)


def _run_script(root):
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "build_bangor_projected_sample_summary.py")],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result


@_REAL_FILES
def test_script_processes_only_two_files_and_writes_outputs():
    root = project_root()
    _run_script(root)

    json_path = root / "outputs" / "corpus_summaries" / "bangor_projected_sample_summary.json"
    csv_path = root / "outputs" / "corpus_summaries" / "bangor_projected_sample_summary.csv"
    assert json_path.exists()
    assert csv_path.exists()

    summary = json.loads(json_path.read_text(encoding="utf-8"))
    assert summary["n_files"] == 2
    assert summary["conversation_ids"] == ["herring1", "herring2"]
    # No transcript-bearing keys anywhere in the published JSON.
    assert _all_keys(summary) & FORBIDDEN_KEYS == set()
    # Safety checks all pass on real data.
    assert summary["checks"]["mixed_morpheme_rows_cscont_only"] is True
    assert summary["checks"]["metadata_rows_have_no_conditions"] is True
    assert summary["checks"]["source_label_length_alignment_ok"] is True


@_REAL_FILES
def test_script_summary_counts_reconcile():
    root = project_root()
    _run_script(root)
    json_path = root / "outputs" / "corpus_summaries" / "bangor_projected_sample_summary.json"
    s = json.loads(json_path.read_text(encoding="utf-8"))
    assert (
        s["total_english_word_tokens"]
        + s["total_spanish_word_tokens"]
        + s["total_neutral_bivalent_word_tokens"]
        + s["total_other_word_tokens"]
        + s["total_mixed_morpheme_word_tokens"]
    ) == s["total_word_tokens_excluding_punctuation"]
    assert (
        s["total_word_tokens_excluding_punctuation"]
        + s["total_punctuation_tokens"]
        + s["total_metadata_tokens"]
    ) == s["total_tokens_including_punctuation"]
    assert s["n_projected_utterance_rows"] == sum(
        s["counts_by_language_category"].values()
    )
