"""Tests for the pinned Hunspell container identity, argv, and cleanup contract.

Docker is always stubbed; no Docker command actually runs, no image is pulled, and
no container is created.  No test uses the network, runs Hunspell, or accesses
RLA-ES, CALLHOME, Bangor, ignored resources, or private logs.  Container
identifiers used here are invented placeholders.
"""

from __future__ import annotations

import inspect
import subprocess
import types

import pytest

from cslm.data import hunspell_container as cont
from cslm.data import hunspell_pipe_stream as h


# ---------------------------------------------------------------------------
# Public pinned identities and hardened argument vector.
# ---------------------------------------------------------------------------
def test_public_pins_match_tracked_evidence():
    assert cont.HUNSPELL_RELEASE == "v1.7.3"
    assert cont.HUNSPELL_COMMIT == "c5f98152a274e25b5107101104bef632b83a0cc9"
    assert cont.CONTAINER_PLATFORM == "linux/arm64"
    assert cont.CONTAINER_REFERENCE.startswith(
        "docker.io/library/buildpack-deps@sha256:"
    )


def test_hardened_container_argv_output_is_unchanged_by_the_shared_prefix(tmp_path):
    """The historical vector must stay byte-for-byte identical after the extraction."""
    argv = cont.hardened_container_argv(
        cidfile_path=tmp_path / "cid",
        bundle_dir=tmp_path / "bundle",
        install_dir=tmp_path / "install",
        inner_argv=["hunspell", "-d", "/bundle/es", "-a"],
    )
    assert argv == [
        "docker",
        "run",
        "--rm",
        "--interactive",
        "--cidfile",
        str(tmp_path / "cid"),
        "--network",
        "none",
        "--platform",
        "linux/arm64",
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
        "--mount",
        f"type=bind,src={tmp_path / 'bundle'},dst=/bundle,readonly",
        "--mount",
        f"type=bind,src={tmp_path / 'install'},dst=/opt/hunspell,readonly",
        cont.CONTAINER_REFERENCE,
        "hunspell",
        "-d",
        "/bundle/es",
        "-a",
    ]
    assert "LD_LIBRARY_PATH=/opt/hunspell/lib" not in argv


def test_pipe_stream_container_argv_is_pinned_hardened_and_fixed(tmp_path):
    argv = cont.pipe_stream_container_argv(
        cidfile_path=tmp_path / "cid",
        bundle_dir=tmp_path / "bundle",
        install_dir=tmp_path / "install",
    )
    assert argv[:4] == ["docker", "run", "--rm", "--interactive"]
    assert argv.count("--interactive") == 1
    assert argv[argv.index("--network") + 1] == "none"
    assert argv[argv.index("--platform") + 1] == cont.CONTAINER_PLATFORM
    assert argv[argv.index("--cap-drop") + 1] == "ALL"
    assert argv[argv.index("--security-opt") + 1] == "no-new-privileges"
    assert argv[argv.index("--tmpfs") + 1] == "/tmp:rw,nosuid,nodev,noexec,size=64m"
    assert "--read-only" in argv
    assert argv[argv.index("--cidfile") + 1] == str(tmp_path / "cid")
    assert "LANG=C.UTF-8" in argv and "LC_ALL=C.UTF-8" in argv
    assert "LD_LIBRARY_PATH=/opt/hunspell/lib" in argv
    mounts = [argv[i + 1] for i, part in enumerate(argv) if part == "--mount"]
    assert mounts == [
        f"type=bind,src={tmp_path / 'bundle'},dst=/bundle,readonly",
        f"type=bind,src={tmp_path / 'install'},dst=/opt/hunspell,readonly",
    ]
    assert cont.CONTAINER_REFERENCE in argv
    assert argv[-4:] == ["/opt/hunspell/bin/hunspell", "-d", "/bundle/es", "-a"]


def test_pipe_stream_container_argv_has_no_tty_or_working_directory(tmp_path):
    argv = cont.pipe_stream_container_argv(
        cidfile_path=tmp_path / "cid",
        bundle_dir=tmp_path / "bundle",
        install_dir=tmp_path / "install",
    )
    assert "-w" not in argv
    assert "--workdir" not in argv
    assert "--tty" not in argv and "-t" not in argv


def test_pipe_stream_dictionary_basename_is_governed_without_override(tmp_path):
    assert cont.CONTAINER_DICTIONARY_BASENAME == "es"
    argv = cont.pipe_stream_container_argv(
        cidfile_path=tmp_path / "cid",
        bundle_dir=tmp_path / "bundle",
        install_dir=tmp_path / "install",
    )
    assert argv[argv.index("-d") + 1] == "/bundle/es"
    parameters = inspect.signature(cont.pipe_stream_container_argv).parameters
    assert set(parameters) == {"cidfile_path", "bundle_dir", "install_dir"}


def test_hardened_container_argv_is_pinned_and_locked_down(tmp_path):
    argv = cont.hardened_container_argv(
        cidfile_path=tmp_path / "cid",
        bundle_dir=tmp_path / "bundle",
        install_dir=tmp_path / "install",
        inner_argv=["hunspell", "-d", "/bundle/es", "-a"],
    )
    assert argv[argv.index("--network") + 1] == "none"
    assert argv[argv.index("--platform") + 1] == "linux/arm64"
    assert argv[argv.index("--cap-drop") + 1] == "ALL"
    assert argv[argv.index("--security-opt") + 1] == "no-new-privileges"
    assert "--read-only" in argv
    assert argv.count("--interactive") == 1
    assert argv[argv.index("--cidfile") + 1] == str(tmp_path / "cid")
    assert cont.CONTAINER_REFERENCE in argv
    assert argv[-4:] == ["hunspell", "-d", "/bundle/es", "-a"]


# ---------------------------------------------------------------------------
# Container cleanup contract (Docker always stubbed).
# ---------------------------------------------------------------------------
def test_clean_exit_cleanup_removes_only_the_cidfile(tmp_path):
    cidfile = tmp_path / "cid"
    cidfile.write_text("cabc\n", encoding="ascii")
    calls: list[str] = []
    cont.finalize_container(cidfile, clean_exit=True, docker_remove=calls.append)
    assert calls == []  # docker rm -f is NOT run on a clean --rm exit
    assert not cidfile.exists()


def test_abnormal_cleanup_calls_the_remover(tmp_path):
    cidfile = tmp_path / "cid"
    cidfile.write_text("cabc\n", encoding="ascii")
    calls: list[str] = []
    cont.finalize_container(cidfile, clean_exit=False, docker_remove=calls.append)
    assert calls == ["cabc"]
    assert not cidfile.exists()


def test_missing_cidfile_on_abnormal_exit_fails_closed(tmp_path):
    with pytest.raises(h.ParityTransportError):
        cont.finalize_container(
            tmp_path / "absent", clean_exit=False, docker_remove=lambda _c: None
        )


def test_remover_failure_becomes_a_fixed_error(tmp_path):
    cidfile = tmp_path / "cid"
    cidfile.write_text("cabc\n", encoding="ascii")

    def _boom(_container_id):
        raise TimeoutError("private docker timeout detail")

    with pytest.raises(h.ParityTransportError) as excinfo:
        cont.finalize_container(cidfile, clean_exit=False, docker_remove=_boom)
    assert "private" not in str(excinfo.value)


def test_nonzero_remover_result_is_not_confirmed(monkeypatch):
    monkeypatch.setattr(
        cont, "_DOCKER_RUN", lambda *a, **k: types.SimpleNamespace(returncode=1)
    )
    with pytest.raises(h.ParityTransportError):
        cont._default_docker_remove("cabc")


def test_docker_removal_output_is_discarded_boundedly(monkeypatch):
    calls: list[tuple] = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(cont, "_DOCKER_RUN", fake_run)
    cont._default_docker_remove("cid123")
    (argv, kwargs) = calls[0]
    assert argv == ["docker", "rm", "-f", "cid123"]
    assert kwargs["stdin"] is subprocess.DEVNULL
    assert kwargs["stdout"] is subprocess.DEVNULL
    assert kwargs["stderr"] is subprocess.DEVNULL
    assert kwargs["timeout"] == cont._DOCKER_REMOVE_TIMEOUT
    assert "capture_output" not in kwargs
