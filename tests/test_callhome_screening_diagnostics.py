"""Tests for the aggregate-only CALLHOME screening diagnostics.

All decisions are synthetic. No real CALLHOME files or transcript text are used.
The summaries must stay aggregate-only: decision ``notes`` (which may contain
free text) must never appear in any output.
"""

import pytest

from cslm.data.callhome_screening import (
    REASON_CODES,
    CallhomeScreeningDecision,
)
from cslm.data.callhome_screening_diagnostics import (
    OUTCOME_ORDER,
    REASON_CODE_ORDER,
    flatten_screening_summary,
    summarize_screening_decisions,
)


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


def _decisions():
    return [
        CallhomeScreeningDecision(outcome="clean", reason_codes=["source_language_expected"]),
        CallhomeScreeningDecision(
            outcome="needs_review",
            reason_codes=["ambiguous_foreign_material", "possible_code_switching"],
        ),
        CallhomeScreeningDecision(outcome="needs_review", reason_codes=["parser_warning"]),
        CallhomeScreeningDecision(outcome="excluded", reason_codes=["empty_or_nonlexical"]),
        CallhomeScreeningDecision(
            outcome="excluded", reason_codes=["unsupported_language_label"]
        ),
    ]


def test_total_and_by_outcome():
    s = summarize_screening_decisions(_decisions())
    assert s.n_decisions == 5
    assert s.decisions_by_outcome == {"clean": 1, "needs_review": 2, "excluded": 2}


def test_by_reason_code_counts_overlap():
    s = summarize_screening_decisions(_decisions())
    # The needs_review row with two reasons contributes to both buckets.
    assert s.decisions_by_reason_code["ambiguous_foreign_material"] == 1
    assert s.decisions_by_reason_code["possible_code_switching"] == 1
    assert s.decisions_by_reason_code["parser_warning"] == 1
    assert s.decisions_by_reason_code["source_language_expected"] == 1
    # Reason-code counts can sum to more than n_decisions.
    assert sum(s.decisions_by_reason_code.values()) == 6


def test_empty_input_is_all_zero_with_stable_keys():
    s = summarize_screening_decisions([])
    assert s.n_decisions == 0
    assert set(s.decisions_by_outcome) == set(OUTCOME_ORDER)
    assert set(s.decisions_by_reason_code) == set(REASON_CODE_ORDER)
    assert all(v == 0 for v in s.decisions_by_outcome.values())
    assert all(v == 0 for v in s.decisions_by_reason_code.values())


def test_all_known_reason_codes_present_as_keys():
    s = summarize_screening_decisions(_decisions())
    assert set(s.decisions_by_reason_code) == REASON_CODES


def test_flatten_is_scalar_int_only():
    s = summarize_screening_decisions(_decisions())
    flat = flatten_screening_summary(s)
    assert all(isinstance(v, int) for v in flat.values())
    assert flat["n_decisions"] == 5
    assert flat["outcome__needs_review"] == 2
    assert flat["reason__parser_warning"] == 1
    # Stable key ordering: outcomes before reasons, following the declared order.
    keys = list(flat.keys())
    assert keys[0] == "n_decisions"
    assert keys.index("outcome__clean") < keys.index("reason__source_language_expected")


def test_notes_never_appear_in_summary_or_flatten():
    forbidden = "syn_secret_note_AAA_transcript"
    decisions = [
        CallhomeScreeningDecision(
            outcome="clean",
            reason_codes=["source_language_expected"],
            notes=forbidden,
        ),
        CallhomeScreeningDecision(
            outcome="excluded",
            reason_codes=["empty_or_nonlexical"],
            notes="another_syn_secret",
        ),
    ]
    s = summarize_screening_decisions(decisions)
    for text in _all_strings(s.to_dict()):
        assert forbidden not in text
        assert "syn_secret" not in text
    for text in _all_strings(flatten_screening_summary(s)):
        assert forbidden not in text
        assert "syn_secret" not in text
    # And no "notes" field name leaks into the aggregate output.
    assert "notes" not in flatten_screening_summary(s)


def test_invariant_rejects_unknown_outcome():
    bad = CallhomeScreeningDecision(outcome="clean", reason_codes=["source_language_expected"])
    bad.outcome = "maybe"  # mutate to bypass the construction guard
    with pytest.raises(ValueError, match="maybe"):
        summarize_screening_decisions([bad])


def test_invariant_rejects_unknown_reason_code():
    bad = CallhomeScreeningDecision(outcome="clean", reason_codes=["source_language_expected"])
    bad.reason_codes = ["not_a_real_reason"]
    with pytest.raises(ValueError, match="not_a_real_reason"):
        summarize_screening_decisions([bad])


def test_invariant_rejects_empty_reason_codes():
    bad = CallhomeScreeningDecision(outcome="clean", reason_codes=["source_language_expected"])
    bad.reason_codes = []
    with pytest.raises(ValueError):
        summarize_screening_decisions([bad])
