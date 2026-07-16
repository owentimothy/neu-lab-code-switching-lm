"""Tests for the English SCOWL lexical-coverage diagnostic.

Everything here is SYNTHETIC: fake ``syn_*`` tokens, fake lexicons, and — for the
production evaluator — a synthetic temporary SCOWL bundle loaded through the real
public loader ``load_approved_english_scowl()`` (its ``_approved_bundle_dir`` is
monkeypatched, exactly as in ``tests/test_english_scowl_resource.py``). No test
reads the real ignored bundle, and no CALLHOME/Bangor corpus data is used.

Coverage is a diagnostic, never a verdict: these tests pin that it produces no
validation, no ``clean``, no condition, and no routing, and that neither results
nor aggregates can carry input token strings.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import FrozenInstanceError, fields
from pathlib import Path

import pytest

from cslm.data import english_scowl_coverage as coverage
from cslm.data import english_scowl_resource as resource
from cslm.data.callhome_chat import parse_chat_lines
from cslm.data.english_scowl_coverage import (
    ApprovedEnglishScowl,
    EnglishCoverageInputError,
    EnglishCoverageLexiconError,
    EnglishCoverageResult,
    EnglishScowlCoverageEvaluator,
    compute_english_coverage,
)
from cslm.data.english_scowl_resource import (
    ARTIFACT_FILENAME,
    NOTICE_FILENAME,
    PROVENANCE_FILENAME,
    RESOURCE_ID,
    load_approved_english_scowl,
)

# Synthetic SCOWL entries, strictly sorted in bytewise order (loader requires it).
_SYN_ENTRIES: tuple[str, ...] = ("syn_apple", "syn_banana", "syn_cherry")
_SYN_NOTICE = "synthetic notice text; never read\n"


# --------------------------------------------------------------------------- #
# Synthetic bundle fixture (mirrors tests/test_english_scowl_resource.py).
# --------------------------------------------------------------------------- #


def _artifact_bytes(entries) -> bytes:
    return "".join(f"{entry}\n" for entry in entries).encode("utf-8")


def _provenance_document(artifact_data: bytes) -> dict:
    return {
        "schema_version": 1,
        "resource_id": RESOURCE_ID,
        "artifact_filename": ARTIFACT_FILENAME,
        "preserved_notice_filename": NOTICE_FILENAME,
        "artifact_SHA256": hashlib.sha256(artifact_data).hexdigest(),
    }


def _build_bundle(root: Path, *, entries=_SYN_ENTRIES) -> Path:
    bundle = root / "syn_bundle"
    bundle.mkdir()
    data = _artifact_bytes(entries)
    (bundle / ARTIFACT_FILENAME).write_bytes(data)
    (bundle / NOTICE_FILENAME).write_text(_SYN_NOTICE, encoding="utf-8")
    (bundle / PROVENANCE_FILENAME).write_text(
        json.dumps(_provenance_document(data), sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return bundle


@pytest.fixture
def approved_scowl(tmp_path, monkeypatch) -> ApprovedEnglishScowl:
    """A genuine ApprovedEnglishScowl loaded from a synthetic temporary bundle."""
    bundle = _build_bundle(tmp_path)
    monkeypatch.setattr(resource, "_approved_bundle_dir", lambda: bundle)
    return load_approved_english_scowl()


def _utt(main_text: str):
    lines = ["@Begin", "@Languages:\teng", f"*AAA:\t{main_text}", "@End"]
    return parse_chat_lines(lines, source_file="synth_00.cha").utterances[0]


# --------------------------------------------------------------------------- #
# Pure core: outcomes.
# --------------------------------------------------------------------------- #


def test_all_covered():
    r = compute_english_coverage(["a", "b"], normalized_lexicon={"a", "b", "c"})
    assert r.outcome == "all_covered"
    assert (r.n_tokens, r.n_covered, r.n_uncovered) == (2, 2, 0)


def test_has_uncovered():
    r = compute_english_coverage(["a", "z"], normalized_lexicon={"a", "b"})
    assert r.outcome == "has_uncovered"
    assert (r.n_tokens, r.n_covered, r.n_uncovered) == (2, 1, 1)


def test_no_lexical_tokens():
    r = compute_english_coverage([], normalized_lexicon={"a"})
    assert r.outcome == "no_lexical_tokens"
    assert (r.n_tokens, r.n_covered, r.n_uncovered) == (0, 0, 0)


def test_core_compares_verbatim_without_hidden_normalization():
    # "Apple" (capital) must NOT match "apple": the core normalizes nothing.
    r = compute_english_coverage(["Apple"], normalized_lexicon={"apple"})
    assert r.outcome == "has_uncovered"
    assert r.n_covered == 0


# --------------------------------------------------------------------------- #
# Pure core: fails closed on token input.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("bad_tokens", ["abc", b"abc", bytearray(b"abc")])
def test_string_or_bytes_token_sequence_rejected(bad_tokens):
    with pytest.raises(EnglishCoverageInputError):
        compute_english_coverage(bad_tokens, normalized_lexicon={"a"})


def test_non_string_token_element_rejected():
    with pytest.raises(EnglishCoverageInputError):
        compute_english_coverage(["a", 7], normalized_lexicon={"a"})


# --------------------------------------------------------------------------- #
# Pure core: fails closed on lexicon (privacy-safe, value never echoed).
# --------------------------------------------------------------------------- #


def test_empty_lexicon_rejected():
    with pytest.raises(EnglishCoverageLexiconError):
        compute_english_coverage(["a"], normalized_lexicon=set())


def test_non_set_lexicon_rejected():
    with pytest.raises(EnglishCoverageLexiconError):
        compute_english_coverage(["a"], normalized_lexicon=["a"])


def test_non_string_lexicon_member_rejected_without_echo():
    with pytest.raises(EnglishCoverageLexiconError) as exc:
        compute_english_coverage(["a"], normalized_lexicon={"a", 7})
    assert "7" not in str(exc.value)


def test_empty_string_lexicon_member_rejected_without_echo():
    with pytest.raises(EnglishCoverageLexiconError) as exc:
        compute_english_coverage(["a"], normalized_lexicon={"a", ""})
    # Fixed message; nothing utterance/lexicon-derived appears.
    assert str(exc.value) == "normalized_lexicon must not contain empty strings"


# --------------------------------------------------------------------------- #
# Production evaluator: trust boundary.
# --------------------------------------------------------------------------- #


def test_evaluator_rejects_a_plain_set():
    with pytest.raises(EnglishCoverageLexiconError):
        EnglishScowlCoverageEvaluator({"syn_apple"})


def test_evaluator_rejects_a_frozenset():
    with pytest.raises(EnglishCoverageLexiconError):
        EnglishScowlCoverageEvaluator(frozenset({"syn_apple"}))


def test_evaluator_rejects_a_forged_substitute():
    class _Fake:
        entries = frozenset({"syn_apple", "syn_banana"})

    with pytest.raises(EnglishCoverageLexiconError):
        EnglishScowlCoverageEvaluator(_Fake())


# --------------------------------------------------------------------------- #
# Production evaluator: behavior over a synthetic bundle.
# --------------------------------------------------------------------------- #


def test_evaluator_all_covered(approved_scowl):
    ev = EnglishScowlCoverageEvaluator(approved_scowl)
    r = ev.evaluate_utterance(_utt("syn_apple syn_banana ."))
    assert r.outcome == "all_covered"
    assert (r.n_tokens, r.n_covered, r.n_uncovered) == (2, 2, 0)


def test_evaluator_has_uncovered(approved_scowl):
    ev = EnglishScowlCoverageEvaluator(approved_scowl)
    r = ev.evaluate_utterance(_utt("syn_apple syn_unknown ."))
    assert r.outcome == "has_uncovered"
    assert (r.n_tokens, r.n_covered, r.n_uncovered) == (2, 1, 1)


def test_evaluator_no_lexical_tokens(approved_scowl):
    ev = EnglishScowlCoverageEvaluator(approved_scowl)
    r = ev.evaluate_utterance(_utt("xxx ."))
    assert r.outcome == "no_lexical_tokens"
    assert r.n_tokens == 0


def test_evaluator_prepares_lexicon_exactly_once(approved_scowl, monkeypatch):
    # Both the (expensive) normalization and the whole-lexicon validation must run
    # exactly once — at construction — and never again per utterance.
    norm_calls = {"n": 0}
    validate_calls = {"n": 0}
    real_norm = coverage.normalize_lexicon
    real_validate = coverage._validate_prepared_lexicon

    def counting_norm(entries):
        norm_calls["n"] += 1
        return real_norm(entries)

    def counting_validate(lexicon):
        validate_calls["n"] += 1
        return real_validate(lexicon)

    monkeypatch.setattr(coverage, "normalize_lexicon", counting_norm)
    monkeypatch.setattr(coverage, "_validate_prepared_lexicon", counting_validate)

    ev = EnglishScowlCoverageEvaluator(approved_scowl)  # prepares once
    ev.evaluate_utterance(_utt("syn_apple ."))
    ev.evaluate_utterance(_utt("syn_banana syn_unknown ."))
    ev.evaluate_utterance(_utt("syn_cherry ."))

    assert norm_calls["n"] == 1
    assert validate_calls["n"] == 1


def test_evaluator_repr_hides_lexicon_and_entries(approved_scowl):
    ev = EnglishScowlCoverageEvaluator(approved_scowl)
    text = repr(ev)
    assert text == "EnglishScowlCoverageEvaluator()"
    for token in _SYN_ENTRIES:
        assert token not in text


def test_evaluator_lexicon_cannot_be_reassigned(approved_scowl):
    ev = EnglishScowlCoverageEvaluator(approved_scowl)
    with pytest.raises(FrozenInstanceError):
        ev._lexicon = frozenset({"syn_reassigned"})


# --------------------------------------------------------------------------- #
# Content-free: no token leakage; no validation/clean/condition/routing fields.
# --------------------------------------------------------------------------- #


def test_result_carries_no_input_token_strings(approved_scowl):
    ev = EnglishScowlCoverageEvaluator(approved_scowl)
    r = ev.evaluate_utterance(_utt("syn_apple syn_unknown ."))
    text = repr(r)
    for token in ("syn_apple", "syn_unknown"):
        assert token not in text
    assert r.outcome in coverage.COVERAGE_OUTCOMES
    assert isinstance(r.n_tokens, int)
    assert isinstance(r.n_covered, int)
    assert isinstance(r.n_uncovered, int)


def test_result_has_exactly_the_four_content_free_fields():
    names = {f.name for f in fields(EnglishCoverageResult)}
    assert names == {"outcome", "n_tokens", "n_covered", "n_uncovered"}


def test_result_has_no_validation_clean_condition_or_routing_fields():
    forbidden = (
        "is_validated",
        "validation_method",
        "reason_codes",
        "clean",
        "condition_candidates",
        "expected_language",
    )
    r = compute_english_coverage(["a"], normalized_lexicon={"a"})
    for name in forbidden:
        assert not hasattr(r, name)


def test_module_does_not_import_validation_or_routing_symbols():
    # The module docstring *mentions* these to say it avoids them; check that it
    # never actually imports them (they must not be module attributes).
    for name in (
        "CallhomeSourceValidationDecision",
        "combine_screening_and_validation",
        "default_source_validation",
        "CallhomeProjectedRow",
    ):
        assert not hasattr(coverage, name)


def test_result_is_frozen():
    r = compute_english_coverage(["a"], normalized_lexicon={"a"})
    with pytest.raises(FrozenInstanceError):
        r.n_tokens = 99


# --------------------------------------------------------------------------- #
# Result invariants: exact non-negative ints, and outcome<->counts consistency.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "kwargs",
    [
        {"outcome": "all_covered", "n_tokens": 2, "n_covered": 2, "n_uncovered": 0},
        {"outcome": "has_uncovered", "n_tokens": 2, "n_covered": 1, "n_uncovered": 1},
        {"outcome": "no_lexical_tokens", "n_tokens": 0, "n_covered": 0, "n_uncovered": 0},
    ],
)
def test_valid_results_construct(kwargs):
    r = EnglishCoverageResult(**kwargs)
    assert r.outcome == kwargs["outcome"]


@pytest.mark.parametrize(
    "bad",
    [
        # bool and float counts are rejected (must be exact ints).
        {"outcome": "all_covered", "n_tokens": True, "n_covered": True, "n_uncovered": 0},
        {"outcome": "all_covered", "n_tokens": 2.0, "n_covered": 2.0, "n_uncovered": 0.0},
        # negative count.
        {"outcome": "has_uncovered", "n_tokens": 1, "n_covered": -1, "n_uncovered": 2},
        # sum mismatch.
        {"outcome": "all_covered", "n_tokens": 3, "n_covered": 2, "n_uncovered": 0},
        # unknown outcome label.
        {"outcome": "syn_bad", "n_tokens": 1, "n_covered": 1, "n_uncovered": 0},
        # all_covered contradictions.
        {"outcome": "all_covered", "n_tokens": 0, "n_covered": 0, "n_uncovered": 0},
        {"outcome": "all_covered", "n_tokens": 2, "n_covered": 1, "n_uncovered": 1},
        # has_uncovered contradictions.
        {"outcome": "has_uncovered", "n_tokens": 2, "n_covered": 2, "n_uncovered": 0},
        {"outcome": "has_uncovered", "n_tokens": 0, "n_covered": 0, "n_uncovered": 0},
        # no_lexical_tokens contradiction.
        {"outcome": "no_lexical_tokens", "n_tokens": 1, "n_covered": 1, "n_uncovered": 0},
    ],
)
def test_contradictory_result_rejected(bad):
    with pytest.raises(ValueError):
        EnglishCoverageResult(**bad)
