from __future__ import annotations

import inspect
import os
from collections.abc import Iterator
from hashlib import sha256

import pytest
import torch
from synthetic_preparation_support import build_synthetic_preparation_fixture
from transformers import BertForMaskedLM

import cslm.modeling.initialization as initialization_module
import cslm.modeling.preparation as preparation_module
from cslm.modeling.config import (
    CONDITIONS,
    NEU_SMALL,
    NEU_TINY,
    ModelContractError,
    ModelSize,
    approved_model_specification,
    validate_bert_config,
    validate_model,
)
from cslm.modeling.contracts import (
    APPROVED_BUDGET,
    APPROVED_DEVICE_POLICY,
    APPROVED_OPTIMIZER,
    DevicePolicyContract,
    ManifestContractError,
    OptimizerContract,
    PairedRunManifest,
    RunManifest,
    create_paired_run_manifest,
)
from cslm.modeling.initialization import (
    SMALL_FIRST_RUN_SEED_PLAN,
    SMALL_PILOT_SEED_PLANS,
    TINY_SMOKE_SEED_PLANS,
    InitializationContractError,
    InitializationManifest,
    PairedInitialization,
    ReplicateSeedPlan,
    create_paired_initialization,
    initial_state_sha256,
    verify_identical_initial_states,
)
from cslm.modeling.masking import (
    MaskingContractError,
    ValidationMaskRecord,
)
from cslm.modeling.preparation import (
    PREPARATION_PROTOCOL_VERSION,
    CandidateValidationSnapshot,
    PreparationSnapshot,
    SyntheticPreparationSnapshot,
    canonical_json_bytes,
    load_synthetic_preparation_candidate,
)


@pytest.fixture(scope="module")
def tiny_initialization() -> PairedInitialization:
    return create_paired_initialization(NEU_TINY, TINY_SMOKE_SEED_PLANS[0])


@pytest.fixture(scope="module")
def small_initialization() -> PairedInitialization:
    return create_paired_initialization(NEU_SMALL, SMALL_FIRST_RUN_SEED_PLAN)


@pytest.fixture
def preparation_snapshot(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[PreparationSnapshot]:
    fixture = build_synthetic_preparation_fixture(
        tmp_path / "synthetic-preparation-snapshot",
    )
    validations = []
    for material in fixture.bundle.validation:
        prefix = (
            fixture.output_root
            / "synthetic-artifacts"
            / "validation"
            / material.condition
            / material.plan_name
        )
        artifact_names = (
            "masked_input_ids.npy",
            "labels.npy",
            "attention_mask.npy",
            "token_type_ids.npy",
            "example_identities.json",
            "validation_mask_record.json",
        )
        validation = object.__new__(CandidateValidationSnapshot)
        object.__setattr__(validation, "condition", material.condition)
        object.__setattr__(validation, "plan_name", material.plan_name)
        object.__setattr__(validation, "seed", material.seed)
        object.__setattr__(validation, "record", material.record)
        object.__setattr__(
            validation,
            "artifact_identities",
            tuple(
                (
                    f"validation/{material.condition}/{material.plan_name}/{name}",
                    sha256((prefix / name).read_bytes()).hexdigest(),
                )
                for name in artifact_names
            ),
        )
        validations.append(validation)
    snapshot = object.__new__(PreparationSnapshot)
    object.__setattr__(snapshot, "status", "candidate_unapproved")
    object.__setattr__(snapshot, "protocol_version", PREPARATION_PROTOCOL_VERSION)
    object.__setattr__(
        snapshot,
        "candidate_checksum_record_sha256",
        fixture.published.artifact_map_sha256,
    )
    object.__setattr__(
        snapshot,
        "preparation_manifest_sha256",
        fixture.published.manifest_sha256,
    )
    object.__setattr__(snapshot, "_candidate_root", fixture.output_root)
    object.__setattr__(
        snapshot,
        "_reconciliation_key_path",
        tmp_path / "synthetic-contract-test-key-is-not-used",
    )
    object.__setattr__(
        snapshot,
        "_tree_identity_sha256",
        sha256(canonical_json_bytes(["synthetic-contract-test"])).hexdigest(),
    )
    object.__setattr__(snapshot, "_validation_snapshots", tuple(validations))

    def verify_contract_test_snapshot(value: PreparationSnapshot) -> None:
        if type(value) is not PreparationSnapshot or value is not snapshot:
            raise preparation_module.PreparationError(
                "contract test snapshot is not the verified fixture"
            )
        loaded = load_synthetic_preparation_candidate(fixture.output_root)
        if (
            value.candidate_checksum_record_sha256
            != loaded.artifact_map_sha256
            or value.preparation_manifest_sha256 != loaded.manifest_sha256
        ):
            raise preparation_module.PreparationError(
                "contract test snapshot changed"
            )

    monkeypatch.setattr(
        preparation_module,
        "verify_preparation_snapshot",
        verify_contract_test_snapshot,
    )
    yield snapshot


@pytest.fixture
def synthetic_preparation_snapshot(tmp_path) -> SyntheticPreparationSnapshot:
    return build_synthetic_preparation_fixture(
        tmp_path / "synthetic-rejection-snapshot",
    ).snapshot


@pytest.mark.parametrize(
    ("specification", "layers", "hidden", "heads", "intermediate", "parameters"),
    [
        (NEU_TINY, 2, 128, 2, 512, 1_462_080),
        (NEU_SMALL, 4, 256, 4, 1_024, 5_314_880),
    ],
)
def test_exact_approved_model_fields_and_parameter_counts(
    specification,
    layers: int,
    hidden: int,
    heads: int,
    intermediate: int,
    parameters: int,
) -> None:
    config = specification.to_bert_config()
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(99)
        model = BertForMaskedLM(config)

    assert config.vocab_size == 8_000
    assert config.max_position_embeddings == 128
    assert config.position_embedding_type == "absolute"
    assert config.type_vocab_size == 1
    assert config.hidden_act == "gelu"
    assert config.hidden_dropout_prob == 0.1
    assert config.attention_probs_dropout_prob == 0.1
    assert config.initializer_range == 0.02
    assert config.layer_norm_eps == 1e-12
    assert config.use_cache is False
    assert config.tie_word_embeddings is True
    assert config.pad_token_id == 0
    assert config.num_hidden_layers == layers
    assert config.hidden_size == hidden
    assert config.num_attention_heads == heads
    assert config.intermediate_size == intermediate
    assert specification.unk_token_id == 1
    assert specification.cls_token_id == 2
    assert specification.sep_token_id == 3
    assert specification.mask_token_id == 4
    assert specification.objective == "masked_language_modeling"
    assert specification.pretrained_weights is False
    assert specification.next_sentence_prediction is False
    assert not hasattr(model.cls, "seq_relationship")
    assert validate_model(model, specification) == parameters
    assert model.get_input_embeddings().weight is model.get_output_embeddings().weight


def test_model_configuration_checksums_are_exact_and_stable() -> None:
    assert NEU_TINY.configuration_sha256() == (
        "ed6a7ca4d0fcf1ce2877b78393411ea35350fb383fa44c1c0eb3752e593a66b0"
    )
    assert NEU_SMALL.configuration_sha256() == (
        "d088cb46733b8a5eebf23120c9fe0f6e4de8f3feeafcccb311d1a8d5c885d0f1"
    )
    assert approved_model_specification(ModelSize.TINY) == NEU_TINY
    assert approved_model_specification(ModelSize.SMALL) == NEU_SMALL


def test_configuration_validation_fails_closed_on_drift() -> None:
    config = NEU_TINY.to_bert_config()
    config.type_vocab_size = 2
    with pytest.raises(ModelContractError, match="differs"):
        validate_bert_config(config, NEU_TINY)


def test_paired_initialization_is_exact_and_checksum_recorded(
    tiny_initialization: PairedInitialization,
) -> None:
    paired = tiny_initialization

    assert tuple(paired.models) == CONDITIONS
    assert paired.manifest.trainable_parameter_count == 1_462_080
    assert paired.manifest.configuration_sha256 == NEU_TINY.configuration_sha256()
    assert paired.manifest.initial_state_sha256 == (
        "0a82ea3846ab242b628df72f1e7a8c440674b75deee0a4fb91652e144989fb26"
    )
    assert paired.manifest.conditions == CONDITIONS
    assert dict(paired.manifest.implementation_versions) == {
        "numpy": "1.26.4",
        "tokenizers": "0.22.2",
        "torch": "2.11.0",
        "transformers": "5.6.2",
    }
    assert all(
        model is not paired.models["EnglishMono"] for model in list(paired.models.values())[1:]
    )
    assert {initial_state_sha256(model) for model in paired.models.values()} == {
        paired.manifest.initial_state_sha256
    }
    assert any(
        {
            "bert.embeddings.word_embeddings.weight",
            "cls.predictions.decoder.weight",
        }
        <= set(group)
        for group in paired.manifest.tied_parameter_groups
    )


def test_small_first_run_initialization_checksum_is_exact(
    small_initialization: PairedInitialization,
) -> None:
    paired = small_initialization
    assert paired.manifest.trainable_parameter_count == 5_314_880
    assert paired.manifest.initial_state_sha256 == (
        "c1a9daf1a1a19871c02655a36cfdb43af61b44cd55f422e0e7a892d3f3d75dc2"
    )


def test_changed_seed_changes_initial_state_and_copy_verifier_fails_on_mutation() -> None:
    first = create_paired_initialization(NEU_TINY, TINY_SMOKE_SEED_PLANS[0])
    second = create_paired_initialization(
        NEU_TINY,
        ReplicateSeedPlan(1_730, 11_730, 21_730),
    )
    assert first.manifest.initial_state_sha256 != second.manifest.initial_state_sha256

    with torch.no_grad():
        next(second.models["CsCont"].parameters()).view(-1)[0] += 1
    with pytest.raises(InitializationContractError, match="value mismatch"):
        verify_identical_initial_states(
            second.models,
            NEU_TINY,
            expected_configuration_sha256=second.manifest.configuration_sha256,
            expected_state_sha256=second.manifest.initial_state_sha256,
        )


def test_initialization_verifier_rejects_two_aliased_nonreference_models() -> None:
    paired = create_paired_initialization(NEU_TINY, TINY_SMOKE_SEED_PLANS[0])
    aliased = dict(paired.models)
    aliased["CsCont"] = aliased["MonoCont"]
    with pytest.raises(InitializationContractError, match="pairwise-distinct"):
        verify_identical_initial_states(
            aliased,
            NEU_TINY,
            expected_configuration_sha256=paired.manifest.configuration_sha256,
            expected_state_sha256=paired.manifest.initial_state_sha256,
        )


def test_initialization_verifier_rejects_shared_parameter_storage() -> None:
    paired = create_paired_initialization(NEU_TINY, TINY_SMOKE_SEED_PLANS[0])
    shared = dict(paired.models)
    shared["CsCont"].set_input_embeddings(shared["EnglishMono"].get_input_embeddings())
    shared["CsCont"].tie_weights()
    with pytest.raises(InitializationContractError, match="storage is shared"):
        verify_identical_initial_states(
            shared,
            NEU_TINY,
            expected_configuration_sha256=paired.manifest.configuration_sha256,
            expected_state_sha256=paired.manifest.initial_state_sha256,
        )


def test_initialization_verifier_rejects_unauthorized_tie_in_nonreference_model() -> None:
    paired = create_paired_initialization(NEU_TINY, TINY_SMOKE_SEED_PLANS[0])
    model = paired.models["CsCont"]
    shared_bias = model.bert.embeddings.LayerNorm.bias
    target_layer_norm = model.bert.encoder.layer[0].attention.output.LayerNorm
    assert torch.equal(shared_bias, target_layer_norm.bias)
    target_layer_norm.bias = torch.nn.Parameter(shared_bias.view_as(shared_bias))

    with pytest.raises(InitializationContractError, match="tying mismatch"):
        verify_identical_initial_states(
            paired.models,
            NEU_TINY,
            expected_configuration_sha256=paired.manifest.configuration_sha256,
            expected_state_sha256=paired.manifest.initial_state_sha256,
        )


def test_initialization_verifier_hashes_and_compares_model_buffers() -> None:
    paired = create_paired_initialization(NEU_TINY, TINY_SMOKE_SEED_PLANS[0])
    original_hash = initial_state_sha256(paired.models["CsCont"])
    position_ids = dict(paired.models["CsCont"].named_buffers())["bert.embeddings.position_ids"]
    position_ids[0, 0] = 1
    assert initial_state_sha256(paired.models["CsCont"]) != original_hash
    with pytest.raises(InitializationContractError, match="buffer value mismatch"):
        verify_identical_initial_states(
            paired.models,
            NEU_TINY,
            expected_configuration_sha256=paired.manifest.configuration_sha256,
            expected_state_sha256=paired.manifest.initial_state_sha256,
        )


def test_replication_seed_policy_is_explicit() -> None:
    assert TINY_SMOKE_SEED_PLANS == (ReplicateSeedPlan(1_729, 11_729, 21_729),)
    assert SMALL_FIRST_RUN_SEED_PLAN == ReplicateSeedPlan(271_828, 281_828, 291_828)
    assert SMALL_PILOT_SEED_PLANS == (
        ReplicateSeedPlan(271_828, 281_828, 291_828),
        ReplicateSeedPlan(314_159, 324_159, 334_159),
        ReplicateSeedPlan(161_803, 171_803, 181_803),
    )


def _paired_run_manifest(
    initialization: PairedInitialization,
    preparation_snapshot: PreparationSnapshot,
    *,
    device: str = "cpu",
) -> PairedRunManifest:
    return create_paired_run_manifest(
        initialization,
        preparation_snapshot=preparation_snapshot,
        expected_preparation_checksum_record_sha256=(
            preparation_snapshot.candidate_checksum_record_sha256
        ),
        preparation_authorization_version="synthetic-contract-test-v1",
        device=device,
        mps_repeatability_passed=True if device == "mps" else None,
    )


def test_typed_future_contract_and_paired_manifest_validation(
    small_initialization: PairedInitialization,
    preparation_snapshot: PreparationSnapshot,
) -> None:
    assert APPROVED_BUDGET.optimizer_updates == 1_000
    assert APPROVED_BUDGET.projected_sequence_exposures == 64_000
    assert APPROVED_BUDGET.microbatch_sequences == 16
    assert APPROVED_BUDGET.gradient_accumulation_steps == 4
    assert APPROVED_BUDGET.diagnostic_checkpoint_updates == (0, 250, 500, 750)
    assert APPROVED_BUDGET.primary_checkpoint_update == 1_000
    assert APPROVED_BUDGET.fixed_mask_validation_interval == 100
    assert APPROVED_OPTIMIZER.peak_learning_rate == 1e-4
    assert APPROVED_DEVICE_POLICY.tiny_smoke_devices == ("cpu", "mps")
    assert APPROVED_DEVICE_POLICY.small_mps_reproducibility_updates == 10
    assert APPROVED_DEVICE_POLICY.small_mps_max_absolute_loss_difference == 1e-5
    assert APPROVED_DEVICE_POLICY.small_mps_max_absolute_parameter_difference == 1e-5
    assert APPROVED_DEVICE_POLICY.maximum_concurrent_conditions == 1
    paired = _paired_run_manifest(small_initialization, preparation_snapshot)
    assert tuple(run.device for run in paired.runs) == ("cpu",) * 4
    assert all(run.initialization is paired.runs[0].initialization for run in paired.runs)
    assert paired.runs[0].initialization == small_initialization.manifest
    assert all(run.model_size is ModelSize.SMALL for run in paired.runs)
    assert all(run.configuration_sha256 == NEU_SMALL.configuration_sha256() for run in paired.runs)
    assert tuple(run.condition for run in paired.runs) == CONDITIONS
    assert tuple(run.validation_mask_record.condition for run in paired.runs) == CONDITIONS
    assert all(len(run.validation_artifact_identities) == 6 for run in paired.runs)
    assert all(run.preparation_identity_matches is True for run in paired.runs)
    assert all(
        run.expected_approved_preparation_checksum_record_sha256
        == run.verified_candidate_checksum_record_sha256
        == preparation_snapshot.candidate_checksum_record_sha256
        for run in paired.runs
    )
    with pytest.raises(ManifestContractError, match="does not match"):
        create_paired_run_manifest(
            small_initialization,
            preparation_snapshot=preparation_snapshot,
            expected_preparation_checksum_record_sha256="0" * 64,
            preparation_authorization_version="synthetic-contract-test-v1",
            device="cpu",
            mps_repeatability_passed=None,
        )


def test_run_manifest_revalidates_immutable_candidate_snapshot_before_completion(
    small_initialization: PairedInitialization,
    preparation_snapshot: PreparationSnapshot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_path = (
        preparation_snapshot._candidate_root
        / "synthetic-artifacts"
        / "runtime.json"
    )
    original_content = runtime_path.read_bytes()
    original_validate = preparation_module.verify_preparation_snapshot
    calls = 0

    def mutate_after_first_validation(snapshot: PreparationSnapshot) -> None:
        nonlocal calls
        original_validate(snapshot)
        calls += 1
        if calls == 1:
            runtime_path.write_bytes(
                original_content.replace(
                    b'"runtime_identity"',
                    b'"runtime_identitY"',
                    1,
                )
            )
            os.chmod(runtime_path, 0o600)

    monkeypatch.setattr(
        preparation_module,
        "verify_preparation_snapshot",
        mutate_after_first_validation,
    )
    try:
        with pytest.raises(ManifestContractError, match="changed during"):
            _paired_run_manifest(
                small_initialization,
                preparation_snapshot,
            )
    finally:
        runtime_path.write_bytes(original_content)
        os.chmod(runtime_path, 0o600)


def test_strict_contracts_reject_unapproved_values(
    small_initialization: PairedInitialization,
) -> None:
    with pytest.raises(ManifestContractError, match="optimizer"):
        OptimizerContract(peak_learning_rate=2e-4)
    with pytest.raises(ManifestContractError, match="device policy"):
        DevicePolicyContract(small_mps_max_absolute_loss_difference=1.00001e-5)
    with pytest.raises(ManifestContractError, match="device policy"):
        DevicePolicyContract(small_mps_max_absolute_parameter_difference=1.00001e-5)
    with pytest.raises(ManifestContractError, match="factory-derived"):
        RunManifest()
    with pytest.raises(ManifestContractError, match="factory-derived"):
        PairedRunManifest()
    with pytest.raises(InitializationContractError, match="factory-derived"):
        PairedInitialization()
    for field in (
        "tokenizer_checksum_record_sha256",
        "corpus_checksum_record_sha256",
    ):
        with pytest.raises(TypeError):
            create_paired_run_manifest(
                small_initialization,
                preparation_snapshot=object(),
                expected_preparation_checksum_record_sha256="0" * 64,
                preparation_authorization_version="test-v1",
                device="cpu",
                mps_repeatability_passed=None,
                **{field: "0" * 64},
            )


def test_initialization_derivation_has_no_precomputed_scientific_inputs(
    small_initialization: PairedInitialization,
) -> None:
    assert not hasattr(initialization_module, "_build_initialization_manifest")
    parameters = inspect.signature(initialization_module._derive_initialization_manifest).parameters
    assert set(parameters) == {"models", "specification", "seed_plan"}
    with pytest.raises(TypeError):
        initialization_module._derive_initialization_manifest(
            small_initialization.models,
            NEU_SMALL,
            SMALL_FIRST_RUN_SEED_PLAN,
            initial_state_sha256="a" * 64,
        )


def test_fabricated_initialization_record_is_rejected_against_live_models(
    small_initialization: PairedInitialization,
    preparation_snapshot: PreparationSnapshot,
) -> None:
    legitimate = small_initialization.manifest
    fabricated = object.__new__(InitializationManifest)
    values = {
        "model_size": legitimate.model_size,
        "seed_plan": legitimate.seed_plan,
        "configuration_sha256": legitimate.configuration_sha256,
        "initial_state_sha256": "a" * 64,
        "trainable_parameter_count": legitimate.trainable_parameter_count,
        "conditions": legitimate.conditions,
        "implementation_versions": legitimate.implementation_versions,
        "tied_parameter_groups": legitimate.tied_parameter_groups,
    }
    for name, value in values.items():
        object.__setattr__(fabricated, name, value)
    fabricated._validate()

    lower_level_pair = object.__new__(PairedInitialization)
    object.__setattr__(lower_level_pair, "models", small_initialization.models)
    object.__setattr__(lower_level_pair, "manifest", fabricated)
    with pytest.raises(ManifestContractError, match="does not match its live models"):
        _paired_run_manifest(lower_level_pair, preparation_snapshot)


def test_fabricated_validation_record_cannot_replace_actual_validation_material(
    small_initialization: PairedInitialization,
    preparation_snapshot: PreparationSnapshot,
) -> None:
    fabricated = object.__new__(ValidationMaskRecord)
    values = {
        "condition": "CsCont",
        "seed": SMALL_FIRST_RUN_SEED_PLAN.validation_mask_seed,
        "example_count": 1,
        "policy_sha256": "a" * 64,
        "checksum_sha256": "b" * 64,
    }
    for name, value in values.items():
        object.__setattr__(fabricated, name, value)
    fabricated._validate()

    with pytest.raises(TypeError):
        create_paired_run_manifest(
            small_initialization,
            {"CsCont": fabricated},
            preparation_snapshot=preparation_snapshot,
            expected_preparation_checksum_record_sha256=(
                preparation_snapshot.candidate_checksum_record_sha256
            ),
            preparation_authorization_version="synthetic-contract-test-v1",
            device="cpu",
            mps_repeatability_passed=None,
        )
    with pytest.raises(TypeError):
        create_paired_run_manifest(
            small_initialization,
            preparation_snapshot=preparation_snapshot,
            expected_preparation_checksum_record_sha256=(
                preparation_snapshot.candidate_checksum_record_sha256
            ),
            preparation_authorization_version="synthetic-contract-test-v1",
            device="cpu",
            mps_repeatability_passed=None,
            validation_mask_record=fabricated,
        )


@pytest.mark.parametrize("mutation", ["parameter", "buffer"])
def test_run_manifest_factory_rejects_live_state_or_buffer_mutation(
    mutation: str,
    preparation_snapshot: PreparationSnapshot,
) -> None:
    paired = create_paired_initialization(NEU_TINY, TINY_SMOKE_SEED_PLANS[0])
    with torch.no_grad():
        for model in paired.models.values():
            if mutation == "parameter":
                next(model.parameters()).view(-1)[0] += 1
            else:
                buffers = dict(model.named_buffers())
                buffers["bert.embeddings.position_ids"][0, 0] = 1

    with pytest.raises(ManifestContractError, match="failed verification"):
        _paired_run_manifest(paired, preparation_snapshot)


def test_strict_derived_records_cannot_be_caller_constructed() -> None:
    with pytest.raises(InitializationContractError, match="must be derived"):
        InitializationManifest()
    with pytest.raises(MaskingContractError, match="must be derived"):
        ValidationMaskRecord()


def test_preparation_snapshot_subclass_cannot_override_verification() -> None:
    class FabricatedSnapshot(PreparationSnapshot):
        pass

    fabricated = object.__new__(FabricatedSnapshot)
    with pytest.raises(
        preparation_module.PreparationError,
        match="exact preparation snapshot",
    ):
        preparation_module.verify_preparation_snapshot(fabricated)


def test_future_contract_constants_remain_exact_without_fabricating_approval() -> None:
    assert APPROVED_BUDGET.optimizer_updates == 1_000
    assert APPROVED_BUDGET.projected_sequence_exposures == 64_000
    assert APPROVED_BUDGET.microbatch_sequences == 16
    assert APPROVED_BUDGET.gradient_accumulation_steps == 4
    assert APPROVED_BUDGET.diagnostic_checkpoint_updates == (0, 250, 500, 750)
    assert APPROVED_BUDGET.primary_checkpoint_update == 1_000
    assert APPROVED_BUDGET.fixed_mask_validation_interval == 100
    assert APPROVED_OPTIMIZER.peak_learning_rate == 1e-4
    assert APPROVED_DEVICE_POLICY.tiny_smoke_devices == ("cpu", "mps")
    assert APPROVED_DEVICE_POLICY.small_mps_reproducibility_updates == 10
    assert APPROVED_DEVICE_POLICY.small_mps_max_absolute_loss_difference == 1e-5
    assert APPROVED_DEVICE_POLICY.small_mps_max_absolute_parameter_difference == 1e-5
    assert APPROVED_DEVICE_POLICY.maximum_concurrent_conditions == 1


def test_synthetic_snapshot_cannot_create_future_run_manifest(
    small_initialization: PairedInitialization,
    synthetic_preparation_snapshot: SyntheticPreparationSnapshot,
) -> None:
    with pytest.raises(ManifestContractError, match="exact preparation snapshot"):
        create_paired_run_manifest(
            small_initialization,
            preparation_snapshot=synthetic_preparation_snapshot,
            expected_preparation_checksum_record_sha256="0" * 64,
            preparation_authorization_version="synthetic-test-v1",
            device="cpu",
            mps_repeatability_passed=None,
        )
