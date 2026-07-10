# CALLHOME Lexicon Resource Candidates (Survey)

## Status
- **Docs-only survey.** No code changes, no resource downloads, no lexicon files
  added, no parser run on real files, no aggregate outputs committed.
- No transcript excerpts, tokens, header values, participant names, speaker IDs,
  or filenames appear here.
- No condition JSONL, no tokenization, no training.
- **No resource is adopted in this PR.** This is a survey/checklist to decide
  what information we must gather before adopting any real lexicon.
- Licenses below are **not** treated as verified: every candidate's license and
  provenance is marked **needs verification** until confirmed from an official /
  clearly authoritative source. **Unclear license means not usable yet.**
- Permission state: **Decision B** (see `docs/callhome_ground_rules.md`).

## Purpose
The lexicon-validation scaffold (`src/cslm/data/callhome_lexicon_validation.py`)
is synthetic-only and caller-provided today; the real pipeline still uses
`default_source_validation` only (behavior remains zero `clean`, zero condition
candidates, zero `validated`, zero `lexicon_exact_match` — specific run counts
are not reproduced here, per Decision B). Before any real English/Spanish lexicon
is used, `docs/callhome_lexicon_resource_policy.md` requires a licensing,
storage, normalization, ambiguity, and review-gate contract. This note is the
**candidate survey** feeding that contract: it lists possible resources at a high
level, records what must be verified, and recommends a conservative next step. It
adopts nothing.

## Selection criteria
A candidate is only worth shortlisting if it can plausibly satisfy the resource
policy:

- **Licensing** compatible with academic / local, non-commercial use; verifiable
  from an authoritative source.
- **Citable and reproducible** (documented origin and version).
- **Local-only usable** without transmitting any CALLHOME text externally.
- **Not derived from CALLHOME** transcript text (no circularity / leakage).
- **Documentable normalization** (case, punctuation, accents, clitics, etc.).
- **Inspectable coverage** so ambiguity/unknown rates can be reviewed in
  aggregate.

## Candidate resource table
High-level metadata only. License/provenance is **needs verification** for every
row until confirmed from an official source; "commit full file?" defaults to
**no/unknown** pending that verification.

| Resource name | Language | Resource type | License / terms status | Commit full file? | Local-only use possible? | Citation/source needed | Coverage notes | Ambiguity risks | Initial recommendation |
|---|---|---|---|---|---|---|---|---|---|
| Hunspell/Aspell `en_US` dictionary | English | Spellcheck wordlist | needs verification | no/unknown | likely yes | yes | broad common vocabulary; inflected forms vary | shares many forms with Spanish (cognates) | shortlist for verification |
| SCOWL / `dwyl/english-words`-style open wordlist | English | Open wordlist | needs verification | unknown | likely yes | yes | large; may include rare/archaic forms | may over-accept cross-language forms | consider |
| `wordfreq` (English list) | English | Frequency list | needs verification (frequency data may differ) | no/unknown | likely yes | yes | frequency-ranked; may include noisy/nonstandard forms | frequency lists can include other-language tokens | caution — verify license + noise |
| spaCy English lexical data | English | Model/lexical resource | needs verification | no/unknown | only if license allows local use | yes | lemmatizer/vocab, not a plain wordlist | mixing tool output with wordlists complicates rules | caution |
| Hunspell/Aspell `es_ES`/`es` dictionary | Spanish | Spellcheck wordlist | needs verification | no/unknown | likely yes | yes | broad; accent-marked forms present | accents/cognates raise ambiguity | shortlist for verification |
| Open Spanish wordlist (documented) | Spanish | Open wordlist | needs verification | unknown | likely yes | yes | coverage varies by source | RAE-derived content may be restricted | consider (verify provenance) |
| `wordfreq` (Spanish list) | Spanish | Frequency list | needs verification (frequency data may differ) | no/unknown | likely yes | yes | frequency-ranked; noisy forms possible | frequency lists can include English tokens | caution — verify license + noise |
| UniMorph (English / Spanish) | Both | Morphological lexicon | needs verification | unknown | likely yes | yes | lemma/inflection tables; documented | paradigm coverage gaps → more unknowns (safe direction) | consider (morphology) |
| FreeLing dictionaries | Both | Morphological lexicon | needs verification | no/unknown | only if license allows local use | yes | rich morphology; tool-bound | tool coupling; license scope unclear | caution |
| spaCy Spanish lexical data | Spanish | Model/lexical resource | needs verification | no/unknown | only if license allows local use | yes | lemmatizer/vocab, not a plain wordlist | same as English spaCy | caution |

## English candidate resources
- **Hunspell/Aspell `en_US`** — a spellcheck dictionary is a natural plain
  wordlist; broad common-vocabulary coverage. License **needs verification**
  (spellcheck dictionaries ship under varied licenses). Strongest plain-wordlist
  candidate to verify first.
- **SCOWL / open English wordlists** — large, transparent, often citable, but may
  include rare/archaic forms that raise cross-language over-acceptance; verify
  license and curation.
- **`wordfreq` English** — frequency data is attractive for filtering noise, but
  **frequency resources should be treated cautiously**: licensing may differ from
  plain wordlists and lists can include other-language / nonstandard tokens.
- **spaCy English lexical data** — usable **only if** local use and license are
  acceptable; it is a model/lemmatizer resource, not a plain wordlist, which
  complicates the deterministic exact-match rule.

## Spanish candidate resources
- **Hunspell/Aspell `es`** — the Spanish analogue; broad coverage with
  accent-marked forms. License **needs verification**. Strongest plain-wordlist
  candidate to verify first.
- **Open Spanish wordlists** — coverage varies; **watch provenance**, since some
  Spanish lexica derive from RAE content with restrictive terms. Verify before
  use.
- **`wordfreq` Spanish** — same caution as English `wordfreq`: verify license and
  expect noisy/other-language forms.
- **spaCy Spanish lexical data** — same constraints as the English spaCy entry.
- **Morphological lexicons (UniMorph / FreeLing, Spanish side)** — helpful for
  inflected/clitic forms; verify license and local-use terms.

## Cross-language ambiguity concerns
- English and Spanish share many **cognates** and identical surface forms; such
  tokens will appear in **both** lexicons and, per policy, **block positive
  validation by default** (ambiguous → `not_validated`).
- **Unknown** tokens (in neither expected lexicon nor recognized residue) also
  **block positive validation by default**.
- The validator must **prefer false negatives over false positives**: broad,
  noisy lists that accept too much are more dangerous than narrow lists that
  leave more rows `not_validated`.
- **Frequency lists** are especially prone to including other-language tokens and
  nonstandard forms, raising ambiguity risk — hence the "caution" recommendation.

## Licensing review checklist
Before shortlisting a resource, record (from an authoritative source):

- [ ] Exact **license** name/version and where it was confirmed.
- [ ] Whether the license permits **academic / local non-commercial** use.
- [ ] Whether the license permits **redistribution** (→ can the full file be
      committed, or must it stay local/gitignored?).
- [ ] Required **citation / attribution** string and canonical source URL/DOI.
- [ ] Confirmation the resource is **not derived from CALLHOME** transcript text.
- [ ] Confirmation that using it requires **no external upload** of CALLHOME text.

If any item is unresolved, the resource stays **needs verification** and is
**not** used.

## Normalization review checklist
Decide and document **before** any real dry run (per the resource policy):

- [ ] **Lowercasing** / case folding.
- [ ] **Punctuation stripping** (leading/trailing/internal).
- [ ] **Spanish accent handling** — preserve vs. fold (accents are meaningful;
      this must be decided before use).
- [ ] **Contractions / clitics** (English `n't`; Spanish enclitic pronouns).
- [ ] **Proper nouns / names** — treat as language-neutral, not evidence.
- [ ] **Borrowings / cognates** — how established borrowings are handled.
- [ ] **CHAT residue markers** — excluded as non-lexical.

Normalization must be applied **identically** to utterance tokens and lexicon
entries, and be reproducible.

## Why no resource is adopted yet
- No candidate's **license/provenance has been verified** from an authoritative
  source in this PR; unclear license means **not usable yet**.
- The **normalization policy** (esp. Spanish accents, clitics, cognates) is not
  yet fixed, so match behavior is undefined.
- No **synthetic ambiguity/normalization tests** exist for a real resource yet.
- Adopting now would risk over-acceptance (false positives) and possible
  licensing/leakage issues — the opposite of the conservative posture required.
- Constraints that hold regardless: **no CALLHOME-derived tokens** may build or
  modify lexicons; resources requiring **external upload of CALLHOME text are
  disallowed**; **full files are not committed unless the license allows
  redistribution** (otherwise local/gitignored, with only aggregate diagnostics
  committed).

## Recommended next decision
**Conservative recommendation (not a final adoption):** shortlist **one** English
and **one** Spanish plain-wordlist candidate for **license verification only** —
suggested starting points: the **Hunspell/Aspell `en_US`** and **`es`**
dictionaries, because plain spellcheck wordlists map most cleanly onto the
deterministic exact-match rule and avoid tool/model coupling. This is a decision
to *verify licenses*, not to adopt: no download, no commit, no wiring. If either
license cannot be verified as compatible, drop it and verify the next candidate.

## Out of scope
- Selecting or adopting a final resource; downloading anything.
- Implementing a real lexicon loader or wiring the validator into the real-data
  script.
- Exact normalization thresholds and the borrowing/cognate resolution policy.
- **Condition JSONL construction** — remains out of scope.
- Sampling proportions, train/dev/test splitting, tokenizer choice.
- **Model training** — remains out of scope.
- Any Bangor / `CsCont` logic. **CALLHOME never feeds `CsCont`** (Bangor-sourced
  only); a future positive lexicon validation only routes clean English rows to
  `EnglishMono` + `MonoCont` and clean Spanish rows to `SpanishMono` + `MonoCont`.

## Future implementation sequence
Before adopting any real lexicon (a **separate**, reviewed PR or PRs), we need:

1. **License verification** — confirm license/terms for the shortlisted English
   and Spanish candidates from an authoritative source.
2. **Citation / source record** — record the exact citation and canonical source
   in an in-repo resource manifest.
3. **Normalization tests** — synthetic tests pinning the documented normalization
   rules.
4. **Synthetic ambiguity tests** — proving cross-language / unknown forms block
   positive validation.
5. **Local-only dry-run plan** — run on gitignored CALLHOME files with per-row
   output kept local/gitignored.
6. **Aggregate-only diagnostics plan** — validated vs not, method/reason counts,
   and (optionally) coverage/unknown/ambiguous counts, all aggregate and
   non-transcript, reviewed before any clean promotion.

Until this sequence completes and is approved, no real lexicon is loaded, every
CALLHOME row stays `not_validated`, and the `clean` count stays zero.
