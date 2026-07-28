# CALLHOME English SCOWL Canonical Build Environment

## Status / Decision
```text
Canonical English SCOWL build environment:
YES / SELECTED FOR CONTINUED GOVERNANCE

Canonical mechanism:
IMMUTABLE, PLATFORM-SPECIFIC CONTAINER-IMAGE DIGEST

Canonical platform:
linux/arm64/v8

Canonical image repository:
docker.io/library/python

Human-readable tag (provenance only, mutable):
3.12.13-bookworm

Multi-platform index digest (provenance only, not the canonical identity):
sha256:4f1cc04d959e1360fb4e6957e23e5cd96d32a239d996af6d5c7ad29ee55175d0

Selected platform-specific immutable digest (canonical identity):
sha256:77747425b0797fccc62b5ced9a4ca7854c7247485c89681c57e48767ed3343d6

Canonical immutable reference:
docker.io/library/python@sha256:77747425b0797fccc62b5ced9a4ca7854c7247485c89681c57e48767ed3343d6

Operational artifact generation:
NO / NOT APPROVED
```

This is a **repository governance record, not legal advice.** This branch selects the
**canonical build environment** (a single, platform-specific, digest-pinned container
image) for a future SCOWL wordlist build, and records the software identities observed
inside that image. It does **not** approve or perform any operational step: no SCOWL
source checkout, no notice retrieval, no `make` execution, no `scowl.db` generation, no
wordlist extraction, no resource-directory creation, no generated-wordlist
output-filename approval, no local placement, no SCOWL artifact, generated-wordlist,
preserved-notice, or build-output SHA-256 computation, no two-clean-build test, no
loader execution, no CALLHOME validation.

- **No CALLHOME transcript content or CALLHOME-derived evidence was inspected or used**
  to make this selection. No CALLHOME content was accessed during Docker inspection.
- **No SCOWL/ESDB source or artifact was downloaded, checked out, saved, built, or
  generated; no `scowl.db` or wordlist was produced; no SCOWL artifact,
  generated-wordlist, preserved-notice, or build-output SHA-256 was computed.**
- **Docker image inspection has now occurred** (candidate base images were pulled and
  examined in temporary `--rm` inspection containers), but **SCOWL operationalization
  has not.** No local repository directory was mounted during inspection.
- **The real pipeline remains unchanged** (`default_source_validation` only;
  validator/loader not wired into `scripts/summarize_callhome_projection_local.py`).
  Every real CALLHOME row stays `not_validated`; `clean` stays zero.
- **All operational approvals remain `NO / NOT APPROVED`.**

### Evidence labels used in this record
```text
VERIFIED LOCAL OBSERVATION      observed directly on the Apple Silicon host
VERIFIED IMAGE OBSERVATION      observed inside a temporary inspection container
PROJECT POLICY DECISION         a governance choice recorded for continued governance
FUTURE VERIFICATION REQUIREMENT something that must still be demonstrated later
NOT YET APPROVED / NOT EXECUTED an operational step that is neither approved nor run
```
A label describing an **observation** is never, in this record, promoted into a legal,
operational, or scientific **conclusion**.

## Existing Decision State
These decisions are already closed by earlier merged records and are **not reopened**
here. They are restated only as the context this environment serves.

```text
Selected English resource:            Direct SCOWL / ESDB Model 1
Resource ID:                          english_scowl_esdb_en_us
Artifact model:                       source-generated plain wordlist
Selected source tag:                  rel-2026.02.25
Selected immutable commit:            7e99edab8e32f9f9ea2b15f249ca8d4d67237410
Dialect / size / variant:             A (American) / 60 / 1
Category / POS policy:                --categories= ; --wo-poses=abbr ;
                                      --wo-pos-categories=nonword,wordpart
Output policy:                        UTF-8, LF, diacritics preserved,
                                      internal apostrophes permitted,
                                      open compounds / hyphens / digits /
                                      special symbols / abbreviations /
                                      nonwords / word parts excluded
Proper-name policy:                   RESOLVED (Policy A)
Reproducibility contract:             RESOLVED (immutable container digest required;
                                      two-clean-build byte-identity test required)
Notice bundle:                        RESOLVED by merged PR #67
Prior LibreOffice en_US candidate:    SUPERSEDED FOR CONTINUED GOVERNANCE;
                                      documented fallback only
```

Governing prior records (not edited in this branch):
`docs/callhome_english_scowl_build_environment_evidence.md`,
`docs/callhome_english_lexicon_resource_selection_reassessment.md`,
`docs/callhome_english_scowl_notice_bundle_decision.md`,
`docs/callhome_english_scowl_candidate_evidence.md`,
`docs/callhome_english_scowl_proper_name_policy.md`.

The prior build-environment record left the canonical container and its
platform-specific digest **UNRESOLVED** and named "select and record a canonical
platform and platform-specific immutable container-image digest" as the next step. This
record resolves that one line **prospectively**; it edits none of the earlier files.

## Canonical Environment Selection
```text
Label: PROJECT POLICY DECISION
```

The canonical build environment for the future SCOWL Model 1 wordlist is the single,
platform-specific container image below.

```text
Canonical platform:                  linux/arm64/v8
Canonical image repository:          docker.io/library/python
Human-readable tag:                  3.12.13-bookworm
Multi-platform index digest:         sha256:4f1cc04d959e1360fb4e6957e23e5cd96d32a239d996af6d5c7ad29ee55175d0
Selected platform-specific digest:   sha256:77747425b0797fccc62b5ced9a4ca7854c7247485c89681c57e48767ed3343d6
Canonical immutable reference:       docker.io/library/python@sha256:77747425b0797fccc62b5ced9a4ca7854c7247485c89681c57e48767ed3343d6
```

Identity semantics (why three identifiers are recorded but only one is canonical):

- The **human-readable tag** (`3.12.13-bookworm`) is recorded for provenance and human
  legibility only. Tags are **mutable** and can be retargeted upstream; a tag is **not**
  the canonical identity.
- The **multi-platform index digest**
  (`sha256:4f1cc04d…`) identifies the multi-architecture manifest list, which resolves
  to different per-platform images depending on the host. It is recorded for provenance
  and traceability but is **not** the canonical identity, because it does not by itself
  fix which single platform image executes.
- The **platform-specific digest**
  (`sha256:77747425…`), for `linux/arm64/v8`, is the **canonical identity**: it
  immutably identifies the exact image whose software stack was observed below and in
  which a future build would run.

No image is built, tagged, published, or modified by this record. The candidate images
were pulled for read-only inspection only.

## Evidence Gathered

### Local host and Docker runtime
```text
Label: VERIFIED LOCAL OBSERVATION
```
Docker Desktop for Apple Silicon was installed manually by the user (not by this
workflow). Read-only local observations (no usernames, hostnames, secrets, or
repository paths recorded):

```text
Docker CLI path:            /usr/local/bin/docker
Docker client version:      29.6.1 (arm64)
Docker engine version:      29.6.1 (Linux, arm64)
Docker engine architecture: aarch64
BuildKit version:           v0.31.1
Mac host architecture:      arm64
Docker platform support:    linux/arm64 natively; linux/amd64 through emulation
```
No repository directory was mounted during Docker inspection. No CALLHOME content was
accessed. No SCOWL source was downloaded, and no build was performed.

### Selected canonical arm64 image (observed inside a temporary inspection container)
```text
Label: VERIFIED IMAGE OBSERVATION
Image: docker.io/library/python@sha256:77747425b0797fccc62b5ced9a4ca7854c7247485c89681c57e48767ed3343d6
Platform: linux/arm64/v8
```
```text
architecture:                aarch64
operating system:            Debian GNU/Linux 12 (bookworm)
Python implementation:       CPython
Python version:              3.12.13
SQLite runtime (via Python): 3.40.1
GNU Make:                    4.3
locale:                      C.UTF-8
output encoding policy:      UTF-8 (carried forward)
line-ending policy:          LF (carried forward)
```
These identities were read from a temporary container started with `docker run --rm`.
No repository directory was mounted; no SCOWL source, build, or wordlist was involved.

### Comparison amd64 image (observed inside a temporary inspection container)
```text
Label: VERIFIED IMAGE OBSERVATION
Image: docker.io/library/python@sha256:058149828b8d4a90425f5ae6d255ee1fcfe73bf7d749635d824f4e033460d83c
Platform: linux/amd64
```
```text
architecture:                x86_64
operating system:            Debian GNU/Linux 12 (bookworm)
Python implementation:       CPython 3.12.13
SQLite runtime (via Python): 3.40.1
GNU Make:                    4.3
locale:                      C.UTF-8
```
The relevant observed software versions (Python, SQLite, GNU Make, Debian, locale)
**match** across the arm64 and amd64 images. This is a version-identity observation
only. It is **not** a claim that the two architectures would produce byte-identical
SCOWL output; cross-platform byte identity has **not** been tested.

### Minimums satisfied
```text
Label: VERIFIED IMAGE OBSERVATION vs. repository-recorded upstream minimums
```
The prior build-environment record documents upstream minimums of Python 3.7 and SQLite
3.33.0. The selected arm64 image's Python 3.12.13 and SQLite 3.40.1 both exceed those
minimums, and GNU Make 4.3 is present for the `make` build step. Meeting the documented
minimums does **not** by itself demonstrate reproducible output.

## Architecture Decision
```text
Label: PROJECT POLICY DECISION

Canonical platform:            linux/arm64/v8
Comparison/corroboration only: linux/amd64 (optional, future)
```

`linux/arm64/v8` is selected as the canonical platform because:

- it runs **natively** on the current Apple Silicon host, with no x86 emulation layer;
- the observed Python, SQLite, GNU Make, Debian, and locale identities **match** the
  inspected amd64 image, so choosing arm64 does not sacrifice any observed version
  parity;
- **no reviewed repository governance evidence identified an x86_64 requirement** for
  the SCOWL build or extraction;
- the exact **platform-specific digest** establishes an immutable canonical identity.

Host convenience alone is explicitly **not** the reproducibility argument. The
reproducibility argument is the immutable platform-specific digest plus the
still-required two-clean-build byte-identity test. The amd64 image
(`sha256:058149828b…`) may remain an **optional future corroboration** environment; it
is not part of the canonical identity, and no cross-platform equivalence is asserted.

## Exact Future Invocation Identity
```text
Label: PROJECT POLICY DECISION for identity;
       NOT YET APPROVED / NOT EXECUTED for execution
```

Any future canonical build must be pinned to **both** the platform flag and the
platform-specific digest:

```text
--platform linux/arm64
docker.io/library/python@sha256:77747425b0797fccc62b5ced9a4ca7854c7247485c89681c57e48767ed3343d6
```

Inside that environment, the future build and extraction would use the already-selected
identities (carried forward, **not executed here**):

```bash
# BUILD (identity only; NOT EXECUTED in this branch)
make            # → combine.py create-db scowl.db

# EXTRACTION (identity only; NOT EXECUTED in this branch)
PYTHONIOENCODING=utf-8 \
./scowl --db scowl.db word-list 60 A 1 \
  --categories= \
  --wo-poses=abbr \
  --wo-pos-categories=nonword,wordpart
```

Deliberately **not** specified here, and deferred to the future operationalization
branch: the exact `docker run` mount points, working directory, source-checkout
procedure, notice-retrieval procedure, and artifact placement. This record fixes the
**environment identity and the platform flag** only. **This future invocation is not
executed in this branch.**

## Reproducibility Requirements Carried Forward
The 15-point reproducibility contract from
`docs/callhome_english_scowl_build_environment_evidence.md` remains in force. This
record advances only the environment-identity items; it satisfies **none** of the
build, hash, or approval items.

```text
 1. use SCOWL tag rel-2026.02.25 ......................... carried forward (unchanged)
 2. verify commit 7e99edab… ............................. FUTURE VERIFICATION REQUIREMENT
 3. use an immutable container-image digest ............. ADVANCED — platform-specific
                                                          digest now selected
 4. record exact Python and SQLite versions from inside
    the image ........................................... ADVANCED — recorded as
                                                          VERIFIED IMAGE OBSERVATION
                                                          (Python 3.12.13, SQLite 3.40.1)
 5. build from a clean source tree ...................... NOT YET APPROVED / NOT EXECUTED
 6. run the exact approved build command ................ NOT YET APPROVED / NOT EXECUTED
 7. run the exact approved extraction command ........... NOT YET APPROVED / NOT EXECUTED
 8. force UTF-8 output .................................. policy carried forward
 9. generate only local, gitignored artifacts .......... NOT YET APPROVED / NOT EXECUTED
10. perform two independent clean builds ................ FUTURE VERIFICATION REQUIREMENT
11. compare SHA-256 digests ............................. FUTURE VERIFICATION REQUIREMENT
12. require exact digest equality before approval ....... FUTURE VERIFICATION REQUIREMENT
13. record aggregate structural checks (no content) ..... FUTURE VERIFICATION REQUIREMENT
14. preserve required notices separately ................ policy carried forward
                                                          (bundle resolved by PR #67)
15. keep artifacts and hashes local until separately
    approved ............................................ carried forward (unchanged)
```

Selecting and observing the canonical image **advances** items 3 and 4 but does not
convert any of them into a demonstrated reproducibility result.

## Risks and Limitations
- **A digest fixes one platform-specific image but does not itself prove deterministic
  SCOWL output.** Determinism must still be demonstrated empirically.
- **Two independent clean builds remain required**, with matching SHA-256 digests,
  before any artifact could be approved. This has not been done.
- **Cross-platform identity has not been tested.** No claim is made that the arm64 and
  amd64 images produce identical SCOWL output, despite matching version strings.
- **Registry availability is not guaranteed forever.** An image could later be
  untagged or removed upstream, so the digest, tag, index digest, and provenance are
  recorded here to preserve identity even if the tag moves or disappears.
- **The image tag and the multi-platform index digest are not substitutes for the
  selected platform-specific digest.** Only the platform-specific digest identifies the
  exact image that executes on the canonical platform.
- **Docker Desktop and host details are not part of the canonical artifact identity.**
  The client/engine versions, BuildKit version, and host architecture are context, not
  build-artifact provenance; a different host with the same digest and platform is
  expected to obtain the same image.
- **No SCOWL build has been empirically tested in the selected image.** Feasibility is
  inferred from observed minimums, not demonstrated by a build.
- **Current environment observations came from temporary inspection containers**
  (`docker run --rm`), not from a persisted, controlled build container.
- **Operational placement and several filenames remain unresolved** here — the
  resource-directory location, the wordlist filename, the provenance filename and
  schema, and the Docker mount and working-directory policy are all deferred to a
  separate future branch. The **notice filename is already resolved as
  `SCOWL-COPYRIGHT.txt`** (by merged PR #67); only the **exact local placement of that
  notice file remains unresolved**.
- **No CALLHOME evidence informed this selection**, and no CALLHOME content was
  accessed during any inspection.

## Evidence Matrix
| Topic | Evidence | What it establishes | Remaining uncertainty | Label |
| ----- | -------- | ------------------- | --------------------- | ----- |
| Docker runtime present | local inspection: client/engine 29.6.1, arm64 | a working arm64 container runtime exists on the host | runtime is host context, not artifact identity | VERIFIED LOCAL OBSERVATION |
| Host architecture | local inspection: `arm64` / engine `aarch64` | host runs arm64 natively | — | VERIFIED LOCAL OBSERVATION |
| Platform support | local inspection: arm64 native, amd64 emulated | both platforms buildable/runnable locally | emulation ≠ identity guarantee | VERIFIED LOCAL OBSERVATION |
| Canonical image identity | platform-specific digest `sha256:77747425…` | one immutable arm64 image is fixed | digest ≠ deterministic output | PROJECT POLICY DECISION |
| Canonical Python version | arm64 image: CPython 3.12.13 | exact canonical Python recorded | reproducibility still untested | VERIFIED IMAGE OBSERVATION |
| Canonical SQLite version | arm64 image: SQLite 3.40.1 (via Python) | exact canonical SQLite recorded; exceeds min 3.33.0 | reproducibility still untested | VERIFIED IMAGE OBSERVATION |
| Canonical build tool | arm64 image: GNU Make 4.3 | `make` step is available in-image | build not run | VERIFIED IMAGE OBSERVATION |
| Canonical OS / locale | arm64 image: Debian 12; `C.UTF-8` | OS and UTF-8 locale fixed | — | VERIFIED IMAGE OBSERVATION |
| Version parity across arch | amd64 image: same Python/SQLite/Make/OS/locale | version strings match across arch | byte-identity untested; not asserted | VERIFIED IMAGE OBSERVATION |
| Upstream minimums met | prior record min (3.7 / 3.33.0) vs. observed (3.12.13 / 3.40.1) | image exceeds documented minimums | meeting minimums ≠ determinism | VERIFIED IMAGE OBSERVATION |
| Two-build byte identity | none | would demonstrate byte determinism | not run | FUTURE VERIFICATION REQUIREMENT |
| Cross-platform identity | none | optional corroboration only | not run | FUTURE VERIFICATION REQUIREMENT |

## Environment Matrix
| Environment layer | Canonical value | Evidence source | Status |
| ----------------- | --------------- | --------------- | ------ |
| SCOWL source tag | `rel-2026.02.25` | prior records | carried forward |
| SCOWL immutable commit | `7e99edab8e32f9f9ea2b15f249ca8d4d67237410` | prior records | FUTURE VERIFICATION REQUIREMENT (verify at build) |
| Canonical platform | `linux/arm64/v8` | this record | PROJECT POLICY DECISION |
| Image repository | `docker.io/library/python` | this record | PROJECT POLICY DECISION |
| Human-readable tag | `3.12.13-bookworm` | this record | provenance only (mutable) |
| Multi-platform index digest | `sha256:4f1cc04d959e1360fb4e6957e23e5cd96d32a239d996af6d5c7ad29ee55175d0` | this record | provenance only (not canonical) |
| Platform-specific digest | `sha256:77747425b0797fccc62b5ced9a4ca7854c7247485c89681c57e48767ed3343d6` | this record | PROJECT POLICY DECISION (canonical identity) |
| Canonical reference | `docker.io/library/python@sha256:77747425b0797fccc62b5ced9a4ca7854c7247485c89681c57e48767ed3343d6` | this record | PROJECT POLICY DECISION |
| Operating system | Debian GNU/Linux 12 (bookworm) | arm64 image | VERIFIED IMAGE OBSERVATION |
| Architecture | aarch64 | arm64 image | VERIFIED IMAGE OBSERVATION |
| Python implementation | CPython | arm64 image | VERIFIED IMAGE OBSERVATION |
| Python version | 3.12.13 | arm64 image | VERIFIED IMAGE OBSERVATION |
| SQLite runtime | 3.40.1 (via Python) | arm64 image | VERIFIED IMAGE OBSERVATION |
| Build tool | GNU Make 4.3 | arm64 image | VERIFIED IMAGE OBSERVATION |
| Locale | `C.UTF-8` | arm64 image | VERIFIED IMAGE OBSERVATION |
| Output encoding | UTF-8 (`PYTHONIOENCODING=utf-8`) | prior policy | carried forward |
| Line endings | LF | prior policy | carried forward |
| Build command | `make` (→ `combine.py create-db scowl.db`) | prior records | identity carried forward; NOT EXECUTED |
| Extraction command | `./scowl --db scowl.db word-list 60 A 1 --categories= --wo-poses=abbr --wo-pos-categories=nonword,wordpart` | prior records | identity carried forward; NOT EXECUTED |
| Notice filename | `SCOWL-COPYRIGHT.txt` | PR #67 | CARRIED FORWARD / ALREADY RESOLVED BY PR #67 |
| Notice local placement | none | — | UNRESOLVED / DEFERRED |
| Mount / working-directory policy | none | — | deferred to future branch |
| First-build SHA-256 | none | — | NOT EXECUTED |
| Second-build SHA-256 | none | — | NOT EXECUTED |
| Byte-identity result | none | — | NOT EXECUTED |
| Cross-platform result | none | — | NOT EXECUTED (optional) |

## Decision Matrix
| Decision or gate | Status |
| ---------------- | ------ |
| Docker runtime installed and inspected | YES / VERIFIED LOCAL OBSERVATION |
| Candidate images inspected in temporary containers | YES / VERIFIED IMAGE OBSERVATION |
| Canonical platform selected (`linux/arm64/v8`) | YES / PROJECT POLICY DECISION |
| Canonical platform-specific digest selected | YES / PROJECT POLICY DECISION |
| Exact canonical Python version recorded | YES / VERIFIED IMAGE OBSERVATION |
| Exact canonical SQLite version recorded | YES / VERIFIED IMAGE OBSERVATION |
| Exact canonical build-tool version recorded | YES / VERIFIED IMAGE OBSERVATION |
| Future invocation identity fixed (`--platform` + digest) | YES / PROJECT POLICY DECISION |
| Cross-platform byte identity asserted | NO |
| Deterministic SCOWL output proven | NO |
| SCOWL source checkout | NO / NOT APPROVED |
| Commit pin re-verification at build | FUTURE VERIFICATION REQUIREMENT |
| Notice retrieval / hashing | NO / NOT APPROVED |
| `make` execution | NO / NOT APPROVED |
| `scowl.db` generation | NO / NOT APPROVED |
| Wordlist extraction | NO / NOT APPROVED |
| Resource-directory creation | NO / NOT APPROVED |
| Generated-wordlist output filename approval | NO / NOT APPROVED |
| Local placement approval | NO / NOT APPROVED |
| Artifact hash computation | NO / NOT APPROVED |
| Two-clean-build byte-identity test | NO / NOT EXECUTED |
| Artifact approval | NO / NOT APPROVED |
| Loader execution | NO / NOT APPROVED |
| Aggregate CALLHOME dry run | NO / NOT APPROVED |
| Real CALLHOME validation | NO / NOT APPROVED |
| Row promotion | NO / NOT APPROVED |
| Condition construction | NO / NOT APPROVED |
| Tokenizer training | NO / NOT APPROVED |
| Model training | NO / NOT APPROVED |

## Current Pipeline State
```text
total CALLHOME rows: 88404
validated: 0
not_validated: 88404
lexicon_exact_match: 0
clean: 0
EnglishMono candidates: 0
SpanishMono candidates: 0
MonoCont candidates: 0
blocked from all conditions: 88404
```

## Safety and Routing State
```text
CALLHOME English
→ potentially EnglishMono
→ potentially the English portion of MonoCont
→ potentially future CsCont English monolingual filler, selected only from
  MonoCont-English

CALLHOME Spanish
→ potentially SpanishMono
→ potentially the Spanish portion of MonoCont
→ potentially future CsCont Spanish monolingual filler, selected only from
  MonoCont-Spanish

Bangor Miami
→ primary current source of genuine code-switched evidence for CsCont
```

CALLHOME never receives generic `CsCont` candidacy and never qualifies as
genuine code-switched, mixed-language, or switching-quota evidence.

- **No CALLHOME content was inspected or accessed.**
- **No SCOWL source was downloaded; no build was run; no SCOWL artifact,
  generated-wordlist, preserved-notice, or build-output SHA-256 was computed.**
- **The real pipeline remains on conservative default validation.**
- **All rows remain blocked from conditions.**
- **No Spanish resource or locale decision changes in this branch.**

## Next Step
The next branch should be a **separate, controlled operationalization-approval branch**.
It should define, without scope creep:

- the exact SCOWL source-retrieval and pin-verification procedure (verify tag
  `rel-2026.02.25` and commit `7e99edab8e32f9f9ea2b15f249ca8d4d67237410`);
- the exact notice-retrieval and hash-verification procedure (upstream `Copyright` byte
  SHA-256 == local `SCOWL-COPYRIGHT.txt` SHA-256);
- the local, gitignored resource-directory location;
- the wordlist filename;
- carry forward the already-selected notice filename `SCOWL-COPYRIGHT.txt` and define
  its exact local placement;
- the provenance filename and schema;
- the two-independent-clean-build procedure and SHA-256 equality criterion;
- the exact Docker mount and working-directory policy;
- the exact build and extraction procedure inside the canonical image;
- the aggregate, content-free structural checks;
- the artifact-approval criteria;
- the cleanup and local-retention policy.

This current branch must **not** perform those operational steps. Until a later,
separately approved branch executes and verifies them, the canonical environment is
**selected but unused**, no build has been run, byte-identical reproducibility is **not
demonstrated**, cross-platform identity is **not asserted**, and every operational gate
remains **closed**.
