"""Synthetic toy utterance fixtures for the data-plumbing pipeline.

These rows exist only to exercise classification and diagnostics end-to-end
before any real Bangor Miami data is touched. They are not derived from any
real corpus.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from cslm.data.classify import classify_utterance
from cslm.data.conditions import condition_candidates_for_category
from cslm.data.schema import UtteranceRow

SOURCE_NAME = "toy_synthetic_v1"


@dataclass(frozen=True)
class _RawUtterance:
    utterance_id: str
    text: str
    conversation_id: str
    speaker_id: str


_RAW_UTTERANCES: tuple[_RawUtterance, ...] = (
    # en_only
    _RawUtterance("u001", "Hello, how are you doing today?", "conv01", "spk1"),
    _RawUtterance("u002", "I want to go to the store for some coffee.", "conv01", "spk2"),
    _RawUtterance("u003", "The dog ran very fast yesterday.", "conv02", "spk1"),
    # es_only
    _RawUtterance("u004", "Hola, como estas hoy?", "conv01", "spk1"),
    _RawUtterance("u005", "Quiero un cafe por favor.", "conv01", "spk2"),
    _RawUtterance("u006", "El perro corrio muy rapido ayer.", "conv02", "spk2"),
    # cs_within_utterance
    _RawUtterance("u007", "I want quiero some coffee cafe please.", "conv03", "spk1"),
    _RawUtterance("u008", "Hola friend, how are you como estas?", "conv03", "spk2"),
    _RawUtterance("u009", "The perro ran rapido to la escuela today.", "conv03", "spk1"),
    # neutral_or_bivalent
    _RawUtterance("u010", "Maria Netflix.", "conv04", "spk1"),
    _RawUtterance("u011", "Okay Juan.", "conv04", "spk2"),
    # punctuation_or_empty
    _RawUtterance("u012", "...", "conv04", "spk1"),
    _RawUtterance("u013", "", "conv04", "spk2"),
    # mixed_or_uncertain
    _RawUtterance("u014", "Xyzzy blorp fnord.", "conv05", "spk1"),
    # metadata_or_noise
    _RawUtterance("u015", "[laughs]", "conv05", "spk2"),
    _RawUtterance("u016", "SPEAKER1:", "conv05", "spk1"),
    # en_only / es_only, in their own conversation. This gives the
    # language-containing stratum 4 conversations total (with conv01,
    # conv02, conv03), which is enough for the stratified split below to
    # guarantee every split contains at least one language-containing
    # utterance regardless of shuffle seed.
    _RawUtterance("u017", "Good morning, thanks very much.", "conv06", "spk1"),
    _RawUtterance("u018", "Buenos dias, gracias mucho.", "conv06", "spk2"),
)

_LANGUAGE_CONTAINING_CATEGORIES = frozenset({"en_only", "es_only", "cs_within_utterance"})


def build_toy_rows(
    *,
    seed: int = 0,
    include_neutral_or_bivalent: bool = False,
    train_frac: float = 0.6,
    dev_frac: float = 0.2,
) -> list[UtteranceRow]:
    """Classify the toy fixtures and assign deterministic train/dev/test splits.

    Splits are assigned per conversation_id, not per utterance, so that all
    utterances belonging to the same conversation land in the same split.
    Conversations are additionally stratified into a language-containing
    group (en_only, es_only, cs_within_utterance) and an other group before
    splitting, so that train/dev/test each receive at least one
    language-containing conversation regardless of shuffle seed.

    Raises:
        ValueError: if ``train_frac``/``dev_frac`` would leave any split
            without a language-containing conversation, given the toy
            fixture's fixed number of language-containing conversations.
    """
    category_by_utterance = {
        raw.utterance_id: classify_utterance(raw.text) for raw in _RAW_UTTERANCES
    }

    language_containing_conversations = sorted(
        {
            raw.conversation_id
            for raw in _RAW_UTTERANCES
            if category_by_utterance[raw.utterance_id] in _LANGUAGE_CONTAINING_CATEGORIES
        }
    )
    other_conversations = sorted(
        {raw.conversation_id for raw in _RAW_UTTERANCES}
        - set(language_containing_conversations)
    )

    split_by_conversation = _assign_splits(
        language_containing_conversations,
        seed=seed,
        train_frac=train_frac,
        dev_frac=dev_frac,
        require_all_splits=True,
    )
    split_by_conversation.update(
        _assign_splits(
            other_conversations,
            seed=seed,
            train_frac=train_frac,
            dev_frac=dev_frac,
        )
    )

    rows: list[UtteranceRow] = []
    for raw in _RAW_UTTERANCES:
        category = category_by_utterance[raw.utterance_id]
        candidates = condition_candidates_for_category(
            category, include_neutral_or_bivalent=include_neutral_or_bivalent
        )
        rows.append(
            UtteranceRow(
                utterance_id=raw.utterance_id,
                text=raw.text,
                source=SOURCE_NAME,
                conversation_id=raw.conversation_id,
                speaker_id=raw.speaker_id,
                split=split_by_conversation[raw.conversation_id],
                language_category=category,
                condition_candidates=candidates,
            )
        )
    return rows


def _assign_splits(
    keys: list[str],
    *,
    seed: int,
    train_frac: float,
    dev_frac: float,
    require_all_splits: bool = False,
) -> dict[str, str]:
    """Deterministically assign each key (e.g. conversation_id) to a split.

    If ``require_all_splits`` is set, raises ``ValueError`` when the given
    fractions would leave train, dev, or test empty for this many keys,
    instead of silently producing an empty split.
    """
    rng = random.Random(seed)
    shuffled = keys[:]
    rng.shuffle(shuffled)

    n = len(shuffled)
    n_train = round(n * train_frac)
    n_dev = round(n * dev_frac)
    n_test = n - n_train - n_dev

    if require_all_splits and (n_train < 1 or n_dev < 1 or n_test < 1):
        raise ValueError(
            f"train_frac={train_frac!r}, dev_frac={dev_frac!r} would leave a "
            f"split empty for {n} language-containing conversations "
            f"(train={n_train}, dev={n_dev}, test={n_test}); choose fractions "
            "that leave at least one conversation per split"
        )

    split_by_key: dict[str, str] = {}
    for i, key in enumerate(shuffled):
        if i < n_train:
            split_by_key[key] = "train"
        elif i < n_train + n_dev:
            split_by_key[key] = "dev"
        else:
            split_by_key[key] = "test"
    return split_by_key
