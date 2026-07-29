"""Typed future-run contracts and strict paired manifest structures."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterable, Literal, Mapping

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
from cslm.modeling.masking import (
    APPROVED_MASKING_POLICY,
    MaskingContractError,
    ValidationMaskRecord,
    build_validation_mask_record,
)
from cslm.modeling.packing import PackedSequence

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
    effective_batch_sequences: int = 64
    microbatch_sequences: int = 16
    gradient_accumulation_steps: int = 4
    maximum_sequence_length: int = MAX_SEQUENCE_LENGTH
    primary_checkpoint_update: int = 1_000
    diagnostic_checkpoint_updates: tuple[int, ...] = (0, 250, 500, 750)
    fixed_mask_validation_interval: int = 100
    condition_specific_early_stopping: bool = False

    def __post_init__(self) -> None:
        actual = (
            self.optimizer_updates,
            self.effective_batch_sequences,
            self.microbatch_sequences,
            self.gradient_accumulation_steps,
            self.maximum_sequence_length,
            self.primary_checkpoint_update,
            self.diagnostic_checkpoint_updates,
            self.fixed_mask_validation_interval,
            self.condition_specific_early_stopping,
        )
        expected = (1_000, 64, 16, 4, 128, 1_000, (0, 250, 500, 750), 100, False)
        if actual != expected:
            raise ManifestContractError("training budget differs from the approved policy")
        if self.microbatch_sequences * self.gradient_accumulation_steps != (
            self.effective_batch_sequences
        ):
            raise ManifestContractError(
                "microbatch and accumulation do not make the effective batch"
            )

    @property
    def projected_sequence_exposures(self) -> int:
        return self.optimizer_updates * self.effective_batch_sequences


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
    validation_mask_record: ValidationMaskRecord
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
        if (
            self.tokenizer_checksum_record_sha256
            != APPROVED_TOKENIZER_CHECKSUM_RECORD_SHA256
        ):
            raise ManifestContractError("run manifest uses an unapproved tokenizer record")
        if (
            self.corpus_checksum_record_sha256
            != APPROVED_CORPUS_CHECKSUM_RECORDS[self.condition]
        ):
            raise ManifestContractError("run manifest uses an unapproved corpus record")
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
        shared_fields = (
            "device",
            "mps_repeatability_passed",
            "tokenizer_checksum_record_sha256",
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
    validation_sequences_by_condition: Mapping[str, Iterable[PackedSequence]],
    *,
    device: Device,
    mps_repeatability_passed: bool | None,
) -> PairedRunManifest:
    """Verify live models and validation material before deriving four run records."""
    if not isinstance(paired_initialization, PairedInitialization):
        raise ManifestContractError("run construction requires a paired initialization")
    if not isinstance(paired_initialization.manifest, InitializationManifest):
        raise ManifestContractError("paired initialization lacks a derived manifest")

    try:
        paired_initialization.manifest._validate()
        specification = approved_model_specification(
            paired_initialization.manifest.model_size
        )
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
        raise ManifestContractError(
            "paired initialization manifest does not match its live models"
        )

    if set(validation_sequences_by_condition) != set(CONDITIONS):
        raise ManifestContractError(
            "run construction requires validation material for all four conditions"
        )

    runs: list[RunManifest] = []
    for condition in CONDITIONS:
        try:
            validation_record = build_validation_mask_record(
                validation_sequences_by_condition[condition],
                seed=derived_initialization.seed_plan.validation_mask_seed,
                policy=APPROVED_MASKING_POLICY,
            )
        except (KeyError, MaskingContractError, TypeError) as exc:
            raise ManifestContractError(
                "validation material failed deterministic derivation"
            ) from exc

        run = object.__new__(RunManifest)
        values = {
            "condition": condition,
            "initialization": derived_initialization,
            "device": device,
            "mps_repeatability_passed": mps_repeatability_passed,
            "tokenizer_checksum_record_sha256": (
                APPROVED_TOKENIZER_CHECKSUM_RECORD_SHA256
            ),
            "corpus_checksum_record_sha256": APPROVED_CORPUS_CHECKSUM_RECORDS[
                condition
            ],
            "validation_mask_record": validation_record,
            "optimizer": APPROVED_OPTIMIZER,
            "budget": APPROVED_BUDGET,
            "device_policy": APPROVED_DEVICE_POLICY,
        }
        for name, value in values.items():
            object.__setattr__(run, name, value)
        run._validate()
        runs.append(run)

    paired = object.__new__(PairedRunManifest)
    object.__setattr__(paired, "runs", tuple(runs))
    paired._validate()
    return paired
