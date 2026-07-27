"""Narrow CALLHOME CHAT-to-training-row construction.

This module is intentionally source-specific. It consumes only transcripts returned
by :func:`cslm.data.callhome_chat.read_chat_transcript`, removes a small reviewed
set of CHAT surface controls, preserves spoken lexical material, and emits local
training rows with opaque provenance.

It does not perform language identification, condition routing, tokenizer work, or
model training. Unknown CHAT residue fails closed so real-data execution can stop
for a narrow review instead of silently changing the corpus.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import unicodedata
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable

from cslm.data.callhome_chat import CallhomeTranscript, read_chat_transcript

SOURCE_TO_LANGUAGE: dict[str, str] = {
    "callhome_eng": "eng",
    "callhome_spa": "spa",
}

EXCLUSION_NO_LEXICAL_MATERIAL = "no_lexical_material"
ERROR_LANGUAGE_CONFLICT = "CALLHOME transcript language conflict"
ERROR_UNRESOLVED_CHAT_CONTROL = "unresolved CHAT control residue"
ERROR_UNSUPPORTED_SOURCE = "unsupported CALLHOME source"
ERROR_OUTPUT_EXISTS = "CALLHOME output already exists"

_RESIDUE_TOKENS = frozenset({"xxx", "yyy", "www", "0"})
_CHAT_TERMINATORS = frozenset(
    {"+/.", "+//.", "+...", "+..?", "++", "+^", "+<", "+/?"}
)
_STANDALONE_CHAT_CONTROLS = frozenset({"[/]", "[//]", "[<]", "[>]"})
_PAUSE_MARKER = re.compile(r"^\(\.{1,3}\)$")
_FILLED_PAUSE = re.compile(r"^&-([\wÀ-ÖØ-öø-ÿ]+)$", flags=re.UNICODE)
_LANGUAGE_TOKEN = re.compile(r"[A-Za-z]+")


class CallhomeTrainingRowsError(Exception):
    """Fixed-category failure for CALLHOME training-row construction."""


@dataclass(frozen=True)
class CallhomeTrainingRow:
    """One local-only, de-identified CALLHOME training row."""

    source: str
    conversation_ref: str
    speaker_ref: str
    turn_index: int
    row_id: str
    split: str | None
    text: str

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "conversation_ref": self.conversation_ref,
            "speaker_ref": self.speaker_ref,
            "turn_index": self.turn_index,
            "row_id": self.row_id,
            "split": self.split,
            "text": self.text,
        }


@dataclass(frozen=True)
class CallhomePopulationRows:
    """Rows and aggregate-only exclusion counts for one source population."""

    source: str
    files_read: int
    utterances_seen: int
    rows: tuple[CallhomeTrainingRow, ...]
    exclusions: dict[str, int]


def _opaque_ref(raw: str, *, domain: str, salt: str = "") -> str:
    digest = hashlib.sha256(f"{domain}\0{salt}\0{raw}".encode("utf-8")).hexdigest()[:16]
    return f"{domain}_{digest}"


def _contains_lexical_material(text: str) -> bool:
    return any(character.isalpha() for character in text)


def _has_unresolved_control(text: str) -> bool:
    if any(unicodedata.category(character) in {"Cc", "Cf"} for character in text):
        return True
    for token in text.split():
        if any(character in token for character in "[]<>"):
            return True
        if token.startswith("&") or token.startswith("+"):
            return True
    return False


def clean_chat_surface(text: str) -> str | None:
    """Return reviewed MLM surface text, ``None`` if no lexical material remains.

    Supported controls are deliberately narrow:

    * exact residue tokens: ``xxx``, ``yyy``, ``www``, ``0``;
    * exact CHAT terminators fixed by the existing screening code;
    * standalone retracing/overlap controls: ``[/]``, ``[//]``, ``[<]``, ``[>]``;
    * one-to-three-dot pause markers;
    * ``&=...`` non-speech events;
    * ``&-word`` filled-pause/nonword forms, preserving ``word``.

    Any remaining CHAT-looking or Unicode control residue fails closed.
    """
    normalized = unicodedata.normalize("NFC", text)
    kept: list[str] = []
    for token in normalized.split():
        lowered = token.lower()
        if lowered in _RESIDUE_TOKENS:
            continue
        if token in _CHAT_TERMINATORS or token in _STANDALONE_CHAT_CONTROLS:
            continue
        if _PAUSE_MARKER.fullmatch(token):
            continue
        if token.startswith("&="):
            continue
        filled_pause = _FILLED_PAUSE.fullmatch(token)
        if filled_pause:
            kept.append(filled_pause.group(1))
            continue
        kept.append(token)

    cleaned = " ".join(kept)
    if _has_unresolved_control(cleaned):
        raise CallhomeTrainingRowsError(ERROR_UNRESOLVED_CHAT_CONTROL)
    if not _contains_lexical_material(cleaned):
        return None
    return cleaned


def _declared_languages(transcript: CallhomeTranscript) -> tuple[str, ...]:
    values = transcript.headers.get("@Languages", [])
    if not values:
        return ()
    return tuple(token.lower() for token in _LANGUAGE_TOKEN.findall(values[0]))


def rows_from_transcript(
    transcript: CallhomeTranscript,
    *,
    source: str,
) -> tuple[list[CallhomeTrainingRow], Counter[str]]:
    """Project one strict-reader transcript into local training rows."""
    expected_language = SOURCE_TO_LANGUAGE.get(source)
    if expected_language is None:
        raise CallhomeTrainingRowsError(ERROR_UNSUPPORTED_SOURCE)
    if _declared_languages(transcript) != (expected_language,):
        raise CallhomeTrainingRowsError(ERROR_LANGUAGE_CONFLICT)

    conversation_ref = _opaque_ref(transcript.source_file, domain="conv")
    rows: list[CallhomeTrainingRow] = []
    exclusions: Counter[str] = Counter()
    for utterance in transcript.utterances:
        if utterance.language != expected_language:
            raise CallhomeTrainingRowsError(ERROR_LANGUAGE_CONFLICT)
        cleaned = clean_chat_surface(utterance.raw_main_tier_text)
        if cleaned is None:
            exclusions[EXCLUSION_NO_LEXICAL_MATERIAL] += 1
            continue
        speaker_ref = _opaque_ref(
            utterance.speaker_id,
            domain="spk",
            salt=conversation_ref,
        )
        row_id = _opaque_ref(
            str(utterance.turn_index),
            domain="row",
            salt=f"{source}\0{conversation_ref}",
        )
        rows.append(
            CallhomeTrainingRow(
                source=source,
                conversation_ref=conversation_ref,
                speaker_ref=speaker_ref,
                turn_index=utterance.turn_index,
                row_id=row_id,
                split=None,
                text=cleaned,
            )
        )
    return rows, exclusions


def build_population_rows(
    paths: Iterable[Path],
    *,
    source: str,
) -> CallhomePopulationRows:
    """Read every sorted path exactly once with the strict reader."""
    if source not in SOURCE_TO_LANGUAGE:
        raise CallhomeTrainingRowsError(ERROR_UNSUPPORTED_SOURCE)

    rows: list[CallhomeTrainingRow] = []
    exclusions: Counter[str] = Counter()
    files_read = 0
    utterances_seen = 0
    for path in sorted(paths, key=lambda item: item.as_posix()):
        transcript = read_chat_transcript(path)
        files_read += 1
        utterances_seen += len(transcript.utterances)
        transcript_rows, transcript_exclusions = rows_from_transcript(
            transcript,
            source=source,
        )
        rows.extend(transcript_rows)
        exclusions.update(transcript_exclusions)

    return CallhomePopulationRows(
        source=source,
        files_read=files_read,
        utterances_seen=utterances_seen,
        rows=tuple(rows),
        exclusions=dict(sorted(exclusions.items())),
    )


def assign_conversation_splits(
    rows: Iterable[CallhomeTrainingRow],
    *,
    seed: int,
    train_fraction: float = 0.90,
    validation_fraction: float = 0.05,
) -> list[CallhomeTrainingRow]:
    """Assign deterministic splits by source and whole conversation."""
    if train_fraction <= 0 or validation_fraction < 0:
        raise ValueError("split fractions must be non-negative with train > 0")
    if train_fraction + validation_fraction >= 1:
        raise ValueError("split fractions must leave a non-empty test fraction")

    materialized = list(rows)
    conversations_by_source: dict[str, set[str]] = {
        source: set() for source in SOURCE_TO_LANGUAGE
    }
    for row in materialized:
        if row.source not in SOURCE_TO_LANGUAGE:
            raise CallhomeTrainingRowsError(ERROR_UNSUPPORTED_SOURCE)
        conversations_by_source[row.source].add(row.conversation_ref)

    split_by_key: dict[tuple[str, str], str] = {}
    for source, conversations in conversations_by_source.items():
        ordered = sorted(
            conversations,
            key=lambda conversation: hashlib.sha256(
                f"{seed}\0{source}\0{conversation}".encode("utf-8")
            ).hexdigest(),
        )
        n_conversations = len(ordered)
        n_train = round(n_conversations * train_fraction)
        n_validation = round(n_conversations * validation_fraction)
        for index, conversation in enumerate(ordered):
            if index < n_train:
                split = "train"
            elif index < n_train + n_validation:
                split = "validation"
            else:
                split = "test"
            split_by_key[(source, conversation)] = split

    return [
        replace(row, split=split_by_key[(row.source, row.conversation_ref)])
        for row in materialized
    ]


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _rows_bytes(rows: Iterable[CallhomeTrainingRow]) -> bytes:
    ordered = sorted(
        rows,
        key=lambda row: (row.source, row.conversation_ref, row.turn_index, row.row_id),
    )
    return b"".join(_json_bytes(row.to_dict()) for row in ordered)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _row_manifest(
    english: CallhomePopulationRows,
    spanish: CallhomePopulationRows,
    rows: list[CallhomeTrainingRow],
    *,
    seed: int,
) -> dict[str, object]:
    rows_by_source = Counter(row.source for row in rows)
    rows_by_split = Counter(row.split for row in rows)
    lexical_tokens_by_source: Counter[str] = Counter()
    for row in rows:
        lexical_tokens_by_source[row.source] += sum(
            1 for token in row.text.split() if any(character.isalpha() for character in token)
        )
    return {
        "format_version": 1,
        "seed": seed,
        "split_fractions": {"train": 0.90, "validation": 0.05, "test": 0.05},
        "sources": {
            english.source: {
                "files_read": english.files_read,
                "utterances_seen": english.utterances_seen,
                "rows_included": rows_by_source[english.source],
                "approximate_lexical_tokens": lexical_tokens_by_source[english.source],
                "exclusions": english.exclusions,
            },
            spanish.source: {
                "files_read": spanish.files_read,
                "utterances_seen": spanish.utterances_seen,
                "rows_included": rows_by_source[spanish.source],
                "approximate_lexical_tokens": lexical_tokens_by_source[spanish.source],
                "exclusions": spanish.exclusions,
            },
        },
        "rows_by_split": {
            split: rows_by_split[split] for split in ("train", "validation", "test")
        },
    }


def write_atomic_build(
    english: CallhomePopulationRows,
    spanish: CallhomePopulationRows,
    *,
    publish_dir: Path,
    seed: int,
) -> dict[str, str]:
    """Write one deterministic build directory and publish it atomically.

    ``publish_dir`` must not already exist. All staging occurs inside its parent,
    and a failed build removes the staging directory before re-raising.
    """
    if english.source != "callhome_eng" or any(
        row.source != "callhome_eng" for row in english.rows
    ):
        raise CallhomeTrainingRowsError(ERROR_UNSUPPORTED_SOURCE)
    if spanish.source != "callhome_spa" or any(
        row.source != "callhome_spa" for row in spanish.rows
    ):
        raise CallhomeTrainingRowsError(ERROR_UNSUPPORTED_SOURCE)
    if publish_dir.exists():
        raise CallhomeTrainingRowsError(ERROR_OUTPUT_EXISTS)

    all_rows = assign_conversation_splits(
        [*english.rows, *spanish.rows],
        seed=seed,
    )
    english_bytes = _rows_bytes(row for row in all_rows if row.source == "callhome_eng")
    spanish_bytes = _rows_bytes(row for row in all_rows if row.source == "callhome_spa")
    manifest_bytes = _json_bytes(_row_manifest(english, spanish, all_rows, seed=seed))
    checksums = {
        "english_rows.jsonl": _sha256(english_bytes),
        "manifest.json": _sha256(manifest_bytes),
        "spanish_rows.jsonl": _sha256(spanish_bytes),
    }
    checksums_bytes = _json_bytes(checksums)

    publish_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{publish_dir.name}.staging-",
            dir=publish_dir.parent,
        )
    )
    try:
        (staging / "english_rows.jsonl").write_bytes(english_bytes)
        (staging / "spanish_rows.jsonl").write_bytes(spanish_bytes)
        (staging / "manifest.json").write_bytes(manifest_bytes)
        (staging / "checksums.json").write_bytes(checksums_bytes)
        os.replace(staging, publish_dir)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return checksums
