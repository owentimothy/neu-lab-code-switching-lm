"""Aggregate condition manifest over projected Bangor sample rows.

Reports, without any transcript-bearing content, how projected
:class:`UtteranceRow` rows map onto the four model conditions. It distinguishes
two layers that must not be conflated:

* **Row-level eligibility** -- the ``condition_candidates`` the projection
  stamped on each row (what a row is *structurally compatible* with).
* **Final experimental sourcing** -- which corpus actually feeds each condition.
  Per policy (``docs/condition_dataset_policy.md``), EnglishMono / SpanishMono /
  MonoCont are sourced from *dedicated monolingual corpora*; **Bangor
  contributes only to CsCont** (its en_only / es_only / cs_within_utterance /
  CsCont-only mixed-morpheme rows), because even Bangor's monolingual-looking
  utterances come from a bilingual interaction context.

This module emits aggregate counts / proportions / booleans only. It does **not**
write final training datasets or any per-utterance text/tokens.
"""

from __future__ import annotations

from collections import Counter

from cslm.data.schema import UtteranceRow

ORDERED_CONDITIONS: tuple[str, ...] = ("EnglishMono", "SpanishMono", "MonoCont", "CsCont")

ORDERED_CATEGORIES: tuple[str, ...] = (
    "en_only",
    "es_only",
    "cs_within_utterance",
    "neutral_or_bivalent",
    "punctuation_or_empty",
    "mixed_or_uncertain",
    "metadata_or_noise",
)

# Final experimental source per condition (policy decision). Bangor is NOT a
# source for the monolingual / no-CS conditions.
FINAL_SOURCE_BY_CONDITION: dict[str, str] = {
    "EnglishMono": "dedicated_english_monolingual_corpus",
    "SpanishMono": "dedicated_spanish_monolingual_corpus",
    "MonoCont": "dedicated_english_and_spanish_monolingual_corpora",
    "CsCont": "bangor_bilingual_interaction",
}

BANGOR_FINAL_SOURCE_ROLE = "CsCont"

_CS_ELIGIBLE_CATEGORIES = ("en_only", "es_only", "cs_within_utterance")
_HARD_EXCLUDED_CATEGORIES = (
    "metadata_or_noise",
    "punctuation_or_empty",
    "mixed_or_uncertain",
)


def _pct(numerator: int, denominator: int) -> float:
    return round(100.0 * numerator / denominator, 4) if denominator else 0.0


def _ordered_conversation_ids(rows: list[UtteranceRow]) -> list[str]:
    seen: list[str] = []
    for row in rows:
        if row.conversation_id not in seen:
            seen.append(row.conversation_id)
    return seen


def build_condition_manifest(
    rows: list[UtteranceRow],
    *,
    n_files: int,
    n_source_word_rows: int,
) -> dict:
    """Build the aggregate, non-transcript condition manifest dict."""
    n_rows = len(rows)
    conversation_ids = _ordered_conversation_ids(rows)

    category_counts = Counter(r.language_category for r in rows)
    counts_by_language_category = {c: category_counts.get(c, 0) for c in ORDERED_CATEGORIES}

    # Row-level eligibility: how many rows are candidates for each condition.
    candidate_counts: Counter[str] = Counter()
    for row in rows:
        candidate_counts.update(row.condition_candidates)
    row_level_condition_candidate_counts = {
        c: candidate_counts.get(c, 0) for c in ORDERED_CONDITIONS
    }

    # Final-source view: the rows Bangor would actually contribute (CsCont only).
    cscont_rows = [r for r in rows if "CsCont" in r.condition_candidates]
    cscont_category_counts = Counter(r.language_category for r in cscont_rows)
    bangor_cscont_contribution = {
        "n_rows": len(cscont_rows),
        "by_language_category": {
            c: cscont_category_counts.get(c, 0) for c in ORDERED_CATEGORIES
        },
        "n_needs_review_mixed_morpheme_rows": sum(
            1 for r in cscont_rows if r.needs_review_mixed_morpheme
        ),
    }

    # Rows eligible for the mono conditions at the row level but NOT used as the
    # final source (Bangor -> CsCont only). Makes the eligibility/sourcing gap
    # explicit.
    bangor_rows_eligible_but_not_final_source = {
        "n_en_only_rows_eligible_englishmono": sum(
            1
            for r in rows
            if r.language_category == "en_only" and "EnglishMono" in r.condition_candidates
        ),
        "n_es_only_rows_eligible_spanishmono": sum(
            1
            for r in rows
            if r.language_category == "es_only" and "SpanishMono" in r.condition_candidates
        ),
        "note": (
            "Eligible at the row level but NOT used as final EnglishMono / "
            "SpanishMono / MonoCont source; Bangor contributes only to CsCont."
        ),
    }

    realized_proportions = {
        "of_all_rows": {
            c: _pct(counts_by_language_category[c], n_rows) for c in ORDERED_CATEGORIES
        },
        "of_cscont_rows": {
            c: _pct(cscont_category_counts.get(c, 0), len(cscont_rows))
            for c in ORDERED_CATEGORIES
        },
    }

    checks = {
        "monocont_excludes_cs_within_utterance": all(
            "MonoCont" not in r.condition_candidates
            for r in rows
            if r.language_category == "cs_within_utterance"
        ),
        "monocont_excludes_mixed_morpheme_review": all(
            "MonoCont" not in r.condition_candidates
            for r in rows
            if r.needs_review_mixed_morpheme
        ),
        "mixed_morpheme_rows_cscont_only": all(
            set(r.condition_candidates) <= {"CsCont"}
            for r in rows
            if r.needs_review_mixed_morpheme
        ),
        "cscont_includes_en_es_cs_rows": all(
            "CsCont" in r.condition_candidates
            for r in rows
            if r.language_category in _CS_ELIGIBLE_CATEGORIES
        ),
        "excluded_categories_have_no_conditions": all(
            not r.condition_candidates
            for r in rows
            if r.language_category in _HARD_EXCLUDED_CATEGORIES
        ),
        "neutral_bivalent_excluded_by_default": all(
            not r.condition_candidates
            for r in rows
            if r.language_category == "neutral_or_bivalent"
        ),
    }

    return {
        "n_files": n_files,
        "conversation_ids": conversation_ids,
        "n_source_word_rows": n_source_word_rows,
        "n_projected_utterance_rows": n_rows,
        "counts_by_language_category": counts_by_language_category,
        "row_level_condition_candidate_counts": row_level_condition_candidate_counts,
        "final_source_by_condition": dict(FINAL_SOURCE_BY_CONDITION),
        "bangor_final_source_role": BANGOR_FINAL_SOURCE_ROLE,
        "bangor_cscont_contribution": bangor_cscont_contribution,
        "bangor_rows_eligible_but_not_final_source": bangor_rows_eligible_but_not_final_source,
        "realized_proportions": realized_proportions,
        "sampling": {
            "strategy": "naturalistic",
            "targets": None,
            "balancing": "deferred",
            "note": (
                "Realized proportions only; balancing/oversampling is a "
                "future policy decision."
            ),
        },
        "checks": checks,
        "writes_training_datasets": False,
        "note": (
            "Aggregate manifest only. Reports row-level eligibility and the "
            "recommended Bangor CsCont-only source role; does not write final "
            "training datasets or any transcript-bearing rows."
        ),
    }


def flatten_condition_manifest(manifest: dict) -> dict:
    """Flatten the manifest into a single scalar row for CSV output."""
    flat: dict[str, object] = {
        "n_files": manifest["n_files"],
        "conversation_ids": ";".join(manifest["conversation_ids"]),
        "n_source_word_rows": manifest["n_source_word_rows"],
        "n_projected_utterance_rows": manifest["n_projected_utterance_rows"],
        "bangor_final_source_role": manifest["bangor_final_source_role"],
        "bangor_cscont_n_rows": manifest["bangor_cscont_contribution"]["n_rows"],
        "bangor_cscont_n_mixed_review_rows": manifest["bangor_cscont_contribution"][
            "n_needs_review_mixed_morpheme_rows"
        ],
        "sampling_strategy": manifest["sampling"]["strategy"],
        "writes_training_datasets": manifest["writes_training_datasets"],
    }
    for key, value in manifest["counts_by_language_category"].items():
        flat[f"category__{key}"] = value
    for key, value in manifest["row_level_condition_candidate_counts"].items():
        flat[f"candidate__{key}"] = value
    for key, value in manifest["final_source_by_condition"].items():
        flat[f"final_source__{key}"] = value
    cscont_by_category = manifest["bangor_cscont_contribution"]["by_language_category"]
    for key, value in cscont_by_category.items():
        flat[f"cscont_category__{key}"] = value
    for key, value in manifest["checks"].items():
        flat[f"check__{key}"] = value
    return flat
