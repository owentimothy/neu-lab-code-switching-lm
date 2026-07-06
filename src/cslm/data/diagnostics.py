"""Corpus diagnostics required by the "Required corpus diagnostics" section of CLAUDE.md.

Percentages are always computed against an explicit, named denominator
(all utterances vs. language-containing utterances) so the different
denominators described there are never conflated.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from cslm.data.classify import annotate_tokens, switch_transitions
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
    """Word-token count (excluding punctuation) for ``text``.

    Delegates to the shared toy tokenizer so this matches the per-utterance
    ``n_word_tokens_excluding_punctuation`` field exactly.
    """
    return annotate_tokens(text).n_word_tokens_excluding_punctuation


@dataclass
class CorpusSummary:
    corpus_name: str
    data_sources: list[str]
    seed: int
    n_conversations: int
    n_utterances: int
    # ``n_word_tokens`` now means word tokens EXCLUDING punctuation; it is kept
    # as an alias of ``total_word_tokens_excluding_punctuation`` for
    # backward compatibility.
    n_word_tokens: int
    n_subword_tokens: int | None
    # Aggregate token-count totals (see per-utterance token diagnostics).
    total_tokens_including_punctuation: int
    total_word_tokens_excluding_punctuation: int
    total_english_word_tokens: int
    total_spanish_word_tokens: int
    # ``eng&spa`` (bivalent) word tokens only; ``other`` word tokens are
    # aggregated separately in ``total_other_word_tokens`` so the two are
    # never conflated.
    total_neutral_bivalent_word_tokens: int
    total_other_word_tokens: int
    total_punctuation_tokens: int
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
    # Intra-sentential (within-utterance) switch diagnostics.
    cs_intra_sentential_count: int
    cs_pct_of_all_utterances: float
    cs_pct_of_language_containing_utterances: float
    en_to_es_transitions: int
    es_to_en_transitions: int
    total_switch_transitions: int
    # Inter-sentential (between-utterance) switch diagnostics, kept strictly
    # separate from the intra-sentential counts above.
    total_inter_sentential_switches: int
    inter_sentential_switches_eng_to_spa: int
    inter_sentential_switches_spa_to_eng: int
    inter_sentential_switches_same_speaker: int
    inter_sentential_switches_cross_speaker: int
    # Leakage and duplicate diagnostics.
    n_conversation_ids: int
    n_conversation_ids_spanning_multiple_splits: int
    n_duplicate_utterance_ids: int
    n_duplicate_utterance_texts: int
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
            "total_tokens_including_punctuation": self.total_tokens_including_punctuation,
            "total_word_tokens_excluding_punctuation": (
                self.total_word_tokens_excluding_punctuation
            ),
            "total_english_word_tokens": self.total_english_word_tokens,
            "total_spanish_word_tokens": self.total_spanish_word_tokens,
            "total_neutral_bivalent_word_tokens": self.total_neutral_bivalent_word_tokens,
            "total_other_word_tokens": self.total_other_word_tokens,
            "total_punctuation_tokens": self.total_punctuation_tokens,
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
            "total_inter_sentential_switches": self.total_inter_sentential_switches,
            "inter_sentential_switches_eng_to_spa": self.inter_sentential_switches_eng_to_spa,
            "inter_sentential_switches_spa_to_eng": self.inter_sentential_switches_spa_to_eng,
            "inter_sentential_switches_same_speaker": (
                self.inter_sentential_switches_same_speaker
            ),
            "inter_sentential_switches_cross_speaker": (
                self.inter_sentential_switches_cross_speaker
            ),
            "n_conversation_ids": self.n_conversation_ids,
            "n_conversation_ids_spanning_multiple_splits": (
                self.n_conversation_ids_spanning_multiple_splits
            ),
            "n_duplicate_utterance_ids": self.n_duplicate_utterance_ids,
            "n_duplicate_utterance_texts": self.n_duplicate_utterance_texts,
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
            "total_tokens_including_punctuation": self.total_tokens_including_punctuation,
            "total_word_tokens_excluding_punctuation": (
                self.total_word_tokens_excluding_punctuation
            ),
            "total_english_word_tokens": self.total_english_word_tokens,
            "total_spanish_word_tokens": self.total_spanish_word_tokens,
            "total_neutral_bivalent_word_tokens": self.total_neutral_bivalent_word_tokens,
            "total_other_word_tokens": self.total_other_word_tokens,
            "total_punctuation_tokens": self.total_punctuation_tokens,
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
            "total_inter_sentential_switches": self.total_inter_sentential_switches,
            "inter_sentential_switches_eng_to_spa": self.inter_sentential_switches_eng_to_spa,
            "inter_sentential_switches_spa_to_eng": self.inter_sentential_switches_spa_to_eng,
            "inter_sentential_switches_same_speaker": (
                self.inter_sentential_switches_same_speaker
            ),
            "inter_sentential_switches_cross_speaker": (
                self.inter_sentential_switches_cross_speaker
            ),
            "n_conversation_ids": self.n_conversation_ids,
            "n_conversation_ids_spanning_multiple_splits": (
                self.n_conversation_ids_spanning_multiple_splits
            ),
            "n_duplicate_utterance_ids": self.n_duplicate_utterance_ids,
            "n_duplicate_utterance_texts": self.n_duplicate_utterance_texts,
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

    # Token-count totals, recomputed from clean_text so the aggregates hold for
    # any row set, including manually constructed rows without stored counts.
    total_tokens_including_punctuation = 0
    total_word_tokens_excluding_punctuation = 0
    total_english_word_tokens = 0
    total_spanish_word_tokens = 0
    total_neutral_bivalent_word_tokens = 0
    total_other_word_tokens = 0
    total_punctuation_tokens = 0
    for row in rows:
        annotation = annotate_tokens(row.clean_text)
        total_tokens_including_punctuation += annotation.n_tokens_including_punctuation
        total_word_tokens_excluding_punctuation += annotation.n_word_tokens_excluding_punctuation
        total_english_word_tokens += annotation.n_english_word_tokens
        total_spanish_word_tokens += annotation.n_spanish_word_tokens
        total_neutral_bivalent_word_tokens += annotation.n_neutral_bivalent_word_tokens
        total_other_word_tokens += annotation.n_other_word_tokens
        total_punctuation_tokens += annotation.n_punctuation_tokens
    n_word_tokens = total_word_tokens_excluding_punctuation

    en_to_es_total = 0
    es_to_en_total = 0
    for row in rows:
        if row.language_category != "cs_within_utterance":
            continue
        en_to_es, es_to_en = switch_transitions(row.text)
        en_to_es_total += en_to_es
        es_to_en_total += es_to_en

    # Inter-sentential switches, aggregated from the per-row switch flags that
    # toy_corpus derives from ordered conversation structure. Kept separate
    # from the intra-sentential transition counts above.
    total_inter_sentential = 0
    inter_eng_to_spa = 0
    inter_spa_to_eng = 0
    inter_same_speaker = 0
    inter_cross_speaker = 0
    for row in rows:
        if not row.is_inter_sentential_switch_from_previous:
            continue
        total_inter_sentential += 1
        if row.inter_sentential_switch_direction_from_previous == "eng_to_spa":
            inter_eng_to_spa += 1
        elif row.inter_sentential_switch_direction_from_previous == "spa_to_eng":
            inter_spa_to_eng += 1
        if row.same_speaker_as_previous is True:
            inter_same_speaker += 1
        elif row.same_speaker_as_previous is False:
            inter_cross_speaker += 1

    # Leakage and duplicate diagnostics.
    splits_by_conversation: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        splits_by_conversation[row.conversation_id].add(row.split)
    n_conversation_ids = len(splits_by_conversation)
    n_conversation_ids_spanning_multiple_splits = sum(
        1 for splits in splits_by_conversation.values() if len(splits) > 1
    )
    utterance_id_counts = Counter(row.utterance_id for row in rows)
    n_duplicate_utterance_ids = sum(1 for count in utterance_id_counts.values() if count > 1)
    utterance_text_counts = Counter(row.clean_text for row in rows)
    n_duplicate_utterance_texts = sum(1 for count in utterance_text_counts.values() if count > 1)

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
        total_tokens_including_punctuation=total_tokens_including_punctuation,
        total_word_tokens_excluding_punctuation=total_word_tokens_excluding_punctuation,
        total_english_word_tokens=total_english_word_tokens,
        total_spanish_word_tokens=total_spanish_word_tokens,
        total_neutral_bivalent_word_tokens=total_neutral_bivalent_word_tokens,
        total_other_word_tokens=total_other_word_tokens,
        total_punctuation_tokens=total_punctuation_tokens,
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
        total_inter_sentential_switches=total_inter_sentential,
        inter_sentential_switches_eng_to_spa=inter_eng_to_spa,
        inter_sentential_switches_spa_to_eng=inter_spa_to_eng,
        inter_sentential_switches_same_speaker=inter_same_speaker,
        inter_sentential_switches_cross_speaker=inter_cross_speaker,
        n_conversation_ids=n_conversation_ids,
        n_conversation_ids_spanning_multiple_splits=n_conversation_ids_spanning_multiple_splits,
        n_duplicate_utterance_ids=n_duplicate_utterance_ids,
        n_duplicate_utterance_texts=n_duplicate_utterance_texts,
        condition_candidate_counts=condition_candidate_counts,
    )
