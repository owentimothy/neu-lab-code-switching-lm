"""Offline tests for the concrete Spanish Hunspell PIPE_STREAM checker.

Only invented tokens and a fake in-memory transport are used.  No process, Docker,
network, resource, or corpus is touched.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from cslm.data import hunspell_pipe_stream as h
from cslm.data.spanish_hunspell_coverage import (
    SpanishHunspellUnavailableError,
    compute_spanish_hunspell_coverage,
)
from cslm.data.spanish_hunspell_pipe_checker import SpanishHunspellPipeChecker

_EXPECTED_LIMITS = {
    "timeout_seconds": h.BATCH_TIMEOUT_SECONDS,
    "max_stdout_bytes": h.MAX_STDOUT_BYTES,
    "max_stderr_bytes": h.MAX_STDERR_BYTES,
    "grace_seconds": h.TERMINATION_GRACE_SECONDS,
}


def _pipe_bytes(tokens: list[str], accepts: list[bool]) -> bytes:
    body = h.PHASE_B_PIPE_HEADING
    for token, ok in zip(tokens, accepts):
        record = b"*" if ok else b"# " + token.encode("utf-8") + b" 0"
        body += record + b"\n\n"
    return body


def _tokens_from_stdin(stdin_bytes: bytes) -> list[str]:
    return [line[1:].decode("utf-8") for line in stdin_bytes.split(b"\n") if line]


class _FakePipeTransport:
    """A fake transport that accepts a fixed invented set; records every call."""

    def __init__(self, accepted=frozenset()):
        self.accepted = frozenset(accepted)
        self.calls: list[dict] = []

    def run_pipe_batch(
        self,
        stdin_bytes,
        *,
        timeout_seconds,
        max_stdout_bytes,
        max_stderr_bytes,
        grace_seconds,
    ) -> bytes:
        self.calls.append(
            {
                "timeout_seconds": timeout_seconds,
                "max_stdout_bytes": max_stdout_bytes,
                "max_stderr_bytes": max_stderr_bytes,
                "grace_seconds": grace_seconds,
                "n_tokens": len(_tokens_from_stdin(stdin_bytes)),
            }
        )
        tokens = _tokens_from_stdin(stdin_bytes)
        return _pipe_bytes(tokens, [t in self.accepted for t in tokens])


class _RaisingTransport:
    """A transport whose operational failure has already collapsed to one error."""

    def __init__(self):
        self.calls = 0

    def run_pipe_batch(self, stdin_bytes, **_limits) -> bytes:
        self.calls += 1
        raise h.ParityTransportError("process cleanup could not be confirmed")


class _MalformedTransport:
    def __init__(self, payload: bytes):
        self.payload = payload

    def run_pipe_batch(self, stdin_bytes, **_limits) -> bytes:
        return self.payload


# Distinctive invented markers that must never appear in an outward exception.
_SECRET = "SENSITIVE-synLEAK-9999"
_TOKEN = "synsecrettoken"


class _ExceptionTransport:
    """Simulates an operational failure by raising a chosen exception."""

    def __init__(self, exc: BaseException):
        self.exc = exc
        self.calls = 0

    def run_pipe_batch(self, stdin_bytes, **_limits) -> bytes:
        self.calls += 1
        raise self.exc


class _NonBytesTransport:
    """Returns a non-``bytes`` object instead of raw stdout."""

    def __init__(self, value):
        self.value = value

    def run_pipe_batch(self, stdin_bytes, **_limits):
        return self.value


class _OversizeTransport:
    """Returns more stdout bytes than the defensive ceiling permits."""

    def run_pipe_batch(self, stdin_bytes, **_limits) -> bytes:
        return b"x" * (h.MAX_STDOUT_BYTES + 1)


# Each of these must collapse to exactly PIPE_STREAM_TRANSPORT_FAILURE_MESSAGE.
_COLLAPSING_TRANSPORTS = {
    "timeout": _ExceptionTransport(TimeoutError(_SECRET)),
    "nonzero_exit": _ExceptionTransport(RuntimeError("nonzero exit " + _SECRET)),
    "stdout_overflow_signal": _ExceptionTransport(RuntimeError("stdout over " + _SECRET)),
    "stderr_overflow_signal": _ExceptionTransport(RuntimeError("stderr over " + _SECRET)),
    "worker_failure": _ExceptionTransport(RuntimeError("worker crashed " + _SECRET)),
    "unconfirmed_cleanup": _ExceptionTransport(
        h.ParityTransportError("cleanup unconfirmed " + _SECRET)
    ),
    "arbitrary_exception": _ExceptionTransport(ValueError(_SECRET)),
    "sensitive_transport_error": _ExceptionTransport(
        h.ParityTransportError(_SECRET + " " + _TOKEN)
    ),
    "non_bytes_return": _NonBytesTransport("not-bytes-" + _SECRET),
    "oversize_return": _OversizeTransport(),
}


def test_accepted_and_rejected_mixture():
    checker = SpanishHunspellPipeChecker(_FakePipeTransport({"syncasa"}))
    assert checker.check_tokens(["syncasa", "synxx"]) == (True, False)


def test_order_and_duplicates_preserved():
    checker = SpanishHunspellPipeChecker(_FakePipeTransport({"syna"}))
    assert checker.check_tokens(["synb", "syna", "synb"]) == (False, True, False)


def test_empty_request_returns_empty_without_transport():
    transport = _FakePipeTransport()
    checker = SpanishHunspellPipeChecker(transport)
    assert checker.check_tokens([]) == ()
    assert transport.calls == []


def test_exact_limits_passed_on_every_batch():
    transport = _FakePipeTransport({f"syn{i}" for i in range(300)})
    checker = SpanishHunspellPipeChecker(transport)
    tokens = [f"syn{i}" for i in range(h.MAX_TOKENS_PER_BATCH + 1)]
    result = checker.check_tokens(tokens)
    assert result == (True,) * len(tokens)
    assert len(transport.calls) == 2
    assert [call["n_tokens"] for call in transport.calls] == [h.MAX_TOKENS_PER_BATCH, 1]
    for call in transport.calls:
        assert {k: call[k] for k in _EXPECTED_LIMITS} == _EXPECTED_LIMITS


def test_multi_batch_order_preserved_across_batches():
    tokens = [f"syn{i}" for i in range(h.MAX_TOKENS_PER_BATCH + 3)]
    accepted = {tokens[0], tokens[-1]}
    checker = SpanishHunspellPipeChecker(_FakePipeTransport(accepted))
    result = checker.check_tokens(tokens)
    assert result[0] is True and result[-1] is True
    assert sum(result) == 2
    assert len(result) == len(tokens)


def test_oversize_and_over_request_refuse_before_transport():
    transport = _FakePipeTransport()
    checker = SpanishHunspellPipeChecker(transport)
    with pytest.raises(h.ParityInputError):
        checker.check_tokens(["a" * (h.MAX_TOKEN_BYTES + 1)])
    with pytest.raises(h.ParityInputError):
        checker.check_tokens(["syn"] * (h.MAX_TOKENS_PER_REQUEST + 1))
    assert transport.calls == []


@pytest.mark.parametrize(
    "payload",
    [
        b"*\n\n",  # missing heading
        h.PHASE_B_PIPE_HEADING + b"*\n",  # missing block blank line
        h.PHASE_B_PIPE_HEADING + b"?bad\n\n",  # unknown marker
        h.PHASE_B_PIPE_HEADING + b"*\n\ntrailing",  # trailing bytes
    ],
)
def test_malformed_responses_fail_closed(payload):
    checker = SpanishHunspellPipeChecker(_MalformedTransport(payload))
    with pytest.raises(h.PhaseBParseError) as excinfo:
        checker.check_tokens(["synzzsecret"])
    assert str(excinfo.value) == h._PHASE_B_FAILURE_MESSAGE
    assert "synzzsecret" not in str(excinfo.value)


def test_transport_failure_collapses_to_fixed_error():
    transport = _RaisingTransport()
    checker = SpanishHunspellPipeChecker(transport)
    with pytest.raises(h.ParityTransportError) as excinfo:
        checker.check_tokens(["synxx"])
    assert "synxx" not in str(excinfo.value)


def test_coverage_layer_wraps_success_and_failure():
    ok = compute_spanish_hunspell_coverage(
        ["syncasa", "synxx"],
        checker=SpanishHunspellPipeChecker(_FakePipeTransport({"syncasa"})),
    )
    assert ok.outcome == "has_uncovered"
    assert (ok.n_tokens, ok.n_covered, ok.n_uncovered) == (2, 1, 1)

    with pytest.raises(SpanishHunspellUnavailableError):
        compute_spanish_hunspell_coverage(
            ["synxx"], checker=SpanishHunspellPipeChecker(_RaisingTransport())
        )


def test_constructor_rejects_transport_without_run_pipe_batch():
    with pytest.raises(h.ParityInputError):
        SpanishHunspellPipeChecker(object())


def test_checker_module_has_no_process_network_or_selection():
    import cslm.data.spanish_hunspell_pipe_checker as mod

    for name in ("subprocess", "urllib", "socket"):
        assert not hasattr(mod, name)
    assert not hasattr(SpanishHunspellPipeChecker, "select_mode")
    assert not hasattr(SpanishHunspellPipeChecker, "select_candidate")


def _load_runner():
    script = Path(__file__).resolve().parents[1] / "scripts" / "run_hunspell_per_token_parity.py"
    spec = importlib.util.spec_from_file_location("run_hunspell_per_token_parity", script)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_runner_reexports_shared_symbols_and_keeps_selection_enum():
    runner = _load_runner()
    assert runner.parse_pipe_stream_response is h.parse_pipe_stream_response
    assert runner.build_pipe_stream_stdin is h.build_pipe_stream_stdin
    assert runner.ParityInputError is h.ParityInputError
    assert runner.MembershipResult is h.MembershipResult
    assert runner.PHASE_B_PIPE_HEADING is h.PHASE_B_PIPE_HEADING
    assert runner.MEMBERSHIP_LABELS is h.MEMBERSHIP_LABELS
    assert runner.SELECTED_MODE_ENUM == ("PIPE_STREAM", "SINGLE_TOKEN_LIST", "NONE")


@pytest.mark.parametrize(
    "transport",
    list(_COLLAPSING_TRANSPORTS.values()),
    ids=list(_COLLAPSING_TRANSPORTS.keys()),
)
def test_operational_failures_collapse_to_fixed_transport_message(transport):
    checker = SpanishHunspellPipeChecker(transport)
    with pytest.raises(h.ParityTransportError) as excinfo:
        checker.check_tokens([_TOKEN])
    message = str(excinfo.value)
    assert message == h.PIPE_STREAM_TRANSPORT_FAILURE_MESSAGE
    assert _TOKEN not in message  # no invented token
    assert _SECRET not in message  # no raw fragment / underlying exception text
    assert "not-bytes" not in message
    assert excinfo.value.__cause__ is None  # no chained original exception


def test_keyboard_interrupt_propagates_unchanged():
    checker = SpanishHunspellPipeChecker(_ExceptionTransport(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        checker.check_tokens([_TOKEN])


def test_system_exit_propagates_unchanged():
    checker = SpanishHunspellPipeChecker(_ExceptionTransport(SystemExit(2)))
    with pytest.raises(SystemExit):
        checker.check_tokens([_TOKEN])
