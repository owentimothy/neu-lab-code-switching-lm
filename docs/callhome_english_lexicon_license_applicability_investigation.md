# English Lexicon License Applicability Investigation

## Status
- **Docs-only investigation record, not implementation.** No code changes.
- **Repository governance and evidence record — not legal advice.** No legal
  determination is made.
- **No lexicon artifact was downloaded, saved, placed, hashed, loaded, or used.**
  The local resource directory (`data/resources/local_lexicons/`) is not created or
  populated; `.gitignore` is not edited.
- **Read-only upstream inspection only.** Official upstream repository/API/raw
  content was inspected read-only at the selected immutable snapshot; **no upstream
  file was saved into this project.**
- **No CALLHOME transcript content or CALLHOME-derived evidence was inspected or
  used.**
- **The real pipeline remains unchanged** (`default_source_validation` only;
  validator/loader not wired in). Every real CALLHOME row stays `not_validated`;
  `clean` stays zero.
- **All operational approvals remain `NO / NOT APPROVED`.**

## Decision Status
```text
Investigation conclusion:
Category C — applicability unresolved

English resource selected for continued governance:
YES / APPROVED

English license-and-notice pathway:
NO / NOT APPROVED

Operational adoption or use:
NO / NOT APPROVED
```

This is a **repository governance and evidence record, not legal advice**. It
records authoritative upstream evidence only. It does **not** approve a license
pathway, redistribution, resource placement, loader use, validation, clean
promotion, condition construction, or training.

## Question Investigated
> What artifact or package component does `en/license.txt` govern at the selected
> LibreOffice snapshot, and how — if at all — does its GPLv2 text apply to
> `en_US.dic`, `en_US.aff`, or their distribution?

## Selected Resource
```text
Resource ID:
english_en_us_hunspell

Selected immutable snapshot:
38d96a4d54ec3449cf7f28cddae1fce32e2b15a7

Selected dictionary files:
en/en_US.dic
en/en_US.aff
```

The selected `en/` object at this snapshot is a **bundled multi-dictionary
LibreOffice extension** (it contains `en_US`, `en_GB`, `en_CA`, `en_AU`, `en_ZA`
spelling dictionaries, `en_US`/`en_GB` hyphenation, an `en_US` thesaurus, and
Lightproof grammar tooling), within which the selected artifact is the `en_US`
`.dic`/`.aff` pair.

## Direct File Evidence
Documented conservatively; presence of a file is distinguished from an explicit
statement of what it governs.

### `en/license.txt`
- Contains the **complete GNU GPL Version 2 text** (Free Software Foundation,
  1991).
- Is present **at the package level** of the bundled English extension.
- Contains **no file-specific statement** naming `en_US.dic` or `en_US.aff`.
- Is **not** the SCOWL permission notice.
- Its **applicability to the selected `en_US` files remains unresolved**.

### `en/README_en_US.txt`
- Identifies the **en_US Hunspell Dictionary, Version `2020.12.07`**.
- States **SCOWL derivation**.
- Carries the **Kevin Atkinson / SCOWL copyright and permission notice**.
- Carries or enumerates **component/source notices** (Ispell, WordNet, VarCon,
  12Dicts, ENABLE, UKACD, Moby/MWords).
- **Does not explain** the applicability of the package-level `en/license.txt`.

### `en/README.txt`
- Identifies itself as an **`OpenOffice.org Hunspell en_US dictionary`**,
  **`2010-03-09` release** — a historical/legacy **en_US** provenance record.
- States that the **en_US wordlist** is based on Kevin Atkinson's Pspell/Aspell
  material and is **covered by the original LGPL**.
- States that the **affix file** is derived from Geoff Kuenning's Ispell material
  and is **covered by BSD**.
- **Does not explain** its relationship to the newer `README_en_US.txt`.
- **Does not explain** the applicability of the package-level `en/license.txt`.
- This is an **en_US** record. It **must not** be labelled en_GB.

### `en/README_en_GB.txt`
- **Separately** describes the **en_GB** lineage (Atkinson/LGPL-origin wordlist,
  extensively updated by David Bartlett, Brian Kelk, Andrew Brown, and
  Marco A.G. Pinto).
- **Must not** be used as direct evidence of the license of **en_US**.
- Included **only** to demonstrate that the extension **bundles components with
  separate provenance records**.

### `en/WordNet_license.txt`
- Contains the **separate WordNet 2.1 / Princeton University notice**.
- **Does not** establish GPLv2 applicability to the dictionary files.

## Historical Evidence

### 2010 consolidation
```text
Commit: 940c58d460f06e7fc33bea1ecdae7767cade28e2
Message: cws dict321: #i10007# en dictionaries update
Author/date: Ivo Hinkelmann (ihi@openoffice.org), 2010-05-07
```
- It **consolidated / reorganized** English dictionary resources (English files
  were moved into the combined `en/` package; `en_US.dic`, `en_US.aff`, and
  `README_en_US.txt` appear as **renamed** from an older per-locale path).
- The package-level license file is **traceable at least as far back as** this
  state.
- The commit **does not explicitly map GPLv2** to `en_US.dic` or `en_US.aff`.
- It is **not proven** to be the **original creation** of the GPLv2 file; earlier
  history may exist behind the OpenOffice.org → git import boundary and was not
  directly established.

### 2012 structural move
```text
Commit: a4473e06b56bfe35187e302754f6baaa8d75e54f
Message: move dictionaries structure one directory up
Author/date: Norbert Thiebaud, 2012 (authored 2012-09-01; committed 2012-10-16)
```
- It is a **repository structural move** (the package moved up one directory).
- It **does not clarify** license applicability.

### Historical en_AU GPL note
Precisely:
- The **2006 GPL conversion statement** (`"I have also decided to change the
  license to the GNU General Public License - as per section 3 of the LGPL."`,
  in the changelog "Notes for 0.1", 2006-08-03) concerns an **en_AU fork**.
- The **en_AU fork descended from en_GB and earlier LGPL-origin material**.
- It is evidence that **at least one bundled English lineage was relicensed to
  GPL**.
- It **does not explicitly apply to en_US**.
- It **does not prove** why the current package-level `en/license.txt` exists.
- It **must not** be attributed to **Lightproof**, to every English dictionary, or
  to the complete LibreOffice English extension.

### 2019 LGPL text note
Only what is directly established:
- The changelog says an **`LGPL_V3 License .txt`** was **added to the extension**
  (`"Added the LGPL_V3 License .txt into the Extension."`, MAGP, 2019-03-01).
- This demonstrates **heterogeneous package-level license material**.
- The **exact corresponding filename and its current disposition were not directly
  verified**; this record therefore **does not claim** which current file, if any,
  implements that note.

## Descriptor and Manifest Evidence

### `en/description.xml`
- Identifies the **extension** (`org.openoffice.en.hunspell.dictionaries`) and its
  **publisher** (Marco A.G. Pinto).
- Contains **no explicit license element** linking `en/license.txt` to the
  dictionaries (no `<registration>` / `<simple-license>` / `<license-text>`).

### `en/META-INF/manifest.xml`
- Registers **configuration and component files** (`dictionaries.xcu`,
  `package-description.txt`, `dialog/OptionsDialog.xcs`/`.xcu`,
  `Lightproof.components`, `Linguistic.xcu`).
- **Does not reference** `en/license.txt`.
- **Does not resolve** file-specific license applicability (it does not register
  the `.dic`/`.aff` files either).

### `en/dictionaries.xcu`
- Registers the **dictionary resources** (the English `.dic`/`.aff`/`.dat` files
  and their locales).
- Contains **no explicit license mapping**.

### `en/package-description.txt`
- Describes the **bundled variants** (`en_AU`, `en_CA`, `en_GB`, `en_US`, `en_ZA`).
- Contains **no applicability statement** for `en/license.txt`.

**Absence of a reference is not proof that a license does not apply.** The
descriptors and manifests not referencing `en/license.txt` does **not** establish
that GPLv2 fails to govern the dictionary files; it only establishes that these
files provide **no explicit mapping** either way.

## Competing or Overlapping Upstream Records
| Evidence                 | Explicit statement           | Scope established                     | Remaining ambiguity                    |
| ------------------------ | ---------------------------- | ------------------------------------- | -------------------------------------- |
| `en/README_en_US.txt`    | SCOWL derivation and notices | current version-specific en_US record | relationship to GPLv2 file             |
| `en/README.txt`          | LGPL wordlist + BSD affix    | historical en_US record               | relationship to current en_US files    |
| `en/license.txt`         | GPLv2 text                   | text identity only                    | governed artifact unknown              |
| `en/WordNet_license.txt` | WordNet notice               | WordNet component                     | relationship to final wordlist         |
| en_AU changelog note     | en_AU fork changed to GPL    | en_AU historical fork                 | no explicit en_US applicability        |
| descriptors/manifests    | no license mapping           | package registration facts            | absence does not resolve applicability |

## Evidence Matrix
| Evidence source | Exact ref/path | What it explicitly establishes | What it does not establish | Confidence |
| --------------- | -------------- | ------------------------------ | -------------------------- | ---------- |
| Pinned `en/license.txt` | `en/license.txt` @ `38d96a4d…` | It is the complete GNU GPL v2 text (FSF, 1991), present at package level | Which artifact/component it governs; any link to `en_US.dic`/`en_US.aff` | DIRECT (content); NO EXPLICIT EVIDENCE FOUND (applicability) |
| Pinned `en/README_en_US.txt` | `en/README_en_US.txt` @ `38d96a4d…` | Current en_US `2020.12.07`; SCOWL derivation; SCOWL + component notices | Applicability of the package-level GPLv2 file to en_US | DIRECT (en_US = SCOWL notices) |
| Pinned `en/README.txt` | `en/README.txt` @ `38d96a4d…` | Legacy en_US (`2010-03-09`); wordlist LGPL (Atkinson), affix BSD (Ispell) | Its relationship to the current en_US files or to `en/license.txt` | DIRECT (self-identified en_US record) |
| Pinned `en/README_en_GB.txt` | `en/README_en_GB.txt` @ `38d96a4d…` | Separate en_GB lineage (Atkinson/LGPL; later maintainers) | Anything about en_US licensing | DIRECT (separate provenance; not en_US evidence) |
| Pinned `en/WordNet_license.txt` | `en/WordNet_license.txt` @ `38d96a4d…` | Separate WordNet 2.1 / Princeton notice | GPLv2 applicability to the dictionary files | DIRECT |
| 2010 consolidation commit | `940c58d4…` (2010-05-07, Hinkelmann) | `en/license.txt` is traceable at least this far back; en_US.* consolidated/renamed | That this commit created the GPLv2 file; any GPLv2→en_US mapping | STRONG (traceability); LIMITED (origin); NO EXPLICIT EVIDENCE FOUND (mapping) |
| 2012 structural move commit | `a4473e06…` (2012, Thiebaud) | The package (incl. `license.txt`) moved up one directory; unmodified since | Any applicability statement | DIRECT (move only) |
| en_AU GPL changelog note | `en/changelog.txt` "Notes for 0.1" (2006-08-03) | An en_AU fork (from en_GB + earlier LGPL material) was relicensed to GPL per LGPL §3 | That this applies to en_US, Lightproof, or the whole extension; why `en/license.txt` exists | STRONG (en_AU lineage); NO EXPLICIT EVIDENCE FOUND (en_US applicability) |
| 2019 LGPL_V3 changelog note | `en/changelog.txt` (MAGP, 2019-03-01) | An `LGPL_V3 License .txt` was added to the extension (heterogeneous license material) | Which current file implements it; any GPLv2→en_US mapping | LIMITED |
| Extension descriptor | `en/description.xml` @ `38d96a4d…` | Extension identity/publisher; no license element referencing `license.txt` | That `license.txt` is / is not the governing license | STRONG (no mapping present) |
| OXT manifest | `en/META-INF/manifest.xml` @ `38d96a4d…` | Registers `.xcu`/Lightproof/`package-description.txt`; not `license.txt`, not `.dic`/`.aff` | Any file-specific license applicability | STRONG (no mapping present) |
| Dictionary registration | `en/dictionaries.xcu` @ `38d96a4d…` | Registers the English `.dic`/`.aff`/`.dat`; no license reference | Any license applicability for the registered files | STRONG (no mapping present) |
| Package description | `en/package-description.txt` @ `38d96a4d…` | Lists bundled English variants; no license statement | Any `license.txt` applicability | STRONG (no mapping present) |
| Search: explicit "en_US dictionary files are GPLv2" | all sources above | — | No source explicitly states en_US.dic/.aff are GPLv2 | NO EXPLICIT EVIDENCE FOUND |
| Search: explicit "license.txt is bundled-only, does not govern .dic/.aff" | all sources above | — | No source explicitly states this either | NO EXPLICIT EVIDENCE FOUND |

## Final Finding
```text
Category C — applicability unresolved
```

- Authoritative upstream sources **identify the contents** of the relevant files
  (`en/license.txt` = GPLv2 text; `README_en_US.txt` = SCOWL notices; legacy
  `README.txt` = LGPL wordlist + BSD affix; `WordNet_license.txt` = WordNet
  notice).
- Authoritative sources provide **multiple historical and component-specific
  provenance statements** (2010 consolidation, 2012 move, the 2006 en_AU GPL note,
  the 2019 LGPL_V3 note).
- Those statements **do not provide a direct mapping** from the GPLv2
  `en/license.txt` to the selected `en_US.dic` or `en_US.aff`.
- The **two en_US README records** (legacy LGPL/BSD vs. current SCOWL) create an
  **additional provenance/applicability ambiguity**.
- **No legal inference is made.**
- The **English license-and-notice pathway remains blocked.**

## Approval Matrix
| Gate                                                  | Status            |
| ----------------------------------------------------- | ----------------- |
| English resource selected for continued governance    | YES / APPROVED    |
| License applicability investigation completed         | YES / RECORDED    |
| `en/license.txt` content identified                   | YES / VERIFIED    |
| `en/license.txt` file-specific applicability resolved | NO / UNRESOLVED   |
| English license-and-notice pathway                    | NO / NOT APPROVED |
| Independent legal determination                       | NOT MADE          |
| Public redistribution                                 | NO / NOT APPROVED |
| Resource download                                     | NO / NOT APPROVED |
| Local placement                                       | NO / NOT APPROVED |
| Hash computation                                      | NO / NOT APPROVED |
| Loader use                                            | NO / NOT APPROVED |
| Aggregate dry run                                     | NO / NOT APPROVED |
| Real CALLHOME validation                              | NO / NOT APPROVED |
| Clean promotion                                       | NO / NOT APPROVED |
| Condition construction                                | NO / NOT APPROVED |
| Tokenization                                          | NO / NOT APPROVED |
| Model training                                        | NO / NOT APPROVED |

## Pipeline and Safety State
```text
CALLHOME English
→ potentially EnglishMono
→ potentially the English portion of MonoCont
→ never CsCont
```

- **Bangor remains the only final source for `CsCont`.**
- **No CALLHOME content or CALLHOME-derived evidence was used.**
- **No lexicon artifact was downloaded, saved, placed, hashed, loaded, or used.**
- **All 88,404 CALLHOME rows remain `not_validated`.**
- **`validated`, `lexicon_exact_match`, `clean`, and all condition candidate counts
  remain zero.**

## Next Step
**Local placement approval remains blocked.** The next legitimate action is **not**
another approval decision. It is one of:

1. **obtain a direct authoritative upstream clarification** of the applicability of
   the package-level GPLv2 file (`en/license.txt`) to the selected `en_US` files; or
2. **select and govern an alternative English lexical resource** with an
   unambiguous, file-specific license pathway.

**This branch does not choose between those paths.**
