"""Synthetic tests for CALLHOME annotation-based monolingual eligibility."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from cslm.data.callhome_chat import CallhomeTranscript, read_chat_transcript
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


def test_unknown_three_letter_language_code_fails_closed(tmp_path):
    with pytest.raises(
        CallhomeEligibilityError,
        match=ERROR_UNKNOWN_LANGUAGE_CONTROL,
    ):
        _decision(tmp_path, "[- zzz] Synthetic words .")


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
