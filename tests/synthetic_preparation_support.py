from __future__ import annotations

import os
from dataclasses import dataclass
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


def _callhome(
    *,
    source: str,
    split: str,
    identity: str,
) -> dict[str, object]:
    return {
        "conversation_ref": f"conversation-{identity}",
        "row_id": f"row-{identity}",
        "source": source,
        "speaker_ref": "synthetic-speaker",
        "split": split,
        "text": "one two three",
        "turn_index": 0,
    }


def _cscont(*, split: str) -> dict[str, object]:
    identity = f"cscont-{split}"
    return {
        "artifact_format_version": 1,
        "component": "bangor_natural_span",
        "condition": "CsCont",
        "conversation_id": f"conversation-{identity}",
        "document_id": f"document-{identity}",
        "document_row_index": 0,
        "lexical_tokens": 3,
        "record_id": f"row-{identity}",
        "row": {
            "conversation_id": f"conversation-{identity}",
            "source_word_ids": [1, 2, 3],
            "text": "one two three",
            "tokens": ["one", "two", "three"],
        },
        "source": "bangor_cgwords",
        "split": split,
    }


def _cscont_filler(row: dict[str, object]) -> dict[str, object]:
    return {
        "artifact_format_version": 1,
        "component": "callhome_monolingual_filler",
        "condition": "CsCont",
        "conversation_id": row["conversation_ref"],
        "document_id": f"filler-{row['conversation_ref']}",
        "document_row_index": row["turn_index"],
        "lexical_tokens": 3,
        "record_id": row["row_id"],
        "row": row,
        "source": row["source"],
        "split": row["split"],
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
        tokenizer=make_synthetic_exact_tokenizer(_tokenizer()),
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
