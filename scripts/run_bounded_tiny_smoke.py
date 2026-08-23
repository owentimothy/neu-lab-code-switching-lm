#!/usr/bin/env python3
"""Closed CLI boundary for a future externally authorized Tiny smoke."""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Sequence
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_SOURCE_ROOT = _REPOSITORY_ROOT / "src"
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

from cslm.modeling import invocation3_diagnostic as invocation3  # noqa: E402

SMOKE_APPROVAL_MISMATCH = "SMOKE_APPROVAL_MISMATCH"
SMOKE_RESUME_MISMATCH = "SMOKE_RESUME_MISMATCH"
SMOKE_FAILURE_CODES = frozenset({SMOKE_APPROVAL_MISMATCH, SMOKE_RESUME_MISMATCH})
RESUME_WORKER_ARGUMENT = "--internal-tiny-resume-worker"


def _load_smoke_training():
    from cslm.modeling import smoke_training

    return smoke_training


def _legacy_diagnostic_record(started: float, phase: str, update: int | None) -> None:
    fields: dict[str, object] = {"elapsed_ms": int((time.monotonic() - started) * 1_000), "phase": phase, "protocol": "neu_tiny_invocation3_replay_diagnostic_v1", "result": True}  # noqa: E501
    if update is not None:
        fields["update"] = update
    print(json.dumps(fields, sort_keys=True, separators=(",", ":")), file=sys.stderr, flush=True)


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
        if (
            workspace.is_absolute()
            and workspace.parent == Path("/private/tmp")
            and workspace.name.startswith(
                ("neu-invocation3-minimal-diagnostic.", "neu-invocation3-replay-")
            )
        ):
            payload["workspace_disposition"] = "preserved"
            payload["workspace_path"] = str(workspace)
    return json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Accept no protocol options and execute only factory-produced authority."""

    arguments = tuple(sys.argv[1:] if argv is None else argv)
    if (
        len(arguments) == 6
        and arguments[0] == invocation3.WORKER_ARGUMENT
        and arguments[2] == invocation3.REQUEST_SHA_ARGUMENT
        and arguments[4] == invocation3.AUTHORITY_SHA_ARGUMENT
    ):
        def sink(phase: str, update: int | None) -> None:
            print(json.dumps({"category": "mechanics", "phase": phase, "update": update}, ensure_ascii=True, sort_keys=True, separators=(",", ":")), file=sys.stderr, flush=True)  # noqa: E501

        try:
            result = invocation3.run_worker(
                Path(arguments[1]),
                arguments[3],
                arguments[5],
                controller_script=Path(__file__).resolve(),
                argv=tuple(sys.orig_argv),
                sink=sink,
            )
        except Exception:
            return 3
        if result:
            sys.stdout.buffer.write(result)
        return 0
    if (
        len(arguments) == 4
        and arguments[0] == invocation3.CONTROLLER_ARGUMENT
        and arguments[1] == invocation3.AUTHORITY_SHA_ARGUMENT
        and arguments[3] == invocation3.ATTESTATION_ARGUMENT
    ):
        try:
            result = invocation3.run_controller(
                arguments[2],
                controller_script=Path(__file__).resolve(),
                argv=tuple(sys.orig_argv),
            )
        except Exception:
            print(
                _fixed_result(
                    SMOKE_RESUME_MISMATCH,
                    executed=False,
                    status="replay_diagnostic_failed",
                ),
                file=sys.stderr,
            )
            return 3
        print(json.dumps(result, ensure_ascii=True, sort_keys=True, separators=(",", ":")))
        return 0 if result.get("diagnostic_disposition") == (
            "DIAGNOSTIC_REPLAY_MECHANICS_COMPLETED"
        ) else 3
    if len(arguments) == 2 and arguments[0] == invocation3.WORKER_ARGUMENT:
        smoke_training = _load_smoke_training()
        started = time.monotonic()
        try:
            result = smoke_training.execute_tiny_resume_replay_worker(
                Path(arguments[1]),
                diagnostic_sink=lambda phase, update: _legacy_diagnostic_record(
                    started, phase, update
                ),
            )
        except Exception:
            return 3
        if result:
            sys.stdout.buffer.write(result)
        return 0
    if len(arguments) == 2 and arguments[0] == RESUME_WORKER_ARGUMENT:
        smoke_training = _load_smoke_training()
        try:
            result = smoke_training.execute_tiny_resume_replay_worker(Path(arguments[1]))
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
        smoke_training = _load_smoke_training()
        authorization = smoke_training.construct_production_smoke_execution_authorization()
        result = smoke_training.execute_bounded_tiny_smoke(authorization)
    except Exception as error:
        code = getattr(error, "code", SMOKE_APPROVAL_MISMATCH)
        print(
            _fixed_result(
                code,
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
