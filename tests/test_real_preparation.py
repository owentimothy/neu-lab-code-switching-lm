from __future__ import annotations

import dis
import inspect
import json
import os
import stat
import subprocess
import sys
import traceback
from collections.abc import MutableMapping, MutableSequence, MutableSet
from hashlib import sha256
from pathlib import Path
from types import CodeType, FunctionType, MappingProxyType, SimpleNamespace

import numpy as np
import pytest
from synthetic_preparation_support import (
    build_synthetic_preparation_fixture,
    synthetic_bangor_nested_row,
    synthetic_bangor_record,
    synthetic_bangor_record_sequence,
    synthetic_callhome_document_identity,
    synthetic_callhome_row_identity,
    synthetic_population,
)

import cslm.modeling.preparation as preparation_module
import cslm.tokenization.shared_wordpiece as shared_wordpiece_module
from cslm.modeling.config import CONDITIONS
from cslm.modeling.preparation import (
    APPROVED_PRIVATE_OUTPUT_ROOT,
    APPROVED_REAL_AGGREGATES,
    MAX_SEALED_JSONL_LINE_BYTES,
    SYNTHETIC_PREPARATION_PROTOCOL_VERSION,
    DecodedPreparationRow,
    ExactTokenizer,
    ExposureAcceptanceError,
    MembershipPlan,
    PreparationError,
    PreparationManifest,
    PreparationSnapshot,
    ProductionPreparationPaths,
    PublicationCommittedError,
    PublicationOutcomeIndeterminateError,
    SyntheticParityCase,
    SyntheticPreparationSnapshot,
    _provenance_payload,
    _pseudonym,
    _validate_cross_condition_reuse,
    _validate_tokenizer_json,
    adapt_callhome_record,
    adapt_cscont_record,
    approved_block_order,
    approved_validation_seed_plans,
    canonical_json_bytes,
    create_hmac_key,
    iter_sealed_callhome_jsonl,
    lexical_token_count,
    load_hmac_key,
    load_preparation_candidate,
    load_synthetic_preparation_candidate,
    make_synthetic_exact_tokenizer,
    make_synthetic_membership_plan,
    materialize_fixed_validation,
    prepare_and_publish_production,
    prepare_synthetic_rows,
    read_sealed_callhome_jsonl,
    scan_sealed_callhome_split,
    validate_membership,
    validate_publication_paths,
)


def _callhome(
    *,
    source: str = "callhome_eng",
    split: str = "train",
    text: str = "one two three",
    identity: str = "synthetic",
    turn_index: int = 0,
) -> dict[str, object]:
    conversation_id = f"conversation-{identity}"
    return {
        "conversation_ref": conversation_id,
        "row_id": synthetic_callhome_row_identity(
            source,
            conversation_id,
            turn_index,
        ),
        "source": source,
        "speaker_ref": "speaker-must-never-be-serialized",
        "split": split,
        "text": text,
        "turn_index": turn_index,
    }


def _line(row: dict[str, object]) -> bytes:
    return (
        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _write_privacy_reconciliation_key(path: Path, key: bytes = b"k" * 32) -> Path:
    path.write_bytes(key)
    os.chmod(path, 0o600)
    return path


def _cscont(
    *,
    split: str = "train",
    identity: str = "synthetic",
    component: str = "bangor_natural_span",
    nested: dict[str, object] | None = None,
) -> dict[str, object]:
    if component == "bangor_natural_span" and nested is None:
        return synthetic_bangor_record(identity=identity, split=split)
    if component == "bangor_natural_span":
        assert nested is not None
        source = "bangor_cgwords"
        conversation = nested["conversation_id"]
        row_id = f"bangor:{nested['utterance_id']}"
        order = 0
    else:
        nested = nested or _callhome(
            source="callhome_eng",
            split=split,
            identity=identity,
        )
        source = str(nested["source"])
        conversation = nested["conversation_ref"]
        row_id = f"{source}:{nested['row_id']}"
        order = 0
    document_id = (
        f"document-{identity}"
        if component == "bangor_natural_span"
        else synthetic_callhome_document_identity(
            source,
            split,
            str(conversation),
        )
    )
    return {
        "artifact_format_version": 1,
        "component": component,
        "condition": "CsCont",
        "conversation_id": conversation,
        "document_id": document_id,
        "document_row_index": order,
        "lexical_tokens": lexical_token_count(str(nested["text"])),
        "record_id": row_id,
        "row": nested,
        "source": source,
        "split": split,
    }


def _callhome_cscont_sequence(
    *,
    identity: str,
    source: str = "callhome_eng",
    split: str = "train",
    turn_indices: tuple[int, ...] = (4, 9),
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for document_row_index, turn_index in enumerate(turn_indices):
        nested = _callhome(
            source=source,
            split=split,
            identity=identity,
            turn_index=turn_index,
        )
        record = _cscont(
            split=split,
            identity=identity,
            component="callhome_monolingual_filler",
            nested=nested,
        )
        record["document_row_index"] = document_row_index
        records.append(record)
    return records


class _SyntheticBackend:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool]] = []

    def encode(self, text: str, *, add_special_tokens: bool):
        self.calls.append((text, add_special_tokens))
        return SimpleNamespace(ids=[10, 11, 12])


def _synthetic_row(key: tuple[str, str, str | None]) -> DecodedPreparationRow:
    condition, split, shard = key
    identity = f"{condition}-{split}-{shard}"
    if condition == "CsCont":
        return adapt_cscont_record(_cscont(split=split, identity=identity))
    source = (
        "callhome_spa"
        if condition == "SpanishMono" or shard == "spanish"
        else "callhome_eng"
    )
    return adapt_callhome_record(
        _callhome(source=source, split=split, identity=identity),
        logical_condition=condition,
    )


def _synthetic_population() -> tuple[DecodedPreparationRow, ...]:
    return tuple(_synthetic_row(key) for key in approved_block_order())


def _assert_exception_private(error: BaseException, forbidden: tuple[str, ...]) -> None:
    assert error.__cause__ is None
    assert error.__context__ is None
    assert not any(value in repr(error.args) for value in forbidden)
    assert not any(value in repr(vars(error)) for value in forbidden)
    rendered = "".join(traceback.format_exception(error))
    assert not any(value in rendered for value in forbidden)
    for frame, _ in traceback.walk_tb(error.__traceback__):
        if Path(frame.f_code.co_filename).name != "preparation.py":
            continue
        rendered_locals = repr(frame.f_locals)
        assert not any(value in rendered_locals for value in forbidden)


def _contains_private_marker(
    value: object,
    marker: str,
    seen: set[int] | None = None,
) -> bool:
    if isinstance(value, str):
        return marker in value
    if isinstance(value, bytes):
        return marker.encode() in value
    if value is None or isinstance(value, int | float | bool):
        return False
    if seen is None:
        seen = set()
    identity = id(value)
    if identity in seen:
        return False
    seen.add(identity)
    if isinstance(value, dict):
        return any(
            _contains_private_marker(item, marker, seen)
            for pair in value.items()
            for item in pair
        )
    if isinstance(value, list | tuple | set | frozenset):
        return any(_contains_private_marker(item, marker, seen) for item in value)
    attributes = getattr(value, "__dict__", None)
    return isinstance(attributes, dict) and _contains_private_marker(
        attributes,
        marker,
        seen,
    )


def _replace_bangor_nested_field(
    record: dict[str, object],
    field_name: str,
    value: object,
) -> dict[str, object]:
    nested = dict(record["row"])
    nested[field_name] = value
    record["row"] = dict(sorted(nested.items()))
    return record


def _wrong_json_type(value: object) -> object:
    if value is None:
        return 0
    if type(value) is bool:
        return 0
    if type(value) is int:
        return "0"
    if type(value) is str:
        return 0
    if type(value) is list:
        return {}
    raise AssertionError("synthetic Bangor fixture has an unhandled field type")


def _adapt_bangor_stream(
    records: list[dict[str, object]],
    *,
    input_role: str = "synthetic:CsCont:train",
    expected_split: str = "train",
    authorized_records: list[dict[str, object]] | None = None,
) -> tuple[DecodedPreparationRow, ...]:
    state = preparation_module._derive_bangor_v1_stream_state(
        hmac_key=b"k" * 32,
        input_role=input_role,
        expected_split=expected_split,
        authorized_records=(
            records if authorized_records is None else authorized_records
        ),
    )
    decoded: list[DecodedPreparationRow] = []
    try:
        for ordinal, record in enumerate(records):
            decoded.append(
                preparation_module._adapt_cscont_record(
                    record,
                    input_role=input_role,
                    input_ordinal=ordinal,
                    bangor_state=state,
                )
            )
        state.finalize()
    finally:
        state.clear()
    return tuple(decoded)


def _open_descriptor_count() -> int:
    for root in (Path("/proc/self/fd"), Path("/dev/fd")):
        if root.is_dir():
            return len(tuple(root.iterdir()))
    pytest.skip("descriptor inventory is unavailable on this platform")


def test_sealed_reader_accepts_escaped_top_level_split_key() -> None:
    raw = _line(_callhome()).replace(b'"split"', b'"\\u0073plit"')
    assert scan_sealed_callhome_split(raw) == "train"


def test_sealed_reader_ignores_fake_split_strings_in_values_and_nested_objects() -> None:
    row = _callhome(text='nested {"split":"test"} and array ["split"] words')
    assert scan_sealed_callhome_split(_line(row)) == "train"


@pytest.mark.parametrize(
    "raw",
    [
        b'{"conversation_ref":"x","row_id":"r","source":"callhome_eng",'
        b'"speaker_ref":"s","split":"train","split":"test","text":"x","turn_index":0}\n',
        b'{"conversation_ref":"x","row_id":"r","source":"callhome_eng",'
        b'"speaker_ref":"s","text":"secret","split":"train","turn_index":0}\n',
        b'{"conversation_ref":"x","row_id":"r","source":"callhome_eng",'
        b'"speaker_ref":"s","split":7,"text":"x","turn_index":0}\n',
        b'{"conversation_ref":"x","row_id":"r","source":"callhome_eng",'
        b'"speaker_ref":"s","split":"other","text":"x","turn_index":0}\n',
        b'\xef\xbb\xbf{"conversation_ref":"x"}\n',
        b'{"conversation_ref":"x","row_id":"r","source":"callhome_eng",'
        b'"speaker_ref":"s","split":"train","text":"x","turn_index":0} trailing\n',
        b'{"conversation_ref":"x","row_id":"r","source":"callhome_eng",'
        b'"speaker_ref":"s","split":"test","text":"x","turn_index":0',
    ],
)
def test_sealed_reader_rejects_duplicate_early_malformed_or_unterminated_rows(
    raw: bytes,
) -> None:
    with pytest.raises(PreparationError):
        scan_sealed_callhome_split(raw)


def test_sealed_reader_rejects_extreme_nesting_before_split() -> None:
    nested = b"[" * 130 + b"0" + b"]" * 130
    raw = (
        b'{"conversation_ref":'
        + nested
        + b',"row_id":"r","source":"callhome_eng","speaker_ref":"s",'
        b'"split":"train","text":"x","turn_index":0}\n'
    )
    with pytest.raises(PreparationError):
        scan_sealed_callhome_split(raw)


def test_test_lexical_bytes_are_never_decoded_even_when_utf8_is_invalid() -> None:
    raw = (
        b'{"conversation_ref":"x","row_id":"r","source":"callhome_eng",'
        b'"speaker_ref":"s","split":"test","text":"private-\xff",'
        b'"turn_index":0}\n'
    )
    calls: list[bytes] = []

    def decoder(value: bytes):
        calls.append(value)
        return json.loads(value)

    assert tuple(iter_sealed_callhome_jsonl((raw,), authorized_decoder=decoder)) == ()
    assert calls == []


def test_authorized_decode_failure_has_no_private_exception_chain_or_locals() -> None:
    secret = "PRIVATE-LEXICAL-DO-NOT-RETAIN"
    raw = (
        b'{"conversation_ref":"secret-path","row_id":"r","source":"callhome_eng",'
        b'"speaker_ref":"s","split":"train","text":"'
        + secret.encode()
        + b'-\xff","turn_index":0}\n'
    )
    with pytest.raises(PreparationError) as caught:
        tuple(iter_sealed_callhome_jsonl((raw,)))
    _assert_exception_private(caught.value, (secret, "secret-path", "\\xff"))


def test_bounded_reader_accepts_exact_limit_and_rejects_over_limit() -> None:
    empty = _line(_callhome(text="x"))
    exact = _line(_callhome(text="x" * (MAX_SEALED_JSONL_LINE_BYTES - len(empty) + 1)))
    assert len(exact) == MAX_SEALED_JSONL_LINE_BYTES
    assert scan_sealed_callhome_split(exact) == "train"
    with pytest.raises(PreparationError):
        scan_sealed_callhome_split(exact[:-2] + b"xx\n")


def test_file_reader_enforces_bound_and_newline_with_owner_only_files(
    tmp_path: Path,
) -> None:
    over = tmp_path / "over.jsonl"
    over.write_bytes(b"x" * (MAX_SEALED_JSONL_LINE_BYTES + 1))
    os.chmod(over, 0o600)
    with pytest.raises(PreparationError):
        tuple(read_sealed_callhome_jsonl(over))
    truncated = tmp_path / "truncated.jsonl"
    truncated.write_bytes(_line(_callhome()).removesuffix(b"\n"))
    os.chmod(truncated, 0o600)
    with pytest.raises(PreparationError):
        tuple(read_sealed_callhome_jsonl(truncated))


def test_adapters_enforce_routes_relationships_and_drop_speaker_data() -> None:
    english = adapt_callhome_record(_callhome(), logical_condition="EnglishMono")
    bangor = adapt_cscont_record(_cscont())
    assert english.document_id == english.conversation_id
    assert bangor.span_id == bangor.document_id
    assert "speaker" not in repr(english)
    with pytest.raises(PreparationError):
        adapt_callhome_record(
            _callhome(source="callhome_spa"),
            logical_condition="EnglishMono",
        )
    with pytest.raises(PreparationError):
        adapt_callhome_record(_callhome(split="test"), logical_condition="EnglishMono")
    with pytest.raises(PreparationError):
        adapt_cscont_record({**_cscont(), "source": "callhome_eng"})


def test_exact_full_bangor_v1_shape_succeeds_and_projects_only_four_fields() -> None:
    record = synthetic_bangor_record(identity="exact-shape", split="train")
    nested = record["row"]
    assert len(nested) == 45
    assert tuple(nested) == preparation_module._BANGOR_V1_ROW_KEYS
    projection = preparation_module._validate_and_project_bangor_v1_row(nested, record)
    assert tuple(projection) == (
        "conversation_id",
        "source_word_ids",
        "text",
        "tokens",
    )
    assert adapt_cscont_record(record).component == "bangor_natural_span"


def test_authoritative_nonmonotonic_word_ids_preserve_location_and_projection_order() -> None:
    record = synthetic_bangor_record(identity="nonmonotonic-word-ids", split="train")
    nested = record["row"]
    assert nested["source_word_ids"] == [3, 1, 2]
    assert nested["source_token_locations"] == [1, 2, 3]
    projection = preparation_module._validate_and_project_bangor_v1_row(nested, record)
    assert projection["source_word_ids"] == (3, 1, 2)
    assert projection["tokens"] == ("one", "two", "three")
    assert adapt_cscont_record(record).component == "bangor_natural_span"


@pytest.mark.parametrize(
    "word_ids",
    ([3, 3, 2], [3, 0, 2], [3, -1, 2]),
)
def test_duplicate_or_nonpositive_bangor_word_ids_fail(
    word_ids: list[int],
) -> None:
    record = synthetic_bangor_record(identity="invalid-word-ids", split="train")
    _replace_bangor_nested_field(record, "source_word_ids", word_ids)
    with pytest.raises(PreparationError):
        adapt_cscont_record(record)


@pytest.mark.parametrize(
    ("field_name", "values"),
    (
        ("source_word_ids", [3, True, 2]),
        ("source_token_locations", [1, True, 3]),
        ("source_line_numbers", [2, True, 4]),
    ),
)
def test_bangor_source_integer_lists_reject_bool(
    field_name: str,
    values: list[object],
) -> None:
    record = synthetic_bangor_record(identity=f"bool-{field_name}", split="train")
    _replace_bangor_nested_field(record, field_name, values)
    with pytest.raises(PreparationError):
        adapt_cscont_record(record)


@pytest.mark.parametrize(
    "locations",
    ([3, 2, 1], [1, 1, 2], [0, 1, 2]),
)
def test_unsorted_duplicate_or_nonpositive_bangor_locations_fail(
    locations: list[int],
) -> None:
    record = synthetic_bangor_record(identity="invalid-locations", split="train")
    _replace_bangor_nested_field(record, "source_token_locations", locations)
    with pytest.raises(PreparationError):
        adapt_cscont_record(record)


@pytest.mark.parametrize(
    "line_numbers",
    ([1, 3, 4], [2, 2, 4], [0, 3, 4]),
)
def test_header_or_duplicate_or_nonpositive_source_line_numbers_fail(
    line_numbers: list[int],
) -> None:
    record = synthetic_bangor_record(identity="invalid-source-lines", split="train")
    _replace_bangor_nested_field(record, "source_line_numbers", line_numbers)
    with pytest.raises(PreparationError):
        adapt_cscont_record(record)


def test_source_path_basename_mismatch_fails_privately() -> None:
    marker = "PRIVATE-SYNTHETIC-SOURCE-PATH-MARKER"
    record = synthetic_bangor_record(identity="path-binding", split="train")
    _replace_bangor_nested_field(
        record,
        "source_path",
        f"{marker}_cgwords.tsv",
    )
    with pytest.raises(PreparationError) as caught:
        adapt_cscont_record(record)
    _assert_exception_private(caught.value, (marker,))


def test_valid_bangor_utterance_document_and_component_boundaries_pass() -> None:
    first_document = synthetic_bangor_record_sequence(
        identity="boundary-a",
        split="train",
        length=3,
    )
    second_document = synthetic_bangor_record_sequence(
        identity="boundary-b",
        split="train",
        length=2,
    )
    nested_filler = _callhome(identity="boundary-filler")
    filler = _cscont(
        component="callhome_monolingual_filler",
        identity="boundary-filler",
        nested=nested_filler,
    )
    decoded = _adapt_bangor_stream(
        [*first_document, *second_document, filler],
    )
    assert [row.row_order for row in decoded] == [0, 1, 2, 0, 1, 0]
    assert [row.document_id for row in decoded[:3]] == [
        first_document[0]["document_id"],
    ] * 3
    assert decoded[3].document_id == decoded[4].document_id
    assert decoded[5].component == "callhome_monolingual_filler"


def test_authoritative_callhome_outer_nested_and_ordinal_identities_pass() -> None:
    records = _callhome_cscont_sequence(
        identity="callhome-authoritative",
        turn_indices=(7, 12),
    )
    decoded = _adapt_bangor_stream(records)
    assert [record["document_row_index"] for record in records] == [0, 1]
    assert [record["row"]["turn_index"] for record in records] == [7, 12]
    assert all(
        record["record_id"] == f"{record['source']}:{record['row']['row_id']}"
        for record in records
    )
    assert [row.row_order for row in decoded] == [0, 1]
    assert [row.source_row_order for row in decoded] == [7, 12]
    assert [row.row_id for row in decoded] == [
        record["row"]["row_id"] for record in records
    ]


@pytest.mark.parametrize("mutation", ["unprefixed_outer", "prefixed_nested"])
def test_callhome_outer_and_nested_identity_forms_are_exact(mutation: str) -> None:
    record = _callhome_cscont_sequence(
        identity=f"callhome-identity-{mutation}",
        turn_indices=(5,),
    )[0]
    if mutation == "unprefixed_outer":
        record["record_id"] = record["row"]["row_id"]
    else:
        record["row"]["row_id"] = (
            f"{record['source']}:{record['row']['row_id']}"
        )
        record["record_id"] = f"{record['source']}:{record['row']['row_id']}"
    with pytest.raises(PreparationError):
        adapt_cscont_record(record)


@pytest.mark.parametrize(
    "mutation",
    (
        "nonzero_start",
        "gap",
        "duplicate",
        "swap",
        "improper_reset",
    ),
)
def test_callhome_document_serialization_ordinal_conflicts_fail(
    mutation: str,
) -> None:
    records = _callhome_cscont_sequence(
        identity=f"callhome-document-{mutation}",
        turn_indices=(3, 8),
    )
    if mutation == "nonzero_start":
        records = records[:1]
        records[0]["document_row_index"] = 1
    elif mutation == "gap":
        records[1]["document_row_index"] = 2
    elif mutation == "duplicate":
        records[1]["document_row_index"] = 0
    elif mutation == "swap":
        records.reverse()
    else:
        records[1]["document_row_index"] = 0
        records[1]["document_id"] = synthetic_callhome_document_identity(
            str(records[1]["source"]),
            str(records[1]["split"]),
            f"{records[1]['conversation_id']}-replacement",
        )
    with pytest.raises(PreparationError):
        _adapt_bangor_stream(records)


@pytest.mark.parametrize(
    "mutation",
    ("row_identity", "duplicate_turn", "descending_turn", "source_substitution"),
)
def test_callhome_turn_and_source_relationship_conflicts_fail(mutation: str) -> None:
    records = _callhome_cscont_sequence(
        identity=f"callhome-turn-{mutation}",
        turn_indices=(4, 10),
    )
    if mutation == "row_identity":
        records[1]["row"]["turn_index"] = 11
    elif mutation == "duplicate_turn":
        records[1]["row"]["turn_index"] = 4
    elif mutation == "descending_turn":
        records[1]["row"]["turn_index"] = 2
    else:
        records[1]["source"] = "callhome_spa"
    with pytest.raises(PreparationError):
        _adapt_bangor_stream(records)


def test_callhome_document_reappearance_and_component_reordering_fail() -> None:
    first = _callhome_cscont_sequence(
        identity="callhome-reappearance-a",
        turn_indices=(1, 6),
    )
    second = _callhome_cscont_sequence(
        identity="callhome-reappearance-z",
        turn_indices=(2,),
    )
    assert first[0]["conversation_id"] < second[0]["conversation_id"]
    with pytest.raises(PreparationError):
        _adapt_bangor_stream([first[0], second[0], first[1]])
    with pytest.raises(PreparationError):
        _adapt_bangor_stream(
            [second[0], first[0]],
            authorized_records=[first[0], second[0]],
        )

    bangor = synthetic_bangor_record(identity="ordered-bangor", split="train")
    with pytest.raises(PreparationError):
        _adapt_bangor_stream([first[0], bangor])


def test_callhome_source_namespace_separates_equal_raw_reconciliation_ids() -> None:
    raw_row_id = "synthetic-equal-raw-row-identity"
    assert _pseudonym(
        b"k" * 32,
        "row",
        "callhome_eng",
        raw_row_id,
    ) != _pseudonym(
        b"k" * 32,
        "row",
        "callhome_spa",
        raw_row_id,
    )


def test_valid_bangor_span_can_begin_after_conversation_start() -> None:
    records = synthetic_bangor_record_sequence(
        identity="mid-conversation-span",
        split="train",
        length=2,
    )
    first = records[0]["row"]
    first["utterance_index"] = 4
    first["previous_utterance_id"] = f"{first['conversation_id']}_000999"
    first["previous_speaker_id"] = first["speaker_id"]
    first["previous_language_category"] = first["language_category"]
    first["same_speaker_as_previous"] = True
    records[1]["row"]["utterance_index"] = 5
    decoded = _adapt_bangor_stream(records)
    assert [row.row_order for row in decoded] == [0, 1]


@pytest.mark.parametrize(
    "mutation",
    (
        "fabricated_index",
        "incorrect_predecessor",
        "missing_predecessor",
        "duplicate_index",
        "skipped_index",
        "reordered_rows",
        "incorrect_previous_speaker",
        "incorrect_previous_category",
    ),
)
def test_bangor_utterance_index_and_predecessor_conflicts_fail(
    mutation: str,
) -> None:
    records = synthetic_bangor_record_sequence(
        identity=f"utterance-conflict-{mutation}",
        split="train",
        length=3,
    )
    if mutation == "fabricated_index":
        records[1]["row"]["utterance_index"] = 999
    elif mutation == "incorrect_predecessor":
        records[1]["row"]["previous_utterance_id"] = (
            f"{records[1]['row']['conversation_id']}_999999"
        )
    elif mutation == "missing_predecessor":
        records[1]["row"]["previous_utterance_id"] = None
    elif mutation == "duplicate_index":
        records[2]["row"]["utterance_index"] = 1
    elif mutation == "skipped_index":
        records[2]["row"]["utterance_index"] = 3
    elif mutation == "reordered_rows":
        records[1]["row"], records[2]["row"] = records[2]["row"], records[1]["row"]
    elif mutation == "incorrect_previous_speaker":
        records[1]["row"]["previous_speaker_id"] = "other-synthetic-speaker"
        records[1]["row"]["same_speaker_as_previous"] = False
    else:
        records[1]["row"]["previous_language_category"] = "en_only"
    with pytest.raises(PreparationError):
        _adapt_bangor_stream(records)


def test_cross_row_word_and_line_identity_reuse_fails() -> None:
    records = synthetic_bangor_record_sequence(
        identity="cross-row-source-reuse",
        split="train",
    )
    records[1]["row"]["source_word_ids"] = [6, 3, 5]
    with pytest.raises(PreparationError):
        _adapt_bangor_stream(records)

    records = synthetic_bangor_record_sequence(
        identity="cross-row-line-reuse",
        split="train",
    )
    records[1]["row"]["source_line_numbers"] = [5, 3, 7]
    with pytest.raises(PreparationError):
        _adapt_bangor_stream(records)


@pytest.mark.parametrize(
    "mutation",
    (
        "starts_at_seven",
        "gap",
        "duplicate",
        "swap",
        "same_conversation_new_document",
        "same_document_new_conversation",
    ),
)
def test_bangor_document_row_and_identity_conflicts_fail(
    mutation: str,
) -> None:
    records = synthetic_bangor_record_sequence(
        identity=f"document-conflict-{mutation}",
        split="train",
    )
    if mutation == "starts_at_seven":
        records = records[:1]
        records[0]["document_row_index"] = 7
    elif mutation == "gap":
        records[1]["document_row_index"] = 2
    elif mutation == "duplicate":
        records[1]["document_row_index"] = 0
    elif mutation == "swap":
        records.reverse()
    elif mutation == "same_conversation_new_document":
        records[1]["document_id"] = "bangor_span_ffffffffffffffff"
        records[1]["document_row_index"] = 0
    else:
        substitute = synthetic_bangor_record_sequence(
            identity=f"document-substitute-{mutation}",
            split="train",
            length=1,
        )[0]
        substitute["document_id"] = records[0]["document_id"]
        substitute["document_row_index"] = 1
        records[1] = substitute
    with pytest.raises(PreparationError):
        _adapt_bangor_stream(records)


def test_bangor_document_serialization_order_cannot_be_swapped() -> None:
    earlier = synthetic_bangor_record_sequence(
        identity="document-order-a",
        split="train",
        length=1,
    )
    later = synthetic_bangor_record_sequence(
        identity="document-order-z",
        split="train",
        length=1,
    )
    assert (
        earlier[0]["conversation_id"]
        < later[0]["conversation_id"]
    )
    with pytest.raises(PreparationError):
        _adapt_bangor_stream(
            [*later, *earlier],
            authorized_records=[*earlier, *later],
        )


def test_bangor_state_rejects_cross_file_split_and_component_substitution() -> None:
    train = synthetic_bangor_record(identity="cross-file", split="train")
    with pytest.raises(PreparationError):
        _adapt_bangor_stream(
            [train],
            input_role="synthetic:CsCont:validation",
            expected_split="validation",
        )

    filler = _cscont(
        component="callhome_monolingual_filler",
        identity="component-first",
        nested=_callhome(identity="component-first"),
    )
    bangor = synthetic_bangor_record(identity="component-after-filler", split="train")
    with pytest.raises(PreparationError):
        _adapt_bangor_stream([filler, bangor])


def test_cross_record_state_and_failures_retain_no_sensitive_metadata() -> None:
    marker = "PRIVATE-BANGOR-STREAM-MARKER-MUST-DISAPPEAR"
    records = synthetic_bangor_record_sequence(
        identity="private-stream",
        split="train",
        sensitive_marker=marker,
    )
    state = preparation_module._derive_bangor_v1_stream_state(
        hmac_key=b"k" * 32,
        input_role="synthetic:CsCont:train",
        expected_split="train",
        authorized_records=records,
    )
    try:
        preparation_module._adapt_cscont_record(
            records[0],
            input_role="synthetic:CsCont:train",
            input_ordinal=0,
            bangor_state=state,
        )
        assert marker not in repr(state)
        records[1]["row"]["previous_utterance_id"] = (
            f"{records[1]['row']['conversation_id']}_999999"
        )
        with pytest.raises(PreparationError) as caught:
            preparation_module._adapt_cscont_record(
                records[1],
                input_role="synthetic:CsCont:train",
                input_ordinal=1,
                bangor_state=state,
            )
        _assert_exception_private(caught.value, (marker,))
        assert marker not in repr(state)
    finally:
        state.clear()
    assert marker not in repr(state)


def test_stream_state_attributes_are_privacy_keyed_across_boundaries() -> None:
    marker = "RAW-STREAM-IDENTITY-MARKER-MUST-NEVER-PERSIST"
    bangor = synthetic_bangor_record_sequence(
        identity=marker,
        split="train",
        length=1,
        sensitive_marker=marker,
    )
    filler = _callhome_cscont_sequence(
        identity=marker,
        turn_indices=(17,),
    )
    records = [*bangor, *filler]
    state = preparation_module._derive_bangor_v1_stream_state(
        hmac_key=b"k" * 32,
        input_role="synthetic:CsCont:train",
        expected_split="train",
        authorized_records=records,
    )
    assert not _contains_private_marker(state, marker)
    try:
        for ordinal, record in enumerate(records):
            preparation_module._adapt_cscont_record(
                record,
                input_role="synthetic:CsCont:train",
                input_ordinal=ordinal,
                bangor_state=state,
            )
            assert not _contains_private_marker(state, marker)
        state.finalize()
        assert not _contains_private_marker(state, marker)
    finally:
        state.clear()
    assert not _contains_private_marker(state, marker)
    assert marker not in repr(state)


def test_former_reduced_bangor_shortcut_and_malformed_nesting_fail() -> None:
    reduced = {
        "conversation_id": "synthetic-conversation",
        "source_word_ids": [1, 2, 3],
        "text": "one two three",
        "tokens": ["one", "two", "three"],
    }
    record = synthetic_bangor_record(identity="reduced", split="train")
    record["row"] = reduced
    with pytest.raises(PreparationError):
        adapt_cscont_record(record)
    record = synthetic_bangor_record(identity="nested-twice", split="train")
    record["row"] = {"row": record["row"]}
    with pytest.raises(PreparationError):
        adapt_cscont_record(record)
    record = synthetic_bangor_record(identity="list-nesting", split="train")
    record["row"] = [record["row"]]
    with pytest.raises(PreparationError):
        adapt_cscont_record(record)


@pytest.mark.parametrize("field_name", preparation_module._BANGOR_V1_ROW_KEYS)
def test_every_missing_bangor_v1_field_fails(field_name: str) -> None:
    record = synthetic_bangor_record(identity=f"missing-{field_name}", split="train")
    nested = dict(record["row"])
    del nested[field_name]
    record["row"] = nested
    with pytest.raises(PreparationError):
        adapt_cscont_record(record)


def test_added_bangor_v1_field_fails() -> None:
    record = synthetic_bangor_record(identity="added-field", split="train")
    nested = dict(record["row"])
    nested["unapproved_metadata"] = "synthetic"
    record["row"] = dict(sorted(nested.items()))
    with pytest.raises(PreparationError):
        adapt_cscont_record(record)


@pytest.mark.parametrize("field_name", preparation_module._BANGOR_V1_ROW_KEYS)
def test_every_renamed_bangor_v1_field_fails(field_name: str) -> None:
    record = synthetic_bangor_record(identity=f"renamed-{field_name}", split="train")
    nested = dict(record["row"])
    value = nested.pop(field_name)
    nested[f"renamed_{field_name}"] = value
    record["row"] = dict(sorted(nested.items()))
    with pytest.raises(PreparationError):
        adapt_cscont_record(record)


@pytest.mark.parametrize("field_name", preparation_module._BANGOR_V1_ROW_KEYS)
def test_every_wrongly_typed_bangor_v1_field_fails(field_name: str) -> None:
    record = synthetic_bangor_record(identity=f"wrong-type-{field_name}", split="train")
    nested = record["row"]
    _replace_bangor_nested_field(record, field_name, _wrong_json_type(nested[field_name]))
    with pytest.raises(PreparationError):
        adapt_cscont_record(record)


@pytest.mark.parametrize(
    "field_name",
    tuple(
        field_name
        for field_name, value in synthetic_bangor_nested_row(
            identity="nullability-schema",
            split="train",
        ).items()
        if value is not None
    ),
)
def test_every_nonnullable_bangor_v1_field_rejects_null(field_name: str) -> None:
    record = synthetic_bangor_record(identity=f"null-{field_name}", split="train")
    _replace_bangor_nested_field(record, field_name, None)
    with pytest.raises(PreparationError):
        adapt_cscont_record(record)


@pytest.mark.parametrize(
    "field_name",
    ("borrowing_status", "matrix_language_heuristic", "equivalence_heuristic"),
)
def test_generator_fixed_null_review_fields_reject_nonnull(field_name: str) -> None:
    record = synthetic_bangor_record(identity=f"nonnull-{field_name}", split="train")
    _replace_bangor_nested_field(record, field_name, "synthetic-review-value")
    with pytest.raises(PreparationError):
        adapt_cscont_record(record)


def test_duplicate_bangor_nested_json_key_fails_before_adaptation() -> None:
    marker = "synthetic-speaker-metadata"
    record = synthetic_bangor_record(identity="duplicate-key", split="train")
    raw = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    needle = f'"speaker_id":"{marker}"'.encode()
    assert needle in raw
    duplicated = raw.replace(
        needle,
        needle + b',"speaker_id":"duplicate-synthetic-speaker"',
        1,
    )
    with pytest.raises(PreparationError) as caught:
        preparation_module._decode_cscont_line(duplicated)
    _assert_exception_private(caught.value, (marker, "duplicate-synthetic-speaker"))


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("source_word_ids", [1, 1, 3]),
        ("source_token_locations", [1, 2]),
        ("source_line_numbers", [2, 3]),
        ("tokens", ["one", "two"]),
        ("token_language_labels", ["eng", "spa", "other"]),
        ("source_token_language_labels", ["eng", "spa", "www"]),
        ("language_category", "en_only"),
        ("condition_candidates", ["EnglishMono"]),
        ("n_english_word_tokens", 1),
        ("needs_review_borrowing", True),
        ("needs_review_equivalence", True),
        ("needs_review_matrix_language", True),
        ("needs_review_mixed_morpheme", True),
        ("normalization_profile", "other-profile"),
        ("source_header", ["word_id"]),
        ("source_optional_fields_present", ["auto"]),
        ("utterance_id", "renamed-synthetic-utterance"),
        ("utterance_index", 1),
        ("is_inter_sentential_switch_from_previous", False),
    ],
)
def test_bangor_v1_structural_relationship_conflicts_fail(
    field_name: str,
    value: object,
) -> None:
    record = synthetic_bangor_record(identity=f"structural-{field_name}", split="train")
    _replace_bangor_nested_field(record, field_name, value)
    with pytest.raises(PreparationError):
        adapt_cscont_record(record)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("condition", "MonoCont"),
        ("source", "callhome_eng"),
        ("component", "callhome_monolingual_filler"),
        ("conversation_id", "conflicting-conversation"),
        ("record_id", "bangor:conflicting-record"),
        ("split", "validation"),
        ("lexical_tokens", 4),
        ("document_id", "unapproved-document"),
    ],
)
def test_bangor_inner_outer_identity_and_route_conflicts_fail(
    field_name: str,
    value: object,
) -> None:
    record = synthetic_bangor_record(identity=f"outer-{field_name}", split="train")
    record[field_name] = value
    with pytest.raises(PreparationError):
        adapt_cscont_record(record)


def test_unused_bangor_sensitive_fields_do_not_survive_or_leak_from_failures() -> None:
    marker = "PRIVATE-BANGOR-SPEAKER-MARKER-MUST-DISAPPEAR"
    record = synthetic_bangor_record(
        identity="private-failure",
        split="train",
        sensitive_marker=marker,
    )
    _replace_bangor_nested_field(record, "n_english_word_tokens", "wrong")
    with pytest.raises(PreparationError) as caught:
        adapt_cscont_record(record)
    _assert_exception_private(caught.value, (marker,))


def test_decoded_bangor_population_does_not_accumulate_unused_45_field_rows() -> None:
    marker = "".join(("PRIVATE-BANGOR-", "POPULATION-MARKER"))
    baseline_references = sys.getrefcount(marker)
    decoded = []
    for index in range(128):
        record = synthetic_bangor_record(
            identity=f"stream-{index}",
            split="train",
            sensitive_marker=marker,
        )
        decoded.append(adapt_cscont_record(record))
        record = None
        assert sys.getrefcount(marker) == baseline_references
    assert marker not in repr(decoded)


def test_filler_adapter_rejects_conflicting_inner_outer_identity() -> None:
    nested = _callhome(identity="inner")
    record = _cscont(
        component="callhome_monolingual_filler",
        identity="inner",
        nested=nested,
    )
    with pytest.raises(PreparationError):
        adapt_cscont_record({**record, "record_id": "different"})
    with pytest.raises(PreparationError):
        adapt_cscont_record({**record, "conversation_id": "different"})
    with pytest.raises(PreparationError):
        adapt_cscont_record({**record, "document_row_index": 2})


def test_rows_membership_and_tokenizer_are_factory_only() -> None:
    with pytest.raises(PreparationError):
        DecodedPreparationRow()
    with pytest.raises(PreparationError):
        MembershipPlan()
    with pytest.raises(PreparationError):
        ExactTokenizer()
    with pytest.raises(PreparationError):
        PreparationManifest()


def test_synthetic_membership_detects_subset_substitution_swap_and_duplication() -> None:
    rows = _synthetic_population()
    plan = make_synthetic_membership_plan(rows)
    validate_membership(rows, plan, hmac_key=b"a" * 32)
    with pytest.raises(PreparationError):
        validate_membership(rows[:-1], plan, hmac_key=b"a" * 32)
    substitute = adapt_cscont_record(_cscont(split="validation", identity="substitute"))
    with pytest.raises(PreparationError):
        validate_membership(rows[:-1] + (substitute,), plan, hmac_key=b"a" * 32)
    with pytest.raises(PreparationError):
        validate_membership(rows[:2] + (rows[3], rows[2]) + rows[4:], plan, hmac_key=b"a" * 32)
    with pytest.raises(PreparationError):
        validate_membership(rows[:1] + rows, plan, hmac_key=b"a" * 32)


def test_membership_allows_documented_cross_condition_source_row_reuse() -> None:
    nested = _callhome(identity="reuse")
    mono = adapt_callhome_record(nested, logical_condition="MonoCont")
    filler = adapt_cscont_record(
        _cscont(
            component="callhome_monolingual_filler",
            identity="reuse",
            nested=nested,
        )
    )
    assert mono.source == filler.source
    assert mono.row_id == filler.row_id
    assert _pseudonym(b"k" * 32, "row", mono.source, mono.row_id) == _pseudonym(
        b"k" * 32,
        "row",
        filler.source,
        filler.row_id,
    )


def test_real_aggregate_policy_remains_exact() -> None:
    assert APPROVED_REAL_AGGREGATES["EnglishMono"].train_rows == 13_136
    assert APPROVED_REAL_AGGREGATES["MonoCont:spanish"].validation_lexical_tokens == 2_500
    assert APPROVED_REAL_AGGREGATES["CsCont"].validation_rows == 706


def test_tokenizer_protocol_rejects_normalizer_and_pretokenizer_changes() -> None:
    vocabulary = {
        "[PAD]": 0,
        "[UNK]": 1,
        "[CLS]": 2,
        "[SEP]": 3,
        "[MASK]": 4,
    }
    vocabulary.update({f"synthetic_{index}": index for index in range(5, 8_000)})
    payload = {
        "normalizer": {
            "type": "Sequence",
            "normalizers": [
                {"type": "NFC"},
                {
                    "type": "BertNormalizer",
                    "clean_text": True,
                    "handle_chinese_chars": False,
                    "strip_accents": False,
                    "lowercase": True,
                },
            ],
        },
        "pre_tokenizer": {"type": "BertPreTokenizer"},
        "model": {
            "type": "WordPiece",
            "unk_token": "[UNK]",
            "continuing_subword_prefix": "##",
            "vocab": vocabulary,
        },
    }
    _validate_tokenizer_json(payload)
    with pytest.raises(PreparationError):
        _validate_tokenizer_json({**payload, "pre_tokenizer": {"type": "Whitespace"}})
    changed = json.loads(json.dumps(payload))
    changed["normalizer"]["normalizers"][1]["strip_accents"] = True
    with pytest.raises(PreparationError):
        _validate_tokenizer_json(changed)


def test_synthetic_tokenizer_disables_special_tokens_and_is_unpublishable(
    tmp_path: Path,
) -> None:
    backend = _SyntheticBackend()
    tokenizer = make_synthetic_exact_tokenizer(backend)
    assert tokenizer.encode("synthetic") == (10, 11, 12)
    assert backend.calls == [("synthetic", False)]
    SyntheticParityCase("synthetic", (10, 11, 12))
    rows = _synthetic_population()
    bundle = prepare_synthetic_rows(rows, tokenizer=tokenizer, hmac_key=b"k" * 32)
    assert bundle.protocol_version == SYNTHETIC_PREPARATION_PROTOCOL_VERSION
    assert not hasattr(preparation_module, "publish_preparation")
    assert not (tmp_path / "synthetic-must-not-publish").exists()


def test_preparation_tokenizes_each_authorized_row_once_and_repeats_validation() -> None:
    rows = _synthetic_population()
    backend = _SyntheticBackend()
    bundle = prepare_synthetic_rows(
        rows,
        tokenizer=make_synthetic_exact_tokenizer(backend),
        hmac_key=b"k" * 32,
    )
    assert len(backend.calls) == len(rows)
    assert all(add_special_tokens is False for _, add_special_tokens in backend.calls)
    assert bundle.packing.source_wordpieces_by_group == bundle.packing.packed_wordpieces_by_group
    assert len(bundle.validation) == len(CONDITIONS) * len(approved_validation_seed_plans())
    assert all(not hasattr(row, "text") for row in bundle.rows)
    assert all(
        len(row.row_id) == 64
        and len(row.document_id) == 64
        and len(row.conversation_id) == 64
        for row in bundle.rows
    )
    repeated = materialize_fixed_validation(bundle.packing.sequences)
    for first, second in zip(bundle.validation, repeated, strict=True):
        assert first.record == second.record
        assert np.array_equal(first.masked_input_ids, second.masked_input_ids)
        assert first.masked_input_ids.dtype == np.uint16
        assert first.labels.dtype == np.int32


@pytest.mark.parametrize(("long_count", "candidate"), [(99, True), (100, False)])
def test_exposure_exactly_one_percent_passes_and_just_over_fails(
    long_count: int,
    candidate: bool,
) -> None:
    rows = list(_synthetic_population())
    rows[0] = adapt_callhome_record(
        _callhome(text="one two three boundary", identity="boundary"),
        logical_condition="EnglishMono",
    )

    class VariableBackend(_SyntheticBackend):
        def encode(self, text: str, *, add_special_tokens: bool):
            self.calls.append((text, add_special_tokens))
            count = long_count if text.endswith("boundary") else 98
            return SimpleNamespace(ids=[10] * count)

    operation = lambda: prepare_synthetic_rows(  # noqa: E731
        rows,
        tokenizer=make_synthetic_exact_tokenizer(VariableBackend()),
        hmac_key=b"k" * 32,
    )
    if candidate:
        bundle = operation()
        assert bundle.exposure_audit.maximum_projected_exposure_difference_fraction == 0.01
    else:
        with pytest.raises(ExposureAcceptanceError) as caught:
            operation()
        assert caught.value.diagnostics["difference_fraction"] > 0.01
        assert "row-" not in json.dumps(dict(caught.value.diagnostics))


def test_hmac_namespaces_separate_sources_and_entity_types() -> None:
    key = b"k" * 32
    assert _pseudonym(key, "row", "callhome_eng", "same") != _pseudonym(
        key,
        "row",
        "callhome_spa",
        "same",
    )
    assert _pseudonym(key, "row", "callhome_eng", "same") != _pseudonym(
        key,
        "document",
        "callhome_eng",
        "same",
    )
    assert _pseudonym(key, "row", "callhome_eng", "same") != _pseudonym(
        b"z" * 32,
        "row",
        "callhome_eng",
        "same",
    )


def test_provenance_contains_only_keyed_roles_and_pseudonyms() -> None:
    rows = _synthetic_population()
    bundle = prepare_synthetic_rows(
        rows,
        tokenizer=make_synthetic_exact_tokenizer(_SyntheticBackend()),
        hmac_key=b"k" * 32,
    )
    payload = _provenance_payload(bundle.packing.sequences[0], b"k" * 32)
    encoded = canonical_json_bytes(payload)
    assert b"row-" not in encoded
    assert b"document-" not in encoded
    assert b"speaker" not in encoded
    assert b"one two three" not in encoded


def test_key_opening_requires_owner_only_regular_file_and_rejects_git_location(
    tmp_path: Path,
) -> None:
    key = tmp_path / "separate.key"
    create_hmac_key(key)
    assert stat.S_IMODE(key.stat().st_mode) == 0o600
    assert len(load_hmac_key(key)) == 32
    with pytest.raises(PreparationError):
        create_hmac_key(key)
    os.chmod(key, 0o644)
    with pytest.raises(PreparationError):
        load_hmac_key(key)
    repository = tmp_path / "repository"
    repository.mkdir()
    (repository / ".git").mkdir()
    inside = repository / "key"
    inside.write_bytes(b"k" * 32)
    os.chmod(inside, 0o600)
    with pytest.raises(PreparationError):
        load_hmac_key(inside)


def test_file_opening_rejects_intermediate_parent_symlink(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    target = real / "rows.jsonl"
    target.write_bytes(_line(_callhome()))
    os.chmod(target, 0o600)
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(PreparationError):
        tuple(read_sealed_callhome_jsonl(link / "rows.jsonl"))


def test_publication_paths_reject_repo_overlap_existing_and_symlink(
    tmp_path: Path,
) -> None:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    key = tmp_path / "key"
    key.write_bytes(b"k" * 32)
    os.chmod(key, 0o600)
    with pytest.raises(PreparationError):
        validate_publication_paths(
            Path(preparation_module.__file__).resolve().parents[3] / "candidate-out",
            input_roots=(inputs,),
            hmac_key_path=key,
        )
    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(PreparationError):
        validate_publication_paths(
            existing,
            input_roots=(inputs,),
            hmac_key_path=key,
        )
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    link = tmp_path / "parent-link"
    link.symlink_to(real_parent, target_is_directory=True)
    with pytest.raises(PreparationError):
        validate_publication_paths(
            link / "out",
            input_roots=(inputs,),
            hmac_key_path=key,
        )


def test_production_factory_and_publication_are_checksum_anchored(
    tmp_path: Path,
) -> None:
    fixture = build_synthetic_preparation_fixture(tmp_path)
    assert fixture.bundle.input_anchor is None
    assert isinstance(fixture.snapshot, SyntheticPreparationSnapshot)
    fixture.snapshot._validate()
    assert stat.S_IMODE(fixture.output_root.stat().st_mode) == 0o700
    assert all(
        stat.S_IMODE(path.stat().st_mode) == (0o700 if path.is_dir() else 0o600)
        for path in fixture.output_root.rglob("*")
    )
    serialized = b"".join(
        path.read_bytes()
        for path in fixture.output_root.rglob("*")
        if path.is_file()
    )
    assert fixture.hmac_key not in serialized
    assert b"synthetic-speaker-metadata" not in serialized
    assert "synthetic-speaker-metadata" not in repr(fixture.bundle.rows)
    assert all(
        "synthetic-speaker-metadata" not in repr(vars(row))
        for row in fixture.bundle.rows
    )
    key_path = _write_privacy_reconciliation_key(tmp_path / "privacy-key.bin")
    with pytest.raises(PreparationError):
        load_preparation_candidate(
            fixture.output_root,
            reconciliation_key_path=key_path,
        )


def test_production_factory_rejects_same_total_constituent_substitution(
    tmp_path: Path,
) -> None:
    fixture = build_synthetic_preparation_fixture(tmp_path)
    membership_path = fixture.output_root / "synthetic-artifacts/membership.json"
    membership = json.loads(membership_path.read_bytes())
    target = next(row for row in membership if row["condition"] == "MonoCont")
    target["row_content_binding_hmac_sha256"] = "0" * 64
    membership_path.write_bytes(canonical_json_bytes(membership))
    os.chmod(membership_path, 0o600)
    _rewrite_synthetic_outer_identities(fixture.output_root)
    with pytest.raises(PreparationError):
        load_synthetic_preparation_candidate(fixture.output_root)


def test_candidate_loader_rejects_minimal_empty_and_missing_directories(
    tmp_path: Path,
) -> None:
    root = tmp_path / "minimal"
    root.mkdir()
    os.chmod(root, 0o700)
    for name, payload in (
        ("checksums.json", {}),
        ("PREPARATION_MANIFEST.json", {}),
        ("CANDIDATE_COMPLETE.json", {}),
    ):
        path = root / name
        path.write_bytes(canonical_json_bytes(payload))
        os.chmod(path, 0o600)
    key_path = _write_privacy_reconciliation_key(tmp_path / "privacy-key.bin")
    with pytest.raises(TypeError):
        load_preparation_candidate(root)
    with pytest.raises(PreparationError):
        load_preparation_candidate(root, reconciliation_key_path=key_path)
    with pytest.raises(PreparationError):
        load_preparation_candidate(
            tmp_path / "missing",
            reconciliation_key_path=key_path,
        )


@pytest.mark.parametrize("mutation", ["escape", "extra", "permissions"])
def test_candidate_loader_rejects_path_escape_extra_files_and_permissions(
    tmp_path: Path,
    mutation: str,
) -> None:
    fixture = build_synthetic_preparation_fixture(tmp_path)
    if mutation == "escape":
        path = fixture.output_root / "SYNTHETIC-ARTIFACTS.json"
        payload = json.loads(path.read_bytes())
        payload["artifacts"]["../outside.bin"] = "0" * 64
        path.write_bytes(canonical_json_bytes(payload))
        os.chmod(path, 0o600)
    elif mutation == "extra":
        extra = fixture.output_root / "extra.bin"
        extra.write_bytes(b"extra")
        os.chmod(extra, 0o600)
    else:
        os.chmod(
            fixture.output_root / "synthetic-artifacts/runtime.json",
            0o644,
        )
    with pytest.raises(PreparationError):
        load_synthetic_preparation_candidate(fixture.output_root)


def test_snapshot_detects_candidate_directory_mutation(
    tmp_path: Path,
) -> None:
    fixture = build_synthetic_preparation_fixture(tmp_path)
    runtime = fixture.output_root / "synthetic-artifacts/runtime.json"
    content = runtime.read_bytes()
    runtime.write_bytes(
        content.replace(b'"runtime_identity"', b'"runtime_identitY"', 1)
    )
    os.chmod(runtime, 0o600)
    with pytest.raises(PreparationError):
        fixture.snapshot._validate()


def test_checksum_map_and_manifest_are_byte_deterministic(
    tmp_path: Path,
) -> None:
    first = build_synthetic_preparation_fixture(tmp_path / "first")
    second = build_synthetic_preparation_fixture(tmp_path / "second")
    assert second.published.manifest_sha256 == first.published.manifest_sha256
    assert (
        second.published.artifact_map_sha256
        == first.published.artifact_map_sha256
    )


def test_publication_target_appearance_race_is_no_overwrite(
    tmp_path: Path,
) -> None:
    target = tmp_path / "synthetic-candidate"

    def race(stage: str) -> None:
        if stage == "before_commit":
            target.mkdir()
            os.chmod(target, 0o700)

    with pytest.raises(PreparationError):
        build_synthetic_preparation_fixture(
            tmp_path,
            synthetic_test_hook=race,
        )
    assert target.is_dir()
    assert not (target / "SYNTHETIC-COMPLETE.json").exists()
    assert not list(tmp_path.glob(".synthetic-candidate.synthetic-staging-*"))


def test_precommit_failure_cleans_staging_without_candidate_marker(
    tmp_path: Path,
) -> None:
    def fail(stage: str) -> None:
        if stage == "before_commit":
            raise OSError("synthetic fsync failure")

    with pytest.raises(PreparationError):
        build_synthetic_preparation_fixture(
            tmp_path,
            synthetic_test_hook=fail,
        )
    assert not (tmp_path / "synthetic-candidate").exists()
    assert not list(tmp_path.glob(".synthetic-candidate.synthetic-staging-*"))


def test_postcommit_failure_is_explicit_and_preserves_candidate_directory(
    tmp_path: Path,
) -> None:
    def fail(stage: str) -> None:
        if stage == "after_commit_before_parent_fsync":
            raise OSError("synthetic parent fsync failure")

    with pytest.raises(PublicationCommittedError) as caught:
        build_synthetic_preparation_fixture(
            tmp_path,
            synthetic_test_hook=fail,
        )
    assert caught.value.committed is True
    assert (
        tmp_path / "synthetic-candidate" / "SYNTHETIC-COMPLETE.json"
    ).is_file()


@pytest.mark.parametrize(
    "stage",
    [
        "before_mkdir",
        "before_stage_open",
        "before_stage_fstat",
        "before_commit",
        "before_atomic_rename",
    ],
)
def test_precommit_resource_window_closes_and_cleans_for_every_stage(
    tmp_path: Path,
    stage: str,
) -> None:
    fixture = build_synthetic_preparation_fixture(tmp_path / "source")
    parent = tmp_path / "attempt"
    parent.mkdir()
    os.chmod(parent, 0o700)
    descriptor_count = _open_descriptor_count()

    def fail(current: str) -> None:
        if current == stage:
            raise OSError(f"injected {stage} failure")

    with pytest.raises(PreparationError):
        preparation_module.publish_synthetic_preparation(
            fixture.bundle,
            output_root=parent / "candidate",
            hmac_key=fixture.hmac_key,
            synthetic_test_hook=fail,
        )
    assert _open_descriptor_count() == descriptor_count
    assert not (parent / "candidate").exists()
    assert not list(parent.glob(".candidate.synthetic-staging-*"))


@pytest.mark.parametrize("failure", ["file_fsync", "nested_fsync", "staging_fsync"])
def test_precommit_fsync_failures_close_and_clean(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    fixture = build_synthetic_preparation_fixture(tmp_path / "source")
    parent = tmp_path / "attempt"
    parent.mkdir()
    os.chmod(parent, 0o700)
    descriptor_count = _open_descriptor_count()
    real_fsync = preparation_module.os.fsync
    real_tree_fsync = preparation_module._fsync_tree_descriptor

    if failure == "file_fsync":
        def fail_fsync(descriptor: int) -> None:
            if stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise OSError("injected file fsync failure")
            real_fsync(descriptor)

        monkeypatch.setattr(preparation_module.os, "fsync", fail_fsync)
    elif failure == "nested_fsync":
        def fail_fsync(descriptor: int) -> None:
            if stat.S_ISDIR(os.fstat(descriptor).st_mode):
                raise OSError("injected nested-directory fsync failure")
            real_fsync(descriptor)

        monkeypatch.setattr(preparation_module.os, "fsync", fail_fsync)
    else:
        def fail_tree_fsync(descriptor: int) -> None:
            real_tree_fsync(descriptor)
            raise OSError("injected staging fsync failure")

        monkeypatch.setattr(
            preparation_module,
            "_fsync_tree_descriptor",
            fail_tree_fsync,
        )

    with pytest.raises(PreparationError):
        preparation_module.publish_synthetic_preparation(
            fixture.bundle,
            output_root=parent / "candidate",
            hmac_key=fixture.hmac_key,
        )
    assert _open_descriptor_count() == descriptor_count
    assert not (parent / "candidate").exists()
    assert not list(parent.glob(".candidate.synthetic-staging-*"))


def test_one_field_backend_manifest_cannot_assert_runtime_correction(
) -> None:
    historical = {
        "backend_correction_id": "tokenizers_0_22_2_sorted_word_counts_v1"
    }
    with pytest.raises(PreparationError):
        preparation_module._validate_historical_identity_record(
            historical,
            None,
        )


def test_no_fixture_contains_real_paths_or_material() -> None:
    rows = _synthetic_population()
    assert all(row.text == "one two three" for row in rows)
    assert {row.source for row in rows} <= {
        "callhome_eng",
        "callhome_spa",
        "bangor_cgwords",
    }


def _rewrite_synthetic_outer_identities(root: Path) -> None:
    artifact_map_path = root / "SYNTHETIC-ARTIFACTS.json"
    artifact_map = json.loads(artifact_map_path.read_bytes())
    artifact_map["artifacts"] = {
        name: sha256((root / name).read_bytes()).hexdigest()
        for name in artifact_map["artifacts"]
    }
    artifact_map_bytes = canonical_json_bytes(artifact_map)
    artifact_map_path.write_bytes(artifact_map_bytes)
    os.chmod(artifact_map_path, 0o600)
    artifact_map_identity = sha256(artifact_map_bytes).hexdigest()

    manifest_path = root / "SYNTHETIC-MANIFEST.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest.pop("manifest_sha256")
    manifest["artifact_map_sha256"] = artifact_map_identity
    manifest_identity = sha256(canonical_json_bytes(manifest)).hexdigest()
    manifest_path.write_bytes(
        canonical_json_bytes({**manifest, "manifest_sha256": manifest_identity})
    )
    os.chmod(manifest_path, 0o600)

    completion_path = root / "SYNTHETIC-COMPLETE.json"
    completion_path.write_bytes(
        canonical_json_bytes(
            {
                "artifact_map_sha256": artifact_map_identity,
                "manifest_sha256": manifest_identity,
                "protocol": SYNTHETIC_PREPARATION_PROTOCOL_VERSION,
                "synthetic_only": True,
            }
        )
    )
    os.chmod(completion_path, 0o600)


def test_training_token_mutation_is_rejected_after_all_outer_rehashing(
    tmp_path: Path,
) -> None:
    fixture = build_synthetic_preparation_fixture(tmp_path)
    path = (
        fixture.output_root
        / "synthetic-artifacts/arrays/EnglishMono/train/input_ids.npy"
    )
    with path.open("rb") as handle:
        inputs = np.load(handle, allow_pickle=False)
    assert inputs[0, 1] == 5
    inputs[0, 1] = 6
    with path.open("wb") as handle:
        np.save(handle, inputs, allow_pickle=False)
    os.chmod(path, 0o600)
    _rewrite_synthetic_outer_identities(fixture.output_root)
    with pytest.raises(PreparationError, match="token content binding"):
        load_synthetic_preparation_candidate(fixture.output_root)


def test_wrong_privacy_reconciliation_key_rejects_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = build_synthetic_preparation_fixture(tmp_path)
    monkeypatch.setattr(
        preparation_module,
        "_SYNTHETIC_PRIVACY_RECONCILIATION_KEY",
        b"w" * 32,
    )
    with pytest.raises(PreparationError, match="token content binding"):
        load_synthetic_preparation_candidate(fixture.output_root)


@pytest.mark.parametrize(
    "mutation",
    [
        "reordered_row_segments",
        "altered_range",
        "missing_range",
        "duplicated_range",
        "cross_row_substitution",
    ],
)
def test_training_provenance_mutations_rejected_after_outer_rehash(
    tmp_path: Path,
    mutation: str,
) -> None:
    fixture = build_synthetic_preparation_fixture(tmp_path)
    path = fixture.output_root / "synthetic-artifacts/provenance.json"
    provenance = json.loads(path.read_bytes())
    candidates = [
        index
        for index, example in enumerate(provenance)
        if example["condition"] == "CsCont" and example["split"] == "train"
    ]
    assert len(candidates) >= 2
    first, second = candidates[:2]
    if mutation == "reordered_row_segments":
        provenance[first], provenance[second] = provenance[second], provenance[first]
    elif mutation == "altered_range":
        provenance[first]["ranges"][0]["packed_token_range"][1] -= 1
    elif mutation == "missing_range":
        provenance[first]["ranges"].clear()
    elif mutation == "duplicated_range":
        provenance[first]["ranges"].append(dict(provenance[first]["ranges"][0]))
    else:
        replacement = provenance[second]["ranges"][0]
        target = provenance[first]["ranges"][0]
        for field in (
            "source_role",
            "row_pseudonym",
            "conversation_pseudonym",
            "row_order",
            "source_row_token_count",
        ):
            target[field] = replacement[field]
    path.write_bytes(canonical_json_bytes(provenance))
    os.chmod(path, 0o600)
    _rewrite_synthetic_outer_identities(fixture.output_root)
    with pytest.raises(PreparationError):
        load_synthetic_preparation_candidate(fixture.output_root)


def test_swapped_equal_length_rows_rejected_after_outer_rehash(
    tmp_path: Path,
) -> None:
    fixture = build_synthetic_preparation_fixture(tmp_path)
    provenance_path = fixture.output_root / "synthetic-artifacts/provenance.json"
    provenance = json.loads(provenance_path.read_bytes())
    group = [
        example
        for example in provenance
        if example["condition"] == "CsCont" and example["split"] == "train"
    ]
    bangor_index = next(
        index
        for index, example in enumerate(group)
        if example["ranges"][0]["source_role"] == "bangor_cgwords"
    )
    other_index = next(index for index in range(len(group)) if index != bangor_index)
    bangor_range = group[bangor_index]["ranges"][0]
    arrays_path = (
        fixture.output_root
        / "synthetic-artifacts/arrays/CsCont/train/input_ids.npy"
    )
    with arrays_path.open("rb") as handle:
        inputs = np.load(handle, allow_pickle=False)
    packed_start, packed_end = bangor_range["packed_token_range"]
    altered_tokens = tuple(int(value) for value in inputs[bangor_index, packed_start:packed_end])
    assert altered_tokens == (5, 6, 7)
    inputs[bangor_index, packed_start:packed_end] = np.asarray(
        (5, 7, 6),
        dtype=np.uint16,
    )

    membership_path = fixture.output_root / "synthetic-artifacts/membership.json"
    membership = json.loads(membership_path.read_bytes())
    target = next(
        row
        for row in membership
        if row["condition"] == "CsCont"
        and row["split"] == "train"
        and row["source_role"] == bangor_range["source_role"]
        and row["row_pseudonym"] == bangor_range["row_pseudonym"]
    )
    target["row_content_binding_hmac_sha256"] = (
        preparation_module._source_row_token_content_binding(
            fixture.hmac_key,
            protocol=SYNTHETIC_PREPARATION_PROTOCOL_VERSION,
            source_namespace=target["source_role"],
            split=target["split"],
            row_pseudonym=target["row_pseudonym"],
            conversation_pseudonym=target["conversation_pseudonym"],
            row_order=target["row_order"],
            lexical_token_count=target["lexical_token_count"],
            source_token_count=target["source_token_count"],
            token_ids=(5, 7, 6),
        )
    )
    membership_path.write_bytes(canonical_json_bytes(membership))
    os.chmod(membership_path, 0o600)

    inputs[[bangor_index, other_index]] = inputs[[other_index, bangor_index]]
    with arrays_path.open("wb") as handle:
        np.save(handle, inputs, allow_pickle=False)
    os.chmod(arrays_path, 0o600)
    _rewrite_synthetic_outer_identities(fixture.output_root)
    with pytest.raises(PreparationError, match="token content binding"):
        load_synthetic_preparation_candidate(fixture.output_root)


def test_synthetic_protocol_cannot_cross_production_candidate_loader(
    tmp_path: Path,
) -> None:
    fixture = build_synthetic_preparation_fixture(tmp_path)
    assert isinstance(fixture.snapshot, SyntheticPreparationSnapshot)
    assert not isinstance(fixture.snapshot, PreparationSnapshot)
    assert not hasattr(fixture.published, "manifest")
    assert (fixture.output_root / "SYNTHETIC-COMPLETE.json").is_file()
    assert not (fixture.output_root / "CANDIDATE_COMPLETE.json").exists()
    key_path = _write_privacy_reconciliation_key(tmp_path / "privacy-key.bin")
    with pytest.raises(PreparationError):
        load_preparation_candidate(
            fixture.output_root,
            reconciliation_key_path=key_path,
        )
    assert not hasattr(preparation_module, "publish_preparation")
    assert not (tmp_path / "forbidden-production-output").exists()


def test_removed_two_step_production_api_and_seal_fabrication_fail(
    tmp_path: Path,
) -> None:
    del tmp_path
    assert not hasattr(preparation_module, "prepare_production_inputs")
    assert not hasattr(preparation_module, "publish_preparation")
    assert not hasattr(preparation_module, "_PRODUCTION_SEAL")


def test_candidate_controls_have_no_in_process_approval_mechanism() -> None:
    source = inspect.getsource(preparation_module)
    assert "AcceptedPreparationBinding" not in source
    assert "acceptance_hmac" not in source
    assert "_PRODUCTION_SEAL" not in source
    assert "_SYNTHETIC_SEAL" not in source
    assert preparation_module._CONTROL_FILES == {
        "checksums.json",
        "PREPARATION_MANIFEST.json",
        "CANDIDATE_COMPLETE.json",
    }
    payload = preparation_module._candidate_checksum_payload(
        {"artifact.bin": b"candidate"},
        inventory={
            "artifact.bin",
            "checksums.json",
            "CANDIDATE_COMPLETE.json",
        },
        protocol_version=preparation_module.PREPARATION_PROTOCOL_VERSION,
    )
    assert payload["status"] == "candidate_unapproved"
    assert payload["completion_state"] == {
        "complete": True,
        "status": "candidate_unapproved",
    }
    with pytest.raises(PreparationError, match="runner-derived"):
        preparation_module.PublishedPreparationCandidate()


def test_candidate_checksum_record_is_deterministic_and_inventory_bound() -> None:
    files = {
        "PREPARATION_MANIFEST.json": canonical_json_bytes(
            {"status": "candidate_unapproved"}
        ),
        "arrays/example.bin": b"array",
    }
    inventory = set(files) | {"checksums.json", "CANDIDATE_COMPLETE.json"}
    first, first_bytes = preparation_module._derive_candidate_checksum_record(
        files,
        inventory=inventory,
        protocol_version=preparation_module.PREPARATION_PROTOCOL_VERSION,
    )
    second, second_bytes = preparation_module._derive_candidate_checksum_record(
        dict(reversed(tuple(files.items()))),
        inventory=reversed(tuple(inventory)),
        protocol_version=preparation_module.PREPARATION_PROTOCOL_VERSION,
    )
    assert first.identity_sha256 == second.identity_sha256
    assert first_bytes == second_bytes
    changed, _ = preparation_module._derive_candidate_checksum_record(
        {**files, "arrays/example.bin": b"changed"},
        inventory=inventory,
        protocol_version=preparation_module.PREPARATION_PROTOCOL_VERSION,
    )
    assert changed.identity_sha256 != first.identity_sha256


def test_hmac_use_is_limited_to_privacy_pseudonymization() -> None:
    hmac_callers = {
        name
        for name, value in vars(preparation_module).items()
        if inspect.isfunction(value) and "hmac.new" in inspect.getsource(value)
    }
    assert hmac_callers == {
        "_pseudonym",
        "_recompute_membership_digest",
        "_source_row_token_content_binding",
        "_stream_binding",
        "validate_membership",
    }
    assert "authentic" not in inspect.getsource(preparation_module._pseudonym)


@pytest.mark.parametrize("control", ["checksum", "aggregates"])
def test_patched_production_controls_cannot_change_reviewed_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    control: str,
) -> None:
    if control == "checksum":
        monkeypatch.setattr(
            preparation_module,
            "APPROVED_CALLHOME_CHECKSUM_RECORD_SHA256",
            "0" * 64,
        )
    else:
        monkeypatch.setattr(
            preparation_module,
            "APPROVED_REAL_AGGREGATES",
            {},
        )
    paths = ProductionPreparationPaths(
        tmp_path / "absent-callhome",
        tmp_path / "absent-cscont",
        tmp_path / "absent-tokenizer",
        tmp_path / "absent-key",
    )
    monkeypatch.setenv("PYTHONHASHSEED", "1729")
    monkeypatch.setenv("TOKENIZERS_PARALLELISM", "false")
    with pytest.raises(PreparationError, match="closed production"):
        prepare_and_publish_production(
            paths,
            APPROVED_PRIVATE_OUTPUT_ROOT.expanduser(),
        )


def test_production_runtime_controls_cannot_be_supplied_by_caller(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PYTHONHASHSEED", raising=False)
    monkeypatch.delenv("TOKENIZERS_PARALLELISM", raising=False)
    input_accessed = False

    def reject_input_access(paths: ProductionPreparationPaths) -> None:
        nonlocal input_accessed
        del paths
        input_accessed = True
        raise AssertionError("private input processing must not begin")

    monkeypatch.setattr(
        preparation_module,
        "_prepare_production_inputs",
        reject_input_access,
    )
    paths = ProductionPreparationPaths(
        tmp_path / "absent-callhome",
        tmp_path / "absent-cscont",
        tmp_path / "absent-tokenizer",
        tmp_path / "absent-key",
    )
    with pytest.raises(PreparationError, match="environment controls are absent"):
        prepare_and_publish_production(
            paths,
            APPROVED_PRIVATE_OUTPUT_ROOT.expanduser(),
        )
    with pytest.raises(TypeError):
        prepare_and_publish_production(
            paths,
            APPROVED_PRIVATE_OUTPUT_ROOT.expanduser(),
            {
                "PYTHONHASHSEED": "1729",
                "TOKENIZERS_PARALLELISM": "false",
            },
        )
    assert input_accessed is False
    assert set(inspect.signature(prepare_and_publish_production).parameters) == {
        "paths",
        "output_root",
    }


def test_public_output_guard_ignores_redirecting_module_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []
    input_accessed = False

    class RedirectingPath:
        def __new__(cls, value: object = "") -> Path:
            del cls
            calls.append(value)
            return APPROVED_PRIVATE_OUTPUT_ROOT.expanduser()

    def permissive_prepare(paths: object) -> object:
        nonlocal input_accessed
        del paths
        input_accessed = True
        return object()

    monkeypatch.setattr(preparation_module, "Path", RedirectingPath)
    monkeypatch.setattr(
        preparation_module,
        "_prepare_production_inputs",
        permissive_prepare,
    )
    unapproved = tmp_path / "redirect-attempt"
    paths = ProductionPreparationPaths(
        tmp_path / "absent-callhome",
        tmp_path / "absent-cscont",
        tmp_path / "absent-tokenizer",
        tmp_path / "absent-key",
    )
    with pytest.raises(PreparationError, match="output root is not"):
        prepare_and_publish_production(paths, unapproved)
    assert calls == []
    assert input_accessed is False
    assert not unapproved.exists()
    assert not list(tmp_path.glob(".*staging*"))


def test_combined_public_wrapper_global_replacement_cannot_redirect_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def permissive(*args: object, **kwargs: object) -> object:
        del args, kwargs
        calls.append("permissive")
        return object()

    class RedirectingPath:
        def __new__(cls, value: object = "") -> Path:
            del cls, value
            calls.append("path")
            return APPROVED_PRIVATE_OUTPUT_ROOT.expanduser()

    for name, replacement in {
        "Path": RedirectingPath,
        "APPROVED_PRIVATE_OUTPUT_ROOT": tmp_path / "redirected-approved",
        "APPROVED_REAL_AGGREGATES": {},
        "APPROVED_TOKENIZER_CHECKSUM_RECORD_SHA256": "0" * 64,
        "APPROVED_CALLHOME_CHECKSUM_RECORD_SHA256": "0" * 64,
        "APPROVED_CSCONT_CHECKSUM_RECORD_SHA256": "0" * 64,
        "_prepare_production_inputs": permissive,
        "_publish_preparation": permissive,
        "_actual_runtime_environment_controls": permissive,
    }.items():
        monkeypatch.setattr(preparation_module, name, replacement)
    unapproved = tmp_path / "combined-redirect-attempt"
    paths = ProductionPreparationPaths(
        tmp_path / "absent-callhome",
        tmp_path / "absent-cscont",
        tmp_path / "absent-tokenizer",
        tmp_path / "absent-key",
    )
    with pytest.raises(PreparationError, match="output root is not"):
        prepare_and_publish_production(paths, unapproved)
    assert calls == []
    assert not unapproved.exists()
    assert not (tmp_path / "redirected-approved").exists()
    assert not list(tmp_path.glob(".*staging*"))


def _closed_reviewed_ingestion() -> tuple[
    dict[str, object],
    FunctionType,
    dict[str, object],
]:
    closed_values = inspect.getclosurevars(
        prepare_and_publish_production
    ).nonlocals
    reviewed_prepare = closed_values["reviewed_prepare_production_inputs"]
    assert isinstance(reviewed_prepare, FunctionType)
    return closed_values, reviewed_prepare, reviewed_prepare.__globals__


def _nested_global_names(code: CodeType) -> set[str]:
    names = {
        str(instruction.argval)
        for instruction in dis.get_instructions(code)
        if instruction.opname in {"LOAD_GLOBAL", "LOAD_NAME"}
    }
    for constant in code.co_consts:
        if isinstance(constant, CodeType):
            names.update(_nested_global_names(constant))
    return names


def _application_methods(class_type: type[object]) -> tuple[FunctionType, ...]:
    methods: list[FunctionType] = []
    for attribute in vars(class_type).values():
        functions: tuple[FunctionType | None, ...]
        if isinstance(attribute, FunctionType):
            functions = (attribute,)
        elif isinstance(attribute, staticmethod | classmethod):
            functions = (attribute.__func__,)
        elif isinstance(attribute, property):
            functions = (attribute.fget, attribute.fset, attribute.fdel)
        else:
            functions = ()
        methods.extend(
            function
            for function in functions
            if (
                function is not None
                and function.__module__ == class_type.__module__
            )
        )
    return tuple(methods)


def _reachable_production_lifecycle_inventory(
    *,
    blocked_names: frozenset[str] = frozenset(),
) -> tuple[
    set[str],
    set[str],
    dict[str, set[str]],
    dict[str, set[str]],
]:
    closed_values, reviewed_prepare, reviewed_globals = (
        _closed_reviewed_ingestion()
    )
    root_names = (
        "_prepare_production_inputs",
        "_publish_preparation",
        "collect_runtime_identity",
        "_validate_historical_identity_record",
        "_load_preparation_candidate",
    )
    pending = [
        reviewed_globals[name]
        for name in root_names
        if name not in blocked_names
    ]
    seen_functions: set[int] = set()
    missing_functions: set[str] = set()
    mutable_authorities: set[str] = set()
    local_functions: set[str] = set()
    local_classes: set[str] = set()
    external_functions = {
        module: set()
        for module in preparation_module._PRODUCTION_LIFECYCLE_REVIEWED_EXTERNAL_FUNCTIONS
    }
    external_classes = {
        module: set()
        for module in preparation_module._PRODUCTION_LIFECYCLE_REVIEWED_EXTERNAL_CLASSES
    }
    reviewed_module_globals = {
        preparation_module.__name__: reviewed_globals,
    }

    def include(
        value: object,
        *,
        application_authority: bool = True,
    ) -> None:
        if isinstance(value, FunctionType):
            if value.__name__ in blocked_names:
                missing_functions.add(value.__name__)
                return
            module = value.__module__
            if module == preparation_module.__name__:
                if "." not in value.__qualname__:
                    local_functions.add(value.__name__)
                if id(value) not in seen_functions:
                    pending.append(value)
            elif module.startswith("cslm."):
                if "." not in value.__qualname__:
                    external_functions.setdefault(module, set()).add(
                        value.__name__
                    )
                if id(value) not in seen_functions:
                    pending.append(value)
        elif isinstance(value, type):
            module = value.__module__
            if module == preparation_module.__name__:
                local_classes.add(value.__name__)
                pending.extend(_application_methods(value))
            elif module.startswith("cslm."):
                external_classes.setdefault(module, set()).add(value.__name__)
                if not issubclass(value, BaseException):
                    pending.extend(_application_methods(value))
        elif isinstance(
            value,
            MutableMapping | MutableSequence | MutableSet | bytearray,
        ) and application_authority:
            mutable_authorities.add(
                f"{type(value).__module__}.{type(value).__qualname__}"
            )

    while pending:
        function = pending.pop()
        if id(function) in seen_functions:
            continue
        seen_functions.add(id(function))
        module = function.__module__
        if module == preparation_module.__name__:
            if "." not in function.__qualname__:
                local_functions.add(function.__name__)
            if function.__globals__ is not reviewed_globals:
                assert (
                    function.__code__.co_filename == "<string>"
                    or Path(function.__code__.co_filename).name
                    == "dataclasses.py"
                )
        elif module.startswith("cslm."):
            if "." not in function.__qualname__:
                external_functions.setdefault(module, set()).add(
                    function.__name__
                )
            expected_globals = reviewed_module_globals.get(module)
            source_file = Path(sys.modules[module].__file__).resolve()
            function_file = Path(function.__code__.co_filename)
            if (
                function.__code__.co_filename != "<string>"
                and function_file.resolve() == source_file
            ):
                if expected_globals is None:
                    reviewed_module_globals[module] = function.__globals__
                else:
                    assert function.__globals__ is expected_globals
            else:
                assert (
                    function.__code__.co_filename == "<string>"
                    or function_file.name == "dataclasses.py"
                )
        application_authority = (
            Path(function.__code__.co_filename).name != "dataclasses.py"
        )
        for value in function.__defaults__ or ():
            include(value, application_authority=application_authority)
        for value in (function.__kwdefaults__ or {}).values():
            include(value, application_authority=application_authority)
        for cell in function.__closure__ or ():
            include(
                cell.cell_contents,
                application_authority=application_authority,
            )
        for name in _nested_global_names(function.__code__):
            if name in function.__globals__:
                if name in blocked_names:
                    missing_functions.add(name)
                    continue
                include(
                    function.__globals__[name],
                    application_authority=application_authority,
                )
    public_global_dependencies = {
        name: prepare_and_publish_production.__globals__[name]
        for name in _nested_global_names(
            prepare_and_publish_production.__code__
        )
        if name in prepare_and_publish_production.__globals__
    }
    assert not any(
        (
            isinstance(value, FunctionType | type)
            and getattr(value, "__module__", "").startswith("cslm.")
        )
        for value in public_global_dependencies.values()
    )
    assert closed_values["reviewed_path_type"] is Path
    assert isinstance(closed_values["reviewed_approved_output"], Path)
    assert closed_values["reviewed_prepare_production_inputs"] is reviewed_prepare
    assert (
        closed_values["reviewed_publish_preparation"]
        is reviewed_globals["_publish_preparation"]
    )
    assert not missing_functions, (
        "reviewed production lifecycle is missing: "
        + ", ".join(sorted(missing_functions))
    )
    assert not mutable_authorities, (
        "reviewed production lifecycle contains mutable authority: "
        + ", ".join(sorted(mutable_authorities))
    )
    return (
        local_functions,
        local_classes,
        external_functions,
        external_classes,
    )


def _test_canonical_json(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode()


def _write_reviewed_frozen_root(
    root: Path,
    *,
    line: bytes,
) -> tuple[Path, str]:
    root.mkdir()
    os.chmod(root, 0o700)
    population_path = root / "rows.jsonl"
    population_path.write_bytes(line)
    os.chmod(population_path, 0o600)
    checksum_bytes = _test_canonical_json(
        {"rows.jsonl": sha256(line).hexdigest()}
    )
    checksum_path = root / "checksums.json"
    checksum_path.write_bytes(checksum_bytes)
    os.chmod(checksum_path, 0o600)
    return root, sha256(checksum_bytes).hexdigest()


def _exercise_reviewed_ingestion_components(
    *,
    reviewed_globals: dict[str, object],
    frozen_root: Path,
    checksum_identity: str,
    expected_line: bytes,
    key_path: Path,
    tokenizer: ExactTokenizer,
) -> None:
    reviewed_verify = reviewed_globals["_verify_frozen_root"]
    verified = reviewed_verify(
        frozen_root,
        checksum_record_name="checksums.json",
        expected_record_identity=checksum_identity,
    )
    try:
        assert tuple(
            reviewed_globals["_snapshot_relative_jsonl_lines"](
                verified,
                "rows.jsonl",
            )
        ) == (expected_line,)
    finally:
        os.close(verified.root_descriptor)
    with pytest.raises(PreparationError):
        reviewed_verify(
            frozen_root,
            checksum_record_name="checksums.json",
            expected_record_identity="0" * 64,
        )

    key = reviewed_globals["load_hmac_key"](
        key_path,
        forbidden_roots=(frozen_root,),
    )
    assert key == b"k" * 32

    duplicate = b'{"source":"callhome_eng","source":"callhome_eng"}\n'
    with pytest.raises(PreparationError):
        reviewed_globals["_decode_cscont_line"](duplicate)
    with pytest.raises(PreparationError):
        reviewed_globals["_default_authorized_decoder"](duplicate)

    callhome_record = _callhome(identity="reviewed-callhome", turn_index=7)
    callhome_line = _line(callhome_record)
    assert reviewed_globals["scan_sealed_callhome_split"](callhome_line) == "train"
    decoded_callhome = reviewed_globals["_adapt_callhome_record"](
        reviewed_globals["_default_authorized_decoder"](callhome_line),
        logical_condition="EnglishMono",
        artifact_format_version=preparation_module.CALLHOME_ARTIFACT_FORMAT_VERSION,
        input_role="callhome:english_train.jsonl",
        input_ordinal=0,
    )
    assert decoded_callhome.row_order == 7
    assert decoded_callhome.conversation_id == callhome_record["conversation_ref"]

    valid = synthetic_bangor_record(identity="reviewed-bangor", split="train")
    state = reviewed_globals["_derive_bangor_v1_stream_state"](
        hmac_key=key,
        input_role="cscont:train_rows.jsonl",
        expected_split="train",
        authorized_records=(valid,),
    )
    decoded = reviewed_globals["_adapt_cscont_record"](
        valid,
        input_role="cscont:train_rows.jsonl",
        input_ordinal=0,
        bangor_state=state,
    )
    state.finalize()
    state.clear()
    assert decoded.source == "bangor_cgwords"
    assert decoded.row_id == valid["record_id"]
    prepared = reviewed_globals["_tokenize_decoded_row"](
        decoded,
        tokenizer,
        key,
    )
    assert prepared.token_ids == (10, 11, 12)
    assert prepared.row_id != decoded.row_id

    malformed = json.loads(json.dumps(valid))
    malformed["row"]["n_word_tokens_excluding_punctuation"] += 1
    malformed_state = reviewed_globals["_derive_bangor_v1_stream_state"](
        hmac_key=key,
        input_role="cscont:train_rows.jsonl",
        expected_split="train",
        authorized_records=(malformed,),
    )
    with pytest.raises(PreparationError) as caught:
        reviewed_globals["_adapt_cscont_record"](
            malformed,
            input_role="cscont:train_rows.jsonl",
            input_ordinal=0,
            bangor_state=malformed_state,
        )
    _assert_exception_private(
        caught.value,
        ("reviewed-bangor", str(frozen_root), str(key_path)),
    )

    first, second = _callhome_cscont_sequence(
        identity="reviewed-order",
        turn_indices=(4, 9),
    )
    with pytest.raises(PreparationError):
        reviewed_globals["_derive_bangor_v1_stream_state"](
            hmac_key=key,
            input_role="cscont:train_rows.jsonl",
            expected_split="train",
            authorized_records=(second, first),
        )


def test_production_lifecycle_static_call_graph_is_explicitly_captured() -> None:
    (
        local_functions,
        local_classes,
        external_functions,
        external_classes,
    ) = (
        _reachable_production_lifecycle_inventory()
    )
    assert local_functions == set(
        preparation_module._PRODUCTION_LIFECYCLE_REVIEWED_LOCAL_FUNCTIONS
    )
    assert local_classes == set(
        preparation_module._PRODUCTION_LIFECYCLE_REVIEWED_LOCAL_CLASSES
    )
    assert external_functions == {
        module: set(names)
        for module, names in (
            preparation_module._PRODUCTION_LIFECYCLE_REVIEWED_EXTERNAL_FUNCTIONS.items()
        )
    }
    assert external_classes == {
        module: set(names)
        for module, names in (
            preparation_module._PRODUCTION_LIFECYCLE_REVIEWED_EXTERNAL_CLASSES.items()
        )
    }
    assert not preparation_module._PRODUCTION_LIFECYCLE_EXTERNAL_CALLABLE_ALLOWLIST

    _, reviewed_prepare, reviewed_globals = _closed_reviewed_ingestion()
    assert reviewed_prepare is not preparation_module._prepare_production_inputs
    assert reviewed_globals is not vars(preparation_module)
    reviewed_external_globals = {
        reviewed_globals[name].__module__: reviewed_globals[name].__globals__
        for name in (
            "audit_exposure",
            "build_validation_mask_record",
            "pack_rows",
            "protocol_configuration",
        )
    }
    for name in local_functions:
        assert reviewed_globals[name] is not getattr(preparation_module, name)
        assert not any(
            parameter.startswith("_reviewed_")
            for parameter in inspect.signature(reviewed_globals[name]).parameters
        )
    for name in local_classes:
        captured = reviewed_globals[name]
        exported = getattr(preparation_module, name)
        if name in preparation_module._PRODUCTION_REVIEWED_ORIGINAL_CLASS_ALLOWLIST:
            assert captured is exported
        else:
            assert captured is not exported
            assert not issubclass(captured, exported)
    for module, names in external_functions.items():
        exported_module = sys.modules[module]
        captured_globals = reviewed_external_globals[module]
        for name in names:
            captured = captured_globals[name]
            exported = getattr(exported_module, name)
            assert captured is not exported
            assert captured.__globals__ is not exported.__globals__
    for module, names in external_classes.items():
        exported_module = sys.modules[module]
        captured_globals = reviewed_external_globals[module]
        for name in names:
            captured = captured_globals[name]
            exported = getattr(exported_module, name)
            if issubclass(exported, BaseException):
                assert captured is exported
            else:
                assert captured is not exported
                assert not issubclass(captured, exported)
    reviewed_snapshot = reviewed_globals["PreparationSnapshot"]
    reviewed_setattr = vars(reviewed_snapshot)["__setattr__"]
    if isinstance(reviewed_setattr, staticmethod):
        reviewed_setattr = reviewed_setattr.__func__
    assert isinstance(reviewed_setattr, FunctionType)
    assert reviewed_snapshot in {
        cell.cell_contents
        for cell in reviewed_setattr.__closure__ or ()
        if isinstance(cell.cell_contents, type)
    }
    reviewed_decoded_eq = vars(reviewed_globals["DecodedPreparationRow"])[
        "__eq__"
    ]
    assert isinstance(reviewed_decoded_eq, FunctionType)
    assert (
        reviewed_decoded_eq.__globals__["lexical_token_count"]
        is reviewed_globals["lexical_token_count"]
    )
    approved_special = reviewed_globals["_APPROVED_SPECIAL_TOKEN_IDS"]
    assert isinstance(approved_special, type(MappingProxyType({})))
    assert dict(approved_special) == {
        "[PAD]": 0,
        "[UNK]": 1,
        "[CLS]": 2,
        "[SEP]": 3,
        "[MASK]": 4,
    }
    assert approved_special is not preparation_module.SPECIAL_TOKEN_IDS
    reviewed_protocol = reviewed_globals["protocol_configuration"]()
    assert reviewed_protocol["special_tokens"] is approved_special
    with pytest.raises(TypeError):
        reviewed_protocol["special_tokens"]["[CLS]"] = 99


@pytest.mark.parametrize(
    "blocked_name",
    (
        "_validate_historical_identity_record",
        "_load_preparation_candidate",
    ),
)
def test_static_lifecycle_audit_rejects_missing_late_dependency(
    blocked_name: str,
) -> None:
    with pytest.raises(
        AssertionError,
        match="reviewed production lifecycle is missing",
    ):
        _reachable_production_lifecycle_inventory(
            blocked_names=frozenset({blocked_name})
        )


def test_clean_first_import_and_reload_have_equivalent_complete_graph(
    tmp_path: Path,
) -> None:
    root = Path(preparation_module.__file__).resolve().parents[3]
    script = r"""
import importlib
import inspect
import json
from pathlib import Path
import cslm.modeling.preparation as preparation

def snapshot(module):
    closed = inspect.getclosurevars(
        module.prepare_and_publish_production
    ).nonlocals
    reviewed_prepare = closed["reviewed_prepare_production_inputs"]
    reviewed_globals = reviewed_prepare.__globals__
    required = {
        "_validate_historical_identity_record",
        "_load_preparation_candidate",
        "collect_runtime_identity",
        "_publish_preparation",
    }
    assert required <= set(reviewed_globals)
    assert all(
        reviewed_globals[name] is not getattr(module, name)
        for name in required
    )
    assert all(
        reviewed_globals[name].__globals__ is reviewed_globals
        for name in required
    )
    unapproved = Path.cwd() / "fresh-import-unapproved"
    paths = module.ProductionPreparationPaths(
        Path.cwd() / "absent-callhome",
        Path.cwd() / "absent-cscont",
        Path.cwd() / "absent-tokenizer",
        Path.cwd() / "absent-key",
    )
    try:
        module.prepare_and_publish_production(paths, unapproved)
    except module.PreparationError as error:
        behavior = str(error)
    else:
        raise AssertionError("unapproved output unexpectedly passed")
    assert not unapproved.exists()
    return {
        "functions": sorted(
            module._PRODUCTION_LIFECYCLE_REVIEWED_LOCAL_FUNCTIONS
        ),
        "classes": sorted(
            module._PRODUCTION_LIFECYCLE_REVIEWED_LOCAL_CLASSES
        ),
        "external_functions": {
            name: sorted(values)
            for name, values in (
                module._PRODUCTION_LIFECYCLE_REVIEWED_EXTERNAL_FUNCTIONS.items()
            )
        },
        "external_classes": {
            name: sorted(values)
            for name, values in (
                module._PRODUCTION_LIFECYCLE_REVIEWED_EXTERNAL_CLASSES.items()
            )
        },
        "behavior": behavior,
        "historical": reviewed_globals[
            "_validate_historical_identity_record"
        ].__qualname__,
        "loader": reviewed_globals[
            "_load_preparation_candidate"
        ].__qualname__,
    }

first = snapshot(preparation)
preparation._validate_historical_identity_record = lambda *args: None
preparation._load_preparation_candidate = lambda *args, **kwargs: None
reloaded = importlib.reload(preparation)
second = snapshot(reloaded)
assert first == second
print(json.dumps({"first": first, "second": second}, sort_keys=True))
"""
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONPATH"] = os.pathsep.join(
        (str(root), str(root / "src"))
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["first"] == payload["second"]
    assert (
        payload["first"]["behavior"]
        == "production output root is not the approved private root"
    )
    assert not (tmp_path / "fresh-import-unapproved").exists()


def test_reviewed_publisher_resolves_late_runtime_and_loader_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, reviewed_globals = _closed_reviewed_ingestion()
    reviewed_publisher = reviewed_globals["_publish_preparation"]
    reviewed_runtime = reviewed_globals["collect_runtime_identity"]
    reviewed_historical = reviewed_globals[
        "_validate_historical_identity_record"
    ]
    reviewed_loader = reviewed_globals["_load_preparation_candidate"]

    assert reviewed_publisher.__globals__ is reviewed_globals
    assert reviewed_publisher.__globals__["collect_runtime_identity"] is reviewed_runtime
    assert (
        reviewed_runtime.__globals__["_validate_historical_identity_record"]
        is reviewed_historical
    )
    assert (
        reviewed_publisher.__globals__["_load_preparation_candidate"]
        is reviewed_loader
    )
    assert "_load_preparation_candidate" in _nested_global_names(
        reviewed_publisher.__code__
    )

    bundle = object.__new__(reviewed_globals["PreparationBundle"])
    object.__setattr__(
        bundle,
        "protocol_version",
        preparation_module.PREPARATION_PROTOCOL_VERSION,
    )
    object.__setattr__(bundle, "tokenizer_historical_build_identity", {})
    object.__setattr__(bundle, "input_anchor", None)
    monkeypatch.setenv("PYTHONHASHSEED", "1729")
    monkeypatch.setenv("TOKENIZERS_PARALLELISM", "false")
    with pytest.raises(
        PreparationError,
        match="historical tokenizer-build identity is not anchored",
    ):
        reviewed_runtime(bundle=bundle)


def _private_synthetic_input_anchor(
    reviewed_globals: dict[str, object],
) -> object:
    records = (
        (
            "callhome",
            reviewed_globals["APPROVED_CALLHOME_CHECKSUM_RECORD_SHA256"],
        ),
        (
            "cscont",
            reviewed_globals["APPROVED_CSCONT_CHECKSUM_RECORD_SHA256"],
        ),
        (
            "tokenizer",
            reviewed_globals["APPROVED_TOKENIZER_CHECKSUM_RECORD_SHA256"],
        ),
    )
    constituent = (("tokenizer:training_manifest.json", "a" * 64),)
    input_counts = (("synthetic-equivalent", 1),)
    authorized_counts = (("synthetic-equivalent", 1),)
    test_counts = (("synthetic-equivalent", 0),)
    payload = {
        "authorized_line_counts": dict(authorized_counts),
        "checksum_record_identities": dict(records),
        "constituent_sha256": dict(constituent),
        "input_line_counts": dict(input_counts),
        "sealed_test_line_counts": dict(test_counts),
    }
    anchor = object.__new__(reviewed_globals["InputPopulationAnchor"])
    for name, value in {
        "checksum_record_identities": records,
        "constituent_sha256": constituent,
        "input_line_counts": input_counts,
        "authorized_line_counts": authorized_counts,
        "sealed_test_line_counts": test_counts,
        "identity_sha256": sha256(_test_canonical_json(payload)).hexdigest(),
    }.items():
        object.__setattr__(anchor, name, value)
    anchor._validate()
    return anchor


def _write_private_synthetic_tree(
    root: Path,
    files: dict[str, bytes],
) -> None:
    root.mkdir()
    os.chmod(root, 0o700)
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        for parent in (path.parent, *path.parent.parents):
            if parent == root.parent:
                break
            os.chmod(parent, 0o700)
        path.write_bytes(content)
        os.chmod(path, 0o600)


def test_reviewed_serialization_and_staged_readback_reach_candidate_loader(
    tmp_path: Path,
) -> None:
    fixture = build_synthetic_preparation_fixture(tmp_path / "source")
    _, _, reviewed_globals = _closed_reviewed_ingestion()
    anchor = _private_synthetic_input_anchor(reviewed_globals)
    bundle_values = dict(vars(fixture.bundle))
    bundle_values.update(
        {
            "input_anchor": anchor,
            "protocol_version": preparation_module.PREPARATION_PROTOCOL_VERSION,
            "tokenizer_historical_build_identity": {},
        }
    )
    bundle = SimpleNamespace(**bundle_values)
    runtime = {
        "synthetic_equivalent": True,
        "scientifically_authoritative": False,
    }
    files, validation_records = reviewed_globals["_artifact_files"](
        bundle,
        hmac_key=fixture.hmac_key,
        runtime_identity=runtime,
    )
    manifest = reviewed_globals["_derive_preparation_manifest"](
        bundle,
        runtime_identity=runtime,
        serialized_validation_records=validation_records,
    )
    manifest_payload = dict(manifest.payload)
    manifest_payload["preparation_manifest_identity_sha256"] = (
        manifest.identity_sha256
    )
    checksummed = {
        **files,
        "PREPARATION_MANIFEST.json": _test_canonical_json(manifest_payload),
    }
    inventory = set(checksummed) | {
        "checksums.json",
        "CANDIDATE_COMPLETE.json",
    }
    checksum_record, checksum_bytes = reviewed_globals[
        "_derive_candidate_checksum_record"
    ](
        checksummed,
        inventory=inventory,
        protocol_version=preparation_module.PREPARATION_PROTOCOL_VERSION,
    )
    all_files = {
        **checksummed,
        "checksums.json": checksum_bytes,
        "CANDIDATE_COMPLETE.json": _test_canonical_json(
            {
                "candidate_checksum_record_sha256": (
                    checksum_record.identity_sha256
                ),
                "complete": True,
                "protocol_version": (
                    preparation_module.PREPARATION_PROTOCOL_VERSION
                ),
                "status": "candidate_unapproved",
            }
        ),
    }
    root = tmp_path / "synthetic-readback-equivalent"
    _write_private_synthetic_tree(root, all_files)
    assert sha256((root / "checksums.json").read_bytes()).hexdigest() == (
        checksum_record.identity_sha256
    )
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        with pytest.raises(PreparationError) as caught:
            reviewed_globals["_load_preparation_candidate"](
                Path(),
                reconciliation_key=fixture.hmac_key,
                root_descriptor=descriptor,
            )
    finally:
        os.close(descriptor)
    assert not isinstance(caught.value, NameError)
    _assert_exception_private(
        caught.value,
        ("synthetic-readback-equivalent", str(root)),
    )
    assert not any(
        isinstance(value, PreparationSnapshot)
        for value in vars(caught.value).values()
    )
    assert not (tmp_path / "candidate").exists()
    assert not list(tmp_path.glob(".*staging*"))


def _tokenizer_payload(
    *,
    token: str | None = None,
    replacement_id: int | None = None,
) -> dict[str, object]:
    special = {
        "[PAD]": 0,
        "[UNK]": 1,
        "[CLS]": 2,
        "[SEP]": 3,
        "[MASK]": 4,
    }
    if token is not None:
        assert replacement_id is not None
        special[token] = replacement_id
    vocabulary = dict(special)
    vocabulary.update(
        {f"synthetic_{index}": index for index in range(5, 8_000)}
    )
    return {
        "normalizer": {
            "type": "Sequence",
            "normalizers": [
                {"type": "NFC"},
                {
                    "type": "BertNormalizer",
                    "clean_text": True,
                    "handle_chinese_chars": False,
                    "strip_accents": False,
                    "lowercase": True,
                },
            ],
        },
        "pre_tokenizer": {"type": "BertPreTokenizer"},
        "model": {
            "type": "WordPiece",
            "unk_token": "[UNK]",
            "continuing_subword_prefix": "##",
            "vocab": vocabulary,
        },
    }


@pytest.mark.parametrize(
    ("token", "replacement_id"),
    (
        ("[PAD]", 95),
        ("[UNK]", 96),
        ("[CLS]", 97),
        ("[SEP]", 98),
        ("[MASK]", 99),
    ),
)
@pytest.mark.parametrize(
    "mutation",
    (
        "preparation-replacement",
        "shared-in-place",
        "shared-replacement",
        "returned-configuration",
        "protocol-aliases",
    ),
)
def test_reviewed_special_token_authority_rejects_public_mutation(
    monkeypatch: pytest.MonkeyPatch,
    token: str,
    replacement_id: int,
    mutation: str,
) -> None:
    _, _, reviewed_globals = _closed_reviewed_ingestion()
    wrong = {
        "[PAD]": 0,
        "[UNK]": 1,
        "[CLS]": 2,
        "[SEP]": 3,
        "[MASK]": 4,
    }
    wrong[token] = replacement_id
    with monkeypatch.context() as patch:
        if mutation == "preparation-replacement":
            patch.setattr(preparation_module, "SPECIAL_TOKEN_IDS", wrong)
        elif mutation == "shared-in-place":
            patch.setitem(
                shared_wordpiece_module.SPECIAL_TOKEN_IDS,
                token,
                replacement_id,
            )
        elif mutation == "shared-replacement":
            patch.setattr(
                shared_wordpiece_module,
                "SPECIAL_TOKEN_IDS",
                wrong,
            )
        elif mutation == "returned-configuration":
            returned = shared_wordpiece_module.protocol_configuration()
            patch.setitem(returned["special_tokens"], token, replacement_id)
        else:
            patch.setattr(
                preparation_module,
                "protocol_configuration",
                lambda: {"special_tokens": wrong},
            )
            patch.setattr(
                shared_wordpiece_module,
                "protocol_configuration",
                lambda: {"special_tokens": wrong},
            )
        with pytest.raises(PreparationError):
            reviewed_globals["_validate_tokenizer_json"](
                _tokenizer_payload(
                    token=token,
                    replacement_id=replacement_id,
                )
            )
        reviewed_configuration = reviewed_globals[
            "protocol_configuration"
        ]()
        assert dict(reviewed_configuration["special_tokens"]) == {
            "[PAD]": 0,
            "[UNK]": 1,
            "[CLS]": 2,
            "[SEP]": 3,
            "[MASK]": 4,
        }
        with pytest.raises(TypeError):
            reviewed_configuration["special_tokens"][token] = replacement_id


_OPERATIONALLY_PROBED_PRODUCTION_GLOBALS = (
    "_prepare_production_inputs",
    "_verify_frozen_root",
    "_snapshot_relative_jsonl_lines",
    "_iter_bounded_descriptor_lines",
    "load_hmac_key",
    "_load_hmac_key",
    "_unique_object",
    "_decode_cscont_line",
    "_default_authorized_decoder",
    "scan_sealed_callhome_split",
    "_adapt_callhome_record",
    "_stream_binding",
    "_stream_record_binding",
    "_derive_cscont_stream_order_impl",
    "_derive_cscont_stream_order",
    "_derive_bangor_v1_stream_state",
    "_BangorV1StreamState",
    "_validate_and_project_bangor_v1_row",
    "_derive_decoded_row",
    "_adapt_cscont_record_impl",
    "_adapt_cscont_record",
    "_tokenize_decoded_row",
)


@pytest.mark.parametrize("binding", _OPERATIONALLY_PROBED_PRODUCTION_GLOBALS)
def test_each_production_global_replacement_is_ineffective(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    binding: str,
) -> None:
    _, reviewed_prepare, reviewed_globals = _closed_reviewed_ingestion()
    calls: list[str] = []

    def permissive_fake(*args: object, **kwargs: object) -> object:
        del args, kwargs
        calls.append(binding)
        return SimpleNamespace(token_ids=(999_999,))

    class PermissiveState:
        pass

    line = _line(_callhome(identity=f"frozen-{binding}"))
    frozen_root, checksum_identity = _write_reviewed_frozen_root(
        tmp_path / "frozen",
        line=line,
    )
    key_path = _write_privacy_reconciliation_key(tmp_path / "key")
    tokenizer = make_synthetic_exact_tokenizer(_SyntheticBackend())
    replacement: object = (
        PermissiveState if binding == "_BangorV1StreamState" else permissive_fake
    )
    monkeypatch.setattr(preparation_module, binding, replacement)

    assert reviewed_globals[binding] is not replacement
    _exercise_reviewed_ingestion_components(
        reviewed_globals=reviewed_globals,
        frozen_root=frozen_root,
        checksum_identity=checksum_identity,
        expected_line=line,
        key_path=key_path,
        tokenizer=tokenizer,
    )
    assert reviewed_prepare is not preparation_module._prepare_production_inputs
    assert calls == []


def test_every_reviewed_application_global_is_disconnected_one_at_a_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, _, reviewed_globals = _closed_reviewed_ingestion()
    external_roots = {
        "cslm.modeling.exposure": "audit_exposure",
        "cslm.modeling.masking": "build_validation_mask_record",
        "cslm.modeling.packing": "pack_rows",
        "cslm.tokenization.shared_wordpiece": "protocol_configuration",
    }

    def permissive_fake(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise AssertionError("permissive replacement was invoked")

    class PermissiveType:
        pass

    for name in preparation_module._PRODUCTION_LIFECYCLE_REVIEWED_LOCAL_FUNCTIONS:
        captured = reviewed_globals[name]
        with monkeypatch.context() as patch:
            patch.setattr(preparation_module, name, permissive_fake)
            assert reviewed_globals[name] is captured
    for name in preparation_module._PRODUCTION_LIFECYCLE_REVIEWED_LOCAL_CLASSES:
        captured = reviewed_globals[name]
        with monkeypatch.context() as patch:
            patch.setattr(preparation_module, name, PermissiveType)
            assert reviewed_globals[name] is captured
    for module, names in (
        preparation_module._PRODUCTION_LIFECYCLE_REVIEWED_EXTERNAL_FUNCTIONS.items()
    ):
        exported_module = sys.modules[module]
        captured_globals = reviewed_globals[
            external_roots[module]
        ].__globals__
        for name in names:
            captured = captured_globals[name]
            with monkeypatch.context() as patch:
                patch.setattr(exported_module, name, permissive_fake)
                assert captured_globals[name] is captured
    for module, names in (
        preparation_module._PRODUCTION_LIFECYCLE_REVIEWED_EXTERNAL_CLASSES.items()
    ):
        exported_module = sys.modules[module]
        captured_globals = reviewed_globals[
            external_roots[module]
        ].__globals__
        for name in names:
            captured = captured_globals[name]
            with monkeypatch.context() as patch:
                patch.setattr(exported_module, name, PermissiveType)
                assert captured_globals[name] is captured


def test_combined_production_global_replacement_cannot_cross_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, reviewed_prepare, reviewed_globals = _closed_reviewed_ingestion()
    calls: list[str] = []

    def permissive_fake(*args: object, **kwargs: object) -> object:
        del args, kwargs
        calls.append("permissive")
        return SimpleNamespace(token_ids=(999_999,))

    class PermissiveType:
        pass

    line = _line(_callhome(identity="frozen-combined"))
    frozen_root, checksum_identity = _write_reviewed_frozen_root(
        tmp_path / "frozen",
        line=line,
    )
    key_path = _write_privacy_reconciliation_key(tmp_path / "key")
    tokenizer = make_synthetic_exact_tokenizer(_SyntheticBackend())
    paths = ProductionPreparationPaths(
        tmp_path / "absent-callhome",
        tmp_path / "absent-cscont",
        tmp_path / "absent-tokenizer",
        tmp_path / "absent-key",
    )
    for name in preparation_module._PRODUCTION_LIFECYCLE_REVIEWED_LOCAL_FUNCTIONS:
        monkeypatch.setattr(preparation_module, name, permissive_fake)
    for name in preparation_module._PRODUCTION_LIFECYCLE_REVIEWED_LOCAL_CLASSES:
        monkeypatch.setattr(preparation_module, name, PermissiveType)
    for name in (
        "PackingRow",
        "audit_exposure",
        "build_validation_mask_record",
        "mask_packed_sequence",
        "pack_rows",
        "protocol_configuration",
    ):
        monkeypatch.setattr(preparation_module, name, permissive_fake)
    for module, names in (
        preparation_module._PRODUCTION_LIFECYCLE_REVIEWED_EXTERNAL_FUNCTIONS.items()
    ):
        for name in names:
            monkeypatch.setattr(sys.modules[module], name, permissive_fake)
    for module, names in (
        preparation_module._PRODUCTION_LIFECYCLE_REVIEWED_EXTERNAL_CLASSES.items()
    ):
        for name in names:
            monkeypatch.setattr(sys.modules[module], name, PermissiveType)

    _exercise_reviewed_ingestion_components(
        reviewed_globals=reviewed_globals,
        frozen_root=frozen_root,
        checksum_identity=checksum_identity,
        expected_line=line,
        key_path=key_path,
        tokenizer=tokenizer,
    )
    monkeypatch.setenv("PYTHONHASHSEED", "1729")
    monkeypatch.setenv("TOKENIZERS_PARALLELISM", "false")
    with pytest.raises(PreparationError, match="closed production"):
        prepare_and_publish_production(
            paths,
            APPROVED_PRIVATE_OUTPUT_ROOT.expanduser(),
        )
    assert reviewed_prepare is not preparation_module._prepare_production_inputs
    assert calls == []


def test_active_process_runtime_controls_are_recorded_exactly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYTHONHASHSEED", "1729")
    monkeypatch.setenv("TOKENIZERS_PARALLELISM", "false")
    controls = preparation_module._actual_runtime_environment_controls()
    assert dict(controls) == {
        "PYTHONHASHSEED": "1729",
        "TOKENIZERS_PARALLELISM": "false",
    }
    assert set(inspect.signature(preparation_module.collect_runtime_identity).parameters) == {
        "bundle"
    }
    collection_source = inspect.getsource(preparation_module.collect_runtime_identity)
    assert "_actual_runtime_environment_controls()" in collection_source
    assert '"environment_controls": dict(environment_controls)' in collection_source
    publication_source = inspect.getsource(preparation_module._publish_preparation)
    assert publication_source.count("_actual_runtime_environment_controls()") == 1
    assert "changed during preparation" in publication_source


def test_closed_production_environment_capture_reads_live_process_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed_values, reviewed_prepare, reviewed_globals = (
        _closed_reviewed_ingestion()
    )
    reviewed_environment = closed_values[
        "reviewed_runtime_environment_controls"
    ]
    reviewed_publish = closed_values["reviewed_publish_preparation"]
    calls: list[str] = []

    def permissive_environment() -> dict[str, str]:
        calls.append("permissive")
        return {
            "PYTHONHASHSEED": "caller-selected",
            "TOKENIZERS_PARALLELISM": "caller-selected",
        }

    monkeypatch.setattr(
        preparation_module,
        "_actual_runtime_environment_controls",
        permissive_environment,
    )
    monkeypatch.setattr(
        preparation_module,
        "os",
        SimpleNamespace(
            environ={
                "PYTHONHASHSEED": "caller-selected",
                "TOKENIZERS_PARALLELISM": "caller-selected",
            }
        ),
    )
    monkeypatch.setenv("PYTHONHASHSEED", "1729")
    monkeypatch.setenv("TOKENIZERS_PARALLELISM", "false")
    first = reviewed_environment()
    monkeypatch.setenv("TOKENIZERS_PARALLELISM", "FALSE")
    second = reviewed_environment()

    assert dict(first)["PYTHONHASHSEED"] == "1729"
    assert dict(second)["PYTHONHASHSEED"] == "1729"
    assert dict(second)["TOKENIZERS_PARALLELISM"] == "FALSE"
    assert calls == []
    assert reviewed_environment is reviewed_globals[
        "_actual_runtime_environment_controls"
    ]
    assert reviewed_publish.__globals__ is reviewed_prepare.__globals__
    assert reviewed_environment.__globals__["os"] is os
    assert set(inspect.signature(prepare_and_publish_production).parameters) == {
        "paths",
        "output_root",
    }


def test_public_reader_traceback_retains_no_secret_record_material(
    tmp_path: Path,
) -> None:
    marker = "PUBLIC-READER-PRIVATE-MARKER"
    path = tmp_path / "synthetic-private.jsonl"
    path.write_bytes(
        b'{"conversation_ref":"private-identifier","row_id":"r",'
        b'"source":"callhome_eng","speaker_ref":"s","split":"train","text":"'
        + marker.encode()
        + b'-\xff","turn_index":0}\n'
    )
    os.chmod(path, 0o600)
    descriptor_count = _open_descriptor_count()
    reader = read_sealed_callhome_jsonl(path)
    with pytest.raises(PreparationError) as caught:
        tuple(reader)
    _assert_exception_private(
        caught.value,
        (marker, "private-identifier", "\\xff", str(path)),
    )
    assert reader.gi_frame is None
    assert _open_descriptor_count() == descriptor_count


def test_public_reader_retains_only_the_current_authorized_record(
    tmp_path: Path,
) -> None:
    first_marker = "CURRENT-AUTHORIZED-MARKER"
    later_marker = "LATER-AUTHORIZED-MARKER"
    path = tmp_path / "streamed.jsonl"
    path.write_bytes(
        _line(_callhome(text=first_marker, identity="first"))
        + _line(_callhome(text=later_marker, identity="second"))
    )
    os.chmod(path, 0o600)
    descriptor_count = _open_descriptor_count()
    reader = read_sealed_callhome_jsonl(path)
    first = next(reader)
    assert first["text"] == first_marker
    assert reader.gi_frame is not None
    assert later_marker not in repr(reader.gi_frame.f_locals)
    reader.close()
    assert reader.gi_frame is None
    assert _open_descriptor_count() == descriptor_count


@pytest.mark.parametrize("invalid_index", [4, 5])
def test_monocont_must_be_exact_subset_of_language_baseline(
    invalid_index: int,
) -> None:
    valid = synthetic_population()
    _validate_cross_condition_reuse(valid)
    material = list(valid)
    row = material[invalid_index]
    source = row.source
    material[invalid_index] = adapt_callhome_record(
        _callhome(
            source=source,
            split=row.split,
            identity=f"same-total-substitution-{invalid_index}",
        ),
        logical_condition="MonoCont",
    )
    with pytest.raises(PreparationError, match="monolingual-baseline subset"):
        _validate_cross_condition_reuse(material)


@pytest.mark.parametrize(
    "mutation",
    [
        "conversation",
        "row_order",
        "lexical_count",
        "token_identity",
        "cross_source_equal_id",
    ],
)
def test_monocont_subset_checks_exact_row_semantics(mutation: str) -> None:
    material = list(synthetic_population())
    original = material[4]
    record = _callhome(
        source="callhome_eng",
        split="train",
        identity="shared-english-train",
    )
    if mutation == "conversation":
        record["conversation_ref"] = "wrong-conversation"
    elif mutation == "row_order":
        record["turn_index"] = 1
    elif mutation == "lexical_count":
        record["text"] = "one two three four"
    elif mutation == "token_identity":
        record["text"] = "red tan seven"
    else:
        record["source"] = "callhome_spa"
        record["conversation_ref"] = "conversation-shared-spanish-train"
    record["row_id"] = original.row_id
    material[4] = adapt_callhome_record(
        record,
        logical_condition="MonoCont",
    )
    with pytest.raises(PreparationError, match="monolingual-baseline subset"):
        _validate_cross_condition_reuse(material)


@pytest.mark.parametrize("source", ["callhome_eng", "callhome_spa"])
def test_serialized_monocont_subset_rejects_same_total_substitution(
    tmp_path: Path,
    source: str,
) -> None:
    fixture = build_synthetic_preparation_fixture(tmp_path)
    membership_path = (
        fixture.output_root / "synthetic-artifacts/membership.json"
    )
    membership = json.loads(membership_path.read_bytes())
    target = next(
        row
        for row in membership
        if row["condition"] == "MonoCont" and row["source_role"] == source
    )
    target["row_content_binding_hmac_sha256"] = "f" * 64
    membership_path.write_bytes(canonical_json_bytes(membership))
    os.chmod(membership_path, 0o600)
    _rewrite_synthetic_outer_identities(fixture.output_root)
    with pytest.raises(PreparationError):
        load_synthetic_preparation_candidate(fixture.output_root)


def test_serialized_cscont_filler_subset_rejects_rebinding(
    tmp_path: Path,
) -> None:
    fixture = build_synthetic_preparation_fixture(tmp_path)
    membership_path = (
        fixture.output_root / "synthetic-artifacts/membership.json"
    )
    membership = json.loads(membership_path.read_bytes())
    target = next(
        row
        for row in membership
        if row["condition"] == "CsCont"
        and row["source_role"] == "callhome_eng"
    )
    target["row_content_binding_hmac_sha256"] = "f" * 64
    membership_path.write_bytes(canonical_json_bytes(membership))
    os.chmod(membership_path, 0o600)
    _rewrite_synthetic_outer_identities(fixture.output_root)
    with pytest.raises(PreparationError):
        load_synthetic_preparation_candidate(fixture.output_root)


def test_changed_validation_label_rejected_after_outer_rehash(
    tmp_path: Path,
) -> None:
    fixture = build_synthetic_preparation_fixture(tmp_path)
    labels_path = (
        fixture.output_root
        / "synthetic-artifacts/validation/EnglishMono/tiny_smoke_1/labels.npy"
    )
    with labels_path.open("rb") as handle:
        labels = np.load(handle, allow_pickle=False)
    labels[0, 0] = 5 if labels[0, 0] != 5 else 6
    with labels_path.open("wb") as handle:
        np.save(handle, labels, allow_pickle=False)
    os.chmod(labels_path, 0o600)
    _rewrite_synthetic_outer_identities(fixture.output_root)
    with pytest.raises(PreparationError, match="not regenerated"):
        load_synthetic_preparation_candidate(fixture.output_root)


@pytest.mark.parametrize(
    "mutation",
    [
        "masked_input",
        "attention",
        "token_types",
        "identity",
        "ordering",
        "seed",
        "policy",
        "condition",
    ],
)
def test_every_persisted_validation_checksum_input_is_revalidated(
    tmp_path: Path,
    mutation: str,
) -> None:
    fixture = build_synthetic_preparation_fixture(tmp_path)
    prefix = (
        fixture.output_root
        / "synthetic-artifacts/validation/EnglishMono/tiny_smoke_1"
    )
    if mutation in {"masked_input", "attention", "token_types"}:
        filename = {
            "masked_input": "masked_input_ids.npy",
            "attention": "attention_mask.npy",
            "token_types": "token_type_ids.npy",
        }[mutation]
        path = prefix / filename
        with path.open("rb") as handle:
            array = np.load(handle, allow_pickle=False)
        array[0, 0] = 0 if array[0, 0] else 1
        with path.open("wb") as handle:
            np.save(handle, array, allow_pickle=False)
        os.chmod(path, 0o600)
    elif mutation == "identity":
        path = prefix / "example_identities.json"
        payload = json.loads(path.read_bytes())
        payload["ordered_example_identities"][0] = "e" * 64
        path.write_bytes(canonical_json_bytes(payload))
        os.chmod(path, 0o600)
    elif mutation == "ordering":
        path = prefix / "example_identities.json"
        payload = json.loads(path.read_bytes())
        original = payload["ordered_example_identities"][0]
        payload["ordered_example_identities"] = ["f" * 64, original]
        path.write_bytes(canonical_json_bytes(payload))
        os.chmod(path, 0o600)
    else:
        path = prefix / "validation_mask_record.json"
        payload = json.loads(path.read_bytes())
        if mutation == "seed":
            payload["seed"] += 1
        elif mutation == "policy":
            payload["policy_sha256"] = "d" * 64
        else:
            payload["condition"] = "SpanishMono"
        path.write_bytes(canonical_json_bytes(payload))
        os.chmod(path, 0o600)
    _rewrite_synthetic_outer_identities(fixture.output_root)
    with pytest.raises(PreparationError):
        load_synthetic_preparation_candidate(fixture.output_root)


def test_validation_is_regenerated_without_a_caller_result_checksum() -> None:
    assert not hasattr(
        preparation_module,
        "_derive_serialized_validation_record",
    )
    source = inspect.getsource(preparation_module._regenerate_fixed_validation)
    assert "mask_packed_sequence" in source
    assert "build_validation_mask_record" in source


def test_validation_regeneration_binds_exact_example_order() -> None:
    inputs = np.zeros((2, 128), dtype=np.uint16)
    inputs[:, :5] = np.asarray([2, 5, 6, 7, 3], dtype=np.uint16)
    attention = np.zeros((2, 128), dtype=np.uint8)
    attention[:, :5] = 1
    token_types = np.zeros((2, 128), dtype=np.uint8)
    identities = ("a" * 64, "b" * 64)
    baseline = preparation_module._regenerate_fixed_validation(
        condition="EnglishMono",
        seed=approved_validation_seed_plans()[0][1],
        ordered_example_identities=identities,
        unmasked_input_ids=inputs,
        attention_mask=attention,
        token_type_ids=token_types,
    )
    reordered = preparation_module._regenerate_fixed_validation(
        condition="EnglishMono",
        seed=approved_validation_seed_plans()[0][1],
        ordered_example_identities=tuple(reversed(identities)),
        unmasked_input_ids=inputs,
        attention_mask=attention,
        token_type_ids=token_types,
    )
    assert reordered[2].checksum_sha256 != baseline[2].checksum_sha256


@pytest.mark.parametrize("git_marker_kind", ["directory", "file"])
def test_output_git_exclusion_is_independent_of_caller_claims(
    tmp_path: Path,
    git_marker_kind: str,
) -> None:
    repository = tmp_path / "different-repository"
    repository.mkdir()
    os.chmod(repository, 0o700)
    marker = repository / ".git"
    if git_marker_kind == "directory":
        marker.mkdir()
    else:
        marker.write_text("gitdir: ../metadata\n", encoding="utf-8")
    key = tmp_path / "separate.key"
    key.write_bytes(b"k" * 32)
    os.chmod(key, 0o600)
    with pytest.raises(PreparationError, match="outside the Git repository"):
        validate_publication_paths(
            repository / "private-output",
            input_roots=(),
            hmac_key_path=key,
        )
    with pytest.raises(TypeError):
        validate_publication_paths(
            repository / "private-output",
            repository_root=tmp_path / "false-claim",
            input_roots=(),
            hmac_key_path=key,
        )


def test_stable_parent_normal_synthetic_publication(tmp_path: Path) -> None:
    fixture = build_synthetic_preparation_fixture(tmp_path)
    fixture.snapshot._validate()
    assert fixture.published.output_root == fixture.output_root
    assert stat.S_IMODE(fixture.output_root.stat().st_mode) == 0o700


def test_candidate_completion_marker_is_written_last(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = build_synthetic_preparation_fixture(tmp_path / "source")
    parent = tmp_path / "attempt"
    parent.mkdir()
    os.chmod(parent, 0o700)
    written: list[str] = []
    original = preparation_module._write_private_file_at

    def record_write(descriptor: int, name: str, content: bytes) -> None:
        written.append(name)
        original(descriptor, name, content)

    monkeypatch.setattr(
        preparation_module,
        "_write_private_file_at",
        record_write,
    )
    preparation_module.publish_synthetic_preparation(
        fixture.bundle,
        output_root=parent / "candidate",
        hmac_key=fixture.hmac_key,
    )
    assert written[-1] == "SYNTHETIC-COMPLETE.json"


def test_parent_rename_and_symlink_replacement_cannot_redirect_commit(
    tmp_path: Path,
) -> None:
    base = tmp_path / "base"
    moved = tmp_path / "moved"

    def replace_parent(stage: str) -> None:
        if stage == "before_commit":
            base.rename(moved)
            base.symlink_to(moved, target_is_directory=True)

    with pytest.raises(PreparationError):
        build_synthetic_preparation_fixture(
            base,
            synthetic_test_hook=replace_parent,
        )
    assert not (moved / "synthetic-candidate").exists()
    assert not list(moved.glob(".synthetic-candidate.synthetic-staging-*"))


def test_target_appearance_remains_atomic_no_overwrite(tmp_path: Path) -> None:
    target = tmp_path / "synthetic-candidate"

    def appear(stage: str) -> None:
        if stage == "before_commit":
            target.mkdir()
            os.chmod(target, 0o700)

    with pytest.raises(PreparationError):
        build_synthetic_preparation_fixture(
            tmp_path,
            synthetic_test_hook=appear,
        )
    assert target.is_dir()
    assert not (target / "SYNTHETIC-COMPLETE.json").exists()


def test_atomic_publication_fails_closed_on_unsupported_platform(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    descriptor = os.open(tmp_path, os.O_RDONLY)
    try:
        monkeypatch.setattr(preparation_module.sys, "platform", "unsupported")
        with pytest.raises(PreparationError, match="unavailable"):
            preparation_module._atomic_rename_noreplace_at(
                descriptor,
                "source",
                "target",
            )
    finally:
        os.close(descriptor)


def test_publication_committed_error_forbids_retry_and_is_revalidatable(
    tmp_path: Path,
) -> None:
    def fail_parent_fsync(stage: str) -> None:
        if stage == "after_commit_before_parent_fsync":
            raise OSError("synthetic parent fsync failure")

    with pytest.raises(PublicationCommittedError) as caught:
        build_synthetic_preparation_fixture(
            tmp_path,
            synthetic_test_hook=fail_parent_fsync,
        )
    assert caught.value.committed is True
    assert caught.value.retry_forbidden is True
    load_synthetic_preparation_candidate(tmp_path / "synthetic-candidate")


def test_atomic_rename_success_then_exception_is_reported_committed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_rename = preparation_module._atomic_rename_noreplace_at

    def rename_then_raise(
        parent_descriptor: int,
        source_name: str,
        target_name: str,
    ) -> None:
        real_rename(parent_descriptor, source_name, target_name)
        raise OSError("injected exception after successful atomic rename")

    monkeypatch.setattr(
        preparation_module,
        "_atomic_rename_noreplace_at",
        rename_then_raise,
    )
    with pytest.raises(PublicationCommittedError) as caught:
        build_synthetic_preparation_fixture(tmp_path)
    assert caught.value.committed is True
    assert caught.value.retry_forbidden is True
    target = tmp_path / "synthetic-candidate"
    assert (target / "SYNTHETIC-COMPLETE.json").is_file()
    assert not list(tmp_path.glob(".synthetic-candidate.synthetic-staging-*"))
    load_synthetic_preparation_candidate(target)


def _install_final_close_probe(
    monkeypatch: pytest.MonkeyPatch,
    *,
    output_root: Path,
    fail_stage: bool,
    fail_parent: bool,
) -> dict[str, object]:
    real_open = preparation_module.os.open
    real_close = preparation_module.os.close
    real_pin = preparation_module._pin_publication_parent
    state: dict[str, object] = {
        "stage_descriptor": None,
        "parent_descriptor": None,
        "attempts": [],
    }
    stage_prefix = f".{output_root.name}.synthetic-staging-"

    def record_open(path, flags, *args, **kwargs):
        descriptor = real_open(path, flags, *args, **kwargs)
        if (
            state["stage_descriptor"] is None
            and isinstance(path, str)
            and path.startswith(stage_prefix)
        ):
            state["stage_descriptor"] = descriptor
        return descriptor

    def record_pin(*args, **kwargs):
        pinned = real_pin(*args, **kwargs)
        state["parent_descriptor"] = pinned.descriptor
        return pinned

    def close_and_optionally_raise(descriptor: int) -> None:
        attempts = state["attempts"]
        assert isinstance(attempts, list)
        label = None
        if (
            descriptor == state["stage_descriptor"]
            and "stage" not in attempts
        ):
            label = "stage"
        elif (
            descriptor == state["parent_descriptor"]
            and "parent" not in attempts
        ):
            label = "parent"
        real_close(descriptor)
        if label is not None:
            attempts.append(label)
            if (label == "stage" and fail_stage) or (
                label == "parent" and fail_parent
            ):
                raise OSError(f"injected final {label} close failure")

    monkeypatch.setattr(preparation_module.os, "open", record_open)
    monkeypatch.setattr(preparation_module.os, "close", close_and_optionally_raise)
    monkeypatch.setattr(preparation_module, "_pin_publication_parent", record_pin)
    return state


def _assert_final_close_attempts(state: dict[str, object]) -> None:
    assert state["stage_descriptor"] is not None
    assert state["parent_descriptor"] is not None
    assert state["attempts"] == ["stage", "parent"]


def test_committed_stage_close_failure_preserves_commit_and_attempts_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = build_synthetic_preparation_fixture(tmp_path / "source")
    parent = tmp_path / "attempt"
    parent.mkdir()
    os.chmod(parent, 0o700)
    target = parent / "candidate"
    state = _install_final_close_probe(
        monkeypatch,
        output_root=target,
        fail_stage=True,
        fail_parent=False,
    )
    with pytest.raises(PublicationCommittedError) as caught:
        preparation_module.publish_synthetic_preparation(
            fixture.bundle,
            output_root=target,
            hmac_key=fixture.hmac_key,
        )
    assert caught.value.committed is True
    assert caught.value.retry_forbidden is True
    _assert_final_close_attempts(state)
    assert (target / "SYNTHETIC-COMPLETE.json").is_file()
    load_synthetic_preparation_candidate(target)


def test_committed_parent_close_failure_preserves_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = build_synthetic_preparation_fixture(tmp_path / "source")
    parent = tmp_path / "attempt"
    parent.mkdir()
    os.chmod(parent, 0o700)
    target = parent / "candidate"
    state = _install_final_close_probe(
        monkeypatch,
        output_root=target,
        fail_stage=False,
        fail_parent=True,
    )
    with pytest.raises(PublicationCommittedError) as caught:
        preparation_module.publish_synthetic_preparation(
            fixture.bundle,
            output_root=target,
            hmac_key=fixture.hmac_key,
        )
    assert caught.value.committed is True
    assert caught.value.retry_forbidden is True
    _assert_final_close_attempts(state)
    load_synthetic_preparation_candidate(target)


def test_both_committed_final_close_failures_are_collected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = build_synthetic_preparation_fixture(tmp_path / "source")
    parent = tmp_path / "attempt"
    parent.mkdir()
    os.chmod(parent, 0o700)
    target = parent / "candidate"
    state = _install_final_close_probe(
        monkeypatch,
        output_root=target,
        fail_stage=True,
        fail_parent=True,
    )
    with pytest.raises(PublicationCommittedError) as caught:
        preparation_module.publish_synthetic_preparation(
            fixture.bundle,
            output_root=target,
            hmac_key=fixture.hmac_key,
        )
    assert caught.value.committed is True
    assert caught.value.retry_forbidden is True
    _assert_final_close_attempts(state)
    load_synthetic_preparation_candidate(target)


def test_existing_committed_error_survives_final_cleanup_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = build_synthetic_preparation_fixture(tmp_path / "source")
    parent = tmp_path / "attempt"
    parent.mkdir()
    os.chmod(parent, 0o700)
    target = parent / "candidate"
    state = _install_final_close_probe(
        monkeypatch,
        output_root=target,
        fail_stage=True,
        fail_parent=False,
    )
    real_rename = preparation_module._atomic_rename_noreplace_at

    def rename_then_raise(parent_descriptor: int, source: str, target_name: str) -> None:
        real_rename(parent_descriptor, source, target_name)
        raise OSError("injected after successful atomic rename")

    monkeypatch.setattr(
        preparation_module,
        "_atomic_rename_noreplace_at",
        rename_then_raise,
    )
    with pytest.raises(PublicationCommittedError) as caught:
        preparation_module.publish_synthetic_preparation(
            fixture.bundle,
            output_root=target,
            hmac_key=fixture.hmac_key,
        )
    assert caught.value.committed is True
    assert caught.value.retry_forbidden is True
    _assert_final_close_attempts(state)
    load_synthetic_preparation_candidate(target)


def test_existing_indeterminate_error_survives_final_cleanup_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = build_synthetic_preparation_fixture(tmp_path / "source")
    parent = tmp_path / "attempt"
    parent.mkdir()
    os.chmod(parent, 0o700)
    target = parent / "candidate"
    state = _install_final_close_probe(
        monkeypatch,
        output_root=target,
        fail_stage=True,
        fail_parent=True,
    )
    quarantine = ".candidate.indeterminate-review"

    def move_elsewhere_then_raise(
        parent_descriptor: int,
        source: str,
        target_name: str,
    ) -> None:
        del target_name
        os.rename(
            source,
            quarantine,
            src_dir_fd=parent_descriptor,
            dst_dir_fd=parent_descriptor,
        )
        raise OSError("injected indeterminate publication outcome")

    monkeypatch.setattr(
        preparation_module,
        "_atomic_rename_noreplace_at",
        move_elsewhere_then_raise,
    )
    with pytest.raises(PublicationOutcomeIndeterminateError) as caught:
        preparation_module.publish_synthetic_preparation(
            fixture.bundle,
            output_root=target,
            hmac_key=fixture.hmac_key,
        )
    assert caught.value.committed is None
    assert caught.value.retry_forbidden is True
    _assert_final_close_attempts(state)
    assert not target.exists()
    assert (parent / quarantine).is_dir()


def test_precommit_failure_with_final_cleanup_failures_touches_only_stage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = build_synthetic_preparation_fixture(tmp_path / "source")
    parent = tmp_path / "attempt"
    parent.mkdir()
    os.chmod(parent, 0o700)
    unrelated = parent / "unrelated"
    unrelated.mkdir()
    os.chmod(unrelated, 0o700)
    marker = unrelated / "marker.txt"
    marker.write_text("preserve", encoding="utf-8")
    os.chmod(marker, 0o600)
    target = parent / "candidate"
    state = _install_final_close_probe(
        monkeypatch,
        output_root=target,
        fail_stage=True,
        fail_parent=True,
    )

    def fail_before_rename(
        parent_descriptor: int,
        source: str,
        target_name: str,
    ) -> None:
        del parent_descriptor, source, target_name
        raise OSError("injected provable pre-commit failure")

    monkeypatch.setattr(
        preparation_module,
        "_atomic_rename_noreplace_at",
        fail_before_rename,
    )
    with pytest.raises(PreparationError) as caught:
        preparation_module.publish_synthetic_preparation(
            fixture.bundle,
            output_root=target,
            hmac_key=fixture.hmac_key,
        )
    assert not isinstance(
        caught.value,
        (PublicationCommittedError, PublicationOutcomeIndeterminateError),
    )
    _assert_final_close_attempts(state)
    assert not target.exists()
    assert not list(parent.glob(".candidate.synthetic-staging-*"))
    assert marker.read_text(encoding="utf-8") == "preserve"


def test_normal_publication_attempts_each_final_close_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = build_synthetic_preparation_fixture(tmp_path / "source")
    parent = tmp_path / "attempt"
    parent.mkdir()
    os.chmod(parent, 0o700)
    target = parent / "candidate"
    state = _install_final_close_probe(
        monkeypatch,
        output_root=target,
        fail_stage=False,
        fail_parent=False,
    )
    preparation_module.publish_synthetic_preparation(
        fixture.bundle,
        output_root=target,
        hmac_key=fixture.hmac_key,
    )
    _assert_final_close_attempts(state)
    load_synthetic_preparation_candidate(target)


def test_synthetic_serialization_is_byte_deterministic(tmp_path: Path) -> None:
    first = build_synthetic_preparation_fixture(tmp_path / "first")
    second = build_synthetic_preparation_fixture(tmp_path / "second")
    assert first.published.artifact_map_sha256 == second.published.artifact_map_sha256
    assert first.published.manifest_sha256 == second.published.manifest_sha256
