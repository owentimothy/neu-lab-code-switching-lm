# Direct-Hunspell Per-Token Protocol Parity — Phase A and Phase B

## Status

```text
Per-token Hunspell candidate viability:               UNRESOLVED
Phase A observation infrastructure:                   IMPLEMENTED (this branch)
Phase A live-execution wiring:                        IMPLEMENTED / ENABLED (opt-in only)
Live pinned-Hunspell Phase A execution:               CORRECTED EXECUTION COMPLETE (2026-07-20) — AGGREGATE OBSERVED
Response parser / marker enum:                        IMPLEMENTED OFFLINE / TESTED
Phase B live-execution wiring:                        IMPLEMENTED / ENABLED (opt-in only)
Live pinned-Hunspell Phase B execution:               NOT RUN
Candidate PASS / membership matching / mode choice:   NOT LIVE-EVALUATED (Phase B / human review)

RLA-ES acquisition / inspection:                      CLOSED
CALLHOME / Bangor access:                             CLOSED
Real Spanish coverage run:                            CLOSED
Validation / clean promotion / routing:               CLOSED
Corpus / tokenizer / model / probe work:              CLOSED
```

**Real candidate viability remains UNRESOLVED.** This branch adds the
synthetic, offline *observation infrastructure* and the Phase A live-execution
*wiring*. That wiring is now **enabled** (`_LIVE_PHASE_A_ENABLED = True`) but
**opt-in only**: execution still requires both the explicit `--allow-phase-a-run`
CLI opt-in and separate acquisition/execution authorization, and by default the CLI
still refuses before any Docker, network, filesystem-resource, or subprocess
activity. Phase A itself makes **no** `-a` or `-l` framing assumption. This branch
now also implements the separately approved Phase B parser and enabled live wiring.
The separate `--allow-phase-b-run` route is opt-in only while
`_LIVE_PHASE_B_ENABLED = True`; the default CLI still refuses before constructing
the live environment or reaching Docker, acquisition, or subprocess activity. Two
separately authorized Phase A executions occurred on 2026-07-20, and only their
fixed aggregate results were recorded. A read-only
audit found that the first invocation lacked Docker `--interactive`, so that first
execution is retained as historical evidence but is **transport-invalid for
protocol evidence**. After the tracked stdin-forwarding correction was reviewed,
verified, committed, and pushed, one corrected execution completed cleanly under
the same pins and limits (see both result sections below). The per-token protocol
remains **UNRESOLVED**: neither candidate has live Phase B PASS status and no mode
has been selected. Every further live execution remains separately authorized.

## Initial Phase A execution result (2026-07-20, transport-invalid aggregate)

One separately authorized Phase A execution was run once on 2026-07-20. Recorded
below are only the fixed protocol-neutral aggregates — no raw stdout, response
lines, lexical entries, corpus content, Docker logs, temporary paths, provenance,
private hashes, or personal paths.

The execution completed at the host process boundary, but it did not constitute a
valid token-level observation. The tracked `docker run` argument vector omitted
`--interactive`, which Docker requires to keep container standard input open.
Host-side `stdin_delivered` therefore established delivery to the Docker client,
not forwarding to Hunspell inside the container. The `PIPE_STREAM` 69-byte,
one-LF result is the fixed public startup heading, while complete
`SINGLE_TOKEN_LIST` silence cannot establish membership behavior. The unchanged
aggregate is retained below as historical execution evidence only; it cannot
support framing, membership, candidate PASS, selection, or Phase B.

```text
Process exit:                             0 (clean); exactly one aggregate JSON object; no stderr
hunspell_release:                         v1.7.3
hunspell_commit:                          c5f98152a274e25b5107101104bef632b83a0cc9  (public pinned upstream)
container_platform:                       linux/arm64
environment_identity_match:               true
offline_build:                            true
modes_compared:                           2
selected_mode_label:                      NONE
pipe_stream_observation_completed:        true
single_token_list_observation_completed:  true
candidate_observation_count:              2
no_real_resource_or_corpus_access:        true
```

Protocol-neutral candidate aggregates:

```text
PIPE_STREAM
  observation_completed             = true
  raw_stream_identical_across_runs  = true
  structural_summary_stable         = true
  total_bytes                       = 69
  total_lf_count                    = 1
  blank_line_count                  = 0
  nonempty_line_count               = 1
  max_stdout_bytes                  = 69
  max_stderr_bytes                  = 0
  max_batch_latency_ms              = 130

SINGLE_TOKEN_LIST
  observation_completed             = true
  raw_stream_identical_across_runs  = true
  structural_summary_stable         = true
  total_bytes                       = 0
  total_lf_count                    = 0
  blank_line_count                  = 0
  nonempty_line_count               = 0
  max_stdout_bytes                  = 0
  max_stderr_bytes                  = 0
  max_batch_latency_ms              = 139
```

These unchanged values are historical, protocol-neutral aggregates only. Because
container standard input was not attached, they establish no token-level framing,
membership, correctness, candidate PASS, or mode preference. Neither `PIPE_STREAM`
nor `SINGLE_TOKEN_LIST` has PASS status. At that historical gate, no parser contract,
marker enum, membership verdict, or mode selection had been approved; the selected
mode remains `NONE` and candidate viability remains **UNRESOLVED**. Phase B, real Spanish coverage,
validation, clean promotion, routing, dataset construction, tokenizer work, model
training, and probes remain **CLOSED**.

## Corrected Phase A execution result (2026-07-20, aggregate only)

After commit `9fe7bc879f423dac249369b1ec6a5c9291ec3777` added exactly one Docker
`--interactive` option to each candidate-container invocation, one separately
authorized corrected Phase A execution completed under the existing pins and
defensive limits. It exited `0` in approximately 23.1 seconds and emitted exactly
one aggregate JSON object with no reported stderr or additional stdout. A
post-execution audit confirmed a clean synchronized repository, zero remaining
Phase A temporary workspaces, and zero lingering containers from the pinned image.

Only the following fixed protocol-neutral aggregates were retained:

```text
Process exit:                             0 (clean); exactly one aggregate JSON object; no stderr
hunspell_release:                         v1.7.3
hunspell_commit:                          c5f98152a274e25b5107101104bef632b83a0cc9  (public pinned upstream)
container_platform:                       linux/arm64
environment_identity_match:               true
offline_build:                            true
modes_compared:                           2
selected_mode_label:                      NONE
pipe_stream_observation_completed:        true
single_token_list_observation_completed:  true
candidate_observation_count:              2
no_real_resource_or_corpus_access:        true
```

```text
PIPE_STREAM
  observation_completed             = true
  raw_stream_identical_across_runs  = true
  structural_summary_stable         = true
  total_bytes                       = 109
  total_lf_count                    = 21
  blank_line_count                  = 10
  nonempty_line_count               = 11
  max_stdout_bytes                  = 109
  max_stderr_bytes                  = 0
  max_batch_latency_ms              = 130

SINGLE_TOKEN_LIST
  observation_completed             = true
  raw_stream_identical_across_runs  = true
  structural_summary_stable         = true
  total_bytes                       = 8
  total_lf_count                    = 1
  blank_line_count                  = 0
  nonempty_line_count               = 1
  max_stdout_bytes                  = 8
  max_stderr_bytes                  = 0
  max_batch_latency_ms              = 132
```

The changed aggregates establish that the corrected transport no longer has the
first run's startup/EOF-only shape. Both repetitions were byte-identical and
structurally stable, with empty stderr under the limits. Phase A still does not
interpret a response line, map output to a token, assert membership, award
candidate PASS, or select a mode. The public aggregates are compatible with the
documented public protocol and invented fixture design, but that compatibility is
not a parser verdict. `selected_mode_label` remains `NONE`; the parser-contract
source diff and Phase B remain separate reviewed gates. Real Spanish coverage,
validation, clean promotion, routing, datasets, tokenizer work, model training,
and probes remain **CLOSED**.

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
membership-sequence matching, and unknown-marker rejection belong to **Phase B**
under the approved parser contract below.

## Two-phase design (with a hard human seam)

- **Phase A — observe.** Run pinned Hunspell 1.7.3 over bounded invented inputs;
  observe raw streams **internally only**; emit only the fixed aggregate schema
  below. No raw byte, line, token, marker, suggestion, path, or diagnostic is
  printed or committed.
- **Approval seam (completed).** A human reviewed the corrected aggregates and
  approved the explicit parser contract below as a source diff containing only
  public fixed protocol constants and fixed semantic labels.
- **Phase B — verify.** Only after approval: parser-specific fixtures verify one
  Boolean per token, order, duplicates, synchronisation, repeated records,
  continuation affixes, determinism, limits, and fail-closed behaviour.

Live Phase A execution is enabled in this branch (`_LIVE_PHASE_A_ENABLED` is
`True`) but opt-in only: the CLI refuses by default and reaches it only with
`--allow-phase-a-run`, and acquisition and execution remain separately authorized.
Two separately authorized Phase A executions occurred on 2026-07-20; the first was
transport-invalid and the corrected second execution produced the aggregate result
recorded above. Any further run remains separately authorized.

## Approved Phase B parser contract, offline implementation, and enabled wiring

The human approval seam was completed after review of the corrected Phase A
aggregate and the pinned public Hunspell 1.7.3 protocol. This section fixes the
Phase B parser contract using only public constants and semantic labels. The
contract is implemented in pure offline functions and tested only with invented
fixtures. Phase B wiring connects those functions to a separate injected
orchestration path that reuses the bounded runner and cleanup controls. It is
reached only through the explicit `--allow-phase-b-run` opt-in while
`_LIVE_PHASE_B_ENABLED = True`. Activation does not itself execute live Phase B,
acquire anything, access a real resource, select a mode, or open any downstream gate.

Public protocol sources:

- Hunspell v1.7.3 source:
  <https://github.com/hunspell/hunspell/blob/v1.7.3/src/tools/hunspell.cxx>
- Hunspell v1.7.3 version definition:
  <https://github.com/hunspell/hunspell/blob/v1.7.3/configure.ac>
- public Hunspell command manual:
  <https://manpages.debian.org/testing/hunspell/hunspell.1.en.html>

### Common input, output, and privacy contract

Input order and duplicates are preserved by ordinal position. Existing limits
remain unchanged: 256 UTF-8 bytes per token, 256 tokens per batch, 10,000 tokens
per request, 30 seconds per candidate process, 2 MiB stdout, 64 KiB stderr, and
300 seconds for pull and build controls. A token must be nonempty valid text with
no whitespace or control character. No token may enter argv, an environment
variable, a path, a log, an exception, or a public diagnostic.

Every candidate requires a zero process exit, empty stderr, complete stdin
delivery, completion within all limits, exact output cardinality, and confirmed
cleanup. Parsing is incremental and bounded. Raw response lines, original-word
echoes, roots, offsets, suggestions, morphology, and unexpected markers remain
internal only and are discarded immediately after validation. A public result may
contain only fixed semantic labels and aggregate non-reconstructive counts.

The minimum per-input internal result is its ordinal plus exactly one membership
label: `ACCEPTED` or `REJECTED`. No lexical string is returned with that result.

### `PIPE_STREAM` contract

`PIPE_STREAM` uses one normal, non-terse `hunspell -a` process per bounded batch.
Each validated token is sent internally as `^` followed by the token and one LF;
the public `^` guard prevents token text from being interpreted as an Ispell
command.

Before any token response, the parser requires this exact public heading followed
by exactly one LF:

```text
@(#) International Ispell Version 3.2.06 (but really Hunspell 1.7.3)
```

The heading is derived from the pinned public source and version definition. Its
encoded shape is 69 bytes and one LF. The corrected Phase A aggregate independently
matches that heading shape, but the public source—not execution output—defines the
constant.

After the heading, the parser requires exactly one response block per input token,
in order. A block contains exactly one recognized response record followed by
exactly one blank separator line. The public response-marker mapping is:

```text
*  -> ACCEPTED (direct dictionary acceptance)
+  -> ACCEPTED (affix-derived acceptance)
-  -> ACCEPTED (compound acceptance)
&  -> REJECTED (with suggestions)
#  -> REJECTED (without suggestions)
```

Accepted records must match their documented fixed shape. Rejected records must
match the documented delimiters and unsigned numeric fields. Any original-word
echo is compared internally with the current input token. For `&`, the declared
suggestion count must agree with the parsed suggestion field. Suggestions, roots,
and offsets are never returned or logged.

A heading mismatch, unknown marker, malformed numeric field, mismatched echo,
missing or extra record, missing or extra separator, premature EOF, invalid UTF-8,
unterminated line, response-cardinality mismatch, output overflow, timeout,
nonzero exit, nonempty stderr, incomplete input, or unconfirmed cleanup stops the
candidate with one fixed non-sensitive failure.

### `SINGLE_TOKEN_LIST` contract

`SINGLE_TOKEN_LIST` uses one separate `hunspell -l` process per validated token,
preserving the implemented process boundary. Each process receives exactly one
token followed by one LF.

With a zero exit, empty stderr, complete input, and confirmed cleanup:

- empty stdout maps to `ACCEPTED`;
- exactly one nonempty LF-terminated output line that internally matches the input
  token maps to `REJECTED`.

The one-process-per-token boundary is what makes silence unambiguous. A blank-only
line, more than one line, a missing final LF, a nonmatching or transformed echo, an
identification line, invalid UTF-8, output overflow, timeout, nonzero exit,
nonempty stderr, incomplete input, or unconfirmed cleanup stops the candidate with
one fixed non-sensitive failure. The matching echo is discarded immediately.

### Offline Phase B verification requirements

Implementation must begin with offline tests using invented fixtures only. The
matrix must cover every approved marker and membership mapping; the exact heading;
required separators; order and non-adjacent duplicates; valid and malformed
numeric fields; matching and mismatching internal echoes; missing, extra, partial,
and reordered records; premature EOF; invalid encoding; output overflow; timeout;
abnormal exit; cleanup failure; `-l` silence; one exact line; multiple lines; and
nonmatching output.

Tests must also prove that no token, echo, root, suggestion, morphology, raw line,
or unexpected marker can reach a returned error, stdout, stderr, log, or aggregate
report. Ordinary tests remain offline and may not access Docker, the network,
RLA-ES, CALLHOME, Bangor, ignored resources, corpora, or private logs.

### Phase B aggregate and candidate decision contract

The fixed Phase B report may contain, per candidate, only attempted/completed
booleans, invented-case and expected-membership match counts, exact-cardinality and
repetition-stability booleans, unknown-response count, cleanup-confirmed boolean,
and candidate-PASS boolean. It must retain `selected_mode_label = NONE` and
`no_real_resource_or_corpus_access = true`; it contains no per-token output.
Global fields also carry only the fixed public Hunspell identity, platform, derived
environment-identity and offline-build booleans, candidate counts, and assessments.

A candidate receives PASS only if every predeclared invented known-truth case is
classified correctly in order, duplicates are preserved, cardinality is exact,
repetitions are identical, all limits and cleanup checks succeed, and no unknown
or privacy-bearing output escapes.

- zero candidates PASS: stop;
- exactly one candidate PASS: report it for separate human review and selection;
- both candidates PASS: stop for human review without applying an automatic
  preference.

No result changes `selected_mode_label` until a separate explicit selection is
reviewed, implemented, verified, committed, and approved. Any live invented-fixture
Phase B execution requires its own authorization.

## Selectable modes

```text
PIPE_STREAM        candidate (offline parser implemented; live Phase B not run)
SINGLE_TOKEN_LIST  candidate (offline parser implemented; live Phase B not run)
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
real per-token response protocol remain unresolved; live Phase A wiring is enabled
but opt-in only. Two separately authorized Phase A executions occurred on
2026-07-20; the first was transport-invalid and the corrected second execution
produced the aggregate result recorded above. Any further run remains separately
authorized.

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

## Phase A live-execution wiring (implemented, enabled; opt-in only)

The live-execution wiring is implemented and enabled (`_LIVE_PHASE_A_ENABLED` is
`True`) but opt-in only. It is dependency-injected so offline tests drive the
orchestration with a fake environment; without `--allow-phase-a-run` the CLI
refuses **before** any Docker, network, filesystem-resource, or subprocess
activity, and acquisition and execution remain separately authorized.

For each separately authorized Phase A run, the live environment performs only the
approved Phase A responsibilities: acquire the
already-approved public pinned Hunspell source and verify it by SHA-256; safely
extract it and confirm the source layout and required build inputs are regular
non-symlink files; verify the pinned container identity by acquiring the platform
digest through a supervised, bounded `docker pull`; build Hunspell offline
(`--network none`) in a **supervised, cleanup-confirmed** container tracked by a
non-token-bearing `--cidfile`, followed by an installed-binary check; and create
only temporary invented `.dic`/`.aff` inputs from the existing invented fixture and
its known-by-construction query.

Each candidate runs **twice** as a logical repetition, and each repetition preserves
the invented input order: `PIPE_STREAM` runs **one supervised process per bounded
token batch**, while `SINGLE_TOKEN_LIST` runs **one separate supervised
`hunspell -l` process per input token**, sending exactly one token plus its newline
to each process — never in argv, an environment variable, a path, or an error. Each
candidate container now uses exactly one Docker `--interactive` option so the
already-bounded host input is forwarded to the container; no TTY is allocated.
Every foreground container and the `docker pull` are supervised through the bounded
transport (`Popen(..., start_new_session=True)`, fixed timeout, bounded output,
process-group SIGTERM → one-second grace → SIGKILL, checked `docker rm -f`, and
confirmed cidfile removal). The `docker pull` and the offline build each use a
**300-second** timeout, and each candidate process uses the **30-second** batch
timeout; none is raised automatically after a failure. Each per-process raw stdout
is summarised **separately** — outputs from different processes are never
concatenated before structural counting — and the public byte, LF, blank-line, and
nonempty-line totals are the **sums of the per-process summaries**. The two
repetitions are compared internally as ordered tuples (raw streams for identity,
per-process summaries for stability); ordered process boundaries stay internal; only
those totals, per-process maxima, and timing are kept; and all raw streams are
discarded before the summary.

Identity and offline-build success are **derived from the actual verified results**
— source SHA-256 identity, acquisition of the exact platform-digest image, and a
clean supervised network-disabled build with an installed-binary check — and carried
into the summary through a typed evidence value; the CLI accepts no caller-supplied
Boolean claims. Exact platform-digest acquisition is the approved container-identity
boundary; the in-container binary and library invocation (the `hunspell` path plus
`LD_LIBRARY_PATH`) remains an **empirical Phase A check** to be confirmed at
activation. The summary emits only the exact aggregate schema with
`selected_mode_label` = `NONE`. The temporary workspace, invented fixtures, archive,
installation, and cidfiles do not survive a successfully reported run; teardown is
attempted exactly once and a cleanup failure surfaces one fixed error.

Phase A **stops after the aggregate observations**. It returns no candidate PASS
verdict and performs no per-token parsing, membership-sequence inference, marker
classification, or banner/separator/suggestion interpretation. The pure Phase B
parser, assessment, and opt-in orchestration functions are a separate boundary
and are never called by Phase A. The Phase B CLI route refuses before live
environment construction by default; actual execution remains separately
authorized. Phase A does not recreate
the abandoned affix-generation parser — real pinned Hunspell interprets the invented
repeated-record and continuation-affix inputs. Acquisition-identity mismatch, build
failure, nonzero execution, timeout, output overflow, worker failure, and cleanup
failure each raise fixed, non-sensitive errors. Live Phase B execution has not run
and remains separately authorized.

## Approved Phase B PASS / STOP criteria (not yet evaluated)

A candidate can pass only in Phase B, after the approved parser contract, by
confirming an ordered, duplicate-preserving Boolean sequence, synchronisation,
correct deterministic repeated-record and continuation-affix membership, contained
suggestion/morphological output, honoured limits, and tripped fail-closed
conditions. At least one passing candidate is required; multiple passing candidates
stop for a reviewed selection; none stops the gate. No mode is selected
automatically.

## Next gate

Perform a read-only Phase B execution preflight. It must confirm the enabled flag,
default refusal, exact aggregate schema, derived identity/build/cleanup evidence,
offline test coverage, clean repository and PR state, public acquisition pins, and
fixed execution limits. It must not use Docker or the network, execute Phase B,
select a candidate, or access any real resource or corpus.

## Standing boundaries

Coverage remains descriptive evidence, not source-language validation. CALLHOME
never feeds `CsCont`; Bangor Miami remains `CsCont`-only. No RLA-ES acquisition,
loader use, real coverage run, validation, clean promotion, routing, dataset
construction, tokenizer, model, probe, or public-redistribution decision is opened
by this branch.
