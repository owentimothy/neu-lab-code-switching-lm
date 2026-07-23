# CALLHOME Execution-Population Census — Implementation Design

**Status:** Design only. No implementation, no tests, no script, no `.gitignore`
change, no real corpus access, no private-directory inspection, no census, no
hashing of real files, no strict-reader execution, no dataset construction. This
document is an implementation-ready contract for a **later, separately reviewed**
synthetic-only implementation gate.

**Correction note (this revision):** an independent design review returned `STOP`
with one **P1** (authorization boundary bypassable through the public API), six
**P2** findings (base-directory purity not enforced; circular source-snapshot
approval; population identity conflated with run/file identity; NFC serialization
rewriting exact paths; overwritable "frozen" output; incomplete schemas/types),
and one **P3** (zero-byte-duplicate case unspecified). This revision rewrites the
affected normative contracts so the future implementer invents no architecture.
Section §0 maps each finding to its resolution.

**Permission state:** Decision B (see `docs/callhome_ground_rules.md`) —
aggregate-only, non-transcript CALLHOME summaries *may* be committed with citation
notes; per-row records, conversation identifiers, filenames, and transcript-
bearing outputs remain blocked and stay local/gitignored. This design does **not**
assert Decision B has expanded, and does **not** claim G3 has approved any census
aggregate for commit.

---

## 0. Finding-closure map

| Finding | Resolution section(s) |
|---|---|
| P1 — authorization boundary bypassable through public API | §8 (nullary public API + opaque internal capability + private test-only core), §17 |
| P2 — base directory purity not operationally enforced | §9.2 (base-purity check before any root traversal) |
| P2 — source-snapshot approval / member-inventory circular | §10 (A→B→C→D workflow; census rehashes the approved archive) |
| P2 — population identity conflated with run/file identity | §11 (`population_identity_sha256` vs run metadata vs `manifest_file_sha256`) |
| P2 — NFC serialization rewrites the exact approved path | §12 (exact path preserved; NFC/NFD/case-fold are transient collision keys only) |
| P2 — frozen output overwritable | §15 (no-overwrite exclusive publication; `frozen_output_exists`) |
| P2 — incomplete schemas/types/filenames | §16 (all persisted schemas), §8.5 (all public types defined) |
| P3 — zero-byte duplicate boundary unspecified | §13.3 (one retained; two+ fail duplicate-byte) |

---

## 1. Status and scope

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
**bytes** to compute a SHA-256 digest is not parsing: each `.cha` file is an
opaque byte stream for hashing only.

### 1.3 Exact implementation file scope (later gate)

```text
src/cslm/data/callhome_population.py     # production module (metadata-only census)
scripts/census_callhome_population.py    # fixed-everything, authorization-gated runner
tests/test_callhome_population.py         # synthetic filesystem fixtures only
.gitignore                               # one narrow entry (§7)
```

No other file may change in the implementation gate. This design document is the
only file changed in the current docs-only gate.

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

```text
duplicate byte content            (identical SHA-256)
duplicate normalized path identity
duplicate conversation identity
Unicode NFC collision
Unicode NFD collision
Unicode case-fold collision
manifest drift (enumerated set ≠ approved inventory)
English/Spanish crossover
```

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
| Accidental real traversal | privacy/ethics exposure | opaque authorization *before* `project_root()` (§8/§17) |
| Overwriting the frozen frame | silent population change | no-overwrite publication (§15) |
| Identity conflation | mislabeling "same population" | separate population/run/file identities (§11) |
| Privacy leakage | committing identifying material | content-free error taxonomy (§18) + Decision B matrix (§19) |

Delegated to later gates: language identification, monolinguality, screening,
projection, promotion, splitting, dataset construction.

---

## 6. Proposed architecture

```text
src/cslm/data/callhome_population.py
  ├── errors     : CallhomePopulationError + closed content-free category constants
  ├── auth       : opaque internal capability + private grant/verify (§17)
  ├── source id  : CallhomeSourceMember, CallhomeSourceSnapshot,
  │                CallhomeSourceSnapshotId, CallhomeSourceApproval
  ├── manifest   : CallhomePopulationEntry, CallhomePopulationCounts,
  │                CallhomePopulationManifest, CallhomePopulationVerification
  ├── public API : census_approved_callhome_population()  (nullary)
  │                verify_frozen_callhome_population()     (nullary)
  ├── core       : _census_population_core(...)  PRIVATE, test-only injection seam
  ├── serialize  : canonical JSON + checksums (§14)
  ├── schemas    : strict loaders for every persisted record (§16)
  └── aggregate  : build_population_census_summary(...) (Decision-B-gated, §19)

scripts/census_callhome_population.py
  └── fixed command; fixed base/roots/control dir/output filenames; explicit
     human-confirmation flag; opaque production authorization; census-only.

tests/test_callhome_population.py
  └── synthetic filesystem fixtures only; uses ONLY the private core.
```

The module depends only on the standard library (`pathlib`, `hashlib`, `os`,
`stat`, `json`, `unicodedata`, `dataclasses`, `io`) and
`cslm.utils.paths.project_root`. It has **no dependency** on `callhome_chat` or any
projection/screening module, so it cannot accidentally parse transcript content.

---

## 7. Fixed locations and local output ignore rule

Fixed project-relative locations (resolved via `project_root()` **after**
authorization; never caller-supplied):

```text
CALLHOME base   : data/raw/callhome
English root    : data/raw/callhome/eng
Spanish root    : data/raw/callhome/spa
Local control/output dir : data/processed/callhome_population
Approved local archive dir : data/processed/callhome_population/archives   (§10)
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
Archives, source-approval records, authorization records, manifests, aggregate
records, and temporary output must **never** reside under `data/raw/callhome`
(enforced by the base-purity check, §9.2).

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
glob, subset, exclusion selector, alternate provider, or permissive mode. The
signatures `roots=...`, `output_dir=...`, `write=...` from the prior draft are
**removed**. `CallhomeRoots` is **not** part of the public API (§8.5).

Both functions internally use only the fixed paths/filenames of §7 and execute, in
order:

```text
1. Authorize BEFORE calling project_root(): load census_authorization.json from
   its fixed local path and validate it in isolation (schema, contract version,
   approved operation). If the authorization record is absent or invalid, refuse
   here — before project_root(), before loading any other record, before
   resolving corpus roots, before any traversal.
2. Load source_approval.json from its fixed local path; verify census
   authorization binds to it by source_approval_sha256 (§17).
3. Only now resolve the project root and the fixed corpus roots.
4. Run the base-purity check (§9.2) and the census/verify pipeline (§9/§11).
```

`census_approved_callhome_population()` refuses if the final manifest already
exists (§15) — it never overwrites the frozen population.
`verify_frozen_callhome_population()` never writes (§11.4).

### 8.2 Opaque internal capability (not publicly constructible)

Authorization is an **opaque, module-private** capability, never a publicly
constructible dataclass whose matching fields grant traversal:

```python
_CAPABILITY_SENTINEL = object()          # module-private; never exported

@dataclass(frozen=True)
class _CensusCapability:
    _token: object                        # must be _CAPABILITY_SENTINEL (identity)
    source_approval_sha256: str
    contract_version: str
    population_schema_version: str
    approved_operation: str

def _grant_capability() -> _CensusCapability:
    """The ONLY way to obtain a valid capability. Loads census_authorization.json
    and source_approval.json from fixed local paths, verifies the authorization's
    canonical checksum and its binding to the source approval, checks contract and
    schema versions and approved operation, and only then stamps the private
    sentinel. Any failure raises authorization_error (content-free)."""

def _require_valid(capability: _CensusCapability) -> None:
    if capability._token is not _CAPABILITY_SENTINEL:
        raise CallhomePopulationError(_AUTHORIZATION_ERROR)
    # ... plus re-checks of checksum/version bindings.
```

Validity depends on the **identity** of a private module sentinel plus successful
fixed-path record loading, canonical-checksum verification, contract-version
match, and approved source-identity match. Because `_CAPABILITY_SENTINEL` is a
private `object()` that external code cannot obtain, **constructing a lookalike
`_CensusCapability` with matching public fields is insufficient** — its `_token`
can never be the sentinel. The module exports **no** public constructor, factory,
or parameter that yields a valid capability. The public entry points call
`_grant_capability()` internally; there is no capability parameter to forge.

### 8.3 Private synthetic-testing seam

```python
def _census_population_core(
    *, capability, base_dir, eng_root, spa_root, control_dir, source_approval,
    fs=<injected filesystem ops>, clock=<injected>, repository_commit=<injected>,
    publish=<injected no-overwrite publisher>,
) -> CallhomePopulationManifest: ...
```

`_census_population_core` is **private** (leading underscore), accepts injected
synthetic roots, filesystem operations, clock, Git commit, and publication
behavior **solely for tests**, and is the single implementation body the nullary
public functions call with fixed real locations. It is **not** imported by the
script, is **not** an authorization mechanism (tests pass a capability minted via
an in-test call to `_grant_capability` over a synthetic tmp control dir, or an
explicit private test-grant that still stamps the sentinel), and never appears on
the production path except beneath the two nullary entry points.

### 8.4 CLI (additional safeguard, not the boundary)

```text
scripts/census_callhome_population.py:
  fixed command name; no positional or path arguments;
  fixed base/roots/control dir/output filenames (imported from the module);
  REQUIRES an explicit, self-describing human-confirmation flag, e.g.
    --i-have-approved-local-callhome-census;
  REQUIRES successful opaque production authorization (via the nullary entry
    point) — the flag alone authorizes nothing;
  calls ONLY census_approved_callhome_population() / verify_frozen_callhome_
    population(); it never touches _census_population_core.
```

The flag is a deliberate extra speed-bump; the security boundary is the opaque
capability, which fails closed regardless of the flag.

### 8.5 All public/persisted types (no undefined names)

```python
@dataclass(frozen=True)
class CallhomeSourceMember:
    relative_path: str        # exact POSIX string (§12)
    size_bytes: int
    sha256: str

@dataclass(frozen=True)
class CallhomeSourceSnapshotId:
    provider: str
    corpus_name: str
    language: str             # "eng" | "spa"
    public_release_label: str # placeholder until G5/G6
    archive_sha256: str
    n_members: int
    # identity-only; carries the archive digest but NOT the local archive_filename.

@dataclass(frozen=True)
class CallhomeSourceSnapshot:
    provider: str; corpus_name: str; language: str; official_url: str
    public_release_label: str
    archive_filename: str; archive_size_bytes: int; archive_sha256: str
    retrieval_utc: str; extraction_procedure_id: str
    members: tuple[CallhomeSourceMember, ...]
    def identity(self) -> CallhomeSourceSnapshotId: ...

@dataclass(frozen=True)
class CallhomeSourceApproval:
    schema_version: str; contract_version: str
    provider: str; distribution_format: str      # "chat_utf8"
    english: CallhomeSourceSnapshot; spanish: CallhomeSourceSnapshot
    approved_by: str; approved_utc: str

@dataclass(frozen=True)
class CallhomePopulationEntry:
    ordinal: int
    language: str             # "eng" | "spa" (expected, directory-derived)
    relative_path: str        # exact POSIX string (§12)
    size_bytes: int
    sha256: str
    conversation_id: str      # derived (§10.5); local/reconstructive

@dataclass(frozen=True)
class CallhomePopulationCounts:
    n_english_files: int; n_spanish_files: int; n_total_files: int
    english_total_bytes: int; spanish_total_bytes: int; total_bytes: int
    n_zero_byte_files: int
    all_identity_checks_passed: bool

@dataclass(frozen=True)
class CallhomePopulationManifest:
    # --- stable scientific population fields (feed population_identity_sha256) ---
    population_schema_version: str
    population_contract_version: str
    provider: str
    distribution_format: str
    english_snapshot_id: CallhomeSourceSnapshotId
    spanish_snapshot_id: CallhomeSourceSnapshotId
    logical_roots: tuple[str, str]          # ("data/raw/callhome/eng", ".../spa")
    ordering_contract_id: str               # e.g. "eng_then_spa/bytewise_utf8/1"
    entries: tuple[CallhomePopulationEntry, ...]
    counts: CallhomePopulationCounts
    population_identity_sha256: str         # §11.1 (over stable fields only)
    # --- run/execution metadata (excluded from population identity) ---
    created_utc: str
    repository_commit: str
    source_approval_sha256: str
    census_authorization_sha256: str
    tool_version: str
    execution_status: str                   # "verified"
    # --- whole-file integrity (excludes itself) ---
    manifest_file_sha256: str               # §11.3

@dataclass(frozen=True)
class CallhomePopulationVerification:
    ok: bool
    population_identity_sha256: str
    manifest_file_sha256_ok: bool
    membership_matches: bool
    repository_commit_compatible: bool      # reported separately, never fatal
    checked_utc: str
    # content-free; carries no path/name/digest of any offending member.

@dataclass(frozen=True)
class CallhomePopulationCensusSummary:      # aggregate; LOCAL until G3 (§19)
    schema_version: str
    provider: str
    n_english_files: int; n_spanish_files: int; n_total_files: int
    english_total_bytes: int; spanish_total_bytes: int; total_bytes: int
    n_zero_byte_files: int
    all_identity_checks_passed: bool
    population_identity_sha256: str
```

A `_CensusRoots` structure (private, test-only) may exist to bundle injected
synthetic roots for `_census_population_core`; it is **not** public and **not**
accepted by the nullary production entry points.

---

## 9. Deterministic enumeration algorithm (incl. base purity)

### 9.1 Order of operations

```text
 1. Authorization gate (§8.1/§17) — BEFORE project_root(); refuse if absent/invalid.
 2. Resolve project root; resolve fixed base/roots (§7). No caller paths.
 3. Base-purity check (§9.2).
 4. Archive verification (§10.4): rehash the approved local archive(s) and compare
    to the approved archive_size/archive_sha256 before trusting extracted files.
 5. Per language (eng, then spa): non-recursive scandir(follow_symlinks=False);
    classify each child by lstat; accept iff regular non-symlink file with exact
    lowercase ".cha" suffix and no hidden/temp/metadata pattern; else
    unexpected_entry (never skipped). Empty language population -> empty_population.
 6. For each accepted member: read bytes once; compute size + SHA-256; derive exact
    POSIX relative_path (§12) and conversation_id (§10.5).
 7. Collision detection (§13) -> duplicate_identity on any collision.
 8. Language attribution / crossover check -> language_crossover.
 9. Source-identity match against the approved frozen inventory (§10.3)
    -> source_identity_mismatch on any missing/extra/modified/substituted member.
10. Ordering (§4.3); assign ordinals; assert total & reproducible -> ordering_error.
11. Compute population_identity_sha256 (§11.1); assemble manifest with run metadata;
    compute manifest_file_sha256 (§11.3).
12. Publish with no-overwrite semantics (§15); refuse if frozen manifest exists.
13. Return the verified manifest.
```

Every abort yields no partial manifest object and leaves no partial file (§15).

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

Therefore each of these fails (base-level): missing `eng`; missing `spa`; an extra
language directory; an archive under `data/raw/callhome`; an approval/control file
under `data/raw/callhome`; a hidden base entry; uppercase `ENG`/`SPA`; a symlinked
language root; a special entry. Failures use `root_error` (base structure) or
`unexpected_entry` (an extra base child), both content-free.

---

## 10. Source-snapshot approval workflow (non-circular)

The expected member inventory is **created and independently approved by prior
gates**, never generated-and-trusted by the census itself. Four separated
artifacts and gates:

### A. Candidate snapshot observation (a separately authorized metadata-only gate)

May: hash the approved local archive bytes; record archive size + SHA-256; execute
the **pinned, versioned extraction procedure**; produce the extracted member
inventory (exact member relative paths, sizes, SHA-256); write
`candidate_source_snapshot.json`. It **does not approve itself**.

Extraction procedure definition (versioned, recorded in the candidate record):

```text
procedure identifier   : e.g. "talkbank_cha_extract/1"
tool and version       : the exact archiver/tool + version
normalization policy    : none — members preserved byte-for-byte; no re-encoding,
                         no path normalization, no case change
destination layout      : eng members under <root>/eng, spa members under <root>/spa
overwrite policy        : extraction destination must be empty; never overwrite
member-path handling    : exact POSIX relative paths retained; reject any member
                         path that fails strict UTF-8 (§12) or escapes its root
```

### B. Independent approval (a separate independent review)

Verifies the candidate record against: the approved official source; expected
language; provider metadata; archive identity; extraction-procedure identity; and
the member inventory. It **freezes** a canonical `source_approval.json` and records
its canonical checksum `source_approval_sha256` (§14). Provider authenticity is
**governance-attested**: unless TalkBank supplies a cryptographically verifiable
signed artifact, the census can prove *byte-identity to an approved archive*, not
*that the archive is authentically TalkBank's*. The document does not claim
technical proof where only governance provenance exists.

### C. Census authorization (a later human-approved gate)

A human-approved `census_authorization.json` binds to:

```text
source_approval_sha256          (exact canonical checksum of the frozen approval)
contract_version
population_schema_version
approved_operation              ("census" | "verify")
```

It is **not** generated automatically by the census.

### D. Population census (this module, at run time)

Chosen non-circular contract (**the safer default**): **rehash the approved
archive from the fixed local archive directory
(`data/processed/callhome_population/archives`, outside `data/raw/callhome`) and
verify it against the approved `archive_size_bytes`/`archive_sha256` before
enumerating and verifying the extracted transcripts.** The census trusts the
frozen `source_approval.json` for the *expected* inventory, and independently
re-derives the *actual* inventory from disk, so approval and observation are never
the same act.

The census **rejects**:

```text
altered archive / changed archive size / changed archive digest
altered source approval (checksum mismatch)
altered member inventory (enumerated set ≠ approved inventory)
changed extraction-procedure identity
replayed authorization bound to a different source_approval_sha256
```

### 10.3 Member-set verification

Compare enumerated `(relative_path, size_bytes, sha256)` triples to the approved
`members`: `missing` (approved absent from disk), `extra` (on-disk not approved),
`modified` (same path, different size/sha256), `substituted` (different path
filling the count) — each `source_identity_mismatch`. Provider and
distribution_format must equal the single approved values.

### 10.5 Derived conversation identity

`conversation_id = f"{language}/{posix_stem}"` (namespaced to avoid cross-language
collision). Local/reconstructive; lives only in the local manifest; duplicates
abort `duplicate_identity` (§13).

### 10.6 Which gate freezes what

```text
gate 8  (observation)          → writes candidate_source_snapshot.json
gate 9  (candidate review)     → reviews the candidate record
gate 10 (independent approval) → freezes source_approval.json + source_approval_sha256
gate 12 (human authorization)  → writes census_authorization.json
gate 13 (real census)          → writes callhome_population_manifest.json (immutable)
```

Synthetic workflow test requirement: candidate snapshot → independent approval →
authorization → census, all over invented archives/trees.

---

## 11. Population identity vs run metadata vs manifest-file integrity

### 11.1 Stable population identity

`population_identity_sha256` = SHA-256 over the canonical serialization (§14) of a
mapping containing **only** stable scientific fields:

```text
population_schema_version
population_contract_version
provider
distribution_format
english_snapshot_id (identity-only; includes archive_sha256, n_members)
spanish_snapshot_id
logical_roots
ordering_contract_id
entries: ordered [ordinal, language, exact relative_path, size, sha256,
                  conversation_id]
```

It **excludes**: `created_utc`, any execution timestamp, `repository_commit`,
`retrieval_utc`, approval/authorization timestamps, operator, run identifier, and
any temporary filename. The same population at a different execution time or
repository commit yields the **same** `population_identity_sha256`; any change to a
member, ordering, snapshot identity, schema, or contract changes it.

### 11.2 Run/execution metadata (kept separate)

`created_utc`, `repository_commit`, `source_approval_sha256`,
`census_authorization_sha256`, `tool_version`, `execution_status` — describe the
run, not the population, and never feed `population_identity_sha256`.

### 11.3 Manifest-file integrity

`manifest_file_sha256` = SHA-256 over the canonical serialization of the **complete
manifest mapping excluding the `manifest_file_sha256` field itself** (it therefore
covers the stable fields *and* the run metadata). It is explicitly **not** the
stable population identity. Two complete manifest files produced at different times
(different `created_utc`/`repository_commit`) may have **different**
`manifest_file_sha256` while sharing the **same** `population_identity_sha256`.

### 11.4 Re-verification (`verify_frozen_callhome_population`)

```text
1. Read the existing frozen manifest (never write).
2. Recompute and validate manifest_file_sha256 over the persisted bytes.
3. Re-run base purity, archive rehash, enumeration, and hashing.
4. Recompute population_identity_sha256 from the live population.
5. Compare exact membership and stable population identity to the manifest.
6. Report repository-commit compatibility SEPARATELY (informational; never fatal).
7. Never rewrite the frozen manifest and never touch its timestamps.
Return a content-free CallhomePopulationVerification.
```

### 11.5 Required tests

```text
same population, different timestamps        → same population_identity_sha256
same population, different repository commits → same population_identity_sha256,
                                               distinct run metadata
changed member/order/snapshot/contract       → different population_identity_sha256
complete manifest bytes changed              → manifest_file_sha256 changes
verification                                 → no rewrite, no timestamp change
```

---

## 12. Exact path preservation

The manifest preserves the **exact** POSIX relative-path string produced by
enumeration. The stored identity is **never** NFC-normalized.

```text
relative_path       : the exact Python str resolved from the filesystem entry,
                      represented with POSIX "/" separators, relative to its root.
relative_path_utf8  : the exact UTF-8 encoding of relative_path, used for ordering
                      (§4.3) and identity. Need not be persisted as a second field
                      if deterministically derived, but the contract is exact:
                      ordering and identity use the exact UTF-8 bytes of the stored
                      relative_path, with no normalization.
```

NFC, NFD, and Unicode case-fold forms are computed as **transient comparison keys
for collision detection only** (§13); they **never** replace the actual path
identity in serialization. Any relative-path string that cannot be encoded under
strict UTF-8 is rejected (`unexpected_entry`).

Required tests:

```text
one decomposed-Unicode (NFD) path round-trips exactly and is re-resolvable via the
  stored exact path
an NFC/NFD path pair fails as a collision
a case-fold path pair fails as a collision
ordering uses the exact UTF-8 bytes of the stored path
serialization does not rewrite the member identity
```

---

## 13. Duplicate and collision handling (incl. zero-byte boundary)

### 13.1 Policy

Detected over the fully-enumerated member set (§9.1 step 7) using raw on-disk
bytes so NFC serialization can never mask a byte-level distinction. Every collision
is an abort (`duplicate_identity`); the census never dedups, shrinks, or merges.

| Collision | Definition |
|---|---|
| duplicate byte content | two members share a SHA-256 |
| duplicate normalized path identity | two members map to one normalized path key |
| duplicate conversation identity | two members yield the same `conversation_id` |
| Unicode NFC collision | paths differ in bytes, equal after NFC |
| Unicode NFD collision | paths differ in bytes, equal after NFD |
| case-fold collision | paths equal after Unicode case-folding, differ in bytes |

Case/normalization folding is used **only to detect** a collision, never to rewrite
membership. Aborts name only the collision class (§18), never the offending paths
or digests.

### 13.2 Rationale

Colliding members indicate an upstream packaging/extraction fault. Silently keeping
one and dropping another would reintroduce the exact non-reproducible,
investigator-chosen reduction the census prevents (§5).

### 13.3 Zero-byte duplicate boundary (P3)

```text
one authorized zero-byte .cha file  : remains a population member; it is NOT
                                      removed by the census (counted in
                                      counts.n_zero_byte_files). It is later
                                      submitted to the strict reader (a separate
                                      gate), where it will fail closed — that is
                                      the reader's job, not the census's.
two or more authorized zero-byte     : all share the empty-input SHA-256
 .cha files                            (e3b0c442... — the well-known SHA-256 of the
                                      empty byte string) and therefore trigger the
                                      standard duplicate-byte population stop
                                      (duplicate_identity).
```

This is deliberate fail-closed behavior, not an automatic exclusion. Both cases are
required synthetic tests: one zero-byte file retained as a member; two zero-byte
files abort with `duplicate_identity`.

---

## 14. Manifest serialization and checksums

### 14.1 Canonical serialization (used for every checksum and every persisted file)

```text
- UTF-8 bytes.
- json.dumps(..., sort_keys=True, ensure_ascii=False, separators=(",", ":")).
- Exactly one trailing "\n".
- String values are serialized VERBATIM (no NFC/NFD normalization of any
  relative_path or identity string; §12).
- Array order is the census order for entries (already total).
```

### 14.2 Checksum procedures

```text
source_approval_sha256      : SHA-256 over the canonical serialization of the
                              source_approval mapping (schema_version, contract_
                              version, provider, distribution_format, english,
                              spanish, approved_by, approved_utc), with english/
                              spanish serialized as their full snapshot mappings
                              (including members) in canonical form. This is the
                              exact mapping the census authorization binds to.
population_identity_sha256  : SHA-256 over the canonical serialization of the
                              stable-fields mapping (§11.1) — run metadata excluded.
manifest_file_sha256        : SHA-256 over the canonical serialization of the
                              complete manifest mapping EXCLUDING the
                              manifest_file_sha256 field; inserted last before write.
census_authorization_sha256 : SHA-256 over the canonical serialization of the
                              census_authorization mapping.
```

Re-verification recomputes each and asserts equality (`manifest_mismatch` on any
difference).

---

## 15. Immutable no-overwrite publication and atomic output

### 15.1 The frozen manifest is immutable once published

`callhome_population_manifest.json` must **never** be silently overwritten. A
census run **refuses** if the final manifest already exists, with the fixed
category `frozen_output_exists`, and directs the caller to
`verify_frozen_callhome_population()`. `os.replace` is **not** used for the final
manifest, because it silently overwrites an existing file.

### 15.2 Safe no-overwrite publication sequence

```text
1. Ensure data/processed/callhome_population/ exists.
2. Create a uniquely-named same-directory temp file with EXCLUSIVE creation
   (os.open with O_CREAT | O_EXCL | O_WRONLY).
3. Write canonical bytes.
4. flush + os.fsync the temp file descriptor.
5. Publish only if the final file does not exist, via an atomic no-overwrite
   primitive: os.link(temp, final) (fails with FileExistsError if final exists),
   then unlink the temp file. (Equivalently, open the final path directly with
   O_CREAT | O_EXCL and write there; the link approach keeps the write atomic and
   the publish no-overwrite.)
6. os.fsync the containing directory where the platform supports it.
7. On any failure, remove the temp file where cleanup succeeds (§15.4).
8. Never alter an existing valid manifest.
```

**Residual assumption:** `os.link` + `O_EXCL` give atomic no-overwrite publication
on a single POSIX filesystem (the only supported target: a local
`data/processed/…` directory on one volume). The census does not support network
filesystems or cross-volume publication; if the platform cannot guarantee atomic
no-overwrite with these primitives, the implementation must fail closed
(`output_error`) rather than fall back to an overwriting rename. This is the exact
protected sequence and its stated residual assumption — no false guarantee is made.

### 15.3 Verification and repeated execution

Verification never writes, replaces, touches timestamps, or changes manifest bytes.
A second census against an existing frozen manifest **refuses write mode**
(`frozen_output_exists`) and points to verification; it never silently creates a
new scientific population record. A future new snapshot requires a new explicit
approval/version gate (a new `source_approval.json` under a new contract/schema
version), not an overwrite.

### 15.4 Cleanup and error precedence

```text
- A cleanup failure must NOT mask the primary failure: the primary content-free
  category is raised; a cleanup problem becomes a sanitized secondary local status
  or a privacy-safe secondary category, never replacing the primary error.
- Cleanup never prints protected paths or names.
- The production script catches approved ordinary exceptions at the top level and
  emits only a fixed governance-safe message and a stable nonzero exit code; it
  never prints a traceback or any protected detail.
- KeyboardInterrupt and SystemExit still propagate as the exact same object.
```

### 15.5 Required tests

```text
existing frozen manifest → census refuses (frozen_output_exists)
verification leaves bytes and timestamps unchanged
serialization failure / disk-full write failure / permission failure /
  publication failure / directory-fsync failure (simulated) → sanitized category
cleanup failure during another failure → primary failure preserved, not masked
a prior valid manifest is preserved on any failure
no partial final artifact remains
no protected stdout/stderr
deterministic fixed output filename
```

---

## 16. Persisted record schemas

For **every** persisted record: a fixed filename; `schema` identifier; `schema_
version`; the allowed and required fields; allowed values; canonical serialization
(§14.1); and fail-closed loading. **Loading rules apply to all records:**

```text
unknown/extra field   → reject (schema_error)
missing required field → reject (schema_error)
duplicate JSON key    → reject (schema_error) — loader uses a strict object hook
                        that raises on repeated keys; JSON duplicate keys never
                        silently last-wins
mistyped field        → reject (schema_error)
invalid enum value    → reject (schema_error)
unsupported schema id  → reject (schema_error)
unsupported version    → reject (schema_error)
non-canonical bytes where a canonical form is required (records whose checksum is
  bound elsewhere: source_approval.json, census_authorization.json, the manifest)
                       → reject (serialization_error / manifest_mismatch)
invalid checksum       → reject (source_identity_mismatch / manifest_mismatch /
                        authorization_error as appropriate)
```

All schema failures are content-free (§18). Privacy classification per §19.

### 16.1 `candidate_source_snapshot.json`  (gate 8; LOCAL ONLY)

```text
schema="callhome_candidate_source_snapshot"; schema_version="1"
required: provider, distribution_format, extraction_procedure_id, tool_version,
  observed_utc, english{snapshot}, spanish{snapshot}
each snapshot: corpus_name, language, official_url, public_release_label,
  archive_filename, archive_size_bytes, archive_sha256, retrieval_utc,
  members[ {relative_path, size_bytes, sha256} ]
privacy: LOCAL ONLY (archive names, member paths, digests).
```

### 16.2 `source_approval.json`  (gate 10; canonical, checksum-bound)

```text
schema="callhome_source_approval"; schema_version="1"
required: schema_version, contract_version, provider, distribution_format,
  english{snapshot}, spanish{snapshot}, approved_by, approved_utc
canonical: yes — its canonical serialization defines source_approval_sha256 (§14.2)
privacy: member inventory + archive identity LOCAL ONLY; provider/corpus/citation
  labels are public facts (§19) but the file as a whole stays local.
```

### 16.3 `census_authorization.json`  (gate 12; checksum-bound)

```text
schema="callhome_census_authorization"; schema_version="1"
required: schema_version, contract_version, population_schema_version,
  approved_operation ("census"|"verify"), source_approval_sha256, approved_by,
  approved_utc
canonical: yes — defines census_authorization_sha256; MUST bind to the current
  source_approval_sha256 or authorization fails closed.
privacy: LOCAL ONLY.
```

### 16.4 `callhome_population_manifest.json`  (gate 13; immutable)

```text
schema="callhome_population_manifest"; schema_version="1"
fields: exactly the CallhomePopulationManifest fields (§8.5) — stable population
  fields, run metadata, and manifest_file_sha256.
canonical: yes; manifest_file_sha256 computed per §11.3/§14.2.
immutability: no-overwrite publication (§15).
privacy: LOCAL ONLY (per-file identities, conversation ids, checksums).
```

### 16.5 `callhome_population_census_summary.json`  (aggregate; LOCAL until G3)

```text
schema="callhome_population_census_summary"; schema_version="1"
fields: exactly CallhomePopulationCensusSummary (§8.5).
privacy: LOCAL ONLY UNDER CURRENT POLICY; ELIGIBLE FOR FUTURE G3 REVIEW for the
  specific aggregate fields — NOT CURRENTLY APPROVED for commit (§19).
```

### 16.6 Round-trip / malformed tests

```text
valid round trip for each record
unknown field / missing field / duplicate key / wrong type / unsupported schema /
  unsupported version / invalid enum / invalid checksum / non-canonical input where
  canonical is required → each a fixed content-free failure
```

---

## 17. Authorization control (detailed)

### 17.1 Mechanism

```text
- The ONLY way to obtain a valid capability is _grant_capability() (§8.2), which:
    1. loads census_authorization.json from its fixed local path;
    2. validates its schema/version/operation and canonical checksum;
    3. loads source_approval.json; verifies the authorization's
       source_approval_sha256 equals the approval's canonical checksum;
    4. checks contract_version and population_schema_version match;
    5. stamps the private module sentinel (_CAPABILITY_SENTINEL) into the frozen
       capability. Any failure raises authorization_error (content-free).
- Public entry points call _grant_capability() BEFORE project_root() and BEFORE any
  corpus traversal; a missing/invalid authorization refuses there.
- The script additionally requires the explicit human-confirmation flag AND a
  successful opaque authorization; the flag alone authorizes nothing.
```

### 17.2 What it proves / does not prove

```text
Proves      : a human deliberately created census_authorization.json binding (by
              canonical checksum) to a specific independently-frozen source
              approval, and ran the fixed runner with an explicit self-describing
              flag.
Does NOT     : prove the archives are authentically TalkBank's (governance G1/G2;
prove         only byte-identity to an approved archive is technically proven),
              nor that any transcript is monolingual (later validation), nor grant
              Decision B commit permission (G3).
```

### 17.3 Why it is not security theater; why tests still work

```text
- Validity depends on a private sentinel IDENTITY plus checksum-bound record
  loading; a lookalike object with matching public fields is rejected (§8.2).
- There is NO public capability parameter, constructor, or factory; the production
  entry points are nullary, so there is nothing to forge or inject on the public
  path.
- Two deliberate artifacts are required (the local authorization record + the
  explicit flag), both absent by default; an ordinary typo cannot synthesize
  either, so accidental real traversal is impossible.
- Tests exercise the logic synthetically via _census_population_core with an
  in-test-granted capability over a tmp control dir, proving BOTH the allow-path
  and the refuse-before-traversal path without any real corpus.
```

### 17.4 Closure tests

```text
public production functions expose no roots/output/write/glob/subset/provider args
constructing a lookalike _CensusCapability cannot authorize traversal
missing/invalid authorization refuses BEFORE project_root(), before loading any
  record beyond the authorization record, before root resolution, before traversal
the script cannot bypass the nullary production entry point
synthetic tests use only the private core; the script never imports the core
```

No authorization is granted by this design gate.

---

## 18. Error and privacy contract (complete coverage)

### 18.1 Closed content-free category taxonomy

```text
environment_error         root_error                unexpected_entry
source_identity_mismatch  manifest_mismatch         empty_population
language_crossover        duplicate_identity        ordering_error
serialization_error       output_error              authorization_error
privacy_error             schema_error              frozen_output_exists
archive_verification_error
```

Each is a fixed string carried alone by `CallhomePopulationError(category)`. A
category names the failing **check**, never the offending item.

### 18.2 Coverage: every operation maps to a content-free category

```text
base enumeration            → root_error / unexpected_entry
archive hashing / verify    → archive_verification_error
member hashing              → source_identity_mismatch / output-independent read
                              failure → environment_error/root_error (no path)
approval-record loading     → schema_error / source_identity_mismatch
JSON parsing                → schema_error
duplicate-key detection     → schema_error
canonical serialization     → serialization_error
temp-file creation          → output_error
write / flush / file fsync  → output_error
publication (link/O_EXCL)   → frozen_output_exists (exists) / output_error (other)
directory fsync             → output_error
cleanup                     → sanitized secondary status; never masks primary (§15.4)
top-level script handling   → fixed governance-safe message + stable nonzero exit
```

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
- Filesystem failures (FileNotFoundError, PermissionError, OSError) become
  fixed categories exposing no path or original text.
- Cleanup-error precedence: the primary error always wins (§15.4).
```

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
| population/contract/schema versions | ALREADY TRACKED PUBLIC FACT |
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
  change MIGHT permit them; that possibility is noted in prose only and does NOT
  make them a current commit candidate.
- file counts by language and all_identity_checks_passed are NOT approved merely
  for being aggregates; they stay LOCAL until G3 explicitly approves those exact
  fields (per-output review — a low-cardinality count can be reconstructive).
- failure-reason counts and small cells REQUIRE SEPARATE GOVERNANCE DECISION.
- a failed or anomalous census produces NO numeric committed bundle.
- per-file identities are LOCAL ONLY; transcript-derived content is FORBIDDEN.
```

This document does **not** imply Decision B has expanded. Until G3, nothing in
`data/processed/callhome_population/` is committed.

---

## 20. Synthetic test matrix (integrated closure tests)

All fixtures are invented (synthetic `.cha` byte blobs, `AAA`/`BBB`-style names,
`syn_*` tokens, unique sentinels, synthetic archives). No real corpus filename,
hash, archive name, conversation id, or text. Tests use only the private core
(§8.3).

```text
Public API / authorization (§8/§17)
  - nullary production functions expose no roots/output/write/glob/subset/provider
  - lookalike _CensusCapability cannot authorize traversal
  - missing/invalid authorization refuses BEFORE project_root()/record load/
    root resolution/traversal (assert roots never scanned via a guard)
  - allow-path with an in-test-granted capability
  - the script drives only the nullary entry point; never the core

Base purity (§9.2)
  - base contains exactly {eng, spa} → pass
  - missing eng / missing spa / extra dir / archive under base / control file under
    base / hidden base entry / ENG or SPA / symlinked root / special entry → fail

Snapshot workflow (§10)
  - candidate → independent approval → authorization → census (happy path)
  - altered archive / changed archive size / changed archive digest → fail
  - altered source approval (checksum) → fail
  - altered member inventory (missing/extra/modified/substituted) → fail
  - changed extraction-procedure identity → fail
  - replayed authorization bound to a different source_approval_sha256 → fail

Enumeration / rejection (§4/§9)
  - correct census → verified manifest, correct counts, ordinals 0..N-1
  - nested dir / hidden / metadata / temp / uppercase suffix / archive / broken
    symlink / special file → unexpected_entry
  - empty English / empty Spanish population → empty_population

Determinism / identity (§4.3/§11/§12)
  - stable ordering regardless of creation order; locale independence
  - same population, different timestamps → same population_identity_sha256
  - same population, different repository commits → same population_identity_sha256,
    distinct run metadata
  - changed member/order/snapshot/contract → different population_identity_sha256
  - complete manifest bytes changed → manifest_file_sha256 changes
  - decomposed (NFD) path round-trips exactly and is re-resolvable
  - NFC/NFD and case-fold path pairs → duplicate_identity
  - ordering uses exact UTF-8 bytes; serialization does not rewrite identity
  - verification never rewrites bytes or timestamps

Collisions / zero-byte (§13)
  - duplicate byte content / duplicate conversation id → duplicate_identity
  - one zero-byte .cha retained as a member (counted)
  - two zero-byte .cha → duplicate_identity (empty-input SHA-256)

Immutable output (§15)
  - existing frozen manifest → census refuses (frozen_output_exists)
  - fixed final filename; deterministic
  - serialization / write / permission / publication / directory-fsync failures →
    sanitized category; no partial final artifact; prior valid manifest preserved
  - cleanup failure during another failure does not mask the primary failure

Schemas (§16)
  - valid round trip for each of the 5 records
  - unknown / missing / duplicate-key / mistyped / unsupported-schema /
    unsupported-version / invalid-enum / invalid-checksum / non-canonical → fail

Privacy / control-flow (§18)
  - injected sentinels (path, filename, digest, member name, archive name) absent
    from str/repr/args/__cause__/__context__/stdout/stderr of any raised error
  - every ordinary error: __cause__ is None and __context__ is None
  - injected KeyboardInterrupt() and SystemExit() propagate as the exact object
  - the script emits no traceback or protected detail; stable nonzero exit code
```

---

## 21. Routing protections

The census records `language` (directory-derived, **expected, not verified**) and
source identity; it does **not** compute condition eligibility and emits no
`condition_candidates`, so it cannot route CALLHOME into `CsCont`. Directory name
is evidence of expectation only; actual language is verified downstream. The
permanent routing is independently enforced at each of: the source manifest, the
strict-execution manifest, linguistic validation (verified monolinguality — a
directory label never validates), projection, promotion (`clean` only after
validation + explicit approval; CALLHOME `clean` routes only to
EnglishMono/MonoCont for eng or SpanishMono/MonoCont for spa), the condition
manifest, and final construction. None of these is this census module.

---

## 22. Deferred strict-execution layer (its own later gate)

A later, separately-designed and separately-reviewed module executes the strict
reader over the frozen population. Contract sketch (not designed here):

```text
- re-verify the frozen manifest (manifest_file_sha256 + membership + population
  identity) before any read;
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
and any committed CALLHOME-derived result. None is resolved here; the corpus is
not accessed to resolve them.

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
non-bypassable production API        — §8.1 (nullary), §8.2 (opaque capability)
opaque authorization mechanism       — §8.2, §17
fixed base/root/output locations     — §7
exact base purity                    — §9.2
non-circular snapshot approval        — §10 (A→B→C→D; census rehashes archive)
exact fixed filenames                — §7, §16
exact schemas                        — §16 (all 5 records + loading rules)
stable population identity           — §11.1
separate run and file identity       — §11.2, §11.3
exact path preservation              — §12
immutable no-overwrite manifest      — §15.1
complete atomic publication behavior — §15.2 (+ residual assumption)
complete privacy/error handling      — §18 (all operations covered)
zero-byte duplicate boundary         — §13.3
correct Decision B classifications   — §19 (five explicit categories)
all closure tests                    — §20
updated future gates                 — §24
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
```
