from __future__ import annotations

import inspect
import json
import os
import stat
import traceback
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from synthetic_preparation_support import (
    build_synthetic_preparation_fixture,
    synthetic_population,
)

import cslm.modeling.preparation as preparation_module
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
    return {
        "conversation_ref": f"conversation-{identity}",
        "row_id": f"row-{identity}",
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
    if component == "bangor_natural_span":
        nested = nested or {
            "conversation_id": f"conversation-{identity}",
            "source_word_ids": [1, 2, 3],
            "text": "one two three",
            "tokens": ["one", "two", "three"],
        }
        source = "bangor_cgwords"
        conversation = nested["conversation_id"]
        row_id = f"row-{identity}"
        order = 0
    else:
        nested = nested or _callhome(
            source="callhome_eng",
            split=split,
            identity=identity,
        )
        source = str(nested["source"])
        conversation = nested["conversation_ref"]
        row_id = nested["row_id"]
        order = nested["turn_index"]
    return {
        "artifact_format_version": 1,
        "component": component,
        "condition": "CsCont",
        "conversation_id": conversation,
        "document_id": f"document-{identity}",
        "document_row_index": order,
        "lexical_tokens": lexical_token_count(str(nested["text"])),
        "record_id": row_id,
        "row": nested,
        "source": source,
        "split": split,
    }


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
    rendered = "".join(traceback.format_exception(error))
    assert not any(value in rendered for value in forbidden)
    for frame, _ in traceback.walk_tb(error.__traceback__):
        if Path(frame.f_code.co_filename).name != "preparation.py":
            continue
        rendered_locals = repr(frame.f_locals)
        assert not any(value in rendered_locals for value in forbidden)


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
        "validate_membership",
    }
    assert "authentic" not in inspect.getsource(preparation_module._pseudonym)


@pytest.mark.parametrize("control", ["checksum", "aggregates"])
def test_patched_production_controls_fail_before_any_input_access(
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
    with pytest.raises(PreparationError, match="controls were altered"):
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
