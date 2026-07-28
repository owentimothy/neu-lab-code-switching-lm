"""Synthetic tests for CALLHOME annotation-based monolingual eligibility."""

from __future__ import annotations

import builtins
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from cslm.data.callhome_chat import (
    CallhomeTranscript,
    StrictChatReaderError,
    read_chat_transcript,
)
from cslm.data.callhome_monolingual_eligibility import (
    CONFLICTING_LANGUAGE_ANNOTATION,
    ELIGIBLE_ANNOTATION_CLEAN,
    ERROR_DUPLICATE_RECONCILIATION,
    ERROR_PROVENANCE_DISAGREEMENT,
    ERROR_RECONCILIATION,
    ERROR_ROUTING_INVARIANT,
    ERROR_SOURCE_DISAGREEMENT,
    ERROR_SPLIT_DISAGREEMENT,
    ERROR_UNKNOWN_LANGUAGE_CONTROL,
    EXPLICIT_LANGUAGE_AMBIGUITY,
    EXPLICIT_MIXED_LANGUAGE,
    EXPLICIT_NONEXPECTED_LANGUAGE,
    RECOGNIZED_LANGUAGE_CODES,
    CallhomeEligibilityDecision,
    CallhomeEligibilityError,
    audit_callhome_monolingual_eligibility,
    condition_candidates,
    evaluate_utterance_annotation_eligibility,
    reconcile_frozen_rows,
)
from cslm.data.callhome_training_rows import (
    assign_conversation_splits,
    build_population_rows,
)
from scripts import audit_callhome_monolingual_eligibility as audit_script


def _write_chat(
    tmp_path: Path,
    name: str,
    language: str,
    tiers: list[str],
) -> Path:
    main_tiers = "".join(f"*AAA:\t{text}\n" for text in tiers)
    path = tmp_path / name
    path.write_text(
        "@UTF8\n"
        "@Begin\n"
        f"@Languages:\t{language}\n"
        "@Participants:\tAAA Adult\n"
        f"{main_tiers}"
        "@End\n",
        encoding="utf-8",
    )
    return path


def _transcript(
    tmp_path: Path,
    text: str,
    *,
    language: str = "eng",
    name: str = "synthetic.cha",
) -> CallhomeTranscript:
    return read_chat_transcript(
        _write_chat(tmp_path, name, language, [text])
    )


def _decision(tmp_path: Path, text: str, *, source: str = "callhome_eng"):
    language = "eng" if source == "callhome_eng" else "spa"
    transcript = _transcript(tmp_path, text, language=language)
    return evaluate_utterance_annotation_eligibility(
        transcript.utterances[0],
        source=source,
    )


def _fixture_population(tmp_path: Path):
    eng_path = _write_chat(
        tmp_path,
        "english.cha",
        "eng",
        ["Expected words .", "Other [- spa] words ."],
    )
    spa_path = _write_chat(
        tmp_path,
        "spanish.cha",
        "spa",
        ["Palabras esperadas .", "Dudoso [- und] ."],
    )
    english = build_population_rows([eng_path], source="callhome_eng")
    spanish = build_population_rows([spa_path], source="callhome_spa")
    frozen = assign_conversation_splits(
        [*english.rows, *spanish.rows],
        seed=1729,
        train_fraction=0.5,
        validation_fraction=0.0,
    )
    # A one-conversation source would otherwise receive train only; assign fixed
    # valid synthetic splits without changing the conversation boundary.
    frozen = [
        replace(row, split="train" if row.source == "callhome_eng" else "test")
        for row in frozen
    ]
    return {
        "callhome_eng": [read_chat_transcript(eng_path)],
        "callhome_spa": [read_chat_transcript(spa_path)],
    }, frozen


def _canonical_splits(frozen):
    return {row.row_id: row.split for row in frozen}


def _write_synthetic_verified_pool(tmp_path, monkeypatch):
    pool_root = tmp_path / "pools"
    pool_root.mkdir()
    artifacts = {
        "english_rows.jsonl": b"",
        "manifest.json": b"{}",
        "spanish_rows.jsonl": b"",
    }
    for name, content in artifacts.items():
        (pool_root / name).write_bytes(content)
    checksums = {
        name: hashlib.sha256(content).hexdigest()
        for name, content in artifacts.items()
    }
    checksum_bytes = json.dumps(
        checksums,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    (pool_root / "checksums.json").write_bytes(checksum_bytes)
    monkeypatch.setattr(
        audit_script,
        "EXPECTED_FROZEN_CHECKSUMS_SHA256",
        hashlib.sha256(checksum_bytes).hexdigest(),
    )
    return pool_root, checksums


def _rewrite_synthetic_checksum_record(pool_root, checksums, monkeypatch):
    checksum_bytes = json.dumps(
        checksums,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    (pool_root / "checksums.json").write_bytes(checksum_bytes)
    monkeypatch.setattr(
        audit_script,
        "EXPECTED_FROZEN_CHECKSUMS_SHA256",
        hashlib.sha256(checksum_bytes).hexdigest(),
    )


def test_unmarked_expected_source_row_is_eligible(tmp_path):
    decision = _decision(tmp_path, "Unmarked synthetic words .")
    assert decision.category == ELIGIBLE_ANNOTATION_CLEAN
    assert decision.is_eligible is True


@pytest.mark.parametrize(
    ("source", "marker"),
    [("callhome_eng", "eng"), ("callhome_spa", "spa")],
)
def test_explicit_expected_language_marker_is_eligible(tmp_path, source, marker):
    assert _decision(
        tmp_path,
        f"[- {marker}] Synthetic words .",
        source=source,
    ).is_eligible is True


@pytest.mark.parametrize(
    ("source", "marker"),
    [("callhome_eng", "spa"), ("callhome_spa", "eng")],
)
def test_explicit_nonexpected_language_marker_is_excluded(
    tmp_path,
    source,
    marker,
):
    decision = _decision(
        tmp_path,
        f"[- {marker}] Synthetic words .",
        source=source,
    )
    assert decision.exclusion_reason == EXPLICIT_NONEXPECTED_LANGUAGE


@pytest.mark.parametrize(
    "marker",
    ["deu", "fra", "grn", "heb", "jpn", "pol", "yid"],
)
@pytest.mark.parametrize("source", ["callhome_eng", "callhome_spa"])
def test_documented_nontarget_language_is_excluded_in_either_source(
    tmp_path,
    source,
    marker,
):
    decision = _decision(
        tmp_path,
        f"[- {marker}] Synthetic words .",
        source=source,
    )
    assert decision.is_eligible is False
    assert decision.category == "excluded"
    assert decision.exclusion_reason == EXPLICIT_NONEXPECTED_LANGUAGE
    assert decision.exclusion_reason not in {
        EXPLICIT_MIXED_LANGUAGE,
        EXPLICIT_LANGUAGE_AMBIGUITY,
    }


def test_recognized_language_code_vocabulary_is_exact():
    assert RECOGNIZED_LANGUAGE_CODES == {
        "deu",
        "eng",
        "fra",
        "grn",
        "heb",
        "jpn",
        "mul",
        "pol",
        "spa",
        "und",
        "yid",
    }


@pytest.mark.parametrize("marker", ["[- eng, spa]", "[- mul]"])
def test_explicit_mixed_language_marker_is_excluded(tmp_path, marker):
    decision = _decision(tmp_path, f"{marker} Synthetic words .")
    assert decision.exclusion_reason == EXPLICIT_MIXED_LANGUAGE


def test_multiple_or_conflicting_language_markers_are_excluded(tmp_path):
    decision = _decision(tmp_path, "[- eng] Synthetic [- spa] words .")
    assert decision.exclusion_reason == CONFLICTING_LANGUAGE_ANNOTATION


@pytest.mark.parametrize("marker", ["[- ?]", "[- und]"])
def test_recognized_language_ambiguity_is_excluded(tmp_path, marker):
    decision = _decision(tmp_path, f"{marker} Synthetic words .")
    assert decision.exclusion_reason == EXPLICIT_LANGUAGE_AMBIGUITY


@pytest.mark.parametrize(
    "control",
    [
        "[?]",
        "[= explanation]",
        "[: replacement]",
        "[+ metadata]",
        "\x15media_100_200\x15",
        "[/]",
        "&=laughs",
    ],
)
def test_ordinary_nonlanguage_controls_do_not_exclude(tmp_path, control):
    decision = _decision(tmp_path, f"Synthetic {control} words .")
    assert decision.is_eligible is True


@pytest.mark.parametrize(
    "control",
    ["[-eng]", "[- eng spa]", "[- eng,]", "[- eng, eng]", "[ - eng]"],
)
def test_malformed_or_unknown_language_controls_fail_closed(tmp_path, control):
    with pytest.raises(
        CallhomeEligibilityError,
        match=ERROR_UNKNOWN_LANGUAGE_CONTROL,
    ):
        _decision(tmp_path, f"{control} Synthetic words .")


@pytest.mark.parametrize("unknown_code", ["zzz", "qzx"])
def test_unknown_three_letter_language_code_fails_closed(tmp_path, unknown_code):
    with pytest.raises(
        CallhomeEligibilityError,
        match=ERROR_UNKNOWN_LANGUAGE_CONTROL,
    ):
        _decision(tmp_path, f"[- {unknown_code}] Synthetic words .")


def test_exact_one_to_one_reconciliation_succeeds(tmp_path):
    transcripts, frozen = _fixture_population(tmp_path)
    reconciled = reconcile_frozen_rows(
        transcripts,
        frozen,
        canonical_splits_by_row_id=_canonical_splits(frozen),
    )
    assert len(reconciled) == len(frozen) == 4


def test_missing_reconciliation_fails(tmp_path):
    transcripts, frozen = _fixture_population(tmp_path)
    with pytest.raises(CallhomeEligibilityError, match=ERROR_RECONCILIATION):
        reconcile_frozen_rows(
            transcripts,
            frozen[:-1],
            canonical_splits_by_row_id=_canonical_splits(frozen),
        )


def test_duplicate_reconciliation_fails(tmp_path):
    transcripts, frozen = _fixture_population(tmp_path)
    with pytest.raises(
        CallhomeEligibilityError,
        match=ERROR_DUPLICATE_RECONCILIATION,
    ):
        reconcile_frozen_rows(
            transcripts,
            [*frozen, frozen[0]],
            canonical_splits_by_row_id=_canonical_splits(frozen),
        )


def test_source_disagreement_fails(tmp_path):
    transcripts, frozen = _fixture_population(tmp_path)
    changed = [replace(frozen[0], source="callhome_spa"), *frozen[1:]]
    with pytest.raises(CallhomeEligibilityError, match=ERROR_SOURCE_DISAGREEMENT):
        reconcile_frozen_rows(
            transcripts,
            changed,
            canonical_splits_by_row_id=_canonical_splits(frozen),
        )


def test_split_disagreement_fails(tmp_path):
    transcripts, frozen = _fixture_population(tmp_path)
    changed = [frozen[0], replace(frozen[1], split="validation"), *frozen[2:]]
    with pytest.raises(CallhomeEligibilityError, match=ERROR_SPLIT_DISAGREEMENT):
        reconcile_frozen_rows(
            transcripts,
            changed,
            canonical_splits_by_row_id=_canonical_splits(frozen),
        )


def test_consistent_whole_conversation_split_reassignment_fails(tmp_path):
    transcripts, frozen = _fixture_population(tmp_path)
    changed = [
        replace(row, split="validation")
        if row.source == "callhome_eng"
        else row
        for row in frozen
    ]
    with pytest.raises(CallhomeEligibilityError, match=ERROR_SPLIT_DISAGREEMENT):
        reconcile_frozen_rows(
            transcripts,
            changed,
            canonical_splits_by_row_id=_canonical_splits(frozen),
        )


def test_provenance_disagreement_fails(tmp_path):
    transcripts, frozen = _fixture_population(tmp_path)
    changed = [replace(frozen[0], speaker_ref="spk_changed"), *frozen[1:]]
    with pytest.raises(
        CallhomeEligibilityError,
        match=ERROR_PROVENANCE_DISAGREEMENT,
    ):
        reconcile_frozen_rows(
            transcripts,
            changed,
            canonical_splits_by_row_id=_canonical_splits(frozen),
        )


def _all_leaf_values(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from _all_leaf_values(child)
    else:
        yield value


def test_aggregate_reporting_is_fixed_labels_and_counts_only(tmp_path):
    transcripts, frozen = _fixture_population(tmp_path)
    summary = audit_callhome_monolingual_eligibility(
        transcripts,
        frozen,
        canonical_splits_by_row_id=_canonical_splits(frozen),
    )
    serialized = json.dumps(summary, sort_keys=True)
    assert "Synthetic" not in serialized
    assert "Palabras" not in serialized
    assert "english.cha" not in serialized
    assert "spanish.cha" not in serialized
    assert "conv_" not in serialized
    assert "row_" not in serialized
    assert all(isinstance(value, (int, float)) for value in _all_leaf_values(summary))


def test_aggregate_results_are_deterministic(tmp_path):
    transcripts, frozen = _fixture_population(tmp_path)
    canonical_splits = _canonical_splits(frozen)
    first = audit_callhome_monolingual_eligibility(
        transcripts,
        frozen,
        canonical_splits_by_row_id=canonical_splits,
    )
    second = audit_callhome_monolingual_eligibility(
        {
            "callhome_spa": reversed(transcripts["callhome_spa"]),
            "callhome_eng": reversed(transcripts["callhome_eng"]),
        },
        reversed(frozen),
        canonical_splits_by_row_id=canonical_splits,
    )
    assert first == second


def test_english_inventory_is_shared_across_allowed_conditions():
    decision = CallhomeEligibilityDecision(ELIGIBLE_ANNOTATION_CLEAN)
    assert condition_candidates(source="callhome_eng", decision=decision) == (
        "EnglishMono",
        "MonoCont-English",
    )


def test_spanish_inventory_is_shared_across_allowed_conditions():
    decision = CallhomeEligibilityDecision(ELIGIBLE_ANNOTATION_CLEAN)
    assert condition_candidates(source="callhome_spa", decision=decision) == (
        "SpanishMono",
        "MonoCont-Spanish",
    )


def test_callhome_routing_to_cscont_is_impossible():
    eligible = CallhomeEligibilityDecision(ELIGIBLE_ANNOTATION_CLEAN)
    excluded = CallhomeEligibilityDecision(
        "excluded",
        EXPLICIT_NONEXPECTED_LANGUAGE,
    )
    for source in ("callhome_eng", "callhome_spa"):
        assert "CsCont" not in condition_candidates(source=source, decision=eligible)
        assert condition_candidates(source=source, decision=excluded) == ()
    with pytest.raises(CallhomeEligibilityError, match=ERROR_ROUTING_INVARIANT):
        condition_candidates(source="callhome_other", decision=eligible)


def test_no_accepted_output_is_produced_after_fail_closed_error(tmp_path):
    transcripts, frozen = _fixture_population(tmp_path)
    changed = [replace(frozen[0], split=None), *frozen[1:]]
    captured: list[dict[str, object]] = []
    with pytest.raises(CallhomeEligibilityError, match=ERROR_SPLIT_DISAGREEMENT):
        captured.append(
            audit_callhome_monolingual_eligibility(
                transcripts,
                changed,
                canonical_splits_by_row_id=_canonical_splits(frozen),
            )
        )
    assert captured == []


@pytest.mark.parametrize(
    ("stage", "error", "expected_category"),
    [
        (
            "transcript_reading",
            StrictChatReaderError("synthetic private detail"),
            "reader_failure",
        ),
        (
            "annotation_classification",
            CallhomeEligibilityError(ERROR_UNKNOWN_LANGUAGE_CONTROL),
            "unknown_or_malformed_language_control",
        ),
        (
            "frozen_row_reconciliation",
            CallhomeEligibilityError(ERROR_SPLIT_DISAGREEMENT),
            "split_disagreement",
        ),
        (
            "summary_calculation",
            ValueError("synthetic private detail"),
            "aggregate_calculation_failure",
        ),
    ],
)
def test_diagnostic_maps_each_major_stage_to_fixed_labels(
    stage,
    error,
    expected_category,
):
    assert audit_script._diagnostic_payload(stage, error) == {
        "error_category": expected_category,
        "stage": stage,
    }


def test_unknown_control_diagnostic_does_not_expose_payload():
    private_payload = "[- zzz] synthetic secret"
    payload = audit_script._diagnostic_payload(
        "annotation_classification",
        CallhomeEligibilityError(ERROR_UNKNOWN_LANGUAGE_CONTROL),
    )
    serialized = json.dumps(payload, sort_keys=True)
    assert payload["error_category"] == "unknown_or_malformed_language_control"
    assert private_payload not in serialized
    assert "zzz" not in serialized


def test_reconciliation_diagnostic_does_not_expose_identifier():
    private_identifier = "row_private_identifier"
    payload = audit_script._diagnostic_payload(
        "frozen_row_reconciliation",
        CallhomeEligibilityError(ERROR_PROVENANCE_DISAGREEMENT),
    )
    serialized = json.dumps(payload, sort_keys=True)
    assert payload["error_category"] == "provenance_disagreement"
    assert private_identifier not in serialized


def test_unexpected_diagnostic_failure_is_unclassified_without_raw_message():
    private_message = "synthetic raw exception detail"
    payload = audit_script._diagnostic_payload(
        "annotation_classification",
        RuntimeError(private_message),
    )
    serialized = json.dumps(payload, sort_keys=True)
    assert payload["error_category"] == "unclassified_internal_failure"
    assert private_message not in serialized


def test_diagnostic_mode_requires_execute(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["audit_callhome_monolingual_eligibility.py", "--diagnose-failure"],
    )
    with pytest.raises(SystemExit, match="explicit --execute opt-in"):
        audit_script.main()


def test_diagnostic_flag_is_explicit(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_callhome_monolingual_eligibility.py",
            "--execute",
            "--diagnose-failure",
        ],
    )
    args = audit_script._parse_args()
    assert args.execute is True
    assert args.diagnose_failure is True


def test_normal_execution_retains_generic_public_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(
        sys,
        "argv",
        ["audit_callhome_monolingual_eligibility.py", "--execute"],
    )
    monkeypatch.setattr(audit_script, "project_root", lambda: tmp_path)

    def synthetic_paths(directory):
        count = 176 if directory.name == "eng" else 140
        return [directory / f"synthetic_{index}.cha" for index in range(count)]

    monkeypatch.setattr(audit_script, "_direct_cha_files", synthetic_paths)
    monkeypatch.setattr(
        audit_script,
        "read_chat_transcript",
        lambda path: (_ for _ in ()).throw(
            StrictChatReaderError("synthetic private detail")
        ),
    )
    with pytest.raises(SystemExit) as caught:
        audit_script.main()
    assert str(caught.value) == "CALLHOME monolingual-eligibility audit failed"
    assert "synthetic private detail" not in str(caught.value)


@pytest.mark.parametrize(
    ("failure_stage", "private_detail"),
    [
        ("project_root_resolution", "private project root path"),
        ("directory_enumeration", "private enumeration path/private.cha"),
        ("transcript_reading", "private reader filename.cha"),
        ("checksum_verification", "private checksum path and hash"),
        ("annotation_classification", "private annotation payload"),
        ("frozen_row_reconciliation", "private row identifier"),
        ("summary_calculation", "private aggregate calculation detail"),
        ("unexpected_internal", "private unexpected exception detail"),
    ],
)
def test_every_normal_mode_failure_has_one_generic_privacy_boundary(
    monkeypatch,
    tmp_path,
    capsys,
    failure_stage,
    private_detail,
):
    monkeypatch.setattr(
        sys,
        "argv",
        ["audit_callhome_monolingual_eligibility.py", "--execute"],
    )
    if failure_stage == "project_root_resolution":
        monkeypatch.setattr(
            audit_script,
            "project_root",
            lambda: (_ for _ in ()).throw(RuntimeError(private_detail)),
        )
    else:
        monkeypatch.setattr(audit_script, "project_root", lambda: tmp_path)

    def synthetic_paths(directory):
        if failure_stage == "directory_enumeration":
            raise RuntimeError(private_detail)
        count = 176 if directory.name == "eng" else 140
        return [
            directory / f"invented_private_filename_{index}.cha"
            for index in range(count)
        ]

    monkeypatch.setattr(audit_script, "_direct_cha_files", synthetic_paths)

    if failure_stage == "transcript_reading":
        monkeypatch.setattr(
            audit_script,
            "read_chat_transcript",
            lambda path: (_ for _ in ()).throw(
                RuntimeError(private_detail)
            ),
        )
    else:
        monkeypatch.setattr(
            audit_script,
            "read_chat_transcript",
            lambda path: object(),
        )

    if failure_stage == "checksum_verification":
        monkeypatch.setattr(
            audit_script,
            "_load_verified_frozen_rows",
            lambda pool_root: (_ for _ in ()).throw(
                RuntimeError(private_detail)
            ),
        )
    else:
        monkeypatch.setattr(
            audit_script,
            "_load_verified_frozen_rows",
            lambda pool_root: [],
        )

    if failure_stage in {
        "annotation_classification",
        "frozen_row_reconciliation",
        "unexpected_internal",
    }:
        monkeypatch.setattr(
            audit_script,
            "audit_callhome_monolingual_eligibility",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                RuntimeError(private_detail)
            ),
        )
    else:
        monkeypatch.setattr(
            audit_script,
            "audit_callhome_monolingual_eligibility",
            lambda *args, **kwargs: {"synthetic_summary": 0},
        )

    if failure_stage == "summary_calculation":
        monkeypatch.setattr(
            audit_script.json,
            "dumps",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                RuntimeError(private_detail)
            ),
        )

    with pytest.raises(SystemExit) as caught:
        audit_script.main()
    captured = capsys.readouterr()
    assert caught.value.code == "CALLHOME monolingual-eligibility audit failed"
    assert caught.value.code != 0
    assert captured.out == ""
    assert captured.err == ""
    serialized_failure = str(caught.value)
    assert serialized_failure == "CALLHOME monolingual-eligibility audit failed"
    assert private_detail not in serialized_failure
    assert str(tmp_path) not in serialized_failure
    assert "invented_private_filename" not in serialized_failure
    assert "Traceback" not in serialized_failure
    assert "synthetic_summary" not in serialized_failure


def test_synthetic_frozen_pool_verification_accepts_exact_artifacts(
    monkeypatch,
    tmp_path,
):
    pool_root, _ = _write_synthetic_verified_pool(tmp_path, monkeypatch)
    assert audit_script._load_verified_frozen_rows(pool_root) == []


def test_modified_checksum_record_fails_closed(monkeypatch, tmp_path):
    pool_root, checksums = _write_synthetic_verified_pool(tmp_path, monkeypatch)
    checksums["english_rows.jsonl"] = "0" * 64
    _rewrite_synthetic_checksum_record(pool_root, checksums, monkeypatch)
    with pytest.raises(ValueError, match="CALLHOME monolingual-eligibility audit failed"):
        audit_script._load_verified_frozen_rows(pool_root)


@pytest.mark.parametrize(
    "artifact_name",
    ["english_rows.jsonl", "spanish_rows.jsonl", "manifest.json"],
)
def test_modified_frozen_artifact_fails_closed(
    monkeypatch,
    tmp_path,
    artifact_name,
):
    pool_root, _ = _write_synthetic_verified_pool(tmp_path, monkeypatch)
    (pool_root / artifact_name).write_bytes(b"synthetic altered content")
    with pytest.raises(ValueError, match="CALLHOME monolingual-eligibility audit failed"):
        audit_script._load_verified_frozen_rows(pool_root)


def test_missing_checksum_entry_fails_closed(monkeypatch, tmp_path):
    pool_root, checksums = _write_synthetic_verified_pool(tmp_path, monkeypatch)
    del checksums["manifest.json"]
    _rewrite_synthetic_checksum_record(pool_root, checksums, monkeypatch)
    with pytest.raises(ValueError, match="CALLHOME monolingual-eligibility audit failed"):
        audit_script._load_verified_frozen_rows(pool_root)


def test_unexpected_checksum_entry_fails_closed(monkeypatch, tmp_path):
    pool_root, checksums = _write_synthetic_verified_pool(tmp_path, monkeypatch)
    checksums["unexpected.bin"] = hashlib.sha256(b"").hexdigest()
    _rewrite_synthetic_checksum_record(pool_root, checksums, monkeypatch)
    with pytest.raises(ValueError, match="CALLHOME monolingual-eligibility audit failed"):
        audit_script._load_verified_frozen_rows(pool_root)


def test_unexpected_pool_filename_fails_closed(monkeypatch, tmp_path):
    pool_root, _ = _write_synthetic_verified_pool(tmp_path, monkeypatch)
    (pool_root / "unexpected.bin").write_bytes(b"synthetic")
    with pytest.raises(ValueError, match="CALLHOME monolingual-eligibility audit failed"):
        audit_script._load_verified_frozen_rows(pool_root)


def test_pinned_checksum_record_disagreement_fails_closed(monkeypatch, tmp_path):
    pool_root, _ = _write_synthetic_verified_pool(tmp_path, monkeypatch)
    monkeypatch.setattr(
        audit_script,
        "EXPECTED_FROZEN_CHECKSUMS_SHA256",
        "0" * 64,
    )
    with pytest.raises(ValueError, match="CALLHOME monolingual-eligibility audit failed"):
        audit_script._load_verified_frozen_rows(pool_root)


def test_checksum_failure_diagnostic_is_fixed_and_private():
    private_detail = "private checksum path filename hash"
    payload = audit_script._diagnostic_payload(
        "frozen_row_reconciliation",
        ValueError(private_detail),
    )
    assert payload == {
        "error_category": "frozen_pool_verification_failure",
        "stage": "frozen_row_reconciliation",
    }
    assert private_detail not in json.dumps(payload, sort_keys=True)


def test_diagnostic_output_contains_only_fixed_labels(capsys):
    audit_script._print_diagnostic(
        "frozen_row_reconciliation",
        CallhomeEligibilityError(ERROR_RECONCILIATION),
    )
    output = capsys.readouterr().out
    assert json.loads(output) == {
        "error_category": "missing_reconciliation",
        "stage": "frozen_row_reconciliation",
    }
    assert "Traceback" not in output


def test_diagnostic_output_is_byte_deterministic(capsys):
    error = CallhomeEligibilityError(ERROR_UNKNOWN_LANGUAGE_CONTROL)
    audit_script._print_diagnostic("annotation_classification", error)
    first = capsys.readouterr().out
    audit_script._print_diagnostic("annotation_classification", error)
    second = capsys.readouterr().out
    assert first == second


def test_successful_diagnostic_has_fixed_no_failure_payload():
    assert audit_script._diagnostic_payload("summary_calculation", None) == {
        "error_category": "no_failure",
        "stage": "summary_calculation",
    }


def test_diagnostic_project_root_failure_is_fixed_json(
    monkeypatch,
    capsys,
):
    private_detail = "private project root path and filename"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_callhome_monolingual_eligibility.py",
            "--execute",
            "--diagnose-failure",
        ],
    )
    monkeypatch.setattr(
        audit_script,
        "project_root",
        lambda: (_ for _ in ()).throw(RuntimeError(private_detail)),
    )
    assert audit_script.main() == 1
    output = capsys.readouterr()
    assert json.loads(output.out) == {
        "error_category": "unclassified_internal_failure",
        "stage": "transcript_reading",
    }
    assert output.err == ""
    assert private_detail not in output.out
    assert "RuntimeError" not in output.out
    assert "Traceback" not in output.out


def test_diagnostic_serialization_failure_uses_fixed_json(
    monkeypatch,
    capsys,
):
    private_detail = "private serialization path and identifier"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_callhome_monolingual_eligibility.py",
            "--execute",
            "--diagnose-failure",
        ],
    )
    monkeypatch.setattr(
        audit_script,
        "project_root",
        lambda: (_ for _ in ()).throw(RuntimeError(private_detail)),
    )
    monkeypatch.setattr(
        audit_script.json,
        "dumps",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError(private_detail)
        ),
    )
    assert audit_script.main() == 1
    output = capsys.readouterr()
    assert output.out == audit_script._FIXED_UNCLASSIFIED_DIAGNOSTIC + "\n"
    assert output.err == ""
    assert private_detail not in output.out
    assert "RuntimeError" not in output.out
    assert "Traceback" not in output.out


def test_diagnostic_output_failure_uses_fixed_system_exit(
    monkeypatch,
    capsys,
):
    private_detail = "private output filename and payload"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_callhome_monolingual_eligibility.py",
            "--execute",
            "--diagnose-failure",
        ],
    )
    monkeypatch.setattr(
        audit_script,
        "project_root",
        lambda: (_ for _ in ()).throw(RuntimeError(private_detail)),
    )
    monkeypatch.setattr(
        builtins,
        "print",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError(private_detail)
        ),
    )
    with pytest.raises(SystemExit) as caught:
        audit_script.main()
    output = capsys.readouterr()
    assert caught.value.code == audit_script._FIXED_UNCLASSIFIED_DIAGNOSTIC
    assert output.out == ""
    assert output.err == ""
    assert private_detail not in str(caught.value)
    assert "RuntimeError" not in str(caught.value)
    assert "Traceback" not in str(caught.value)


@pytest.mark.parametrize(
    "control",
    [
        "[- eng]",
        "[- spa]",
        "[- mul]",
        "[- und]",
        "[- ?]",
        "[- eng, spa]",
        "[- deu]",
        "[- fra]",
        "[- grn]",
        "[- heb]",
        "[- jpn]",
        "[- pol]",
        "[- yid]",
    ],
)
def test_census_omits_controls_supported_by_current_parser(control):
    assert audit_script._sanitize_census_control(control) is None


@pytest.mark.parametrize(
    "marker",
    ["deu", "fra", "grn", "heb", "jpn", "pol", "yid"],
)
@pytest.mark.parametrize(
    ("source", "language"),
    [("callhome_eng", "eng"), ("callhome_spa", "spa")],
)
def test_documented_nontarget_codes_do_not_trigger_failure_diagnostic(
    tmp_path,
    source,
    language,
    marker,
):
    transcript = _transcript(
        tmp_path,
        f"[- {marker}] Synthetic words .",
        language=language,
    )
    transcripts = {"callhome_eng": [], "callhome_spa": []}
    transcripts[source] = [transcript]
    audit_script._classify_annotations(transcripts)


def test_census_counts_unknown_code_without_exposing_value():
    private_code = "zzz"
    result = audit_script._sanitize_census_control(f"[- {private_code}]")
    assert result == ("unknown_code", "single_alpha_length_three")
    assert private_code not in json.dumps(result)


@pytest.mark.parametrize(
    ("control", "expected_category", "expected_shape"),
    [
        ("[-]", "unsupported_empty_form", "empty"),
        ("[-eng]", "unsupported_delimiter_form", "single_alpha_length_three"),
        ("[ - eng]", "unsupported_delimiter_form", "single_alpha_length_three"),
        (
            "[- eng spa]",
            "unsupported_multi_value_form",
            "whitespace_separated_alpha",
        ),
        (
            "[- eng, eng]",
            "unsupported_multi_value_form",
            "comma_separated_alpha",
        ),
        ("[- eng;spa]", "unsupported_delimiter_form", "punctuation_present"),
        ("[- abcd]", "malformed_payload", "single_alpha_other_length"),
    ],
)
def test_census_assigns_fixed_sanitized_malformed_categories(
    control,
    expected_category,
    expected_shape,
):
    assert audit_script._sanitize_census_control(control) == (
        expected_category,
        expected_shape,
    )


def test_unexpected_census_structure_uses_other_bucket():
    assert audit_script._sanitize_census_control("synthetic non-control") == (
        "other_sanitized_structure",
        "other",
    )


def _synthetic_census_records():
    return [
        (
            "english",
            "train",
            "private_conversation_one",
            (
                ("unknown_code", "single_alpha_length_three"),
                ("unsupported_delimiter_form", "punctuation_present"),
            ),
        ),
        (
            "english",
            "validation",
            "private_conversation_two",
            (("malformed_payload", "single_alpha_other_length"),),
        ),
        (
            "spanish",
            "test",
            "private_conversation_three",
            (("unknown_code", "single_alpha_length_three"),),
        ),
    ]


def test_census_aggregates_sources_splits_categories_and_conversations():
    summary = audit_script._summarize_census_records(_synthetic_census_records())
    combined = summary["combined"]
    assert combined["occurrences"] == 4
    assert combined["affected_utterances"] == 3
    assert combined["affected_conversations"] == 3
    assert combined["utterances_with_multiple_controls"] == 1
    assert combined["splits"]["train"] == {
        "occurrences": 2,
        "affected_utterances": 1,
        "affected_conversations": 1,
    }
    assert combined["splits"]["validation"]["occurrences"] == 1
    assert combined["splits"]["test"]["occurrences"] == 1
    assert summary["sources"]["english"]["occurrences"] == 3
    assert summary["sources"]["spanish"]["occurrences"] == 1
    assert combined["categories"]["unknown_code"] == 2
    assert summary["category_occurs_in_both_sources"]["unknown_code"] is True
    assert summary["more_than_one_unknown_control_in_affected_utterance"] is True


def test_census_totals_reconcile_exactly():
    summary = audit_script._summarize_census_records(_synthetic_census_records())
    combined = summary["combined"]
    assert sum(combined["categories"].values()) == combined["occurrences"]
    assert sum(combined["shapes"].values()) == combined["occurrences"]
    assert (
        sum(split["occurrences"] for split in combined["splits"].values())
        == combined["occurrences"]
    )
    assert (
        sum(
            source["occurrences"] for source in summary["sources"].values()
        )
        == combined["occurrences"]
    )


def test_census_summary_exposes_no_payload_or_identifier():
    private_values = (
        "zzz",
        "private_conversation_one",
        "private_conversation_two",
        "private_conversation_three",
        "/private/synthetic/path",
    )
    serialized = json.dumps(
        audit_script._summarize_census_records(_synthetic_census_records()),
        sort_keys=True,
    )
    assert all(value not in serialized for value in private_values)
    assert "Traceback" not in serialized


def test_census_output_is_deterministic_across_record_order():
    records = _synthetic_census_records()
    first = json.dumps(
        audit_script._summarize_census_records(records),
        sort_keys=True,
        separators=(",", ":"),
    )
    second = json.dumps(
        audit_script._summarize_census_records(list(reversed(records))),
        sort_keys=True,
        separators=(",", ":"),
    )
    assert first == second


def test_census_mode_requires_execute(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["audit_callhome_monolingual_eligibility.py", "--census-unknown-controls"],
    )
    with pytest.raises(SystemExit, match="explicit --execute opt-in"):
        audit_script.main()


def test_census_requires_dedicated_flag(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["audit_callhome_monolingual_eligibility.py", "--execute"],
    )
    args = audit_script._parse_args()
    assert args.census_unknown_controls is False

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_callhome_monolingual_eligibility.py",
            "--execute",
            "--census-unknown-controls",
        ],
    )
    args = audit_script._parse_args()
    assert args.census_unknown_controls is True


def test_census_and_failure_diagnostic_are_mutually_exclusive(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_callhome_monolingual_eligibility.py",
            "--execute",
            "--diagnose-failure",
            "--census-unknown-controls",
        ],
    )
    with pytest.raises(SystemExit, match="exactly one privacy-safe diagnostic"):
        audit_script.main()


def test_census_failure_is_generic_without_raw_exception(monkeypatch, tmp_path):
    private_message = "synthetic raw census exception"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_callhome_monolingual_eligibility.py",
            "--execute",
            "--census-unknown-controls",
        ],
    )
    monkeypatch.setattr(audit_script, "project_root", lambda: tmp_path)
    monkeypatch.setattr(
        audit_script,
        "_run_unknown_control_census",
        lambda raw_root, pool_root: (_ for _ in ()).throw(
            RuntimeError(private_message)
        ),
    )
    with pytest.raises(SystemExit) as caught:
        audit_script.main()
    assert str(caught.value) == "CALLHOME unknown-language-control census failed"
    assert private_message not in str(caught.value)


def _assert_fixed_census_failure(caught, captured, private_detail, tmp_path):
    assert caught.value.code == "CALLHOME unknown-language-control census failed"
    assert caught.value.code != 0
    assert captured.out == ""
    assert captured.err == ""
    serialized = str(caught.value)
    assert private_detail not in serialized
    assert str(tmp_path) not in serialized
    assert "invented_private_filename" not in serialized
    assert "RuntimeError" not in serialized
    assert "Traceback" not in serialized
    assert "partial_summary" not in serialized


def test_census_project_root_failure_is_generic(
    monkeypatch,
    tmp_path,
    capsys,
):
    private_detail = "private census project root path"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_callhome_monolingual_eligibility.py",
            "--execute",
            "--census-unknown-controls",
        ],
    )
    monkeypatch.setattr(
        audit_script,
        "project_root",
        lambda: (_ for _ in ()).throw(RuntimeError(private_detail)),
    )
    with pytest.raises(SystemExit) as caught:
        audit_script.main()
    _assert_fixed_census_failure(
        caught,
        capsys.readouterr(),
        private_detail,
        tmp_path,
    )


@pytest.mark.parametrize(
    ("failure_stage", "private_detail"),
    [
        ("transcript_reading", "private transcript filename and payload"),
        ("aggregate_calculation", "private aggregate row identifier"),
    ],
)
def test_census_processing_failure_is_generic(
    monkeypatch,
    tmp_path,
    capsys,
    failure_stage,
    private_detail,
):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_callhome_monolingual_eligibility.py",
            "--execute",
            "--census-unknown-controls",
        ],
    )
    monkeypatch.setattr(audit_script, "project_root", lambda: tmp_path)
    monkeypatch.setattr(
        audit_script,
        "_run_unknown_control_census",
        lambda raw_root, pool_root: (_ for _ in ()).throw(
            RuntimeError(f"{failure_stage}: {private_detail}")
        ),
    )
    with pytest.raises(SystemExit) as caught:
        audit_script.main()
    _assert_fixed_census_failure(
        caught,
        capsys.readouterr(),
        private_detail,
        tmp_path,
    )


def test_census_serialization_failure_is_generic(
    monkeypatch,
    tmp_path,
    capsys,
):
    private_detail = "private census serialization identifier"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_callhome_monolingual_eligibility.py",
            "--execute",
            "--census-unknown-controls",
        ],
    )
    monkeypatch.setattr(audit_script, "project_root", lambda: tmp_path)
    monkeypatch.setattr(
        audit_script,
        "_run_unknown_control_census",
        lambda raw_root, pool_root: {"partial_summary": 1},
    )
    monkeypatch.setattr(
        audit_script.json,
        "dumps",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError(private_detail)
        ),
    )
    with pytest.raises(SystemExit) as caught:
        audit_script.main()
    _assert_fixed_census_failure(
        caught,
        capsys.readouterr(),
        private_detail,
        tmp_path,
    )


def test_census_output_failure_is_generic(
    monkeypatch,
    tmp_path,
    capsys,
):
    private_detail = "private census output filename and payload"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_callhome_monolingual_eligibility.py",
            "--execute",
            "--census-unknown-controls",
        ],
    )
    monkeypatch.setattr(audit_script, "project_root", lambda: tmp_path)
    monkeypatch.setattr(
        audit_script,
        "_run_unknown_control_census",
        lambda raw_root, pool_root: {"partial_summary": 1},
    )
    monkeypatch.setattr(
        builtins,
        "print",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            RuntimeError(private_detail)
        ),
    )
    with pytest.raises(SystemExit) as caught:
        audit_script.main()
    _assert_fixed_census_failure(
        caught,
        capsys.readouterr(),
        private_detail,
        tmp_path,
    )


def test_successful_census_output_is_byte_deterministic(
    monkeypatch,
    tmp_path,
    capsys,
):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_callhome_monolingual_eligibility.py",
            "--execute",
            "--census-unknown-controls",
        ],
    )
    monkeypatch.setattr(audit_script, "project_root", lambda: tmp_path)
    summary = {
        "combined": {"occurrences": 1},
        "sources": {"english": {"occurrences": 1}},
    }
    monkeypatch.setattr(
        audit_script,
        "_run_unknown_control_census",
        lambda raw_root, pool_root: summary,
    )
    assert audit_script.main() == 0
    first = capsys.readouterr()
    assert audit_script.main() == 0
    second = capsys.readouterr()
    expected = json.dumps(
        summary,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"
    assert first.out == second.out == expected
    assert first.err == second.err == ""


def test_identical_census_failures_are_byte_deterministic(
    monkeypatch,
    tmp_path,
    capsys,
):
    private_detail = "private repeated census failure"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "audit_callhome_monolingual_eligibility.py",
            "--execute",
            "--census-unknown-controls",
        ],
    )
    monkeypatch.setattr(audit_script, "project_root", lambda: tmp_path)
    monkeypatch.setattr(
        audit_script,
        "_run_unknown_control_census",
        lambda raw_root, pool_root: (_ for _ in ()).throw(
            RuntimeError(private_detail)
        ),
    )
    failures = []
    for _ in range(2):
        with pytest.raises(SystemExit) as caught:
            audit_script.main()
        failures.append(str(caught.value))
        captured = capsys.readouterr()
        assert captured.out == captured.err == ""
    assert failures == [
        "CALLHOME unknown-language-control census failed",
        "CALLHOME unknown-language-control census failed",
    ]
    assert private_detail not in "".join(failures)


def test_census_path_makes_no_eligibility_decision(monkeypatch, tmp_path):
    english_path = _write_chat(
        tmp_path,
        "census_english.cha",
        "eng",
        ["Synthetic [- zzz] words ."],
    )
    spanish_path = _write_chat(
        tmp_path,
        "census_spanish.cha",
        "spa",
        ["Palabras sinteticas ."],
    )
    transcripts = {
        "eng": read_chat_transcript(english_path),
        "spa": read_chat_transcript(spanish_path),
    }
    english_rows = build_population_rows(
        [english_path],
        source="callhome_eng",
    ).rows
    spanish_rows = build_population_rows(
        [spanish_path],
        source="callhome_spa",
    ).rows
    frozen = [
        replace(row, split="train")
        for row in [*english_rows, *spanish_rows]
    ]

    def synthetic_paths(directory):
        count = 176 if directory.name == "eng" else 140
        return [directory / f"synthetic_{index}.cha" for index in range(count)]

    monkeypatch.setattr(audit_script, "_direct_cha_files", synthetic_paths)
    monkeypatch.setattr(
        audit_script,
        "read_chat_transcript",
        lambda path: transcripts[path.parent.name],
    )
    monkeypatch.setattr(
        audit_script,
        "_load_verified_frozen_rows",
        lambda pool_root: frozen,
    )
    monkeypatch.setattr(
        audit_script,
        "evaluate_utterance_annotation_eligibility",
        lambda utterance, source: (_ for _ in ()).throw(
            AssertionError("eligibility decision must not run")
        ),
    )
    summary = audit_script._run_unknown_control_census(
        tmp_path / "raw",
        tmp_path / "pools",
    )
    assert summary["combined"]["occurrences"] == 176
    assert summary["sources"]["english"]["occurrences"] == 176
    assert summary["sources"]["spanish"]["occurrences"] == 0
