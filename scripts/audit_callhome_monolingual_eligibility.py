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
from pathlib import Path

from cslm.data.callhome_chat import StrictChatReaderError, read_chat_transcript
from cslm.data.callhome_monolingual_eligibility import (
    CallhomeEligibilityError,
    audit_callhome_monolingual_eligibility,
)
from cslm.data.callhome_training_rows import (
    CallhomeTrainingRow,
    CallhomeTrainingRowsError,
)
from cslm.utils.paths import project_root

EXPECTED_ENGLISH_FILES = 176
EXPECTED_SPANISH_FILES = 140
EXPECTED_FROZEN_CHECKSUMS_SHA256 = (
    "e3571a6c9158a5cb53dd3088a371306ee18a568098ed67f51e25e7cb816bb328"
)
_FIXED_FAILURE = "CALLHOME monolingual-eligibility audit failed"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Required explicit opt-in for a later real local audit.",
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
    if set(checksums) != expected_names:
        raise ValueError(_FIXED_FAILURE)
    for name in sorted(expected_names):
        if hashlib.sha256((pool_root / name).read_bytes()).hexdigest() != checksums[name]:
            raise ValueError(_FIXED_FAILURE)
    return [
        *_load_frozen_rows(pool_root / "english_rows.jsonl"),
        *_load_frozen_rows(pool_root / "spanish_rows.jsonl"),
    ]


def main() -> int:
    args = _parse_args()
    if not args.execute:
        raise SystemExit(
            "Refusing to process real CALLHOME without the explicit --execute opt-in."
        )

    root = project_root()
    raw_root = root / "data" / "raw" / "callhome"
    pool_root = root / "data" / "processed" / "callhome" / "pools"
    english_paths = _direct_cha_files(raw_root / "eng")
    spanish_paths = _direct_cha_files(raw_root / "spa")
    if len(english_paths) != EXPECTED_ENGLISH_FILES:
        raise SystemExit(_FIXED_FAILURE)
    if len(spanish_paths) != EXPECTED_SPANISH_FILES:
        raise SystemExit(_FIXED_FAILURE)

    try:
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
    except (
        CallhomeEligibilityError,
        CallhomeTrainingRowsError,
        StrictChatReaderError,
        OSError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
    ):
        raise SystemExit(_FIXED_FAILURE) from None

    print(
        json.dumps(
            summary,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
