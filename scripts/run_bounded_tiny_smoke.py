#!/usr/bin/env python3
"""Closed CLI boundary for a future externally authorized Tiny smoke."""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from cslm.modeling.smoke_training import (
    RESUME_DIAGNOSTIC_ARGUMENT,
    RESUME_DIAGNOSTIC_PROTOCOL,
    RESUME_DIAGNOSTIC_WORKER_ARGUMENT,
    RESUME_WORKER_ARGUMENT,
    SMOKE_APPROVAL_MISMATCH,
    SMOKE_FAILURE_CODES,
    SMOKE_RESUME_MISMATCH,
    SmokeTrainingError,
    _invocation3_diagnostic_workspace_path_is_safe,
    construct_production_smoke_execution_authorization,
    execute_bounded_tiny_smoke,
    execute_tiny_resume_replay_worker,
    run_invocation3_replay_diagnostic,
)


def _fixed_result(
    code: str | None,
    *,
    executed: bool,
    status: str,
    preserved_workspace: str | None = None,
) -> str:
    if code is not None and code not in SMOKE_FAILURE_CODES:
        code = SMOKE_APPROVAL_MISMATCH
    payload: dict[str, bool | str] = {
        "executed": executed,
        "mechanics_only": True,
        "status": status,
    }
    if code is not None:
        payload["code"] = code
    if preserved_workspace is not None:
        workspace = Path(preserved_workspace)
        if _invocation3_diagnostic_workspace_path_is_safe(workspace):
            payload["workspace_disposition"] = "preserved"
            payload["workspace_path"] = str(workspace)
    return json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )


def _diagnostic_record(
    started: float,
    phase: str,
    update: int | None,
) -> None:
    fields: dict[str, object] = {
        "elapsed_ms": int((time.monotonic() - started) * 1_000),
        "phase": phase,
        "protocol": RESUME_DIAGNOSTIC_PROTOCOL,
        "result": True,
    }
    if update is not None:
        fields["update"] = update
    print(
        json.dumps(fields, sort_keys=True, separators=(",", ":")),
        file=sys.stderr,
        flush=True,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Accept no protocol options and execute only factory-produced authority."""

    arguments = tuple(sys.argv[1:] if argv is None else argv)
    if len(arguments) == 2 and arguments[0] == RESUME_DIAGNOSTIC_WORKER_ARGUMENT:
        started = time.monotonic()

        def sink(phase: str, update: int | None) -> None:
            _diagnostic_record(started, phase, update)

        try:
            result = execute_tiny_resume_replay_worker(
                Path(arguments[1]),
                diagnostic_sink=sink,
            )
        except Exception:
            return 3
        if result:
            sys.stdout.buffer.write(result)
        return 0
    if arguments == (RESUME_DIAGNOSTIC_ARGUMENT,):
        try:
            result = run_invocation3_replay_diagnostic()
        except Exception as error:
            preserved_workspace = (
                getattr(error, "preserved_workspace", None)
                if isinstance(error, SmokeTrainingError)
                else None
            )
            print(
                _fixed_result(
                    SMOKE_RESUME_MISMATCH,
                    executed=False,
                    status="replay_diagnostic_failed",
                    preserved_workspace=preserved_workspace,
                ),
                file=sys.stderr,
            )
            return 3
        print(json.dumps(result, ensure_ascii=True, sort_keys=True, separators=(",", ":")))
        return 0 if str(result.get("disposition", "")).startswith("COMPLETED_") else 3
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
