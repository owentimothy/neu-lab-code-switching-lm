#!/usr/bin/env python3
"""Build the checksum-pinned, provisional CALLHOME pilot conditions.

Real population execution is refused unless ``--execute`` is supplied. This
script does not train a tokenizer, pack sequences, process Bangor, or create an
intermediate eligible-row pool.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from cslm.data.callhome_chat import read_chat_transcript
from cslm.data.callhome_monolingual_eligibility import (
    EXPLICIT_NONEXPECTED_LANGUAGE,
    SOURCE_ORDER,
    reconcile_frozen_rows,
)
from cslm.data.callhome_pilot_conditions import (
    DEFAULT_SEED,
    build_pilot_condition_membership,
    lexical_token_count,
    write_atomic_pilot_build,
)
from cslm.data.callhome_training_rows import CallhomeTrainingRow
from cslm.utils.paths import project_root

_FIXED_FAILURE = "CALLHOME pilot-condition build failed"
EXPECTED_ENGLISH_FILES = 176
EXPECTED_SPANISH_FILES = 140
EXPECTED_FROZEN_CHECKSUMS_SHA256 = (
    "e3571a6c9158a5cb53dd3088a371306ee18a568098ed67f51e25e7cb816bb328"
)
_EXPECTED_ELIGIBLE_ROWS = {
    "callhome_eng": 53_896,
    "callhome_spa": 31_166,
}
_EXPECTED_ELIGIBLE_TOKENS = {
    "callhome_eng": 365_533,
    "callhome_spa": 237_557,
}
_EXPECTED_EXCLUDED_ROWS = 48


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
    """Load only the exact reviewed frozen pool, without writing a sidecar."""
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
        or set(checksums) != expected_names
    ):
        raise ValueError(_FIXED_FAILURE)
    for name in sorted(expected_names):
        if hashlib.sha256((pool_root / name).read_bytes()).hexdigest() != checksums[name]:
            raise ValueError(_FIXED_FAILURE)
    return [
        *_load_frozen_rows(pool_root / "english_rows.jsonl"),
        *_load_frozen_rows(pool_root / "spanish_rows.jsonl"),
    ]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Required explicit opt-in for a separately authorized real build.",
    )
    return parser.parse_args()


def _verify_reviewed_inventory(reconciled) -> None:
    eligible_rows = {source: 0 for source in SOURCE_ORDER}
    eligible_tokens = {source: 0 for source in SOURCE_ORDER}
    excluded_rows = 0
    for item in reconciled:
        if item.decision.is_eligible:
            eligible_rows[item.row.source] += 1
            eligible_tokens[item.row.source] += lexical_token_count(item.row.text)
        else:
            excluded_rows += 1
            if item.decision.exclusion_reason != EXPLICIT_NONEXPECTED_LANGUAGE:
                raise ValueError(_FIXED_FAILURE)
    if (
        eligible_rows != _EXPECTED_ELIGIBLE_ROWS
        or eligible_tokens != _EXPECTED_ELIGIBLE_TOKENS
        or excluded_rows != _EXPECTED_EXCLUDED_ROWS
    ):
        raise ValueError(_FIXED_FAILURE)


def main() -> int:
    args = _parse_args()
    if not args.execute:
        raise SystemExit(
            "Refusing to process real CALLHOME without the explicit --execute opt-in."
        )

    try:
        root = project_root()
        raw_root = root / "data" / "raw" / "callhome"
        pool_root = root / "data" / "processed" / "callhome" / "pools"
        publish_dir = root / "data" / "processed" / "callhome" / "pilot_conditions"

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
        reconciled = reconcile_frozen_rows(
            transcripts_by_source,
            frozen_rows,
            canonical_splits_by_row_id=canonical_splits_by_row_id,
        )
        _verify_reviewed_inventory(reconciled)
        build = build_pilot_condition_membership(
            reconciled,
            frozen_checksum_record_sha256=EXPECTED_FROZEN_CHECKSUMS_SHA256,
            seed=DEFAULT_SEED,
        )
        write_atomic_pilot_build(build, publish_dir=publish_dir)
        print(
            json.dumps(
                {"status": "published"},
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    except Exception:
        raise SystemExit(_FIXED_FAILURE) from None
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
