from __future__ import annotations

import json
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import pytest

import cslm.modeling.preparation as preparation
from cslm.modeling.preparation import (
    APPROVED_CALLHOME_CHECKSUM_RECORD_SHA256,
    APPROVED_CSCONT_CHECKSUM_RECORD_SHA256,
    APPROVED_TOKENIZER_CHECKSUM_RECORD_SHA256,
    InputPopulationAnchor,
    PreparationError,
    _VerifiedFrozenRoot,
)

_CORRECTED_BACKEND = {
    "backend_build_configuration_sha256": (
        "addb9604439dab5c2a4b9b686f514624282180893196bcd2033ee5c9f44adb7a"
    ),
    "backend_build_manifest_sha256": (
        "e719e7b9711045442a549063830ea27de7a9026df8aa2a3be4e8a3c24e30c293"
    ),
    "backend_correction_id": "tokenizers_0_22_2_sorted_word_counts_v1",
    "maturin": "maturin 1.9.6",
    "native_backend_sha256": (
        "04abb6b68b30c7f6393d7bff7ee77400ae69f4010dae4c98a93e1665cbcc0954"
    ),
    "patch_sha256": "9cd04532dfcb5e788eadf170f642a27a27bce318f6b11f27afc839c7cd771280",
    "rustc": "rustc 1.89.0 (29483883e 2025-08-04)",
    "tokenizers_version": "0.22.2",
    "upstream_commit": "f383101a26663708484cac0727792aad74f78234",
}


def _accepted_manifest() -> dict[str, object]:
    wordpiece_configuration = preparation.protocol_configuration()
    configuration_sha256 = sha256(
        preparation.canonical_json_bytes(wordpiece_configuration)
    ).hexdigest()
    return {
        "audit": {},
        "builder": "shared_wordpiece_tokenizer_freeze_v1",
        "configuration_sha256": configuration_sha256,
        "corrected_backend": deepcopy(_CORRECTED_BACKEND),
        "format_version": 1,
        "freeze_decision": "PASS",
        "freeze_declaration": (
            "This single tokenizer vocabulary, token-ID mapping, normalization, "
            "preprocessing, and checksum are frozen for EnglishMono, SpanishMono, "
            "MonoCont, and CsCont."
        ),
        "frozen_inputs": {},
        "repository": {},
        "reproducibility": {},
        "runtime": {
            "architecture": "synthetic-architecture",
            "backend_build_configuration_sha256": _CORRECTED_BACKEND[
                "backend_build_configuration_sha256"
            ],
            "backend_correction_id": _CORRECTED_BACKEND["backend_correction_id"],
            "configuration_sha256": configuration_sha256,
            "native_backend": {
                "filename": "tokenizers.abi3.so",
                "sha256": _CORRECTED_BACKEND["native_backend_sha256"],
            },
            "os": "synthetic-platform",
            "python": "3.12.2",
            "python_executable_sha256": "1" * 64,
            "python_hash_seed": "1729",
            "python_implementation": "CPython",
            "rust_backend_version_exposed": None,
            "tokenizers": "0.22.2",
            "tokenizers_parallelism": "false",
        },
        "scientific_invariants": {},
        "training_corpus": {},
        "wordpiece_configuration": wordpiece_configuration,
    }


def _root(
    manifest: dict[str, object] | None = None,
    *,
    replacements: dict[str, bytes] | None = None,
    unaccounted: dict[str, bytes] | None = None,
    record_identity: str = APPROVED_TOKENIZER_CHECKSUM_RECORD_SHA256,
) -> _VerifiedFrozenRoot:
    files = {
        "audit_results.json": preparation.canonical_json_bytes({"format_version": 1}),
        "tokenizer.json": preparation.canonical_json_bytes({}),
        "tokenizer_config.json": preparation.canonical_json_bytes({"format_version": 1}),
        "training_manifest.json": preparation.canonical_json_bytes(
            manifest if manifest is not None else _accepted_manifest()
        ),
        "vocab.txt": b"synthetic-token\n",
    }
    files.update(replacements or {})
    checksums = {name: sha256(content).hexdigest() for name, content in files.items()}
    small_contents = {**files, **(unaccounted or {})}
    return _VerifiedFrozenRoot(
        root_descriptor=-1,
        record_identity_sha256=record_identity,
        constituent_sha256=MappingProxyType(dict(sorted(checksums.items()))),
        small_contents=MappingProxyType(dict(sorted(small_contents.items()))),
        file_identities=MappingProxyType({}),
    )


def _historical(
    manifest: dict[str, object] | None = None,
    **root_options: object,
):
    return preparation._historical_tokenizer_build_identity(
        _root(manifest, **root_options)
    )


def _standalone_record() -> dict[str, object]:
    return {
        "backend_correction_id": "tokenizers_0_22_2_sorted_word_counts_v1",
        "build": {"cargo_locked": True, "maturin": "1.9.6", "rust": "1.89.0"},
        "format_version": 1,
        "patch": "infra/tokenizers/tokenizers-0.22.2-neu-deterministic-wordpiece.patch",
        "tokenizers": "0.22.2",
        "upstream_commit": "f383101a26663708484cac0727792aad74f78234",
        "upstream_repository": "https://github.com/huggingface/tokenizers.git",
        "upstream_tag": "v0.22.2",
    }


def _changed_build_configuration_sha256(
    manifest: dict[str, object],
    *,
    lock_mutation,
) -> str:
    lock = deepcopy(preparation._accepted_tokenizer_backend_lock())
    lock_mutation(lock)
    record = manifest["corrected_backend"]
    runtime = manifest["runtime"]
    assert isinstance(record, dict)
    assert isinstance(runtime, dict)
    configuration = {
        "backend_lock": lock,
        "backend_lock_sha256": sha256(
            preparation.canonical_json_bytes(lock)
        ).hexdigest(),
        "patch_sha256": record["patch_sha256"],
        "cargo_locked": lock["build"]["cargo_locked"],
        "rustc": record["rustc"],
        "maturin": record["maturin"],
        "python": f"Python {runtime['python']}",
    }
    return sha256(preparation.canonical_json_bytes(configuration)).hexdigest()


def _anchor(historical) -> InputPopulationAnchor:
    anchor = object.__new__(InputPopulationAnchor)
    object.__setattr__(
        anchor,
        "checksum_record_identities",
        (
            ("callhome", APPROVED_CALLHOME_CHECKSUM_RECORD_SHA256),
            ("cscont", APPROVED_CSCONT_CHECKSUM_RECORD_SHA256),
            ("tokenizer", APPROVED_TOKENIZER_CHECKSUM_RECORD_SHA256),
        ),
    )
    object.__setattr__(
        anchor,
        "constituent_sha256",
        (("tokenizer:training_manifest.json", historical["constituent_sha256"]),),
    )
    object.__setattr__(anchor, "input_line_counts", ())
    object.__setattr__(anchor, "authorized_line_counts", ())
    object.__setattr__(anchor, "sealed_test_line_counts", ())
    object.__setattr__(anchor, "identity_sha256", "0" * 64)
    return anchor


def test_exact_accepted_nested_tokenizer_metadata_schema_succeeds() -> None:
    historical = _historical()
    assert historical["record_location"] == "training_manifest.json#/corrected_backend"
    assert historical["container_schema"] == "shared_wordpiece_tokenizer_freeze_v1"
    assert historical["container_format_version"] == 1
    assert historical["record"] == _CORRECTED_BACKEND
    assert historical["backend_lock"] == _standalone_record()


def test_nested_historical_identity_is_deterministic_across_repeated_loading() -> None:
    first = _historical()
    second = _historical()
    assert first == second
    assert preparation.canonical_json_bytes(first) == preparation.canonical_json_bytes(second)


def test_missing_nested_record_fails() -> None:
    manifest = _accepted_manifest()
    manifest.pop("corrected_backend")
    with pytest.raises(PreparationError):
        _historical(manifest)


@pytest.mark.parametrize("location", ["accounted-file", "container-section"])
def test_duplicate_nested_record_in_accounted_metadata_fails(location: str) -> None:
    if location == "container-section":
        manifest = _accepted_manifest()
        manifest["audit"]["corrected_backend"] = deepcopy(_CORRECTED_BACKEND)
        with pytest.raises(PreparationError):
            _historical(manifest)
        return
    duplicate = preparation.canonical_json_bytes({"corrected_backend": _CORRECTED_BACKEND})
    with pytest.raises(PreparationError):
        _historical(replacements={"audit_results.json": duplicate})


def test_conflicting_nested_and_standalone_records_fail() -> None:
    standalone = preparation.canonical_json_bytes(_standalone_record())
    with pytest.raises(PreparationError):
        _historical(replacements={"tokenizer_config.json": standalone})


def test_standalone_only_record_is_not_an_accepted_production_layout() -> None:
    standalone = preparation.canonical_json_bytes(_standalone_record())
    with pytest.raises(PreparationError):
        _historical(replacements={"training_manifest.json": standalone})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("format_version", 2),
        ("builder", "different_freeze_schema"),
    ],
)
def test_wrong_container_format_or_schema_version_fails(field: str, value: object) -> None:
    manifest = _accepted_manifest()
    manifest[field] = value
    with pytest.raises(PreparationError):
        _historical(manifest)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("backend_correction_id", "uncorrected_backend"),
        ("tokenizers_version", "0.22.1"),
        ("upstream_commit", "f" * 40),
        ("upstream_commit", "not-a-commit"),
    ],
)
def test_wrong_backend_tokenizers_version_or_upstream_commit_fails(
    field: str,
    value: str,
) -> None:
    manifest = _accepted_manifest()
    manifest["corrected_backend"][field] = value
    with pytest.raises(PreparationError):
        _historical(manifest)


@pytest.mark.parametrize(
    "lock_mutation",
    [
        lambda lock: lock.update(
            upstream_repository="https://example.invalid/tokenizers.git"
        ),
        lambda lock: lock.update(upstream_tag="v0.22.1"),
        lambda lock: lock.update(patch="infra/tokenizers/different.patch"),
        lambda lock: lock["build"].update(cargo_locked=False),
    ],
    ids=["repository", "tag", "patch-reference", "cargo-unlocked"],
)
def test_changed_upstream_patch_reference_or_cargo_lock_digest_is_not_authoritative(
    lock_mutation,
) -> None:
    manifest = _accepted_manifest()
    manifest["corrected_backend"]["backend_build_configuration_sha256"] = (
        _changed_build_configuration_sha256(manifest, lock_mutation=lock_mutation)
    )
    manifest["runtime"]["backend_build_configuration_sha256"] = manifest[
        "corrected_backend"
    ]["backend_build_configuration_sha256"]
    with pytest.raises(PreparationError):
        _historical(manifest)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("patch_sha256", "not-a-checksum"),
        ("maturin", "maturin 1.9.5"),
        ("rustc", "rustc 1.88.0"),
    ],
)
def test_malformed_patch_or_wrong_maturin_or_rust_identity_fails(
    field: str,
    value: str,
) -> None:
    manifest = _accepted_manifest()
    manifest["corrected_backend"][field] = value
    with pytest.raises(PreparationError):
        _historical(manifest)


@pytest.mark.parametrize("field", ["patch_sha256", "maturin", "rustc"])
def test_missing_patch_maturin_or_rust_identity_fails(field: str) -> None:
    manifest = _accepted_manifest()
    manifest["corrected_backend"].pop(field)
    with pytest.raises(PreparationError):
        _historical(manifest)


def test_unaccounted_extra_metadata_file_cannot_provide_authority() -> None:
    extra = preparation.canonical_json_bytes(
        {"corrected_backend": deepcopy(_CORRECTED_BACKEND)}
    )
    with pytest.raises(PreparationError):
        _historical(unaccounted={"extra_metadata.json": extra})


@pytest.mark.parametrize(
    "mutation",
    ["record-identity", "constituent-digest"],
)
def test_checksum_accounted_metadata_binding_is_enforced(mutation: str) -> None:
    root = _root(
        record_identity="f" * 64
        if mutation == "record-identity"
        else APPROVED_TOKENIZER_CHECKSUM_RECORD_SHA256
    )
    if mutation == "constituent-digest":
        checksums = dict(root.constituent_sha256)
        checksums["training_manifest.json"] = "f" * 64
        object.__setattr__(
            root,
            "constituent_sha256",
            MappingProxyType(dict(sorted(checksums.items()))),
        )
    with pytest.raises(PreparationError):
        preparation._historical_tokenizer_build_identity(root)


def test_validation_does_not_trust_patchable_identity_constants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(preparation, "APPROVED_TOKENIZER_CHECKSUM_RECORD_SHA256", "f" * 64)
    monkeypatch.setattr(preparation, "BACKEND_CORRECTION_ID", "uncorrected_backend")
    historical = _historical()
    assert historical["checksum_record_sha256"] == (
        "25489e732b64ce63c0380012ea719571f9cb4fc6c369e43da920d2b45af55b8d"
    )
    assert historical["record"]["backend_correction_id"] == (
        "tokenizers_0_22_2_sorted_word_counts_v1"
    )


def test_persisted_historical_identity_binds_to_tokenizer_input_anchor() -> None:
    historical = _historical()
    anchor = _anchor(historical)
    preparation._validate_historical_identity_record(historical, anchor)
    object.__setattr__(
        anchor,
        "checksum_record_identities",
        (("tokenizer", "f" * 64),),
    )
    with pytest.raises(PreparationError):
        preparation._validate_historical_identity_record(historical, anchor)


def test_historical_and_current_runtime_native_identities_remain_separate() -> None:
    historical = json.loads(preparation.canonical_json_bytes(_historical()))
    runtime_native_sha256 = "f" * 64
    runtime = {
        "python": {
            "version": "3.12.2",
            "implementation": "CPython",
            "abi": "synthetic-abi",
            "executable_sha256": "2" * 64,
        },
        "platform": {
            "os": "SyntheticOS",
            "os_release": "1",
            "architecture": "synthetic",
            "platform_tag": "synthetic-tag",
        },
        "dependencies": {
            name: {
                "version": version,
                "normalized_record_sha256": "3" * 64,
                "wheel_tags": ["synthetic-wheel"],
            }
            for name, version in {
                "numpy": "1.26.4",
                "tokenizers": "0.22.2",
                "torch": "2.11.0",
                "transformers": "5.6.2",
            }.items()
        },
        "historical_tokenizer_build": historical,
        "encoding_runtime_native": {
            "sha256": runtime_native_sha256,
            "abi": "synthetic-abi",
            "platform": "synthetic-tag",
            "historical_binary_equality_claimed": False,
        },
        "backend_correction_id": "tokenizers_0_22_2_sorted_word_counts_v1",
        "frozen_tokenizer_checksum_record_sha256": (
            APPROVED_TOKENIZER_CHECKSUM_RECORD_SHA256
        ),
        "loader_protocol": preparation.TOKENIZER_LOADER_PROTOCOL,
        "environment_controls": {
            "PYTHONHASHSEED": "1729",
            "TOKENIZERS_PARALLELISM": "false",
        },
    }
    preparation._validate_runtime_record(runtime, historical)
    assert runtime_native_sha256 != historical["record"]["native_backend_sha256"]
    assert runtime["encoding_runtime_native"]["historical_binary_equality_claimed"] is False


class _SyntheticNormalizer:
    @staticmethod
    def normalize_str(value: str) -> str:
        return {"CAFÉ": "café", "CAFE": "cafe"}[value]


class _SyntheticParityBackend:
    normalizer = _SyntheticNormalizer()

    @staticmethod
    def encode(text: str, *, add_special_tokens: bool):
        assert add_special_tokens is False
        normalized = " ".join(text.lower().replace("cafe\u0301", "café").split())
        if text == "x" * 101:
            return SimpleNamespace(ids=[1], tokens=["[UNK]"])
        token_id = sum(normalized.encode("utf-8")) % 997 + 2
        return SimpleNamespace(ids=[token_id], tokens=["base", "##continuation"])


def test_mandatory_fixed_synthetic_parity_still_passes() -> None:
    first = _SyntheticParityBackend()
    second = _SyntheticParityBackend()
    digest = preparation._fixed_tokenizer_parity(first, second)
    assert len(digest) == 64
    assert digest == preparation._fixed_tokenizer_parity(first, second)


def test_metadata_fixtures_contain_no_real_corpus_or_private_lexical_material() -> None:
    serialized = preparation.canonical_json_bytes(_accepted_manifest())
    assert b"conversation" not in serialized
    assert b"utterance" not in serialized
    assert b"speaker" not in serialized
    assert b"lexical_tokens" not in serialized
    assert Path(__file__).name == "test_preparation_tokenizer_metadata.py"
