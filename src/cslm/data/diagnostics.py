"""Corpus diagnostics required by the "Required corpus diagnostics" section of CLAUDE.md.

Percentages are always computed against an explicit, named denominator
(all utterances vs. language-containing utterances) so the different
denominators described there are never conflated.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from cslm.data.classify import switch_transitions
from cslm.data.schema import CONDITIONS, UtteranceRow

ALL_CATEGORIES: tuple[str, ...] = (
    "en_only",
    "es_only",
    "cs_within_utterance",
    "neutral_or_bivalent",
    "punctuation_or_empty",
    "mixed_or_uncertain",
    "metadata_or_noise",
)
# Ordered tuples, not sets: their iteration order determines the key order
# of dicts that get serialized to JSON/CSV, and frozenset iteration order is
# not stable across interpreter runs (PYTHONHASHSEED). Order matches
# ALL_CATEGORIES.
_LANGUAGE_CONTAINING_CATEGORIES: tuple[str, ...] = ("en_only", "es_only", "cs_within_utterance")
_EXCLUDED_CATEGORIES: tuple[str, ...] = (
    "neutral_or_bivalent",
    "punctuation_or_empty",
    "mixed_or_uncertain",
    "metadata_or_noise",
)
_SPLITS: tuple[str, ...] = ("train", "dev", "test")


def _pct(numerator: int, denominator: int) -> float:
    return round(100.0 * numerator / denominator, 4) if denominator else 0.0


def word_token_count(text: str) -> int:
    """Whitespace token count, per the "word tokens" diagnostic field."""
    return len(text.split())


@dataclass
class CorpusSummary:
    corpus_name: str
    data_sources: list[str]
    seed: int
    n_conversations: int
    n_utterances: int
    n_word_tokens: int
    n_subword_tokens: int | None
    counts_by_category: dict[str, int]
    pct_of_all_utterances: dict[str, float]
    # Keyed only by the language-containing categories (en_only, es_only,
    # cs_within_utterance); excluded categories have no meaning under this
    # denominator and are not reported here.
    pct_of_language_containing_utterances: dict[str, float]
    n_language_containing_utterances: int
    n_excluded_utterances: int
    exclusion_reasons: dict[str, int]
    split_counts: dict[str, int]
    split_language_composition: dict[str, dict[str, int]]
    cs_intra_sentential_count: int
    cs_pct_of_all_utterances: float
    cs_pct_of_language_containing_utterances: float
    en_to_es_transitions: int
    es_to_en_transitions: int
    total_switch_transitions: int
    condition_candidate_counts: dict[str, int]

    def to_dict(self) -> dict:
        return {
            "corpus_name": self.corpus_name,
            "data_sources": self.data_sources,
            "seed": self.seed,
            "n_conversations": self.n_conversations,
            "n_utterances": self.n_utterances,
            "n_word_tokens": self.n_word_tokens,
            "n_subword_tokens": self.n_subword_tokens,
            "counts_by_category": self.counts_by_category,
            "pct_of_all_utterances": self.pct_of_all_utterances,
            "pct_of_language_containing_utterances": self.pct_of_language_containing_utterances,
            "n_language_containing_utterances": self.n_language_containing_utterances,
            "n_excluded_utterances": self.n_excluded_utterances,
            "exclusion_reasons": self.exclusion_reasons,
            "split_counts": self.split_counts,
            "split_language_composition": self.split_language_composition,
            "cs_intra_sentential_count": self.cs_intra_sentential_count,
            "cs_pct_of_all_utterances": self.cs_pct_of_all_utterances,
            "cs_pct_of_language_containing_utterances": (
                self.cs_pct_of_language_containing_utterances
            ),
            "en_to_es_transitions": self.en_to_es_transitions,
            "es_to_en_transitions": self.es_to_en_transitions,
            "total_switch_transitions": self.total_switch_transitions,
            "condition_candidate_counts": self.condition_candidate_counts,
        }

    def to_flat_row(self) -> dict:
        """Flatten nested fields into a single CSV-friendly row."""
        flat: dict = {
            "corpus_name": self.corpus_name,
            "data_sources": ";".join(self.data_sources),
            "seed": self.seed,
            "n_conversations": self.n_conversations,
            "n_utterances": self.n_utterances,
            "n_word_tokens": self.n_word_tokens,
            "n_subword_tokens": self.n_subword_tokens,
            "n_language_containing_utterances": self.n_language_containing_utterances,
            "n_excluded_utterances": self.n_excluded_utterances,
            "cs_intra_sentential_count": self.cs_intra_sentential_count,
            "cs_pct_of_all_utterances": self.cs_pct_of_all_utterances,
            "cs_pct_of_language_containing_utterances": (
                self.cs_pct_of_language_containing_utterances
            ),
            "en_to_es_transitions": self.en_to_es_transitions,
            "es_to_en_transitions": self.es_to_en_transitions,
            "total_switch_transitions": self.total_switch_transitions,
        }
        for category in ALL_CATEGORIES:
            flat[f"count__{category}"] = self.counts_by_category[category]
            flat[f"pct_all__{category}"] = self.pct_of_all_utterances[category]
        for category, pct in self.pct_of_language_containing_utterances.items():
            flat[f"pct_lang__{category}"] = pct
        for reason, count in self.exclusion_reasons.items():
            flat[f"excluded__{reason}"] = count
        for split in _SPLITS:
            flat[f"split__{split}"] = self.split_counts[split]
            for category in ALL_CATEGORIES:
                flat[f"split__{split}__{category}"] = self.split_language_composition[split][
                    category
                ]
        for condition, count in self.condition_candidate_counts.items():
            flat[f"condition__{condition}"] = count
        return flat


def build_corpus_summary(
    rows: list[UtteranceRow],
    *,
    corpus_name: str,
    data_sources: list[str],
    seed: int,
    n_subword_tokens: int | None = None,
) -> CorpusSummary:
    """Compute the full set of required corpus diagnostics for ``rows``."""
    n_utterances = len(rows)
    n_conversations = len({row.conversation_id for row in rows})

    raw_category_counts = Counter(row.language_category for row in rows)
    counts_by_category = {c: raw_category_counts.get(c, 0) for c in ALL_CATEGORIES}

    n_language_containing = sum(
        counts_by_category[c] for c in _LANGUAGE_CONTAINING_CATEGORIES
    )

    pct_of_all = {c: _pct(counts_by_category[c], n_utterances) for c in ALL_CATEGORIES}
    pct_of_language_containing = {
        c: _pct(counts_by_category[c], n_language_containing)
        for c in _LANGUAGE_CONTAINING_CATEGORIES
    }

    exclusion_reasons = {
        c: counts_by_category[c] for c in _EXCLUDED_CATEGORIES if counts_by_category[c] > 0
    }
    n_excluded = sum(exclusion_reasons.values())

    raw_split_counts = Counter(row.split for row in rows)
    split_counts = {s: raw_split_counts.get(s, 0) for s in _SPLITS}
    split_language_composition = {}
    for split in _SPLITS:
        split_category_counts = Counter(
            row.language_category for row in rows if row.split == split
        )
        split_language_composition[split] = {
            c: split_category_counts.get(c, 0) for c in ALL_CATEGORIES
        }

    n_word_tokens = sum(word_token_count(row.text) for row in rows)

    en_to_es_total = 0
    es_to_en_total = 0
    for row in rows:
        if row.language_category != "cs_within_utterance":
            continue
        en_to_es, es_to_en = switch_transitions(row.text)
        en_to_es_total += en_to_es
        es_to_en_total += es_to_en

    condition_candidate_counts = {c: 0 for c in sorted(CONDITIONS)}
    for row in rows:
        for condition in row.condition_candidates:
            condition_candidate_counts[condition] += 1

    return CorpusSummary(
        corpus_name=corpus_name,
        data_sources=list(data_sources),
        seed=seed,
        n_conversations=n_conversations,
        n_utterances=n_utterances,
        n_word_tokens=n_word_tokens,
        n_subword_tokens=n_subword_tokens,
        counts_by_category=counts_by_category,
        pct_of_all_utterances=pct_of_all,
        pct_of_language_containing_utterances=pct_of_language_containing,
        n_language_containing_utterances=n_language_containing,
        n_excluded_utterances=n_excluded,
        exclusion_reasons=exclusion_reasons,
        split_counts=split_counts,
        split_language_composition=split_language_composition,
        cs_intra_sentential_count=counts_by_category["cs_within_utterance"],
        cs_pct_of_all_utterances=pct_of_all["cs_within_utterance"],
        cs_pct_of_language_containing_utterances=pct_of_language_containing[
            "cs_within_utterance"
        ],
        en_to_es_transitions=en_to_es_total,
        es_to_en_transitions=es_to_en_total,
        total_switch_transitions=en_to_es_total + es_to_en_total,
        condition_candidate_counts=condition_candidate_counts,
    )
