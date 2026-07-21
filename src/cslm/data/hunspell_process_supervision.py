"""Bounded process supervision for the Direct-Hunspell harness.

This module owns the reviewed, exception-safe process lifecycle used by the
Direct-Hunspell work: a complete-payload stdin writer worker, concurrent
stdout/stderr drain workers that read through EOF on a normal exit and enforce the
byte ceilings *while reading*, one common operational deadline, process-group
termination (SIGTERM, the fixed grace, then SIGKILL), final-result classification,
and a clean/abnormal cleanup callback that must be confirmed or fail closed.

It is deliberately **Hunspell-specific**, not a general-purpose process library: it
raises the project's existing fixed :class:`~cslm.data.hunspell_pipe_stream`
exception hierarchy and defaults its termination grace to the approved
``TERMINATION_GRACE_SECONDS``.  It is the single source of truth for that
lifecycle, so the parity runner and any later bounded transport supervise
processes identically instead of duplicating safety-critical logic.

Raw process streams are sensitive by discipline: they are returned on
:class:`BoundedRun` so a caller can reduce them internally and drop them, and they
are never printed, logged, embedded in an error, or committed.  No error raised
here carries subprocess data.  This module launches nothing on import, imports no
CLI script, and reads no resource, corpus, or private log.
"""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from cslm.data.hunspell_pipe_stream import (
    TERMINATION_GRACE_SECONDS,
    ParityHarnessError,
    ParityInputError,
    ParityTransportError,
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
