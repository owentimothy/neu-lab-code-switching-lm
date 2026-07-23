# CALLHOME Execution-Population Census — Implementation Design

**Status:** Design only. No implementation, no tests, no script, no `.gitignore`
change, no real corpus access, no private-directory inspection, no population
census, no hashing of real files, no strict-reader execution, no dataset
construction. This document is an implementation-ready contract for a **later,
separately reviewed** synthetic-only implementation gate.

**Permission state:** Decision B (see `docs/callhome_ground_rules.md`) —
aggregate-only, non-transcript CALLHOME summaries may be committed with the
required citation/license notes; per-row records, conversation identifiers,
filenames, and transcript-bearing outputs remain blocked from commit and stay
local/gitignored. This design does **not** claim Decision B has approved the new
census aggregate schema; that approval (G3) is an explicit open decision below.

**Preflight authority:** the read-only execution-population preflight returned
`WARNING` (governance-only) with no substantive P0–P3 findings and
"EXECUTION-POPULATION DESIGN ACCEPTED — READY FOR BOUNDED IMPLEMENTATION DESIGN."
The three governance prerequisites (pin English/Spanish snapshots; approve the
census + strict-result disclosure schemas under Decision B; finalize public
citation/release labels) are recorded in the Governance Decision Register (§19)
and block real execution, not synthetic design.

---

## 1. Status and scope

### 1.1 What this layer is

The **metadata-only census layer**: given two fixed, gitignored local transcript
roots and an approved source-identity specification, it deterministically
enumerates the complete CALLHOME transcript population, computes local identity
metadata (size + SHA-256 + derived conversation identity per file), detects
duplicate and colliding identities, verifies the enumeration against an approved
frozen source manifest, and writes a **local-only** frozen population manifest.
It then can re-verify that manifest without changing membership, and emit only an
explicitly approved, privacy-safe **aggregate** census.

### 1.2 What this layer is not

This layer **does not** parse transcript contents. It never opens a `.cha` file
as text, never tokenizes, never language-labels, never screens, never validates
monolinguality, never projects, never promotes, never constructs a condition
dataset, and never assigns a train/dev/test split. It must not import or call
`read_chat_transcript`, `parse_chat_file`, or `parse_chat_lines`. Strict-reader
execution over the frozen population is a **separate later module and gate** (§18).

Reading raw **bytes** to compute a SHA-256 digest is not "parsing": the census
treats each `.cha` file as an opaque byte stream for hashing only and derives no
linguistic content from it.

### 1.3 Exact implementation file scope (for the later gate)

```text
src/cslm/data/callhome_population.py     # production module (metadata-only census)
scripts/census_callhome_population.py    # fixed-root, authorization-gated runner
tests/test_callhome_population.py        # synthetic filesystem fixtures only
.gitignore                               # one narrow entry (see §7 / §11.8)
```

No other file may change in the implementation gate. This design document itself
is the only file changed in the current docs-only gate.

---

## 2. Scientific rationale

The project trains four comparable BERT-style masked-language encoders —
`EnglishMono`, `SpanishMono`, `MonoCont`, `CsCont` — and the principal comparison
is `CsCont − MonoCont`. The monolingual/no-CS conditions are sourced from
CALLHOME; `CsCont` is Bangor-only. Permanent source routing:

```text
CALLHOME English  → EnglishMono and MonoCont only
CALLHOME Spanish  → SpanishMono and MonoCont only
CALLHOME          → never CsCont
Bangor Miami      → CsCont only
```

Before a single CALLHOME row can be validated, screened, or promoted, the project
must fix **exactly which files constitute the population**. If the population
drifts — a provider is silently mixed, one language's archive is a different
snapshot than the other's, a file is silently omitted or duplicated, a language
crosses over, or files are quietly excluded after the fact — then the eventual
training corpora differ for reasons unrelated to code-switching. That is an
uncontrolled sampling confound sitting upstream of `CsCont − MonoCont`.

The census exists to make population membership **deterministic, frozen, and
auditable** before any linguistic processing begins, and to **fail closed** on
any anomaly rather than guess. It is the sampling-frame analogue of the strict
CHAT reader: the reader guarantees each file is read faithfully; the census
guarantees the *set of files* is exactly the approved set, in a fixed order, with
verified identities.

---

## 3. Accepted source authority

Fixed upstream decision (see `docs/callhome_access_verification.md`,
`docs/callhome_ground_rules.md`):

```text
Provider           : TalkBank CABank only (the canonical distribution)
English authority  : one approved TalkBank CABank CallHome English CHAT snapshot
Spanish authority  : one approved TalkBank CABank CallHome Spanish CHAT snapshot
LDC (LDC97T14 /    : historical provenance or a separately approved fallback only;
 LDC96T17)           never mixed with the primary TalkBank population
```

Logical transcript roots (both gitignored; never committed):

```text
data/raw/callhome/eng
data/raw/callhome/spa
```

The census consumes the **TalkBank UTF-8 `.cha`** distribution (consistent with
the strict reader's `@UTF8` requirement). It does not consume LDC ISO-8859-1
transcripts. Any approved LDC fallback would be a **separate, distinctly-labelled
source approval** and would never be blended into a TalkBank population manifest.

No real archive filename, size, digest, URL, citation string, snapshot label, or
conversation identifier appears anywhere in this document. Citation and release
labels are governance decisions G5/G6 and are `TODO` in
`docs/callhome_ground_rules.md`; this design uses placeholders only.

---

## 4. Population contract

### 4.1 Membership

Population membership is: **every direct, regular, non-symlink file with an exact
lowercase `.cha` suffix that is present directly inside an approved logical root
and matches the approved frozen source manifest.** Enumeration is **non-recursive**
(direct children only). Both language populations must be **nonempty**.

A **zero-byte** authorized `.cha` file remains in the population (it is a real
member and is later submitted to strict validation, where it will fail closed —
that is the later layer's job, not the census's). The census never deduplicates,
filters, shrinks, or "repairs" the population.

### 4.2 Structural rules (each violation aborts)

```text
roots and their parents must be real, non-symlink directories
non-recursive enumeration (no descent into subdirectories)
both eng and spa populations nonempty
no unexpected root entries        (anything that is not an accepted .cha member)
no nested directories inside a root
no archives inside transcript roots (e.g. *.zip, *.tgz, *.tar, *.gz)
no hidden files                   (name begins with ".")
no temporary files                (e.g. *~, *.tmp, *.swp, *.part, #...#)
no macOS metadata                 (.DS_Store, ._* AppleDouble files)
no uppercase or mixed-case suffix (.CHA, .Cha — exact lowercase .cha only)
no special files                  (symlink, FIFO, socket, device, block)
no broken symlinks
no silent-ignore policy           (an unexpected entry is an error, never skipped)
```

"No silent-ignore policy" is load-bearing: the census must **never** encounter a
filesystem entry it quietly drops. Every entry is either an accepted `.cha` member
or an `unexpected_entry` abort.

### 4.3 Ordering (total, deterministic, locale-independent)

```text
Primary  : language — English (eng) before Spanish (spa)
Secondary: within each language, ascending BYTEWISE ordering of the UTF-8-encoded
           POSIX relative-path string (compare raw bytes, not locale collation,
           not NFC/NFD-folded, not case-folded)
```

Ordinals are assigned `0..N-1` over the concatenation (all eng entries, then all
spa entries) after sorting. Ordering must not depend on OS directory-iteration
order, locale, `LC_COLLATE`, or filesystem creation order.

### 4.4 Rejected identity collisions (each aborts)

```text
Unicode-normalization collision : two members whose relative paths differ in bytes
                                  but are equal after NFC (or NFD) normalization
case-fold collision             : two members whose relative paths are equal after
                                  Unicode case-folding but differ in bytes
duplicate byte content          : two members with identical SHA-256
duplicate normalized identity   : two members mapping to the same normalized path id
duplicate conversation identity : two members yielding the same derived
                                  conversation identity
manifest drift                  : enumerated set ≠ approved frozen source manifest
English/Spanish crossover       : a member attributed to the wrong language root
```

The census reports the **existence** of a collision via a content-free category;
it never emits the offending path, name, or digest (§13).

---

## 5. Threat model

The census defends against these failure modes, all upstream of the science:

| Threat | Consequence if undetected | Census defense |
|---|---|---|
| Provider mixing (LDC files under a TalkBank root) | encoding/format drift across the corpus | source-identity match to a single-provider approved manifest |
| Snapshot/version drift (eng and spa from different releases) | asymmetric corpora | per-language pinned snapshot identity (archive + member digests) |
| Silent omission | shrunken, unrepresentative population | manifest-drift check (missing member aborts) |
| Silent addition (stray file) | contamination | `unexpected_entry` + extra-member abort |
| Duplicate exposure | over-weighting some conversations | duplicate byte / conversation / path identity checks |
| Language crossover | wrong-language rows in a condition | per-root language attribution + crossover check |
| Post-hoc exclusion | investigator-degrees-of-freedom bias | frozen manifest; no silent-ignore; no dedup/shrink |
| Ordering nondeterminism | non-reproducible downstream sampling | total bytewise ordering, locale-independent |
| Accidental real traversal | privacy/ethics exposure before approval | authorization capability required *before* root resolution (§14) |
| Privacy leakage in outputs/errors | committing identifying material | fixed content-free error taxonomy + Decision B disclosure matrix |
| Partial/corrupt manifest | inconsistent frozen frame | atomic write + checksum + re-verification |

Out of the census's remit (delegated to later, separately-gated layers):
genuine language identification, monolinguality, code-switch detection, screening,
projection, promotion, splitting, and dataset construction.

---

## 6. Proposed architecture

Three artifacts, smallest coherent surface, mirroring existing repo conventions
(`cslm.utils.paths.project_root`, content-free aggregate dataclasses with
`to_dict()`, ordered tuples for determinism, sanitized fixed-category errors as in
`callhome_chat.StrictChatReaderError`):

```text
src/cslm/data/callhome_population.py
  ├── errors      : CallhomePopulationError + closed category constants
  ├── auth        : CallhomeCensusAuthorization (capability object)
  ├── source id   : CallhomeSourceMember, CallhomeSourceSnapshot,
  │                 CallhomeSourceApproval
  ├── manifest    : CallhomePopulationEntry, CallhomePopulationManifest
  ├── census      : census_callhome_population(...) -> manifest
  ├── verify      : verify_callhome_population_manifest(...) -> None
  ├── serialize   : manifest_to_canonical_json / manifest_from_mapping /
  │                 compute_manifest_checksum
  └── aggregate   : build_population_census_summary(...) (Decision-B-gated)

scripts/census_callhome_population.py
  └── fixed roots, fixed local output, authorization-gated, census-only

tests/test_callhome_population.py
  └── synthetic filesystem fixtures only
```

The module has **no dependency** on `callhome_chat`, `callhome_project`,
`callhome_screening`, or `conditions`. It depends only on the standard library
(`pathlib`, `hashlib`, `os`, `stat`, `json`, `unicodedata`, `dataclasses`) and
`cslm.utils.paths.project_root`. This isolation guarantees the census cannot
accidentally parse transcript content.

---

## 7. Local output ignore rule

The frozen manifest, the local approval/authorization record, and any aggregate
census output are **local-only** and must never be committed. The exact fixed
location is:

```text
data/processed/callhome_population/
```

This is consistent with the existing ignore convention (`data/processed/…` for
derived local artifacts; `docs/callhome_ground_rules.md` explicitly anticipates
`data/processed/callhome_*/`). It is safe because:

- it holds per-file inventories, transcript checksums, and conversation
  identifiers — all **per-row, reconstructive** material that Decision B does not
  cover and this repo's conservative default keeps local;
- it sits under `data/processed/`, an already-untracked derived-artifact area,
  not under any tracked docs or source path;
- a single directory prefix ignore covers the manifest, the local approval
  record, and any aggregate output subfolder.

The later implementation gate adds exactly one `.gitignore` line
(`data/processed/callhome_population/`) and one guardrail test asserting that line
is present (mirroring `tests/test_lexicon_storage_gitignore.py`). **This design
gate does not edit `.gitignore`.**

---

## 8. Public API

Names are proposed as the smallest coherent surface consistent with repo
conventions; the implementation reviewer may rename, but the **contracts** below
are the design.

### 8.1 Errors

```python
class CallhomePopulationError(Exception):
    """Every census/verify failure; message is a fixed content-free category."""
```

One public exception type (as with `StrictChatReaderError`), carrying exactly one
of the closed category constants in §13. No subclass carries protected data. An
authorization failure uses the `authorization_error` category (a distinct
category is acceptable because the *category name* names the failing check, never
the offending path/name/digest).

### 8.2 Authorization capability

```python
@dataclass(frozen=True)
class CallhomeCensusAuthorization:
    """Proof that a human deliberately approved a real local census run.

    Constructed only via `load_census_authorization(path)`, which reads a local
    approval record (never committed) and checks it binds to the approved source
    approval. Its mere existence as a required argument means census functions
    refuse to resolve or traverse the corpus roots without it.
    """
    approved_source_checksum: str      # SHA-256 of the canonical source approval
    contract_version: str
    approved_utc: str

def load_census_authorization(path: str | Path) -> CallhomeCensusAuthorization: ...
```

### 8.3 Source identity

```python
@dataclass(frozen=True)
class CallhomeSourceMember:
    relative_path: str        # POSIX, relative to its language root
    size_bytes: int
    sha256: str

@dataclass(frozen=True)
class CallhomeSourceSnapshot:
    provider: str             # "talkbank_cabank"
    corpus_name: str          # public corpus name (placeholder until G5/G6)
    language: str             # "eng" | "spa"
    official_url: str         # public catalog URL (placeholder until G5/G6)
    public_release_label: str # citation/release label (placeholder until G5/G6)
    archive_filename: str     # local archive name (local only)
    archive_size_bytes: int
    archive_sha256: str
    retrieval_utc: str
    extraction_procedure_id: str
    members: tuple[CallhomeSourceMember, ...]  # frozen expected inventory

@dataclass(frozen=True)
class CallhomeSourceApproval:
    contract_version: str
    provider: str             # single provider for the whole approval
    distribution_format: str  # "chat_utf8"
    english: CallhomeSourceSnapshot
    spanish: CallhomeSourceSnapshot
    approved_by: str
    approved_utc: str
```

A retrieval date alone is **not** identity: a snapshot is identified by
`archive_sha256` plus the per-member `sha256` inventory, so a re-download of a
different release cannot masquerade as the approved snapshot.

### 8.4 Manifest

```python
@dataclass(frozen=True)
class CallhomePopulationEntry:
    ordinal: int
    language: str             # "eng" | "spa" (expected, directory-derived)
    relative_path: str        # POSIX, relative to its language root
    size_bytes: int
    sha256: str
    conversation_id: str      # derived; see §10.4

@dataclass(frozen=True)
class CallhomePopulationManifest:
    schema_version: str
    contract_version: str
    status: str               # "verified"
    provider: str
    distribution_format: str
    repository_commit: str
    created_utc: str
    english_snapshot_id: CallhomeSourceSnapshotId   # identity-only view (§10.2)
    spanish_snapshot_id: CallhomeSourceSnapshotId
    logical_roots: tuple[str, str]                  # ("data/raw/callhome/eng",
                                                    #  "data/raw/callhome/spa")
    entries: tuple[CallhomePopulationEntry, ...]
    counts: CallhomePopulationCounts                # §11.5
    manifest_checksum: str    # SHA-256 over canonical serialization (§11)
```

`CallhomeSourceSnapshotId` is an identity-only projection of a snapshot (provider,
corpus_name, language, public_release_label, archive_sha256, member count) that
carries the archive digest but not the local `archive_filename` — so the manifest
records *which snapshot* without embedding a local filename.

### 8.5 Census and verification

```python
def census_callhome_population(
    authorization: CallhomeCensusAuthorization,
    approval: CallhomeSourceApproval,
    *,
    roots: CallhomeRoots | None = None,   # defaults to the two fixed logical roots
    output_dir: Path | None = None,       # defaults to data/processed/callhome_population/
    write: bool = True,
) -> CallhomePopulationManifest: ...

def verify_callhome_population_manifest(
    manifest: CallhomePopulationManifest,
    authorization: CallhomeCensusAuthorization,
    approval: CallhomeSourceApproval,
    *,
    roots: CallhomeRoots | None = None,
) -> None:   # returns None on success; raises CallhomePopulationError otherwise
    ...
```

Both require an `authorization` and an `approval`; both refuse before touching the
filesystem if authorization is invalid. `verify_...` recomputes the census and
asserts identical membership, ordering, identities, and `manifest_checksum`; it
**never** changes membership (a mismatch aborts with `manifest_mismatch`).

### 8.6 Serialization and aggregate

```python
def manifest_to_canonical_json(manifest: CallhomePopulationManifest) -> str: ...
def compute_manifest_checksum(manifest_without_checksum: Mapping) -> str: ...
def build_population_census_summary(
    manifest: CallhomePopulationManifest,
) -> CallhomePopulationCensusSummary: ...   # Decision-B-gated aggregate (§12)
```

Input contract for every public function: no argument may be a glob, a subset
selector, an exclusion selector, an alternate-provider flag, an arbitrary output
path outside `data/processed/callhome_population/`, or a permissive-mode toggle.
Return contract: `census_callhome_population` returns a fully-verified,
checksummed manifest or raises; it never returns a partial or unverified manifest.

---

## 9. Deterministic enumeration algorithm

`census_callhome_population` runs, in order, with no fallback and no silent skip:

```text
 1. Authorization gate (§14): validate `authorization`; if invalid,
    raise authorization_error BEFORE resolving or traversing any root.
 2. Resolve fixed roots via project_root(); do not accept caller globs/paths
    beyond the fixed logical roots (a non-default `roots` is only for synthetic
    tests and must still be two concrete directories).
 3. Environment checks: for each root and each of its parents up to the repo
    root, assert it exists, is a directory, and is NOT a symlink (os.lstat +
    stat.S_ISDIR/S_ISLNK). Failure -> environment_error / root_error.
 4. For each language in fixed order (eng, then spa):
      a. Non-recursively list direct children (os.scandir, follow_symlinks=False).
      b. For each child, classify via lstat WITHOUT following symlinks:
           - accept iff: regular file AND not a symlink AND name has exact
             lowercase '.cha' suffix AND name does not begin with '.' AND name
             matches none of the temp/metadata patterns AND it is not a directory,
             archive, or special file.
           - anything else -> unexpected_entry (never skipped).
      c. Reject an empty language population -> empty_population.
 5. For each accepted member: read bytes once, compute size_bytes and sha256;
    derive relative_path (POSIX) and conversation_id (§10.4). Reading bytes for
    hashing is not parsing.
 6. Collision detection across all members (§4.4): NFC/NFD normalization
    collisions, case-fold collisions, duplicate sha256, duplicate normalized
    path id, duplicate conversation id -> duplicate_identity.
 7. Language attribution: each member's language is its root; assert no crossover
    (a member can only come from its own root) -> language_crossover.
 8. Source-identity match (§10.3): the enumerated (relative_path, size, sha256)
    set for each language must equal the approved snapshot's frozen member set —
    no missing, extra, modified, or substituted member -> source_identity_mismatch.
 9. Ordering: sort eng then spa, each by bytewise UTF-8 of relative_path; assign
    ordinals; assert the ordering is total and reproducible -> ordering_error.
10. Build manifest; canonical-serialize; compute manifest_checksum (§11).
11. If write: atomically write to data/processed/callhome_population/ (§11.7).
12. Return the verified manifest.
```

Every abort produces **no** partial manifest object and (if writing) leaves **no**
partial file (§11.7).

---

## 10. Source identity and verification

### 10.1 Four separated layers

```text
1. Approved public source declaration  — TRACKED public policy record: provider,
   corpus names, official URLs, citation/release labels. Public facts only.
   Pending G1/G2/G5/G6. (A future tracked doc, e.g.
   docs/callhome_execution_population_source_approval.md — NOT created here.)
2. Local archive identity              — LOCAL approval record: archive filename,
   size, SHA-256, retrieval_utc, extraction_procedure_id. Never committed.
3. Extracted member inventory          — LOCAL: per-member relative_path, size,
   SHA-256 (the frozen expected set). Never committed.
4. Execution manifest                  — LOCAL: the CallhomePopulationManifest.
   Never committed.
```

### 10.2 Representation decision

Source approval is represented as **two coordinated records**:

- a **tracked public policy record** (layer 1) carrying only Decision-B-safe
  public facts and the citation/release labels once G5/G6 are finalized; and
- a **local JSON approval record** (layers 2–3) carrying the archive and member
  identities, stored under `data/processed/callhome_population/` and never
  committed.

Rationale: the public labels are exactly the material Decision B permits to commit
(citations), while archive filenames, per-member paths, and digests are per-row
reconstructive material that must stay local. Splitting them keeps the public
record committable and the identifying inventory local, and lets the authorization
capability (§14) bind to the local record's checksum without ever committing it.

### 10.3 Verification

For each language, the census computes the enumerated member set and compares it
to the approved snapshot's frozen `members`:

```text
missing member     : approved member absent from disk        -> source_identity_mismatch
extra member       : on-disk member not in the approved set   -> source_identity_mismatch
modified member     : same relative_path, different size/sha256 -> source_identity_mismatch
substituted member : different relative_path filling the count -> source_identity_mismatch
```

Comparison is on `(relative_path, size_bytes, sha256)` triples; a matching count
with any triple mismatch still fails. The provider and distribution_format on the
approval must be the single approved values, or `source_identity_mismatch`.

### 10.4 Derived conversation identity

`conversation_id` is derived deterministically from the member's relative path
(its stem), namespaced by language to avoid cross-language collision, e.g.
`f"{language}/{posix_stem}"`. It is **local/reconstructive** (a conversation
identifier), so it lives only in the local manifest and never in committed output.
Two members yielding the same `conversation_id` abort with `duplicate_identity`.

---

## 11. Local manifest schema, serialization, and checksum

### 11.1 Top-level fields

```text
schema_version        : "callhome_population/1"
contract_version      : matches the approval.contract_version
status                : "verified" (a manifest is only ever written after full
                        verification; there is no "partial"/"failed" manifest file)
provider              : single approved provider
distribution_format   : "chat_utf8"
repository_commit      : git HEAD at census time (public fact)
created_utc           : ISO-8601 UTC timestamp
english_snapshot_id   : identity-only snapshot view (archive_sha256 + counts)
spanish_snapshot_id   : identity-only snapshot view
logical_roots         : ["data/raw/callhome/eng", "data/raw/callhome/spa"]
entries               : ordered list of entry objects
counts                : aggregate counts object (§11.5)
manifest_checksum     : SHA-256 over the canonical serialization sans this field
```

### 11.2 Entry object

```text
ordinal          : 0..N-1 in census order
language         : "eng" | "spa"
relative_path    : POSIX, relative to the language root (local only)
size_bytes       : int
sha256           : hex string (local only)
conversation_id  : derived identity (local only)
```

### 11.3 Canonical serialization

```text
- UTF-8 bytes.
- JSON with sort_keys=True, separators=(",", ":"), ensure_ascii=False.
- Exactly one trailing "\n".
- String values are NFC-normalized for serialization stability ONLY in the
  serialized form; the raw on-disk bytes are separately preserved for the
  collision checks (§4.4) so normalization is never used to mask a collision.
- Entry order is the census order (already total); keys within objects are sorted.
```

### 11.4 Checksum procedure

```text
1. Build the manifest mapping WITHOUT the manifest_checksum field.
2. Canonically serialize it (§11.3).
3. manifest_checksum = SHA-256(hex) of those bytes.
4. Insert manifest_checksum and write.
Re-verification recomputes steps 1–3 and asserts equality -> else manifest_mismatch.
```

### 11.5 Counts object (aggregate, local)

```text
n_english_files
n_spanish_files
n_total_files
english_total_bytes
spanish_total_bytes
total_bytes
n_zero_byte_files
all_identity_checks_passed : bool
```

### 11.6 Path normalization / Unicode / case / stable ordering

```text
- relative_path stored as POSIX ("/" separators), relative to the language root.
- Ordering: bytewise UTF-8 of relative_path (locale-independent).
- Unicode: detect NFC/NFD collisions; store NFC in serialization but never fold
  away a real byte-level distinction when detecting duplicates.
- Case: detect case-fold collisions; never case-normalize membership.
- Absolute paths and any personal directory component (home dir, username) MUST
  NEVER be serialized. Only root-relative POSIX paths appear, and only in the
  local manifest.
```

### 11.7 Atomic output and partial-output cleanup

```text
1. Ensure output_dir exists (data/processed/callhome_population/).
2. Write canonical bytes to a uniquely-named temp file in the SAME directory.
3. flush + os.fsync the temp file.
4. os.replace(temp, final)  # atomic rename on the same filesystem.
5. On ANY exception, remove the temp file in a finally block; never leave a
   partial or half-written final manifest. A failed census writes no final file.
```

### 11.8 `.gitignore`

The later gate adds `data/processed/callhome_population/` (one line) plus a
guardrail test. Not edited here.

---

## 12. Decision B disclosure matrix

Statuses: **TRACKED PUBLIC FACT** (already committable), **COMMIT-CANDIDATE AFTER
DECISION B** (aggregate, committable only after an explicit per-output G3 review),
**LOCAL ONLY** (never committed under current policy), **FORBIDDEN** (never
committed, ever), **REQUIRES SEPARATE REVIEW** (needs its own governance
decision).

| Field | Status |
|---|---|
| provider | TRACKED PUBLIC FACT |
| public corpus names | TRACKED PUBLIC FACT |
| public citation labels | TRACKED PUBLIC FACT (once G5/G6 finalized) |
| public release labels | TRACKED PUBLIC FACT (once G5/G6 finalized) |
| schema_version | TRACKED PUBLIC FACT |
| contract_version | TRACKED PUBLIC FACT |
| repository_commit | TRACKED PUBLIC FACT |
| logical roots (eng/spa) | TRACKED PUBLIC FACT |
| file counts by language | COMMIT-CANDIDATE AFTER DECISION B (G3) |
| all identity checks passed (bool) | COMMIT-CANDIDATE AFTER DECISION B (G3) |
| aggregate byte totals | COMMIT-CANDIDATE AFTER DECISION B (G3) |
| failure-reason counts | REQUIRES SEPARATE REVIEW (small cells reconstructive) |
| small-cell counts (< review threshold) | REQUIRES SEPARATE REVIEW |
| archive filename | LOCAL ONLY |
| archive checksum | REQUIRES SEPARATE REVIEW (source-identity fact, not aggregate) |
| archive size | REQUIRES SEPARATE REVIEW |
| retrieval timestamp | LOCAL ONLY |
| relative transcript path | LOCAL ONLY |
| transcript checksum | LOCAL ONLY |
| conversation identifier | LOCAL ONLY |
| population manifest checksum | REQUIRES SEPARATE REVIEW |
| run identifier | LOCAL ONLY |
| absolute path | FORBIDDEN |
| transcript text | FORBIDDEN |
| speaker/participant metadata | FORBIDDEN |
| header/tier values | FORBIDDEN |
| exception traceback | FORBIDDEN (in committed output) |
| raw exception text | FORBIDDEN (in committed output) |

Preserved accepted defaults:

```text
per-file inventories          : LOCAL ONLY
aggregate byte totals         : LOCAL ONLY by default; commit only after G3
failure-reason counts / cells : REQUIRES SEPARATE REVIEW
failed or anomalous census    : NO numeric committed bundle until reviewed
transcript-derived content    : FORBIDDEN
```

This design does **not** assert G3 has approved committing any aggregate. Until G3,
even the `COMMIT-CANDIDATE` rows stay local. A low-cardinality count can itself be
reconstructive, so G3 is a **per-output** safety review, not a category blanket
(consistent with `docs/callhome_ground_rules.md`).

---

## 13. Error and privacy contract

### 13.1 Closed category taxonomy (content-free constants)

```text
environment_error        # repo/root environment wrong (e.g. missing base tree)
root_error               # a root or parent is missing / not a dir / is a symlink
unexpected_entry         # a filesystem entry that is not an accepted .cha member
source_identity_mismatch # enumerated set != approved frozen manifest
manifest_mismatch        # re-verification checksum/membership mismatch
empty_population         # a language population is empty
language_crossover       # a member attributed to the wrong language
duplicate_identity       # byte / path / normalized / conversation duplicate
ordering_error           # ordering not total/reproducible
serialization_error      # canonical serialization failed
output_error             # atomic write failed
authorization_error      # missing/invalid census authorization
privacy_error            # an internal check would have emitted protected data
```

Each is a fixed string; `CallhomePopulationError(category)` carries only the
category. These categories name the **failing check**, never the offending item,
so they may be distinguished publicly. Categories that could otherwise hint at a
specific file (e.g. duplicate/collision) still never embed the path, name, or
digest — only the fact that the class of collision exists.

### 13.2 Forbidden on every failure surface

```text
no absolute path, filename, or relative path
no hash / digest
no source member name
no corpus text, header, tier, speaker, or participant value
no traceback in any committed output
no nested __cause__/__context__ carrying protected data
no stdout/stderr leakage of protected data
```

### 13.3 Chain-free, control-flow-safe (reuse the strict reader's proven pattern)

```text
- catch Exception, NEVER BaseException.
- KeyboardInterrupt and SystemExit propagate as the exact same object (identity).
- Convert underlying exceptions with the raise-after-exit pattern: catch inside an
  inner helper, record only a content-free category, exit the except block, THEN
  raise CallhomePopulationError outside any active handler, so
  __cause__ is None and __context__ is None.
- Filesystem failures (FileNotFoundError, PermissionError, generic OSError) become
  fixed-category errors (root_error / environment_error / output_error) exposing
  no path or original error text.
```

This does not weaken the strict reader's existing contract; it re-applies it.

---

## 14. Authorization control

### 14.1 Mechanism

A **capability object** `CallhomeCensusAuthorization` plus a **fixed local
approval-record path** plus a **narrowly named CLI flag**:

```text
- Real census requires a CallhomeCensusAuthorization argument. Its ONLY constructor
  is load_census_authorization(path), which:
    1. reads a local JSON approval record from the fixed local path
       (data/processed/callhome_population/authorization.json — never committed);
    2. checks required fields (approved_source_checksum, contract_version,
       approved_utc) and that approved_source_checksum equals the SHA-256 of the
       canonical CallhomeSourceApproval it will be used with;
    3. returns a frozen capability on success, else raises authorization_error.
- census_callhome_population validates the authorization/approval binding BEFORE
  resolving or traversing roots. No authorization -> authorization_error, and the
  corpus roots are never touched.
- The script additionally requires an explicit, unmistakable flag, e.g.
  --i-have-approved-local-callhome-census, AND the local approval record present
  AND matching. Absent either, the script prints a governance message and exits
  without traversing anything.
```

### 14.2 What it proves / does not prove

```text
Proves      : a human deliberately created a local approval artifact naming the
              exact approved source approval (by its canonical checksum) and ran
              the runner with an explicit, self-describing flag.
Does NOT     : prove the archives are the genuine official TalkBank snapshots
prove         (that is governance G1/G2), nor that any transcript is monolingual
              (later validation), nor grant Decision B commit permission (G3).
```

### 14.3 Why it is not security theater; why tests still work

```text
- Two independent deliberate artifacts are required (local record + explicit
  flag), both absent by default; an ordinary typo cannot synthesize either, so
  accidental real traversal is impossible.
- The binding is a checksum match, not a mere boolean, so a stale/mismatched
  record fails closed.
- Tests exercise the logic synthetically: a test builds a synthetic approval, a
  matching synthetic authorization record in a tmp dir, and synthetic roots, then
  runs the census against the tmp tree — proving both the allow-path and the
  refuse-before-traversal path without any real corpus.
```

No authorization is granted by this design gate.

---

## 15. Synthetic test matrix

All fixtures are invented (synthetic `.cha` byte blobs, `AAA`/`BBB`-style names,
`syn_*` tokens, unique sentinels). No real corpus filename, hash, archive name,
conversation id, or text is used. Each test builds a temporary directory tree and,
where needed, a synthetic approval + authorization record.

```text
Happy path
  - correct synthetic census over eng+spa -> verified manifest, correct counts,
    total bytewise ordering, ordinals 0..N-1, all_identity_checks_passed True.

Root / environment
  - missing eng root / missing spa root                -> root_error
  - extra unexpected root entry                        -> unexpected_entry
  - symlink root / symlinked parent                    -> root_error
  - empty English population / empty Spanish population -> empty_population

Filesystem-entry rejection (each -> unexpected_entry)
  - nested directory inside a root
  - hidden file (.name)
  - macOS metadata (.DS_Store, ._name)
  - temp file (name~, name.tmp, name.part)
  - uppercase/mixed suffix (.CHA, .Cha)
  - archive inside root (.zip/.tgz/.tar/.gz)
  - broken symlink
  - special file (FIFO/socket) where creatable; else documented skip

Determinism
  - stable ordering regardless of creation order (create files in shuffled order)
  - locale independence (run under different LC_COLLATE, same order)
  - identical manifest_checksum across repeated runs on the same tree

Identity collisions (each -> duplicate_identity)
  - Unicode NFC/NFD path collision
  - case-fold path collision
  - duplicate byte content (identical sha256)
  - duplicate derived conversation id

Source-identity (each -> source_identity_mismatch)
  - wrong provider / wrong distribution_format
  - wrong language attribution vs approval
  - wrong snapshot (member set differs)
  - wrong archive size / wrong archive digest in approval binding
  - missing transcript / extra transcript / modified transcript / substituted
    transcript

Boundary
  - zero-byte authorized .cha remains a member (present in manifest, counted in
    n_zero_byte_files), not dropped

Manifest
  - canonical serialization is stable and key-sorted
  - manifest_checksum recomputation matches
  - verify_callhome_population_manifest re-verifies an unchanged tree (pass) and
    fails closed (manifest_mismatch) on any drift

Authorization
  - refusal BEFORE traversal when authorization missing/invalid (assert the roots
    were never scanned, e.g. via a sentinel/guard) -> authorization_error
  - allow-path with a matching synthetic authorization record

Output
  - atomic output writes the final file
  - a forced failure during write leaves NO partial final file (temp cleaned up)

Privacy / control-flow
  - injected sentinels (path, filename, digest, member name) absent from
    str/repr/args/__cause__/__context__/stdout/stderr of any raised error
  - every ordinary error has __cause__ is None and __context__ is None
  - injected KeyboardInterrupt() propagates as the exact object
  - injected SystemExit() propagates as the exact object
```

---

## 16. Routing protections

The census records `language` (directory-derived, marked **expected, not
verified**) and source identity. It **does not** compute condition eligibility.
Directory name is *evidence of expectation only*; the actual language is verified
later. The permanent routing:

```text
CALLHOME English → EnglishMono and MonoCont only
CALLHOME Spanish → SpanishMono and MonoCont only
CALLHOME         → never CsCont
Bangor           → CsCont only
```

is independently enforced downstream at each of these points, none of which is
this census module:

```text
source manifest            : records provenance (callhome_eng / callhome_spa) and
                             single-provider identity; no CsCont routing exists here.
strict execution manifest  : consumes the frozen population; still no condition logic.
linguistic validation      : verifies actual monolinguality in the expected
                             language before any row is 'clean' (source-validation
                             method policy); directory label alone never validates.
projection                 : stamps source=callhome_eng/spa and provenance; CsCont
                             is unreachable for CALLHOME rows.
promotion                  : 'clean' only after validation + explicit approval;
                             CALLHOME 'clean' rows route ONLY to EnglishMono/MonoCont
                             (eng) or SpanishMono/MonoCont (spa).
condition manifest         : final-source rule keeps CALLHOME out of CsCont and
                             Bangor out of the monolingual conditions.
final construction         : builds datasets under the sourcing invariants.
```

Because the census never emits `condition_candidates`, it cannot accidentally
route CALLHOME into `CsCont`. Language is carried as expected-only metadata so a
later verified-language signal — not a directory name — governs admission.

---

## 17. Duplicate and collision handling (consolidated)

The census applies a single, explicit collision policy (detected at §9 step 6 over
the fully-enumerated member set, using the criteria in §4.4). It **never**
deduplicates, shrinks, or silently merges; every collision is an abort:

| Collision | Definition | Category |
|---|---|---|
| duplicate byte content | two members share a SHA-256 | `duplicate_identity` |
| duplicate normalized path id | two members map to one normalized path identity | `duplicate_identity` |
| duplicate conversation identity | two members yield the same derived `conversation_id` | `duplicate_identity` |
| Unicode-normalization collision | paths differ in bytes but are equal after NFC (or NFD) | `duplicate_identity` |
| case-fold collision | paths equal after Unicode case-folding but differ in bytes | `duplicate_identity` |

Rationale for fail-closed rather than auto-dedup: two members that collide are an
upstream packaging or extraction fault. Silently keeping one and dropping the
other would introduce exactly the kind of non-reproducible, investigator-chosen
population reduction the census exists to prevent (§5). Detection uses raw on-disk
bytes so that NFC serialization (§11.3) can never mask a real byte-level
distinction, and case/normalization folding is used **only** to *detect* a
collision, never to *rewrite* membership. The abort names only the collision class
(§13), never the offending paths or digests.

---

## 18. Deferred strict-execution layer (design deferred to its own gate)

A later, separately-designed and separately-reviewed module will execute the
strict reader over the frozen population. Its contract (sketch only; not designed
in full here):

```text
- re-verify the frozen manifest first (membership + checksum) before any read;
- process each entry exactly once, in manifest order;
- call read_chat_transcript(...) — the strict reader — for each entry;
- NEVER call the permissive parse_chat_file / parse_chat_lines;
- collect only local, content-free status categories per entry (accepted /
  rejected-by-category), never transcript-derived detail;
- block population acceptance if ANY file rejects (no silently reduced population);
- abort immediately on an unknown exception or on manifest drift detected mid-run;
- preserve the reader's existing limitation that ordinary read failures and
  warning-bearing dispatch failures may SHARE the same privacy-safe public error
  category — do NOT inspect nested exceptions to recover private detail.
```

This design does not implement, schedule, or authorize that layer. It is listed so
the census manifest schema (ordered, checksummed, re-verifiable) is sufficient to
support it later without redesign.

---

## 19. Governance decision register

| ID | Decision | Current status | Why it matters | Evidence required | Blocks which gate | Blocks synthetic impl? |
|---|---|---|---|---|---|---|
| G1 | Exact English TalkBank archive snapshot approval | OPEN | pins the English population identity (archive + members) | approved archive filename/size/SHA-256 + member inventory in the local record | real census (gate 8) | No |
| G2 | Exact Spanish TalkBank archive snapshot approval | OPEN | pins the Spanish population identity | same as G1 for Spanish | real census (gate 8) | No |
| G3 | Decision B approval of census aggregate schema | OPEN | licenses committing any aggregate census field | per-output safety review of the §12 COMMIT-CANDIDATE fields | committed census results (gate 9) | No |
| G4 | Decision B approval of later strict-result schema | OPEN | licenses committing strict-execution aggregates | per-output safety review of the strict-result fields | committed strict results (gate 11) | No |
| G5 | Approved English public citation/release label | OPEN (TODO in ground rules) | required public attribution string | confirmed corpus manual / LDC citation | committed public source record | No |
| G6 | Approved Spanish public citation/release label | OPEN (TODO in ground rules) | required public attribution string + DOI | confirmed corpus manual / LDC citation + DOI | committed public source record | No |

**Conclusion:** G1–G6 do **not** block this design or a synthetic-only
implementation. They **do** block all real census, real hashing, real validation
execution, and any committed CALLHOME-derived result. This design does not resolve
any of them and does not access the corpus to resolve them.

---

## 20. Future bounded gates

```text
 1. Docs-only implementation design            — THIS gate
 2. Independent Codex design review
 3. Separate design merge
 4. Synthetic-only census implementation
 5. Independent implementation review
 6. Separate implementation merge
 7. Exact source-snapshot + disclosure approval (G1–G6)
 8. Metadata-only real census authorization
 9. Independent census-result review
10. Strict-reader execution authorization
11. Strict-result review
12. Linguistic-validation design
13. Linguistic-validation execution
14. Explicit promotion
15. Preliminary EnglishMono / SpanishMono / MonoCont construction
```

Source approval, census, strict parsing, linguistic screening, promotion, and
dataset construction stay separate gates and are never collapsed.

---

## 21. Definition of done (for this design)

An independent reviewer can determine from this document alone:

```text
exact population membership          — §4.1 (direct lowercase .cha, in approved manifest)
exact ordering                       — §4.3 (eng before spa; bytewise POSIX path)
exact root policy                    — §4.2 (real non-symlink dirs; non-recursive; no silent ignore)
exact source authority               — §3 (TalkBank CABank single provider; two pinned snapshots)
exact identity fields                — §8.3/§8.4/§11.2 (path, size, sha256, conversation id)
exact duplicate policy               — §4.4 (byte / path / normalized / conversation / case / NFC)
exact serialization                  — §11.3 (sorted-key compact UTF-8 JSON, one newline)
exact checksum method                — §11.4 (SHA-256 over canonical mapping sans checksum)
exact authorization boundary         — §14 (capability + local record + explicit flag, pre-traversal)
exact error categories               — §13.1 (closed content-free taxonomy)
exact disclosure status per field    — §12 (Decision B matrix)
exact synthetic tests                — §15
exact implementation file scope      — §1.3 (three files + one .gitignore line)
exact later gate boundaries          — §18, §19, §20
```

No real-data value appears anywhere in this document.

---

## 22. Explicit non-goals

```text
- No transcript parsing, tokenization, language labeling, or screening.
- No condition eligibility, projection, promotion, or dataset construction.
- No train/dev/test splitting or corpus freeze (beyond freezing the file set).
- No tokenizer or model work.
- No language identification or monolinguality judgment.
- No real corpus access, archive download, hashing of real files, or private-
  directory inspection in this or the implementation gate's synthetic tests.
- No committing of per-file inventories, transcript checksums, conversation ids,
  archive filenames, or any transcript-derived content.
- No Decision B expansion; no governance decision resolved here.
- No generalized filesystem framework, glob interface, subset/exclusion selector,
  alternate-provider flag, permissive mode, or arbitrary output path.
```
