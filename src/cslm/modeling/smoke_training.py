"""Approved Tiny BERT smoke mechanics with a synthetic-only current gate."""

from __future__ import annotations

import copy
import hashlib
import importlib.metadata
import io
import json
import math
import os
import random
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import FunctionType, MappingProxyType, ModuleType
from typing import Any, Callable, Mapping, Sequence

import numpy as np
import torch
import torch.nn.functional as functional
from transformers import BertForMaskedLM

from cslm.modeling.config import (
    CONDITIONS,
    NEU_TINY,
    NUMPY_VERSION,
    SEP_TOKEN_ID,
    SPECIAL_TOKEN_IDS,
    TOKENIZERS_VERSION,
    TORCH_VERSION,
    TRANSFORMERS_VERSION,
    VOCAB_SIZE,
)
from cslm.modeling.contracts import (
    TINY_SMOKE_CHECKPOINT_UPDATES,
    TINY_SMOKE_DROPOUT_BASE_SEED,
    TINY_SMOKE_DROPOUT_PROTOCOL,
    TINY_SMOKE_EXECUTOR_DEVICE,
    TINY_SMOKE_MAXIMUM_CONCURRENCY,
    TINY_SMOKE_VALIDATION_UPDATES,
)
from cslm.modeling.initialization import (
    TINY_SMOKE_SEED_PLANS,
    InitializationManifest,
    PairedInitialization,
    create_paired_initialization,
    tied_parameter_groups,
    verify_independent_tiny_smoke_optimizers,
    verify_tiny_smoke_paired_initialization,
)
from cslm.modeling.masking import (
    IGNORE_INDEX,
    build_validation_mask_record,
    mask_packed_sequence,
)
from cslm.modeling.packing import PackedSequence, SourceTokenRange
from cslm.modeling.preparation import (
    SANITIZED_PREPARATION_RUNNER_DIGEST,
    SANITIZED_TRAINING_VIEW_PROTOCOL,
    SanitizedConditionTrainingView,
    SanitizedTensorArrays,
    SanitizedTrainingView,
    _derive_sanitized_tensor_arrays,
    _sanitized_tensor_digest_contract,
    _schedule_evidence_digest_contract,
    _source_ranges_digest_contract,
    canonical_json_bytes,
    derive_sanitized_training_view,
    load_preparation_candidate,
    sanitized_condition_view_digest,
    sanitized_training_view_digest,
)
from cslm.modeling.smoke_artifacts import (
    SMOKE_ARTIFACT_COMMIT_INDETERMINATE,
    SMOKE_CHECKPOINT_WRITE_FAILURE,
    PrivateRunArtifactWriter,
    SmokeArtifactError,
    _canonical_checkpoint_transaction_files,
    begin_private_run_artifacts,
    commit_private_checkpoint,
    commit_private_condition_result,
    commit_private_run,
)
from cslm.modeling.training_contract import (
    MicrobatchLoss,
    authorize_adamw_step,
    authorize_gradient_clipping,
    normalize_complete_update_loss,
)

_APPROVED_ADAMW_CLASS = torch.optim.AdamW
_APPROVED_ADAMW_STEP = torch.optim.AdamW.step

APPROVED_TRACKER_PATH = Path(
    "/Users/timothyowen/Desktop/NEU_LAB_Codex_Context_2026-07-15/"
    "NEU_LAB_Master_Progress_Tracker_2026-07-23_v5.0.md"
)
APPROVED_TRACKER_SHA256 = (
    "46d24c4d0442cb5c871db01e71529258bae38bb0c09127fe06d794e4d5596e12"
)
APPROVED_TRACKER_SIZE = 65_437
APPROVED_TRACKER_VERSION = "5.6"
APPROVED_TRACKER_DATE = "August 3, 2026"
APPROVED_CANDIDATE_CHECKSUM_RECORD_SHA256 = (
    "99400ad5e4e4757da54adc28a5a1e6ba8620196ed9d8799c682238856362dab3"
)
APPROVED_PREPARATION_MANIFEST_SHA256 = (
    "4bb52b5c0c541a0e59f354b64d75929adb80dd0d6decda04fa6b33229ba8d704"
)
APPROVED_SCHEDULE_PLAN_IDENTITY_SHA256 = (
    "e6dc6571483a8fe7e0a37070f1beaaf1ee57e21932bcf809f0c0da667e01ebb3"
)
APPROVED_PREPARATION_LINEAGE_COMMIT = (
    "adb2fbaa0fb0c72b8445a39714eabe7c7f8654a5"
)
APPROVED_PREPARATION_RUNNER_DIGEST = (
    "c4bc94d531e9f0b4eba4f048f447fda7ae000854b6c77e4a7ceafadae20806eb"
)
if APPROVED_PREPARATION_RUNNER_DIGEST != SANITIZED_PREPARATION_RUNNER_DIGEST:
    raise RuntimeError("sanitized preparation runner authority is inconsistent")
PREPARATION_PROTOCOL = "neu_real_preparation_v1"
CANDIDATE_SERIALIZED_STATUS = "candidate_unapproved"

MODEL_SEED = 1_729
TRAINING_MASK_SEED = 11_729
VALIDATION_MASK_SEED = 21_729
DROPOUT_BASE_SEED = TINY_SMOKE_DROPOUT_BASE_SEED
DROPOUT_PROTOCOL = TINY_SMOKE_DROPOUT_PROTOCOL
LEARNING_RATE_PROTOCOL = "neu_tiny_explicit_linear_lr_v1"
CHECKPOINT_PROTOCOL = "neu_tiny_smoke_checkpoint_v2"
RESUME_PROTOCOL = "neu_tiny_englishmono_fresh_process_resume_v2"
RESUME_WORKER_PROTOCOL = "neu_tiny_englishmono_fresh_process_worker_v2"
RESUME_BUNDLE_PROTOCOL = "neu_tiny_englishmono_replay_bundle_v2"
RESUME_RESULT_PROTOCOL = "neu_tiny_englishmono_replay_result_v2"
RESUME_WORKER_ARGUMENT = "--internal-tiny-resume-worker"
RESUME_DIAGNOSTIC_ARGUMENT = "--internal-tiny-replay-diagnostic"
RESUME_DIAGNOSTIC_WORKER_ARGUMENT = "--internal-tiny-replay-diagnostic-worker"
RESUME_DIAGNOSTIC_PROTOCOL = "neu_tiny_invocation3_replay_diagnostic_v1"
RESUME_WORKER_TIMEOUT_SECONDS = 600.0
RESUME_DIAGNOSTIC_HARD_TIMEOUT_SECONDS = 3_600.0
_INVOCATION3_DIAGNOSTIC_WORKSPACE_ROOT = Path("/private/tmp")
_INVOCATION3_DIAGNOSTIC_WORKSPACE_PREFIX = (
    "neu-invocation3-minimal-diagnostic."
)
INVOCATION3_RETAINED_STAGE = Path(
    "/Users/timothyowen/NEU_LAB_private_runs/tiny_smoke/"
    "run-stage-e1f72b4384747f7f2250f6d651eec427"
)
INVOCATION3_CHECKPOINT_750_STATE_SHA256 = (
    "c8b18f8fc662362664309ff1b8222058a14e1a7acc84bf33640e29d91461eae2"
)
EXECUTOR_PROTOCOL = "neu_tiny_smoke_executor_v1"
SYNTHETIC_AUTHORITY_PROTOCOL = "neu_tiny_smoke_synthetic_test_authority_v1"
PRODUCTION_AUTHORITY_PROTOCOL = "neu_tiny_smoke_production_authority_v1"
SYNTHETIC_PRODUCTION_EQUIVALENT_PROTOCOL = (
    "neu_tiny_smoke_synthetic_production_equivalent_v1"
)
PRODUCTION_RUNTIME_ADMISSION_TEST_TRACKER_PROTOCOL = (
    "neu_tiny_smoke_production_runtime_admission_test_v1"
)
TRACKER_LAUNCH_APPROVAL_PROTOCOL = "neu_tiny_smoke_tracker_launch_approval_v1"
TRACKER_LAUNCH_AUTHORITY_PREFIX = "NEU Tiny smoke launch authority record: "
SYNTHETIC_UPDATED_TRACKER_VERSION = "5.7"
SYNTHETIC_UPDATED_TRACKER_DATE = "August 4, 2026"
PEAK_LEARNING_RATE = 1e-4
VALIDATION_POINTS = TINY_SMOKE_VALIDATION_UPDATES
CHECKPOINT_UPDATES = TINY_SMOKE_CHECKPOINT_UPDATES
MAX_VALIDATION_BATCH_SIZE = 16
REPLAY_VALIDATION_POINTS = (800, 900, 1_000)
APPROVED_OUTPUT_PARENT = Path("~/NEU_LAB_private_runs/tiny_smoke").expanduser()
APPROVED_REPOSITORY_ROOT = Path("/Users/timothyowen/cs-lm-integrated-syntax")
APPROVED_CANDIDATE_ROOT = Path(
    "/Users/timothyowen/NEU_LAB_frozen_artifacts/model_ready/real_preparation_v1"
)
APPROVED_RECONCILIATION_KEY_PATH = Path(
    "/Users/timothyowen/.neu_lab_private_keys/real_preparation_v1.hmac"
)
APPROVED_LAUNCH_MANIFEST_PATH = Path(
    "/Users/timothyowen/Desktop/NEU_LAB_Codex_Context_2026-07-15/"
    "NEU_LAB_Tiny_Smoke_Launch_Manifest_v1.json"
)
EXECUTOR_CLOSURE_FILES = (
    "scripts/run_bounded_tiny_smoke.py",
    "src/cslm/modeling/config.py",
    "src/cslm/modeling/contracts.py",
    "src/cslm/modeling/initialization.py",
    "src/cslm/modeling/masking.py",
    "src/cslm/modeling/packing.py",
    "src/cslm/modeling/preparation.py",
    "src/cslm/modeling/scheduling.py",
    "src/cslm/modeling/smoke_artifacts.py",
    "src/cslm/modeling/smoke_training.py",
    "src/cslm/modeling/training_contract.py",
)
FUTURE_LAUNCH_APPROVAL_PROTOCOL = "neu_tiny_smoke_external_launch_approval_v1"

_PROCESS_IMPORT_PID = os.getpid()
_PROCESS_IMPORT_NONCE_SHA256 = hashlib.sha256(os.urandom(32)).hexdigest()

SMOKE_APPROVAL_MISMATCH = "SMOKE_APPROVAL_MISMATCH"
SMOKE_CANDIDATE_VERIFICATION_FAILURE = "SMOKE_CANDIDATE_VERIFICATION_FAILURE"
SMOKE_INITIALIZATION_MISMATCH = "SMOKE_INITIALIZATION_MISMATCH"
SMOKE_DEVICE_RUNTIME_MISMATCH = "SMOKE_DEVICE_RUNTIME_MISMATCH"
SMOKE_DATA_SCHEDULE_MISMATCH = "SMOKE_DATA_SCHEDULE_MISMATCH"
SMOKE_MASKING_MISMATCH = "SMOKE_MASKING_MISMATCH"
SMOKE_NONFINITE_LOSS = "SMOKE_NONFINITE_LOSS"
SMOKE_NONFINITE_GRADIENT = "SMOKE_NONFINITE_GRADIENT"
SMOKE_TARGET_COUNT_MISMATCH = "SMOKE_TARGET_COUNT_MISMATCH"
SMOKE_LOSS_NORMALIZATION_MISMATCH = "SMOKE_LOSS_NORMALIZATION_MISMATCH"
SMOKE_GRADIENT_CLIPPING_FAILURE = "SMOKE_GRADIENT_CLIPPING_FAILURE"
SMOKE_OPTIMIZER_SCHEDULER_FAILURE = "SMOKE_OPTIMIZER_SCHEDULER_FAILURE"
SMOKE_VALIDATION_MISMATCH = "SMOKE_VALIDATION_MISMATCH"
SMOKE_RESUME_MISMATCH = "SMOKE_RESUME_MISMATCH"

SMOKE_FAILURE_CODES = (
    SMOKE_APPROVAL_MISMATCH,
    SMOKE_CANDIDATE_VERIFICATION_FAILURE,
    SMOKE_INITIALIZATION_MISMATCH,
    SMOKE_DEVICE_RUNTIME_MISMATCH,
    SMOKE_DATA_SCHEDULE_MISMATCH,
    SMOKE_MASKING_MISMATCH,
    SMOKE_NONFINITE_LOSS,
    SMOKE_NONFINITE_GRADIENT,
    SMOKE_TARGET_COUNT_MISMATCH,
    SMOKE_LOSS_NORMALIZATION_MISMATCH,
    SMOKE_GRADIENT_CLIPPING_FAILURE,
    SMOKE_OPTIMIZER_SCHEDULER_FAILURE,
    SMOKE_VALIDATION_MISMATCH,
    SMOKE_CHECKPOINT_WRITE_FAILURE,
    SMOKE_RESUME_MISMATCH,
    SMOKE_ARTIFACT_COMMIT_INDETERMINATE,
)
_FAILURE_CODE_SET = frozenset(SMOKE_FAILURE_CODES)
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
_GIT_COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")


class SmokeTrainingError(RuntimeError):
    """Fixed-code error that never renders tensor, identity, path, or provenance data."""

    def __init__(self, code: str) -> None:
        if code not in _FAILURE_CODE_SET:
            code = SMOKE_APPROVAL_MISMATCH
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, init=False, slots=True)
class CandidateApprovalEvidence:
    authority_kind: str
    tracker_sha256: str
    tracker_size: int
    tracker_version: str
    canonical_date: str
    candidate_checksum_record_sha256: str
    preparation_manifest_sha256: str
    schedule_plan_identity_sha256: str
    preparation_protocol: str
    serialized_status: str
    exact_unique_approval: bool
    launch_manifest_approved: bool
    approved_launch_manifest_sha256: str | None
    _tracker_path: Path = field(repr=False, compare=False)
    _tracker_bytes: bytes = field(repr=False, compare=False)
    _factory_token: object = field(repr=False, compare=False)

    def __new__(cls) -> CandidateApprovalEvidence:
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)


@dataclass(frozen=True, init=False, slots=True)
class SmokeLaunchManifest:
    authority_kind: str
    candidate_checksum_record_sha256: str
    preparation_manifest_sha256: str
    schedule_plan_identity_sha256: str
    preparation_lineage_commit: str
    preparation_runner_digest: str
    executor_commit: str
    executor_closure_digest: str
    runtime_policy_sha256: str
    tiny_configuration_sha256: str
    seed_plan_sha256: str
    device: str
    learning_rate_protocol: str
    optimizer_protocol: str
    validation_points: tuple[int, ...]
    resume_protocol: str
    output_policy: str
    output_root_identity_sha256: str
    reporting_policy: str
    sanitized_view_sha256: str
    condition_digests: tuple[tuple[str, str], ...]
    tensor_array_digests: tuple[tuple[str, str, str], ...]
    schedule_bindings: tuple[tuple[str, str, str, str, str], ...]
    condition_order: tuple[str, ...]
    optimizer_updates_per_condition: int
    checkpoint_updates: tuple[int, ...]
    tracker_baseline_sha256: str
    tracker_baseline_size: int
    tracker_baseline_version: str
    tracker_baseline_canonical_date: str
    manifest_sha256: str
    manifest_file_sha256: str
    _manifest_path: Path = field(repr=False, compare=False)
    _manifest_bytes: bytes = field(repr=False, compare=False)
    _factory_token: object = field(repr=False, compare=False)

    def __new__(cls) -> SmokeLaunchManifest:
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)


@dataclass(frozen=True, init=False, slots=True)
class SmokeExecutionAuthorization:
    authority_kind: str
    approval: CandidateApprovalEvidence
    launch_manifest: SmokeLaunchManifest
    initialization_manifest: InitializationManifest
    training_view_sha256: str
    condition_digests: tuple[tuple[str, str], ...]
    tensor_array_digests: tuple[tuple[str, str, str], ...]
    schedule_bindings: tuple[tuple[str, str, str, str, str], ...]
    device: str
    maximum_concurrent_conditions: int
    authorization_sha256: str
    _tracker_path: Path = field(repr=False, compare=False)
    _launch_path: Path = field(repr=False, compare=False)
    _models: Mapping[str, BertForMaskedLM] = field(repr=False, compare=False)
    _training_view: SanitizedTrainingView = field(repr=False, compare=False)
    _factory_token: object = field(repr=False, compare=False)

    def __new__(cls) -> SmokeExecutionAuthorization:
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)


@dataclass(frozen=True, init=False, slots=True)
class RuntimeRunManifest:
    condition: str
    device: str
    executor_protocol: str
    authorization_sha256: str
    initialization_sha256: str
    schedule_sha256: str
    runtime_sha256: str
    deterministic_algorithms: bool
    maximum_concurrency: int

    def __new__(cls) -> RuntimeRunManifest:
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)


@dataclass(frozen=True, init=False, slots=True)
class PrivacySafeTerminalResult:
    mechanics_passed: bool
    completed_conditions: tuple[str, ...]
    completed_updates_per_condition: int
    cpu_only: bool
    final_semantic_sha256: str
    reporting_policy: str

    def __new__(cls) -> PrivacySafeTerminalResult:
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)


@dataclass(frozen=True, init=False, slots=True)
class ExplicitLearningRateState:
    completed_update: int
    last_step_learning_rate: float
    next_step_learning_rate: float
    protocol: str

    def __new__(cls) -> ExplicitLearningRateState:
        raise SmokeTrainingError(SMOKE_OPTIMIZER_SCHEDULER_FAILURE)


@dataclass(frozen=True, init=False, slots=True)
class UpdateMechanicsResult:
    condition: str
    completed_update: int
    selected_target_count: int
    normalized_loss: float = field(repr=False)
    unclipped_gradient_norm: float = field(repr=False)
    learning_rate_state: ExplicitLearningRateState
    mask_checksum_sha256: str

    def __new__(cls) -> UpdateMechanicsResult:
        raise SmokeTrainingError(SMOKE_OPTIMIZER_SCHEDULER_FAILURE)


@dataclass(frozen=True, init=False, slots=True)
class ValidationMechanicsResult:
    condition: str
    completed_update: int
    selected_target_count: int
    normalized_loss: float = field(repr=False)
    semantic_sha256: str

    def __new__(cls) -> ValidationMechanicsResult:
        raise SmokeTrainingError(SMOKE_VALIDATION_MISMATCH)


@dataclass(frozen=True, init=False, slots=True)
class CheckpointEnvelope:
    condition: str
    completed_update: int
    authorization_sha256: str
    sanitized_view_sha256: str
    launch_manifest_sha256: str
    checkpoint_inventory_sha256: str
    artifact_transaction_inventory_sha256: str
    envelope_sha256: str
    _files: Mapping[str, bytes] = field(repr=False, compare=False)
    _factory_token: object = field(repr=False, compare=False)

    def __new__(cls) -> CheckpointEnvelope:
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)


@dataclass(frozen=True, slots=True)
class _FreshProcessReplayResult:
    worker_pid: int
    module_import_pid: int
    fresh_interpreter: bool
    process_start_nonce_sha256: str
    request_sha256: str
    authorization_sha256: str
    checkpoint_envelope_sha256: str
    condition: str
    checkpoint_update: int
    first_replay_update: int
    last_replay_update: int
    replay_update_count: int
    validation_updates: tuple[int, ...]
    runtime_semantic_sha256: str
    rng_semantic_sha256: str
    learning_rate_semantic_sha256: str
    history_checksums: tuple[tuple[str, str], ...]
    result_sha256: str


@dataclass(frozen=True, init=False, slots=True)
class TinySmokeOptimizerSet:
    parameter_group_identities: tuple[tuple[str, str], ...]
    _optimizers: Mapping[str, torch.optim.AdamW] = field(repr=False, compare=False)
    _authorization_sha256: str = field(repr=False)
    _factory_token: object = field(repr=False, compare=False)

    def __new__(cls) -> TinySmokeOptimizerSet:
        raise SmokeTrainingError(SMOKE_OPTIMIZER_SCHEDULER_FAILURE)


@dataclass(init=False, slots=True)
class TinySmokeConditionRuntime:
    condition: str
    completed_update: int
    at_update_boundary: bool
    learning_rate_state: ExplicitLearningRateState
    _authorization: SmokeExecutionAuthorization = field(repr=False)
    _model: BertForMaskedLM = field(repr=False)
    _optimizer: torch.optim.AdamW = field(repr=False)
    _condition_view: SanitizedConditionTrainingView = field(repr=False)
    _loss_history: list[float] = field(repr=False)
    _target_count_history: list[int] = field(repr=False)
    _mask_history: list[str] = field(repr=False)
    _validation_history: list[tuple[int, float, int, str]] = field(repr=False)
    _factory_token: object = field(repr=False)

    def __new__(cls) -> TinySmokeConditionRuntime:
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)


@dataclass(frozen=True)
class _SyntheticAppearance:
    sequence_index: int
    sequence_identity: str
    visit: int


@dataclass(frozen=True)
class _SyntheticMicrobatchPlan:
    microbatch_index: int
    schedule_start_cursor: int
    schedule_end_cursor: int
    sequence_count: int
    selected_targets_by_seed: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class _SyntheticUpdatePlan:
    update: int
    schedule_start_cursor: int
    schedule_end_cursor: int
    microbatches: tuple[_SyntheticMicrobatchPlan, ...]
    selected_targets_by_seed: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class _SyntheticConditionSchedule:
    condition: str
    appearances: tuple[_SyntheticAppearance, ...] = field(repr=False)
    updates: tuple[_SyntheticUpdatePlan, ...] = field(repr=False)
    identity_sha256: str
    update_plan_sha256: str


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _require_sha256(value: object, code: str = SMOKE_APPROVAL_MISMATCH) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise SmokeTrainingError(code)
    return value


def _require_git_commit(value: object) -> str:
    if not isinstance(value, str) or _GIT_COMMIT_RE.fullmatch(value) is None:
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    return value


def approved_learning_rate(one_based_update: int) -> float:
    """Pure explicit LR authority; callers cannot select schedule parameters."""

    if type(one_based_update) is not int or not 1 <= one_based_update <= 1_000:
        raise SmokeTrainingError(SMOKE_OPTIMIZER_SCHEDULER_FAILURE)
    if one_based_update <= 100:
        return PEAK_LEARNING_RATE * one_based_update / 100
    return PEAK_LEARNING_RATE * ((1001 - one_based_update) / 900)


def learning_rate_state_after_update(completed_update: int) -> ExplicitLearningRateState:
    if type(completed_update) is not int or not 0 <= completed_update <= 1_000:
        raise SmokeTrainingError(SMOKE_OPTIMIZER_SCHEDULER_FAILURE)
    result = object.__new__(ExplicitLearningRateState)
    last_rate = 0.0 if completed_update == 0 else approved_learning_rate(completed_update)
    next_rate = (
        0.0
        if completed_update == 1_000
        else approved_learning_rate(completed_update + 1)
    )
    for name, value in {
        "completed_update": completed_update,
        "last_step_learning_rate": last_rate,
        "next_step_learning_rate": next_rate,
        "protocol": LEARNING_RATE_PROTOCOL,
    }.items():
        object.__setattr__(result, name, value)
    return result


def derive_tiny_dropout_seed(
    condition: str,
    one_based_update: int,
    zero_based_microbatch_position: int,
) -> int:
    """Derive the fixed domain-separated per-forward CPU dropout seed."""

    if (
        condition not in CONDITIONS
        or type(one_based_update) is not int
        or not 1 <= one_based_update <= 1_000
        or type(zero_based_microbatch_position) is not int
        or zero_based_microbatch_position < 0
    ):
        raise SmokeTrainingError(SMOKE_DATA_SCHEDULE_MISMATCH)
    digest = hashlib.sha256(
        canonical_json_bytes(
            [
                DROPOUT_PROTOCOL,
                ["base_seed", DROPOUT_BASE_SEED],
                ["canonical_condition", condition],
                ["one_based_optimizer_update", one_based_update],
                ["zero_based_microbatch_position", zero_based_microbatch_position],
            ]
        )
    ).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def _stable_read(path: Path, *, maximum_bytes: int) -> tuple[bytes, os.stat_result]:
    descriptor = -1
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_uid != os.getuid()
            or before.st_size > maximum_bytes
        ):
            raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
        chunks: list[bytes] = []
        remaining = maximum_bytes + 1
        while remaining:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        content = b"".join(chunks)
        after = os.fstat(descriptor)
        fields = ("st_dev", "st_ino", "st_size", "st_mode", "st_uid", "st_nlink")
        if len(content) > maximum_bytes or any(
            getattr(before, name) != getattr(after, name) for name in fields
        ):
            raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
        return content, after
    except SmokeTrainingError:
        raise
    except OSError:
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH) from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _runtime_policy_sha256() -> str:
    return _sha256_bytes(
        canonical_json_bytes(
            {
                "cpu_only": True,
                "deterministic_algorithms": True,
                "maximum_concurrency": 1,
                "numpy": NUMPY_VERSION,
                "python": ">=3.11,<3.13",
                "tokenizers": TOKENIZERS_VERSION,
                "torch": TORCH_VERSION,
                "transformers": TRANSFORMERS_VERSION,
            }
        )
    )


def _verify_supported_runtime() -> str:
    versions = {
        "numpy": NUMPY_VERSION,
        "tokenizers": TOKENIZERS_VERSION,
        "torch": TORCH_VERSION,
        "transformers": TRANSFORMERS_VERSION,
    }
    if (
        not (sys.version_info[:2] >= (3, 11) and sys.version_info[:2] < (3, 13))
        or any(importlib.metadata.version(name) != value for name, value in versions.items())
        or torch.get_default_dtype() != torch.float32
        or TINY_SMOKE_EXECUTOR_DEVICE != "cpu"
        or TINY_SMOKE_MAXIMUM_CONCURRENCY != 1
    ):
        raise SmokeTrainingError(SMOKE_DEVICE_RUNTIME_MISMATCH)
    return _runtime_policy_sha256()


def _output_root_identity(path: Path) -> str:
    return _sha256_bytes(
        canonical_json_bytes(
            [
                "neu_tiny_private_output_root_v1",
                path.absolute().as_posix(),
                "directories_0700",
                "files_0600",
                "no_overwrite_completion_last",
            ]
        )
    )


def _executor_repository_identity(repository_root: Path) -> tuple[str, str]:
    if not isinstance(repository_root, Path) or not repository_root.is_absolute():
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    git_directory = repository_root / ".git"
    head_bytes, _ = _stable_read(git_directory / "HEAD", maximum_bytes=512)
    try:
        head = head_bytes.decode("ascii").strip()
    except UnicodeDecodeError:
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH) from None
    if head.startswith("ref: "):
        reference = head[5:]
        if (
            not reference.startswith("refs/")
            or ".." in reference
            or re.fullmatch(r"[A-Za-z0-9._/-]+", reference) is None
        ):
            raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
        commit_bytes, _ = _stable_read(git_directory / reference, maximum_bytes=128)
        try:
            commit = commit_bytes.decode("ascii").strip()
        except UnicodeDecodeError:
            raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH) from None
    else:
        commit = head
    commit = _require_git_commit(commit)
    return commit, _executor_source_closure_identity(repository_root)


def _executor_source_closure_identity(repository_root: Path) -> str:
    if not isinstance(repository_root, Path) or not repository_root.is_absolute():
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    inventory: list[tuple[str, str]] = []
    for relative_name in EXECUTOR_CLOSURE_FILES:
        content, _ = _stable_read(
            repository_root / relative_name,
            maximum_bytes=5 * 1024 * 1024,
        )
        inventory.append((relative_name, _sha256_bytes(content)))
    return _sha256_bytes(
        canonical_json_bytes(["neu_tiny_executor_source_closure_v1", inventory])
    )


def _validate_output_root_custody(path: Path, *, production: bool) -> None:
    if (
        not isinstance(path, Path)
        or not path.is_absolute()
        or (production and path.absolute() != APPROVED_OUTPUT_PARENT)
        or (
            not production
            and (
                path.absolute() == APPROVED_OUTPUT_PARENT
                or APPROVED_OUTPUT_PARENT in path.absolute().parents
            )
        )
    ):
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    probe = path.absolute()
    while not probe.exists():
        parent = probe.parent
        if parent == probe:
            raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
        probe = parent
    try:
        resolved = probe.resolve(strict=True)
        status = os.lstat(probe)
    except OSError:
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH) from None
    if (
        resolved != probe
        or not stat.S_ISDIR(status.st_mode)
        or status.st_uid != os.getuid()
    ):
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    if path.exists():
        target = os.lstat(path)
        if (
            not stat.S_ISDIR(target.st_mode)
            or stat.S_IMODE(target.st_mode) != 0o700
            or target.st_uid != os.getuid()
        ):
            raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)


def _validate_candidate_custody(
    candidate_root: Path,
    key_path: Path,
    *,
    production: bool,
) -> None:
    if (
        not isinstance(candidate_root, Path)
        or not isinstance(key_path, Path)
        or not candidate_root.is_absolute()
        or not key_path.is_absolute()
        or (
            production
            and (
                candidate_root.absolute() != APPROVED_CANDIDATE_ROOT
                or key_path.absolute() != APPROVED_RECONCILIATION_KEY_PATH
            )
        )
    ):
        raise SmokeTrainingError(SMOKE_CANDIDATE_VERIFICATION_FAILURE)
    try:
        root_status = os.lstat(candidate_root)
        key_status = os.lstat(key_path)
    except OSError:
        raise SmokeTrainingError(SMOKE_CANDIDATE_VERIFICATION_FAILURE) from None
    if (
        not stat.S_ISDIR(root_status.st_mode)
        or stat.S_IMODE(root_status.st_mode) != 0o700
        or root_status.st_uid != os.getuid()
        or not stat.S_ISREG(key_status.st_mode)
        or stat.S_IMODE(key_status.st_mode) != 0o600
        or key_status.st_uid != os.getuid()
        or key_status.st_nlink != 1
        or key_status.st_size != 32
    ):
        raise SmokeTrainingError(SMOKE_CANDIDATE_VERIFICATION_FAILURE)


def _ensure_production_output_container() -> None:
    """Create the fixed private container only after production authority passes."""

    container = APPROVED_OUTPUT_PARENT.parent
    try:
        os.mkdir(container, 0o700)
    except FileExistsError:
        pass
    except OSError:
        raise SmokeTrainingError(SMOKE_CHECKPOINT_WRITE_FAILURE) from None
    try:
        status = container.lstat()
        if (
            not stat.S_ISDIR(status.st_mode)
            or stat.S_IMODE(status.st_mode) != 0o700
            or status.st_uid != os.getuid()
            or container.resolve(strict=True) != container
        ):
            raise SmokeTrainingError(SMOKE_CHECKPOINT_WRITE_FAILURE)
    except SmokeTrainingError:
        raise
    except Exception:
        raise SmokeTrainingError(SMOKE_CHECKPOINT_WRITE_FAILURE) from None


def _approval_sentence(candidate: str) -> str:
    return (
        "Timothy explicitly approves the exact candidate checksum-record SHA-256 `"
        + candidate
        + "` for the bounded Tiny BERT smoke-training gate and, subject to later "
        "training gates, the primary naturalistic experiment."
    )


def _parse_approval_content(
    content: bytes,
    *,
    tracker_sha256: str,
    tracker_version: str,
    canonical_date: str,
    candidate_checksum: str,
    preparation_manifest: str,
    schedule_identity: str,
    authority_kind: str,
    tracker_path: Path,
    token: object,
) -> CandidateApprovalEvidence:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH) from None
    required_unique = _approval_sentence(candidate_checksum)
    if (
        text.count(required_unique) != 1
        or text.count("Timothy explicitly approves the ") != 1
        or text.count(f"**Tracker version:** {tracker_version}") != 1
        or text.count(f"**Canonical status date:** {canonical_date}") != 1
        or preparation_manifest not in text
        or schedule_identity not in text
        or PREPARATION_PROTOCOL not in text
        or CANDIDATE_SERIALIZED_STATUS not in text
        or "No launch manifest is created or approved" not in text
        or "Real execution remains unauthorized" not in text
        or "context-matched sensitivity experiment" not in text
    ):
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    result = object.__new__(CandidateApprovalEvidence)
    values = {
        "authority_kind": authority_kind,
        "tracker_sha256": tracker_sha256,
        "tracker_size": len(content),
        "tracker_version": tracker_version,
        "canonical_date": canonical_date,
        "candidate_checksum_record_sha256": candidate_checksum,
        "preparation_manifest_sha256": preparation_manifest,
        "schedule_plan_identity_sha256": schedule_identity,
        "preparation_protocol": PREPARATION_PROTOCOL,
        "serialized_status": CANDIDATE_SERIALIZED_STATUS,
        "exact_unique_approval": True,
        "launch_manifest_approved": False,
        "approved_launch_manifest_sha256": None,
        "_tracker_path": tracker_path,
        "_tracker_bytes": content,
        "_factory_token": token,
    }
    for name, value in values.items():
        object.__setattr__(result, name, value)
    return result


def _load_candidate_approval_evidence_impl(
    tracker_path: Path,
    *,
    token: object,
) -> CandidateApprovalEvidence:
    if (
        os.environ.get("CSLM_TRACKED_ONLY_TEST") == "1"
        or not isinstance(tracker_path, Path)
        or tracker_path.absolute() != APPROVED_TRACKER_PATH
    ):
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    content, status = _stable_read(tracker_path, maximum_bytes=APPROVED_TRACKER_SIZE)
    if (
        len(content) != APPROVED_TRACKER_SIZE
        or _sha256_bytes(content) != APPROVED_TRACKER_SHA256
        or stat.S_IMODE(status.st_mode) != 0o644
    ):
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    return _parse_approval_content(
        content,
        tracker_sha256=APPROVED_TRACKER_SHA256,
        tracker_version=APPROVED_TRACKER_VERSION,
        canonical_date=APPROVED_TRACKER_DATE,
        candidate_checksum=APPROVED_CANDIDATE_CHECKSUM_RECORD_SHA256,
        preparation_manifest=APPROVED_PREPARATION_MANIFEST_SHA256,
        schedule_identity=APPROVED_SCHEDULE_PLAN_IDENTITY_SHA256,
        authority_kind="production_tracker",
        tracker_path=tracker_path,
        token=token,
    )


def _load_synthetic_candidate_approval_for_tests_impl(
    tracker_path: Path,
    *,
    candidate_checksum: str,
    preparation_manifest: str,
    schedule_identity: str,
    token: object,
) -> CandidateApprovalEvidence:
    candidate_checksum = _require_sha256(candidate_checksum)
    preparation_manifest = _require_sha256(preparation_manifest)
    schedule_identity = _require_sha256(schedule_identity)
    content, _ = _stable_read(tracker_path, maximum_bytes=1_000_000)
    return _parse_approval_content(
        content,
        tracker_sha256=_sha256_bytes(content),
        tracker_version=APPROVED_TRACKER_VERSION,
        canonical_date=APPROVED_TRACKER_DATE,
        candidate_checksum=candidate_checksum,
        preparation_manifest=preparation_manifest,
        schedule_identity=schedule_identity,
        authority_kind="synthetic_test_only",
        tracker_path=tracker_path,
        token=token,
    )


def _tracker_launch_approval_payload(
    *,
    authority_kind: str,
    candidate_checksum: str,
    preparation_manifest: str,
    schedule_identity: str,
    launch_manifest_sha256: str,
    executor_commit: str,
    executor_closure_digest: str,
    runtime_policy_sha256: str,
    output_parent: Path,
    tracker_version: str,
    canonical_date: str,
) -> dict[str, object]:
    """Return the sole reviewed tracker-carried launch-approval schema."""

    if (
        authority_kind
        not in {"production_tracker_and_launch", "synthetic_production_equivalent"}
        or re.fullmatch(r"[1-9][0-9]*\.[0-9]+", tracker_version) is None
        or re.fullmatch(
            r"(?:January|February|March|April|May|June|July|August|September|"
            r"October|November|December) [1-9][0-9]?, [0-9]{4}",
            canonical_date,
        )
        is None
        or not isinstance(output_parent, Path)
        or not output_parent.is_absolute()
    ):
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    return {
        "authority_kind": authority_kind,
        "baseline_tracker_canonical_date": APPROVED_TRACKER_DATE,
        "baseline_tracker_sha256": APPROVED_TRACKER_SHA256,
        "baseline_tracker_size": APPROVED_TRACKER_SIZE,
        "baseline_tracker_version": APPROVED_TRACKER_VERSION,
        "candidate_checksum_record_sha256": _require_sha256(candidate_checksum),
        "checkpoint_updates": list(CHECKPOINT_UPDATES),
        "condition_order": list(CONDITIONS),
        "decision": "approved",
        "device": TINY_SMOKE_EXECUTOR_DEVICE,
        "executor_closure_digest": _require_sha256(executor_closure_digest),
        "executor_commit": _require_git_commit(executor_commit),
        "launch_manifest_sha256": _require_sha256(launch_manifest_sha256),
        "learning_rate_protocol": LEARNING_RATE_PROTOCOL,
        "optimizer_protocol": _optimizer_protocol(),
        "optimizer_updates_per_condition": 1_000,
        "output_policy": "private_0700_files_0600_no_overwrite_completion_last",
        "output_root_identity_sha256": _output_root_identity(output_parent),
        "preparation_lineage_commit": APPROVED_PREPARATION_LINEAGE_COMMIT,
        "preparation_manifest_sha256": _require_sha256(preparation_manifest),
        "preparation_protocol": PREPARATION_PROTOCOL,
        "preparation_runner_digest": APPROVED_PREPARATION_RUNNER_DIGEST,
        "protocol": TRACKER_LAUNCH_APPROVAL_PROTOCOL,
        "reporting_policy": "mechanics_only_private_non_scientific",
        "resume_protocol": RESUME_PROTOCOL,
        "runtime_policy_sha256": _require_sha256(runtime_policy_sha256),
        "schedule_plan_identity_sha256": _require_sha256(schedule_identity),
        "seed_plan_sha256": _seed_plan_sha256(),
        "serialized_candidate_status": CANDIDATE_SERIALIZED_STATUS,
        "tiny_configuration_sha256": NEU_TINY.configuration_sha256(),
        "tracker_canonical_date": canonical_date,
        "tracker_version": tracker_version,
        "validation_points": list(VALIDATION_POINTS),
    }


def _updated_tracker_text_for_tests(
    *,
    heading: str,
    authority_kind: str,
    candidate_checksum: str,
    preparation_manifest: str,
    schedule_identity: str,
    launch_manifest_sha256: str,
    executor_commit: str,
    executor_closure_digest: str,
    runtime_policy_sha256: str,
    output_parent: Path,
) -> bytes:
    approval_payload = _tracker_launch_approval_payload(
        authority_kind=authority_kind,
        candidate_checksum=candidate_checksum,
        preparation_manifest=preparation_manifest,
        schedule_identity=schedule_identity,
        launch_manifest_sha256=launch_manifest_sha256,
        executor_commit=executor_commit,
        executor_closure_digest=executor_closure_digest,
        runtime_policy_sha256=runtime_policy_sha256,
        output_parent=output_parent,
        tracker_version=SYNTHETIC_UPDATED_TRACKER_VERSION,
        canonical_date=SYNTHETIC_UPDATED_TRACKER_DATE,
    )
    approval_record = canonical_json_bytes(approval_payload).decode("ascii").rstrip("\n")
    return "\n".join(
        (
            heading,
            f"**Tracker version:** {SYNTHETIC_UPDATED_TRACKER_VERSION}",
            f"**Canonical status date:** {SYNTHETIC_UPDATED_TRACKER_DATE}",
            _approval_sentence(candidate_checksum),
            f"Preparation-manifest SHA-256: `{preparation_manifest}`",
            f"Schedule-plan identity: `{schedule_identity}`",
            PREPARATION_PROTOCOL,
            CANDIDATE_SERIALIZED_STATUS,
            "The context-matched sensitivity experiment remains mandatory.",
            TRACKER_LAUNCH_AUTHORITY_PREFIX + approval_record,
            "Tiny smoke execution is authorized only for the bound manifest.",
            "",
        )
    ).encode("utf-8")


def _parse_tracker_launch_approval_record(
    content: bytes,
    *,
    authority_kind: str,
    candidate_checksum: str,
    preparation_manifest: str,
    schedule_identity: str,
    executor_commit: str,
    executor_closure_digest: str,
    runtime_policy_sha256: str,
    output_parent: Path,
) -> tuple[str, str, str]:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH) from None
    version_matches = re.findall(
        r"^\*\*Tracker version:\*\* ([1-9][0-9]*\.[0-9]+)$",
        text,
        flags=re.MULTILINE,
    )
    date_matches = re.findall(
        r"^\*\*Canonical status date:\*\* "
        r"((?:January|February|March|April|May|June|July|August|September|"
        r"October|November|December) [1-9][0-9]?, [0-9]{4})$",
        text,
        flags=re.MULTILINE,
    )
    record_lines = tuple(
        line.removeprefix(TRACKER_LAUNCH_AUTHORITY_PREFIX)
        for line in text.splitlines()
        if line.startswith(TRACKER_LAUNCH_AUTHORITY_PREFIX)
    )
    if (
        len(version_matches) != 1
        or len(date_matches) != 1
        or len(record_lines) != 1
        or text.count(TRACKER_LAUNCH_AUTHORITY_PREFIX) != 1
        or text.count(_approval_sentence(candidate_checksum)) != 1
        or text.count("Timothy explicitly approves the exact candidate ") != 1
        or PREPARATION_PROTOCOL not in text
        or CANDIDATE_SERIALIZED_STATUS not in text
        or "context-matched sensitivity experiment" not in text
        or "Tiny smoke execution is authorized only for the bound manifest." not in text
        or "No launch manifest is created or approved" in text
        or "Real execution remains unauthorized" in text
    ):
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    try:
        payload = json.loads(record_lines[0])
    except json.JSONDecodeError:
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH) from None
    expected = _tracker_launch_approval_payload(
        authority_kind=authority_kind,
        candidate_checksum=candidate_checksum,
        preparation_manifest=preparation_manifest,
        schedule_identity=schedule_identity,
        launch_manifest_sha256=str(payload.get("launch_manifest_sha256")),
        executor_commit=executor_commit,
        executor_closure_digest=executor_closure_digest,
        runtime_policy_sha256=runtime_policy_sha256,
        output_parent=output_parent,
        tracker_version=version_matches[0],
        canonical_date=date_matches[0],
    )
    if (
        payload != expected
        or canonical_json_bytes(payload).decode("ascii").rstrip("\n")
        != record_lines[0]
    ):
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    return (
        str(payload["launch_manifest_sha256"]),
        version_matches[0],
        date_matches[0],
    )


def _load_future_tracker_approval(
    tracker_path: Path,
    *,
    candidate_checksum: str,
    preparation_manifest: str,
    schedule_identity: str,
    executor_commit: str,
    executor_closure_digest: str,
    runtime_policy_sha256: str,
    output_parent: Path,
    authority_kind: str,
    production: bool,
    token: object,
) -> CandidateApprovalEvidence:
    if (
        not isinstance(tracker_path, Path)
        or not tracker_path.is_absolute()
        or (production and tracker_path.absolute() != APPROVED_TRACKER_PATH)
        or authority_kind
        not in {"production_tracker_and_launch", "synthetic_production_equivalent"}
    ):
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    content, status = _stable_read(tracker_path, maximum_bytes=1_000_000)
    tracker_sha256 = _sha256_bytes(content)
    if (
        stat.S_IMODE(status.st_mode) != (0o644 if production else 0o600)
    ):
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    if (
        production
        and tracker_sha256 == APPROVED_TRACKER_SHA256
        and len(content) == APPROVED_TRACKER_SIZE
    ):
        _parse_approval_content(
            content,
            tracker_sha256=tracker_sha256,
            tracker_version=APPROVED_TRACKER_VERSION,
            canonical_date=APPROVED_TRACKER_DATE,
            candidate_checksum=candidate_checksum,
            preparation_manifest=preparation_manifest,
            schedule_identity=schedule_identity,
            authority_kind="production_tracker",
            tracker_path=tracker_path,
            token=token,
        )
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    launch_sha256, tracker_version, canonical_date = (
        _parse_tracker_launch_approval_record(
            content,
            authority_kind=authority_kind,
            candidate_checksum=candidate_checksum,
            preparation_manifest=preparation_manifest,
            schedule_identity=schedule_identity,
            executor_commit=executor_commit,
            executor_closure_digest=executor_closure_digest,
            runtime_policy_sha256=runtime_policy_sha256,
            output_parent=output_parent,
        )
    )
    if production and tracker_sha256 == APPROVED_TRACKER_SHA256:
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    result = object.__new__(CandidateApprovalEvidence)
    for name, value in {
        "authority_kind": authority_kind,
        "tracker_sha256": tracker_sha256,
        "tracker_size": len(content),
        "tracker_version": tracker_version,
        "canonical_date": canonical_date,
        "candidate_checksum_record_sha256": candidate_checksum,
        "preparation_manifest_sha256": preparation_manifest,
        "schedule_plan_identity_sha256": schedule_identity,
        "preparation_protocol": PREPARATION_PROTOCOL,
        "serialized_status": CANDIDATE_SERIALIZED_STATUS,
        "exact_unique_approval": True,
        "launch_manifest_approved": True,
        "approved_launch_manifest_sha256": launch_sha256,
        "_tracker_path": tracker_path.absolute(),
        "_tracker_bytes": content,
        "_factory_token": token,
    }.items():
        object.__setattr__(result, name, value)
    return result


def _seed_plan_sha256() -> str:
    return _sha256_bytes(
        canonical_json_bytes(
            {
                "dropout": {"base_seed": DROPOUT_BASE_SEED, "protocol": DROPOUT_PROTOCOL},
                "model": MODEL_SEED,
                "training_mask": TRAINING_MASK_SEED,
                "validation_mask": VALIDATION_MASK_SEED,
            }
        )
    )


def _optimizer_protocol() -> str:
    return (
        "AdamW(lr=explicit,betas=0.9:0.999,eps=1e-8,weight_decay=0.01,"
        "uniform_unique_parameters,foreach=false,fused=false,clip_l2=1.0)"
    )


def _derive_synthetic_launch_manifest_for_tests_impl(
    approval: CandidateApprovalEvidence,
    *,
    executor_commit: str,
    executor_closure_digest: str,
    token: object,
) -> SmokeLaunchManifest:
    if (
        type(approval) is not CandidateApprovalEvidence
        or approval.authority_kind != "synthetic_test_only"
        or approval._factory_token is not token
    ):
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    executor_commit = _require_git_commit(executor_commit)
    executor_closure_digest = _require_sha256(executor_closure_digest)
    payload = {
        "authority_kind": "synthetic_test_only",
        "tracker_baseline_sha256": APPROVED_TRACKER_SHA256,
        "tracker_baseline_size": APPROVED_TRACKER_SIZE,
        "tracker_baseline_version": APPROVED_TRACKER_VERSION,
        "tracker_baseline_canonical_date": APPROVED_TRACKER_DATE,
        "candidate_checksum_record_sha256": approval.candidate_checksum_record_sha256,
        "preparation_manifest_sha256": approval.preparation_manifest_sha256,
        "schedule_plan_identity_sha256": approval.schedule_plan_identity_sha256,
        "preparation_lineage_commit": APPROVED_PREPARATION_LINEAGE_COMMIT,
        "preparation_runner_digest": APPROVED_PREPARATION_RUNNER_DIGEST,
        "executor_commit": executor_commit,
        "executor_closure_digest": executor_closure_digest,
        "runtime_policy_sha256": _runtime_policy_sha256(),
        "tiny_configuration_sha256": NEU_TINY.configuration_sha256(),
        "seed_plan_sha256": _seed_plan_sha256(),
        "device": TINY_SMOKE_EXECUTOR_DEVICE,
        "learning_rate_protocol": LEARNING_RATE_PROTOCOL,
        "optimizer_protocol": _optimizer_protocol(),
        "validation_points": VALIDATION_POINTS,
        "resume_protocol": RESUME_PROTOCOL,
        "output_policy": "private_0700_files_0600_no_overwrite_completion_last",
        "output_root_identity_sha256": _output_root_identity(APPROVED_OUTPUT_PARENT),
        "reporting_policy": "mechanics_only_private_non_scientific",
        "sanitized_view_sha256": "",
        "condition_digests": (),
        "tensor_array_digests": (),
        "schedule_bindings": (),
        "condition_order": CONDITIONS,
        "optimizer_updates_per_condition": 1_000,
        "checkpoint_updates": CHECKPOINT_UPDATES,
    }
    manifest_bytes = canonical_json_bytes(payload)
    result = object.__new__(SmokeLaunchManifest)
    for name, value in {
        **payload,
        "manifest_sha256": _sha256_bytes(manifest_bytes),
        "manifest_file_sha256": _sha256_bytes(manifest_bytes),
        "_manifest_path": Path(),
        "_manifest_bytes": manifest_bytes,
        "_factory_token": token,
    }.items():
        object.__setattr__(result, name, value)
    return result


def _synthetic_sequence(
    condition: str,
    arrays: SanitizedTensorArrays,
    identities: Sequence[str],
    source_ranges: Sequence[tuple[SourceTokenRange, ...]],
    index: int,
    *,
    split: str,
) -> PackedSequence:
    return PackedSequence(
        condition=condition,
        split=split,
        input_ids=tuple(int(value) for value in arrays.input_ids[index]),
        attention_mask=tuple(int(value) for value in arrays.attention_mask[index]),
        token_type_ids=tuple(int(value) for value in arrays.token_type_ids[index]),
        provenance=source_ranges[index],
        example_identity=identities[index],
    )


def _synthetic_privacy_safe_source_ranges(
    condition: str,
    arrays: SanitizedTensorArrays,
    identities: tuple[str, ...],
    *,
    split: str,
) -> tuple[tuple[SourceTokenRange, ...], ...]:
    """Create deterministic pseudonymous row ranges for synthetic-only fixtures."""

    if split not in {"train", "validation"}:
        raise SmokeTrainingError(SMOKE_DATA_SCHEDULE_MISMATCH)
    result: list[tuple[SourceTokenRange, ...]] = []
    separator_id = SEP_TOKEN_ID
    for index, identity in enumerate(identities):
        attended = int(arrays.attention_mask[index].sum())
        separators = tuple(
            position
            for position in range(1, attended)
            if int(arrays.input_ids[index, position]) == separator_id
        )
        cursor = 1
        sequence_ranges: list[SourceTokenRange] = []
        for row_order, separator in enumerate(separators):
            lexical_count = separator - cursor
            pseudonym_material = [
                "neu_tiny_synthetic_privacy_safe_provenance_v1",
                condition,
                split,
                identity,
                index,
                row_order,
            ]

            def pseudonym(kind: str) -> str:
                return _sha256_bytes(canonical_json_bytes([*pseudonym_material, kind]))

            sequence_ranges.append(
                SourceTokenRange(
                    condition=condition,
                    split=split,
                    source="synthetic_privacy_safe",
                    component="synthetic_privacy_safe",
                    document_id=pseudonym("document"),
                    conversation_id=pseudonym("conversation"),
                    span_id=pseudonym("span"),
                    row_id=pseudonym("row"),
                    row_order=row_order,
                    language_shard=(
                        "english"
                        if condition == "EnglishMono"
                        else "spanish" if condition == "SpanishMono" else None
                    ),
                    source_row_token_count=lexical_count,
                    source_token_start=0,
                    source_token_end=lexical_count,
                    packed_token_start=cursor,
                    packed_token_end=separator,
                )
            )
            cursor = separator + 1
        ranges = tuple(sequence_ranges)
        try:
            _synthetic_sequence(
                condition,
                arrays,
                identities,
                (ranges,) * len(identities),
                index,
                split=split,
            )
        except Exception:
            raise SmokeTrainingError(SMOKE_DATA_SCHEDULE_MISMATCH) from None
        result.append(ranges)
    return tuple(result)


def _sanitized_arrays_semantic_sha256(arrays: SanitizedTensorArrays) -> str:
    material = []
    for name in ("input_ids", "attention_mask", "token_type_ids", "labels"):
        array = getattr(arrays, name)
        material.append(
            [
                name,
                None if array is None else str(array.dtype),
                None if array is None else list(array.shape),
                None if array is None else _sha256_bytes(array.tobytes(order="C")),
            ]
        )
    return _sha256_bytes(canonical_json_bytes(["sanitized_arrays_v1", material]))


def _live_schedule_identities(
    schedule: _SyntheticConditionSchedule,
) -> tuple[str, str]:
    update_payload = [
        [
            item.update,
            item.schedule_start_cursor,
            item.schedule_end_cursor,
            [
                [
                    micro.microbatch_index,
                    micro.schedule_start_cursor,
                    micro.schedule_end_cursor,
                    micro.selected_targets_by_seed,
                ]
                for micro in item.microbatches
            ],
            item.selected_targets_by_seed,
        ]
        for item in schedule.updates
    ]
    schedule_payload = [
        schedule.condition,
        [
            [item.sequence_index, item.sequence_identity, item.visit]
            for item in schedule.appearances
        ],
        update_payload,
    ]
    return (
        _sha256_bytes(canonical_json_bytes(schedule_payload)),
        _sha256_bytes(canonical_json_bytes(["synthetic_update_plan", update_payload])),
    )


def _condition_view_semantic_sha256(
    view: SanitizedConditionTrainingView,
) -> str:
    try:
        return sanitized_condition_view_digest(view)
    except Exception:
        raise SmokeTrainingError(SMOKE_DATA_SCHEDULE_MISMATCH) from None


def _training_view_semantic_sha256(view: SanitizedTrainingView) -> str:
    try:
        return sanitized_training_view_digest(view)
    except Exception:
        raise SmokeTrainingError(SMOKE_DATA_SCHEDULE_MISMATCH) from None


def _view_anchor_components(
    view: SanitizedTrainingView,
) -> tuple[
    tuple[tuple[str, str], ...],
    tuple[tuple[str, str, str], ...],
    tuple[tuple[str, str, str, str, str], ...],
]:
    condition_digests = tuple(
        (item.condition, _condition_view_semantic_sha256(item))
        for item in view.conditions
    )
    tensor_digests = tuple(
        (
            item.condition,
            _sanitized_tensor_digest_contract(item.train_tensors),
            _sanitized_tensor_digest_contract(item.validation_tensors),
        )
        for item in view.conditions
    )
    schedule_bindings = tuple(
        (
            item.condition,
            item.schedule.identity_sha256,
            item.schedule.update_plan_sha256,
            _schedule_evidence_digest_contract(item.schedule),
            item.validation_plan_sha256,
        )
        for item in view.conditions
    )
    return condition_digests, tensor_digests, schedule_bindings


def _authorization_protocol(authority_kind: str) -> str:
    if authority_kind == "synthetic_test_only":
        return SYNTHETIC_AUTHORITY_PROTOCOL
    if authority_kind == "synthetic_production_equivalent":
        return SYNTHETIC_PRODUCTION_EQUIVALENT_PROTOCOL
    if authority_kind == "production_tracker_and_launch":
        return PRODUCTION_AUTHORITY_PROTOCOL
    raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)


def _authorization_semantic_sha256(
    authority_kind: str,
    approval: CandidateApprovalEvidence,
    launch_manifest: SmokeLaunchManifest,
    initialization_manifest: InitializationManifest,
    training_view_sha256: str,
    condition_digests: tuple[tuple[str, str], ...],
    tensor_digests: tuple[tuple[str, str, str], ...],
    schedule_bindings: tuple[tuple[str, str, str, str, str], ...],
) -> str:
    return _sha256_bytes(
        canonical_json_bytes(
            [
                _authorization_protocol(authority_kind),
                approval.tracker_sha256,
                approval.tracker_size,
                launch_manifest.manifest_sha256,
                initialization_manifest.initial_state_sha256,
                training_view_sha256,
                condition_digests,
                tensor_digests,
                schedule_bindings,
                "cpu",
                1,
            ]
        )
    )


def _tracker_authority_binding(
    authorization: SmokeExecutionAuthorization,
) -> dict[str, object]:
    if type(authorization) is not SmokeExecutionAuthorization:
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    return {
        "actual_canonical_date": authorization.approval.canonical_date,
        "actual_sha256": authorization.approval.tracker_sha256,
        "actual_size": authorization.approval.tracker_size,
        "actual_version": authorization.approval.tracker_version,
        "baseline_canonical_date": (
            authorization.launch_manifest.tracker_baseline_canonical_date
        ),
        "baseline_sha256": authorization.launch_manifest.tracker_baseline_sha256,
        "baseline_size": authorization.launch_manifest.tracker_baseline_size,
        "baseline_version": authorization.launch_manifest.tracker_baseline_version,
    }


def _production_launch_payload(
    view: SanitizedTrainingView,
    *,
    authority_kind: str,
    executor_commit: str,
    executor_closure_digest: str,
    output_parent: Path = APPROVED_OUTPUT_PARENT,
) -> dict[str, object]:
    condition_digests, tensor_digests, schedule_bindings = _view_anchor_components(view)
    return {
        "authority_kind": authority_kind,
        "tracker_baseline_sha256": APPROVED_TRACKER_SHA256,
        "tracker_baseline_size": APPROVED_TRACKER_SIZE,
        "tracker_baseline_version": APPROVED_TRACKER_VERSION,
        "tracker_baseline_canonical_date": APPROVED_TRACKER_DATE,
        "candidate_checksum_record_sha256": view.candidate_checksum_record_sha256,
        "checkpoint_updates": CHECKPOINT_UPDATES,
        "condition_digests": condition_digests,
        "condition_order": CONDITIONS,
        "device": TINY_SMOKE_EXECUTOR_DEVICE,
        "executor_closure_digest": _require_sha256(executor_closure_digest),
        "executor_commit": _require_git_commit(executor_commit),
        "learning_rate_protocol": LEARNING_RATE_PROTOCOL,
        "optimizer_protocol": _optimizer_protocol(),
        "optimizer_updates_per_condition": 1_000,
        "output_policy": "private_0700_files_0600_no_overwrite_completion_last",
        "output_root_identity_sha256": _output_root_identity(output_parent),
        "preparation_lineage_commit": APPROVED_PREPARATION_LINEAGE_COMMIT,
        "preparation_manifest_sha256": view.preparation_manifest_sha256,
        "preparation_runner_digest": APPROVED_PREPARATION_RUNNER_DIGEST,
        "reporting_policy": "mechanics_only_private_non_scientific",
        "resume_protocol": RESUME_PROTOCOL,
        "runtime_policy_sha256": _runtime_policy_sha256(),
        "sanitized_view_sha256": _training_view_semantic_sha256(view),
        "schedule_bindings": schedule_bindings,
        "schedule_plan_identity_sha256": view.schedule_plan_identity_sha256,
        "seed_plan_sha256": _seed_plan_sha256(),
        "tensor_array_digests": tensor_digests,
        "tiny_configuration_sha256": NEU_TINY.configuration_sha256(),
        "validation_points": VALIDATION_POINTS,
    }


def synthetic_production_authority_documents_for_tests(
    view: SanitizedTrainingView,
    *,
    executor_commit: str,
    executor_closure_digest: str,
) -> Mapping[str, bytes]:
    """Create marked external test documents; they can never authorize production."""

    if (
        type(view) is not SanitizedTrainingView
        or view.authority_kind != "synthetic_test_only"
        or any(len(item.schedule.updates) != 1_000 for item in view.conditions)
    ):
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    launch_payload = _production_launch_payload(
        view,
        authority_kind="synthetic_production_equivalent",
        executor_commit=executor_commit,
        executor_closure_digest=executor_closure_digest,
    )
    launch_bytes = canonical_json_bytes(launch_payload)
    tracker_payload = {
        "candidate_approval": "exact_unique_external_checksum_approval",
        "candidate_checksum_record_sha256": view.candidate_checksum_record_sha256,
        "canonical_date": APPROVED_TRACKER_DATE,
        "context_matched_sensitivity_required": True,
        "launch_manifest_sha256": _sha256_bytes(launch_bytes),
        "preparation_manifest_sha256": view.preparation_manifest_sha256,
        "preparation_protocol": PREPARATION_PROTOCOL,
        "protocol": "neu_tiny_synthetic_production_tracker_v1",
        "schedule_plan_identity_sha256": view.schedule_plan_identity_sha256,
        "serialized_status": CANDIDATE_SERIALIZED_STATUS,
        "tracker_version": APPROVED_TRACKER_VERSION,
    }
    return MappingProxyType(
        {
            "synthetic-production-tracker.json": canonical_json_bytes(tracker_payload),
            "synthetic-production-launch.json": launch_bytes,
        }
    )


def production_condition_runtime_authority_documents_for_tests(
    view: SanitizedTrainingView,
    *,
    executor_commit: str,
    executor_closure_digest: str,
) -> Mapping[str, bytes]:
    """Create fixed test documents for the exact production runtime authority kind."""

    if (
        os.environ.get("CSLM_TRACKED_ONLY_TEST") != "1"
        or type(view) is not SanitizedTrainingView
        or view.authority_kind != "synthetic_test_only"
        or any(len(item.schedule.updates) != 1_000 for item in view.conditions)
    ):
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    launch_payload = _production_launch_payload(
        view,
        authority_kind="production_tracker_and_launch",
        executor_commit=executor_commit,
        executor_closure_digest=executor_closure_digest,
    )
    launch_bytes = canonical_json_bytes(launch_payload)
    tracker_bytes = _updated_tracker_text_for_tests(
        heading="# Synthetic approval-updated production tracker",
        authority_kind="production_tracker_and_launch",
        candidate_checksum=view.candidate_checksum_record_sha256,
        preparation_manifest=view.preparation_manifest_sha256,
        schedule_identity=view.schedule_plan_identity_sha256,
        launch_manifest_sha256=_sha256_bytes(launch_bytes),
        executor_commit=executor_commit,
        executor_closure_digest=executor_closure_digest,
        runtime_policy_sha256=_runtime_policy_sha256(),
        output_parent=APPROVED_OUTPUT_PARENT,
    )
    return MappingProxyType(
        {
            "production-runtime-admission-tracker.json": tracker_bytes,
            "production-runtime-admission-launch.json": launch_bytes,
        }
    )


def synthetic_future_production_authority_documents_for_tests(
    view: SanitizedTrainingView,
    repository_root: Path,
    output_parent: Path,
) -> Mapping[str, bytes]:
    """Derive marked test documents from live synthetic repository and view state."""

    if (
        os.environ.get("CSLM_TRACKED_ONLY_TEST") != "1"
        or type(view) is not SanitizedTrainingView
        or view.authority_kind != "synthetic_test_only"
        or any(len(item.schedule.updates) != 1_000 for item in view.conditions)
    ):
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    executor_commit, executor_closure_digest = _executor_repository_identity(
        repository_root
    )
    launch_payload = _production_launch_payload(
        view,
        authority_kind="synthetic_production_equivalent",
        executor_commit=executor_commit,
        executor_closure_digest=executor_closure_digest,
        output_parent=output_parent,
    )
    launch_bytes = canonical_json_bytes(launch_payload)
    tracker_text = _updated_tracker_text_for_tests(
        heading="# Synthetic future Tiny smoke production authority",
        authority_kind="synthetic_production_equivalent",
        candidate_checksum=view.candidate_checksum_record_sha256,
        preparation_manifest=view.preparation_manifest_sha256,
        schedule_identity=view.schedule_plan_identity_sha256,
        launch_manifest_sha256=_sha256_bytes(launch_bytes),
        executor_commit=executor_commit,
        executor_closure_digest=executor_closure_digest,
        runtime_policy_sha256=_runtime_policy_sha256(),
        output_parent=output_parent,
    )
    return MappingProxyType(
        {
            "synthetic-future-tracker.md": tracker_text,
            "synthetic-future-launch.json": launch_bytes,
        }
    )


def _external_launch_manifest(
    payload: Mapping[str, object],
    content: bytes,
    path: Path,
    *,
    token: object,
) -> SmokeLaunchManifest:
    result = object.__new__(SmokeLaunchManifest)
    tuple_fields = {
        "checkpoint_updates": lambda value: tuple(value),
        "condition_digests": lambda value: tuple(tuple(item) for item in value),
        "condition_order": lambda value: tuple(value),
        "schedule_bindings": lambda value: tuple(tuple(item) for item in value),
        "tensor_array_digests": lambda value: tuple(tuple(item) for item in value),
        "validation_points": lambda value: tuple(value),
    }
    for name in (
        "authority_kind",
        "candidate_checksum_record_sha256",
        "preparation_manifest_sha256",
        "schedule_plan_identity_sha256",
        "preparation_lineage_commit",
        "preparation_runner_digest",
        "executor_commit",
        "executor_closure_digest",
        "runtime_policy_sha256",
        "tiny_configuration_sha256",
        "seed_plan_sha256",
        "device",
        "learning_rate_protocol",
        "optimizer_protocol",
        "validation_points",
        "resume_protocol",
        "output_policy",
        "output_root_identity_sha256",
        "reporting_policy",
        "sanitized_view_sha256",
        "condition_digests",
        "tensor_array_digests",
        "schedule_bindings",
        "condition_order",
        "optimizer_updates_per_condition",
        "checkpoint_updates",
        "tracker_baseline_sha256",
        "tracker_baseline_size",
        "tracker_baseline_version",
        "tracker_baseline_canonical_date",
    ):
        value = payload[name]
        if name in tuple_fields:
            value = tuple_fields[name](value)
        object.__setattr__(result, name, value)
    object.__setattr__(result, "manifest_sha256", _sha256_bytes(content))
    object.__setattr__(result, "manifest_file_sha256", _sha256_bytes(content))
    object.__setattr__(result, "_manifest_path", path)
    object.__setattr__(result, "_manifest_bytes", content)
    object.__setattr__(result, "_factory_token", token)
    return result


def _launch_payload_field_names() -> tuple[str, ...]:
    return (
        "authority_kind",
        "candidate_checksum_record_sha256",
        "checkpoint_updates",
        "condition_digests",
        "condition_order",
        "device",
        "executor_closure_digest",
        "executor_commit",
        "learning_rate_protocol",
        "optimizer_protocol",
        "optimizer_updates_per_condition",
        "output_policy",
        "output_root_identity_sha256",
        "preparation_lineage_commit",
        "preparation_manifest_sha256",
        "preparation_runner_digest",
        "reporting_policy",
        "resume_protocol",
        "runtime_policy_sha256",
        "sanitized_view_sha256",
        "schedule_bindings",
        "schedule_plan_identity_sha256",
        "seed_plan_sha256",
        "tensor_array_digests",
        "tiny_configuration_sha256",
        "tracker_baseline_canonical_date",
        "tracker_baseline_sha256",
        "tracker_baseline_size",
        "tracker_baseline_version",
        "validation_points",
    )


def _validate_launch_before_candidate_load(
    approval: CandidateApprovalEvidence,
    launch_path: Path,
    *,
    authority_kind: str,
    executor_commit: str,
    executor_closure_digest: str,
    runtime_policy_sha256: str,
    output_parent: Path,
    production: bool,
    token: object,
) -> SmokeLaunchManifest:
    if (
        type(approval) is not CandidateApprovalEvidence
        or approval._factory_token is not token
        or approval.authority_kind != authority_kind
        or not approval.launch_manifest_approved
        or not isinstance(launch_path, Path)
        or not launch_path.is_absolute()
        or (production and launch_path.absolute() != APPROVED_LAUNCH_MANIFEST_PATH)
    ):
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    content, status = _stable_read(launch_path, maximum_bytes=1_000_000)
    if (
        stat.S_IMODE(status.st_mode) != 0o600
        or _sha256_bytes(content) != approval.approved_launch_manifest_sha256
    ):
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    try:
        payload = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH) from None
    if (
        not isinstance(payload, dict)
        or set(payload) != set(_launch_payload_field_names())
        or canonical_json_bytes(payload) != content
    ):
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    condition_digests = payload.get("condition_digests")
    tensor_digests = payload.get("tensor_array_digests")
    schedule_bindings = payload.get("schedule_bindings")
    static_valid = (
        payload.get("authority_kind") == authority_kind
        and payload.get("tracker_baseline_sha256") == APPROVED_TRACKER_SHA256
        and payload.get("tracker_baseline_size") == APPROVED_TRACKER_SIZE
        and payload.get("tracker_baseline_version") == APPROVED_TRACKER_VERSION
        and payload.get("tracker_baseline_canonical_date")
        == APPROVED_TRACKER_DATE
        and payload.get("candidate_checksum_record_sha256")
        == approval.candidate_checksum_record_sha256
        and payload.get("preparation_manifest_sha256")
        == approval.preparation_manifest_sha256
        and payload.get("schedule_plan_identity_sha256")
        == approval.schedule_plan_identity_sha256
        and payload.get("preparation_lineage_commit")
        == APPROVED_PREPARATION_LINEAGE_COMMIT
        and payload.get("preparation_runner_digest")
        == APPROVED_PREPARATION_RUNNER_DIGEST
        and payload.get("executor_commit") == executor_commit
        and payload.get("executor_closure_digest") == executor_closure_digest
        and payload.get("runtime_policy_sha256") == runtime_policy_sha256
        and payload.get("tiny_configuration_sha256")
        == NEU_TINY.configuration_sha256()
        and payload.get("seed_plan_sha256") == _seed_plan_sha256()
        and payload.get("device") == "cpu"
        and payload.get("learning_rate_protocol") == LEARNING_RATE_PROTOCOL
        and payload.get("optimizer_protocol") == _optimizer_protocol()
        and payload.get("validation_points") == list(VALIDATION_POINTS)
        and payload.get("checkpoint_updates") == list(CHECKPOINT_UPDATES)
        and payload.get("resume_protocol") == RESUME_PROTOCOL
        and payload.get("optimizer_updates_per_condition") == 1_000
        and payload.get("condition_order") == list(CONDITIONS)
        and payload.get("output_policy")
        == "private_0700_files_0600_no_overwrite_completion_last"
        and payload.get("output_root_identity_sha256")
        == _output_root_identity(output_parent)
        and payload.get("reporting_policy")
        == "mechanics_only_private_non_scientific"
        and _SHA256_RE.fullmatch(str(payload.get("sanitized_view_sha256")))
        is not None
        and isinstance(condition_digests, list)
        and isinstance(tensor_digests, list)
        and isinstance(schedule_bindings, list)
        and len(condition_digests) == len(CONDITIONS)
        and len(tensor_digests) == len(CONDITIONS)
        and len(schedule_bindings) == len(CONDITIONS)
        and all(
            isinstance(item, list)
            and len(item) == 2
            and item[0] == condition
            and _SHA256_RE.fullmatch(str(item[1])) is not None
            for condition, item in zip(CONDITIONS, condition_digests, strict=True)
        )
        and all(
            isinstance(item, list)
            and len(item) == 3
            and item[0] == condition
            and all(_SHA256_RE.fullmatch(str(value)) is not None for value in item[1:])
            for condition, item in zip(CONDITIONS, tensor_digests, strict=True)
        )
        and all(
            isinstance(item, list)
            and len(item) == 5
            and item[0] == condition
            and all(_SHA256_RE.fullmatch(str(value)) is not None for value in item[1:])
            for condition, item in zip(CONDITIONS, schedule_bindings, strict=True)
        )
    )
    if not static_valid:
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    return _external_launch_manifest(
        payload,
        content,
        launch_path.absolute(),
        token=token,
    )


def _construct_bound_production_authorization(
    approval: CandidateApprovalEvidence,
    launch: SmokeLaunchManifest,
    training_view: SanitizedTrainingView,
    paired_initialization: PairedInitialization,
    *,
    authority_kind: str,
    required_view_kind: str,
    output_parent: Path,
    token: object,
) -> SmokeExecutionAuthorization:
    expected_launch = _production_launch_payload(
        training_view,
        authority_kind=authority_kind,
        executor_commit=launch.executor_commit,
        executor_closure_digest=launch.executor_closure_digest,
        output_parent=output_parent,
    )
    if (
        type(approval) is not CandidateApprovalEvidence
        or type(launch) is not SmokeLaunchManifest
        or type(training_view) is not SanitizedTrainingView
        or approval._factory_token is not token
        or launch._factory_token is not token
        or approval.authority_kind != authority_kind
        or launch.authority_kind != authority_kind
        or training_view.authority_kind != required_view_kind
        or training_view.candidate_checksum_record_sha256
        != approval.candidate_checksum_record_sha256
        or training_view.preparation_manifest_sha256
        != approval.preparation_manifest_sha256
        or training_view.schedule_plan_identity_sha256
        != approval.schedule_plan_identity_sha256
        or training_view.training_mask_seed != TRAINING_MASK_SEED
        or training_view.validation_mask_seed != VALIDATION_MASK_SEED
        or training_view.condition_order != CONDITIONS
        or tuple(item.condition for item in training_view.conditions) != CONDITIONS
        or any(len(item.schedule.updates) != 1_000 for item in training_view.conditions)
        or canonical_json_bytes(expected_launch) != launch._manifest_bytes
        or launch.manifest_sha256 != _sha256_bytes(launch._manifest_bytes)
        or approval.approved_launch_manifest_sha256 != launch.manifest_file_sha256
    ):
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    try:
        torch.use_deterministic_algorithms(True)
        verify_tiny_smoke_paired_initialization(paired_initialization)
    except Exception:
        raise SmokeTrainingError(SMOKE_INITIALIZATION_MISMATCH) from None
    condition_digests, tensor_digests, schedule_bindings = _view_anchor_components(
        training_view
    )
    result = object.__new__(SmokeExecutionAuthorization)
    for name, value in {
        "authority_kind": authority_kind,
        "approval": approval,
        "launch_manifest": launch,
        "initialization_manifest": paired_initialization.manifest,
        "training_view_sha256": training_view.semantic_sha256,
        "condition_digests": condition_digests,
        "tensor_array_digests": tensor_digests,
        "schedule_bindings": schedule_bindings,
        "device": "cpu",
        "maximum_concurrent_conditions": 1,
        "authorization_sha256": _authorization_semantic_sha256(
            authority_kind,
            approval,
            launch,
            paired_initialization.manifest,
            training_view.semantic_sha256,
            condition_digests,
            tensor_digests,
            schedule_bindings,
        ),
        "_tracker_path": approval._tracker_path,
        "_launch_path": launch._manifest_path,
        "_models": paired_initialization.models,
        "_training_view": training_view,
        "_factory_token": token,
    }.items():
        object.__setattr__(result, name, value)
    _reanchor_consumed_view(result, code=SMOKE_APPROVAL_MISMATCH)
    return result


def _construct_future_production_authority_path_impl(
    *,
    repository_root: Path,
    tracker_path: Path,
    launch_path: Path,
    candidate_root: Path,
    key_path: Path,
    output_parent: Path,
    authority_kind: str,
    production: bool,
    synthetic_view: SanitizedTrainingView | None,
    test_hook: Callable[[str], None] | None,
    token: object,
) -> SmokeExecutionAuthorization:
    if (
        (production and os.environ.get("CSLM_TRACKED_ONLY_TEST") == "1")
        or (not production and os.environ.get("CSLM_TRACKED_ONLY_TEST") != "1")
        or (production and repository_root.absolute() != APPROVED_REPOSITORY_ROOT)
        or (
            production
            and authority_kind != "production_tracker_and_launch"
        )
        or (
            not production
            and (
                authority_kind != "synthetic_production_equivalent"
                or type(synthetic_view) is not SanitizedTrainingView
                or synthetic_view.authority_kind != "synthetic_test_only"
            )
        )
    ):
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)

    def reached(event: str) -> None:
        if test_hook is not None:
            test_hook(event)

    runtime_policy = _verify_supported_runtime()
    executor_commit, executor_closure_digest = _executor_repository_identity(
        repository_root
    )
    reached("runtime_and_executor_verified")
    candidate_checksum = (
        APPROVED_CANDIDATE_CHECKSUM_RECORD_SHA256
        if production
        else synthetic_view.candidate_checksum_record_sha256
    )
    preparation_manifest = (
        APPROVED_PREPARATION_MANIFEST_SHA256
        if production
        else synthetic_view.preparation_manifest_sha256
    )
    schedule_identity = (
        APPROVED_SCHEDULE_PLAN_IDENTITY_SHA256
        if production
        else synthetic_view.schedule_plan_identity_sha256
    )
    approval = _load_future_tracker_approval(
        tracker_path,
        candidate_checksum=candidate_checksum,
        preparation_manifest=preparation_manifest,
        schedule_identity=schedule_identity,
        executor_commit=executor_commit,
        executor_closure_digest=executor_closure_digest,
        runtime_policy_sha256=runtime_policy,
        output_parent=output_parent,
        authority_kind=authority_kind,
        production=production,
        token=token,
    )
    reached("tracker_verified")
    launch = _validate_launch_before_candidate_load(
        approval,
        launch_path,
        authority_kind=authority_kind,
        executor_commit=executor_commit,
        executor_closure_digest=executor_closure_digest,
        runtime_policy_sha256=runtime_policy,
        output_parent=output_parent,
        production=production,
        token=token,
    )
    reached("launch_verified")
    _validate_output_root_custody(output_parent, production=production)
    _validate_candidate_custody(
        candidate_root,
        key_path,
        production=production,
    )
    reached("runtime_output_and_candidate_custody_verified")
    if production:
        try:
            snapshot = load_preparation_candidate(
                candidate_root,
                reconciliation_key_path=key_path,
            )
        except Exception:
            raise SmokeTrainingError(SMOKE_CANDIDATE_VERIFICATION_FAILURE) from None
        reached("candidate_loaded")
        try:
            view = derive_sanitized_training_view(snapshot)
        except Exception:
            raise SmokeTrainingError(SMOKE_CANDIDATE_VERIFICATION_FAILURE) from None
        snapshot = None
    else:
        reached("candidate_loaded")
        view = synthetic_view
    reached("sanitized_view_derived")
    try:
        paired = create_paired_initialization(NEU_TINY, TINY_SMOKE_SEED_PLANS[0])
    except Exception:
        raise SmokeTrainingError(SMOKE_INITIALIZATION_MISMATCH) from None
    authorization = _construct_bound_production_authorization(
        approval,
        launch,
        view,
        paired,
        authority_kind=authority_kind,
        required_view_kind="production_loader" if production else "synthetic_test_only",
        output_parent=output_parent,
        token=token,
    )
    reached("production_authority_constructed")
    return authorization


def _construct_production_smoke_execution_authorization_impl(
    *,
    token: object,
) -> SmokeExecutionAuthorization:
    return _construct_future_production_authority_path_impl(
        repository_root=APPROVED_REPOSITORY_ROOT,
        tracker_path=APPROVED_TRACKER_PATH,
        launch_path=APPROVED_LAUNCH_MANIFEST_PATH,
        candidate_root=APPROVED_CANDIDATE_ROOT,
        key_path=APPROVED_RECONCILIATION_KEY_PATH,
        output_parent=APPROVED_OUTPUT_PARENT,
        authority_kind="production_tracker_and_launch",
        production=True,
        synthetic_view=None,
        test_hook=None,
        token=token,
    )


def _construct_synthetic_future_production_authorization_for_tests_impl(
    repository_root: Path,
    tracker_path: Path,
    launch_path: Path,
    candidate_root: Path,
    key_path: Path,
    output_parent: Path,
    synthetic_view: SanitizedTrainingView,
    *,
    test_hook: Callable[[str], None] | None,
    token: object,
) -> SmokeExecutionAuthorization:
    return _construct_future_production_authority_path_impl(
        repository_root=repository_root,
        tracker_path=tracker_path,
        launch_path=launch_path,
        candidate_root=candidate_root,
        key_path=key_path,
        output_parent=output_parent,
        authority_kind="synthetic_production_equivalent",
        production=False,
        synthetic_view=synthetic_view,
        test_hook=test_hook,
        token=token,
    )


def _derive_external_test_authorization_impl(
    tracker_path: Path,
    launch_path: Path,
    training_view: SanitizedTrainingView,
    paired_initialization: PairedInitialization,
    *,
    executor_commit: str,
    executor_closure_digest: str,
    authority_kind: str,
    tracker_protocol: str,
    token: object,
) -> SmokeExecutionAuthorization:
    if (
        os.environ.get("CSLM_TRACKED_ONLY_TEST") != "1"
        or not isinstance(tracker_path, Path)
        or not isinstance(launch_path, Path)
        or type(training_view) is not SanitizedTrainingView
        or training_view.authority_kind != "synthetic_test_only"
        or any(len(item.schedule.updates) != 1_000 for item in training_view.conditions)
        or (authority_kind, tracker_protocol)
        not in {
            (
                "synthetic_production_equivalent",
                "neu_tiny_synthetic_production_tracker_v1",
            ),
            (
                "production_tracker_and_launch",
                PRODUCTION_RUNTIME_ADMISSION_TEST_TRACKER_PROTOCOL,
            ),
        }
    ):
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    if authority_kind == "production_tracker_and_launch":
        approval = _load_future_tracker_approval(
            tracker_path.absolute(),
            candidate_checksum=training_view.candidate_checksum_record_sha256,
            preparation_manifest=training_view.preparation_manifest_sha256,
            schedule_identity=training_view.schedule_plan_identity_sha256,
            executor_commit=executor_commit,
            executor_closure_digest=executor_closure_digest,
            runtime_policy_sha256=_runtime_policy_sha256(),
            output_parent=APPROVED_OUTPUT_PARENT,
            authority_kind=authority_kind,
            production=False,
            token=token,
        )
        launch = _validate_launch_before_candidate_load(
            approval,
            launch_path.absolute(),
            authority_kind=authority_kind,
            executor_commit=executor_commit,
            executor_closure_digest=executor_closure_digest,
            runtime_policy_sha256=_runtime_policy_sha256(),
            output_parent=APPROVED_OUTPUT_PARENT,
            production=False,
            token=token,
        )
        return _construct_bound_production_authorization(
            approval,
            launch,
            training_view,
            paired_initialization,
            authority_kind=authority_kind,
            required_view_kind="synthetic_test_only",
            output_parent=APPROVED_OUTPUT_PARENT,
            token=token,
        )
    tracker_bytes, _ = _stable_read(tracker_path, maximum_bytes=100_000)
    launch_bytes, _ = _stable_read(launch_path, maximum_bytes=100_000)
    try:
        tracker_payload = json.loads(tracker_bytes.decode("utf-8"))
        launch_payload = json.loads(launch_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH) from None
    expected_launch = _production_launch_payload(
        training_view,
        authority_kind=authority_kind,
        executor_commit=executor_commit,
        executor_closure_digest=executor_closure_digest,
    )
    expected_tracker = {
        "candidate_approval": "exact_unique_external_checksum_approval",
        "candidate_checksum_record_sha256": (
            training_view.candidate_checksum_record_sha256
        ),
        "canonical_date": APPROVED_TRACKER_DATE,
        "context_matched_sensitivity_required": True,
        "launch_manifest_sha256": _sha256_bytes(launch_bytes),
        "preparation_manifest_sha256": training_view.preparation_manifest_sha256,
        "preparation_protocol": PREPARATION_PROTOCOL,
        "protocol": tracker_protocol,
        "schedule_plan_identity_sha256": training_view.schedule_plan_identity_sha256,
        "serialized_status": CANDIDATE_SERIALIZED_STATUS,
        "tracker_version": APPROVED_TRACKER_VERSION,
    }
    if (
        tracker_payload != expected_tracker
        or canonical_json_bytes(launch_payload) != canonical_json_bytes(expected_launch)
        or canonical_json_bytes(tracker_payload) != tracker_bytes
        or canonical_json_bytes(launch_payload) != launch_bytes
    ):
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    approval = object.__new__(CandidateApprovalEvidence)
    for name, value in {
        "authority_kind": authority_kind,
        "tracker_sha256": _sha256_bytes(tracker_bytes),
        "tracker_size": len(tracker_bytes),
        "tracker_version": APPROVED_TRACKER_VERSION,
        "canonical_date": APPROVED_TRACKER_DATE,
        "candidate_checksum_record_sha256": (
            training_view.candidate_checksum_record_sha256
        ),
        "preparation_manifest_sha256": training_view.preparation_manifest_sha256,
        "schedule_plan_identity_sha256": training_view.schedule_plan_identity_sha256,
        "preparation_protocol": PREPARATION_PROTOCOL,
        "serialized_status": CANDIDATE_SERIALIZED_STATUS,
        "exact_unique_approval": True,
        "launch_manifest_approved": True,
        "approved_launch_manifest_sha256": _sha256_bytes(launch_bytes),
        "_tracker_path": tracker_path.absolute(),
        "_tracker_bytes": tracker_bytes,
        "_factory_token": token,
    }.items():
        object.__setattr__(approval, name, value)
    launch = _external_launch_manifest(
        expected_launch,
        launch_bytes,
        launch_path.absolute(),
        token=token,
    )
    return _construct_bound_production_authorization(
        approval,
        launch,
        training_view,
        paired_initialization,
        authority_kind=authority_kind,
        required_view_kind="synthetic_test_only",
        output_parent=APPROVED_OUTPUT_PARENT,
        token=token,
    )


def _derive_synthetic_production_authorization_for_tests_impl(
    tracker_path: Path,
    launch_path: Path,
    training_view: SanitizedTrainingView,
    paired_initialization: PairedInitialization,
    *,
    executor_commit: str,
    executor_closure_digest: str,
    token: object,
) -> SmokeExecutionAuthorization:
    return _derive_external_test_authorization_impl(
        tracker_path,
        launch_path,
        training_view,
        paired_initialization,
        executor_commit=executor_commit,
        executor_closure_digest=executor_closure_digest,
        authority_kind="synthetic_production_equivalent",
        tracker_protocol="neu_tiny_synthetic_production_tracker_v1",
        token=token,
    )


def _derive_production_condition_runtime_authorization_for_tests_impl(
    tracker_path: Path,
    launch_path: Path,
    training_view: SanitizedTrainingView,
    paired_initialization: PairedInitialization,
    *,
    executor_commit: str,
    executor_closure_digest: str,
    token: object,
) -> SmokeExecutionAuthorization:
    return _derive_external_test_authorization_impl(
        tracker_path,
        launch_path,
        training_view,
        paired_initialization,
        executor_commit=executor_commit,
        executor_closure_digest=executor_closure_digest,
        authority_kind="production_tracker_and_launch",
        tracker_protocol=PRODUCTION_RUNTIME_ADMISSION_TEST_TRACKER_PROTOCOL,
        token=token,
    )


def _reanchor_consumed_view(
    authorization: SmokeExecutionAuthorization,
    *,
    condition: str | None = None,
    code: str = SMOKE_DATA_SCHEDULE_MISMATCH,
) -> SanitizedConditionTrainingView | None:
    try:
        view = authorization._training_view
        matches = (
            ()
            if condition is None
            else tuple(item for item in view.conditions if item.condition == condition)
        )
        if condition is not None and len(matches) != 1:
            raise SmokeTrainingError(code)
        consumed = None if condition is None else matches[0]
        if consumed is None:
            live_digest = _training_view_semantic_sha256(view)
            condition_digests, tensor_digests, schedule_bindings = (
                _view_anchor_components(view)
            )
        else:
            live_digest = authorization.training_view_sha256
            condition_digests = authorization.condition_digests
            tensor_digests = authorization.tensor_array_digests
            schedule_bindings = authorization.schedule_bindings
            live_condition_digest = _condition_view_semantic_sha256(consumed)
            expected_condition_digest = dict(condition_digests).get(condition)
            expected_tensor = {
                item_condition: (train_digest, validation_digest)
                for item_condition, train_digest, validation_digest in tensor_digests
            }.get(condition)
            expected_schedule = {
                item_condition: binding
                for item_condition, *binding in schedule_bindings
            }.get(condition)
            if (
                expected_tensor is None
                or expected_schedule is None
                or live_condition_digest != expected_condition_digest
                or consumed.train_tensor_sha256 != expected_tensor[0]
                or consumed.train_source_ranges_sha256
                != _source_ranges_digest_contract(
                    consumed.condition,
                    consumed.train_tensors,
                    consumed.ordered_train_identities,
                    consumed.ordered_train_source_ranges,
                )
                or consumed.validation_tensor_sha256 != expected_tensor[1]
                or consumed.schedule.identity_sha256 != expected_schedule[0]
                or consumed.schedule.update_plan_sha256 != expected_schedule[1]
                or consumed.schedule_evidence_sha256 != expected_schedule[2]
                or consumed.validation_plan_sha256 != expected_schedule[3]
            ):
                raise SmokeTrainingError(code)
        valid = (
            type(authorization) is SmokeExecutionAuthorization
            and type(view) is SanitizedTrainingView
            and view.digest_protocol == SANITIZED_TRAINING_VIEW_PROTOCOL
            and view.preparation_protocol == PREPARATION_PROTOCOL
            and view.preparation_runner_digest == APPROVED_PREPARATION_RUNNER_DIGEST
            and view.condition_order == CONDITIONS
            and tuple(item.condition for item in view.conditions) == CONDITIONS
            and view.condition_digests == authorization.condition_digests
            and view.semantic_sha256 == authorization.training_view_sha256
            and authorization.training_view_sha256 == live_digest
            and authorization.condition_digests == condition_digests
            and authorization.tensor_array_digests == tensor_digests
            and authorization.schedule_bindings == schedule_bindings
            and (
                consumed is not None
                or all(
                item.train_tensor_sha256 == train_digest
                and item.train_source_ranges_sha256
                == _source_ranges_digest_contract(
                    item.condition,
                    item.train_tensors,
                    item.ordered_train_identities,
                    item.ordered_train_source_ranges,
                )
                and item.validation_tensor_sha256 == validation_digest
                and item.schedule_evidence_sha256 == schedule_digest
                for item, (_, train_digest, validation_digest), (
                    _,
                    _,
                    _,
                    schedule_digest,
                    _,
                ) in zip(
                    view.conditions,
                    tensor_digests,
                    schedule_bindings,
                    strict=True,
                )
                )
            )
        )
        if authorization.authority_kind in {
            "production_tracker_and_launch",
            "synthetic_production_equivalent",
        }:
            valid = valid and all(
                len(item.schedule.updates) == 1_000 for item in view.conditions
            )
            tracker_bytes, _ = _stable_read(
                authorization._tracker_path,
                maximum_bytes=max(authorization.approval.tracker_size, 1),
            )
            launch_bytes, _ = _stable_read(
                authorization._launch_path,
                maximum_bytes=max(len(authorization.launch_manifest._manifest_bytes), 1),
            )
            valid = (
                valid
                and tracker_bytes == authorization.approval._tracker_bytes
                and _sha256_bytes(tracker_bytes) == authorization.approval.tracker_sha256
                and launch_bytes == authorization.launch_manifest._manifest_bytes
                and _sha256_bytes(launch_bytes)
                == authorization.launch_manifest.manifest_file_sha256
                and authorization.approval.launch_manifest_approved is True
                and authorization.approval.approved_launch_manifest_sha256
                == authorization.launch_manifest.manifest_file_sha256
                and authorization.launch_manifest.sanitized_view_sha256 == live_digest
                and authorization.launch_manifest.condition_digests
                == condition_digests
                and authorization.launch_manifest.tensor_array_digests
                == tensor_digests
                and authorization.launch_manifest.schedule_bindings
                == schedule_bindings
                and authorization.launch_manifest.condition_order == CONDITIONS
                and authorization.launch_manifest.optimizer_updates_per_condition
                == 1_000
                and authorization.launch_manifest.checkpoint_updates
                == CHECKPOINT_UPDATES
            )
        if not valid:
            raise SmokeTrainingError(code)
        return consumed
    except SmokeTrainingError:
        raise
    except Exception:
        raise SmokeTrainingError(code) from None


def create_synthetic_smoke_training_view_for_tests(
    tensors_by_condition: Mapping[str, tuple[np.ndarray, np.ndarray, np.ndarray]],
    *,
    test_updates: int,
    microbatch_size: int = 2,
) -> SanitizedTrainingView:
    """Derive a marked test-only view; it can never satisfy production authority."""

    if (
        not isinstance(tensors_by_condition, Mapping)
        or tuple(tensors_by_condition) != CONDITIONS
        or type(test_updates) is not int
        or not 1 <= test_updates <= 1_000
        or type(microbatch_size) is not int
        or not 1 <= microbatch_size <= 16
    ):
        raise SmokeTrainingError(SMOKE_DATA_SCHEDULE_MISMATCH)
    interim: list[dict[str, Any]] = []
    for condition in CONDITIONS:
        arrays = tensors_by_condition[condition]
        if not isinstance(arrays, tuple) or len(arrays) != 3:
            raise SmokeTrainingError(SMOKE_DATA_SCHEDULE_MISMATCH)
        tensors = _derive_sanitized_tensor_arrays(*arrays)
        if (
            tensors.input_ids.shape[1] != 128
            or tensors.input_ids.dtype not in {np.dtype("uint16"), np.dtype("int64")}
            or tensors.attention_mask.dtype not in {np.dtype("uint8"), np.dtype("int64")}
            or tensors.token_type_ids.dtype not in {np.dtype("uint8"), np.dtype("int64")}
            or tensors.input_ids.shape[0] <= 0
        ):
            raise SmokeTrainingError(SMOKE_DATA_SCHEDULE_MISMATCH)
        identities = tuple(
            _sha256_bytes(
                canonical_json_bytes(
                    [
                        "neu_tiny_synthetic_sequence_v1",
                        condition,
                        index,
                        _sha256_bytes(tensors.input_ids[index].tobytes()),
                        _sha256_bytes(tensors.attention_mask[index].tobytes()),
                        _sha256_bytes(tensors.token_type_ids[index].tobytes()),
                    ]
                )
            )
            for index in range(tensors.input_ids.shape[0])
        )
        train_source_ranges = _synthetic_privacy_safe_source_ranges(
            condition,
            tensors,
            identities,
            split="train",
        )
        validation_source_ranges = _synthetic_privacy_safe_source_ranges(
            condition,
            tensors,
            identities,
            split="validation",
        )
        appearances: list[_SyntheticAppearance] = []
        updates: list[_SyntheticUpdatePlan] = []
        for update in range(1, test_updates + 1):
            update_start = len(appearances)
            update_counts: list[int] = []
            for index in range(tensors.input_ids.shape[0]):
                appearance = _SyntheticAppearance(index, identities[index], update - 1)
                appearances.append(appearance)
                sequence = _synthetic_sequence(
                    condition,
                    tensors,
                    identities,
                    train_source_ranges,
                    index,
                    split="train",
                )
                update_counts.append(
                    len(
                        mask_packed_sequence(
                            sequence,
                            seed=TRAINING_MASK_SEED,
                            mode="train",
                            visit=appearance.visit,
                        ).selected_positions
                    )
                )
            microbatches: list[_SyntheticMicrobatchPlan] = []
            for position, start in enumerate(
                range(update_start, len(appearances), microbatch_size)
            ):
                end = min(len(appearances), start + microbatch_size)
                local_start = start - update_start
                local_end = end - update_start
                microbatches.append(
                    _SyntheticMicrobatchPlan(
                        microbatch_index=position,
                        schedule_start_cursor=start,
                        schedule_end_cursor=end,
                        sequence_count=end - start,
                        selected_targets_by_seed=(
                            ("tiny_smoke_1", sum(update_counts[local_start:local_end])),
                        ),
                    )
                )
            total = sum(update_counts)
            if total <= 0:
                raise SmokeTrainingError(SMOKE_TARGET_COUNT_MISMATCH)
            updates.append(
                _SyntheticUpdatePlan(
                    update=update,
                    schedule_start_cursor=update_start,
                    schedule_end_cursor=len(appearances),
                    microbatches=tuple(microbatches),
                    selected_targets_by_seed=(("tiny_smoke_1", total),),
                )
            )
        schedule_payload = [
            condition,
            [
                [item.sequence_index, item.sequence_identity, item.visit]
                for item in appearances
            ],
            [
                [
                    item.update,
                    item.schedule_start_cursor,
                    item.schedule_end_cursor,
                    [
                        [
                            micro.microbatch_index,
                            micro.schedule_start_cursor,
                            micro.schedule_end_cursor,
                            micro.selected_targets_by_seed,
                        ]
                        for micro in item.microbatches
                    ],
                    item.selected_targets_by_seed,
                ]
                for item in updates
            ],
        ]
        schedule_identity = _sha256_bytes(canonical_json_bytes(schedule_payload))
        schedule = _SyntheticConditionSchedule(
            condition=condition,
            appearances=tuple(appearances),
            updates=tuple(updates),
            identity_sha256=schedule_identity,
            update_plan_sha256=_sha256_bytes(
                canonical_json_bytes(["synthetic_update_plan", schedule_payload[2]])
            ),
        )
        validation_sequences = tuple(
            _synthetic_sequence(
                condition,
                tensors,
                identities,
                validation_source_ranges,
                index,
                split="validation",
            )
            for index in range(tensors.input_ids.shape[0])
        )
        validation_examples = tuple(
            mask_packed_sequence(
                sequence,
                seed=VALIDATION_MASK_SEED,
                mode="validation",
            )
            for sequence in validation_sequences
        )
        validation_tensors = _derive_sanitized_tensor_arrays(
            np.asarray([item.input_ids for item in validation_examples], dtype=np.uint16),
            np.asarray(tensors.attention_mask, dtype=np.uint8),
            np.asarray(tensors.token_type_ids, dtype=np.uint8),
            np.asarray([item.labels for item in validation_examples], dtype=np.int32),
        )
        interim.append(
            {
                "condition": condition,
                "tensors": tensors,
                "identities": identities,
                "train_source_ranges": train_source_ranges,
                "schedule": schedule,
                "validation_tensors": validation_tensors,
                "validation_record": build_validation_mask_record(
                    validation_sequences,
                    seed=VALIDATION_MASK_SEED,
                ),
            }
        )
    schedule_plan_identity = _sha256_bytes(
        canonical_json_bytes(
            ["synthetic_schedule_plan", [item["schedule"].identity_sha256 for item in interim]]
        )
    )
    candidate_checksum = _sha256_bytes(
        canonical_json_bytes(
            [
                "synthetic_candidate",
                schedule_plan_identity,
                [
                    _sha256_bytes(item["tensors"].input_ids.tobytes())
                    for item in interim
                ],
            ]
        )
    )
    preparation_manifest = _sha256_bytes(
        canonical_json_bytes(["synthetic_preparation", candidate_checksum])
    )
    condition_views: list[SanitizedConditionTrainingView] = []
    for item in interim:
        selected = int(np.count_nonzero(item["validation_tensors"].labels != IGNORE_INDEX))
        if selected <= 0:
            raise SmokeTrainingError(SMOKE_TARGET_COUNT_MISMATCH)
        condition_view = object.__new__(SanitizedConditionTrainingView)
        for name, value in {
            "condition": item["condition"],
            "train_tensors": item["tensors"],
            "ordered_train_identities": item["identities"],
            "ordered_train_source_ranges": item["train_source_ranges"],
            "schedule": item["schedule"],
            "validation_tensors": item["validation_tensors"],
            "ordered_validation_identities": item["identities"],
            "validation_record": item["validation_record"],
            "aggregate_evidence": (
                ("train_sequences", item["tensors"].input_ids.shape[0]),
                ("validation_sequences", item["validation_tensors"].input_ids.shape[0]),
                ("validation_selected_targets", selected),
            ),
            "train_tensor_sha256": _sanitized_tensor_digest_contract(item["tensors"]),
            "train_source_ranges_sha256": _source_ranges_digest_contract(
                item["condition"],
                item["tensors"],
                item["identities"],
                item["train_source_ranges"],
            ),
            "validation_tensor_sha256": _sanitized_tensor_digest_contract(
                item["validation_tensors"]
            ),
            "schedule_evidence_sha256": _schedule_evidence_digest_contract(
                item["schedule"]
            ),
        }.items():
            object.__setattr__(condition_view, name, value)
        object.__setattr__(
            condition_view,
            "validation_plan_sha256",
            _sha256_bytes(
                canonical_json_bytes(
                    [
                        "neu_sanitized_fixed_validation_plan_v1",
                        item["condition"],
                        item["identities"],
                        [
                            type(item["validation_record"]).__name__,
                            [
                                [name, getattr(item["validation_record"], name)]
                                for name in type(item["validation_record"]).__dataclass_fields__
                            ],
                        ],
                        _sanitized_tensor_digest_contract(item["validation_tensors"]),
                        condition_view.aggregate_evidence,
                    ]
                )
            ),
        )
        object.__setattr__(
            condition_view,
            "semantic_sha256",
            _condition_view_semantic_sha256(condition_view),
        )
        condition_views.append(condition_view)
    result = object.__new__(SanitizedTrainingView)
    for name, value in {
        "authority_kind": "synthetic_test_only",
        "digest_protocol": SANITIZED_TRAINING_VIEW_PROTOCOL,
        "preparation_protocol": PREPARATION_PROTOCOL,
        "preparation_runner_digest": APPROVED_PREPARATION_RUNNER_DIGEST,
        "candidate_checksum_record_sha256": candidate_checksum,
        "preparation_manifest_sha256": preparation_manifest,
        "schedule_plan_identity_sha256": schedule_plan_identity,
        "training_mask_seed": TRAINING_MASK_SEED,
        "validation_mask_seed": VALIDATION_MASK_SEED,
        "condition_order": CONDITIONS,
        "condition_digests": tuple(
            (item.condition, item.semantic_sha256) for item in condition_views
        ),
        "conditions": tuple(condition_views),
    }.items():
        object.__setattr__(result, name, value)
    object.__setattr__(result, "semantic_sha256", _training_view_semantic_sha256(result))
    return result


def _derive_synthetic_execution_authorization_for_tests_impl(
    approval: CandidateApprovalEvidence,
    launch_manifest: SmokeLaunchManifest,
    training_view: SanitizedTrainingView,
    paired_initialization: PairedInitialization,
    *,
    token: object,
) -> SmokeExecutionAuthorization:
    launch_payload = {
        name: getattr(launch_manifest, name, None)
        for name in (
            "authority_kind",
            "candidate_checksum_record_sha256",
            "preparation_manifest_sha256",
            "schedule_plan_identity_sha256",
            "preparation_lineage_commit",
            "preparation_runner_digest",
            "executor_commit",
            "executor_closure_digest",
            "runtime_policy_sha256",
            "tiny_configuration_sha256",
            "seed_plan_sha256",
            "device",
            "learning_rate_protocol",
            "optimizer_protocol",
            "validation_points",
            "resume_protocol",
            "output_policy",
            "output_root_identity_sha256",
            "reporting_policy",
            "sanitized_view_sha256",
            "condition_digests",
            "tensor_array_digests",
            "schedule_bindings",
            "condition_order",
            "optimizer_updates_per_condition",
            "checkpoint_updates",
            "tracker_baseline_sha256",
            "tracker_baseline_size",
            "tracker_baseline_version",
            "tracker_baseline_canonical_date",
        )
    }
    expected_view_sha256 = _training_view_semantic_sha256(training_view)
    if (
        type(approval) is not CandidateApprovalEvidence
        or type(launch_manifest) is not SmokeLaunchManifest
        or type(training_view) is not SanitizedTrainingView
        or approval._factory_token is not token
        or launch_manifest._factory_token is not token
        or approval.authority_kind != "synthetic_test_only"
        or launch_manifest.authority_kind != "synthetic_test_only"
        or training_view.authority_kind != "synthetic_test_only"
        or training_view.training_mask_seed != TRAINING_MASK_SEED
        or training_view.validation_mask_seed != VALIDATION_MASK_SEED
        or tuple(item.condition for item in training_view.conditions) != CONDITIONS
        or approval.preparation_protocol != PREPARATION_PROTOCOL
        or approval.serialized_status != CANDIDATE_SERIALIZED_STATUS
        or approval.exact_unique_approval is not True
        or approval.launch_manifest_approved is not False
        or _SHA256_RE.fullmatch(approval.tracker_sha256) is None
        or approval.candidate_checksum_record_sha256
        != training_view.candidate_checksum_record_sha256
        or approval.preparation_manifest_sha256
        != training_view.preparation_manifest_sha256
        or approval.schedule_plan_identity_sha256
        != training_view.schedule_plan_identity_sha256
        or launch_manifest.candidate_checksum_record_sha256
        != approval.candidate_checksum_record_sha256
        or launch_manifest.preparation_manifest_sha256
        != approval.preparation_manifest_sha256
        or launch_manifest.schedule_plan_identity_sha256
        != approval.schedule_plan_identity_sha256
        or launch_manifest.tiny_configuration_sha256 != NEU_TINY.configuration_sha256()
        or launch_manifest.runtime_policy_sha256 != _runtime_policy_sha256()
        or launch_manifest.seed_plan_sha256 != _seed_plan_sha256()
        or launch_manifest.device != "cpu"
        or launch_manifest.validation_points != VALIDATION_POINTS
        or launch_manifest.resume_protocol != RESUME_PROTOCOL
        or launch_manifest.learning_rate_protocol != LEARNING_RATE_PROTOCOL
        or launch_manifest.optimizer_protocol != _optimizer_protocol()
        or launch_manifest.output_root_identity_sha256
        != _output_root_identity(APPROVED_OUTPUT_PARENT)
        or launch_manifest.preparation_lineage_commit
        != APPROVED_PREPARATION_LINEAGE_COMMIT
        or launch_manifest.preparation_runner_digest
        != APPROVED_PREPARATION_RUNNER_DIGEST
        or launch_manifest.tracker_baseline_sha256 != APPROVED_TRACKER_SHA256
        or launch_manifest.tracker_baseline_size != APPROVED_TRACKER_SIZE
        or launch_manifest.tracker_baseline_version != APPROVED_TRACKER_VERSION
        or launch_manifest.tracker_baseline_canonical_date
        != APPROVED_TRACKER_DATE
        or launch_manifest.manifest_sha256
        != _sha256_bytes(canonical_json_bytes(launch_payload))
        or training_view.semantic_sha256 != expected_view_sha256
        or any(
            item.semantic_sha256 != _condition_view_semantic_sha256(item)
            for item in training_view.conditions
        )
    ):
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    try:
        torch.use_deterministic_algorithms(True)
        verify_tiny_smoke_paired_initialization(paired_initialization)
    except Exception:
        raise SmokeTrainingError(SMOKE_INITIALIZATION_MISMATCH) from None
    condition_digests, tensor_digests, schedule_bindings = _view_anchor_components(
        training_view
    )
    payload = [
        SYNTHETIC_AUTHORITY_PROTOCOL,
        approval.tracker_sha256,
        approval.tracker_size,
        launch_manifest.manifest_sha256,
        paired_initialization.manifest.initial_state_sha256,
        training_view.semantic_sha256,
        condition_digests,
        tensor_digests,
        schedule_bindings,
        "cpu",
        1,
    ]
    result = object.__new__(SmokeExecutionAuthorization)
    for name, value in {
        "authority_kind": "synthetic_test_only",
        "approval": approval,
        "launch_manifest": launch_manifest,
        "initialization_manifest": paired_initialization.manifest,
        "training_view_sha256": training_view.semantic_sha256,
        "condition_digests": condition_digests,
        "tensor_array_digests": tensor_digests,
        "schedule_bindings": schedule_bindings,
        "device": "cpu",
        "maximum_concurrent_conditions": TINY_SMOKE_MAXIMUM_CONCURRENCY,
        "authorization_sha256": _sha256_bytes(canonical_json_bytes(payload)),
        "_tracker_path": approval._tracker_path,
        "_launch_path": launch_manifest._manifest_path,
        "_models": paired_initialization.models,
        "_training_view": training_view,
        "_factory_token": token,
    }.items():
        object.__setattr__(result, name, value)
    return result


def _unique_trainable_parameters(model: BertForMaskedLM) -> tuple[torch.nn.Parameter, ...]:
    material = tuple(parameter for parameter in model.parameters() if parameter.requires_grad)
    if len({id(parameter) for parameter in material}) != len(material):
        raise SmokeTrainingError(SMOKE_OPTIMIZER_SCHEDULER_FAILURE)
    return material


def _parameter_group_identity(model: BertForMaskedLM) -> str:
    names = tuple(
        name for name, parameter in model.named_parameters() if parameter.requires_grad
    )
    return _sha256_bytes(
        canonical_json_bytes(["neu_tiny_uniform_adamw_group_v1", names])
    )


def _create_optimizer_set_impl(
    authorization: SmokeExecutionAuthorization,
    *,
    token: object,
) -> TinySmokeOptimizerSet:
    if (
        type(authorization) is not SmokeExecutionAuthorization
        or authorization._factory_token is not token
        or authorization.device != "cpu"
    ):
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    _reanchor_consumed_view(
        authorization,
        code=SMOKE_APPROVAL_MISMATCH,
    )
    optimizers = {
        condition: _APPROVED_ADAMW_CLASS(
            _unique_trainable_parameters(authorization._models[condition]),
            lr=PEAK_LEARNING_RATE,
            betas=(0.9, 0.999),
            eps=1e-8,
            weight_decay=0.01,
            maximize=False,
            amsgrad=False,
            capturable=False,
            differentiable=False,
            foreach=False,
            fused=False,
        )
        for condition in CONDITIONS
    }
    try:
        verify_independent_tiny_smoke_optimizers(authorization._models, optimizers)
    except Exception:
        raise SmokeTrainingError(SMOKE_OPTIMIZER_SCHEDULER_FAILURE) from None
    result = object.__new__(TinySmokeOptimizerSet)
    for name, value in {
        "parameter_group_identities": tuple(
            (condition, _parameter_group_identity(authorization._models[condition]))
            for condition in CONDITIONS
        ),
        "_optimizers": MappingProxyType(optimizers),
        "_authorization_sha256": authorization.authorization_sha256,
        "_factory_token": token,
    }.items():
        object.__setattr__(result, name, value)
    return result


def _production_condition_runtime_authority_is_exact(
    authorization: SmokeExecutionAuthorization,
    condition: str,
    *,
    token: object,
) -> bool:
    """Revalidate the complete production authority at condition admission."""

    try:
        approval = authorization.approval
        launch = authorization.launch_manifest
        view = authorization._training_view
        if (
            type(approval) is not CandidateApprovalEvidence
            or type(launch) is not SmokeLaunchManifest
            or type(view) is not SanitizedTrainingView
            or approval._factory_token is not token
            or launch._factory_token is not token
            or approval.authority_kind != "production_tracker_and_launch"
            or launch.authority_kind != "production_tracker_and_launch"
            or approval.preparation_protocol != PREPARATION_PROTOCOL
            or approval.serialized_status != CANDIDATE_SERIALIZED_STATUS
            or approval.exact_unique_approval is not True
            or approval.launch_manifest_approved is not True
            or approval.approved_launch_manifest_sha256
            != launch.manifest_file_sha256
            or approval.candidate_checksum_record_sha256
            != view.candidate_checksum_record_sha256
            or approval.preparation_manifest_sha256
            != view.preparation_manifest_sha256
            or approval.schedule_plan_identity_sha256
            != view.schedule_plan_identity_sha256
            or launch.candidate_checksum_record_sha256
            != approval.candidate_checksum_record_sha256
            or launch.preparation_manifest_sha256
            != approval.preparation_manifest_sha256
            or launch.schedule_plan_identity_sha256
            != approval.schedule_plan_identity_sha256
            or launch.preparation_lineage_commit
            != APPROVED_PREPARATION_LINEAGE_COMMIT
            or launch.preparation_runner_digest
            != APPROVED_PREPARATION_RUNNER_DIGEST
            or launch.tracker_baseline_sha256 != APPROVED_TRACKER_SHA256
            or launch.tracker_baseline_size != APPROVED_TRACKER_SIZE
            or launch.tracker_baseline_version != APPROVED_TRACKER_VERSION
            or launch.tracker_baseline_canonical_date != APPROVED_TRACKER_DATE
            or launch.runtime_policy_sha256 != _runtime_policy_sha256()
            or launch.tiny_configuration_sha256 != NEU_TINY.configuration_sha256()
            or launch.seed_plan_sha256 != _seed_plan_sha256()
            or launch.device != TINY_SMOKE_EXECUTOR_DEVICE
            or launch.learning_rate_protocol != LEARNING_RATE_PROTOCOL
            or launch.optimizer_protocol != _optimizer_protocol()
            or launch.validation_points != VALIDATION_POINTS
            or launch.checkpoint_updates != CHECKPOINT_UPDATES
            or launch.resume_protocol != RESUME_PROTOCOL
            or launch.output_policy
            != "private_0700_files_0600_no_overwrite_completion_last"
            or launch.reporting_policy != "mechanics_only_private_non_scientific"
            or launch.condition_order != CONDITIONS
            or launch.optimizer_updates_per_condition != 1_000
            or launch.sanitized_view_sha256 != authorization.training_view_sha256
            or launch.condition_digests != authorization.condition_digests
            or launch.tensor_array_digests != authorization.tensor_array_digests
            or launch.schedule_bindings != authorization.schedule_bindings
            or view.training_mask_seed != TRAINING_MASK_SEED
            or view.validation_mask_seed != VALIDATION_MASK_SEED
            or view.condition_order != CONDITIONS
            or tuple(item.condition for item in view.conditions) != CONDITIONS
            or any(len(item.schedule.updates) != 1_000 for item in view.conditions)
            or tuple(item[0] for item in authorization.condition_digests) != CONDITIONS
            or tuple(item[0] for item in authorization.tensor_array_digests)
            != CONDITIONS
            or tuple(item[0] for item in authorization.schedule_bindings) != CONDITIONS
            or condition not in CONDITIONS
        ):
            return False
        condition_index = CONDITIONS.index(condition)
        if (
            authorization.condition_digests[condition_index][0] != condition
            or authorization.tensor_array_digests[condition_index][0] != condition
            or authorization.schedule_bindings[condition_index][0] != condition
        ):
            return False
        expected_launch = _production_launch_payload(
            view,
            authority_kind="production_tracker_and_launch",
            executor_commit=launch.executor_commit,
            executor_closure_digest=launch.executor_closure_digest,
        )
        tracker_bytes, tracker_status = _stable_read(
            authorization._tracker_path,
            maximum_bytes=max(approval.tracker_size, 1),
        )
        launch_bytes, launch_status = _stable_read(
            authorization._launch_path,
            maximum_bytes=max(len(launch._manifest_bytes), 1),
        )
        if (
            canonical_json_bytes(expected_launch) != launch._manifest_bytes
            or launch_bytes != launch._manifest_bytes
            or launch.manifest_sha256 != _sha256_bytes(launch_bytes)
            or launch.manifest_file_sha256 != _sha256_bytes(launch_bytes)
            or tracker_bytes != approval._tracker_bytes
            or approval.tracker_sha256 != _sha256_bytes(tracker_bytes)
            or approval.tracker_size != len(tracker_bytes)
        ):
            return False
        approved_launch_sha256, tracker_version, canonical_date = (
            _parse_tracker_launch_approval_record(
                tracker_bytes,
                authority_kind="production_tracker_and_launch",
                candidate_checksum=approval.candidate_checksum_record_sha256,
                preparation_manifest=approval.preparation_manifest_sha256,
                schedule_identity=approval.schedule_plan_identity_sha256,
                executor_commit=launch.executor_commit,
                executor_closure_digest=launch.executor_closure_digest,
                runtime_policy_sha256=launch.runtime_policy_sha256,
                output_parent=APPROVED_OUTPUT_PARENT,
            )
        )
        if (
            approved_launch_sha256 != launch.manifest_file_sha256
            or tracker_version != approval.tracker_version
            or canonical_date != approval.canonical_date
        ):
            return False
        if view.authority_kind == "production_loader":
            live_executor_commit, live_executor_closure = _executor_repository_identity(
                APPROVED_REPOSITORY_ROOT
            )
            return (
                os.environ.get("CSLM_TRACKED_ONLY_TEST") != "1"
                and authorization._tracker_path == APPROVED_TRACKER_PATH
                and authorization._launch_path == APPROVED_LAUNCH_MANIFEST_PATH
                and (
                    approval.tracker_sha256,
                    approval.tracker_size,
                )
                != (APPROVED_TRACKER_SHA256, APPROVED_TRACKER_SIZE)
                and approval.candidate_checksum_record_sha256
                == APPROVED_CANDIDATE_CHECKSUM_RECORD_SHA256
                and approval.preparation_manifest_sha256
                == APPROVED_PREPARATION_MANIFEST_SHA256
                and approval.schedule_plan_identity_sha256
                == APPROVED_SCHEDULE_PLAN_IDENTITY_SHA256
                and stat.S_IMODE(tracker_status.st_mode) == 0o644
                and stat.S_IMODE(launch_status.st_mode) == 0o600
                and launch.executor_commit == live_executor_commit
                and launch.executor_closure_digest == live_executor_closure
            )
        if (
            view.authority_kind != "synthetic_test_only"
            or os.environ.get("CSLM_TRACKED_ONLY_TEST") != "1"
            or authorization._tracker_path == APPROVED_TRACKER_PATH
            or authorization._launch_path == APPROVED_LAUNCH_MANIFEST_PATH
            or stat.S_IMODE(tracker_status.st_mode) != 0o600
            or stat.S_IMODE(launch_status.st_mode) != 0o600
        ):
            return False
        return True
    except Exception:
        return False


def _begin_condition_runtime_impl(
    authorization: SmokeExecutionAuthorization,
    optimizers: TinySmokeOptimizerSet,
    condition: str,
    *,
    token: object,
) -> TinySmokeConditionRuntime:
    if (
        type(authorization) is not SmokeExecutionAuthorization
        or type(optimizers) is not TinySmokeOptimizerSet
    ):
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    expected_authorization_sha256 = _authorization_semantic_sha256(
        authorization.authority_kind,
        authorization.approval,
        authorization.launch_manifest,
        authorization.initialization_manifest,
        authorization.training_view_sha256,
        authorization.condition_digests,
        authorization.tensor_array_digests,
        authorization.schedule_bindings,
    )
    if (
        type(authorization) is not SmokeExecutionAuthorization
        or type(optimizers) is not TinySmokeOptimizerSet
        or authorization._factory_token is not token
        or optimizers._factory_token is not token
        or optimizers._authorization_sha256 != authorization.authorization_sha256
        or authorization.authority_kind not in {
            "synthetic_test_only",
            "synthetic_production_equivalent",
            "production_tracker_and_launch",
        }
        or authorization.device != TINY_SMOKE_EXECUTOR_DEVICE
        or authorization.maximum_concurrent_conditions
        != TINY_SMOKE_MAXIMUM_CONCURRENCY
        or authorization.training_view_sha256
        != authorization._training_view.semantic_sha256
        or authorization._training_view.training_mask_seed != TRAINING_MASK_SEED
        or authorization._training_view.validation_mask_seed != VALIDATION_MASK_SEED
        or tuple(item.condition for item in authorization._training_view.conditions)
        != CONDITIONS
        or authorization.authorization_sha256 != expected_authorization_sha256
        or condition not in CONDITIONS
        or (
            authorization.authority_kind == "production_tracker_and_launch"
            and not _production_condition_runtime_authority_is_exact(
                authorization,
                condition,
                token=token,
            )
        )
    ):
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    condition_view = _reanchor_consumed_view(
        authorization,
        condition=condition,
        code=SMOKE_APPROVAL_MISMATCH,
    )
    assert condition_view is not None
    try:
        torch.set_num_threads(1)
        if (
            torch.get_num_threads() != 1
            or not torch.are_deterministic_algorithms_enabled()
        ):
            raise SmokeTrainingError(SMOKE_DEVICE_RUNTIME_MISMATCH)
    except SmokeTrainingError:
        raise
    except Exception:
        raise SmokeTrainingError(SMOKE_DEVICE_RUNTIME_MISMATCH) from None
    runtime = object.__new__(TinySmokeConditionRuntime)
    for name, value in {
        "condition": condition,
        "completed_update": 0,
        "at_update_boundary": True,
        "learning_rate_state": learning_rate_state_after_update(0),
        "_authorization": authorization,
        "_model": authorization._models[condition],
        "_optimizer": optimizers._optimizers[condition],
        "_condition_view": condition_view,
        "_loss_history": [],
        "_target_count_history": [],
        "_mask_history": [],
        "_validation_history": [],
        "_factory_token": token,
    }.items():
        object.__setattr__(runtime, name, value)
    runtime._model.train()
    return runtime


def _optimizer_steps(
    optimizer: torch.optim.AdamW,
    parameters: Sequence[torch.nn.Parameter],
) -> dict[int, int]:
    result: dict[int, int] = {}
    for parameter in parameters:
        state = optimizer.state.get(parameter, {})
        value = state.get("step", 0)
        if isinstance(value, torch.Tensor):
            if value.numel() != 1 or value.device.type != "cpu":
                raise SmokeTrainingError(SMOKE_OPTIMIZER_SCHEDULER_FAILURE)
            value = value.item()
        if isinstance(value, bool) or not isinstance(value, int | float) or int(value) != value:
            raise SmokeTrainingError(SMOKE_OPTIMIZER_SCHEDULER_FAILURE)
        result[id(parameter)] = int(value)
    return result


def _grads_are_clear(parameters: Sequence[torch.nn.Parameter]) -> bool:
    return all(parameter.grad is None for parameter in parameters)


def _unwrapped_callable(value: Callable[..., object]) -> Callable[..., object]:
    seen: set[int] = set()
    while hasattr(value, "__wrapped__") and id(value) not in seen:
        seen.add(id(value))
        value = value.__wrapped__  # type: ignore[attr-defined]
    return value


def _verify_runtime_optimizer(
    optimizer: torch.optim.AdamW,
    parameters: Sequence[torch.nn.Parameter],
    *,
    expected_lr: float | None = None,
    adamw_class: type[torch.optim.AdamW] = _APPROVED_ADAMW_CLASS,
    adamw_step: Callable[..., object] = _APPROVED_ADAMW_STEP,
) -> None:
    if (
        type(optimizer) is not adamw_class
        or _unwrapped_callable(type(optimizer).step)
        is not _unwrapped_callable(adamw_step)
        or "step" in vars(optimizer)
        or len(optimizer.param_groups) != 1
    ):
        raise SmokeTrainingError(SMOKE_OPTIMIZER_SCHEDULER_FAILURE)
    group = optimizer.param_groups[0]
    defaults = optimizer.defaults
    if (
        tuple(id(parameter) for parameter in group["params"])
        != tuple(id(parameter) for parameter in parameters)
        or len({id(parameter) for parameter in group["params"]}) != len(parameters)
        or (expected_lr is not None and group["lr"] != expected_lr)
        or group["betas"] != (0.9, 0.999)
        or group["eps"] != 1e-8
        or group["weight_decay"] != 0.01
        or group.get("maximize") is not False
        or group.get("amsgrad") is not False
        or group.get("capturable") is not False
        or group.get("differentiable") is not False
        or group.get("foreach") is not False
        or group.get("fused") is not False
        or defaults.get("betas") != (0.9, 0.999)
        or defaults.get("eps") != 1e-8
        or defaults.get("weight_decay") != 0.01
        or defaults.get("maximize") is not False
        or defaults.get("amsgrad") is not False
        or defaults.get("capturable") is not False
        or defaults.get("differentiable") is not False
        or defaults.get("foreach") is not False
        or defaults.get("fused") is not False
    ):
        raise SmokeTrainingError(SMOKE_OPTIMIZER_SCHEDULER_FAILURE)


def _validate_masked_batch(
    original: torch.Tensor,
    attention: torch.Tensor,
    labels: torch.Tensor,
) -> None:
    selected = labels != IGNORE_INDEX
    if torch.any(selected & (attention != 1)):
        raise SmokeTrainingError(SMOKE_MASKING_MISMATCH)
    for special in SPECIAL_TOKEN_IDS:
        if torch.any(selected & (original == special)):
            raise SmokeTrainingError(SMOKE_MASKING_MISMATCH)


def _execute_next_update_impl(
    runtime: TinySmokeConditionRuntime,
    *,
    token: object,
) -> UpdateMechanicsResult:
    anchored_view = _reanchor_consumed_view(
        runtime._authorization,
        condition=runtime.condition,
        code=SMOKE_DATA_SCHEDULE_MISMATCH,
    )
    if (
        type(runtime) is not TinySmokeConditionRuntime
        or runtime._factory_token is not token
        or not runtime.at_update_boundary
        or runtime.completed_update >= len(runtime._condition_view.schedule.updates)
        or runtime._model.training is not True
        or runtime._condition_view is not anchored_view
        or runtime._condition_view.semantic_sha256
        != _condition_view_semantic_sha256(runtime._condition_view)
        or any(parameter.device.type != "cpu" for parameter in runtime._model.parameters())
    ):
        raise SmokeTrainingError(SMOKE_DATA_SCHEDULE_MISMATCH)
    update_number = runtime.completed_update + 1
    plan = runtime._condition_view.schedule.updates[update_number - 1]
    expected_validation_updates = tuple(
        update
        for update in VALIDATION_POINTS
        if update <= runtime.completed_update
        and update <= len(runtime._condition_view.schedule.updates)
    )
    if (
        plan.update != update_number
        or runtime.condition != runtime._condition_view.condition
        or len(runtime._loss_history) != runtime.completed_update
        or len(runtime._target_count_history) != runtime.completed_update
        or len(runtime._mask_history) != runtime.completed_update
        or tuple(item[0] for item in runtime._validation_history)
        != expected_validation_updates
        or runtime.learning_rate_state
        != learning_rate_state_after_update(runtime.completed_update)
    ):
        raise SmokeTrainingError(SMOKE_DATA_SCHEDULE_MISMATCH)
    parameters = _unique_trainable_parameters(runtime._model)
    _verify_runtime_optimizer(
        runtime._optimizer,
        parameters,
        expected_lr=(
            PEAK_LEARNING_RATE
            if runtime.completed_update == 0
            else approved_learning_rate(runtime.completed_update)
        ),
    )
    if set(_optimizer_steps(runtime._optimizer, parameters).values()) != {
        runtime.completed_update
    }:
        raise SmokeTrainingError(SMOKE_DATA_SCHEDULE_MISMATCH)
    if not _grads_are_clear(parameters):
        raise SmokeTrainingError(SMOKE_NONFINITE_GRADIENT)
    runtime._optimizer.zero_grad(set_to_none=True)
    if not _grads_are_clear(parameters):
        raise SmokeTrainingError(SMOKE_NONFINITE_GRADIENT)
    runtime.at_update_boundary = False
    contributions: list[MicrobatchLoss] = []
    mask_checksums: list[str] = []
    failure: str | None = None
    try:
        for microbatch_position, microbatch in enumerate(plan.microbatches):
            if (
                microbatch.microbatch_index != microbatch_position
                or not (
                    plan.schedule_start_cursor
                    <= microbatch.schedule_start_cursor
                    < microbatch.schedule_end_cursor
                    <= plan.schedule_end_cursor
                )
            ):
                raise SmokeTrainingError(SMOKE_DATA_SCHEDULE_MISMATCH)
            appearances = runtime._condition_view.schedule.appearances[
                microbatch.schedule_start_cursor : microbatch.schedule_end_cursor
            ]
            masked_examples = []
            original_rows = []
            attention_rows = []
            type_rows = []
            for appearance in appearances:
                sequence = _synthetic_sequence(
                    runtime.condition,
                    runtime._condition_view.train_tensors,
                    runtime._condition_view.ordered_train_identities,
                    runtime._condition_view.ordered_train_source_ranges,
                    appearance.sequence_index,
                    split="train",
                )
                if sequence.example_identity != appearance.sequence_identity:
                    raise SmokeTrainingError(SMOKE_DATA_SCHEDULE_MISMATCH)
                masked = mask_packed_sequence(
                    sequence,
                    seed=TRAINING_MASK_SEED,
                    mode="train",
                    visit=appearance.visit,
                )
                masked_examples.append(masked)
                original_rows.append(sequence.input_ids)
                attention_rows.append(sequence.attention_mask)
                type_rows.append(sequence.token_type_ids)
                mask_checksums.append(masked.checksum_sha256)
            input_ids = torch.tensor(
                [item.input_ids for item in masked_examples], dtype=torch.long
            )
            labels = torch.tensor(
                [item.labels for item in masked_examples], dtype=torch.long
            )
            attention = torch.tensor(attention_rows, dtype=torch.long)
            token_types = torch.tensor(type_rows, dtype=torch.long)
            original = torch.tensor(original_rows, dtype=torch.long)
            target_count = int(torch.count_nonzero(labels != IGNORE_INDEX).item())
            expected_microbatch_count = dict(microbatch.selected_targets_by_seed).get(
                "tiny_smoke_1"
            )
            if target_count != expected_microbatch_count:
                raise SmokeTrainingError(SMOKE_TARGET_COUNT_MISMATCH)
            _validate_masked_batch(original, attention, labels)
            dropout_seed = derive_tiny_dropout_seed(
                runtime.condition,
                update_number,
                microbatch_position,
            )
            with torch.random.fork_rng(devices=[]):
                torch.manual_seed(dropout_seed)
                outputs = runtime._model(
                    input_ids=input_ids,
                    attention_mask=attention,
                    token_type_ids=token_types,
                    return_dict=True,
                )
                numerator = functional.cross_entropy(
                    outputs.logits.reshape(-1, VOCAB_SIZE),
                    labels.reshape(-1),
                    ignore_index=IGNORE_INDEX,
                    reduction="sum",
                )
                if not bool(torch.isfinite(numerator).item()):
                    raise SmokeTrainingError(SMOKE_NONFINITE_LOSS)
                numerator.backward()
            detached = float(numerator.detach().item())
            contributions.append(MicrobatchLoss(detached, target_count))
        target_count = sum(item.actual_selected_target_count for item in contributions)
        expected_update_count = dict(plan.selected_targets_by_seed).get("tiny_smoke_1")
        if target_count <= 0 or target_count != expected_update_count:
            raise SmokeTrainingError(SMOKE_TARGET_COUNT_MISMATCH)
        normalized = normalize_complete_update_loss(contributions)
        if (
            normalized.actual_selected_target_count != target_count
            or not math.isfinite(normalized.normalized_loss)
            or normalized.normalized_loss
            != normalized.target_cross_entropy_numerator / target_count
        ):
            raise SmokeTrainingError(SMOKE_LOSS_NORMALIZATION_MISMATCH)
        reciprocal = 1.0 / target_count
        active_parameters = tuple(
            parameter for parameter in parameters if parameter.grad is not None
        )
        if not active_parameters:
            raise SmokeTrainingError(SMOKE_NONFINITE_GRADIENT)
        with torch.no_grad():
            for parameter in active_parameters:
                if not bool(torch.isfinite(parameter.grad).all().item()):
                    raise SmokeTrainingError(SMOKE_NONFINITE_GRADIENT)
                parameter.grad.mul_(reciprocal)
                if not bool(torch.isfinite(parameter.grad).all().item()):
                    raise SmokeTrainingError(SMOKE_NONFINITE_GRADIENT)
        clipping = authorize_gradient_clipping(normalized)
        authorize_adamw_step(clipping)
        try:
            unclipped = torch.nn.utils.clip_grad_norm_(
                active_parameters,
                max_norm=1.0,
                norm_type=2.0,
                error_if_nonfinite=True,
                foreach=False,
            )
        except Exception:
            raise SmokeTrainingError(SMOKE_GRADIENT_CLIPPING_FAILURE) from None
        unclipped_value = float(unclipped.item())
        if not math.isfinite(unclipped_value):
            raise SmokeTrainingError(SMOKE_GRADIENT_CLIPPING_FAILURE)
        rate = approved_learning_rate(update_number)
        if len(runtime._optimizer.param_groups) != 1:
            raise SmokeTrainingError(SMOKE_OPTIMIZER_SCHEDULER_FAILURE)
        for group in runtime._optimizer.param_groups:
            group["lr"] = rate
        _verify_runtime_optimizer(
            runtime._optimizer,
            parameters,
            expected_lr=rate,
        )
        if any(
            parameter.grad is not None
            and not bool(torch.isfinite(parameter.grad).all().item())
            for parameter in parameters
        ):
            raise SmokeTrainingError(SMOKE_NONFINITE_GRADIENT)
        before_steps = _optimizer_steps(runtime._optimizer, active_parameters)
        runtime._optimizer.step()
        after_steps = _optimizer_steps(runtime._optimizer, active_parameters)
        if any(
            after_steps[id(parameter)] != before_steps[id(parameter)] + 1
            for parameter in active_parameters
        ) or set(_optimizer_steps(runtime._optimizer, parameters).values()) != {
            update_number
        }:
            raise SmokeTrainingError(SMOKE_OPTIMIZER_SCHEDULER_FAILURE)
        runtime._optimizer.zero_grad(set_to_none=True)
        if not _grads_are_clear(parameters):
            raise SmokeTrainingError(SMOKE_NONFINITE_GRADIENT)
        state = learning_rate_state_after_update(update_number)
        runtime.completed_update = update_number
        runtime.learning_rate_state = state
        runtime._loss_history.append(normalized.normalized_loss)
        runtime._target_count_history.append(target_count)
        mask_checksum = _sha256_bytes(canonical_json_bytes(mask_checksums))
        runtime._mask_history.append(mask_checksum)
        runtime.at_update_boundary = True
        result = object.__new__(UpdateMechanicsResult)
        for name, value in {
            "condition": runtime.condition,
            "completed_update": update_number,
            "selected_target_count": target_count,
            "normalized_loss": normalized.normalized_loss,
            "unclipped_gradient_norm": unclipped_value,
            "learning_rate_state": state,
            "mask_checksum_sha256": mask_checksum,
        }.items():
            object.__setattr__(result, name, value)
        return result
    except SmokeTrainingError as error:
        failure = error.code
    except Exception:
        failure = SMOKE_DATA_SCHEDULE_MISMATCH
    if failure is None:
        failure = SMOKE_DATA_SCHEDULE_MISMATCH
    raise SmokeTrainingError(failure)


def _numpy_rng_equal(first: tuple[Any, ...], second: tuple[Any, ...]) -> bool:
    return (
        first[0] == second[0]
        and np.array_equal(first[1], second[1])
        and first[2:] == second[2:]
    )


def _validate_condition_impl(
    runtime: TinySmokeConditionRuntime,
    *,
    token: object,
) -> ValidationMechanicsResult:
    anchored_view = _reanchor_consumed_view(
        runtime._authorization,
        condition=runtime.condition,
        code=SMOKE_VALIDATION_MISMATCH,
    )
    if (
        type(runtime) is not TinySmokeConditionRuntime
        or runtime._factory_token is not token
        or not runtime.at_update_boundary
        or runtime.completed_update not in VALIDATION_POINTS
        or tuple(item[0] for item in runtime._validation_history)
        != tuple(point for point in VALIDATION_POINTS if point < runtime.completed_update)
        or runtime._model.training is not True
        or runtime._condition_view is not anchored_view
        or runtime._condition_view.semantic_sha256
        != _condition_view_semantic_sha256(runtime._condition_view)
    ):
        raise SmokeTrainingError(SMOKE_VALIDATION_MISMATCH)
    tensors = runtime._condition_view.validation_tensors
    labels = tensors.labels
    if labels is None:
        raise SmokeTrainingError(SMOKE_VALIDATION_MISMATCH)
    python_state = random.getstate()
    numpy_state_value = np.random.get_state()
    numpy_state = (
        numpy_state_value[0],
        numpy_state_value[1].copy(),
        numpy_state_value[2],
        numpy_state_value[3],
        numpy_state_value[4],
    )
    torch_state = torch.get_rng_state().clone()
    numerator = 0.0
    target_count = 0
    failure = False
    runtime._model.eval()
    try:
        with torch.inference_mode():
            for start in range(0, tensors.input_ids.shape[0], MAX_VALIDATION_BATCH_SIZE):
                end = min(tensors.input_ids.shape[0], start + MAX_VALIDATION_BATCH_SIZE)
                batch_inputs = torch.from_numpy(
                    np.array(tensors.input_ids[start:end], dtype=np.int64, copy=True)
                )
                batch_attention = torch.from_numpy(
                    np.array(tensors.attention_mask[start:end], dtype=np.int64, copy=True)
                )
                batch_types = torch.from_numpy(
                    np.array(tensors.token_type_ids[start:end], dtype=np.int64, copy=True)
                )
                batch_labels = torch.from_numpy(
                    np.array(labels[start:end], dtype=np.int64, copy=True)
                )
                batch_count = int(
                    torch.count_nonzero(batch_labels != IGNORE_INDEX).item()
                )
                outputs = runtime._model(
                    input_ids=batch_inputs,
                    attention_mask=batch_attention,
                    token_type_ids=batch_types,
                    return_dict=True,
                )
                batch_numerator = functional.cross_entropy(
                    outputs.logits.reshape(-1, VOCAB_SIZE),
                    batch_labels.reshape(-1),
                    ignore_index=IGNORE_INDEX,
                    reduction="sum",
                )
                if not bool(torch.isfinite(batch_numerator).item()):
                    raise SmokeTrainingError(SMOKE_VALIDATION_MISMATCH)
                numerator += float(batch_numerator.item())
                target_count += batch_count
    except Exception:
        failure = True
    finally:
        try:
            random.setstate(python_state)
            np.random.set_state(numpy_state)
            torch.set_rng_state(torch_state)
            runtime._model.train()
        except Exception:
            failure = True
    expected = dict(runtime._condition_view.aggregate_evidence).get(
        "validation_selected_targets"
    )
    if (
        failure
        or target_count <= 0
        or target_count != expected
        or not math.isfinite(numerator)
        or random.getstate() != python_state
        or not _numpy_rng_equal(np.random.get_state(), numpy_state)
        or not torch.equal(torch.get_rng_state(), torch_state)
        or runtime._model.training is not True
    ):
        raise SmokeTrainingError(SMOKE_VALIDATION_MISMATCH)
    normalized = numerator / target_count
    semantic = _sha256_bytes(
        canonical_json_bytes(
            [
                "neu_tiny_fixed_validation_result_v1",
                runtime.condition,
                runtime.completed_update,
                target_count,
                normalized.hex(),
            ]
        )
    )
    runtime._validation_history.append(
        (runtime.completed_update, normalized, target_count, semantic)
    )
    result = object.__new__(ValidationMechanicsResult)
    for name, value in {
        "condition": runtime.condition,
        "completed_update": runtime.completed_update,
        "selected_target_count": target_count,
        "normalized_loss": normalized,
        "semantic_sha256": semantic,
    }.items():
        object.__setattr__(result, name, value)
    return result


def _update_tensor_hash(digest: Any, tensor: torch.Tensor) -> None:
    material = tensor.detach().cpu().contiguous()
    digest.update(
        canonical_json_bytes([str(material.dtype), list(material.shape)])
    )
    digest.update(material.numpy().tobytes(order="C"))


def _semantic_hash(value: object) -> str:
    digest = hashlib.sha256()

    def update(item: object) -> None:
        if isinstance(item, torch.Tensor):
            digest.update(b"torch\0")
            _update_tensor_hash(digest, item)
        elif isinstance(item, np.ndarray):
            digest.update(b"numpy\0")
            digest.update(canonical_json_bytes([str(item.dtype), list(item.shape)]))
            digest.update(item.tobytes(order="C"))
        elif isinstance(item, Mapping):
            digest.update(b"mapping\0")
            for key in sorted(item, key=lambda candidate: repr(candidate)):
                update(key)
                update(item[key])
        elif isinstance(item, tuple | list):
            digest.update(type(item).__name__.encode("ascii") + b"\0")
            for value_item in item:
                update(value_item)
        elif isinstance(item, bytes):
            digest.update(b"bytes\0" + len(item).to_bytes(8, "big") + item)
        elif item is None or isinstance(item, str | int | float | bool):
            digest.update(canonical_json_bytes([type(item).__name__, item]))
        else:
            raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)

    update(value)
    return digest.hexdigest()


def runtime_semantic_sha256(runtime: TinySmokeConditionRuntime) -> str:
    if type(runtime) is not TinySmokeConditionRuntime or not runtime.at_update_boundary:
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    return _semantic_hash(
        {
            "condition": runtime.condition,
            "completed_update": runtime.completed_update,
            "learning_rate": {
                "completed": runtime.learning_rate_state.completed_update,
                "last": runtime.learning_rate_state.last_step_learning_rate,
                "next": runtime.learning_rate_state.next_step_learning_rate,
                "protocol": runtime.learning_rate_state.protocol,
            },
            "loss_history": tuple(runtime._loss_history),
            "mask_history": tuple(runtime._mask_history),
            "model": runtime._model.state_dict(),
            "optimizer": runtime._optimizer.state_dict(),
            "target_count_history": tuple(runtime._target_count_history),
            "validation_history": tuple(runtime._validation_history),
        }
    )


def _rng_payload() -> dict[str, object]:
    numpy_state = np.random.get_state()
    return {
        "python": random.getstate(),
        "numpy": {
            "generator": numpy_state[0],
            "keys": torch.from_numpy(numpy_state[1].copy()),
            "position": numpy_state[2],
            "has_gauss": numpy_state[3],
            "cached_gaussian": numpy_state[4],
        },
        "torch_cpu": torch.get_rng_state().clone(),
    }


def _checkpoint_state(runtime: TinySmokeConditionRuntime) -> dict[str, object]:
    if type(runtime) is not TinySmokeConditionRuntime:
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    anchored_view = _reanchor_consumed_view(
        runtime._authorization,
        condition=runtime.condition,
        code=SMOKE_RESUME_MISMATCH,
    )
    expected_validation_updates = tuple(
        update
        for update in VALIDATION_POINTS
        if update <= runtime.completed_update
        and update <= len(runtime._condition_view.schedule.updates)
    )
    if (
        not runtime.at_update_boundary
        or runtime._condition_view is not anchored_view
        or runtime.completed_update not in CHECKPOINT_UPDATES
        or runtime._model.training is not True
        or runtime.learning_rate_state
        != learning_rate_state_after_update(runtime.completed_update)
        or len(runtime._loss_history) != runtime.completed_update
        or len(runtime._target_count_history) != runtime.completed_update
        or len(runtime._mask_history) != runtime.completed_update
        or tuple(item[0] for item in runtime._validation_history)
        != expected_validation_updates
    ):
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    parameters = _unique_trainable_parameters(runtime._model)
    try:
        _verify_runtime_optimizer(
            runtime._optimizer,
            parameters,
            expected_lr=(
                PEAK_LEARNING_RATE
                if runtime.completed_update == 0
                else approved_learning_rate(runtime.completed_update)
            ),
        )
        if set(_optimizer_steps(runtime._optimizer, parameters).values()) != {
            runtime.completed_update
        }:
            raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    except SmokeTrainingError:
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH) from None
    authorization = runtime._authorization
    state: dict[str, object] = {
        "protocol": CHECKPOINT_PROTOCOL,
        "condition": runtime.condition,
        "device": "cpu",
        "completed_optimizer_update": runtime.completed_update,
        "at_update_boundary": True,
        "candidate_checksum_record_sha256": (
            authorization.approval.candidate_checksum_record_sha256
        ),
        "preparation_manifest_sha256": (
            authorization.approval.preparation_manifest_sha256
        ),
        "schedule_plan_identity_sha256": (
            authorization.approval.schedule_plan_identity_sha256
        ),
        "schedule_identity_sha256": runtime._condition_view.schedule.identity_sha256,
        "schedule_update_plan_sha256": (
            runtime._condition_view.schedule.update_plan_sha256
        ),
        "condition_view_sha256": runtime._condition_view.semantic_sha256,
        "train_tensor_sha256": runtime._condition_view.train_tensor_sha256,
        "train_source_ranges_sha256": (
            runtime._condition_view.train_source_ranges_sha256
        ),
        "validation_tensor_sha256": runtime._condition_view.validation_tensor_sha256,
        "schedule_evidence_sha256": runtime._condition_view.schedule_evidence_sha256,
        "validation_plan_sha256": runtime._condition_view.validation_plan_sha256,
        "training_view_sha256": authorization.training_view_sha256,
        "authorization_sha256": authorization.authorization_sha256,
        "launch_manifest_sha256": authorization.launch_manifest.manifest_sha256,
        "tracker_authority": _tracker_authority_binding(authorization),
        "executor_lineage": {
            "commit": authorization.launch_manifest.executor_commit,
            "closure_digest": authorization.launch_manifest.executor_closure_digest,
            "protocol": EXECUTOR_PROTOCOL,
        },
        "initialization_manifest": {
            "configuration_sha256": authorization.initialization_manifest.configuration_sha256,
            "initial_state_sha256": authorization.initialization_manifest.initial_state_sha256,
            "parameter_count": authorization.initialization_manifest.trainable_parameter_count,
            "tied_parameter_groups": authorization.initialization_manifest.tied_parameter_groups,
        },
        "model_state": runtime._model.state_dict(),
        "model_ties": tied_parameter_groups(runtime._model),
        "optimizer_state": runtime._optimizer.state_dict(),
        "optimizer_group_identity": _parameter_group_identity(runtime._model),
        "optimizer_protocol": _optimizer_protocol(),
        "learning_rate_state": {
            "completed_update": runtime.learning_rate_state.completed_update,
            "last_step_learning_rate": runtime.learning_rate_state.last_step_learning_rate,
            "next_step_learning_rate": runtime.learning_rate_state.next_step_learning_rate,
            "protocol": runtime.learning_rate_state.protocol,
        },
        "seeds": {
            "dropout_base": DROPOUT_BASE_SEED,
            "dropout_protocol": DROPOUT_PROTOCOL,
            "model": MODEL_SEED,
            "training_mask": TRAINING_MASK_SEED,
            "validation_mask": VALIDATION_MASK_SEED,
        },
        "runtime": {
            "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
            "device": "cpu",
            "intraop_threads": torch.get_num_threads(),
            "maximum_concurrency": 1,
            "numpy": importlib.metadata.version("numpy"),
            "python": sys.version.split()[0],
            "torch": importlib.metadata.version("torch"),
            "transformers": importlib.metadata.version("transformers"),
        },
        "rng": _rng_payload(),
        "histories": {
            "loss": tuple(runtime._loss_history),
            "targets": tuple(runtime._target_count_history),
            "masks": tuple(runtime._mask_history),
            "validation": tuple(runtime._validation_history),
        },
        "history_checksums": {
            "loss": _semantic_hash(tuple(runtime._loss_history)),
            "targets": _semantic_hash(tuple(runtime._target_count_history)),
            "masks": _semantic_hash(tuple(runtime._mask_history)),
            "validation": _semantic_hash(tuple(runtime._validation_history)),
        },
        "resume": {
            "protocol": RESUME_PROTOCOL,
            "next_update": runtime.completed_update + 1,
            "schedule_update_count": len(runtime._condition_view.schedule.updates),
        },
    }
    state["semantic_sha256"] = _semantic_hash(state)
    return state


def _checkpoint_envelope_identity(files: Mapping[str, bytes]) -> str:
    return _sha256_bytes(
        canonical_json_bytes(
            [
                "neu_tiny_checkpoint_external_envelope_v2",
                [
                    [name, _sha256_bytes(files[name]), len(files[name])]
                    for name in sorted(files)
                ],
            ]
        )
    )


def checkpoint_envelope_for_runtime(
    runtime: TinySmokeConditionRuntime,
) -> CheckpointEnvelope:
    """Build a factory-only external envelope before any state can be decoded."""

    state = _checkpoint_state(runtime)
    buffer = io.BytesIO()
    torch.save(state, buffer)
    state_bytes = buffer.getvalue()
    authorization = runtime._authorization
    manifest = {
        "authorization_sha256": authorization.authorization_sha256,
        "candidate_checksum_record_sha256": (
            authorization.approval.candidate_checksum_record_sha256
        ),
        "checkpoint_namespace": f"checkpoint-{runtime.completed_update:04d}",
        "checkpoint_protocol": CHECKPOINT_PROTOCOL,
        "completed_optimizer_update": runtime.completed_update,
        "condition": runtime.condition,
        "condition_view_sha256": runtime._condition_view.semantic_sha256,
        "train_source_ranges_sha256": (
            runtime._condition_view.train_source_ranges_sha256
        ),
        "device": "cpu",
        "executor_closure_digest": authorization.launch_manifest.executor_closure_digest,
        "executor_commit": authorization.launch_manifest.executor_commit,
        "history_checksums": state["history_checksums"],
        "launch_manifest_sha256": authorization.launch_manifest.manifest_sha256,
        "tracker_authority": _tracker_authority_binding(authorization),
        "model_state_sha256": _semantic_hash(state["model_state"]),
        "optimizer_state_sha256": _semantic_hash(state["optimizer_state"]),
        "preparation_manifest_sha256": (
            authorization.approval.preparation_manifest_sha256
        ),
        "rng_state_sha256": _semantic_hash(state["rng"]),
        "runtime_sha256": _semantic_hash(state["runtime"]),
        "sanitized_view_sha256": authorization.training_view_sha256,
        "schedule_plan_identity_sha256": (
            authorization.approval.schedule_plan_identity_sha256
        ),
        "semantic_state_sha256": state["semantic_sha256"],
        "state_sha256": _sha256_bytes(state_bytes),
        "validation_history_sha256": state["history_checksums"]["validation"],
    }
    manifest_bytes = canonical_json_bytes(manifest)
    inventory = {
        "algorithm": "sha256",
        "files": {
            "checkpoint_manifest.json": {
                "mode": "0600",
                "sha256": _sha256_bytes(manifest_bytes),
                "size": len(manifest_bytes),
            },
            "checkpoint_state.pt": {
                "mode": "0600",
                "sha256": _sha256_bytes(state_bytes),
                "size": len(state_bytes),
            },
        },
        "schema_version": 2,
    }
    inventory_bytes = canonical_json_bytes(inventory)
    files = _canonical_checkpoint_transaction_files(
        {
            "checkpoint_state.pt": state_bytes,
            "checkpoint_manifest.json": manifest_bytes,
            "checkpoint_inventory.json": inventory_bytes,
        }
    )
    result = object.__new__(CheckpointEnvelope)
    for name, value in {
        "condition": runtime.condition,
        "completed_update": runtime.completed_update,
        "authorization_sha256": authorization.authorization_sha256,
        "sanitized_view_sha256": authorization.training_view_sha256,
        "launch_manifest_sha256": authorization.launch_manifest.manifest_sha256,
        "checkpoint_inventory_sha256": _sha256_bytes(inventory_bytes),
        "artifact_transaction_inventory_sha256": _sha256_bytes(
            files["inventory.json"]
        ),
        "envelope_sha256": _checkpoint_envelope_identity(files),
        "_files": files,
        "_factory_token": runtime._factory_token,
    }.items():
        object.__setattr__(result, name, value)
    return result


def checkpoint_payloads_for_runtime(
    runtime: TinySmokeConditionRuntime,
) -> Mapping[str, bytes]:
    """Return the complete privacy-safe envelope for artifact transport."""

    return checkpoint_envelope_for_runtime(runtime)._files


def _checkpoint_envelope_from_files_for_tests_impl(
    files: Mapping[str, bytes],
    expected_envelope_sha256: str,
    *,
    token: object,
) -> CheckpointEnvelope:
    if (
        not isinstance(files, Mapping)
        or set(files)
        != {
            "checkpoint_state.pt",
            "checkpoint_manifest.json",
            "checkpoint_inventory.json",
            "inventory.json",
            "CHECKPOINT_COMPLETE.json",
        }
        or any(type(value) is not bytes for value in files.values())
        or _require_sha256(expected_envelope_sha256, SMOKE_RESUME_MISMATCH)
        != _checkpoint_envelope_identity(files)
    ):
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    completion = _checkpoint_json(files["CHECKPOINT_COMPLETE.json"])
    result = object.__new__(CheckpointEnvelope)
    for name, value in {
        "condition": completion.get("condition"),
        "completed_update": completion.get("completed_optimizer_update"),
        "authorization_sha256": completion.get("authorization_sha256"),
        "sanitized_view_sha256": completion.get("sanitized_view_sha256"),
        "launch_manifest_sha256": completion.get("launch_manifest_sha256"),
        "checkpoint_inventory_sha256": completion.get(
            "checkpoint_inventory_sha256"
        ),
        "artifact_transaction_inventory_sha256": completion.get(
            "artifact_transaction_inventory_sha256"
        ),
        "envelope_sha256": expected_envelope_sha256,
        "_files": MappingProxyType(dict(files)),
        "_factory_token": token,
    }.items():
        object.__setattr__(result, name, value)
    return result


def write_private_runtime_checkpoint(
    writer: PrivateRunArtifactWriter,
    runtime: TinySmokeConditionRuntime,
    *,
    _envelope: CheckpointEnvelope | None = None,
    _test_hook: Callable[[str], None] | None = None,
) -> object:
    try:
        if _envelope is None:
            envelope = checkpoint_envelope_for_runtime(runtime)
        else:
            if type(_envelope) is not CheckpointEnvelope:
                raise SmokeTrainingError(SMOKE_CHECKPOINT_WRITE_FAILURE)
            manifest = _checkpoint_json(
                _envelope._files.get("checkpoint_manifest.json", b"")
            )
            checkpoint_bytes = _verify_checkpoint_envelope(
                runtime._authorization,
                runtime.condition,
                _envelope,
                runtime.completed_update,
                token=runtime._factory_token,
            )
            if (
                _envelope.condition != runtime.condition
                or _envelope.completed_update != runtime.completed_update
                or _envelope.authorization_sha256
                != runtime._authorization.authorization_sha256
                or _envelope.sanitized_view_sha256
                != runtime._authorization.training_view_sha256
                or _envelope.launch_manifest_sha256
                != runtime._authorization.launch_manifest.manifest_sha256
                or not checkpoint_bytes
                or manifest.get("semantic_state_sha256")
                != _checkpoint_state(runtime).get("semantic_sha256")
            ):
                raise SmokeTrainingError(SMOKE_CHECKPOINT_WRITE_FAILURE)
            envelope = _envelope
        return commit_private_checkpoint(
            writer,
            condition=runtime.condition,
            completed_update=runtime.completed_update,
            payloads=envelope._files,
            _test_hook=_test_hook,
        )
    except SmokeArtifactError as error:
        code = error.code
    raise SmokeTrainingError(code)


def _restore_rng(payload: Mapping[str, object]) -> None:
    try:
        numpy_payload = payload["numpy"]
        if not isinstance(numpy_payload, Mapping):
            raise TypeError
        keys = numpy_payload["keys"]
        if not isinstance(keys, torch.Tensor) or keys.device.type != "cpu":
            raise TypeError
        random.setstate(payload["python"])
        np.random.set_state(
            (
                numpy_payload["generator"],
                keys.numpy().astype(np.uint32, copy=True),
                numpy_payload["position"],
                numpy_payload["has_gauss"],
                numpy_payload["cached_gaussian"],
            )
        )
        torch.set_rng_state(payload["torch_cpu"])
    except Exception:
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH) from None


def _checkpoint_json(content: bytes) -> dict[str, object]:
    try:
        value = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH) from None
    if not isinstance(value, dict) or canonical_json_bytes(value) != content:
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    return value


def _verify_checkpoint_envelope(
    authorization: SmokeExecutionAuthorization,
    condition: str,
    envelope: CheckpointEnvelope,
    expected_completed_update: int,
    *,
    token: object,
) -> bytes:
    _reanchor_consumed_view(
        authorization,
        condition=condition,
        code=SMOKE_RESUME_MISMATCH,
    )
    if (
        type(envelope) is not CheckpointEnvelope
        or envelope._factory_token is not token
        or type(expected_completed_update) is not int
        or expected_completed_update not in CHECKPOINT_UPDATES
        or envelope.condition != condition
        or envelope.completed_update != expected_completed_update
        or envelope.authorization_sha256 != authorization.authorization_sha256
        or envelope.sanitized_view_sha256 != authorization.training_view_sha256
        or envelope.launch_manifest_sha256
        != authorization.launch_manifest.manifest_sha256
        or set(envelope._files)
        != {
            "checkpoint_state.pt",
            "checkpoint_manifest.json",
            "checkpoint_inventory.json",
            "inventory.json",
            "CHECKPOINT_COMPLETE.json",
        }
        or any(type(value) is not bytes for value in envelope._files.values())
        or envelope.envelope_sha256 != _checkpoint_envelope_identity(envelope._files)
    ):
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    state_bytes = envelope._files["checkpoint_state.pt"]
    manifest_bytes = envelope._files["checkpoint_manifest.json"]
    inventory_bytes = envelope._files["checkpoint_inventory.json"]
    transaction_inventory_bytes = envelope._files["inventory.json"]
    completion_bytes = envelope._files["CHECKPOINT_COMPLETE.json"]
    manifest = _checkpoint_json(manifest_bytes)
    inventory = _checkpoint_json(inventory_bytes)
    transaction_inventory = _checkpoint_json(transaction_inventory_bytes)
    completion = _checkpoint_json(completion_bytes)
    expected_inventory = {
        "algorithm": "sha256",
        "files": {
            "checkpoint_manifest.json": {
                "mode": "0600",
                "sha256": _sha256_bytes(manifest_bytes),
                "size": len(manifest_bytes),
            },
            "checkpoint_state.pt": {
                "mode": "0600",
                "sha256": _sha256_bytes(state_bytes),
                "size": len(state_bytes),
            },
        },
        "schema_version": 2,
    }
    expected_transaction_inventory = {
        "algorithm": "sha256",
        "files": {
            name: {
                "mode": "0600",
                "sha256": _sha256_bytes(envelope._files[name]),
                "size": len(envelope._files[name]),
            }
            for name in (
                "checkpoint_inventory.json",
                "checkpoint_manifest.json",
                "checkpoint_state.pt",
            )
        },
        "schema_version": 1,
    }
    expected_completion = {
        "artifact_transaction_inventory_sha256": _sha256_bytes(
            transaction_inventory_bytes
        ),
        "artifact_transaction_inventory_size": len(transaction_inventory_bytes),
        "authorization_sha256": authorization.authorization_sha256,
        "candidate_checksum_record_sha256": (
            authorization.approval.candidate_checksum_record_sha256
        ),
        "checkpoint_inventory_sha256": _sha256_bytes(inventory_bytes),
        "checkpoint_protocol": CHECKPOINT_PROTOCOL,
        "complete": True,
        "completed_optimizer_update": expected_completed_update,
        "condition": condition,
        "launch_manifest_sha256": authorization.launch_manifest.manifest_sha256,
        "device": "cpu",
        "namespace": f"checkpoint-{expected_completed_update:04d}",
        "sanitized_view_sha256": authorization.training_view_sha256,
        "schema_version": 2,
    }
    required_manifest_keys = {
        "authorization_sha256",
        "candidate_checksum_record_sha256",
        "checkpoint_namespace",
        "checkpoint_protocol",
        "completed_optimizer_update",
        "condition",
        "condition_view_sha256",
        "train_source_ranges_sha256",
        "device",
        "executor_closure_digest",
        "executor_commit",
        "history_checksums",
        "launch_manifest_sha256",
        "tracker_authority",
        "model_state_sha256",
        "optimizer_state_sha256",
        "preparation_manifest_sha256",
        "rng_state_sha256",
        "runtime_sha256",
        "sanitized_view_sha256",
        "schedule_plan_identity_sha256",
        "semantic_state_sha256",
        "state_sha256",
        "validation_history_sha256",
    }
    condition_view = next(
        item for item in authorization._training_view.conditions if item.condition == condition
    )
    if (
        inventory != expected_inventory
        or transaction_inventory != expected_transaction_inventory
        or completion != expected_completion
        or envelope.checkpoint_inventory_sha256 != _sha256_bytes(inventory_bytes)
        or envelope.artifact_transaction_inventory_sha256
        != _sha256_bytes(transaction_inventory_bytes)
        or set(manifest) != required_manifest_keys
        or manifest["authorization_sha256"] != authorization.authorization_sha256
        or manifest["candidate_checksum_record_sha256"]
        != authorization.approval.candidate_checksum_record_sha256
        or manifest["checkpoint_namespace"]
        != f"checkpoint-{expected_completed_update:04d}"
        or manifest["checkpoint_protocol"] != CHECKPOINT_PROTOCOL
        or manifest["completed_optimizer_update"] != expected_completed_update
        or manifest["condition"] != condition
        or manifest["condition_view_sha256"] != condition_view.semantic_sha256
        or manifest["train_source_ranges_sha256"]
        != condition_view.train_source_ranges_sha256
        or manifest["device"] != "cpu"
        or manifest["executor_closure_digest"]
        != authorization.launch_manifest.executor_closure_digest
        or manifest["executor_commit"] != authorization.launch_manifest.executor_commit
        or manifest["launch_manifest_sha256"]
        != authorization.launch_manifest.manifest_sha256
        or manifest["tracker_authority"] != _tracker_authority_binding(authorization)
        or manifest["preparation_manifest_sha256"]
        != authorization.approval.preparation_manifest_sha256
        or manifest["sanitized_view_sha256"] != authorization.training_view_sha256
        or manifest["schedule_plan_identity_sha256"]
        != authorization.approval.schedule_plan_identity_sha256
        or manifest["state_sha256"] != _sha256_bytes(state_bytes)
    ):
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    return state_bytes


def _restore_runtime_from_checkpoint_impl(
    authorization: SmokeExecutionAuthorization,
    optimizers: TinySmokeOptimizerSet,
    condition: str,
    envelope: CheckpointEnvelope,
    *,
    expected_completed_update: int,
    token: object,
) -> TinySmokeConditionRuntime:
    checkpoint_bytes = _verify_checkpoint_envelope(
        authorization,
        condition,
        envelope,
        expected_completed_update,
        token=token,
    )
    runtime = _begin_condition_runtime_impl(
        authorization,
        optimizers,
        condition,
        token=token,
    )
    source_parameters = tuple(runtime._model.parameters())
    try:
        restored_model = copy.deepcopy(runtime._model).cpu()
        restored_parameters = tuple(restored_model.parameters())
        if len(source_parameters) != len(restored_parameters) or any(
            source.untyped_storage().data_ptr()
            == restored.untyped_storage().data_ptr()
            for source, restored in zip(source_parameters, restored_parameters, strict=True)
        ):
            raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
        restored_optimizer = _APPROVED_ADAMW_CLASS(
            _unique_trainable_parameters(restored_model),
            lr=PEAK_LEARNING_RATE,
            betas=(0.9, 0.999),
            eps=1e-8,
            weight_decay=0.01,
            maximize=False,
            amsgrad=False,
            capturable=False,
            differentiable=False,
            foreach=False,
            fused=False,
        )
        runtime._model = restored_model
        runtime._optimizer = restored_optimizer
    except SmokeTrainingError:
        raise
    except Exception:
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH) from None
    try:
        state = torch.load(
            io.BytesIO(checkpoint_bytes),
            map_location="cpu",
            weights_only=True,
        )
    except Exception:
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH) from None
    manifest = _checkpoint_json(envelope._files["checkpoint_manifest.json"])
    semantic = state.pop("semantic_sha256", None) if isinstance(state, dict) else None
    required_state_keys = {
        "at_update_boundary",
        "authorization_sha256",
        "candidate_checksum_record_sha256",
        "completed_optimizer_update",
        "condition",
        "condition_view_sha256",
        "device",
        "executor_lineage",
        "histories",
        "history_checksums",
        "initialization_manifest",
        "launch_manifest_sha256",
        "tracker_authority",
        "learning_rate_state",
        "model_state",
        "model_ties",
        "optimizer_group_identity",
        "optimizer_protocol",
        "optimizer_state",
        "preparation_manifest_sha256",
        "protocol",
        "resume",
        "rng",
        "runtime",
        "schedule_evidence_sha256",
        "schedule_identity_sha256",
        "schedule_plan_identity_sha256",
        "schedule_update_plan_sha256",
        "seeds",
        "train_tensor_sha256",
        "train_source_ranges_sha256",
        "training_view_sha256",
        "validation_plan_sha256",
        "validation_tensor_sha256",
    }
    expected_initialization = {
        "configuration_sha256": authorization.initialization_manifest.configuration_sha256,
        "initial_state_sha256": authorization.initialization_manifest.initial_state_sha256,
        "parameter_count": authorization.initialization_manifest.trainable_parameter_count,
        "tied_parameter_groups": authorization.initialization_manifest.tied_parameter_groups,
    }
    expected_seeds = {
        "dropout_base": DROPOUT_BASE_SEED,
        "dropout_protocol": DROPOUT_PROTOCOL,
        "model": MODEL_SEED,
        "training_mask": TRAINING_MASK_SEED,
        "validation_mask": VALIDATION_MASK_SEED,
    }
    expected_runtime = {
        "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
        "device": "cpu",
        "intraop_threads": torch.get_num_threads(),
        "maximum_concurrency": 1,
        "numpy": importlib.metadata.version("numpy"),
        "python": sys.version.split()[0],
        "torch": importlib.metadata.version("torch"),
        "transformers": importlib.metadata.version("transformers"),
    }
    if (
        not isinstance(state, dict)
        or set(state) != required_state_keys
        or semantic != _semantic_hash(state)
        or semantic != manifest["semantic_state_sha256"]
        or _semantic_hash(state.get("model_state")) != manifest["model_state_sha256"]
        or _semantic_hash(state.get("optimizer_state"))
        != manifest["optimizer_state_sha256"]
        or _semantic_hash(state.get("rng")) != manifest["rng_state_sha256"]
        or _semantic_hash(state.get("runtime")) != manifest["runtime_sha256"]
        or state.get("history_checksums") != manifest["history_checksums"]
        or state.get("history_checksums", {}).get("validation")
        != manifest["validation_history_sha256"]
        or state.get("protocol") != CHECKPOINT_PROTOCOL
        or state.get("condition") != condition
        or state.get("device") != "cpu"
        or state.get("at_update_boundary") is not True
        or state.get("authorization_sha256") != authorization.authorization_sha256
        or state.get("tracker_authority")
        != _tracker_authority_binding(authorization)
        or state.get("candidate_checksum_record_sha256")
        != authorization.approval.candidate_checksum_record_sha256
        or state.get("preparation_manifest_sha256")
        != authorization.approval.preparation_manifest_sha256
        or state.get("schedule_plan_identity_sha256")
        != authorization.approval.schedule_plan_identity_sha256
        or state.get("training_view_sha256") != authorization.training_view_sha256
        or state.get("launch_manifest_sha256")
        != authorization.launch_manifest.manifest_sha256
        or state.get("schedule_identity_sha256")
        != runtime._condition_view.schedule.identity_sha256
        or state.get("schedule_update_plan_sha256")
        != runtime._condition_view.schedule.update_plan_sha256
        or state.get("condition_view_sha256")
        != runtime._condition_view.semantic_sha256
        or state.get("train_tensor_sha256")
        != runtime._condition_view.train_tensor_sha256
        or state.get("train_source_ranges_sha256")
        != runtime._condition_view.train_source_ranges_sha256
        or state.get("validation_tensor_sha256")
        != runtime._condition_view.validation_tensor_sha256
        or state.get("schedule_evidence_sha256")
        != runtime._condition_view.schedule_evidence_sha256
        or state.get("validation_plan_sha256")
        != runtime._condition_view.validation_plan_sha256
        or state.get("initialization_manifest") != expected_initialization
        or state.get("seeds") != expected_seeds
        or state.get("runtime") != expected_runtime
        or state.get("model_ties") != tied_parameter_groups(runtime._model)
        or state.get("optimizer_group_identity") != _parameter_group_identity(runtime._model)
        or state.get("optimizer_protocol") != _optimizer_protocol()
        or state.get("executor_lineage")
        != {
            "commit": authorization.launch_manifest.executor_commit,
            "closure_digest": authorization.launch_manifest.executor_closure_digest,
            "protocol": EXECUTOR_PROTOCOL,
        }
    ):
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    completed = state.get("completed_optimizer_update")
    if (
        type(completed) is not int
        or completed != expected_completed_update
        or completed not in CHECKPOINT_UPDATES
    ):
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    if state.get("resume") != {
        "protocol": RESUME_PROTOCOL,
        "next_update": completed + 1,
        "schedule_update_count": len(runtime._condition_view.schedule.updates),
    }:
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    histories = state.get("histories")
    if not isinstance(histories, dict) or state.get("history_checksums") != {
        name: _semantic_hash(tuple(histories[name]))
        for name in ("loss", "targets", "masks", "validation")
    }:
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    expected_validation_updates = tuple(
        update
        for update in VALIDATION_POINTS
        if update <= completed
        and update <= len(runtime._condition_view.schedule.updates)
    )
    if (
        len(histories.get("loss", ())) != completed
        or len(histories.get("targets", ())) != completed
        or len(histories.get("masks", ())) != completed
        or tuple(item[0] for item in histories.get("validation", ()))
        != expected_validation_updates
    ):
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    try:
        runtime._model.load_state_dict(state["model_state"], strict=True)
        runtime._optimizer.load_state_dict(state["optimizer_state"])
        runtime._optimizer.zero_grad(set_to_none=True)
    except Exception:
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH) from None
    if tied_parameter_groups(runtime._model) != state["model_ties"]:
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    restored_parameters = _unique_trainable_parameters(runtime._model)
    try:
        _verify_runtime_optimizer(
            runtime._optimizer,
            restored_parameters,
            expected_lr=(
                PEAK_LEARNING_RATE
                if completed == 0
                else approved_learning_rate(completed)
            ),
        )
        if set(_optimizer_steps(runtime._optimizer, restored_parameters).values()) != {
            completed
        }:
            raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    except SmokeTrainingError:
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH) from None
    runtime.completed_update = completed
    runtime.at_update_boundary = True
    runtime.learning_rate_state = learning_rate_state_after_update(completed)
    if state["learning_rate_state"] != {
        "completed_update": runtime.learning_rate_state.completed_update,
        "last_step_learning_rate": runtime.learning_rate_state.last_step_learning_rate,
        "next_step_learning_rate": runtime.learning_rate_state.next_step_learning_rate,
        "protocol": runtime.learning_rate_state.protocol,
    }:
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    runtime._loss_history[:] = histories["loss"]
    runtime._target_count_history[:] = histories["targets"]
    runtime._mask_history[:] = histories["masks"]
    runtime._validation_history[:] = histories["validation"]
    _restore_rng(state["rng"])
    runtime._model.train()
    return runtime


def _prime_synthetic_runtime_for_tests(
    runtime: TinySmokeConditionRuntime,
    completed_update: int,
    *,
    include_current_validation: bool,
) -> None:
    """Create deterministic test-only state at a validation or checkpoint boundary."""

    if (
        type(runtime) is not TinySmokeConditionRuntime
        or runtime._authorization.authority_kind != "synthetic_test_only"
        or runtime.completed_update != 0
        or completed_update not in set(CHECKPOINT_UPDATES) | set(VALIDATION_POINTS)
        or completed_update > len(runtime._condition_view.schedule.updates)
    ):
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    for parameter in _unique_trainable_parameters(runtime._model):
        runtime._optimizer.state[parameter] = {
            "step": torch.tensor(float(completed_update)),
            "exp_avg": torch.zeros_like(parameter),
            "exp_avg_sq": torch.zeros_like(parameter),
        }
    for group in runtime._optimizer.param_groups:
        group["lr"] = (
            PEAK_LEARNING_RATE
            if completed_update == 0
            else approved_learning_rate(completed_update)
        )
    runtime.completed_update = completed_update
    runtime.learning_rate_state = learning_rate_state_after_update(completed_update)
    runtime._loss_history[:] = [
        float((index % 17) + 1) / 1_000 for index in range(completed_update)
    ]
    runtime._target_count_history[:] = [1] * completed_update
    runtime._mask_history[:] = [
        _sha256_bytes(canonical_json_bytes(["synthetic_prime", index + 1]))
        for index in range(completed_update)
    ]
    runtime._validation_history[:] = [
        (
            point,
            float(point) / 10_000,
            1,
            _sha256_bytes(canonical_json_bytes(["synthetic_validation", point])),
        )
        for point in VALIDATION_POINTS
        if point < completed_update
        or (include_current_validation and point == completed_update)
    ]
    runtime.at_update_boundary = True


def prime_synthetic_runtime_to_update_for_tests(
    runtime: TinySmokeConditionRuntime,
    completed_update: int,
) -> None:
    """Prime synthetic state immediately before a fixed validation point."""

    _prime_synthetic_runtime_for_tests(
        runtime,
        completed_update,
        include_current_validation=False,
    )


def prime_synthetic_runtime_to_checkpoint_for_tests(
    runtime: TinySmokeConditionRuntime,
    completed_update: int,
) -> None:
    """Create deterministic test-only optimizer state at an approved checkpoint."""

    if completed_update not in CHECKPOINT_UPDATES:
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    _prime_synthetic_runtime_for_tests(
        runtime,
        completed_update,
        include_current_validation=True,
    )


_REPLAY_CHECKPOINT_FILE_NAMES = (
    "CHECKPOINT_COMPLETE.json",
    "checkpoint_inventory.json",
    "checkpoint_manifest.json",
    "checkpoint_state.pt",
    "inventory.json",
)
_REPLAY_TRANSACTION_FILE_NAMES = (
    "artifact_transaction_completion.json",
    "artifact_transaction_inventory.json",
)
_REPLAY_BUNDLE_CONTROL_NAMES = (
    "replay_request.json",
    "replay_inventory.json",
    "REPLAY_BUNDLE_COMPLETE.json",
)
_REPLAY_HISTORY_NAMES = ("loss", "masks", "targets", "validation")
_REPLAY_FILE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,159}\Z")


def _read_regular_file_at(
    directory_descriptor: int,
    name: str,
    *,
    maximum_bytes: int,
) -> bytes:
    if (
        not isinstance(name, str)
        or _REPLAY_FILE_RE.fullmatch(name) is None
        or type(maximum_bytes) is not int
        or maximum_bytes <= 0
    ):
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    descriptor = -1
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(name, flags, dir_fd=directory_descriptor)
        before = os.fstat(descriptor)
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_IMODE(before.st_mode) != 0o600
            or before.st_uid != os.getuid()
            or before.st_nlink != 1
            or before.st_size > maximum_bytes
        ):
            raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(descriptor, min(remaining, 1024 * 1024))
            if not chunk:
                raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
            chunks.append(chunk)
            remaining -= len(chunk)
        if os.read(descriptor, 1):
            raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
        after = os.fstat(descriptor)
        fields = ("st_dev", "st_ino", "st_size", "st_mode", "st_uid", "st_nlink")
        if any(getattr(before, field) != getattr(after, field) for field in fields):
            raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
        return b"".join(chunks)
    except SmokeTrainingError:
        raise
    except OSError:
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH) from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _write_regular_file_at(
    directory_descriptor: int,
    name: str,
    content: bytes,
) -> None:
    if (
        not isinstance(name, str)
        or _REPLAY_FILE_RE.fullmatch(name) is None
        or type(content) is not bytes
    ):
        raise SmokeTrainingError(SMOKE_CHECKPOINT_WRITE_FAILURE)
    descriptor = -1
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        descriptor = os.open(name, flags, 0o600, dir_fd=directory_descriptor)
        view = memoryview(content)
        written = 0
        while written < len(view):
            count = os.write(descriptor, view[written:])
            if count <= 0:
                raise OSError("incomplete replay file write")
            written += count
        os.fsync(descriptor)
        status = os.fstat(descriptor)
        if (
            not stat.S_ISREG(status.st_mode)
            or stat.S_IMODE(status.st_mode) != 0o600
            or status.st_uid != os.getuid()
            or status.st_nlink != 1
            or status.st_size != len(content)
        ):
            raise SmokeTrainingError(SMOKE_CHECKPOINT_WRITE_FAILURE)
    except SmokeTrainingError:
        raise
    except OSError:
        raise SmokeTrainingError(SMOKE_CHECKPOINT_WRITE_FAILURE) from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _open_directory_at(directory_descriptor: int, name: str) -> int:
    if not isinstance(name, str) or _REPLAY_FILE_RE.fullmatch(name) is None:
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=directory_descriptor,
        )
        status = os.fstat(descriptor)
        if (
            not stat.S_ISDIR(status.st_mode)
            or stat.S_IMODE(status.st_mode) != 0o700
            or status.st_uid != os.getuid()
        ):
            raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
        return descriptor
    except SmokeTrainingError:
        if "descriptor" in locals():
            os.close(descriptor)
        raise
    except OSError:
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH) from None


def _read_committed_checkpoint_transaction(
    writer: PrivateRunArtifactWriter,
    envelope: CheckpointEnvelope,
    commit_result: object,
) -> Mapping[str, bytes]:
    if (
        type(writer) is not PrivateRunArtifactWriter
        or writer._committed
        or type(envelope) is not CheckpointEnvelope
        or envelope.condition != "EnglishMono"
        or envelope.completed_update != 750
        or not isinstance(getattr(commit_result, "inventory_sha256", None), str)
        or not isinstance(getattr(commit_result, "completion_sha256", None), str)
    ):
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    condition_descriptor = cpu_descriptor = checkpoint_descriptor = -1
    try:
        condition_descriptor = _open_directory_at(writer._stage_descriptor, "EnglishMono")
        cpu_descriptor = _open_directory_at(condition_descriptor, "cpu")
        checkpoint_descriptor = _open_directory_at(cpu_descriptor, "checkpoint-0750")
        expected_names = {
            "CHECKPOINT_COMPLETE.json",
            "checkpoint_inventory.json",
            "checkpoint_manifest.json",
            "checkpoint_state.pt",
            "inventory.json",
        }
        if set(os.listdir(checkpoint_descriptor)) != expected_names:
            raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
        files = {
            name: _read_regular_file_at(
                checkpoint_descriptor,
                name,
                maximum_bytes=128 * 1024 * 1024,
            )
            for name in sorted(expected_names)
        }
    finally:
        for descriptor in (checkpoint_descriptor, cpu_descriptor, condition_descriptor):
            if descriptor >= 0:
                os.close(descriptor)
    for name in sorted(expected_names):
        if files[name] != envelope._files[name]:
            raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    manifest = _checkpoint_json(files["checkpoint_manifest.json"])
    outer_inventory = _checkpoint_json(files["inventory.json"])
    outer_completion = _checkpoint_json(files["CHECKPOINT_COMPLETE.json"])
    expected_outer_files = {
        name: {
            "mode": "0600",
            "sha256": _sha256_bytes(files[name]),
            "size": len(files[name]),
        }
        for name in (
            "checkpoint_inventory.json",
            "checkpoint_manifest.json",
            "checkpoint_state.pt",
        )
    }
    if (
        outer_inventory
        != {"algorithm": "sha256", "files": expected_outer_files, "schema_version": 1}
        or _sha256_bytes(files["inventory.json"])
        != getattr(commit_result, "inventory_sha256")
        or _sha256_bytes(files["CHECKPOINT_COMPLETE.json"])
        != getattr(commit_result, "completion_sha256")
        or outer_completion
        != {
            "artifact_transaction_inventory_sha256": getattr(
                commit_result, "inventory_sha256"
            ),
            "artifact_transaction_inventory_size": len(files["inventory.json"]),
            "authorization_sha256": envelope.authorization_sha256,
            "candidate_checksum_record_sha256": manifest[
                "candidate_checksum_record_sha256"
            ],
            "checkpoint_inventory_sha256": envelope.checkpoint_inventory_sha256,
            "checkpoint_protocol": CHECKPOINT_PROTOCOL,
            "complete": True,
            "completed_optimizer_update": 750,
            "condition": "EnglishMono",
            "device": "cpu",
            "launch_manifest_sha256": envelope.launch_manifest_sha256,
            "namespace": "checkpoint-0750",
            "sanitized_view_sha256": envelope.sanitized_view_sha256,
            "schema_version": 2,
        }
    ):
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    return MappingProxyType(
        {
            "artifact_transaction_completion.json": files["CHECKPOINT_COMPLETE.json"],
            "artifact_transaction_inventory.json": files["inventory.json"],
        }
    )


def _numpy_array_bytes(array: np.ndarray) -> bytes:
    if not isinstance(array, np.ndarray) or array.ndim != 2:
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    buffer = io.BytesIO()
    np.save(buffer, array, allow_pickle=False)
    return buffer.getvalue()


def _numpy_array_from_bytes(content: bytes) -> np.ndarray:
    try:
        buffer = io.BytesIO(content)
        array = np.load(buffer, allow_pickle=False)
        if buffer.tell() != len(content) or not isinstance(array, np.ndarray):
            raise ValueError
        return array
    except Exception:
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH) from None


def _synthetic_replay_material(
    authorization: SmokeExecutionAuthorization,
) -> tuple[dict[str, object], Mapping[str, bytes]]:
    view = authorization._training_view
    if (
        authorization.authority_kind
        not in {"synthetic_test_only", "synthetic_production_equivalent"}
        or type(view) is not SanitizedTrainingView
        or tuple(item.condition for item in view.conditions) != CONDITIONS
        or any(len(item.schedule.updates) != 1_000 for item in view.conditions)
    ):
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    microbatch_sizes = {
        max(
            microbatch.sequence_count
            for update in item.schedule.updates
            for microbatch in update.microbatches
        )
        for item in view.conditions
    }
    if len(microbatch_sizes) != 1:
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    arrays_manifest: list[list[str]] = []
    files: dict[str, bytes] = {}
    for condition_view in view.conditions:
        names = []
        for field_name in ("input_ids", "attention_mask", "token_type_ids"):
            name = f"synthetic_{condition_view.condition}_{field_name}.npy"
            files[name] = _numpy_array_bytes(
                getattr(condition_view.train_tensors, field_name)
            )
            names.append(name)
        arrays_manifest.append([condition_view.condition, *names])
    material = {
        "arrays": arrays_manifest,
        "microbatch_size": next(iter(microbatch_sizes)),
        "test_updates": 1_000,
    }
    return material, MappingProxyType(files)


def _runtime_replay_comparison(
    runtime: TinySmokeConditionRuntime,
) -> dict[str, object]:
    if (
        type(runtime) is not TinySmokeConditionRuntime
        or runtime.condition != "EnglishMono"
        or runtime.completed_update != 1_000
        or not runtime.at_update_boundary
        or tuple(item[0] for item in runtime._validation_history) != VALIDATION_POINTS
    ):
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    learning_rate_payload = {
        "completed_update": runtime.learning_rate_state.completed_update,
        "last_step_learning_rate": runtime.learning_rate_state.last_step_learning_rate,
        "next_step_learning_rate": runtime.learning_rate_state.next_step_learning_rate,
        "protocol": runtime.learning_rate_state.protocol,
    }
    return {
        "history_checksums": {
            "loss": _semantic_hash(tuple(runtime._loss_history)),
            "masks": _semantic_hash(tuple(runtime._mask_history)),
            "targets": _semantic_hash(tuple(runtime._target_count_history)),
            "validation": _semantic_hash(tuple(runtime._validation_history)),
        },
        "learning_rate_semantic_sha256": _semantic_hash(learning_rate_payload),
        "rng_semantic_sha256": _semantic_hash(_rng_payload()),
        "runtime_semantic_sha256": runtime_semantic_sha256(runtime),
        "validation_updates": tuple(item[0] for item in runtime._validation_history),
    }


def _worker_source_root() -> Path:
    try:
        root = Path(__file__).resolve(strict=True).parents[3]
        script = root / "scripts" / "run_bounded_tiny_smoke.py"
        status = script.lstat()
        if (
            not stat.S_ISREG(status.st_mode)
            or status.st_nlink != 1
            or script.resolve(strict=True) != script
        ):
            raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
        return root
    except SmokeTrainingError:
        raise
    except Exception:
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH) from None


def _replay_worker_environment(
    source_root: Path,
    *,
    authority_kind: str,
    test_fault: str | None,
) -> dict[str, str]:
    environment = {
        "HOME": str(Path.home()),
        "LANG": "C",
        "LC_ALL": "C",
        "MKL_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": str(MODEL_SEED),
        "PYTHONPATH": os.pathsep.join((str(source_root / "src"), str(source_root))),
        "TOKENIZERS_PARALLELISM": "false",
        "VECLIB_MAXIMUM_THREADS": "1",
    }
    if authority_kind != "production_tracker_and_launch":
        environment["CSLM_TRACKED_ONLY_TEST"] = "1"
    if test_fault is not None:
        if authority_kind == "production_tracker_and_launch":
            raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
        environment["CSLM_TINY_REPLAY_TEST_FAULT"] = test_fault
    return environment


def _replay_request_payload(
    authorization: SmokeExecutionAuthorization,
    envelope: CheckpointEnvelope,
    transaction_files: Mapping[str, bytes],
    source_root: Path,
    synthetic_material: dict[str, object] | None,
    environment: Mapping[str, str],
    output_parent: Path,
    *,
    bundle_fault: str | None,
) -> dict[str, object]:
    condition = "SpanishMono" if bundle_fault == "wrong_condition" else "EnglishMono"
    checkpoint_update = 500 if bundle_fault == "wrong_update" else 750
    script_bytes, _ = _stable_read(
        source_root / "scripts" / "run_bounded_tiny_smoke.py",
        maximum_bytes=1024 * 1024,
    )
    return {
        "artifact_completion_sha256": _sha256_bytes(
            transaction_files["artifact_transaction_completion.json"]
        ),
        "artifact_inventory_sha256": _sha256_bytes(
            transaction_files["artifact_transaction_inventory.json"]
        ),
        "authority_kind": authorization.authority_kind,
        "authorization_sha256": authorization.authorization_sha256,
        "candidate_checksum_record_sha256": (
            authorization.approval.candidate_checksum_record_sha256
        ),
        "checkpoint_envelope_sha256": envelope.envelope_sha256,
        "checkpoint_inventory_sha256": envelope.checkpoint_inventory_sha256,
        "checkpoint_update": checkpoint_update,
        "condition": condition,
        "condition_digests": authorization.condition_digests,
        "dropout_protocol": DROPOUT_PROTOCOL,
        "executor_closure_digest": (
            authorization.launch_manifest.executor_closure_digest
        ),
        "executor_commit": authorization.launch_manifest.executor_commit,
        "first_replay_update": 751,
        "launch_manifest_sha256": authorization.launch_manifest.manifest_sha256,
        "last_replay_update": 1_000,
        "parent_pid": os.getpid(),
        "preparation_manifest_sha256": (
            authorization.approval.preparation_manifest_sha256
        ),
        "preparation_runner_digest": APPROVED_PREPARATION_RUNNER_DIGEST,
        "process_environment_sha256": _semantic_hash(dict(environment)),
        "process_start_nonce": os.urandom(32).hex(),
        "protocol": RESUME_WORKER_PROTOCOL,
        "runtime_policy_sha256": _runtime_policy_sha256(),
        "sanitized_view_sha256": authorization.training_view_sha256,
        "schedule_bindings": authorization.schedule_bindings,
        "schedule_plan_identity_sha256": (
            authorization.approval.schedule_plan_identity_sha256
        ),
        "schema_version": 1,
        "synthetic_material": synthetic_material,
        "synthetic_output_parent": (
            None
            if authorization.authority_kind != "synthetic_production_equivalent"
            else str(output_parent)
        ),
        "tensor_array_digests": authorization.tensor_array_digests,
        "tracker_authority": _tracker_authority_binding(authorization),
        "tracker_sha256": authorization.approval.tracker_sha256,
        "validation_updates": REPLAY_VALIDATION_POINTS,
        "worker_script_sha256": _sha256_bytes(script_bytes),
        "worker_source_closure_sha256": _executor_source_closure_identity(source_root),
    }


def _create_replay_bundle(
    writer: PrivateRunArtifactWriter,
    authorization: SmokeExecutionAuthorization,
    envelope: CheckpointEnvelope,
    transaction_files: Mapping[str, bytes],
    output_parent: Path,
    *,
    bundle_fault: str | None,
    test_fault: str | None,
) -> tuple[Path, Mapping[str, str], str]:
    if (
        type(writer) is not PrivateRunArtifactWriter
        or writer._committed
        or type(authorization) is not SmokeExecutionAuthorization
        or type(envelope) is not CheckpointEnvelope
        or envelope.condition != "EnglishMono"
        or envelope.completed_update != 750
        or set(transaction_files) != set(_REPLAY_TRANSACTION_FILE_NAMES)
        or not isinstance(output_parent, Path)
        or not output_parent.is_absolute()
        or bundle_fault
        not in {
            None,
            "wrong_condition",
            "wrong_update",
            "missing_envelope",
            "inconsistent_envelope",
        }
    ):
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    source_root = _worker_source_root()
    environment = _replay_worker_environment(
        source_root,
        authority_kind=authorization.authority_kind,
        test_fault=test_fault,
    )
    synthetic_material: dict[str, object] | None = None
    synthetic_files: Mapping[str, bytes] = MappingProxyType({})
    if authorization.authority_kind != "production_tracker_and_launch":
        synthetic_material, synthetic_files = _synthetic_replay_material(authorization)
    request = _replay_request_payload(
        authorization,
        envelope,
        transaction_files,
        source_root,
        synthetic_material,
        environment,
        output_parent,
        bundle_fault=bundle_fault,
    )
    files: dict[str, bytes] = {
        **dict(envelope._files),
        **dict(transaction_files),
        **dict(synthetic_files),
    }
    if authorization.authority_kind != "production_tracker_and_launch":
        files["synthetic_tracker_authority.bin"] = authorization.approval._tracker_bytes
        files["synthetic_launch_authority.json"] = (
            authorization.launch_manifest._manifest_bytes
        )
    if bundle_fault == "missing_envelope":
        files.pop("checkpoint_state.pt")
    elif bundle_fault == "inconsistent_envelope":
        state = files["checkpoint_state.pt"]
        files["checkpoint_state.pt"] = state[:-1] + bytes([state[-1] ^ 1])
    request_bytes = canonical_json_bytes(request)
    files["replay_request.json"] = request_bytes
    stage_root = writer._parent / writer._stage_name
    bundle_path: Path | None = None
    descriptor = -1
    try:
        if (
            stage_root.resolve(strict=True) != stage_root
            or stat.S_IMODE(stage_root.stat().st_mode) != 0o700
        ):
            raise SmokeTrainingError(SMOKE_CHECKPOINT_WRITE_FAILURE)
        bundle_path = Path(
            tempfile.mkdtemp(prefix="resume-replay-", dir=stage_root)
        ).resolve(strict=True)
        os.chmod(bundle_path, 0o700)
        descriptor = os.open(
            bundle_path,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0),
        )
        root_status = os.fstat(descriptor)
        if (
            not stat.S_ISDIR(root_status.st_mode)
            or stat.S_IMODE(root_status.st_mode) != 0o700
            or root_status.st_uid != os.getuid()
        ):
            raise SmokeTrainingError(SMOKE_CHECKPOINT_WRITE_FAILURE)
        inventory_files: dict[str, dict[str, object]] = {}
        for name in sorted(files):
            content = files[name]
            _write_regular_file_at(descriptor, name, content)
            inventory_files[name] = {
                "mode": "0600",
                "sha256": _sha256_bytes(content),
                "size": len(content),
            }
        inventory_bytes = canonical_json_bytes(
            {"algorithm": "sha256", "files": inventory_files, "schema_version": 1}
        )
        _write_regular_file_at(descriptor, "replay_inventory.json", inventory_bytes)
        completion_bytes = canonical_json_bytes(
            {
                "bundle_protocol": RESUME_BUNDLE_PROTOCOL,
                "complete": True,
                "inventory_sha256": _sha256_bytes(inventory_bytes),
                "inventory_size": len(inventory_bytes),
                "request_sha256": _sha256_bytes(request_bytes),
                "schema_version": 1,
            }
        )
        _write_regular_file_at(
            descriptor,
            "REPLAY_BUNDLE_COMPLETE.json",
            completion_bytes,
        )
        os.fsync(descriptor)
        if set(os.listdir(descriptor)) != set(files) | {
            "replay_inventory.json",
            "REPLAY_BUNDLE_COMPLETE.json",
        }:
            raise SmokeTrainingError(SMOKE_CHECKPOINT_WRITE_FAILURE)
        return bundle_path, MappingProxyType(dict(environment)), _sha256_bytes(request_bytes)
    except SmokeTrainingError:
        if bundle_path is not None:
            shutil.rmtree(bundle_path, ignore_errors=True)
        raise
    except Exception:
        if bundle_path is not None:
            shutil.rmtree(bundle_path, ignore_errors=True)
        raise SmokeTrainingError(SMOKE_CHECKPOINT_WRITE_FAILURE) from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _remove_replay_bundle(bundle_path: Path) -> None:
    try:
        if (
            not isinstance(bundle_path, Path)
            or not bundle_path.is_absolute()
            or not bundle_path.name.startswith("resume-replay-")
        ):
            raise ValueError
        shutil.rmtree(bundle_path)
        if bundle_path.exists():
            raise ValueError
    except Exception:
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH) from None


def _read_replay_bundle(bundle_path: Path) -> Mapping[str, bytes]:
    descriptor = -1
    try:
        if (
            not isinstance(bundle_path, Path)
            or not bundle_path.is_absolute()
            or bundle_path.resolve(strict=True) != bundle_path
        ):
            raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
        descriptor = os.open(
            bundle_path,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0),
        )
        root_status = os.fstat(descriptor)
        if (
            not stat.S_ISDIR(root_status.st_mode)
            or stat.S_IMODE(root_status.st_mode) != 0o700
            or root_status.st_uid != os.getuid()
        ):
            raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
        names = set(os.listdir(descriptor))
        if not set(_REPLAY_BUNDLE_CONTROL_NAMES) <= names:
            raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
        inventory_bytes = _read_regular_file_at(
            descriptor,
            "replay_inventory.json",
            maximum_bytes=1024 * 1024,
        )
        completion_bytes = _read_regular_file_at(
            descriptor,
            "REPLAY_BUNDLE_COMPLETE.json",
            maximum_bytes=1024 * 1024,
        )
        inventory = _checkpoint_json(inventory_bytes)
        completion = _checkpoint_json(completion_bytes)
        inventory_files = inventory.get("files")
        if (
            set(inventory) != {"algorithm", "files", "schema_version"}
            or inventory.get("algorithm") != "sha256"
            or inventory.get("schema_version") != 1
            or not isinstance(inventory_files, dict)
            or not inventory_files
            or set(completion)
            != {
                "bundle_protocol",
                "complete",
                "inventory_sha256",
                "inventory_size",
                "request_sha256",
                "schema_version",
            }
            or completion.get("bundle_protocol") != RESUME_BUNDLE_PROTOCOL
            or completion.get("complete") is not True
            or completion.get("schema_version") != 1
            or completion.get("inventory_sha256") != _sha256_bytes(inventory_bytes)
            or completion.get("inventory_size") != len(inventory_bytes)
            or names
            != set(inventory_files)
            | {"replay_inventory.json", "REPLAY_BUNDLE_COMPLETE.json"}
        ):
            raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
        files: dict[str, bytes] = {}
        for name, evidence in inventory_files.items():
            if (
                not isinstance(name, str)
                or _REPLAY_FILE_RE.fullmatch(name) is None
                or not isinstance(evidence, dict)
                or set(evidence) != {"mode", "sha256", "size"}
                or evidence.get("mode") != "0600"
                or _SHA256_RE.fullmatch(str(evidence.get("sha256"))) is None
                or type(evidence.get("size")) is not int
                or not 0 <= evidence["size"] <= 128 * 1024 * 1024
            ):
                raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
            content = _read_regular_file_at(
                descriptor,
                name,
                maximum_bytes=128 * 1024 * 1024,
            )
            if (
                len(content) != evidence["size"]
                or _sha256_bytes(content) != evidence["sha256"]
            ):
                raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
            files[name] = content
        if (
            _sha256_bytes(files.get("replay_request.json", b""))
            != completion.get("request_sha256")
        ):
            raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
        return MappingProxyType(files)
    except SmokeTrainingError:
        raise
    except Exception:
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH) from None
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _reconstruct_synthetic_replay_view(
    request: Mapping[str, object],
    files: Mapping[str, bytes],
) -> SanitizedTrainingView:
    material = request.get("synthetic_material")
    if not isinstance(material, dict) or set(material) != {
        "arrays",
        "microbatch_size",
        "test_updates",
    }:
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    arrays = material.get("arrays")
    if (
        not isinstance(arrays, list)
        or len(arrays) != len(CONDITIONS)
        or material.get("test_updates") != 1_000
        or type(material.get("microbatch_size")) is not int
    ):
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    tensors: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    for condition, item in zip(CONDITIONS, arrays, strict=True):
        if (
            not isinstance(item, list)
            or len(item) != 4
            or item[0] != condition
            or any(not isinstance(name, str) for name in item[1:])
        ):
            raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
        tensors[condition] = tuple(
            _numpy_array_from_bytes(files[name]) for name in item[1:]
        )  # type: ignore[assignment]
    return create_synthetic_smoke_training_view_for_tests(
        tensors,
        test_updates=1_000,
        microbatch_size=material["microbatch_size"],
    )


def _reconstruct_replay_authorization(
    request: Mapping[str, object],
    files: Mapping[str, bytes],
    bundle_path: Path,
    *,
    token: object,
) -> SmokeExecutionAuthorization:
    authority_kind = request.get("authority_kind")
    if authority_kind == "production_tracker_and_launch":
        authorization = _construct_production_smoke_execution_authorization_impl(
            token=token
        )
    elif authority_kind in {
        "synthetic_test_only",
        "synthetic_production_equivalent",
    }:
        view = _reconstruct_synthetic_replay_view(request, files)
        tracker_path = bundle_path / "synthetic_tracker_authority.bin"
        launch_path = bundle_path / "synthetic_launch_authority.json"
        if authority_kind == "synthetic_test_only":
            approval = _parse_approval_content(
                files["synthetic_tracker_authority.bin"],
                tracker_sha256=_sha256_bytes(
                    files["synthetic_tracker_authority.bin"]
                ),
                tracker_version=APPROVED_TRACKER_VERSION,
                canonical_date=APPROVED_TRACKER_DATE,
                candidate_checksum=view.candidate_checksum_record_sha256,
                preparation_manifest=view.preparation_manifest_sha256,
                schedule_identity=view.schedule_plan_identity_sha256,
                authority_kind="synthetic_test_only",
                tracker_path=tracker_path,
                token=token,
            )
            launch = _derive_synthetic_launch_manifest_for_tests_impl(
                approval,
                executor_commit=str(request.get("executor_commit")),
                executor_closure_digest=str(
                    request.get("executor_closure_digest")
                ),
                token=token,
            )
            paired = create_paired_initialization(
                NEU_TINY,
                TINY_SMOKE_SEED_PLANS[0],
            )
            authorization = _derive_synthetic_execution_authorization_for_tests_impl(
                approval,
                launch,
                view,
                paired,
                token=token,
            )
        else:
            output_parent_value = request.get("synthetic_output_parent")
            if not isinstance(output_parent_value, str):
                raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
            output_parent = Path(output_parent_value)
            approval = _load_future_tracker_approval(
                tracker_path,
                candidate_checksum=view.candidate_checksum_record_sha256,
                preparation_manifest=view.preparation_manifest_sha256,
                schedule_identity=view.schedule_plan_identity_sha256,
                executor_commit=str(request.get("executor_commit")),
                executor_closure_digest=str(
                    request.get("executor_closure_digest")
                ),
                runtime_policy_sha256=_runtime_policy_sha256(),
                output_parent=output_parent,
                authority_kind="synthetic_production_equivalent",
                production=False,
                token=token,
            )
            launch = _validate_launch_before_candidate_load(
                approval,
                launch_path,
                authority_kind="synthetic_production_equivalent",
                executor_commit=str(request.get("executor_commit")),
                executor_closure_digest=str(
                    request.get("executor_closure_digest")
                ),
                runtime_policy_sha256=_runtime_policy_sha256(),
                output_parent=output_parent,
                production=False,
                token=token,
            )
            paired = create_paired_initialization(
                NEU_TINY,
                TINY_SMOKE_SEED_PLANS[0],
            )
            authorization = _construct_bound_production_authorization(
                approval,
                launch,
                view,
                paired,
                authority_kind="synthetic_production_equivalent",
                required_view_kind="synthetic_test_only",
                output_parent=output_parent,
                token=token,
            )
    else:
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    if (
        authorization.authorization_sha256 != request.get("authorization_sha256")
        or authorization.approval.tracker_sha256 != request.get("tracker_sha256")
        or canonical_json_bytes(_tracker_authority_binding(authorization))
        != canonical_json_bytes(request.get("tracker_authority"))
        or authorization.approval.candidate_checksum_record_sha256
        != request.get("candidate_checksum_record_sha256")
        or authorization.approval.preparation_manifest_sha256
        != request.get("preparation_manifest_sha256")
        or authorization.approval.schedule_plan_identity_sha256
        != request.get("schedule_plan_identity_sha256")
        or authorization.launch_manifest.manifest_sha256
        != request.get("launch_manifest_sha256")
        or authorization.launch_manifest.executor_commit
        != request.get("executor_commit")
        or authorization.launch_manifest.executor_closure_digest
        != request.get("executor_closure_digest")
        or authorization.training_view_sha256
        != request.get("sanitized_view_sha256")
        or canonical_json_bytes(authorization.condition_digests)
        != canonical_json_bytes(request.get("condition_digests"))
        or canonical_json_bytes(authorization.tensor_array_digests)
        != canonical_json_bytes(request.get("tensor_array_digests"))
        or canonical_json_bytes(authorization.schedule_bindings)
        != canonical_json_bytes(request.get("schedule_bindings"))
    ):
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    return authorization


def _verify_replay_transaction(
    request: Mapping[str, object],
    files: Mapping[str, bytes],
) -> None:
    outer_inventory_bytes = files["artifact_transaction_inventory.json"]
    outer_completion_bytes = files["artifact_transaction_completion.json"]
    outer_inventory = _checkpoint_json(outer_inventory_bytes)
    outer_completion = _checkpoint_json(outer_completion_bytes)
    manifest = _checkpoint_json(files["checkpoint_manifest.json"])
    expected_files = {
        name: {
            "mode": "0600",
            "sha256": _sha256_bytes(files[name]),
            "size": len(files[name]),
        }
        for name in (
            "checkpoint_inventory.json",
            "checkpoint_manifest.json",
            "checkpoint_state.pt",
        )
    }
    if (
        _sha256_bytes(outer_inventory_bytes)
        != request.get("artifact_inventory_sha256")
        or _sha256_bytes(outer_completion_bytes)
        != request.get("artifact_completion_sha256")
        or outer_inventory
        != {"algorithm": "sha256", "files": expected_files, "schema_version": 1}
        or outer_completion
        != {
            "artifact_transaction_inventory_sha256": request.get(
                "artifact_inventory_sha256"
            ),
            "artifact_transaction_inventory_size": len(outer_inventory_bytes),
            "authorization_sha256": request.get("authorization_sha256"),
            "candidate_checksum_record_sha256": request.get(
                "candidate_checksum_record_sha256"
            ),
            "checkpoint_inventory_sha256": request.get(
                "checkpoint_inventory_sha256"
            ),
            "checkpoint_protocol": CHECKPOINT_PROTOCOL,
            "complete": True,
            "completed_optimizer_update": 750,
            "condition": "EnglishMono",
            "device": "cpu",
            "launch_manifest_sha256": request.get("launch_manifest_sha256"),
            "namespace": "checkpoint-0750",
            "sanitized_view_sha256": request.get("sanitized_view_sha256"),
            "schema_version": 2,
        }
        or manifest.get("checkpoint_protocol") != CHECKPOINT_PROTOCOL
    ):
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)


def _replay_result_bytes(
    request: Mapping[str, object],
    comparison: Mapping[str, object],
) -> bytes:
    history = comparison.get("history_checksums")
    if not isinstance(history, dict) or set(history) != set(_REPLAY_HISTORY_NAMES):
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    payload: dict[str, object] = {
        "authorization_sha256": request["authorization_sha256"],
        "checkpoint_envelope_sha256": request["checkpoint_envelope_sha256"],
        "checkpoint_update": 750,
        "condition": "EnglishMono",
        "first_replay_update": 751,
        "fresh_interpreter": (
            _PROCESS_IMPORT_PID == os.getpid()
            and os.getpid() != request.get("parent_pid")
        ),
        "history_checksums": history,
        "last_replay_update": 1_000,
        "learning_rate_semantic_sha256": comparison[
            "learning_rate_semantic_sha256"
        ],
        "module_import_pid": _PROCESS_IMPORT_PID,
        "process_start_nonce_sha256": _sha256_bytes(
            str(request["process_start_nonce"]).encode("ascii")
        ),
        "protocol": RESUME_RESULT_PROTOCOL,
        "replay_update_count": 250,
        "request_sha256": _sha256_bytes(canonical_json_bytes(request)),
        "rng_semantic_sha256": comparison["rng_semantic_sha256"],
        "runtime_semantic_sha256": comparison["runtime_semantic_sha256"],
        "schema_version": 1,
        "validation_updates": REPLAY_VALIDATION_POINTS,
        "worker_import_nonce_sha256": _PROCESS_IMPORT_NONCE_SHA256,
        "worker_pid": os.getpid(),
    }
    payload["result_sha256"] = _sha256_bytes(
        canonical_json_bytes([RESUME_RESULT_PROTOCOL, payload])
    )
    return canonical_json_bytes(payload)


def _mismatched_replay_result_for_tests(request: Mapping[str, object]) -> bytes:
    zero = "0" * 64
    return _replay_result_bytes(
        request,
        {
            "history_checksums": {name: zero for name in _REPLAY_HISTORY_NAMES},
            "learning_rate_semantic_sha256": zero,
            "rng_semantic_sha256": zero,
            "runtime_semantic_sha256": zero,
        },
    )


def _execute_tiny_resume_replay_worker_impl(
    bundle_path: Path,
    *,
    token: object,
    diagnostic_sink: Callable[[str, int | None], None] | None = None,
) -> bytes:
    def complete(phase: str, update: int | None = None) -> None:
        if diagnostic_sink is not None:
            diagnostic_sink(phase, update)

    complete("WORKER_STARTED")
    test_fault = os.environ.get("CSLM_TINY_REPLAY_TEST_FAULT")
    if test_fault is not None and os.environ.get("CSLM_TRACKED_ONLY_TEST") != "1":
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    if test_fault == "timeout":
        time.sleep(5.0)
    if test_fault == "child_nonzero":
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    if test_fault == "missing_result":
        return b""
    if test_fault == "malformed_result":
        return b"{}\n"
    files = _read_replay_bundle(bundle_path)
    request = _checkpoint_json(files["replay_request.json"])
    required_request_keys = {
        "artifact_completion_sha256",
        "artifact_inventory_sha256",
        "authority_kind",
        "authorization_sha256",
        "candidate_checksum_record_sha256",
        "checkpoint_envelope_sha256",
        "checkpoint_inventory_sha256",
        "checkpoint_update",
        "condition",
        "condition_digests",
        "dropout_protocol",
        "executor_closure_digest",
        "executor_commit",
        "first_replay_update",
        "launch_manifest_sha256",
        "last_replay_update",
        "parent_pid",
        "preparation_manifest_sha256",
        "preparation_runner_digest",
        "process_environment_sha256",
        "process_start_nonce",
        "protocol",
        "runtime_policy_sha256",
        "sanitized_view_sha256",
        "schedule_bindings",
        "schedule_plan_identity_sha256",
        "schema_version",
        "synthetic_material",
        "synthetic_output_parent",
        "tensor_array_digests",
        "tracker_authority",
        "tracker_sha256",
        "validation_updates",
        "worker_script_sha256",
        "worker_source_closure_sha256",
    }
    source_root = _worker_source_root()
    script_bytes, _ = _stable_read(
        source_root / "scripts" / "run_bounded_tiny_smoke.py",
        maximum_bytes=1024 * 1024,
    )
    expected_environment = _replay_worker_environment(
        source_root,
        authority_kind=str(request.get("authority_kind")),
        test_fault=test_fault,
    )
    if (
        set(request) != required_request_keys
        or request.get("protocol") != RESUME_WORKER_PROTOCOL
        or request.get("schema_version") != 1
        or request.get("condition") != "EnglishMono"
        or request.get("checkpoint_update") != 750
        or request.get("first_replay_update") != 751
        or request.get("last_replay_update") != 1_000
        or request.get("validation_updates") != list(REPLAY_VALIDATION_POINTS)
        or request.get("dropout_protocol") != DROPOUT_PROTOCOL
        or request.get("preparation_runner_digest")
        != APPROVED_PREPARATION_RUNNER_DIGEST
        or request.get("runtime_policy_sha256") != _verify_supported_runtime()
        or request.get("worker_source_closure_sha256")
        != _executor_source_closure_identity(source_root)
        or request.get("worker_script_sha256") != _sha256_bytes(script_bytes)
        or request.get("process_environment_sha256")
        != _semantic_hash(expected_environment)
        or any(os.environ.get(name) != value for name, value in expected_environment.items())
        or type(request.get("parent_pid")) is not int
        or request.get("parent_pid") == os.getpid()
        or _SHA256_RE.fullmatch(str(request.get("process_start_nonce"))) is None
    ):
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    complete("REQUEST_AND_SOURCE_VALIDATED")
    if test_fault == "identity_mismatch":
        return _mismatched_replay_result_for_tests(request)
    _verify_replay_transaction(request, files)
    complete("TRANSACTION_VERIFIED")
    authorization = _reconstruct_replay_authorization(
        request,
        files,
        bundle_path,
        token=token,
    )
    complete("AUTHORITY_RECONSTRUCTED")
    checkpoint_files = {
        name: files[name] for name in _REPLAY_CHECKPOINT_FILE_NAMES
    }
    envelope = _checkpoint_envelope_from_files_for_tests_impl(
        checkpoint_files,
        str(request.get("checkpoint_envelope_sha256")),
        token=token,
    )
    if envelope.checkpoint_inventory_sha256 != request.get(
        "checkpoint_inventory_sha256"
    ):
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    if diagnostic_sink is not None:
        _verify_checkpoint_envelope(
            authorization,
            "EnglishMono",
            envelope,
            750,
            token=token,
        )
        complete("ENVELOPE_VERIFIED_PREDECODE")
    optimizers = _create_optimizer_set_impl(authorization, token=token)
    runtime = _restore_runtime_from_checkpoint_impl(
        authorization,
        optimizers,
        "EnglishMono",
        envelope,
        expected_completed_update=750,
        token=token,
    )
    complete("CHECKPOINT_RESTORED")
    replay_updates: list[int] = []
    replay_validations: list[int] = []
    complete("REPLAY_STARTED")
    while runtime.completed_update < 1_000:
        _execute_next_update_impl(runtime, token=token)
        replay_updates.append(runtime.completed_update)
        if runtime.completed_update in {751, 1_000}:
            complete(f"UPDATE_{runtime.completed_update}_COMPLETED", runtime.completed_update)
        if runtime.completed_update in VALIDATION_POINTS:
            _validate_condition_impl(runtime, token=token)
            replay_validations.append(runtime.completed_update)
            if runtime.completed_update in REPLAY_VALIDATION_POINTS:
                complete(
                    f"VALIDATION_{runtime.completed_update}_COMPLETED",
                    runtime.completed_update,
                )
    if (
        replay_updates != list(range(751, 1_001))
        or tuple(replay_validations) != REPLAY_VALIDATION_POINTS
    ):
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    result = _replay_result_bytes(request, _runtime_replay_comparison(runtime))
    complete("RESULT_ENCODED")
    return result


def _parse_fresh_process_replay_result(
    content: bytes,
    *,
    expected_pid: int,
) -> _FreshProcessReplayResult:
    payload = _checkpoint_json(content)
    required_keys = {
        "authorization_sha256",
        "checkpoint_envelope_sha256",
        "checkpoint_update",
        "condition",
        "first_replay_update",
        "fresh_interpreter",
        "history_checksums",
        "last_replay_update",
        "learning_rate_semantic_sha256",
        "module_import_pid",
        "process_start_nonce_sha256",
        "protocol",
        "replay_update_count",
        "request_sha256",
        "result_sha256",
        "rng_semantic_sha256",
        "runtime_semantic_sha256",
        "schema_version",
        "validation_updates",
        "worker_import_nonce_sha256",
        "worker_pid",
    }
    semantic = payload.pop("result_sha256", None)
    history = payload.get("history_checksums")
    if (
        set(payload) | {"result_sha256"} != required_keys
        or semantic
        != _sha256_bytes(canonical_json_bytes([RESUME_RESULT_PROTOCOL, payload]))
        or payload.get("protocol") != RESUME_RESULT_PROTOCOL
        or payload.get("schema_version") != 1
        or payload.get("fresh_interpreter") is not True
        or payload.get("worker_pid") != expected_pid
        or payload.get("module_import_pid") != expected_pid
        or expected_pid == os.getpid()
        or payload.get("condition") != "EnglishMono"
        or payload.get("checkpoint_update") != 750
        or payload.get("first_replay_update") != 751
        or payload.get("last_replay_update") != 1_000
        or payload.get("replay_update_count") != 250
        or payload.get("validation_updates") != list(REPLAY_VALIDATION_POINTS)
        or not isinstance(history, dict)
        or set(history) != set(_REPLAY_HISTORY_NAMES)
        or any(_SHA256_RE.fullmatch(str(value)) is None for value in history.values())
        or any(
            _SHA256_RE.fullmatch(str(payload.get(name))) is None
            for name in (
                "authorization_sha256",
                "checkpoint_envelope_sha256",
                "learning_rate_semantic_sha256",
                "process_start_nonce_sha256",
                "request_sha256",
                "rng_semantic_sha256",
                "runtime_semantic_sha256",
                "worker_import_nonce_sha256",
            )
        )
    ):
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    return _FreshProcessReplayResult(
        worker_pid=payload["worker_pid"],
        module_import_pid=payload["module_import_pid"],
        fresh_interpreter=True,
        process_start_nonce_sha256=payload["process_start_nonce_sha256"],
        request_sha256=payload["request_sha256"],
        authorization_sha256=payload["authorization_sha256"],
        checkpoint_envelope_sha256=payload["checkpoint_envelope_sha256"],
        condition="EnglishMono",
        checkpoint_update=750,
        first_replay_update=751,
        last_replay_update=1_000,
        replay_update_count=250,
        validation_updates=REPLAY_VALIDATION_POINTS,
        runtime_semantic_sha256=payload["runtime_semantic_sha256"],
        rng_semantic_sha256=payload["rng_semantic_sha256"],
        learning_rate_semantic_sha256=payload["learning_rate_semantic_sha256"],
        history_checksums=tuple(
            (name, history[name]) for name in _REPLAY_HISTORY_NAMES
        ),
        result_sha256=semantic,
    )


def _launch_fresh_process_replay(
    bundle_path: Path,
    environment: Mapping[str, str],
    expected: Mapping[str, object],
    authorization: SmokeExecutionAuthorization,
    envelope_sha256: str,
    request_sha256: str,
    *,
    timeout_seconds: float,
) -> _FreshProcessReplayResult:
    source_root = _worker_source_root()
    interpreter = Path(sys.executable)
    if (
        not interpreter.is_absolute()
        or not interpreter.is_file()
        or not os.access(interpreter, os.X_OK)
    ):
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    command = (
        str(interpreter),
        str(source_root / "scripts" / "run_bounded_tiny_smoke.py"),
        RESUME_WORKER_ARGUMENT,
        str(bundle_path),
    )
    process: subprocess.Popen[bytes] | None = None
    try:
        process = subprocess.Popen(
            command,
            cwd=source_root,
            env=dict(environment),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        child_pid = process.pid
        if child_pid == os.getpid():
            raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
        try:
            stdout, stderr = process.communicate(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            raise SmokeTrainingError(SMOKE_RESUME_MISMATCH) from None
        if (
            process.returncode != 0
            or stderr
            or not stdout
            or len(stdout) > 128 * 1024
        ):
            raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
        result = _parse_fresh_process_replay_result(
            stdout,
            expected_pid=child_pid,
        )
    except SmokeTrainingError:
        raise
    except Exception:
        if process is not None and process.poll() is None:
            process.kill()
            process.communicate()
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH) from None
    expected_history = expected.get("history_checksums")
    if (
        result.authorization_sha256 != authorization.authorization_sha256
        or result.checkpoint_envelope_sha256 != envelope_sha256
        or result.request_sha256 != request_sha256
        or result.runtime_semantic_sha256 != expected.get("runtime_semantic_sha256")
        or result.rng_semantic_sha256 != expected.get("rng_semantic_sha256")
        or result.learning_rate_semantic_sha256
        != expected.get("learning_rate_semantic_sha256")
        or dict(result.history_checksums) != expected_history
        or expected.get("validation_updates") != VALIDATION_POINTS
    ):
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    return result


def _launch_replay_diagnostic(
    bundle_path: Path,
    environment: Mapping[str, str],
) -> Mapping[str, object]:
    source_root = _worker_source_root()
    process = subprocess.Popen(
        (
            str(Path(sys.executable)),
            str(source_root / "scripts" / "run_bounded_tiny_smoke.py"),
            RESUME_DIAGNOSTIC_WORKER_ARGUMENT,
            str(bundle_path),
        ),
        cwd=source_root,
        env=dict(environment),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    started = time.monotonic()
    crossed_600 = hard_timeout = False
    try:
        try:
            stdout, stderr = process.communicate(timeout=RESUME_WORKER_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            crossed_600 = True
            try:
                stdout, stderr = process.communicate(
                    timeout=RESUME_DIAGNOSTIC_HARD_TIMEOUT_SECONDS
                    - RESUME_WORKER_TIMEOUT_SECONDS
                )
            except subprocess.TimeoutExpired:
                hard_timeout = True
                process.kill()
                stdout, stderr = process.communicate()
    except BaseException:
        if process.poll() is None:
            process.kill()
            process.communicate()
        raise
    phases: tuple[str, ...] = ()
    stdout_status = "empty" if not stdout else "malformed"
    if len(stdout) > 128 * 1024 or len(stderr) > 128 * 1024:
        disposition = "CHANNEL_OVERSIZED"
    else:
        try:
            records = tuple(json.loads(line) for line in stderr.splitlines())
            if any(
                not isinstance(record, dict)
                or record.get("protocol") != RESUME_DIAGNOSTIC_PROTOCOL
                or not isinstance(record.get("phase"), str)
                or type(record.get("elapsed_ms")) is not int
                or record.get("result") is not True
                for record in records
            ):
                raise ValueError
            phases = tuple(record["phase"] for record in records)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
            disposition = "CHANNEL_MALFORMED"
        else:
            if process.returncode == 0 and stdout:
                if not phases or phases[-1] != "RESULT_ENCODED":
                    disposition = "CHANNEL_MALFORMED"
                else:
                    try:
                        _parse_fresh_process_replay_result(
                            stdout,
                            expected_pid=process.pid,
                        )
                    except SmokeTrainingError:
                        disposition = "RESULT_MALFORMED"
                    else:
                        stdout_status = "valid"
                        disposition = (
                            "COMPLETED_AFTER_600_SECONDS"
                            if crossed_600
                            else "COMPLETED_AT_OR_BELOW_600_SECONDS"
                        )
            elif hard_timeout:
                disposition = "HARD_TIMEOUT"
            else:
                disposition = "WORKER_FAILED"
    return MappingProxyType(
        {
            "crossed_600_seconds": crossed_600,
            "disposition": disposition,
            "elapsed_ms": int((time.monotonic() - started) * 1_000),
            "last_phase": phases[-1] if phases else None,
            "protocol": RESUME_DIAGNOSTIC_PROTOCOL,
            "stderr_bytes": len(stderr),
            "stderr_nonempty": bool(stderr),
            "stderr_sha256": _sha256_bytes(stderr),
            "stdout_bytes": len(stdout),
            "stdout_sha256": _sha256_bytes(stdout),
            "stdout_status": stdout_status,
            "worker_returncode": process.returncode,
        }
    )


@dataclass(frozen=True, slots=True)
class _Invocation3DiagnosticWorkspaceCustody:
    path: Path
    parent_device: int
    parent_inode: int
    device: int
    inode: int
    owner_uid: int
    _factory_token: object = field(repr=False, compare=False)


def _invocation3_diagnostic_workspace_path_is_safe(path: Path) -> bool:
    root = _INVOCATION3_DIAGNOSTIC_WORKSPACE_ROOT
    forbidden = {
        Path("/"),
        root,
        Path().absolute(),
        Path.cwd().absolute(),
        Path.home().absolute(),
        APPROVED_REPOSITORY_ROOT.absolute(),
    }
    return (
        isinstance(path, Path)
        and path.is_absolute()
        and path == path.absolute()
        and path.parent == root
        and path == root / path.name
        and path.name.startswith(_INVOCATION3_DIAGNOSTIC_WORKSPACE_PREFIX)
        and path.name not in {"", ".", ".."}
        and path not in forbidden
    )


def _create_invocation3_diagnostic_workspace(
    *,
    token: object,
) -> _Invocation3DiagnosticWorkspaceCustody:
    try:
        if token is not _AUTHORITY_TOKEN:
            raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
        root = _INVOCATION3_DIAGNOSTIC_WORKSPACE_ROOT
        parent_status = os.lstat(root)
        if not stat.S_ISDIR(parent_status.st_mode):
            raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
        path = Path(
            tempfile.mkdtemp(
                prefix=_INVOCATION3_DIAGNOSTIC_WORKSPACE_PREFIX,
                dir=root,
            )
        )
        workspace_status = os.lstat(path)
        if (
            not _invocation3_diagnostic_workspace_path_is_safe(path)
            or not stat.S_ISDIR(workspace_status.st_mode)
            or stat.S_IMODE(workspace_status.st_mode) != 0o700
            or workspace_status.st_uid != os.getuid()
        ):
            raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
        return _Invocation3DiagnosticWorkspaceCustody(
            path=path,
            parent_device=parent_status.st_dev,
            parent_inode=parent_status.st_ino,
            device=workspace_status.st_dev,
            inode=workspace_status.st_ino,
            owner_uid=workspace_status.st_uid,
            _factory_token=token,
        )
    except SmokeTrainingError:
        raise
    except Exception:
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH) from None


def _remove_invocation3_diagnostic_workspace(
    custody: _Invocation3DiagnosticWorkspaceCustody | None,
    *,
    token: object,
) -> None:
    if custody is None:
        return
    parent_descriptor = -1
    failure: BaseException | None = None
    try:
        if (
            type(custody) is not _Invocation3DiagnosticWorkspaceCustody
            or custody._factory_token is not token
            or token is not _AUTHORITY_TOKEN
            or not _invocation3_diagnostic_workspace_path_is_safe(custody.path)
            or custody.owner_uid != os.getuid()
            or not shutil.rmtree.avoids_symlink_attacks
        ):
            raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
        parent_descriptor = os.open(
            _INVOCATION3_DIAGNOSTIC_WORKSPACE_ROOT,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0),
        )
        parent_status = os.fstat(parent_descriptor)
        workspace_status = os.stat(
            custody.path.name,
            dir_fd=parent_descriptor,
            follow_symlinks=False,
        )
        if (
            not stat.S_ISDIR(parent_status.st_mode)
            or (parent_status.st_dev, parent_status.st_ino)
            != (custody.parent_device, custody.parent_inode)
            or not stat.S_ISDIR(workspace_status.st_mode)
            or (workspace_status.st_dev, workspace_status.st_ino)
            != (custody.device, custody.inode)
            or workspace_status.st_uid != custody.owner_uid
            or stat.S_IMODE(workspace_status.st_mode) != 0o700
        ):
            raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
        shutil.rmtree(custody.path.name, dir_fd=parent_descriptor)
        try:
            os.stat(
                custody.path.name,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            pass
        else:
            raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    except SmokeTrainingError as error:
        failure = error
    except Exception:
        failure = SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    if parent_descriptor >= 0:
        try:
            os.close(parent_descriptor)
        except BaseException:
            if failure is None:
                failure = SmokeTrainingError(SMOKE_RESUME_MISMATCH)
            else:
                failure.add_note("diagnostic cleanup descriptor close also failed")
    if failure is not None:
        raise failure


def _execute_invocation3_replay_diagnostic_impl(*, token: object) -> Mapping[str, object]:
    authorization = _construct_production_smoke_execution_authorization_impl(token=token)
    checkpoint = INVOCATION3_RETAINED_STAGE / "EnglishMono/cpu/checkpoint-0750"
    writer: PrivateRunArtifactWriter | None = None
    workspace: _Invocation3DiagnosticWorkspaceCustody | None = None
    result: Mapping[str, object] | None = None
    failure: BaseException | None = None
    try:
        files = {
            name: _stable_read(
                checkpoint / name,
                maximum_bytes=128 * 1024 * 1024,
            )[0]
            for name in _REPLAY_CHECKPOINT_FILE_NAMES
        }
        if _sha256_bytes(files["checkpoint_state.pt"]) != (
            INVOCATION3_CHECKPOINT_750_STATE_SHA256
        ):
            raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
        envelope = _checkpoint_envelope_from_files_for_tests_impl(
            files,
            _checkpoint_envelope_identity(files),
            token=token,
        )
        transaction_files = MappingProxyType(
            {
                "artifact_transaction_completion.json": files[
                    "CHECKPOINT_COMPLETE.json"
                ],
                "artifact_transaction_inventory.json": files["inventory.json"],
            }
        )
        workspace = _create_invocation3_diagnostic_workspace(token=token)
        output_parent = workspace.path / "private-output"
        writer = begin_private_run_artifacts(
            output_parent,
            "invocation3-replay-diagnostic",
            create_parent=True,
        )
        bundle_path, environment, _ = _create_replay_bundle(
            writer,
            authorization,
            envelope,
            transaction_files,
            output_parent,
            bundle_fault=None,
            test_fault=None,
        )
        result = _launch_replay_diagnostic(bundle_path, environment)
    except SmokeTrainingError as error:
        failure = error
    except Exception:
        failure = SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    except BaseException as error:
        failure = error
    cleanup_failure: BaseException | None = None
    if writer is not None:
        for descriptor in (writer._stage_descriptor, writer._parent_descriptor):
            try:
                os.close(descriptor)
            except BaseException as error:
                if cleanup_failure is None:
                    cleanup_failure = error
                else:
                    cleanup_failure.add_note(
                        "additional diagnostic cleanup step also failed closed"
                    )
    try:
        _remove_invocation3_diagnostic_workspace(workspace, token=token)
    except BaseException as error:
        if cleanup_failure is None:
            cleanup_failure = error
        else:
            cleanup_failure.add_note(
                "diagnostic workspace cleanup also failed closed"
            )
    if failure is not None:
        if cleanup_failure is not None:
            failure.add_note("diagnostic workspace cleanup also failed closed")
        raise failure
    if cleanup_failure is not None:
        if isinstance(cleanup_failure, SmokeTrainingError):
            raise cleanup_failure
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH) from None
    if result is None:
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    return result


def _run_fresh_process_resume_rehearsal(
    writer: PrivateRunArtifactWriter,
    authorization: SmokeExecutionAuthorization,
    envelope: CheckpointEnvelope,
    checkpoint_commit_result: object,
    expected: Mapping[str, object],
    output_parent: Path,
    *,
    bundle_fault: str | None = None,
    test_fault: str | None = None,
    timeout_seconds: float = RESUME_WORKER_TIMEOUT_SECONDS,
) -> _FreshProcessReplayResult:
    transaction_files = _read_committed_checkpoint_transaction(
        writer,
        envelope,
        checkpoint_commit_result,
    )
    bundle_path, environment, request_sha256 = _create_replay_bundle(
        writer,
        authorization,
        envelope,
        transaction_files,
        output_parent,
        bundle_fault=bundle_fault,
        test_fault=test_fault,
    )
    envelope_sha256 = envelope.envelope_sha256
    envelope = None  # type: ignore[assignment]
    try:
        return _launch_fresh_process_replay(
            bundle_path,
            environment,
            expected,
            authorization,
            envelope_sha256,
            request_sha256,
            timeout_seconds=timeout_seconds,
        )
    finally:
        _remove_replay_bundle(bundle_path)


def _run_synthetic_fresh_process_resume_for_tests_impl(
    authorization: SmokeExecutionAuthorization,
    envelope: CheckpointEnvelope,
    uninterrupted_runtime: TinySmokeConditionRuntime,
    workspace: Path,
    *,
    fault: str | None,
    token: object,
) -> Mapping[str, object]:
    """Exercise the canonical replay boundary with disposable synthetic state."""

    bundle_faults = {
        "wrong_condition",
        "wrong_update",
        "missing_envelope",
        "inconsistent_envelope",
    }
    worker_faults = {
        "child_nonzero",
        "timeout",
        "missing_result",
        "malformed_result",
        "identity_mismatch",
    }
    if (
        os.environ.get("CSLM_TRACKED_ONLY_TEST") != "1"
        or type(authorization) is not SmokeExecutionAuthorization
        or authorization._factory_token is not token
        or authorization.authority_kind not in {
            "synthetic_test_only",
            "synthetic_production_equivalent",
        }
        or type(envelope) is not CheckpointEnvelope
        or envelope.condition != "EnglishMono"
        or envelope.completed_update != 750
        or type(uninterrupted_runtime) is not TinySmokeConditionRuntime
        or uninterrupted_runtime._authorization is not authorization
        or uninterrupted_runtime.condition != "EnglishMono"
        or uninterrupted_runtime.completed_update != 1_000
        or not isinstance(workspace, Path)
        or not workspace.is_absolute()
        or workspace.exists()
        or workspace == APPROVED_OUTPUT_PARENT
        or APPROVED_OUTPUT_PARENT in workspace.parents
        or fault not in {None, *bundle_faults, *worker_faults}
    ):
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    writer: PrivateRunArtifactWriter | None = None
    workspace_identity: tuple[int, int] | None = None
    try:
        workspace.mkdir(mode=0o700)
        workspace_status = workspace.stat()
        workspace_identity = (workspace_status.st_dev, workspace_status.st_ino)
        output_parent = workspace / "private-output"
        writer = begin_private_run_artifacts(
            output_parent,
            "synthetic-resume-rehearsal",
            create_parent=True,
        )
        checkpoint_commit = commit_private_checkpoint(
            writer,
            condition="EnglishMono",
            completed_update=750,
            payloads=envelope._files,
        )
        comparison = _runtime_replay_comparison(uninterrupted_runtime)
        replay = _run_fresh_process_resume_rehearsal(
            writer,
            authorization,
            envelope,
            checkpoint_commit,
            comparison,
            output_parent,
            bundle_fault=fault if fault in bundle_faults else None,
            test_fault=fault if fault in worker_faults else None,
            timeout_seconds=0.05 if fault == "timeout" else RESUME_WORKER_TIMEOUT_SECONDS,
        )
        return MappingProxyType(
            {
                "checkpoint_update": replay.checkpoint_update,
                "first_replay_update": replay.first_replay_update,
                "fresh_interpreter": replay.fresh_interpreter,
                "last_replay_update": replay.last_replay_update,
                "parent_pid": os.getpid(),
                "replay_result_sha256": replay.result_sha256,
                "replay_update_count": replay.replay_update_count,
                "runtime_semantic_sha256": replay.runtime_semantic_sha256,
                "validation_updates": replay.validation_updates,
                "worker_pid": replay.worker_pid,
            }
        )
    except SmokeTrainingError:
        raise
    except Exception:
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH) from None
    finally:
        if writer is not None:
            for descriptor_name in ("_stage_descriptor", "_parent_descriptor"):
                descriptor = getattr(writer, descriptor_name, -1)
                if isinstance(descriptor, int) and descriptor >= 0:
                    try:
                        os.close(descriptor)
                    except OSError:
                        pass
        if workspace_identity is not None and workspace.exists():
            workspace_status = workspace.stat()
            if (workspace_status.st_dev, workspace_status.st_ino) != workspace_identity:
                raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
            shutil.rmtree(workspace)


def _execute_canonical_four_condition_orchestrator_impl(
    authorization: SmokeExecutionAuthorization,
    output_parent: Path,
    *,
    authority_kind: str,
    test_output: bool,
    token: object,
) -> PrivacySafeTerminalResult:
    """Run the one canonical four-condition Tiny smoke orchestration."""

    if (
        type(authorization) is not SmokeExecutionAuthorization
        or authorization._factory_token is not token
        or authorization.authority_kind != authority_kind
        or not isinstance(output_parent, Path)
        or not output_parent.is_absolute()
    ):
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    if test_output:
        if (
            os.environ.get("CSLM_TRACKED_ONLY_TEST") != "1"
            or authority_kind != "synthetic_production_equivalent"
            or output_parent == APPROVED_OUTPUT_PARENT
            or APPROVED_OUTPUT_PARENT in output_parent.parents
        ):
            raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    elif (
        os.environ.get("CSLM_TRACKED_ONLY_TEST") == "1"
        or authority_kind != "production_tracker_and_launch"
        or output_parent != APPROVED_OUTPUT_PARENT
    ):
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    _reanchor_consumed_view(authorization, code=SMOKE_APPROVAL_MISMATCH)
    if (
        authorization.device != "cpu"
        or authorization.maximum_concurrent_conditions != 1
        or authorization.launch_manifest.validation_points != VALIDATION_POINTS
        or authorization.launch_manifest.checkpoint_updates != CHECKPOINT_UPDATES
        or authorization.launch_manifest.optimizer_updates_per_condition != 1_000
    ):
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    if not test_output:
        _ensure_production_output_container()
    run_name = (
        "synthetic-smoke-" if test_output else "tiny-smoke-"
    ) + authorization.authorization_sha256[:24]
    try:
        writer = begin_private_run_artifacts(
            output_parent,
            run_name,
            create_parent=True,
        )
    except SmokeArtifactError as error:
        raise SmokeTrainingError(error.code) from None
    optimizer_set = _create_optimizer_set_impl(authorization, token=token)
    completed_conditions: list[str] = []
    condition_semantics: list[tuple[str, str]] = []
    resume_semantic = ""
    resume_result_sha256 = ""
    active_conditions = 0
    for condition in CONDITIONS:
        if active_conditions != 0:
            raise SmokeTrainingError(SMOKE_DEVICE_RUNTIME_MISMATCH)
        active_conditions += 1
        runtime = _begin_condition_runtime_impl(
            authorization,
            optimizer_set,
            condition,
            token=token,
        )
        checkpoint_results: list[tuple[int, str, str]] = []
        resume_envelope: CheckpointEnvelope | None = None
        resume_checkpoint_commit: object | None = None
        try:
            checkpoint_result = write_private_runtime_checkpoint(writer, runtime)
            checkpoint_results.append(
                (
                    0,
                    checkpoint_result.inventory_sha256,
                    checkpoint_result.completion_sha256,
                )
            )
            for _ in range(1_000):
                _execute_next_update_impl(runtime, token=token)
                if runtime.completed_update in VALIDATION_POINTS:
                    _validate_condition_impl(runtime, token=token)
                if runtime.completed_update in CHECKPOINT_UPDATES:
                    if condition == "EnglishMono" and runtime.completed_update == 750:
                        resume_envelope = checkpoint_envelope_for_runtime(runtime)
                    checkpoint_result = write_private_runtime_checkpoint(
                        writer,
                        runtime,
                        _envelope=resume_envelope
                        if condition == "EnglishMono"
                        and runtime.completed_update == 750
                        else None,
                    )
                    if condition == "EnglishMono" and runtime.completed_update == 750:
                        resume_checkpoint_commit = checkpoint_result
                    checkpoint_results.append(
                        (
                            runtime.completed_update,
                            checkpoint_result.inventory_sha256,
                            checkpoint_result.completion_sha256,
                        )
                    )
            if (
                runtime.completed_update != 1_000
                or tuple(item[0] for item in runtime._validation_history)
                != VALIDATION_POINTS
                or tuple(item[0] for item in checkpoint_results) != CHECKPOINT_UPDATES
            ):
                raise SmokeTrainingError(SMOKE_DATA_SCHEDULE_MISMATCH)
            uninterrupted_semantic = runtime_semantic_sha256(runtime)
            fresh_process_record: dict[str, object] | None = None
            if condition == "EnglishMono":
                if resume_envelope is None or resume_checkpoint_commit is None:
                    raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
                comparison = _runtime_replay_comparison(runtime)
                parent_rng_semantic = comparison["rng_semantic_sha256"]
                runtime = None  # type: ignore[assignment]
                replay_result = _run_fresh_process_resume_rehearsal(
                    writer,
                    authorization,
                    resume_envelope,
                    resume_checkpoint_commit,
                    comparison,
                    output_parent,
                )
                resume_semantic = replay_result.runtime_semantic_sha256
                resume_result_sha256 = replay_result.result_sha256
                if _semantic_hash(_rng_payload()) != parent_rng_semantic:
                    raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
                fresh_process_record = {
                    "checkpoint_update": replay_result.checkpoint_update,
                    "first_replay_update": replay_result.first_replay_update,
                    "fresh_interpreter": replay_result.fresh_interpreter,
                    "last_replay_update": replay_result.last_replay_update,
                    "protocol": RESUME_WORKER_PROTOCOL,
                    "replay_result_sha256": replay_result.result_sha256,
                    "replay_update_count": replay_result.replay_update_count,
                    "validation_updates": list(replay_result.validation_updates),
                    "worker_pid_differed": replay_result.worker_pid != os.getpid(),
                }
            condition_record = {
                "authorization_sha256": authorization.authorization_sha256,
                "candidate_checksum_record_sha256": (
                    authorization.approval.candidate_checksum_record_sha256
                ),
                "completed_optimizer_updates": 1_000,
                "condition": condition,
                "condition_protocol": "neu_tiny_smoke_condition_completion_v1",
                "device": "cpu",
                "launch_manifest_sha256": (
                    authorization.launch_manifest.manifest_sha256
                ),
                "tracker_authority": _tracker_authority_binding(authorization),
                "mechanics_passed": True,
                "sanitized_view_sha256": authorization.training_view_sha256,
                "semantic_sha256": uninterrupted_semantic,
            }
            if fresh_process_record is not None:
                condition_record["fresh_process_resume"] = fresh_process_record
            commit_private_condition_result(
                writer,
                condition=condition,
                payloads={
                    "condition_result.json": canonical_json_bytes(condition_record)
                },
            )
            condition_semantics.append((condition, uninterrupted_semantic))
            completed_conditions.append(condition)
        except SmokeArtifactError as error:
            raise SmokeTrainingError(error.code) from None
        finally:
            active_conditions -= 1
    if (
        active_conditions != 0
        or tuple(completed_conditions) != CONDITIONS
        or not resume_semantic
        or not resume_result_sha256
    ):
        raise SmokeTrainingError(SMOKE_RESUME_MISMATCH)
    run_identity = _sha256_bytes(
        canonical_json_bytes(
            [
                "neu_tiny_smoke_runtime_run_v1",
                authorization.authorization_sha256,
                condition_semantics,
                resume_semantic,
                resume_result_sha256,
            ]
        )
    )
    run_manifest = {
        "authorization_sha256": authorization.authorization_sha256,
        "candidate_checksum_record_sha256": (
            authorization.approval.candidate_checksum_record_sha256
        ),
        "completed_conditions": list(CONDITIONS),
        "completed_updates_per_condition": 1_000,
        "device": "cpu",
        "launch_manifest_sha256": authorization.launch_manifest.manifest_sha256,
        "tracker_authority": _tracker_authority_binding(authorization),
        "mechanics_passed": True,
        "protocol": "neu_tiny_smoke_runtime_run_v1",
        "run_identity_sha256": run_identity,
        "resume_rehearsal_result_sha256": resume_result_sha256,
        "sanitized_view_sha256": authorization.training_view_sha256,
        "terminal_classification": "mechanics_passed",
    }
    terminal_payload = {
        "completed_conditions": list(CONDITIONS),
        "completed_updates_per_condition": 1_000,
        "cpu_only": True,
        "mechanics_passed": True,
        "reporting_policy": "mechanics_only_private_non_scientific",
        "run_identity_sha256": run_identity,
        "tracker_authority_sha256": _semantic_hash(
            _tracker_authority_binding(authorization)
        ),
    }
    try:
        commit_result = commit_private_run(
            writer,
            payloads={
                "run_manifest.json": canonical_json_bytes(run_manifest),
                "terminal_result.json": canonical_json_bytes(terminal_payload),
            },
            completion_fields={},
        )
    except SmokeArtifactError as error:
        raise SmokeTrainingError(error.code) from None
    final_semantic = _sha256_bytes(
        canonical_json_bytes(
            [
                run_identity,
                commit_result.inventory_sha256,
                commit_result.completion_sha256,
            ]
        )
    )
    result = object.__new__(PrivacySafeTerminalResult)
    for name, value in {
        "mechanics_passed": True,
        "completed_conditions": CONDITIONS,
        "completed_updates_per_condition": 1_000,
        "cpu_only": True,
        "final_semantic_sha256": final_semantic,
        "reporting_policy": "mechanics_only_private_non_scientific",
    }.items():
        object.__setattr__(result, name, value)
    return result


def _execute_synthetic_production_equivalent_impl(
    authorization: SmokeExecutionAuthorization,
    output_parent: Path,
    *,
    token: object,
) -> PrivacySafeTerminalResult:
    """Exercise the canonical production orchestration with synthetic tensors only."""

    return _execute_canonical_four_condition_orchestrator_impl(
        authorization,
        output_parent,
        authority_kind="synthetic_production_equivalent",
        test_output=True,
        token=token,
    )


def _execute_bounded_tiny_smoke_impl(
    authorization: SmokeExecutionAuthorization,
    *,
    token: object,
) -> PrivacySafeTerminalResult:
    """Execute only a fully constructed future production authorization."""

    if (
        type(authorization) is not SmokeExecutionAuthorization
        or authorization._factory_token is not token
        or authorization.authority_kind != "production_tracker_and_launch"
        or authorization._training_view.authority_kind != "production_loader"
        or authorization._tracker_path != APPROVED_TRACKER_PATH
        or authorization._launch_path != APPROVED_LAUNCH_MANIFEST_PATH
        or (
            authorization.approval.tracker_sha256,
            authorization.approval.tracker_size,
        )
        == (APPROVED_TRACKER_SHA256, APPROVED_TRACKER_SIZE)
        or authorization.launch_manifest.tracker_baseline_sha256
        != APPROVED_TRACKER_SHA256
        or authorization.launch_manifest.tracker_baseline_size
        != APPROVED_TRACKER_SIZE
        or authorization.launch_manifest.tracker_baseline_version
        != APPROVED_TRACKER_VERSION
        or authorization.launch_manifest.tracker_baseline_canonical_date
        != APPROVED_TRACKER_DATE
        or authorization.approval.candidate_checksum_record_sha256
        != APPROVED_CANDIDATE_CHECKSUM_RECORD_SHA256
        or authorization.approval.preparation_manifest_sha256
        != APPROVED_PREPARATION_MANIFEST_SHA256
        or authorization.approval.schedule_plan_identity_sha256
        != APPROVED_SCHEDULE_PLAN_IDENTITY_SHA256
        or not authorization.approval.launch_manifest_approved
        or authorization.device != "cpu"
        or authorization.maximum_concurrent_conditions != 1
    ):
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    if os.environ.get("CSLM_TRACKED_ONLY_TEST") == "1":
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    approved_launch_sha256, tracker_version, canonical_date = (
        _parse_tracker_launch_approval_record(
            authorization.approval._tracker_bytes,
            authority_kind="production_tracker_and_launch",
            candidate_checksum=(
                authorization.approval.candidate_checksum_record_sha256
            ),
            preparation_manifest=(
                authorization.approval.preparation_manifest_sha256
            ),
            schedule_identity=(
                authorization.approval.schedule_plan_identity_sha256
            ),
            executor_commit=authorization.launch_manifest.executor_commit,
            executor_closure_digest=(
                authorization.launch_manifest.executor_closure_digest
            ),
            runtime_policy_sha256=(
                authorization.launch_manifest.runtime_policy_sha256
            ),
            output_parent=APPROVED_OUTPUT_PARENT,
        )
    )
    if (
        approved_launch_sha256
        != authorization.launch_manifest.manifest_file_sha256
        or tracker_version != authorization.approval.tracker_version
        or canonical_date != authorization.approval.canonical_date
    ):
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    _reanchor_consumed_view(authorization, code=SMOKE_APPROVAL_MISMATCH)
    executor_commit, executor_closure = _executor_repository_identity(
        APPROVED_REPOSITORY_ROOT
    )
    if (
        authorization.launch_manifest.executor_commit != executor_commit
        or authorization.launch_manifest.executor_closure_digest != executor_closure
        or authorization.launch_manifest.runtime_policy_sha256
        != _verify_supported_runtime()
        or authorization.launch_manifest.output_root_identity_sha256
        != _output_root_identity(APPROVED_OUTPUT_PARENT)
    ):
        raise SmokeTrainingError(SMOKE_APPROVAL_MISMATCH)
    _validate_output_root_custody(APPROVED_OUTPUT_PARENT, production=True)
    return _execute_canonical_four_condition_orchestrator_impl(
        authorization,
        APPROVED_OUTPUT_PARENT,
        authority_kind="production_tracker_and_launch",
        test_output=False,
        token=token,
    )


_STABLE_SMOKE_TYPE_NAMES = (
    "CandidateApprovalEvidence",
    "CheckpointEnvelope",
    "ExplicitLearningRateState",
    "PrivacySafeTerminalResult",
    "RuntimeRunManifest",
    "SmokeExecutionAuthorization",
    "SmokeLaunchManifest",
    "SmokeTrainingError",
    "TinySmokeConditionRuntime",
    "TinySmokeOptimizerSet",
    "UpdateMechanicsResult",
    "ValidationMechanicsResult",
)
_previous_runtime_state = getattr(
    sys.modules[__name__],
    "_STABLE_SMOKE_RUNTIME_STATE",
    None,
)


def _stabilize_smoke_types_and_token(
    previous: tuple[Mapping[str, type[object]], object] | None,
) -> tuple[Mapping[str, type[object]], object]:
    current = {name: globals()[name] for name in _STABLE_SMOKE_TYPE_NAMES}
    if previous is None:
        stable = MappingProxyType(dict(current))
        token = object()
    else:
        stable, token = previous
        if set(stable) != set(_STABLE_SMOKE_TYPE_NAMES):
            raise RuntimeError("stable Tiny smoke boundary types are invalid")
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
    state = (stable, token)
    module = sys.modules[__name__]
    if previous is None:

        class _StableSmokeModule(ModuleType):
            def __getattribute__(self, name: str) -> object:
                if name == "_STABLE_SMOKE_RUNTIME_STATE":
                    return state
                return ModuleType.__getattribute__(self, name)

        module.__class__ = _StableSmokeModule
    globals()["_STABLE_SMOKE_RUNTIME_STATE"] = state
    return state


_STABLE_SMOKE_RUNTIME_STATE = _stabilize_smoke_types_and_token(_previous_runtime_state)
_STABLE_SMOKE_BOUNDARY_TYPES, _AUTHORITY_TOKEN = _STABLE_SMOKE_RUNTIME_STATE
del _previous_runtime_state
del _stabilize_smoke_types_and_token


def _clone_smoke_implementation_graph() -> Mapping[str, FunctionType]:
    """Clone application callables into one module-alias-independent namespace."""

    original = {
        name: value
        for name, value in globals().items()
        if isinstance(value, FunctionType)
        and value.__module__ == __name__
        and name not in {"_clone_smoke_implementation_graph"}
    }
    reviewed_globals = dict(globals())
    reviewed: dict[str, FunctionType] = {}
    for name, function in original.items():
        clone = FunctionType(
            function.__code__,
            reviewed_globals,
            function.__name__,
            function.__defaults__,
            function.__closure__,
        )
        clone.__kwdefaults__ = dict(function.__kwdefaults__ or {})
        clone.__annotations__ = dict(function.__annotations__)
        clone.__doc__ = function.__doc__
        clone.__module__ = function.__module__
        clone.__qualname__ = function.__qualname__
        reviewed[name] = clone
    reviewed_globals.update(reviewed)
    return MappingProxyType(reviewed)


_REVIEWED_SMOKE_IMPLEMENTATION_GRAPH = _clone_smoke_implementation_graph()
del _clone_smoke_implementation_graph


def _public_factories(
    token: object,
    reviewed: Mapping[str, FunctionType],
) -> Mapping[str, Callable[..., object]]:
    load_approval_impl = reviewed["_load_candidate_approval_evidence_impl"]
    load_synthetic_approval_impl = reviewed[
        "_load_synthetic_candidate_approval_for_tests_impl"
    ]
    launch_impl = reviewed["_derive_synthetic_launch_manifest_for_tests_impl"]
    authorization_impl = reviewed[
        "_derive_synthetic_execution_authorization_for_tests_impl"
    ]
    production_equivalent_authorization_impl = reviewed[
        "_derive_synthetic_production_authorization_for_tests_impl"
    ]
    production_runtime_admission_authorization_impl = reviewed[
        "_derive_production_condition_runtime_authorization_for_tests_impl"
    ]
    production_authority_impl = reviewed[
        "_construct_production_smoke_execution_authorization_impl"
    ]
    synthetic_future_authority_impl = reviewed[
        "_construct_synthetic_future_production_authorization_for_tests_impl"
    ]
    optimizers_impl = reviewed["_create_optimizer_set_impl"]
    runtime_impl = reviewed["_begin_condition_runtime_impl"]
    update_impl = reviewed["_execute_next_update_impl"]
    validation_impl = reviewed["_validate_condition_impl"]
    restore_impl = reviewed["_restore_runtime_from_checkpoint_impl"]
    envelope_from_files_impl = reviewed[
        "_checkpoint_envelope_from_files_for_tests_impl"
    ]
    production_equivalent_impl = reviewed[
        "_execute_synthetic_production_equivalent_impl"
    ]
    resume_worker_impl = reviewed["_execute_tiny_resume_replay_worker_impl"]
    invocation3_diagnostic_impl = reviewed[
        "_execute_invocation3_replay_diagnostic_impl"
    ]
    synthetic_resume_impl = reviewed[
        "_run_synthetic_fresh_process_resume_for_tests_impl"
    ]
    production_impl = reviewed["_execute_bounded_tiny_smoke_impl"]

    def load_approval(path: Path) -> CandidateApprovalEvidence:
        result: CandidateApprovalEvidence | None = None
        failure: str | None = None
        try:
            result = load_approval_impl(path, token=token)
        except SmokeTrainingError as error:
            failure = error.code
        except Exception:
            failure = SMOKE_APPROVAL_MISMATCH
        path = Path()
        if failure is not None or result is None:
            raise SmokeTrainingError(failure or SMOKE_APPROVAL_MISMATCH)
        return result

    def load_synthetic_approval(
        path: Path,
        *,
        candidate_checksum: str,
        preparation_manifest: str,
        schedule_identity: str,
    ) -> CandidateApprovalEvidence:
        result: CandidateApprovalEvidence | None = None
        failure: str | None = None
        try:
            result = load_synthetic_approval_impl(
                path,
                candidate_checksum=candidate_checksum,
                preparation_manifest=preparation_manifest,
                schedule_identity=schedule_identity,
                token=token,
            )
        except SmokeTrainingError as error:
            failure = error.code
        except Exception:
            failure = SMOKE_APPROVAL_MISMATCH
        path = Path()
        candidate_checksum = ""
        preparation_manifest = ""
        schedule_identity = ""
        if failure is not None or result is None:
            raise SmokeTrainingError(failure or SMOKE_APPROVAL_MISMATCH)
        return result

    def launch(
        approval: CandidateApprovalEvidence,
        *,
        executor_commit: str,
        executor_closure_digest: str,
    ) -> SmokeLaunchManifest:
        result: SmokeLaunchManifest | None = None
        failure: str | None = None
        try:
            result = launch_impl(
                approval,
                executor_commit=executor_commit,
                executor_closure_digest=executor_closure_digest,
                token=token,
            )
        except SmokeTrainingError as error:
            failure = error.code
        except Exception:
            failure = SMOKE_APPROVAL_MISMATCH
        approval = None  # type: ignore[assignment]
        executor_commit = ""
        executor_closure_digest = ""
        if failure is not None or result is None:
            raise SmokeTrainingError(failure or SMOKE_APPROVAL_MISMATCH)
        return result

    def authorize(
        approval: CandidateApprovalEvidence,
        launch_manifest: SmokeLaunchManifest,
        training_view: SanitizedTrainingView,
        paired_initialization: PairedInitialization,
    ) -> SmokeExecutionAuthorization:
        result: SmokeExecutionAuthorization | None = None
        failure: str | None = None
        try:
            result = authorization_impl(
                approval,
                launch_manifest,
                training_view,
                paired_initialization,
                token=token,
            )
        except SmokeTrainingError as error:
            failure = error.code
        except Exception:
            failure = SMOKE_APPROVAL_MISMATCH
        approval = None  # type: ignore[assignment]
        launch_manifest = None  # type: ignore[assignment]
        training_view = None  # type: ignore[assignment]
        paired_initialization = None  # type: ignore[assignment]
        if failure is not None or result is None:
            raise SmokeTrainingError(failure or SMOKE_APPROVAL_MISMATCH)
        return result

    def authorize_production_equivalent(
        tracker_path: Path,
        launch_path: Path,
        training_view: SanitizedTrainingView,
        paired_initialization: PairedInitialization,
        *,
        executor_commit: str,
        executor_closure_digest: str,
    ) -> SmokeExecutionAuthorization:
        result: SmokeExecutionAuthorization | None = None
        failure: str | None = None
        try:
            result = production_equivalent_authorization_impl(
                tracker_path,
                launch_path,
                training_view,
                paired_initialization,
                executor_commit=executor_commit,
                executor_closure_digest=executor_closure_digest,
                token=token,
            )
        except SmokeTrainingError as error:
            failure = error.code
        except Exception:
            failure = SMOKE_APPROVAL_MISMATCH
        tracker_path = Path()
        launch_path = Path()
        training_view = None  # type: ignore[assignment]
        paired_initialization = None  # type: ignore[assignment]
        executor_commit = ""
        executor_closure_digest = ""
        if failure is not None or result is None:
            raise SmokeTrainingError(failure or SMOKE_APPROVAL_MISMATCH)
        return result

    def authorize_production_runtime_admission(
        tracker_path: Path,
        launch_path: Path,
        training_view: SanitizedTrainingView,
        paired_initialization: PairedInitialization,
        *,
        executor_commit: str,
        executor_closure_digest: str,
    ) -> SmokeExecutionAuthorization:
        result: SmokeExecutionAuthorization | None = None
        failure: str | None = None
        try:
            result = production_runtime_admission_authorization_impl(
                tracker_path,
                launch_path,
                training_view,
                paired_initialization,
                executor_commit=executor_commit,
                executor_closure_digest=executor_closure_digest,
                token=token,
            )
        except SmokeTrainingError as error:
            failure = error.code
        except Exception:
            failure = SMOKE_APPROVAL_MISMATCH
        tracker_path = Path()
        launch_path = Path()
        training_view = None  # type: ignore[assignment]
        paired_initialization = None  # type: ignore[assignment]
        executor_commit = ""
        executor_closure_digest = ""
        if failure is not None or result is None:
            raise SmokeTrainingError(failure or SMOKE_APPROVAL_MISMATCH)
        return result

    def construct_production_authority() -> SmokeExecutionAuthorization:
        result: SmokeExecutionAuthorization | None = None
        failure: str | None = None
        try:
            result = production_authority_impl(token=token)
        except SmokeTrainingError as error:
            failure = error.code
        except Exception:
            failure = SMOKE_APPROVAL_MISMATCH
        if failure is not None or result is None:
            raise SmokeTrainingError(failure or SMOKE_APPROVAL_MISMATCH)
        return result

    def construct_synthetic_future_authority(
        repository_root: Path,
        tracker_path: Path,
        launch_path: Path,
        candidate_root: Path,
        key_path: Path,
        output_parent: Path,
        synthetic_view: SanitizedTrainingView,
        *,
        _test_hook: Callable[[str], None] | None = None,
    ) -> SmokeExecutionAuthorization:
        result: SmokeExecutionAuthorization | None = None
        failure: str | None = None
        try:
            result = synthetic_future_authority_impl(
                repository_root,
                tracker_path,
                launch_path,
                candidate_root,
                key_path,
                output_parent,
                synthetic_view,
                test_hook=_test_hook,
                token=token,
            )
        except SmokeTrainingError as error:
            failure = error.code
        except Exception:
            failure = SMOKE_APPROVAL_MISMATCH
        repository_root = Path()
        tracker_path = Path()
        launch_path = Path()
        candidate_root = Path()
        key_path = Path()
        output_parent = Path()
        synthetic_view = None  # type: ignore[assignment]
        _test_hook = None
        if failure is not None or result is None:
            raise SmokeTrainingError(failure or SMOKE_APPROVAL_MISMATCH)
        return result

    def optimizers(authorization: SmokeExecutionAuthorization) -> TinySmokeOptimizerSet:
        result: TinySmokeOptimizerSet | None = None
        failure: str | None = None
        try:
            result = optimizers_impl(authorization, token=token)
        except SmokeTrainingError as error:
            failure = error.code
        except Exception:
            failure = SMOKE_OPTIMIZER_SCHEDULER_FAILURE
        authorization = None  # type: ignore[assignment]
        if failure is not None or result is None:
            raise SmokeTrainingError(
                failure or SMOKE_OPTIMIZER_SCHEDULER_FAILURE
            )
        return result

    def runtime(
        authorization: SmokeExecutionAuthorization,
        optimizer_set: TinySmokeOptimizerSet,
        condition: str,
    ) -> TinySmokeConditionRuntime:
        result: TinySmokeConditionRuntime | None = None
        failure: str | None = None
        try:
            result = runtime_impl(
                authorization,
                optimizer_set,
                condition,
                token=token,
            )
        except SmokeTrainingError as error:
            failure = error.code
        except Exception:
            failure = SMOKE_APPROVAL_MISMATCH
        authorization = None  # type: ignore[assignment]
        optimizer_set = None  # type: ignore[assignment]
        condition = ""
        if failure is not None or result is None:
            raise SmokeTrainingError(failure or SMOKE_APPROVAL_MISMATCH)
        return result

    def update(runtime_value: TinySmokeConditionRuntime) -> UpdateMechanicsResult:
        result: UpdateMechanicsResult | None = None
        failure: str | None = None
        try:
            result = update_impl(runtime_value, token=token)
        except SmokeTrainingError as error:
            failure = error.code
        except Exception:
            failure = SMOKE_DATA_SCHEDULE_MISMATCH
        runtime_value = None  # type: ignore[assignment]
        if failure is not None or result is None:
            raise SmokeTrainingError(failure or SMOKE_DATA_SCHEDULE_MISMATCH)
        return result

    def validation(runtime_value: TinySmokeConditionRuntime) -> ValidationMechanicsResult:
        result: ValidationMechanicsResult | None = None
        failure: str | None = None
        try:
            result = validation_impl(runtime_value, token=token)
        except SmokeTrainingError as error:
            failure = error.code
        except Exception:
            failure = SMOKE_VALIDATION_MISMATCH
        runtime_value = None  # type: ignore[assignment]
        if failure is not None or result is None:
            raise SmokeTrainingError(failure or SMOKE_VALIDATION_MISMATCH)
        return result

    def restore(
        authorization: SmokeExecutionAuthorization,
        optimizer_set: TinySmokeOptimizerSet,
        condition: str,
        envelope: CheckpointEnvelope,
        *,
        expected_completed_update: int,
    ) -> TinySmokeConditionRuntime:
        result: TinySmokeConditionRuntime | None = None
        failure: str | None = None
        try:
            result = restore_impl(
                authorization,
                optimizer_set,
                condition,
                envelope,
                expected_completed_update=expected_completed_update,
                token=token,
            )
        except SmokeTrainingError as error:
            failure = error.code
        except Exception:
            failure = SMOKE_RESUME_MISMATCH
        authorization = None  # type: ignore[assignment]
        optimizer_set = None  # type: ignore[assignment]
        condition = ""
        envelope = None  # type: ignore[assignment]
        expected_completed_update = -1
        if failure is not None or result is None:
            raise SmokeTrainingError(failure or SMOKE_RESUME_MISMATCH)
        return result

    def envelope_from_files(
        files: Mapping[str, bytes],
        *,
        expected_envelope_sha256: str,
    ) -> CheckpointEnvelope:
        try:
            return envelope_from_files_impl(
                files,
                expected_envelope_sha256,
                token=token,
            )
        except SmokeTrainingError:
            raise
        except Exception:
            raise SmokeTrainingError(SMOKE_RESUME_MISMATCH) from None

    def production(
        authorization: SmokeExecutionAuthorization,
    ) -> PrivacySafeTerminalResult:
        result: PrivacySafeTerminalResult | None = None
        failure: str | None = None
        try:
            result = production_impl(authorization, token=token)
        except SmokeTrainingError as error:
            failure = error.code
        except Exception:
            failure = SMOKE_APPROVAL_MISMATCH
        authorization = None  # type: ignore[assignment]
        if failure is not None or result is None:
            raise SmokeTrainingError(failure or SMOKE_APPROVAL_MISMATCH)
        return result

    def production_equivalent(
        authorization: SmokeExecutionAuthorization,
        output_parent: Path,
    ) -> PrivacySafeTerminalResult:
        result: PrivacySafeTerminalResult | None = None
        failure: str | None = None
        try:
            result = production_equivalent_impl(
                authorization,
                output_parent,
                token=token,
            )
        except SmokeTrainingError as error:
            failure = error.code
        except Exception:
            failure = SMOKE_APPROVAL_MISMATCH
        authorization = None  # type: ignore[assignment]
        output_parent = Path()
        if failure is not None or result is None:
            raise SmokeTrainingError(failure or SMOKE_APPROVAL_MISMATCH)
        return result

    def resume_worker(
        bundle_path: Path,
        *,
        diagnostic_sink: Callable[[str, int | None], None] | None = None,
    ) -> bytes:
        result: bytes | None = None
        failure: str | None = None
        try:
            result = resume_worker_impl(
                bundle_path,
                token=token,
                diagnostic_sink=diagnostic_sink,
            )
        except SmokeTrainingError as error:
            failure = error.code
        except Exception:
            failure = SMOKE_RESUME_MISMATCH
        bundle_path = Path()
        if failure is not None or result is None:
            raise SmokeTrainingError(failure or SMOKE_RESUME_MISMATCH)
        return result

    def invocation3_diagnostic() -> Mapping[str, object]:
        try:
            return invocation3_diagnostic_impl(token=token)
        except SmokeTrainingError:
            raise
        except Exception:
            raise SmokeTrainingError(SMOKE_RESUME_MISMATCH) from None

    def synthetic_resume(
        authorization: SmokeExecutionAuthorization,
        envelope: CheckpointEnvelope,
        uninterrupted_runtime: TinySmokeConditionRuntime,
        workspace: Path,
        *,
        fault: str | None = None,
    ) -> Mapping[str, object]:
        result: Mapping[str, object] | None = None
        failure: str | None = None
        try:
            result = synthetic_resume_impl(
                authorization,
                envelope,
                uninterrupted_runtime,
                workspace,
                fault=fault,
                token=token,
            )
        except SmokeTrainingError as error:
            failure = error.code
        except Exception:
            failure = SMOKE_RESUME_MISMATCH
        authorization = None  # type: ignore[assignment]
        envelope = None  # type: ignore[assignment]
        uninterrupted_runtime = None  # type: ignore[assignment]
        workspace = Path()
        fault = None
        if failure is not None or result is None:
            raise SmokeTrainingError(failure or SMOKE_RESUME_MISMATCH)
        return result

    return MappingProxyType(
        {
            "load_candidate_approval_evidence": load_approval,
            "load_synthetic_candidate_approval_for_tests": load_synthetic_approval,
            "derive_synthetic_smoke_launch_manifest_for_tests": launch,
            "derive_synthetic_smoke_execution_authorization_for_tests": authorize,
            "derive_synthetic_production_authorization_for_tests": (
                authorize_production_equivalent
            ),
            "derive_production_condition_runtime_authorization_for_tests": (
                authorize_production_runtime_admission
            ),
            "construct_production_smoke_execution_authorization": (
                construct_production_authority
            ),
            "construct_synthetic_future_production_authorization_for_tests": (
                construct_synthetic_future_authority
            ),
            "create_tiny_smoke_optimizers": optimizers,
            "begin_tiny_smoke_condition": runtime,
            "execute_next_optimizer_update": update,
            "validate_tiny_smoke_condition": validation,
            "restore_synthetic_runtime_from_checkpoint": restore,
            "reconstitute_checkpoint_envelope_for_tests": envelope_from_files,
            "execute_bounded_tiny_smoke": production,
            "execute_synthetic_production_equivalent_for_tests": (
                production_equivalent
            ),
            "execute_tiny_resume_replay_worker": resume_worker,
            "run_invocation3_replay_diagnostic": invocation3_diagnostic,
            "run_synthetic_fresh_process_resume_for_tests": synthetic_resume,
        }
    )


_factories = _public_factories(
    _AUTHORITY_TOKEN,
    _REVIEWED_SMOKE_IMPLEMENTATION_GRAPH,
)
globals().update(_factories)
del _factories
del _public_factories

SMOKE_PRODUCTION_REVIEWED_CALLABLES = frozenset(
    {
        "approved_learning_rate",
        "derive_tiny_dropout_seed",
        "execute_bounded_tiny_smoke",
        "execute_tiny_resume_replay_worker",
        "run_invocation3_replay_diagnostic",
        "learning_rate_state_after_update",
        "load_candidate_approval_evidence",
        "construct_production_smoke_execution_authorization",
    }
)
SMOKE_EXTERNAL_APPLICATION_CALLABLE_ALLOWLIST = frozenset()
SMOKE_PUBLIC_BOUNDARY_CLASS_INVENTORY = MappingProxyType(
    {
        __name__: frozenset(_STABLE_SMOKE_TYPE_NAMES),
        "cslm.modeling.preparation": frozenset(
            {
                "SanitizedConditionTrainingView",
                "SanitizedTensorArrays",
                "SanitizedTrainingView",
            }
        ),
        "cslm.modeling.smoke_artifacts": frozenset(
            {
                "ArtifactCommitResult",
                "PrivateRunArtifactWriter",
                "SmokeArtifactError",
            }
        ),
    }
)
