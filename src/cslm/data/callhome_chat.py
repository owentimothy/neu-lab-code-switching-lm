"""Source-faithful CHAT (`.cha`) reader for CALLHOME — permissive and strict paths.

This module now exposes two intentionally different reading paths over the same
CHAT dataclasses (``CallhomeTier``, ``CallhomeUtterance``, ``CallhomeTranscript``):

* **Permissive** — ``parse_chat_lines`` / ``parse_chat_file``. These are the
  *survey / diagnostic* readers. They tolerate messy input: blank lines are
  skipped, continuation-like and unknown lines are recorded as ``parser_warnings``
  and their text is dropped, and orphan dependent tiers warn and skip. They never
  fail closed. Their purpose is structure scanning, warning counting, and legacy
  permissive inspection — not building model-training data.

* **Strict** — ``read_chat_transcript`` (raises ``StrictChatReaderError``). This is
  the **sole reader authorized for future condition-dataset construction**
  (``EnglishMono``, ``SpanishMono``, ``MonoCont``, ``CsCont``). It fails closed:
  it decodes exactly once as strict UTF-8, rejects a BOM or a literal ``U+FFFD``,
  requires an exact reconstructed ``@UTF8`` first logical line, reconstructs
  continuations under a strict grammar (or aborts), validates tier structure, and
  finally rejects *any* transcript- or utterance-level parser warning. Silent
  encoding damage or dropped continuation text would alter the actual training
  material and inject a preprocessing confound into the principal
  ``CsCont − MonoCont`` comparison; failing closed makes that class of corruption
  impossible.

The two paths share only the small, content-neutral tier-*dispatch* helper
(``_dispatch_logical_tier``) so they agree on what a header / main tier / dependent
tier is. They do **not** share a reconstruction policy: permissive reconstruction
drops continuations, strict reconstruction rebuilds or aborts.

Like the Bangor layer, both paths are **source-faithful only**: they preserve
header lines, main speaker tiers, and dependent tiers verbatim, and do **not**
tokenize, clean, normalize disfluencies, language-label tokens, or project into
``UtteranceRow``. This scaffold is developed and tested against **synthetic**
`.cha` content; real CALLHOME transcripts stay local / gitignored (see
``docs/callhome_format_audit.md``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# Dependent tiers that carry media / time alignment (captured onto the utterance).
_MEDIA_TIER_PREFIXES = ("%snd", "%mov")


@dataclass(frozen=True)
class CallhomeTier:
    """A single dependent tier line, preserved verbatim."""

    prefix: str  # marker before the colon, e.g. "%mor"
    value: str  # raw text after the colon


@dataclass
class CallhomeUtterance:
    """One main speaker tier and the dependent tiers attached to it."""

    conversation_id: str
    source_file: str
    speaker_id: str
    turn_index: int
    raw_main_tier_text: str
    dependent_tiers: list[CallhomeTier] = field(default_factory=list)
    language: str | None = None
    media_id: str | None = None
    parser_warnings: list[str] = field(default_factory=list)


@dataclass
class CallhomeTranscript:
    """A parsed CHAT transcript: headers + ordered utterances."""

    conversation_id: str
    source_file: str
    headers: dict[str, list[str]] = field(default_factory=dict)
    utterances: list[CallhomeUtterance] = field(default_factory=list)
    parser_warnings: list[str] = field(default_factory=list)


def _split_marker(line: str) -> tuple[str, str]:
    """Split a CHAT line into ``(marker, value)`` on the first colon.

    A line with no colon (e.g. ``@Begin``) yields ``(marker, "")``. The value is
    stripped of surrounding whitespace (CHAT separates marker and value with a
    tab); the raw text after the tab is otherwise preserved.
    """
    if ":" in line:
        marker, value = line.split(":", 1)
        return marker.strip(), value.strip()
    return line.strip(), ""


def _infer_first_language(value: str) -> str | None:
    """Return the first language token from an ``@Languages`` value, or ``None``."""
    tokens = re.findall(r"[A-Za-z]+", value)
    return tokens[0] if tokens else None


# ---------------------------------------------------------------------------
# Shared tier dispatch (used by both the permissive and strict paths)
# ---------------------------------------------------------------------------


@dataclass
class _DispatchState:
    """Mutable state threaded through tier dispatch for one transcript."""

    transcript: CallhomeTranscript
    language: str | None = None
    current: CallhomeUtterance | None = None
    turn_index: int = 0


def _dispatch_logical_tier(state: _DispatchState, line: str) -> str | None:
    """Dispatch one ``@`` / ``*`` / ``%`` logical tier line into ``state``.

    This is the single tier-dispatch semantics shared by the permissive and strict
    paths, so both agree on what a header / main tier / dependent tier is without
    sharing a reconstruction policy. It performs no continuation, blank, or
    unknown-line handling — the caller has already reconstructed logical tiers.

    Returns the dependent-tier marker string when ``line`` is an **orphan**
    dependent tier (a ``%`` tier with no current main tier); the caller decides how
    to record that (the permissive path warns and skips; the strict path never
    reaches this case because strict tier validation rejects orphans earlier).
    Returns ``None`` in every other case.
    """
    first = line[:1]

    if first == "@":
        key, value = _split_marker(line)
        state.transcript.headers.setdefault(key, []).append(value)
        if key == "@Languages":
            state.language = _infer_first_language(value)
        return None

    if first == "*":
        marker, value = _split_marker(line)
        utterance = CallhomeUtterance(
            conversation_id=state.transcript.conversation_id,
            source_file=state.transcript.source_file,
            speaker_id=marker[1:].strip(),  # drop the leading '*'
            turn_index=state.turn_index,
            raw_main_tier_text=value,
            language=state.language,
        )
        state.transcript.utterances.append(utterance)
        state.current = utterance
        state.turn_index += 1
        return None

    if first == "%":
        marker, value = _split_marker(line)
        if state.current is None:
            return marker  # orphan dependent tier; caller records
        state.current.dependent_tiers.append(CallhomeTier(prefix=marker, value=value))
        if marker in _MEDIA_TIER_PREFIXES:
            state.current.media_id = value
        return None

    return None


def parse_chat_lines(lines: list[str], *, source_file: str) -> CallhomeTranscript:
    """Permissively parse CHAT ``lines`` into a :class:`CallhomeTranscript`.

    **Permissive survey / diagnostic reader.** This path never fails closed; it is
    for structure scanning, warning counting, and legacy permissive inspection. It
    is **not** the reader for building model-condition datasets — use the strict
    :func:`read_chat_transcript` for that.

    Behavior (deliberately minimal, unchanged):

    * ``@`` lines are headers; keys (including the ``@``) and values are stored in
      ``headers`` (a key may repeat, e.g. ``@ID``, so values are lists).
    * ``*`` lines start a new main speaker tier / utterance; ``turn_index``
      increments per main tier.
    * ``%`` lines are dependent tiers attached to the most recent main tier; a
      dependent tier before any main tier is recorded as a parser warning.
    * ``@Languages`` sets a simple nullable language carried onto later utterances;
      ``%snd`` / ``%mov`` set the utterance ``media_id``.
    * Continuation lines (leading whitespace) and unknown structural lines are
      recorded as parser warnings and otherwise skipped (not merged/tokenized).
    """
    conversation_id = Path(source_file).stem
    transcript = CallhomeTranscript(conversation_id=conversation_id, source_file=source_file)
    state = _DispatchState(transcript=transcript)

    for lineno, raw in enumerate(lines, start=1):
        line = raw.rstrip("\r\n")
        if line.strip() == "":
            continue

        first = line[:1]

        if first in ("@", "*", "%"):
            orphan_marker = _dispatch_logical_tier(state, line)
            if orphan_marker is not None:
                transcript.parser_warnings.append(
                    f"orphan dependent tier {orphan_marker!r} before any speaker tier "
                    f"(line {lineno})"
                )
            continue

        if first in (" ", "\t"):
            transcript.parser_warnings.append(f"unmerged continuation line (line {lineno})")
            continue

        transcript.parser_warnings.append(f"unknown structural line (line {lineno})")

    return transcript


def parse_chat_file(path: str | Path) -> CallhomeTranscript:
    """Permissively parse a CHAT ``.cha`` file into a :class:`CallhomeTranscript`.

    **Permissive survey / diagnostic reader** (see :func:`parse_chat_lines`). Reads
    the file as UTF-8 and records — rather than rejects — malformed structure. Do
    **not** use this to build model-condition datasets; the strict
    :func:`read_chat_transcript` is the sole reader authorized for that.
    """
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        lines = f.readlines()
    return parse_chat_lines(lines, source_file=path.name)


# ---------------------------------------------------------------------------
# Strict reader — the sole reader authorized for future condition construction
# ---------------------------------------------------------------------------

_UTF8_BOM = b"\xef\xbb\xbf"
_UTF8_HEADER = "@UTF8"
_REPLACEMENT_CHAR = "\ufffd"

# Fixed, content-free strict-reader failure categories. No path, filename,
# transcript text, tier marker, line number, byte offset, or byte sequence may
# ever appear in a raised StrictChatReaderError — only one of these constants.
_READ_FAILED = "strict CHAT read failed"
_DECODE_FAILED = "strict UTF-8 decode failed"
_CONTINUATION_VIOLATED = "CHAT continuation grammar violated"
_TIER_MALFORMED = "malformed CHAT tier"
_HEADER_MALFORMED = "missing or malformed @UTF8 header"


class StrictChatReaderError(Exception):
    """Every strict-read failure surfaces as this, with a fixed content-free message.

    The message is one of a closed set of category constants. The exception never
    carries a path, filename, transcript fragment, speaker/tier marker, line
    number, byte offset, offending bytes, or a chained original exception:
    instances satisfy ``__cause__ is None`` and ``__context__ is None`` so no
    protected content leaks through the exception chain.
    """


def _read_bytes_strict(path: Path) -> bytes:
    """Read raw bytes from ``path``, converting any failure to a sanitized error.

    ``KeyboardInterrupt`` / ``SystemExit`` are ``BaseException`` and are **not**
    caught, so they propagate as the exact same object. Ordinary failures
    (``FileNotFoundError``, ``PermissionError``, generic ``OSError``, ...) are
    caught, reduced to a content-free category, and re-raised **after** the
    ``except`` block exits so the resulting error has no ``__context__``/``__cause__``
    and exposes no path.
    """
    failure: str | None = None
    data: bytes | None = None
    try:
        data = path.read_bytes()
    except Exception:  # never BaseException: KeyboardInterrupt/SystemExit propagate
        failure = _READ_FAILED
    if failure is not None:
        raise StrictChatReaderError(failure)
    assert data is not None  # for type-checkers; unreachable when failure is None
    return data


def _decode_strict(data: bytes) -> str:
    """Decode ``data`` as strict UTF-8, rejecting a BOM and any literal ``U+FFFD``.

    No encoding sniffing, fallback, or retry: a BOM prefix, a decode error, or a
    literal replacement character each aborts. The decode error is converted to a
    content-free category and raised after the ``except`` block exits.
    """
    if data.startswith(_UTF8_BOM):
        raise StrictChatReaderError(_DECODE_FAILED)

    failure: str | None = None
    text: str | None = None
    try:
        text = data.decode("utf-8")  # strict errors; no fallback
    except Exception:  # never BaseException
        failure = _DECODE_FAILED
    if failure is not None:
        raise StrictChatReaderError(_DECODE_FAILED)
    assert text is not None  # for type-checkers; unreachable when failure is None

    if _REPLACEMENT_CHAR in text:
        raise StrictChatReaderError(_DECODE_FAILED)
    return text


def _split_physical_lines(text: str) -> list[str]:
    """Split decoded text into physical lines on LF, stripping a single trailing CR.

    This is a content-neutral end-of-line helper only (so a CRLF file behaves like
    an LF file); it performs no other normalization. "Exact empty physical line" in
    the strict grammar means the resulting line is exactly ``""`` — a SPACE-only
    line is never empty.
    """
    return [line[:-1] if line.endswith("\r") else line for line in text.split("\n")]


def _reconstruct_strict_logical_lines(physical_lines: list[str]) -> list[str]:
    """Reconstruct strict logical tier lines from physical lines, or abort.

    Physical-line rules (distinct from the permissive path, which drops
    continuations):

    * exact empty physical line (``""``) — ends continuation ownership;
    * TAB-prefixed line — a continuation of the immediately preceding owner tier;
      an orphan continuation (no current owner) aborts;
    * SPACE-prefixed line — malformed (a SPACE-first line is never blank) → abort;
    * ``@`` / ``*`` / ``%`` line — begins a new logical-tier owner;
    * any other line — unknown structural line → abort.

    A valid continuation has exactly one leading TAB, a payload that does not begin
    with TAB or SPACE, and at least one non-whitespace character. The join happens
    only at the physical continuation boundary: the owner fragment's trailing
    horizontal layout whitespace is removed with ``rstrip(" \\t")`` (never a bare
    ``rstrip()``), the single leading TAB is removed from the continuation, and the
    two are joined with exactly one ``U+0020``. Punctuation and interior whitespace
    are never normalized.
    """
    logical: list[str] = []
    owner_index: int | None = None  # index into `logical` of the current owner

    for line in physical_lines:
        if line == "":
            owner_index = None  # exact empty physical line ends ownership
            continue

        first = line[:1]

        if first == "\t":
            if owner_index is None:
                raise StrictChatReaderError(_CONTINUATION_VIOLATED)  # orphan continuation
            payload = line[1:]  # remove exactly the one required leading TAB
            if payload[:1] in (" ", "\t"):
                raise StrictChatReaderError(_CONTINUATION_VIOLATED)  # extra leading ws
            if payload.strip() == "":
                raise StrictChatReaderError(_CONTINUATION_VIOLATED)  # empty payload
            owner_fragment = logical[owner_index].rstrip(" \t")
            logical[owner_index] = owner_fragment + " " + payload
            continue

        if first == " ":
            raise StrictChatReaderError(_CONTINUATION_VIOLATED)  # SPACE-first: malformed

        if first in ("@", "*", "%"):
            logical.append(line)
            owner_index = len(logical) - 1
            continue

        raise StrictChatReaderError(_TIER_MALFORMED)  # unknown structural line

    return logical


def _validate_strict_tiers(logical: list[str]) -> None:
    """Validate reconstructed logical tiers, aborting on any malformed tier.

    Header (``@``) lines are lenient (``@Begin``/``@End`` have no colon). Main
    (``*``) and dependent (``%``) tiers must be colon-bearing, have a non-empty
    marker, and separate marker from value with a TAB; a dependent tier before any
    main tier is an orphan. Any violation aborts the strict read.
    """
    seen_main = False
    for line in logical:
        first = line[:1]
        if first == "@":
            continue
        if first == "*":
            _validate_main_tier(line)
            seen_main = True
        elif first == "%":
            if not seen_main:
                raise StrictChatReaderError(_TIER_MALFORMED)  # orphan dependent tier
            _validate_dependent_tier(line)
        else:
            # Unreachable: reconstruction only emits @/*/% owner lines.
            raise StrictChatReaderError(_TIER_MALFORMED)


def _validate_main_tier(line: str) -> None:
    """Abort unless ``line`` is a well-formed ``*speaker:<TAB>value`` main tier."""
    if ":" not in line:
        raise StrictChatReaderError(_TIER_MALFORMED)  # colonless main tier
    marker, value = line.split(":", 1)
    if marker[1:].strip() == "":
        raise StrictChatReaderError(_TIER_MALFORMED)  # empty / whitespace-only speaker marker
    if not value.startswith("\t"):
        raise StrictChatReaderError(_TIER_MALFORMED)  # missing required TAB after colon


def _validate_dependent_tier(line: str) -> None:
    """Abort unless ``line`` is a well-formed ``%marker:<TAB>value`` dependent tier."""
    if ":" not in line:
        raise StrictChatReaderError(_TIER_MALFORMED)  # colonless dependent tier
    marker, value = line.split(":", 1)
    if marker[1:].strip() == "":
        raise StrictChatReaderError(_TIER_MALFORMED)  # empty / whitespace-only dependent marker
    if not value.startswith("\t"):
        raise StrictChatReaderError(_TIER_MALFORMED)  # missing required TAB after colon


def _dispatch_strict(logical: list[str], *, source_file: str) -> CallhomeTranscript:
    """Build a transcript from validated strict logical tiers via shared dispatch."""
    conversation_id = Path(source_file).stem
    transcript = CallhomeTranscript(conversation_id=conversation_id, source_file=source_file)
    state = _DispatchState(transcript=transcript)
    for line in logical:
        _dispatch_logical_tier(state, line)
    return transcript


def read_chat_transcript(path: str | Path) -> CallhomeTranscript:
    """Strictly read a CHAT ``.cha`` file, or raise :class:`StrictChatReaderError`.

    **The sole reader authorized for future condition-dataset construction**
    (``EnglishMono``, ``SpanishMono``, ``MonoCont``, ``CsCont``). The future
    condition builder must use only this reader and must never call the permissive
    :func:`parse_chat_file` / :func:`parse_chat_lines`.

    Runs, in order, with no fallback and no retry: read raw bytes; reject a UTF-8
    BOM; decode exactly once as strict UTF-8; reject a literal ``U+FFFD``; split
    into physical lines; reconstruct strict logical lines; require the first
    reconstructed logical line to equal exactly ``@UTF8``; validate strict tier
    structure; dispatch through the shared tier semantics; reject **any**
    transcript- or utterance-level parser warning; return only a warning-free
    transcript. A failed file yields no partial transcript.
    """
    path = Path(path)

    data = _read_bytes_strict(path)
    text = _decode_strict(data)
    physical_lines = _split_physical_lines(text)
    logical = _reconstruct_strict_logical_lines(physical_lines)

    if not logical or logical[0] != _UTF8_HEADER:
        raise StrictChatReaderError(_HEADER_MALFORMED)

    _validate_strict_tiers(logical)

    transcript = _dispatch_strict(logical, source_file=path.name)

    # Mandatory post-dispatch warning rejection: even though tier dispatch is
    # reused, any warning it (or reused semantics) could surface becomes an
    # immediate strict failure, so a returned strict transcript is warning-free by
    # construction. This check is intentionally separate from earlier validation.
    if transcript.parser_warnings:
        raise StrictChatReaderError(_READ_FAILED)
    for utterance in transcript.utterances:
        if utterance.parser_warnings:
            raise StrictChatReaderError(_READ_FAILED)

    return transcript
