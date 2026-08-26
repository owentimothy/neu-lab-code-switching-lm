from __future__ import annotations

# ruff: noqa: E501 -- compact synthetic matrices preserve the reviewed test budget.
import ast
import copy
import hashlib
import importlib.util
import json
import os
import select
import stat
import subprocess
import sys
from fractions import Fraction
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import pytest
import test_bounded_tiny_smoke_executor as legacy

import cslm.modeling.invocation3_diagnostic as diagnostic
import cslm.modeling.smoke_training as smoke

ZERO_SHA = "0" * 64
ONE_SHA = "1" * 64
TWO_SHA = "2" * 64
THREE_SHA = "3" * 64


def _base_payload() -> dict[str, object]:
    repository = diagnostic.REPOSITORY_ROOT
    script = repository / "scripts/run_bounded_tiny_smoke.py"
    interpreter = "/opt/anaconda3/bin/python"
    return {
        "authority_kind": "invocation3_checkpoint750_replay_diagnostic_only",
        "protocol": diagnostic.AUTHORITY_PROTOCOL,
        "schema_version": 2,
        "status": "installed_reviewed",
        "decision": "diagnostic_authority_only_execution_separately_required",
        "grants": {
            "execution": False,
            "production": False,
            "production_completion": False,
        },
        "production_cli_count": 3,
        "invocation_4_authorized": False,
        "one_shot_attempt_id": "0123456789abcdef0123456789abcdef",
        "threat_model": {
            "protocol": diagnostic.THREAT_MODEL_PROTOCOL,
            "trusted_uid": 501,
            "trusted_gid": 20,
            "same_uid_adversary_defended": False,
        },
        "implementation": {
            "repository_root": str(repository),
            "branch": "main",
            "head_commit": "a" * 40,
            "local_main_commit": "a" * 40,
            "local_origin_main_commit": "a" * 40,
            "ordered_parents": ["b" * 40, "c" * 40],
            "tree": "d" * 40,
            "source_closure_protocol": diagnostic.SOURCE_CLOSURE_PROTOCOL,
            "source_closure_sha256": ZERO_SHA,
            "origins": {
                "controller_script": str(script),
                "diagnostic_module": str(repository / "src/cslm/modeling/invocation3_diagnostic.py"),
                "smoke_training_module": str(repository / "src/cslm/modeling/smoke_training.py"),
                "smoke_artifacts_module": str(repository / "src/cslm/modeling/smoke_artifacts.py"),
            },
        },
        "command": {
            "working_directory": str(repository),
            "controller_argv_template": [interpreter, "-I", "-B", "-S", str(script), diagnostic.CONTROLLER_ARGUMENT, diagnostic.AUTHORITY_SHA_ARGUMENT, "{authority_file_sha256}", diagnostic.ATTESTATION_ARGUMENT],
            "worker_argv_template": [interpreter, "-I", "-B", "-S", str(script), diagnostic.WORKER_ARGUMENT, "{request_path}", diagnostic.REQUEST_SHA_ARGUMENT, "{request_file_sha256}", diagnostic.AUTHORITY_SHA_ARGUMENT, "{authority_file_sha256}"],
            "interpreter": {
                "public_path": interpreter,
                "resolved_path": "/opt/anaconda3/bin/python3.12",
                "sha256": ONE_SHA,
                "size": 1_000,
                "uid": 501,
                "gid": 20,
                "mode": "0755",
                "link_count": 1,
                "python_version": "3.12.synthetic",
            },
            "python_path": ["/opt/anaconda3/lib/python312.zip", "/opt/anaconda3/lib/python3.12", "/opt/anaconda3/lib/python3.12/lib-dynload", str(repository / "src"), "/opt/anaconda3/lib/python3.12/site-packages"],
            "packages": {
                "numpy": {
                    "version": "1.0",
                    "root": "/opt/anaconda3/lib/python3.12/site-packages/numpy",
                },
                "tokenizers": {
                    "version": "1.0",
                    "root": "/opt/anaconda3/lib/python3.12/site-packages/tokenizers",
                },
                "torch": {
                    "version": "1.0",
                    "root": "/opt/anaconda3/lib/python3.12/site-packages/torch",
                },
                "transformers": {
                    "version": "1.0",
                    "root": "/opt/anaconda3/lib/python3.12/site-packages/transformers",
                },
            },
            "worker_environment": dict(diagnostic.WORKER_ENVIRONMENT),
        },
        "historical_lineage": {
            "executor": {
                "commit": "9779180186febe9f1e7ff0de6e990f562443080e",
                "source_closure_sha256": (
                    "7b8b04614db9546c86f2bb17fcc9329f6e71cc62396f38464baf2f880a9d9256"
                ),
            },
            "tracker": {
                "path": "/synthetic/historical-tracker.md",
                "sha256": (
                    "828688bdd9e19d77972b5686cdbe95572d67897b6a169413539863b06f543509"
                ),
                "size": 99_418,
            },
            "manifest": {
                "path": "/synthetic/historical-manifest.json",
                "sha256": (
                    "d07ae9720dfb08011fbaf26116c7b783e350ede54d46fa2b048408df367583ae"
                ),
                "size": 4_079,
            },
            "candidate": {
                "root": "/synthetic/candidate",
                "reconciliation_key_path": "/synthetic/key",
                "checksum_record_sha256": TWO_SHA,
                "preparation_manifest_sha256": THREE_SHA,
                "schedule_plan_identity_sha256": "4" * 64,
                "sanitized_view_sha256": "5" * 64,
            },
            "production_authorization_sha256": "6" * 64,
            "checkpoint": {
                "condition": "EnglishMono",
                "device": "cpu",
                "completed_update": 750,
                "namespace": "checkpoint-0750",
                "checkpoint_protocol": "neu_tiny_smoke_checkpoint_v2",
                "resume_protocol": "neu_tiny_englishmono_fresh_process_resume_v2",
            },
        },
        "retained_stage": {
            "path": str(diagnostic.RETAINED_STAGE),
            "root_device": 1,
            "root_inode": 76_933_379,
            "uid": 501,
            "gid": 20,
            "directory_mode": "0700",
            "file_mode": "0600",
            "directory_count": 14,
            "file_count": 25,
            "total_file_bytes": 76_566_392,
            "metadata_protocol": diagnostic.STAGE_METADATA_PROTOCOL,
            "metadata_sha256": "7" * 64,
            "controls": {
                "transaction_completion": {
                    "relative_path": (
                        "EnglishMono/cpu/checkpoint-0750/"
                        "CHECKPOINT_COMPLETE.json"
                    ),
                    "size": 1,
                    "sha256": "8" * 64,
                },
                "transaction_inventory": {
                    "relative_path": (
                        "EnglishMono/cpu/checkpoint-0750/inventory.json"
                    ),
                    "size": 1,
                    "sha256": "9" * 64,
                },
                "checkpoint_inventory": {
                    "relative_path": (
                        "EnglishMono/cpu/checkpoint-0750/"
                        "checkpoint_inventory.json"
                    ),
                    "size": 1,
                    "sha256": "a" * 64,
                },
                "checkpoint_manifest": {
                    "relative_path": (
                        "EnglishMono/cpu/checkpoint-0750/"
                        "checkpoint_manifest.json"
                    ),
                    "size": 1,
                    "sha256": "b" * 64,
                },
            },
            "checkpoint_state": {
                "relative_path": (
                    "EnglishMono/cpu/checkpoint-0750/checkpoint_state.pt"
                ),
                "size": 17_676_843,
                "sha256": (
                    "c8b18f8fc662362664309ff1b8222058a14e1a7acc84bf33640e29d91461eae2"
                ),
            },
            "external_envelope_sha256": "c" * 64,
        },
        "execution_policy": {
            "worker_count": 1,
            "retry_count": 0,
            "observation_seconds": 600,
            "hard_timeout_seconds": 3_600,
            "workspace_path": "/private/tmp/neu-invocation3-replay-<attempt-id>",
            "preserve_workspace": True,
            "stdout_limit_bytes": diagnostic.STDOUT_LIMIT,
            "stderr_limit_bytes": diagnostic.STDERR_LIMIT,
            "request_protocol": diagnostic.REQUEST_PROTOCOL,
            "evidence_protocol": diagnostic.EVIDENCE_PROTOCOL,
            "production_output_write": False,
        },
        "authority_semantic_sha256": ZERO_SHA,
    }


def _seal(payload: dict[str, object]) -> bytes:
    draft = copy.deepcopy(payload)
    draft.pop("authority_semantic_sha256")
    payload["authority_semantic_sha256"] = diagnostic._sha(
        diagnostic.AUTHORITY_SEMANTIC_DOMAIN + diagnostic._canonical(draft)
    )
    return diagnostic._canonical(payload)


def _authority_object(
    payload: dict[str, object],
) -> diagnostic.Invocation3ReplayDiagnosticAuthority:
    result = object.__new__(diagnostic.Invocation3ReplayDiagnosticAuthority)
    object.__setattr__(result, "authority_file_sha256", "f" * 64)
    object.__setattr__(
        result,
        "authority_semantic_sha256",
        payload["authority_semantic_sha256"],
    )
    object.__setattr__(
        result,
        "one_shot_attempt_id",
        payload["one_shot_attempt_id"],
    )
    object.__setattr__(result, "payload", MappingProxyType(payload))
    object.__setattr__(
        result,
        "_factory_token",
        diagnostic._DIAGNOSTIC_TOKEN,
    )
    return result


def _write_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    payload: dict[str, object] | None = None,
    *,
    content: bytes | None = None,
) -> tuple[Path, bytes]:
    path = tmp_path / "authority.json"
    monkeypatch.setattr(diagnostic, "AUTHORITY_PATH", path)
    body = _seal(payload or _base_payload()) if content is None else content
    path.write_bytes(body)
    os.chmod(path, 0o600)
    os.chown(path, 501, 20)
    return path, body


def test_authority_parser_canonical_round_trip_and_independent_hashes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _base_payload()
    path, content = _write_authority(tmp_path, monkeypatch, payload)
    whole = hashlib.sha256(content).hexdigest()
    authority = diagnostic.load_authority(path, whole)
    assert type(authority) is diagnostic.Invocation3ReplayDiagnosticAuthority
    assert authority.authority_file_sha256 == whole
    assert authority.authority_semantic_sha256 == payload[
        "authority_semantic_sha256"
    ]
    assert authority.authority_file_sha256 != authority.authority_semantic_sha256
    assert diagnostic._canonical(dict(authority.payload)) == content
    assert authority.one_shot_attempt_id == payload["one_shot_attempt_id"]


@pytest.mark.parametrize(
    "mutation",
    (
        "bom",
        "missing_lf",
        "double_lf",
        "leading_space",
        "duplicate",
        "wrong_whole_sha",
        "wrong_semantic_sha",
    ),
)
def test_authority_parser_rejects_noncanonical_or_wrong_hash_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    payload = _base_payload()
    content = _seal(payload)
    expected = hashlib.sha256(content).hexdigest()
    if mutation == "bom":
        content = b"\xef\xbb\xbf" + content
    elif mutation == "missing_lf":
        content = content[:-1]
    elif mutation == "double_lf":
        content += b"\n"
    elif mutation == "leading_space":
        content = b" " + content
    elif mutation == "duplicate":
        content = content.replace(
            b'{"authority_kind":',
            b'{"authority_kind":"duplicate","authority_kind":',
            1,
        )
    elif mutation == "wrong_whole_sha":
        expected = "e" * 64
    else:
        payload["authority_semantic_sha256"] = "e" * 64
        content = diagnostic._canonical(payload)
        expected = hashlib.sha256(content).hexdigest()
    path, _ = _write_authority(
        tmp_path,
        monkeypatch,
        content=content,
    )
    with pytest.raises(diagnostic.Invocation3DiagnosticError):
        diagnostic.load_authority(path, expected)


@pytest.mark.parametrize(
    ("path", "value"),
    (
        (("unexpected",), True),
        (("schema_version",), True),
        (("production_cli_count",), False),
        (("invocation_4_authorized",), 0),
        (("grants", "execution"), 0),
        (("threat_model", "trusted_uid"), True),
        (("implementation", "head_commit"), "A" * 40),
        (("implementation", "source_closure_sha256"), "A" * 64),
        (("command", "interpreter", "size"), True),
        (("command", "python_path"), []),
        (("historical_lineage", "checkpoint", "completed_update"), 750.0),
        (("retained_stage", "file_count"), True),
        (("execution_policy", "retry_count"), 1),
    ),
)
def test_authority_schema_rejects_unknown_wrong_type_or_wrong_fixed_value(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    path: tuple[str, ...],
    value: object,
) -> None:
    payload = _base_payload()
    target: dict[str, object] = payload
    for component in path[:-1]:
        target = target[component]  # type: ignore[assignment]
    target[path[-1]] = value
    authority_path, content = _write_authority(
        tmp_path,
        monkeypatch,
        payload,
    )
    with pytest.raises(diagnostic.Invocation3DiagnosticError):
        diagnostic.load_authority(
            authority_path,
            hashlib.sha256(content).hexdigest(),
        )


def test_authority_parser_rejects_missing_nested_field(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = _base_payload()
    payload["historical_lineage"]["candidate"].pop("sanitized_view_sha256")
    path, content = _write_authority(tmp_path, monkeypatch, payload)
    with pytest.raises(diagnostic.Invocation3DiagnosticError):
        diagnostic.load_authority(
            path,
            hashlib.sha256(content).hexdigest(),
        )


def test_authority_types_are_factory_only_and_distinct() -> None:
    with pytest.raises(diagnostic.Invocation3DiagnosticError):
        diagnostic.Invocation3ReplayDiagnosticAuthority()
    with pytest.raises(diagnostic.Invocation3DiagnosticError):
        diagnostic.Invocation3ReplayDiagnosticAuthorization()
    assert (
        diagnostic.Invocation3ReplayDiagnosticAuthority
        is not diagnostic.Invocation3ReplayDiagnosticAuthorization
    )
    assert diagnostic._DIAGNOSTIC_TOKEN is not diagnostic._HISTORICAL_TOKEN


def test_diagnostic_parser_rejects_production_document(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, content = _write_authority(
        tmp_path,
        monkeypatch,
        content=b'{"authority_kind":"production_tracker_and_launch"}\n',
    )
    with pytest.raises(diagnostic.Invocation3DiagnosticError):
        diagnostic.load_authority(
            path,
            hashlib.sha256(content).hexdigest(),
        )


def test_production_parser_rejects_diagnostic_document(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path, _ = _write_authority(tmp_path, monkeypatch)
    with pytest.raises(
        smoke.SmokeTrainingError,
        match=smoke.SMOKE_APPROVAL_MISMATCH,
    ):
        smoke.load_candidate_approval_evidence(path)


def _run_git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ("/usr/bin/git", "-C", str(repository), *arguments),
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _temporary_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    repository.mkdir()
    _run_git(repository, "init", "-q")
    _run_git(repository, "config", "user.name", "Synthetic Reviewer")
    _run_git(
        repository,
        "config",
        "user.email",
        "synthetic@example.invalid",
    )
    for relative in diagnostic.SOURCE_FILES:
        path = repository / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"synthetic:{relative}\n", encoding="utf-8")
    _run_git(repository, "add", "--", ".")
    _run_git(repository, "commit", "-q", "-m", "synthetic base")
    _run_git(repository, "branch", "-M", "main")
    _run_git(
        repository,
        "update-ref",
        "refs/remotes/origin/main",
        _run_git(repository, "rev-parse", "HEAD"),
    )
    return repository


def _current_identity_authority(
    repository: Path,
) -> diagnostic.Invocation3ReplayDiagnosticAuthority:
    payload = _base_payload()
    implementation = payload["implementation"]
    head = _run_git(repository, "rev-parse", "HEAD")
    implementation.update(
        {
            "repository_root": str(repository),
            "head_commit": head,
            "local_main_commit": head,
            "local_origin_main_commit": head,
            "ordered_parents": _run_git(
                repository,
                "show",
                "-s",
                "--format=%P",
                "HEAD",
            ).split(),
            "tree": _run_git(repository, "rev-parse", "HEAD^{tree}"),
            "source_closure_sha256": diagnostic.source_closure_sha256(
                repository
            ),
        }
    )
    return _authority_object(payload)


def test_temporary_git_current_identity_accepts_exact_clean_main(
    tmp_path: Path,
) -> None:
    repository = _temporary_repository(tmp_path)
    authority = _current_identity_authority(repository)
    diagnostic._validate_current_source(authority, diagnostic.time.monotonic_ns() + diagnostic.HARD_TIMEOUT_NS)


@pytest.mark.parametrize(
    "mutation",
    (
        "wrong_head",
        "wrong_main",
        "wrong_origin",
        "wrong_parent",
        "wrong_tree",
        "wrong_closure",
        "dirty_worktree",
        "dirty_index",
        "untracked",
    ),
)
def test_temporary_git_current_identity_rejects_every_drift_class(
    tmp_path: Path,
    mutation: str,
) -> None:
    repository = _temporary_repository(tmp_path)
    authority = _current_identity_authority(repository)
    implementation = authority.payload["implementation"]
    if mutation == "wrong_head":
        _run_git(repository, "switch", "-q", "-c", "other")
    elif mutation == "wrong_main":
        _run_git(
            repository,
            "update-ref",
            "-d",
            "refs/heads/main",
        )
    elif mutation == "wrong_origin":
        _run_git(
            repository,
            "update-ref",
            "-d",
            "refs/remotes/origin/main",
        )
    elif mutation == "wrong_parent":
        implementation["ordered_parents"] = ["e" * 40]
    elif mutation == "wrong_tree":
        implementation["tree"] = "e" * 40
    elif mutation == "wrong_closure":
        implementation["source_closure_sha256"] = "e" * 64
    elif mutation == "dirty_worktree":
        target = repository / diagnostic.SOURCE_FILES[0]
        target.write_text("dirty\n", encoding="utf-8")
    elif mutation == "dirty_index":
        target = repository / diagnostic.SOURCE_FILES[0]
        target.write_text("staged\n", encoding="utf-8")
        _run_git(repository, "add", "--", str(target))
    else:
        (repository / "untracked.py").write_text(
            "shadow\n",
            encoding="utf-8",
        )
    with pytest.raises(diagnostic.Invocation3DiagnosticError):
        diagnostic._validate_current_source(authority, diagnostic.time.monotonic_ns() + diagnostic.HARD_TIMEOUT_NS)


def test_source_closure_binds_ordered_runtime_files_only(
    tmp_path: Path,
) -> None:
    repository = _temporary_repository(tmp_path)
    first = diagnostic.source_closure_sha256(repository)
    unrelated = repository / "README.synthetic"
    unrelated.write_text("outside closure\n", encoding="utf-8")
    assert diagnostic.source_closure_sha256(repository) == first
    runtime_file = repository / diagnostic.SOURCE_FILES[-1]
    runtime_file.write_text("changed runtime\n", encoding="utf-8")
    assert diagnostic.source_closure_sha256(repository) != first


def _metadata(root: Path) -> dict[str, object]:
    root_status = os.lstat(root)
    entries: list[list[object]] = [
        [
            ".",
            "d",
            root_status.st_dev,
            root_status.st_ino,
            root_status.st_uid,
            root_status.st_gid,
            f"{stat.S_IMODE(root_status.st_mode):04o}",
            root_status.st_nlink,
            root_status.st_size,
        ]
    ]
    directories = 1
    files = 0
    total = 0
    paths = sorted(
        root.rglob("*"),
        key=lambda item: item.relative_to(root).as_posix(),
    )
    for path in paths:
        status = os.lstat(path)
        relative = path.relative_to(root).as_posix()
        kind = (
            "d"
            if stat.S_ISDIR(status.st_mode)
            else "f"
            if stat.S_ISREG(status.st_mode)
            else "x"
        )
        entries.append(
            [
                relative,
                kind,
                status.st_dev,
                status.st_ino,
                status.st_uid,
                status.st_gid,
                f"{stat.S_IMODE(status.st_mode):04o}",
                status.st_nlink,
                status.st_size,
            ]
        )
        if kind == "d":
            directories += 1
        elif kind == "f":
            files += 1
            total += status.st_size
    return {
        "root_device": root_status.st_dev,
        "root_inode": root_status.st_ino,
        "uid": root_status.st_uid,
        "gid": root_status.st_gid,
        "directory_count": directories,
        "file_count": files,
        "total_file_bytes": total,
        "metadata_sha256": diagnostic._sha(
            diagnostic._canonical(
                [
                    diagnostic.STAGE_METADATA_PROTOCOL,
                    sorted(entries),
                ]
            )
        ),
    }


def _synthetic_stage(
    tmp_path: Path,
) -> tuple[
    Path,
    dict[str, bytes],
    diagnostic.Invocation3ReplayDiagnosticAuthority,
]:
    root = tmp_path / "stage"
    checkpoint = root / "EnglishMono/cpu/checkpoint-0750"
    checkpoint.mkdir(parents=True, mode=0o700)
    empty = root / "empty-directory"
    empty.mkdir(mode=0o700)
    files = {
        "CHECKPOINT_COMPLETE.json": b"completion\n",
        "inventory.json": b"transaction\n",
        "checkpoint_inventory.json": b"inventory\n",
        "checkpoint_manifest.json": b"manifest\n",
        "checkpoint_state.pt": b"state-bytes\n",
    }
    for name, content in files.items():
        path = checkpoint / name
        path.write_bytes(content)
        os.chmod(path, 0o600)
    for directory in (
        root,
        root / "EnglishMono",
        root / "EnglishMono/cpu",
        checkpoint,
        empty,
    ):
        os.chmod(directory, 0o700)
    payload = _base_payload()
    stage = payload["retained_stage"]
    stage["path"] = str(root)
    stage.update(_metadata(root))
    control_names = {
        "transaction_completion": "CHECKPOINT_COMPLETE.json",
        "transaction_inventory": "inventory.json",
        "checkpoint_inventory": "checkpoint_inventory.json",
        "checkpoint_manifest": "checkpoint_manifest.json",
    }
    for key, name in control_names.items():
        relative = f"EnglishMono/cpu/checkpoint-0750/{name}"
        content = files[name]
        stage["controls"][key] = {
            "relative_path": relative,
            "size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
    state = files["checkpoint_state.pt"]
    stage["checkpoint_state"] = {
        "relative_path": (
            "EnglishMono/cpu/checkpoint-0750/checkpoint_state.pt"
        ),
        "size": len(state),
        "sha256": hashlib.sha256(state).hexdigest(),
    }
    return root, files, _authority_object(payload)


def test_stage_metadata_accepts_exact_owner_private_topology(
    tmp_path: Path,
) -> None:
    _, _, authority = _synthetic_stage(tmp_path)
    snapshot = diagnostic._stage_snapshot(authority)
    stage = authority.payload["retained_stage"]
    assert snapshot.metadata_sha256 == stage["metadata_sha256"]
    assert snapshot.directory_count == stage["directory_count"]
    assert snapshot.file_count == stage["file_count"]
    assert snapshot.total_file_bytes == stage["total_file_bytes"]


@pytest.mark.parametrize(
    "mutation",
    (
        "replacement_inode",
        "empty_directory_rename",
        "file_count",
        "file_size",
        "file_mode",
        "hardlink",
        "symlink",
        "fifo",
        "unexpected_entry",
        "metadata_digest",
        "root_inode",
    ),
)
def test_stage_metadata_rejects_custody_and_topology_mutations(
    tmp_path: Path,
    mutation: str,
) -> None:
    root, _, authority = _synthetic_stage(tmp_path)
    checkpoint = root / "EnglishMono/cpu/checkpoint-0750"
    target = checkpoint / "checkpoint_manifest.json"
    if mutation == "replacement_inode":
        replacement = checkpoint / "replacement"
        replacement.write_bytes(target.read_bytes())
        os.chmod(replacement, 0o600)
        replacement.replace(target)
    elif mutation == "empty_directory_rename":
        (root / "empty-directory").rename(root / "renamed-empty")
    elif mutation == "file_count":
        target.unlink()
    elif mutation == "file_size":
        target.write_bytes(target.read_bytes() + b"x")
    elif mutation == "file_mode":
        os.chmod(target, 0o640)
    elif mutation == "hardlink":
        os.link(target, checkpoint / "linked")
    elif mutation == "symlink":
        (checkpoint / "linked").symlink_to(target)
    elif mutation == "fifo":
        os.mkfifo(checkpoint / "fifo", 0o600)
    elif mutation == "unexpected_entry":
        unexpected = checkpoint / "unexpected"
        unexpected.write_bytes(b"x")
        os.chmod(unexpected, 0o600)
    elif mutation == "metadata_digest":
        authority.payload["retained_stage"]["metadata_sha256"] = ZERO_SHA
    else:
        authority.payload["retained_stage"]["root_inode"] += 1
    with pytest.raises(diagnostic.Invocation3DiagnosticError):
        diagnostic._stage_snapshot(authority)


def test_stage_payload_requires_prior_snapshot_exact_inode_size_and_hash(
    tmp_path: Path,
) -> None:
    _, files, authority = _synthetic_stage(tmp_path)
    snapshot = diagnostic._stage_snapshot(authority)
    record = authority.payload["retained_stage"]["controls"][
        "checkpoint_manifest"
    ]
    content = diagnostic._read_stage_payload(
        authority,
        snapshot,
        record["relative_path"],
        record,
    )
    assert content == files["checkpoint_manifest.json"]
    path = Path(authority.payload["retained_stage"]["path"]) / record[
        "relative_path"
    ]
    replacement = path.with_suffix(".replacement")
    replacement.write_bytes(content)
    os.chmod(replacement, 0o600)
    replacement.replace(path)
    with pytest.raises(diagnostic.Invocation3DiagnosticError):
        diagnostic._read_stage_payload(
            authority,
            snapshot,
            record["relative_path"],
            record,
        )


def test_descriptor_reads_reject_intermediate_symlink_parent_substitution_and_final_symlink(tmp_path: Path) -> None:
    root, _, authority = _synthetic_stage(tmp_path)
    alias = tmp_path / "stage-alias"
    alias.symlink_to(root, target_is_directory=True)
    authority.payload["retained_stage"]["path"] = str(alias)
    with pytest.raises(diagnostic.Invocation3DiagnosticError):
        diagnostic._stage_snapshot(authority)
    authority.payload["retained_stage"]["path"] = str(root)
    displaced = tmp_path / "displaced-stage"
    root.rename(displaced)
    root.mkdir(mode=0o700)
    with pytest.raises(diagnostic.Invocation3DiagnosticError):
        diagnostic._stage_snapshot(authority)
    target = tmp_path / "target"
    target.write_bytes(b"bounded")
    link = tmp_path / "final-link"
    link.symlink_to(target)
    with pytest.raises(diagnostic.Invocation3DiagnosticError):
        diagnostic._stable_read(link, 32)


@pytest.mark.parametrize("relative", ("EnglishMono", "EnglishMono/cpu", "EnglishMono/cpu/checkpoint-0750"))
def test_stage_payload_rejects_replaced_intermediate_with_original_final_inode(tmp_path: Path, relative: str) -> None:
    root, _, authority = _synthetic_stage(tmp_path)
    snapshot = diagnostic._stage_snapshot(authority)
    record = authority.payload["retained_stage"]["controls"]["checkpoint_manifest"]
    target = root / relative
    displaced = tmp_path / f"accepted-{relative.replace('/', '-')}"
    target.rename(displaced)
    target.mkdir(mode=0o700)
    child = {"EnglishMono": "cpu", "EnglishMono/cpu": "checkpoint-0750"}.get(relative, "checkpoint_manifest.json")
    original = displaced / child
    original.rename(target / child)
    parent_relative = Path(relative).parent.as_posix()
    parent_relative = "." if parent_relative == "." else parent_relative
    accepted_parent = snapshot.directories[parent_relative]
    parent = target.parent
    os.utime(parent, ns=(os.lstat(parent).st_atime_ns, accepted_parent[-1]), follow_symlinks=False)
    assert tuple(getattr(os.lstat(parent), field) for field in diagnostic._IDENTITY_FIELDS) == accepted_parent
    accepted_inode = snapshot.files[record["relative_path"]][1]
    assert os.lstat(root / record["relative_path"]).st_ino == accepted_inode
    with pytest.raises(diagnostic.Invocation3DiagnosticError):
        diagnostic._read_stage_payload(authority, snapshot, record["relative_path"], record)


def test_diagnostic_and_embedded_historical_types_cannot_enter_production(
    tmp_path: Path,
) -> None:
    _, _, _, _, historical, _ = legacy._authority(tmp_path)
    object.__setattr__(
        historical,
        "_factory_token",
        diagnostic._HISTORICAL_TOKEN,
    )
    authority = _authority_object(_base_payload())
    wrapper = object.__new__(
        diagnostic.Invocation3ReplayDiagnosticAuthorization
    )
    object.__setattr__(wrapper, "authority", authority)
    object.__setattr__(
        wrapper,
        "historical_authorization_sha256",
        ZERO_SHA,
    )
    object.__setattr__(
        wrapper,
        "one_shot_attempt_id",
        authority.one_shot_attempt_id,
    )
    object.__setattr__(wrapper, "_historical_authorization", historical)
    object.__setattr__(
        wrapper,
        "_factory_token",
        diagnostic._DIAGNOSTIC_TOKEN,
    )
    with pytest.raises(
        smoke.SmokeTrainingError,
        match=smoke.SMOKE_APPROVAL_MISMATCH,
    ):
        smoke.execute_bounded_tiny_smoke(wrapper)
    with pytest.raises(
        smoke.SmokeTrainingError,
        match=smoke.SMOKE_APPROVAL_MISMATCH,
    ):
        smoke.execute_bounded_tiny_smoke(historical)


def _exercise_real_shared_reanchor_transaction_and_envelope(tmp_path: Path) -> bytes:
    *_, authorization, optimizers, runtime = legacy._runtime(
        tmp_path,
        test_updates=751,
    )
    smoke.prime_synthetic_runtime_to_checkpoint_for_tests(runtime, 750)
    envelope = smoke.checkpoint_envelope_for_runtime(runtime)
    anchored = smoke._reanchor_consumed_view(
        authorization,
        condition="EnglishMono",
        code=smoke.SMOKE_RESUME_MISMATCH,
    )
    assert anchored.condition == "EnglishMono"
    files = dict(envelope._files)
    replay_files = {
        **files,
        "artifact_transaction_completion.json": files[
            "CHECKPOINT_COMPLETE.json"
        ],
        "artifact_transaction_inventory.json": files["inventory.json"],
    }
    request = {
        "artifact_completion_sha256": hashlib.sha256(
            files["CHECKPOINT_COMPLETE.json"]
        ).hexdigest(),
        "artifact_inventory_sha256": hashlib.sha256(
            files["inventory.json"]
        ).hexdigest(),
        "authorization_sha256": authorization.authorization_sha256,
        "candidate_checksum_record_sha256": (
            authorization.approval.candidate_checksum_record_sha256
        ),
        "checkpoint_inventory_sha256": hashlib.sha256(
            files["checkpoint_inventory.json"]
        ).hexdigest(),
        "launch_manifest_sha256": (
            authorization.launch_manifest.manifest_sha256
        ),
        "sanitized_view_sha256": authorization.training_view_sha256,
    }
    smoke._verify_replay_transaction(request, replay_files)
    historical_token = object()
    rebuilt = smoke._checkpoint_envelope_from_files_for_tests_impl(
        files,
        envelope.envelope_sha256,
        token=historical_token,
    )
    checkpoint_bytes = smoke._verify_checkpoint_envelope(
        authorization,
        "EnglishMono",
        rebuilt,
        750,
        token=historical_token,
    )
    assert checkpoint_bytes == files["checkpoint_state.pt"]
    return checkpoint_bytes


def test_real_shared_reanchor_transaction_and_envelope_accept_exact_lineage(tmp_path: Path) -> None:
    assert _exercise_real_shared_reanchor_transaction_and_envelope(tmp_path)


@pytest.mark.parametrize("mutation", ("valid", "wrong_tracker_mode", "wrong_manifest_mode", "manifest_tracker_bytes", "manifest_other_launch"))
def test_real_production_mode_loader_and_reanchor_use_file_specific_custody(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str) -> None:
    view, paired, tracker, manifest = legacy._production_condition_runtime_material(tmp_path)
    output = tmp_path / "synthetic-output"
    output.mkdir(mode=0o700)
    commit, closure, runtime = "a" * 40, "b" * 64, smoke._runtime_policy_sha256()
    launch_bytes = smoke.canonical_json_bytes(smoke._production_launch_payload(view, authority_kind="production_tracker_and_launch", executor_commit=commit, executor_closure_digest=closure, output_parent=output))
    tracker_bytes = smoke._updated_tracker_text_for_tests(heading="# Synthetic production-mode historical tracker", authority_kind="production_tracker_and_launch", candidate_checksum=view.candidate_checksum_record_sha256, preparation_manifest=view.preparation_manifest_sha256, schedule_identity=view.schedule_plan_identity_sha256, launch_manifest_sha256=hashlib.sha256(launch_bytes).hexdigest(), executor_commit=commit, executor_closure_digest=closure, runtime_policy_sha256=runtime, output_parent=output)
    tracker.write_bytes(tracker_bytes)
    manifest.write_bytes(launch_bytes)
    os.chmod(tracker, 0o644)
    os.chmod(manifest, 0o600)
    monkeypatch.setattr(smoke, "APPROVED_TRACKER_PATH", tracker.absolute())
    monkeypatch.setattr(smoke, "APPROVED_LAUNCH_MANIFEST_PATH", manifest.absolute())
    if mutation == "wrong_tracker_mode":
        os.chmod(tracker, 0o600)
    elif mutation == "wrong_manifest_mode":
        os.chmod(manifest, 0o644)
    elif mutation == "manifest_tracker_bytes":
        manifest.write_bytes(tracker_bytes)
    elif mutation == "manifest_other_launch":
        other = json.loads(launch_bytes)
        other["reporting_policy"] = "different_canonical_launch"
        manifest.write_bytes(smoke.canonical_json_bytes(other))
    calls: list[str] = []
    for name in ("_load_future_tracker_approval", "_validate_launch_before_candidate_load", "_construct_bound_production_authorization", "_reanchor_consumed_view", "_verify_replay_transaction", "_checkpoint_envelope_from_files_for_tests_impl", "_verify_checkpoint_envelope"):
        original = getattr(smoke, name)
        def wrapped(*args, _name=name, _original=original, **kwargs):
            calls.append(_name)
            return _original(*args, **kwargs)
        monkeypatch.setattr(smoke, name, wrapped)
    token = object()
    load_kwargs = {"candidate_checksum": view.candidate_checksum_record_sha256, "preparation_manifest": view.preparation_manifest_sha256, "schedule_identity": view.schedule_plan_identity_sha256, "executor_commit": commit, "executor_closure_digest": closure, "runtime_policy_sha256": runtime, "output_parent": output, "authority_kind": "production_tracker_and_launch", "production": True, "token": token}
    if mutation == "wrong_tracker_mode":
        with pytest.raises(smoke.SmokeTrainingError, match=smoke.SMOKE_APPROVAL_MISMATCH):
            smoke._load_future_tracker_approval(tracker.absolute(), **load_kwargs)
        assert calls == ["_load_future_tracker_approval"]
        return
    approval = smoke._load_future_tracker_approval(tracker.absolute(), **load_kwargs)
    launch_kwargs = {"authority_kind": "production_tracker_and_launch", "executor_commit": commit, "executor_closure_digest": closure, "runtime_policy_sha256": runtime, "output_parent": output, "production": True, "token": token}
    if mutation != "valid":
        with pytest.raises(smoke.SmokeTrainingError, match=smoke.SMOKE_APPROVAL_MISMATCH):
            smoke._validate_launch_before_candidate_load(approval, manifest.absolute(), **launch_kwargs)
        assert calls == ["_load_future_tracker_approval", "_validate_launch_before_candidate_load"]
        return
    launch = smoke._validate_launch_before_candidate_load(approval, manifest.absolute(), **launch_kwargs)
    authorization = smoke._construct_bound_production_authorization(approval, launch, view, paired, authority_kind="production_tracker_and_launch", required_view_kind="synthetic_test_only", output_parent=output, token=token)
    assert smoke._reanchor_consumed_view(authorization, code=smoke.SMOKE_APPROVAL_MISMATCH) is None
    shared = tmp_path / "shared-validation"
    shared.mkdir()
    assert _exercise_real_shared_reanchor_transaction_and_envelope(shared)
    for name in ("_load_future_tracker_approval", "_validate_launch_before_candidate_load", "_construct_bound_production_authorization", "_reanchor_consumed_view", "_verify_replay_transaction", "_checkpoint_envelope_from_files_for_tests_impl", "_verify_checkpoint_envelope"):
        assert name in calls


def test_real_reanchor_rejects_view_substitution_before_decode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    *_, authorization, optimizers, runtime = legacy._runtime(
        tmp_path,
        test_updates=751,
    )
    smoke.prime_synthetic_runtime_to_checkpoint_for_tests(runtime, 750)
    envelope = smoke.checkpoint_envelope_for_runtime(runtime)
    object.__setattr__(authorization._training_view, "semantic_sha256", ZERO_SHA)
    monkeypatch.setattr(
        smoke.torch,
        "load",
        lambda *args, **kwargs: pytest.fail(
            "decode reached after crossed lineage"
        ),
    )
    with pytest.raises(
        smoke.SmokeTrainingError,
        match=smoke.SMOKE_RESUME_MISMATCH,
    ):
        smoke._verify_checkpoint_envelope(
            authorization,
            "EnglishMono",
            envelope,
            750,
            token=runtime._factory_token,
        )


def test_every_torch_load_is_literal_weights_only_true() -> None:
    repository = Path(smoke.__file__).resolve().parents[3]
    calls: list[tuple[Path, ast.Call]] = []
    for path in repository.rglob("*.py"):
        if any(
            part in {".git", ".venv", "outputs"}
            for part in path.parts
        ):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "torch"
                and node.func.attr == "load"
            ):
                calls.append((path, node))
    assert len(calls) >= 1
    assert sum(path == Path(smoke.__file__).resolve() for path, _ in calls) == 1
    for _, call in calls:
        keyword = next(
            item
            for item in call.keywords
            if item.arg == "weights_only"
        )
        assert isinstance(keyword.value, ast.Constant)
        assert keyword.value.value is True


def test_checkpoint_restore_runtime_passes_literal_weights_only_true(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    *_, authorization, optimizers, runtime = legacy._runtime(tmp_path)
    envelope = smoke.checkpoint_envelope_for_runtime(runtime)
    original = smoke.torch.load
    calls: list[object] = []

    def spy(*args, **kwargs):
        calls.append(kwargs.get("weights_only"))
        return original(*args, **kwargs)

    monkeypatch.setattr(smoke.torch, "load", spy)
    smoke.restore_synthetic_runtime_from_checkpoint(
        authorization, optimizers, "EnglishMono", envelope,
        expected_completed_update=0,
    )
    assert calls == [True]


def _shared_replay_mocks(
    monkeypatch: pytest.MonkeyPatch,
) -> SimpleNamespace:
    runtime = SimpleNamespace(completed_update=750)
    monkeypatch.setattr(
        smoke,
        "_verify_checkpoint_envelope",
        lambda *args, **kwargs: b"state",
    )
    monkeypatch.setattr(
        smoke,
        "_create_optimizer_set_impl",
        lambda *args, **kwargs: object(),
    )
    monkeypatch.setattr(
        smoke,
        "_restore_runtime_from_checkpoint_impl",
        lambda *args, **kwargs: runtime,
    )
    monkeypatch.setattr(
        smoke,
        "_execute_next_update_impl",
        lambda value, **kwargs: setattr(
            value,
            "completed_update",
            value.completed_update + 1,
        ),
    )
    monkeypatch.setattr(
        smoke,
        "_validate_condition_impl",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        smoke,
        "_runtime_replay_comparison",
        lambda runtime: {},
    )
    monkeypatch.setattr(
        smoke,
        "_replay_result_bytes",
        lambda request, comparison: b"result\n",
    )
    return runtime


def test_shared_replay_guard_detects_parent_loss_after_selected_update(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _shared_replay_mocks(monkeypatch)

    def guard() -> None:
        if runtime.completed_update == 755:
            raise diagnostic.Invocation3DiagnosticError()

    with pytest.raises(diagnostic.Invocation3DiagnosticError):
        smoke._execute_verified_replay(
            object(),
            object(),
            {},
            token=object(),
            diagnostic_sink=None,
            guard=guard,
        )


def test_shared_replay_guard_detects_parent_loss_during_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _shared_replay_mocks(monkeypatch)
    validating = {"active": False}

    def validate(*args, **kwargs):
        validating["active"] = True

    def guard() -> None:
        if validating["active"]:
            raise diagnostic.Invocation3DiagnosticError()

    monkeypatch.setattr(smoke, "_validate_condition_impl", validate)
    with pytest.raises(diagnostic.Invocation3DiagnosticError):
        smoke._execute_verified_replay(
            object(),
            object(),
            {},
            token=object(),
            diagnostic_sink=None,
            guard=guard,
        )


def test_shared_replay_exact_updates_validations_and_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _shared_replay_mocks(monkeypatch)
    phases: list[tuple[str, int | None]] = []
    result = smoke._execute_verified_replay(
        object(),
        object(),
        {},
        token=object(),
        diagnostic_sink=(
            lambda phase, update: phases.append((phase, update))
        ),
        guard=lambda: None,
    )
    assert result == b"result\n"
    assert runtime.completed_update == 1_000
    assert phases == [
        ("ENVELOPE_VERIFIED_PREDECODE", None),
        ("CHECKPOINT_RESTORED", None),
        ("REPLAY_STARTED", None),
        ("UPDATE_751_COMPLETED", 751),
        ("VALIDATION_800_COMPLETED", 800),
        ("VALIDATION_900_COMPLETED", 900),
        ("UPDATE_1000_COMPLETED", 1_000),
        ("VALIDATION_1000_COMPLETED", 1_000),
        ("RESULT_ENCODED", None),
    ]


@pytest.mark.parametrize(("boundary", "offset", "expected"), (("observation", -1, (False, False)), ("observation", 0, (True, False)), ("observation", 1, (True, False)), ("hard", -1, (True, False)), ("hard", 0, (True, True)), ("hard", 1, (True, True))))
def test_deadline_boundaries_use_integer_nanoseconds_and_greater_equal(boundary: str, offset: int, expected: tuple[bool, bool]) -> None:
    observation = 10_000
    hard = 20_000
    assert diagnostic._deadline_state((observation if boundary == "observation" else hard) + offset, observation, hard) == expected


@pytest.mark.parametrize("helper", ("git", "process_snapshot"))
@pytest.mark.parametrize(("case", "clock", "code"), (("success", (999, 999), None), ("nonzero", (999, 999), "INVOCATION3_DIAGNOSTIC_REJECTED"), ("early_timeout", (998, 999), "INVOCATION3_DIAGNOSTIC_REJECTED"), ("deadline_timeout", (999, 1_000), "HARD_TIMEOUT"), ("progressed", (999, 1_000), "HARD_TIMEOUT"), ("exact", (1_000,), "HARD_TIMEOUT")))
def test_admission_helpers_are_bound_to_remaining_hard_deadline(monkeypatch: pytest.MonkeyPatch, helper: str, case: str, clock: tuple[int, ...], code: str | None) -> None:
    ticks, calls = iter(clock), []
    monkeypatch.setattr(diagnostic.time, "monotonic_ns", lambda: next(ticks))
    def run(arguments, **kwargs):
        calls.append((arguments, kwargs))
        if "timeout" in case:
            raise subprocess.TimeoutExpired(arguments, kwargs["timeout"], output=b"private", stderr=b"private")
        stdout = b"synthetic\n" if helper == "git" else f"{os.getpid()} {diagnostic.CONTROLLER_ARGUMENT}\n".encode()
        return SimpleNamespace(returncode=2 if case == "nonzero" else 0, stdout=stdout)
    monkeypatch.setattr(diagnostic.subprocess, "run", run)
    def invoke():
        return diagnostic._git(Path("/synthetic"), "status", hard=1_000) if helper == "git" else diagnostic._process_snapshot(worker=False, hard=1_000)
    if code is None:
        result = invoke()
        assert result == "synthetic\n" if helper == "git" else result[1:] == (1, 0)
    else:
        with pytest.raises(diagnostic.Invocation3DiagnosticError) as caught:
            invoke()
        assert caught.value.code == code and str(caught.value) == code
    if case == "exact":
        assert not calls
    else:
        timeout, remaining = calls[0][1]["timeout"], 1_000 - clock[0]
        assert calls[0][0][0] == ("/usr/bin/git" if helper == "git" else "/bin/ps") and timeout > 0 and Fraction.from_float(timeout) <= Fraction(remaining, 1_000_000_000)


def test_admission_timeout_conversion_never_exceeds_exact_rational_remainder(monkeypatch: pytest.MonkeyPatch) -> None:
    remaining_values = (1, 2, 999_999_999, 1_000_000_000, 1_000_000_001, 3_599_999_999_999, 3_600_000_000_000)
    timeouts: list[float] = []
    monkeypatch.setattr(diagnostic.time, "monotonic_ns", lambda: 0)
    monkeypatch.setattr(diagnostic.subprocess, "run", lambda *args, timeout, **kwargs: timeouts.append(timeout) or SimpleNamespace(returncode=0, stdout=b""))
    for remaining in remaining_values:
        diagnostic._admission_process(("/synthetic",), remaining)
    assert all(timeout > 0 and Fraction.from_float(timeout) <= Fraction(remaining, 1_000_000_000) for remaining, timeout in zip(remaining_values, timeouts, strict=True))


def test_worker_guard_rejects_parent_loss_and_exact_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = {
        "parent_pid": 123,
        "hard_deadline_monotonic_ns": 1_000,
    }
    monkeypatch.setattr(diagnostic.os, "getppid", lambda: 123)
    monkeypatch.setattr(
        diagnostic.time,
        "monotonic_ns",
        lambda: 999,
    )
    diagnostic._guard(request)
    monkeypatch.setattr(
        diagnostic.time,
        "monotonic_ns",
        lambda: 1_000,
    )
    with pytest.raises(diagnostic.Invocation3DiagnosticError):
        diagnostic._guard(request)
    monkeypatch.setattr(diagnostic.time, "monotonic_ns", lambda: 999)
    monkeypatch.setattr(diagnostic.os, "getppid", lambda: 124)
    with pytest.raises(diagnostic.Invocation3DiagnosticError):
        diagnostic._guard(request)


def test_worker_passes_authenticated_deadline_to_both_admission_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    authority, started = _authority_object(_base_payload()), 100
    hard, workspace = started + diagnostic.HARD_TIMEOUT_NS, Path("/private/tmp/neu-invocation3-replay-0123456789abcdef0123456789abcdef")
    request = {"authority_file_sha256": authority.authority_file_sha256, "authority_semantic_sha256": authority.authority_semantic_sha256, "one_shot_attempt_id": authority.one_shot_attempt_id, "workspace_path": str(workspace), "observation_boundary_monotonic_ns": started + diagnostic.OBSERVATION_NS, "attempt_started_monotonic_ns": started, "hard_deadline_monotonic_ns": hard, "relevant_process_count": 1, "other_replay_worker_count": 0, "request_source_closure_sha256": authority.payload["implementation"]["source_closure_sha256"], "interpreter_sha256": authority.payload["command"]["interpreter"]["sha256"], "parent_pid": 42}
    deadlines: list[int] = []
    monkeypatch.setattr(diagnostic, "_stable_read", lambda *args, **kwargs: (b"request", None))
    monkeypatch.setattr(diagnostic, "_parse_request", lambda *args: request)
    monkeypatch.setattr(diagnostic, "load_authority", lambda *args: authority)
    monkeypatch.setattr(diagnostic.os, "getppid", lambda: 42)
    monkeypatch.setattr(diagnostic.time, "monotonic_ns", lambda: hard - 1)
    monkeypatch.setattr(diagnostic, "bootstrap_runtime", lambda *args, hard, **kwargs: deadlines.append(hard) or object())
    monkeypatch.setattr(diagnostic, "_process_snapshot", lambda *, worker, hard: deadlines.append(hard) or ("a" * 64, 2, 0))
    monkeypatch.setattr(diagnostic, "_worker_replay", lambda *args: b"result\n")
    assert diagnostic.run_worker(workspace / "request.json", "e" * 64, "f" * 64, controller_script=Path("/synthetic/run.py"), argv=(), sink=lambda *args: None) == b"result\n"
    assert deadlines == [hard, hard]


def test_bounded_simultaneous_stdout_stderr_floods_do_not_deadlock() -> None:
    program = (
        "import sys,threading;"
        "a=threading.Thread("
        "target=lambda:sys.stdout.buffer.write(b'x'*200000));"
        "b=threading.Thread("
        "target=lambda:sys.stderr.buffer.write(b'y'*220000));"
        "a.start();b.start();a.join();b.join()"
    )
    process = subprocess.Popen(
        (sys.executable, "-c", program),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    now = diagnostic.time.monotonic_ns()
    result = diagnostic._drain_process(
        process,
        now + 10_000_000_000,
        now + 20_000_000_000,
    )
    assert result["returncode"] == 0
    assert result["stdout_bytes"] == 200_000
    assert result["stderr_bytes"] == 220_000
    assert len(result["stdout"]) == diagnostic.STDOUT_LIMIT + 1
    assert len(result["stderr"]) == diagnostic.STDERR_LIMIT + 1
    assert result["stdout_sha256"] == hashlib.sha256(
        b"x" * 200_000
    ).hexdigest()
    assert result["stderr_sha256"] == hashlib.sha256(
        b"y" * 220_000
    ).hexdigest()


def test_early_channel_eof_child_is_killed_and_reaped_at_hard_deadline() -> None:
    process = subprocess.Popen(
        (sys.executable, "-c", "import os,time;os.close(1);os.close(2);time.sleep(2)"),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    started = diagnostic.time.monotonic_ns()
    result = diagnostic._drain_process(
        process,
        started + 50_000_000,
        started + 100_000_000,
    )
    assert result["hard_timeout"] is True and result["returncode"] < 0 and process.poll() is not None
    assert process.stdout.closed and process.stderr.closed
    assert diagnostic.time.monotonic_ns() - started < 1_500_000_000


def test_continuous_inherited_writer_forces_timeout_without_descendant_signal() -> None:
    writer = "import os\ntry:\n while True: os.write(1,b'x'*4096)\nexcept BrokenPipeError: pass"
    program = f"import subprocess,sys;subprocess.Popen((sys.executable,'-c',{writer!r}))"
    process = subprocess.Popen((sys.executable, "-c", program), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert process.wait(timeout=2) == 0 and select.select([process.stdout], [], [], 2)[0]
    killed, ticks = [], iter(range(100))
    original_kill = process.kill
    def kill():
        killed.append(True)
        original_kill()
    process.kill = kill
    result = diagnostic._drain_process(process, 5, 10, clock=lambda: next(ticks))
    assert result["returncode"] == 0 and result["hard_timeout"] is True
    assert result["stdout_bytes"] > 0 and killed == []
    assert process.stdout.closed and process.stderr.closed


@pytest.mark.parametrize(("offset", "hard_timeout", "killed", "stdout"), ((-1, False, False, b"apparent-result"), (0, True, True, b""), (1, True, True, b"")))
def test_direct_child_deadline_precedence_kills_and_reaps(offset: int, hard_timeout: bool, killed: bool, stdout: bytes) -> None:
    stdout_read, stdout_write = os.pipe()
    stderr_read, stderr_write = os.pipe()
    os.write(stdout_write, b"apparent-result")
    os.close(stdout_write)
    os.close(stderr_write)

    class Child:
        stdout = os.fdopen(stdout_read, "rb", buffering=0)
        stderr = os.fdopen(stderr_read, "rb", buffering=0)
        returncode = None
        killed = waited = False

        def poll(self):
            if offset < 0:
                self.returncode = 0
            return self.returncode

        def kill(self):
            self.killed, self.returncode = True, -9

        def wait(self, timeout):
            assert 0 < timeout <= 1.0
            self.waited = True
            return self.returncode

    child = Child()
    result = diagnostic._drain_process(child, 50, 100, clock=lambda: 100 + offset)
    assert result["hard_timeout"] is hard_timeout
    assert child.killed is killed and child.waited is killed
    assert result["stdout"] == stdout


def test_child_exit_observation_resamples_exact_hard_boundary_before_drain() -> None:
    stdout_read, stdout_write = os.pipe()
    stderr_read, stderr_write = os.pipe()
    os.write(stdout_write, b"buffered-result")
    os.close(stdout_write)
    os.close(stderr_write)
    class ExitedChild:
        stdout, stderr, returncode, killed = os.fdopen(stdout_read, "rb", buffering=0), os.fdopen(stderr_read, "rb", buffering=0), None, False
        def poll(self):
            self.returncode = 0
            return 0
        def kill(self):
            self.killed = True
        def wait(self, timeout):
            pytest.fail(f"reap wait reached for already exited child: {timeout}")
    times = iter((99, 100))
    child = ExitedChild()
    result = diagnostic._drain_process(child, 50, 100, clock=lambda: next(times))
    assert result["hard_timeout"] is True and result["returncode"] == 0
    assert result["stdout"] == b"" and child.killed is False


@pytest.mark.parametrize("failure", ("partial_write", "file_fsync", "publish", "directory_fsync"))
def test_failed_completion_publication_leaves_no_acceptable_final(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(mode=0o700)
    os.chown(workspace, 501, 20)
    unrelated = workspace / "unrelated"
    unrelated.write_bytes(b"preserve")
    real_write, real_fsync = diagnostic.os.write, diagnostic.os.fsync
    calls = [0]
    if failure == "partial_write":
        def broken_write(descriptor, content):
            calls[0] += 1
            return real_write(descriptor, content[:1]) if calls[0] == 1 else 0
        monkeypatch.setattr(diagnostic.os, "write", broken_write)
    elif failure in {"file_fsync", "directory_fsync"}:
        def broken_fsync(descriptor):
            calls[0] += 1
            if calls[0] == (1 if failure == "file_fsync" else 2):
                raise OSError
            return real_fsync(descriptor)
        monkeypatch.setattr(diagnostic.os, "fsync", broken_fsync)
    else:
        monkeypatch.setattr(diagnostic.os, "link", lambda *args, **kwargs: (_ for _ in ()).throw(OSError()))
    with pytest.raises(diagnostic.Invocation3DiagnosticError) as caught:
        diagnostic._publish_completion(workspace, b'{"complete":true}\n')
    assert caught.value.code == "INVOCATION3_DIAGNOSTIC_REJECTED"
    assert not (workspace / "completion.json").exists()
    assert not (workspace / ".completion.json.pending").exists()
    assert unrelated.read_bytes() == b"preserve"


def test_completion_removal_failure_is_indeterminate_and_preserves_exact_final(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(mode=0o700)
    os.chown(workspace, 501, 20)
    real_fsync, real_unlink, calls = diagnostic.os.fsync, diagnostic.os.unlink, [0]
    def fail_publish_fsync(descriptor):
        calls[0] += 1
        if calls[0] == 2:
            raise OSError
        return real_fsync(descriptor)
    def fail_final_unlink(name, *args, **kwargs):
        if name == "completion.json":
            raise OSError
        return real_unlink(name, *args, **kwargs)
    monkeypatch.setattr(diagnostic.os, "fsync", fail_publish_fsync)
    monkeypatch.setattr(diagnostic.os, "unlink", fail_final_unlink)
    with pytest.raises(diagnostic.Invocation3DiagnosticError) as caught:
        diagnostic._publish_completion(workspace, b'{"complete":true}\n')
    assert caught.value.code == diagnostic.INVOCATION3_EVIDENCE_INDETERMINATE
    assert (workspace / "completion.json").exists()


def test_completion_cleanup_second_directory_fsync_failure_is_indeterminate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(mode=0o700)
    os.chown(workspace, 501, 20)
    real_fsync, calls = diagnostic.os.fsync, [0]
    def fail_both_directory_fsyncs(descriptor):
        calls[0] += 1
        if calls[0] in {2, 3}:
            raise OSError
        return real_fsync(descriptor)
    monkeypatch.setattr(diagnostic.os, "fsync", fail_both_directory_fsyncs)
    with pytest.raises(diagnostic.Invocation3DiagnosticError) as caught:
        diagnostic._publish_completion(workspace, b'{"complete":true}\n')
    assert caught.value.code == diagnostic.INVOCATION3_EVIDENCE_INDETERMINATE
    assert not (workspace / "completion.json").exists()


def test_postpublication_identity_failure_does_not_remove_substituted_final(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(mode=0o700)
    os.chown(workspace, 501, 20)
    foreign = workspace / "foreign"
    foreign.write_bytes(b"foreign-record\n")
    os.chmod(foreign, 0o600)
    os.chown(foreign, 501, 20)
    real_open, swapped = diagnostic.os.open, [False]
    def substitute_before_final_open(name, flags, *args, **kwargs):
        if name == "completion.json" and not swapped[0]:
            swapped[0] = True
            (workspace / "completion.json").rename(workspace / "displaced-created-record")
            foreign.rename(workspace / "completion.json")
        return real_open(name, flags, *args, **kwargs)
    monkeypatch.setattr(diagnostic.os, "open", substitute_before_final_open)
    with pytest.raises(diagnostic.Invocation3DiagnosticError) as caught:
        diagnostic._publish_completion(workspace, b'{"complete":true}\n')
    assert caught.value.code == diagnostic.INVOCATION3_EVIDENCE_INDETERMINATE
    assert (workspace / "completion.json").read_bytes() == b"foreign-record\n"


def test_completion_is_private_canonical_and_published_last(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(mode=0o700)
    os.chown(workspace, 501, 20)
    content, events = diagnostic._canonical({"complete": True}), []
    real_link, real_fsync = diagnostic.os.link, diagnostic.os.fsync
    def observed_link(*args, **kwargs):
        assert not (workspace / "completion.json").exists()
        events.append("publish")
        return real_link(*args, **kwargs)
    def observed_fsync(descriptor):
        events.append("directory_fsync" if stat.S_ISDIR(os.fstat(descriptor).st_mode) else "file_fsync")
        return real_fsync(descriptor)
    monkeypatch.setattr(diagnostic.os, "link", observed_link)
    monkeypatch.setattr(diagnostic.os, "fsync", observed_fsync)
    diagnostic._publish_completion(workspace, content)
    status = os.lstat(workspace / "completion.json")
    assert events == ["file_fsync", "publish", "directory_fsync"]
    assert stat.S_ISREG(status.st_mode) and stat.S_IMODE(status.st_mode) == 0o600 and status.st_nlink == 1
    assert (workspace / "completion.json").read_bytes() == content


@pytest.mark.parametrize("publication", ("success", "indeterminate"))
def test_controller_spawns_once_kills_reaps_and_preserves_indeterminate_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    publication: str,
) -> None:
    authority = _authority_object(_base_payload())
    stage = diagnostic._StageSnapshot("7" * 64, 1, 2, 1, 0, 0, MappingProxyType({".": (1,) * 8}), MappingProxyType({}))
    workspace = tmp_path / "preserved-attempt"
    workspace.mkdir(mode=0o700)
    os.chown(workspace, 501, 20)
    children: list[object] = []
    deadlines: list[int] = []

    class Child:
        returncode = None

        def poll(self):
            return self.returncode

        def kill(self):
            self.returncode = -9

        def wait(self, timeout):
            assert timeout == 1.0
            self.waited = True
            return self.returncode

    def popen(*args, **kwargs):
        del args, kwargs
        child = Child()
        children.append(child)
        return child

    monkeypatch.setattr(diagnostic, "load_authority", lambda *args: authority)
    monkeypatch.setattr(diagnostic.time, "monotonic_ns", lambda: 100)
    monkeypatch.setattr(diagnostic, "bootstrap_runtime", lambda *args, hard, **kwargs: deadlines.append(hard) or object())
    monkeypatch.setattr(diagnostic, "_process_snapshot", lambda *, worker, hard: deadlines.append(hard) or ("a" * 64, 1, 0))
    monkeypatch.setattr(diagnostic, "_stage_snapshot", lambda value: stage)
    monkeypatch.setattr(diagnostic, "_workspace", lambda value: workspace)
    monkeypatch.setattr(diagnostic, "_validate_current_source", lambda value, hard: deadlines.append(hard))
    monkeypatch.setattr(diagnostic.subprocess, "Popen", popen)
    monkeypatch.setattr(diagnostic, "_drain_process", lambda *args, **kwargs: diagnostic._reject())
    if publication == "indeterminate":
        monkeypatch.setattr(diagnostic, "_publish_completion", lambda *args: (_ for _ in ()).throw(diagnostic.Invocation3DiagnosticError(diagnostic.INVOCATION3_EVIDENCE_INDETERMINATE)))
        with pytest.raises(diagnostic.Invocation3DiagnosticError) as caught:
            diagnostic.run_controller("f" * 64, controller_script=tmp_path / "run.py", argv=())
        assert caught.value.code == diagnostic.INVOCATION3_EVIDENCE_INDETERMINATE
    else:
        result = diagnostic.run_controller("f" * 64, controller_script=tmp_path / "run.py", argv=())
        assert result["diagnostic_disposition"] == "CONTROLLER_REJECTED"
        assert sorted(path.name for path in workspace.iterdir()) == ["completion.json", "events.jsonl", "request.json"]
    assert len(children) == 1 and children[0].returncode == -9 and children[0].waited
    assert deadlines == [100 + diagnostic.HARD_TIMEOUT_NS] * 3


def test_exact_cli_preserves_only_indeterminate_diagnostic_code_without_private_context(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    script = Path(smoke.__file__).resolve().parents[3] / "scripts/run_bounded_tiny_smoke.py"
    spec = importlib.util.spec_from_file_location("indeterminate_diagnostic_cli", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    private = "/private/tmp/neu-invocation3-replay-private-marker"
    def fail(*args, **kwargs):
        try:
            raise RuntimeError(private)
        except RuntimeError as context:
            raise diagnostic.Invocation3DiagnosticError(diagnostic.INVOCATION3_EVIDENCE_INDETERMINATE) from context
    monkeypatch.setattr(module.invocation3, "run_controller", fail)
    arguments = (diagnostic.CONTROLLER_ARGUMENT, diagnostic.AUTHORITY_SHA_ARGUMENT, "f" * 64, diagnostic.ATTESTATION_ARGUMENT)
    assert module.main(arguments) == 3
    stderr = capsys.readouterr().err
    assert json.loads(stderr) == {"code": diagnostic.INVOCATION3_EVIDENCE_INDETERMINATE, "diagnostic_only": True, "executed": False, "mechanics_only": True, "production_completion": False, "status": "replay_diagnostic_evidence_indeterminate"}
    assert private not in stderr and "RuntimeError" not in stderr
    monkeypatch.setattr(module.invocation3, "run_controller", lambda *args, **kwargs: (_ for _ in ()).throw(diagnostic.Invocation3DiagnosticError()))
    assert module.main(arguments) == 3
    assert json.loads(capsys.readouterr().err)["code"] == "SMOKE_RESUME_MISMATCH"


def _bootstrap_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = tmp_path / "runtime"
    root.mkdir()
    interpreter = root / "python"
    interpreter.write_bytes(b"interpreter")
    os.chmod(interpreter, 0o755)
    script, smoke_path, artifact_path = root / "run.py", root / "smoke.py", root / "artifacts.py"
    for path in (script, smoke_path, artifact_path):
        path.write_text("# synthetic\n")
    payload = _base_payload()
    command, origins = payload["command"], payload["implementation"]["origins"]
    command["working_directory"] = str(root)
    command["python_path"] = [str(root / f"path-{index}") for index in range(5)]
    for path in command["python_path"]:
        Path(path).mkdir()
    for name, package in command["packages"].items():
        package_root = root / "packages" / name
        package_root.mkdir(parents=True)
        package["root"] = str(package_root)
    command["interpreter"].update({"public_path": str(interpreter), "resolved_path": str(interpreter), "sha256": hashlib.sha256(interpreter.read_bytes()).hexdigest(), "size": interpreter.stat().st_size, "uid": interpreter.stat().st_uid, "gid": interpreter.stat().st_gid, "link_count": 1, "python_version": "synthetic"})
    origins.update({"controller_script": str(script), "diagnostic_module": str(Path(diagnostic.__file__).resolve()), "smoke_training_module": str(smoke_path), "smoke_artifacts_module": str(artifact_path)})
    argv = [str(interpreter), "-I", "-B", "-S", str(script), diagnostic.CONTROLLER_ARGUMENT, diagnostic.AUTHORITY_SHA_ARGUMENT, "f" * 64, diagnostic.ATTESTATION_ARGUMENT]
    command["controller_argv_template"] = list(argv)
    fake_smoke, fake_artifacts = SimpleNamespace(__file__=str(smoke_path)), SimpleNamespace(__file__=str(artifact_path))
    monkeypatch.setattr(diagnostic, "_validate_current_source", lambda value, hard: None)
    monkeypatch.setattr(diagnostic.importlib.metadata, "version", lambda name: command["packages"][name]["version"])
    monkeypatch.setattr(diagnostic, "_package_root", lambda name: command["packages"][name]["root"])
    monkeypatch.setattr(diagnostic.importlib, "import_module", lambda name: fake_smoke if name.endswith("smoke_training") else fake_artifacts)
    monkeypatch.setattr(diagnostic, "sys", SimpleNamespace(executable=str(interpreter), flags=SimpleNamespace(isolated=1, no_site=1, dont_write_bytecode=1), version="synthetic", path=[]))
    monkeypatch.chdir(root)
    return _authority_object(payload), script, argv


@pytest.mark.parametrize("mutation", ("none", "public", "resolved", "hash", "size", "python_version", "interpreter_mode", "flags", "package_version", "package_root", "package_custody", "origin"))
def test_bootstrap_validates_interpreter_runtime_packages_and_origins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str) -> None:
    authority, script, argv = _bootstrap_case(tmp_path, monkeypatch)
    interpreter, command = authority.payload["command"]["interpreter"], authority.payload["command"]
    if mutation == "public":
        interpreter["public_path"] = "/wrong"
    elif mutation == "resolved":
        interpreter["resolved_path"] = "/wrong"
    elif mutation == "hash":
        interpreter["sha256"] = ZERO_SHA
    elif mutation == "size":
        interpreter["size"] += 1
    elif mutation == "python_version":
        diagnostic.sys.version = "wrong"
    elif mutation == "interpreter_mode":
        os.chmod(interpreter["resolved_path"], 0o700)
    elif mutation == "flags":
        diagnostic.sys.flags.no_site = 0
    elif mutation == "package_version":
        monkeypatch.setattr(diagnostic.importlib.metadata, "version", lambda name: "wrong" if name == "torch" else command["packages"][name]["version"])
    elif mutation == "package_root":
        monkeypatch.setattr(diagnostic, "_package_root", lambda name: "/wrong" if name == "torch" else command["packages"][name]["root"])
    elif mutation == "package_custody":
        os.chmod(command["packages"]["torch"]["root"], 0o777)
    elif mutation == "origin":
        authority.payload["implementation"]["origins"]["smoke_training_module"] = "/wrong"
    if mutation == "none":
        assert diagnostic.bootstrap_runtime(authority, controller_script=script, argv=argv, worker=False, hard=diagnostic.time.monotonic_ns() + diagnostic.HARD_TIMEOUT_NS).__file__
    else:
        with pytest.raises(diagnostic.Invocation3DiagnosticError):
            diagnostic.bootstrap_runtime(authority, controller_script=script, argv=argv, worker=False, hard=diagnostic.time.monotonic_ns() + diagnostic.HARD_TIMEOUT_NS)


@pytest.mark.parametrize("substitution", ("none", "tracker_mode", "tracker", "manifest", "crossed_pair", "candidate", "view", "authorization"))
def test_historical_lineage_reconstruction_and_substitution(tmp_path: Path, substitution: str) -> None:
    tracker, manifest = tmp_path / "tracker", tmp_path / "manifest"
    tracker.write_bytes(b"tracker\n")
    manifest.write_bytes(b"manifest\n")
    os.chmod(tracker, 0o644)
    os.chmod(manifest, 0o600)
    os.chown(tracker, 501, 20)
    os.chown(manifest, 501, 20)
    candidate, key = tmp_path / "candidate", tmp_path / "key"
    candidate.mkdir(mode=0o700)
    key.write_bytes(b"k" * 32)
    os.chmod(key, 0o600)
    payload, calls = _base_payload(), []
    lineage = payload["historical_lineage"]
    lineage["tracker"] = {"path": str(tracker), "sha256": hashlib.sha256(tracker.read_bytes()).hexdigest(), "size": tracker.stat().st_size}
    lineage["manifest"] = {"path": str(manifest), "sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(), "size": manifest.stat().st_size}
    lineage["candidate"].update({"root": str(candidate), "reconciliation_key_path": str(key)})
    approval = SimpleNamespace(tracker_sha256=lineage["tracker"]["sha256"], tracker_size=lineage["tracker"]["size"], _tracker_path=tracker, candidate_checksum_record_sha256=lineage["candidate"]["checksum_record_sha256"], preparation_manifest_sha256=lineage["candidate"]["preparation_manifest_sha256"], schedule_plan_identity_sha256=lineage["candidate"]["schedule_plan_identity_sha256"])
    launch = SimpleNamespace(manifest_sha256=lineage["manifest"]["sha256"], _manifest_bytes=manifest.read_bytes(), _manifest_path=manifest, executor_commit=lineage["executor"]["commit"], executor_closure_digest=lineage["executor"]["source_closure_sha256"], resume_protocol=lineage["checkpoint"]["resume_protocol"])
    view = SimpleNamespace(semantic_sha256=lineage["candidate"]["sanitized_view_sha256"])
    historical = SimpleNamespace(authorization_sha256=lineage["production_authorization_sha256"])
    if substitution == "tracker_mode":
        os.chmod(tracker, 0o600)
    elif substitution == "tracker":
        approval.tracker_sha256 = ZERO_SHA
    elif substitution == "manifest":
        launch.manifest_sha256 = ZERO_SHA
    elif substitution == "crossed_pair":
        approval._tracker_path, launch._manifest_path = manifest, tracker
    elif substitution == "candidate":
        approval.candidate_checksum_record_sha256 = ZERO_SHA
    elif substitution == "view":
        view.semantic_sha256 = ZERO_SHA
    elif substitution == "authorization":
        historical.authorization_sha256 = ZERO_SHA
    def reached(name, value):
        calls.append(name)
        return value

    fake = SimpleNamespace(APPROVED_OUTPUT_PARENT=tmp_path / "unused", APPROVED_CANDIDATE_ROOT=candidate, APPROVED_RECONCILIATION_KEY_PATH=key, NEU_TINY=object(), TINY_SMOKE_SEED_PLANS=(object(),), _verify_supported_runtime=lambda: "runtime", _load_future_tracker_approval=lambda *args, **kwargs: reached("tracker", approval), _validate_launch_before_candidate_load=lambda *args, **kwargs: reached("manifest", launch), _validate_candidate_custody=lambda *args, **kwargs: reached("custody", None), load_preparation_candidate=lambda *args, **kwargs: reached("candidate", object()), derive_sanitized_training_view=lambda value: reached("view", view), create_paired_initialization=lambda *args: reached("initialization", object()), _construct_bound_production_authorization=lambda *args, **kwargs: reached("authorization", historical))
    if substitution == "none":
        result = diagnostic._historical_authorization(_authority_object(payload), fake, lambda: None)
        assert result.historical_authorization_sha256 == lineage["production_authorization_sha256"]
        assert calls == ["tracker", "manifest", "custody", "candidate", "view", "initialization", "authorization"]
    else:
        with pytest.raises(diagnostic.Invocation3DiagnosticError):
            diagnostic._historical_authorization(_authority_object(payload), fake, lambda: None)


def test_request_event_controller_and_cleanup_static_contract(tmp_path: Path) -> None:
    authority = _authority_object(_base_payload())
    stage = diagnostic._StageSnapshot("7" * 64, 1, 2, 1, 0, 0, MappingProxyType({".": (1,) * 8}), MappingProxyType({}))
    request = diagnostic._request_payload(authority, tmp_path, stage, ("a" * 64, 1, 0), 100)
    content = diagnostic._canonical(request)
    assert diagnostic._parse_request(content, hashlib.sha256(content).hexdigest()) == request
    request["parent_pid"] += 1
    changed = diagnostic._canonical(request)
    with pytest.raises(diagnostic.Invocation3DiagnosticError):
        diagnostic._parse_request(changed, hashlib.sha256(changed).hexdigest())
    source = Path(diagnostic.__file__).read_text()
    assert source.count("subprocess.Popen(") == 1
    tree = ast.parse(source)
    runs = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess" and node.func.attr == "run"]
    assert len(runs) == 1 and any(keyword.arg == "timeout" for keyword in runs[0].keywords)
    assert all(term not in source for term in ("rmtree", "TemporaryDirectory", "sys.meta_path", "SourceFileLoader", "launch_record"))
    assert source.count("os.unlink(") == 2
    controller = source[source.index("def run_controller"):]
    assert controller.index('"request.json"') < controller.index('"events.jsonl"') < controller.index("_publish_completion")
    assert "construct_production_smoke_execution_authorization" not in source
    assert "execute_bounded_tiny_smoke" not in source
