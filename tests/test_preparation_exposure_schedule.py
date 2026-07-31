from __future__ import annotations

import copy
import inspect
import json
import os
import subprocess
import sys
import traceback
from dataclasses import fields, replace
from hashlib import sha256
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import pytest

import cslm.modeling.eligibility as eligibility_module
import cslm.modeling.scheduling as scheduling_module
from cslm.modeling.config import CONDITIONS
from cslm.modeling.eligibility import (
    EligibilityContractError,
    approved_special_token_mapping,
    derive_mask_eligibility,
)
from cslm.modeling.masking import mask_packed_sequence as real_mask_packed_sequence
from cslm.modeling.packing import (
    PackedSequence,
    PackingContractError,
    PackingRow,
    pack_rows,
)
from cslm.modeling.scheduling import (
    NOMINAL_ELIGIBLE_TARGET,
    OPTIMIZER_UPDATES,
    PairedSeedTargetAudit,
    ResumeState,
    SchedulingContractError,
    SeedTargetAudit,
    audit_future_paired_training_mask_seed,
    audit_training_mask_seed,
    build_condition_schedule,
    build_training_exposure_plan,
    derive_resume_state,
    exact_one_percent_pass,
    scheduling_contract_payload,
    training_exposure_plan_payload,
    validate_canonical_real_reference,
    validate_condition_schedule,
    validate_resume_state,
    validate_seed_authorization,
    validate_training_exposure_plan_payload,
)
from cslm.modeling.training_contract import (
    GradientClippingAuthorization,
    MicrobatchLoss,
    NormalizedUpdateLoss,
    TrainingContractError,
    authorize_adamw_step,
    authorize_gradient_clipping,
    loss_normalization_contract_payload,
    normalize_complete_update_loss,
)


def _packed(
    *,
    condition: str = "EnglishMono",
    index: int = 0,
    eligible: int = 126,
    identity_prefix: str = "sequence",
) -> PackedSequence:
    if not 0 <= eligible <= 126:
        raise ValueError("synthetic eligible count is outside one packed sequence")
    lexical = (
        (1,)
        if eligible == 0
        else tuple(
            5 + ((index + offset) % 7_990)
            for offset in range(eligible)
        )
    )
    attended_ids = (2, *lexical, 3)
    padding = 128 - len(attended_ids)
    identity = sha256(
        f"{identity_prefix}:{condition}:{index}".encode("ascii")
    ).hexdigest()
    return PackedSequence(
        condition=condition,
        split="train",
        input_ids=(*attended_ids, *((0,) * padding)),
        attention_mask=(*((1,) * len(attended_ids)), *((0,) * padding)),
        token_type_ids=(0,) * 128,
        provenance=(),
        example_identity=identity,
    )


def _unsafe_packed_copy(
    sequence: PackedSequence,
    **changes: object,
) -> PackedSequence:
    copied = object.__new__(PackedSequence)
    for item in fields(PackedSequence):
        object.__setattr__(
            copied,
            item.name,
            changes.get(item.name, getattr(sequence, item.name)),
        )
    return copied


def _packing_row(
    row_id: str,
    token_ids: tuple[int, ...],
    *,
    row_order: int,
) -> PackingRow:
    return PackingRow(
        condition="CsCont",
        split="train",
        source="synthetic_source",
        component="bangor_natural_span",
        document_id="synthetic_document",
        conversation_id="synthetic_conversation",
        span_id="synthetic_span",
        row_id=row_id,
        row_order=row_order,
        token_ids=token_ids,
        lexical_token_count=len(token_ids),
    )


def _population(
    condition: str,
    *,
    full_sequences: int = 850,
    zero_sequences: int = 0,
) -> tuple[PackedSequence, ...]:
    return tuple(
        [
            *(
                _packed(condition=condition, index=index)
                for index in range(full_sequences)
            ),
            *(
                _packed(
                    condition=condition,
                    index=full_sequences + index,
                    eligible=0,
                )
                for index in range(zero_sequences)
            ),
        ]
    )


def _one_selected_target(*args: object, **kwargs: object) -> SimpleNamespace:
    del args, kwargs
    return SimpleNamespace(selected_positions=(1,))


@pytest.fixture(scope="module")
def fast_plan():
    populations = {
        condition: _population(condition) for condition in CONDITIONS
    }
    sequences = tuple(
        sequence
        for condition in CONDITIONS
        for sequence in populations[condition]
    )
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            scheduling_module,
            "mask_packed_sequence",
            _one_selected_target,
        )
        plan = build_training_exposure_plan(
            sequences,
            input_population_anchor_sha256="a" * 64,
        )
        yield plan, populations, sequences


def test_authoritative_eligibility_includes_punctuation_and_excludes_specials() -> None:
    sequence = _packed(eligible=4)
    values = list(sequence.input_ids)
    values[1:5] = [5, 6, 7, 1]
    profile = derive_mask_eligibility(
        tuple(values),
        sequence.attention_mask,
    )
    assert profile.eligible_positions[:6] == (
        False,
        True,
        True,
        True,
        False,
        False,
    )
    assert profile.eligible_count == 3
    assert profile.unk_count == 1
    assert profile.cls_count == profile.sep_count == 1
    assert profile.mask_count == 0
    assert profile.padding_count == 122


def test_punctuation_only_bangor_wordpiece_remains_eligible() -> None:
    sequence = _packed(eligible=1)
    values = list(sequence.input_ids)
    values[1] = 7
    profile = derive_mask_eligibility(tuple(values), sequence.attention_mask)
    assert profile.eligible_positions[1] is True
    assert profile.eligible_count == 1


def test_input_mask_is_prohibited_and_padding_is_ineligible() -> None:
    sequence = _packed(eligible=1)
    profile = derive_mask_eligibility(
        sequence.input_ids,
        sequence.attention_mask,
    )
    assert not any(profile.eligible_positions[3:])
    values = list(sequence.input_ids)
    values[1] = 4
    with pytest.raises(EligibilityContractError, match="special-token"):
        derive_mask_eligibility(tuple(values), sequence.attention_mask)
    with pytest.raises(PackingContractError, match="input contract"):
        replace(sequence, input_ids=tuple(values))


def test_direct_eligibility_rejects_internal_or_repeated_cls() -> None:
    sequence = _packed(eligible=3)
    for position in (1, 2):
        values = list(sequence.input_ids)
        values[position] = 2
        with pytest.raises(EligibilityContractError, match="special-token"):
            derive_mask_eligibility(tuple(values), sequence.attention_mask)


def test_authoritative_multirow_separator_layout_accepts_valid_rows() -> None:
    sequence = pack_rows(
        (
            _packing_row("row-1", (7, 1), row_order=0),
            _packing_row("row-2", (8,), row_order=1),
        )
    ).sequences[0]
    assert sequence.input_ids[:7] == (2, 7, 1, 3, 8, 3, 0)
    assert tuple(item.packed_token_end for item in sequence.provenance) == (3, 5)
    profile = derive_mask_eligibility(
        sequence.input_ids,
        sequence.attention_mask,
    )
    assert profile.eligible_count == 2
    assert profile.unk_count == 1
    assert profile.sep_count == 2


@pytest.mark.parametrize(
    "mutation",
    (
        "extra_separator",
        "missing_separator",
        "shifted_separator",
        "consecutive_separator",
        "provenance_mismatch",
    ),
)
def test_authoritative_multirow_separator_layout_rejects_tampering(
    mutation: str,
) -> None:
    sequence = pack_rows(
        (
            _packing_row("row-1", (7, 8), row_order=0),
            _packing_row("row-2", (9, 10), row_order=1),
        )
    ).sequences[0]
    values = list(sequence.input_ids)
    provenance = sequence.provenance
    if mutation == "extra_separator":
        values[2] = 3
    elif mutation == "missing_separator":
        values[3] = 11
    elif mutation == "shifted_separator":
        values[2], values[3] = 3, 11
    elif mutation == "consecutive_separator":
        values[4] = 3
    else:
        first = provenance[0]
        altered = replace(first, packed_token_end=first.packed_token_end + 1)
        provenance = (altered, *provenance[1:])
    with pytest.raises(PackingContractError, match="separator|provenance"):
        replace(
            sequence,
            input_ids=tuple(values),
            provenance=provenance,
        )


def test_multirow_layout_without_authoritative_provenance_fails() -> None:
    sequence = pack_rows(
        (
            _packing_row("row-1", (7,), row_order=0),
            _packing_row("row-2", (8,), row_order=1),
        )
    ).sequences[0]
    with pytest.raises(PackingContractError, match="authoritative provenance"):
        replace(sequence, provenance=())


@pytest.mark.parametrize(
    ("ids_mutator", "mask_mutator"),
    [
        (lambda values: values[:-1], lambda values: values),
        (lambda values: [*values[:1], True, *values[2:]], lambda values: values),
        (lambda values: [*values[:1], -1, *values[2:]], lambda values: values),
        (lambda values: [*values[:1], 8_000, *values[2:]], lambda values: values),
        (lambda values: values, lambda values: values[:-1]),
        (lambda values: values, lambda values: [True, *values[1:]]),
        (lambda values: values, lambda values: [2, *values[1:]]),
        (lambda values: values, lambda values: [*values[:-1], 1]),
    ],
)
def test_eligibility_rejects_malformed_values_and_shapes(
    ids_mutator,
    mask_mutator,
) -> None:
    sequence = _packed(eligible=2)
    with pytest.raises(EligibilityContractError):
        derive_mask_eligibility(
            ids_mutator(list(sequence.input_ids)),
            mask_mutator(list(sequence.attention_mask)),
        )


def test_public_special_token_replacement_cannot_change_eligibility(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    approved = approved_special_token_mapping()
    assert isinstance(approved, type(MappingProxyType({})))
    with pytest.raises(TypeError):
        approved["[UNK]"] = 99  # type: ignore[index]
    monkeypatch.setattr(
        eligibility_module,
        "_APPROVED_SPECIAL_TOKEN_IDS",
        MappingProxyType(
            {"[PAD]": 99, "[UNK]": 98, "[CLS]": 97, "[SEP]": 96, "[MASK]": 95}
        ),
    )
    sequence = _packed(eligible=1)
    assert derive_mask_eligibility(
        sequence.input_ids,
        sequence.attention_mask,
    ).eligible_count == 1


def test_exact_one_percent_integer_boundary() -> None:
    assert exact_one_percent_pass((100, 101))
    assert not exact_one_percent_pass((100, 102))
    with pytest.raises(SchedulingContractError):
        exact_one_percent_pass((True, 100))


def test_schedule_has_exact_complete_passes_residual_and_repetitions(
    fast_plan,
) -> None:
    plan, _, _ = fast_plan
    assert plan.exact_one_percent_passed is True
    assert plan.minimum_eligible_exposure == 746_046
    assert plan.maximum_eligible_exposure == 746_046
    for schedule in plan.conditions:
        assert schedule.complete_pass_appearances == 6 * schedule.sequence_count
        assert 0 < schedule.residual_appearances <= schedule.sequence_count
        assert schedule.repetition_distribution == ((6, 29), (7, 821))
        assert {appearance.visit for appearance in schedule.appearances} == set(
            range(7)
        )
        assert all(
            appearance.pass_index == appearance.visit
            for appearance in schedule.appearances
        )
        assert schedule.actual_eligible_exposure == 746_046
        assert schedule.overshoot == 46
        assert max(
            count
            for _, count in schedule.repetition_distribution
        ) < schedule.sequence_count


def test_updates_credit_frontiers_and_microbatches_are_exact(fast_plan) -> None:
    plan, _, _ = fast_plan
    for schedule in plan.conditions:
        assert len(schedule.updates) == OPTIMIZER_UPDATES
        assert schedule.updates[-1].schedule_end_cursor == len(
            schedule.appearances
        )
        for expected_update, update in enumerate(schedule.updates, start=1):
            assert update.update == expected_update
            assert update.cumulative_frontier == 746 * expected_update
            assert update.token_credit == (
                update.cumulative_eligible_exposure
                - update.cumulative_frontier
            )
            assert 1 <= len(update.microbatches) <= 6
            assert all(
                1 <= microbatch.sequence_count <= 16
                for microbatch in update.microbatches
            )
            assert update.microbatches[0].schedule_start_cursor == (
                update.schedule_start_cursor
            )
            assert update.microbatches[-1].schedule_end_cursor == (
                update.schedule_end_cursor
            )
            assert all(
                count > 0
                for _, count in update.selected_targets_by_seed
            )
    assert all(
        update.microbatches[-1].sequence_count < 16
        for update in plan.conditions[0].updates
    )


def test_schedule_is_deterministic_and_tampering_does_not_establish_authority(
    fast_plan,
) -> None:
    plan, populations, _ = fast_plan
    schedule = plan.conditions[0]
    repeated = build_condition_schedule(
        populations[schedule.condition],
        input_population_anchor_sha256="a" * 64,
    )
    assert repeated == schedule
    validate_condition_schedule(schedule, populations[schedule.condition])
    tampered = replace(
        schedule,
        actual_eligible_exposure=schedule.actual_eligible_exposure + 1,
    )
    with pytest.raises(SchedulingContractError, match="regenerate"):
        validate_condition_schedule(
            tampered,
            populations[schedule.condition],
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "identity",
        "visit",
        "condition",
        "population_anchor",
        "permutation",
        "pass",
        "residual",
        "cursor",
        "credit",
        "frontier",
        "update",
        "microbatch",
        "repetition",
        "target",
        "checksum",
    ],
)
def test_schedule_semantic_mutations_fail_regeneration(
    fast_plan,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    plan, populations, _ = fast_plan
    authoritative = plan.conditions[0]
    monkeypatch.setattr(
        scheduling_module,
        "build_condition_schedule",
        lambda *args, **kwargs: authoritative,
    )
    appearances = list(authoritative.appearances)
    updates = list(authoritative.updates)
    tampered = authoritative
    if mutation == "identity":
        appearances[0] = replace(
            appearances[0],
            sequence_identity="0" * 64,
        )
        tampered = replace(tampered, appearances=tuple(appearances))
    elif mutation == "visit":
        appearances[0] = replace(
            appearances[0],
            visit=appearances[0].visit + 1,
        )
        tampered = replace(tampered, appearances=tuple(appearances))
    elif mutation == "condition":
        tampered = replace(tampered, condition="SpanishMono")
    elif mutation == "population_anchor":
        tampered = replace(tampered, population_anchor_sha256="0" * 64)
    elif mutation == "permutation":
        appearances[:2] = reversed(appearances[:2])
        tampered = replace(tampered, appearances=tuple(appearances))
    elif mutation == "pass":
        appearances[0] = replace(
            appearances[0],
            pass_index=appearances[0].pass_index + 1,
        )
        tampered = replace(tampered, appearances=tuple(appearances))
    elif mutation == "residual":
        tampered = replace(
            tampered,
            residual_appearances=tampered.residual_appearances + 1,
        )
    elif mutation == "cursor":
        updates[0] = replace(
            updates[0],
            schedule_end_cursor=updates[0].schedule_end_cursor + 1,
        )
        tampered = replace(tampered, updates=tuple(updates))
    elif mutation == "credit":
        updates[0] = replace(
            updates[0],
            token_credit=updates[0].token_credit + 1,
        )
        tampered = replace(tampered, updates=tuple(updates))
    elif mutation == "frontier":
        updates[0] = replace(
            updates[0],
            cumulative_frontier=updates[0].cumulative_frontier + 1,
        )
        tampered = replace(tampered, updates=tuple(updates))
    elif mutation == "update":
        updates[0] = replace(updates[0], update=2)
        tampered = replace(tampered, updates=tuple(updates))
    elif mutation == "microbatch":
        microbatches = list(updates[0].microbatches)
        microbatches[0] = replace(
            microbatches[0],
            sequence_count=microbatches[0].sequence_count + 1,
        )
        updates[0] = replace(
            updates[0],
            microbatches=tuple(microbatches),
        )
        tampered = replace(tampered, updates=tuple(updates))
    elif mutation == "repetition":
        tampered = replace(tampered, repetition_distribution=((6, 850),))
    elif mutation == "target":
        tampered = replace(
            tampered,
            nominal_target=tampered.nominal_target + 1,
        )
    elif mutation == "checksum":
        tampered = replace(tampered, update_plan_sha256="0" * 64)
    with pytest.raises(SchedulingContractError, match="does not regenerate"):
        validate_condition_schedule(
            tampered,
            populations[authoritative.condition],
        )


def test_permutation_domain_separates_condition_population_anchor_and_pass() -> None:
    sequences = _population("EnglishMono")[:5]
    base = scheduling_module._permutation_digest(
        input_population_anchor_sha256="a" * 64,
        population_anchor_sha256="b" * 64,
        condition="EnglishMono",
        pass_index=0,
        sequence_identity=sequences[0].example_identity,
    )
    variants = {
        scheduling_module._permutation_digest(
            input_population_anchor_sha256="c" * 64,
            population_anchor_sha256="b" * 64,
            condition="EnglishMono",
            pass_index=0,
            sequence_identity=sequences[0].example_identity,
        ),
        scheduling_module._permutation_digest(
            input_population_anchor_sha256="a" * 64,
            population_anchor_sha256="c" * 64,
            condition="EnglishMono",
            pass_index=0,
            sequence_identity=sequences[0].example_identity,
        ),
        scheduling_module._permutation_digest(
            input_population_anchor_sha256="a" * 64,
            population_anchor_sha256="b" * 64,
            condition="SpanishMono",
            pass_index=0,
            sequence_identity=sequences[0].example_identity,
        ),
        scheduling_module._permutation_digest(
            input_population_anchor_sha256="a" * 64,
            population_anchor_sha256="b" * 64,
            condition="EnglishMono",
            pass_index=1,
            sequence_identity=sequences[0].example_identity,
        ),
    }
    assert base not in variants
    assert len(variants) == 4


def test_permutation_collision_uses_only_canonical_index_as_tie_breaker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sequences = tuple(reversed(_population("EnglishMono")[:7]))
    monkeypatch.setattr(
        scheduling_module,
        "_permutation_digest",
        lambda **kwargs: "0" * 64,
    )
    assert scheduling_module._pass_permutation(
        input_population_anchor_sha256="a" * 64,
        population_anchor_sha256="b" * 64,
        condition="EnglishMono",
        pass_index=0,
        sequences=sequences,
    ) == tuple(range(7))


def test_python_hash_seed_does_not_change_permutation() -> None:
    root = Path(__file__).resolve().parents[1]
    code = """
import json
from hashlib import sha256
from cslm.modeling.packing import PackedSequence
from cslm.modeling.scheduling import _pass_permutation
sequences = tuple(
    PackedSequence(
        "EnglishMono", "train", (2, 5, 3) + (0,) * 125,
        (1, 1, 1) + (0,) * 125, (0,) * 128, (),
        sha256(f"identity:{index}".encode()).hexdigest(),
    )
    for index in range(20)
)
print(json.dumps(_pass_permutation(
    input_population_anchor_sha256="a" * 64,
    population_anchor_sha256="b" * 64,
    condition="EnglishMono",
    pass_index=2,
    sequences=sequences,
)))
"""
    outputs = []
    for seed in ("1", "987654"):
        environment = {
            **os.environ,
            "PYTHONHASHSEED": seed,
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": str(root / "src"),
        }
        outputs.append(
            subprocess.run(
                [sys.executable, "-c", code],
                check=True,
                capture_output=True,
                text=True,
                env=environment,
            ).stdout
        )
    assert outputs[0] == outputs[1]


def test_zero_eligible_sequences_are_covered_without_looping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        scheduling_module,
        "mask_packed_sequence",
        _one_selected_target,
    )
    sequences = _population(
        "EnglishMono",
        full_sequences=850,
        zero_sequences=10,
    )
    schedule = build_condition_schedule(
        sequences,
        input_population_anchor_sha256="a" * 64,
    )
    counts = {
        index: 0 for index in range(len(sequences))
    }
    for appearance in schedule.appearances:
        counts[appearance.sequence_index] += 1
    assert set(counts.values()) <= {6, 7}
    assert all(count >= 6 for count in counts.values())


def test_zero_total_duplicate_and_insufficient_populations_fail() -> None:
    zeros = tuple(
        _packed(index=index, eligible=0) for index in range(5)
    )
    with pytest.raises(SchedulingContractError, match="zero eligible"):
        build_condition_schedule(
            zeros,
            input_population_anchor_sha256="a" * 64,
        )
    duplicate = (_packed(index=0), _packed(index=0))
    with pytest.raises(SchedulingContractError, match="not unique"):
        build_condition_schedule(
            duplicate,
            input_population_anchor_sha256="a" * 64,
        )
    with pytest.raises(SchedulingContractError, match="cannot reach"):
        build_condition_schedule(
            (_packed(index=1),),
            input_population_anchor_sha256="a" * 64,
        )


@pytest.mark.parametrize(
    "mutation",
    (
        "unknown_condition",
        "missing_condition",
        "extra_fifth_condition",
        "validation_member",
        "test_member",
        "duplicate_within_condition",
        "duplicate_across_conditions",
        "identical_across_all_conditions",
        "cross_condition_substitution",
    ),
)
def test_four_condition_population_is_exact_and_globally_distinct(
    fast_plan,
    mutation: str,
) -> None:
    _, _, sequences = fast_plan
    altered = list(sequences)
    if mutation == "missing_condition":
        altered = [
            sequence
            for sequence in altered
            if sequence.condition != "CsCont"
        ]
    elif mutation in {"unknown_condition", "extra_fifth_condition"}:
        altered.append(
            _unsafe_packed_copy(
                altered[0],
                condition=(
                    "Unknown"
                    if mutation == "unknown_condition"
                    else "FifthCondition"
                ),
                example_identity=sha256(mutation.encode()).hexdigest(),
            )
        )
    elif mutation in {"validation_member", "test_member"}:
        altered[0] = _unsafe_packed_copy(
            altered[0],
            split="validation" if mutation == "validation_member" else "test",
        )
    elif mutation == "duplicate_within_condition":
        altered[1] = replace(
            altered[1],
            example_identity=altered[0].example_identity,
        )
    elif mutation == "duplicate_across_conditions":
        other = next(
            index
            for index, sequence in enumerate(altered)
            if sequence.condition == "SpanishMono"
        )
        altered[other] = replace(
            altered[other],
            example_identity=altered[0].example_identity,
        )
    elif mutation == "identical_across_all_conditions":
        shared = altered[0].example_identity
        for condition in CONDITIONS[1:]:
            index = next(
                index
                for index, sequence in enumerate(altered)
                if sequence.condition == condition
            )
            altered[index] = replace(altered[index], example_identity=shared)
    else:
        other = next(
            index
            for index, sequence in enumerate(altered)
            if sequence.condition == "SpanishMono"
        )
        altered[other] = _unsafe_packed_copy(
            altered[0],
            condition="SpanishMono",
        )
    with pytest.raises(SchedulingContractError, match="four|distinct"):
        build_training_exposure_plan(
            altered,
            input_population_anchor_sha256="a" * 64,
        )


def test_exact_population_reconciliation_preserves_condition_bound_reuse(
    fast_plan,
) -> None:
    plan, _, sequences = fast_plan
    assert sum(schedule.sequence_count for schedule in plan.conditions) == len(
        sequences
    )
    assert len(
        {
            appearance.sequence_identity
            for schedule in plan.conditions
            for appearance in schedule.appearances[
                : schedule.complete_pass_appearances
            ]
        }
    ) == len(sequences)

    shared_rows = {
        condition: PackingRow(
            condition=condition,
            split="train",
            source="synthetic_shared_source",
            component="synthetic_authorized_reuse",
            document_id="synthetic_shared_document",
            conversation_id="synthetic_shared_conversation",
            span_id=None,
            row_id="synthetic_shared_row",
            row_order=0,
            token_ids=tuple(5 + index for index in range(126)),
            lexical_token_count=126,
            language_shard="english" if condition == "MonoCont" else None,
        )
        for condition in ("MonoCont", "CsCont")
    }
    reused = {
        condition: pack_rows((row,)).sequences[0]
        for condition, row in shared_rows.items()
    }
    assert (
        reused["MonoCont"].provenance[0].row_id
        == reused["CsCont"].provenance[0].row_id
    )
    assert (
        reused["MonoCont"].example_identity
        != reused["CsCont"].example_identity
    )
    replaced = list(sequences)
    for condition, sequence in reused.items():
        index = next(
            index
            for index, existing in enumerate(replaced)
            if existing.condition == condition
        )
        replaced[index] = sequence
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            scheduling_module,
            "mask_packed_sequence",
            _one_selected_target,
        )
        reused_plan = build_training_exposure_plan(
            replaced,
            input_population_anchor_sha256="b" * 64,
        )
    assert sum(
        schedule.sequence_count for schedule in reused_plan.conditions
    ) == len(replaced)


def test_more_than_six_microbatches_is_rejected() -> None:
    appearances = tuple(
        scheduling_module.SequenceAppearance(
            cursor=index,
            pass_index=0,
            pass_cursor=index,
            sequence_index=index,
            sequence_identity=sha256(str(index).encode()).hexdigest(),
            visit=0,
            eligible_count=7,
        )
        for index in range(107)
    )
    selected = tuple((1, 1, 1, 1) for _ in appearances)
    with pytest.raises(SchedulingContractError, match="more than six"):
        scheduling_module._build_updates(
            appearances=appearances,
            selected_counts=selected,
            seed_plans=scheduling_module.approved_training_mask_seed_plans(),
        )


def test_update_with_zero_actual_targets_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        scheduling_module,
        "mask_packed_sequence",
        lambda *args, **kwargs: SimpleNamespace(selected_positions=()),
    )
    with pytest.raises(SchedulingContractError, match="zero selected"):
        build_condition_schedule(
            _population("EnglishMono"),
            input_population_anchor_sha256="a" * 64,
        )


def test_each_approved_seed_is_independently_audited(fast_plan) -> None:
    plan, _, _ = fast_plan
    expected = {
        "tiny_smoke_1": 11_729,
        "small_1": 281_828,
        "small_2": 324_159,
        "small_3": 171_803,
    }
    assert {
        audit.plan_name: audit.seed for audit in plan.seed_audits
    } == expected
    assert all(
        audit.exact_one_percent_passed for audit in plan.seed_audits
    )
    assert all(
        set(dict(audit.actual_selected_targets_by_condition))
        == set(CONDITIONS)
        for audit in plan.seed_audits
    )


def test_future_seed_requires_independent_condition_and_paired_audits(
    fast_plan,
) -> None:
    plan, populations, sequences = fast_plan
    condition_audit = audit_training_mask_seed(
        plan.conditions[0],
        populations[plan.conditions[0].condition],
        plan_name="future_1",
        seed=999_983,
    )
    assert condition_audit.seed == 999_983
    with pytest.raises(SchedulingContractError, match="lacks"):
        derive_resume_state(
            plan.conditions[0],
            training_exposure_plan=plan,
            population_sequences=sequences,
            completed_optimizer_update=250,
            training_mask_seed=999_983,
            optimizer_state_reference="d" * 64,
            scheduler_state_reference="e" * 64,
        )
    with pytest.raises(SchedulingContractError, match="four-condition"):
        derive_resume_state(
            plan.conditions[0],
            training_exposure_plan=plan,
            population_sequences=sequences,
            completed_optimizer_update=250,
            training_mask_seed=999_983,
            optimizer_state_reference="d" * 64,
            scheduler_state_reference="e" * 64,
            seed_authorization=condition_audit,  # type: ignore[arg-type]
        )
    paired = audit_future_paired_training_mask_seed(
        plan,
        sequences,
        plan_name="future_1",
        seed=999_983,
    )
    assert paired.exact_one_percent_passed is True
    future_resume = derive_resume_state(
        plan.conditions[0],
        training_exposure_plan=plan,
        population_sequences=sequences,
        completed_optimizer_update=250,
        training_mask_seed=999_983,
        optimizer_state_reference="d" * 64,
        scheduler_state_reference="e" * 64,
        seed_authorization=paired,
    )
    assert future_resume.training_mask_seed == 999_983
    with pytest.raises(SchedulingContractError, match="already reviewed"):
        audit_training_mask_seed(
            plan.conditions[0],
            populations[plan.conditions[0].condition],
            plan_name="tiny_smoke_1",
            seed=11_729,
        )


def test_failing_future_seed_stops_without_reseed(
    fast_plan,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan, populations, _ = fast_plan
    requested_seed = 999_979
    observed: list[int] = []

    def selective_mask(*args: object, seed: int, **kwargs: object) -> SimpleNamespace:
        del args, kwargs
        observed.append(seed)
        return SimpleNamespace(
            selected_positions=()
            if seed == requested_seed
            else (1,)
        )

    monkeypatch.setattr(
        scheduling_module,
        "mask_packed_sequence",
        selective_mask,
    )
    schedule = plan.conditions[0]
    with pytest.raises(SchedulingContractError, match="zero-target"):
        audit_training_mask_seed(
            schedule,
            populations[schedule.condition],
            plan_name="future_failure",
            seed=requested_seed,
        )
    unreviewed = {
        seed
        for seed in observed
        if seed
        not in {
            value
            for _, value in (
                scheduling_module.approved_training_mask_seed_plans()
            )
        }
    }
    assert unreviewed == {requested_seed}


@pytest.mark.parametrize(
    "mutation",
    [
        "target",
        "overshoot",
        "seed",
        "condition_anchor",
        "schedule_checksum",
        "update_checksum",
        "repetition",
        "frontier",
        "microbatch_range",
        "plan_checksum",
    ],
)
def test_serialized_schedule_aggregate_substitution_fails(
    fast_plan,
    mutation: str,
) -> None:
    plan, _, _ = fast_plan
    legacy = {condition: 1_000_000.0 for condition in CONDITIONS}
    payload = training_exposure_plan_payload(
        plan,
        legacy_non_padding_projection=legacy,
    )
    tampered = copy.deepcopy(payload)
    condition = CONDITIONS[0]
    record = tampered["conditions"][condition]
    if mutation == "target":
        record["nominal_eligible_target"] += 1
    elif mutation == "overshoot":
        record["whole_sequence_overshoot"] += 1
    elif mutation == "seed":
        tampered["selected_target_comparisons"]["tiny_smoke_1"]["seed"] += 1
    elif mutation == "condition_anchor":
        record["population_anchor_sha256"] = "0" * 64
    elif mutation == "schedule_checksum":
        record["schedule_order_sha256"] = "0" * 64
    elif mutation == "update_checksum":
        record["update_plan_sha256"] = "0" * 64
    elif mutation == "repetition":
        record["repetition_distribution"][0]["sequence_count"] += 1
    elif mutation == "frontier":
        record["updates"]["frontier_rule"] = "caller frontier"
    elif mutation == "microbatch_range":
        record["updates"]["microbatch_sequence_count_range"]["maximum"] = 17
    elif mutation == "plan_checksum":
        tampered["plan_identity_sha256"] = "0" * 64
    with pytest.raises(SchedulingContractError, match="does not regenerate"):
        validate_training_exposure_plan_payload(
            plan,
            tampered,
            legacy_non_padding_projection=legacy,
        )


def test_schedule_payload_binds_diagnostics_and_contract_apis(fast_plan) -> None:
    plan, _, _ = fast_plan
    legacy = {
        condition: float(index + 1)
        for index, condition in enumerate(CONDITIONS)
    }
    payload = training_exposure_plan_payload(
        plan,
        legacy_non_padding_projection=legacy,
    )
    assert payload["immutable_special_token_ids"] == {
        "[PAD]": 0,
        "[UNK]": 1,
        "[CLS]": 2,
        "[SEP]": 3,
        "[MASK]": 4,
    }
    assert payload["nominal_eligible_target"] == NOMINAL_ELIGIBLE_TARGET
    assert payload["optimizer_updates"] == 1_000
    assert payload["eligible_exposure_comparison"]["passed"] is True
    assert scheduling_contract_payload()["checkpoint_updates"] == [
        0,
        250,
        500,
        750,
        1_000,
    ]
    assert loss_normalization_contract_payload()["operation_order"][-2:] == [
        "clip_gradients",
        "one_adamw_step",
    ]
    assert "hmac" not in inspect.signature(
        build_condition_schedule
    ).parameters
    assert "seed" not in inspect.signature(
        build_condition_schedule
    ).parameters


def test_synthetic_plan_cannot_match_canonical_real_reference(fast_plan) -> None:
    plan, _, _ = fast_plan
    with pytest.raises(SchedulingContractError, match="reference"):
        validate_canonical_real_reference(plan)


def test_real_masker_produces_nonzero_targets_for_every_complete_update() -> None:
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            scheduling_module,
            "mask_packed_sequence",
            real_mask_packed_sequence,
        )
        schedule = build_condition_schedule(
            _population("EnglishMono"),
            input_population_anchor_sha256="c" * 64,
        )
    assert len(schedule.updates) == 1_000
    assert all(
        audit.minimum_update_selected_targets > 0
        for audit in schedule.seed_audits
    )


def test_complete_update_loss_normalizes_once_and_is_partition_invariant() -> None:
    first = normalize_complete_update_loss(
        (
            MicrobatchLoss(8.0, 2),
            MicrobatchLoss(12.0, 3),
        )
    )
    second = normalize_complete_update_loss((MicrobatchLoss(20.0, 5),))
    assert first.normalized_loss == second.normalized_loss == 4.0
    assert first.actual_selected_target_count == 5
    assert first.operation_order == (
        "sum_target_cross_entropy",
        "divide_by_actual_selected_target_count",
    )


def test_zero_target_microbatch_is_zero_and_zero_target_update_fails() -> None:
    normalized = normalize_complete_update_loss(
        (
            MicrobatchLoss(0.0, 0),
            MicrobatchLoss(5.0, 1),
        )
    )
    assert normalized.normalized_loss == 5.0
    with pytest.raises(TrainingContractError):
        MicrobatchLoss(1.0, 0)
    with pytest.raises(TrainingContractError, match="zero selected"):
        normalize_complete_update_loss((MicrobatchLoss(0.0, 0),))


def test_clipping_and_adamw_order_is_factory_enforced() -> None:
    normalized = normalize_complete_update_loss((MicrobatchLoss(6.0, 2),))
    clipping = authorize_gradient_clipping(normalized)
    step = authorize_adamw_step(clipping)
    assert step.operation_order == (
        "sum_target_cross_entropy",
        "divide_by_actual_selected_target_count",
        "clip_gradients",
        "one_adamw_step",
    )
    with pytest.raises(TrainingContractError):
        NormalizedUpdateLoss()
    with pytest.raises(TrainingContractError):
        GradientClippingAuthorization()
    with pytest.raises(TrainingContractError):
        authorize_gradient_clipping(object())  # type: ignore[arg-type]


def _resume_copy(state: ResumeState, **changes: object) -> ResumeState:
    copied = object.__new__(ResumeState)
    for item in fields(ResumeState):
        object.__setattr__(
            copied,
            item.name,
            changes.get(item.name, getattr(state, item.name)),
        )
    return copied


def _condition_audit_copy(
    audit: SeedTargetAudit,
    **changes: object,
) -> SeedTargetAudit:
    copied = object.__new__(SeedTargetAudit)
    for item in fields(SeedTargetAudit):
        object.__setattr__(
            copied,
            item.name,
            changes.get(item.name, getattr(audit, item.name)),
        )
    return copied


def _paired_audit_copy(
    audit: PairedSeedTargetAudit,
    **changes: object,
) -> PairedSeedTargetAudit:
    copied = object.__new__(PairedSeedTargetAudit)
    for item in fields(PairedSeedTargetAudit):
        object.__setattr__(
            copied,
            item.name,
            changes.get(item.name, getattr(audit, item.name)),
        )
    return copied


@pytest.mark.parametrize(
    "mutation",
    (
        "all_zero_checksum",
        "single_condition",
        "three_conditions",
        "duplicate_condition",
        "wrong_condition",
        "swapped_schedules",
        "wrong_seed",
        "missing_update",
        "update_count_1001",
        "zero_target_update",
        "altered_selected_count",
        "altered_ratio",
        "failed_parity_marked_passing",
        "wrong_candidate_schedule_set",
    ),
)
def test_four_condition_seed_authorization_rejects_fabricated_evidence(
    fast_plan,
    mutation: str,
) -> None:
    plan, _, sequences = fast_plan
    audit = plan.seed_audits[0]
    condition_audits = list(audit.condition_audits)
    tampered = audit
    if mutation == "all_zero_checksum":
        tampered = _paired_audit_copy(audit, evidence_sha256="0" * 64)
    elif mutation == "single_condition":
        tampered = _paired_audit_copy(
            audit,
            condition_audits=(condition_audits[0],),
        )
    elif mutation == "three_conditions":
        tampered = _paired_audit_copy(
            audit,
            condition_audits=tuple(condition_audits[:3]),
        )
    elif mutation == "duplicate_condition":
        condition_audits[-1] = condition_audits[0]
        tampered = _paired_audit_copy(
            audit,
            condition_audits=tuple(condition_audits),
        )
    elif mutation == "wrong_condition":
        condition_audits[0] = _condition_audit_copy(
            condition_audits[0],
            condition="Unknown",
        )
        tampered = _paired_audit_copy(
            audit,
            condition_audits=tuple(condition_audits),
        )
    elif mutation == "swapped_schedules":
        condition_audits[:2] = reversed(condition_audits[:2])
        tampered = _paired_audit_copy(
            audit,
            condition_audits=tuple(condition_audits),
        )
    elif mutation == "wrong_seed":
        tampered = _paired_audit_copy(audit, seed=audit.seed + 1)
    elif mutation in {
        "missing_update",
        "update_count_1001",
        "zero_target_update",
        "altered_selected_count",
    }:
        selected = list(condition_audits[0].selected_targets_by_update)
        update_count = condition_audits[0].update_count
        total = condition_audits[0].actual_selected_targets
        if mutation == "missing_update":
            selected.pop()
            update_count = 999
        elif mutation == "update_count_1001":
            selected.append(selected[-1])
            update_count = 1_001
        elif mutation == "zero_target_update":
            selected[0] = 0
        else:
            selected[0] += 1
            total += 1
        condition_audits[0] = _condition_audit_copy(
            condition_audits[0],
            selected_targets_by_update=tuple(selected),
            update_count=update_count,
            actual_selected_targets=total,
        )
        tampered = _paired_audit_copy(
            audit,
            condition_audits=tuple(condition_audits),
        )
    elif mutation == "altered_ratio":
        tampered = _paired_audit_copy(
            audit,
            exact_ratio_numerator=audit.exact_ratio_numerator + 1,
        )
    elif mutation == "failed_parity_marked_passing":
        counts = list(audit.actual_selected_targets_by_condition)
        counts[0] = (counts[0][0], counts[0][1] * 2)
        tampered = _paired_audit_copy(
            audit,
            actual_selected_targets_by_condition=tuple(counts),
            exact_one_percent_passed=True,
        )
    else:
        tampered = _paired_audit_copy(
            audit,
            schedule_set_identity_sha256="0" * 64,
        )
    with pytest.raises(
        SchedulingContractError,
        match="audit|evidence|already reviewed",
    ):
        validate_seed_authorization(plan, sequences, tampered)


def test_seed_authorization_cannot_cross_candidate_schedule_set(
    fast_plan,
) -> None:
    plan, _, sequences = fast_plan
    other = build_training_exposure_plan(
        sequences,
        input_population_anchor_sha256="b" * 64,
    )
    with pytest.raises(SchedulingContractError, match="audit|evidence"):
        validate_seed_authorization(
            plan,
            sequences,
            other.seed_audits[0],
        )


def test_update_boundary_resume_regenerates_exact_suffix(fast_plan) -> None:
    plan, _, sequences = fast_plan
    schedule = plan.conditions[0]
    state = derive_resume_state(
        schedule,
        training_exposure_plan=plan,
        population_sequences=sequences,
        completed_optimizer_update=250,
        training_mask_seed=11_729,
        optimizer_state_reference="d" * 64,
        scheduler_state_reference="e" * 64,
    )
    suffix = validate_resume_state(
        schedule,
        state,
        training_exposure_plan=plan,
        population_sequences=sequences,
        checkpoint_update=250,
    )
    assert suffix == schedule.appearances[state.schedule_cursor :]
    assert state.schedule_cursor == schedule.updates[249].schedule_end_cursor
    assert state.token_credit == schedule.updates[249].token_credit


def test_resume_rejects_mid_update_tampering_and_checkpoint_mismatch(
    fast_plan,
) -> None:
    plan, _, sequences = fast_plan
    schedule = plan.conditions[0]
    state = derive_resume_state(
        schedule,
        training_exposure_plan=plan,
        population_sequences=sequences,
        completed_optimizer_update=500,
        training_mask_seed=281_828,
        optimizer_state_reference="d" * 64,
        scheduler_state_reference="e" * 64,
    )
    for tampered in (
        _resume_copy(state, at_update_boundary=False),
        _resume_copy(state, schedule_cursor=state.schedule_cursor + 1),
        _resume_copy(state, token_credit=state.token_credit + 1),
        _resume_copy(state, training_mask_seed=123),
        _resume_copy(state, ordered_prefix_sha256="0" * 64),
    ):
        with pytest.raises(SchedulingContractError):
            validate_resume_state(
                schedule,
                tampered,
                training_exposure_plan=plan,
                population_sequences=sequences,
                checkpoint_update=500,
            )
    with pytest.raises(SchedulingContractError, match="incompatible"):
        validate_resume_state(
            schedule,
            state,
            training_exposure_plan=plan,
            population_sequences=sequences,
            checkpoint_update=750,
        )
    with pytest.raises(SchedulingContractError, match="checkpoint update"):
        validate_resume_state(
            schedule,
            state,
            training_exposure_plan=plan,
            population_sequences=sequences,
            checkpoint_update=False,
        )
    with pytest.raises(SchedulingContractError, match="checkpoint"):
        derive_resume_state(
            schedule,
            training_exposure_plan=plan,
            population_sequences=sequences,
            completed_optimizer_update=1_001,
            training_mask_seed=281_828,
            optimizer_state_reference="d" * 64,
            scheduler_state_reference="e" * 64,
        )


def test_schedule_errors_and_state_representations_are_privacy_safe(
    fast_plan,
) -> None:
    marker = "synthetic-sensitive-private-identifier"
    sequence = replace(
        _packed(index=1),
        example_identity=marker,
    )
    with pytest.raises(SchedulingContractError) as caught:
        build_condition_schedule(
            (sequence,),
            input_population_anchor_sha256="a" * 64,
        )
    error = caught.value
    assert error.__cause__ is None
    assert error.__context__ is None
    assert marker not in repr(error.args)
    assert marker not in repr(vars(error))
    assert marker not in "".join(traceback.format_exception(error))
    for frame, _ in traceback.walk_tb(error.__traceback__):
        if Path(frame.f_code.co_filename).name == "scheduling.py":
            assert marker not in repr(frame.f_locals)
    plan, _, sequences = fast_plan
    schedule = plan.conditions[0]
    state = derive_resume_state(
        schedule,
        training_exposure_plan=plan,
        population_sequences=sequences,
        completed_optimizer_update=0,
        training_mask_seed=11_729,
        optimizer_state_reference="d" * 64,
        scheduler_state_reference="e" * 64,
    )
    assert marker not in repr(schedule)
    assert marker not in repr(state)
    serialized = json.dumps(
        training_exposure_plan_payload(
            plan,
            legacy_non_padding_projection={
                condition: 1.0 for condition in CONDITIONS
            },
        )
    )
    assert marker not in serialized
