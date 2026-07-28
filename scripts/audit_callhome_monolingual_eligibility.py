#!/usr/bin/env python3
"""Aggregate-only CALLHOME annotation-eligibility audit.

The command is fixed to the approved repository-local CALLHOME populations and
frozen source pools. It is read-only, writes no row-level sidecar or corpus
artifact, and refuses to run without explicit ``--execute`` authorization.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

from cslm.data.callhome_chat import (
    CallhomeTranscript,
    StrictChatReaderError,
    read_chat_transcript,
)
from cslm.data.callhome_monolingual_eligibility import (
    ERROR_DUPLICATE_RECONCILIATION,
    ERROR_PROVENANCE_DISAGREEMENT,
    ERROR_RECONCILIATION,
    ERROR_ROUTING_INVARIANT,
    ERROR_SOURCE_DISAGREEMENT,
    ERROR_SPLIT_DISAGREEMENT,
    ERROR_UNKNOWN_LANGUAGE_CONTROL,
    RECOGNIZED_LANGUAGE_CODES,
    CallhomeEligibilityError,
    audit_callhome_monolingual_eligibility,
    evaluate_utterance_annotation_eligibility,
    reconcile_frozen_rows,
    summarize_reconciled_eligibility,
)
from cslm.data.callhome_training_rows import (
    ERROR_LANGUAGE_CONFLICT,
    ERROR_UNRESOLVED_CHAT_CONTROL,
    ERROR_UNSUPPORTED_SOURCE,
    CallhomeTrainingRow,
    CallhomeTrainingRowsError,
    rows_from_transcript,
)
from cslm.utils.paths import project_root

EXPECTED_ENGLISH_FILES = 176
EXPECTED_SPANISH_FILES = 140
EXPECTED_FROZEN_CHECKSUMS_SHA256 = (
    "e3571a6c9158a5cb53dd3088a371306ee18a568098ed67f51e25e7cb816bb328"
)
_FIXED_FAILURE = "CALLHOME monolingual-eligibility audit failed"
_FIXED_CENSUS_FAILURE = "CALLHOME unknown-language-control census failed"
_FIXED_UNCLASSIFIED_DIAGNOSTIC = (
    '{"error_category":"unclassified_internal_failure",'
    '"stage":"summary_calculation"}'
)
_DIAGNOSTIC_STAGES = (
    "transcript_reading",
    "annotation_classification",
    "frozen_row_reconciliation",
    "summary_calculation",
)
_DIAGNOSTIC_CATEGORIES = (
    "reader_failure",
    "source_population_mismatch",
    "unknown_or_malformed_language_control",
    "source_language_conflict",
    "unsupported_annotation_structure",
    "missing_reconciliation",
    "duplicate_reconciliation",
    "source_disagreement",
    "split_disagreement",
    "provenance_disagreement",
    "routing_invariant",
    "frozen_pool_verification_failure",
    "category_reconciliation_failure",
    "split_reconciliation_failure",
    "aggregate_calculation_failure",
    "unclassified_internal_failure",
    "no_failure",
)
_CENSUS_CATEGORIES = (
    "unknown_code",
    "malformed_payload",
    "unsupported_multi_value_form",
    "unsupported_delimiter_form",
    "unsupported_empty_form",
    "other_sanitized_structure",
)
_CENSUS_SHAPES = (
    "empty",
    "single_alpha_length_three",
    "single_alpha_other_length",
    "comma_separated_alpha",
    "whitespace_separated_alpha",
    "punctuation_present",
    "other",
)
_CENSUS_SPLITS = ("train", "validation", "test")
_CENSUS_SOURCE_NAMES = {
    "callhome_eng": "english",
    "callhome_spa": "spanish",
}
_CENSUS_ANY_PRECODE = re.compile(r"\[\s*-[^\[\]]*\]")
_CENSUS_STRICT_PRECODE = re.compile(r"\[-[ \t]+([^ \t\[\]][^\[\]]*?)\]")
_CENSUS_LANGUAGE_LIST = re.compile(
    r"[A-Za-z]{3}(?:[ \t]*,[ \t]*[A-Za-z]{3})*"
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Required explicit opt-in for a later real local audit.",
    )
    parser.add_argument(
        "--diagnose-failure",
        action="store_true",
        help="Emit only a fixed privacy-safe stage and error category.",
    )
    parser.add_argument(
        "--census-unknown-controls",
        action="store_true",
        help="Emit only aggregate sanitized structures for unsupported precodes.",
    )
    return parser.parse_args()


def _direct_cha_files(directory: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in directory.iterdir()
            if path.is_file() and path.suffix == ".cha"
        ),
        key=lambda path: path.name,
    )


def _load_frozen_rows(path: Path) -> list[CallhomeTrainingRow]:
    rows: list[CallhomeTrainingRow] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            rows.append(CallhomeTrainingRow(**json.loads(line)))
    return rows


def _load_verified_frozen_rows(pool_root: Path) -> list[CallhomeTrainingRow]:
    """Load only the exact frozen pool whose checksum record was reviewed."""
    checksum_path = pool_root / "checksums.json"
    checksum_bytes = checksum_path.read_bytes()
    if hashlib.sha256(checksum_bytes).hexdigest() != EXPECTED_FROZEN_CHECKSUMS_SHA256:
        raise ValueError(_FIXED_FAILURE)
    checksums = json.loads(checksum_bytes)
    expected_names = {
        "english_rows.jsonl",
        "manifest.json",
        "spanish_rows.jsonl",
    }
    expected_pool_names = {*expected_names, "checksums.json"}
    pool_entries = tuple(pool_root.iterdir())
    if (
        {path.name for path in pool_entries} != expected_pool_names
        or any(not path.is_file() or path.is_symlink() for path in pool_entries)
    ):
        raise ValueError(_FIXED_FAILURE)
    if set(checksums) != expected_names:
        raise ValueError(_FIXED_FAILURE)
    for name in sorted(expected_names):
        if hashlib.sha256((pool_root / name).read_bytes()).hexdigest() != checksums[name]:
            raise ValueError(_FIXED_FAILURE)
    return [
        *_load_frozen_rows(pool_root / "english_rows.jsonl"),
        *_load_frozen_rows(pool_root / "spanish_rows.jsonl"),
    ]


class _FixedDiagnosticFailure(Exception):
    """Internal fixed-category failure carrying no corpus-derived value."""

    def __init__(self, category: str) -> None:
        if category not in _DIAGNOSTIC_CATEGORIES:
            raise ValueError("unknown diagnostic category")
        super().__init__(category)
        self.category = category


def _fixed_message_matches(error: Exception, expected: str) -> bool:
    """Match only an exact tracked fixed message; never serialize the exception."""
    return error.args == (expected,)


def _diagnostic_category(stage: str, error: Exception) -> str:
    """Map a stage-local failure directly to one fixed privacy-safe category."""
    if stage not in _DIAGNOSTIC_STAGES:
        return "unclassified_internal_failure"
    if isinstance(error, _FixedDiagnosticFailure):
        return error.category

    if stage == "transcript_reading":
        if isinstance(error, (StrictChatReaderError, OSError)):
            return "reader_failure"
        return "unclassified_internal_failure"

    if stage == "annotation_classification":
        if isinstance(error, CallhomeEligibilityError):
            if _fixed_message_matches(error, ERROR_UNKNOWN_LANGUAGE_CONTROL):
                return "unknown_or_malformed_language_control"
            if _fixed_message_matches(error, ERROR_SOURCE_DISAGREEMENT):
                return "source_disagreement"
        if isinstance(error, CallhomeTrainingRowsError):
            if _fixed_message_matches(error, ERROR_LANGUAGE_CONFLICT):
                return "source_language_conflict"
            if _fixed_message_matches(error, ERROR_UNRESOLVED_CHAT_CONTROL):
                return "unsupported_annotation_structure"
            if _fixed_message_matches(error, ERROR_UNSUPPORTED_SOURCE):
                return "source_disagreement"
        return "unclassified_internal_failure"

    if stage == "frozen_row_reconciliation":
        if isinstance(error, CallhomeEligibilityError):
            fixed_categories = {
                ERROR_RECONCILIATION: "missing_reconciliation",
                ERROR_DUPLICATE_RECONCILIATION: "duplicate_reconciliation",
                ERROR_SOURCE_DISAGREEMENT: "source_disagreement",
                ERROR_SPLIT_DISAGREEMENT: "split_disagreement",
                ERROR_PROVENANCE_DISAGREEMENT: "provenance_disagreement",
                ERROR_ROUTING_INVARIANT: "routing_invariant",
            }
            for fixed_message, category in fixed_categories.items():
                if _fixed_message_matches(error, fixed_message):
                    return category
        if isinstance(
            error,
            (CallhomeTrainingRowsError, OSError, ValueError, TypeError, json.JSONDecodeError),
        ):
            return "frozen_pool_verification_failure"
        return "unclassified_internal_failure"

    if isinstance(error, CallhomeEligibilityError):
        if _fixed_message_matches(error, ERROR_SPLIT_DISAGREEMENT):
            return "split_reconciliation_failure"
        if any(
            _fixed_message_matches(error, fixed_message)
            for fixed_message in (
                ERROR_SOURCE_DISAGREEMENT,
                ERROR_ROUTING_INVARIANT,
            )
        ):
            return "category_reconciliation_failure"
    if isinstance(error, (ArithmeticError, TypeError, ValueError)):
        return "aggregate_calculation_failure"
    return "unclassified_internal_failure"


def _diagnostic_payload(stage: str, error: Exception | None) -> dict[str, str]:
    """Return only allowed labels, never an exception message or corpus value."""
    if stage not in _DIAGNOSTIC_STAGES:
        stage = "summary_calculation"
        category = "unclassified_internal_failure"
    else:
        category = "no_failure" if error is None else _diagnostic_category(stage, error)
    if category not in _DIAGNOSTIC_CATEGORIES:
        category = "unclassified_internal_failure"
    return {"error_category": category, "stage": stage}


def _print_diagnostic(stage: str, error: Exception | None) -> bool:
    """Emit one safe JSON object; return false if fallback output was required."""
    try:
        serialized = json.dumps(
            _diagnostic_payload(stage, error),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        print(serialized)
    except Exception:
        try:
            print(_FIXED_UNCLASSIFIED_DIAGNOSTIC)
        except Exception:
            raise SystemExit(_FIXED_UNCLASSIFIED_DIAGNOSTIC) from None
        return False
    return True


def _classify_annotations(
    transcripts_by_source: dict[str, list[CallhomeTranscript]],
) -> None:
    """Exercise the exact projection/classification path without retaining output."""
    for source in ("callhome_eng", "callhome_spa"):
        for transcript in transcripts_by_source[source]:
            projected_rows, _ = rows_from_transcript(transcript, source=source)
            utterances_by_turn = {
                utterance.turn_index: utterance for utterance in transcript.utterances
            }
            for row in projected_rows:
                utterance = utterances_by_turn.get(row.turn_index)
                if utterance is None:
                    raise CallhomeEligibilityError(ERROR_RECONCILIATION)
                evaluate_utterance_annotation_eligibility(
                    utterance,
                    source=source,
                )


def _run_privacy_safe_diagnostic(raw_root: Path, pool_root: Path) -> int:
    """Run four fixed stages and emit only the first safe failure classification."""
    stage = "transcript_reading"
    try:
        english_paths = _direct_cha_files(raw_root / "eng")
        spanish_paths = _direct_cha_files(raw_root / "spa")
        if (
            len(english_paths) != EXPECTED_ENGLISH_FILES
            or len(spanish_paths) != EXPECTED_SPANISH_FILES
        ):
            raise _FixedDiagnosticFailure("source_population_mismatch")
        transcripts_by_source = {
            "callhome_eng": [read_chat_transcript(path) for path in english_paths],
            "callhome_spa": [read_chat_transcript(path) for path in spanish_paths],
        }
    except Exception as error:
        _print_diagnostic(stage, error)
        return 1

    stage = "annotation_classification"
    try:
        _classify_annotations(transcripts_by_source)
    except Exception as error:
        _print_diagnostic(stage, error)
        return 1

    stage = "frozen_row_reconciliation"
    try:
        frozen_rows = _load_verified_frozen_rows(pool_root)
        canonical_splits_by_row_id = {
            row.row_id: row.split for row in frozen_rows
        }
        reconciled = reconcile_frozen_rows(
            transcripts_by_source,
            frozen_rows,
            canonical_splits_by_row_id=canonical_splits_by_row_id,
        )
    except Exception as error:
        _print_diagnostic(stage, error)
        return 1

    stage = "summary_calculation"
    try:
        summarize_reconciled_eligibility(reconciled)
    except Exception as error:
        _print_diagnostic(stage, error)
        return 1
    return 0 if _print_diagnostic(stage, None) else 1


def _census_shape(payload: str) -> str:
    """Reduce a payload to one broad, non-reversible structural bucket."""
    stripped = payload.strip()
    if not stripped:
        return "empty"
    if stripped.isalpha():
        if len(stripped) == 3:
            return "single_alpha_length_three"
        return "single_alpha_other_length"
    comma_parts = tuple(part.strip() for part in stripped.split(","))
    if len(comma_parts) > 1 and all(part.isalpha() for part in comma_parts):
        return "comma_separated_alpha"
    whitespace_parts = tuple(stripped.split())
    if len(whitespace_parts) > 1 and all(
        part.isalpha() for part in whitespace_parts
    ):
        return "whitespace_separated_alpha"
    if any(
        not character.isalnum()
        and not character.isspace()
        and character != ","
        for character in stripped
    ):
        return "punctuation_present"
    return "other"


def _sanitize_census_control(control: str) -> tuple[str, str] | None:
    """Classify one precode structurally, returning no payload-derived value."""
    candidate = _CENSUS_ANY_PRECODE.fullmatch(control)
    if candidate is None:
        return ("other_sanitized_structure", "other")

    matched = _CENSUS_STRICT_PRECODE.fullmatch(control)
    if matched is None:
        inner = control[1:-1]
        stripped_inner = inner.strip()
        payload = stripped_inner[1:].strip() if stripped_inner.startswith("-") else ""
        shape = _census_shape(payload)
        if shape == "empty":
            return ("unsupported_empty_form", shape)
        if not inner.startswith("-"):
            return ("unsupported_delimiter_form", shape)
        if len(inner) > 1 and not inner[1].isspace():
            return ("unsupported_delimiter_form", shape)
        if shape == "whitespace_separated_alpha":
            return ("unsupported_multi_value_form", shape)
        if shape == "punctuation_present":
            return ("unsupported_delimiter_form", shape)
        return ("malformed_payload", shape)

    payload = matched.group(1).strip().lower()
    shape = _census_shape(payload)
    if payload in {"?", "und"}:
        return None
    if _CENSUS_LANGUAGE_LIST.fullmatch(payload):
        languages = tuple(part.strip() for part in payload.split(","))
        if len(languages) != len(set(languages)):
            return ("unsupported_multi_value_form", shape)
        if any(
            language not in RECOGNIZED_LANGUAGE_CODES
            for language in languages
        ):
            return ("unknown_code", shape)
        return None
    if shape == "empty":
        return ("unsupported_empty_form", shape)
    if shape == "whitespace_separated_alpha":
        return ("unsupported_multi_value_form", shape)
    if shape in {"comma_separated_alpha", "punctuation_present"} or "," in payload:
        return ("unsupported_delimiter_form", shape)
    if shape in {"single_alpha_length_three", "single_alpha_other_length"}:
        return ("malformed_payload", shape)
    return ("other_sanitized_structure", shape)


def _sanitized_controls_in_text(text: str) -> tuple[tuple[str, str], ...]:
    """Return only fixed category/shape pairs for controls rejected by the core."""
    structures: list[tuple[str, str]] = []
    for candidate in _CENSUS_ANY_PRECODE.finditer(text):
        sanitized = _sanitize_census_control(candidate.group(0))
        if sanitized is not None:
            structures.append(sanitized)
    return tuple(structures)


def _empty_census_bucket() -> dict[str, object]:
    return {
        "occurrences": 0,
        "affected_utterances": 0,
        "affected_conversations": 0,
        "utterances_with_multiple_controls": 0,
        "categories": {category: 0 for category in _CENSUS_CATEGORIES},
        "shapes": {shape: 0 for shape in _CENSUS_SHAPES},
        "splits": {
            split: {
                "occurrences": 0,
                "affected_utterances": 0,
                "affected_conversations": 0,
            }
            for split in _CENSUS_SPLITS
        },
    }


def _summarize_census_records(
    records: list[tuple[str, str, str, tuple[tuple[str, str], ...]]],
) -> dict[str, object]:
    """Aggregate in-memory records without serializing their opaque identity."""
    source_buckets = {
        source_name: _empty_census_bucket()
        for source_name in ("english", "spanish")
    }
    combined = _empty_census_bucket()
    source_conversations: dict[str, set[str]] = defaultdict(set)
    source_split_conversations: dict[tuple[str, str], set[str]] = defaultdict(set)
    combined_conversations: set[tuple[str, str]] = set()
    combined_split_conversations: dict[str, set[tuple[str, str]]] = defaultdict(set)
    category_sources: dict[str, set[str]] = defaultdict(set)

    for source_name, split, conversation_token, structures in records:
        if source_name not in source_buckets or split not in _CENSUS_SPLITS:
            raise ValueError(_FIXED_CENSUS_FAILURE)
        if not structures:
            raise ValueError(_FIXED_CENSUS_FAILURE)
        bucket = source_buckets[source_name]
        occurrence_count = len(structures)
        bucket["occurrences"] = int(bucket["occurrences"]) + occurrence_count
        bucket["affected_utterances"] = int(bucket["affected_utterances"]) + 1
        combined["occurrences"] = int(combined["occurrences"]) + occurrence_count
        combined["affected_utterances"] = int(combined["affected_utterances"]) + 1
        if occurrence_count > 1:
            bucket["utterances_with_multiple_controls"] = (
                int(bucket["utterances_with_multiple_controls"]) + 1
            )
            combined["utterances_with_multiple_controls"] = (
                int(combined["utterances_with_multiple_controls"]) + 1
            )

        source_conversations[source_name].add(conversation_token)
        source_split_conversations[(source_name, split)].add(conversation_token)
        combined_conversations.add((source_name, conversation_token))
        combined_split_conversations[split].add((source_name, conversation_token))

        source_split = bucket["splits"][split]
        combined_split = combined["splits"][split]
        source_split["occurrences"] = (
            int(source_split["occurrences"]) + occurrence_count
        )
        source_split["affected_utterances"] = (
            int(source_split["affected_utterances"]) + 1
        )
        combined_split["occurrences"] = (
            int(combined_split["occurrences"]) + occurrence_count
        )
        combined_split["affected_utterances"] = (
            int(combined_split["affected_utterances"]) + 1
        )

        for category, shape in structures:
            if category not in _CENSUS_CATEGORIES or shape not in _CENSUS_SHAPES:
                raise ValueError(_FIXED_CENSUS_FAILURE)
            bucket["categories"][category] = int(
                bucket["categories"][category]
            ) + 1
            bucket["shapes"][shape] = int(bucket["shapes"][shape]) + 1
            combined["categories"][category] = int(
                combined["categories"][category]
            ) + 1
            combined["shapes"][shape] = int(combined["shapes"][shape]) + 1
            category_sources[category].add(source_name)

    for source_name, bucket in source_buckets.items():
        bucket["affected_conversations"] = len(source_conversations[source_name])
        for split in _CENSUS_SPLITS:
            bucket["splits"][split]["affected_conversations"] = len(
                source_split_conversations[(source_name, split)]
            )
    combined["affected_conversations"] = len(combined_conversations)
    for split in _CENSUS_SPLITS:
        combined["splits"][split]["affected_conversations"] = len(
            combined_split_conversations[split]
        )

    return {
        "combined": combined,
        "sources": source_buckets,
        "category_occurs_in_both_sources": {
            category: len(category_sources[category]) == 2
            for category in _CENSUS_CATEGORIES
        },
        "more_than_one_unknown_control_in_affected_utterance": (
            int(combined["utterances_with_multiple_controls"]) > 0
        ),
    }


def _run_unknown_control_census(
    raw_root: Path,
    pool_root: Path,
) -> dict[str, object]:
    """Scan approved rows and return only aggregate sanitized control structure."""
    english_paths = _direct_cha_files(raw_root / "eng")
    spanish_paths = _direct_cha_files(raw_root / "spa")
    if (
        len(english_paths) != EXPECTED_ENGLISH_FILES
        or len(spanish_paths) != EXPECTED_SPANISH_FILES
    ):
        raise ValueError(_FIXED_CENSUS_FAILURE)
    transcripts_by_source = {
        "callhome_eng": [read_chat_transcript(path) for path in english_paths],
        "callhome_spa": [read_chat_transcript(path) for path in spanish_paths],
    }
    frozen_rows = _load_verified_frozen_rows(pool_root)
    split_by_row_id: dict[str, str] = {}
    for row in frozen_rows:
        if row.row_id in split_by_row_id or row.split not in _CENSUS_SPLITS:
            raise ValueError(_FIXED_CENSUS_FAILURE)
        split_by_row_id[row.row_id] = row.split

    records: list[tuple[str, str, str, tuple[tuple[str, str], ...]]] = []
    for source, transcripts in transcripts_by_source.items():
        source_name = _CENSUS_SOURCE_NAMES[source]
        for transcript in transcripts:
            projected_rows, _ = rows_from_transcript(transcript, source=source)
            utterances_by_turn = {
                utterance.turn_index: utterance for utterance in transcript.utterances
            }
            for row in projected_rows:
                utterance = utterances_by_turn.get(row.turn_index)
                split = split_by_row_id.get(row.row_id)
                if utterance is None or split is None:
                    raise ValueError(_FIXED_CENSUS_FAILURE)
                structures = _sanitized_controls_in_text(
                    utterance.raw_main_tier_text
                )
                if structures:
                    records.append(
                        (
                            source_name,
                            split,
                            row.conversation_ref,
                            structures,
                        )
                    )
    return _summarize_census_records(records)


def main() -> int:
    args = _parse_args()
    if not args.execute:
        raise SystemExit(
            "Refusing to process real CALLHOME without the explicit --execute opt-in."
        )

    if args.diagnose_failure and args.census_unknown_controls:
        raise SystemExit("Choose exactly one privacy-safe diagnostic mode.")
    if args.diagnose_failure:
        try:
            root = project_root()
            raw_root = root / "data" / "raw" / "callhome"
            pool_root = root / "data" / "processed" / "callhome" / "pools"
        except Exception as error:
            _print_diagnostic("transcript_reading", error)
            return 1
        return _run_privacy_safe_diagnostic(raw_root, pool_root)
    if args.census_unknown_controls:
        try:
            root = project_root()
            raw_root = root / "data" / "raw" / "callhome"
            pool_root = root / "data" / "processed" / "callhome" / "pools"
            census = _run_unknown_control_census(raw_root, pool_root)
            print(
                json.dumps(
                    census,
                    ensure_ascii=True,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )
        except Exception:
            raise SystemExit(_FIXED_CENSUS_FAILURE) from None
        return 0

    try:
        root = project_root()
        raw_root = root / "data" / "raw" / "callhome"
        pool_root = root / "data" / "processed" / "callhome" / "pools"
        english_paths = _direct_cha_files(raw_root / "eng")
        spanish_paths = _direct_cha_files(raw_root / "spa")
        if (
            len(english_paths) != EXPECTED_ENGLISH_FILES
            or len(spanish_paths) != EXPECTED_SPANISH_FILES
        ):
            raise ValueError(_FIXED_FAILURE)
        transcripts_by_source = {
            "callhome_eng": [
                read_chat_transcript(path) for path in english_paths
            ],
            "callhome_spa": [
                read_chat_transcript(path) for path in spanish_paths
            ],
        }
        frozen_rows = _load_verified_frozen_rows(pool_root)
        canonical_splits_by_row_id = {
            row.row_id: row.split for row in frozen_rows
        }
        summary = audit_callhome_monolingual_eligibility(
            transcripts_by_source,
            frozen_rows,
            canonical_splits_by_row_id=canonical_splits_by_row_id,
        )
        print(
            json.dumps(
                summary,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    except Exception:
        raise SystemExit(_FIXED_FAILURE) from None
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
