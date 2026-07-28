# CALLHOME English SCOWL / ESDB Build-Environment Evidence

## Status
```text
Canonical reproducibility contract:
YES / APPROVED FOR CONTINUED GOVERNANCE

Canonical mechanism:
IMMUTABLE CONTAINER IMAGE DIGEST REQUIRED

Container image selected:
NO

Container image pulled or created:
NO

Exact image digest recorded:
NO

Exact canonical Python version recorded:
NO / PENDING IMAGE SELECTION

Exact canonical SQLite version recorded:
NO / PENDING IMAGE SELECTION

Two-build byte identity demonstrated:
NO

Cross-environment identity demonstrated:
NO
```

Determination:
```text
Source-generated Model 1 has a concrete, testable path to
reproducible generation under a canonical digest-pinned
environment and a two-clean-build byte-identity test.

Technical reproducibility feasibility:
YES / SUPPORTED BY EVIDENCE

Byte-identical reproducibility demonstrated:
NO

Model 1 selected:
NO

ESDB selected:
NO

LibreOffice selection replaced:
NO
```

This is a **repository governance record, not legal advice.** This branch approves
**only** a bounded reproducibility contract for continued governance. It does **not**
select ESDB, replace the LibreOffice candidate, download or build SCOWL, run
`combine.py` or `scowl`, generate `scowl.db` or a wordlist, pull or create a
container image, compute a resource hash, or run CALLHOME validation.

- **No CALLHOME transcript content or CALLHOME-derived evidence was inspected or
  used.**
- **No SCOWL/ESDB source or artifact was downloaded, checked out, saved, built, or
  generated; no container was pulled, built, or created; no hash was computed.**
- **Upstream inspection was read-only** (official `en-wl/wordlist` README at the
  pinned commit) and is distinguished below from facts already recorded in prior
  repository documentation.
- **The real pipeline remains unchanged** (`default_source_validation` only;
  validator/loader not wired into `scripts/summarize_callhome_projection_local.py`).
  Every real CALLHOME row stays `not_validated`; `clean` stays zero.
- **All operational approvals remain `NO / NOT APPROVED`.**

## Problem Being Addressed
The SCOWL/ESDB candidate evidence record
(`docs/callhome_english_scowl_candidate_evidence.md`) proposed **Model 1** — a
source-generated plain wordlist — as technically preferable for the current
exact-match / no-affix-expansion validator, but left **byte-for-byte reproducibility
across Python and SQLite environments undemonstrated**, and the proper-name policy
record (`docs/callhome_english_scowl_proper_name_policy.md`) resolved the residual
proper-name question for continued governance. What remains, before Model 1 could be
considered for selection, is a **canonical build-environment and reproducibility
contract**: exactly which environment the wordlist would be generated in, and what
would make its output reproducible. This record defines that contract. It selects and
executes nothing.

## Three Distinct Environments (not assumed identical)
This project involves **three separate environments** that must not be conflated:

1. **Current development environment** — where tests and lint run today. Defined
   loosely by `pyproject.toml` (`requires-python >= 3.11`; dev extras `pytest>=8`,
   `ruff>=0.6`; `[tool.ruff] target-version = "py311"`; **no runtime
   dependencies**). The repository contains **no** `.python-version`, `uv.lock`,
   `requirements*.txt`, `environment*.yml`, `Dockerfile*`, `Makefile`, or
   `.github/workflows/` — so the current dev environment is currently
   under-pinned and is **not** a canonical build environment.
2. **Proposed SCOWL artifact-generation environment** — where a future wordlist
   would be built. This is the subject of this record and **must** be a canonical,
   digest-pinned container (below). It is **not** the developer laptop.
3. **Later model-training environment** — a separate environment for training the
   four model conditions. Out of scope here; **not** assumed identical to either of
   the above.

The observed local environment (below) is **evidence only**; it is **not**
designated canonical.

## Observed Local Environment (evidence only)
Read-only inspection of the current machine (no usernames, paths, hostnames,
environment variables, or secrets recorded):

```text
python_version=3.12.7
python_implementation=CPython
sqlite_runtime_version=3.45.3
sqlite_module_version=2.6.0
os_system=Darwin
os_release=24.4.0
machine=arm64
pip=24.2 (Python 3.12)
make=GNU Make 3.81
```

The local Python (3.12.7) and SQLite (3.45.3) both exceed the documented upstream
minimums (Python 3.7 / SQLite 3.33.0), consistent with "newer versions should work."
This does **not** make the laptop canonical; the canonical environment must be
identified by an immutable container-image digest.

## Upstream Evidence at the Proposed Pin
```text
Release tag: rel-2026.02.25
Commit:      7e99edab8e32f9f9ea2b15f249ca8d4d67237410
```

New **direct** read-only verification of the official `en-wl/wordlist` README at this
commit:

- **Documented Python requirement (DIRECT):** "It currently requires Python 3.7 and
  SQLite 3.33.0. Newer versions should work, older versions may work but are not
  supported."
- **Documented SQLite requirement (DIRECT):** SQLite 3.33.0 (same statement).
- **Alpha/testing status (DIRECT):** "As SCOWLv2 is still in an alpha/testing phase
  the command line utility and schema is subject to change"; and the `scowl` script
  is "a very thin wrapper around the `libscowl` package … the API may still change."
- **Build role (DIRECT):** "the database must first be created from the source files
  in the `data/` … simply type: make which will create the sqlite3 file `scowl.db`."
- **Extraction role (DIRECT):** "To extract wordlists from the database use:
  `./scowl --db scowl.db word-list 60 A 1 > wl.txt`."

Facts **already recorded in prior repository documentation** (cited, distinguished
from the new direct verification above):

- **`combine.py` role (REPOSITORY-RECORDED):** per the Makefile inspection recorded
  in `docs/callhome_english_scowl_candidate_evidence.md`, `make` builds `scowl.db`
  via `./combine.py create-db scowl.db`, and `scowl.txt` via
  `./scowl export --db scowl.db`. (The README describes `make`→`scowl.db` but does
  not itself name `combine.py`.)
- **`scowl.db` construction / offline sufficiency (REPOSITORY-RECORDED):**
  `data/scowl-pre.txt` (~15.6 MB) and the other `data/` inputs are committed at the
  pin; `make` runs offline with no network access. The committed source tree
  **appears sufficient** for an offline build; this has **not** been empirically
  demonstrated by an actual build in this branch.
- **Sorted + deduplicated output (REPOSITORY-RECORDED):** `printWordList` does
  `words = sorted(...)` and emits deduplicated bare entries (`if w != prev:
  print(w)`), one per line, no header — per the `libscowl/__main__.py` reading in
  the candidate-evidence record.
- **Byte-level reproducibility (NOT DEMONSTRATED):** no build has been run; exact
  byte-for-byte reproducibility has **not** been empirically demonstrated.

No upstream file was cloned, checked out, downloaded, or saved.

## Conceptual Distinctions (five kinds of reproducibility)

### 1. Source reproducibility
The same immutable upstream source commit and extraction policy are used. Required
components:
```text
SCOWL release tag:   rel-2026.02.25
SCOWL immutable commit: 7e99edab8e32f9f9ea2b15f249ca8d4d67237410
source-artifact model: Model 1 (source-generated plain wordlist)
build command:       make  (→ combine.py create-db scowl.db)
extraction command:  ./scowl --db scowl.db word-list 60 A 1 --categories= --wo-poses=abbr --wo-pos-categories=nonword,wordpart
dialect:             A (American)
size:                60
variant level:       1
category/POS policy: --categories= ; --wo-poses=abbr ; --wo-pos-categories=nonword,wordpart
encoding policy:     PYTHONIOENCODING=utf-8 (UTF-8), LF line endings
```

### 2. Environment reproducibility
The build executes inside **one canonical environment whose complete software stack
is immutably identified**. The preferred future mechanism is:
```text
immutable container image identified by digest
```
An image **tag alone is insufficient** because tags can be retargeted. For a
multi-architecture image, the canonical platform and its platform-specific manifest
digest must both be fixed; an unresolved multi-architecture manifest does not
identify the environment that actually executes. The canonical environment must
make it possible to record: image repository; human-readable image tag; immutable
platform-specific image digest; operating-system distribution; architecture and
platform; exact Python version; Python implementation; exact SQLite runtime version;
exact build-tool version; locale and encoding policy; relevant environment variables;
SCOWL source commit; and the exact build and extraction commands. **No image is
selected or pulled in this branch.**

### 3. Semantic reproducibility
Two outputs contain the **same normalized entries in the same order**. This can
later be evaluated with **non-content-bearing** measurements only: total line count;
unique line count; duplicate count; blank-line count; UTF-8 validity; sorted-order
check; a normalized ordered-sequence hash; an optional normalized set hash; and fixed
policy metadata. The ordered-sequence hash tests both content and order, while the set
hash tests membership without order. Any such hash remains subject to separate
hash-computation approval. **No lexical entries are printed or committed.**

### 4. Byte-level reproducibility
Two independent **clean** builds in the **same canonical environment** produce
wordlist files with the **same SHA-256 digest**. Byte-level identity is **stronger**
than merely obtaining the same vocabulary size. **This has not yet been
demonstrated.**

### 5. Cross-environment reproducibility
A **second** environment produces the same byte-level or semantic output as the
canonical environment. This is valuable corroboration but is **not required** to
define the canonical build artifact; the **canonical environment remains the source
of truth**.

## Approved Reproducibility Contract (continued governance only)
The future canonical build must satisfy **all** of the following. Approving this
contract does **not** approve executing it.

1. use SCOWL tag `rel-2026.02.25`;
2. verify source commit `7e99edab8e32f9f9ea2b15f249ca8d4d67237410`;
3. use an immutable container-image **digest**;
4. record exact Python and SQLite versions **from inside the image**;
5. build from a **clean** source tree;
6. run the exact approved **build** command;
7. run the exact approved **extraction** command;
8. force **UTF-8** output;
9. generate only **local, gitignored** artifacts;
10. perform **two independent clean builds** inside the same canonical environment;
11. compare **SHA-256** digests;
12. require **exact digest equality** before artifact approval;
13. record **aggregate structural checks** without printing lexical content;
14. preserve required **notices** separately;
15. keep all artifacts and hashes **local** until a separate approval determines what
    metadata may enter Git.

## Proposed Extraction Policy
```bash
PYTHONIOENCODING=utf-8 \
./scowl --db scowl.db word-list 60 A 1 \
  --categories= \
  --wo-poses=abbr \
  --wo-pos-categories=nonword,wordpart
```
- It **remains proposed**.
- It **was not executed** in this branch.
- It is **not approved operationally** in this branch.
- Its **identity is part of the reproducibility contract** (source reproducibility,
  §1).

## Risks and Limitations
- **Upstream is alpha/testing.** The pinned README states SCOWLv2 is "still in an
  alpha/testing phase" and "the command line utility and schema is subject to
  change" (the `libscowl` API "may still change").
- **Newer `v2` commits may change extraction semantics.** `v2` HEAD post-dates the
  pin and includes commits that rework extraction (variant renumbering, "adjust
  cmd", POS codes) — hence a **dated-release pin**, not `v2` HEAD.
- **Python and SQLite versions may influence database construction or
  serialization** (e.g. SQLite storage/serialization behavior across versions).
- **Operating-system and architecture differences may matter** (the local machine is
  Darwin/arm64; a canonical Linux container would differ).
- **Locale should not control Python string sorting** (Python `sorted()` is
  code-point order), **but encoding and any external tooling still require control**
  (fixed locale/`PYTHONIOENCODING`).
- **Line endings must be fixed to LF.**
- **Output encoding must be UTF-8.**
- **Container tags alone are mutable** — only a **digest** immutably identifies the
  image.
- **A source commit does not identify the complete build environment** — the
  interpreter, libraries, OS, and tooling must also be pinned.
- **Identical line counts do not prove identical content.**
- **Identical semantic content does not necessarily imply identical bytes.**
- **No empirical reproduction test has yet been run** — byte identity is unproven.

Pinning **only** Python and SQLite would be **insufficient**; the full canonical
environment (image digest, OS, architecture, build tool, locale, encoding) must be
identified. Python's sorted output alone does **not** prove complete build
determinism (the SQLite database build precedes extraction).

## Evidence Matrix
| Topic | Evidence | What it establishes | Remaining uncertainty | Confidence |
| ----- | -------- | ------------------- | --------------------- | ---------- |
| Immutable SCOWL source identity | tag `rel-2026.02.25` → commit `7e99edab…` | A dated, immutable pin exists | pin is proposed, not selected | DIRECT |
| Upstream Python requirement | README @ pin: "requires Python 3.7" | Documented minimum Python 3.7; newer should work | exact canonical version pending image | DIRECT |
| Upstream SQLite requirement | README @ pin: "SQLite 3.33.0" | Documented minimum SQLite 3.33.0; newer should work | exact canonical version pending image | DIRECT |
| Offline source-build completeness | `data/scowl-pre.txt` + `data/*` committed; `make` offline (REPOSITORY-RECORDED) | Source tree **appears** sufficient for an offline build | not empirically built | STRONG |
| Build-command identity | README @ pin ("type: make"); Makefile record | `make` builds `scowl.db` (via `combine.py`) | — | DIRECT |
| Extraction-command identity | README @ pin (`./scowl … word-list 60 A 1`); libscowl record | The extraction path/command is fixed | remains proposed operationally | DIRECT |
| Sorted and deduplicated output | `libscowl/__main__.py` `printWordList` (REPOSITORY-RECORDED) | Output is sorted, unique, one bare line, no header | — | DIRECT |
| Current local Python version | local inspection | Python 3.12.7 (CPython) present | not canonical | DIRECT (OBSERVED LOCALLY) |
| Current local SQLite runtime | local inspection | SQLite 3.45.3 present | not canonical | DIRECT (OBSERVED LOCALLY) |
| Current local build tool | local inspection | GNU Make 3.81 present | not canonical | DIRECT (OBSERVED LOCALLY) |
| Container-digest requirement | OCI image addressing (tags mutable, digests immutable) | A digest is required to immutably identify the environment | no image selected | STRONG |
| Semantic reproducibility | non-content aggregate checks (planned) | Can be measured later without content | not yet measured | LIMITED |
| Byte-level reproducibility | two-clean-build SHA-256 test (planned) | Would prove byte identity in the canonical env | not yet run | LIMITED |
| Cross-environment reproducibility | second-environment comparison (optional) | Corroborates, not required for canonical identity | not yet run | LIMITED |

## Environment Matrix
| Environment layer | Current evidence | Canonical requirement | Status |
| ----------------- | ---------------- | --------------------- | ------ |
| SCOWL source | `rel-2026.02.25` @ `7e99edab…` (proposed pin) | verify tag + commit at build | PROPOSED |
| Operating system | Darwin 24.4.0 (local) | container OS recorded through image inspection | OBSERVED LOCALLY |
| Architecture | arm64 (local) | canonical platform and architecture explicitly fixed | OBSERVED LOCALLY |
| Container image | none present in repo | immutable image required | POLICY RESOLVED |
| Container digest | none | platform-specific manifest digest required before build | UNRESOLVED |
| Python implementation | CPython (local) | CPython recorded from image | OBSERVED LOCALLY |
| Python version | 3.12.7 (local); upstream min 3.7 | exact version recorded from image | OBSERVED LOCALLY |
| SQLite runtime | 3.45.3 (local); upstream min 3.33.0 | exact version recorded from image | OBSERVED LOCALLY |
| Build tool | GNU Make 3.81 (local) | exact make version recorded from image | OBSERVED LOCALLY |
| Locale | not designated | fixed UTF-8 locale (e.g. `C.UTF-8`) | POLICY RESOLVED |
| Output encoding | not designated | UTF-8 (`PYTHONIOENCODING=utf-8`) | POLICY RESOLVED |
| Line endings | not designated | LF | POLICY RESOLVED |
| Build command | `make` (README + Makefile record) | fixed `make` from a clean tree | POLICY RESOLVED |
| Extraction command | proposed `scowl … word-list 60 A 1 …` | exact command fixed in the contract | PROPOSED |
| First-build SHA-256 | none | computed after future approval | NOT EXECUTED |
| Second-build SHA-256 | none | computed after future approval | NOT EXECUTED |
| Byte-identity result | none | first == second required | NOT EXECUTED |
| Cross-environment result | none | optional corroboration only | NOT EXECUTED |

## Decision Matrix
| Decision or gate                              | Status                      |
| --------------------------------------------- | --------------------------- |
| Build-environment evidence reviewed           | YES / RECORDED              |
| Local environment observed                    | YES / RECORDED              |
| Canonical reproducibility contract defined    | YES / APPROVED              |
| Immutable container digest required           | YES / APPROVED              |
| Canonical image selected                      | NO                          |
| Exact canonical Python version selected       | NO                          |
| Exact canonical SQLite version selected       | NO                          |
| Two-build byte identity demonstrated          | NO                          |
| Cross-environment identity demonstrated       | NO                          |
| Model 1 technically reproducible in principle | YES / SUPPORTED BY EVIDENCE |
| Model 1 selected                              | NO                          |
| ESDB selected                                 | NO                          |
| LibreOffice replaced                          | NO                          |
| License-and-notice pathway approved           | NO / NOT APPROVED           |
| Container pull/build approved                 | NO / NOT APPROVED           |
| Source checkout approved                      | NO / NOT APPROVED           |
| SCOWL build approved                          | NO / NOT APPROVED           |
| Wordlist extraction approved                  | NO / NOT APPROVED           |
| Local placement approved                      | NO / NOT APPROVED           |
| Hash computation approved                     | NO / NOT APPROVED           |
| Loader use approved                           | NO / NOT APPROVED           |
| Aggregate dry run approved                    | NO / NOT APPROVED           |
| Real CALLHOME validation approved             | NO / NOT APPROVED           |
| Clean promotion approved                      | NO / NOT APPROVED           |
| Condition construction approved               | NO / NOT APPROVED           |
| Tokenization approved                         | NO / NOT APPROVED           |
| Model training approved                       | NO / NOT APPROVED           |

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

## Next Step
The next branch may perform the **English resource-selection reassessment** between
source-generated SCOWL / ESDB Model 1 and the currently selected LibreOffice
candidate. This contract supports only the conclusion that Model 1 has a concrete,
testable reproducibility path; it does not authorize its execution.

Before any later build, a separate branch must select and record a canonical
platform and platform-specific immutable container-image digest, then capture the
exact Python, SQLite, and build-tool versions from inside that image. Only a still
later, separately approved step may perform the two-clean-build byte-identity test on
**local, gitignored** artifacts and compute their SHA-256 digests. Until a selection
decision is made, Model 1 is **not selected**, ESDB is **not selected**, the
LibreOffice resource **remains selected pending review**, byte-identical
reproducibility is **not demonstrated**, and every operational gate remains
**closed**.
