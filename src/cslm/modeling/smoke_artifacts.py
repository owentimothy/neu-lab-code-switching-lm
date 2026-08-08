"""Private, no-overwrite artifact transactions for a future Tiny smoke run."""

from __future__ import annotations

import ctypes
import errno
import hashlib
import json
import os
import re
import secrets
import stat
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import FunctionType, MappingProxyType, ModuleType
from typing import Callable, Mapping

PRIVATE_DIRECTORY_MODE = 0o700
PRIVATE_FILE_MODE = 0o600
_COMPONENT_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}\Z")
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_CHECKPOINT_UPDATES = frozenset({0, 250, 500, 750, 1_000})
_CONDITIONS = ("EnglishMono", "SpanishMono", "MonoCont", "CsCont")
_BASELINE_TRACKER_SHA256 = (
    "46d24c4d0442cb5c871db01e71529258bae38bb0c09127fe06d794e4d5596e12"
)
_BASELINE_TRACKER_SIZE = 65_437
_BASELINE_TRACKER_VERSION = "5.6"
_BASELINE_TRACKER_DATE = "August 3, 2026"
_TRACKER_VERSION_RE = re.compile(r"[1-9][0-9]*\.[0-9]+\Z")
_TRACKER_DATE_RE = re.compile(
    r"(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December) [1-9][0-9]?, [0-9]{4}\Z"
)

SMOKE_CHECKPOINT_WRITE_FAILURE = "SMOKE_CHECKPOINT_WRITE_FAILURE"
SMOKE_ARTIFACT_COMMIT_INDETERMINATE = "SMOKE_ARTIFACT_COMMIT_INDETERMINATE"


class SmokeArtifactError(RuntimeError):
    """A privacy-safe private-artifact operation failed."""

    def __init__(self, code: str) -> None:
        if code not in {
            SMOKE_CHECKPOINT_WRITE_FAILURE,
            SMOKE_ARTIFACT_COMMIT_INDETERMINATE,
        }:
            code = SMOKE_CHECKPOINT_WRITE_FAILURE
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, init=False, slots=True)
class ArtifactCommitResult:
    """Path-free checksum evidence for one committed private tree."""

    namespace: str
    inventory_sha256: str
    completion_sha256: str
    file_count: int

    def __new__(cls) -> ArtifactCommitResult:
        raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE)


@dataclass(frozen=True, init=False, slots=True)
class PrivateRunArtifactWriter:
    """Pinned whole-run staging authority; paths are deliberately private."""

    run_name: str
    _parent: Path = field(repr=False)
    _stage_name: str = field(repr=False)
    _parent_descriptor: int = field(repr=False, compare=False)
    _stage_descriptor: int = field(repr=False, compare=False)
    _committed: bool = field(repr=False, compare=False)

    def __new__(cls) -> PrivateRunArtifactWriter:
        raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE)


def _canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _tracker_authority_is_exact(value: object) -> bool:
    if not isinstance(value, dict) or set(value) != {
        "actual_canonical_date",
        "actual_sha256",
        "actual_size",
        "actual_version",
        "baseline_canonical_date",
        "baseline_sha256",
        "baseline_size",
        "baseline_version",
    }:
        return False
    return (
        isinstance(value["actual_sha256"], str)
        and _SHA256_RE.fullmatch(value["actual_sha256"]) is not None
        and type(value["actual_size"]) is int
        and value["actual_size"] > 0
        and isinstance(value["actual_version"], str)
        and _TRACKER_VERSION_RE.fullmatch(value["actual_version"]) is not None
        and isinstance(value["actual_canonical_date"], str)
        and _TRACKER_DATE_RE.fullmatch(value["actual_canonical_date"]) is not None
        and value["baseline_sha256"] == _BASELINE_TRACKER_SHA256
        and value["baseline_size"] == _BASELINE_TRACKER_SIZE
        and value["baseline_version"] == _BASELINE_TRACKER_VERSION
        and value["baseline_canonical_date"] == _BASELINE_TRACKER_DATE
        and (value["actual_sha256"], value["actual_size"])
        != (_BASELINE_TRACKER_SHA256, _BASELINE_TRACKER_SIZE)
    )


def _safe_component(value: str) -> str:
    if not isinstance(value, str) or _COMPONENT_RE.fullmatch(value) is None:
        raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE)
    return value


def _safe_file_name(value: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value in {".", ".."}
        or "/" in value
        or "\\" in value
        or "\x00" in value
        or len(value.encode("utf-8")) > 160
    ):
        raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE)
    return value


def _directory_flags() -> int:
    return os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)


def _regular_flags() -> int:
    return os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)


def _verify_directory_status(status: os.stat_result) -> None:
    if (
        not stat.S_ISDIR(status.st_mode)
        or stat.S_IMODE(status.st_mode) != PRIVATE_DIRECTORY_MODE
        or status.st_uid != os.getuid()
    ):
        raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE)


def _verify_regular_status(status: os.stat_result) -> None:
    if (
        not stat.S_ISREG(status.st_mode)
        or stat.S_IMODE(status.st_mode) != PRIVATE_FILE_MODE
        or status.st_uid != os.getuid()
        or status.st_nlink != 1
    ):
        raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE)


def _open_canonical_private_parent(parent: Path, *, create: bool) -> tuple[Path, int]:
    if not isinstance(parent, Path) or not parent.is_absolute():
        raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE)
    absolute = parent.absolute()
    if create:
        try:
            os.mkdir(absolute, PRIVATE_DIRECTORY_MODE)
        except FileExistsError:
            pass
        except OSError:
            raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE) from None
    try:
        resolved = absolute.resolve(strict=True)
        if resolved != absolute:
            raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE)
        descriptor = os.open(absolute, _directory_flags())
        _verify_directory_status(os.fstat(descriptor))
    except SmokeArtifactError:
        raise
    except OSError:
        raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE) from None
    return absolute, descriptor


def _mkdir_at(parent_descriptor: int, name: str) -> int:
    name = _safe_component(name)
    try:
        os.mkdir(name, PRIVATE_DIRECTORY_MODE, dir_fd=parent_descriptor)
        descriptor = os.open(name, _directory_flags(), dir_fd=parent_descriptor)
        _verify_directory_status(os.fstat(descriptor))
        return descriptor
    except (OSError, SmokeArtifactError):
        raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE) from None


def _write_file_at(
    directory_descriptor: int,
    name: str,
    content: bytes,
    *,
    hook: Callable[[str], None] | None,
) -> tuple[str, int]:
    name = _safe_file_name(name)
    if type(content) is not bytes:
        raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    descriptor = -1
    try:
        if hook is not None:
            hook(f"write:{name}")
        descriptor = os.open(
            name,
            flags,
            PRIVATE_FILE_MODE,
            dir_fd=directory_descriptor,
        )
        view = memoryview(content)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError(errno.EIO, "short private write")
            view = view[written:]
        os.fchmod(descriptor, PRIVATE_FILE_MODE)
        if hook is not None:
            hook(f"sync:{name}")
        os.fsync(descriptor)
        _verify_regular_status(os.fstat(descriptor))
    except Exception:
        raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE) from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    return _sha256(content), len(content)


def _snapshot_file_at(directory_descriptor: int, name: str) -> tuple[str, int]:
    descriptor = -1
    try:
        descriptor = os.open(name, _regular_flags(), dir_fd=directory_descriptor)
        before = os.fstat(descriptor)
        _verify_regular_status(before)
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
        _verify_regular_status(after)
        stable = (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mode,
            before.st_uid,
            before.st_nlink,
            before.st_mtime_ns,
            before.st_ctime_ns,
        ) == (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mode,
            after.st_uid,
            after.st_nlink,
            after.st_mtime_ns,
            after.st_ctime_ns,
        )
        content = b"".join(chunks)
        if not stable or len(content) != before.st_size:
            raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE)
        return _sha256(content), len(content)
    except SmokeArtifactError:
        raise
    except OSError:
        raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE) from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _status_identity(status: os.stat_result) -> tuple[int, ...]:
    return (
        status.st_dev,
        status.st_ino,
        status.st_size,
        status.st_mode,
        status.st_uid,
        status.st_gid,
        status.st_nlink,
        status.st_mtime_ns,
        status.st_ctime_ns,
    )


def _verify_pinned_child_directory(
    parent_descriptor: int,
    name: str,
    child_descriptor: int,
) -> None:
    try:
        named = os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
        pinned = os.fstat(child_descriptor)
        _verify_directory_status(named)
        _verify_directory_status(pinned)
        if _status_identity(named) != _status_identity(pinned):
            raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE)
    except SmokeArtifactError:
        raise
    except OSError:
        raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE) from None


def _rename_noreplace_at(
    source_parent: int,
    source: str,
    destination_parent: int,
    destination: str,
) -> None:
    source_bytes = os.fsencode(source)
    destination_bytes = os.fsencode(destination)
    if sys.platform == "darwin":
        libc = ctypes.CDLL(None, use_errno=True)
        renameatx_np = libc.renameatx_np
        renameatx_np.argtypes = (
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        )
        renameatx_np.restype = ctypes.c_int
        if renameatx_np(
            source_parent,
            source_bytes,
            destination_parent,
            destination_bytes,
            0x00000004,
        ) != 0:
            error = ctypes.get_errno()
            raise OSError(error, os.strerror(error))
        return
    if sys.platform.startswith("linux"):
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = getattr(libc, "renameat2", None)
        if renameat2 is not None:
            renameat2.argtypes = (
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_int,
                ctypes.c_char_p,
                ctypes.c_uint,
            )
            renameat2.restype = ctypes.c_int
            if renameat2(
                source_parent,
                source_bytes,
                destination_parent,
                destination_bytes,
                1,
            ) != 0:
                error = ctypes.get_errno()
                raise OSError(error, os.strerror(error))
            return
    raise OSError(errno.ENOTSUP, "atomic no-replace rename unavailable")


def _commit_tree_at(
    parent_descriptor: int,
    namespace: str,
    payloads: Mapping[str, bytes],
    *,
    completion_name: str,
    completion_fields: Mapping[str, object],
    hook: Callable[[str], None] | None = None,
) -> ArtifactCommitResult:
    namespace = _safe_component(namespace)
    completion_name = _safe_file_name(completion_name)
    reserved_completion_keys = frozenset(
        {"complete", "inventory_sha256", "inventory_size", "namespace", "schema_version"}
    )
    allowed_completion_keys = frozenset(
        {
            "authorization_sha256",
            "candidate_checksum_record_sha256",
            "checkpoint_protocol",
            "condition_protocol",
            "completed_optimizer_update",
            "condition",
            "device",
            "launch_manifest_sha256",
            "resume_rehearsal_result_sha256",
            "sanitized_view_sha256",
            "tracker_authority_sha256",
        }
    )
    if (
        not isinstance(payloads, Mapping)
        or not payloads
        or completion_name in payloads
        or "inventory.json" in payloads
        or any(_safe_file_name(name) != name for name in payloads)
        or any(type(content) is not bytes for content in payloads.values())
        or not isinstance(completion_fields, Mapping)
        or set(completion_fields) & reserved_completion_keys
        or not set(completion_fields) <= allowed_completion_keys
    ):
        raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE)
    stage_name = "artifact-stage-" + secrets.token_hex(16)
    stage_descriptor = -1
    renamed = False
    try:
        stage_descriptor = _mkdir_at(parent_descriptor, stage_name)
        inventory: dict[str, dict[str, object]] = {}
        for name in sorted(payloads):
            digest, size = _write_file_at(
                stage_descriptor,
                name,
                payloads[name],
                hook=hook,
            )
            inventory[name] = {
                "mode": "0600",
                "sha256": digest,
                "size": size,
            }
        inventory_bytes = _canonical_json_bytes(
            {
                "algorithm": "sha256",
                "files": inventory,
                "schema_version": 1,
            }
        )
        inventory_digest, inventory_size = _write_file_at(
            stage_descriptor,
            "inventory.json",
            inventory_bytes,
            hook=hook,
        )
        completion = {
            **dict(completion_fields),
            "complete": True,
            "inventory_sha256": inventory_digest,
            "inventory_size": inventory_size,
            "namespace": namespace,
            "schema_version": 1,
        }
        completion_bytes = _canonical_json_bytes(completion)
        completion_digest, _ = _write_file_at(
            stage_descriptor,
            completion_name,
            completion_bytes,
            hook=hook,
        )
        if hook is not None:
            hook("snapshot")
        for name, expected in {
            **{name: value["sha256"] for name, value in inventory.items()},
            "inventory.json": inventory_digest,
            completion_name: completion_digest,
        }.items():
            actual, _ = _snapshot_file_at(stage_descriptor, name)
            if actual != expected or _SHA256_RE.fullmatch(actual) is None:
                raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE)
        os.fsync(stage_descriptor)
        if hook is not None:
            hook("commit:before")
        _rename_noreplace_at(
            parent_descriptor,
            stage_name,
            parent_descriptor,
            namespace,
        )
        renamed = True
        if hook is not None:
            hook("commit:after")
        os.fsync(parent_descriptor)
    except SmokeArtifactError:
        if renamed:
            raise SmokeArtifactError(SMOKE_ARTIFACT_COMMIT_INDETERMINATE) from None
        raise
    except Exception:
        code = (
            SMOKE_ARTIFACT_COMMIT_INDETERMINATE
            if renamed
            else SMOKE_CHECKPOINT_WRITE_FAILURE
        )
        raise SmokeArtifactError(code) from None
    finally:
        if stage_descriptor >= 0:
            os.close(stage_descriptor)
    result = object.__new__(ArtifactCommitResult)
    for name, value in {
        "namespace": namespace,
        "inventory_sha256": inventory_digest,
        "completion_sha256": completion_digest,
        "file_count": len(payloads) + 2,
    }.items():
        object.__setattr__(result, name, value)
    return result


def begin_private_run_artifacts(
    parent: Path,
    run_name: str,
    *,
    create_parent: bool = False,
) -> PrivateRunArtifactWriter:
    """Begin a whole-run staging tree; no completed output is yet visible."""

    run_name = _safe_component(run_name)
    canonical, parent_descriptor = _open_canonical_private_parent(
        parent,
        create=create_parent,
    )
    stage_name = "run-stage-" + secrets.token_hex(16)
    try:
        stage_descriptor = _mkdir_at(parent_descriptor, stage_name)
        for condition in _CONDITIONS:
            condition_descriptor = _mkdir_at(stage_descriptor, condition)
            try:
                cpu_descriptor = _mkdir_at(condition_descriptor, "cpu")
                os.close(cpu_descriptor)
            finally:
                os.close(condition_descriptor)
        os.fsync(stage_descriptor)
    except Exception:
        os.close(parent_descriptor)
        raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE) from None
    writer = object.__new__(PrivateRunArtifactWriter)
    for name, value in {
        "run_name": run_name,
        "_parent": canonical,
        "_stage_name": stage_name,
        "_parent_descriptor": parent_descriptor,
        "_stage_descriptor": stage_descriptor,
        "_committed": False,
    }.items():
        object.__setattr__(writer, name, value)
    return writer


def commit_private_checkpoint(
    writer: PrivateRunArtifactWriter,
    *,
    condition: str,
    completed_update: int,
    payloads: Mapping[str, bytes],
    _test_hook: Callable[[str], None] | None = None,
) -> ArtifactCommitResult:
    """Commit one complete-boundary checkpoint inside run staging."""

    if (
        type(writer) is not PrivateRunArtifactWriter
        or writer._committed
        or condition not in _CONDITIONS
        or type(completed_update) is not int
        or completed_update not in _CHECKPOINT_UPDATES
    ):
        raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE)
    try:
        if set(payloads) != {
            "checkpoint_state.pt",
            "checkpoint_manifest.json",
            "checkpoint_inventory.json",
            "CHECKPOINT_COMPLETE.json",
        }:
            raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE)
        manifest = json.loads(payloads["checkpoint_manifest.json"].decode("utf-8"))
        inner_inventory = json.loads(
            payloads["checkpoint_inventory.json"].decode("utf-8")
        )
        completion = json.loads(
            payloads["CHECKPOINT_COMPLETE.json"].decode("utf-8")
        )
        if (
            not isinstance(manifest, dict)
            or not isinstance(inner_inventory, dict)
            or not isinstance(completion, dict)
            or _canonical_json_bytes(manifest) != payloads["checkpoint_manifest.json"]
            or _canonical_json_bytes(inner_inventory)
            != payloads["checkpoint_inventory.json"]
            or _canonical_json_bytes(completion) != payloads["CHECKPOINT_COMPLETE.json"]
            or completion.get("complete") is not True
            or completion.get("condition") != condition
            or completion.get("completed_optimizer_update") != completed_update
            or completion.get("namespace") != f"checkpoint-{completed_update:04d}"
            or completion.get("inventory_sha256")
            != _sha256(payloads["checkpoint_inventory.json"])
            or completion.get("checkpoint_protocol")
            != manifest.get("checkpoint_protocol")
            or completion.get("authorization_sha256")
            != manifest.get("authorization_sha256")
            or completion.get("candidate_checksum_record_sha256")
            != manifest.get("candidate_checksum_record_sha256")
            or completion.get("launch_manifest_sha256")
            != manifest.get("launch_manifest_sha256")
            or completion.get("sanitized_view_sha256")
            != manifest.get("sanitized_view_sha256")
        ):
            raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE)
    except (KeyError, UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE) from None
    condition_descriptor = cpu_descriptor = -1
    try:
        condition_descriptor = os.open(
            condition,
            _directory_flags(),
            dir_fd=writer._stage_descriptor,
        )
        cpu_descriptor = os.open(
            "cpu",
            _directory_flags(),
            dir_fd=condition_descriptor,
        )
        return _commit_tree_at(
            cpu_descriptor,
            f"checkpoint-{completed_update:04d}",
            {
                name: payloads[name]
                for name in (
                    "checkpoint_state.pt",
                    "checkpoint_manifest.json",
                    "checkpoint_inventory.json",
                )
            },
            completion_name="CHECKPOINT_COMPLETE.json",
            completion_fields={
                "authorization_sha256": completion["authorization_sha256"],
                "candidate_checksum_record_sha256": completion[
                    "candidate_checksum_record_sha256"
                ],
                "checkpoint_protocol": completion["checkpoint_protocol"],
                "completed_optimizer_update": completed_update,
                "condition": condition,
                "device": "cpu",
                "launch_manifest_sha256": completion["launch_manifest_sha256"],
                "sanitized_view_sha256": completion["sanitized_view_sha256"],
            },
            hook=_test_hook,
        )
    finally:
        if cpu_descriptor >= 0:
            os.close(cpu_descriptor)
        if condition_descriptor >= 0:
            os.close(condition_descriptor)


def commit_private_condition_result(
    writer: PrivateRunArtifactWriter,
    *,
    condition: str,
    payloads: Mapping[str, bytes],
    _test_hook: Callable[[str], None] | None = None,
) -> ArtifactCommitResult:
    """Commit one completed condition through its pinned condition namespace."""

    if (
        type(writer) is not PrivateRunArtifactWriter
        or writer._committed
        or condition not in _CONDITIONS
        or set(payloads) != {"condition_result.json"}
    ):
        raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE)
    try:
        record = json.loads(payloads["condition_result.json"].decode("utf-8"))
        required_record_keys = {
            "authorization_sha256",
            "candidate_checksum_record_sha256",
            "completed_optimizer_updates",
            "condition",
            "condition_protocol",
            "device",
            "launch_manifest_sha256",
            "mechanics_passed",
            "sanitized_view_sha256",
            "semantic_sha256",
            "tracker_authority",
        }
        if condition == "EnglishMono":
            required_record_keys.add("fresh_process_resume")
        replay = record.get("fresh_process_resume") if isinstance(record, dict) else None
        if (
            not isinstance(record, dict)
            or _canonical_json_bytes(record) != payloads["condition_result.json"]
            or set(record) != required_record_keys
            or record["condition"] != condition
            or record["completed_optimizer_updates"] != 1_000
            or record["condition_protocol"]
            != "neu_tiny_smoke_condition_completion_v1"
            or record["device"] != "cpu"
            or record["mechanics_passed"] is not True
            or not _tracker_authority_is_exact(record["tracker_authority"])
            or any(
                not isinstance(record[name], str)
                or _SHA256_RE.fullmatch(record[name]) is None
                for name in (
                    "authorization_sha256",
                    "candidate_checksum_record_sha256",
                    "launch_manifest_sha256",
                    "sanitized_view_sha256",
                    "semantic_sha256",
                )
            )
            or (
                condition == "EnglishMono"
                and (
                    not isinstance(replay, dict)
                    or set(replay)
                    != {
                        "checkpoint_update",
                        "first_replay_update",
                        "fresh_interpreter",
                        "last_replay_update",
                        "protocol",
                        "replay_result_sha256",
                        "replay_update_count",
                        "validation_updates",
                        "worker_pid_differed",
                    }
                    or replay["checkpoint_update"] != 750
                    or replay["first_replay_update"] != 751
                    or replay["fresh_interpreter"] is not True
                    or replay["last_replay_update"] != 1_000
                    or replay["protocol"]
                    != "neu_tiny_englishmono_fresh_process_worker_v1"
                    or not isinstance(replay["replay_result_sha256"], str)
                    or _SHA256_RE.fullmatch(replay["replay_result_sha256"])
                    is None
                    or replay["replay_update_count"] != 250
                    or replay["validation_updates"] != [800, 900, 1_000]
                    or replay["worker_pid_differed"] is not True
                )
            )
        ):
            raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE)
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError):
        raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE) from None
    condition_descriptor = cpu_descriptor = -1
    try:
        condition_descriptor = os.open(
            condition,
            _directory_flags(),
            dir_fd=writer._stage_descriptor,
        )
        cpu_descriptor = os.open(
            "cpu",
            _directory_flags(),
            dir_fd=condition_descriptor,
        )
        completion_fields = {
            "authorization_sha256": record["authorization_sha256"],
            "candidate_checksum_record_sha256": record[
                "candidate_checksum_record_sha256"
            ],
            "condition": condition,
            "condition_protocol": record["condition_protocol"],
            "device": "cpu",
            "launch_manifest_sha256": record["launch_manifest_sha256"],
            "sanitized_view_sha256": record["sanitized_view_sha256"],
            "tracker_authority_sha256": _sha256(
                _canonical_json_bytes(record["tracker_authority"])
            ),
        }
        if condition == "EnglishMono":
            completion_fields["resume_rehearsal_result_sha256"] = replay[
                "replay_result_sha256"
            ]
        return _commit_tree_at(
            cpu_descriptor,
            "condition-complete",
            payloads,
            completion_name="CONDITION_COMPLETE.json",
            completion_fields=completion_fields,
            hook=_test_hook,
        )
    finally:
        if cpu_descriptor >= 0:
            os.close(cpu_descriptor)
        if condition_descriptor >= 0:
            os.close(condition_descriptor)


def _tree_inventory_at(
    root_descriptor: int,
    *,
    excluded_files: frozenset[str] = frozenset(),
) -> tuple[dict[str, dict[str, object]], dict[str, dict[str, object]], str]:
    """Inventory recursively through pinned descriptors without path reopening."""

    inventory: dict[str, dict[str, object]] = {}
    directories: dict[str, dict[str, object]] = {}

    def visit(directory_descriptor: int, prefix: str) -> None:
        before_directory = os.fstat(directory_descriptor)
        _verify_directory_status(before_directory)
        try:
            names = sorted(os.listdir(directory_descriptor))
        except OSError:
            raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE) from None
        if len(names) != len(set(names)):
            raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE)
        for name in names:
            _safe_file_name(name)
            relative = name if not prefix else f"{prefix}/{name}"
            try:
                named_before = os.stat(
                    name,
                    dir_fd=directory_descriptor,
                    follow_symlinks=False,
                )
            except OSError:
                raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE) from None
            if stat.S_ISLNK(named_before.st_mode):
                raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE)
            if stat.S_ISDIR(named_before.st_mode):
                _verify_directory_status(named_before)
                child_descriptor = -1
                try:
                    child_descriptor = os.open(
                        name,
                        _directory_flags(),
                        dir_fd=directory_descriptor,
                    )
                    _verify_pinned_child_directory(
                        directory_descriptor,
                        name,
                        child_descriptor,
                    )
                    child_status = os.fstat(child_descriptor)
                    directories[relative] = {
                        "device": child_status.st_dev,
                        "gid": child_status.st_gid,
                        "inode": child_status.st_ino,
                        "mode": "0700",
                        "uid": child_status.st_uid,
                    }
                    visit(child_descriptor, relative)
                    _verify_pinned_child_directory(
                        directory_descriptor,
                        name,
                        child_descriptor,
                    )
                finally:
                    if child_descriptor >= 0:
                        os.close(child_descriptor)
                continue
            if relative in excluded_files:
                _verify_regular_status(named_before)
                continue
            _verify_regular_status(named_before)
            digest, size = _snapshot_file_at(directory_descriptor, name)
            try:
                named_after = os.stat(
                    name,
                    dir_fd=directory_descriptor,
                    follow_symlinks=False,
                )
            except OSError:
                raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE) from None
            if _status_identity(named_before) != _status_identity(named_after):
                raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE)
            inventory[relative] = {
                "device": named_after.st_dev,
                "gid": named_after.st_gid,
                "inode": named_after.st_ino,
                "link_count": named_after.st_nlink,
                "mode": "0600",
                "sha256": digest,
                "size": size,
                "uid": named_after.st_uid,
            }
        after_directory = os.fstat(directory_descriptor)
        _verify_directory_status(after_directory)
        if _status_identity(before_directory) != _status_identity(after_directory):
            raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE)

    visit(root_descriptor, "")
    directory_inventory = dict(sorted(directories.items()))
    payload = _canonical_json_bytes(
        {
            "algorithm": "sha256",
            "directories": directory_inventory,
            "files": inventory,
            "schema_version": 2,
        }
    )
    return inventory, directory_inventory, _sha256(payload)


def commit_private_run(
    writer: PrivateRunArtifactWriter,
    *,
    payloads: Mapping[str, bytes],
    completion_fields: Mapping[str, object],
    _test_hook: Callable[[str], None] | None = None,
) -> ArtifactCommitResult:
    """Write run metadata, snapshot the full staging tree, then commit no-replace."""

    if (
        type(writer) is not PrivateRunArtifactWriter
        or writer._committed
        or not isinstance(payloads, Mapping)
        or "run_manifest.json" not in payloads
        or any(_safe_file_name(name) != name for name in payloads)
        or any(type(content) is not bytes for content in payloads.values())
        or not isinstance(completion_fields, Mapping)
        or not set(completion_fields) <= {"description"}
        or any(type(value) is not str or len(value) > 160 for value in completion_fields.values())
    ):
        raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE)
    try:
        run_manifest = json.loads(payloads["run_manifest.json"].decode("utf-8"))
        required_manifest_keys = {
            "authorization_sha256",
            "candidate_checksum_record_sha256",
            "completed_conditions",
            "completed_updates_per_condition",
            "device",
            "launch_manifest_sha256",
            "mechanics_passed",
            "protocol",
            "resume_rehearsal_result_sha256",
            "run_identity_sha256",
            "sanitized_view_sha256",
            "terminal_classification",
            "tracker_authority",
        }
        if (
            not isinstance(run_manifest, dict)
            or set(run_manifest) != required_manifest_keys
            or _canonical_json_bytes(run_manifest) != payloads["run_manifest.json"]
            or run_manifest["protocol"] != "neu_tiny_smoke_runtime_run_v1"
            or run_manifest["completed_conditions"] != list(_CONDITIONS)
            or run_manifest["completed_updates_per_condition"] != 1_000
            or run_manifest["device"] != "cpu"
            or run_manifest["mechanics_passed"] is not True
            or run_manifest["terminal_classification"] != "mechanics_passed"
            or not _tracker_authority_is_exact(run_manifest["tracker_authority"])
            or any(
                not isinstance(run_manifest[name], str)
                or _SHA256_RE.fullmatch(run_manifest[name]) is None
                for name in (
                    "authorization_sha256",
                    "candidate_checksum_record_sha256",
                    "launch_manifest_sha256",
                    "resume_rehearsal_result_sha256",
                    "run_identity_sha256",
                    "sanitized_view_sha256",
                )
            )
        ):
            raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE)
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError):
        raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE) from None
    renamed = False
    try:
        _verify_pinned_child_directory(
            writer._parent_descriptor,
            writer._stage_name,
            writer._stage_descriptor,
        )
        for name in sorted(payloads):
            _write_file_at(
                writer._stage_descriptor,
                name,
                payloads[name],
                hook=_test_hook,
            )
        inventory, directories, inventory_digest = _tree_inventory_at(
            writer._stage_descriptor
        )
        inventory_bytes = _canonical_json_bytes(
            {
                "algorithm": "sha256",
                "directories": directories,
                "files": inventory,
                "schema_version": 2,
            }
        )
        written_inventory, _ = _write_file_at(
            writer._stage_descriptor,
            "RUN_INVENTORY.json",
            inventory_bytes,
            hook=_test_hook,
        )
        if written_inventory != inventory_digest:
            raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE)
        completion_bytes = _canonical_json_bytes(
            {
                **dict(completion_fields),
                "authorization_sha256": run_manifest["authorization_sha256"],
                "candidate_checksum_record_sha256": run_manifest[
                    "candidate_checksum_record_sha256"
                ],
                "complete": True,
                "completed_conditions": list(_CONDITIONS),
                "completed_updates_per_condition": 1_000,
                "inventory_sha256": inventory_digest,
                "launch_manifest_sha256": run_manifest["launch_manifest_sha256"],
                "mechanics_passed": True,
                "resume_rehearsal_result_sha256": run_manifest[
                    "resume_rehearsal_result_sha256"
                ],
                "run_identity_sha256": run_manifest["run_identity_sha256"],
                "run_name": writer.run_name,
                "sanitized_view_sha256": run_manifest["sanitized_view_sha256"],
                "schema_version": 1,
                "terminal_classification": "mechanics_passed",
                "tracker_authority_sha256": _sha256(
                    _canonical_json_bytes(run_manifest["tracker_authority"])
                ),
            }
        )
        completion_digest, _ = _write_file_at(
            writer._stage_descriptor,
            "RUN_COMPLETE.json",
            completion_bytes,
            hook=_test_hook,
        )
        if _test_hook is not None:
            _test_hook("snapshot")
        stable_inventory, stable_directories, stable_inventory_digest = _tree_inventory_at(
            writer._stage_descriptor,
            excluded_files=frozenset({"RUN_COMPLETE.json", "RUN_INVENTORY.json"}),
        )
        stable_inventory_file, _ = _snapshot_file_at(
            writer._stage_descriptor,
            "RUN_INVENTORY.json",
        )
        stable_completion_file, _ = _snapshot_file_at(
            writer._stage_descriptor,
            "RUN_COMPLETE.json",
        )
        if (
            stable_inventory != inventory
            or stable_directories != directories
            or stable_inventory_digest != inventory_digest
            or stable_inventory_file != written_inventory
            or stable_completion_file != completion_digest
        ):
            raise SmokeArtifactError(SMOKE_CHECKPOINT_WRITE_FAILURE)
        _verify_pinned_child_directory(
            writer._parent_descriptor,
            writer._stage_name,
            writer._stage_descriptor,
        )
        os.fsync(writer._stage_descriptor)
        if _test_hook is not None:
            _test_hook("commit:before")
        _rename_noreplace_at(
            writer._parent_descriptor,
            writer._stage_name,
            writer._parent_descriptor,
            writer.run_name,
        )
        renamed = True
        object.__setattr__(writer, "_committed", True)
        if _test_hook is not None:
            _test_hook("commit:after")
        os.fsync(writer._parent_descriptor)
    except SmokeArtifactError:
        if renamed:
            raise SmokeArtifactError(SMOKE_ARTIFACT_COMMIT_INDETERMINATE) from None
        raise
    except Exception:
        code = (
            SMOKE_ARTIFACT_COMMIT_INDETERMINATE
            if renamed
            else SMOKE_CHECKPOINT_WRITE_FAILURE
        )
        raise SmokeArtifactError(code) from None
    finally:
        if writer._stage_descriptor >= 0:
            os.close(writer._stage_descriptor)
            object.__setattr__(writer, "_stage_descriptor", -1)
        if writer._parent_descriptor >= 0:
            os.close(writer._parent_descriptor)
            object.__setattr__(writer, "_parent_descriptor", -1)
    result = object.__new__(ArtifactCommitResult)
    for name, value in {
        "namespace": writer.run_name,
        "inventory_sha256": inventory_digest,
        "completion_sha256": completion_digest,
        "file_count": len(inventory) + 2,
    }.items():
        object.__setattr__(result, name, value)
    return result


_STABLE_ARTIFACT_TYPE_NAMES = (
    "ArtifactCommitResult",
    "PrivateRunArtifactWriter",
    "SmokeArtifactError",
)
_previous_artifact_types = getattr(
    sys.modules[__name__],
    "_STABLE_ARTIFACT_BOUNDARY_TYPES",
    None,
)


def _stabilize_artifact_types(
    previous: Mapping[str, type[object]] | None,
) -> Mapping[str, type[object]]:
    current = {name: globals()[name] for name in _STABLE_ARTIFACT_TYPE_NAMES}
    stable = MappingProxyType(dict(current)) if previous is None else previous
    if set(stable) != set(_STABLE_ARTIFACT_TYPE_NAMES):
        raise RuntimeError("stable smoke artifact types are invalid")
    replacements = {id(current[name]): stable[name] for name in current}
    for name, class_type in stable.items():
        globals()[name] = class_type
    for value in tuple(globals().values()):
        if isinstance(value, FunctionType) and value.__module__ == __name__:
            value.__defaults__ = tuple(
                replacements.get(id(default), default)
                for default in (value.__defaults__ or ())
            )
            value.__kwdefaults__ = {
                name: replacements.get(id(default), default)
                for name, default in (value.__kwdefaults__ or {}).items()
            }
            value.__annotations__ = {
                name: replacements.get(id(annotation), annotation)
                for name, annotation in value.__annotations__.items()
            }
    module = sys.modules[__name__]
    if previous is None:

        class _StableArtifactModule(ModuleType):
            def __getattribute__(self, name: str) -> object:
                if name == "_STABLE_ARTIFACT_BOUNDARY_TYPES":
                    return stable
                return ModuleType.__getattribute__(self, name)

        module.__class__ = _StableArtifactModule
    globals()["_STABLE_ARTIFACT_BOUNDARY_TYPES"] = stable
    return stable


_STABLE_ARTIFACT_BOUNDARY_TYPES = _stabilize_artifact_types(
    _previous_artifact_types
)
del _previous_artifact_types
del _stabilize_artifact_types

SMOKE_ARTIFACT_PUBLIC_TYPES = MappingProxyType(
    {
        "ArtifactCommitResult": ArtifactCommitResult,
        "PrivateRunArtifactWriter": PrivateRunArtifactWriter,
        "SmokeArtifactError": SmokeArtifactError,
    }
)
