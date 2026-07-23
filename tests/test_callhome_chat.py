"""Tests for the CALLHOME/CHAT reader — permissive scaffold and strict reader.

All `.cha` content here is SYNTHETIC — hand-written placeholder lines using
obviously fake speaker codes (AAA/BBB) and fake tokens (``syn_*``), plus unique
``syn_sentinel_*`` strings for the privacy tests. No real CALLHOME transcript
text, speaker, or lexical entry is used anywhere in this file.
"""

from pathlib import Path

import pytest

from cslm.data import callhome_chat
from cslm.data.callhome_chat import (
    CallhomeTier,
    CallhomeTranscript,
    CallhomeUtterance,
    StrictChatReaderError,
    parse_chat_file,
    parse_chat_lines,
    read_chat_transcript,
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


# ---------------------------------------------------------------------------
# Permissive path (existing behavior — must remain unchanged)
# ---------------------------------------------------------------------------


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


def test_permissive_warning_counts_unchanged():
    # Locks the permissive counts: exactly one continuation + one unknown warning,
    # and the continuation text is dropped (owner text is unchanged, not merged).
    lines = [
        "@Begin",
        "*AAA:\tsyn_alpha",
        "\tsyn_dropped_continuation",  # continuation → warning, text dropped
        "garbage_structural_line",  # unknown → warning
        "@End",
    ]
    t = parse_chat_lines(lines, source_file="synth_counts.cha")
    continuation = [w for w in t.parser_warnings if "continuation line" in w]
    unknown = [w for w in t.parser_warnings if "unknown structural line" in w]
    assert len(continuation) == 1
    assert len(unknown) == 1
    # Continuation text is dropped, not merged, on the permissive path.
    assert t.utterances[0].raw_main_tier_text == "syn_alpha"


def test_permissive_blank_line_silently_skipped():
    lines = ["@Begin", "", "   ", "*AAA:\tsyn_alpha .", "@End"]
    t = parse_chat_lines(lines, source_file="synth_blank.cha")
    # A blank line and a space-only line (permissive strips) produce no warnings.
    assert t.parser_warnings == []
    assert t.utterances[0].raw_main_tier_text == "syn_alpha ."


# ---------------------------------------------------------------------------
# Strict reader — helpers
# ---------------------------------------------------------------------------

# Minimal well-formed strict transcript (must start with an exact @UTF8 header).
_STRICT_VALID = (
    "@UTF8\n"
    "@Begin\n"
    "@Languages:\teng\n"
    "@Participants:\tAAA Adult, BBB Adult\n"
    "*AAA:\tsyn_alpha syn_beta .\n"
    "%mor:\tsyn_mortag_one syn_mortag_two\n"
    "*BBB:\tsyn_gamma .\n"
    "%snd:\tsynthmedia_0_1000\n"
    "@End\n"
)


def _write_text(tmp_path, content, name="synth_strict.cha"):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def _assert_sanitized(exc, sentinel, capsys):
    """Assert a sentinel appears on no public surface and the chain is empty."""
    out, err = capsys.readouterr()
    assert sentinel not in str(exc)
    assert sentinel not in repr(exc)
    assert all(sentinel not in str(arg) for arg in exc.args)
    assert exc.__cause__ is None
    assert exc.__context__ is None
    assert sentinel not in out
    assert sentinel not in err


# ---------------------------------------------------------------------------
# Strict reader — encoding and @UTF8 header exactness
# ---------------------------------------------------------------------------


def test_strict_valid_transcript_reads(tmp_path):
    t = read_chat_transcript(_write_text(tmp_path, _STRICT_VALID))
    assert [u.speaker_id for u in t.utterances] == ["AAA", "BBB"]
    assert t.utterances[0].raw_main_tier_text == "syn_alpha syn_beta ."
    assert t.utterances[0].dependent_tiers[0].prefix == "%mor"
    assert t.utterances[1].media_id == "synthmedia_0_1000"
    assert all(u.language == "eng" for u in t.utterances)
    assert t.conversation_id == "synth_strict"
    assert t.parser_warnings == []
    assert all(u.parser_warnings == [] for u in t.utterances)


def test_strict_accepts_str_path(tmp_path):
    t = read_chat_transcript(str(_write_text(tmp_path, _STRICT_VALID)))
    assert len(t.utterances) == 2


def test_strict_accented_multibyte_survives(tmp_path):
    p = _write_text(tmp_path, "@UTF8\n*AAA:\tsyn_café synüber .\n")
    t = read_chat_transcript(p)
    assert t.utterances[0].raw_main_tier_text == "syn_café synüber ."


def test_strict_invalid_utf8_aborts_without_fallback(tmp_path):
    # 0xFF is never valid UTF-8; a latin-1 fallback would (wrongly) succeed.
    p = tmp_path / "synth_badenc.cha"
    p.write_bytes(b"@UTF8\n*AAA:\tsyn_\xff\xfe .\n")
    with pytest.raises(StrictChatReaderError) as ei:
        read_chat_transcript(p)
    assert str(ei.value) == "strict UTF-8 decode failed"
    assert ei.value.__cause__ is None
    assert ei.value.__context__ is None


def test_strict_bom_aborts(tmp_path):
    p = tmp_path / "synth_bom.cha"
    p.write_bytes(b"\xef\xbb\xbf@UTF8\n*AAA:\tsyn_alpha .\n")
    with pytest.raises(StrictChatReaderError) as ei:
        read_chat_transcript(p)
    assert str(ei.value) == "strict UTF-8 decode failed"


def test_strict_literal_replacement_char_aborts(tmp_path):
    # A literal U+FFFD is valid UTF-8 on disk but must still abort the strict read.
    p = _write_text(tmp_path, "@UTF8\n*AAA:\tsyn_� .\n")
    with pytest.raises(StrictChatReaderError) as ei:
        read_chat_transcript(p)
    assert str(ei.value) == "strict UTF-8 decode failed"


@pytest.mark.parametrize(
    "content",
    [
        "@UTF8:\n*AAA:\tsyn_alpha .\n",  # trailing colon
        "@UTF8 \n*AAA:\tsyn_alpha .\n",  # trailing space
        "@UTF8\t\n*AAA:\tsyn_alpha .\n",  # trailing tab
        "@UTF8\n\tsyn_more\n*AAA:\tsyn_alpha .\n",  # continuation-bearing header
        "@Begin\n@UTF8\n*AAA:\tsyn_alpha .\n",  # @UTF8 not first
        "@Begin\n*AAA:\tsyn_alpha .\n",  # missing @UTF8
        "",  # empty file
    ],
)
def test_strict_malformed_header_rejected(tmp_path, content):
    p = _write_text(tmp_path, content)
    with pytest.raises(StrictChatReaderError) as ei:
        read_chat_transcript(p)
    assert str(ei.value) == "missing or malformed @UTF8 header"


# ---------------------------------------------------------------------------
# Strict reader — tier structure
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "content",
    [
        "@UTF8\n*AAAnocolon\n",  # colonless main tier
        "@UTF8\n*:\tsyn_alpha\n",  # empty main-tier speaker marker
        "@UTF8\n*AAA:syn_alpha\n",  # main tier missing TAB after colon
        "@UTF8\n*AAA:\tsyn_alpha\n%mornocolon\n",  # colonless dependent tier
        "@UTF8\n*AAA:\tsyn_alpha\n%:\tsyn_dep\n",  # empty dependent marker
        "@UTF8\n*AAA:\tsyn_alpha\n%mor:syn_dep\n",  # dependent tier missing TAB
        "@UTF8\n%mor:\tsyn_dep\n",  # orphan dependent tier (before any main tier)
        "@UTF8\ngarbage_structural_line\n",  # unknown structural line
    ],
)
def test_strict_malformed_tier_rejected(tmp_path, content):
    p = _write_text(tmp_path, content)
    with pytest.raises(StrictChatReaderError) as ei:
        read_chat_transcript(p)
    assert str(ei.value) == "malformed CHAT tier"


# ---------------------------------------------------------------------------
# Strict reader — continuation boundaries
# ---------------------------------------------------------------------------


def test_strict_owner_ends_with_space_single_u0020(tmp_path):
    p = _write_text(tmp_path, "@UTF8\n*AAA:\tsyn_alpha \n\tsyn_more\n")
    t = read_chat_transcript(p)
    assert t.utterances[0].raw_main_tier_text == "syn_alpha syn_more"


def test_strict_owner_ends_with_tab_single_u0020(tmp_path):
    p = _write_text(tmp_path, "@UTF8\n*AAA:\tsyn_alpha\t\n\tsyn_more\n")
    t = read_chat_transcript(p)
    assert t.utterances[0].raw_main_tier_text == "syn_alpha syn_more"


def test_strict_valid_continuation_joins(tmp_path):
    p = _write_text(tmp_path, "@UTF8\n*AAA:\tsyn_alpha\n\tsyn_more\n")
    t = read_chat_transcript(p)
    assert t.utterances[0].raw_main_tier_text == "syn_alpha syn_more"


def test_strict_multiple_continuations_preserve_order(tmp_path):
    p = _write_text(tmp_path, "@UTF8\n*AAA:\tsyn_one\n\tsyn_two\n\tsyn_three\n")
    t = read_chat_transcript(p)
    assert t.utterances[0].raw_main_tier_text == "syn_one syn_two syn_three"


def test_strict_punctuation_preserved_across_join(tmp_path):
    p = _write_text(tmp_path, "@UTF8\n*AAA:\tsyn_alpha,\n\t.\n")
    t = read_chat_transcript(p)
    assert t.utterances[0].raw_main_tier_text == "syn_alpha, ."


def test_strict_interior_whitespace_not_normalized(tmp_path):
    # Interior double space inside a payload is preserved; only the boundary is
    # normalized to exactly one U+0020.
    p = _write_text(tmp_path, "@UTF8\n*AAA:\tsyn_a\n\tsyn_b  syn_c\n")
    t = read_chat_transcript(p)
    assert t.utterances[0].raw_main_tier_text == "syn_a syn_b  syn_c"


@pytest.mark.parametrize(
    "content",
    [
        "@UTF8\n*AAA:\tsyn_alpha\n\t syn_more\n",  # TAB + SPACE + text
        "@UTF8\n*AAA:\tsyn_alpha\n\t\tsyn_more\n",  # TAB + TAB + text
        "@UTF8\n*AAA:\tsyn_alpha\n\t\n",  # TAB only
        "@UTF8\n*AAA:\tsyn_alpha\n\t   \n",  # TAB + spaces only
        "@UTF8\n syn_more\n",  # SPACE-prefixed content
        "@UTF8\n   \n*AAA:\tsyn_alpha .\n",  # SPACE-only physical line (not blank)
        "@UTF8\n*AAA:\tsyn_alpha\n\n\tsyn_more\n",  # empty line orphans continuation
    ],
)
def test_strict_malformed_continuation_rejected(tmp_path, content):
    p = _write_text(tmp_path, content)
    with pytest.raises(StrictChatReaderError) as ei:
        read_chat_transcript(p)
    assert str(ei.value) == "CHAT continuation grammar violated"


# ---------------------------------------------------------------------------
# Strict reader — filesystem failures (sanitized)
# ---------------------------------------------------------------------------


def test_strict_missing_file_sanitized(tmp_path, capsys):
    sentinel = "syn_sentinel_missing_9x7"
    missing = tmp_path / f"{sentinel}.cha"  # never created
    with pytest.raises(StrictChatReaderError) as ei:
        read_chat_transcript(missing)
    assert str(ei.value) == "strict CHAT read failed"
    _assert_sanitized(ei.value, sentinel, capsys)


def test_strict_permission_error_sanitized(tmp_path, monkeypatch, capsys):
    sentinel = "syn_sentinel_perm_1a3"

    def boom(self):
        raise PermissionError(sentinel)

    monkeypatch.setattr(Path, "read_bytes", boom)
    with pytest.raises(StrictChatReaderError) as ei:
        read_chat_transcript(tmp_path / "synth_perm.cha")
    assert str(ei.value) == "strict CHAT read failed"
    _assert_sanitized(ei.value, sentinel, capsys)


def test_strict_generic_oserror_sanitized(tmp_path, monkeypatch, capsys):
    sentinel = "syn_sentinel_os_2b4"

    def boom(self):
        raise OSError(sentinel)

    monkeypatch.setattr(Path, "read_bytes", boom)
    with pytest.raises(StrictChatReaderError) as ei:
        read_chat_transcript(tmp_path / "synth_os.cha")
    assert str(ei.value) == "strict CHAT read failed"
    _assert_sanitized(ei.value, sentinel, capsys)


# ---------------------------------------------------------------------------
# Strict reader — privacy surfaces
# ---------------------------------------------------------------------------


def test_strict_path_and_filename_not_leaked(tmp_path, capsys):
    sentinel = "syn_sentinel_path_5k2"
    missing = tmp_path / f"{sentinel}.cha"
    with pytest.raises(StrictChatReaderError) as ei:
        read_chat_transcript(missing)
    _assert_sanitized(ei.value, sentinel, capsys)


def test_strict_transcript_text_and_marker_not_leaked(tmp_path, capsys):
    sentinel = "syn_sentinel_marker_3q8"
    # Colonless main tier whose marker embeds the sentinel → malformed tier abort.
    p = _write_text(tmp_path, f"@UTF8\n*{sentinel}nocolon\n")
    with pytest.raises(StrictChatReaderError) as ei:
        read_chat_transcript(p)
    assert str(ei.value) == "malformed CHAT tier"
    _assert_sanitized(ei.value, sentinel, capsys)


def test_strict_invalid_byte_payload_not_leaked(tmp_path, capsys):
    sentinel = "syn_sentinel_bytes_7t1"
    p = tmp_path / "synth_badbytes.cha"
    p.write_bytes(b"@UTF8\n*AAA:\t" + sentinel.encode("ascii") + b"\xff\xfe\n")
    with pytest.raises(StrictChatReaderError) as ei:
        read_chat_transcript(p)
    assert str(ei.value) == "strict UTF-8 decode failed"
    _assert_sanitized(ei.value, sentinel, capsys)


def test_strict_errors_have_no_cause_or_context(tmp_path):
    # A validation failure (raised outside any except block) and a decode failure
    # (raise-after-exit) both yield a chain-free StrictChatReaderError.
    p1 = _write_text(tmp_path, "@UTF8\n*:\tsyn_alpha\n")  # empty speaker marker
    with pytest.raises(StrictChatReaderError) as ei1:
        read_chat_transcript(p1)
    assert ei1.value.__cause__ is None
    assert ei1.value.__context__ is None

    p2 = tmp_path / "synth_decode.cha"
    p2.write_bytes(b"@UTF8\n\xff\n")  # invalid UTF-8
    with pytest.raises(StrictChatReaderError) as ei2:
        read_chat_transcript(p2)
    assert ei2.value.__cause__ is None
    assert ei2.value.__context__ is None


# ---------------------------------------------------------------------------
# Strict reader — control-flow exceptions propagate as the exact object
# ---------------------------------------------------------------------------


def test_strict_keyboardinterrupt_propagates_exact_object(tmp_path, monkeypatch):
    injected = KeyboardInterrupt()

    def boom(self):
        raise injected

    monkeypatch.setattr(Path, "read_bytes", boom)
    with pytest.raises(KeyboardInterrupt) as captured:
        read_chat_transcript(tmp_path / "synth_ctrl_ki.cha")
    assert captured.value is injected


def test_strict_systemexit_propagates_exact_object(tmp_path, monkeypatch):
    injected = SystemExit()

    def boom(self):
        raise injected

    monkeypatch.setattr(Path, "read_bytes", boom)
    with pytest.raises(SystemExit) as captured:
        read_chat_transcript(tmp_path / "synth_ctrl_se.cha")
    assert captured.value is injected


# ---------------------------------------------------------------------------
# Strict reader — forced post-dispatch warning rejection
# ---------------------------------------------------------------------------
#
# The malformed-input tests above all fail BEFORE shared tier dispatch, so they do
# not exercise the mandatory post-dispatch warning assertion. These two tests
# inject a dispatch result that already carries a warning (via a narrow in-test
# monkeypatch of the module-private `_dispatch_strict`, confined to this test
# file — no production configuration, registry, or third file) so the post-dispatch
# assertion itself is exercised. The input is a minimal valid `@UTF8` file that
# passes header, reconstruction, and tier validation, guaranteeing the failure is
# the post-dispatch check and not an earlier stage.


def test_strict_forced_transcript_warning_rejected(tmp_path, monkeypatch, capsys):
    sentinel = "synthetic_warning_sentinel_txn"

    def fake_dispatch(logical, *, source_file):
        t = CallhomeTranscript(conversation_id="synth", source_file=source_file)
        t.parser_warnings.append(sentinel)
        return t

    monkeypatch.setattr(callhome_chat, "_dispatch_strict", fake_dispatch)
    p = _write_text(tmp_path, "@UTF8\n", name="synth_forced_txn.cha")
    with pytest.raises(StrictChatReaderError) as ei:
        read_chat_transcript(p)
    assert str(ei.value) == "strict CHAT read failed"
    _assert_sanitized(ei.value, sentinel, capsys)


def test_strict_forced_utterance_warning_rejected(tmp_path, monkeypatch, capsys):
    sentinel = "synthetic_warning_sentinel_utt"

    def fake_dispatch(logical, *, source_file):
        t = CallhomeTranscript(conversation_id="synth", source_file=source_file)
        u = CallhomeUtterance(
            conversation_id="synth",
            source_file=source_file,
            speaker_id="AAA",
            turn_index=0,
            raw_main_tier_text="syn_alpha",
        )
        u.parser_warnings.append(sentinel)
        t.utterances.append(u)
        return t

    monkeypatch.setattr(callhome_chat, "_dispatch_strict", fake_dispatch)
    p = _write_text(tmp_path, "@UTF8\n", name="synth_forced_utt.cha")
    with pytest.raises(StrictChatReaderError) as ei:
        read_chat_transcript(p)
    assert str(ei.value) == "strict CHAT read failed"
    # transcript.parser_warnings was empty; the utterance warning must still abort.
    _assert_sanitized(ei.value, sentinel, capsys)


# ---------------------------------------------------------------------------
# Compatibility — same invented input diverges across the two paths
# ---------------------------------------------------------------------------


def test_permissive_drops_but_strict_reconstructs_same_continuation(tmp_path):
    body = ["*AAA:\tsyn_alpha", "\tsyn_more"]

    # Permissive path: continuation is dropped and a warning is recorded; the
    # owner utterance text is unchanged (legacy behavior).
    perm = parse_chat_lines(["@Begin", *body, "@End"], source_file="synth_div.cha")
    assert perm.utterances[0].raw_main_tier_text == "syn_alpha"
    assert any("continuation line" in w for w in perm.parser_warnings)

    # Strict path: the same content reconstructs with exactly one U+0020 boundary.
    p = _write_text(tmp_path, "@UTF8\n" + "\n".join(body) + "\n", name="synth_div.cha")
    strict = read_chat_transcript(p)
    assert strict.utterances[0].raw_main_tier_text == "syn_alpha syn_more"
    assert strict.parser_warnings == []
    assert strict.utterances[0].parser_warnings == []
