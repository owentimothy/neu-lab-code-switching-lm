# CALLHOME English SCOWL / ESDB Candidate Evidence

## Status
```text
Candidate-evidence conclusion:
Category B — promising but material governance questions remain

Strongest proposed candidate:
Direct SCOWL / English Speller Database (ESDB)

Proposed immutable source pin:
Release tag:  rel-2026.02.25
Commit:       7e99edab8e32f9f9ea2b15f249ca8d4d67237410

Existing LibreOffice selection:
YES / REMAINS SELECTED PENDING REVIEW

ESDB replacement decision:
NOT MADE

Operational adoption or use:
NO / NOT APPROVED
```

This is a **repository governance record, not legal advice.** It records corrected
candidate evidence only. This branch **remains evidence-only**: it does **not**
select, approve, download, generate, place, load, or use an ESDB lexicon, and it
does **not** replace the currently selected LibreOffice candidate.

- **Read-only upstream inspection only.** Official upstream repository/API/raw and
  documentation content was inspected read-only; **no ESDB source, database,
  release asset, or wordlist was downloaded or saved into this project.**
- **No build or extraction command was executed** (`make`/`scowl` not run).
- **No hash was computed.**
- **No CALLHOME transcript content or CALLHOME-derived evidence was inspected or
  used.**
- **The real pipeline remains unchanged** (`default_source_validation` only;
  validator/loader not wired in). Every real CALLHOME row stays `not_validated`;
  `clean` stays zero.
- **All operational approvals remain `NO / NOT APPROVED`.**

## Problem Being Addressed
The selected **LibreOffice `en_US`** candidate remains **operationally blocked**:
its `en/` package carries a package-level **GPLv2 `license.txt` whose file-specific
applicability to `en_US.dic`/`en_US.aff` is unresolved** (Category C in
`docs/callhome_english_lexicon_license_applicability_investigation.md`). The prior
candidate scan (`docs/callhome_english_alternative_lexicon_candidate_scan.md`)
identified **Direct SCOWL / ESDB** as the strongest alternative. This record is the
corrected evidence pass that proposes one exact ESDB candidate configuration and
determines whether it can advance to a later resource-selection review. It selects
nothing.

## Proposed Extraction Command
```bash
PYTHONIOENCODING=utf-8 \
./scowl --db scowl.db word-list 60 A 1 \
  --categories= \
  --wo-poses=abbr \
  --wo-pos-categories=nonword,wordpart
```

This is a **proposed reproducible candidate command, not an approved command.** It
must **not** be executed in this branch.

## Command Behavior
The `word-list` subparser uses **both** query arguments (`addQueryArguments`) and
word-filter arguments (`addFilterArguments`). The default word-filter behavior at
the pinned commit is:

```text
space=False
hyphen=False
dot=strip
digits=False
special=False
apostrophe=middle
deaccent=False
```

Therefore, by default:

- **Open compounds containing spaces are excluded.**
- **Hyphenated entries are excluded.**
- **No external U+0020 space filter is required** (this corrects the earlier
  first-pass claim).
- **`--hyphen` would be required** to include hyphenated entries.
- **Digits and special-symbol entries are excluded.**
- **Internal apostrophes are permitted** (`apostrophe=middle`).
- **Trailing dots on abbreviations are stripped by default** (`dot=strip`).
- **Diacritics remain preserved** because `--deaccent` is not used.

The conservative candidate **intentionally omits**:

```text
--space
--hyphen
--digits
--special
--deaccent
```

## Correct Option Spelling (README ↔ implementation mismatch)
At the pinned implementation, the supported exclusion option is:

```text
--wo-poses=abbr
```

The README example using `--poses-to-exclude=abbr` **does not match** the argparse
implementation at this commit (which exposes `--poses` / `--wo-poses`). This
**README/implementation mismatch is explicit**, and the **implementation is
authoritative**.

## Category and POS Policy
- `--categories=` restricts the SCOWL category field to the **default empty
  category**.
- `--wo-poses=abbr` **excludes abbreviation POS entries**.
- `--wo-pos-categories=nonword,wordpart` **excludes**:
  - prefixes;
  - suffixes;
  - Roman numerals and other non-word entries;
  - multi-word parts;
  - multi-word endings.

The policy **retains**:

- contractions;
- pronouns;
- determiners;
- conjunctions;
- prepositions;
- interjections;
- nouns;
- verbs;
- adjectives;
- adverbs;
- inflected surface forms.

(Supporting facts: `libscowl/_constdata.py` defines
`POS_CATEGORIES = ('', 'nonword', 'special', 'wordpart')` with `nonword` ⊇
`{pre, suf, x}` and `wordpart` ⊇ `{wp, we}`; POS `abbr` = abbreviation, POS `s` =
contraction; `libscowl/_search.py` applies no restriction when a query field is
unset — `if members is None: return`.)

## Output Format
The generated wordlist is expected to be:

- **UTF-8** when `PYTHONIOENCODING=utf-8` is set;
- **one bare entry per line**;
- **sorted** using Python sorting (`words = sorted(...)`);
- **duplicate-free** (`if w != prev: print(w)`);
- **free of a numeric count header**;
- **free of Hunspell affix flags**;
- **free of comments and metadata on stdout**;
- **compatible with `load_plain_wordlist`** (`src/cslm/data/callhome_lexicon_loader.py`).

**Locale does not control Python string sorting** (Python `sorted()` orders by
Unicode code point, deterministically). The explicit **encoding environment
(`PYTHONIOENCODING=utf-8`) controls stdout encoding**.

## Source-Build Completeness
- **`data/scowl-pre.txt` exists at the pinned commit** (~15.6 MB).
- Required committed data and source files are present (`data/basic`, `data/coca`,
  `data/compounds`, `data/variants`, `libscowl/*.sql`, `combine.py`, `Makefile`,
  `scowl`).
- **`make` builds `scowl.db` through `combine.py`** (`./combine.py create-db
  scowl.db`); `scowl.txt` via `./scowl export --db scowl.db`.
- **The build does not require CALLHOME data** and needs **no network access**.
- **The source-generated model can be performed offline** from the pinned source
  tree.
- **Exact byte-for-byte stability across Python and SQLite environments has not yet
  been demonstrated.**

`make` was **not** run in this branch.

## Official Release Assets
`rel-2026.02.25` is described as a **dictionary-only release** and includes official
pre-generated assets such as:

```text
hunspell-en_US-2026.02.25.zip
hunspell-en_US-large-2026.02.25.zip
aspell6-en-2026.02.25-0.tar.bz2
```

(plus `en_AU` / `en_CA` / `en_GB-ise` / `en_GB-ize` / `-large` variants.)

- **No official plain-wordlist asset was identified.**
- **No official published checksum was identified.**
- The official **Hunspell asset is operationally simpler to pin**.
- Under the current loader, which **does not expand `.aff` rules**, the Hunspell
  `.dic` would **not provide the same enumerated surface-form coverage** as the
  source-generated plain wordlist.

No release asset was downloaded.

## Artifact-Model Comparison

### Model 1 — source-generated plain wordlist
```text
immutable source commit
+ pinned build environment
+ make
+ exact scowl extraction command
+ local SHA-256 after future approval
```
**Advantages:**
- plain wordlist;
- enumerated inflected surface forms;
- directly compatible with `load_plain_wordlist`;
- technically preferable for the current exact-match / no-affix-expansion validator.

**Unresolved:**
- exact Python version;
- exact SQLite version;
- byte-for-byte reproducibility demonstration;
- proper-name policy;
- final selection approval.

### Model 2 — official pre-generated Hunspell asset
```text
immutable release tag
+ exact asset filename
+ local SHA-256 after future approval
```
**Advantages:**
- official pre-generated release asset;
- simpler immutable identity.

**Limitation:**
- the current loader strips flags but **does not expand `.aff` rules**;
- therefore surface-form coverage may be **substantially lower**.

### Recommendation
```text
Model 1 is technically preferred for further governance review.

Model 1 is not selected or approved in this branch.
```

## Proper-Name Limitation
The upstream README POS-CLASS section warns that **POS-class tagging cannot reliably
filter all proper nouns** ("the classes can't be used to reliably filter out proper
nouns"). Name-related classes include:

```text
person
surname
place
name
name?
upper?
```

**Complete deterministic proper-name exclusion cannot be guaranteed at this
release.** This policy must **not** be decided using CALLHOME contents.

Two possible future governance positions (neither selected here):

```text
Policy A:
Accept residual size-60 proper-name material and rely on:
- all-token exact-match validation;
- cross-language lexicon overlap blocking;
- conservative false-negative behavior.

Policy B:
Keep ESDB blocked until a stronger proper-name exclusion policy exists.
```

**Neither Policy A nor Policy B is selected in this branch.**

## Notice Pathway
At the proposed **American size-60** output (governance reading of upstream
evidence, **not legal advice**):

- the **primary Kevin Atkinson SCOWLv2 notice applies**;
- the permission **explicitly covers wordlists created from SCOWLv2**;
- **Australian notice conditions are not triggered** because dialect `A` is used,
  not `D`;
- **UKACD conditions are not triggered** because size 60 is **not larger than 80**;
- COCA is an NDA-restricted **source** (not an obligation attached to a
  non-Australian ≤80 speller output under the upstream conditional).

The exact notice bundle **remains proposed, not operationally approved.**

## Remaining Material Questions
1. whether Model 1 should replace the currently selected LibreOffice candidate;
2. whether residual proper-name content is acceptable;
3. exact Python version to pin;
4. exact SQLite version to pin;
5. whether the source build and extraction are byte-identical across the pinned
   environment;
6. final filename and local storage metadata;
7. future locally computed SHA-256;
8. final notice-bundle approval;
9. final size-60 / variant-1 selection approval.

**Resolved (explicitly not open questions):**
- `word-list` **does** wire query/filter arguments;
- `--categories=` **is valid** (restricts to the default empty category);
- **no external space filter is needed** (default filter excludes spaces);
- `--wo-poses=abbr` **is the correct implementation option** (not
  `--poses-to-exclude`).

## Candidate Specification Table
| Field | Proposed value | Status |
| ----- | -------------- | ------ |
| Resource ID | `english_scowl_esdb_en_us` | PROPOSED |
| Official upstream | `en-wl/wordlist` (ESDB), `wordlist.aspell.net` | RESOLVED |
| Release tag | `rel-2026.02.25` | PROPOSED |
| Immutable commit | `7e99edab8e32f9f9ea2b15f249ca8d4d67237410` | PROPOSED |
| Source artifact model | Model 1 (source-generated plain wordlist) | PROPOSED |
| Source files | `data/scowl-pre.txt` (+ `data/*`), `libscowl/*`, `combine.py`, `Makefile`, `scowl` | RESOLVED |
| Build command | `make` → `./combine.py create-db scowl.db` (offline) | PROPOSED |
| Extraction command | `PYTHONIOENCODING=utf-8 ./scowl --db scowl.db word-list 60 A 1 --categories= --wo-poses=abbr --wo-pos-categories=nonword,wordpart` | PROPOSED |
| Dialect | `A` (American) | PROPOSED |
| Size | `60` | PROPOSED |
| Variant level | `1` (include) | PROPOSED |
| Category policy | `--categories=` (default empty category) | PROPOSED |
| Contraction policy | retain (POS `s`) | RESOLVED |
| Abbreviation policy | exclude via `--wo-poses=abbr` | RESOLVED |
| Inflection policy | retain inflected surface forms | RESOLVED |
| Proper-name policy | complete exclusion not guaranteed; Policy A/B undecided | UNRESOLVED |
| Open-compound policy | excluded by default (no `--space`) | RESOLVED |
| Hyphen policy | excluded by default (omit `--hyphen`) | RESOLVED |
| Diacritic policy | preserved (no `--deaccent`) | PROPOSED |
| Apostrophe policy | internal permitted (`apostrophe=middle`) | RESOLVED |
| Encoding | UTF-8 via `PYTHONIOENCODING=utf-8` | PROPOSED |
| Sorting | Python `sorted()` (code-point; locale-independent) | RESOLVED |
| Duplicate policy | duplicate-free | RESOLVED |
| Output filename | `scowl_en_US_size60_var1.txt` | PROPOSED |
| Notice bundle | primary Atkinson SCOWLv2 notice only (American ≤80) | PROPOSED |
| Future SHA-256 | compute only after future approval | NOT APPLICABLE |
| Local-only storage | gitignored `data/resources/local_lexicons/` | PROPOSED |
| Operational approval | — | NO / NOT APPROVED |

## Evidence Matrix
| Topic | Exact source/ref | What it establishes | Remaining uncertainty | Confidence |
| ----- | ---------------- | ------------------- | --------------------- | ---------- |
| Immutable pin | tag `rel-2026.02.25` → `7e99edab…` (target `v2`) | Stable, immutable, v2-lineage release pin | final governance selection | DIRECT |
| v2 HEAD instability | `commits/v2` (`1e5b7d3a…`, 2026-06-24) | Recent June-2026 commits rework extraction semantics (variant renumber, adjust cmd) | — | DIRECT |
| word-list wiring | `libscowl/__main__.py` word-list parser | `word-list` calls `addQueryArguments(..., usePositional=True)` and `addFilterArguments(...)` | — | DIRECT |
| Word-filter defaults | `libscowl/_search.py` `wordFilterRegEx()` | space & hyphen excluded by default; apostrophe middle; dot strip; digits/special off; deaccent off | — | DIRECT |
| Abbreviation option | `libscowl/__main__.py` opts + `_constdata.py` `abbr` | correct option is `--wo-poses=abbr` | — | DIRECT |
| README↔impl mismatch | README `--poses-to-exclude` vs argparse `--poses/--wo-poses` | README wording is stale; implementation authoritative | — | DIRECT |
| Default query and empty-category behavior | `libscowl/__main__.py` `Lst`; `libscowl/_search.py` `queryString` / `addSetQueryClause` | unset fields impose no restriction; `--categories=` selects the default empty category | — | DIRECT |
| POS categories | `libscowl/_constdata.py` `POS_CATEGORIES` | nonword={pre,suf,x}; wordpart={wp,we}; abbr; s=contraction | — | DIRECT |
| Function/contraction/inflection retention | `libscowl/_constdata.py` POS set | pronouns/preps/dets/conj/interj + contractions + inflections retained | — | DIRECT |
| Output format | `libscowl/__main__.py` `printWordList` | sorted, unique, one bare line, no header; stdout encoding env-dependent | stderr-diagnostics routing not separately confirmed | DIRECT |
| Proper-name limitation | `README.md` POS-CLASS + warning | classes person/surname/place/name…; proper nouns not reliably filterable | complete exclusion impossible | DIRECT |
| Source-build completeness | `data/` listing; `Makefile` | `scowl-pre.txt` present; `make` builds `scowl.db` offline | byte-for-byte determinism | DIRECT (inputs); LIMITED (determinism) |
| Release assets | `releases/tags/rel-2026.02.25` | dictionary-only; hunspell/aspell zips; no plain-wordlist asset; no checksums | — | DIRECT |
| Hunspell-asset limitation | loader (`callhome_lexicon_loader.py`) | loader reads raw `.dic` entries but does not expand `.aff` rules, so many generated surface forms would be unavailable | — | DIRECT |
| Notice pathway | `Copyright` @ pin | American ≤80 ⇒ primary Atkinson notice; AU only for `D`; UKACD only >80 | legal (out of scope) | DIRECT |

## Approval Matrix
| Gate                                        | Status            |
| ------------------------------------------- | ----------------- |
| SCOWL evidence pass completed               | YES / RECORDED    |
| Proposed immutable pin identified           | YES / PROPOSED    |
| Corrected extraction command identified     | YES / PROPOSED    |
| Source-build model preferred                | YES / PROPOSED    |
| Proper-name policy resolved                 | NO                |
| Exact build environment pinned              | NO                |
| Byte-stable output demonstrated             | NO                |
| ESDB selected                               | NO                |
| LibreOffice selection replaced              | NO                |
| English license-and-notice pathway approved | NO / NOT APPROVED |
| Download approved                           | NO / NOT APPROVED |
| Build or generation approved                | NO / NOT APPROVED |
| Local placement approved                    | NO / NOT APPROVED |
| Hash computation approved                   | NO / NOT APPROVED |
| Loader use approved                         | NO / NOT APPROVED |
| Aggregate dry run approved                  | NO / NOT APPROVED |
| Real CALLHOME validation approved           | NO / NOT APPROVED |
| Clean promotion approved                    | NO / NOT APPROVED |
| Condition construction approved             | NO / NOT APPROVED |
| Tokenization approved                       | NO / NOT APPROVED |
| Model training approved                     | NO / NOT APPROVED |

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

- **No CALLHOME content or CALLHOME-derived evidence was used.**
- **No ESDB artifact was downloaded or saved.**
- **No build or extraction command was executed.**
- **No hash was computed.**
- **CALLHOME never receives generic `CsCont` candidacy and never qualifies as
  genuine code-switched, mixed-language, or switching-quota evidence.**
- **All 88,404 CALLHOME rows remain `not_validated`.**
- **`validated`, `lexicon_exact_match`, `clean`, and every condition-candidate count
  remain zero.**

## Next Step
A future branch — evidence-first, then a separate decision — would resolve the
remaining material questions (Model 1 vs. LibreOffice replacement; proper-name
policy; exact Python/SQLite pin; byte-stable reproduction; filename/storage
metadata; notice-bundle and size-60/variant-1 approval). Until then, the existing
LibreOffice resource **remains selected for governance pending review**, ESDB is
**not** selected or approved, and every operational gate remains **closed**.
