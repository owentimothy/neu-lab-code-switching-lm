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


# --- Normalization / matching policy tests -----------------------------------
# (docs/callhome_lexicon_normalization_policy.md). Synthetic lexicons/tokens only.


def _validates(text, expected_language, lex):
    return validate_utterance_against_lexicons(
        _utt(text), expected_language=expected_language, lexicons_by_language=lex
    ).is_validated


def test_same_normalization_applied_to_tokens_and_lexicon_entries():
    # Lexicon entry carries case + surrounding punctuation/space; the token is a
    # plain lowercase word. Identical normalization on both sides makes them match.
    lex = {"eng": {"  Hello!  "}, "spa": set()}
    assert _validates("hello .", "eng", lex) is True


def test_case_folding_uppercase_token_matches_lowercase_entry():
    assert _validates("HELLO .", "eng", {"eng": {"hello"}, "spa": set()}) is True


def test_case_folding_lowercase_token_matches_uppercase_entry():
    assert _validates("hello .", "eng", {"eng": {"HELLO"}, "spa": set()}) is True


def test_nfc_normalization_token_decomposed_matches_precomposed_entry():
    # 'café' typed with a combining acute accent must match a precomposed entry.
    assert _validates("café .", "spa", {"spa": {"café"}, "eng": set()}) is True


def test_nfc_normalization_applied_to_lexicon_entries_too():
    # ...and the reverse: precomposed token vs decomposed lexicon entry.
    assert _validates("café .", "spa", {"spa": {"café"}, "eng": set()}) is True


def test_leading_trailing_punctuation_stripped():
    # Surrounding quotes/punctuation are trimmed; the core token still matches.
    assert _validates('"hello!" .', "eng", {"eng": {"hello"}, "spa": set()}) is True


def test_spanish_inverted_punctuation_normalizes():
    # '¿qué?' -> 'qué' (leading ¿ and trailing ? both stripped).
    assert _validates("¿qué? .", "spa", {"spa": {"qué"}, "eng": set()}) is True


def test_spanish_accents_preserved_si_without_accent_does_not_validate():
    # Expected lexicon has only accented 'sí'; unaccented 'si' must NOT validate.
    assert _validates("si .", "spa", {"spa": {"sí"}, "eng": set()}) is False


def test_spanish_accents_preserved_accented_form_validates():
    assert _validates("sí .", "spa", {"spa": {"sí"}, "eng": set()}) is True


def test_english_contraction_internal_apostrophe_preserved_validates():
    # Current policy KEEPS internal apostrophes, so an exact contraction entry
    # validates as a single token.
    assert _validates("don't .", "eng", {"eng": {"don't"}, "spa": set()}) is True


def test_english_contraction_not_split_conservative_block():
    # 'don't' is one token; it does not validate against split 'do'/'not'.
    assert _validates("don't .", "eng", {"eng": {"do", "not"}, "spa": set()}) is False


def test_possessive_kept_whole_validates_with_exact_entry():
    assert _validates("dog's .", "eng", {"eng": {"dog's"}, "spa": set()}) is True


def test_possessive_kept_whole_conservative_block_without_exact_entry():
    # 'dog's' is not split to 'dog'; conservative behavior blocks validation.
    assert _validates("dog's .", "eng", {"eng": {"dog"}, "spa": set()}) is False


def test_hyphen_kept_whole_validates_with_exact_entry():
    assert _validates("co-op .", "eng", {"eng": {"co-op"}, "spa": set()}) is True


def test_hyphen_kept_whole_conservative_block_without_exact_entry():
    # 'co-op' is not split to 'co'/'op'; conservative behavior blocks validation.
    assert _validates("co-op .", "eng", {"eng": {"co", "op"}, "spa": set()}) is False


def test_residue_markers_are_not_lexical_evidence_only_residue_blocks():
    # A row of only residue / non-lexical markers has no retained lexical tokens.
    assert _validates("xxx 0 &laugh [note] (.) .", "eng", _LEX) is False


def test_residue_ignored_but_valid_token_still_validates():
    # Residue is skipped; the one real expected-language token still validates.
    assert _validates("xxx syn_e1 0 &laugh .", "eng", _LEX) is True


def test_unknown_token_blocks_validation():
    assert _validates("syn_e1 syn_unknown .", "eng", _LEX) is False


def test_ambiguous_cross_lexicon_token_blocks_validation():
    assert _validates("syn_both .", "eng", _LEX) is False


def test_non_expected_language_token_blocks_validation():
    assert _validates("syn_e1 syn_s1 .", "eng", _LEX) is False


def test_empty_or_no_retained_token_row_does_not_validate():
    assert _validates("   ", "eng", _LEX) is False
    assert _validates(". ? !", "eng", _LEX) is False


def test_expected_language_only_tokens_validate():
    assert _validates("syn_e1 syn_e2 .", "eng", _LEX) is True


def test_lexicon_source_sets_not_modified_in_place():
    eng = {"HELLO", "  World!  "}
    spa = {"hola"}
    lex = {"eng": set(eng), "spa": set(spa)}
    validate_utterance_against_lexicons(
        _utt("hello ."), expected_language="eng", lexicons_by_language=lex
    )
    # The caller-provided sets are untouched (normalization builds new sets).
    assert lex["eng"] == eng
    assert lex["spa"] == spa


def test_positive_decision_uses_lexicon_method_and_reason():
    d = validate_utterance_against_lexicons(
        _utt("syn_e1 ."), expected_language="eng", lexicons_by_language=_LEX
    )
    assert d.validation_method == "lexicon_exact_match"
    assert d.reason_codes == ["lexicon_expected_only"]


def test_no_transcript_token_strings_in_returned_decision():
    # A distinctive synthetic token must not appear anywhere in the decision.
    d = validate_utterance_against_lexicons(
        _utt("zzsecrettoken ."),
        expected_language="eng",
        lexicons_by_language={"eng": {"zzsecrettoken"}, "spa": set()},
    )
    strings = _all_strings([d.expected_language, d.validation_method, d.reason_codes])
    assert all("zzsecrettoken" not in s for s in strings)
    for attr in ("notes", "text", "tokens", "raw_text"):
        assert not hasattr(d, attr)
