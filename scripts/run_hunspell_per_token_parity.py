#!/usr/bin/env python
"""Phase A infrastructure for the Direct-Hunspell per-token protocol parity gate.

This module provides the *observation infrastructure* only.  The real per-token
Hunspell response protocol is UNRESOLVED.  Phase A therefore makes **no** framing
assumption: it does not equate output lines with input tokens, does not derive any
"candidate passed" verdict from one-line-per-token behaviour, and assumes no
banners, separators, response blocks, or suggestion shapes.  It reduces raw output
to protocol-neutral *whole-stream* aggregates and records only observed execution
facts.  Candidate PASS, membership-sequence matching, and marker rejection belong
to Phase B, after a parser contract is separately reviewed.

Contents:

* refusal-by-default CLI; live pinned-Hunspell execution is disabled in this gate
  (``_LIVE_PHASE_A_ENABLED`` is ``False``);
* a bounded process supervisor with an exception-safe lifecycle: a complete-payload
  stdin writer worker, concurrent stdout/stderr drain workers that read through EOF
  on a normal exit, one common operational deadline, process-group termination,
  final-result classification, and a clean/abnormal cleanup callback that must be
  confirmed or fail closed;
* protocol-neutral whole-stream observation;
* invented fixture builders (dictionary/affix inputs only), used later by the
  authorized Phase A execution step, not by ordinary tests.

It never accepts a corpus/resource/output path argument.  It never touches RLA-ES,
CALLHOME, Bangor, ignored resources, private logs, the network, or Docker in this
gate.  Raw process streams are treated as sensitive: reduced internally, never
printed, logged, returned in the summary, or embedded in an error.
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

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

# Live pinned-Hunspell Phase A execution is a SEPARATELY AUTHORIZED step and is
# intentionally not enabled in this initial implementation gate.
_LIVE_PHASE_A_ENABLED = False

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
# CLI.
# ---------------------------------------------------------------------------
def _execute_phase_a() -> dict[str, object]:
    """Live Phase A execution seam.

    Disabled in this implementation gate.  A separately authorized step will flip
    ``_LIVE_PHASE_A_ENABLED`` and inject the pinned-container probe; it must still
    emit only :data:`SUMMARY_KEYS` and never expose raw streams or marker values.
    """
    if not _LIVE_PHASE_A_ENABLED:
        raise ParityHarnessError("live Phase A execution is not enabled in this gate")
    raise ParityHarnessError("live Phase A execution wiring is deferred")  # pragma: no cover


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Direct-Hunspell per-token protocol parity: Phase A observation."
    )
    parser.add_argument(
        "--allow-phase-a-run",
        action="store_true",
        help="request the Phase A observation (live execution is gated off)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
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
