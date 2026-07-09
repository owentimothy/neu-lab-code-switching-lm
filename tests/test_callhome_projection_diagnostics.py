"""Tests for the aggregate-only CALLHOME projection diagnostics.

All rows are built from SYNTHETIC CHAT strings (fake ``AAA``/``BBB`` codes,
``syn_*`` tokens) via the parser + projection scaffolds, or constructed directly
as fake projected rows. No real CALLHOME files or transcript text are used. The
diagnostics must stay aggregate-only: no transcript-bearing content may appear
in any output.
"""

import pytest

from cslm.data.callhome_chat import parse_chat_lines
from cslm.data.callhome_project import (
    CallhomeProjectedRow,
    project_transcript,
)
from cslm.data.callhome_projection_diagnostics import (
    flatten_projection_summary,
    summarize_projected_rows,
)

_SYNTH_LINES = [
    "@UTF8",
    "@Begin",
    "@Languages:\teng",
    "@Participants:\tAAA Adult, BBB Adult",
    "*AAA:\tsyn_alpha syn_beta .",
    "*BBB:\tsyn_gamma .",
    "@End",
]


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


def _row(source, screening_outcome, candidates, *, needs_review=False, raw_text=None):
    return CallhomeProjectedRow(
        source=source,
        conversation_id="synth_00",
        turn_index=0,
        speaker_ref="spk_deadbeef",
        source_file_ref="file_deadbeef",
        screening_outcome=screening_outcome,
        condition_candidates=list(candidates),
        needs_review=needs_review,
        raw_text=raw_text,
    )


def _mixed_rows():
    return [
        _row("callhome_eng", "clean", ["EnglishMono", "MonoCont"]),
        _row("callhome_eng", "needs_review", [], needs_review=True),
        _row("callhome_spa", "clean", ["SpanishMono", "MonoCont"]),
        _row("callhome_spa", "excluded", []),
    ]


def test_total_rows_and_by_source():
    s = summarize_projected_rows(_mixed_rows())
    assert s.n_rows == 4
    assert s.rows_by_source == {"callhome_eng": 2, "callhome_spa": 2}


def test_by_screening_outcome_includes_all_known_outcomes():
    s = summarize_projected_rows(_mixed_rows())
    assert s.rows_by_screening_outcome == {
        "clean": 2,
        "needs_review": 1,
        "excluded": 1,
    }


def test_by_condition_candidate_counts_overlap():
    s = summarize_projected_rows(_mixed_rows())
    # Each clean row is eligible for its mono baseline AND MonoCont.
    assert s.rows_by_condition_candidate == {
        "EnglishMono": 1,
        "SpanishMono": 1,
        "MonoCont": 2,
    }


def test_needs_review_and_blocked_counts():
    s = summarize_projected_rows(_mixed_rows())
    assert s.n_needs_review == 1
    assert s.n_blocked_from_all_conditions == 2  # needs_review + excluded rows


def test_empty_input_is_all_zero_with_stable_keys():
    s = summarize_projected_rows([])
    assert s.n_rows == 0
    assert s.rows_by_source == {"callhome_eng": 0, "callhome_spa": 0}
    assert set(s.rows_by_screening_outcome) == {"clean", "needs_review", "excluded"}
    assert s.rows_by_condition_candidate == {
        "EnglishMono": 0,
        "SpanishMono": 0,
        "MonoCont": 0,
    }


def test_invariant_rejects_cscont_in_candidates():
    # Bypass the row's own guard by mutating after construction, to prove the
    # diagnostics layer independently enforces the no-CsCont invariant.
    bad = _row("callhome_eng", "clean", ["EnglishMono"])
    bad.condition_candidates.append("CsCont")
    with pytest.raises(ValueError, match="CsCont"):
        summarize_projected_rows([bad])


def test_invariant_rejects_non_monolingual_condition():
    bad = _row("callhome_eng", "clean", ["EnglishMono"])
    bad.condition_candidates.append("SomethingElse")
    with pytest.raises(ValueError):
        summarize_projected_rows([bad])


def test_invariant_rejects_unknown_source():
    # Mutate after construction to bypass the CallhomeProjectedRow guard.
    bad = _row("callhome_eng", "clean", ["EnglishMono", "MonoCont"])
    bad.source = "callhome_fra"
    with pytest.raises(ValueError, match="callhome_fra"):
        summarize_projected_rows([bad])


def test_invariant_rejects_unknown_screening_outcome():
    bad = _row("callhome_eng", "clean", ["EnglishMono", "MonoCont"])
    bad.screening_outcome = "maybe"
    with pytest.raises(ValueError, match="maybe"):
        summarize_projected_rows([bad])


def test_flatten_is_scalar_int_only():
    s = summarize_projected_rows(_mixed_rows())
    flat = flatten_projection_summary(s)
    assert all(isinstance(v, int) for v in flat.values())
    assert flat["n_rows"] == 4
    assert flat["source__callhome_eng"] == 2
    assert flat["screening__clean"] == 2
    assert flat["condition__MonoCont"] == 2
    assert flat["n_blocked_from_all_conditions"] == 2


def test_flatten_has_no_transcript_bearing_fields():
    # Include raw_text on rows to prove it never reaches the aggregate output.
    rows = [
        _row("callhome_eng", "clean", ["EnglishMono", "MonoCont"], raw_text="syn_secret"),
        _row("callhome_spa", "excluded", [], raw_text="syn_hidden"),
    ]
    flat = flatten_projection_summary(summarize_projected_rows(rows))
    forbidden_keys = {"raw_text", "text", "tokens", "speaker_ref", "source_file_ref"}
    assert set(flat.keys()) & forbidden_keys == set()
    strings = _all_strings(flat)
    for token in ("syn_secret", "syn_hidden", "syn_", "AAA", "deadbeef"):
        assert all(token not in s for s in strings), token


def test_to_dict_is_aggregate_only():
    rows = [_row("callhome_eng", "clean", ["EnglishMono", "MonoCont"], raw_text="syn_x")]
    d = summarize_projected_rows(rows).to_dict()
    strings = _all_strings(d)
    for token in ("syn_x", "raw_text", "deadbeef", "AAA"):
        assert all(token not in s for s in strings), token


def test_summarizes_rows_from_synthetic_parser_projection():
    # End-to-end over the synthetic parser + projector (no real files).
    transcript = parse_chat_lines(_SYNTH_LINES, source_file="synth_00.cha")
    rows = project_transcript(
        transcript, language_label="eng", screening_by_turn={0: "clean"}
    )
    s = summarize_projected_rows(rows)
    assert s.n_rows == 2
    assert s.rows_by_source == {"callhome_eng": 2, "callhome_spa": 0}
    assert s.rows_by_condition_candidate["EnglishMono"] == 1  # only turn 0 clean
    assert s.n_blocked_from_all_conditions == 1  # turn 1 defaults needs_review
