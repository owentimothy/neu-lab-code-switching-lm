"""Utterance row schema shared by the classifier, diagnostics, and IO layers."""

from __future__ import annotations

from dataclasses import dataclass, field

LANGUAGE_CATEGORIES: frozenset[str] = frozenset(
    {
        "en_only",
        "es_only",
        "cs_within_utterance",
        "neutral_or_bivalent",
        "punctuation_or_empty",
        "mixed_or_uncertain",
        "metadata_or_noise",
    }
)

CONDITIONS: frozenset[str] = frozenset({"EnglishMono", "SpanishMono", "MonoCont", "CsCont"})

SPLITS: frozenset[str] = frozenset({"train", "dev", "test"})


@dataclass
class UtteranceRow:
    """A single classified utterance and its model-condition eligibility."""

    utterance_id: str
    text: str
    source: str
    conversation_id: str
    speaker_id: str
    split: str
    language_category: str
    condition_candidates: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.utterance_id:
            raise ValueError("utterance_id must be non-empty")
        if self.split not in SPLITS:
            raise ValueError(f"invalid split: {self.split!r}; expected one of {sorted(SPLITS)}")
        if self.language_category not in LANGUAGE_CATEGORIES:
            raise ValueError(
                f"invalid language_category: {self.language_category!r}; "
                f"expected one of {sorted(LANGUAGE_CATEGORIES)}"
            )
        invalid_conditions = set(self.condition_candidates) - CONDITIONS
        if invalid_conditions:
            raise ValueError(f"invalid condition_candidates: {sorted(invalid_conditions)}")

    def to_dict(self) -> dict:
        return {
            "utterance_id": self.utterance_id,
            "text": self.text,
            "source": self.source,
            "conversation_id": self.conversation_id,
            "speaker_id": self.speaker_id,
            "split": self.split,
            "language_category": self.language_category,
            "condition_candidates": list(self.condition_candidates),
        }
