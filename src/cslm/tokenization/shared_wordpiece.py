"""Deterministic shared WordPiece extraction, training, and comparison.

The Rust backend correction is kept separate from this module.  The correction
removes randomized ``AHashMap`` traversal from WordPiece's initial subword-ID
assignment.  This module makes the Python control plane deterministic and
rejects an incompletely pinned runtime.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

PROTOCOL_ID = "shared_wordpiece_8k_v1"
BACKEND_CORRECTION_ID = "tokenizers_0_22_2_sorted_word_counts_v1"
PROTOCOL_SEED = 1729
TOKENIZERS_VERSION = "0.22.2"
VOCAB_SIZE = 8_000
MIN_FREQUENCY = 2
LIMIT_ALPHABET = 1_000
CONTINUATION_PREFIX = "##"
SPECIAL_TOKENS = ("[PAD]", "[UNK]", "[CLS]", "[SEP]", "[MASK]")
SPECIAL_TOKEN_IDS = {token: index for index, token in enumerate(SPECIAL_TOKENS)}


class WordPieceReproducibilityError(RuntimeError):
    """A strict tokenizer reproducibility invariant failed."""


@dataclass(frozen=True)
class TrainingExample:
    """Lexical trainer input plus control-plane identity."""

    logical_source: str
    identity_sha256: str
    text: str
    lexical_tokens: int


@dataclass(frozen=True)
class TrainingExtraction:
    """Deterministically ordered tokenizer examples and aggregate manifest."""

    examples: tuple[TrainingExample, ...]
    manifest: Mapping[str, Any]
    ordered_input_sha256: str

    @property
    def trainer_texts(self) -> tuple[str, ...]:
        """Return the only values permitted to enter the tokenizer trainer."""
        return tuple(example.text for example in self.examples)


@dataclass(frozen=True)
class TokenizerBuild:
    """In-memory tokenizer files and their checksums."""

    files: Mapping[str, bytes]
    file_sha256: Mapping[str, str]
    vocabulary_by_id: tuple[str, ...]


@dataclass(frozen=True)
class BuildComparison:
    """Strict comparison of two independently trained tokenizers."""

    identical_vocabulary: bool
    identical_token_ids: bool
    identical_vocab_txt: bool
    identical_tokenizer_json: bool
    identical_checksums: bool

    @property
    def passed(self) -> bool:
        return all(
            (
                self.identical_vocabulary,
                self.identical_token_ids,
                self.identical_vocab_txt,
                self.identical_tokenizer_json,
                self.identical_checksums,
            )
        )


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize JSON canonically for manifests and configuration hashes."""
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_file_sha256(path: Path, expected: str) -> None:
    actual = sha256_file(path)
    if actual != expected:
        raise WordPieceReproducibilityError(
            f"checksum mismatch for {path.name}: {actual} != {expected}"
        )


def _iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open("rb") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            if not raw_line.endswith(b"\n"):
                raise WordPieceReproducibilityError(
                    f"unterminated JSONL record in {path.name}:{line_number}"
                )
            try:
                record = json.loads(raw_line)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise WordPieceReproducibilityError(
                    f"invalid JSONL in {path.name}:{line_number}"
                ) from exc
            if not isinstance(record, dict):
                raise WordPieceReproducibilityError(
                    f"non-object JSONL record in {path.name}:{line_number}"
                )
            yield record


def _lexical_token_count(text: str) -> int:
    return sum(any(character.isalpha() for character in token) for token in text.split())


def _identity_sha256(parts: Sequence[Any]) -> str:
    return sha256_bytes(canonical_json_bytes(list(parts)))


def _validated_callhome_row(
    record: Mapping[str, Any],
    expected_source: str,
) -> tuple[tuple[str, str], str, str, int]:
    source = record.get("source")
    row_id = record.get("row_id")
    split = record.get("split")
    text = record.get("text")
    if not (
        source == expected_source
        and isinstance(row_id, str)
        and split in {"train", "validation", "test"}
        and isinstance(text, str)
        and text.strip()
        and "\n" not in text
        and "\r" not in text
    ):
        raise WordPieceReproducibilityError("invalid CALLHOME condition row")
    return (expected_source, row_id), str(split), text, _lexical_token_count(text)


def extract_training_examples(
    english_mono_path: Path,
    spanish_mono_path: Path,
    cscont_train_path: Path,
) -> TrainingExtraction:
    """Extract the frozen train-only union in a byte-stable order.

    Ordering is explicit: EnglishMono frozen JSONL order, SpanishMono frozen
    JSONL order, then Bangor rows in the frozen CsCont train JSONL order.
    No filesystem enumeration, Python set ordering, or dictionary iteration
    contributes trainer examples.
    """

    examples: list[TrainingExample] = []
    seen_callhome: dict[tuple[str, str], str] = {}
    rows_by_split: dict[str, Counter[str]] = {}
    lexical_by_split: dict[str, Counter[str]] = {}
    duplicate_counts: Counter[str] = Counter()

    for logical_source, path, expected_source in (
        ("EnglishMono", english_mono_path, "callhome_eng"),
        ("SpanishMono", spanish_mono_path, "callhome_spa"),
    ):
        row_counts: Counter[str] = Counter()
        lexical_counts: Counter[str] = Counter()
        for record in _iter_jsonl(path):
            identity, split, text, lexical_tokens = _validated_callhome_row(record, expected_source)
            row_counts[split] += 1
            lexical_counts[split] += lexical_tokens
            if split != "train":
                continue
            previous = seen_callhome.get(identity)
            if previous is not None:
                if previous != text:
                    raise WordPieceReproducibilityError("conflicting CALLHOME identity/text pair")
                duplicate_counts[f"{logical_source}_exact_identity"] += 1
                continue
            seen_callhome[identity] = text
            examples.append(
                TrainingExample(
                    logical_source=logical_source,
                    identity_sha256=_identity_sha256(identity),
                    text=text,
                    lexical_tokens=lexical_tokens,
                )
            )
        rows_by_split[logical_source] = row_counts
        lexical_by_split[logical_source] = lexical_counts

    bangor_token_text: dict[tuple[str, int], str] = {}
    bangor_row_text: dict[tuple[tuple[str, int], ...], str] = {}
    cscont_component_rows: Counter[str] = Counter()
    cscont_component_lexical: Counter[str] = Counter()

    for record in _iter_jsonl(cscont_train_path):
        if record.get("condition") != "CsCont" or record.get("split") != "train":
            raise WordPieceReproducibilityError("non-training row in CsCont train artifact")
        component = record.get("component")
        source = record.get("source")
        row = record.get("row")
        lexical_tokens = record.get("lexical_tokens")
        if not isinstance(row, dict) or not isinstance(lexical_tokens, int):
            raise WordPieceReproducibilityError("invalid CsCont training record")
        cscont_component_rows[str(component)] += 1
        cscont_component_lexical[str(component)] += lexical_tokens

        if component == "callhome_monolingual_filler":
            identity, nested_split, text, nested_lexical = _validated_callhome_row(row, str(source))
            if nested_split != "train" or nested_lexical != lexical_tokens:
                raise WordPieceReproducibilityError("invalid CsCont CALLHOME filler split/count")
            baseline_text = seen_callhome.get(identity)
            if baseline_text is None:
                raise WordPieceReproducibilityError(
                    "CsCont CALLHOME filler is absent from monolingual train"
                )
            if baseline_text != text:
                raise WordPieceReproducibilityError(
                    "CsCont CALLHOME filler conflicts with baseline text"
                )
            duplicate_counts["CsCont_CALLHOME_already_in_monolingual_union"] += 1
            continue

        if component != "bangor_natural_span" or source != "bangor_cgwords":
            raise WordPieceReproducibilityError("unexpected CsCont training component")
        text = row.get("text")
        tokens = row.get("tokens")
        word_ids = row.get("source_word_ids")
        conversation_id = row.get("conversation_id")
        if not (
            isinstance(text, str)
            and text.strip()
            and "\n" not in text
            and "\r" not in text
            and isinstance(tokens, list)
            and isinstance(word_ids, list)
            and len(tokens) == len(word_ids)
            and all(isinstance(token, str) for token in tokens)
            and all(isinstance(word_id, int) for word_id in word_ids)
            and isinstance(conversation_id, str)
            and " ".join(tokens) == text
            and _lexical_token_count(text) == lexical_tokens
        ):
            raise WordPieceReproducibilityError("invalid Bangor tokenizer-input row")

        token_identities = tuple((conversation_id, word_id) for word_id in word_ids)
        prior_row_text = bangor_row_text.get(token_identities)
        if prior_row_text is not None:
            if prior_row_text != text:
                raise WordPieceReproducibilityError("conflicting duplicate Bangor row identity")
            duplicate_counts["CsCont_Bangor_exact_row_identity"] += 1
            continue
        if any(identity in bangor_token_text for identity in token_identities):
            raise WordPieceReproducibilityError(
                "partial Bangor provenance overlap across tokenizer rows"
            )
        for identity, token in zip(token_identities, tokens, strict=True):
            bangor_token_text[identity] = token
        bangor_row_text[token_identities] = text
        examples.append(
            TrainingExample(
                logical_source="CsContUniqueBangor",
                identity_sha256=_identity_sha256([conversation_id, *word_ids]),
                text=text,
                lexical_tokens=lexical_tokens,
            )
        )

    ordered_hash = hashlib.sha256()
    identity_hash = hashlib.sha256()
    source_rows: Counter[str] = Counter()
    source_lexical: Counter[str] = Counter()
    for example in examples:
        ordered_hash.update(example.text.encode("utf-8"))
        ordered_hash.update(b"\n")
        identity_hash.update(example.identity_sha256.encode("ascii"))
        identity_hash.update(b"\n")
        source_rows[example.logical_source] += 1
        source_lexical[example.logical_source] += example.lexical_tokens

    manifest: dict[str, Any] = {
        "format_version": 1,
        "protocol_id": PROTOCOL_ID,
        "emitted_schema": ["text"],
        "trainer_input_value_type": "str",
        "metadata_fields_emitted": [],
        "logical_source_order": [
            "EnglishMono",
            "SpanishMono",
            "CsContUniqueBangor",
        ],
        "within_source_order": "verified_frozen_jsonl_byte_order",
        "rows_by_split": {
            source: dict(sorted(counts.items())) for source, counts in rows_by_split.items()
        },
        "lexical_tokens_by_split": {
            source: dict(sorted(counts.items())) for source, counts in lexical_by_split.items()
        },
        "cscont_component_rows": dict(sorted(cscont_component_rows.items())),
        "cscont_component_lexical_tokens": dict(sorted(cscont_component_lexical.items())),
        "input_rows_by_logical_source": dict(sorted(source_rows.items())),
        "input_lexical_tokens_by_logical_source": dict(sorted(source_lexical.items())),
        "input_rows": len(examples),
        "input_lexical_tokens": sum(source_lexical.values()),
        "unique_callhome_identities": len(seen_callhome),
        "unique_bangor_token_identities": len(bangor_token_text),
        "unique_bangor_row_identities": len(bangor_row_text),
        "duplicate_counts": dict(sorted(duplicate_counts.items())),
        "ordered_identity_sha256": identity_hash.hexdigest(),
        "trainer_received_lexical_strings_only": True,
        "forbidden_metadata_emitted": False,
    }
    return TrainingExtraction(
        examples=tuple(examples),
        manifest=manifest,
        ordered_input_sha256=ordered_hash.hexdigest(),
    )


def protocol_configuration() -> dict[str, Any]:
    """Return every frozen training parameter in a hashable structure."""
    return {
        "architecture": "WordPiece",
        "vocabulary_size": VOCAB_SIZE,
        "minimum_frequency": MIN_FREQUENCY,
        "limit_alphabet": LIMIT_ALPHABET,
        "initial_alphabet": [],
        "continuing_subword_prefix": CONTINUATION_PREFIX,
        "end_of_word_suffix": None,
        "special_tokens": SPECIAL_TOKEN_IDS,
        "normalization": {
            "sequence": ["NFC", "BertNormalizer"],
            "clean_text": True,
            "handle_chinese_chars": False,
            "lowercase": True,
            "strip_accents": False,
        },
        "pretokenizer": "BertPreTokenizer",
        "protocol_seed": PROTOCOL_SEED,
    }


def configuration_sha256() -> str:
    return sha256_bytes(canonical_json_bytes(protocol_configuration()))


def require_reproducibility_environment(
    environment: Mapping[str, str] | None = None,
) -> None:
    """Reject a process that was not launched with the frozen controls."""
    values = os.environ if environment is None else environment
    if values.get("PYTHONHASHSEED") != str(PROTOCOL_SEED):
        raise WordPieceReproducibilityError(
            f"PYTHONHASHSEED must be {PROTOCOL_SEED} before interpreter startup"
        )
    if values.get("TOKENIZERS_PARALLELISM", "").lower() != "false":
        raise WordPieceReproducibilityError("TOKENIZERS_PARALLELISM must be explicitly false")


def runtime_manifest(
    tokenizers_module: Any,
    backend_build_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Verify and record the complete Python/native tokenizer runtime identity."""
    require_reproducibility_environment()
    if tokenizers_module.__version__ != TOKENIZERS_VERSION:
        raise WordPieceReproducibilityError(f"tokenizers must be {TOKENIZERS_VERSION}")
    package_dir = Path(tokenizers_module.__file__).resolve().parent
    native_extensions = sorted(package_dir.glob("tokenizers.*.so"))
    if len(native_extensions) != 1:
        raise WordPieceReproducibilityError("expected exactly one native tokenizers backend")
    native_sha256 = sha256_file(native_extensions[0])
    if not (
        backend_build_manifest.get("backend_correction_id") == BACKEND_CORRECTION_ID
        and backend_build_manifest.get("tokenizers_version") == TOKENIZERS_VERSION
        and backend_build_manifest.get("native_backend", {}).get("sha256") == native_sha256
    ):
        raise WordPieceReproducibilityError(
            "loaded native backend does not match the corrected build manifest"
        )
    return {
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "python_executable_sha256": sha256_file(Path(sys.executable)),
        "tokenizers": tokenizers_module.__version__,
        "os": platform.platform(),
        "architecture": platform.machine(),
        "rust_backend_version_exposed": None,
        "native_backend": {
            "filename": native_extensions[0].name,
            "sha256": native_sha256,
        },
        "python_hash_seed": os.environ["PYTHONHASHSEED"],
        "tokenizers_parallelism": os.environ["TOKENIZERS_PARALLELISM"],
        "configuration_sha256": configuration_sha256(),
        "backend_correction_id": BACKEND_CORRECTION_ID,
        "backend_build_configuration_sha256": backend_build_manifest["build_configuration_sha256"],
    }


def build_wordpiece(
    texts: Sequence[str],
    backend_build_manifest: Mapping[str, Any],
) -> TokenizerBuild:
    """Train one in-memory tokenizer under the frozen configuration."""
    require_reproducibility_environment()
    import tokenizers
    from tokenizers import (
        Tokenizer,
        decoders,
        models,
        normalizers,
        pre_tokenizers,
        processors,
        trainers,
    )

    if tokenizers.__version__ != TOKENIZERS_VERSION:
        raise WordPieceReproducibilityError(f"tokenizers must be {TOKENIZERS_VERSION}")
    runtime_manifest(tokenizers, backend_build_manifest)
    if any(not isinstance(text, str) or not text for text in texts):
        raise WordPieceReproducibilityError("trainer inputs must be nonempty strings")

    tokenizer = Tokenizer(
        models.WordPiece(
            unk_token="[UNK]",
            max_input_chars_per_word=100,
            continuing_subword_prefix=CONTINUATION_PREFIX,
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
    tokenizer.decoder = decoders.WordPiece(
        prefix=CONTINUATION_PREFIX,
        cleanup=True,
    )
    trainer = trainers.WordPieceTrainer(
        vocab_size=VOCAB_SIZE,
        min_frequency=MIN_FREQUENCY,
        show_progress=False,
        special_tokens=list(SPECIAL_TOKENS),
        limit_alphabet=LIMIT_ALPHABET,
        initial_alphabet=[],
        continuing_subword_prefix=CONTINUATION_PREFIX,
    )
    tokenizer.train_from_iterator(iter(texts), trainer=trainer, length=len(texts))
    actual_special_ids = {token: tokenizer.token_to_id(token) for token in SPECIAL_TOKENS}
    if actual_special_ids != SPECIAL_TOKEN_IDS:
        raise WordPieceReproducibilityError("special-token IDs changed")
    if tokenizer.get_vocab_size(with_added_tokens=True) != VOCAB_SIZE:
        raise WordPieceReproducibilityError("vocabulary size is not exactly 8,000")
    tokenizer.post_processor = processors.TemplateProcessing(
        single="[CLS] $A [SEP]",
        pair="[CLS] $A [SEP] $B:1 [SEP]:1",
        special_tokens=[("[CLS]", 2), ("[SEP]", 3)],
    )

    vocabulary = tokenizer.get_vocab(with_added_tokens=True)
    vocabulary_by_id = tuple(sorted(vocabulary, key=vocabulary.get))
    if vocabulary_by_id[:5] != SPECIAL_TOKENS:
        raise WordPieceReproducibilityError("special-token vocabulary prefix changed")
    files = {
        "tokenizer.json": (tokenizer.to_str(pretty=False) + "\n").encode("utf-8"),
        "vocab.txt": ("\n".join(vocabulary_by_id) + "\n").encode("utf-8"),
        "tokenizer_config.json": canonical_json_bytes(
            {
                "clean_up_tokenization_spaces": True,
                "cls_token": "[CLS]",
                "do_lower_case": True,
                "handle_chinese_chars": False,
                "mask_token": "[MASK]",
                "model_max_length": 512,
                "pad_token": "[PAD]",
                "sep_token": "[SEP]",
                "strip_accents": False,
                "tokenizer_class": "BertTokenizerFast",
                "unk_token": "[UNK]",
            }
        ),
    }
    return TokenizerBuild(
        files=files,
        file_sha256={
            filename: sha256_bytes(content) for filename, content in sorted(files.items())
        },
        vocabulary_by_id=vocabulary_by_id,
    )


def compare_builds(first: TokenizerBuild, second: TokenizerBuild) -> BuildComparison:
    """Apply Option A's strict byte-reproducibility acceptance rule."""
    first_tokens = set(first.vocabulary_by_id)
    second_tokens = set(second.vocabulary_by_id)
    return BuildComparison(
        identical_vocabulary=first_tokens == second_tokens,
        identical_token_ids=first.vocabulary_by_id == second.vocabulary_by_id,
        identical_vocab_txt=first.files["vocab.txt"] == second.files["vocab.txt"],
        identical_tokenizer_json=(first.files["tokenizer.json"] == second.files["tokenizer.json"]),
        identical_checksums=first.file_sha256 == second.file_sha256,
    )
