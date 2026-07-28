# CALLHOME Lexicon Normalization Policy

## Status
- **Docs-only normalization policy, not implementation.** No code changes, no
  downloads, no lexicon files added, no upstream license files copied, no long
  license texts pasted.
- **No resource is adopted, downloaded, committed, loaded, or used.**
- **No clean promotion is enabled.** No condition JSONL construction. No model
  training.
- Defines the normalization rules that **future synthetic tests and loader code
  must follow**; **future code must apply the same normalization to utterance
  tokens and lexicon entries.**
- No transcript excerpts, tokens, header values, participant names, speaker IDs,
  or filenames appear here.
- Permission state: **Decision B** (see `docs/callhome_ground_rules.md`).

## Purpose
Before any real English/Spanish lexicon (`docs/callhome_lexicon_resource_manifest.md`)
can be used by the lexicon validator, the way tokens and lexicon entries are
normalized before matching must be fixed and documented — otherwise match results
are undefined and could silently over-accept. This note defines those rules and
the synthetic tests that must pin them, consistent with the conservative posture
of `docs/callhome_lexicon_resource_policy.md` and the existing synthetic
validator scaffold.

## Scope
- Applies to the two manifest candidates (English SCOWL/LibreOffice `en_US`;
  Spanish RLA-ES/LibreOffice) and any future lexicon used by the validator.
- Governs **normalization and matching rules only** — not resource adoption, not
  a loader, not wiring into the real-data script (the validator remains
  synthetic-only / caller-provided).
- Uses only existing repo context and source references already recorded in docs.

## Normalization principle
- **Normalize utterance tokens and lexicon entries identically before matching.**
  A match is meaningful only if both sides went through the exact same pipeline.
- **Preserve conservative behavior: uncertainty returns `not_validated`.**
- **Prefer false negatives over false positives** — it is better to leave a
  genuinely-clean row `not_validated` than to validate a mixed/ambiguous row.
- **No CALLHOME-derived token lists** may shape, filter, expand, or modify the
  lexicon **or these normalization rules**.

## Token normalization rules
Applied to each candidate token from an utterance's main tier (in memory only;
never printed/stored):

- **Unicode normalize consistently**, preferably **NFC**, applied identically on
  both sides.
- **Case-fold / lowercase consistently.**
- **Strip leading/trailing punctuation** (including inverted marks such as `¿`,
  `¡`).
- **Internal apostrophes / hyphens**: preserved **only if** an explicit,
  documented rule allows it; otherwise the treatment must be documented and
  tested (see English-specific handling). Default: do not silently alter internal
  characters without a documented rule.
- **Remove / ignore pure-punctuation tokens** (no retained lexical content).
- **Ignore CHAT residue / non-lexical markers** already treated as non-lexical by
  screening — e.g. `xxx`, `yyy`, `www`, `0`, `&`-forms, bracketed markers, and
  pause markers (consistent with the existing scaffold).
- **Do not use CALLHOME-derived token lists to tune these rules.**

## Lexicon-entry normalization rules
- Apply the **exact same** Unicode / case / punctuation rules to lexicon entries
  as to utterance tokens.
- **Do not modify source lexicons in place** — normalization builds a derived
  comparison form; the upstream `.dic` / `.aff` files are never edited.
- Any **derived normalized wordlist must stay local / gitignored** until its
  license/notice treatment is documented and **explicit approval** is given.
- **No derived wordlist is committed in this PR** (or until approved).

## English-specific handling
- **Contractions must be explicitly tested** (e.g. `don't`, `can't`, `I'm`) — the
  chosen treatment (kept as one token vs. affected by apostrophe rules) must be
  documented and pinned by tests.
- **Possessive / apostrophe-`s`** forms need a **documented choice** (e.g. whether
  `dog's` is treated as-is, stripped, or blocked).
- **Hyphenated compounds** need a **documented choice** (kept whole vs. split vs.
  blocked).
- **Do not assume SCOWL coverage is sufficient for all spoken forms** — spoken
  conversation contains reductions/variants that a spelling dictionary may not
  list; missing forms simply yield `not_validated` (the safe direction).

## Spanish-specific handling
- **Preserve Spanish diacritics / accents by default**; **do not fold accented
  and unaccented forms together** unless explicitly approved later.
  - *Why:* accents can distinguish distinct words/forms — e.g. `si` vs `sí`,
    `esta` vs `está`. Folding them would erase a real lexical distinction and
    risk false positives.
- **Handle inverted punctuation** by stripping leading/trailing punctuation —
  e.g. `¿qué?` → `qué`.
- **Clitics / enclitics** need **explicit handling**: do not split or accept them
  unless they are present after normalization **or** covered by a future
  documented rule.
- **Regional variant decision remains unresolved:** `es` vs `es_ES` vs other
  variants — to be decided before a real dry run.

## CHAT / transcript-residue handling
- Residue and non-lexical CHAT markers are **not evidence** for English or
  Spanish.
- They are **ignored or blocked** according to the existing screening / scaffold
  behavior (residue tokens, `&`-forms, bracketed/pause markers are non-lexical).
- **Parser warnings or uncertain structures continue to block clean promotion**
  (they route to `needs_review`, per the screening/validation combination), and
  are never rescued by lexicon matching.

## Proper names and named entities
- **Proper names do not count as evidence for either language by default.**
- A row containing **names plus otherwise validated expected-language tokens**
  needs a **future explicit policy** (e.g. treat names as neutral/skip vs. block);
  it is not resolved here.
- **Avoid using participant names or any CALLHOME-derived name lists** — no name
  material from the corpus may shape the lexicon or the rules.

## Borrowings, cognates, and ambiguous forms
- If a **normalized form appears in both** the English and Spanish lexicons, it is
  **ambiguous and blocks positive validation by default**.
- **Borrowings and cognates are not manually rescued at this stage.**
- The validator **prefers `not_validated`** over incorrectly validating a
  mixed/ambiguous row.

## Unknown-token policy
- **Unknown lexical tokens block positive validation by default** (a token in
  neither the expected lexicon nor recognized as residue).
- Unknowns may be **counted only in aggregate diagnostics** later — **never**
  listed as transcript tokens in committed output.

## Matching policy
After identical normalization, positive validation requires **all** of:

- **Every retained lexical token matches the expected-language lexicon**, and
- **No retained lexical token matches the other-language lexicon.**

Consequences:
- **Tokens in both lexicons block** positive validation (ambiguous).
- **Tokens only in the non-expected lexicon block** positive validation.
- **Empty / no-retained-token rows do not validate.**
- **Any uncertainty returns `not_validated`.**

This matches the existing scaffold's conservative exact-match semantics.

## Diagnostics policy
Future diagnostics may include **only aggregate counts**, for example:

- number of rows with **unknown** tokens,
- number of rows with **ambiguous** (both-lexicon) tokens,
- number of rows blocked by **non-expected-language** tokens,
- number of rows with **no retained lexical tokens**.

**Do not emit** token strings, source lines, speaker IDs, filenames, or any
per-row transcript-bearing data. All committed diagnostics remain aggregate and
non-transcript (Decision B).

## Required synthetic tests
Future implementation must add these **synthetic-only** tests before any real dry
run (fake lexicons / fake tokens only):

- **Unicode / case normalization** (NFC + lowercase, both sides).
- **Leading/trailing punctuation stripping.**
- **Spanish inverted punctuation** (e.g. `¿qué?` → `qué`).
- **Spanish accent preservation** — e.g. `si` vs `sí` remain **distinct**.
- **English contractions** (e.g. `don't`, `can't`, `I'm`).
- **Apostrophe / possessive handling** (documented choice).
- **Hyphen handling** (documented choice).
- **CHAT residue exclusion** (`xxx`, `0`, `&`-forms, brackets, pauses).
- **Empty / no-retained-token rows** do not validate.
- **Unknown token blocks validation.**
- **Ambiguous cross-lexicon token blocks validation.**
- **Non-expected-language token blocks validation.**
- **Expected-language-only tokens can validate** (synthetic lexicons).
- **Same normalization applied to lexicon entries and utterance tokens.**

## Out of scope
- Adopting, downloading, or loading any resource; adding lexicon or license files.
- Implementing the normalization/loader code or wiring the validator into the
  real-data script.
- Final decisions on internal apostrophe/hyphen treatment, clitic handling, the
  proper-name policy, and the Spanish regional variant (each needs its own
  documented rule + tests).
- Editing `.gitignore` or creating the resource path (future implementation PR).
- **Condition JSONL construction** — remains out of scope.
- Sampling proportions, train/dev/test splitting, tokenizer choice.
- **Model training** — remains out of scope.
- Any Bangor / `CsCont` construction logic. This normalization policy creates no
  condition output. A future positive lexicon validation may permit clean rows
  to serve their language-matched baseline, matching `MonoCont` role, and future
  language-matched `CsCont` monolingual-filler role selected only from that
  `MonoCont` material. CALLHOME never qualifies as genuine code-switched,
  mixed-language, or switching-quota evidence.

## Next steps
1. Resolve the open documented choices (internal apostrophe/hyphen treatment,
   possessives, Spanish clitics, proper-name policy, regional variant) — each as
   an explicit rule with a synthetic test.
2. Add the **synthetic normalization + ambiguity tests** listed above (no real
   resource needed to prove the rules).
3. Only then proceed to a **local-only loader scaffold** and **local-only dry
   run** emitting **aggregate-only** diagnostics for review, before any **explicit
   approval** to enable clean promotion.

Guardrails that hold regardless: **CALLHOME text must never be uploaded
externally**; **CALLHOME-derived token lists must never shape the lexicon or
normalization rules**; **CALLHOME never receives generic `CsCont` or
switching-evidence candidacy**; and until the gates clear, no real lexicon is
loaded, every CALLHOME row stays `not_validated`, and the `clean` count stays
zero.
