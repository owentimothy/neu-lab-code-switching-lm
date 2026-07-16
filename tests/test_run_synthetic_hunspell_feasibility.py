"""Synthetic unit tests for the synthetic-only Hunspell feasibility runner.

These tests use temporary invented fixtures only. They do not start Docker,
download Hunspell, acquire RLA-ES, or access CALLHOME, Bangor, ignored resources,
private logs, or corpus paths.
"""

from __future__ import annotations

import importlib.util
import io
import sys
import tarfile
from pathlib import Path

import pytest

from cslm.utils.paths import project_root

_SCRIPT_PATH = project_root() / "scripts" / "run_synthetic_hunspell_feasibility.py"


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "run_synthetic_hunspell_feasibility", _SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


runner = _load_script()


def _valid_fixture(tmp_path: Path) -> Path:
    fixture = tmp_path / "fixture"
    runner._write_fixture(fixture)
    return fixture


def _replace(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace(old, new), encoding="utf-8", newline="\n")


def _safe_summary() -> dict[str, object]:
    return {
        "hunspell_release": runner.HUNSPELL_RELEASE,
        "hunspell_commit": runner.HUNSPELL_COMMIT,
        "container_platform": runner.CONTAINER_PLATFORM,
        "environment_identity_match": True,
        "offline_build": True,
        "synthetic_generation_runs": 2,
        "generated_entry_count": 13,
        "two_runs_byte_identical": True,
        "expected_set_match": True,
        "direct_hunspell_parity": True,
        "rejected_form_rejected": True,
        "scale_probe_base_count": 1024,
        "scale_probe_generated_entry_count": 2048,
        "scale_probe_two_runs_byte_identical": True,
        "scale_probe_expected_set_match": True,
        "scale_probe_direct_hunspell_parity": True,
        "missing_affix_failed_closed": True,
        "missing_dictionary_failed_closed": True,
        "malformed_affix_failed_closed": True,
        "malformed_dictionary_failed_closed": True,
        "unsupported_flag_mode_failed_closed": True,
        "unsupported_directive_failed_closed": True,
        "no_real_resource_or_corpus_access": True,
    }


def test_public_identities_are_fully_pinned():
    assert runner.HUNSPELL_RELEASE == "v1.7.3"
    assert runner.HUNSPELL_COMMIT == "c5f98152a274e25b5107101104bef632b83a0cc9"
    assert runner.CONTAINER_PLATFORM == "linux/arm64"
    assert runner.CONTAINER_REFERENCE.startswith("docker.io/library/buildpack-deps@sha256:")
    assert ":bookworm" not in runner.CONTAINER_REFERENCE
    assert len(runner.HUNSPELL_ARCHIVE_SHA256) == 64


def test_summary_schema_is_fixed_and_content_free():
    summary = _safe_summary()
    assert tuple(summary) == runner.SUMMARY_KEYS
    assert set(summary.values()).isdisjoint(set(runner._EXPECTED_FORMS))
    assert set(summary.values()).isdisjoint(set(runner._REJECTED_FORMS))


def test_fixture_is_valid_and_exactly_scoped(tmp_path):
    fixture = _valid_fixture(tmp_path)
    runner._validate_fixture_dir(fixture)
    assert {path.name for path in fixture.iterdir()} == runner._FIXTURE_FILENAMES


def test_fixture_exercises_required_rule_shapes(tmp_path):
    fixture = _valid_fixture(tmp_path)
    flags = runner._parse_affix(fixture / "synthetic.aff")
    words = runner._parse_dictionary(fixture / "synthetic.dic", allowed_flags=flags)
    assert flags == frozenset({"A", "B", "C", "D"})
    assert len(words) == 6
    assert len(runner._EXPECTED_FORMS) == 13
    assert len(runner._REJECTED_FORMS) == 1


def test_scale_fixture_is_bounded_invented_and_valid(tmp_path):
    fixture = tmp_path / "scale_fixture"
    runner._write_scale_fixture(fixture)
    runner._validate_fixture_dir(fixture)
    flags = runner._parse_affix(fixture / "synthetic.aff")
    words = runner._parse_dictionary(fixture / "synthetic.dic", allowed_flags=flags)
    expected = runner._validate_word_list(fixture / "expected.txt")
    assert len(words) == runner._SCALE_BASE_COUNT == 1024
    assert len(expected) == runner._SCALE_BASE_COUNT * 2
    assert all(runner._SAFE_WORD_RE.fullmatch(word) for word in words)


@pytest.mark.parametrize(
    ("index", "expected"),
    [(0, "aaa"), (25, "aaz"), (26, "aba"), (1023, "bnj")],
)
def test_alphabetic_id_is_deterministic(index, expected):
    assert runner._alphabetic_id(index) == expected


@pytest.mark.parametrize("value", [-1, 26**3, True, 1.5])
def test_alphabetic_id_rejects_out_of_range_or_non_integer(value):
    with pytest.raises(runner.SyntheticFeasibilityError):
        runner._alphabetic_id(value)


@pytest.mark.parametrize("filename", ["synthetic.aff", "synthetic.dic"])
def test_missing_dependency_fails_closed(tmp_path, filename):
    fixture = _valid_fixture(tmp_path)
    (fixture / filename).unlink()
    with pytest.raises(runner.SyntheticFeasibilityError):
        runner._validate_fixture_dir(fixture)


def test_unexpected_fixture_entry_fails_closed_without_naming_it(tmp_path):
    fixture = _valid_fixture(tmp_path)
    (fixture / "private-looking-name").write_text("invented\n", encoding="utf-8")
    with pytest.raises(runner.SyntheticFeasibilityError) as excinfo:
        runner._validate_fixture_dir(fixture)
    assert str(excinfo.value) == ""
    assert "private-looking-name" not in repr(excinfo.value)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("PFX A Y 1", "PFX A Y 2"),
        ("SFX B 0 in .", "SFX B 0"),
        ("SFX D 0 z [ae]", "SFX D 0 z [ae] extra"),
    ],
)
def test_malformed_affix_rules_fail_closed(tmp_path, old, new):
    fixture = _valid_fixture(tmp_path)
    _replace(fixture / "synthetic.aff", old, new)
    with pytest.raises(runner.SyntheticFeasibilityError):
        runner._validate_fixture_dir(fixture)


def test_unsupported_flag_mode_fails_closed(tmp_path):
    fixture = _valid_fixture(tmp_path)
    _replace(fixture / "synthetic.aff", "FLAG UTF-8", "FLAG long")
    with pytest.raises(runner.SyntheticFeasibilityError):
        runner._validate_fixture_dir(fixture)


def test_unsupported_directive_fails_closed(tmp_path):
    fixture = _valid_fixture(tmp_path)
    affix = fixture / "synthetic.aff"
    affix.write_text(
        affix.read_text(encoding="utf-8") + "COMPLEXPREFIXES\n",
        encoding="utf-8",
        newline="\n",
    )
    with pytest.raises(runner.SyntheticFeasibilityError):
        runner._validate_fixture_dir(fixture)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("6\n", "7\n"),
        ("synpavor/A", "synpavor/Z"),
        ("synpavor/A", "synpavor/AA"),
        ("synpavor/A", "syn.pavor/A"),
    ],
)
def test_malformed_dictionary_fails_closed(tmp_path, old, new):
    fixture = _valid_fixture(tmp_path)
    _replace(fixture / "synthetic.dic", old, new)
    with pytest.raises(runner.SyntheticFeasibilityError):
        runner._validate_fixture_dir(fixture)


def test_non_utf8_or_non_lf_input_fails_closed(tmp_path):
    fixture = _valid_fixture(tmp_path)
    (fixture / "synthetic.dic").write_bytes(b"1\r\nsyn\xff\r\n")
    with pytest.raises(runner.SyntheticFeasibilityError):
        runner._validate_fixture_dir(fixture)


def test_expected_and_candidate_sets_must_be_sorted_and_consistent(tmp_path):
    fixture = _valid_fixture(tmp_path)
    expected = fixture / "expected.txt"
    lines = expected.read_text(encoding="utf-8").splitlines()
    expected.write_text("\n".join(reversed(lines)) + "\n", encoding="utf-8")
    with pytest.raises(runner.SyntheticFeasibilityError):
        runner._validate_fixture_dir(fixture)


def test_docker_base_is_offline_read_only_and_platform_pinned():
    args = runner._base_docker_args()
    assert args[:3] == ["docker", "run", "--rm"]
    assert args[args.index("--network") + 1] == "none"
    assert args[args.index("--platform") + 1] == "linux/arm64"
    assert "--read-only" in args
    assert args[args.index("--cap-drop") + 1] == "ALL"
    assert args[args.index("--security-opt") + 1] == "no-new-privileges"
    assert any(value.startswith("/tmp:rw,") for value in args)


def test_generation_command_mounts_only_fixture_install_and_output(tmp_path, monkeypatch):
    fixture = tmp_path / "fixture"
    install = tmp_path / "install"
    output = tmp_path / "output"
    fixture.mkdir()
    install.mkdir()
    captured: list[str] = []

    def fake_run(command, *, timeout=300):
        captured.extend(command)
        return None

    monkeypatch.setattr(runner, "_run", fake_run)
    runner._run_generation(fixture, install, output)
    mounts = [captured[index + 1] for index, item in enumerate(captured) if item == "--mount"]
    assert len(mounts) == 3
    assert any("dst=/fixture,readonly" in mount for mount in mounts)
    assert any("dst=/opt/hunspell,readonly" in mount for mount in mounts)
    assert any("dst=/output" in mount and "readonly" not in mount for mount in mounts)
    assert "--network" in captured and "none" in captured


def test_tar_path_traversal_fails_closed(tmp_path):
    archive_path = tmp_path / "unsafe.tar.gz"
    with tarfile.open(archive_path, "w:gz") as archive:
        payload = b"invented\n"
        info = tarfile.TarInfo("../escape")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    with pytest.raises(runner.SyntheticFeasibilityError):
        runner._extract_source(archive_path, tmp_path / "destination")
    assert not (tmp_path / "escape").exists()


def test_cli_exposes_only_opt_in_and_help():
    parser = runner._build_parser()
    options: set[str] = set()
    for action in parser._actions:
        options.update(action.option_strings)
    assert options == {"-h", "--help", "--allow-synthetic-hunspell-run"}


def test_default_refuses_before_execution(monkeypatch, capsys):
    def boom():
        raise AssertionError("execution must not be reached")

    monkeypatch.setattr(runner, "_execute", boom)
    assert runner.main([]) == runner.EXIT_OPT_IN_REQUIRED
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == runner._OPT_IN_MESSAGE + "\n"


def test_opt_in_prints_only_fixed_summary(monkeypatch, capsys):
    summary = _safe_summary()
    monkeypatch.setattr(runner, "_execute", lambda: summary)
    assert runner.main(["--allow-synthetic-hunspell-run"]) == runner.EXIT_SUCCESS
    captured = capsys.readouterr()
    assert captured.err == ""
    assert list(__import__("json").loads(captured.out)) == list(runner.SUMMARY_KEYS)


def test_operational_failure_uses_fixed_non_sensitive_message(monkeypatch, capsys):
    def fail():
        raise RuntimeError("invented secret path and token")

    monkeypatch.setattr(runner, "_execute", fail)
    assert runner.main(["--allow-synthetic-hunspell-run"]) == runner.EXIT_OPERATIONAL_ABORT
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == runner._ABORT_MESSAGE + "\n"
    assert "secret" not in captured.err


@pytest.mark.parametrize("argument", ["--root", "--dictionary", "--output", "extra"])
def test_path_and_data_arguments_are_rejected(argument):
    with pytest.raises(SystemExit) as excinfo:
        runner.main([argument])
    assert excinfo.value.code == 2
