from pathlib import Path

import pytest

from cslm.data.bangor_cgwords import (
    BANGOR_TOKEN_LABELS,
    CGWORDS_COLUMNS,
    ParsedCgwords,
    derive_language_category,
    flatten_ingestion_summary,
    global_utterance_id,
    group_utterances,
    map_langid_to_token_label,
    parse_cgwords_file,
    summarize_ingestion,
)
from cslm.utils.paths import project_root

SAMPLE_DIR = project_root() / "data" / "raw" / "bangor" / "cgwords"
HERRING1 = SAMPLE_DIR / "herring1_cgwords.tsv"
HERRING2 = SAMPLE_DIR / "herring2_cgwords.tsv"


# (word_id, utterance_id, location, surface, langid, speaker) -> full TSV row.
def _row(word_id, utterance_id, location, surface, langid, speaker):
    fields = [""] * len(CGWORDS_COLUMNS)
    values = {
        "word_id": str(word_id),
        "utterance_id": str(utterance_id),
        "location": str(location),
        "surface": surface,
        "speaker": speaker,
        "langid": langid,
        "filename": "toyconv",
    }
    for i, col in enumerate(CGWORDS_COLUMNS):
        fields[i] = values.get(col, "")
    return "\t".join(fields)


def _write_fixture(tmp_path: Path) -> Path:
    rows = [
        "\t".join(CGWORDS_COLUMNS),  # header
        # utt 1: English monolingual
        _row(1, 1, 1, "well", "eng", "AAA"),
        _row(2, 1, 2, ".", "999", "AAA"),
        # utt 2: Spanish monolingual
        _row(3, 2, 1, "hola", "spa", "AAA"),
        _row(4, 2, 2, ".", "999", "AAA"),
        # utt 3: intra-sentential CS, deliberately out of location order
        _row(5, 3, 2, "casa", "spa", "BBB"),
        _row(6, 3, 1, "the", "eng", "BBB"),
        _row(7, 3, 3, ".", "999", "BBB"),
        # utt 4: bivalent only
        _row(8, 4, 1, "ok", "eng&spa", "BBB"),
        _row(9, 4, 2, ".", "999", "BBB"),
        # utt 5: punctuation only
        _row(10, 5, 1, ".", "999", "AAA"),
        # utt 6: mixed morpheme only
        _row(11, 6, 1, "tagueé", "eng+spa", "AAA"),
        # utt 7: metadata / noise
        _row(12, 7, 1, "xxx", "www", "BBB"),
        "",  # blank line
        "(14 rows)",  # footer
    ]
    path = tmp_path / "toyconv_cgwords.tsv"
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path


def test_map_langid_to_token_label():
    assert map_langid_to_token_label("eng", "well") == "eng"
    assert map_langid_to_token_label("spa", "hola") == "spa"
    assert map_langid_to_token_label("eng&spa", "Oprah") == "eng&spa"
    assert map_langid_to_token_label("999", ".") == "punct"
    assert map_langid_to_token_label("999", "?") == "punct"
    # 999 with a non-punctuation surface is not silently trusted.
    assert map_langid_to_token_label("999", "word") == "other"
    assert map_langid_to_token_label("www", "xxx") == "metadata"
    for mixed in ("eng+spa", "spa+eng", "eng&spa+eng"):
        assert map_langid_to_token_label(mixed, "x") == "mixed_morpheme"
    assert map_langid_to_token_label("", "x") == "other"
    assert map_langid_to_token_label("deu", "x") == "other"


def test_www_surface_is_metadata_regardless_of_langid():
    # The real export mislabels the ``www`` redaction marker as ``eng&spa``; a
    # ``www`` *surface* must still normalize to metadata, never bivalent/other.
    assert map_langid_to_token_label("eng&spa", "www") == "metadata"
    assert map_langid_to_token_label("eng", "WWW") == "metadata"
    assert map_langid_to_token_label("999", "www") == "metadata"
    # A normal bivalent word/name is unaffected by the fix.
    assert map_langid_to_token_label("eng&spa", "Oprah") == "eng&spa"


def test_www_surface_utterance_categories():
    def labels(pairs):
        return [map_langid_to_token_label(langid, surface) for surface, langid in pairs]

    # www + punctuation only -> metadata_or_noise.
    only_www = labels([("www", "eng&spa"), (".", "999")])
    assert only_www == ["metadata", "punct"]
    assert derive_language_category(only_www) == "metadata_or_noise"

    # www mixed with real linguistic material -> mixed_or_uncertain.
    mixed = labels([("hello", "eng"), ("www", "eng&spa"), (".", "999")])
    assert derive_language_category(mixed) == "mixed_or_uncertain"


def test_map_langid_labels_are_in_vocabulary():
    for langid in ("eng", "spa", "eng&spa", "999", "www", "eng+spa", "", "deu"):
        assert map_langid_to_token_label(langid, ".") in BANGOR_TOKEN_LABELS


def test_derive_language_category():
    assert derive_language_category(["eng", "punct"]) == "en_only"
    assert derive_language_category(["spa", "punct"]) == "es_only"
    assert derive_language_category(["eng", "spa", "punct"]) == "cs_within_utterance"
    assert derive_language_category(["eng&spa", "punct"]) == "neutral_or_bivalent"
    assert derive_language_category(["punct"]) == "punctuation_or_empty"
    assert derive_language_category([]) == "punctuation_or_empty"
    assert derive_language_category(["mixed_morpheme"]) == "mixed_or_uncertain"
    assert derive_language_category(["metadata"]) == "metadata_or_noise"
    assert derive_language_category(["metadata", "punct"]) == "metadata_or_noise"
    # Contested material never overrides a clean monolingual decision, and never
    # forces a code-switching decision on its own.
    assert derive_language_category(["eng", "mixed_morpheme"]) == "en_only"
    assert derive_language_category(["spa", "mixed_morpheme"]) == "es_only"
    assert derive_language_category(["metadata", "eng"]) == "mixed_or_uncertain"


def test_global_utterance_id():
    assert global_utterance_id("herring1", 1) == "herring1_000001"
    assert global_utterance_id("herring2", 884) == "herring2_000884"


def test_parse_skips_header_footer_and_blank(tmp_path):
    parsed = parse_cgwords_file(_write_fixture(tmp_path))
    assert parsed.filename == "toyconv"
    assert parsed.n_skipped_footer == 1
    assert parsed.n_skipped_blank == 1
    assert len(parsed.words) == 12
    surfaces = {w.surface for w in parsed.words}
    assert "(14 rows)" not in surfaces
    assert "word_id" not in surfaces
    # Source columns are preserved verbatim.
    first = parsed.words[0]
    assert (first.surface, first.langid, first.speaker) == ("well", "eng", "AAA")


def test_group_sorts_by_location_and_mints_ids(tmp_path):
    parsed = parse_cgwords_file(_write_fixture(tmp_path))
    utterances = group_utterances(parsed.words)
    assert [u.utterance_id for u in utterances] == [
        f"toyconv_{i:06d}" for i in range(1, 8)
    ]
    # utt 3 was written out of order; tokens must come back sorted by location.
    cs = utterances[2]
    assert cs.locations == [1, 2, 3]
    assert cs.surfaces == ["the", "casa", "."]
    assert cs.speaker_id == "BBB"


def test_group_derives_categories_and_review_flag(tmp_path):
    parsed = parse_cgwords_file(_write_fixture(tmp_path))
    utterances = group_utterances(parsed.words)
    categories = [u.language_category for u in utterances]
    assert categories == [
        "en_only",
        "es_only",
        "cs_within_utterance",
        "neutral_or_bivalent",
        "punctuation_or_empty",
        "mixed_or_uncertain",
        "metadata_or_noise",
    ]
    flagged = [u.source_utterance_id for u in utterances if u.needs_review_mixed_morpheme]
    assert flagged == [6]


def test_utterance_to_dict_roundtrip(tmp_path):
    parsed = parse_cgwords_file(_write_fixture(tmp_path))
    utt = group_utterances(parsed.words)[2]
    d = utt.to_dict()
    assert d["utterance_id"] == "toyconv_000003"
    assert d["text"] == "the casa ."
    assert d["token_labels"] == ["eng", "spa", "punct"]
    assert d["language_category"] == "cs_within_utterance"
    assert d["n_words"] == 3


def test_summarize_and_flatten(tmp_path):
    parsed = parse_cgwords_file(_write_fixture(tmp_path))
    utterances = group_utterances(parsed.words)
    summary = summarize_ingestion([(parsed, utterances)])
    assert summary["n_files"] == 1
    assert summary["n_word_rows"] == 12
    assert summary["n_utterances"] == 7
    assert summary["n_skipped_footer_lines"] == 1
    assert summary["speakers"] == ["AAA", "BBB"]
    assert summary["source_langid_counts"]["eng"] == 2
    assert summary["source_langid_counts"]["eng+spa"] == 1
    assert summary["n_needs_review_mixed_morpheme"] == 1

    flat = flatten_ingestion_summary(summary)
    assert flat["n_word_rows"] == 12
    assert flat["langid_eng+spa"] == 1
    assert flat["category_cs_within_utterance"] == 1


# --- Smoke tests over the real two-file sample -----------------------------

_REAL_FILES = pytest.mark.skipif(
    not (HERRING1.exists() and HERRING2.exists()),
    reason="Bangor CG-words sample files not present",
)


@_REAL_FILES
@pytest.mark.parametrize(
    "path, filename, n_words, n_utts, footer_skips, langid_spot",
    [
        (
            HERRING1,
            "herring1",
            7590,
            1072,
            1,
            {"eng": 6037, "spa": 291, "999": 1072, "eng&spa": 187, "eng&spa+eng": 3},
        ),
        (
            HERRING2,
            "herring2",
            6371,
            884,
            1,
            {"spa": 5235, "eng": 113, "999": 884, "eng&spa": 138, "eng+spa": 1},
        ),
    ],
)
def test_real_sample_file(path, filename, n_words, n_utts, footer_skips, langid_spot):
    parsed = parse_cgwords_file(path)
    assert parsed.filename == filename
    assert parsed.n_skipped_footer == footer_skips
    assert len(parsed.words) == n_words

    from collections import Counter

    counts = Counter(w.langid for w in parsed.words)
    for langid, expected in langid_spot.items():
        assert counts[langid] == expected, langid

    # No footer/junk leaked into the surfaces.
    assert not any(w.surface.endswith("rows)") for w in parsed.words)

    utterances = group_utterances(parsed.words)
    assert len(utterances) == n_utts
    # Global ids are unique and every derived label is in the vocabulary.
    assert len({u.utterance_id for u in utterances}) == len(utterances)
    for utt in utterances:
        assert set(utt.token_labels) <= BANGOR_TOKEN_LABELS
        assert utt.language_category
        # CG-words utterances do not mix speakers.
        assert len({w.speaker for w in utt.words}) == 1


@_REAL_FILES
def test_www_surface_is_metadata_on_real_sample():
    # herring1 utterance 431 is a bare ``www`` redaction (langid mislabeled
    # ``eng&spa``). It must land in metadata_or_noise, not neutral_or_bivalent.
    parsed = parse_cgwords_file(HERRING1)
    utterances = {u.utterance_id: u for u in group_utterances(parsed.words)}
    utt = utterances["herring1_000431"]
    assert [s.lower() for s in utt.surfaces][:1] == ["www"]
    assert utt.token_labels[0] == "metadata"
    assert utt.language_category == "metadata_or_noise"


@_REAL_FILES
def test_summarize_over_both_sample_files():
    results = []
    for path in (HERRING1, HERRING2):
        parsed = parse_cgwords_file(path)
        results.append((parsed, group_utterances(parsed.words)))
    summary = summarize_ingestion(results)
    assert summary["n_files"] == 2
    assert summary["conversation_ids"] == ["herring1", "herring2"]
    assert summary["n_word_rows"] == 7590 + 6371
    assert summary["n_utterances"] == 1072 + 884
    assert summary["n_skipped_footer_lines"] == 2
    assert summary["speakers"] == ["CHL", "LAU", "MIG", "OSE", "TOM"]


def test_parsedcgwords_defaults():
    empty = ParsedCgwords(filename="x")
    assert empty.words == []
    assert empty.n_skipped_footer == 0
