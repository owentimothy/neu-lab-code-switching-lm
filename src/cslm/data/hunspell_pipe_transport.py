"""Concrete bounded container transport for one PIPE_STREAM batch.

This implements the reviewed :class:`~cslm.data.hunspell_pipe_stream.PipeStreamTransport`
boundary over the shared bounded process supervisor and the pinned container/cleanup
contract.  It performs process/container I/O only: it selects no resource, verifies no
bundle identity, inspects no lexical entry, normalizes no token, parses no Hunspell
response, computes no coverage, and never validates, promotes, or routes a row.

One ``docker run`` — one container, one supervised process — is created per call; there
is no persistent cross-batch process.  Every operational failure collapses to one fixed
non-sensitive :class:`ParityTransportError` with a suppressed cause.  ``KeyboardInterrupt``
and ``SystemExit`` are never converted; they cross the boundary as the same object with a
single fixed ``pipe_stream_cleanup_status`` attribute.

Recovery evidence is never destroyed: the cidfile belongs to ``finalize_container``, and
the per-call control directory and its ownership marker are removed only after cleanup is
confirmed.  Raw stdout is returned to the approved strict parser only after every
invariant passes; raw stderr never leaves this module.  No path, token, container
identifier, control-artifact name, stream, or underlying exception enters a message,
representation, or diagnostic.
"""

from __future__ import annotations

import math
import os
import stat
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Final, Protocol

from cslm.data.hunspell_container import (
    container_cleanup,
    pipe_stream_container_argv,
)
from cslm.data.hunspell_pipe_stream import (
    BATCH_TIMEOUT_SECONDS,
    MAX_STDERR_BYTES,
    MAX_STDOUT_BYTES,
    MAX_TOKEN_BYTES,
    MAX_TOKENS_PER_BATCH,
    PIPE_STREAM_TRANSPORT_FAILURE_MESSAGE,
    TERMINATION_GRACE_SECONDS,
    ParityInputError,
    ParityTransportError,
)
from cslm.data.hunspell_process_supervision import (
    STATE_NORMAL_EXIT,
    BoundedRun,
    run_bounded,
)

# --- Fixed public cleanup statuses (the only diagnostic that crosses the boundary).
PIPE_STREAM_CLEANUP_NOT_ATTEMPTED: Final = "NOT_ATTEMPTED"
PIPE_STREAM_CLEANUP_CONFIRMED: Final = "CONFIRMED"
PIPE_STREAM_CLEANUP_UNCONFIRMED: Final = "UNCONFIRMED"

# --- Fixed, non-sensitive control-artifact names (never input-derived).
CONTROL_OWNER_MARKER_NAME: Final = ".pipe-stream-owner"
CONTROL_CIDFILE_NAME: Final = "container.cid"
CONTROL_DIRECTORY_MODE: Final = 0o700
CONTROL_MARKER_MODE: Final = 0o600

# Derived from the existing approved limits; never a new or raised limit.
MAX_PIPE_STREAM_STDIN_BYTES: Final = MAX_TOKENS_PER_BATCH * (1 + MAX_TOKEN_BYTES + 1)

# Characters that make a Docker long-form ``--mount`` value ambiguous.  An argument
# vector is used, never a shell, so ordinary spaces and ``=`` are safe.
_MOUNT_AMBIGUOUS_CHARACTERS: Final = frozenset({",", '"'})

# Fixed configuration-failure messages; they never echo a path, name, or character.
_INVALID_RUNTIME_PATH: Final = "transport runtime paths must be canonical existing directories"
_INVALID_INSTALLATION: Final = "transport installation directory is not usable"
_INVALID_MOUNT_PATH: Final = "transport mount path is not safely encodable"
_INVALID_DEPENDENCY: Final = "transport dependencies must be callable"


def _transport_failure() -> ParityTransportError:
    """Return the one fixed operational failure, carrying no subprocess data."""
    return ParityTransportError(PIPE_STREAM_TRANSPORT_FAILURE_MESSAGE)


# ---------------------------------------------------------------------------
# Injected dependency boundaries.
# ---------------------------------------------------------------------------
class BoundedProcessRunner(Protocol):
    """One bounded supervised process invocation (``run_bounded`` in production)."""

    def __call__(
        self,
        argv: Sequence[str],
        *,
        stdin_bytes: bytes,
        timeout_seconds: float,
        max_stdout_bytes: int,
        max_stderr_bytes: int,
        grace_seconds: float,
        cleanup: Callable[[bool], None],
    ) -> BoundedRun: ...


ContainerRemover = Callable[[str], None]


class ControlDirectoryFactory(Protocol):
    """Create one unique control directory for the current call, under ``parent``."""

    def __call__(self, parent: Path) -> Path: ...


class _CheckedDefaultRemover:
    """Explicit sentinel selecting the checked default remover in the container module."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "USE_CHECKED_DEFAULT_REMOVER"


USE_CHECKED_DEFAULT_REMOVER: Final = _CheckedDefaultRemover()


def create_unique_control_directory(parent: Path) -> Path:
    """Atomically create one fresh private control directory for the current call."""
    return Path(tempfile.mkdtemp(prefix="pipe-", dir=parent))


# ---------------------------------------------------------------------------
# Cleanup recording (explicit status without losing a cancellation).
# ---------------------------------------------------------------------------
class _CleanupRecorder:
    """Wrap ``container_cleanup`` so its outcome is explicit and cancellation-safe.

    ``_perform_teardown`` guards the cleanup callback with ``except Exception``, so an
    ordinary failure is re-raised here and recorded by the supervisor as
    ``cleanup_confirmed=False``.  A cleanup-time ``KeyboardInterrupt``/``SystemExit`` is
    stored instead of escaping, because escaping would replace an earlier cancellation.
    """

    __slots__ = ("_inner", "state", "cleanup_cancellation", "cleanup_cancellation_traceback")

    def __init__(self, inner: Callable[[bool], None]) -> None:
        self._inner = inner
        self.state: str = PIPE_STREAM_CLEANUP_NOT_ATTEMPTED
        self.cleanup_cancellation: BaseException | None = None
        self.cleanup_cancellation_traceback: TracebackType | None = None

    def __call__(self, clean_exit: bool) -> None:
        self.state = PIPE_STREAM_CLEANUP_UNCONFIRMED  # pessimistic before delegating
        try:
            self._inner(clean_exit)
        except (KeyboardInterrupt, SystemExit) as cancellation:
            if self.cleanup_cancellation is None:
                self.cleanup_cancellation = cancellation
                self.cleanup_cancellation_traceback = cancellation.__traceback__
            return
        self.state = PIPE_STREAM_CLEANUP_CONFIRMED


@dataclass
class _ReleaseResult:
    """Outcome of the single lease/directory release attempt; never raises outward."""

    status: str
    cancellation: BaseException | None = None
    traceback: TracebackType | None = None
    released: bool = False


# ---------------------------------------------------------------------------
# Configuration validation (structural only; never lexical).
# ---------------------------------------------------------------------------
def _validate_directory(value: object) -> Path:
    """Require a canonical, absolute, non-symlink existing directory."""
    if not isinstance(value, Path):
        raise ParityInputError(_INVALID_RUNTIME_PATH)
    if not value.is_absolute() or ".." in value.parts:
        raise ParityInputError(_INVALID_RUNTIME_PATH)
    try:
        resolved = value.resolve(strict=True)
        symlinked = value.is_symlink()
        directory = value.is_dir()
    except OSError:
        raise ParityInputError(_INVALID_RUNTIME_PATH) from None
    if resolved != value or symlinked or not directory:
        raise ParityInputError(_INVALID_RUNTIME_PATH)
    return value


def _is_control_character(code: int) -> bool:
    """C0 controls, DEL, and C1 controls are unsafe in argv and mount encodings."""
    return code < 32 or code == 127 or 128 <= code <= 159


def _reject_unsafe_characters(value: Path, *, mount_value: bool) -> None:
    """Reject characters unsafe for argv, and for a Docker ``--mount`` value."""
    for character in str(value):
        if _is_control_character(ord(character)):
            raise ParityInputError(_INVALID_MOUNT_PATH)
        if mount_value and character in _MOUNT_AMBIGUOUS_CHARACTERS:
            raise ParityInputError(_INVALID_MOUNT_PATH)


def _validate_installation(install_dir: Path) -> None:
    """Require the pinned installation shape without reading any resource content.

    The ``bin`` and ``lib`` parents are checked as well as the executable itself, so a
    symlinked directory cannot redirect the mounted installation tree.
    """
    binary_dir = install_dir / "bin"
    binary = binary_dir / "hunspell"
    library = install_dir / "lib"
    try:
        binary_dir_ok = not binary_dir.is_symlink() and binary_dir.is_dir()
        binary_ok = (
            not binary.is_symlink() and binary.is_file() and os.access(binary, os.X_OK)
        )
        library_ok = not library.is_symlink() and library.is_dir()
    except OSError:
        raise ParityInputError(_INVALID_INSTALLATION) from None
    if not (binary_dir_ok and binary_ok and library_ok):
        raise ParityInputError(_INVALID_INSTALLATION)


def _is_finite_number(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
    )


def _require_exact_limits(
    timeout_seconds: object,
    max_stdout_bytes: object,
    max_stderr_bytes: object,
    grace_seconds: object,
) -> None:
    """Require exact equality with every approved limit, so policy cannot drift."""
    for value, approved in (
        (timeout_seconds, BATCH_TIMEOUT_SECONDS),
        (grace_seconds, TERMINATION_GRACE_SECONDS),
    ):
        if not _is_finite_number(value) or value != approved:
            raise _transport_failure() from None
    for value, approved in (
        (max_stdout_bytes, MAX_STDOUT_BYTES),
        (max_stderr_bytes, MAX_STDERR_BYTES),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value != approved:
            raise _transport_failure() from None


# ---------------------------------------------------------------------------
# Per-call control directory and its atomic ownership marker.
# ---------------------------------------------------------------------------
def _validate_control_directory(candidate: object, workspace_dir: Path) -> Path:
    """Verify every observable property of the factory's result before any launch."""
    if not isinstance(candidate, Path) or not candidate.is_absolute():
        raise _transport_failure() from None
    if ".." in candidate.parts:
        raise _transport_failure() from None
    try:
        resolved = candidate.resolve(strict=True)
        symlinked = candidate.is_symlink()
        info = os.stat(candidate, follow_symlinks=False)
    except OSError:
        raise _transport_failure() from None
    if resolved != candidate or symlinked or not stat.S_ISDIR(info.st_mode):
        raise _transport_failure() from None
    if candidate.parent != workspace_dir:
        raise _transport_failure() from None
    if stat.S_IMODE(info.st_mode) != CONTROL_DIRECTORY_MODE:
        raise _transport_failure() from None
    if hasattr(os, "geteuid") and info.st_uid != os.geteuid():
        raise _transport_failure() from None
    try:
        with os.scandir(candidate) as entries:
            occupied = next(entries, None) is not None
        cidfile_present = (candidate / CONTROL_CIDFILE_NAME).exists()
    except OSError:
        raise _transport_failure() from None
    if occupied or cidfile_present:
        raise _transport_failure() from None
    return candidate


def _marker_flags() -> int:
    return os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)


def _acquire_lease(control_dir: Path) -> tuple[int, int]:
    """Claim exclusive ownership atomically and return the lease identity."""
    marker = control_dir / CONTROL_OWNER_MARKER_NAME
    try:
        descriptor = os.open(marker, _marker_flags(), CONTROL_MARKER_MODE)
    except OSError:
        raise _transport_failure() from None
    try:
        info = os.fstat(descriptor)
        link = os.lstat(marker)
    except OSError:
        _close_quietly(descriptor)
        raise _transport_failure() from None
    valid = (
        stat.S_ISREG(info.st_mode)
        and stat.S_IMODE(info.st_mode) == CONTROL_MARKER_MODE
        and stat.S_ISREG(link.st_mode)
        and not stat.S_ISLNK(link.st_mode)
        and (link.st_dev, link.st_ino) == (info.st_dev, info.st_ino)
    )
    if valid and hasattr(os, "geteuid"):
        valid = info.st_uid == os.geteuid()
    try:
        os.close(descriptor)
    except OSError:
        raise _transport_failure() from None
    if not valid:
        raise _transport_failure() from None
    return (info.st_dev, info.st_ino)


def _close_quietly(descriptor: int) -> None:
    """Close a lease descriptor.  A cancellation here must still propagate."""
    try:
        os.close(descriptor)
    except OSError:
        pass


def _close_after_restoration(descriptor: int) -> None:
    """Close a restoration descriptor without letting any failure escape.

    Restoration is best-effort and runs only when a winning cancellation or failure has
    already been selected, so a cancellation raised by this close must be suppressed
    rather than replace it.  This is deliberately narrower than
    :func:`_close_quietly`, which is also used during lease acquisition where a
    cancellation must still reach the setup handler.
    """
    try:
        os.close(descriptor)
    except (KeyboardInterrupt, SystemExit, OSError):
        pass


def _restore_marker(control_dir: Path) -> None:
    """Make one bounded attempt to retain the ownership claim; never raise outward.

    ``O_EXCL`` guarantees this can never overwrite or adopt another owner's marker.
    """
    try:
        if not control_dir.is_dir():
            return
        descriptor = os.open(
            control_dir / CONTROL_OWNER_MARKER_NAME, _marker_flags(), CONTROL_MARKER_MODE
        )
    except (KeyboardInterrupt, SystemExit, OSError):
        return
    _close_after_restoration(descriptor)


def _release_control_directory(
    control_dir: Path, identity: tuple[int, int], recorder: _CleanupRecorder
) -> _ReleaseResult:
    """Release the lease and directory at most once.  This never raises outward.

    The cidfile belongs to ``finalize_container``; it is never unlinked or recreated
    here, and no second container remover is ever invoked.
    """
    if recorder.state != PIPE_STREAM_CLEANUP_CONFIRMED:
        return _ReleaseResult(recorder.state)

    marker = control_dir / CONTROL_OWNER_MARKER_NAME
    try:
        link = os.lstat(marker)
        if not stat.S_ISREG(link.st_mode) or (link.st_dev, link.st_ino) != identity:
            return _ReleaseResult(PIPE_STREAM_CLEANUP_UNCONFIRMED)
        os.unlink(marker)
    except (KeyboardInterrupt, SystemExit) as cancellation:
        # Deletion may or may not have completed; ``O_EXCL`` makes one restoration
        # attempt safe because it can never overwrite a surviving marker.
        _restore_marker(control_dir)
        return _ReleaseResult(
            PIPE_STREAM_CLEANUP_UNCONFIRMED, cancellation, cancellation.__traceback__
        )
    except OSError:
        _restore_marker(control_dir)
        return _ReleaseResult(PIPE_STREAM_CLEANUP_UNCONFIRMED)

    try:
        control_dir.rmdir()
    except (KeyboardInterrupt, SystemExit) as cancellation:
        _restore_marker(control_dir)
        return _ReleaseResult(
            PIPE_STREAM_CLEANUP_UNCONFIRMED, cancellation, cancellation.__traceback__
        )
    except OSError:
        _restore_marker(control_dir)
        return _ReleaseResult(PIPE_STREAM_CLEANUP_UNCONFIRMED)
    return _ReleaseResult(PIPE_STREAM_CLEANUP_CONFIRMED, released=True)


# ---------------------------------------------------------------------------
# Result reduction (no parsing; the strict parser owns protocol framing).
# ---------------------------------------------------------------------------
def _reduce_bounded_run(
    result: object, recorder: _CleanupRecorder, max_stdout_bytes: int
) -> bytes:
    """Return raw stdout only when every supervised invariant holds."""
    if not isinstance(result, BoundedRun):
        raise _transport_failure() from None
    if recorder.state != PIPE_STREAM_CLEANUP_CONFIRMED:
        raise _transport_failure() from None
    stdout = result.stdout
    stderr = result.stderr
    # Every counted field must be an actual non-Boolean integer *before* any value
    # comparison: ``False == 0`` would otherwise satisfy an exact-zero check.
    for counted in (
        result.returncode,
        result.stdout_bytes,
        result.stderr_bytes,
        result.latency_ms,
    ):
        if isinstance(counted, bool) or not isinstance(counted, int):
            raise _transport_failure() from None
    if (
        result.returncode != 0
        or result.terminal_state != STATE_NORMAL_EXIT
        or result.forced_termination is not False
        or result.stdin_delivered is not True
        or type(stdout) is not bytes
        or type(stderr) is not bytes
        or stderr != b""
        or result.stderr_bytes != len(stderr)
        or result.stdout_bytes != len(stdout)
        or result.stdout_bytes > max_stdout_bytes
        or result.stdout_limit_exceeded is not False
        or result.stderr_limit_exceeded is not False
        or result.timed_out is not False
        or result.worker_failed is not False
        or result.workers_joined is not True
        or result.cleanup_required is not True
        or result.cleanup_confirmed is not True
        or result.latency_ms < 0
    ):
        raise _transport_failure() from None
    return stdout


class HunspellContainerPipeTransport:
    """One bounded pinned-container PIPE_STREAM batch per call.

    Dependencies are explicit constructor arguments; there is no module-global seam and
    no mutable per-instance state, so uniqueness comes from the injected factory and the
    atomic ownership marker rather than from a counter.
    """

    def __init__(
        self,
        *,
        bundle_dir: Path,
        install_dir: Path,
        workspace_dir: Path,
        process_runner: BoundedProcessRunner = run_bounded,
        container_remover: ContainerRemover | _CheckedDefaultRemover = (
            USE_CHECKED_DEFAULT_REMOVER
        ),
        control_directory_factory: ControlDirectoryFactory = create_unique_control_directory,
    ) -> None:
        bundle = _validate_directory(bundle_dir)
        install = _validate_directory(install_dir)
        workspace = _validate_directory(workspace_dir)
        _reject_unsafe_characters(bundle, mount_value=True)
        _reject_unsafe_characters(install, mount_value=True)
        _reject_unsafe_characters(workspace, mount_value=False)
        _validate_installation(install)
        if not callable(process_runner) or not callable(control_directory_factory):
            raise ParityInputError(_INVALID_DEPENDENCY)
        if not isinstance(container_remover, _CheckedDefaultRemover) and not callable(
            container_remover
        ):
            raise ParityInputError(_INVALID_DEPENDENCY)
        self._bundle_dir = bundle
        self._install_dir = install
        self._workspace_dir = workspace
        self._process_runner = process_runner
        self._container_remover = container_remover
        self._control_directory_factory = control_directory_factory

    def __repr__(self) -> str:
        return "HunspellContainerPipeTransport(...)"

    # -- internals ---------------------------------------------------------
    def _create_control_directory(self) -> object:
        """Call the injected factory only; validation is a separate, tracked step."""
        try:
            return self._control_directory_factory(self._workspace_dir)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception:
            raise _transport_failure() from None

    def _cleanup_callback(self, cidfile_path: Path) -> Callable[[bool], None]:
        remover = (
            None
            if isinstance(self._container_remover, _CheckedDefaultRemover)
            else self._container_remover
        )
        return container_cleanup(cidfile_path, docker_remove=remover)

    # -- protocol ----------------------------------------------------------
    def run_pipe_batch(
        self,
        stdin_bytes: bytes,
        *,
        timeout_seconds: float,
        max_stdout_bytes: int,
        max_stderr_bytes: int,
        grace_seconds: float,
    ) -> bytes:
        """Run one bounded PIPE_STREAM batch and return raw stdout, or fail closed."""
        _require_exact_limits(
            timeout_seconds, max_stdout_bytes, max_stderr_bytes, grace_seconds
        )
        if type(stdin_bytes) is not bytes or len(stdin_bytes) > MAX_PIPE_STREAM_STDIN_BYTES:
            raise _transport_failure() from None

        # Setup phase.  A cancellation here reports NOT_ATTEMPTED while nothing has been
        # created, and UNCONFIRMED once a control directory (and possibly its ownership
        # marker) exists, so preserved artifacts are always announced.
        created: object = None
        try:
            created = self._create_control_directory()
            control_dir = _validate_control_directory(created, self._workspace_dir)
            identity = _acquire_lease(control_dir)
            cidfile = control_dir / CONTROL_CIDFILE_NAME
            argv = pipe_stream_container_argv(
                cidfile_path=cidfile,
                bundle_dir=self._bundle_dir,
                install_dir=self._install_dir,
            )
        except (KeyboardInterrupt, SystemExit) as cancellation:
            cancellation.pipe_stream_cleanup_status = (
                PIPE_STREAM_CLEANUP_NOT_ATTEMPTED
                if created is None
                else PIPE_STREAM_CLEANUP_UNCONFIRMED
            )
            raise
        except (ParityInputError, ParityTransportError):
            raise
        except Exception:
            raise _transport_failure() from None

        recorder = _CleanupRecorder(self._cleanup_callback(cidfile))
        pending: BaseException | None = None
        pending_traceback: TracebackType | None = None
        result: object = None
        try:
            result = self._process_runner(
                argv,
                stdin_bytes=stdin_bytes,
                timeout_seconds=timeout_seconds,
                max_stdout_bytes=max_stdout_bytes,
                max_stderr_bytes=max_stderr_bytes,
                grace_seconds=grace_seconds,
                cleanup=recorder,
            )
        except (KeyboardInterrupt, SystemExit) as cancellation:
            # The runner's cancellation is the original winner; a later cleanup
            # cancellation never replaces it.
            release = _release_control_directory(control_dir, identity, recorder)
            cancellation.pipe_stream_cleanup_status = release.status
            raise
        except Exception:
            # A stored cleanup cancellation outranks an ordinary runner error, whose
            # message is never inspected, attached, or chained.
            if recorder.cleanup_cancellation is None:
                raise _transport_failure() from None
            pending = recorder.cleanup_cancellation
            pending_traceback = recorder.cleanup_cancellation_traceback

        if pending is None and recorder.cleanup_cancellation is not None:
            del result  # the BoundedRun is never reduced; no stream is exposed
            pending = recorder.cleanup_cancellation
            pending_traceback = recorder.cleanup_cancellation_traceback

        if pending is not None:
            # Raised outside every handler so no implicit context is attached.
            pending.pipe_stream_cleanup_status = PIPE_STREAM_CLEANUP_UNCONFIRMED
            pending.__context__ = None
            raise pending.with_traceback(pending_traceback) from None

        stdout = _reduce_bounded_run(result, recorder, max_stdout_bytes)
        release = _release_control_directory(control_dir, identity, recorder)
        if release.cancellation is not None:
            release.cancellation.pipe_stream_cleanup_status = release.status
            release.cancellation.__context__ = None
            raise release.cancellation.with_traceback(release.traceback) from None
        if not release.released:
            raise _transport_failure() from None
        del result  # drop the raw process record promptly
        return stdout
