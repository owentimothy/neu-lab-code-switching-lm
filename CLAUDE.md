cat > CLAUDE.md <<'EOF'
# Project: Code-switching LM probes for integrated bilingual syntax

## Goal

Build a reproducible experimental pipeline comparing masked language models trained under different corpus conditions:

1. MonoCont: English and Spanish monolingual texts concatenated.
2. CsCont: English, Spanish, and English/Spanish code-switched dialogue.
3. SpanishMono: Spanish monolingual baseline.

The core research question is whether code-switching exposure changes model behavior on syntactic probes, especially:

- Bilingual Sentence Superiority Effect-style probes.
- Pro-drop / overt subject pronoun expectation.
- Body-part possession / inalienable possession probes.

## Current phase

We are in the setup and data-plumbing phase.

Do not implement model training yet.
Do not implement probe scoring yet.
Do not run large experiments yet.
Do not process the real Bangor Miami corpus yet.

First priority:

toy corpus -> classified utterances -> corpus summary report

## Coding rules

- Keep reusable logic in `src/cslm/`.
- Use notebooks only for inspection, debugging, and figures.
- Do not hard-code local absolute paths.
- Every script should be runnable from the repo root.
- Prefer small, testable functions.
- Add or update tests when changing scoring, data schemas, or model logic.
- Use deterministic random seeds where possible.
- Never overwrite raw data.
- Save generated outputs under `outputs/`.

## Experimental rules

- Keep model conditions strictly separated.
- Do not mix CsCont data into MonoCont.
- Track corpus size, language balance, token counts, and random seed for every condition.
- Do not make theoretical claims from corpus labels alone.
- Claims about CsCont must be supported by saved corpus diagnostics.

## Corpus composition rules

The code-switching dataset should not be treated as one undifferentiated text dump.

When processing bilingual or code-switching data, classify each utterance into one of these categories:

- `en_only`: utterance contains English material only.
- `es_only`: utterance contains Spanish material only.
- `cs_within_utterance`: utterance contains both English and Spanish material inside the same utterance.
- `neutral_or_bivalent`: utterance contains neutral, ambiguous, proper-name-only, or bivalent material.
- `punctuation_or_empty`: utterance contains only punctuation, empty content, or non-linguistic material.
- `mixed_or_uncertain`: utterance cannot be reliably classified.
- `metadata_or_noise`: transcription markers, comments, speaker labels, or unusable metadata.

Do not silently discard rows. Save counts of kept and discarded rows with exclusion reasons.

## Required corpus diagnostics

For every corpus-building run, save a corpus summary containing:

- condition name
- data sources used
- random seed
- number of documents/conversations
- number of utterances
- number of word tokens
- number of model subword tokens, if available
- number and percentage of English-only utterances
- number and percentage of Spanish-only utterances
- number and percentage of code-switched utterances
- number of uncertain/excluded utterances
- exclusion reasons
- train/dev/test sizes
- train/dev/test language composition

For code-switched utterances, track:

- number of intra-sentential CS utterances
- percentage of all utterances that are intra-sentential CS
- percentage of language-containing utterances that are intra-sentential CS
- English -> Spanish transition counts
- Spanish -> English transition counts
- total switch transitions

Always distinguish between:

- percentage of all utterances
- percentage of language-containing utterances
- percentage of word tokens
- percentage of model subword tokens
- percentage of switch transitions

Do not mix these denominators.

## Sampling rules

Sampling proportions should be configurable, not hard-coded.

Support two eventual sampling strategies:

1. `naturalistic`: preserve observed corpus proportions as closely as possible.
2. `balanced_or_oversampled`: deliberately oversample code-switched material for experimental power.

Always report both target proportions and realized proportions.

## Validation

Before making large changes, run:

```bash
pytest
ruff check .