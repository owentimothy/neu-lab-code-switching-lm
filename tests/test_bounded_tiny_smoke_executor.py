from __future__ import annotations

import hashlib
import importlib
import inspect
import io
import json
import os
import random
import stat
import subprocess
import sys
import traceback
from dataclasses import replace
from pathlib import Path
from typing import Mapping

import numpy as np
import pytest
import torch

import cslm.modeling.smoke_artifacts as artifact_module
import cslm.modeling.smoke_training as smoke_module
from cslm.modeling.config import CONDITIONS, NEU_TINY
from cslm.modeling.initialization import (
    TINY_SMOKE_SEED_PLANS,
    create_paired_initialization,
    tied_parameter_groups,
)
from cslm.modeling.masking import mask_packed_sequence
from cslm.modeling.preparation import (
    PreparationError,
    SanitizedConditionTrainingView,
    SanitizedTensorArrays,
    SanitizedTrainingView,
)
from cslm.modeling.smoke_artifacts import (
    ArtifactCommitResult,
    PrivateRunArtifactWriter,
    SmokeArtifactError,
    begin_private_run_artifacts,
    commit_private_checkpoint,
    commit_private_condition_result,
    commit_private_run,
)
from cslm.modeling.smoke_training import (
    APPROVED_TRACKER_DATE,
    APPROVED_TRACKER_SHA256,
    APPROVED_TRACKER_SIZE,
    APPROVED_TRACKER_VERSION,
    DROPOUT_BASE_SEED,
    DROPOUT_PROTOCOL,
    EXECUTOR_CLOSURE_FILES,
    LEARNING_RATE_PROTOCOL,
    SMOKE_APPROVAL_MISMATCH,
    SMOKE_ARTIFACT_COMMIT_INDETERMINATE,
    SMOKE_CHECKPOINT_WRITE_FAILURE,
    SMOKE_DATA_SCHEDULE_MISMATCH,
    SMOKE_FAILURE_CODES,
    SMOKE_NONFINITE_GRADIENT,
    SMOKE_NONFINITE_LOSS,
    SMOKE_OPTIMIZER_SCHEDULER_FAILURE,
    SMOKE_RESUME_MISMATCH,
    SMOKE_TARGET_COUNT_MISMATCH,
    SMOKE_VALIDATION_MISMATCH,
    VALIDATION_POINTS,
    CandidateApprovalEvidence,
    CheckpointEnvelope,
    PrivacySafeTerminalResult,
    RuntimeRunManifest,
    SmokeExecutionAuthorization,
    SmokeLaunchManifest,
    SmokeTrainingError,
    TinySmokeConditionRuntime,
    TinySmokeOptimizerSet,
    approved_learning_rate,
    begin_tiny_smoke_condition,
    checkpoint_envelope_for_runtime,
    checkpoint_payloads_for_runtime,
    construct_production_smoke_execution_authorization,
    construct_synthetic_future_production_authorization_for_tests,
    create_synthetic_smoke_training_view_for_tests,
    create_tiny_smoke_optimizers,
    derive_production_condition_runtime_authorization_for_tests,
    derive_synthetic_production_authorization_for_tests,
    derive_synthetic_smoke_execution_authorization_for_tests,
    derive_synthetic_smoke_launch_manifest_for_tests,
    derive_tiny_dropout_seed,
    execute_bounded_tiny_smoke,
    execute_next_optimizer_update,
    execute_synthetic_production_equivalent_for_tests,
    learning_rate_state_after_update,
    load_candidate_approval_evidence,
    load_synthetic_candidate_approval_for_tests,
    prime_synthetic_runtime_to_checkpoint_for_tests,
    prime_synthetic_runtime_to_update_for_tests,
    production_condition_runtime_authority_documents_for_tests,
    reconstitute_checkpoint_envelope_for_tests,
    restore_synthetic_runtime_from_checkpoint,
    run_synthetic_fresh_process_resume_for_tests,
    runtime_semantic_sha256,
    synthetic_future_production_authority_documents_for_tests,
    synthetic_production_authority_documents_for_tests,
    validate_tiny_smoke_condition,
)


def _arrays(
    *,
    rows: int = 2,
    lexical: int = 48,
    varied: bool = False,
) -> dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]]:
    result: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    for condition_index, condition in enumerate(CONDITIONS):
        input_ids = np.zeros((rows, 128), dtype=np.uint16)
        attention = np.zeros((rows, 128), dtype=np.uint8)
        token_types = np.zeros((rows, 128), dtype=np.uint8)
        for row in range(rows):
            row_lexical = lexical - (row % 5 if varied else 0)
            input_ids[row, 0] = 2
            for offset in range(row_lexical):
                input_ids[row, offset + 1] = (
                    5 + (condition_index * 997 + row * 131 + offset) % 7_995
                )
            input_ids[row, row_lexical + 1] = 3
            attention[row, : row_lexical + 2] = 1
        result[condition] = (input_ids, attention, token_types)
    return result


def _approval_sentence(candidate: str) -> str:
    return (
        "Timothy explicitly approves the exact candidate checksum-record SHA-256 `"
        + candidate
        + "` for the bounded Tiny BERT smoke-training gate and, subject to later "
        "training gates, the primary naturalistic experiment."
    )


def _tracker_text(view: SanitizedTrainingView) -> str:
    return "\n".join(
        (
            "# Synthetic Tiny smoke authority fixture",
            f"**Tracker version:** {APPROVED_TRACKER_VERSION}",
            f"**Canonical status date:** {APPROVED_TRACKER_DATE}",
            _approval_sentence(view.candidate_checksum_record_sha256),
            view.preparation_manifest_sha256,
            view.schedule_plan_identity_sha256,
            "neu_real_preparation_v1",
            "candidate_unapproved",
            "No launch manifest is created or approved",
            "Real execution remains unauthorized",
            "The context-matched sensitivity experiment remains mandatory.",
            "",
        )
    )


def _write_tracker(path: Path, view: SanitizedTrainingView, text: str | None = None) -> Path:
    path.write_text(_tracker_text(view) if text is None else text, encoding="utf-8")
    os.chmod(path, 0o644)
    return path


def _authority(
    tmp_path: Path,
    *,
    view: SanitizedTrainingView | None = None,
    test_updates: int = 1,
    rows: int = 2,
    lexical: int = 48,
    microbatch_size: int = 2,
):
    view = view or create_synthetic_smoke_training_view_for_tests(
        _arrays(rows=rows, lexical=lexical),
        test_updates=test_updates,
        microbatch_size=microbatch_size,
    )
    tracker = _write_tracker(tmp_path / "synthetic-tracker.md", view)
    approval = load_synthetic_candidate_approval_for_tests(
        tracker,
        candidate_checksum=view.candidate_checksum_record_sha256,
        preparation_manifest=view.preparation_manifest_sha256,
        schedule_identity=view.schedule_plan_identity_sha256,
    )
    launch = derive_synthetic_smoke_launch_manifest_for_tests(
        approval,
        executor_commit="a" * 40,
        executor_closure_digest="b" * 64,
    )
    paired = create_paired_initialization(NEU_TINY, TINY_SMOKE_SEED_PLANS[0])
    authorization = derive_synthetic_smoke_execution_authorization_for_tests(
        approval,
        launch,
        view,
        paired,
    )
    optimizers = create_tiny_smoke_optimizers(authorization)
    return view, approval, launch, paired, authorization, optimizers


def _runtime(tmp_path: Path, **kwargs):
    material = _authority(tmp_path, **kwargs)
    runtime = begin_tiny_smoke_condition(material[4], material[5], "EnglishMono")
    return (*material, runtime)


def test_fixed_failure_categories_are_exact_and_privacy_safe() -> None:
    assert SMOKE_FAILURE_CODES == (
        "SMOKE_APPROVAL_MISMATCH",
        "SMOKE_CANDIDATE_VERIFICATION_FAILURE",
        "SMOKE_INITIALIZATION_MISMATCH",
        "SMOKE_DEVICE_RUNTIME_MISMATCH",
        "SMOKE_DATA_SCHEDULE_MISMATCH",
        "SMOKE_MASKING_MISMATCH",
        "SMOKE_NONFINITE_LOSS",
        "SMOKE_NONFINITE_GRADIENT",
        "SMOKE_TARGET_COUNT_MISMATCH",
        "SMOKE_LOSS_NORMALIZATION_MISMATCH",
        "SMOKE_GRADIENT_CLIPPING_FAILURE",
        "SMOKE_OPTIMIZER_SCHEDULER_FAILURE",
        "SMOKE_VALIDATION_MISMATCH",
        "SMOKE_CHECKPOINT_WRITE_FAILURE",
        "SMOKE_RESUME_MISMATCH",
        "SMOKE_ARTIFACT_COMMIT_INDETERMINATE",
    )
    for code in SMOKE_FAILURE_CODES:
        error = SmokeTrainingError(code)
        assert error.args == (code,)
        assert vars(error) == {"code": code}


@pytest.mark.parametrize(
    ("update", "expected"),
    (
        (1, 1e-6),
        (100, 1e-4),
        (101, 1e-4),
        (999, 2e-4 / 900),
        (1_000, 1e-4 / 900),
    ),
)
def test_explicit_learning_rate_boundaries(update: int, expected: float) -> None:
    assert approved_learning_rate(update) == expected
    state = learning_rate_state_after_update(update)
    assert state.last_step_learning_rate == expected
    assert state.protocol == LEARNING_RATE_PROTOCOL
    if update == 1_000:
        assert state.next_step_learning_rate == 0.0


@pytest.mark.parametrize("update", (0, True, 1_001, -1, 1.5))
def test_learning_rate_rejects_every_nonapproved_update(update: object) -> None:
    with pytest.raises(SmokeTrainingError, match=SMOKE_OPTIMIZER_SCHEDULER_FAILURE):
        approved_learning_rate(update)  # type: ignore[arg-type]


def test_dropout_derivation_is_exact_order_independent_and_domain_separated() -> None:
    first = {
        condition: derive_tiny_dropout_seed(condition, 751, 3)
        for condition in CONDITIONS
    }
    second = {
        condition: derive_tiny_dropout_seed(condition, 751, 3)
        for condition in reversed(CONDITIONS)
    }
    assert first == second
    assert len(set(first.values())) == 4
    assert derive_tiny_dropout_seed("EnglishMono", 751, 3) == int.from_bytes(
        hashlib.sha256(
            smoke_module.canonical_json_bytes(
                [
                    DROPOUT_PROTOCOL,
                    ["base_seed", DROPOUT_BASE_SEED],
                    ["canonical_condition", "EnglishMono"],
                    ["one_based_optimizer_update", 751],
                    ["zero_based_microbatch_position", 3],
                ]
            )
        ).digest()[:8],
        "big",
    )
    assert derive_tiny_dropout_seed("EnglishMono", 751, 3) != 11_729
    assert derive_tiny_dropout_seed("EnglishMono", 751, 3) != 21_729


def test_sanitized_training_view_is_immutable_and_has_no_custody_fields() -> None:
    source = _arrays(rows=2, lexical=40)
    view = create_synthetic_smoke_training_view_for_tests(source, test_updates=2)
    condition = view.conditions[0]
    assert type(view) is SanitizedTrainingView
    assert type(condition) is SanitizedConditionTrainingView
    assert type(condition.train_tensors) is SanitizedTensorArrays
    assert "ordered_train_identities" not in repr(condition)
    assert "input_ids" not in repr(condition.train_tensors)
    assert not condition.train_tensors.input_ids.flags.writeable
    source["EnglishMono"][0][0, 1] = 7_999
    assert condition.train_tensors.input_ids[0, 1] != 7_999
    with pytest.raises(ValueError):
        condition.train_tensors.input_ids.setflags(write=True)
    forbidden = {
        "raw_text",
        "source_text",
        "membership",
        "provenance",
        "pseudonym",
        "path",
        "filename",
        "key",
    }
    assert not forbidden & set(vars(type(condition)))


def test_factory_only_public_types_reject_direct_construction() -> None:
    for class_type in (
        CandidateApprovalEvidence,
        CheckpointEnvelope,
        SmokeLaunchManifest,
        SmokeExecutionAuthorization,
        RuntimeRunManifest,
        PrivacySafeTerminalResult,
        TinySmokeOptimizerSet,
        TinySmokeConditionRuntime,
    ):
        with pytest.raises(SmokeTrainingError):
            class_type()
    for class_type in (
        SanitizedTensorArrays,
        SanitizedConditionTrainingView,
        SanitizedTrainingView,
    ):
        with pytest.raises(PreparationError):
            class_type()
    with pytest.raises(SmokeArtifactError):
        ArtifactCommitResult()
    with pytest.raises(SmokeArtifactError):
        PrivateRunArtifactWriter()


def test_exact_synthetic_tracker_and_candidate_binding(tmp_path: Path) -> None:
    view = create_synthetic_smoke_training_view_for_tests(_arrays(), test_updates=1)
    path = _write_tracker(tmp_path / "tracker.md", view)
    evidence = load_synthetic_candidate_approval_for_tests(
        path,
        candidate_checksum=view.candidate_checksum_record_sha256,
        preparation_manifest=view.preparation_manifest_sha256,
        schedule_identity=view.schedule_plan_identity_sha256,
    )
    assert evidence.authority_kind == "synthetic_test_only"
    assert evidence.exact_unique_approval is True
    assert evidence.serialized_status == "candidate_unapproved"
    assert evidence.launch_manifest_approved is False
    assert evidence.tracker_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize(
    "mutation",
    ("missing", "changed", "duplicate", "ambiguous", "fabricated_hmac"),
)
def test_tracker_approval_missing_changed_duplicate_ambiguous_or_fabricated_rejected(
    tmp_path: Path,
    mutation: str,
) -> None:
    view = create_synthetic_smoke_training_view_for_tests(_arrays(), test_updates=1)
    sentence = _approval_sentence(view.candidate_checksum_record_sha256)
    text = _tracker_text(view)
    if mutation == "missing":
        text = text.replace(sentence, "approval absent")
    elif mutation == "changed":
        text = text.replace(view.candidate_checksum_record_sha256, "0" * 64)
    elif mutation == "duplicate":
        text += sentence + "\n"
    elif mutation == "ambiguous":
        text = text.replace(sentence, sentence + "\n" + sentence.replace("exact", "ambiguous"))
    else:
        text = text.replace(sentence, "HMAC approval=" + view.candidate_checksum_record_sha256)
    path = _write_tracker(tmp_path / f"{mutation}.md", view, text)
    with pytest.raises(SmokeTrainingError, match=SMOKE_APPROVAL_MISMATCH):
        load_synthetic_candidate_approval_for_tests(
            path,
            candidate_checksum=view.candidate_checksum_record_sha256,
            preparation_manifest=view.preparation_manifest_sha256,
            schedule_identity=view.schedule_plan_identity_sha256,
        )


def test_production_tracker_loader_rejects_caller_path_before_acceptance(tmp_path: Path) -> None:
    marker = tmp_path / "private-marker-tracker"
    marker.write_text("private-marker", encoding="utf-8")
    with pytest.raises(SmokeTrainingError) as caught:
        load_candidate_approval_evidence(marker)
    assert caught.value.args == (SMOKE_APPROVAL_MISMATCH,)
    assert "private-marker" not in repr(caught.value)


def test_launch_manifest_binds_every_approved_mechanics_field(tmp_path: Path) -> None:
    _, approval, launch, _, _, _ = _authority(tmp_path)
    assert launch.candidate_checksum_record_sha256 == approval.candidate_checksum_record_sha256
    assert launch.preparation_manifest_sha256 == approval.preparation_manifest_sha256
    assert launch.schedule_plan_identity_sha256 == approval.schedule_plan_identity_sha256
    assert launch.tiny_configuration_sha256 == NEU_TINY.configuration_sha256()
    assert launch.device == "cpu"
    assert launch.learning_rate_protocol == LEARNING_RATE_PROTOCOL
    assert "uniform_unique_parameters" in launch.optimizer_protocol
    assert launch.validation_points == VALIDATION_POINTS
    assert launch.resume_protocol == smoke_module.RESUME_PROTOCOL
    assert launch.output_policy == "private_0700_files_0600_no_overwrite_completion_last"
    assert launch.reporting_policy == "mechanics_only_private_non_scientific"


def _production_equivalent_authority(tmp_path: Path):
    view = create_synthetic_smoke_training_view_for_tests(
        _arrays(rows=1, lexical=126),
        test_updates=1_000,
        microbatch_size=1,
    )
    documents = synthetic_production_authority_documents_for_tests(
        view,
        executor_commit="a" * 40,
        executor_closure_digest="b" * 64,
    )
    for name, content in documents.items():
        path = tmp_path / name
        path.write_bytes(content)
        os.chmod(path, 0o600)
    paired = create_paired_initialization(NEU_TINY, TINY_SMOKE_SEED_PLANS[0])
    authorization = derive_synthetic_production_authorization_for_tests(
        tmp_path / "synthetic-production-tracker.json",
        tmp_path / "synthetic-production-launch.json",
        view,
        paired,
        executor_commit="a" * 40,
        executor_closure_digest="b" * 64,
    )
    return view, authorization


def _production_condition_runtime_material(tmp_path: Path):
    view = create_synthetic_smoke_training_view_for_tests(
        _arrays(rows=1, lexical=126),
        test_updates=1_000,
        microbatch_size=1,
    )
    documents = production_condition_runtime_authority_documents_for_tests(
        view,
        executor_commit="a" * 40,
        executor_closure_digest="b" * 64,
    )
    for name, content in documents.items():
        path = tmp_path / name
        path.write_bytes(content)
        os.chmod(path, 0o600)
    paired = create_paired_initialization(NEU_TINY, TINY_SMOKE_SEED_PLANS[0])
    return (
        view,
        paired,
        tmp_path / "production-runtime-admission-tracker.json",
        tmp_path / "production-runtime-admission-launch.json",
    )


def _production_condition_runtime_authority(tmp_path: Path):
    view, paired, tracker_path, launch_path = (
        _production_condition_runtime_material(tmp_path)
    )
    authorization = derive_production_condition_runtime_authorization_for_tests(
        tracker_path,
        launch_path,
        view,
        paired,
        executor_commit="a" * 40,
        executor_closure_digest="b" * 64,
    )
    return view, authorization


def test_factory_created_production_authority_reaches_condition_runtime(
    tmp_path: Path,
) -> None:
    view, authorization = _production_condition_runtime_authority(tmp_path)
    optimizers = create_tiny_smoke_optimizers(authorization)
    assert authorization.authority_kind == "production_tracker_and_launch"
    assert authorization.approval.serialized_status == "candidate_unapproved"
    assert authorization.launch_manifest.sanitized_view_sha256 == view.semantic_sha256
    admitted: list[str] = []
    for condition in CONDITIONS:
        runtime = begin_tiny_smoke_condition(authorization, optimizers, condition)
        assert type(runtime) is TinySmokeConditionRuntime
        assert runtime.condition == condition
        assert runtime.completed_update == 0
        assert runtime._authorization is authorization
        admitted.append(runtime.condition)
        del runtime
    assert tuple(admitted) == CONDITIONS


def test_approval_updated_tracker_identity_reaches_reviewed_update_path(
    tmp_path: Path,
) -> None:
    _, authorization = _production_condition_runtime_authority(tmp_path)
    tracker_bytes = authorization._tracker_path.read_bytes()
    actual_sha256 = hashlib.sha256(tracker_bytes).hexdigest()
    assert actual_sha256 != APPROVED_TRACKER_SHA256
    assert len(tracker_bytes) != APPROVED_TRACKER_SIZE
    assert authorization.approval.tracker_sha256 == actual_sha256
    assert authorization.approval.tracker_size == len(tracker_bytes)
    assert authorization.launch_manifest.tracker_baseline_sha256 == (
        APPROVED_TRACKER_SHA256
    )
    assert authorization.launch_manifest.tracker_baseline_size == (
        APPROVED_TRACKER_SIZE
    )
    optimizers = create_tiny_smoke_optimizers(authorization)
    runtime = begin_tiny_smoke_condition(
        authorization,
        optimizers,
        "EnglishMono",
    )
    result = execute_next_optimizer_update(runtime)
    assert result.completed_update == 1
    assert runtime.completed_update == 1


def test_obsolete_baseline_identity_cannot_be_rehashed_into_updated_authority(
    tmp_path: Path,
) -> None:
    _, authorization = _production_condition_runtime_authority(tmp_path)
    optimizers = create_tiny_smoke_optimizers(authorization)
    object.__setattr__(
        authorization.approval,
        "tracker_sha256",
        APPROVED_TRACKER_SHA256,
    )
    object.__setattr__(
        authorization.approval,
        "tracker_size",
        APPROVED_TRACKER_SIZE,
    )
    locally_rehashed = smoke_module._authorization_semantic_sha256(
        authorization.authority_kind,
        authorization.approval,
        authorization.launch_manifest,
        authorization.initialization_manifest,
        authorization.training_view_sha256,
        authorization.condition_digests,
        authorization.tensor_array_digests,
        authorization.schedule_bindings,
    )
    object.__setattr__(authorization, "authorization_sha256", locally_rehashed)
    object.__setattr__(optimizers, "_authorization_sha256", locally_rehashed)
    with pytest.raises(SmokeTrainingError, match=SMOKE_APPROVAL_MISMATCH):
        begin_tiny_smoke_condition(
            authorization,
            optimizers,
            "EnglishMono",
        )


def test_production_runtime_authority_domains_remain_noninterchangeable(
    tmp_path: Path,
) -> None:
    _, authorization = _production_condition_runtime_authority(tmp_path)
    output = (tmp_path / "must-not-exist").resolve()
    with pytest.raises(SmokeTrainingError, match=SMOKE_APPROVAL_MISMATCH):
        execute_synthetic_production_equivalent_for_tests(authorization, output)
    with pytest.raises(SmokeTrainingError, match=SMOKE_APPROVAL_MISMATCH):
        execute_bounded_tiny_smoke(authorization)
    assert not output.exists()

    synthetic_root = tmp_path / "synthetic"
    synthetic_root.mkdir()
    *_, synthetic_authorization, synthetic_optimizers, _ = _runtime(
        synthetic_root,
        test_updates=1,
    )
    object.__setattr__(
        synthetic_authorization,
        "authority_kind",
        "production_tracker_and_launch",
    )
    with pytest.raises(SmokeTrainingError, match=SMOKE_APPROVAL_MISMATCH):
        begin_tiny_smoke_condition(
            synthetic_authorization,
            synthetic_optimizers,
            "EnglishMono",
        )


@pytest.mark.parametrize(
    "tamper",
    (
        "wrong_kind",
        "wrong_condition",
        "mismatched_lineage",
        "stale_launch",
        "locally_rehashed",
        "fabricated",
    ),
)
def test_production_condition_runtime_authority_tampering_fails_closed(
    tmp_path: Path,
    tamper: str,
) -> None:
    _, authorization = _production_condition_runtime_authority(tmp_path)
    optimizers = create_tiny_smoke_optimizers(authorization)
    condition = "EnglishMono"
    candidate = authorization
    if tamper == "wrong_kind":
        object.__setattr__(candidate, "authority_kind", "caller_claimed_production")
    elif tamper == "wrong_condition":
        condition = "EnglishMono-substituted"
    elif tamper == "mismatched_lineage":
        object.__setattr__(
            candidate.launch_manifest,
            "preparation_runner_digest",
            "f" * 64,
        )
    elif tamper == "stale_launch":
        path = tmp_path / "production-runtime-admission-launch.json"
        content = path.read_bytes()
        path.write_bytes(content[:-1] + b" ")
        os.chmod(path, 0o600)
    elif tamper == "locally_rehashed":
        object.__setattr__(candidate, "training_view_sha256", "f" * 64)
        object.__setattr__(
            candidate,
            "authorization_sha256",
            smoke_module._authorization_semantic_sha256(
                candidate.authority_kind,
                candidate.approval,
                candidate.launch_manifest,
                candidate.initialization_manifest,
                candidate.training_view_sha256,
                candidate.condition_digests,
                candidate.tensor_array_digests,
                candidate.schedule_bindings,
            ),
        )
        object.__setattr__(optimizers, "_authorization_sha256", candidate.authorization_sha256)
    else:
        candidate = object.__new__(SmokeExecutionAuthorization)
    with pytest.raises(SmokeTrainingError, match=SMOKE_APPROVAL_MISMATCH):
        begin_tiny_smoke_condition(candidate, optimizers, condition)


def _synthetic_executor_repository(root: Path) -> Path:
    repository = (root / "synthetic-executor-repository").resolve()
    (repository / ".git" / "refs" / "heads").mkdir(parents=True)
    (repository / ".git" / "HEAD").write_text(
        "ref: refs/heads/main\n",
        encoding="ascii",
    )
    (repository / ".git" / "refs" / "heads" / "main").write_text(
        "1" * 40 + "\n",
        encoding="ascii",
    )
    for index, relative_name in enumerate(EXECUTOR_CLOSURE_FILES):
        path = repository / relative_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"synthetic-reviewed-closure-{index}\n".encode("ascii"))
    return repository


def _future_authority_material(
    tmp_path: Path,
    *,
    view: SanitizedTrainingView | None = None,
    hook=None,
    construct: bool = True,
):
    view = view or create_synthetic_smoke_training_view_for_tests(
        _arrays(rows=1, lexical=126),
        test_updates=1_000,
        microbatch_size=1,
    )
    repository = _synthetic_executor_repository(tmp_path)
    output_parent = (tmp_path / "synthetic-private-output").resolve()
    documents = synthetic_future_production_authority_documents_for_tests(
        view,
        repository,
        output_parent,
    )
    tracker_path = (tmp_path / "synthetic-future-tracker.md").resolve()
    launch_path = (tmp_path / "synthetic-future-launch.json").resolve()
    tracker_path.write_bytes(documents[tracker_path.name])
    launch_path.write_bytes(documents[launch_path.name])
    os.chmod(tracker_path, 0o600)
    os.chmod(launch_path, 0o600)
    candidate_root = (tmp_path / "synthetic-candidate").resolve()
    candidate_root.mkdir(mode=0o700)
    os.chmod(candidate_root, 0o700)
    key_path = (tmp_path / "synthetic-reconciliation.key").resolve()
    key_path.write_bytes(b"synthetic-boundary-key-material!")
    assert key_path.stat().st_size == 32
    os.chmod(key_path, 0o600)
    authorization = None
    if construct:
        authorization = construct_synthetic_future_production_authorization_for_tests(
            repository,
            tracker_path,
            launch_path,
            candidate_root,
            key_path,
            output_parent,
            view,
            _test_hook=hook,
        )
    return (
        view,
        authorization,
        repository,
        tracker_path,
        launch_path,
        candidate_root,
        key_path,
        output_parent,
    )


def _rewrite_future_launch(material, field: str, value: object) -> None:
    tracker_path = material[3]
    launch_path = material[4]
    previous = launch_path.read_bytes()
    payload = json.loads(previous)
    payload[field] = value
    changed = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    launch_path.write_bytes(changed)
    os.chmod(launch_path, 0o600)
    tracker = tracker_path.read_text(encoding="utf-8")
    tracker_path.write_text(
        tracker.replace(
            hashlib.sha256(previous).hexdigest(),
            hashlib.sha256(changed).hexdigest(),
            1,
        ),
        encoding="utf-8",
    )
    os.chmod(tracker_path, 0o600)


def _rewrite_tracker_launch_approval(
    tracker_path: Path,
    *,
    field: str | None = None,
    value: object = None,
    decision: str | None = None,
    duplicate: bool = False,
    malformed: bool = False,
) -> None:
    text = tracker_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    indexes = [
        index
        for index, line in enumerate(lines)
        if line.startswith(smoke_module.TRACKER_LAUNCH_AUTHORITY_PREFIX)
    ]
    assert len(indexes) == 1
    index = indexes[0]
    encoded = lines[index].removeprefix(
        smoke_module.TRACKER_LAUNCH_AUTHORITY_PREFIX
    )
    payload = json.loads(encoded)
    if field is not None:
        payload[field] = value
    if decision is not None:
        payload["decision"] = decision
    changed = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    if malformed:
        changed = changed[:-1]
    lines[index] = smoke_module.TRACKER_LAUNCH_AUTHORITY_PREFIX + changed
    if duplicate:
        lines.insert(index + 1, lines[index])
    tracker_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(tracker_path, 0o600)


def _construct_future_material(material, hook=None):
    return construct_synthetic_future_production_authorization_for_tests(
        material[2],
        material[3],
        material[4],
        material[5],
        material[6],
        material[7],
        material[0],
        _test_hook=hook,
    )


def test_production_equivalent_authority_is_external_and_test_only(
    tmp_path: Path,
) -> None:
    ordinary_root = tmp_path / "ordinary"
    ordinary_root.mkdir()
    *_, ordinary_authorization, _ = _authority(ordinary_root)
    output = (tmp_path / "must-not-exist").resolve()
    with pytest.raises(SmokeTrainingError, match=SMOKE_APPROVAL_MISMATCH):
        execute_synthetic_production_equivalent_for_tests(
            ordinary_authorization,
            output,
        )
    assert not output.exists()

    production_root = tmp_path / "production"
    production_root.mkdir()
    view, authorization = _production_equivalent_authority(production_root)
    assert authorization.authority_kind == "synthetic_production_equivalent"
    assert authorization.approval.launch_manifest_approved is True
    assert authorization.launch_manifest.sanitized_view_sha256 == view.semantic_sha256
    assert authorization.launch_manifest.optimizer_updates_per_condition == 1_000
    assert authorization.launch_manifest.condition_order == CONDITIONS
    assert authorization.launch_manifest.checkpoint_updates == (0, 250, 500, 750, 1_000)


def test_future_production_authority_uses_closed_ordered_boundary(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    material = _future_authority_material(tmp_path, hook=events.append)
    authorization = material[1]
    assert type(authorization) is SmokeExecutionAuthorization
    assert authorization.authority_kind == "synthetic_production_equivalent"
    assert authorization.approval.serialized_status == "candidate_unapproved"
    assert authorization.approval.launch_manifest_approved is True
    assert authorization.launch_manifest.condition_order == CONDITIONS
    assert authorization.launch_manifest.optimizer_updates_per_condition == 1_000
    assert events == [
        "runtime_and_executor_verified",
        "tracker_verified",
        "launch_verified",
        "runtime_output_and_candidate_custody_verified",
        "candidate_loaded",
        "sanitized_view_derived",
        "production_authority_constructed",
    ]
    assert not material[7].exists()


def test_current_production_factory_fails_before_external_access_or_output() -> None:
    with pytest.raises(SmokeTrainingError, match=SMOKE_APPROVAL_MISMATCH):
        construct_production_smoke_execution_authorization()


@pytest.mark.parametrize("missing", ("tracker", "launch"))
def test_missing_future_authority_fails_before_candidate_load_and_output(
    tmp_path: Path,
    missing: str,
) -> None:
    material = _future_authority_material(tmp_path, construct=False)
    missing_path = material[3] if missing == "tracker" else material[4]
    missing_path.unlink()
    events: list[str] = []
    with pytest.raises(SmokeTrainingError, match=SMOKE_APPROVAL_MISMATCH):
        _construct_future_material(material, events.append)
    assert "candidate_loaded" not in events
    assert not material[7].exists()


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("candidate_checksum_record_sha256", "f" * 64),
        ("preparation_runner_digest", "f" * 64),
        ("executor_commit", "2" * 40),
        ("executor_closure_digest", "f" * 64),
        ("runtime_policy_sha256", "f" * 64),
        ("tiny_configuration_sha256", "f" * 64),
        ("seed_plan_sha256", "f" * 64),
        ("device", "mps"),
        ("condition_order", list(reversed(CONDITIONS))),
        ("optimizer_updates_per_condition", 999),
        ("learning_rate_protocol", "caller-selected-lr"),
        ("optimizer_protocol", "caller-selected-optimizer"),
        ("validation_points", [100]),
        ("checkpoint_updates", [0]),
        ("resume_protocol", "caller-selected-resume"),
        ("output_policy", "caller-selected-output"),
        ("output_root_identity_sha256", "f" * 64),
        ("reporting_policy", "caller-selected-reporting"),
    ),
)
def test_future_launch_policy_tampering_fails_before_candidate_load(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    material = _future_authority_material(tmp_path, construct=False)
    _rewrite_future_launch(material, field, value)
    events: list[str] = []
    with pytest.raises(SmokeTrainingError, match=SMOKE_APPROVAL_MISMATCH):
        _construct_future_material(material, events.append)
    assert "candidate_loaded" not in events
    assert not material[7].exists()


@pytest.mark.parametrize("ambiguity", ("duplicate_candidate", "duplicate_launch"))
def test_future_tracker_approval_ambiguity_fails_before_candidate_load(
    tmp_path: Path,
    ambiguity: str,
) -> None:
    material = _future_authority_material(tmp_path, construct=False)
    tracker_path = material[3]
    text = tracker_path.read_text(encoding="utf-8")
    line = next(
        item
        for item in text.splitlines()
        if (
            "candidate checksum-record" in item
            if ambiguity == "duplicate_candidate"
            else item.startswith(smoke_module.TRACKER_LAUNCH_AUTHORITY_PREFIX)
        )
    )
    tracker_path.write_text(text + line + "\n", encoding="utf-8")
    os.chmod(tracker_path, 0o600)
    events: list[str] = []
    with pytest.raises(SmokeTrainingError, match=SMOKE_APPROVAL_MISMATCH):
        _construct_future_material(material, events.append)
    assert events == ["runtime_and_executor_verified"]
    assert not material[7].exists()


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("baseline_tracker_sha256", "f" * 64),
        ("baseline_tracker_size", APPROVED_TRACKER_SIZE + 1),
        ("baseline_tracker_version", "5.5"),
        ("baseline_tracker_canonical_date", "August 2, 2026"),
        ("launch_manifest_sha256", "f" * 64),
        ("candidate_checksum_record_sha256", "f" * 64),
        ("preparation_manifest_sha256", "f" * 64),
        ("schedule_plan_identity_sha256", "f" * 64),
        ("preparation_runner_digest", "f" * 64),
        ("executor_commit", "2" * 40),
        ("executor_closure_digest", "f" * 64),
    ),
)
def test_approval_updated_tracker_binding_tampering_fails_closed(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    material = _future_authority_material(tmp_path, construct=False)
    _rewrite_tracker_launch_approval(material[3], field=field, value=value)
    events: list[str] = []
    with pytest.raises(SmokeTrainingError, match=SMOKE_APPROVAL_MISMATCH):
        _construct_future_material(material, events.append)
    assert events == ["runtime_and_executor_verified"] + (
        ["tracker_verified"] if field == "launch_manifest_sha256" else []
    )
    assert not material[7].exists()


@pytest.mark.parametrize(
    "failure",
    (
        "duplicate",
        "conflicting",
        "rejected",
        "revoked",
        "partial",
        "malformed",
        "unrelated",
    ),
)
def test_approval_updated_tracker_record_shape_fails_closed(
    tmp_path: Path,
    failure: str,
) -> None:
    material = _future_authority_material(tmp_path, construct=False)
    tracker_path = material[3]
    if failure == "duplicate":
        _rewrite_tracker_launch_approval(tracker_path, duplicate=True)
    elif failure == "conflicting":
        _rewrite_tracker_launch_approval(tracker_path, duplicate=True)
        text = tracker_path.read_text(encoding="utf-8")
        record = smoke_module.TRACKER_LAUNCH_AUTHORITY_PREFIX
        first = text.index(record)
        second = text.index(record, first + len(record))
        tracker_path.write_text(
            text[:second]
            + text[second:].replace('"decision":"approved"', '"decision":"rejected"', 1),
            encoding="utf-8",
        )
        os.chmod(tracker_path, 0o600)
    elif failure in {"rejected", "revoked"}:
        _rewrite_tracker_launch_approval(tracker_path, decision=failure)
    elif failure == "partial":
        text = tracker_path.read_text(encoding="utf-8")
        record_line = next(
            line
            for line in text.splitlines()
            if line.startswith(smoke_module.TRACKER_LAUNCH_AUTHORITY_PREFIX)
        )
        payload = json.loads(
            record_line.removeprefix(smoke_module.TRACKER_LAUNCH_AUTHORITY_PREFIX)
        )
        del payload["resume_protocol"]
        replacement = smoke_module.TRACKER_LAUNCH_AUTHORITY_PREFIX + json.dumps(
            payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        tracker_path.write_text(
            text.replace(record_line, replacement, 1),
            encoding="utf-8",
        )
        os.chmod(tracker_path, 0o600)
    elif failure == "malformed":
        _rewrite_tracker_launch_approval(tracker_path, malformed=True)
    else:
        _rewrite_tracker_launch_approval(
            tracker_path,
            field="unrelated_approval",
            value=True,
        )
    events: list[str] = []
    with pytest.raises(SmokeTrainingError, match=SMOKE_APPROVAL_MISMATCH):
        _construct_future_material(material, events.append)
    assert events == ["runtime_and_executor_verified"]
    assert not material[7].exists()


def test_launch_manifest_cannot_bind_its_post_approval_tracker_identity(
    tmp_path: Path,
) -> None:
    material = _future_authority_material(tmp_path, construct=False)
    launch_path = material[4]
    payload = json.loads(launch_path.read_bytes())
    payload["approval_updated_tracker_sha256"] = "f" * 64
    changed = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    launch_path.write_bytes(changed)
    os.chmod(launch_path, 0o600)
    _rewrite_tracker_launch_approval(
        material[3],
        field="launch_manifest_sha256",
        value=hashlib.sha256(changed).hexdigest(),
    )
    events: list[str] = []
    with pytest.raises(SmokeTrainingError, match=SMOKE_APPROVAL_MISMATCH):
        _construct_future_material(material, events.append)
    assert events == ["runtime_and_executor_verified", "tracker_verified"]
    assert not material[7].exists()


def test_production_entry_rejects_future_synthetic_authority(tmp_path: Path) -> None:
    authorization = _future_authority_material(tmp_path)[1]
    with pytest.raises(SmokeTrainingError, match=SMOKE_APPROVAL_MISMATCH):
        execute_bounded_tiny_smoke(authorization)


def test_production_equivalent_authority_rechecks_external_launch_bytes(
    tmp_path: Path,
) -> None:
    view, authorization = _production_equivalent_authority(tmp_path)
    launch_path = tmp_path / "synthetic-production-launch.json"
    changed = launch_path.read_bytes().replace(b"b" * 64, b"c" * 64, 1)
    assert len(changed) == launch_path.stat().st_size
    launch_path.write_bytes(changed)
    os.chmod(launch_path, 0o600)
    with pytest.raises(SmokeTrainingError, match=SMOKE_APPROVAL_MISMATCH):
        create_tiny_smoke_optimizers(authorization)
    assert view.authority_kind == "synthetic_test_only"


def test_production_equivalent_schedule_cannot_be_shortened() -> None:
    shortened = create_synthetic_smoke_training_view_for_tests(
        _arrays(rows=1, lexical=126),
        test_updates=999,
        microbatch_size=1,
    )
    with pytest.raises(SmokeTrainingError, match=SMOKE_APPROVAL_MISMATCH):
        synthetic_production_authority_documents_for_tests(
            shortened,
            executor_commit="a" * 40,
            executor_closure_digest="b" * 64,
        )


def test_complete_production_shaped_four_condition_orchestration(
    tmp_path: Path,
) -> None:
    material = _future_authority_material(tmp_path)
    authorization = material[1]
    output_parent = material[7]
    assert not output_parent.exists()
    result = execute_synthetic_production_equivalent_for_tests(
        authorization,
        output_parent,
    )
    assert type(result) is PrivacySafeTerminalResult
    assert result.mechanics_passed is True
    assert result.completed_conditions == CONDITIONS
    assert result.completed_updates_per_condition == 1_000
    assert result.cpu_only is True
    runs = tuple(output_parent.iterdir())
    assert len(runs) == 1
    run_root = runs[0]
    assert (run_root / "RUN_COMPLETE.json").is_file()
    assert json.loads((run_root / "RUN_COMPLETE.json").read_bytes())[
        "terminal_classification"
    ] == "mechanics_passed"
    english_result = json.loads(
        (
            run_root
            / "EnglishMono"
            / "cpu"
            / "condition-complete"
            / "condition_result.json"
        ).read_bytes()
    )
    assert english_result["fresh_process_resume"] == {
        "checkpoint_update": 750,
        "first_replay_update": 751,
        "fresh_interpreter": True,
        "last_replay_update": 1_000,
        "protocol": smoke_module.RESUME_WORKER_PROTOCOL,
        "replay_result_sha256": english_result["fresh_process_resume"][
            "replay_result_sha256"
        ],
        "replay_update_count": 250,
        "validation_updates": [800, 900, 1_000],
        "worker_pid_differed": True,
    }
    assert not tuple(run_root.rglob("resume-replay-*"))
    for condition in CONDITIONS:
        cpu_root = run_root / condition / "cpu"
        assert tuple(
            sorted(
                int(path.name.removeprefix("checkpoint-"))
                for path in cpu_root.glob("checkpoint-*")
            )
        ) == (0, 250, 500, 750, 1_000)
        assert (cpu_root / "condition-complete" / "CONDITION_COMPLETE.json").is_file()


def test_condition_failure_prevents_whole_run_terminal_result(tmp_path: Path) -> None:
    authority_root = tmp_path / "authority"
    authority_root.mkdir()
    _, authorization = _production_equivalent_authority(authority_root)

    def fail_forward(*args, **kwargs):
        del args, kwargs
        raise RuntimeError("synthetic injected failure")

    authorization._models["EnglishMono"].forward = fail_forward  # type: ignore[method-assign]
    output_parent = (tmp_path / "synthetic-private-output").resolve()
    with pytest.raises(SmokeTrainingError):
        execute_synthetic_production_equivalent_for_tests(
            authorization,
            output_parent,
        )
    assert output_parent.is_dir()
    assert not tuple(output_parent.glob("*/RUN_COMPLETE.json"))


@pytest.mark.parametrize("material", ("train", "validation", "microbatch", "cross"))
def test_rehashed_live_view_and_cross_condition_substitution_fail_closed(
    tmp_path: Path,
    material: str,
) -> None:
    view, _, _, _, authorization, optimizers, runtime = _runtime(
        tmp_path,
        test_updates=100,
    )
    condition = view.conditions[0]
    if material == "validation":
        prime_synthetic_runtime_to_update_for_tests(runtime, 100)
    if material in {"train", "validation"}:
        attribute = "train_tensors" if material == "train" else "validation_tensors"
        arrays = getattr(condition, attribute)
        changed = np.array(arrays.input_ids, copy=True)
        changed[0, 1] = 7_998
        replacement = smoke_module._derive_sanitized_tensor_arrays(
            changed,
            arrays.attention_mask,
            arrays.token_type_ids,
            arrays.labels,
        )
        object.__setattr__(condition, attribute, replacement)
        digest_field = (
            "train_tensor_sha256" if material == "train" else "validation_tensor_sha256"
        )
        object.__setattr__(
            condition,
            digest_field,
            smoke_module._sanitized_tensor_digest_contract(replacement),
        )
    elif material == "microbatch":
        schedule = condition.schedule
        first_update = schedule.updates[0]
        first_microbatch = first_update.microbatches[0]
        changed_microbatch = replace(
            first_microbatch,
            selected_targets_by_seed=(("tiny_smoke_1", 999),),
        )
        changed_update = replace(
            first_update,
            microbatches=(changed_microbatch, *first_update.microbatches[1:]),
        )
        object.__setattr__(
            condition,
            "schedule",
            replace(schedule, updates=(changed_update, *schedule.updates[1:])),
        )
        object.__setattr__(
            condition,
            "schedule_evidence_sha256",
            smoke_module._schedule_evidence_digest_contract(condition.schedule),
        )
    else:
        runtime._condition_view = view.conditions[1]
    if material != "cross":
        object.__setattr__(
            condition,
            "semantic_sha256",
            smoke_module.sanitized_condition_view_digest(condition),
        )
        object.__setattr__(
            view,
            "condition_digests",
            tuple((item.condition, item.semantic_sha256) for item in view.conditions),
        )
        object.__setattr__(
            view,
            "semantic_sha256",
            smoke_module.sanitized_training_view_digest(view),
        )
    expected_code = (
        SMOKE_VALIDATION_MISMATCH
        if material == "validation"
        else SMOKE_DATA_SCHEDULE_MISMATCH
    )
    operation = (
        validate_tiny_smoke_condition
        if material == "validation"
        else execute_next_optimizer_update
    )
    with pytest.raises(SmokeTrainingError, match=expected_code):
        operation(runtime)


@pytest.mark.parametrize(
    ("target", "field", "value"),
    (
        ("approval", "candidate_checksum_record_sha256", "0" * 64),
        ("approval", "schedule_plan_identity_sha256", "0" * 64),
        ("launch", "executor_closure_digest", "0" * 64),
        ("launch", "device", "mps"),
        ("launch", "seed_plan_sha256", "0" * 64),
        ("view", "semantic_sha256", "0" * 64),
    ),
)
def test_candidate_schedule_seed_device_and_executor_tampering_fails_closed(
    tmp_path: Path,
    target: str,
    field: str,
    value: object,
) -> None:
    view = create_synthetic_smoke_training_view_for_tests(_arrays(), test_updates=1)
    tracker = _write_tracker(tmp_path / "tracker.md", view)
    approval = load_synthetic_candidate_approval_for_tests(
        tracker,
        candidate_checksum=view.candidate_checksum_record_sha256,
        preparation_manifest=view.preparation_manifest_sha256,
        schedule_identity=view.schedule_plan_identity_sha256,
    )
    launch = derive_synthetic_smoke_launch_manifest_for_tests(
        approval,
        executor_commit="a" * 40,
        executor_closure_digest="b" * 64,
    )
    object.__setattr__({"approval": approval, "launch": launch, "view": view}[target], field, value)
    paired = create_paired_initialization(NEU_TINY, TINY_SMOKE_SEED_PLANS[0])
    with pytest.raises(SmokeTrainingError, match=SMOKE_APPROVAL_MISMATCH):
        derive_synthetic_smoke_execution_authorization_for_tests(
            approval,
            launch,
            view,
            paired,
        )


def test_exact_tiny_pair_ties_storage_independence_and_parameter_count(tmp_path: Path) -> None:
    _, _, _, paired, authorization, optimizers = _authority(tmp_path)
    assert paired.manifest.trainable_parameter_count == 1_462_080
    assert tuple(paired.models) == CONDITIONS
    assert authorization.device == "cpu"
    parameter_storages: set[int] = set()
    buffer_storages: set[int] = set()
    for model in paired.models.values():
        assert model.get_input_embeddings().weight is model.get_output_embeddings().weight
        assert tied_parameter_groups(model) == paired.manifest.tied_parameter_groups
        local_parameters = {
            parameter.untyped_storage().data_ptr() for parameter in model.parameters()
        }
        local_buffers = {buffer.untyped_storage().data_ptr() for buffer in model.buffers()}
        assert not parameter_storages & local_parameters
        assert not buffer_storages & local_buffers
        parameter_storages.update(local_parameters)
        buffer_storages.update(local_buffers)
    assert len({id(value) for value in optimizers._optimizers.values()}) == 4
    assert len({id(value.state) for value in optimizers._optimizers.values()}) == 4


def test_uniform_adamw_grouping_and_independent_state(tmp_path: Path) -> None:
    _, _, _, paired, _, optimizers = _authority(tmp_path)
    for condition in CONDITIONS:
        optimizer = optimizers._optimizers[condition]
        group = optimizer.param_groups[0]
        expected = tuple(parameter for parameter in paired.models[condition].parameters())
        assert len(optimizer.param_groups) == 1
        assert tuple(id(parameter) for parameter in group["params"]) == tuple(
            id(parameter) for parameter in expected
        )
        assert len({id(parameter) for parameter in group["params"]}) == len(expected)
        assert group["betas"] == (0.9, 0.999)
        assert group["eps"] == 1e-8
        assert group["weight_decay"] == 0.01
        assert group["foreach"] is False
        assert group["fused"] is False
        assert optimizer.state == {}


def test_actual_tensor_update_normalizes_then_clips_and_steps_once(tmp_path: Path) -> None:
    *_, runtime = _runtime(tmp_path, rows=2, lexical=64, microbatch_size=1)
    optimizer = runtime._optimizer
    before = tuple(parameter.detach().clone() for parameter in runtime._model.parameters())
    result = execute_next_optimizer_update(runtime)
    assert result.completed_update == 1
    assert result.selected_target_count == runtime._target_count_history[0]
    assert result.normalized_loss == runtime._loss_history[0]
    assert result.learning_rate_state.last_step_learning_rate == 1e-6
    assert math_is_finite(result.normalized_loss)
    assert math_is_finite(result.unclipped_gradient_norm)
    assert result.unclipped_gradient_norm > 1.0
    assert runtime.at_update_boundary is True
    assert all(parameter.grad is None for parameter in runtime._model.parameters())
    steps = {
        int(state["step"].item())
        for state in optimizer.state.values()
        if "step" in state
    }
    assert steps == {1}
    assert any(
        not torch.equal(previous, current)
        for previous, current in zip(before, runtime._model.parameters(), strict=True)
    )


def math_is_finite(value: float) -> bool:
    return not (np.isnan(value) or np.isinf(value))


def test_actual_update_is_invariant_to_approved_microbatch_partition(
    tmp_path: Path,
) -> None:
    arrays = _arrays(rows=2, lexical=64)
    first_view = create_synthetic_smoke_training_view_for_tests(
        arrays,
        test_updates=1,
        microbatch_size=1,
    )
    second_view = create_synthetic_smoke_training_view_for_tests(
        arrays,
        test_updates=1,
        microbatch_size=2,
    )
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    *_, first_runtime = _runtime(first_root, view=first_view)
    *_, second_runtime = _runtime(second_root, view=second_view)
    for runtime in (first_runtime, second_runtime):
        for module in runtime._model.modules():
            if type(module) is torch.nn.Dropout:
                module.p = 0.0
    first = execute_next_optimizer_update(first_runtime)
    second = execute_next_optimizer_update(second_runtime)
    assert first.selected_target_count == second.selected_target_count
    assert np.isclose(first.normalized_loss, second.normalized_loss, rtol=0.0, atol=2e-6)
    assert np.isclose(
        first.unclipped_gradient_norm,
        second.unclipped_gradient_norm,
        rtol=0.0,
        atol=2e-6,
    )
    for name, tensor in first_runtime._model.state_dict().items():
        assert torch.allclose(
            tensor,
            second_runtime._model.state_dict()[name],
            rtol=0.0,
            atol=2e-6,
        )


def test_masking_visits_counts_special_exclusion_and_80_10_10(tmp_path: Path) -> None:
    view = create_synthetic_smoke_training_view_for_tests(
        _arrays(rows=4, lexical=64),
        test_updates=100,
        microbatch_size=4,
    )
    condition = view.conditions[0]
    kinds: list[str] = []
    selected_total = 0
    for appearance in condition.schedule.appearances:
        sequence = smoke_module._synthetic_sequence(
            condition.condition,
            condition.train_tensors,
            condition.ordered_train_identities,
            appearance.sequence_index,
            split="train",
        )
        masked = mask_packed_sequence(
            sequence,
            seed=11_729,
            mode="train",
            visit=appearance.visit,
        )
        selected_total += len(masked.selected_positions)
        kinds.extend(masked.replacement_kinds)
        for position in masked.selected_positions:
            assert sequence.attention_mask[position] == 1
            assert sequence.input_ids[position] not in {0, 1, 2, 3, 4}
    evidence_total = sum(
        dict(update.selected_targets_by_seed)["tiny_smoke_1"]
        for update in condition.schedule.updates
    )
    assert selected_total == evidence_total
    assert {appearance.visit for appearance in condition.schedule.appearances} == set(range(100))
    fractions = {kind: kinds.count(kind) / len(kinds) for kind in set(kinds)}
    assert abs(fractions["mask"] - 0.8) < 0.04
    assert abs(fractions["random"] - 0.1) < 0.03
    assert abs(fractions["unchanged"] - 0.1) < 0.03


def test_zero_target_microbatch_is_accepted_when_complete_update_has_targets(
    tmp_path: Path,
) -> None:
    view = create_synthetic_smoke_training_view_for_tests(
        _arrays(rows=8, lexical=3),
        test_updates=1,
        microbatch_size=1,
    )
    english = view.conditions[0]
    counts = [
        dict(microbatch.selected_targets_by_seed)["tiny_smoke_1"]
        for microbatch in english.schedule.updates[0].microbatches
    ]
    assert 0 in counts and sum(counts) > 0
    *_, runtime = _runtime(tmp_path, view=view)
    result = execute_next_optimizer_update(runtime)
    assert result.selected_target_count == sum(counts)


def test_complete_zero_target_update_is_rejected() -> None:
    with pytest.raises(SmokeTrainingError, match=SMOKE_TARGET_COUNT_MISMATCH):
        create_synthetic_smoke_training_view_for_tests(
            _arrays(rows=1, lexical=1),
            test_updates=1,
            microbatch_size=1,
        )


def test_nonfinite_loss_is_rejected_without_optimizer_step(tmp_path: Path) -> None:
    *_, runtime = _runtime(tmp_path, rows=2, lexical=48)
    with torch.no_grad():
        next(runtime._model.parameters()).fill_(float("inf"))
    with pytest.raises(SmokeTrainingError, match=SMOKE_NONFINITE_LOSS):
        execute_next_optimizer_update(runtime)
    assert runtime.completed_update == 0
    assert runtime.at_update_boundary is False
    assert runtime._optimizer.state == {}


def test_nonfinite_gradient_is_rejected_before_clipping_or_step(tmp_path: Path) -> None:
    *_, runtime = _runtime(tmp_path, rows=2, lexical=48)
    parameter = next(runtime._model.parameters())
    handle = parameter.register_hook(lambda gradient: torch.full_like(gradient, float("inf")))
    try:
        with pytest.raises(SmokeTrainingError, match=SMOKE_NONFINITE_GRADIENT):
            execute_next_optimizer_update(runtime)
    finally:
        handle.remove()
    assert runtime.completed_update == 0
    assert runtime._optimizer.state == {}


@pytest.mark.parametrize(
    ("option", "changed"),
    (
        ("lr", 0.5),
        ("betas", (0.8, 0.999)),
        ("eps", 1e-7),
        ("weight_decay", 0.0),
        ("maximize", True),
        ("amsgrad", True),
        ("capturable", True),
        ("differentiable", True),
        ("foreach", True),
        ("fused", True),
    ),
)
def test_every_mutable_adamw_option_fails_closed_before_forward(
    tmp_path: Path,
    option: str,
    changed: object,
) -> None:
    *_, runtime = _runtime(tmp_path)
    runtime._optimizer.param_groups[0][option] = changed
    with pytest.raises(SmokeTrainingError, match=SMOKE_OPTIMIZER_SCHEDULER_FAILURE):
        execute_next_optimizer_update(runtime)
    assert runtime.completed_update == 0


def test_adamw_parameter_order_and_step_callable_tampering_fail_closed(
    tmp_path: Path,
) -> None:
    first_root = tmp_path / "order"
    first_root.mkdir()
    *_, order_runtime = _runtime(first_root)
    order_runtime._optimizer.param_groups[0]["params"].reverse()
    with pytest.raises(SmokeTrainingError, match=SMOKE_OPTIMIZER_SCHEDULER_FAILURE):
        execute_next_optimizer_update(order_runtime)

    callable_root = tmp_path / "callable"
    callable_root.mkdir()
    *_, callable_runtime = _runtime(callable_root)
    callable_runtime._optimizer.step = lambda: None  # type: ignore[method-assign]
    with pytest.raises(SmokeTrainingError, match=SMOKE_OPTIMIZER_SCHEDULER_FAILURE):
        execute_next_optimizer_update(callable_runtime)


def test_stale_gradient_is_rejected_before_zero_grad(tmp_path: Path) -> None:
    *_, runtime = _runtime(tmp_path)
    parameter = next(runtime._model.parameters())
    parameter.grad = torch.ones_like(parameter)
    with pytest.raises(SmokeTrainingError, match=SMOKE_NONFINITE_GRADIENT):
        execute_next_optimizer_update(runtime)
    assert parameter.grad is not None
    assert torch.count_nonzero(parameter.grad).item() == parameter.numel()
    assert runtime.completed_update == 0


def test_validation_uses_target_weighting_and_preserves_all_rng_states(tmp_path: Path) -> None:
    view = create_synthetic_smoke_training_view_for_tests(
        _arrays(rows=17, lexical=50, varied=True),
        test_updates=100,
        microbatch_size=16,
    )
    *_, runtime = _runtime(tmp_path, view=view)
    prime_synthetic_runtime_to_update_for_tests(runtime, 100)
    random.seed(91)
    np.random.seed(92)
    torch.manual_seed(93)
    python_before = random.getstate()
    numpy_before = np.random.get_state()
    torch_before = torch.get_rng_state().clone()
    result = validate_tiny_smoke_condition(runtime)
    assert result.selected_target_count == dict(
        runtime._condition_view.aggregate_evidence
    )["validation_selected_targets"]
    assert runtime._model.training is True
    assert random.getstate() == python_before
    numpy_after = np.random.get_state()
    assert numpy_after[0] == numpy_before[0]
    assert np.array_equal(numpy_after[1], numpy_before[1])
    assert numpy_after[2:] == numpy_before[2:]
    assert torch.equal(torch.get_rng_state(), torch_before)
    tensors = runtime._condition_view.validation_tensors
    labels = tensors.labels
    assert labels is not None
    numerator = 0.0
    count = 0
    runtime._model.eval()
    with torch.inference_mode():
        for start in range(0, 17, 16):
            end = min(17, start + 16)
            outputs = runtime._model(
                input_ids=torch.tensor(tensors.input_ids[start:end].tolist()),
                attention_mask=torch.tensor(tensors.attention_mask[start:end].tolist()),
                token_type_ids=torch.tensor(tensors.token_type_ids[start:end].tolist()),
                return_dict=True,
            )
            batch_labels = torch.tensor(labels[start:end].tolist())
            numerator += float(
                torch.nn.functional.cross_entropy(
                    outputs.logits.reshape(-1, 8_000),
                    batch_labels.reshape(-1),
                    ignore_index=-100,
                    reduction="sum",
                ).item()
            )
            count += int(torch.count_nonzero(batch_labels != -100).item())
    runtime._model.train()
    assert result.normalized_loss == numerator / count
    with pytest.raises(SmokeTrainingError, match=SMOKE_VALIDATION_MISMATCH):
        validate_tiny_smoke_condition(runtime)


def test_validation_points_are_exact_and_exclude_update_zero(tmp_path: Path) -> None:
    assert VALIDATION_POINTS == tuple(range(100, 1_001, 100))
    assert 0 not in VALIDATION_POINTS
    assert smoke_module.MAX_VALIDATION_BATCH_SIZE == 16
    *_, runtime = _runtime(tmp_path)
    execute_next_optimizer_update(runtime)
    with pytest.raises(SmokeTrainingError, match=SMOKE_VALIDATION_MISMATCH):
        validate_tiny_smoke_condition(runtime)


def test_mid_update_checkpoint_and_resume_are_rejected(tmp_path: Path) -> None:
    *_, runtime = _runtime(tmp_path)
    runtime.at_update_boundary = False
    with pytest.raises(SmokeTrainingError, match=SMOKE_RESUME_MISMATCH):
        checkpoint_payloads_for_runtime(runtime)
    with pytest.raises(SmokeTrainingError, match=SMOKE_RESUME_MISMATCH):
        runtime_semantic_sha256(runtime)


def test_checkpoint_payload_is_complete_and_tampering_fails_closed(tmp_path: Path) -> None:
    view, _, _, _, authorization, optimizers, runtime = _runtime(tmp_path)
    envelope = checkpoint_envelope_for_runtime(runtime)
    payloads = envelope._files
    assert type(envelope) is CheckpointEnvelope
    assert set(payloads) == {
        "CHECKPOINT_COMPLETE.json",
        "checkpoint_inventory.json",
        "checkpoint_manifest.json",
        "checkpoint_state.pt",
    }
    manifest = json.loads(payloads["checkpoint_manifest.json"])
    assert manifest["completed_optimizer_update"] == 0
    assert manifest["device"] == "cpu"
    assert manifest["semantic_state_sha256"]
    restored = restore_synthetic_runtime_from_checkpoint(
        authorization,
        optimizers,
        "EnglishMono",
        envelope,
        expected_completed_update=0,
    )
    assert runtime_semantic_sha256(restored) == runtime_semantic_sha256(runtime)
    corrupted = dict(payloads)
    state_bytes = bytearray(corrupted["checkpoint_state.pt"])
    state_bytes[len(state_bytes) // 2] ^= 1
    corrupted["checkpoint_state.pt"] = bytes(state_bytes)
    with pytest.raises(SmokeTrainingError, match=SMOKE_RESUME_MISMATCH):
        reconstitute_checkpoint_envelope_for_tests(
            corrupted,
            expected_envelope_sha256=envelope.envelope_sha256,
        )
    assert view.authority_kind == "synthetic_test_only"


def test_checkpoint_cross_condition_and_cross_update_substitution_fail_closed(
    tmp_path: Path,
) -> None:
    _, _, _, _, authorization, _, runtime = _runtime(tmp_path)
    envelope = checkpoint_envelope_for_runtime(runtime)
    with pytest.raises(SmokeTrainingError, match=SMOKE_RESUME_MISMATCH):
        restore_synthetic_runtime_from_checkpoint(
            authorization,
            create_tiny_smoke_optimizers(authorization),
            "SpanishMono",
            envelope,
            expected_completed_update=0,
        )
    with pytest.raises(SmokeTrainingError, match=SMOKE_RESUME_MISMATCH):
        restore_synthetic_runtime_from_checkpoint(
            authorization,
            create_tiny_smoke_optimizers(authorization),
            "EnglishMono",
            envelope,
            expected_completed_update=250,
        )


def test_locally_rehashed_malicious_pickle_is_rejected_by_safe_decoder(
    tmp_path: Path,
) -> None:
    _, _, _, _, authorization, _, runtime = _runtime(tmp_path)
    files = dict(checkpoint_envelope_for_runtime(runtime)._files)
    files["checkpoint_state.pt"] = b"cos\nsystem\n(S'false'\ntR."
    manifest = json.loads(files["checkpoint_manifest.json"])
    manifest["state_sha256"] = hashlib.sha256(files["checkpoint_state.pt"]).hexdigest()
    files["checkpoint_manifest.json"] = smoke_module.canonical_json_bytes(manifest)
    inventory = json.loads(files["checkpoint_inventory.json"])
    for name in ("checkpoint_manifest.json", "checkpoint_state.pt"):
        inventory["files"][name]["sha256"] = hashlib.sha256(files[name]).hexdigest()
        inventory["files"][name]["size"] = len(files[name])
    files["checkpoint_inventory.json"] = smoke_module.canonical_json_bytes(inventory)
    completion = json.loads(files["CHECKPOINT_COMPLETE.json"])
    completion["inventory_sha256"] = hashlib.sha256(
        files["checkpoint_inventory.json"]
    ).hexdigest()
    files["CHECKPOINT_COMPLETE.json"] = smoke_module.canonical_json_bytes(completion)
    envelope = reconstitute_checkpoint_envelope_for_tests(
        files,
        expected_envelope_sha256=smoke_module._checkpoint_envelope_identity(files),
    )
    with pytest.raises(SmokeTrainingError, match=SMOKE_RESUME_MISMATCH):
        restore_synthetic_runtime_from_checkpoint(
            authorization,
            create_tiny_smoke_optimizers(authorization),
            "EnglishMono",
            envelope,
            expected_completed_update=0,
        )


@pytest.mark.parametrize(
    "tamper",
    (
        "model",
        "optimizer",
        "rng",
        "history",
        "additional_file",
        "missing_file",
        "malicious_pickle",
    ),
)
def test_semantically_rehashed_checkpoint_policy_tampering_fails_closed(
    tmp_path: Path,
    tamper: str,
) -> None:
    *_, runtime = _runtime(tmp_path)
    envelope = checkpoint_envelope_for_runtime(runtime)
    rewritten = dict(envelope._files)
    if tamper == "additional_file":
        rewritten["additional.bin"] = b"unexpected"
    elif tamper == "missing_file":
        rewritten.pop("checkpoint_manifest.json")
    elif tamper == "malicious_pickle":
        rewritten["checkpoint_state.pt"] = b"cos\nsystem\n(S'false'\ntR."
    else:
        state = torch.load(
            io.BytesIO(rewritten["checkpoint_state.pt"]),
            map_location="cpu",
            weights_only=True,
        )
        if tamper == "model":
            next(iter(state["model_state"].values())).add_(1)
        elif tamper == "optimizer":
            state["optimizer_state"]["param_groups"][0]["weight_decay"] = 0.0
        elif tamper == "rng":
            state["rng"]["torch_cpu"][0] ^= 1
        else:
            state["histories"]["loss"] = (999.0,)
        state["semantic_sha256"] = smoke_module._semantic_hash(
            {name: value for name, value in state.items() if name != "semantic_sha256"}
        )
        buffer = io.BytesIO()
        torch.save(state, buffer)
        rewritten["checkpoint_state.pt"] = buffer.getvalue()
    with pytest.raises(SmokeTrainingError, match=SMOKE_RESUME_MISMATCH):
        reconstitute_checkpoint_envelope_for_tests(
            rewritten,
            expected_envelope_sha256=envelope.envelope_sha256,
        )


def _private_parent(tmp_path: Path) -> Path:
    parent = (tmp_path / "private-artifacts").absolute()
    parent.mkdir()
    os.chmod(parent, 0o700)
    return parent


def _artifact_checkpoint_files(tmp_path: Path) -> Mapping[str, bytes]:
    authority_root = tmp_path / "artifact-authority"
    authority_root.mkdir(exist_ok=True)
    *_, runtime = _runtime(authority_root)
    return checkpoint_envelope_for_runtime(runtime)._files


def _valid_run_payloads() -> Mapping[str, bytes]:
    tracker_authority = {
        "actual_canonical_date": smoke_module.SYNTHETIC_UPDATED_TRACKER_DATE,
        "actual_sha256": "7" * 64,
        "actual_size": 2_991,
        "actual_version": smoke_module.SYNTHETIC_UPDATED_TRACKER_VERSION,
        "baseline_canonical_date": APPROVED_TRACKER_DATE,
        "baseline_sha256": APPROVED_TRACKER_SHA256,
        "baseline_size": APPROVED_TRACKER_SIZE,
        "baseline_version": APPROVED_TRACKER_VERSION,
    }
    run_manifest = {
        "authorization_sha256": "1" * 64,
        "candidate_checksum_record_sha256": "2" * 64,
        "completed_conditions": list(CONDITIONS),
        "completed_updates_per_condition": 1_000,
        "device": "cpu",
        "launch_manifest_sha256": "3" * 64,
        "mechanics_passed": True,
        "protocol": "neu_tiny_smoke_runtime_run_v1",
        "resume_rehearsal_result_sha256": "6" * 64,
        "run_identity_sha256": "4" * 64,
        "sanitized_view_sha256": "5" * 64,
        "terminal_classification": "mechanics_passed",
        "tracker_authority": tracker_authority,
    }
    return {"run_manifest.json": smoke_module.canonical_json_bytes(run_manifest)}


def test_condition_completion_accepts_exact_updated_tracker_authority(
    tmp_path: Path,
) -> None:
    authority_root = tmp_path / "condition-authority"
    authority_root.mkdir()
    _, authorization = _production_condition_runtime_authority(authority_root)
    writer = begin_private_run_artifacts(
        _private_parent(tmp_path),
        "synthetic-condition-run",
    )
    optimizers = create_tiny_smoke_optimizers(authorization)
    runtime = begin_tiny_smoke_condition(
        authorization,
        optimizers,
        "SpanishMono",
    )
    envelope = checkpoint_envelope_for_runtime(runtime)
    commit_private_checkpoint(
        writer,
        condition="SpanishMono",
        completed_update=0,
        payloads=envelope._files,
    )
    record = {
        "authorization_sha256": authorization.authorization_sha256,
        "candidate_checksum_record_sha256": (
            authorization.approval.candidate_checksum_record_sha256
        ),
        "completed_optimizer_updates": 1_000,
        "condition": "SpanishMono",
        "condition_protocol": "neu_tiny_smoke_condition_completion_v1",
        "device": "cpu",
        "launch_manifest_sha256": authorization.launch_manifest.manifest_sha256,
        "mechanics_passed": True,
        "sanitized_view_sha256": authorization.training_view_sha256,
        "semantic_sha256": "f" * 64,
        "tracker_authority": smoke_module._tracker_authority_binding(authorization),
    }
    result = commit_private_condition_result(
        writer,
        condition="SpanishMono",
        payloads={"condition_result.json": smoke_module.canonical_json_bytes(record)},
    )
    assert type(result) is ArtifactCommitResult


def test_checkpoint_and_run_transactions_are_private_completion_last_and_no_overwrite(
    tmp_path: Path,
) -> None:
    parent = _private_parent(tmp_path)
    writer = begin_private_run_artifacts(parent, "synthetic-run")
    checkpoint = commit_private_checkpoint(
        writer,
        condition="EnglishMono",
        completed_update=0,
        payloads=_artifact_checkpoint_files(tmp_path),
    )
    assert type(checkpoint) is ArtifactCommitResult
    checkpoint_root = (
        parent
        / writer._stage_name
        / "EnglishMono"
        / "cpu"
        / "checkpoint-0000"
    )
    assert (checkpoint_root / "CHECKPOINT_COMPLETE.json").is_file()
    assert set(path.name for path in checkpoint_root.iterdir()) == {
        "checkpoint_state.pt",
        "checkpoint_manifest.json",
        "checkpoint_inventory.json",
        "inventory.json",
        "CHECKPOINT_COMPLETE.json",
    }
    with pytest.raises(SmokeArtifactError, match=SMOKE_CHECKPOINT_WRITE_FAILURE):
        commit_private_checkpoint(
            writer,
            condition="EnglishMono",
            completed_update=0,
            payloads=_artifact_checkpoint_files(tmp_path),
        )
    result = commit_private_run(
        writer,
        payloads=_valid_run_payloads(),
        completion_fields={},
    )
    assert result.namespace == "synthetic-run"
    run_root = parent / "synthetic-run"
    assert (run_root / "RUN_COMPLETE.json").is_file()
    assert not any("label" in path.name or "token" in path.name for path in run_root.rglob("*"))
    for path in run_root.rglob("*"):
        status = path.lstat()
        assert not stat.S_ISLNK(status.st_mode)
        if path.is_dir():
            assert stat.S_IMODE(status.st_mode) == 0o700
        else:
            assert stat.S_IMODE(status.st_mode) == 0o600
            assert status.st_nlink == 1


@pytest.mark.parametrize(
    ("boundary", "expected"),
    (
        ("write:checkpoint_state.pt", SMOKE_CHECKPOINT_WRITE_FAILURE),
        ("sync:checkpoint_state.pt", SMOKE_CHECKPOINT_WRITE_FAILURE),
        ("snapshot", SMOKE_CHECKPOINT_WRITE_FAILURE),
        ("commit:before", SMOKE_CHECKPOINT_WRITE_FAILURE),
        ("commit:after", SMOKE_ARTIFACT_COMMIT_INDETERMINATE),
    ),
)
def test_checkpoint_failure_injection_is_fixed_and_no_retry(
    tmp_path: Path,
    boundary: str,
    expected: str,
) -> None:
    writer = begin_private_run_artifacts(_private_parent(tmp_path), "synthetic-run")

    def fail(current: str) -> None:
        if current == boundary:
            raise OSError("private failure detail")

    with pytest.raises(SmokeArtifactError) as caught:
        commit_private_checkpoint(
            writer,
            condition="EnglishMono",
            completed_update=0,
            payloads=_artifact_checkpoint_files(tmp_path),
            _test_hook=fail,
        )
    assert caught.value.args == (expected,)
    assert caught.value.__cause__ is None
    assert "private failure detail" not in repr(caught.value)


def test_checkpoint_stable_snapshot_detects_post_sync_mutation(tmp_path: Path) -> None:
    writer = begin_private_run_artifacts(_private_parent(tmp_path), "synthetic-run")

    def mutate(boundary: str) -> None:
        if boundary != "snapshot":
            return
        stages = tuple(
            (
                writer._parent
                / writer._stage_name
                / "EnglishMono"
                / "cpu"
            ).glob("artifact-stage-*")
        )
        assert len(stages) == 1
        target = stages[0] / "checkpoint_state.pt"
        target.write_bytes(b"mutated")
        os.chmod(target, 0o600)

    with pytest.raises(SmokeArtifactError, match=SMOKE_CHECKPOINT_WRITE_FAILURE):
        commit_private_checkpoint(
            writer,
            condition="EnglishMono",
            completed_update=0,
            payloads=_artifact_checkpoint_files(tmp_path),
            _test_hook=mutate,
        )


def test_artifact_parent_symlink_and_file_hardlink_anomalies_fail_closed(
    tmp_path: Path,
) -> None:
    parent = _private_parent(tmp_path)
    alias = (tmp_path / "private-artifacts-alias").absolute()
    alias.symlink_to(parent, target_is_directory=True)
    with pytest.raises(SmokeArtifactError, match=SMOKE_CHECKPOINT_WRITE_FAILURE):
        begin_private_run_artifacts(alias, "synthetic-run")

    writer = begin_private_run_artifacts(parent, "synthetic-hardlink-run")

    def add_hardlink(boundary: str) -> None:
        if boundary != "snapshot":
            return
        stages = tuple(
            (
                writer._parent
                / writer._stage_name
                / "EnglishMono"
                / "cpu"
            ).glob("artifact-stage-*")
        )
        assert len(stages) == 1
        os.link(
            stages[0] / "checkpoint_state.pt",
            stages[0] / "state-hardlink.bin",
        )

    with pytest.raises(SmokeArtifactError, match=SMOKE_CHECKPOINT_WRITE_FAILURE):
        commit_private_checkpoint(
            writer,
            condition="EnglishMono",
            completed_update=0,
            payloads=_artifact_checkpoint_files(tmp_path),
            _test_hook=add_hardlink,
        )


def test_whole_run_stable_snapshot_detects_post_inventory_mutation(tmp_path: Path) -> None:
    writer = begin_private_run_artifacts(
        _private_parent(tmp_path),
        "synthetic-run",
    )

    def mutate(boundary: str) -> None:
        if boundary == "snapshot":
            target = writer._parent / writer._stage_name / "run_manifest.json"
            target.write_bytes(b'{"forged":true}\n')
            os.chmod(target, 0o600)

    with pytest.raises(SmokeArtifactError, match=SMOKE_CHECKPOINT_WRITE_FAILURE):
        commit_private_run(
            writer,
            payloads=_valid_run_payloads(),
            completion_fields={},
            _test_hook=mutate,
        )


@pytest.mark.parametrize(
    "completion_fields",
    (
        {"complete": "false"},
        {"run_name": "forged"},
        {"inventory_sha256": "0" * 64},
        {"terminal_classification": "scientific_result"},
        {"mechanics_passed": "false"},
    ),
)
def test_run_completion_reserved_fields_cannot_be_overridden(
    tmp_path: Path,
    completion_fields: Mapping[str, object],
) -> None:
    writer = begin_private_run_artifacts(
        _private_parent(tmp_path),
        "synthetic-run",
    )
    with pytest.raises(SmokeArtifactError, match=SMOKE_CHECKPOINT_WRITE_FAILURE):
        commit_private_run(
            writer,
            payloads=_valid_run_payloads(),
            completion_fields=completion_fields,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("mechanics_passed", False),
        ("terminal_classification", "scientific_result"),
        ("completed_updates_per_condition", 999),
        ("completed_conditions", ["EnglishMono"]),
    ),
)
def test_run_manifest_protocol_facts_are_fixed(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    payloads = dict(_valid_run_payloads())
    record = json.loads(payloads["run_manifest.json"])
    record[field] = value
    payloads["run_manifest.json"] = smoke_module.canonical_json_bytes(record)
    writer = begin_private_run_artifacts(
        _private_parent(tmp_path),
        "synthetic-run",
    )
    with pytest.raises(SmokeArtifactError, match=SMOKE_CHECKPOINT_WRITE_FAILURE):
        commit_private_run(writer, payloads=payloads, completion_fields={})


@pytest.mark.parametrize(
    "tamper",
    ("missing", "wrong_lineage", "obsolete_actual_identity"),
)
def test_run_manifest_tracker_authority_is_fixed(
    tmp_path: Path,
    tamper: str,
) -> None:
    payloads = dict(_valid_run_payloads())
    record = json.loads(payloads["run_manifest.json"])
    tracker_authority = record["tracker_authority"]
    if tamper == "missing":
        del record["tracker_authority"]
    elif tamper == "wrong_lineage":
        tracker_authority["baseline_sha256"] = "f" * 64
    else:
        tracker_authority["actual_sha256"] = APPROVED_TRACKER_SHA256
        tracker_authority["actual_size"] = APPROVED_TRACKER_SIZE
    payloads["run_manifest.json"] = smoke_module.canonical_json_bytes(record)
    writer = begin_private_run_artifacts(
        _private_parent(tmp_path),
        "synthetic-run",
    )
    with pytest.raises(SmokeArtifactError, match=SMOKE_CHECKPOINT_WRITE_FAILURE):
        commit_private_run(writer, payloads=payloads, completion_fields={})


def test_checkpoint_completion_protocol_facts_are_fixed(tmp_path: Path) -> None:
    payloads = dict(_artifact_checkpoint_files(tmp_path))
    completion = json.loads(payloads["CHECKPOINT_COMPLETE.json"])
    completion["complete"] = False
    payloads["CHECKPOINT_COMPLETE.json"] = smoke_module.canonical_json_bytes(completion)
    writer = begin_private_run_artifacts(
        _private_parent(tmp_path),
        "synthetic-run",
    )
    with pytest.raises(SmokeArtifactError, match=SMOKE_CHECKPOINT_WRITE_FAILURE):
        commit_private_checkpoint(
            writer,
            condition="EnglishMono",
            completed_update=0,
            payloads=payloads,
        )


@pytest.mark.parametrize("race", ("symlink", "stage_swap", "inode_change"))
def test_descriptor_relative_run_inventory_rejects_component_races(
    tmp_path: Path,
    race: str,
) -> None:
    writer = begin_private_run_artifacts(
        _private_parent(tmp_path),
        "synthetic-run",
    )

    def inject(boundary: str) -> None:
        if boundary != "snapshot":
            return
        stage = writer._parent / writer._stage_name
        if race == "symlink":
            (stage / "unexpected-link").symlink_to(stage / "run_manifest.json")
        elif race == "stage_swap":
            displaced = writer._parent / "displaced-stage"
            stage.rename(displaced)
            stage.mkdir(mode=0o700)
        else:
            target = stage / "run_manifest.json"
            replacement = stage / "replacement.tmp"
            replacement.write_bytes(target.read_bytes())
            os.chmod(replacement, 0o600)
            replacement.replace(target)

    with pytest.raises(SmokeArtifactError, match=SMOKE_CHECKPOINT_WRITE_FAILURE):
        commit_private_run(
            writer,
            payloads=_valid_run_payloads(),
            completion_fields={},
            _test_hook=inject,
        )


def test_update_750_checkpoint_resume_matches_uninterrupted_semantics(tmp_path: Path) -> None:
    view = create_synthetic_smoke_training_view_for_tests(
        _arrays(rows=4, lexical=64),
        test_updates=751,
        microbatch_size=4,
    )
    _, _, _, _, authorization, optimizers = _authority(tmp_path, view=view)
    uninterrupted = begin_tiny_smoke_condition(authorization, optimizers, "EnglishMono")
    prime_synthetic_runtime_to_checkpoint_for_tests(uninterrupted, 750)
    checkpoint = checkpoint_envelope_for_runtime(uninterrupted)
    resumed_optimizers = create_tiny_smoke_optimizers(authorization)
    resumed = restore_synthetic_runtime_from_checkpoint(
        authorization,
        resumed_optimizers,
        "EnglishMono",
        checkpoint,
        expected_completed_update=750,
    )
    first = execute_next_optimizer_update(uninterrupted)
    second = execute_next_optimizer_update(resumed)
    assert first.mask_checksum_sha256 == second.mask_checksum_sha256
    assert first.selected_target_count == second.selected_target_count
    assert first.normalized_loss.hex() == second.normalized_loss.hex()
    assert runtime_semantic_sha256(uninterrupted) == runtime_semantic_sha256(resumed)


def test_fresh_process_update_750_resume_is_bitwise_equivalent(tmp_path: Path) -> None:
    view = create_synthetic_smoke_training_view_for_tests(
        _arrays(rows=1, lexical=126),
        test_updates=1_000,
        microbatch_size=1,
    )
    tracker = _write_tracker(tmp_path / "fresh-tracker.md", view)
    approval = load_synthetic_candidate_approval_for_tests(
        tracker,
        candidate_checksum=view.candidate_checksum_record_sha256,
        preparation_manifest=view.preparation_manifest_sha256,
        schedule_identity=view.schedule_plan_identity_sha256,
    )
    launch = derive_synthetic_smoke_launch_manifest_for_tests(
        approval,
        executor_commit="a" * 40,
        executor_closure_digest="b" * 64,
    )
    paired = create_paired_initialization(NEU_TINY, TINY_SMOKE_SEED_PLANS[0])
    authorization = derive_synthetic_smoke_execution_authorization_for_tests(
        approval, launch, view, paired
    )
    optimizers = create_tiny_smoke_optimizers(authorization)
    uninterrupted = begin_tiny_smoke_condition(authorization, optimizers, "EnglishMono")
    envelope = None
    for update in range(1, 1_001):
        execute_next_optimizer_update(uninterrupted)
        if update in VALIDATION_POINTS:
            validate_tiny_smoke_condition(uninterrupted)
        if update == 750:
            envelope = checkpoint_envelope_for_runtime(uninterrupted)
    assert type(envelope) is CheckpointEnvelope
    workspace = (tmp_path / "fresh-process-worker").resolve()
    result = run_synthetic_fresh_process_resume_for_tests(
        authorization,
        envelope,
        uninterrupted,
        workspace,
    )
    assert result["worker_pid"] != result["parent_pid"] == os.getpid()
    assert result["fresh_interpreter"] is True
    assert result["checkpoint_update"] == 750
    assert result["first_replay_update"] == 751
    assert result["last_replay_update"] == 1_000
    assert result["replay_update_count"] == 250
    assert result["validation_updates"] == (800, 900, 1_000)
    assert result["runtime_semantic_sha256"] == runtime_semantic_sha256(uninterrupted)
    assert not workspace.exists()


def _failed_fresh_process_material(tmp_path: Path):
    view = create_synthetic_smoke_training_view_for_tests(
        _arrays(rows=1, lexical=126),
        test_updates=1_000,
        microbatch_size=1,
    )
    _, _, _, _, authorization, optimizers = _authority(tmp_path, view=view)
    checkpoint_runtime = begin_tiny_smoke_condition(
        authorization,
        optimizers,
        "EnglishMono",
    )
    prime_synthetic_runtime_to_checkpoint_for_tests(checkpoint_runtime, 750)
    envelope = checkpoint_envelope_for_runtime(checkpoint_runtime)
    final_optimizers = create_tiny_smoke_optimizers(authorization)
    uninterrupted = begin_tiny_smoke_condition(
        authorization,
        final_optimizers,
        "EnglishMono",
    )
    prime_synthetic_runtime_to_checkpoint_for_tests(uninterrupted, 1_000)
    return authorization, envelope, uninterrupted


@pytest.mark.parametrize(
    "fault",
    (
        "wrong_condition",
        "wrong_update",
        "missing_envelope",
        "inconsistent_envelope",
        "child_nonzero",
        "timeout",
        "missing_result",
        "malformed_result",
        "identity_mismatch",
    ),
)
def test_fresh_process_replay_failures_are_closed_and_disposable(
    tmp_path: Path,
    fault: str,
) -> None:
    authority_root = tmp_path / "authority"
    authority_root.mkdir()
    authorization, envelope, uninterrupted = _failed_fresh_process_material(
        authority_root
    )
    workspace = (tmp_path / f"replay-{fault}").resolve()
    with pytest.raises(SmokeTrainingError, match=SMOKE_RESUME_MISMATCH):
        run_synthetic_fresh_process_resume_for_tests(
            authorization,
            envelope,
            uninterrupted,
            workspace,
            fault=fault,
        )
    assert not workspace.exists()


def test_canonical_orchestrator_requires_worker_and_never_restores_in_process() -> None:
    code = smoke_module._execute_canonical_four_condition_orchestrator_impl.__code__
    assert "_run_fresh_process_resume_rehearsal" in code.co_names
    assert "_restore_runtime_from_checkpoint_impl" not in code.co_names
    assert "subprocess" in smoke_module._launch_fresh_process_replay.__code__.co_names


def test_fresh_process_worker_failure_is_not_retried(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority_root = tmp_path / "authority"
    authority_root.mkdir()
    authorization, envelope, uninterrupted = _failed_fresh_process_material(
        authority_root
    )
    calls = 0
    original = smoke_module.subprocess.Popen

    def counted_popen(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(smoke_module.subprocess, "Popen", counted_popen)
    workspace = (tmp_path / "single-attempt").resolve()
    with pytest.raises(SmokeTrainingError, match=SMOKE_RESUME_MISMATCH):
        run_synthetic_fresh_process_resume_for_tests(
            authorization,
            envelope,
            uninterrupted,
            workspace,
            fault="child_nonzero",
        )
    assert calls == 1
    assert not workspace.exists()


def test_device_switching_and_production_execution_remain_impossible(tmp_path: Path) -> None:
    _, _, _, _, authorization, optimizers = _authority(tmp_path)
    object.__setattr__(authorization, "device", "mps")
    with pytest.raises(SmokeTrainingError, match=SMOKE_APPROVAL_MISMATCH):
        begin_tiny_smoke_condition(authorization, optimizers, "EnglishMono")
    object.__setattr__(authorization, "device", "cpu")
    with pytest.raises(SmokeTrainingError, match=SMOKE_APPROVAL_MISMATCH):
        execute_bounded_tiny_smoke(authorization)
    assert not smoke_module.APPROVED_OUTPUT_PARENT.exists()


def test_fail_closed_cli_exposes_no_scientific_or_execution_options(tmp_path: Path) -> None:
    script = Path(smoke_module.__file__).resolve().parents[3] / "scripts/run_bounded_tiny_smoke.py"
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    for arguments in ((), ("--device", "mps"), ("--candidate", "private")):
        result = subprocess.run(
            [sys.executable, str(script), *arguments],
            cwd=tmp_path,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 2
        assert result.stdout == ""
        payload = json.loads(result.stderr)
        assert payload == {
            "code": SMOKE_APPROVAL_MISMATCH,
            "executed": False,
            "mechanics_only": True,
            "status": "launch_not_authorized",
        }


def test_cli_and_reviewed_factory_have_a_reachable_option_free_production_edge() -> None:
    script = Path(smoke_module.__file__).resolve().parents[3] / "scripts/run_bounded_tiny_smoke.py"
    source = script.read_text(encoding="utf-8")
    assert source.count("construct_production_smoke_execution_authorization()") == 1
    assert source.count("execute_bounded_tiny_smoke(authorization)") == 1
    assert tuple(
        inspect.signature(
            smoke_module.construct_production_smoke_execution_authorization
        ).parameters
    ) == ()
    closure = inspect.getclosurevars(
        smoke_module.construct_production_smoke_execution_authorization
    ).nonlocals
    assert (
        closure["production_authority_impl"]
        is not smoke_module._construct_production_smoke_execution_authorization_impl
    )


def test_public_type_identity_reload_old_references_and_reverse_import_are_stable() -> None:
    old_types = {
        name: getattr(smoke_module, name)
        for name in smoke_module.SMOKE_PUBLIC_BOUNDARY_CLASS_INVENTORY[
            smoke_module.__name__
        ]
    }
    old_update = smoke_module.execute_next_optimizer_update
    old_production_factory = (
        smoke_module.construct_production_smoke_execution_authorization
    )
    old_error = smoke_module.SmokeTrainingError
    artifact_types = dict(artifact_module.SMOKE_ARTIFACT_PUBLIC_TYPES)
    reloaded_artifacts = importlib.reload(artifact_module)
    assert all(getattr(reloaded_artifacts, name) is value for name, value in artifact_types.items())
    reloaded = importlib.reload(smoke_module)
    assert all(getattr(reloaded, name) is value for name, value in old_types.items())
    assert old_error is reloaded.SmokeTrainingError
    assert old_update is not reloaded.execute_next_optimizer_update
    with pytest.raises(SmokeTrainingError, match=SMOKE_APPROVAL_MISMATCH):
        old_production_factory()
    assert not reloaded.SMOKE_EXTERNAL_APPLICATION_CALLABLE_ALLOWLIST


def test_module_global_replacement_cannot_redirect_closed_public_entrypoints(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    *_, runtime = _runtime(tmp_path)
    calls: list[str] = []

    def permissive(*args, **kwargs):
        del args, kwargs
        calls.append("redirected")
        return object()

    monkeypatch.setattr(smoke_module, "_execute_next_update_impl", permissive)
    monkeypatch.setattr(
        smoke_module,
        "_construct_production_smoke_execution_authorization_impl",
        permissive,
    )
    monkeypatch.setattr(smoke_module, "derive_tiny_dropout_seed", permissive)
    result = execute_next_optimizer_update(runtime)
    with pytest.raises(SmokeTrainingError, match=SMOKE_APPROVAL_MISMATCH):
        construct_production_smoke_execution_authorization()
    assert result.completed_update == 1
    assert calls == []


def test_privacy_safe_exception_has_neutralized_public_traceback_locals(tmp_path: Path) -> None:
    private_marker = "private-tensor-marker-99173"
    *_, runtime = _runtime(tmp_path)
    runtime._optimizer.param_groups[0]["weight_decay"] = 0.0
    with pytest.raises(SmokeTrainingError) as caught:
        execute_next_optimizer_update(runtime)
    error = caught.value
    assert error.__cause__ is None
    assert error.__context__ is None
    assert private_marker not in "".join(traceback.format_exception(error))
    for frame, _ in traceback.walk_tb(error.__traceback__):
        if frame.f_code.co_name == "update":
            assert frame.f_locals["runtime_value"] is None


def test_runtime_and_condition_order_tampering_fail_closed(tmp_path: Path) -> None:
    *_, runtime = _runtime(tmp_path, test_updates=2)
    runtime.completed_update = 1
    with pytest.raises(SmokeTrainingError, match=SMOKE_DATA_SCHEDULE_MISMATCH):
        execute_next_optimizer_update(runtime)
    with pytest.raises(SmokeTrainingError, match=SMOKE_APPROVAL_MISMATCH):
        begin_tiny_smoke_condition(
            runtime._authorization,
            create_tiny_smoke_optimizers(runtime._authorization),
            "not-a-condition",
        )


def test_cpu_deterministic_algorithms_are_enabled_by_authorization(tmp_path: Path) -> None:
    _, _, _, _, authorization, _ = _authority(tmp_path)
    assert authorization.device == "cpu"
    assert authorization.maximum_concurrent_conditions == 1
    assert torch.are_deterministic_algorithms_enabled()
    assert all(
        parameter.device.type == "cpu"
        for model in authorization._models.values()
        for parameter in model.parameters()
    )


def test_smoke_production_graph_inventory_is_explicit_and_allowlist_empty() -> None:
    assert smoke_module.SMOKE_PRODUCTION_REVIEWED_CALLABLES == {
        "approved_learning_rate",
        "construct_production_smoke_execution_authorization",
        "derive_tiny_dropout_seed",
        "execute_bounded_tiny_smoke",
        "execute_tiny_resume_replay_worker",
        "learning_rate_state_after_update",
        "load_candidate_approval_evidence",
    }
    assert not smoke_module.SMOKE_EXTERNAL_APPLICATION_CALLABLE_ALLOWLIST
    assert set(smoke_module.SMOKE_PUBLIC_BOUNDARY_CLASS_INVENTORY) == {
        "cslm.modeling.smoke_training",
        "cslm.modeling.preparation",
        "cslm.modeling.smoke_artifacts",
    }
    closure = inspect.getclosurevars(smoke_module.execute_bounded_tiny_smoke).nonlocals
    assert closure["production_impl"] is not smoke_module._execute_bounded_tiny_smoke_impl
