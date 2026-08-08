#!/usr/bin/env python3
"""Closed CLI boundary for a future externally authorized Tiny smoke."""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path

from cslm.modeling.smoke_training import (
    RESUME_WORKER_ARGUMENT,
    SMOKE_APPROVAL_MISMATCH,
    SMOKE_FAILURE_CODES,
    SMOKE_RESUME_MISMATCH,
    SmokeTrainingError,
    construct_production_smoke_execution_authorization,
    execute_bounded_tiny_smoke,
    execute_tiny_resume_replay_worker,
)


def _fixed_result(code: str | None, *, executed: bool, status: str) -> str:
    if code is not None and code not in SMOKE_FAILURE_CODES:
        code = SMOKE_APPROVAL_MISMATCH
    payload: dict[str, bool | str] = {
        "executed": executed,
        "mechanics_only": True,
        "status": status,
    }
    if code is not None:
        payload["code"] = code
    return json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Accept no protocol options and execute only factory-produced authority."""

    arguments = tuple(sys.argv[1:] if argv is None else argv)
    if len(arguments) == 2 and arguments[0] == RESUME_WORKER_ARGUMENT:
        try:
            result = execute_tiny_resume_replay_worker(Path(arguments[1]))
        except Exception:
            print(
                _fixed_result(
                    SMOKE_RESUME_MISMATCH,
                    executed=False,
                    status="resume_worker_failed",
                ),
                file=sys.stderr,
            )
            return 3
        if result:
            sys.stdout.buffer.write(result)
        return 0
    if arguments:
        print(
            _fixed_result(
                SMOKE_APPROVAL_MISMATCH,
                executed=False,
                status="launch_not_authorized",
            ),
            file=sys.stderr,
        )
        return 2
    try:
        authorization = construct_production_smoke_execution_authorization()
        result = execute_bounded_tiny_smoke(authorization)
    except SmokeTrainingError as error:
        print(
            _fixed_result(
                error.code,
                executed=False,
                status="launch_not_authorized",
            ),
            file=sys.stderr,
        )
        return 2
    except Exception:
        print(
            _fixed_result(
                SMOKE_APPROVAL_MISMATCH,
                executed=False,
                status="launch_not_authorized",
            ),
            file=sys.stderr,
        )
        return 2
    if (
        not result.mechanics_passed
        or result.completed_updates_per_condition != 1_000
        or not result.cpu_only
    ):
        print(
            _fixed_result(
                SMOKE_APPROVAL_MISMATCH,
                executed=False,
                status="launch_not_authorized",
            ),
            file=sys.stderr,
        )
        return 2
    print(
        _fixed_result(
            None,
            executed=True,
            status="mechanics_passed",
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
