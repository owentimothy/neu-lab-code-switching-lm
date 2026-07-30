from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest
from synthetic_preparation_support import synthetic_bangor_record

from cslm.tokenization.shared_wordpiece import (
    BACKEND_CORRECTION_ID,
    PROTOCOL_SEED,
    TOKENIZERS_VERSION,
    BuildComparison,
    TokenizerBuild,
    WordPieceReproducibilityError,
    build_wordpiece,
    canonical_json_bytes,
    compare_builds,
    configuration_sha256,
    extract_training_examples,
    protocol_configuration,
    runtime_manifest,
    sha256_file,
)


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_bytes(b"".join(canonical_json_bytes(row) for row in rows))


def _callhome(
    source: str,
    row_id: str,
    split: str,
    text: str,
) -> dict[str, object]:
    return {
        "conversation_ref": f"conversation-{row_id}",
        "row_id": row_id,
        "source": source,
        "speaker_ref": f"speaker-metadata-{row_id}",
        "split": split,
        "text": text,
        "turn_index": 0,
    }


def _cscont_callhome(row: dict[str, object]) -> dict[str, object]:
    return {
        "artifact_format_version": 1,
        "component": "callhome_monolingual_filler",
        "condition": "CsCont",
        "conversation_id": row["conversation_ref"],
        "document_id": "document-callhome",
        "document_row_index": 0,
        "lexical_tokens": sum(
            any(character.isalpha() for character in token) for token in str(row["text"]).split()
        ),
        "record_id": "callhome-record",
        "row": row,
        "source": row["source"],
        "split": "train",
    }


def _cscont_bangor() -> dict[str, object]:
    return synthetic_bangor_record(identity="shared-wordpiece", split="train")


@pytest.fixture
def synthetic_corpora(tmp_path: Path) -> tuple[Path, Path, Path]:
    english = tmp_path / "english_mono_rows.jsonl"
    spanish = tmp_path / "spanish_mono_rows.jsonl"
    cscont = tmp_path / "train_rows.jsonl"
    english_train_1 = _callhome("callhome_eng", "eng-2", "train", "same lexical text")
    english_train_2 = _callhome("callhome_eng", "eng-1", "train", "same lexical text")
    spanish_train = _callhome("callhome_spa", "spa-1", "train", "texto español")
    _write_jsonl(
        english,
        [
            english_train_1,
            _callhome("callhome_eng", "eng-validation", "validation", "forbidden leak"),
            english_train_2,
        ],
    )
    _write_jsonl(
        spanish,
        [
            spanish_train,
            _callhome("callhome_spa", "spa-test", "test", "fuga prohibida"),
        ],
    )
    _write_jsonl(cscont, [_cscont_callhome(english_train_2), _cscont_bangor()])
    return english, spanish, cscont


def test_two_extractions_have_identical_order_and_hash(
    synthetic_corpora: tuple[Path, Path, Path],
) -> None:
    first = extract_training_examples(*synthetic_corpora)
    second = extract_training_examples(*synthetic_corpora)

    assert first == second
    assert first.trainer_texts == (
        "same lexical text",
        "same lexical text",
        "texto español",
        "one two three",
    )
    assert first.ordered_input_sha256 == second.ordered_input_sha256
    assert first.manifest["ordered_identity_sha256"] == second.manifest["ordered_identity_sha256"]
    assert first.manifest["duplicate_counts"] == {"CsCont_CALLHOME_already_in_monolingual_union": 1}
    assert first.manifest["metadata_fields_emitted"] == []
    assert "forbidden leak" not in first.trainer_texts
    assert "fuga prohibida" not in first.trainer_texts


def test_extraction_does_not_modify_frozen_inputs(
    synthetic_corpora: tuple[Path, Path, Path],
) -> None:
    before = {path: sha256_file(path) for path in synthetic_corpora}
    extract_training_examples(*synthetic_corpora)
    after = {path: sha256_file(path) for path in synthetic_corpora}
    assert after == before


def test_conflicting_identity_text_pair_fails(tmp_path: Path) -> None:
    english = tmp_path / "english.jsonl"
    spanish = tmp_path / "spanish.jsonl"
    cscont = tmp_path / "cscont.jsonl"
    row = _callhome("callhome_eng", "eng-1", "train", "baseline text")
    conflicting = dict(row)
    conflicting["text"] = "conflicting text"
    _write_jsonl(english, [row, conflicting])
    _write_jsonl(
        spanish,
        [_callhome("callhome_spa", "spa-1", "train", "texto español")],
    )
    _write_jsonl(cscont, [])

    with pytest.raises(
        WordPieceReproducibilityError,
        match="conflicting CALLHOME identity/text pair",
    ):
        extract_training_examples(english, spanish, cscont)


def test_environment_manifest_records_versions_and_configuration_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tokenizers = pytest.importorskip("tokenizers")
    monkeypatch.setenv("PYTHONHASHSEED", str(PROTOCOL_SEED))
    monkeypatch.setenv("TOKENIZERS_PARALLELISM", "false")
    package_dir = Path(tokenizers.__file__).resolve().parent
    extension = next(package_dir.glob("tokenizers.*.so"))
    backend_manifest = {
        "backend_correction_id": BACKEND_CORRECTION_ID,
        "tokenizers_version": TOKENIZERS_VERSION,
        "build_configuration_sha256": "configuration-record",
        "native_backend": {"sha256": sha256_file(extension)},
    }

    manifest = runtime_manifest(tokenizers, backend_manifest)

    assert manifest["python"]
    assert manifest["tokenizers"] == TOKENIZERS_VERSION
    assert manifest["architecture"]
    assert manifest["configuration_sha256"] == configuration_sha256()
    assert manifest["backend_build_configuration_sha256"] == "configuration-record"
    assert len(manifest["native_backend"]["sha256"]) == 64


def test_missing_python_hash_seed_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tokenizers = pytest.importorskip("tokenizers")
    monkeypatch.delenv("PYTHONHASHSEED", raising=False)
    monkeypatch.setenv("TOKENIZERS_PARALLELISM", "false")
    with pytest.raises(WordPieceReproducibilityError, match="PYTHONHASHSEED"):
        runtime_manifest(tokenizers, {})


def test_configuration_hash_covers_frozen_protocol() -> None:
    configuration = protocol_configuration()
    assert configuration["vocabulary_size"] == 8_000
    assert configuration["special_tokens"] == {
        "[PAD]": 0,
        "[UNK]": 1,
        "[CLS]": 2,
        "[SEP]": 3,
        "[MASK]": 4,
    }
    assert configuration["normalization"]["strip_accents"] is False
    assert len(configuration_sha256()) == 64


def test_strict_comparison_detects_token_id_difference() -> None:
    first = TokenizerBuild(
        files={"vocab.txt": b"a\nb\n", "tokenizer.json": b"first\n"},
        file_sha256={"vocab.txt": "one", "tokenizer.json": "two"},
        vocabulary_by_id=("a", "b"),
    )
    second = TokenizerBuild(
        files={"vocab.txt": b"b\na\n", "tokenizer.json": b"second\n"},
        file_sha256={"vocab.txt": "three", "tokenizer.json": "four"},
        vocabulary_by_id=("b", "a"),
    )

    comparison = compare_builds(first, second)

    assert comparison == BuildComparison(
        identical_vocabulary=True,
        identical_token_ids=False,
        identical_vocab_txt=False,
        identical_tokenizer_json=False,
        identical_checksums=False,
    )
    assert comparison.passed is False


def test_two_corrected_backend_builds_are_byte_identical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_path_value = os.environ.get("NEU_TOKENIZERS_BACKEND_MANIFEST")
    if not manifest_path_value:
        pytest.skip("corrected backend integration manifest was not supplied")
    backend_manifest = json.loads(Path(manifest_path_value).read_text(encoding="utf-8"))
    monkeypatch.setenv("PYTHONHASHSEED", str(PROTOCOL_SEED))
    monkeypatch.setenv("TOKENIZERS_PARALLELISM", "false")
    texts = tuple(
        "english"
        + hashlib.sha256(f"english-{index}".encode()).hexdigest()[:20]
        + " español"
        + hashlib.sha256(f"spanish-{index}".encode()).hexdigest()[:20]
        for index in range(12_000)
    )

    first = build_wordpiece(texts, backend_manifest)
    second = build_wordpiece(texts, backend_manifest)
    comparison = compare_builds(first, second)

    assert len(first.vocabulary_by_id) == 8_000
    assert comparison.passed is True
