"""Deterministic lexical-stage selection for small CALLHOME pilot conditions.

This module consumes only in-memory rows already reconciled by the approved
annotation-based eligibility implementation. It does not read raw CALLHOME,
train a tokenizer, construct model sequences, or route CALLHOME into CsCont.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from cslm.data.callhome_monolingual_eligibility import (
    CALLHOME_CODE_SWITCHED_EVIDENCE_ROLES,
    CSCONT_ENGLISH_MONOLINGUAL_FILLER_ROLE,
    CSCONT_SPANISH_MONOLINGUAL_FILLER_ROLE,
    ELIGIBLE_ANNOTATION_CLEAN,
    ENGLISH_MONO_ROLE,
    EXCLUSION_REASON_ORDER,
    MONOCONT_ENGLISH_ROLE,
    MONOCONT_SPANISH_ROLE,
    SOURCE_ORDER,
    SPANISH_MONO_ROLE,
    SPLIT_ORDER,
    CallhomeEligibilityError,
    ReconciledEligibility,
    _approximate_lexical_tokens,
    condition_candidates,
    qualifies_as_genuine_code_switched_evidence,
    validate_permitted_roles,
)
from cslm.data.callhome_training_rows import CallhomeTrainingRow

DEFAULT_SEED = 1729
FORMAT_VERSION = 1
ELIGIBILITY_POLICY_ID = "callhome_annotation_clean_v1"
SELECTION_RULE_ID = "seeded_sha256_whole_row_greedy_under_quota_v1"

ENGLISH_MONO = "EnglishMono"
SPANISH_MONO = "SpanishMono"
MONOCONT_ENGLISH = "MonoCont-English"
MONOCONT_SPANISH = "MonoCont-Spanish"

assert ENGLISH_MONO == ENGLISH_MONO_ROLE
assert SPANISH_MONO == SPANISH_MONO_ROLE
assert MONOCONT_ENGLISH == MONOCONT_ENGLISH_ROLE
assert MONOCONT_SPANISH == MONOCONT_SPANISH_ROLE

CONDITION_ORDER: tuple[str, ...] = (
    ENGLISH_MONO,
    SPANISH_MONO,
    MONOCONT_ENGLISH,
    MONOCONT_SPANISH,
)

CONDITION_SOURCE: dict[str, str] = {
    ENGLISH_MONO: "callhome_eng",
    SPANISH_MONO: "callhome_spa",
    MONOCONT_ENGLISH: "callhome_eng",
    MONOCONT_SPANISH: "callhome_spa",
}

CONDITION_FILENAME: dict[str, str] = {
    ENGLISH_MONO: "english_mono_rows.jsonl",
    SPANISH_MONO: "spanish_mono_rows.jsonl",
    MONOCONT_ENGLISH: "monocont_english_rows.jsonl",
    MONOCONT_SPANISH: "monocont_spanish_rows.jsonl",
}

PROVISIONAL_TARGETS: dict[str, dict[str, int]] = {
    ENGLISH_MONO: {"train": 90_000, "validation": 5_000, "test": 5_000},
    SPANISH_MONO: {"train": 90_000, "validation": 5_000, "test": 5_000},
    MONOCONT_ENGLISH: {"train": 45_000, "validation": 2_500, "test": 2_500},
    MONOCONT_SPANISH: {"train": 45_000, "validation": 2_500, "test": 2_500},
}

_MONO_BY_SOURCE: dict[str, str] = {
    "callhome_eng": ENGLISH_MONO,
    "callhome_spa": SPANISH_MONO,
}
_MONOCONT_BY_SOURCE: dict[str, str] = {
    "callhome_eng": MONOCONT_ENGLISH,
    "callhome_spa": MONOCONT_SPANISH,
}
_REQUIRED_LOCAL_ROLES: dict[str, frozenset[str]] = {
    "callhome_eng": frozenset({ENGLISH_MONO, MONOCONT_ENGLISH}),
    "callhome_spa": frozenset({SPANISH_MONO, MONOCONT_SPANISH}),
}
_RECOGNIZED_FILLER_ROLE: dict[str, str] = {
    "callhome_eng": CSCONT_ENGLISH_MONOLINGUAL_FILLER_ROLE,
    "callhome_spa": CSCONT_SPANISH_MONOLINGUAL_FILLER_ROLE,
}
_ARTIFACT_NAMES = frozenset(
    {*CONDITION_FILENAME.values(), "manifest.json", "checksums.json"}
)

ERROR_INVALID_INPUT = "invalid CALLHOME pilot-condition input"
ERROR_QUOTA = "CALLHOME pilot-condition lexical quota cannot be satisfied"
ERROR_OUTPUT_EXISTS = "CALLHOME pilot-condition output already exists"


class CallhomePilotConditionError(Exception):
    """Fixed-category failure for provisional condition construction."""


@dataclass(frozen=True)
class PilotConditionBuild:
    """Selected row membership and aggregate manifest, before publication."""

    rows_by_condition: Mapping[str, tuple[CallhomeTrainingRow, ...]]
    manifest: Mapping[str, object]


def lexical_token_count(text: str) -> int:
    """Use the exact lexical-token definition from the eligibility audit."""
    return _approximate_lexical_tokens(text)


def quota_tolerance(target: int) -> int:
    """Return the largest integral shortfall allowed by the reviewed rule."""
    if isinstance(target, bool) or not isinstance(target, int) or target <= 0:
        raise CallhomePilotConditionError(ERROR_INVALID_INPUT)
    return max(1, math.floor(target * 0.001))


def _validated_targets(
    targets: Mapping[str, Mapping[str, int]],
) -> dict[str, dict[str, int]]:
    if set(targets) != set(CONDITION_ORDER):
        raise CallhomePilotConditionError(ERROR_INVALID_INPUT)
    validated: dict[str, dict[str, int]] = {}
    for condition in CONDITION_ORDER:
        split_targets = targets[condition]
        if set(split_targets) != set(SPLIT_ORDER):
            raise CallhomePilotConditionError(ERROR_INVALID_INPUT)
        validated[condition] = {}
        for split in SPLIT_ORDER:
            target = split_targets[split]
            if isinstance(target, bool) or not isinstance(target, int) or target <= 0:
                raise CallhomePilotConditionError(ERROR_INVALID_INPUT)
            validated[condition][split] = target
    for source in SOURCE_ORDER:
        mono = _MONO_BY_SOURCE[source]
        monocont = _MONOCONT_BY_SOURCE[source]
        if any(
            validated[monocont][split] > validated[mono][split]
            for split in SPLIT_ORDER
        ):
            raise CallhomePilotConditionError(ERROR_INVALID_INPUT)
    return validated


def _selection_key(
    row: CallhomeTrainingRow,
    *,
    seed: int,
    source: str,
    split: str,
) -> tuple[str, str]:
    digest = hashlib.sha256(
        f"{seed}\0{source}\0{split}\0{row.row_id}".encode("utf-8")
    ).hexdigest()
    return digest, row.row_id


def _select_under_target(
    ordered_rows: Iterable[CallhomeTrainingRow],
    *,
    target: int,
    required_rows: Iterable[CallhomeTrainingRow] = (),
) -> tuple[tuple[CallhomeTrainingRow, ...], int]:
    ordered = tuple(ordered_rows)
    required = tuple(required_rows)
    required_ids = {row.row_id for row in required}
    if len(required_ids) != len(required):
        raise CallhomePilotConditionError(ERROR_INVALID_INPUT)
    ordered_ids = {row.row_id for row in ordered}
    if not required_ids <= ordered_ids:
        raise CallhomePilotConditionError(ERROR_INVALID_INPUT)

    realized = sum(lexical_token_count(row.text) for row in required)
    if realized > target:
        raise CallhomePilotConditionError(ERROR_QUOTA)

    selected_ids = set(required_ids)
    for row in ordered:
        if row.row_id in selected_ids:
            continue
        row_tokens = lexical_token_count(row.text)
        if row_tokens <= 0:
            raise CallhomePilotConditionError(ERROR_INVALID_INPUT)
        if realized + row_tokens <= target:
            selected_ids.add(row.row_id)
            realized += row_tokens
        if realized == target:
            break

    shortfall = target - realized
    if shortfall > quota_tolerance(target):
        raise CallhomePilotConditionError(ERROR_QUOTA)
    return tuple(row for row in ordered if row.row_id in selected_ids), realized


def _materialize_eligible_inventories(
    reconciled: Iterable[ReconciledEligibility],
) -> tuple[
    dict[tuple[str, str], list[CallhomeTrainingRow]],
    dict[str, object],
]:
    inventories: dict[tuple[str, str], list[CallhomeTrainingRow]] = {
        (source, split): [] for source in SOURCE_ORDER for split in SPLIT_ORDER
    }
    seen_row_ids: set[str] = set()
    eligible_rows: Counter[str] = Counter()
    eligible_tokens: Counter[str] = Counter()
    excluded_rows: dict[str, Counter[str]] = {
        source: Counter() for source in SOURCE_ORDER
    }
    filler_candidate_rows: Counter[str] = Counter()
    code_switched_evidence_rows: Counter[str] = Counter()
    splits_by_conversation: dict[tuple[str, str], set[str]] = {}

    for item in reconciled:
        row = item.row
        if (
            row.row_id in seen_row_ids
            or row.source not in SOURCE_ORDER
            or row.split not in SPLIT_ORDER
            or lexical_token_count(row.text) <= 0
        ):
            raise CallhomePilotConditionError(ERROR_INVALID_INPUT)
        seen_row_ids.add(row.row_id)
        splits_by_conversation.setdefault(
            (row.source, row.conversation_ref),
            set(),
        ).add(row.split)
        candidates = condition_candidates(source=row.source, decision=item.decision)
        try:
            validate_permitted_roles(
                source=row.source,
                decision=item.decision,
                roles=candidates,
            )
        except CallhomeEligibilityError as error:
            raise CallhomePilotConditionError(ERROR_INVALID_INPUT) from error
        is_code_switched_evidence = qualifies_as_genuine_code_switched_evidence(
            source=row.source,
            decision=item.decision,
        )
        if (
            is_code_switched_evidence
            or set(candidates) & CALLHOME_CODE_SWITCHED_EVIDENCE_ROLES
        ):
            raise CallhomePilotConditionError(ERROR_INVALID_INPUT)
        if item.decision.is_eligible:
            if (
                item.decision.category != ELIGIBLE_ANNOTATION_CLEAN
                or not _REQUIRED_LOCAL_ROLES[row.source] <= set(candidates)
                or _RECOGNIZED_FILLER_ROLE[row.source] not in candidates
            ):
                raise CallhomePilotConditionError(ERROR_INVALID_INPUT)
            inventories[(row.source, row.split)].append(row)
            eligible_rows[row.source] += 1
            eligible_tokens[row.source] += lexical_token_count(row.text)
            filler_candidate_rows[row.source] += 1
            code_switched_evidence_rows[row.source] += int(
                is_code_switched_evidence
            )
        else:
            if candidates:
                raise CallhomePilotConditionError(ERROR_INVALID_INPUT)
            reason = item.decision.exclusion_reason
            if reason not in EXCLUSION_REASON_ORDER:
                raise CallhomePilotConditionError(ERROR_INVALID_INPUT)
            assert reason is not None
            excluded_rows[row.source][reason] += 1

    if not seen_row_ids:
        raise CallhomePilotConditionError(ERROR_INVALID_INPUT)
    if any(len(splits) != 1 for splits in splits_by_conversation.values()):
        raise CallhomePilotConditionError(ERROR_INVALID_INPUT)

    summary = {
        "eligible_rows": {
            source: eligible_rows[source] for source in SOURCE_ORDER
        },
        "eligible_lexical_tokens": {
            source: eligible_tokens[source] for source in SOURCE_ORDER
        },
        "future_cscont_monolingual_filler_candidate_rows": {
            source: filler_candidate_rows[source] for source in SOURCE_ORDER
        },
        "genuine_code_switched_evidence_rows": {
            source: code_switched_evidence_rows[source] for source in SOURCE_ORDER
        },
        "future_cscont_monolingual_filler_selection_performed": False,
        "future_cscont_monolingual_filler_subset_requirement": {
            "callhome_eng": MONOCONT_ENGLISH,
            "callhome_spa": MONOCONT_SPANISH,
        },
        "excluded_rows_by_reason": {
            source: {
                reason: excluded_rows[source][reason]
                for reason in EXCLUSION_REASON_ORDER
            }
            for source in SOURCE_ORDER
        },
    }
    return inventories, summary


def _condition_summary(
    rows: tuple[CallhomeTrainingRow, ...],
    *,
    condition: str,
    targets: Mapping[str, int],
) -> dict[str, object]:
    by_split: dict[str, object] = {}
    for split in SPLIT_ORDER:
        split_rows = tuple(row for row in rows if row.split == split)
        realized = sum(lexical_token_count(row.text) for row in split_rows)
        target = targets[split]
        by_split[split] = {
            "target_lexical_tokens": target,
            "realized_lexical_tokens": realized,
            "shortfall_lexical_tokens": target - realized,
            "allowed_shortfall_lexical_tokens": quota_tolerance(target),
            "rows": len(split_rows),
            "conversations": len({row.conversation_ref for row in split_rows}),
        }
    return {
        "file": CONDITION_FILENAME[condition],
        "source": CONDITION_SOURCE[condition],
        "splits": by_split,
        "total_target_lexical_tokens": sum(targets.values()),
        "total_realized_lexical_tokens": sum(
            int(by_split[split]["realized_lexical_tokens"]) for split in SPLIT_ORDER
        ),
        "total_rows": len(rows),
    }


def _mono_balance(
    rows_by_condition: Mapping[str, tuple[CallhomeTrainingRow, ...]],
) -> dict[str, object]:
    balance: dict[str, object] = {}
    for split in SPLIT_ORDER:
        english = sum(
            lexical_token_count(row.text)
            for row in rows_by_condition[MONOCONT_ENGLISH]
            if row.split == split
        )
        spanish = sum(
            lexical_token_count(row.text)
            for row in rows_by_condition[MONOCONT_SPANISH]
            if row.split == split
        )
        total = english + spanish
        balance[split] = {
            "target_english_fraction": 0.5,
            "target_spanish_fraction": 0.5,
            "realized_english_lexical_tokens": english,
            "realized_spanish_lexical_tokens": spanish,
            "realized_english_fraction": round(english / total, 8) if total else 0.0,
            "realized_spanish_fraction": round(spanish / total, 8) if total else 0.0,
        }
    return balance


def build_pilot_condition_membership(
    reconciled: Iterable[ReconciledEligibility],
    *,
    frozen_checksum_record_sha256: str,
    seed: int = DEFAULT_SEED,
    targets: Mapping[str, Mapping[str, int]] = PROVISIONAL_TARGETS,
) -> PilotConditionBuild:
    """Select four deterministic, nested, provisional condition memberships."""
    if (
        isinstance(seed, bool)
        or not isinstance(seed, int)
        or not frozen_checksum_record_sha256
    ):
        raise CallhomePilotConditionError(ERROR_INVALID_INPUT)
    selected_targets = _validated_targets(targets)
    inventories, eligibility_summary = _materialize_eligible_inventories(reconciled)

    rows_by_condition_lists: dict[str, list[CallhomeTrainingRow]] = {
        condition: [] for condition in CONDITION_ORDER
    }
    for source in SOURCE_ORDER:
        mono_condition = _MONO_BY_SOURCE[source]
        monocont_condition = _MONOCONT_BY_SOURCE[source]
        for split in SPLIT_ORDER:
            ordered = sorted(
                inventories[(source, split)],
                key=lambda row: _selection_key(
                    row,
                    seed=seed,
                    source=source,
                    split=split,
                ),
            )
            monocont_rows, _ = _select_under_target(
                ordered,
                target=selected_targets[monocont_condition][split],
            )
            mono_rows, _ = _select_under_target(
                ordered,
                target=selected_targets[mono_condition][split],
                required_rows=monocont_rows,
            )
            rows_by_condition_lists[monocont_condition].extend(monocont_rows)
            rows_by_condition_lists[mono_condition].extend(mono_rows)

    rows_by_condition = {
        condition: tuple(rows_by_condition_lists[condition])
        for condition in CONDITION_ORDER
    }
    for source in SOURCE_ORDER:
        mono_ids = {
            row.row_id for row in rows_by_condition[_MONO_BY_SOURCE[source]]
        }
        monocont_ids = {
            row.row_id for row in rows_by_condition[_MONOCONT_BY_SOURCE[source]]
        }
        if not monocont_ids <= mono_ids:
            raise CallhomePilotConditionError(ERROR_INVALID_INPUT)

    manifest = {
        "format_version": FORMAT_VERSION,
        "seed": seed,
        "eligibility_policy_id": ELIGIBILITY_POLICY_ID,
        "selection_rule_id": SELECTION_RULE_ID,
        "matching": {
            "stage": "provisional_lexical",
            "lexical_token_definition": (
                "whitespace-delimited token containing at least one alphabetic character"
            ),
            "shared_tokenizer_adjustment_pending": True,
        },
        "frozen_checksum_record_sha256": frozen_checksum_record_sha256,
        "eligibility": {
            "required_category": ELIGIBLE_ANNOTATION_CLEAN,
            "recomputed_from_approved_raw_and_reconciled_to_frozen_rows": True,
            "intermediate_eligible_row_sidecar_written": False,
            **eligibility_summary,
        },
        "conditions": {
            condition: _condition_summary(
                rows_by_condition[condition],
                condition=condition,
                targets=selected_targets[condition],
            )
            for condition in CONDITION_ORDER
        },
        "monocont_balance": _mono_balance(rows_by_condition),
        "sequence_boundary": {
            "sequence_packing_performed": False,
            "row_files_represent_membership_only": True,
            "cross_language_packing": "forbidden",
            "future_packer_requirement": (
                "English and Spanish MonoCont rows must never share a sequence "
                "or packed context."
            ),
        },
        "invariants": {
            "sampling_without_replacement": True,
            "frozen_splits_preserved": True,
            "provenance_fields_preserved": True,
            "monocont_shards_are_separate": True,
            "monocont_shards_subset_of_corresponding_monolingual_baseline": True,
            "cscont_rows_emitted_by_this_builder": 0,
            "callhome_rows_qualified_as_code_switched_evidence": 0,
        },
    }
    return PilotConditionBuild(rows_by_condition=rows_by_condition, manifest=manifest)


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def _rows_bytes(rows: Iterable[CallhomeTrainingRow]) -> bytes:
    ordered = sorted(
        rows,
        key=lambda row: (
            row.source,
            row.split or "",
            row.conversation_ref,
            row.turn_index,
            row.row_id,
        ),
    )
    return b"".join(_json_bytes(row.to_dict()) for row in ordered)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_atomic_pilot_build(
    build: PilotConditionBuild,
    *,
    publish_dir: Path,
) -> dict[str, str]:
    """Atomically publish exactly four membership files and two metadata files."""
    if publish_dir.exists():
        raise CallhomePilotConditionError(ERROR_OUTPUT_EXISTS)
    if set(build.rows_by_condition) != set(CONDITION_ORDER):
        raise CallhomePilotConditionError(ERROR_INVALID_INPUT)

    artifact_bytes = {
        CONDITION_FILENAME[condition]: _rows_bytes(build.rows_by_condition[condition])
        for condition in CONDITION_ORDER
    }
    artifact_bytes["manifest.json"] = _json_bytes(build.manifest)
    checksums = {
        name: _sha256(content)
        for name, content in sorted(artifact_bytes.items())
    }
    artifact_bytes["checksums.json"] = _json_bytes(checksums)
    if set(artifact_bytes) != _ARTIFACT_NAMES:
        raise CallhomePilotConditionError(ERROR_INVALID_INPUT)

    publish_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{publish_dir.name}.staging-",
            dir=publish_dir.parent,
        )
    )
    try:
        for name, content in artifact_bytes.items():
            (staging / name).write_bytes(content)
        os.replace(staging, publish_dir)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return checksums
