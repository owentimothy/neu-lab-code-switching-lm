"""Tests for the CALLHOME/CHAT parser scaffold.

All `.cha` content here is SYNTHETIC — hand-written placeholder lines using
obviously fake speaker codes (AAA/BBB) and fake tokens (``syn_*``). No real
CALLHOME transcript text is used anywhere in this file.
"""

from cslm.data.callhome_chat import (
    CallhomeTier,
    parse_chat_file,
    parse_chat_lines,
)

# A well-formed synthetic CHAT transcript. Tabs separate markers from values,
# as in real CHAT, but every value is a made-up placeholder.
_SYNTH_LINES = [
    "@UTF8",
    "@Begin",
    "@Languages:\teng",
    "@Participants:\tAAA Adult, BBB Adult",
    "@ID:\teng|callhome|AAA|||||Adult|||",
    "@ID:\teng|callhome|BBB|||||Adult|||",
    "@Media:\tsynthmedia, audio",
    "*AAA:\tsyn_alpha syn_beta .",
    "%mor:\tsyn_mortag_one syn_mortag_two",
    "*BBB:\tsyn_gamma .",
    "%snd:\tsynthmedia_0_1000",
    "@End",
]


def _synth_transcript(source_file="synth_chat_01.cha"):
    return parse_chat_lines(_SYNTH_LINES, source_file=source_file)


def test_header_parsing():
    t = _synth_transcript()
    assert t.headers["@Languages"] == ["eng"]
    assert t.headers["@Media"] == ["synthmedia, audio"]
    # Repeated headers accumulate.
    assert len(t.headers["@ID"]) == 2
    # No-value headers are recorded with an empty value.
    assert t.headers["@Begin"] == [""]
    assert "@End" in t.headers


def test_conversation_id_from_source_filename():
    t = parse_chat_lines(_SYNTH_LINES, source_file="synth_chat_42.cha")
    assert t.conversation_id == "synth_chat_42"
    assert t.source_file == "synth_chat_42.cha"


def test_main_speaker_tier_parsing():
    t = _synth_transcript()
    assert len(t.utterances) == 2
    first = t.utterances[0]
    assert first.speaker_id == "AAA"
    assert first.raw_main_tier_text == "syn_alpha syn_beta ."


def test_dependent_tier_attaches_to_previous_speaker():
    t = _synth_transcript()
    assert t.utterances[0].dependent_tiers == [
        CallhomeTier(prefix="%mor", value="syn_mortag_one syn_mortag_two")
    ]
    # The %snd tier attaches to the second utterance and sets media_id.
    assert t.utterances[1].dependent_tiers[0].prefix == "%snd"
    assert t.utterances[1].media_id == "synthmedia_0_1000"


def test_turn_index_increments():
    t = _synth_transcript()
    assert [u.turn_index for u in t.utterances] == [0, 1]


def test_language_inferred_from_languages_header():
    t = _synth_transcript()
    assert all(u.language == "eng" for u in t.utterances)


def test_language_is_none_without_languages_header():
    lines = ["@Begin", "*AAA:\tsyn_alpha .", "@End"]
    t = parse_chat_lines(lines, source_file="synth_nolang.cha")
    assert t.utterances[0].language is None


def test_orphan_dependent_tier_warning():
    lines = ["@Begin", "%mor:\tsyn_orphan_tag", "*AAA:\tsyn_alpha .", "@End"]
    t = parse_chat_lines(lines, source_file="synth_orphan.cha")
    assert any("orphan dependent tier" in w for w in t.parser_warnings)
    # The orphan tier is not attached to the later utterance.
    assert t.utterances[0].dependent_tiers == []


def test_continuation_and_unknown_line_warnings():
    lines = [
        "@Begin",
        "*AAA:\tsyn_alpha",
        "\tsyn_continued_placeholder",  # continuation (leading whitespace)
        "garbage_structural_line",  # unknown (no @ * % / whitespace)
        "@End",
    ]
    t = parse_chat_lines(lines, source_file="synth_warn.cha")
    assert any("continuation line" in w for w in t.parser_warnings)
    assert any("unknown structural line" in w for w in t.parser_warnings)


def test_parse_chat_file_reads_synthetic_tmp_file(tmp_path):
    # Confirms parse_chat_file works without any real corpus dependency.
    p = tmp_path / "synth_file_chat.cha"
    p.write_text("\n".join(_SYNTH_LINES) + "\n", encoding="utf-8")
    t = parse_chat_file(p)
    assert t.conversation_id == "synth_file_chat"
    assert len(t.utterances) == 2


def test_synthetic_content_is_obviously_fake():
    # Guardrail: our fixtures use placeholder tokens, never real transcript text.
    t = _synth_transcript()
    assert all(
        tok.startswith("syn_")
        for u in t.utterances
        for tok in u.raw_main_tier_text.split()
        if tok not in {".", "?", "!"}
    )
