"""Shared, pure PIPE_STREAM protocol primitives for Direct-Hunspell coverage.

This module is the single source of truth for the reviewed PIPE_STREAM (``-a``)
protocol contract: the exact defensive limits, token validation and batching, the
strict response parser, the internal :class:`MembershipResult`, the fixed
non-sensitive exception hierarchy, the ``build_pipe_stream_stdin`` builder, and the
:class:`PipeStreamTransport` boundary.

It performs no I/O.  It launches no process and imports no CLI script.  Raw process
streams are handled only transiently inside the parser boundary and are never
returned, logged, embedded in errors, or exposed.  Both the parity runner and the
concrete offline checker import from here so the approved parser contract is never
duplicated.  The real bounded subprocess/Docker transport is a separate, still-closed
gate; only the :class:`PipeStreamTransport` Protocol lives here.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

# --- Exact approved defensive limits (do not raise automatically after failure).
MAX_TOKEN_BYTES = 256  # defensive policy choice
MAX_TOKENS_PER_BATCH = 256  # proposed ceiling, suitability tested synthetically
MAX_TOKENS_PER_REQUEST = 10_000  # defensive policy choice
BATCH_TIMEOUT_SECONDS = 30  # proposed ceiling, suitability tested synthetically
MAX_STDOUT_BYTES = 2 * 1024 * 1024  # defensive hard ceiling (terminate midstream)
MAX_STDERR_BYTES = 64 * 1024  # defensive hard ceiling (terminate midstream)
TERMINATION_GRACE_SECONDS = 1.0  # exactly one second grace before SIGKILL

# Fixed internal membership labels; never lexical, never a caller-facing verdict.
MEMBERSHIP_ACCEPTED = "ACCEPTED"
MEMBERSHIP_REJECTED = "REJECTED"
MEMBERSHIP_LABELS: tuple[str, ...] = (MEMBERSHIP_ACCEPTED, MEMBERSHIP_REJECTED)
PHASE_B_PIPE_HEADING = (
    b"@(#) International Ispell Version 3.2.06 (but really Hunspell 1.7.3)\n"
)


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

# One fixed, non-sensitive message for every transport-boundary failure.  It must
# carry no token, response fragment, path, exception detail, or subprocess data.
PIPE_STREAM_TRANSPORT_FAILURE_MESSAGE = "PIPE_STREAM transport did not complete safely"


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
# Internal non-lexical result type.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class MembershipResult:
    """One internal non-lexical result, preserving only ordinal and membership."""

    ordinal: int
    membership: str


# ---------------------------------------------------------------------------
# Strict PIPE_STREAM / SINGLE_TOKEN_LIST parsing (raw stays internal here).
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


def build_pipe_stream_stdin(tokens: Sequence[str]) -> bytes:
    """Build the exact PIPE_STREAM (``-a``) stdin for validated tokens."""
    prepared = validate_tokens(tokens)
    return b"".join(b"^" + token.encode("utf-8") + b"\n" for token in prepared)


class PipeStreamTransport(Protocol):
    """One bounded PIPE_STREAM batch transport (dependency-injected).

    ``run_pipe_batch`` receives the exact stdin bytes and the explicit per-batch
    limits, and returns raw stdout **only after** its implementation has verified
    zero-exit completion, a stderr within ``max_stderr_bytes``, no stdout/stderr
    overflow, completed supervision, and confirmed cleanup.  Timeout, nonzero exit,
    stderr-policy failure, overflow, worker failure, or unconfirmed cleanup must
    raise one fixed, non-sensitive :class:`ParityTransportError` carrying no stream
    or subprocess data.  Implementations must not be a CLI script and must not be
    imported from one.
    """

    def run_pipe_batch(
        self,
        stdin_bytes: bytes,
        *,
        timeout_seconds: float,
        max_stdout_bytes: int,
        max_stderr_bytes: int,
        grace_seconds: float,
    ) -> bytes: ...
