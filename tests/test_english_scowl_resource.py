"""Tests for the approved English SCOWL resource loader.

Every bundle here is SYNTHETIC and built under a temporary directory with fake
``syn_*`` entries. No test reads, requires, or touches the real ignored approved
bundle, no real lexical resource is involved, and no CALLHOME data is used.

The private resolver ``_approved_bundle_dir`` is monkeypatched so the real public
entry point ``load_approved_english_scowl()`` is exercised end to end against a
synthetic bundle. There is no public way to pass a path.

Path-like sentinels below (``/synthetic/private/project``) are deliberately
artificial: they stand in for a personal absolute path without putting one in a
tracked file.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from dataclasses import FrozenInstanceError, fields
from pathlib import Path

import pytest

from cslm.data import english_scowl_resource as resource
from cslm.data.english_scowl_resource import (
    ARTIFACT_FILENAME,
    NOTICE_FILENAME,
    PROVENANCE_FILENAME,
    RESOURCE_ID,
    ApprovedEnglishScowl,
    EnglishScowlArtifactError,
    EnglishScowlBundleLayoutError,
    EnglishScowlBundleMissingError,
    EnglishScowlIntegrityError,
    EnglishScowlProvenanceError,
    EnglishScowlResourceError,
    load_approved_english_scowl,
)

# Synthetic entries, strictly sorted in bytewise order.
_SYN_ENTRIES: tuple[str, ...] = ("syn_alpha", "syn_beta", "syn_gamma")
_SYN_NOTICE = "synthetic notice text; never read by the loader\n"

# Clearly artificial stand-in for a personal absolute path.
_SYN_PRIVATE_ROOT = "/synthetic/private/project"


class _SynFrozensetSubclass(frozenset):
    """Synthetic frozenset subclass used to pin exact-type enforcement."""


def _artifact_bytes(entries) -> bytes:
    return "".join(f"{entry}\n" for entry in entries).encode("utf-8")


def _provenance_document(artifact_data: bytes, **overrides) -> dict:
    document = {
        "schema_version": 1,
        "resource_id": RESOURCE_ID,
        "artifact_filename": ARTIFACT_FILENAME,
        "preserved_notice_filename": NOTICE_FILENAME,
        "artifact_SHA256": hashlib.sha256(artifact_data).hexdigest(),
        # Present to prove unknown provenance keys are ignored.
        "syn_unknown_future_key": "syn_ignored_value",
    }
    document.update(overrides)
    return document


def _build_bundle(
    root: Path,
    *,
    entries=_SYN_ENTRIES,
    artifact_data: bytes | None = None,
    provenance: dict | None = None,
    provenance_raw: bytes | None = None,
) -> Path:
    bundle = root / "syn_bundle"
    bundle.mkdir()
    data = _artifact_bytes(entries) if artifact_data is None else artifact_data
    (bundle / ARTIFACT_FILENAME).write_bytes(data)
    (bundle / NOTICE_FILENAME).write_text(_SYN_NOTICE, encoding="utf-8")
    if provenance_raw is not None:
        (bundle / PROVENANCE_FILENAME).write_bytes(provenance_raw)
    else:
        document = _provenance_document(data) if provenance is None else provenance
        (bundle / PROVENANCE_FILENAME).write_text(
            json.dumps(document, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
    return bundle


@pytest.fixture
def point_at(monkeypatch):
    """Replace the private resolver so the public loader sees a synthetic path."""

    def _factory(path: Path) -> Path:
        monkeypatch.setattr(resource, "_approved_bundle_dir", lambda: path)
        return path

    return _factory


@pytest.fixture
def make_bundle(tmp_path, point_at):
    """Build a synthetic bundle and point the loader at it."""

    def _factory(**kwargs) -> Path:
        return point_at(_build_bundle(tmp_path, **kwargs))

    return _factory


# --------------------------------------------------------------------------- #
# Successful contract.
# --------------------------------------------------------------------------- #


def test_loads_valid_synthetic_bundle(make_bundle):
    make_bundle()
    scowl = load_approved_english_scowl()
    assert isinstance(scowl, ApprovedEnglishScowl)
    assert scowl.resource_id == RESOURCE_ID
    assert scowl.entries == frozenset(_SYN_ENTRIES)


def test_entries_are_an_immutable_frozenset(make_bundle):
    make_bundle()
    scowl = load_approved_english_scowl()
    assert type(scowl.entries) is frozenset


def test_entry_count_is_derived_not_stored(make_bundle):
    make_bundle()
    scowl = load_approved_english_scowl()
    assert scowl.entry_count == len(_SYN_ENTRIES)
    assert scowl.entry_count == len(scowl.entries)
    field_names = [f.name for f in fields(scowl)]
    assert "entry_count" not in field_names
    assert "resource_id" not in field_names
    assert field_names == ["entries"]


def test_instance_is_frozen(make_bundle):
    make_bundle()
    scowl = load_approved_english_scowl()
    with pytest.raises(FrozenInstanceError):
        scowl.entries = frozenset({"syn_other"})


def test_repr_reveals_only_safe_metadata(make_bundle):
    make_bundle()
    scowl = load_approved_english_scowl()
    text = repr(scowl)
    assert RESOURCE_ID in text
    assert f"entry_count={len(_SYN_ENTRIES)}" in text
    for entry in _SYN_ENTRIES:
        assert entry not in text


def test_no_filesystem_path_is_stored_or_exposed(make_bundle):
    bundle = make_bundle()
    scowl = load_approved_english_scowl()
    for value in vars(scowl).values():
        assert not isinstance(value, Path)
    assert str(bundle) not in repr(scowl)
    assert not any(isinstance(getattr(scowl, name, None), Path) for name in dir(scowl))


def test_entries_are_returned_raw_without_normalization(make_bundle):
    # Bytewise-sorted synthetic entries exercising case and an apostrophe.
    raw = ("syn_Beta", "syn_alpha", "syn_don't")
    make_bundle(entries=raw)
    scowl = load_approved_english_scowl()
    assert scowl.entries == frozenset(raw)


def test_unknown_provenance_keys_are_ignored(make_bundle):
    data = _artifact_bytes(_SYN_ENTRIES)
    document = _provenance_document(data, syn_extra_key={"syn_nested": [1, 2, 3]})
    make_bundle(provenance=document)
    assert load_approved_english_scowl().entry_count == len(_SYN_ENTRIES)


def test_public_loader_accepts_no_arguments():
    assert inspect.signature(load_approved_english_scowl).parameters == {}


def test_loader_results_are_not_cached(make_bundle):
    bundle = make_bundle()
    assert load_approved_english_scowl().entry_count == len(_SYN_ENTRIES)
    # Corrupt the bundle; a cached loader would wrongly succeed again.
    (bundle / ARTIFACT_FILENAME).write_bytes(b"syn_zeta\nsyn_alpha\n")
    with pytest.raises(EnglishScowlArtifactError):
        load_approved_english_scowl()


def test_exception_hierarchy_is_resource_specific():
    for error in (
        EnglishScowlBundleMissingError,
        EnglishScowlBundleLayoutError,
        EnglishScowlProvenanceError,
        EnglishScowlArtifactError,
        EnglishScowlIntegrityError,
    ):
        assert issubclass(error, EnglishScowlResourceError)
    assert issubclass(EnglishScowlResourceError, RuntimeError)


def test_loading_writes_nothing(make_bundle):
    bundle = make_bundle()

    def snapshot():
        return sorted((p.name, p.stat().st_size) for p in bundle.iterdir())

    before = snapshot()
    load_approved_english_scowl()
    assert snapshot() == before


# --------------------------------------------------------------------------- #
# Construction is reserved to the verified loader.
# --------------------------------------------------------------------------- #


def test_direct_construction_is_rejected():
    # The type asserts "these entries are the approved artifact's". That claim
    # must not be forgeable by ordinary construction.
    with pytest.raises(TypeError):
        ApprovedEnglishScowl(entries=frozenset({"syn_forged_vocabulary"}))


def test_no_argument_construction_is_rejected():
    with pytest.raises(TypeError):
        ApprovedEnglishScowl()


def test_construction_with_a_foreign_token_is_rejected():
    with pytest.raises(TypeError):
        ApprovedEnglishScowl(entries=frozenset({"syn_alpha"}), _token=object())


def test_resource_id_cannot_be_supplied_at_construction():
    with pytest.raises(TypeError):
        ApprovedEnglishScowl(
            entries=frozenset({"syn_alpha"}),
            resource_id="syn_forged",
            _token=resource._CONSTRUCTION_TOKEN,
        )


@pytest.mark.parametrize(
    "bad_entries",
    [
        {"syn_alpha"},
        ["syn_alpha"],
        ("syn_alpha",),
        _SynFrozensetSubclass({"syn_alpha"}),
    ],
    ids=["set", "list", "tuple", "frozenset_subclass"],
)
def test_entries_must_be_exactly_a_frozenset(bad_entries):
    with pytest.raises(TypeError):
        ApprovedEnglishScowl(entries=bad_entries, _token=resource._CONSTRUCTION_TOKEN)


def test_construction_error_omits_forged_entries():
    forged = "syn_forged_secret_vocabulary"
    with pytest.raises(TypeError) as exc_info:
        ApprovedEnglishScowl(entries=frozenset({forged}))
    assert forged not in str(exc_info.value)


# --------------------------------------------------------------------------- #
# Project-root resolution failures.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "failure",
    [
        RuntimeError(
            f"Could not locate project root from {_SYN_PRIVATE_ROOT}/paths.py; "
            "expected markers in a parent directory."
        ),
        OSError(f"{_SYN_PRIVATE_ROOT}/unreadable"),
    ],
    ids=["runtime_error", "os_error"],
)
def test_project_root_failure_is_wrapped_privately(monkeypatch, failure):
    # Monkeypatched, never the real resolver: the real project root resolves fine
    # and must not be sabotaged. The OSError case pins the (OSError, RuntimeError)
    # catch rather than a RuntimeError-only one.
    def _raise():
        raise failure

    monkeypatch.setattr(resource, "project_root", _raise)
    with pytest.raises(EnglishScowlBundleMissingError) as exc_info:
        load_approved_english_scowl()
    message = str(exc_info.value)
    assert _SYN_PRIVATE_ROOT not in message
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True


# --------------------------------------------------------------------------- #
# Bundle layout failures.
# --------------------------------------------------------------------------- #


def test_missing_bundle_directory_rejected(tmp_path, point_at):
    point_at(tmp_path / "syn_absent")
    with pytest.raises(EnglishScowlBundleMissingError):
        load_approved_english_scowl()


def test_bundle_path_that_is_a_file_rejected(tmp_path, point_at):
    target = tmp_path / "syn_not_a_dir"
    target.write_text("syn", encoding="utf-8")
    point_at(target)
    with pytest.raises(EnglishScowlBundleMissingError):
        load_approved_english_scowl()


def test_bundle_directory_symlink_rejected(tmp_path, point_at):
    real = _build_bundle(tmp_path)
    link = tmp_path / "syn_bundle_link"
    link.symlink_to(real, target_is_directory=True)
    point_at(link)
    with pytest.raises(EnglishScowlBundleMissingError):
        load_approved_english_scowl()


@pytest.mark.parametrize(
    "name", [ARTIFACT_FILENAME, NOTICE_FILENAME, PROVENANCE_FILENAME]
)
def test_missing_required_file_rejected(make_bundle, name):
    bundle = make_bundle()
    (bundle / name).unlink()
    with pytest.raises(EnglishScowlBundleLayoutError):
        load_approved_english_scowl()


def test_unexpected_extra_file_rejected(make_bundle):
    bundle = make_bundle()
    (bundle / "syn_unexpected.txt").write_text("syn", encoding="utf-8")
    with pytest.raises(EnglishScowlBundleLayoutError):
        load_approved_english_scowl()


def test_unexpected_dotfile_rejected(make_bundle):
    bundle = make_bundle()
    (bundle / ".DS_Store").write_bytes(b"syn")
    with pytest.raises(EnglishScowlBundleLayoutError):
        load_approved_english_scowl()


def test_unexpected_subdirectory_rejected(make_bundle):
    bundle = make_bundle()
    (bundle / "syn_subdir").mkdir()
    with pytest.raises(EnglishScowlBundleLayoutError):
        load_approved_english_scowl()


@pytest.mark.parametrize(
    "name", [ARTIFACT_FILENAME, NOTICE_FILENAME, PROVENANCE_FILENAME]
)
def test_required_file_symlink_rejected(make_bundle, tmp_path, name):
    bundle = make_bundle()
    target = tmp_path / "syn_outside_target"
    target.write_text("syn", encoding="utf-8")
    (bundle / name).unlink()
    (bundle / name).symlink_to(target)
    with pytest.raises(EnglishScowlBundleLayoutError):
        load_approved_english_scowl()


def test_required_name_that_is_a_directory_rejected(make_bundle):
    bundle = make_bundle()
    (bundle / ARTIFACT_FILENAME).unlink()
    (bundle / ARTIFACT_FILENAME).mkdir()
    with pytest.raises(EnglishScowlBundleLayoutError):
        load_approved_english_scowl()


# --------------------------------------------------------------------------- #
# Provenance failures.
# --------------------------------------------------------------------------- #


def test_provenance_not_valid_json_rejected(make_bundle):
    make_bundle(provenance_raw=b"{not valid json\n")
    with pytest.raises(EnglishScowlProvenanceError):
        load_approved_english_scowl()


def test_provenance_not_valid_utf8_rejected(make_bundle):
    make_bundle(provenance_raw=b"\xff\xfe{}\n")
    with pytest.raises(EnglishScowlProvenanceError):
        load_approved_english_scowl()


def test_provenance_that_is_not_an_object_rejected(make_bundle):
    make_bundle(provenance_raw=b"[1, 2, 3]\n")
    with pytest.raises(EnglishScowlProvenanceError):
        load_approved_english_scowl()


def test_deeply_nested_provenance_recursion_error_is_wrapped_privately(
    make_bundle, monkeypatch
):
    make_bundle()
    secret = f"{_SYN_PRIVATE_ROOT}/recursion-detail"

    def _raise_recursion(*_args, **_kwargs):
        raise RecursionError(f"maximum recursion depth exceeded near {secret}")

    # Patch the parser rather than building genuinely deep JSON, so the test does
    # not depend on this machine's recursion limit (real nesting can overflow the
    # C stack instead of raising).
    monkeypatch.setattr(resource.json, "loads", _raise_recursion)
    with pytest.raises(EnglishScowlProvenanceError) as exc_info:
        load_approved_english_scowl()
    message = str(exc_info.value)
    assert secret not in message
    assert _SYN_PRIVATE_ROOT not in message
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True


@pytest.mark.parametrize("bad_version", [2, 0, "1", 1.0, None, True, False])
def test_wrong_schema_version_rejected(make_bundle, bad_version):
    data = _artifact_bytes(_SYN_ENTRIES)
    make_bundle(provenance=_provenance_document(data, schema_version=bad_version))
    with pytest.raises(EnglishScowlProvenanceError):
        load_approved_english_scowl()


@pytest.mark.parametrize(
    ("field_name", "bad_value"),
    [
        ("resource_id", "syn_wrong_resource_identity"),
        ("resource_id", None),
        ("artifact_filename", "syn_wrong_artifact_name.txt"),
        ("artifact_filename", 7),
        ("preserved_notice_filename", "syn_wrong_notice_name.txt"),
        ("preserved_notice_filename", None),
    ],
)
def test_wrong_identity_field_rejected(make_bundle, field_name, bad_value):
    data = _artifact_bytes(_SYN_ENTRIES)
    make_bundle(provenance=_provenance_document(data, **{field_name: bad_value}))
    with pytest.raises(EnglishScowlProvenanceError):
        load_approved_english_scowl()


@pytest.mark.parametrize(
    "bad_digest",
    [
        None,
        7,
        "",
        "abc123",
        "A" * 64,
        "g" * 64,
        "0" * 63,
        "0" * 65,
    ],
)
def test_invalid_artifact_hash_field_rejected(make_bundle, bad_digest):
    data = _artifact_bytes(_SYN_ENTRIES)
    make_bundle(provenance=_provenance_document(data, artifact_SHA256=bad_digest))
    with pytest.raises(EnglishScowlProvenanceError):
        load_approved_english_scowl()


def test_missing_artifact_hash_field_rejected(make_bundle):
    data = _artifact_bytes(_SYN_ENTRIES)
    document = _provenance_document(data)
    del document["artifact_SHA256"]
    make_bundle(provenance=document)
    with pytest.raises(EnglishScowlProvenanceError):
        load_approved_english_scowl()


# --------------------------------------------------------------------------- #
# Strict artifact-format failures.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "artifact_data",
    [
        b"",  # empty
        b"syn_alpha\r\nsyn_beta\n",  # CR
        b"syn_alpha\x00\nsyn_beta\n",  # NUL
        b"syn_alpha\nsyn_beta",  # no final LF
        b"syn_alpha\n\nsyn_beta\n",  # blank entry
        b"syn_alpha\nsyn_alpha\n",  # duplicate
        b" syn_alpha\nsyn_beta\n",  # leading whitespace
        b"syn_alpha \nsyn_beta\n",  # trailing whitespace
        b"syn_alpha syn_beta\n",  # interior ASCII space
        b"syn_alpha\tsyn_beta\n",  # interior tab
        b"syn_zeta\nsyn_alpha\n",  # not sorted
        b"\xff\xfe\n",  # invalid UTF-8
    ],
)
def test_malformed_artifact_rejected(make_bundle, artifact_data):
    make_bundle(artifact_data=artifact_data)
    with pytest.raises(EnglishScowlArtifactError):
        load_approved_english_scowl()


def test_artifact_with_only_a_final_lf_rejected(make_bundle):
    make_bundle(artifact_data=b"\n")
    with pytest.raises(EnglishScowlArtifactError):
        load_approved_english_scowl()


def test_decode_failure_suppresses_exception_chaining(make_bundle):
    make_bundle(artifact_data=b"\xff\xfe\n")
    with pytest.raises(EnglishScowlArtifactError) as exc_info:
        load_approved_english_scowl()
    assert exc_info.value.__cause__ is None
    assert exc_info.value.__suppress_context__ is True


# --------------------------------------------------------------------------- #
# Mandatory integrity gate.
# --------------------------------------------------------------------------- #


def test_stale_provenance_hash_rejected(make_bundle):
    bundle = make_bundle()
    # Structurally valid but different bytes; the recorded hash is now stale.
    (bundle / ARTIFACT_FILENAME).write_bytes(_artifact_bytes(("syn_delta", "syn_omega")))
    with pytest.raises(EnglishScowlIntegrityError):
        load_approved_english_scowl()


def test_well_formed_but_wrong_hash_rejected(make_bundle):
    data = _artifact_bytes(_SYN_ENTRIES)
    make_bundle(provenance=_provenance_document(data, artifact_SHA256="0" * 64))
    with pytest.raises(EnglishScowlIntegrityError):
        load_approved_english_scowl()


# --------------------------------------------------------------------------- #
# Privacy-safe exception text.
# --------------------------------------------------------------------------- #


def test_layout_error_omits_path_and_unexpected_filename(make_bundle, tmp_path):
    bundle = make_bundle()
    (bundle / "syn_personal_notes.txt").write_text("syn", encoding="utf-8")
    with pytest.raises(EnglishScowlBundleLayoutError) as exc_info:
        load_approved_english_scowl()
    message = str(exc_info.value)
    assert str(tmp_path) not in message
    assert str(bundle) not in message
    assert "syn_personal_notes.txt" not in message


def test_artifact_error_omits_lexical_entries(make_bundle, tmp_path):
    make_bundle(artifact_data=b"syn_zeta\nsyn_alpha\n")
    with pytest.raises(EnglishScowlArtifactError) as exc_info:
        load_approved_english_scowl()
    message = str(exc_info.value)
    assert "syn_zeta" not in message
    assert "syn_alpha" not in message
    assert str(tmp_path) not in message


def test_provenance_error_omits_provenance_values(make_bundle, tmp_path):
    data = _artifact_bytes(_SYN_ENTRIES)
    make_bundle(provenance=_provenance_document(data, resource_id="syn_forged_identity"))
    with pytest.raises(EnglishScowlProvenanceError) as exc_info:
        load_approved_english_scowl()
    message = str(exc_info.value)
    assert "syn_forged_identity" not in message
    assert str(tmp_path) not in message


def test_integrity_error_omits_both_hashes(make_bundle, tmp_path):
    bundle = make_bundle()
    replacement = _artifact_bytes(("syn_delta", "syn_omega"))
    (bundle / ARTIFACT_FILENAME).write_bytes(replacement)
    recorded = json.loads((bundle / PROVENANCE_FILENAME).read_text(encoding="utf-8"))[
        "artifact_SHA256"
    ]
    computed = hashlib.sha256(replacement).hexdigest()
    with pytest.raises(EnglishScowlIntegrityError) as exc_info:
        load_approved_english_scowl()
    message = str(exc_info.value)
    assert recorded not in message
    assert computed not in message
    assert str(tmp_path) not in message


def test_missing_bundle_error_omits_path(tmp_path, point_at):
    point_at(tmp_path / "syn_absent")
    with pytest.raises(EnglishScowlBundleMissingError) as exc_info:
        load_approved_english_scowl()
    assert str(tmp_path) not in str(exc_info.value)


def test_notice_contents_are_never_read_or_exposed(make_bundle):
    # A notice whose bytes are not valid UTF-8 must not affect loading at all:
    # the loader checks the notice's presence and file type only.
    bundle = make_bundle()
    (bundle / NOTICE_FILENAME).write_bytes(b"\xff\xfe syn_notice_secret\n")
    scowl = load_approved_english_scowl()
    assert scowl.entry_count == len(_SYN_ENTRIES)
    assert "syn_notice_secret" not in repr(scowl)
