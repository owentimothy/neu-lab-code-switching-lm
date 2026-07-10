"""Tests for the DISABLED aggregate-only CALLHOME lexicon dry-run script stub.

Everything here is SYNTHETIC: projected rows and validation decisions are built
directly with obviously-fake safe fields (``synth_*`` ids/refs). No real CALLHOME
data is parsed, no lexicons are loaded, no network is touched, and nothing is
written under data/resources/local_lexicons/. The stub must refuse to run a real
dry run and must only ever emit aggregate counts.
"""

import importlib.util
import json
import sys

import pytest

from cslm.data.callhome_project import CallhomeProjectedRow
from cslm.data.callhome_source_validation import (
    default_source_validation,
    explicit_source_validation,
)
from cslm.utils.paths import project_root

_SCRIPT_PATH = project_root() / "scripts" / "dry_run_callhome_lexicon_validation.py"
_SUMMARY_SCRIPT_PATH = project_root() / "scripts" / "summarize_callhome_projection_local.py"

# Synthetic, transcript-shaped strings that must NEVER surface in aggregate output.
_FORBIDDEN_STRINGS = (
    "synth_conv",  # conversation id
    "spk_synthsecret",  # speaker ref
    "file_synthsecret",  # source file ref
    "syn_alpha",  # token-like
    "AAA",  # speaker code
    "secretfile",  # filename-like
)


def _load_script():
    spec = importlib.util.spec_from_file_location("dry_run_callhome_lexicon", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    # Register before exec so the module's @dataclass can resolve its annotations.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _row(source, outcome, candidates=None):
    """A synthetic projected row with fake, safe-looking provenance fields."""
    return CallhomeProjectedRow(
        source=source,
        conversation_id="synth_conv",
        turn_index=0,
        speaker_ref="spk_synthsecret",
        source_file_ref="file_synthsecret",
        screening_outcome=outcome,
        condition_candidates=list(candidates or []),
        needs_review=(outcome == "needs_review"),
    )


def test_script_module_imports():
    mod = _load_script()
    assert hasattr(mod, "summarize_dry_run")
    assert hasattr(mod, "DryRunValidationSummary")
    assert hasattr(mod, "build_arg_parser")
    assert hasattr(mod, "main")


def test_default_cli_refuses_without_allow_flag(capsys):
    mod = _load_script()
    rc = mod.main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert "refus" in out.lower()
    # No transcript-bearing content in the refusal message.
    for s in _FORBIDDEN_STRINGS:
        assert s not in out


def test_allow_flag_hits_unimplemented_placeholder():
    mod = _load_script()
    # Even when explicitly opted in, the real dry run is intentionally absent.
    with pytest.raises(NotImplementedError):
        mod.main(["--allow-real-dry-run"])


def test_parser_exposes_explicit_path_arguments():
    mod = _load_script()
    help_text = mod.build_arg_parser().format_help()
    for flag in (
        "--callhome-root",
        "--english-lexicon",
        "--spanish-lexicon",
        "--output",
        "--allow-real-dry-run",
    ):
        assert flag in help_text


def test_summarize_dry_run_returns_aggregate_counts():
    mod = _load_script()
    rows = [
        _row("callhome_eng", "needs_review"),
        _row("callhome_spa", "needs_review"),
        _row("callhome_eng", "excluded"),
    ]
    decisions = [default_source_validation("eng") for _ in rows]
    summary = mod.summarize_dry_run(rows, decisions)
    assert summary.total_rows == 3
    assert summary.rows_by_source == {"callhome_eng": 2, "callhome_spa": 1}
    # Two non-excluded rows are structurally eligible (upper bound on clean).
    assert summary.structurally_eligible_rows == 2
    assert summary.n_blocked_from_all_conditions == 3


def test_condition_candidates_counted_only_from_monolingual_conditions():
    mod = _load_script()
    rows = [
        _row("callhome_eng", "clean", ["EnglishMono", "MonoCont"]),
        _row("callhome_spa", "clean", ["SpanishMono", "MonoCont"]),
        _row("callhome_eng", "needs_review"),
    ]
    decisions = [explicit_source_validation("eng"), explicit_source_validation("spa"),
                 default_source_validation("eng")]
    summary = mod.summarize_dry_run(rows, decisions)
    assert summary.potential_condition_candidates == {
        "EnglishMono": 1,
        "SpanishMono": 1,
        "MonoCont": 2,
    }
    # CsCont is never a counted candidate for CALLHOME.
    assert "CsCont" not in summary.potential_condition_candidates


def test_synthetic_cscont_candidate_is_rejected():
    mod = _load_script()
    row = _row("callhome_eng", "clean", ["EnglishMono"])
    # Mutate past the constructor guard to simulate a corrupted/hostile row.
    row.condition_candidates = ["CsCont"]
    with pytest.raises(ValueError):
        mod.summarize_dry_run([row], [explicit_source_validation("eng")])


def test_validation_method_and_reason_counts_are_integers():
    mod = _load_script()
    rows = [_row("callhome_eng", "needs_review"), _row("callhome_spa", "needs_review")]
    decisions = [default_source_validation("eng"), explicit_source_validation("spa")]
    summary = mod.summarize_dry_run(rows, decisions)
    for counts in (
        summary.validation_status_counts,
        summary.validation_method_counts,
        summary.validation_reason_counts,
    ):
        assert all(isinstance(v, int) for v in counts.values())
    assert summary.validation_status_counts == {"validated": 1, "not_validated": 1}


def test_to_dict_is_integers_and_dicts_of_integers_only():
    mod = _load_script()
    rows = [
        _row("callhome_eng", "clean", ["EnglishMono", "MonoCont"]),
        _row("callhome_spa", "needs_review"),
    ]
    decisions = [explicit_source_validation("eng"), default_source_validation("spa")]
    data = mod.summarize_dry_run(rows, decisions).to_dict()
    for value in data.values():
        if isinstance(value, dict):
            assert all(isinstance(k, str) for k in value)
            assert all(isinstance(v, int) for v in value.values())
        else:
            assert isinstance(value, int)


def test_output_contains_no_transcript_bearing_content():
    mod = _load_script()
    rows = [_row("callhome_eng", "needs_review"), _row("callhome_spa", "clean",
                                                        ["SpanishMono", "MonoCont"])]
    decisions = [default_source_validation("eng"), explicit_source_validation("spa")]
    serialized = json.dumps(mod.summarize_dry_run(rows, decisions).to_dict())
    for s in _FORBIDDEN_STRINGS:
        assert s not in serialized
    for banned in (
        "speaker_ref",
        "source_file_ref",
        "raw_text",
        "tokens",
        "conversation_id",
        "turn_index",
        "filename",
        "media",
    ):
        assert banned not in serialized


def test_real_summary_script_does_not_use_dry_run_or_lexicon_modules():
    source = _SUMMARY_SCRIPT_PATH.read_text(encoding="utf-8")
    assert "dry_run_callhome_lexicon_validation" not in source
    assert "callhome_lexicon_loader" not in source
    assert "callhome_lexicon_validation" not in source
    assert "summarize_dry_run" not in source


def _local_lexicons_snapshot(local):
    if not local.exists():
        return None
    return sorted(str(p.relative_to(local)) for p in local.rglob("*"))


def test_disabled_cli_writes_no_files(tmp_path, monkeypatch, capsys):
    mod = _load_script()
    local = project_root() / "data" / "resources" / "local_lexicons"
    before = _local_lexicons_snapshot(local)

    monkeypatch.chdir(tmp_path)
    mod.main([])  # refusal path: must process/write nothing
    capsys.readouterr()

    # Nothing created in the working directory (no JSONL, no output at all)...
    assert list(tmp_path.iterdir()) == []
    # ...and the ignored resource path is untouched.
    after = _local_lexicons_snapshot(local)
    assert before == after
    if before is None:
        assert not local.exists()
