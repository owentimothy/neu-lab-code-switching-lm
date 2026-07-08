"""Aggregate, non-transcript diagnostics over projected Bangor sample rows.

Given a list of projected :class:`UtteranceRow` objects (from
``bangor_project.project_utterances``), build a safe aggregate summary: counts,
token totals, ordinary token-level switch counts, and a few invariant checks.
It deliberately emits **no** per-utterance text, tokens, or switch-point lists,
so the resulting JSON/CSV are safe to commit.

Token totals and ordinary switch counts are delegated to
``diagnostics.build_corpus_summary`` so this stays consistent with the rest of
the pipeline rather than re-deriving them.

Out of scope (follow-up PR): full switch-site localization. That work must
compute three *separate* families and never sum them into one number:
1. ordinary token-level eng<->spa transitions (the counts produced here),
2. bivalent ``eng&spa`` bridge boundaries,
3. ``mixed_morpheme`` internal / re-entry switch sites.
"""

from __future__ import annotations

from cslm.data.classify import switch_transitions_from_labels
from cslm.data.diagnostics import build_corpus_summary
from cslm.data.schema import UtteranceRow

SWITCH_SITE_LOCALIZATION_TODO = (
    "Full switch-site localization is a follow-up PR. It must compute three "
    "separate families and never sum them into one number: "
    "(1) ordinary token-level eng<->spa transitions, "
    "(2) bivalent eng&spa bridge boundaries, "
    "(3) mixed_morpheme internal/re-entry switch sites."
)


def _ordered_conversation_ids(rows: list[UtteranceRow]) -> list[str]:
    seen: list[str] = []
    for row in rows:
        if row.conversation_id not in seen:
            seen.append(row.conversation_id)
    return seen


def _count_neutralized_disfluency_tokens(rows: list[UtteranceRow]) -> int:
    """Projected label ``neutral`` where the source langid was ``eng``/``spa``.

    Bangor never emits ``neutral`` from the source, so a ``neutral`` projected
    label over an ``eng``/``spa`` source langid is exactly a neutralized
    disfluency.
    """
    total = 0
    for row in rows:
        source_labels = row.source_token_language_labels or []
        for label, source in zip(row.token_language_labels, source_labels):
            if label == "neutral" and source in ("eng", "spa"):
                total += 1
    return total


def build_projected_sample_summary(
    rows: list[UtteranceRow],
    *,
    n_files: int,
    n_source_word_rows: int,
) -> dict:
    """Build the aggregate, non-transcript projected-sample summary dict."""
    conversation_ids = _ordered_conversation_ids(rows)
    cs = build_corpus_summary(
        rows,
        corpus_name="bangor_projected_sample",
        data_sources=conversation_ids,
        seed=0,
    )

    mixed_rows = [r for r in rows if r.needs_review_mixed_morpheme]
    metadata_rows = [r for r in rows if r.language_category == "metadata_or_noise"]

    n_rows_with_ordinary_switches = sum(
        1
        for r in rows
        if sum(switch_transitions_from_labels(r.token_language_labels)) > 0
    )

    # Invariant checks (booleans, safe to publish).
    mixed_morpheme_rows_cscont_only = all(
        set(r.condition_candidates) <= {"CsCont"} for r in mixed_rows
    )
    metadata_rows_have_no_conditions = all(
        not r.condition_candidates for r in metadata_rows
    )
    source_label_length_alignment_ok = all(
        r.source_token_language_labels is not None
        and len(r.source_token_language_labels) == len(r.tokens)
        for r in rows
    )

    return {
        "n_files": n_files,
        "conversation_ids": conversation_ids,
        "n_source_word_rows": n_source_word_rows,
        "n_projected_utterance_rows": len(rows),
        "counts_by_language_category": cs.counts_by_category,
        "condition_candidate_counts": cs.condition_candidate_counts,
        "total_tokens_including_punctuation": cs.total_tokens_including_punctuation,
        "total_word_tokens_excluding_punctuation": cs.total_word_tokens_excluding_punctuation,
        "total_english_word_tokens": cs.total_english_word_tokens,
        "total_spanish_word_tokens": cs.total_spanish_word_tokens,
        "total_neutral_bivalent_word_tokens": cs.total_neutral_bivalent_word_tokens,
        "total_other_word_tokens": cs.total_other_word_tokens,
        "total_mixed_morpheme_word_tokens": cs.total_mixed_morpheme_word_tokens,
        "total_metadata_tokens": cs.total_metadata_tokens,
        "total_punctuation_tokens": cs.total_punctuation_tokens,
        "n_needs_review_mixed_morpheme_rows": len(mixed_rows),
        "n_metadata_or_noise_rows": len(metadata_rows),
        "n_neutralized_disfluency_tokens": _count_neutralized_disfluency_tokens(rows),
        # Ordinary token-level switch diagnostics only (bivalent bridges and
        # mixed-morpheme internal sites are intentionally NOT computed here).
        "ordinary_token_switch_count": cs.total_switch_transitions,
        "ordinary_eng_to_spa_switch_count": cs.en_to_es_transitions,
        "ordinary_spa_to_eng_switch_count": cs.es_to_en_transitions,
        "n_rows_with_ordinary_token_switches": n_rows_with_ordinary_switches,
        "checks": {
            "mixed_morpheme_rows_cscont_only": mixed_morpheme_rows_cscont_only,
            "metadata_rows_have_no_conditions": metadata_rows_have_no_conditions,
            "source_label_length_alignment_ok": source_label_length_alignment_ok,
        },
        "switch_site_localization_todo": SWITCH_SITE_LOCALIZATION_TODO,
    }


def flatten_projected_sample_summary(summary: dict) -> dict:
    """Flatten the summary into a single scalar row for CSV output.

    Nested count dicts are expanded into prefixed columns; ``conversation_ids``
    is joined; the free-text TODO note is omitted from the CSV.
    """
    flat: dict[str, object] = {
        "n_files": summary["n_files"],
        "conversation_ids": ";".join(summary["conversation_ids"]),
        "n_source_word_rows": summary["n_source_word_rows"],
        "n_projected_utterance_rows": summary["n_projected_utterance_rows"],
        "total_tokens_including_punctuation": summary["total_tokens_including_punctuation"],
        "total_word_tokens_excluding_punctuation": summary[
            "total_word_tokens_excluding_punctuation"
        ],
        "total_english_word_tokens": summary["total_english_word_tokens"],
        "total_spanish_word_tokens": summary["total_spanish_word_tokens"],
        "total_neutral_bivalent_word_tokens": summary["total_neutral_bivalent_word_tokens"],
        "total_other_word_tokens": summary["total_other_word_tokens"],
        "total_mixed_morpheme_word_tokens": summary["total_mixed_morpheme_word_tokens"],
        "total_metadata_tokens": summary["total_metadata_tokens"],
        "total_punctuation_tokens": summary["total_punctuation_tokens"],
        "n_needs_review_mixed_morpheme_rows": summary["n_needs_review_mixed_morpheme_rows"],
        "n_metadata_or_noise_rows": summary["n_metadata_or_noise_rows"],
        "n_neutralized_disfluency_tokens": summary["n_neutralized_disfluency_tokens"],
        "ordinary_token_switch_count": summary["ordinary_token_switch_count"],
        "ordinary_eng_to_spa_switch_count": summary["ordinary_eng_to_spa_switch_count"],
        "ordinary_spa_to_eng_switch_count": summary["ordinary_spa_to_eng_switch_count"],
        "n_rows_with_ordinary_token_switches": summary["n_rows_with_ordinary_token_switches"],
    }
    for key, value in summary["counts_by_language_category"].items():
        flat[f"category__{key}"] = value
    for key, value in summary["condition_candidate_counts"].items():
        flat[f"condition__{key}"] = value
    for key, value in summary["checks"].items():
        flat[f"check__{key}"] = value
    return flat
