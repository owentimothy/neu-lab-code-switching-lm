# CALLHOME English SCOWL Canonical Artifact Build Record

## 1. Status

```text
Controlled canonical execution:       COMPLETED
Two independent source checkouts:      PASS
Two canonical offline builds:          PASS
Artifact SHA-256 equality:              PASS
Artifact exact byte identity:           PASS
Aggregate structural checks:           PASS
Notice SHA-256 equality:                PASS
Notice exact byte identity:             PASS
Provenance validation:                  PASS
Atomic local promotion:                 PASS
Final local bundle present:             YES
Repository working tree clean:          YES

Repository-level artifact approval:     PENDING / REQUIRES LATER REVIEW
Loader use:                             CLOSED
CALLHOME validation:                    CLOSED
Clean row promotion:                    CLOSED
Condition construction:                 CLOSED
Tokenizer training:                     CLOSED
Model training:                         CLOSED
Git tracking of local bundle contents:  CLOSED
```

This record documents the successful controlled execution of the procedure approved in:

```text
docs/callhome_english_scowl_operationalization_approval.md
```

Procedure merge commit:

```text
2135596f82f302cc169e68b9be8a31f039e66300
```

Execution branch:

```text
callhome-english-scowl-canonical-artifact-build
```

Execution date:

```text
2026-07-14
```

The generated artifact, preserved notice, local provenance file, complete hashes, lexical
entries, and detailed build logs remain local and Git-ignored.

## 2. Scope

This branch executed only the approved English SCOWL artifact-build procedure.

It:

- verified the approved upstream tag and immutable commit;
- created two independent source checkouts;
- verified both source pins and clean detached working trees;
- ran two independent canonical container builds;
- ran both build containers offline;
- extracted the approved English wordlist independently from each build;
- computed local SHA-256 values;
- compared the two outputs by hash and exact bytes;
- ran aggregate, content-free structural checks;
- verified and preserved the complete upstream notice verbatim;
- created and validated local deterministic provenance;
- assembled a complete three-file staging bundle;
- promoted the staging directory through one same-filesystem atomic rename;
- verified the resulting final local bundle.

It did not:

- access CALLHOME;
- inspect or use CALLHOME-derived evidence;
- use CALLHOME data to select, alter, filter, normalize, or expand SCOWL;
- wire the lexicon loader;
- run CALLHOME validation;
- promote any CALLHOME row to `clean`;
- construct condition datasets;
- train a tokenizer;
- train a model;
- commit lexical content;
- commit notice text;
- commit local provenance;
- commit full artifact or notice hashes;
- commit detailed operational logs.

## 3. Approved Source Identity

```text
Resource ID:       english_scowl_esdb_en_us
Resource family:   Direct SCOWL / English Speller Database (ESDB)
Upstream URL:      https://github.com/en-wl/wordlist.git
Release tag:       rel-2026.02.25
Immutable commit:  7e99edab8e32f9f9ea2b15f249ca8d4d67237410
Dialect:           A
Size:              60
Variant level:     1
```

Approved build command:

```text
make
```

Approved extraction policy:

```text
word-list 60 A 1
--categories=
--wo-poses=abbr
--wo-pos-categories=nonword,wordpart
```

## 4. Independent Source Verification

Two fresh source trees were cloned independently from the approved upstream URL.

For both checkouts:

```text
Origin URL matched approved URL:       YES
Release tag resolved to approved SHA:  YES
HEAD matched approved SHA:             YES
Detached HEAD:                         YES
Clean before make:                     YES
No untracked files before make:        YES
```

The two builds used distinct source directories and distinct output directories. No
source tree, generated database, or output artifact was copied or reused between builds.

## 5. Canonical Build Environment

Canonical container reference:

```text
docker.io/library/python@sha256:77747425b0797fccc62b5ced9a4ca7854c7247485c89681c57e48767ed3343d6
```

Canonical platform:

```text
linux/arm64/v8
```

Observed independently in both builds:

```text
Architecture:             aarch64
Operating system ID:      debian
Operating system version: 12
Python implementation:    CPython
Python version:           3.12.13
SQLite version:           3.40.1
Build tool:               GNU Make
Build tool version:       4.3
Locale character map:     UTF-8
Python stdout encoding:   UTF-8
```

Both containers ran with:

```text
--platform linux/arm64
--pull=never
--network none
```

Only the corresponding source and output directories were mounted. No CALLHOME path and
no project repository root were mounted.

## 6. Build Results

```text
Build 1 environment assertions: PASS
Build 1 make:                   PASS
Build 1 extraction:             PASS

Build 2 environment assertions: PASS
Build 2 make:                   PASS
Build 2 extraction:             PASS
```

The upstream build emitted the same nonfatal compound-resolution warnings in both builds.
In each case, `make` completed successfully and the approved extraction command completed
successfully.

Detailed build output remains local and untracked.

## 7. Artifact Reproducibility

```text
Build 1 SHA-256 computed:       YES
Build 2 SHA-256 computed:       YES
Artifact SHA-256 values equal:  YES
Artifact exact bytes equal:     YES
Artifact byte count:            1028745
Artifact total line count:      109035
```

Matching byte and line counts were not treated as sufficient evidence by themselves.
The two independently generated outputs were also required to have matching SHA-256
values and exact byte equality.

The complete SHA-256 value remains local and is intentionally omitted from this
repository record.

## 8. Aggregate Structural Results

The two independently generated artifacts and the final promoted artifact produced the
same aggregate results:

| Check | Result |
|---|---:|
| UTF-8 decode success | true |
| Final LF present | true |
| Artifact byte count | 1028745 |
| Total line count | 109035 |
| Unique line count | 109035 |
| Duplicate count | 0 |
| Blank-line count | 0 |
| Leading/trailing-whitespace line count | 0 |
| Space-or-tab line count | 0 |
| ASCII-digit line count | 0 |
| ASCII-hyphen-minus line count | 0 |
| Carriage-return byte count | 0 |
| NUL-byte count | 0 |
| Adjacent out-of-order pair count | 0 |
| Strictly sorted | true |
| Nonempty | true |

No lexical entries, examples, first or last entries, or failed-token examples were printed
or committed.

## 9. Notice Preservation

The complete upstream root file `Copyright` was verified independently in both source
checkouts.

```text
Build 1 source-notice SHA-256 computed:  YES
Build 2 source-notice SHA-256 computed:  YES
Source-notice SHA-256 values equal:      YES
Source-notice exact bytes equal:         YES
Preserved notice hash matched source:    YES
Preserved notice bytes matched source:   YES
Final notice matched source checkout 1:  YES
Final notice matched source checkout 2:  YES
```

The notice was preserved locally as:

```text
SCOWL-COPYRIGHT.txt
```

The complete notice text and complete SHA-256 value remain local and untracked.

Preserving the complete upstream file verbatim is a project preservation policy. It is
not an independent legal determination or a claim about the minimum legally required
notice.

## 10. Provenance Validation

A local `provenance.json` was created and validated with:

```text
Schema version:                    1
UTF-8 JSON:                        PASS
Lexicographic key ordering:        PASS
Two-space indentation:             PASS
Exactly one trailing LF:           PASS
Approved required fields present:  PASS
Required field types valid:        PASS
Observed per-build environments:   RECORDED
Artifact hash relations valid:     PASS
Notice hash relations valid:       PASS
Structural results valid:          PASS
Provenance self-hash absent:        YES
```

The provenance file records:

- the approved upstream identity;
- the immutable source commit;
- the approved extraction policy;
- the canonical container and platform identities;
- the actual observed environment from each build;
- success results from both builds;
- local artifact and notice hashes;
- exact byte-identity results;
- aggregate structural-check results;
- staging-validation results;
- the procedure document and procedure commit.

The provenance file contains no CALLHOME material and no lexical entries. It remains
local and Git-ignored.

## 11. Staging and Atomic Promotion

Before promotion:

```text
Staging contained exactly three required files:  YES
Unexpected staging files or directories:         NO
Staging and final parent on same device:          YES
Final bundle absent:                              YES
Final bundle path Git-ignored:                    YES
```

The three required files were:

```text
scowl_en_US_size60_var1.txt
SCOWL-COPYRIGHT.txt
provenance.json
```

The staged artifact, notice, and provenance were revalidated immediately before
promotion.

Promotion result:

```text
Final staging file-set validation:           PASS
Final artifact-hash validation:              PASS
Final notice-hash validation:                PASS
Final provenance validation:                 PASS
Final structural validation:                 PASS
Same-filesystem validation:                  PASS
Single same-filesystem os.rename:             PASS
Recursive-copy fallback used:                 NO
Overwrite or replacement used:                NO
Promotion staging absent afterward:           YES
Final local bundle present afterward:         YES
Final bundle required file count:             3
Final local bundle audit:                     PASS
```

Promotion used one same-filesystem directory rename. No file was copied piecemeal into
the final bundle, no existing bundle was overwritten, and no fallback operation was
used.

## 12. Privacy and Repository Boundaries

The repository contains only this aggregate execution record.

The following remain local and Git-ignored:

- generated wordlist;
- preserved notice;
- provenance JSON;
- full artifact SHA-256;
- full notice SHA-256;
- independent source checkouts;
- generated SCOWL databases;
- per-build output directories;
- detailed operational logs.

This execution did not access CALLHOME.

No CALLHOME content, metadata, transcript identifiers, participant information, speaker
identifiers, transcript filenames, tokens, headers, or transcript-derived examples
entered the build process or this record.

No CALLHOME-derived evidence was used to select, alter, filter, normalize, expand, or
otherwise influence the SCOWL artifact.

## 13. Pipeline and Routing State

```text
CALLHOME English
→ potentially EnglishMono after separate validation approval
→ potentially the English portion of MonoCont after separate approval
→ never CsCont

CALLHOME Spanish
→ potentially SpanishMono after separate validation approval
→ potentially the Spanish portion of MonoCont after separate approval
→ never CsCont

Bangor Miami
→ CsCont only
```

The current CALLHOME pipeline state remains unchanged:

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

The existence of the local canonical artifact does not change the eligibility or
validation state of any CALLHOME row.

## 14. Decision and Next Gate

The controlled build execution succeeded, and a reproducible canonical English SCOWL
bundle now exists locally.

The execution demonstrated:

- exact source reproducibility across two independent checkouts;
- canonical environment reproducibility across two offline container builds;
- matching artifact SHA-256 values;
- exact artifact byte identity;
- passing aggregate structural checks;
- matching and byte-identical source notices;
- verbatim notice preservation;
- valid deterministic provenance;
- successful non-destructive atomic local promotion;
- a clean repository boundary.

This execution does not by itself grant repository-level artifact approval or permission
to use the artifact in the CALLHOME validation pipeline.

The next controlled sequence is:

1. review and merge this aggregate execution record;
2. open a separate artifact-approval branch;
3. determine whether the verified local artifact may be approved for later loader use.

Until that separate approval is merged:

```text
Artifact approval:        PENDING
Loader use:               CLOSED
CALLHOME dry run:         CLOSED
CALLHOME validation:      CLOSED
Clean promotion:          CLOSED
Condition construction:   CLOSED
Tokenizer training:       CLOSED
Model training:           CLOSED
```
