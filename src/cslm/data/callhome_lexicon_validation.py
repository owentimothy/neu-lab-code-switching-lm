"""Deterministic lexicon-based source-language validation scaffold (synthetic).

A **conservative** future validation method: it validates a single
:class:`cslm.data.callhome_chat.CallhomeUtterance` against **caller-provided**
lexicon sets, returning a content-free
:class:`cslm.data.callhome_source_validation.CallhomeSourceValidationDecision`.

Deliberate constraints (see ``docs/callhome_source_validation_method_policy.md``):

* It **loads no lexicon files** and **hardcodes no real vocabulary** — the caller
  supplies `lexicons_by_language` (e.g. synthetic sets in tests).
* A positive validation (`is_validated=True`, method ``lexicon_exact_match``)
  requires **all** of: at least one lexical token, every lexical token present in
  the expected-language lexicon, and no lexical token present in any
  non-expected-language lexicon. Any ambiguity (token in both lexicons, unknown
  token, or no lexical token) returns the conservative
  ``default_source_validation`` (not validated) — it prefers false negatives.
* It is **not** wired into the real-data pipeline; source directory alone never
  implies validation, and lexical content alone never implies validation without
  lexicon agreement.

Decisions carry only booleans, the language label, and safe labels — never
transcript text, tokens, filenames, speaker ids, refs, or notes.
"""

from __future__ import annotations

import unicodedata

from cslm.data.callhome_chat import CallhomeUtterance
from cslm.data.callhome_source_validation import (
    SUPPORTED_LANGUAGE_LABELS,
    CallhomeSourceValidationDecision,
    default_source_validation,
)

# CHAT residue that carries no lexical content (mirrors the screening heuristics).
_RESIDUE_TOKENS: frozenset[str] = frozenset({"xxx", "yyy", "www", "0"})

_VALIDATED_METHOD = "lexicon_exact_match"
_VALIDATED_REASON = "lexicon_expected_only"


def _normalize_token(raw: str) -> str:
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


def _normalize_lexicon(words: set[str]) -> set[str]:
    """Normalize lexicon entries with the same rule as tokens (never in place)."""
    normalized: set[str] = set()
    for word in words:
        norm = _normalize_token(word)
        if norm:
            normalized.add(norm)
    return normalized


def _lexical_tokens(text: str | None) -> list[str]:
    """Return normalized lexical tokens (residue/non-lexical markers excluded).

    Reads text **in memory only** to produce comparison tokens; nothing is
    stored or returned to any diagnostic. Residue markers, ``&``-forms, bracketed
    codes, and punctuation-only tokens are skipped (same rule as screening), then
    the remaining tokens are normalized via :func:`_normalize_token`.
    """
    if not text or not text.strip():
        return []
    out: list[str] = []
    for raw in text.split():
        t = raw.strip()
        # Residue / non-lexical markers are checked *before* normalization, so a
        # leading ``&`` or surrounding brackets are not stripped into a word.
        if not t or t.lower() in _RESIDUE_TOKENS or t.startswith("&"):
            continue
        if (t.startswith("[") and t.endswith("]")) or (t.startswith("(") and t.endswith(")")):
            continue
        norm = _normalize_token(t)
        if any(ch.isalpha() for ch in norm):
            out.append(norm)
    return out


def validate_utterance_against_lexicons(
    utterance: CallhomeUtterance,
    *,
    expected_language: str,
    lexicons_by_language: dict[str, set[str]],
) -> CallhomeSourceValidationDecision:
    """Validate one utterance against caller-provided lexicons (conservative).

    Returns a positive ``lexicon_exact_match`` decision only when every lexical
    token is in the expected-language lexicon and none is in any other-language
    lexicon; otherwise returns ``default_source_validation(expected_language)``.
    """
    if expected_language not in SUPPORTED_LANGUAGE_LABELS:
        raise ValueError(f"unsupported expected_language: {expected_language!r}")

    tokens = _lexical_tokens(utterance.raw_main_tier_text)
    if not tokens:
        # No lexical content -> cannot positively validate.
        return default_source_validation(expected_language)

    expected_lex = _normalize_lexicon(lexicons_by_language.get(expected_language, set()))
    other_lex: set[str] = set()
    for label, words in lexicons_by_language.items():
        if label != expected_language:
            other_lex |= _normalize_lexicon(words)

    for token in tokens:
        # A token in another language's lexicon (including a token in *both*,
        # i.e. ambiguous) or a token unknown to the expected lexicon blocks a
        # positive validation.
        if token in other_lex or token not in expected_lex:
            return default_source_validation(expected_language)

    return CallhomeSourceValidationDecision(
        is_validated=True,
        expected_language=expected_language,
        validation_method=_VALIDATED_METHOD,
        reason_codes=[_VALIDATED_REASON],
    )
