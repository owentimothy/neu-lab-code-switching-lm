"""Paired BERT initialization and strict in-memory copying controls."""

from __future__ import annotations

import copy
import hashlib
import importlib.metadata
import json
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping

import numpy as np
import torch
from transformers import BertForMaskedLM

from cslm.modeling.config import (
    CONDITIONS,
    NUMPY_VERSION,
    TOKENIZERS_VERSION,
    TORCH_VERSION,
    TRANSFORMERS_VERSION,
    ModelSize,
    ModelSpecification,
    approved_model_specification,
    validate_model,
)


class InitializationContractError(RuntimeError):
    """An initialization, copy, version, or tying invariant was violated."""


_APPROVED_TIED_PARAMETER_GROUPS = (
    (
        "bert.embeddings.word_embeddings.weight",
        "cls.predictions.decoder.weight",
    ),
    (
        "cls.predictions.bias",
        "cls.predictions.decoder.bias",
    ),
)


@dataclass(frozen=True)
class ReplicateSeedPlan:
    """Independent explicit seeds for initialization, train masks, and validation masks."""

    model_seed: int
    training_mask_seed: int
    validation_mask_seed: int

    def __post_init__(self) -> None:
        values = (self.model_seed, self.training_mask_seed, self.validation_mask_seed)
        if any(not isinstance(value, int) or value < 0 for value in values):
            raise InitializationContractError("replicate seeds must be non-negative integers")
        if len(set(values)) != len(values):
            raise InitializationContractError(
                "initialization and masking seeds must be independent"
            )


TINY_SMOKE_SEED_PLANS = (ReplicateSeedPlan(1_729, 11_729, 21_729),)
SMALL_FIRST_RUN_SEED_PLAN = ReplicateSeedPlan(271_828, 281_828, 291_828)
SMALL_PILOT_SEED_PLANS = (
    SMALL_FIRST_RUN_SEED_PLAN,
    ReplicateSeedPlan(314_159, 324_159, 334_159),
    ReplicateSeedPlan(161_803, 171_803, 181_803),
)


@dataclass(frozen=True, init=False)
class InitializationManifest:
    """Checksum record for one paired four-condition initialization."""

    model_size: ModelSize
    seed_plan: ReplicateSeedPlan
    configuration_sha256: str
    initial_state_sha256: str
    trainable_parameter_count: int
    conditions: tuple[str, ...]
    implementation_versions: tuple[tuple[str, str], ...]
    tied_parameter_groups: tuple[tuple[str, ...], ...]

    def __new__(cls) -> InitializationManifest:
        raise InitializationContractError("initialization manifests must be derived")

    def _validate(self) -> None:
        if not isinstance(self.model_size, ModelSize) or not isinstance(
            self.seed_plan, ReplicateSeedPlan
        ):
            raise InitializationContractError("initialization manifest has invalid typed fields")
        specification = approved_model_specification(self.model_size)
        if self.configuration_sha256 != specification.configuration_sha256():
            raise InitializationContractError("initialization configuration checksum mismatch")
        if (
            len(self.initial_state_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.initial_state_sha256
            )
        ):
            raise InitializationContractError("initialization state checksum is invalid")
        if self.trainable_parameter_count != specification.expected_trainable_parameters:
            raise InitializationContractError("initialization parameter count mismatch")
        if self.conditions != CONDITIONS:
            raise InitializationContractError("initialization conditions mismatch")
        expected_versions = {
            "numpy": NUMPY_VERSION,
            "tokenizers": TOKENIZERS_VERSION,
            "torch": TORCH_VERSION,
            "transformers": TRANSFORMERS_VERSION,
        }
        if dict(self.implementation_versions) != expected_versions:
            raise InitializationContractError("initialization implementation versions mismatch")
        if self.tied_parameter_groups != _APPROVED_TIED_PARAMETER_GROUPS:
            raise InitializationContractError("initialization tying fingerprint mismatch")

    @property
    def model_seed(self) -> int:
        return self.seed_plan.model_seed


def _derive_initialization_manifest(
    models: Mapping[str, BertForMaskedLM],
    specification: ModelSpecification,
    seed_plan: ReplicateSeedPlan,
) -> InitializationManifest:
    """Derive a manifest only from a strictly verified live paired initialization."""
    if tuple(models) != CONDITIONS or set(models) != set(CONDITIONS):
        raise InitializationContractError("paired initialization has wrong condition membership")

    reference = models[CONDITIONS[0]]
    trainable_parameter_count = validate_model(reference, specification)
    configuration_sha256 = specification.configuration_sha256()
    state_sha256 = initial_state_sha256(reference)
    verify_identical_initial_states(
        models,
        specification,
        expected_configuration_sha256=configuration_sha256,
        expected_state_sha256=state_sha256,
    )

    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed_plan.model_seed)
        seeded_reference = BertForMaskedLM(specification.to_bert_config())
    validate_model(seeded_reference, specification)
    if initial_state_sha256(seeded_reference) != state_sha256:
        raise InitializationContractError(
            "paired initialization does not match the recorded model seed"
        )

    manifest = object.__new__(InitializationManifest)
    values = {
        "model_size": specification.name,
        "seed_plan": seed_plan,
        "configuration_sha256": configuration_sha256,
        "initial_state_sha256": state_sha256,
        "trainable_parameter_count": trainable_parameter_count,
        "conditions": tuple(models),
        "implementation_versions": tuple(sorted(_runtime_versions().items())),
        "tied_parameter_groups": tied_parameter_groups(reference),
    }
    for name, value in values.items():
        object.__setattr__(manifest, name, value)
    manifest._validate()
    return manifest


@dataclass(frozen=True, init=False)
class PairedInitialization:
    """Four independent model objects copied exactly from one realization."""

    models: Mapping[str, BertForMaskedLM] = field(repr=False)
    manifest: InitializationManifest

    def __new__(cls) -> PairedInitialization:
        raise InitializationContractError("paired initializations must be factory-derived")


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _runtime_versions() -> dict[str, str]:
    versions = {
        "numpy": importlib.metadata.version("numpy"),
        "tokenizers": importlib.metadata.version("tokenizers"),
        "torch": importlib.metadata.version("torch"),
        "transformers": importlib.metadata.version("transformers"),
    }
    expected = {
        "numpy": NUMPY_VERSION,
        "tokenizers": TOKENIZERS_VERSION,
        "torch": TORCH_VERSION,
        "transformers": TRANSFORMERS_VERSION,
    }
    if versions != expected:
        raise InitializationContractError("model runtime does not match the pinned dependency set")
    if np.__version__ != NUMPY_VERSION:
        raise InitializationContractError("NumPy runtime differs from the pinned dependency")
    return versions


def _named_parameters(model: BertForMaskedLM) -> tuple[tuple[str, torch.nn.Parameter], ...]:
    return tuple(sorted(model.named_parameters(remove_duplicate=False), key=lambda item: item[0]))


def _named_buffers(model: BertForMaskedLM) -> tuple[tuple[str, torch.Tensor], ...]:
    return tuple(sorted(model.named_buffers(remove_duplicate=False), key=lambda item: item[0]))


def tied_parameter_groups(model: BertForMaskedLM) -> tuple[tuple[str, ...], ...]:
    """Return a name-only alias fingerprint; memory addresses never enter manifests."""
    aliases: dict[tuple[str, int], list[str]] = {}
    for name, parameter in _named_parameters(model):
        key = (str(parameter.device), parameter.untyped_storage().data_ptr())
        aliases.setdefault(key, []).append(name)
    return tuple(
        sorted(tuple(sorted(names)) for names in aliases.values() if len(names) > 1)
    )


def _update_tensor_hash(
    digest: Any,
    *,
    kind: str,
    name: str,
    tensor: torch.Tensor,
    requires_grad: bool | None,
) -> None:
    metadata = {
        "dtype": str(tensor.dtype),
        "kind": kind,
        "name": name,
        "shape": list(tensor.shape),
    }
    if requires_grad is not None:
        metadata["requires_grad"] = requires_grad
    digest.update(_canonical_json_bytes(metadata))
    array = tensor.detach().cpu().contiguous().numpy()
    if array.dtype.byteorder == ">":
        array = array.byteswap().newbyteorder("<")
    digest.update(array.tobytes(order="C"))


def initial_state_sha256(model: BertForMaskedLM) -> str:
    """Hash every parameter and buffer plus trainability and tying metadata."""
    digest = hashlib.sha256()
    for name, parameter in _named_parameters(model):
        _update_tensor_hash(
            digest,
            kind="parameter",
            name=name,
            tensor=parameter,
            requires_grad=parameter.requires_grad,
        )
    for name, buffer in _named_buffers(model):
        _update_tensor_hash(
            digest,
            kind="buffer",
            name=name,
            tensor=buffer,
            requires_grad=None,
        )
    digest.update(_canonical_json_bytes({"tied_parameter_groups": tied_parameter_groups(model)}))
    return digest.hexdigest()


def verify_identical_initial_states(
    models: Mapping[str, BertForMaskedLM],
    specification: ModelSpecification,
    *,
    expected_configuration_sha256: str,
    expected_state_sha256: str,
) -> None:
    """Fail on any condition, config, name, shape, dtype, value, tying, or hash mismatch."""
    if tuple(models) != CONDITIONS or set(models) != set(CONDITIONS):
        raise InitializationContractError("paired initialization has wrong condition membership")
    if specification.configuration_sha256() != expected_configuration_sha256:
        raise InitializationContractError("configuration checksum mismatch")

    if len({id(model) for model in models.values()}) != len(CONDITIONS):
        raise InitializationContractError("conditions must receive pairwise-distinct model objects")

    reference = models[CONDITIONS[0]]
    validate_model(reference, specification)
    reference_parameters = _named_parameters(reference)
    reference_buffers = _named_buffers(reference)
    reference_ties = tied_parameter_groups(reference)
    if reference_ties != _APPROVED_TIED_PARAMETER_GROUPS:
        raise InitializationContractError("reference model has unapproved parameter tying")

    storage_owners: dict[tuple[str, int], str] = {}
    for condition, model in models.items():
        for _, parameter in _named_parameters(model):
            storage_key = (str(parameter.device), parameter.untyped_storage().data_ptr())
            owner = storage_owners.setdefault(storage_key, condition)
            if owner != condition:
                raise InitializationContractError(
                    "parameter storage is shared across conditions"
                )

    for condition in CONDITIONS:
        model = models[condition]
        validate_model(model, specification)
        parameters = _named_parameters(model)
        if len(parameters) != len(reference_parameters):
            raise InitializationContractError("parameter count mismatch across condition copies")
        for (reference_name, reference_parameter), (name, parameter) in zip(
            reference_parameters, parameters, strict=True
        ):
            if reference_name != name:
                raise InitializationContractError("parameter name mismatch across condition copies")
            if reference_parameter.shape != parameter.shape:
                raise InitializationContractError(
                    "parameter shape mismatch across condition copies"
                )
            if reference_parameter.dtype != parameter.dtype:
                raise InitializationContractError(
                    "parameter dtype mismatch across condition copies"
                )
            if reference_parameter.requires_grad != parameter.requires_grad:
                raise InitializationContractError(
                    "parameter trainability mismatch across condition copies"
                )
            if not torch.equal(reference_parameter.detach(), parameter.detach()):
                raise InitializationContractError(
                    "parameter value mismatch across condition copies"
                )
        buffers = _named_buffers(model)
        if len(buffers) != len(reference_buffers):
            raise InitializationContractError("buffer count mismatch across condition copies")
        for (reference_name, reference_buffer), (name, buffer) in zip(
            reference_buffers, buffers, strict=True
        ):
            if reference_name != name:
                raise InitializationContractError("buffer name mismatch across condition copies")
            if reference_buffer.shape != buffer.shape:
                raise InitializationContractError("buffer shape mismatch across condition copies")
            if reference_buffer.dtype != buffer.dtype:
                raise InitializationContractError("buffer dtype mismatch across condition copies")
            if not torch.equal(reference_buffer.detach(), buffer.detach()):
                raise InitializationContractError("buffer value mismatch across condition copies")
        if tied_parameter_groups(model) != reference_ties:
            raise InitializationContractError("parameter tying mismatch across condition copies")
        if initial_state_sha256(model) != expected_state_sha256:
            raise InitializationContractError("initial-state checksum mismatch")


def create_paired_initialization(
    specification: ModelSpecification,
    seed_plan: ReplicateSeedPlan,
) -> PairedInitialization:
    """Create one random realization and exact independent copies for four conditions."""
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed_plan.model_seed)
        reference = BertForMaskedLM(specification.to_bert_config())
    models = {condition: copy.deepcopy(reference) for condition in CONDITIONS}
    manifest = _derive_initialization_manifest(
        models,
        specification,
        seed_plan=seed_plan,
    )
    paired = object.__new__(PairedInitialization)
    object.__setattr__(paired, "models", MappingProxyType(models))
    object.__setattr__(paired, "manifest", manifest)
    return paired
