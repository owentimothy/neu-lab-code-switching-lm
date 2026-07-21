"""Pinned Hunspell container identity, hardened invocation, and cleanup contract.

This module owns the public pinned Hunspell/container identities, the hardened
(network-disabled, read-only, capability-dropped, cidfile-tracked) ``docker run``
argument vector, and the clean/abnormal container-cleanup contract used by the
Direct-Hunspell work.  It is the single source of truth for those, so the parity
runner and any later bounded transport cannot drift apart on pins, hardening
flags, or cleanup confirmation.

Only the pinned identities are public constants; nothing here reads a resource, a
corpus, or a private log, and no lexical entry, bundle identity, provenance value,
or personal path is defined, printed, logged, or embedded in an error.  A cidfile
holds only a container identifier — never tokens, streams, or diagnostics.  No
Docker command runs on import; the removal helper is executed only by a supervised
lifecycle and always discards its output to ``DEVNULL``.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

from cslm.data.hunspell_pipe_stream import ParityTransportError

# --- Public pinned identities (carried forward from tracked feasibility evidence).
HUNSPELL_RELEASE = "v1.7.3"
HUNSPELL_COMMIT = "c5f98152a274e25b5107101104bef632b83a0cc9"
CONTAINER_REPOSITORY = "docker.io/library/buildpack-deps"
CONTAINER_PLATFORM = "linux/arm64"
CONTAINER_PLATFORM_DIGEST = (
    "sha256:a60c415ba968e9accc8795332295eca29c58968ef95d45616e90e2a5da40f498"
)
CONTAINER_REFERENCE = f"{CONTAINER_REPOSITORY}@{CONTAINER_PLATFORM_DIGEST}"

# In-container layout for a live run.
_CONTAINER_HUNSPELL_BIN = "/opt/hunspell/bin/hunspell"
_CONTAINER_HUNSPELL_LIB = "/opt/hunspell/lib"

# The governed public dictionary basename selected inside the read-only bundle mount.
# It is fixed here; no caller may override it.
CONTAINER_DICTIONARY_BASENAME = "es"

# Docker removal is bounded and never runs in ordinary tests.
_DOCKER_REMOVE_TIMEOUT = 20
_DOCKER_RUN = subprocess.run


# ---------------------------------------------------------------------------
# Container transport helpers (structure only; not executed in this gate).
# ---------------------------------------------------------------------------
def _hardened_prefix(
    *,
    cidfile_path: Path,
    bundle_dir: Path,
    install_dir: Path,
    library_path: str | None = None,
) -> list[str]:
    """Build the hardened option prefix shared by every pinned container invocation.

    ``library_path`` is the only variation, and it is inserted at a fixed position so a
    caller never has to splice into a finished argument vector.  With ``None`` the
    result is byte-for-byte the historical prefix.
    """
    argv = [
        "docker",
        "run",
        "--rm",
        "--interactive",
        "--cidfile",
        str(cidfile_path),
        "--network",
        "none",
        "--platform",
        CONTAINER_PLATFORM,
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--tmpfs",
        "/tmp:rw,nosuid,nodev,noexec,size=64m",
        "-e",
        "LANG=C.UTF-8",
        "-e",
        "LC_ALL=C.UTF-8",
    ]
    if library_path is not None:
        argv += ["-e", f"LD_LIBRARY_PATH={library_path}"]
    argv += [
        "--mount",
        f"type=bind,src={bundle_dir},dst=/bundle,readonly",
        "--mount",
        f"type=bind,src={install_dir},dst=/opt/hunspell,readonly",
        CONTAINER_REFERENCE,
    ]
    return argv


def hardened_container_argv(
    *,
    cidfile_path: Path,
    bundle_dir: Path,
    install_dir: Path,
    inner_argv: Sequence[str],
) -> list[str]:
    """Build the pinned, network-disabled, read-only container argument vector."""
    return [
        *_hardened_prefix(
            cidfile_path=cidfile_path, bundle_dir=bundle_dir, install_dir=install_dir
        ),
        *inner_argv,
    ]


def pipe_stream_container_argv(
    *,
    cidfile_path: Path,
    bundle_dir: Path,
    install_dir: Path,
) -> list[str]:
    """Build the fixed PIPE_STREAM (``-a``) container argument vector.

    The inner invocation, the library path, and the governed dictionary basename are
    fixed here; no caller may override them.  Tokens are delivered only on stdin and
    never enter this vector.
    """
    return [
        *_hardened_prefix(
            cidfile_path=cidfile_path,
            bundle_dir=bundle_dir,
            install_dir=install_dir,
            library_path=_CONTAINER_HUNSPELL_LIB,
        ),
        _CONTAINER_HUNSPELL_BIN,
        "-d",
        f"/bundle/{CONTAINER_DICTIONARY_BASENAME}",
        "-a",
    ]


def _default_docker_remove(container_id: str) -> None:
    """Force-remove a container: argument vector, DEVNULL discard, timeout, checked."""
    completed = _DOCKER_RUN(
        ["docker", "rm", "-f", container_id],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=_DOCKER_REMOVE_TIMEOUT,
        check=False,
    )
    if getattr(completed, "returncode", 1) != 0:
        raise ParityTransportError("docker removal returned a nonzero result")


def _remove_cidfile(cidfile_path: Path) -> None:
    try:
        cidfile_path.unlink()
    except FileNotFoundError:
        pass
    except OSError:
        raise ParityTransportError("cidfile removal failed") from None
    if cidfile_path.exists():
        raise ParityTransportError("cidfile still present after cleanup")


def finalize_container(
    cidfile_path: Path,
    *,
    clean_exit: bool,
    docker_remove=None,
) -> None:
    """Confirm container cleanup for the supervised lifecycle, or fail closed.

    Clean zero exit under ``docker run --rm``: the container removed itself, so only
    the non-token-bearing cidfile is removed and its removal confirmed.  Any
    abnormal exit force-removes a surviving container (checked) and confirms cidfile
    removal; a missing/unreadable cidfile, empty id, remover failure, or unremoved
    cidfile fails closed.  The cidfile holds only the container identifier.
    """
    remover = docker_remove if docker_remove is not None else _default_docker_remove
    present = cidfile_path.exists()
    container_id = ""
    if present:
        try:
            container_id = cidfile_path.read_text(encoding="ascii").strip()
        except (OSError, UnicodeError):
            if not clean_exit:
                raise ParityTransportError("cidfile unreadable on abnormal exit") from None
    if not clean_exit:
        if not present:
            raise ParityTransportError("cidfile missing on abnormal exit")
        if not container_id:
            raise ParityTransportError("cidfile empty on abnormal exit")
        try:
            remover(container_id)
        except ParityTransportError:
            raise
        except Exception:  # noqa: BLE001 - never expose a private value
            raise ParityTransportError("surviving container removal failed") from None
    _remove_cidfile(cidfile_path)


def container_cleanup(cidfile_path: Path, *, docker_remove=None) -> Callable[[bool], None]:
    """Return a clean/abnormal-aware cleanup callable for the process lifecycle."""

    def _cleanup(clean_exit: bool) -> None:
        finalize_container(
            cidfile_path, clean_exit=clean_exit, docker_remove=docker_remove
        )

    return _cleanup
