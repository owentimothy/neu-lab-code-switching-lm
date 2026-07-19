# Direct-Hunspell Per-Token Protocol Parity — Phase A Infrastructure

## Status

```text
Per-token Hunspell response protocol:                 UNRESOLVED
Phase A observation infrastructure:                   IMPLEMENTED (this branch)
Live pinned-Hunspell Phase A execution:               NOT ENABLED / SEPARATELY AUTHORIZED
Response parser / marker enum:                        NOT DEFINED (Phase B, after review)
Candidate PASS / membership matching / mode choice:   DEFERRED (Phase B / human review)

RLA-ES acquisition / inspection:                      CLOSED
CALLHOME / Bangor access:                             CLOSED
Real Spanish coverage run:                            CLOSED
Validation / clean promotion / routing:               CLOSED
Corpus / tokenizer / model / probe work:              CLOSED
```

**The real per-token Hunspell protocol is UNRESOLVED.** This branch adds only the
synthetic, offline *observation infrastructure*. It does not run pinned Hunspell,
Docker, or the network; it does not implement or activate a response parser; and it
makes **no** `-a` or `-l` framing assumption. No Phase A execution has been
performed and no results are recorded here.

## Scope

Tracked additions:

```text
scripts/run_hunspell_per_token_parity.py
tests/test_run_hunspell_per_token_parity.py
docs/callhome_spanish_hunspell_per_token_parity.md
```

No existing tracked file is modified. Ordinary tests are offline (Tier 1 pure
functions, fixtures, and CLI; Tier 2 a local synthetic stub executable) and never
touch Docker, the network, RLA-ES, CALLHOME, Bangor, ignored resources, or private
logs.

## No framing assumption in Phase A

Phase A does **not**:

- equate raw output line count with input-token count;
- derive any "candidate passed" verdict from one-line-per-token behaviour;
- assume banners, separators, response blocks, or suggestion shapes.

Instead it reduces each raw output stream to protocol-neutral **whole-stream**
observations and records only observed execution facts. Candidate PASS,
membership-sequence matching, and unknown-marker rejection belong to **Phase B**,
after a parser contract is presented as a reviewed source diff and approved.

## Two-phase design (with a hard human seam)

- **Phase A — observe.** Run pinned Hunspell 1.7.3 over bounded invented inputs;
  observe raw streams **internally only**; emit only the fixed aggregate schema
  below. No raw byte, line, token, marker, suggestion, path, or diagnostic is
  printed or committed.
- **Approval seam (stop).** A human reviews the aggregates and, if viable, approves
  an explicit parser contract as a reviewed source diff containing only public
  fixed protocol constants and fixed semantic labels.
- **Phase B — verify.** Only after approval: parser-specific fixtures verify one
  Boolean per token, order, duplicates, synchronisation, repeated records,
  continuation affixes, determinism, limits, and fail-closed behaviour.

Live Phase A execution is gated off in this branch (`_LIVE_PHASE_A_ENABLED` is
`False`); enabling it is a separately authorized step.

## Selectable modes

```text
PIPE_STREAM        candidate (invocation only fixed; framing unobserved)
SINGLE_TOKEN_LIST  candidate (invocation only fixed; framing unobserved)
NONE               Phase A always reports NONE; a human selects afterwards
```

`BATCH_FILTER` is a documented negative baseline (it destroys order and
duplicates) and can never be a selected result.

## Protocol-neutral whole-stream observation

Per candidate mode, two independent invented runs are reduced to:

```text
observation_completed             execution finished within the limits
raw_stream_identical_across_runs  the two raw byte streams were identical
structural_summary_stable         the coarse whole-stream summary matched
total_bytes
total_lf_count
blank_line_count
nonempty_line_count
max_stdout_bytes
max_stderr_bytes
max_batch_latency_ms
```

These are coarse counts only. Raw bytes, lines, markers, and suggestions are never
exposed. There is no per-token segment count, no segment-to-input comparison, and
no truth-partition claim in Phase A.

## Fixed aggregate Phase A schema

```text
hunspell_release
hunspell_commit
container_platform
environment_identity_match
offline_build
modes_compared
selected_mode_label                          (always NONE)
pipe_stream_observation_completed
single_token_list_observation_completed
candidate_observation_count
candidate_observations:
  PIPE_STREAM / SINGLE_TOKEN_LIST:
    observation_completed
    raw_stream_identical_across_runs
    structural_summary_stable
    total_bytes
    total_lf_count
    blank_line_count
    nonempty_line_count
    max_stdout_bytes
    max_stderr_bytes
    max_batch_latency_ms
no_real_resource_or_corpus_access
```

There is no `candidate_passed` and no `passing_candidate_count`: Phase A never
asserts protocol viability. The summary reports only observed execution facts.
Transport protections are established by the offline test suite and by source/diff
review, not by a caller-constructed all-true evidence block.

## Defensive limits

```text
maximum UTF-8 bytes per token:            256      (policy)
maximum tokens per process batch:         256      (proposed ceiling; test synthetically)
maximum tokens per check_tokens request:  10000    (policy)
per-batch timeout:                        30 s     (proposed ceiling; test synthetically)
maximum captured stdout per batch:        2 MiB    (hard ceiling; terminate midstream)
maximum captured stderr per batch:        64 KiB   (hard ceiling; terminate midstream)
termination grace before SIGKILL:         1 s
```

Byte ceilings are enforced **while reading** via bounded concurrent drain workers,
never by capturing unboundedly and checking afterwards. Timeout, output caps, grace
period, and polling interval are validated as positive. No limit may be raised
automatically after a failed experiment.

## Bounded process supervision

- `subprocess.Popen` with an argument vector and `start_new_session=True`.
- **A normal child exit does not set the stop event.** The stdin writer and both
  drain workers finish naturally, reading stdout and stderr through EOF, bounded
  only by the original operational deadline; if workers do not finish by that
  deadline the run is classified and cleaned up as a bounded failure. The stop
  event is set immediately only for timeout, stdout/stderr overflow, worker
  failure, cancellation, an unexpected exception, or a thread-start failure.
- The **stdin writer worker** delivers the complete payload via a `memoryview`
  offset loop, advancing until every byte is written and then flushing; a zero,
  `None`, invalid, or incomplete write fails closed, and a BrokenPipe/OSError
  before supervised termination means incomplete delivery. `stdin_delivered`
  becomes true only after the full payload is written and flushed; empty stdin
  counts as delivered without writing. Incomplete delivery on an otherwise-normal
  exit (e.g. a child that closes stdin early) is a worker failure.
- Concurrent stdout/stderr **drain workers** keep neither pipe from deadlocking and
  enforce byte ceilings while reading; a read error before supervised termination
  is a worker failure, a stream close after termination is expected cleanup, and a
  failed worker is never marked completed.
- **`clean_exit` is computed only after the worker results are known** — return
  code zero, no timeout, no output-limit breach, every started worker completed and
  joined, and complete stdin delivery confirmed — and cleanup is invoked with that
  final classification. Container cleanup is never invoked before this
  classification.
- **Only successfully started workers are joined;** an unstarted thread is never
  joined. If starting any worker raises, the child process group is terminated,
  only started workers are joined, pipes are closed, abnormal cleanup runs, and the
  original failure becomes one fixed `ParityTransportError`.
- **Cancellation and unexpected exceptions** after launch perform teardown and
  cleanup; `KeyboardInterrupt`/`SystemExit` re-raise without subprocess data, and
  any other exception becomes one fixed `ParityTransportError`.
- Teardown, and therefore the cleanup callback, is **attempted exactly once**; an
  error during worker join or pipe closure cannot prevent the cleanup callback from
  running, and unconfirmed cleanup is recorded or surfaced as a fixed error.
- One common **operational deadline** bounds ordinary work; **termination grace may
  occur after** that deadline. Timeout, output caps, grace period, and polling
  interval are validated as positive.
- Fixed terminal states — `normal_exit`, `timeout`, `output_overflow`,
  `worker_failure` — plus a `forced_termination` flag for SIGKILL escalation.
  Errors carry no subprocess data.

## Integrated cleanup

A clean/abnormal-aware cleanup callback is part of the supervised lifecycle and is
told whether the foreground process ended cleanly.

- **Clean zero exit** under `docker run --rm`: the container removed itself, so
  `docker rm -f` is **not** run; only the non-token-bearing cidfile is removed and
  its removal is confirmed.
- **Abnormal completion** (timeout, cancellation, overflow, worker failure, nonzero
  exit, thread-start failure, or other): a surviving container is force-removed with
  a **checked** `docker rm -f` — argument vector, `DEVNULL` stdin/stdout/stderr,
  fixed timeout, validated return code — then the cidfile is removed and confirmed.
- A missing or unreadable cidfile on an abnormal exit, an empty id, a Docker
  removal launch failure/timeout/nonzero result, or an unremoved cidfile all **fail
  closed** — cleanup that cannot be confirmed is never silently swallowed.

The cidfile holds only the container identifier — never tokens, streams, resource
contents, or diagnostics. No Docker command runs in ordinary tests; Docker is
always stubbed and its output is discarded to `DEVNULL`, never captured or exposed.

Raw stdout and stderr are sensitive by discipline: reduced internally, never
printed, logged, returned in the summary, or embedded in an error. Phase A and the
real per-token response protocol remain unresolved, and live Phase A execution
remains disabled in this branch.

## Invented fixtures

The invented dictionary header is constructed from the record sequence, so it
equals the actual record count. The fixture provides independently interpretable
invented cases — unflagged base, prefix-, suffix-, and explicit cross-product forms,
repeated base records with distinct flags, derived forms whose acceptance
demonstrates repeated-record handling, and a two-step continuation-affix chain
(first and chained derived forms). The query and its known truth cover these
derived behaviours, include an ordered non-adjacent duplicate, and a fixed rejected
form. Repeated records and continuation affixes are valid Hunspell interpreted by
the real engine in Phase A; no restricted affix-directive parser is used, and this
gate does not run them.

## Future PASS / STOP criteria (recorded, not yet evaluated)

A candidate can pass only in Phase B, after the approved parser contract, by
confirming an ordered, duplicate-preserving Boolean sequence, synchronisation,
correct deterministic repeated-record and continuation-affix membership, contained
suggestion/morphological output, honoured limits, and tripped fail-closed
conditions. At least one passing candidate is required; multiple passing candidates
stop for a reviewed selection; none stops the gate. No mode is selected
automatically.

## Standing boundaries

Coverage remains descriptive evidence, not source-language validation. CALLHOME
never feeds `CsCont`; Bangor Miami remains `CsCont`-only. No RLA-ES acquisition,
loader use, real coverage run, validation, clean promotion, routing, dataset
construction, tokenizer, model, probe, or public-redistribution decision is opened
by this branch.
