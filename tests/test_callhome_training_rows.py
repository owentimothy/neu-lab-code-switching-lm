"""Synthetic-only tests for narrow CALLHOME training-row construction."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

import cslm.data.callhome_training_rows as training_rows
from cslm.data.callhome_chat import read_chat_transcript
from cslm.data.callhome_training_rows import (
    ERROR_LANGUAGE_CONFLICT,
    ERROR_UNRESOLVED_CHAT_CONTROL,
    EXCLUSION_NO_LEXICAL_MATERIAL,
    CallhomePopulationRows,
    CallhomeTrainingRow,
    CallhomeTrainingRowsError,
    assign_conversation_splits,
    build_population_rows,
    clean_chat_surface,
    rows_from_transcript,
    write_atomic_build,
)


def _chat(language: str, main_tiers: list[str]) -> str:
    tiers = "".join(
        f"*AAA:\t{text}\n%mor:\tsyn_morphology_{index}\n"
        for index, text in enumerate(main_tiers)
    )
    return (
        "@UTF8\n"
        "@Begin\n"
        f"@Languages:\t{language}\n"
        "@Participants:\tAAA Adult\n"
        f"{tiers}"
        "@End\n"
    )


def _write_chat(tmp_path: Path, name: str, language: str, tiers: list[str]) -> Path:
    path = tmp_path / name
    path.write_text(_chat(language, tiers), encoding="utf-8")
    return path


def _row(
    *,
    source: str = "callhome_eng",
    conversation: str = "conv_a",
    turn: int = 0,
    text: str = "Synthetic text.",
) -> CallhomeTrainingRow:
    return CallhomeTrainingRow(
        source=source,
        conversation_ref=conversation,
        speaker_ref=f"spk_{conversation}",
        turn_index=turn,
        row_id=f"row_{source}_{conversation}_{turn}",
        split=None,
        text=text,
    )


def _population(
    source: str,
    rows: list[CallhomeTrainingRow],
) -> CallhomePopulationRows:
    return CallhomePopulationRows(
        source=source,
        files_read=1,
        utterances_seen=len(rows),
        rows=tuple(rows),
        exclusions={},
    )


def test_cleaner_handles_only_reviewed_controls_and_preserves_surface():
    raw = (
        "Hola Café can't co-op &-uh palabra [/ ]".replace("[/ ]", "[/]")
        + " repetida [//] corregida [<] [>] (..) xxx yyy www 0 &=laughs +/. ¡bien!"
    )
    assert clean_chat_surface(raw) == (
        "Hola Café can't co-op uh palabra repetida corregida ¡bien!"
    )


def test_cleaner_preserves_casing_accents_punctuation_and_repetition():
    text = "I I REALLY can't re-enter. ¿Sí?"
    assert clean_chat_surface(text) == text


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("before \x15media_100_200\x15 after", "before after"),
        ("before <scoped spoken words> after", "before scoped spoken words after"),
        ("spoken [= explanation] surface", "spoken surface"),
        ("spoken [=! paralinguistic] surface", "spoken surface"),
        ("produced [: replacement] surface", "produced surface"),
        ("uncertain [?] surface", "uncertain surface"),
        ("[- eng] spoken surface", "spoken surface"),
        ("spoken surface [+ metadata]", "spoken surface"),
        ("+, continuation survives", "continuation survives"),
        ("before &+fragment after", "before after"),
        ("before &~nonword after", "before after"),
        ("&{l=laughs spoken material", "spoken material"),
        ("spoken material &}l=laughs", "spoken material"),
    ],
)
def test_cleaner_handles_observed_real_population_controls(text, expected):
    assert clean_chat_surface(text) == expected


def test_cleaner_handles_multiple_observed_controls_together():
    text = (
        "Start \x15media_100_200\x15 <spoken words> [= note] +, "
        "&+fragment &~nonword &{l=laughs still spoken &}l=laughs end."
    )
    assert clean_chat_surface(text) == "Start spoken words still spoken end."


def test_cleaner_preserves_spoken_surface_around_repairs_and_false_starts():
    text = (
        "Ándale I I REALLY can't re-enter &-uh first [/] repaired [//] "
        "replacement false_start +/. final-word."
    )
    assert clean_chat_surface(text) == (
        "Ándale I I REALLY can't re-enter uh first repaired replacement "
        "false_start final-word."
    )


@pytest.mark.parametrize(
    "text",
    [
        ". ? !",
        "xxx yyy www 0 +/.",
        "&=laughs (...)",
    ],
)
def test_nonlexical_rows_return_none(text):
    assert clean_chat_surface(text) is None


@pytest.mark.parametrize(
    "text",
    [
        "word [unknown]",
        "word &unknown",
        "word +unknown",
        "word [=unknown]",
        "word [:unknown]",
        "word [!]",
        "word <unclosed",
        "word \x15unpaired",
        "word &{",
        "word &}",
        "word &{x=unknown",
    ],
)
def test_unknown_control_residue_fails_closed(text):
    with pytest.raises(CallhomeTrainingRowsError, match=ERROR_UNRESOLVED_CHAT_CONTROL):
        clean_chat_surface(text)


def test_strict_reader_is_sole_reader_and_tiers_do_not_enter_text(tmp_path, monkeypatch):
    path = _write_chat(tmp_path, "secret_filename.cha", "eng", ["Words here ."])
    calls: list[Path] = []
    real_reader = read_chat_transcript

    def recording_reader(read_path):
        calls.append(Path(read_path))
        return real_reader(read_path)

    monkeypatch.setattr(training_rows, "read_chat_transcript", recording_reader)
    population = build_population_rows([path], source="callhome_eng")
    assert calls == [path]
    assert len(population.rows) == 1
    text = population.rows[0].text
    assert text == "Words here ."
    assert "@Languages" not in text
    assert "*AAA" not in text
    assert "%mor" not in text


def test_language_source_conflict_stops(tmp_path):
    path = _write_chat(tmp_path, "synthetic.cha", "spa", ["palabras ."])
    transcript = read_chat_transcript(path)
    with pytest.raises(CallhomeTrainingRowsError, match=ERROR_LANGUAGE_CONFLICT):
        rows_from_transcript(transcript, source="callhome_eng")


@pytest.mark.parametrize(
    ("source", "language"),
    [
        ("callhome_eng", "eng, spa"),
        ("callhome_eng", "eng, spa, fra"),
        ("callhome_spa", "spa, eng"),
        ("callhome_spa", "spa, eng, fra"),
    ],
)
def test_expected_language_first_with_additional_metadata_is_accepted(
    tmp_path,
    source,
    language,
):
    path = _write_chat(tmp_path, "synthetic.cha", language, ["Words ."])
    population = build_population_rows([path], source=source)
    assert len(population.rows) == 1
    assert population.transcripts_with_additional_language_metadata == 1


def test_unexpected_language_first_stops(tmp_path):
    path = _write_chat(tmp_path, "synthetic.cha", "spa, eng", ["Words ."])
    transcript = read_chat_transcript(path)
    with pytest.raises(CallhomeTrainingRowsError, match=ERROR_LANGUAGE_CONFLICT):
        rows_from_transcript(transcript, source="callhome_eng")


@pytest.mark.parametrize(
    "language",
    [
        "",
        "eng spa",
        "eng,",
        "eng,,spa",
        "eng, eng",
        "english, spa",
    ],
)
def test_malformed_or_ambiguous_language_declaration_stops(tmp_path, language):
    path = _write_chat(tmp_path, "synthetic.cha", language, ["Words ."])
    transcript = read_chat_transcript(path)
    with pytest.raises(CallhomeTrainingRowsError, match=ERROR_LANGUAGE_CONFLICT):
        rows_from_transcript(transcript, source="callhome_eng")


def test_repeated_language_declaration_header_stops(tmp_path):
    path = _write_chat(tmp_path, "synthetic.cha", "eng, spa", ["Words ."])
    transcript = read_chat_transcript(path)
    transcript.headers["@Languages"].append("eng")
    with pytest.raises(CallhomeTrainingRowsError, match=ERROR_LANGUAGE_CONFLICT):
        rows_from_transcript(transcript, source="callhome_eng")


def test_utterance_language_conflict_stops(tmp_path):
    path = _write_chat(tmp_path, "synthetic.cha", "eng, spa", ["Words ."])
    transcript = read_chat_transcript(path)
    transcript.utterances[0].language = "spa"
    with pytest.raises(CallhomeTrainingRowsError, match=ERROR_LANGUAGE_CONFLICT):
        rows_from_transcript(transcript, source="callhome_eng")


def test_additional_language_metadata_count_is_deterministic(tmp_path):
    paths = [
        _write_chat(tmp_path, "exact.cha", "eng", ["Exact ."]),
        _write_chat(tmp_path, "one.cha", "eng, spa", ["One ."]),
        _write_chat(tmp_path, "multiple.cha", "eng, spa, fra", ["Multiple ."]),
    ]
    first = build_population_rows(paths, source="callhome_eng")
    second = build_population_rows(reversed(paths), source="callhome_eng")
    assert first == second
    assert first.transcripts_with_additional_language_metadata == 2


def test_nonlexical_exclusion_has_fixed_reason(tmp_path):
    path = _write_chat(tmp_path, "synthetic.cha", "eng", ["xxx .", "Words ."])
    population = build_population_rows([path], source="callhome_eng")
    assert len(population.rows) == 1
    assert population.exclusions == {EXCLUSION_NO_LEXICAL_MATERIAL: 1}


def test_serialized_rows_exclude_raw_identifiers(tmp_path):
    path = _write_chat(tmp_path, "secret_filename.cha", "eng", ["Words ."])
    population = build_population_rows([path], source="callhome_eng")
    serialized = json.dumps(population.rows[0].to_dict())
    assert "secret_filename" not in serialized
    assert "AAA" not in serialized
    assert population.rows[0].conversation_ref.startswith("conv_")
    assert population.rows[0].speaker_ref.startswith("spk_")


def test_population_source_cannot_cross(tmp_path):
    english = _write_chat(tmp_path, "english.cha", "eng", ["Words ."])
    spanish = _write_chat(tmp_path, "spanish.cha", "spa", ["Palabras ."])
    assert build_population_rows([english], source="callhome_eng").rows[0].source == (
        "callhome_eng"
    )
    assert build_population_rows([spanish], source="callhome_spa").rows[0].source == (
        "callhome_spa"
    )
    with pytest.raises(CallhomeTrainingRowsError, match=ERROR_LANGUAGE_CONFLICT):
        build_population_rows([spanish], source="callhome_eng")


def test_atomic_writer_rejects_rows_in_wrong_population(tmp_path):
    english = _population(
        "callhome_eng",
        [_row(source="callhome_spa", conversation="wrong_source")],
    )
    spanish = _population(
        "callhome_spa",
        [_row(source="callhome_spa", conversation="spa_a", text="Palabras .")],
    )
    with pytest.raises(CallhomeTrainingRowsError, match="unsupported CALLHOME source"):
        write_atomic_build(
            english,
            spanish,
            publish_dir=tmp_path / "published",
            seed=1729,
        )


def test_conversation_splits_are_stable_and_have_zero_leakage():
    rows = [
        _row(conversation=f"conv_{conversation}", turn=turn)
        for conversation in range(20)
        for turn in range(2)
    ]
    first = assign_conversation_splits(rows, seed=1729)
    second = assign_conversation_splits(rows, seed=1729)
    assert first == second
    splits_by_conversation: dict[str, set[str | None]] = {}
    for row in first:
        splits_by_conversation.setdefault(row.conversation_ref, set()).add(row.split)
    assert all(len(splits) == 1 for splits in splits_by_conversation.values())
    assert {row.split for row in first} == {"train", "validation", "test"}


def test_repeated_atomic_builds_are_byte_identical(tmp_path):
    english = replace(
        _population(
            "callhome_eng",
            [_row(conversation=f"eng_{index}") for index in range(20)],
        ),
        transcripts_with_additional_language_metadata=7,
    )
    spanish = _population(
        "callhome_spa",
        [
            _row(source="callhome_spa", conversation=f"spa_{index}", text="Palabras .")
            for index in range(20)
        ],
    )
    first = tmp_path / "first"
    second = tmp_path / "second"
    assert write_atomic_build(english, spanish, publish_dir=first, seed=1729) == (
        write_atomic_build(english, spanish, publish_dir=second, seed=1729)
    )
    assert sorted(path.name for path in first.iterdir()) == sorted(
        path.name for path in second.iterdir()
    )
    for first_path in first.iterdir():
        assert first_path.read_bytes() == (second / first_path.name).read_bytes()
    manifest = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
    assert (
        manifest["sources"]["callhome_eng"][
            "transcripts_with_additional_language_metadata"
        ]
        == 7
    )
    assert (
        manifest["sources"]["callhome_spa"][
            "transcripts_with_additional_language_metadata"
        ]
        == 0
    )


def test_failure_leaves_no_accepted_partial_output(tmp_path, monkeypatch):
    english = _population("callhome_eng", [_row()])
    spanish = _population(
        "callhome_spa",
        [_row(source="callhome_spa", conversation="spa_a", text="Palabras .")],
    )
    publish_dir = tmp_path / "published"

    def fail_write(self, data):
        raise OSError("synthetic write failure")

    monkeypatch.setattr(Path, "write_bytes", fail_write)
    with pytest.raises(OSError, match="synthetic write failure"):
        write_atomic_build(english, spanish, publish_dir=publish_dir, seed=1729)
    assert not publish_dir.exists()
    assert list(tmp_path.iterdir()) == []


def test_rows_bytes_change_only_with_row_content(tmp_path):
    english = _population("callhome_eng", [_row()])
    spanish_row = _row(source="callhome_spa", conversation="spa_a", text="Palabras .")
    spanish = _population("callhome_spa", [spanish_row])
    first = tmp_path / "first"
    second = tmp_path / "second"
    write_atomic_build(english, spanish, publish_dir=first, seed=1729)
    changed = _population("callhome_spa", [replace(spanish_row, text="Otra palabra .")])
    write_atomic_build(english, changed, publish_dir=second, seed=1729)
    assert (first / "spanish_rows.jsonl").read_bytes() != (
        second / "spanish_rows.jsonl"
    ).read_bytes()


def test_processed_callhome_path_is_gitignored():
    repository_root = Path(__file__).resolve().parents[1]
    ignore_lines = {
        line.strip()
        for line in (repository_root / ".gitignore").read_text(encoding="utf-8").splitlines()
    }
    assert "data/processed/callhome/" in ignore_lines
