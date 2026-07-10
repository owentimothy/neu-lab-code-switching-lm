"""Tests for the local-only lexicon loader scaffold.

All lexicon files here are SYNTHETIC and created under a temporary directory
(fake ``syn_*`` entries). No real lexical resources, no downloads, and no
CALLHOME data are used. Nothing is written under data/resources/local_lexicons/.
"""

import pytest

from cslm.data.callhome_chat import parse_chat_lines
from cslm.data.callhome_lexicon_loader import (
    load_hunspell_dic_wordlist,
    load_plain_wordlist,
    load_wordlist,
)
from cslm.data.callhome_lexicon_validation import validate_utterance_against_lexicons
from cslm.utils.paths import project_root

_SCRIPT_PATH = project_root() / "scripts" / "summarize_callhome_projection_local.py"


def _write(tmp_path, name, body):
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


def _utt(main_text):
    lines = ["@Begin", "@Languages:\teng", f"*AAA:\t{main_text}", "@End"]
    return parse_chat_lines(lines, source_file="synth_00.cha").utterances[0]


def test_plain_wordlist_loads_one_entry_per_line(tmp_path):
    p = _write(tmp_path, "syn.txt", "syn_alpha\nsyn_beta\nsyn_gamma\n")
    assert load_plain_wordlist(p) == {"syn_alpha", "syn_beta", "syn_gamma"}


def test_plain_wordlist_ignores_blank_lines(tmp_path):
    p = _write(tmp_path, "syn.txt", "syn_alpha\n\n   \nsyn_beta\n")
    assert load_plain_wordlist(p) == {"syn_alpha", "syn_beta"}


def test_plain_wordlist_ignores_comment_lines(tmp_path):
    p = _write(tmp_path, "syn.txt", "# a synthetic comment\nsyn_alpha\n# another\nsyn_beta\n")
    assert load_plain_wordlist(p) == {"syn_alpha", "syn_beta"}


def test_hunspell_count_line_is_ignored(tmp_path):
    p = _write(tmp_path, "syn.dic", "3\nsyn_alpha\nsyn_beta\nsyn_gamma\n")
    assert load_hunspell_dic_wordlist(p) == {"syn_alpha", "syn_beta", "syn_gamma"}


def test_hunspell_affix_flags_are_stripped(tmp_path):
    p = _write(tmp_path, "syn.dic", "2\nsyn_alpha/AB\nsyn_beta/XYZ\n")
    assert load_hunspell_dic_wordlist(p) == {"syn_alpha", "syn_beta"}


def test_hunspell_loader_does_not_expand_affixes(tmp_path):
    # Only the base (before-slash) entry is returned; no expanded forms appear.
    p = _write(tmp_path, "syn.dic", "1\nsyn_alpha/AB\n")
    result = load_hunspell_dic_wordlist(p)
    assert result == {"syn_alpha"}
    assert all("/" not in e for e in result)


def test_hunspell_ignores_blank_and_comment_lines(tmp_path):
    p = _write(tmp_path, "syn.dic", "2\n\n# comment\nsyn_alpha/A\n   \nsyn_beta\n")
    assert load_hunspell_dic_wordlist(p) == {"syn_alpha", "syn_beta"}


def test_loader_returns_set_and_deduplicates(tmp_path):
    p = _write(tmp_path, "syn.txt", "syn_alpha\nsyn_alpha\nsyn_beta\nsyn_alpha\n")
    result = load_plain_wordlist(p)
    assert isinstance(result, set)
    assert result == {"syn_alpha", "syn_beta"}


def test_missing_file_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_plain_wordlist(tmp_path / "does_not_exist.txt")
    with pytest.raises(FileNotFoundError):
        load_hunspell_dic_wordlist(tmp_path / "missing.dic")


def test_load_wordlist_dispatch(tmp_path):
    plain = _write(tmp_path, "p.txt", "syn_alpha\n")
    dic = _write(tmp_path, "d.dic", "1\nsyn_alpha/AB\n")
    assert load_wordlist(plain) == {"syn_alpha"}
    assert load_wordlist(dic, hunspell_dic=True) == {"syn_alpha"}


def test_loaded_lexicon_validates_expected_language_only_row(tmp_path):
    eng = _write(tmp_path, "eng.txt", "syn_alpha\nsyn_beta\n")
    lex = {"eng": load_plain_wordlist(eng), "spa": set()}
    d = validate_utterance_against_lexicons(
        _utt("syn_alpha syn_beta ."), expected_language="eng", lexicons_by_language=lex
    )
    assert d.is_validated is True
    assert d.validation_method == "lexicon_exact_match"


def test_ambiguous_entries_from_two_files_block_validation(tmp_path):
    eng = _write(tmp_path, "eng.txt", "syn_alpha\nsyn_shared\n")
    spa = _write(tmp_path, "spa.txt", "syn_shared\nsyn_delta\n")
    lex = {"eng": load_plain_wordlist(eng), "spa": load_plain_wordlist(spa)}
    d = validate_utterance_against_lexicons(
        _utt("syn_shared ."), expected_language="eng", lexicons_by_language=lex
    )
    # syn_shared is in both loaded lexicons -> ambiguous -> not validated.
    assert d.is_validated is False


def test_real_summary_script_does_not_use_loader():
    source = _SCRIPT_PATH.read_text(encoding="utf-8")
    assert "callhome_lexicon_loader" not in source
    assert "load_wordlist" not in source
    assert "load_plain_wordlist" not in source
    assert "load_hunspell_dic_wordlist" not in source


def _local_lexicons_snapshot(local):
    """Relative path names under ``local`` (names only, never file contents)."""
    if not local.exists():
        return None
    return sorted(str(p.relative_to(local)) for p in local.rglob("*"))


def test_loading_does_not_touch_local_lexicons_path(tmp_path):
    # Loading a synthetic tmp file must not create or modify anything under the
    # ignored resource path (works whether or not real local files exist there).
    local = project_root() / "data" / "resources" / "local_lexicons"
    before = _local_lexicons_snapshot(local)

    p = _write(tmp_path, "syn.txt", "syn_alpha\n")
    load_plain_wordlist(p)

    after = _local_lexicons_snapshot(local)
    assert before == after
    if before is None:
        # If it did not exist before, loading must not have created it.
        assert not local.exists()
