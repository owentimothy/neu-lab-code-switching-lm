# CALLHOME English SCOWL Notice-Bundle Decision

## Status / Decision
```text
English direct-SCOWL notice-bundle decision:
YES / RECORDED

Selected notice-preservation bundle:
VERBATIM FULL UPSTREAM COPYRIGHT FILE AT THE SELECTED PIN

Selected upstream notice source:
the complete official upstream file named "Copyright" at the
selected commit

Notice preservation policy:
PRESERVE VERBATIM / NO EDITING OR TRUNCATION

Notice bundle approved for continued governance:
YES / POLICY APPROVED

Independent legal approval:
NO / NOT PROVIDED

Operational resource generation:
NO / NOT APPROVED
```

This is a **repository governance record, not legal advice.** It closes the English
notice-preservation-bundle decision for continued governance. It does **not**
approve or perform any operational step: no resource generation, source checkout,
container work, notice retrieval/saving, hashing, loading, or CALLHOME validation.

- **No CALLHOME transcript content or CALLHOME-derived lexical evidence was inspected
  or used.**
- **No source, resource, notice file, or container was downloaded or saved; no
  resource directory or metadata file was created; no hash was computed; no build or
  extraction occurred.**
- **Upstream inspection was read-only** at the exact selected pin and is distinguished
  below from prior repository-recorded interpretation.
- **No Spanish resource or locale decision changed.**
- **The real pipeline remains unchanged** (`default_source_validation` only;
  validator/loader not wired into `scripts/summarize_callhome_projection_local.py`).
  Every real CALLHOME row stays `not_validated`; `clean` stays zero.
- **All operational approvals remain `NO / NOT APPROVED`.**

## Existing Decision State (not reopened)
The following already-merged decisions are carried forward unchanged:

```text
Selected English resource family: Direct SCOWL / English Speller Database
Selected artifact model:          Model 1 — source-generated plain wordlist
Resource ID:                      english_scowl_esdb_en_us
Release tag:                      rel-2026.02.25
Immutable commit:                 7e99edab8e32f9f9ea2b15f249ca8d4d67237410
Dialect:                          A — American
Size:                             60
Variant level:                    1
Resource selection:               YES / SELECTED FOR CONTINUED GOVERNANCE
Operational resource use:         NO / NOT APPROVED
```

Selected extraction-command identity (unchanged, not altered here):
```bash
PYTHONIOENCODING=utf-8 \
./scowl --db scowl.db word-list 60 A 1 \
  --categories= \
  --wo-poses=abbr \
  --wo-pos-categories=nonword,wordpart
```

## Upstream Notice-Source Identity

### DIRECT UPSTREAM EVIDENCE AT THE PIN
A narrow, read-only inspection of the official `en-wl/wordlist` top-level directory
listing at commit `7e99edab8e32f9f9ea2b15f249ca8d4d67237410` (tag `rel-2026.02.25`)
establishes:

- a file named **`Copyright`** is **present** at the repository root;
- **no** `COPYING`, `LICENSE`, `LICENSE.txt`, `LICENSE.md`, or `NOTICE` file exists at
  the root;
- documentation is in `README.md`.

The directory listing directly establishes that the root file named `Copyright`
exists at the selected pin and fixes its exact upstream filename. Its role as the
authoritative notice source for this project is supported by the prior
repository-recorded direct review of that file's contents; the directory listing
alone does not establish legal meaning or applicability.

### PRIOR REPOSITORY-RECORDED INTERPRETATION
Prior repository records (`docs/callhome_english_scowl_candidate_evidence.md`,
`docs/callhome_english_scowl_build_environment_evidence.md`,
`docs/callhome_english_lexicon_resource_selection_reassessment.md`) record the
content of that `Copyright` file: a primary Kevin Atkinson copyright + permission
notice covering **SCOWLv2 and word lists created from it**, followed by separate
component notices (Australian/Titze, UKACD/Beresford, WordNet, COCA, 12dicts/ENABLE2K),
and a conditional stating that a **non-Australian** official speller dictionary needs
only the notice before the `===`, with UKACD material entering only in generated
word lists **larger than size 80**. Those content facts are cited as prior
repository-recorded interpretation and are **not** re-adjudicated here.

## Notice-Preservation Decision
> The project conservatively elects to preserve the complete authoritative upstream
> notice file verbatim. This preservation decision is broader than a claim about the
> minimum legally required subset.

The project selects the **complete authoritative upstream `Copyright` file** as the
notice-preservation bundle even if a narrower component-specific notice (for example,
the primary Atkinson notice alone) might ultimately be legally sufficient. This
conservative repository policy is intended to:

- avoid accidentally omitting an applicable component notice;
- preserve the upstream wording exactly;
- avoid making the project depend on a contested minimal-notice interpretation;
- retain a clear audit trail tied to the selected source pin.

Careful limits:

- This decision **does not claim** that every notice inside the complete `Copyright`
  file necessarily applies to the selected generated output.
- This decision **does not claim** that the full file is legally mandatory.
- **No independent legal determination is made.**

## Notice-Bundle Contents

### 1. Verbatim upstream notice file
The complete authoritative upstream notice file from:
```text
tag:    rel-2026.02.25
commit: 7e99edab8e32f9f9ea2b15f249ca8d4d67237410
file:   Copyright
```
Requirements (future, upon separately approved retrieval):

- retrieve the raw file bytes from the immutable pinned commit, not rendered webpage
  text;
- compute and record the SHA-256 of the retrieved upstream notice bytes;
- preserve the local copy **byte-for-byte**;
- compute the local preserved-copy SHA-256 and require equality with the source-notice
  SHA-256;
- **no** wording changes;
- **no** removal of sections;
- **no** reformatting;
- **no** generated project commentary inserted into the notice file;
- retained **locally with the future resource artifact**;
- kept **separate from the generated lexical entries**.

Byte-for-byte preservation is a **future requirement**; it is **not demonstrated in
this branch** because no notice file was retrieved, saved, or hashed.

### 2. Separate project provenance metadata
A separate provenance record must accompany the future artifact. This is **project
metadata, not part of the upstream notice text**. Required future fields (not created
here; values not selected here):

```text
resource_id
resource_family
artifact_model
upstream_repository
release_tag
immutable_commit
dialect
size
variant_level
category_policy
POS_filter_policy
exact_build_command
exact_extraction_command
canonical_platform
container_repository
container_tag
platform-specific_container_digest
Python_implementation
Python_version
SQLite_version
build_tool_version
output_encoding
line_endings
artifact_filename
artifact_SHA256
notice_source_filename
notice_source_tag
notice_source_commit
notice_source_SHA256
preserved_notice_SHA256
notice_byte_identity_result
notice_preservation_policy
generation_date
```

No provenance file is created in this branch, and no unresolved value is selected.

## Filename and Placement Policy
```text
Future preserved notice filename:
SCOWL-COPYRIGHT.txt

Future placement:
adjacent to the generated English wordlist inside the
approved local-only English resource directory

Notice file tracked in Git:
NO / NOT APPROVED

Generated wordlist tracked in Git:
NO / NOT APPROVED

Resource directory creation:
NO / NOT APPROVED
```

Clarifications:

- `SCOWL-COPYRIGHT.txt` is the **project-side future filename** only.
- Its contents must remain the **complete verbatim authoritative upstream notice file**
  (`Copyright` at the pin).
- **Renaming the local copy does not permit editing its contents.**
- The **original upstream filename (`Copyright`) and source identity (tag + commit)
  must be recorded in the provenance metadata**.
- **No filename or placement action occurs in this branch.**
- The **English wordlist artifact filename remains unresolved** (no earlier merged
  decision approved one); it is **not** approved here.

## Relationship to the Proposed Primary Notice
- Prior repository evidence proposed that the selected **American size-60** output may
  map to the **primary Kevin Atkinson notice** pathway.
- That proposal helped establish that **direct SCOWL has a clearer permission pathway**
  than the LibreOffice package.
- This branch **does not need to decide** that the primary notice is the exclusive
  legally required notice.
- The project instead selects the **complete authoritative upstream notice file** as
  its conservative preservation bundle.
- This **does not contradict** the earlier proposed component mapping.
- It **avoids relying operationally** on a minimum-notice interpretation.

```text
Primary-notice component mapping:
SUPPORTED AS A PRIOR GOVERNANCE INTERPRETATION

Exclusive minimum-notice determination:
NOT MADE

Full authoritative notice preservation:
YES / SELECTED AS PROJECT POLICY
```

## Required Distinctions
- **Notice-source identity** — the exact upstream file (`Copyright`) and source commit
  (`7e99edab…`, tag `rel-2026.02.25`) that supply the notice text.
- **Notice preservation** — the project policy to retain that file **verbatim** beside
  the future artifact.
- **Permission-pathway evidence** — the upstream terms (Atkinson permission covering
  word lists created from SCOWLv2) and prior repository evidence supporting continued
  governance.
- **Independent legal approval** — **not supplied by this branch.**
- **Artifact approval** — **still blocked** until the resource is generated
  reproducibly and separately reviewed.
- **Git redistribution approval** — **not supplied by this branch** (neither the
  notice file nor the wordlist is approved for Git tracking).
- **Local operational use** — **not supplied by this branch.**

## Evidence Matrix
| Topic | Evidence | What it establishes | Remaining limitation | Confidence |
| ----- | -------- | ------------------- | -------------------- | ---------- |
| Selected direct-SCOWL resource identity | `docs/callhome_english_lexicon_resource_selection_reassessment.md` | Model 1 / `english_scowl_esdb_en_us` selected for continued governance | governance-only; not operational | DIRECT |
| Authoritative upstream notice-file identity | root listing @ `7e99edab…` | `Copyright` is present; no `COPYING`/`LICENSE*`/`NOTICE` | which components apply to the output not adjudicated | DIRECT |
| Notice coverage of SCOWLv2 | `Copyright` @ pin (prior direct read) | permission covers "any part of SCOWLv2" | legal sufficiency not determined | DIRECT |
| Notice coverage of generated wordlists | `Copyright` @ pin (prior direct read) | permission covers "word lists created from it" | legal sufficiency not determined | DIRECT |
| Prior primary-notice component mapping | candidate-evidence / build-env / reassessment records | American ≤80 proposed to map to the primary Atkinson notice | a governance interpretation, not a legal ruling | STRONG |
| Complete-file preservation policy | this decision | full `Copyright` file selected for verbatim preservation | broader than any minimum-notice claim | DIRECT |
| Verbatim-preservation requirement | this decision | future copy preserved byte-for-byte, unedited | not demonstrated (no retrieval) | DIRECT |
| Future provenance metadata requirement | this decision | separate provenance record required with listed fields | file not created; values unselected | DIRECT |
| Independent legal approval | this decision | no independent legal determination is made | legal sufficiency unestablished | LIMITED |
| Git redistribution approval | this decision | neither notice nor wordlist approved for Git tracking | separate future decision | DIRECT |
| Operational artifact approval | this decision + build-env contract | artifact remains blocked pending reproducible generation + review | not executed | DIRECT |

(Legal sufficiency is deliberately **not** labeled `DIRECT`.)

## Notice-Bundle Matrix
| Bundle component | Future content | Source identity | Preservation rule | Status |
| ---------------- | -------------- | --------------- | ----------------- | ------ |
| Authoritative upstream notice | complete verbatim `Copyright` file | `en-wl/wordlist` `Copyright` @ `rel-2026.02.25` / `7e99edab…` | retrieve raw pinned bytes; preserve verbatim; require source-hash == preserved-copy hash; adjacent; separate from entries | SELECTED FOR FUTURE PRESERVATION |
| Project provenance metadata | the listed provenance fields, including source-notice hash, preserved-copy hash, and notice byte-identity result | project-authored (not upstream) | separate from the notice; records upstream filename + pin | POLICY RESOLVED |
| Generated English wordlist | size-60 `A` variant-1 output | generated from the selected pin | local-only, gitignored; never edited into the notice | NOT EXECUTED |
| Artifact SHA-256 record | digest of the generated artifact | computed post-generation | recorded in provenance; local | NOT EXECUTED |
| Build-environment record | canonical digest + two-build byte test | `docs/callhome_english_scowl_build_environment_evidence.md` | reproducibility contract (blocking gate) | POLICY RESOLVED |

## Decision Matrix
| Decision or gate | Status |
| ---------------- | ------ |
| Notice-bundle evidence reviewed | YES / RECORDED |
| Authoritative upstream notice source identified | YES / RECORDED |
| Full authoritative notice preservation selected | YES / SELECTED FOR FUTURE PRESERVATION |
| Verbatim preservation required | YES / POLICY RESOLVED |
| Future notice filename selected | YES / POLICY RESOLVED |
| Future adjacent-placement policy selected | YES / POLICY RESOLVED |
| Project provenance metadata required | YES / POLICY RESOLVED |
| Primary-notice mapping reviewed | YES / RECORDED |
| Exclusive minimum-notice determination made | NO / NOT MADE |
| Independent legal approval provided | NO / NOT PROVIDED |
| Git tracking of notice approved | NO / NOT APPROVED |
| Git tracking of generated wordlist approved | NO / NOT APPROVED |
| Resource directory creation approved | NO / NOT APPROVED |
| Canonical container selected | NO |
| Canonical platform selected | NO |
| Canonical Python selected | NO |
| Canonical SQLite selected | NO |
| SCOWL source checkout approved | NO / NOT APPROVED |
| Container pull/build approved | NO / NOT APPROVED |
| SCOWL build approved | NO / NOT APPROVED |
| Wordlist extraction approved | NO / NOT APPROVED |
| Notice retrieval approved | NO / NOT APPROVED |
| Local placement approved | NO / NOT APPROVED |
| Hash computation approved | NO / NOT APPROVED |
| Two-build byte identity demonstrated | NO |
| Artifact approved | NO / NOT APPROVED |
| Loader use approved | NO / NOT APPROVED |
| Aggregate dry run approved | NO / NOT APPROVED |
| Real CALLHOME validation approved | NO / NOT APPROVED |
| Clean promotion approved | NO / NOT APPROVED |
| Condition construction approved | NO / NOT APPROVED |
| Tokenization approved | NO / NOT APPROVED |
| Model training approved | NO / NOT APPROVED |

## Current English Governance State
```text
English resource family:
DIRECT SCOWL / ESDB — SELECTED

Source-artifact model:
MODEL 1 SOURCE-GENERATED PLAIN WORDLIST — SELECTED

Release tag and immutable commit:
SELECTED

Dialect / size / variant:
SELECTED

Extraction-policy identity:
SELECTED

Proper-name policy:
RESOLVED

Reproducibility contract:
RESOLVED

Notice-preservation bundle:
RESOLVED BY THIS BRANCH

Operational generation:
NO / NOT APPROVED
```

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
→ never CsCont

CALLHOME Spanish
→ potentially SpanishMono
→ potentially the Spanish portion of MonoCont
→ never CsCont

Bangor Miami
→ CsCont only
```

- **No CALLHOME content or CALLHOME-derived evidence was inspected.**
- **No source or resource was downloaded.**
- **No notice file was saved.**
- **No resource directory was created.**
- **No hash was computed.**
- **No build or extraction occurred.**
- **No Spanish resource or locale decision changed.**
- **The real pipeline remains on conservative default validation.**

## Next Step
With the notice-preservation bundle resolved, the remaining open items are the
**canonical container-image digest selection** and recording the exact canonical
Python/SQLite versions from inside that image — still **without executing a build**.
Only a later, separately approved step would perform the two-clean-build
byte-identity test, retrieve and verbatim-preserve the `Copyright` file as
`SCOWL-COPYRIGHT.txt` beside the generated wordlist in a local-only resource
directory, write the provenance metadata, and compute the artifact SHA-256. Until
then, the notice-preservation policy is **RESOLVED** for continued governance and
every operational gate remains **closed**.
