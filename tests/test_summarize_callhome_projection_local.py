"""Tests for the local-only CALLHOME projection + screening summary script.

All CALLHOME directories/files here are SYNTHETIC and created under a temporary
directory (fake ``AAA`` speaker codes, ``syn_*`` tokens, obviously-fake
filenames). No real CALLHOME files are used. The script's output must be
aggregate-only: no transcript tokens, speaker codes, filenames, de-identified
refs, or screening notes may appear.
"""

import importlib.util
import subprocess
import sys

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


def _cha(main_tiers, *, lang="eng"):
    """Build a synthetic .cha body from a list of main-tier strings."""
    lines = ["@UTF8", "@Begin", f"@Languages:\t{lang}", "@Participants:\tAAA Adult"]
    for text in main_tiers:
        lines.append(f"*AAA:\t{text}")
    lines.append("@End")
    return "\n".join(lines) + "\n"


def _load_script():
    spec = importlib.util.spec_from_file_location("summarize_callhome_local", _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    # Register before exec so the module's @dataclass can resolve its own
    # annotations (dataclasses look the class's module up in sys.modules).
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write(root, label, name, body):
    lang_dir = root / label
    lang_dir.mkdir(parents=True, exist_ok=True)
    (lang_dir / name).write_text(body, encoding="utf-8")


def _all_strings_in_lines(lines):
    return "\n".join(lines)


def test_lexical_rows_default_to_needs_review_unscreened(tmp_path):
    mod = _load_script()
    root = tmp_path / "callhome"
    _write(root, "eng", "synth_secretfile_eng_0.cha", _cha(["syn_alpha syn_beta .", "syn_gamma ."]))
    summaries = mod.summarize_local(root)
    proj, scr = summaries.projection, summaries.screening
    assert proj.n_rows == 2
    assert proj.rows_by_screening_outcome["needs_review"] == 2
    assert scr.decisions_by_outcome["needs_review"] == 2
    assert scr.decisions_by_reason_code["default_unscreened"] == 2
    # No language ID yet: nothing is clean, nothing admitted to a condition.
    assert scr.decisions_by_outcome["clean"] == 0
    assert proj.n_blocked_from_all_conditions == 2


def test_punctuation_only_rows_are_excluded_empty_or_nonlexical(tmp_path):
    mod = _load_script()
    root = tmp_path / "callhome"
    _write(root, "eng", "synth_secretfile_eng_1.cha", _cha([".", "xxx .", "syn_word ."]))
    scr = mod.summarize_local(root).screening
    # Two non-lexical rows excluded; one lexical row needs_review.
    assert scr.decisions_by_outcome["excluded"] == 2
    assert scr.decisions_by_reason_code["empty_or_nonlexical"] == 2
    assert scr.decisions_by_outcome["needs_review"] == 1


def test_parser_warning_row_is_needs_review_parser_warning():
    # The CHAT parser records continuation/orphan warnings at the TRANSCRIPT
    # level, so a file-parsed utterance never carries its own warning. Exercise
    # the utterance-warning screening path via the exact heuristic the script
    # uses, with a synthetic utterance-level warning attached.
    from cslm.data.callhome_chat import parse_chat_lines
    from cslm.data.callhome_screening_heuristics import build_screening_decisions_by_turn

    transcript = parse_chat_lines(
        ["@Begin", "@Languages:\teng", "*AAA:\tsyn_alpha .", "@End"],
        source_file="synth_warn.cha",
    )
    transcript.utterances[0].parser_warnings.append("synthetic warning")
    decisions = build_screening_decisions_by_turn(transcript, language_label="eng")
    assert decisions[0].outcome == "needs_review"
    assert "parser_warning" in decisions[0].reason_codes


def test_transcript_level_warning_counted_as_parser_warning(tmp_path):
    # An orphan dependent tier before any speaker records a TRANSCRIPT-level
    # warning; the folded heuristic must surface it as a parser_warning reason,
    # and no warning text may appear in the aggregate output.
    mod = _load_script()
    root = tmp_path / "callhome"
    body = "\n".join(
        [
            "@Begin",
            "@Languages:\teng",
            "%mor:\tsyn_orphan_tier",  # orphan dependent tier -> transcript warning
            "*AAA:\tsyn_alpha .",
            "@End",
        ]
    ) + "\n"
    _write(root, "eng", "synth_orphan.cha", body)
    summaries = mod.summarize_local(root)
    scr = summaries.screening
    assert scr.decisions_by_reason_code["parser_warning"] >= 1
    assert scr.decisions_by_outcome["needs_review"] >= 1
    # No warning text (e.g. "orphan", "syn_orphan_tier") leaks into the summary.
    text = _all_strings_in_lines(mod.format_summary_lines(summaries))
    for token in ("orphan", "syn_orphan_tier", "dependent tier"):
        assert token not in text, token


def test_collect_returns_rows_screening_and_validation_decisions(tmp_path):
    # A normal lexical file yields one row + one needs_review/default_unscreened
    # screening decision + one not_validated validation decision.
    mod = _load_script()
    root = tmp_path / "callhome"
    _write(root, "eng", "synth_ok.cha", _cha(["syn_alpha ."]))
    rows, decisions, validation_decisions = mod.collect_rows_and_decisions(root)
    assert len(rows) == 1
    assert len(decisions) == 1
    assert decisions[0].outcome == "needs_review"
    assert decisions[0].reason_codes == ["default_unscreened"]
    # One validation decision per row, and it is the default (not validated).
    assert len(validation_decisions) == 1
    assert validation_decisions[0].is_validated is False
    assert validation_decisions[0].validation_method == "not_validated"


def test_validation_summary_default_is_all_not_validated(tmp_path):
    mod = _load_script()
    root = tmp_path / "callhome"
    _write(root, "eng", "synth_secretfile_eng_0.cha", _cha(["syn_alpha .", "syn_beta ."]))
    _write(root, "spa", "synth_secretfile_spa_0.cha", _cha(["syn_gamma ."], lang="spa"))
    summaries = mod.summarize_local(root)
    val, proj = summaries.validation, summaries.projection
    # One validation decision per row; all not_validated, none validated.
    assert val.n_decisions == proj.n_rows == 3
    assert val.decisions_by_validated_status == {"validated": 0, "not_validated": 3}
    assert val.decisions_by_validation_method == {"explicit_override": 0, "not_validated": 3}
    assert val.decisions_by_reason_code == {
        "explicit_source_validation": 0,
        "not_validated": 3,
    }
    # Clean stays zero and no condition candidates appear.
    assert proj.rows_by_screening_outcome["clean"] == 0
    assert proj.rows_by_condition_candidate == {
        "EnglishMono": 0,
        "SpanishMono": 0,
        "MonoCont": 0,
    }


def test_validation_summary_section_printed_and_aggregate_only(tmp_path):
    mod = _load_script()
    root = tmp_path / "callhome"
    _write(root, "eng", "synth_secretfile_eng_0.cha", _cha(["syn_alpha syn_beta .", "."]))
    lines = mod.format_summary_lines(mod.summarize_local(root))
    text = _all_strings_in_lines(lines)
    assert "== validation summary ==" in text
    assert "decisions by validated status:" in text
    assert "decisions by validation method:" in text
    for token in _FORBIDDEN_TOKENS:
        assert token not in text, token
    for field_name in (
        "speaker_ref",
        "source_file_ref",
        "raw_text",
        "tokens",
        "notes",
        "expected_language",
    ):
        assert field_name not in text, field_name


def test_default_validation_keeps_clean_zero(tmp_path):
    # Wiring default source validation must NOT admit any row to clean, and no
    # condition candidates may appear, even for structurally clean lexical rows.
    mod = _load_script()
    root = tmp_path / "callhome"
    _write(root, "eng", "synth_secretfile_eng_0.cha", _cha(["syn_alpha syn_beta .", "syn_gamma ."]))
    _write(root, "spa", "synth_secretfile_spa_0.cha", _cha(["syn_delta ."], lang="spa"))
    summaries = mod.summarize_local(root)
    proj, scr = summaries.projection, summaries.screening
    # No clean rows via projection or screening.
    assert proj.rows_by_screening_outcome["clean"] == 0
    assert scr.decisions_by_outcome["clean"] == 0
    # No condition candidates at all under the default.
    assert proj.rows_by_condition_candidate == {
        "EnglishMono": 0,
        "SpanishMono": 0,
        "MonoCont": 0,
    }
    assert proj.n_blocked_from_all_conditions == proj.n_rows


def test_default_validation_preserves_structural_outcomes(tmp_path):
    # Combining with not_validated leaves structural outcomes unchanged:
    # lexical -> needs_review, punctuation/residue -> excluded.
    mod = _load_script()
    root = tmp_path / "callhome"
    _write(root, "eng", "synth_mix.cha", _cha(["syn_alpha .", ".", "xxx ."]))
    proj = mod.summarize_local(root).projection
    assert proj.rows_by_screening_outcome["needs_review"] == 1
    assert proj.rows_by_screening_outcome["excluded"] == 2
    assert proj.rows_by_screening_outcome["clean"] == 0


def test_local_script_does_not_use_explicit_source_validation():
    # The real-data script must never CALL or import the explicit (positive)
    # validation. (A mention in a comment explaining that it is not used is fine,
    # so we check for a call/import form rather than any occurrence.)
    source = _SCRIPT_PATH.read_text(encoding="utf-8")
    assert "explicit_source_validation(" not in source  # no call
    assert "import explicit_source_validation" not in source
    # And confirm the default path is present and imported.
    mod = _load_script()
    assert hasattr(mod, "default_source_validation")
    assert hasattr(mod, "combine_screening_and_validation")


def test_missing_root_reports_zero_counts(tmp_path):
    mod = _load_script()
    summaries = mod.summarize_local(tmp_path / "does_not_exist")
    assert summaries.projection.n_rows == 0
    assert summaries.projection.rows_by_source == {"callhome_eng": 0, "callhome_spa": 0}
    assert summaries.screening.n_decisions == 0
    # Stable zero keys on both summaries.
    assert summaries.screening.decisions_by_outcome["clean"] == 0
    assert summaries.screening.decisions_by_reason_code["default_unscreened"] == 0


def test_missing_one_language_dir_still_summarizes(tmp_path):
    mod = _load_script()
    root = tmp_path / "callhome"
    _write(root, "eng", "synth_secretfile_eng_0.cha", _cha(["syn_alpha ."]))
    # No spa/ directory at all.
    proj = mod.summarize_local(root).projection
    assert proj.rows_by_source == {"callhome_eng": 1, "callhome_spa": 0}


def test_format_summary_lines_are_aggregate_only(tmp_path):
    mod = _load_script()
    root = tmp_path / "callhome"
    _write(root, "eng", "synth_secretfile_eng_0.cha", _cha(["syn_alpha syn_beta .", "."]))
    _write(root, "spa", "synth_secretfile_spa_0.cha", _cha(["syn_gamma ."], lang="spa"))
    lines = mod.format_summary_lines(mod.summarize_local(root))
    text = _all_strings_in_lines(lines)
    for token in _FORBIDDEN_TOKENS:
        assert token not in text, token
    for field_name in ("speaker_ref", "source_file_ref", "raw_text", "tokens", "notes"):
        assert field_name not in text, field_name
    # Both summary sections are present.
    assert "== projection summary ==" in text
    assert "== screening summary ==" in text


def test_cli_stdout_is_aggregate_only(tmp_path):
    root = tmp_path / "callhome"
    _write(root, "eng", "synth_secretfile_eng_0.cha", _cha(["syn_alpha .", "xxx ."]))
    _write(root, "spa", "synth_secretfile_spa_0.cha", _cha(["syn_gamma ."], lang="spa"))
    result = subprocess.run(
        [sys.executable, str(_SCRIPT_PATH), "--root", str(root)],
        capture_output=True,
        text=True,
        cwd=str(project_root()),
        check=True,
    )
    out = result.stdout
    assert "projection summary" in out
    assert "screening summary" in out
    assert "callhome_eng" in out  # source label is safe aggregate provenance
    for token in _FORBIDDEN_TOKENS:
        assert token not in out, token
    for field_name in ("speaker_ref", "source_file_ref", "raw_text", "notes"):
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
    root = tmp_path / "callhome"
    _write(root, "eng", "synth_secretfile_eng_0.cha", _cha(["syn_alpha ."]))
    before = {p for p in root.rglob("*")}
    mod.summarize_local(root)
    after = {p for p in root.rglob("*")}
    assert before == after  # summarizing created nothing


def test_unparseable_file_is_skipped_not_raised(tmp_path):
    mod = _load_script()
    root = tmp_path / "callhome"
    _write(root, "eng", "good.cha", _cha(["syn_alpha ."]))
    (root / "eng" / "bad.cha").write_bytes(b"\xff\xfe not valid utf-8 \x80\x81")
    proj = mod.summarize_local(root).projection
    # Only the good file contributes (1 row); the bad file is skipped.
    assert proj.rows_by_source["callhome_eng"] == 1
