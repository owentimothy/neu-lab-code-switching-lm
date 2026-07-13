# CALLHOME English Lexicon Resource Selection Decision

## Status
- **Docs-only decision record, not implementation.** No code changes.
- **No English or other lexicon resource is placed, downloaded, or committed.**
- **No lexicon artifact is saved, downloaded, copied, or placed.** The local
  resource directory (`data/resources/local_lexicons/`) is not created or
  populated; `.gitignore` is not edited.
- **No hashes.** No loader use. No validator use over real CALLHOME. No aggregate
  dry run. No clean promotion. No condition JSONL. No tokenization or dataset
  construction. No model training.
- **The real pipeline remains unchanged** (`default_source_validation` only;
  validator/loader not wired in). Every real CALLHOME row stays `not_validated`;
  `clean` stays zero.
- **No external browsing was performed and no upstream files were fetched or
  saved.** This record rests only on facts already established in the repository,
  chiefly the authoritative `docs/callhome_lexicon_exact_resource_metadata.md`.
- **No CALLHOME transcript content or CALLHOME-derived evidence was inspected or
  used.**
- **All operational approvals remain `NO / NOT APPROVED`.** The only thing this
  record approves is the *selection for continued governance* (below).

## Decision
This record formally selects the **LibreOffice/SCOWL `en_US` Hunspell resource at
immutable LibreOffice repository snapshot
`38d96a4d54ec3449cf7f28cddae1fce32e2b15a7`** as the **exact English candidate
permitted to proceed to a separate English license-and-notice pathway review**.

```text
English resource selection for continued governance:
YES / APPROVED
```

This approval is **narrow**. It permits the English resource to advance to the
*next governance gate only*. It does **not** approve operational adoption or use.
The following are kept strictly separate:

```text
resource selected for continued governance
≠ resource adopted for operational use
≠ resource approved for local placement
≠ resource approved for loader use
```

## Exact Resource Record
All values are taken from the authoritative
`docs/callhome_lexicon_exact_resource_metadata.md` (upstream-verified there).

```text
Resource ID:
english_en_us_hunspell

Resource family:
SCOWL-derived LibreOffice en_US Hunspell

Language:
eng

Locale:
en_US

Selected immutable LibreOffice snapshot:
38d96a4d54ec3449cf7f28cddae1fce32e2b15a7

Dictionary files:
en/en_US.dic
en/en_US.aff

Metadata, license, and notice files:
en/README_en_US.txt
en/license.txt
en/WordNet_license.txt

README version string:
2020.12.07

en_US.dic / en_US.aff last-touch commit:
4fa94195b8136364dd40bf2b0366a0fe32058899

English en/ tree last-touch commit:
e7f163feb2beaf526135132d8716e68e19d2716e
```

## Pin Interpretation
The pins above must not be over-read. Precisely:

- **`2020.12.07`** is **descriptive upstream version metadata** taken from the
  README (`en/README_en_US.txt`). It is **not a Git tag** and **does not uniquely
  pin file contents**; LibreOffice/dictionaries has no per-dictionary version tag.
- **`4fa94195...`** records the **last direct change to `en_US.dic` and
  `en_US.aff`** (2021-05-12). It pins those two files' last modification, but it
  **does not bind the accompanying README, license, and notice files together as
  one complete package snapshot**. (Note also that this last-touch date *postdates*
  the `2020.12.07` version string, so the version string alone does not pin the
  distributed file content.)
- **`e7f163fe...`** is the **last-touch commit for the whole `en/` tree**
  (2025-03-31); the `en/` directory content is unchanged since then. It is recorded
  as a stability fact, not as the binding snapshot.
- **`38d96a4d...`** is selected as the **immutable full-repository snapshot** that
  **binds the dictionary, affix, README, license, and notice files to one
  reproducible state**. This is the reference this decision selects.
- The later full-repository snapshot **does not imply that every English file
  changed at that commit** — most did not; it simply fixes a single reproducible
  state in which all five files coexist.

These commit references establish **reproducible identity and co-location** of the
files. They do **not** prove licensing, redistribution rights, notice
sufficiency, or linguistic suitability — those remain for later gates.

## Rationale for Selection
This English resource is selected **for continued governance** (not for use)
because:

1. **Already documented.** It is the English candidate already documented
   throughout the repository (resource policy, license sources, manifest draft,
   attribution notices, candidate record, exact-resource metadata).
2. **Documented origin.** Its origin and **SCOWL derivation** are documented
   (SCOWL size 60; `en_US`/`en_CA`/`en_AU` are the official Hunspell dictionaries;
   Kevin Atkinson copyright), per `docs/callhome_lexicon_exact_resource_metadata.md`.
3. **Files upstream-verified.** Its exact files (`en/en_US.dic`, `en/en_US.aff`,
   `en/README_en_US.txt`, `en/license.txt`, `en/WordNet_license.txt`) have been
   **upstream-verified** in the existing metadata record.
4. **Immutable reproducible snapshot.** It has an immutable full-repository
   snapshot (`38d96a4d...`) that binds those files to one reproducible state.
5. **Local-only capable.** It is compatible with a future **local-only workflow**
   and does **not** require sending any CALLHOME data to an external service.
6. **Loader-format compatible.** Its `.dic` format is **technically compatible**
   with the existing raw-entry loader scaffold (`.dic` raw entries).
7. **Conservative failure direction.** The loader's lack of `.aff` expansion means
   only base forms are covered, producing **more false negatives** — the
   conservative direction for a validation gate (a genuinely-clean row left
   `not_validated` is safer than a wrongly-admitted one).
8. **No CALLHOME evidence used.** **No CALLHOME-derived evidence** was used to
   choose the resource or the snapshot.

This selection makes **no** claim that the English resource has been empirically
proven **linguistically optimal**. No candidates were compared using CALLHOME
validation yield, vocabulary, token frequencies, unknown-token counts, condition
candidate counts, or any transcript content.

## Loader Limitation
Descriptively, the current loader scaffold
(`src/cslm/data/callhome_lexicon_loader.py`):

- can read **raw `.dic` entries**;
- **skips a leading count line**;
- **strips Hunspell flags after `/`** (e.g. `hello/AB` → `hello`);
- **does not read `.aff`**;
- **does not expand affix rules**;
- **does not generate inflected forms**.

**Technical compatibility is not loader-use approval.** That the `.dic` could, in
principle, be read by the scaffold does not permit running the loader on any real
resource; loader use is a separate gate that remains `NO / NOT APPROVED`.

## Approval Matrix
Candidate selection for continued governance must **not** be silently converted
into adoption. Exactly one gate is approved by this record:

| Gate                                               | Status            |
| -------------------------------------------------- | ----------------- |
| English resource selected for continued governance | YES / APPROVED    |
| Operational candidate adoption                     | NO / NOT APPROVED |
| English license-and-notice pathway                 | NO / NOT APPROVED |
| Redistribution determination                       | NO / NOT APPROVED |
| Local placement                                    | NO / NOT APPROVED |
| Resource download                                  | NO / NOT APPROVED |
| Local directory creation or population             | NO / NOT APPROVED |
| Hash computation                                   | NO / NOT APPROVED |
| Loader use                                         | NO / NOT APPROVED |
| Aggregate dry run                                  | NO / NOT APPROVED |
| Real CALLHOME validation                           | NO / NOT APPROVED |
| Clean promotion                                    | NO / NOT APPROVED |
| Condition JSONL                                    | NO / NOT APPROVED |
| Tokenization or dataset construction               | NO / NOT APPROVED |
| Model training                                     | NO / NOT APPROVED |

`YES / APPROVED` applies **only** to *selection for continued governance*. It
does **not** approve the resource for operational adoption or use, local
placement, loader use, validation, promotion, condition JSONL, or training.

## Safety and Source Boundaries
Source-routing invariant (unchanged by this decision):

```text
CALLHOME English
→ potentially EnglishMono
→ potentially the English portion of MonoCont
→ never CsCont
```

Reaffirmed:

- **No CALLHOME transcript text or token strings** may appear in this record.
- **No transcript headers, participant names, speaker IDs, or raw filenames** may
  appear.
- **No CALLHOME-derived material influenced this selection** (resource or snapshot).
- **No lexicon artifact is downloaded, saved, placed, loaded, hashed, or used.**
- **All real CALLHOME rows remain `not_validated`.**
- **`clean` remains zero.**
- **All condition candidate counts remain zero** (`EnglishMono`, `SpanishMono`,
  `MonoCont`).
- **Bangor remains the only final source for `CsCont`.**

## Relationship to Existing Documentation
This decision sits:

```text
after:
exact resource metadata

before:
English license-and-notice pathway decision
local-placement approval
loader-use approval
dry-run approval
```

It reads from (repository-relative), rather than duplicating long license text:

- `docs/callhome_lexicon_resource_policy.md` — acceptable-resource / licensing /
  storage / review-gate contract; conservative "prefer false negatives" posture.
- `docs/callhome_lexicon_license_sources.md` — SCOWL/ESDB source-license evidence
  ("source evidence found; not adopted").
- `docs/callhome_lexicon_resource_manifest.md` — **draft-level** manifest; its
  language is draft and does **not** itself constitute adoption or legal approval.
- `docs/callhome_lexicon_attribution_notices.md` — notice obligations to preserve
  (SCOWL + Ispell/WordNet/VarCon/other component notices); verbatim capture pending.
- `docs/callhome_lexicon_placement_approval_template.md` — the reviewer gate a
  future placement must clear.
- `docs/callhome_lexicon_local_resource_approval_record.md` — the concrete
  candidate record; every approval field `NO / NOT APPROVED`.
- `docs/callhome_lexicon_exact_resource_metadata.md` — **authoritative** for the
  exact files, README version string, last-touch commits, and the selected
  immutable snapshot; where it corrects older draft documentation, it governs.
- `docs/callhome_spanish_lexicon_locale_decision.md` — used only as a **structural
  example** of a narrow governance decision; Spanish policy is unchanged here.

Older manifest language is **draft-level** and, by itself, constitutes neither
adoption nor legal approval. The redistribution status remains
`not independently legally determined`, and the English notice obligations remain
identified-but-not-captured — both are for the next gate.

## Next Gate
The next recommended branch is a **separate, docs-only English
license-and-notice pathway decision**. That future branch should determine:

- the **exact English notice obligations**;
- the **relationship among `README_en_US.txt`, `license.txt`, and
  `WordNet_license.txt`** (which notices each carries; how they combine);
- **how required notices would accompany** a future local-only resource;
- **whether notice text may be committed** or must remain alongside the ignored
  local resource;
- the **conservative redistribution status**.

**This document does not resolve those questions.** They remain **pending**; this
record only states that they are the next gate.

## Final Gate Status
- **The English `en_US` resource is selected for continued governance**
  (`YES / APPROVED`) at snapshot `38d96a4d54ec3449cf7f28cddae1fce32e2b15a7`.
- **No resource is adopted for operational use.**
- **No resource is placed, downloaded, or loaded.**
- **No hashes are computed.**
- **No real CALLHOME validation occurs.**
- **All real CALLHOME rows remain `not_validated`** (`clean` stays zero; all
  condition candidate counts stay zero).
- **Bangor remains the only final source for `CsCont`.**
- **Every operational gate remains closed** until each later approval — starting
  with the English license-and-notice pathway decision — is separately granted.
