# CALLHOME Lexicon Resource Manifest (Draft)

## Status
- **Manifest draft, not adoption.** No code changes, no downloads, no lexicon
  files added, no parser run on real files, no aggregate outputs committed.
- **No resource is downloaded, committed, loaded, or used.**
- **No clean promotion is enabled**, and **no real lexicon can be loaded yet.**
- No condition JSONL construction. No model training.
- The manifest records the **source / version / license / notice / storage
  decisions** that must be satisfied **before** a future implementation PR.
- No transcript excerpts, tokens, header values, participant names, speaker IDs,
  or filenames appear here.
- Permission state: **Decision B** (see `docs/callhome_ground_rules.md`).

## Purpose
Following the source-evidence note (`docs/callhome_lexicon_license_sources.md`),
this draft assembles a **resource manifest** for the two shortlisted candidates —
pinning package/version, source URLs, license pathway, provenance, attribution
obligations, and storage strategy — so a **future implementation PR** has a
single reference of what must hold before any real lexicon is used. It **adopts
nothing**; each entry is marked *manifest drafted; not adopted for use*.

## Manifest scope
- Covers **two** candidates only: the English SCOWL/LibreOffice `en_US` Hunspell
  dictionary and the Spanish RLA-ES/LibreOffice Hunspell dictionary.
- Records decisions and obligations; it does **not** place any file, wire any
  loader, or enable validation. The lexicon validator remains synthetic-only /
  caller-provided and is **not** wired into the real-data script.
- Long license texts are **not** copied here — this manifest **summarizes** and
  points to source references; verbatim notices belong in a future
  attribution/notice appendix or file.

## English resource manifest entry
- **Resource label:** English SCOWL/LibreOffice `en_US` Hunspell dictionary.
- **Candidate source:** LibreOffice/dictionaries `en/README_en_US.txt`.
- **Source URL:**
  `https://raw.githubusercontent.com/LibreOffice/dictionaries/master/en/README_en_US.txt`
- **Package / version:** `en_US Hunspell Dictionary Version 2020.12.07`.
- **Provenance:**
  - Derived from **SCOWL / English Speller Database**.
  - Normal dictionary **corresponds to SCOWL size 60**.
  - `en_US`, `en_CA`, and `en_AU` are **official Hunspell dictionaries**.
- **License / notice summary:**
  - The SCOWL **copyright and permission notice** allows use, copy, modification,
    distribution, and sale of the word lists and generated outputs, **provided
    the copyright and permission notices are preserved**.
  - **Additional source notices** include **Ispell, WordNet, VarCon, and other
    components** (to be reviewed and preserved).
- **Manifest status:** `manifest drafted; not adopted for use`.
- **Storage decision:** full dictionary files remain **local / gitignored** at
  first. **No dictionary file or derived wordlist is committed in this PR.**
- **Before use:**
  1. Record the **full SCOWL / English notice text** in a future
     attribution/notice file or manifest appendix.
  2. Decide whether a **derived plain wordlist** will be **local-only or
     committable**.
  3. Add **synthetic normalization and ambiguity tests** before any real loader /
     dry run.

## Spanish resource manifest entry
- **Resource label:** Spanish RLA-ES/LibreOffice Hunspell dictionary.
- **Candidate sources:** LibreOffice/dictionaries `es/` package and RLA-ES
  `sbosio/rla-es`.
- **Source URLs:**
  - `https://github.com/LibreOffice/dictionaries/tree/master/es`
  - `https://raw.githubusercontent.com/LibreOffice/dictionaries/master/es/README_hunspell_es.txt`
  - `https://raw.githubusercontent.com/LibreOffice/dictionaries/master/es/LICENSE.md`
  - `https://raw.githubusercontent.com/sbosio/rla-es/master/README.md`
  - `https://raw.githubusercontent.com/sbosio/rla-es/master/LICENSE.md`
  - `https://github.com/sbosio/rla-es/releases/tag/v2.9`
- **Package / version:** RLA-ES `v2.9` / LibreOffice Spanish dictionary package.
- **Provenance:**
  - **RLA-ES / Recursos Lingüísticos Abiertos del Español.**
  - Dictionary **initially developed by Santiago Bosio**.
  - The README states it is a **completely new development**, **not** based on the
    older Carretero/Rodríguez work or the Richard Holt MySpell adaptation.
  - RLA-ES **compiles spellchecking dictionaries used by LibreOffice, Apache
    OpenOffice, and Mozilla Firefox**.
  - Regional variants include `es_ES`, `es_MX`, `es_US`, and general/international
    `es`.
- **License / notice summary:**
  - **Triple disjunctive license:** GPLv3-or-later **OR** LGPLv3-or-later **OR**
    MPL 1.1-or-later. The user **may choose freely** which license to use.
- **Selected manifest pathway:**
  - **Prefer MPL 1.1-or-later** as the selected pathway for future review, because
    it is **file-level / copyleft-limited** relative to the GPL-style
    alternatives.
  - This is a **manifest preference, not legal approval**.
  - If the project later decides MPL 1.1 is unsuitable, **revisit** and choose a
    different source or pathway.
- **Manifest status:** `manifest drafted; not adopted for use`.
- **Storage decision:** full dictionary files remain **local / gitignored** at
  first. **No dictionary file or derived wordlist is committed in this PR.**
- **Before use:**
  1. Record **RLA-ES attribution** and the **selected license text / notice
     requirements**.
  2. Decide whether **`es`, `es_ES`, or another regional variant** is the intended
     validation lexicon.
  3. Add **synthetic normalization and ambiguity tests** before any real loader /
     dry run.

## Storage strategy
- Full dictionary files stay under a future **local / gitignored** resource path.
- **Suggested future path:** `data/resources/local_lexicons/`.
- This path is **not** added to `.gitignore` in this docs-only PR; ignore
  coverage should be verified and added if needed in a **future implementation /
  storage PR**.
- **No files are placed there in this PR.**
- Only **aggregate, non-transcript diagnostics** may be committed later (under
  Decision B).

## Attribution and notice obligations
- **English:**
  - The **SCOWL copyright + permission notice must be preserved.**
  - Component notices for **Ispell, WordNet, VarCon, and others** must be
    **reviewed and preserved**.
- **Spanish:**
  - **RLA-ES attribution must be preserved.**
  - **Santiago Bosio and contributors** should be credited according to upstream
    notices.
  - The chosen **MPL 1.1-or-later** pathway and its **license text / notice
    requirements** must be recorded before use.
- **Do not copy long license texts into this doc** — summarize and point to the
  source references above; verbatim notices belong in a future attribution/notice
  file or appendix.

## License pathway decisions
- **English:** the SCOWL/ESDB permission-notice pathway (preserve copyright +
  permission notices and component notices). The exact combined-license details
  (per the upstream ESDB/`en-wl` Copyright file) must be confirmed and recorded
  before use.
- **Spanish:** **preferred pathway = MPL 1.1-or-later** (manifest preference
  only), chosen for its file-level/limited-copyleft character vs. GPL/LGPL;
  **not** a legal determination. The final selection and its obligations must be
  recorded before use, and revisited if MPL 1.1 proves unsuitable.

## Derived wordlist policy
- **Derived wordlists are not automatically safe to commit.**
- If generated from Hunspell `.dic` / `.aff` files, they **carry the source
  license / notice obligations**.
- Any derived English or Spanish plain wordlist must stay **local / gitignored**
  until:
  1. the **derivation process is documented**,
  2. the **license / notice treatment is documented**,
  3. **explicit approval** is given to commit or keep local-only.
- **CALLHOME-derived token lists must never shape, filter, expand, or modify the
  lexicon.**

## Remaining review gates
Ordered gates that must clear before any clean promotion:

1. **Manifest recorded** (this draft, once finalized).
2. **Attribution / notice appendix or file** (verbatim notices captured).
3. **Normalization policy** for these exact resources documented.
4. **Synthetic normalization tests.**
5. **Synthetic ambiguity tests.**
6. **Local-only loader scaffold.**
7. **Local-only dry run.**
8. **Aggregate-only diagnostics review.**
9. **Explicit approval** before clean promotion.

## Current recommendation
- Treat this as a **manifest draft** to finalize; **do not download, add, load,
  or use** either dictionary.
- Keep **full files local/gitignored** and commit **nothing** derived until the
  attribution/notice and normalization gates are satisfied.
- For Spanish, carry the **MPL 1.1-or-later preference** forward as a working
  assumption to be legally confirmed, not an approval.
- If any obligation cannot be met, **drop that candidate** and revisit.

## Out of scope
- Adopting, downloading, or loading any resource; adding lexicon files.
- Implementing a real lexicon loader or wiring the validator into the real-data
  script.
- Exact normalization thresholds and the borrowing/cognate resolution policy.
- Editing `.gitignore` or creating the resource path (future implementation PR).
- **Condition JSONL construction** — remains out of scope.
- Sampling proportions, train/dev/test splitting, tokenizer choice.
- **Model training** — remains out of scope.
- Any Bangor / `CsCont` construction logic. This resource manifest creates no
  condition output. A future positive lexicon validation may permit clean rows
  to serve their language-matched baseline, matching `MonoCont` role, and future
  language-matched `CsCont` monolingual-filler role selected only from that
  `MonoCont` material. CALLHOME never qualifies as genuine code-switched,
  mixed-language, or switching-quota evidence.

## Next steps
1. Finalize this manifest (confirm the English combined-license details and the
   Spanish selected pathway), and add an **attribution/notice file/appendix** with
   the verbatim upstream notices.
2. In a **future implementation / storage PR**: add `data/resources/local_lexicons/`
   to `.gitignore`, document the normalization policy for these exact resources,
   and add **synthetic normalization + ambiguity tests**.
3. Then a **local-only loader scaffold** and **local-only dry run**, emitting
   **aggregate-only** diagnostics for review, before any **explicit approval** to
   enable clean promotion.

Guardrails that hold regardless: **CALLHOME text must never be uploaded
externally**; **CALLHOME-derived token lists must never shape the lexicon**;
**CALLHOME never receives generic `CsCont` or switching-evidence candidacy**; and
until the gates clear, no real lexicon is loaded, every CALLHOME row stays
`not_validated`, and the `clean` count stays zero.
