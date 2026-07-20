"""Offline concrete Spanish Hunspell checker using the reviewed PIPE_STREAM mode.

This implements the ``SpanishHunspellCoverageEvaluator`` checker boundary
(``check_tokens``) over the shared strict PIPE_STREAM protocol.  It is
dependency-injected with a :class:`PipeStreamTransport`; ordinary tests supply a
fake in-memory transport.

It launches nothing, reads no resource, imports no CLI parity runner, and performs
no real subprocess/Docker/network work.  Raw responses stay inside the shared parser
boundary and never enter results, errors, logs, or diagnostics.  Coverage is
descriptive only: a Boolean per token records whether the injected checker accepted
it.  This class never validates source language, cleans, promotes, or routes rows.
The concrete bounded subprocess/Docker transport is a separate, still-closed gate and
is neither implemented nor imported here.
"""

from __future__ import annotations

from collections.abc import Sequence

from cslm.data.hunspell_pipe_stream import (
    BATCH_TIMEOUT_SECONDS,
    MAX_STDERR_BYTES,
    MAX_STDOUT_BYTES,
    MEMBERSHIP_ACCEPTED,
    PIPE_STREAM_TRANSPORT_FAILURE_MESSAGE,
    TERMINATION_GRACE_SECONDS,
    ParityInputError,
    ParityTransportError,
    PipeStreamTransport,
    batch_tokens,
    build_pipe_stream_stdin,
    parse_pipe_stream_response,
    validate_tokens,
)


class SpanishHunspellPipeChecker:
    """A ``check_tokens`` checker that asks pinned Hunspell via PIPE_STREAM.

    The injected transport performs one bounded ``-a`` batch and returns stdout only
    after verified clean completion and confirmed cleanup; any operational failure
    raises the fixed non-sensitive transport exception.  This checker validates
    (never normalizes) tokens, batches them under the shared limits, passes every
    exact limit explicitly, parses with the shared strict parser, and returns exactly
    one Boolean per input token, preserving order and duplicates.
    """

    def __init__(self, transport: PipeStreamTransport) -> None:
        if not callable(getattr(transport, "run_pipe_batch", None)):
            raise ParityInputError("transport must provide a callable run_pipe_batch")
        self._transport = transport

    def check_tokens(self, normalized_tokens: Sequence[str]) -> tuple[bool, ...]:
        """Return one Boolean per already-normalized token; fail closed otherwise."""
        prepared = validate_tokens(normalized_tokens)
        if not prepared:
            return ()
        decisions: list[bool] = []
        for batch in batch_tokens(prepared):
            stdin_bytes = build_pipe_stream_stdin(batch)
            try:
                raw = self._transport.run_pipe_batch(
                    stdin_bytes,
                    timeout_seconds=BATCH_TIMEOUT_SECONDS,
                    max_stdout_bytes=MAX_STDOUT_BYTES,
                    max_stderr_bytes=MAX_STDERR_BYTES,
                    grace_seconds=TERMINATION_GRACE_SECONDS,
                )
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception:
                # Collapse every operational failure (timeout, nonzero exit,
                # overflow, worker failure, unconfirmed cleanup, or a
                # transport-supplied ParityTransportError) to one fixed message,
                # dropping any original exception, so no stream or subprocess
                # detail can escape.
                raise ParityTransportError(
                    PIPE_STREAM_TRANSPORT_FAILURE_MESSAGE
                ) from None
            if not isinstance(raw, bytes) or len(raw) > MAX_STDOUT_BYTES:
                raise ParityTransportError(PIPE_STREAM_TRANSPORT_FAILURE_MESSAGE)
            results = parse_pipe_stream_response(raw, batch)
            del raw  # discard the raw stdout reference immediately after parsing
            decisions.extend(
                result.membership == MEMBERSHIP_ACCEPTED for result in results
            )
        return tuple(decisions)
