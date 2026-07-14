# CALLHOME English SCOWL Operationalization Approval

## 1. Status / Decision
```text
Operationalization procedure:
YES / APPROVED FOR FUTURE CONTROLLED EXECUTION

What is approved:
the exact procedure a later execution branch may follow to retrieve, verify,
build, compare, preserve, check, and locally place the selected English SCOWL
wordlist and its upstream notice.

What is NOT approved and NOT done here:
executing any part of that procedure.

Operational execution in this branch:
NO / NOT EXECUTED IN THIS BRANCH
```

This is a **repository governance record, not legal advice.** This branch approves an
exact, auditable **procedure**. It does **not** run it. Approving a procedure is not the
same as executing it: fixing every identity in advance (URL, tag, commit, image digest,
filenames, environment, commands) is precisely what makes a later execution reviewable
and reproducible, while leaving every operational gate closed until that separate branch.

Nothing in this branch:

- clones or downloads SCOWL; pulls a container image; runs Docker; runs `make`;
  generates `scowl.db`; extracts a wordlist; retrieves or copies the notice;
- creates any local resource directory; computes any artifact or notice hash; writes any
  `provenance.json`;
- accesses CALLHOME in any form; runs a loader or validator;
- stages, commits, or pushes any SCOWL source, generated artifact, preserved
  notice, provenance file, artifact or notice hash, local operational log, or
  CALLHOME material.

Standing invariants (unchanged):

- **No CALLHOME transcript content or CALLHOME-derived evidence was inspected or used.**
- **CALLHOME-derived material must never shape, filter, expand, normalize, or otherwise
  influence the SCOWL artifact.**
- **CALLHOME never feeds CsCont; Bangor Miami remains CsCont-only.**
- **The real pipeline remains unchanged** (`default_source_validation` only; the
  validator/loader is not wired into `scripts/summarize_callhome_projection_local.py`).
  Every real CALLHOME row stays `not_validated`; `clean` stays zero.
- **No operational step is executed in this branch.**
- **Future SCOWL build operations** — source checkout, canonical Docker execution,
  two-build byte-identity verification, notice preservation, and conditional local
  placement — are **conditionally approved only under this exact procedure.**
- **Loader use, CALLHOME dry run/validation, row promotion, condition construction,
  tokenizer work, model training, and Git tracking remain closed.**

### Evidence labels used in this record
```text
VERIFIED REPOSITORY OBSERVATION   observed directly in this repository/working tree
VERIFIED REMOTE-REF OBSERVATION   observed via a narrow git remote-ref check
CARRIED-FORWARD PROJECT POLICY    a decision already closed by a merged record
PROJECT POLICY DECISION           a governance choice recorded in this record
FUTURE EXECUTION REQUIREMENT      something the execution branch MUST do/verify
CONDITIONAL FUTURE APPROVAL       approved only if all stated checks pass
NOT EXECUTED IN THIS BRANCH       an operational step neither run nor approved-as-run here
REMAINS CLOSED                    a downstream gate that stays closed
```
An **observation** is never, in this record, promoted into an operational **result**.

## 2. Scope and Relationship to Prior Records
This record is the operationalization-procedure layer anticipated by the prior
build-environment records. It sits **after** resource selection, proper-name policy, the
reproducibility contract, the notice bundle, and the canonical-container selection, and
**before** any actual build.

Governing prior records (not edited or reopened in this branch):
`docs/callhome_english_scowl_candidate_evidence.md`,
`docs/callhome_english_scowl_proper_name_policy.md`,
`docs/callhome_english_scowl_build_environment_evidence.md`,
`docs/callhome_english_lexicon_resource_selection_reassessment.md`,
`docs/callhome_english_scowl_notice_bundle_decision.md`,
`docs/callhome_english_scowl_canonical_build_environment.md`.

This record **adds** an approved procedure. It changes **no** existing file, reopens
**no** closed decision, and grants **no** operational execution.

## 3. Decisions Carried Forward
```text
Label: CARRIED-FORWARD PROJECT POLICY (all rows below)
```
```text
Resource ID:                 english_scowl_esdb_en_us
Resource family:             Direct SCOWL / English Speller Database (ESDB)
Artifact model:              source-generated plain wordlist
Upstream clone URL:          https://github.com/en-wl/wordlist.git
Release tag:                 rel-2026.02.25
Immutable commit:            7e99edab8e32f9f9ea2b15f249ca8d4d67237410
Dialect / size / variant:    A / 60 / 1
Category policy:             --categories=
Abbreviation exclusion:      --wo-poses=abbr
POS-category exclusions:     --wo-pos-categories=nonword,wordpart
Exact build command:         make
Exact extraction command:    PYTHONIOENCODING=utf-8 ./scowl --db scowl.db word-list 60 A 1
                             --categories= --wo-poses=abbr --wo-pos-categories=nonword,wordpart
Output policy:               UTF-8; LF; diacritics preserved; internal apostrophes
                             permitted; open compounds / hyphens / digits / special
                             symbols / abbreviations / nonwords / word parts excluded
Proper-name policy:          Policy A (resolved)
Canonical platform:          linux/arm64/v8
Docker platform flag:        linux/arm64
Container repository:        docker.io/library/python
Container tag:               3.12.13-bookworm
Multi-platform index digest: sha256:4f1cc04d959e1360fb4e6957e23e5cd96d32a239d996af6d5c7ad29ee55175d0
Platform-specific digest:    sha256:77747425b0797fccc62b5ced9a4ca7854c7247485c89681c57e48767ed3343d6
Canonical reference:         docker.io/library/python@sha256:77747425b0797fccc62b5ced9a4ca7854c7247485c89681c57e48767ed3343d6
Observed in canonical image: aarch64; Debian GNU/Linux 12 (bookworm); CPython 3.12.13;
                             SQLite 3.40.1; GNU Make 4.3; locale C.UTF-8
Notice source file:          Copyright (upstream repository root)
Preserved notice filename:   SCOWL-COPYRIGHT.txt
Preservation policy:         complete authoritative upstream file, verbatim, byte-for-byte
```

Cross-platform arm64/amd64 byte identity has **not** been tested and is **not required**
for canonical artifact approval.

## 4. Verified Remote-Reference Evidence
```text
Label: VERIFIED REMOTE-REF OBSERVATION
```
A narrow remote-ref check of the official upstream was previously run:

```bash
git ls-remote --exit-code \
  https://github.com/en-wl/wordlist.git \
  'refs/tags/rel-2026.02.25' \
  'refs/tags/rel-2026.02.25^{}'
```

It resolved the release tag directly to the selected immutable commit:

```text
7e99edab8e32f9f9ea2b15f249ca8d4d67237410    refs/tags/rel-2026.02.25
```

Recorded fact: **the tag ref `refs/tags/rel-2026.02.25` resolves to commit
`7e99edab8e32f9f9ea2b15f249ca8d4d67237410`.** No claim is made here about whether the tag
is annotated or lightweight; that distinction is unnecessary for this approval. **No
source repository clone, working-tree checkout, or SCOWL source-artifact download
occurred.** The narrow `git ls-remote` ref-advertisement exchange did involve network
communication and received ref metadata; this is **not** overstated as receiving no
network data. It remains a **`VERIFIED REMOTE-REF OBSERVATION`** only.

## 5. Approved Local Bundle Layout
```text
Label: PROJECT POLICY DECISION (layout, filenames); not created in this branch
```
Approved future local layout under the already-ignored root
`data/resources/local_lexicons/` (**not created here**):

```text
data/resources/local_lexicons/
  _work/
    english_scowl_esdb_en_us/
      build-1/
        source/
        output/
      build-2/
        source/
        output/
      promotion-staging/
        scowl_en_US_size60_var1.txt
        SCOWL-COPYRIGHT.txt
        provenance.json
  english/
    english_scowl_esdb_en_us/
      scowl_en_US_size60_var1.txt
      SCOWL-COPYRIGHT.txt
      provenance.json
```

Interpretation:

- `_work/` holds two temporary, independent checkouts and their build outputs.
- `_work/english_scowl_esdb_en_us/promotion-staging/` is a temporary, **complete
  candidate bundle** (artifact + notice + provenance) assembled and verified inside
  `_work/` before conditional promotion (§14) to the final bundle.
- `english/english_scowl_esdb_en_us/` is the final local bundle.
- **Neither structure is created in this branch.**
- All content remains **local and Git-ignored**; nothing here may appear in `git status`.
- **No `.gitkeep` or placeholder resource files may be added** (that would introduce
  tracked resource paths).

Approved exact filenames (`PROJECT POLICY DECISION`):

```text
Generated wordlist:   scowl_en_US_size60_var1.txt
Preserved notice:     SCOWL-COPYRIGHT.txt   (CARRIED-FORWARD; already resolved by PR #67)
Provenance:           provenance.json
```

The loader remains **caller-path-driven** and must **not** be modified or wired in this
branch, nor in the execution branch.

## 6. Approved Future Network Boundary
```text
Label: PROJECT POLICY DECISION / FUTURE EXECUTION REQUIREMENT
```
Network access during future execution is allowed **only** for:

1. the narrow git remote-ref verification (§8);
2. cloning the official upstream repository `https://github.com/en-wl/wordlist.git` (§7);
3. pulling the canonical image **by immutable digest** only if it is not already present
   locally.

The SCOWL build containers must run **fully offline**:

```text
--network none
--pull=never
```

- **No CALLHOME path and no repository root may be mounted into any container.**
- **Only** the specific per-build `source/` and `output/` directories may be mounted.
- **No network request may occur during `make` or extraction.** If the build attempts
  network access, that is a stop condition (§17).

## 7. Approved Future Source-Retrieval Procedure
```text
Label: CONDITIONAL FUTURE APPROVAL / FUTURE EXECUTION REQUIREMENT
Not executed in this branch.
```
Identities the execution branch must use verbatim:

```bash
UPSTREAM_URL=https://github.com/en-wl/wordlist.git
RELEASE_TAG=rel-2026.02.25
EXPECTED_COMMIT=7e99edab8e32f9f9ea2b15f249ca8d4d67237410
```

`PROJECT_ROOT` must be determined dynamically (never hard-coded):

```bash
PROJECT_ROOT="$(git rev-parse --show-toplevel)"
```

**Fresh-path preconditions (`FUTURE EXECUTION REQUIREMENT`).** Before creating anything,
the execution branch must confirm that **all** of the following paths are **absent**, and
must **stop** rather than reuse any stale directory or file:

```text
data/resources/local_lexicons/_work/english_scowl_esdb_en_us/build-1/source
data/resources/local_lexicons/_work/english_scowl_esdb_en_us/build-1/output
data/resources/local_lexicons/_work/english_scowl_esdb_en_us/build-2/source
data/resources/local_lexicons/_work/english_scowl_esdb_en_us/build-2/output
data/resources/local_lexicons/_work/english_scowl_esdb_en_us/promotion-staging
data/resources/local_lexicons/english/english_scowl_esdb_en_us          (final bundle)
```

Stale `scowl.db` files, prior wordlists, prior notices, prior `provenance.json` files, or
prior build outputs **must never be reused**. The procedure may create an approved path
only after **each** of these holds for that path:

1. `PROJECT_ROOT` is resolved with `git rev-parse --show-toplevel`;
2. the intended path is confirmed to be **beneath** `data/resources/local_lexicons/`;
3. `git check-ignore` confirms the intended path is **Git-ignored**.

**Path-creation rules (`FUTURE EXECUTION REQUIREMENT`).** Creation is restricted **per
path**; `mkdir -p` is **not** a blanket license to create every path listed above:

- `build-1/source` and `build-2/source` must remain **absent** and must be created **only**
  by their respective independent `git clone` operations (below);
- `build-1/output` and `build-2/output` may be created explicitly (e.g. `mkdir -p`) **after**
  the `PROJECT_ROOT`, beneath-`local_lexicons/` containment, and `git check-ignore` checks
  pass;
- `promotion-staging/` may be created **only when assembling the complete candidate
  bundle**, after the two builds and preliminary verification (§10/§12/§14);
- the final parent directory `data/resources/local_lexicons/english/` may be created **after
  the same safety checks** (`PROJECT_ROOT` resolution, beneath-`local_lexicons/`
  containment, and `git check-ignore`);
- the final bundle directory
  `data/resources/local_lexicons/english/english_scowl_esdb_en_us/` must **never** be created
  with `mkdir`, `mkdir -p`, copying, or placeholder files — it comes into existence **only**
  through the approved atomic rename (§14);
- **no broad `rm -rf` operation is approved** (see §18 for the narrow, targeted retention
  and cleanup policy).

Every relevant path must **initially be absent**, and **stale files must never be reused**.

Two **independent** fresh checkouts must be created, one per build:

```text
data/resources/local_lexicons/_work/english_scowl_esdb_en_us/build-1/source
data/resources/local_lexicons/_work/english_scowl_esdb_en_us/build-2/source
```

Each checkout must be created **independently** from the official URL (no reuse, no copy
of one into the other). An approved procedure per `SOURCE_DIR`:

```bash
git clone --no-checkout \
  https://github.com/en-wl/wordlist.git \
  "$SOURCE_DIR"

git -C "$SOURCE_DIR" checkout --detach \
  refs/tags/rel-2026.02.25
```

Each checkout must then verify, before `make`:

- `origin` URL equals the approved `UPSTREAM_URL`;
- `HEAD` equals `EXPECTED_COMMIT`;
- the checked-out tree is **clean** (no modifications);
- **no untracked files** exist;
- the tag resolves **exactly** to `EXPECTED_COMMIT` via
  `git -C "$SOURCE_DIR" rev-parse "refs/tags/${RELEASE_TAG}^{commit}"` (see §8).

**If any verification fails, the execution branch must stop** and must not continue to
`make` (§17).

## 8. Approved Future Pin-Verification Procedure
```text
Label: FUTURE EXECUTION REQUIREMENT
```
For **each** of the two checkouts, independently:

1. confirm the remote-ref resolution (as in §4) still yields `EXPECTED_COMMIT`;
2. confirm the local tag resolves **exactly** to the expected commit:

```bash
git -C "$SOURCE_DIR" rev-parse "refs/tags/${RELEASE_TAG}^{commit}"
```

   and require the result to equal `7e99edab8e32f9f9ea2b15f249ca8d4d67237410`;
3. confirm `git -C "$SOURCE_DIR" rev-parse HEAD` equals `EXPECTED_COMMIT`;
4. confirm `git -C "$SOURCE_DIR" config --get remote.origin.url` equals `UPSTREAM_URL`;
5. confirm `git -C "$SOURCE_DIR" status --porcelain` is empty (clean, no untracked) before
   `make`;
6. record both resolved commits into provenance as `build_1_source_commit` and
   `build_2_source_commit` (both must equal `EXPECTED_COMMIT`).

The `^{commit}` peel resolves the tag to its underlying commit regardless of whether the
tag is annotated or lightweight, so no annotated-versus-lightweight claim is made or
needed. Pin verification is content-free: it records commit identity and cleanliness only,
never repository file contents.

## 9. Approved Future Container Invocation
```text
Label: CONDITIONAL FUTURE APPROVAL / FUTURE EXECUTION REQUIREMENT
Not executed or tested in this branch.
```
Canonical image (immutable digest):

```bash
IMAGE=docker.io/library/python@sha256:77747425b0797fccc62b5ced9a4ca7854c7247485c89681c57e48767ed3343d6
```

**Canonical-image availability preflight (`FUTURE EXECUTION REQUIREMENT`; not run here).**
Before any build, run this preflight once (network is permitted here only per §6):

1. check whether the exact canonical image reference is already available locally:

```bash
docker image inspect \
  docker.io/library/python@sha256:77747425b0797fccc62b5ced9a4ca7854c7247485c89681c57e48767ed3343d6 \
  >/dev/null 2>&1
```

2. if it is **absent**, allow **exactly one** pull, by the exact immutable reference and
   the pinned platform:

```bash
docker pull --platform linux/arm64 \
  docker.io/library/python@sha256:77747425b0797fccc62b5ced9a4ca7854c7247485c89681c57e48767ed3343d6
```

3. afterward, inspect the image by the **exact digest reference** and read its platform:

```bash
docker image inspect \
  --format '{{.Os}}/{{.Architecture}}' \
  docker.io/library/python@sha256:77747425b0797fccc62b5ced9a4ca7854c7247485c89681c57e48767ed3343d6
```

4. require the resolved image platform to be `linux/arm64`;
5. **stop** (§17) if any of these holds:
   - the exact canonical digest reference cannot be inspected;
   - when absent, the exact canonical digest reference cannot be pulled using
     `--platform linux/arm64`;
   - the exact canonical digest reference remains unavailable after the permitted pull;
   - the inspected image reports a platform other than `linux/arm64`.

The build containers themselves must still run with `--pull=never` (§6); the single
permitted pull happens **only** in this preflight, never inside a build container.

Each build must run **independently** with an invocation equivalent to:

```bash
docker run --rm \
  --platform linux/arm64 \
  --pull=never \
  --network none \
  --user "$(id -u):$(id -g)" \
  -e HOME=/tmp \
  -e LANG=C.UTF-8 \
  -e LC_ALL=C.UTF-8 \
  -e PYTHONIOENCODING=utf-8 \
  -e PYTHONDONTWRITEBYTECODE=1 \
  -v "$SOURCE_DIR:/work/source:rw" \
  -v "$OUTPUT_DIR:/work/output:rw" \
  -w /work/source \
  "$IMAGE" \
  sh -eu -c '
    umask 077

    # --- Mandatory environment assertions: must ALL pass BEFORE make. ---
    # Each check exits nonzero on mismatch; only version strings / PASS are printed.

    arch="$(uname -m)"
    echo "uname_m=${arch}"
    [ "${arch}" = "aarch64" ] || { echo "FAIL: architecture"; exit 1; }

    . /etc/os-release
    echo "os_id=${ID} os_version_id=${VERSION_ID}"
    [ "${ID}" = "debian" ]      || { echo "FAIL: os id"; exit 1; }
    [ "${VERSION_ID}" = "12" ]  || { echo "FAIL: os version"; exit 1; }

    make_version="$(make --version | head -n1)"
    echo "make_version=${make_version}"
    [ "${make_version}" = "GNU Make 4.3" ] || { echo "FAIL: make version"; exit 1; }

    charmap="$(locale charmap)"
    echo "locale_charmap=${charmap}"
    [ "${charmap}" = "UTF-8" ] || { echo "FAIL: locale charmap"; exit 1; }

    python3 - <<"PYCHECK"
import platform, sqlite3, sys
enc = (sys.stdout.encoding or "").lower().replace("-", "")
assert platform.python_implementation() == "CPython", "python implementation"
assert platform.python_version() == "3.12.13", "python version"
assert sqlite3.sqlite_version == "3.40.1", "sqlite version"
assert enc == "utf8", "python stdout encoding"
print("python_implementation=%s" % platform.python_implementation())
print("python_version=%s" % platform.python_version())
print("sqlite_version=%s" % sqlite3.sqlite_version)
print("python_stdout_encoding=%s" % sys.stdout.encoding)
print("ENV_ASSERTIONS=PASS")
PYCHECK

    # --- Only after every assertion passes: build, then extract. ---
    make

    PYTHONIOENCODING=utf-8 \
    ./scowl --db scowl.db word-list 60 A 1 \
      --categories= \
      --wo-poses=abbr \
      --wo-pos-categories=nonword,wordpart \
      > /work/output/scowl_en_US_size60_var1.txt
  '
```

This is a **future approved procedure only**; it is **not executed or tested** in this
branch. `$SOURCE_DIR` and `$OUTPUT_DIR` are the per-build directories from §5/§7; only
those two directories are mounted. No CALLHOME path and no repository root is mounted.

The assertions above are the **mandatory environment checks**, enforced **inside the same
container before `make`** (any mismatch exits nonzero and is a stop condition, §17):

```text
uname -m                       == aarch64
/etc/os-release ID             == debian
/etc/os-release VERSION_ID     == 12
Python implementation          == CPython
Python version                 == 3.12.13
Python sqlite3.sqlite_version  == 3.40.1
GNU Make version               == 4.3
locale charmap                 == UTF-8
Python stdout encoding         resolves to UTF-8
```

These checks record version strings and pass/Boolean results only; they must **not** print
repository, source, or lexical content. `make` and the extraction command run **only after
every assertion has passed**.

## 10. Approved Two-Independent-Build Protocol
```text
Label: CONDITIONAL FUTURE APPROVAL / FUTURE EXECUTION REQUIREMENT
```
The two builds must share **identity** but never share **state**:

- two **independently cloned** source trees (§7);
- both trees **clean** before `make`;
- the **same** canonical image digest;
- the **same** platform flag (`linux/arm64`);
- the **same** environment variables (§9);
- the **same** build command (`make`);
- the **same** extraction command (§3/§9);
- **separate** source directories;
- **separate** output directories;
- **no copying** of `scowl.db` or generated output between builds;
- **no reuse** of one checkout for both builds;
- **no host-side modification** of either source tree before execution.

The two output files must then be compared using **SHA-256** and **exact byte equality**:

- matching line counts alone are **insufficient**;
- matching semantic sets alone are **insufficient**;
- **exact bytes must match.**

## 11. Approved Notice-Preservation Procedure
```text
Label: CONDITIONAL FUTURE APPROVAL / FUTURE EXECUTION REQUIREMENT
No notice bytes are copied or hashed in this branch.
```
Approved future sequence:

1. verify **both** source checkouts resolve to `EXPECTED_COMMIT`;
2. locate `Copyright` at the repository root in **each** checkout;
3. compute SHA-256 for **both** checkout copies;
4. require the two source-notice hashes to **match**;
5. copy the bytes from one verified checkout into **`promotion-staging/`** as
   `SCOWL-COPYRIGHT.txt` (the notice is first copied and verified **inside
   `promotion-staging/`**, **not** written directly into the final bundle);
6. perform the copy **without** decoding, normalizing, re-encoding, or rewriting the text
   (no wording, formatting, or line-ending changes);
7. compute the staged-copy SHA-256;
8. require `source notice hash == staged notice hash`;
9. require an **exact byte comparison** in addition to hash equality;
10. keep the notice **separate** from lexical entries, **adjacent** to the staged wordlist
    in `promotion-staging/`; it reaches the final bundle only via the atomic promotion
    in §14.

Preserving the complete upstream file verbatim is a **project preservation policy**. It
is **not** an independent legal determination and **not** a claim about the minimum
legally required notice.

## 12. Approved Byte-Identity and Hash Procedure
```text
Label: FUTURE EXECUTION REQUIREMENT
```
Hashes to compute during future execution (local only):

```text
build_1_artifact_SHA256          SHA-256 of build-1 output wordlist
build_2_artifact_SHA256          SHA-256 of build-2 output wordlist
artifact_SHA256                  the shared value, required to equal both of the above
byte_identity_result             true iff build-1 and build-2 outputs are byte-identical

build_1_notice_source_SHA256     SHA-256 of Copyright in build-1 checkout
build_2_notice_source_SHA256     SHA-256 of Copyright in build-2 checkout
notice_source_SHA256             the shared value, required to equal both of the above
preserved_notice_SHA256          SHA-256 of the staged/preserved SCOWL-COPYRIGHT.txt
notice_byte_identity_result      true iff staged/preserved notice == verified source notice
```

Required equalities before any promotion (§14):

```text
build_1_artifact_SHA256 == build_2_artifact_SHA256 == artifact_SHA256
byte_identity_result == true (exact bytes match, not merely equal hashes)
build_1_notice_source_SHA256 == build_2_notice_source_SHA256 == notice_source_SHA256
preserved_notice_SHA256 == notice_source_SHA256
notice_byte_identity_result == true
```

All hashes and comparisons are computed on **local, Git-ignored** files only.

## 13. Approved Aggregate Structural Checks
```text
Label: FUTURE EXECUTION REQUIREMENT — content-free
```
A future checker must print **counts and Boolean results only**. It must **never** print
lexical entries, examples, first/last lines, or failed tokens.

Record, at minimum:

```text
artifact byte count
SHA-256
UTF-8 decode success (bool)
file ends with LF (bool)
carriage-return byte count
NUL-byte count
total line count
unique line count
duplicate count
blank-line count
leading/trailing-whitespace line count
lines containing spaces or tabs
lines containing ASCII digits
lines containing ASCII hyphen-minus
adjacent out-of-order pair count
strictly sorted (bool)
nonempty (bool)
```

Required approval outcomes:

```text
UTF-8 decode succeeds                         == true
final LF present                              == true
carriage-return count                         == 0
NUL count                                     == 0
line count                                    >  0
duplicate count                               == 0
blank-line count                              == 0
leading/trailing-whitespace count             == 0
space-or-tab line count                       == 0
ASCII-digit line count                        == 0
ASCII-hyphen line count                       == 0
out-of-order pair count                       == 0
unique line count                             == total line count
```

Note: there is **no** broad ASCII-only restriction — diacritics are preserved and
internal apostrophes are permitted, so non-ASCII letters and apostrophes are expected and
allowed. The checker must **not** print any lexical content.

## 14. Approved Artifact-Promotion Procedure
```text
Label: CONDITIONAL FUTURE APPROVAL — conditional local artifact placement only
```
Promotion is **atomic and non-destructive**. The candidate bundle is fully assembled and
verified inside `promotion-staging/`, and a **single atomic rename** moves it into the
final path. No file is ever written piecemeal into the final bundle.

**Start-state preconditions (both must hold):**

1. the final bundle path
   `data/resources/local_lexicons/english/english_scowl_esdb_en_us/` **does not already
   exist** — an existing final bundle is an **immediate stop condition** (§17);
2. the `promotion-staging/` path **does not already exist** at the start (§7/§17).

**Assemble the candidate inside `promotion-staging/`:**

3. place all three candidate files in `promotion-staging/`:
   - `scowl_en_US_size60_var1.txt` (build-1 output, after §10/§12 byte-identity);
   - `SCOWL-COPYRIGHT.txt` (verified notice from §11);
   - `provenance.json` (§15).

**Verify the staged bundle (all must pass):**

4. both source pins verify (§7/§8);
5. both in-container environment assertions passed (§9);
6. both builds finished successfully;
7. both generated wordlist hashes match and exact output **bytes** match (§10/§12);
8. both source `Copyright` hashes match, and the staged notice hash **and** bytes match
   the verified source notice (§11/§12);
9. the staged artifact and notice hashes are **recomputed** from the files now in
   `promotion-staging/`;
10. all aggregate structural checks (§13) are **rerun on the staged artifact** and pass;
11. the staged `provenance.json` **validates against the approved schema** (§15);
12. exactly the **three required files** are present in `promotion-staging/` — **no extra
    files** are allowed;
13. the final bundle path is confirmed **Git-ignored** (§7).

**Promote atomically (`FUTURE EXECUTION REQUIREMENT`):**

14. only after **every** check above passes, promote with a **single same-filesystem
    directory rename** — net effect:

```text
data/resources/local_lexicons/_work/english_scowl_esdb_en_us/promotion-staging/
  →  data/resources/local_lexicons/english/english_scowl_esdb_en_us/
```

    a. ensure the final parent directory `data/resources/local_lexicons/english/` exists
       (created per §7, only after `PROJECT_ROOT` resolution, beneath-`local_lexicons/`
       verification, and `git check-ignore`);
    b. require the `promotion-staging/` directory and the final parent directory
       `data/resources/local_lexicons/english/` to be on the **same filesystem/device**;
    c. **recheck immediately before the rename** that the final bundle path
       `data/resources/local_lexicons/english/english_scowl_esdb_en_us/` **does not
       exist**;
    d. define and **export** absolute paths beneath the resolved `PROJECT_ROOT` (they must
       be **exported** so the child Python process inherits them via `os.environ`;
       unexported shell variables are **not** inherited by the child process):

```bash
export PROMOTION_STAGING="$PROJECT_ROOT/data/resources/local_lexicons/_work/english_scowl_esdb_en_us/promotion-staging"
export FINAL_PARENT="$PROJECT_ROOT/data/resources/local_lexicons/english"
export FINAL_BUNDLE="$PROJECT_ROOT/data/resources/local_lexicons/english/english_scowl_esdb_en_us"
```

    e. then perform a local check/rename **equivalent to** the following (future procedure
       text only; **not executed in this branch**):

```bash
python - <<'PY'
import os
from pathlib import Path

src = Path(os.environ["PROMOTION_STAGING"])
parent = Path(os.environ["FINAL_PARENT"])
dst = Path(os.environ["FINAL_BUNDLE"])

# Preconditions.
if not src.is_dir():
    raise SystemExit("promotion staging directory is absent")
if not parent.is_dir():
    raise SystemExit("final parent directory is absent")
if dst.exists() or dst.is_symlink():
    raise SystemExit("final bundle already exists")
if src.stat().st_dev != parent.stat().st_dev:
    raise SystemExit("staging and final parent are on different devices")

# The execution branch must hold EXCLUSIVE control of PROMOTION_STAGING and
# FINAL_BUNDLE during this interval; no concurrent process may create, replace,
# rename, or otherwise modify either path. Repeat the destination-absence and
# same-device checks immediately before the rename.
if dst.exists() or dst.is_symlink():
    raise SystemExit("final bundle appeared just before rename")
if src.stat().st_dev != parent.stat().st_dev:
    raise SystemExit("staging and final parent are on different devices")

# Any exception here -- not only SystemExit -- is a promotion failure; do not retry.
os.rename(src, dst)
PY
```

Requirements for this operation (`FUTURE EXECUTION REQUIREMENT`):

- `PROMOTION_STAGING` must equal the approved `promotion-staging` path
  `data/resources/local_lexicons/_work/english_scowl_esdb_en_us/promotion-staging/`;
- `FINAL_PARENT` must equal `data/resources/local_lexicons/english/`;
- `FINAL_BUNDLE` must equal
  `data/resources/local_lexicons/english/english_scowl_esdb_en_us/`;
- the three variables must be **exported** so the child Python process inherits them via
  `os.environ`;
- all three paths must first pass the `PROJECT_ROOT` containment and `git check-ignore`
  requirements (§7);
- the execution branch must have **exclusive control** of `PROMOTION_STAGING` and
  `FINAL_BUNDLE` during the final validation and rename;
- **no concurrent process** may create, replace, rename, or otherwise modify either path
  during that interval;
- immediately before `os.rename`, the block must **repeat** the destination-absence and
  same-device checks;
- `os.rename` is used **specifically to avoid** a recursive-copy or cross-filesystem
  fallback — it raises rather than silently copying across devices;
- **any exception** from `os.rename` — not only `SystemExit` — must be treated as a
  promotion failure;
- **any failed precondition or exception from `os.rename` aborts promotion and is a stop
  condition**;
- on failure, **do not retry** with `mv`, copying, overwrite, or any other fallback (no
  `mv`, `shutil.copytree`, recursive copying, piecemeal copying, overwrite, or
  cross-filesystem behavior is approved).

**`os.rename` does not itself provide a no-replace flag.** The non-destructive guarantee
here depends on:

- the destination-absence checks (the initial check and the repeat immediately before the
  rename);
- **exclusive control** of the relevant local paths;
- the **same-filesystem** requirement;
- the **prohibition on fallback or retry** behavior.

Because the rename preserves bytes, the final artifact and notice hashes equal the verified
staged hashes.

**Non-destructive guarantees:**

- an **existing final bundle is an immediate stop condition** (§17) — this procedure never
  overwrites it;
- **replacement or overwrite of an existing final bundle requires a separate future
  approval** and is **not** granted here;
- **no partial final bundle may remain after a failure** — on failure nothing is renamed
  into the final path, and the incomplete staging directory is handled per §18;
- **in-place overwriting and piecemeal copying into the final path are not approved** —
  only the single atomic rename of a fully-verified staging directory is.

This is **conditional local artifact placement**. It is **not** loader approval, dry-run
approval, validation approval, clean-promotion approval, dataset approval, tokenizer
approval, or model-training approval.

## 15. Provenance JSON Schema
```text
Label: PROJECT POLICY DECISION (schema) / FUTURE EXECUTION REQUIREMENT (population)
```
`provenance.json` must be **local and Git-ignored** and must contain **no CALLHOME
material and no lexical entries**. Deterministic serialization is required:

- valid UTF-8 JSON;
- two-space indentation;
- **lexicographic key ordering**;
- equivalent to `json.dump(..., sort_keys=True, indent=2, ensure_ascii=False)`;
- followed by exactly **one** trailing LF;
- **no provenance self-hash** (a file cannot contain its own hash).

Required fields and types:

```text
schema_version                      integer   (initial value: 1)
resource_id                         string    "english_scowl_esdb_en_us"
resource_family                     string    "Direct SCOWL / English Speller Database (ESDB)"
artifact_model                      string    "source-generated plain wordlist"
upstream_repository                 string    "https://github.com/en-wl/wordlist.git"
release_tag                         string    "rel-2026.02.25"
immutable_commit                    string    full 40-character commit
dialect                             string    "A"
size                                integer   60
variant_level                       integer   1
category_policy                     string    "--categories="
POS_filter_policy                   array[str] ["--wo-poses=abbr", "--wo-pos-categories=nonword,wordpart"]
exact_build_command                 string    "make"
exact_extraction_command            string    complete approved extraction command
canonical_platform                  string    "linux/arm64/v8"
docker_platform_flag                string    "linux/arm64"
container_repository                string    "docker.io/library/python"
container_tag                       string    "3.12.13-bookworm"
multi_platform_index_digest         string    full selected index digest
platform_specific_container_digest  string    full selected arm64 digest
canonical_container_reference       string    full repository@digest reference
Python_implementation               string    "CPython"
Python_version                      string    "3.12.13"
SQLite_version                      string    "3.40.1"
build_tool                          string    "GNU Make"
build_tool_version                  string    "4.3"
locale                              string    "C.UTF-8"
output_encoding                     string    "UTF-8"
line_endings                        string    "LF"
artifact_filename                   string    "scowl_en_US_size60_var1.txt"
build_1_source_commit               string
build_2_source_commit               string
build_1_environment                 object    actual observed environment from build 1 (fields below)
build_2_environment                 object    actual observed environment from build 2 (fields below)
build_1_succeeded                   boolean
build_2_succeeded                   boolean
build_1_artifact_SHA256             string
build_2_artifact_SHA256             string
artifact_SHA256                     string
byte_identity_result                boolean
notice_source_filename              string    "Copyright"
notice_source_tag                   string    "rel-2026.02.25"
notice_source_commit                string
build_1_notice_source_SHA256        string
build_2_notice_source_SHA256        string
notice_source_SHA256                string
preserved_notice_filename           string    "SCOWL-COPYRIGHT.txt"
preserved_notice_SHA256             string
notice_byte_identity_result         boolean
notice_preservation_policy          string    "complete_authoritative_upstream_file_verbatim"
build_1_structural_checks           object    all required aggregate structural checks for build 1 (§13)
build_2_structural_checks           object    all required aggregate structural checks for build 2 (§13)
final_artifact_structural_checks    object    structural checks rerun on the promotion-staging artifact (§13/§14)
promotion_staging_validated         boolean
generation_date_utc                 string    UTC ISO-8601 form
procedure_document                  string    "docs/callhome_english_scowl_operationalization_approval.md"
procedure_commit                    string    merged procedure commit used by the execution branch
```

The `build_1_environment` and `build_2_environment` objects must each record the **actual
observed values** from that execution (not merely the expected constants):

```text
canonical_container_reference   string    full repository@digest reference actually used
architecture                    string    observed uname -m (expected aarch64)
operating_system_id             string    observed /etc/os-release ID (expected debian)
operating_system_version        string    observed /etc/os-release VERSION_ID (expected 12)
Python_implementation           string    observed (expected CPython)
Python_version                  string    observed (expected 3.12.13)
SQLite_version                  string    observed sqlite3.sqlite_version (expected 3.40.1)
build_tool                      string    observed (expected GNU Make)
build_tool_version              string    observed (expected 4.3)
locale_charmap                  string    observed locale charmap (expected UTF-8)
Python_output_encoding          string    observed stdout encoding (expected UTF-8)
verification_passed             boolean   true iff every environment assertion passed
```

These environment objects must contain the **observed** values recorded during build 1 and
build 2 respectively; they must **not** be back-filled with the expected constants if an
observation differs (a difference is a stop condition, §9/§17). The top-level fields above
(`Python_version`, `SQLite_version`, etc.) record the **expected canonical** values; the
per-build environment objects record what was **actually observed**.

The provenance file itself remains **local and is not approved for Git tracking**. It must
**not** contain a hash of itself (a self-hash would be circular).

## 16. Approval Criteria
```text
Label: FUTURE EXECUTION REQUIREMENT
```
The future artifact becomes eligible for a **later artifact-approval review** only when:

- exact source verification passes **twice**;
- exact environment verification passes **twice**;
- both builds succeed;
- artifact SHA-256 values match;
- artifact **bytes** match;
- all aggregate structural checks pass;
- notice source hashes match;
- preserved notice hash **and** bytes match the source notice;
- `provenance.json` validates against the approved schema (§15);
- all final paths remain **Git-ignored**;
- `git status` exposes **no** resource files;
- **no** CALLHOME material influenced or entered the process.

Passing these checks **does not itself approve loader use** — that remains a separate,
closed gate.

## 17. Failure and Stop Conditions
```text
Label: FUTURE EXECUTION REQUIREMENT
```
The execution branch must **stop immediately** if any of the following occurs:

- branch or repository state is unexpected;
- any required fresh work path already exists (build-1/2 `source` or `output`, or
  `promotion-staging`) — stale directories or files must not be reused;
- the final bundle path already exists (it must never be overwritten here);
- an intended path is not beneath `data/resources/local_lexicons/`, or `git check-ignore`
  does not confirm it is Git-ignored;
- a stale `scowl.db`, prior wordlist, prior notice, prior `provenance.json`, or prior
  build output would be reused;
- the official upstream URL differs;
- the tag does not resolve **exactly** to the expected commit
  (`git rev-parse "refs/tags/${RELEASE_TAG}^{commit}"`);
- either checkout `HEAD` differs from the expected commit;
- either source tree is dirty (modified or untracked) before `make`;
- the exact canonical digest reference cannot be inspected or pulled
  (`--platform linux/arm64`), remains unavailable after the permitted pull, or the
  inspected image reports a platform other than `linux/arm64` (§9 preflight);
- canonical environment versions differ (arch/OS/Python/SQLite/Make/locale/encoding);
- the build requires network access;
- either `make` or extraction fails;
- output hashes differ;
- output bytes differ;
- structural checks fail;
- `promotion-staging/` contains any file other than the three required candidate files;
- the staged `provenance.json` does not validate against the approved schema (§15);
- the `promotion-staging/` directory and the final parent directory
  `data/resources/local_lexicons/english/` are not on the same filesystem/device, or a
  same-filesystem atomic rename cannot be guaranteed;
- the final bundle path exists on the immediate pre-rename recheck (§14);
- the upstream `Copyright` files differ between checkouts;
- preserved notice bytes differ from the verified source notice;
- the local root is not Git-ignored;
- any resource file appears in `git status`;
- any CALLHOME path is mounted or accessed;
- lexical content would be printed or committed;
- provenance would contain transcript or lexical content;
- loader use, CALLHOME validation, clean promotion, condition construction, tokenizer
  work, or model training is proposed in the same execution step.

**No failed artifact may be promoted to the final bundle.**

## 18. Cleanup and Local-Retention Policy
```text
Label: PROJECT POLICY DECISION
```
On **success**:

- retain the final local bundle;
- retain `provenance.json` locally;
- retain the **build-1 and build-2 directories under `_work/`** until the local
  artifact-approval review completes;
- after artifact approval, those `_work/` build directories **may** be deleted;
- do **not** delete the final bundle automatically;
- do **not** commit any local artifact, notice, provenance, log, or hash.

After a successful atomic promotion (§14), **`promotion-staging/` no longer exists under
`_work/`** — that directory has *become* the final bundle via the same-filesystem rename,
so only `build-1/` and `build-2/` remain under `_work/`.

On **failure**:

- do **not** create or update the final bundle;
- retain failed `_work/` directories locally **only** if needed for diagnosis;
- do **not** expose lexical content during diagnosis;
- delete failed `_work/` directories once diagnosis is complete;
- record only **aggregate, non-lexical** conclusions in any later repository document.

**Repository-result disclosure boundary (`PROJECT POLICY DECISION`).** Regardless of
success or failure:

- full artifact SHA-256 values remain **local**;
- full notice SHA-256 values remain **local**;
- `provenance.json` remains **local**;
- full local logs remain **local**.

A future **committed** execution record may contain **only**:

- aggregate structural counts;
- source and environment identities already approved for disclosure (upstream URL, tag,
  commit, container reference/digests, platform, Python/SQLite/Make versions, locale,
  encoding);
- equality results;
- pass/fail Booleans.

It must **not** contain:

- lexical entries;
- notice text;
- local paths containing personal information;
- full local logs;
- `provenance.json`;
- full artifact SHA-256 values;
- full notice SHA-256 values —

unless a later approval **explicitly** authorizes committing those hashes.

## 19. Decision Matrix
| Decision or gate | Status |
| ---------------- | ------ |
| Operationalization procedure | YES / APPROVED FOR FUTURE CONTROLLED EXECUTION |
| Source checkout in this branch | NO / NOT EXECUTED |
| Docker execution in this branch | NO / NOT EXECUTED |
| SCOWL build in this branch | NO / NOT EXECUTED |
| Wordlist extraction in this branch | NO / NOT EXECUTED |
| Notice retrieval in this branch | NO / NOT EXECUTED |
| Hash computation in this branch | NO / NOT EXECUTED |
| Directory creation in this branch | NO / NOT EXECUTED |
| Future controlled source checkout | CONDITIONALLY APPROVED UNDER THIS PROCEDURE |
| Future controlled canonical Docker execution | CONDITIONALLY APPROVED UNDER THIS PROCEDURE |
| Future two-build test | CONDITIONALLY APPROVED UNDER THIS PROCEDURE |
| Future local artifact placement | CONDITIONALLY APPROVED ONLY AFTER ALL CHECKS PASS |
| Artifact approved | NO / REQUIRES LATER REVIEW |
| Loader use | NO / REMAINS CLOSED |
| Aggregate CALLHOME dry run | NO / REMAINS CLOSED |
| Real CALLHOME validation | NO / REMAINS CLOSED |
| Clean promotion | NO / REMAINS CLOSED |
| Condition construction | NO / REMAINS CLOSED |
| Tokenizer training | NO / REMAINS CLOSED |
| Model training | NO / REMAINS CLOSED |
| Git tracking of artifact | NO / REMAINS CLOSED |
| Git tracking of notice | NO / REMAINS CLOSED |
| Git tracking of provenance | NO / REMAINS CLOSED |

## 20. Current Pipeline State
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

## 21. Safety and Routing State
```text
CALLHOME English
→ potentially EnglishMono
→ potentially the English portion of MonoCont
→ never CsCont

CALLHOME Spanish
→ potentially SpanishMono
→ potentially the Spanish portion of MonoCont
→ never CsCont

Bangor Miami
→ CsCont only
```

- **No CALLHOME content was inspected or accessed.**
- **CALLHOME-derived material must never shape, filter, expand, normalize, or influence
  the SCOWL artifact.**
- **CALLHOME never feeds CsCont; Bangor Miami remains CsCont-only.**
- **Only future clean English CALLHOME rows may eventually feed EnglishMono and MonoCont**
  — routing that remains **separately gated and is not approved here**.
- **No SCOWL source was downloaded; no build was run; no artifact, notice, or hash was
  produced; no directory was created.**
- **The real pipeline remains on conservative default validation; all rows remain blocked
  from conditions.**
- **No Spanish resource or locale decision changes in this branch.**
- **The `.gitignore` is unchanged**; `data/resources/local_lexicons/` is already ignored
  (`VERIFIED REPOSITORY OBSERVATION`).

## 22. Next Step
The next branch should be a **controlled execution branch**, proposed name:

```text
callhome-english-scowl-canonical-artifact-build
```

That later branch may execute **only** the approved operationalization procedure. It must:

- create local, Git-ignored `_work/` paths;
- perform two independent source checkouts;
- verify both source pins;
- run two canonical **offline** container builds;
- compute local hashes;
- run aggregate, content-free structural checks;
- preserve the notice verbatim;
- create the final local bundle **conditionally** (only after all checks pass);
- write local `provenance.json`;
- produce a repository documentation record containing **only aggregate, non-lexical
  results**.

It must **not**:

- wire the loader;
- access CALLHOME;
- run CALLHOME validation;
- promote rows;
- construct condition datasets;
- train tokenizers;
- train models;
- commit the generated artifact, notice, provenance, or any lexical content.

The future committed execution record produced by that branch may contain **only**
aggregate structural counts, already-approved source and environment identities, equality
results, and pass/fail Booleans (per §18). It must **not** commit lexical entries, notice
text, personal-information paths, full local logs, `provenance.json`, or full artifact or
notice SHA-256 values — unless a later approval **explicitly** authorizes committing those
hashes. In particular, **full artifact and notice SHA-256 values, `provenance.json`, and
full local logs remain local.**

Until that separate branch executes and passes every check above, no build has been run,
no artifact exists, byte-identity is **not demonstrated**, artifact approval **requires a
later review**, and every downstream pipeline gate **remains closed**.
