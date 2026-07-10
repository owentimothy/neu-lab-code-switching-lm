# CALLHOME Lexicon Local-Use Checklist

## Status
- **Docs-only checklist, not implementation.** No code changes.
- **No resource is adopted, downloaded, committed, loaded, or used.**
- **No real lexicon files or derived wordlists are added.**
- **No clean promotion is enabled.** No condition JSONL construction. No model
  training.
- **The real pipeline remains unchanged** (`default_source_validation` only;
  validator/loader not wired in).
- No transcript excerpts, tokens, header values, participant names, speaker IDs,
  or filenames appear here.
- Permission state: **Decision B** (see `docs/callhome_ground_rules.md`).

## Purpose
The repo now has the **policy**, **storage guardrails**, a **loader scaffold**,
and **synthetic validator tests** for lexicon-based source validation. This
document defines the **checklist that must be satisfied before moving from
scaffold to local-only resource use** — i.e. before approved resources may be
placed under the ignored local path and exercised in an aggregate-only dry run.
It gates that transition; it does not perform it.

## Current gate state
**Completed** (in `main`):
- resource policy (`docs/callhome_lexicon_resource_policy.md`)
- candidate survey (`docs/callhome_lexicon_resource_candidates.md`)
- license-source evidence (`docs/callhome_lexicon_license_sources.md`)
- manifest draft (`docs/callhome_lexicon_resource_manifest.md`)
- attribution/notice inventory (`docs/callhome_lexicon_attribution_notices.md`)
- normalization policy (`docs/callhome_lexicon_normalization_policy.md`)
- synthetic normalization tests (`tests/test_callhome_lexicon_validation.py`)
- storage scaffold (`docs/callhome_lexicon_storage_scaffold.md`; ignored path)
- loader scaffold (`src/cslm/data/callhome_lexicon_loader.py`)

**Not completed** (still ahead):
- no actual resource placement
- no derived wordlist generation
- no local resource manifest with hashes
- no aggregate dry run using real lexicons
- no clean-promotion approval
- no condition JSONL
- no training

## Resources covered
- **English** SCOWL/LibreOffice `en_US` Hunspell candidate.
- **Spanish** RLA-ES/LibreOffice Hunspell candidate.
- **Any derived normalized wordlists** produced from those resources.

Do **not** broaden this document to other resources.

## Pre-placement checklist
Before any file is placed locally under `data/resources/local_lexicons/`:

- [ ] exact resource name identified
- [ ] exact upstream source URL or package source recorded in docs
- [ ] exact version / release / date recorded
- [ ] license pathway recorded
- [ ] notice obligations recorded
- [ ] attribution requirements recorded
- [ ] whether redistribution is allowed or blocked recorded
- [ ] whether a derived wordlist can ever be committed recorded
- [ ] local-only status confirmed
- [ ] explicit human approval recorded in a future PR
- [ ] no CALLHOME text uploaded externally
- [ ] no CALLHOME-derived token lists used to select, filter, or modify resources

## Local placement checklist
When resources are eventually placed locally:

- [ ] files go under `data/resources/local_lexicons/`
- [ ] the path remains gitignored
- [ ] no files under that path are committed
- [ ] no `.dic` / `.aff` files are committed
- [ ] no upstream license files are committed unless separately approved
- [ ] no long license texts pasted
- [ ] local file names are stable and descriptive
- [ ] local file hashes may be computed and recorded **only if** legally/safely
      acceptable and containing no transcript data
- [ ] local placement is **not** adoption by itself
- [ ] local placement does **not** enable clean promotion by itself

## Attribution / notice checklist
Before any local or derived file is used:

- [ ] a notice mapping exists from file → required notices
- [ ] required attribution has been recorded
- [ ] the selected license pathway is recorded
- [ ] the verbatim notice appendix plan is resolved if needed
- [ ] if notices cannot be preserved adequately, resource use is **blocked**
- [ ] if license ambiguity remains, resource use is **blocked**

## Derived wordlist checklist
Before generating or using derived normalized wordlists:

- [ ] the derivation script / process is documented
- [ ] derivation uses only approved upstream lexicon files
- [ ] derivation does **not** use CALLHOME tokens
- [ ] derivation does **not** use CALLHOME-derived frequency lists
- [ ] derivation does **not** filter based on CALLHOME
- [ ] derived wordlists stay local / gitignored unless later explicitly approved
- [ ] derived files inherit source notice / license obligations
- [ ] derived files have hashes / metadata recorded if approved
- [ ] no derived file is committed in this PR

## Loader-use checklist
Before using the loader on real local resources:

- [ ] loader path arguments are explicit
- [ ] no hardcoded downloads
- [ ] no network calls
- [ ] no `data/raw/callhome` reads
- [ ] no `.aff` expansion unless a later documented implementation supports it
- [ ] raw entries only unless a future PR changes this with tests
- [ ] the validator remains the single normalization authority
- [ ] synthetic tests pass before and after
- [ ] the loader is **not** imported by the real summary script until an explicit
      future wiring PR

## Aggregate dry-run checklist
Before an aggregate-only dry run with local resources:

- [ ] resources placed locally and ignored
- [ ] notices and license records complete
- [ ] loader tests pass
- [ ] validator tests pass
- [ ] storage guardrail tests pass
- [ ] dry-run output is **aggregate-only**, with **none** of: transcript text,
      token strings, source lines, header values, participant names, raw speaker
      IDs, raw filenames, or any per-row transcript-bearing output
- [ ] output may include **only counts** such as:
  - validated vs `not_validated`
  - validation-method counts
  - validation-reason counts
  - unknown / ambiguous / non-expected / no-retained aggregate counts if
    implemented safely
- [ ] the dry run does **not** create condition JSONL
- [ ] the dry run does **not** change training inputs
- [ ] the dry run does **not** enable clean promotion unless separately approved

## Review and approval checklist
Before clean promotion:

- [ ] the aggregate dry-run is reviewed
- [ ] unexpected counts are investigated **without exposing transcript content**
- [ ] false-positive risk is assessed
- [ ] source-language validation behavior is approved
- [ ] explicit approval is recorded in a future PR
- [ ] only then may **clean English** rows route to **`EnglishMono` + `MonoCont`**
- [ ] only then may **clean Spanish** rows route to **`SpanishMono` + `MonoCont`**
- [ ] **CALLHOME still never feeds `CsCont`**

## Explicit non-goals
- no real lexicon adoption
- no real resource download
- no resource files
- no derived files
- no loader wiring
- no validator wiring
- no clean promotion
- no condition JSONL
- no tokenizer changes
- no model training
- no Bangor / `CsCont` logic

## Failure conditions
Resource use must **stop** if:

- the license pathway is unclear
- notices cannot be preserved
- redistribution / derivation status is unclear
- any CALLHOME transcript text would be exposed
- any token strings from real data would be committed
- the local path is not ignored
- the loader would require network access
- a derived wordlist depends on CALLHOME tokens
- validation would route CALLHOME into `CsCont`
- the aggregate dry-run emits per-row or transcript-bearing output
- clean promotion is enabled without explicit approval

## Next steps
- After this checklist, the next future branch may be a **local-only
  resource-placement / dry-run preparation** branch — but **only after explicit
  approval**.
- **Keep the real pipeline unchanged for now.** Until the checklist and approvals
  are satisfied, no real lexicon is loaded, every CALLHOME row stays
  `not_validated`, and the `clean` count stays zero.
