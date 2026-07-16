# English SCOWL Coverage Diagnostic Contract

## 1. Status

```text
English SCOWL lexical coverage (synthetic + adapter):  IMPLEMENTED / OPEN
Shared normalization single-source-of-truth:            IMPLEMENTED / OPEN

Source-language validation:                             UNCHANGED / CLOSED
CALLHOME clean promotion / clean-row assignment:        CLOSED
Condition routing / dataset construction:               CLOSED
Spanish lexicon / locale selection:                     CLOSED
Real-data coverage run:                                 COMPLETE (one canonical English run)
Seven-count aggregate execution record:                 APPROVED (Decision B reviewed)
Tokenizer training / model training / probes:           CLOSED
```

This record is the contract for `src/cslm/data/english_scowl_coverage.py` and its
aggregate companion `src/cslm/data/english_scowl_coverage_diagnostics.py`. It
implements **one** capability: measuring how well the approved English SCOWL word
list *covers* an utterance's normalized lexical tokens. It opens nothing else.

## 2. Coverage is a diagnostic, not a verdict

The load-bearing distinction:

| | Source-language validation (`callhome_lexicon_validation`) | English SCOWL coverage (this module) |
|---|---|---|
| Question | "Is this utterance confidently monolingual English?" | "Are these tokens present in the approved English list?" |
| Needs the other language | **Yes** — the cross-language guard is essential | **No**, and it must not pretend to have one |
| Returns | `CallhomeSourceValidationDecision` (can set `is_validated=True`) | `EnglishCoverageResult` (cannot validate) |
| Can reach `clean` | Yes, via `combine_screening_and_validation` | **Never** |

English alone **cannot** safely claim monolinguality: with no Spanish lexicon,
a Spanish word that is also an English word would slip through. This module
therefore refuses the monolinguality claim and reports only coverage. It never
produces a validation decision, sets `is_validated`, yields `clean`, decides
condition eligibility, or routes a row.

## 3. Two layers

**Pure core — carries no approved-resource guarantee.**

```python
def compute_english_coverage(
    normalized_tokens: Sequence[str],
    *,
    normalized_lexicon: Set[str],
) -> EnglishCoverageResult
```

It **normalizes nothing** and **loads nothing**; it counts set membership only.
Both arguments must already be normalized by
`cslm.data.callhome_lexicon_normalization`. The `normalized_lexicon` argument is
trusted verbatim — it is **not** a proof of approval. Callers needing the
approved bundle must use the adapter below.

Fails closed on both sides. Tokens: a `str`/`bytes`/`bytearray` sequence or a
non-`str` element raises `EnglishCoverageInputError`. Lexicon: it must be a
non-empty set-like collection whose members are all non-empty strings — an empty
lexicon, a non-set, a non-string member, or an empty-string member raises
`EnglishCoverageLexiconError`. An empty lexicon is rejected rather than silently
reported as "everything uncovered", and lexicon error messages are fixed and
**never echo the offending value**.

**Production evaluator — requires the approved resource, normalizes once.**

```python
class EnglishScowlCoverageEvaluator:
    def __init__(self, approved_scowl: ApprovedEnglishScowl) -> None: ...
    def evaluate_utterance(self, utterance: CallhomeUtterance) -> EnglishCoverageResult: ...
```

Construction requires an **exact** `ApprovedEnglishScowl` — the type only
`load_approved_english_scowl()` can produce — so an arbitrary set, a `frozenset`,
or a forged subclass is rejected. **Construction performs the expensive work
exactly once:** it normalizes the approved entries and runs the full
prepared-lexicon validation a single time, storing the result as an immutable
exact `frozenset`. Each `evaluate_utterance` then calls the shared internal
counting core directly, so **per-utterance evaluation is proportional only to
that utterance's retained token count** — the lexicon is never re-normalized and
never re-scanned. This matters at the known real workload (~109,000 lexicon
entries × tens of thousands of utterances).

The evaluator is a frozen, slotted dataclass; its prepared lexicon is hidden from
`repr` (which is just `EnglishScowlCoverageEvaluator()`) and cannot be reassigned
after construction. It stores no path, raw provenance, hash, or lexical entry in
any representation, and **does not call the loader** — obtaining the
`ApprovedEnglishScowl` is the eventual local runner's explicit, separate
responsibility.

Internally the module separates three responsibilities so the membership-counting
logic lives in exactly one place: `_validate_prepared_lexicon` (the whole-set
check), `_count_coverage` (the shared counting core that assumes a validated
lexicon and validates only token structure), and the public
`compute_english_coverage` (validate the caller's lexicon, then delegate to the
core). The whole-set check's frequency differs by API: `compute_english_coverage`
runs it **once per call** (it validates whatever set the caller passes each time),
whereas `EnglishScowlCoverageEvaluator` runs it **once during construction** and
**never during per-utterance evaluation**.

## 4. One source of truth for normalization

`src/cslm/data/callhome_lexicon_normalization.py` now holds the sole copy of
`normalize_token`, `normalize_lexicon`, `lexical_tokens`, and `RESIDUE_TOKENS`
(extracted unchanged from the lexicon validator, which now imports them). Both
the validator and this coverage module apply the *identical* rule to tokens and
to lexicon entries, as `docs/callhome_lexicon_normalization_policy.md` requires.
The coverage adapter does not *silently* normalize transcript tokens — it calls
the same documented `lexical_tokens` the validator uses.

## 5. Content-free result

```python
@dataclass(frozen=True)
class EnglishCoverageResult:
    outcome: str        # all_covered | has_uncovered | no_lexical_tokens
    n_tokens: int
    n_covered: int
    n_uncovered: int
```

Exactly four fields — counts and one fixed label. There is deliberately **no**
`is_validated`, `clean`, condition, validation-method, validation-reason,
transcript text, token, path, or free-form note. The tokens themselves are never
stored, so the result cannot leak them.

Invariants are enforced at construction and mirrored in the aggregate
diagnostics' defensive re-check via one shared helper: counts must be **exact,
non-negative ints** (booleans and floats rejected), `n_covered + n_uncovered ==
n_tokens`, and the outcome must agree exactly with the counts —
`no_lexical_tokens` exactly when all counts are zero; `all_covered` only when
`n_tokens > 0`, `n_uncovered == 0`, and `n_covered == n_tokens`; `has_uncovered`
only when `n_tokens > 0` and `n_uncovered > 0`.

## 6. Aggregate schema (corpus-level, content-free)

`summarize_english_coverage_results(list[EnglishCoverageResult])` yields only:

```text
n_results
results_by_outcome:  {all_covered, has_uncovered, no_lexical_tokens}
n_tokens_total
n_covered_total
n_uncovered_total
```

The summary is **flat and corpus-level by design** — no source, file,
conversation, speaker, row, or per-token breakdown. A finely sliced count can
single out one row; keeping the schema coarse is a reconstructive-risk control,
not an omission.

## 7. Decision B privacy gate and approved execution

These aggregate categories were **new** — not among the examples originally
reviewed for commit in `docs/callhome_ground_rules.md`. The required separate
Decision B review was completed before the first real run. It approved exactly
the seven fixed scalar counts, over the complete canonical English population,
subject to the `k = 10` whole-bundle guard and the no-subsetting/no-differencing
rules in `docs/english_scowl_coverage_dry_run_plan.md`.

Exactly one authorized canonical English run was then completed. Its approved,
content-free result and citation/license record are preserved in
`docs/english_scowl_coverage_execution_2026-07-16.md`. This approval does **not**
cover per-row output, additional fields, changed populations, or repeated
external releases; each would require a new review.

## 8. What remains closed

The authorized coverage run did **not**: modify the local projection script;
run Bangor; produce a validation decision; promote a row to `validated` or
`clean`; route a condition; select a Spanish lexicon or locale; or change
tokenizer or training data. All CALLHOME rows stay `not_validated` and `clean`
stays 0. `CsCont` remains Bangor-only.

## 9. Testing

`tests/test_english_scowl_coverage.py` and
`tests/test_english_scowl_coverage_diagnostics.py` use synthetic tokens and
lexicons only. The production evaluator is exercised against a **synthetic
temporary bundle loaded through the real `load_approved_english_scowl()`** (its
`_approved_bundle_dir` monkeypatched, per the loader-test fixture pattern) — never
the real ignored bundle, and never any corpus. Tests pin: the three outcomes;
verbatim comparison with no hidden normalization; fail-closed input and lexicon
handling (including non-string/empty-string lexicon members, with no value
echoed); evaluator rejection of arbitrary sets and forged substitutes; a
**prepare-once** regression (one evaluator over several utterances calls both
`normalize_lexicon` and the whole-lexicon `_validate_prepared_lexicon` exactly
once, proven by counting monkeypatches); that the evaluator's prepared `_lexicon`
cannot be reassigned after construction; the strengthened result invariants for
every contradictory outcome/count combination, at construction and in the
aggregate re-check; the evaluator `repr` exposing no lexicon or entries; absence
of any validation/clean/condition/routing field; and that neither results nor
aggregates can carry input token strings.
