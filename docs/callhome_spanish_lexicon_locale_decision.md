# CALLHOME Spanish Lexicon Locale Decision

## Status
- **Docs-only decision record, not implementation.** No code changes.
- **No Spanish locale is selected.**
- **No lexicon artifact is saved, downloaded, copied, or placed.** The local
  resource directory (`data/resources/local_lexicons/`) is not created or
  populated.
- **No hashes.** No loader use. No validator use. No aggregate dry run. No clean
  promotion. No condition JSONL. No tokenization or dataset construction. No model
  training.
- **The real pipeline remains unchanged** (`default_source_validation` only;
  validator/loader not wired in). Every real CALLHOME row stays `not_validated`;
  `clean` stays zero.
- **No CALLHOME transcript content was inspected, and no CALLHOME-derived evidence
  was used.** No external browsing was performed; this record rests only on facts
  already established in the repository.
- **All operational approvals remain `NO / NOT APPROVED`.**

## Decision
```text
Decision: DEFER SPANISH LEXICON LOCALE SELECTION
```

- **Effective immediately** for the current pipeline phase.
- **No Spanish regional variant is approved** (`es_ES`, `es_MX`, `es_US`, or any
  other).
- **No fallback default is silently selected.** There is no implicit default
  variant.
- `es_ES`, `es_MX`, and `es_US` remain **candidate examples only**.
- **No union, intersection, or common-core resource is approved.**
- The decision **may be reopened only through a later dedicated research-policy
  PR** (see "What Would Be Required to Reopen the Decision").

This is a **deliberate research-control decision**, not indecision or failure.
Deferring prevents circularity (letting CALLHOME choose its own gate) and prevents
an unexamined regional assumption from silently entering the Spanish data gate.

## Purpose
The locale policy (`docs/callhome_spanish_lexicon_locale_policy.md`) evaluated the
principled strategies for choosing a Spanish expected-language lexicon and
**recommended deferral** of the binding choice. This record **formally ratifies**
that outcome as an explicit, documented decision, and fixes its operational
consequences, so that no Spanish resource work can proceed by default. It selects
nothing and approves no resource.

## Scope
Docs-only, and **Spanish-specific**. This record: selects no resource file; grants
no local-placement, loader-use, dry-run, or clean-promotion approval; creates or
populates no `data/resources/local_lexicons/`; computes no hashes; runs no loader
or validator; enables no dry run; creates no condition JSONL; tokenizes nothing;
trains nothing; and changes no routing. It **does not** block unrelated English
metadata or future English-policy work — it blocks **Spanish** resource use only.

## Relationship to Existing Documentation
This decision consumes and is bound by (repository-relative):

- `docs/callhome_spanish_lexicon_locale_policy.md` — the strategy evaluation and
  deferral recommendation this record ratifies.
- `docs/callhome_lexicon_exact_resource_metadata.md` — the verified 23-variant
  inventory, license alternatives, encoding, and loader-compatibility facts.
- `docs/callhome_lexicon_local_resource_approval_record.md` — the concrete
  candidate record; every approval field `NO / NOT APPROVED`.
- `docs/callhome_lexicon_placement_approval_template.md` — the reviewer gate a
  future placement must clear.
- `docs/callhome_lexicon_resource_policy.md` — acceptable-resource / storage /
  review-gate contract; conservative "prefer false negatives" posture.
- `docs/callhome_lexicon_normalization_policy.md` — identical normalization on both
  sides; Spanish accents preserved; ambiguous/unknown/other-language →
  `not_validated`; the unresolved regional-variant question.
- `docs/callhome_lexicon_local_use_checklist.md` — the pre-placement / local-use
  gates.
- `docs/callhome_lexicon_dry_run_plan.md` — the aggregate dry-run plan (which may
  only evaluate an already-approved configuration, never select one).

This document sits **after** the locale policy and **before** any locale-selection
PR. It records the approved decision to defer while changing no resource or
operational approval state.

## Why the Decision Is Deferred
1. **Research construct ambiguity.** Selecting one national lexicon **narrows the
   operational meaning of "Spanish monolingual"** to that standard. The meaning of
   the construct is a research choice that must be made deliberately, not defaulted.
2. **Regional bias.** A single variant may **preferentially validate one regional
   standard**, so which rows are admitted could correlate with variety — a bias
   that must be examined before, not after, it can affect any dataset.
3. **No independently sufficient basis yet.** The existing metadata establishes
   **availability and reproducibility** facts (which files exist, pinning,
   encoding), **not** which locale best represents the research construct. No
   comparative lexical coverage was measured in this branch. Comparative CALLHOME
   coverage, validation yield, and unknown-token behavior may not be used to select
   or revise the locale.
4. **CALLHOME circularity prohibition.** CALLHOME tokens, validation yields,
   unknown-token counts, and aggregate dry-run results **must not** choose or
   revise the locale — that would let the corpus select its own gate.
5. **Derived-resource burden.** Union / intersection / common-core options are
   **derived resources** requiring separate design, provenance, notice, manifest,
   and approval work; none is approved.
6. **Conservative gate principle.** Because **false negatives are safer than false
   positives**, deferral is preferable to committing to an unjustified
   single-variant choice or an unapproved broad derived-resource gate.

## Evidence Considered
The decision weighed only these already-established kinds of evidence:

- the verified upstream **variant inventory** (23 national variants; no bare `es`);
- the **exact-resource metadata** (files, license alternatives, encoding, pins);
- **reproducibility and pinning** considerations (single file pair vs. derived set);
- **loader compatibility** (raw-entry mode; no `.aff` expansion);
- **derived-resource complexity** (union/intersection/common-core burden);
- the **false-positive / false-negative asymmetry** (FP is the dangerous error);
- **regional-bias implications** of a single-variant gate;
- existing repository **source-boundary rules** (CALLHOME never shapes the lexicon;
  CALLHOME never feeds `CsCont`).

No comparative lexical **coverage** was measured; availability and reproducibility
facts are not the same as research fitness.

## Evidence Explicitly Excluded
The decision did **not** use any of:

- CALLHOME transcript content
- CALLHOME token lists
- CALLHOME vocabulary
- CALLHOME frequency counts
- CALLHOME unknown-token counts
- CALLHOME validation yields
- CALLHOME speaker geography
- participant names
- regional forms observed in CALLHOME
- actual lexicon-entry comparison
- model results

## Operational Consequences
Because Spanish locale selection is deferred:

- **No Spanish resource may be approved for local placement.**
- **No Spanish `.dic` file may be selected operationally.**
- **No Spanish loader-use approval may be granted.**
- **No Spanish aggregate dry run may run.**
- **No Spanish clean promotion may occur.**
- **Spanish CALLHOME rows remain `not_validated`.**
- **`SpanishMono` candidates remain zero.**
- **The Spanish contribution to `MonoCont` remains zero.**
- **CALLHOME still never feeds `CsCont`** (Bangor-sourced only).

This is **Spanish-specific**: it does **not** block unrelated English metadata or
future English-policy work; it blocks **Spanish** resource use until a later
locale-selection decision is approved.

## What Would Be Required to Reopen the Decision
Reopening requires a later **dedicated PR** that provides all of:

- a **clearly stated research construct** for "Spanish monolingual";
- **independently sourced, non-CALLHOME justification** for the candidate locale;
- an **exact immutable upstream file pin** (commit-pinned `.dic`/`.aff`);
- **verified encoding** for the selected variant's files;
- a **verified license / notice pathway** (selected among the triple alternatives,
  with notices preservable);
- an **explicit regional-bias analysis**;
- an **explanation of why a single variant is appropriate** for the construct;
- **confirmation that no CALLHOME-derived evidence was used**;
- an **explicit locale-selection approval**.

**CALLHOME diagnostics are not required and not acceptable** as evidence for
selection.

## Acceptable Future Evidence
Examples of evidence that could justify a future selection:

- peer-reviewed linguistic research on standard-variety choice;
- official corpus documentation about the intended language variety, **without**
  transcript inspection;
- externally defined experimental comparability rules;
- institutional or lab-level corpus policy;
- a **pre-registered** rule for selecting one upstream variant;
- authoritative metadata on resource scope and construction;
- independent methodology review.

## Unacceptable Future Evidence
Examples that must **never** justify a selection:

- whichever variant validates the most CALLHOME rows;
- whichever minimizes CALLHOME unknown tokens;
- whichever produces the most condition candidates;
- participant names or geography;
- CALLHOME lexical frequencies;
- manual inspection of CALLHOME regional vocabulary;
- repeated dry runs used to optimize the locale choice;
- modifying a lexicon after observing CALLHOME failures.

## Decision Matrix
No locale is preferred; single variants are **deferred**, derived resources are
**not approved**, and continued deferral is the **approved decision**.

| Option                   | Current decision  | Reason                                                       |
| ------------------------ | ----------------- | ------------------------------------------------------------ |
| `es_ES`                  | DEFERRED          | exact file exists, but research fitness not established      |
| `es_MX`                  | DEFERRED          | exact file exists, but research fitness not established      |
| `es_US`                  | DEFERRED          | exact file exists, but boundary implications not established |
| another single variant   | DEFERRED          | requires independent justification                           |
| all-variant union        | NO / NOT APPROVED | derived resource; broader gate; separate policy required     |
| intersection/common core | NO / NOT APPROVED | derived resource; separate design required                   |
| continued deferral       | APPROVED DECISION | prevents unjustified and circular selection                  |

## Approval State
| Gate                         | Status            |
| ---------------------------- | ----------------- |
| deferral decision documented | APPROVED DECISION |
| Spanish locale selected      | NO / NOT APPROVED |
| Spanish resource placement   | NO / NOT APPROVED |
| loader use                   | NO / NOT APPROVED |
| aggregate dry run            | NO / NOT APPROVED |
| clean promotion              | NO / NOT APPROVED |
| condition JSONL              | NO / NOT APPROVED |
| model training               | NO / NOT APPROVED |

**`APPROVED DECISION` applies only to the decision to defer** — it approves **no**
resource, placement, loader use, dry run, clean promotion, JSONL, or training.

## Failure and Stop Conditions
Work must **stop** if:

- a locale is **silently selected**
- `es_ES` is treated as a **default**
- a locale is selected from **CALLHOME yields**
- **CALLHOME diagnostics are used comparatively** across variants
- a resource file is **saved or placed**
- a **union / intersection / common core** is generated
- **hashes** are computed
- **loader use** is introduced
- **validator use** is introduced
- a **dry run** is enabled
- **clean promotion** is proposed
- **condition JSONL or training** is proposed
- **CALLHOME could route to `CsCont`**

## Reviewer Checklist
- [ ] the document records **deferral, not selection**
- [ ] **no fallback locale** is implied (no silent default)
- [ ] **no CALLHOME-derived evidence** was used
- [ ] acceptable and unacceptable **future evidence** are explicit
- [ ] Spanish operational gates remain **closed** (`NO / NOT APPROVED`)
- [ ] the **English side is not accidentally blocked** by this Spanish-specific decision
- [ ] source-boundary rules remain intact (CALLHOME never shapes the lexicon; never feeds `CsCont`)
- [ ] real pipeline behavior is unchanged

## Next Approved Step
The next step is **not** Spanish placement. Depending on review:

1. **pause Spanish lexicon work** until independent, non-CALLHOME evidence exists;
2. **continue English-side approval work separately**, if desired (unblocked by
   this decision);
3. **develop an external-evidence research plan** for Spanish locale selection;
4. **later open a dedicated locale-selection PR** that meets the reopening
   requirements above.

**Do not** use CALLHOME dry-run output to choose the locale.

## Final Gate Status
- **Deferral is the approved decision.**
- **No Spanish locale is selected.**
- **No Spanish resource is placed or loaded.**
- **No Spanish real-data validation occurs.**
- **Spanish CALLHOME rows remain blocked.**
- **All real CALLHOME rows remain `not_validated`** (`clean` stays zero).
- **The gate remains closed** until a later locale-selection decision is separately
  approved.
