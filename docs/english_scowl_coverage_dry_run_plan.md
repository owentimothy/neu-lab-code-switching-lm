# English SCOWL Coverage Aggregate Dry-Run Plan

## Status

```text
Runner + synthetic tests:                               IMPLEMENTED / OPEN
k = 10 whole-bundle privacy guard:                      ADOPTED (new project rule)

Decision B approval of the seven-count schema:          APPROVED (canonical run only)
Aggregate execution record:                             APPROVED / RECORDED
Separately authorized real local execution:             COMPLETE (one canonical run)
Source-language validation / clean promotion:           CLOSED / UNCHANGED
Condition routing / dataset construction:               CLOSED
Tokenizer training / model training / probes:           CLOSED
```

This is the contract for `scripts/dry_run_english_scowl_coverage.py`. It plans and
implements a **local-only, aggregate-only** run and its **synthetic** tests. The
required Decision B review later approved the exact seven-count schema for one
canonical English run; that execution is recorded in
`docs/english_scowl_coverage_execution_2026-07-16.md`.

## Coverage is a diagnostic, not validation

This run measures **only** how well the approved English SCOWL word list *covers*
the normalized lexical tokens of English CALLHOME utterances. It answers "are
these tokens present in the approved English list?" — never "is this utterance
monolingual English?". Consequently it **cannot** and **does not**:

- set `is_validated` or produce a source-language validation decision;
- mark a row `clean`;
- decide condition eligibility or route a row to any condition;
- change, tune, expand, filter, or normalize the SCOWL lexicon using CALLHOME
  outcomes;
- feed CALLHOME into `CsCont`.

CALLHOME never feeds `CsCont`. Bangor remains untouched and `CsCont`-only. English
alone cannot safely claim monolinguality (with no Spanish lexicon, a Spanish word
that is also an English word would slip through), so this run reports coverage and
claims nothing about language identity. See
`docs/english_scowl_coverage_contract.md`.

## Canonical English population

- **Population** = every utterance parsed from every **direct** `*.cha` file in the
  one canonical, repository-relative directory
  `project_root()/data/raw/callhome/eng` (gitignored; local only).
- **Deterministic sorted** file order; traversal is **non-recursive** (`glob`, not
  `rglob`).
- The canonical English directory must be a real **non-symlink directory**, and
  every direct matching `*.cha` entry must be a **regular non-symlink file**.
  Any symlink, broken symlink, directory, or other non-regular matching entry
  aborts the complete run before parsing or resource loading; it is never
  followed or silently skipped. This prevents the English-only population
  boundary from being redirected into Spanish, Bangor, or another location.
- **No screening subset** and **no content-based language selection**: membership
  is defined solely by residing in the canonical English directory.
- **Every parsed utterance is included.** Utterances with no retained lexical
  tokens are **counted** under `no_lexical_tokens`, never silently dropped.
- Spanish (`spa/`) and Bangor directories are **never opened**.

## Separate denominators

Two denominators are tracked and **never mixed**:

- **Utterance denominator** — `n_results` (the three outcome counts sum to it).
- **Token denominator** — `n_tokens_total` (`n_covered_total + n_uncovered_total`).

Version 1 prints **no percentages, rates, averages, samples, examples, or
distributions** — only the raw counts. Any ratio is computed by a human at review
time from the released counts.

## Exact output schema (seven scalar counts)

On success the runner prints exactly one JSON object with these seven integer
keys, in this order, followed by a single newline, to **stdout only**:

```text
n_results
outcome__all_covered
outcome__has_uncovered
outcome__no_lexical_tokens
n_tokens_total
n_covered_total
n_uncovered_total
```

This is exactly the flattened shape of the merged `EnglishCoverageSummary`
(`flatten_english_coverage_summary`). No source, file, conversation, speaker, row,
per-token, path, hash, notice, provenance, example, unknown-word, validation,
`clean`, condition, routing, tokenizer, or model field can appear. **All seven
counts remain CLOSED for real output** pending the Decision B per-output review.

## `k = 10` whole-bundle privacy guard (new project rule)

**`k = 10` is a new project decision adopted for this diagnostic. It is NOT drawn
from any pre-existing governance document.** No tracked rule (Decision B, the
CALLHOME ground rules, or the coverage contract) establishes any numeric
low-cardinality threshold; this plan introduces one, approved by the project for
this runner.

Before printing, the runner inspects all seven scalar counts:

- **zero is permitted** (a zero count singles out no one);
- every **positive** count must be **at least 10**;
- if **any** positive count is below 10, the runner withholds the **entire**
  numeric bundle, identifies **no** field, prints one fixed generic message to
  stderr, and exits nonzero. It prints no `<10`, no range, no partial totals, no
  percentages, and none of the remaining fields.

### Why whole-bundle, not per-cell

The counts are linked by two identities:

- the three outcome counts sum to `n_results`;
- `n_covered_total + n_uncovered_total == n_tokens_total`.

Redacting a single small cell while showing the rest would let it be recovered by
subtraction. The guard is therefore **all-or-nothing**: release all seven, or
release none.

## Fixed exit semantics

```text
0  success: exactly one seven-key JSON object on stdout; nothing on stderr
2  opt-in missing, or a command-line usage failure
3  operational/input/invariant failure (fail closed)
4  privacy-guard suppression
```

The command exposes only `--allow-real-coverage-run` (plus built-in `-h/--help`).
**Without the opt-in it refuses before resolving any corpus or resource path**,
reads and writes nothing, and exits 2.

Three fixed, interpolation-free messages are used (opt-in required; operational
run aborted; aggregate withheld by the privacy guard). On any failure the runner
prints **no** numeric stdout, prints only the applicable fixed message to stderr,
and **writes no file**. No traceback, chained exception, path, filename, token,
identifier, count, or corpus-derived value is ever exposed; the CLI boundary
catches `Exception` (not `BaseException`).

## Atomic execution order

1. confirm the explicit opt-in;
2. resolve the canonical path;
3. validate the population exists and is non-empty;
4. load and prepare the approved resource once;
5. parse and evaluate the complete population (no file or utterance skipped);
6. construct and validate the complete summary;
7. reject an empty or zero-token summary;
8. apply the `k = 10` whole-bundle guard;
9. print the single JSON object.

Nothing numeric is printed before step 9. Any missing dependency, parse failure,
loader/evaluator failure, invalid/contradictory result, empty or zero-token
summary, or other ordinary exception aborts the **whole** run — **no partial
aggregate is ever emitted**.

## Differencing protections

- **No corpus-root override**; no filename, conversation, speaker, row, date,
  limit, sampling, or subset option. One canonical full-population run only.
- The count identities are handled by the whole-bundle guard, not per-cell
  redaction.
- **Any future population change requires a new design and a new Decision B
  review.** Repeated **externally released** runs over changed inputs remain
  prohibited without a new review. The approved execution record is the only
  externally released real run; no additional differencing surface is approved.

## Approved execution and what stays closed

- The exact seven-count schema passed its Decision B review for **one complete
  canonical English run**. Every positive cell cleared `k = 10`; the approved
  aggregate is recorded in
  `docs/english_scowl_coverage_execution_2026-07-16.md`.
- This is **not** standing authorization for a changed population, subset,
  additional output field, or repeated external release. Those remain separately
  gated and require a new Decision B review.
- Source-language validation, `clean` promotion, condition eligibility, condition
  routing, dataset construction, tokenizer training, model training, and probes
  all remain **closed**. CALLHOME never feeds `CsCont`; Bangor remains untouched
  and `CsCont`-only.

## Testing

`tests/test_dry_run_english_scowl_coverage.py` is **synthetic only**: temporary
CHAT fixtures and a synthetic temporary SCOWL bundle loaded through the real
loader boundary (`_approved_bundle_dir` monkeypatched). Injection uses internal
seams, never production CLI path arguments. No test touches real CALLHOME, Bangor,
the ignored SCOWL bundle, ignored resources, the network, or private logs. The
tests pin: default refusal before any resolution/loading; the CLI exposing only
the opt-in plus help; the fixed canonical path with no override; deterministic
sorted, non-recursive traversal; Spanish/Bangor never opened; all three outcomes
counted with `no_lexical_tokens` retained; fail-closed operational aborts (missing
/empty directory, zero utterances, zero tokens, one parse failure, loader and
evaluator failures) with no partial aggregate; the guard rejecting bad
types/booleans/negatives/missing-or-extra-keys/inconsistent complements; every
positive scalar `1`–`9` suppressing the whole bundle without revealing the field
or any number; success only when every positive count is at least `10`; success
being exactly one seven-key JSON object plus one newline; and no transcript-shaped
secret appearing in stdout, stderr, exceptions, or the returned aggregate.
