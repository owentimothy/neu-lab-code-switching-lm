# CALLHOME English Lexicon Resource-Selection Reassessment

## Status / Decision
```text
English resource-selection reassessment:
YES / RECORDED

Selected English resource for continued governance:
DIRECT SCOWL / ESDB MODEL 1

Resource ID:
english_scowl_esdb_en_us

Source-artifact model:
SOURCE-GENERATED PLAIN WORDLIST

SCOWL / ESDB Model 1 selected:
YES / APPROVED FOR CONTINUED GOVERNANCE

Prior LibreOffice selection:
SUPERSEDED FOR CONTINUED GOVERNANCE

Operational resource use:
NO / NOT APPROVED
```

This is a **repository governance record, not legal advice.** It makes the
**resource-selection decision for continued governance** only. It does **not**
approve or perform any operational action: no legal/notice approval, no container
selection or pull/build, no SCOWL checkout or build, no `scowl.db` or wordlist
generation, no placement, no hash, no loader execution, no CALLHOME validation.

- **No CALLHOME transcript content or CALLHOME-derived lexical evidence was inspected
  or used** to make this decision.
- **No external investigation was performed** — this is a synthesis of already-merged
  repository evidence; no new external source was accessed.
- **No SCOWL/ESDB source, artifact, or container was downloaded, checked out, built,
  generated, created, or saved; no hash was computed.**
- **The real pipeline remains unchanged** (`default_source_validation` only;
  validator/loader not wired into `scripts/summarize_callhome_projection_local.py`).
  Every real CALLHOME row stays `not_validated`; `clean` stays zero.
- **No Spanish resource or locale decision changes in this branch.**
- **All operational approvals remain `NO / NOT APPROVED`.**

## Selected Upstream Identity
```text
Release tag:      rel-2026.02.25
Immutable commit: 7e99edab8e32f9f9ea2b15f249ca8d4d67237410
```

## Selected Candidate Configuration (continued governance)
```text
Dialect:                A — American
Size:                   60
Variant level:          1
Category policy:        default empty SCOWL category only
Abbreviation policy:    exclude POS abbr
POS-category policy:    exclude nonword and wordpart
Open compounds:         excluded
Hyphenated entries:     excluded
Digits:                 excluded
Special-symbol entries: excluded
Internal apostrophes:   permitted
Diacritics:             preserved
Output encoding:        UTF-8
Line endings:           LF
```

## Selected Extraction-Command Identity (continued governance)
```bash
PYTHONIOENCODING=utf-8 \
./scowl --db scowl.db word-list 60 A 1 \
  --categories= \
  --wo-poses=abbr \
  --wo-pos-categories=nonword,wordpart
```

Selecting this **identity** does **not** approve **executing** the command.

## Decision Rationale
Direct SCOWL / ESDB Model 1 is selected over the existing LibreOffice candidate for
the following reasons, synthesized from the merged repository records.

### 1. Clearer upstream permission pathway
- The direct SCOWL evidence (`docs/callhome_english_scowl_candidate_evidence.md`,
  `docs/callhome_english_scowl_build_environment_evidence.md`) records that the
  SCOWLv2 `Copyright` at the pin explicitly addresses **SCOWLv2 and word lists
  generated from it**. The prior governance reading supports a proposed primary
  Kevin Atkinson notice pathway for the selected American size-60 output, but the
  exact notice bundle remains separately unapproved.
- The LibreOffice `en/` package
  (`docs/callhome_english_lexicon_license_applicability_investigation.md`,
  `docs/callhome_lexicon_exact_resource_metadata.md`) contains **overlapping notice
  and license records** — including a package-level GPLv2 `license.txt` coexisting
  with the SCOWL/component notices — whose **file-specific applicability to
  `en_US.dic` and `en_US.aff` remains unresolved (Category C)**.
- This makes **direct SCOWL the clearer candidate for continued governance**.
- Notice preservation and final notice-bundle approval remain separate blocking
  governance gates.
- This is a **governance assessment, not legal advice or an independent legal
  conclusion**. LibreOffice is **not** described as illegal or unusable.

### 2. Better fit for the current loader
- Model 1 produces a **plain wordlist** directly compatible with
  `load_plain_wordlist` (`src/cslm/data/callhome_lexicon_loader.py`).
- The selected extraction model is designed to produce **enumerated surface
  entries**; the artifact has not yet been generated or inspected.
- The current loader reads **raw Hunspell `.dic` entries and strips affix flags**
  after `/`, and it **does not expand `.aff` rules**.
- Because there is no `.aff` expansion, the LibreOffice and official-Hunspell
  alternatives would not expose surface forms obtainable only through the affix
  rules under the current implementation, potentially reducing exact-match
  coverage.
- Model 1 is therefore **technically better aligned** with the conservative
  exact-match validator (`src/cslm/data/callhome_lexicon_validation.py`), which
  matches whole normalized surface tokens.

### 3. Exact source and extraction identity
- A **dated release tag** exists (`rel-2026.02.25`).
- An **immutable commit** exists (`7e99edab…`).
- The **exact dialect, size, variant, and filter policy** are defined (A / 60 / 1 /
  `--categories=` / `--wo-poses=abbr` / `--wo-pos-categories=nonword,wordpart`).
- Output behavior is **expected to be plain, sorted, and duplicate-free** (per the
  `printWordList` reading recorded in the candidate-evidence record).
- The candidate is **more precisely specified** than the prior LibreOffice selection
  for the current validator use case.

### 4. Proper-name policy resolved
- **Complete deterministic proper-name exclusion is not available** at the proposed
  release (upstream POS-class tagging cannot reliably filter all proper nouns).
- **Policy A has been approved for continued governance**
  (`docs/callhome_english_scowl_proper_name_policy.md`).
- **Residual proper-name risk remains** — short rows, asymmetric name coverage, and
  undetected mixed material require **later aggregate-only diagnostics** before real
  validation.
- **Proper-name risk is not claimed to be zero.**

### 5. Reproducibility path defined
- Model 1 has a **concrete and testable reproducibility path**
  (`docs/callhome_english_scowl_build_environment_evidence.md`).
- A **canonical, platform-specific container-image digest is required before
  execution**.
- **Two independent clean builds with matching SHA-256 digests are required before
  artifact approval**.
- **Semantic and byte-level reproducibility have not yet been demonstrated.**
- **No container or exact canonical Python/SQLite version is selected in this
  branch.**
- **Selection for continued governance can precede execution** because the
  reproducibility contract **remains a blocking operational gate**. (Containers do
  **not** by themselves guarantee determinism; the two-build byte-identity test is
  what would demonstrate it.)

### 6. Independence from CALLHOME evidence
- **No CALLHOME content or CALLHOME-derived lexical evidence influenced** this
  resource decision.
- The selection rests on **upstream resource properties, repository implementation
  requirements, licensing/notice evidence, and reproducibility policy**.
- **No resource should be tuned using CALLHOME contents.**

## LibreOffice Supersession Semantics
```text
LibreOffice candidate status:
NOT SELECTED AS THE PRIMARY ENGLISH RESOURCE

Historical records:
PRESERVED

Fallback status:
DOCUMENTED ONLY / NOT OPERATIONALLY APPROVED
```

- The **prior LibreOffice selection** (`docs/callhome_english_lexicon_resource_selection_decision.md`)
  was a **valid governance decision at the time it was made**.
- This new decision **prospectively supersedes only its status as the selected
  English resource candidate**.
- **Earlier records remain part of the historical audit trail and must not be edited
  or deleted** (none were touched in this branch).
- **LibreOffice is not approved operationally.**
- **LibreOffice remains documented as a fallback candidate; this branch does not
  impose a universal technical or legal rejection.**
- **No LibreOffice artifact is downloaded, removed, modified, or used** in this
  branch.
- This decision **does not claim the LibreOffice resource is legally defective**; the
  **unresolved package-level license-applicability question** remains part of **why
  it is not preferred**.

## Direct SCOWL Selection Boundary

### Approved in this branch
```text
Direct SCOWL / ESDB selected as the English resource family
and Model 1 selected as the source-artifact model for
continued governance.

Immutable source tag and commit selected.

Dialect A, size 60, variant 1 and the documented extraction
policy selected as the candidate specification.

Prior LibreOffice selection superseded.
```

### Not approved in this branch
```text
legal approval
final notice-bundle approval
container-image selection
container pull or build
SCOWL source checkout
SCOWL build
scowl.db generation
wordlist extraction
local resource placement
output filename approval
SHA-256 computation
two-build reproduction test
artifact approval
loader execution
aggregate dry run
real CALLHOME validation
clean promotion
condition construction
tokenization
model training
```

## Comparison Matrix
| Criterion | LibreOffice `en_US` candidate | Direct SCOWL / ESDB Model 1 | Decision significance |
| --------- | ----------------------------- | --------------------------- | --------------------- |
| upstream identity | LibreOffice/dictionaries `en/` bundled extension (SCOWL-derived `en_US`) | `en-wl/wordlist` ESDB (direct SCOWLv2 upstream) | direct upstream vs. repackaged bundle |
| immutable source identity | immutable repository snapshot `38d96a4d…`; README version and per-file last-touch commits recorded separately | dated tag `rel-2026.02.25` → immutable commit `7e99edab…` | both are commit-pinnable; SCOWL adds a dated release identity tied directly to the selected source model |
| license/notice clarity | package-level GPLv2 `license.txt` coexists with SCOWL/component notices | SCOWLv2 permission explicitly covers word lists generated from it | favors SCOWL for governance |
| file-specific applicability | unresolved (Category C) for `.dic`/`.aff` | permission explicitly reaches generated word lists | favors SCOWL |
| artifact form | Hunspell `.dic`/`.aff` inside a bundled extension | plain generated wordlist | plain list fits the loader natively |
| current-loader compatibility | `load_hunspell_dic_wordlist` (raw entries, flags stripped) | `load_plain_wordlist` directly | both loadable; SCOWL native plain |
| affix expansion requirement | would need `.aff` expansion to realize inflected forms (loader does not expand) | none — surface forms enumerated | favors SCOWL |
| surface-form coverage | current loader sees raw `.dic` entries but not forms obtainable only through `.aff` expansion | selected SCOWL extraction is designed to emit enumerated surface entries; artifact not yet generated | SCOWL is better aligned in principle; empirical coverage remains untested |
| dialect control | fixed `en_US` file | explicit dialect code `A` | SCOWL parameterized |
| size control | fixed | size `60` selectable | SCOWL parameterized |
| variant control | fixed | variant level `1` selectable | SCOWL parameterized |
| category/POS control | none (fixed dictionary) | `--categories=` / `--wo-poses` / `--wo-pos-categories` | SCOWL conservative filtering |
| proper-name policy | not the subject of the merged SCOWL-specific Policy A decision | complete exclusion unavailable; Policy A approved for SCOWL governance | policy resolved for the selected SCOWL candidate; risks are not assumed equal across resources |
| reproducibility path | static committed `.dic`/`.aff` (simple to pin), but license applicability unresolved | build + extract; canonical digest + two-build byte test required | SCOWL path defined; preferred despite more steps |
| byte identity demonstrated | NO | NO | undemonstrated for both |
| CALLHOME independence | decision independent of CALLHOME | decision independent of CALLHOME | required; satisfied |
| operational readiness | NOT APPROVED | NOT APPROVED | governance selection only |

## Selected-Resource Specification
| Field | Selected value | Status |
| ----- | -------------- | ------ |
| Resource ID | `english_scowl_esdb_en_us` | SELECTED FOR CONTINUED GOVERNANCE |
| Resource family | Direct SCOWL / English Speller Database (ESDB) | SELECTED FOR CONTINUED GOVERNANCE |
| Artifact model | source-generated plain wordlist (Model 1) | SELECTED FOR CONTINUED GOVERNANCE |
| Upstream | `en-wl/wordlist` (`wordlist.aspell.net`) | SELECTED FOR CONTINUED GOVERNANCE |
| Release tag | `rel-2026.02.25` | SELECTED FOR CONTINUED GOVERNANCE |
| Immutable commit | `7e99edab8e32f9f9ea2b15f249ca8d4d67237410` | SELECTED FOR CONTINUED GOVERNANCE |
| Dialect | `A` (American) | SELECTED FOR CONTINUED GOVERNANCE |
| Size | `60` | SELECTED FOR CONTINUED GOVERNANCE |
| Variant level | `1` | SELECTED FOR CONTINUED GOVERNANCE |
| Category policy | `--categories=` (default empty category) | SELECTED FOR CONTINUED GOVERNANCE |
| Abbreviation policy | `--wo-poses=abbr` (exclude abbreviations) | SELECTED FOR CONTINUED GOVERNANCE |
| POS-category policy | `--wo-pos-categories=nonword,wordpart` | SELECTED FOR CONTINUED GOVERNANCE |
| Open-compound policy | excluded (default word filter) | POLICY RESOLVED |
| Hyphen policy | excluded (omit `--hyphen`) | POLICY RESOLVED |
| Digit policy | excluded | POLICY RESOLVED |
| Special-symbol policy | excluded | POLICY RESOLVED |
| Apostrophe policy | internal permitted (`apostrophe=middle`) | POLICY RESOLVED |
| Diacritic policy | preserved (no `--deaccent`) | POLICY RESOLVED |
| Encoding | UTF-8 (`PYTHONIOENCODING=utf-8`) | POLICY RESOLVED |
| Line endings | LF | POLICY RESOLVED |
| Build command | `make` (→ `combine.py create-db scowl.db`) | POLICY RESOLVED |
| Extraction command | `./scowl --db scowl.db word-list 60 A 1 --categories= --wo-poses=abbr --wo-pos-categories=nonword,wordpart` | SELECTED FOR CONTINUED GOVERNANCE |
| Proper-name policy | Policy A (residual accepted for governance) | POLICY RESOLVED |
| Reproducibility contract | canonical digest + two-clean-build byte-identity test | POLICY RESOLVED |
| Canonical container | none selected | UNRESOLVED |
| Canonical platform | none selected | UNRESOLVED |
| Canonical Python | pending image (upstream min 3.7) | UNRESOLVED |
| Canonical SQLite | pending image (upstream min 3.33.0) | UNRESOLVED |
| Output filename | `scowl_en_US_size60_var1.txt` (proposed) | PROPOSED |
| Notice bundle | primary Atkinson SCOWLv2 notice (proposed) | PROPOSED |
| Artifact SHA-256 | none | NOT EXECUTED |
| Operational approval | — | NO / NOT APPROVED |

## Evidence Matrix
| Topic | Repository evidence | What it establishes | Remaining limitation | Confidence |
| ----- | ------------------- | ------------------- | -------------------- | ---------- |
| Prior LibreOffice selection | `docs/callhome_english_lexicon_resource_selection_decision.md` | LibreOffice `en_US` was selected for continued governance (governance only) | governance-only; now superseded | DIRECT |
| LibreOffice package-license applicability | `docs/callhome_english_lexicon_license_applicability_investigation.md` (Category C) | file-specific GPLv2 applicability to `.dic`/`.aff` is unresolved | not a legal defect finding | DIRECT |
| Direct SCOWL permission pathway | `docs/callhome_english_scowl_candidate_evidence.md` / build-env record (`Copyright` @ pin) | permission covers word lists created from SCOWLv2; prior governance reading supports a proposed primary-notice pathway for the selected American size-60 output | exact notice bundle not yet approved | DIRECT |
| Exact SCOWL source identity | candidate-evidence + build-env records | tag `rel-2026.02.25` → commit `7e99edab…` | pin selected, not executed | DIRECT |
| Model 1 output compatibility | candidate-evidence (`printWordList` sorted/dedup) + loader | plain wordlist compatible with `load_plain_wordlist` | output not yet generated | DIRECT |
| Hunspell loader limitation | `src/cslm/data/callhome_lexicon_loader.py` | reads raw `.dic` entries, strips flags, no `.aff` expansion | does not expose forms obtainable only through `.aff` expansion | DIRECT |
| Proper-name policy | `docs/callhome_english_scowl_proper_name_policy.md` | Policy A approved for governance; complete exclusion unavailable | residual risk remains | DIRECT |
| Reproducibility contract | `docs/callhome_english_scowl_build_environment_evidence.md` | canonical digest + two-build byte-identity test required | contract not executed | DIRECT |
| Untested byte identity | build-env record | byte-for-byte reproducibility not demonstrated | must be demonstrated later | LIMITED |
| CALLHOME-independent decision basis | this record + prior records | decision used no CALLHOME/derived evidence | — | DIRECT |

## Decision Matrix
| Decision or gate | Status |
| ---------------- | ------ |
| English resource reassessment completed | YES / RECORDED |
| Direct SCOWL / ESDB resource family selected | YES / SELECTED FOR CONTINUED GOVERNANCE |
| Model 1 source-generated artifact selected | YES / SELECTED FOR CONTINUED GOVERNANCE |
| SCOWL release tag selected | YES / SELECTED FOR CONTINUED GOVERNANCE |
| SCOWL immutable commit selected | YES / SELECTED FOR CONTINUED GOVERNANCE |
| Dialect A selected | YES / SELECTED FOR CONTINUED GOVERNANCE |
| Size 60 selected | YES / SELECTED FOR CONTINUED GOVERNANCE |
| Variant level 1 selected | YES / SELECTED FOR CONTINUED GOVERNANCE |
| Extraction-policy identity selected | YES / SELECTED FOR CONTINUED GOVERNANCE |
| Proper-name policy resolved | YES / POLICY RESOLVED |
| Reproducibility contract resolved | YES / POLICY RESOLVED |
| Prior LibreOffice selection superseded | SUPERSEDED |
| LibreOffice operationally rejected | NO / DOCUMENTED FALLBACK ONLY |
| Direct SCOWL notice bundle approved | NO / NOT APPROVED |
| Canonical container selected | NO |
| Canonical platform selected | NO |
| Canonical Python selected | NO |
| Canonical SQLite selected | NO |
| Source checkout approved | NO / NOT APPROVED |
| Container pull/build approved | NO / NOT APPROVED |
| SCOWL build approved | NO / NOT APPROVED |
| Wordlist extraction approved | NO / NOT APPROVED |
| Local placement approved | NO / NOT APPROVED |
| Output filename approved | NO / NOT APPROVED |
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

- **No CALLHOME content was inspected.**
- **No resource was downloaded or generated.**
- **No hash was computed.**
- **The real pipeline remains on conservative default validation.**
- **All rows remain blocked from conditions.**
- **No Spanish resource or locale decision changes in this branch.**

## Next Step
The next legitimate action is **not** an operational step. It is the future
**English license-and-notice bundle decision** for the selected direct-SCOWL output
(proposed: the primary Atkinson notice), followed by **canonical container-image
digest selection** and the recording of the exact canonical Python/SQLite versions —
all still **without executing a build**. Only a later, separately approved step would
run the two-clean-build byte-identity test on **local, gitignored** artifacts. Until
then, direct SCOWL / ESDB Model 1 is **selected for continued governance only**, the
LibreOffice candidate is a **documented fallback only**, and every operational gate
remains **closed**.
