#!/usr/bin/env python
"""Build the approved private RLA-ES surface-form bundle.

The command has no path or corpus arguments and refuses to run without one
explicit opt-in.  Unit tests use invented package bytes only.  A real execution
is permitted only after this implementation is committed and reviewed.

Successful external output contains public identities, aggregate counts, and
Booleans only.  Lexical entries, affix contents, notices, hashes, provenance
values, archive listings, tool diagnostics, and local paths never leave private
temporary storage.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Final

from cslm.utils.paths import project_root

EXIT_SUCCESS = 0
EXIT_OPT_IN_REQUIRED = 2
EXIT_OPERATIONAL_ABORT = 3
EXIT_UNSUPPORTED_CAPABILITY = 4

_OPT_IN_MESSAGE = (
    "Refusing to run: pass --allow-rla-es-bundle-build to execute the approved "
    "private RLA-ES acquisition and generation gate. Nothing was changed."
)
_ABORT_MESSAGE = (
    "RLA-ES bundle build aborted. No bundle was promoted and no private value "
    "was printed."
)

RESOURCE_ID: Final = "spanish_rla_es_v2_9_general"
RESOURCE_RELEASE: Final = "v2.9"
RESOURCE_TAG_OBJECT: Final = "c67eae826908d05a8dfabf3f7a012ce280678208"
RESOURCE_SOURCE_COMMIT: Final = "ea82c1214ead57740798acf66a1e18e5ac874c41"
RESOURCE_ASSET_ID: Final = 217140315
RESOURCE_ASSET_NAME: Final = "es.oxt"
RESOURCE_ASSET_SIZE: Final = 1_475_270
RESOURCE_ASSET_CONTENT_TYPE: Final = "application/vnd.openofficeorg.extension"
RESOURCE_ASSET_URL: Final = (
    "https://github.com/sbosio/rla-es/releases/download/v2.9/es.oxt"
)
RESOURCE_RELEASE_API: Final = (
    "https://api.github.com/repos/sbosio/rla-es/releases/tags/v2.9"
)
RESOURCE_TAG_REF_API: Final = (
    "https://api.github.com/repos/sbosio/rla-es/git/ref/tags/v2.9"
)
RESOURCE_TAG_API_PREFIX: Final = (
    "https://api.github.com/repos/sbosio/rla-es/git/tags/"
)
SELECTED_LICENSE_PATHWAY: Final = "MPL-1.1-or-later"

HUNSPELL_RELEASE: Final = "v1.7.3"
HUNSPELL_COMMIT: Final = "c5f98152a274e25b5107101104bef632b83a0cc9"
HUNSPELL_ARCHIVE_NAME: Final = "hunspell-1.7.3.tar.gz"
HUNSPELL_ARCHIVE_URL: Final = (
    "https://github.com/hunspell/hunspell/releases/download/"
    f"{HUNSPELL_RELEASE}/{HUNSPELL_ARCHIVE_NAME}"
)
HUNSPELL_ARCHIVE_SHA256: Final = (
    "433274dac0619cb00c2e18b43a3dd3a9d50da5b5613fa9b5c21781e35dd76bc1"
)

CONTAINER_REPOSITORY: Final = "docker.io/library/buildpack-deps"
CONTAINER_TAG: Final = "bookworm"
CONTAINER_INDEX_DIGEST: Final = (
    "sha256:5bfacbc6611775f980cf283fbc86b999517878d39723510687135a0d6366bbee"
)
CONTAINER_PLATFORM_DIGEST: Final = (
    "sha256:a60c415ba968e9accc8795332295eca29c58968ef95d45616e90e2a5da40f498"
)
CONTAINER_PLATFORM: Final = "linux/arm64"
CONTAINER_REFERENCE: Final = f"{CONTAINER_REPOSITORY}@{CONTAINER_PLATFORM_DIGEST}"

APPROVAL_DOCUMENT_COMMIT: Final = "665fa722995ebf0ac3febf51197b03703bc6b83e"
APPROVAL_MERGE_COMMIT: Final = "74330b0712497f9bb6d00ed2026e66409848d745"
EXECUTION_BRANCH: Final = "spanish-rla-es-bundle-acquisition"

BUNDLE_RELATIVE_PATH: Final = (
    Path("data")
    / "resources"
    / "local_lexicons"
    / "spanish"
    / RESOURCE_ID
)
SURFACE_FILENAME: Final = "rla_es_v2_9_general_surface_forms.txt"
PROVENANCE_FILENAME: Final = "provenance.json"

NOTICE_FILENAMES: Final = (
    "LICENSE.md",
    "GPLv3.txt",
    "LGPLv2.1.txt",
    "LGPLv3.txt",
    "MPL-1.1.txt",
    "README.txt",
)
EXTRACTED_FILENAMES: Final = ("es.dic", "es.aff", *NOTICE_FILENAMES)
BUNDLE_FILENAMES: Final = (
    RESOURCE_ASSET_NAME,
    "es.dic",
    "es.aff",
    SURFACE_FILENAME,
    *NOTICE_FILENAMES,
    PROVENANCE_FILENAME,
)

MAX_ARCHIVE_MEMBERS: Final = 128
MAX_ARCHIVE_UNCOMPRESSED_BYTES: Final = 64 * 1024 * 1024
MAX_MEMBER_UNCOMPRESSED_BYTES: Final = 16 * 1024 * 1024
MAX_METADATA_BYTES: Final = 2 * 1024 * 1024

_EXPECTED_ENVIRONMENT: Final = {
    "architecture": "aarch64",
    "os": "debian:12",
    "bash": "5.2.15(1)-release",
    "grep": "3.8",
    "awk": "1.3.4",
    "sort": "9.1",
    "locale": "UTF-8",
    "gcc": "12.2.0",
    "gxx": "12.2.0",
    "make": "4.3",
    "hunspell": "1.7.3",
    "wordforms_installed": "true",
}

_ALLOWED_AFFIX_DIRECTIVES: Final = frozenset(
    {
        "AF",
        "AM",
        "CHECKSHARPS",
        "FLAG",
        "FORBIDDENWORD",
        "HOME",
        "KEEPCASE",
        "KEY",
        "LANG",
        "MAP",
        "MAXDIFF",
        "MAXNGRAMSUGS",
        "NAME",
        "NOSPLITSUGS",
        "NOSUGGEST",
        "ONLYMAXDIFF",
        "PFX",
        "PHONE",
        "REP",
        "SET",
        "SFX",
        "SUGSWITHDOTS",
        "TRY",
        "VERSION",
        "WORDCHARS",
    }
)
_BLOCKED_AFFIX_DIRECTIVES: Final = frozenset(
    {
        "BREAK",
        "CIRCUMFIX",
        "COMPLEXPREFIXES",
        "FORCEUCASE",
        "FULLSTRIP",
        "ICONV",
        "IGNORE",
        "NEEDAFFIX",
        "OCONV",
        "ONLYINCOMPOUND",
    }
)
_QUERY_REGEX_META: Final = re.compile(r"[.\\[\]{}()*+?^$|\\]")

SUMMARY_KEYS: Final = (
    "resource_release",
    "resource_source_commit",
    "selected_license_pathway",
    "source_download_runs",
    "source_exact_byte_identity",
    "archive_safety_passed",
    "approved_extracted_member_count",
    "unexpected_archive_member_count",
    "notice_byte_preservation_passed",
    "affix_capability_supported",
    "unsupported_capability_count",
    "generation_runs",
    "generated_entry_count",
    "generated_exact_byte_identity",
    "direct_hunspell_acceptance_passed",
    "bundle_entry_count",
    "bundle_layout_passed",
    "git_ignored",
    "untracked",
    "unstaged",
    "atomic_promotion_passed",
    "no_corpus_access",
)

PROVENANCE_KEYS: Final = (
    "schema_version",
    "resource_id",
    "resource_role",
    "upstream_project",
    "upstream_release",
    "upstream_tag_object",
    "upstream_source_commit",
    "release_asset_id",
    "release_asset_name",
    "release_asset_url",
    "release_asset_content_type",
    "release_asset_public_size",
    "selected_license_pathway",
    "required_notice_filenames",
    "notice_mapping",
    "container_platform",
    "container_reference",
    "hunspell_release",
    "hunspell_source_commit",
    "generation_runner_commit",
    "character_encoding",
    "sort_locale",
    "source_download_results",
    "source_asset_hashes",
    "source_exact_byte_identity",
    "package_safety_results",
    "extracted_file_hashes",
    "notice_byte_preservation_results",
    "affix_capability_results",
    "generation_run_results",
    "generated_artifact_hashes",
    "generated_exact_byte_identity",
    "aggregate_structural_results",
    "bundle_layout_results",
    "git_ignore_results",
    "atomic_promotion_results",
    "procedure_document_commit",
)


class BundleBuildError(RuntimeError):
    """A fail-closed error whose text never contains private values."""


class UnsupportedCapabilityError(BundleBuildError):
    """The real package uses behavior outside the reviewed generation subset."""

    def __init__(self, count: int):
        super().__init__()
        self.count = count


@dataclass(frozen=True)
class LiveAssetIdentity:
    """Verified public release-asset fields only."""

    download_url: str
    publisher_digest: str | None


@dataclass(frozen=True)
class PackageExtraction:
    """Aggregate package facts plus private extracted bytes."""

    approved_member_count: int
    unexpected_member_count: int
    files: dict[str, bytes] = field(repr=False, compare=False)


@dataclass(frozen=True)
class CapabilityAudit:
    """Aggregate capability facts plus private query words."""

    dictionary_entry_count: int
    affix_rule_count: int
    unsupported_capability_count: int
    query_words: tuple[str, ...] = field(repr=False)
    flagged_query_words: tuple[str, ...] = field(repr=False)


@dataclass(frozen=True)
class GeneratedListStats:
    """Content-free facts for one canonical generated list."""

    entry_count: int
    byte_count: int


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _request_bytes(url: str, *, maximum_bytes: int) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "neu-lab"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read(maximum_bytes + 1)
    except (OSError, TimeoutError):
        raise BundleBuildError from None
    if not data or len(data) > maximum_bytes:
        raise BundleBuildError
    return data


def _request_json(url: str) -> dict[str, object]:
    try:
        document = json.loads(
            _request_bytes(url, maximum_bytes=MAX_METADATA_BYTES).decode("utf-8")
        )
    except (UnicodeError, json.JSONDecodeError):
        raise BundleBuildError from None
    if not isinstance(document, dict):
        raise BundleBuildError
    return document


def _verify_live_identity(
    release: dict[str, object],
    tag_ref: dict[str, object],
    tag: dict[str, object],
) -> LiveAssetIdentity:
    if release.get("tag_name") != RESOURCE_RELEASE:
        raise BundleBuildError
    assets = release.get("assets")
    if not isinstance(assets, list):
        raise BundleBuildError
    matches = [
        asset
        for asset in assets
        if isinstance(asset, dict) and asset.get("id") == RESOURCE_ASSET_ID
    ]
    if len(matches) != 1:
        raise BundleBuildError
    asset = matches[0]
    expected_asset = {
        "name": RESOURCE_ASSET_NAME,
        "size": RESOURCE_ASSET_SIZE,
        "content_type": RESOURCE_ASSET_CONTENT_TYPE,
        "browser_download_url": RESOURCE_ASSET_URL,
    }
    if any(asset.get(key) != value for key, value in expected_asset.items()):
        raise BundleBuildError

    ref_object = tag_ref.get("object")
    tag_object = tag.get("object")
    if not isinstance(ref_object, dict) or not isinstance(tag_object, dict):
        raise BundleBuildError
    if ref_object.get("type") != "tag" or ref_object.get("sha") != RESOURCE_TAG_OBJECT:
        raise BundleBuildError
    if tag.get("sha") != RESOURCE_TAG_OBJECT:
        raise BundleBuildError
    if tag_object.get("type") != "commit" or tag_object.get("sha") != RESOURCE_SOURCE_COMMIT:
        raise BundleBuildError

    digest = asset.get("digest")
    if digest is not None and (
        not isinstance(digest, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", digest) is None
    ):
        raise BundleBuildError
    return LiveAssetIdentity(RESOURCE_ASSET_URL, digest)


def _fetch_live_identity() -> LiveAssetIdentity:
    release = _request_json(RESOURCE_RELEASE_API)
    tag_ref = _request_json(RESOURCE_TAG_REF_API)
    tag = _request_json(RESOURCE_TAG_API_PREFIX + RESOURCE_TAG_OBJECT)
    return _verify_live_identity(release, tag_ref, tag)


def _download_asset(identity: LiveAssetIdentity) -> bytes:
    data = _request_bytes(identity.download_url, maximum_bytes=RESOURCE_ASSET_SIZE)
    if len(data) != RESOURCE_ASSET_SIZE:
        raise BundleBuildError
    digest = _sha256(data)
    if identity.publisher_digest is not None and identity.publisher_digest != f"sha256:{digest}":
        raise BundleBuildError
    return data


def _safe_zip_member(info: zipfile.ZipInfo) -> None:
    name = info.filename
    relative = PurePosixPath(name)
    if (
        not name
        or "\x00" in name
        or "\\" in name
        or relative.is_absolute()
        or ".." in relative.parts
        or any(part in {"", "."} for part in relative.parts)
        or info.flag_bits & 0x1
    ):
        raise BundleBuildError
    mode = (info.external_attr >> 16) & 0xFFFF
    file_type = stat.S_IFMT(mode)
    allowed_types = {0, stat.S_IFREG, stat.S_IFDIR}
    if info.create_system == 3 and file_type not in allowed_types:
        raise BundleBuildError
    if info.file_size < 0 or info.file_size > MAX_MEMBER_UNCOMPRESSED_BYTES:
        raise BundleBuildError


def _extract_approved_members(package: bytes, destination: Path) -> PackageExtraction:
    if destination.exists() or destination.is_symlink():
        raise BundleBuildError
    try:
        with zipfile.ZipFile(io.BytesIO(package), "r") as archive:
            infos = archive.infolist()
            if not infos or len(infos) > MAX_ARCHIVE_MEMBERS:
                raise BundleBuildError
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                raise BundleBuildError
            for info in infos:
                _safe_zip_member(info)
            if sum(info.file_size for info in infos) > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                raise BundleBuildError
            by_name = {info.filename: info for info in infos}
            if any(name not in by_name for name in EXTRACTED_FILENAMES):
                raise BundleBuildError
            files: dict[str, bytes] = {}
            for name in EXTRACTED_FILENAMES:
                info = by_name[name]
                if info.is_dir() or PurePosixPath(name).parent != PurePosixPath("."):
                    raise BundleBuildError
                data = archive.read(info)
                if not data:
                    raise BundleBuildError
                files[name] = data
    except (OSError, RuntimeError, zipfile.BadZipFile, zipfile.LargeZipFile):
        raise BundleBuildError from None

    destination.mkdir()
    for name, data in files.items():
        path = destination / name
        path.write_bytes(data)
        if path.is_symlink() or not path.is_file():
            raise BundleBuildError
    return PackageExtraction(
        approved_member_count=len(files),
        unexpected_member_count=len(infos) - len(files),
        files=files,
    )


def _strict_utf8_lines(data: bytes) -> list[str]:
    if not data or b"\x00" in data:
        raise BundleBuildError
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeError:
        raise BundleBuildError from None
    lines = text.splitlines()
    if not lines:
        raise BundleBuildError
    return lines


def _audit_dictionary_pair(dictionary: bytes, affix: bytes) -> CapabilityAudit:
    affix_lines = _strict_utf8_lines(affix)
    meaningful = [
        line.strip()
        for line in affix_lines
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not meaningful or meaningful[0] != "SET UTF-8":
        raise BundleBuildError

    unsupported = 0
    affix_rule_count = 0
    for line in meaningful:
        parts = line.split()
        directive = parts[0]
        if directive.startswith("COMPOUND") or directive in _BLOCKED_AFFIX_DIRECTIVES:
            unsupported += 1
            continue
        if directive not in _ALLOWED_AFFIX_DIRECTIVES:
            unsupported += 1
            continue
        if directive in {"PFX", "SFX"} and len(parts) >= 5:
            affix_rule_count += 1
            if "/" in parts[3]:
                unsupported += 1

    dictionary_lines = _strict_utf8_lines(dictionary)
    if not dictionary_lines[0].isdigit():
        raise BundleBuildError
    entries = dictionary_lines[1:]
    if int(dictionary_lines[0]) != len(entries) or not entries:
        raise BundleBuildError

    query_words: list[str] = []
    flagged_query_words: list[str] = []
    for entry in entries:
        if not entry or entry != entry.strip() or "\\" in entry:
            raise BundleBuildError
        lexical = entry.split("\t", 1)[0]
        lexical_parts = lexical.split("/")
        if len(lexical_parts) > 2 or (len(lexical_parts) == 2 and not lexical_parts[1]):
            raise BundleBuildError
        word = lexical_parts[0]
        if not word or any(char.isspace() for char in word):
            raise BundleBuildError
        if _QUERY_REGEX_META.search(word):
            unsupported += 1
        query_words.append(word)
        if len(lexical_parts) == 2:
            flagged_query_words.append(word)
    if len(query_words) != len(set(query_words)):
        raise BundleBuildError
    return CapabilityAudit(
        dictionary_entry_count=len(entries),
        affix_rule_count=affix_rule_count,
        unsupported_capability_count=unsupported,
        query_words=tuple(query_words),
        flagged_query_words=tuple(flagged_query_words),
    )


def _write_queries(path: Path, query_words: tuple[str, ...]) -> None:
    data = "".join(f"{word}\n" for word in query_words).encode("utf-8")
    path.write_bytes(data)


def _base_docker_args() -> list[str]:
    return [
        "docker",
        "run",
        "--rm",
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
        "/tmp:rw,nosuid,nodev,noexec,size=256m",
        "-e",
        "LANG=C.UTF-8",
        "-e",
        "LC_ALL=C.UTF-8",
    ]


def _run(command: list[str], *, timeout: int = 900) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        raise BundleBuildError from None


def _download_hunspell_source(archive_path: Path) -> None:
    data = _request_bytes(HUNSPELL_ARCHIVE_URL, maximum_bytes=16 * 1024 * 1024)
    if _sha256(data) != HUNSPELL_ARCHIVE_SHA256:
        raise BundleBuildError
    archive_path.write_bytes(data)


def _extract_hunspell_source(archive_path: Path, destination: Path) -> Path:
    try:
        with tarfile.open(archive_path, "r:gz") as archive:
            members = archive.getmembers()
            for member in members:
                relative = PurePosixPath(member.name)
                if relative.is_absolute() or ".." in relative.parts:
                    raise BundleBuildError
                if not (member.isdir() or member.isfile()):
                    raise BundleBuildError
            archive.extractall(destination, members=members, filter="data")
    except (OSError, tarfile.TarError):
        raise BundleBuildError from None
    source_dir = destination / "hunspell-1.7.3"
    if source_dir.is_symlink() or not source_dir.is_dir():
        raise BundleBuildError
    if not (source_dir / "configure").is_file():
        raise BundleBuildError
    if not (source_dir / "src" / "tools" / "wordforms").is_file():
        raise BundleBuildError
    return source_dir


def _build_hunspell(source_dir: Path, install_dir: Path) -> None:
    install_dir.mkdir()
    _run(["docker", "pull", "--platform", CONTAINER_PLATFORM, CONTAINER_REFERENCE])
    command = _base_docker_args() + [
        "--mount",
        f"type=bind,src={source_dir},dst=/src",
        "--mount",
        f"type=bind,src={install_dir},dst=/install",
        "-w",
        "/src",
        CONTAINER_REFERENCE,
        "bash",
        "-lc",
        "./configure --prefix=/install >/tmp/configure.log 2>&1 "
        "&& make -j2 >/tmp/make.log 2>&1 "
        "&& make install >/tmp/install.log 2>&1 "
        "&& test -x /install/bin/hunspell "
        "&& test -x /install/bin/wordforms",
    ]
    _run(command)


def _inspect_environment(install_dir: Path) -> dict[str, str]:
    script = r"""
set -euo pipefail
export PATH=/opt/hunspell/bin:$PATH
export LD_LIBRARY_PATH=/opt/hunspell/lib
. /etc/os-release
printf 'architecture=%s\n' "$(uname -m)"
printf 'os=%s:%s\n' "$ID" "$VERSION_ID"
printf 'bash=%s\n' "$BASH_VERSION"
printf 'grep=%s\n' "$(grep --version | head -n1 | awk '{print $NF}')"
printf 'awk=%s\n' "$(awk -W version 2>&1 | head -n1 | awk '{print $2}')"
printf 'sort=%s\n' "$(sort --version | head -n1 | awk '{print $NF}')"
printf 'locale=%s\n' "$(locale charmap)"
printf 'gcc=%s\n' "$(gcc -dumpfullversion)"
printf 'gxx=%s\n' "$(g++ -dumpfullversion)"
printf 'make=%s\n' "$(make --version | head -n1 | awk '{print $3}')"
hunspell_version="$(hunspell --version | head -n1 | sed -n 's/.*Hunspell \([0-9.]*\)).*/\1/p')"
printf 'hunspell=%s\n' "$hunspell_version"
test -x /opt/hunspell/bin/wordforms
printf 'wordforms_installed=true\n'
"""
    command = _base_docker_args() + [
        "--mount",
        f"type=bind,src={install_dir},dst=/opt/hunspell,readonly",
        CONTAINER_REFERENCE,
        "bash",
        "-lc",
        script,
    ]
    result = _run(command)
    observed: dict[str, str] = {}
    for line in result.stdout.splitlines():
        if "=" not in line:
            raise BundleBuildError
        key, value = line.split("=", 1)
        if key in observed or not key or not value:
            raise BundleBuildError
        observed[key] = value
    if observed != _EXPECTED_ENVIRONMENT:
        raise BundleBuildError
    return observed


_GENERATION_SCRIPT: Final = r"""#!/usr/bin/env bash
set -euo pipefail
export PATH=/opt/hunspell/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export LD_LIBRARY_PATH=/opt/hunspell/lib
export LANG=C.UTF-8
export LC_ALL=C.UTF-8
cd /fixture
test -f es.aff
test -f es.dic
test -f queries.txt
test -f flagged_queries.txt
cp queries.txt /tmp/generated.unsorted
while IFS= read -r word; do
    wordforms es.aff es.dic "$word"
done < flagged_queries.txt >> /tmp/generated.unsorted
LC_ALL=C sort -u /tmp/generated.unsorted > /output/generated.txt
hunspell -d /fixture/es -G -l < /output/generated.txt \
    | LC_ALL=C sort -u > /output/accepted.txt
"""


def _run_generation(fixture_dir: Path, install_dir: Path, output_dir: Path) -> None:
    output_dir.mkdir()
    command = _base_docker_args() + [
        "--mount",
        f"type=bind,src={fixture_dir},dst=/fixture,readonly",
        "--mount",
        f"type=bind,src={install_dir},dst=/opt/hunspell,readonly",
        "--mount",
        f"type=bind,src={output_dir},dst=/output",
        "-w",
        "/fixture",
        CONTAINER_REFERENCE,
        "bash",
        "/fixture/run_generation.sh",
    ]
    _run(command)


def _validate_generated_list(data: bytes) -> GeneratedListStats:
    if not data or not data.endswith(b"\n") or b"\r" in data or b"\x00" in data:
        raise BundleBuildError
    try:
        text = data.decode("utf-8", errors="strict")
    except UnicodeError:
        raise BundleBuildError from None
    lines = text.splitlines()
    if not lines or any(not line or line != line.strip() for line in lines):
        raise BundleBuildError
    encoded_lines = [line.encode("utf-8") for line in lines]
    if encoded_lines != sorted(set(encoded_lines)):
        raise BundleBuildError
    return GeneratedListStats(entry_count=len(lines), byte_count=len(data))


def _write_generation_fixture(
    directory: Path,
    extraction: PackageExtraction,
    audit: CapabilityAudit,
) -> None:
    directory.mkdir()
    for name in ("es.dic", "es.aff"):
        (directory / name).write_bytes(extraction.files[name])
    _write_queries(directory / "queries.txt", audit.query_words)
    _write_queries(
        directory / "flagged_queries.txt", audit.flagged_query_words
    )
    (directory / "run_generation.sh").write_text(
        _GENERATION_SCRIPT, encoding="utf-8", newline="\n"
    )
    (directory / "run_generation.sh").chmod(0o755)


def _deterministic_json(document: dict[str, object]) -> bytes:
    try:
        text = json.dumps(document, sort_keys=True, indent=2, ensure_ascii=True)
        return (text + "\n").encode("utf-8")
    except (TypeError, ValueError):
        raise BundleBuildError from None


def _validate_bundle(directory: Path) -> None:
    if directory.is_symlink() or not directory.is_dir():
        raise BundleBuildError
    try:
        entries = list(directory.iterdir())
    except OSError:
        raise BundleBuildError from None
    if {entry.name for entry in entries} != set(BUNDLE_FILENAMES):
        raise BundleBuildError
    if len(entries) != len(BUNDLE_FILENAMES):
        raise BundleBuildError
    if any(entry.is_symlink() or not entry.is_file() for entry in entries):
        raise BundleBuildError


def _git_output(arguments: list[str]) -> str:
    result = _run(["git", *arguments], timeout=60)
    return result.stdout.strip()


def _git_pathspec(path: Path) -> str:
    try:
        return path.absolute().relative_to(project_root()).as_posix()
    except ValueError:
        raise BundleBuildError from None


def _require_repository_gate(root: Path, target: Path) -> str:
    if root != project_root() or target.exists() or target.is_symlink():
        raise BundleBuildError
    if _git_output(["status", "--porcelain", "--untracked-files=all"]):
        raise BundleBuildError
    if _git_output(["branch", "--show-current"]) != EXECUTION_BRANCH:
        raise BundleBuildError
    head = _git_output(["rev-parse", "HEAD"])
    if re.fullmatch(r"[0-9a-f]{40}", head) is None:
        raise BundleBuildError
    _run(["git", "merge-base", "--is-ancestor", APPROVAL_DOCUMENT_COMMIT, "HEAD"], timeout=60)
    _run(["git", "merge-base", "--is-ancestor", APPROVAL_MERGE_COMMIT, "HEAD"], timeout=60)
    ignored = subprocess.run(
        ["git", "check-ignore", "--no-index", "--quiet", _git_pathspec(target)],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    if ignored.returncode != 0:
        raise BundleBuildError
    return head


def _git_boundary_results(target: Path) -> tuple[bool, bool, bool]:
    pathspec = _git_pathspec(target)
    ignored = subprocess.run(
        ["git", "check-ignore", "--no-index", "--quiet", pathspec],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    ).returncode == 0
    tracked = _git_output(["ls-files", "--", pathspec])
    staged = _git_output(["diff", "--cached", "--name-only", "--", pathspec])
    return ignored, not bool(tracked), not bool(staged)


def _prepare_target_parent(root: Path, target: Path) -> Path:
    try:
        relative_parent = target.relative_to(root).parent
    except ValueError:
        raise BundleBuildError from None
    current = root
    for part in relative_parent.parts:
        current = current / part
        if current.is_symlink():
            raise BundleBuildError
        if current.exists():
            if not current.is_dir():
                raise BundleBuildError
        else:
            current.mkdir()
    return current


def _assemble_staging_bundle(
    staging: Path,
    *,
    package: bytes,
    extraction: PackageExtraction,
    generated: bytes,
    provenance: dict[str, object],
) -> None:
    if staging.is_symlink() or not staging.is_dir():
        raise BundleBuildError
    if any(staging.iterdir()):
        raise BundleBuildError
    (staging / RESOURCE_ASSET_NAME).write_bytes(package)
    for name in EXTRACTED_FILENAMES:
        (staging / name).write_bytes(extraction.files[name])
    (staging / SURFACE_FILENAME).write_bytes(generated)
    (staging / PROVENANCE_FILENAME).write_bytes(_deterministic_json(provenance))
    _validate_bundle(staging)


def _atomic_promote(staging: Path, target: Path) -> None:
    if target.exists() or target.is_symlink():
        raise BundleBuildError
    if staging.parent != target.parent:
        raise BundleBuildError
    try:
        staging.rename(target)
    except OSError:
        raise BundleBuildError from None
    _validate_bundle(target)


def _build_provenance(
    *,
    runner_commit: str,
    identity: LiveAssetIdentity,
    downloads: tuple[bytes, bytes],
    extraction: PackageExtraction,
    generated_runs: tuple[bytes, bytes],
    generated_stats: GeneratedListStats,
    unexpected_member_count: int,
) -> dict[str, object]:
    extracted_hashes = {name: _sha256(extraction.files[name]) for name in EXTRACTED_FILENAMES}
    generated_hashes = [_sha256(data) for data in generated_runs]
    notice_mapping = {
        RESOURCE_ASSET_NAME: list(NOTICE_FILENAMES),
        "es.dic": ["LICENSE.md", "MPL-1.1.txt", "README.txt"],
        "es.aff": ["LICENSE.md", "MPL-1.1.txt", "README.txt"],
        SURFACE_FILENAME: ["LICENSE.md", "MPL-1.1.txt", "README.txt"],
    }
    document: dict[str, object] = {
        "schema_version": 1,
        "resource_id": RESOURCE_ID,
        "resource_role": "broad_pan_regional_lexical_coverage_diagnostic_only",
        "upstream_project": "RLA-ES",
        "upstream_release": RESOURCE_RELEASE,
        "upstream_tag_object": RESOURCE_TAG_OBJECT,
        "upstream_source_commit": RESOURCE_SOURCE_COMMIT,
        "release_asset_id": RESOURCE_ASSET_ID,
        "release_asset_name": RESOURCE_ASSET_NAME,
        "release_asset_url": identity.download_url,
        "release_asset_content_type": RESOURCE_ASSET_CONTENT_TYPE,
        "release_asset_public_size": RESOURCE_ASSET_SIZE,
        "selected_license_pathway": SELECTED_LICENSE_PATHWAY,
        "required_notice_filenames": list(NOTICE_FILENAMES),
        "notice_mapping": notice_mapping,
        "container_platform": CONTAINER_PLATFORM,
        "container_reference": CONTAINER_REFERENCE,
        "hunspell_release": HUNSPELL_RELEASE,
        "hunspell_source_commit": HUNSPELL_COMMIT,
        "generation_runner_commit": runner_commit,
        "character_encoding": "UTF-8",
        "sort_locale": "C",
        "source_download_results": {"runs": 2, "public_identity_verified": True},
        "source_asset_hashes": [_sha256(data) for data in downloads],
        "source_exact_byte_identity": downloads[0] == downloads[1],
        "package_safety_results": {
            "passed": True,
            "approved_member_count": len(EXTRACTED_FILENAMES),
            "unexpected_member_count": unexpected_member_count,
        },
        "extracted_file_hashes": extracted_hashes,
        "notice_byte_preservation_results": {"passed": True, "notice_count": len(NOTICE_FILENAMES)},
        "affix_capability_results": {
            "passed": True,
            "unsupported_count": 0,
        },
        "generation_run_results": {
            "runs": 2,
            "entry_count": generated_stats.entry_count,
            "direct_hunspell_acceptance_passed": True,
        },
        "generated_artifact_hashes": generated_hashes,
        "generated_exact_byte_identity": generated_runs[0] == generated_runs[1],
        "aggregate_structural_results": {
            "entry_count": generated_stats.entry_count,
            "byte_count": generated_stats.byte_count,
            "passed": True,
        },
        "bundle_layout_results": {"entry_count": len(BUNDLE_FILENAMES), "passed": True},
        "git_ignore_results": {"ignored": True, "tracked": False, "staged": False},
        "atomic_promotion_results": {
            "method": "same_filesystem_rename",
            "target_absent": True,
            "promotion_pending_at_record_creation": True,
        },
        "procedure_document_commit": APPROVAL_DOCUMENT_COMMIT,
    }
    if tuple(document) != PROVENANCE_KEYS:
        raise BundleBuildError
    return document


def _execute() -> dict[str, object]:
    root = project_root()
    target = root / BUNDLE_RELATIVE_PATH
    runner_commit = _require_repository_gate(root, target)

    with tempfile.TemporaryDirectory(prefix="neu-lab-rla-es-build-") as raw_work:
        work = Path(raw_work)
        identity = _fetch_live_identity()
        source_one = work / "source_one"
        source_two = work / "source_two"
        source_one.mkdir()
        source_two.mkdir()
        download_one = _download_asset(identity)
        (source_one / RESOURCE_ASSET_NAME).write_bytes(download_one)
        download_two = _download_asset(identity)
        (source_two / RESOURCE_ASSET_NAME).write_bytes(download_two)
        if download_one != download_two:
            raise BundleBuildError

        extraction_one = _extract_approved_members(download_one, work / "extract_one")
        extraction_two = _extract_approved_members(download_two, work / "extract_two")
        if extraction_one.files != extraction_two.files:
            raise BundleBuildError
        if extraction_one.unexpected_member_count != extraction_two.unexpected_member_count:
            raise BundleBuildError

        audit_one = _audit_dictionary_pair(
            extraction_one.files["es.dic"], extraction_one.files["es.aff"]
        )
        audit_two = _audit_dictionary_pair(
            extraction_two.files["es.dic"], extraction_two.files["es.aff"]
        )
        if audit_one != audit_two:
            raise BundleBuildError
        if audit_one.unsupported_capability_count:
            raise UnsupportedCapabilityError(audit_one.unsupported_capability_count)

        hunspell_archive = work / HUNSPELL_ARCHIVE_NAME
        _download_hunspell_source(hunspell_archive)
        source_dir = _extract_hunspell_source(hunspell_archive, work / "hunspell_source")
        install_dir = work / "hunspell_install"
        _build_hunspell(source_dir, install_dir)
        _inspect_environment(install_dir)

        fixture_one = work / "fixture_one"
        fixture_two = work / "fixture_two"
        _write_generation_fixture(fixture_one, extraction_one, audit_one)
        _write_generation_fixture(fixture_two, extraction_two, audit_two)
        run_one = work / "run_one"
        run_two = work / "run_two"
        _run_generation(fixture_one, install_dir, run_one)
        _run_generation(fixture_two, install_dir, run_two)
        generated_one = (run_one / "generated.txt").read_bytes()
        generated_two = (run_two / "generated.txt").read_bytes()
        accepted_one = (run_one / "accepted.txt").read_bytes()
        accepted_two = (run_two / "accepted.txt").read_bytes()
        stats = _validate_generated_list(generated_one)
        direct_acceptance = (
            accepted_one == generated_one and accepted_two == generated_two
        )
        if generated_one != generated_two or not direct_acceptance:
            raise BundleBuildError

        target_parent = _prepare_target_parent(root, target)
        staging = Path(tempfile.mkdtemp(prefix=".rla-es-staging-", dir=target_parent))
        try:
            provenance = _build_provenance(
                runner_commit=runner_commit,
                identity=identity,
                downloads=(download_one, download_two),
                extraction=extraction_one,
                generated_runs=(generated_one, generated_two),
                generated_stats=stats,
                unexpected_member_count=extraction_one.unexpected_member_count,
            )
            _assemble_staging_bundle(
                staging,
                package=download_one,
                extraction=extraction_one,
                generated=generated_one,
                provenance=provenance,
            )
            ignored, untracked, unstaged = _git_boundary_results(staging)
            if not all((ignored, untracked, unstaged)):
                raise BundleBuildError
            _atomic_promote(staging, target)
        finally:
            if staging.exists():
                shutil.rmtree(staging)

    ignored, untracked, unstaged = _git_boundary_results(target)
    if not all((ignored, untracked, unstaged)):
        raise BundleBuildError
    summary: dict[str, object] = {
        "resource_release": RESOURCE_RELEASE,
        "resource_source_commit": RESOURCE_SOURCE_COMMIT,
        "selected_license_pathway": SELECTED_LICENSE_PATHWAY,
        "source_download_runs": 2,
        "source_exact_byte_identity": True,
        "archive_safety_passed": True,
        "approved_extracted_member_count": len(EXTRACTED_FILENAMES),
        "unexpected_archive_member_count": extraction_one.unexpected_member_count,
        "notice_byte_preservation_passed": True,
        "affix_capability_supported": True,
        "unsupported_capability_count": 0,
        "generation_runs": 2,
        "generated_entry_count": stats.entry_count,
        "generated_exact_byte_identity": True,
        "direct_hunspell_acceptance_passed": True,
        "bundle_entry_count": len(BUNDLE_FILENAMES),
        "bundle_layout_passed": True,
        "git_ignored": ignored,
        "untracked": untracked,
        "unstaged": unstaged,
        "atomic_promotion_passed": True,
        "no_corpus_access": True,
    }
    if tuple(summary) != SUMMARY_KEYS:
        raise BundleBuildError
    return summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the approved private RLA-ES lexical bundle."
    )
    parser.add_argument(
        "--allow-rla-es-bundle-build",
        action="store_true",
        help="explicitly allow the approved private acquisition and generation run",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if not args.allow_rla_es_bundle_build:
        print(_OPT_IN_MESSAGE, file=sys.stderr)
        return EXIT_OPT_IN_REQUIRED
    try:
        summary = _execute()
    except UnsupportedCapabilityError as exc:
        safe_stop = {
            "gate": "STOP",
            "unsupported_capability_count": exc.count,
            "bundle_promoted": False,
        }
        print(json.dumps(safe_stop, separators=(",", ":")), file=sys.stderr)
        return EXIT_UNSUPPORTED_CAPABILITY
    except (Exception, KeyboardInterrupt):
        print(_ABORT_MESSAGE, file=sys.stderr)
        return EXIT_OPERATIONAL_ABORT
    print(json.dumps(summary, ensure_ascii=True, separators=(",", ":")))
    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
