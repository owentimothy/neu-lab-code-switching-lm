"""Tests for the shared bounded process supervisor.

These exercise the real subprocess supervisor (writer/drain workers, output
preservation on normal exit, byte ceilings, timeout, SIGTERM->SIGKILL, cancellation,
thread-start failure, and the clean/abnormal cleanup callback) against a local
synthetic *stub executable*.  The stub is an invented local process that mimics
generic process behaviours only.

No test starts Docker, uses the network, runs Hunspell, or accesses RLA-ES,
CALLHOME, Bangor, ignored resources, or private logs.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

from cslm.data import hunspell_pipe_stream as h
from cslm.data import hunspell_process_supervision as sup

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
    return sup.run_bounded(_stub_argv(tmp_path, *args), **kwargs)


# ---------------------------------------------------------------------------
# Stdin writer worker (offset loop).
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
    sup._writer_worker(stream, b"abcdefgh", delivered)
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
    sup._writer_worker(_Bad(), b"abc", delivered)
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
    sup._writer_worker(stream, b"", delivered)
    assert delivered == [True]
    assert stream.wrote is False


# ---------------------------------------------------------------------------
# Output preservation and success path.
# ---------------------------------------------------------------------------
def test_stdout_captured_completely_after_child_exit(tmp_path):
    payload = 200_000  # more than one pipe buffer
    result = _bounded(
        tmp_path, "flood_out", str(payload), max_stdout_bytes=5_000_000
    )
    assert result.terminal_state == sup.STATE_NORMAL_EXIT
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
    assert result.terminal_state == sup.STATE_NORMAL_EXIT
    assert result.stdout_bytes == payload
    assert result.stderr_bytes == payload


def test_run_bounded_captures_stdout_and_workers_join(tmp_path):
    result = _bounded(tmp_path, "echo", stdin_bytes=b"hello\n")
    assert result.terminal_state == sup.STATE_NORMAL_EXIT
    assert result.returncode == 0
    assert result.stdout == b"hello\n"
    assert result.workers_joined is True
    assert result.stdin_delivered is True


def test_complete_stdin_delivery_on_success(tmp_path):
    payload = b"hola\n" * 200
    result = _bounded(tmp_path, "echo", stdin_bytes=payload, max_stdout_bytes=5_000_000)
    assert result.terminal_state == sup.STATE_NORMAL_EXIT
    assert result.stdin_delivered is True
    assert result.stdout == payload
    assert result.worker_failed is False


def test_success_requires_all_workers_joined(tmp_path):
    result = sup.supervise(
        _stub_argv(tmp_path, "echo"),
        stdin_bytes=b"ok\n",
        timeout_seconds=10,
        max_stdout_bytes=1024,
        max_stderr_bytes=1024,
    )
    assert result.terminal_state == sup.STATE_NORMAL_EXIT
    assert result.workers_joined is True


def test_clean_success_invokes_clean_cleanup(tmp_path):
    calls: list[bool] = []
    result = _bounded(tmp_path, "echo", stdin_bytes=b"ok\n", cleanup=calls.append)
    assert result.terminal_state == sup.STATE_NORMAL_EXIT
    assert result.cleanup_required is True
    assert result.cleanup_confirmed is True
    assert calls == [True]


# ---------------------------------------------------------------------------
# Worker failures and incomplete delivery.
# ---------------------------------------------------------------------------
def test_child_closing_stdin_early_is_worker_failure(tmp_path):
    result = _bounded(
        tmp_path, "read_some_exit0", stdin_bytes=b"x" * 1_000_000
    )
    assert result.terminal_state == sup.STATE_WORKER_FAILURE
    assert result.worker_failed is True
    assert result.stdin_delivered is False
    assert result.returncode == 0


def test_incomplete_delivery_passes_clean_exit_false(tmp_path):
    calls: list[bool] = []
    result = _bounded(
        tmp_path, "read_some_exit0", stdin_bytes=b"x" * 1_000_000, cleanup=calls.append
    )
    assert result.terminal_state == sup.STATE_WORKER_FAILURE
    assert calls == [False]


def test_worker_failure_passes_clean_exit_false(tmp_path, monkeypatch):
    def _boom(*_args, **_kwargs):
        raise RuntimeError("private drain detail")

    monkeypatch.setattr(sup, "_drain_worker", _boom)
    calls: list[bool] = []
    result = _bounded(tmp_path, "sleep", "0.05", cleanup=calls.append)
    assert result.terminal_state == sup.STATE_WORKER_FAILURE
    assert calls == [False]


def test_writer_worker_failure_is_recorded(tmp_path, monkeypatch):
    def _boom(*_args, **_kwargs):
        raise RuntimeError("private writer detail")

    monkeypatch.setattr(sup, "_writer_worker", _boom)
    result = _bounded(tmp_path, "sleep", "0.05")
    assert result.terminal_state == sup.STATE_WORKER_FAILURE
    assert result.worker_failed is True


# ---------------------------------------------------------------------------
# Timeout, overflow, nonzero exit.
# ---------------------------------------------------------------------------
def test_run_bounded_reports_nonzero_exit_and_supervise_fails_closed(tmp_path):
    result = _bounded(tmp_path, "exit7")
    assert result.terminal_state == sup.STATE_NORMAL_EXIT
    assert result.returncode == 7
    with pytest.raises(h.ParityTransportError):
        sup.supervise(
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
    assert result.terminal_state == sup.STATE_OUTPUT_OVERFLOW
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
    assert result.terminal_state == sup.STATE_OUTPUT_OVERFLOW
    assert result.stderr_limit_exceeded is True
    assert result.stderr_bytes <= 1000


def test_timeout_invokes_abnormal_cleanup(tmp_path):
    calls: list[bool] = []
    result = _bounded(tmp_path, "sleep", "5", timeout_seconds=0.3, cleanup=calls.append)
    assert result.terminal_state == sup.STATE_TIMEOUT
    assert calls == [False]


def test_forced_termination_when_sigterm_ignored(tmp_path):
    result = _bounded(
        tmp_path,
        "ignore_term_sleep",
        "5",
        timeout_seconds=0.3,
        grace_seconds=1.0,
    )
    assert result.terminal_state == sup.STATE_TIMEOUT
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
    assert result.terminal_state == sup.STATE_TIMEOUT
    assert result.timed_out is True
    assert result.workers_joined is True
    assert elapsed < 0.4 + h.TERMINATION_GRACE_SECONDS + 3.0


# ---------------------------------------------------------------------------
# Cleanup confirmation, cancellation, and lifecycle safety.
# ---------------------------------------------------------------------------
def test_cleanup_failure_produces_fixed_failure(tmp_path):
    def _boom(_clean_exit):
        raise RuntimeError("private cleanup detail")

    result = _bounded(tmp_path, "echo", stdin_bytes=b"ok\n", cleanup=_boom)
    assert result.cleanup_confirmed is False
    with pytest.raises(h.ParityTransportError) as excinfo:
        sup.supervise(
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
        sup.run_bounded(
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

    with pytest.raises(h.ParityTransportError) as excinfo:
        sup.run_bounded(
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
    real_start = sup._start_worker
    real_join = sup._join_workers
    count = [0]

    def fake_start(thread):
        count[0] += 1
        if count[0] == 2:
            raise RuntimeError("private start detail")
        return real_start(thread)

    def spy_join(started, until):
        joined_started["n"] = len(list(started))
        return real_join(started, until)

    monkeypatch.setattr(sup, "_start_worker", fake_start)
    monkeypatch.setattr(sup, "_join_workers", spy_join)
    with pytest.raises(h.ParityTransportError) as excinfo:
        sup.run_bounded(
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

    monkeypatch.setattr(sup, "_join_workers", _boom)
    with pytest.raises(h.ParityTransportError) as excinfo:
        sup.run_bounded(
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

    monkeypatch.setattr(sup, "_close_streams", _boom)
    result = _bounded(tmp_path, "echo", stdin_bytes=b"ok\n", cleanup=calls.append)
    assert result.terminal_state == sup.STATE_NORMAL_EXIT
    assert calls == [True]


# ---------------------------------------------------------------------------
# Parameter validation.
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
    with pytest.raises(h.ParityInputError):
        sup.run_bounded(_stub_argv(tmp_path, "echo"), **base)


def test_run_bounded_rejects_bad_argv_and_launch_failure(tmp_path):
    with pytest.raises(h.ParityInputError):
        sup.run_bounded(
            "not-a-list",
            stdin_bytes=b"",
            timeout_seconds=1,
            max_stdout_bytes=1,
            max_stderr_bytes=1,
        )
    with pytest.raises(h.ParityTransportError):
        sup.run_bounded(
            [str(tmp_path / "does-not-exist")],
            stdin_bytes=b"",
            timeout_seconds=1,
            max_stdout_bytes=1,
            max_stderr_bytes=1,
        )
