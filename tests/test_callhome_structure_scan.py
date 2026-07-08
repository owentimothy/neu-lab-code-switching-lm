"""Tests for the local-only CALLHOME structure scanner.

All `.cha` content is SYNTHETIC (fake AAA/BBB codes, ``syn_*`` tokens). No real
CALLHOME files are read. The key guardrail: the scanner output must contain
structural facts only — no header values, tier values, speaker IDs, or text.
"""

from cslm.data.callhome_chat import parse_chat_lines
from cslm.data.callhome_structure_scan import (
    flatten_structure_summary,
    scan_callhome_transcripts,
    summarize_transcripts,
)

# Synthetic content that would be *forbidden* to appear in any scanner output.
_SYNTH_VALUE_TOKENS = ("syn_alpha", "syn_beta", "syn_gamma", "syn_mortag", "AAA", "BBB")

_SYNTH_LINES = [
    "@UTF8",
    "@Begin",
    "@Languages:\teng",
    "@Participants:\tAAA Adult, BBB Adult",
    "@Media:\tsynthmedia, audio",
    "*AAA:\tsyn_alpha syn_beta .",
    "%mor:\tsyn_mortag_one syn_mortag_two",
    "*BBB:\tsyn_gamma .",
    "%snd:\tsynthmedia_0_1000",
    "@End",
]


def _synth_transcripts(n=1):
    return [
        parse_chat_lines(_SYNTH_LINES, source_file=f"synth_{i:02d}.cha") for i in range(n)
    ]


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


def test_header_key_counts_include_keys_not_values():
    s = summarize_transcripts(_synth_transcripts(2), language_label="eng")
    assert s.header_key_counts["@Languages"] == 2
    assert s.header_key_counts["@Media"] == 2
    assert "@Begin" in s.header_key_counts
    # No header VALUE leaks into the counts' keys.
    assert all("syn_" not in k for k in s.header_key_counts)


def test_dependent_tier_prefix_counts_include_prefixes_not_values():
    s = summarize_transcripts(_synth_transcripts(1), language_label="eng")
    assert s.dependent_tier_prefix_counts.get("%mor") == 1
    assert s.dependent_tier_prefix_counts.get("%snd") == 1
    # Tier VALUES must not appear anywhere in the prefix map.
    assert all("syn_" not in k for k in s.dependent_tier_prefix_counts)


def test_utterance_and_media_counts():
    s = summarize_transcripts(_synth_transcripts(3), language_label="eng")
    assert s.n_utterances == 6  # 2 speaker turns * 3 transcripts
    assert s.n_files_with_media_header == 3
    assert s.n_files_with_dependent_tiers == 3
    assert s.n_utterances_with_media_id == 3  # one %snd per transcript


def test_parser_warnings_are_counted_only():
    lines = ["@Begin", "%mor:\tsyn_orphan", "*AAA:\tsyn_alpha .", "@End"]
    t = parse_chat_lines(lines, source_file="synth_orphan.cha")
    s = summarize_transcripts([t], language_label="eng")
    assert s.n_parser_warnings >= 1
    # The summary exposes only an integer count, never warning strings.
    assert isinstance(s.n_parser_warnings, int)
    assert not hasattr(s, "parser_warnings")


def test_flattened_output_has_no_forbidden_content():
    s = summarize_transcripts(_synth_transcripts(2), language_label="eng")
    flat = flatten_structure_summary(s)
    strings = _all_strings(flat)
    # No synthetic content tokens (would signal a value/text leak).
    for token in _SYNTH_VALUE_TOKENS:
        assert all(token not in text for text in strings), token
    # No structural-object field names that would carry content.
    forbidden_keys = {
        "raw_main_tier_text",
        "dependent_tiers",
        "utterances",
        "headers",
        "value",
        "speaker_id",
    }
    assert set(flat.keys()) & forbidden_keys == set()


def test_scan_reads_synthetic_tmp_files_only(tmp_path):
    # Exercises the path-based API without any real CALLHOME dependency.
    for i in range(2):
        (tmp_path / f"synth_{i}.cha").write_text(
            "\n".join(_SYNTH_LINES) + "\n", encoding="utf-8"
        )
    paths = sorted(tmp_path.glob("*.cha"))
    s = scan_callhome_transcripts(paths, language_label="eng")
    assert s.n_files == 2
    assert s.n_transcripts_parsed == 2
    assert s.n_utterances == 4


def test_scan_counts_unparseable_files_without_raising(tmp_path):
    good = tmp_path / "good.cha"
    good.write_text("\n".join(_SYNTH_LINES) + "\n", encoding="utf-8")
    bad = tmp_path / "bad.cha"
    bad.write_bytes(b"\xff\xfe not valid utf-8 \x80\x81")
    s = scan_callhome_transcripts(sorted(tmp_path.glob("*.cha")), language_label="eng")
    assert s.n_files == 2
    assert s.n_transcripts_parsed == 1  # the bad file is counted but skipped


def test_synthetic_fixture_is_obviously_fake():
    # The fixture tokens are placeholders, never real transcript text.
    assert all(line.count("\t") <= 1 for line in _SYNTH_LINES)
    assert any("syn_" in line for line in _SYNTH_LINES)
