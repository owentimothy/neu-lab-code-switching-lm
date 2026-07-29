"""Deterministic, boundary-preserving packing of pretokenized corpus rows."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable, Literal, Mapping, Sequence

from cslm.modeling.config import (
    CLS_TOKEN_ID,
    CONDITIONS,
    MASK_TOKEN_ID,
    MAX_SEQUENCE_LENGTH,
    PAD_TOKEN_ID,
    SEP_TOKEN_ID,
    VOCAB_SIZE,
)

Split = Literal["train", "validation", "test"]
LanguageShard = Literal["english", "spanish"]
GroupKey = tuple[str, str]
SourceRowIdentity = tuple[str, str, str]
EntityIdentity = tuple[str, str, str]


class PackingContractError(RuntimeError):
    """A packing or provenance invariant was violated."""


def _authorized_entity_keys(
    *,
    source: str,
    document_id: str,
    conversation_id: str,
    span_id: str | None,
) -> tuple[EntityIdentity, ...]:
    keys = [
        ("document", source, document_id),
        ("conversation", source, conversation_id),
    ]
    if span_id is not None:
        keys.append(("span", source, span_id))
    return tuple(keys)


@dataclass(frozen=True)
class PackingRow:
    """One pretokenized utterance and its existing authorization boundaries."""

    condition: str
    split: Split
    source: str
    component: str
    document_id: str = field(repr=False)
    conversation_id: str = field(repr=False)
    span_id: str | None = field(repr=False)
    row_id: str = field(repr=False)
    row_order: int
    token_ids: tuple[int, ...] = field(repr=False)
    lexical_token_count: int
    language_shard: LanguageShard | None = None

    def __post_init__(self) -> None:
        if self.condition not in CONDITIONS:
            raise PackingContractError("unknown condition")
        if self.split not in {"train", "validation", "test"}:
            raise PackingContractError("unknown split")
        if not all(
            isinstance(value, str) and value
            for value in (
                self.source,
                self.component,
                self.document_id,
                self.conversation_id,
                self.row_id,
            )
        ):
            raise PackingContractError("packing provenance fields must be non-empty")
        if self.span_id is not None and not self.span_id:
            raise PackingContractError("span provenance must be non-empty when present")
        if self.row_order < 0 or self.lexical_token_count < 0 or not self.token_ids:
            raise PackingContractError("invalid row order, lexical count, or token sequence")
        if self.condition == "MonoCont" and self.language_shard not in {"english", "spanish"}:
            raise PackingContractError("MonoCont rows require an explicit language shard")
        if self.condition != "MonoCont" and self.language_shard is not None:
            raise PackingContractError("language shards are only valid for MonoCont")
        forbidden_lexical_ids = {PAD_TOKEN_ID, CLS_TOKEN_ID, SEP_TOKEN_ID, MASK_TOKEN_ID}
        if any(
            not isinstance(token_id, int)
            or token_id < 0
            or token_id >= VOCAB_SIZE
            or token_id in forbidden_lexical_ids
            for token_id in self.token_ids
        ):
            raise PackingContractError("row token IDs violate the lexical-input contract")

    @property
    def group_key(self) -> GroupKey:
        return (self.condition, self.split)

    @property
    def source_row_identity(self) -> SourceRowIdentity:
        return (self.condition, self.source, self.row_id)

    @property
    def authorization_key(self) -> tuple[str, ...]:
        return (
            self.condition,
            self.split,
            self.source,
            self.component,
            self.document_id,
            self.conversation_id,
            self.span_id or "",
            self.language_shard or "",
        )


@dataclass(frozen=True)
class SourceTokenRange:
    """Exact mapping between packed lexical positions and one source-row slice."""

    condition: str
    split: Split
    source: str
    component: str
    document_id: str = field(repr=False)
    conversation_id: str = field(repr=False)
    span_id: str | None = field(repr=False)
    row_id: str = field(repr=False)
    row_order: int
    language_shard: LanguageShard | None
    source_row_token_count: int
    source_token_start: int
    source_token_end: int
    packed_token_start: int
    packed_token_end: int

    @property
    def authorization_key(self) -> tuple[str, ...]:
        return (
            self.condition,
            self.split,
            self.source,
            self.component,
            self.document_id,
            self.conversation_id,
            self.span_id or "",
            self.language_shard or "",
        )

    @property
    def source_row_identity(self) -> SourceRowIdentity:
        return (self.condition, self.source, self.row_id)


@dataclass(frozen=True)
class PackedSequence:
    """One padded model input plus internal source-token provenance."""

    condition: str
    split: Split
    input_ids: tuple[int, ...] = field(repr=False)
    attention_mask: tuple[int, ...] = field(repr=False)
    token_type_ids: tuple[int, ...] = field(repr=False)
    provenance: tuple[SourceTokenRange, ...] = field(repr=False)
    example_identity: str = field(repr=False)

    def __post_init__(self) -> None:
        lengths = {len(self.input_ids), len(self.attention_mask), len(self.token_type_ids)}
        if lengths != {MAX_SEQUENCE_LENGTH}:
            raise PackingContractError("packed tensors must have the approved maximum length")
        if self.input_ids[0] != CLS_TOKEN_ID:
            raise PackingContractError("packed sequence does not start with CLS")
        if any(value != 0 for value in self.token_type_ids):
            raise PackingContractError("all token-type IDs must be zero")
        if any(value not in {0, 1} for value in self.attention_mask):
            raise PackingContractError("attention mask is not binary")
        padding_started = False
        for token_id, attended in zip(self.input_ids, self.attention_mask, strict=True):
            if attended == 0:
                padding_started = True
                if token_id != PAD_TOKEN_ID:
                    raise PackingContractError("unattended positions must use PAD")
            elif padding_started or token_id == PAD_TOKEN_ID:
                raise PackingContractError("padding must be a contiguous terminal suffix")
        last_attended = sum(self.attention_mask) - 1
        if last_attended < 1 or self.input_ids[last_attended] != SEP_TOKEN_ID:
            raise PackingContractError("last attended token must be SEP")

    @property
    def non_padding_wordpieces(self) -> int:
        return sum(self.attention_mask)

    @property
    def padding_count(self) -> int:
        return MAX_SEQUENCE_LENGTH - self.non_padding_wordpieces


@dataclass(frozen=True)
class PackingResult:
    """Packed sequences and loss/boundary diagnostics, with no public text."""

    sequences: tuple[PackedSequence, ...]
    source_lexical_tokens_by_group: Mapping[GroupKey, int]
    source_wordpieces_by_group: Mapping[GroupKey, int]
    packed_wordpieces_by_group: Mapping[GroupKey, int]
    prohibited_boundary_crossings: int
    split_leakage_count: int
    dropped_token_count: int
    truncated_token_count: int

    def __post_init__(self) -> None:
        if (
            self.prohibited_boundary_crossings
            or self.split_leakage_count
            or self.dropped_token_count
            or self.truncated_token_count
        ):
            raise PackingContractError("packing diagnostics contain a prohibited loss or crossing")
        if dict(self.source_wordpieces_by_group) != dict(self.packed_wordpieces_by_group):
            raise PackingContractError("packed WordPieces do not reconcile with source rows")


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _sequence_identity(
    condition: str,
    split: str,
    sequence_index: int,
    provenance: Iterable[SourceTokenRange],
) -> str:
    ranges = [
        [
            item.source,
            item.component,
            item.condition,
            item.split,
            item.document_id,
            item.conversation_id,
            item.span_id,
            item.row_id,
            item.row_order,
            item.language_shard,
            item.source_row_token_count,
            item.source_token_start,
            item.source_token_end,
            item.packed_token_start,
            item.packed_token_end,
        ]
        for item in provenance
    ]
    return hashlib.sha256(
        _canonical_json_bytes([condition, split, sequence_index, ranges])
    ).hexdigest()


def packing_row_from_frozen_cscont(
    record: Mapping[str, Any],
    token_ids: Sequence[int],
) -> PackingRow:
    """Adapt the accepted CsCont structure without consulting private text fields."""
    required = {
        "component": str,
        "condition": str,
        "conversation_id": str,
        "document_id": str,
        "document_row_index": int,
        "lexical_tokens": int,
        "record_id": str,
        "source": str,
        "split": str,
    }
    if any(not isinstance(record.get(key), expected) for key, expected in required.items()):
        raise PackingContractError("frozen CsCont record has an invalid packing schema")
    if record["condition"] != "CsCont":
        raise PackingContractError("frozen CsCont adapter received another condition")
    return PackingRow(
        condition="CsCont",
        split=record["split"],
        source=record["source"],
        component=record["component"],
        document_id=record["document_id"],
        conversation_id=record["conversation_id"],
        span_id=record["document_id"] if record["component"] == "bangor_natural_span" else None,
        row_id=record["record_id"],
        row_order=record["document_row_index"],
        token_ids=tuple(token_ids),
        lexical_token_count=record["lexical_tokens"],
    )


def packing_row_from_callhome(
    record: Mapping[str, Any],
    token_ids: Sequence[int],
    *,
    condition: str,
    lexical_token_count: int,
) -> PackingRow:
    """Adapt existing CALLHOME conversation/turn/source/split/row fields."""
    required = {
        "conversation_ref": str,
        "row_id": str,
        "source": str,
        "split": str,
        "turn_index": int,
    }
    if any(not isinstance(record.get(key), expected) for key, expected in required.items()):
        raise PackingContractError("CALLHOME record has an invalid packing schema")
    source = record["source"]
    source_to_shard = {"callhome_eng": "english", "callhome_spa": "spanish"}
    if source not in source_to_shard:
        raise PackingContractError("CALLHOME source is not authorized for model packing")
    if condition == "EnglishMono" and source != "callhome_eng":
        raise PackingContractError("EnglishMono received a non-English CALLHOME source")
    if condition == "SpanishMono" and source != "callhome_spa":
        raise PackingContractError("SpanishMono received a non-Spanish CALLHOME source")
    if condition not in {"EnglishMono", "SpanishMono", "MonoCont"}:
        raise PackingContractError("CALLHOME adapter received an unauthorized condition")
    conversation = record["conversation_ref"]
    return PackingRow(
        condition=condition,
        split=record["split"],
        source=source,
        component="callhome_monolingual",
        document_id=conversation,
        conversation_id=conversation,
        span_id=None,
        row_id=record["row_id"],
        row_order=record["turn_index"],
        token_ids=tuple(token_ids),
        lexical_token_count=lexical_token_count,
        language_shard=source_to_shard[source] if condition == "MonoCont" else None,
    )


def pack_rows(rows: Iterable[PackingRow]) -> PackingResult:
    """Pack ordered rows without crossing an existing authorization boundary."""
    material = tuple(rows)
    if not material:
        raise PackingContractError("at least one row is required")

    seen_source_rows: set[SourceRowIdentity] = set()
    entity_splits: dict[EntityIdentity, Split] = {}
    closed_authorizations: set[tuple[str, ...]] = set()
    previous_row: PackingRow | None = None
    lexical_by_group: Counter[GroupKey] = Counter()
    source_wordpieces_by_group: Counter[GroupKey] = Counter()
    packed_wordpieces_by_group: Counter[GroupKey] = Counter()
    sequences: list[PackedSequence] = []

    current_key: tuple[str, ...] | None = None
    current_condition = ""
    current_split: Split = "train"
    current_ids: list[int] = []
    current_provenance: list[SourceTokenRange] = []

    def begin(row: PackingRow) -> None:
        nonlocal current_key, current_condition, current_split, current_ids, current_provenance
        current_key = row.authorization_key
        current_condition = row.condition
        current_split = row.split
        current_ids = [CLS_TOKEN_ID]
        current_provenance = []

    def finish() -> None:
        nonlocal current_ids, current_provenance
        if len(current_ids) <= 1:
            return
        attention = [1] * len(current_ids)
        padding = MAX_SEQUENCE_LENGTH - len(current_ids)
        current_ids.extend([PAD_TOKEN_ID] * padding)
        attention.extend([0] * padding)
        sequence = PackedSequence(
            condition=current_condition,
            split=current_split,
            input_ids=tuple(current_ids),
            attention_mask=tuple(attention),
            token_type_ids=(0,) * MAX_SEQUENCE_LENGTH,
            provenance=tuple(current_provenance),
            example_identity=_sequence_identity(
                current_condition,
                current_split,
                len(sequences),
                current_provenance,
            ),
        )
        sequences.append(sequence)
        packed_wordpieces_by_group[(current_condition, current_split)] += sum(
            item.source_token_end - item.source_token_start for item in current_provenance
        )
        current_ids = []
        current_provenance = []

    for row in material:
        if row.source_row_identity in seen_source_rows:
            raise PackingContractError("source row identity is not unique")
        seen_source_rows.add(row.source_row_identity)
        for entity_key in _authorized_entity_keys(
            source=row.source,
            document_id=row.document_id,
            conversation_id=row.conversation_id,
            span_id=row.span_id,
        ):
            previous_split = entity_splits.setdefault(entity_key, row.split)
            if previous_split != row.split:
                raise PackingContractError("authorized entity occurs in more than one split")
        lexical_by_group[row.group_key] += row.lexical_token_count
        source_wordpieces_by_group[row.group_key] += len(row.token_ids)

        force_new_sequence = False
        if previous_row is not None and row.authorization_key == previous_row.authorization_key:
            if row.row_order <= previous_row.row_order:
                raise PackingContractError("row order is not strictly increasing")
            force_new_sequence = row.row_order != previous_row.row_order + 1
        elif previous_row is not None:
            closed_authorizations.add(previous_row.authorization_key)
            if row.authorization_key in closed_authorizations:
                raise PackingContractError("an authorization block is not contiguous")

        if force_new_sequence:
            finish()
            begin(row)
        elif current_key != row.authorization_key:
            finish()
            begin(row)

        source_start = 0
        while source_start < len(row.token_ids):
            available_lexical = MAX_SEQUENCE_LENGTH - len(current_ids) - 1
            if available_lexical <= 0:
                finish()
                begin(row)
                available_lexical = MAX_SEQUENCE_LENGTH - 2
            source_end = min(len(row.token_ids), source_start + available_lexical)
            packed_start = len(current_ids)
            current_ids.extend(row.token_ids[source_start:source_end])
            packed_end = len(current_ids)
            current_ids.append(SEP_TOKEN_ID)
            current_provenance.append(
                SourceTokenRange(
                    condition=row.condition,
                    split=row.split,
                    source=row.source,
                    component=row.component,
                    document_id=row.document_id,
                    conversation_id=row.conversation_id,
                    span_id=row.span_id,
                    row_id=row.row_id,
                    row_order=row.row_order,
                    language_shard=row.language_shard,
                    source_row_token_count=len(row.token_ids),
                    source_token_start=source_start,
                    source_token_end=source_end,
                    packed_token_start=packed_start,
                    packed_token_end=packed_end,
                )
            )
            source_start = source_end
            if source_start < len(row.token_ids):
                finish()
                begin(row)
        previous_row = row

    finish()
    if not sequences:
        raise PackingContractError("packing produced no sequences")

    return PackingResult(
        sequences=tuple(sequences),
        source_lexical_tokens_by_group=dict(sorted(lexical_by_group.items())),
        source_wordpieces_by_group=dict(sorted(source_wordpieces_by_group.items())),
        packed_wordpieces_by_group=dict(sorted(packed_wordpieces_by_group.items())),
        prohibited_boundary_crossings=0,
        split_leakage_count=0,
        dropped_token_count=0,
        truncated_token_count=0,
    )
