# CALLHOME Lexicon Resource Policy

## Status
- **Docs-only policy note.** No code changes, no real lexicon files added, no
  downloads, no parser run on real files, no aggregate outputs committed.
- No transcript excerpts, tokens, header values, participant names, speaker IDs,
  or filenames appear here.
- No condition JSONL, no tokenization, no training.
- Defines what English/Spanish lexical resources a *future* real lexicon
  validator may use, and how they must be licensed, stored, normalized, and
  reviewed. No resource is adopted here.
- Permission state: **Decision B** (see `docs/callhome_ground_rules.md`) —
  aggregate-only, non-transcript summaries may be committed with citation/license
  notes; transcript-bearing outputs remain blocked.

## Purpose
The lexicon-validation scaffold (`src/cslm/data/callhome_lexicon_validation.py`)
can, in principle, produce a positive source-language validation by checking an
utterance's tokens against English/Spanish lexicons. Today it uses **synthetic,
caller-provided** lexicons only. Before any *real* lexical resource is used, we
need an explicit policy for which resources are acceptable, how they are
licensed and stored, how tokens are normalized, and which review gates must
clear. This note is that contract; it complements
`docs/callhome_source_validation_method_policy.md` (what validation must prove)
and `docs/callhome_clean_admission_policy.md` (the clean gate).

## Current implementation state
- The lexicon validator is **synthetic-only and caller-provided**: the caller
  passes `lexicons_by_language`; the module **loads no lexicon files and
  hardcodes no real vocabulary**.
- **No real lexical resources are currently committed or loaded**, and the
  validator is **not** wired into the real-data summary script.
- Real CALLHOME behavior is therefore unchanged: zero `clean`, zero condition
  candidates, zero `validated`, zero `lexicon_exact_match`. (Specific run counts
  are not reproduced here, per Decision B; only the *type* of result is stated.)

## Why resource policy is needed
A lexicon turns "has words" into "confidently monolingual in the expected
language" — but only if the lexicon is trustworthy. The two failure modes this
policy guards against are (1) using a resource whose **licensing** or provenance
is unclear, and (2) building a lexicon that is **contaminated by CALLHOME
transcript text**, which would make validation circular and could leak corpus
content. This policy also fixes the interpretive guardrails so no future
resource silently weakens them:

- **Source directory `eng`/`spa` is not validation.** It states the *expected*
  language, never the verified language.
- **Lexical content alone is not validation** unless every lexical token is
  checked against an **approved** resource under the rules below.

## Acceptable resource types
Subject to the licensing and review requirements below, acceptable resources
*could* include:

- **Documented open English wordlists** (transparent origin, citable).
- **Documented open Spanish wordlists** (transparent origin, citable).
- **Reviewed morphological lexicons** (e.g. lemma/form tables) whose coverage and
  construction are documented.
- **Locally installed language-ID / lexical resources**, if licensing allows
  local, non-commercial academic use and no data leaves the machine.

Each must be transparent, citable, and reproducible.

## Resource licensing requirements
- Lexicons must have **licensing compatible with academic / local, non-commercial
  use** (consistent with the corpus terms in `docs/callhome_ground_rules.md`).
- The **license and citation must be documented before use** — recorded in-repo
  (e.g. a resource manifest) with the exact license and a reproducible source
  reference.
- If a resource's license is unclear or incompatible, it is **not** used.

## Resource storage policy
- If a full lexicon file **cannot be committed** (license or size), it must stay
  **local / gitignored**; only **aggregate diagnostics** derived from it may be
  committed (under Decision B).
- **No CALLHOME-derived tokens may be written into lexicon files.** Lexicons must
  never be **built from CALLHOME transcript text** (that would be circular and
  could leak corpus content).
- Committed artifacts about a resource are limited to its **manifest**
  (name, version, license, citation) and **aggregate diagnostics** — never
  transcript-bearing content.

## Normalization policy
Normalization maps utterance tokens and lexicon entries onto a common form; it
materially affects matches, so the exact rules **must be documented before use**.
At minimum, decide and record how each of these is handled:

- **Lowercasing** (case folding).
- **Punctuation stripping** (leading/trailing, internal).
- **Unicode / accent handling** (NFC/NFD; whether accents are preserved or
  folded — noting Spanish accents are meaningful).
- **Contractions / clitics** (English `don't`; Spanish enclitics such as
  attached object pronouns).
- **CHAT residue markers** (e.g. `xxx`, `0`, `&`-forms) — excluded as non-lexical.
- **Proper nouns / names** — how names are treated (typically language-neutral,
  not evidence for either language).
- **Borrowings / cognates** — how established borrowings and cross-language
  cognates are handled, given they blur the monolinguality signal.

Normalization must be applied **identically** to utterance tokens and lexicon
entries, and documented so results are reproducible.

## Coverage and ambiguity policy
The validator must be **conservative and prefer false negatives over false
positives**:

- A token appearing in **both** the English and Spanish lexicons (ambiguous)
  **blocks positive validation by default**.
- An **unknown** token (in neither the expected lexicon nor recognized as
  residue) **blocks positive validation by default**.
- A token in the **non-expected** language's lexicon blocks positive validation.
- Positive validation requires **every** lexical token to be in the
  expected-language lexicon and none in the other — partial coverage is not a
  positive.

Coverage gaps are expected and acceptable: they produce more `not_validated`
rows, which is the safe direction.

## Validation behavior
- A real lexicon validator must still return only a content-free
  `CallhomeSourceValidationDecision` (`is_validated`, `expected_language`,
  `validation_method` = `lexicon_exact_match`, `reason_codes` =
  `["lexicon_expected_only"]` for a positive; otherwise the default
  `not_validated`).
- Any uncertainty (ambiguous, unknown, no lexical token, other-language token)
  returns `not_validated`.
- Source directory and raw lexical presence never, on their own, yield a
  positive.

## Diagnostics requirements
Validation diagnostics must remain **aggregate-only and non-transcript**:

- `validated` vs `not_validated`,
- validation-method counts,
- reason-code counts,
- source-level counts, if that breakdown is later added,
- **optional** coverage / unknown / ambiguous counts — **only** if they are
  aggregate and non-transcript (counts of rows/tokens, never the tokens
  themselves).

No lexicon entry, transcript token, filename, speaker identifier, ref, or note
may appear in any committed diagnostic.

## Review gates
Before any **real** lexicon is used to admit CALLHOME rows to `clean`:

1. **Document the candidate resource and its license** (manifest + citation).
2. **Synthetic tests** for normalization and ambiguity behavior (no real
   resource needed to prove the rules).
3. **Local-only dry run** on the gitignored CALLHOME files, with any per-row
   output kept local/gitignored.
4. **Aggregate-only review** of the resulting counts (validated vs not,
   coverage, unknown, ambiguous — all aggregate).
5. **Explicit approval** before clean promotion is enabled.

Until gate 5 clears, real lexicon validation stays disabled and the CALLHOME
`clean` count stays zero.

## Disallowed practices
- **Scraped resources with unclear licensing.**
- **Resources derived from CALLHOME transcript text** (circular / leakage).
- **Resources that require uploading CALLHOME text externally** (any external
  API/service that would transmit transcript content).
- **Resources that cannot be cited or reproduced.**
- Committing full lexicon files whose license forbids redistribution.
- Inferring positive validation from source directory or bare lexical presence.

## Out of scope
- Selecting or adopting a specific lexical resource.
- Implementing a real lexicon loader or wiring the validator into the real-data
  script.
- Exact normalization thresholds and the borrowing/cognate resolution policy.
- **Condition JSONL construction** — remains out of scope.
- Sampling proportions, train/dev/test splitting, tokenizer choice.
- **Model training** — remains out of scope.
- Any Bangor / `CsCont` construction logic. This resource policy creates no
  condition output. A positive lexicon validation may permit clean rows to serve
  their language-matched baseline, matching `MonoCont` role, and future
  language-matched `CsCont` monolingual-filler role selected only from that
  `MonoCont` material. CALLHOME never qualifies as genuine code-switched,
  mixed-language, or switching-quota evidence.

## Future implementation sequence
When a real lexicon is eventually adopted (a **separate**, reviewed PR or PRs):

1. Choose a licensing-compatible, citable resource and record its **manifest +
   license + citation** in-repo; keep the full file local/gitignored if it
   cannot be committed.
2. Document the **normalization rules** and add **synthetic tests** for
   normalization and ambiguity behavior (gate 2).
3. Implement a local lexicon loader that never ingests CALLHOME text, and run a
   **local-only dry run** (gate 3) emitting **aggregate-only** diagnostics.
4. **Review the aggregate counts** (gate 4) and obtain **explicit approval**
   (gate 5) before enabling clean promotion.
5. Only then proceed — under the existing sourcing invariants (CALLHOME →
   language-matched baseline and `MonoCont` roles, plus future language-matched
   `CsCont` monolingual filler drawn only from the corresponding `MonoCont`
   material; Bangor → primary current genuine code-switched evidence) — toward
   condition-dataset construction, which remains out of scope here.

Until this sequence completes and is approved, no real lexicon is loaded, every
CALLHOME row stays `not_validated`, and the `clean` count stays zero.
