"""Single source of truth for CALLHOME lexicon/token normalization.

This module holds the normalization and lexical-tokenization rules defined by
``docs/callhome_lexicon_normalization_policy.md``. They were previously private
helpers inside :mod:`cslm.data.callhome_lexicon_validation`; they are extracted
here, unchanged, so that **every** consumer — the lexicon validator and the
English SCOWL coverage diagnostic — applies the *exact same* rule to utterance
tokens and to lexicon entries. A match (or a coverage hit) is meaningful only if
both sides passed through one identical pipeline.

Everything here works **in memory only**. Nothing is printed, stored, or
returned to any diagnostic; callers receive normalized strings and are
responsible for keeping transcript-derived tokens out of committed output.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable

# CHAT residue that carries no lexical content (mirrors the screening heuristics).
RESIDUE_TOKENS: frozenset[str] = frozenset({"xxx", "yyy", "www", "0"})


def normalize_token(raw: str) -> str:
    """Normalize one token per ``docs/callhome_lexicon_normalization_policy.md``.

    Applied **identically** to utterance tokens and lexicon entries: NFC Unicode
    normalization, then strip leading/trailing punctuation (Unicode ``P*``
    categories, so inverted marks such as ``¿``/``¡`` are removed), then
    lowercase. **Internal** punctuation is preserved (e.g. the apostrophe in
    ``don't`` or hyphen in ``co-op``). Spanish accents are preserved (NFC keeps
    e.g. ``sí`` distinct from ``si``).
    """
    t = unicodedata.normalize("NFC", raw)
    # Strip leading/trailing punctuation (P*) and whitespace/separators (Z*).
    start, end = 0, len(t)
    while start < end and unicodedata.category(t[start])[0] in ("P", "Z"):
        start += 1
    while end > start and unicodedata.category(t[end - 1])[0] in ("P", "Z"):
        end -= 1
    return t[start:end].lower()


def normalize_lexicon(words: Iterable[str]) -> set[str]:
    """Normalize lexicon entries with the same rule as tokens (never in place)."""
    normalized: set[str] = set()
    for word in words:
        norm = normalize_token(word)
        if norm:
            normalized.add(norm)
    return normalized


def lexical_tokens(text: str | None) -> list[str]:
    """Return normalized lexical tokens (residue/non-lexical markers excluded).

    Reads text **in memory only** to produce comparison tokens; nothing is
    stored or returned to any diagnostic. Residue markers, ``&``-forms, bracketed
    codes, and punctuation-only tokens are skipped (same rule as screening), then
    the remaining tokens are normalized via :func:`normalize_token`.
    """
    if not text or not text.strip():
        return []
    out: list[str] = []
    for raw in text.split():
        t = raw.strip()
        # Residue / non-lexical markers are checked *before* normalization, so a
        # leading ``&`` or surrounding brackets are not stripped into a word.
        if not t or t.lower() in RESIDUE_TOKENS or t.startswith("&"):
            continue
        if (t.startswith("[") and t.endswith("]")) or (t.startswith("(") and t.endswith(")")):
            continue
        norm = normalize_token(t)
        if any(ch.isalpha() for ch in norm):
            out.append(norm)
    return out
