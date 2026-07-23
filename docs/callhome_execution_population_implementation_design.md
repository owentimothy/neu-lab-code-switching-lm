# CALLHOME Execution-Population Census — Implementation Design

**Status:** Design only. No implementation, no tests, no script, no `.gitignore`
change, no real corpus access, no private-directory inspection, no census, no
hashing of real files, no strict-reader execution, no dataset construction. This
document is an implementation-ready contract for a **later, separately reviewed**
synthetic-only implementation gate.

**Permission state:** Decision B (see `docs/callhome_ground_rules.md`) —
aggregate-only, non-transcript CALLHOME summaries *may* be committed with citation
notes; per-row records, conversation identifiers, filenames, and transcript-
bearing outputs remain blocked and stay local/gitignored. This design does **not**
assert Decision B has expanded, and does **not** claim G3 has approved any census
aggregate for commit.

---

## 0. Finding-closure map (two review rounds)

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

Round-1 findings are reopened only where round-2 changes must stay consistent
with them.

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
**bytes** to compute a SHA-256 digest is not parsing: each `.cha` file (and each
approved archive) is an opaque byte stream for hashing only.

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
  └── synthetic filesystem fixtures only; uses ONLY the private core.
```

The module depends only on the standard library (`pathlib`, `hashlib`, `os`,
`stat`, `json`, `unicodedata`, `dataclasses`, `io`) and
`cslm.utils.paths.project_root`. It has **no dependency** on `callhome_chat` or any
projection/screening module, so it cannot accidentally parse transcript content.

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

### 8.3 Private synthetic-testing seam

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
@dataclass(frozen=True)
class CallhomeSourceMember:
    relative_path: str        # exact POSIX str (§12); strict-UTF-8; LOC
    size_bytes: int           # >= 0; LOC
    sha256: str               # 64 lowercase hex; LOC

@dataclass(frozen=True)
class CallhomeExtractionProcedure:
    procedure_id: str         # e.g. "talkbank_cha_extract/1"; PUB label
    tool_name: str            # PUB label
    tool_version: str         # PUB label
    normalization_policy: str # fixed "none_byte_for_byte" (§10.A); PUB
    destination_layout: str   # fixed "eng_root_spa_root"; PUB
    overwrite_policy: str     # fixed "empty_destination_no_overwrite"; PUB
    member_path_policy: str   # fixed "exact_posix_no_escape_strict_utf8"; PUB

@dataclass(frozen=True)
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

@dataclass(frozen=True)
class CallhomeSourceSnapshotId:                 # identity-only view (no archive_filename)
    provider: str; corpus_name: str; language: str
    public_release_label: str; archive_sha256: str; n_members: int

@dataclass(frozen=True)
class CallhomeCandidateSourceSnapshotRecord:    # candidate_source_snapshot.json
    schema: str               # "callhome_candidate_source_snapshot"
    schema_version: str       # "1"
    observed_utc: str
    provider: str
    distribution_format: str  # "chat_utf8"
    english: CallhomeSourceSnapshot
    spanish: CallhomeSourceSnapshot
    # NOTE: extraction procedure lives INSIDE each snapshot, not at top level.

@dataclass(frozen=True)
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

@dataclass(frozen=True)
class CallhomeCensusAuthorizationRecord:         # census_authorization.json (checksum-bound)
    schema: str               # "callhome_census_authorization"
    schema_version: str       # "1"
    contract_version: str
    population_schema_version: str   # MUST equal the manifest's schema_version
    approved_operation: str          # "census" | "verify"
    source_approval_sha256: str
    approved_by: str
    approved_utc: str

@dataclass(frozen=True)
class CallhomePopulationEntry:
    ordinal: int              # 0..N-1
    language: str             # "eng" | "spa" (expected, directory-derived)
    relative_path: str        # exact POSIX str (§12); LOC
    size_bytes: int           # >= 0; LOC
    sha256: str               # 64 hex; LOC
    conversation_id: str      # derived (§10.5); LOC

@dataclass(frozen=True)
class CallhomePopulationCounts:                  # canonical stable field (§11.6)
    n_english_files: int; n_spanish_files: int; n_total_files: int
    english_total_bytes: int; spanish_total_bytes: int; total_bytes: int
    n_zero_byte_files: int
    all_identity_checks_passed: bool             # always True in a persisted manifest

@dataclass(frozen=True)
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

@dataclass(frozen=True)
class CallhomePopulationVerification:
    ok: bool
    population_identity_sha256: str
    manifest_file_sha256_ok: bool
    membership_matches: bool
    counts_reconciled: bool                      # §11.6
    repository_commit_compatible: bool           # reported separately, never fatal
    checked_utc: str
    # content-free; carries no path/name/digest of any offending member.

@dataclass(frozen=True)
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
 7. Collision detection (§13) -> duplicate_identity on any collision.
 8. Language attribution / crossover check -> language_crossover.
 9. Source-identity match against the approved frozen inventory (§10.3)
    -> source_identity_mismatch on any missing/extra/modified/substituted member.
10. Ordering (§4.3); assign ordinals; assert total & reproducible -> ordering_error.
11. Derive counts from entries and reconcile (§11.6); compute
    population_identity_sha256 (§11.1); assemble manifest with run metadata;
    compute manifest_file_sha256 (§11.3).
12. Publish via the six-state no-overwrite machine (§15); refuse if the frozen
    manifest exists (frozen_output_exists).
13. Return the verified manifest.
```

Every abort yields no partial manifest object; publication failures follow §15.3.

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
case-fold, remove another suffix, or rely on `Path.stem` without noting it is only
acceptable if it is exactly equivalent to removing the final `.cha` (it is not, for
multi-dot names, so use `filename[:-4]`). Examples (invented names):

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

The persisted filename is a **basename, never a path**. Any violation →
`source_identity_mismatch` (approval-bound records) or `schema_error` (candidate).

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
Failures use `archive_verification_error` (directory/identity/digest) or
`source_identity_mismatch`/`schema_error` (basename), all content-free.

Closure tests: absolute path / `../` traversal / nested path / forward- or
backslash / `"."` / `".."` / NUL rejected; symlink or special archive rejected;
same English/Spanish basename rejected; same inode via hard link rejected;
unexpected third archive rejected; hidden/temp archive entry rejected; changed
archive size or digest rejected.

Synthetic workflow test requirement: candidate snapshot → independent approval →
authorization → census, all over invented archives/trees.

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

### 11.4 Re-verification (`verify_frozen_callhome_population`)

```text
1. Read the existing frozen manifest (never write).
2. Recompute and validate manifest_file_sha256 over the persisted bytes.
3. Re-run bootstrap/authorization, base purity, archive confinement + rehash,
   enumeration, and hashing.
4. Recompute counts from live entries and reconcile (§11.6).
5. Recompute population_identity_sha256; compare exact membership and stable
   identity to the manifest.
6. Report repository-commit compatibility SEPARATELY (informational; never fatal).
7. Never rewrite the frozen manifest and never touch its timestamps.
Return a content-free CallhomePopulationVerification.
```

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
checksums). Reconciliation runs at initial construction, persisted-record loading,
and re-verification.

Required tampering tests (each must fail even when both checksums were recomputed
over the altered record): `n_english_files`, `n_spanish_files`, `n_total_files`,
`english_total_bytes`, `spanish_total_bytes`, `total_bytes`, `n_zero_byte_files`,
`all_identity_checks_passed`. Plus a test that reconciliation occurs at
construction, loading, and re-verification.

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
is rejected (`unexpected_entry`). Required tests: an NFD path round-trips exactly
and is re-resolvable via the stored exact path; NFC/NFD and case-fold path pairs
fail as collisions; ordering uses the exact UTF-8 bytes; serialization does not
rewrite the member identity.

---

## 13. Duplicate and collision handling (incl. zero-byte boundary)

### 13.1 Policy

Detected over the fully-enumerated member set (§9.1 step 7) using raw on-disk bytes
so NFC serialization can never mask a byte-level distinction. Every collision is an
abort (`duplicate_identity`); the census never dedups, shrinks, or merges.

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

Re-verification recomputes each and asserts equality (`manifest_mismatch` /
`source_identity_mismatch` / `authorization_error` as appropriate).

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
invalid checksum       → reject (source_identity_mismatch / manifest_mismatch /
                         authorization_error as appropriate)
non-canonical bytes where a checksum binds the canonical form (source_approval.json,
  census_authorization.json, the manifest) → reject (serialization_error /
  manifest_mismatch)
```

Manifest loading additionally runs the §11.6 counts reconciliation.

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
`schema_version="1"`. Loading validates `manifest_file_sha256` (§11.3), the counts
reconciliation (§11.6), and the stable-identity recomputation (§11.1). LOCAL ONLY
(per-file identities, conversation ids, checksums). No-overwrite publication (§15).

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
authorization/approval loading → authorization_error / schema_error /
                                 source_identity_mismatch
base enumeration            → root_error / unexpected_entry
archive-dir purity / basename / identity → archive_verification_error /
                                 source_identity_mismatch / schema_error
archive hashing / verify    → archive_verification_error
member hashing              → source_identity_mismatch; read failure →
                              environment_error/root_error (no path)
counts reconciliation       → manifest_mismatch
JSON parsing / duplicate key → schema_error
canonical serialization     → serialization_error
temp-file creation / write / flush / file fsync → output_error
link publication            → frozen_output_exists (exists) / output_error (other)
post-link durability (dir fsync / unlink / dir fsync) → publication_verification_required
cleanup                     → sanitized secondary status; never masks primary (§15.5)
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
- Filesystem failures (FileNotFoundError, PermissionError, OSError) become fixed
  categories exposing no path or original text.
- Cleanup-error precedence: the primary error always wins (§15.5).
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
name, conversation id, or text. Tests use only the private core (§8.3).

```text
Bootstrap / authorization (§8/§17)
  - nullary functions expose no roots/output/write/glob/subset/provider args
  - lookalike _CensusCapability (public fields) cannot authorize traversal
  - CWD change to a dir with a lookalike authorization record has no effect
  - missing bootstrap marker fails before private-path resolution
  - invalid authorization fails before project_root()
  - project_root()/bootstrap mismatch fails before archive/corpus traversal
  - bootstrap performs no access under data/raw
  - no env/CLI override changes the bootstrap root
  - the script drives only the nullary entry point; never the core

Base purity (§9.2)
  - base contains exactly {eng, spa} → pass
  - missing eng / missing spa / extra dir / archive under base / control file under
    base / hidden base entry / ENG or SPA / symlinked root / special entry → fail

Archive confinement (§10.7)
  - absolute / ../ / nested / forward- or backslash / "." / ".." / NUL basename → fail
  - symlink or special archive → fail
  - same eng/spa basename → fail
  - same inode via hard link → fail
  - unexpected third archive / hidden / temp archive entry → fail
  - changed archive size or digest → fail

Snapshot workflow (§10)
  - candidate → independent approval → authorization → census (happy path)
  - altered archive / size / digest → fail
  - altered source approval (checksum) → fail
  - altered member inventory (missing/extra/modified/substituted) → fail
  - changed extraction-procedure identity → fail
  - eng vs spa extraction-procedure contract mismatch → fail (§8.5)
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
  - changed member/order/snapshot/contract/count → different population_identity_sha256
  - complete manifest bytes changed → manifest_file_sha256 changes
  - NFD path round-trips exactly and is re-resolvable
  - NFC/NFD and case-fold path pairs → duplicate_identity
  - ordering uses exact UTF-8 bytes; serialization does not rewrite identity
  - verification never rewrites bytes or timestamps

Counts reconciliation (§11.6)
  - tamper each of the 8 count fields (with both checksums recomputed) → manifest_mismatch
  - reconciliation occurs at construction, loading, and re-verification

Conversation identity (§10.5)
  - single-dot / multi-dot / Unicode name / equal eng-spa stems / name ending in
    another suffix before .cha → correct f"{language}/{filename[:-4]}"

Collisions / zero-byte (§13)
  - duplicate byte content / duplicate conversation id → duplicate_identity
  - one zero-byte .cha retained as a member (counted)
  - two zero-byte .cha → duplicate_identity (empty-input SHA-256)

Publication state machine (§15)
  - inject failure at each transition (temp create / write / flush / file fsync /
    link / first dir fsync / temp unlink / second dir fsync); assert exactly one of:
    no final exists | existing final preserved | byte-complete final +
    publication_verification_required | durable success
  - existing frozen manifest → frozen_output_exists; fixed deterministic filename
  - no partially-written final ever visible; post-link failures never delete final
  - residual temp names not printed; verification does not clean up or rewrite
  - cleanup failure during another failure does not mask the primary

Schemas (§16)
  - valid round trip for each of the 5 records; fixed canonical vectors match
    dataclass fields / JSON / checksum inputs / schema tables
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
