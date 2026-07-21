"""Offline tests for the per-token parity Phase A observation infrastructure.

These cover the runner itself: pure functions, invented fixtures, the CLI, the
Phase A/B orchestration and live-environment wiring (always driven by injected
fakes), and the Phase B parser and aggregate contract.  The bounded process
supervisor and the container identity/cleanup contract now live in stable source
modules and are tested directly in ``tests/test_hunspell_process_supervision.py``
and ``tests/test_hunspell_container.py``; this file only asserts that the runner's
re-exports remain identical to those source objects and that the moved
implementation-private helpers are no longer runner-owned.

No test starts Docker, uses the network, runs pinned Hunspell, or accesses RLA-ES,
CALLHOME, Bangor, ignored resources, or private logs.  Phase A tests assume no
framing; Phase B tests enforce only the approved public ``-a``/``-l`` contract over
invented bytes. Docker is always stubbed; no Docker command actually runs.
"""

from __future__ import annotations

import importlib.util
import io
import json
import sys
import tarfile
import types
from pathlib import Path

import pytest

from cslm.data import hunspell_container as cont
from cslm.data import hunspell_process_supervision as sup
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

# Implementation-private helpers that moved to the stable source modules.  The
# runner must not re-export them, so a stale ``monkeypatch.setattr`` aimed at the
# runner fails immediately instead of patching a copy nobody calls.
_MOVED_PRIVATE_NAMES = (
    "_WorkerOutcome",
    "_validate_supervision_params",
    "_writer_worker",
    "_drain_worker",
    "_supervised_worker",
    "_start_worker",
    "_join_workers",
    "_close_streams",
    "_terminate_group",
    "_watch_process",
    "_default_docker_remove",
    "_remove_cidfile",
    "_DOCKER_RUN",
    "_DOCKER_REMOVE_TIMEOUT",
)


# ---------------------------------------------------------------------------
# Tier 1 -- stable-source compatibility and ownership.
# ---------------------------------------------------------------------------
def test_runner_reexports_the_shared_supervisor_objects():
    assert runner.run_bounded is sup.run_bounded
    assert runner.supervise is sup.supervise
    assert runner.BoundedRun is sup.BoundedRun
    assert runner.TERMINAL_STATES is sup.TERMINAL_STATES
    assert runner.STATE_NORMAL_EXIT is sup.STATE_NORMAL_EXIT
    assert runner.STATE_TIMEOUT is sup.STATE_TIMEOUT
    assert runner.STATE_OUTPUT_OVERFLOW is sup.STATE_OUTPUT_OVERFLOW
    assert runner.STATE_WORKER_FAILURE is sup.STATE_WORKER_FAILURE


def test_runner_reexports_the_shared_container_objects():
    assert runner.hardened_container_argv is cont.hardened_container_argv
    assert runner.finalize_container is cont.finalize_container
    assert runner.container_cleanup is cont.container_cleanup
    assert runner.HUNSPELL_RELEASE == cont.HUNSPELL_RELEASE
    assert runner.HUNSPELL_COMMIT == cont.HUNSPELL_COMMIT
    assert runner.CONTAINER_REPOSITORY == cont.CONTAINER_REPOSITORY
    assert runner.CONTAINER_PLATFORM == cont.CONTAINER_PLATFORM
    assert runner.CONTAINER_PLATFORM_DIGEST == cont.CONTAINER_PLATFORM_DIGEST
    assert runner.CONTAINER_REFERENCE == cont.CONTAINER_REFERENCE
    assert runner._CONTAINER_HUNSPELL_BIN == cont._CONTAINER_HUNSPELL_BIN
    assert runner._CONTAINER_HUNSPELL_LIB == cont._CONTAINER_HUNSPELL_LIB


@pytest.mark.parametrize("name", _MOVED_PRIVATE_NAMES)
def test_moved_private_helpers_are_not_runner_owned(name):
    assert not hasattr(runner, name)
    assert hasattr(sup, name) or hasattr(cont, name)


def test_runner_does_not_import_a_concrete_transport():
    assert not hasattr(runner, "HunspellContainerPipeTransport")
    assert not hasattr(runner, "hunspell_pipe_transport")


# ---------------------------------------------------------------------------
# Tier 1 -- pins, limits, CLI.
# ---------------------------------------------------------------------------
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
    assert options == {
        "-h",
        "--help",
        "--allow-phase-a-run",
        "--allow-phase-b-run",
    }


def test_default_refuses_before_execution(capsys):
    assert runner.main([]) == runner.EXIT_OPT_IN_REQUIRED
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == runner._OPT_IN_MESSAGE + "\n"


def test_phase_b_live_gate_is_enabled_but_default_still_refuses(capsys):
    assert runner._LIVE_PHASE_B_ENABLED is True
    assert runner.main([]) == runner.EXIT_OPT_IN_REQUIRED
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == runner._OPT_IN_MESSAGE + "\n"


def test_phase_a_and_phase_b_opt_ins_are_mutually_exclusive():
    with pytest.raises(SystemExit) as excinfo:
        runner.main(["--allow-phase-a-run", "--allow-phase-b-run"])
    assert excinfo.value.code == 2


def test_opt_in_enabled_gate_uses_injected_fake_environment(monkeypatch, capsys):
    assert runner._LIVE_PHASE_A_ENABLED is True
    env = _FakeEnvironment()
    monkeypatch.setattr(runner, "_LivePhaseAEnvironment", lambda *a, **k: env)

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("real Phase A seam must not run in tests")

    monkeypatch.setattr(runner, "_acquire_public_pinned_source", _fail_if_called)
    monkeypatch.setattr(runner, "run_bounded", _fail_if_called)
    assert runner.main(["--allow-phase-a-run"]) == runner.EXIT_SUCCESS
    # The opted-in CLI path drove only the injected fake through its lifecycle,
    # never the real acquisition or bounded-transport seam.
    assert (env.verified, env.built, env.teardowns) == (True, True, 1)
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out != ""  # a summary was produced; schema is covered elsewhere


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


# ---------------------------------------------------------------------------
# Phase A -- shared helpers.
# ---------------------------------------------------------------------------
def _phase_a_bounded_run(**overrides):
    base = dict(
        returncode=0,
        terminal_state=runner.STATE_NORMAL_EXIT,
        forced_termination=False,
        stdin_delivered=True,
        stdout=b"out\n",
        stderr=b"",
        stdout_bytes=4,
        stderr_bytes=0,
        stdout_limit_exceeded=False,
        stderr_limit_exceeded=False,
        timed_out=False,
        worker_failed=False,
        workers_joined=True,
        cleanup_required=False,
        cleanup_confirmed=True,
        latency_ms=3,
    )
    base.update(overrides)
    return runner.BoundedRun(**base)


def _repetition(streams, **over):
    return runner._CandidateRepetition(
        raw_streams=tuple(streams),
        max_stdout_bytes=over.get("max_stdout_bytes", 4),
        max_stderr_bytes=over.get("max_stderr_bytes", 0),
        max_latency_ms=over.get("max_latency_ms", 1),
        cleanup_confirmed=over.get("cleanup_confirmed", True),
    )


class _FakeEnvironment:
    """A fake Phase A environment; performs no acquisition, build, or subprocess."""

    def __init__(self, raise_at=None, raw=b"line\n", evidence=None):
        self.raise_at = raise_at
        self.raw = raw
        self._evidence = evidence or runner._PhaseAEvidence(
            environment_identity_match=True, offline_build=True
        )
        self.calls: list[tuple[str, int]] = []
        self.fixture_seen = None
        self.verified = False
        self.built = False
        self.teardowns = 0

    def verify_identities(self):
        if self.raise_at == "verify":
            raise runner.ParityHarnessError("verify failed")
        self.verified = True

    def build(self):
        if self.raise_at == "build":
            raise runner.ParityHarnessError("build failed")
        self.built = True

    def run_candidate(self, label, fixture, run_index):
        self.fixture_seen = fixture
        self.calls.append((label, run_index))
        if self.raise_at == "run":
            raise runner.ParityHarnessError("run failed")
        return _repetition((self.raw,), max_stdout_bytes=len(self.raw))

    def evidence(self):
        return self._evidence

    def teardown(self):
        self.teardowns += 1


# ---------------------------------------------------------------------------
# Phase A -- orchestration wiring (dependency-injected; no Docker/network).
# ---------------------------------------------------------------------------
def test_orchestration_runs_two_candidates_two_runs_each():
    env = _FakeEnvironment()
    runner._run_phase_a(env)
    assert env.verified is True
    assert env.built is True
    assert env.calls == [
        ("PIPE_STREAM", 0),
        ("PIPE_STREAM", 1),
        ("SINGLE_TOKEN_LIST", 0),
        ("SINGLE_TOKEN_LIST", 1),
    ]


def test_orchestration_emits_exact_schema_none_and_no_verdict():
    summary = runner._run_phase_a(_FakeEnvironment())
    assert tuple(summary) == runner.SUMMARY_KEYS
    assert summary["selected_mode_label"] == "NONE"
    assert summary["candidate_observation_count"] == 2
    assert "candidate_passed" not in summary
    assert "passing_candidate_count" not in summary
    for observation in summary["candidate_observations"].values():
        assert "candidate_passed" not in observation


def test_orchestration_only_invented_fixture_reaches_environment():
    env = _FakeEnvironment()
    runner._run_phase_a(env)
    assert env.fixture_seen == runner.build_invented_fixture()


def test_orchestration_reduces_raw_and_emits_only_scalars():
    env = _FakeEnvironment(raw=b"aa\nbb\n")
    summary = runner._run_phase_a(env)
    observation = summary["candidate_observations"]["PIPE_STREAM"]
    assert observation["total_bytes"] == len(b"aa\nbb\n")
    assert observation["total_lf_count"] == 2
    serialized = json.dumps(summary)  # content-free: no raw bytes reach the summary
    assert "aa" not in serialized and "bb" not in serialized


@pytest.mark.parametrize("stage", ["verify", "build", "run"])
def test_orchestration_fails_closed_at_each_stage(stage):
    with pytest.raises(runner.ParityHarnessError):
        runner._run_phase_a(_FakeEnvironment(raise_at=stage))


def test_summary_reports_derived_evidence_not_hardcoded():
    env = _FakeEnvironment(
        evidence=runner._PhaseAEvidence(
            environment_identity_match=False, offline_build=True
        )
    )
    summary = runner._run_phase_a(env)
    assert summary["environment_identity_match"] is False
    assert summary["offline_build"] is True


def test_run_phase_a_with_teardown_success_tears_down_once():
    env = _FakeEnvironment()
    runner._run_phase_a_with_teardown(env)
    assert env.teardowns == 1


@pytest.mark.parametrize("stage", ["verify", "build", "run"])
def test_run_phase_a_with_teardown_tears_down_on_failure(stage):
    env = _FakeEnvironment(raise_at=stage)
    with pytest.raises(runner.ParityHarnessError):
        runner._run_phase_a_with_teardown(env)
    assert env.teardowns == 1


def test_both_failure_surfaces_only_fixed_cleanup_error():
    class _BadTeardownEnv(_FakeEnvironment):
        def teardown(self):
            super().teardown()
            raise runner.ParityHarnessError("cleanup could not be confirmed")

    env = _BadTeardownEnv(raise_at="build")
    with pytest.raises(runner.ParityHarnessError) as excinfo:
        runner._run_phase_a_with_teardown(env)
    assert "build failed" not in str(excinfo.value)  # underlying detail not leaked
    assert env.teardowns == 1


# ---------------------------------------------------------------------------
# Phase A -- per-token candidate processes (no Docker; captured via a fake runner).
# ---------------------------------------------------------------------------
def _recording_runner():
    calls: list[dict] = []

    def run_process(argv, stdin_bytes, cleanup):
        calls.append({"argv": list(argv), "stdin": stdin_bytes, "cleanup": cleanup})
        return _phase_a_bounded_run(stdout=b"r\n", stdout_bytes=2)

    return run_process, calls


def _cidfile_factory(tmp_path):
    return lambda label, index: tmp_path / f"cid_{label}_{index}"


def test_single_token_list_launches_one_process_per_token(tmp_path):
    fixture = runner.build_invented_fixture()
    tokens = runner.validate_tokens(fixture.query_tokens)
    run_process, calls = _recording_runner()
    repetition = runner._run_candidate_processes(
        "SINGLE_TOKEN_LIST", tokens, tmp_path / "fx", tmp_path / "install",
        run_process, None, _cidfile_factory(tmp_path),
    )
    assert len(calls) == len(tokens)  # one process per token
    assert len(repetition.raw_streams) == len(tokens)
    # order preserved; each stdin is exactly one token plus a newline
    for call, token in zip(calls, tokens):
        assert call["stdin"] == (token + "\n").encode("utf-8")
    # duplicate token yields distinct invocations in their original positions
    assert calls[0]["stdin"] == b"synbase\n"
    assert calls[len(tokens) - 2]["stdin"] == b"synbase\n"
    # no token ever appears in argv
    for call in calls:
        joined = " ".join(call["argv"])
        for token in tokens:
            assert token not in joined
        assert callable(call["cleanup"])


def test_pipe_stream_uses_one_bounded_batch_invocation(tmp_path):
    fixture = runner.build_invented_fixture()
    tokens = runner.validate_tokens(fixture.query_tokens)
    run_process, calls = _recording_runner()
    repetition = runner._run_candidate_processes(
        "PIPE_STREAM", tokens, tmp_path / "fx", tmp_path / "install",
        run_process, None, _cidfile_factory(tmp_path),
    )
    assert len(calls) == 1  # the invented query fits one bounded batch
    assert len(repetition.raw_streams) == 1
    assert calls[0]["stdin"] == ("\n".join(tokens) + "\n").encode("utf-8")


@pytest.mark.parametrize("label", runner.CANDIDATE_LABELS)
def test_shared_process_runner_uses_exact_phase_b_stdin(label, tmp_path):
    fixture = runner.build_invented_fixture()
    tokens = runner.validate_tokens(fixture.query_tokens)
    run_process, calls = _recording_runner()
    runner._run_candidate_processes(
        label,
        tokens,
        tmp_path / "fx",
        tmp_path / "install",
        run_process,
        None,
        _cidfile_factory(tmp_path),
        stdin_builder=runner._phase_b_stdin,
    )
    if label == "PIPE_STREAM":
        assert len(calls) == 1
        assert calls[0]["stdin"] == b"".join(
            b"^" + token.encode("utf-8") + b"\n" for token in tokens
        )
    else:
        assert len(calls) == len(tokens)
        assert [call["stdin"] for call in calls] == [
            token.encode("utf-8") + b"\n" for token in tokens
        ]


def test_live_phase_b_environment_routes_only_to_phase_b_stdin(tmp_path):
    captured: list[bytes] = []

    def fake_runner(argv, **kwargs):
        captured.append(kwargs["stdin_bytes"])
        return _phase_a_bounded_run(stdout=b"", stdout_bytes=0)

    env = runner._LivePhaseBEnvironment(runner=fake_runner)
    env._workspace = types.SimpleNamespace(name=str(tmp_path))
    env._source_verified = True
    env._container_verified = True
    env._build_verified = True
    env._install_dir = tmp_path / "install"
    env.run_candidate("PIPE_STREAM", runner.build_invented_fixture(), 0)
    assert len(captured) == 1
    assert captured[0].startswith(b"^")
    assert captured[0].count(b"\n^") == 9


def test_phase_a_batch_stdin_encoding():
    assert runner._phase_a_batch_stdin(("a", "b")) == b"a\nb\n"
    assert runner._phase_a_batch_stdin(()) == b""


def test_observe_repetitions_compares_ordered_tuples_deterministically():
    first = _repetition((b"x\n", b"y\n"))
    same = _repetition((b"x\n", b"y\n"))
    observation = runner._observe_repetitions(first, same)
    assert observation.raw_stream_identical_across_runs is True
    assert observation.structural_summary_stable is True
    different = _repetition((b"x\n", b"z\n"))
    observation_two = runner._observe_repetitions(first, different)
    assert observation_two.raw_stream_identical_across_runs is False


@pytest.mark.parametrize(
    ("label", "mode"),
    [("PIPE_STREAM", "-a"), ("SINGLE_TOKEN_LIST", "-l")],
)
def test_phase_a_container_argv_is_correct_without_framing(tmp_path, label, mode):
    argv = runner._phase_a_container_argv(
        label, tmp_path / "fx", tmp_path / "install", tmp_path / "cid"
    )
    assert argv[argv.index("--network") + 1] == "none"
    assert "--read-only" in argv
    assert argv[argv.index("--cap-drop") + 1] == "ALL"
    assert argv[argv.index("--cidfile") + 1] == str(tmp_path / "cid")
    assert f"LD_LIBRARY_PATH={runner._CONTAINER_HUNSPELL_LIB}" in argv
    assert argv[-4:] == [
        runner._CONTAINER_HUNSPELL_BIN,
        "-d",
        f"/bundle/{runner._FIXTURE_BASE}",
        mode,
    ]


def test_reduce_candidate_clean_returns_record():
    record = runner._reduce_candidate(_phase_a_bounded_run())
    assert record.raw_stdout == b"out\n"
    assert record.stdout_bytes == 4
    assert record.latency_ms == 3


@pytest.mark.parametrize(
    "overrides",
    [
        {"terminal_state": runner.STATE_TIMEOUT, "timed_out": True},
        {"terminal_state": runner.STATE_OUTPUT_OVERFLOW, "stdout_limit_exceeded": True},
        {"terminal_state": runner.STATE_WORKER_FAILURE, "worker_failed": True},
        {"returncode": 7},
        {"cleanup_required": True, "cleanup_confirmed": False},
        {"stdin_delivered": False},
    ],
)
def test_reduce_candidate_fails_closed(overrides):
    with pytest.raises(runner.ParityHarnessError):
        runner._reduce_candidate(_phase_a_bounded_run(**overrides))


# ---------------------------------------------------------------------------
# Phase A -- supervised Docker pull and build (Docker stubbed via a fake runner).
# ---------------------------------------------------------------------------
def test_docker_pull_argv_is_pinned_and_quiet():
    argv = runner._docker_pull_argv()
    assert argv[:2] == ["docker", "pull"]
    assert "--quiet" in argv
    assert argv[argv.index("--platform") + 1] == "linux/arm64"
    assert runner.CONTAINER_REFERENCE in argv


def test_build_container_argv_is_hardened_with_cidfile(tmp_path):
    argv = runner._build_container_argv(
        tmp_path / "src", tmp_path / "install", tmp_path / "cid"
    )
    assert argv[argv.index("--cidfile") + 1] == str(tmp_path / "cid")
    assert argv[argv.index("--network") + 1] == "none"
    assert "--read-only" in argv
    assert argv[argv.index("--cap-drop") + 1] == "ALL"
    assert argv[argv.index("--security-opt") + 1] == "no-new-privileges"
    assert any(value.startswith("/tmp:rw,") for value in argv)
    assert runner.CONTAINER_REFERENCE in argv
    assert "test -x /install/bin/hunspell" in argv[-1]


def test_verify_identities_supervises_pull(tmp_path):
    captured: list[tuple] = []

    def fake_runner(argv, **kwargs):
        captured.append((list(argv), kwargs))
        return _phase_a_bounded_run()

    env = runner._LivePhaseAEnvironment(
        source_acquirer=lambda _p: None,
        source_extractor=lambda _a, _d: tmp_path / "source",
        runner=fake_runner,
    )
    env.verify_identities()
    pull_argv, pull_kwargs = captured[-1]
    assert pull_argv[:2] == ["docker", "pull"]
    assert pull_kwargs["timeout_seconds"] == runner._DOCKER_PULL_TIMEOUT_SECONDS
    assert env.evidence().environment_identity_match is True
    env.teardown()


@pytest.mark.parametrize(
    "bad",
    [
        {"terminal_state": runner.STATE_TIMEOUT, "timed_out": True},
        {"returncode": 1},
    ],
)
def test_pull_failure_fails_closed(tmp_path, bad):
    env = runner._LivePhaseAEnvironment(
        source_acquirer=lambda _p: None,
        source_extractor=lambda _a, _d: tmp_path / "source",
        runner=lambda argv, **kwargs: _phase_a_bounded_run(**bad),
    )
    with pytest.raises(runner.ParityHarnessError):
        env.verify_identities()
    workspace_path = env._workspace.name  # created before the pull failed
    env.teardown()  # attempted once whenever workspace creation succeeded
    assert not Path(workspace_path).exists()


def _prepared_build_env(tmp_path, fake_runner):
    env = runner._LivePhaseAEnvironment(runner=fake_runner)
    env._workspace = types.SimpleNamespace(name=str(tmp_path))
    env._source_verified = True
    env._container_verified = True
    env._source_dir = tmp_path / "source"
    return env


def test_build_supervises_container_with_cidfile_and_cleanup(tmp_path):
    captured: list[tuple] = []

    def fake_runner(argv, **kwargs):
        captured.append((list(argv), kwargs))
        installed = tmp_path / "install" / "bin"
        installed.mkdir(parents=True, exist_ok=True)
        (installed / "hunspell").write_bytes(b"")
        return _phase_a_bounded_run()

    env = _prepared_build_env(tmp_path, fake_runner)
    env.build()
    build_argv, build_kwargs = captured[-1]
    assert "--cidfile" in build_argv
    assert build_kwargs["timeout_seconds"] == runner._DOCKER_BUILD_TIMEOUT_SECONDS
    assert callable(build_kwargs["cleanup"])
    assert env.evidence().offline_build is True


@pytest.mark.parametrize(
    "bad",
    [
        {"terminal_state": runner.STATE_TIMEOUT, "timed_out": True},
        {"returncode": 2},
        {"terminal_state": runner.STATE_OUTPUT_OVERFLOW, "stdout_limit_exceeded": True},
        {"terminal_state": runner.STATE_WORKER_FAILURE, "worker_failed": True},
        {"cleanup_required": True, "cleanup_confirmed": False},
    ],
)
def test_build_failure_modes_fail_closed(tmp_path, bad):
    env = _prepared_build_env(tmp_path, lambda argv, **kwargs: _phase_a_bounded_run(**bad))
    with pytest.raises(runner.ParityHarnessError):
        env.build()


def test_build_missing_installed_binary_fails_closed(tmp_path):
    env = _prepared_build_env(tmp_path, lambda argv, **kwargs: _phase_a_bounded_run())
    with pytest.raises(runner.ParityHarnessError):
        env.build()


# ---------------------------------------------------------------------------
# Phase A -- evidence derivation, teardown, and hardened extraction.
# ---------------------------------------------------------------------------
def test_live_environment_evidence_is_derived():
    env = runner._LivePhaseAEnvironment()
    assert env.evidence() == runner._PhaseAEvidence(False, False)
    env._source_verified = True
    env._container_verified = True
    assert env.evidence() == runner._PhaseAEvidence(True, False)
    env._build_verified = True
    assert env.evidence() == runner._PhaseAEvidence(True, True)


def test_teardown_removes_workspace(tmp_path):
    import tempfile as _tempfile

    env = runner._LivePhaseAEnvironment()
    workspace = _tempfile.TemporaryDirectory()
    env._workspace = workspace
    root = Path(workspace.name)
    (root / "leftover").write_bytes(b"x")
    env.teardown()
    assert not root.exists()


def test_teardown_failure_is_fixed_error():
    class _BadWorkspace:
        name = "/nonexistent/whatever"

        def cleanup(self):
            raise OSError("private cleanup detail")

    env = runner._LivePhaseAEnvironment()
    env._workspace = _BadWorkspace()
    with pytest.raises(runner.ParityHarnessError) as excinfo:
        env.teardown()
    assert "private" not in str(excinfo.value)


def test_teardown_is_attempted_at_most_once():
    import tempfile as _tempfile

    env = runner._LivePhaseAEnvironment()
    env._workspace = _tempfile.TemporaryDirectory()
    env.teardown()
    env.teardown()  # second call is a no-op; must not raise


def test_extract_source_rejects_unsafe_member(tmp_path):
    archive = tmp_path / "bad.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        payload = b"x"
        info = tarfile.TarInfo("../escape")
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))
    with pytest.raises(runner.ParityHarnessError):
        runner._extract_source(archive, tmp_path / "dest")
    assert not (tmp_path / "escape").exists()


def test_extract_source_requires_configure(tmp_path):
    archive = tmp_path / "src.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        payload = b"readme\n"
        info = tarfile.TarInfo("hunspell-1.7.3/README")
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))
    with pytest.raises(runner.ParityHarnessError):
        runner._extract_source(archive, tmp_path / "dest")


# ---------------------------------------------------------------------------
# Phase A -- enabled-gate opt-in behaviour and boundary symbols.
# ---------------------------------------------------------------------------
def test_opt_in_enabled_gate_aborts_closed_without_reaching_real_seams(monkeypatch, capsys):
    env = _FakeEnvironment(raise_at="build")
    monkeypatch.setattr(runner, "_LivePhaseAEnvironment", lambda *a, **k: env)

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("real Phase A seam must not run in tests")

    monkeypatch.setattr(runner, "_acquire_public_pinned_source", _fail_if_called)
    monkeypatch.setattr(runner, "run_bounded", _fail_if_called)
    # The injected fake fails at the build stage; main() converts that into a fixed,
    # non-sensitive abort without reaching any real acquisition/transport seam.
    assert runner.main(["--allow-phase-a-run"]) == runner.EXIT_OPERATIONAL_ABORT
    captured = capsys.readouterr()
    assert captured.err == runner._ABORT_MESSAGE + "\n"
    assert captured.out == ""
    assert (env.verified, env.built, env.teardowns) == (True, False, 1)


def test_default_cli_refusal_performs_no_live_work(monkeypatch, capsys):
    calls: list[str] = []
    monkeypatch.setattr(
        runner, "_acquire_public_pinned_source", lambda _p: calls.append("acquire")
    )
    monkeypatch.setattr(runner, "_execute_phase_a", lambda *a, **k: calls.append("exec"))
    monkeypatch.setattr(
        runner, "_execute_phase_b", lambda *a, **k: calls.append("phase_b")
    )
    assert runner.main([]) == runner.EXIT_OPT_IN_REQUIRED
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == runner._OPT_IN_MESSAGE + "\n"
    assert calls == []


def test_phase_b_parser_exists_without_live_or_autoselection_symbols():
    assert callable(runner.parse_pipe_stream_response)
    assert callable(runner.parse_single_token_list_response)
    assert callable(runner.assess_phase_b_candidate)
    for absent in ("run_phase_b", "select_mode", "select_candidate"):
        assert not hasattr(runner, absent)
    assert runner.SELECTED_MODE_ENUM == ("PIPE_STREAM", "SINGLE_TOKEN_LIST", "NONE")


# ---------------------------------------------------------------------------
# Phase B -- pure offline parsing and aggregate assessment (invented data only).
# ---------------------------------------------------------------------------
def _pipe_response(*records: bytes) -> bytes:
    return runner.PHASE_B_PIPE_HEADING + b"".join(
        record + b"\n\n" for record in records
    )


def _phase_b_fixture_repetition(label, fixture, *, rejected=True, **overrides):
    if label == "PIPE_STREAM":
        records = [b"*"] * len(fixture.query_tokens)
        if rejected:
            records[-1] = b"# synqzzz 0"
        streams = (_pipe_response(*records),)
    else:
        streams = tuple(
            b"" if truth else token.encode("utf-8") + b"\n"
            for token, truth in zip(
                fixture.query_tokens, fixture.known_truth, strict=True
            )
        )
        if not rejected:
            streams = tuple(b"" for _token in fixture.query_tokens)
    return _repetition(
        streams,
        max_stdout_bytes=overrides.get(
            "max_stdout_bytes", max((len(stream) for stream in streams), default=0)
        ),
        max_stderr_bytes=overrides.get("max_stderr_bytes", 0),
        max_latency_ms=overrides.get("max_latency_ms", 1),
        cleanup_confirmed=overrides.get("cleanup_confirmed", True),
    )


class _FakePhaseBEnvironment:
    """Invented-only Phase B environment; performs no external operation."""

    def __init__(self, *, raise_at=None, evidence=None):
        self.raise_at = raise_at
        self._evidence = evidence or runner._PhaseAEvidence(True, True)
        self.calls: list[tuple[str, int]] = []
        self.verified = False
        self.built = False
        self.teardowns = 0

    def verify_identities(self):
        if self.raise_at == "verify":
            raise runner.ParityHarnessError("fixed fake failure")
        self.verified = True

    def build(self):
        if self.raise_at == "build":
            raise runner.ParityHarnessError("fixed fake failure")
        self.built = True

    def run_candidate(self, label, fixture, run_index):
        self.calls.append((label, run_index))
        if self.raise_at == "run":
            raise runner.ParityHarnessError("fixed fake failure")
        return _phase_b_fixture_repetition(label, fixture)

    def evidence(self):
        return self._evidence

    def teardown(self):
        self.teardowns += 1


def test_phase_b_orchestration_uses_two_repetitions_and_aggregate_only():
    env = _FakePhaseBEnvironment()
    summary = runner._run_phase_b(env)
    assert env.verified is True
    assert env.built is True
    assert env.calls == [
        ("PIPE_STREAM", 0),
        ("PIPE_STREAM", 1),
        ("SINGLE_TOKEN_LIST", 0),
        ("SINGLE_TOKEN_LIST", 1),
    ]
    assert tuple(summary) == runner.PHASE_B_SUMMARY_KEYS
    assert summary["passing_candidate_count"] == 2
    assert summary["selected_mode_label"] == "NONE"
    assert summary["environment_identity_match"] is True
    assert summary["offline_build"] is True
    serialized = json.dumps(summary)
    assert all(token not in serialized for token in runner.build_invented_fixture().query_tokens)


@pytest.mark.parametrize("stage", ["verify", "build", "run"])
def test_phase_b_orchestration_fails_closed_and_tears_down_once(stage):
    env = _FakePhaseBEnvironment(raise_at=stage)
    with pytest.raises(runner.ParityHarnessError):
        runner._run_phase_b_with_teardown(env)
    assert env.teardowns == 1


@pytest.mark.parametrize(
    "evidence",
    [
        runner._PhaseAEvidence(False, True),
        runner._PhaseAEvidence(True, False),
    ],
)
def test_phase_b_orchestration_rejects_unconfirmed_environment_evidence(evidence):
    env = _FakePhaseBEnvironment(evidence=evidence)
    with pytest.raises(runner.ParityHarnessError) as excinfo:
        runner._run_phase_b_with_teardown(env)
    assert str(excinfo.value) == "Phase B environment evidence was not confirmed"
    assert env.teardowns == 1


def test_enabled_phase_b_cli_uses_only_injected_invented_environment(
    monkeypatch, capsys
):
    env = _FakePhaseBEnvironment()
    assert runner._LIVE_PHASE_B_ENABLED is True
    monkeypatch.setattr(runner, "_LivePhaseBEnvironment", lambda *a, **k: env)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("real acquisition and transport must remain offline")

    monkeypatch.setattr(runner, "_acquire_public_pinned_source", fail_if_called)
    monkeypatch.setattr(runner, "run_bounded", fail_if_called)
    assert runner.main(["--allow-phase-b-run"]) == runner.EXIT_SUCCESS
    captured = capsys.readouterr()
    assert captured.err == ""
    summary = json.loads(captured.out)
    assert summary["passing_candidate_count"] == 2
    assert summary["selected_mode_label"] == "NONE"
    assert env.teardowns == 1


@pytest.mark.parametrize(
    ("record", "membership"),
    [
        (b"*", "ACCEPTED"),
        (b"+ inventedroot", "ACCEPTED"),
        (b"- inventedroot", "ACCEPTED"),
        (b"& invented 2 0: optionone, option two", "REJECTED"),
        (b"# invented 0", "REJECTED"),
    ],
)
def test_pipe_parser_maps_every_approved_marker(record, membership):
    result = runner.parse_pipe_stream_response(
        _pipe_response(record), ("invented",)
    )
    assert result == (runner.MembershipResult(0, membership),)


def test_pipe_parser_preserves_fixture_order_cardinality_and_duplicate_ordinals():
    fixture = runner.build_invented_fixture()
    records = [b"*"] * (len(fixture.query_tokens) - 1) + [b"# synqzzz 0"]
    results = runner.parse_pipe_stream_response(
        _pipe_response(*records), fixture.query_tokens
    )
    assert tuple(result.ordinal for result in results) == tuple(
        range(len(fixture.query_tokens))
    )
    assert results[0].membership == results[8].membership == "ACCEPTED"
    assert results[-1].membership == "REJECTED"


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"wrong heading\n*\n\n",
        runner.PHASE_B_PIPE_HEADING + b"*\n",
        runner.PHASE_B_PIPE_HEADING + b"*\n\nextra",
        runner.PHASE_B_PIPE_HEADING + b"?\n\n",
        runner.PHASE_B_PIPE_HEADING + b"+ \n\n",
        runner.PHASE_B_PIPE_HEADING + b"- root extra\n\n",
        runner.PHASE_B_PIPE_HEADING + b"# invented x\n\n",
        runner.PHASE_B_PIPE_HEADING + b"# transformed 0\n\n",
        runner.PHASE_B_PIPE_HEADING + b"& invented 2 0: onlyone\n\n",
        runner.PHASE_B_PIPE_HEADING + b"& invented 0 0: option\n\n",
        runner.PHASE_B_PIPE_HEADING + b"\xff\n\n",
    ],
)
def test_pipe_parser_fails_closed_on_malformed_or_unexpected_stream(raw):
    with pytest.raises(runner.PhaseBParseError) as excinfo:
        runner.parse_pipe_stream_response(raw, ("invented",))
    assert str(excinfo.value) == runner._PHASE_B_FAILURE_MESSAGE


def test_pipe_parser_rejects_reordered_echoes_and_extra_records():
    with pytest.raises(runner.PhaseBParseError):
        runner.parse_pipe_stream_response(
            _pipe_response(b"# second 0", b"# first 0"), ("first", "second")
        )
    with pytest.raises(runner.PhaseBParseError):
        runner.parse_pipe_stream_response(
            _pipe_response(b"*", b"*"), ("invented",)
        )


def test_single_token_list_parser_maps_silence_and_exact_echo():
    assert runner.parse_single_token_list_response(
        b"", "invented", ordinal=4
    ) == runner.MembershipResult(4, "ACCEPTED")
    assert runner.parse_single_token_list_response(
        b"invented\n", "invented", ordinal=4
    ) == runner.MembershipResult(4, "REJECTED")


@pytest.mark.parametrize(
    "raw",
    [b"\n", b"invented", b"invented\n\n", b"other\n", b"\xff\n"],
)
def test_single_token_list_parser_fails_closed_on_every_other_shape(raw):
    with pytest.raises(runner.PhaseBParseError) as excinfo:
        runner.parse_single_token_list_response(raw, "invented", ordinal=0)
    assert str(excinfo.value) == runner._PHASE_B_FAILURE_MESSAGE


def test_phase_b_stdin_is_exact_and_remains_separate_from_live_phase_a_stdin():
    assert runner._phase_b_stdin("PIPE_STREAM", ("one", "two")) == b"^one\n^two\n"
    assert runner._phase_b_stdin("SINGLE_TOKEN_LIST", ("one",)) == b"one\n"
    assert runner._phase_a_batch_stdin(("one", "two")) == b"one\ntwo\n"
    with pytest.raises(runner.ParityInputError):
        runner._phase_b_stdin("SINGLE_TOKEN_LIST", ("one", "two"))


def test_phase_b_fixed_error_never_contains_internal_protocol_material():
    private_fragments = ("invented", "rootvalue", "suggestionvalue", "?")
    raw = _pipe_response(b"& invented 1 0: suggestionvalue", b"? rootvalue")
    with pytest.raises(runner.PhaseBParseError) as excinfo:
        runner.parse_pipe_stream_response(raw, ("invented", "rootvalue"))
    message = str(excinfo.value)
    assert message == runner._PHASE_B_FAILURE_MESSAGE
    assert all(fragment not in message for fragment in private_fragments)


@pytest.mark.parametrize("label", runner.CANDIDATE_LABELS)
def test_phase_b_candidate_assessment_passes_known_invented_truth(label):
    fixture = runner.build_invented_fixture()
    repetition = _phase_b_fixture_repetition(label, fixture)
    assessment = runner.assess_phase_b_candidate(
        label, repetition, repetition, fixture
    )
    assert tuple(assessment.to_dict()) == runner.PHASE_B_CANDIDATE_ASSESSMENT_KEYS
    assert assessment.invented_case_count == 10
    assert assessment.expected_membership_match_count == 10
    assert assessment.exact_cardinality is True
    assert assessment.repetitions_identical is True
    assert assessment.unknown_response_count == 0
    assert assessment.cleanup_confirmed is True
    assert assessment.candidate_passed is True


def test_phase_b_candidate_assessment_does_not_pass_wrong_truth_or_instability():
    fixture = runner.build_invented_fixture()
    correct = _phase_b_fixture_repetition("PIPE_STREAM", fixture)
    wrong = _phase_b_fixture_repetition("PIPE_STREAM", fixture, rejected=False)
    assessment = runner.assess_phase_b_candidate(
        "PIPE_STREAM", wrong, wrong, fixture
    )
    assert assessment.expected_membership_match_count == 9
    assert assessment.candidate_passed is False
    unstable = runner.assess_phase_b_candidate(
        "PIPE_STREAM", correct, wrong, fixture
    )
    assert unstable.repetitions_identical is False
    assert unstable.candidate_passed is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"max_stdout_bytes": runner.MAX_STDOUT_BYTES + 1},
        {"max_stdout_bytes": 0},
        {"max_stderr_bytes": 1},
        {"max_stderr_bytes": -1},
        {"max_latency_ms": runner.BATCH_TIMEOUT_SECONDS * 1000 + 1},
        {"max_latency_ms": -1},
        {"cleanup_confirmed": False},
    ],
)
def test_phase_b_assessment_fails_closed_when_retained_limits_fail(overrides):
    fixture = runner.build_invented_fixture()
    repetition = _phase_b_fixture_repetition(
        "PIPE_STREAM", fixture, **overrides
    )
    with pytest.raises(runner.PhaseBParseError) as excinfo:
        runner.assess_phase_b_candidate(
            "PIPE_STREAM", repetition, repetition, fixture
        )
    assert str(excinfo.value) == runner._PHASE_B_FAILURE_MESSAGE


def _phase_b_assessment(passed):
    return runner.PhaseBCandidateAssessment(
        candidate_attempted=True,
        candidate_completed=True,
        invented_case_count=10,
        expected_membership_match_count=10 if passed else 9,
        exact_cardinality=True,
        repetitions_identical=True,
        unknown_response_count=0,
        cleanup_confirmed=True,
        candidate_passed=passed,
    )


@pytest.mark.parametrize("passing_labels", [(), ("PIPE_STREAM",), runner.CANDIDATE_LABELS])
def test_phase_b_summary_never_automatically_selects(passing_labels):
    assessments = {
        label: _phase_b_assessment(label in passing_labels)
        for label in runner.CANDIDATE_LABELS
    }
    summary = runner.build_phase_b_summary(
        assessments,
        environment_identity_match=True,
        offline_build=True,
    )
    assert tuple(summary) == runner.PHASE_B_SUMMARY_KEYS
    assert summary["environment_identity_match"] is True
    assert summary["offline_build"] is True
    assert summary["passing_candidate_count"] == len(passing_labels)
    assert summary["selected_mode_label"] == "NONE"
    assert summary["no_real_resource_or_corpus_access"] is True
    serialized = json.dumps(summary)
    assert all(
        fragment not in serialized
        for fragment in ("synbase", "synqzzz", "rootvalue", "suggestionvalue")
    )


# ---------------------------------------------------------------------------
# Phase A -- per-process boundaries are preserved (no concatenation before counting).
# ---------------------------------------------------------------------------
def test_observe_repetitions_counts_per_process_not_concatenated():
    # process 1 has no trailing newline; process 2 opens with a boundary blank line.
    rep = _repetition((b"a", b"\nb\n"))
    obs = runner._observe_repetitions(rep, rep)
    # per-process (1,0,0,1)+(3,2,1,1) -> a boundary blank that concatenation would hide
    assert obs.total_bytes == 4
    assert obs.total_lf_count == 2
    assert obs.blank_line_count == 1  # concatenation of b"a\nb\n" would yield 0
    assert obs.nonempty_line_count == 2


def test_no_trailing_newline_processes_stay_separate():
    split = _repetition((b"ab", b"cd"))
    joined = _repetition((b"abcd",))
    assert runner._observe_repetitions(split, split).nonempty_line_count == 2
    assert runner._observe_repetitions(joined, joined).nonempty_line_count == 1


def test_equal_concatenation_different_partitions_not_identical():
    split = _repetition((b"ab", b"cd"))
    joined = _repetition((b"abcd",))  # equal concatenated bytes, different partition
    obs = runner._observe_repetitions(split, joined)
    assert obs.raw_stream_identical_across_runs is False
    assert obs.structural_summary_stable is False


def test_reordered_per_process_outputs_are_detected():
    forward = _repetition((b"aa\n", b"b\n"))
    reordered = _repetition((b"b\n", b"aa\n"))
    obs = runner._observe_repetitions(forward, reordered)
    assert obs.raw_stream_identical_across_runs is False
    assert obs.structural_summary_stable is False


def test_repetition_observation_exposes_no_framing_meaning():
    obs = runner._observe_repetitions(_repetition((b"x\n",)), _repetition((b"x\n",)))
    for forbidden in (
        "candidate_passed",
        "response_segment_count",
        "known_truth_partition_consistent",
        "marker",
    ):
        assert not hasattr(obs, forbidden)


# ---------------------------------------------------------------------------
# Phase A -- control timeouts match the tracked precedent.
# ---------------------------------------------------------------------------
def test_control_timeouts_match_tracked_precedent():
    assert runner._DOCKER_PULL_TIMEOUT_SECONDS == 300
    assert runner._DOCKER_BUILD_TIMEOUT_SECONDS == 300
    assert runner.BATCH_TIMEOUT_SECONDS == 30


def _prepared_run_env(tmp_path, fake_runner):
    env = runner._LivePhaseAEnvironment(runner=fake_runner)
    env._workspace = types.SimpleNamespace(name=str(tmp_path))
    env._source_verified = True
    env._container_verified = True
    env._build_verified = True
    env._source_dir = tmp_path / "source"
    env._install_dir = tmp_path / "install"
    return env


def test_candidate_process_uses_batch_timeout(tmp_path):
    captured: list[dict] = []

    def fake_runner(argv, **kwargs):
        captured.append(kwargs)
        return _phase_a_bounded_run(stdout=b"x\n", stdout_bytes=2)

    env = _prepared_run_env(tmp_path, fake_runner)
    env.run_candidate("PIPE_STREAM", runner.build_invented_fixture(), 0)
    assert captured[0]["timeout_seconds"] == 30
    assert captured[0]["timeout_seconds"] == runner.BATCH_TIMEOUT_SECONDS


# ---------------------------------------------------------------------------
# Phase A -- temporary local-operation failures become fixed, path-free errors.
# ---------------------------------------------------------------------------
def test_workspace_creation_failure_is_fixed_error(monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("private tmp detail")

    monkeypatch.setattr(runner.tempfile, "TemporaryDirectory", boom)
    env = runner._LivePhaseAEnvironment(
        source_acquirer=lambda _p: None,
        source_extractor=lambda _a, _d: None,
        runner=lambda *a, **k: _phase_a_bounded_run(),
    )
    with pytest.raises(runner.ParityHarnessError) as excinfo:
        env.verify_identities()
    assert "private" not in str(excinfo.value)


def test_archive_write_failure_is_fixed_error(monkeypatch):
    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return b"data"

    monkeypatch.setattr(runner.urllib.request, "urlopen", lambda *a, **k: _Response())
    monkeypatch.setattr(
        runner.hashlib,
        "sha256",
        lambda data: types.SimpleNamespace(
            hexdigest=lambda: runner.HUNSPELL_ARCHIVE_SHA256
        ),
    )

    class _UnwritablePath:
        def write_bytes(self, data):
            raise OSError("private write detail")

    with pytest.raises(runner.ParityHarnessError) as excinfo:
        runner._acquire_public_pinned_source(_UnwritablePath())
    assert "private" not in str(excinfo.value)


def test_install_dir_creation_failure_is_fixed_error(tmp_path):
    (tmp_path / "install").mkdir()  # pre-exists so mkdir() fails
    env = _prepared_build_env(tmp_path, lambda *a, **k: _phase_a_bounded_run())
    with pytest.raises(runner.ParityHarnessError) as excinfo:
        env.build()
    assert str(tmp_path) not in str(excinfo.value)


def test_fixture_directory_creation_failure_is_fixed_error(tmp_path):
    env = _prepared_run_env(tmp_path, lambda *a, **k: _phase_a_bounded_run())
    (tmp_path / "fixture_PIPE_STREAM_0").mkdir()  # pre-exists so mkdir() fails
    with pytest.raises(runner.ParityHarnessError) as excinfo:
        env.run_candidate("PIPE_STREAM", runner.build_invented_fixture(), 0)
    assert str(tmp_path) not in str(excinfo.value)


def test_fixture_write_failure_is_fixed_error(tmp_path, monkeypatch):
    env = _prepared_run_env(tmp_path, lambda *a, **k: _phase_a_bounded_run())

    def boom(self, data):
        raise OSError("private write detail")

    monkeypatch.setattr(runner.Path, "write_bytes", boom)
    with pytest.raises(runner.ParityHarnessError) as excinfo:
        env.run_candidate("PIPE_STREAM", runner.build_invented_fixture(), 0)
    assert "private" not in str(excinfo.value)
