# CALLHOME Lexicon License Verification

## Status
- **Docs-only verification note.** No code changes, no downloads, no lexicon
  files added, no parser run on real files, no aggregate outputs committed.
- No transcript excerpts, tokens, header values, participant names, speaker IDs,
  or filenames appear here.
- No condition JSONL, no tokenization, no training.
- **No license is verified in this PR.** No authoritative license source is
  present in the repo/context, and the web was not browsed, so both shortlisted
  candidates are marked **needs external verification**.
- **No resource is adopted.** This note only records what must be verified.
- Permission state: **Decision B** (see `docs/callhome_ground_rules.md`).

## Purpose
The candidate survey (`docs/callhome_lexicon_resource_candidates.md`) recommended
shortlisting **one English and one Spanish plain-wordlist** candidate for
**license verification only**:

- Hunspell/Aspell **`en_US`**
- Hunspell/Aspell **`es` / `es_ES`**

This note records the verification standard and the exact questions that must be
answered — from an authoritative source — before either could ever be used. Per
`docs/callhome_lexicon_resource_policy.md`, an unclear license means the resource
is **not usable yet**.

## Candidate resources under review
| Candidate | Language | Type | License status (this PR) | Adopted? |
|---|---|---|---|---|
| Hunspell/Aspell `en_US` | English | Plain spellcheck wordlist (family) | **needs external verification** | no |
| Hunspell/Aspell `es` / `es_ES` | Spanish | Plain spellcheck wordlist (family) | **needs external verification** | no |

**Important:** "Hunspell/Aspell dictionary" names a **resource family, not one
license.** Different `en_US` / `es` dictionary packages (different maintainers,
distributions, and versions) can ship under **different licenses** and terms.
Therefore the **generic name is insufficient**; we must identify the **exact
dictionary package and version** and verify that specific package's license from
an authoritative source.

## Verification standard
A candidate moves from **needs external verification** to a usable state only
when **all** of the following are recorded from an **authoritative source**
(official project page, package repository metadata, or the license file shipped
with the specific package):

1. Exact **package name / version**.
2. **Canonical source URL** (official/authoritative).
3. **License name / version** (from the package's own license file/metadata).
4. **Redistribution permission** (may the file, or derived wordlists, be
   redistributed / committed?).
5. **Academic / local use permission** (non-commercial local academic use).
6. **Required attribution / citation** string.
7. Whether **derived forms / wordlists** may be committed (vs. local-only).

No item may be assumed. If any is unresolved, the candidate stays **needs
external verification** and is **not** used.

## English candidate: Hunspell/Aspell `en_US`
- **License status (this PR): needs external verification.** No authoritative
  license evidence is present in the repo/context.
- The generic "`en_US` Hunspell/Aspell dictionary" spans multiple packages with
  potentially different licenses; the **exact package/version and its license
  file** must be identified before any claim is made.
- To resolve: record items 1–7 of the verification standard for the specific
  English package chosen.

## Spanish candidate: Hunspell/Aspell `es` / `es_ES`
- **License status (this PR): needs external verification.** No authoritative
  license evidence is present in the repo/context.
- The same family caveat applies: multiple Spanish (`es`, `es_ES`, and other
  regional) packages exist under potentially different terms; Spanish lexical
  resources may also have provenance restrictions that must be checked. The
  **exact package/version and its license file** must be identified.
- To resolve: record items 1–7 of the verification standard for the specific
  Spanish package chosen.

## License questions to resolve
For **each** shortlisted package (English and Spanish), from an authoritative
source:

- What is the **exact package name and version**?
- What is the **license name and version**, per the package's own license file
  or metadata (not inferred from the family name)?
- Does the license permit **academic / local, non-commercial** use?
- Are there **field-of-use or share-alike** obligations that would affect this
  repository?

## Redistribution questions
- Does the license permit **redistribution of the full dictionary file**?
- Does it permit **redistribution of a derived wordlist** (a subset/normalized
  form extracted from the dictionary)?
- If redistribution is **not allowed or unclear**, the **full lexicon file (and
  any committable derivative) must stay local / gitignored**, and only
  **aggregate, non-transcript diagnostics** may be committed.

## Citation/source questions
- What is the **required attribution / citation** string for the specific
  package?
- What is the **canonical source URL** (and version tag/commit) so the resource
  is **reproducible**?
- Is there an upstream **primary reference** (project, maintainer, or paper) that
  must be cited?
- These must be recorded in an in-repo **resource manifest** before use.

## Local-only storage implications
- **Local-only use may still be acceptable** — but **only if** the specific
  package's license permits local academic use.
- If redistribution is disallowed/unclear but local academic use is permitted,
  the file stays **local / gitignored**; only **aggregate diagnostics** derived
  from it may be committed (under Decision B).
- **No CALLHOME text may be uploaded to any external service** as part of
  verification or use (no external validators/APIs that would transmit transcript
  content).
- **No CALLHOME-derived token list may be used to shape the lexicon** — lexicons
  must never be built from or filtered by CALLHOME transcript text (circularity /
  leakage).

## Current recommendation
- **Continue with license verification only.** Both candidates remain **needs
  external verification**; **no resource is adopted, downloaded, or used** in this
  PR.
- **Do not download or use resources yet.**
- **Prefer resources with a clear license, a clear citation, and plain-text /
  local use** — plain spellcheck wordlists remain the best fit for the
  deterministic exact-match rule, but only once the **specific package's** terms
  are confirmed.
- If a shortlisted package's license cannot be verified as compatible, **drop it**
  and verify the next candidate.

## Out of scope
- Adopting, downloading, or loading any resource; adding lexicon files.
- Implementing a real lexicon loader or wiring the validator into the real-data
  script.
- Exact normalization thresholds and the borrowing/cognate resolution policy.
- **Condition JSONL construction** — remains out of scope.
- Sampling proportions, train/dev/test splitting, tokenizer choice.
- **Model training** — remains out of scope.
- Any Bangor / `CsCont` logic. **CALLHOME never feeds `CsCont`** (Bangor-sourced
  only); a future positive lexicon validation would only route clean English rows
  to `EnglishMono` + `MonoCont` and clean Spanish rows to `SpanishMono` +
  `MonoCont`.

## Next steps
1. For the chosen English and Spanish packages, gather items **1–7** of the
   verification standard from an **authoritative source**, and record them in an
   in-repo **resource manifest** (name, version, source URL, license, citation).
2. Decide **redistribution vs. local-only** storage per the confirmed license.
3. Only after license + citation are recorded, proceed to the resource policy's
   remaining gates (normalization tests → synthetic ambiguity tests → local-only
   dry run → aggregate-only review → explicit approval) before any clean
   promotion.

Until an authoritative license is recorded, both candidates stay **needs external
verification**, no real lexicon is loaded, every CALLHOME row stays
`not_validated`, and the `clean` count stays zero.
