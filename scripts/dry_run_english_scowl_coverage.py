#!/usr/bin/env python
"""Aggregate-only, local-only CALLHOME English SCOWL *coverage* dry run.

This runner measures **only** how well the approved English SCOWL word list
*covers* the normalized lexical tokens of the canonical English CALLHOME
population, and prints one small block of corpus-level counts. It is a
**diagnostic, never a verdict**: it does not validate a row, set ``clean``,
decide condition eligibility, route a row, build a dataset, or touch a tokenizer
or model. It reuses the merged coverage interfaces without changing them.

Safety posture (see ``docs/english_scowl_coverage_dry_run_plan.md``):

* **Refuses by default.** Without the explicit ``--allow-real-coverage-run``
  flag the command refuses *before* resolving any corpus or resource path,
  reads and writes nothing, and exits ``2``.
* **One canonical population, no knobs.** With the opt-in it resolves exactly
  ``project_root()/data/raw/callhome/eng`` and processes every *direct* ``*.cha``
  file there in deterministic sorted order. There is no corpus-root, path, glob,
  filename, output, subset, limit, sample, date, speaker, conversation, row, or
  filter option. Spanish and Bangor are never opened.
* **Aggregate-only, content-free output.** On success it prints exactly one JSON
  object of seven integer counts to stdout (and nothing to stderr). It writes no
  file and logs no corpus-derived value.
* **Fail closed and atomic.** Any missing dependency, parse failure, loader or
  evaluator failure, invalid/contradictory result, empty or zero-token summary,
  or other ordinary exception aborts the *whole* run with a single fixed message
  and a nonzero exit. No file is skipped; no partial aggregate is ever emitted.
* **Whole-bundle privacy guard (k = 10).** Before printing, all seven counts are
  checked: zero is allowed, but every *positive* count must be at least 10. If
  any positive count is below 10 the entire numeric bundle is withheld (the count
  identities would otherwise leak a small cell by subtraction). ``k = 10`` is a
  **new project decision**, not a pre-existing governance rule.

Real execution stays separately gated: the exact seven-count schema is still
**closed** for real output pending a Decision B per-output privacy review, and a
real run must be separately authorized. CALLHOME never feeds ``CsCont``; Bangor
remains untouched and ``CsCont``-only.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path

from cslm.data.callhome_chat import CallhomeTranscript, parse_chat_file
from cslm.data.english_scowl_coverage import EnglishScowlCoverageEvaluator
from cslm.data.english_scowl_coverage_diagnostics import (
    flatten_english_coverage_summary,
    summarize_english_coverage_results,
)
from cslm.data.english_scowl_resource import load_approved_english_scowl
from cslm.utils.paths import project_root

# --------------------------------------------------------------------------- #
# Fixed contract: exit codes, messages, schema keys, and the privacy threshold.
# --------------------------------------------------------------------------- #

EXIT_SUCCESS = 0
EXIT_OPT_IN_REQUIRED = 2  # opt-in missing OR argparse usage failure (argparse uses 2)
EXIT_OPERATIONAL_ABORT = 3  # missing dependency / input / invariant / ordinary failure
EXIT_PRIVACY_SUPPRESSED = 4  # whole-bundle k=10 privacy guard withheld the output

# Fixed, interpolation-free messages. None contains a path, filename, token,
# identifier, count, or any corpus-derived value.
_OPT_IN_REQUIRED_MESSAGE = (
    "Refusing to run: pass --allow-real-coverage-run to execute the local "
    "aggregate-only English SCOWL coverage dry run. Nothing was read or written."
)
_OPERATIONAL_ABORT_MESSAGE = (
    "Run aborted: the aggregate-only English SCOWL coverage dry run could not "
    "complete. No aggregate was produced."
)
_PRIVACY_SUPPRESSED_MESSAGE = (
    "Aggregate withheld: the output did not satisfy the whole-bundle privacy "
    "guard. No counts were printed."
)

# The seven scalar counts, in deterministic output order. This is exactly the
# flattened shape of the merged EnglishCoverageSummary.
EXPECTED_KEYS: tuple[str, ...] = (
    "n_results",
    "outcome__all_covered",
    "outcome__has_uncovered",
    "outcome__no_lexical_tokens",
    "n_tokens_total",
    "n_covered_total",
    "n_uncovered_total",
)

# New project decision (NOT existing governance): every positive scalar count in
# the released bundle must be at least this value, or the whole bundle is withheld.
PRIVACY_MIN_COUNT = 10


# --------------------------------------------------------------------------- #
# Internal control-flow exceptions. They carry no payload: the CLI boundary maps
# them to a *fixed* message, never to their text, so nothing sensitive can leak.
# --------------------------------------------------------------------------- #


class _CoverageDryRunError(Exception):
    """Base for this runner's internal control-flow signals (no payload used)."""


class _OperationalError(_CoverageDryRunError):
    """A missing dependency, invalid input, or invariant failure — maps to exit 3."""


class _PrivacyGuardError(_CoverageDryRunError):
    """The whole-bundle k=10 privacy guard withheld the output — maps to exit 4."""


# --------------------------------------------------------------------------- #
# Canonical population resolution and traversal.
# --------------------------------------------------------------------------- #


def _resolve_canonical_english_dir() -> Path:
    """Resolve the one canonical English CALLHOME directory (repo-relative).

    Fixed by this module: ``project_root()/data/raw/callhome/eng``. There is no
    caller path and no override; production always resolves exactly this path.
    """
    return project_root() / "data" / "raw" / "callhome" / "eng"


def _list_english_cha_files(english_dir: Path) -> list[Path]:
    """Return the direct ``*.cha`` files under ``english_dir`` in sorted order.

    Non-recursive (``glob``, not ``rglob``). Raises ``_OperationalError`` if the
    directory is absent, is a symlink, is not a directory, contains no direct
    ``*.cha`` entry, or any matching entry is not a regular non-symlink file.
    Rejecting rather than following or skipping unexpected filesystem objects
    preserves the fixed English-only population boundary.
    """
    if english_dir.is_symlink() or not english_dir.is_dir():
        raise _OperationalError
    files = sorted(english_dir.glob("*.cha"))
    if not files:
        raise _OperationalError
    if any(path.is_symlink() or not path.is_file() for path in files):
        raise _OperationalError
    return files


# --------------------------------------------------------------------------- #
# Whole-bundle privacy guard (k = 10).
# --------------------------------------------------------------------------- #


def _apply_privacy_guard(flat: dict[str, object]) -> None:
    """Validate the flattened bundle, then apply the k=10 whole-bundle guard.

    Structure/type/invariant violations raise ``_OperationalError`` (exit 3). A
    positive count below ``PRIVACY_MIN_COUNT`` raises ``_PrivacyGuardError``
    (exit 4) for the *whole* bundle — never per cell — because the count
    identities (the three outcomes sum to ``n_results``; covered + uncovered ==
    total tokens) would otherwise reveal a suppressed cell by subtraction.
    """
    # Exactly the seven expected keys, nothing missing or extra.
    if set(flat) != set(EXPECTED_KEYS):
        raise _OperationalError
    # Exact, non-negative ints. ``isinstance(bool)`` and the exact ``type`` check
    # both reject booleans (a subclass of int) and any non-int.
    for key in EXPECTED_KEYS:
        value = flat[key]
        if isinstance(value, bool) or type(value) is not int:
            raise _OperationalError
        if value < 0:
            raise _OperationalError
    # Re-check the two count identities.
    outcomes_sum = (
        flat["outcome__all_covered"]
        + flat["outcome__has_uncovered"]
        + flat["outcome__no_lexical_tokens"]
    )
    if outcomes_sum != flat["n_results"]:
        raise _OperationalError
    if flat["n_covered_total"] + flat["n_uncovered_total"] != flat["n_tokens_total"]:
        raise _OperationalError
    # k = 10 whole-bundle guard: zero is allowed; any positive count must be >= 10.
    for key in EXPECTED_KEYS:
        value = flat[key]
        if 0 < value < PRIVACY_MIN_COUNT:
            raise _PrivacyGuardError


# --------------------------------------------------------------------------- #
# Orchestration seam (used by tests via dependency injection; never by the CLI).
# --------------------------------------------------------------------------- #


def _evaluate_and_summarize(
    cha_files: list[Path],
    evaluator: EnglishScowlCoverageEvaluator,
    *,
    parse_file: Callable[[Path], CallhomeTranscript] = parse_chat_file,
) -> dict[str, int]:
    """Parse + evaluate every utterance, summarize, reject empties, apply the guard.

    Collects the complete result population and builds the complete summary before
    any guard or output. A parse or evaluation failure propagates (aborting the
    whole run at the CLI boundary); no file or utterance is skipped.
    """
    results = []
    for path in cha_files:
        transcript = parse_file(path)
        for utterance in transcript.utterances:
            results.append(evaluator.evaluate_utterance(utterance))

    summary = summarize_english_coverage_results(results)
    flat = flatten_english_coverage_summary(summary)

    # Reject an empty or zero-token population (operational, not a valid run).
    if flat["n_results"] == 0 or flat["n_tokens_total"] == 0:
        raise _OperationalError

    _apply_privacy_guard(flat)
    return {key: flat[key] for key in EXPECTED_KEYS}


def _run_coverage_dry_run(
    english_dir: Path,
    evaluator: EnglishScowlCoverageEvaluator,
    *,
    parse_file: Callable[[Path], CallhomeTranscript] = parse_chat_file,
) -> dict[str, int]:
    """Internal seam: validate the population, then evaluate + guard.

    Tests call this with a synthetic ``english_dir``, an evaluator built from a
    synthetic bundle through the real loader boundary, and (where needed) an
    injected ``parse_file``. This seam is **not** reachable from the production
    CLI, which resolves the canonical path and loads the approved resource itself.
    """
    cha_files = _list_english_cha_files(english_dir)
    return _evaluate_and_summarize(cha_files, evaluator, parse_file=parse_file)


def _load_evaluator() -> EnglishScowlCoverageEvaluator:
    """Load and prepare the approved SCOWL resource once (production path)."""
    return EnglishScowlCoverageEvaluator(load_approved_english_scowl())


def _production_run() -> dict[str, int]:
    """Run over the canonical English population (order per requirement 7).

    Resolve the canonical path, validate the population exists and is non-empty,
    load the approved resource once, then evaluate + summarize + guard.
    """
    english_dir = _resolve_canonical_english_dir()
    cha_files = _list_english_cha_files(english_dir)  # validate population first
    evaluator = _load_evaluator()  # load the resource only after population is valid
    return _evaluate_and_summarize(cha_files, evaluator)


# --------------------------------------------------------------------------- #
# CLI.
# --------------------------------------------------------------------------- #


def _build_arg_parser() -> argparse.ArgumentParser:
    """Production CLI: only ``--allow-real-coverage-run`` (plus built-in help)."""
    parser = argparse.ArgumentParser(
        prog="dry_run_english_scowl_coverage.py",
        description=(
            "Local-only, aggregate-only English SCOWL coverage dry run over the "
            "canonical CALLHOME English population. Refuses without the opt-in."
        ),
        allow_abbrev=False,
    )
    parser.add_argument(
        "--allow-real-coverage-run",
        action="store_true",
        help=(
            "Explicit opt-in to execute the local run. Without it the command "
            "refuses before resolving any corpus or resource path."
        ),
    )
    return parser


def _print_aggregate(flat: dict[str, int]) -> None:
    """Print exactly one deterministic seven-key JSON object + one newline."""
    ordered = {key: flat[key] for key in EXPECTED_KEYS}
    print(json.dumps(ordered))


def main(argv: list[str] | None = None) -> int:
    """Refuse without opt-in; otherwise run atomically and print or fail closed."""
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    if not args.allow_real_coverage_run:
        print(_OPT_IN_REQUIRED_MESSAGE, file=sys.stderr)
        return EXIT_OPT_IN_REQUIRED

    try:
        flat = _production_run()
    except _PrivacyGuardError:
        # Order matters: this subclass must be caught before the generic Exception.
        print(_PRIVACY_SUPPRESSED_MESSAGE, file=sys.stderr)
        return EXIT_PRIVACY_SUPPRESSED
    except Exception:
        # Catch Exception (not BaseException): SystemExit/KeyboardInterrupt pass
        # through. No traceback, chained cause, or corpus-derived value is shown.
        print(_OPERATIONAL_ABORT_MESSAGE, file=sys.stderr)
        return EXIT_OPERATIONAL_ABORT

    _print_aggregate(flat)
    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
