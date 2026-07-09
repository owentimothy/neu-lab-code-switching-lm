"""Tests for the CALLHOME source-language validation scaffold.

All content is synthetic. No real CALLHOME files or transcript text are used.
The scaffold must keep ``clean`` gated behind explicit validation, must never
let structural cleanliness or source directory alone imply validation, and must
expose no transcript text.
"""

import pytest

from cslm.data.callhome_screening import CallhomeScreeningDecision
from cslm.data.callhome_source_validation import (
    VALIDATION_METHODS,
    VALIDATION_REASON_CODES,
    CallhomeSourceValidationDecision,
    combine_screening_and_validation,
    default_source_validation,
    explicit_source_validation,
    is_structurally_eligible_for_clean,
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


# Synthetic screening-decision fixtures (structurally shaped like the heuristics'
# real outputs, but built directly with fake reason codes only).
def _default_unscreened():
    return CallhomeScreeningDecision(outcome="needs_review", reason_codes=["default_unscreened"])


def _parser_warning():
    return CallhomeScreeningDecision(outcome="needs_review", reason_codes=["parser_warning"])


def _possible_cs():
    return CallhomeScreeningDecision(
        outcome="needs_review",
        reason_codes=["ambiguous_foreign_material", "possible_code_switching"],
    )


def _excluded_empty():
    return CallhomeScreeningDecision(outcome="excluded", reason_codes=["empty_or_nonlexical"])


def _excluded_unsupported():
    return CallhomeScreeningDecision(
        outcome="excluded", reason_codes=["unsupported_language_label"]
    )


def test_default_validation_is_not_validated():
    v = default_source_validation("eng")
    assert v.is_validated is False
    assert v.expected_language == "eng"
    assert v.validation_method == "not_validated"
    assert v.reason_codes == ["not_validated"]


def test_explicit_validation_is_validated():
    v = explicit_source_validation("spa")
    assert v.is_validated is True
    assert v.expected_language == "spa"
    assert v.validation_method == "explicit_override"
    assert v.reason_codes == ["explicit_source_validation"]


def test_default_validation_does_not_make_rows_clean():
    # Structurally clean but unvalidated -> stays needs_review.
    outcome = combine_screening_and_validation(
        _default_unscreened(), default_source_validation("eng")
    )
    assert outcome == "needs_review"


def test_explicit_validation_makes_structurally_clean_row_clean():
    outcome = combine_screening_and_validation(
        _default_unscreened(), explicit_source_validation("eng")
    )
    assert outcome == "clean"


def test_explicit_validation_cannot_rescue_parser_warning():
    outcome = combine_screening_and_validation(
        _parser_warning(), explicit_source_validation("eng")
    )
    assert outcome == "needs_review"


def test_explicit_validation_cannot_rescue_possible_code_switching():
    outcome = combine_screening_and_validation(
        _possible_cs(), explicit_source_validation("eng")
    )
    assert outcome == "needs_review"


def test_explicit_validation_cannot_rescue_empty_or_nonlexical():
    outcome = combine_screening_and_validation(
        _excluded_empty(), explicit_source_validation("eng")
    )
    assert outcome == "excluded"


def test_unsupported_language_cannot_become_clean():
    # Screening already excluded it; even a validated decision keeps it excluded.
    outcome = combine_screening_and_validation(
        _excluded_unsupported(), explicit_source_validation("eng")
    )
    assert outcome == "excluded"


def test_source_directory_alone_does_not_imply_validation():
    # A row "from eng/" with only the default validation is not validated.
    assert default_source_validation("eng").is_validated is False
    # Only explicit validation flips the bit.
    assert explicit_source_validation("eng").is_validated is True


def test_structural_eligibility_helper():
    assert is_structurally_eligible_for_clean(_default_unscreened()) is True
    assert is_structurally_eligible_for_clean(_parser_warning()) is False
    assert is_structurally_eligible_for_clean(_possible_cs()) is False
    assert is_structurally_eligible_for_clean(_excluded_empty()) is False


def test_expected_language_must_be_supported():
    with pytest.raises(ValueError):
        CallhomeSourceValidationDecision(
            is_validated=False,
            expected_language="fra",
            validation_method="not_validated",
            reason_codes=["not_validated"],
        )
    with pytest.raises(ValueError):
        default_source_validation("fra")
    with pytest.raises(ValueError):
        explicit_source_validation("fra")


def test_validation_method_and_reason_vocabularies_enforced():
    with pytest.raises(ValueError):
        CallhomeSourceValidationDecision(
            is_validated=True,
            expected_language="eng",
            validation_method="magic",
            reason_codes=["explicit_source_validation"],
        )
    with pytest.raises(ValueError):
        CallhomeSourceValidationDecision(
            is_validated=True,
            expected_language="eng",
            validation_method="explicit_override",
            reason_codes=["not_a_real_reason"],
        )
    with pytest.raises(ValueError):
        CallhomeSourceValidationDecision(
            is_validated=True,
            expected_language="eng",
            validation_method="explicit_override",
            reason_codes=[],
        )


def test_inconsistent_validated_true_combinations_raise():
    # is_validated=True must pair with explicit_override + explicit_source_validation.
    with pytest.raises(ValueError):
        CallhomeSourceValidationDecision(
            is_validated=True,
            expected_language="eng",
            validation_method="not_validated",
            reason_codes=["explicit_source_validation"],
        )
    with pytest.raises(ValueError):
        CallhomeSourceValidationDecision(
            is_validated=True,
            expected_language="eng",
            validation_method="explicit_override",
            reason_codes=["not_validated"],
        )


def test_inconsistent_validated_false_combinations_raise():
    # is_validated=False must pair with not_validated + not_validated reason.
    with pytest.raises(ValueError):
        CallhomeSourceValidationDecision(
            is_validated=False,
            expected_language="eng",
            validation_method="explicit_override",
            reason_codes=["not_validated"],
        )
    with pytest.raises(ValueError):
        CallhomeSourceValidationDecision(
            is_validated=False,
            expected_language="eng",
            validation_method="not_validated",
            reason_codes=["explicit_source_validation"],
        )


def test_validated_rejects_extra_or_mixed_positive_reasons():
    # lexicon method + an extra explicit reason must be rejected.
    with pytest.raises(ValueError):
        CallhomeSourceValidationDecision(
            is_validated=True,
            expected_language="eng",
            validation_method="lexicon_exact_match",
            reason_codes=["lexicon_expected_only", "explicit_source_validation"],
        )
    # explicit method + an extra lexicon reason must be rejected.
    with pytest.raises(ValueError):
        CallhomeSourceValidationDecision(
            is_validated=True,
            expected_language="eng",
            validation_method="explicit_override",
            reason_codes=["explicit_source_validation", "lexicon_expected_only"],
        )


def test_validated_rejects_duplicate_reason_codes():
    with pytest.raises(ValueError):
        CallhomeSourceValidationDecision(
            is_validated=True,
            expected_language="eng",
            validation_method="lexicon_exact_match",
            reason_codes=["lexicon_expected_only", "lexicon_expected_only"],
        )


def test_not_validated_rejects_duplicate_reason_codes():
    with pytest.raises(ValueError):
        CallhomeSourceValidationDecision(
            is_validated=False,
            expected_language="eng",
            validation_method="not_validated",
            reason_codes=["not_validated", "not_validated"],
        )


def test_lexicon_method_singleton_reason_is_accepted():
    d = CallhomeSourceValidationDecision(
        is_validated=True,
        expected_language="spa",
        validation_method="lexicon_exact_match",
        reason_codes=["lexicon_expected_only"],
    )
    assert d.is_validated is True


def test_vocabularies_are_the_expected_labels():
    assert VALIDATION_METHODS == {
        "explicit_override",
        "lexicon_exact_match",
        "not_validated",
    }
    assert VALIDATION_REASON_CODES == {
        "explicit_source_validation",
        "lexicon_expected_only",
        "not_validated",
    }


def test_no_transcript_text_in_decisions():
    # Even if a caller mislabels intent, the decision carries no free text and
    # no synthetic transcript tokens can appear in its content-free fields.
    v = explicit_source_validation("eng")
    strings = _all_strings([v.expected_language, v.validation_method, v.reason_codes])
    for token in ("syn_", "AAA", "BBB", "transcript"):
        assert all(token not in s for s in strings), token
    # The dataclass has no text/tokens/notes field.
    assert not hasattr(v, "notes")
    assert not hasattr(v, "text")
    assert not hasattr(v, "tokens")
