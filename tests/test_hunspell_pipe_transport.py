"""Synthetic tests for the concrete bounded container PIPE_STREAM transport.

Only invented bytes, injected fakes, and temporary directories are used.  No test runs
Docker, Hunspell, a real subprocess, or the network, and none touches RLA-ES, CALLHOME,
Bangor, an ignored resource, a private bundle, or a private log.  Container identifiers
here are invented placeholders.

Cancellation assertions inspect object identity, type, the fixed status attribute, and
frame *names* only; no traceback is logged, serialized, exported, or formatted with
captured locals.
"""

from __future__ import annotations

import inspect
import os
import stat
import threading
import traceback
from pathlib import Path, PurePosixPath

import pytest

from cslm.data import hunspell_container as cont
from cslm.data import hunspell_pipe_stream as h
from cslm.data import hunspell_pipe_transport as tr
from cslm.data import hunspell_process_supervision as sup
from cslm.data.hunspell_pipe_transport import HunspellContainerPipeTransport
from cslm.data.spanish_hunspell_pipe_checker import SpanishHunspellPipeChecker

_LIMITS = {
    "timeout_seconds": h.BATCH_TIMEOUT_SECONDS,
    "max_stdout_bytes": h.MAX_STDOUT_BYTES,
    "max_stderr_bytes": h.MAX_STDERR_BYTES,
    "grace_seconds": h.TERMINATION_GRACE_SECONDS,
}
_STDIN = b"^syna\n^synb\n"
_INVENTED_CONTAINER_ID = "cabc"


def _bounded_run(**overrides):
    base = {
        "returncode": 0,
        "terminal_state": sup.STATE_NORMAL_EXIT,
        "forced_termination": False,
        "stdin_delivered": True,
        "stdout": b"OUT",
        "stderr": b"",
        "stdout_bytes": 3,
        "stderr_bytes": 0,
        "stdout_limit_exceeded": False,
        "stderr_limit_exceeded": False,
        "timed_out": False,
        "worker_failed": False,
        "workers_joined": True,
        "cleanup_required": True,
        "cleanup_confirmed": True,
        "latency_ms": 1,
    }
    base.update(overrides)
    return sup.BoundedRun(**base)


def _runtime(tmp_path):
    """Build an invented, structurally valid runtime layout (no lexical content)."""
    root = tmp_path.resolve()
    bundle = root / "bundle"
    install = root / "install"
    workspace = root / "workspace"
    bundle.mkdir()
    (install / "bin").mkdir(parents=True)
    (install / "lib").mkdir()
    binary = install / "bin" / "hunspell"
    binary.write_text("#!/bin/sh\n", encoding="ascii")
    binary.chmod(0o700)
    workspace.mkdir()
    return bundle, install, workspace


_UNSET = object()  # lets a test pass an explicit ``None`` result to the transport


class _FakeRunner:
    """Mimics the observable ``run_bounded`` contract without launching anything."""

    def __init__(
        self,
        *,
        result=_UNSET,
        raises=None,
        clean_exit=True,
        write_cidfile=True,
        before_cleanup=None,
        call_cleanup=True,
    ):
        self.result = result
        self.raises = raises
        self.clean_exit = clean_exit
        self.write_cidfile = write_cidfile
        self.before_cleanup = before_cleanup
        self.call_cleanup = call_cleanup
        self.calls: list[dict] = []
        self.cleanup_confirmed = True

    def __call__(
        self,
        argv,
        *,
        stdin_bytes,
        timeout_seconds,
        max_stdout_bytes,
        max_stderr_bytes,
        grace_seconds,
        cleanup,
    ):
        cidfile = Path(argv[argv.index("--cidfile") + 1])
        self.calls.append(
            {
                "argv": list(argv),
                "stdin_bytes": stdin_bytes,
                "timeout_seconds": timeout_seconds,
                "max_stdout_bytes": max_stdout_bytes,
                "max_stderr_bytes": max_stderr_bytes,
                "grace_seconds": grace_seconds,
                "control_dir": cidfile.parent,
                "cidfile": cidfile,
            }
        )
        if self.write_cidfile:
            cidfile.write_text(_INVENTED_CONTAINER_ID + "\n", encoding="ascii")
        if self.before_cleanup is not None:
            self.before_cleanup(cidfile.parent)
        if self.call_cleanup:
            try:
                cleanup(self.clean_exit)
            except Exception:  # mirrors the supervisor's ``except Exception`` guard
                self.cleanup_confirmed = False
        if self.raises is not None:
            raise self.raises
        if self.result is not _UNSET:
            return self.result
        return _bounded_run(cleanup_confirmed=self.cleanup_confirmed)


def _transport(tmp_path, **overrides):
    bundle, install, workspace = _runtime(tmp_path)
    kwargs = {
        "bundle_dir": bundle,
        "install_dir": install,
        "workspace_dir": workspace,
        "process_runner": _FakeRunner(),
    }
    kwargs.update(overrides)
    return HunspellContainerPipeTransport(**kwargs), kwargs


def _fixed_dir_factory(target: Path):
    def factory(parent: Path) -> Path:
        return target

    return factory


# ---------------------------------------------------------------------------
# Protocol conformance and dependency injection.
# ---------------------------------------------------------------------------
def test_structurally_conforms_to_the_pipe_stream_protocol(tmp_path):
    transport, _ = _transport(tmp_path)
    assert callable(transport.run_pipe_batch)
    parameters = inspect.signature(transport.run_pipe_batch).parameters
    assert list(parameters) == [
        "stdin_bytes",
        "timeout_seconds",
        "max_stdout_bytes",
        "max_stderr_bytes",
        "grace_seconds",
    ]
    assert SpanishHunspellPipeChecker(transport) is not None


def test_dependencies_are_explicit_constructor_arguments(tmp_path):
    parameters = inspect.signature(HunspellContainerPipeTransport.__init__).parameters
    assert parameters["process_runner"].default is sup.run_bounded
    assert parameters["container_remover"].default is tr.USE_CHECKED_DEFAULT_REMOVER
    assert parameters["control_directory_factory"].default is tr.create_unique_control_directory
    transport, _ = _transport(tmp_path)
    assert repr(transport) == "HunspellContainerPipeTransport(...)"
    assert not any("count" in name for name in vars(transport))


def test_module_has_no_mutable_global_seams_or_leaky_imports():
    source = Path(tr.__file__).read_text(encoding="utf-8")
    for forbidden in ("_RUN_BOUNDED", "_DOCKER_REMOVE =", "run_hunspell_per_token_parity"):
        assert forbidden not in source
    for module in ("logging", "json", "traceback", "pickle", "urllib", "socket"):
        assert not hasattr(tr, module)
    for later_phase in ("spanish_hunspell_coverage", "conditions", "condition_manifest"):
        assert later_phase not in source


def test_invalid_dependencies_fail_closed(tmp_path):
    bundle, install, workspace = _runtime(tmp_path)
    for bad in ({"process_runner": object()}, {"control_directory_factory": object()}):
        with pytest.raises(h.ParityInputError):
            HunspellContainerPipeTransport(
                bundle_dir=bundle, install_dir=install, workspace_dir=workspace, **bad
            )
    with pytest.raises(h.ParityInputError):
        HunspellContainerPipeTransport(
            bundle_dir=bundle,
            install_dir=install,
            workspace_dir=workspace,
            container_remover=object(),
        )


# ---------------------------------------------------------------------------
# Exact defensive-limit equality.
# ---------------------------------------------------------------------------
def test_exact_limits_are_accepted_and_forwarded(tmp_path):
    runner = _FakeRunner()
    transport, _ = _transport(tmp_path, process_runner=runner)
    assert transport.run_pipe_batch(_STDIN, **_LIMITS) == b"OUT"
    call = runner.calls[0]
    assert {key: call[key] for key in _LIMITS} == _LIMITS


@pytest.mark.parametrize(
    "override",
    [
        {"timeout_seconds": h.BATCH_TIMEOUT_SECONDS - 1},
        {"timeout_seconds": h.BATCH_TIMEOUT_SECONDS + 1},
        {"timeout_seconds": True},
        {"timeout_seconds": "30"},
        {"timeout_seconds": float("inf")},
        {"timeout_seconds": float("nan")},
        {"max_stdout_bytes": h.MAX_STDOUT_BYTES - 1},
        {"max_stdout_bytes": h.MAX_STDOUT_BYTES + 1},
        {"max_stdout_bytes": True},
        {"max_stdout_bytes": float(h.MAX_STDOUT_BYTES)},
        {"max_stderr_bytes": h.MAX_STDERR_BYTES - 1},
        {"max_stderr_bytes": h.MAX_STDERR_BYTES + 1},
        {"max_stderr_bytes": True},
        {"grace_seconds": 0.5},
        {"grace_seconds": 2.0},
        {"grace_seconds": True},
        {"grace_seconds": None},
    ],
)
def test_every_limit_mismatch_fails_closed_before_launch(tmp_path, override):
    runner = _FakeRunner()
    transport, _ = _transport(tmp_path, process_runner=runner)
    limits = dict(_LIMITS)
    limits.update(override)
    with pytest.raises(h.ParityTransportError) as excinfo:
        transport.run_pipe_batch(_STDIN, **limits)
    assert str(excinfo.value) == h.PIPE_STREAM_TRANSPORT_FAILURE_MESSAGE
    assert excinfo.value.__cause__ is None
    assert runner.calls == []


# ---------------------------------------------------------------------------
# Stdin boundary.
# ---------------------------------------------------------------------------
def test_stdin_bytes_reach_the_runner_unchanged(tmp_path):
    runner = _FakeRunner()
    transport, _ = _transport(tmp_path, process_runner=runner)
    transport.run_pipe_batch(_STDIN, **_LIMITS)
    assert runner.calls[0]["stdin_bytes"] == _STDIN
    assert type(runner.calls[0]["stdin_bytes"]) is bytes


@pytest.mark.parametrize(
    "payload",
    [bytearray(b"^syna\n"), memoryview(b"^syna\n"), "^syna\n", None],
)
def test_non_bytes_stdin_fails_closed(tmp_path, payload):
    runner = _FakeRunner()
    transport, _ = _transport(tmp_path, process_runner=runner)
    with pytest.raises(h.ParityTransportError):
        transport.run_pipe_batch(payload, **_LIMITS)
    assert runner.calls == []


def test_oversized_stdin_fails_closed_without_inspecting_tokens(tmp_path):
    runner = _FakeRunner()
    transport, _ = _transport(tmp_path, process_runner=runner)
    payload = b"x" * (tr.MAX_PIPE_STREAM_STDIN_BYTES + 1)
    with pytest.raises(h.ParityTransportError):
        transport.run_pipe_batch(payload, **_LIMITS)
    assert runner.calls == []
    assert tr.MAX_PIPE_STREAM_STDIN_BYTES == h.MAX_TOKENS_PER_BATCH * (
        1 + h.MAX_TOKEN_BYTES + 1
    )


# ---------------------------------------------------------------------------
# Runtime path validation and mount-character scoping.
# ---------------------------------------------------------------------------
def test_path_types_and_shapes_are_validated(tmp_path):
    bundle, install, workspace = _runtime(tmp_path)
    bad_values = [
        str(bundle),
        PurePosixPath("/absent/bundle"),
        tmp_path / "missing",
        install / "bin" / "hunspell",  # a file, not a directory
    ]
    for bad in bad_values:
        with pytest.raises(h.ParityInputError):
            HunspellContainerPipeTransport(
                bundle_dir=bad, install_dir=install, workspace_dir=workspace
            )


def test_symlinked_and_traversal_paths_are_rejected(tmp_path):
    bundle, install, workspace = _runtime(tmp_path)
    link = tmp_path.resolve() / "bundle-link"
    link.symlink_to(bundle, target_is_directory=True)
    with pytest.raises(h.ParityInputError):
        HunspellContainerPipeTransport(
            bundle_dir=link, install_dir=install, workspace_dir=workspace
        )
    with pytest.raises(h.ParityInputError):
        HunspellContainerPipeTransport(
            bundle_dir=bundle.parent / "bundle" / ".." / "bundle",
            install_dir=install,
            workspace_dir=workspace,
        )


def test_incomplete_installation_is_rejected(tmp_path):
    bundle, install, workspace = _runtime(tmp_path)
    (install / "bin" / "hunspell").chmod(0o600)  # not executable
    with pytest.raises(h.ParityInputError):
        HunspellContainerPipeTransport(
            bundle_dir=bundle, install_dir=install, workspace_dir=workspace
        )


def test_spaces_are_accepted_in_mounted_paths(tmp_path):
    root = tmp_path.resolve() / "with space"
    root.mkdir()
    bundle, install, workspace = _runtime(root)
    runner = _FakeRunner()
    transport = HunspellContainerPipeTransport(
        bundle_dir=bundle,
        install_dir=install,
        workspace_dir=workspace,
        process_runner=runner,
    )
    assert transport.run_pipe_batch(_STDIN, **_LIMITS) == b"OUT"


def test_mount_delimiter_characters_are_rejected_only_for_mounted_paths(tmp_path):
    root = tmp_path.resolve()
    comma_dir = root / "bun,dle"
    comma_dir.mkdir()
    _, install, workspace = _runtime(root)
    with pytest.raises(h.ParityInputError):
        HunspellContainerPipeTransport(
            bundle_dir=comma_dir, install_dir=install, workspace_dir=workspace
        )
    comma_workspace = root / "work,space"
    comma_workspace.mkdir()
    bundle = root / "bundle"
    HunspellContainerPipeTransport(
        bundle_dir=bundle, install_dir=install, workspace_dir=comma_workspace
    )  # a workspace is not a Docker mount value


def test_equals_sign_is_accepted_in_a_mounted_path(tmp_path):
    root = tmp_path.resolve()
    equals_dir = root / "bun=dle"
    equals_dir.mkdir()
    _, install, workspace = _runtime(root)
    HunspellContainerPipeTransport(
        bundle_dir=equals_dir, install_dir=install, workspace_dir=workspace
    )


# ---------------------------------------------------------------------------
# Container argument vector.
# ---------------------------------------------------------------------------
def test_argv_is_hardened_pinned_and_carries_no_token(tmp_path):
    runner = _FakeRunner()
    transport, kwargs = _transport(tmp_path, process_runner=runner)
    transport.run_pipe_batch(b"^synsecret\n", **_LIMITS)
    argv = runner.calls[0]["argv"]
    assert argv[:4] == ["docker", "run", "--rm", "--interactive"]
    assert argv.count("--interactive") == 1
    assert argv[argv.index("--network") + 1] == "none"
    assert "--read-only" in argv
    assert argv[argv.index("--cap-drop") + 1] == "ALL"
    assert argv[argv.index("--security-opt") + 1] == "no-new-privileges"
    assert cont.CONTAINER_REFERENCE in argv
    assert "LD_LIBRARY_PATH=/opt/hunspell/lib" in argv
    assert "-w" not in argv and "--workdir" not in argv and "-t" not in argv
    assert argv[-4:] == ["/opt/hunspell/bin/hunspell", "-d", "/bundle/es", "-a"]
    assert not any("synsecret" in part for part in argv)
    assert str(kwargs["bundle_dir"]) in argv[argv.index("--mount") + 1]


def test_one_container_invocation_per_batch(tmp_path):
    runner = _FakeRunner()
    transport, _ = _transport(tmp_path, process_runner=runner)
    transport.run_pipe_batch(_STDIN, **_LIMITS)
    transport.run_pipe_batch(_STDIN, **_LIMITS)
    assert len(runner.calls) == 2
    assert runner.calls[0]["control_dir"] != runner.calls[1]["control_dir"]


# ---------------------------------------------------------------------------
# Control directory: production factory, validation, and lease.
# ---------------------------------------------------------------------------
def test_production_factory_creates_unique_private_children(tmp_path):
    workspace = tmp_path.resolve()
    first = tr.create_unique_control_directory(workspace)
    second = tr.create_unique_control_directory(workspace)
    assert first != second
    for created in (first, second):
        assert created.parent == workspace
        assert stat.S_IMODE(os.stat(created).st_mode) == tr.CONTROL_DIRECTORY_MODE
        assert not any(created.iterdir())


def test_control_directory_is_removed_only_after_confirmed_cleanup(tmp_path):
    runner = _FakeRunner()
    transport, kwargs = _transport(tmp_path, process_runner=runner)
    assert transport.run_pipe_batch(_STDIN, **_LIMITS) == b"OUT"
    control_dir = runner.calls[0]["control_dir"]
    assert not control_dir.exists()
    assert not any(kwargs["workspace_dir"].iterdir())


def test_marker_flags_mode_and_name_are_fixed(tmp_path):
    assert tr.CONTROL_OWNER_MARKER_NAME == ".pipe-stream-owner"
    assert tr.CONTROL_CIDFILE_NAME == "container.cid"
    assert tr.CONTROL_MARKER_MODE == 0o600
    flags = tr._marker_flags()
    assert flags & os.O_CREAT and flags & os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        assert flags & os.O_NOFOLLOW

    seen: dict[str, object] = {}

    def observe(control_dir: Path) -> None:
        marker = control_dir / tr.CONTROL_OWNER_MARKER_NAME
        info = os.lstat(marker)
        seen["mode"] = stat.S_IMODE(info.st_mode)
        seen["regular"] = stat.S_ISREG(info.st_mode)
        seen["size"] = info.st_size
        seen["cidfile_absent_at_build"] = True

    transport, _ = _transport(
        tmp_path, process_runner=_FakeRunner(before_cleanup=observe, write_cidfile=False)
    )
    transport.run_pipe_batch(_STDIN, **_LIMITS)
    assert seen == {
        "mode": 0o600,
        "regular": True,
        "size": 0,
        "cidfile_absent_at_build": True,
    }


def test_cidfile_is_not_pre_created_before_launch(tmp_path):
    observed: list[bool] = []

    class _Checking(_FakeRunner):
        def __call__(self, argv, **kwargs):
            cidfile = Path(argv[argv.index("--cidfile") + 1])
            observed.append(cidfile.exists())
            return super().__call__(argv, **kwargs)

    transport, _ = _transport(tmp_path, process_runner=_Checking())
    transport.run_pipe_batch(_STDIN, **_LIMITS)
    assert observed == [False]


@pytest.mark.parametrize("factory_result", ["string", PurePosixPath("/tmp"), 7, None])
def test_defective_factory_result_types_fail_closed(tmp_path, factory_result):
    runner = _FakeRunner()
    transport, _ = _transport(
        tmp_path,
        process_runner=runner,
        control_directory_factory=lambda parent: factory_result,
    )
    with pytest.raises(h.ParityTransportError):
        transport.run_pipe_batch(_STDIN, **_LIMITS)
    assert runner.calls == []


def test_defective_factory_locations_and_states_fail_closed(tmp_path):
    bundle, install, workspace = _runtime(tmp_path)
    outside = tmp_path.resolve() / "outside"
    outside.mkdir(mode=0o700)
    grandchild = workspace / "child" / "grandchild"
    grandchild.mkdir(mode=0o700, parents=True)
    nonempty = workspace / "nonempty"
    nonempty.mkdir(mode=0o700)
    (nonempty / "leftover").write_text("x", encoding="ascii")
    loose = workspace / "loose"
    loose.mkdir(mode=0o755)
    with_cidfile = workspace / "withcid"
    with_cidfile.mkdir(mode=0o700)
    (with_cidfile / tr.CONTROL_CIDFILE_NAME).write_text("cid", encoding="ascii")
    link_target = workspace / "target"
    link_target.mkdir(mode=0o700)
    symlinked = workspace / "linked"
    symlinked.symlink_to(link_target, target_is_directory=True)
    missing = workspace / "missing"

    for candidate in (
        workspace,
        outside,
        grandchild,
        nonempty,
        loose,
        with_cidfile,
        symlinked,
        missing,
    ):
        runner = _FakeRunner()
        transport = HunspellContainerPipeTransport(
            bundle_dir=bundle,
            install_dir=install,
            workspace_dir=workspace,
            process_runner=runner,
            control_directory_factory=_fixed_dir_factory(candidate),
        )
        with pytest.raises(h.ParityTransportError):
            transport.run_pipe_batch(_STDIN, **_LIMITS)
        assert runner.calls == []


def test_prior_batch_marker_prevents_reuse_without_deleting_it(tmp_path):
    bundle, install, workspace = _runtime(tmp_path)
    stale = workspace / "stale"
    stale.mkdir(mode=0o700)
    marker = stale / tr.CONTROL_OWNER_MARKER_NAME
    marker.write_text("", encoding="ascii")
    runner = _FakeRunner()
    transport = HunspellContainerPipeTransport(
        bundle_dir=bundle,
        install_dir=install,
        workspace_dir=workspace,
        process_runner=runner,
        control_directory_factory=_fixed_dir_factory(stale),
    )
    with pytest.raises(h.ParityTransportError):
        transport.run_pipe_batch(_STDIN, **_LIMITS)
    assert runner.calls == []
    assert marker.exists()  # a foreign claim is never deleted


def test_symlinked_marker_is_rejected(tmp_path):
    bundle, install, workspace = _runtime(tmp_path)
    control = workspace / "control"
    control.mkdir(mode=0o700)
    victim = tmp_path.resolve() / "victim"
    victim.write_text("", encoding="ascii")
    (control / tr.CONTROL_OWNER_MARKER_NAME).symlink_to(victim)
    runner = _FakeRunner()
    transport = HunspellContainerPipeTransport(
        bundle_dir=bundle,
        install_dir=install,
        workspace_dir=workspace,
        process_runner=runner,
        control_directory_factory=_fixed_dir_factory(control),
    )
    with pytest.raises(h.ParityTransportError):
        transport.run_pipe_batch(_STDIN, **_LIMITS)
    assert runner.calls == []
    assert victim.exists()


def test_empty_markerless_directory_is_an_injected_factory_trust_case(tmp_path):
    """A bare ``Path`` cannot prove creation history; only observables are enforced."""
    bundle, install, workspace = _runtime(tmp_path)
    prior = workspace / "prior"
    prior.mkdir(mode=0o700)
    runner = _FakeRunner()
    transport = HunspellContainerPipeTransport(
        bundle_dir=bundle,
        install_dir=install,
        workspace_dir=workspace,
        process_runner=runner,
        control_directory_factory=_fixed_dir_factory(prior),
    )
    assert transport.run_pipe_batch(_STDIN, **_LIMITS) == b"OUT"
    assert len(runner.calls) == 1  # indistinguishable from a fresh directory


def test_two_synchronized_claims_on_one_directory_have_exactly_one_winner(tmp_path):
    bundle, install, workspace = _runtime(tmp_path)
    shared = workspace / "shared"
    shared.mkdir(mode=0o700)
    barrier = threading.Barrier(2)

    def factory(parent: Path) -> Path:
        barrier.wait(timeout=5)
        return shared

    outcomes: list[str] = []
    lock = threading.Lock()

    def attempt() -> None:
        transport = HunspellContainerPipeTransport(
            bundle_dir=bundle,
            install_dir=install,
            workspace_dir=workspace,
            process_runner=_FakeRunner(),
            control_directory_factory=factory,
        )
        try:
            transport.run_pipe_batch(_STDIN, **_LIMITS)
        except h.ParityTransportError:
            with lock:
                outcomes.append("refused")
        else:
            with lock:
                outcomes.append("owned")

    threads = [threading.Thread(target=attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)
    assert sorted(outcomes) == ["owned", "refused"]


# ---------------------------------------------------------------------------
# Lease identity revalidation and release failures.
# ---------------------------------------------------------------------------
def test_marker_identity_mismatch_prevents_unlink_and_rmdir(tmp_path):
    def substitute(control_dir: Path) -> None:
        marker = control_dir / tr.CONTROL_OWNER_MARKER_NAME
        marker.unlink()
        marker.write_text("", encoding="ascii")  # same name, different inode

    runner = _FakeRunner(before_cleanup=substitute)
    transport, _ = _transport(tmp_path, process_runner=runner)
    with pytest.raises(h.ParityTransportError) as excinfo:
        transport.run_pipe_batch(_STDIN, **_LIMITS)
    assert str(excinfo.value) == h.PIPE_STREAM_TRANSPORT_FAILURE_MESSAGE
    control_dir = runner.calls[0]["control_dir"]
    assert control_dir.is_dir()
    assert (control_dir / tr.CONTROL_OWNER_MARKER_NAME).exists()


def test_directory_removal_failure_restores_the_marker_and_fails_closed(tmp_path):
    def litter(control_dir: Path) -> None:
        (control_dir / "leftover").write_text("x", encoding="ascii")

    runner = _FakeRunner(before_cleanup=litter)
    transport, _ = _transport(tmp_path, process_runner=runner)
    with pytest.raises(h.ParityTransportError):
        transport.run_pipe_batch(_STDIN, **_LIMITS)
    control_dir = runner.calls[0]["control_dir"]
    assert control_dir.is_dir()
    assert (control_dir / "leftover").exists()
    assert (control_dir / tr.CONTROL_OWNER_MARKER_NAME).exists()  # claim retained


def test_marker_restoration_never_overwrites_another_owner(tmp_path):
    control = tmp_path.resolve() / "control"
    control.mkdir(mode=0o700)
    marker = control / tr.CONTROL_OWNER_MARKER_NAME
    marker.write_text("", encoding="ascii")
    before = os.lstat(marker).st_ino
    tr._restore_marker(control)
    assert os.lstat(marker).st_ino == before


def test_marker_restoration_is_silent_when_the_directory_is_absent(tmp_path):
    tr._restore_marker(tmp_path.resolve() / "absent")  # must not raise


@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0, reason="root ignores mode bits"
)
def test_marker_restoration_failure_is_silent(tmp_path):
    control = tmp_path.resolve() / "control"
    control.mkdir(mode=0o700)
    control.chmod(0o500)
    try:
        tr._restore_marker(control)  # must not raise
        assert not (control / tr.CONTROL_OWNER_MARKER_NAME).exists()
    finally:
        control.chmod(0o700)


def test_close_helper_swallows_an_invalid_descriptor():
    tr._close_quietly(-1)


# ---------------------------------------------------------------------------
# Cleanup evidence: no fallback unlink, no second remover.
# ---------------------------------------------------------------------------
def test_unconfirmed_cleanup_preserves_the_cidfile_marker_and_directory(tmp_path):
    calls: list[str] = []

    def failing_remover(container_id: str) -> None:
        calls.append(container_id)
        raise h.ParityTransportError("private removal detail")

    runner = _FakeRunner(clean_exit=False)
    transport, _ = _transport(
        tmp_path, process_runner=runner, container_remover=failing_remover
    )
    with pytest.raises(h.ParityTransportError) as excinfo:
        transport.run_pipe_batch(_STDIN, **_LIMITS)
    assert str(excinfo.value) == h.PIPE_STREAM_TRANSPORT_FAILURE_MESSAGE
    assert "private" not in str(excinfo.value)
    control_dir = runner.calls[0]["control_dir"]
    assert (control_dir / tr.CONTROL_CIDFILE_NAME).exists()  # no fallback unlink
    assert (control_dir / tr.CONTROL_OWNER_MARKER_NAME).exists()
    assert control_dir.is_dir()
    assert calls == [_INVENTED_CONTAINER_ID]  # exactly one remover invocation


def test_clean_exit_never_invokes_the_remover(tmp_path):
    calls: list[str] = []
    runner = _FakeRunner(clean_exit=True)
    transport, _ = _transport(tmp_path, process_runner=runner, container_remover=calls.append)
    assert transport.run_pipe_batch(_STDIN, **_LIMITS) == b"OUT"
    assert calls == []


# ---------------------------------------------------------------------------
# BoundedRun reduction.
# ---------------------------------------------------------------------------
def test_clean_success_returns_exact_stdout(tmp_path):
    transport, _ = _transport(
        tmp_path, process_runner=_FakeRunner(result=_bounded_run(stdout=b"xy", stdout_bytes=2))
    )
    assert transport.run_pipe_batch(_STDIN, **_LIMITS) == b"xy"


def test_clean_empty_stdout_is_returned_unchanged(tmp_path):
    transport, _ = _transport(
        tmp_path, process_runner=_FakeRunner(result=_bounded_run(stdout=b"", stdout_bytes=0))
    )
    assert transport.run_pipe_batch(_STDIN, **_LIMITS) == b""


@pytest.mark.parametrize(
    "override",
    [
        {"returncode": 1},
        {"returncode": None},
        {"terminal_state": sup.STATE_TIMEOUT},
        {"terminal_state": sup.STATE_OUTPUT_OVERFLOW},
        {"terminal_state": sup.STATE_WORKER_FAILURE},
        {"forced_termination": True},
        {"stdin_delivered": False},
        {"stdout": "OUT"},
        {"stdout": bytearray(b"OUT")},
        {"stderr": b"boom", "stderr_bytes": 4},
        {"stderr": b"boom"},
        {"stderr_bytes": 1},
        {"stdout_bytes": 2},
        {"stdout_limit_exceeded": True},
        {"stderr_limit_exceeded": True},
        {"timed_out": True},
        {"worker_failed": True},
        {"workers_joined": False},
        {"cleanup_required": False},
        {"cleanup_confirmed": False},
        {"latency_ms": -1},
        {"latency_ms": True},
        {"latency_ms": 1.5},
    ],
)
def test_every_bounded_run_violation_fails_closed(tmp_path, override):
    runner = _FakeRunner(result=_bounded_run(**override))
    transport, _ = _transport(tmp_path, process_runner=runner)
    with pytest.raises(h.ParityTransportError) as excinfo:
        transport.run_pipe_batch(_STDIN, **_LIMITS)
    assert str(excinfo.value) == h.PIPE_STREAM_TRANSPORT_FAILURE_MESSAGE
    assert excinfo.value.__cause__ is None
    control_dir = runner.calls[0]["control_dir"]
    assert control_dir.is_dir()  # evidence preserved on failure


@pytest.mark.parametrize("value", ["not-a-run", None, 7, object()])
def test_malformed_runner_return_fails_closed(tmp_path, value):
    transport, _ = _transport(tmp_path, process_runner=_FakeRunner(result=value))
    with pytest.raises(h.ParityTransportError):
        transport.run_pipe_batch(_STDIN, **_LIMITS)


# ---------------------------------------------------------------------------
# Ordinary runner errors.
# ---------------------------------------------------------------------------
_SECRET = "SENSITIVE-synLEAK-9999"


@pytest.mark.parametrize(
    "error",
    [
        h.ParityTransportError("bounded process supervision failed " + _SECRET),
        RuntimeError(_SECRET),
        ValueError(_SECRET),
        OSError(_SECRET),
    ],
)
def test_ordinary_runner_errors_collapse_to_the_fixed_failure(tmp_path, error):
    transport, _ = _transport(tmp_path, process_runner=_FakeRunner(raises=error))
    with pytest.raises(h.ParityTransportError) as excinfo:
        transport.run_pipe_batch(_STDIN, **_LIMITS)
    assert str(excinfo.value) == h.PIPE_STREAM_TRANSPORT_FAILURE_MESSAGE
    assert _SECRET not in str(excinfo.value)
    assert excinfo.value.__cause__ is None


# ---------------------------------------------------------------------------
# Cancellation precedence, identity, and fixed status.
# ---------------------------------------------------------------------------
def _cancelling_remover(cancellation: BaseException):
    def remover(container_id: str) -> None:
        raise cancellation

    return remover


@pytest.mark.parametrize("cancellation", [KeyboardInterrupt(), SystemExit(3)])
def test_original_cancellation_with_confirmed_cleanup_removes_the_directory(
    tmp_path, cancellation
):
    runner = _FakeRunner(raises=cancellation)
    transport, _ = _transport(tmp_path, process_runner=runner)
    with pytest.raises(type(cancellation)) as excinfo:
        transport.run_pipe_batch(_STDIN, **_LIMITS)
    assert excinfo.value is cancellation
    assert cancellation.pipe_stream_cleanup_status == tr.PIPE_STREAM_CLEANUP_CONFIRMED
    assert not runner.calls[0]["control_dir"].exists()


def test_original_cancellation_with_unconfirmed_cleanup_preserves_evidence(tmp_path):
    cancellation = KeyboardInterrupt()
    runner = _FakeRunner(raises=cancellation, clean_exit=False)

    def failing_remover(container_id: str) -> None:
        raise h.ParityTransportError("private removal detail")

    transport, _ = _transport(
        tmp_path, process_runner=runner, container_remover=failing_remover
    )
    with pytest.raises(KeyboardInterrupt) as excinfo:
        transport.run_pipe_batch(_STDIN, **_LIMITS)
    assert excinfo.value is cancellation
    assert cancellation.pipe_stream_cleanup_status == tr.PIPE_STREAM_CLEANUP_UNCONFIRMED
    control_dir = runner.calls[0]["control_dir"]
    assert control_dir.is_dir()
    assert (control_dir / tr.CONTROL_CIDFILE_NAME).exists()
    assert (control_dir / tr.CONTROL_OWNER_MARKER_NAME).exists()


def test_original_cancellation_with_rmdir_failure_reports_unconfirmed(tmp_path):
    cancellation = KeyboardInterrupt()

    def litter(control_dir: Path) -> None:
        (control_dir / "leftover").write_text("x", encoding="ascii")

    runner = _FakeRunner(raises=cancellation, before_cleanup=litter)
    transport, _ = _transport(tmp_path, process_runner=runner)
    with pytest.raises(KeyboardInterrupt) as excinfo:
        transport.run_pipe_batch(_STDIN, **_LIMITS)
    assert excinfo.value is cancellation
    assert cancellation.pipe_stream_cleanup_status == tr.PIPE_STREAM_CLEANUP_UNCONFIRMED
    control_dir = runner.calls[0]["control_dir"]
    assert control_dir.is_dir()
    assert (control_dir / tr.CONTROL_OWNER_MARKER_NAME).exists()


@pytest.mark.parametrize("cancellation", [KeyboardInterrupt(), SystemExit(4)])
def test_cleanup_time_cancellation_wins_when_the_runner_returns(tmp_path, cancellation):
    runner = _FakeRunner(clean_exit=False)
    transport, _ = _transport(
        tmp_path,
        process_runner=runner,
        container_remover=_cancelling_remover(cancellation),
    )
    with pytest.raises(type(cancellation)) as excinfo:
        transport.run_pipe_batch(_STDIN, **_LIMITS)
    assert excinfo.value is cancellation
    assert cancellation.pipe_stream_cleanup_status == tr.PIPE_STREAM_CLEANUP_UNCONFIRMED
    assert excinfo.value.__cause__ is None
    assert excinfo.value.__context__ is None
    control_dir = runner.calls[0]["control_dir"]
    assert (control_dir / tr.CONTROL_CIDFILE_NAME).exists()
    assert (control_dir / tr.CONTROL_OWNER_MARKER_NAME).exists()


def test_stored_cleanup_cancellation_outranks_an_ordinary_runner_error(tmp_path):
    cancellation = KeyboardInterrupt()
    runner = _FakeRunner(clean_exit=False, raises=RuntimeError(_SECRET))
    transport, _ = _transport(
        tmp_path,
        process_runner=runner,
        container_remover=_cancelling_remover(cancellation),
    )
    with pytest.raises(KeyboardInterrupt) as excinfo:
        transport.run_pipe_batch(_STDIN, **_LIMITS)
    assert excinfo.value is cancellation
    assert excinfo.value.__cause__ is None
    assert excinfo.value.__context__ is None
    assert _SECRET not in str(excinfo.value)
    assert cancellation.pipe_stream_cleanup_status == tr.PIPE_STREAM_CLEANUP_UNCONFIRMED
    control_dir = runner.calls[0]["control_dir"]
    assert (control_dir / tr.CONTROL_CIDFILE_NAME).exists()


def test_original_runner_cancellation_beats_a_later_cleanup_cancellation(tmp_path):
    original = KeyboardInterrupt()
    later = KeyboardInterrupt()
    runner = _FakeRunner(clean_exit=False, raises=original)
    transport, _ = _transport(
        tmp_path, process_runner=runner, container_remover=_cancelling_remover(later)
    )
    with pytest.raises(KeyboardInterrupt) as excinfo:
        transport.run_pipe_batch(_STDIN, **_LIMITS)
    assert excinfo.value is original
    assert excinfo.value is not later
    assert original.pipe_stream_cleanup_status == tr.PIPE_STREAM_CLEANUP_UNCONFIRMED
    assert not hasattr(later, "pipe_stream_cleanup_status")


def test_cancellation_traceback_frames_are_preserved(tmp_path):
    cancellation = KeyboardInterrupt()
    runner = _FakeRunner(clean_exit=False)
    transport, _ = _transport(
        tmp_path,
        process_runner=runner,
        container_remover=_cancelling_remover(cancellation),
    )
    with pytest.raises(KeyboardInterrupt) as excinfo:
        transport.run_pipe_batch(_STDIN, **_LIMITS)
    # Frame names only: no locals are formatted, logged, serialized, or exported.
    names = [frame.name for frame in traceback.extract_tb(excinfo.value.__traceback__)]
    assert "remover" in names
    assert "finalize_container" in names


# ---------------------------------------------------------------------------
# Pre-runner cancellations carry an explicit status.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("cancellation", [KeyboardInterrupt(), SystemExit(5)])
def test_factory_cancellation_reports_not_attempted(tmp_path, cancellation):
    def cancelling_factory(parent: Path) -> Path:
        raise cancellation

    runner = _FakeRunner()
    transport, _ = _transport(
        tmp_path, process_runner=runner, control_directory_factory=cancelling_factory
    )
    with pytest.raises(type(cancellation)) as excinfo:
        transport.run_pipe_batch(_STDIN, **_LIMITS)
    assert excinfo.value is cancellation
    assert cancellation.pipe_stream_cleanup_status == tr.PIPE_STREAM_CLEANUP_NOT_ATTEMPTED
    assert runner.calls == []


@pytest.mark.parametrize("cancellation", [KeyboardInterrupt(), SystemExit(6)])
def test_validation_cancellation_after_creation_reports_unconfirmed(tmp_path, cancellation):
    bundle, install, workspace = _runtime(tmp_path)
    control = workspace / "control"
    control.mkdir(mode=0o700)

    class _CancellingPath(type(control)):
        """A returned path whose first inspection is interrupted."""

        def is_absolute(self):
            raise cancellation

    runner = _FakeRunner()
    transport = HunspellContainerPipeTransport(
        bundle_dir=bundle,
        install_dir=install,
        workspace_dir=workspace,
        process_runner=runner,
        control_directory_factory=lambda parent: _CancellingPath(control),
    )
    with pytest.raises(type(cancellation)) as excinfo:
        transport.run_pipe_batch(_STDIN, **_LIMITS)
    assert excinfo.value is cancellation
    assert cancellation.pipe_stream_cleanup_status == tr.PIPE_STREAM_CLEANUP_UNCONFIRMED
    assert control.is_dir()  # the created directory is preserved
    assert runner.calls == []


def test_lease_cancellation_reports_unconfirmed_and_preserves_artifacts(tmp_path):
    cancellation = KeyboardInterrupt()
    bundle, install, workspace = _runtime(tmp_path)
    control = workspace / "control"
    control.mkdir(mode=0o700)

    class _CancellingParent(type(control)):
        """Interrupts after validation, at lease-path construction."""

        def __truediv__(self, other):
            if other == tr.CONTROL_OWNER_MARKER_NAME:
                raise cancellation
            return super().__truediv__(other)

    runner = _FakeRunner()
    transport = HunspellContainerPipeTransport(
        bundle_dir=bundle,
        install_dir=install,
        workspace_dir=workspace,
        process_runner=runner,
        control_directory_factory=lambda parent: _CancellingParent(control),
    )
    with pytest.raises(KeyboardInterrupt) as excinfo:
        transport.run_pipe_batch(_STDIN, **_LIMITS)
    assert excinfo.value is cancellation
    assert cancellation.pipe_stream_cleanup_status == tr.PIPE_STREAM_CLEANUP_UNCONFIRMED
    assert control.is_dir()
    assert runner.calls == []


@pytest.mark.parametrize("cancellation", [KeyboardInterrupt(), SystemExit(11)])
def test_argv_construction_cancellation_reports_unconfirmed(
    tmp_path, monkeypatch, cancellation
):
    bundle, install, workspace = _runtime(tmp_path)
    control = workspace / "control"
    control.mkdir(mode=0o700)
    removers: list[str] = []

    def cancelling_argv(**kwargs):
        raise cancellation

    monkeypatch.setattr(tr, "pipe_stream_container_argv", cancelling_argv)
    runner = _FakeRunner()
    transport = HunspellContainerPipeTransport(
        bundle_dir=bundle,
        install_dir=install,
        workspace_dir=workspace,
        process_runner=runner,
        container_remover=removers.append,
        control_directory_factory=_fixed_dir_factory(control),
    )
    with pytest.raises(type(cancellation)) as excinfo:
        transport.run_pipe_batch(_STDIN, **_LIMITS)

    assert excinfo.value is cancellation
    assert type(excinfo.value) is type(cancellation)
    assert not isinstance(excinfo.value, h.ParityTransportError)
    assert cancellation.pipe_stream_cleanup_status == tr.PIPE_STREAM_CLEANUP_UNCONFIRMED
    names = [frame.name for frame in traceback.extract_tb(excinfo.value.__traceback__)]
    assert "cancelling_argv" in names  # original traceback frames retained
    assert control.is_dir()
    assert (control / tr.CONTROL_OWNER_MARKER_NAME).exists()  # lease intact
    assert not (control / tr.CONTROL_CIDFILE_NAME).exists()  # no cidfile created
    assert runner.calls == []  # nothing launched
    assert removers == []  # no container-removal attempt


def test_pre_runner_cancellations_are_never_converted(tmp_path):
    cancellation = KeyboardInterrupt()

    def cancelling_factory(parent: Path) -> Path:
        raise cancellation

    transport, _ = _transport(tmp_path, control_directory_factory=cancelling_factory)
    with pytest.raises(KeyboardInterrupt) as excinfo:
        transport.run_pipe_batch(_STDIN, **_LIMITS)
    assert not isinstance(excinfo.value, h.ParityTransportError)
    assert excinfo.value.__traceback__ is not None
    names = [frame.name for frame in traceback.extract_tb(excinfo.value.__traceback__)]
    assert "cancelling_factory" in names


# ---------------------------------------------------------------------------
# Cancellation during lease-marker deletion.
# ---------------------------------------------------------------------------
def test_marker_deletion_cancellation_restores_the_claim_and_preserves_evidence(
    tmp_path, monkeypatch
):
    cancellation = KeyboardInterrupt()
    real_unlink = os.unlink
    seen: list[str] = []

    def cancelling_unlink(path, *args, **kwargs):
        if str(path).endswith(tr.CONTROL_OWNER_MARKER_NAME):
            seen.append("marker")
            raise cancellation
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(tr.os, "unlink", cancelling_unlink)
    runner = _FakeRunner()
    transport, _ = _transport(tmp_path, process_runner=runner)
    with pytest.raises(KeyboardInterrupt) as excinfo:
        transport.run_pipe_batch(_STDIN, **_LIMITS)
    assert excinfo.value is cancellation
    assert cancellation.pipe_stream_cleanup_status == tr.PIPE_STREAM_CLEANUP_UNCONFIRMED
    control_dir = runner.calls[0]["control_dir"]
    assert control_dir.is_dir()  # no rmdir was attempted
    assert (control_dir / tr.CONTROL_OWNER_MARKER_NAME).exists()  # claim retained
    assert seen == ["marker"]  # exactly one deletion attempt, never retried


def test_original_cancellation_survives_a_marker_deletion_cancellation(
    tmp_path, monkeypatch
):
    original = SystemExit(7)
    later = KeyboardInterrupt()
    real_unlink = os.unlink

    def cancelling_unlink(path, *args, **kwargs):
        if str(path).endswith(tr.CONTROL_OWNER_MARKER_NAME):
            raise later
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(tr.os, "unlink", cancelling_unlink)
    runner = _FakeRunner(raises=original)
    transport, _ = _transport(tmp_path, process_runner=runner)
    with pytest.raises(SystemExit) as excinfo:
        transport.run_pipe_batch(_STDIN, **_LIMITS)
    assert excinfo.value is original
    assert original.pipe_stream_cleanup_status == tr.PIPE_STREAM_CLEANUP_UNCONFIRMED
    assert not hasattr(later, "pipe_stream_cleanup_status")
    control_dir = runner.calls[0]["control_dir"]
    assert (control_dir / tr.CONTROL_OWNER_MARKER_NAME).exists()


@pytest.mark.parametrize("cancellation", [KeyboardInterrupt(), SystemExit(8)])
def test_cancellation_after_a_completed_marker_unlink_restores_the_claim(
    tmp_path, monkeypatch, cancellation
):
    """The temporal case: deletion succeeds, then the interrupt arrives."""
    real_unlink = os.unlink
    real_open = os.open
    unlinks: list[str] = []
    restorations: list[str] = []
    rmdirs: list[str] = []
    removers: list[str] = []

    def unlink_then_cancel(path, *args, **kwargs):
        if str(path).endswith(tr.CONTROL_OWNER_MARKER_NAME):
            unlinks.append(str(path))
            real_unlink(path, *args, **kwargs)  # the deletion really completes
            raise cancellation
        return real_unlink(path, *args, **kwargs)

    def counting_open(path, *args, **kwargs):
        if str(path).endswith(tr.CONTROL_OWNER_MARKER_NAME) and unlinks:
            restorations.append(str(path))
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(tr.os, "unlink", unlink_then_cancel)
    monkeypatch.setattr(tr.os, "open", counting_open)
    monkeypatch.setattr(Path, "rmdir", lambda self: rmdirs.append(str(self)))

    runner = _FakeRunner()
    transport, _ = _transport(
        tmp_path, process_runner=runner, container_remover=removers.append
    )
    with pytest.raises(type(cancellation)) as excinfo:
        transport.run_pipe_batch(_STDIN, **_LIMITS)

    assert excinfo.value is cancellation
    assert type(excinfo.value) is type(cancellation)
    assert cancellation.pipe_stream_cleanup_status == tr.PIPE_STREAM_CLEANUP_UNCONFIRMED
    control_dir = runner.calls[0]["control_dir"]
    assert len(unlinks) == 1  # deletion attempted exactly once, never retried
    assert len(restorations) == 1  # exactly one O_CREAT|O_EXCL restoration attempt
    assert (control_dir / tr.CONTROL_OWNER_MARKER_NAME).exists()  # claim restored
    assert rmdirs == []  # rmdir never attempted
    assert not (control_dir / tr.CONTROL_CIDFILE_NAME).exists()  # never recreated
    assert removers == []  # no second container remover
    assert control_dir.is_dir()


def test_restoration_descriptor_close_cancellation_is_suppressed(tmp_path, monkeypatch):
    """A cancellation from the restoration close must never replace a winner."""
    control = tmp_path.resolve() / "control"
    control.mkdir(mode=0o700)

    def cancelling_close(descriptor):
        raise KeyboardInterrupt

    monkeypatch.setattr(tr.os, "close", cancelling_close)
    tr._restore_marker(control)  # must not raise
    assert (control / tr.CONTROL_OWNER_MARKER_NAME).exists()


def test_lease_close_helper_still_propagates_cancellation(monkeypatch):
    """``_close_quietly`` must stay narrow so setup cancellations still surface."""

    def cancelling_close(descriptor):
        raise KeyboardInterrupt

    monkeypatch.setattr(tr.os, "close", cancelling_close)
    with pytest.raises(KeyboardInterrupt):
        tr._close_quietly(0)


def test_marker_deletion_cancellation_never_recreates_a_cidfile(tmp_path, monkeypatch):
    cancellation = KeyboardInterrupt()
    removers: list[str] = []
    real_unlink = os.unlink

    def cancelling_unlink(path, *args, **kwargs):
        if str(path).endswith(tr.CONTROL_OWNER_MARKER_NAME):
            raise cancellation
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(tr.os, "unlink", cancelling_unlink)
    runner = _FakeRunner()
    transport, _ = _transport(
        tmp_path, process_runner=runner, container_remover=removers.append
    )
    with pytest.raises(KeyboardInterrupt):
        transport.run_pipe_batch(_STDIN, **_LIMITS)
    control_dir = runner.calls[0]["control_dir"]
    assert not (control_dir / tr.CONTROL_CIDFILE_NAME).exists()  # not recreated
    assert removers == []  # no second container remover


# ---------------------------------------------------------------------------
# Cancellation raised by the control-directory removal itself.
# ---------------------------------------------------------------------------
def _cancelling_rmdir(cancellation: BaseException, workspace: Path, attempts: list[str]):
    """Patch ``Path.rmdir`` to cancel *before* a control directory is removed.

    Only directories inside the injected workspace are intercepted; every other
    removal still reaches the real implementation.
    """
    real_rmdir = Path.rmdir

    def cancelling_rmdir(self):
        if workspace in self.parents:
            attempts.append(str(self))
            raise cancellation  # the directory itself is left in place
        return real_rmdir(self)

    return cancelling_rmdir


def _recording_unlink(unlinks: list[str]):
    """Record every deletion so a retry or a fallback cidfile deletion would show."""
    real_unlink = os.unlink

    def recording_unlink(path, *args, **kwargs):
        unlinks.append(str(path))
        return real_unlink(path, *args, **kwargs)

    return recording_unlink


@pytest.mark.parametrize("cancellation", [KeyboardInterrupt(), SystemExit(11)])
def test_directory_removal_cancellation_wins_when_nothing_cancelled_earlier(
    tmp_path, monkeypatch, cancellation
):
    """``Path.rmdir()`` is itself interrupted, so it becomes the winning cancellation."""
    attempts: list[str] = []
    unlinks: list[str] = []
    removers: list[str] = []
    runner = _FakeRunner(clean_exit=False)
    transport, kwargs = _transport(
        tmp_path, process_runner=runner, container_remover=removers.append
    )
    monkeypatch.setattr(tr.os, "unlink", _recording_unlink(unlinks))
    monkeypatch.setattr(
        Path, "rmdir", _cancelling_rmdir(cancellation, kwargs["workspace_dir"], attempts)
    )

    with pytest.raises(type(cancellation)) as excinfo:
        transport.run_pipe_batch(_STDIN, **_LIMITS)

    control_dir = runner.calls[0]["control_dir"]
    marker = control_dir / tr.CONTROL_OWNER_MARKER_NAME
    cidfile = control_dir / tr.CONTROL_CIDFILE_NAME
    assert attempts == [str(control_dir)]  # reached exactly once, never retried
    assert excinfo.value is cancellation  # the same object crosses the boundary
    assert type(excinfo.value) is type(cancellation)
    assert not isinstance(excinfo.value, h.ParityTransportError)
    assert excinfo.value.__cause__ is None
    assert excinfo.value.__context__ is None
    # Frame names only: no locals are formatted, logged, serialized, or exported.
    names = [frame.name for frame in traceback.extract_tb(excinfo.value.__traceback__)]
    assert "cancelling_rmdir" in names  # the injected removal frame is retained
    assert cancellation.pipe_stream_cleanup_status == tr.PIPE_STREAM_CLEANUP_UNCONFIRMED
    assert cancellation.pipe_stream_cleanup_status == "UNCONFIRMED"
    # Cleanup deleted the cidfile once and the release deleted the marker once; nothing
    # else was unlinked, so there was no retry and no fallback cidfile deletion.
    assert unlinks == [str(cidfile), str(marker)]
    assert not cidfile.exists()  # never recreated
    assert removers == [_INVENTED_CONTAINER_ID]  # no second container-removal attempt
    assert control_dir.is_dir()  # preserved: the fake removed nothing
    assert marker.exists()  # the ownership claim was restored


@pytest.mark.parametrize(
    ("original_type", "later_type"),
    [
        (KeyboardInterrupt, KeyboardInterrupt),
        (KeyboardInterrupt, SystemExit),
        (SystemExit, KeyboardInterrupt),
        (SystemExit, SystemExit),
    ],
)
def test_original_runner_cancellation_outranks_a_directory_removal_cancellation(
    tmp_path, monkeypatch, original_type, later_type
):
    """A later ``Path.rmdir()`` cancellation never displaces the original winner."""
    original = original_type()
    later = later_type()
    attempts: list[str] = []
    unlinks: list[str] = []
    removers: list[str] = []
    runner = _FakeRunner(raises=original, clean_exit=False)
    transport, kwargs = _transport(
        tmp_path, process_runner=runner, container_remover=removers.append
    )
    monkeypatch.setattr(tr.os, "unlink", _recording_unlink(unlinks))
    monkeypatch.setattr(
        Path, "rmdir", _cancelling_rmdir(later, kwargs["workspace_dir"], attempts)
    )

    with pytest.raises(original_type) as excinfo:
        transport.run_pipe_batch(_STDIN, **_LIMITS)

    control_dir = runner.calls[0]["control_dir"]
    marker = control_dir / tr.CONTROL_OWNER_MARKER_NAME
    cidfile = control_dir / tr.CONTROL_CIDFILE_NAME
    assert attempts == [str(control_dir)]  # reached exactly once, never retried
    assert excinfo.value is original  # the exact original object survives
    assert excinfo.value is not later
    assert type(excinfo.value) is original_type
    assert not isinstance(excinfo.value, h.ParityTransportError)
    assert not isinstance(later, h.ParityTransportError)
    assert excinfo.value.__cause__ is None
    assert excinfo.value.__context__ is None  # never exposed through chaining
    names = [frame.name for frame in traceback.extract_tb(excinfo.value.__traceback__)]
    assert "__call__" in names  # the original runner frame is preserved
    assert "cancelling_rmdir" not in names  # the later frame never replaces it
    assert original.pipe_stream_cleanup_status == tr.PIPE_STREAM_CLEANUP_UNCONFIRMED
    assert original.pipe_stream_cleanup_status == "UNCONFIRMED"
    assert not hasattr(later, "pipe_stream_cleanup_status")
    assert unlinks == [str(cidfile), str(marker)]  # no retry, no fallback deletion
    assert not cidfile.exists()  # never recreated
    assert removers == [_INVENTED_CONTAINER_ID]  # no second container remover
    assert control_dir.is_dir()  # surviving evidence matches UNCONFIRMED
    assert marker.exists()
    assert sorted(entry.name for entry in control_dir.iterdir()) == [
        tr.CONTROL_OWNER_MARKER_NAME
    ]  # nothing was recursively deleted


# ---------------------------------------------------------------------------
# Strict integer fields.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("field", ["returncode", "stdout_bytes", "stderr_bytes", "latency_ms"])
@pytest.mark.parametrize("value", [False, True])
def test_boolean_counted_fields_are_rejected(tmp_path, field, value):
    runner = _FakeRunner(result=_bounded_run(**{field: value}))
    transport, _ = _transport(tmp_path, process_runner=runner)
    with pytest.raises(h.ParityTransportError) as excinfo:
        transport.run_pipe_batch(_STDIN, **_LIMITS)
    assert str(excinfo.value) == h.PIPE_STREAM_TRANSPORT_FAILURE_MESSAGE


@pytest.mark.parametrize(
    "field", ["returncode", "stdout_bytes", "stderr_bytes", "latency_ms"]
)
@pytest.mark.parametrize("value", [None, "0", 0.0, 1.5])
def test_non_integer_counted_fields_are_rejected(tmp_path, field, value):
    runner = _FakeRunner(result=_bounded_run(**{field: value}))
    transport, _ = _transport(tmp_path, process_runner=runner)
    with pytest.raises(h.ParityTransportError):
        transport.run_pipe_batch(_STDIN, **_LIMITS)


# ---------------------------------------------------------------------------
# Control-character and installation-shape completeness.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("code", [0x01, 0x1F, 0x7F, 0x80, 0x9F])
def test_all_control_characters_are_rejected_in_paths(code):
    assert tr._is_control_character(code)


@pytest.mark.parametrize("code", [0x20, 0x3D, 0x41, 0xA0, 0x2019])
def test_printable_characters_remain_accepted(code):
    assert not tr._is_control_character(code)


def test_c1_control_in_a_mounted_path_is_rejected(tmp_path):
    root = tmp_path.resolve()
    bundle, install, workspace = _runtime(root)
    exotic = root / "bundle"
    try:
        exotic.mkdir()
    except OSError:  # pragma: no cover - platform-dependent name support
        pytest.skip("platform rejects C1 characters in filenames")
    with pytest.raises(h.ParityInputError):
        HunspellContainerPipeTransport(
            bundle_dir=exotic, install_dir=install, workspace_dir=workspace
        )


def test_symlinked_installation_bin_parent_is_rejected(tmp_path):
    root = tmp_path.resolve()
    bundle, install, workspace = _runtime(root)
    elsewhere = root / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "hunspell").write_text("#!/bin/sh\n", encoding="ascii")
    (elsewhere / "hunspell").chmod(0o700)
    swapped = root / "swapped"
    (swapped / "lib").mkdir(parents=True)
    (swapped / "bin").symlink_to(elsewhere, target_is_directory=True)
    with pytest.raises(h.ParityInputError):
        HunspellContainerPipeTransport(
            bundle_dir=bundle, install_dir=swapped, workspace_dir=workspace
        )


def test_symlinked_installation_lib_is_rejected(tmp_path):
    root = tmp_path.resolve()
    bundle, install, workspace = _runtime(root)
    elsewhere = root / "libs"
    elsewhere.mkdir()
    swapped = root / "swapped2"
    (swapped / "bin").mkdir(parents=True)
    binary = swapped / "bin" / "hunspell"
    binary.write_text("#!/bin/sh\n", encoding="ascii")
    binary.chmod(0o700)
    (swapped / "lib").symlink_to(elsewhere, target_is_directory=True)
    with pytest.raises(h.ParityInputError):
        HunspellContainerPipeTransport(
            bundle_dir=bundle, install_dir=swapped, workspace_dir=workspace
        )


def test_every_cancellation_status_is_one_fixed_value(tmp_path):
    statuses = {
        tr.PIPE_STREAM_CLEANUP_NOT_ATTEMPTED,
        tr.PIPE_STREAM_CLEANUP_CONFIRMED,
        tr.PIPE_STREAM_CLEANUP_UNCONFIRMED,
    }
    assert statuses == {"NOT_ATTEMPTED", "CONFIRMED", "UNCONFIRMED"}
    cancellation = SystemExit(9)
    transport, _ = _transport(tmp_path, process_runner=_FakeRunner(raises=cancellation))
    with pytest.raises(SystemExit):
        transport.run_pipe_batch(_STDIN, **_LIMITS)
    status = cancellation.pipe_stream_cleanup_status
    assert status in statuses
    assert isinstance(status, str)
