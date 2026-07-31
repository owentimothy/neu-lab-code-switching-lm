"""Typed future-run contracts and strict paired manifest structures."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from types import MappingProxyType, ModuleType
from typing import TYPE_CHECKING, Literal

from cslm.modeling.config import (
    CONDITIONS,
    MAX_SEQUENCE_LENGTH,
    ModelContractError,
    ModelSize,
    approved_model_specification,
)
from cslm.modeling.initialization import (
    InitializationContractError,
    InitializationManifest,
    PairedInitialization,
    ReplicateSeedPlan,
    _derive_initialization_manifest,
)
from cslm.modeling.masking import ValidationMaskRecord

if TYPE_CHECKING:
    from cslm.modeling.preparation import PreparationSnapshot

Device = Literal["cpu", "mps"]


class ManifestContractError(RuntimeError):
    """A future training or run-manifest invariant was violated."""


APPROVED_TOKENIZER_CHECKSUM_RECORD_SHA256 = (
    "25489e732b64ce63c0380012ea719571f9cb4fc6c369e43da920d2b45af55b8d"
)
APPROVED_CALLHOME_CHECKSUM_RECORD_SHA256 = (
    "840236bdd4c8f3d18898b02c824478dfbb663f160bc03d13590ae5ca4dc8003f"
)
APPROVED_CSCONT_CHECKSUM_RECORD_SHA256 = (
    "f06216f6588337c53100cf6066166f4979b3b06fe0f8a65c04e350fd8fcb0b3e"
)
APPROVED_CORPUS_CHECKSUM_RECORDS = MappingProxyType(
    {
        "EnglishMono": APPROVED_CALLHOME_CHECKSUM_RECORD_SHA256,
        "SpanishMono": APPROVED_CALLHOME_CHECKSUM_RECORD_SHA256,
        "MonoCont": APPROVED_CALLHOME_CHECKSUM_RECORD_SHA256,
        "CsCont": APPROVED_CSCONT_CHECKSUM_RECORD_SHA256,
    }
)


@dataclass(frozen=True)
class OptimizerContract:
    name: str = "AdamW"
    peak_learning_rate: float = 1e-4
    beta1: float = 0.9
    beta2: float = 0.999
    epsilon: float = 1e-8
    weight_decay: float = 0.01
    gradient_clipping: float = 1.0
    warmup_updates: int = 100
    schedule: str = "linear_decay_to_zero"
    decay_end_update: int = 1_000

    def __post_init__(self) -> None:
        actual = (
            self.name,
            self.peak_learning_rate,
            self.beta1,
            self.beta2,
            self.epsilon,
            self.weight_decay,
            self.gradient_clipping,
            self.warmup_updates,
            self.schedule,
            self.decay_end_update,
        )
        expected = ("AdamW", 1e-4, 0.9, 0.999, 1e-8, 0.01, 1.0, 100, "linear_decay_to_zero", 1_000)
        if actual != expected:
            raise ManifestContractError("optimizer contract differs from the approved policy")


@dataclass(frozen=True)
class TrainingBudgetContract:
    optimizer_updates: int = 1_000
    nominal_eligible_appearances: int = 746_000
    eligible_frontier_per_update: int = 746
    maximum_microbatch_sequences: int = 16
    minimum_microbatches_per_update: int = 1
    maximum_microbatches_per_update: int = 6
    maximum_sequence_length: int = MAX_SEQUENCE_LENGTH
    primary_checkpoint_update: int = 1_000
    diagnostic_checkpoint_updates: tuple[int, ...] = (0, 250, 500, 750)
    fixed_mask_validation_interval: int = 100
    condition_specific_early_stopping: bool = False

    def __post_init__(self) -> None:
        actual = (
            self.optimizer_updates,
            self.nominal_eligible_appearances,
            self.eligible_frontier_per_update,
            self.maximum_microbatch_sequences,
            self.minimum_microbatches_per_update,
            self.maximum_microbatches_per_update,
            self.maximum_sequence_length,
            self.primary_checkpoint_update,
            self.diagnostic_checkpoint_updates,
            self.fixed_mask_validation_interval,
            self.condition_specific_early_stopping,
        )
        expected = (
            1_000,
            746_000,
            746,
            16,
            1,
            6,
            128,
            1_000,
            (0, 250, 500, 750),
            100,
            False,
        )
        exact_integer_fields = (
            self.optimizer_updates,
            self.nominal_eligible_appearances,
            self.eligible_frontier_per_update,
            self.maximum_microbatch_sequences,
            self.minimum_microbatches_per_update,
            self.maximum_microbatches_per_update,
            self.maximum_sequence_length,
            self.primary_checkpoint_update,
            self.fixed_mask_validation_interval,
        )
        if (
            actual != expected
            or any(type(value) is not int for value in exact_integer_fields)
            or any(
                type(value) is not int
                for value in self.diagnostic_checkpoint_updates
            )
        ):
            raise ManifestContractError("training budget differs from the approved policy")
        if self.optimizer_updates * self.eligible_frontier_per_update != (
            self.nominal_eligible_appearances
        ):
            raise ManifestContractError(
                "eligible update frontiers do not reach the nominal target"
            )

    @property
    def projected_sequence_exposures(self) -> int:
        """Legacy all-non-padding projection scale retained as a diagnostic only."""

        return 64_000

    @property
    def microbatch_sequences(self) -> int:
        """Compatibility alias for the maximum sequence count."""

        return self.maximum_microbatch_sequences


@dataclass(frozen=True)
class DevicePolicyContract:
    tiny_smoke_devices: tuple[Device, ...] = ("cpu", "mps")
    small_mps_reproducibility_updates: int = 10
    small_mps_max_absolute_loss_difference: float = 1e-5
    small_mps_max_absolute_parameter_difference: float = 1e-5
    paired_pilot_requires_mps_repeatability_pass: bool = True
    fallback_device: Device = "cpu"
    mix_devices_within_pair: bool = False
    maximum_concurrent_conditions: int = 1

    def __post_init__(self) -> None:
        actual = (
            self.tiny_smoke_devices,
            self.small_mps_reproducibility_updates,
            self.small_mps_max_absolute_loss_difference,
            self.small_mps_max_absolute_parameter_difference,
            self.paired_pilot_requires_mps_repeatability_pass,
            self.fallback_device,
            self.mix_devices_within_pair,
            self.maximum_concurrent_conditions,
        )
        expected = (("cpu", "mps"), 10, 1e-5, 1e-5, True, "cpu", False, 1)
        if actual != expected:
            raise ManifestContractError("device policy differs from the approved contract")


APPROVED_OPTIMIZER = OptimizerContract()
APPROVED_BUDGET = TrainingBudgetContract()
APPROVED_DEVICE_POLICY = DevicePolicyContract()


@dataclass(frozen=True, init=False)
class RunManifest:
    """Strict record for one future condition run; this gate does not execute it."""

    condition: str
    initialization: InitializationManifest
    device: Device
    mps_repeatability_passed: bool | None
    tokenizer_checksum_record_sha256: str
    corpus_checksum_record_sha256: str
    expected_approved_preparation_checksum_record_sha256: str
    verified_candidate_checksum_record_sha256: str
    preparation_authorization_version: str
    preparation_identity_matches: bool
    preparation_manifest_sha256: str
    training_schedule_plan_identity_sha256: str
    training_schedule_identity_sha256: str
    training_mask_seed: int
    training_seed_audit_evidence_sha256: str
    resume_policy_protocol: str
    validation_mask_record: ValidationMaskRecord
    validation_artifact_identities: tuple[tuple[str, str], ...]
    optimizer: OptimizerContract = APPROVED_OPTIMIZER
    budget: TrainingBudgetContract = APPROVED_BUDGET
    device_policy: DevicePolicyContract = APPROVED_DEVICE_POLICY

    def __new__(cls) -> RunManifest:
        raise ManifestContractError("run manifests must be factory-derived")

    def _validate(self) -> None:
        if self.condition not in CONDITIONS:
            raise ManifestContractError("unknown run condition")
        if not isinstance(self.initialization, InitializationManifest):
            raise ManifestContractError("run lacks a derived initialization manifest")
        self.initialization._validate()
        if self.device not in {"cpu", "mps"}:
            raise ManifestContractError("unsupported device")
        if self.tokenizer_checksum_record_sha256 != APPROVED_TOKENIZER_CHECKSUM_RECORD_SHA256:
            raise ManifestContractError("run manifest uses an unapproved tokenizer record")
        if self.corpus_checksum_record_sha256 != APPROVED_CORPUS_CHECKSUM_RECORDS[self.condition]:
            raise ManifestContractError("run manifest uses an unapproved corpus record")
        for identity in (
            self.expected_approved_preparation_checksum_record_sha256,
            self.verified_candidate_checksum_record_sha256,
            self.preparation_manifest_sha256,
            self.training_schedule_plan_identity_sha256,
            self.training_schedule_identity_sha256,
            self.training_seed_audit_evidence_sha256,
        ):
            if not isinstance(identity, str) or len(identity) != 64 or any(
                character not in "0123456789abcdef" for character in identity
            ):
                raise ManifestContractError("run manifest lacks a candidate checksum identity")
        if (
            not isinstance(self.preparation_authorization_version, str)
            or not self.preparation_authorization_version.strip()
            or self.preparation_identity_matches is not True
            or self.expected_approved_preparation_checksum_record_sha256
            != self.verified_candidate_checksum_record_sha256
        ):
            raise ManifestContractError(
                "externally expected and internally verified preparation identities differ"
            )
        if (
            self.training_mask_seed
            != self.initialization.seed_plan.training_mask_seed
            or self.resume_policy_protocol
            != "neu_option2_update_boundary_resume_v1"
        ):
            raise ManifestContractError(
                "run training schedule seed or resume policy is invalid"
            )
        if not isinstance(self.validation_mask_record, ValidationMaskRecord):
            raise ManifestContractError("run lacks a derived validation mask record")
        self.validation_mask_record._validate()
        if (
            self.validation_mask_record.condition != self.condition
            or self.validation_mask_record.seed
            != self.initialization.seed_plan.validation_mask_seed
        ):
            raise ManifestContractError(
                "validation mask record does not match the run condition and seed"
            )
        if (
            len(self.validation_artifact_identities) != 6
            or len({name for name, _ in self.validation_artifact_identities}) != 6
            or any(
                not name.startswith(f"validation/{self.condition}/")
                or len(identity) != 64
                or any(character not in "0123456789abcdef" for character in identity)
                for name, identity in self.validation_artifact_identities
            )
        ):
            raise ManifestContractError(
                "run manifest lacks exact verified validation artifact identities"
            )
        if self.device == "mps" and self.model_size is ModelSize.SMALL:
            if self.mps_repeatability_passed is not True:
                raise ManifestContractError("Small MPS run lacks a passed repeatability gate")
        elif self.mps_repeatability_passed is not None:
            raise ManifestContractError("MPS repeatability status is inapplicable to this run")

    @property
    def model_size(self) -> ModelSize:
        return self.initialization.model_size

    @property
    def seed_plan(self) -> ReplicateSeedPlan:
        return self.initialization.seed_plan

    @property
    def configuration_sha256(self) -> str:
        return self.initialization.configuration_sha256

    @property
    def initial_state_sha256(self) -> str:
        return self.initialization.initial_state_sha256

    @property
    def validation_mask_checksum_sha256(self) -> str:
        return self.validation_mask_record.checksum_sha256


@dataclass(frozen=True, init=False)
class PairedRunManifest:
    """Four-condition comparison enforcing shared initialization and device policy."""

    runs: tuple[RunManifest, ...]

    def __new__(cls) -> PairedRunManifest:
        raise ManifestContractError("paired run manifests must be factory-derived")

    def _validate(self) -> None:
        if tuple(run.condition for run in self.runs) != CONDITIONS:
            raise ManifestContractError("paired manifest must contain the four conditions in order")
        reference = self.runs[0]
        if any(run.initialization is not reference.initialization for run in self.runs[1:]):
            raise ManifestContractError(
                "paired runs do not derive from one initialization manifest"
            )
        if len(
            {
                run.training_schedule_identity_sha256
                for run in self.runs
            }
        ) != len(CONDITIONS):
            raise ManifestContractError(
                "condition training schedule identities are not separated"
            )
        shared_fields = (
            "device",
            "mps_repeatability_passed",
            "tokenizer_checksum_record_sha256",
            "expected_approved_preparation_checksum_record_sha256",
            "verified_candidate_checksum_record_sha256",
            "preparation_authorization_version",
            "preparation_identity_matches",
            "preparation_manifest_sha256",
            "training_schedule_plan_identity_sha256",
            "training_mask_seed",
            "training_seed_audit_evidence_sha256",
            "resume_policy_protocol",
            "optimizer",
            "budget",
            "device_policy",
        )
        for run in self.runs[1:]:
            if any(getattr(run, field) != getattr(reference, field) for field in shared_fields):
                raise ManifestContractError(
                    "paired runs differ in initialization, tokenizer, budget, or device"
                )


def create_paired_run_manifest(
    paired_initialization: PairedInitialization,
    *,
    preparation_snapshot: PreparationSnapshot,
    expected_preparation_checksum_record_sha256: str,
    preparation_authorization_version: str,
    device: Device,
    mps_repeatability_passed: bool | None,
) -> PairedRunManifest:
    """Bind future runs to an externally supplied identity after internal verification."""
    from cslm.modeling.preparation import (
        PREPARATION_PROTOCOL_VERSION,
        PreparationError,
        PreparationSnapshot,
        candidate_validation_for,
        verify_preparation_snapshot,
    )

    if type(preparation_snapshot) is not PreparationSnapshot:
        raise ManifestContractError("run construction requires an exact preparation snapshot")
    snapshot_failed = False
    try:
        verify_preparation_snapshot(preparation_snapshot)
    except PreparationError:
        snapshot_failed = True
    if snapshot_failed:
        raise ManifestContractError("preparation candidate failed internal verification")
    if (
        preparation_snapshot.status != "candidate_unapproved"
        or preparation_snapshot.protocol_version
        != PREPARATION_PROTOCOL_VERSION
    ):
        raise ManifestContractError(
            "run construction requires an unapproved production candidate snapshot"
        )
    if (
        not isinstance(expected_preparation_checksum_record_sha256, str)
        or expected_preparation_checksum_record_sha256
        != preparation_snapshot.candidate_checksum_record_sha256
    ):
        raise ManifestContractError(
            "expected preparation checksum identity does not match the verified candidate"
        )
    if (
        not isinstance(preparation_authorization_version, str)
        or not preparation_authorization_version.strip()
    ):
        raise ManifestContractError("preparation authorization version is required")
    if not isinstance(paired_initialization, PairedInitialization):
        raise ManifestContractError("run construction requires a paired initialization")
    if not isinstance(paired_initialization.manifest, InitializationManifest):
        raise ManifestContractError("paired initialization lacks a derived manifest")

    try:
        paired_initialization.manifest._validate()
        specification = approved_model_specification(paired_initialization.manifest.model_size)
        derived_initialization = _derive_initialization_manifest(
            paired_initialization.models,
            specification,
            paired_initialization.manifest.seed_plan,
        )
    except (
        AttributeError,
        InitializationContractError,
        ModelContractError,
        TypeError,
    ) as exc:
        raise ManifestContractError(
            "paired initialization failed verification against its live models"
        ) from exc
    if derived_initialization != paired_initialization.manifest:
        raise ManifestContractError("paired initialization manifest does not match its live models")

    runs: list[RunManifest] = []
    seed_audit_evidence = {
        seed: evidence
        for _, seed, evidence in (
            preparation_snapshot.training_seed_audit_evidence
        )
    }
    for condition in CONDITIONS:
        validation_failed = False
        try:
            validation_snapshot = candidate_validation_for(
                preparation_snapshot,
                condition,
                derived_initialization.seed_plan.validation_mask_seed,
            )
        except PreparationError:
            validation_snapshot = None
            validation_failed = True
        if validation_failed or validation_snapshot is None:
            raise ManifestContractError("verified validation snapshot is unavailable")

        run = object.__new__(RunManifest)
        schedule_identities = dict(
            preparation_snapshot.schedule_identities_by_condition
        )
        if (
            set(schedule_identities) != set(CONDITIONS)
            or derived_initialization.seed_plan.training_mask_seed
            not in {
                seed
                for _, seed in (
                    preparation_snapshot.approved_training_mask_seeds
                )
            }
            or derived_initialization.seed_plan.training_mask_seed
            not in seed_audit_evidence
        ):
            raise ManifestContractError(
                "verified training schedule snapshot is unavailable"
            )
        values = {
            "condition": condition,
            "initialization": derived_initialization,
            "device": device,
            "mps_repeatability_passed": mps_repeatability_passed,
            "tokenizer_checksum_record_sha256": (APPROVED_TOKENIZER_CHECKSUM_RECORD_SHA256),
            "corpus_checksum_record_sha256": APPROVED_CORPUS_CHECKSUM_RECORDS[condition],
            "expected_approved_preparation_checksum_record_sha256": (
                expected_preparation_checksum_record_sha256
            ),
            "verified_candidate_checksum_record_sha256": (
                preparation_snapshot.candidate_checksum_record_sha256
            ),
            "preparation_authorization_version": preparation_authorization_version,
            "preparation_identity_matches": True,
            "preparation_manifest_sha256": (
                preparation_snapshot.preparation_manifest_sha256
            ),
            "training_schedule_plan_identity_sha256": (
                preparation_snapshot.schedule_plan_identity_sha256
            ),
            "training_schedule_identity_sha256": (
                schedule_identities[condition]
            ),
            "training_mask_seed": (
                derived_initialization.seed_plan.training_mask_seed
            ),
            "training_seed_audit_evidence_sha256": seed_audit_evidence[
                derived_initialization.seed_plan.training_mask_seed
            ],
            "resume_policy_protocol": (
                preparation_snapshot.resume_policy_protocol
            ),
            "validation_mask_record": validation_snapshot.record,
            "validation_artifact_identities": (
                validation_snapshot.artifact_identities
            ),
            "optimizer": APPROVED_OPTIMIZER,
            "budget": APPROVED_BUDGET,
            "device_policy": APPROVED_DEVICE_POLICY,
        }
        for name, value in values.items():
            object.__setattr__(run, name, value)
        run._validate()
        runs.append(run)

    final_snapshot_failed = False
    try:
        verify_preparation_snapshot(preparation_snapshot)
    except PreparationError:
        final_snapshot_failed = True
    if final_snapshot_failed:
        raise ManifestContractError(
            "preparation candidate changed during run-manifest construction"
        )
    paired = object.__new__(PairedRunManifest)
    object.__setattr__(paired, "runs", tuple(runs))
    paired._validate()
    return paired


def _install_reviewed_dependency_capsule() -> None:
    """Retain first-execution definitions independently of module aliases."""

    reviewed_namespace = MappingProxyType(dict(globals()))
    capsule = MappingProxyType(
        {"module": __name__, "namespace": reviewed_namespace}
    )

    class _ReviewedDependencyModule(ModuleType):
        def __getattribute__(self, name: str) -> object:
            if name == "_REVIEWED_DEPENDENCY_CAPSULE":
                return capsule
            return ModuleType.__getattribute__(self, name)

    sys.modules[__name__].__class__ = _ReviewedDependencyModule


_install_reviewed_dependency_capsule()
del _install_reviewed_dependency_capsule
