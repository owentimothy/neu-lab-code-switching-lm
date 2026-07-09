"""Tests for the conservative CALLHOME screening scaffold.

All CHAT content is SYNTHETIC (fake ``AAA``/``BBB`` codes, ``syn_*`` tokens). No
real CALLHOME files or transcript text are used. Screening decides from explicit
safe signals only; these tests confirm the conservative precedence and that
``clean`` is never returned without an explicit clean signal.
"""

import pytest

from cslm.data.callhome_chat import parse_chat_lines
from cslm.data.callhome_screening import (
    REASON_CODES,
    CallhomeScreeningDecision,
    build_screening_by_turn,
    default_decision,
    screen_utterance,
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


def _utt(lines=None, source_file="synth_00.cha", index=0):
    lines = lines or _SYNTH_LINES
    return parse_chat_lines(lines, source_file=source_file).utterances[index]


def test_default_decision_is_conservative():
    d = default_decision()
    assert d.outcome == "needs_review"
    assert d.reason_codes == ["default_unscreened"]


def test_no_signals_defaults_to_needs_review():
    d = screen_utterance(_utt(), language_label="eng")
    assert d.outcome == "needs_review"
    assert d.reason_codes == ["default_unscreened"]


def test_explicit_clean_override_returns_clean():
    d = screen_utterance(_utt(), language_label="eng", explicit_clean_override=True)
    assert d.outcome == "clean"
    assert d.reason_codes == ["source_language_expected"]


def test_clean_override_is_ignored_when_review_signal_present():
    # Clean must never win over a review/blocking signal.
    d = screen_utterance(
        _utt(),
        language_label="eng",
        explicit_clean_override=True,
        has_possible_foreign_material=True,
    )
    assert d.outcome == "needs_review"
    assert "ambiguous_foreign_material" in d.reason_codes
    assert "possible_code_switching" in d.reason_codes


def test_clean_override_is_ignored_when_blocking_signal_present():
    d = screen_utterance(
        _utt(),
        language_label="eng",
        explicit_clean_override=True,
        is_empty_or_nonlexical=True,
    )
    assert d.outcome == "excluded"
    assert "empty_or_nonlexical" in d.reason_codes


def test_parser_warning_forces_needs_review():
    d = screen_utterance(_utt(), language_label="eng", has_parser_warning=True)
    assert d.outcome == "needs_review"
    assert d.reason_codes == ["parser_warning"]


def test_utterance_own_parser_warning_is_folded_in():
    # An orphan dependent tier makes the parser record a warning on the utterance.
    lines = ["@Begin", "%mor:\tsyn_orphan", "*AAA:\tsyn_alpha .", "@End"]
    transcript = parse_chat_lines(lines, source_file="synth_warn.cha")
    # The transcript-level warning is recorded; also test a per-utterance one.
    utt = transcript.utterances[0]
    utt.parser_warnings.append("synthetic warning")
    d = screen_utterance(utt, language_label="eng")
    assert d.outcome == "needs_review"
    assert "parser_warning" in d.reason_codes


def test_empty_or_nonlexical_is_excluded():
    d = screen_utterance(_utt(), language_label="eng", is_empty_or_nonlexical=True)
    assert d.outcome == "excluded"
    assert d.reason_codes[0] == "empty_or_nonlexical"


def test_unsupported_language_label_is_excluded_not_clean():
    d = screen_utterance(
        _utt(), language_label="fra", explicit_clean_override=True
    )
    assert d.outcome == "excluded"
    assert d.reason_codes == ["unsupported_language_label"]


def test_exclude_takes_precedence_over_review():
    d = screen_utterance(
        _utt(),
        language_label="eng",
        is_empty_or_nonlexical=True,
        has_possible_foreign_material=True,
        has_parser_warning=True,
    )
    assert d.outcome == "excluded"
    assert "empty_or_nonlexical" in d.reason_codes


def test_decision_validates_outcome_and_reasons():
    with pytest.raises(ValueError):
        CallhomeScreeningDecision(outcome="maybe", reason_codes=["default_unscreened"])
    with pytest.raises(ValueError):
        CallhomeScreeningDecision(outcome="clean", reason_codes=[])
    with pytest.raises(ValueError):
        CallhomeScreeningDecision(outcome="clean", reason_codes=["not_a_real_reason"])


def test_all_returned_reason_codes_are_known():
    # Sweep the signal space; every produced reason must be in the vocabulary.
    combos = [
        {},
        {"has_parser_warning": True},
        {"has_possible_foreign_material": True},
        {"is_empty_or_nonlexical": True},
        {"explicit_clean_override": True},
    ]
    for signals in combos:
        d = screen_utterance(_utt(), language_label="eng", **signals)
        assert set(d.reason_codes) <= REASON_CODES


def test_build_screening_by_turn_defaults_all_needs_review():
    transcript = parse_chat_lines(_SYNTH_LINES, source_file="synth_00.cha")
    outcomes = build_screening_by_turn(transcript, language_label="eng")
    assert outcomes == {0: "needs_review", 1: "needs_review"}


def test_build_screening_by_turn_applies_synthetic_signals():
    transcript = parse_chat_lines(_SYNTH_LINES, source_file="synth_00.cha")
    outcomes = build_screening_by_turn(
        transcript,
        language_label="eng",
        signals_by_turn={
            0: {"explicit_clean_override": True},
            1: {"is_empty_or_nonlexical": True},
        },
    )
    assert outcomes == {0: "clean", 1: "excluded"}


def test_build_screening_by_turn_unsupported_language_excludes_all():
    transcript = parse_chat_lines(_SYNTH_LINES, source_file="synth_00.cha")
    outcomes = build_screening_by_turn(transcript, language_label="fra")
    assert set(outcomes.values()) == {"excluded"}


def test_notes_field_is_optional_and_defaults_none():
    d = screen_utterance(_utt(), language_label="eng")
    assert d.notes is None
