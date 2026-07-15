"""Controlled loader for the approved local English SCOWL resource bundle.

This module loads **one** fixed, approved, Git-ignored local resource bundle and
returns its **raw** entries. It is deliberately narrow:

* it takes **no caller path** — the approved bundle location is fixed by this
  module and resolved relative to the project root (never a hard-coded absolute
  path);
* it **never writes**, creates directories, downloads, or falls back to another
  location;
* it **never reads CALLHOME**, never validates rows, never promotes rows, and is
  **not wired** into any script or pipeline;
* it performs **no normalization** — no Unicode normalization, no case folding,
  no token normalization, no vocabulary expansion, no fallback substitution.
  Entries are returned verbatim so that a future validator can normalize lexicon
  entries and utterance tokens *identically*
  (``docs/callhome_lexicon_normalization_policy.md``).

The approved bundle, its contents, and its hashes remain **local and
Git-ignored** (``docs/callhome_english_scowl_artifact_approval.md``). Nothing in
this module prints, returns, or logs lexical entries, hashes, provenance values,
notice contents, or filesystem paths.

Governing records:

* ``docs/english_scowl_loader_contract.md`` (this module's contract)
* ``docs/callhome_english_scowl_artifact_approval.md`` (approved resource)
* ``docs/callhome_english_scowl_operationalization_approval.md`` (bundle layout,
  provenance schema)
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import InitVar, dataclass, field
from pathlib import Path
from typing import Final

from cslm.utils.paths import project_root

# --------------------------------------------------------------------------- #
# Approved identity (fixed by this module; never caller-supplied).
# --------------------------------------------------------------------------- #

RESOURCE_ID: Final[str] = "english_scowl_esdb_en_us"
ARTIFACT_FILENAME: Final[str] = "scowl_en_US_size60_var1.txt"
NOTICE_FILENAME: Final[str] = "SCOWL-COPYRIGHT.txt"
PROVENANCE_FILENAME: Final[str] = "provenance.json"

REQUIRED_BUNDLE_FILENAMES: Final[frozenset[str]] = frozenset(
    {ARTIFACT_FILENAME, NOTICE_FILENAME, PROVENANCE_FILENAME}
)

PROVENANCE_SCHEMA_VERSION: Final[int] = 1

# Provenance field names are public schema constants (safe to name in errors);
# their *values* are never echoed.
_FIELD_SCHEMA_VERSION: Final[str] = "schema_version"
_FIELD_RESOURCE_ID: Final[str] = "resource_id"
_FIELD_ARTIFACT_FILENAME: Final[str] = "artifact_filename"
_FIELD_NOTICE_FILENAME: Final[str] = "preserved_notice_filename"
_FIELD_ARTIFACT_SHA256: Final[str] = "artifact_SHA256"

# Approved provenance identity subset. Unknown provenance keys are ignored.
_APPROVED_STRING_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    (_FIELD_RESOURCE_ID, RESOURCE_ID),
    (_FIELD_ARTIFACT_FILENAME, ARTIFACT_FILENAME),
    (_FIELD_NOTICE_FILENAME, NOTICE_FILENAME),
)

_BUNDLE_RELPATH: Final[Path] = (
    Path("data") / "resources" / "local_lexicons" / "english" / RESOURCE_ID
)

_SHA256_HEX_RE: Final[re.Pattern[str]] = re.compile(r"[0-9a-f]{64}")


# --------------------------------------------------------------------------- #
# Typed, resource-specific exceptions.
#
# Every message is built only from module constants and aggregate integers. No
# message contains a filesystem path, a lexical entry, a hash, a provenance
# value, notice content, an unexpected local filename, or a line number.
# --------------------------------------------------------------------------- #


class EnglishScowlResourceError(RuntimeError):
    """Base class for every approved English SCOWL resource failure."""


class EnglishScowlBundleMissingError(EnglishScowlResourceError):
    """The approved bundle cannot be located.

    Raised when the project root cannot be resolved, or when the bundle path is
    absent, is not a directory, or is a symlink.
    """


class EnglishScowlBundleLayoutError(EnglishScowlResourceError):
    """The approved bundle does not contain exactly the three approved files."""


class EnglishScowlProvenanceError(EnglishScowlResourceError):
    """The approved provenance record is unreadable or fails identity checks."""


class EnglishScowlArtifactError(EnglishScowlResourceError):
    """The approved artifact is unreadable or violates its strict format."""


class EnglishScowlIntegrityError(EnglishScowlResourceError):
    """The artifact bytes do not match the SHA-256 recorded in provenance."""


# --------------------------------------------------------------------------- #
# Returned value.
# --------------------------------------------------------------------------- #


# Module-private construction sentinel. It prevents **ordinary or accidental**
# construction of a forged lexicon; it is **not** a Python security boundary (the
# name is importable, and ``copy``/``pickle`` reconstruct without ``__init__``).
_CONSTRUCTION_TOKEN: Final[object] = object()


@dataclass(frozen=True)
class ApprovedEnglishScowl:
    """An approved, verified English SCOWL lexicon.

    Instances are produced **only** by :func:`load_approved_english_scowl`, which
    constructs them after the bundle layout, provenance identity, artifact
    format, and mandatory artifact hash have all been verified. Direct
    construction raises :class:`TypeError`: this type asserts that its entries
    *are* the approved artifact's, and that assertion must not be forgeable by
    ordinary construction. The guard is a module-private token — it stops
    ordinary or accidental construction, and is **not** a security boundary.

    ``TypeError`` (rather than an :class:`EnglishScowlResourceError`) is
    deliberate: misusing the constructor is an API error, not a resource
    condition, and must not be swallowed by a resource-failure handler.

    Holds **raw** entries only. It stores no filesystem path, and its
    representation reveals only the fixed approved resource identity and the
    aggregate entry count — never lexical entries.
    """

    entries: frozenset[str] = field(repr=False)
    _token: InitVar[object] = None

    def __post_init__(self, _token: object) -> None:
        # The token is checked first so a forged construction reports the useful
        # cause rather than a container-type complaint.
        if _token is not _CONSTRUCTION_TOKEN:
            raise TypeError(
                "ApprovedEnglishScowl cannot be constructed directly; "
                "use load_approved_english_scowl()"
            )
        # Exact type, not ``isinstance``: a frozenset subclass could override
        # membership. The loader always supplies an exact frozenset.
        if type(self.entries) is not frozenset:
            raise TypeError("ApprovedEnglishScowl entries must be a frozenset")

    @property
    def resource_id(self) -> str:
        """The approved resource identity (fixed by this module)."""
        return RESOURCE_ID

    @property
    def entry_count(self) -> int:
        """Number of approved entries (derived from ``entries``)."""
        return len(self.entries)

    def __repr__(self) -> str:
        # Defined explicitly so the dataclass-generated repr is not used; the
        # ``repr=False`` on ``entries`` keeps entries out of any repr regardless.
        return (
            f"{type(self).__name__}(resource_id={self.resource_id!r}, "
            f"entry_count={self.entry_count})"
        )


# --------------------------------------------------------------------------- #
# Private helpers.
# --------------------------------------------------------------------------- #


def _approved_bundle_dir() -> Path:
    """Resolve the approved bundle directory relative to the project root.

    Private on purpose: this is the module's only path-producing function and
    the only seam synthetic tests may replace. There is no public way to point
    the loader at an arbitrary directory.

    Known root-resolution failures are converted to a typed, privacy-safe error.
    The shared resolver reports the absolute filesystem path it started from, and
    that path must never escape this module.
    """
    try:
        root = project_root()
    except (OSError, RuntimeError):
        # Narrow on purpose: ``project_root`` signals "no marker found" with
        # RuntimeError and filesystem trouble with OSError, and both carry an
        # absolute path. Unrelated programming defects are deliberately *not*
        # caught, so they are never mislabelled as a missing resource.
        raise EnglishScowlBundleMissingError(
            "the approved bundle location could not be resolved because the "
            "project root was not found"
        ) from None
    return root / _BUNDLE_RELPATH


def _check_bundle_layout(bundle_dir: Path) -> None:
    """Require exactly the three approved regular, non-symlink files."""
    # Checked before ``is_dir()``, which would follow a symlink.
    if bundle_dir.is_symlink():
        raise EnglishScowlBundleMissingError("approved bundle path is a symlink")
    if not bundle_dir.is_dir():
        raise EnglishScowlBundleMissingError(
            "approved bundle directory is absent or is not a directory"
        )

    try:
        present = {entry.name for entry in bundle_dir.iterdir()}
    except OSError:
        raise EnglishScowlBundleLayoutError(
            "approved bundle directory could not be listed"
        ) from None

    missing = REQUIRED_BUNDLE_FILENAMES - present
    if missing:
        # Required filenames are public approved constants, so naming them is safe.
        raise EnglishScowlBundleLayoutError(
            "approved bundle is missing required file(s): " + ", ".join(sorted(missing))
        )

    unexpected = present - REQUIRED_BUNDLE_FILENAMES
    if unexpected:
        # Unexpected names may be personal; report an aggregate count only.
        raise EnglishScowlBundleLayoutError(
            f"approved bundle contains {len(unexpected)} unexpected filesystem "
            f"entries; exactly the {len(REQUIRED_BUNDLE_FILENAMES)} approved files "
            "are required"
        )

    for name in sorted(REQUIRED_BUNDLE_FILENAMES):
        path = bundle_dir / name
        if path.is_symlink():
            raise EnglishScowlBundleLayoutError(
                f"approved bundle entry {name!r} is a symlink"
            )
        if not path.is_file():
            raise EnglishScowlBundleLayoutError(
                f"approved bundle entry {name!r} is not a regular file"
            )


def _load_expected_artifact_hash(path: Path) -> str:
    """Validate the approved provenance identity subset; return the expected hash.

    Only the expected digest is returned, so provenance contents cannot travel
    further into this module. Unknown provenance keys are ignored.
    """
    try:
        raw = path.read_bytes()
    except OSError:
        raise EnglishScowlProvenanceError(
            "approved provenance file could not be read"
        ) from None

    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise EnglishScowlProvenanceError(
            "approved provenance file is not valid UTF-8"
        ) from None

    try:
        document = json.loads(text)
    except json.JSONDecodeError:
        raise EnglishScowlProvenanceError(
            "approved provenance file is not valid JSON"
        ) from None
    except RecursionError:
        # ``json.loads`` recurses once per nesting level. RecursionError is a
        # sibling of EnglishScowlResourceError under RuntimeError, so without
        # this it would escape this module's typed contract entirely.
        raise EnglishScowlProvenanceError(
            "approved provenance file is nested too deeply to parse"
        ) from None

    if not isinstance(document, dict):
        raise EnglishScowlProvenanceError(
            "approved provenance file is not a JSON object"
        )

    # ``type(...) is int`` rather than ``isinstance`` so JSON booleans (bool is a
    # subclass of int) are rejected.
    version = document.get(_FIELD_SCHEMA_VERSION)
    if type(version) is not int or version != PROVENANCE_SCHEMA_VERSION:
        raise EnglishScowlProvenanceError(
            f"approved provenance field {_FIELD_SCHEMA_VERSION!r} is missing or is "
            "not the approved value"
        )

    for field_name, approved_value in _APPROVED_STRING_FIELDS:
        value = document.get(field_name)
        if not isinstance(value, str) or value != approved_value:
            raise EnglishScowlProvenanceError(
                f"approved provenance field {field_name!r} is missing or is not the "
                "approved value"
            )

    digest = document.get(_FIELD_ARTIFACT_SHA256)
    if not isinstance(digest, str) or _SHA256_HEX_RE.fullmatch(digest) is None:
        raise EnglishScowlProvenanceError(
            f"approved provenance field {_FIELD_ARTIFACT_SHA256!r} is missing or is "
            "not a valid lowercase SHA-256 hex digest"
        )
    return digest


def _read_artifact_bytes(path: Path) -> bytes:
    """Read the approved artifact exactly once, as raw bytes."""
    try:
        return path.read_bytes()
    except OSError:
        raise EnglishScowlArtifactError("approved artifact could not be read") from None


def _parse_artifact_entries(data: bytes) -> list[str]:
    """Parse the approved artifact strictly; return raw entries in file order.

    Enforces the *format* invariants of a plain sorted wordlist. Extraction
    policy (which word classes are present) is **not** re-checked here: the
    mandatory artifact hash is the extraction-policy integrity gate.
    """
    if not data:
        raise EnglishScowlArtifactError("approved artifact is empty")
    if b"\r" in data:
        raise EnglishScowlArtifactError(
            "approved artifact contains CR bytes; LF line endings are required"
        )
    if b"\x00" in data:
        raise EnglishScowlArtifactError("approved artifact contains NUL bytes")
    if not data.endswith(b"\n"):
        raise EnglishScowlArtifactError("approved artifact does not end with a final LF")

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise EnglishScowlArtifactError("approved artifact is not valid UTF-8") from None

    # Split only on LF (never ``str.splitlines``, which also splits on other
    # Unicode line boundaries and could silently divide one entry into two).
    lines = text.split("\n")
    lines.pop()  # the trailing empty element produced by the required final LF
    if not lines:
        raise EnglishScowlArtifactError("approved artifact contains no entries")

    previous: bytes | None = None
    for line in lines:
        if not line:
            raise EnglishScowlArtifactError("approved artifact contains an empty entry")
        if line != line.strip():
            raise EnglishScowlArtifactError(
                "approved artifact contains an entry with leading or trailing whitespace"
            )
        if " " in line or "\t" in line:
            raise EnglishScowlArtifactError(
                "approved artifact contains an entry with an ASCII space or tab"
            )
        # UTF-8 byte order equals code-point order, so this bytewise comparison
        # matches the sort the approved artifact was generated with. Strict
        # ordering also guarantees uniqueness; the equality branch exists only to
        # report duplicates precisely.
        current = line.encode("utf-8")
        if previous is not None:
            if current == previous:
                raise EnglishScowlArtifactError(
                    "approved artifact contains a duplicate entry"
                )
            if current < previous:
                raise EnglishScowlArtifactError(
                    "approved artifact entries are not in strict sorted order"
                )
        previous = current
    return lines


def _verify_artifact_hash(data: bytes, expected_hex: str) -> None:
    """Require the artifact bytes to match the digest recorded in provenance.

    This detects accidental corruption or substitution of the local bundle. It is
    **not** a malicious-tampering trust anchor: the expected digest lives beside
    the file it describes. A plain ``==`` comparison is therefore used rather than
    a constant-time comparison, which would imply a security posture this module
    does not claim. Neither digest is ever printed, returned, or raised.
    """
    if hashlib.sha256(data).hexdigest() != expected_hex:
        raise EnglishScowlIntegrityError(
            "approved artifact bytes do not match the SHA-256 recorded in the "
            "approved provenance record"
        )


# --------------------------------------------------------------------------- #
# Public API.
# --------------------------------------------------------------------------- #


def load_approved_english_scowl() -> ApprovedEnglishScowl:
    """Load and verify the approved local English SCOWL bundle.

    Takes no arguments: the approved bundle is fixed by this module. Results are
    **not cached** — every call re-reads and re-verifies the bundle.

    Validation order: the project root is resolved, then the bundle layout, then
    the provenance identity subset, then the strict artifact format, then the
    mandatory artifact hash. Structure is checked before the hash so that
    realistic accidental corruption produces a precise, privacy-safe error rather
    than an opaque integrity failure.

    This is the only way to obtain an :class:`ApprovedEnglishScowl`; the class
    cannot be constructed directly.

    Raises:
        EnglishScowlBundleMissingError: project root unresolvable, or bundle
            absent/not a directory/symlink.
        EnglishScowlBundleLayoutError: not exactly the three approved regular files.
        EnglishScowlProvenanceError: provenance unreadable, unparseable, or
            identity mismatch.
        EnglishScowlArtifactError: artifact unreadable or format violation.
        EnglishScowlIntegrityError: artifact bytes do not match provenance.
    """
    bundle_dir = _approved_bundle_dir()
    _check_bundle_layout(bundle_dir)
    expected_hash = _load_expected_artifact_hash(bundle_dir / PROVENANCE_FILENAME)
    data = _read_artifact_bytes(bundle_dir / ARTIFACT_FILENAME)
    entries = _parse_artifact_entries(data)
    _verify_artifact_hash(data, expected_hash)
    return ApprovedEnglishScowl(
        entries=frozenset(entries), _token=_CONSTRUCTION_TOKEN
    )
