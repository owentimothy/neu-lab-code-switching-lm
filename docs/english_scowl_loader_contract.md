# English SCOWL Loader Contract

## 1. Status

```text
Controlled, unwired approved-English-SCOWL loading:  IMPLEMENTED / OPEN

CALLHOME loader wiring:                              CLOSED
CALLHOME validation:                                 CLOSED
CALLHOME row promotion:                              CLOSED
Clean-row assignment:                                CLOSED
Condition dataset construction:                      CLOSED
Spanish lexicon selection:                           CLOSED
Spanish locale selection:                            CLOSED
Tokenizer training:                                  CLOSED
Model training:                                      CLOSED
Experimental probes:                                 CLOSED

Git tracking of the artifact, notice, provenance, or hashes:  CLOSED
```

This record is the contract for `src/cslm/data/english_scowl_resource.py`. It
implements **one** capability: loading the already-approved local English SCOWL
resource bundle and returning its raw entries. It opens nothing else.

The artifact this module loads was approved by
`docs/callhome_english_scowl_artifact_approval.md`, which records
`English lexicon validation: YES` as an approved **future** use. This module is
the resource-access half of that future use. The validation half — and every
step after it — remains closed.

## 2. What is implemented and open

**Controlled, unwired approved-English-SCOWL loading.**

```python
from cslm.data.english_scowl_resource import load_approved_english_scowl

scowl = load_approved_english_scowl()   # no arguments
scowl.resource_id   # "english_scowl_esdb_en_us"  (fixed by the module)
scowl.entry_count   # aggregate count (derived)
scowl.entries       # frozenset[str] of RAW entries
```

`ApprovedEnglishScowl` instances are produced **only** by
`load_approved_english_scowl()`. Direct construction raises `TypeError`: the type
asserts that its entries *are* the approved artifact's, and that assertion must
not be forgeable by ordinary construction. Stored entries are enforced at runtime
to be exactly a `frozenset`. The guard is a module-private construction token; it
prevents **ordinary or accidental** construction and is **not a Python security
boundary** — the token name is importable, and `copy`/`pickle` reconstruct
objects without calling `__init__`.

"Unwired" is load-bearing: **no script, pipeline, or existing module imports
this one.** Loading the resource changes no CALLHOME row's state. The CALLHOME
pipeline remains exactly as recorded in
`docs/callhome_english_scowl_canonical_artifact_build_record.md` §13:

```text
Total rows:                  88404
Validated:                   0
Not validated:               88404
Lexicon exact match:         0
Clean:                       0
EnglishMono candidates:      0
SpanishMono candidates:      0
MonoCont candidates:         0
Blocked from all conditions: 88404
```

## 3. What remains closed

| Gate | Status | Why it is not this module's business |
|---|---|---|
| CALLHOME loader wiring | **CLOSED** | This module is imported by nothing; wiring is a separate, reviewed step |
| CALLHOME validation | **CLOSED** | Validation is `cslm.data.callhome_lexicon_validation`, untouched here |
| CALLHOME row promotion | **CLOSED** | Every row stays `not_validated` |
| Clean-row assignment | **CLOSED** | `clean` stays 0 |
| Condition dataset construction | **CLOSED** | `docs/condition_dataset_policy.md`; artifact approval §4 |
| Spanish lexicon selection | **CLOSED** | Separate Spanish pipeline; this module is English-only |
| Spanish locale selection | **CLOSED** | Regional variant still unresolved |
| Tokenizer training | **CLOSED** | Artifact approval §4 |
| Model training | **CLOSED** | Artifact approval §4; `CLAUDE.md` |
| Experimental probes | **CLOSED** | No probe logic exists or is enabled |
| Git tracking of bundle contents | **CLOSED** | Bundle stays local and Git-ignored |

This loader constructs or emits no `CsCont`. A future positive validation may
permit clean English rows to serve `EnglishMono`, `MonoCont-English`, and future
`CsCont-English-Monolingual-Filler` selected only from `MonoCont-English` — and
that routing remains closed here. CALLHOME never receives generic `CsCont`
candidacy or qualifies as genuine code-switched, mixed-language, or
switching-quota evidence; Bangor Miami remains the primary current source of
genuine code-switched evidence.

## 4. Approved bundle contract

The module reads exactly one fixed location, resolved from the project root
(never a hard-coded absolute path):

```text
data/resources/local_lexicons/english/english_scowl_esdb_en_us/
  scowl_en_US_size60_var1.txt
  SCOWL-COPYRIGHT.txt
  provenance.json
```

The bundle must contain **exactly** these three **regular, non-symlink** files —
no extras, no subdirectories, no dotfiles, no symlinks (including the bundle
directory itself). The path remains **local and Git-ignored**; the module never
creates it.

## 5. Validation order

1. **Location** — the project root is resolved. A known resolution failure
   (`OSError` or `RuntimeError`) becomes `EnglishScowlBundleMissingError`; the
   shared resolver reports the absolute filesystem path it started from, and that
   path must never escape this module.
2. **Layout** — bundle directory is a real (non-symlink) directory containing
   exactly the three approved regular files.
3. **Provenance identity** — parse `provenance.json` (UTF-8, JSON object) and
   check the approved identity subset:

   | Field | Approved value |
   |---|---|
   | `schema_version` | `1` (`type(...) is int`, so JSON booleans are rejected) |
   | `resource_id` | `english_scowl_esdb_en_us` |
   | `artifact_filename` | `scowl_en_US_size60_var1.txt` |
   | `preserved_notice_filename` | `SCOWL-COPYRIGHT.txt` |
   | `artifact_SHA256` | present, lowercase 64-hex |

   Unknown provenance keys are **ignored** (forward compatibility).
4. **Artifact format** — strict checks (§6).
5. **Integrity** — the artifact's computed SHA-256 must equal the recorded
   `artifact_SHA256`. **Mandatory; there is no skip option, public or private.**

Structure is checked *before* the hash so that realistic accidental corruption
(a CRLF rewrite, a truncated copy) yields a precise, privacy-safe error instead
of an opaque integrity failure.

## 6. Strict artifact format

Enforced: non-empty; strict UTF-8; LF line endings only; final LF required; no CR
bytes; no NUL bytes; no empty entries; no duplicate entries; no leading or
trailing whitespace; no ASCII space or tab anywhere in an entry; entries in
**strict bytewise sorted order**.

Splitting is on `\n` only — never `str.splitlines()`, which also splits on other
Unicode line boundaries and could silently divide one entry into two. Bytewise
comparison matches the sort the artifact was generated with, because UTF-8 byte
order equals code-point order.

**No digit or hyphen eligibility rules are applied.** Those encode *extraction
policy* (word-filter configuration), not the *format* of a plain sorted wordlist.
The mandatory artifact hash is the extraction-policy integrity gate: if the bytes
match the approved record, the extraction policy matched by construction. Adding
such rules would also make a future approved re-extraction crash the loader.

## 7. Normalization boundary

The loader returns entries **verbatim**. It performs **no** Unicode
normalization, **no** case conversion, **no** token normalization, **no**
vocabulary expansion, and **no** fallback substitution.

`docs/callhome_lexicon_normalization_policy.md` requires that utterance tokens
and lexicon entries be normalized **identically, by the same rule**. Normalizing
at load time would break that invariant. The module imports no `unicodedata`,
which makes this structural rather than merely intended.

Policy A's residual proper-name question
(`docs/callhome_english_scowl_proper_name_policy.md`) is likewise **not** filtered
here; it belongs to validation and diagnostics, which are closed.

## 8. Integrity claim — scope and limits

The mandatory hash comparison detects **accidental corruption or substitution**
of the local bundle. It is **not** a malicious-tampering trust anchor: the
expected digest lives inside the same local, mutable bundle it describes, and the
full digest is deliberately absent from this repository
(`docs/callhome_english_scowl_canonical_artifact_build_record.md` §7, §12).

Accordingly the module uses a plain `==` comparison rather than a constant-time
comparison, which would imply a security posture this module does not claim.

The construction token (§2) is subject to the same honest limit: it defends
against ordinary and accidental construction, not against a determined caller.

## 9. Privacy contract

Exception messages are constructed **only** from module constants and aggregate
integers. No message contains:

- a filesystem path (absolute or relative);
- a lexical entry;
- a hash (recorded or computed);
- a provenance value;
- notice contents;
- an unexpected local filename;
- a line number.

Required filenames **may** appear (they are public approved constants); unexpected
filenames are reported as an aggregate count only.

The following **known** failures are wrapped in typed errors and chain-suppressed
with `from None`, so no underlying message or chained traceback can expose a
personal path or protected local information:

| Underlying failure | Wrapped as |
|---|---|
| `project_root()` raising `OSError` or `RuntimeError` | `EnglishScowlBundleMissingError` |
| Directory listing / file read `OSError` | `EnglishScowlBundleLayoutError` / `…ProvenanceError` / `…ArtifactError` |
| `UnicodeDecodeError` (provenance or artifact) | `…ProvenanceError` / `…ArtifactError` |
| `json.JSONDecodeError` | `EnglishScowlProvenanceError` |
| `RecursionError` from `json.loads` (excessive nesting) | `EnglishScowlProvenanceError` |

**Scope limit, stated plainly:** this list is exhaustive of what the module
converts. The module does **not** claim that arbitrary programming defects, or
every possible Python exception, become resource exceptions. The project-root
catch is deliberately narrowed to `(OSError, RuntimeError)` — the failure modes
the shared resolver actually signals — so an unrelated defect is never
mislabelled as a missing resource. Unrelated exceptions propagate unchanged.

The returned `ApprovedEnglishScowl` stores **no path**, keeps `entries` out of
`repr`, and represents itself as only the fixed resource identity plus the
aggregate entry count.

The notice file's **contents are never read or hashed** — only its presence and
file type are checked.

## 10. Typed exceptions

```text
EnglishScowlResourceError            (base; RuntimeError)
├── EnglishScowlBundleMissingError   project root unresolvable, or bundle absent /
│                                    not a directory / symlink
├── EnglishScowlBundleLayoutError    not exactly the three approved regular files
├── EnglishScowlProvenanceError      provenance unreadable, unparseable (including
│                                    excessive nesting), or identity mismatch
├── EnglishScowlArtifactError        artifact unreadable or format violation
└── EnglishScowlIntegrityError       artifact bytes ≠ recorded SHA-256
```

**Fail-closed for expected resource and parsing failures.** Every failure listed
in §9 raises a typed error. The loader never returns a partial or empty lexicon,
never creates the bundle, never writes, never downloads, and never falls back to
another path or resource.

Constructing `ApprovedEnglishScowl` outside the loader raises `TypeError` — an
API misuse, deliberately kept outside the `EnglishScowlResourceError` tree so
that a construction bug is never swallowed by a resource-failure handler.

## 11. Caching

**Results are not cached.** Every call re-reads and re-verifies the bundle,
because caching would silently skip the mandatory integrity check. Callers should
call once and reuse the returned immutable object rather than calling per row.

## 12. Testing

`tests/test_english_scowl_resource.py` uses **synthetic temporary bundles only**
(fake `syn_*` entries under `tmp_path`). No test reads, requires, or touches the
real ignored approved bundle, and no real lexical resource or CALLHOME data is
involved. Tests replace the private resolver `_approved_bundle_dir` so the real
public entry point is exercised end to end; there is no public way to pass a path.

Path-like sentinels in tests (`/synthetic/private/project`) are deliberately
artificial stand-ins for a personal absolute path, so no real or personal-looking
user path enters a tracked file.

Coverage: the successful contract (identity, immutability, derived count, safe
`repr`, raw entries, unknown-key tolerance, no caching, no writes); reserved
construction (direct construction, no-argument construction, a foreign token,
caller-supplied `resource_id`, wrong entry-container types, a `frozenset`
subclass, and omission of forged entry text from the error); and each fail-closed
boundary (project-root resolution, layout, provenance, strict format, integrity),
plus explicit assertions that exception text omits paths, entries, hashes,
provenance values, and unexpected filenames.

Root-resolution and `RecursionError` cases are exercised by monkeypatching, never
by sabotaging the real resolver or by relying on this machine's recursion limit.

## 13. Repository boundary

Unchanged by this branch: the CALLHOME validator, the generic lexicon loader,
package exports (`__init__.py` files remain export-free, matching the existing
convention), routing code, scripts, `.gitignore`, and all existing tests. The
module is additive and imported by nothing.

The generated wordlist, preserved notice, provenance JSON, and full hashes remain
**local and Git-ignored**. This repository continues to contain only documentation
records and content-free code.

## 14. Out of scope

The pre-existing CALLHOME identifier/provenance privacy question is **outside**
this branch. This module neither uses nor modifies CALLHOME serialization, and
nothing here resolves, mitigates, or depends on that question.

The `provenance.json` described above is the **SCOWL artifact's** provenance
(upstream identity, container identity, build hashes). It is unrelated to CALLHOME
provenance and contains no CALLHOME material.

## 15. Next gate

Wiring this loader into CALLHOME validation is a **separate, closed** gate
requiring its own review. Until that gate opens, every CALLHOME row remains
`not_validated`, `clean` remains 0, and no condition, tokenizer, or model work is
authorized.
