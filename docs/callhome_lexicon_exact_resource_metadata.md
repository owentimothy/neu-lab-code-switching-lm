# CALLHOME Lexicon Exact Resource Metadata

## Status
- **Docs-only metadata record, not implementation.** No code changes.
- **No lexicon resource artifact was saved to disk, copied into the repository,
  placed under `data/resources/local_lexicons/`, loaded, or hashed.** The local
  resource directory is not created or populated; it remains local-only and
  ignored.
- **No hashes are computed.** No loader use. No validator use over real CALLHOME.
- **No aggregate dry run.** No clean promotion. No condition JSONL. No tokenizer
  or dataset construction. No model training.
- **The real pipeline remains unchanged** (`default_source_validation` only;
  validator/loader not wired in). Every real CALLHOME row stays `not_validated`;
  `clean` stays zero.
- **This revision incorporates an authorized, read-only scoped web-verification
  pass** against official upstream sources (see Evidence Standard). Official
  upstream webpage, API, and raw-text content was inspected read-only; **no
  lexicon resource artifact was saved to disk, copied into the repository, placed
  under `data/resources/local_lexicons/`, loaded, or hashed.**
- No real CALLHOME transcript excerpts, token strings, header values, participant
  names, raw speaker IDs, or raw CALLHOME filenames appear here.
- **All operational approvals remain `NO / NOT APPROVED`.**

## Purpose
The prior record (`docs/callhome_lexicon_local_resource_approval_record.md`)
documented the two candidate resource families but left several items unresolved:
exact upstream source locations, exact release/version pins, exact English files,
exact Spanish locale/variant, exact Spanish files, final notice references, and a
conservative redistribution status. This record resolves those **as precisely as
can be justified from cited evidence**, and marks everything else
`TBD / NOT YET VERIFIED`. This is **metadata verification only**; it is not
placement approval, adoption, loader-use approval, dry-run approval,
clean-promotion approval, condition-JSONL approval, or training approval.

## Verification Pass Result (this revision)
An authorized read-only pass against official upstream sources **resolved** the
following that were previously `TBD`:

- **English exact files** — `en/en_US.dic`, `en/en_US.aff` (UPSTREAM-VERIFIED).
- **English license/notice files** — `en/license.txt`, `en/WordNet_license.txt`,
  plus the notices carried in `en/README_en_US.txt` (UPSTREAM-VERIFIED).
- **English version + date** — README states "Version 2020.12.07", released
  Mon Dec 7 2020 (UPSTREAM-VERIFIED), with a pin caveat (below).
- **English encoding** — `SET UTF-8` (UPSTREAM-VERIFIED).
- **English LibreOffice pin** — inspected at `LibreOffice/dictionaries` master
  HEAD `38d96a4d54ec3449cf7f28cddae1fce32e2b15a7` (verification date 2026-07-10);
  the `en/` tree is unchanged since its last-touch commit
  `e7f163feb2beaf526135132d8716e68e19d2716e` (2025-03-31), and `en_US.dic`/`.aff`
  were last touched by `4fa94195b8136364dd40bf2b0366a0fe32058899` (2021-05-12).
- **RLA-ES source release pin** — `sbosio/rla-es` tag `v2.9` = commit
  `ea82c1214ead57740798acf66a1e18e5ac874c41`; published 2025-01-02
  (UPSTREAM-VERIFIED). This is the **source-project** release reference.
- **Spanish package variant set** — 23 regional `.dic`/`.aff` pairs in the
  **separate** `LibreOffice/dictionaries` `es/` package, incl. `es_ES`, `es_MX`,
  `es_US` (UPSTREAM-VERIFIED from the `es/` listing). This package is **not**
  automatically the same artifact as RLA-ES `v2.9` — see the correspondence
  caveat below.
- **Spanish license alternatives** — triple disjunctive GPLv3-or-later /
  LGPLv3-or-later / MPL 1.1-or-later (user may choose); thesaurus separately
  LGPLv2.1 (UPSTREAM-VERIFIED).
- **Spanish encoding** — `es_ES.aff` declares `SET UTF-8` (UPSTREAM-VERIFIED for
  that one file only; other regional variants were not individually verified).

**Correction — RLA-ES release vs. LibreOffice package:** the `sbosio/rla-es`
`v2.9` tag is a **source-project** release. The inspected variant inventory and
packaged files were read from the **separate** `LibreOffice/dictionaries` `es/`
package. Official evidence indicates these are **not** the same snapshot: the
LibreOffice `es/README_hunspell_es.txt` was last updated by commit
`2b9183e45954cfd9d1638f838b461de1ce68b296` (2020-10-28) whose message is
"Update all Spanish dictionaries to RLA v2.6". Whether any later commit advanced
individual `es/` `.dic` files past RLA v2.6 was **not** verified this pass. The
exact correspondence therefore stays unresolved (below).

**Still unresolved by design/policy:** the **Spanish regional variant** stays
`TBD / NOT YET VERIFIED` (no approved locale policy; not chosen here), the English
content-vs-version **immutable pin** carries a caveat (below), the
**RLA-ES v2.9 ↔ inspected LibreOffice Spanish package correspondence** is
`TBD / NOT YET VERIFIED` (evidence indicates the package is RLA v2.6-era), and the
**redistribution legality** is `not independently legally determined`.

## Scope
- Covers the **two currently documented candidate families only**: the **English**
  SCOWL/LibreOffice `en_US` Hunspell candidate and the **Spanish** RLA-ES/
  LibreOffice Spanish Hunspell candidate.
- Does **not** select a different resource family, and does **not** broaden to the
  other resources surveyed in `docs/callhome_lexicon_resource_candidates.md`.
- Records metadata; it changes **no** routing, code, or approval state.

## Evidence Standard
Two evidence layers are used, with explicit labels on each material claim:

1. **`UPSTREAM-VERIFIED`** — confirmed in this revision from an official upstream
   primary source (official repository file/listing, release, tag, commit, README,
   or license file).
2. **`REPOSITORY-RECORDED`** — established only by existing in-repo docs.

Unresolved facts are `TBD / NOT YET VERIFIED`; research/policy decisions and
operational approvals are called out separately (e.g. `NO / NOT APPROVED`).

**Browsing posture for this revision:** an **authorized, read-only** scoped
verification pass was performed against official upstream sources only
(`LibreOffice/dictionaries`, `sbosio/rla-es`, and their README/license/release
metadata via the official GitHub API and raw file endpoints). Search was used only
to locate official sources; every material fact was read from the official source
itself. **No lexicon resource artifact was saved to disk, copied into the
repository, placed under `data/resources/local_lexicons/`, loaded, or hashed;**
official upstream webpage, API, and raw-text content was inspected read-only. No
long README/license/notice text is pasted; summaries are narrow. Nothing was
inferred or guessed; anything not confirmed is left `TBD / NOT YET VERIFIED`.

**Pin discipline:** `LibreOffice/dictionaries` `master` is a mutable branch, so
raw `/master/` reads resolve to HEAD at fetch time. This pass records the
**snapshot** HEAD used for verification and, separately, each file's **last-touch**
commit. A file's last-touch commit is **not** presumed to be the correct
package-version pin (e.g. English `en_US.dic` was last touched in 2021-05-12 while
the README version string reads `2020.12.07`).

### Source-verification table
| Claim | Official source | Type | Immutable pin / reference | Status |
| ----- | --------------- | ---- | ------------------------- | ------ |
| LibreOffice inspection HEAD (snapshot) | `LibreOffice/dictionaries` master | branch HEAD | `38d96a4d54ec3449cf7f28cddae1fce32e2b15a7` (2026-07-10) | UPSTREAM-VERIFIED (mutable branch) |
| English `en/` tree stability | `LibreOffice/dictionaries` | last-touch commit for `en/` | `e7f163feb2beaf526135132d8716e68e19d2716e` (2025-03-31) | UPSTREAM-VERIFIED |
| English files `en_US.dic` / `en_US.aff` | `LibreOffice/dictionaries` `en/` | repo dir listing; last-touch `4fa94195…` (2021-05-12) | commit sha (last-touch, not a version tag) | UPSTREAM-VERIFIED |
| English README `README_en_US.txt` | `LibreOffice/dictionaries` `en/` | repo file | (within `en/` tree `e7f163fe…`) | UPSTREAM-VERIFIED |
| English license files `license.txt`, `WordNet_license.txt` | `LibreOffice/dictionaries` `en/` | repo files | (within `en/` tree `e7f163fe…`) | UPSTREAM-VERIFIED |
| English version `2020.12.07`, released Dec 7 2020 | `en/README_en_US.txt` | repo file (README) | version string only (see caveat) | UPSTREAM-VERIFIED |
| English SCOWL size 60; en_US/en_CA/en_AU official | `en/README_en_US.txt` | repo file (README) | — | UPSTREAM-VERIFIED |
| English encoding `SET UTF-8` | `en/README_en_US.txt` | repo file (README) | — | UPSTREAM-VERIFIED |
| RLA-ES source release `v2.9`, published 2025-01-02 | `sbosio/rla-es` releases/tags | release → commit | tag `v2.9` → `ea82c1214ead57740798acf66a1e18e5ac874c41` | UPSTREAM-VERIFIED (source project) |
| Spanish package variant set (23 `.dic`/`.aff`) incl. es_ES/es_MX/es_US | `LibreOffice/dictionaries` `es/` | repo dir listing | snapshot HEAD `38d96a4d…` (master, mutable) | UPSTREAM-VERIFIED |
| Spanish package README `README_hunspell_es.txt` | `LibreOffice/dictionaries` `es/` | repo file; last-touch `2b9183e4…` (2020-10-28, "RLA v2.6") | commit sha | UPSTREAM-VERIFIED |
| Spanish license files `LICENSE.md`, `GPLv3.txt`, `LGPLv2.1.txt`, `LGPLv3.txt` | `LibreOffice/dictionaries` `es/` | repo files | (within `es/` snapshot) | UPSTREAM-VERIFIED |
| Spanish license alternatives (GPLv3+/LGPLv3+/MPL 1.1+; thesaurus LGPLv2.1) | `es/LICENSE.md` | repo file | — | UPSTREAM-VERIFIED |
| Spanish encoding `SET UTF-8` (es_ES only) | `es/es_ES.aff` | repo file | snapshot HEAD (master, mutable) | UPSTREAM-VERIFIED (es_ES only) |
| RLA-ES `v2.9` ↔ inspected LibreOffice `es/` package correspondence | LibreOffice `es/` history | correspondence | — | TBD / NOT YET VERIFIED (README indicates RLA v2.6) |
| Spanish per-variant encoding (non-es_ES) | `es/<variant>.aff` | repo files | — | TBD / NOT YET VERIFIED |
| Spanish selected variant | — | policy decision | — | TBD / NOT YET VERIFIED |
| Redistribution legality (either resource) | upstream license files | legal review | — | not independently legally determined |

## Relationship to Existing Documentation
This record sits **after** the concrete candidate record and **before** any
placement-approval decision. It reads from (repository-relative):

- `docs/callhome_lexicon_resource_policy.md`
- `docs/callhome_lexicon_resource_candidates.md`
- `docs/callhome_lexicon_license_sources.md`
- `docs/callhome_lexicon_resource_manifest.md`
- `docs/callhome_lexicon_attribution_notices.md`
- `docs/callhome_lexicon_normalization_policy.md`
- `docs/callhome_lexicon_storage_scaffold.md`
- `docs/callhome_lexicon_local_use_checklist.md`
- `docs/callhome_lexicon_local_resource_manifest_template.md`
- `docs/callhome_lexicon_placement_approval_template.md`
- `docs/callhome_lexicon_local_resource_approval_record.md`

It also uses one **code fact**: the loader scaffold
`src/cslm/data/callhome_lexicon_loader.py` reads plain wordlists or Hunspell
`.dic` raw entries, ignores a leading count line, strips affix flags after `/`,
and performs **no `.aff` reading and no affix expansion**.

## Unresolved Metadata Entering This Branch
Carried in from `docs/callhome_lexicon_local_resource_approval_record.md`; the
"Now" column reflects this verification pass.

| # | Item | Prior status | Now |
| - | ---- | ------------ | --- |
| 1 | exact English upstream version pin + canonical URL | TBD | version + files UPSTREAM-VERIFIED; LibreOffice snapshot/last-touch pins recorded; version-tag caveat (below) |
| 2 | exact English files (`.dic` / `.aff` / wordlist) | TBD | `en_US.dic`, `en_US.aff` UPSTREAM-VERIFIED |
| 3 | exact Spanish upstream version pin + canonical URL | TBD | RLA-ES source `v2.9` → `ea82c12…` UPSTREAM-VERIFIED; LibreOffice package snapshot is separate (RLA v2.6-era per README) |
| 4 | exact Spanish locale / regional variant | TBD | still `TBD / NOT YET VERIFIED` (policy) |
| 5 | exact Spanish files for the chosen variant | TBD | package variant set UPSTREAM-VERIFIED; chosen-variant files + non-es_ES encoding pending |
| 6 | final license pathway confirmation | TBD | alternatives UPSTREAM-VERIFIED; selection still `TBD` |
| 7 | final redistribution status | TBD | still `not independently legally determined` |
| 8 | exact notice-preservation method | TBD | exact notice files verified; verbatim capture still pending |

## English Exact Resource Metadata
Labels: `UPSTREAM-VERIFIED` / `REPOSITORY-RECORDED` / `TBD / NOT YET VERIFIED`.
Every approval field is `NO / NOT APPROVED`.

```
- Resource ID: english_en_us_hunspell
- Resource family: SCOWL / LibreOffice en_US Hunspell (English Speller Database /
  SCOWL pathway) [UPSTREAM-VERIFIED: README states SCOWL derivation]
- Language: eng
- Locale: en_US
- Authoritative upstream project: LibreOffice/dictionaries English dictionaries,
  derived from SCOWL (Kevin Atkinson, copyright 2000-2018) [UPSTREAM-VERIFIED]
- Authoritative upstream repository/dir: github.com/LibreOffice/dictionaries, `en/`
  [UPSTREAM-VERIFIED: official repo directory listing]
- LibreOffice inspection pin: master HEAD 38d96a4d54ec3449cf7f28cddae1fce32e2b15a7
  (snapshot, verified 2026-07-10); `en/` tree unchanged since last-touch
  e7f163feb2beaf526135132d8716e68e19d2716e (2025-03-31) [UPSTREAM-VERIFIED]
- Exact release/version: "Version 2020.12.07", released Mon Dec 7 2020
  [UPSTREAM-VERIFIED: en/README_en_US.txt]
- Exact `.dic` file: en_US.dic [UPSTREAM-VERIFIED: en/ listing]
- Exact `.aff` file: en_US.aff [UPSTREAM-VERIFIED: en/ listing]
- Exact README/metadata file: README_en_US.txt [UPSTREAM-VERIFIED]
- Exact license/notice files: en/license.txt, en/WordNet_license.txt, plus the
  SCOWL copyright + permission notice carried in en/README_en_US.txt
  [UPSTREAM-VERIFIED: en/ listing + README]
- Provenance/components: SCOWL size 60 (standard); en_US/en_CA/en_AU are the
  official Hunspell dictionaries; components named upstream include Ispell,
  WordNet, VarCon, 12Dicts, ENABLE, UKACD, MWords [UPSTREAM-VERIFIED: README]
- Immutable pin: LibreOffice/dictionaries has NO per-dictionary version tag; the
  version string lives in the README. Snapshot pin = master HEAD 38d96a4d… ;
  en_US.dic/.aff last-touch = 4fa94195b8136364dd40bf2b0366a0fe32058899 (2021-05-12).
  CAVEAT: the last-touch commit (2021-05-12) POSTDATES the stated "2020.12.07"
  version, and a last-touch commit is NOT presumed to be the version pin — the
  version string alone does not uniquely pin file content
  [UPSTREAM-VERIFIED commits; version-tag correspondence = TBD / NOT YET VERIFIED]
- Expected encoding: UTF-8 — README states files became UTF-8 in 2016 and the
  affix declares `SET UTF-8` [UPSTREAM-VERIFIED]
- `.aff` required by current raw-entry loader: NO (code fact: no `.aff` reading /
  no affix expansion). `.aff` remains relevant for provenance and for future full
  Hunspell behavior (affixed forms, declared encoding)
- `.dic` consumable by current loader: technically yes in raw-entry mode (base
  forms only; no affix expansion → more `not_validated`, the safe direction).
  NOT an approval to load
- Redistribution status: TBD / NOT YET VERIFIED — upstream permission notice
  appears to allow redistribution if notices are preserved, but this is
  `not independently legally determined`
- Local-only status: local-only remains the safest default [REPOSITORY-RECORDED]
- Approval status: candidate adoption / placement / loader use / dry run / clean
  promotion / condition JSONL / training = NO / NOT APPROVED
```

## Spanish Exact Resource Metadata
Same fields as English, plus regional-variant fields. The **regional variant is
unresolved and is not selected here.** Note the **source vs. package** distinction:
the pinned `v2.9` is an RLA-ES **source-project** release; the inspected variant
inventory is from the **separate LibreOffice package**, whose correspondence to
`v2.9` is unverified (evidence indicates RLA v2.6).

```
- Resource ID: spanish_rla_es_hunspell
- Resource family: RLA-ES / LibreOffice Spanish Hunspell (sbosio/rla-es)
- Language: spa
- Locale: TBD / NOT YET VERIFIED (regional variant unresolved — see Spanish Locale
  Decision Status)
- Authoritative upstream project (source): Recursos Lingüísticos Abiertos del
  Español (RLA-ES); Santiago Bosio + contributors [UPSTREAM-VERIFIED]
- Authoritative upstream repositories: github.com/sbosio/rla-es (SOURCE project)
  and github.com/LibreOffice/dictionaries `es/` (SEPARATE packaged distribution)
  [UPSTREAM-VERIFIED]
- RLA-ES source release/version: v2.9 ("Versión v2.9"); latest, not a prerelease;
  published 2025-01-02 (created 2025-01-01)
  [UPSTREAM-VERIFIED: sbosio/rla-es releases]
- RLA-ES source immutable reference: tag v2.9 → commit
  ea82c1214ead57740798acf66a1e18e5ac874c41 [UPSTREAM-VERIFIED: sbosio/rla-es tags]
- LibreOffice package inspection pin: master HEAD
  38d96a4d54ec3449cf7f28cddae1fce32e2b15a7 (snapshot, verified 2026-07-10);
  `es/README_hunspell_es.txt` last-touch 2b9183e45954cfd9d1638f838b461de1ce68b296
  (2020-10-28, message "Update all Spanish dictionaries to RLA v2.6")
  [UPSTREAM-VERIFIED]
- Source ↔ package correspondence: RLA-ES v2.9 ↔ inspected LibreOffice Spanish
  package = TBD / NOT YET VERIFIED. Evidence indicates the LibreOffice package is
  an RLA v2.6-era snapshot; whether any later commit advanced individual es/ .dic
  files past v2.6 was NOT verified this pass
- Available regional variants (LibreOffice `es/` package snapshot): es_AR, es_BO,
  es_CL, es_CO, es_CR, es_CU, es_DO, es_EC, es_ES, es_GQ, es_GT, es_HN, es_MX,
  es_NI, es_PA, es_PE, es_PH, es_PR, es_PY, es_SV, es_US, es_UY, es_VE — each with
  a matching `.dic` and `.aff` [UPSTREAM-VERIFIED: es/ listing at snapshot HEAD;
  NOT asserted to be "at the RLA-ES v2.9 pin"]
- Selected regional variant: TBD / NOT YET VERIFIED
- Exact `.dic`/`.aff` for chosen variant: pending locale selection (each listed
  variant has `<variant>.dic` + `<variant>.aff`) [UPSTREAM-VERIFIED naming pattern;
  selected file TBD]
- Exact README/metadata file: README_hunspell_es.txt [UPSTREAM-VERIFIED: es/ listing]
- Exact license/notice files: es/LICENSE.md, es/GPLv3.txt, es/LGPLv2.1.txt,
  es/LGPLv3.txt [UPSTREAM-VERIFIED: es/ listing]
- License alternatives: triple disjunctive GPLv3-or-later / LGPLv3-or-later /
  MPL 1.1-or-later — user may freely choose; the SYNONYM/thesaurus dictionary is
  separately LGPLv2.1 [UPSTREAM-VERIFIED: es/LICENSE.md]. NOTE: es/ ships GPLv3,
  LGPLv2.1, LGPLv3 text files; MPL 1.1 is offered per LICENSE.md but its full text
  file is not present in es/ [UPSTREAM-VERIFIED: es/ listing]
- Expected encoding: es_ES.aff declares `SET UTF-8` [UPSTREAM-VERIFIED for es_ES
  ONLY]; the encoding of every other regional variant's file is
  TBD / NOT YET VERIFIED (not individually inspected this pass)
- `.aff` required by current raw-entry loader: NO (code fact, as above); relevant
  for provenance / future full Hunspell behavior
- `.dic` consumable by current loader: technically yes in raw-entry mode (base
  forms only), once the selected variant's encoding is verified. NOT an approval
  to load
- Redistribution status: TBD / NOT YET VERIFIED — a permissive alternative exists,
  but the choice is unmade and `not independently legally determined`
- Local-only status: local-only remains the safest default [REPOSITORY-RECORDED]
- Locale-selection rationale: no approved rule exists; selecting a variant is a
  corpus-design / research-policy decision, not a metadata lookup, and must not use
  CALLHOME-derived evidence
- Locale-selection approval: NO / NOT APPROVED
- Approval status: candidate adoption / placement / loader use / dry run / clean
  promotion / condition JSONL / training = NO / NOT APPROVED
```

## Spanish Locale Decision Status
The package variant set is now `UPSTREAM-VERIFIED` (23 variants, above), but
**choosing one** is not a mere metadata lookup. It is:

- **partly a metadata question** — the variant set and each variant's files are
  identified (verified); but which is the intended *expected* lexicon is not;
- **primarily a corpus-design / linguistic-research decision** — a research-policy
  judgment about which Spanish variant should serve as the expected lexicon;
- **also a downstream operational choice** (which file the loader would read),
  gated behind placement/loader approval.

**The repository has no approved rule for choosing the locale.** Therefore the
variant stays `TBD / NOT YET VERIFIED` and locale-selection approval stays
`NO / NOT APPROVED`. The decision still required: an explicit, approved policy for
selecting the Spanish variant that does **not** rely on CALLHOME-derived token
distributions, vocabulary, names, frequencies, or regional forms.

## Exact Upstream File Inventory
"Required for current loader?" reflects the raw-entry loader scaffold (no `.aff`
expansion). "Verified?" is `UPSTREAM-VERIFIED` where confirmed from the official
listing/file this pass; otherwise `TBD / NOT YET VERIFIED`.

### English (`en_US`) — `LibreOffice/dictionaries` `en/` (snapshot HEAD `38d96a4d…`; `en/` last-touch `e7f163fe…`)
| Role | Exact upstream path/file | Required for current loader? | Verified? | Notes |
| ---- | ------------------------ | ---------------------------- | --------- | ----- |
| `.dic` | `en/en_US.dic` | yes (raw-entry mode) or a plain wordlist | UPSTREAM-VERIFIED | last-touch `4fa94195…` (2021-05-12); base forms only under current loader |
| `.aff` | `en/en_US.aff` | no | UPSTREAM-VERIFIED | not read/expanded; declares `SET UTF-8` |
| README | `en/README_en_US.txt` | no | UPSTREAM-VERIFIED | carries SCOWL copyright + permission notice |
| license | `en/license.txt` | no | UPSTREAM-VERIFIED | SCOWL/combined permission notice |
| notice | `en/WordNet_license.txt` | no | UPSTREAM-VERIFIED | WordNet component notice |
| release metadata | version `2020.12.07` in README; no per-dictionary tag | no | UPSTREAM-VERIFIED (with pin caveat) | last-touch ≠ version pin |

### Spanish — `LibreOffice/dictionaries` `es/` package (snapshot HEAD `38d96a4d…`; variant unselected)
| Role | Exact upstream path/file | Required for current loader? | Verified? | Notes |
| ---- | ------------------------ | ---------------------------- | --------- | ----- |
| `.dic` | `es/<variant>.dic` (23 variants incl. es_ES/es_MX/es_US) | yes (raw-entry mode) or a plain wordlist | UPSTREAM-VERIFIED (set); chosen file TBD | depends on unselected variant |
| `.aff` | `es/<variant>.aff` | no | UPSTREAM-VERIFIED (set); chosen file TBD | not read/expanded; only es_ES `SET UTF-8` verified |
| README | `es/README_hunspell_es.txt` | no | UPSTREAM-VERIFIED | last-touch `2b9183e4…` (2020-10-28, "RLA v2.6") |
| license | `es/LICENSE.md` | no | UPSTREAM-VERIFIED | triple disjunctive license |
| license texts | `es/GPLv3.txt`, `es/LGPLv2.1.txt`, `es/LGPLv3.txt` | no | UPSTREAM-VERIFIED | MPL 1.1 offered but no MPL text file present |
| source release (separate) | `sbosio/rla-es` tag `v2.9` → `ea82c12…` (2025-01-02) | no | UPSTREAM-VERIFIED | SOURCE project pin; correspondence to this package = TBD |

## License Pathway Evidence
- **License family identified** — `UPSTREAM-VERIFIED`, both. English: SCOWL
  copyright + permission notice (Kevin Atkinson; combined public-domain / BSD-style
  components), with `en/license.txt` and `en/WordNet_license.txt` present. Spanish:
  triple disjunctive **GPLv3-or-later / LGPLv3-or-later / MPL 1.1-or-later** with a
  free choice among them (thesaurus separately LGPLv2.1), per `es/LICENSE.md`.
- **Exact file-specific applicability verified** — **no**
  (`not independently legally determined`).
- **Pathway choice required** — Spanish requires selecting one of the three
  alternatives; English requires confirming the exact combined component-notice
  obligations from `en/license.txt` + README. Status: `TBD / NOT YET VERIFIED`.
- **Pathway choice approved** — `NO / NOT APPROVED`.
- **Redistribution implications** — depend on the confirmed/selected pathway and
  on preserving required notices; not determined here (`TBD / NOT YET VERIFIED`).
- **Local-only implications** — local-only storage remains the safest default
  regardless of pathway [REPOSITORY-RECORDED].

No legal conclusion is drawn beyond what the official upstream sources state.

## Notice and Attribution Evidence
- **Exact upstream notice files** — English: `en/license.txt`,
  `en/WordNet_license.txt`, and the SCOWL copyright + permission notice within
  `en/README_en_US.txt` [UPSTREAM-VERIFIED]. Spanish: `es/LICENSE.md`,
  `es/GPLv3.txt`, `es/LGPLv2.1.txt`, `es/LGPLv3.txt`, and
  `es/README_hunspell_es.txt` [UPSTREAM-VERIFIED].
- **Attribution names/projects** — English: SCOWL / Kevin Atkinson, with named
  components (Ispell, WordNet, VarCon, 12Dicts, ENABLE, UKACD, MWords). Spanish:
  RLA-ES (Recursos Lingüísticos Abiertos del Español), Santiago Bosio and
  contributors [UPSTREAM-VERIFIED].
- **Verbatim notice capture still required** — **yes**; the exact notice *files*
  are now identified, but their **verbatim text is not captured** here. Capture
  belongs in a future attribution/notice appendix once a variant/pathway is fixed.
- **Notices can be preserved locally** — expected yes, alongside any local file;
  not exercised here.
- **Repository notice text may be committed** — `TBD / NOT YET VERIFIED`; not in
  this branch. No upstream notice files are added and no long notice text is pasted.
- **Unresolved obligations** — the exact English combined-license obligations from
  `en/license.txt`; the Spanish selected-pathway notice requirements; the location
  of the future verbatim appendix.

## Redistribution and Local-Only Status
Each question separated; unresolved items stay `TBD / NOT YET VERIFIED`:

- **May the upstream resource be downloaded locally?** — `TBD / NOT YET VERIFIED`
  (not done here; a future, separately approved step).
- **May it be stored only in the ignored local directory?** — intended yes under
  policy (`data/resources/local_lexicons/`, gitignored), but only after placement
  approval; not exercised here.
- **May it be redistributed publicly?** — `TBD / NOT YET VERIFIED`
  (`not independently legally determined`; permissive alternatives exist upstream).
- **May a derived normalized wordlist be redistributed?** — `TBD / NOT YET
  VERIFIED`; derived files inherit source obligations and stay local/gitignored
  unless later explicitly approved.
- **May notices be committed?** — `TBD / NOT YET VERIFIED`; verbatim capture is a
  future appendix decision.
- **Is local-only use still the safest default?** — **yes** (unchanged posture).

## Intended Local Placement Mapping
Conceptual future mapping only; **nothing is created or placed.** The exact
upstream filenames are now verified, but local filenames are still **not** fixed
here (that is a placement-approval decision), and the Spanish variant is unchosen.

```
data/resources/local_lexicons/            (ignored; NOT populated by this branch)
  english/                                (conceptual; NOT CREATED)
    en_US.dic  (+ en_US.aff for provenance)   (verified upstream; NOT placed)
  spanish/                                (conceptual; NOT CREATED)
    <chosen-variant>.dic (+ .aff)         (variant TBD / NOT YET VERIFIED; NOT placed)
```

Actual mapping from verified upstream files to local paths requires a **separate
placement-approval decision** (`docs/callhome_lexicon_placement_approval_template.md`).
This branch creates no directories, places no files, and adds no `.gitkeep` or
sample file.

## Loader Compatibility Notes
Technical compatibility facts for the existing scaffold
(`src/cslm/data/callhome_lexicon_loader.py`); **descriptive only, no loader use is
approved:**

- **Plain wordlist mode** — one entry per line; blank lines and `#` comments
  ignored; returns raw entries.
- **Hunspell `.dic` raw-entry mode** — ignores a leading all-digits count line;
  strips affix flags after `/` (e.g. `hello/AB` → `hello`); returns raw entries.
- **Count-line handling** — first all-digits line treated as the Hunspell count
  line and skipped.
- **Affix-flag stripping** — yes (before-slash form only).
- **No `.aff` expansion** — `.aff` files are not read; affixes are not expanded.
- **No morphological generation** — no inflected forms are synthesized.
- **No automatic downloads** — the loader reads only an explicit caller-provided
  path.
- **Explicit caller-provided paths only** — no knowledge of `data/raw/callhome` or
  any resource location.

The verified `en/en_US.dic` could theoretically be consumed by the scaffold's
raw-entry mode, and the English resource declares UTF-8.

A future selected Spanish `<variant>.dic` could theoretically be consumed in the
same raw-entry mode, but the selected variant's encoding must first be verified.
This pass confirmed `SET UTF-8` only for `es_ES.aff`; it did not verify every
regional variant.

The loader still uses UTF-8 and performs no `.aff` expansion. These are technical
compatibility observations, not approval to load any resource. The Spanish locale
remains `TBD / NOT YET VERIFIED` and `NO / NOT APPROVED`.

## Remaining Unresolved Metadata
| Unresolved item | Why unresolved | Evidence still needed | Blocking gate | Recommended future action |
| --------------- | -------------- | --------------------- | ------------- | ------------------------- |
| Spanish regional variant | no approved locale-selection rule | approved corpus-design/research policy (no CALLHOME-derived evidence) | locale-selection approval | decide + approve a locale policy |
| RLA-ES v2.9 ↔ inspected LibreOffice `es/` package correspondence | package README last-touch indicates RLA v2.6, not v2.9 | official evidence tying the LibreOffice `es/` snapshot to a specific RLA-ES release | placement approval | verify the package's RLA version at a pinned commit |
| Spanish chosen-variant exact file + its encoding | depends on the unselected variant; only es_ES encoding checked | that variant's `.dic`/`.aff` + `SET` line at a pin | placement approval | verify after locale approval |
| English content-vs-version pin | no per-dictionary tag; `en_US.dic` last changed 2021-05-12, after the stated `2020.12.07` | a chosen immutable commit sha + a note that the version string ≠ tag | placement approval | pin a specific commit sha |
| final license pathway | Spanish disjunctive choice unmade; English exact combined obligations not enumerated | pathway selection + `en/license.txt` obligation read | placement approval | record selected pathway + obligations |
| redistribution determination | `not independently legally determined` | legal/notice review | placement approval | conservative local-only until determined |
| verbatim notice capture + appendix location | deferred to a future appendix | selected variant/pathway + verbatim notices | placement approval | create appendix when files chosen |

## Explicit Non-Approval Gates
This record grants **none** of the following, for **either** candidate:

| Gate | English | Spanish |
| ---- | ------- | ------- |
| candidate adoption | NO / NOT APPROVED | NO / NOT APPROVED |
| local placement | NO / NOT APPROVED | NO / NOT APPROVED |
| loader use | NO / NOT APPROVED | NO / NOT APPROVED |
| aggregate dry run | NO / NOT APPROVED | NO / NOT APPROVED |
| clean promotion | NO / NOT APPROVED | NO / NOT APPROVED |
| condition JSONL | NO / NOT APPROVED | NO / NOT APPROVED |
| tokenizer/dataset construction | NO / NOT APPROVED | NO / NOT APPROVED |
| training | NO / NOT APPROVED | NO / NOT APPROVED |

## Failure and Stop Conditions
Work must **stop** if:

- an exact source is **guessed**
- a version is **inferred from a filename** without authoritative confirmation
- a file path is **inferred** rather than verified
- a license claim **exceeds** upstream evidence
- a locale is selected using **CALLHOME-derived material**
- a locale is selected **without an approved policy**
- files would be **downloaded** and saved locally
- files would be **placed**
- **hashes** would be computed
- **real loader use** is introduced
- **validator use** is introduced
- **dry-run wiring** is introduced
- **clean promotion** is proposed
- **condition JSONL or training** is proposed
- **CALLHOME could route to `CsCont`**

## Reviewer Checklist
- [ ] every exact fact cites an official upstream source or a repository doc, with a label
- [ ] upstream sources are authoritative (official repos / release / tag / commit / license files)
- [ ] LibreOffice snapshot HEAD and per-file last-touch commits are recorded, and last-touch is not treated as a version pin
- [ ] RLA-ES source release is distinguished from the LibreOffice package snapshot
- [ ] search was used only to locate official sources; facts read from the source itself
- [ ] unresolved items remain explicit (`TBD / NOT YET VERIFIED`)
- [ ] no lexicon artifact was saved to disk, copied, placed, loaded, or hashed
- [ ] no CALLHOME-derived evidence was used
- [ ] Spanish locale status is represented accurately (unresolved; not selected)
- [ ] Spanish encoding claim is scoped to es_ES only
- [ ] license claims are conservative (`UPSTREAM-VERIFIED` statements, not legal determinations)
- [ ] notice claims are conservative (files identified; verbatim not captured)
- [ ] loader notes are descriptive only (no loader use approved)
- [ ] all operational approvals remain `NO / NOT APPROVED`
- [ ] real pipeline behavior is unchanged

## Next Approved Step
The next step depends on the result of review:

- **If exact metadata remains unresolved** (the Spanish locale, the RLA-ES↔package
  correspondence, the English content pin, the license-pathway selection),
  **revise this record in a future docs PR** as those are decided/verified.
- **If exact files and license/notice pathways become sufficiently resolved**
  (English is now largely verified; Spanish awaits a locale policy and a package
  correspondence check), **create a separate placement-approval decision PR** using
  `docs/callhome_lexicon_placement_approval_template.md`.
- **Do not place resources automatically** after this branch.

## Final Gate Status
- **Metadata is now more precise (English files/version/encoding pinned to a
  LibreOffice snapshot; Spanish source release, package variant-set, and license
  verified upstream) — with the RLA-ES source vs. LibreOffice package distinction
  made explicit.**
- **No resource is approved.**
- **No resource is placed.**
- **No resource is loaded.**
- **No real validation occurs.**
- **All CALLHOME rows remain blocked** (`not_validated`; `clean` stays zero).
- **The gate remains closed** until each later approval is separately granted.
