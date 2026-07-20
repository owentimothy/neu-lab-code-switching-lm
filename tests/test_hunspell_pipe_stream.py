"""Tests for the shared pure PIPE_STREAM protocol module.

Only invented tokens and hand-built protocol byte strings are used.  No process,
resource, corpus, Docker, or network is involved.
"""

from __future__ import annotations

import pytest

from cslm.data import hunspell_pipe_stream as h


def _pipe(records: list[bytes]) -> bytes:
    """Build a valid PIPE_STREAM stream: heading, then record + blank per token."""
    return h.PHASE_B_PIPE_HEADING + b"".join(record + b"\n\n" for record in records)


def test_exact_defensive_limits():
    assert h.MAX_TOKEN_BYTES == 256
    assert h.MAX_TOKENS_PER_BATCH == 256
    assert h.MAX_TOKENS_PER_REQUEST == 10_000
    assert h.BATCH_TIMEOUT_SECONDS == 30
    assert h.MAX_STDOUT_BYTES == 2 * 1024 * 1024
    assert h.MAX_STDERR_BYTES == 64 * 1024
    assert h.TERMINATION_GRACE_SECONDS == 1.0


def test_exception_hierarchy_and_fixed_message():
    assert issubclass(h.ParityInputError, h.ParityHarnessError)
    assert issubclass(h.ParityTransportError, h.ParityHarnessError)
    assert issubclass(h.PhaseBParseError, h.ParityHarnessError)
    with pytest.raises(h.PhaseBParseError) as excinfo:
        h._phase_b_fail()
    assert str(excinfo.value) == h._PHASE_B_FAILURE_MESSAGE


def test_validate_tokens_accepts_and_copies():
    assert h.validate_tokens(["syna", "synb", "syna"]) == ("syna", "synb", "syna")
    assert h.validate_tokens([]) == ()


@pytest.mark.parametrize("bad", ["syntext", b"syntext", bytearray(b"x"), object()])
def test_validate_tokens_rejects_non_sequence_of_str(bad):
    with pytest.raises(h.ParityInputError):
        h.validate_tokens(bad)


def test_validate_tokens_rejects_bad_elements_without_echo():
    for bad in ([7], [""], ["syn two"], ["syn\ttwo"], ["syn\x00two"]):
        with pytest.raises(h.ParityInputError) as excinfo:
            h.validate_tokens(bad)
        assert "syn" not in str(excinfo.value)


def test_validate_tokens_enforces_byte_and_request_limits():
    with pytest.raises(h.ParityInputError):
        h.validate_tokens(["a" * (h.MAX_TOKEN_BYTES + 1)])
    with pytest.raises(h.ParityInputError):
        h.validate_tokens(["syn"] * (h.MAX_TOKENS_PER_REQUEST + 1))


def test_batch_tokens_preserves_order_and_bounds():
    tokens = tuple(f"syn{i}" for i in range(h.MAX_TOKENS_PER_BATCH + 1))
    batches = h.batch_tokens(tokens)
    assert len(batches) == 2
    assert len(batches[0]) == h.MAX_TOKENS_PER_BATCH
    assert len(batches[1]) == 1
    assert tuple(t for batch in batches for t in batch) == tokens
    assert h.batch_tokens(()) == ()


def test_build_pipe_stream_stdin_exact_bytes():
    assert h.build_pipe_stream_stdin(["syna", "synb"]) == b"^syna\n^synb\n"
    assert h.build_pipe_stream_stdin([]) == b""


def test_parse_accepts_star_and_root_forms():
    raw = _pipe([b"*", b"+ ROOT", b"- ROOT"])
    result = h.parse_pipe_stream_response(raw, ["syna", "synb", "sync"])
    assert [r.membership for r in result] == [h.MEMBERSHIP_ACCEPTED] * 3
    assert [r.ordinal for r in result] == [0, 1, 2]


def test_parse_rejects_hash_and_ampersand_forms():
    raw = _pipe([b"# synb 0", b"& sync 1 0: alt"])
    result = h.parse_pipe_stream_response(raw, ["synb", "sync"])
    assert [r.membership for r in result] == [h.MEMBERSHIP_REJECTED, h.MEMBERSHIP_REJECTED]


def test_parse_preserves_order_and_duplicates():
    raw = _pipe([b"*", b"# synb 0", b"*"])
    result = h.parse_pipe_stream_response(raw, ["syna", "synb", "syna"])
    assert [r.membership for r in result] == [
        h.MEMBERSHIP_ACCEPTED,
        h.MEMBERSHIP_REJECTED,
        h.MEMBERSHIP_ACCEPTED,
    ]


@pytest.mark.parametrize(
    "raw_builder",
    [
        lambda: b"*\n\n",  # missing heading
        lambda: h.PHASE_B_PIPE_HEADING + b"*\n",  # missing block blank line
        lambda: _pipe([b"*"]) + b"trailing",  # trailing bytes after exact cardinality
        lambda: _pipe([b"?bad"]),  # unknown marker
        lambda: _pipe([b"# synZZ 9"]),  # hash echo does not match the token
    ],
)
def test_parse_fails_closed_without_content(raw_builder):
    with pytest.raises(h.PhaseBParseError) as excinfo:
        h.parse_pipe_stream_response(raw_builder(), ["syna"])
    assert str(excinfo.value) == h._PHASE_B_FAILURE_MESSAGE
    assert "syna" not in str(excinfo.value)


def test_parse_requires_exact_cardinality():
    with pytest.raises(h.PhaseBParseError):
        h.parse_pipe_stream_response(_pipe([b"*"]), ["syna", "synb"])
    with pytest.raises(h.PhaseBParseError):
        h.parse_pipe_stream_response(_pipe([b"*", b"*"]), ["syna"])


def test_single_token_list_parse():
    assert h.parse_single_token_list_response(b"", "syna", ordinal=0).membership == (
        h.MEMBERSHIP_ACCEPTED
    )
    assert h.parse_single_token_list_response(b"syna\n", "syna", ordinal=1).membership == (
        h.MEMBERSHIP_REJECTED
    )
    with pytest.raises(h.PhaseBParseError):
        h.parse_single_token_list_response(b"other\n", "syna", ordinal=0)


def test_no_process_or_resource_imports():
    for name in ("subprocess", "urllib", "socket", "os"):
        assert not hasattr(h, name)
