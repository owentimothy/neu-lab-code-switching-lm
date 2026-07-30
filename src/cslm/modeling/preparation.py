"""Sealed, model-free preparation of frozen memberships.

The public readers and factories in this module are deliberately narrow.  They
accept frozen train/validation membership, never authorize ``test``, and emit
only arrays, aggregate records, and keyed pseudonyms.  No model class is
imported or instantiated here.
"""

from __future__ import annotations

import csv
import ctypes
import errno
import hashlib
import hmac
import importlib.metadata
import io
import json
import os
import platform
import re
import shutil
import stat
import sys
import sysconfig
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Iterable, Iterator, Literal, Mapping, Sequence

import numpy as np

from cslm.modeling.config import CONDITIONS, MAX_SEQUENCE_LENGTH, VOCAB_SIZE
from cslm.modeling.initialization import SMALL_PILOT_SEED_PLANS, TINY_SMOKE_SEED_PLANS
from cslm.modeling.masking import (
    ValidationMaskRecord,
    build_validation_mask_record,
    mask_packed_sequence,
)
from cslm.modeling.packing import PackedSequence, PackingResult, PackingRow, pack_rows
from cslm.tokenization.shared_wordpiece import (
    BACKEND_CORRECTION_ID,
    CONTINUATION_PREFIX,
    SPECIAL_TOKEN_IDS,
    protocol_configuration,
)

PREPARATION_PROTOCOL_VERSION = "neu_real_preparation_v1"
SYNTHETIC_PREPARATION_PROTOCOL_VERSION = "neu_synthetic_preparation_v1"
_SYNTHETIC_PRIVACY_RECONCILIATION_KEY = b"k" * 32
INTERNAL_TRACKER_VERSION = "5.4"
TOKENIZER_LOADER_PROTOCOL = "tokenizers.Tokenizer.from_file:add_special_tokens=false:v1"
APPROVED_PRIVATE_OUTPUT_ROOT = Path("~/NEU_LAB_frozen_artifacts/model_ready/real_preparation_v1/")
APPROVED_TOKENIZER_CHECKSUM_RECORD_SHA256 = (
    "25489e732b64ce63c0380012ea719571f9cb4fc6c369e43da920d2b45af55b8d"
)
APPROVED_CALLHOME_CHECKSUM_RECORD_SHA256 = (
    "840236bdd4c8f3d18898b02c824478dfbb663f160bc03d13590ae5ca4dc8003f"
)
APPROVED_CSCONT_CHECKSUM_RECORD_SHA256 = (
    "f06216f6588337c53100cf6066166f4979b3b06fe0f8a65c04e350fd8fcb0b3e"
)
CALLHOME_ARTIFACT_FORMAT_VERSION = 1
CSCONT_ARTIFACT_FORMAT_VERSION = 1
EXPOSURE_TOLERANCE_FRACTION = 0.01
MAX_SEALED_JSONL_LINE_BYTES = 1024 * 1024
PRIVATE_DIRECTORY_MODE = 0o700
PRIVATE_FILE_MODE = 0o600

_CONTROL_FILES = frozenset(
    {"checksums.json", "PREPARATION_MANIFEST.json", "CANDIDATE_COMPLETE.json"}
)
_CALLHOME_MEMBERSHIP_FILES = MappingProxyType(
    {
        "english_mono_rows.jsonl": "EnglishMono",
        "spanish_mono_rows.jsonl": "SpanishMono",
        "monocont_english_rows.jsonl": "MonoCont",
        "monocont_spanish_rows.jsonl": "MonoCont",
    }
)
_CSCONT_MEMBERSHIP_FILES = ("train_rows.jsonl", "validation_rows.jsonl")
_SERIALIZATION_SCHEMA = MappingProxyType(
    {
        "schema_version": 1,
        "input_and_masked_ids": "uint16",
        "attention_and_token_type_ids": "uint8",
        "labels": "int32",
        "label_ignore_index": -100,
        "records": "canonical_json_utf8_lf",
    }
)

Split = Literal["train", "validation"]
LanguageShard = Literal["english", "spanish"]
BlockKey = tuple[str, str, str | None]
MembershipIdentity = tuple[str, str, str, str, str | None, str, int]

_CALLHOME_KEYS = (
    "conversation_ref",
    "row_id",
    "source",
    "speaker_ref",
    "split",
    "text",
    "turn_index",
)
_CSCONT_KEYS = (
    "artifact_format_version",
    "component",
    "condition",
    "conversation_id",
    "document_id",
    "document_row_index",
    "lexical_tokens",
    "record_id",
    "row",
    "source",
    "split",
)
_BANGOR_ROW_KEYS = ("conversation_id", "source_word_ids", "text", "tokens")
_LEXICAL_TOP_LEVEL_KEYS = frozenset({"text", "tokens", "row"})
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class PreparationError(RuntimeError):
    """Privacy-safe preparation failure with no record values or paths."""


class ExposureAcceptanceError(PreparationError):
    """Fail-closed 1% exposure result carrying aggregate diagnostics only."""

    def __init__(self, diagnostics: Mapping[str, object]) -> None:
        super().__init__("projected non-padding exposure exceeds the approved tolerance")
        self.diagnostics = MappingProxyType(dict(diagnostics))


def canonical_json_bytes(value: Any) -> bytes:
    """Canonical JSON used by every preparation record."""
    return (
        json.dumps(_jsonable(value), ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _raise_fixed(message: str) -> None:
    """Raise a fixed exception from a frame containing no private input."""
    raise PreparationError(message)


@dataclass(frozen=True)
class _StableFileSnapshot:
    content: bytes = field(repr=False)
    device: int
    inode: int
    size: int
    mode: int
    uid: int


def _safe_relative_name(name: str) -> str:
    if not isinstance(name, str) or not name or "\\" in name or "\x00" in name:
        raise PreparationError("artifact name is not a canonical relative path")
    path = Path(name)
    parts = path.parts
    if (
        path.is_absolute()
        or not parts
        or any(part in {"", ".", ".."} for part in parts)
        or path.as_posix() != name
    ):
        raise PreparationError("artifact name is not a canonical relative path")
    return name


def _directory_open_flags() -> int:
    return os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)


def _regular_open_flags() -> int:
    return os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)


def _open_directory_chain(path: Path) -> int:
    """Open an absolute directory component-by-component without following links."""
    expanded = path.expanduser()
    if any(part in {"", ".", ".."} for part in expanded.parts[1:]):
        raise PreparationError("filesystem path is not canonical")
    absolute = expanded.absolute()
    descriptor = os.open(absolute.anchor, _directory_open_flags())
    try:
        for part in absolute.parts[1:]:
            next_descriptor = os.open(part, _directory_open_flags(), dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
            metadata = os.fstat(descriptor)
            if not stat.S_ISDIR(metadata.st_mode):
                raise PreparationError("filesystem path component is not a directory")
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _verify_owner_mode(
    metadata: os.stat_result,
    *,
    expected_mode: int,
    kind: Literal["file", "directory"],
) -> None:
    if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) != expected_mode:
        raise PreparationError(f"private {kind} ownership or permissions are not approved")
    expected_kind = stat.S_ISREG if kind == "file" else stat.S_ISDIR
    if not expected_kind(metadata.st_mode):
        raise PreparationError(f"private {kind} type is not approved")


def _open_relative_directory(root_descriptor: int, parts: Sequence[str]) -> int:
    descriptor = os.dup(root_descriptor)
    try:
        for part in parts:
            if part in {"", ".", ".."} or "/" in part or "\\" in part:
                raise PreparationError("artifact path component is not approved")
            next_descriptor = os.open(part, _directory_open_flags(), dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
            _verify_owner_mode(
                os.fstat(descriptor),
                expected_mode=PRIVATE_DIRECTORY_MODE,
                kind="directory",
            )
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _read_descriptor_bounded(descriptor: int, *, maximum_bytes: int | None) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        limit = 1024 * 1024
        if maximum_bytes is not None:
            limit = min(limit, maximum_bytes + 1 - total)
            if limit <= 0:
                raise PreparationError("private file exceeds its approved size bound")
        chunk = os.read(descriptor, limit)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)
        total += len(chunk)
        if maximum_bytes is not None and total > maximum_bytes:
            raise PreparationError("private file exceeds its approved size bound")


def _snapshot_relative_regular_file(
    root_descriptor: int,
    name: str,
    *,
    maximum_bytes: int | None = None,
) -> _StableFileSnapshot:
    canonical = _safe_relative_name(name)
    parts = Path(canonical).parts
    parent = _open_relative_directory(root_descriptor, parts[:-1])
    try:
        descriptor = os.open(parts[-1], _regular_open_flags(), dir_fd=parent)
    finally:
        os.close(parent)
    try:
        before = os.fstat(descriptor)
        _verify_owner_mode(before, expected_mode=PRIVATE_FILE_MODE, kind="file")
        content = _read_descriptor_bounded(descriptor, maximum_bytes=maximum_bytes)
        after = os.fstat(descriptor)
        stable_fields = (
            "st_dev",
            "st_ino",
            "st_size",
            "st_mtime_ns",
            "st_ctime_ns",
        )
        if any(
            getattr(before, field_name) != getattr(after, field_name)
            for field_name in stable_fields
        ):
            raise PreparationError("private file changed during verified reading")
        if len(content) != after.st_size:
            raise PreparationError("private file size changed during verified reading")
        return _StableFileSnapshot(
            content=content,
            device=after.st_dev,
            inode=after.st_ino,
            size=after.st_size,
            mode=stat.S_IMODE(after.st_mode),
            uid=after.st_uid,
        )
    finally:
        os.close(descriptor)


def _snapshot_absolute_regular_file(
    path: Path,
    *,
    maximum_bytes: int | None = None,
    expected_mode: int = PRIVATE_FILE_MODE,
) -> _StableFileSnapshot:
    absolute = path.expanduser().absolute()
    parent_descriptor = _open_directory_chain(absolute.parent)
    try:
        descriptor = os.open(absolute.name, _regular_open_flags(), dir_fd=parent_descriptor)
    finally:
        os.close(parent_descriptor)
    try:
        before = os.fstat(descriptor)
        _verify_owner_mode(before, expected_mode=expected_mode, kind="file")
        content = _read_descriptor_bounded(descriptor, maximum_bytes=maximum_bytes)
        after = os.fstat(descriptor)
        if (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            raise PreparationError("private file changed during verified reading")
        return _StableFileSnapshot(
            content=content,
            device=after.st_dev,
            inode=after.st_ino,
            size=after.st_size,
            mode=stat.S_IMODE(after.st_mode),
            uid=after.st_uid,
        )
    finally:
        os.close(descriptor)


def _snapshot_absolute_jsonl_lines(path: Path) -> tuple[tuple[bytes, ...], _StableFileSnapshot]:
    absolute = path.expanduser().absolute()
    parent_descriptor = _open_directory_chain(absolute.parent)
    try:
        descriptor = os.open(absolute.name, _regular_open_flags(), dir_fd=parent_descriptor)
    finally:
        os.close(parent_descriptor)
    try:
        before = os.fstat(descriptor)
        _verify_owner_mode(before, expected_mode=PRIVATE_FILE_MODE, kind="file")
        lines: list[bytes] = []
        pending = bytearray()
        while True:
            chunk = os.read(descriptor, 64 * 1024)
            if not chunk:
                break
            pending.extend(chunk)
            while True:
                newline = pending.find(b"\n")
                if newline < 0:
                    break
                if newline + 1 > MAX_SEALED_JSONL_LINE_BYTES:
                    raise PreparationError("sealed CALLHOME record exceeds the approved line bound")
                lines.append(bytes(pending[: newline + 1]))
                del pending[: newline + 1]
            if len(pending) > MAX_SEALED_JSONL_LINE_BYTES:
                raise PreparationError("sealed CALLHOME record exceeds the approved line bound")
        if pending:
            raise PreparationError("sealed CALLHOME record is not newline terminated")
        after = os.fstat(descriptor)
        if (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            raise PreparationError("sealed CALLHOME input changed during verified reading")
        return (
            tuple(lines),
            _StableFileSnapshot(
                content=b"",
                device=after.st_dev,
                inode=after.st_ino,
                size=after.st_size,
                mode=stat.S_IMODE(after.st_mode),
                uid=after.st_uid,
            ),
        )
    finally:
        os.close(descriptor)


def _walk_private_tree(root_descriptor: int) -> tuple[tuple[str, ...], tuple[str, ...]]:
    files: list[str] = []
    directories: list[str] = []

    def visit(descriptor: int, prefix: tuple[str, ...]) -> None:
        entries = sorted(os.scandir(descriptor), key=lambda entry: entry.name)
        for entry in entries:
            metadata = entry.stat(follow_symlinks=False)
            name = entry.name
            if (
                name in {"", ".", ".."}
                or "/" in name
                or "\\" in name
                or stat.S_ISLNK(metadata.st_mode)
            ):
                raise PreparationError("private artifact tree contains an unsafe entry")
            relative = "/".join((*prefix, name))
            if stat.S_ISDIR(metadata.st_mode):
                _verify_owner_mode(
                    metadata,
                    expected_mode=PRIVATE_DIRECTORY_MODE,
                    kind="directory",
                )
                directories.append(relative)
                child = os.open(name, _directory_open_flags(), dir_fd=descriptor)
                try:
                    visit(child, (*prefix, name))
                finally:
                    os.close(child)
            elif stat.S_ISREG(metadata.st_mode):
                _verify_owner_mode(metadata, expected_mode=PRIVATE_FILE_MODE, kind="file")
                files.append(relative)
            else:
                raise PreparationError("private artifact tree contains a non-regular entry")

    visit(root_descriptor, ())
    return tuple(files), tuple(directories)


@dataclass(frozen=True)
class _VerifiedFrozenRoot:
    root_descriptor: int = field(repr=False)
    record_identity_sha256: str
    constituent_sha256: Mapping[str, str]
    small_contents: Mapping[str, bytes] = field(repr=False)
    file_identities: Mapping[str, tuple[int, int, int, int, int]] = field(repr=False)


def _canonical_json_object(raw: bytes, *, category: str) -> dict[str, Any]:
    value: Any = None
    failed = False
    original = raw
    try:
        value = json.loads(raw, object_pairs_hook=_unique_object)
    except BaseException:
        failed = True
    raw = b""
    if failed or not isinstance(value, dict):
        original = b""
        value = None
        _raise_fixed(category)
    canonical = canonical_json_bytes(value)
    if canonical != original:
        original = b""
        value = None
        _raise_fixed(category)
    original = b""
    return value


def _json_object(raw: bytes, *, category: str) -> dict[str, Any]:
    """Decode an exact checksum-anchored JSON artifact without rewriting its bytes."""
    value: Any = None
    failed = False
    try:
        value = json.loads(raw, object_pairs_hook=_unique_object)
    except BaseException:
        failed = True
    raw = b""
    if failed or not isinstance(value, dict):
        value = None
        _raise_fixed(category)
    return value


def _stream_hash_relative_file(
    root_descriptor: int,
    name: str,
) -> tuple[str, tuple[int, int, int, int, int]]:
    canonical = _safe_relative_name(name)
    parts = Path(canonical).parts
    parent = _open_relative_directory(root_descriptor, parts[:-1])
    try:
        descriptor = os.open(parts[-1], _regular_open_flags(), dir_fd=parent)
    finally:
        os.close(parent)
    try:
        before = os.fstat(descriptor)
        _verify_owner_mode(before, expected_mode=PRIVATE_FILE_MODE, kind="file")
        digest = hashlib.sha256()
        while chunk := os.read(descriptor, 1024 * 1024):
            digest.update(chunk)
        after = os.fstat(descriptor)
        identity = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if identity != (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        ):
            raise PreparationError("frozen constituent changed during checksum verification")
        return digest.hexdigest(), identity
    finally:
        os.close(descriptor)


def _verify_frozen_root(
    root: Path,
    *,
    checksum_record_name: str,
    expected_record_identity: str,
) -> _VerifiedFrozenRoot:
    descriptor = _open_directory_chain(root)
    try:
        _verify_owner_mode(
            os.fstat(descriptor),
            expected_mode=PRIVATE_DIRECTORY_MODE,
            kind="directory",
        )
        files_before, _ = _walk_private_tree(descriptor)
        record_snapshot = _snapshot_relative_regular_file(
            descriptor,
            checksum_record_name,
            maximum_bytes=4 * 1024 * 1024,
        )
        if _sha256_bytes(record_snapshot.content) != expected_record_identity:
            raise PreparationError("frozen checksum-record identity is not approved")
        checksum_record = _canonical_json_object(
            record_snapshot.content,
            category="frozen checksum record is malformed",
        )
        if not checksum_record:
            raise PreparationError("frozen checksum record is empty")
        normalized_names: set[str] = set()
        expected_files: set[str] = {checksum_record_name}
        checksums: dict[str, str] = {}
        for name, digest in checksum_record.items():
            canonical = _safe_relative_name(name)
            if canonical in normalized_names:
                raise PreparationError("frozen checksum record aliases a constituent")
            normalized_names.add(canonical)
            if not isinstance(digest, str) or not _SHA256_RE.fullmatch(digest):
                raise PreparationError("frozen constituent checksum is malformed")
            expected_files.add(canonical)
            checksums[canonical] = digest
        if set(files_before) != expected_files:
            raise PreparationError("frozen input inventory is incomplete or contains extras")
        contents: dict[str, bytes] = {}
        identities: dict[str, tuple[int, int, int, int, int]] = {}
        for name, expected_digest in sorted(checksums.items()):
            actual_digest, identity = _stream_hash_relative_file(descriptor, name)
            if actual_digest != expected_digest:
                raise PreparationError("frozen constituent checksum verification failed")
            identities[name] = identity
            if not name.endswith(".jsonl"):
                snapshot = _snapshot_relative_regular_file(
                    descriptor,
                    name,
                    maximum_bytes=32 * 1024 * 1024,
                )
                if _sha256_bytes(snapshot.content) != expected_digest:
                    raise PreparationError("frozen constituent changed after checksum verification")
                contents[name] = snapshot.content
        files_after, _ = _walk_private_tree(descriptor)
        if files_after != files_before:
            raise PreparationError("frozen input inventory changed during verification")
        return _VerifiedFrozenRoot(
            root_descriptor=os.dup(descriptor),
            record_identity_sha256=expected_record_identity,
            constituent_sha256=MappingProxyType(dict(sorted(checksums.items()))),
            small_contents=MappingProxyType(dict(sorted(contents.items()))),
            file_identities=MappingProxyType(dict(sorted(identities.items()))),
        )
    finally:
        os.close(descriptor)


def _iter_bounded_descriptor_lines(
    descriptor: int,
    *,
    category: str,
) -> Iterator[bytes]:
    """Read exactly one bounded line without retaining bytes from a later record."""
    line = bytearray()
    chunk = b""
    try:
        while True:
            chunk = os.read(
                descriptor,
                min(64 * 1024, MAX_SEALED_JSONL_LINE_BYTES + 1 - len(line)),
            )
            if not chunk:
                if line:
                    raise PreparationError(f"{category} is not newline terminated")
                return
            newline = chunk.find(b"\n")
            if newline < 0:
                line.extend(chunk)
                chunk = b""
                if len(line) > MAX_SEALED_JSONL_LINE_BYTES:
                    raise PreparationError(f"{category} exceeds the approved line bound")
                continue
            consumed = newline + 1
            unread = len(chunk) - consumed
            line.extend(chunk[:consumed])
            if unread:
                os.lseek(descriptor, -unread, os.SEEK_CUR)
            chunk = b""
            if len(line) > MAX_SEALED_JSONL_LINE_BYTES:
                raise PreparationError(f"{category} exceeds the approved line bound")
            raw_line = bytes(line)
            line.clear()
            yield raw_line
            raw_line = b""
    finally:
        chunk = b""
        line.clear()


def _snapshot_relative_jsonl_lines(
    verified: _VerifiedFrozenRoot,
    name: str,
) -> Iterator[bytes]:
    """Yield one verified line at a time without retaining the constituent population."""
    canonical = _safe_relative_name(name)
    parts = Path(canonical).parts
    parent = _open_relative_directory(verified.root_descriptor, parts[:-1])
    try:
        descriptor = os.open(parts[-1], _regular_open_flags(), dir_fd=parent)
    finally:
        os.close(parent)
    digest = hashlib.sha256()
    try:
        before = os.fstat(descriptor)
        _verify_owner_mode(before, expected_mode=PRIVATE_FILE_MODE, kind="file")
        expected_identity = verified.file_identities.get(canonical)
        if expected_identity is None:
            raise PreparationError("JSONL constituent is absent from its checksum record")
        for line in _iter_bounded_descriptor_lines(
            descriptor,
            category="JSONL record",
        ):
            digest.update(line)
            yield line
            line = b""
        after = os.fstat(descriptor)
        identity = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        if (
            identity != expected_identity
            or digest.hexdigest() != verified.constituent_sha256[canonical]
        ):
            raise PreparationError("JSONL constituent changed after checksum verification")
    finally:
        os.close(descriptor)


class _ByteJsonScanner:
    """Validate JSON structure while never decoding value strings."""

    def __init__(self, raw: bytes) -> None:
        self.raw = raw
        self.index = 0

    def _ws(self) -> None:
        while self.index < len(self.raw) and self.raw[self.index] in b" \t\r\n":
            self.index += 1

    def _take(self, byte: int) -> None:
        self._ws()
        if self.index >= len(self.raw) or self.raw[self.index] != byte:
            raise PreparationError("malformed sealed JSONL record")
        self.index += 1

    def _string_bounds(self) -> tuple[int, int]:
        self._ws()
        if self.index >= len(self.raw) or self.raw[self.index] != ord('"'):
            raise PreparationError("malformed sealed JSONL record")
        start = self.index
        self.index += 1
        while self.index < len(self.raw):
            value = self.raw[self.index]
            if value == ord('"'):
                self.index += 1
                return start, self.index
            if value < 0x20:
                raise PreparationError("malformed sealed JSONL record")
            if value == ord("\\"):
                self.index += 1
                if self.index >= len(self.raw):
                    raise PreparationError("malformed sealed JSONL record")
                escaped = self.raw[self.index]
                if escaped == ord("u"):
                    end = self.index + 5
                    if end > len(self.raw) or any(
                        byte not in b"0123456789abcdefABCDEF"
                        for byte in self.raw[self.index + 1 : end]
                    ):
                        raise PreparationError("malformed sealed JSONL record")
                    self.index = end
                    continue
                if escaped not in b'"\\/bfnrt':
                    raise PreparationError("malformed sealed JSONL record")
            self.index += 1
        raise PreparationError("malformed sealed JSONL record")

    def _string(self) -> str:
        start, end = self._string_bounds()
        try:
            value = json.loads(self.raw[start:end])
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise PreparationError("malformed sealed JSONL record")
        if not isinstance(value, str):
            raise PreparationError("malformed sealed JSONL record")
        return value

    def _number(self) -> None:
        match = re.match(
            rb"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?", self.raw[self.index :]
        )
        if match is None:
            raise PreparationError("malformed sealed JSONL record")
        self.index += len(match.group(0))

    def skip_value(self, depth: int = 0) -> None:
        if depth > 128:
            raise PreparationError("sealed JSON nesting limit exceeded")
        self._ws()
        if self.index >= len(self.raw):
            raise PreparationError("malformed sealed JSONL record")
        value = self.raw[self.index]
        if value == ord('"'):
            self._string_bounds()
        elif value == ord("{"):
            self.index += 1
            self._ws()
            if self.index < len(self.raw) and self.raw[self.index] == ord("}"):
                self.index += 1
                return
            while True:
                self._string_bounds()
                self._take(ord(":"))
                self.skip_value(depth + 1)
                self._ws()
                if self.index < len(self.raw) and self.raw[self.index] == ord("}"):
                    self.index += 1
                    break
                self._take(ord(","))
        elif value == ord("["):
            self.index += 1
            self._ws()
            if self.index < len(self.raw) and self.raw[self.index] == ord("]"):
                self.index += 1
                return
            while True:
                self.skip_value(depth + 1)
                self._ws()
                if self.index < len(self.raw) and self.raw[self.index] == ord("]"):
                    self.index += 1
                    break
                self._take(ord(","))
        elif self.raw.startswith(b"true", self.index):
            self.index += 4
        elif self.raw.startswith(b"false", self.index):
            self.index += 5
        elif self.raw.startswith(b"null", self.index):
            self.index += 4
        else:
            self._number()

    def scan_callhome(self) -> str:
        self._take(ord("{"))
        keys: list[str] = []
        seen: set[str] = set()
        split: str | None = None
        while True:
            self._ws()
            if self.index < len(self.raw) and self.raw[self.index] == ord("}"):
                self.index += 1
                break
            key = self._string()
            if key in seen:
                raise PreparationError("duplicate top-level key in sealed record")
            seen.add(key)
            keys.append(key)
            self._take(ord(":"))
            if key in _LEXICAL_TOP_LEVEL_KEYS and split is None:
                raise PreparationError("lexical field precedes the validated split field")
            if key == "split":
                split = self._string()
                if split not in {"train", "validation", "test"}:
                    raise PreparationError("sealed record has an unknown split")
            else:
                self.skip_value()
            self._ws()
            if self.index < len(self.raw) and self.raw[self.index] == ord("}"):
                self.index += 1
                break
            self._take(ord(","))
        self._ws()
        if self.index != len(self.raw) or split is None:
            raise PreparationError("malformed or missing sealed split prefix")
        if tuple(keys) != _CALLHOME_KEYS:
            raise PreparationError("sealed CALLHOME key order or schema is not approved")
        return split


def scan_sealed_callhome_split(raw_line: bytes) -> str:
    """Return the top-level split after a structure-only byte scan."""
    result: str | None = None
    failed = False
    scanner: _ByteJsonScanner | None = None
    if (
        not isinstance(raw_line, bytes)
        or len(raw_line) > MAX_SEALED_JSONL_LINE_BYTES
        or not raw_line.endswith(b"\n")
    ):
        failed = True
    else:
        try:
            scanner = _ByteJsonScanner(raw_line[:-1])
            result = scanner.scan_callhome()
        except BaseException:
            failed = True
    raw_line = b""
    scanner = None
    if failed or result is None:
        _raise_fixed("sealed CALLHOME record is invalid")
    return result


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PreparationError("duplicate key in authorized JSON record")
        result[key] = value
    return result


def _default_authorized_decoder(raw: bytes) -> Mapping[str, Any]:
    value: Any = None
    failed = False
    try:
        value = json.loads(raw, object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, PreparationError):
        failed = True
    raw = b""
    if failed:
        value = None
        _raise_fixed("authorized CALLHOME record is malformed")
    if not isinstance(value, dict):
        value = None
        raise PreparationError("authorized CALLHOME record is not an object")
    return value


def iter_sealed_callhome_jsonl(
    lines: Iterable[bytes],
    *,
    authorized_decoder: Callable[[bytes], Mapping[str, Any]] = _default_authorized_decoder,
) -> Iterator[Mapping[str, Any]]:
    """Yield train/validation objects; structurally discard test bytes."""
    iterator = iter(lines)
    lines = ()
    while True:
        try:
            raw_line = next(iterator)
        except StopIteration:
            return
        failure: str | None = None
        split: str | None = None
        record: Mapping[str, Any] | None = None
        try:
            split = scan_sealed_callhome_split(raw_line)
        except BaseException:
            failure = "sealed CALLHOME record is invalid"
        if failure is not None:
            raw_line = b""
            iterator = iter(())
            authorized_decoder = _default_authorized_decoder
            _raise_fixed(failure)
        if split == "test":
            raw_line = b""
            continue
        try:
            record = authorized_decoder(raw_line)
        except BaseException:
            failure = "authorized CALLHOME record is malformed"
        raw_line = b""
        if failure is not None:
            iterator = iter(())
            authorized_decoder = _default_authorized_decoder
            record = None
            _raise_fixed(failure)
        assert record is not None and split is not None
        if tuple(record) != _CALLHOME_KEYS or record.get("split") != split:
            record = None
            iterator = iter(())
            authorized_decoder = _default_authorized_decoder
            raise PreparationError("authorized CALLHOME schema changed after split validation")
        yield record


def read_sealed_callhome_jsonl(
    path: Path,
    *,
    authorized_decoder: Callable[[bytes], Mapping[str, Any]] = _default_authorized_decoder,
) -> Iterator[Mapping[str, Any]]:
    """Stream one frozen CALLHOME JSONL through a traceback-scrubbing boundary."""
    failed = False
    descriptor: int | None = None
    absolute = Path()
    raw_line = b""
    record: Mapping[str, Any] | None = None
    try:
        absolute = path.expanduser().absolute()
        parent_descriptor = _open_directory_chain(absolute.parent)
        try:
            descriptor = os.open(
                absolute.name,
                _regular_open_flags(),
                dir_fd=parent_descriptor,
            )
        finally:
            os.close(parent_descriptor)
        before = os.fstat(descriptor)
        _verify_owner_mode(before, expected_mode=PRIVATE_FILE_MODE, kind="file")
        for raw_line in _iter_bounded_descriptor_lines(
            descriptor,
            category="sealed CALLHOME record",
        ):
            for record in iter_sealed_callhome_jsonl(
                (raw_line,),
                authorized_decoder=authorized_decoder,
            ):
                yield record
                record = None
            raw_line = b""
        after = os.fstat(descriptor)
        if (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        ) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            raise PreparationError("sealed CALLHOME input changed during verified reading")
    except GeneratorExit:
        raise
    except BaseException:
        failed = True
    finally:
        if descriptor is not None:
            os.close(descriptor)
    absolute = Path()
    raw_line = b""
    record = None
    descriptor = None
    path = Path()
    authorized_decoder = _default_authorized_decoder
    if failed:
        _raise_fixed("sealed CALLHOME input is unavailable")


def lexical_token_count(text: str) -> int:
    """Recompute the approved whitespace lexical count."""
    if not isinstance(text, str) or not text.strip() or "\n" in text or "\r" in text:
        raise PreparationError("authorized lexical field is invalid")
    count = sum(any(character.isalpha() for character in token) for token in text.split())
    if count <= 0:
        raise PreparationError("authorized lexical field has no lexical tokens")
    return count


@dataclass(frozen=True, init=False)
class DecodedPreparationRow:
    """Authorized lexical row; all raw identities and text are hidden from repr."""

    condition: str
    source: str
    component: str
    document_id: str = field(repr=False)
    conversation_id: str = field(repr=False)
    span_id: str | None = field(repr=False)
    split: Split
    row_order: int
    row_id: str = field(repr=False)
    lexical_token_count: int
    text: str = field(repr=False)
    language_shard: LanguageShard | None = None
    input_role: str = field(repr=False, compare=False)
    input_ordinal: int = field(repr=False, compare=False)

    def __new__(cls) -> DecodedPreparationRow:
        raise PreparationError("decoded rows must be adapter-derived")

    def _validate(self) -> None:
        if self.condition not in CONDITIONS or self.split not in {"train", "validation"}:
            raise PreparationError("decoded row is outside the authorized population")
        if not all(
            isinstance(value, str) and value
            for value in (
                self.source,
                self.component,
                self.document_id,
                self.conversation_id,
                self.row_id,
            )
        ):
            raise PreparationError("decoded row provenance is invalid")
        if (
            type(self.row_order) is not int
            or self.row_order < 0
            or lexical_token_count(self.text) != self.lexical_token_count
        ):
            raise PreparationError("decoded row lexical count or ordering is invalid")
        expected_route = {
            ("EnglishMono", "callhome_eng", "callhome_monolingual", None),
            ("SpanishMono", "callhome_spa", "callhome_monolingual", None),
            ("MonoCont", "callhome_eng", "callhome_monolingual", "english"),
            ("MonoCont", "callhome_spa", "callhome_monolingual", "spanish"),
            ("CsCont", "callhome_eng", "callhome_monolingual_filler", None),
            ("CsCont", "callhome_spa", "callhome_monolingual_filler", None),
            ("CsCont", "bangor_cgwords", "bangor_natural_span", None),
        }
        if (self.condition, self.source, self.component, self.language_shard) not in expected_route:
            raise PreparationError("decoded row condition, source, and component do not agree")
        if self.component == "callhome_monolingual" and (
            self.document_id != self.conversation_id or self.span_id is not None
        ):
            raise PreparationError("CALLHOME monolingual provenance relationship is invalid")
        if self.component == "callhome_monolingual_filler" and self.span_id is not None:
            raise PreparationError("CALLHOME filler must not carry Bangor span provenance")
        if self.component == "bangor_natural_span" and self.span_id != self.document_id:
            raise PreparationError("Bangor span and document provenance do not agree")
        if (
            not isinstance(self.input_role, str)
            or not self.input_role
            or type(self.input_ordinal) is not int
            or self.input_ordinal < 0
        ):
            raise PreparationError("decoded row input anchor is invalid")

    @property
    def block_key(self) -> BlockKey:
        return (self.condition, self.split, self.language_shard)

    @property
    def authorization_key(self) -> tuple[str, ...]:
        return (
            self.condition,
            self.split,
            self.source,
            self.component,
            self.document_id,
            self.conversation_id,
            self.span_id or "",
            self.language_shard or "",
        )

def _derive_decoded_row(**values: Any) -> DecodedPreparationRow:
    row = object.__new__(DecodedPreparationRow)
    for name, value in values.items():
        object.__setattr__(row, name, value)
    row._validate()
    return row


@dataclass(frozen=True, init=False)
class PreparedPreparationRow:
    """Privacy-safe tokenized row; no decoded lexical string is retained."""

    condition: str
    source: str
    component: str
    document_id: str = field(repr=False)
    conversation_id: str = field(repr=False)
    span_id: str | None = field(repr=False)
    split: Split
    row_order: int
    row_id: str = field(repr=False)
    lexical_token_count: int
    token_ids: tuple[int, ...] = field(repr=False)
    language_shard: LanguageShard | None = None
    input_role: str = field(repr=False, compare=False)
    input_ordinal: int = field(repr=False, compare=False)

    def __new__(cls) -> PreparedPreparationRow:
        raise PreparationError("prepared rows must be tokenizer-derived")

    def _validate(self) -> None:
        if (
            self.condition not in CONDITIONS
            or self.split not in {"train", "validation"}
            or type(self.row_order) is not int
            or self.row_order < 0
            or type(self.lexical_token_count) is not int
            or self.lexical_token_count <= 0
            or not self.token_ids
            or any(
                type(token_id) is not int or not 0 <= token_id < VOCAB_SIZE
                for token_id in self.token_ids
            )
            or not all(
                isinstance(value, str) and value
                for value in (
                    self.source,
                    self.component,
                    self.document_id,
                    self.conversation_id,
                    self.row_id,
                    self.input_role,
                )
            )
            or type(self.input_ordinal) is not int
            or self.input_ordinal < 0
        ):
            raise PreparationError("prepared row metadata or tokens are invalid")
        expected_route = {
            ("EnglishMono", "callhome_eng", "callhome_monolingual", None),
            ("SpanishMono", "callhome_spa", "callhome_monolingual", None),
            ("MonoCont", "callhome_eng", "callhome_monolingual", "english"),
            ("MonoCont", "callhome_spa", "callhome_monolingual", "spanish"),
            ("CsCont", "callhome_eng", "callhome_monolingual_filler", None),
            ("CsCont", "callhome_spa", "callhome_monolingual_filler", None),
            ("CsCont", "bangor_cgwords", "bangor_natural_span", None),
        }
        if (
            self.condition,
            self.source,
            self.component,
            self.language_shard,
        ) not in expected_route:
            raise PreparationError("prepared row route is invalid")
        if self.component == "callhome_monolingual" and (
            self.document_id != self.conversation_id or self.span_id is not None
        ):
            raise PreparationError("prepared CALLHOME provenance is invalid")
        if self.component == "callhome_monolingual_filler" and self.span_id is not None:
            raise PreparationError("prepared CALLHOME filler provenance is invalid")
        if self.component == "bangor_natural_span" and self.span_id != self.document_id:
            raise PreparationError("prepared Bangor provenance is invalid")

    @property
    def block_key(self) -> BlockKey:
        return (self.condition, self.split, self.language_shard)

    @property
    def authorization_key(self) -> tuple[str, ...]:
        return (
            self.condition,
            self.split,
            self.source,
            self.component,
            self.document_id,
            self.conversation_id,
            self.span_id or "",
            self.language_shard or "",
        )


def _tokenize_decoded_row(
    row: DecodedPreparationRow,
    tokenizer: ExactTokenizer,
    hmac_key: bytes,
) -> PreparedPreparationRow:
    _require_hmac_key(hmac_key)
    token_ids = tokenizer.encode(row.text)
    prepared = object.__new__(PreparedPreparationRow)
    for name in (
        "condition",
        "source",
        "component",
        "split",
        "row_order",
        "lexical_token_count",
        "language_shard",
        "input_role",
        "input_ordinal",
    ):
        object.__setattr__(prepared, name, getattr(row, name))
    conversation_id = _pseudonym(
        hmac_key,
        "conversation",
        row.source,
        row.conversation_id,
    )
    document_id = (
        conversation_id
        if row.component == "callhome_monolingual"
        else _pseudonym(
            hmac_key,
            "document",
            row.source,
            row.document_id,
        )
    )
    span_id = (
        document_id
        if row.component == "bangor_natural_span"
        else (
            None
            if row.span_id is None
            else _pseudonym(
                hmac_key,
                "span",
                row.source,
                row.span_id,
            )
        )
    )
    object.__setattr__(prepared, "conversation_id", conversation_id)
    object.__setattr__(prepared, "document_id", document_id)
    object.__setattr__(prepared, "span_id", span_id)
    object.__setattr__(
        prepared,
        "row_id",
        _pseudonym(
            hmac_key,
            "row",
            row.source,
            row.row_id,
        ),
    )
    object.__setattr__(prepared, "token_ids", token_ids)
    prepared._validate()
    return prepared


def adapt_callhome_record(
    record: Mapping[str, Any],
    *,
    logical_condition: str,
    artifact_format_version: int = CALLHOME_ARTIFACT_FORMAT_VERSION,
) -> DecodedPreparationRow:
    """Build a synthetic-only adapted CALLHOME row for tests."""
    return _adapt_callhome_record(
        record,
        logical_condition=logical_condition,
        artifact_format_version=artifact_format_version,
        input_role=f"synthetic:{logical_condition}",
        input_ordinal=0,
    )


def _adapt_callhome_record(
    record: Mapping[str, Any],
    *,
    logical_condition: str,
    artifact_format_version: int,
    input_role: str,
    input_ordinal: int,
) -> DecodedPreparationRow:
    """Strictly adapt one CALLHOME row without retaining speaker data."""
    if (
        artifact_format_version != CALLHOME_ARTIFACT_FORMAT_VERSION
        or tuple(record) != _CALLHOME_KEYS
    ):
        raise PreparationError("CALLHOME artifact schema or format version is not approved")
    source = record.get("source")
    source_to_shard = {"callhome_eng": "english", "callhome_spa": "spanish"}
    expected = {
        "EnglishMono": "callhome_eng",
        "SpanishMono": "callhome_spa",
    }
    if logical_condition not in {"EnglishMono", "SpanishMono", "MonoCont"}:
        raise PreparationError("CALLHOME logical condition is not approved")
    if source not in source_to_shard or (
        logical_condition in expected and source != expected[logical_condition]
    ):
        raise PreparationError("CALLHOME source and logical condition do not agree")
    required_types = {
        "conversation_ref": str,
        "row_id": str,
        "source": str,
        "speaker_ref": str,
        "split": str,
        "text": str,
        "turn_index": int,
    }
    if any(type(record.get(key)) is not value_type for key, value_type in required_types.items()):
        raise PreparationError("CALLHOME artifact field type is not approved")
    split = record["split"]
    if split not in {"train", "validation"}:
        raise PreparationError("CALLHOME test or unknown split is sealed")
    conversation = record["conversation_ref"]
    text = record["text"]
    return _derive_decoded_row(
        condition=logical_condition,
        source=source,
        component="callhome_monolingual",
        document_id=conversation,
        conversation_id=conversation,
        span_id=None,
        split=split,
        row_order=record["turn_index"],
        row_id=record["row_id"],
        lexical_token_count=lexical_token_count(text),
        text=text,
        language_shard=source_to_shard[source] if logical_condition == "MonoCont" else None,
        input_role=input_role,
        input_ordinal=input_ordinal,
    )


def adapt_cscont_record(record: Mapping[str, Any]) -> DecodedPreparationRow:
    """Build a synthetic-only adapted CsCont row for tests."""
    return _adapt_cscont_record(
        record,
        input_role="synthetic:CsCont",
        input_ordinal=0,
    )


def _adapt_cscont_record(
    record: Mapping[str, Any],
    *,
    input_role: str,
    input_ordinal: int,
) -> DecodedPreparationRow:
    """Strictly adapt candidate CsCont Bangor-span or CALLHOME-filler rows."""
    if tuple(record) != _CSCONT_KEYS or record.get("artifact_format_version") != 1:
        raise PreparationError("CsCont artifact schema or format version is not approved")
    typed = {
        "artifact_format_version": int,
        "component": str,
        "condition": str,
        "conversation_id": str,
        "document_id": str,
        "document_row_index": int,
        "lexical_tokens": int,
        "record_id": str,
        "row": dict,
        "source": str,
        "split": str,
    }
    if any(type(record.get(key)) is not value_type for key, value_type in typed.items()):
        raise PreparationError("CsCont artifact field type is not approved")
    if record["condition"] != "CsCont" or record["split"] not in {"train", "validation"}:
        raise PreparationError("CsCont test, condition, or split is sealed")
    component = record["component"]
    source = record["source"]
    nested = record["row"]
    span_id: str | None
    if component == "callhome_monolingual_filler" and source in {"callhome_eng", "callhome_spa"}:
        if tuple(nested) != _CALLHOME_KEYS:
            raise PreparationError("CsCont CALLHOME filler nesting is not approved")
        if (
            nested.get("source") != source
            or nested.get("split") != record["split"]
            or nested.get("conversation_ref") != record["conversation_id"]
            or nested.get("row_id") != record["record_id"]
        ):
            raise PreparationError("CsCont CALLHOME filler routing is inconsistent")
        required_nested_types = {
            "conversation_ref": str,
            "row_id": str,
            "source": str,
            "speaker_ref": str,
            "split": str,
            "text": str,
            "turn_index": int,
        }
        if any(
            type(nested.get(key)) is not expected
            for key, expected in required_nested_types.items()
        ):
            raise PreparationError("CsCont CALLHOME filler lexical field is invalid")
        text = nested["text"]
        if record["document_row_index"] != nested["turn_index"]:
            raise PreparationError("CsCont CALLHOME filler ordering is inconsistent")
        span_id = None
    elif component == "bangor_natural_span" and source == "bangor_cgwords":
        if tuple(nested) != _BANGOR_ROW_KEYS:
            raise PreparationError("CsCont Bangor nesting is not approved")
        tokens = nested.get("tokens")
        word_ids = nested.get("source_word_ids")
        text = nested.get("text")
        if not (
            nested.get("conversation_id") == record["conversation_id"]
            and isinstance(tokens, list)
            and tokens
            and all(isinstance(token, str) and token for token in tokens)
            and isinstance(word_ids, list)
            and len(tokens) == len(word_ids)
            and len(set(word_ids)) == len(word_ids)
            and all(type(word_id) is int and word_id >= 0 for word_id in word_ids)
            and all(later > earlier for earlier, later in zip(word_ids, word_ids[1:]))
            and isinstance(text, str)
            and " ".join(tokens) == text
        ):
            raise PreparationError("CsCont Bangor lexical/provenance nesting is invalid")
        span_id = record["document_id"]
    else:
        raise PreparationError("CsCont source and component combination is not approved")
    count = lexical_token_count(text)
    if count != record["lexical_tokens"]:
        raise PreparationError("CsCont stored and recomputed lexical counts differ")
    return _derive_decoded_row(
        condition="CsCont",
        source=source,
        component=component,
        document_id=record["document_id"],
        conversation_id=record["conversation_id"],
        span_id=span_id,
        split=record["split"],
        row_order=record["document_row_index"],
        row_id=record["record_id"],
        lexical_token_count=count,
        text=text,
        language_shard=None,
        input_role=input_role,
        input_ordinal=input_ordinal,
    )


@dataclass(frozen=True)
class AggregateExpectation:
    train_rows: int
    train_lexical_tokens: int
    validation_rows: int
    validation_lexical_tokens: int

    def __post_init__(self) -> None:
        if any(type(value) is not int or value <= 0 for value in self.__dict__.values()):
            raise PreparationError("membership aggregate expectation is invalid")


APPROVED_REAL_AGGREGATES = MappingProxyType(
    {
        "EnglishMono": AggregateExpectation(13_136, 90_000, 735, 5_000),
        "SpanishMono": AggregateExpectation(12_091, 90_000, 600, 5_000),
        "MonoCont:english": AggregateExpectation(6_654, 45_000, 355, 2_500),
        "MonoCont:spanish": AggregateExpectation(6_125, 45_000, 299, 2_500),
        "CsCont": AggregateExpectation(14_366, 90_000, 706, 5_000),
    }
)


def approved_block_order() -> tuple[BlockKey, ...]:
    return (
        ("EnglishMono", "train", None),
        ("EnglishMono", "validation", None),
        ("SpanishMono", "train", None),
        ("SpanishMono", "validation", None),
        ("MonoCont", "train", "english"),
        ("MonoCont", "train", "spanish"),
        ("MonoCont", "validation", "english"),
        ("MonoCont", "validation", "spanish"),
        ("CsCont", "train", None),
        ("CsCont", "validation", None),
    )


def _aggregate_for_block(key: BlockKey) -> tuple[int, int]:
    condition, split, shard = key
    aggregate_key = f"{condition}:{shard}" if shard else condition
    expectation = APPROVED_REAL_AGGREGATES[aggregate_key]
    if split == "train":
        return expectation.train_rows, expectation.train_lexical_tokens
    return expectation.validation_rows, expectation.validation_lexical_tokens


@dataclass(frozen=True)
class ExpectedMembershipBlock:
    key: BlockKey
    ordered_row_ids: tuple[str, ...] = field(repr=False)
    lexical_tokens: int
    ordered_membership: tuple[MembershipIdentity, ...] | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.key not in approved_block_order() or not self.ordered_row_ids:
            raise PreparationError("expected membership block is invalid")
        if len(set(self.ordered_row_ids)) != len(self.ordered_row_ids):
            raise PreparationError("expected membership contains a duplicate row")
        if self.lexical_tokens <= 0:
            raise PreparationError("expected membership lexical total is invalid")
        if self.ordered_membership is not None and (
            len(self.ordered_membership) != len(self.ordered_row_ids)
            or tuple(identity[5] for identity in self.ordered_membership) != self.ordered_row_ids
        ):
            raise PreparationError("expected entity membership does not match its rows")


@dataclass(frozen=True, init=False)
class MembershipPlan:
    """Complete ordered membership authorization, held only in memory."""

    blocks: tuple[ExpectedMembershipBlock, ...] = field(repr=False)
    input_anchor: InputPopulationAnchor | None = field(repr=False)

    def __new__(cls) -> MembershipPlan:
        raise PreparationError("membership plans must be factory-derived")

    def _validate(self) -> None:
        if tuple(block.key for block in self.blocks) != approved_block_order():
            raise PreparationError("membership blocks are missing, reordered, or duplicated")
        identities = [
            (block.key[0], block.key[1], block.key[2], row_id)
            for block in self.blocks
            for row_id in block.ordered_row_ids
        ]
        if len(set(identities)) != len(identities):
            raise PreparationError("membership row identity overlaps an authorization block")
        if self.input_anchor is not None:
            if not isinstance(self.input_anchor, InputPopulationAnchor):
                raise PreparationError("production membership lacks its verified input anchor")
            for block in self.blocks:
                if block.ordered_membership is None:
                    raise PreparationError(
                        "real membership plan requires complete entity identities"
                    )
                rows, lexical = _aggregate_for_block(block.key)
                if len(block.ordered_row_ids) != rows or block.lexical_tokens != lexical:
                    raise PreparationError("membership plan does not reconcile approved totals")


@dataclass(frozen=True, init=False)
class InputPopulationAnchor:
    checksum_record_identities: tuple[tuple[str, str], ...]
    constituent_sha256: tuple[tuple[str, str], ...]
    input_line_counts: tuple[tuple[str, int], ...]
    authorized_line_counts: tuple[tuple[str, int], ...]
    sealed_test_line_counts: tuple[tuple[str, int], ...]
    identity_sha256: str

    def __new__(cls) -> InputPopulationAnchor:
        raise PreparationError("input population anchors must be production-derived")

    def _validate(self) -> None:
        expected_records = (
            ("callhome", APPROVED_CALLHOME_CHECKSUM_RECORD_SHA256),
            ("cscont", APPROVED_CSCONT_CHECKSUM_RECORD_SHA256),
            ("tokenizer", APPROVED_TOKENIZER_CHECKSUM_RECORD_SHA256),
        )
        if self.checksum_record_identities != expected_records:
            raise PreparationError("input population checksum identities are not approved")
        if not self.constituent_sha256 or not self.input_line_counts:
            raise PreparationError("input population anchor is incomplete")
        for _, digest in self.constituent_sha256:
            if not _SHA256_RE.fullmatch(digest):
                raise PreparationError("input constituent identity is invalid")
        payload = {
            "authorized_line_counts": dict(self.authorized_line_counts),
            "checksum_record_identities": dict(self.checksum_record_identities),
            "constituent_sha256": dict(self.constituent_sha256),
            "input_line_counts": dict(self.input_line_counts),
            "sealed_test_line_counts": dict(self.sealed_test_line_counts),
        }
        if _sha256_bytes(canonical_json_bytes(payload)) != self.identity_sha256:
            raise PreparationError("input population anchor identity does not reconcile")


def _derive_membership_plan(
    rows: Sequence[DecodedPreparationRow | PreparedPreparationRow],
    *,
    input_anchor: InputPopulationAnchor | None,
) -> MembershipPlan:
    blocks: list[ExpectedMembershipBlock] = []
    for key in approved_block_order():
        material = tuple(row for row in rows if row.block_key == key)
        if not material:
            raise PreparationError("membership block is empty")
        blocks.append(
            ExpectedMembershipBlock(
                key=key,
                ordered_row_ids=tuple(row.row_id for row in material),
                lexical_tokens=sum(row.lexical_token_count for row in material),
                ordered_membership=tuple(_membership_identity(row) for row in material),
            )
        )
    plan = object.__new__(MembershipPlan)
    object.__setattr__(plan, "blocks", tuple(blocks))
    object.__setattr__(plan, "input_anchor", input_anchor)
    plan._validate()
    return plan


def make_synthetic_membership_plan(
    rows: Sequence[DecodedPreparationRow],
) -> MembershipPlan:
    """Derive an unmistakably synthetic plan which publication rejects."""
    if not rows:
        raise PreparationError("synthetic membership requires synthetic adapted rows")
    return _derive_membership_plan(rows, input_anchor=None)


@dataclass(frozen=True, init=False)
class MembershipValidation:
    ordered_digest_hmac_sha256: str
    input_population_anchor_sha256: str | None
    row_totals: tuple[tuple[BlockKey, int], ...]
    lexical_totals: tuple[tuple[BlockKey, int], ...]
    test_sealed: bool

    def __new__(cls) -> MembershipValidation:
        raise PreparationError("membership validations must be factory-derived")


def _require_hmac_key(key: bytes) -> None:
    if not isinstance(key, bytes) or len(key) < 32:
        raise PreparationError("HMAC key must contain at least 32 bytes")


def _membership_identity(
    row: DecodedPreparationRow | PreparedPreparationRow,
) -> MembershipIdentity:
    return (
        row.source,
        row.component,
        row.document_id,
        row.conversation_id,
        row.span_id,
        row.row_id,
        row.row_order,
    )


def validate_membership(
    rows: Iterable[DecodedPreparationRow | PreparedPreparationRow],
    plan: MembershipPlan,
    *,
    hmac_key: bytes,
) -> MembershipValidation:
    """Bind exact blocks, rows, byte order, totals, and identities."""
    _require_hmac_key(hmac_key)
    plan._validate()
    material = tuple(rows)
    actual_keys: list[BlockKey] = []
    blocks: dict[
        BlockKey,
        list[DecodedPreparationRow | PreparedPreparationRow],
    ] = {}
    closed: set[BlockKey] = set()
    previous_key: BlockKey | None = None
    seen_rows: set[tuple[str, str, str]] = set()
    seen_entities: dict[tuple[str, str, str], str] = {}
    for row in material:
        if row.split not in {"train", "validation"}:
            raise PreparationError("test membership reached completeness validation")
        key = row.block_key
        identity = (row.condition, row.source, row.row_id)
        if identity in seen_rows:
            raise PreparationError("membership contains a duplicate row")
        seen_rows.add(identity)
        for kind, value in (
            ("document", row.document_id),
            ("conversation", row.conversation_id),
            ("span", row.span_id),
        ):
            if value is None:
                continue
            entity = (kind, row.source, value)
            prior_split = seen_entities.setdefault(entity, row.split)
            if prior_split != row.split:
                raise PreparationError("membership entity overlaps train and validation")
        if key != previous_key:
            if previous_key is not None:
                closed.add(previous_key)
            if key in closed:
                raise PreparationError("authorization block is not contiguous")
            actual_keys.append(key)
            previous_key = key
        blocks.setdefault(key, []).append(row)
    if tuple(actual_keys) != approved_block_order():
        raise PreparationError("condition, split, or shard block order is not approved")
    row_totals: list[tuple[BlockKey, int]] = []
    lexical_totals: list[tuple[BlockKey, int]] = []
    digest = hmac.new(hmac_key, digestmod=hashlib.sha256)
    if plan.input_anchor is not None:
        plan.input_anchor._validate()
        digest.update(canonical_json_bytes(["input_anchor", plan.input_anchor.identity_sha256]))
    for expected in plan.blocks:
        actual = blocks.get(expected.key, [])
        ids = tuple(row.row_id for row in actual)
        if ids != expected.ordered_row_ids:
            raise PreparationError("membership row is missing, duplicated, or reordered")
        identities = tuple(_membership_identity(row) for row in actual)
        if expected.ordered_membership is not None and identities != expected.ordered_membership:
            raise PreparationError(
                "membership entity is missing, duplicated, changed, or reordered"
            )
        if any(
            later.row_order <= earlier.row_order
            for earlier, later in zip(actual, actual[1:])
            if later.authorization_key == earlier.authorization_key
        ):
            raise PreparationError("row order is not strictly increasing in an authorization block")
        lexical = sum(row.lexical_token_count for row in actual)
        if lexical != expected.lexical_tokens:
            raise PreparationError("membership lexical total does not reconcile")
        row_totals.append((expected.key, len(actual)))
        lexical_totals.append((expected.key, lexical))
        digest.update(canonical_json_bytes([expected.key, identities, lexical]))
    result = object.__new__(MembershipValidation)
    object.__setattr__(result, "ordered_digest_hmac_sha256", digest.hexdigest())
    object.__setattr__(
        result,
        "input_population_anchor_sha256",
        plan.input_anchor.identity_sha256 if plan.input_anchor is not None else None,
    )
    object.__setattr__(result, "row_totals", tuple(row_totals))
    object.__setattr__(result, "lexical_totals", tuple(lexical_totals))
    object.__setattr__(result, "test_sealed", True)
    return result


@dataclass(frozen=True)
class SyntheticParityCase:
    text: str = field(repr=False)
    expected_ids: tuple[int, ...] = field(repr=False)

    def __post_init__(self) -> None:
        if (
            not isinstance(self.text, str)
            or not self.text
            or not self.expected_ids
            or any(type(token_id) is not int for token_id in self.expected_ids)
        ):
            raise PreparationError("synthetic tokenizer parity case is invalid")


@dataclass(frozen=True, init=False)
class ExactTokenizer:
    """Backend-only tokenizer wrapper which can never add special tokens."""

    _backend: Any = field(repr=False)
    checksum_record_sha256: str
    loader_protocol: str
    synthetic_parity_sha256: str
    tokenizer_artifact_sha256: str
    backend_configuration_sha256: str
    historical_build_identity: Mapping[str, Any] | None = field(repr=False)

    def __new__(cls) -> ExactTokenizer:
        raise PreparationError("exact tokenizers must be backend-loader-derived")

    def _validate(self) -> None:
        if (
            self.checksum_record_sha256 != APPROVED_TOKENIZER_CHECKSUM_RECORD_SHA256
            or self.loader_protocol != TOKENIZER_LOADER_PROTOCOL
            or not _SHA256_RE.fullmatch(self.synthetic_parity_sha256)
            or not hasattr(self._backend, "encode")
        ):
            raise PreparationError("exact tokenizer wrapper is not approved")
        if self.historical_build_identity is not None:
            if (
                not _SHA256_RE.fullmatch(self.tokenizer_artifact_sha256)
                or not _SHA256_RE.fullmatch(self.backend_configuration_sha256)
                or not isinstance(self.historical_build_identity, Mapping)
                or not hasattr(self._backend, "to_str")
            ):
                raise PreparationError("production tokenizer lacks its frozen backend identity")
            try:
                backend_payload = json.loads(self._backend.to_str())
            except BaseException:
                backend_payload = None
            if (
                not isinstance(backend_payload, dict)
                or _sha256_bytes(canonical_json_bytes(backend_payload))
                != self.backend_configuration_sha256
            ):
                raise PreparationError("production tokenizer backend changed after loading")

    def encode(self, text: str) -> tuple[int, ...]:
        self._validate()
        if not isinstance(text, str) or not text:
            raise PreparationError("tokenizer input is invalid")
        encoding: Any = None
        failed = False
        try:
            encoding = self._backend.encode(text, add_special_tokens=False)
        except BaseException:  # tokenizers exposes backend-specific exception types
            failed = True
        text = ""
        if failed:
            encoding = None
            _raise_fixed("exact tokenizer encoding failed")
        ids = tuple(encoding.ids)
        encoding = None
        if not ids or any(
            type(token_id) is not int or token_id < 0 or token_id >= VOCAB_SIZE for token_id in ids
        ):
            raise PreparationError("exact tokenizer returned an invalid encoding")
        return ids


def _derive_exact_tokenizer(
    backend: Any,
    parity_sha256: str,
    *,
    checksum_record_sha256: str,
    tokenizer_artifact_sha256: str,
    backend_configuration_sha256: str,
    historical_build_identity: Mapping[str, Any] | None,
) -> ExactTokenizer:
    wrapper = object.__new__(ExactTokenizer)
    object.__setattr__(wrapper, "_backend", backend)
    object.__setattr__(wrapper, "checksum_record_sha256", checksum_record_sha256)
    object.__setattr__(wrapper, "loader_protocol", TOKENIZER_LOADER_PROTOCOL)
    object.__setattr__(wrapper, "synthetic_parity_sha256", parity_sha256)
    object.__setattr__(wrapper, "tokenizer_artifact_sha256", tokenizer_artifact_sha256)
    object.__setattr__(wrapper, "backend_configuration_sha256", backend_configuration_sha256)
    object.__setattr__(wrapper, "historical_build_identity", historical_build_identity)
    wrapper._validate()
    return wrapper


def make_synthetic_exact_tokenizer(backend: Any) -> ExactTokenizer:
    """Wrap a synthetic backend for in-memory tests; publication always rejects it."""
    wrapper = _derive_exact_tokenizer(
        backend,
        "0" * 64,
        checksum_record_sha256=APPROVED_TOKENIZER_CHECKSUM_RECORD_SHA256,
        tokenizer_artifact_sha256="",
        backend_configuration_sha256="",
        historical_build_identity=None,
    )
    parity = _sha256_bytes(
        canonical_json_bytes(
            {
                "protocol": "synthetic_exact_tokenizer_only",
                "special_tokens_disabled": True,
            }
        )
    )
    object.__setattr__(wrapper, "synthetic_parity_sha256", parity)
    wrapper._validate()
    return wrapper


def _validate_tokenizer_json(payload: Mapping[str, Any]) -> None:
    normalizer = payload.get("normalizer")
    pretokenizer = payload.get("pre_tokenizer")
    model = payload.get("model")
    expected_normalizer = {
        "type": "Sequence",
        "normalizers": [
            {"type": "NFC"},
            {
                "type": "BertNormalizer",
                "clean_text": True,
                "handle_chinese_chars": False,
                "strip_accents": False,
                "lowercase": True,
            },
        ],
    }
    if normalizer != expected_normalizer:
        raise PreparationError("tokenizer normalizer differs from the frozen protocol")
    if pretokenizer != {"type": "BertPreTokenizer"}:
        raise PreparationError("tokenizer pretokenizer differs from the frozen protocol")
    if not isinstance(model, dict) or any(
        (
            model.get("type") != "WordPiece",
            model.get("unk_token") != "[UNK]",
            model.get("continuing_subword_prefix") != CONTINUATION_PREFIX,
        )
    ):
        raise PreparationError("tokenizer WordPiece model differs from the frozen protocol")
    vocabulary = model.get("vocab")
    if not isinstance(vocabulary, dict) or len(vocabulary) != VOCAB_SIZE:
        raise PreparationError("tokenizer vocabulary size differs from 8,000")
    if {token: vocabulary.get(token) for token in SPECIAL_TOKEN_IDS} != SPECIAL_TOKEN_IDS:
        raise PreparationError("tokenizer special-token IDs differ from the frozen protocol")
    approved = protocol_configuration()
    if approved["normalization"] != {
        "sequence": ["NFC", "BertNormalizer"],
        "clean_text": True,
        "handle_chinese_chars": False,
        "lowercase": True,
        "strip_accents": False,
    }:
        raise PreparationError("compiled tokenizer protocol is internally inconsistent")


def load_synthetic_exact_tokenizer(
    tokenizer_json_path: Path,
    checksum_record_path: Path,
    *,
    parity_cases: Sequence[SyntheticParityCase],
) -> ExactTokenizer:
    """Load a synthetic exact artifact for tests; it can never be published."""
    if (
        tokenizer_json_path.is_symlink()
        or checksum_record_path.is_symlink()
        or not tokenizer_json_path.is_file()
        or not checksum_record_path.is_file()
    ):
        raise PreparationError("tokenizer artifact path is not a regular file")
    if _sha256_file(checksum_record_path) != APPROVED_TOKENIZER_CHECKSUM_RECORD_SHA256:
        raise PreparationError("tokenizer checksum-record identity is not approved")
    checksum_record_failed = False
    try:
        checksum_record = json.loads(checksum_record_path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        checksum_record = None
        checksum_record_failed = True
    if checksum_record_failed:
        _raise_fixed("tokenizer checksum record is malformed")
    if not isinstance(checksum_record, dict):
        raise PreparationError("tokenizer checksum record is malformed")
    expected_tokenizer_sha = checksum_record.get("tokenizer.json")
    if (
        not isinstance(expected_tokenizer_sha, str)
        or _sha256_file(tokenizer_json_path) != expected_tokenizer_sha
    ):
        raise PreparationError("tokenizer artifact does not match its checksum record")
    payload_failed = False
    try:
        payload = json.loads(tokenizer_json_path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        payload = None
        payload_failed = True
    if payload_failed:
        _raise_fixed("tokenizer JSON is malformed")
    if not isinstance(payload, dict):
        raise PreparationError("tokenizer JSON is malformed")
    _validate_tokenizer_json(payload)
    backend_failed = False
    try:
        from tokenizers import Tokenizer

        backend = Tokenizer.from_file(str(tokenizer_json_path))
    except Exception:
        backend = None
        backend_failed = True
    if backend_failed or backend is None:
        _raise_fixed("exact Tokenizers backend could not be loaded")
    if backend.get_vocab_size(with_added_tokens=True) != VOCAB_SIZE:
        raise PreparationError("loaded tokenizer vocabulary size differs from 8,000")
    if {token: backend.token_to_id(token) for token in SPECIAL_TOKEN_IDS} != SPECIAL_TOKEN_IDS:
        raise PreparationError("loaded tokenizer special-token IDs differ from the frozen protocol")
    if not parity_cases:
        raise PreparationError("synthetic tokenizer parity cases are required")
    parity_payload: list[object] = []
    backend_payload = json.loads(backend.to_str())
    backend_configuration_sha256 = _sha256_bytes(canonical_json_bytes(backend_payload))
    wrapper = _derive_exact_tokenizer(
        backend,
        "0" * 64,
        checksum_record_sha256=APPROVED_TOKENIZER_CHECKSUM_RECORD_SHA256,
        tokenizer_artifact_sha256=expected_tokenizer_sha,
        backend_configuration_sha256=backend_configuration_sha256,
        historical_build_identity=None,
    )
    for case in parity_cases:
        actual = wrapper.encode(case.text)
        if actual != case.expected_ids:
            raise PreparationError("synthetic tokenizer parity mismatch")
        parity_payload.append([case.text, case.expected_ids])
    return _derive_exact_tokenizer(
        backend,
        _sha256_bytes(canonical_json_bytes(parity_payload)),
        checksum_record_sha256=APPROVED_TOKENIZER_CHECKSUM_RECORD_SHA256,
        tokenizer_artifact_sha256=expected_tokenizer_sha,
        backend_configuration_sha256=backend_configuration_sha256,
        historical_build_identity=None,
    )


_FIXED_TOKENIZER_PARITY_TEXTS = (
    "NEU MixedCase CAFÉ",
    "neu mixedcase café",
    "CAFE\u0301",
    "CAFÉ",
    "alpha   beta\tgamma",
    "alpha beta gamma",
    "hello,world! ¿qué?",
    "x" * 101,
)


def _fixed_tokenizer_parity(
    first: Any,
    second: Any,
) -> str:
    results: list[dict[str, object]] = []
    for text in _FIXED_TOKENIZER_PARITY_TEXTS:
        first_encoding = first.encode(text, add_special_tokens=False)
        second_encoding = second.encode(text, add_special_tokens=False)
        if (
            first_encoding.ids != second_encoding.ids
            or first_encoding.tokens != second_encoding.tokens
        ):
            raise PreparationError("repeated exact tokenizer loading changed synthetic parity")
        results.append(
            {
                "text": text,
                "ids": tuple(first_encoding.ids),
                "tokens": tuple(first_encoding.tokens),
            }
        )
    if results[0]["ids"] != results[1]["ids"]:
        raise PreparationError("tokenizer lowercase parity failed")
    if results[2]["ids"] != results[3]["ids"]:
        raise PreparationError("tokenizer NFC/decomposition parity failed")
    if results[4]["ids"] != results[5]["ids"]:
        raise PreparationError("tokenizer whitespace parity failed")
    if 1 not in results[-1]["ids"]:
        raise PreparationError("tokenizer unknown-token parity failed")
    try:
        normalized_accented = first.normalizer.normalize_str("CAFÉ")
        normalized_plain = first.normalizer.normalize_str("CAFE")
    except BaseException:
        normalized_accented = None
        normalized_plain = None
    if normalized_accented != "café" or normalized_plain != "cafe":
        raise PreparationError("tokenizer accent-preservation parity failed")
    if not any(
        isinstance(token, str) and token.startswith(CONTINUATION_PREFIX)
        for result in results
        for token in result["tokens"]
    ):
        vocabulary = first.get_vocab(with_added_tokens=True)
        continuation_tokens = sorted(
            token
            for token in vocabulary
            if token.startswith(CONTINUATION_PREFIX)
            and token[len(CONTINUATION_PREFIX) :].isalpha()
        )
        start_tokens = sorted(
            token
            for token in vocabulary
            if token.isalpha() and not token.startswith(CONTINUATION_PREFIX)
        )
        found = False
        for start in start_tokens[:256]:
            for continuation in continuation_tokens[:256]:
                candidate = start + continuation[len(CONTINUATION_PREFIX) :]
                encoding = first.encode(candidate, add_special_tokens=False)
                if any(token.startswith(CONTINUATION_PREFIX) for token in encoding.tokens):
                    results.append(
                        {
                            "text": candidate,
                            "ids": tuple(encoding.ids),
                            "tokens": tuple(encoding.tokens),
                        }
                    )
                    found = True
                    break
            if found:
                break
        if not found:
            raise PreparationError("tokenizer continuation parity failed")
    return _sha256_bytes(canonical_json_bytes(results))


@dataclass(frozen=True)
class ValidationMaterial:
    condition: str
    plan_name: str
    seed: int
    masked_input_ids: np.ndarray = field(repr=False)
    labels: np.ndarray = field(repr=False)
    attention_mask: np.ndarray = field(repr=False)
    token_type_ids: np.ndarray = field(repr=False)
    example_identities: tuple[str, ...] = field(repr=False)
    record: ValidationMaskRecord

    def __post_init__(self) -> None:
        if self.condition not in CONDITIONS or not self.example_identities:
            raise PreparationError("fixed validation material has invalid membership")
        shape = (len(self.example_identities), MAX_SEQUENCE_LENGTH)
        expected = (
            (self.masked_input_ids, np.dtype("uint16")),
            (self.labels, np.dtype("int32")),
            (self.attention_mask, np.dtype("uint8")),
            (self.token_type_ids, np.dtype("uint8")),
        )
        if any(array.shape != shape or array.dtype != dtype for array, dtype in expected):
            raise PreparationError("fixed validation arrays have invalid shape or dtype")
        if self.record.condition != self.condition or self.record.seed != self.seed:
            raise PreparationError("fixed validation record does not match its material")


def approved_validation_seed_plans() -> tuple[tuple[str, int], ...]:
    """Import, label, and expose the authoritative merged seed plans."""
    plans = [("tiny_smoke_1", TINY_SMOKE_SEED_PLANS[0].validation_mask_seed)]
    plans.extend(
        (f"small_{index}", plan.validation_mask_seed)
        for index, plan in enumerate(SMALL_PILOT_SEED_PLANS, start=1)
    )
    return tuple(plans)


def materialize_fixed_validation(
    sequences: Iterable[PackedSequence],
) -> tuple[ValidationMaterial, ...]:
    """Materialize every approved fixed validation plan for all conditions."""
    material = tuple(sequences)
    by_condition = {
        condition: tuple(
            sequence
            for sequence in material
            if sequence.condition == condition and sequence.split == "validation"
        )
        for condition in CONDITIONS
    }
    if any(not by_condition[condition] for condition in CONDITIONS):
        raise PreparationError("all four validation populations must be nonempty")
    if any(sequence.split == "test" for sequence in material):
        raise PreparationError("test sequence reached validation materialization")
    outputs: list[ValidationMaterial] = []
    for condition in CONDITIONS:
        condition_sequences = by_condition[condition]
        identities = tuple(sequence.example_identity for sequence in condition_sequences)
        for plan_name, seed in approved_validation_seed_plans():
            masked = tuple(
                mask_packed_sequence(sequence, seed=seed, mode="validation")
                for sequence in condition_sequences
            )
            output = ValidationMaterial(
                condition=condition,
                plan_name=plan_name,
                seed=seed,
                masked_input_ids=np.asarray(
                    [example.input_ids for example in masked], dtype=np.uint16
                ),
                labels=np.asarray([example.labels for example in masked], dtype=np.int32),
                attention_mask=np.asarray(
                    [sequence.attention_mask for sequence in condition_sequences],
                    dtype=np.uint8,
                ),
                token_type_ids=np.asarray(
                    [sequence.token_type_ids for sequence in condition_sequences],
                    dtype=np.uint8,
                ),
                example_identities=identities,
                record=build_validation_mask_record(condition_sequences, seed=seed),
            )
            outputs.append(output)
    return tuple(outputs)


@dataclass(frozen=True)
class PreparationBundle:
    rows: tuple[PreparedPreparationRow, ...] = field(repr=False)
    membership_plan: MembershipPlan = field(repr=False)
    membership: MembershipValidation
    packing: PackingResult
    validation: tuple[ValidationMaterial, ...]
    exposure_audit: Any
    tokenizer_checksum_record_sha256: str
    tokenizer_loader_protocol: str
    tokenizer_synthetic_parity_sha256: str
    tokenizer_artifact_sha256: str
    tokenizer_backend_configuration_sha256: str
    tokenizer_historical_build_identity: Mapping[str, Any] | None = field(repr=False)
    input_anchor: InputPopulationAnchor | None
    protocol_version: str


def _packing_row(row: PreparedPreparationRow) -> PackingRow:
    if row.split not in {"train", "validation"}:
        raise PreparationError("test row reached packing construction")
    return PackingRow(
        condition=row.condition,
        split=row.split,
        source=row.source,
        component=row.component,
        document_id=row.document_id,
        conversation_id=row.conversation_id,
        span_id=row.span_id,
        row_id=row.row_id,
        row_order=row.row_order,
        token_ids=row.token_ids,
        lexical_token_count=row.lexical_token_count,
        language_shard=row.language_shard,
    )


def _aggregate_exposure_diagnostics(packing: PackingResult) -> dict[str, object]:
    train: dict[str, dict[str, int | float]] = {}
    for condition in CONDITIONS:
        sequences = [
            sequence
            for sequence in packing.sequences
            if sequence.condition == condition and sequence.split == "train"
        ]
        non_padding = sum(sequence.non_padding_wordpieces for sequence in sequences)
        train[condition] = {
            "sequence_count": len(sequences),
            "non_padding_wordpieces": non_padding,
            "mean_non_padding_wordpieces": non_padding / len(sequences) if sequences else 0.0,
        }
    means = [float(train[condition]["mean_non_padding_wordpieces"]) for condition in CONDITIONS]
    minimum = min(means) if means else 0.0
    maximum = max(means) if means else 0.0
    return {
        "by_condition": train,
        "difference_fraction": (maximum - minimum) / minimum if minimum > 0 else None,
        "tolerance_fraction": EXPOSURE_TOLERANCE_FRACTION,
    }


def _validate_cross_condition_reuse(
    rows: Sequence[DecodedPreparationRow | PreparedPreparationRow],
) -> None:
    baselines: dict[
        tuple[str, str, str],
        DecodedPreparationRow | PreparedPreparationRow,
    ] = {}
    monocont: dict[
        tuple[str, str, str],
        DecodedPreparationRow | PreparedPreparationRow,
    ] = {}

    def content_identity(
        row: DecodedPreparationRow | PreparedPreparationRow,
    ) -> str | tuple[int, ...]:
        return row.text if isinstance(row, DecodedPreparationRow) else row.token_ids
    for row in rows:
        if row.condition in {"EnglishMono", "SpanishMono"}:
            baselines[(row.source, row.split, row.row_id)] = row
        elif row.condition == "MonoCont":
            monocont[(row.source, row.split, row.row_id)] = row
    for key, row in monocont.items():
        baseline = baselines.get(key)
        if baseline is None or (
            baseline.conversation_id != row.conversation_id
            or baseline.row_order != row.row_order
            or content_identity(baseline) != content_identity(row)
            or baseline.lexical_token_count != row.lexical_token_count
        ):
            raise PreparationError(
                "MonoCont membership is not an exact monolingual-baseline subset"
            )
    for row in rows:
        if row.component != "callhome_monolingual_filler":
            continue
        baseline = monocont.get((row.source, row.split, row.row_id))
        if baseline is None or (
            baseline.conversation_id != row.conversation_id
            or baseline.row_order != row.row_order
            or content_identity(baseline) != content_identity(row)
            or baseline.lexical_token_count != row.lexical_token_count
        ):
            raise PreparationError("CsCont CALLHOME filler is not an exact MonoCont member")


def _prepare_rows(
    rows: Iterable[DecodedPreparationRow],
    *,
    tokenizer: ExactTokenizer,
    hmac_key: bytes,
    protocol_version: str,
    input_anchor: InputPopulationAnchor | None = None,
) -> PreparationBundle:
    """Validate, tokenize exactly once, pack, mask validation, and audit."""
    if not isinstance(tokenizer, ExactTokenizer):
        raise PreparationError("preparation requires an exact backend-derived tokenizer")
    tokenizer._validate()
    material: list[PreparedPreparationRow] = []
    for row in rows:
        if row.split not in {"train", "validation"}:
            raise PreparationError("test row reached tokenization")
        material.append(_tokenize_decoded_row(row, tokenizer, hmac_key))
        row = None
    return _prepare_tokenized_rows(
        tuple(material),
        input_anchor=input_anchor,
        tokenizer=tokenizer,
        hmac_key=hmac_key,
        protocol_version=protocol_version,
    )


def _prepare_tokenized_rows(
    material: tuple[PreparedPreparationRow, ...],
    *,
    input_anchor: InputPopulationAnchor | None,
    tokenizer: ExactTokenizer,
    hmac_key: bytes,
    protocol_version: str,
) -> PreparationBundle:
    membership_plan = _derive_membership_plan(
        material,
        input_anchor=input_anchor,
    )
    if input_anchor is not None:
        _validate_cross_condition_reuse(material)
    membership = validate_membership(material, membership_plan, hmac_key=hmac_key)
    packing_rows = [_packing_row(row) for row in material]
    source_wordpieces = sum(len(row.token_ids) for row in material)
    packing = pack_rows(packing_rows)
    if source_wordpieces != sum(packing.source_wordpieces_by_group.values()):
        raise PreparationError("source WordPieces do not reconcile before auditing")
    exposure_failure = False
    exposure_diagnostics: dict[str, object] | None = None
    try:
        from cslm.modeling.exposure import ExposureAuditError, audit_exposure

        exposure = audit_exposure((packing,))
    except ExposureAuditError:
        exposure_diagnostics = _aggregate_exposure_diagnostics(packing)
        exposure_failure = True
        exposure = None
    if exposure_failure:
        assert exposure_diagnostics is not None
        if exposure_diagnostics["difference_fraction"] is not None and (
            float(exposure_diagnostics["difference_fraction"]) > EXPOSURE_TOLERANCE_FRACTION
        ):
            raise ExposureAcceptanceError(exposure_diagnostics)
        _raise_fixed("aggregate exposure audit failed")
    assert exposure is not None
    validation = materialize_fixed_validation(packing.sequences)
    repeated = materialize_fixed_validation(packing.sequences)
    for first, second in zip(validation, repeated, strict=True):
        if not (
            first.record == second.record
            and np.array_equal(first.masked_input_ids, second.masked_input_ids)
            and np.array_equal(first.labels, second.labels)
            and np.array_equal(first.attention_mask, second.attention_mask)
            and np.array_equal(first.token_type_ids, second.token_type_ids)
            and first.example_identities == second.example_identities
        ):
            raise PreparationError("fixed validation material did not reproduce exactly")
    return PreparationBundle(
        rows=material,
        membership_plan=membership_plan,
        membership=membership,
        packing=packing,
        validation=validation,
        exposure_audit=exposure,
        tokenizer_checksum_record_sha256=tokenizer.checksum_record_sha256,
        tokenizer_loader_protocol=tokenizer.loader_protocol,
        tokenizer_synthetic_parity_sha256=tokenizer.synthetic_parity_sha256,
        tokenizer_artifact_sha256=tokenizer.tokenizer_artifact_sha256,
        tokenizer_backend_configuration_sha256=tokenizer.backend_configuration_sha256,
        tokenizer_historical_build_identity=tokenizer.historical_build_identity,
        input_anchor=membership_plan.input_anchor,
        protocol_version=protocol_version,
    )


def prepare_synthetic_rows(
    rows: Iterable[DecodedPreparationRow],
    *,
    tokenizer: ExactTokenizer,
    hmac_key: bytes,
) -> PreparationBundle:
    """Prepare synthetic in-memory fixtures which can never be published."""
    material = tuple(rows)
    return _prepare_rows(
        material,
        tokenizer=tokenizer,
        hmac_key=hmac_key,
        protocol_version=SYNTHETIC_PREPARATION_PROTOCOL_VERSION,
    )


@dataclass(frozen=True)
class ProductionPreparationPaths:
    """Only filesystem roots candidate by the production preparation factory."""

    callhome_root: Path
    cscont_root: Path
    tokenizer_root: Path
    hmac_key_path: Path


def _decode_cscont_line(raw: bytes) -> Mapping[str, Any]:
    value: Any = None
    failed = False
    try:
        value = json.loads(raw, object_pairs_hook=_unique_object)
    except BaseException:
        failed = True
    raw = b""
    if failed or not isinstance(value, dict):
        value = None
        _raise_fixed("authorized CsCont record is malformed")
    return value


def _historical_tokenizer_build_identity(
    tokenizer_root: _VerifiedFrozenRoot,
) -> Mapping[str, Any]:
    required_keys = {
        "backend_correction_id",
        "build",
        "format_version",
        "patch",
        "tokenizers",
        "upstream_commit",
        "upstream_repository",
        "upstream_tag",
    }
    candidates: list[tuple[str, dict[str, Any]]] = []
    for name, content in tokenizer_root.small_contents.items():
        if not name.endswith(".json") or name == "tokenizer.json":
            continue
        try:
            payload = json.loads(content, object_pairs_hook=_unique_object)
        except BaseException:
            continue
        if isinstance(payload, dict) and set(payload) == required_keys:
            candidates.append((name, payload))
    if len(candidates) != 1:
        raise PreparationError("historical tokenizer-build record is absent or ambiguous")
    name, payload = candidates[0]
    build = payload.get("build")
    if (
        payload.get("backend_correction_id") != BACKEND_CORRECTION_ID
        or payload.get("format_version") != 1
        or payload.get("tokenizers") != "0.22.2"
        or payload.get("upstream_tag") != "v0.22.2"
        or payload.get("upstream_repository") != "https://github.com/huggingface/tokenizers.git"
        or not isinstance(payload.get("upstream_commit"), str)
        or not re.fullmatch(r"[0-9a-f]{40}", payload["upstream_commit"])
        or not isinstance(payload.get("patch"), str)
        or not isinstance(build, dict)
        or set(build) != {"cargo_locked", "maturin", "rust"}
        or build.get("cargo_locked") is not True
        or not all(isinstance(build.get(key), str) and build[key] for key in ("maturin", "rust"))
    ):
        raise PreparationError("historical tokenizer-build record schema is not approved")
    return MappingProxyType(
        {
            "constituent_name": name,
            "constituent_sha256": tokenizer_root.constituent_sha256[name],
            "record": payload,
        }
    )


def _load_production_exact_tokenizer(
    tokenizer_root: _VerifiedFrozenRoot,
) -> ExactTokenizer:
    tokenizer_bytes = tokenizer_root.small_contents.get("tokenizer.json")
    if tokenizer_bytes is None:
        raise PreparationError("frozen tokenizer JSON is absent")
    payload = _json_object(
        tokenizer_bytes,
        category="frozen tokenizer JSON is malformed",
    )
    _validate_tokenizer_json(payload)
    historical = _historical_tokenizer_build_identity(tokenizer_root)
    first: Any = None
    second: Any = None
    descriptor: int | None = None
    try:
        descriptor = os.open(
            "tokenizer.json",
            _regular_open_flags(),
            dir_fd=tokenizer_root.root_descriptor,
        )
        before = os.fstat(descriptor)
        _verify_owner_mode(before, expected_mode=PRIVATE_FILE_MODE, kind="file")
        identity = (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
            before.st_ctime_ns,
        )
        if identity != tokenizer_root.file_identities["tokenizer.json"]:
            raise PreparationError("frozen tokenizer changed before backend loading")
        if sys.platform == "darwin":
            tokenizer_path = f"/dev/fd/{descriptor}"
        elif sys.platform.startswith("linux"):
            tokenizer_path = f"/proc/self/fd/{descriptor}"
        else:
            raise PreparationError("stable descriptor tokenizer loading is unavailable")
        from tokenizers import Tokenizer

        os.lseek(descriptor, 0, os.SEEK_SET)
        first = Tokenizer.from_file(tokenizer_path)
        os.lseek(descriptor, 0, os.SEEK_SET)
        second = Tokenizer.from_file(tokenizer_path)
        after = os.fstat(descriptor)
        if (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ) != identity:
            raise PreparationError("frozen tokenizer changed during backend loading")
        parity_sha256 = _fixed_tokenizer_parity(first, second)
    except BaseException:
        if descriptor is not None:
            os.close(descriptor)
            descriptor = None
        tokenizer_path = ""
        first = None
        second = None
        tokenizer_bytes = b""
        payload = {}
        _raise_fixed("exact production tokenizer loading or parity failed")
    assert descriptor is not None
    os.close(descriptor)
    descriptor = None
    tokenizer_path = ""
    assert first is not None
    backend_payload = json.loads(first.to_str())
    backend_configuration_sha256 = _sha256_bytes(canonical_json_bytes(backend_payload))
    tokenizer_artifact_sha256 = tokenizer_root.constituent_sha256["tokenizer.json"]
    tokenizer_bytes = b""
    payload = {}
    return _derive_exact_tokenizer(
        first,
        parity_sha256,
        checksum_record_sha256=tokenizer_root.record_identity_sha256,
        tokenizer_artifact_sha256=tokenizer_artifact_sha256,
        backend_configuration_sha256=backend_configuration_sha256,
        historical_build_identity=historical,
    )


def _derive_input_anchor(
    roots: Mapping[str, _VerifiedFrozenRoot],
    *,
    input_line_counts: Mapping[str, int],
    authorized_line_counts: Mapping[str, int],
    sealed_test_line_counts: Mapping[str, int],
) -> InputPopulationAnchor:
    constituent = tuple(
        sorted(
            (f"{role}:{name}", digest)
            for role, root in roots.items()
            for name, digest in root.constituent_sha256.items()
        )
    )
    records = (
        ("callhome", roots["callhome"].record_identity_sha256),
        ("cscont", roots["cscont"].record_identity_sha256),
        ("tokenizer", roots["tokenizer"].record_identity_sha256),
    )
    payload = {
        "authorized_line_counts": dict(sorted(authorized_line_counts.items())),
        "checksum_record_identities": dict(records),
        "constituent_sha256": dict(constituent),
        "input_line_counts": dict(sorted(input_line_counts.items())),
        "sealed_test_line_counts": dict(sorted(sealed_test_line_counts.items())),
    }
    anchor = object.__new__(InputPopulationAnchor)
    object.__setattr__(anchor, "checksum_record_identities", records)
    object.__setattr__(anchor, "constituent_sha256", constituent)
    object.__setattr__(
        anchor,
        "input_line_counts",
        tuple(sorted(input_line_counts.items())),
    )
    object.__setattr__(
        anchor,
        "authorized_line_counts",
        tuple(sorted(authorized_line_counts.items())),
    )
    object.__setattr__(
        anchor,
        "sealed_test_line_counts",
        tuple(sorted(sealed_test_line_counts.items())),
    )
    object.__setattr__(anchor, "identity_sha256", _sha256_bytes(canonical_json_bytes(payload)))
    anchor._validate()
    return anchor


def _prepare_production_inputs(
    paths: ProductionPreparationPaths,
) -> PreparationBundle:
    """Derive a production bundle for immediate in-scope publication only."""
    if not isinstance(paths, ProductionPreparationPaths):
        raise PreparationError("production preparation requires typed frozen roots")
    callhome: _VerifiedFrozenRoot | None = None
    cscont: _VerifiedFrozenRoot | None = None
    tokenizer_root: _VerifiedFrozenRoot | None = None
    private_rows: list[PreparedPreparationRow] = []
    decoded_row: DecodedPreparationRow | None = None
    record: Mapping[str, Any] | None = None
    raw_line = b""
    line_iterator: Iterator[bytes] | None = None
    anchor: InputPopulationAnchor | None = None
    exact_tokenizer: ExactTokenizer | None = None
    key = b""
    roots: dict[str, _VerifiedFrozenRoot] = {}
    verified: _VerifiedFrozenRoot | None = None
    failed = False
    exposure_diagnostics: dict[str, object] | None = None
    try:
        callhome = _verify_frozen_root(
            paths.callhome_root,
            checksum_record_name="checksums.json",
            expected_record_identity=APPROVED_CALLHOME_CHECKSUM_RECORD_SHA256,
        )
        cscont = _verify_frozen_root(
            paths.cscont_root,
            checksum_record_name="checksums.json",
            expected_record_identity=APPROVED_CSCONT_CHECKSUM_RECORD_SHA256,
        )
        tokenizer_root = _verify_frozen_root(
            paths.tokenizer_root,
            checksum_record_name="checksums.json",
            expected_record_identity=APPROVED_TOKENIZER_CHECKSUM_RECORD_SHA256,
        )
        for name in _CALLHOME_MEMBERSHIP_FILES:
            if name not in callhome.constituent_sha256:
                raise PreparationError("CALLHOME frozen membership file is absent")
        for name in _CSCONT_MEMBERSHIP_FILES:
            if name not in cscont.constituent_sha256:
                raise PreparationError("CsCont frozen membership file is absent")
        exact_tokenizer = _load_production_exact_tokenizer(tokenizer_root)
        key = load_hmac_key(
            paths.hmac_key_path,
            forbidden_roots=(
                paths.callhome_root,
                paths.cscont_root,
                paths.tokenizer_root,
            ),
        )
        line_counts: Counter[str] = Counter()
        authorized_counts: Counter[str] = Counter()
        test_counts: Counter[str] = Counter()
        for name, condition in _CALLHOME_MEMBERSHIP_FILES.items():
            role = f"callhome:{name}"
            line_iterator = _snapshot_relative_jsonl_lines(callhome, name)
            try:
                for ordinal, raw_line in enumerate(line_iterator):
                    line_counts[role] += 1
                    split = scan_sealed_callhome_split(raw_line)
                    if split == "test":
                        test_counts[role] += 1
                        raw_line = b""
                        continue
                    record = _default_authorized_decoder(raw_line)
                    decoded_row = _adapt_callhome_record(
                        record,
                        logical_condition=condition,
                        artifact_format_version=CALLHOME_ARTIFACT_FORMAT_VERSION,
                        input_role=role,
                        input_ordinal=ordinal,
                    )
                    private_rows.append(
                        _tokenize_decoded_row(decoded_row, exact_tokenizer, key)
                    )
                    authorized_counts[role] += 1
                    decoded_row = None
                    record = None
                    raw_line = b""
            finally:
                close = getattr(line_iterator, "close", None)
                if close is not None:
                    close()
                line_iterator = None
        for name in _CSCONT_MEMBERSHIP_FILES:
            role = f"cscont:{name}"
            expected_split = name.removesuffix("_rows.jsonl")
            line_iterator = _snapshot_relative_jsonl_lines(cscont, name)
            try:
                for ordinal, raw_line in enumerate(line_iterator):
                    line_counts[role] += 1
                    record = _decode_cscont_line(raw_line)
                    if record.get("split") != expected_split:
                        raise PreparationError(
                            "CsCont membership file contains an unexpected split"
                        )
                    decoded_row = _adapt_cscont_record(
                        record,
                        input_role=role,
                        input_ordinal=ordinal,
                    )
                    private_rows.append(
                        _tokenize_decoded_row(decoded_row, exact_tokenizer, key)
                    )
                    authorized_counts[role] += 1
                    decoded_row = None
                    record = None
                    raw_line = b""
            finally:
                close = getattr(line_iterator, "close", None)
                if close is not None:
                    close()
                line_iterator = None
        roots = {"callhome": callhome, "cscont": cscont, "tokenizer": tokenizer_root}
        anchor = _derive_input_anchor(
            roots,
            input_line_counts=line_counts,
            authorized_line_counts=authorized_counts,
            sealed_test_line_counts=test_counts,
        )
        block_rank = {key: index for index, key in enumerate(approved_block_order())}
        private_rows.sort(
            key=lambda row: (
                block_rank[row.block_key],
                row.input_role,
                row.input_ordinal,
            )
        )
        result = _prepare_tokenized_rows(
            tuple(private_rows),
            input_anchor=anchor,
            tokenizer=exact_tokenizer,
            hmac_key=key,
            protocol_version=PREPARATION_PROTOCOL_VERSION,
        )
    except ExposureAcceptanceError as error:
        exposure_diagnostics = dict(error.diagnostics)
        failed = True
        result = None
    except BaseException:
        failed = True
        result = None
    finally:
        for verified in (callhome, cscont, tokenizer_root):
            if verified is not None:
                os.close(verified.root_descriptor)
        private_rows = []
        decoded_row = None
        record = None
        raw_line = b""
        line_iterator = None
        anchor = None
        exact_tokenizer = None
        key = b""
        roots = {}
        verified = None
        callhome = None
        cscont = None
        tokenizer_root = None
        paths = ProductionPreparationPaths(Path(), Path(), Path(), Path())
    if exposure_diagnostics is not None:
        raise ExposureAcceptanceError(exposure_diagnostics)
    if failed or result is None:
        _raise_fixed("production preparation failed")
    return result


def _distribution_record_digest(distribution: importlib.metadata.Distribution) -> str:
    record_text = distribution.read_text("RECORD")
    if record_text is None:
        raise PreparationError("pinned dependency lacks a wheel RECORD")
    rows: list[tuple[str, str, str]] = []
    try:
        for row in csv.reader(io.StringIO(record_text)):
            if len(row) != 3 or Path(row[0]).is_absolute():
                raise PreparationError("dependency wheel RECORD is malformed")
            rows.append((row[0].replace("\\", "/"), row[1], row[2]))
    except csv.Error:
        rows.clear()
        failed = True
    else:
        failed = False
    if failed:
        _raise_fixed("dependency wheel RECORD is malformed")
    return _sha256_bytes(canonical_json_bytes(sorted(rows)))


def _wheel_tags(distribution: importlib.metadata.Distribution) -> tuple[str, ...]:
    wheel = distribution.read_text("WHEEL")
    if wheel is None:
        return ()
    return tuple(
        sorted(
            line.partition(":")[2].strip() for line in wheel.splitlines() if line.startswith("Tag:")
        )
    )


def _actual_runtime_environment_controls() -> Mapping[str, str]:
    """Read deterministic controls from the running process, never caller evidence."""
    controls = {
        "PYTHONHASHSEED": os.environ.get("PYTHONHASHSEED", ""),
        "TOKENIZERS_PARALLELISM": os.environ.get("TOKENIZERS_PARALLELISM", ""),
    }
    if (
        controls["PYTHONHASHSEED"] != "1729"
        or controls["TOKENIZERS_PARALLELISM"].lower() != "false"
    ):
        raise PreparationError("required deterministic environment controls are absent")
    return MappingProxyType(controls)


def collect_runtime_identity(
    *,
    bundle: PreparationBundle,
) -> Mapping[str, Any]:
    """Record pinned Python, wheel, native backend, and environment identities."""
    if (
        not isinstance(bundle, PreparationBundle)
        or bundle.protocol_version != PREPARATION_PROTOCOL_VERSION
        or not isinstance(bundle.tokenizer_historical_build_identity, Mapping)
    ):
        raise PreparationError("runtime identity requires a production tokenizer binding")
    environment_controls = _actual_runtime_environment_controls()
    expected_versions = {
        "numpy": "1.26.4",
        "tokenizers": "0.22.2",
        "torch": "2.11.0",
        "transformers": "5.6.2",
    }
    dependencies: dict[str, object] = {}
    for name, expected in expected_versions.items():
        distribution = importlib.metadata.distribution(name)
        if distribution.version != expected:
            raise PreparationError("runtime dependency differs from the pinned version")
        dependencies[name] = {
            "version": distribution.version,
            "normalized_record_sha256": _distribution_record_digest(distribution),
            "wheel_tags": _wheel_tags(distribution),
        }
    tokenizers_failed = False
    try:
        import tokenizers
    except ImportError:
        tokenizers = None
        tokenizers_failed = True
    if tokenizers_failed or tokenizers is None:
        _raise_fixed("Tokenizers runtime is unavailable")
    package = Path(tokenizers.__file__).resolve().parent
    native = sorted(package.glob("tokenizers.*.so")) + sorted(package.glob("tokenizers.*.pyd"))
    if len(native) != 1:
        raise PreparationError("Tokenizers native extension identity is ambiguous")
    historical = bundle.tokenizer_historical_build_identity
    historical_record = historical.get("record")
    anchored_constituents = (
        dict(bundle.input_anchor.constituent_sha256)
        if isinstance(bundle.input_anchor, InputPopulationAnchor)
        else {}
    )
    if (
        not isinstance(historical_record, Mapping)
        or historical_record.get("backend_correction_id") != BACKEND_CORRECTION_ID
        or historical.get("constituent_sha256")
        != anchored_constituents.get(f"tokenizer:{historical.get('constituent_name')}")
    ):
        raise PreparationError("historical tokenizer-build identity is not anchored")
    executable = Path(sys.executable)
    return MappingProxyType(
        {
            "python": {
                "version": platform.python_version(),
                "implementation": platform.python_implementation(),
                "abi": sysconfig.get_config_var("SOABI"),
                "executable_sha256": _sha256_file(executable),
            },
            "platform": {
                "os": platform.system(),
                "os_release": platform.release(),
                "architecture": platform.machine(),
                "platform_tag": sysconfig.get_platform(),
            },
            "dependencies": dependencies,
            "historical_tokenizer_build": historical,
            "encoding_runtime_native": {
                "sha256": _sha256_file(native[0]),
                "abi": sysconfig.get_config_var("SOABI"),
                "platform": sysconfig.get_platform(),
                "historical_binary_equality_claimed": False,
            },
            "backend_correction_id": BACKEND_CORRECTION_ID,
            "frozen_tokenizer_checksum_record_sha256": APPROVED_TOKENIZER_CHECKSUM_RECORD_SHA256,
            "loader_protocol": TOKENIZER_LOADER_PROTOCOL,
            "environment_controls": dict(environment_controls),
        }
    )


def _validation_record_payload(record: ValidationMaskRecord) -> dict[str, object]:
    return {
        "condition": record.condition,
        "seed": record.seed,
        "example_count": record.example_count,
        "policy_sha256": record.policy_sha256,
        "checksum_sha256": record.checksum_sha256,
    }


def _exposure_payload(audit: Any) -> dict[str, object]:
    return {
        "groups": [
            {
                "condition": group.condition,
                "split": group.split,
                "source_lexical_tokens": group.source_lexical_tokens,
                "non_padding_wordpieces": group.non_padding_wordpieces,
                "sequence_count": group.sequence_count,
                "padding_count": group.padding_count,
                "padding_fraction": group.padding_fraction,
                "expected_masked_target_count": group.expected_masked_target_count,
            }
            for group in audit.groups
        ],
        "projected_train_non_padding_wordpieces": dict(
            audit.projected_train_non_padding_wordpieces
        ),
        "prohibited_boundary_crossings": audit.prohibited_boundary_crossings,
        "split_leakage_count": audit.split_leakage_count,
        "dropped_token_count": audit.dropped_token_count,
        "truncated_token_count": audit.truncated_token_count,
        "maximum_projected_exposure_difference_fraction": (
            audit.maximum_projected_exposure_difference_fraction
        ),
        "exposure_tolerance_fraction": audit.exposure_tolerance_fraction,
    }


def _pseudonym(
    key: bytes,
    entity_type: Literal[
        "example",
        "row",
        "row_binding",
        "document",
        "conversation",
        "span",
    ],
    source_namespace: str,
    value: str | None,
) -> str | None:
    if value is None:
        return None
    payload = canonical_json_bytes(
        ["neu_preparation_pseudonym_v1", entity_type, source_namespace, value]
    )
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def _source_row_token_content_binding(
    key: bytes,
    *,
    protocol: str,
    source_namespace: str,
    split: str,
    row_pseudonym: str,
    conversation_pseudonym: str,
    row_order: int,
    lexical_token_count: int,
    source_token_count: int,
    token_ids: Sequence[int],
) -> str:
    """Key exact row tokens for privacy-safe membership reconciliation only."""
    _require_hmac_key(key)
    material = tuple(token_ids)
    if (
        protocol
        not in {PREPARATION_PROTOCOL_VERSION, SYNTHETIC_PREPARATION_PROTOCOL_VERSION}
        or not all(
            isinstance(value, str) and value
            for value in (
                source_namespace,
                split,
                row_pseudonym,
                conversation_pseudonym,
            )
        )
        or split not in {"train", "validation"}
        or any(
            type(value) is not int or value < 0
            for value in (row_order, lexical_token_count, source_token_count)
        )
        or lexical_token_count == 0
        or source_token_count == 0
        or source_token_count != len(material)
        or any(type(token_id) is not int or not 0 <= token_id < VOCAB_SIZE for token_id in material)
    ):
        raise PreparationError("source-row token binding material is invalid")
    payload = canonical_json_bytes(
        [
            "neu_source_row_token_content_binding_v1",
            protocol,
            source_namespace,
            split,
            row_pseudonym,
            conversation_pseudonym,
            row_order,
            lexical_token_count,
            source_token_count,
            material,
        ]
    )
    return hmac.new(key, payload, hashlib.sha256).hexdigest()


def _provenance_payload(sequence: PackedSequence, hmac_key: bytes) -> dict[str, object]:
    if not sequence.provenance:
        raise PreparationError("packed sequence lacks provenance")
    example_source = sequence.provenance[0].source
    return {
        "condition": sequence.condition,
        "split": sequence.split,
        "example_pseudonym": _pseudonym(
            hmac_key,
            "example",
            example_source,
            sequence.example_identity,
        ),
        "ranges": [
            {
                "condition": item.condition,
                "split": item.split,
                "source_role": item.source,
                "component_role": item.component,
                "language_shard": item.language_shard,
                "row_order": item.row_order,
                "source_row_token_count": item.source_row_token_count,
                "packed_token_range": [item.packed_token_start, item.packed_token_end],
                "source_token_range": [item.source_token_start, item.source_token_end],
                "row_pseudonym": _pseudonym(hmac_key, "row", item.source, item.row_id),
                "document_pseudonym": _pseudonym(
                    hmac_key,
                    "document",
                    item.source,
                    item.document_id,
                ),
                "conversation_pseudonym": _pseudonym(
                    hmac_key,
                    "conversation",
                    item.source,
                    item.conversation_id,
                ),
                "span_pseudonym": _pseudonym(
                    hmac_key,
                    "span",
                    item.source,
                    item.span_id,
                ),
            }
            for item in sequence.provenance
        ],
    }


def _npy_bytes(array: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    np.save(buffer, array, allow_pickle=False)
    return buffer.getvalue()


def _serialized_membership_payload(
    bundle: PreparationBundle,
    *,
    hmac_key: bytes,
) -> list[dict[str, object]]:
    fragments: dict[
        tuple[str, str, str, str],
        list[tuple[int, int, tuple[int, ...]]],
    ] = {}
    for sequence in bundle.packing.sequences:
        for item in sequence.provenance:
            key = (item.condition, item.split, item.source, item.row_id)
            token_ids = tuple(
                sequence.input_ids[item.packed_token_start : item.packed_token_end]
            )
            fragments.setdefault(key, []).append(
                (item.source_token_start, item.source_token_end, token_ids)
            )
    output: list[dict[str, object]] = []
    for row in bundle.rows:
        key = (row.condition, row.split, row.source, row.row_id)
        ordered = sorted(fragments.get(key, ()))
        if (
            not ordered
            or ordered[0][0] != 0
            or any(
                earlier[1] != later[0]
                for earlier, later in zip(ordered, ordered[1:])
            )
        ):
            raise PreparationError("serialized row token identity is incomplete")
        token_ids = tuple(
            token_id
            for _, _, fragment in ordered
            for token_id in fragment
        )
        if ordered[-1][1] != len(row.token_ids) or token_ids != row.token_ids:
            raise PreparationError("serialized row token identity changed during packing")
        row_pseudonym = _pseudonym(
            hmac_key,
            "row",
            row.source,
            row.row_id,
        )
        conversation_pseudonym = _pseudonym(
            hmac_key,
            "conversation",
            row.source,
            row.conversation_id,
        )
        assert row_pseudonym is not None
        assert conversation_pseudonym is not None
        output.append(
            {
                "condition": row.condition,
                "split": row.split,
                "source_role": row.source,
                "row_pseudonym": row_pseudonym,
                "conversation_pseudonym": conversation_pseudonym,
                "row_order": row.row_order,
                "lexical_token_count": row.lexical_token_count,
                "source_token_count": len(token_ids),
                "row_content_binding_hmac_sha256": _source_row_token_content_binding(
                    hmac_key,
                    protocol=bundle.protocol_version,
                    source_namespace=row.source,
                    split=row.split,
                    row_pseudonym=row_pseudonym,
                    conversation_pseudonym=conversation_pseudonym,
                    row_order=row.row_order,
                    lexical_token_count=row.lexical_token_count,
                    source_token_count=len(token_ids),
                    token_ids=token_ids,
                ),
            }
        )
    return output


def _reconcile_packed_row_token_content(
    *,
    serialized_membership: object,
    provenance: object,
    packed_arrays: Mapping[
        tuple[str, str],
        tuple[np.ndarray, np.ndarray, np.ndarray],
    ],
    protocol: str,
    reconciliation_key: bytes,
) -> Mapping[tuple[str, str, str, str], tuple[object, ...]]:
    """Rebuild every source row from packed arrays and verify its keyed binding."""
    _require_hmac_key(reconciliation_key)
    if (
        protocol
        not in {PREPARATION_PROTOCOL_VERSION, SYNTHETIC_PREPARATION_PROTOCOL_VERSION}
        or not isinstance(serialized_membership, list)
        or not serialized_membership
        or not isinstance(provenance, list)
        or not provenance
    ):
        raise PreparationError("serialized row-content reconciliation is incomplete")

    membership_rows: dict[
        tuple[str, str, str, str],
        tuple[str, str, int, int, int, str],
    ] = {}
    membership_order: list[tuple[str, str, str, str]] = []
    membership_fields = {
        "condition",
        "split",
        "source_role",
        "row_pseudonym",
        "conversation_pseudonym",
        "row_order",
        "lexical_token_count",
        "source_token_count",
        "row_content_binding_hmac_sha256",
    }
    for row in serialized_membership:
        if (
            not isinstance(row, dict)
            or set(row) != membership_fields
            or row["condition"] not in CONDITIONS
            or row["split"] not in {"train", "validation"}
            or row["source_role"]
            not in {"callhome_eng", "callhome_spa", "bangor_cgwords"}
            or any(
                not isinstance(row[name], str)
                or not _SHA256_RE.fullmatch(row[name])
                for name in (
                    "row_pseudonym",
                    "conversation_pseudonym",
                    "row_content_binding_hmac_sha256",
                )
            )
            or any(
                type(row[name]) is not int or row[name] < 0
                for name in (
                    "row_order",
                    "lexical_token_count",
                    "source_token_count",
                )
            )
            or row["lexical_token_count"] == 0
            or row["source_token_count"] == 0
        ):
            raise PreparationError("serialized membership content schema is invalid")
        row_key = (
            row["condition"],
            row["split"],
            row["source_role"],
            row["row_pseudonym"],
        )
        if row_key in membership_rows:
            raise PreparationError("serialized membership contains a duplicate row")
        membership_rows[row_key] = (
            row["source_role"],
            row["conversation_pseudonym"],
            row["row_order"],
            row["lexical_token_count"],
            row["source_token_count"],
            row["row_content_binding_hmac_sha256"],
        )
        membership_order.append(row_key)

    array_rows_seen: Counter[tuple[str, str]] = Counter()
    fragments: dict[
        tuple[str, str, str, str],
        list[tuple[int, int, tuple[int, ...]]],
    ] = {}
    observed_row_order: list[tuple[str, str, str, str]] = []
    observed_rows: set[tuple[str, str, str, str]] = set()
    provenance_fields = {"condition", "split", "example_pseudonym", "ranges"}
    range_fields = {
        "condition",
        "split",
        "source_role",
        "component_role",
        "language_shard",
        "row_order",
        "source_row_token_count",
        "packed_token_range",
        "source_token_range",
        "row_pseudonym",
        "document_pseudonym",
        "conversation_pseudonym",
        "span_pseudonym",
    }
    for example in provenance:
        if (
            not isinstance(example, dict)
            or set(example) != provenance_fields
            or example["condition"] not in CONDITIONS
            or example["split"] not in {"train", "validation"}
            or not isinstance(example["ranges"], list)
            or not example["ranges"]
        ):
            raise PreparationError("serialized provenance content schema is invalid")
        group = (example["condition"], example["split"])
        arrays = packed_arrays.get(group)
        row_index = array_rows_seen[group]
        if arrays is None or any(array.ndim != 2 for array in arrays):
            raise PreparationError("packed arrays are incomplete for provenance")
        inputs, attention, token_types = arrays
        if (
            inputs.shape != attention.shape
            or inputs.shape != token_types.shape
            or row_index >= inputs.shape[0]
        ):
            raise PreparationError("packed arrays do not match provenance ordering")
        input_row = inputs[row_index]
        attention_row = attention[row_index]
        type_row = token_types[row_index]
        array_rows_seen[group] += 1
        attended = int(attention_row.sum())
        if (
            input_row.shape != (MAX_SEQUENCE_LENGTH,)
            or not np.array_equal(type_row, np.zeros_like(type_row))
            or attended < 2
            or not np.array_equal(
                attention_row,
                np.concatenate(
                    (
                        np.ones(attended, dtype=attention_row.dtype),
                        np.zeros(MAX_SEQUENCE_LENGTH - attended, dtype=attention_row.dtype),
                    )
                ),
            )
            or int(input_row[0]) != SPECIAL_TOKEN_IDS["[CLS]"]
            or int(input_row[attended - 1]) != SPECIAL_TOKEN_IDS["[SEP]"]
            or np.any(input_row[attended:] != SPECIAL_TOKEN_IDS["[PAD]"])
        ):
            raise PreparationError("packed sequence special tokens do not reconcile")
        packed_cursor = 1
        for item in example["ranges"]:
            if (
                not isinstance(item, dict)
                or set(item) != range_fields
                or item["condition"] != group[0]
                or item["split"] != group[1]
                or not isinstance(item["source_role"], str)
                or not isinstance(item["row_pseudonym"], str)
                or not isinstance(item["conversation_pseudonym"], str)
                or any(
                    type(item[name]) is not int or item[name] < 0
                    for name in ("row_order", "source_row_token_count")
                )
                or item["source_row_token_count"] == 0
                or not all(
                    isinstance(item[name], list)
                    and len(item[name]) == 2
                    and all(type(value) is int and value >= 0 for value in item[name])
                    and item[name][1] > item[name][0]
                    for name in ("packed_token_range", "source_token_range")
                )
            ):
                raise PreparationError("serialized provenance token range is invalid")
            packed_start, packed_end = item["packed_token_range"]
            source_start, source_end = item["source_token_range"]
            if (
                packed_start != packed_cursor
                or packed_end - packed_start != source_end - source_start
                or packed_end >= attended
                or int(input_row[packed_end]) != SPECIAL_TOKEN_IDS["[SEP]"]
                or source_end > item["source_row_token_count"]
            ):
                raise PreparationError("packed provenance token positions do not reconcile")
            lexical_ids = tuple(int(value) for value in input_row[packed_start:packed_end])
            if any(
                token_id in {
                    SPECIAL_TOKEN_IDS["[PAD]"],
                    SPECIAL_TOKEN_IDS["[CLS]"],
                    SPECIAL_TOKEN_IDS["[SEP]"],
                    SPECIAL_TOKEN_IDS["[MASK]"],
                }
                for token_id in lexical_ids
            ):
                raise PreparationError("packed lexical content contains a special token")
            row_key = (
                group[0],
                group[1],
                item["source_role"],
                item["row_pseudonym"],
            )
            membership = membership_rows.get(row_key)
            if (
                membership is None
                or membership[1] != item["conversation_pseudonym"]
                or membership[2] != item["row_order"]
                or membership[4] != item["source_row_token_count"]
            ):
                raise PreparationError("provenance does not match serialized membership")
            if row_key not in observed_rows:
                observed_rows.add(row_key)
                observed_row_order.append(row_key)
            fragments.setdefault(row_key, []).append(
                (source_start, source_end, lexical_ids)
            )
            packed_cursor = packed_end + 1
        if packed_cursor != attended:
            raise PreparationError("packed sequence contains unaccounted token content")

    if any(
        array_rows_seen[group] != arrays[0].shape[0]
        for group, arrays in packed_arrays.items()
    ):
        raise PreparationError("packed array rows are not fully covered by provenance")
    if set(array_rows_seen) != set(packed_arrays):
        raise PreparationError("provenance groups do not match packed arrays")
    if observed_row_order != membership_order or set(fragments) != set(membership_rows):
        raise PreparationError("source-row identity or ordering does not reconcile")

    for row_key, membership in membership_rows.items():
        ordered = sorted(fragments[row_key], key=lambda value: (value[0], value[1]))
        if (
            ordered[0][0] != 0
            or any(
                earlier[1] != later[0]
                for earlier, later in zip(ordered, ordered[1:])
            )
            or ordered[-1][1] != membership[4]
        ):
            raise PreparationError("source-row provenance is missing or duplicated")
        token_ids = tuple(
            token_id
            for _, _, fragment in ordered
            for token_id in fragment
        )
        expected_binding = _source_row_token_content_binding(
            reconciliation_key,
            protocol=protocol,
            source_namespace=membership[0],
            split=row_key[1],
            row_pseudonym=row_key[3],
            conversation_pseudonym=membership[1],
            row_order=membership[2],
            lexical_token_count=membership[3],
            source_token_count=membership[4],
            token_ids=token_ids,
        )
        if not hmac.compare_digest(expected_binding, membership[5]):
            raise PreparationError("source-row token content binding does not reconcile")
    return MappingProxyType(dict(membership_rows))


def _base_array_files(bundle: PreparationBundle) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for condition in CONDITIONS:
        for split in ("train", "validation"):
            sequences = [
                sequence
                for sequence in bundle.packing.sequences
                if sequence.condition == condition and sequence.split == split
            ]
            if not sequences:
                raise PreparationError("every condition and split requires packed sequences")
            prefix = f"arrays/{condition}/{split}"
            files[f"{prefix}/input_ids.npy"] = _npy_bytes(
                np.asarray([sequence.input_ids for sequence in sequences], dtype=np.uint16)
            )
            files[f"{prefix}/attention_mask.npy"] = _npy_bytes(
                np.asarray([sequence.attention_mask for sequence in sequences], dtype=np.uint8)
            )
            files[f"{prefix}/token_type_ids.npy"] = _npy_bytes(
                np.asarray([sequence.token_type_ids for sequence in sequences], dtype=np.uint8)
            )
    return files


def _artifact_files(
    bundle: PreparationBundle,
    *,
    hmac_key: bytes,
    runtime_identity: Mapping[str, Any],
) -> tuple[dict[str, bytes], tuple[dict[str, object], ...]]:
    _require_hmac_key(hmac_key)
    files = _base_array_files(bundle)
    serialized_validation_records: list[dict[str, object]] = []
    for material in bundle.validation:
        prefix = f"validation/{material.condition}/{material.plan_name}"
        files[f"{prefix}/masked_input_ids.npy"] = _npy_bytes(material.masked_input_ids)
        files[f"{prefix}/labels.npy"] = _npy_bytes(material.labels)
        files[f"{prefix}/attention_mask.npy"] = _npy_bytes(material.attention_mask)
        files[f"{prefix}/token_type_ids.npy"] = _npy_bytes(material.token_type_ids)
        files[f"{prefix}/example_identities.json"] = canonical_json_bytes(
            {
                "identity_protocol": "packing_sequence_identity_sha256_v1",
                "ordered_example_identities": material.example_identities,
            }
        )
        record_payload = {
            "plan_name": material.plan_name,
            **_validation_record_payload(material.record),
        }
        serialized_validation_records.append(record_payload)
        files[f"{prefix}/validation_mask_record.json"] = canonical_json_bytes(
            _validation_record_payload(material.record)
        )
    files["audits/exposure.json"] = canonical_json_bytes(_exposure_payload(bundle.exposure_audit))
    files["runtime.json"] = canonical_json_bytes(runtime_identity)
    files["provenance.json"] = canonical_json_bytes(
        [_provenance_payload(sequence, hmac_key) for sequence in bundle.packing.sequences]
    )
    files["membership.json"] = canonical_json_bytes(
        _serialized_membership_payload(bundle, hmac_key=hmac_key)
    )
    return dict(sorted(files.items())), tuple(serialized_validation_records)


def _recompute_membership_digest(
    rows: tuple[PreparedPreparationRow, ...],
    hmac_key: bytes,
    input_anchor: InputPopulationAnchor | None,
) -> str:
    blocks: dict[BlockKey, list[PreparedPreparationRow]] = {
        key: [] for key in approved_block_order()
    }
    for row in rows:
        if row.block_key not in blocks:
            raise PreparationError("published membership contains an unauthorized block")
        blocks[row.block_key].append(row)
    digest = hmac.new(hmac_key, digestmod=hashlib.sha256)
    if input_anchor is not None:
        input_anchor._validate()
        digest.update(canonical_json_bytes(["input_anchor", input_anchor.identity_sha256]))
    for key in approved_block_order():
        block = blocks[key]
        identities = tuple(_membership_identity(row) for row in block)
        lexical = sum(row.lexical_token_count for row in block)
        digest.update(canonical_json_bytes([key, identities, lexical]))
    return digest.hexdigest()


def _validate_bundle_for_publication(
    bundle: PreparationBundle,
    *,
    hmac_key: bytes,
) -> None:
    if not isinstance(bundle, PreparationBundle):
        raise PreparationError("publisher requires a derived preparation bundle")
    if (
        bundle.protocol_version != PREPARATION_PROTOCOL_VERSION
        or not isinstance(bundle.input_anchor, InputPopulationAnchor)
        or bundle.membership.input_population_anchor_sha256
        != bundle.input_anchor.identity_sha256
        or bundle.tokenizer_checksum_record_sha256
        != APPROVED_TOKENIZER_CHECKSUM_RECORD_SHA256
        or not isinstance(bundle.tokenizer_historical_build_identity, Mapping)
    ):
        raise PreparationError("publisher requires a checksum-anchored production bundle")
    bundle.input_anchor._validate()
    bundle.membership_plan._validate()
    if not isinstance(bundle.membership, MembershipValidation) or not bundle.membership.test_sealed:
        raise PreparationError("publisher lacks a passed test seal")
    if any(
        row.split not in {"train", "validation"}
        for row in bundle.rows
    ):
        raise PreparationError("test row reached the publication boundary")
    for row in bundle.rows:
        row._validate()
    _validate_cross_condition_reuse(bundle.rows)
    row_totals = Counter(row.block_key for row in bundle.rows)
    lexical_totals: Counter[BlockKey] = Counter()
    for row in bundle.rows:
        lexical_totals[row.block_key] += row.lexical_token_count
    if (
        tuple((key, row_totals[key]) for key in approved_block_order())
        != bundle.membership.row_totals
        or tuple((key, lexical_totals[key]) for key in approved_block_order())
        != bundle.membership.lexical_totals
        or _recompute_membership_digest(bundle.rows, hmac_key, bundle.input_anchor)
        != bundle.membership.ordered_digest_hmac_sha256
    ):
        raise PreparationError("publisher membership completeness binding failed")
    source_rows = {
        (
            item.condition,
            item.split,
            item.source,
            item.component,
            item.document_id,
            item.conversation_id,
            item.span_id,
            item.row_id,
            item.row_order,
            item.language_shard,
        )
        for sequence in bundle.packing.sequences
        for item in sequence.provenance
    }
    expected_rows = {
        (
            row.condition,
            row.split,
            row.source,
            row.component,
            row.document_id,
            row.conversation_id,
            row.span_id,
            row.row_id,
            row.row_order,
            row.language_shard,
        )
        for row in bundle.rows
    }
    if source_rows != expected_rows:
        raise PreparationError("publisher packing membership does not reconcile")
    exposure_failed = False
    try:
        from cslm.modeling.exposure import audit_exposure

        repeated_audit = audit_exposure((bundle.packing,))
    except Exception:
        repeated_audit = None
        exposure_failed = True
    if exposure_failed or repeated_audit is None:
        _raise_fixed("publisher exposure revalidation failed")
    if repeated_audit != bundle.exposure_audit:
        raise PreparationError("publisher exposure record is not derived from packing")
    repeated_validation = materialize_fixed_validation(bundle.packing.sequences)
    if len(repeated_validation) != len(bundle.validation):
        raise PreparationError("publisher fixed validation population is incomplete")
    for expected, actual in zip(repeated_validation, bundle.validation, strict=True):
        if not (
            expected.condition == actual.condition
            and expected.plan_name == actual.plan_name
            and expected.seed == actual.seed
            and expected.record == actual.record
            and expected.example_identities == actual.example_identities
            and np.array_equal(expected.masked_input_ids, actual.masked_input_ids)
            and np.array_equal(expected.labels, actual.labels)
            and np.array_equal(expected.attention_mask, actual.attention_mask)
            and np.array_equal(expected.token_type_ids, actual.token_type_ids)
        ):
            raise PreparationError("publisher fixed validation revalidation failed")


@dataclass(frozen=True, init=False, slots=True)
class CandidateChecksumRecord:
    """Deterministic internal-consistency record; scientific approval is external."""

    checksums: tuple[tuple[str, str], ...]
    file_inventory: tuple[str, ...]
    identity_sha256: str

    def __new__(cls) -> CandidateChecksumRecord:
        raise PreparationError("candidate checksum records must be factory-derived")


def _candidate_checksum_payload(
    files: Mapping[str, bytes],
    *,
    inventory: Iterable[str],
    protocol_version: str,
) -> dict[str, object]:
    return {
        "algorithm": "sha256",
        "artifacts": {
            name: _sha256_bytes(content) for name, content in sorted(files.items())
        },
        "completion_state": {
            "complete": True,
            "status": "candidate_unapproved",
        },
        "file_inventory": sorted(inventory),
        "protocol_version": protocol_version,
        "schema_version": 1,
        "status": "candidate_unapproved",
    }


def _derive_candidate_checksum_record(
    files: Mapping[str, bytes],
    *,
    inventory: Iterable[str],
    protocol_version: str,
) -> tuple[CandidateChecksumRecord, bytes]:
    payload = _candidate_checksum_payload(
        files,
        inventory=inventory,
        protocol_version=protocol_version,
    )
    serialized = canonical_json_bytes(payload)
    result = object.__new__(CandidateChecksumRecord)
    object.__setattr__(
        result,
        "checksums",
        tuple(sorted(payload["artifacts"].items())),
    )
    object.__setattr__(
        result,
        "file_inventory",
        tuple(payload["file_inventory"]),
    )
    object.__setattr__(result, "identity_sha256", _sha256_bytes(serialized))
    return result, serialized


@dataclass(frozen=True, init=False)
class PreparationManifest:
    protocol_version: str
    payload: Mapping[str, Any]
    identity_sha256: str

    def __new__(cls) -> PreparationManifest:
        raise PreparationError("preparation manifests must be factory-derived")

    def _validate(self) -> None:
        if self.protocol_version != PREPARATION_PROTOCOL_VERSION:
            raise PreparationError("preparation manifest protocol is not production")
        if _sha256_bytes(canonical_json_bytes(self.payload)) != self.identity_sha256:
            raise PreparationError("preparation manifest identity does not derive from its payload")


def _aggregate_manifest_payload(bundle: PreparationBundle) -> dict[str, object]:
    rows = Counter((row.condition, row.split) for row in bundle.rows)
    lexical = Counter()
    for row in bundle.rows:
        lexical[(row.condition, row.split)] += row.lexical_token_count
    wordpieces = Counter(bundle.packing.source_wordpieces_by_group)
    sequences = Counter((seq.condition, seq.split) for seq in bundle.packing.sequences)
    padding = Counter()
    for sequence in bundle.packing.sequences:
        padding[(sequence.condition, sequence.split)] += sequence.padding_count
    return {
        condition: {
            split: {
                "rows": rows[(condition, split)],
                "lexical_tokens": lexical[(condition, split)],
                "wordpieces": wordpieces[(condition, split)],
                "sequences": sequences[(condition, split)],
                "padding": padding[(condition, split)],
            }
            for split in ("train", "validation")
        }
        for condition in CONDITIONS
    }


def _derive_preparation_manifest(
    bundle: PreparationBundle,
    *,
    runtime_identity: Mapping[str, Any],
    serialized_validation_records: Sequence[Mapping[str, object]],
) -> PreparationManifest:
    payload: dict[str, Any] = {
        "protocol_version": PREPARATION_PROTOCOL_VERSION,
        "status": "candidate_unapproved",
        "internal_tracker_version": INTERNAL_TRACKER_VERSION,
        "frozen_checksum_record_identities": {
            "CsCont": APPROVED_CSCONT_CHECKSUM_RECORD_SHA256,
            "CALLHOME_pilot_conditions": APPROVED_CALLHOME_CHECKSUM_RECORD_SHA256,
            "tokenizer": APPROVED_TOKENIZER_CHECKSUM_RECORD_SHA256,
        },
        "tokenizer_loader_protocol": bundle.tokenizer_loader_protocol,
        "tokenizer_synthetic_parity_passed": True,
        "tokenizer_synthetic_parity_sha256": bundle.tokenizer_synthetic_parity_sha256,
        "tokenizer_artifact_sha256": bundle.tokenizer_artifact_sha256,
        "tokenizer_backend_configuration_sha256": (
            bundle.tokenizer_backend_configuration_sha256
        ),
        "historical_tokenizer_build_identity": bundle.tokenizer_historical_build_identity,
        "input_population_anchor": {
            "identity_sha256": bundle.input_anchor.identity_sha256,
            "checksum_record_identities": dict(
                bundle.input_anchor.checksum_record_identities
            ),
            "constituent_sha256": dict(bundle.input_anchor.constituent_sha256),
            "input_line_counts": dict(bundle.input_anchor.input_line_counts),
            "authorized_line_counts": dict(bundle.input_anchor.authorized_line_counts),
            "sealed_test_line_counts": dict(bundle.input_anchor.sealed_test_line_counts),
        },
        "subset_reconciliation": {
            "monocont_english_subset_of_englishmono": True,
            "monocont_spanish_subset_of_spanishmono": True,
            "cscont_callhome_filler_subset_of_monocont": True,
        },
        "test_seal": {"passed": bundle.membership.test_sealed, "test_rows_emitted": 0},
        "conditions": list(CONDITIONS),
        "included_splits": ["train", "validation"],
        "aggregates": _aggregate_manifest_payload(bundle),
        "exposure": _exposure_payload(bundle.exposure_audit),
        "fixed_validation_seed_plans": [
            {"name": name, "validation_mask_seed": seed}
            for name, seed in approved_validation_seed_plans()
        ],
        "derived_validation_records": list(serialized_validation_records),
        "serialization": dict(_SERIALIZATION_SCHEMA),
        "runtime_identity": runtime_identity,
    }
    manifest = object.__new__(PreparationManifest)
    object.__setattr__(manifest, "protocol_version", PREPARATION_PROTOCOL_VERSION)
    object.__setattr__(manifest, "payload", MappingProxyType(payload))
    object.__setattr__(manifest, "identity_sha256", _sha256_bytes(canonical_json_bytes(payload)))
    manifest._validate()
    return manifest


def _create_hmac_key(path: Path, *, byte_count: int = 32) -> None:
    """Safely create a separately held owner-only key; never overwrite."""
    if byte_count < 32:
        raise PreparationError("HMAC key destination or size is not approved")
    absolute = path.expanduser().absolute()
    parent_descriptor = _open_directory_chain(absolute.parent)
    try:
        descriptor = os.open(
            absolute.name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0),
            PRIVATE_FILE_MODE,
            dir_fd=parent_descriptor,
        )
    finally:
        os.close(parent_descriptor)
    try:
        key = os.urandom(byte_count)
        view = memoryview(key)
        while view:
            written = os.write(descriptor, view)
            view = view[written:]
        os.fsync(descriptor)
        _verify_owner_mode(
            os.fstat(descriptor),
            expected_mode=PRIVATE_FILE_MODE,
            kind="file",
        )
    except BaseException:
        os.close(descriptor)
        key = b""
        parent_descriptor = _open_directory_chain(absolute.parent)
        try:
            try:
                os.unlink(absolute.name, dir_fd=parent_descriptor)
            except FileNotFoundError:
                pass
        finally:
            os.close(parent_descriptor)
        _raise_fixed("HMAC key creation failed")
    os.close(descriptor)
    key = b""
    _fsync_directory(absolute.parent)


def create_hmac_key(path: Path, *, byte_count: int = 32) -> None:
    """Create a key through a privacy-scrubbing exception boundary."""
    failed = False
    try:
        _create_hmac_key(path, byte_count=byte_count)
    except BaseException:
        failed = True
    path = Path()
    byte_count = 0
    if failed:
        _raise_fixed("HMAC key creation failed")


def _inside_git_repository(path: Path) -> bool:
    absolute = path.expanduser().absolute()
    for parent in (absolute.parent, *absolute.parents):
        marker = parent / ".git"
        try:
            metadata = marker.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISDIR(metadata.st_mode) or stat.S_ISREG(metadata.st_mode):
            return True
    return False


def _load_hmac_key(
    path: Path,
    *,
    forbidden_roots: Sequence[Path] = (),
) -> bytes:
    """Load a separate owner-only regular key without exposing its bytes."""
    if _inside_git_repository(path) or any(_paths_overlap(path, root) for root in forbidden_roots):
        path = Path()
        forbidden_roots = ()
        raise PreparationError("HMAC key must remain outside protected roots")
    snapshot: _StableFileSnapshot | None = None
    failed = False
    try:
        snapshot = _snapshot_absolute_regular_file(path, maximum_bytes=4096)
    except BaseException:
        failed = True
    path = Path()
    if failed or snapshot is None:
        _raise_fixed("HMAC key is unavailable")
    key = snapshot.content
    snapshot = None
    valid = isinstance(key, bytes) and len(key) >= 32
    if not valid:
        key = b""
        _raise_fixed("HMAC key is unavailable")
    return key


def load_hmac_key(
    path: Path,
    *,
    forbidden_roots: Sequence[Path] = (),
) -> bytes:
    """Load a key through a privacy-scrubbing exception boundary."""
    key = b""
    failed = False
    try:
        key = _load_hmac_key(path, forbidden_roots=forbidden_roots)
    except BaseException:
        failed = True
    path = Path()
    forbidden_roots = ()
    if failed:
        key = b""
        _raise_fixed("HMAC key is unavailable")
    return key


def _resolved_without_symlinks(path: Path) -> Path:
    expanded = path.expanduser()
    if any(part in {"", ".", ".."} for part in expanded.parts[1:]):
        raise PreparationError("filesystem path is not canonical")
    absolute = expanded.absolute()
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        try:
            metadata = current.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(metadata.st_mode):
            raise PreparationError("filesystem path contains a symlink")
    return absolute


def _paths_overlap(first: Path, second: Path) -> bool:
    first_resolved = first.resolve(strict=False)
    second_resolved = second.resolve(strict=False)
    return (
        first_resolved == second_resolved
        or first_resolved in second_resolved.parents
        or second_resolved in first_resolved.parents
    )


def validate_publication_paths(
    output_root: Path,
    *,
    input_roots: Sequence[Path],
    hmac_key_path: Path,
) -> None:
    """Validate and immediately release an independently derived output parent."""
    pinned = _pin_publication_parent(
        output_root,
        input_roots=input_roots,
        hmac_key_path=hmac_key_path,
    )
    os.close(pinned.descriptor)


@dataclass(frozen=True)
class _PinnedPublicationParent:
    descriptor: int = field(repr=False)
    path: Path = field(repr=False)
    device: int
    inode: int
    target_name: str


def _pin_publication_parent(
    output_root: Path,
    *,
    input_roots: Sequence[Path],
    hmac_key_path: Path | None,
) -> _PinnedPublicationParent:
    """Pin the verified output parent through the publication commit point."""
    output = _resolved_without_symlinks(output_root.expanduser())
    inputs = tuple(_resolved_without_symlinks(path) for path in input_roots)
    if output.exists() or output.is_symlink():
        raise PreparationError("candidate output already exists")
    implementation_root = Path(__file__).resolve().parents[3]
    if _inside_git_repository(output) or _paths_overlap(output, implementation_root):
        raise PreparationError("output root must remain outside the Git repository")
    if any(_paths_overlap(output, input_root) for input_root in inputs):
        raise PreparationError("output root overlaps an input root")
    if hmac_key_path is not None:
        key = _resolved_without_symlinks(hmac_key_path)
        if _paths_overlap(key, output) or any(
            _paths_overlap(key, root) for root in inputs
        ):
            raise PreparationError("HMAC key must remain separate from outputs and inputs")
    parent = output.parent
    if parent.is_symlink() or not parent.is_dir():
        raise PreparationError("output parent is not a real directory")
    descriptor = _open_directory_chain(parent)
    try:
        metadata = os.fstat(descriptor)
        _verify_owner_mode(
            metadata,
            expected_mode=PRIVATE_DIRECTORY_MODE,
            kind="directory",
        )
    except BaseException:
        os.close(descriptor)
        raise
    return _PinnedPublicationParent(
        descriptor=descriptor,
        path=parent,
        device=metadata.st_dev,
        inode=metadata.st_ino,
        target_name=output.name,
    )


def _verify_named_parent(pinned: _PinnedPublicationParent) -> None:
    descriptor: int | None = None
    failed = False
    try:
        descriptor = _open_directory_chain(pinned.path)
    except BaseException:
        failed = True
    if descriptor is not None:
        try:
            metadata = os.fstat(descriptor)
        finally:
            os.close(descriptor)
        if (metadata.st_dev, metadata.st_ino) != (pinned.device, pinned.inode):
            failed = True
    descriptor = None
    if failed:
        raise PreparationError("output parent identity changed")


def _relative_parent_descriptor(root_descriptor: int, name: str) -> tuple[int, str]:
    canonical = _safe_relative_name(name)
    parts = Path(canonical).parts
    descriptor = os.dup(root_descriptor)
    try:
        for part in parts[:-1]:
            try:
                os.mkdir(
                    part,
                    PRIVATE_DIRECTORY_MODE,
                    dir_fd=descriptor,
                )
            except FileExistsError:
                pass
            child = os.open(part, _directory_open_flags(), dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
            _verify_owner_mode(
                os.fstat(descriptor),
                expected_mode=PRIVATE_DIRECTORY_MODE,
                kind="directory",
            )
        return descriptor, parts[-1]
    except BaseException:
        os.close(descriptor)
        raise


def _write_private_file_at(root_descriptor: int, name: str, content: bytes) -> None:
    parent, leaf = _relative_parent_descriptor(root_descriptor, name)
    try:
        descriptor = os.open(
            leaf,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0),
            PRIVATE_FILE_MODE,
            dir_fd=parent,
        )
    finally:
        os.close(parent)
    try:
        view = memoryview(content)
        while view:
            written = os.write(descriptor, view)
            view = view[written:]
        os.fsync(descriptor)
        _verify_owner_mode(
            os.fstat(descriptor),
            expected_mode=PRIVATE_FILE_MODE,
            kind="file",
        )
    finally:
        os.close(descriptor)


def _fsync_directory(path: Path) -> None:
    descriptor = _open_directory_chain(path)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _fsync_tree_descriptor(root_descriptor: int) -> None:
    def visit(descriptor: int) -> None:
        entries = sorted(os.scandir(descriptor), key=lambda entry: entry.name)
        for entry in entries:
            metadata = entry.stat(follow_symlinks=False)
            if stat.S_ISDIR(metadata.st_mode):
                child = os.open(
                    entry.name,
                    _directory_open_flags(),
                    dir_fd=descriptor,
                )
                try:
                    visit(child)
                finally:
                    os.close(child)
            elif not stat.S_ISREG(metadata.st_mode):
                raise PreparationError("staging tree contains a non-regular entry")
        os.fsync(descriptor)

    duplicate = os.dup(root_descriptor)
    try:
        visit(duplicate)
    finally:
        os.close(duplicate)


def _atomic_rename_noreplace_at(
    parent_descriptor: int,
    source_name: str,
    target_name: str,
) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    source_bytes = os.fsencode(source_name)
    target_bytes = os.fsencode(target_name)
    if sys.platform == "darwin" and hasattr(libc, "renameatx_np"):
        rename = libc.renameatx_np
        rename.argtypes = (
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        )
        rename.restype = ctypes.c_int
        result = rename(
            parent_descriptor,
            source_bytes,
            parent_descriptor,
            target_bytes,
            0x00000004,
        )
    elif sys.platform.startswith("linux") and hasattr(libc, "renameat2"):
        rename = libc.renameat2
        rename.argtypes = (
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        )
        rename.restype = ctypes.c_int
        result = rename(
            parent_descriptor,
            source_bytes,
            parent_descriptor,
            target_bytes,
            0x00000001,
        )
    else:
        raise PreparationError("atomic no-replace publication is unavailable")
    if result != 0:
        error_number = ctypes.get_errno()
        if error_number in {errno.EEXIST, errno.ENOTEMPTY}:
            raise PreparationError("candidate output appeared before the commit point")
        raise PreparationError("atomic no-replace publication failed")


def _remove_verified_stage_at(
    parent_descriptor: int,
    stage_name: str,
    *,
    device: int,
    inode: int,
) -> None:
    try:
        descriptor = os.open(
            stage_name,
            _directory_open_flags(),
            dir_fd=parent_descriptor,
        )
    except FileNotFoundError:
        return
    try:
        metadata = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if not stat.S_ISDIR(metadata.st_mode) or (
        metadata.st_dev,
        metadata.st_ino,
    ) != (device, inode):
        raise PreparationError("staging path identity changed; cleanup refused")
    shutil.rmtree(stage_name, dir_fd=parent_descriptor)


class PublicationCommittedError(PreparationError):
    """The atomic commit occurred, but post-commit durability could not be confirmed."""

    committed = True
    retry_forbidden = True


class PublicationOutcomeIndeterminateError(PreparationError):
    """Publication may have committed, so an automatic retry is never safe."""

    committed = None
    retry_forbidden = True


def _publication_name_identity_at(
    parent_descriptor: int,
    name: str,
) -> tuple[int, int] | None:
    """Return a directory identity without following a publication-name symlink."""
    try:
        metadata = os.stat(
            name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        return None
    if not stat.S_ISDIR(metadata.st_mode):
        raise PreparationError("publication name is not a private directory")
    return metadata.st_dev, metadata.st_ino


def _close_publication_descriptors(
    stage_descriptor: int | None,
    parent_descriptor: int | None,
) -> bool:
    """Attempt each final close once and report only whether cleanup failed."""
    failed = False
    for descriptor in (stage_descriptor, parent_descriptor):
        if descriptor is None:
            continue
        try:
            os.close(descriptor)
        except BaseException:
            failed = True
    return failed


def _commit_private_tree(
    files: Mapping[str, bytes],
    *,
    output_root: Path,
    input_roots: Sequence[Path],
    hmac_key_path: Path | None,
    staging_label: str,
    precommit_validator: Callable[[int], None],
    test_hook: Callable[[str], None] | None = None,
) -> None:
    """Commit a private tree with complete descriptor cleanup around every failure."""

    pinned: _PinnedPublicationParent | None = None
    stage_descriptor: int | None = None
    stage_name = ""
    stage_identity: tuple[int, int] | None = None
    promoted = False
    committed_error = False
    failure_kind: Literal["none", "precommit", "committed", "indeterminate"] = "none"
    candidate = ""
    ordered_files: list[tuple[str, bytes]] = []
    name = ""
    content = b""
    try:
        if test_hook is not None:
            test_hook("before_parent_pin")
        pinned = _pin_publication_parent(
            output_root,
            input_roots=input_roots,
            hmac_key_path=hmac_key_path,
        )
        if test_hook is not None:
            test_hook("before_mkdir")
        for _ in range(128):
            candidate = (
                f".{pinned.target_name}.{staging_label}-{os.urandom(12).hex()}"
            )
            try:
                os.mkdir(
                    candidate,
                    PRIVATE_DIRECTORY_MODE,
                    dir_fd=pinned.descriptor,
                )
            except FileExistsError:
                continue
            stage_name = candidate
            break
        if not stage_name:
            raise PreparationError("private staging name allocation failed")
        named_metadata = os.stat(
            stage_name,
            dir_fd=pinned.descriptor,
            follow_symlinks=False,
        )
        stage_identity = (named_metadata.st_dev, named_metadata.st_ino)
        if test_hook is not None:
            test_hook("before_stage_open")
        stage_descriptor = os.open(
            stage_name,
            _directory_open_flags(),
            dir_fd=pinned.descriptor,
        )
        if test_hook is not None:
            test_hook("before_stage_fstat")
        opened_metadata = os.fstat(stage_descriptor)
        if (
            not stat.S_ISDIR(opened_metadata.st_mode)
            or (opened_metadata.st_dev, opened_metadata.st_ino) != stage_identity
        ):
            raise PreparationError("staging directory identity changed")
        completion_markers = {
            "CANDIDATE_COMPLETE.json",
            "SYNTHETIC-COMPLETE.json",
        }
        ordered_files = sorted(
            files.items(),
            key=lambda item: (item[0] in completion_markers, item[0]),
        )
        for name, content in ordered_files:
            _write_private_file_at(stage_descriptor, name, content)
        if test_hook is not None:
            test_hook("before_commit")
        _fsync_tree_descriptor(stage_descriptor)
        precommit_validator(stage_descriptor)
        _verify_named_parent(pinned)
        if test_hook is not None:
            test_hook("before_atomic_rename")
        try:
            _atomic_rename_noreplace_at(
                pinned.descriptor,
                stage_name,
                pinned.target_name,
            )
            # Record the commit before any further fallible operation.  The
            # exception recovery below also covers an asynchronous exception
            # between the system call's return and this assignment.
            promoted = True
        except BaseException as rename_error:
            try:
                source_identity = _publication_name_identity_at(
                    pinned.descriptor,
                    stage_name,
                )
                target_identity = _publication_name_identity_at(
                    pinned.descriptor,
                    pinned.target_name,
                )
            except BaseException as inspection_error:
                promoted = True
                raise PublicationOutcomeIndeterminateError(
                    "atomic publication outcome could not be established; "
                    "retry is forbidden"
                ) from inspection_error
            if target_identity == stage_identity:
                promoted = True
                raise PublicationCommittedError(
                    "publication committed to the pinned parent; retry is forbidden"
                ) from rename_error
            if source_identity == stage_identity and target_identity != stage_identity:
                raise
            promoted = True
            raise PublicationOutcomeIndeterminateError(
                "atomic publication outcome could not be established; "
                "retry is forbidden"
            ) from rename_error
        try:
            if test_hook is not None:
                test_hook("after_commit_before_parent_fsync")
            os.fsync(pinned.descriptor)
            _verify_named_parent(pinned)
        except BaseException:
            committed_error = True
    except PublicationCommittedError:
        failure_kind = "committed"
    except PublicationOutcomeIndeterminateError:
        failure_kind = "indeterminate"
    except BaseException:
        failure_kind = "committed" if promoted else "precommit"

    if committed_error:
        failure_kind = "committed"
    cleanup_failed = False
    if (
        failure_kind == "precommit"
        and pinned is not None
        and stage_name
        and stage_identity is not None
    ):
        try:
            _remove_verified_stage_at(
                pinned.descriptor,
                stage_name,
                device=stage_identity[0],
                inode=stage_identity[1],
            )
        except BaseException:
            cleanup_failed = True

    parent_descriptor = pinned.descriptor if pinned is not None else None
    cleanup_failed = (
        _close_publication_descriptors(stage_descriptor, parent_descriptor)
        or cleanup_failed
    )
    if cleanup_failed and failure_kind == "none":
        failure_kind = "committed" if promoted else "precommit"

    files = {}
    output_root = Path()
    input_roots = ()
    hmac_key_path = None
    precommit_validator = None
    test_hook = None
    pinned = None
    stage_descriptor = None
    parent_descriptor = None
    stage_name = ""
    stage_identity = None
    candidate = ""
    ordered_files.clear()
    name = ""
    content = b""

    if failure_kind == "committed":
        raise PublicationCommittedError(
            "publication committed to the pinned parent; final durability or cleanup "
            "reported a failure, commit state is true, and retry is forbidden"
        )
    if failure_kind == "indeterminate":
        raise PublicationOutcomeIndeterminateError(
            "publication outcome is indeterminate and retry is forbidden"
        )
    if failure_kind == "precommit":
        raise PreparationError("pre-commit publication or cleanup failed")


@dataclass(frozen=True, init=False, slots=True)
class PublishedPreparationCandidate:
    output_root: Path = field(repr=False)
    status: str
    manifest: PreparationManifest
    checksum_record: CandidateChecksumRecord
    candidate_checksum_record_sha256: str

    def __new__(cls) -> PublishedPreparationCandidate:
        raise PreparationError("published candidate results must be runner-derived")


def _publish_preparation(
    bundle: PreparationBundle,
    *,
    output_root: Path,
    input_roots: Sequence[Path],
    hmac_key_path: Path,
) -> PublishedPreparationCandidate:
    """Serialize a complete, internally verified, scientifically unapproved candidate."""
    output = output_root.expanduser().absolute()
    hmac_key = load_hmac_key(
        hmac_key_path,
        forbidden_roots=(output, *input_roots),
    )
    _validate_bundle_for_publication(
        bundle,
        hmac_key=hmac_key,
    )
    runtime = collect_runtime_identity(bundle=bundle)
    files, serialized_validation_records = _artifact_files(
        bundle,
        hmac_key=hmac_key,
        runtime_identity=runtime,
    )
    manifest = _derive_preparation_manifest(
        bundle,
        runtime_identity=runtime,
        serialized_validation_records=serialized_validation_records,
    )
    manifest_payload = dict(manifest.payload)
    manifest_payload["preparation_manifest_identity_sha256"] = manifest.identity_sha256
    manifest_bytes = canonical_json_bytes(manifest_payload)
    checksummed_files = {
        **files,
        "PREPARATION_MANIFEST.json": manifest_bytes,
    }
    full_inventory = set(checksummed_files) | {
        "checksums.json",
        "CANDIDATE_COMPLETE.json",
    }
    checksum_record, checksum_bytes = _derive_candidate_checksum_record(
        checksummed_files,
        inventory=full_inventory,
        protocol_version=PREPARATION_PROTOCOL_VERSION,
    )
    completion_bytes = canonical_json_bytes(
        {
            "candidate_checksum_record_sha256": checksum_record.identity_sha256,
            "complete": True,
            "protocol_version": PREPARATION_PROTOCOL_VERSION,
            "status": "candidate_unapproved",
        }
    )
    all_files = {
        **checksummed_files,
        "checksums.json": checksum_bytes,
        "CANDIDATE_COMPLETE.json": completion_bytes,
    }

    def validate_stage(descriptor: int) -> None:
        current_environment = _actual_runtime_environment_controls()
        if dict(current_environment) != runtime["environment_controls"]:
            raise PreparationError(
                "deterministic environment controls changed during preparation"
            )
        snapshot = _load_preparation_candidate(
            Path(),
            root_descriptor=descriptor,
            reconciliation_key=hmac_key,
        )
        if snapshot.candidate_checksum_record_sha256 != checksum_record.identity_sha256:
            raise PreparationError("candidate checksum readback failed")

    _commit_private_tree(
        all_files,
        output_root=output,
        input_roots=input_roots,
        hmac_key_path=hmac_key_path,
        staging_label="staging",
        precommit_validator=validate_stage,
    )
    hmac_key = b""
    result = object.__new__(PublishedPreparationCandidate)
    object.__setattr__(result, "output_root", output)
    object.__setattr__(result, "status", "candidate_unapproved")
    object.__setattr__(result, "manifest", manifest)
    object.__setattr__(result, "checksum_record", checksum_record)
    object.__setattr__(
        result,
        "candidate_checksum_record_sha256",
        checksum_record.identity_sha256,
    )
    return result


def _create_closed_production_entrypoint() -> Callable[
    [ProductionPreparationPaths, Path],
    PublishedPreparationCandidate,
]:
    frozen_controls = (
        "25489e732b64ce63c0380012ea719571f9cb4fc6c369e43da920d2b45af55b8d",
        "840236bdd4c8f3d18898b02c824478dfbb663f160bc03d13590ae5ca4dc8003f",
        "f06216f6588337c53100cf6066166f4979b3b06fe0f8a65c04e350fd8fcb0b3e",
        (
            ("CsCont", 14_366, 90_000, 706, 5_000),
            ("EnglishMono", 13_136, 90_000, 735, 5_000),
            ("MonoCont:english", 6_654, 45_000, 355, 2_500),
            ("MonoCont:spanish", 6_125, 45_000, 299, 2_500),
            ("SpanishMono", 12_091, 90_000, 600, 5_000),
        ),
        "~/NEU_LAB_frozen_artifacts/model_ready/real_preparation_v1",
    )

    def prepare_and_publish(
        paths: ProductionPreparationPaths,
        output_root: Path,
    ) -> PublishedPreparationCandidate:
        current_aggregates = tuple(
            sorted(
                (
                    name,
                    value.train_rows,
                    value.train_lexical_tokens,
                    value.validation_rows,
                    value.validation_lexical_tokens,
                )
                for name, value in APPROVED_REAL_AGGREGATES.items()
            )
        )
        if (
            APPROVED_TOKENIZER_CHECKSUM_RECORD_SHA256 != frozen_controls[0]
            or APPROVED_CALLHOME_CHECKSUM_RECORD_SHA256 != frozen_controls[1]
            or APPROVED_CSCONT_CHECKSUM_RECORD_SHA256 != frozen_controls[2]
            or current_aggregates != frozen_controls[3]
            or str(APPROVED_PRIVATE_OUTPUT_ROOT) != frozen_controls[4]
        ):
            raise PreparationError("production scientific controls were altered")
        approved_output = Path(frozen_controls[4]).expanduser().absolute()
        if output_root.expanduser().absolute() != approved_output:
            raise PreparationError("production output root is not the approved private root")
        _actual_runtime_environment_controls()
        bundle: PreparationBundle | None = None
        result: PublishedPreparationCandidate | None = None
        failed = False
        committed = False
        indeterminate = False
        try:
            bundle = _prepare_production_inputs(paths)
            result = _publish_preparation(
                bundle,
                output_root=approved_output,
                input_roots=(
                    paths.callhome_root,
                    paths.cscont_root,
                    paths.tokenizer_root,
                ),
                hmac_key_path=paths.hmac_key_path,
            )
        except PublicationCommittedError:
            committed = True
        except PublicationOutcomeIndeterminateError:
            indeterminate = True
        except BaseException:
            failed = True
        finally:
            bundle = None
            paths = ProductionPreparationPaths(Path(), Path(), Path(), Path())
            output_root = Path()
        if committed:
            raise PublicationCommittedError(
                "publication committed to the pinned parent; retry is forbidden"
            )
        if indeterminate:
            raise PublicationOutcomeIndeterminateError(
                "publication outcome is indeterminate; retry is forbidden"
            )
        if failed or result is None:
            _raise_fixed("closed production prepare-and-publish failed")
        return result

    return prepare_and_publish


prepare_and_publish_production = _create_closed_production_entrypoint()
del _create_closed_production_entrypoint


_SYNTHETIC_CONTROL_FILES = frozenset(
    {
        "SYNTHETIC-ARTIFACTS.json",
        "SYNTHETIC-MANIFEST.json",
        "SYNTHETIC-COMPLETE.json",
    }
)


@dataclass(frozen=True)
class SyntheticPublishedPreparationCandidate:
    output_root: Path = field(repr=False)
    artifact_map_sha256: str
    manifest_sha256: str


@dataclass(frozen=True, init=False)
class SyntheticPreparationSnapshot:
    """Synthetic-only snapshot which production run construction always rejects."""

    artifact_map_sha256: str
    manifest_sha256: str
    _root: Path = field(repr=False)

    def __new__(cls) -> SyntheticPreparationSnapshot:
        raise PreparationError("synthetic bindings must be snapshot-derived")

    def _validate(self) -> None:
        loaded = load_synthetic_preparation_candidate(self._root)
        if (
            self.artifact_map_sha256,
            self.manifest_sha256,
        ) != (
            loaded.artifact_map_sha256,
            loaded.manifest_sha256,
        ):
            raise PreparationError("synthetic preparation binding changed")


def _commit_synthetic_snapshot(
    files: Mapping[str, bytes],
    *,
    output_root: Path,
    synthetic_test_hook: Callable[[str], None] | None,
) -> None:
    def validate_stage(descriptor: int) -> None:
        del descriptor

    failed = False
    try:
        _commit_private_tree(
            files,
            output_root=output_root,
            input_roots=(),
            hmac_key_path=None,
            staging_label="synthetic-staging",
            precommit_validator=validate_stage,
            test_hook=synthetic_test_hook,
        )
    except PublicationCommittedError:
        raise
    except PublicationOutcomeIndeterminateError:
        raise
    except BaseException:
        failed = True
    if failed:
        _raise_fixed("synthetic candidate publication failed")


def publish_synthetic_preparation(
    bundle: PreparationBundle,
    *,
    output_root: Path,
    hmac_key: bytes,
    synthetic_test_hook: Callable[[str], None] | None = None,
) -> SyntheticPublishedPreparationCandidate:
    """Publish mechanics under a categorically non-production protocol."""
    if (
        not isinstance(bundle, PreparationBundle)
        or bundle.protocol_version != SYNTHETIC_PREPARATION_PROTOCOL_VERSION
        or bundle.input_anchor is not None
        or bundle.tokenizer_historical_build_identity is not None
        or hmac_key != _SYNTHETIC_PRIVACY_RECONCILIATION_KEY
    ):
        raise PreparationError("synthetic publisher requires a synthetic-only bundle")
    runtime = {
        "protocol": SYNTHETIC_PREPARATION_PROTOCOL_VERSION,
        "runtime_identity": "synthetic-only",
    }
    artifacts, records = _artifact_files(
        bundle,
        hmac_key=hmac_key,
        runtime_identity=runtime,
    )
    prefixed_artifacts = {
        f"synthetic-artifacts/{name}": content
        for name, content in artifacts.items()
    }
    artifact_map_payload = {
        "algorithm": "sha256",
        "artifacts": {
            name: _sha256_bytes(content)
            for name, content in sorted(prefixed_artifacts.items())
        },
        "protocol": SYNTHETIC_PREPARATION_PROTOCOL_VERSION,
        "schema_version": 1,
    }
    artifact_map_bytes = canonical_json_bytes(artifact_map_payload)
    artifact_map_identity = _sha256_bytes(artifact_map_bytes)
    manifest_payload = {
        "artifact_map_sha256": artifact_map_identity,
        "protocol": SYNTHETIC_PREPARATION_PROTOCOL_VERSION,
        "synthetic_only": True,
        "validation_records": list(records),
    }
    manifest_identity = _sha256_bytes(canonical_json_bytes(manifest_payload))
    manifest_bytes = canonical_json_bytes(
        {
            **manifest_payload,
            "manifest_sha256": manifest_identity,
        }
    )
    completion_bytes = canonical_json_bytes(
        {
            "artifact_map_sha256": artifact_map_identity,
            "manifest_sha256": manifest_identity,
            "protocol": SYNTHETIC_PREPARATION_PROTOCOL_VERSION,
            "synthetic_only": True,
        }
    )
    all_files = {
        **prefixed_artifacts,
        "SYNTHETIC-ARTIFACTS.json": artifact_map_bytes,
        "SYNTHETIC-MANIFEST.json": manifest_bytes,
        "SYNTHETIC-COMPLETE.json": completion_bytes,
    }
    _commit_synthetic_snapshot(
        all_files,
        output_root=output_root,
        synthetic_test_hook=synthetic_test_hook,
    )
    return SyntheticPublishedPreparationCandidate(
        output_root.expanduser().absolute(),
        artifact_map_identity,
        manifest_identity,
    )


def load_synthetic_preparation_candidate(
    root: Path,
) -> SyntheticPreparationSnapshot:
    """Load only the distinct synthetic protocol and rederive validation semantics."""
    root_descriptor = _open_directory_chain(root)
    try:
        _verify_owner_mode(
            os.fstat(root_descriptor),
            expected_mode=PRIVATE_DIRECTORY_MODE,
            kind="directory",
        )
        files, directories = _walk_private_tree(root_descriptor)
        snapshots = {
            name: _snapshot_relative_regular_file(root_descriptor, name)
            for name in files
        }
    finally:
        os.close(root_descriptor)
    artifact_map = _strict_json_value(
        snapshots["SYNTHETIC-ARTIFACTS.json"].content,
        category="synthetic artifact map is malformed",
    )
    manifest_file = _strict_json_value(
        snapshots["SYNTHETIC-MANIFEST.json"].content,
        category="synthetic manifest is malformed",
    )
    completion = _strict_json_value(
        snapshots["SYNTHETIC-COMPLETE.json"].content,
        category="synthetic completion record is malformed",
    )
    if (
        not isinstance(artifact_map, dict)
        or set(artifact_map)
        != {"algorithm", "artifacts", "protocol", "schema_version"}
        or artifact_map["algorithm"] != "sha256"
        or artifact_map["protocol"] != SYNTHETIC_PREPARATION_PROTOCOL_VERSION
        or artifact_map["schema_version"] != 1
        or not isinstance(artifact_map["artifacts"], dict)
        or not artifact_map["artifacts"]
        or not isinstance(manifest_file, dict)
        or manifest_file.get("protocol") != SYNTHETIC_PREPARATION_PROTOCOL_VERSION
        or manifest_file.get("synthetic_only") is not True
    ):
        raise PreparationError("synthetic preparation controls are invalid")
    expected_files = set(artifact_map["artifacts"]) | set(_SYNTHETIC_CONTROL_FILES)
    if set(files) != expected_files or set(directories) != set(
        _required_directory_names(files)
    ):
        raise PreparationError("synthetic preparation inventory is not exact")
    for name, digest in artifact_map["artifacts"].items():
        if (
            _safe_relative_name(name) != name
            or not isinstance(digest, str)
            or not _SHA256_RE.fullmatch(digest)
            or _sha256_bytes(snapshots[name].content) != digest
        ):
            raise PreparationError("synthetic artifact checksum verification failed")
    artifact_map_identity = _sha256_bytes(
        snapshots["SYNTHETIC-ARTIFACTS.json"].content
    )
    manifest_identity = manifest_file.get("manifest_sha256")
    manifest_payload = {
        key: value
        for key, value in manifest_file.items()
        if key != "manifest_sha256"
    }
    if (
        not isinstance(manifest_identity, str)
        or _sha256_bytes(canonical_json_bytes(manifest_payload)) != manifest_identity
        or manifest_payload.get("artifact_map_sha256") != artifact_map_identity
        or completion
        != {
            "artifact_map_sha256": artifact_map_identity,
            "manifest_sha256": manifest_identity,
            "protocol": SYNTHETIC_PREPARATION_PROTOCOL_VERSION,
            "synthetic_only": True,
        }
    ):
        raise PreparationError("synthetic preparation control identities do not reconcile")
    membership_payload = _strict_json_value(
        snapshots["synthetic-artifacts/membership.json"].content,
        category="synthetic membership is malformed",
    )
    provenance_payload = _strict_json_value(
        snapshots["synthetic-artifacts/provenance.json"].content,
        category="synthetic provenance is malformed",
    )
    packed_arrays: dict[
        tuple[str, str],
        tuple[np.ndarray, np.ndarray, np.ndarray],
    ] = {}
    for condition in CONDITIONS:
        for split in ("train", "validation"):
            prefix = f"synthetic-artifacts/arrays/{condition}/{split}"
            inputs = _load_npy(
                snapshots[f"{prefix}/input_ids.npy"].content,
                dtype="uint16",
            )
            attention = _load_npy(
                snapshots[f"{prefix}/attention_mask.npy"].content,
                dtype="uint8",
                rows=inputs.shape[0],
            )
            token_types = _load_npy(
                snapshots[f"{prefix}/token_type_ids.npy"].content,
                dtype="uint8",
                rows=inputs.shape[0],
            )
            packed_arrays[(condition, split)] = (
                inputs,
                attention,
                token_types,
            )
    membership_rows = _reconcile_packed_row_token_content(
        serialized_membership=membership_payload,
        provenance=provenance_payload,
        packed_arrays=packed_arrays,
        protocol=SYNTHETIC_PREPARATION_PROTOCOL_VERSION,
        reconciliation_key=_SYNTHETIC_PRIVACY_RECONCILIATION_KEY,
    )
    baselines = {
        (source, split, row_id): binding
        for (condition, split, source, row_id), binding in membership_rows.items()
        if condition in {"EnglishMono", "SpanishMono"}
    }
    monocont = {
        (source, split, row_id): binding
        for (condition, split, source, row_id), binding in membership_rows.items()
        if condition == "MonoCont"
    }
    filler = {
        (source, split, row_id): binding
        for (condition, split, source, row_id), binding in membership_rows.items()
        if condition == "CsCont" and source in {"callhome_eng", "callhome_spa"}
    }
    if any(baselines.get(key) != binding for key, binding in monocont.items()):
        raise PreparationError(
            "synthetic MonoCont membership is not a monolingual-baseline subset"
        )
    if any(monocont.get(key) != binding for key, binding in filler.items()):
        raise PreparationError(
            "synthetic filler membership is not a MonoCont subset"
        )
    records: list[dict[str, object]] = []
    for condition in CONDITIONS:
        unmasked_inputs, base_attention, base_token_types = packed_arrays[
            (condition, "validation")
        ]
        for plan_name, seed in approved_validation_seed_plans():
            prefix = f"synthetic-artifacts/validation/{condition}/{plan_name}"
            masked = _load_npy(
                snapshots[f"{prefix}/masked_input_ids.npy"].content,
                dtype="uint16",
            )
            labels = _load_npy(
                snapshots[f"{prefix}/labels.npy"].content,
                dtype="int32",
                rows=masked.shape[0],
            )
            attention = _load_npy(
                snapshots[f"{prefix}/attention_mask.npy"].content,
                dtype="uint8",
                rows=masked.shape[0],
            )
            token_types = _load_npy(
                snapshots[f"{prefix}/token_type_ids.npy"].content,
                dtype="uint8",
                rows=masked.shape[0],
            )
            identities = _strict_json_value(
                snapshots[f"{prefix}/example_identities.json"].content,
                category="synthetic validation identities are malformed",
            )
            record_payload = _strict_json_value(
                snapshots[f"{prefix}/validation_mask_record.json"].content,
                category="synthetic validation record is malformed",
            )
            ordered_identities = (
                identities.get("ordered_example_identities")
                if isinstance(identities, dict)
                else None
            )
            if (
                not isinstance(identities, dict)
                or set(identities)
                != {"identity_protocol", "ordered_example_identities"}
                or identities["identity_protocol"]
                != "packing_sequence_identity_sha256_v1"
                or not isinstance(ordered_identities, list)
            ):
                raise PreparationError("synthetic validation identities are invalid")
            record = _validation_record_from_payload(record_payload)
            regenerated_masked, regenerated_labels, regenerated_record = (
                _regenerate_fixed_validation(
                condition=condition,
                seed=seed,
                    ordered_example_identities=tuple(ordered_identities),
                    unmasked_input_ids=unmasked_inputs,
                    attention_mask=base_attention,
                    token_type_ids=base_token_types,
                )
            )
            if not (
                np.array_equal(masked, regenerated_masked)
                and np.array_equal(labels, regenerated_labels)
                and np.array_equal(attention, base_attention)
                and np.array_equal(token_types, base_token_types)
                and record == regenerated_record
            ):
                raise PreparationError(
                    "synthetic validation material is not regenerated by the approved masker"
                )
            records.append({"plan_name": plan_name, **record_payload})
    if manifest_payload.get("validation_records") != records:
        raise PreparationError("synthetic validation manifest records do not reconcile")
    result = object.__new__(SyntheticPreparationSnapshot)
    object.__setattr__(result, "artifact_map_sha256", artifact_map_identity)
    object.__setattr__(result, "manifest_sha256", manifest_identity)
    object.__setattr__(result, "_root", root.expanduser().absolute())
    return result


def _required_artifact_names() -> frozenset[str]:
    names = {
        "audits/exposure.json",
        "membership.json",
        "provenance.json",
        "runtime.json",
    }
    for condition in CONDITIONS:
        for split in ("train", "validation"):
            prefix = f"arrays/{condition}/{split}"
            names.update(
                {
                    f"{prefix}/input_ids.npy",
                    f"{prefix}/attention_mask.npy",
                    f"{prefix}/token_type_ids.npy",
                }
            )
        for plan_name, _ in approved_validation_seed_plans():
            prefix = f"validation/{condition}/{plan_name}"
            names.update(
                {
                    f"{prefix}/masked_input_ids.npy",
                    f"{prefix}/labels.npy",
                    f"{prefix}/attention_mask.npy",
                    f"{prefix}/token_type_ids.npy",
                    f"{prefix}/example_identities.json",
                    f"{prefix}/validation_mask_record.json",
                }
            )
    return frozenset(names)


def _required_directory_names(files: Iterable[str]) -> frozenset[str]:
    directories: set[str] = set()
    for name in files:
        parent = Path(name).parent
        while parent != Path("."):
            directories.add(parent.as_posix())
            parent = parent.parent
    return frozenset(directories)


def _strict_json_value(raw: bytes, *, category: str) -> Any:
    value: Any = None
    failed = False
    original = raw
    try:
        value = json.loads(raw, object_pairs_hook=_unique_object)
    except BaseException:
        failed = True
    raw = b""
    if failed or canonical_json_bytes(value) != original:
        value = None
        original = b""
        _raise_fixed(category)
    original = b""
    return value


def _load_npy(raw: bytes, *, dtype: str, rows: int | None = None) -> np.ndarray:
    array: Any = None
    failed = False
    original = raw
    try:
        array = np.load(io.BytesIO(raw), allow_pickle=False)
    except BaseException:
        failed = True
    raw = b""
    if (
        failed
        or not isinstance(array, np.ndarray)
        or array.dtype != np.dtype(dtype)
        or array.ndim != 2
        or array.shape[1] != MAX_SEQUENCE_LENGTH
        or (rows is not None and array.shape[0] != rows)
        or array.shape[0] <= 0
        or _npy_bytes(array) != original
    ):
        array = None
        original = b""
        _raise_fixed("candidate array schema is invalid")
    original = b""
    return array


def _validation_record_from_payload(payload: Mapping[str, Any]) -> ValidationMaskRecord:
    if set(payload) != {
        "condition",
        "seed",
        "example_count",
        "policy_sha256",
        "checksum_sha256",
    }:
        raise PreparationError("candidate validation record schema is invalid")
    record = object.__new__(ValidationMaskRecord)
    for name in (
        "condition",
        "seed",
        "example_count",
        "policy_sha256",
        "checksum_sha256",
    ):
        object.__setattr__(record, name, payload[name])
    record._validate()
    return record


def _regenerate_fixed_validation(
    *,
    condition: str,
    seed: int,
    ordered_example_identities: Sequence[str],
    unmasked_input_ids: np.ndarray,
    attention_mask: np.ndarray,
    token_type_ids: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, ValidationMaskRecord]:
    """Rerun the one approved masker from serialized unmasked validation inputs."""
    if (
        condition not in CONDITIONS
        or type(seed) is not int
        or seed < 0
        or not ordered_example_identities
        or unmasked_input_ids.ndim != 2
        or unmasked_input_ids.shape != attention_mask.shape
        or unmasked_input_ids.shape != token_type_ids.shape
        or len(ordered_example_identities) != unmasked_input_ids.shape[0]
        or len(set(ordered_example_identities)) != len(ordered_example_identities)
        or any(
            not isinstance(identity, str) or not _SHA256_RE.fullmatch(identity)
            for identity in ordered_example_identities
        )
    ):
        raise PreparationError("candidate validation reconstruction metadata is invalid")
    sequences = tuple(
        PackedSequence(
            condition=condition,
            split="validation",
            input_ids=tuple(int(value) for value in unmasked_input_ids[index]),
            attention_mask=tuple(int(value) for value in attention_mask[index]),
            token_type_ids=tuple(int(value) for value in token_type_ids[index]),
            provenance=(),
            example_identity=identity,
        )
        for index, identity in enumerate(ordered_example_identities)
    )
    masked = tuple(
        mask_packed_sequence(sequence, seed=seed, mode="validation")
        for sequence in sequences
    )
    return (
        np.asarray([example.input_ids for example in masked], dtype=np.uint16),
        np.asarray([example.labels for example in masked], dtype=np.int32),
        build_validation_mask_record(sequences, seed=seed),
    )


def _validate_runtime_record(payload: Any, historical: Any) -> None:
    if not isinstance(payload, dict) or set(payload) != {
        "python",
        "platform",
        "dependencies",
        "historical_tokenizer_build",
        "encoding_runtime_native",
        "backend_correction_id",
        "frozen_tokenizer_checksum_record_sha256",
        "loader_protocol",
        "environment_controls",
    }:
        raise PreparationError("candidate runtime identity schema is invalid")
    if (
        payload["backend_correction_id"] != BACKEND_CORRECTION_ID
        or payload["frozen_tokenizer_checksum_record_sha256"]
        != APPROVED_TOKENIZER_CHECKSUM_RECORD_SHA256
        or payload["loader_protocol"] != TOKENIZER_LOADER_PROTOCOL
        or payload["historical_tokenizer_build"] != historical
        or payload["environment_controls"]
        != {"PYTHONHASHSEED": "1729", "TOKENIZERS_PARALLELISM": "false"}
    ):
        raise PreparationError("candidate runtime identity is not approved")
    dependencies = payload["dependencies"]
    expected_versions = {
        "numpy": "1.26.4",
        "tokenizers": "0.22.2",
        "torch": "2.11.0",
        "transformers": "5.6.2",
    }
    if not isinstance(dependencies, dict) or set(dependencies) != set(expected_versions):
        raise PreparationError("candidate runtime dependency identity is incomplete")
    for name, version in expected_versions.items():
        record = dependencies[name]
        if (
            not isinstance(record, dict)
            or set(record) != {"version", "normalized_record_sha256", "wheel_tags"}
            or record["version"] != version
            or not _SHA256_RE.fullmatch(record["normalized_record_sha256"])
            or not isinstance(record["wheel_tags"], list)
            or not all(isinstance(tag, str) and tag for tag in record["wheel_tags"])
        ):
            raise PreparationError("candidate runtime dependency identity is invalid")
    python = payload["python"]
    platform_record = payload["platform"]
    native = payload["encoding_runtime_native"]
    if (
        not isinstance(python, dict)
        or set(python) != {"version", "implementation", "abi", "executable_sha256"}
        or not _SHA256_RE.fullmatch(python["executable_sha256"])
        or not all(
            isinstance(python[name], str) and python[name]
            for name in ("version", "implementation")
        )
        or not isinstance(platform_record, dict)
        or set(platform_record) != {"os", "os_release", "architecture", "platform_tag"}
        or not all(isinstance(value, str) and value for value in platform_record.values())
        or not isinstance(native, dict)
        or set(native)
        != {"sha256", "abi", "platform", "historical_binary_equality_claimed"}
        or not _SHA256_RE.fullmatch(native["sha256"])
        or native["historical_binary_equality_claimed"] is not False
    ):
        raise PreparationError("candidate runtime native identity is invalid")


def _validate_historical_identity_record(
    historical: Any,
    anchor: InputPopulationAnchor,
) -> None:
    if not isinstance(historical, dict) or set(historical) != {
        "constituent_name",
        "constituent_sha256",
        "record",
    }:
        raise PreparationError("candidate historical tokenizer-build identity is invalid")
    name = historical["constituent_name"]
    digest = historical["constituent_sha256"]
    record = historical["record"]
    build = record.get("build") if isinstance(record, dict) else None
    if (
        not isinstance(name, str)
        or not name.endswith(".json")
        or name == "tokenizer.json"
        or not isinstance(digest, str)
        or not _SHA256_RE.fullmatch(digest)
        or not isinstance(record, dict)
        or set(record)
        != {
            "backend_correction_id",
            "build",
            "format_version",
            "patch",
            "tokenizers",
            "upstream_commit",
            "upstream_repository",
            "upstream_tag",
        }
        or record["backend_correction_id"] != BACKEND_CORRECTION_ID
        or record["format_version"] != 1
        or record["tokenizers"] != "0.22.2"
        or record["upstream_tag"] != "v0.22.2"
        or record["upstream_repository"]
        != "https://github.com/huggingface/tokenizers.git"
        or not isinstance(record["upstream_commit"], str)
        or not re.fullmatch(r"[0-9a-f]{40}", record["upstream_commit"])
        or not isinstance(record["patch"], str)
        or not record["patch"]
        or not isinstance(build, dict)
        or set(build) != {"cargo_locked", "maturin", "rust"}
        or build["cargo_locked"] is not True
        or not all(isinstance(build[key], str) and build[key] for key in ("maturin", "rust"))
        or dict(anchor.constituent_sha256).get(f"tokenizer:{name}") != digest
    ):
        raise PreparationError("candidate historical tokenizer-build identity is invalid")


def _validate_exposure_record(payload: Any) -> None:
    if not isinstance(payload, dict) or set(payload) != {
        "groups",
        "projected_train_non_padding_wordpieces",
        "prohibited_boundary_crossings",
        "split_leakage_count",
        "dropped_token_count",
        "truncated_token_count",
        "maximum_projected_exposure_difference_fraction",
        "exposure_tolerance_fraction",
    }:
        raise PreparationError("candidate exposure record schema is invalid")
    if (
        payload["exposure_tolerance_fraction"] != EXPOSURE_TOLERANCE_FRACTION
        or payload["prohibited_boundary_crossings"] != 0
        or payload["split_leakage_count"] != 0
        or payload["dropped_token_count"] != 0
        or payload["truncated_token_count"] != 0
        or not isinstance(payload["maximum_projected_exposure_difference_fraction"], (int, float))
        or payload["maximum_projected_exposure_difference_fraction"]
        > EXPOSURE_TOLERANCE_FRACTION
    ):
        raise PreparationError("candidate exposure result did not pass")
    projected = payload["projected_train_non_padding_wordpieces"]
    if (
        not isinstance(projected, dict)
        or set(projected) != set(CONDITIONS)
        or any(
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or value <= 0
            for value in projected.values()
        )
    ):
        raise PreparationError("candidate projected exposure population is invalid")
    groups = payload["groups"]
    expected_groups = {
        (condition, split)
        for condition in CONDITIONS
        for split in ("train", "validation")
    }
    if (
        not isinstance(groups, list)
        or {
            (group.get("condition"), group.get("split"))
            for group in groups
            if isinstance(group, dict)
        }
        != expected_groups
    ):
        raise PreparationError("candidate exposure groups are incomplete")


def _expected_aggregate_rows(condition: str, split: str) -> tuple[int, int]:
    if condition == "MonoCont":
        english = _aggregate_for_block((condition, split, "english"))
        spanish = _aggregate_for_block((condition, split, "spanish"))
        return english[0] + spanish[0], english[1] + spanish[1]
    return _aggregate_for_block((condition, split, None))


@dataclass(frozen=True, init=False, slots=True)
class CandidateValidationSnapshot:
    condition: str
    plan_name: str
    seed: int
    record: ValidationMaskRecord
    artifact_identities: tuple[tuple[str, str], ...]

    def __new__(cls) -> CandidateValidationSnapshot:
        raise PreparationError("validation snapshots must be candidate-loader-derived")


@dataclass(frozen=True, init=False, slots=True)
class PreparationSnapshot:
    """Immutable, internally verified snapshot that remains scientifically unapproved."""

    status: str
    protocol_version: str
    candidate_checksum_record_sha256: str
    preparation_manifest_sha256: str
    _candidate_root: Path = field(repr=False)
    _reconciliation_key_path: Path = field(repr=False)
    _tree_identity_sha256: str = field(repr=False)
    _validation_snapshots: tuple[CandidateValidationSnapshot, ...] = field(repr=False)

    def __new__(cls) -> PreparationSnapshot:
        raise PreparationError("preparation snapshots must be candidate-loader-derived")


def verify_preparation_snapshot(snapshot: PreparationSnapshot) -> None:
    """Revalidate an exact factory product without dispatch through caller methods."""
    if type(snapshot) is not PreparationSnapshot:
        raise PreparationError("run construction requires an exact preparation snapshot")
    loaded = load_preparation_candidate(
        snapshot._candidate_root,
        reconciliation_key_path=snapshot._reconciliation_key_path,
    )
    values = (
        snapshot.status,
        snapshot.protocol_version,
        snapshot.candidate_checksum_record_sha256,
        snapshot.preparation_manifest_sha256,
        snapshot._reconciliation_key_path,
        snapshot._tree_identity_sha256,
        snapshot._validation_snapshots,
    )
    expected = (
        loaded.status,
        loaded.protocol_version,
        loaded.candidate_checksum_record_sha256,
        loaded.preparation_manifest_sha256,
        loaded._reconciliation_key_path,
        loaded._tree_identity_sha256,
        loaded._validation_snapshots,
    )
    if values != expected:
        raise PreparationError("preparation candidate snapshot changed")


def candidate_validation_for(
    snapshot: PreparationSnapshot,
    condition: str,
    seed: int,
) -> CandidateValidationSnapshot:
    if type(snapshot) is not PreparationSnapshot:
        raise PreparationError("validation requires an exact preparation snapshot")
    matches = tuple(
        item
        for item in snapshot._validation_snapshots
        if item.condition == condition and item.seed == seed
    )
    if len(matches) != 1:
        raise PreparationError("candidate validation seed plan is unavailable")
    return matches[0]


def _load_preparation_candidate(
    root: Path,
    *,
    reconciliation_key: bytes,
    root_descriptor: int | None = None,
) -> PreparationSnapshot:
    _require_hmac_key(reconciliation_key)
    provided_descriptor = root_descriptor
    root_descriptor = (
        os.dup(provided_descriptor)
        if provided_descriptor is not None
        else _open_directory_chain(root)
    )
    try:
        _verify_owner_mode(
            os.fstat(root_descriptor),
            expected_mode=PRIVATE_DIRECTORY_MODE,
            kind="directory",
        )
        files, directories = _walk_private_tree(root_descriptor)
        required_artifacts = _required_artifact_names()
        required_files = required_artifacts | _CONTROL_FILES
        if set(files) != set(required_files):
            raise PreparationError(
                "candidate artifact inventory is incomplete or contains extras"
            )
        if set(directories) != set(_required_directory_names(required_files)):
            raise PreparationError("candidate directory inventory is not canonical")
        snapshots = {
            name: _snapshot_relative_regular_file(root_descriptor, name)
            for name in sorted(required_files)
        }
    finally:
        os.close(root_descriptor)

    checksum_payload = _strict_json_value(
        snapshots["checksums.json"].content,
        category="candidate checksum record is malformed",
    )
    if (
        not isinstance(checksum_payload, dict)
        or set(checksum_payload)
        != {
            "algorithm",
            "artifacts",
            "completion_state",
            "file_inventory",
            "protocol_version",
            "schema_version",
            "status",
        }
        or checksum_payload["algorithm"] != "sha256"
        or checksum_payload["schema_version"] != 1
        or checksum_payload["protocol_version"] != PREPARATION_PROTOCOL_VERSION
        or checksum_payload["status"] != "candidate_unapproved"
        or checksum_payload["completion_state"]
        != {"complete": True, "status": "candidate_unapproved"}
        or checksum_payload["file_inventory"] != sorted(required_files)
        or not isinstance(checksum_payload["artifacts"], dict)
        or not checksum_payload["artifacts"]
    ):
        raise PreparationError("candidate checksum record schema is invalid")
    artifacts = checksum_payload["artifacts"]
    normalized: set[str] = set()
    for name, digest in artifacts.items():
        canonical = _safe_relative_name(name)
        if (
            canonical in normalized
            or not isinstance(digest, str)
            or not _SHA256_RE.fullmatch(digest)
        ):
            raise PreparationError(
                "candidate checksum record contains an invalid artifact"
            )
        normalized.add(canonical)
    checksummed_files = required_artifacts | {"PREPARATION_MANIFEST.json"}
    if set(artifacts) != set(checksummed_files):
        raise PreparationError("candidate checksum inventory is not exact")
    for name, digest in artifacts.items():
        if _sha256_bytes(snapshots[name].content) != digest:
            raise PreparationError("candidate artifact checksum verification failed")
    checksum_identity = _sha256_bytes(snapshots["checksums.json"].content)

    manifest_with_identity = _strict_json_value(
        snapshots["PREPARATION_MANIFEST.json"].content,
        category="candidate preparation manifest is malformed",
    )
    if not isinstance(manifest_with_identity, dict):
        raise PreparationError("candidate preparation manifest schema is invalid")
    manifest_identity = manifest_with_identity.get("preparation_manifest_identity_sha256")
    manifest = {
        key: value
        for key, value in manifest_with_identity.items()
        if key != "preparation_manifest_identity_sha256"
    }
    expected_manifest_keys = {
        "protocol_version",
        "status",
        "internal_tracker_version",
        "frozen_checksum_record_identities",
        "tokenizer_loader_protocol",
        "tokenizer_synthetic_parity_passed",
        "tokenizer_synthetic_parity_sha256",
        "tokenizer_artifact_sha256",
        "tokenizer_backend_configuration_sha256",
        "historical_tokenizer_build_identity",
        "input_population_anchor",
        "subset_reconciliation",
        "test_seal",
        "conditions",
        "included_splits",
        "aggregates",
        "exposure",
        "fixed_validation_seed_plans",
        "derived_validation_records",
        "serialization",
        "runtime_identity",
    }
    if (
        set(manifest) != expected_manifest_keys
        or not isinstance(manifest_identity, str)
        or not _SHA256_RE.fullmatch(manifest_identity)
        or _sha256_bytes(canonical_json_bytes(manifest)) != manifest_identity
        or manifest["protocol_version"] != PREPARATION_PROTOCOL_VERSION
        or manifest["status"] != "candidate_unapproved"
        or manifest["internal_tracker_version"] != INTERNAL_TRACKER_VERSION
        or manifest["frozen_checksum_record_identities"]
        != {
            "CsCont": APPROVED_CSCONT_CHECKSUM_RECORD_SHA256,
            "CALLHOME_pilot_conditions": APPROVED_CALLHOME_CHECKSUM_RECORD_SHA256,
            "tokenizer": APPROVED_TOKENIZER_CHECKSUM_RECORD_SHA256,
        }
        or manifest["tokenizer_loader_protocol"] != TOKENIZER_LOADER_PROTOCOL
        or manifest["tokenizer_synthetic_parity_passed"] is not True
        or not all(
            _SHA256_RE.fullmatch(manifest[name])
            for name in (
                "tokenizer_synthetic_parity_sha256",
                "tokenizer_artifact_sha256",
                "tokenizer_backend_configuration_sha256",
            )
        )
        or manifest["subset_reconciliation"]
        != {
            "monocont_english_subset_of_englishmono": True,
            "monocont_spanish_subset_of_spanishmono": True,
            "cscont_callhome_filler_subset_of_monocont": True,
        }
        or manifest["test_seal"] != {"passed": True, "test_rows_emitted": 0}
        or manifest["conditions"] != list(CONDITIONS)
        or manifest["included_splits"] != ["train", "validation"]
        or manifest["serialization"] != dict(_SERIALIZATION_SCHEMA)
    ):
        raise PreparationError("candidate preparation manifest semantics are invalid")

    anchor_payload = manifest["input_population_anchor"]
    if not isinstance(anchor_payload, dict) or set(anchor_payload) != {
        "identity_sha256",
        "checksum_record_identities",
        "constituent_sha256",
        "input_line_counts",
        "authorized_line_counts",
        "sealed_test_line_counts",
    }:
        raise PreparationError("candidate input population anchor is invalid")
    anchor = object.__new__(InputPopulationAnchor)
    for name in (
        "checksum_record_identities",
        "constituent_sha256",
        "input_line_counts",
        "authorized_line_counts",
        "sealed_test_line_counts",
    ):
        value = anchor_payload[name]
        if not isinstance(value, dict):
            raise PreparationError("candidate input population anchor is invalid")
        object.__setattr__(anchor, name, tuple(sorted(value.items())))
    object.__setattr__(anchor, "identity_sha256", anchor_payload["identity_sha256"])
    anchor._validate()
    expected_authorized_counts = {
        "callhome:english_mono_rows.jsonl": (
            _aggregate_for_block(("EnglishMono", "train", None))[0]
            + _aggregate_for_block(("EnglishMono", "validation", None))[0]
        ),
        "callhome:spanish_mono_rows.jsonl": (
            _aggregate_for_block(("SpanishMono", "train", None))[0]
            + _aggregate_for_block(("SpanishMono", "validation", None))[0]
        ),
        "callhome:monocont_english_rows.jsonl": (
            _aggregate_for_block(("MonoCont", "train", "english"))[0]
            + _aggregate_for_block(("MonoCont", "validation", "english"))[0]
        ),
        "callhome:monocont_spanish_rows.jsonl": (
            _aggregate_for_block(("MonoCont", "train", "spanish"))[0]
            + _aggregate_for_block(("MonoCont", "validation", "spanish"))[0]
        ),
        "cscont:train_rows.jsonl": _aggregate_for_block(("CsCont", "train", None))[0],
        "cscont:validation_rows.jsonl": _aggregate_for_block(
            ("CsCont", "validation", None)
        )[0],
    }
    input_counts = dict(anchor.input_line_counts)
    authorized_counts = dict(anchor.authorized_line_counts)
    test_counts = dict(anchor.sealed_test_line_counts)
    if (
        authorized_counts != expected_authorized_counts
        or set(input_counts) != set(expected_authorized_counts)
        or any(type(value) is not int or value <= 0 for value in input_counts.values())
        or any(
            input_counts[role]
            != authorized_counts[role]
            + (test_counts.get(role, 0) if role.startswith("callhome:") else 0)
            for role in input_counts
        )
        or any(
            role not in input_counts
            or not role.startswith("callhome:")
            or type(value) is not int
            or value < 0
            for role, value in test_counts.items()
        )
    ):
        raise PreparationError("candidate input and authorized populations do not reconcile")
    _validate_historical_identity_record(
        manifest["historical_tokenizer_build_identity"],
        anchor,
    )
    if (
        dict(anchor.constituent_sha256).get("tokenizer:tokenizer.json")
        != manifest["tokenizer_artifact_sha256"]
    ):
        raise PreparationError("candidate tokenizer artifact is not input-anchored")

    plans = [
        {"name": name, "validation_mask_seed": seed}
        for name, seed in approved_validation_seed_plans()
    ]
    if manifest["fixed_validation_seed_plans"] != plans:
        raise PreparationError("candidate validation seed plans are not exact")
    aggregates = manifest["aggregates"]
    if not isinstance(aggregates, dict) or set(aggregates) != set(CONDITIONS):
        raise PreparationError("candidate aggregate population is incomplete")

    validation_records: list[CandidateValidationSnapshot] = []
    derived_records: list[dict[str, object]] = []
    packed_nonpadding: dict[tuple[str, str], int] = {}
    packed_arrays: dict[
        tuple[str, str],
        tuple[np.ndarray, np.ndarray, np.ndarray],
    ] = {}
    for condition in CONDITIONS:
        condition_aggregates = aggregates[condition]
        if not isinstance(condition_aggregates, dict) or set(condition_aggregates) != {
            "train",
            "validation",
        }:
            raise PreparationError("candidate aggregate schema is invalid")
        base_arrays: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
        for split in ("train", "validation"):
            aggregate = condition_aggregates[split]
            if not isinstance(aggregate, dict) or set(aggregate) != {
                "rows",
                "lexical_tokens",
                "wordpieces",
                "sequences",
                "padding",
            }:
                raise PreparationError("candidate aggregate schema is invalid")
            expected_rows, expected_lexical = _expected_aggregate_rows(condition, split)
            if (
                aggregate["rows"] != expected_rows
                or aggregate["lexical_tokens"] != expected_lexical
                or any(
                    type(aggregate[name]) is not int or aggregate[name] <= 0
                    for name in ("wordpieces", "sequences")
                )
                or type(aggregate["padding"]) is not int
                or aggregate["padding"] < 0
            ):
                raise PreparationError("candidate aggregate controls did not pass")
            prefix = f"arrays/{condition}/{split}"
            inputs = _load_npy(
                snapshots[f"{prefix}/input_ids.npy"].content,
                dtype="uint16",
                rows=aggregate["sequences"],
            )
            attention = _load_npy(
                snapshots[f"{prefix}/attention_mask.npy"].content,
                dtype="uint8",
                rows=aggregate["sequences"],
            )
            token_types = _load_npy(
                snapshots[f"{prefix}/token_type_ids.npy"].content,
                dtype="uint8",
                rows=aggregate["sequences"],
            )
            if (
                inputs.shape != attention.shape
                or inputs.shape != token_types.shape
                or np.any(inputs >= VOCAB_SIZE)
                or not np.isin(attention, (0, 1)).all()
                or not np.isin(token_types, (0, 1)).all()
                or int(attention.size - attention.sum()) != aggregate["padding"]
                or np.any(inputs[attention == 0] != SPECIAL_TOKEN_IDS["[PAD]"])
            ):
                raise PreparationError("candidate packed arrays do not reconcile")
            packed_nonpadding[(condition, split)] = int(attention.sum())
            base_arrays[split] = (inputs, attention, token_types)
            packed_arrays[(condition, split)] = (
                inputs,
                attention,
                token_types,
            )

        validation_inputs, validation_attention, validation_types = base_arrays["validation"]
        for plan_name, seed in approved_validation_seed_plans():
            prefix = f"validation/{condition}/{plan_name}"
            masked = _load_npy(
                snapshots[f"{prefix}/masked_input_ids.npy"].content,
                dtype="uint16",
                rows=validation_inputs.shape[0],
            )
            labels = _load_npy(
                snapshots[f"{prefix}/labels.npy"].content,
                dtype="int32",
                rows=validation_inputs.shape[0],
            )
            attention = _load_npy(
                snapshots[f"{prefix}/attention_mask.npy"].content,
                dtype="uint8",
                rows=validation_inputs.shape[0],
            )
            token_types = _load_npy(
                snapshots[f"{prefix}/token_type_ids.npy"].content,
                dtype="uint8",
                rows=validation_inputs.shape[0],
            )
            identities = _strict_json_value(
                snapshots[f"{prefix}/example_identities.json"].content,
                category="candidate validation identities are malformed",
            )
            record_payload = _strict_json_value(
                snapshots[f"{prefix}/validation_mask_record.json"].content,
                category="candidate validation record is malformed",
            )
            record = _validation_record_from_payload(record_payload)
            ordered_identities = (
                identities.get("ordered_example_identities")
                if isinstance(identities, dict)
                else None
            )
            if (
                masked.shape != validation_inputs.shape
                or labels.shape != validation_inputs.shape
                or not np.array_equal(attention, validation_attention)
                or not np.array_equal(token_types, validation_types)
                or np.any(masked >= VOCAB_SIZE)
                or np.any((labels != -100) & ((labels < 0) | (labels >= VOCAB_SIZE)))
                or not isinstance(identities, dict)
                or set(identities)
                != {"identity_protocol", "ordered_example_identities"}
                or identities["identity_protocol"]
                != "packing_sequence_identity_sha256_v1"
                or not isinstance(ordered_identities, list)
                or len(ordered_identities) != validation_inputs.shape[0]
                or len(set(ordered_identities)) != len(ordered_identities)
                or not all(
                    isinstance(value, str) and _SHA256_RE.fullmatch(value)
                    for value in ordered_identities
                )
                or record.condition != condition
                or record.seed != seed
                or record.example_count != validation_inputs.shape[0]
            ):
                raise PreparationError("candidate fixed validation material does not reconcile")
            assert isinstance(ordered_identities, list)
            regenerated_masked, regenerated_labels, regenerated_record = (
                _regenerate_fixed_validation(
                    condition=condition,
                    seed=seed,
                    ordered_example_identities=tuple(ordered_identities),
                    unmasked_input_ids=validation_inputs,
                    attention_mask=validation_attention,
                    token_type_ids=validation_types,
                )
            )
            if not (
                np.array_equal(masked, regenerated_masked)
                and np.array_equal(labels, regenerated_labels)
                and record == regenerated_record
            ):
                raise PreparationError(
                    "candidate validation material was not regenerated by the approved masker"
                )
            artifact_names = (
                f"{prefix}/masked_input_ids.npy",
                f"{prefix}/labels.npy",
                f"{prefix}/attention_mask.npy",
                f"{prefix}/token_type_ids.npy",
                f"{prefix}/example_identities.json",
                f"{prefix}/validation_mask_record.json",
            )
            binding = object.__new__(CandidateValidationSnapshot)
            object.__setattr__(binding, "condition", condition)
            object.__setattr__(binding, "plan_name", plan_name)
            object.__setattr__(binding, "seed", seed)
            object.__setattr__(binding, "record", record)
            object.__setattr__(
                binding,
                "artifact_identities",
                tuple((name, artifacts[name]) for name in artifact_names),
            )
            validation_records.append(binding)
            derived_records.append({"plan_name": plan_name, **record_payload})

    if manifest["derived_validation_records"] != derived_records:
        raise PreparationError("candidate validation records do not match their artifacts")
    exposure = _strict_json_value(
        snapshots["audits/exposure.json"].content,
        category="candidate exposure record is malformed",
    )
    _validate_exposure_record(exposure)
    if manifest["exposure"] != exposure:
        raise PreparationError("candidate exposure manifest binding failed")
    groups = {
        (group["condition"], group["split"]): group for group in exposure["groups"]
    }
    from cslm.modeling.contracts import APPROVED_BUDGET

    projected_expected: dict[str, float] = {}
    for condition in CONDITIONS:
        for split in ("train", "validation"):
            aggregate = aggregates[condition][split]
            prefix = f"arrays/{condition}/{split}"
            input_array = _load_npy(
                snapshots[f"{prefix}/input_ids.npy"].content,
                dtype="uint16",
                rows=aggregate["sequences"],
            )
            attention_array = _load_npy(
                snapshots[f"{prefix}/attention_mask.npy"].content,
                dtype="uint8",
                rows=aggregate["sequences"],
            )
            eligible = int(
                (
                    (attention_array == 1)
                    & ~np.isin(input_array, tuple(SPECIAL_TOKEN_IDS.values()))
                ).sum()
            )
            group = groups[(condition, split)]
            expected_group = {
                "condition": condition,
                "split": split,
                "source_lexical_tokens": aggregate["lexical_tokens"],
                "non_padding_wordpieces": int(attention_array.sum()),
                "sequence_count": aggregate["sequences"],
                "padding_count": aggregate["padding"],
                "padding_fraction": aggregate["padding"]
                / (aggregate["sequences"] * MAX_SEQUENCE_LENGTH),
                "expected_masked_target_count": eligible * 0.15,
            }
            if group != expected_group:
                raise PreparationError("candidate exposure groups do not reconcile arrays")
        train = aggregates[condition]["train"]
        projected_expected[condition] = (
            packed_nonpadding[(condition, "train")] / train["sequences"]
        ) * APPROVED_BUDGET.projected_sequence_exposures
    if exposure["projected_train_non_padding_wordpieces"] != projected_expected:
        raise PreparationError("candidate projected exposure does not match packed arrays")
    runtime = _strict_json_value(
        snapshots["runtime.json"].content,
        category="candidate runtime record is malformed",
    )
    _validate_runtime_record(runtime, manifest["historical_tokenizer_build_identity"])
    if manifest["runtime_identity"] != runtime:
        raise PreparationError("candidate runtime manifest binding failed")
    provenance = _strict_json_value(
        snapshots["provenance.json"].content,
        category="candidate provenance record is malformed",
    )
    if not isinstance(provenance, list) or not provenance:
        raise PreparationError("candidate serialized population is empty")
    serialized_examples = sum(
        aggregates[condition][split]["sequences"]
        for condition in CONDITIONS
        for split in ("train", "validation")
    )
    if len(provenance) != serialized_examples:
        raise PreparationError("candidate serialized population does not reconcile")
    provenance_counts: Counter[tuple[str, str]] = Counter()
    provenance_wordpieces: Counter[tuple[str, str]] = Counter()
    ranges_by_row: dict[
        tuple[str, str, str, str],
        list[tuple[int, int]],
    ] = {}
    filler_rows: set[tuple[str, str, str]] = set()
    monocont_rows: set[tuple[str, str, str]] = set()
    for example in provenance:
        if (
            not isinstance(example, dict)
            or set(example) != {"condition", "split", "example_pseudonym", "ranges"}
            or example["condition"] not in CONDITIONS
            or example["split"] not in {"train", "validation"}
            or not isinstance(example["example_pseudonym"], str)
            or not _SHA256_RE.fullmatch(example["example_pseudonym"])
            or not isinstance(example["ranges"], list)
            or not example["ranges"]
        ):
            raise PreparationError("candidate provenance schema is invalid")
        provenance_counts[(example["condition"], example["split"])] += 1
        packed_ranges: list[tuple[int, int]] = []
        for item in example["ranges"]:
            if (
                not isinstance(item, dict)
                or set(item)
                != {
                    "condition",
                    "split",
                    "source_role",
                    "component_role",
                    "language_shard",
                    "row_order",
                    "source_row_token_count",
                    "packed_token_range",
                    "source_token_range",
                    "row_pseudonym",
                    "document_pseudonym",
                    "conversation_pseudonym",
                    "span_pseudonym",
                }
                or item["condition"] != example["condition"]
                or item["split"] != example["split"]
                or not isinstance(item["source_role"], str)
                or not isinstance(item["component_role"], str)
                or type(item["row_order"]) is not int
                or item["row_order"] < 0
                or type(item["source_row_token_count"]) is not int
                or item["source_row_token_count"] <= 0
                or (
                    item["condition"],
                    item["source_role"],
                    item["component_role"],
                    item["language_shard"],
                )
                not in {
                    (
                        "EnglishMono",
                        "callhome_eng",
                        "callhome_monolingual",
                        None,
                    ),
                    (
                        "SpanishMono",
                        "callhome_spa",
                        "callhome_monolingual",
                        None,
                    ),
                    (
                        "MonoCont",
                        "callhome_eng",
                        "callhome_monolingual",
                        "english",
                    ),
                    (
                        "MonoCont",
                        "callhome_spa",
                        "callhome_monolingual",
                        "spanish",
                    ),
                    (
                        "CsCont",
                        "callhome_eng",
                        "callhome_monolingual_filler",
                        None,
                    ),
                    (
                        "CsCont",
                        "callhome_spa",
                        "callhome_monolingual_filler",
                        None,
                    ),
                    (
                        "CsCont",
                        "bangor_cgwords",
                        "bangor_natural_span",
                        None,
                    ),
                }
                or any(
                    not isinstance(value, str)
                    or not _SHA256_RE.fullmatch(value)
                    for value in (
                        item["row_pseudonym"],
                        item["document_pseudonym"],
                        item["conversation_pseudonym"],
                    )
                )
                or any(
                    value is not None
                    and (not isinstance(value, str) or not _SHA256_RE.fullmatch(value))
                    for value in (
                        item["row_pseudonym"],
                        item["document_pseudonym"],
                        item["conversation_pseudonym"],
                        item["span_pseudonym"],
                    )
                )
                or not all(
                    isinstance(item[name], list)
                    and len(item[name]) == 2
                    and all(type(value) is int and value >= 0 for value in item[name])
                    and item[name][1] >= item[name][0]
                    for name in ("packed_token_range", "source_token_range")
                )
                or (
                    item["component_role"] == "bangor_natural_span"
                    and item["span_pseudonym"] is None
                )
                or (
                    item["component_role"] != "bangor_natural_span"
                    and item["span_pseudonym"] is not None
                )
            ):
                raise PreparationError("candidate provenance schema is invalid")
            provenance_wordpieces[(example["condition"], example["split"])] += (
                item["source_token_range"][1] - item["source_token_range"][0]
            )
            row_key = (
                example["condition"],
                example["split"],
                item["source_role"],
                item["row_pseudonym"],
            )
            ranges_by_row.setdefault(row_key, []).append(
                tuple(item["source_token_range"])
            )
            packed_ranges.append(tuple(item["packed_token_range"]))
            reuse_key = (
                example["split"],
                item["source_role"],
                item["row_pseudonym"],
            )
            if item["condition"] == "MonoCont":
                monocont_rows.add(reuse_key)
            elif item["component_role"] == "callhome_monolingual_filler":
                filler_rows.add(reuse_key)
        for earlier, later in zip(
            sorted(packed_ranges),
            sorted(packed_ranges)[1:],
        ):
            if earlier[1] > later[0]:
                raise PreparationError("candidate packed provenance ranges overlap")
    if any(
        provenance_counts[(condition, split)]
        != aggregates[condition][split]["sequences"]
        or provenance_wordpieces[(condition, split)]
        != aggregates[condition][split]["wordpieces"]
        for condition in CONDITIONS
        for split in ("train", "validation")
    ):
        raise PreparationError("candidate provenance population does not reconcile")
    if any(
        ranges[0][0] != 0
        or any(
            earlier[1] != later[0]
            for earlier, later in zip(ranges, ranges[1:])
        )
        for ranges in (sorted(material) for material in ranges_by_row.values())
    ):
        raise PreparationError("candidate source provenance ranges are incomplete")
    if any(
        len(
            {
                key
                for key in ranges_by_row
                if key[0] == condition and key[1] == split
            }
        )
        != aggregates[condition][split]["rows"]
        for condition in CONDITIONS
        for split in ("train", "validation")
    ):
        raise PreparationError("candidate serialized rows do not reconcile")
    if not filler_rows <= monocont_rows:
        raise PreparationError("candidate CALLHOME filler reuse is not anchored")
    serialized_membership = _strict_json_value(
        snapshots["membership.json"].content,
        category="candidate serialized membership is malformed",
    )
    if (
        not isinstance(serialized_membership, list)
        or len(serialized_membership)
        != sum(
            aggregates[condition][split]["rows"]
            for condition in CONDITIONS
            for split in ("train", "validation")
        )
    ):
        raise PreparationError("candidate serialized membership population is incomplete")
    membership_rows = _reconcile_packed_row_token_content(
        serialized_membership=serialized_membership,
        provenance=provenance,
        packed_arrays=packed_arrays,
        protocol=PREPARATION_PROTOCOL_VERSION,
        reconciliation_key=reconciliation_key,
    )
    if set(membership_rows) != set(ranges_by_row):
        raise PreparationError(
            "candidate serialized membership and packed provenance do not reconcile"
        )
    baselines = {
        (source, split, row_id): binding
        for (condition, split, source, row_id), binding in membership_rows.items()
        if condition in {"EnglishMono", "SpanishMono"}
    }
    monocont = {
        (source, split, row_id): binding
        for (condition, split, source, row_id), binding in membership_rows.items()
        if condition == "MonoCont"
    }
    filler = {
        (source, split, row_id): binding
        for (condition, split, source, row_id), binding in membership_rows.items()
        if condition == "CsCont" and source in {"callhome_eng", "callhome_spa"}
    }
    if any(baselines.get(key) != binding for key, binding in monocont.items()):
        raise PreparationError(
            "candidate MonoCont membership is not a monolingual-baseline subset"
        )
    if any(monocont.get(key) != binding for key, binding in filler.items()):
        raise PreparationError(
            "candidate CALLHOME filler membership is not a MonoCont subset"
        )

    completion = _strict_json_value(
        snapshots["CANDIDATE_COMPLETE.json"].content,
        category="candidate completion record is malformed",
    )
    if completion != {
        "candidate_checksum_record_sha256": checksum_identity,
        "complete": True,
        "protocol_version": PREPARATION_PROTOCOL_VERSION,
        "status": "candidate_unapproved",
    }:
        raise PreparationError("candidate completion state is invalid")

    final_root_descriptor = (
        os.dup(provided_descriptor)
        if provided_descriptor is not None
        else _open_directory_chain(root)
    )
    try:
        final_files, final_directories = _walk_private_tree(final_root_descriptor)
        if set(final_files) != set(required_files) or set(final_directories) != set(
            _required_directory_names(required_files)
        ):
            raise PreparationError("candidate artifact tree changed during validation")
        for name, snapshot in snapshots.items():
            repeated_snapshot = _snapshot_relative_regular_file(
                final_root_descriptor,
                name,
            )
            if (
                repeated_snapshot.device,
                repeated_snapshot.inode,
                repeated_snapshot.size,
                repeated_snapshot.mode,
                repeated_snapshot.uid,
                _sha256_bytes(repeated_snapshot.content),
            ) != (
                snapshot.device,
                snapshot.inode,
                snapshot.size,
                snapshot.mode,
                snapshot.uid,
                _sha256_bytes(snapshot.content),
            ):
                raise PreparationError(
                    "candidate artifact changed during stable snapshot validation"
                )
    finally:
        os.close(final_root_descriptor)

    tree_payload = [
        [
            name,
            _sha256_bytes(snapshot.content),
            snapshot.device,
            snapshot.inode,
            snapshot.size,
            snapshot.mode,
            snapshot.uid,
        ]
        for name, snapshot in sorted(snapshots.items())
    ]
    result = object.__new__(PreparationSnapshot)
    object.__setattr__(result, "status", "candidate_unapproved")
    object.__setattr__(result, "protocol_version", PREPARATION_PROTOCOL_VERSION)
    object.__setattr__(
        result,
        "candidate_checksum_record_sha256",
        checksum_identity,
    )
    object.__setattr__(result, "preparation_manifest_sha256", manifest_identity)
    object.__setattr__(result, "_candidate_root", root.expanduser().absolute())
    object.__setattr__(result, "_reconciliation_key_path", Path())
    object.__setattr__(
        result,
        "_tree_identity_sha256",
        _sha256_bytes(canonical_json_bytes(tree_payload)),
    )
    object.__setattr__(result, "_validation_snapshots", tuple(validation_records))
    return result


def load_preparation_candidate(
    root: Path,
    *,
    reconciliation_key_path: Path,
) -> PreparationSnapshot:
    """Reconcile a candidate with its separate privacy pseudonymization key."""
    result: PreparationSnapshot | None = None
    reconciliation_key = b""
    failed = False
    try:
        reconciliation_key = load_hmac_key(
            reconciliation_key_path,
            forbidden_roots=(root,),
        )
        result = _load_preparation_candidate(
            root,
            reconciliation_key=reconciliation_key,
        )
    except BaseException:
        failed = True
    candidate_root = root.expanduser().absolute()
    key_path = reconciliation_key_path.expanduser().absolute()
    reconciliation_key = b""
    root = Path()
    reconciliation_key_path = Path()
    if failed or result is None:
        candidate_root = Path()
        key_path = Path()
        _raise_fixed("preparation candidate failed verification")
    object.__setattr__(result, "_candidate_root", candidate_root)
    object.__setattr__(result, "_reconciliation_key_path", key_path)
    return result
