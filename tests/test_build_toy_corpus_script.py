import json
import subprocess
import sys

from cslm.data.io import read_utterances_jsonl
from cslm.utils.paths import project_root


def test_script_writes_expected_output_files():
    root = project_root()
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "build_toy_corpus.py")],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr

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
