from __future__ import annotations

import os
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from tokenizers import Tokenizer, models, normalizers, pre_tokenizers

from cslm.modeling.preparation import (
    PreparationBundle,
    SyntheticPreparationSnapshot,
    SyntheticPublishedPreparationCandidate,
    adapt_callhome_record,
    adapt_cscont_record,
    load_synthetic_preparation_candidate,
    make_synthetic_exact_tokenizer,
    prepare_synthetic_rows,
    publish_synthetic_preparation,
)


@dataclass(frozen=True)
class SyntheticPreparationFixture:
    bundle: PreparationBundle
    published: SyntheticPublishedPreparationCandidate
    snapshot: SyntheticPreparationSnapshot
    output_root: Path
    hmac_key: bytes


def synthetic_callhome_row_identity(
    source: str,
    conversation_id: str,
    turn_index: int,
) -> str:
    payload = f"row\0{source}\0{conversation_id}\0{turn_index}".encode()
    return "row_" + sha256(payload).hexdigest()[:16]


def synthetic_callhome_document_identity(
    source: str,
    split: str,
    conversation_id: str,
) -> str:
    payload = "\0".join(
        ("1729", "callhome-document", source, split, conversation_id)
    ).encode()
    return "callhome_doc_" + sha256(payload).hexdigest()[:16]


def _callhome(
    *,
    source: str,
    split: str,
    identity: str,
) -> dict[str, object]:
    conversation_id = f"conversation-{identity}"
    return {
        "conversation_ref": conversation_id,
        "row_id": synthetic_callhome_row_identity(source, conversation_id, 0),
        "source": source,
        "speaker_ref": "synthetic-speaker",
        "split": split,
        "text": "one two three",
        "turn_index": 0,
    }


def synthetic_bangor_nested_row(
    *,
    identity: str,
    split: str,
    sensitive_marker: str = "synthetic-speaker-metadata",
) -> dict[str, object]:
    """Privacy-safe exact representation of the accepted 45-field Bangor row."""
    conversation_id = f"conversation-{identity}"
    source_utterance_id = 1
    text = "one two three"
    row = {
        "borrowing_status": None,
        "clean_text": text,
        "condition_candidates": ["CsCont"],
        "conversation_id": conversation_id,
        "equivalence_heuristic": None,
        "inter_sentential_switch_direction_from_previous": None,
        "is_inter_sentential_switch_from_previous": None,
        "language_category": "cs_within_utterance",
        "matrix_language_heuristic": None,
        "n_english_word_tokens": 2,
        "n_metadata_tokens": 0,
        "n_mixed_morpheme_word_tokens": 0,
        "n_neutral_bivalent_word_tokens": 0,
        "n_other_word_tokens": 0,
        "n_punctuation_tokens": 0,
        "n_spanish_word_tokens": 1,
        "n_tokens_including_punctuation": 3,
        "n_word_tokens_excluding_punctuation": 3,
        "needs_review_borrowing": False,
        "needs_review_equivalence": False,
        "needs_review_matrix_language": False,
        "needs_review_mixed_morpheme": False,
        "needs_review_unexpected_langid": False,
        "normalization_profile": "source_faithful_audit",
        "previous_language_category": None,
        "previous_speaker_id": None,
        "previous_utterance_id": None,
        "raw_text": text,
        "same_speaker_as_previous": None,
        "source": "bangor_cgwords",
        "source_header": [
            "word_id",
            "utterance_id",
            "location",
            "surface",
            "auto",
            "fix",
            "eng",
            "com",
            "speaker",
            "langid",
            "filename",
            "clause",
            "clauseno",
        ],
        "source_line_numbers": [2, 3, 4],
        "source_optional_fields_present": [
            "auto",
            "clause",
            "clauseno",
            "com",
            "eng",
            "fix",
        ],
        "source_path": f"{conversation_id}_cgwords.tsv",
        "source_token_language_labels": ["eng", "spa", "eng"],
        "source_token_locations": [1, 2, 3],
        "source_utterance_id": source_utterance_id,
        "source_word_ids": [3, 1, 2],
        "speaker_id": sensitive_marker,
        "split": split,
        "text": text,
        "token_language_labels": ["eng", "spa", "eng"],
        "tokens": ["one", "two", "three"],
        "utterance_id": f"{conversation_id}_{source_utterance_id:06d}",
        "utterance_index": 0,
    }
    return dict(sorted(row.items()))


def synthetic_bangor_punctuation_nested_row(
    *,
    identity: str,
    split: str,
    sensitive_marker: str = "synthetic-speaker-metadata",
) -> dict[str, object]:
    """Exact source-faithful Bangor punctuation-only row using synthetic values."""
    row = synthetic_bangor_nested_row(
        identity=identity,
        split=split,
        sensitive_marker=sensitive_marker,
    )
    text = "!"
    row.update(
        {
            "clean_text": text,
            "condition_candidates": [],
            "language_category": "punctuation_or_empty",
            "n_english_word_tokens": 0,
            "n_punctuation_tokens": 1,
            "n_spanish_word_tokens": 0,
            "n_tokens_including_punctuation": 1,
            "n_word_tokens_excluding_punctuation": 0,
            "raw_text": text,
            "source_line_numbers": [2],
            "source_token_language_labels": ["999"],
            "source_token_locations": [1],
            "source_word_ids": [1],
            "text": text,
            "token_language_labels": ["punct"],
            "tokens": [text],
        }
    )
    return dict(sorted(row.items()))


def synthetic_bangor_record(
    *,
    identity: str,
    split: str,
    sensitive_marker: str = "synthetic-speaker-metadata",
    nested: dict[str, object] | None = None,
    document_id: str | None = None,
    document_row_index: int = 0,
) -> dict[str, object]:
    if nested is None:
        nested = synthetic_bangor_nested_row(
            identity=identity,
            split=split,
            sensitive_marker=sensitive_marker,
        )
    document_suffix = sha256(identity.encode("ascii")).hexdigest()[:16]
    return {
        "artifact_format_version": 1,
        "component": "bangor_natural_span",
        "condition": "CsCont",
        "conversation_id": nested["conversation_id"],
        "document_id": document_id or f"bangor_span_{document_suffix}",
        "document_row_index": document_row_index,
        "lexical_tokens": nested["n_word_tokens_excluding_punctuation"],
        "record_id": f"bangor:{nested['utterance_id']}",
        "row": nested,
        "source": "bangor_cgwords",
        "split": split,
    }


def synthetic_bangor_record_sequence(
    *,
    identity: str,
    split: str,
    length: int = 2,
    sensitive_marker: str = "synthetic-speaker-metadata",
) -> list[dict[str, object]]:
    """Build one authoritative contiguous Bangor span using synthetic values."""
    if length <= 0:
        raise ValueError("synthetic Bangor sequence length must be positive")
    document_suffix = sha256(identity.encode("ascii")).hexdigest()[:16]
    document_id = f"bangor_span_{document_suffix}"
    records: list[dict[str, object]] = []
    previous: dict[str, object] | None = None
    for index in range(length):
        nested = synthetic_bangor_nested_row(
            identity=identity,
            split=split,
            sensitive_marker=sensitive_marker,
        )
        source_utterance_id = index + 1
        nested["source_utterance_id"] = source_utterance_id
        nested["utterance_id"] = (
            f"{nested['conversation_id']}_{source_utterance_id:06d}"
        )
        nested["utterance_index"] = index
        base_word_id = index * 3
        nested["source_word_ids"] = [
            base_word_id + 3,
            base_word_id + 1,
            base_word_id + 2,
        ]
        base_line = 2 + index * 3
        nested["source_line_numbers"] = [base_line, base_line + 1, base_line + 2]
        if previous is not None:
            nested["previous_utterance_id"] = previous["utterance_id"]
            nested["previous_speaker_id"] = previous["speaker_id"]
            nested["previous_language_category"] = previous["language_category"]
            nested["same_speaker_as_previous"] = True
        nested = dict(sorted(nested.items()))
        records.append(
            synthetic_bangor_record(
                identity=identity,
                split=split,
                sensitive_marker=sensitive_marker,
                nested=nested,
                document_id=document_id,
                document_row_index=index,
            )
        )
        previous = nested
    return records


def _cscont(*, split: str) -> dict[str, object]:
    return synthetic_bangor_record(identity=f"cscont-{split}", split=split)


def _cscont_filler(row: dict[str, object]) -> dict[str, object]:
    source = str(row["source"])
    split = str(row["split"])
    conversation_id = str(row["conversation_ref"])
    nested_row_id = str(row["row_id"])
    return {
        "artifact_format_version": 1,
        "component": "callhome_monolingual_filler",
        "condition": "CsCont",
        "conversation_id": conversation_id,
        "document_id": synthetic_callhome_document_identity(
            source,
            split,
            conversation_id,
        ),
        "document_row_index": 0,
        "lexical_tokens": 3,
        "record_id": f"{source}:{nested_row_id}",
        "row": row,
        "source": source,
        "split": split,
    }


def synthetic_population():
    rows = []
    for split in ("train", "validation"):
        english = _callhome(
            source="callhome_eng",
            split=split,
            identity=f"shared-english-{split}",
        )
        spanish = _callhome(
            source="callhome_spa",
            split=split,
            identity=f"shared-spanish-{split}",
        )
        rows.extend(
            (
                adapt_callhome_record(
                    english,
                    logical_condition="EnglishMono",
                ),
                adapt_callhome_record(
                    spanish,
                    logical_condition="SpanishMono",
                ),
            )
        )
    ordered = (
        rows[0],
        rows[2],
        rows[1],
        rows[3],
        adapt_callhome_record(
            _callhome(
                source="callhome_eng",
                split="train",
                identity="shared-english-train",
            ),
            logical_condition="MonoCont",
        ),
        adapt_callhome_record(
            _callhome(
                source="callhome_spa",
                split="train",
                identity="shared-spanish-train",
            ),
            logical_condition="MonoCont",
        ),
        adapt_callhome_record(
            _callhome(
                source="callhome_eng",
                split="validation",
                identity="shared-english-validation",
            ),
            logical_condition="MonoCont",
        ),
        adapt_callhome_record(
            _callhome(
                source="callhome_spa",
                split="validation",
                identity="shared-spanish-validation",
            ),
            logical_condition="MonoCont",
        ),
        adapt_cscont_record(_cscont(split="train")),
        adapt_cscont_record(
            _cscont_filler(
                _callhome(
                    source="callhome_eng",
                    split="train",
                    identity="shared-english-train",
                )
            )
        ),
        adapt_cscont_record(
            _cscont_filler(
                _callhome(
                    source="callhome_spa",
                    split="train",
                    identity="shared-spanish-train",
                )
            )
        ),
        adapt_cscont_record(_cscont(split="validation")),
        adapt_cscont_record(
            _cscont_filler(
                _callhome(
                    source="callhome_eng",
                    split="validation",
                    identity="shared-english-validation",
                )
            )
        ),
        adapt_cscont_record(
            _cscont_filler(
                _callhome(
                    source="callhome_spa",
                    split="validation",
                    identity="shared-spanish-validation",
                )
            )
        ),
    )
    return ordered


def _tokenizer() -> Tokenizer:
    tokens = [
        "[PAD]",
        "[UNK]",
        "[CLS]",
        "[SEP]",
        "[MASK]",
        "one",
        "two",
        "three",
    ]
    tokens.extend(f"synthetic_{index}" for index in range(len(tokens), 8_000))
    tokenizer = Tokenizer(
        models.WordPiece(
            {token: index for index, token in enumerate(tokens)},
            unk_token="[UNK]",
            continuing_subword_prefix="##",
        )
    )
    tokenizer.normalizer = normalizers.Sequence(
        [
            normalizers.NFC(),
            normalizers.BertNormalizer(
                clean_text=True,
                handle_chinese_chars=False,
                strip_accents=False,
                lowercase=True,
            ),
        ]
    )
    tokenizer.pre_tokenizer = pre_tokenizers.BertPreTokenizer()
    return tokenizer


def synthetic_exact_tokenizer():
    """Return the existing synthetic-only exact WordPiece test tokenizer."""
    return make_synthetic_exact_tokenizer(_tokenizer())


def build_synthetic_preparation_fixture(
    base: Path,
    *,
    synthetic_test_hook=None,
) -> SyntheticPreparationFixture:
    base.mkdir(parents=True, exist_ok=True)
    os.chmod(base, 0o700)
    output_root = base / "synthetic-candidate"
    hmac_key = b"k" * 32
    bundle = prepare_synthetic_rows(
        synthetic_population(),
        tokenizer=synthetic_exact_tokenizer(),
        hmac_key=hmac_key,
    )
    published = publish_synthetic_preparation(
        bundle,
        output_root=output_root,
        hmac_key=hmac_key,
        synthetic_test_hook=synthetic_test_hook,
    )
    snapshot = load_synthetic_preparation_candidate(output_root)
    return SyntheticPreparationFixture(
        bundle=bundle,
        published=published,
        snapshot=snapshot,
        output_root=output_root,
        hmac_key=hmac_key,
    )
