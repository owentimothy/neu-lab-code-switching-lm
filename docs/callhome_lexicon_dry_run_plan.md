# CALLHOME Lexicon Aggregate Dry-Run Plan

## Status
- **Docs-only plan, not implementation.** No code changes.
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
The repo now has enough scaffolding (policy, storage guardrails, loader scaffold,
synthetic validator tests, and the local-use checklist) to **plan** a future
local-only aggregate dry run. This document defines **how to run it safely
later** — without exposing transcripts or changing training data — and the
approval gates that must clear afterward. It plans the run; it does not perform
it.

## What the dry run is
- A **future local-only** run that loads **approved** English and Spanish lexicon
  resources from **explicit local paths**.
- Applies source-language validation decisions to CALLHOME rows **only for
  aggregate diagnostic review**.
- Produces **aggregate counts only**.
- Used to **estimate** how many CALLHOME rows might become eligible for
  `EnglishMono`, `SpanishMono`, and `MonoCont` after review.
- It is a **diagnostic gate, not automatic admission.**

## What the dry run is not
- **Not** resource adoption.
- **Not** public redistribution of lexicons.
- **Not** a dataset build.
- **Not** clean promotion.
- **Not** condition JSONL.
- **Not** model training.
- **Not** Bangor or `CsCont` logic.
- **Not** transcript inspection.

## Preconditions
Before the dry run may be run:

- [ ] local-use checklist satisfied (`docs/callhome_lexicon_local_use_checklist.md`)
- [ ] resources approved for local use
- [ ] notices / license records complete
- [ ] local files placed only under `data/resources/local_lexicons/`
- [ ] that path remains gitignored
- [ ] loader tests pass
- [ ] validator tests pass
- [ ] storage guardrail tests pass
- [ ] existing parser / screening / projection / source-validation tests pass
- [ ] explicit human approval to run the aggregate dry run

## Inputs
- approved local **English** lexicon path
- approved local **Spanish** lexicon path
- CALLHOME local raw directories (already ignored)
- existing parser / screening rows
- existing screening decisions
- local-only loader output
- **no network inputs**

## Forbidden inputs
- external upload of CALLHOME text
- CALLHOME-derived token lists
- CALLHOME-derived frequency lists
- transcript snippets copied into config / docs
- unapproved lexicons
- nonlocal / remote paths
- network calls
- Bangor data for CALLHOME validation
- any resource lacking clear license / notice treatment

## Execution mode
- **local only**
- **explicit paths only**
- no downloads
- no network
- no committed resource files
- no committed derived wordlists
- no changed training inputs
- no condition JSONL creation
- no writing transcript-bearing output
- output location must be **ignored**, or **aggregate-only** if committed

## Validation behavior during dry run
- parser and screening behavior **unchanged**
- `excluded` rows stay `excluded`
- `parser_warning` rows **cannot** be rescued
- `empty_or_nonlexical` rows **cannot** be rescued
- `possible_code_switching` / `ambiguous_foreign_material` rows **cannot** be
  rescued
- `clean` can only become possible when **structural screening is eligible AND
  lexicon validation passes**
- English clean candidates may serve `EnglishMono`, `MonoCont-English`, and
  future `CsCont-English-Monolingual-Filler`, with filler selected only from
  `MonoCont-English`
- Spanish clean candidates may serve `SpanishMono`, `MonoCont-Spanish`, and
  future `CsCont-Spanish-Monolingual-Filler`, with filler selected only from
  `MonoCont-Spanish`
- **CALLHOME never receives generic `CsCont` or switching-evidence candidacy**
- the dry run may **compute candidate counts** but does **not** enable promotion

## Required aggregate outputs
Only aggregate counts, such as:

- total rows
- rows by source
- rows by screening outcome
- rows structurally eligible for validation
- rows blocked by screening reason
- validation status counts
- validation method counts
- validation reason counts
- potential `EnglishMono` candidate count
- potential `SpanishMono` candidate count
- potential `MonoCont` candidate count
- unknown-token row count *(if safely implemented)*
- ambiguous-token row count *(if safely implemented)*
- non-expected-language-token row count *(if safely implemented)*
- no-retained-token row count *(if safely implemented)*

## Forbidden outputs
- transcript text
- token strings from real data
- source lines
- per-row text
- per-row token lists
- speaker IDs
- speaker refs
- source file refs
- raw filenames
- participant names
- header values
- media IDs
- row-level examples
- sampled utterances
- derived vocabulary lists from CALLHOME
- any JSONL containing transcript-bearing content

## Expected review questions
- Are counts plausible by source?
- How many rows remain blocked by screening?
- How many rows are structurally eligible but **not** lexicon validated?
- How many rows validate by source?
- Are Spanish and English validation rates **suspiciously asymmetric**?
- Are unknown / ambiguous / non-expected aggregate counts high enough to indicate
  normalization or resource-coverage problems?
- Is there any sign that **code-switching rows** could be accidentally promoted?
- Is there any path by which **CALLHOME could receive generic `CsCont` candidacy,
  qualify as switching evidence, or supply filler outside the matching
  `MonoCont` material**?
- Does output remain **aggregate-only and non-transcript**?

## Failure / stop conditions
Stop if:

- any transcript text appears
- any real token strings appear
- any row-level data is emitted
- any raw filename or speaker identifier appears
- any resource license / notice ambiguity remains
- local files are not gitignored
- the loader requires network access
- a derived wordlist depends on CALLHOME tokens
- `possible_code_switching` rows are promoted
- `parser_warning` rows are promoted
- CALLHOME rows receive generic `CsCont` or switching-evidence candidacy, or
  future filler is sampled outside the matching `MonoCont` material
- clean promotion happens automatically
- condition JSONL is created
- training inputs change

## Approval gate after dry run
- aggregate counts reviewed
- false-positive risk assessed
- suspicious counts investigated **without transcript exposure**
- license / notice obligations rechecked
- explicit approval recorded in a future PR
- only after approval may a **separate clean-promotion PR** be considered

## Relationship to clean promotion
- the dry run does **not** promote clean rows
- the dry run **only estimates** possible clean candidates
- clean promotion requires a **separate PR and explicit approval**
- clean English rows may serve `EnglishMono`, `MonoCont-English`, and future
  `CsCont-English-Monolingual-Filler` selected only from `MonoCont-English`
- clean Spanish rows may serve `SpanishMono`, `MonoCont-Spanish`, and future
  `CsCont-Spanish-Monolingual-Filler` selected only from `MonoCont-Spanish`
- **CALLHOME never qualifies as genuine code-switched, mixed-language, or
  switching-quota evidence**

## Relationship to condition JSONL
- the dry run creates **no condition JSONL**
- the dry run changes **no training data**
- condition JSONL construction is a **later separate gate**

## Relationship to model training
- no model training
- no tokenizer changes
- no training configs
- no checkpoints
- no evaluation runs

## Next steps
- After this plan, a future branch **may** add an aggregate-only dry-run **script
  stub**, but only if it remains **disabled / unwired** and safe.
- Real local resource placement still requires **explicit approval**.

Until the preconditions and approvals are satisfied, no real lexicon is loaded,
the validator/loader stay unwired, every CALLHOME row stays `not_validated`, and
the `clean` count stays zero.
