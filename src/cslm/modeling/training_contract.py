"""Model-free loss-normalization and optimizer-step ordering contracts."""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from types import MappingProxyType, ModuleType
from typing import Iterable

LOSS_NORMALIZATION_PROTOCOL = "neu_update_target_loss_normalization_v1"


class TrainingContractError(RuntimeError):
    """A future executor attempted an unapproved loss or step operation."""


@dataclass(frozen=True)
class MicrobatchLoss:
    target_cross_entropy_numerator: float
    actual_selected_target_count: int

    def __post_init__(self) -> None:
        numerator = self.target_cross_entropy_numerator
        count = self.actual_selected_target_count
        if (
            isinstance(numerator, bool)
            or not isinstance(numerator, int | float)
            or not math.isfinite(float(numerator))
            or numerator < 0
            or isinstance(count, bool)
            or not isinstance(count, int)
            or count < 0
            or (count == 0 and numerator != 0)
        ):
            raise TrainingContractError("microbatch loss contribution is invalid")


@dataclass(frozen=True, init=False)
class NormalizedUpdateLoss:
    target_cross_entropy_numerator: float
    actual_selected_target_count: int
    normalized_loss: float
    operation_order: tuple[str, ...]

    def __new__(cls) -> NormalizedUpdateLoss:
        raise TrainingContractError("normalized update losses must be factory-derived")


@dataclass(frozen=True, init=False)
class GradientClippingAuthorization:
    normalized_update_loss: NormalizedUpdateLoss
    operation_order: tuple[str, ...]

    def __new__(cls) -> GradientClippingAuthorization:
        raise TrainingContractError("gradient clipping must follow normalization")


@dataclass(frozen=True, init=False)
class OptimizerStepAuthorization:
    clipping_authorization: GradientClippingAuthorization
    operation_order: tuple[str, ...]

    def __new__(cls) -> OptimizerStepAuthorization:
        raise TrainingContractError("optimizer steps must follow gradient clipping")


def normalize_complete_update_loss(
    microbatches: Iterable[MicrobatchLoss],
) -> NormalizedUpdateLoss:
    """Sum all target numerators, then divide once by the complete-update count."""

    material = tuple(microbatches)
    if not material or any(
        not isinstance(microbatch, MicrobatchLoss) for microbatch in material
    ):
        raise TrainingContractError("complete update loss requires microbatch contributions")
    numerator = float(
        sum(
            microbatch.target_cross_entropy_numerator
            for microbatch in material
        )
    )
    target_count = sum(
        microbatch.actual_selected_target_count for microbatch in material
    )
    if target_count <= 0:
        raise TrainingContractError("complete optimizer update has zero selected targets")
    result = object.__new__(NormalizedUpdateLoss)
    object.__setattr__(result, "target_cross_entropy_numerator", numerator)
    object.__setattr__(result, "actual_selected_target_count", target_count)
    object.__setattr__(result, "normalized_loss", numerator / target_count)
    object.__setattr__(
        result,
        "operation_order",
        ("sum_target_cross_entropy", "divide_by_actual_selected_target_count"),
    )
    return result


def authorize_gradient_clipping(
    normalized_loss: NormalizedUpdateLoss,
) -> GradientClippingAuthorization:
    """Authorize clipping only after complete-update normalization."""

    if (
        not isinstance(normalized_loss, NormalizedUpdateLoss)
        or normalized_loss.operation_order
        != ("sum_target_cross_entropy", "divide_by_actual_selected_target_count")
    ):
        raise TrainingContractError("gradient clipping preceded loss normalization")
    result = object.__new__(GradientClippingAuthorization)
    object.__setattr__(result, "normalized_update_loss", normalized_loss)
    object.__setattr__(
        result,
        "operation_order",
        (*normalized_loss.operation_order, "clip_gradients"),
    )
    return result


def authorize_adamw_step(
    clipping: GradientClippingAuthorization,
) -> OptimizerStepAuthorization:
    """Authorize exactly one future AdamW step after normalization and clipping."""

    if (
        not isinstance(clipping, GradientClippingAuthorization)
        or clipping.operation_order
        != (
            "sum_target_cross_entropy",
            "divide_by_actual_selected_target_count",
            "clip_gradients",
        )
    ):
        raise TrainingContractError("AdamW step preceded approved gradient clipping")
    result = object.__new__(OptimizerStepAuthorization)
    object.__setattr__(result, "clipping_authorization", clipping)
    object.__setattr__(
        result,
        "operation_order",
        (*clipping.operation_order, "one_adamw_step"),
    )
    return result


def loss_normalization_contract_payload() -> dict[str, object]:
    """Canonical future-executor API and operation order bound by preparation."""

    return {
        "protocol": LOSS_NORMALIZATION_PROTOCOL,
        "numerator": "sum_target_token_cross_entropy_over_complete_update",
        "denominator": "total_actual_selected_targets_over_complete_update",
        "zero_target_microbatch": "zero_numerator",
        "zero_target_complete_update": "invalid",
        "operation_order": [
            "sum_target_cross_entropy",
            "divide_by_actual_selected_target_count",
            "clip_gradients",
            "one_adamw_step",
        ],
        "api": [
            normalize_complete_update_loss.__name__,
            authorize_gradient_clipping.__name__,
            authorize_adamw_step.__name__,
        ],
    }


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
