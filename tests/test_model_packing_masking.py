from __future__ import annotations

from collections import Counter
from dataclasses import replace

import pytest

import cslm.modeling.masking as masking_module
from cslm.modeling.masking import (
    IGNORE_INDEX,
    MaskingContractError,
    MaskingPolicy,
    build_validation_mask_record,
    mask_packed_sequence,
)
from cslm.modeling.packing import (
    PackingContractError,
    PackingRow,
    pack_rows,
    packing_row_from_callhome,
    packing_row_from_frozen_cscont,
)


def _row(
    row_id: str,
    token_ids: tuple[int, ...],
    *,
    row_order: int = 0,
    condition: str = "CsCont",
    split: str = "train",
    source: str = "synthetic_source",
    component: str = "synthetic_component",
    document_id: str = "synthetic_document",
    conversation_id: str = "synthetic_conversation",
    span_id: str = "synthetic_span",
    language_shard: str | None = None,
    lexical_token_count: int | None = None,
) -> PackingRow:
    return PackingRow(
        condition=condition,
        split=split,
        source=source,
        component=component,
        document_id=document_id,
        conversation_id=conversation_id,
        span_id=span_id,
        row_id=row_id,
        row_order=row_order,
        token_ids=token_ids,
        lexical_token_count=(
            len(token_ids) if lexical_token_count is None else lexical_token_count
        ),
        language_shard=language_shard,
    )


def test_within_document_packing_has_utterance_separators_and_zero_token_types() -> None:
    result = pack_rows(
        [
            _row("row-a", (10, 11), row_order=0),
            _row("row-b", (12,), row_order=1),
        ]
    )
    sequence = result.sequences[0]

    assert sequence.input_ids[:6] == (2, 10, 11, 3, 12, 3)
    assert sequence.attention_mask[:6] == (1,) * 6
    assert sequence.attention_mask[6:] == (0,) * 122
    assert sequence.input_ids[6:] == (0,) * 122
    assert sequence.token_type_ids == (0,) * 128
    assert len(sequence.provenance) == 2
    assert all(
        sequence.input_ids[item.packed_token_end] == 3 for item in sequence.provenance
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source", "other_source"),
        ("component", "other_component"),
        ("document_id", "other_document"),
        ("conversation_id", "other_conversation"),
        ("span_id", "other_span"),
        ("condition", "EnglishMono"),
    ],
)
def test_prohibited_authorization_boundaries_never_share_a_sequence(
    field: str,
    value: str,
) -> None:
    first = _row("row-a", (10,), row_order=0)
    second = replace(first, row_id="row-b", row_order=0, **{field: value})
    result = pack_rows([first, second])
    assert len(result.sequences) == 2


def test_monocont_language_shards_never_share_a_sequence() -> None:
    english = _row(
        "row-en",
        (10, 11),
        condition="MonoCont",
        language_shard="english",
    )
    spanish = replace(
        english,
        row_id="row-es",
        row_order=0,
        language_shard="spanish",
    )
    result = pack_rows([english, spanish])
    assert len(result.sequences) == 2
    assert {
        sequence.provenance[0].language_shard for sequence in result.sequences
    } == {"english", "spanish"}


def test_same_source_row_may_be_reused_across_experimental_conditions() -> None:
    english = _row(
        "shared-source-row",
        (10, 11),
        condition="EnglishMono",
        span_id=None,
    )
    monocont = replace(
        english,
        condition="MonoCont",
        language_shard="english",
    )
    result = pack_rows([english, monocont])
    assert tuple(sequence.condition for sequence in result.sequences) == (
        "EnglishMono",
        "MonoCont",
    )


def test_duplicate_source_row_within_one_condition_is_rejected() -> None:
    first = _row("duplicate-row", (10,), row_order=0)
    duplicate = replace(
        first,
        document_id="changed-document",
        conversation_id="changed-conversation",
        span_id="changed-span",
        row_order=1,
    )
    with pytest.raises(PackingContractError, match="identity is not unique"):
        pack_rows([first, duplicate])


def test_existing_frozen_cscont_and_callhome_structures_are_adapted_directly() -> None:
    cscont = packing_row_from_frozen_cscont(
        {
            "component": "bangor_natural_span",
            "condition": "CsCont",
            "conversation_id": "synthetic-conversation",
            "document_id": "synthetic-frozen-span",
            "document_row_index": 4,
            "lexical_tokens": 2,
            "record_id": "synthetic-record",
            "source": "bangor_cgwords",
            "split": "train",
        },
        (10, 11, 12),
    )
    callhome = packing_row_from_callhome(
        {
            "conversation_ref": "synthetic-callhome-conversation",
            "row_id": "synthetic-callhome-row",
            "source": "callhome_spa",
            "split": "validation",
            "turn_index": 8,
        },
        (20, 21),
        condition="MonoCont",
        lexical_token_count=2,
    )
    assert cscont.document_id == cscont.span_id == "synthetic-frozen-span"
    assert cscont.row_order == 4
    assert callhome.document_id == callhome.conversation_id
    assert callhome.row_order == 8
    assert callhome.language_shard == "spanish"


def test_overlength_utterance_splits_contiguously_without_overlap_or_loss() -> None:
    original = tuple(5 + (index % 100) for index in range(300))
    result = pack_rows([_row("long-row", original, lexical_token_count=73)])
    assert len(result.sequences) == 3

    ranges = sorted(
        (
            item.source_token_start,
            item.source_token_end,
            sequence.input_ids[item.packed_token_start : item.packed_token_end],
        )
        for sequence in result.sequences
        for item in sequence.provenance
    )
    assert [(start, end) for start, end, _ in ranges] == [(0, 126), (126, 252), (252, 300)]
    reconstructed = tuple(token for _, _, tokens in ranges for token in tokens)
    assert reconstructed == original
    assert result.source_wordpieces_by_group == {("CsCont", "train"): 300}
    assert result.packed_wordpieces_by_group == result.source_wordpieces_by_group
    assert result.source_lexical_tokens_by_group == {("CsCont", "train"): 73}
    assert result.dropped_token_count == 0
    assert result.truncated_token_count == 0


def _packed_lexical_tokens(result) -> tuple[int, ...]:
    return tuple(
        token_id
        for sequence in result.sequences
        for item in sequence.provenance
        for token_id in sequence.input_ids[item.packed_token_start : item.packed_token_end]
    )


def test_exactly_full_fresh_sequence_starts_following_consecutive_row_cleanly() -> None:
    first_tokens = tuple(5 + (index % 100) for index in range(126))
    second_tokens = (500, 501)
    result = pack_rows(
        [
            _row("exact-full-row", first_tokens, row_order=0),
            _row("following-row", second_tokens, row_order=1),
        ]
    )

    assert len(result.sequences) == 2
    assert result.sequences[0].input_ids == (2, *first_tokens, 3)
    assert result.sequences[1].input_ids[:4] == (2, *second_tokens, 3)
    assert sum(result.sequences[0].attention_mask) == 128
    assert sum(result.sequences[1].attention_mask) == 4
    assert _packed_lexical_tokens(result) == first_tokens + second_tokens
    assert all(
        item.source_token_end > item.source_token_start
        and sequence.input_ids[item.packed_token_end] == 3
        for sequence in result.sequences
        for item in sequence.provenance
    )
    assert result.source_wordpieces_by_group == {("CsCont", "train"): 128}
    assert result.packed_wordpieces_by_group == result.source_wordpieces_by_group
    assert result.dropped_token_count == 0
    assert result.truncated_token_count == 0


def test_exact_remaining_capacity_starts_next_consecutive_row_cleanly() -> None:
    prefix_tokens = (10, 11, 12)
    capacity_tokens = tuple(100 + index for index in range(122))
    following_tokens = (700,)
    result = pack_rows(
        [
            _row("prefix-row", prefix_tokens, row_order=0),
            _row("capacity-row", capacity_tokens, row_order=1),
            _row("next-row", following_tokens, row_order=2),
        ]
    )

    assert len(result.sequences) == 2
    assert result.sequences[0].input_ids == (
        2,
        *prefix_tokens,
        3,
        *capacity_tokens,
        3,
    )
    assert result.sequences[1].input_ids[:3] == (2, *following_tokens, 3)
    assert [len(sequence.provenance) for sequence in result.sequences] == [2, 1]
    assert _packed_lexical_tokens(result) == (
        prefix_tokens + capacity_tokens + following_tokens
    )
    assert all(
        item.source_token_end > item.source_token_start
        and sequence.input_ids[item.packed_token_end] == 3
        for sequence in result.sequences
        for item in sequence.provenance
    )
    assert result.source_wordpieces_by_group == {("CsCont", "train"): 126}
    assert result.packed_wordpieces_by_group == result.source_wordpieces_by_group
    assert result.dropped_token_count == 0
    assert result.truncated_token_count == 0


def test_short_terminal_example_is_retained_and_padded() -> None:
    result = pack_rows([_row("tail-row", (55,))])
    sequence = result.sequences[0]
    assert sequence.input_ids[:3] == (2, 55, 3)
    assert sequence.input_ids[3:] == (0,) * 125
    assert sum(sequence.attention_mask) == 3
    assert sequence.padding_count == 125


@pytest.mark.parametrize("token_count", [127, 128])
def test_rows_just_over_fresh_capacity_are_split_without_loss(token_count: int) -> None:
    tokens = tuple(5 + (index % 100) for index in range(token_count))
    result = pack_rows([_row(f"length-{token_count}", tokens)])
    assert len(result.sequences) == 2
    assert _packed_lexical_tokens(result) == tokens
    assert [
        (item.source_token_start, item.source_token_end)
        for sequence in result.sequences
        for item in sequence.provenance
    ] == [(0, 126), (126, token_count)]


def test_nonconsecutive_rows_start_a_new_sequence_and_reentry_fails_privately() -> None:
    first = _row("private-row-alpha", (10,), row_order=0)
    skipped = _row("private-row-beta", (11,), row_order=2)
    separated = pack_rows([first, skipped])
    assert len(separated.sequences) == 2

    other = replace(
        first,
        row_id="private-row-other",
        document_id="other-document",
        row_order=0,
    )
    reentered = replace(first, row_id="private-row-return", row_order=1)
    with pytest.raises(PackingContractError, match="not contiguous") as error:
        pack_rows([first, other, reentered])
    assert "private-row" not in str(error.value)


def test_lexical_input_rejects_boundary_control_tokens() -> None:
    for forbidden in (0, 2, 3, 4):
        with pytest.raises(PackingContractError, match="lexical-input"):
            _row("bad-row", (forbidden,))


def test_mask_targets_exclude_all_special_and_padding_tokens() -> None:
    tokens = tuple([1, 5, 6, 7] * 31)
    sequence = pack_rows([_row("mask-row", tokens)]).sequences[0]
    special_positions = {
        index
        for index, token_id in enumerate(sequence.input_ids)
        if token_id in {0, 1, 2, 3, 4}
    }
    for visit in range(200):
        masked = mask_packed_sequence(sequence, seed=400, mode="train", visit=visit)
        assert special_positions.isdisjoint(masked.selected_positions)
        assert all(masked.labels[position] == IGNORE_INDEX for position in special_positions)


def test_dynamic_training_masks_reproduce_by_visit_and_change_across_visits() -> None:
    sequence = pack_rows([_row("dynamic-row", tuple(range(5, 125)))]).sequences[0]
    first = mask_packed_sequence(sequence, seed=901, mode="train", visit=7)
    repeated = mask_packed_sequence(sequence, seed=901, mode="train", visit=7)
    next_visit = mask_packed_sequence(sequence, seed=901, mode="train", visit=8)
    assert first == repeated
    assert first.checksum_sha256 != next_visit.checksum_sha256


def test_validation_mask_is_fixed_checksum_recordable_and_independently_seeded() -> None:
    sequence = pack_rows([_row("validation-row", tuple(range(5, 125)))]).sequences[0]
    first = mask_packed_sequence(sequence, seed=21_729, mode="validation")
    repeated = mask_packed_sequence(sequence, seed=21_729, mode="validation")
    training = mask_packed_sequence(sequence, seed=11_729, mode="train", visit=0)
    assert first == repeated
    assert len(first.checksum_sha256) == 64
    assert first.checksum_sha256 != training.checksum_sha256
    with pytest.raises(MaskingContractError, match="does not accept"):
        mask_packed_sequence(sequence, seed=21_729, mode="validation", visit=0)


def _validation_sequences():
    return pack_rows(
        [
            _row(
                "validation-record-a",
                tuple(range(5, 25)),
                row_order=0,
                split="validation",
                document_id="validation-document-a",
                conversation_id="validation-conversation-a",
                span_id="validation-span-a",
            ),
            _row(
                "validation-record-b",
                tuple(range(25, 45)),
                row_order=0,
                split="validation",
                document_id="validation-document-b",
                conversation_id="validation-conversation-b",
                span_id="validation-span-b",
            ),
        ]
    ).sequences


def test_validation_set_checksum_is_stable_and_order_sensitive() -> None:
    sequences = _validation_sequences()
    first = build_validation_mask_record(sequences, seed=21_729)
    repeated = build_validation_mask_record(sequences, seed=21_729)
    reordered = build_validation_mask_record(tuple(reversed(sequences)), seed=21_729)
    assert first == repeated
    assert first.example_count == 2
    assert first.checksum_sha256 != reordered.checksum_sha256


def test_validation_set_checksum_changes_with_example_mask_or_seed() -> None:
    sequences = _validation_sequences()
    baseline = build_validation_mask_record(sequences, seed=21_729)

    changed_identity = replace(sequences[0], example_identity="f" * 64)
    identity_record = build_validation_mask_record(
        (changed_identity, sequences[1]),
        seed=21_729,
    )

    changed_ids = list(sequences[0].input_ids)
    changed_ids[1] += 1
    changed_mask_input = replace(sequences[0], input_ids=tuple(changed_ids))
    mask_record = build_validation_mask_record(
        (changed_mask_input, sequences[1]),
        seed=21_729,
    )
    seed_record = build_validation_mask_record(sequences, seed=21_730)

    assert len(
        {
            baseline.checksum_sha256,
            identity_record.checksum_sha256,
            mask_record.checksum_sha256,
            seed_record.checksum_sha256,
        }
    ) == 4


@pytest.mark.parametrize("field", ["input_ids", "labels"])
def test_validation_set_checksum_binds_derived_masked_inputs_and_labels(
    field: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sequences = _validation_sequences()
    baseline = build_validation_mask_record(sequences, seed=21_729)
    original_mask = masking_module.mask_packed_sequence

    def altered_mask(*args, **kwargs):
        masked = original_mask(*args, **kwargs)
        values = list(getattr(masked, field))
        values[1] = 7_999 if values[1] != 7_999 else 7_998
        return replace(masked, **{field: tuple(values)})

    monkeypatch.setattr(masking_module, "mask_packed_sequence", altered_mask)
    changed = build_validation_mask_record(sequences, seed=21_729)
    assert changed.checksum_sha256 != baseline.checksum_sha256


@pytest.mark.parametrize("field", ["attention_mask", "token_type_ids"])
def test_validation_metadata_changes_are_rejected_by_packed_sequence_contract(
    field: str,
) -> None:
    sequence = _validation_sequences()[0]
    values = list(getattr(sequence, field))
    values[1] = 0 if field == "attention_mask" else 1
    with pytest.raises(PackingContractError):
        replace(sequence, **{field: tuple(values)})


def test_changed_masking_policy_is_rejected() -> None:
    with pytest.raises(MaskingContractError, match="approved contract"):
        MaskingPolicy(probability=0.16)


def test_validation_set_checksum_rejects_an_empty_set() -> None:
    with pytest.raises(MaskingContractError, match="at least one"):
        build_validation_mask_record((), seed=21_729)


def test_masking_uses_deterministic_aggregate_15_percent_and_80_10_10_behavior() -> None:
    sequence = pack_rows([_row("aggregate-row", tuple(range(5, 131)))]).sequences[0]
    replacements: Counter[str] = Counter()
    selected = 0
    random_tokens: list[int] = []
    visits = 500
    for visit in range(visits):
        masked = mask_packed_sequence(sequence, seed=777, mode="train", visit=visit)
        selected += len(masked.selected_positions)
        replacements.update(masked.replacement_kinds)
        random_tokens.extend(
            masked.input_ids[position]
            for position, kind in zip(
                masked.selected_positions, masked.replacement_kinds, strict=True
            )
            if kind == "random"
        )

    assert selected == sum(replacements.values())
    assert (selected, replacements) == (
        9_470,
        Counter({"mask": 7_538, "random": 976, "unchanged": 956}),
    )
    assert selected / (126 * visits) == pytest.approx(0.15, abs=0.005)
    assert replacements["mask"] / selected == pytest.approx(0.80, abs=0.02)
    assert replacements["random"] / selected == pytest.approx(0.10, abs=0.015)
    assert replacements["unchanged"] / selected == pytest.approx(0.10, abs=0.015)
    assert random_tokens
    assert set(random_tokens).isdisjoint({0, 1, 2, 3, 4})
