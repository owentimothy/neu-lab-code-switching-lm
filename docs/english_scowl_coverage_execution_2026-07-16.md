# English SCOWL Coverage Execution Record — 2026-07-16

## Status

```text
Decision B review of exact seven-count schema:          PASS
One canonical English local run:                        COMPLETE
Whole-bundle k = 10 privacy guard:                      PASS
Aggregate result approved for this record:              YES

Source-language validation / clean promotion:           CLOSED / UNCHANGED
Condition routing / dataset construction:               CLOSED
Spanish lexicon / locale selection:                     CLOSED
Tokenizer training / model training / probes:           CLOSED
```

This document preserves the first real, aggregate-only English SCOWL coverage
result. It contains **only** seven whole-corpus integer counts and public
repository commit identifiers. It contains no transcript text, token string,
header value, participant information, speaker identifier, conversation
identifier, corpus filename, local path, lexical entry, resource hash, notice,
provenance value, per-row record, or per-row provenance.

## Execution identity

- Execution date: `2026-07-16`.
- Repository `main` and runner merge commit:
  `4b51e390d859db1daa7823e52cea1f316693584d`.
- Runner feature commit:
  `f8bfc716c5d9c521864a6138528f7d300d6b327d`.
- Entrypoint: `scripts/dry_run_english_scowl_coverage.py`.
- Population: every utterance parsed from every direct regular non-symlink
  `*.cha` file in the one canonical repository-relative English CALLHOME
  directory, in deterministic sorted order.
- Execution count: exactly one authorized real run.
- Output destination: standard output only; the runner wrote no file.
- Repository state after execution: clean and synchronized with `origin/main`.

No corpus path override, filename selector, subset, filter, sampling option, or
output-file option existed. Spanish CALLHOME and Bangor were not opened by this
runner.

## Decision B per-output review

The seven-count schema passed the required review under
`docs/callhome_ground_rules.md` before execution:

- **Aggregate-only:** all values describe the complete canonical population;
  there is no row, file, conversation, speaker, or subgroup breakdown.
- **Non-transcript:** the schema cannot contain transcript text, tokens, header
  values, examples, or unknown-word strings.
- **Identifier-free:** it carries no participant, speaker, conversation, file,
  media, or path field.
- **Non-reconstructive:** the fixed full-population design exposes no subsetting
  controls. The whole bundle is withheld if any positive scalar count is below
  `10`, so a small cell cannot be recovered through complementary totals.
- **Atomic:** the complete summary is validated and privacy-checked before any
  number is printed. Failures emit no partial aggregate.

Approval is limited to these seven scalar fields, this canonical population,
and this execution record. A changed population, additional field, subset,
percentage, or repeated external release requires a new review.

## Approved aggregate result

```text
n_results:                         56204
outcome__all_covered:              47445
outcome__has_uncovered:             6388
outcome__no_lexical_tokens:         2371
n_tokens_total:                   361935
n_covered_total:                  354465
n_uncovered_total:                  7470
```

The invariants reconcile:

```text
47445 + 6388 + 2371 = 56204
354465 + 7470 = 361935
```

Every positive scalar count is at least `10`, so the whole-bundle privacy guard
passed. No percentage, rate, average, sample, example, distribution, or lexical
item is reported.

## Scientific interpretation boundary

This result answers only:

> How many retained lexical tokens in the canonical English CALLHOME population
> are present in the independently approved English SCOWL resource?

It does **not** establish that an utterance is monolingual English. English-only
coverage cannot detect every Spanish token, cross-language overlap, borrowing,
or code-switch. The run produced no source-language validation decision, set no
`is_validated` or `clean` value, admitted no row to a condition, and created no
training dataset. CALLHOME remains barred from `CsCont`; Bangor remains
`CsCont`-only.

The result was not used to tune, expand, filter, normalize, or otherwise change
the SCOWL resource.

## Citation, license, and use restrictions

Corpus-specific citation:

> Kingsbury, Paul, et al. *CALLHOME American English Transcripts LDC97T14*.
> Web Download. Philadelphia: Linguistic Data Consortium, 1997.
> DOI: `10.35111/z1z4-ep76`.

Official catalog record: <https://catalog.ldc.upenn.edu/LDC97T14>

CABank citation:

> MacWhinney, B., & Wagner, J. (2010). Transcribing, searching and data sharing:
> The CLAN software and the TalkBank data repository. *Gesprachsforschung*, 11,
> 154–173.

TalkBank materials are governed, except where otherwise indicated, by
CC BY-NC-SA 3.0 and are restricted to professional, research, teaching, and
other non-commercial uses under the current TalkBank Ground Rules. This record
redistributes no underlying transcript data. Any publication using the corpus
must follow the corpus-specific and general-database citation requirements in
`docs/callhome_ground_rules.md` and the current official source pages.

- Ground Rules: <https://talkbank.org/0share/rules.html>
- Citation rules: <https://talkbank.org/0share/citation.html>

## Remaining gates

- Spanish locale/resource selection remains deferred until it is justified by
  independent, non-CALLHOME evidence and approved in a dedicated decision.
- Actual CALLHOME source-language validation remains closed until both sides of
  the conservative validation method are approved and synthetic-tested.
- `clean` promotion remains disabled; the clean-row count remains zero.
- Condition dataset construction, tokenizer training, model training, and probes
  remain closed.

The next approved scientific step is an external-evidence research plan for the
Spanish locale/resource decision. CALLHOME outcomes must not be used to choose or
tune that resource.
