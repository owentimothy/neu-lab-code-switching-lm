# CALLHOME Lexicon Attribution / Notice Inventory

## Status
- **Notice inventory only, not adoption.** No code changes, no downloads, no
  lexicon files added, no upstream license files copied, no long license texts
  pasted.
- **No resource is downloaded, committed, loaded, or used.**
- **No clean promotion is enabled**, and **no real lexicon can be loaded yet.**
- No condition JSONL construction. No model training.
- Records **which attribution/copyright/license/notice obligations must be
  preserved** before any future implementation/storage PR — it does not preserve
  them verbatim here.
- No transcript excerpts, tokens, header values, participant names, speaker IDs,
  or filenames appear here.
- Permission state: **Decision B** (see `docs/callhome_ground_rules.md`).

## Purpose
The resource manifest draft (`docs/callhome_lexicon_resource_manifest.md`) pinned
two candidates and their source references. This note inventories the **notices
that must be preserved** for each, so a future **attribution/notice appendix or
file** can capture the **verbatim** text once the exact resource files are
selected. It **adopts nothing** and copies no license text; it **summarizes**
obligations and points to the source references already recorded in the manifest.

## Scope
- Covers the same **two** candidates as the manifest: the English SCOWL/LibreOffice
  `en_US` Hunspell dictionary and the Spanish RLA-ES/LibreOffice Hunspell
  dictionary.
- **No dictionary files, derived wordlists, or long license texts are added.**
- **Actual verbatim notice preservation belongs in a future attribution/notice
  appendix or file**, created **after** the exact resource files are selected —
  not here.
- Uses **only** the source references already recorded in the manifest; no new
  URLs and no browsing.

## English notice inventory
Notices to preserve for the English SCOWL/LibreOffice `en_US` dictionary
(per the manifest's `en/README_en_US.txt` reference and upstream ESDB/`en-wl`
Copyright file):

- **SCOWL copyright and permission notice** — the core notice permitting use,
  copy, modification, distribution, and sale **provided the copyright and
  permission notices are preserved**.
- **Ispell-related notices** — component notice(s) referenced by the upstream
  README.
- **WordNet-related notices** — component notice(s) referenced by the upstream
  README.
- **VarCon-related notices** — component notice(s) referenced by the upstream
  README.
- **Any other component notices** listed by the upstream English README /
  Copyright file (ESDB/`en-wl` combined-work details) — to be enumerated when the
  exact files are selected.

## Spanish notice inventory
Notices to preserve for the Spanish RLA-ES/LibreOffice dictionary
(per the manifest's LibreOffice `es/` and RLA-ES references):

- **RLA-ES attribution** — Recursos Lingüísticos Abiertos del Español.
- **Santiago Bosio and contributors** — credit per upstream notices.
- **Selected license pathway notice requirements** — the notice text/obligations
  for the chosen pathway.
- **MPL 1.1-or-later preference** — remains a **working manifest preference, not
  legal approval**; the final pathway and its notice obligations must be recorded
  before use.
- **Upstream `LICENSE.md` and `README_hunspell_es.txt` notices** — must be
  **reviewed before use** and captured verbatim in the future appendix.

## Notice inventory table
Status values: *identified; verbatim text not yet captured* · *requires future
appendix* · *not adopted*.

| Resource | Notice source | Notice category | Must preserve? | Where to preserve later | Status |
|---|---|---|---|---|---|
| English `en_US` (SCOWL/LibreOffice) | `en/README_en_US.txt` (manifest) | SCOWL copyright + permission notice | yes | future attribution/notice appendix or file | identified; verbatim text not yet captured; requires future appendix; not adopted |
| English `en_US` | upstream English README / ESDB `en-wl` Copyright file | Ispell component notice | yes | future attribution/notice appendix or file | identified; verbatim text not yet captured; requires future appendix; not adopted |
| English `en_US` | upstream English README / ESDB `en-wl` Copyright file | WordNet component notice | yes | future attribution/notice appendix or file | identified; verbatim text not yet captured; requires future appendix; not adopted |
| English `en_US` | upstream English README / ESDB `en-wl` Copyright file | VarCon component notice | yes | future attribution/notice appendix or file | identified; verbatim text not yet captured; requires future appendix; not adopted |
| English `en_US` | upstream English README / ESDB `en-wl` Copyright file | Other component notices (combined-work) | yes (once enumerated) | future attribution/notice appendix or file | identified; verbatim text not yet captured; requires future appendix; not adopted |
| Spanish RLA-ES (LibreOffice `es/`) | RLA-ES `README.md` / LibreOffice `es/` (manifest) | RLA-ES project attribution | yes | future attribution/notice appendix or file | identified; verbatim text not yet captured; requires future appendix; not adopted |
| Spanish RLA-ES | `README_hunspell_es.txt` (manifest) | Author credit (Santiago Bosio + contributors) | yes | future attribution/notice appendix or file | identified; verbatim text not yet captured; requires future appendix; not adopted |
| Spanish RLA-ES | `es/LICENSE.md` / RLA-ES `LICENSE.md` (manifest) | Selected license pathway notice (MPL 1.1+ preference) | yes (once pathway confirmed) | future attribution/notice appendix or file | identified; verbatim text not yet captured; requires future appendix; not adopted |

Every row is **identified but not captured verbatim**, **requires a future
appendix**, and is **not adopted**.

## Notice preservation strategy
- **Identify now, capture later:** this inventory lists *what* must be preserved;
  the *verbatim* text is captured in a future appendix once exact files are chosen.
- Notices travel with the resource: **wherever a dictionary file or a derived
  wordlist is stored** (local/gitignored first), the corresponding notices must
  accompany it.
- Preserve notices **unmodified** and **in full** in the future appendix; do not
  paraphrase the legally operative text there.
- Keep the mapping from **each stored/derived file → its required notices**
  explicit, so nothing is stored without its notice obligations recorded.

## What must not be copied into this doc
- **No verbatim license texts** (SCOWL/permission notice bodies, MPL/GPL/LGPL full
  texts, component license bodies).
- **No dictionary files** (`.dic` / `.aff`) or **derived wordlists**.
- **No upstream license files** copied into the repo.
- **No new source URLs** beyond those already recorded in the manifest.
- Summaries and pointers only — the operative text lives upstream and, later, in
  the dedicated appendix.

## Future attribution/notice file plan
When exact resource files are selected (a **future** implementation/storage PR):

- Create a dedicated **attribution/notice file or appendix** (e.g. alongside the
  local/gitignored resource path) capturing the **verbatim** notices enumerated
  above.
- Record, per resource: the **exact file(s)**, **version/tag**, **source URL(s)**
  (from the manifest), and the **verbatim** copyright/permission/component notices.
- For Spanish, record the **confirmed** license pathway (MPL 1.1+ if retained) and
  its exact notice requirements.
- Cross-link each stored/derived file to its notice entry.

## Derived wordlist notice implications
- **If derived plain wordlists are created, they still carry the upstream notice
  obligations** of the source dictionary.
- Derived files must stay **local / gitignored** until:
  1. the **derivation process is documented**,
  2. the **notice treatment is documented** (which notices ship with the derived
     file), and
  3. **explicit approval** is given to commit or keep local-only.
- **CALLHOME-derived token lists must never shape, filter, expand, or modify the
  lexicon** (or any derived wordlist).

## Remaining questions
- **English:** exactly which component notices (beyond SCOWL/Ispell/WordNet/VarCon)
  the ESDB/`en-wl` **Copyright** file enumerates, and the effective combined
  license to record.
- **Spanish:** the **final** license pathway (MPL 1.1+ preference vs.
  GPLv3+/LGPLv3+) and its precise notice obligations; and which regional variant
  (`es`, `es_ES`, …) is the intended validation lexicon.
- **Placement:** where the future attribution/notice appendix lives relative to
  the local/gitignored resource path.

## Current recommendation
- Treat this as an **inventory to drive a future appendix**; **do not download,
  add, load, or use** any dictionary, and **do not** copy notice text here.
- Keep the conservative posture: notices are **identified but not captured**;
  files stay **local/gitignored**; nothing derived is committed until notice
  treatment is documented and explicitly approved.
- Resolve the remaining questions before the attribution/notice appendix is
  finalized.

## Out of scope
- Adopting, downloading, or loading any resource; adding lexicon or license files.
- Implementing a real lexicon loader or wiring the validator into the real-data
  script.
- Exact normalization thresholds and the borrowing/cognate resolution policy.
- Editing `.gitignore` or creating the resource path (future implementation PR).
- **Condition JSONL construction** — remains out of scope.
- Sampling proportions, train/dev/test splitting, tokenizer choice.
- **Model training** — remains out of scope.
- Any Bangor / `CsCont` construction logic. This notice inventory creates no
  condition output. A future positive lexicon validation may permit clean rows
  to serve their language-matched baseline, matching `MonoCont` role, and future
  language-matched `CsCont` monolingual-filler role selected only from that
  `MonoCont` material. CALLHOME never qualifies as genuine code-switched,
  mixed-language, or switching-quota evidence.

## Next steps
1. When exact files are selected, create the **attribution/notice appendix** and
   capture the **verbatim** notices enumerated in the table above.
2. Confirm the English combined-license/component-notice set and the Spanish
   license pathway; update the manifest and this inventory's statuses accordingly.
3. Only then proceed to the resource policy's remaining gates (normalization
   policy → synthetic normalization tests → synthetic ambiguity tests →
   local-only loader scaffold → local-only dry run → aggregate-only diagnostics
   review → explicit approval) before any clean promotion.

Guardrails that hold regardless: **CALLHOME text must never be uploaded
externally**; **CALLHOME-derived token lists must never shape the lexicon**;
**CALLHOME never receives generic `CsCont` or switching-evidence candidacy**; and
until the gates clear, no real lexicon is loaded, every CALLHOME row stays
`not_validated`, and the `clean` count stays zero.
