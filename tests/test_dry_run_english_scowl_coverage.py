"""Synthetic tests for the aggregate-only CALLHOME English SCOWL coverage dry run.

Everything here is SYNTHETIC. English utterances are built as temporary ``.cha``
fixtures with obviously-fake ``syn_*`` tokens and ``ZZZSECRET*`` speaker codes; the
approved SCOWL resource is a synthetic temporary bundle loaded through the **real**
loader boundary (``english_scowl_resource._approved_bundle_dir`` monkeypatched,
exactly as in ``tests/test_english_scowl_coverage.py``). No test reads the real
ignored SCOWL bundle, real CALLHOME, Bangor, ignored resources, the network, or
any private log.

Injection is done through internal seams (``_run_coverage_dry_run``,
``_resolve_canonical_english_dir``, ``_load_evaluator``); none of these are
reachable from the production CLI, which resolves the one canonical English
population itself and exposes only ``--allow-real-coverage-run``.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from cslm.data import english_scowl_resource as resource
from cslm.data.callhome_chat import parse_chat_file
from cslm.data.english_scowl_coverage import EnglishScowlCoverageEvaluator
from cslm.data.english_scowl_resource import (
    ARTIFACT_FILENAME,
    NOTICE_FILENAME,
    PROVENANCE_FILENAME,
    RESOURCE_ID,
    load_approved_english_scowl,
)
from cslm.utils.paths import project_root

# --------------------------------------------------------------------------- #
# Load the script (in scripts/, not an importable package) once, by path.
# --------------------------------------------------------------------------- #

_SCRIPT_PATH = project_root() / "scripts" / "dry_run_english_scowl_coverage.py"


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "dry_run_english_scowl_coverage", _SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # register before exec so annotations resolve
    spec.loader.exec_module(module)
    return module


dry_run = _load_script()

# Synthetic SCOWL lexicon (strictly bytewise-sorted; the loader requires it).
_SYN_ENTRIES: tuple[str, ...] = ("syn_apple", "syn_banana", "syn_cherry")
_SYN_NOTICE = "synthetic notice text; never read\n"

# Transcript-shaped synthetic secrets that must never surface in any output.
_SECRET_TOKEN = "syn_secrettoken"
_SECRET_SPEAKER = "ZZZSECRETSPK"
_SECRET_FILENAME = "secretfile_00.cha"


# --------------------------------------------------------------------------- #
# Synthetic approved-bundle fixture (mirrors tests/test_english_scowl_coverage.py).
# --------------------------------------------------------------------------- #


def _artifact_bytes(entries) -> bytes:
    return "".join(f"{entry}\n" for entry in entries).encode("utf-8")


def _provenance_document(artifact_data: bytes) -> dict:
    return {
        "schema_version": 1,
        "resource_id": RESOURCE_ID,
        "artifact_filename": ARTIFACT_FILENAME,
        "preserved_notice_filename": NOTICE_FILENAME,
        "artifact_SHA256": hashlib.sha256(artifact_data).hexdigest(),
    }


def _build_bundle(root: Path, *, entries=_SYN_ENTRIES) -> Path:
    bundle = root / "syn_bundle"
    bundle.mkdir()
    data = _artifact_bytes(entries)
    (bundle / ARTIFACT_FILENAME).write_bytes(data)
    (bundle / NOTICE_FILENAME).write_text(_SYN_NOTICE, encoding="utf-8")
    (bundle / PROVENANCE_FILENAME).write_text(
        json.dumps(_provenance_document(data), sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return bundle


def _make_evaluator(root: Path, monkeypatch) -> EnglishScowlCoverageEvaluator:
    """A genuine evaluator built from a synthetic bundle via the real loader."""
    bundle = _build_bundle(root)
    monkeypatch.setattr(resource, "_approved_bundle_dir", lambda: bundle)
    return EnglishScowlCoverageEvaluator(load_approved_english_scowl())


# --------------------------------------------------------------------------- #
# Synthetic CHAT fixtures.
# --------------------------------------------------------------------------- #


def _big_lines(
    n_all: int,
    n_unc: int,
    n_empty: int,
    *,
    speaker: str = "AAA",
    covered: str = "syn_apple",
    uncovered: str = _SECRET_TOKEN,
) -> list[str]:
    """CHAT lines yielding n_all all_covered, n_unc has_uncovered, n_empty empty."""
    lines = ["@Begin", "@Languages:\teng"]
    for _ in range(n_all):
        lines.append(f"*{speaker}:\t{covered} .")
    for _ in range(n_unc):
        lines.append(f"*{speaker}:\t{uncovered} .")
    for _ in range(n_empty):
        lines.append(f"*{speaker}:\t. ?")
    lines.append("@End")
    return lines


def _write_cha(directory: Path, name: str, lines: list[str]) -> Path:
    path = directory / name
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _populate_eng(
    eng_dir: Path,
    *,
    per_file: tuple[int, int, int] = (4, 4, 4),
    names: tuple[str, ...] = ("a.cha", "b.cha", "c.cha"),
) -> None:
    eng_dir.mkdir(parents=True, exist_ok=True)
    for name in names:
        _write_cha(eng_dir, name, _big_lines(*per_file))


def _spy(record: list[Path]):
    def parse(path):
        record.append(Path(path))
        return parse_chat_file(path)

    return parse


def _bundle(all_covered, has_uncovered, no_lex, covered, uncovered) -> dict:
    """A flattened seven-count bundle that always satisfies the count identities."""
    return {
        "n_results": all_covered + has_uncovered + no_lex,
        "outcome__all_covered": all_covered,
        "outcome__has_uncovered": has_uncovered,
        "outcome__no_lexical_tokens": no_lex,
        "n_tokens_total": covered + uncovered,
        "n_covered_total": covered,
        "n_uncovered_total": uncovered,
    }


# --------------------------------------------------------------------------- #
# Contract constants.
# --------------------------------------------------------------------------- #


def test_exit_code_constants():
    assert dry_run.EXIT_SUCCESS == 0
    assert dry_run.EXIT_OPT_IN_REQUIRED == 2
    assert dry_run.EXIT_OPERATIONAL_ABORT == 3
    assert dry_run.EXIT_PRIVACY_SUPPRESSED == 4


def test_privacy_threshold_is_ten():
    assert dry_run.PRIVACY_MIN_COUNT == 10


def test_expected_keys_are_the_seven_scalars():
    assert dry_run.EXPECTED_KEYS == (
        "n_results",
        "outcome__all_covered",
        "outcome__has_uncovered",
        "outcome__no_lexical_tokens",
        "n_tokens_total",
        "n_covered_total",
        "n_uncovered_total",
    )


def test_messages_are_fixed_distinct_and_digit_free():
    msgs = [
        dry_run._OPT_IN_REQUIRED_MESSAGE,
        dry_run._OPERATIONAL_ABORT_MESSAGE,
        dry_run._PRIVACY_SUPPRESSED_MESSAGE,
    ]
    assert len(set(msgs)) == 3
    for m in msgs:
        assert "{" not in m and "}" not in m and "%" not in m  # no interpolation
        assert not any(ch.isdigit() for ch in m)  # no counts / thresholds leak


# --------------------------------------------------------------------------- #
# CLI shape and default refusal.
# --------------------------------------------------------------------------- #


def test_cli_exposes_only_opt_in_plus_help():
    parser = dry_run._build_arg_parser()
    option_strings: set[str] = set()
    for action in parser._actions:
        option_strings.update(action.option_strings)
    assert option_strings == {"-h", "--help", "--allow-real-coverage-run"}


@pytest.mark.parametrize(
    "argv",
    [["--root", "x"], ["--output", "y"], ["--limit", "5"], ["--allow"], ["extra"]],
)
def test_unknown_or_forbidden_args_are_usage_failures(argv):
    with pytest.raises(SystemExit) as excinfo:
        dry_run.main(argv)
    assert excinfo.value.code == 2  # argparse usage failure


def test_default_invocation_refuses_before_resolution_or_loading(monkeypatch, capsys):
    def boom(*args, **kwargs):
        raise AssertionError("must not be reached before opt-in")

    monkeypatch.setattr(dry_run, "_resolve_canonical_english_dir", boom)
    monkeypatch.setattr(dry_run, "_list_english_cha_files", boom)
    monkeypatch.setattr(dry_run, "_load_evaluator", boom)
    monkeypatch.setattr(dry_run, "load_approved_english_scowl", boom)

    rc = dry_run.main([])
    captured = capsys.readouterr()
    assert rc == dry_run.EXIT_OPT_IN_REQUIRED
    assert captured.out == ""
    assert captured.err.strip() == dry_run._OPT_IN_REQUIRED_MESSAGE


# --------------------------------------------------------------------------- #
# Canonical population resolution and traversal.
# --------------------------------------------------------------------------- #


def test_canonical_path_is_fixed_and_repo_relative():
    assert dry_run._resolve_canonical_english_dir() == (
        project_root() / "data" / "raw" / "callhome" / "eng"
    )


def test_direct_files_processed_in_sorted_order(tmp_path, monkeypatch):
    eng = tmp_path / "eng"
    _populate_eng(eng, per_file=(4, 4, 4), names=("c.cha", "a.cha", "b.cha"))
    evaluator = _make_evaluator(tmp_path, monkeypatch)
    record: list[Path] = []
    dry_run._run_coverage_dry_run(eng, evaluator, parse_file=_spy(record))
    assert record == [eng / "a.cha", eng / "b.cha", eng / "c.cha"]


def test_nested_files_are_not_processed(tmp_path, monkeypatch):
    eng = tmp_path / "eng"
    _populate_eng(eng, per_file=(4, 4, 4))  # 3 direct files -> counts pass the guard
    nested = eng / "sub"
    nested.mkdir()
    _write_cha(nested, "deep.cha", _big_lines(4, 4, 4))
    evaluator = _make_evaluator(tmp_path, monkeypatch)
    record: list[Path] = []
    dry_run._run_coverage_dry_run(eng, evaluator, parse_file=_spy(record))
    assert (nested / "deep.cha") not in record
    assert all(p.parent == eng for p in record)


def test_spanish_and_bangor_are_never_opened(tmp_path, monkeypatch):
    eng = tmp_path / "eng"
    _populate_eng(eng, per_file=(4, 4, 4))
    for sibling in ("spa", "bangor"):
        sib = tmp_path / sibling
        sib.mkdir()
        _write_cha(sib, "other.cha", _big_lines(4, 4, 4))
    evaluator = _make_evaluator(tmp_path, monkeypatch)
    record: list[Path] = []
    dry_run._run_coverage_dry_run(eng, evaluator, parse_file=_spy(record))
    assert all(p.parent == eng for p in record)
    assert (tmp_path / "spa" / "other.cha") not in record
    assert (tmp_path / "bangor" / "other.cha") not in record


def _parser_must_not_run(_path):
    raise AssertionError("parser must not run for an invalid population boundary")


def test_symlinked_english_directory_is_rejected_before_parsing(tmp_path, monkeypatch):
    target = tmp_path / "outside_secret_directory"
    _populate_eng(target, names=("secret_target.cha",))
    eng = tmp_path / "eng"
    eng.symlink_to(target, target_is_directory=True)
    evaluator = _make_evaluator(tmp_path, monkeypatch)

    with pytest.raises(dry_run._OperationalError):
        dry_run._run_coverage_dry_run(
            eng, evaluator, parse_file=_parser_must_not_run
        )


def test_direct_cha_symlink_is_rejected_before_parsing(tmp_path, monkeypatch):
    eng = tmp_path / "eng"
    eng.mkdir()
    target = _write_cha(
        tmp_path, "outside_secret.cha", _big_lines(12, 12, 12)
    )
    (eng / "redirect_secret.cha").symlink_to(target)
    evaluator = _make_evaluator(tmp_path, monkeypatch)

    with pytest.raises(dry_run._OperationalError):
        dry_run._run_coverage_dry_run(
            eng, evaluator, parse_file=_parser_must_not_run
        )


def test_broken_direct_cha_symlink_is_rejected_before_parsing(tmp_path, monkeypatch):
    eng = tmp_path / "eng"
    eng.mkdir()
    (eng / "broken_secret.cha").symlink_to(tmp_path / "missing_secret.cha")
    evaluator = _make_evaluator(tmp_path, monkeypatch)

    with pytest.raises(dry_run._OperationalError):
        dry_run._run_coverage_dry_run(
            eng, evaluator, parse_file=_parser_must_not_run
        )


def test_directory_named_cha_is_rejected_before_parsing(tmp_path, monkeypatch):
    eng = tmp_path / "eng"
    eng.mkdir()
    (eng / "directory_secret.cha").mkdir()
    evaluator = _make_evaluator(tmp_path, monkeypatch)

    with pytest.raises(dry_run._OperationalError):
        dry_run._run_coverage_dry_run(
            eng, evaluator, parse_file=_parser_must_not_run
        )


def test_symlinked_population_aborts_before_loading_without_leak(
    tmp_path, monkeypatch, capsys
):
    target = tmp_path / "outside_secret_directory"
    _populate_eng(target, names=("secret_target.cha",))
    eng = tmp_path / "eng"
    eng.symlink_to(target, target_is_directory=True)

    def loader_must_not_run():
        raise AssertionError("loader must not run for an invalid population boundary")

    monkeypatch.setattr(dry_run, "_resolve_canonical_english_dir", lambda: eng)
    monkeypatch.setattr(dry_run, "_load_evaluator", loader_must_not_run)

    rc = dry_run.main(["--allow-real-coverage-run"])
    captured = capsys.readouterr()
    assert rc == dry_run.EXIT_OPERATIONAL_ABORT
    assert captured.out == ""
    assert captured.err.strip() == dry_run._OPERATIONAL_ABORT_MESSAGE
    for secret in ("outside_secret_directory", "secret_target.cha"):
        assert secret not in captured.err


# --------------------------------------------------------------------------- #
# Outcomes counted; no_lexical_tokens retained.
# --------------------------------------------------------------------------- #


def test_all_three_outcomes_counted_and_no_lexical_retained(tmp_path, monkeypatch):
    eng = tmp_path / "eng"
    _populate_eng(eng, per_file=(12, 12, 12), names=("only.cha",))
    evaluator = _make_evaluator(tmp_path, monkeypatch)
    result = dry_run._run_coverage_dry_run(eng, evaluator)
    assert result["outcome__all_covered"] == 12
    assert result["outcome__has_uncovered"] == 12
    assert result["outcome__no_lexical_tokens"] == 12  # retained, not dropped
    assert result["n_results"] == 36


# --------------------------------------------------------------------------- #
# Operational (fail-closed) failures — exit 3, no aggregate.
# --------------------------------------------------------------------------- #


def test_empty_directory_fails_operationally(tmp_path, monkeypatch):
    eng = tmp_path / "eng"
    eng.mkdir()
    evaluator = _make_evaluator(tmp_path, monkeypatch)
    with pytest.raises(dry_run._OperationalError):
        dry_run._run_coverage_dry_run(eng, evaluator)


def test_missing_directory_fails_operationally(tmp_path, monkeypatch):
    evaluator = _make_evaluator(tmp_path, monkeypatch)
    with pytest.raises(dry_run._OperationalError):
        dry_run._run_coverage_dry_run(tmp_path / "does_not_exist", evaluator)


def test_empty_directory_main_validates_population_before_loading(
    tmp_path, monkeypatch, capsys
):
    eng = tmp_path / "eng"
    eng.mkdir()

    def loader_boom():
        raise AssertionError("resource must not load before population is validated")

    monkeypatch.setattr(dry_run, "_resolve_canonical_english_dir", lambda: eng)
    monkeypatch.setattr(dry_run, "_load_evaluator", loader_boom)

    rc = dry_run.main(["--allow-real-coverage-run"])
    captured = capsys.readouterr()
    assert rc == dry_run.EXIT_OPERATIONAL_ABORT
    assert captured.out == ""
    assert captured.err.strip() == dry_run._OPERATIONAL_ABORT_MESSAGE


def test_zero_utterances_fails_operationally(tmp_path, monkeypatch):
    eng = tmp_path / "eng"
    eng.mkdir()
    _write_cha(eng, "a.cha", ["@Begin", "@Languages:\teng", "@End"])  # no * tiers
    evaluator = _make_evaluator(tmp_path, monkeypatch)
    with pytest.raises(dry_run._OperationalError):
        dry_run._run_coverage_dry_run(eng, evaluator)


def test_zero_lexical_tokens_fails_operationally(tmp_path, monkeypatch):
    eng = tmp_path / "eng"
    eng.mkdir()
    _write_cha(
        eng, "a.cha", ["@Begin", "@Languages:\teng", "*AAA:\t. ?", "*BBB:\t...", "@End"]
    )
    evaluator = _make_evaluator(tmp_path, monkeypatch)
    with pytest.raises(dry_run._OperationalError):
        dry_run._run_coverage_dry_run(eng, evaluator)


def test_one_parse_failure_aborts_the_whole_run(tmp_path, monkeypatch):
    eng = tmp_path / "eng"
    _populate_eng(eng, per_file=(4, 4, 4))
    evaluator = _make_evaluator(tmp_path, monkeypatch)
    state = {"n": 0}

    def flaky(path):
        state["n"] += 1
        if state["n"] == 2:
            raise RuntimeError("secret-parse-detail-must-not-surface")
        return parse_chat_file(path)

    with pytest.raises(RuntimeError):
        dry_run._run_coverage_dry_run(eng, evaluator, parse_file=flaky)


def test_evaluator_failure_aborts_the_whole_run(tmp_path, monkeypatch):
    eng = tmp_path / "eng"
    _populate_eng(eng, per_file=(4, 4, 4))

    class _BoomEvaluator:
        def evaluate_utterance(self, utterance):
            raise RuntimeError("secret-eval-detail-must-not-surface")

    with pytest.raises(RuntimeError):
        dry_run._run_coverage_dry_run(eng, _BoomEvaluator())


def test_loader_failure_maps_to_operational_exit_without_leak(
    tmp_path, monkeypatch, capsys
):
    eng = tmp_path / "eng"
    _populate_eng(eng, per_file=(4, 4, 4))

    def loader_boom():
        raise RuntimeError("secret-loader-path-detail")

    monkeypatch.setattr(dry_run, "_resolve_canonical_english_dir", lambda: eng)
    monkeypatch.setattr(dry_run, "_load_evaluator", loader_boom)

    rc = dry_run.main(["--allow-real-coverage-run"])
    captured = capsys.readouterr()
    assert rc == dry_run.EXIT_OPERATIONAL_ABORT
    assert captured.out == ""
    assert captured.err.strip() == dry_run._OPERATIONAL_ABORT_MESSAGE
    assert "secret-loader-path-detail" not in captured.err


def test_generic_exception_maps_to_operational_exit(monkeypatch, capsys):
    def boom():
        raise ValueError("secret-generic-detail")

    monkeypatch.setattr(dry_run, "_production_run", boom)
    rc = dry_run.main(["--allow-real-coverage-run"])
    captured = capsys.readouterr()
    assert rc == dry_run.EXIT_OPERATIONAL_ABORT
    assert captured.out == ""
    assert captured.err.strip() == dry_run._OPERATIONAL_ABORT_MESSAGE
    assert "secret-generic-detail" not in captured.err


def test_internal_control_errors_carry_no_payload():
    assert str(dry_run._OperationalError()) == ""
    assert str(dry_run._PrivacyGuardError()) == ""


# --------------------------------------------------------------------------- #
# Privacy guard: structure, types, invariants (exit 3), and k=10 (exit 4).
# --------------------------------------------------------------------------- #


def test_guard_accepts_full_release():
    dry_run._apply_privacy_guard(_bundle(10, 10, 10, 10, 10))  # no raise


def test_guard_allows_zero_cells():
    # Zeros are permitted; every *positive* count is >= 10 here.
    dry_run._apply_privacy_guard(_bundle(10, 0, 0, 10, 0))  # no raise


def test_guard_rejects_extra_key():
    bad = _bundle(10, 10, 10, 10, 10)
    bad["unexpected_extra"] = 10
    with pytest.raises(dry_run._OperationalError):
        dry_run._apply_privacy_guard(bad)


def test_guard_rejects_missing_key():
    bad = _bundle(10, 10, 10, 10, 10)
    del bad["n_results"]
    with pytest.raises(dry_run._OperationalError):
        dry_run._apply_privacy_guard(bad)


@pytest.mark.parametrize("value", [True, False, 2.0, "10", None])
def test_guard_rejects_non_int_values(value):
    bad = _bundle(10, 10, 10, 10, 10)
    bad["n_covered_total"] = value
    with pytest.raises(dry_run._OperationalError):
        dry_run._apply_privacy_guard(bad)


def test_guard_rejects_negative_count():
    bad = _bundle(10, 10, 10, 10, 10)
    bad["n_uncovered_total"] = -1
    with pytest.raises(dry_run._OperationalError):
        dry_run._apply_privacy_guard(bad)


def test_guard_rejects_inconsistent_outcome_sum():
    bad = _bundle(10, 10, 10, 10, 10)
    bad["n_results"] = 999
    with pytest.raises(dry_run._OperationalError):
        dry_run._apply_privacy_guard(bad)


def test_guard_rejects_inconsistent_token_complement():
    bad = _bundle(10, 10, 10, 10, 10)
    bad["n_tokens_total"] = 999
    with pytest.raises(dry_run._OperationalError):
        dry_run._apply_privacy_guard(bad)


@pytest.mark.parametrize("field_index", [0, 1, 2, 3, 4])
@pytest.mark.parametrize("value", list(range(1, 10)))
def test_positive_scalar_below_ten_suppresses_whole_bundle(field_index, value):
    knobs = [10, 10, 10, 10, 10]
    knobs[field_index] = value
    with pytest.raises(dry_run._PrivacyGuardError):
        dry_run._apply_privacy_guard(_bundle(*knobs))


def test_guard_boundary_nine_suppresses_ten_passes():
    with pytest.raises(dry_run._PrivacyGuardError):
        dry_run._apply_privacy_guard(_bundle(9, 10, 10, 10, 10))
    dry_run._apply_privacy_guard(_bundle(10, 10, 10, 10, 10))  # no raise


# --------------------------------------------------------------------------- #
# End-to-end suppression and success through main().
# --------------------------------------------------------------------------- #


def test_suppression_main_withholds_everything(tmp_path, monkeypatch, capsys):
    eng = tmp_path / "eng"
    _populate_eng(eng, per_file=(3, 3, 3), names=("only.cha",))  # counts < 10
    evaluator = _make_evaluator(tmp_path, monkeypatch)
    monkeypatch.setattr(dry_run, "_resolve_canonical_english_dir", lambda: eng)
    monkeypatch.setattr(dry_run, "_load_evaluator", lambda: evaluator)

    rc = dry_run.main(["--allow-real-coverage-run"])
    captured = capsys.readouterr()
    assert rc == dry_run.EXIT_PRIVACY_SUPPRESSED
    assert captured.out == ""  # no numeric bundle, no complementary totals
    assert captured.err.strip() == dry_run._PRIVACY_SUPPRESSED_MESSAGE
    # Does not identify the triggering field, and prints no numbers at all.
    for key in dry_run.EXPECTED_KEYS:
        assert key not in captured.err
    assert not any(ch.isdigit() for ch in captured.err)


def test_success_prints_exactly_one_seven_key_json_object(tmp_path, monkeypatch, capsys):
    eng = tmp_path / "eng"
    _populate_eng(eng, per_file=(12, 12, 12), names=("only.cha",))
    evaluator = _make_evaluator(tmp_path, monkeypatch)
    monkeypatch.setattr(dry_run, "_resolve_canonical_english_dir", lambda: eng)
    monkeypatch.setattr(dry_run, "_load_evaluator", lambda: evaluator)

    rc = dry_run.main(["--allow-real-coverage-run"])
    captured = capsys.readouterr()
    assert rc == dry_run.EXIT_SUCCESS
    assert captured.err == ""  # nothing on stderr on success
    assert captured.out.endswith("\n")
    assert captured.out.count("\n") == 1  # exactly one line

    payload = json.loads(captured.out)
    assert list(payload.keys()) == list(dry_run.EXPECTED_KEYS)  # deterministic order
    assert payload == {
        "n_results": 36,
        "outcome__all_covered": 12,
        "outcome__has_uncovered": 12,
        "outcome__no_lexical_tokens": 12,
        "n_tokens_total": 24,
        "n_covered_total": 12,
        "n_uncovered_total": 12,
    }
    assert all(isinstance(v, int) and not isinstance(v, bool) for v in payload.values())


# --------------------------------------------------------------------------- #
# No corpus-derived leakage; no verdict / routing fields; no forbidden imports.
# --------------------------------------------------------------------------- #


def test_no_transcript_shaped_secret_leaks_on_success(tmp_path, monkeypatch, capsys):
    eng = tmp_path / "eng"
    eng.mkdir()
    _write_cha(
        eng,
        _SECRET_FILENAME,
        _big_lines(12, 12, 12, speaker=_SECRET_SPEAKER, uncovered=_SECRET_TOKEN),
    )
    evaluator = _make_evaluator(tmp_path, monkeypatch)
    monkeypatch.setattr(dry_run, "_resolve_canonical_english_dir", lambda: eng)
    monkeypatch.setattr(dry_run, "_load_evaluator", lambda: evaluator)

    rc = dry_run.main(["--allow-real-coverage-run"])
    captured = capsys.readouterr()
    assert rc == dry_run.EXIT_SUCCESS
    blob = captured.out + captured.err
    for secret in (_SECRET_TOKEN, _SECRET_SPEAKER, "secretfile", "syn_apple"):
        assert secret not in blob


def test_returned_aggregate_holds_only_the_seven_int_counts(tmp_path, monkeypatch):
    eng = tmp_path / "eng"
    _populate_eng(eng, per_file=(12, 12, 12), names=("only.cha",))
    evaluator = _make_evaluator(tmp_path, monkeypatch)
    result = dry_run._run_coverage_dry_run(eng, evaluator)
    assert set(result) == set(dry_run.EXPECTED_KEYS)
    assert all(isinstance(v, int) and not isinstance(v, bool) for v in result.values())


def test_no_validation_clean_condition_or_routing_field():
    banned_substrings = (
        "validated",
        "clean",
        "condition",
        "routing",
        "candidate",
        "tokenizer",
        "model",
    )
    for key in dry_run.EXPECTED_KEYS:
        assert not any(sub in key for sub in banned_substrings)


def test_script_imports_only_allowed_modules():
    import_lines = [
        line
        for line in _SCRIPT_PATH.read_text(encoding="utf-8").splitlines()
        if line.startswith("from ") or line.startswith("import ")
    ]
    joined = "\n".join(import_lines)
    for banned in (
        "callhome_source_validation",
        "callhome_project",  # also covers callhome_projection_diagnostics
        "callhome_screening",
        "cslm.data.conditions",
        "condition_manifest",
        "cslm.data.schema",
    ):
        assert banned not in joined
    # Positively confirm the reused, allowed interfaces.
    assert "from cslm.data.english_scowl_coverage import EnglishScowlCoverageEvaluator" in joined
    assert "from cslm.data.english_scowl_coverage_diagnostics import" in joined
    assert "from cslm.data.english_scowl_resource import load_approved_english_scowl" in joined
    assert "from cslm.data.callhome_chat import" in joined
