"""Tests for the aggregate-only CALLHOME source-validation diagnostics.

All decisions are synthetic. No real CALLHOME files or transcript text are used.
Summaries must stay aggregate-only (counts, with stable keys).
"""

import pytest

from cslm.data.callhome_source_validation import (
    default_source_validation,
    explicit_source_validation,
)
from cslm.data.callhome_source_validation_diagnostics import (
    VALIDATED_STATUS_ORDER,
    VALIDATION_METHOD_ORDER,
    VALIDATION_REASON_CODE_ORDER,
    flatten_source_validation_summary,
    summarize_source_validation_decisions,
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


def test_default_decisions_summarize_as_not_validated():
    decisions = [default_source_validation("eng"), default_source_validation("spa")]
    s = summarize_source_validation_decisions(decisions)
    assert s.n_decisions == 2
    assert s.decisions_by_validated_status == {"validated": 0, "not_validated": 2}
    assert s.decisions_by_validation_method == {"explicit_override": 0, "not_validated": 2}
    assert s.decisions_by_reason_code == {
        "explicit_source_validation": 0,
        "not_validated": 2,
    }


def test_explicit_decisions_summarize_correctly():
    decisions = [explicit_source_validation("eng"), explicit_source_validation("eng")]
    s = summarize_source_validation_decisions(decisions)
    assert s.decisions_by_validated_status == {"validated": 2, "not_validated": 0}
    assert s.decisions_by_validation_method == {"explicit_override": 2, "not_validated": 0}
    assert s.decisions_by_reason_code == {
        "explicit_source_validation": 2,
        "not_validated": 0,
    }


def test_mixed_default_and_explicit_decisions_summarize_correctly():
    decisions = [
        default_source_validation("eng"),
        explicit_source_validation("eng"),
        default_source_validation("spa"),
    ]
    s = summarize_source_validation_decisions(decisions)
    assert s.n_decisions == 3
    assert s.decisions_by_validated_status == {"validated": 1, "not_validated": 2}
    assert s.decisions_by_validation_method == {"explicit_override": 1, "not_validated": 2}
    assert s.decisions_by_reason_code == {
        "explicit_source_validation": 1,
        "not_validated": 2,
    }


def test_empty_input_is_all_zero_with_stable_keys():
    s = summarize_source_validation_decisions([])
    assert s.n_decisions == 0
    assert set(s.decisions_by_validated_status) == set(VALIDATED_STATUS_ORDER)
    assert set(s.decisions_by_validation_method) == set(VALIDATION_METHOD_ORDER)
    assert set(s.decisions_by_reason_code) == set(VALIDATION_REASON_CODE_ORDER)
    assert all(v == 0 for v in s.decisions_by_validated_status.values())


def test_flatten_is_scalar_int_only():
    decisions = [default_source_validation("eng"), explicit_source_validation("eng")]
    flat = flatten_source_validation_summary(
        summarize_source_validation_decisions(decisions)
    )
    assert all(isinstance(v, int) for v in flat.values())
    assert flat["n_decisions"] == 2
    assert flat["status__validated"] == 1
    assert flat["status__not_validated"] == 1
    assert flat["method__explicit_override"] == 1
    assert flat["reason__not_validated"] == 1


def test_malformed_decision_unknown_method_is_rejected():
    bad = default_source_validation("eng")
    bad.validation_method = "magic"  # mutate to bypass the construction guard
    with pytest.raises(ValueError, match="magic"):
        summarize_source_validation_decisions([bad])


def test_malformed_decision_unknown_reason_is_rejected():
    bad = default_source_validation("eng")
    bad.reason_codes = ["not_a_real_reason"]
    with pytest.raises(ValueError, match="not_a_real_reason"):
        summarize_source_validation_decisions([bad])


def test_malformed_decision_empty_reasons_is_rejected():
    bad = default_source_validation("eng")
    bad.reason_codes = []
    with pytest.raises(ValueError):
        summarize_source_validation_decisions([bad])


def test_mutated_default_flipped_to_validated_is_rejected():
    bad = default_source_validation("eng")
    bad.is_validated = True  # now inconsistent with method/reason
    with pytest.raises(ValueError):
        summarize_source_validation_decisions([bad])


def test_mutated_explicit_flipped_to_not_validated_is_rejected():
    bad = explicit_source_validation("eng")
    bad.is_validated = False
    with pytest.raises(ValueError):
        summarize_source_validation_decisions([bad])


def test_mutated_default_method_to_explicit_override_is_rejected():
    bad = default_source_validation("eng")
    bad.validation_method = "explicit_override"
    with pytest.raises(ValueError):
        summarize_source_validation_decisions([bad])


def test_mutated_explicit_method_to_not_validated_is_rejected():
    bad = explicit_source_validation("eng")
    bad.validation_method = "not_validated"
    with pytest.raises(ValueError):
        summarize_source_validation_decisions([bad])


def test_mutated_default_reason_to_explicit_source_validation_is_rejected():
    bad = default_source_validation("eng")
    bad.reason_codes = ["explicit_source_validation"]
    with pytest.raises(ValueError):
        summarize_source_validation_decisions([bad])


def test_mutated_explicit_reason_to_not_validated_is_rejected():
    bad = explicit_source_validation("eng")
    bad.reason_codes = ["not_validated"]
    with pytest.raises(ValueError):
        summarize_source_validation_decisions([bad])


def test_summary_has_no_free_text_fields():
    decisions = [default_source_validation("eng")]
    d = summarize_source_validation_decisions(decisions).to_dict()
    # Only aggregate count structures; no content field names.
    forbidden = {"notes", "expected_language", "text", "tokens", "raw_text"}
    assert set(d.keys()) & forbidden == set()
    for text in _all_strings(d):
        assert "syn_" not in text
