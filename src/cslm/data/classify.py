"""Toy heuristic language classifier.

This is a small word-list based classifier intended only to exercise the
corpus-classification pipeline on synthetic fixtures (see ``toy_corpus.py``).
It is not a real language-identification model and must not be pointed at
the real Bangor Miami corpus.
"""

from __future__ import annotations

import re

_METADATA_PATTERN = re.compile(
    r"^\s*[\[<].*[\]>]\s*$"  # bracketed markers, e.g. "[laughs]", "<unintelligible>"
    r"|^\s*[A-Z][A-Z0-9_]*\s*:\s*$"  # speaker labels, e.g. "SPEAKER1:"
    r"|^\s*%\w+:"  # CHAT-style comment tiers, e.g. "%com:"
)
_PUNCT_ONLY_PATTERN = re.compile(r"^[\s.,!?¿¡\-–—'\"…]*$")
_WORD_PATTERN = re.compile(r"[a-záéíóúñü]+", re.IGNORECASE)

_EN_WORDS: frozenset[str] = frozenset(
    {
        "the", "is", "are", "hello", "how", "you", "doing", "going", "to",
        "store", "want", "some", "coffee", "please", "dog", "ran", "fast",
        "yesterday", "friend", "school", "work", "today", "good", "morning",
        "thanks", "very", "much", "yes",
    }
)
_ES_WORDS: frozenset[str] = frozenset(
    {
        "el", "la", "es", "son", "un", "una", "hola", "como", "estas",
        "vas", "tienda", "quiero", "cafe", "café", "por", "favor", "perro",
        "corrio", "corrió", "rapido", "rápido", "ayer", "amigo", "escuela",
        "trabajo", "hoy", "buenos", "dias", "días", "gracias", "mucho",
        "si", "sí",
    }
)
_NEUTRAL_WORDS: frozenset[str] = frozenset({"maria", "juan", "ok", "okay", "netflix", "wifi"})


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
