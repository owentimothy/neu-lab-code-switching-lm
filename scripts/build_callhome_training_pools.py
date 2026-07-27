#!/usr/bin/env python3
"""Build local-only CALLHOME English and Spanish training-row pools.

This script is intentionally fixed to the approved repository-local CALLHOME
populations and processed-output directory. It prints aggregate counts only.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from cslm.data.callhome_training_rows import (
    build_population_rows,
    write_atomic_build,
)
from cslm.utils.paths import project_root

EXPECTED_ENGLISH_FILES = 176
EXPECTED_SPANISH_FILES = 140
DEFAULT_SEED = 1729


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Required explicit opt-in for a real local build.",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    return parser.parse_args()


def _direct_cha_files(directory: Path) -> list[Path]:
    return sorted(
        (path for path in directory.iterdir() if path.is_file() and path.suffix == ".cha"),
        key=lambda path: path.name,
    )


def main() -> int:
    args = _parse_args()
    if not args.execute:
        raise SystemExit(
            "Refusing to process real CALLHOME without the explicit --execute opt-in."
        )

    root = project_root()
    callhome_root = root / "data" / "raw" / "callhome"
    english_paths = _direct_cha_files(callhome_root / "eng")
    spanish_paths = _direct_cha_files(callhome_root / "spa")
    if len(english_paths) != EXPECTED_ENGLISH_FILES:
        raise SystemExit("CALLHOME English population count mismatch")
    if len(spanish_paths) != EXPECTED_SPANISH_FILES:
        raise SystemExit("CALLHOME Spanish population count mismatch")

    english = build_population_rows(english_paths, source="callhome_eng")
    spanish = build_population_rows(spanish_paths, source="callhome_spa")
    publish_dir = root / "data" / "processed" / "callhome" / "pools"
    write_atomic_build(
        english,
        spanish,
        publish_dir=publish_dir,
        seed=args.seed,
    )

    print(f"English files read: {english.files_read}")
    print(f"English rows included: {len(english.rows)}")
    print(f"Spanish files read: {spanish.files_read}")
    print(f"Spanish rows included: {len(spanish.rows)}")
    print("CALLHOME local training-row build completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
