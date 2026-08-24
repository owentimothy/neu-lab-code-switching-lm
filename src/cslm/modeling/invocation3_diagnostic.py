"""Minimal checksum-bound, diagnostic-only authority for invocation-3 replay."""

# ruff: noqa: E302,E305,E501 -- compact exact-schema code preserves the reviewed source budget.

from __future__ import annotations

import hashlib
import importlib
import importlib.metadata
import json
import os
import re
import selectors
import stat
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType, ModuleType
from typing import Any

AUTHORITY_PATH = Path("/Users/timothyowen/Desktop/NEU_LAB_Codex_Context_2026-07-15/NEU_LAB_Tiny_Smoke_Invocation3_Minimal_Diagnostic_Authority_v2.json")
REPOSITORY_ROOT = Path("/Users/timothyowen/cs-lm-integrated-syntax")
RETAINED_STAGE = Path("/Users/timothyowen/NEU_LAB_private_runs/tiny_smoke/run-stage-e1f72b4384747f7f2250f6d651eec427")
CONTROLLER_ARGUMENT = "--internal-tiny-replay-diagnostic"
WORKER_ARGUMENT = "--internal-tiny-replay-diagnostic-worker"
AUTHORITY_SHA_ARGUMENT = "--approved-diagnostic-authority-sha256"
REQUEST_SHA_ARGUMENT = "--request-sha256"
ATTESTATION_ARGUMENT = "--attest-exclusive-uid-501-session"
AUTHORITY_PROTOCOL = "neu_tiny_invocation3_replay_authority_v2"
REQUEST_PROTOCOL = "neu_invocation3_replay_request_v2"
EVIDENCE_PROTOCOL = "neu_invocation3_replay_evidence_v2"
SOURCE_CLOSURE_PROTOCOL = "neu_tiny_executor_source_closure_v2"
STAGE_METADATA_PROTOCOL = "neu_invocation3_retained_stage_metadata_v2"
THREAT_MODEL_PROTOCOL = "neu_bounded_single_user_trusted_uid_v1"
AUTHORITY_SEMANTIC_DOMAIN = b"neu_tiny_invocation3_replay_authority_semantic_v2\0"
REQUEST_SEMANTIC_DOMAIN = b"neu_invocation3_replay_request_semantic_v2\0"
MAX_AUTHORITY_BYTES = 64 * 1024
OBSERVATION_NS = 600 * 1_000_000_000
HARD_TIMEOUT_NS = 3_600 * 1_000_000_000
STDOUT_LIMIT = 32_768
STDERR_LIMIT = 65_536
SOURCE_FILES = ("scripts/run_bounded_tiny_smoke.py", "src/cslm/modeling/config.py", "src/cslm/modeling/contracts.py", "src/cslm/modeling/initialization.py", "src/cslm/modeling/invocation3_diagnostic.py", "src/cslm/modeling/masking.py", "src/cslm/modeling/packing.py", "src/cslm/modeling/preparation.py", "src/cslm/modeling/scheduling.py", "src/cslm/modeling/smoke_artifacts.py", "src/cslm/modeling/smoke_training.py", "src/cslm/modeling/training_contract.py")
WORKER_ENVIRONMENT = MappingProxyType({"HF_HUB_OFFLINE": "1", "LANG": "C", "LC_ALL": "C", "MKL_NUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "PATH": "/opt/anaconda3/bin:/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "1729", "PYTHONNOUSERSITE": "1", "TOKENIZERS_PARALLELISM": "false", "TRANSFORMERS_OFFLINE": "1", "VECLIB_MAXIMUM_THREADS": "1"})
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_GIT_ID = re.compile(r"[0-9a-f]{40}\Z")
_ATTEMPT_ID = re.compile(r"[0-9a-f]{32}\Z")
_DIAGNOSTIC_TOKEN = object()
_HISTORICAL_TOKEN = object()
_EVENT_CATEGORIES = frozenset({"admission", "custody", "mechanics", "observation", "process", "result"})
_WORKER_PHASES = frozenset({"WORKER_ADMISSION_VALIDATED", "STAGE_METADATA_VALIDATED", "CONTROL_FILES_VALIDATED", "HISTORICAL_AUTHORITY_RECONSTRUCTED", "TRANSACTION_AND_ENVELOPE_BOUND", "ENVELOPE_VERIFIED_PREDECODE", "CHECKPOINT_RESTORED", "REPLAY_STARTED", "UPDATE_751_COMPLETED", "VALIDATION_800_COMPLETED", "VALIDATION_900_COMPLETED", "UPDATE_1000_COMPLETED", "VALIDATION_1000_COMPLETED", "RESULT_ENCODED"})


class Invocation3DiagnosticError(RuntimeError):
    """Privacy-safe fixed diagnostic rejection."""

    def __init__(self, code: str = "INVOCATION3_DIAGNOSTIC_REJECTED") -> None:
        self.code = code
        super().__init__(code)

@dataclass(frozen=True, init=False, slots=True)
class Invocation3ReplayDiagnosticAuthority:
    authority_file_sha256: str
    authority_semantic_sha256: str
    one_shot_attempt_id: str
    payload: Mapping[str, object] = field(repr=False, compare=False)
    _factory_token: object = field(repr=False, compare=False)

    def __new__(cls) -> Invocation3ReplayDiagnosticAuthority:
        raise Invocation3DiagnosticError()

@dataclass(frozen=True, init=False, slots=True)
class Invocation3ReplayDiagnosticAuthorization:
    authority: Invocation3ReplayDiagnosticAuthority
    historical_authorization_sha256: str
    one_shot_attempt_id: str
    _historical_authorization: object = field(repr=False, compare=False)
    _factory_token: object = field(repr=False, compare=False)

    def __new__(cls) -> Invocation3ReplayDiagnosticAuthorization:
        raise Invocation3DiagnosticError()

@dataclass(frozen=True, slots=True)
class _StageSnapshot:
    metadata_sha256: str
    root_device: int
    root_inode: int
    directory_count: int
    file_count: int
    total_file_bytes: int
    files: Mapping[str, tuple[int, ...]] = field(repr=False)

def _reject() -> None:
    raise Invocation3DiagnosticError()

def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()

def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")

def _no_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _reject()
        result[key] = value
    return result

def _decode_canonical(content: bytes) -> dict[str, object]:
    if content.startswith(b"\xef\xbb\xbf") or not content.endswith(b"\n") or content.endswith(b"\n\n"):
        _reject()
    try:
        text = content.decode("utf-8")
        value = json.loads(
            text,
            object_pairs_hook=_no_duplicates,
            parse_float=lambda _value: _reject(),
            parse_constant=lambda _value: _reject(),
        )
    except (UnicodeDecodeError, json.JSONDecodeError, Invocation3DiagnosticError):
        _reject()
    if not isinstance(value, dict) or _canonical(value) != content:
        _reject()
    return value

def _keys(value: object, expected: set[str]) -> Mapping[str, object]:
    if not isinstance(value, dict) or set(value) != expected:
        _reject()
    return value

def _text(value: object, *, exact: str | None = None, absolute: bool = False) -> str:
    if type(value) is not str or (exact is not None and value != exact):
        _reject()
    if absolute and (not Path(value).is_absolute() or Path(value) != Path(value).absolute()):
        _reject()
    return value

def _integer(value: object, *, exact: int | None = None, positive: bool = False) -> int:
    if type(value) is not int or (exact is not None and value != exact) or (positive and value <= 0):
        _reject()
    return value

def _boolean(value: object, exact: bool) -> bool:
    if type(value) is not bool or value is not exact:
        _reject()
    return value

def _hash(value: object) -> str:
    result = _text(value)
    if _SHA256.fullmatch(result) is None:
        _reject()
    return result

def _git_id(value: object) -> str:
    result = _text(value)
    if _GIT_ID.fullmatch(result) is None:
        _reject()
    return result

def _validate_authority_payload(payload: dict[str, object]) -> None:
    _keys(payload, {
        "authority_kind", "protocol", "schema_version", "status", "decision",
        "grants", "production_cli_count", "invocation_4_authorized",
        "one_shot_attempt_id", "threat_model", "implementation", "command",
        "historical_lineage", "retained_stage", "execution_policy",
        "authority_semantic_sha256",
    })
    _text(payload["authority_kind"], exact="invocation3_checkpoint750_replay_diagnostic_only")
    _text(payload["protocol"], exact=AUTHORITY_PROTOCOL)
    _integer(payload["schema_version"], exact=2)
    _text(payload["status"], exact="installed_reviewed")
    _text(payload["decision"], exact="diagnostic_authority_only_execution_separately_required")
    grants = _keys(payload["grants"], {"execution", "production", "production_completion"})
    for value in grants.values():
        _boolean(value, False)
    _integer(payload["production_cli_count"], exact=3)
    _boolean(payload["invocation_4_authorized"], False)
    attempt = _text(payload["one_shot_attempt_id"])
    if _ATTEMPT_ID.fullmatch(attempt) is None:
        _reject()
    threat = _keys(payload["threat_model"], {"protocol", "trusted_uid", "trusted_gid", "same_uid_adversary_defended"})
    _text(threat["protocol"], exact=THREAT_MODEL_PROTOCOL)
    _integer(threat["trusted_uid"], exact=501)
    _integer(threat["trusted_gid"], exact=20)
    _boolean(threat["same_uid_adversary_defended"], False)
    implementation = _keys(payload["implementation"], {
        "repository_root", "branch", "head_commit", "local_main_commit",
        "local_origin_main_commit", "ordered_parents", "tree",
        "source_closure_protocol", "source_closure_sha256", "origins",
    })
    _text(implementation["repository_root"], exact=str(REPOSITORY_ROOT), absolute=True)
    _text(implementation["branch"], exact="main")
    head = _git_id(implementation["head_commit"])
    if _git_id(implementation["local_main_commit"]) != head or _git_id(implementation["local_origin_main_commit"]) != head:
        _reject()
    parents = implementation["ordered_parents"]
    if not isinstance(parents, list) or len(parents) not in {1, 2}:
        _reject()
    for parent in parents:
        _git_id(parent)
    _git_id(implementation["tree"])
    _text(implementation["source_closure_protocol"], exact=SOURCE_CLOSURE_PROTOCOL)
    _hash(implementation["source_closure_sha256"])
    origins = _keys(implementation["origins"], {"controller_script", "diagnostic_module", "smoke_training_module", "smoke_artifacts_module"})
    for value in origins.values():
        _text(value, absolute=True)
    command = _keys(payload["command"], {"working_directory", "controller_argv_template", "worker_argv_template", "interpreter", "python_path", "packages", "worker_environment"})
    _text(command["working_directory"], exact=str(REPOSITORY_ROOT), absolute=True)
    interpreter = _keys(command["interpreter"], {"public_path", "resolved_path", "sha256", "size", "uid", "gid", "mode", "link_count", "python_version"})
    _text(interpreter["public_path"], absolute=True)
    _text(interpreter["resolved_path"], absolute=True)
    _hash(interpreter["sha256"])
    _integer(interpreter["size"], positive=True)
    _integer(interpreter["uid"], exact=501)
    _integer(interpreter["gid"], exact=20)
    _text(interpreter["mode"], exact="0755")
    _integer(interpreter["link_count"], exact=1)
    _text(interpreter["python_version"])
    python_path = command["python_path"]
    if not isinstance(python_path, list) or len(python_path) != 5:
        _reject()
    for item in python_path:
        _text(item, absolute=True)
    packages = _keys(command["packages"], {"numpy", "tokenizers", "torch", "transformers"})
    for package in packages.values():
        record = _keys(package, {"version", "root"})
        _text(record["version"])
        _text(record["root"], absolute=True)
    worker_environment = _keys(command["worker_environment"], set(WORKER_ENVIRONMENT))
    if dict(worker_environment) != dict(WORKER_ENVIRONMENT):
        _reject()
    script = str(REPOSITORY_ROOT / "scripts/run_bounded_tiny_smoke.py")
    executable = interpreter["public_path"]
    expected_controller = [executable, "-I", "-B", "-S", script, CONTROLLER_ARGUMENT, AUTHORITY_SHA_ARGUMENT, "{authority_file_sha256}", ATTESTATION_ARGUMENT]
    expected_worker = [executable, "-I", "-B", "-S", script, WORKER_ARGUMENT, "{request_path}", REQUEST_SHA_ARGUMENT, "{request_file_sha256}", AUTHORITY_SHA_ARGUMENT, "{authority_file_sha256}"]
    if command["controller_argv_template"] != expected_controller or command["worker_argv_template"] != expected_worker:
        _reject()
    lineage = _keys(payload["historical_lineage"], {"executor", "tracker", "manifest", "candidate", "production_authorization_sha256", "checkpoint"})
    executor = _keys(lineage["executor"], {"commit", "source_closure_sha256"})
    _text(executor["commit"], exact="9779180186febe9f1e7ff0de6e990f562443080e")
    _text(executor["source_closure_sha256"], exact="7b8b04614db9546c86f2bb17fcc9329f6e71cc62396f38464baf2f880a9d9256")
    tracker = _keys(lineage["tracker"], {"path", "sha256", "size"})
    _text(tracker["path"], absolute=True)
    _text(tracker["sha256"], exact="828688bdd9e19d77972b5686cdbe95572d67897b6a169413539863b06f543509")
    _integer(tracker["size"], exact=99_418)
    manifest = _keys(lineage["manifest"], {"path", "sha256", "size"})
    _text(manifest["path"], absolute=True)
    _text(manifest["sha256"], exact="d07ae9720dfb08011fbaf26116c7b783e350ede54d46fa2b048408df367583ae")
    _integer(manifest["size"], exact=4_079)
    candidate = _keys(lineage["candidate"], {"root", "reconciliation_key_path", "checksum_record_sha256", "preparation_manifest_sha256", "schedule_plan_identity_sha256", "sanitized_view_sha256"})
    _text(candidate["root"], absolute=True)
    _text(candidate["reconciliation_key_path"], absolute=True)
    for name in ("checksum_record_sha256", "preparation_manifest_sha256", "schedule_plan_identity_sha256", "sanitized_view_sha256"):
        _hash(candidate[name])
    _hash(lineage["production_authorization_sha256"])
    checkpoint = _keys(lineage["checkpoint"], {"condition", "device", "completed_update", "namespace", "checkpoint_protocol", "resume_protocol"})
    _text(checkpoint["condition"], exact="EnglishMono")
    _text(checkpoint["device"], exact="cpu")
    _integer(checkpoint["completed_update"], exact=750)
    _text(checkpoint["namespace"], exact="checkpoint-0750")
    _text(checkpoint["checkpoint_protocol"], exact="neu_tiny_smoke_checkpoint_v2")
    _text(checkpoint["resume_protocol"], exact="neu_tiny_englishmono_fresh_process_resume_v2")
    stage = _keys(payload["retained_stage"], {"path", "root_device", "root_inode", "uid", "gid", "directory_mode", "file_mode", "directory_count", "file_count", "total_file_bytes", "metadata_protocol", "metadata_sha256", "controls", "checkpoint_state", "external_envelope_sha256"})
    _text(stage["path"], exact=str(RETAINED_STAGE), absolute=True)
    _integer(stage["root_device"], positive=True)
    _integer(stage["root_inode"], exact=76_933_379)
    _integer(stage["uid"], exact=501)
    _integer(stage["gid"], exact=20)
    _text(stage["directory_mode"], exact="0700")
    _text(stage["file_mode"], exact="0600")
    _integer(stage["directory_count"], exact=14)
    _integer(stage["file_count"], exact=25)
    _integer(stage["total_file_bytes"], exact=76_566_392)
    _text(stage["metadata_protocol"], exact=STAGE_METADATA_PROTOCOL)
    _hash(stage["metadata_sha256"])
    controls = _keys(stage["controls"], {"transaction_completion", "transaction_inventory", "checkpoint_inventory", "checkpoint_manifest"})
    expected_relatives = {
        "transaction_completion": "EnglishMono/cpu/checkpoint-0750/CHECKPOINT_COMPLETE.json",
        "transaction_inventory": "EnglishMono/cpu/checkpoint-0750/inventory.json",
        "checkpoint_inventory": "EnglishMono/cpu/checkpoint-0750/checkpoint_inventory.json",
        "checkpoint_manifest": "EnglishMono/cpu/checkpoint-0750/checkpoint_manifest.json",
    }
    for name, relative in expected_relatives.items():
        record = _keys(controls[name], {"relative_path", "size", "sha256"})
        _text(record["relative_path"], exact=relative)
        _integer(record["size"], positive=True)
        _hash(record["sha256"])
    state = _keys(stage["checkpoint_state"], {"relative_path", "size", "sha256"})
    _text(state["relative_path"], exact="EnglishMono/cpu/checkpoint-0750/checkpoint_state.pt")
    _integer(state["size"], exact=17_676_843)
    _text(state["sha256"], exact="c8b18f8fc662362664309ff1b8222058a14e1a7acc84bf33640e29d91461eae2")
    _hash(stage["external_envelope_sha256"])
    policy = _keys(payload["execution_policy"], {"worker_count", "retry_count", "observation_seconds", "hard_timeout_seconds", "workspace_path", "preserve_workspace", "stdout_limit_bytes", "stderr_limit_bytes", "request_protocol", "evidence_protocol", "production_output_write"})
    _integer(policy["worker_count"], exact=1)
    _integer(policy["retry_count"], exact=0)
    _integer(policy["observation_seconds"], exact=600)
    _integer(policy["hard_timeout_seconds"], exact=3_600)
    _text(policy["workspace_path"], exact="/private/tmp/neu-invocation3-replay-<attempt-id>")
    _boolean(policy["preserve_workspace"], True)
    _integer(policy["stdout_limit_bytes"], exact=STDOUT_LIMIT)
    _integer(policy["stderr_limit_bytes"], exact=STDERR_LIMIT)
    _text(policy["request_protocol"], exact=REQUEST_PROTOCOL)
    _text(policy["evidence_protocol"], exact=EVIDENCE_PROTOCOL)
    _boolean(policy["production_output_write"], False)
    _hash(payload["authority_semantic_sha256"])


_IDENTITY_FIELDS = ("st_dev", "st_ino", "st_mode", "st_uid", "st_gid", "st_nlink", "st_size", "st_mtime_ns")

def _directory_descriptor(path: Path) -> int:
    if not path.is_absolute():
        _reject()
    descriptor = os.open("/", os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        current = Path("/")
        for component in path.parts[1:]:
            child = os.open(component, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0), dir_fd=descriptor)
            status = os.fstat(child)
            current /= component
            if not stat.S_ISDIR(status.st_mode) or (status.st_mode & 0o022 and not (current == Path("/private/tmp") and status.st_uid == 0 and status.st_mode & stat.S_ISVTX)):
                os.close(child)
                _reject()
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise

def _read_at(parent: int, name: str, maximum: int, *, uid: int | None = None, gid: int | None = None, mode: int | None = None) -> tuple[bytes, os.stat_result]:
    descriptor = -1
    try:
        parent_before = os.fstat(parent)
        descriptor = os.open(name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=parent)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > maximum or (uid is not None and before.st_uid != uid) or (gid is not None and before.st_gid != gid) or (mode is not None and stat.S_IMODE(before.st_mode) != mode):
            _reject()
        chunks: list[bytes] = []
        remaining = maximum + 1
        while remaining:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        content = b"".join(chunks)
        after = os.fstat(descriptor)
        parent_after = os.fstat(parent)
        if len(content) > maximum or any(getattr(before, field) != getattr(after, field) for field in _IDENTITY_FIELDS) or any(getattr(parent_before, field) != getattr(parent_after, field) for field in _IDENTITY_FIELDS):
            _reject()
        return content, after
    except Invocation3DiagnosticError:
        raise
    except OSError:
        _reject()
    finally:
        if descriptor >= 0:
            os.close(descriptor)

def _stable_read(path: Path, maximum: int, *, uid: int | None = None, gid: int | None = None, mode: int | None = None) -> tuple[bytes, os.stat_result]:
    parent = _directory_descriptor(path.parent)
    try:
        return _read_at(parent, path.name, maximum, uid=uid, gid=gid, mode=mode)
    finally:
        os.close(parent)

def _validate_path_custody(path: Path) -> None:
    descriptor = _directory_descriptor(path if path.is_dir() else path.parent)
    os.close(descriptor)

def load_authority(path: Path, expected_file_sha256: str) -> Invocation3ReplayDiagnosticAuthority:
    if path != AUTHORITY_PATH or _SHA256.fullmatch(expected_file_sha256) is None:
        _reject()
    _validate_path_custody(path)
    content, _ = _stable_read(path, MAX_AUTHORITY_BYTES, uid=501, gid=20, mode=0o600)
    if _sha(content) != expected_file_sha256:
        _reject()
    payload = _decode_canonical(content)
    _validate_authority_payload(payload)
    semantic_payload = dict(payload)
    semantic = semantic_payload.pop("authority_semantic_sha256")
    if semantic != _sha(AUTHORITY_SEMANTIC_DOMAIN + _canonical(semantic_payload)):
        _reject()
    result = object.__new__(Invocation3ReplayDiagnosticAuthority)
    object.__setattr__(result, "authority_file_sha256", expected_file_sha256)
    object.__setattr__(result, "authority_semantic_sha256", semantic)
    object.__setattr__(result, "one_shot_attempt_id", payload["one_shot_attempt_id"])
    object.__setattr__(result, "payload", MappingProxyType(payload))
    object.__setattr__(result, "_factory_token", _DIAGNOSTIC_TOKEN)
    return result

def _git(repository: Path, *arguments: str, allow_one: bool = False) -> str:
    result = subprocess.run(
        ("/usr/bin/git", "-C", str(repository), *arguments),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode != 0 and not (allow_one and result.returncode == 1):
        _reject()
    try:
        return result.stdout.decode("utf-8")
    except UnicodeDecodeError:
        _reject()

def source_closure_sha256(repository: Path) -> str:
    inventory: list[list[str]] = []
    for relative in SOURCE_FILES:
        content, _ = _stable_read(repository / relative, 5 * 1024 * 1024)
        inventory.append([relative, _sha(content)])
    return _sha(_canonical([SOURCE_CLOSURE_PROTOCOL, inventory]))

def _validate_current_source(authority: Invocation3ReplayDiagnosticAuthority) -> None:
    implementation = authority.payload["implementation"]
    repository = Path(implementation["repository_root"])
    head = implementation["head_commit"]
    if (
        _git(repository, "symbolic-ref", "--short", "HEAD").strip() != "main"
        or _git(repository, "rev-parse", "HEAD").strip() != head
        or _git(repository, "rev-parse", "refs/heads/main").strip() != head
        or _git(repository, "rev-parse", "refs/remotes/origin/main").strip() != head
        or _git(repository, "show", "-s", "--format=%P", "HEAD").split() != implementation["ordered_parents"]
        or _git(repository, "rev-parse", "HEAD^{tree}").strip() != implementation["tree"]
        or _git(repository, "status", "--porcelain=v1", "--untracked-files=all")
        or source_closure_sha256(repository) != implementation["source_closure_sha256"]
    ):
        _reject()

def _package_root(name: str) -> str:
    distribution = importlib.metadata.distribution(name)
    return str(Path(distribution.locate_file(name.replace("-", "_"))).resolve())

def bootstrap_runtime(
    authority: Invocation3ReplayDiagnosticAuthority,
    *,
    controller_script: Path,
    argv: Sequence[str],
    worker: bool,
) -> ModuleType:
    if type(authority) is not Invocation3ReplayDiagnosticAuthority or authority._factory_token is not _DIAGNOSTIC_TOKEN:
        _reject()
    _validate_current_source(authority)
    command = authority.payload["command"]
    interpreter = command["interpreter"]
    expected = list(command["worker_argv_template"] if worker else command["controller_argv_template"])
    replacements = {
        "{authority_file_sha256}": authority.authority_file_sha256,
        "{request_path}": argv[6] if worker and len(argv) > 6 else "",
        "{request_file_sha256}": argv[8] if worker and len(argv) > 8 else "",
    }
    expected = [replacements.get(item, item) for item in expected]
    executable = Path(sys.executable)
    resolved = executable.resolve(strict=True)
    content, status = _stable_read(resolved, 128 * 1024 * 1024)
    _validate_path_custody(controller_script)
    _validate_path_custody(resolved)
    flags_ok = sys.flags.isolated == 1 and sys.flags.no_site == 1 and sys.flags.dont_write_bytecode == 1
    if (
        list(argv) != expected
        or Path.cwd() != Path(command["working_directory"])
        or controller_script.resolve() != Path(authority.payload["implementation"]["origins"]["controller_script"])
        or str(executable) != interpreter["public_path"]
        or str(resolved) != interpreter["resolved_path"]
        or _sha(content) != interpreter["sha256"]
        or status.st_size != interpreter["size"]
        or status.st_uid != interpreter["uid"]
        or status.st_gid != interpreter["gid"]
        or f"{stat.S_IMODE(status.st_mode):04o}" != interpreter["mode"]
        or status.st_nlink != interpreter["link_count"]
        or sys.version != interpreter["python_version"]
        or not flags_ok
        or (worker and dict(os.environ) != dict(command["worker_environment"]))
    ):
        _reject()
    sys.path[:] = list(command["python_path"])
    if sys.path != command["python_path"]:
        _reject()
    for name, expected_package in command["packages"].items():
        if importlib.metadata.version(name) != expected_package["version"] or _package_root(name) != expected_package["root"]:
            _reject()
        _validate_path_custody(Path(expected_package["root"]))
    smoke = importlib.import_module("cslm.modeling.smoke_training")
    origins = authority.payload["implementation"]["origins"]
    if (
        Path(__file__).resolve() != Path(origins["diagnostic_module"])
        or Path(smoke.__file__).resolve() != Path(origins["smoke_training_module"])
        or Path(importlib.import_module("cslm.modeling.smoke_artifacts").__file__).resolve() != Path(origins["smoke_artifacts_module"])
    ):
        _reject()
    return smoke

def _stage_root(authority: Invocation3ReplayDiagnosticAuthority) -> tuple[int, os.stat_result]:
    expected = authority.payload["retained_stage"]
    descriptor = _directory_descriptor(Path(expected["path"]))
    status = os.fstat(descriptor)
    if status.st_dev != expected["root_device"] or status.st_ino != expected["root_inode"] or status.st_uid != expected["uid"] or status.st_gid != expected["gid"] or stat.S_IMODE(status.st_mode) != int(expected["directory_mode"], 8):
        os.close(descriptor)
        _reject()
    return descriptor, status

def _stage_snapshot(authority: Invocation3ReplayDiagnosticAuthority) -> _StageSnapshot:
    expected = authority.payload["retained_stage"]
    opened: set[int] = set()
    try:
        root, root_status = _stage_root(authority)
        opened.add(root)
        entries: list[list[object]] = [[".", "d", root_status.st_dev, root_status.st_ino, root_status.st_uid, root_status.st_gid, f"{stat.S_IMODE(root_status.st_mode):04o}", root_status.st_nlink, root_status.st_size]]
        files: dict[str, tuple[int, ...]] = {}
        directory_count = 1
        file_count = total = 0
        pending = [(root, "")]
        while pending:
            directory, prefix = pending.pop()
            directory_before = os.fstat(directory)
            for name in sorted(os.listdir(directory)):
                relative = f"{prefix}/{name}" if prefix else name
                status = os.stat(name, dir_fd=directory, follow_symlinks=False)
                kind = "d" if stat.S_ISDIR(status.st_mode) else "f" if stat.S_ISREG(status.st_mode) else "x"
                if kind == "x" or status.st_uid != expected["uid"] or status.st_gid != expected["gid"] or (kind == "d" and stat.S_IMODE(status.st_mode) != int(expected["directory_mode"], 8)) or (kind == "f" and (stat.S_IMODE(status.st_mode) != int(expected["file_mode"], 8) or status.st_nlink != 1)):
                    _reject()
                record = [relative, kind, status.st_dev, status.st_ino, status.st_uid, status.st_gid, f"{stat.S_IMODE(status.st_mode):04o}", status.st_nlink, status.st_size]
                entries.append(record)
                if kind == "d":
                    child = os.open(name, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0), dir_fd=directory)
                    if any(getattr(status, field) != getattr(os.fstat(child), field) for field in _IDENTITY_FIELDS):
                        os.close(child)
                        _reject()
                    opened.add(child)
                    directory_count += 1
                    pending.append((child, relative))
                else:
                    file_count += 1
                    total += status.st_size
                    files[relative] = (status.st_dev, status.st_ino, status.st_mode, status.st_uid, status.st_gid, status.st_nlink, status.st_size, status.st_mtime_ns)
            if any(getattr(directory_before, field) != getattr(os.fstat(directory), field) for field in _IDENTITY_FIELDS):
                _reject()
            os.close(directory)
            opened.remove(directory)
    except Invocation3DiagnosticError:
        raise
    except OSError:
        _reject()
    finally:
        for descriptor in opened:
            os.close(descriptor)
    digest = _sha(_canonical([STAGE_METADATA_PROTOCOL, sorted(entries)]))
    if (
        directory_count != expected["directory_count"]
        or file_count != expected["file_count"]
        or total != expected["total_file_bytes"]
        or digest != expected["metadata_sha256"]
    ):
        _reject()
    return _StageSnapshot(digest, root_status.st_dev, root_status.st_ino, directory_count, file_count, total, MappingProxyType(files))

def _read_stage_payload(authority: Invocation3ReplayDiagnosticAuthority, snapshot: _StageSnapshot, relative: str, expected: Mapping[str, object]) -> bytes:
    if relative not in snapshot.files or expected["relative_path"] != relative:
        _reject()
    stage = authority.payload["retained_stage"]
    parts = Path(relative).parts
    if not parts or Path(relative).is_absolute() or any(part in ("", ".", "..") for part in parts):
        _reject()
    directory, _ = _stage_root(authority)
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0), dir_fd=directory)
            status = os.fstat(child)
            if not stat.S_ISDIR(status.st_mode) or status.st_uid != stage["uid"] or status.st_gid != stage["gid"] or stat.S_IMODE(status.st_mode) != int(stage["directory_mode"], 8):
                os.close(child)
                _reject()
            os.close(directory)
            directory = child
        content, status = _read_at(directory, parts[-1], int(expected["size"]), uid=stage["uid"], gid=stage["gid"], mode=int(stage["file_mode"], 8))
        current = tuple(getattr(status, field) for field in _IDENTITY_FIELDS)
        if current != snapshot.files[relative] or len(content) != expected["size"] or _sha(content) != expected["sha256"]:
            _reject()
        return content
    except OSError:
        _reject()
    finally:
        os.close(directory)

def _process_snapshot(*, worker: bool) -> tuple[str, int, int]:
    result = subprocess.run(("/bin/ps", "-axo", "pid=,command="), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
    if result.returncode != 0:
        _reject()
    relevant: list[list[object]] = []
    others = 0
    for line in result.stdout.decode("utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        pid_text, _, command = stripped.partition(" ")
        if CONTROLLER_ARGUMENT in command or WORKER_ARGUMENT in command:
            pid = int(pid_text)
            category = "worker" if WORKER_ARGUMENT in command else "controller"
            relevant.append([pid, category])
            if category == "worker" and pid != os.getpid():
                others += 1
    expected_maximum = 2 if worker else 1
    if others or len(relevant) > expected_maximum:
        _reject()
    return _sha(_canonical(["neu_invocation3_process_snapshot_v2", sorted(relevant)])), len(relevant), others

def _request_payload(authority: Invocation3ReplayDiagnosticAuthority, workspace: Path, stage: _StageSnapshot, process_snapshot: tuple[str, int, int], started: int) -> dict[str, object]:
    payload: dict[str, object] = {
        "protocol": REQUEST_PROTOCOL,
        "schema_version": 2,
        "one_shot_attempt_id": authority.one_shot_attempt_id,
        "process_nonce": _sha(os.urandom(32)),
        "parent_pid": os.getpid(),
        "workspace_path": str(workspace),
        "authority_file_sha256": authority.authority_file_sha256,
        "authority_semantic_sha256": authority.authority_semantic_sha256,
        "request_source_closure_sha256": authority.payload["implementation"]["source_closure_sha256"],
        "interpreter_sha256": authority.payload["command"]["interpreter"]["sha256"],
        "stage_metadata_sha256": stage.metadata_sha256,
        "quiescence_snapshot_sha256": process_snapshot[0],
        "relevant_process_count": process_snapshot[1],
        "other_replay_worker_count": process_snapshot[2],
        "attempt_started_monotonic_ns": started,
        "observation_boundary_monotonic_ns": started + OBSERVATION_NS,
        "hard_deadline_monotonic_ns": started + HARD_TIMEOUT_NS,
    }
    payload["request_semantic_sha256"] = _sha(REQUEST_SEMANTIC_DOMAIN + _canonical(payload))
    return payload

def _parse_request(content: bytes, expected_sha256: str) -> dict[str, object]:
    if _sha(content) != expected_sha256:
        _reject()
    request = _decode_canonical(content)
    required = {"protocol", "schema_version", "one_shot_attempt_id", "process_nonce", "parent_pid", "workspace_path", "authority_file_sha256", "authority_semantic_sha256", "request_source_closure_sha256", "interpreter_sha256", "stage_metadata_sha256", "quiescence_snapshot_sha256", "relevant_process_count", "other_replay_worker_count", "attempt_started_monotonic_ns", "observation_boundary_monotonic_ns", "hard_deadline_monotonic_ns", "request_semantic_sha256"}
    _keys(request, required)
    semantic = request["request_semantic_sha256"]
    draft = dict(request)
    draft.pop("request_semantic_sha256")
    if (
        request["protocol"] != REQUEST_PROTOCOL
        or type(request["schema_version"]) is not int
        or request["schema_version"] != 2
        or any(type(request[name]) is not str or _SHA256.fullmatch(request[name]) is None for name in ("process_nonce", "authority_file_sha256", "authority_semantic_sha256", "request_source_closure_sha256", "interpreter_sha256", "stage_metadata_sha256", "quiescence_snapshot_sha256", "request_semantic_sha256"))
        or type(request["one_shot_attempt_id"]) is not str or _ATTEMPT_ID.fullmatch(request["one_shot_attempt_id"]) is None or type(request["workspace_path"]) is not str or not Path(request["workspace_path"]).is_absolute()
        or any(type(request[name]) is not int for name in ("parent_pid", "relevant_process_count", "other_replay_worker_count", "attempt_started_monotonic_ns", "observation_boundary_monotonic_ns", "hard_deadline_monotonic_ns"))
        or semantic != _sha(REQUEST_SEMANTIC_DOMAIN + _canonical(draft))
    ):
        _reject()
    return request

def _exclusive_write(path: Path, content: bytes) -> None:
    descriptor = -1
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        os.fchmod(descriptor, 0o600)
        view = memoryview(content)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError
            view = view[written:]
        os.fsync(descriptor)
    except OSError:
        _reject()
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    parent = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(parent)
    finally:
        os.close(parent)

def _publish_completion(workspace: Path, content: bytes) -> None:
    directory = _directory_descriptor(workspace)
    directory_status = os.fstat(directory)
    if directory_status.st_uid != 501 or directory_status.st_gid != 20 or stat.S_IMODE(directory_status.st_mode) != 0o700:
        os.close(directory)
        _reject()
    descriptor = final_descriptor = -1
    pending, final = ".completion.json.pending", "completion.json"
    created: dict[str, tuple[int, int]] = {}
    try:
        descriptor = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600, dir_fd=directory)
        os.fchmod(descriptor, 0o600)
        os.fchown(descriptor, 501, 20)
        created[pending] = (os.fstat(descriptor).st_dev, os.fstat(descriptor).st_ino)
        view = memoryview(content)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError
            view = view[written:]
        os.fsync(descriptor)
        status = os.fstat(descriptor)
        if not stat.S_ISREG(status.st_mode) or status.st_uid != 501 or status.st_gid != 20 or stat.S_IMODE(status.st_mode) != 0o600 or status.st_nlink != 1 or status.st_size != len(content):
            raise OSError
        os.link(pending, final, src_dir_fd=directory, dst_dir_fd=directory, follow_symlinks=False)
        created[final] = created[pending]
        os.unlink(pending, dir_fd=directory)
        final_descriptor = os.open(final, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=directory)
        published = os.fstat(final_descriptor)
        if (published.st_dev, published.st_ino) != created[final] or not stat.S_ISREG(published.st_mode) or stat.S_IMODE(published.st_mode) != 0o600 or published.st_uid != 501 or published.st_gid != 20 or published.st_nlink != 1 or published.st_size != len(content):
            raise OSError
        os.fsync(directory)
    except BaseException:
        safe_absence = True
        for name, identity in reversed(tuple(created.items())):
            try:
                status = os.stat(name, dir_fd=directory, follow_symlinks=False)
                if (status.st_dev, status.st_ino) == identity:
                    os.unlink(name, dir_fd=directory)
                else:
                    safe_absence = False
            except FileNotFoundError:
                pass
            except OSError:
                safe_absence = False
        try:
            os.fsync(directory)
        except OSError:
            safe_absence = False
        raise Invocation3DiagnosticError("INVOCATION3_DIAGNOSTIC_REJECTED" if safe_absence else "INVOCATION3_EVIDENCE_INDETERMINATE") from None
    finally:
        if final_descriptor >= 0:
            os.close(final_descriptor)
        if descriptor >= 0:
            os.close(descriptor)
        os.close(directory)

def _workspace(authority: Invocation3ReplayDiagnosticAuthority) -> Path:
    root = Path("/private/tmp")
    root_status = os.lstat(root)
    if root_status.st_uid != 0 or not stat.S_ISDIR(root_status.st_mode) or not (root_status.st_mode & stat.S_ISVTX):
        _reject()
    workspace = root / f"neu-invocation3-replay-{authority.one_shot_attempt_id}"
    try:
        os.mkdir(workspace, 0o700)
        os.chown(workspace, 501, 20, follow_symlinks=False)
    except OSError:
        _reject()
    status = os.lstat(workspace)
    if not stat.S_ISDIR(status.st_mode) or status.st_uid != 501 or status.st_gid != 20 or stat.S_IMODE(status.st_mode) != 0o700:
        _reject()
    return workspace

def _deadline_state(now: int, observation: int, hard: int) -> tuple[bool, bool]:
    return now >= observation, now >= hard

def _kill_and_reap(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        process.kill()
    try:
        process.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        _reject()
    if process.poll() is None:
        _reject()

def _drain_process(process: subprocess.Popen[bytes], observation: int, hard: int, *, clock: Callable[[], int] = time.monotonic_ns, observation_sink: Callable[[], None] | None = None) -> Mapping[str, object]:
    selector = selectors.DefaultSelector()
    streams = (("stdout", process.stdout, STDOUT_LIMIT), ("stderr", process.stderr, STDERR_LIMIT))
    states = {name: {"count": 0, "hash": hashlib.sha256(), "data": bytearray(), "limit": limit} for name, _, limit in streams}
    for name, stream, _ in streams:
        if stream is None:
            _reject()
        os.set_blocking(stream.fileno(), False)
        selector.register(stream, selectors.EVENT_READ, name)
    crossed = killed = False
    def consume(timeout: float) -> bool:
        ready = selector.select(timeout)
        for key, _ in ready:
            try:
                chunk = os.read(key.fileobj.fileno(), 65_536)
            except BlockingIOError:
                continue
            if not chunk:
                selector.unregister(key.fileobj)
                continue
            state = states[key.data]
            state["count"] += len(chunk)
            state["hash"].update(chunk)
            remaining = state["limit"] + 1 - len(state["data"])
            if remaining > 0:
                state["data"].extend(chunk[:remaining])
        return bool(ready)

    try:
        while True:
            now = clock()
            observed, timed_out = _deadline_state(now, observation, hard)
            if observed and not crossed:
                crossed = True
                if observation_sink is not None:
                    observation_sink()
            if timed_out:
                killed = True
                _kill_and_reap(process)
                while selector.get_map() and consume(0):
                    pass
                break
            if process.poll() is not None:
                while selector.get_map() and consume(0):
                    pass
                break
            timeout = min(0.1, max(0.0, (hard - now) / 1_000_000_000))
            if selector.get_map():
                consume(timeout)
            else:
                try:
                    process.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    pass
    finally:
        for _, stream, _ in streams:
            if stream is not None:
                stream.close()
        selector.close()
    return MappingProxyType({
        "crossed_observation": crossed,
        "hard_timeout": killed,
        "returncode": process.returncode,
        "stdout": bytes(states["stdout"]["data"]),
        "stdout_bytes": states["stdout"]["count"],
        "stdout_sha256": states["stdout"]["hash"].hexdigest(),
        "stderr": bytes(states["stderr"]["data"]),
        "stderr_bytes": states["stderr"]["count"],
        "stderr_sha256": states["stderr"]["hash"].hexdigest(),
    })

def _guard(request: Mapping[str, object]) -> None:
    if os.getppid() != request["parent_pid"] or time.monotonic_ns() >= request["hard_deadline_monotonic_ns"]:
        _reject()

def _bounded_file(record: Mapping[str, object], *, mode: int) -> bytes:
    path = Path(record["path"])
    content, _ = _stable_read(path, int(record["size"]), uid=501, gid=20, mode=mode)
    if len(content) != record["size"] or _sha(content) != record["sha256"]:
        _reject()
    return content

def _historical_authorization(authority: Invocation3ReplayDiagnosticAuthority, smoke: ModuleType, guard: Callable[[], None]) -> Invocation3ReplayDiagnosticAuthorization:
    lineage = authority.payload["historical_lineage"]
    candidate = lineage["candidate"]
    tracker = lineage["tracker"]
    manifest = lineage["manifest"]
    guard()
    _bounded_file(tracker, mode=0o644)
    guard()
    _bounded_file(manifest, mode=0o600)
    guard()
    runtime_policy = smoke._verify_supported_runtime()
    approval = smoke._load_future_tracker_approval(
        Path(tracker["path"]),
        candidate_checksum=candidate["checksum_record_sha256"],
        preparation_manifest=candidate["preparation_manifest_sha256"],
        schedule_identity=candidate["schedule_plan_identity_sha256"],
        executor_commit=lineage["executor"]["commit"],
        executor_closure_digest=lineage["executor"]["source_closure_sha256"],
        runtime_policy_sha256=runtime_policy,
        output_parent=smoke.APPROVED_OUTPUT_PARENT,
        authority_kind="production_tracker_and_launch",
        production=True,
        token=_HISTORICAL_TOKEN,
    )
    guard()
    launch = smoke._validate_launch_before_candidate_load(
        approval,
        Path(manifest["path"]),
        authority_kind="production_tracker_and_launch",
        executor_commit=lineage["executor"]["commit"],
        executor_closure_digest=lineage["executor"]["source_closure_sha256"],
        runtime_policy_sha256=runtime_policy,
        output_parent=smoke.APPROVED_OUTPUT_PARENT,
        production=True,
        token=_HISTORICAL_TOKEN,
    )
    guard()
    if Path(candidate["root"]) != smoke.APPROVED_CANDIDATE_ROOT or Path(candidate["reconciliation_key_path"]) != smoke.APPROVED_RECONCILIATION_KEY_PATH:
        _reject()
    smoke._validate_candidate_custody(Path(candidate["root"]), Path(candidate["reconciliation_key_path"]), production=True)
    guard()
    try:
        snapshot = smoke.load_preparation_candidate(Path(candidate["root"]), reconciliation_key_path=Path(candidate["reconciliation_key_path"]))
        guard()
        view = smoke.derive_sanitized_training_view(snapshot)
        guard()
        paired = smoke.create_paired_initialization(smoke.NEU_TINY, smoke.TINY_SMOKE_SEED_PLANS[0])
    except Invocation3DiagnosticError:
        raise
    except Exception:
        _reject()
    guard()
    historical = smoke._construct_bound_production_authorization(
        approval,
        launch,
        view,
        paired,
        authority_kind="production_tracker_and_launch",
        required_view_kind="production_loader",
        output_parent=smoke.APPROVED_OUTPUT_PARENT,
        token=_HISTORICAL_TOKEN,
    )
    guard()
    if (
        approval.tracker_sha256 != tracker["sha256"]
        or approval.tracker_size != tracker["size"]
        or approval._tracker_path != Path(tracker["path"])
        or launch.manifest_sha256 != manifest["sha256"]
        or len(launch._manifest_bytes) != manifest["size"]
        or launch._manifest_path != Path(manifest["path"])
        or launch.executor_commit != lineage["executor"]["commit"]
        or launch.executor_closure_digest != lineage["executor"]["source_closure_sha256"]
        or launch.resume_protocol != lineage["checkpoint"]["resume_protocol"]
        or approval.candidate_checksum_record_sha256 != candidate["checksum_record_sha256"]
        or approval.preparation_manifest_sha256 != candidate["preparation_manifest_sha256"]
        or approval.schedule_plan_identity_sha256 != candidate["schedule_plan_identity_sha256"]
        or view.semantic_sha256 != candidate["sanitized_view_sha256"]
        or historical.authorization_sha256 != lineage["production_authorization_sha256"]
    ):
        _reject()
    result = object.__new__(Invocation3ReplayDiagnosticAuthorization)
    object.__setattr__(result, "authority", authority)
    object.__setattr__(result, "historical_authorization_sha256", historical.authorization_sha256)
    object.__setattr__(result, "one_shot_attempt_id", authority.one_shot_attempt_id)
    object.__setattr__(result, "_historical_authorization", historical)
    object.__setattr__(result, "_factory_token", _DIAGNOSTIC_TOKEN)
    return result

def _worker_replay(authority: Invocation3ReplayDiagnosticAuthority, request: Mapping[str, object], smoke: ModuleType, sink: Callable[[str, int | None], None]) -> bytes:
    def guard() -> None:
        _guard(request)

    guard()
    stage = _stage_snapshot(authority)
    guard()
    if stage.metadata_sha256 != request["stage_metadata_sha256"]:
        _reject()
    sink("STAGE_METADATA_VALIDATED", None)
    controls_spec = authority.payload["retained_stage"]["controls"]
    controls: dict[str, bytes] = {}
    for name in ("transaction_completion", "transaction_inventory", "checkpoint_inventory", "checkpoint_manifest"):
        guard()
        record = controls_spec[name]
        controls[name] = _read_stage_payload(authority, stage, record["relative_path"], record)
        guard()
    completion = smoke._checkpoint_json(controls["transaction_completion"])
    smoke._checkpoint_json(controls["transaction_inventory"])
    smoke._checkpoint_json(controls["checkpoint_inventory"])
    manifest = smoke._checkpoint_json(controls["checkpoint_manifest"])
    checkpoint = authority.payload["historical_lineage"]["checkpoint"]
    if completion.get("condition") != checkpoint["condition"] or completion.get("completed_optimizer_update") != checkpoint["completed_update"] or completion.get("namespace") != checkpoint["namespace"] or completion.get("checkpoint_protocol") != checkpoint["checkpoint_protocol"] or manifest.get("checkpoint_protocol") != checkpoint["checkpoint_protocol"]:
        _reject()
    guard()
    sink("CONTROL_FILES_VALIDATED", None)
    diagnostic = _historical_authorization(authority, smoke, guard)
    sink("HISTORICAL_AUTHORITY_RECONSTRUCTED", None)
    if diagnostic.historical_authorization_sha256 != authority.payload["historical_lineage"]["production_authorization_sha256"]:
        _reject()
    state_spec = authority.payload["retained_stage"]["checkpoint_state"]
    guard()
    state = _read_stage_payload(authority, stage, state_spec["relative_path"], state_spec)
    guard()
    files = {
        "CHECKPOINT_COMPLETE.json": controls["transaction_completion"],
        "inventory.json": controls["transaction_inventory"],
        "checkpoint_inventory.json": controls["checkpoint_inventory"],
        "checkpoint_manifest.json": controls["checkpoint_manifest"],
        "checkpoint_state.pt": state,
        "artifact_transaction_completion.json": controls["transaction_completion"],
        "artifact_transaction_inventory.json": controls["transaction_inventory"],
    }
    try:
        canonical = smoke._canonical_checkpoint_transaction_files({name: files[name] for name in ("checkpoint_inventory.json", "checkpoint_manifest.json", "checkpoint_state.pt")})
    except Exception:
        _reject()
    if any(canonical[name] != files[name] for name in canonical):
        _reject()
    historical = diagnostic._historical_authorization
    replay_request = MappingProxyType({
        "artifact_completion_sha256": _sha(files["artifact_transaction_completion.json"]),
        "artifact_inventory_sha256": _sha(files["artifact_transaction_inventory.json"]),
        "authorization_sha256": diagnostic.historical_authorization_sha256,
        "candidate_checksum_record_sha256": authority.payload["historical_lineage"]["candidate"]["checksum_record_sha256"],
        "checkpoint_envelope_sha256": authority.payload["retained_stage"]["external_envelope_sha256"],
        "checkpoint_inventory_sha256": _sha(files["checkpoint_inventory.json"]),
        "launch_manifest_sha256": authority.payload["historical_lineage"]["manifest"]["sha256"],
        "parent_pid": request["parent_pid"],
        "process_start_nonce": request["process_nonce"],
        "sanitized_view_sha256": authority.payload["historical_lineage"]["candidate"]["sanitized_view_sha256"],
    })
    guard()
    smoke._verify_replay_transaction(replay_request, files)
    guard()
    envelope = smoke._checkpoint_envelope_from_files_for_tests_impl(
        {name: files[name] for name in ("CHECKPOINT_COMPLETE.json", "checkpoint_inventory.json", "checkpoint_manifest.json", "checkpoint_state.pt", "inventory.json")},
        authority.payload["retained_stage"]["external_envelope_sha256"],
        token=_HISTORICAL_TOKEN,
    )
    guard()
    sink("TRANSACTION_AND_ENVELOPE_BOUND", None)
    return smoke._execute_verified_replay(historical, envelope, replay_request, token=_HISTORICAL_TOKEN, diagnostic_sink=sink, guard=guard)

def run_worker(request_path: Path, request_sha256: str, authority_sha256: str, *, controller_script: Path, argv: Sequence[str], sink: Callable[[str, int | None], None]) -> bytes:
    request_content, _ = _stable_read(request_path, 64 * 1024, uid=501, gid=20, mode=0o600)
    request = _parse_request(request_content, request_sha256)
    authority = load_authority(AUTHORITY_PATH, authority_sha256)
    if request["authority_file_sha256"] != authority.authority_file_sha256 or request["authority_semantic_sha256"] != authority.authority_semantic_sha256 or request["one_shot_attempt_id"] != authority.one_shot_attempt_id or Path(request["workspace_path"]) != Path("/private/tmp") / f"neu-invocation3-replay-{authority.one_shot_attempt_id}" or request_path != Path(request["workspace_path"]) / "request.json" or request["observation_boundary_monotonic_ns"] - request["attempt_started_monotonic_ns"] != OBSERVATION_NS or request["hard_deadline_monotonic_ns"] - request["attempt_started_monotonic_ns"] != HARD_TIMEOUT_NS or request["relevant_process_count"] != 1 or request["other_replay_worker_count"] != 0:
        _reject()
    _guard(request)
    smoke = bootstrap_runtime(authority, controller_script=controller_script, argv=argv, worker=True)
    _guard(request)
    if request["request_source_closure_sha256"] != authority.payload["implementation"]["source_closure_sha256"] or request["interpreter_sha256"] != authority.payload["command"]["interpreter"]["sha256"]:
        _reject()
    _process_snapshot(worker=True)
    sink("WORKER_ADMISSION_VALIDATED", None)
    result = _worker_replay(authority, request, smoke, sink)
    _guard(request)
    return result

def _worker_records(content: bytes) -> tuple[tuple[str, int | None], ...]:
    records: list[tuple[str, int | None]] = []
    for line in content.splitlines(keepends=True):
        record = _decode_canonical(line)
        _keys(record, {"category", "phase", "update"})
        if record["category"] != "mechanics" or record["phase"] not in _WORKER_PHASES or (record["update"] is not None and type(record["update"]) is not int):
            _reject()
        records.append((record["phase"], record["update"]))
    return tuple(records)

def _open_events(path: Path) -> tuple[int, Any, list[int]]:
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        os.fchmod(descriptor, 0o600)
    except OSError:
        _reject()
    parent = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(parent)
    finally:
        os.close(parent)
    return descriptor, hashlib.sha256(), [0]

def _event(events: tuple[int, Any, list[int]], authority: Invocation3ReplayDiagnosticAuthority, started: int, phase: str, category: str, update: int | None = None) -> None:
    if category not in _EVENT_CATEGORIES or (update is not None and type(update) is not int):
        _reject()
    descriptor, digest, sequence = events
    record = _canonical({"protocol": EVIDENCE_PROTOCOL, "one_shot_attempt_id": authority.one_shot_attempt_id, "sequence": sequence[0], "elapsed_monotonic_ms": max(0, (time.monotonic_ns() - started) // 1_000_000), "phase": phase, "update": update, "category": category})
    try:
        view = memoryview(record)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError
            view = view[written:]
        os.fsync(descriptor)
    except OSError:
        _reject()
    digest.update(record)
    sequence[0] += 1

def run_controller(authority_sha256: str, *, controller_script: Path, argv: Sequence[str]) -> Mapping[str, object]:
    started = time.monotonic_ns()
    authority = load_authority(AUTHORITY_PATH, authority_sha256)
    smoke = bootstrap_runtime(authority, controller_script=controller_script, argv=argv, worker=False)
    process_snapshot = _process_snapshot(worker=False)
    stage = _stage_snapshot(authority)
    workspace = _workspace(authority)
    request = _request_payload(authority, workspace, stage, process_snapshot, started)
    request_bytes = _canonical(request)
    request_sha256 = _sha(request_bytes)
    _exclusive_write(workspace / "request.json", request_bytes)
    events = _open_events(workspace / "events.jsonl")
    _event(events, authority, started, "CONTROLLER_ADMISSION_VALIDATED", "admission")
    process: subprocess.Popen[bytes] | None = None
    channels: Mapping[str, object] = MappingProxyType({"crossed_observation": False, "hard_timeout": False, "returncode": None, "stdout": b"", "stdout_bytes": 0, "stdout_sha256": _sha(b""), "stderr": b"", "stderr_bytes": 0, "stderr_sha256": _sha(b"")})
    disposition = "WORKER_FAILED"
    parsed_semantic: str | None = None
    try:
        _validate_current_source(authority)
        if _stage_snapshot(authority).metadata_sha256 != stage.metadata_sha256:
            _reject()
        command = list(authority.payload["command"]["worker_argv_template"])
        substitutions = {"{request_path}": str(workspace / "request.json"), "{request_file_sha256}": request_sha256, "{authority_file_sha256}": authority.authority_file_sha256}
        command = [substitutions.get(item, item) for item in command]
        process = subprocess.Popen(
            command,
            cwd=authority.payload["command"]["working_directory"],
            env=dict(authority.payload["command"]["worker_environment"]),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        _event(events, authority, started, "WORKER_SPAWNED", "process")
        channels = _drain_process(process, request["observation_boundary_monotonic_ns"], request["hard_deadline_monotonic_ns"], observation_sink=lambda: _event(events, authority, started, "OBSERVATION_BOUNDARY_REACHED", "observation"))
        if channels["hard_timeout"]:
            disposition = "HARD_TIMEOUT"
        elif channels["stdout_bytes"] > STDOUT_LIMIT or channels["stderr_bytes"] > STDERR_LIMIT:
            disposition = "CHANNEL_OVERSIZED"
        else:
            try:
                worker_records = _worker_records(channels["stderr"])
                if not worker_records or worker_records[-1][0] != "RESULT_ENCODED":
                    _reject()
                for phase, update in worker_records:
                    _event(events, authority, started, phase, "mechanics", update)
                parsed = smoke._parse_fresh_process_replay_result(channels["stdout"], expected_pid=process.pid)
                parsed_semantic = parsed.result_sha256
            except Exception:
                disposition = "CHANNEL_OR_RESULT_MALFORMED"
            else:
                disposition = "DIAGNOSTIC_REPLAY_MECHANICS_COMPLETED" if channels["returncode"] == 0 else "WORKER_FAILED"
    except BaseException:
        if process is not None and process.poll() is None:
            _kill_and_reap(process)
        disposition = "CONTROLLER_REJECTED"
    _event(events, authority, started, "CONTROLLER_DISPOSITION_RECORDED", "result")
    os.close(events[0])
    completion = {
        "protocol": EVIDENCE_PROTOCOL,
        "one_shot_attempt_id": authority.one_shot_attempt_id,
        "authority_file_sha256": authority.authority_file_sha256,
        "authority_semantic_sha256": authority.authority_semantic_sha256,
        "request_file_sha256": request_sha256,
        "request_semantic_sha256": request["request_semantic_sha256"],
        "diagnostic_disposition": disposition,
        "observation_boundary_reached": channels["crossed_observation"],
        "worker_return_code": channels["returncode"],
        "stdout_bytes": channels["stdout_bytes"],
        "stdout_sha256": channels["stdout_sha256"],
        "stderr_bytes": channels["stderr_bytes"],
        "stderr_sha256": channels["stderr_sha256"],
        "parsed_result_semantic_sha256": parsed_semantic,
        "events_sha256": events[1].hexdigest(),
        "diagnostic_only": True,
        "production_completion": False,
        "production_cli_count": 3,
        "invocation_4_authorized": False,
    }
    _publish_completion(workspace, _canonical(completion))
    return MappingProxyType({**completion, "workspace_disposition": "preserved", "workspace_path": str(workspace)})
