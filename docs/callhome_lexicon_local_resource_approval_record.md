# CALLHOME Lexicon Local Resource Approval Record

## Status
- **Docs-only record, not implementation.** No code changes.
- **No resource is downloaded, placed, or committed** by this branch.
- **This branch does not create or populate the local resource directory**
  (`data/resources/local_lexicons/` remains local-only and ignored).
- **No hashes are computed.**
- **No loader is enabled.** No validator is run over real CALLHOME.
- **No aggregate dry run is enabled.** No clean promotion. No condition JSONL. No
  tokenization or dataset construction. No model training.
- **The real pipeline remains unchanged** (`default_source_validation` only;
  validator/loader not wired in). Every real CALLHOME row stays `not_validated`;
  `clean` stays zero.
- No real CALLHOME transcript excerpts, token strings, header values,
  participant names, raw speaker IDs, or raw CALLHOME filenames appear here.
- **All approval fields remain `NO / NOT APPROVED`.**

## Purpose
This record moves from the blank placement-approval template
(`docs/callhome_lexicon_placement_approval_template.md`) to a **concrete
candidate-resource record** for the two documented English and Spanish lexicon
candidates. It:

- names the intended candidate resources more concretely,
- consolidates already-documented source, license, notice, and placement
  information from the existing docs chain,
- identifies the metadata that is still unresolved,
- prepares for a **future reviewer decision**.

It does **not** itself grant permission to place or use any resource. Facts here
are taken **only** from existing repository documentation; anything not explicitly
established there is marked `TBD / NOT YET VERIFIED`.

## Scope of This Record
- Covers the **two currently documented candidate roles**: the **English**
  SCOWL/LibreOffice `en_US` Hunspell candidate and the **Spanish** RLA-ES/
  LibreOffice Spanish Hunspell candidate.
- Consolidates and cross-links existing documentation; it introduces **no new
  source URLs, versions, filenames, or license conclusions** beyond what the docs
  already record.
- Does **not** broaden to other resources (e.g. `wordfreq`, spaCy, UniMorph,
  FreeLing) surveyed in `docs/callhome_lexicon_resource_candidates.md`.

## Relationship to Existing Documentation
This record sits **after** the candidate/resource evidence chain and **before**
any dedicated placement-approval decision. It reads from (repository-relative):

- `docs/callhome_lexicon_resource_policy.md`
- `docs/callhome_lexicon_resource_candidates.md`
- `docs/callhome_lexicon_license_sources.md`
- `docs/callhome_lexicon_resource_manifest.md`
- `docs/callhome_lexicon_attribution_notices.md`
- `docs/callhome_lexicon_normalization_policy.md`
- `docs/callhome_lexicon_storage_scaffold.md`
- `docs/callhome_lexicon_local_use_checklist.md`
- `docs/callhome_lexicon_dry_run_plan.md`
- `docs/callhome_lexicon_local_resource_manifest_template.md`
- `docs/callhome_lexicon_placement_approval_template.md`

The evidence note pins **source/license evidence** ("source evidence found; not
adopted"); the manifest draft and notice inventory record **obligations**; the
templates define **what must be filled**. This record **instantiates** those into
a concrete per-candidate record while approving nothing.

## Approval State Summary
"Verified" means an existing repository doc explicitly establishes the fact; where
docs only identify a candidate or a provisional pathway, the cell stays
`TBD / NOT YET VERIFIED` or names the provisional status.

| Gate                           | English                                                                 | Spanish                                                                                    |
| ------------------------------ | ----------------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| candidate identified           | DOCUMENTED (SCOWL/LibreOffice `en_US` Hunspell)                         | DOCUMENTED (RLA-ES/LibreOffice Spanish Hunspell)                                          |
| exact source/version verified  | TBD / NOT YET VERIFIED (evidence: `en_US 2020.12.07`; canonical pin required) | TBD / NOT YET VERIFIED (evidence: LibreOffice `es` 2.9 / RLA-ES `v2.9`; canonical pin required) |
| exact upstream files verified  | TBD / NOT YET VERIFIED                                                   | TBD / NOT YET VERIFIED (regional variant unresolved)                                      |
| license pathway verified       | candidate pathway identified; appears potentially compatible; NOT verified; not adopted | candidate pathways identified (triple GPL/LGPL/MPL); pathway selection TBD / NOT YET VERIFIED; not adopted |
| notice obligations verified    | identified; verbatim not captured; NOT verified                         | identified; verbatim not captured; NOT verified                                           |
| approved for local placement   | NO / NOT APPROVED                                                        | NO / NOT APPROVED                                                                         |
| approved for loader use        | NO / NOT APPROVED                                                        | NO / NOT APPROVED                                                                         |
| approved for aggregate dry run | NO / NOT APPROVED                                                        | NO / NOT APPROVED                                                                         |
| approved for clean promotion   | NO / NOT APPROVED                                                        | NO / NOT APPROVED                                                                         |
| approved for condition JSONL   | NO / NOT APPROVED                                                        | NO / NOT APPROVED                                                                         |
| approved for training          | NO / NOT APPROVED                                                        | NO / NOT APPROVED                                                                         |

No cell overstates verification: the license/source docs record **evidence only**
("source evidence found; not adopted"), not a determination that the files may be
used.

## English Candidate Resource Record
Populated only from documented facts; unresolved items are `TBD / NOT YET
VERIFIED`; every approval field is `NO / NOT APPROVED`.

```
### Candidate record: english_en_us_hunspell

- Resource ID: english_en_us_hunspell
- Resource role: English lexicon
- Language: eng
- Candidate project/package: LibreOffice/dictionaries English Hunspell
  (SCOWL / English Speller Database pathway)
- Candidate dictionary/locale: en_US
- Upstream source: LibreOffice/dictionaries en/README_en_US.txt (per
  docs/callhome_lexicon_license_sources.md); canonical URL pin TBD / NOT YET VERIFIED
- Exact version or release date: evidence records
  "en_US Hunspell Dictionary Version 2020.12.07"; canonical pin TBD / NOT YET VERIFIED
- Exact upstream files: TBD / NOT YET VERIFIED (README referenced; exact .dic/.aff
  or wordlist files not yet selected)
- Expected file type: Hunspell .dic (raw entries) or plain wordlist — TBD / NOT YET VERIFIED
- Expected encoding: expected UTF-8; exact per-file encoding TBD / NOT YET VERIFIED
- Intended loader mode: plain wordlist | Hunspell .dic raw-entry (per loader
  scaffold); exact mode TBD / NOT YET VERIFIED
- License pathway: SCOWL copyright + permission notice pathway; combined
  ESDB/en-wl MIT-like per its Copyright file; "appears potentially compatible";
  NOT verified; not adopted
- Redistribution status: TBD / NOT YET VERIFIED (default: local/gitignored first)
- Notice obligations: SCOWL copyright + permission notice; Ispell / WordNet /
  VarCon / other component notices — identified; verbatim not captured
- Attribution obligations: preserve SCOWL + component notices per
  docs/callhome_lexicon_attribution_notices.md
- Derivation status: source resource (not a derived wordlist)
- Proposed normalized derivative: none proposed; NO / NOT APPROVED
- Intended ignored local directory: data/resources/local_lexicons/
- Intended local filename or subpath: TBD / NOT YET VERIFIED (NOT PLACED)
- Placement approval: NO / NOT APPROVED
- Loader-use approval: NO / NOT APPROVED
- Aggregate-dry-run approval: NO / NOT APPROVED
- Clean-promotion approval: NO / NOT APPROVED
- Notes: status per docs/callhome_lexicon_license_sources.md =
  "source evidence found; not adopted."
```

## Spanish Candidate Resource Record
Same fields as the English record. The **regional variant is explicitly
unresolved** and is not silently chosen here.

```
### Candidate record: spanish_rla_es_hunspell

- Resource ID: spanish_rla_es_hunspell
- Resource role: Spanish lexicon
- Language: spa
- Candidate project/package: LibreOffice/dictionaries Spanish Hunspell from RLA-ES
  (Recursos Lingüísticos Abiertos del Español; sbosio/rla-es)
- Candidate dictionary/locale: TBD / NOT YET VERIFIED — regional variant UNRESOLVED
  (documented variants include es, es_ES, es_MX, es_US; not selected here)
- Upstream source: LibreOffice es/ package + RLA-ES sbosio/rla-es (per
  docs/callhome_lexicon_license_sources.md); canonical URL pin TBD / NOT YET VERIFIED
- Exact version or release date: evidence records LibreOffice es/ version 2.9 and
  RLA-ES latest release v2.9 (Jan 2, 2025); canonical pin TBD / NOT YET VERIFIED
- Exact upstream files: TBD / NOT YET VERIFIED (LibreOffice es/ includes LICENSE.md,
  README_hunspell_es.txt, and regional dictionary files including es_ES.aff/es_ES.dic;
  the chosen variant's exact files are not selected)
- Expected file type: Hunspell .dic (raw entries) or plain wordlist — TBD / NOT YET VERIFIED
- Expected encoding: expected UTF-8; exact per-file encoding TBD / NOT YET VERIFIED
- Intended loader mode: plain wordlist | Hunspell .dic raw-entry (per loader
  scaffold); exact mode TBD / NOT YET VERIFIED
- License pathway: triple disjunctive GPLv3-or-later / LGPLv3-or-later /
  MPL 1.1-or-later; exact pathway selection TBD / NOT YET VERIFIED; NOT
  verified; not adopted
- Redistribution status: TBD / NOT YET VERIFIED (default: local/gitignored first)
- Notice obligations: RLA-ES attribution (Recursos Lingüísticos Abiertos del
  Español); Santiago Bosio + contributors; selected-pathway notice; upstream
  LICENSE.md / README_hunspell_es.txt — identified; verbatim not captured
- Attribution obligations: preserve RLA-ES attribution + author credit per
  docs/callhome_lexicon_attribution_notices.md
- Derivation status: source resource (not a derived wordlist)
- Proposed normalized derivative: none proposed; NO / NOT APPROVED
- Intended ignored local directory: data/resources/local_lexicons/
- Intended local filename or subpath: TBD / NOT YET VERIFIED (NOT PLACED)
- Placement approval: NO / NOT APPROVED
- Loader-use approval: NO / NOT APPROVED
- Aggregate-dry-run approval: NO / NOT APPROVED
- Clean-promotion approval: NO / NOT APPROVED
- Notes: regional variant unresolved (explicit); status per
  docs/callhome_lexicon_license_sources.md = "source evidence found; not adopted."
```

## Intended Local Placement Layout
This describes only the **intended future** structure; **nothing here exists or is
created by this branch.** Exact filenames are placeholders until an approved
record fixes them.

```
data/resources/local_lexicons/            (ignored; NOT populated by this branch)
  english/                                (conceptual; NOT CREATED)
    <en_US wordlist or .dic>              (TBD / NOT YET VERIFIED; NOT PLACED)
  spanish/                                (conceptual; NOT CREATED)
    <chosen-variant wordlist or .dic>     (TBD / NOT YET VERIFIED; NOT PLACED)
```

- **This branch does not create directories.**
- **This branch does not place files.**
- The path remains **local-only and gitignored**.
- **Real lexicon files must not appear in `git status`** (tracked or untracked).
- Exact future local filenames must match an **approved** record before placement.
- **No `.gitkeep`, placeholder lexicon file, or sample resource file is added
  here** (consistent with `docs/callhome_lexicon_storage_scaffold.md`).

## License, Notice, and Attribution Status
Summarized conservatively from the existing docs; no legal certainty is claimed
beyond what those docs state, and no long license text or upstream license file is
added.

- **Candidate license pathway identified** — **yes** for both (English: SCOWL/ESDB
  permission-notice pathway; Spanish: triple disjunctive GPL/LGPL/MPL pathways,
  with the exact pathway still TBD / NOT YET VERIFIED).
- **Exact license applicability verified** — **no** (evidence only; "appears
  potentially compatible" is explicitly *not* a determination that files may be
  used).
- **Redistribution status established** — **no** (`TBD / NOT YET VERIFIED`; default
  posture is local/gitignored first).
- **Notice obligations mapped** — **identified** (SCOWL + Ispell/WordNet/VarCon/
  other for English; RLA-ES attribution + author credit + selected-pathway notice
  for Spanish) but **verbatim text not captured**; capture belongs in a future
  attribution/notice appendix.
- **Attribution obligations mapped** — **identified**, per
  `docs/callhome_lexicon_attribution_notices.md`; not yet captured verbatim.

If notices cannot be preserved, or license ambiguity remains, use is **blocked**.

## Normalization and Derivation Status
- **Source files must never be modified in place** (normalization builds a derived
  comparison form; upstream `.dic` / `.aff` files are never edited).
- **Normalization is defined by the repository policy**
  (`docs/callhome_lexicon_normalization_policy.md`) and must be applied
  **identically** to utterance tokens and lexicon entries.
- **Derived normalized wordlists require separate approval** and stay
  local/gitignored until their license/notice treatment is documented and approved.
- **No derived wordlist is created in this branch.**
- **No CALLHOME-derived token list may shape, filter, expand, normalize, or modify
  a lexicon.**
- **CALLHOME text or tokens must never influence lexicon construction.**
- Any proposed derivative remains **`NO / NOT APPROVED`**.

## Hash and Provenance Status
- **No hashes are computed in this branch.**
- Hashes belong to a **later post-placement local manifest record**, after
  approval and local placement.
- Future hash entries must identify the **algorithm, the local file, the source/
  version linkage, the person, and the date**.
- **Hashes do not imply adoption or use approval.**
- Exact file provenance remains **unresolved** until exact files and versions are
  approved.

Placeholders only:

```
- Hash algorithm: TBD (e.g. SHA256)
- Local file hash: TBD (not computed in this branch)
- Source / version linkage: TBD / NOT YET VERIFIED
- Hash computed by: TBD
- Hash computation date: TBD
```

## Loader and Validation Status
- A **loader scaffold exists** (`src/cslm/data/callhome_lexicon_loader.py`).
- A **lexicon validator scaffold exists**
  (`src/cslm/data/callhome_lexicon_validation.py`).
- **Neither is approved for real local-resource use.**
- The **real summary script remains unwired** from the loader and validator
  (`scripts/summarize_callhome_projection_local.py` uses
  `default_source_validation` only).
- The **disabled dry-run script remains disabled**
  (`scripts/dry_run_callhome_lexicon_validation.py`).
- **No real CALLHOME validation occurs here.**
- **Every real CALLHOME row remains `not_validated`.**
- **`clean` remains zero; condition candidates remain zero.**

## Condition-Routing Guardrails
- **CALLHOME must never feed `CsCont`.**
- **`CsCont` remains Bangor-sourced only.**
- Future **clean English** CALLHOME rows may route **only** to:
  - `EnglishMono`
  - `MonoCont`
- Future **clean Spanish** CALLHOME rows may route **only** to:
  - `SpanishMono`
  - `MonoCont`
- Routing is allowed **only after** later explicit validation and clean-promotion
  approval.
- **Candidate-resource documentation alone changes no routing.**

## Unresolved Questions
Based only on the existing docs:

| # | Unresolved item                                                   | Status                 |
| - | ----------------------------------------------------------------- | ---------------------- |
| 1 | exact English upstream version pin + canonical URL                | TBD / NOT YET VERIFIED |
| 2 | exact English files (`.dic`/`.aff` or wordlist) for placement     | TBD / NOT YET VERIFIED |
| 3 | exact Spanish upstream version pin + canonical URL                | TBD / NOT YET VERIFIED |
| 4 | exact Spanish locale / regional variant (`es` / `es_ES` / …)       | TBD / NOT YET VERIFIED |
| 5 | exact Spanish files for the chosen variant                        | TBD / NOT YET VERIFIED |
| 6 | final license pathway confirmation (English combined; Spanish one of three) | TBD / NOT YET VERIFIED |
| 7 | final redistribution status (committable vs local-only)           | TBD / NOT YET VERIFIED |
| 8 | exact notice-preservation method (future verbatim appendix)       | TBD / NOT YET VERIFIED |
| 9 | intended local filenames                                          | TBD / NOT YET VERIFIED |
| 10 | future hash algorithm                                            | TBD / NOT YET VERIFIED |
| 11 | reviewer and approval PR                                         | TBD / NOT YET VERIFIED |
| 12 | whether derived normalized wordlists will ever be requested      | TBD / NOT YET VERIFIED |

## Explicit Non-Approval Gates
This record grants **none** of the following, for **either** candidate:

| Gate                            | English           | Spanish           |
| ------------------------------- | ----------------- | ----------------- |
| local placement                 | NO / NOT APPROVED | NO / NOT APPROVED |
| resource adoption               | NO / NOT APPROVED | NO / NOT APPROVED |
| loader use                      | NO / NOT APPROVED | NO / NOT APPROVED |
| aggregate dry run               | NO / NOT APPROVED | NO / NOT APPROVED |
| clean promotion                 | NO / NOT APPROVED | NO / NOT APPROVED |
| condition JSONL                 | NO / NOT APPROVED | NO / NOT APPROVED |
| tokenizer/dataset construction  | NO / NOT APPROVED | NO / NOT APPROVED |
| training                        | NO / NOT APPROVED | NO / NOT APPROVED |

## Failure and Stop Conditions
Work must **stop** if:

- exact resource identity **cannot be tied** to documented sources
- exact source / version is **guessed**
- exact files are **guessed**
- license or notice status is **overstated**
- the **Spanish locale is silently selected** without approval
- files would be **downloaded or placed** in this branch
- files would appear in **`git status`**
- **hashes would be computed** in this branch
- **CALLHOME-derived material influenced** the resource
- **loader use is combined with placement approval**
- **dry-run approval is combined with placement approval**
- **clean promotion is combined with this record**
- **condition JSONL or training is proposed**
- **CALLHOME could route to `CsCont`**

## Reviewer Checklist
- [ ] facts were checked against existing repository docs
- [ ] no unsupported facts were added
- [ ] unresolved facts are marked `TBD / NOT YET VERIFIED`
- [ ] the documented English candidate family and locale are recorded
- [ ] the documented Spanish candidate family is recorded
- [ ] unresolved exact versions, files, and locale choices remain explicit
- [ ] unresolved Spanish locale status is explicit
- [ ] license status is represented conservatively (evidence, not determination)
- [ ] notice and attribution status are represented conservatively (identified, not captured)
- [ ] no resource files were added
- [ ] no derived files were added
- [ ] no hashes were computed
- [ ] all approval fields remain `NO / NOT APPROVED`
- [ ] source-boundary rules remain intact (CALLHOME never shapes lexicons; never feeds `CsCont`)
- [ ] no real pipeline behavior changed

## Next Approved Step
The next step is a **future reviewer decision**, not an automatic action. After
this record is reviewed, the likely next step is **one** of:

1. **revise** the unresolved source/license metadata (versions, exact files,
   Spanish variant, license selection, notice-capture method), or
2. **create a dedicated placement-approval decision PR** for exact resources and
   files, using `docs/callhome_lexicon_placement_approval_template.md`.

Placement does **not** occur automatically after this branch. Nothing is placed,
loaded, validated, or promoted without its own separate, explicit approval.

## Final Gate Status
- **Candidate resources are documented more concretely.**
- **No resource is approved.**
- **No resource is placed.**
- **No resource is loaded.**
- **No real validation occurs.**
- **All CALLHOME rows remain blocked** (`not_validated`; `clean` stays zero).
- **The gate remains closed** until each later approval is separately granted.
