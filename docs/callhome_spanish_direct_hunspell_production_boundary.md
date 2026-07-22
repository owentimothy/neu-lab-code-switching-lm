# CALLHOME Spanish Direct-Hunspell Production Boundary

## Status

```text
Docs-only design record:                              THIS RECORD (revision 3)
Production boundary design:                           PROPOSED, NOT APPROVED

Revised direct-runtime bundle + snapshot contract:    CLOSED
Pinned Hunspell installation + snapshot contract:     CLOSED
Pinned image local-inspection contract:               CLOSED
Production Spanish reader contract:                   PROPOSED; R-1/R-2 deferred to a
                                                      bounded reader-format preflight
First-run parser-warning policy:                      RESOLVED — fail closed
Population authorization:                             CLOSED
Execution authorization:                              CLOSED
Local human-visible output authorization:             CLOSED
Commit/publication authorization:                     CLOSED

Implementation of any handle, loader, snapshot, factory,
composer, reader, runner, inspection, or no-pull change: NOT AUTHORIZED
```

This record changes no code, no test, no script, no configuration, and no tracker.
It creates no bundle or snapshot, opens no resource, reads no corpus, runs no
process, and releases no output.

Revision 2 resolved four P2 findings from the second independent review: the
unspecified and mis-ordered local-image check; the mis-staged reader questions;
the inexact cleanup-evidence model; and the missing validation-to-mount binding.

Revision 3 resolves the two remaining findings from the third review: transport
cleanup confirmation was conflated with stream disposal, handle closure, and
snapshot deletion (P2, §7); and malformed/incomplete image-supervision outcomes
were absent from the explicit failure and test inventories (P3, §14 and §15). No
other design change was made.

Nothing here authorizes resource preparation, population selection, execution,
local viewing, printing, serialization, commit, or publication.

## Scope and Ownership

This record owns the **production boundary**: how the already-merged components
may be composed for a real run, what typed provenance must exist first, how that
provenance stays bound through to mount time, and which authorizations gate each
stage.

It does **not** re-decide the approved RLA-ES v2.9 resource identity
(`docs/callhome_spanish_rla_es_general_coverage_selection.md`), the deferred
regional locale decision (`docs/callhome_spanish_lexicon_locale_decision.md`),
the synthetic adapter contract
(`docs/spanish_direct_hunspell_coverage_contract.md`), or CALLHOME ground rules
(`docs/callhome_ground_rules.md`).

## Verified Current Code State

Established by read-only inspection at `769c7a52…`:

```text
src/cslm/data/spanish_hunspell_diagnostic.py
    run_spanish_hunspell_coverage_diagnostic(utterances, *, evaluator)
    SpanishLexicalCoverageAggregate / require_releasable_aggregate
    MINIMUM_RELEASABLE_POSITIVE_COUNT = 10; no default evaluator

src/cslm/data/spanish_hunspell_coverage.py       SpanishHunspellCoverageEvaluator(checker)
src/cslm/data/spanish_hunspell_pipe_checker.py   SpanishHunspellPipeChecker(transport)

src/cslm/data/hunspell_pipe_transport.py
    HunspellContainerPipeTransport(bundle_dir, install_dir, workspace_dir, ...)
    _validate_directory: absolute, canonical, non-symlink, existing directory
    _validate_installation: install/bin, install/bin/hunspell (executable), install/lib
    create_unique_control_directory: tempfile.mkdtemp(prefix="pipe-", dir=workspace_dir)
    CONTROL_OWNER_MARKER_NAME = ".pipe-stream-owner"   (mode 0o600, O_EXCL)
    CONTROL_CIDFILE_NAME      = "container.cid"        (owned by finalize_container)
    _release_control_directory: releases ONLY when cleanup state is CONFIRMED
    Interrupts cross unchanged, carrying one fixed pipe_stream_cleanup_status attribute

src/cslm/data/hunspell_container.py
    CONTAINER_REFERENCE = docker.io/library/buildpack-deps@sha256:a60c415b...
    CONTAINER_DICTIONARY_BASENAME = "es"   (fixed; not caller-overridable)
    inner argv: /opt/hunspell/bin/hunspell -d /bundle/es -a
    hardened prefix has --network none but NO --pull=never

src/cslm/data/hunspell_process_supervision.py    run_bounded / supervise / BoundedRun

src/cslm/data/callhome_chat.py
    parse_chat_file: opens with encoding="utf-8", hard-coded
    parse_chat_lines: leading-space/tab lines are DISCARDED with the warning
                      "unmerged continuation line"
```

Two Spanish aggregate shapes coexist: streaming `SpanishLexicalCoverageAggregate`
(PR #91) and list-based `SpanishHunspellCoverageSummary`.

---

# 1. Finding 1 — Supervised local-image inspection and correct ordering

## Observed

`_hardened_prefix` is digest-pinned and uses `--network none`, but has **no
`--pull=never`**; `--network none` constrains the container, not the daemon's
image resolution. Revision 1 additionally specified the availability check only
loosely and sequenced it after resource-handle creation, contradicting its own
early-failure requirement.

## Proposed operation — `inspect_pinned_image_locally(...)`

Proposed symbol; **does not exist**; not authorized for implementation.

Requirements:

1. runs **before** either governed loader;
2. runs **before** any corpus path is resolved or any file is opened;
3. inspects only the exact existing `CONTAINER_REFERENCE` constant;
4. performs **no pull** and **no registry access**;
5. executes through the existing bounded process-supervision layer
   (`run_bounded` / `supervise`) — **never** raw `subprocess.run`;
6. uses a fixed command shape with no caller-provided image, tag, or flag;
7. enforces an explicit timeout and explicit stdout/stderr byte limits;
8. discards all stdout and stderr after bounded capture;
9. returns only success, or raises **one fixed non-sensitive error**;
10. exposes no image name, digest, registry, daemon text, path, command, output,
    or exception text — in any message, `repr`, log, or attribute;
11. preserves exact `KeyboardInterrupt` / `SystemExit` identity, unwrapped and
    unchained;
12. treats timeout, stdout/stderr overflow, daemon error, nonzero exit, malformed
    supervision result, worker failure, or incomplete supervision as **one fixed
    failure**.

Structural command shape (descriptive only — **not authorized, not executed**):

```text
docker image inspect <exact pinned digest reference>
```

## Corrected execution ordering

```text
opt-in authorization check
        ↓
population / execution gate checks that require no path access
        ↓
bounded supervised local-image inspection
        ↓
governed resource snapshot loader        → ApprovedSpanishRlaEs
        ↓
governed pinned-installation loader      → ApprovedPinnedHunspellInstallation
        ↓
production runtime composition (time-of-use revalidation, §6)
        ↓
corpus population resolution and traversal
```

Image inspection **must precede** resource-handle creation and any corpus access.
Revision 1's ordering is superseded.

## Relationship to `--pull=never`

Both are required and are complementary, not redundant:

- **inspection** gives an early, controlled, pre-resource availability failure;
- **`--pull=never`** — a fixed invariant inside the shared `docker run` argv
  builder, non-overridable — prevents a later execution path from pulling despite
  a passing preflight (for example if the image is removed between preflight and
  run).

Precedent: the English SCOWL build records already use `--pull=never`
(`docs/callhome_english_scowl_operationalization_approval.md` §6).

## Required synthetic tests (not implemented here)

Exact inspection command shape; fixed pinned reference (no caller override);
bounded-supervisor use rather than raw subprocess; timeout; stdout overflow;
stderr overflow; nonzero exit; daemon failure; worker failure; cancellation
identity; invented-secret suppression across message/`repr`/attributes; **no
resource-loader call before successful inspection**; **no corpus resolution
before successful inspection**; and the fixed `--pull=never` present in the later
`docker run` argv.

---

# 2. Finding 2 — Resource and runtime provenance handles

## Observed

`HunspellContainerPipeTransport` validates **directory shape** only. Structural
checks are not provenance checks: any directory of the right shape passes.

Two distinct dependencies must be separately governed:

```text
Approved Spanish dictionary bundle        (what Hunspell reads)
Approved pinned Hunspell installation     (what executes)
```

**Neither exists.** Per
`docs/callhome_spanish_rla_es_bundle_execution_stop_2026-07-16.md`: bundle
promotion `NOT RUN`, pinned Hunspell build `NOT RUN`, target bundle absent before
and after; the prior flat surface-form preparation method was **refused**, so no
approved direct-runtime preparation method exists.

## Proposed typed handles

```text
ApprovedSpanishRlaEs                    [PROPOSED — does not exist]
ApprovedPinnedHunspellInstallation      [PROPOSED — does not exist]
```

Both must:

- be constructible **only** by their governed loaders, behind a private
  construction token (mirroring the reviewed `ApprovedEnglishScowl`);
- be checked by **exact type** (`type(x) is not ApprovedX`), never `isinstance`,
  so a forged subclass cannot masquerade as approved;
- carry or privately bind the approved identity;
- expose only the minimum path needed for composition;
- expose **no** entries, affix content, notices, hashes, provenance text, or
  arbitrary caller-selected paths, and hide all of it from `repr`;
- fail with **fixed pathless** errors;
- own a controlled verified snapshot for their whole lifetime (§6).

`ApprovedSpanishRlaEs` must prove the revised approved bundle layout, the notice
and provenance boundary, and dictionary/affix integrity — **without exposing any
value**.

`ApprovedPinnedHunspellInstallation` must prove the exact pinned release and
commit (`HUNSPELL_RELEASE = v1.7.3`, `HUNSPELL_COMMIT = c5f98152…`) and the
required installation layout, at least as strictly as `_validate_installation`.

---

# 3. Finding 3 — Production Spanish reader contract and question staging

## Observed defects in the scaffold

`src/cslm/data/callhome_chat.py` is a **synthetic parser scaffold**. Two defects
would corrupt the scientific denominator if reused unchanged:

1. **Hard-coded UTF-8.** `parse_chat_file` opens with `encoding="utf-8"`; its own
   docstring and `docs/callhome_format_audit.md` line 108 record LDC CALLHOME
   Spanish as ISO-8859-1. A UTF-8 read of ISO-8859-1 bytes either raises or
   silently mis-decodes accents, changing normalized tokens and therefore counts.
2. **Continuation lines are discarded.** A leading space/tab line appends the
   warning `"unmerged continuation line"` and is `continue`d — its **text is
   dropped**. In CHAT such lines carry the remainder of an utterance, so dropping
   them silently truncates utterances and understates `n_tokens_total`.

The unchanged scaffold is therefore **rejected for production execution**.

## Corrected staging of the three reader questions

### R-1 and R-2 — technical format determinations, not owner preferences

These are **factual questions about the authorized source format**, and revision 1
wrongly framed them as preference-based owner choices. They are re-staged to one
future bounded, read-only technical gate:

```text
CALLHOME Spanish reader-format preflight        [FUTURE GATE — not authorized here]
```

That preflight must determine, **without displaying transcript content**:

```text
R-1: What encoding contract is supported by the exact authorized Spanish source —
     fixed ISO-8859-1, CHAT @UTF8/header-derived, or another tracked rule?

R-2: What is the authoritative CHAT continuation-line joining behavior, including
     separator semantics and continuation attachment?
```

It may inspect public CHAT format documentation, tracked format and access
records, parser interfaces, and already-authorized metadata or structure-only
evidence. It must **not** inspect or reproduce transcript text.

```text
R-1 and R-2 block final production-reader design and implementation.
They are technical format determinations, not preference-based owner choices.
```

This document deliberately **does not choose** R-1 or R-2.

### R-3 — RESOLVED for the first controlled run

```text
First-run parser-warning policy: FAIL CLOSED ON EVERY PARSER WARNING
```

- any parser warning **aborts the entire run**;
- **no** file and **no** utterance is skipped;
- **no** partial aggregate is returned;
- **no** warning detail becomes human-visible;
- any future warning allowlist requires a **separate later design and
  authorization gate**.

R-3 is therefore removed from the unresolved, implementation-blocking decisions.
A permissive policy is **not** needed for the first implementation.

## Required production reader contract

| Aspect | Required contract |
|---|---|
| Encoding | Per the R-1 determination. Silent fallback and replacement characters are prohibited; a decode failure is fail-closed. |
| Continuation lines | Joined into the owning utterance before normalization per the R-2 determination; **never silently dropped**. |
| Tier inclusion | Main speaker tiers (`*`) only; header (`@`) and dependent (`%`) tiers excluded from coverage text. |
| Malformed lines | Fail closed for the whole run; no line skipped. |
| Parser warnings | **Fail closed on every warning** (R-3, settled). |
| Traversal | Deterministic, sorted, direct-file only over the authorized population. |
| Skipping | Prohibited — a failing file aborts the whole run. |
| Disclosure | No filename, conversation id, speaker id, transcript text, or row content in any error, log, or output. |
| Output | A **stream** of utterance-like objects satisfying `SpanishDiagnosticUtterance`; consumable one-shot; no list materialization. |
| Normalization | Unchanged — the reader must not tokenize or normalize; `lexical_tokens` remains the single source of truth. |
| Failure | Fixed message, no partial aggregate, no serialization. |

## Likely next bounded action

After this document passes review, the next bounded action is expected to be the
**read-only CALLHOME Spanish reader-format preflight for R-1 and R-2**, unless
another finding independently blocks it. That preflight is **identified, not
authorized**, by this record.

---

# 4. Finding 4 — Trusted resource-identity binding

`run_spanish_hunspell_coverage_diagnostic(...)` stamps fixed metadata
(`resource_id = "spanish_rla_es_v2_9_general"`,
`resource_role = "broad_pan_regional_lexical_coverage_only"`) while accepting any
structurally compatible evaluator, and never sees the resource. A mis-wired runner
would emit an authentic-looking but mislabeled aggregate.

The **production runtime composer** owns the binding — not the generic evaluator.
It must:

- accept **no** arbitrary evaluator;
- accept **no** caller-provided bundle path;
- accept **no** caller-provided installation path;
- accept only **live, exact-typed** approved handles;
- construct transport, checker, and evaluator **internally**;
- revalidate both time-of-use bindings immediately before argv construction (§6).

The merged `spanish_hunspell_diagnostic` module is unchanged: keeping policy and
filesystem ownership out of the generic evaluator preserves its synthetic
testability. **No plugin registry, no generalized resource framework, no
configuration-driven wiring.**

Required synthetic tests: forged handle type, duck-typed look-alike, raw path
string, and an externally-constructed evaluator are each rejected.

---

# 5. Finding 5 — One human-visible schema

```text
Sole candidate:  SpanishLexicalCoverageAggregate.to_dict()
Only after:      require_releasable_aggregate(...) returns successfully
                 AND local human-visible output authorization exists (§8)

SpanishHunspellCoverageSummary is NOT an authorized human-visible output
for the first controlled diagnostic.
```

Implementation-time controls: the runner imports only the streaming aggregate
path; the returned aggregate's **exact type** is checked; the exact top-level keys
and exact nested outcome keys are checked; the runner does **not** import
`cslm.data.spanish_hunspell_coverage_diagnostics` (enforced by a structural import
test); serialization cannot occur before the release guard; no alternative schema
may be printed or written.

Neither schema is deleted or modified by this docs-only record.

---

# 6. Validation-to-mount provenance binding (P2 correction)

## Problem

Exact typed handles and loader-time verification do **not** alone prove that the
same bytes are mounted later. A dictionary, affix file, executable, or library
could be replaced between validation and use. Revision 1 left the binding as
"verify earlier, then later mount a path", which is insufficient.

## Controlled verified snapshot

Each governed loader produces or adopts a **private, loader-owned runtime
snapshot**. The snapshot must:

- contain only the exact approved runtime files;
- live under a private controlled directory;
- reject symlinks and unexpected file types;
- be validated for layout, identity, and integrity **inside that snapshot**;
- become **read-only after validation**;
- expose **no caller-selectable path**;
- remain owned by the typed handle for the handle's full lifetime;
- be **mounted directly from the same validated snapshot**;
- **not** be copied again between validation and mount;
- be **revalidated immediately before** runtime composition and mount;
- be inaccessible to ordinary composition callers except through the exact typed
  handle;
- be deleted only after confirmed successful cleanup **and** handle closure;
- be **preserved** under the cleanup-evidence policy (§7) if safe provenance or
  cleanup cannot be confirmed.

```text
This protects against ordinary or accidental post-validation replacement.
It is not claimed to be a security boundary against a malicious same-user actor.
```

An alternative lease, file-descriptor, immutable-store, or revalidation design may
be substituted **only** if it provides an equally reviewable validation-to-use
binding.

## Runtime composer requirements

The composer must: accept only **live** exact typed handles; retrieve snapshot
paths **privately**; revalidate handle liveness and snapshot identity immediately
before argv construction; prevent any caller path substitution; mount exactly the
snapshot owned by the validated handle; refuse if the snapshot changed,
disappeared, became unexpectedly writable, or no longer matches the approved
identity; return **one fixed pathless failure**; and construct **no evaluator** if
either binding fails.

## Installation binding

`ApprovedPinnedHunspellInstallation` binds the executable, the library directory,
release/commit provenance, and the exact validated snapshot mounted at
`/opt/hunspell`. A structural executable check alone is insufficient.

## Resource binding

`ApprovedSpanishRlaEs` binds the exact approved `es.dic`, the exact approved
`es.aff`, required notices and the provenance boundary, the approved preparation
identity, and the exact validated snapshot mounted at `/bundle`. **Filename
equality alone is insufficient.**

## Required synthetic tests

Resource mutation after handle creation; installation mutation after handle
creation; file replacement; symlink substitution; snapshot deletion; permission
change; unexpected file addition; stale or closed handle; mounting only the path
privately bound to the exact handle; no evaluator construction after binding
failure; no path or digest disclosure.

---

# 7. Cleanup, teardown, and evidence-retention policy (P2 correction)

## Exact retained-evidence set

Revision 1 inaccurately said unconfirmed cleanup retains "a container identifier".
The exact possible set, established from
`src/cslm/data/hunspell_pipe_transport.py`:

```text
When cleanup is unconfirmed, retained non-corpus control evidence may contain:

1. the private control directory  (tempfile.mkdtemp(prefix="pipe-", dir=workspace_dir));
2. its fixed ownership marker     (".pipe-stream-owner", mode 0o600, created O_EXCL);
3. a cidfile                      ("container.cid"), ONLY if container creation
                                   reached that point.

No cidfile is guaranteed to exist.
```

A startup failure may occur **before** any cidfile exists. Consequently the design
**must not** assert that a container was removed whenever startup failed.

## Ownership determination

The existing transport **already owns** per-call retention correctly:
`_release_control_directory` returns early unless the recorded cleanup state is
`PIPE_STREAM_CLEANUP_CONFIRMED`, the cidfile belongs to `finalize_container` and
is never unlinked there, and a failed release restores the marker via `O_EXCL`.

What remains unowned is the **parent `workspace_dir`**, a caller-supplied
constructor input. Therefore the proposed runtime factory — not the merged
transport — must own conditional workspace preservation, and **unconditional
`finally` removal of the workspace is prohibited**, because it would destroy the
transport's preserved evidence.

## What transport cleanup confirmation does and does not establish

Transport cleanup confirmation is a **narrow, per-call** fact. It must never be
read as whole-run teardown.

```text
Transport cleanup confirmation establishes only that the supervised
process/container lifecycle and its per-call control-artifact cleanup have
completed safely enough for the bounded stdout result to cross to the approved
strict parser.

It does not establish that:
- bounded stdout has already been parsed or discarded;
- approved resource or installation handles have been closed;
- their governed snapshots have been deleted;
- all runtime material has completed final teardown.
```

**Transport-level cleanup and final runtime teardown are distinct stages.** Bounded
stdout may exist briefly after transport cleanup confirmation, and governed
snapshots remain live after it — by design, because later batches and the
still-running evaluator need them.

## Final teardown order

```text
1. transport completes process/container supervision;
2. transport cleanup is confirmed;
3. bounded stdout crosses only to the approved strict checker/parser;
4. raw stdout is parsed and discarded;
5. checker/evaluator/orchestration complete or fail;
6. approved resource and installation handles are closed;
7. governed snapshots are deleted only after:
   a. transport cleanup is confirmed;
   b. parsing no longer needs the stream;
   c. no live evaluator/runtime owner remains;
   d. snapshot provenance and closure remain confirmed;
8. parent workspace is removed only when no retained control evidence remains.
```

Rules that follow from this order:

- neither bounded stdout nor any snapshot may become human-visible at any stage;
- **no snapshot may be destroyed while a live runtime owner still needs it**;
- **snapshot deletion must not occur merely because one batch returned** with
  cleanup confirmed;
- all snapshots and workspace artifacts **must ultimately be deleted** after
  successful full-run completion and handle closure.

## Policy

**Per-call transport/control cleanup confirmed** — the per-call ephemeral control
artifacts (control directory, ownership marker, and cidfile if created) may be
removed and no recovery artifact from that call remains. This says nothing about
stream disposal, handle closure, snapshot deletion, or workspace teardown.

**Final teardown confirmed** — steps 3–8 above all completed: stdout parsed and
discarded, handles closed, snapshots deleted, workspace removed, and no retained
control evidence anywhere.

**Any stage unconfirmed** — preserve the minimum applicable recovery evidence and
**do not claim final teardown succeeded**:

```text
When transport cleanup, provenance, handle closure, snapshot deletion,
or workspace cleanup is unconfirmed, preserve the minimum applicable
recovery evidence and do not claim final teardown succeeded.
```

*Transport cleanup unconfirmed* — potentially preserve the private control
directory, the ownership marker, and the cidfile if it exists; **do not claim the
container was removed**.

*Snapshot or handle teardown unconfirmed* — potentially preserve the applicable
private governed snapshot and the fixed non-content control status needed for
recovery.

In **every** unconfirmed case: retained evidence is limited to non-corpus control
material; **never** preserve or expose tokens, transcript text, corpus
identifiers, raw stdout, raw stderr, aggregate output, lexical entries, or affix
content; the human-visible failure remains fixed and non-sensitive; **no retained
path or contents may be printed, logged, serialized, or placed in an exception**;
and a **separately reviewed recovery procedure** must exist before real execution.

Retained evidence may identify a potentially live container and is therefore
**sensitive operational metadata**, protected by the existing restrictive
directory boundary.

## Interrupt contract

- the exact original `KeyboardInterrupt` / `SystemExit` instance remains the
  **winning exception**;
- cleanup is attempted according to the existing lifecycle;
- **cleanup failure must not replace, wrap, or chain onto the cancellation**;
- a fixed internal cleanup status (the transport's existing
  `pipe_stream_cleanup_status`) may control **evidence retention only**;
- no cleanup detail becomes public.

## Required synthetic tests

**Lifecycle separation:** transport cleanup may be confirmed **before** parser
consumption; stdout is discarded **immediately after** strict parsing; snapshots
remain live until handle closure; snapshots are **not** deleted merely because a
batch cleanup completed; successful final teardown closes handles **before**
deleting snapshots; final workspace removal occurs **only after** no control
evidence remains; snapshot-deletion failure does **not** falsely report complete
teardown; handle-closure failure does **not** falsely report complete teardown; no
stream, path, snapshot identity, or cleanup detail becomes public.

**Retention:** unconfirmed cleanup **before** cidfile creation; unconfirmed cleanup
**after** cidfile creation; marker-only retained state; marker-plus-cidfile
retained state; confirmed cleanup deletes control artifacts; unconfirmed cleanup
preserves them;
retained path never appears in errors or output; interrupts retain exact identity
despite cleanup failure; **no false assertion that a container was removed**.

The recovery procedure itself is neither designed nor implemented here.

---

# 8. `/bundle/es` provenance invariant

- Regional locale selection **remains deferred** for validation, `validated`/
  `clean` status, condition eligibility, and routing.
- RLA-ES v2.9 general `es.oxt` is **already approved** as the resource identity for
  broad descriptive coverage **design**.
- `/bundle/es` is an **implementation/provenance binding**, not a new locale
  selection. No new regional decision is required for this descriptive diagnostic.
- **A matching filename does not prove identity**: `CONTAINER_DICTIONARY_BASENAME
  = "es"` selects whatever is mounted at `/bundle/es.dic` and `/bundle/es.aff`.
- The typed resource handle must prove that the mounted `es.dic` and `es.aff`
  derive from the approved general artifact **and** an approved direct-runtime
  preparation method, and that those exact bytes remain mounted (§6).

> This record does **not** claim the direct-runtime preparation method is approved.
> It is not.

---

# 9. Four separate authorization states

```text
1. Population authorization
   CLOSED — no Spanish CALLHOME population has been authorized for this run.
2. Execution authorization
   CLOSED.
3. Local human-visible output authorization
   CLOSED pending exact per-output review.
4. Commit/publication authorization
   CLOSED pending Decision B review of this exact aggregate category.
```

Decision B permits committing aggregate-only, non-transcript CALLHOME summaries
**in general**. It is **not** authorization to compute, view, print, serialize,
commit, or publish **this specific output**. Passing the `k = 10` guard is
**necessary but not sufficient**: it is a small-cell test, not an authorization.

---

# 10. Corrected architecture

```text
opt-in and closed-gate checks                        [runner, PROPOSED]
        ↓
bounded supervised local-image inspection            [inspect_pinned_image_locally, PROPOSED]
        ↓
governed resource snapshot loader                    [load_approved_spanish_rla_es, PROPOSED]
        ↓
ApprovedSpanishRlaEs live typed handle               [PROPOSED]
        ↓
governed installation snapshot loader                [load_approved_pinned_hunspell, PROPOSED]
        ↓
ApprovedPinnedHunspellInstallation live typed handle [PROPOSED]
        ↓
runtime composer revalidates both time-of-use bindings [PROPOSED]
        ↓
HunspellContainerPipeTransport with fixed --pull=never [EXISTING + PROPOSED flag]
        ↓
SpanishHunspellPipeChecker                           [EXISTING]
        ↓
SpanishHunspellCoverageEvaluator                     [EXISTING]
        ↓
authorized production Spanish utterance stream       [PROPOSED CONTRACT, §3]
        ↓
run_spanish_hunspell_coverage_diagnostic             [EXISTING]
        ↓
exact SpanishLexicalCoverageAggregate                [EXISTING]
        ↓
aggregate invariant validation                       [EXISTING]
        ↓
require_releasable_aggregate                         [EXISTING]
        ↓
local-output authorization check                     [CLOSED gate]
        ↓
to_dict()                                            [EXISTING]
        ↓
serialization or printing                            [runner, PROPOSED]
        ↓
separate commit/publication authorization            [CLOSED gate]
```

## Boundary table

| Boundary | Owner | Input | Output | Must not cross | Error behavior | Cleanup / retention | Authorization before activation |
|---|---|---|---|---|---|---|---|
| opt-in / gate checks | runner | flags, gate state | proceed | any path | fixed refusal | nothing opened | population + execution |
| image inspection | inspection op | pinned constant | success | image/digest/registry/daemon text/command/output | one fixed error; interrupts unchanged | none created | image contract |
| resource snapshot loader | loader | approved layout | live typed handle | entries, affix content, notices, hashes, provenance, paths | fixed pathless error | snapshot owned by handle | bundle + snapshot contract |
| installation snapshot loader | loader | approved layout | live typed handle | binary paths, build logs | fixed pathless error | snapshot owned by handle | installation + snapshot contract |
| composer | runtime factory | live typed handles only | evaluator | any caller path or evaluator | fixed pathless failure; no evaluator built | creates workspace; conditional preservation (§7) | all runtime contracts |
| transport | transport | dirs + limits | bounded stdout | argv, container id, stderr, control paths | fixed `ParityTransportError` | per-call; releases only when CONFIRMED | execution |
| checker | checker | raw stdout | one bool/token | raw bytes (discarded post-parse) | fixed message, cause dropped | n/a | — |
| evaluator | evaluator | bools | four counts | token values | fixed message | n/a | — |
| reader → orchestration | runner | authorized population | utterance stream | filenames, ids, transcript text | fixed message, no partial | file handles closed | population |
| orchestration | orchestration | counts | aggregate | utterances, tokens, ids | atomic; no partial aggregate | counters discarded | — |
| release guard | guard | aggregate | same aggregate | partial/redacted objects | fixed withheld error | none | — |
| output-authorization check | runner | aggregate in memory | permission | everything | fixed refusal; no mapping built | workspace policy §7 | local output |
| `to_dict()` → print | runner | aggregate | mapping | everything else | no traceback; no second attempt | — | local output |
| publication | human | mapping | committed record | — | — | — | commit/publication |

---

# 11. Production runner boundary

Proposed file (**does not exist**): `scripts/dry_run_spanish_hunspell_coverage.py`,
modeled on the merged precedent `scripts/dry_run_english_scowl_coverage.py`
(exit codes `0/2/3/4`, `PRIVACY_MIN_COUNT = 10`, refuse-by-default opt-in, fixed
interpolation-free messages).

The runner must: refuse **before resolving any path** unless the exact opt-in flag
is supplied, reading and writing nothing on that path; expose **no** corpus-root,
resource-root, path, glob, filename, subset, sample, limit, speaker, conversation,
filter, or output option; run the §1 ordering; resolve a fixed canonical
population only after population authorization exists; resolve only approved typed
handles; construct transport → checker → evaluator internally; use the §3 reader
contract; run the streaming orchestration; apply the release guard **before** any
serialization; check local-output authorization **before** calling `to_dict()`;
perform **no** file output; print nothing until every gate succeeds; use fixed exit
codes and fixed interpolation-free messages; never print exception text or a
traceback; never log paths, identifiers, pre-release counts, streams, or commands;
and **not** import or emit `SpanishHunspellCoverageSummary`.

---

# 12. Fixed population proposal (recommendation only)

Recommended future fixed canonical population: `data/raw/callhome/spa`, full
population with **no subsetting**, because it requires no invented sampling rule,
exposes no user-configurable selection surface, yields a stable reproducible
denominator, lowers small-cell risk under `k = 10`, and matches the English
precedent's single-population design.

```text
This is a design recommendation only.
Population authorization remains closed.
```

---

# 13. Release contract and corrected release ordering

## Ordering

```text
population authorization
        ↓
execution authorization
        ↓
controlled execution
        ↓
exact aggregate-type and invariant validation
        ↓
require_releasable_aggregate
        ↓
local human-visible output authorization
        ↓
to_dict()
        ↓
serialization / printing
        ↓
separate commit/publication authorization
```

- an aggregate **may exist privately in memory** after an authorized execution;
- **`to_dict()` must not be called before local-output authorization**;
- passing the release guard **does not** authorize viewing or serialization;
- denied output authorization produces **no mapping and no output**;
- an output-write failure must produce **no traceback, no alternative schema, and
  no second serialization attempt**.

## Candidate mapping fields

```text
schema_version                      (fixed metadata)
diagnostic_name                     (fixed metadata)
diagnostic_status                   (fixed metadata)
resource_id                         (fixed metadata)
resource_role                       (fixed metadata)
n_utterances_total                  (corpus-derived)
n_utterances_with_lexical_tokens    (corpus-derived)
results_by_outcome:
  all_covered                       (corpus-derived)
  has_uncovered                     (corpus-derived)
  no_lexical_tokens                 (corpus-derived)
n_tokens_total                      (corpus-derived)
n_covered_total                     (corpus-derived)
n_uncovered_total                   (corpus-derived)
```

Rules: every **positive** corpus-derived cell must be at least **10**; **zero is
allowed**; any positive value in **1–9 withholds the whole object**; invalid or
mutated aggregates are **withheld**; **no redaction, no rounding, no partial
schema** (the counts are mutually derivable by subtraction, so a redacted subset
would leak the suppressed cell); **no serialization before the guard**; fixed
metadata does not participate in the threshold; and **passing the guard authorizes
nothing** — viewing, printing, serialization, commit, and publication remain
separately closed.

---

# 14. Corrected failure inventory

Every category: fixed **non-sensitive** public outcome; original exception text
**never visible**; unless stated otherwise **no aggregate exists and nothing may
be serialized**.

## Authorization and preflight

| # | Condition | Public outcome | Retention | Aggregate? | Serialize? |
|---|---|---|---|---|---|
| 1 | No population authorization | fixed refusal | nothing created | No | No |
| 2 | No execution authorization | fixed refusal | nothing created | No | No |
| 3 | Denied local-output authorization | fixed refusal | per §7 | may exist in memory | **No** |
| 4 | `to_dict()` called before authorization | fixed error; treated as a defect | per §7 | may exist | No |
| 5 | Image-inspection timeout | fixed error | none created | No | No |
| 6 | Image-inspection stdout overflow | fixed error | none created | No | No |
| 7 | Image-inspection stderr overflow | fixed error | none created | No | No |
| 8 | Image-inspection nonzero exit | fixed error | none created | No | No |
| 9 | Docker daemon failure | fixed error | none created | No | No |
| 10 | Image unavailable locally | fixed error **before** resource/corpus access | none created | No | No |
| 11 | Attempted image pull | fixed error (failure, not recovery) | none created | No | No |
| 12 | **Image-inspection malformed supervision result** | fixed error; no result field disclosed | none created | No | No |
| 13 | **Image-inspection incomplete supervision** | fixed error; no result field disclosed | none created | No | No |
| 14 | Image-inspection cancellation | **exact interrupt instance propagates** | none created | No | No |

**Malformed supervision result** — the bounded supervisor returns a result whose
fields are invalid, contradictory, missing, wrong-typed, or outside the required
fixed invariants.

**Incomplete supervision** — the bounded result does not **positively confirm**
all required lifecycle facts, including as applicable: process completion; worker
completion; joined workers; timeout state; stdout-limit state; stderr-limit state;
cleanup-required state; cleanup-confirmed state; and nonnegative latency or the
equivalent structural requirements.

For either condition:

```text
Public outcome:    one fixed non-sensitive image-inspection failure
Output:            none
Resource access:   none
Corpus access:     none
Original exception or malformed fields:  not exposed
Interrupt behavior: exact KeyboardInterrupt/SystemExit identity remains unchanged
```

The inspection operation must require **positive confirmation of every expected
bounded-supervision invariant** rather than treating the absence of a failure flag
as success.

## Resource, runtime, and binding

| # | Condition | Public outcome | Retention | Aggregate? | Serialize? |
|---|---|---|---|---|---|
| 15 | Missing/invalid resource approval record | fixed error | nothing opened | No | No |
| 16 | Missing/invalid direct-runtime bundle | fixed error | nothing opened | No | No |
| 17 | Invalid dictionary/affix provenance | fixed error | nothing opened | No | No |
| 18 | Missing/invalid pinned installation | fixed error | nothing opened | No | No |
| 19 | **Resource mutation after handle creation** | fixed pathless failure; **no evaluator built** | snapshot preserved per §6/§7 | No | No |
| 20 | **Installation mutation after handle creation** | fixed pathless failure; **no evaluator built** | snapshot preserved | No | No |
| 21 | Workspace creation failure | fixed error | nothing to preserve | No | No |

## Reader

| # | Condition | Public outcome | Retention | Aggregate? | Serialize? |
|---|---|---|---|---|---|
| 22 | Empty authorized population | fixed error | files closed | No | No |
| 23 | Structurally invalid authorized population | fixed error | files closed | No | No |
| 24 | Reader encoding failure | fixed error | files closed | No | No |
| 25 | Continuation-line failure | fixed error | files closed | No | No |
| 26 | Malformed transcript structure | fixed error | files closed | No | No |
| 27 | Parser warning (fail-closed, R-3) | fixed error | files closed | No | No |
| 28 | Normalization failure | fixed error | files closed | No | No |

## Operational transport failures — each branches on **per-call** cleanup state

For every row below: **per-call transport/control cleanup confirmed** → that
call's ephemeral control artifacts may be removed and no recovery artifact from
that call remains; **cleanup unconfirmed** → preserve the control directory and
any marker/cidfile that exists, **do not claim the container was removed**,
recovery required. Both branches give the same fixed public failure, no aggregate,
and no serialization.

Neither branch asserts anything about stream disposal, handle closure, snapshot
deletion, or workspace teardown — those are the separate final-teardown stage
below (§7).

| # | Condition |
|---|---|
| 29 | Transport startup failure (**cidfile may not exist**) |
| 30 | Timeout |
| 31 | stdout / stderr overflow |
| 32 | stderr-policy failure |
| 33 | Broken pipe |
| 34 | Nonzero process exit |
| 35 | Worker failure |
| 36 | Malformed supervision result |
| 37 | Shutdown failure |

## Final teardown failures (distinct from per-call transport cleanup)

These occur **after** per-call transport cleanup may already have been confirmed.
For every row: fixed non-sensitive public failure; **complete teardown must not be
reported**; the applicable minimum recovery evidence is preserved per §7; no
retained path, snapshot identity, or cleanup detail is disclosed; no aggregate is
released and nothing further is serialized.

| # | Condition | Preserved evidence |
|---|---|---|
| 38 | Raw stdout disposal failure | no stream retained; fixed control status only |
| 39 | Resource-handle closure failure | applicable governed snapshot |
| 40 | Installation-handle closure failure | applicable governed snapshot |
| 41 | Resource-snapshot deletion failure | that snapshot |
| 42 | Installation-snapshot deletion failure | that snapshot |
| 43 | Final workspace removal failure | control directory and any marker/cidfile |

## Result, release, and cancellation

| # | Condition | Public outcome | Retention | Aggregate? | Serialize? |
|---|---|---|---|---|---|
| 44 | Malformed checker response | fixed error | per branch | No | No |
| 45 | Evaluator failure | fixed error | per branch | No | No |
| 46 | Aggregate mutation | fixed validation/withheld error | — | withheld | No |
| 47 | Unexpected schema or keys | fixed error | — | withheld | No |
| 48 | Low-count suppression (`1–9`) | fixed withheld message | — | exists, **withheld whole** | No |
| 49 | Output serialization/write failure | fixed error; **no traceback, no alternative schema, no retry** | — | exists | No further |
| 50 | `KeyboardInterrupt` | **exact instance propagates**, unwrapped, unchained | cleanup attempted; evidence per §7 | No | No |
| 51 | `SystemExit` | **exact instance propagates**, unwrapped, unchained | cleanup attempted; evidence per §7 | No | No |

An aggregate existing in memory is **never** by itself human-visible.

---

# 15. Corrected synthetic test plan

All tests use invented material and fakes only. **No test may touch a real
resource, corpus, Docker, Hunspell, or the network.**

**Image inspection:** exact command shape; fixed pinned reference; bounded
supervisor rather than raw subprocess; timeout; stdout overflow; stderr overflow;
nonzero exit; daemon failure; worker failure; cancellation identity;
invented-secret suppression; **no loader call before successful inspection**; **no
corpus resolution before successful inspection**; fixed `--pull=never` in the
later `docker run` argv.

**Image-supervision result integrity:** malformed result object; missing required
result field; wrong-typed Boolean or numeric field; contradictory lifecycle flags;
workers not joined; cleanup required but not confirmed; incomplete completion
state; negative or invalid latency if the result contract carries latency; fixed
error with **no result-field disclosure**; **no resource-loader invocation**; **no
corpus resolution**; **no fallback to `docker run`**; and **no retry or registry
access**. All fakes — no Docker and no network.

**Handles and snapshots:** exact typed resource handle; exact typed
pinned-installation handle; rejection of forged handles; rejection of arbitrary
paths; bundle layout and provenance checks; dictionary and affix integrity checks
**without exposing values**; installation provenance checks; resource mutation
after handle creation; installation mutation after handle creation; file
replacement; symlink substitution; snapshot deletion; permission change;
unexpected file addition; stale or closed handle; mount only the privately bound
snapshot; no evaluator construction after binding failure; no path or digest
disclosure.

**Reader:** encoding behavior per the R-1 determination; continuation-line
behavior per R-2; **fail-closed parser-warning policy (R-3)**; deterministic
full-population traversal; no skip, sample, or subset behavior.

**Composition and schema:** trusted resource-to-evaluator binding; exact aggregate
type; exact top-level keys; exact nested outcome keys; absence of any
`spanish_hunspell_coverage_diagnostics` import in the runner.

**Release ordering:** guard runs before `to_dict`, before JSON serialization,
before stdout; **`to_dict()` not called before local-output authorization**;
denied authorization yields no mapping and no output; no serialization after a
midstream failure; no serialization after a cleanup failure; output-write failure
produces no traceback, no alternative schema, and no retry.

**Cleanup evidence:** unconfirmed cleanup **before** cidfile creation; unconfirmed
cleanup **after** cidfile creation; marker-only retained state; marker-plus-cidfile
retained state; confirmed cleanup deletes control artifacts; unconfirmed cleanup
preserves them; retained path never appears in errors or output; interrupts retain
exact identity despite cleanup failure; no false "container removed" assertion.

**Cleanup-versus-teardown lifecycle:** transport cleanup may be confirmed **before**
parser consumption; stdout is discarded **immediately after** strict parsing;
snapshots remain live until handle closure; snapshots are **not** deleted merely
because a batch cleanup completed; successful final teardown closes handles
**before** deleting snapshots; final workspace removal occurs **only after** no
control evidence remains; snapshot-deletion failure does **not** falsely report
complete teardown; handle-closure failure does **not** falsely report complete
teardown; and no stream, path, snapshot identity, or cleanup detail becomes public.

**Behavior and privacy:** fixed exit codes and messages; invented-secret
disclosure resistance across `str`, `repr`, `args`, stdout, stderr; one-shot
streaming input; duplicate-token and repeated-utterance preservation; occurrence
counting; `k = 10` boundary at exactly 9 and exactly 10; exact
`KeyboardInterrupt` / `SystemExit` instance identity.

---

# 16. Stage-blocking matrix

| Decision or contract | Blocks design | Blocks implementation | Blocks execution | Blocks release |
|---|---|---|---|---|
| Corrected production boundary document (this record) | Yes, until independently reviewed | Yes | Yes | Yes |
| Revised direct-runtime bundle + snapshot contract | Final loader design | Production loader | Yes | Yes |
| Pinned installation + image + no-pull + snapshot contract | Final runtime-factory design | Production runtime factory | Yes | Yes |
| R-1 encoding determination | Final reader design | Production traversal | Yes | Yes |
| R-2 continuation determination | Final reader design | Production traversal | Yes | Yes |
| R-3 parser-warning policy | **No — resolved (fail closed)** | No | No | No |
| Recovery procedure for unconfirmed cleanup | No | No | Yes | Yes |
| CALLHOME population authorization | No | No | Yes | Yes |
| Execution authorization | No | No | Yes | Yes |
| Local human-visible output authorization | No | No | No | Yes |
| Commit/publication authorization | No | No | No | Yes |

Some contracts block **implementation** without blocking **design**; the four
authorization states block **execution** or **release** without blocking design or
implementation. They must not be collapsed into one gate.

---

# 17. Definitions of done

**Docs-only design correction (this record).** Complete when all findings are
addressed; runtime, snapshot, and reader contracts are specified with unresolved
items correctly staged; the four authorization states are separated; the corrected
architecture, ordering, failure inventory, release flow, cleanup-evidence policy,
and test plan are complete; and independent review returns no blocking findings.

**Reader-format preflight gate.** Complete when R-1 and R-2 are determined from
format and access evidence **without displaying transcript content**, and the
determination is independently reviewed.

**Owner-decision gate.** Complete when the owner decides — **not necessarily all
at once**: (1) whether to authorize a revised direct-runtime bundle preparation
and snapshot path; (2) whether to authorize the pinned installation, image, and
snapshot provisioning contract; later (3) which fixed CALLHOME population may
execute; later (4) whether the exact output may become human-visible or be
committed. Decisions 1–2 (with R-1/R-2) unblock implementation; 3 gates execution;
4 gates release.

**Bounded implementation gate.** Complete when separately authorized files are
implemented, tested, independently reviewed, merged, and synchronized. **It still
performs no real resource or corpus execution.**

**First controlled real diagnostic.** Complete when resource, runtime, reader,
population, execution, and output gates are all approved and only the approved
aggregate mapping becomes visible — with no row validated, promoted, rejected,
routed, split, or frozen.

---

# 18. Findings disposition

### Finding 1 — Supervised local-image inspection and ordering

```text
Design correction:            Proposed inspect_pinned_image_locally(...) fully specified:
                              bounded supervisor, fixed command shape, explicit timeout and
                              stream limits, discarded output, one fixed pathless error,
                              exact interrupt identity. Ordering corrected so inspection
                              precedes both loaders and all corpus access. --pull=never
                              retained as a complementary fixed argv invariant.
Owner decision still required: Image provisioning/verification contract.
Blocks implementation:        Yes (runtime factory).
Blocks execution:             Yes.
Blocks release:               Yes.
```

### Finding 2 — Reader decisions and staging

```text
Design correction:            R-1 and R-2 reclassified as technical format determinations
                              and moved to a future bounded read-only reader-format
                              preflight; neither is chosen here. R-3 RESOLVED for the first
                              run as fail-closed on every parser warning, and removed from
                              the unresolved implementation-blocking decisions.
Owner decision still required: None for R-1/R-2 (technical evidence gate, not preference);
                              none for R-3 (settled).
Blocks implementation:        Yes, via R-1/R-2 evidence — not via owner preference.
Blocks execution:             Yes.
Blocks release:               Yes.
```

### Finding 3 — Exact cleanup-evidence model

```text
Design correction:            Retained set stated exactly (control directory, ownership
                              marker, cidfile only if creation was reached; no cidfile
                              guaranteed). Every operational transport failure now branches
                              on confirmed vs unconfirmed cleanup, and no row claims
                              container removal. Transport confirmed to already own per-call
                              retention; the runtime factory must not unconditionally delete
                              the parent workspace. Interrupt contract stated precisely.
Owner decision still required: A separately reviewed recovery procedure before execution.
Blocks implementation:        No (the transport already behaves correctly).
Blocks execution:             Yes (recovery procedure).
Blocks release:               Yes.
```

### Finding 4 — Validation-to-mount provenance binding

```text
Design correction:            Controlled verified snapshot owned by each typed handle:
                              validated in place, read-only after validation, never
                              re-copied, revalidated immediately before composition and
                              mount, mounted only from the same snapshot, deleted only after
                              confirmed cleanup and handle closure, preserved when
                              provenance or cleanup is unconfirmed. Composer revalidates
                              liveness and identity before argv construction and builds no
                              evaluator on binding failure. Explicitly not claimed as a
                              defense against a malicious same-user actor.
Owner decision still required: The snapshot contract is part of D-1 and D-2.
Blocks implementation:        Yes (both loaders and the composer).
Blocks execution:             Yes.
Blocks release:               Yes.
```

### Retained from revision 1 (accepted, unchanged)

Trusted resource-identity binding (composer-owned, no registry, merged
orchestration unchanged); one human-visible schema
(`SpanishLexicalCoverageAggregate.to_dict()` only, `SpanishHunspellCoverageSummary`
unauthorized); `/bundle/es` as a provenance binding rather than a new locale
decision; and the four separate closed authorization states.

---

# 19. Unresolved decisions

## Owner authorization decisions

```text
D-1  Revised direct-runtime RLA-ES bundle preparation, placement,
     and snapshot contract.                                    [blocks implementation]
D-2  Pinned Hunspell build + image provisioning/verification +
     snapshot contract.                                        [blocks implementation]
D-6  Fixed CALLHOME Spanish population authorization.          [blocks execution]
D-7  Execution authorization.                                  [blocks execution]
D-8  Local human-visible output authorization.                 [blocks release]
D-9  Commit/publication authorization.                         [blocks release]
```

Historical numbering is preserved: D-3 and D-4 are re-staged below, and D-5 is
resolved. No historical reference is silently altered.

## Unresolved technical reader-format evidence (not owner preferences)

```text
D-3 / R-1  Encoding contract for the authorized Spanish source.
D-4 / R-2  Authoritative CHAT continuation-line joining behavior.
```

Both are to be determined by the future bounded **CALLHOME Spanish reader-format
preflight**, without displaying transcript content.

## Resolved first-run safety policy

```text
D-5 / R-3  Parser-warning policy — RESOLVED: fail closed on every warning.
```

## Separately required before execution

```text
Recovery procedure for unconfirmed cleanup (§7).
```

---

# 20. Gates that remain closed

```text
implementation of any proposed handle, loader, snapshot, factory, composer,
reader, runner, inspection operation, or argv flag
real-resource inspection, preparation, snapshotting, or placement
real CALLHOME access or execution
validation
promotion
rejection
routing
corpus freezing
tokenizer training
model training
HPC
evaluation
probes
```

## Final Gate Result

```text
SPANISH DIRECT-HUNSPELL PRODUCTION BOUNDARY DESIGN — REVISION 3:
image availability is inspected under bounded supervision before any resource or
corpus access and is complemented by a fixed no-pull invariant; approved identity
is bound from validation through mount by loader-owned verified snapshots;
cleanup evidence is described exactly and preserved whenever cleanup is
unconfirmed; the reader's format questions are staged as technical determinations
while the first-run parser-warning policy is settled fail-closed; one schema is
releasable and only after both the release guard and a separate local-output
authorization; and no resource, corpus, process, or output gate is opened by this
record.
```
