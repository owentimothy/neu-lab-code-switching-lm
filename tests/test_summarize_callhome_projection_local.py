"""Tests for the local-only CALLHOME projection summary script.

All CALLHOME directories/files here are SYNTHETIC and created under a temporary
directory (fake ``AAA``/``BBB`` speaker codes, ``syn_*`` tokens, obviously-fake
filenames). No real CALLHOME files are used. The script's output must be
aggregate-only: no transcript tokens, speaker codes, or filenames may appear.
"""

import importlib.util
import subprocess
import sys

import pytest

from cslm.utils.paths import project_root

_SCRIPT_PATH = project_root() / "scripts" / "summarize_callhome_projection_local.py"

# Synthetic content that must NEVER appear in aggregate output.
_FORBIDDEN_TOKENS = (
    "syn_alpha",
    "syn_beta",
    "syn_gamma",
    "syn_mortag",
    "AAA",
    "BBB",
    "secretfile",
)

_SYNTH_CHA = "\n".join(
    [
        "@UTF8",
        "@Begin",
        "@Languages:\t{lang}",
        "@Participants:\tAAA Adult, BBB Adult",
        "*AAA:\tsyn_alpha syn_beta .",
        "%mor:\tsyn_mortag_one syn_mortag_two",
        "*BBB:\tsyn_gamma .",
        "@End",
        "",
    ]
)


def _load_script():
    spec = importlib.util.spec_from_file_location("summarize_callhome_local", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_callhome_root(tmp_path, *, n_eng=2, n_spa=1):
    root = tmp_path / "callhome"
    for label, n in (("eng", n_eng), ("spa", n_spa)):
        lang_dir = root / label
        lang_dir.mkdir(parents=True)
        for i in range(n):
            (lang_dir / f"synth_secretfile_{label}_{i}.cha").write_text(
                _SYNTH_CHA.format(lang=label), encoding="utf-8"
            )
    return root


def _all_strings_in_lines(lines):
    return "\n".join(lines)


def test_default_screening_marks_everything_needs_review(tmp_path):
    mod = _load_script()
    root = _make_callhome_root(tmp_path, n_eng=2, n_spa=1)
    summary = mod.summarize_local_projection(root)
    # 2 eng files * 2 turns + 1 spa file * 2 turns = 6 rows.
    assert summary.n_rows == 6
    assert summary.rows_by_source == {"callhome_eng": 4, "callhome_spa": 2}
    assert summary.n_needs_review == 6
    # Nothing admitted to any condition under default screening.
    assert summary.rows_by_condition_candidate == {
        "EnglishMono": 0,
        "SpanishMono": 0,
        "MonoCont": 0,
    }
    assert summary.n_blocked_from_all_conditions == 6


def test_synthetic_clean_screening_populates_conditions(tmp_path):
    mod = _load_script()
    root = _make_callhome_root(tmp_path, n_eng=1, n_spa=1)

    def clean_fn(language_label, conversation_id, turn_index):
        return "clean"

    summary = mod.summarize_local_projection(root, screening_fn=clean_fn)
    # 1 eng * 2 turns clean -> EnglishMono 2, MonoCont from both langs.
    assert summary.rows_by_condition_candidate["EnglishMono"] == 2
    assert summary.rows_by_condition_candidate["SpanishMono"] == 2
    assert summary.rows_by_condition_candidate["MonoCont"] == 4
    assert "CsCont" not in summary.rows_by_condition_candidate
    assert summary.n_blocked_from_all_conditions == 0


def test_missing_root_reports_zero_counts(tmp_path):
    mod = _load_script()
    summary = mod.summarize_local_projection(tmp_path / "does_not_exist")
    assert summary.n_rows == 0
    assert summary.rows_by_source == {"callhome_eng": 0, "callhome_spa": 0}
    assert summary.n_blocked_from_all_conditions == 0


def test_missing_one_language_dir_still_summarizes(tmp_path):
    mod = _load_script()
    root = tmp_path / "callhome"
    (root / "eng").mkdir(parents=True)
    (root / "eng" / "synth_secretfile_eng_0.cha").write_text(
        _SYNTH_CHA.format(lang="eng"), encoding="utf-8"
    )
    # No spa/ directory at all.
    summary = mod.summarize_local_projection(root)
    assert summary.rows_by_source == {"callhome_eng": 2, "callhome_spa": 0}


def test_format_summary_lines_are_aggregate_only(tmp_path):
    mod = _load_script()
    root = _make_callhome_root(tmp_path)

    def clean_fn(language_label, conversation_id, turn_index):
        return "clean"

    summary = mod.summarize_local_projection(root, screening_fn=clean_fn)
    text = _all_strings_in_lines(mod.format_summary_lines(summary))
    for token in _FORBIDDEN_TOKENS:
        assert token not in text, token
    # No de-identified refs or transcript field names leak either.
    for field_name in ("speaker_ref", "source_file_ref", "raw_text", "tokens"):
        assert field_name not in text, field_name


def test_cli_stdout_is_aggregate_only(tmp_path):
    root = _make_callhome_root(tmp_path)
    result = subprocess.run(
        [sys.executable, str(_SCRIPT_PATH), "--root", str(root)],
        capture_output=True,
        text=True,
        cwd=str(project_root()),
        check=True,
    )
    out = result.stdout
    assert "total rows" in out
    assert "callhome_eng" in out  # source label is safe aggregate provenance
    for token in _FORBIDDEN_TOKENS:
        assert token not in out, token
    for field_name in ("speaker_ref", "source_file_ref", "raw_text"):
        assert field_name not in out, field_name


def test_cli_missing_root_exits_cleanly(tmp_path):
    result = subprocess.run(
        [sys.executable, str(_SCRIPT_PATH), "--root", str(tmp_path / "nope")],
        capture_output=True,
        text=True,
        cwd=str(project_root()),
    )
    assert result.returncode == 0
    assert "zero counts" in result.stdout.lower()
    assert "total rows                    : 0" in result.stdout


def test_script_writes_no_files(tmp_path):
    mod = _load_script()
    root = _make_callhome_root(tmp_path)
    before = {p for p in root.rglob("*")}
    mod.summarize_local_projection(root)
    after = {p for p in root.rglob("*")}
    assert before == after  # summarizing created nothing


@pytest.mark.parametrize("bad_bytes", [b"\xff\xfe not utf-8 \x80"])
def test_unparseable_file_is_skipped_not_raised(tmp_path, bad_bytes):
    mod = _load_script()
    root = tmp_path / "callhome"
    (root / "eng").mkdir(parents=True)
    (root / "eng" / "good.cha").write_text(_SYNTH_CHA.format(lang="eng"), encoding="utf-8")
    (root / "eng" / "bad.cha").write_bytes(bad_bytes)
    summary = mod.summarize_local_projection(root)
    # Only the good file contributes (2 turns); the bad file is skipped.
    assert summary.rows_by_source["callhome_eng"] == 2
