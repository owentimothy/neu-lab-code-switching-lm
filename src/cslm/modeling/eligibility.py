"""Authoritative mask-eligible WordPiece classification."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from types import MappingProxyType, ModuleType
from typing import Sequence

from cslm.modeling.config import MAX_SEQUENCE_LENGTH, VOCAB_SIZE


class EligibilityContractError(RuntimeError):
    """A packed tensor is not eligible for approved mask-target accounting."""


@dataclass(frozen=True)
class EligibilityProfile:
    """Privacy-safe counts and the exact eligible-position bitmap."""

    eligible_positions: tuple[bool, ...]
    eligible_count: int
    non_padding_count: int
    padding_count: int
    pad_count: int
    unk_count: int
    cls_count: int
    sep_count: int
    mask_count: int


_APPROVED_SPECIAL_TOKEN_IDS = MappingProxyType(
    {
        "[PAD]": 0,
        "[UNK]": 1,
        "[CLS]": 2,
        "[SEP]": 3,
        "[MASK]": 4,
    }
)
_APPROVED_SPECIAL_ID_SET = frozenset(_APPROVED_SPECIAL_TOKEN_IDS.values())


def approved_special_token_mapping(
    _approved: MappingProxyType[str, int] = _APPROVED_SPECIAL_TOKEN_IDS,
) -> MappingProxyType[str, int]:
    """Return the immutable private mapping used by eligibility authority."""

    return _approved


def _derive_mask_eligibility_impl(
    input_ids: Sequence[int],
    attention_mask: Sequence[int],
    _approved: MappingProxyType[str, int] = _APPROVED_SPECIAL_TOKEN_IDS,
    _special_ids: frozenset[int] = _APPROVED_SPECIAL_ID_SET,
) -> EligibilityProfile:
    if (
        not isinstance(input_ids, Sequence)
        or isinstance(input_ids, (str, bytes, bytearray))
        or not isinstance(attention_mask, Sequence)
        or isinstance(attention_mask, (str, bytes, bytearray))
        or len(input_ids) != MAX_SEQUENCE_LENGTH
        or len(attention_mask) != MAX_SEQUENCE_LENGTH
    ):
        raise EligibilityContractError("packed eligibility tensors have invalid lengths")

    normalized_ids: list[int] = []
    normalized_attention: list[int] = []
    padding_started = False
    for token_id, attended in zip(input_ids, attention_mask, strict=True):
        if (
            isinstance(token_id, bool)
            or not isinstance(token_id, int)
            or token_id < 0
            or token_id >= VOCAB_SIZE
            or isinstance(attended, bool)
            or not isinstance(attended, int)
            or attended not in {0, 1}
        ):
            raise EligibilityContractError(
                "packed eligibility tensors contain invalid values"
            )
        normalized_ids.append(token_id)
        normalized_attention.append(attended)
        if attended == 0:
            padding_started = True
            if token_id != _approved["[PAD]"]:
                raise EligibilityContractError("unattended positions must contain PAD")
        elif padding_started or token_id == _approved["[PAD]"]:
            raise EligibilityContractError(
                "packed padding is not a contiguous terminal suffix"
            )

    attended_count = sum(normalized_attention)
    attended_ids = normalized_ids[:attended_count]
    if (
        attended_count < 2
        or normalized_ids[0] != _approved["[CLS]"]
        or normalized_attention[0] != 1
        or normalized_ids[attended_count - 1] != _approved["[SEP]"]
        or attended_ids.count(_approved["[CLS]"]) != 1
        or _approved["[MASK]"] in attended_ids
        or attended_ids[1] == _approved["[SEP]"]
        or any(
            left == right == _approved["[SEP]"]
            for left, right in zip(attended_ids, attended_ids[1:])
        )
    ):
        raise EligibilityContractError("packed special-token structure is invalid")

    eligible = tuple(
        attended == 1 and token_id not in _special_ids
        for token_id, attended in zip(
            normalized_ids,
            normalized_attention,
            strict=True,
        )
    )
    counts = {
        token: sum(
            attended == 1 and token_id == _approved[token]
            for token_id, attended in zip(
                normalized_ids,
                normalized_attention,
                strict=True,
            )
        )
        for token in ("[UNK]", "[CLS]", "[SEP]", "[MASK]")
    }
    pad_count = sum(
        token_id == _approved["[PAD]"] for token_id in normalized_ids
    )
    return EligibilityProfile(
        eligible_positions=eligible,
        eligible_count=sum(eligible),
        non_padding_count=attended_count,
        padding_count=MAX_SEQUENCE_LENGTH - attended_count,
        pad_count=pad_count,
        unk_count=counts["[UNK]"],
        cls_count=counts["[CLS]"],
        sep_count=counts["[SEP]"],
        mask_count=counts["[MASK]"],
    )


def derive_mask_eligibility(
    input_ids: Sequence[int],
    attention_mask: Sequence[int],
) -> EligibilityProfile:
    """Validate packed arrays and derive every eligible position exactly once."""

    return _derive_mask_eligibility_impl(input_ids, attention_mask)


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
