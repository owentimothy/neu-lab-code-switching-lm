import json
import subprocess
import sys

from cslm.data.io import read_utterances_jsonl
from cslm.utils.paths import project_root


def _run_script(root):
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "build_toy_corpus.py")],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_script_writes_expected_output_files():
    root = project_root()
    _run_script(root)

    utterances_path = root / "data" / "processed" / "toy" / "utterances.jsonl"
    summary_json_path = root / "outputs" / "corpus_summaries" / "toy_condition_summary.json"
    summary_csv_path = root / "outputs" / "corpus_summaries" / "toy_condition_summary.csv"

    assert utterances_path.exists()
    assert summary_json_path.exists()
    assert summary_csv_path.exists()

    rows = read_utterances_jsonl(utterances_path)
    assert len(rows) == 18

    summary = json.loads(summary_json_path.read_text(encoding="utf-8"))
    assert summary["n_utterances"] == 18
    assert summary["cs_intra_sentential_count"] == 3
    assert summary["condition_candidate_counts"]["CsCont"] == 11

    csv_text = summary_csv_path.read_text(encoding="utf-8")
    assert "n_utterances" in csv_text.splitlines()[0]


def test_output_files_contain_new_schema_and_diagnostic_fields():
    root = project_root()
    _run_script(root)

    utterances_path = root / "data" / "processed" / "toy" / "utterances.jsonl"
    summary_json_path = root / "outputs" / "corpus_summaries" / "toy_condition_summary.json"
    summary_csv_path = root / "outputs" / "corpus_summaries" / "toy_condition_summary.csv"

    first_row = json.loads(utterances_path.read_text(encoding="utf-8").splitlines()[0])
    for key in (
        "raw_text",
        "clean_text",
        "tokens",
        "token_language_labels",
        "n_tokens_including_punctuation",
        "n_word_tokens_excluding_punctuation",
        "utterance_index",
        "previous_utterance_id",
        "same_speaker_as_previous",
        "is_inter_sentential_switch_from_previous",
        "needs_review_borrowing",
    ):
        assert key in first_row

    summary = json.loads(summary_json_path.read_text(encoding="utf-8"))
    for key in (
        "total_tokens_including_punctuation",
        "total_english_word_tokens",
        "total_spanish_word_tokens",
        "total_neutral_bivalent_word_tokens",
        "total_other_word_tokens",
        "total_punctuation_tokens",
        "total_inter_sentential_switches",
        "inter_sentential_switches_cross_speaker",
        "n_conversation_ids_spanning_multiple_splits",
        "n_duplicate_utterance_ids",
    ):
        assert key in summary

    header = summary_csv_path.read_text(encoding="utf-8").splitlines()[0]
    assert "total_inter_sentential_switches" in header
    assert "n_duplicate_utterance_texts" in header


def test_output_is_byte_for_byte_deterministic_across_runs():
    root = project_root()
    utterances_path = root / "data" / "processed" / "toy" / "utterances.jsonl"
    summary_json_path = root / "outputs" / "corpus_summaries" / "toy_condition_summary.json"
    summary_csv_path = root / "outputs" / "corpus_summaries" / "toy_condition_summary.csv"

    _run_script(root)
    first = {
        p: p.read_bytes()
        for p in (utterances_path, summary_json_path, summary_csv_path)
    }
    _run_script(root)
    second = {
        p: p.read_bytes()
        for p in (utterances_path, summary_json_path, summary_csv_path)
    }
    assert first == second
