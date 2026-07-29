#!/usr/bin/env python3
"""Build the pinned deterministic tokenizers 0.22.2 backend.

The source directory must be a clean checkout of the commit recorded in
``infra/tokenizers/backend-lock.json``.  The script applies the single NEU LAB
determinism patch and writes a wheel plus an aggregate build manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import zipfile
from pathlib import Path
from typing import Any, Sequence


class BackendBuildError(RuntimeError):
    """The pinned backend build contract was not satisfied."""


def canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run(
    command: Sequence[str],
    *,
    cwd: Path,
    environment: dict[str, str] | None = None,
) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise BackendBuildError(f"command failed ({command[0]}): {result.stderr.strip()}")
    return result.stdout.strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--maturin", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    lock_path = project_root / "infra/tokenizers/backend-lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    patch_path = project_root / lock["patch"]
    source_dir = args.source_dir.resolve()
    python_binding_dir = source_dir / "bindings/python"

    if not python_binding_dir.is_dir():
        raise BackendBuildError("tokenizers Python binding source is absent")
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise BackendBuildError("output directory must be absent or empty")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    commit = run(("git", "rev-parse", "HEAD"), cwd=source_dir)
    if commit != lock["upstream_commit"]:
        raise BackendBuildError("tokenizers source commit does not match the lock")
    dirty = run(
        ("git", "status", "--porcelain", "--untracked-files=no"),
        cwd=source_dir,
    )
    if dirty:
        raise BackendBuildError("tokenizers source must be clean before patching")
    run(("git", "apply", "--check", str(patch_path)), cwd=source_dir)
    run(("git", "apply", str(patch_path)), cwd=source_dir)
    run(("git", "diff", "--check"), cwd=source_dir)

    environment = os.environ.copy()
    environment["RUSTUP_TOOLCHAIN"] = lock["build"]["rust"]
    environment["MACOSX_DEPLOYMENT_TARGET"] = "11.0"
    rust_version = run(("rustc", "--version"), cwd=source_dir, environment=environment)
    if not rust_version.startswith(f"rustc {lock['build']['rust']} "):
        raise BackendBuildError("rustc version does not match the build lock")
    maturin_version = run(
        (str(args.maturin), "--version"),
        cwd=source_dir,
        environment=environment,
    )
    if maturin_version != f"maturin {lock['build']['maturin']}":
        raise BackendBuildError("maturin version does not match the build lock")
    python_version = run(
        (str(args.python), "--version"),
        cwd=source_dir,
        environment=environment,
    )

    run(
        (
            str(args.maturin),
            "build",
            "--release",
            "--locked",
            "--interpreter",
            str(args.python),
            "--out",
            str(args.output_dir),
        ),
        cwd=python_binding_dir,
        environment=environment,
    )
    wheels = sorted(args.output_dir.glob("tokenizers-0.22.2-*.whl"))
    if len(wheels) != 1:
        raise BackendBuildError("expected exactly one tokenizers 0.22.2 wheel")
    wheel = wheels[0]
    with zipfile.ZipFile(wheel) as archive:
        extension_names = sorted(name for name in archive.namelist() if name.endswith(".so"))
        if len(extension_names) != 1:
            raise BackendBuildError("expected exactly one native extension in wheel")
        native_name = extension_names[0]
        native_sha256 = sha256_bytes(archive.read(native_name))

    patch_sha256 = sha256_file(patch_path)
    build_configuration = {
        "backend_lock": lock,
        "backend_lock_sha256": sha256_file(lock_path),
        "patch_sha256": patch_sha256,
        "cargo_locked": True,
        "rustc": rust_version,
        "maturin": maturin_version,
        "python": python_version,
    }
    manifest = {
        "format_version": 1,
        "backend_correction_id": lock["backend_correction_id"],
        "upstream_commit": commit,
        "tokenizers_version": lock["tokenizers"],
        "build_configuration": build_configuration,
        "build_configuration_sha256": sha256_bytes(canonical_json_bytes(build_configuration)),
        "wheel": {
            "filename": wheel.name,
            "sha256": sha256_file(wheel),
        },
        "native_backend": {
            "archive_path": native_name,
            "sha256": native_sha256,
        },
    }
    manifest_path = args.output_dir / "backend_build_manifest.json"
    if manifest_path.exists():
        raise BackendBuildError("refusing to overwrite backend build manifest")
    manifest_path.write_bytes(canonical_json_bytes(manifest))
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
