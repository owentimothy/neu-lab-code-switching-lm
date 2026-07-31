from __future__ import annotations

from dataclasses import fields, replace

import pytest

from cslm.modeling.config import CONDITIONS
from cslm.modeling.exposure import ExposureAuditError, audit_exposure
from cslm.modeling.packing import (
    PackedSequence,
    PackingContractError,
    PackingRow,
    pack_rows,
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


def _packing_result(
    condition: str,
    token_count: int = 10,
    *,
    include_validation: bool = True,
):
    rows = [
        PackingRow(
            condition=condition,
            split="train",
            source="synthetic_source",
            component="synthetic_component",
            document_id=f"document-{condition}-train",
            conversation_id=f"conversation-{condition}-train",
            span_id=f"span-{condition}-train",
            row_id=f"row-{condition}-train",
            row_order=0,
            token_ids=tuple(range(5, 5 + token_count)),
            lexical_token_count=7,
            language_shard="english" if condition == "MonoCont" else None,
        )
    ]
    if include_validation:
        rows.append(
            PackingRow(
                condition=condition,
                split="validation",
                source="synthetic_source",
                component="synthetic_component",
                document_id=f"document-{condition}-validation",
                conversation_id=f"conversation-{condition}-validation",
                span_id=f"span-{condition}-validation",
                row_id=f"row-{condition}-validation",
                row_order=0,
                token_ids=tuple(range(5, 5 + token_count)),
                lexical_token_count=7,
                language_shard="english" if condition == "MonoCont" else None,
            )
        )
    return pack_rows(rows)


def test_exposure_audit_calculates_privacy_safe_aggregate_counts() -> None:
    audit = audit_exposure(_packing_result(condition) for condition in CONDITIONS)

    assert len(audit.groups) == 8
    for group in audit.groups:
        assert group.source_lexical_tokens == 7
        assert group.non_padding_wordpieces == 12
        assert group.sequence_count == 1
        assert group.padding_count == 116
        assert group.padding_fraction == 116 / 128
        assert group.mask_eligible_wordpieces == 10
        assert group.cls_wordpieces == 1
        assert group.sep_wordpieces == 1
        assert group.unk_wordpieces == 0
        assert group.mask_wordpieces == 0
        assert group.expected_masked_target_count == 1.5
    assert audit.projected_train_non_padding_wordpieces == tuple(
        (condition, 12 * 64_000) for condition in CONDITIONS
    )
    assert audit.maximum_projected_exposure_difference_fraction == 0
    assert audit.prohibited_boundary_crossings == 0
    assert audit.dropped_token_count == 0
    diagnostic = repr(audit)
    assert "document-" not in diagnostic
    assert "conversation-" not in diagnostic
    assert "row-" not in diagnostic
    assert "synthetic_source" not in diagnostic


def test_legacy_non_padding_imbalance_is_diagnostic_only() -> None:
    results = [
        _packing_result(condition, token_count=11 if condition == "CsCont" else 10)
        for condition in CONDITIONS
    ]
    audit = audit_exposure(results)
    assert audit.maximum_projected_exposure_difference_fraction > 0.01


def test_exposure_audit_fails_closed_on_boundary_crossing() -> None:
    results = [_packing_result(condition) for condition in CONDITIONS]
    cscont = results[-1]
    sequence = cscont.sequences[0]
    provenance = sequence.provenance[0]
    crossed = _unsafe_packed_copy(
        sequence,
        provenance=(
            provenance,
            replace(provenance, document_id="private-crossed-document"),
        ),
    )
    results[-1] = replace(cscont, sequences=(crossed,))

    with pytest.raises(ExposureAuditError) as error:
        audit_exposure(results)
    assert "private-crossed-document" not in str(error.value)


def test_exposure_audit_fails_closed_on_split_leakage() -> None:
    results = [_packing_result(condition) for condition in CONDITIONS]
    cscont = results[-1]
    sequence = cscont.sequences[0]
    leaked = _unsafe_packed_copy(
        sequence,
        provenance=(replace(sequence.provenance[0], split="validation"),),
    )
    results[-1] = replace(cscont, sequences=(leaked,))
    with pytest.raises(ExposureAuditError, match="leakage"):
        audit_exposure(results)


@pytest.mark.parametrize("shared_field", ["document_id", "conversation_id", "span_id"])
def test_pack_rows_rejects_entity_level_split_leakage_in_one_call(
    shared_field: str,
) -> None:
    train = PackingRow(
        condition="CsCont",
        split="train",
        source="synthetic_source",
        component="synthetic_component",
        document_id="private-shared-document",
        conversation_id="private-shared-conversation",
        span_id="private-shared-span",
        row_id="private-train-row",
        row_order=0,
        token_ids=(5,),
        lexical_token_count=1,
    )
    validation_values = {
        "document_id": "private-validation-document",
        "conversation_id": "private-validation-conversation",
        "span_id": "private-validation-span",
    }
    validation_values[shared_field] = getattr(train, shared_field)
    validation = replace(
        train,
        **validation_values,
        split="validation",
        row_id="private-validation-row",
        row_order=1,
    )
    with pytest.raises(PackingContractError, match="more than one split") as error:
        pack_rows([train, validation])
    assert "private-" not in str(error.value)


def test_exposure_audit_rejects_entity_split_leakage_across_results() -> None:
    results = [_packing_result(condition) for condition in CONDITIONS]
    extra = pack_rows(
        [
            PackingRow(
                condition="EnglishMono",
                split="validation",
                source="synthetic_source",
                component="synthetic_component",
                document_id="document-EnglishMono-train",
                conversation_id="conversation-EnglishMono-train",
                span_id="span-EnglishMono-train",
                row_id="cross-result-leak",
                row_order=1,
                token_ids=tuple(range(5, 15)),
                lexical_token_count=7,
            )
        ]
    )
    with pytest.raises(ExposureAuditError, match="leakage"):
        audit_exposure([*results, extra])


def test_exposure_audit_requires_every_validation_condition() -> None:
    results = [
        _packing_result(condition, include_validation=condition != "CsCont")
        for condition in CONDITIONS
    ]
    with pytest.raises(ExposureAuditError, match="validation"):
        audit_exposure(results)


def test_exposure_audit_rejects_an_empty_validation_population() -> None:
    results = [
        _packing_result(condition, include_validation=False) for condition in CONDITIONS
    ]
    with pytest.raises(ExposureAuditError, match="validation"):
        audit_exposure(results)


def test_exposure_audit_rejects_duplicate_row_across_results() -> None:
    results = [_packing_result(condition) for condition in CONDITIONS]
    duplicate = pack_rows(
        [
            PackingRow(
                condition="EnglishMono",
                split="train",
                source="synthetic_source",
                component="changed_component",
                document_id="changed_document",
                conversation_id="changed_conversation",
                span_id=None,
                row_id="row-EnglishMono-train",
                row_order=99,
                token_ids=tuple(range(5, 15)),
                lexical_token_count=7,
            )
        ]
    )
    with pytest.raises(ExposureAuditError, match="token-loss"):
        audit_exposure([*results, duplicate])


def test_exposure_audit_rejects_duplicate_row_moved_to_another_split() -> None:
    results = [_packing_result(condition) for condition in CONDITIONS]
    moved = pack_rows(
        [
            PackingRow(
                condition="EnglishMono",
                split="validation",
                source="synthetic_source",
                component="changed_component",
                document_id="changed_document",
                conversation_id="changed_conversation",
                span_id=None,
                row_id="row-EnglishMono-train",
                row_order=99,
                token_ids=tuple(range(5, 15)),
                lexical_token_count=7,
            )
        ]
    )
    with pytest.raises(ExposureAuditError, match="leakage"):
        audit_exposure([*results, moved])


@pytest.mark.parametrize("range_kind", ["repeated", "overlapping"])
def test_exposure_audit_rejects_repeated_or_overlapping_source_ranges(
    range_kind: str,
) -> None:
    results = [_packing_result(condition) for condition in CONDITIONS]
    english = results[0]
    sequence = english.sequences[0]
    provenance = sequence.provenance[0]
    extra = provenance
    if range_kind == "overlapping":
        extra = replace(
            provenance,
            source_token_start=5,
            packed_token_start=6,
        )
    forged = _unsafe_packed_copy(
        sequence,
        provenance=(provenance, extra),
    )
    results[0] = replace(english, sequences=(forged, *english.sequences[1:]))
    with pytest.raises(ExposureAuditError, match="token-loss"):
        audit_exposure(results)
