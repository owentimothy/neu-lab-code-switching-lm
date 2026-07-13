# CALLHOME English SCOWL / ESDB Proper-Name Policy

## Status
```text
Proper-name policy for continued resource governance:
YES / APPROVED

Complete deterministic proper-name exclusion:
NO / NOT AVAILABLE

ESDB selected:
NO

LibreOffice selection replaced:
NO

Operational resource use:
NO / NOT APPROVED

Real CALLHOME validation:
NO / NOT APPROVED
```

This is a **repository governance record, not legal advice.** It resolves **one**
bounded question: whether the residual proper-name coverage in the proposed direct
SCOWL / ESDB English candidate is acceptable for **continued resource governance**
under the existing conservative validation architecture. It is **not** approval to
download, check out, build, generate, place, hash, load, or use ESDB, and it does
**not** select ESDB or replace the LibreOffice candidate.

- **No CALLHOME transcript content or CALLHOME-derived evidence was inspected or
  used** to make this decision.
- **No SCOWL/ESDB resource was downloaded, checked out, built, generated, saved, or
  hashed.**
- **The real pipeline remains unchanged** (`default_source_validation` only;
  validator/loader not wired into `scripts/summarize_callhome_projection_local.py`).
  Every real CALLHOME row stays `not_validated`; `clean` stays zero.
- **All operational approvals remain `NO / NOT APPROVED`.**

## Approved Policy
```text
Policy A — residual SCOWL proper-name material is acceptable
for continued English resource governance under the existing
conservative validation architecture.
```

Policy A is approved for **continued governance only**. It does not enable any
operational step. The alternative position (Policy B — keep ESDB blocked until a
stronger proper-name exclusion policy exists) is recorded in
`docs/callhome_english_scowl_candidate_evidence.md`; this record adopts Policy A for
governance while keeping every operational gate closed.

## Problem Being Addressed
The SCOWL/ESDB candidate evidence
(`docs/callhome_english_scowl_candidate_evidence.md`) established that **complete
deterministic proper-name exclusion cannot be guaranteed at the proposed release**:
the upstream POS-CLASS tagging is inconsistent and "can't be used to reliably filter
out proper nouns" (name-related classes include `person`, `surname`, `place`,
`name`). The proposed conservative extraction already excludes abbreviations,
non-words (prefixes/suffixes/Roman numerals), and word-parts, but **some proper-name
material will remain**. This record decides whether that residual is acceptable for
continued governance, grounded in what the repository's validation architecture
actually enforces.

## Validation Architecture (repository-grounded)
Read from `src/cslm/data/callhome_lexicon_validation.py` (the validator scaffold —
note the actual filename; there is no `callhome_lexicon_validator.py`),
`src/cslm/data/callhome_source_validation.py` (the decision type, the conservative
default, and screening+validation combination), `src/cslm/data/callhome_lexicon_loader.py`
(the raw-entry loader), and the governing tests
`tests/test_callhome_lexicon_validation.py` and
`tests/test_callhome_source_validation.py`:

- **Conservative default:** every real CALLHOME row is `not_validated` by
  `default_source_validation(...)`; the validator is **not** imported or called by
  the local summary script (`test_validator_not_imported_or_called_by_local_script`).
- **All-token expected-language membership:** a positive
  (`lexicon_exact_match` / `lexicon_expected_only`) requires **at least one** lexical
  token and **every** lexical token present in the expected-language lexicon
  (`test_all_expected_language_tokens_validate`,
  `test_expected_language_only_tokens_validate`).
- **Other-language overlap blocks:** any lexical token present in a non-expected
  lexicon blocks validation, **including** a token present in **both** lexicons
  (ambiguous) (`test_token_in_other_language_lexicon_is_not_validated`,
  `test_ambiguous_token_in_both_lexicons_is_not_validated`,
  `test_non_expected_language_token_blocks_validation`).
- **Unknown tokens block:** any lexical token not in the expected lexicon blocks
  validation (`test_unknown_token_is_not_validated`,
  `test_unknown_token_blocks_validation`).
- **Residue / empty blocks:** rows with no retained lexical token do not validate
  (`test_residue_markers_are_not_lexical_evidence_only_residue_blocks`,
  `test_empty_or_no_retained_token_row_does_not_validate`).
- **Clean gate:** `combine_screening_and_validation(...)` yields `clean` **only** if
  a row is structurally eligible **and** source-validated; `excluded` stays
  `excluded`; otherwise `needs_review`.
- **Content-free decisions:** decisions carry only booleans, a language label, and
  fixed-vocabulary labels — never transcript text, tokens, names, or notes
  (`test_decision_is_content_free`, `test_no_transcript_token_strings_in_returned_decision`).

## Reasoning — Why the Proper-Name Risk Is Bounded
1. **Known source identity.** CALLHOME source language (`eng`/`spa`) is already
   known from the corpus; the validator **confirms source-language consistency**,
   not language discovery from arbitrary text. A residual English proper name in the
   English lexicon does not change the row's known source.
2. **All-token requirement.** Validation requires **every** lexical token to match
   the expected-language lexicon; a single unmatched token blocks the row.
3. **Cross-language overlap blocks.** Any lexical token that also appears in the
   other-language lexicon blocks validation; a token represented in both lexicons
   cannot support a positive validation decision.
4. **Unknown tokens block.** Any lexical token unknown to the expected lexicon
   blocks validation.
5. **Detected ambiguous / mixed material stays blocked.** Material already
   flagged upstream by screening reason codes such as `possible_code_switching` or
   `ambiguous_foreign_material` cannot be rescued by lexical validation and remains
   `needs_review`. This does not establish that screening detects every mixed or
   code-switched row.
6. **Monolingual restriction.** CALLHOME English and Spanish remain restricted to
   the **monolingual** conditions (`EnglishMono` / `SpanishMono`) and the matching
   monolingual portion of `MonoCont`.
7. **CALLHOME never feeds `CsCont`.**
8. **Bangor Miami remains the only final source for `CsCont`.**

Consequently, **residual proper names do not generally allow a foreign-language
utterance to pass** unless **all** remaining lexical material *also* satisfies the
expected-language-only criteria (present in the expected lexicon and absent from the
other). A proper name embedded in material whose remaining tokens satisfy the
expected-language-only criteria does not, by itself, provide evidence of foreign
material. Source metadata and lexical validation jointly support a conservative
source-consistency decision, but they do not prove that the row is linguistically
monolingual. The remaining risk is described below.

**Proper-name risk is not claimed to be zero.**

## Residual-Risk Section
The following residual risks remain and are explicitly acknowledged:

- **Single-token or name-dominated utterances** — a very short row consisting mostly
  or entirely of a proper name carries little independent language evidence.
- **A proper name appearing in only one language lexicon** — an asymmetrically
  listed name would not be blocked by cross-language overlap.
- **Inconsistent upstream proper-name and capitalization tagging** — upstream POS
  tagging cannot reliably identify all proper nouns, so exclusion is incomplete.
- **English/Spanish lexicon asymmetry** — differing coverage or construction of the
  two lexicons could make some names/tokens matchable on one side only.
- **Names that overlap ordinary lexical items** — a token that is both a name and a
  common word cannot be distinguished by surface form alone.
- **Normalization effects on capitalization** — case-folding (lowercasing) during
  normalization removes capitalization as a proper-name cue.
- **Short utterances carrying less independent language evidence** — fewer tokens
  mean fewer independent blocking opportunities.
- **Undetected mixed-language material** — a mixed row could evade the screening and
  overlap gates if every retained surface token appears only in the expected-language
  lexicon; source identity and lexical membership do not independently prove
  monolinguality.

These residual risks are **acceptable for continued governance** but **require later
aggregate-only diagnostics before any real-validation approval**. This record does
**not** approve that dry run.

## Future Aggregate-Only Diagnostic Requirements
A later, separately approved dry run should report **only** non-content-bearing
aggregates, for example:

- counts by lexical-token length;
- counts of one-token rows;
- counts blocked by cross-language overlap;
- counts blocked by unknown tokens;
- counts passing expected-language-only membership;
- counts by source and validation outcome;
- counts of short rows accepted or blocked;
- reason-code distributions.

It must **not** print any of:

- transcript text;
- tokens;
- names;
- speaker IDs;
- filenames;
- raw row identifiers;
- participant metadata;
- transcript-bearing examples.

**No CALLHOME content may be inspected to make this policy decision**, and none was.

## Decision Boundary

### Approved in this branch
```text
Residual proper-name coverage is acceptable for continued
SCOWL/ESDB resource governance.
```

### Not approved in this branch
```text
ESDB resource selection
LibreOffice replacement
license-and-notice approval
download
source checkout
build
wordlist extraction
local placement
hash computation
loader execution
aggregate dry run
real CALLHOME validation
clean promotion
condition construction
tokenization
model training
```

## Evidence Matrix
| Topic | Repository evidence | What it establishes | Remaining risk | Confidence |
| ----- | ------------------- | ------------------- | -------------- | ---------- |
| All-token expected-language membership | `callhome_lexicon_validation.py`; `test_all_expected_language_tokens_validate`, `test_expected_language_only_tokens_validate` | A positive requires ≥1 lexical token and every token in the expected lexicon | a name-only row can still be all-expected-language | DIRECT |
| Other-language overlap blocking | `callhome_lexicon_validation.py`; `test_token_in_other_language_lexicon_is_not_validated`, `test_ambiguous_token_in_both_lexicons_is_not_validated` | Any token in another (or both) lexicon blocks validation | a name listed in only one lexicon isn't blocked by overlap | DIRECT |
| Unknown-token blocking | `callhome_lexicon_validation.py`; `test_unknown_token_is_not_validated`, `test_unknown_token_blocks_validation` | Any token unknown to the expected lexicon blocks validation | short rows offer fewer blocking chances | DIRECT |
| Source routing | `callhome_source_validation.py` `combine_screening_and_validation`; CLAUDE.md sourcing invariants | CALLHOME → monolingual conditions only; clean only if eligible **and** validated; never `CsCont` | — | DIRECT |
| Proper-name exclusion limitation | `docs/callhome_english_scowl_candidate_evidence.md` (upstream POS-CLASS warning) | Complete deterministic proper-name exclusion is not available at the proposed release | residual names remain in the lexicon | DIRECT |
| Short-utterance risk | validator all-token logic; `test_residue_...`, `test_empty_or_no_retained_token_row_does_not_validate` | Rows with no retained lexical token never validate; short rows carry less evidence | a short name-dominated row could satisfy source-consistency validation despite limited independent language evidence | STRONG |
| Privacy-safe aggregate diagnostics | `callhome_source_validation_diagnostics.py`; content-free decision tests | Decisions/diagnostics are content-free (counts, labels only) | aggregate design must avoid any content leakage | DIRECT |

## Decision Matrix
| Decision or gate                                          | Status            |
| --------------------------------------------------------- | ----------------- |
| Proper-name policy reviewed                               | YES / RECORDED    |
| Residual proper names acceptable for continued governance | YES / APPROVED    |
| Complete proper-name exclusion available                  | NO                |
| Aggregate diagnostic requirements defined                 | YES / RECORDED    |
| ESDB selected                                             | NO                |
| LibreOffice replaced                                      | NO                |
| License-and-notice pathway approved                       | NO / NOT APPROVED |
| Download approved                                         | NO / NOT APPROVED |
| Build or extraction approved                              | NO / NOT APPROVED |
| Local placement approved                                  | NO / NOT APPROVED |
| Hash computation approved                                 | NO / NOT APPROVED |
| Loader use approved                                       | NO / NOT APPROVED |
| Aggregate dry run approved                                | NO / NOT APPROVED |
| Real CALLHOME validation approved                         | NO / NOT APPROVED |
| Clean promotion approved                                  | NO / NOT APPROVED |
| Condition construction approved                           | NO / NOT APPROVED |
| Tokenization approved                                     | NO / NOT APPROVED |
| Model training approved                                   | NO / NOT APPROVED |

## Current Pipeline State
```text
total CALLHOME rows: 88404
validated: 0
not_validated: 88404
lexicon_exact_match: 0
clean: 0
EnglishMono candidates: 0
SpanishMono candidates: 0
MonoCont candidates: 0
blocked from all conditions: 88404
```

## Safety and Routing State
```text
CALLHOME English
→ potentially EnglishMono
→ potentially the English portion of MonoCont
→ never CsCont

CALLHOME Spanish
→ potentially SpanishMono
→ potentially the Spanish portion of MonoCont
→ never CsCont

Bangor Miami
→ CsCont only
```

## Next Step
With the proper-name policy resolved (Policy A) for continued governance, the
remaining SCOWL/ESDB material questions in
`docs/callhome_english_scowl_candidate_evidence.md` (Model 1 vs. LibreOffice
replacement; exact Python/SQLite pin; byte-stable reproduction; filename/storage
metadata; notice-bundle and size-60/variant-1 approval) remain open. A future
branch would address those; a still-later, separately approved **aggregate-only dry
run** (never inspecting CALLHOME content) would exercise the residual-risk
diagnostics above **before** any real-validation approval. Until then, ESDB is
**not** selected, the LibreOffice resource **remains selected pending review**, and
every operational gate remains **closed**.
