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

# Allowed token-level language labels (see classify.token_language_labels).
TOKEN_LANGUAGE_LABELS: frozenset[str] = frozenset({"eng", "spa", "eng&spa", "punct", "other"})

# Allowed inter-sentential switch directions between ordered utterances.
INTER_SENTENTIAL_DIRECTIONS: frozenset[str] = frozenset({"eng_to_spa", "spa_to_eng"})


@dataclass
class UtteranceRow:
    """A single classified utterance and its model-condition eligibility.

    Beyond the core classification fields, this schema carries the metadata the
    real Bangor Miami preprocessing will need: token-level language labels,
    token-count diagnostics, ordered-conversation context, inter-sentential
    switch flags, and nullable review-only heuristic fields for contested
    linguistic phenomena (borrowing, matrix language, equivalence). The
    review-only fields are placeholders for later human adjudication and must
    not be treated as ground truth.
    """

    utterance_id: str
    text: str
    source: str
    conversation_id: str
    speaker_id: str
    split: str
    language_category: str
    condition_candidates: list[str] = field(default_factory=list)

    # Token-level annotations. ``raw_text``/``clean_text`` default to ``text``
    # for the toy pipeline; the real pipeline will populate them separately.
    raw_text: str | None = None
    clean_text: str | None = None
    tokens: list[str] = field(default_factory=list)
    token_language_labels: list[str] = field(default_factory=list)

    # Token-count diagnostics.
    n_tokens_including_punctuation: int = 0
    n_word_tokens_excluding_punctuation: int = 0
    n_english_word_tokens: int = 0
    n_spanish_word_tokens: int = 0
    # ``eng&spa`` (bivalent) word tokens only. Unknown / proper-name /
    # out-of-vocabulary word tokens are counted in ``n_other_word_tokens``
    # instead, so the two are never conflated.
    n_neutral_bivalent_word_tokens: int = 0
    n_other_word_tokens: int = 0
    n_punctuation_tokens: int = 0

    # Ordered-conversation metadata. ``previous_*`` and
    # ``same_speaker_as_previous`` are ``None`` for the first utterance in a
    # conversation.
    utterance_index: int | None = None
    previous_utterance_id: str | None = None
    previous_speaker_id: str | None = None
    previous_language_category: str | None = None
    same_speaker_as_previous: bool | None = None

    # Inter-sentential switch relative to the previous utterance. ``None`` when
    # a switch is not well-defined (no previous utterance, or either utterance
    # lacks a clear dominant language). Kept strictly separate from the
    # intra-sentential (within-utterance) switch diagnostics.
    is_inter_sentential_switch_from_previous: bool | None = None
    inter_sentential_switch_direction_from_previous: str | None = None

    # Review-only heuristic fields for contested phenomena. These stay ``None``
    # (no automatic decisions); only the ``needs_review_*`` flags are set, to
    # mark utterances that will need human adjudication later.
    borrowing_status: str | None = None
    needs_review_borrowing: bool = False
    matrix_language_heuristic: str | None = None
    needs_review_matrix_language: bool = False
    equivalence_heuristic: str | None = None
    needs_review_equivalence: bool = False

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

        if self.raw_text is None:
            self.raw_text = self.text
        if self.clean_text is None:
            self.clean_text = self.text

        if len(self.token_language_labels) != len(self.tokens):
            raise ValueError(
                "token_language_labels length "
                f"({len(self.token_language_labels)}) must match tokens length "
                f"({len(self.tokens)})"
            )
        invalid_labels = set(self.token_language_labels) - TOKEN_LANGUAGE_LABELS
        if invalid_labels:
            raise ValueError(
                f"invalid token_language_labels: {sorted(invalid_labels)}; "
                f"expected values from {sorted(TOKEN_LANGUAGE_LABELS)}"
            )

        direction = self.inter_sentential_switch_direction_from_previous
        if direction is not None and direction not in INTER_SENTENTIAL_DIRECTIONS:
            raise ValueError(
                f"invalid inter_sentential_switch_direction_from_previous: {direction!r}; "
                f"expected None or one of {sorted(INTER_SENTENTIAL_DIRECTIONS)}"
            )

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
            "raw_text": self.raw_text,
            "clean_text": self.clean_text,
            "tokens": list(self.tokens),
            "token_language_labels": list(self.token_language_labels),
            "n_tokens_including_punctuation": self.n_tokens_including_punctuation,
            "n_word_tokens_excluding_punctuation": self.n_word_tokens_excluding_punctuation,
            "n_english_word_tokens": self.n_english_word_tokens,
            "n_spanish_word_tokens": self.n_spanish_word_tokens,
            "n_neutral_bivalent_word_tokens": self.n_neutral_bivalent_word_tokens,
            "n_other_word_tokens": self.n_other_word_tokens,
            "n_punctuation_tokens": self.n_punctuation_tokens,
            "utterance_index": self.utterance_index,
            "previous_utterance_id": self.previous_utterance_id,
            "previous_speaker_id": self.previous_speaker_id,
            "previous_language_category": self.previous_language_category,
            "same_speaker_as_previous": self.same_speaker_as_previous,
            "is_inter_sentential_switch_from_previous": (
                self.is_inter_sentential_switch_from_previous
            ),
            "inter_sentential_switch_direction_from_previous": (
                self.inter_sentential_switch_direction_from_previous
            ),
            "borrowing_status": self.borrowing_status,
            "needs_review_borrowing": self.needs_review_borrowing,
            "matrix_language_heuristic": self.matrix_language_heuristic,
            "needs_review_matrix_language": self.needs_review_matrix_language,
            "equivalence_heuristic": self.equivalence_heuristic,
            "needs_review_equivalence": self.needs_review_equivalence,
        }
