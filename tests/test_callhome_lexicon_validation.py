"""Tests for the deterministic lexicon-validation scaffold.

All lexicons and CHAT content are SYNTHETIC (fake ``syn_*`` tokens). No real
lexical resources and no real CALLHOME files are used. Validation must be
conservative: positive only on full expected-language agreement, content-free
outputs, and never wired into the real-data script.
"""

import pytest

from cslm.data.callhome_chat import parse_chat_lines
from cslm.data.callhome_lexicon_validation import validate_utterance_against_lexicons
from cslm.data.callhome_source_validation_diagnostics import (
    summarize_source_validation_decisions,
)
from cslm.utils.paths import project_root

_SCRIPT_PATH = project_root() / "scripts" / "summarize_callhome_projection_local.py"

# Synthetic lexicons — fake tokens only, no real vocabulary.
_LEX = {
    "eng": {"syn_e1", "syn_e2", "syn_e3", "syn_both"},
    "spa": {"syn_s1", "syn_s2", "syn_both"},  # syn_both is deliberately ambiguous
}


def _utt(main_text):
    lines = ["@Begin", "@Languages:\teng", f"*AAA:\t{main_text}", "@End"]
    return parse_chat_lines(lines, source_file="synth_00.cha").utterances[0]


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


def test_all_expected_language_tokens_validate():
    d = validate_utterance_against_lexicons(
        _utt("syn_e1 syn_e2 ."), expected_language="eng", lexicons_by_language=_LEX
    )
    assert d.is_validated is True
    assert d.validation_method == "lexicon_exact_match"
    assert d.reason_codes == ["lexicon_expected_only"]
    assert d.expected_language == "eng"


def test_token_in_other_language_lexicon_is_not_validated():
    d = validate_utterance_against_lexicons(
        _utt("syn_e1 syn_s1 ."), expected_language="eng", lexicons_by_language=_LEX
    )
    assert d.is_validated is False
    assert d.validation_method == "not_validated"


def test_unknown_token_is_not_validated():
    d = validate_utterance_against_lexicons(
        _utt("syn_e1 syn_unknown ."), expected_language="eng", lexicons_by_language=_LEX
    )
    assert d.is_validated is False


def test_ambiguous_token_in_both_lexicons_is_not_validated():
    d = validate_utterance_against_lexicons(
        _utt("syn_e1 syn_both ."), expected_language="eng", lexicons_by_language=_LEX
    )
    assert d.is_validated is False


def test_punctuation_or_residue_only_is_not_validated():
    for text in (".", "xxx .", "&=laughs .", "0 ."):
        d = validate_utterance_against_lexicons(
            _utt(text), expected_language="eng", lexicons_by_language=_LEX
        )
        assert d.is_validated is False, text


def test_case_insensitive_matching():
    d = validate_utterance_against_lexicons(
        _utt("SYN_E1 Syn_E2 ."), expected_language="eng", lexicons_by_language=_LEX
    )
    assert d.is_validated is True


def test_spanish_expected_language_validates_against_spanish_lexicon():
    d = validate_utterance_against_lexicons(
        _utt("syn_s1 syn_s2 ."), expected_language="spa", lexicons_by_language=_LEX
    )
    assert d.is_validated is True
    assert d.expected_language == "spa"


def test_empty_expected_lexicon_cannot_validate():
    d = validate_utterance_against_lexicons(
        _utt("syn_e1 ."), expected_language="eng", lexicons_by_language={"eng": set()}
    )
    assert d.is_validated is False


def test_unsupported_expected_language_raises():
    with pytest.raises(ValueError):
        validate_utterance_against_lexicons(
            _utt("syn_e1 ."), expected_language="fra", lexicons_by_language=_LEX
        )


def test_decision_is_content_free():
    d = validate_utterance_against_lexicons(
        _utt("syn_e1 syn_e2 ."), expected_language="eng", lexicons_by_language=_LEX
    )
    # No transcript tokens leak into the decision's fields.
    strings = _all_strings([d.expected_language, d.validation_method, d.reason_codes])
    for token in ("syn_e1", "syn_e2", "AAA", "transcript"):
        assert all(token not in s for s in strings), token
    for attr in ("notes", "text", "tokens", "speaker_ref", "source_file_ref"):
        assert not hasattr(d, attr)


def test_diagnostics_count_lexicon_method_with_stable_keys():
    validated = validate_utterance_against_lexicons(
        _utt("syn_e1 ."), expected_language="eng", lexicons_by_language=_LEX
    )
    not_validated = validate_utterance_against_lexicons(
        _utt("syn_unknown ."), expected_language="eng", lexicons_by_language=_LEX
    )
    s = summarize_source_validation_decisions([validated, not_validated])
    assert s.decisions_by_validated_status == {"validated": 1, "not_validated": 1}
    # New method/reason keys present with stable zero-able keys.
    assert s.decisions_by_validation_method == {
        "explicit_override": 0,
        "lexicon_exact_match": 1,
        "not_validated": 1,
    }
    assert s.decisions_by_reason_code == {
        "explicit_source_validation": 0,
        "lexicon_expected_only": 1,
        "not_validated": 1,
    }


def test_diagnostics_reject_mutated_lexicon_decision():
    bad = validate_utterance_against_lexicons(
        _utt("syn_e1 ."), expected_language="eng", lexicons_by_language=_LEX
    )
    # Flip to inconsistent state; diagnostics must reject defensively.
    bad.is_validated = False
    with pytest.raises(ValueError):
        summarize_source_validation_decisions([bad])


def test_diagnostics_reject_mutated_lexicon_decision_with_extra_positive_reason():
    bad = validate_utterance_against_lexicons(
        _utt("syn_e1 ."), expected_language="eng", lexicons_by_language=_LEX
    )
    assert bad.is_validated is True and bad.validation_method == "lexicon_exact_match"
    bad.reason_codes = ["lexicon_expected_only", "explicit_source_validation"]
    with pytest.raises(ValueError):
        summarize_source_validation_decisions([bad])


def test_validator_not_imported_or_called_by_local_script():
    source = _SCRIPT_PATH.read_text(encoding="utf-8")
    assert "callhome_lexicon_validation" not in source
    assert "validate_utterance_against_lexicons" not in source
