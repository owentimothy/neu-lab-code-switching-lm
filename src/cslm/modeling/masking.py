"""Seeded token-level MLM masking with dynamic train and fixed validation modes."""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field
from types import MappingProxyType, ModuleType
from typing import Any, Iterable, Literal

from cslm.modeling.config import (
    CONDITIONS,
    MASK_TOKEN_ID,
    SPECIAL_TOKEN_IDS,
    VOCAB_SIZE,
)
from cslm.modeling.eligibility import derive_mask_eligibility
from cslm.modeling.packing import PackedSequence

MaskingMode = Literal["train", "validation"]
ReplacementKind = Literal["mask", "random", "unchanged"]
IGNORE_INDEX = -100


class MaskingContractError(RuntimeError):
    """An MLM masking invariant was violated."""


@dataclass(frozen=True)
class MaskingPolicy:
    probability: float = 0.15
    mask_fraction: float = 0.80
    random_fraction: float = 0.10
    unchanged_fraction: float = 0.10
    vocabulary_size: int = VOCAB_SIZE
    special_token_ids: frozenset[int] = SPECIAL_TOKEN_IDS

    def __post_init__(self) -> None:
        if (
            self.probability != 0.15
            or self.mask_fraction != 0.80
            or self.random_fraction != 0.10
            or self.unchanged_fraction != 0.10
            or self.vocabulary_size != VOCAB_SIZE
            or self.special_token_ids != SPECIAL_TOKEN_IDS
        ):
            raise MaskingContractError("masking policy differs from the approved contract")


APPROVED_MASKING_POLICY = MaskingPolicy()


def _policy_payload(policy: MaskingPolicy) -> dict[str, Any]:
    return {
        "probability": policy.probability,
        "mask_fraction": policy.mask_fraction,
        "random_fraction": policy.random_fraction,
        "unchanged_fraction": policy.unchanged_fraction,
        "vocabulary_size": policy.vocabulary_size,
        "special_token_ids": sorted(policy.special_token_ids),
    }


@dataclass(frozen=True)
class MaskedExample:
    """One deterministic masking realization and checksum-recordable metadata."""

    input_ids: tuple[int, ...] = field(repr=False)
    labels: tuple[int, ...] = field(repr=False)
    selected_positions: tuple[int, ...] = field(repr=False)
    replacement_kinds: tuple[ReplacementKind, ...]
    checksum_sha256: str

    def __post_init__(self) -> None:
        if len(self.input_ids) != len(self.labels):
            raise MaskingContractError("masked inputs and labels have different lengths")
        if len(self.selected_positions) != len(self.replacement_kinds):
            raise MaskingContractError("masking target metadata does not reconcile")


@dataclass(frozen=True, init=False)
class ValidationMaskRecord:
    """Derived checksum record for one ordered, fixed validation set."""

    condition: str
    seed: int
    example_count: int
    policy_sha256: str
    checksum_sha256: str

    def __new__(cls) -> ValidationMaskRecord:
        raise MaskingContractError("validation mask records must be derived")

    def _validate(self) -> None:
        if self.condition not in CONDITIONS:
            raise MaskingContractError("validation mask record has an unknown condition")
        if (
            type(self.seed) is not int
            or self.seed < 0
            or type(self.example_count) is not int
            or self.example_count <= 0
        ):
            raise MaskingContractError("validation mask record has invalid metadata")
        for checksum in (self.policy_sha256, self.checksum_sha256):
            if len(checksum) != 64 or any(
                character not in "0123456789abcdef" for character in checksum
            ):
                raise MaskingContractError("validation mask record has an invalid checksum")


class _HashRandom:
    """Small counter-mode SHA-256 stream for platform-stable masking decisions."""

    def __init__(self, seed_material: bytes) -> None:
        self._key = hashlib.sha256(seed_material).digest()
        self._counter = 0

    def _uint64(self) -> int:
        block = hashlib.sha256(self._key + self._counter.to_bytes(16, "big")).digest()
        self._counter += 1
        return int.from_bytes(block[:8], "big")

    def random(self) -> float:
        return self._uint64() / 2**64

    def randbelow(self, upper_bound: int) -> int:
        if upper_bound <= 0:
            raise MaskingContractError("random replacement range is empty")
        limit = 2**64 - (2**64 % upper_bound)
        while True:
            value = self._uint64()
            if value < limit:
                return value % upper_bound


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def mask_packed_sequence(
    sequence: PackedSequence,
    *,
    seed: int,
    mode: MaskingMode,
    visit: int | None = None,
    policy: MaskingPolicy = APPROVED_MASKING_POLICY,
) -> MaskedExample:
    """Apply approved MLM masking using stable identity plus an explicit seed."""
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise MaskingContractError("masking seed must be a non-negative integer")
    if mode == "train":
        if isinstance(visit, bool) or not isinstance(visit, int) or visit < 0:
            raise MaskingContractError("training masking requires a non-negative visit")
        stream_identity: list[Any] = [
            "neu_mlm_masking_v1",
            mode,
            seed,
            sequence.example_identity,
            visit,
        ]
    elif mode == "validation":
        if visit is not None:
            raise MaskingContractError("validation masking does not accept a visit")
        stream_identity = ["neu_mlm_masking_v1", mode, seed, sequence.example_identity]
    else:
        raise MaskingContractError("unknown masking mode")

    rng = _HashRandom(_canonical_json_bytes(stream_identity))
    masked_ids = list(sequence.input_ids)
    labels = [IGNORE_INDEX] * len(sequence.input_ids)
    selected_positions: list[int] = []
    replacement_kinds: list[ReplacementKind] = []
    non_special_count = policy.vocabulary_size - len(policy.special_token_ids)
    eligibility = derive_mask_eligibility(
        sequence.input_ids,
        sequence.attention_mask,
    )

    for position, (token_id, eligible) in enumerate(
        zip(sequence.input_ids, eligibility.eligible_positions, strict=True)
    ):
        if not eligible:
            continue
        if rng.random() >= policy.probability:
            continue
        labels[position] = token_id
        selected_positions.append(position)
        replacement_draw = rng.random()
        if replacement_draw < policy.mask_fraction:
            masked_ids[position] = MASK_TOKEN_ID
            replacement_kinds.append("mask")
        elif replacement_draw < policy.mask_fraction + policy.random_fraction:
            replacement_rank = rng.randbelow(non_special_count)
            masked_ids[position] = _non_special_token_at_rank(
                replacement_rank,
                policy.special_token_ids,
                policy.vocabulary_size,
            )
            replacement_kinds.append("random")
        else:
            replacement_kinds.append("unchanged")

    checksum_payload = {
        "attention_mask": sequence.attention_mask,
        "example_identity": sequence.example_identity,
        "input_ids": masked_ids,
        "labels": labels,
        "mode": mode,
        "policy": _policy_payload(policy),
        "seed": seed,
        "token_type_ids": sequence.token_type_ids,
        "visit": visit,
    }
    checksum = hashlib.sha256(_canonical_json_bytes(checksum_payload)).hexdigest()
    return MaskedExample(
        input_ids=tuple(masked_ids),
        labels=tuple(labels),
        selected_positions=tuple(selected_positions),
        replacement_kinds=tuple(replacement_kinds),
        checksum_sha256=checksum,
    )


def build_validation_mask_record(
    sequences: Iterable[PackedSequence],
    *,
    seed: int,
    policy: MaskingPolicy = APPROVED_MASKING_POLICY,
) -> ValidationMaskRecord:
    """Derive one canonical checksum over an ordered fixed validation set."""
    material = tuple(sequences)
    if not material:
        raise MaskingContractError("validation mask records require at least one example")
    conditions = {sequence.condition for sequence in material}
    if len(conditions) != 1 or any(sequence.split != "validation" for sequence in material):
        raise MaskingContractError(
            "validation mask records require one condition and validation examples only"
        )
    identities = tuple(sequence.example_identity for sequence in material)
    if len(set(identities)) != len(identities):
        raise MaskingContractError("validation example identities must be unique")

    policy_payload = _policy_payload(policy)
    examples = []
    for sequence in material:
        masked = mask_packed_sequence(
            sequence,
            seed=seed,
            mode="validation",
            policy=policy,
        )
        examples.append(
            {
                "attention_mask": sequence.attention_mask,
                "example_identity": sequence.example_identity,
                "labels": masked.labels,
                "masked_input_ids": masked.input_ids,
                "token_type_ids": sequence.token_type_ids,
            }
        )
    payload = {
        "condition": material[0].condition,
        "examples": examples,
        "policy": policy_payload,
        "protocol": "neu_fixed_validation_masks_v1",
        "seed": seed,
    }
    record = object.__new__(ValidationMaskRecord)
    values = {
        "condition": material[0].condition,
        "seed": seed,
        "example_count": len(material),
        "policy_sha256": hashlib.sha256(
            _canonical_json_bytes(policy_payload)
        ).hexdigest(),
        "checksum_sha256": hashlib.sha256(_canonical_json_bytes(payload)).hexdigest(),
    }
    for name, value in values.items():
        object.__setattr__(record, name, value)
    record._validate()
    return record


def _non_special_token_at_rank(
    rank: int,
    special_token_ids: frozenset[int],
    vocabulary_size: int,
) -> int:
    """Map a uniform dense rank onto the vocabulary excluding all special IDs."""
    for token_id in range(vocabulary_size):
        if token_id in special_token_ids:
            continue
        if rank == 0:
            return token_id
        rank -= 1
    raise MaskingContractError("random replacement rank is outside the vocabulary")


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
