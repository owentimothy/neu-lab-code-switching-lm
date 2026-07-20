# Spanish Direct Hunspell Coverage Adapter Contract

## Status

```text
RLA-ES flat surface-form generation:                 STOP / CARRIED FORWARD
Direct local Hunspell fallback direction:            APPROVED FOR SYNTHETIC ADAPTER
Language-neutral coverage arithmetic:                SHARED WITH ENGLISH
Synthetic injected-checker implementation:           IMPLEMENTED IN THIS BRANCH
Offline PIPE_STREAM checker core:                    IMPLEMENTED WITH FAKE TRANSPORT
Reviewed PIPE_STREAM invocation mode:                REPRESENTED IN CODE
Concrete RLA-ES loader or bundle:                     CLOSED
Concrete subprocess/container transport:             CLOSED
Real CALLHOME or Bangor access:                       CLOSED
Real aggregate Spanish coverage run:                 CLOSED
Validation, clean promotion, or routing:              CLOSED
Corpus construction, tokenizer, or model training:   CLOSED
```

This contract defines a synthetic-only software boundary. It does not acquire,
extract, preserve, load, or inspect RLA-ES. It does not launch Hunspell, Docker,
or another process. It does not read CALLHOME, Bangor, an ignored resource, a
private log, or a generated output.

## Plain-Language Purpose

The failed flat-list attempt taught us that RLA-ES must retain its real Hunspell
semantics. The next coverage mechanism will eventually ask a pinned local
Hunspell checker whether each already-normalized token is recognized.

This branch implements only the safe middle layer:

```text
already-normalized invented tokens
        ↓ immutable tuple
injected synthetic checker
        ↓ exactly one Boolean per token
shared language-neutral arithmetic
        ↓
four content-free result fields
        ↓
corpus-level aggregate counts
```

The adapter knows nothing about a dictionary path, archive, license file,
container, corpus row, speaker, condition, or validation state. That separation
allows the token-to-Boolean contract to be reviewed before any real token crosses
a process boundary.

## Public API

```python
class SpanishHunspellChecker(Protocol):
    def check_tokens(
        self,
        normalized_tokens: tuple[str, ...],
    ) -> Sequence[bool]: ...


class SpanishHunspellCoverageEvaluator:
    def __init__(self, checker: SpanishHunspellChecker) -> None: ...

    def evaluate_tokens(
        self,
        normalized_tokens: Sequence[str],
    ) -> SpanishHunspellCoverageResult: ...


def compute_spanish_hunspell_coverage(
    normalized_tokens: Sequence[str],
    *,
    checker: SpanishHunspellChecker,
) -> SpanishHunspellCoverageResult: ...
```

The reusable evaluator and the one-shot function have identical semantics. The
checker receives an immutable tuple so it cannot change the caller's sequence.
The result never retains or returns a token.

## Result Type

```python
@dataclass(frozen=True)
class SpanishHunspellCoverageResult:
    outcome: str
    n_tokens: int
    n_covered: int
    n_uncovered: int
```

Fixed outcomes, in stable order:

```text
all_covered
has_uncovered
no_lexical_tokens
```

The result has no text, token, accepted/rejected list, path, resource identity,
hash, provenance, free-form note, source label, identifier, `is_validated`,
`clean`, condition, or routing field.

Coverage is not source-language validation. An RLA-ES match does not prove that a
token or utterance is monolingual Spanish, and an uncovered token is not proof of
English or code-switching.

## Normalization Ownership

The adapter normalizes nothing.

The future local dry-run caller owns token extraction and normalization through
the already-tracked CALLHOME normalization policy. The future concrete checker
must receive those tokens verbatim. The adapter rejects structurally unsafe
inputs but never changes case, accents, punctuation, or Unicode composition.

Synthetic tests prove the absence of hidden normalization by sending a
case-different invented token and observing that the checker receives it
unchanged.

## Input and Transport Safety

Accepted token input must be a sequence of strings. Each token must be non-empty
and contain no whitespace, NUL, or other ASCII control character. These are
transport-safety checks, not lexical filters. A structurally invalid input fails
before the checker is called.

The adapter passes one immutable tuple to `check_tokens`. The checker must return
one exact Boolean per input token in the same order.

It fails closed if the dependency:

- is absent or does not provide a callable `check_tokens` method;
- raises an operational exception;
- returns a string, bytes, generator, or another non-sequence;
- returns the wrong number of decisions; or
- returns anything other than exact `bool` values.

Dependency exceptions are replaced with fixed text. A token, path, subprocess
message, resource value, or tool diagnostic cannot enter the public exception.

An empty token sequence produces `no_lexical_tokens` without invoking the
checker, because no membership decision is required.

## Shared English/Spanish Arithmetic

`src/cslm/data/lexical_coverage.py` now owns:

- the ordered three-outcome vocabulary;
- the exact result arithmetic;
- count/outcome invariants; and
- conversion from one Boolean per token to content-free fields.

English SCOWL set membership and Spanish Hunspell decisions both use this same
function. Resource access differs, but the meaning of `n_tokens`, `n_covered`,
`n_uncovered`, and the three outcomes cannot drift by language.

The existing English public API and result type remain unchanged.

## Aggregate Diagnostics

The synthetic aggregate module exposes:

```text
n_results
results_by_outcome:
  all_covered
  has_uncovered
  no_lexical_tokens
n_tokens_total
n_covered_total
n_uncovered_total
```

It also provides one stable flattened scalar row. There is no source, file,
conversation, speaker, row, identifier, token, or per-token breakdown.

These Spanish aggregate fields have not yet received their real-output privacy
approval. Any future result computed over real CALLHOME remains local and
uncommitted until that separate review passes.

## Synthetic Tests

Ordinary tests use invented `syn_*` tokens and in-memory fake checkers only. They
cover:

- all-covered, partly uncovered, and empty outcomes;
- unchanged token handoff and immutable tuple input;
- no dependency call for empty input;
- rejection of invalid token structures;
- unavailable and failing dependencies;
- wrong-length and non-Boolean responses;
- fixed, token-free exceptions;
- hidden checker state in evaluator `repr`;
- the exact four result fields;
- frozen results and evaluators;
- absence of validation, clean, condition, routing, corpus, resource, and process
  symbols;
- aggregate totals and stable outcome ordering; and
- defensive rejection of mutated inconsistent results.

No ordinary test starts Docker, launches Hunspell, downloads RLA-ES, or accesses
CALLHOME, Bangor, an ignored resource, or a private log.

## Future Concrete Local Checker Gate

The offline checker core is now implemented with a **fake transport**:
`src/cslm/data/hunspell_pipe_stream.py` owns the shared strict PIPE_STREAM parser,
the defensive limits, batching, and `build_pipe_stream_stdin`; and
`src/cslm/data/spanish_hunspell_pipe_checker.py` implements the `check_tokens`
boundary over an injected `PipeStreamTransport`.  The reviewed `PIPE_STREAM`
invocation mode is therefore now represented in code.  **Real bounded
subprocess/Docker transport wiring remains CLOSED**, and the **real aggregate
Spanish coverage run remains CLOSED**; coverage remains descriptive only and cannot
validate, clean, promote, or route rows.  A separate design and execution branch
must still resolve:

1. a revised private bundle layout that preserves the original `es.oxt`,
   `es.dic`, `es.aff`, all required notices, and deterministic provenance without
   claiming a generated surface list;
2. exact local bundle loading and integrity checks;
3. the pinned offline container command and Hunspell invocation mode;
4. batch boundaries, ordering, duplicate-token behavior, timeout, and maximum
   input size;
5. content-free handling of process exit codes, stderr, malformed output, and
   partial output;
6. proof with invented Spanish-like `.dic`/`.aff` fixtures, including repeated
   bases and continuation rules; and
7. safe cleanup of every token-bearing temporary stream.

That checker must implement this branch's `check_tokens` contract. The adapter
must not be changed in response to CALLHOME coverage outcomes.

## Later Aggregate-Only CALLHOME Connection

After the concrete checker and exact output schema are separately approved, a
future local runner may:

1. load and verify the revised private RLA-ES bundle;
2. construct the pinned local/offline checker;
3. parse one CALLHOME utterance locally;
4. extract and normalize lexical tokens through the shared policy;
5. call `SpanishHunspellCoverageEvaluator.evaluate_tokens`;
6. discard token-bearing checker input/output after each bounded batch;
7. retain per-row results locally only long enough to aggregate; and
8. print only the separately approved corpus-level summary.

The runner may not mark a row validated or clean, route a condition, inspect
Bangor, or change RLA-ES behavior based on coverage.

## Gates That Remain Closed

This branch does not approve:

- acquisition or placement of a revised RLA-ES bundle;
- a concrete subprocess, Docker, or Hunspell checker;
- CALLHOME or Bangor access;
- real Spanish aggregate output;
- comparison-driven changes to the checker or lexicon;
- source-language validation;
- `validated` or `clean` promotion;
- condition routing or corpus construction;
- corpus freezing, tokenizer training, model training, or probes; or
- public redistribution of RLA-ES or any derivative.

## Final Gate Result

```text
SPANISH DIRECT HUNSPELL ADAPTER DESIGN PASS:
the adapter accepts only already-normalized tokens, delegates private membership
decisions through one injected immutable interface, shares coverage arithmetic
with English, returns counts only, aggregates at corpus level only, and fails
closed on invalid input or dependency behavior. Real resource/process/corpus
execution remains closed.
```
