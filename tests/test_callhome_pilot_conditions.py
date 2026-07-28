"""Invented synthetic validation for the CALLHOME pilot-condition builder."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

import cslm.data.callhome_pilot_conditions as pilot_conditions
from cslm.data.callhome_monolingual_eligibility import (
    CSCONT_CODE_SWITCHED_EVIDENCE_ROLE,
    CSCONT_ENGLISH_MONOLINGUAL_FILLER_ROLE,
    CSCONT_SPANISH_MONOLINGUAL_FILLER_ROLE,
    ELIGIBLE_ANNOTATION_CLEAN,
    ENGLISH_MONO_ROLE,
    EXPLICIT_NONEXPECTED_LANGUAGE,
    GENERIC_CSCONT_ROLE,
    MONOCONT_ENGLISH_ROLE,
    MONOCONT_SPANISH_ROLE,
    SPANISH_MONO_ROLE,
    CallhomeEligibilityDecision,
    ReconciledEligibility,
)
from cslm.data.callhome_monolingual_eligibility import (
    condition_candidates as eligibility_condition_candidates,
)
from cslm.data.callhome_pilot_conditions import (
    CONDITION_FILENAME,
    CONDITION_ORDER,
    ENGLISH_MONO,
    ERROR_INVALID_INPUT,
    ERROR_OUTPUT_EXISTS,
    ERROR_QUOTA,
    MONOCONT_ENGLISH,
    MONOCONT_SPANISH,
    SPANISH_MONO,
    CallhomePilotConditionError,
    _rows_bytes,
    _select_under_target,
    build_pilot_condition_membership,
    quota_tolerance,
    write_atomic_pilot_build,
)
from cslm.data.callhome_training_rows import CallhomeTrainingRow

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "build_callhome_pilot_conditions.py"
)
_SCRIPT_SPEC = importlib.util.spec_from_file_location(
    "build_callhome_pilot_conditions",
    _SCRIPT_PATH,
)
assert _SCRIPT_SPEC is not None and _SCRIPT_SPEC.loader is not None
build_script = importlib.util.module_from_spec(_SCRIPT_SPEC)
_SCRIPT_SPEC.loader.exec_module(build_script)

SPLITS = ("train", "validation", "test")
SOURCES = ("callhome_eng", "callhome_spa")
PRE_DECOUPLING_ROW_SHA256 = {
    ENGLISH_MONO: "7da9ce0b1d08543b84f1daf9941dd0ac1df52c72352405b1e28874167e9480c7",
    SPANISH_MONO: "9731fdf036ab836a2f5b87ed01a7665a9b71abc6e952d244f7b91351e5c5e3fb",
    MONOCONT_ENGLISH: (
        "5f5fbe7386ff7c4a43de3f2f9da786c459eb651b9e32e35ec849aa2fb6d92ed6"
    ),
    MONOCONT_SPANISH: (
        "08a03515f92da7492468ac0fc58285f92c36e356df01e5fbd6e27fe1c6edf104"
    ),
}


def _row(
    source: str,
    split: str,
    index: int,
    *,
    text: str | None = None,
) -> CallhomeTrainingRow:
    language_word = "word" if source == "callhome_eng" else "palabra"
    return CallhomeTrainingRow(
        source=source,
        conversation_ref=f"conv_{source}_{split}_{index // 2:03d}",
        speaker_ref=f"spk_{source}_{split}_{index:03d}",
        turn_index=index,
        row_id=f"row_{source}_{split}_{index:03d}",
        split=split,
        text=text or language_word,
    )


def _reconciled(
    *,
    rows_per_split: int = 40,
    words_per_row: int = 1,
    include_excluded: bool = True,
) -> tuple[ReconciledEligibility, ...]:
    items: list[ReconciledEligibility] = []
    for source in SOURCES:
        word = "word" if source == "callhome_eng" else "palabra"
        text = " ".join([word] * words_per_row)
        for split in SPLITS:
            for index in range(rows_per_split):
                items.append(
                    ReconciledEligibility(
                        _row(source, split, index, text=text),
                        CallhomeEligibilityDecision(ELIGIBLE_ANNOTATION_CLEAN),
                    )
                )
        if include_excluded:
            items.append(
                ReconciledEligibility(
                    _row(source, "train", rows_per_split, text=word),
                    CallhomeEligibilityDecision(
                        "excluded",
                        EXPLICIT_NONEXPECTED_LANGUAGE,
                    ),
                )
            )
    return tuple(items)


def _targets(*, mono: int = 10, monocont: int = 5):
    return {
        ENGLISH_MONO: {split: mono for split in SPLITS},
        SPANISH_MONO: {split: mono for split in SPLITS},
        MONOCONT_ENGLISH: {split: monocont for split in SPLITS},
        MONOCONT_SPANISH: {split: monocont for split in SPLITS},
    }


def _build(*, seed: int = 1729, targets=None, reconciled=None):
    return build_pilot_condition_membership(
        reconciled or _reconciled(),
        frozen_checksum_record_sha256="synthetic-frozen-checksum",
        seed=seed,
        targets=targets or _targets(),
    )


def _ids(build, condition):
    return {row.row_id for row in build.rows_by_condition[condition]}


def test_membership_uses_one_inventory_and_preserves_rows_exactly():
    reconciled = _reconciled()
    source_rows = {item.row.row_id: item.row for item in reconciled}
    build = _build(reconciled=reconciled)

    assert _ids(build, MONOCONT_ENGLISH) <= _ids(build, ENGLISH_MONO)
    assert _ids(build, MONOCONT_SPANISH) <= _ids(build, SPANISH_MONO)
    assert _ids(build, ENGLISH_MONO).isdisjoint(_ids(build, SPANISH_MONO))
    assert set(build.rows_by_condition) == set(CONDITION_ORDER)

    for condition, rows in build.rows_by_condition.items():
        expected_source = (
            "callhome_eng"
            if condition in {ENGLISH_MONO, MONOCONT_ENGLISH}
            else "callhome_spa"
        )
        assert all(row.source == expected_source for row in rows)
        assert all(row == source_rows[row.row_id] for row in rows)
        assert len({row.row_id for row in rows}) == len(rows)
        assert all(not row.row_id.endswith("_040") for row in rows)

    manifest = build.manifest
    assert manifest["eligibility_policy_id"] == "callhome_annotation_clean_v1"
    assert (
        manifest["selection_rule_id"]
        == "seeded_sha256_whole_row_greedy_under_quota_v1"
    )
    assert manifest["invariants"]["cscont_rows_emitted_by_this_builder"] == 0
    assert (
        manifest["invariants"]["callhome_rows_qualified_as_code_switched_evidence"]
        == 0
    )
    assert "callhome_to_cscont_routing_count" not in manifest["invariants"]
    assert (
        manifest["eligibility"][
            "future_cscont_monolingual_filler_selection_performed"
        ]
        is False
    )
    assert manifest["eligibility"][
        "future_cscont_monolingual_filler_subset_requirement"
    ] == {
        "callhome_eng": MONOCONT_ENGLISH,
        "callhome_spa": MONOCONT_SPANISH,
    }
    assert manifest["sequence_boundary"] == {
        "sequence_packing_performed": False,
        "row_files_represent_membership_only": True,
        "cross_language_packing": "forbidden",
        "future_packer_requirement": (
            "English and Spanish MonoCont rows must never share a sequence "
            "or packed context."
        ),
    }
    assert manifest["eligibility"]["intermediate_eligible_row_sidecar_written"] is False


def test_future_filler_roles_are_accepted_but_not_emitted():
    build = _build()
    permitted_roles = {
        source: eligibility_condition_candidates(
            source=source,
            decision=CallhomeEligibilityDecision(ELIGIBLE_ANNOTATION_CLEAN),
        )
        for source in SOURCES
    }
    assert CSCONT_ENGLISH_MONOLINGUAL_FILLER_ROLE in permitted_roles[
        "callhome_eng"
    ]
    assert CSCONT_SPANISH_MONOLINGUAL_FILLER_ROLE in permitted_roles[
        "callhome_spa"
    ]
    assert set(build.rows_by_condition) == set(CONDITION_ORDER)
    assert all("CsCont" not in condition for condition in build.rows_by_condition)


@pytest.mark.parametrize(
    ("source", "invalid_roles"),
    [
        (
            "callhome_eng",
            (
                ENGLISH_MONO_ROLE,
                CSCONT_ENGLISH_MONOLINGUAL_FILLER_ROLE,
            ),
        ),
        (
            "callhome_eng",
            (
                ENGLISH_MONO_ROLE,
                MONOCONT_ENGLISH_ROLE,
                GENERIC_CSCONT_ROLE,
            ),
        ),
        (
            "callhome_eng",
            (
                ENGLISH_MONO_ROLE,
                MONOCONT_ENGLISH_ROLE,
                CSCONT_SPANISH_MONOLINGUAL_FILLER_ROLE,
            ),
        ),
        (
            "callhome_spa",
            (
                SPANISH_MONO_ROLE,
                MONOCONT_SPANISH_ROLE,
                CSCONT_CODE_SWITCHED_EVIDENCE_ROLE,
            ),
        ),
        (
            "callhome_spa",
            (
                SPANISH_MONO_ROLE,
                MONOCONT_SPANISH_ROLE,
                "Unknown-Future-Role",
            ),
        ),
    ],
)
def test_pilot_builder_fails_closed_on_invalid_global_roles(
    monkeypatch,
    source,
    invalid_roles,
):
    def candidates_for_test(*, source: str, decision: CallhomeEligibilityDecision):
        if source == source_to_corrupt and decision.is_eligible:
            return invalid_roles
        return eligibility_condition_candidates(source=source, decision=decision)

    source_to_corrupt = source
    monkeypatch.setattr(
        pilot_conditions,
        "condition_candidates",
        candidates_for_test,
    )
    with pytest.raises(CallhomePilotConditionError, match=ERROR_INVALID_INPUT):
        _build()


def test_selected_row_bytes_match_pre_decoupling_implementation():
    build = _build()
    assert {
        condition: hashlib.sha256(
            _rows_bytes(build.rows_by_condition[condition])
        ).hexdigest()
        for condition in CONDITION_ORDER
    } == PRE_DECOUPLING_ROW_SHA256


def test_targets_and_split_local_monocont_balance_are_realized():
    build = _build()
    for condition in (ENGLISH_MONO, SPANISH_MONO):
        for split in SPLITS:
            report = build.manifest["conditions"][condition]["splits"][split]
            assert report["target_lexical_tokens"] == 10
            assert report["realized_lexical_tokens"] == 10
            assert report["shortfall_lexical_tokens"] == 0
    for condition in (MONOCONT_ENGLISH, MONOCONT_SPANISH):
        for split in SPLITS:
            report = build.manifest["conditions"][condition]["splits"][split]
            assert report["target_lexical_tokens"] == 5
            assert report["realized_lexical_tokens"] == 5
            assert report["shortfall_lexical_tokens"] == 0
    for split in SPLITS:
        balance = build.manifest["monocont_balance"][split]
        assert balance["realized_english_fraction"] == 0.5
        assert balance["realized_spanish_fraction"] == 0.5


def test_seeded_selection_is_repeatable_and_not_filesystem_order_dependent():
    source = _reconciled()
    first = _build(reconciled=source)
    reversed_input = _build(reconciled=tuple(reversed(source)))
    changed_seed = _build(reconciled=source, seed=1730)

    assert first == reversed_input
    assert any(
        _ids(first, condition) != _ids(changed_seed, condition)
        for condition in CONDITION_ORDER
    )


def test_indivisible_rows_may_leave_only_the_reviewed_shortfall():
    targets = _targets(mono=10, monocont=10)
    build = _build(
        targets=targets,
        reconciled=_reconciled(rows_per_split=10, words_per_row=3),
    )
    assert quota_tolerance(10) == 1
    for condition in CONDITION_ORDER:
        for split in SPLITS:
            report = build.manifest["conditions"][condition]["splits"][split]
            assert report["realized_lexical_tokens"] == 9
            assert report["shortfall_lexical_tokens"] == 1
            assert report["allowed_shortfall_lexical_tokens"] == 1


def test_selection_continues_after_a_whole_row_does_not_fit():
    ordered = (
        _row("callhome_eng", "train", 0, text="one two three four five six"),
        _row("callhome_eng", "train", 1, text="one two three four five"),
        _row("callhome_eng", "train", 2, text="one two three four"),
    )
    selected, realized = _select_under_target(ordered, target=10)
    assert [row.row_id for row in selected] == [ordered[0].row_id, ordered[2].row_id]
    assert realized == 10


def test_quota_fails_closed_beyond_tolerance():
    with pytest.raises(CallhomePilotConditionError, match=ERROR_QUOTA):
        _build(
            targets=_targets(mono=10, monocont=10),
            reconciled=_reconciled(rows_per_split=10, words_per_row=4),
        )


def test_cross_split_conversation_fails_closed():
    reconciled = list(_reconciled())
    train_item = next(
        item
        for item in reconciled
        if item.row.source == "callhome_eng" and item.row.split == "train"
    )
    validation_index = next(
        index
        for index, item in enumerate(reconciled)
        if item.row.source == "callhome_eng" and item.row.split == "validation"
    )
    validation_item = reconciled[validation_index]
    reconciled[validation_index] = ReconciledEligibility(
        replace(
            validation_item.row,
            conversation_ref=train_item.row.conversation_ref,
        ),
        validation_item.decision,
    )
    with pytest.raises(CallhomePilotConditionError, match=ERROR_INVALID_INPUT):
        _build(reconciled=tuple(reconciled))


def test_synthetic_frozen_pool_verification_rejects_tampering(tmp_path, monkeypatch):
    pool_root = tmp_path / "pools"
    pool_root.mkdir()
    artifacts = {
        "english_rows.jsonl": b"",
        "manifest.json": b"{}\n",
        "spanish_rows.jsonl": b"",
    }
    for name, content in artifacts.items():
        (pool_root / name).write_bytes(content)
    checksums = {
        name: hashlib.sha256(content).hexdigest()
        for name, content in artifacts.items()
    }
    checksum_bytes = (
        json.dumps(checksums, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    (pool_root / "checksums.json").write_bytes(checksum_bytes)
    monkeypatch.setattr(
        build_script,
        "EXPECTED_FROZEN_CHECKSUMS_SHA256",
        hashlib.sha256(checksum_bytes).hexdigest(),
    )

    assert build_script._load_verified_frozen_rows(pool_root) == []
    (pool_root / "english_rows.jsonl").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="CALLHOME pilot-condition build failed"):
        build_script._load_verified_frozen_rows(pool_root)


def test_atomic_publication_writes_exact_contract_and_valid_checksums(tmp_path):
    first = tmp_path / "first" / "pilot_conditions"
    second = tmp_path / "second" / "pilot_conditions"
    first_checksums = write_atomic_pilot_build(_build(), publish_dir=first)
    second_checksums = write_atomic_pilot_build(_build(), publish_dir=second)

    expected_names = {
        *CONDITION_FILENAME.values(),
        "manifest.json",
        "checksums.json",
    }
    assert {path.name for path in first.iterdir()} == expected_names
    assert first_checksums == second_checksums
    assert json.loads((first / "checksums.json").read_text(encoding="utf-8")) == (
        first_checksums
    )
    for name, expected_digest in first_checksums.items():
        assert hashlib.sha256((first / name).read_bytes()).hexdigest() == expected_digest
        assert (first / name).read_bytes() == (second / name).read_bytes()


def test_publication_rejects_existing_output(tmp_path):
    publish_dir = tmp_path / "pilot_conditions"
    write_atomic_pilot_build(_build(), publish_dir=publish_dir)
    with pytest.raises(CallhomePilotConditionError, match=ERROR_OUTPUT_EXISTS):
        write_atomic_pilot_build(_build(), publish_dir=publish_dir)


def test_failed_publication_leaves_no_partial_directory(tmp_path, monkeypatch):
    publish_dir = tmp_path / "pilot_conditions"

    def fail_write(_self: Path, _data: bytes):
        raise OSError("invented write failure")

    monkeypatch.setattr(Path, "write_bytes", fail_write)
    with pytest.raises(OSError, match="invented write failure"):
        write_atomic_pilot_build(_build(), publish_dir=publish_dir)
    assert not publish_dir.exists()
    assert list(tmp_path.iterdir()) == []


def test_real_script_refuses_execution_without_explicit_flag(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["build_callhome_pilot_conditions.py"])
    with pytest.raises(SystemExit, match="Refusing to process real CALLHOME"):
        build_script.main()
