"""Deterministic mask-eligible exposure schedules for future training."""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from types import MappingProxyType, ModuleType
from typing import Any, Iterable, Mapping, Sequence

from cslm.modeling.config import CONDITIONS, MAX_SEQUENCE_LENGTH
from cslm.modeling.eligibility import (
    EligibilityProfile,
    approved_special_token_mapping,
    derive_mask_eligibility,
)
from cslm.modeling.initialization import (
    SMALL_PILOT_SEED_PLANS,
    TINY_SMOKE_SEED_PLANS,
)
from cslm.modeling.masking import mask_packed_sequence
from cslm.modeling.packing import PackedSequence

ELIGIBILITY_PROTOCOL = "neu_mask_eligible_wordpieces_v1"
EXPOSURE_POLICY_PROTOCOL = "neu_mask_eligible_exposure_v1"
SCHEDULE_PROTOCOL = "neu_option2_population_passes_v1"
RESUME_POLICY_PROTOCOL = "neu_option2_update_boundary_resume_v1"
SEED_AUDIT_PROTOCOL = "neu_option2_four_condition_seed_audit_v1"
NOMINAL_ELIGIBLE_TARGET = 746_000
COMPLETE_POPULATION_PASSES = 6
OPTIMIZER_UPDATES = 1_000
UPDATE_FRONTIER_INCREMENT = 746
MAXIMUM_MICROBATCH_SEQUENCES = 16
MAXIMUM_MICROBATCHES_PER_UPDATE = 6
CHECKPOINT_UPDATES = (0, 250, 500, 750, 1_000)
EXACT_TOLERANCE_NUMERATOR = 101
EXACT_TOLERANCE_DENOMINATOR = 100
LEGACY_PROJECTED_SEQUENCE_EXPOSURES = 64_000

_SHA256_CHARACTERS = frozenset("0123456789abcdef")
_SPECIAL_TOKEN_IDS = approved_special_token_mapping()
_APPROVED_REAL_APPEARANCES = MappingProxyType(
    {
        "EnglishMono": 59_424,
        "SpanishMono": 42_990,
        "MonoCont": 64_371,
        "CsCont": 7_527,
    }
)
_APPROVED_REAL_ELIGIBLE_EXPOSURE = MappingProxyType(
    {
        "EnglishMono": 746_019,
        "SpanishMono": 746_009,
        "MonoCont": 746_003,
        "CsCont": 746_017,
    }
)
_APPROVED_REAL_SELECTED_TARGETS = MappingProxyType(
    {
        "tiny_smoke_1": MappingProxyType(
            {
                "EnglishMono": 112_163,
                "SpanishMono": 112_124,
                "MonoCont": 111_634,
                "CsCont": 111_674,
            }
        ),
        "small_1": MappingProxyType(
            {
                "EnglishMono": 112_327,
                "SpanishMono": 111_570,
                "MonoCont": 112_298,
                "CsCont": 111_586,
            }
        ),
        "small_2": MappingProxyType(
            {
                "EnglishMono": 111_405,
                "SpanishMono": 111_484,
                "MonoCont": 111_860,
                "CsCont": 111_424,
            }
        ),
        "small_3": MappingProxyType(
            {
                "EnglishMono": 112_277,
                "SpanishMono": 112_036,
                "MonoCont": 111_768,
                "CsCont": 111_830,
            }
        ),
    }
)
_APPROVED_REAL_POPULATION_EVIDENCE = MappingProxyType(
    {
        "EnglishMono": MappingProxyType(
            {
                "train_sequences": 9_750,
                "validation_sequences": 537,
                "population_eligible_exposure": 122_418,
                "overshoot": 19,
                "six_visits": 8_826,
                "seven_visits": 924,
            }
        ),
        "SpanishMono": MappingProxyType(
            {
                "train_sequences": 7_155,
                "validation_sequences": 362,
                "population_eligible_exposure": 124_172,
                "overshoot": 9,
                "six_visits": 7_095,
                "seven_visits": 60,
            }
        ),
        "MonoCont": MappingProxyType(
            {
                "train_sequences": 10_640,
                "validation_sequences": 525,
                "population_eligible_exposure": 123_271,
                "overshoot": 3,
                "six_visits": 10_109,
                "seven_visits": 531,
            }
        ),
        "CsCont": MappingProxyType(
            {
                "train_sequences": 1_247,
                "validation_sequences": 67,
                "population_eligible_exposure": 123_672,
                "overshoot": 17,
                "six_visits": 1_202,
                "seven_visits": 45,
            }
        ),
    }
)


class SchedulingContractError(RuntimeError):
    """A population, exposure, masking-audit, update, or resume invariant failed."""


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _require_sha256(value: object, category: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in _SHA256_CHARACTERS for character in value)
    ):
        raise SchedulingContractError(category)
    return value


def _require_exact_nonnegative_integer(value: object, category: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise SchedulingContractError(category)
    return value


def approved_training_mask_seed_plans() -> tuple[tuple[str, int], ...]:
    """Derive current training-mask seeds from merged initialization contracts."""

    plans = (("tiny_smoke_1", TINY_SMOKE_SEED_PLANS[0].training_mask_seed),)
    plans += tuple(
        (f"small_{index}", plan.training_mask_seed)
        for index, plan in enumerate(SMALL_PILOT_SEED_PLANS, start=1)
    )
    if plans != (
        ("tiny_smoke_1", 11_729),
        ("small_1", 281_828),
        ("small_2", 324_159),
        ("small_3", 171_803),
    ):
        raise SchedulingContractError("approved training-mask seed authority changed")
    return plans


def exact_one_percent_pass(values: Iterable[int]) -> bool:
    """Apply the exact reviewed comparison without floating-point arithmetic."""

    material = tuple(values)
    if not material or any(
        isinstance(value, bool) or not isinstance(value, int) or value <= 0
        for value in material
    ):
        raise SchedulingContractError("exact exposure comparison requires positive integers")
    return EXACT_TOLERANCE_DENOMINATOR * max(material) <= (
        EXACT_TOLERANCE_NUMERATOR * min(material)
    )


@dataclass(frozen=True)
class SequenceAppearance:
    cursor: int
    pass_index: int
    pass_cursor: int
    sequence_index: int
    sequence_identity: str = field(repr=False)
    visit: int
    eligible_count: int


@dataclass(frozen=True)
class MicrobatchPlan:
    microbatch_index: int
    schedule_start_cursor: int
    schedule_end_cursor: int
    sequence_count: int
    eligible_exposure: int
    selected_targets_by_seed: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class OptimizerUpdatePlan:
    update: int
    cumulative_frontier: int
    schedule_start_cursor: int
    schedule_end_cursor: int
    eligible_exposure: int
    cumulative_eligible_exposure: int
    token_credit: int
    microbatches: tuple[MicrobatchPlan, ...]
    selected_targets_by_seed: tuple[tuple[str, int], ...]


@dataclass(frozen=True, init=False)
class SeedTargetAudit:
    audit_protocol: str
    plan_name: str
    seed: int
    condition: str
    input_population_anchor_sha256: str
    population_anchor_sha256: str
    schedule_identity_sha256: str
    schedule_order_sha256: str
    appearance_count: int
    appearance_visit_sha256: str
    update_count: int
    selected_targets_by_update: tuple[int, ...] = field(repr=False)
    actual_selected_targets: int
    minimum_update_selected_targets: int
    maximum_update_selected_targets: int
    update_counts_sha256: str
    evidence_sha256: str

    def __new__(cls) -> SeedTargetAudit:
        raise SchedulingContractError("seed target audits must be schedule-derived")


@dataclass(frozen=True)
class ConditionSchedule:
    condition: str
    input_population_anchor_sha256: str
    population_anchor_sha256: str
    sequence_count: int
    population_eligible_exposure: int
    appearances: tuple[SequenceAppearance, ...] = field(repr=False)
    updates: tuple[OptimizerUpdatePlan, ...] = field(repr=False)
    seed_audits: tuple[SeedTargetAudit, ...]
    nominal_target: int
    actual_eligible_exposure: int
    overshoot: int
    complete_pass_appearances: int
    residual_appearances: int
    repetition_distribution: tuple[tuple[int, int], ...]
    scheduled_non_padding_positions: int
    scheduled_padding_positions: int
    scheduled_cls_appearances: int
    scheduled_sep_appearances: int
    scheduled_unk_appearances: int
    scheduled_mask_appearances: int
    schedule_order_sha256: str
    update_plan_sha256: str
    identity_sha256: str


@dataclass(frozen=True, init=False)
class PairedSeedTargetAudit:
    audit_protocol: str
    plan_name: str
    seed: int
    input_population_anchor_sha256: str
    schedule_set_identity_sha256: str
    condition_audits: tuple[SeedTargetAudit, ...] = field(repr=False)
    actual_selected_targets_by_condition: tuple[tuple[str, int], ...]
    minimum_selected_targets: int
    maximum_selected_targets: int
    exact_ratio_numerator: int
    exact_ratio_denominator: int
    exact_one_percent_passed: bool
    evidence_sha256: str

    def __new__(cls) -> PairedSeedTargetAudit:
        raise SchedulingContractError("paired seed audits must be schedule-derived")


@dataclass(frozen=True)
class TrainingExposurePlan:
    input_population_anchor_sha256: str
    schedule_set_identity_sha256: str
    conditions: tuple[ConditionSchedule, ...] = field(repr=False)
    seed_audits: tuple[PairedSeedTargetAudit, ...]
    minimum_eligible_exposure: int
    maximum_eligible_exposure: int
    exact_ratio_numerator: int
    exact_ratio_denominator: int
    exact_one_percent_passed: bool
    identity_sha256: str


@dataclass(frozen=True, init=False)
class ResumeState:
    resume_policy_protocol: str
    seed_audit_protocol: str
    schedule_protocol: str
    input_population_anchor_sha256: str
    schedule_set_identity_sha256: str
    seed_authorization_evidence_sha256: str
    schedule_identity_sha256: str
    condition: str
    nominal_target: int
    completed_optimizer_update: int
    checkpoint_update: int
    schedule_cursor: int
    population_pass: int
    population_pass_cursor: int
    cumulative_eligible_exposure: int
    token_credit: int
    visit_state_sha256: str
    training_mask_seed: int
    ordered_prefix_sha256: str
    optimizer_state_reference: str
    scheduler_state_reference: str
    at_update_boundary: bool

    def __new__(cls) -> ResumeState:
        raise SchedulingContractError("resume states must be schedule-derived")


def _seed_target_audit(**values: object) -> SeedTargetAudit:
    values = {"audit_protocol": SEED_AUDIT_PROTOCOL, **values}
    values["evidence_sha256"] = _sha256(
        [
            SEED_AUDIT_PROTOCOL,
            "condition_seed_audit_evidence",
            values["plan_name"],
            values["seed"],
            values["condition"],
            values["input_population_anchor_sha256"],
            values["population_anchor_sha256"],
            values["schedule_identity_sha256"],
            values["schedule_order_sha256"],
            values["appearance_count"],
            values["appearance_visit_sha256"],
            values["update_count"],
            values["selected_targets_by_update"],
            values["actual_selected_targets"],
            values["minimum_update_selected_targets"],
            values["maximum_update_selected_targets"],
            values["update_counts_sha256"],
        ]
    )
    audit = object.__new__(SeedTargetAudit)
    for name, value in values.items():
        object.__setattr__(audit, name, value)
    return audit


def _paired_seed_target_audit(**values: object) -> PairedSeedTargetAudit:
    values = {"audit_protocol": SEED_AUDIT_PROTOCOL, **values}
    values["evidence_sha256"] = _sha256(
        [
            SEED_AUDIT_PROTOCOL,
            "four_condition_seed_audit_evidence",
            values["plan_name"],
            values["seed"],
            values["input_population_anchor_sha256"],
            values["schedule_set_identity_sha256"],
            [
                [
                    audit.condition,
                    audit.population_anchor_sha256,
                    audit.schedule_identity_sha256,
                    audit.appearance_visit_sha256,
                    audit.update_count,
                    audit.selected_targets_by_update,
                    audit.evidence_sha256,
                ]
                for audit in values["condition_audits"]
            ],
            values["actual_selected_targets_by_condition"],
            values["minimum_selected_targets"],
            values["maximum_selected_targets"],
            values["exact_ratio_numerator"],
            values["exact_ratio_denominator"],
            values["exact_one_percent_passed"],
        ]
    )
    audit = object.__new__(PairedSeedTargetAudit)
    for name, value in values.items():
        object.__setattr__(audit, name, value)
    return audit


def _sequence_material(
    sequences: Iterable[PackedSequence],
) -> tuple[str, tuple[PackedSequence, ...], tuple[EligibilityProfile, ...]]:
    material = tuple(sequences)
    if not material:
        raise SchedulingContractError("training schedule population is empty")
    condition = material[0].condition
    if condition not in CONDITIONS or any(
        sequence.condition != condition or sequence.split != "train"
        for sequence in material
    ):
        raise SchedulingContractError("training schedule population crosses condition or split")
    identities = tuple(sequence.example_identity for sequence in material)
    if any(
        not isinstance(identity, str)
        or len(identity) != 64
        or any(character not in _SHA256_CHARACTERS for character in identity)
        for identity in identities
    ):
        identities = ()
        material = ()
        condition = ""
        raise SchedulingContractError("packed sequence identity is invalid")
    if len(set(identities)) != len(identities):
        raise SchedulingContractError("packed sequence identities are not unique")
    profiles = tuple(
        derive_mask_eligibility(sequence.input_ids, sequence.attention_mask)
        for sequence in material
    )
    if sum(profile.eligible_count for profile in profiles) <= 0:
        raise SchedulingContractError("training population has zero eligible exposure")
    return condition, material, profiles


def _population_anchor(
    *,
    input_population_anchor_sha256: str,
    condition: str,
    sequences: Sequence[PackedSequence],
    profiles: Sequence[EligibilityProfile],
) -> str:
    sequence_bindings = [
        [
            index,
            sequence.example_identity,
            _sha256(
                [
                    "neu_option2_packed_sequence_binding_v1",
                    condition,
                    index,
                    sequence.input_ids,
                    sequence.attention_mask,
                    sequence.token_type_ids,
                    profile.eligible_positions,
                ]
            ),
        ]
        for index, (sequence, profile) in enumerate(
            zip(sequences, profiles, strict=True)
        )
    ]
    return _sha256(
        [
            "neu_option2_condition_population_anchor_v1",
            SCHEDULE_PROTOCOL,
            input_population_anchor_sha256,
            condition,
            sequence_bindings,
        ]
    )


def _permutation_digest(
    *,
    input_population_anchor_sha256: str,
    population_anchor_sha256: str,
    condition: str,
    pass_index: int,
    sequence_identity: str,
) -> str:
    return _sha256(
        [
            SCHEDULE_PROTOCOL,
            "complete_population_permutation",
            ["input_population_anchor", input_population_anchor_sha256],
            ["condition_population_anchor", population_anchor_sha256],
            ["condition", condition],
            ["zero_based_pass_index", pass_index],
            ["packed_sequence_identity", sequence_identity],
        ]
    )


def _pass_permutation(
    *,
    input_population_anchor_sha256: str,
    population_anchor_sha256: str,
    condition: str,
    pass_index: int,
    sequences: Sequence[PackedSequence],
) -> tuple[int, ...]:
    _require_exact_nonnegative_integer(pass_index, "population pass index is invalid")
    return tuple(
        sorted(
            range(len(sequences)),
            key=lambda index: (
                _permutation_digest(
                    input_population_anchor_sha256=input_population_anchor_sha256,
                    population_anchor_sha256=population_anchor_sha256,
                    condition=condition,
                    pass_index=pass_index,
                    sequence_identity=sequences[index].example_identity,
                ),
                index,
            ),
        )
    )


def _appearance_payload(appearance: SequenceAppearance) -> list[object]:
    return [
        appearance.cursor,
        appearance.pass_index,
        appearance.pass_cursor,
        appearance.sequence_index,
        appearance.sequence_identity,
        appearance.visit,
        appearance.eligible_count,
    ]


def _schedule_order_checksum(
    *,
    condition: str,
    population_anchor_sha256: str,
    appearances: Sequence[SequenceAppearance],
) -> str:
    return _sha256(
        [
            SCHEDULE_PROTOCOL,
            "ordered_schedule",
            condition,
            population_anchor_sha256,
            [_appearance_payload(appearance) for appearance in appearances],
        ]
    )


def _selected_counts(
    *,
    appearances: Sequence[SequenceAppearance],
    sequences: Sequence[PackedSequence],
    seed_plans: Sequence[tuple[str, int]],
) -> tuple[tuple[int, ...], ...]:
    rows: list[tuple[int, ...]] = []
    for appearance in appearances:
        sequence = sequences[appearance.sequence_index]
        counts = tuple(
            len(
                mask_packed_sequence(
                    sequence,
                    seed=seed,
                    mode="train",
                    visit=appearance.visit,
                ).selected_positions
            )
            for _, seed in seed_plans
        )
        rows.append(counts)
    return tuple(rows)


def _build_updates(
    *,
    appearances: Sequence[SequenceAppearance],
    selected_counts: Sequence[Sequence[int]],
    seed_plans: Sequence[tuple[str, int]],
) -> tuple[OptimizerUpdatePlan, ...]:
    updates: list[OptimizerUpdatePlan] = []
    cursor = 0
    cumulative = 0
    for update in range(1, OPTIMIZER_UPDATES + 1):
        frontier = UPDATE_FRONTIER_INCREMENT * update
        start = cursor
        while cursor < len(appearances) and cumulative < frontier:
            cumulative += appearances[cursor].eligible_count
            cursor += 1
        if cursor == start or cumulative < frontier:
            raise SchedulingContractError("schedule cannot reach an optimizer-update frontier")
        if cursor - start > (
            MAXIMUM_MICROBATCH_SEQUENCES * MAXIMUM_MICROBATCHES_PER_UPDATE
        ):
            raise SchedulingContractError("optimizer update requires more than six microbatches")

        microbatches: list[MicrobatchPlan] = []
        for microbatch_index, micro_start in enumerate(
            range(start, cursor, MAXIMUM_MICROBATCH_SEQUENCES)
        ):
            micro_end = min(cursor, micro_start + MAXIMUM_MICROBATCH_SEQUENCES)
            seed_totals = tuple(
                (
                    plan_name,
                    sum(
                        selected_counts[index][seed_index]
                        for index in range(micro_start, micro_end)
                    ),
                )
                for seed_index, (plan_name, _) in enumerate(seed_plans)
            )
            microbatches.append(
                MicrobatchPlan(
                    microbatch_index=microbatch_index,
                    schedule_start_cursor=micro_start,
                    schedule_end_cursor=micro_end,
                    sequence_count=micro_end - micro_start,
                    eligible_exposure=sum(
                        appearances[index].eligible_count
                        for index in range(micro_start, micro_end)
                    ),
                    selected_targets_by_seed=seed_totals,
                )
            )
        if not 1 <= len(microbatches) <= MAXIMUM_MICROBATCHES_PER_UPDATE:
            raise SchedulingContractError("optimizer update has an invalid microbatch count")
        update_seed_totals = tuple(
            (
                plan_name,
                sum(
                    selected_counts[index][seed_index]
                    for index in range(start, cursor)
                ),
            )
            for seed_index, (plan_name, _) in enumerate(seed_plans)
        )
        if any(count <= 0 for _, count in update_seed_totals):
            raise SchedulingContractError("optimizer update has zero selected targets")
        updates.append(
            OptimizerUpdatePlan(
                update=update,
                cumulative_frontier=frontier,
                schedule_start_cursor=start,
                schedule_end_cursor=cursor,
                eligible_exposure=sum(
                    appearance.eligible_count for appearance in appearances[start:cursor]
                ),
                cumulative_eligible_exposure=cumulative,
                token_credit=cumulative - frontier,
                microbatches=tuple(microbatches),
                selected_targets_by_seed=update_seed_totals,
            )
        )
    if cursor != len(appearances) or cumulative != sum(
        appearance.eligible_count for appearance in appearances
    ):
        raise SchedulingContractError("schedule contains material beyond update 1000")
    return tuple(updates)


def _update_plan_payload(updates: Sequence[OptimizerUpdatePlan]) -> list[object]:
    return [
        [
            update.update,
            update.cumulative_frontier,
            update.schedule_start_cursor,
            update.schedule_end_cursor,
            update.eligible_exposure,
            update.cumulative_eligible_exposure,
            update.token_credit,
            [
                [
                    microbatch.microbatch_index,
                    microbatch.schedule_start_cursor,
                    microbatch.schedule_end_cursor,
                    microbatch.sequence_count,
                    microbatch.eligible_exposure,
                    microbatch.selected_targets_by_seed,
                ]
                for microbatch in update.microbatches
            ],
            update.selected_targets_by_seed,
        ]
        for update in updates
    ]


def build_condition_schedule(
    sequences: Iterable[PackedSequence],
    *,
    input_population_anchor_sha256: str,
) -> ConditionSchedule:
    """Build one exact six-pass-plus-residual schedule without caller randomness."""

    input_anchor = _require_sha256(
        input_population_anchor_sha256,
        "input population anchor is invalid",
    )
    condition, material, profiles = _sequence_material(sequences)
    population_anchor = _population_anchor(
        input_population_anchor_sha256=input_anchor,
        condition=condition,
        sequences=material,
        profiles=profiles,
    )
    appearances: list[SequenceAppearance] = []
    visits = [0] * len(material)
    cumulative = 0

    def append_pass(pass_index: int, *, stop_at_target: bool) -> None:
        nonlocal cumulative
        permutation = _pass_permutation(
            input_population_anchor_sha256=input_anchor,
            population_anchor_sha256=population_anchor,
            condition=condition,
            pass_index=pass_index,
            sequences=material,
        )
        if len(permutation) != len(material) or set(permutation) != set(
            range(len(material))
        ):
            raise SchedulingContractError("population permutation is incomplete")
        for pass_cursor, sequence_index in enumerate(permutation):
            profile = profiles[sequence_index]
            appearances.append(
                SequenceAppearance(
                    cursor=len(appearances),
                    pass_index=pass_index,
                    pass_cursor=pass_cursor,
                    sequence_index=sequence_index,
                    sequence_identity=material[sequence_index].example_identity,
                    visit=visits[sequence_index],
                    eligible_count=profile.eligible_count,
                )
            )
            visits[sequence_index] += 1
            cumulative += profile.eligible_count
            if stop_at_target and cumulative >= NOMINAL_ELIGIBLE_TARGET:
                break

    for pass_index in range(COMPLETE_POPULATION_PASSES):
        append_pass(pass_index, stop_at_target=False)
    if cumulative >= NOMINAL_ELIGIBLE_TARGET:
        raise SchedulingContractError("six complete passes already reach the nominal target")
    append_pass(COMPLETE_POPULATION_PASSES, stop_at_target=True)
    if cumulative < NOMINAL_ELIGIBLE_TARGET:
        raise SchedulingContractError("bounded residual pass cannot reach the nominal target")

    counts = Counter(appearance.sequence_index for appearance in appearances)
    if (
        set(counts) != set(range(len(material)))
        or any(value not in {6, 7} for value in counts.values())
        or any(visits[index] != counts[index] for index in range(len(material)))
    ):
        raise SchedulingContractError("schedule repetition bounds are invalid")
    complete_count = COMPLETE_POPULATION_PASSES * len(material)
    if appearances[:complete_count] and any(
        appearance.pass_index != appearance.cursor // len(material)
        for appearance in appearances[:complete_count]
    ):
        raise SchedulingContractError("complete population passes interleave")

    seed_plans = approved_training_mask_seed_plans()
    selected = _selected_counts(
        appearances=appearances,
        sequences=material,
        seed_plans=seed_plans,
    )
    updates = _build_updates(
        appearances=appearances,
        selected_counts=selected,
        seed_plans=seed_plans,
    )
    schedule_order_sha256 = _schedule_order_checksum(
        condition=condition,
        population_anchor_sha256=population_anchor,
        appearances=appearances,
    )
    update_plan_sha256 = _sha256(
        [
            SCHEDULE_PROTOCOL,
            "update_and_microbatch_plan",
            condition,
            schedule_order_sha256,
            _update_plan_payload(updates),
        ]
    )
    provisional_identity = _sha256(
        [
            SCHEDULE_PROTOCOL,
            condition,
            population_anchor,
            schedule_order_sha256,
            update_plan_sha256,
        ]
    )
    seed_audits = tuple(
        _seed_target_audit(
            plan_name=plan_name,
            seed=seed,
            condition=condition,
            input_population_anchor_sha256=input_anchor,
            population_anchor_sha256=population_anchor,
            schedule_identity_sha256=provisional_identity,
            schedule_order_sha256=schedule_order_sha256,
            appearance_count=len(appearances),
            appearance_visit_sha256=schedule_order_sha256,
            update_count=len(updates),
            selected_targets_by_update=tuple(
                dict(update.selected_targets_by_seed)[plan_name]
                for update in updates
            ),
            actual_selected_targets=sum(row[seed_index] for row in selected),
            minimum_update_selected_targets=min(
                dict(update.selected_targets_by_seed)[plan_name] for update in updates
            ),
            maximum_update_selected_targets=max(
                dict(update.selected_targets_by_seed)[plan_name] for update in updates
            ),
            update_counts_sha256=_sha256(
                [
                    SCHEDULE_PROTOCOL,
                    "selected_targets_by_update",
                    condition,
                    schedule_order_sha256,
                    plan_name,
                    seed,
                    [
                        dict(update.selected_targets_by_seed)[plan_name]
                        for update in updates
                    ],
                ]
            ),
        )
        for seed_index, (plan_name, seed) in enumerate(seed_plans)
    )
    del selected

    scheduled_profiles = [
        profiles[appearance.sequence_index] for appearance in appearances
    ]
    identity = _sha256(
        [
            SCHEDULE_PROTOCOL,
            "condition_schedule_identity",
            provisional_identity,
            [
                [
                    audit.plan_name,
                    audit.seed,
                    audit.actual_selected_targets,
                    audit.update_counts_sha256,
                ]
                for audit in seed_audits
            ],
        ]
    )
    seed_audits = tuple(
        _seed_target_audit(
            plan_name=audit.plan_name,
            seed=audit.seed,
            condition=audit.condition,
            input_population_anchor_sha256=(
                audit.input_population_anchor_sha256
            ),
            population_anchor_sha256=audit.population_anchor_sha256,
            schedule_identity_sha256=identity,
            schedule_order_sha256=audit.schedule_order_sha256,
            appearance_count=audit.appearance_count,
            appearance_visit_sha256=audit.appearance_visit_sha256,
            update_count=audit.update_count,
            selected_targets_by_update=(
                audit.selected_targets_by_update
            ),
            actual_selected_targets=audit.actual_selected_targets,
            minimum_update_selected_targets=audit.minimum_update_selected_targets,
            maximum_update_selected_targets=audit.maximum_update_selected_targets,
            update_counts_sha256=audit.update_counts_sha256,
        )
        for audit in seed_audits
    )
    return ConditionSchedule(
        condition=condition,
        input_population_anchor_sha256=input_anchor,
        population_anchor_sha256=population_anchor,
        sequence_count=len(material),
        population_eligible_exposure=sum(
            profile.eligible_count for profile in profiles
        ),
        appearances=tuple(appearances),
        updates=updates,
        seed_audits=seed_audits,
        nominal_target=NOMINAL_ELIGIBLE_TARGET,
        actual_eligible_exposure=cumulative,
        overshoot=cumulative - NOMINAL_ELIGIBLE_TARGET,
        complete_pass_appearances=complete_count,
        residual_appearances=len(appearances) - complete_count,
        repetition_distribution=tuple(sorted(Counter(counts.values()).items())),
        scheduled_non_padding_positions=sum(
            profile.non_padding_count for profile in scheduled_profiles
        ),
        scheduled_padding_positions=sum(
            profile.padding_count for profile in scheduled_profiles
        ),
        scheduled_cls_appearances=sum(
            profile.cls_count for profile in scheduled_profiles
        ),
        scheduled_sep_appearances=sum(
            profile.sep_count for profile in scheduled_profiles
        ),
        scheduled_unk_appearances=sum(
            profile.unk_count for profile in scheduled_profiles
        ),
        scheduled_mask_appearances=sum(
            profile.mask_count for profile in scheduled_profiles
        ),
        schedule_order_sha256=schedule_order_sha256,
        update_plan_sha256=update_plan_sha256,
        identity_sha256=identity,
    )


def _schedule_set_identity(
    *,
    input_population_anchor_sha256: str,
    schedules: Sequence[ConditionSchedule],
) -> str:
    return _sha256(
        [
            SCHEDULE_PROTOCOL,
            "four_condition_schedule_set",
            input_population_anchor_sha256,
            [
                [
                    schedule.condition,
                    schedule.population_anchor_sha256,
                    schedule.schedule_order_sha256,
                    schedule.update_plan_sha256,
                    schedule.identity_sha256,
                ]
                for schedule in schedules
            ],
        ]
    )


def _paired_seed_audits(
    schedules: Sequence[ConditionSchedule],
    *,
    input_population_anchor_sha256: str,
    schedule_set_identity_sha256: str,
) -> tuple[PairedSeedTargetAudit, ...]:
    output: list[PairedSeedTargetAudit] = []
    for plan_name, seed in approved_training_mask_seed_plans():
        counts = tuple(
            (
                condition,
                next(
                    audit.actual_selected_targets
                    for audit in schedule.seed_audits
                    if audit.plan_name == plan_name and audit.seed == seed
                ),
            )
            for condition in CONDITIONS
            for schedule in schedules
            if schedule.condition == condition
        )
        if len(counts) != len(CONDITIONS):
            raise SchedulingContractError("approved seed audit population is incomplete")
        values = tuple(value for _, value in counts)
        passed = exact_one_percent_pass(values)
        if not passed:
            raise SchedulingContractError("approved seed selected-target parity failed")
        condition_audits = tuple(
            next(
                audit
                for audit in schedule.seed_audits
                if audit.plan_name == plan_name and audit.seed == seed
            )
            for condition in CONDITIONS
            for schedule in schedules
            if schedule.condition == condition
        )
        output.append(
            _paired_seed_target_audit(
                plan_name=plan_name,
                seed=seed,
                input_population_anchor_sha256=(
                    input_population_anchor_sha256
                ),
                schedule_set_identity_sha256=(
                    schedule_set_identity_sha256
                ),
                condition_audits=condition_audits,
                actual_selected_targets_by_condition=counts,
                minimum_selected_targets=min(values),
                maximum_selected_targets=max(values),
                exact_ratio_numerator=max(values),
                exact_ratio_denominator=min(values),
                exact_one_percent_passed=True,
            )
        )
    return tuple(output)


def build_training_exposure_plan(
    sequences: Iterable[PackedSequence],
    *,
    input_population_anchor_sha256: str,
) -> TrainingExposurePlan:
    """Build four condition schedules and enforce primary and seed parity."""

    material = tuple(sequences)
    if (
        not material
        or any(
            type(sequence) is not PackedSequence
            or sequence.condition not in CONDITIONS
            or sequence.split != "train"
            for sequence in material
        )
        or {sequence.condition for sequence in material} != set(CONDITIONS)
        or len({sequence.example_identity for sequence in material})
        != len(material)
    ):
        raise SchedulingContractError(
            "exactly four globally distinct training populations are required"
        )
    by_condition = {
        condition: tuple(
            sequence
            for sequence in material
            if sequence.condition == condition and sequence.split == "train"
        )
        for condition in CONDITIONS
    }
    if (
        any(not by_condition[condition] for condition in CONDITIONS)
        or sum(len(population) for population in by_condition.values())
        != len(material)
    ):
        raise SchedulingContractError("four complete training populations are required")
    schedules = tuple(
        build_condition_schedule(
            by_condition[condition],
            input_population_anchor_sha256=input_population_anchor_sha256,
        )
        for condition in CONDITIONS
    )
    if sum(schedule.sequence_count for schedule in schedules) != len(material):
        raise SchedulingContractError("scheduled populations do not reconcile with input")
    exposures = tuple(schedule.actual_eligible_exposure for schedule in schedules)
    if not exact_one_percent_pass(exposures):
        raise SchedulingContractError("mask-eligible exposure differs by more than one percent")
    schedule_set_identity = _schedule_set_identity(
        input_population_anchor_sha256=input_population_anchor_sha256,
        schedules=schedules,
    )
    seed_audits = _paired_seed_audits(
        schedules,
        input_population_anchor_sha256=input_population_anchor_sha256,
        schedule_set_identity_sha256=schedule_set_identity,
    )
    identity = _sha256(
        [
            EXPOSURE_POLICY_PROTOCOL,
            SCHEDULE_PROTOCOL,
            input_population_anchor_sha256,
            schedule_set_identity,
            [schedule.identity_sha256 for schedule in schedules],
            [
                [
                    audit.plan_name,
                    audit.seed,
                    audit.actual_selected_targets_by_condition,
                ]
                for audit in seed_audits
            ],
        ]
    )
    return TrainingExposurePlan(
        input_population_anchor_sha256=_require_sha256(
            input_population_anchor_sha256,
            "input population anchor is invalid",
        ),
        schedule_set_identity_sha256=schedule_set_identity,
        conditions=schedules,
        seed_audits=seed_audits,
        minimum_eligible_exposure=min(exposures),
        maximum_eligible_exposure=max(exposures),
        exact_ratio_numerator=max(exposures),
        exact_ratio_denominator=min(exposures),
        exact_one_percent_passed=True,
        identity_sha256=identity,
    )


def validate_condition_schedule(
    schedule: ConditionSchedule,
    sequences: Iterable[PackedSequence],
) -> None:
    """Reject any schedule field not regenerated from the packed population."""

    if type(schedule) is not ConditionSchedule:
        raise SchedulingContractError("condition schedule type is invalid")
    regenerated = build_condition_schedule(
        sequences,
        input_population_anchor_sha256=(
            schedule.input_population_anchor_sha256
        ),
    )
    if regenerated != schedule:
        raise SchedulingContractError("condition schedule does not regenerate")


def validate_training_exposure_plan(
    plan: TrainingExposurePlan,
    sequences: Iterable[PackedSequence],
) -> None:
    """Reject aggregate or condition-plan substitution."""

    if type(plan) is not TrainingExposurePlan:
        raise SchedulingContractError("training exposure plan type is invalid")
    regenerated = build_training_exposure_plan(
        sequences,
        input_population_anchor_sha256=(
            plan.input_population_anchor_sha256
        ),
    )
    if regenerated != plan:
        raise SchedulingContractError("training exposure plan does not regenerate")


def audit_training_mask_seed(
    schedule: ConditionSchedule,
    sequences: Iterable[PackedSequence],
    *,
    plan_name: str,
    seed: int,
) -> SeedTargetAudit:
    """Independently audit one future seed without adapting the schedule."""

    if (
        not isinstance(plan_name, str)
        or not plan_name
        or plan_name in {name for name, _ in approved_training_mask_seed_plans()}
    ):
        raise SchedulingContractError("future seed plan name is invalid or already reviewed")
    audited_seed = _require_exact_nonnegative_integer(
        seed,
        "future training-mask seed is invalid",
    )
    material = tuple(sequences)
    validate_condition_schedule(schedule, material)
    _, condition_sequences, _ = _sequence_material(material)
    selected = tuple(
        len(
            mask_packed_sequence(
                condition_sequences[appearance.sequence_index],
                seed=audited_seed,
                mode="train",
                visit=appearance.visit,
            ).selected_positions
        )
        for appearance in schedule.appearances
    )
    update_counts = tuple(
        sum(selected[update.schedule_start_cursor : update.schedule_end_cursor])
        for update in schedule.updates
    )
    if any(count <= 0 for count in update_counts):
        raise SchedulingContractError("future seed has a zero-target optimizer update")
    return _seed_target_audit(
        plan_name=plan_name,
        seed=audited_seed,
        condition=schedule.condition,
        input_population_anchor_sha256=(
            schedule.input_population_anchor_sha256
        ),
        population_anchor_sha256=schedule.population_anchor_sha256,
        schedule_identity_sha256=schedule.identity_sha256,
        schedule_order_sha256=schedule.schedule_order_sha256,
        appearance_count=len(schedule.appearances),
        appearance_visit_sha256=schedule.schedule_order_sha256,
        update_count=len(schedule.updates),
        selected_targets_by_update=update_counts,
        actual_selected_targets=sum(selected),
        minimum_update_selected_targets=min(update_counts),
        maximum_update_selected_targets=max(update_counts),
        update_counts_sha256=_sha256(
            [
                SCHEDULE_PROTOCOL,
                "future_selected_targets_by_update",
                schedule.condition,
                schedule.schedule_order_sha256,
                plan_name,
                audited_seed,
                update_counts,
            ]
        ),
    )


def audit_future_paired_training_mask_seed(
    plan: TrainingExposurePlan,
    sequences: Iterable[PackedSequence],
    *,
    plan_name: str,
    seed: int,
) -> PairedSeedTargetAudit:
    """Require independent per-condition and exact paired parity for a new seed."""

    material = tuple(sequences)
    validate_training_exposure_plan(plan, material)
    condition_audits = tuple(
        audit_training_mask_seed(
            schedule,
            (
                sequence
                for sequence in material
                if (
                    sequence.condition == schedule.condition
                    and sequence.split == "train"
                )
            ),
            plan_name=plan_name,
            seed=seed,
        )
        for schedule in plan.conditions
    )
    counts = tuple(
        (condition, next(
            audit.actual_selected_targets
            for audit in condition_audits
            if audit.condition == condition
        ))
        for condition in CONDITIONS
    )
    values = tuple(value for _, value in counts)
    if not exact_one_percent_pass(values):
        raise SchedulingContractError("future seed selected-target parity failed")
    return _paired_seed_target_audit(
        plan_name=plan_name,
        seed=seed,
        input_population_anchor_sha256=(
            plan.input_population_anchor_sha256
        ),
        schedule_set_identity_sha256=(
            plan.schedule_set_identity_sha256
        ),
        condition_audits=condition_audits,
        actual_selected_targets_by_condition=counts,
        minimum_selected_targets=min(values),
        maximum_selected_targets=max(values),
        exact_ratio_numerator=max(values),
        exact_ratio_denominator=min(values),
        exact_one_percent_passed=True,
    )


def validate_seed_authorization(
    plan: TrainingExposurePlan,
    sequences: Iterable[PackedSequence],
    audit: PairedSeedTargetAudit,
) -> PairedSeedTargetAudit:
    """Regenerate the complete four-condition authority for one exact seed."""

    material = tuple(sequences)
    if type(audit) is not PairedSeedTargetAudit:
        raise SchedulingContractError("four-condition seed audit type is invalid")
    validate_training_exposure_plan(plan, material)
    approved = {
        (candidate.plan_name, candidate.seed): candidate
        for candidate in plan.seed_audits
    }
    try:
        audit_key = (audit.plan_name, audit.seed)
    except AttributeError:
        raise SchedulingContractError(
            "four-condition seed audit evidence is incomplete"
        ) from None
    expected = approved.get(audit_key)
    if expected is None:
        expected = audit_future_paired_training_mask_seed(
            plan,
            material,
            plan_name=audit.plan_name,
            seed=audit.seed,
        )
    try:
        matches = audit == expected
    except AttributeError:
        raise SchedulingContractError(
            "four-condition seed audit evidence is incomplete"
        ) from None
    if not matches:
        raise SchedulingContractError(
            "four-condition seed audit evidence does not regenerate"
        )
    return expected


def validate_canonical_real_reference(plan: TrainingExposurePlan) -> None:
    """Fail closed unless a production plan derives the reviewed real aggregates."""

    appearances = {
        schedule.condition: len(schedule.appearances)
        for schedule in plan.conditions
    }
    exposures = {
        schedule.condition: schedule.actual_eligible_exposure
        for schedule in plan.conditions
    }
    selected = {
        audit.plan_name: dict(audit.actual_selected_targets_by_condition)
        for audit in plan.seed_audits
    }
    population_evidence = {
        schedule.condition: {
            "train_sequences": schedule.sequence_count,
            "population_eligible_exposure": schedule.population_eligible_exposure,
            "overshoot": schedule.overshoot,
            "six_visits": dict(schedule.repetition_distribution).get(6, 0),
            "seven_visits": dict(schedule.repetition_distribution).get(7, 0),
        }
        for schedule in plan.conditions
    }
    expected_population_evidence = {
        condition: {
            key: value
            for key, value in evidence.items()
            if key != "validation_sequences"
        }
        for condition, evidence in _APPROVED_REAL_POPULATION_EVIDENCE.items()
    }
    exposure_values = tuple(exposures.values())
    primary_comparison_matches = bool(exposure_values) and (
        plan.minimum_eligible_exposure == min(exposure_values)
        and plan.maximum_eligible_exposure == max(exposure_values)
        and plan.exact_ratio_numerator == max(exposure_values)
        and plan.exact_ratio_denominator == min(exposure_values)
        and plan.exact_one_percent_passed is True
        and exact_one_percent_pass(exposure_values)
    )
    seed_comparisons_match = len(selected) == len(plan.seed_audits)
    for audit in plan.seed_audits:
        values = tuple(dict(audit.actual_selected_targets_by_condition).values())
        seed_comparisons_match = seed_comparisons_match and bool(values) and (
            audit.minimum_selected_targets == min(values)
            and audit.maximum_selected_targets == max(values)
            and audit.exact_ratio_numerator == max(values)
            and audit.exact_ratio_denominator == min(values)
            and audit.exact_one_percent_passed is True
            and exact_one_percent_pass(values)
        )
    if (
        len(appearances) != len(plan.conditions)
        or len(selected) != len(plan.seed_audits)
        or appearances != dict(_APPROVED_REAL_APPEARANCES)
        or exposures != dict(_APPROVED_REAL_ELIGIBLE_EXPOSURE)
        or population_evidence != expected_population_evidence
        or not primary_comparison_matches
        or not seed_comparisons_match
        or selected
        != {
            name: dict(values)
            for name, values in _APPROVED_REAL_SELECTED_TARGETS.items()
        }
    ):
        raise SchedulingContractError("canonical real schedule reference differs")


def _range_payload(values: Sequence[int]) -> dict[str, int]:
    if not values:
        raise SchedulingContractError("schedule range diagnostic is empty")
    return {"minimum": min(values), "maximum": max(values)}


def training_exposure_plan_payload(
    plan: TrainingExposurePlan,
    *,
    legacy_non_padding_projection: Mapping[str, int | float],
) -> dict[str, object]:
    """Return the smallest canonical independently regenerable schedule summary."""

    if set(legacy_non_padding_projection) != set(CONDITIONS):
        raise SchedulingContractError("legacy exposure diagnostic is incomplete")
    minimum_appearances = min(
        len(schedule.appearances) for schedule in plan.conditions
    )
    condition_payload: dict[str, object] = {}
    for schedule in plan.conditions:
        update_sequences = [
            update.schedule_end_cursor - update.schedule_start_cursor
            for update in schedule.updates
        ]
        update_eligible = [
            update.eligible_exposure for update in schedule.updates
        ]
        microbatch_counts = [
            len(update.microbatches) for update in schedule.updates
        ]
        microbatch_sequences = [
            microbatch.sequence_count
            for update in schedule.updates
            for microbatch in update.microbatches
        ]
        seed_ranges = {
            audit.plan_name: {
                "audit_protocol": audit.audit_protocol,
                "seed": audit.seed,
                "population_anchor_sha256": audit.population_anchor_sha256,
                "appearance_visit_sha256": audit.appearance_visit_sha256,
                "appearance_count": audit.appearance_count,
                "update_count": audit.update_count,
                "actual_selected_targets": audit.actual_selected_targets,
                "minimum_update_selected_targets": (
                    audit.minimum_update_selected_targets
                ),
                "maximum_update_selected_targets": (
                    audit.maximum_update_selected_targets
                ),
                "update_counts_sha256": audit.update_counts_sha256,
                "evidence_sha256": audit.evidence_sha256,
            }
            for audit in schedule.seed_audits
        }
        condition_payload[schedule.condition] = {
            "population_anchor_sha256": schedule.population_anchor_sha256,
            "population_sequence_count": schedule.sequence_count,
            "population_eligible_exposure": schedule.population_eligible_exposure,
            "sequence_appearances": len(schedule.appearances),
            "mean_source_population_repetition": {
                "ratio_numerator": len(schedule.appearances),
                "ratio_denominator": schedule.sequence_count,
                "ratio_decimal": (
                    len(schedule.appearances) / schedule.sequence_count
                ),
            },
            "complete_pass_count": COMPLETE_POPULATION_PASSES,
            "complete_pass_appearances": schedule.complete_pass_appearances,
            "residual_appearances": schedule.residual_appearances,
            "repetition_distribution": [
                {
                    "appearances_per_sequence": appearances,
                    "sequence_count": sequence_count,
                }
                for appearances, sequence_count in (
                    schedule.repetition_distribution
                )
            ],
            "nominal_eligible_target": schedule.nominal_target,
            "actual_eligible_exposure": schedule.actual_eligible_exposure,
            "whole_sequence_overshoot": schedule.overshoot,
            "expected_selected_targets": {
                "numerator": schedule.actual_eligible_exposure * 15,
                "denominator": 100,
            },
            "actual_selected_targets": seed_ranges,
            "scheduled_non_padding_positions": (
                schedule.scheduled_non_padding_positions
            ),
            "scheduled_padding_positions": schedule.scheduled_padding_positions,
            "scheduled_special_appearances": {
                "[CLS]": schedule.scheduled_cls_appearances,
                "[SEP]": schedule.scheduled_sep_appearances,
                "[UNK]": schedule.scheduled_unk_appearances,
                "[MASK]": schedule.scheduled_mask_appearances,
                "other": 0,
            },
            "relative_tensor_compute": {
                "tensor_positions": len(schedule.appearances)
                * MAX_SEQUENCE_LENGTH,
                "ratio_numerator": len(schedule.appearances),
                "ratio_denominator": minimum_appearances,
            },
            "legacy_projected_non_padding_wordpieces_diagnostic": (
                legacy_non_padding_projection[schedule.condition]
            ),
            "schedule_order_sha256": schedule.schedule_order_sha256,
            "update_plan_sha256": schedule.update_plan_sha256,
            "schedule_identity_sha256": schedule.identity_sha256,
            "updates": {
                "count": len(schedule.updates),
                "frontier_rule": "746 * one_based_optimizer_update",
                "sequence_count_range": _range_payload(update_sequences),
                "eligible_exposure_range": _range_payload(update_eligible),
                "microbatch_count_range": _range_payload(microbatch_counts),
                "microbatch_sequence_count_range": _range_payload(
                    microbatch_sequences
                ),
                "partial_final_microbatch_updates": sum(
                    update.microbatches[-1].sequence_count
                    < MAXIMUM_MICROBATCH_SEQUENCES
                    for update in schedule.updates
                ),
                "maximum_microbatch_sequences": (
                    MAXIMUM_MICROBATCH_SEQUENCES
                ),
                "maximum_microbatches_per_update": (
                    MAXIMUM_MICROBATCHES_PER_UPDATE
                ),
            },
        }
    return {
        "exposure_policy_protocol": EXPOSURE_POLICY_PROTOCOL,
        "eligibility_protocol": ELIGIBILITY_PROTOCOL,
        "eligibility_definition": (
            "attention_mask==1 and original_token_id not in "
            "{[PAD],[UNK],[CLS],[SEP],[MASK]}"
        ),
        "immutable_special_token_ids": dict(_SPECIAL_TOKEN_IDS),
        "schedule_protocol": SCHEDULE_PROTOCOL,
        "resume_policy_protocol": RESUME_POLICY_PROTOCOL,
        "seed_audit_protocol": SEED_AUDIT_PROTOCOL,
        "input_population_anchor_sha256": (
            plan.input_population_anchor_sha256
        ),
        "schedule_set_identity_sha256": (
            plan.schedule_set_identity_sha256
        ),
        "nominal_eligible_target": NOMINAL_ELIGIBLE_TARGET,
        "optimizer_updates": OPTIMIZER_UPDATES,
        "update_frontier_increment": UPDATE_FRONTIER_INCREMENT,
        "conditions": condition_payload,
        "eligible_exposure_comparison": {
            "minimum": plan.minimum_eligible_exposure,
            "maximum": plan.maximum_eligible_exposure,
            "ratio_numerator": plan.exact_ratio_numerator,
            "ratio_denominator": plan.exact_ratio_denominator,
            "ratio_decimal": (
                plan.exact_ratio_numerator
                / plan.exact_ratio_denominator
            ),
            "comparison": "100 * maximum <= 101 * minimum",
            "passed": plan.exact_one_percent_passed,
        },
        "selected_target_comparisons": {
            audit.plan_name: {
                "audit_protocol": audit.audit_protocol,
                "seed": audit.seed,
                "schedule_set_identity_sha256": (
                    audit.schedule_set_identity_sha256
                ),
                "condition_audit_evidence": {
                    condition_audit.condition: condition_audit.evidence_sha256
                    for condition_audit in audit.condition_audits
                },
                "by_condition": dict(
                    audit.actual_selected_targets_by_condition
                ),
                "minimum": audit.minimum_selected_targets,
                "maximum": audit.maximum_selected_targets,
                "ratio_numerator": audit.exact_ratio_numerator,
                "ratio_denominator": audit.exact_ratio_denominator,
                "ratio_decimal": (
                    audit.exact_ratio_numerator
                    / audit.exact_ratio_denominator
                ),
                "comparison": "100 * maximum <= 101 * minimum",
                "passed": audit.exact_one_percent_passed,
                "evidence_sha256": audit.evidence_sha256,
            }
            for audit in plan.seed_audits
        },
        "plan_identity_sha256": plan.identity_sha256,
    }


def validate_training_exposure_plan_payload(
    plan: TrainingExposurePlan,
    payload: object,
    *,
    legacy_non_padding_projection: Mapping[str, int | float],
) -> None:
    """Reject any serialized schedule or aggregate substitution."""

    expected = training_exposure_plan_payload(
        plan,
        legacy_non_padding_projection=legacy_non_padding_projection,
    )
    if not isinstance(payload, dict) or payload != expected:
        raise SchedulingContractError(
            "serialized training exposure plan does not regenerate"
        )


def _prefix_checksum(
    schedule: ConditionSchedule,
    end_cursor: int,
) -> str:
    return _sha256(
        [
            SCHEDULE_PROTOCOL,
            "ordered_schedule_prefix",
            schedule.condition,
            schedule.population_anchor_sha256,
            [
                _appearance_payload(appearance)
                for appearance in schedule.appearances[:end_cursor]
            ],
        ]
    )


def _visit_state_checksum(
    schedule: ConditionSchedule,
    end_cursor: int,
) -> str:
    visits = Counter(
        appearance.sequence_index
        for appearance in schedule.appearances[:end_cursor]
    )
    return _sha256(
        [
            SCHEDULE_PROTOCOL,
            "sequence_visit_state",
            schedule.condition,
            schedule.population_anchor_sha256,
            [[index, visits[index]] for index in range(schedule.sequence_count)],
        ]
    )


def _resume_position(
    schedule: ConditionSchedule,
    cursor: int,
) -> tuple[int, int]:
    if cursor < len(schedule.appearances):
        next_appearance = schedule.appearances[cursor]
        return next_appearance.pass_index, next_appearance.pass_cursor
    return COMPLETE_POPULATION_PASSES, schedule.residual_appearances


def derive_resume_state(
    schedule: ConditionSchedule,
    *,
    training_exposure_plan: TrainingExposurePlan,
    population_sequences: Iterable[PackedSequence],
    completed_optimizer_update: int,
    training_mask_seed: int,
    optimizer_state_reference: str,
    scheduler_state_reference: str,
    seed_authorization: PairedSeedTargetAudit | None = None,
) -> ResumeState:
    """Derive an update-boundary-only checkpoint state from the schedule."""

    update = _require_exact_nonnegative_integer(
        completed_optimizer_update,
        "completed optimizer update is invalid",
    )
    seed = _require_exact_nonnegative_integer(
        training_mask_seed,
        "training-mask seed is invalid",
    )
    if update not in CHECKPOINT_UPDATES:
        raise SchedulingContractError("resume update is not an approved checkpoint")
    material = tuple(population_sequences)
    validate_training_exposure_plan(training_exposure_plan, material)
    exact_schedule = next(
        (
            candidate
            for candidate in training_exposure_plan.conditions
            if candidate.condition == schedule.condition
        ),
        None,
    )
    if exact_schedule != schedule:
        raise SchedulingContractError(
            "resume schedule is not in the validated four-condition plan"
        )
    if seed_authorization is None:
        seed_authorization = next(
            (
                audit
                for audit in training_exposure_plan.seed_audits
                if audit.seed == seed
            ),
            None,
        )
    if (
        seed_authorization is None
        or seed_authorization.seed != seed
    ):
        raise SchedulingContractError("training-mask seed lacks a complete audit")
    validate_seed_authorization(
        training_exposure_plan,
        material,
        seed_authorization,
    )
    optimizer_reference = _require_sha256(
        optimizer_state_reference,
        "optimizer state reference is invalid",
    )
    scheduler_reference = _require_sha256(
        scheduler_state_reference,
        "scheduler state reference is invalid",
    )
    if update == 0:
        cursor = 0
        cumulative = 0
        credit = 0
    else:
        boundary = schedule.updates[update - 1]
        cursor = boundary.schedule_end_cursor
        cumulative = boundary.cumulative_eligible_exposure
        credit = boundary.token_credit
    population_pass, population_pass_cursor = _resume_position(
        schedule,
        cursor,
    )
    state = object.__new__(ResumeState)
    values = {
        "resume_policy_protocol": RESUME_POLICY_PROTOCOL,
        "seed_audit_protocol": SEED_AUDIT_PROTOCOL,
        "schedule_protocol": SCHEDULE_PROTOCOL,
        "input_population_anchor_sha256": (
            training_exposure_plan.input_population_anchor_sha256
        ),
        "schedule_set_identity_sha256": (
            training_exposure_plan.schedule_set_identity_sha256
        ),
        "seed_authorization_evidence_sha256": (
            seed_authorization.evidence_sha256
        ),
        "schedule_identity_sha256": schedule.identity_sha256,
        "condition": schedule.condition,
        "nominal_target": NOMINAL_ELIGIBLE_TARGET,
        "completed_optimizer_update": update,
        "checkpoint_update": update,
        "schedule_cursor": cursor,
        "population_pass": population_pass,
        "population_pass_cursor": population_pass_cursor,
        "cumulative_eligible_exposure": cumulative,
        "token_credit": credit,
        "visit_state_sha256": _visit_state_checksum(schedule, cursor),
        "training_mask_seed": seed,
        "ordered_prefix_sha256": _prefix_checksum(schedule, cursor),
        "optimizer_state_reference": optimizer_reference,
        "scheduler_state_reference": scheduler_reference,
        "at_update_boundary": True,
    }
    for name, value in values.items():
        object.__setattr__(state, name, value)
    return state


def validate_resume_state(
    schedule: ConditionSchedule,
    state: ResumeState,
    *,
    training_exposure_plan: TrainingExposurePlan,
    population_sequences: Iterable[PackedSequence],
    checkpoint_update: int,
    seed_authorization: PairedSeedTargetAudit | None = None,
) -> tuple[SequenceAppearance, ...]:
    """Validate a checkpoint claim and return the exact regenerated suffix."""

    if type(state) is not ResumeState or state.at_update_boundary is not True:
        raise SchedulingContractError("mid-update resume is prohibited")
    checkpoint = _require_exact_nonnegative_integer(
        checkpoint_update,
        "checkpoint update is invalid",
    )
    expected = derive_resume_state(
        schedule,
        training_exposure_plan=training_exposure_plan,
        population_sequences=population_sequences,
        completed_optimizer_update=state.completed_optimizer_update,
        training_mask_seed=state.training_mask_seed,
        optimizer_state_reference=state.optimizer_state_reference,
        scheduler_state_reference=state.scheduler_state_reference,
        seed_authorization=seed_authorization,
    )
    if state != expected or checkpoint != state.checkpoint_update:
        raise SchedulingContractError("checkpoint schedule state is incompatible")
    return schedule.appearances[state.schedule_cursor :]


def scheduling_contract_payload() -> dict[str, object]:
    """Canonical production-bound scheduling, seed-audit, and resume API."""

    return {
        "eligibility_protocol": ELIGIBILITY_PROTOCOL,
        "exposure_policy_protocol": EXPOSURE_POLICY_PROTOCOL,
        "schedule_protocol": SCHEDULE_PROTOCOL,
        "resume_policy_protocol": RESUME_POLICY_PROTOCOL,
        "nominal_eligible_target": NOMINAL_ELIGIBLE_TARGET,
        "complete_population_passes": COMPLETE_POPULATION_PASSES,
        "optimizer_updates": OPTIMIZER_UPDATES,
        "update_frontier_increment": UPDATE_FRONTIER_INCREMENT,
        "maximum_microbatch_sequences": MAXIMUM_MICROBATCH_SEQUENCES,
        "maximum_microbatches_per_update": MAXIMUM_MICROBATCHES_PER_UPDATE,
        "checkpoint_updates": list(CHECKPOINT_UPDATES),
        "immutable_special_token_ids": dict(
            approved_special_token_mapping()
        ),
        "api": [
            build_condition_schedule.__name__,
            build_training_exposure_plan.__name__,
            validate_condition_schedule.__name__,
            validate_training_exposure_plan.__name__,
            audit_training_mask_seed.__name__,
            audit_future_paired_training_mask_seed.__name__,
            validate_seed_authorization.__name__,
            derive_resume_state.__name__,
            validate_resume_state.__name__,
            training_exposure_plan_payload.__name__,
            validate_training_exposure_plan_payload.__name__,
            validate_canonical_real_reference.__name__,
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
