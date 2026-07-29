"""Aggregate, privacy-safe pre-training exposure audits."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from cslm.modeling.config import CONDITIONS, SEP_TOKEN_ID, SPECIAL_TOKEN_IDS
from cslm.modeling.contracts import APPROVED_BUDGET, TrainingBudgetContract
from cslm.modeling.packing import (
    EntityIdentity,
    GroupKey,
    PackingResult,
    SourceRowIdentity,
    SourceTokenRange,
    _authorized_entity_keys,
)


class ExposureAuditError(RuntimeError):
    """An exposure, boundary, leakage, or token-loss invariant failed."""


@dataclass(frozen=True)
class ExposureGroup:
    condition: str
    split: str
    source_lexical_tokens: int
    non_padding_wordpieces: int
    sequence_count: int
    padding_count: int
    padding_fraction: float
    expected_masked_target_count: float


@dataclass(frozen=True)
class ExposureAudit:
    """Only aggregate values; no text, identifiers, paths, or provenance are exposed."""

    groups: tuple[ExposureGroup, ...]
    projected_train_non_padding_wordpieces: tuple[tuple[str, float], ...]
    prohibited_boundary_crossings: int
    split_leakage_count: int
    dropped_token_count: int
    truncated_token_count: int
    maximum_projected_exposure_difference_fraction: float
    exposure_tolerance_fraction: float


def audit_exposure(
    packing_results: Iterable[PackingResult],
    *,
    budget: TrainingBudgetContract = APPROVED_BUDGET,
    exposure_tolerance_fraction: float = 0.01,
) -> ExposureAudit:
    """Aggregate packed data and enforce the paired projected-exposure rule."""
    if exposure_tolerance_fraction != 0.01:
        raise ExposureAuditError("the exposure tolerance must remain exactly one percent")
    results = tuple(packing_results)
    if not results:
        raise ExposureAuditError("at least one packing result is required")

    source_lexical: Counter[GroupKey] = Counter()
    source_wordpieces: Counter[GroupKey] = Counter()
    packed_wordpieces: Counter[GroupKey] = Counter()
    non_padding: Counter[GroupKey] = Counter()
    padding: Counter[GroupKey] = Counter()
    eligible_targets: Counter[GroupKey] = Counter()
    sequence_counts: Counter[GroupKey] = Counter()
    crossings = 0
    leakage = 0
    dropped = 0
    truncated = 0
    ranges_by_row: dict[SourceRowIdentity, list[SourceTokenRange]] = {}
    entity_splits: dict[EntityIdentity, str] = {}

    for result in results:
        source_lexical.update(result.source_lexical_tokens_by_group)
        source_wordpieces.update(result.source_wordpieces_by_group)
        packed_wordpieces.update(result.packed_wordpieces_by_group)
        crossings += result.prohibited_boundary_crossings
        leakage += result.split_leakage_count
        dropped += result.dropped_token_count
        truncated += result.truncated_token_count
        for sequence in result.sequences:
            key = (sequence.condition, sequence.split)
            sequence_counts[key] += 1
            non_padding[key] += sequence.non_padding_wordpieces
            padding[key] += sequence.padding_count
            eligible_targets[key] += sum(
                attended and token_id not in SPECIAL_TOKEN_IDS
                for token_id, attended in zip(
                    sequence.input_ids, sequence.attention_mask, strict=True
                )
            )
            authorization_keys = {item.authorization_key for item in sequence.provenance}
            if len(authorization_keys) != 1:
                crossings += 1
            if any(
                item.condition != sequence.condition or item.split != sequence.split
                for item in sequence.provenance
            ):
                leakage += 1
            for item in sequence.provenance:
                for entity_key in _authorized_entity_keys(
                    source=item.source,
                    document_id=item.document_id,
                    conversation_id=item.conversation_id,
                    span_id=item.span_id,
                ):
                    previous_split = entity_splits.setdefault(entity_key, item.split)
                    if previous_split != item.split:
                        leakage += 1
                if sequence.input_ids[item.packed_token_end] != SEP_TOKEN_ID:
                    truncated += 1
                if item.packed_token_end <= item.packed_token_start:
                    dropped += 1
                if (
                    item.source_token_end - item.source_token_start
                    != item.packed_token_end - item.packed_token_start
                ):
                    dropped += 1
                ranges_by_row.setdefault(item.source_row_identity, []).append(item)

    for row_ranges in ranges_by_row.values():
        if len({item.split for item in row_ranges}) != 1:
            leakage += 1
        stable_metadata = {
            (
                item.split,
                item.component,
                item.document_id,
                item.conversation_id,
                item.span_id,
                item.row_order,
                item.language_shard,
                item.source_row_token_count,
            )
            for item in row_ranges
        }
        if len(stable_metadata) != 1:
            dropped += 1
        ordered = sorted(
            (
                item.source_token_start,
                item.source_token_end,
                item.source_row_token_count,
            )
            for item in row_ranges
        )
        expected_start = 0
        row_token_counts = {row_token_count for _, _, row_token_count in ordered}
        if len(row_token_counts) != 1:
            dropped += 1
            continue
        for start, end, _ in ordered:
            if start != expected_start or end <= start:
                dropped += 1
            expected_start = end
        if expected_start != next(iter(row_token_counts)):
            truncated += 1

    if source_wordpieces != packed_wordpieces:
        dropped += sum(
            abs(source_wordpieces[key] - packed_wordpieces[key])
            for key in source_wordpieces.keys() | packed_wordpieces.keys()
        )
    if crossings or leakage or dropped or truncated:
        raise ExposureAuditError(
            "exposure audit found a boundary, leakage, or token-loss violation"
        )

    groups = tuple(
        ExposureGroup(
            condition=condition,
            split=split,
            source_lexical_tokens=source_lexical[(condition, split)],
            non_padding_wordpieces=non_padding[(condition, split)],
            sequence_count=sequence_counts[(condition, split)],
            padding_count=padding[(condition, split)],
            padding_fraction=padding[(condition, split)]
            / (sequence_counts[(condition, split)] * budget.maximum_sequence_length),
            expected_masked_target_count=eligible_targets[(condition, split)] * 0.15,
        )
        for condition, split in sorted(sequence_counts)
    )

    projected: dict[str, float] = {}
    for condition in CONDITIONS:
        train_key = (condition, "train")
        validation_key = (condition, "validation")
        if sequence_counts[train_key] == 0:
            raise ExposureAuditError("all four conditions require packed training examples")
        if sequence_counts[validation_key] == 0:
            raise ExposureAuditError("all four conditions require packed validation examples")
        mean_non_padding = non_padding[train_key] / sequence_counts[train_key]
        projected[condition] = mean_non_padding * budget.projected_sequence_exposures

    minimum = min(projected.values())
    maximum = max(projected.values())
    if minimum <= 0:
        raise ExposureAuditError("projected exposure must be positive")
    difference_fraction = (maximum - minimum) / minimum
    if difference_fraction > exposure_tolerance_fraction:
        raise ExposureAuditError("projected WordPiece exposure differs by more than one percent")

    return ExposureAudit(
        groups=groups,
        projected_train_non_padding_wordpieces=tuple(
            (condition, projected[condition]) for condition in CONDITIONS
        ),
        prohibited_boundary_crossings=0,
        split_leakage_count=0,
        dropped_token_count=0,
        truncated_token_count=0,
        maximum_projected_exposure_difference_fraction=difference_fraction,
        exposure_tolerance_fraction=exposure_tolerance_fraction,
    )
