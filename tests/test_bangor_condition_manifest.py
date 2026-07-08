import json
import subprocess
import sys

import pytest

from cslm.data.bangor_cgwords import BangorUtterance, BangorWord
from cslm.data.bangor_project import project_utterances
from cslm.data.condition_manifest import (
    build_condition_manifest,
    flatten_condition_manifest,
)
from cslm.utils.paths import project_root

FORBIDDEN_KEYS = frozenset(
    {
        "text",
        "raw_text",
        "clean_text",
        "tokens",
        "surfaces",
        "token_language_labels",
        "source_token_language_labels",
        "langids",
    }
)

SAMPLE_DIR = project_root() / "data" / "raw" / "bangor" / "cgwords"
HERRING1 = SAMPLE_DIR / "herring1_cgwords.tsv"
HERRING2 = SAMPLE_DIR / "herring2_cgwords.tsv"


def _bw(location, surface, langid, *, speaker="AAA", filename="conv", utt=1):
    return BangorWord(
        word_id=location, utterance_id=utt, location=location, surface=surface,
        auto="", fix="", eng="", com="", speaker=speaker, langid=langid,
        filename=filename, clause="", clauseno="",
    )


def _utt(pairs, *, speaker="AAA", filename="conv", utt=1):
    words = [
        _bw(i + 1, s, lang, speaker=speaker, filename=filename, utt=utt)
        for i, (s, lang) in enumerate(pairs)
    ]
    return BangorUtterance(
        conversation_id=filename,
        source_utterance_id=utt,
        utterance_id=f"{filename}_{utt:06d}",
        speaker_id=speaker,
        words=words,
    )


def _sample_rows():
    utts = [
        _utt([("the", "eng"), (".", "999")], utt=1),                       # en_only
        _utt([("SPWORD", "spa"), (".", "999")], utt=2),                    # es_only
        _utt([("the", "eng"), ("SPWORD", "spa"), (".", "999")], utt=3),  # cs
        # en_only frame + mixed-morpheme token
        _utt([("NAME_STEM_s", "eng&spa+eng"), ("the", "eng"), (".", "999")], utt=4),
        _utt([("www", "eng&spa"), (".", "999")], utt=5),  # metadata
        _utt([(".", "999")], utt=6),  # punctuation_or_empty
        _utt([("um", "eng"), (".", "999")], utt=7),  # neutral (um neutralized)
        _utt([("MIXEDWORD", "eng+spa"), (".", "999")], utt=8),  # mixed_or_uncertain
    ]
    n_source = sum(len(u.words) for u in utts)
    return project_utterances(utts), n_source


def _manifest():
    rows, n_source = _sample_rows()
    return build_condition_manifest(rows, n_files=1, n_source_word_rows=n_source)


def _all_keys(obj):
    keys = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(k)
            keys |= _all_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            keys |= _all_keys(v)
    return keys


def test_manifest_has_no_text_or_tokens_fields():
    m = _manifest()
    assert _all_keys(m) & FORBIDDEN_KEYS == set()
    assert set(flatten_condition_manifest(m).keys()) & FORBIDDEN_KEYS == set()


def test_final_source_policy_is_documented_in_manifest():
    m = _manifest()
    assert m["final_source_by_condition"] == {
        "EnglishMono": "dedicated_english_monolingual_corpus",
        "SpanishMono": "dedicated_spanish_monolingual_corpus",
        "MonoCont": "dedicated_english_and_spanish_monolingual_corpora",
        "CsCont": "bangor_bilingual_interaction",
    }
    assert m["bangor_final_source_role"] == "CsCont"
    assert m["writes_training_datasets"] is False


def test_all_policy_invariants_hold():
    m = _manifest()
    assert m["checks"] == {
        "monocont_excludes_cs_within_utterance": True,
        "monocont_excludes_mixed_morpheme_review": True,
        "mixed_morpheme_rows_cscont_only": True,
        "cscont_includes_en_es_cs_rows": True,
        "excluded_categories_have_no_conditions": True,
        "neutral_bivalent_excluded_by_default": True,
    }


def test_row_level_candidate_counts():
    m = _manifest()
    c = m["row_level_condition_candidate_counts"]
    # en_only non-mixed (u1) -> EnglishMono; es_only (u2) -> SpanishMono.
    assert c["EnglishMono"] == 1
    assert c["SpanishMono"] == 1
    # MonoCont: u1 + u2 (u4 en_only is mixed -> excluded).
    assert c["MonoCont"] == 2
    # CsCont: u1, u2, u3 (cs), u4 (mixed en_only). u8 mixed_or_uncertain -> none.
    assert c["CsCont"] == 4


def test_cscont_contribution_breakdown():
    m = _manifest()
    contrib = m["bangor_cscont_contribution"]
    assert contrib["n_rows"] == 4
    assert contrib["by_language_category"]["en_only"] == 2  # u1 + u4
    assert contrib["by_language_category"]["es_only"] == 1
    assert contrib["by_language_category"]["cs_within_utterance"] == 1
    assert contrib["n_needs_review_mixed_morpheme_rows"] == 1  # u4


def test_eligible_but_not_final_source_gap():
    m = _manifest()
    gap = m["bangor_rows_eligible_but_not_final_source"]
    # u1 en_only is EnglishMono-eligible but Bangor is not the final mono source.
    assert gap["n_en_only_rows_eligible_englishmono"] == 1
    assert gap["n_es_only_rows_eligible_spanishmono"] == 1


def test_sampling_is_naturalistic_with_no_targets():
    m = _manifest()
    assert m["sampling"]["strategy"] == "naturalistic"
    assert m["sampling"]["targets"] is None


def test_realized_proportions_present_and_bounded():
    m = _manifest()
    of_all = m["realized_proportions"]["of_all_rows"]
    assert abs(sum(of_all.values()) - 100.0) < 1e-6
    # CsCont-row proportions only cover CsCont-eligible categories.
    of_cs = m["realized_proportions"]["of_cscont_rows"]
    assert of_cs["metadata_or_noise"] == 0.0
    assert of_cs["neutral_or_bivalent"] == 0.0


# --- Script-level tests over the real two-file sample ----------------------

_REAL_FILES = pytest.mark.skipif(
    not (HERRING1.exists() and HERRING2.exists()),
    reason="Bangor CG-words sample files not present",
)


def _run_script(root):
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "build_bangor_condition_manifest.py")],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@_REAL_FILES
def test_script_writes_manifest_and_processes_only_two_files():
    root = project_root()
    _run_script(root)
    json_path = root / "outputs" / "corpus_summaries" / "bangor_condition_manifest.json"
    csv_path = root / "outputs" / "corpus_summaries" / "bangor_condition_manifest.csv"
    assert json_path.exists()
    assert csv_path.exists()

    m = json.loads(json_path.read_text(encoding="utf-8"))
    assert m["n_files"] == 2
    assert m["conversation_ids"] == ["herring1", "herring2"]
    assert _all_keys(m) & FORBIDDEN_KEYS == set()
    assert all(m["checks"].values())
    assert m["writes_training_datasets"] is False
    # Bangor's whole contribution is CsCont; mono conditions are sourced elsewhere.
    assert m["bangor_final_source_role"] == "CsCont"
    assert m["bangor_cscont_contribution"]["n_rows"] == m[
        "row_level_condition_candidate_counts"
    ]["CsCont"]
