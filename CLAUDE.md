# Project: Code-switching LM probes for integrated bilingual syntax

## Goal

Build a reproducible experimental pipeline comparing masked language models trained under different corpus conditions:

1. EnglishMono: English monolingual baseline.
2. SpanishMono: Spanish monolingual baseline.
3. MonoCont: English and Spanish monolingual texts concatenated.
4. CsCont: English, Spanish, and English/Spanish code-switched dialogue.

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
- `EnglishMono` should contain English monolingual material only.
- `SpanishMono` should contain Spanish monolingual material only.
- `MonoCont` should contain English monolingual and Spanish monolingual material only, with no genuine code-switched utterances.
- `CsCont` should contain English monolingual, Spanish monolingual, and English/Spanish code-switched dialogue.
- Do not mix code-switched material into `EnglishMono`, `SpanishMono`, or `MonoCont`.
- Track corpus size, language balance, token counts, and random seed for every condition.
- Do not make theoretical claims from corpus labels alone.
- Claims about `CsCont` must be supported by saved corpus diagnostics.

## Model-condition logic

The four conditions serve different interpretive roles:

- `EnglishMono`: estimates behavior after English-only exposure.
- `SpanishMono`: estimates behavior after Spanish-only exposure.
- `MonoCont`: estimates behavior after bilingual exposure without code-switching.
- `CsCont`: estimates behavior after bilingual exposure with code-switching.

The key contrast for code-switching exposure is:

`CsCont` vs `MonoCont`

The monolingual baselines are interpretive anchors. They help determine whether `MonoCont` and `CsCont` shift toward English-like or Spanish-like expectations.

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

## Condition-candidate rules

Each utterance may be eligible for more than one model condition. Represent this as `condition_candidates`, not as a single forced label.

Expected eligibility:

- `en_only`: eligible for `EnglishMono`, `MonoCont`, and `CsCont`.
- `es_only`: eligible for `SpanishMono`, `MonoCont`, and `CsCont`.
- `cs_within_utterance`: eligible for `CsCont` only.
- `neutral_or_bivalent`: eligible only if an explicit inclusion policy is defined.
- `punctuation_or_empty`: exclude.
- `mixed_or_uncertain`: exclude unless manually resolved.
- `metadata_or_noise`: exclude.

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

## Tokenizer rule

Unless explicitly changed later, use the same tokenizer/vocabulary across all model conditions. This keeps model comparisons cleaner by making training corpus composition the main difference across conditions.

Do not let `EnglishMono` and `SpanishMono` use incompatible vocabularies unless the experiment is explicitly redesigned around tokenizer differences.

## Validation

Before making large changes, run:

```bash
pytest
ruff check .
```

## Do not do yet

- Do not train a model.
- Do not download large datasets.
- Do not process real Bangor Miami data.
- Do not implement final probe analysis.
- Do not put core experiment logic in notebooks.