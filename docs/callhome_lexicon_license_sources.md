# CALLHOME Lexicon License Sources (Evidence)

## Status
- **Docs-only evidence note.** No code changes, no downloads, no lexicon files
  added, no parser run on real files, no aggregate outputs committed.
- No transcript excerpts, tokens, header values, participant names, speaker IDs,
  or filenames appear here.
- No condition JSONL, no tokenization, no training.
- **Neither resource is adopted, downloaded, committed, loaded, or used.** This
  note records **source/license evidence only**, for a future manifest / adoption
  decision.
- **License review is not complete enough to use the files yet**, and **clean
  promotion is not enabled.** Both candidates are recorded as *source evidence
  found; not adopted*.
- Permission state: **Decision B** (see `docs/callhome_ground_rules.md`).

## Purpose
Following `docs/callhome_lexicon_license_verification.md`, which required
identifying the **exact package/source/license** for the two shortlisted
candidates, this note records the **authoritative source evidence** now gathered
for:

- **English** — LibreOffice/dictionaries `en_US` Hunspell dictionary (derived
  from SCOWL / the English Speller Database).
- **Spanish** — LibreOffice/dictionaries Spanish Hunspell dictionaries from
  RLA-ES (Recursos Lingüísticos Abiertos del Español).

This is evidence to feed a **future resource-manifest PR**. It does **not** adopt
either resource.

## Source evidence summary
| Candidate | Package identity | Provenance | License (as stated by source) | Status |
|---|---|---|---|---|
| English `en_US` | `en_US Hunspell Dictionary Version 2020.12.07` (LibreOffice/dictionaries) | Derived from SCOWL (normal dicts ≈ SCOWL size 60); `en_US`/`en_CA`/`en_AU` are the official Hunspell dictionaries | SCOWL copyright + permission notice (use/copy/modify/distribute/sell if notices preserved); additional Ispell/WordNet/VarCon/other notices. Upstream ESDB/en-wl states BSD-compatible sources, combined work under an MIT-like license (see its Copyright file) | **source evidence found; license appears potentially compatible, but manifest/notice handling still required; not adopted** |
| Spanish `es` | LibreOffice `es/` version `2.9`; publisher **Recursos Lingüísticos Abiertos del español (RLA-ES)**; from `sbosio/rla-es` | New development by Santiago Bosio (not based on older Carretero/Rodríguez or Holt MySpell adaptation); RLA-ES compiles dictionaries used by LibreOffice, Apache OpenOffice, Mozilla Firefox; latest release `v2.9` (Jan 2, 2025) | Triple disjunctive license: GPLv3-or-later, LGPLv3-or-later, or MPL 1.1-or-later; user may choose freely | **source evidence found; license appears potentially compatible, but selected-license strategy and manifest/notice handling still required; not adopted** |

Both rows are **evidence only**. "Appears potentially compatible" is **not** a
determination that the files may be used; the remaining questions below must be
resolved in a manifest PR first.

## English candidate evidence
- **Source candidate:** LibreOffice/dictionaries `en/README_en_US.txt`.
- **Package identity:** the README identifies the package as
  `en_US Hunspell Dictionary Version 2020.12.07`.
- **Source / provenance (per the README):**
  - The English dictionaries are **derived from SCOWL**.
  - The normal dictionaries **correspond to SCOWL size 60**.
  - `en_US`, `en_CA`, and `en_AU` are the **official dictionaries for Hunspell**.
- **License / copyright (per the README):**
  - The English dictionaries come **directly from SCOWL** and are under the
    **same copyright as SCOWL**.
  - It includes a **permission notice** allowing use, copy, modification,
    distribution, and sale of the word lists and generated outputs, **provided
    the copyright notice and permission notice are preserved**.
  - It includes **additional source notices** for components including
    Ispell / WordNet / VarCon / others.
- **Related current upstream (English Speller Database / ESDB):**
  - The ESDB site says ESDB is used to create high-quality spellchecker
    dictionaries, with **premade dictionaries for Hunspell, Aspell, and plain
    wordlists**.
  - The `en-wl/wordlist` GitHub repo says ESDB is **derived from many sources
    under a BSD-compatible license**, and the **combined work is available under
    an MIT-like license**, with details in its **Copyright** file.
- **Conservative status:** *source evidence found; not adopted.* License
  *appears potentially compatible, but manifest/notice handling still
  required.* Not ready for use.

## Spanish candidate evidence
- **Source candidate:** LibreOffice/dictionaries `es/` package and RLA-ES
  (`sbosio/rla-es`).
- **Package identity:**
  - LibreOffice `es/description.xml` identifies version `2.9`.
  - Publisher is **Recursos Lingüísticos Abiertos del español (RLA-ES)** /
    *Open language resources for Spanish (RLA-ES)*.
- **Files (in LibreOffice `es/`):** `LICENSE.md`, `README_hunspell_es.txt`, and
  regional dictionary files including `es_ES.aff` and `es_ES.dic`.
- **Source / provenance:**
  - `README_hunspell_es.txt` says the Spanish spelling dictionary was **initially
    developed by Santiago Bosio**.
  - It says the dictionary is a **completely new development**, **not** based on
    the older Carretero/Rodríguez work or the Richard Holt MySpell adaptation.
  - The RLA-ES repo describes itself as a **collaborative project for open
    Spanish linguistic resources** and says it **compiles spellchecking
    dictionaries used by LibreOffice, Apache OpenOffice, and Mozilla Firefox**.
  - The RLA-ES README lists regional variants including `es_ES`, `es_MX`,
    `es_US`, and `es` general/international.
  - The RLA-ES GitHub repo shows latest release **`v2.9`, dated Jan 2, 2025**.
- **License (per LibreOffice `es/LICENSE.md` and RLA-ES `LICENSE.md`):**
  - The project/dictionaries are distributed under a **triple disjunctive
    license**: **GPLv3-or-later, LGPLv3-or-later, or MPL 1.1-or-later**.
  - The user **may choose freely** which license to use.
- **Conservative status:** *source evidence found; not adopted.* License
  *appears potentially compatible, but selected-license strategy and
  manifest/notice handling still required.* Not ready for use.

## Remaining legal/implementation questions
Before either candidate could be used (to be resolved in a manifest PR):

- **English — notice preservation:** exactly which **copyright + permission
  notices** (SCOWL, and the Ispell/WordNet/VarCon/other components) must be
  reproduced, and where, if the file or a derived wordlist is stored/committed?
  Confirm the ESDB/`en-wl` **Copyright** file details and the effective combined
  license.
- **Spanish — license selection:** which of the **three disjunctive licenses**
  (GPLv3+/LGPLv3+/MPL 1.1+) do we elect, and what obligations does that choice
  impose on this repository (especially **copyleft/share-alike** implications of
  GPL/LGPL vs. MPL for any committed derivative)?
- **Pinned versions & URLs:** exact **canonical source URLs** and version tags
  (`en_US` `2020.12.07`; RLA-ES `v2.9`) for reproducibility.
- **Derived wordlists:** if we later extract plain wordlists, do the **same
  license/notice obligations** carry to the derived files before any commit?
- **Storage decision:** local/gitignored vs. committable, given the confirmed
  license and notice obligations (see below).

## Storage recommendation
- **Prefer local / gitignored storage for full dictionary files at first**, even
  if redistribution appears allowed, **until attribution/notice obligations are
  fully documented** in a manifest.
- If we later **derive plain wordlists**, those derived files **also need
  license/notice treatment before commit** — do not commit derivatives until
  their notices are documented.
- Only **aggregate, non-transcript diagnostics** may be committed in the interim
  (under Decision B).

## Attribution/notice requirements to preserve
Record and preserve (in a future manifest and alongside any stored/derived file):

- **English:** the **SCOWL copyright + permission notice** (verbatim), plus the
  **additional component notices** (Ispell / WordNet / VarCon / others), and the
  ESDB/`en-wl` **Copyright**/combined-license details.
- **Spanish:** the RLA-ES attribution (**Recursos Lingüísticos Abiertos del
  español**, Santiago Bosio and contributors), the **chosen** license text
  (GPLv3+/LGPLv3+/MPL 1.1+), and the `LICENSE.md` / `README_hunspell_es.txt`
  notices.
- **Versions:** `en_US 2020.12.07` and RLA-ES `v2.9`, with canonical source URLs.

## Current recommendation
- These sources look **promising enough to proceed to a resource-manifest PR** —
  but this PR **does not adopt** either resource.
- **Do not download, add, load, or use** the dictionaries yet.
- The manifest PR should **pin exact source URLs and versions**, record the
  **selected Spanish license pathway**, capture **required attribution notices**,
  and set the **storage strategy** (default local/gitignored first).
- Keep the conservative posture: unresolved notice/selection questions mean the
  files are **not usable yet**.

## Out of scope
- Adopting, downloading, or loading any resource; adding lexicon files.
- Implementing a real lexicon loader or wiring the validator into the real-data
  script.
- Exact normalization thresholds and the borrowing/cognate resolution policy.
- **Condition JSONL construction** — remains out of scope.
- Sampling proportions, train/dev/test splitting, tokenizer choice.
- **Model training** — remains out of scope.
- Any Bangor / `CsCont` logic. **CALLHOME never feeds `CsCont`** (Bangor-sourced
  only); a future positive lexicon validation would only route clean English rows
  to `EnglishMono` + `MonoCont` and clean Spanish rows to `SpanishMono` +
  `MonoCont`.

## Next steps
1. Open a **resource-manifest PR** that pins, for each candidate: exact
   **package name/version**, **canonical source URL(s)**, the **license pathway**
   (English: SCOWL/ESDB combined; Spanish: the **selected** one of GPLv3+/LGPLv3+/
   MPL 1.1+), **required attribution notices**, and the **storage strategy**.
2. Default the manifest to **local/gitignored** full-file storage; document notice
   obligations before considering committing any file or derived wordlist.
3. Only after the manifest is recorded, proceed to the resource policy's remaining
   gates (normalization tests → synthetic ambiguity tests → local-only dry run →
   aggregate-only review → explicit approval) before any clean promotion.

Guardrails that hold regardless: **CALLHOME-derived token lists must never shape
the lexicon**; **CALLHOME text must never be uploaded externally**; until a
manifest and approvals exist, no real lexicon is loaded, every CALLHOME row stays
`not_validated`, and the `clean` count stays zero.
