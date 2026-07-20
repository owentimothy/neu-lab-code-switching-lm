#!/usr/bin/env python
"""Phase A infrastructure and offline Phase B parser for Hunspell parity.

This module provides Phase A *observation infrastructure* plus pure offline Phase B
parsing.  Real candidate viability is UNRESOLVED.  Phase A makes **no** framing
assumption: it does not equate output lines with input tokens or derive any
"candidate passed" verdict from one-line-per-token behaviour.  It reduces raw
output to protocol-neutral *whole-stream* aggregates and records only observed
execution facts.  The separately approved Phase B contract is implemented here as
pure offline parsing and aggregate-assessment functions; it is not connected to
the live runner or CLI.

Contents:

* refusal-by-default CLI; the live pinned-Hunspell wiring is enabled
  (``_LIVE_PHASE_A_ENABLED`` is ``True``) but reached only through the
  ``--allow-phase-a-run`` opt-in, with acquisition and execution separately
  authorized and no Phase A run performed here;
* a bounded process supervisor with an exception-safe lifecycle: a complete-payload
  stdin writer worker, concurrent stdout/stderr drain workers that read through EOF
  on a normal exit, one common operational deadline, process-group termination,
  final-result classification, and a clean/abnormal cleanup callback that must be
  confirmed or fail closed;
* protocol-neutral whole-stream observation;
* invented fixture builders (dictionary/affix inputs only), used later by the
  authorized Phase A execution step, not by ordinary tests.
* strict offline Phase B parsing and aggregate assessment over invented results,
  with no automatic candidate selection and no live execution path.

It never accepts a corpus/resource/output path argument.  It never touches RLA-ES,
CALLHOME, Bangor, ignored resources, private logs, the network, or Docker in this
gate.  Raw process streams are treated as sensitive: reduced internally, never
printed, logged, returned in the summary, or embedded in an error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol

EXIT_SUCCESS = 0
EXIT_OPT_IN_REQUIRED = 2
EXIT_OPERATIONAL_ABORT = 3

_OPT_IN_MESSAGE = (
    "Refusing to run: pass --allow-phase-a-run to request the Phase A parity "
    "observation. Nothing was read, written, or executed."
)
_ABORT_MESSAGE = (
    "Phase A parity run aborted. No protocol was selected, no resource or corpus "
    "was accessed, and no private value was printed."
)
_PHASE_B_ABORT_MESSAGE = (
    "Phase B parity run aborted. No protocol was selected, no resource or corpus "
    "was accessed, and no private value was printed."
)

# Live pinned-Hunspell Phase A execution is a SEPARATELY AUTHORIZED step.  The
# wiring is enabled here, but the CLI still refuses by default and reaches it only
# with --allow-phase-a-run; acquisition and execution remain separately authorized
# and no Phase A run is performed here.
_LIVE_PHASE_A_ENABLED = True
_LIVE_PHASE_B_ENABLED = False

# --- Public pinned identities (carried forward from tracked feasibility evidence).
HUNSPELL_RELEASE = "v1.7.3"
HUNSPELL_COMMIT = "c5f98152a274e25b5107101104bef632b83a0cc9"
CONTAINER_REPOSITORY = "docker.io/library/buildpack-deps"
CONTAINER_PLATFORM = "linux/arm64"
CONTAINER_PLATFORM_DIGEST = (
    "sha256:a60c415ba968e9accc8795332295eca29c58968ef95d45616e90e2a5da40f498"
)
CONTAINER_REFERENCE = f"{CONTAINER_REPOSITORY}@{CONTAINER_PLATFORM_DIGEST}"

# --- Exact approved defensive limits (do not raise automatically after failure).
MAX_TOKEN_BYTES = 256  # defensive policy choice
MAX_TOKENS_PER_BATCH = 256  # proposed ceiling, suitability tested synthetically
MAX_TOKENS_PER_REQUEST = 10_000  # defensive policy choice
BATCH_TIMEOUT_SECONDS = 30  # proposed ceiling, suitability tested synthetically
MAX_STDOUT_BYTES = 2 * 1024 * 1024  # defensive hard ceiling (terminate midstream)
MAX_STDERR_BYTES = 64 * 1024  # defensive hard ceiling (terminate midstream)
TERMINATION_GRACE_SECONDS = 1.0  # exactly one second grace before SIGKILL

# Candidate mode labels.  BATCH_FILTER is a documented negative baseline and is
# never a selectable result; the selectable enum is PIPE_STREAM / SINGLE_TOKEN_LIST
# / NONE.
CANDIDATE_LABELS: tuple[str, ...] = ("PIPE_STREAM", "SINGLE_TOKEN_LIST")
SELECTED_MODE_ENUM: tuple[str, ...] = ("PIPE_STREAM", "SINGLE_TOKEN_LIST", "NONE")
MEMBERSHIP_ACCEPTED = "ACCEPTED"
MEMBERSHIP_REJECTED = "REJECTED"
MEMBERSHIP_LABELS: tuple[str, ...] = (MEMBERSHIP_ACCEPTED, MEMBERSHIP_REJECTED)
PHASE_B_PIPE_HEADING = (
    b"@(#) International Ispell Version 3.2.06 (but really Hunspell 1.7.3)\n"
)

# Fixed internal supervisor terminal states.  ``forced_termination`` (SIGKILL
# escalation) is reported separately so all five outcomes are distinguishable.
STATE_NORMAL_EXIT = "normal_exit"
STATE_TIMEOUT = "timeout"
STATE_OUTPUT_OVERFLOW = "output_overflow"
STATE_WORKER_FAILURE = "worker_failure"
TERMINAL_STATES: tuple[str, ...] = (
    STATE_NORMAL_EXIT,
    STATE_TIMEOUT,
    STATE_OUTPUT_OVERFLOW,
    STATE_WORKER_FAILURE,
)

# Docker removal is bounded and never runs in ordinary tests.
_DOCKER_REMOVE_TIMEOUT = 20
_DOCKER_RUN = subprocess.run


class ParityHarnessError(RuntimeError):
    """Base class for every fixed, non-sensitive parity-harness failure."""


class ParityInputError(ParityHarnessError):
    """The caller did not supply a valid invented-token or parameter structure."""


class ParityTransportError(ParityHarnessError):
    """A process could not be launched, supervised, or cleaned up safely."""


class PhaseBParseError(ParityHarnessError):
    """A response failed the approved Phase B contract without exposing content."""


_PHASE_B_FAILURE_MESSAGE = (
    "Phase B candidate response did not match the approved protocol contract"
)


# ---------------------------------------------------------------------------
# Token validation and batching (defensive limits).
# ---------------------------------------------------------------------------
def validate_tokens(tokens: object) -> tuple[str, ...]:
    """Validate an invented-token request without echoing any token."""
    if isinstance(tokens, (str, bytes, bytearray)) or not isinstance(tokens, Sequence):
        raise ParityInputError("tokens must be a sequence of strings")
    if len(tokens) > MAX_TOKENS_PER_REQUEST:
        raise ParityInputError("too many tokens in one request")
    prepared: list[str] = []
    for token in tokens:
        if not isinstance(token, str):
            raise ParityInputError("every token must be a string")
        if not token:
            raise ParityInputError("tokens must not be empty")
        if any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in token):
            raise ParityInputError("tokens must not contain whitespace or control")
        if len(token.encode("utf-8")) > MAX_TOKEN_BYTES:
            raise ParityInputError("token exceeds the maximum byte length")
        prepared.append(token)
    return tuple(prepared)


def batch_tokens(tokens: Sequence[str]) -> tuple[tuple[str, ...], ...]:
    """Split validated tokens into bounded batches, preserving order."""
    return tuple(
        tuple(tokens[start : start + MAX_TOKENS_PER_BATCH])
        for start in range(0, len(tokens), MAX_TOKENS_PER_BATCH)
    )


# ---------------------------------------------------------------------------
# Bounded process supervision.
# ---------------------------------------------------------------------------
@dataclass
class _WorkerOutcome:
    completed: bool = False
    failed: bool = False


@dataclass(frozen=True)
class BoundedRun:
    """Outcome of one supervised process invocation.

    ``stdout``/``stderr`` are sensitive by discipline: they exist so a caller can
    reduce them internally and drop them.  They are never printed or committed.
    """

    returncode: int | None
    terminal_state: str
    forced_termination: bool
    stdin_delivered: bool
    stdout: bytes
    stderr: bytes
    stdout_bytes: int
    stderr_bytes: int
    stdout_limit_exceeded: bool
    stderr_limit_exceeded: bool
    timed_out: bool
    worker_failed: bool
    workers_joined: bool
    cleanup_required: bool
    cleanup_confirmed: bool
    latency_ms: int


def _validate_supervision_params(
    timeout_seconds: float,
    max_stdout_bytes: int,
    max_stderr_bytes: int,
    grace_seconds: float,
    poll_interval: float,
) -> None:
    for value in (timeout_seconds, grace_seconds, poll_interval):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
            raise ParityInputError("timing parameters must be positive")
    for value in (max_stdout_bytes, max_stderr_bytes):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ParityInputError("output caps must be positive integers")


def _writer_worker(stdin_stream, data: bytes, delivered: list) -> None:
    """Deliver the complete stdin payload via an offset loop, then flush.

    ``delivered[0]`` becomes ``True`` only after every byte is written and flushed.
    A zero/None/invalid write or a BrokenPipe/OSError leaves it ``False``.
    """
    try:
        try:
            view = memoryview(data)
            total = view.nbytes
            written = 0
            while written < total:
                count = stdin_stream.write(view[written:])
                if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
                    raise OSError("invalid stdin write result")
                written += count
            stdin_stream.flush()
            delivered[0] = written == total
        except (BrokenPipeError, OSError):
            delivered[0] = False
    finally:
        try:
            stdin_stream.close()
        except OSError:
            pass


def _drain_worker(
    stream,
    cap: int,
    buffer: bytearray,
    seen: list,
    exceeded: list,
    stop: threading.Event,
) -> None:
    """Drain one stream into a bounded buffer, reading through EOF.

    The loop does not exit merely because ``stop`` is unset; it stops on EOF or a
    cap breach.  A read error before supervised termination has begun (``stop``
    unset) is a worker failure; once ``stop`` is set a stream-close error is
    expected cleanup.
    """
    try:
        while True:
            chunk = stream.read(65536)
            if not chunk:
                break
            seen[0] += len(chunk)
            if len(buffer) < cap:
                buffer.extend(chunk[: cap - len(buffer)])
            if seen[0] > cap:
                exceeded[0] = True
                stop.set()
                break
    except (OSError, ValueError):
        if not stop.is_set():
            raise


def _supervised_worker(
    work: Callable[[], None], outcome: _WorkerOutcome, stop: threading.Event
) -> None:
    try:
        work()
        outcome.completed = True
    except Exception:  # noqa: BLE001 - captured as a fixed worker-failure state
        outcome.failed = True
        stop.set()


def _start_worker(thread: threading.Thread) -> None:
    """Start one worker thread (indirected so failures are injectable in tests)."""
    thread.start()


def _join_workers(started, until: float) -> bool:
    """Join only started workers, up to an absolute deadline; report full join."""
    joined = True
    for thread, _ in started:
        thread.join(timeout=max(0.0, until - time.monotonic()))
        if thread.is_alive():
            joined = False
    return joined


def _close_streams(proc: subprocess.Popen) -> None:
    for stream in (proc.stdin, proc.stdout, proc.stderr):
        try:
            if stream is not None:
                stream.close()
        except OSError:
            pass


def _terminate_group(proc: subprocess.Popen, grace_seconds: float) -> bool:
    """SIGTERM the group, wait one grace, SIGKILL if still alive.

    Returns ``True`` only when SIGKILL escalation was required.
    """
    try:
        pgid = os.getpgid(proc.pid)
    except (ProcessLookupError, OSError):
        return False
    try:
        os.killpg(pgid, signal.SIGTERM)
    except (ProcessLookupError, OSError):
        return False
    try:
        proc.wait(timeout=grace_seconds)
        return False
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(pgid, signal.SIGKILL)
    except (ProcessLookupError, OSError):
        pass
    try:
        proc.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        pass
    return True


def _watch_process(
    proc: subprocess.Popen,
    outcomes: Sequence[_WorkerOutcome],
    out_over: list,
    err_over: list,
    deadline: float,
    poll_interval: float,
) -> str | None:
    """Watch until an abnormal reason, a normal child exit (``None``), or timeout.

    A normal child exit does not set the shared stop event: drainers keep reading
    through EOF afterwards.
    """
    while True:
        if any(outcome.failed for outcome in outcomes):
            return "worker_failure"
        if out_over[0] or err_over[0]:
            return "overflow"
        if proc.poll() is not None:
            return None
        if time.monotonic() >= deadline:
            return "timeout"
        time.sleep(poll_interval)


def run_bounded(
    argv: Sequence[str],
    *,
    stdin_bytes: bytes,
    timeout_seconds: float,
    max_stdout_bytes: int,
    max_stderr_bytes: int,
    grace_seconds: float = TERMINATION_GRACE_SECONDS,
    poll_interval: float = 0.01,
    cleanup: Callable[[bool], None] | None = None,
    _after_launch: Callable[[subprocess.Popen], None] | None = None,
) -> BoundedRun:
    """Run an argument vector under a bounded, exception-safe supervisor.

    On a normal child exit the stop event is not set: the writer and both drainers
    complete naturally and read through EOF, bounded only by the original
    operational deadline.  ``clean_exit`` is computed only after worker results are
    known (return code zero, no timeout/overflow, every started worker completed
    and joined, complete stdin delivery), and cleanup is invoked with that final
    classification.  Stop is set immediately only for timeout, overflow, worker
    failure, cancellation, unexpected exception, or a thread-start failure; in each
    of those the process group is terminated, only started workers are joined,
    pipes are closed, and abnormal cleanup runs.  ``KeyboardInterrupt``/
    ``SystemExit`` re-raise; other unexpected exceptions become one fixed
    :class:`ParityTransportError`.  No error carries subprocess data.
    ``_after_launch`` is a test seam.
    """
    _validate_supervision_params(
        timeout_seconds, max_stdout_bytes, max_stderr_bytes, grace_seconds, poll_interval
    )
    if (
        isinstance(argv, (str, bytes))
        or not isinstance(argv, Sequence)
        or not argv
        or not all(isinstance(part, str) for part in argv)
    ):
        raise ParityInputError("argv must be a non-empty sequence of strings")
    if not isinstance(stdin_bytes, (bytes, bytearray)):
        raise ParityInputError("stdin_bytes must be bytes")

    start = time.monotonic()
    try:
        proc = subprocess.Popen(  # noqa: S603 - argument vector, no shell
            list(argv),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except OSError:
        raise ParityTransportError("process could not be launched") from None

    out_buf = bytearray()
    err_buf = bytearray()
    out_seen = [0]
    err_seen = [0]
    out_over = [False]
    err_over = [False]
    delivered = [False]
    stop = threading.Event()
    writer_outcome = _WorkerOutcome()
    out_outcome = _WorkerOutcome()
    err_outcome = _WorkerOutcome()
    payload = bytes(stdin_bytes)

    workers = [
        (
            threading.Thread(
                target=_supervised_worker,
                args=(
                    lambda: _writer_worker(proc.stdin, payload, delivered),
                    writer_outcome,
                    stop,
                ),
                daemon=True,
            ),
            writer_outcome,
        ),
        (
            threading.Thread(
                target=_supervised_worker,
                args=(
                    lambda: _drain_worker(
                        proc.stdout, max_stdout_bytes, out_buf, out_seen, out_over, stop
                    ),
                    out_outcome,
                    stop,
                ),
                daemon=True,
            ),
            out_outcome,
        ),
        (
            threading.Thread(
                target=_supervised_worker,
                args=(
                    lambda: _drain_worker(
                        proc.stderr, max_stderr_bytes, err_buf, err_seen, err_over, stop
                    ),
                    err_outcome,
                    stop,
                ),
                daemon=True,
            ),
            err_outcome,
        ),
    ]
    started_workers: list = []
    teardown = {
        "done": False,
        "forced": False,
        "joined": True,
        "cleanup_required": cleanup is not None,
        "cleanup_confirmed": True,
    }

    def _perform_teardown(clean_exit: bool) -> None:
        if teardown["done"]:
            return
        teardown["done"] = True
        stop.set()
        try:
            if proc.poll() is None:
                teardown["forced"] = _terminate_group(proc, grace_seconds)
        except Exception:  # noqa: BLE001 - cleanup must still run
            pass
        try:
            teardown["joined"] = _join_workers(
                started_workers, time.monotonic() + grace_seconds + 2.0
            )
        except Exception:  # noqa: BLE001 - cleanup must still run
            teardown["joined"] = False
        try:
            _close_streams(proc)
        except Exception:  # noqa: BLE001 - cleanup must still run
            pass
        if cleanup is not None:
            try:
                cleanup(clean_exit)
            except Exception:  # noqa: BLE001 - recorded, never swallowed silently
                teardown["cleanup_confirmed"] = False

    deadline = start + timeout_seconds
    try:
        if _after_launch is not None:
            _after_launch(proc)
        for thread, outcome in workers:
            _start_worker(thread)
            started_workers.append((thread, outcome))
        reason = _watch_process(
            proc,
            [outcome for _, outcome in started_workers],
            out_over,
            err_over,
            deadline,
            poll_interval,
        )
        if reason is None:
            joined_normal = _join_workers(started_workers, deadline)
            overflow = out_over[0] or err_over[0]
            incomplete = bool(payload) and not delivered[0]
            started_ok = all(
                outcome.completed and not outcome.failed
                for _, outcome in started_workers
            )
            clean_exit = (
                proc.poll() == 0
                and not overflow
                and joined_normal
                and started_ok
                and not incomplete
            )
            _perform_teardown(clean_exit)
            timed_out = False
            if overflow:
                terminal_state = STATE_OUTPUT_OVERFLOW
            elif not started_ok or not joined_normal or incomplete:
                terminal_state = STATE_WORKER_FAILURE
            else:
                terminal_state = STATE_NORMAL_EXIT
        else:
            stop.set()
            _perform_teardown(False)
            timed_out = reason == "timeout"
            overflow = out_over[0] or err_over[0]
            terminal_state = {
                "timeout": STATE_TIMEOUT,
                "overflow": STATE_OUTPUT_OVERFLOW,
                "worker_failure": STATE_WORKER_FAILURE,
            }[reason]
    except (KeyboardInterrupt, SystemExit):
        stop.set()
        _perform_teardown(False)
        raise
    except ParityHarnessError:
        stop.set()
        _perform_teardown(False)
        raise
    except Exception:
        stop.set()
        _perform_teardown(False)
        raise ParityTransportError("bounded process supervision failed") from None

    latency_ms = int((time.monotonic() - start) * 1000)
    return BoundedRun(
        returncode=proc.poll(),
        terminal_state=terminal_state,
        forced_termination=teardown["forced"],
        stdin_delivered=delivered[0],
        stdout=bytes(out_buf),
        stderr=bytes(err_buf),
        stdout_bytes=len(out_buf),
        stderr_bytes=len(err_buf),
        stdout_limit_exceeded=out_over[0],
        stderr_limit_exceeded=err_over[0],
        timed_out=timed_out,
        worker_failed=terminal_state == STATE_WORKER_FAILURE,
        workers_joined=teardown["joined"],
        cleanup_required=teardown["cleanup_required"],
        cleanup_confirmed=teardown["cleanup_confirmed"],
        latency_ms=latency_ms,
    )


def supervise(argv: Sequence[str], **kwargs) -> BoundedRun:
    """Run ``run_bounded`` and fail closed on any non-clean outcome."""
    result = run_bounded(argv, **kwargs)
    if result.terminal_state != STATE_NORMAL_EXIT or result.returncode != 0:
        raise ParityTransportError("bounded process did not complete cleanly")
    if result.cleanup_required and not result.cleanup_confirmed:
        raise ParityTransportError("process cleanup could not be confirmed")
    return result


# ---------------------------------------------------------------------------
# Container transport helpers (structure only; not executed in this gate).
# ---------------------------------------------------------------------------
def hardened_container_argv(
    *,
    cidfile_path: Path,
    bundle_dir: Path,
    install_dir: Path,
    inner_argv: Sequence[str],
) -> list[str]:
    """Build the pinned, network-disabled, read-only container argument vector."""
    return [
        "docker",
        "run",
        "--rm",
        "--interactive",
        "--cidfile",
        str(cidfile_path),
        "--network",
        "none",
        "--platform",
        CONTAINER_PLATFORM,
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,noexec,size=64m",
        "-e",
        "LANG=C.UTF-8",
        "-e",
        "LC_ALL=C.UTF-8",
        "--mount",
        f"type=bind,src={bundle_dir},dst=/bundle,readonly",
        "--mount",
        f"type=bind,src={install_dir},dst=/opt/hunspell,readonly",
        CONTAINER_REFERENCE,
        *inner_argv,
    ]


def _default_docker_remove(container_id: str) -> None:
    """Force-remove a container: argument vector, DEVNULL discard, timeout, checked."""
    completed = _DOCKER_RUN(
        ["docker", "rm", "-f", container_id],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=_DOCKER_REMOVE_TIMEOUT,
        check=False,
    )
    if getattr(completed, "returncode", 1) != 0:
        raise ParityTransportError("docker removal returned a nonzero result")


def _remove_cidfile(cidfile_path: Path) -> None:
    try:
        cidfile_path.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        raise ParityTransportError("cidfile removal failed") from None
    if cidfile_path.exists():
        raise ParityTransportError("cidfile still present after cleanup")


def finalize_container(
    cidfile_path: Path,
    *,
    clean_exit: bool,
    docker_remove=None,
) -> None:
    """Confirm container cleanup for the supervised lifecycle, or fail closed.

    Clean zero exit under ``docker run --rm``: the container removed itself, so only
    the non-token-bearing cidfile is removed and its removal confirmed.  Any
    abnormal exit force-removes a surviving container (checked) and confirms cidfile
    removal; a missing/unreadable cidfile, empty id, remover failure, or unremoved
    cidfile fails closed.  The cidfile holds only the container identifier.
    """
    remover = docker_remove if docker_remove is not None else _default_docker_remove
    present = cidfile_path.exists()
    container_id = ""
    if present:
        try:
            container_id = cidfile_path.read_text(encoding="ascii").strip()
        except (OSError, UnicodeError):
            if not clean_exit:
                raise ParityTransportError("cidfile unreadable on abnormal exit") from None
    if not clean_exit:
        if not present:
            raise ParityTransportError("cidfile missing on abnormal exit")
        if not container_id:
            raise ParityTransportError("cidfile empty on abnormal exit")
        try:
            remover(container_id)
        except ParityTransportError:
            raise
        except Exception:  # noqa: BLE001 - never expose a private value
            raise ParityTransportError("surviving container removal failed") from None
    _remove_cidfile(cidfile_path)


def container_cleanup(cidfile_path: Path, *, docker_remove=None) -> Callable[[bool], None]:
    """Return a clean/abnormal-aware cleanup callable for the process lifecycle."""

    def _cleanup(clean_exit: bool) -> None:
        finalize_container(
            cidfile_path, clean_exit=clean_exit, docker_remove=docker_remove
        )

    return _cleanup


# ---------------------------------------------------------------------------
# Candidate invocations (only the invocation is fixed; no framing is assumed).
# ---------------------------------------------------------------------------
def candidate_invocation(label: str, dictionary_base: str) -> tuple[str, ...]:
    """Return the invocation for a candidate mode.

    Only the invocation is fixed here.  No banner, segment, separator, or status
    framing is assumed; those are hypotheses Phase A observes.
    """
    if label == "PIPE_STREAM":
        return ("hunspell", "-d", dictionary_base, "-a")
    if label == "SINGLE_TOKEN_LIST":
        return ("hunspell", "-d", dictionary_base, "-l")
    raise ParityInputError("unknown candidate label")


# ---------------------------------------------------------------------------
# Protocol-neutral whole-stream observation.
# ---------------------------------------------------------------------------
def whole_stream_summary(raw: bytes) -> tuple[int, int, int, int]:
    """Reduce raw output to coarse whole-stream counts, assuming no framing.

    Returns ``(total_bytes, total_lf_count, blank_line_count, nonempty_line_count)``.
    This never maps output to input tokens and never inspects marker shapes.
    """
    total_bytes = len(raw)
    total_lf = raw.count(b"\n")
    if not raw:
        return (0, 0, 0, 0)
    lines = raw.split(b"\n")
    if raw.endswith(b"\n"):
        lines = lines[:-1]
    blank = sum(1 for line in lines if line == b"")
    nonempty = sum(1 for line in lines if line != b"")
    return (total_bytes, total_lf, blank, nonempty)


@dataclass(frozen=True)
class CandidateObservation:
    """Protocol-neutral whole-stream Phase A observation for one candidate mode."""

    observation_completed: bool
    raw_stream_identical_across_runs: bool
    structural_summary_stable: bool
    total_bytes: int
    total_lf_count: int
    blank_line_count: int
    nonempty_line_count: int
    max_stdout_bytes: int
    max_stderr_bytes: int
    max_batch_latency_ms: int

    def to_dict(self) -> dict[str, object]:
        return {
            "observation_completed": self.observation_completed,
            "raw_stream_identical_across_runs": self.raw_stream_identical_across_runs,
            "structural_summary_stable": self.structural_summary_stable,
            "total_bytes": self.total_bytes,
            "total_lf_count": self.total_lf_count,
            "blank_line_count": self.blank_line_count,
            "nonempty_line_count": self.nonempty_line_count,
            "max_stdout_bytes": self.max_stdout_bytes,
            "max_stderr_bytes": self.max_stderr_bytes,
            "max_batch_latency_ms": self.max_batch_latency_ms,
        }


def observe_candidate(
    raw_run_one: bytes,
    raw_run_two: bytes,
    *,
    execution_completed_within_limits: bool,
    max_stdout_bytes: int,
    max_stderr_bytes: int,
    max_batch_latency_ms: int,
) -> CandidateObservation:
    """Reduce two invented runs to protocol-neutral whole-stream observations."""
    summary_one = whole_stream_summary(raw_run_one)
    summary_two = whole_stream_summary(raw_run_two)
    total_bytes, total_lf, blank, nonempty = summary_one
    return CandidateObservation(
        observation_completed=execution_completed_within_limits,
        raw_stream_identical_across_runs=raw_run_one == raw_run_two,
        structural_summary_stable=summary_one == summary_two,
        total_bytes=total_bytes,
        total_lf_count=total_lf,
        blank_line_count=blank,
        nonempty_line_count=nonempty,
        max_stdout_bytes=max_stdout_bytes,
        max_stderr_bytes=max_stderr_bytes,
        max_batch_latency_ms=max_batch_latency_ms,
    )


# Fixed, exact aggregate schema keys.
SUMMARY_KEYS: tuple[str, ...] = (
    "hunspell_release",
    "hunspell_commit",
    "container_platform",
    "environment_identity_match",
    "offline_build",
    "modes_compared",
    "selected_mode_label",
    "pipe_stream_observation_completed",
    "single_token_list_observation_completed",
    "candidate_observation_count",
    "candidate_observations",
    "no_real_resource_or_corpus_access",
)
CANDIDATE_OBSERVATION_KEYS: tuple[str, ...] = tuple(
    CandidateObservation(
        True, True, True, 0, 0, 0, 0, 0, 0, 0
    ).to_dict().keys()
)


def build_phase_a_summary(
    observations: dict[str, CandidateObservation],
    *,
    environment_identity_match: bool,
    offline_build: bool,
) -> dict[str, object]:
    """Assemble the fixed aggregate Phase A summary of observed execution facts.

    ``selected_mode_label`` is always ``NONE``: Phase A never selects a mode and
    never asserts protocol viability.  There is no ``candidate_passed`` or
    ``passing_candidate_count``; PASS belongs to Phase B after parser review.
    """
    if tuple(observations) != CANDIDATE_LABELS:
        raise ParityInputError("observations must cover exactly the candidate labels")
    summary: dict[str, object] = {
        "hunspell_release": HUNSPELL_RELEASE,
        "hunspell_commit": HUNSPELL_COMMIT,
        "container_platform": CONTAINER_PLATFORM,
        "environment_identity_match": environment_identity_match,
        "offline_build": offline_build,
        "modes_compared": len(CANDIDATE_LABELS),
        "selected_mode_label": "NONE",
        "pipe_stream_observation_completed": (
            observations["PIPE_STREAM"].observation_completed
        ),
        "single_token_list_observation_completed": (
            observations["SINGLE_TOKEN_LIST"].observation_completed
        ),
        "candidate_observation_count": len(observations),
        "candidate_observations": {
            label: observations[label].to_dict() for label in CANDIDATE_LABELS
        },
        "no_real_resource_or_corpus_access": True,
    }
    if tuple(summary) != SUMMARY_KEYS:
        raise ParityInputError("summary schema drifted from the fixed key order")
    return summary


# ---------------------------------------------------------------------------
# Invented fixtures (dictionary/affix inputs only; not executed in this gate).
# ---------------------------------------------------------------------------
REQUIRED_QUERY_BEHAVIORS: tuple[str, ...] = (
    "unflagged_base",
    "prefix_derived",
    "suffix_derived",
    "cross_product",
    "repeated_record_prefix_derived",
    "repeated_record_suffix_derived",
    "first_continuation_derived",
    "chained_continuation_derived",
    "duplicate_base",
    "rejected",
)


@dataclass(frozen=True)
class InventedFixture:
    """Invented Hunspell inputs plus a query, its behaviours, and known truth."""

    affix_bytes: bytes
    dictionary_bytes: bytes
    query_tokens: tuple[str, ...]
    query_behaviors: tuple[str, ...]
    known_truth: tuple[bool, ...]


def _encode_dictionary(records: Sequence[str]) -> bytes:
    """Encode a Hunspell dictionary whose header equals the actual record count."""
    body = "".join(f"{record}\n" for record in records)
    return f"{len(records)}\n{body}".encode("ascii")


def dictionary_declared_and_actual_counts(dictionary_bytes: bytes) -> tuple[int, int]:
    """Return (declared header count, actual record count) without a rule parser."""
    text = dictionary_bytes.decode("ascii")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    if not lines or not lines[0].isdigit():
        raise ParityInputError("dictionary header is not a record count")
    return int(lines[0]), len(lines) - 1


def build_invented_fixture() -> InventedFixture:
    """Build one invented fixture with independently interpretable derived cases.

    The dictionary header is constructed from the record sequence.  A single base
    (``synrep``) appears in two records with distinct flags; an affix continuation
    chain (``C`` -> ``D``) yields a first and a chained continuation form.  The
    query covers base and derived behaviours, an ordered non-adjacent duplicate,
    and one rejected form.  Real pinned Hunspell interprets these in Phase A; this
    gate does not run them, and no restricted affix-directive parser is used.
    """
    records = (
        "synbase",  # unflagged base
        "synpre/A",  # prefix rule A
        "synsuf/B",  # suffix rule B
        "syncross/AB",  # cross-product base
        "synrep/A",  # repeated base, record one
        "synrep/B",  # repeated base, record two (distinct flag)
        "synchain/C",  # continuation base (C continues to D)
    )
    dictionary_bytes = _encode_dictionary(records)
    affix_bytes = (
        b"SET UTF-8\n"
        b"FLAG UTF-8\n"
        b"PFX A Y 1\n"
        b"PFX A 0 re .\n"
        b"SFX B Y 1\n"
        b"SFX B 0 s .\n"
        b"SFX C Y 1\n"
        b"SFX C 0 er/D .\n"  # derived form carries D (continuation)
        b"SFX D Y 1\n"
        b"SFX D 0 s .\n"
    )
    query_tokens = (
        "synbase",  # unflagged_base
        "resynpre",  # prefix_derived
        "synsufs",  # suffix_derived
        "resyncrosss",  # cross_product (prefix + suffix)
        "resynrep",  # repeated_record_prefix_derived
        "synreps",  # repeated_record_suffix_derived
        "synchainer",  # first_continuation_derived (C)
        "synchainers",  # chained_continuation_derived (C then D)
        "synbase",  # duplicate_base (ordered, non-adjacent)
        "synqzzz",  # rejected
    )
    known_truth = (True, True, True, True, True, True, True, True, True, False)
    return InventedFixture(
        affix_bytes=affix_bytes,
        dictionary_bytes=dictionary_bytes,
        query_tokens=query_tokens,
        query_behaviors=REQUIRED_QUERY_BEHAVIORS,
        known_truth=known_truth,
    )


# ---------------------------------------------------------------------------
# Phase A live-execution wiring (implemented, enabled; opt-in only).
#
# The orchestration is dependency-injected so offline tests drive it with a fake
# environment.  The live environment performs the only Docker/network/filesystem/
# subprocess work and is reached only through the ``main`` opt-in
# (``--allow-phase-a-run``); the CLI refuses by default before any of it runs, and
# acquisition and execution remain separately authorized.  ``PIPE_STREAM`` runs one
# supervised process per bounded token batch; ``SINGLE_TOKEN_LIST`` runs one
# separate supervised process per input token.  Phase A stops after the aggregate
# observations: it never selects a mode, parses responses, classifies markers, or
# infers membership.
# ---------------------------------------------------------------------------

# Public pinned acquisition identities (carried forward from the feasibility gate).
HUNSPELL_ARCHIVE_NAME = "hunspell-1.7.3.tar.gz"
HUNSPELL_ARCHIVE_URL = (
    "https://github.com/hunspell/hunspell/releases/download/"
    f"{HUNSPELL_RELEASE}/{HUNSPELL_ARCHIVE_NAME}"
)
HUNSPELL_ARCHIVE_SHA256 = (
    "433274dac0619cb00c2e18b43a3dd3a9d50da5b5613fa9b5c21781e35dd76bc1"
)
CONTAINER_TAG = "bookworm"
CONTAINER_INDEX_DIGEST = (
    "sha256:5bfacbc6611775f980cf283fbc86b999517878d39723510687135a0d6366bbee"
)

# In-container invented-fixture layout for a live run.
_FIXTURE_BASE = "synthetic"
_CONTAINER_HUNSPELL_BIN = "/opt/hunspell/bin/hunspell"
_CONTAINER_HUNSPELL_LIB = "/opt/hunspell/lib"

# Timeouts for supervised Docker operations (tracked precedent; never raised auto).
_DOCKER_PULL_TIMEOUT_SECONDS = 300
_DOCKER_BUILD_TIMEOUT_SECONDS = 300


@dataclass(frozen=True)
class _CandidateRun:
    """Internal per-process record; ``raw_stdout`` is reduced then dropped."""

    raw_stdout: bytes
    stdout_bytes: int
    stderr_bytes: int
    latency_ms: int
    cleanup_confirmed: bool


@dataclass(frozen=True)
class _CandidateRepetition:
    """One logical repetition: the ordered per-process raw outputs plus bounds.

    ``raw_streams`` is the ordered tuple of each process's raw stdout; it is compared
    internally across repetitions and reduced, then dropped.  The maxima are per
    actual process batch, never an unbounded combined buffer.
    """

    raw_streams: tuple[bytes, ...]
    max_stdout_bytes: int
    max_stderr_bytes: int
    max_latency_ms: int
    cleanup_confirmed: bool


@dataclass(frozen=True)
class MembershipResult:
    """One internal non-lexical result, preserving only ordinal and membership."""

    ordinal: int
    membership: str


@dataclass(frozen=True)
class PhaseBCandidateAssessment:
    """Fixed non-reconstructive Phase B assessment for one candidate."""

    candidate_attempted: bool
    candidate_completed: bool
    invented_case_count: int
    expected_membership_match_count: int
    exact_cardinality: bool
    repetitions_identical: bool
    unknown_response_count: int
    cleanup_confirmed: bool
    candidate_passed: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "candidate_attempted": self.candidate_attempted,
            "candidate_completed": self.candidate_completed,
            "invented_case_count": self.invented_case_count,
            "expected_membership_match_count": (
                self.expected_membership_match_count
            ),
            "exact_cardinality": self.exact_cardinality,
            "repetitions_identical": self.repetitions_identical,
            "unknown_response_count": self.unknown_response_count,
            "cleanup_confirmed": self.cleanup_confirmed,
            "candidate_passed": self.candidate_passed,
        }


@dataclass(frozen=True)
class _PhaseAEvidence:
    """Verified environment evidence carried into the aggregate summary."""

    environment_identity_match: bool
    offline_build: bool


class PhaseAEnvironment(Protocol):
    """Injected Phase A dependency boundary (real in a live run, fake in tests)."""

    def verify_identities(self) -> None: ...
    def build(self) -> None: ...
    def run_candidate(
        self, label: str, fixture: InventedFixture, run_index: int
    ) -> _CandidateRepetition: ...
    def evidence(self) -> _PhaseAEvidence: ...
    def teardown(self) -> None: ...


class PhaseBEnvironment(Protocol):
    """Injected Phase B dependency boundary (real later, fake in offline tests)."""

    def verify_identities(self) -> None: ...
    def build(self) -> None: ...
    def run_candidate(
        self, label: str, fixture: InventedFixture, run_index: int
    ) -> _CandidateRepetition: ...
    def evidence(self) -> _PhaseAEvidence: ...
    def teardown(self) -> None: ...


def _phase_a_batch_stdin(tokens: Sequence[str]) -> bytes:
    """Encode one process's tokens as a bounded, newline-delimited stdin stream."""
    if not tokens:
        return b""
    return ("\n".join(tokens) + "\n").encode("utf-8")


def _phase_a_candidate_stdin(_label: str, tokens: Sequence[str]) -> bytes:
    """Adapt the unchanged Phase A stdin encoding to the shared process runner."""
    return _phase_a_batch_stdin(tokens)


def _phase_a_container_argv(
    label: str,
    fixture_dir: Path,
    install_dir: Path,
    cidfile_path: Path,
) -> list[str]:
    """Build the pinned container argv for one candidate over invented inputs.

    Only the invocation is fixed; no banner, separator, or response framing is
    assumed.  Tokens are delivered via stdin, never via the command.
    """
    mode_flag = candidate_invocation(label, _FIXTURE_BASE)[-1]
    inner = [_CONTAINER_HUNSPELL_BIN, "-d", f"/bundle/{_FIXTURE_BASE}", mode_flag]
    argv = hardened_container_argv(
        cidfile_path=cidfile_path,
        bundle_dir=fixture_dir,
        install_dir=install_dir,
        inner_argv=inner,
    )
    marker = argv.index("LC_ALL=C.UTF-8")
    argv[marker + 1 : marker + 1] = ["-e", f"LD_LIBRARY_PATH={_CONTAINER_HUNSPELL_LIB}"]
    return argv


def _reduce_candidate(result: BoundedRun) -> _CandidateRun:
    """Convert one supervised process into a per-process record, or fail closed."""
    if result.terminal_state != STATE_NORMAL_EXIT or result.returncode != 0:
        raise ParityHarnessError("candidate execution did not complete cleanly")
    if result.cleanup_required and not result.cleanup_confirmed:
        raise ParityHarnessError("candidate cleanup could not be confirmed")
    if not result.stdin_delivered:
        raise ParityHarnessError("candidate stdin delivery was incomplete")
    return _CandidateRun(
        raw_stdout=result.stdout,
        stdout_bytes=result.stdout_bytes,
        stderr_bytes=result.stderr_bytes,
        latency_ms=result.latency_ms,
        cleanup_confirmed=(
            not result.cleanup_required or result.cleanup_confirmed
        ),
    )


def _candidate_token_groups(label: str, tokens: Sequence[str]) -> tuple[tuple[str, ...], ...]:
    """Group tokens per process: bounded batches for PIPE_STREAM, one per token else."""
    if label == "PIPE_STREAM":
        return batch_tokens(tokens)
    if label == "SINGLE_TOKEN_LIST":
        return tuple((token,) for token in tokens)
    raise ParityInputError("unknown candidate label")


# ---------------------------------------------------------------------------
# Phase B pure offline parser and aggregate assessment (not live-wired).
# ---------------------------------------------------------------------------
def _phase_b_fail() -> None:
    """Raise the one fixed Phase B parse failure without response material."""
    raise PhaseBParseError(_PHASE_B_FAILURE_MESSAGE)


def _decode_protocol_text(raw: bytes) -> str:
    """Decode internal protocol material, collapsing all failures to one error."""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        _phase_b_fail()


def _is_protocol_field(value: str, *, allow_internal_space: bool = False) -> bool:
    """Check an internal field without returning or reporting its content."""
    if not value or value != value.strip():
        return False
    if any(not character.isprintable() for character in value):
        return False
    return allow_internal_space or not any(character.isspace() for character in value)


def _unsigned_protocol_integer(value: str) -> int:
    """Parse a bounded ASCII integer or fail without reporting its text."""
    if not (value.isascii() and value.isdigit() and len(value) <= 10):
        _phase_b_fail()
    return int(value)


def _parse_pipe_record(record: bytes, token: str, ordinal: int) -> MembershipResult:
    """Parse one exact normal-mode ``-a`` record and immediately discard fields."""
    text = _decode_protocol_text(record)
    if text == "*":
        return MembershipResult(ordinal, MEMBERSHIP_ACCEPTED)

    if text.startswith(("+ ", "- ")):
        root = text[2:]
        if _is_protocol_field(root):
            return MembershipResult(ordinal, MEMBERSHIP_ACCEPTED)
        _phase_b_fail()

    if text.startswith("# "):
        fields = text[2:].split(" ")
        if (
            len(fields) == 2
            and fields[0] == token
        ):
            _unsigned_protocol_integer(fields[1])
            return MembershipResult(ordinal, MEMBERSHIP_REJECTED)
        _phase_b_fail()

    if text.startswith("& "):
        left, delimiter, suggestion_text = text[2:].partition(": ")
        fields = left.split(" ")
        if delimiter and len(fields) == 3:
            echo, count_text, offset_text = fields
            suggestions = suggestion_text.split(", ")
            count = _unsigned_protocol_integer(count_text)
            _unsigned_protocol_integer(offset_text)
            suggestions_valid = all(
                _is_protocol_field(suggestion, allow_internal_space=True)
                for suggestion in suggestions
            )
            if (
                echo == token
                and count > 0
                and suggestions_valid
                and len(suggestions) == count
            ):
                return MembershipResult(ordinal, MEMBERSHIP_REJECTED)
        _phase_b_fail()

    _phase_b_fail()


def parse_pipe_stream_response(
    raw: bytes, tokens: Sequence[str], *, ordinal_offset: int = 0
) -> tuple[MembershipResult, ...]:
    """Parse one complete bounded ``-a`` stream under the approved exact framing."""
    prepared = validate_tokens(tokens)
    if not isinstance(raw, bytes) or ordinal_offset < 0:
        _phase_b_fail()
    if not raw.startswith(PHASE_B_PIPE_HEADING):
        _phase_b_fail()

    cursor = len(PHASE_B_PIPE_HEADING)
    results: list[MembershipResult] = []
    for index, token in enumerate(prepared):
        line_end = raw.find(b"\n", cursor)
        if line_end < 0:
            _phase_b_fail()
        record = raw[cursor:line_end]
        cursor = line_end + 1
        if raw[cursor : cursor + 1] != b"\n":
            _phase_b_fail()
        cursor += 1
        results.append(_parse_pipe_record(record, token, ordinal_offset + index))
    if cursor != len(raw):
        _phase_b_fail()
    return tuple(results)


def parse_single_token_list_response(
    raw: bytes, token: str, *, ordinal: int
) -> MembershipResult:
    """Parse one complete single-token ``-l`` process response."""
    prepared = validate_tokens((token,))
    if not isinstance(raw, bytes) or ordinal < 0:
        _phase_b_fail()
    if raw == b"":
        return MembershipResult(ordinal, MEMBERSHIP_ACCEPTED)
    _decode_protocol_text(raw)
    if raw == prepared[0].encode("utf-8") + b"\n":
        return MembershipResult(ordinal, MEMBERSHIP_REJECTED)
    _phase_b_fail()


def _phase_b_stdin(label: str, tokens: Sequence[str]) -> bytes:
    """Build approved Phase B stdin without connecting it to the live runner."""
    prepared = validate_tokens(tokens)
    if label == "PIPE_STREAM":
        return b"".join(b"^" + token.encode("utf-8") + b"\n" for token in prepared)
    if label == "SINGLE_TOKEN_LIST" and len(prepared) == 1:
        return prepared[0].encode("utf-8") + b"\n"
    raise ParityInputError("Phase B stdin requires one approved candidate grouping")


def _validate_phase_b_repetition(repetition: _CandidateRepetition) -> None:
    """Require the retained process aggregates to remain within approved limits."""
    observed_max_stdout = max(
        (len(stream) for stream in repetition.raw_streams), default=0
    )
    if (
        repetition.max_stdout_bytes < 0
        or repetition.max_stdout_bytes != observed_max_stdout
        or repetition.max_stdout_bytes > MAX_STDOUT_BYTES
        or repetition.max_stderr_bytes < 0
        or repetition.max_stderr_bytes != 0
        or repetition.max_latency_ms < 0
        or repetition.max_latency_ms > BATCH_TIMEOUT_SECONDS * 1000
        or not repetition.cleanup_confirmed
    ):
        _phase_b_fail()


def parse_candidate_responses(
    label: str, repetition: _CandidateRepetition, tokens: Sequence[str]
) -> tuple[MembershipResult, ...]:
    """Parse one candidate repetition while preserving process boundaries."""
    prepared = validate_tokens(tokens)
    _validate_phase_b_repetition(repetition)
    groups = _candidate_token_groups(label, prepared)
    if len(repetition.raw_streams) != len(groups):
        _phase_b_fail()

    results: list[MembershipResult] = []
    ordinal = 0
    for stream, group in zip(repetition.raw_streams, groups, strict=True):
        if label == "PIPE_STREAM":
            parsed = parse_pipe_stream_response(stream, group, ordinal_offset=ordinal)
            results.extend(parsed)
        elif label == "SINGLE_TOKEN_LIST":
            results.append(
                parse_single_token_list_response(stream, group[0], ordinal=ordinal)
            )
        else:  # guarded by _candidate_token_groups; retained as fail-closed defense.
            _phase_b_fail()
        ordinal += len(group)
    return tuple(results)


def assess_phase_b_candidate(
    label: str,
    first: _CandidateRepetition,
    second: _CandidateRepetition,
    fixture: InventedFixture,
) -> PhaseBCandidateAssessment:
    """Assess two invented repetitions without exposing per-token results."""
    if not (
        len(fixture.query_tokens)
        == len(fixture.query_behaviors)
        == len(fixture.known_truth)
    ):
        raise ParityInputError("invented fixture cardinality is inconsistent")
    first_results = parse_candidate_responses(label, first, fixture.query_tokens)
    second_results = parse_candidate_responses(label, second, fixture.query_tokens)
    expected = tuple(
        MEMBERSHIP_ACCEPTED if truth else MEMBERSHIP_REJECTED
        for truth in fixture.known_truth
    )
    observed = tuple(result.membership for result in first_results)
    second_observed = tuple(result.membership for result in second_results)
    match_count = sum(
        actual == wanted for actual, wanted in zip(observed, expected, strict=True)
    )
    exact_cardinality = len(observed) == len(expected) == len(second_observed)
    repetitions_identical = (
        first.raw_streams == second.raw_streams and observed == second_observed
    )
    cleanup_confirmed = first.cleanup_confirmed and second.cleanup_confirmed
    candidate_passed = (
        exact_cardinality
        and repetitions_identical
        and cleanup_confirmed
        and match_count == len(expected)
    )
    return PhaseBCandidateAssessment(
        candidate_attempted=True,
        candidate_completed=True,
        invented_case_count=len(expected),
        expected_membership_match_count=match_count,
        exact_cardinality=exact_cardinality,
        repetitions_identical=repetitions_identical,
        unknown_response_count=0,
        cleanup_confirmed=cleanup_confirmed,
        candidate_passed=candidate_passed,
    )


PHASE_B_SUMMARY_KEYS: tuple[str, ...] = (
    "hunspell_release",
    "hunspell_commit",
    "container_platform",
    "environment_identity_match",
    "offline_build",
    "modes_compared",
    "selected_mode_label",
    "passing_candidate_count",
    "candidate_assessment_count",
    "candidate_assessments",
    "no_real_resource_or_corpus_access",
)
PHASE_B_CANDIDATE_ASSESSMENT_KEYS: tuple[str, ...] = tuple(
    PhaseBCandidateAssessment(True, True, 0, 0, True, True, 0, True, True)
    .to_dict()
    .keys()
)


def build_phase_b_summary(
    assessments: dict[str, PhaseBCandidateAssessment],
    *,
    environment_identity_match: bool,
    offline_build: bool,
) -> dict[str, object]:
    """Build a fixed aggregate report that never chooses between candidates."""
    if tuple(assessments) != CANDIDATE_LABELS:
        raise ParityInputError("assessments must cover exactly the candidate labels")
    summary: dict[str, object] = {
        "hunspell_release": HUNSPELL_RELEASE,
        "hunspell_commit": HUNSPELL_COMMIT,
        "container_platform": CONTAINER_PLATFORM,
        "environment_identity_match": environment_identity_match,
        "offline_build": offline_build,
        "modes_compared": len(CANDIDATE_LABELS),
        "selected_mode_label": "NONE",
        "passing_candidate_count": sum(
            assessment.candidate_passed for assessment in assessments.values()
        ),
        "candidate_assessment_count": len(assessments),
        "candidate_assessments": {
            label: assessments[label].to_dict() for label in CANDIDATE_LABELS
        },
        "no_real_resource_or_corpus_access": True,
    }
    if tuple(summary) != PHASE_B_SUMMARY_KEYS:
        raise ParityInputError("Phase B summary schema drifted from fixed key order")
    return summary


def _run_candidate_processes(
    label: str,
    tokens: Sequence[str],
    fixture_dir: Path,
    install_dir: Path,
    run_process: Callable[[list[str], bytes, Callable[[bool], None] | None], BoundedRun],
    docker_remover: Callable[[str], None] | None,
    cidfile_factory: Callable[[str, int], Path],
    *,
    stdin_builder: Callable[[str, Sequence[str]], bytes] = _phase_a_candidate_stdin,
) -> _CandidateRepetition:
    """Launch one supervised process per token group, preserving input order.

    Each process receives exactly its group's tokens on stdin (one token plus a
    newline for SINGLE_TOKEN_LIST); no token enters argv, an environment variable, a
    path, or an error.  Per-process raw stdout is retained only long enough to form
    the ordered repetition; maxima are per actual process batch.
    """
    groups = _candidate_token_groups(label, tokens)
    raw_streams: list[bytes] = []
    max_stdout = 0
    max_stderr = 0
    max_latency = 0
    cleanup_confirmed = True
    for index, group in enumerate(groups):
        cidfile = cidfile_factory(label, index)
        argv = _phase_a_container_argv(label, fixture_dir, install_dir, cidfile)
        cleanup = container_cleanup(cidfile, docker_remove=docker_remover)
        record = _reduce_candidate(run_process(argv, stdin_builder(label, group), cleanup))
        raw_streams.append(record.raw_stdout)
        max_stdout = max(max_stdout, record.stdout_bytes)
        max_stderr = max(max_stderr, record.stderr_bytes)
        max_latency = max(max_latency, record.latency_ms)
        cleanup_confirmed = cleanup_confirmed and record.cleanup_confirmed
    return _CandidateRepetition(
        tuple(raw_streams),
        max_stdout,
        max_stderr,
        max_latency,
        cleanup_confirmed,
    )


def _per_process_summaries(
    repetition: _CandidateRepetition,
) -> tuple[tuple[int, int, int, int], ...]:
    """Summarise each process's raw stdout separately, preserving order."""
    return tuple(whole_stream_summary(stream) for stream in repetition.raw_streams)


def _observe_repetitions(
    first: _CandidateRepetition, second: _CandidateRepetition
) -> CandidateObservation:
    """Reduce two logical repetitions to protocol-neutral observations.

    Each process's raw stdout is summarised separately; outputs from different
    processes are never concatenated before counting.  Public totals sum the first
    repetition's per-process summaries; stability compares the ordered per-process
    summary tuples; identity compares the ordered raw-stream tuples.  No individual
    summary, raw stream, token, response line, marker, or hash is exposed.
    """
    first_summaries = _per_process_summaries(first)
    second_summaries = _per_process_summaries(second)
    total_bytes = sum(summary[0] for summary in first_summaries)
    total_lf = sum(summary[1] for summary in first_summaries)
    blank = sum(summary[2] for summary in first_summaries)
    nonempty = sum(summary[3] for summary in first_summaries)
    return CandidateObservation(
        observation_completed=True,
        raw_stream_identical_across_runs=first.raw_streams == second.raw_streams,
        structural_summary_stable=first_summaries == second_summaries,
        total_bytes=total_bytes,
        total_lf_count=total_lf,
        blank_line_count=blank,
        nonempty_line_count=nonempty,
        max_stdout_bytes=max(first.max_stdout_bytes, second.max_stdout_bytes),
        max_stderr_bytes=max(first.max_stderr_bytes, second.max_stderr_bytes),
        max_batch_latency_ms=max(first.max_latency_ms, second.max_latency_ms),
    )


def _run_phase_a(
    environment: PhaseAEnvironment,
    *,
    fixture: InventedFixture | None = None,
) -> dict[str, object]:
    """Orchestrate Phase A: verify, build, two repetitions per candidate, aggregate.

    Each repetition's raw streams are reduced to whole-stream observations and
    dropped.  Identity/build success is taken from the environment's derived
    evidence, not a hardcoded claim.  Emits only the fixed aggregate schema with
    ``selected_mode_label`` = ``NONE`` and no candidate PASS verdict.
    """
    active = fixture if fixture is not None else build_invented_fixture()
    environment.verify_identities()
    environment.build()
    observations: dict[str, CandidateObservation] = {}
    for label in CANDIDATE_LABELS:
        first = environment.run_candidate(label, active, 0)
        second = environment.run_candidate(label, active, 1)
        observations[label] = _observe_repetitions(first, second)
        del first, second  # discard raw streams
    evidence = environment.evidence()
    return build_phase_a_summary(
        observations,
        environment_identity_match=evidence.environment_identity_match,
        offline_build=evidence.offline_build,
    )


def _run_phase_a_with_teardown(environment: PhaseAEnvironment) -> dict[str, object]:
    """Run Phase A and attempt teardown exactly once, on success or failure."""
    try:
        return _run_phase_a(environment)
    finally:
        environment.teardown()


def _run_phase_b(
    environment: PhaseBEnvironment,
    *,
    fixture: InventedFixture | None = None,
) -> dict[str, object]:
    """Orchestrate Phase B over invented inputs and emit aggregates only."""
    active = fixture if fixture is not None else build_invented_fixture()
    environment.verify_identities()
    environment.build()
    assessments: dict[str, PhaseBCandidateAssessment] = {}
    for label in CANDIDATE_LABELS:
        first = environment.run_candidate(label, active, 0)
        second = environment.run_candidate(label, active, 1)
        assessments[label] = assess_phase_b_candidate(label, first, second, active)
        del first, second
    evidence = environment.evidence()
    if not (evidence.environment_identity_match and evidence.offline_build):
        raise ParityHarnessError("Phase B environment evidence was not confirmed")
    return build_phase_b_summary(
        assessments,
        environment_identity_match=evidence.environment_identity_match,
        offline_build=evidence.offline_build,
    )


def _run_phase_b_with_teardown(environment: PhaseBEnvironment) -> dict[str, object]:
    """Run Phase B and attempt teardown exactly once, on success or failure."""
    try:
        return _run_phase_b(environment)
    finally:
        environment.teardown()


# --- Live boundary: the only Docker/network/subprocess work, reached only when
# the gate is enabled and a real environment is constructed.
def _acquire_public_pinned_source(archive_path: Path) -> None:
    try:
        with urllib.request.urlopen(HUNSPELL_ARCHIVE_URL, timeout=60) as response:
            data = response.read()
    except (OSError, TimeoutError):
        raise ParityHarnessError("hunspell source acquisition failed") from None
    if hashlib.sha256(data).hexdigest() != HUNSPELL_ARCHIVE_SHA256:
        raise ParityHarnessError("hunspell source identity mismatch")
    try:
        archive_path.write_bytes(data)
    except OSError:
        raise ParityHarnessError("hunspell source archive could not be written") from None


def _extract_source(archive_path: Path, destination: Path) -> Path:
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            members = archive.getmembers()
            for member in members:
                relative = PurePosixPath(member.name)
                if relative.is_absolute() or ".." in relative.parts:
                    raise ParityHarnessError("unsafe archive member path")
                if not (member.isdir() or member.isfile()):
                    raise ParityHarnessError("unsafe archive member type")
            archive.extractall(destination, members=members, filter="data")
    except (OSError, tarfile.TarError):
        raise ParityHarnessError("hunspell source extraction failed") from None
    source_dir = destination / "hunspell-1.7.3"
    if source_dir.is_symlink() or not source_dir.is_dir():
        raise ParityHarnessError("hunspell source layout unexpected")
    configure = source_dir / "configure"
    if configure.is_symlink() or not configure.is_file():
        raise ParityHarnessError("hunspell source is missing the configure script")
    return source_dir


def _require_clean(result: BoundedRun) -> BoundedRun:
    """Fail closed unless a supervised docker operation completed and cleaned up."""
    if result.terminal_state != STATE_NORMAL_EXIT or result.returncode != 0:
        raise ParityHarnessError("docker operation did not complete cleanly")
    if result.cleanup_required and not result.cleanup_confirmed:
        raise ParityHarnessError("docker cleanup could not be confirmed")
    return result


def _docker_pull_argv() -> list[str]:
    """Argument vector for the bounded, quiet pull of the pinned image digest."""
    return [
        "docker", "pull", "--quiet",
        "--platform", CONTAINER_PLATFORM,
        CONTAINER_REFERENCE,
    ]


def _build_container_argv(
    source_dir: Path, install_dir: Path, cidfile_path: Path
) -> list[str]:
    """Argument vector for the hardened, offline, cidfile-tracked build container."""
    return [
        "docker", "run", "--rm",
        "--cidfile", str(cidfile_path),
        "--network", "none",
        "--platform", CONTAINER_PLATFORM,
        "--read-only",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=256m",
        "-e", "LANG=C.UTF-8",
        "-e", "LC_ALL=C.UTF-8",
        "--mount", f"type=bind,src={source_dir},dst=/src",
        "--mount", f"type=bind,src={install_dir},dst=/install",
        "-w", "/src",
        CONTAINER_REFERENCE,
        "bash", "-lc",
        "./configure --prefix=/install >/tmp/configure.log 2>&1 "
        "&& make -j2 >/tmp/make.log 2>&1 "
        "&& make install >/tmp/install.log 2>&1 "
        "&& test -x /install/bin/hunspell",
    ]


class _LivePhaseAEnvironment:
    """Real Phase A environment; performs the only Docker/network/subprocess work.

    Every foreground container, the build container, and the ``docker pull`` are
    supervised through the bounded transport (``Popen(..., start_new_session=True)``,
    fixed timeouts, bounded output, process-group termination, checked container
    cleanup).  Identity and build success are derived from the actual verified
    results.  External effects are injected callables so an authorized run uses the
    real defaults while offline tests substitute fakes; constructing the class has no
    side effects.
    """

    _phase_label = "phase A"
    _workspace_prefix = "neu-lab-parity-phase-a-"

    def __init__(
        self,
        *,
        source_acquirer: Callable[[Path], None] = _acquire_public_pinned_source,
        source_extractor: Callable[[Path, Path], Path] = _extract_source,
        runner: Callable[..., BoundedRun] = run_bounded,
        docker_remover: Callable[[str], None] | None = None,
    ) -> None:
        self._acquire = source_acquirer
        self._extract = source_extractor
        self._runner = runner
        self._docker_remover = docker_remover
        self._workspace: tempfile.TemporaryDirectory | None = None
        self._source_dir: Path | None = None
        self._install_dir: Path | None = None
        self._source_verified = False
        self._container_verified = False
        self._build_verified = False

    def _supervise_docker(
        self,
        argv: list[str],
        *,
        timeout: int,
        stdin_bytes: bytes = b"",
        cleanup: Callable[[bool], None] | None = None,
    ) -> BoundedRun:
        result = self._runner(
            argv,
            stdin_bytes=stdin_bytes,
            timeout_seconds=timeout,
            max_stdout_bytes=MAX_STDOUT_BYTES,
            max_stderr_bytes=MAX_STDERR_BYTES,
            cleanup=cleanup,
        )
        return _require_clean(result)

    def verify_identities(self) -> None:
        try:
            self._workspace = tempfile.TemporaryDirectory(
                prefix=self._workspace_prefix
            )
        except OSError:
            raise ParityHarnessError(
                f"{self._phase_label} workspace could not be created"
            ) from None
        root = Path(self._workspace.name)
        archive = root / HUNSPELL_ARCHIVE_NAME
        self._acquire(archive)  # sha-256 verified against the pinned identity
        self._source_verified = True
        self._source_dir = self._extract(archive, root / "source")
        self._supervise_docker(_docker_pull_argv(), timeout=_DOCKER_PULL_TIMEOUT_SECONDS)
        self._container_verified = True

    def build(self) -> None:
        if (
            not (self._source_verified and self._container_verified)
            or self._workspace is None
            or self._source_dir is None
        ):
            raise ParityHarnessError(
                f"{self._phase_label} build requested before verification"
            )
        install_dir = Path(self._workspace.name) / "install"
        try:
            install_dir.mkdir()
        except OSError:
            raise ParityHarnessError(
                f"{self._phase_label} install directory could not be created"
            ) from None
        cidfile = Path(self._workspace.name) / "build.cid"
        cleanup = container_cleanup(cidfile, docker_remove=self._docker_remover)
        self._supervise_docker(
            _build_container_argv(self._source_dir, install_dir, cidfile),
            timeout=_DOCKER_BUILD_TIMEOUT_SECONDS,
            cleanup=cleanup,
        )
        binary = install_dir / "bin" / "hunspell"
        if binary.is_symlink() or not binary.is_file():
            raise ParityHarnessError("hunspell build did not install the expected binary")
        self._install_dir = install_dir
        self._build_verified = True

    def _run_candidate_with_stdin(
        self,
        label: str,
        fixture: InventedFixture,
        run_index: int,
        stdin_builder: Callable[[str, Sequence[str]], bytes],
    ) -> _CandidateRepetition:
        if not self._build_verified or self._install_dir is None or self._workspace is None:
            raise ParityHarnessError(
                f"{self._phase_label} run requested before build"
            )
        root = Path(self._workspace.name)
        fixture_dir = root / f"fixture_{label}_{run_index}"
        try:
            fixture_dir.mkdir()
            (fixture_dir / f"{_FIXTURE_BASE}.dic").write_bytes(fixture.dictionary_bytes)
            (fixture_dir / f"{_FIXTURE_BASE}.aff").write_bytes(fixture.affix_bytes)
        except OSError:
            raise ParityHarnessError(
                f"{self._phase_label} invented fixture could not be materialised"
            ) from None
        tokens = validate_tokens(fixture.query_tokens)

        def cidfile_factory(candidate_label: str, index: int) -> Path:
            return root / f"cid_{candidate_label}_{run_index}_{index}"

        def run_process(argv, stdin_bytes, cleanup):
            return self._runner(
                argv,
                stdin_bytes=stdin_bytes,
                timeout_seconds=BATCH_TIMEOUT_SECONDS,
                max_stdout_bytes=MAX_STDOUT_BYTES,
                max_stderr_bytes=MAX_STDERR_BYTES,
                cleanup=cleanup,
            )

        return _run_candidate_processes(
            label,
            tokens,
            fixture_dir,
            self._install_dir,
            run_process,
            self._docker_remover,
            cidfile_factory,
            stdin_builder=stdin_builder,
        )

    def run_candidate(
        self, label: str, fixture: InventedFixture, run_index: int
    ) -> _CandidateRepetition:
        return self._run_candidate_with_stdin(
            label,
            fixture,
            run_index,
            _phase_a_candidate_stdin,
        )

    def evidence(self) -> _PhaseAEvidence:
        return _PhaseAEvidence(
            environment_identity_match=self._source_verified and self._container_verified,
            offline_build=self._build_verified,
        )

    def teardown(self) -> None:
        if self._workspace is None:
            return
        workspace = self._workspace
        self._workspace = None  # attempted exactly once
        try:
            workspace.cleanup()
        except OSError:
            raise ParityHarnessError(
                f"{self._phase_label} workspace cleanup could not be confirmed"
            ) from None


class _LivePhaseBEnvironment(_LivePhaseAEnvironment):
    """Dormant Phase B live environment; construction itself has no side effects."""

    _phase_label = "phase B"
    _workspace_prefix = "neu-lab-parity-phase-b-"

    def run_candidate(
        self, label: str, fixture: InventedFixture, run_index: int
    ) -> _CandidateRepetition:
        return self._run_candidate_with_stdin(
            label,
            fixture,
            run_index,
            _phase_b_stdin,
        )


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------
def _execute_phase_a(environment: PhaseAEnvironment | None = None) -> dict[str, object]:
    """Run live Phase A under the enabled activation flag (opt-in only).

    The activation flag is enabled, so when reached this constructs the injected
    (or default live) environment, which verifies identities, builds offline, runs
    two repetitions per candidate, and reduces to the aggregate schema only
    (``selected_mode_label`` = ``NONE``), with teardown attempted exactly once.  It
    is reached only through the ``main`` opt-in (``--allow-phase-a-run``); the CLI
    still refuses by default, and acquisition and execution remain separately
    authorized.  If the flag were disabled it would refuse before any Docker,
    network, filesystem-resource, or subprocess activity.  The CLI accepts no
    caller-supplied evidence.
    """
    if not _LIVE_PHASE_A_ENABLED:
        raise ParityHarnessError("live Phase A execution is not enabled in this gate")
    env = environment if environment is not None else _LivePhaseAEnvironment()
    return _run_phase_a_with_teardown(env)


def _execute_phase_b(environment: PhaseBEnvironment | None = None) -> dict[str, object]:
    """Reach the dormant Phase B live wiring only after a later activation gate."""
    if not _LIVE_PHASE_B_ENABLED:
        raise ParityHarnessError("live Phase B execution is not enabled in this gate")
    env = environment if environment is not None else _LivePhaseBEnvironment()
    return _run_phase_b_with_teardown(env)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Direct-Hunspell per-token protocol parity gates."
    )
    live_gate = parser.add_mutually_exclusive_group()
    live_gate.add_argument(
        "--allow-phase-a-run",
        action="store_true",
        help=(
            "opt in to reach the enabled live Phase A wiring "
            "(required; execution stays separately authorized)"
        ),
    )
    live_gate.add_argument(
        "--allow-phase-b-run",
        action="store_true",
        help=(
            "request the disabled live Phase B wiring "
            "(activation and execution stay separately authorized)"
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.allow_phase_b_run:
        try:
            summary = _execute_phase_b()
        except Exception:
            print(_PHASE_B_ABORT_MESSAGE, file=sys.stderr)
            return EXIT_OPERATIONAL_ABORT
        print(json.dumps(summary, ensure_ascii=True, separators=(",", ":")))
        return EXIT_SUCCESS
    if not args.allow_phase_a_run:
        print(_OPT_IN_MESSAGE, file=sys.stderr)
        return EXIT_OPT_IN_REQUIRED
    try:
        summary = _execute_phase_a()
    except Exception:
        print(_ABORT_MESSAGE, file=sys.stderr)
        return EXIT_OPERATIONAL_ABORT
    print(json.dumps(summary, ensure_ascii=True, separators=(",", ":")))
    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
