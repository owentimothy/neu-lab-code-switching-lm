# CALLHOME Lexicon Placement Approval (Template)

## Status
- **Docs-only reviewer template, not implementation.** No code changes.
- **This document approves nothing by itself.** It is a form + checklist that must
  be **completed and reviewed before** any real local lexicon placement.
- **No resource is downloaded, copied, generated, derived, placed, loaded, or
  used** in this branch.
- **This branch does not create or populate the local resource directory**
  (`data/resources/local_lexicons/` remains local-only and ignored).
- **No hashes are computed** in this template-only branch.
- **No clean promotion is enabled.** No condition JSONL construction. No tokenizer
  or dataset construction. No model training. No loader enabled. No validator run
  over real CALLHOME.
- **The real pipeline remains unchanged** (`default_source_validation` only;
  validator/loader not wired in).
- No transcript excerpts, tokens, header values, participant names, speaker IDs,
  or filenames appear here.
- **All approval fields default to `NO / NOT APPROVED`.**

## Purpose
This is a **conservative approval form and reviewer checklist** that must clear
**before any real local lexicon placement**. Its job is to prevent accidental
movement from:

`candidate resource` → `placed resource` → `used resource`

**without separate, explicit approvals at each step.** Completing this form grants
**placement consideration only**; it never grants use.

Crucially:

- **Placement approval is not resource adoption.**
- **Placement approval is not loader-use approval.**
- **Placement approval is not aggregate-dry-run approval.**
- **Placement approval is not clean-promotion approval.**
- **Placement approval is not condition-JSONL approval.**
- **Placement approval is not model-training approval.**

## Relationship to Existing Documentation
This document sits **between** the candidate/resource documentation chain and
**actual local placement**. It consumes the decisions those docs record and gates
the transition to placing files locally. Related docs (repository-relative):

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

The candidate/resource docs establish *what* the resources are and their
license/notice pathways; the manifest template records *what must be logged* once
files are placed. **This document is the reviewer gate that authorizes (or
refuses) the placement step itself.**

## When to Use This Template
- Use it when a **future PR** proposes placing an approved candidate lexicon under
  the ignored local path for the first time.
- Complete it **only after** the resource's identity, version, license pathway,
  and notice/attribution obligations are already documented in the docs chain
  above.
- Fill **one request** per resource (English, Spanish, or a derived wordlist).
- Copying or completing this form is **not** approval; a named reviewer must
  record an explicit decision.

## What This Template Does Not Approve
Completing this template does **not** grant any of the following. Each is a
**separate** gate requiring its own explicit approval:

- resource adoption
- loader use
- aggregate dry run
- clean promotion
- condition JSONL
- model training

See the **Explicit Non-Approval Gates** matrix below.

## Placement Approval Request Template
Copy this block once **per resource** and fill it in a future PR. Leave unresolved
values as `TBD`; **every approval field defaults to `NO / NOT APPROVED`.** Do not
fill real resource versions, filenames, hashes, or approval identities here.

```
### Placement request: <resource id>

- Request status: DRAFT / NOT APPROVED
- Requested by: TBD
- Date: TBD
- Reviewers: TBD
- Approval PR: TBD
- Resource role: TBD (English lexicon | Spanish lexicon | derived wordlist)
- Language: TBD (eng | spa)
- Upstream project / package: TBD
- Upstream source: TBD (reference already-recorded docs; do not invent facts)
- Exact version or release date: TBD
- Exact upstream files intended for local placement: TBD
- Intended ignored local directory: data/resources/local_lexicons/ (TBD subpath)
- Intended local filenames: TBD (NOT PLACED)
- File type: TBD (Hunspell .dic | plain wordlist)
- Expected encoding: TBD (expected UTF-8)
- Proposed loader mode: TBD (plain wordlist | Hunspell .dic raw-entry)
- License pathway: TBD
- Redistribution status: TBD
- Notice requirements: TBD
- Attribution requirements: TBD
- Derivation status: TBD (source resource | derived wordlist)
- Normalized derivatives proposed: TBD (yes/no; if yes, separate derived request)
- Any CALLHOME-derived material influenced the resource: MUST BE "no"
- Placement approval status: NO / NOT APPROVED
- Reviewer decision: NO / NOT APPROVED
- Reviewer notes: TBD
```

## Required Reviewer Checks
Before a reviewer may approve placement, confirm **all** of the following:

- [ ] resource identity, version, and source are documented in the docs chain
- [ ] exact upstream files intended for placement are named
- [ ] license pathway is documented and unambiguous
- [ ] notice + attribution obligations are documented and satisfiable
- [ ] intended local destination is under `data/resources/local_lexicons/`
- [ ] the repository ignore policy covers
      `data/resources/local_lexicons/`
- [ ] **no** CALLHOME-derived material influenced the resource in any way
- [ ] placement is being approved **independently** of loader use, dry run, and
      clean promotion
- [ ] no hashes are computed in the template/approval PR itself
- [ ] no resource files are downloaded, generated, derived, placed, loaded, or
      used in the approval PR itself
- [ ] the request proposes **no** condition JSONL, tokenizer/dataset work, or
      training

## English Resource Placement Checklist
For the **English** SCOWL/LibreOffice `en_US` Hunspell candidate. This checklist
does **not** imply the English resource is currently approved.

- [ ] resource identity is documented
- [ ] version / source is documented
- [ ] exact intended files are named
- [ ] license pathway is documented
- [ ] notice / attribution obligations are documented
- [ ] local destination is under `data/resources/local_lexicons/`
- [ ] no CALLHOME-derived material influenced the resource
- [ ] placement is approved **independently** from loader use
- [ ] placement is approved **independently** from dry-run use
- [ ] placement is approved **independently** from clean promotion

## Spanish Resource Placement Checklist
For the **Spanish** RLA-ES/LibreOffice Hunspell candidate. This checklist does
**not** imply the Spanish resource is currently approved.

- [ ] resource identity is documented
- [ ] version / source is documented
- [ ] exact intended files are named
- [ ] license pathway is documented
- [ ] notice / attribution obligations are documented
- [ ] local destination is under `data/resources/local_lexicons/`
- [ ] no CALLHOME-derived material influenced the resource
- [ ] placement is approved **independently** from loader use
- [ ] placement is approved **independently** from dry-run use
- [ ] placement is approved **independently** from clean promotion

## Local Path and Gitignore Checks
Local resources **must** remain under `data/resources/local_lexicons/`, and that
path **must remain gitignored**. `git status` **must not** show real lexicon
files as tracked or untracked.

Before approving placement, reviewers must confirm that the repository ignore
policy covers `data/resources/local_lexicons/`.

After a future placement request is approved and files are placed locally, the
implementer must verify the actual placed paths with:

```bash
git check-ignore -v data/resources/local_lexicons/
git status --short
```

`git check-ignore -v` must confirm that the relevant local path is ignored and
identify the matching `.gitignore` rule. Real local resource files must not
appear as tracked or untracked entries in `git status`.

Do not create the directory or run placement-specific checks as part of this
template-only branch.

## License and Notice Checks
- [ ] license pathway selected and recorded (see
      `docs/callhome_lexicon_license_sources.md`)
- [ ] redistribution status recorded
- [ ] required notices identified and preservable (see
      `docs/callhome_lexicon_attribution_notices.md`)
- [ ] required attribution identified and preservable
- [ ] if notices **cannot** be preserved, placement is **blocked**
- [ ] if license ambiguity remains, placement is **blocked**
- [ ] **no long license texts pasted** into the repo; summarize and point to
      source references

## Hash and Metadata Checks
Hashes belong to a **later local-placement record**, computed **after** approval
and **after** files are placed locally — **never** in this template-only branch.
Future entries should record:

```
- Hash algorithm: TBD (e.g. SHA256)
- Local file hash: TBD (not computed in this branch)
- Hash computed by: TBD
- Hash computation date: TBD
- Source / version linkage: TBD (hash must tie to the approved source + version)
```

**This template-only branch must not compute hashes.** A hash records integrity
and provenance; it is **not** approval and **not** redistribution, and it must
**never** expose transcript data.

## Explicit Non-Approval Gates
This document does **not** grant any of the following. The matrix is exhaustive
for this step:

| Gate                         | Status         |
| ---------------------------- | -------------- |
| candidate-resource approval  | NO / NOT APPROVED |
| local-placement approval     | NO / NOT APPROVED |
| resource-adoption approval   | NO / NOT APPROVED |
| loader-use approval          | NO / NOT APPROVED |
| aggregate-dry-run approval   | NO / NOT APPROVED |
| clean-promotion approval     | NO / NOT APPROVED |
| condition-JSONL approval     | NO / NOT APPROVED |
| training approval            | NO / NOT APPROVED |

Even a fully completed placement request only ever flips **local-placement
approval** (in its own PR); every other row stays `NO / NOT APPROVED` until its
own separate approval.

## Failure and Stop Conditions
The reviewer or implementer must **stop** if:

- the local destination is **outside** `data/resources/local_lexicons/`
- the path is **not** gitignored
- `git status` **exposes** real resource files (tracked or untracked)
- license or notice obligations are **unresolved**
- the exact source / version is **unknown**
- the exact upstream files are **unknown**
- hashes **cannot later be tied** to the approved source / version
- **CALLHOME-derived material influenced** the resource
- the resource would be **used before separate loader approval**
- the validator would **run over real CALLHOME before separate dry-run approval**
- **clean promotion is proposed in the same step**
- **condition JSONL or training is proposed in the same step**
- CALLHOME **could route to `CsCont`**

## Safety Guardrails
- Local resources must remain under `data/resources/local_lexicons/`, and that
  path must remain **gitignored**; `git status` must not show real lexicon files.
- **No raw CALLHOME `.cha` files, ZIPs, transcript-bearing JSONL, or
  transcript-bearing outputs** may be committed.
- **No CALLHOME transcript text** may be quoted or exposed.
- **No real CALLHOME token strings** may be quoted or exposed.
- **No header values, participant names, raw speaker IDs, or raw filenames** may
  be quoted or exposed.
- **CALLHOME-derived token lists must never be used to create, shape, expand,
  filter, normalize, or modify lexicons.**
- **CALLHOME text or tokens must never influence lexicon construction.**
- **CALLHOME must never feed `CsCont`** (Bangor-sourced only).
- Future **clean English** CALLHOME rows may route **only** to `EnglishMono` and
  `MonoCont`.
- Future **clean Spanish** CALLHOME rows may route **only** to `SpanishMono` and
  `MonoCont`.
- Those routing rules apply **only after** later explicit validation and
  clean-promotion approval.
- **No condition JSONL** may be created in this step.
- **No tokenizer or dataset construction** may occur in this step.
- **No model training** may occur in this step.
- **No loader** may be enabled in this step.
- **No validator** may be run over real CALLHOME in this step.
- **No hashes** should be computed in this template-only branch.
- **No resource files** should be downloaded, copied, generated, derived, placed,
  loaded, or used in this branch.

## Next Steps After Approval
The future sequence (described here, **not** performed):

1. Complete and review the placement request.
2. Approve local placement in a **dedicated PR**.
3. Place approved files locally under the ignored path.
4. Verify gitignore behavior (`git check-ignore` / `git status`).
5. Record exact local metadata and hashes.
6. Request **separate** loader-use approval.
7. Request **separate** aggregate-dry-run approval.
8. Run aggregate-only dry validation **locally**.
9. Review counts and safety invariants.
10. **Only then** consider a **separate** clean-promotion PR.

**The gate remains closed.** No resource is placed, loaded, validated, promoted,
serialized to JSONL, or trained on until **each** later approval is **separately**
granted. Until then, no real lexicon is loaded, every CALLHOME row stays
`not_validated`, and the `clean` count stays zero.
