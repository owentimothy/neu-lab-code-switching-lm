# CALLHOME Lexicon Local Resource Manifest (Template)

## Status
- **Docs-only template, not implementation.** No code changes.
- **No resource is adopted, downloaded, committed, loaded, or used.**
- **No real lexicon files or derived wordlists are added.**
- **No local resource directory is populated** (`data/resources/local_lexicons/`
  stays empty/ignored).
- **No clean promotion is enabled.** No condition JSONL construction. No model
  training.
- **The real pipeline remains unchanged** (`default_source_validation` only;
  validator/loader not wired in).
- No transcript excerpts, tokens, header values, participant names, speaker IDs,
  or filenames appear here.
- Permission state: **Decision B** (see `docs/callhome_ground_rules.md`).

## Purpose
The repo now has a **storage scaffold** (`docs/callhome_lexicon_storage_scaffold.md`),
a **local-use checklist** (`docs/callhome_lexicon_local_use_checklist.md`), a
**loader scaffold** (`src/cslm/data/callhome_lexicon_loader.py`), and an
**aggregate dry-run plan** (`docs/callhome_lexicon_dry_run_plan.md`). Before any
approved local resource is actually used, the project needs a **structured local
manifest entry** per resource.

This template defines **what must be recorded later**. It does **not** record any
actual approved local resource, and it **adopts nothing**. It is distinct from the
existing `docs/callhome_lexicon_resource_manifest.md` (a *draft* pinning candidate
source/license facts): this file is the **fill-in form** a future approval PR
copies once approved files are placed under the ignored local path.

## How to use this template
- Future PRs should **copy and fill one manifest entry per resource**.
- Entries should be filled **only after explicit approval** to place local files.
- Placeholder values must be marked clearly, e.g. `TBD` / `NOT APPROVED` /
  `NOT PLACED`.
- **Do not treat this template as approval.** Copying it grants nothing.
- **Do not use it to justify resource use** without completed license/notice
  review (see `docs/callhome_lexicon_license_sources.md` and
  `docs/callhome_lexicon_attribution_notices.md`).

## Scope
- **English** SCOWL/LibreOffice `en_US` Hunspell candidate.
- **Spanish** RLA-ES/LibreOffice Hunspell candidate.
- **Derived normalized wordlists** produced from those approved resources.
- **Do not broaden** this template to other resources without a future PR.

## Local resource manifest entry template
Copy the fenced block below once **per resource**, replacing `<resource id>` and
each value. Leave unresolved values as `TBD` / `NOT APPROVED` / `NOT PLACED`.

```
### Resource entry: <resource id>

- Resource role:
- Language:
- Upstream project / package:
- Upstream source URL or package reference:
- Upstream version / release / date:
- Exact upstream files used:
- Local ignored path:
- Local file names:
- File type:
- Loader mode:
- Encoding:
- License pathway:
- Redistribution status:
- Derivation status:
- Notice obligations:
- Attribution obligations:
- Notice mapping file / section:
- Hash algorithm:
- File hash(es):
- Hash computed by:
- Hash computed date:
- Approved for local placement:
- Approved for loader use:
- Approved for aggregate dry run:
- Approved for clean promotion:
- Reviewer / approver:
- Approval PR:
- Notes:
```

## Required fields
Each field and why it matters:

- **Resource role** — `English lexicon` / `Spanish lexicon` / `derived wordlist`.
  Fixes what the entry is for and which templates/guardrails apply.
- **Language** — `eng` / `spa`. Ties the resource to the source language it may
  validate; a lexicon is only ever the *expected* lexicon for its own language.
- **Upstream project / package** — the identifiable origin (e.g. LibreOffice
  dictionaries, RLA-ES). Required so provenance is auditable.
- **Upstream version / release / date** — pins the exact release; without it the
  resource cannot be reproduced or license-checked. `TBD` blocks use.
- **Exact upstream files used** — which specific files were taken (e.g. a `.dic`),
  so notices and hashes map to real artifacts, not a whole package.
- **Local ignored path** — the path under `data/resources/local_lexicons/` (which
  is gitignored). Confirms files stay local and are never committed.
- **Loader mode** — `plain wordlist` or `Hunspell .dic raw-entry` (per
  `src/cslm/data/callhome_lexicon_loader.py`); the loader does **no** affix
  expansion and returns **raw** entries (the validator owns normalization).
- **License pathway** — the specific license chosen/obligated (see
  `docs/callhome_lexicon_license_sources.md`). Ambiguity here blocks use.
- **Notice obligations** — what attribution/notices must be preserved and where
  (see `docs/callhome_lexicon_attribution_notices.md`). Unmet notices block use.
- **Hashes / checksums** — integrity + provenance record for the exact local file;
  see the hash policy below. Missing required hashes block use.
- **Approval statuses** — the four independent gates below; each defaults to `NO`.
- **Approval PR references** — the PR that recorded each approval, for audit.
- **Derived-wordlist relationship, if any** — parent resource(s) and derivation,
  so a derived file inherits its parents' license/notice obligations.

## English resource template
Not filled. Copy and complete only after explicit approval; do not invent
version/source facts beyond what existing docs already reference.

```
### Resource entry: english_en_us_hunspell

- Resource role: English lexicon
- Language: eng
- Upstream project / package: English SCOWL/LibreOffice en_US Hunspell candidate
  (see docs/callhome_lexicon_resource_manifest.md / license_sources.md)
- Upstream source URL or package reference: TBD (use references already recorded
  in docs/callhome_lexicon_license_sources.md; do not invent new facts)
- Upstream version / release / date: TBD
- Exact upstream files used: TBD
- Local ignored path: TBD under data/resources/local_lexicons/
- Local file names: TBD (NOT PLACED)
- File type: TBD (e.g. Hunspell .dic / plain wordlist)
- Loader mode: TBD (plain wordlist | Hunspell .dic raw-entry)
- Encoding: TBD (expected UTF-8)
- License pathway: TBD (SCOWL copyright + permission notice pathway; confirm)
- Redistribution status: TBD
- Derivation status: TBD (source resource, not a derived wordlist)
- Notice obligations: TBD (SCOWL + component notices: Ispell/WordNet/VarCon/etc.)
- Attribution obligations: TBD
- Notice mapping file / section: docs/callhome_lexicon_attribution_notices.md (TBD)
- Hash algorithm: TBD (e.g. SHA256)
- File hash(es): TBD (not computed in this PR)
- Hash computed by: TBD
- Hash computed date: TBD
- Approved for local placement: NO / NOT APPROVED
- Approved for loader use: NO / NOT APPROVED
- Approved for aggregate dry run: NO / NOT APPROVED
- Approved for clean promotion: NO / NOT APPROVED
- Reviewer / approver: TBD
- Approval PR: TBD
- Notes: Status: NOT PLACED / NOT APPROVED FOR USE.
```

## Spanish resource template
Not filled. Copy and complete only after explicit approval; do not invent
version/source facts beyond what existing docs already reference.

```
### Resource entry: spanish_rla_es_hunspell

- Resource role: Spanish lexicon
- Language: spa
- Upstream project / package: Spanish RLA-ES/LibreOffice Hunspell candidate
  (see docs/callhome_lexicon_resource_manifest.md / license_sources.md)
- Upstream source URL or package reference: TBD (use references already recorded
  in docs/callhome_lexicon_license_sources.md; do not invent new facts)
- Upstream version / release / date: TBD
- Exact upstream files used: TBD (choose es / es_ES / other variant)
- Local ignored path: TBD under data/resources/local_lexicons/
- Local file names: TBD (NOT PLACED)
- File type: TBD (e.g. Hunspell .dic / plain wordlist)
- Loader mode: TBD (plain wordlist | Hunspell .dic raw-entry)
- Encoding: TBD (expected UTF-8)
- License pathway: TBD (triple disjunctive GPL/LGPL/MPL; MPL 1.1-or-later
  preference recorded in the manifest draft; confirm before use)
- Redistribution status: TBD
- Derivation status: TBD (source resource, not a derived wordlist)
- Notice obligations: TBD (RLA-ES attribution; Santiago Bosio + contributors)
- Attribution obligations: TBD
- Notice mapping file / section: docs/callhome_lexicon_attribution_notices.md (TBD)
- Hash algorithm: TBD (e.g. SHA256)
- File hash(es): TBD (not computed in this PR)
- Hash computed by: TBD
- Hash computed date: TBD
- Approved for local placement: NO / NOT APPROVED
- Approved for loader use: NO / NOT APPROVED
- Approved for aggregate dry run: NO / NOT APPROVED
- Approved for clean promotion: NO / NOT APPROVED
- Reviewer / approver: TBD
- Approval PR: TBD
- Notes: Status: NOT PLACED / NOT APPROVED FOR USE.
```

## Derived wordlist template
Not filled. For any future normalized wordlist derived from an approved parent
resource.

```
### Derived wordlist entry: <derived id>

- Parent resource(s): TBD (must reference an approved English/Spanish entry above)
- Derivation script / process: TBD (documented + reproducible)
- Normalization policy version / doc: docs/callhome_lexicon_normalization_policy.md
- Source files used: TBD (approved upstream lexicon files only)
- Output file name: TBD (NOT PLACED)
- Local ignored path: TBD under data/resources/local_lexicons/
- Hash algorithm / hash: TBD (e.g. SHA256; not computed in this PR)
- Notice / license inherited from parent: TBD (inherits parent obligations)
- Committing allowed: NO by default (local/gitignored unless later approved)
- Approved for local placement: NO / NOT APPROVED
- Approved for loader use: NO / NOT APPROVED
- Approved for aggregate dry run: NO / NOT APPROVED
- Approved for clean promotion: NO / NOT APPROVED
- Reviewer / approver: TBD
- Approval PR: TBD
- Notes: Status: NOT PLACED / NOT APPROVED FOR USE.
```

Rules for derived wordlists:

- Derived wordlists **stay local / gitignored** unless a **later PR explicitly
  approves committing them**.
- Derived wordlists **must not use CALLHOME tokens, CALLHOME-derived token lists,
  or CALLHOME frequency lists**.
- Derived wordlists **must not be filtered based on CALLHOME** in any way.
- A derived file **inherits** its parent resource's license/notice obligations.

## Hash / checksum policy
- Hashes **may** be recorded for local files if legally/safely acceptable.
- Hash records **must not** expose transcript data.
- Recording a hash is **not** resource redistribution.
- Hashes **do not imply approval** — an entry with hashes can still be
  `NOT APPROVED`.
- Future actual entries should use a **clear algorithm such as SHA256**.
- **Do not compute hashes in this PR** (no local files exist to hash, by design).

## Attribution / notice mapping
- Every local or derived file **must map** to its required attribution/notice
  obligations.
- Link the mapping back to `docs/callhome_lexicon_attribution_notices.md`.
- If notices **cannot be mapped**, resource use is **blocked**.
- If **license ambiguity remains**, resource use is **blocked**.

## Approval status fields
Each entry carries **four independent** statuses, each defaulting to
`NO` / `NOT APPROVED` in the template:

- **Approved for local placement** — files may be placed under the ignored path.
- **Approved for loader use** — the loader may read the placed files locally.
- **Approved for aggregate dry run** — the resource may feed an aggregate-only
  dry run.
- **Approved for clean promotion** — validation may contribute to promoting rows
  to `clean`.

Independence rules:

- **Local placement alone is not adoption.**
- **Loader use alone is not clean promotion.**
- **Aggregate dry run alone is not clean promotion.**
- Each later gate requires the earlier ones **plus** its own explicit approval.

## Safety guardrails
- **CALLHOME text must never be uploaded externally.**
- **CALLHOME-derived token lists must never shape, filter, expand, or modify**
  lexicons or derived wordlists.
- **CALLHOME never feeds `CsCont`** (Bangor-sourced only).
- Clean **English** rows may route **only** to `EnglishMono` + `MonoCont`, and
  only after explicit approval.
- Clean **Spanish** rows may route **only** to `SpanishMono` + `MonoCont`, and
  only after explicit approval.
- **No condition JSONL** is produced from this template.
- **No model training** is triggered by this template.

## Failure conditions
Resource use must **stop** if:

- the exact upstream source / version **cannot be identified**
- the **license pathway is unclear**
- **notices cannot be preserved**
- local files are **not gitignored**
- hashes / metadata are **missing when required**
- any **CALLHOME transcript text** would be exposed
- any **token strings from real data** would be committed
- a **derived wordlist depends on CALLHOME tokens**
- validation would route **CALLHOME to `CsCont`**
- clean promotion is approved **implicitly instead of explicitly**

## Explicit non-goals
- no real resource placement
- no real resource adoption
- no download
- no loader execution
- no validator execution over real data
- no aggregate dry run
- no clean promotion
- no condition JSONL
- no model training
- no Bangor / `CsCont` logic

## Next steps
- A future **approval PR** may fill this template for the English and Spanish
  local resources (and any derived wordlist).
- Only after that may **local placement** and an **aggregate-only dry run** be
  considered — each behind its own explicit approval.
- **Keep the real pipeline unchanged for now.** Until entries are filled and
  approved, no real lexicon is loaded, every CALLHOME row stays `not_validated`,
  and the `clean` count stays zero.
