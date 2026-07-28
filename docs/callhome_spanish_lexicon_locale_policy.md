# CALLHOME Spanish Lexicon Locale Policy

## Status
- **Docs-only policy, not implementation.** No code changes.
- **No lexicon artifact is saved, downloaded, copied, or placed.** The local
  resource directory (`data/resources/local_lexicons/`) is not created or
  populated.
- **No locale file is selected operationally.** No derived wordlists. No hashes.
- **No loader use. No validator use.** No aggregate dry run. No clean promotion.
  No condition JSONL. No tokenization. No model training.
- **The real pipeline remains unchanged** (`default_source_validation` only;
  validator/loader not wired in). Every real CALLHOME row stays `not_validated`;
  `clean` stays zero.
- **No CALLHOME transcript content was inspected, quoted, summarized, counted, or
  used** to write this policy. No external browsing was performed (the policy is
  conceptual and rests on already-verified upstream metadata).
- **All operational approvals remain `NO / NOT APPROVED`.**

## Purpose
The exact-resource-metadata record
(`docs/callhome_lexicon_exact_resource_metadata.md`) verified upstream that the
LibreOffice Spanish dictionary package ships **23 national regional variants**
(`es_AR`, `es_BO`, `es_CL`, `es_CO`, `es_CR`, `es_CU`, `es_DO`, `es_EC`, `es_ES`,
`es_GQ`, `es_GT`, `es_HN`, `es_MX`, `es_NI`, `es_PA`, `es_PE`, `es_PH`, `es_PR`,
`es_PY`, `es_SV`, `es_US`, `es_UY`, `es_VE`) and **no bare `es` general/
pan-Hispanic dictionary file**. The exact Spanish variant to use for future
CALLHOME monolingual validation is still unresolved.

This is **not merely a filename choice**. The selected lexicon determines which
CALLHOME Spanish rows could later pass the monolingual validation gate, so it is a
**corpus-design and linguistic-policy decision**. This policy defines *how* that
choice must be made — and, decisively, how it must **not** be made (it must not be
driven by CALLHOME-derived content).

## Research Question
The parent project compares masked LMs across four corpus conditions
(`EnglishMono`, `SpanishMono`, `MonoCont`, `CsCont`) to study whether
code-switching exposure changes behavior on syntactic probes. CALLHOME Spanish is
a **monolingual source**: a positively-validated clean Spanish row may feed
`SpanishMono` and the Spanish side of `MonoCont`, and **never** `CsCont`. The
locale question is therefore: *which Spanish lexicon defines "confidently Spanish"
for admission into those monolingual conditions, in a way that is conservative,
reproducible, and free of CALLHOME contamination?*

## Scope
Docs-only. This branch must not: select a resource file operationally; approve
local placement; download or save lexicon artifacts; create or populate
`data/resources/local_lexicons/`; compute hashes; enable loader use; run the
validator; run an aggregate dry run; promote clean rows; create condition JSONL;
tokenize datasets; train models; or change routing behavior. Every operational
approval remains `NO / NOT APPROVED`.

## Relationship to Existing Documentation
This policy consumes and is bound by (repository-relative):

- `docs/callhome_lexicon_resource_policy.md` — the acceptable-resource /
  storage / review-gate contract; conservative "prefer false negatives" posture.
- `docs/callhome_lexicon_resource_candidates.md` — candidate survey; cross-language
  cognate/ambiguity concerns.
- `docs/callhome_lexicon_license_sources.md` — RLA-ES / LibreOffice source
  evidence; triple disjunctive license.
- `docs/callhome_lexicon_resource_manifest.md` — pinned candidate manifest draft.
- `docs/callhome_lexicon_attribution_notices.md` — notices to preserve per source.
- `docs/callhome_lexicon_normalization_policy.md` — identical normalization on both
  sides; Spanish accents preserved; ambiguous/unknown/other-language → not_validated.
- `docs/callhome_lexicon_storage_scaffold.md` — ignored local path; no derived
  wordlist committed without approval.
- `docs/callhome_lexicon_local_use_checklist.md`,
  `docs/callhome_lexicon_local_resource_manifest_template.md`,
  `docs/callhome_lexicon_placement_approval_template.md`,
  `docs/callhome_lexicon_local_resource_approval_record.md` — the placement gates.
- `docs/callhome_lexicon_exact_resource_metadata.md` — the verified 23-variant
  inventory, license alternatives, encoding, and loader compatibility used here.

This document sits **before** any locale-selection decision PR and changes no
approval state.

## Decision Constraints
Non-negotiable constraints on how the locale may be chosen:

- **No CALLHOME-derived evidence** of any kind.
- **No transcript inspection.**
- **No token-frequency analysis** of CALLHOME.
- **No unknown-token analysis** of CALLHOME.
- **No adapting the resource to observed CALLHOME validation failures.**
- **No use of participant geography, names, or speaker metadata.**
- **No hidden expansion** of a lexicon.
- **No resource union or intersection** without separate approval.
- **No comparing candidate locales using CALLHOME aggregate yields.**
- **No choosing or revising a locale based on CALLHOME validation rates or
  dry-run performance.**
- **No generic `CsCont` or switching-evidence candidacy for CALLHOME.** Future
  `CsCont-Spanish-Monolingual-Filler` must be selected only from
  `MonoCont-Spanish`.
- **False negatives are preferred over false positives.**

A locale chosen because it *maximizes validation yield on CALLHOME*, or because it
*minimizes unknown tokens on CALLHOME*, is **forbidden** — that would let the
corpus pick its own gate (circular) and could leak corpus structure into the
resource decision. **A future aggregate dry run may assess the consequences of an
already independently selected and approved locale; CALLHOME-derived aggregate
results must not be used to compare candidate locales or decide which locale to
select.**

## What the Lexicon Gate Is and Is Not
- **Is:** a conservative, deterministic *admission gate* answering "is every
  retained lexical token confidently in the expected language, and none in the
  other?" for the purpose of admitting rows to `SpanishMono` + `MonoCont`.
- **Is not:** a model of *all* valid Spanish, a dialectology tool, a coverage
  benchmark, or a description of CALLHOME's variety.
- **Consequence:** the gate should **prefer false negatives**. A genuinely-clean
  Spanish row left `not_validated` is a *safe* miss; a mixed/ambiguous/English-
  adjacent row wrongly marked `clean` is a *harmful* error that would contaminate
  `SpanishMono`/`MonoCont`. Coverage gaps that raise `not_validated` are
  acceptable and expected.

## Candidate Locale Strategies
The strategies evaluated below (none assumed correct in advance):

1. **Single national variant** (general form of options 2–4).
2. **`es_ES`.**
3. **`es_MX`.**
4. **`es_US`.**
5. **Pan-regional union** of multiple variants.
6. **Pan-regional intersection** (common core) of multiple variants.
7. **Common-core plus separately approved regional supplements.**
8. **Defer** selection pending an external corpus-policy decision.

Evaluation criteria (all independent of CALLHOME content): fit to the research
question; conservativeness; false-positive risk; false-negative risk; regional
bias; reproducibility; interpretability; licensing/notice complexity; loader
compatibility; ease of pinning exact files; effect on cross-condition
comparability; whether the choice changes the meaning of "Spanish monolingual";
whether it could accidentally admit English or ambiguous material; whether it
requires lexical expansion/derivation; whether it creates an unapproved derived
resource.

## Single-Variant Strategy
Choosing one national `.dic`/`.aff` pair (e.g. `es_ES`, `es_MX`, `es_US`).

- **Assumption encoded:** that a single national standard is an adequate *proxy*
  for "confidently Spanish" for admission purposes — **not** a claim that CALLHOME
  is that variety (which we cannot and must not assert from CALLHOME content).
- **Reproducibility:** highest — exactly one upstream file pair to pin; no
  derivation; no derived-resource notice/manifest complexity.
- **Loader compatibility:** direct — a single Hunspell `.dic` consumed in
  raw-entry mode (base forms only; no `.aff` expansion under the current loader).
- **Regional coverage limitation:** national lexica under-cover other varieties'
  everyday forms (e.g. regionally-specific vocabulary, voseo-associated forms).
  Under the false-negative-preferring posture, those misses are *acceptable* but
  produce **regional bias**: which rows get admitted may correlate with variety.
- **Interpretability:** high — "validated against `es_XX`" is a single, legible
  statement. But it narrows the meaning of "Spanish monolingual" to one standard.
- **Too narrow?** For a *general* Spanish gate a single national variant is
  arguably narrow; however, narrowness manifests as **false negatives**, which are
  the safe direction. The real risk is not narrowness but **regional bias in which
  rows survive**, which is an interpretability/comparability concern, not a
  contamination concern.

## `es_ES` Assessment
- **Assumption encoded:** peninsular/Castilian standard as the reference lexicon.
- **Coverage:** medium (as for any single national variant; not established as
  broader than other variants).
- **False-positive risk:** low–moderate — cross-language cognates shared with
  English still block by the two-lexicon ambiguity rule (per the normalization
  policy), independent of variant.
- **False-negative risk:** moderate — forms outside the peninsular list yield
  `not_validated` (safe direction).
- **Regional bias:** high (peninsular).
- **Reproducibility:** high — single pinnable `es_ES.dic`/`es_ES.aff`.
- **Interpretability:** high.
- **Narrow verification advantage:** Among the currently documented single-variant
  options, `es_ES` has one narrow verification advantage: its file pair is known
  to exist and `es_ES.aff` has already been independently checked for `SET UTF-8`.
  That does not establish superior lexical coverage, linguistic neutrality,
  licensing status, or research fitness relative to other variants.

## `es_MX` Assessment
- **Assumption encoded:** Mexican standard as the reference lexicon.
- **Coverage:** medium.
- **False-positive risk:** low–moderate (curated national standard).
- **False-negative risk:** moderate for non-Mexican varieties (safe direction).
- **Regional bias:** high (Mexican).
- **Reproducibility:** high — single pinnable pair; encoding must be verified for
  `es_MX.aff` (only `es_ES.aff` encoding was verified upstream so far).
- **Interpretability:** high.
- **Caveat:** selecting `es_MX` must be justified on non-CALLHOME grounds; it must
  **not** be chosen because it is believed to match CALLHOME's variety.

## `es_US` Assessment
- **Assumption encoded:** US-Spanish as the reference lexicon.
- **Coverage:** medium.
- **Potential boundary concern:** because `es_US` represents a Spanish variety
  used in sustained contact with English, it raises a research question about
  how borrowings and English-adjacent forms are represented. This policy has not
  inspected the lexicon entries or cited comparative lexical evidence, so it
  does not assign `es_US` a higher false-positive risk.
- **False-positive risk:** TBD / NOT YET ESTABLISHED.
- **False-negative risk:** moderate for non-US varieties.
- **Regional bias:** high (US Spanish).
- **Reproducibility:** high — single pinnable pair (encoding to verify).
- **Interpretability:** the boundary concern above is a research question to
  resolve with non-CALLHOME evidence, not a basis for penalizing the variant here.
- **Assessment:** neither preferred nor rejected without separate, non-CALLHOME
  evidence about its construction and lexical scope.

## Pan-Regional Union Assessment
Union of multiple (up to all 23) regional lexica.

- **Coverage:** high; **false-negative risk:** lower in principle; unmeasured.
- **False-positive risk:** higher in principle than a single-variant resource
  because the accepted Spanish surface expands. The magnitude is not established
  and must not be estimated using CALLHOME.
- **Regional bias:** low.
- **Reproducibility:** moderate — every contributing `.dic`/`.aff` must be pinned
  individually, and the exact union construction procedure documented.
- **Licensing/provenance/notice/manifest complexity:** high — a union is a
  **derived resource**; it inherits and must preserve notices from every source,
  and needs a derived-resource policy and manifest before it could ever be used.
- **Interpretability:** low — "validated against a 23-way union" is hard to
  interpret and weakens cross-condition comparability.
- **Status:** a union must remain `NO / NOT APPROVED` unless separately approved.
  **Do not create a union.**

## Pan-Regional Intersection Assessment
Intersection / common-core of multiple regional lexica.

- **Coverage:** low (shared core only); **false-negative risk:** higher in
  principle; unmeasured.
- **False-positive risk:** lower in principle; unmeasured — restriction to the
  shared core should reduce acceptance opportunities, but no empirical risk rate
  has been established (and none may be estimated using CALLHOME).
- **Regional bias:** low for shared vocabulary (but excludes valid everyday
  regional forms, which is itself a form of bias-by-omission).
- **Reproducibility:** moderate–high, **but** requires defining exact
  normalization and set-construction procedures (which files, what normalization,
  how ties/accents are handled) before the core is reproducible.
- **Derived-resource complexity:** high — an intersection is a **derived
  resource** needing a derived-resource policy, manifest, and notice treatment.
- **Interpretability:** moderate — very conservative, but "core Spanish" excludes
  much valid everyday language, so a large `not_validated` share is expected.
- **Status:** must remain `NO / NOT APPROVED` unless separately approved.
  **Do not create an intersection.**

## Common-Core Plus Supplements Assessment
A conservative **shared core** performs validation; **regional supplements** are
handled separately or remain review-only.

- **Idea:** admit on the conservative core (low false-positive risk); route
  core-miss-but-plausibly-regional rows to `needs_review` rather than admitting
  them — preserving conservative admission while avoiding *silent* regional bias
  (the regional gap is made explicit as review, not hidden as validation).
- **False-positive risk:** low (admission rides the conservative core).
- **False-negative risk:** moderate (regional forms → review, not admission).
- **Regional bias:** lower than a single national variant, and **explicit** rather
  than silent.
- **Derived-resource complexity:** high — the core is a **derived resource** and
  needs a derived-resource design policy, exact set-construction, manifest, and
  notice treatment; supplements need their own handling.
- **Interpretability:** moderate–high — clean separation of "validated core" vs.
  "regional-review" is legible and defensible.
- **Status:** conceptually attractive but heavier to build; the derived core and
  any supplements remain `NO / NOT APPROVED`. **Do not implement or generate it.**

## Comparative Decision Matrix
Qualitative labels (no numerical estimates are given, since numbers would require
CALLHOME-derived measurement, which is forbidden):

| Strategy | Coverage | False-positive risk | False-negative risk | Regional bias | Reproducibility | Derived-resource complexity | Interpretability |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `es_ES` | medium | low–moderate | moderate | high (peninsular) | high | none | high |
| `es_MX` | medium | low–moderate | moderate | high (Mexican) | high | none | high |
| `es_US` | medium | TBD / not established | moderate | high (US) | high | none | high |
| all-variant union | high | higher in principle; unmeasured | lower in principle; unmeasured | low | moderate | **high** | low |
| all-variant intersection | low | lower in principle; unmeasured | higher in principle; unmeasured | low (by omission) | moderate–high | **high** | moderate |
| common-core + supplements | medium | low | moderate | low, **explicit** | moderate | **high** | moderate–high |
| defer decision | n/a (no active gate) | n/a | n/a | n/a | n/a | none | high (decision kept explicit) |

Label meanings: **Coverage** = breadth of forms accepted as Spanish; **FP risk** =
chance of admitting mixed/English-adjacent/ambiguous rows (the dangerous error);
**FN risk** = chance of leaving genuinely-clean rows `not_validated` (the safe
error); **Regional bias** = degree to which admission correlates with variety;
**Reproducibility** = ease of pinning and re-deriving the exact resource;
**Derived-resource complexity** = whether a new derived artifact (with its own
manifest/notice/approval burden) must be constructed; **Interpretability** = how
legibly "validated" can be described in the write-up.

## False-Positive and False-Negative Tradeoff
The gate's guiding asymmetry: **a false positive is worse than a false negative.**
Admitting a mixed or ambiguous row into `SpanishMono`/`MonoCont` contaminates the
very contrast (`CsCont` vs `MonoCont`) the study depends on; leaving a clean row
`not_validated` merely shrinks the admitted set. This asymmetry:

- **favors** conservative strategies (a single curated variant, an intersection,
  or a common-core) over a broad union, in principle;
- makes high false-negative rates *tolerable*, so "narrowness" is not disqualifying;
- means a union's lower-in-principle false-negative rate does **not** obviously
  compensate for its higher-in-principle false-positive risk — and neither
  magnitude has been established (and none may be estimated using CALLHOME).

## Regional Bias and Experimental Interpretability
Any single national variant imposes a regional lens on "Spanish monolingual,"
which can make **which rows are admitted correlate with variety**. Because the
research contrast is across conditions (`CsCont` vs `MonoCont`, anchored by
`SpanishMono`), a variety-correlated admission filter could subtly shift the
Spanish side of `MonoCont`/`SpanishMono` in ways that are hard to disentangle from
the code-switching effect. Two mitigations, both **policy-level, not operational**:

- prefer strategies whose regional bias is **explicit** (common-core + review) over
  silent single-variant bias;
- if a single variant is used, **document the bias** and treat early runs as
  **diagnostic-only** (no clean promotion) so the bias of an **already-selected**
  variant can be assessed in aggregate before it can affect any dataset — such runs
  evaluate an already-approved choice and must **not** be used to compare or pick
  variants.

None of this may be assessed using CALLHOME-derived lexical evidence.

## Licensing, Provenance, and Reproducibility
- **Single national variant:** simplest — one `.dic`/`.aff` pair to pin; inherits
  the RLA-ES/LibreOffice triple disjunctive license (GPLv3-or-later /
  LGPLv3-or-later / MPL 1.1-or-later; thesaurus separately LGPLv2.1) and its
  notices; **no derived resource** created.
- **Union / intersection / common-core:** each is a **derived resource** requiring
  a separate derived-resource design policy, exact construction procedure, a
  manifest pinning *every* contributing file, and preservation of notices from all
  contributors — a materially larger provenance and approval burden.
- **Pinning:** the LibreOffice package is a mutable-branch snapshot and its exact
  RLA-ES-version correspondence is still `TBD / NOT YET VERIFIED`
  (see `docs/callhome_lexicon_exact_resource_metadata.md`); whichever strategy is
  chosen, the exact contributing file(s) must be pinned to an immutable commit
  before any use.

## Recommended Policy
This is a **policy recommendation only**; it grants **no** operational approval.

1. **Defer the binding locale selection** to a dedicated research-policy decision
   PR. No option is yet justified strongly enough — on non-CALLHOME grounds — to
   bind the gate, and the meaning of "Spanish monolingual" is a research choice
   that should be made deliberately, not defaulted.
2. **Prefer a single pinned upstream variant** over a union / intersection /
   common-core for the first approved implementation, because a single variant is
   **simpler, more reproducible, and does not create a derived resource** (with its
   attendant construction, manifest, and multi-source notice burden).
3. **Do not yet prefer `es_ES`, `es_MX`, or `es_US`.** No variant has been shown
   superior on coverage, linguistic neutrality, licensing, or research fitness; the
   only variant-specific fact established so far is the narrow `es_ES.aff` UTF-8
   verification advantage, which does not confer research fitness.
4. **Select among variants only through separate, independently established,
   non-CALLHOME evidence** (authoritative linguistic / corpus / lexicon-construction
   sources), never from CALLHOME content.
5. **CALLHOME dry-run output may evaluate an already-selected policy but may not
   select or revise it.** A future aggregate dry run may assess the consequences of
   an already independently selected and approved locale. CALLHOME-derived aggregate
   results must not be used to compare candidate locales or decide which locale to
   select.

This recommendation deliberately distinguishes:

- **policy recommendation** — *this document* (DOCUMENTED);
- **locale-selection approval** — `NO / NOT APPROVED`;
- **local-placement approval** — `NO / NOT APPROVED`;
- **loader-use approval** — `NO / NOT APPROVED`;
- **aggregate-dry-run approval** — `NO / NOT APPROVED`;
- **clean-promotion approval** — `NO / NOT APPROVED`.

If, on review, even the general single-variant preference (point 2) is judged
premature, **deferral stands** and nothing is selected.

## Approval State
| Gate                            | Status            |
| ------------------------------- | ----------------- |
| locale policy documented        | DOCUMENTED        |
| Spanish locale selected         | NO / NOT APPROVED |
| union/intersection construction | NO / NOT APPROVED |
| local placement                 | NO / NOT APPROVED |
| loader use                      | NO / NOT APPROVED |
| aggregate dry run               | NO / NOT APPROVED |
| clean promotion                 | NO / NOT APPROVED |
| condition JSONL                 | NO / NOT APPROVED |
| training                        | NO / NOT APPROVED |

## Failure and Stop Conditions
Work must **stop** if:

- CALLHOME-derived evidence is used
- a locale is selected because it **maximizes validation yield** on CALLHOME
- a locale is selected because it **minimizes unknown tokens** on CALLHOME
- **Spanish candidate locales are compared using CALLHOME aggregate yields**
- **a locale is chosen based on CALLHOME validation rates**
- **the locale is changed after observing CALLHOME dry-run performance**
- a union or intersection is generated
- resource files are downloaded or saved locally
- local placement occurs
- hashes are computed
- loader use is introduced
- validator use is introduced
- dry-run wiring is introduced
- clean promotion is proposed
- condition JSONL or training is proposed
- CALLHOME could receive generic `CsCont` or switching-evidence candidacy, or
  future filler could be sampled outside `MonoCont-Spanish`

## Reviewer Checklist
- [ ] the decision criteria are independent of CALLHOME content
- [ ] CALLHOME dry-run results are not used to compare or select locales (only to evaluate an already-approved policy)
- [ ] no variant (`es_ES`/`es_MX`/`es_US`) is preferred in this policy
- [ ] false positives are treated as more dangerous than false negatives
- [ ] regional bias is made explicit
- [ ] no locale is silently chosen
- [ ] union/intersection complexity is documented (derived-resource burden)
- [ ] no derived resource is created
- [ ] no resource files are added
- [ ] all operational approvals remain `NO / NOT APPROVED`
- [ ] source-boundary rules remain intact (CALLHOME never shapes the lexicon;
      never receives generic `CsCont` or switching-evidence candidacy; future
      Spanish filler is a subset of `MonoCont-Spanish`)
- [ ] real pipeline behavior is unchanged

## Next Approved Step
Depending on review of the recommendation:

- a **dedicated locale-selection decision PR** (ratifying deferral, or an
  explicitly-justified single variant on non-CALLHOME grounds); and/or
- a **derived-resource design policy** first, **if** a union / intersection /
  common-core is ever preferred; and/or
- a **narrow single-variant placement decision** (using the placement-approval
  template) once a variant is justified and pinned; and/or
- **further external research** on Spanish variety coverage from authoritative
  linguistic/corpus sources (not CALLHOME transcripts).

Any future aggregate dry run **evaluates an already-approved locale; it does not
select or revise one**, and CALLHOME-derived results must not be used to compare
candidate locales. **No files are placed automatically** after this branch.

## Final Gate Status
- **The locale strategies are documented.**
- **The research tradeoffs are explicit.**
- **No Spanish locale is operationally selected** unless separately approved.
- **No resource is placed or loaded.**
- **No real validation occurs.**
- **All CALLHOME rows remain blocked** (`not_validated`; `clean` stays zero).
- **The gate remains closed** until each later approval is separately granted.
