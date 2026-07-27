# CALLHOME Execution-Population Census — Implementation Design

> [!IMPORTANT]
> **Status: deferred, non-authoritative design**
>
> This document preserves the generalized Checkpoint A/B population-census
> architecture for possible later scaling, reusable tooling, multi-operator
> execution, publication workflows, or broader corpus support.
>
> It does **not** govern the minimum first-pilot CALLHOME census and is no longer
> on the critical path to the initial `CsCont − MonoCont` experiment.
>
> The first-pilot census will be governed by a separate, minimum-defensible
> census contract created and reviewed in a later gate.
>
> Nothing in this document currently authorizes implementation, corpus access,
> source approval, real census execution, strict-reader execution, condition
> construction, corpus freezing, tokenizer training, or model training.

**Preserved generalized-design status:** Design only. No implementation, no
tests, no script, no `.gitignore` change, no real corpus access, no
private-directory inspection, no census, no hashing of real files, no strict-reader
execution, no dataset construction. This document is an implementation-ready
contract for a **later, separately reviewed** synthetic-only implementation gate.

The eventual synthetic-only implementation is split into two normative checkpoints
(§1.4): **Checkpoint A** (a pure, filesystem-free deterministic core) and
**Checkpoint B** (the production/filesystem/publication boundary). This document
fixes the privacy, schema, ordering, identity, and collision behavior so that a
Checkpoint A implementer need invent none of it.

**Permission state:** Decision B (see `docs/callhome_ground_rules.md`) —
aggregate-only, non-transcript CALLHOME summaries *may* be committed with citation
notes; per-row records, conversation identifiers, filenames, and transcript-
bearing outputs remain blocked and stay local/gitignored. This design does **not**
assert Decision B has expanded, and does **not** claim G3 has approved any census
aggregate for commit.

---

## 0. Finding-closure map (fourteen review rounds)

**Round 1** (all closed):

| Finding | Resolution |
|---|---|
| P1 — authorization boundary bypassable through public API | §8 (nullary API + opaque capability + private test core), §17 |
| P2 — base directory purity not enforced | §9.2 |
| P2 — source-snapshot approval circular | §10 |
| P2 — population identity conflated with run/file identity | §11 |
| P2 — NFC serialization rewrites exact path | §12 |
| P2 — frozen output overwritable | §15 |
| P2 — incomplete schemas/types | §8.5, §16 |
| P3 — zero-byte duplicate boundary unspecified | §13.3 |

**Round 2** (this revision):

| Finding | Resolution |
|---|---|
| P2 — authorization-record bootstrap before `project_root()` undefined | §8.6 (`_bootstrap_repository_root`), §8.1 (ordered bootstrap + project-root equality), §17.1 |
| P2 — approved archive filenames / archive-directory membership not confined | §10.7 (basename rules + archive-directory purity + containment) |
| P2 — counts not bound to / reconciled with entries | §11.6 (counts in stable identity + mandatory reconciliation), §8.5, §16.4 |
| P2 — persisted schema ids / dataclasses / checksum mappings inconsistent | §8.5 (all types incl. `CallhomeExtractionProcedure`), §14.2, §16 (schema/version in every record; canonical vectors) |
| P2 — post-publication interruption / no-overwrite semantics underspecified | §15.2 (six-state machine), §15.3 (`publication_verification_required`) |
| P3 — Python-private sentinel described too strongly as security | §8.2, §17.3 (supported-interface authorization boundary, not adversarial isolation) |
| P3 — conversation-identity suffix removal not defined exactly | §10.5 (remove exactly the final `.cha`) |

**Round 3** (this revision — implementation-plan contract correction):

| Correction | Resolution |
|---|---|
| A — Checkpoint A/B boundary undefined; implementer would invent the pure/filesystem split | §1.4 (normative pure-core vs production/filesystem checkpoints; `.gitignore` deferred to B) |
| B — constants left as prose/examples | §8.7 (normative constants table; identity-participation clarified) |
| C — field predicates not enumerated per field | §8.8 (normative field-predicate table for every persisted/nested record) |
| D — source-member array ordering unspecified | §10.8 (canonical ascending UTF-8-byte ordering; noncanonical persisted order rejected) |
| E — ambiguous "duplicate normalized path identity" collision class; crossover under-defined | §13.1 (class removed), §13.4 (five exact classes + internal precedence), §13.5 (exact language-crossover), §9.1 (failure precedence) |
| F — record/error representation privacy not normative | §18.5 (`repr=False` + fixed redacted `__repr__`; error carries only a category; sentinel repr tests) |
| G — strict JSON persistence boundary not exact | §14.3 (BOM/NaN/Infinity/duplicate-key/surrogate rules; reserialize-and-compare; explicit mapping functions; `asdict` not the contract) |
| H — identity/reconciliation closure not stated as one contract | §11.7 (four checksum scopes; reconciliation points; tampered counts never accepted) |
| I — parsing/filesystem independence of the pure core not normative | §6.1 (import/dependency guard; no Path/handles/clock/Git in Checkpoint A) |
| J — factual error: `Path.stem` claimed to mishandle multi-dot `.cha` | §10.5 (corrected; `filename[:-4]` is the *chosen contract*, not a `Path.stem` bug) |

**Round 4** (this revision — focused Codex P1/P2 follow-up):

| Correction | Resolution |
|---|---|
| 1 — NFC/NFD/case-fold path collisions not language-namespaced | §13.4 (keys carry `language`; same-language requirement; duplicate-byte stays global; cross-language equivalents permitted), §12 (tests) |
| 2 — record-level invariants absent | §16.7 (normative invariant table for snapshots, candidate/approval, authorization, manifest, summary; Checkpoint B verification `ok` formula) |
| 3 — Checkpoint A/B contradictions (`Path.stem`/re-resolution/`_census_population_core`/cancellation in A) | §8.3 (seam = Checkpoint B), §10.5/§12/§20.2 (Path.stem is doc-only, not an A test), §20.2 (cancellation → B) |
| 4 — "production roots or paths" ambiguous vs logical-root strings | §1.4 (precise resolved-path exclusions), §6.1 (logical-root string constants explicitly allowed as identity values) |
| 5 — missing `## 9.` main heading | §9 heading restored before §9.1 |
| 6 — stale "test file uses only the private core" | §6 architecture, §20 intro (staged A-pure / B-filesystem roles; consistent across §§1.4, 6.1, 20.1, 20.2) |
| 9 — narrow cleanups | §6 (dependency set stated normative/complete), §14.3 (mapping functions guard field-set drift + pre-approval canonicalization) |

**Round 5** (this revision — final narrow Codex follow-up):

| Finding | Resolution |
|---|---|
| CHC-P2-04 — source-approval contract version not pinned | §16.7 (exact `contract_version == POPULATION_CONTRACT_VERSION`; no upgrade/fallback/normalize/caller-select; enters `source_approval_sha256`), §20.1 (test) |
| CHC-P2-05 — manifest snapshot-ID predicates not self-contained | §16.7 (intrinsic provider/language/`n_members`>0 predicates; per-language entry-count reconciliation independent of `counts`; `identity()` binding to approved snapshots; A/B enforcement boundaries), §11.4, §20.1/§20.2 (tests) |
| CHC-P2-06 — stable-identity verification result missing | §8.5 + §16.7 (`population_identity_matches` added; four-term `ok`; `membership_matches` ≠ identity; `repository_commit_compatible` informational), §11.4 (re-verification), §20.2 (tests) |

**Round 6** (this revision — final verification-semantics correction):

| Finding | Resolution |
|---|---|
| CHC-P2-07 — verification error-versus-result semantics conflict | §16.4 (strict acceptance loader: accepts or raises), §16.8 (new: strict loader vs private non-accepting verification inspector), §11.4 (Stage-R raise list vs returned Booleans), §16.7 (live authenticated snapshot-ID mismatch RETURNS `population_identity_matches==False`/`ok==False`, not raise; acceptance/construction still raise), §18.2 (two outcome classes), §20.2 (returned-result vs raise-without-record tests) |

**Round 7** (this revision — two-finding cleanup):

| Finding | Resolution |
|---|---|
| CHC-P2-08 — stale §14.2 blanket "recomputes each and asserts equality" | §14.2 (replaced with the two-boundary contract: strict acceptance raises; live Checkpoint B verification returns Booleans for evaluable manifest-file / entry / stable-identity / count mismatches; agrees with §11.4/§16.4/§16.7/§16.8/§18.2/§20.2) |
| CHC-P3-09 — inaccurate §18.2 "already-approved aggregate" wording | §18.2 (removed "already-approved"; `population_identity_sha256` is a privacy-safe local-only aggregate, disclosure governed by §19; a verification result grants no disclosure approval; record stays content-free) |

**Round 8** (this revision — bounded Checkpoint-A design-contract clarification, CHPA):

| Finding | Resolution |
|---|---|
| CHPA-P2-01 — pure-core API contract incomplete | §8.9 (single authoritative Checkpoint A API table: exact names, visibility, signatures, raise/pure/serialized-format-facing attributes, Checkpoint B consumers; Rule-A type-syntax resolution preserving the four-module import set), §8.10 (Checkpoint A type/record inventory) |
| CHPA-P2-02 — strict acceptance failure precedence incomplete | §16.9 (one total strict-loader pipeline — 22 stages at Round 8; **23 after Round 11** inserted the ordinary approved-inventory stage; one fixed category per stage; earliest-stage-wins; malformed/noncanonical serialization before checksum; fixed ordering/ordinals→collision→crossover→inventory→count→identity→manifest-checksum order) |
| CHPA-P2-03 — verification-record checkpoint ownership contradictory | §16.10 (inert `CallhomePopulationVerification` type defined in Checkpoint A; live inspector, producer, and behavioral tests owned by Checkpoint B; defining the inert type authorizes no Checkpoint B capability) |
| CHPA-P2-04 — record layout mechanics incomplete | §18.6 (uniform `@dataclass(frozen=True, slots=True)`, `eq=True`, `unsafe_hash=False`, `field(repr=False)` + fixed `__repr__`, `str` delegation, generated-hash policy; every record hashable), §8.5 (decorators updated) |
| CHPA-P2-05 — closed error constructor not fully specified | §18.7 (exact supported category set; unsupported / protected / empty / wrong-type → non-echoing `ValueError("unsupported_error_category")`; no recursion; chain-free supported boundary) |
| CHPA-P3-01 — non-blocking test-count planning estimate | §20.1 (≈170–220 collected cases retained as a PLANNING TARGET, not a Definition-of-Done count; behavioral coverage remains normative) |

**Round 9** (this revision — bounded Codex follow-up on the Round-8 clarification, CHPA-R2):

| Finding | Resolution |
|---|---|
| CHPA-R2-01 — bidirectional mapping API incomplete/ambiguous | §8.9 (complete typed converter inventory: 12 exactly-named `_<record>_to_mapping` / `_mapping_to_<record>` pairs with exact param/return types; generic `_<record>_…` forms removed), §14.3 (points to the §8.9 inventory; no second converter rule), §20.1 (per-pair round-trip tests) |
| CHPA-R2-02 — manifest approval binding not observable | §8.9 (`_build_population_manifest` now takes `source_approval: CallhomeSourceApproval` and derives snapshot IDs internally; no caller-supplied IDs; verifies `source_approval_sha256` + contract version), §16.7 (derive-not-compare binding), §16.9 (builder vs loader), §20.1/§20.2 (tests) |
| CHPA-R2-03 — structural decoding not separated from invariant construction | §16.9 (two-phase loader: Phase 1 raw-mapping structural + canonical byte comparison BEFORE any invariant-enforcing typed construction; Phase 2 ordered semantic construction/acceptance), §14.3 (two-phase steps), §16.7 (aggregate invariants are Phase-2), §8.9 (converter/constructor ownership) |
| CHPA-R2-04 — `__context__` guarantee overscoped | §18.7 (constructor controls own state + no explicit chaining; `__context__ is None` guaranteed only at project-controlled supported boundaries that raise outside any active handler; arbitrary third-party construction inside a handler is outside the guarantee), §20.1 (scoped tests) |

**Round 10** (this revision — final bounded Codex follow-up, CHPA-R3):

| Finding | Resolution |
|---|---|
| CHPA-R3-01 (constructor/converter/builder split) — PARTIAL | Round 10 established the three-layer validation-ownership contract: direct constructors and `_mapping_to_<record>` converters own **intrinsic/local** validation only (`schema_error`); named ordered builders (`_build_population_manifest`, `build_population_census_summary`) and strict loaders (`_load_<record>`) own aggregate and cross-record acceptance; direct construction alone never establishes accepted persisted status. §8.9, §16.7, §16.9 (Stage 12), §11.7, §20.1. **This closed the constructor-vs-builder split but did NOT yet make crossover / approved-inventory ownership consistent — that remained open and is completed in Round 11 (do not read Round 10 as fully closing CHPA-R3-01).** |

**Round 11** (this revision — crossover & approved-inventory ownership, CHPA-R3-01 completion):

| Finding | Resolution |
|---|---|
| CHPA-R3-01 (ownership assignment) — crossover and approved-inventory acceptance ownership inconsistent across §§8.9, 9.1, 16.7, 16.9, 20.1 | Assigned `_build_population_manifest` as authoritative owner of both **language crossover** (§13.5) and **ordinary approved-inventory membership comparison** (§10.3), derived from `source_approval.english/spanish.members`: §8.9 (builder owns both), §9.1 (census core delegates), §16.7 (applicability rule), §16.9 (stage 19 added; contextual stages 14/18/19 skipped when unevaluable), §10.3/§13.5, §20.1. **Round 11 assigned ownership but left three residual contradictions — §1.4 boundary wording, §9.1 in-step ordering position, and the collective strict-loader error inventory — which Round 12 removes; do not read Round 11 as achieving whole-document consistency by itself.** |

**Round 12** (this revision — checkpoint-boundary & per-loader error truthfulness, P2-01..03):

| Finding | Resolution |
|---|---|
| P2-01 — Checkpoint ownership contradiction (§1.4 deferred "approved-inventory comparison" to Checkpoint B while §8.9 assigns it to the pure builder) | §1.4 now lists **pure approved-inventory membership comparison + language-crossover detection over supplied values** in the Checkpoint A allowance and removes "approved-inventory comparison" from the Checkpoint B deferred list, reframing Checkpoint B as live acquisition / authentication / candidate-entry creation / builder invocation / publication only; §1.4 summary line adds §10.3 as a Checkpoint A contract. |
| P2-02 — §9.1 contradicts authoritative builder precedence (ordering listed after collision/crossover/inventory) | §9.1 step 8 and the failure-precedence block now use the exact §16.9 order — ordering/ordinals **before** collision → crossover → ordinary inventory → counts → identity → manifest-file checksum — and state §16.9 is the **sole** precedence contract. |
| P2-03 — strict-loader error inventory claims unavailable contextual failures | §8.9 replaces the collective loader raise-set with **exact per-loader** inventories; `_load_population_manifest` raises only self-contained `{schema_error, serialization_error, duplicate_identity, ordering_error, manifest_mismatch}` and **cannot** emit `language_crossover` or contextual `source_identity_mismatch` (stages 14/18/19 skipped); §20.1 adds per-loader error-inventory tests. **Round 12 pinned the per-loader §8.9 declarations but left three residual stale statements — a collision-first §25 precedence summary, an unreachable `source_identity_mismatch` on `_load_source_approval`, and collective contextual categories in §14.2 / §16 — which Round 13 removes; do not read Round 12 as achieving whole-document consistency by itself.** |

**Round 13** (this revision — residual precedence & loader-error contracts, P2-02-R1 / P2-03-R1 / P2-03-R2):

| Finding | Resolution |
|---|---|
| P2-02-R1 — stale collision-first precedence summary in §25 | §25 now states the aggregate precedence beginning with **ordering/ordinals** → collision → crossover → ordinary approved-inventory mismatch → counts → stable identity → manifest-file checksum (§§9.1, 16.9); the §0 Round-8 shorthand is likewise ordering-first; no complete precedence summary begins with collision. |
| P2-03-R1 — unreachable source-approval-loader error category | An invalid `archive_filename` basename / field grammar is an **intrinsic/local field defect → `schema_error`** (§8.8, §10.7), not a source-identity comparison. `_load_source_approval` now raises `{schema_error, serialization_error}` only; §8.9, §10.7, §18.2, §20.1 aligned. **Round 13 corrected the loader category but did not yet make the three approval-related boundaries fully consistent across §§8.9, 16.7, 17.1, 18.2, and 20.1; Round 14 closes that residual ownership issue.** |
| P2-03-R2 — stale contextual strict-loader categories in §14.2 and §16 | §14.2 and the general §16 loading prose now defer to the exact §8.9 per-loader inventories: context-free loading authenticates no approval/authorization, so `_load_population_manifest` raises **no** `source_identity_mismatch` (binding/inventory) and **no** `authorization_error`; its `manifest_mismatch` arises only from the self-contained `n_members` / counts / stable-identity / manifest-file-checksum predicates. **This did not yet establish the complete boundary-specific split for `_load_source_approval`, `_build_population_manifest`, and `_grant_capability`; that is the Round-14 correction below.** |

**Round 14** (this revision — boundary-specific approval error ownership, P2-03-R1-R2):

| Finding | Resolution |
|---|---|
| P2-03-R1-R2 — boundary-specific error ownership remained inconsistent across §§8.9, 16.7, 17.1, and 18.2 | §§8.9, 16.7, 18.2, and 20.1 now assign exact categories by boundary: `_load_source_approval` performs structural, canonical-serialization, and intrinsic/local validation only and raises `schema_error` / `serialization_error`; `_build_population_manifest` performs pure supplied-approval contract/checksum/source/inventory binding and raises `source_identity_mismatch` where assigned; `_grant_capability` performs Checkpoint B authorization/authentication/trusted-bootstrap/capability binding and every failure raises `authorization_error` under §17.1. The categories are non-substitutable. |

Round-1 through Round-13 findings are reopened only where Round-14 changes must stay
consistent with them. (The Round-1 through Round-13 rows above quote the wording each
round superseded; those quotes are **historical and resolved**, not live rules.)

---

## 1. Status and scope

### 1.0 Transition to a minimum first-pilot design

This document remains an honest record of the accepted generalized design. Its
status has changed because that architecture is no longer on the first-pilot
critical path.

Preserved here:

- prior design reasoning;
- threat analysis;
- generalized API proposals;
- Checkpoint A/B separation;
- privacy and publication concepts;
- review and finding-closure history.

No longer authoritative for the first pilot:

- exact implementation file scope;
- mandatory Checkpoint A/B sequencing;
- record and loader family;
- capability architecture;
- global validation-stage precedence;
- per-boundary error inventories;
- generalized publication and verification machinery;
- nullary production APIs and reusable CLI requirements.

Terms such as “normative,” “authoritative,” “must,” “implementation-ready
contract,” and “next implementation gate” elsewhere in this document apply only
within the preserved, deferred generalized architecture. They do not authorize or
govern first-pilot work.

Where this document conflicts with the later minimum-defensible census contract,
the minimum-defensible contract controls the first pilot.

### 1.1 What this layer is

The **metadata-only census layer**: given fixed local transcript roots and an
independently approved source-identity specification, it deterministically
enumerates the complete CALLHOME transcript population, computes local identity
metadata (size + SHA-256 + derived conversation identity per file), detects
duplicate/colliding identities, verifies the enumeration against a frozen approved
member inventory, computes a **stable population identity**, and publishes a
**local-only, immutable** frozen population manifest. It can re-verify that
manifest without changing membership and emit only an explicitly approved,
privacy-safe **aggregate** census.

### 1.2 What this layer is not

It **does not** parse transcript contents. It never opens a `.cha` file as text,
never tokenizes, language-labels, screens, validates monolinguality, projects,
promotes, constructs a dataset, or assigns a split. It must not import or call
`read_chat_transcript`, `parse_chat_file`, or `parse_chat_lines`. Reading raw
**bytes** to compute a SHA-256 digest is not parsing: each `.cha` file (and each
approved archive) is an opaque byte stream for hashing only.

### 1.3 Exact implementation file scope (later gates)

The eventual implementation touches only these files, and only across the two
checkpoints of §1.4:

```text
src/cslm/data/callhome_population.py     # Checkpoint A: pure core; Checkpoint B: + filesystem boundary
scripts/census_callhome_population.py    # Checkpoint B only: fixed-everything, authorization-gated runner
tests/test_callhome_population.py         # A: invented-only tests; B: synthetic filesystem fixtures
.gitignore                               # Checkpoint B only: one narrow entry (§7)
```

No other file may change in either implementation checkpoint. This design document
is the only file changed in the current docs-only gate.

### 1.4 Implementation checkpoint boundary (normative)

The synthetic-only implementation is delivered in two separately reviewed
checkpoints. This boundary is **normative**: it fixes exactly what a Checkpoint A
implementer may and may not build, so no privacy, schema, ordering, identity, or
collision behavior has to be invented, and so filesystem/production concerns cannot
leak into the pure core.

#### Checkpoint A — pure deterministic core

Maximum eventual implementation scope:

```text
src/cslm/data/callhome_population.py
tests/test_callhome_population.py
```

Checkpoint A may contain **only**:

```text
frozen typed records
exact constants and field predicates
privacy-safe representations
strict mapping and JSON validation
canonical serialization
source-approval checksum calculation
authorization checksum calculation
stable population identity
manifest-file identity
count derivation and reconciliation
exact conversation identity
pure deterministic ordering
pure collision checks over supplied values
pure approved-inventory membership comparison over supplied immutable
  CallhomeSourceApproval and CallhomePopulationEntry values (§10.3)
pure language-crossover detection over those supplied approved inventories and
  candidate entries (§13.5)
pure aggregate acceptance with fixed deterministic failure categories and precedence
  for those comparisons, via _build_population_manifest over supplied values (§16.9)
in-memory aggregate-summary construction
invented-only tests
```

The pure approved-inventory and crossover comparisons operate **only** on values
explicitly supplied to the pure core (a supplied `CallhomeSourceApproval` and supplied
candidate `CallhomePopulationEntry` values). Checkpoint A must **not** enumerate real
directories, open archives, inspect live resources, discover approval state, or
authenticate a caller: it compares only handed-in values, with **no** filesystem,
archive, environment, Git, clock, authorization-bootstrap, or live-source access.

Checkpoint A must **exclude**:

```text
pathlib
os
filesystem-capable imports or APIs
filesystem traversal
archive or transcript hashing
trusted bootstrap
project_root
authorization capability
resolved production filesystem paths
Path objects
path-producing helpers
filesystem-root discovery or access
caller-supplied filesystem locations
publication
verification execution
nullary production entry points
CLI
.gitignore changes
real corpus or archive access
strict CHAT parsing
```

Checkpoint A **may and must** contain the fixed public **logical identity strings**:

```text
ENGLISH_LOGICAL_ROOT = "data/raw/callhome/eng"
SPANISH_LOGICAL_ROOT = "data/raw/callhome/spa"
```

These are **canonical serialized identity values** (they populate `logical_roots`,
§11.1) — they are **not** resolved filesystem paths, **not** `Path` objects, and
**not** filesystem capabilities. Excluding "resolved production filesystem paths"
does not exclude these fixed strings; the exclusion targets `Path`/`os`/`project_root`
resolution and access, not the presence of the logical-root string constants (§6.1).

All Checkpoint A inputs (mappings, member values, candidate/approval/authorization
records, JSON text or bytes) are **supplied to pure functions**; the pure core reads
nothing from disk and resolves no path (see §6.1). Checkpoint A computes checksums
and identities over values it is handed, validates JSON strings/bytes it is handed,
and constructs records and the in-memory aggregate summary — all without touching
the filesystem, the clock, the environment, or Git.

#### Checkpoint B — production/filesystem boundary

Deferred to Checkpoint B — **live acquisition, authentication, input preparation,
invocation, and publication** (NOT the pure aggregate comparisons themselves, which are
Checkpoint A over supplied values):

```text
trusted bootstrap
authorization capability and capability enforcement
fixed paths
directory and archive purity
live filesystem and archive enumeration
archive and transcript hashing
construction of candidate source snapshots from real resources
acquisition and authentication of the accepted CallhomeSourceApproval
creation of candidate CallhomePopulationEntry values from live enumeration
supplying source_approval, entries, run metadata, and authorization checksums to
  _build_population_manifest
propagating builder failure
publishing only the builder-returned accepted manifest
immutable publication
frozen-manifest verification
nullary production APIs
CLI
.gitignore
filesystem, publication, cancellation, and boundary privacy tests
```

**Approved-inventory membership comparison and language-crossover detection are NOT
deferred to Checkpoint B**: they are pure Checkpoint A comparisons over supplied values
(§10.3, §13.5, §16.9), owned by `_build_population_manifest`. Checkpoint B **prepares**
the inputs (live enumeration, authentication, candidate-entry creation) and **invokes**
the builder; it must **not** independently replace the builder's authoritative ordering,
collision, language-crossover, approved-inventory, count, stable-identity, or
manifest-integrity acceptance decision. The correct distinction is: **Checkpoint A** =
pure comparison and deterministic aggregate acceptance over supplied values;
**Checkpoint B** = live acquisition, authentication, input preparation, invocation, and
publication.

`.gitignore` is **not** part of Checkpoint A because Checkpoint A creates and
accesses **no local-output path** — it neither writes nor resolves any file under
`data/processed/callhome_population/`, so there is nothing for a `.gitignore` entry
to protect until Checkpoint B introduces publication. The single `.gitignore` line
(§7) and its guardrail test are Checkpoint B work.

Sections §8.7 (constants), §8.8 (field predicates), §10.3 (approved-inventory
membership comparison, over supplied values), §10.8 (member ordering), §11.7
(identity/reconciliation closure), §13.4–§13.5 (collision/crossover algorithms),
§14.3 (strict JSON), and §18.5 (privacy-safe representations) are Checkpoint A
contracts. Sections §8.6, §9.2, §10.7, §15, §17, and the CLI (§8.4) are Checkpoint B
contracts.

---

## 2. Scientific rationale

The project trains four comparable BERT-style masked-language encoders —
`EnglishMono`, `SpanishMono`, `MonoCont`, `CsCont` — and the principal comparison
is `CsCont − MonoCont`. Permanent source routing:

```text
CALLHOME English → EnglishMono and MonoCont only
CALLHOME Spanish → SpanishMono and MonoCont only
CALLHOME         → never CsCont
Bangor Miami     → CsCont only
```

Before any CALLHOME row is parsed, validated, or promoted, the project must fix
exactly which files constitute the population. Provider mixing, snapshot drift,
silent omission, duplicate exposure, language crossover, or post-hoc source
selection would make the eventual monolingual corpora differ for reasons unrelated
to code-switching — an uncontrolled sampling confound upstream of
`CsCont − MonoCont`. The census freezes population membership deterministically,
auditably, and immutably, failing closed on any anomaly. It is the sampling-frame
analogue of the strict CHAT reader.

---

## 3. Accepted source authority

```text
Provider           : TalkBank CABank only (canonical distribution)
English authority  : one approved TalkBank CABank CallHome English CHAT snapshot
Spanish authority  : one approved TalkBank CABank CallHome Spanish CHAT snapshot
LDC (LDC97T14 /    : historical provenance or a separately approved fallback only;
 LDC96T17)           never mixed into the primary TalkBank population
```

The census consumes the TalkBank **UTF-8 `.cha`** distribution (consistent with
the reader's `@UTF8` requirement); it does not consume LDC ISO-8859-1 transcripts.
Any approved LDC fallback would be a separate, distinctly-labelled source approval,
never blended into a TalkBank population manifest. No real archive filename, size,
digest, URL, citation string, snapshot label, or conversation identifier appears
in this document; citation/release labels are governance decisions G5/G6 and are
`TODO` in `docs/callhome_ground_rules.md`. Placeholders only.

---

## 4. Population contract

### 4.1 Membership

Population membership is **every direct, regular, non-symlink file with an exact
lowercase `.cha` suffix that is a direct child of an approved logical root and is
present in the approved frozen member inventory.** Enumeration is **non-recursive**.
Both language populations must be **nonempty**. The census never deduplicates,
filters, shrinks, or repairs the population. A single authorized zero-byte `.cha`
file remains a member (§13.3).

### 4.2 Structural rules (each aborts, never silently skipped)

```text
base + roots + parents are real, non-symlink directories
non-recursive enumeration
both eng and spa populations nonempty
no unexpected entries         (anything not an accepted .cha member)
no nested directories in a root
no archives in transcript roots (*.zip, *.tgz, *.tar, *.gz, ...)
no hidden files               (name begins with ".")
no temporary files            (*~, *.tmp, *.swp, *.part, #...#)
no macOS metadata             (.DS_Store, ._* AppleDouble)
no uppercase/mixed suffix     (exact lowercase ".cha" only)
no special files              (symlink, FIFO, socket, device)
no broken symlinks
no silent-ignore policy       (every entry is an accepted member or an abort)
```

### 4.3 Ordering (total, deterministic, locale-independent)

```text
Primary  : English (eng) before Spanish (spa)
Secondary: ascending BYTEWISE ordering of the exact UTF-8 encoding of the POSIX
           relative-path string (raw bytes; not locale collation, not NFC/NFD-
           folded, not case-folded)
```

Ordinals `0..N-1` are assigned over eng-then-spa after sorting. Ordering must not
depend on directory-iteration order, locale, `LC_COLLATE`, or creation order.

### 4.4 Rejected identity collisions (each aborts) — see §13

The five exact collision classes (§13.4), in internal precedence order:

```text
duplicate byte content            (identical SHA-256)
duplicate conversation identity   (identical exact conversation_id)
Unicode NFC collision             (exact bytes differ; equal after NFC)
Unicode NFD collision             (exact bytes differ; equal after NFD)
Unicode case-fold collision       (exact bytes differ; equal after casefold())
```

Plus the two non-collision population aborts:

```text
manifest drift (enumerated set ≠ approved inventory)  → source_identity_mismatch
English/Spanish crossover                             → language_crossover (§13.5)
```

The former generic "duplicate normalized path identity" class is **removed** as an
independent collision category (§13.1); the four exact-path comparisons above
(bytes, NFC, NFD, case-fold) plus conversation-ID equality already cover every
deterministic path-collision class without an unspecified extra normalization.

---

## 5. Threat model

| Threat | Consequence if undetected | Census defense |
|---|---|---|
| Provider mixing | encoding/format drift | single-provider approval; archive rehash (§10) |
| Snapshot/version drift | asymmetric corpora | per-language pinned archive + member digests |
| Silent omission | shrunken population | manifest-drift check (§10.3) |
| Silent addition | contamination | `unexpected_entry` + extra-member abort |
| Duplicate exposure | over-weighting | duplicate byte/conversation/path checks (§13) |
| Language crossover | wrong-language rows | per-root attribution + crossover check |
| Post-hoc exclusion | investigator bias | frozen inventory; no silent ignore; no dedup/shrink |
| Ordering nondeterminism | non-reproducible sampling | total bytewise ordering (§4.3) |
| Accidental real traversal | privacy/ethics exposure | bootstrap + opaque authorization *before* corpus resolution (§8) |
| Working-directory spoof of control records | wrong authorization selected | `__file__`-based bootstrap; CWD/env ignored (§8.6) |
| Archive path escape / stray archive | wrong bytes hashed | basename confinement + archive-dir purity (§10.7) |
| Count/entry divergence | mislabeled aggregates | counts in stable identity + reconciliation (§11.6) |
| Overwriting the frozen frame | silent population change | no-overwrite state machine (§15) |
| Interrupted publication | ambiguous frozen state | `publication_verification_required` (§15.3) |
| Identity conflation | mislabeling "same population" | separate population/run/file identities (§11) |
| Privacy leakage | committing identifying material | content-free error taxonomy (§18) + Decision B matrix (§19) |

The authorization boundary is a **supported-interface** control against accidental
or ordinary misuse of the production API (§8.2/§17.3); it is **not** cryptographic
isolation against hostile code already executing inside the Python process.
Delegated to later gates: language identification, monolinguality, screening,
projection, promotion, splitting, dataset construction.

---

## 6. Proposed architecture

```text
src/cslm/data/callhome_population.py
  ├── errors     : CallhomePopulationError + closed content-free category constants
  ├── bootstrap  : _bootstrap_repository_root() (§8.6)
  ├── auth       : opaque capability + private grant/verify (§8.2/§17)
  ├── source id  : CallhomeSourceMember, CallhomeExtractionProcedure,
  │                CallhomeSourceSnapshot, CallhomeSourceSnapshotId,
  │                CallhomeCandidateSourceSnapshotRecord, CallhomeSourceApproval,
  │                CallhomeCensusAuthorizationRecord
  ├── manifest   : CallhomePopulationEntry, CallhomePopulationCounts,
  │                CallhomePopulationManifest, CallhomePopulationVerification,
  │                CallhomePopulationCensusSummary
  ├── public API : census_approved_callhome_population()  (nullary)
  │                verify_frozen_callhome_population()     (nullary)
  ├── core       : _census_population_core(...)  PRIVATE, test-only injection seam
  ├── serialize  : canonical JSON + checksums (§14)
  ├── schemas    : strict loaders for every persisted record (§16)
  ├── publish    : six-state no-overwrite publisher (§15)
  └── aggregate  : build_population_census_summary(...) (Decision-B-gated, §19)

scripts/census_callhome_population.py
  └── fixed command; fixed base/roots/control dir/output filenames; explicit
     human-confirmation flag; opaque production authorization; census-only.

tests/test_callhome_population.py
  ├── Checkpoint A: pure invented-value tests (constructors, validators, mapping
  │                 functions, serializers, checksums, ordering, collision,
  │                 reconciliation, summary) — NO filesystem, NO _census_population_core
  └── Checkpoint B: synthetic filesystem trees + the private _census_population_core
                    seam (authorization, traversal, hashing, publication, verification,
                    privacy-boundary, cancellation, CLI)
```

The **eventual complete** module depends only on the standard library and
`cslm.utils.paths.project_root`. This dependency list is **normative and complete**,
not an accidentally-partial illustration:

```text
Checkpoint A (pure core) — COMPLETE allowed dependency set:
    hashlib, json, unicodedata, dataclasses   (and only these)

Checkpoint B (filesystem boundary) — ADDS exactly:
    pathlib, os, stat, io, cslm.utils.paths.project_root
```

It has **no dependency** on `callhome_chat` or any projection/screening module, so it
cannot accidentally parse transcript content. The filesystem-capable imports
(`pathlib`, `os`, `stat`, `io`) and `project_root` are introduced **only at
Checkpoint B**; at Checkpoint A the module imports **none** of them (§6.1).

### 6.1 Parsing and filesystem independence of the pure core (normative)

At **Checkpoint A**, the module (`callhome_population.py`) is a pure, deterministic
core. Normatively, the Checkpoint A module:

```text
does not import callhome_chat
does not import strict or permissive CHAT readers (read_chat_transcript,
  parse_chat_file, parse_chat_lines)
does not import screening, projection, condition, or routing modules
does not import pathlib, os, stat, io, or any other filesystem-capable API
does not accept Path values or filesystem handles as arguments
does not access files, directories, archives, environment variables, Git, or the
  clock
```

The pure core operates exclusively on values passed to it (mappings, member values,
record objects, JSON strings/bytes, injected timestamps/commit strings when a record
must carry one — supplied as data, never read from the environment). **One
dependency/import guard test is sufficient** to establish the absence of filesystem
and parsing capabilities in Checkpoint A (assert the module's imported names are a
subset of the complete Checkpoint A set `{hashlib, json, unicodedata, dataclasses}`,
contain none of the forbidden modules, and that the module exposes no path-accepting
public helper).

**Logical-root strings are not filesystem capability.** The fixed public constants
`ENGLISH_LOGICAL_ROOT = "data/raw/callhome/eng"` and
`SPANISH_LOGICAL_ROOT = "data/raw/callhome/spa"` (§8.7) are **canonical serialized
identity strings** that Checkpoint A may and must hold (they populate the manifest's
`logical_roots`, §11.1). Holding these `str` constants is **not** resolving a
filesystem path, is **not** a `Path` object, and grants no filesystem access. The
Checkpoint A exclusion (§1.4) bans **resolved production filesystem paths**, `Path`
objects, path-producing helpers, filesystem-root discovery/access, and
caller-supplied filesystem locations — not the presence of the logical-root string
literals.

Because Checkpoint A helpers are pure and **catch no exceptions from I/O**, do
**not** require artificial filesystem-error or cancellation tests for them; those
belong to Checkpoint B, where the filesystem boundary actually exists. Filesystem
traversal, bootstrap, archive/transcript hashing, `project_root`, and publication
(§8.6, §9.2, §10.7, §15, §17) are introduced at Checkpoint B; that is where the
`pathlib`/`os`/`stat`/`io`/`project_root` dependencies first appear.

---

## 7. Fixed locations and local output ignore rule

Fixed project-relative locations (resolved via the bootstrap of §8.6 **after**
authorization; never caller-supplied, never CWD- or environment-derived):

```text
CALLHOME base            : data/raw/callhome
English root             : data/raw/callhome/eng
Spanish root             : data/raw/callhome/spa
Local control/output dir : data/processed/callhome_population
Approved local archive dir : data/processed/callhome_population/archives  (§10.7)
```

Fixed output filenames under `data/processed/callhome_population/` (§16 defines
each schema; §10 defines which gate produces each):

```text
candidate_source_snapshot.json          (produced by gate 8: observation)
source_approval.json                    (frozen by gate 10: independent approval)
census_authorization.json               (produced by gate 12: human authorization)
callhome_population_manifest.json        (produced by gate 13: real census; immutable)
callhome_population_census_summary.json  (aggregate; local until G3)
```

**Everything except the two `.cha` roots lives outside `data/raw/callhome`.**
Archives (under `…/archives/`), source-approval records, authorization records,
manifests, aggregate records, and temporary census outputs must **never** reside
under `data/raw/callhome` (enforced by the base-purity check, §9.2) and archives
must reside only in the fixed archive directory (enforced by §10.7).

The frozen manifest, the local approval/authorization records, per-file
inventories, transcript checksums, and conversation identifiers are per-row /
reconstructive material Decision B does not cover, so the whole
`data/processed/callhome_population/` tree is **local-only and gitignored**. The
later gate adds exactly one `.gitignore` line
(`data/processed/callhome_population/`) plus a guardrail test asserting it is
present (mirroring `tests/test_lexicon_storage_gitignore.py`). **This design gate
does not edit `.gitignore`.**

---

## 8. Public API (non-bypassable)

### 8.1 Nullary production entry points

```python
def census_approved_callhome_population() -> CallhomePopulationManifest: ...
def verify_frozen_callhome_population() -> CallhomePopulationVerification: ...
```

These take **no arguments**. There is deliberately **no** public parameter for
roots, base directory, output directory, output filename, write/no-write mode,
glob, subset, exclusion selector, alternate provider, or permissive mode.
`CallhomeRoots` is **not** part of the public API (§8.5). Both functions execute,
in this exact order (bootstrap first; see §8.6):

```text
1. Derive the bootstrap repository root from __file__ (§8.6). No CWD, no PWD, no
   env var, no CLI override, no Git discovery from the current directory.
2. Validate the fixed tracked repository markers under the bootstrap root (§8.6).
   (No traversal of data/raw/… occurs in the bootstrap.)
3. Locate census_authorization.json under the bootstrap control dir; load and
   validate it in isolation (schema, schema_version, contract_version,
   population_schema_version, approved_operation) and its canonical checksum.
4. Locate source_approval.json under the same fixed control dir; validate it and
   verify the authorization binds to it by source_approval_sha256 (§17.1).
5. Call project_root(); require project_root() == the bootstrap root, else fail
   closed with environment_error.
6. Only now resolve or inspect the fixed corpus roots and the fixed archive dir.
7. Base-purity check (§9.2); archive confinement + rehash (§10.7/§10.4); census /
   verify pipeline (§9/§11).
```

A missing or invalid authorization refuses at step 3 — **before** `project_root()`,
before loading any record other than the authorization record, before corpus-root
resolution, and before any traversal of `data/raw`.
`census_approved_callhome_population()` refuses if the final manifest already
exists (§15) — it never overwrites the frozen population.
`verify_frozen_callhome_population()` never writes (§11.4).

### 8.2 Opaque capability (supported-interface authorization boundary)

Authorization is an **opaque, module-internal** capability. It is a
**supported-interface guard against accidental or ordinary caller misuse of the
production API** — not access control and not cryptographic isolation (§17.3). It
protects the normal production path; it does not defend against code that
deliberately imports or introspects private module internals, which is unsupported
and outside this project's threat model.

```python
_CAPABILITY_SENTINEL = object()          # module-internal; not part of the public API

@dataclass(frozen=True)
class _CensusCapability:
    _token: object                        # set to _CAPABILITY_SENTINEL by the grant path
    source_approval_sha256: str
    contract_version: str
    population_schema_version: str
    approved_operation: str

def _grant_capability(control_dir: Path) -> _CensusCapability:
    """The supported way to obtain a valid capability. Loads census_authorization.json
    and source_approval.json from the fixed control_dir, verifies the authorization's
    canonical checksum and its binding to the source approval, checks contract and
    population-schema versions and the approved operation, and only then stamps the
    module sentinel. Any failure raises authorization_error (content-free)."""

def _require_valid(capability: _CensusCapability) -> None:
    if capability._token is not _CAPABILITY_SENTINEL:
        raise CallhomePopulationError(_AUTHORIZATION_ERROR)
    # ... plus re-checks of checksum/version bindings.
```

On the **supported production path** there is no public capability parameter,
constructor, or factory, and the entry points are nullary — so ordinary calling
code has nothing to pass, populate, or forge. Constructing a lookalike
`_CensusCapability` with matching public fields does not authorize traversal
because its `_token` is not the sentinel value the grant path stamps. Underscore
names are Python **convention, not enforcement**: nothing prevents code that
deliberately reaches into module internals from reading `_CAPABILITY_SENTINEL`;
that is explicitly out of scope (§17.3).

### 8.3 Private synthetic-testing seam (Checkpoint B)

`_census_population_core` is a **Checkpoint B** construct: it exists only once the
filesystem boundary is introduced, and it is the seam Checkpoint B tests drive with
synthetic filesystem trees. Checkpoint A tests never use it — they call the pure
supplied-value constructors, validators, mapping functions, serializers, checksum,
ordering, collision, reconciliation, and summary functions directly (§20.1).

```python
def _census_population_core(
    *, capability, bootstrap_root, base_dir, eng_root, spa_root, control_dir,
    archive_dir, source_approval, fs=<injected>, clock=<injected>,
    repository_commit=<injected>, publish=<injected six-state publisher>,
) -> CallhomePopulationManifest: ...
```

`_census_population_core` is **private**, accepts injected synthetic roots,
filesystem operations, clock, Git commit, and publication behavior **solely for
tests**, and is the single implementation body the nullary public functions call
with fixed real locations. It is **not** imported by the script, is **not** an
authorization mechanism (tests mint a capability via `_grant_capability` over a
synthetic tmp control dir), and never appears on the production path except beneath
the two nullary entry points. Tests verify the supported production path, not
adversarial in-process isolation.

### 8.4 CLI (additional safeguard, not the boundary)

```text
scripts/census_callhome_population.py:
  fixed command name; no positional or path arguments;
  fixed base/roots/control dir/archive dir/output filenames (imported from module);
  REQUIRES an explicit, self-describing human-confirmation flag, e.g.
    --i-have-approved-local-callhome-census;
  REQUIRES successful opaque production authorization (via the nullary entry
    point) — the flag alone authorizes nothing;
  calls ONLY census_approved_callhome_population() / verify_frozen_callhome_
    population(); it never touches _census_population_core.
```

The flag is a deliberate extra speed-bump; the supported-interface authorization
boundary is the opaque capability, which fails closed regardless of the flag.

### 8.5 All public/persisted types (exact fields)

Field notes use: **type**; required (R) / value set; **privacy** (PUB = public
fact, LOC = local only); canonical representation. Strict loading per §16.

```python
@dataclass(frozen=True, slots=True)
class CallhomeSourceMember:
    relative_path: str        # exact POSIX str (§12); strict-UTF-8; LOC
    size_bytes: int           # >= 0; LOC
    sha256: str               # 64 lowercase hex; LOC

@dataclass(frozen=True, slots=True)
class CallhomeExtractionProcedure:
    procedure_id: str         # e.g. "talkbank_cha_extract/1"; PUB label
    tool_name: str            # PUB label
    tool_version: str         # PUB label
    normalization_policy: str # fixed "none_byte_for_byte" (§10.A); PUB
    destination_layout: str   # fixed "eng_root_spa_root"; PUB
    overwrite_policy: str     # fixed "empty_destination_no_overwrite"; PUB
    member_path_policy: str   # fixed "exact_posix_no_escape_strict_utf8"; PUB

@dataclass(frozen=True, slots=True)
class CallhomeSourceSnapshot:
    provider: str             # "talkbank_cabank"; PUB
    corpus_name: str          # PUB (placeholder until G5/G6)
    language: str             # "eng" | "spa"; PUB
    official_url: str         # PUB (placeholder until G5/G6)
    public_release_label: str # PUB (placeholder until G5/G6)
    archive_filename: str     # bare basename (§10.7); LOC
    archive_size_bytes: int   # >= 0; LOC
    archive_sha256: str       # 64 hex; LOC
    retrieval_utc: str        # ISO-8601 UTC; LOC
    extraction_procedure: CallhomeExtractionProcedure   # exactly one; nested
    members: tuple[CallhomeSourceMember, ...]           # frozen expected inventory; LOC
    def identity(self) -> "CallhomeSourceSnapshotId": ...

@dataclass(frozen=True, slots=True)
class CallhomeSourceSnapshotId:                 # identity-only view (no archive_filename)
    provider: str; corpus_name: str; language: str
    public_release_label: str; archive_sha256: str; n_members: int

@dataclass(frozen=True, slots=True)
class CallhomeCandidateSourceSnapshotRecord:    # candidate_source_snapshot.json
    schema: str               # "callhome_candidate_source_snapshot"
    schema_version: str       # "1"
    observed_utc: str
    provider: str
    distribution_format: str  # "chat_utf8"
    english: CallhomeSourceSnapshot
    spanish: CallhomeSourceSnapshot
    # NOTE: extraction procedure lives INSIDE each snapshot, not at top level.

@dataclass(frozen=True, slots=True)
class CallhomeSourceApproval:                   # source_approval.json (checksum-bound)
    schema: str               # "callhome_source_approval"
    schema_version: str       # "1"
    contract_version: str
    provider: str
    distribution_format: str  # "chat_utf8"
    english: CallhomeSourceSnapshot
    spanish: CallhomeSourceSnapshot
    approved_by: str
    approved_utc: str

@dataclass(frozen=True, slots=True)
class CallhomeCensusAuthorizationRecord:         # census_authorization.json (checksum-bound)
    schema: str               # "callhome_census_authorization"
    schema_version: str       # "1"
    contract_version: str
    population_schema_version: str   # MUST equal the manifest's schema_version
    approved_operation: str          # "census" | "verify"
    source_approval_sha256: str
    approved_by: str
    approved_utc: str

@dataclass(frozen=True, slots=True)
class CallhomePopulationEntry:
    ordinal: int              # 0..N-1
    language: str             # "eng" | "spa" (expected, directory-derived)
    relative_path: str        # exact POSIX str (§12); LOC
    size_bytes: int           # >= 0; LOC
    sha256: str               # 64 hex; LOC
    conversation_id: str      # derived (§10.5); LOC

@dataclass(frozen=True, slots=True)
class CallhomePopulationCounts:                  # canonical stable field (§11.6)
    n_english_files: int; n_spanish_files: int; n_total_files: int
    english_total_bytes: int; spanish_total_bytes: int; total_bytes: int
    n_zero_byte_files: int
    all_identity_checks_passed: bool             # always True in a persisted manifest

@dataclass(frozen=True, slots=True)
class CallhomePopulationManifest:                 # callhome_population_manifest.json
    schema: str               # "callhome_population_manifest"
    schema_version: str       # "1"  (the census-authorization population_schema_version)
    # --- stable scientific population fields (feed population_identity_sha256) ---
    population_contract_version: str
    provider: str
    distribution_format: str
    english_snapshot_id: CallhomeSourceSnapshotId
    spanish_snapshot_id: CallhomeSourceSnapshotId
    logical_roots: tuple[str, str]               # ("data/raw/callhome/eng", ".../spa")
    ordering_contract_id: str                    # "eng_then_spa/bytewise_utf8/1"
    entries: tuple[CallhomePopulationEntry, ...]
    counts: CallhomePopulationCounts             # reconciled with entries (§11.6)
    population_identity_sha256: str              # §11.1 (over stable fields only)
    # --- run/execution metadata (excluded from population identity) ---
    created_utc: str
    repository_commit: str
    source_approval_sha256: str
    census_authorization_sha256: str
    tool_version: str
    execution_status: str                        # "verified"
    # --- whole-file integrity (excludes itself) ---
    manifest_file_sha256: str                    # §11.3

@dataclass(frozen=True, slots=True)
class CallhomePopulationVerification:             # inert type DEFINED in Checkpoint A; CONSTRUCTED by Checkpoint B live verification (§11.4, §16.7, §16.10)
    ok: bool                                     # == the four fatal terms below (§11.7)
    population_identity_sha256: str
    manifest_file_sha256_ok: bool                # FATAL
    membership_matches: bool                     # FATAL; ordered entries only (NOT identity)
    population_identity_matches: bool            # FATAL; recomputed stable identity == persisted (§11.1)
    counts_reconciled: bool                      # FATAL; §11.6
    repository_commit_compatible: bool           # INFORMATIONAL only; never affects ok
    checked_utc: str
    # content-free; carries no path/name/digest of any offending member.

@dataclass(frozen=True, slots=True)
class CallhomePopulationCensusSummary:            # callhome_population_census_summary.json
    schema: str               # "callhome_population_census_summary"
    schema_version: str       # "1"
    provider: str
    n_english_files: int; n_spanish_files: int; n_total_files: int
    english_total_bytes: int; spanish_total_bytes: int; total_bytes: int
    n_zero_byte_files: int
    all_identity_checks_passed: bool
    population_identity_sha256: str
```

English and Spanish each carry their own `CallhomeExtractionProcedure`. **Intended
requirement:** both procedures must satisfy the same fixed procedure contract
(same fixed `normalization_policy`, `destination_layout`, `overwrite_policy`,
`member_path_policy` values); `procedure_id`/`tool_name`/`tool_version` are
recorded per snapshot and may differ, but any difference is recorded, not silently
tolerated. This equality-of-contract requirement is explicitly tested (§20).

A `_CensusRoots` structure (private, test-only) may bundle injected synthetic roots
for `_census_population_core`; it is **not** public and **not** accepted by the
nullary entry points.

### 8.6 Trusted authorization bootstrap (CWD-independent)

```python
def _bootstrap_repository_root() -> Path:
    """Derive the repository root ONLY from the resolved module location.
    For <repo>/src/cslm/data/callhome_population.py the root is
    Path(__file__).resolve().parents[3]. Validate fixed tracked markers, then
    return the root. No CWD, PWD, env var, CLI override, PATH, or Git discovery."""
```

Contract:

```text
- root = Path(__file__).resolve().parents[3]  (data → cslm → src → <repo>).
- Validate a fixed, non-private, tracked layout using public markers:
      <root>/pyproject.toml
      <root>/src/cslm/
      <root>/src/cslm/data/
  A missing marker fails closed (environment_error) BEFORE any private-path
  resolution or corpus traversal.
- The bootstrap NEVER inspects or traverses data/raw/, data/raw/callhome/, or
  data/raw/bangor/. It exists only to locate the fixed control directory
  <root>/data/processed/callhome_population/.
- It ignores the current working directory, PWD, environment variables, CLI root
  overrides, PATH, and Git discovery from the current directory. Changing the
  process working directory has NO effect on which records are selected. Lookalike
  authorization/approval records outside the fixed control directory are ignored.
- After authorization, the entry point calls project_root() and requires
  project_root() == the bootstrap root; a mismatch fails closed (environment_error)
  before any archive or corpus traversal.
```

Closure tests: changing CWD to a directory holding a lookalike
`census_authorization.json` has no effect; a missing bootstrap marker fails before
private-path resolution; invalid authorization fails before `project_root()`; a
`project_root()`/bootstrap mismatch fails before archive/corpus traversal; the
bootstrap performs no access under `data/raw`; no environment or CLI override
changes the bootstrap root.

### 8.7 Normative constants (exact values — not examples)

These are **exact module-level constants** (Checkpoint A defines the pure-core
constants; Checkpoint B may reference them). None is a placeholder or example; each
is fixed at exactly the value shown.

```text
CANDIDATE_SOURCE_SNAPSHOT_SCHEMA          = "callhome_candidate_source_snapshot"
CANDIDATE_SOURCE_SNAPSHOT_SCHEMA_VERSION  = "1"

SOURCE_APPROVAL_SCHEMA                    = "callhome_source_approval"
SOURCE_APPROVAL_SCHEMA_VERSION            = "1"

CENSUS_AUTHORIZATION_SCHEMA               = "callhome_census_authorization"
CENSUS_AUTHORIZATION_SCHEMA_VERSION       = "1"

POPULATION_MANIFEST_SCHEMA                = "callhome_population_manifest"
POPULATION_MANIFEST_SCHEMA_VERSION        = "1"

CENSUS_SUMMARY_SCHEMA                     = "callhome_population_census_summary"
CENSUS_SUMMARY_SCHEMA_VERSION             = "1"

POPULATION_CONTRACT_VERSION               = "callhome_population_contract/1"
ORDERING_CONTRACT_ID                      = "eng_then_spa/bytewise_utf8/1"
TOOL_VERSION                              = "callhome_population_census/1"

PROVIDER                                  = "talkbank_cabank"
DISTRIBUTION_FORMAT                       = "chat_utf8"

ENGLISH_LOGICAL_ROOT                      = "data/raw/callhome/eng"
SPANISH_LOGICAL_ROOT                      = "data/raw/callhome/spa"

EXECUTION_STATUS                          = "verified"

NORMALIZATION_POLICY                      = "none_byte_for_byte"
DESTINATION_LAYOUT                        = "eng_root_spa_root"
OVERWRITE_POLICY                          = "empty_destination_no_overwrite"
MEMBER_PATH_POLICY                        = "exact_posix_no_escape_strict_utf8"
```

**Identity participation (normative).**

```text
- POPULATION_CONTRACT_VERSION, the manifest schema/schema_version
  (POPULATION_MANIFEST_SCHEMA / POPULATION_MANIFEST_SCHEMA_VERSION), and
  ORDERING_CONTRACT_ID PARTICIPATE in the stable population identity (§11.1).
- TOOL_VERSION is RUN METADATA ONLY (§11.2); it never enters population identity.
- The candidate, approval, authorization, and summary record schema versions
  (CANDIDATE_SOURCE_SNAPSHOT_SCHEMA_VERSION, SOURCE_APPROVAL_SCHEMA_VERSION,
  CENSUS_AUTHORIZATION_SCHEMA_VERSION, CENSUS_SUMMARY_SCHEMA_VERSION) govern their
  OWN persisted formats but do NOT independently enter the stable population
  identity, except where a value is already carried through a stable nested mapping
  specified in §11.1 (e.g. the snapshot-id fields).
- PROVIDER and DISTRIBUTION_FORMAT participate in stable identity via the manifest's
  provider/distribution_format fields (§11.1). ENGLISH_LOGICAL_ROOT and
  SPANISH_LOGICAL_ROOT participate via logical_roots (§11.1). EXECUTION_STATUS is run
  metadata only.
```

The extraction-policy constants (`NORMALIZATION_POLICY`, `DESTINATION_LAYOUT`,
`OVERWRITE_POLICY`, `MEMBER_PATH_POLICY`) are the exact required values every source
snapshot's `extraction_procedure` must carry (§8.8, §10.A).

### 8.8 Normative field predicates (every field of every record)

Each persisted and nested record field is validated on construction and on strict
load (§14.3, §16). Predicates are **normative**; a violation fails closed
(`schema_error` unless a stricter category applies).

**Type strictness (all records):**

```text
type(value) is str      for every string field
type(value) is int      for every integer field
type(value) is bool     for every Boolean field
bool is NEVER accepted where an int is required (isinstance(x, bool) → reject as int)
JSON arrays are validated explicitly and converted to IMMUTABLE tuples ONLY AFTER
  validation (never trusted in place, never left as lists)
unknown fields → reject; missing fields → reject
```

**String fields** (unless a stricter rule below applies):

```text
nonempty; strictly UTF-8 encodable; contains no lone surrogate; contains no NUL
```

**SHA-256 fields** (`sha256`, `archive_sha256`, `source_approval_sha256`,
`census_authorization_sha256`, `population_identity_sha256`, `manifest_file_sha256`):

```text
exactly 64 characters; each character in [0-9a-f] (lowercase hex ASCII)
```

**Timestamp fields** (`observed_utc`, `retrieval_utc`, `approved_utc`, `created_utc`,
`checked_utc`) — one exact grammar:

```text
YYYY-MM-DDTHH:MM:SSZ
- a REAL calendar/time value in UTC (validated as an actual date-time);
- no fractional seconds; no offset other than the literal trailing "Z";
- no surrounding whitespace.
```

**Git commit field** (`repository_commit`):

```text
exactly 40 characters; each in [0-9a-f] (lowercase hex ASCII)
```

**Integer fields** (`size_bytes`, `archive_size_bytes`, `n_members`, all count and
byte-total fields, `ordinal`):

```text
nonnegative unless a stricter rule applies;
ordinals begin at 0 and are consecutive across the ordered population with no gaps
  or duplicates (§4.3, §11.6)
```

**Boolean fields:**

```text
all_identity_checks_passed must be EXACTLY True in any persisted manifest or summary
  (a persisted verified record never stores False)
```

**Provider / language / format agreement:**

```text
candidate.provider == PROVIDER and approval.provider == PROVIDER
distribution_format == DISTRIBUTION_FORMAT
english.language == "eng"        spanish.language == "spa"
english snapshot provider == PROVIDER  and  spanish snapshot provider == PROVIDER
```

**Extraction-procedure policy (both snapshots, independently):**

```text
extraction_procedure.normalization_policy == NORMALIZATION_POLICY
extraction_procedure.destination_layout   == DESTINATION_LAYOUT
extraction_procedure.overwrite_policy      == OVERWRITE_POLICY
extraction_procedure.member_path_policy    == MEMBER_PATH_POLICY
procedure_id, tool_name, tool_version      : recorded nonempty labels; MAY differ
                                             between the English and Spanish snapshots
```

**Archive filename field** (`archive_filename`): the exact basename rules of §10.7
are normative here (nonempty strict-UTF-8 basename; no directory component; not "."
or ".."; no "/" or "\\"; no NUL; no drive/absolute syntax; no parent-traversal
component).

**Source-member relative-path field** (`relative_path` in `CallhomeSourceMember` and
`CallhomePopulationEntry`) — because membership is non-recursive, this is an exact
**direct-child basename**:

```text
nonempty; contains no "/" and no "\\"; not "." and not ".."; contains no NUL;
strictly UTF-8; ends in the exact lowercase ".cha" suffix;
not hidden, temporary, metadata, or otherwise excluded by the membership policy
  (§4.2)
```

The stored `relative_path` is **never normalized or case-folded** (§12); it is stored
exactly as enumerated. `conversation_id` is derived per §10.5 and is likewise stored
verbatim.

### 8.9 Normative Checkpoint A API contract (CHPA-P2-01)

This subsection is the **single authoritative Checkpoint A API table**. Every
Checkpoint A callable that implementation and tests are expected to use is pinned here
by exact Python name, visibility, signature, raise behavior, purity,
serialized-format exposure, and eventual Checkpoint B consumer. No Checkpoint A
operation may be implemented under a different name, and **no earlier prose in this
document overrides these names or signatures** — earlier prose that used phrases such
as "a helper" or "equivalent function" is subordinate to this table.

**Facts stated once for every row.** Every callable below is a **pure** Checkpoint A
function or type: it reads nothing from disk, resolves no path, and touches no clock,
environment, or Git (§6.1). The purity attribute is therefore `pure = yes` for every
row and is not repeated per row. Legend: `PUB` = public, importable from
`cslm.data.callhome_population`; `PRIV` = module-internal underscore name (Checkpoint
B lives in the **same module** and calls these directly; Checkpoint A tests may also
import them from the module — see "Direct imports" below). `raises` = may raise
`CallhomePopulationError`. `fmt` = serialized-format-facing (operates on canonical
JSON bytes, the explicit canonical mappings, or a cryptographic-checksum surface).
`B-consumer` = the Checkpoint B component that may later call it.

**A. Public types, constructors, and the one derivation method** (constructor
parameters and types are exactly the field declarations of §8.5; §8.10 is the type
inventory). **Per the validation-ownership rule (§16.7, CHPA-R3-01), every direct
dataclass constructor below enforces INTRINSIC / LOCAL invariants only and raises
`schema_error`; it never owns an aggregate / cross-record acceptance category — those
belong exclusively to the named builders and strict loaders (Parts B–D).**

```text
CallhomeSourceMember(...)                   PUB  raises(schema_error §8.8; intrinsic/local)  fmt no
    B-consumer: _census_population_core (builds live members before comparison)
CallhomeExtractionProcedure(...)            PUB  raises(schema_error §8.8; intrinsic/local)  fmt no
    B-consumer: _census_population_core
CallhomeSourceSnapshot(...)                 PUB  raises(schema_error §8.8/§16.7; intrinsic/local: incl. own members canonical order §10.8, n_members==len)  fmt no
    B-consumer: _census_population_core
CallhomeSourceSnapshot.identity(self) -> CallhomeSourceSnapshotId
                                            PUB (method)  raises no  fmt no
    B-consumer: _census_population_core; verification inspector (snapshot-ID binding)
CallhomeSourceSnapshotId(...)               PUB  raises(schema_error §8.8/§16.7; intrinsic/local)  fmt no
    B-consumer: verification inspector
CallhomeCandidateSourceSnapshotRecord(...)  PUB  raises(schema_error §8.8/§16.7; intrinsic/local)  fmt no
    B-consumer: candidate-observation gate (writer is out of module scope)
CallhomeSourceApproval(...)                 PUB  raises(schema_error §8.8/§16.7; intrinsic/local: contract_version==constant. The source_approval_sha256 → source_identity_mismatch binding is AGGREGATE, owned by _build_population_manifest (supplied source_approval + source_approval_sha256; §16.9), NOT this constructor and NOT _grant_capability — which authenticates the authorization record's own source_approval_sha256 at Checkpoint B → authorization_error, never source_identity_mismatch)  fmt no
    B-consumer: _grant_capability; _census_population_core
CallhomeCensusAuthorizationRecord(...)      PUB  raises(schema_error §8.8/§16.7; intrinsic/local)  fmt no
    B-consumer: _grant_capability
CallhomePopulationEntry(...)                PUB  raises(schema_error §8.8; intrinsic/local)  fmt no
    B-consumer: _census_population_core
CallhomePopulationCounts(...)               PUB  raises(schema_error §8.8; intrinsic/local)  fmt no
    B-consumer: _census_population_core
CallhomePopulationManifest(...)             PUB  raises(schema_error §8.8; INTRINSIC/LOCAL ONLY — fixed constants + ≥1 eng & ≥1 spa entry. Aggregate acceptance categories are owned by the named builder/loader boundaries per each boundary's evaluable stages (§16.7/§16.9/§8.9), NOT this constructor: _build_population_manifest owns language_crossover, binding/inventory source_identity_mismatch, ordering, duplicate_identity, count/identity/file-checksum manifest_mismatch; _load_population_manifest owns ONLY the self-contained subset {duplicate_identity, ordering_error, manifest_mismatch} and emits NO language_crossover or contextual source_identity_mismatch)  fmt no
    B-consumer: _census_population_core; publisher; verification inspector
CallhomePopulationCensusSummary(...)        PUB  raises(schema_error §8.8; INTRINSIC/LOCAL ONLY — fixed constants, all_identity_checks_passed==True, and local summary arithmetic. Manifest reconciliation (manifest_mismatch) is owned by build_population_census_summary, §16.7 — NOT this constructor)  fmt no
    B-consumer: (aggregate; publication deferred/governance-gated, §19)
CallhomePopulationVerification(...)         PUB (INERT type, §16.10)  raises(schema_error, constructor scalar invariants §8.8)  fmt no
    B-consumer: verification inspector CONSTRUCTS live results (A never does)
CallhomePopulationError(category: str)      PUB  raises(ValueError on unsupported category, §18.7)  fmt no
    (is itself the raised type for supported categories; B: all raising paths)
```

**B. Public function:**

```text
build_population_census_summary(manifest: CallhomePopulationManifest)
        -> CallhomePopulationCensusSummary
    PUB  raises(schema_error/manifest_mismatch on reconciliation §11.6/§16.7)  fmt no
    B-consumer: none required (A-constructed in memory; publication deferred, §19)
```

**C. Private serialized-format-facing helpers** (`fmt = yes`):

```text
_encode_canonical_json(mapping: dict[str, object]) -> bytes
    PRIV  raises(serialization_error §14.1)   B: publisher; every checksum
_decode_strict_json(data: str | bytes) -> dict[str, object]
    PRIV  raises(serialization_error/schema_error §14.3)   B: verification inspector
```

Typed bidirectional converters — EXACTLY ONE PAIR per Checkpoint A record (CHPA-R2-01).
This is the single authoritative converter inventory; §14.3 points here and defines no
second converter rule. Each `_<record>_to_mapping` is a pure projection of an
already-valid record to its canonical mapping (raises no). Each `_mapping_to_<record>`
constructs the typed record, enforcing ONLY the intrinsic / local scalar invariants
assigned to its construction stage (§16.9 Phase 2), and raises `schema_error` on an
intrinsic/local violation. Aggregate, cross-record, checksum, reconciliation, ordering,
collision, and crossover invariants are NEVER enforced by a converter — they are
enforced by the ordered builder/loader (§16.9). All 24 are PRIV, pure, `fmt = yes`.

```text
_source_member_to_mapping(record: CallhomeSourceMember) -> dict[str, object]
_mapping_to_source_member(mapping: dict[str, object]) -> CallhomeSourceMember
_extraction_procedure_to_mapping(record: CallhomeExtractionProcedure) -> dict[str, object]
_mapping_to_extraction_procedure(mapping: dict[str, object]) -> CallhomeExtractionProcedure
_source_snapshot_to_mapping(record: CallhomeSourceSnapshot) -> dict[str, object]
_mapping_to_source_snapshot(mapping: dict[str, object]) -> CallhomeSourceSnapshot
_source_snapshot_id_to_mapping(record: CallhomeSourceSnapshotId) -> dict[str, object]
_mapping_to_source_snapshot_id(mapping: dict[str, object]) -> CallhomeSourceSnapshotId
_candidate_source_snapshot_record_to_mapping(record: CallhomeCandidateSourceSnapshotRecord) -> dict[str, object]
_mapping_to_candidate_source_snapshot_record(mapping: dict[str, object]) -> CallhomeCandidateSourceSnapshotRecord
_source_approval_to_mapping(record: CallhomeSourceApproval) -> dict[str, object]
_mapping_to_source_approval(mapping: dict[str, object]) -> CallhomeSourceApproval
_census_authorization_record_to_mapping(record: CallhomeCensusAuthorizationRecord) -> dict[str, object]
_mapping_to_census_authorization_record(mapping: dict[str, object]) -> CallhomeCensusAuthorizationRecord
_population_entry_to_mapping(record: CallhomePopulationEntry) -> dict[str, object]
_mapping_to_population_entry(mapping: dict[str, object]) -> CallhomePopulationEntry
_population_counts_to_mapping(record: CallhomePopulationCounts) -> dict[str, object]
_mapping_to_population_counts(mapping: dict[str, object]) -> CallhomePopulationCounts
_population_manifest_to_mapping(record: CallhomePopulationManifest) -> dict[str, object]
_mapping_to_population_manifest(mapping: dict[str, object]) -> CallhomePopulationManifest
_population_verification_to_mapping(record: CallhomePopulationVerification) -> dict[str, object]
_mapping_to_population_verification(mapping: dict[str, object]) -> CallhomePopulationVerification
_population_census_summary_to_mapping(record: CallhomePopulationCensusSummary) -> dict[str, object]
_mapping_to_population_census_summary(mapping: dict[str, object]) -> CallhomePopulationCensusSummary

    _<record>_to_mapping:  PRIV, pure, fmt yes, raises no (projects an already-valid
      record).  B: checksums; publisher; the strict loaders' canonical reconstruction.
    _mapping_to_<record>:  PRIV, pure, fmt yes, raises schema_error for an intrinsic/
      local field violation ONLY (§16.9 Phase 2); it enforces no aggregate/cross-record
      invariant.  B: strict loaders (§16.9); verification inspector.
```

One-directional canonical projection (NOT a bidirectional pair):

```text
_population_manifest_stable_mapping(record: CallhomePopulationManifest) -> dict[str, object]
    # the §11.1 stable-fields mapping; the input to _population_identity_sha256
    PRIV  pure  fmt yes  raises no   B: verification inspector
```

Inert-only record note (`CallhomePopulationVerification`). Its converter pair
`_population_verification_to_mapping` / `_mapping_to_population_verification` supports
the record's canonical **internal representation and synthetic testing only** (§8.10,
§16.10). It does **not** authorize persistence of `CallhomePopulationVerification` and
does **not** authorize any live verification production behavior; the live
producer/inspector remain Checkpoint B.

```text
_source_approval_sha256(approval: CallhomeSourceApproval) -> str
    PRIV  raises no   B: _grant_capability; _census_population_core
_census_authorization_sha256(auth: CallhomeCensusAuthorizationRecord) -> str
    PRIV  raises no   B: _grant_capability
_population_identity_sha256(manifest: CallhomePopulationManifest) -> str   # over §11.1 stable mapping
    PRIV  raises no   B: _census_population_core; verification inspector
_manifest_file_sha256(manifest: CallhomePopulationManifest) -> str        # excludes own field, §11.3
    PRIV  raises no   B: publisher; verification inspector
```

**Strict loaders — EXACT per-loader error inventory (CHPA-R3-01 / P2-03).** Each strict
loader is pinned SEPARATELY; there is **no** collective "all loaders raise the full set"
rule. A loader may raise **only** categories arising from stages its API context can
actually evaluate (§16.9); contextual stages 14 (approval binding), 18 (crossover), and
19 (approved-inventory membership) require the approved source record and are **skipped**
where the API does not receive it. All are PRIV, pure, `fmt = yes`.

```text
_load_candidate_source_snapshot(data: str | bytes) -> CallhomeCandidateSourceSnapshotRecord
    evaluable: Phase 1 (stages 1–11) + Phase-2 intrinsic construction/invariants (12–13),
      incl. nested-snapshot member canonical order (§10.8) and archive_filename basename
      rules (§10.7, candidate → schema_error). No population entries; no checksum binding.
    raises(schema_error / serialization_error)
    NOT performed (no context): approval/manifest binding, crossover, approved-inventory,
      population collision/ordering/counts/identity/manifest-file checksum.
    B: candidate-observation gate reviewer (out of module scope)

_load_source_approval(data: str | bytes) -> CallhomeSourceApproval
    evaluable: Phase 1 + Phase-2 intrinsic (12–13) incl. §16.7 source-approval invariants
      (contract_version / provider / distribution_format constants; nested-snapshot
      language/provider; member order §10.8) and the archive_filename basename/field-grammar
      predicate (§8.8, §10.7 — an INTRINSIC/LOCAL field defect → schema_error, NOT a
      source-identity comparison).
    raises(schema_error / serialization_error)
    NOT performed (no context): approval-to-MANIFEST binding; crossover; approved-inventory
      membership; population collision/ordering/counts/identity/manifest-file checksum. This
      loader performs NO expected-checksum or authenticated binding and therefore raises NO
      source_identity_mismatch or authorization_error. Pure supplied-approval/checksum/source
      binding belongs to _build_population_manifest → source_identity_mismatch where assigned;
      authentication of the authorization record's own source_approval_sha256 belongs to
      Checkpoint B _grant_capability → authorization_error.
    B: _grant_capability

_load_census_authorization(data: str | bytes) -> CallhomeCensusAuthorizationRecord
    evaluable: Phase 1 + Phase-2 intrinsic (12–13) incl. §16.7 authorization invariants
      (schema / schema_version / contract_version / population_schema_version constants;
      approved_operation enum; source_approval_sha256 grammar).
    raises(schema_error / serialization_error)
    NOT performed (no context): the source_approval_sha256 BINDING to the frozen approval
      (Checkpoint B _grant_capability); no population checks.
    B: _grant_capability

_load_population_manifest(data: str | bytes) -> CallhomePopulationManifest   # STRICT ACCEPTANCE loader §16.4/§16.9
    evaluable SELF-CONTAINED stages ONLY: Phase 1 (1–11); typed construction (12);
      intrinsic invariants (13); n_members-vs-own-entries reconciliation (15); ordering +
      ordinals (16); collision over its own entries (17); count reconciliation (20);
      stable-identity recomputation (21); manifest-file checksum recomputation (22).
    raises(schema_error / serialization_error / duplicate_identity / ordering_error /
      manifest_mismatch)
    NOT performed — contextual stages 14 / 18 / 19 are SKIPPED because the API receives
      only canonical persisted str|bytes and NO approved-source context. It therefore
      CANNOT emit language_crossover (stage 18) and CANNOT emit source_identity_mismatch
      from approval binding (14) or ordinary approved-inventory mismatch (19). Skipping is
      NOT approval of a real source population, NOT evidence that persisted entries match an
      external approved source, and NOT authorization or live verification (§16.9, §16.7).
    B: verification inspector (§11.4/§16.8)

_load_census_summary(data: str | bytes) -> CallhomePopulationCensusSummary
    evaluable: Phase 1 + Phase-2 intrinsic (12–13) incl. §16.7 summary constants,
      all_identity_checks_passed == True, and local summary arithmetic
      (n_total_files == n_english_files + n_spanish_files; total_bytes ==
      english_total_bytes + spanish_total_bytes).
    raises(schema_error / serialization_error)
    NOT performed (no context): reconciliation of counts / population_identity_sha256
      AGAINST the accepted manifest (owned by build_population_census_summary); no
      population collision/ordering/crossover/inventory checks.
    B: (aggregate; publication deferred/governance-gated, §19)
```

**D. Private pure validation / derivation helpers** (`fmt = no` unless noted):

```text
_conversation_id(language: str, filename: str) -> str      # f"{language}/{filename[:-4]}", §10.5
    PRIV  raises no   B: _census_population_core
_derive_counts(entries: tuple[CallhomePopulationEntry, ...]) -> CallhomePopulationCounts   # §11.6
    PRIV  raises no   B: _census_population_core; verification inspector (as a compared value)
_reconcile_counts(counts: CallhomePopulationCounts,
                  entries: tuple[CallhomePopulationEntry, ...]) -> None   # raises on mismatch, §11.6
    PRIV  raises(manifest_mismatch)   B: _census_population_core
    (live verification derives its Boolean as _derive_counts(entries) == counts, §11.4)
_order_population_entries(entries: tuple[CallhomePopulationEntry, ...])
                  -> tuple[CallhomePopulationEntry, ...]     # eng-then-spa, exact-UTF-8-byte, §4.3
    PRIV  raises no   B: _census_population_core
_validate_population_order(entries: tuple[CallhomePopulationEntry, ...]) -> None   # total order + ordinals 0..N-1, §4.3
    PRIV  raises(ordering_error)   B: _census_population_core; verification inspector
_detect_population_collisions(entries: tuple[CallhomePopulationEntry, ...]) -> None   # §13.4 internal precedence
    PRIV  raises(duplicate_identity)   B: _census_population_core; verification inspector
_detect_language_crossover(entries: tuple[CallhomePopulationEntry, ...],
                  english_members: tuple[CallhomeSourceMember, ...],
                  spanish_members: tuple[CallhomeSourceMember, ...]) -> None    # §13.5, over supplied inventory
    PRIV  raises(language_crossover)   B: _census_population_core
_build_population_manifest(*, source_approval: CallhomeSourceApproval,
                  entries: tuple[CallhomePopulationEntry, ...], created_utc: str,
                  repository_commit: str, source_approval_sha256: str,
                  census_authorization_sha256: str) -> CallhomePopulationManifest
    # Takes the approved CallhomeSourceApproval as a SUPPLIED pure value (never read
    # from disk). DERIVES english_snapshot_id = source_approval.english.identity() and
    # spanish_snapshot_id = source_approval.spanish.identity() INTERNALLY; it accepts NO
    # caller-supplied snapshot IDs (CHPA-R2-02). Requires
    # source_approval.contract_version == POPULATION_CONTRACT_VERSION and
    # source_approval_sha256 == _source_approval_sha256(source_approval) (the canonical
    # checksum of the supplied approval). DERIVES the approved English and Spanish
    # inventories from source_approval.english.members / source_approval.spanish.members
    # (no extra parameter needed), and is therefore the AUTHORITATIVE aggregate-acceptance
    # boundary for approved in-memory construction (CHPA-R3-01). Reconciles each derived
    # snapshot-ID n_members against the per-language entries, then INDEPENDENTLY performs,
    # in §16.9 Phase-2 order: intrinsic + entry-count invariants (§16.7); ordering + ordinals
    # (§4.3); collision validation (§13.4); language-crossover detection (§13.5); ordinary
    # approved-inventory membership comparison (§10.3, over the derived inventories); count
    # reconciliation (§11.6); stable-identity recomputation (§11.1); manifest-file checksum
    # (§11.3). It NEVER trusts a claimed prevalidated Checkpoint B input: it re-evaluates
    # every applicable aggregate rule in its authoritative order. created_utc and
    # repository_commit are INERT supplied values: Checkpoint A validates only their
    # scalar grammar (§8.8); Checkpoint B owns any live acquisition or semantic
    # validation. No filesystem, authorization-bootstrap, clock, Git, or live-source
    # access. Supplied entries are already ordered by _order_population_entries.
    PRIV  raises(schema_error/duplicate_identity/language_crossover/
      source_identity_mismatch/manifest_mismatch/ordering_error)   B: _census_population_core
      (prepares entries + passes a separately approved CallhomeSourceApproval; the builder,
      not the census core, is the acceptance authority — it never returns a partial manifest)
```

**Not part of the Checkpoint A API (Checkpoint B only — do NOT implement in A):**

```text
census_approved_callhome_population(), verify_frozen_callhome_population() (nullary, §8.1);
_census_population_core (§8.3); _grant_capability, _require_valid (§8.2);
_bootstrap_repository_root (§8.6); the six-state publisher (§15); the verification
inspector (§11.4/§16.8); filesystem traversal; Path resolution; environment / Git /
clock lookup; archive access; and the CLI (§8.4). Checkpoint A adds NO API for
filesystem traversal, Path resolution, environment lookup, Git lookup, clock lookup,
authorization bootstrap, archive access, publication, live verification, cancellation,
or the CLI.
```

**Direct imports.** Tests and future consumers import Checkpoint A names **directly**
from `cslm.data.callhome_population` (e.g. `from cslm.data.callhome_population import
CallhomePopulationManifest, CallhomePopulationError`). **No `__init__.py` re-export is
required or added**; `src/cslm/data/__init__.py` is out of scope for both this
docs-only gate and Checkpoint A (§1.3). Private underscore helpers are imported from
the same module by Checkpoint A tests where a pure-function test needs one; the
underscore is a convention, not an export barrier (§8.2, §17.3), and no underscore
helper accepts a `Path` or exposes a path-accepting public surface (§6.1).

**Type-syntax constraint resolution — RULE A (chosen).** The preflight noted that
Checkpoint A restricts imports to `{hashlib, json, unicodedata, dataclasses}` (§6),
which could conflict with exact type signatures. This is resolved by **Rule A**: the
four-module import set is **preserved unchanged**, and every signature above is
expressed using **built-in Python 3.11+ typing only**:

```text
- built-in generics: tuple[...], dict[...], list[...]   (never typing.Tuple/Dict/List);
- built-in unions: X | Y, X | None                       (never typing.Optional/Union);
- built-in scalar/collection types and the module's own dataclass types;
- object for heterogeneous canonical-mapping values (dict[str, object]).
```

No signature requires `typing`, `collections.abc`, `re`, `datetime`, or any module
outside the four. The one operation that could tempt an extra import —
**real-calendar validation** of the fixed `YYYY-MM-DDTHH:MM:SSZ` timestamp grammar
(§8.8, "validated as an actual date-time") — is performed with **pure integer
range + leap-year arithmetic** over the parsed digit fields; it uses neither
`datetime` nor `re`. The §6 / §6.1 import-guard test
(`imports ⊆ {hashlib, json, unicodedata, dataclasses}`) therefore remains exactly as
already specified, with **no** added standard-library module. **Rule B** (expanding
the authorized import list) is explicitly **not** taken; there is no residual conflict
between the exact signatures and the authorized import set.

### 8.10 Checkpoint A defined type and record inventory (CHPA-P2-01)

Every dataclass and error type **defined in Checkpoint A** (`callhome_population.py`),
with definition ownership, Checkpoint A construction/use scope, any future Checkpoint B
use, persisted-vs-inert status, and privacy classification. "Persisted" means the type
(or a record embedding it) is written to a fixed JSON file (§7/§16); "inert" means
Checkpoint A defines the value type but Checkpoint A does not persist it.

```text
CallhomeSourceMember
  A: defines + constructs from supplied values    B: builds from live inventory
  persisted (nested in candidate/approval)        privacy LOC
CallhomeExtractionProcedure
  A: defines + constructs                         B: builds from live observation
  persisted (nested in each snapshot)             privacy PUB labels
CallhomeSourceSnapshot
  A: defines + constructs; identity() derivation  B: builds from live observation
  persisted (nested in candidate/approval)        privacy mixed (PUB labels + LOC archive/members)
CallhomeSourceSnapshotId
  A: defines; DERIVED via CallhomeSourceSnapshot.identity()   B: binding comparison
  persisted (nested in manifest)                  privacy mixed (PUB provider/language + LOC archive_sha256)
CallhomeCandidateSourceSnapshotRecord
  A: defines + strict-loads                       B: observation gate writes it (out of module)
  persisted (candidate_source_snapshot.json)      privacy LOC
CallhomeSourceApproval
  A: defines + strict-loads + checksums           B: _grant_capability loads/authenticates
  persisted (source_approval.json; checksum-bound)  privacy LOC
CallhomeCensusAuthorizationRecord
  A: defines + strict-loads + checksums           B: _grant_capability loads/authenticates
  persisted (census_authorization.json; checksum-bound)  privacy LOC
CallhomePopulationEntry
  A: defines + constructs                         B: builds from live enumeration
  persisted (nested in manifest)                  privacy LOC
CallhomePopulationCounts
  A: defines + derives/reconciles                 B: reconciles at re-verification
  persisted (nested in manifest/summary)          privacy aggregate (G3-eligible / LOC per §19)
CallhomePopulationManifest
  A: defines + constructs + strict-loads          B: builds live, publishes, verifies
  persisted (callhome_population_manifest.json; immutable)  privacy LOC
CallhomePopulationVerification
  A: DEFINES the inert frozen value type + redacted representation only (§16.10);
     A does NOT construct live results and exposes NO inspector
  B: verification inspector CONSTRUCTS it during live re-verification
  INERT / NOT persisted (in-memory result, local-only)
  privacy content-free; population_identity_sha256 is a privacy-safe local-only
    aggregate (§18.2/§19) — NOT a persisted manifest record
CallhomePopulationCensusSummary
  A: defines + constructs IN MEMORY (build_population_census_summary) + strict-loads
  B: publication deferred / governance-gated (§19)
  persisted (callhome_population_census_summary.json; LOCAL until G3)  privacy aggregate
CallhomePopulationError
  A: defines; raised across all failure surfaces (§18)   B: raised at B boundaries
  NOT persisted (exception type)                  privacy content-free (category only, §18.1/§18.7)
```

---

## 9. Deterministic enumeration algorithm (incl. base purity)

### 9.1 Order of operations

```text
 1. Bootstrap (§8.6) and authorization (§8.1 steps 1–4) — BEFORE project_root().
 2. project_root() == bootstrap root check (§8.6); resolve fixed base/roots/archive
    dir (§7). No caller paths.
 3. Base-purity check (§9.2).
 4. Archive confinement + verification (§10.7 then §10.4): validate the fixed
    archive directory membership and each approved basename, then rehash each
    approved archive and compare to approved archive_size_bytes/archive_sha256
    BEFORE trusting extracted files.
 5. Per language (eng, then spa): non-recursive scandir(follow_symlinks=False);
    classify each child by lstat; accept iff regular non-symlink file with exact
    lowercase ".cha" suffix and no hidden/temp/metadata pattern; else
    unexpected_entry (never skipped). Empty language population -> empty_population.
 6. For each accepted member: read bytes once; compute size + SHA-256; derive exact
    POSIX relative_path (§12) and conversation_id (§10.5).
 7. Construct candidate CallhomePopulationEntry values (§8.9 direct constructors:
    intrinsic/local only) and order them deterministically via _order_population_entries
    (§4.3). This step PREPARES inputs; it does not accept an aggregate.
 8. Call _build_population_manifest(source_approval=<accepted approval>,
    entries=<ordered candidate entries>, created_utc=<injected>,
    repository_commit=<injected>, source_approval_sha256=<bound>,
    census_authorization_sha256=<bound>). The BUILDER is the authoritative
    aggregate-acceptance boundary (§8.9, §16.9): from source_approval it derives the
    approved English/Spanish inventories and both snapshot IDs, then INDEPENDENTLY
    re-evaluates, in the exact §16.9 Phase-2 applicable order:
      (1)  intrinsic/local validity of the supplied typed values (schema_error);
      (2)  source-approval contract-version and checksum binding (source_identity_mismatch);
      (3)  derived snapshot-ID and source/manifest binding (source_identity_mismatch);
      (4)  snapshot n_members reconciliation (manifest_mismatch);
      (5)  population ordering and ordinal validation (§4.3 -> ordering_error);
      (6)  collision validation, preserving the §13.4 internal collision order
           (-> duplicate_identity);
      (7)  language-crossover detection (§13.5 -> language_crossover);
      (8)  ordinary approved-inventory membership comparison (§10.3 -> source_identity_mismatch);
      (9)  population-count derivation and reconciliation (§11.6 -> manifest_mismatch);
      (10) stable population-identity recomputation (§11.1 -> manifest_mismatch);
      (11) manifest-file checksum recomputation (§11.3 -> manifest_mismatch);
      (12) final accepted-manifest construction/return.
    The earliest applicable stage wins; §16.9 is the SOLE authoritative precedence
    contract and §9.1 defines no competing order. The census core does NOT independently
    establish ordering, collision, crossover, inventory, count, identity, or file-integrity
    acceptance. A builder raise aborts the census with that exact fixed category; no
    partial manifest is produced.
 9. Publish the builder-returned accepted manifest via the six-state no-overwrite machine
    (§15); refuse if the frozen manifest exists (frozen_output_exists).
10. Return only the builder-returned, published manifest.
```

Every abort yields no partial manifest object; publication failures follow §15.3.

**Failure precedence (normative — delegated to the builder).** The census core does
**not** define its own aggregate failure order; it surfaces exactly the fixed category
`_build_population_manifest` raises, and the **sole authoritative** aggregate failure
precedence is the builder's §16.9 Phase-2 order (ordering/ordinals **before**
collisions, crossover, and inventory):

```text
population ordering / ordinals (§4.3)                -> ordering_error
    before collisions (§13.4)                        -> duplicate_identity
    before language crossover (§13.5)                -> language_crossover
    before ordinary approved-inventory mismatch (§10.3) -> source_identity_mismatch
    before population counts (§11.6)                 -> manifest_mismatch
    before stable population identity (§11.1)        -> manifest_mismatch
    before manifest-file checksum (§11.3)            -> manifest_mismatch
```

The earliest applicable stage wins. If more than one collision class applies, the builder
fails with the first class in the exact §13.4 internal precedence (byte content →
conversation identity → NFC → NFD → case-fold). A duplicated or crossed member is reported
as the collision or crossover it is, never misreported as a bare inventory mismatch. §9.1
defines **no** separate order — §16.9 is the single precedence contract.

The census core **may** precompute per-language inventory lookup structures for
efficiency **only if**: the builder remains the normative acceptance authority; the
builder independently re-evaluates each check; the precomputation cannot alter any fixed
category or its precedence; and the only supported output is the builder-returned
manifest. Prefer one authoritative evaluation (the builder) over duplicate normative
validation in the census core.

### 9.2 Base-directory purity (three levels)

```text
project-relative base : data/raw/callhome
English root          : data/raw/callhome/eng
Spanish root          : data/raw/callhome/spa
```

After authorization, **before either language root is traversed**:

```text
1. lstat the base; require a real, non-symlink directory (else root_error).
2. Non-recursively enumerate the base WITHOUT following links.
3. Require its entries to be exactly {"eng", "spa"} — no more, no fewer.
4. Require both "eng" and "spa" to be real, non-symlink directories.
5. Reject every missing, additional, differently-cased, symlinked, or special
   entry.
```

Therefore each of these fails: missing `eng`; missing `spa`; an extra language
directory; an archive under `data/raw/callhome`; an approval/control file under
`data/raw/callhome`; a hidden base entry; uppercase `ENG`/`SPA`; a symlinked
language root; a special entry. Failures use `root_error` (base structure) or
`unexpected_entry` (an extra base child), both content-free.

---

## 10. Source-snapshot approval workflow (non-circular)

The expected member inventory is **created and independently approved by prior
gates**, never generated-and-trusted by the census itself.

### A. Candidate snapshot observation (a separately authorized metadata-only gate)

May: hash the approved local archive bytes; record archive size + SHA-256; execute
the **pinned, versioned extraction procedure**; produce the extracted member
inventory (exact member relative paths, sizes, SHA-256); write
`candidate_source_snapshot.json` (each snapshot carrying one
`CallhomeExtractionProcedure`). It **does not approve itself**. The extraction
procedure's fixed policy values:

```text
normalization_policy = "none_byte_for_byte"   (no re-encoding / path norm / case change)
destination_layout   = "eng_root_spa_root"    (eng members under eng, spa under spa)
overwrite_policy     = "empty_destination_no_overwrite"
member_path_policy   = "exact_posix_no_escape_strict_utf8" (reject escape / non-UTF-8)
```

### B. Independent approval (a separate independent review)

Verifies the candidate record against the approved official source, expected
language, provider metadata, archive identity, extraction-procedure identity, and
the member inventory. It **freezes** a canonical `source_approval.json` and its
canonical checksum `source_approval_sha256` (§14.2). Provider authenticity is
**governance-attested**: unless TalkBank supplies a cryptographically verifiable
signed artifact, the census can prove *byte-identity to an approved archive*, not
*that the archive is authentically TalkBank's*. No technical proof is claimed where
only governance provenance exists.

### C. Census authorization (a later human-approved gate)

`census_authorization.json` binds to `source_approval_sha256`, `contract_version`,
`population_schema_version`, and `approved_operation`. It is **not** generated
automatically by the census.

### D. Population census (this module, at run time)

Chosen non-circular contract (**the safer default**): **rehash each approved
archive from the fixed archive directory
(`data/processed/callhome_population/archives`, outside `data/raw/callhome`) and
verify it against the approved `archive_size_bytes`/`archive_sha256` before
enumerating and verifying the extracted transcripts.** The census trusts the frozen
`source_approval.json` for the *expected* inventory and independently re-derives the
*actual* inventory from disk, so approval and observation are never the same act.
The census **rejects**: altered archive / changed archive size / changed archive
digest; altered source approval (checksum mismatch); altered member inventory;
changed extraction-procedure identity; replayed authorization bound to a different
`source_approval_sha256`.

### 10.3 Member-set verification

Compare enumerated `(relative_path, size_bytes, sha256)` triples to the approved
`members`: `missing`, `extra`, `modified` (same path, different size/sha256),
`substituted` — each `source_identity_mismatch`. Provider and distribution_format
must equal the single approved values.

**Ownership (CHPA-R3-01).** This ordinary approved-inventory membership comparison is an
AGGREGATE / CROSS-RECORD acceptance check owned by `_build_population_manifest`
(§16.9 stage 19), which derives the approved inventories from
`source_approval.english.members` / `source_approval.spanish.members`. The Checkpoint B
census core prepares candidate entries and delegates to the builder (§9.1); it does not
independently accept membership. It is evaluated only at a boundary that actually
receives the approved source record (crossover §13.5 is the adjacent stage 18); a
persisted-manifest-only strict loader without that context skips it (§16.9).

### 10.5 Derived conversation identity (exact)

Because membership is non-recursive and requires an exact lowercase `.cha` suffix:

```text
filename        = the direct-child basename exactly as enumerated
stem            = filename with EXACTLY the final four characters ".cha" removed
                  (i.e., filename[:-4]); no other suffix, dot component, or
                  character is removed
conversation_id = f"{language}/{stem}"
```

Do not split on the first dot, remove any earlier dot component, normalize Unicode,
case-fold, or remove another suffix. The normative rule is direct removal of exactly
the final four characters, `filename[:-4]`, because that is the **explicitly selected
contract** — not because any alternative produces a different result for admitted
names.

**Factual correction (do not repeat the earlier error).** It is **not** true that
`Path.stem` mishandles multi-dot `.cha` names: `Path.stem` strips only the final
suffix, so for every admitted member (a name ending in exactly `.cha`)
`Path(filename).stem` equals `filename[:-4]` — e.g. `Path("a.b.cha").stem == "a.b"`.
The contract mandates `filename[:-4]` for explicitness and to avoid depending on
`pathlib` in the pure core (§6.1), **not** because `Path.stem` would compute a
different stem for admitted names. Examples (invented names):

```text
a.cha    → eng/a
a.b.cha  → eng/a.b
ñ.cha    → spa/ñ
x.txt.cha→ eng/x.txt
```

Equal stems across languages stay distinct via the language namespace. Duplicate
`conversation_id` aborts `duplicate_identity` (§13). Required tests: single-dot,
multi-dot, Unicode, equal eng/spa stems, and a name ending in another suffix before
`.cha`.

### 10.6 Which gate freezes what

```text
gate 8  (observation)          → writes candidate_source_snapshot.json
gate 9  (candidate review)     → reviews the candidate record
gate 10 (independent approval) → freezes source_approval.json + source_approval_sha256
gate 12 (human authorization)  → writes census_authorization.json
gate 13 (real census)          → writes callhome_population_manifest.json (immutable)
```

### 10.7 Archive path confinement and archive-directory purity

**Basename rules** (enforced when loading `candidate_source_snapshot.json` and
`source_approval.json`, and again before archive hashing) — each approved
`archive_filename` must be:

```text
a nonempty strict-UTF-8 string; exactly one basename (no directory component);
not "." or ".."; contains no "/"; contains no "\"; contains no NUL;
no drive letter or absolute-path syntax; no parent-traversal component.
```

The persisted filename is a **basename, never a path**. Any violation of these
basename/field-grammar rules is an **intrinsic/local field defect** → `schema_error`
(for both `source_approval.json` and `candidate_source_snapshot.json`; §8.8, §16.7).
This is a field-grammar check, **not** a source-identity comparison, so it does **not**
produce `source_identity_mismatch`.

**Archive-directory purity** — after authorization, before archive hashing:

```text
1. lstat the fixed archive directory; require a real non-symlink directory.
2. Non-recursively enumerate it WITHOUT following links.
3. Require its entries to be exactly the two approved archive basenames (one
   English, one Spanish) — no more, no fewer.
4. Require both entries to be direct, regular, non-symlink files.
5. Require the two basenames to be distinct.
6. Require the two filesystem identities to be distinct: different (st_dev, st_ino)
   where supported (guards hard-linked duplicates).
7. Require their approved archive digests to be distinct unless a later explicit
   source-governance decision approves otherwise.
8. Reject every unexpected, hidden, temporary, symlinked, nested, special, or extra
   archive-directory entry.
```

No approval, authorization, manifest, summary, or temporary census output may share
the archive subdirectory. The archive path is constructed **only** as
`fixed_archive_directory / validated_basename`, then re-checked by `lstat` without
following links; caller-supplied or record-supplied directories are never used.
Failures use `archive_verification_error` (archive-directory purity / filesystem identity
/ digest — a live Checkpoint B comparison) or `schema_error` (intrinsic archive_filename
basename/field-grammar defect at loading), all content-free.

Closure tests: absolute path / `../` traversal / nested path / forward- or
backslash / `"."` / `".."` / NUL rejected; symlink or special archive rejected;
same English/Spanish basename rejected; same inode via hard link rejected;
unexpected third archive rejected; hidden/temp archive entry rejected; changed
archive size or digest rejected.

Synthetic workflow test requirement: candidate snapshot → independent approval →
authorization → census, all over invented archives/trees.

### 10.8 Canonical source-member array ordering

Each source snapshot's `members` array (in `candidate_source_snapshot.json` and
`source_approval.json`) has a single canonical order:

```text
strictly ascending by the exact UTF-8 bytes of relative_path
(raw bytes; not locale collation; not NFC/NFD-folded; not case-folded)
```

Normative requirements:

```text
- relative_path is UNIQUE within each language snapshot (no two members share it);
- there are NO duplicate member entries;
- candidate observation CONSTRUCTS the members array already in canonical order;
- strict persisted-record loaders REJECT a noncanonical order (out-of-order or
  duplicate relative_path) with schema_error;
- strict loaders NEVER silently sort or repair persisted input — they reject it;
- serialization PRESERVES the validated canonical order (§14.1).
```

Because the array order is fixed and validated, the source-approval checksum
(`source_approval_sha256`, §14.2) binds **one unambiguous ordering of one
inventory**: two byte-identical inventories in different orders cannot both be
canonical, and only the canonical order round-trips (§14.3). This is the pure-core
ordering of §1.4 (Checkpoint A) applied to supplied member values; it uses the same
exact-UTF-8-byte key as population ordering (§4.3) but is a per-snapshot inventory
order, distinct from the eng-then-spa population order.

---

## 11. Population identity vs run metadata vs manifest-file integrity

### 11.1 Stable population identity

`population_identity_sha256` = SHA-256 over the canonical serialization (§14) of a
mapping containing **only** stable scientific fields:

```text
schema
schema_version
population_contract_version
provider
distribution_format
english_snapshot_id (identity-only; includes archive_sha256, n_members)
spanish_snapshot_id
logical_roots
ordering_contract_id
entries: ordered [ordinal, language, exact relative_path, size, sha256,
                  conversation_id]
counts: {n_english_files, n_spanish_files, n_total_files, english_total_bytes,
         spanish_total_bytes, total_bytes, n_zero_byte_files,
         all_identity_checks_passed}
```

It **excludes**: `created_utc`, any execution timestamp, `repository_commit`,
`retrieval_utc`, approval/authorization timestamps, operator, run identifier, and
any temporary filename. Same population, different run/commit → **same**
`population_identity_sha256`; any change to a member, ordering, snapshot identity,
schema, contract, or a count → **different** value.

### 11.2 Run/execution metadata (kept separate)

`created_utc`, `repository_commit`, `source_approval_sha256`,
`census_authorization_sha256`, `tool_version`, `execution_status` — describe the
run, not the population, and never feed `population_identity_sha256`.

### 11.3 Manifest-file integrity

`manifest_file_sha256` = SHA-256 over the canonical serialization of the **complete
manifest mapping excluding the `manifest_file_sha256` field itself** (covers stable
fields *and* run metadata). It is explicitly **not** the stable population identity.
Two complete manifest files produced at different times may have **different**
`manifest_file_sha256` while sharing the **same** `population_identity_sha256`.

### 11.4 Re-verification (`verify_frozen_callhome_population`) — Checkpoint B

Live re-verification uses a **separate, private, non-accepting verification
inspector** (§16.8), **not** the strict acceptance loader (§16.4). The inspector
structurally decodes and canonical-form–validates enough of the persisted record to
evaluate its integrity and its relationship to live authorized state, **without
treating the record as accepted merely because it decoded**. The distinction is the
CHC-P2-07 resolution: **structural / environmental / authorization / operational
failures raise** (no record); **evaluable integrity and equality failures return** a
`CallhomePopulationVerification` with explicit `False` Booleans.

```text
Stage R — RAISE without a record (comparison impossible/unsafe; §16.8, §18):
  manifest missing/unreadable; I/O failure; invalid UTF-8; UTF-8 BOM; duplicate JSON
  keys; NaN/Infinity; lone surrogate; non-object top-level; missing/unknown fields;
  wrong field types; invalid scalar grammar (incl. a malformed manifest_file_sha256
  value); invalid schema/unsupported version; invalid contract-field grammar;
  noncanonical persisted JSON bytes; authorization/bootstrap failure; unreadable or
  structurally invalid source_approval.json or census_authorization.json; filesystem
  traversal/hashing failure; archive-verification failure preventing a reliable live
  population result.
  → raise the existing fixed content-free category (§18); expose no protected value;
    produce NO verification record. KeyboardInterrupt/SystemExit preserved (§18.4).

Steps (only reached once Stage R has passed — structural decode + canonical-form
validation + authorization + live recomputation all succeeded enough to compare):
1. Read the existing frozen manifest (never write).
2. Recompute manifest_file_sha256 over the complete persisted mapping excluding
   manifest_file_sha256; compare to the persisted (grammar-valid) value
   → manifest_file_sha256_ok (True/False).
3. Re-run bootstrap/authorization, base purity, archive confinement + rehash,
   enumeration, and hashing (a failure here is a Stage-R raise, not a Boolean).
4. Recompute counts from live entries and reconcile (§11.6) → counts_reconciled.
5. Compare the exact current ordered entries to the persisted manifest entries
   → membership_matches (ordered entries ONLY; NOT stable-identity equality).
6. Recompute the stable population identity over ALL stable fields, using the
   AUTHENTICATED approved English/Spanish snapshot identities, the fixed
   schema/contract/logical-root/ordering values, the live ordered entries, and
   independently reconciled counts (§11.1); compare to the persisted
   population_identity_sha256 → population_identity_matches. An authenticated
   persisted-versus-approved snapshot-ID mismatch makes this False (it does NOT
   raise — §6/§16.7, CHC-P2-07).
7. Report repository-commit compatibility SEPARATELY (informational; never fatal).
8. Never rewrite the frozen manifest and never touch its timestamps.
Set ok == (manifest_file_sha256_ok and membership_matches
           and population_identity_matches and counts_reconciled)  (§11.7, §16.7).
Return a content-free CallhomePopulationVerification.
```

A stable-field change with unchanged entries (e.g. a differing or wrongly bound
snapshot identity, contract version, logical root, ordering contract, provider,
format, or schema version — where both records are structurally valid and
authentication/comparison completed) leaves `membership_matches == True` but sets
`population_identity_matches == False`, so `ok == False` — a **returned** result, not
a raise.

### 11.6 Counts are bound to entries (identity + reconciliation)

`counts` is a **canonical stable field** included in `population_identity_sha256`
(§11.1) and is also **strictly derived from and reconciled with `entries`** on
every construction, load, checksum validation, and re-verification:

```text
n_english_files      = count(entries where language == "eng")
n_spanish_files      = count(entries where language == "spa")
n_total_files        = len(entries)
english_total_bytes  = sum(size_bytes for eng entries)
spanish_total_bytes  = sum(size_bytes for spa entries)
total_bytes          = english_total_bytes + spanish_total_bytes
n_zero_byte_files    = count(entries where size_bytes == 0)
all_identity_checks_passed = True   (a persisted verified manifest never stores False)
```

Any mismatch between persisted counts and recomputed counts fails closed with
`manifest_mismatch` **before the manifest is accepted**, even if
`population_identity_sha256` and `manifest_file_sha256` were recomputed
consistently around the tampered counts (reconciliation is independent of the
checksums). Reconciliation is an AGGREGATE / CROSS-RECORD check (§16.7, CHPA-R3-01) and
runs at the named builder (`_build_population_manifest`), persisted-record strict
loading, and live re-verification — never in a direct dataclass `__post_init__`.

Required tampering tests (each must fail even when both checksums were recomputed
over the altered record): `n_english_files`, `n_spanish_files`, `n_total_files`,
`english_total_bytes`, `spanish_total_bytes`, `total_bytes`, `n_zero_byte_files`,
`all_identity_checks_passed`. Plus a test that reconciliation occurs at
construction, loading, and re-verification.

### 11.7 Identity and reconciliation closure (single contract)

The four checksums remain **distinct** and cover **distinct scopes**:

```text
source_approval_sha256      covers the COMPLETE canonical source-approval object
                            (§14.2; no field excluded).
census_authorization_sha256 covers the COMPLETE canonical authorization object
                            (§14.2; no field excluded).
population_identity_sha256  covers ONLY the enumerated stable scientific mapping
                            (§11.1; run metadata excluded, counts included).
manifest_file_sha256        covers the COMPLETE manifest EXCEPT its own
                            manifest_file_sha256 field (§11.3).
```

Count reconciliation (§11.6) is an **independent** check that runs at **every** point
the counts are handled:

```text
- _build_population_manifest   (Checkpoint A named builder: pure, over supplied entries)
- _load_population_manifest    (Checkpoint A strict loader: Phase-2 aggregate acceptance)
- build_population_census_summary (Checkpoint A named builder: in-memory aggregate summary, §19)
- live re-verification         (Checkpoint B: verify_frozen_callhome_population, §11.4)
```

Count reconciliation is an AGGREGATE / CROSS-RECORD check (§16.7, CHPA-R3-01): it is
owned by these named builders / loaders, never by a direct dataclass constructor.
Reconciliation is independent of the four checksums. Therefore **recomputing
`population_identity_sha256` and `manifest_file_sha256` around tampered counts does
NOT make the manifest acceptable**: the recomputed-checksum count-tampering tests
(§11.6) fail with `manifest_mismatch` because the persisted counts disagree with the
counts re-derived from `entries`, regardless of any internally consistent checksum
over the altered record. Stable population identity, run metadata, and file
integrity stay separated exactly as in §11.1–§11.3; this section only states their
closure as one contract.

---

## 12. Exact path preservation

The manifest preserves the **exact** POSIX relative-path string produced by
enumeration. The stored identity is **never** NFC-normalized.

```text
relative_path       : the exact Python str resolved from the filesystem entry,
                      POSIX "/" separators, relative to its root.
relative_path_utf8  : the exact UTF-8 encoding of relative_path, used for ordering
                      (§4.3) and identity. Need not be persisted as a second field
                      if deterministically derived, but ordering and identity use
                      the exact UTF-8 bytes of the stored relative_path, unnormalized.
```

NFC, NFD, and Unicode case-fold forms are transient comparison keys for collision
detection only (§13); they **never** replace the actual path identity in
serialization. Any relative-path string that cannot be encoded under strict UTF-8
is rejected (`unexpected_entry`). Required tests — **Checkpoint A** (pure, over
supplied string values): an NFD path string round-trips byte-for-byte through
canonical serialization; **same-language** NFC/NFD and case-fold path pairs fail as
collisions (§13.4), while **cross-language** normalization-/case-equivalent pairs do
**not** trigger those path-collision classes; ordering uses the exact UTF-8 bytes;
serialization does not rewrite the member identity. **Checkpoint B** (filesystem):
an NFD path re-resolves via the stored exact path on a real filesystem.

---

## 13. Duplicate and collision handling (incl. zero-byte boundary)

### 13.1 Policy and the removed generic class

Detected over the fully-enumerated member set (§9.1 step 7) using raw on-disk bytes
so NFC serialization can never mask a byte-level distinction. Every collision is an
abort (`duplicate_identity`); the census never dedups, shrinks, or merges.
Case/normalization folding is used **only to detect** a collision, never to rewrite
membership. Aborts name only the collision class (§18), never the offending paths
or digests. Collision detection itself is a **pure check over supplied member values**
(Checkpoint A, §1.4) — it needs no filesystem access.

**Removed class.** The former generic collision category **"duplicate normalized
path identity"** is **deleted** as an independent normative class. It is removed
because **no unique additional normalization algorithm was ever specified** for it,
and because the exact-path comparisons (raw UTF-8 bytes, NFC, NFD, case-fold) plus
exact `conversation_id` equality (§13.4) already cover every required deterministic
collision class. An unspecified "normalized path key" would be nondeterministic and
redundant. All test requirements and implementation-plan references use the exact
classes of §13.4 instead; no test may reference "duplicate normalized path identity".

### 13.2 Rationale

Colliding members indicate an upstream packaging/extraction fault. Silently keeping
one and dropping another would reintroduce the exact non-reproducible,
investigator-chosen reduction the census prevents (§5).

### 13.3 Zero-byte duplicate boundary (P3)

```text
one authorized zero-byte .cha file  : remains a population member; NOT removed by
                                      the census (counted in counts.n_zero_byte_files).
                                      It is later submitted to the strict reader (a
                                      separate gate), where it will fail closed —
                                      the reader's job, not the census's.
two or more authorized zero-byte     : all share the empty-input SHA-256 (the
 .cha files                            well-known SHA-256 of the empty byte string)
                                      and therefore trigger the standard duplicate-
                                      byte population stop (duplicate_identity).
```

Deliberate fail-closed behavior, not an automatic exclusion. Both cases are
required synthetic tests: one zero-byte file retained as a member; two zero-byte
files abort with `duplicate_identity`.

### 13.4 Exact retained collision classes (internal precedence order)

Over the observed population, detect exactly these classes (comparisons **detect
collisions only; they never rewrite stored membership**). The **path** collision
classes (NFC, NFD, case-fold) are **language-namespaced**: their comparison keys
carry the entry's `language`, so a path collision requires two entries in the **same**
language. Duplicate byte content stays **global** across English and Spanish;
duplicate conversation identity uses the already language-namespaced
`conversation_id` (§10.5).

```text
duplicate byte content (GLOBAL across eng and spa):
    two population entries have equal sha256

duplicate conversation identity (already language-namespaced via conversation_id):
    two entries have equal exact conversation_id
    (conversation_id = f"{language}/{filename[:-4]}", so equality already implies
     same language)

Unicode NFC collision (SAME language):
    NFC key = (language, unicodedata.normalize("NFC", relative_path))
    a collision exists only when two entries share a language, their exact
    relative_path UTF-8 bytes differ, and their NFC keys are equal

Unicode NFD collision (SAME language):
    NFD key = (language, unicodedata.normalize("NFD", relative_path))
    a collision exists only when two entries share a language, their exact
    relative_path UTF-8 bytes differ, and their NFD keys are equal

case-fold collision (SAME language):
    case-fold key = (language, relative_path.casefold())
    a collision exists only when two entries share a language, their exact
    relative_path UTF-8 bytes differ, and their case-fold keys are equal
```

A path collision (NFC / NFD / case-fold) exists **only when all three** hold:

```text
the language values are the same;
the exact relative_path UTF-8 bytes differ;
the transformed (language-namespaced) keys are equal.
```

Therefore equal or normalization-equivalent filenames across **different** language
roots (e.g. `eng/a.cha` and `spa/a.cha`, or a canonically equivalent Unicode pair
split across languages) do **not** constitute an NFC, NFD, or case-fold path
collision — they are permitted unless another independently defined rule applies
(global duplicate byte content §13.4, or language crossover §13.5). Exact stored
paths are **never** normalized, rewritten, or case-folded (§12); the transformed
keys are transient comparison keys only.

When more than one class applies, fail with the **first** in this exact internal
precedence (also §4.4, §9.1):

```text
1. duplicate byte content
2. duplicate conversation identity
3. Unicode NFC collision
4. Unicode NFD collision
5. case-fold collision
```

### 13.5 Exact language-crossover definition

Crossover is owned by `_build_population_manifest` (§16.9 stage 18, CHPA-R3-01), which
derives the approved inventories from `source_approval.english.members` /
`source_approval.spanish.members`. It is evaluated **after** the §13.4 collision checks
(stage 17) and **before** ordinary approved-inventory membership mismatch (§10.3,
stage 19). A persisted-manifest-only strict loader without the approved source record
cannot evaluate crossover and skips it (§16.9). For each observed entry under expected
language `L`, define its exact **member key**:

```text
member_key = (relative_path, size_bytes, sha256)
```

Let, from the approved inventory:

```text
same_language_inventory     = the approved member-key set for language L
opposite_language_inventory = the approved member-key set for the other language
```

Return `language_crossover` for an observed entry **only when**:

```text
observed_key NOT IN same_language_inventory
AND observed_key IN opposite_language_inventory
```

Otherwise an absent, extra, modified, or substituted member is **not** crossover; it
remains `source_identity_mismatch` (§10.3). Equal filenames, stems, or conversation
stems across languages do **not** by themselves constitute crossover — crossover
requires the full `(relative_path, size_bytes, sha256)` key to appear under the
opposite language and be absent under its own. External errors remain content-free
and reveal only the fixed failure category (`language_crossover` /
`source_identity_mismatch`), never paths, names, hashes, or records (§18).

---

## 14. Manifest serialization and checksums

### 14.1 Canonical serialization (used for every checksum and every persisted file)

```text
- UTF-8 bytes.
- json.dumps(..., sort_keys=True, ensure_ascii=False, separators=(",", ":")).
- Exactly one trailing "\n".
- String values serialized VERBATIM (no NFC/NFD normalization of any relative_path
  or identity string; §12).
- Array order is the census order for entries (already total).
```

### 14.2 Checksum procedures (over the exact complete mappings)

```text
source_approval_sha256      : SHA-256 over the canonical serialization of the FULL
                              CallhomeSourceApproval mapping (schema, schema_version,
                              contract_version, provider, distribution_format,
                              english, spanish, approved_by, approved_utc), with
                              english/spanish serialized as their full snapshot
                              mappings (including extraction_procedure and members).
                              No field excluded. This is what the authorization binds to.
census_authorization_sha256 : SHA-256 over the canonical serialization of the FULL
                              CallhomeCensusAuthorizationRecord mapping (schema,
                              schema_version, contract_version, population_schema_
                              version, approved_operation, source_approval_sha256,
                              approved_by, approved_utc).
population_identity_sha256  : SHA-256 over the canonical serialization of the
                              stable-fields mapping (§11.1) — run metadata excluded,
                              counts included.
manifest_file_sha256        : SHA-256 over the canonical serialization of the
                              complete manifest mapping EXCLUDING manifest_file_sha256;
                              inserted last before write.
```

These checksums are recomputed at two distinct boundaries with **different outcome
semantics** (CHC-P2-08; agrees with §11.4, §16.4, §16.7, §16.8, §18.2, §20.2):

**Strict acceptance loading (§16.4).** The strict manifest loader
(`_load_population_manifest`, §8.9) recomputes and **requires equality** for the manifest
checksum, stable identity, counts, and self-contained record invariants it can evaluate
from supplied canonical bytes. A mismatch at this acceptance boundary **raises** the fixed
content-free category assigned to that specific self-contained predicate by §8.9 / §16.9
— for the manifest loader, `manifest_mismatch` (snapshot `n_members` reconciliation, count
reconciliation, stable-identity recomputation, manifest-file checksum recomputation),
`duplicate_identity` (collision), `ordering_error` (ordering/ordinals), `schema_error`
(intrinsic), or `serialization_error` (canonicality) — and **returns no accepted
manifest**. Context-free loading does **not** authenticate source approval or
authorization: the manifest loader raises **no** `source_identity_mismatch` (from
approval-to-manifest binding or ordinary approved-inventory mismatch) and **no**
`authorization_error`. Those contextual categories belong only to boundaries that receive
and authenticate the required context (`_build_population_manifest` with a supplied
`source_approval`; the Checkpoint B `_grant_capability` boundary; the live verification
inspector, §11.4/§16.8). Each strict loader follows its exact §8.9 per-loader inventory;
there is no collective "all loaders raise the full set" rule.

**Live Checkpoint B verification (§11.4, §16.8).** Authorization validity and
structural validity are **prerequisites**. Authorization, bootstrap, malformed-record,
and structurally-unusable-input failures **raise** the appropriate fixed content-free
error and return **no** verification record (§11.4 Stage R). Once a structurally valid
comparison is possible, these recomputations become **returned Booleans**, not raises:

```text
manifest_file_sha256 mismatch                     → manifest_file_sha256_ok == False
ordered population-entry mismatch                 → membership_matches == False
stable population-identity mismatch, including an
  authenticated snapshot-ID binding mismatch      → population_identity_matches == False
count mismatch                                    → counts_reconciled == False
```

Each evaluable mismatch returns `CallhomePopulationVerification(ok=False)` per the
existing four-term formula (§11.7, §16.7); an evaluable manifest-file or
stable-population-identity mismatch does **not** raise during live verification.
`source_approval`/authorization authentication failure, structural record invalidity,
unsupported schema/version, and comparison-preventing operational failure remain in
the raise-without-record class (§11.4, §16.8, §18).

### 14.3 Strict JSON persistence boundary (exact)

The persisted-JSON boundary is exact and is a **pure Checkpoint A contract** (it
parses and reserializes supplied text/bytes; it opens no file). Persisted JSON must
be:

```text
strict UTF-8
no UTF-8 BOM
top-level object only (never a top-level array/scalar)
duplicate keys rejected at EVERY object depth (strict object hook; never last-wins)
NaN rejected
Infinity and -Infinity rejected
lone surrogates rejected
unknown fields rejected
missing fields rejected
canonical separators (",", ":")
sorted mapping keys
ensure_ascii=False
exactly one final LF ("\n")
```

**Strict loading is two-phase** (§16.9, CHPA-R2-03): it validates and canonicalizes over
the RAW parsed mapping **before** it constructs any invariant-enforcing typed record, so
a later-stage category can never preempt a serialization/canonicality failure.

```text
Phase 1 — structural raw-mapping acceptance (NO typed records constructed):
  1. validate input type; reject BOM; decode strict UTF-8; parse JSON with duplicate-key
     and NaN/Infinity/lone-surrogate rejection; require a top-level object; validate the
     exact nested field sets and the primitive container/scalar grammar (§8.8) over the
     RAW mapping, using raw-mapping validators;
  2. reconstruct canonical bytes DIRECTLY from the validated RAW mapping (§14.1);
  3. require BYTE-FOR-BYTE equality with the persisted input.
Phase 2 — ordered semantic construction (only after Phase 1 succeeds):
  4. construct the exact typed records via the §8.9 `_mapping_to_<record>` converters
     (JSON arrays → immutable tuples), each constructor enforcing only its
     intrinsic/local invariants, then the ordered aggregate / binding / reconciliation /
     ordering / collision / crossover / identity / checksum checks (§16.9 Phase 2).
```

No invariant-enforcing typed record is constructed before the Phase-1 canonical byte
comparison, so a Phase-2 category can never preempt a Phase-1 `serialization_error` /
`schema_error` (§16.9).

Noncanonical persisted input (unsorted keys, wrong separators, BOM, trailing bytes,
missing/extra final LF, noncanonical member order §10.8) is **rejected**
(`serialization_error` / `schema_error`, or `manifest_mismatch` where a checksum
binds the canonical form) — **never silently repaired**.

**Explicit mapping functions.** Every record and every nested value has an explicit
**typed bidirectional** converter pair; the single authoritative, exactly-named
converter inventory is the one pinned in **§8.9** (CHPA-R2-01) — this section defines
**no second converter rule** and points to §8.9 for names and types. The mapping is the
canonical identity/checksum surface. Normatively:

```text
dataclasses.asdict is NEVER the canonical identity or checksum contract.
```

The explicit mapping functions exist to prevent **schema-field drift and unintended
identity changes**: they fix exactly which fields enter the canonical mapping (and
thus each checksum §14.2 and identity §11), so adding, renaming, reordering, or
removing a dataclass field cannot silently change a serialized format or a stable
identity without a deliberate mapping-function edit. `dataclasses.asdict` — which
recurses automatically and mirrors declaration order — would couple identity to
incidental dataclass shape and is therefore never the identity/checksum contract; the
checksums (§14.2) and identities (§11) are computed over the explicit canonical
mappings only. This is stronger than merely avoiding declaration-order effects: it
guards the field **set** and semantics, not just field order.

**Canonicalize before approval.** Because strict loading (above) **never reformats an
already-approved artifact** — it rejects any noncanonical persisted input rather than
repairing it — independently prepared `source_approval.json` and
`census_authorization.json` records must be **canonicalized before** they are
approved/frozen and before their checksums are computed. An approver that freezes a
noncanonical artifact produces a file the census will later reject; canonicalization
is a pre-approval responsibility, not a load-time repair.

---

## 15. Immutable no-overwrite publication (six-state machine)

### 15.1 The frozen manifest is immutable once published

`callhome_population_manifest.json` must **never** be silently overwritten. A census
refuses if the final manifest already exists (`frozen_output_exists`) and directs
the caller to `verify_frozen_callhome_population()`. `os.replace` is **not** used
for the final manifest, because it silently overwrites. **Directly opening and
writing the final path with `O_EXCL` is NOT equivalent** to the link publication
and must not be used, because a reader could observe a partially written final
file; the final must appear only as a fully-written, fsynced artifact via an atomic
hard link.

### 15.2 Publication state machine

```text
STATE 0 — no temporary file
STATE 1 — temporary file exclusively created
STATE 2 — temporary bytes written, flushed, file-fsynced
STATE 3 — final hard link atomically created
STATE 4 — first directory fsync completed; final publication durable
STATE 5 — temporary hard link removed
STATE 6 — second directory fsync completed; cleanup durable; SUCCESS

Transitions:
0 → 1 : exclusive same-directory temp creation (os.open O_CREAT|O_EXCL|O_WRONLY)
1 → 2 : write canonical bytes; flush; os.fsync(temp fd)
2 → 3 : os.link(temp, final) — MUST fail with frozen_output_exists if final exists
3 → 4 : os.fsync(containing directory) to persist final-link creation
4 → 5 : os.unlink(temp name)
5 → 6 : os.fsync(containing directory) to persist temp-name removal
```

### 15.3 Result semantics

```text
Failure BEFORE STATE 3:
  category output_error; NO final manifest exists; temp removed where cleanup
  succeeds; a prior valid final (if any) is untouched.

Final already exists at 2 → 3:
  category frozen_output_exists; the existing final is never altered.

Failure AFTER STATE 3 but before STATE 6:
  a byte-complete final name may exist (the source temp was file-fsynced).
  DO NOT claim "no final artifact." Report the distinct category
  publication_verification_required, meaning:
    - the final, if visible, is byte-complete;
    - publication or cleanup durability may be uncertain;
    - the final must NOT be deleted, overwritten, or treated as success;
    - the next action is READ-ONLY manifest verification + explicit recovery review;
    - a residual temporary hard link is local protected material — never printed or
      committed; verification does not delete it; residual-temp cleanup is a
      separately bounded local recovery step AFTER verification.

Success:
  reported only after STATE 6.
```

Specific interruption cases (all → `publication_verification_required`): link
succeeds but first directory fsync fails; first directory fsync succeeds but temp
unlink fails; temp unlink succeeds but second directory fsync fails. Process
interruption after the link: on restart the census refuses overwrite
(`frozen_output_exists`) and directs to verification/recovery. Because `os.link`
fails when the final exists, the publication path can never alter a previous valid
final in any scenario.

### 15.4 Verification and repeated execution

Verification never writes, replaces, touches timestamps, or changes manifest bytes,
and never deletes residual temporary names. A second census against an existing
frozen manifest refuses (`frozen_output_exists`) and points to verification; it
never silently creates a new scientific population record. A future new snapshot
requires a new explicit approval/version gate, not an overwrite.

### 15.5 Cleanup and error precedence

```text
- A cleanup failure MUST NOT mask the primary failure: the primary content-free
  category is raised; a cleanup problem becomes a sanitized secondary local status,
  never replacing the primary error.
- Cleanup never prints protected paths or names.
- The production script catches approved ordinary exceptions at the top level and
  emits only a fixed governance-safe message + stable nonzero exit code; it never
  prints a traceback or protected detail.
- KeyboardInterrupt and SystemExit still propagate as the exact same object.
```

### 15.6 Required tests

Inject failure at every transition (temp create, write, flush, file fsync, link,
first directory fsync, temp unlink, second directory fsync) and assert exactly one
of: **no final exists**; **existing final preserved**; **byte-complete final exists
and `publication_verification_required`**; **durable successful final**. Also
assert: no partially-written final is ever visible; post-link failures never delete
the final; residual temp names are not printed; verification does not clean up or
rewrite; existing frozen manifest → `frozen_output_exists`; deterministic fixed
output filename; cleanup failure during another failure does not mask the primary.

---

## 16. Persisted record schemas

For **every** persisted record: a fixed filename; explicit `schema` and
`schema_version` fields; allowed and required fields; allowed values; canonical
serialization (§14.1); and fail-closed loading. The dataclass fields (§8.5), the
JSON fields here, and the checksum mappings (§14.2) are identical. **Loading rules
apply to all records:**

```text
unknown/extra field    → reject (schema_error)
missing required field → reject (schema_error)
duplicate JSON key     → reject (schema_error): the loader uses a strict object hook
                         that raises on repeated keys; JSON duplicate keys never
                         silently last-wins
wrong type             → reject (schema_error)
invalid enum value     → reject (schema_error)
unsupported schema id  → reject (schema_error)
unsupported schema_version → reject (schema_error)
non-canonical persisted bytes → reject (serialization_error at the Phase-1 canonical
                         comparison, §16.9 stage 11; the manifest loader never reaches a
                         checksum stage for noncanonical input)
```

**Per-loader categories, not a collective set (P2-03).** Beyond the shared schema_error /
serialization_error rules above, each loader raises **only** the categories in its exact
§8.9 per-loader inventory, realizable from the stages its API context can evaluate
(§16.9). A self-contained checksum/reconciliation mismatch in the manifest loader is
`manifest_mismatch` (snapshot `n_members`, count reconciliation, stable identity, and
manifest-file checksum — the §11.6/§11.1/§11.3 self-contained predicates); collision is
`duplicate_identity`; ordering is `ordering_error`. **Context-free loaders do not
authenticate source approval or authorization**, so they raise **no**
`source_identity_mismatch` from approval binding or approved-inventory mismatch and **no**
`authorization_error`; those contextual categories arise only at boundaries that receive
and authenticate that context (`_build_population_manifest`, `_grant_capability`, the live
verification inspector). Skipping an unevaluable contextual stage is not approval,
authorization, source matching, or live verification (§16.7, §16.9).

Manifest loading additionally runs the §11.6 counts reconciliation (a self-contained
`manifest_mismatch` predicate).

### 16.1 `candidate_source_snapshot.json` (gate 8; LOCAL ONLY)

`CallhomeCandidateSourceSnapshotRecord` (§8.5). `schema="callhome_candidate_source_
snapshot"`, `schema_version="1"`. Fields: `schema, schema_version, observed_utc,
provider, distribution_format, english{snapshot}, spanish{snapshot}`. Each snapshot
carries exactly one nested `extraction_procedure` and its `members`. Extraction
fields do **not** appear at the record's top level.

### 16.2 `source_approval.json` (gate 10; canonical, checksum-bound)

`CallhomeSourceApproval` (§8.5). `schema="callhome_source_approval"`,
`schema_version="1"`. `source_approval_sha256` is computed over the exact complete
canonical mapping, excluding no field (§14.2). Member inventory + archive identity
LOCAL ONLY; provider/corpus/citation labels are public facts (§19) but the file as
a whole stays local.

### 16.3 `census_authorization.json` (gate 12; checksum-bound)

`CallhomeCensusAuthorizationRecord` (§8.5). `schema="callhome_census_
authorization"`, `schema_version="1"`. Fields: `schema, schema_version,
contract_version, population_schema_version, approved_operation ("census"|"verify"),
source_approval_sha256, approved_by, approved_utc`. Must bind to the current
`source_approval_sha256` and its `population_schema_version` must equal the
manifest's `schema_version`, else authorization fails closed. LOCAL ONLY.

### 16.4 `callhome_population_manifest.json` (gate 13; immutable)

`CallhomePopulationManifest` (§8.5). `schema="callhome_population_manifest"`,
`schema_version="1"`. LOCAL ONLY (per-file identities, conversation ids, checksums).
No-overwrite publication (§15).

**Strict acceptance loader (accepts or raises).** The strict persisted-manifest
loader is an **acceptance boundary**: it validates `manifest_file_sha256` (§11.3),
the counts reconciliation (§11.6), the record-level invariants (§16.7 intrinsic
predicates + entry-count reconciliation), and the stable-identity recomputation
(§11.1), and on **any** required acceptance failure it raises a fixed content-free
error (§18) — it **never returns a partially accepted manifest**. It is the loader
used by Checkpoint A construction/loading tests and by any production path that
requires an accepted manifest object. It is **not** the live-verification inspection
path: `verify_frozen_callhome_population()` uses a separate, non-accepting inspector
(§11.4, §16.8) so that evaluable integrity mismatches become verification Booleans
rather than exceptions (CHC-P2-07).

### 16.5 `callhome_population_census_summary.json` (aggregate; LOCAL until G3)

`CallhomePopulationCensusSummary` (§8.5). `schema="callhome_population_census_
summary"`, `schema_version="1"`. LOCAL ONLY UNDER CURRENT POLICY; the specific
aggregate fields are ELIGIBLE FOR FUTURE G3 REVIEW — NOT CURRENTLY APPROVED (§19).

### 16.6 Strict loading + canonical vectors

Round-trip and malformed tests for each of the five records: valid round trip;
unknown / missing / duplicate-key / mistyped / unsupported-schema /
unsupported-version / invalid-enum / invalid-checksum / non-canonical → each a fixed
content-free failure. **Fixed invented canonical JSON test vectors** are required
for all five records, proving that the dataclass fields, the serialized JSON fields,
the checksum inputs, and the schema tables in this section are identical.

### 16.7 Record-level invariants (normative)

**Validation-ownership rule (CHPA-R3-01, authoritative — applied consistently in §8.9,
§14.3, §16.9, §20.1).** Record validation is owned by three distinct layers, and only
the third establishes aggregate acceptance:

```text
Direct Checkpoint A dataclass constructors (__init__ / __post_init__):
  - enforce exact field types; scalar grammar; the fixed schema, version, namespace,
    provider, language, and policy constants that belong to the individual record;
  - enforce local relationships among fields contained entirely within that record
    where the check needs NO population-wide ordering, comparison, reconciliation,
    recomputation, or approved external context (e.g. a summary's own local arithmetic;
    a snapshot's own members-array canonical order §10.8; n_members == len(members));
  - convert JSON arrays to immutable tuples where applicable;
  - NEVER establish aggregate persisted-record acceptance merely because construction
    succeeds.

Private _mapping_to_<record> converters:
  - validate exact mapping field sets and primitive/container types;
  - invoke the corresponding direct constructor;
  - enforce ONLY the same intrinsic scalar and local-field contract as that constructor;
  - NEVER enforce aggregate or cross-record acceptance rules; NEVER bypass or weaken
    constructor validation.

Named ordered builders and strict loaders (_build_population_manifest,
build_population_census_summary, _load_<record>, §8.9):
  - EXCLUSIVELY own aggregate and cross-record acceptance;
  - enforce source-approval / snapshot binding; snapshot n_members reconciliation;
    population ordering and ordinals; global and language-scoped collision rules;
    language crossover; approved-inventory membership where applicable; derive and
    reconcile population counts; recompute and validate stable population identity;
    recompute and validate manifest-file checksum;
  - return a fully accepted aggregate OR raise; NEVER return a partially accepted aggregate.
```

**Successful direct construction proves only intrinsic and local validity.** Successful
direct construction of `CallhomePopulationManifest`, `CallhomePopulationCensusSummary`,
or any other record proves ONLY its intrinsic and local validity. It does **not** prove
aggregate acceptance, persisted-file acceptance, authorization, source approval,
population reconciliation, canonical persistence, or live verification. An aggregate is
accepted through the supported module boundary **only** when it is returned by the
appropriate named builder or strict loader. There is **no** undocumented constructor
bypass, **no** factory-only hidden mode, and **no** validation-disable flag.

**Boundary terminology for the invariants below.** Each invariant is one of:

```text
INTRINSIC / LOCAL          — enforced by direct constructors and _mapping_to_<record>
                             converters; a violation is schema_error (unless §18.7 applies).
AGGREGATE / CROSS-RECORD   — enforced ONLY by the named ordered builder or strict loader;
                             NEVER assigned to a direct dataclass __post_init__; evaluated
                             during Phase 2 in the exact §16.9 order. Exactly these:
    approval-to-manifest snapshot binding; snapshot n_members versus language-specific
    entries; English-before-Spanish ordering; within-language bytewise ordering; ordinal
    sequence; global duplicate SHA-256; conversation-ID collision; NFC / NFD / case-fold
    collisions; language crossover; approved-inventory comparison; counts derived from
    entries; population-identity recomputation; manifest-file checksum recomputation.
```

Each per-record group below is enforced at its applicable boundary: **intrinsic / local**
items at direct construction and `_mapping_to_<record>` conversion; **aggregate /
cross-record** items ONLY at the named builder or strict loader (§16.9 Phase 2). At the
persisted-manifest strict loader the aggregate / cross-record invariants are the Phase-2
checks (§16.9, CHPA-R2-03): they run only after Phase-1 raw-mapping structural validation
and byte-for-byte canonical acceptance, so a Phase-1 serialization/canonicality failure
preempts them (§14.3, §16.9). The verification record is Checkpoint B.

**Applicability of the aggregate boundaries (CHPA-R3-01).** "Named aggregate-acceptance
boundaries exclusively own applicable checks" does **not** mean every strict loader
performs every aggregate check: a boundary performs a check only where its API actually
receives the required authenticated context. Concretely:

```text
_build_population_manifest — receives source_approval, so it OWNS language crossover
    (§13.5) AND ordinary approved-inventory membership comparison (§10.3) for construction
    from an approved source record, deriving the inventories from
    source_approval.english.members / source_approval.spanish.members, in addition to the
    self-contained checks.
_load_population_manifest — owns the self-contained manifest acceptance checks but does
    NOT fabricate an unavailable approved inventory; crossover and inventory membership
    are not evaluable from manifest bytes alone and are skipped (§16.9). Skipping an
    unevaluable contextual check is NOT acceptance of a real source population.
Checkpoint B census core — PREPARES inputs and INVOKES _build_population_manifest; it is
    NOT a separate unnamed aggregate-acceptance boundary (§9.1).
```

Direct constructors and `_mapping_to_<record>` converters remain intrinsic/local only and
own **none** of these aggregate checks (approved-inventory comparison and language
crossover included).

**Source snapshots** — INTRINSIC / LOCAL (`CallhomeSourceSnapshot`, both English and Spanish):

```text
each snapshot has at least one member (len(members) >= 1);
members satisfy the canonical ordering and uniqueness rules (§10.8);
CallhomeSourceSnapshotId.n_members == len(snapshot.members);
the identity view (CallhomeSourceSnapshotId) is DERIVED from the snapshot and is
  never accepted as an independent, contradictory description.
```

**Candidate snapshot and source approval** — INTRINSIC / LOCAL
(`CallhomeCandidateSourceSnapshotRecord`, `CallhomeSourceApproval`):

```text
top-level schema and schema_version equal their fixed constants (§8.7);
provider == PROVIDER;
distribution_format == DISTRIBUTION_FORMAT;
the english and spanish records satisfy their assigned language and provider
  contracts (§8.8: english.language == "eng", spanish.language == "spa",
  each snapshot provider == PROVIDER).
```

**Source-approval contract version (CHC-P2-04)** — INTRINSIC / LOCAL. At every
`CallhomeSourceApproval` construction and `_mapping_to_source_approval` boundary,
require **exactly**:

```text
schema == SOURCE_APPROVAL_SCHEMA;
schema_version == SOURCE_APPROVAL_SCHEMA_VERSION;
contract_version == POPULATION_CONTRACT_VERSION;
provider == PROVIDER;
distribution_format == DISTRIBUTION_FORMAT;
```

The existing English/Spanish source-snapshot language, provider, ordering (§10.8),
member, extraction-policy (§8.8), and canonicalization (§14.3) requirements are
retained unchanged. A source approval carrying **any other** `contract_version` is
**rejected** at direct construction / conversion with the established fixed content-free
`schema_error` (INTRINSIC / LOCAL: `contract_version == POPULATION_CONTRACT_VERSION` is a
local scalar-constant check). The `source_identity_mismatch` variant arises **only** at
the pure aggregate builder `_build_population_manifest`, which is supplied both the
`source_approval` value and the `source_approval_sha256` parameter and performs the
supplied-approval checksum, contract-version, source, and approved-inventory binding
checks assigned to it by §8.9 and §16.9; it does **not** arise at direct dataclass
construction, it is **not** raised by `_load_source_approval`, and it is **not** raised
by `_grant_capability` (see the boundary split below).
There is **no** silent upgrading, **no** fallback to another contract version, **no**
normalization of the value, and **no** caller-selected contract version. Because
`source_approval_sha256` is computed over the **complete** canonical source-approval
mapping (§14.2), the exact approved `contract_version` string is included in that
mapping and any change to it changes `source_approval_sha256`.

**Boundary-specific ownership of approval-related categories (P2-03-R1-R2, authoritative).**
The word "approval" appears in several distinct operations; they are separate boundaries
with distinct, **non-substitutable** error categories. No boundary emits another's
category, and there is no shared "approval-loading" category:

```text
_load_source_approval (context-free strict record loader, §8.9):
  - validates ONLY the intrinsic/local content of a supplied CallhomeSourceApproval
    mapping (structure, field types, fixed constants, archive_filename basename/grammar,
    canonical serialization);
  - receives NO expected checksum, NO authorization record, NO authenticated capability,
    NO population manifest, and NO live source state, so it performs NO expected-checksum
    comparison and NO authenticated source binding;
  - raises ONLY schema_error or serialization_error;
  - NEVER raises source_identity_mismatch and NEVER raises authorization_error.

_build_population_manifest (pure Checkpoint A aggregate-acceptance builder, §8.9/§16.9):
  - is SUPPLIED source_approval and source_approval_sha256 (plus candidate entries and
    explicit metadata/checksums);
  - performs the pure supplied-approval checksum, contract-version, derived-source, and
    approved-inventory binding checks;
  - raises source_identity_mismatch where assigned by §8.9 and the §16.9 order (in
    addition to language_crossover, manifest_mismatch, duplicate_identity, ordering_error,
    schema_error as already assigned);
  - NEVER raises authorization_error.

_grant_capability (Checkpoint B authorization/authentication/trusted-bootstrap and
capability-binding boundary, §17.1):
  - authenticates the census-authorization record and its own source_approval_sha256
    against the frozen approval, checks versions, trusted-bootstrap and capability-issuance
    conditions;
  - EVERY failure raises authorization_error (content-free) under §17.1;
  - NEVER raises source_identity_mismatch.
```

`source_approval_sha256` is checked at two different boundaries with two different
categories: the pure builder verifies the **supplied** `source_approval_sha256` against
`_source_approval_sha256(source_approval)` → `source_identity_mismatch`; `_grant_capability`
authenticates the **authorization record's** `source_approval_sha256` against the frozen
approval at Checkpoint B → `authorization_error`. These are distinct operations and are
never assigned to a shared owner.

**Census authorization** — INTRINSIC / LOCAL (`CallhomeCensusAuthorizationRecord`):

```text
schema and schema_version equal their fixed constants (§8.7);
contract_version == POPULATION_CONTRACT_VERSION;
population_schema_version == POPULATION_MANIFEST_SCHEMA_VERSION;
approved_operation is exactly one supported value ("census" | "verify");
source_approval_sha256 satisfies the exact SHA-256 grammar (§8.8).
```

(The authorization record's `source_approval_sha256` binding to the actual frozen
approval is AGGREGATE / CROSS-RECORD and is owned by `_grant_capability` — Checkpoint B —
not by this direct constructor. Every failure at that authorization/authentication
boundary is `authorization_error` under §17.1.)

**Population manifest** (`CallhomePopulationManifest`). This record's invariants split
across the two ownership layers:

*INTRINSIC / LOCAL* (direct constructor + `_mapping_to_population_manifest`; `schema_error`):

```text
schema == POPULATION_MANIFEST_SCHEMA;
schema_version == POPULATION_MANIFEST_SCHEMA_VERSION;
population_contract_version == POPULATION_CONTRACT_VERSION;
provider == PROVIDER;
distribution_format == DISTRIBUTION_FORMAT;
logical_roots == (ENGLISH_LOGICAL_ROOT, SPANISH_LOGICAL_ROOT);
ordering_contract_id == ORDERING_CONTRACT_ID;
tool_version == TOOL_VERSION;
execution_status == EXECUTION_STATUS;
entries are nonempty AND contain at least one English and at least one Spanish entry
  (a local existence check over the record's own entries tuple).
```

*AGGREGATE / CROSS-RECORD* (owned by `_build_population_manifest` or the strict manifest
loader `_load_population_manifest` only for the checks each boundary can evaluate,
§16.9 Phase 2 — **never** by the direct dataclass `__post_init__`):

```text
ordinals, ordering, collision checks, snapshot identities, and counts all reconcile
(§4.3, §11.1, §11.6, §13.4–§13.5); stable population identity and manifest-file
checksum are recomputed and validated (§11.1, §11.3). Supplied-approval binding is
contextual and belongs to `_build_population_manifest`; `_load_population_manifest`
does not receive an approval and cannot perform that binding.
```

Successful direct construction of a `CallhomePopulationManifest` value proves the
intrinsic / local group ONLY; aggregate acceptance is established solely by the builder
or strict loader returning the record.

**Manifest snapshot-ID predicates and reconciliation (CHC-P2-05).** The persisted
snapshot identities are **self-contained and exact**.

*Intrinsic scalar/namespace predicates* — INTRINSIC / LOCAL (direct constructor +
`_mapping_to_source_snapshot_id`; `schema_error`) — for `english_snapshot_id`:

```text
provider == PROVIDER;
language == "eng";
corpus_name satisfies its exact string predicate (§8.8);
public_release_label satisfies its exact string predicate (§8.8);
archive_sha256 satisfies the exact 64-lowercase-hex SHA-256 predicate (§8.8);
n_members is type int (not bool) and > 0.
```

for `spanish_snapshot_id`: the same, except `language == "spa"`.

*Entry-count reconciliation* — AGGREGATE / CROSS-RECORD (owned by
`_build_population_manifest` and the strict manifest loader, **not** the direct
dataclass constructor; **independent** of the general `counts` fields — both are
required):

```text
english_snapshot_id.n_members == count(entries where language == "eng");
spanish_snapshot_id.n_members == count(entries where language == "spa");
counts.n_english_files      == count(entries where language == "eng");
counts.n_spanish_files      == count(entries where language == "spa").
```

If either snapshot identity disagrees with the manifest entries, the manifest is
rejected at the builder / strict loader — independently of the `counts`-field
reconciliation (§11.6).

*Binding to the approved source snapshots (CHPA-R2-02)* — the pure builder
`_build_population_manifest` (§8.9) is **supplied** the approved `CallhomeSourceApproval`
as a value and **derives** the manifest snapshot IDs internally:

```text
english_snapshot_id = source_approval.english.identity();
spanish_snapshot_id = source_approval.spanish.identity();
require source_approval.contract_version == POPULATION_CONTRACT_VERSION;
require source_approval_sha256 == _source_approval_sha256(source_approval).
```

The builder **never accepts caller-supplied English or Spanish snapshot IDs**: the IDs
are derived, so there is no contradictory-ID case to compare or reject at construction.
(A persisted manifest loaded later without the approval object is checked by the
intrinsic snapshot-ID predicates and `n_members` reconciliation above; the
persisted-versus-approved binding is re-evaluated at live re-verification, below.)

*Enforcement boundaries* (CHC-P2-05, with CHC-P2-07 outcome semantics):

```text
- manifest construction (Checkpoint A, _build_population_manifest, §8.9) — ACCEPTANCE
  boundary: it is SUPPLIED the approved source_approval, DERIVES both snapshot IDs via
  identity() (accepting NO caller-supplied IDs), requires
  source_approval.contract_version == POPULATION_CONTRACT_VERSION and
  source_approval_sha256 == the canonical approval checksum, and reconciles derived
  n_members + entry counts over the supplied entries. A derivation / binding / checksum /
  contract-version failure RAISES the fixed content-free source_identity_mismatch (never
  returns a record).
- persisted-manifest strict loading (Checkpoint A, §16.4) — ACCEPTANCE boundary,
  where the full approval object is not necessarily supplied: intrinsic snapshot-ID
  predicates, language/provider correctness, n_members reconciliation with the
  manifest entries, and population-identity + manifest-file checksum verification. A
  failure RAISES a fixed content-free category (never returns a record).
- live re-verification (Checkpoint B, §11.4, §16.8) — INSPECTION boundary: after the
  non-accepting inspector structurally decodes the manifest and loads + authenticates
  the bound source_approval.json, the authenticated comparison
  persisted english_snapshot_id == approved English snapshot identity and
  persisted spanish_snapshot_id == approved Spanish snapshot identity is an
  EVALUABLE comparison. A mismatch there does NOT raise; it sets
  population_identity_matches == False (and hence ok == False) in the RETURNED
  CallhomePopulationVerification (§16.7 verification block, CHC-P2-07).
```

At the named builder, a supplied-approval contract/checksum/source binding failure
raises `source_identity_mismatch`; at the context-free strict manifest loader, a
self-contained snapshot-identity / `n_members` reconciliation failure raises
`manifest_mismatch`. Neither acceptance boundary is a direct dataclass `__post_init__`,
and neither returns or exposes a differing value. At **live re-verification**, the
authenticated persisted-versus-approved snapshot-ID comparison is a returned Boolean
(`population_identity_matches == False`, `ok == False`), never a raise — this is the
CHC-P2-07 resolution of the prior raise-versus-return conflict.

**Summary** (`CallhomePopulationCensusSummary`). This record's invariants split across
the two ownership layers:

*INTRINSIC / LOCAL* (direct constructor + `_mapping_to_population_census_summary`;
`schema_error`) — validates only the supplied fields:

```text
schema == CENSUS_SUMMARY_SCHEMA;
schema_version == CENSUS_SUMMARY_SCHEMA_VERSION;
provider == PROVIDER;
all_identity_checks_passed is exactly True;
local summary arithmetic contained entirely in the record
  (n_total_files == n_english_files + n_spanish_files;
   total_bytes == english_total_bytes + spanish_total_bytes).
```

*AGGREGATE / CROSS-RECORD* (owned ONLY by the named builder
`build_population_census_summary(manifest)`, §8.9 — **not** the direct dataclass
constructor):

```text
all summary counts and population_identity_sha256 are DERIVED FROM and RECONCILED WITH
  the accepted manifest (§11.6). A mismatch raises manifest_mismatch at the builder.
```

**Verification record — Checkpoint B** (`CallhomePopulationVerification`,
CHC-P2-06). The record includes, at minimum:

```text
ok: bool
population_identity_sha256: str
manifest_file_sha256_ok: bool
membership_matches: bool
population_identity_matches: bool
counts_reconciled: bool
repository_commit_compatible: bool
checked_utc: str
```

Field definitions (Boolean responsibilities kept separate and explicit):

```text
manifest_file_sha256_ok:
    the complete persisted manifest-file checksum is valid (§11.3).
membership_matches:
    the exact current ordered population entries match the persisted manifest
    entries. (This does NOT implicitly include stable-population-identity equality.)
population_identity_matches:
    the recomputed stable population identity equals the persisted
    population_identity_sha256 after ALL stable fields, snapshot identities, entries,
    ordering, and reconciled counts are recomputed (§11.1).
counts_reconciled:
    all persisted counts independently equal counts derived from the current
    entries (§11.6).
```

The fatal conjunction (four terms):

```text
ok == (
    manifest_file_sha256_ok
    and membership_matches
    and population_identity_matches
    and counts_reconciled
)
repository_commit_compatible is INFORMATIONAL only and does NOT affect ok.
```

Therefore a **stable-population-identity mismatch** makes
`population_identity_matches == False` and `ok == False` **even when**
`membership_matches == True`, `counts_reconciled == True`, and
`manifest_file_sha256_ok == True` — for example when the entries are unchanged but a
stable field (source snapshot identity, contract version, logical root, ordering
contract, provider, format, or schema version) differs.

**Outcome model (CHC-P2-07).** The verification record is **returned** only for
**evaluable** comparison outcomes — the four Booleans above are set to `True`/`False`
after structural decode, canonical-form validation, authorization, and live
recomputation have all succeeded enough to compare (§11.4 steps 1–8). A
**structural, environmental, authorization, or operational** failure — where no
reliable comparison can be produced (§11.4 Stage R; §16.8) — instead **raises** the
existing fixed content-free error (§18) and returns **no** record. In particular, an
authenticated persisted-versus-approved snapshot-ID mismatch during live verification
is an evaluable comparison and is **returned** (`population_identity_matches == False`,
`ok == False`), **not** raised; `source_identity_mismatch`/`manifest_mismatch` remain
the outcome only at the strict acceptance / construction / structurally-invalid
boundaries (§16.4, §16.7 enforcement boundaries).

Verification-record construction, the non-accepting inspector (§16.8), and their
tests **remain in Checkpoint B** (they require live re-verification of a frozen
manifest, §11.4); only the pure type/schema contract of the record is described
earlier (§8.5, §16.7).

### 16.8 Strict acceptance loader versus verification inspector (CHC-P2-07)

Two distinct persisted-manifest paths exist. They are **not** interchangeable:

```text
strict manifest loader (§16.4) — Checkpoint A:
    accepts or raises;
    never returns an invalid or partially accepted manifest;
    used by construction/loading tests and any production path that needs an
    accepted manifest object.

verification inspector (§11.4) — Checkpoint B, PRIVATE:
    structurally decodes and canonical-form-validates WITHOUT accepting;
    RAISES a fixed content-free error when comparison is impossible or unsafe
      (structural / environmental / authorization / operational failure, §11.4
       Stage R) and returns no record;
    RETURNS CallhomePopulationVerification with explicit False Booleans when
      comparison is possible and an integrity/equality check fails.
```

Normative constraints:

```text
- The verification inspector is PRIVATE to Checkpoint B live verification. It is
  NOT exposed as a general public manifest loader, and no other production path may
  use it to bypass strict acceptance.
- verify_frozen_callhome_population() must not call the strict acceptance loader in a
  way that turns an evaluable integrity mismatch into a raise; evaluable mismatches
  must surface as verification Booleans.
- The public nullary verification API remains verify_frozen_callhome_population()
  (§8.1). The inspector is a private helper beneath it.
- A decoded record is NEVER treated as accepted merely because it decoded.
- Do not add the inspection implementation or its API in Checkpoint A.
```

### 16.9 Strict acceptance loader stage order and failure precedence (CHPA-P2-02)

The strict acceptance loader of §16.4
(`_load_population_manifest(data: str | bytes) -> CallhomePopulationManifest`, §8.9)
runs **one total, deterministic** pipeline in **two phases** (CHPA-R2-03): **Phase 1**
performs all structural raw-mapping validation and the canonical byte comparison over
the RAW parsed mapping, **before** any invariant-enforcing typed record is constructed;
**Phase 2** performs ordered semantic construction and acceptance. It accepts one
supplied in-memory `str` or `bytes` value and either **returns one fully accepted
`CallhomePopulationManifest`** or **raises exactly one fixed content-free
`CallhomePopulationError`** (§18) — it **never** returns a partial, repaired, or invalid
record. Each stage has **one fixed error category**; on failure the loader raises that
category and **no later stage runs**, so **no later category is observable**. When
several defects coexist, the **earliest stage wins**: the reported category is that of
the earliest failing stage, never a later one.

| Phase | # | Stage | Fixed category on failure | Later stages reachable? |
|---|---|---|---|---|
| 1 | 1 | input-type validation (`str` or `bytes` only) | `schema_error` | no |
| 1 | 2 | UTF-8 BOM rejection | `serialization_error` | no |
| 1 | 3 | strict UTF-8 decoding (`bytes` → `str`) | `serialization_error` | no |
| 1 | 4 | JSON parsing (well-formed JSON) | `schema_error` | no |
| 1 | 5 | duplicate-key rejection (every object depth) | `schema_error` | no |
| 1 | 6 | non-finite-number rejection (NaN, Infinity, -Infinity) | `schema_error` | no |
| 1 | 7 | top-level-object requirement (not array/scalar) | `schema_error` | no |
| 1 | 8 | exact nested field-set validation over the RAW mapping (no missing, no unknown, at every depth) | `schema_error` | no |
| 1 | 9 | primitive container + scalar-grammar validation over the RAW mapping (bool-as-int reject; JSON string/number/bool types; array shapes; enums; schema/version; SHA-256 / timestamp / commit grammar §8.8) | `schema_error` | no |
| 1 | 10 | canonical byte reconstruction from the validated RAW mapping (re-encode per §14.1) | `serialization_error` | no |
| 1 | 11 | byte-for-byte canonicality comparison (reserialized raw mapping == input) | `serialization_error` | no |
| 2 | 12 | typed value/record construction via the §8.9 `_mapping_to_<record>` converters and the direct dataclass constructors (JSON arrays → immutable tuples; they enforce ONLY intrinsic/local scalar invariants per §16.7/CHPA-R3-01 — NO aggregate category is emitted here; aggregate/cross-record categories belong to stages 14–22) | `schema_error` | no |
| 2 | 13 | intrinsic record invariants (§16.7: fixed-constant fields; ≥1 eng and ≥1 spa entry; snapshot-ID scalar/namespace predicates; `n_members` type & > 0; canonical member ordering §10.8 where a members array exists) | `schema_error` | no |
| 2 | 14 | source-snapshot / manifest binding invariants — **conditional**: only where an approved source identity is available (builder: derive IDs from the supplied `source_approval` + verify `source_approval_sha256`/contract version; verification: authenticated compare) | `source_identity_mismatch` | no |
| 2 | 15 | source-snapshot `n_members` reconciliation (`english/spanish_snapshot_id.n_members` == per-language manifest-entry counts) | `manifest_mismatch` | no |
| 2 | 16 | population ordering + ordinal validation (§4.3: total eng-then-spa order; ordinals 0..N-1 consecutive, no gaps/dups) | `ordering_error` | no |
| 2 | 17 | collision validation (§13.4 internal precedence: byte → conversation → NFC → NFD → case-fold) | `duplicate_identity` | no |
| 2 | 18 | language-crossover validation — **conditional**: where the approved source inventory is available (builder: derived from `source_approval.english/spanish.members`; §13.5) | `language_crossover` | no |
| 2 | 19 | ordinary approved-inventory membership comparison — **conditional**: where the approved source inventory is available (each candidate key present in its own-language approved inventory; §10.3) | `source_identity_mismatch` | no |
| 2 | 20 | population-count reconciliation (§11.6: all eight count fields == derived-from-entries) | `manifest_mismatch` | no |
| 2 | 21 | stable population-identity recomputation (§11.1) == persisted `population_identity_sha256` | `manifest_mismatch` | no |
| 2 | 22 | manifest-file checksum recomputation (§11.3) == persisted `manifest_file_sha256` | `manifest_mismatch` | no |
| 2 | 23 | final acceptance (return the manifest) | — (returns) | — |

**Precedence properties (all guaranteed by the two-phase order above):**

```text
- Phase-1 structural or canonicality failure ALWAYS wins before ANY Phase-2 category.
  No invariant-enforcing typed record is constructed in Phase 1, so no Phase-2 category
  (construction schema_error, source_identity_mismatch, manifest_mismatch,
  ordering_error, duplicate_identity, language_crossover) can preempt a Phase-1
  serialization_error / schema_error. In particular, a noncanonical persisted manifest
  fails at stage 11 (serialization_error) and NEVER reaches any Phase-2 stage — it is
  never reported as manifest_mismatch. This removes the §14.3 "serialization_error OR
  manifest_mismatch, implementer's choice" ambiguity for the manifest, deterministically.
- Malformed or noncanonical serialization (stages 2, 3, 10, 11 → serialization_error)
  therefore always precedes every checksum-acceptance stage (20–22 → manifest_mismatch).
- Within Phase 2 the exact order remains authoritative: global duplicate-byte collision
  precedes conversation and path collisions, path collisions ordered NFC → NFD →
  case-fold, ALL inside stage 17 in the §13.4 internal precedence (byte → conversation →
  NFC → NFD → case-fold); collision (stage 17) precedes language-crossover (stage 18);
  language-crossover (stage 18) precedes ordinary approved-inventory membership mismatch
  (stage 19, §10.3, source_identity_mismatch). Stages 18 and 19 are **owned by
  `_build_population_manifest`** (which derives the approved inventories from
  `source_approval.english/spanish.members`) and by any acceptance boundary that actually
  receives the approved source context — they are **not** a separate unnamed
  Checkpoint B census-pipeline comparison outside the builder. The loader's stage 14 is
  the distinct structural snapshot-ID BINDING invariant (same category). Ordering and
  ordinal failure have the single fixed position stage 16; count reconciliation, stable
  identity, and manifest-file checksum keep the fixed relative order 20 → 21 → 22.
```

**Coexisting defects — earliest stage wins.** When multiple defects are present, the
loader raises the earliest failing stage's category and no later category is
observable. Examples: a manifest that is both noncanonical (stage 11) and carries a
wrong `manifest_file_sha256` (stage 22) raises `serialization_error` and never
constructs a typed record or evaluates stage 22; a manifest that both collides
(stage 17) and crosses over (stage 18) raises `duplicate_identity`; a member that both
crosses over (stage 18) and would otherwise be an own-inventory mismatch (stage 19)
raises `language_crossover`; a manifest whose counts are tampered (stage 20) and whose
stable identity was recomputed around the tamper (stage 21) raises `manifest_mismatch`
at stage 20. This holds for every combination.

**Builder versus strict loader (CHPA-R2-02 / CHPA-R3-01).** `_build_population_manifest`
(§8.9) **constructs** a manifest from a SUPPLIED `CallhomeSourceApproval` + supplied
entries + inert run metadata: it derives both snapshot IDs **and the approved
English/Spanish inventories** from the approval, and runs the Phase-2
construction/acceptance checks (stages 12–23) over the values it is handed — including
crossover (18) and ordinary approved-inventory membership (19), which it CAN and MUST
perform because it holds the approved inventories. It performs no Phase-1 byte parsing
because it receives typed inputs, not persisted JSON. `_load_population_manifest` (§16.4)
**accepts** a persisted manifest `str`/`bytes`, running Phase 1 then Phase 2, but its API
receives **no** approved source record, so it evaluates only the **self-contained**
manifest checks and skips the contextual stages 14, 18, and 19 (below). Both are
Checkpoint A pure and never return a partial or invalid record.

**Conditional stages 14, 18, and 19.** These run only where the approved source
identity / inventory is actually available to the boundary: `_build_population_manifest`
is SUPPLIED the approval, DERIVES the snapshot IDs and the approved inventories, and
therefore evaluates stage 14 (derivation + `source_approval_sha256`/contract-version
binding → `source_identity_mismatch`), stage 18 (crossover → `language_crossover`), and
stage 19 (ordinary own-inventory membership → `source_identity_mismatch`); a live
verification path evaluates them against the authenticated approval. For a pure
persisted-manifest-only load with **no** approved source context, stages 14, 18, and 19
are **not evaluable** and are skipped; the intrinsic snapshot-ID predicates (stage 13,
`schema_error`) and `n_members` reconciliation (stage 15, `manifest_mismatch`) still bind
the persisted snapshot IDs to the manifest's own entries, and every self-contained check
(collision 17, ordering 16, counts 20, identity 21, file checksum 22) still runs.
**Skipping an unevaluable contextual comparison is NOT equivalent to accepting or
approving a real source population** — it merely reflects that the loader's API lacks the
required approved-inventory context. No stage is skipped for any other reason, and
skipping a conditional stage never changes the category or position of any other stage.

**Non-manifest record loaders.** The per-record strict loaders `_load_source_approval`,
`_load_census_authorization`, `_load_candidate_source_snapshot`, and
`_load_census_summary` (§8.9) run Phase 1 (stages 1–11) then the applicable Phase-2
intrinsic construction and invariants (stages 12–13) for their own schema; they carry
no population entries, so stages 16–22 do not apply. Canonical source-member ordering
(§10.8; out-of-order or duplicate `relative_path`) is validated at stage 13 with
`schema_error`. This subsection does not weaken §16.4, §16.6, or §16.7; it fixes their
two-phase order and per-stage category.

### 16.10 `CallhomePopulationVerification` checkpoint ownership (CHPA-P2-03)

The ownership of `CallhomePopulationVerification` across the two checkpoints is
**normative and unambiguous**:

```text
Checkpoint A:
  - DEFINES the inert frozen value type CallhomePopulationVerification (§8.5 fields;
    §8.10 inventory) and its privacy-safe representation contract (§18.5/§18.6:
    frozen=True, slots=True, eq=True, field(repr=False), fixed __repr__ rendering
    ClassName(<redacted>), generated hash).
  - Does NOT construct live verification results.
  - Exposes NO verification inspector and NO nullary verification production API.

Checkpoint B OWNS:
  - verify_frozen_callhome_population() (the nullary public API, §8.1);
  - the private verification-specific inspector (§11.4, §16.8);
  - filesystem / live recomputation (bootstrap, authorization, traversal, hashing,
    archive verification);
  - authorization and bootstrap;
  - construction of CallhomePopulationVerification during live verification;
  - the Checkpoint B behavioral tests for returned records and raise-without-record
    outcomes (§20.2).
```

**Checkpoint A tests of the type may verify ONLY** its inert, in-memory properties:

```text
field order; field types; immutability (frozen); slots + absence of __dict__;
hash behavior; equality behavior; redacted repr/str; constructor-level scalar
invariants (the §8.8 field predicates the constructor enforces).
```

Checkpoint A **must not test or simulate live verification execution** — no synthetic
manifest re-verification, no Boolean-outcome simulation, no inspector behavior. Those
are Checkpoint B (§20.2 "Live re-verification" blocks).

**Defining the inert type in Checkpoint A authorizes nothing else.** Declaring
`CallhomePopulationVerification` in Checkpoint A does **not** authorize the Checkpoint B
inspector, `verify_frozen_callhome_population()`, or any nullary production API, and it
does not move any live-verification capability into Checkpoint A. The type is a value
container; its live producer, its inspector, and their tests remain Checkpoint B
(§11.4, §16.7, §16.8, §1.4).

---

## 17. Authorization control (detailed)

### 17.1 Mechanism

```text
- Bootstrap (§8.6) derives the repo root from __file__ and validates fixed tracked
  markers, WITHOUT touching data/raw.
- _grant_capability(control_dir) then:
    1. loads census_authorization.json from the fixed control dir;
    2. validates schema/schema_version/operation, versions, and its canonical
       checksum;
    3. loads source_approval.json; verifies source_approval_sha256 matches the
       approval's canonical checksum;
    4. checks contract_version and that population_schema_version equals the target
       manifest schema_version;
    5. stamps the module sentinel into the frozen capability. Any failure raises
       authorization_error (content-free).
- Public entry points call the bootstrap + _grant_capability BEFORE project_root()
  and BEFORE any corpus/archive traversal; a missing/invalid authorization refuses
  there. After granting, project_root() is required to equal the bootstrap root.
- The script additionally requires the explicit human-confirmation flag AND a
  successful opaque authorization; the flag alone authorizes nothing.
```

### 17.2 What it proves / does not prove

```text
Proves : a human deliberately created census_authorization.json binding (by
         canonical checksum) to a specific independently-frozen source approval,
         and ran the fixed runner with an explicit self-describing flag.
Does NOT prove : the archives are authentically TalkBank's (governance G1/G2; only
         byte-identity to an approved archive is technically proven); that any
         transcript is monolingual (later validation); or Decision B commit
         permission (G3).
```

### 17.3 Supported-interface boundary (accurate threat model)

```text
- Leading underscores are a Python CONVENTION, not access control. Code that
  deliberately imports or introspects private module internals CAN read
  _CAPABILITY_SENTINEL and construct a valid-looking capability. That is
  UNSUPPORTED and OUTSIDE this project's threat model.
- The capability is a supported-interface authorization boundary / accidental-
  misuse guard / normal production-path control. It ensures the nullary public API
  cannot be driven into real traversal by ordinary calling code, a stray import, a
  CLI typo, or a wrong working directory.
- This is NOT cryptographic isolation and does NOT protect against hostile code
  already executing inside the Python process. No claim of "unforgeable against
  external Python code" is made.
- Preserved: nullary public entry points; fixed locations; checksum-bound records;
  the private test seam; the CLI uses only supported entry points.
- Tests verify the supported production path (allow-path + refuse-before-traversal),
  NOT impossible hostile-process isolation.
```

### 17.4 Closure tests

```text
public production functions expose no roots/output/write/glob/subset/provider args
a lookalike _CensusCapability built via public fields does not authorize traversal
missing/invalid authorization refuses BEFORE project_root(), before loading any
  record beyond the authorization/approval records, before root resolution/traversal
CWD change to a dir holding a lookalike authorization record has no effect
project_root()/bootstrap mismatch fails before archive/corpus traversal
the script drives only the nullary entry point; never the private core
```

No authorization is granted by this design gate.

---

## 18. Error and privacy contract (complete coverage)

### 18.1 Closed content-free category taxonomy

```text
environment_error            root_error                 unexpected_entry
source_identity_mismatch     manifest_mismatch          empty_population
language_crossover           duplicate_identity         ordering_error
serialization_error          output_error               authorization_error
privacy_error                schema_error               frozen_output_exists
archive_verification_error   publication_verification_required
```

Each is a fixed string carried alone by `CallhomePopulationError(category)`. A
category names the failing **check**, never the offending item.

### 18.2 Coverage: every operation maps to a content-free category

```text
bootstrap marker validation → environment_error
project_root/bootstrap mismatch → environment_error
_load_source_approval loading (structural / serialization / intrinsic-local)
                            → schema_error / serialization_error (NEVER source_identity_mismatch,
                              NEVER authorization_error)
_build_population_manifest supplied-approval contract / checksum / source / inventory binding
                            → source_identity_mismatch (§8.9, §16.9; NEVER authorization_error)
_grant_capability authorization / authentication / trusted-bootstrap / capability binding
                            → authorization_error (§17.1; NEVER source_identity_mismatch)
base enumeration            → root_error / unexpected_entry
archive-dir purity / filesystem identity → archive_verification_error (live Checkpoint B)
archive_filename basename / field grammar → schema_error (intrinsic field defect §8.8/§10.7;
                                 NOT source_identity_mismatch)
archive hashing / verify    → archive_verification_error
member hashing              → source_identity_mismatch; read failure →
                              environment_error/root_error (no path)
counts reconciliation       → manifest_mismatch (at strict acceptance / construction)
JSON parsing / duplicate key → schema_error
canonical serialization     → serialization_error
temp-file creation / write / flush / file fsync → output_error
link publication            → frozen_output_exists (exists) / output_error (other)
post-link durability (dir fsync / unlink / dir fsync) → publication_verification_required
cleanup                     → sanitized secondary status; never masks primary (§15.5)
top-level script handling   → fixed governance-safe message + stable nonzero exit
live verification (§11.4/§16.8) — two outcome classes (CHC-P2-07):
  comparison impossible/unsafe (structural/env/auth/operational, Stage R) → RAISE the
    mapped fixed content-free category above (schema_error / serialization_error /
    authorization_error / environment_error / archive_verification_error / …), NO record;
  evaluable integrity/equality mismatch (incl. authenticated snapshot-ID mismatch) →
    RETURN a content-free CallhomePopulationVerification with the relevant Boolean
    False and ok == False (NOT a raise).
```

**"Approval" is not one boundary (P2-03-R1-R2).** The three approval-related rows above
are distinct boundaries with distinct, non-substitutable categories; there is **no**
shared "authorization/approval loading" operation and **no** generic "approval loading"
category. `_load_source_approval` performs no authentication and no expected-checksum
comparison (→ `schema_error` / `serialization_error` only); among these three boundaries,
only `_build_population_manifest` emits `source_identity_mismatch`, and only
`_grant_capability` emits `authorization_error`. See §16.7 for the authoritative
boundary split.

The returned verification record remains **content-free** with respect to paths,
filenames, archive members, per-file digests, conversation identifiers, and offending
values. Its only aggregate identity field, `population_identity_sha256`, may exist in
the **local** verification record as a privacy-safe aggregate identity value; it
remains **local-only by default**, and its publication, commitment, or external
disclosure is subject to the separate governance decision defined in §19 (CHC-P3-09).
Producing a verification result does **not** itself grant disclosure approval, and it
is **not** an "already-approved" value.

### 18.3 Forbidden on every failure surface

```text
no path, filename, relative path, or absolute path
no hash/digest, member name, or archive name
no transcript text, header, tier, speaker, or participant value
no original exception text; no traceback (in any committed output or the script)
no nested __cause__/__context__ carrying protected data
no protected stdout/stderr
```

### 18.4 Chain-free, control-flow-safe (reuse the strict reader's proven pattern)

```text
- catch Exception, NEVER BaseException.
- KeyboardInterrupt and SystemExit propagate as the exact same object (identity).
- raise-after-exit: catch inside an inner helper, record a content-free category,
  exit the except block, THEN raise CallhomePopulationError outside any active
  handler, so __cause__ is None and __context__ is None.
- Filesystem failures (FileNotFoundError, PermissionError, OSError) become fixed
  categories exposing no path or original text.
- Cleanup-error precedence: the primary error always wins (§15.5).
```

### 18.5 Privacy-safe record and error representations (Checkpoint A, normative)

Representation safety is a **normative Checkpoint A** requirement — it holds for the
pure records before any filesystem or publication code exists.

**Every census record dataclass** (`CallhomeSourceMember`,
`CallhomeExtractionProcedure`, `CallhomeSourceSnapshot`, `CallhomeSourceSnapshotId`,
`CallhomeCandidateSourceSnapshotRecord`, `CallhomeSourceApproval`,
`CallhomeCensusAuthorizationRecord`, `CallhomePopulationEntry`,
`CallhomePopulationCounts`, `CallhomePopulationManifest`,
`CallhomePopulationVerification`, `CallhomePopulationCensusSummary`, and any eventual
verification record) must:

```text
- declare field(repr=False) for EVERY field, and
- provide an explicit, fixed custom __repr__.
```

The custom representation must be **exactly equivalent in disclosure level** to:

```text
ClassName(<redacted>)
```

It must expose **no**:

```text
path            filename            archive name        hash or digest
conversation identifier             timestamp           approver
repository commit                    count               byte total
population identity                  manifest identity   record content
```

This applies to **nested records, persisted top-level records, the summary, and any
eventual verification record**. **Sentinel tests are required**: directly call
`repr()` on every record type (constructed with injected sentinel values — path,
filename, digest, member name, count, timestamp) and assert none of the sentinels
appears in the result, which must be the fixed `ClassName(<redacted>)` form.

**`CallhomePopulationError`** must:

```text
- expose ONLY a fixed content-free category (§18.1);
- carry no protected value in args;
- carry no protected value in its repr or str;
- expose no exception chaining or original exception context across the supported
  boundary (__cause__ is None and __context__ is None, §18.4);
```

and the **pure module performs no logging or printing** (no `print`, no logging
handler emission from the pure core).

**In-memory aggregate summary.** `CallhomePopulationCensusSummary` may be
constructed in Checkpoint A (in memory only), but its representation must be redacted
exactly as above, and its **real publication remains deferred and
governance-controlled** (LOCAL until G3, §19). Checkpoint A neither writes it nor
resolves any path for it (§1.4, §6.1).

### 18.6 Record dataclass mechanics and hash policy (CHPA-P2-04)

This record-mechanics contract is **normative** and applies to **every** Checkpoint A
record dataclass listed in §18.5 (the twelve record/value dataclasses, including
`CallhomePopulationVerification` and the census summary). The
error type `CallhomePopulationError` is an **exception, not a dataclass**, and is
governed by §18.7; the authorization capability `_CensusCapability` (§8.2) is a
Checkpoint B internal, out of this record-mechanics scope. This subsection fixes the
decorator, equality, hashing, and representation mechanics so no implementer invents
them.

**Uniform declaration (every record dataclass):**

```text
@dataclass(frozen=True, slots=True)     # frozen AND slots on EVERY record
eq=True                                  # dataclass-generated structural __eq__
unsafe_hash=False                        # never; hashing comes from frozen+eq only
repr suppression: field(repr=False) on EVERY field, PLUS an explicit fixed __repr__
  (the explicit __repr__ is authoritative and returns exactly ClassName(<redacted>))
__str__: NOT separately defined — str() delegates to the explicit __repr__, so
  str(record) and repr(record) BOTH render exactly ClassName(<redacted>)
__hash__: the normal dataclass-generated hash (present because frozen=True and
  eq=True and unsafe_hash=False)
```

**Slots.** `slots=True` is required on every record; therefore **no record has a
`__dict__`**, and setting an unknown attribute fails. No record field carries a default
value, so `slots=True` composes cleanly. Tests assert `slots` presence and the
**absence of `__dict__`** for every record (§20.1).

**Hash policy (exact):**

```text
- Use the normal dataclass-generated hash ONLY; introduce NO custom semantic hash.
- The generated hash is available for a record only when ALL its fields are
  transitively hashable. Every Checkpoint A record field is a str, an int, a bool, a
  nested frozen record, or an IMMUTABLE TUPLE of such values (e.g.
  tuple[CallhomeSourceMember, ...], tuple[CallhomePopulationEntry, ...],
  tuple[str, str]). No record contains a list, dict, set, or any other unhashable
  field. Therefore EVERY public record — including records holding immutable tuples —
  is hashable, and hash(record) SUCCEEDS for every record type. No field type would
  make the generated hash unavailable, so no per-record "hash unavailable" policy or
  exception exists to specify.
- Record hashing NEVER replaces cryptographic identity or checksum functions: the
  Python object hash is unrelated to population_identity_sha256, manifest_file_sha256,
  source_approval_sha256, and census_authorization_sha256 (§11, §14.2) and must never
  be used where a cryptographic digest is required.
- Tests PIN, for every public record, that hash(record) succeeds (no record raises
  TypeError on hashing) (§20.1).
```

**Representation (reaffirming §18.5, now with slots):**

```text
- field(repr=False) on every field; explicit fixed __repr__ returning
  ClassName(<redacted>); str() delegates to it.
- repr(record) and str(record) each render exactly ClassName(<redacted>) and expose
  no field value (path, filename, digest, timestamp, count, byte total, identity,
  approver, commit) — the §18.5 sentinel tests apply to every record type.
```

This contract changes no field, type, or checksum (§8.5, §14.2); it only fixes the
dataclass mechanics. The §8.5 declarations show `@dataclass(frozen=True, slots=True)`
consistently with this subsection.

### 18.7 `CallhomePopulationError` construction contract (CHPA-P2-05)

`CallhomePopulationError` is constructed as:

```python
CallhomePopulationError(category)
```

and accepts **exactly one** argument: a single **supported category string** drawn
**only** from the closed content-free taxonomy of §18.1 (the exact set):

```text
environment_error            root_error                 unexpected_entry
source_identity_mismatch     manifest_mismatch          empty_population
language_crossover           duplicate_identity         ordering_error
serialization_error          output_error               authorization_error
privacy_error                schema_error               frozen_output_exists
archive_verification_error   publication_verification_required
```

**Supported category (a member of the set above).** Two guarantee scopes are
distinguished (CHPA-R2-04): properties the error type controls itself, and properties
guaranteed only at project-controlled supported boundaries.

*Controlled by `CallhomePopulationError` itself* — for supported construction, always:

```text
args == (category,)
str(error) == category
repr(error) contains ONLY the class name and the supported category
             (e.g. CallhomePopulationError('schema_error')) and no other value
the constructor performs NO explicit exception chaining
             (never `raise ... from ...`; never sets __cause__)
```

*Guaranteed at project-controlled supported boundaries* — every project call site that
raises or converts these errors **leaves the active exception handler first** and
raises the fixed error **outside** any handler (§18.4), so at the supported API
boundary:

```text
error.__cause__ is None
error.__context__ is None
```

Python may **automatically** attach an active exception to a newly raised exception's
`__context__`. `CallhomePopulationError` therefore does **not** claim that arbitrary
caller code constructing it **inside an active exception handler** will have
`__context__ is None` — that is outside the type's control. The `__context__ is None`
guarantee holds at the project-controlled supported boundaries (which raise outside any
handler), **not** for arbitrary third-party direct construction. Regardless of call
site, the constructor still performs no explicit chaining and never echoes a rejected
value (below).

**Unsupported value** — any value that is **not** one of the exact supported strings,
**including** a protected/sensitive string (e.g. a path, filename, digest, or member
name), an empty string, a value of the wrong type (non-`str`), or an unknown category
string — the constructor must:

```text
raise a fixed, NON-ECHOING ValueError with:
    args == ("unsupported_error_category",)
    str(exc) == "unsupported_error_category"
```

The rejected value must **not** appear in any of:

```text
the ValueError args, str, or repr;
the ValueError __cause__ or __context__;
any logging, or any other output.
```

**Additional constraints:**

```text
- Do NOT recursively construct another CallhomePopulationError for this
  constructor-validation failure: rejection raises a PLAIN ValueError
  ("unsupported_error_category"), never a CallhomePopulationError, and never recurses.
- Ordinary Checkpoint A validation failures are UNAFFECTED: they still raise a VALID
  CallhomePopulationError carrying one supported category (e.g. schema_error,
  serialization_error, manifest_mismatch, duplicate_identity), exactly as specified
  throughout §§9–18 and the §16.9 stage table.
- Every project-controlled supported call site that raises or converts these errors
  must LEAVE the active exception handler first, raise the fixed error OUTSIDE any
  handler, and avoid explicit chaining — thereby ensuring __cause__ is None AND
  __context__ is None at the supported API boundary. Sanitized conversion of caught
  JSON / UTF-8 (and other) exceptions into a supported CallhomePopulationError category
  must occur OUTSIDE the active exception handler (record a content-free category inside
  the handler, exit the handler, THEN raise), so the supported error boundary has NO
  leaked original exception through __cause__ or __context__ (§18.4). This applies to
  the strict loaders (§16.9) and to every raising Checkpoint A helper.
- The __context__ is None property is a SUPPORTED-BOUNDARY guarantee, NOT a claim about
  arbitrary third-party construction inside an active exception handler (Python may
  auto-populate __context__ there, from the caller's active exception, not from any
  rejected value). Even in that case the constructor still never places a rejected or
  caller-supplied value in its own args, str, repr, logging, output, or an explicit
  __cause__ chain.
- KeyboardInterrupt and SystemExit are NEVER caught and NEVER converted; they
  propagate as the exact same object (§18.4).
```

This makes the supported-category surface **closed and non-echoing**: an unsupported or
protected value can never be reflected back through the error type, and the
constructor-validation failure is itself content-free.

---

## 19. Decision B disclosure matrix

Categories (unambiguous):

```text
ALREADY TRACKED PUBLIC FACT
LOCAL ONLY UNDER CURRENT POLICY
ELIGIBLE FOR FUTURE G3 REVIEW — NOT CURRENTLY APPROVED
REQUIRES SEPARATE GOVERNANCE DECISION
FORBIDDEN
```

| Field | Status |
|---|---|
| provider | ALREADY TRACKED PUBLIC FACT |
| public corpus names | ALREADY TRACKED PUBLIC FACT |
| public citation labels | ALREADY TRACKED PUBLIC FACT (once G5/G6 finalized) |
| public release labels | ALREADY TRACKED PUBLIC FACT (once G5/G6 finalized) |
| schema / schema_version / contract versions | ALREADY TRACKED PUBLIC FACT |
| extraction-procedure policy labels | ALREADY TRACKED PUBLIC FACT |
| repository_commit | ALREADY TRACKED PUBLIC FACT |
| logical roots (eng/spa) | ALREADY TRACKED PUBLIC FACT |
| ordering_contract_id | ALREADY TRACKED PUBLIC FACT |
| file counts by language | ELIGIBLE FOR FUTURE G3 REVIEW — NOT CURRENTLY APPROVED (local now) |
| all_identity_checks_passed (bool) | ELIGIBLE FOR FUTURE G3 REVIEW — NOT CURRENTLY APPROVED (local now) |
| aggregate byte totals | LOCAL ONLY UNDER CURRENT POLICY |
| population_identity_sha256 | REQUIRES SEPARATE GOVERNANCE DECISION |
| manifest_file_sha256 | REQUIRES SEPARATE GOVERNANCE DECISION |
| archive checksum / size | REQUIRES SEPARATE GOVERNANCE DECISION |
| failure-reason counts | REQUIRES SEPARATE GOVERNANCE DECISION (per-output; small cells) |
| small-cell counts | REQUIRES SEPARATE GOVERNANCE DECISION |
| archive filename | LOCAL ONLY UNDER CURRENT POLICY |
| retrieval / approval / auth timestamps | LOCAL ONLY UNDER CURRENT POLICY |
| relative transcript path | LOCAL ONLY UNDER CURRENT POLICY |
| transcript checksum (per file) | LOCAL ONLY UNDER CURRENT POLICY |
| conversation identifier | LOCAL ONLY UNDER CURRENT POLICY |
| run identifier | LOCAL ONLY UNDER CURRENT POLICY |
| absolute path | FORBIDDEN |
| transcript text | FORBIDDEN |
| speaker/participant metadata | FORBIDDEN |
| header/tier values | FORBIDDEN |
| exception traceback / raw exception text | FORBIDDEN |

Clarifications (no ambiguity):

```text
- Aggregate byte totals are LOCAL ONLY UNDER CURRENT POLICY. A future governance
  change MIGHT permit them; that possibility is prose-only and does NOT make them a
  current commit candidate.
- file counts by language and all_identity_checks_passed are NOT approved merely for
  being aggregates; they stay LOCAL until G3 explicitly approves those exact fields
  (per-output review — a low-cardinality count can be reconstructive).
- failure-reason counts and small cells REQUIRE SEPARATE GOVERNANCE DECISION.
- a failed or anomalous census produces NO numeric committed bundle.
- per-file identities are LOCAL ONLY; transcript-derived content is FORBIDDEN.
```

This document does **not** imply Decision B has expanded. Until G3, nothing in
`data/processed/callhome_population/` is committed.

---

## 20. Synthetic test matrix (integrated closure tests)

All fixtures are invented (synthetic `.cha` byte blobs and archives, `AAA`/`BBB`
names, `syn_*` tokens, unique sentinels). No real corpus filename, hash, archive
name, conversation id, or text. The test module is **staged**: **Checkpoint A** tests
(§20.1) use pure supplied-value constructors, validators, mapping functions,
serializers, checksum functions, ordering, collision, reconciliation, and summary
functions — with **no filesystem capability and no `_census_population_core`**;
**Checkpoint B** tests (§20.2) use synthetic filesystem trees and the private
`_census_population_core` seam (§8.3). The test module is **not** solely a
filesystem/private-core suite.

### 20.1 Checkpoint A test contract (pure core; no filesystem)

Checkpoint A tests exercise pure functions over **supplied values only** — no
filesystem trees, no archives, no bootstrap, no publication. Required:

```text
exact constants and schemas (§8.7, §16)
protected repr for every record (§18.5)
strict scalar predicates (§8.8)
bool-as-int rejection (§8.8)
missing and unknown field rejection (§8.8, §16)
duplicate JSON keys at nested depths (§14.3, §16)
BOM, invalid UTF-8, NaN, Infinity, and lone-surrogate rejection (§14.3)
canonical JSON fixed byte vectors (§14.1, §16.6)
approval checksum fixed vectors (§14.2)
authorization checksum fixed vectors (§14.2)
stable population identity fixed vectors (§11.1)
manifest-file checksum fixed vectors (§11.3)
run-metadata independence (§11.2)
canonical source-member ordering (§10.8)
noncanonical member-order rejection (§10.8)
duplicate source-member rejection (§10.8)
population entry ordering (§4.3)
ordinal consecutiveness (§4.3, §8.8)
filename[:-4] conversation identities (§10.5)
multi-dot filenames (§10.5)
count derivation and all eight reconciliation mismatch cases (§11.6)
recomputed-checksum count tampering (§11.6, §11.7)
duplicate byte collision — GLOBAL across eng and spa (§13.4)
conversation-ID collision (§13.4)
same-language NFC collision (§13.4)
same-language NFD collision (§13.4)
same-language case-fold collision — e.g. same-language A.cha vs a.cha (§13.4)
cross-language equivalents do NOT path-collide — e.g. eng/A.cha and spa/a.cha
  permitted unless another rule applies; cross-language canonically equivalent
  Unicode names do not trigger NFC/NFD/case-fold path collisions (§13.4)
exact language-crossover behavior (§13.5)
collision and mismatch precedence (§9.1, §13.4)
record-level invariants for every record (§16.7)
snapshot id n_members == len(members); identity view derived not contradictory (§16.7)
source-approval contract-version mismatch rejected at construction and strict
  loading — no upgrade/fallback/normalize/caller-select (§16.7, CHC-P2-04)
english/spanish snapshot-ID provider mismatch rejected (§16.7, CHC-P2-05)
english/spanish snapshot-ID language mismatch rejected (§16.7, CHC-P2-05)
snapshot-ID n_members zero / negative / Boolean / wrong-type rejected (§16.7, CHC-P2-05)
english snapshot-ID n_members vs English manifest-entry count mismatch rejected (§16.7)
spanish snapshot-ID n_members vs Spanish manifest-entry count mismatch rejected (§16.7)
manifest builder DERIVES snapshot IDs from the supplied source_approval and accepts NO
  caller-supplied IDs; source_approval contract-version mismatch and source_approval_sha256
  mismatch each rejected (§16.7, §8.9, CHPA-R2-02)
empty population rejection (§4.1)
one-language-empty rejection (§4.1)
aggregate-summary construction (§19)
summary repr privacy (§18.5)
fixed content-free errors (§18)
dependency guard against CHAT/parsing/condition modules (§6.1)
import guard: imports ⊆ {hashlib, json, unicodedata, dataclasses}; no pathlib/os/
  Path/_census_population_core; no filesystem or archive activity (§6.1)

--- Round-8 clarification coverage (CHPA-P2-01..05) ---
every normative public API name present and importable from cslm.data.callhome_population,
  with its §8.9 signature (§8.9, CHPA-P2-01)
private-helper non-export expectations where enforceable: the public surface is the §8.9
  PUB set; underscore helpers are module-internal; no path-accepting public helper (§6.1, §8.9)
strict-loader exact stage precedence: stages 1–23 evaluated in the fixed order (§16.9)
coexisting malformed / canonicality / checksum / count / identity defects select the
  EARLIEST fixed category; no later category observable (§16.9)
CallhomePopulationVerification inert-type ownership: field order / types / immutability /
  slots / hash / equality / redacted repr / constructor invariants ONLY; NO live-
  verification behavior simulated in Checkpoint A (§16.10)
slots present and __dict__ ABSENT for EVERY record (§18.6)
exact dataclass equality behavior for every record (§18.6)
exact hash behavior for every record: hash(record) succeeds (§18.6)
exact repr and str for every record == ClassName(<redacted>) (§18.5, §18.6)
supported CallhomePopulationError category: args==(category,), str==category,
  __cause__/__context__ None (§18.7)
unsupported string category → ValueError("unsupported_error_category") (§18.7)
protected sentinel as unsupported category → same ValueError; value NOT echoed (§18.7)
empty category → ValueError("unsupported_error_category") (§18.7)
wrong-type (non-str) category → ValueError("unsupported_error_category") (§18.7)
unsupported-category failure contains ONLY "unsupported_error_category"; the rejected
  value is absent from args, str, repr, __cause__, __context__, logs, and output (§18.7)

--- Round-9 clarification coverage (CHPA-R2-01..04) ---
every typed bidirectional converter pair present with its exact §8.9 name, parameter
  type, and return type; no generic `_<record>_…` form remains (§8.9, CHPA-R2-01)
round-trip per record: _mapping_to_X(_X_to_mapping(record)) == record, and
  _X_to_mapping(_mapping_to_X(canonical_mapping)) == canonical_mapping (§8.9, §14.3)
_mapping_to_<record> enforces intrinsic/local invariants only; aggregate/cross-record
  invariants come from the ordered builder/loader, not the converter (§8.9, §16.9)
inert-only verification converters do not persist and do not run live verification (§8.9, §16.10)
_build_population_manifest takes source_approval and DERIVES both snapshot IDs; accepts
  NO caller-supplied snapshot IDs (§8.9, §16.7, CHPA-R2-02)
_build_population_manifest rejects source_approval.contract_version != POPULATION_CONTRACT_VERSION
  and source_approval_sha256 != _source_approval_sha256(source_approval) (§8.9, §16.7)
_build_population_manifest reconciles each derived snapshot-ID n_members against the
  per-language entries (§16.7)
created_utc and repository_commit validated for scalar grammar ONLY at the builder;
  no live acquisition in Checkpoint A (§8.9, §8.8, CHPA-R2-02)
two-phase strict loader: a noncanonical manifest fails at the Phase-1 byte comparison
  (serialization_error) BEFORE any typed record is constructed and before any Phase-2
  category (§16.9, CHPA-R2-03)
noncanonical + wrong-checksum / bad-counts / collision manifest → serialization_error
  (Phase 1 wins over every Phase-2 category) (§16.9)
no invariant-enforcing typed record is constructed before the Phase-1 canonical
  comparison (§16.9, §14.3)
CallhomePopulationError supported construction: own state pinned (args/str/repr) and the
  constructor performs no explicit chaining (§18.7, CHPA-R2-04)
project-controlled supported boundary: __cause__ is None AND __context__ is None when
  the fixed error is raised outside any active handler (§18.7, §18.4)
tests do NOT require arbitrary external construction inside an active exception handler
  to have __context__ is None (that is outside the type's control) (§18.7, CHPA-R2-04)

--- Round-10 clarification coverage (CHPA-R3-01, three validation layers) ---
DIRECT-CONSTRUCTOR tests (every record) — test ONLY: exact field order; exact field
  types; fixed constants and namespaces; scalar grammar; local field relationships
  (incl. summary local arithmetic; snapshot own members canonical order §10.8;
  n_members==len(members)); tuple immutability; frozen/slots/equality/hash/repr;
  intrinsic/local constructor failures → schema_error (§8.9, §16.7)
DIRECT-CONSTRUCTOR tests do NOT expect direct constructors to reject aggregate
  population defects requiring cross-record comparison or recomputation (§16.7)
CONVERTER tests (_mapping_to_<record>) — test: exact field-set validation; primitive/
  container-type validation; nested + tuple conversion; intrinsic/local validation;
  typed round trips; NO aggregate acceptance performed by a converter (§8.9, §16.7)
BUILDER/STRICT-LOADER tests own ALL of: approval binding; n_members reconciliation;
  ordering and ordinals; collisions; crossover; inventory matching; count reconciliation;
  stable identity; manifest checksum; coexisting-defect precedence; accepted-aggregate
  vs raise-without-result behavior (§16.7, §16.9)
CONTRACT-ALLOCATION test: an intrinsically valid direct CallhomePopulationManifest
  dataclass value can EXIST before aggregate acceptance; ONLY _build_population_manifest
  or the strict manifest loader establishes accepted aggregate status through the
  supported module contract (no partially accepted object is ever returned; not a
  license to expose or persist an invalid aggregate) (§16.7, §16.9, CHPA-R3-01)

--- Round-11 crossover & approved-inventory ownership (CHPA-R3-01 follow-up) ---
_build_population_manifest OWNS crossover + approved-inventory matching (derives the
  approved inventories from source_approval.english/spanish.members):
  - candidate entry key present in its OWN approved inventory → membership passes
  - candidate key absent from own but EXACTLY present in opposite inventory → language_crossover
  - candidate key absent from BOTH inventories → source_identity_mismatch
  - filename-only / stem-only / path-only / digest-only / partial matches do NOT become
    crossover (crossover needs the full (relative_path,size_bytes,sha256) key, §13.5)
  - collision (stage 17) precedence remains earlier than crossover (stage 18); crossover
    earlier than ordinary own-inventory mismatch (stage 19) (§16.9)
  - builder cannot trust a claimed prevalidated Checkpoint B input — it re-evaluates
  - builder returns NO manifest when any of these checks fails (§8.9)
STRICT-LOADER tests: all self-contained aggregate checks run; approval-context stages
  14/18/19 are explicitly SKIPPED when the loader API lacks approved-source context, and
  such skipping is NOT a claim that a real source population was approved (§16.9)
CHECKPOINT-B CENSUS-CORE tests: the census core passes prepared entries + source_approval
  to _build_population_manifest; propagates builder success/failure; publishes ONLY the
  accepted builder result; never substitutes an independent acceptance decision (§9.1)

--- Round-12 checkpoint-boundary & per-loader error truthfulness (P2-01..03) ---
§1.4 boundary: pure approved-inventory membership + language-crossover comparison over
  SUPPLIED values are Checkpoint A (assert the pure functions perform them with no
  filesystem/archive/env/Git/clock/bootstrap/live-source access); live enumeration,
  authentication, candidate-entry creation, invocation, and publication are Checkpoint B (P2-01)
§9.1 / builder precedence: _build_population_manifest applicable order is ordering/ordinals
  → collision → crossover → ordinary inventory → counts → identity → manifest-file checksum;
  a coexisting ordering + collision defect yields ordering_error (ordering wins); §16.9 is the
  sole precedence contract; no §9.1 step lists ordering after collision/crossover/inventory (P2-02)
per-loader EXACT error inventory matches only the loader's evaluable stages (P2-03, §8.9):
  - _load_candidate_source_snapshot → {schema_error, serialization_error} only
  - _load_source_approval → {schema_error, serialization_error} only; an invalid
      archive_filename basename/field grammar → schema_error (intrinsic, §8.8/§10.7), NOT
      source_identity_mismatch; NO approval-to-manifest binding / inventory comparison
  - _load_census_authorization → {schema_error, serialization_error} only
  - _load_population_manifest → {schema_error, serialization_error, duplicate_identity,
      ordering_error, manifest_mismatch} ONLY
  - _load_census_summary → {schema_error, serialization_error} only
_load_population_manifest CANNOT emit language_crossover or contextual source_identity_mismatch
  from bytes lacking approved-source context: feed a canonical manifest whose entries would
  cross over / mismatch an approved inventory NOT supplied to the loader → the loader accepts
  (self-contained stages pass) or raises only a self-contained category; it NEVER raises
  language_crossover or a binding/inventory source_identity_mismatch (§16.9 stages 14/18/19 skipped)
loader contextual-skip is non-approving: skipping stages 14/18/19 is asserted NOT to imply
  approval, matched-to-approved-source evidence, authorization, or live verification (§16.9, §16.7)

--- Round-13 residual precedence & loader-error truthfulness (P2-02-R1, P2-03-R1..R2) ---
§25 (and every summary) states aggregate precedence beginning with ordering/ordinals, then
  collision → crossover → ordinary inventory → counts → identity → manifest-file checksum;
  no complete precedence summary begins with collision (P2-02-R1, §§9.1/16.9)
_load_source_approval: invalid archive_filename basename / field grammar → schema_error
  (P2-03-R1, §8.8/§10.7); it does NOT emit source_identity_mismatch for an intrinsic field defect
_load_population_manifest CANNOT emit authorization_error from context-free str|bytes
  (feed valid canonical manifest bytes with no authorization context → never authorization_error) (P2-03-R2)
_load_population_manifest STILL emits manifest_mismatch for the exact self-contained
  predicates: snapshot n_members reconciliation, count reconciliation, stable-identity
  recomputation, manifest-file checksum recomputation (P2-03-R2, §8.9/§16.9)
§14.2 and the general §16 loading prose defer to the exact §8.9 per-loader inventories; no
  collective contextual category set is applied to context-free loaders (P2-03-R2)

--- Round-14 boundary-specific approval error ownership (P2-03-R1-R2) ---
three approval-related operations are distinct boundaries carrying distinct, non-substitutable
  categories; assert each boundary raises ONLY its own category and NEVER another's:
_load_source_approval (pure Checkpoint A):
  - malformed archive_filename basename / grammar → schema_error
  - malformed mapping / wrong field type / invalid fixed constant / nested intrinsic field
    defect → schema_error
  - noncanonical serialized bytes → serialization_error
  - NEVER source_identity_mismatch and NEVER authorization_error (it authenticates nothing and
    compares no expected checksum) (§8.9, §16.7, §18.2)
_build_population_manifest (pure Checkpoint A): a supplied source_approval / source_approval_sha256
  contract, checksum, source, or approved-inventory mismatch → source_identity_mismatch; NEVER
  authorization_error (§8.9, §16.7, §16.9)
_grant_capability (Checkpoint B; behavioral test in §20.2/§17.4): every authorization,
  authentication, trusted-bootstrap, or capability-binding failure — including expected-checksum
  authentication of the authorization record's own source_approval_sha256 — → authorization_error;
  NEVER source_identity_mismatch (§17.1, §18.2). §20.1 pins the category taxonomy and the two
  pure-core boundaries; the filesystem-dependent _grant_capability behavior is exercised in §20.2
category non-substitution: assert _load_source_approval, _build_population_manifest, and
  _grant_capability cannot stand in for one another's error category — there is no shared
  "authorization/approval loading" category (§18.1, §18.2)
```

**Planning target (CHPA-P3-01, non-normative).** The preflight's estimate of
**approximately 170–220 collected test cases** is retained as a **planning target
only**, not a Definition-of-Done count. What is normative is **behavioral coverage** —
every normative rule of §§8–20 exercised, including the Round-8 items above — **not** a
specific collected-case count. No specific number is required or asserted; CHPA-P3-01
is carried as non-blocking planning guidance.

Deferred to **Checkpoint B** (do not attempt at Checkpoint A): synthetic filesystem
trees, archives, symlinks, hard links, publication state-machine, trusted bootstrap,
authorization capability, CLI, and any real-data tests. The blocks below (§20.2)
labeled Checkpoint B are those tests; the earlier §20.1 items are their pure-core
counterparts.

### 20.2 Full integrated matrix (A = Checkpoint A pure; B = Checkpoint B filesystem)

```text
Bootstrap / authorization (§8/§17) — Checkpoint B
  - nullary functions expose no roots/output/write/glob/subset/provider args
  - lookalike _CensusCapability (public fields) cannot authorize traversal
  - CWD change to a dir with a lookalike authorization record has no effect
  - missing bootstrap marker fails before private-path resolution
  - invalid authorization fails before project_root()
  - project_root()/bootstrap mismatch fails before archive/corpus traversal
  - bootstrap performs no access under data/raw
  - no env/CLI override changes the bootstrap root
  - the script drives only the nullary entry point; never the core

Base purity (§9.2) — Checkpoint B
  - base contains exactly {eng, spa} → pass
  - missing eng / missing spa / extra dir / archive under base / control file under
    base / hidden base entry / ENG or SPA / symlinked root / special entry → fail

Archive confinement (§10.7) — Checkpoint B
  - absolute / ../ / nested / forward- or backslash / "." / ".." / NUL basename → fail
  - symlink or special archive → fail
  - same eng/spa basename → fail
  - same inode via hard link → fail
  - unexpected third archive / hidden / temp archive entry → fail
  - changed archive size or digest → fail

Snapshot workflow (§10) — Checkpoint B (pure record/checksum validation: A, §20.1)
  - candidate → independent approval → authorization → census (happy path)
  - altered archive / size / digest → fail
  - altered source approval (checksum) → fail
  - altered member inventory (missing/extra/modified/substituted) → fail
  - changed extraction-procedure identity → fail
  - eng vs spa extraction-procedure contract mismatch → fail (§8.5)
  - replayed authorization bound to a different source_approval_sha256 → fail
  - manifest CONSTRUCTION derives snapshot IDs from the supplied source_approval (no
    caller-supplied IDs); a source_approval with contract_version != POPULATION_CONTRACT_VERSION,
    or source_approval_sha256 != its canonical checksum, → RAISE source_identity_mismatch
    (acceptance boundary, §16.7, CHPA-R2-02); (the LIVE-verification snapshot-ID comparison
    is a RETURNED result — see the Live re-verification block, CHC-P2-07)

Enumeration / rejection (§4/§9) — Checkpoint B (pure empty/one-language rejection: A, §20.1)
  - correct census → verified manifest, correct counts, ordinals 0..N-1
  - nested dir / hidden / metadata / temp / uppercase suffix / archive / broken
    symlink / special file → unexpected_entry
  - empty English / empty Spanish population → empty_population

Determinism / identity (§4.3/§11/§12) — Checkpoint A (re-resolution/verification: B)
  - stable ordering regardless of creation order; locale independence
  - same population, different timestamps → same population_identity_sha256
  - same population, different repository commits → same population_identity_sha256,
    distinct run metadata
  - changed member/order/snapshot/contract/count → different population_identity_sha256
  - complete manifest bytes changed → manifest_file_sha256 changes
  - (A) NFD path STRING round-trips byte-for-byte through canonical serialization
  - (A) same-language NFC/NFD/case-fold path pairs → duplicate_identity; cross-language
    equivalents do NOT path-collide (§13.4)
  - (A) ordering uses exact UTF-8 bytes; serialization does not rewrite identity
  - (B) NFD path re-resolves via the stored exact path on a real filesystem
  - (B) verification never rewrites bytes or timestamps

Counts reconciliation (§11.6/§11.7) — Checkpoint A (re-verification point: B)
  - tamper each of the 8 count fields (with both checksums recomputed) → manifest_mismatch
  - reconciliation occurs at builder construction (_build_population_manifest), strict
    loading, and re-verification — never in a direct dataclass __post_init__ (§16.7, CHPA-R3-01)

Conversation identity (§10.5) — Checkpoint A
  - single-dot / multi-dot / Unicode name / equal eng-spa stems / name ending in
    another suffix before .cha → correct f"{language}/{filename[:-4]}" over supplied
    strings (no pathlib, no Path.stem, no filesystem)
  - NOTE: the fact that Path(filename).stem equals filename[:-4] for admitted .cha
    names is documentation only (§10.5); it is NOT a Checkpoint A test and must not
    import pathlib

Collisions / crossover / zero-byte (§13) — Checkpoint A (zero-byte enumeration fixture: B)
  - duplicate byte content / duplicate conversation id / NFC / NFD / case-fold →
    duplicate_identity (§13.4)
  - collision internal precedence: byte → conversation → NFC → NFD → case-fold (§13.4)
  - exact language crossover (owned by _build_population_manifest, §13.5/§16.9 stage 18):
    opposite-language member key present AND own absent → language_crossover; equal
    filenames/stems across languages are NOT crossover (§13.5)
  - ordinary approved-inventory membership (_build_population_manifest, §10.3/§16.9 stage 19):
    candidate key absent from both inventories → source_identity_mismatch
  - failure precedence among these builder checks: collision (stage 17) → crossover
    (stage 18) → ordinary inventory mismatch (stage 19); ordering has its own fixed
    stage 16 (§16.9, §13.4, §13.5)
  - one zero-byte .cha retained as a member (counted)
  - two zero-byte .cha → duplicate_identity (empty-input SHA-256)
  - NO test references the removed "duplicate normalized path identity" class (§13.1)

Publication state machine (§15) — Checkpoint B
  - inject failure at each transition (temp create / write / flush / file fsync /
    link / first dir fsync / temp unlink / second dir fsync); assert exactly one of:
    no final exists | existing final preserved | byte-complete final +
    publication_verification_required | durable success
  - existing frozen manifest → frozen_output_exists; fixed deterministic filename
  - no partially-written final ever visible; post-link failures never delete final
  - residual temp names not printed; verification does not clean up or rewrite
  - cleanup failure during another failure does not mask the primary

Schemas (§16/§14.3) — Checkpoint A
  - valid round trip for each of the 5 records; fixed canonical vectors match
    dataclass fields / JSON / checksum inputs / schema tables
  - unknown / missing / duplicate-key (nested depths) / mistyped / bool-as-int /
    unsupported-schema / unsupported-version / invalid-enum / invalid-checksum /
    BOM / invalid-UTF-8 / NaN / Infinity / lone-surrogate / non-canonical → fail
  - reserialize-and-compare byte equality; explicit mapping funcs; asdict not the
    checksum contract (§14.3)

Privacy / record + error representation (§18/§18.5) — Checkpoint A
  - repr() of EVERY record type returns the fixed ClassName(<redacted>) form with no
    injected sentinel (path, filename, digest, member name, count, timestamp) (§18.5)
  - injected sentinels (path, filename, digest, member name, archive name) absent
    from str/repr/args/__cause__/__context__ of any raised error (over supplied values)
  - every ordinary error: __cause__ is None and __context__ is None
  - CallhomePopulationError carries only a fixed category; pure module never logs/prints

Control-flow / cancellation / script (§18.4/§15.5) — Checkpoint B
  - injected sentinels absent from stdout/stderr at the I/O / traversal / hashing /
    publication / verification / CLI boundaries
  - injected KeyboardInterrupt() and SystemExit() propagate as the exact object at the
    Checkpoint B boundaries (I/O, authorization, traversal, hashing, publication,
    verification, CLI); pure Checkpoint A helpers that catch no exceptions need no
    artificial cancellation test
  - the script emits no traceback or protected detail; stable nonzero exit code

Live re-verification — RETURNED result (§11.4/§11.7/§16.7/§16.8) — Checkpoint B (CHC-P2-06/CHC-P2-07)
  (all inputs are valid canonical manifests that decode + authenticate + recompute)
  - all four fatal fields true (manifest_file_sha256_ok, membership_matches,
    population_identity_matches, counts_reconciled) → ok == True
  - incorrect manifest-file checksum VALUE (grammar-valid but wrong) →
    manifest_file_sha256_ok == False and ok == False
  - persisted entries differ from recomputed live entries →
    membership_matches == False and ok == False
  - stable identity differs from identity recomputed with authenticated snapshot IDs
    and live stable fields → population_identity_matches == False and ok == False
  - persisted counts differ from independently derived live counts →
    counts_reconciled == False and ok == False
  - repository_commit_compatible False while every fatal field True → ok remains True
  - valid canonical persisted English snapshot ID differs from authenticated English
    approval identity → population_identity_matches == False and ok == False (RETURNED,
    not raised) (§16.7/§16.8, CHC-P2-07)
  - valid canonical persisted Spanish snapshot ID differs from authenticated Spanish
    approval identity → population_identity_matches == False and ok == False (RETURNED)
  - unchanged entries but changed stable snapshot/contract metadata →
    membership_matches == True, population_identity_matches == False, ok == False

Live re-verification — RAISE without a record (§11.4 Stage R/§16.8/§18) — Checkpoint B (CHC-P2-07)
  (comparison impossible/unsafe → fixed content-free error, NO CallhomePopulationVerification)
  - missing or unreadable manifest / I/O failure → raise
  - invalid UTF-8 / UTF-8 BOM / duplicate JSON keys / NaN / Infinity / lone surrogate → raise
  - non-object top-level / missing fields / unknown fields / wrong field types → raise
  - invalid scalar grammar (incl. malformed manifest_file_sha256 value) → raise
  - invalid schema / unsupported schema version / invalid contract-field grammar → raise
  - noncanonical persisted JSON bytes → raise
  - invalid authorization / bootstrap failure → raise
  - structurally invalid source_approval.json or census_authorization.json → raise
  - filesystem traversal / hashing / archive-verification failure preventing a
    reliable live population result → raise
  - NO returned false Booleans for any malformed/structurally-unusable input above;
    all raises are content-free; KeyboardInterrupt/SystemExit preserved (§18.4)
```

---

## 21. Routing protections

The census records `language` (directory-derived, **expected, not verified**) and
source identity; it does **not** compute condition eligibility and emits no
`condition_candidates`, so it cannot route CALLHOME into `CsCont`. Directory name is
evidence of expectation only; actual language is verified downstream. The permanent
routing is independently enforced at each of: the source manifest, the
strict-execution manifest, linguistic validation (verified monolinguality — a
directory label never validates), projection, promotion (`clean` only after
validation + explicit approval; CALLHOME `clean` routes only to EnglishMono/MonoCont
for eng or SpanishMono/MonoCont for spa), the condition manifest, and final
construction. None of these is this census module.

---

## 22. Deferred strict-execution layer (its own later gate)

A later, separately-designed and separately-reviewed module executes the strict
reader over the frozen population. Contract sketch (not designed here):

```text
- re-verify the frozen manifest (manifest_file_sha256 + membership + population
  identity + counts) before any read;
- process each entry exactly once, in manifest order;
- call read_chat_transcript(...); NEVER the permissive parse_chat_file/lines;
- collect only local, content-free per-entry status categories;
- block population acceptance if ANY file rejects (no silently reduced population);
- abort immediately on an unknown exception or on manifest drift mid-run;
- preserve the reader's limitation that ordinary read failures and warning-bearing
  dispatch failures MAY share one privacy-safe public category — do NOT inspect
  nested exceptions to recover private detail.
```

Not implemented, scheduled, or authorized here.

---

## 23. Governance decision register

| ID | Decision | Status | Why it matters | Evidence required | Blocks gate | Blocks synthetic impl? |
|---|---|---|---|---|---|---|
| G1 | Exact English TalkBank archive snapshot approval | OPEN | pins English population identity | approved archive size/SHA-256 + member inventory (gates 8–10) | real census (13) | No |
| G2 | Exact Spanish TalkBank archive snapshot approval | OPEN | pins Spanish population identity | same as G1 for Spanish | real census (13) | No |
| G3 | Decision B approval of census aggregate schema | OPEN | licenses committing any aggregate census field | per-output safety review of §19 ELIGIBLE fields | committed census results (14) | No |
| G4 | Decision B approval of strict-result schema | OPEN | licenses committing strict-execution aggregates | per-output review of strict-result fields | committed strict results (16) | No |
| G5 | Approved English public citation/release label | OPEN (TODO in ground rules) | required public attribution | confirmed corpus manual / LDC citation | committed public source record | No |
| G6 | Approved Spanish public citation/release label | OPEN (TODO in ground rules) | required public attribution + DOI | confirmed corpus manual / LDC citation + DOI | committed public source record | No |

**Conclusion:** G1–G6 do **not** block this design or a synthetic-only
implementation. They **do** block all real census, real hashing, real validation,
and any committed CALLHOME-derived result. None is resolved here; the corpus is not
accessed to resolve them.

---

## 24. Future bounded gates (non-circular)

```text
 1. Corrected docs-only census design            — THIS gate
 2. Focused independent correction review
 3. Separate design merge
 4. Synthetic-only census implementation
 5. Independent implementation review
 6. Separate implementation merge
 7. Source-snapshot observation design
 8. Metadata-only candidate snapshot observation authorization
 9. Independent candidate snapshot review
10. Explicit English and Spanish snapshot approval (freezes source_approval.json)
11. Decision B G3/G4 and citation-label (G5/G6) decisions
12. Explicit census authorization (writes census_authorization.json)
13. Metadata-only real census (publishes the immutable manifest)
14. Independent census-result review
15. Strict-reader execution design and authorization
16. Strict-result review
17. Linguistic-validation design
18. Linguistic-validation execution
19. Explicit promotion
20. Preliminary EnglishMono / SpanishMono / MonoCont construction
```

The census never generates and approves its own expected inventory: observation
(8–9), approval (10), authorization (12), and census (13) are separate gates.

---

## 25. Definition of done

An independent reviewer can determine from this document alone:

```text
CWD-independent __file__-based bootstrap    — §8.6
bootstrap/project_root equality check       — §8.1 step 5, §8.6
strict archive basenames + archive-dir purity — §10.7
two distinct direct regular archive files    — §10.7 (basenames, inodes, digests)
counts included in stable identity           — §11.1, §11.6
counts recomputed and reconciled with entries— §11.6
identical dataclass/schema/checksum mappings  — §8.5, §14.2, §16
schema + schema_version in every persisted record — §8.5, §16
exact extraction-procedure placement (in snapshot) — §8.5, §16.1
fixed canonical JSON vectors                 — §16.6
six-state publication lifecycle              — §15.2
publication_verification_required semantics  — §15.3
no direct-final-write equivalence            — §15.1
supported-interface (not adversarial) threat model — §8.2, §17.3
exact final-.cha conversation-ID removal      — §10.5
non-bypassable production API                 — §8.1 (nullary), §8.2
exact base purity                            — §9.2
non-circular snapshot approval                — §10
stable / run / file identity separation       — §11
exact path preservation                      — §12
zero-byte duplicate boundary                 — §13.3
correct Decision B classifications           — §19
all closure tests                            — §20
Checkpoint A / Checkpoint B boundary          — §1.4
normative constants (exact values)            — §8.7
normative field predicates (every field)      — §8.8
canonical source-member ordering              — §10.8
five exact collision classes + precedence     — §13.4
exact language-crossover definition           — §13.5
failure precedence (ordering/ordinals → collision → crossover → ordinary approved-inventory mismatch → counts → stable identity → manifest-file checksum) — §§9.1, 16.9
privacy-safe record + error representations    — §18.5
strict JSON persistence boundary              — §14.3
identity/reconciliation closure                — §11.7
parsing/filesystem independence of pure core  — §6.1
Path.stem factual correction                  — §10.5
Checkpoint A test contract                    — §20.1
language-namespaced NFC/NFD/case-fold keys    — §13.4
record-level invariants (every record)         — §16.7
logical-root strings allowed in Checkpoint A   — §1.4, §6.1
complete normative dependency set              — §6
source-approval contract-version pinned        — §16.7 (CHC-P2-04)
manifest snapshot-ID predicates + binding       — §16.7, §11.4 (CHC-P2-05)
population_identity_matches + four-term ok      — §8.5, §16.7, §11.4, §11.7 (CHC-P2-06)
strict acceptance loader vs verification inspector — §16.4, §16.8 (CHC-P2-07)
verification raise-vs-return outcome model      — §11.4, §16.7, §18.2 (CHC-P2-07)
Checkpoint A API table (names/signatures/visibility) — §8.9 (CHPA-P2-01)
Checkpoint A type/record inventory               — §8.10 (CHPA-P2-01)
Rule-A type-syntax (four-module import set kept)  — §8.9 (CHPA-P2-01)
strict acceptance loader 23-stage precedence      — §16.9 (CHPA-P2-02; stage 19 added Round 11)
CallhomePopulationVerification A-defines/B-uses    — §16.10 (CHPA-P2-03)
record dataclass slots/eq/hash/repr mechanics     — §18.6 (CHPA-P2-04)
CallhomePopulationError unsupported-category rule  — §18.7 (CHPA-P2-05)
complete typed bidirectional converter inventory   — §8.9, §14.3 (CHPA-R2-01)
source_approval-bearing manifest builder (derives IDs) — §8.9, §16.7 (CHPA-R2-02)
two-phase strict loader (raw canonicality then construction) — §16.9, §14.3 (CHPA-R2-03)
__context__ guarantee scoped to supported boundaries — §18.7 (CHPA-R2-04)
validation-ownership: constructors/converters intrinsic-local, builders/loaders aggregate — §16.7, §8.9, §16.9, §11.7, §20.1 (CHPA-R3-01)
crossover + approved-inventory owned by _build_population_manifest; census delegates; loader skips when context absent — §8.9, §9.1, §16.7, §16.9 stages 18/19, §10.3, §13.5, §20.1 (CHPA-R3-01 / Round 11)
pure approved-inventory + crossover comparison is Checkpoint A over supplied values; Checkpoint B = live acquisition/auth/invoke/publish — §1.4 (P2-01 / Round 12)
§9.1 builder order = §16.9 (ordering before collision/crossover/inventory); single precedence contract — §9.1, §16.9 (P2-02 / Round 12)
exact per-loader error inventories; _load_population_manifest emits no contextual crossover/inventory — §8.9, §20.1 (P2-03 / Round 12)
aggregate precedence summaries are ordering-first everywhere — §25, §0, §§9.1/16.9 (P2-02-R1 / Round 13)
invalid source-approval archive_filename → schema_error (intrinsic); _load_source_approval raises no source_identity_mismatch — §8.9, §10.7, §18.2 (P2-03-R1 / Round 13)
§14.2/§16 defer to per-loader §8.9; context-free manifest loader emits no authorization_error or contextual source_identity_mismatch — §14.2, §16, §8.9 (P2-03-R2 / Round 13)
boundary-specific approval error ownership: _load_source_approval → schema_error / serialization_error; _build_population_manifest supplied approval/source binding → source_identity_mismatch where assigned; _grant_capability failures → authorization_error — §§8.9, 16.7, 17.1, 18.2, 20.1 (P2-03-R1-R2 / Round 14)
```

No real-data value appears anywhere in this document.

---

## 26. Explicit non-goals

```text
- No transcript parsing, tokenization, language labeling, or screening.
- No condition eligibility, projection, promotion, or dataset construction.
- No train/dev/test splitting or corpus freeze beyond freezing the file set.
- No tokenizer or model work; no language identification / monolinguality judgment.
- No real corpus access, archive download, real hashing, or private-directory
  inspection in this or the implementation gate's synthetic tests.
- No committing of per-file inventories, transcript checksums, conversation ids,
  archive filenames, aggregate byte totals, or any transcript-derived content.
- No Decision B expansion; no governance decision resolved here.
- No public roots/output/write/glob/subset/exclusion/alternate-provider/permissive
  interface; no generalized filesystem framework.
- No claim of cryptographic or adversarial in-process isolation for the capability.
```
