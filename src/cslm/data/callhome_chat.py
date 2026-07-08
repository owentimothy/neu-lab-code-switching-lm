"""Minimal, source-faithful CHAT (`.cha`) parser scaffold for CALLHOME.

This is the smallest safe first step toward CALLHOME ingestion. Like the Bangor
layer, it is **source-faithful only**: it preserves CHAT header lines, main
speaker tiers, and dependent tiers verbatim, and does **not** tokenize, clean,
normalize disfluencies, language-label tokens, or project into ``UtteranceRow``.
A later, separate module will handle projection (mirroring ``bangor_project``).

Scope note: this scaffold handles the common CHAT structure only. It is developed
and tested against **synthetic** `.cha` content; it does not attempt exhaustive
CA-CHAT edge-case coverage, and real CALLHOME transcripts stay local / gitignored
(see ``docs/callhome_format_audit.md``).
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


def parse_chat_lines(lines: list[str], *, source_file: str) -> CallhomeTranscript:
    """Parse CHAT ``lines`` into a source-faithful :class:`CallhomeTranscript`.

    Behavior (deliberately minimal):

    * ``@`` lines are headers; keys (including the ``@``) and values are stored
      in ``headers`` (a key may repeat, e.g. ``@ID``, so values are lists).
    * ``*`` lines start a new main speaker tier / utterance; ``turn_index``
      increments per main tier.
    * ``%`` lines are dependent tiers attached to the most recent main tier; a
      dependent tier before any main tier is recorded as a parser warning.
    * ``@Languages`` sets a simple nullable language carried onto later
      utterances; ``%snd`` / ``%mov`` set the utterance ``media_id``.
    * Continuation lines (leading whitespace) and unknown structural lines are
      recorded as parser warnings and otherwise skipped (not merged/tokenized).
    """
    conversation_id = Path(source_file).stem
    transcript = CallhomeTranscript(conversation_id=conversation_id, source_file=source_file)

    language: str | None = None
    current: CallhomeUtterance | None = None
    turn_index = 0

    for lineno, raw in enumerate(lines, start=1):
        line = raw.rstrip("\r\n")
        if line.strip() == "":
            continue

        first = line[:1]

        if first == "@":
            key, value = _split_marker(line)
            transcript.headers.setdefault(key, []).append(value)
            if key == "@Languages":
                language = _infer_first_language(value)
            continue

        if first == "*":
            marker, value = _split_marker(line)
            current = CallhomeUtterance(
                conversation_id=conversation_id,
                source_file=source_file,
                speaker_id=marker[1:].strip(),  # drop the leading '*'
                turn_index=turn_index,
                raw_main_tier_text=value,
                language=language,
            )
            transcript.utterances.append(current)
            turn_index += 1
            continue

        if first == "%":
            marker, value = _split_marker(line)
            if current is None:
                transcript.parser_warnings.append(
                    f"orphan dependent tier {marker!r} before any speaker tier (line {lineno})"
                )
                continue
            current.dependent_tiers.append(CallhomeTier(prefix=marker, value=value))
            if marker in _MEDIA_TIER_PREFIXES:
                current.media_id = value
            continue

        if first in (" ", "\t"):
            transcript.parser_warnings.append(f"unmerged continuation line (line {lineno})")
            continue

        transcript.parser_warnings.append(f"unknown structural line (line {lineno})")

    return transcript


def parse_chat_file(path: str | Path) -> CallhomeTranscript:
    """Parse a CHAT ``.cha`` file into a :class:`CallhomeTranscript`.

    Reads the file as UTF-8. (CALLHOME Spanish from LDC is ISO-8859-1; encoding
    normalization is a future ingestion concern, out of scope for this scaffold.)
    """
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        lines = f.readlines()
    return parse_chat_lines(lines, source_file=path.name)
