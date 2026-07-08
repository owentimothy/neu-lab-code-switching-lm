"""Toy heuristic language classifier.

This is a small word-list based classifier intended only to exercise the
corpus-classification pipeline on synthetic fixtures (see ``toy_corpus.py``).
It is not a real language-identification model and must not be pointed at
the real Bangor Miami corpus.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_METADATA_PATTERN = re.compile(
    r"^\s*[\[<].*[\]>]\s*$"  # bracketed markers, e.g. "[laughs]", "<unintelligible>"
    r"|^\s*[A-Z][A-Z0-9_]*\s*:\s*$"  # speaker labels, e.g. "SPEAKER1:"
    r"|^\s*%\w+:"  # CHAT-style comment tiers, e.g. "%com:"
)
_PUNCT_ONLY_PATTERN = re.compile(r"^[\s.,!?¿¡\-–—'\"…]*$")
_WORD_PATTERN = re.compile(r"[a-záéíóúñü]+", re.IGNORECASE)

_EN_WORDS: frozenset[str] = frozenset(
    {
        "i", "the", "is", "are", "hello", "how", "you", "doing", "going",
        "go", "to", "for", "store", "want", "some", "coffee", "please",
        "dog", "ran", "fast", "yesterday", "friend", "school", "work",
        "today", "good", "morning", "thanks", "very", "much", "yes",
    }
)
_ES_WORDS: frozenset[str] = frozenset(
    {
        "el", "la", "es", "son", "un", "una", "hola", "como", "estas",
        "vas", "tienda", "quiero", "cafe", "café", "por", "favor", "perro",
        "corrio", "corrió", "rapido", "rápido", "muy", "ayer", "amigo",
        "escuela", "trabajo", "hoy", "buenos", "dias", "días", "gracias",
        "mucho", "si", "sí", "empanada", "fiesta",
    }
)
_NEUTRAL_WORDS: frozenset[str] = frozenset({"maria", "juan", "ok", "okay", "netflix", "wifi"})

# Toy bivalent word list: forms equally valid as English and Spanish words in
# isolation. These are labeled ``eng&spa`` at the token level. This is a tiny
# hand-curated list for exercising the schema, not a real bivalency detector,
# and it is deliberately disjoint from the monolingual word lists so that
# utterance-level ``classify_utterance`` behavior is unaffected.
_BIVALENT_WORDS: frozenset[str] = frozenset({"no", "a", "me"})

# One word run OR one non-word/non-space character. Splitting punctuation into
# individual characters keeps ``n_punctuation_tokens`` unambiguous for toy data.
_TOKEN_PATTERN = re.compile(r"[a-záéíóúñü]+|[^\sa-záéíóúñü]", re.IGNORECASE)
_WORD_TOKEN_PATTERN = re.compile(r"^[a-záéíóúñü]+$", re.IGNORECASE)
_PUNCT_CHARS: frozenset[str] = frozenset(".,!?¿¡-–—'\"…:;()[]{}<>%&/\\")

# Utterance-level categories that carry a single clear dominant language, used
# for inter-sentential switch detection between ordered utterances.
_DOMINANT_LANGUAGE_BY_CATEGORY: dict[str, str] = {"en_only": "eng", "es_only": "spa"}


def _word_language(word: str) -> str:
    if word in _EN_WORDS:
        return "en"
    if word in _ES_WORDS:
        return "es"
    if word in _NEUTRAL_WORDS:
        return "neutral"
    return "unknown"


def classify_utterance(text: str) -> str:
    """Assign a toy ``language_category`` to a raw utterance string."""
    if _METADATA_PATTERN.match(text):
        return "metadata_or_noise"
    if _PUNCT_ONLY_PATTERN.match(text):
        return "punctuation_or_empty"

    words = [w.lower() for w in _WORD_PATTERN.findall(text)]
    if not words:
        return "punctuation_or_empty"

    languages = [_word_language(w) for w in words]
    has_en = "en" in languages
    has_es = "es" in languages
    has_neutral = "neutral" in languages
    has_unknown = "unknown" in languages

    if has_en and has_es:
        return "cs_within_utterance"
    if has_en:
        return "en_only"
    if has_es:
        return "es_only"
    if has_neutral and not has_unknown:
        return "neutral_or_bivalent"
    return "mixed_or_uncertain"


def switch_transitions(text: str) -> tuple[int, int]:
    """Count en->es and es->en transitions among the known-language words.

    Words tagged ``neutral`` or ``unknown`` are skipped when building the
    transition sequence, since they carry no code-switch signal on their own.
    """
    words = [w.lower() for w in _WORD_PATTERN.findall(text)]
    sequence = [lang for lang in (_word_language(w) for w in words) if lang in ("en", "es")]

    en_to_es = 0
    es_to_en = 0
    for prev, curr in zip(sequence, sequence[1:]):
        if prev == "en" and curr == "es":
            en_to_es += 1
        elif prev == "es" and curr == "en":
            es_to_en += 1
    return en_to_es, es_to_en


def switch_transitions_from_labels(labels: list[str]) -> tuple[int, int]:
    """Count intra-sentential eng->spa and spa->en transitions from token labels.

    Only ``eng`` and ``spa`` labels carry a code-switch signal, so every other
    label (``punct``, ``neutral``, ``eng&spa``, ``other``) is skipped when
    building the transition sequence. This is the label-driven counterpart of
    :func:`switch_transitions`, used so intra-sentential diagnostics rely on the
    stored token-level labels rather than re-tokenizing raw text.
    """
    sequence = [label for label in labels if label in ("eng", "spa")]
    en_to_es = 0
    es_to_en = 0
    for prev, curr in zip(sequence, sequence[1:]):
        if prev == "eng" and curr == "spa":
            en_to_es += 1
        elif prev == "spa" and curr == "eng":
            es_to_en += 1
    return en_to_es, es_to_en


def tokenize(text: str) -> list[str]:
    """Split ``text`` into word tokens and single-character punctuation tokens.

    This is a toy whitespace/punctuation tokenizer for synthetic fixtures, not
    a real subword tokenizer. Word runs (including accented Spanish letters) are
    kept whole; each punctuation/symbol character becomes its own token.
    """
    return _TOKEN_PATTERN.findall(text)


def _token_language_label(token: str) -> str:
    """Assign one token-level language label to a single ``token``.

    Word tokens resolve to ``eng&spa`` (bivalent), ``eng``, ``spa``,
    ``neutral`` (language-neutral proper names / interjections), or ``other``
    (unknown / out-of-vocabulary). ``neutral`` is kept distinct from ``other``
    so language-neutral material is never conflated with genuinely unknown
    tokens.
    """
    if _WORD_TOKEN_PATTERN.match(token):
        lowered = token.lower()
        if lowered in _BIVALENT_WORDS or (lowered in _EN_WORDS and lowered in _ES_WORDS):
            return "eng&spa"
        if lowered in _EN_WORDS:
            return "eng"
        if lowered in _ES_WORDS:
            return "spa"
        if lowered in _NEUTRAL_WORDS:
            return "neutral"
        return "other"
    if all(ch in _PUNCT_CHARS for ch in token):
        return "punct"
    return "other"


def token_language_labels(tokens: list[str]) -> list[str]:
    """Assign a token-level language label to each token in ``tokens``."""
    return [_token_language_label(t) for t in tokens]


@dataclass(frozen=True)
class TokenAnnotation:
    """Tokens, their language labels, and derived token-count diagnostics."""

    tokens: list[str]
    token_language_labels: list[str]
    n_tokens_including_punctuation: int
    n_word_tokens_excluding_punctuation: int
    n_english_word_tokens: int
    n_spanish_word_tokens: int
    n_neutral_bivalent_word_tokens: int
    n_other_word_tokens: int
    n_punctuation_tokens: int
    # Real-corpus (Bangor) buckets. The toy annotator never produces these, so
    # they default to 0; projected rows populate them from stored counts.
    n_mixed_morpheme_word_tokens: int = 0
    n_metadata_tokens: int = 0


def annotate_tokens(text: str) -> TokenAnnotation:
    """Tokenize ``text`` and compute per-utterance token-count diagnostics.

    Word tokens exclude punctuation and split into disjoint buckets:
    ``eng`` (English), ``spa`` (Spanish), the neutral/bivalent bucket
    (``neutral`` language-neutral proper names/interjections + ``eng&spa``
    bivalent tokens), and ``other`` (unknown / out-of-vocabulary word tokens).
    ``other`` tokens are counted separately from the neutral/bivalent bucket, so
    ``n_word_tokens_excluding_punctuation`` always equals
    ``n_english + n_spanish + n_neutral_bivalent + n_other``.
    """
    tokens = tokenize(text)
    labels = token_language_labels(tokens)
    n_punct = labels.count("punct")
    n_english = labels.count("eng")
    n_spanish = labels.count("spa")
    # Both language-neutral (``neutral``) and bivalent (``eng&spa``) word tokens
    # go in the neutral/bivalent bucket; ``other`` (unknown/OOV) stays separate.
    n_neutral_bivalent = labels.count("neutral") + labels.count("eng&spa")
    n_other = labels.count("other")
    return TokenAnnotation(
        tokens=tokens,
        token_language_labels=labels,
        n_tokens_including_punctuation=len(tokens),
        n_word_tokens_excluding_punctuation=len(tokens) - n_punct,
        n_english_word_tokens=n_english,
        n_spanish_word_tokens=n_spanish,
        n_neutral_bivalent_word_tokens=n_neutral_bivalent,
        n_other_word_tokens=n_other,
        n_punctuation_tokens=n_punct,
    )


def inter_sentential_switch(
    previous_category: str | None,
    current_category: str,
) -> tuple[bool | None, str | None]:
    """Detect an inter-sentential switch between two ordered utterances.

    Returns ``(is_switch, direction)``. A switch is only detected when both the
    previous and current utterances have a single clear dominant language
    (``en_only`` -> eng, ``es_only`` -> spa). Anything else (no previous
    utterance, code-switched, neutral, excluded) is undefined and returns
    ``(None, None)`` rather than guessing. When both dominant languages are
    defined and equal, there is no switch: ``(False, None)``. Directions are
    ``"eng_to_spa"`` and ``"spa_to_eng"``.
    """
    if previous_category is None:
        return None, None
    prev_lang = _DOMINANT_LANGUAGE_BY_CATEGORY.get(previous_category)
    curr_lang = _DOMINANT_LANGUAGE_BY_CATEGORY.get(current_category)
    if prev_lang is None or curr_lang is None:
        return None, None
    if prev_lang == curr_lang:
        return False, None
    if prev_lang == "eng" and curr_lang == "spa":
        return True, "eng_to_spa"
    return True, "spa_to_eng"
