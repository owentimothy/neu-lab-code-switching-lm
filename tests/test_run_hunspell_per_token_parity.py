"""Offline tests for the per-token parity Phase A observation infrastructure.

Two tiers run in ordinary CI:

* Tier 1 -- pure functions, fixtures, and CLI, using invented data only;
* Tier 2 -- a local synthetic *stub executable* exercising the real subprocess
  supervisor (writer/drain workers, output preservation on normal exit, byte
  ceilings, timeout, SIGTERM->SIGKILL, cancellation, thread-start failure, and the
  clean/abnormal cleanup callback).

No test starts Docker, uses the network, runs pinned Hunspell, or accesses RLA-ES,
CALLHOME, Bangor, ignored resources, or private logs.  The stub is an invented
local process; no ``-a``/``-l`` framing is assumed anywhere.  Docker is always
stubbed; no Docker command actually runs.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import time
import types
from pathlib import Path

import pytest

from cslm.utils.paths import project_root

_SCRIPT_PATH = project_root() / "scripts" / "run_hunspell_per_token_parity.py"


def _load_script():
    spec = importlib.util.spec_from_file_location(
        "run_hunspell_per_token_parity", _SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


runner = _load_script()


# Invented local stub executable.  It mimics generic process behaviours only.
_STUB = """\
import signal
import sys
import time

mode = sys.argv[1]
if mode == "echo":
    data = sys.stdin.buffer.read()
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()
elif mode == "exit7":
    sys.exit(7)
elif mode == "read_some_exit0":
    sys.stdin.buffer.read(10)
    sys.exit(0)
elif mode == "flood_out":
    sys.stdout.buffer.write(b"x" * int(sys.argv[2]))
    sys.stdout.buffer.flush()
elif mode == "flood_err":
    sys.stderr.buffer.write(b"e" * int(sys.argv[2]))
    sys.stderr.buffer.flush()
elif mode == "flood_both":
    n = int(sys.argv[2])
    sys.stdout.buffer.write(b"x" * n)
    sys.stderr.buffer.write(b"e" * n)
    sys.stdout.buffer.flush()
    sys.stderr.buffer.flush()
elif mode == "sleep":
    time.sleep(float(sys.argv[2]))
elif mode == "ignore_stdin_sleep":
    time.sleep(float(sys.argv[2]))
elif mode == "ignore_term_sleep":
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    time.sleep(float(sys.argv[2]))
"""


def _stub(tmp_path: Path) -> Path:
    path = tmp_path / "stub.py"
    path.write_text(_STUB, encoding="utf-8")
    return path


def _stub_argv(tmp_path: Path, *args: str) -> list[str]:
    return [sys.executable, str(_stub(tmp_path)), *args]


def _bounded(tmp_path, *args, **kwargs):
    kwargs.setdefault("stdin_bytes", b"")
    kwargs.setdefault("timeout_seconds", 10)
    kwargs.setdefault("max_stdout_bytes", 1024)
    kwargs.setdefault("max_stderr_bytes", 1024)
    return runner.run_bounded(_stub_argv(tmp_path, *args), **kwargs)


# ---------------------------------------------------------------------------
# Tier 1 -- pins, limits, CLI.
# ---------------------------------------------------------------------------
def test_public_pins_match_tracked_evidence():
    assert runner.HUNSPELL_RELEASE == "v1.7.3"
    assert runner.HUNSPELL_COMMIT == "c5f98152a274e25b5107101104bef632b83a0cc9"
    assert runner.CONTAINER_PLATFORM == "linux/arm64"
    assert runner.CONTAINER_REFERENCE.startswith(
        "docker.io/library/buildpack-deps@sha256:"
    )


def test_exact_defensive_limits():
    assert runner.MAX_TOKEN_BYTES == 256
    assert runner.MAX_TOKENS_PER_BATCH == 256
    assert runner.MAX_TOKENS_PER_REQUEST == 10_000
    assert runner.BATCH_TIMEOUT_SECONDS == 30
    assert runner.MAX_STDOUT_BYTES == 2 * 1024 * 1024
    assert runner.MAX_STDERR_BYTES == 64 * 1024
    assert runner.TERMINATION_GRACE_SECONDS == 1.0


def test_cli_exposes_only_opt_in_and_help():
    parser = runner._build_parser()
    options: set[str] = set()
    for action in parser._actions:
        options.update(action.option_strings)
    assert options == {"-h", "--help", "--allow-phase-a-run"}


def test_default_refuses_before_execution(capsys):
    assert runner.main([]) == runner.EXIT_OPT_IN_REQUIRED
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == runner._OPT_IN_MESSAGE + "\n"


def test_opt_in_does_not_execute_live_phase_a(capsys):
    assert runner.main(["--allow-phase-a-run"]) == runner.EXIT_OPERATIONAL_ABORT
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == runner._ABORT_MESSAGE + "\n"
    assert runner._LIVE_PHASE_A_ENABLED is False


@pytest.mark.parametrize("argument", ["--root", "--dictionary", "--output", "extra"])
def test_forbidden_arguments_are_rejected(argument):
    with pytest.raises(SystemExit) as excinfo:
        runner.main([argument])
    assert excinfo.value.code == 2


# ---------------------------------------------------------------------------
# Tier 1 -- token validation and batching.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "bad",
    [
        "syn_text",
        b"syn_text",
        bytearray(b"x"),
        ["ok", 7],
        [""],
        ["syn two"],
        ["syn\ttwo"],
        ["syn\ntwo"],
        ["syn\x00two"],
        ["syn\x7ftwo"],
        ["a" * 257],
    ],
)
def test_validate_tokens_fails_closed_without_echoing(bad):
    with pytest.raises(runner.ParityInputError) as excinfo:
        runner.validate_tokens(bad)
    assert "syn" not in str(excinfo.value)


def test_validate_tokens_accepts_boundary_length():
    tokens = runner.validate_tokens(["a" * 256, "syn_ok"])
    assert tokens == ("a" * 256, "syn_ok")


def test_over_request_limit_fails_closed():
    with pytest.raises(runner.ParityInputError):
        runner.validate_tokens(["t"] * (runner.MAX_TOKENS_PER_REQUEST + 1))


def test_batch_tokens_splits_at_ceiling_preserving_order():
    tokens = tuple(f"t{i}" for i in range(600))
    batches = runner.batch_tokens(tokens)
    assert [len(batch) for batch in batches] == [256, 256, 88]
    assert tuple(tok for batch in batches for tok in batch) == tokens


# ---------------------------------------------------------------------------
# Tier 1 -- protocol-neutral whole-stream observation (no framing assumption).
# ---------------------------------------------------------------------------
def test_whole_stream_summary_counts_are_coarse():
    assert runner.whole_stream_summary(b"") == (0, 0, 0, 0)
    total_bytes, total_lf, blank, nonempty = runner.whole_stream_summary(
        b"aa\n\nbbb\ncccc\n"
    )
    assert total_bytes == len(b"aa\n\nbbb\ncccc\n")
    assert total_lf == 4
    assert blank == 1
    assert nonempty == 3


def test_observation_has_no_per_token_framing_fields():
    obs = runner.observe_candidate(
        b"banner\n",
        b"banner\n",
        execution_completed_within_limits=True,
        max_stdout_bytes=7,
        max_stderr_bytes=0,
        max_batch_latency_ms=1,
    )
    for forbidden in (
        "candidate_passed",
        "response_segment_count",
        "response_segment_count_matches_input",
        "known_truth_partition_consistent",
    ):
        assert not hasattr(obs, forbidden)


def test_banner_blank_and_multiline_are_not_one_token_per_line_proof():
    hypothetical = b"@ (#) banner line\n\n*\n& near 2 0: a, b\n\n+ ROOT\n"
    obs = runner.observe_candidate(
        hypothetical,
        hypothetical,
        execution_completed_within_limits=True,
        max_stdout_bytes=len(hypothetical),
        max_stderr_bytes=0,
        max_batch_latency_ms=2,
    )
    assert obs.observation_completed is True
    assert obs.raw_stream_identical_across_runs is True
    assert obs.structural_summary_stable is True
    assert obs.total_lf_count == hypothetical.count(b"\n")
    assert obs.blank_line_count == 2
    assert not hasattr(obs, "candidate_passed")


def test_observation_detects_cross_run_instability():
    obs = runner.observe_candidate(
        b"aa\nbb\n",
        b"aa\nbbb\n",
        execution_completed_within_limits=True,
        max_stdout_bytes=8,
        max_stderr_bytes=0,
        max_batch_latency_ms=1,
    )
    assert obs.raw_stream_identical_across_runs is False
    assert obs.structural_summary_stable is False


# ---------------------------------------------------------------------------
# Tier 1 -- summary schema (observed facts only; never selects a mode).
# ---------------------------------------------------------------------------
def _observation(completed=True):
    return runner.CandidateObservation(
        observation_completed=completed,
        raw_stream_identical_across_runs=True,
        structural_summary_stable=True,
        total_bytes=10,
        total_lf_count=2,
        blank_line_count=0,
        nonempty_line_count=2,
        max_stdout_bytes=10,
        max_stderr_bytes=0,
        max_batch_latency_ms=1,
    )


def test_summary_schema_is_exact_and_reports_only_observed_facts():
    observations = {
        "PIPE_STREAM": _observation(True),
        "SINGLE_TOKEN_LIST": _observation(False),
    }
    summary = runner.build_phase_a_summary(
        observations,
        environment_identity_match=True,
        offline_build=True,
    )
    assert tuple(summary) == runner.SUMMARY_KEYS
    assert summary["selected_mode_label"] == "NONE"
    assert summary["candidate_observation_count"] == 2
    assert summary["pipe_stream_observation_completed"] is True
    assert summary["single_token_list_observation_completed"] is False
    assert set(summary["candidate_observations"]) == set(runner.CANDIDATE_LABELS)
    assert (
        tuple(summary["candidate_observations"]["PIPE_STREAM"])
        == runner.CANDIDATE_OBSERVATION_KEYS
    )
    assert summary["no_real_resource_or_corpus_access"] is True
    assert "candidate_passed" not in summary
    assert "passing_candidate_count" not in summary
    for observation in summary["candidate_observations"].values():
        assert "candidate_passed" not in observation


# ---------------------------------------------------------------------------
# Tier 1 -- invocations and fixtures.
# ---------------------------------------------------------------------------
def test_candidate_invocation_is_argument_vector():
    assert runner.candidate_invocation("PIPE_STREAM", "/b/es") == (
        "hunspell",
        "-d",
        "/b/es",
        "-a",
    )
    assert runner.candidate_invocation("SINGLE_TOKEN_LIST", "/b/es") == (
        "hunspell",
        "-d",
        "/b/es",
        "-l",
    )
    with pytest.raises(runner.ParityInputError):
        runner.candidate_invocation("BATCH_FILTER", "/b/es")


def test_dictionary_header_equals_actual_record_count():
    fixture = runner.build_invented_fixture()
    declared, actual = runner.dictionary_declared_and_actual_counts(
        fixture.dictionary_bytes
    )
    assert declared == actual == 7
    tampered = fixture.dictionary_bytes.replace(b"7\n", b"6\n", 1)
    declared2, actual2 = runner.dictionary_declared_and_actual_counts(tampered)
    assert declared2 != actual2


def test_invented_fixture_covers_all_required_behaviors():
    fixture = runner.build_invented_fixture()
    assert fixture.query_behaviors == runner.REQUIRED_QUERY_BEHAVIORS
    assert set(fixture.query_behaviors) == set(runner.REQUIRED_QUERY_BEHAVIORS)
    assert len(fixture.query_tokens) == len(fixture.known_truth)
    assert len(fixture.query_tokens) == len(fixture.query_behaviors)
    behavior = dict(zip(fixture.query_behaviors, fixture.known_truth))
    for derived in (
        "prefix_derived",
        "suffix_derived",
        "cross_product",
        "repeated_record_prefix_derived",
        "repeated_record_suffix_derived",
        "first_continuation_derived",
        "chained_continuation_derived",
    ):
        assert behavior[derived] is True
    assert behavior["unflagged_base"] is True
    assert behavior["rejected"] is False


def test_invented_fixture_has_repeated_records_and_continuation():
    fixture = runner.build_invented_fixture()
    assert fixture.dictionary_bytes.count(b"synrep/") == 2
    assert b"er/D" in fixture.affix_bytes
    index_one = fixture.query_tokens.index("synbase")
    index_two = len(fixture.query_tokens) - 1 - fixture.query_tokens[::-1].index(
        "synbase"
    )
    assert index_two - index_one > 1
    assert fixture.query_behaviors[index_two] == "duplicate_base"


def test_hardened_container_argv_is_pinned_and_locked_down(tmp_path):
    argv = runner.hardened_container_argv(
        cidfile_path=tmp_path / "cid",
        bundle_dir=tmp_path / "bundle",
        install_dir=tmp_path / "install",
        inner_argv=["hunspell", "-d", "/bundle/es", "-a"],
    )
    assert argv[argv.index("--network") + 1] == "none"
    assert argv[argv.index("--platform") + 1] == "linux/arm64"
    assert argv[argv.index("--cap-drop") + 1] == "ALL"
    assert argv[argv.index("--security-opt") + 1] == "no-new-privileges"
    assert "--read-only" in argv
    assert argv[argv.index("--cidfile") + 1] == str(tmp_path / "cid")
    assert runner.CONTAINER_REFERENCE in argv
    assert argv[-4:] == ["hunspell", "-d", "/bundle/es", "-a"]


# ---------------------------------------------------------------------------
# Tier 1 -- stdin writer worker (offset loop).
# ---------------------------------------------------------------------------
class _PartialStream:
    def __init__(self, chunk):
        self.chunk = chunk
        self.buf = bytearray()
        self.flushed = False
        self.closed = False

    def write(self, view):
        data = bytes(view)
        take = min(self.chunk, len(data))
        self.buf.extend(data[:take])
        return take

    def flush(self):
        self.flushed = True

    def close(self):
        self.closed = True


def test_writer_delivers_full_payload_via_offset_loop():
    delivered = [False]
    stream = _PartialStream(chunk=3)
    runner._writer_worker(stream, b"abcdefgh", delivered)
    assert bytes(stream.buf) == b"abcdefgh"
    assert delivered == [True]
    assert stream.flushed and stream.closed


@pytest.mark.parametrize("result", [0, None, -1])
def test_writer_zero_or_invalid_write_fails_closed(result):
    class _Bad:
        def write(self, _view):
            return result

        def flush(self):
            pass

        def close(self):
            pass

    delivered = [False]
    runner._writer_worker(_Bad(), b"abc", delivered)
    assert delivered == [False]


def test_writer_empty_payload_is_delivered_without_writing():
    class _Track:
        def __init__(self):
            self.wrote = False

        def write(self, view):
            self.wrote = True
            return len(bytes(view))

        def flush(self):
            pass

        def close(self):
            pass

    stream = _Track()
    delivered = [False]
    runner._writer_worker(stream, b"", delivered)
    assert delivered == [True]
    assert stream.wrote is False


# ---------------------------------------------------------------------------
# Tier 1 -- container cleanup contract (Docker always stubbed).
# ---------------------------------------------------------------------------
def test_clean_exit_cleanup_removes_only_the_cidfile(tmp_path):
    cidfile = tmp_path / "cid"
    cidfile.write_text("cabc\n", encoding="ascii")
    calls: list[str] = []
    runner.finalize_container(cidfile, clean_exit=True, docker_remove=calls.append)
    assert calls == []  # docker rm -f is NOT run on a clean --rm exit
    assert not cidfile.exists()


def test_abnormal_cleanup_calls_the_remover(tmp_path):
    cidfile = tmp_path / "cid"
    cidfile.write_text("cabc\n", encoding="ascii")
    calls: list[str] = []
    runner.finalize_container(cidfile, clean_exit=False, docker_remove=calls.append)
    assert calls == ["cabc"]
    assert not cidfile.exists()


def test_missing_cidfile_on_abnormal_exit_fails_closed(tmp_path):
    with pytest.raises(runner.ParityTransportError):
        runner.finalize_container(
            tmp_path / "absent", clean_exit=False, docker_remove=lambda _c: None
        )


def test_remover_failure_becomes_a_fixed_error(tmp_path):
    cidfile = tmp_path / "cid"
    cidfile.write_text("cabc\n", encoding="ascii")

    def _boom(_container_id):
        raise TimeoutError("private docker timeout detail")

    with pytest.raises(runner.ParityTransportError) as excinfo:
        runner.finalize_container(cidfile, clean_exit=False, docker_remove=_boom)
    assert "private" not in str(excinfo.value)


def test_nonzero_remover_result_is_not_confirmed(monkeypatch):
    monkeypatch.setattr(
        runner, "_DOCKER_RUN", lambda *a, **k: types.SimpleNamespace(returncode=1)
    )
    with pytest.raises(runner.ParityTransportError):
        runner._default_docker_remove("cabc")


def test_docker_removal_output_is_discarded_boundedly(monkeypatch):
    calls: list[tuple] = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(runner, "_DOCKER_RUN", fake_run)
    runner._default_docker_remove("cid123")
    (argv, kwargs) = calls[0]
    assert argv == ["docker", "rm", "-f", "cid123"]
    assert kwargs["stdin"] is subprocess.DEVNULL
    assert kwargs["stdout"] is subprocess.DEVNULL
    assert kwargs["stderr"] is subprocess.DEVNULL
    assert kwargs["timeout"] == runner._DOCKER_REMOVE_TIMEOUT
    assert "capture_output" not in kwargs


# ---------------------------------------------------------------------------
# Tier 2 -- output preservation and success path.
# ---------------------------------------------------------------------------
def test_stdout_captured_completely_after_child_exit(tmp_path):
    payload = 200_000  # more than one pipe buffer
    result = _bounded(
        tmp_path, "flood_out", str(payload), max_stdout_bytes=5_000_000
    )
    assert result.terminal_state == runner.STATE_NORMAL_EXIT
    assert result.stdout_bytes == payload


def test_stdout_and_stderr_completely_drained_after_exit(tmp_path):
    payload = 200_000
    result = _bounded(
        tmp_path,
        "flood_both",
        str(payload),
        max_stdout_bytes=5_000_000,
        max_stderr_bytes=5_000_000,
    )
    assert result.terminal_state == runner.STATE_NORMAL_EXIT
    assert result.stdout_bytes == payload
    assert result.stderr_bytes == payload


def test_run_bounded_captures_stdout_and_workers_join(tmp_path):
    result = _bounded(tmp_path, "echo", stdin_bytes=b"hello\n")
    assert result.terminal_state == runner.STATE_NORMAL_EXIT
    assert result.returncode == 0
    assert result.stdout == b"hello\n"
    assert result.workers_joined is True
    assert result.stdin_delivered is True


def test_complete_stdin_delivery_on_success(tmp_path):
    payload = b"hola\n" * 200
    result = _bounded(tmp_path, "echo", stdin_bytes=payload, max_stdout_bytes=5_000_000)
    assert result.terminal_state == runner.STATE_NORMAL_EXIT
    assert result.stdin_delivered is True
    assert result.stdout == payload
    assert result.worker_failed is False


def test_success_requires_all_workers_joined(tmp_path):
    result = runner.supervise(
        _stub_argv(tmp_path, "echo"),
        stdin_bytes=b"ok\n",
        timeout_seconds=10,
        max_stdout_bytes=1024,
        max_stderr_bytes=1024,
    )
    assert result.terminal_state == runner.STATE_NORMAL_EXIT
    assert result.workers_joined is True


def test_clean_success_invokes_clean_cleanup(tmp_path):
    calls: list[bool] = []
    result = _bounded(tmp_path, "echo", stdin_bytes=b"ok\n", cleanup=calls.append)
    assert result.terminal_state == runner.STATE_NORMAL_EXIT
    assert result.cleanup_required is True
    assert result.cleanup_confirmed is True
    assert calls == [True]


# ---------------------------------------------------------------------------
# Tier 2 -- worker failures and incomplete delivery.
# ---------------------------------------------------------------------------
def test_child_closing_stdin_early_is_worker_failure(tmp_path):
    result = _bounded(
        tmp_path, "read_some_exit0", stdin_bytes=b"x" * 1_000_000
    )
    assert result.terminal_state == runner.STATE_WORKER_FAILURE
    assert result.worker_failed is True
    assert result.stdin_delivered is False
    assert result.returncode == 0


def test_incomplete_delivery_passes_clean_exit_false(tmp_path):
    calls: list[bool] = []
    result = _bounded(
        tmp_path, "read_some_exit0", stdin_bytes=b"x" * 1_000_000, cleanup=calls.append
    )
    assert result.terminal_state == runner.STATE_WORKER_FAILURE
    assert calls == [False]


def test_worker_failure_passes_clean_exit_false(tmp_path, monkeypatch):
    def _boom(*_args, **_kwargs):
        raise RuntimeError("private drain detail")

    monkeypatch.setattr(runner, "_drain_worker", _boom)
    calls: list[bool] = []
    result = _bounded(tmp_path, "sleep", "0.05", cleanup=calls.append)
    assert result.terminal_state == runner.STATE_WORKER_FAILURE
    assert calls == [False]


def test_writer_worker_failure_is_recorded(tmp_path, monkeypatch):
    def _boom(*_args, **_kwargs):
        raise RuntimeError("private writer detail")

    monkeypatch.setattr(runner, "_writer_worker", _boom)
    result = _bounded(tmp_path, "sleep", "0.05")
    assert result.terminal_state == runner.STATE_WORKER_FAILURE
    assert result.worker_failed is True


# ---------------------------------------------------------------------------
# Tier 2 -- timeout, overflow, nonzero exit.
# ---------------------------------------------------------------------------
def test_run_bounded_reports_nonzero_exit_and_supervise_fails_closed(tmp_path):
    result = _bounded(tmp_path, "exit7")
    assert result.terminal_state == runner.STATE_NORMAL_EXIT
    assert result.returncode == 7
    with pytest.raises(runner.ParityTransportError):
        runner.supervise(
            _stub_argv(tmp_path, "exit7"),
            stdin_bytes=b"",
            timeout_seconds=10,
            max_stdout_bytes=1024,
            max_stderr_bytes=1024,
        )


def test_stdout_ceiling_enforced_midstream_invokes_abnormal_cleanup(tmp_path):
    calls: list[bool] = []
    result = _bounded(
        tmp_path,
        "flood_out",
        "500000",
        timeout_seconds=20,
        max_stdout_bytes=1000,
        cleanup=calls.append,
    )
    assert result.terminal_state == runner.STATE_OUTPUT_OVERFLOW
    assert result.stdout_limit_exceeded is True
    assert result.stdout_bytes <= 1000
    assert calls == [False]


def test_stderr_ceiling_enforced_midstream(tmp_path):
    result = _bounded(
        tmp_path,
        "flood_err",
        "500000",
        timeout_seconds=20,
        max_stderr_bytes=1000,
    )
    assert result.terminal_state == runner.STATE_OUTPUT_OVERFLOW
    assert result.stderr_limit_exceeded is True
    assert result.stderr_bytes <= 1000


def test_timeout_invokes_abnormal_cleanup(tmp_path):
    calls: list[bool] = []
    result = _bounded(tmp_path, "sleep", "5", timeout_seconds=0.3, cleanup=calls.append)
    assert result.terminal_state == runner.STATE_TIMEOUT
    assert calls == [False]


def test_forced_termination_when_sigterm_ignored(tmp_path):
    result = _bounded(
        tmp_path,
        "ignore_term_sleep",
        "5",
        timeout_seconds=0.3,
        grace_seconds=1.0,
    )
    assert result.terminal_state == runner.STATE_TIMEOUT
    assert result.forced_termination is True


def test_nonzero_exit_invokes_abnormal_cleanup(tmp_path):
    calls: list[bool] = []
    result = _bounded(tmp_path, "exit7", cleanup=calls.append)
    assert result.returncode == 7
    assert calls == [False]


def test_writer_worker_prevents_deadlock_when_child_never_reads_stdin(tmp_path):
    start = time.monotonic()
    result = _bounded(
        tmp_path,
        "ignore_stdin_sleep",
        "5",
        stdin_bytes=b"x" * 1_000_000,
        timeout_seconds=0.4,
    )
    elapsed = time.monotonic() - start
    assert result.terminal_state == runner.STATE_TIMEOUT
    assert result.timed_out is True
    assert result.workers_joined is True
    assert elapsed < 0.4 + runner.TERMINATION_GRACE_SECONDS + 3.0


# ---------------------------------------------------------------------------
# Tier 2 -- cleanup confirmation, cancellation, and lifecycle safety.
# ---------------------------------------------------------------------------
def test_cleanup_failure_produces_fixed_failure(tmp_path):
    def _boom(_clean_exit):
        raise RuntimeError("private cleanup detail")

    result = _bounded(tmp_path, "echo", stdin_bytes=b"ok\n", cleanup=_boom)
    assert result.cleanup_confirmed is False
    with pytest.raises(runner.ParityTransportError) as excinfo:
        runner.supervise(
            _stub_argv(tmp_path, "echo"),
            stdin_bytes=b"ok\n",
            timeout_seconds=10,
            max_stdout_bytes=1024,
            max_stderr_bytes=1024,
            cleanup=_boom,
        )
    assert "private" not in str(excinfo.value)


def test_cancellation_after_launch_terminates_and_cleans_up(tmp_path):
    seen: dict[str, int] = {}
    calls: list[bool] = []

    def hook(proc):
        seen["pid"] = proc.pid
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        runner.run_bounded(
            _stub_argv(tmp_path, "sleep", "5"),
            stdin_bytes=b"",
            timeout_seconds=10,
            max_stdout_bytes=1024,
            max_stderr_bytes=1024,
            cleanup=calls.append,
            _after_launch=hook,
        )
    assert calls == [False]
    with pytest.raises(ProcessLookupError):
        os.kill(seen["pid"], 0)


def test_unexpected_supervisor_exception_is_wrapped(tmp_path):
    calls: list[bool] = []

    def hook(_proc):
        raise RuntimeError("private supervisor detail")

    with pytest.raises(runner.ParityTransportError) as excinfo:
        runner.run_bounded(
            _stub_argv(tmp_path, "sleep", "5"),
            stdin_bytes=b"",
            timeout_seconds=10,
            max_stdout_bytes=1024,
            max_stderr_bytes=1024,
            cleanup=calls.append,
            _after_launch=hook,
        )
    assert "private" not in str(excinfo.value)
    assert calls == [False]


def test_second_worker_start_failure_terminates_and_cleans_up(tmp_path, monkeypatch):
    seen: dict[str, int] = {}
    calls: list[bool] = []
    joined_started: dict[str, int] = {}
    real_start = runner._start_worker
    real_join = runner._join_workers
    count = [0]

    def fake_start(thread):
        count[0] += 1
        if count[0] == 2:
            raise RuntimeError("private start detail")
        return real_start(thread)

    def spy_join(started, until):
        joined_started["n"] = len(list(started))
        return real_join(started, until)

    monkeypatch.setattr(runner, "_start_worker", fake_start)
    monkeypatch.setattr(runner, "_join_workers", spy_join)
    with pytest.raises(runner.ParityTransportError) as excinfo:
        runner.run_bounded(
            _stub_argv(tmp_path, "sleep", "5"),
            stdin_bytes=b"",
            timeout_seconds=10,
            max_stdout_bytes=1024,
            max_stderr_bytes=1024,
            cleanup=calls.append,
            _after_launch=lambda proc: seen.update(pid=proc.pid),
        )
    assert "private" not in str(excinfo.value)
    assert calls == [False]
    assert joined_started["n"] == 1  # only the one started worker was joined
    with pytest.raises(ProcessLookupError):
        os.kill(seen["pid"], 0)


def test_cleanup_runs_even_if_join_errors(tmp_path, monkeypatch):
    calls: list[bool] = []

    def _boom(*_args, **_kwargs):
        raise RuntimeError("private join detail")

    monkeypatch.setattr(runner, "_join_workers", _boom)
    with pytest.raises(runner.ParityTransportError) as excinfo:
        runner.run_bounded(
            _stub_argv(tmp_path, "echo"),
            stdin_bytes=b"ok\n",
            timeout_seconds=10,
            max_stdout_bytes=1024,
            max_stderr_bytes=1024,
            cleanup=calls.append,
        )
    assert "private" not in str(excinfo.value)
    assert calls == [False]


def test_cleanup_runs_even_if_stream_close_errors(tmp_path, monkeypatch):
    calls: list[bool] = []

    def _boom(_proc):
        raise RuntimeError("private close detail")

    monkeypatch.setattr(runner, "_close_streams", _boom)
    result = _bounded(tmp_path, "echo", stdin_bytes=b"ok\n", cleanup=calls.append)
    assert result.terminal_state == runner.STATE_NORMAL_EXIT
    assert calls == [True]


# ---------------------------------------------------------------------------
# Tier 2 -- parameter validation.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "kwargs",
    [
        {"timeout_seconds": 0},
        {"timeout_seconds": -1},
        {"grace_seconds": 0},
        {"poll_interval": 0},
        {"max_stdout_bytes": 0},
        {"max_stderr_bytes": -5},
    ],
)
def test_run_bounded_validates_parameters(tmp_path, kwargs):
    base = {
        "stdin_bytes": b"",
        "timeout_seconds": 1,
        "max_stdout_bytes": 16,
        "max_stderr_bytes": 16,
    }
    base.update(kwargs)
    with pytest.raises(runner.ParityInputError):
        runner.run_bounded(_stub_argv(tmp_path, "echo"), **base)


def test_run_bounded_rejects_bad_argv_and_launch_failure(tmp_path):
    with pytest.raises(runner.ParityInputError):
        runner.run_bounded(
            "not-a-list",
            stdin_bytes=b"",
            timeout_seconds=1,
            max_stdout_bytes=1,
            max_stderr_bytes=1,
        )
    with pytest.raises(runner.ParityTransportError):
        runner.run_bounded(
            [str(tmp_path / "does-not-exist")],
            stdin_bytes=b"",
            timeout_seconds=1,
            max_stdout_bytes=1,
            max_stderr_bytes=1,
        )
