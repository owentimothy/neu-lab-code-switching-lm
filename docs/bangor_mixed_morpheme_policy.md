# Bangor CG-words: mixed-morpheme handling policy

Status: notes captured during the two-file Bangor CG-words dry run, before the
`BangorUtterance → UtteranceRow` projection. No code changes accompany this note.

This note deliberately avoids verbatim transcript text and corpus proper names;
cases are described abstractly by their source `langid` pattern.

## What "mixed morpheme" means here

The CG-words `langid` column sometimes marks a *single word token* whose
morphemes come from different languages, using a `+` separator (e.g.
`eng+spa`, `spa+eng`, `eng&spa+eng`). The parser normalizes any such label to
the token label `mixed_morpheme` and sets `needs_review_mixed_morpheme = true`
on the containing utterance. This is within-word morphological mixing, which is
distinct from ordinary sentential code-switching between separate word tokens.

## Source-label patterns observed in the two-file dry run

The two sample conversations contain a small number of mixed-morpheme review
tokens, falling into two source-label patterns.

### `eng&spa+eng` — bivalent/proper-name-like stem plus English possessive `'s`

A bivalent or proper-name-like stem carrying the English possessive clitic
`'s`. These should be **preserved and review-flagged**, but should **not** be
treated as ordinary sentential code-switching, and should **not** turn an
otherwise English utterance into `cs_within_utterance`. In the dry run these
occur inside English-frame utterances, which correctly remain `en_only` with
`needs_review_mixed_morpheme = true`.

### `eng+spa` — English lexical material with Spanish morphology

An English lexical root carrying Spanish inflectional morphology. This is a
**genuine internally mixed token**. The surrounding utterance frame may be
Spanish even though the token itself is mixed; such an utterance is a
Spanish-frame utterance containing an internally mixed English+Spanish token,
not a purely Spanish utterance.

## Policy (for the upcoming projection and any diagnostics)

- `mixed_morpheme` remains a normalized token label; it is never silently
  collapsed into `eng`, `spa`, `eng&spa`, or `other`.
- The original source `langid` (e.g. `eng&spa+eng`, `eng+spa`) must be
  **preserved somewhere** alongside the normalized label, not discarded.
- Mixed-morpheme tokens must **not** create ordinary `eng ↔ spa` switch
  transitions.
- Mixed-morpheme tokens must **not** automatically promote an otherwise English
  or Spanish utterance to `cs_within_utterance`.
- Utterances containing a mixed-morpheme token carry
  `needs_review_mixed_morpheme = true` for later human adjudication.
