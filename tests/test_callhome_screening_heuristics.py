"""Tests for the conservative CALLHOME screening heuristics.

All CHAT content is SYNTHETIC (fake ``AAA`` codes, ``syn_*`` tokens). No real
CALLHOME files or transcript text are used. Heuristics may read utterance text
in memory, but decisions/outcomes must expose only safe codes — never text.
"""

from cslm.data.callhome_chat import parse_chat_lines
from cslm.data.callhome_screening_heuristics import (
    CallhomeScreeningSignals,
    build_screening_decisions_by_turn,
    build_screening_outcomes_by_turn,
    infer_screening_signals,
    screen_utterance_with_heuristics,
)


def _utt_from_main(main_text, *, source_file="synth_00.cha"):
    lines = ["@Begin", "@Languages:\teng", f"*AAA:\t{main_text}", "@End"]
    return parse_chat_lines(lines, source_file=source_file).utterances[0]


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


def test_signals_default_all_false():
    s = CallhomeScreeningSignals()
    assert s.has_parser_warning is False
    assert s.has_possible_foreign_material is False
    assert s.is_empty_or_nonlexical is False
    assert s.explicit_clean_override is False


def test_infer_lexical_utterance_has_no_blocking_signals():
    s = infer_screening_signals(_utt_from_main("syn_alpha syn_beta ."), language_label="eng")
    assert s.is_empty_or_nonlexical is False
    assert s.has_parser_warning is False
    # Never inferred:
    assert s.has_possible_foreign_material is False
    assert s.explicit_clean_override is False


def test_infer_empty_text_is_nonlexical():
    assert infer_screening_signals(_utt_from_main(""), language_label="eng").is_empty_or_nonlexical
    assert infer_screening_signals(
        _utt_from_main("   "), language_label="eng"
    ).is_empty_or_nonlexical


def test_infer_punctuation_only_is_nonlexical():
    for text in (".", "? !", ",  .", "+/."):
        s = infer_screening_signals(_utt_from_main(text), language_label="eng")
        assert s.is_empty_or_nonlexical is True, text


def test_infer_chat_residue_only_is_nonlexical():
    for text in ("xxx .", "0 .", "yyy", "www .", "&=laughs ."):
        s = infer_screening_signals(_utt_from_main(text), language_label="eng")
        assert s.is_empty_or_nonlexical is True, text


def test_infer_mixed_residue_and_word_is_lexical():
    # A real word alongside residue keeps the utterance lexical (not excluded).
    s = infer_screening_signals(_utt_from_main("xxx syn_word ."), language_label="eng")
    assert s.is_empty_or_nonlexical is False


def test_infer_parser_warning_detected():
    utt = _utt_from_main("syn_alpha .")
    utt.parser_warnings.append("synthetic warning")
    s = infer_screening_signals(utt, language_label="eng")
    assert s.has_parser_warning is True


def test_heuristics_lexical_no_override_is_needs_review():
    d = screen_utterance_with_heuristics(_utt_from_main("syn_alpha ."), language_label="eng")
    assert d.outcome == "needs_review"
    assert d.reason_codes == ["default_unscreened"]


def test_heuristics_clean_override_on_lexical_is_clean():
    d = screen_utterance_with_heuristics(
        _utt_from_main("syn_alpha ."), language_label="eng", explicit_clean_override=True
    )
    assert d.outcome == "clean"
    assert d.reason_codes == ["source_language_expected"]


def test_heuristics_clean_override_on_nonlexical_is_excluded():
    # Blocking structural signal beats the clean override.
    d = screen_utterance_with_heuristics(
        _utt_from_main("."), language_label="eng", explicit_clean_override=True
    )
    assert d.outcome == "excluded"
    assert "empty_or_nonlexical" in d.reason_codes


def test_heuristics_parser_warning_is_needs_review():
    utt = _utt_from_main("syn_alpha .")
    utt.parser_warnings.append("synthetic warning")
    d = screen_utterance_with_heuristics(
        utt, language_label="eng", explicit_clean_override=True
    )
    # Parser warning forces review even with a clean override.
    assert d.outcome == "needs_review"
    assert "parser_warning" in d.reason_codes


def test_heuristics_foreign_material_overlay_is_needs_review():
    d = screen_utterance_with_heuristics(
        _utt_from_main("syn_alpha ."),
        language_label="eng",
        explicit_clean_override=True,
        has_possible_foreign_material=True,
    )
    assert d.outcome == "needs_review"
    assert "possible_code_switching" in d.reason_codes


def test_heuristics_unsupported_language_is_not_clean():
    d = screen_utterance_with_heuristics(
        _utt_from_main("syn_alpha ."), language_label="fra", explicit_clean_override=True
    )
    assert d.outcome == "excluded"
    assert d.reason_codes == ["unsupported_language_label"]


def _transcript():
    lines = [
        "@Begin",
        "@Languages:\teng",
        "*AAA:\tsyn_alpha syn_beta .",  # turn 0: lexical
        "*AAA:\t.",  # turn 1: punctuation only
        "*AAA:\tsyn_gamma .",  # turn 2: lexical
        "@End",
    ]
    return parse_chat_lines(lines, source_file="synth_00.cha")


def test_build_decisions_by_turn_defaults_conservatively():
    decisions = build_screening_decisions_by_turn(_transcript(), language_label="eng")
    assert decisions[0].outcome == "needs_review"  # lexical, unscreened
    assert decisions[1].outcome == "excluded"  # punctuation only
    assert decisions[2].outcome == "needs_review"


def test_build_decisions_by_turn_applies_overrides():
    decisions = build_screening_decisions_by_turn(
        _transcript(),
        language_label="eng",
        overrides_by_turn={0: {"explicit_clean_override": True}},
    )
    assert decisions[0].outcome == "clean"
    # Override does not rescue the punctuation-only turn.
    assert decisions[1].outcome == "excluded"


def test_build_outcomes_by_turn_returns_strings():
    outcomes = build_screening_outcomes_by_turn(
        _transcript(),
        language_label="eng",
        overrides_by_turn={0: {"explicit_clean_override": True}},
    )
    assert outcomes == {0: "clean", 1: "excluded", 2: "needs_review"}
    assert all(isinstance(v, str) for v in outcomes.values())


def test_decisions_never_expose_transcript_text():
    # Utterances carry distinctive synthetic tokens; decisions must not.
    transcript = _transcript()
    decisions = build_screening_decisions_by_turn(transcript, language_label="eng")
    for decision in decisions.values():
        strings = _all_strings(decision.reason_codes)
        for token in ("syn_alpha", "syn_beta", "syn_gamma", "AAA"):
            assert all(token not in s for s in strings), token
        assert decision.notes is None
