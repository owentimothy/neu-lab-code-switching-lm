"""Tests for the synthetic-only CALLHOME projection scaffold.

All CHAT content is SYNTHETIC (fake ``AAA``/``BBB`` speaker codes, ``syn_*``
tokens). No real CALLHOME files or transcript text are used. The projection
must (a) never route CALLHOME rows to CsCont, (b) never silently admit non-clean
rows, and (c) de-identify speaker/source references in its safe outputs.
"""

import pytest

from cslm.data.callhome_chat import parse_chat_lines
from cslm.data.callhome_project import (
    CallhomeProjectedRow,
    callhome_condition_candidates,
    project_transcript,
    project_utterance,
)

_SYNTH_LINES = [
    "@UTF8",
    "@Begin",
    "@Languages:\teng",
    "@Participants:\tAAA Adult, BBB Adult",
    "*AAA:\tsyn_alpha syn_beta .",
    "%mor:\tsyn_mortag_one syn_mortag_two",
    "*BBB:\tsyn_gamma .",
    "@End",
]


def _synth_transcript(source_file="synth_00.cha"):
    return parse_chat_lines(_SYNTH_LINES, source_file=source_file)


def _all_strings(obj):
    out = []
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            out.append(str(k))
            out.extend(_all_strings(v))
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            out.extend(_all_strings(v))
    return out


def test_clean_english_row_eligible_for_englishmono_and_monocont():
    utt = _synth_transcript().utterances[0]
    row = project_utterance(utt, language_label="eng", screening_outcome="clean")
    assert row.source == "callhome_eng"
    assert row.condition_candidates == ["EnglishMono", "MonoCont"]
    assert "CsCont" not in row.condition_candidates


def test_clean_spanish_row_eligible_for_spanishmono_and_monocont():
    lines = [ln.replace("@Languages:\teng", "@Languages:\tspa") for ln in _SYNTH_LINES]
    utt = parse_chat_lines(lines, source_file="synth_es.cha").utterances[0]
    row = project_utterance(utt, language_label="spa", screening_outcome="clean")
    assert row.source == "callhome_spa"
    assert row.condition_candidates == ["SpanishMono", "MonoCont"]
    assert "CsCont" not in row.condition_candidates


def test_non_clean_rows_are_not_silently_admitted():
    utt = _synth_transcript().utterances[0]
    review = project_utterance(utt, language_label="eng", screening_outcome="needs_review")
    excluded = project_utterance(utt, language_label="eng", screening_outcome="excluded")
    assert review.condition_candidates == []
    assert review.needs_review is True
    assert excluded.condition_candidates == []
    assert excluded.needs_review is False


def test_default_screening_outcome_admits_nothing():
    # No explicit screening decision -> conservative needs_review, no conditions.
    utt = _synth_transcript().utterances[0]
    row = project_utterance(utt, language_label="eng")
    assert row.screening_outcome == "needs_review"
    assert row.condition_candidates == []


def test_callhome_never_assigns_cscont():
    for label in ("eng", "spa"):
        for outcome in ("clean", "needs_review", "excluded"):
            source = f"callhome_{label}"
            assert "CsCont" not in callhome_condition_candidates(source, outcome)


def test_constructing_row_with_cscont_raises():
    with pytest.raises(ValueError):
        CallhomeProjectedRow(
            source="callhome_eng",
            conversation_id="synth_00",
            turn_index=0,
            speaker_ref="spk_deadbeef",
            source_file_ref="file_deadbeef",
            screening_outcome="clean",
            condition_candidates=["EnglishMono", "CsCont"],
        )


def test_speaker_and_source_refs_are_deidentified():
    utt = _synth_transcript(source_file="synth_secretname.cha").utterances[0]
    assert utt.speaker_id == "AAA"  # raw code present on the parser object
    row = project_utterance(utt, language_label="eng", screening_outcome="clean")
    # De-identified refs do not expose the raw speaker code or filename.
    assert row.speaker_ref != "AAA"
    assert "AAA" not in row.speaker_ref
    assert "secretname" not in row.source_file_ref
    assert row.speaker_ref.startswith("spk_")
    assert row.source_file_ref.startswith("file_")


def test_refs_are_stable_and_speaker_salted_by_conversation():
    utt = _synth_transcript().utterances[0]
    r1 = project_utterance(utt, language_label="eng", screening_outcome="clean")
    r2 = project_utterance(utt, language_label="eng", screening_outcome="clean")
    assert r1.speaker_ref == r2.speaker_ref  # deterministic
    # Same speaker code in a different conversation salts to a different ref.
    other = parse_chat_lines(
        [ln for ln in _SYNTH_LINES], source_file="synth_99.cha"
    ).utterances[0]
    other.conversation_id = "different_conv"
    r3 = project_utterance(other, language_label="eng", screening_outcome="clean")
    assert r3.speaker_ref != r1.speaker_ref


def test_raw_text_is_in_memory_only_and_excluded_from_provenance():
    utt = _synth_transcript().utterances[0]
    without = project_utterance(utt, language_label="eng", screening_outcome="clean")
    assert without.raw_text is None  # not kept by default
    with_text = project_utterance(
        utt, language_label="eng", screening_outcome="clean", keep_text=True
    )
    assert with_text.raw_text is not None  # retained in memory
    # ...but never appears in the safe provenance surface.
    prov = with_text.to_provenance_dict()
    strings = _all_strings(prov)
    for token in ("syn_alpha", "syn_beta", "syn_gamma"):
        assert all(token not in s for s in strings), token
    assert "raw_text" not in prov


def test_provenance_dict_has_no_forbidden_content():
    utt = _synth_transcript().utterances[0]
    row = project_utterance(utt, language_label="eng", screening_outcome="clean")
    prov = row.to_provenance_dict()
    # No raw speaker code or transcript token leaks in the safe provenance view.
    for token in ("AAA", "BBB", "syn_"):
        assert all(token not in s for s in _all_strings(prov)), token
    # conversation_id is safe provenance and legitimately present.
    assert prov["conversation_id"] == "synth_00"
    assert "raw_text" not in prov


def test_project_transcript_preserves_order_and_screening_map():
    transcript = _synth_transcript()
    rows = project_transcript(
        transcript,
        language_label="eng",
        screening_by_turn={0: "clean"},  # turn 1 defaults to needs_review
    )
    assert [r.turn_index for r in rows] == [0, 1]
    assert rows[0].screening_outcome == "clean"
    assert rows[0].condition_candidates == ["EnglishMono", "MonoCont"]
    assert rows[1].screening_outcome == "needs_review"
    assert rows[1].condition_candidates == []
    assert all(r.conversation_id == "synth_00" for r in rows)


def test_invalid_inputs_raise():
    utt = _synth_transcript().utterances[0]
    with pytest.raises(ValueError):
        project_utterance(utt, language_label="fra", screening_outcome="clean")
    with pytest.raises(ValueError):
        project_utterance(utt, language_label="eng", screening_outcome="maybe")
    with pytest.raises(ValueError):
        callhome_condition_candidates("callhome_fra", "clean")
