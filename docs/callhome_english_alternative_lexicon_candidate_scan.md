# English Alternative Lexicon Candidate Scan

## Status
```text
Candidate-scan conclusion:
Category B — a promising candidate exists but needs another evidence pass

Strongest candidate:
Direct SCOWL / English Speller Database (ESDB)

Current LibreOffice resource selection:
YES / REMAINS SELECTED PENDING REVIEW

Alternative replacement decision:
NOT MADE

Operational adoption or use:
NO / NOT APPROVED
```

This is a **repository governance record, not legal advice.** It records
candidate-comparison evidence only. It does **not** replace the currently selected
LibreOffice candidate and does **not** approve downloading, placement, loading,
validation, clean promotion, condition construction, tokenization, or training.

- **Read-only upstream inspection only.** Official upstream repository/API/raw and
  official documentation content was inspected read-only; **no lexical artifact was
  downloaded or saved into this project.**
- **No CALLHOME transcript content or CALLHOME-derived evidence was inspected or
  used.**
- **The real pipeline remains unchanged** (`default_source_validation` only;
  validator/loader not wired in). Every real CALLHOME row stays `not_validated`;
  `clean` stays zero.
- **All operational approvals remain `NO / NOT APPROVED`.**

## Problem Being Addressed
- The selected **LibreOffice `en_US`** candidate remains **operationally blocked**:
  its `en/` package carries a package-level **GPLv2 `license.txt` whose file-specific
  applicability** to `en_US.dic`/`en_US.aff` is **unresolved** (Category C in
  `docs/callhome_english_lexicon_license_applicability_investigation.md`).
- The purpose of this scan was to determine whether an **alternative resource** has
  **clearer file/output-specific licensing** and **adequate exact-match
  suitability** for conservative CALLHOME English validation.
- **No candidate is selected or adopted in this branch.** The current LibreOffice
  resource **remains selected for governance pending review**.

## Current Validator Requirements
Documented directly from
`src/cslm/data/callhome_lexicon_loader.py` and
`src/cslm/data/callhome_lexicon_validation.py`:

- **UTF-8** input.
- A **plain one-entry-per-line** wordlist **or** a Hunspell **`.dic`** file.
- An optional **numeric `.dic` count header** (a leading all-digits line) is
  skipped.
- Hunspell **affix flags after `/`** are stripped (`hello/AB` → `hello`).
- **No `.aff` expansion** — affix files are not read; affixes are not expanded.
- **NFC** Unicode normalization.
- **Outer-punctuation stripping** (leading/trailing `P*`/`Z*`).
- **Lowercase** matching.
- **Internal apostrophes and hyphens preserved** (e.g. `don't`, `co-op`).
- **Every lexical token** in an utterance **must match** the expected-language
  lexicon.
- An expected-language match **must not also match** another-language lexicon
  (ambiguous → blocked).
- **Unknown tokens remain `not_validated`** (false negatives preferred over false
  positives).

**Why this matters:** because there is **no morphological/affix expansion**, the
lexicon must already contain the **surface forms** that appear in speech —
including **function words** (`the`, `a`, `of`, `to`, `you`, `I`), **inflected
forms** (`kids`, `running`, `walked`), and **contractions** (`don't`, `it's`).
A lemma-only or content-word-only resource would over-reject natural conversational
English, producing excessive false negatives (the safe direction, but a poor
validator).

## Candidates Considered
1. **Direct SCOWL / English Speller Database (ESDB)** — official upstream, not the
   LibreOffice-packaged copy.
2. **Princeton WordNet** — official lexical-semantic database.
3. **Alternate 12Dicts** — official curated public-domain word lists (Alan Beale).
4. **Excluded from serious consideration:** arbitrary GitHub wordlist mirrors (e.g.
   `dwyl/english-words`) — a wrapper-repository license does not establish the
   lexical data's provenance/license; **frequency corpora** (e.g. `wordfreq`) —
   mixed, partly non-pinnable corpus provenance and frequency (not a clean
   deterministic lexicon), and some draw on external corpora; and **archaic generic
   wordlists** (e.g. Webster's-derived `web2`) — poor coverage of modern
   conversational forms and contractions. None of these meet the authoritative-
   provenance / file-specific-license / exact-match requirements.

## Candidate Findings

### Direct SCOWL / ESDB
- **Official upstream identity:** the English Speller Database (ESDB), GitHub
  `en-wl/wordlist`, homepage `wordlist.aspell.net`. This is the **direct** upstream,
  distinct from the LibreOffice-packaged copy.
- **Branch:** `v2` (current default).
- **Combined-work permission applies directly to generated output:** the root
  `Copyright` file grants permission to use/copy/modify/distribute/sell **"any part
  of the English Speller Database (ESDB)"** and **"word lists created from it"**,
  without fee. The permission therefore **reaches a generated wordlist**, not only
  the database.
- **Primary notice requirement:** the primary copyright and permission notice (the
  text **before the `===` separator**) must be preserved in all copies.
- **AU / UKACD conditional notices:** additional component notices — Australian
  English (Benjamin Titze) and the UK Advanced Cryptics Dictionary (J Ross
  Beresford) — are listed after the separator. The `Copyright` file states that for
  an official ESDB speller dictionary that is **not Australian English**, **"no
  additional copyright applies and including the notice before the === is
  sufficient."**
- **American size-60 speller wordlist:** an **American-dialect** speller wordlist at
  the recommended **size 60** does **not appear to trigger** those additional AU/
  UKACD conditions (it is non-Australian; UKACD/AU material is associated with the
  Australian dialect and with larger generated lists). Under the conditional rule,
  the **primary notice before the `===` appears sufficient** for that intended
  output. (This is a governance reading of the upstream text, **not legal advice**;
  the exact notice bundle is a next-pass item.)
- **Dialect and size controls:** documented sizes **35, 50, 60, 70, 80, 85** (size
  60 recommended for spell-checking) and dialect/variant controls (American,
  British `-ise`/`-ize`, Canadian, Australian via spelling codes `A`/`B`/`Z`/`C`/`D`;
  variant levels `0–9`).
- **Inflection information:** ESDB carries **inflection information** and derived
  forms (plurals, verb tenses) via its part-of-speech data.
- **Contraction POS/category support:** ESDB's POS categories include a
  **`s: contraction`** category, so contraction surface forms are representable.
- **Deterministic extraction capability:** the documented American extraction
  example is `./scowl --db scowl.db word-list 60 A 1 > wl.txt`, producing a plain
  wordlist compatible with the current loader.
- **Unresolved:** the **exact immutable ESDB/v2 commit** and the **exact extraction
  command/options** (size threshold, variant level, category/abbreviation/compound/
  proper-name/diacritic policy, reproducibility) **remain unresolved** and are
  **not** decided here.
- **Governance status:**
  ```text
  PROMISING BUT REQUIRES MORE EVIDENCE
  ```

### Princeton WordNet
- **Clear permissive license:** the official WordNet / Princeton notice permits
  use/copy/modify/distribute for any purpose provided the copyright and permission
  notice appear in all copies (with a warranty disclaimer and a no-name-in-
  advertising restriction).
- **Authoritative lexical-semantic resource.**
- **Coverage:** organized around **nouns, verbs, adjectives, and adverbs** only.
- **Morphology structure:** provides **morphology exception files** (base-form
  lookup via Morphy) rather than a comprehensive **enumerated conversational
  surface vocabulary**; it also excludes closed-class **function words**.
- **Technically incompatible** as the standalone validator lexicon: under the
  current exact-surface-match, no-expansion validator, WordNet would **omit or fail
  to directly validate** many function words and inflected conversational forms,
  producing extreme false-negative behavior.
- **Governance status:**
  ```text
  NOT SUITABLE
  ```

### Alternate 12Dicts
- **Authoritative project source:** the official 12dicts / Alternate 12Dicts word
  lists (Alan Beale), `wordlist.aspell.net/12dicts`.
- **Core public-domain statement:** the official Alternate 12Dicts readme states
  that **"All of these files have been explicitly placed in the Public Domain by
  Alan Beale."**
- **Useful common-word material:** curated, error-checked common-word lists.
- **AGID-related qualification:** some **inflection-rich** files depend on **AGID**
  and require more careful **artifact-specific** review before their status can be
  treated as equivalent to the core public-domain lists.
- **Less complete / less directly suitable than ESDB**, and **largely represented
  within ESDB's source lineage** (12dicts/ENABLE2K are ESDB "and Friends"
  components). It is therefore **not the strongest candidate**.
- **Governance status:**
  ```text
  PROMISING BUT REQUIRES MORE EVIDENCE
  ```

## Candidate Matrix
| Candidate | Official upstream | Candidate artifact model | Immutable pin readiness | File/output-specific license clarity | Notice pathway | Exact-match suitability | Major limitation | Governance status |
| --------- | ----------------- | ------------------------ | ----------------------- | ------------------------------------ | -------------- | ----------------------- | ---------------- | ----------------- |
| **Direct SCOWL / ESDB** | `en-wl/wordlist` (`v2`); `wordlist.aspell.net` | Generated American wordlist via `scowl` (e.g. size 60, code `A`) | Pinnable via a specific `v2` commit + fixed extraction command (not yet chosen) | **DIRECT** — permission reaches "word lists created from" ESDB; non-Australian speller needs only the primary notice | Primary notice before `===`; AU/UKACD conditional (not triggered by American size-60); all permissive/PD | **Good** — plain wordlist, inflections + contraction POS, dialect/size controls | Exact commit + extraction policy not yet defined | **PROMISING BUT REQUIRES MORE EVIDENCE** |
| **Princeton WordNet** | `wordnet.princeton.edu` (WordNet 3.x) | Lemma/index database + morphology exception files | Versioned DB release | STRONG (permissive WordNet notice) | Single WordNet/Princeton notice | **Poor** — content words only; no function words; no enumerated inflected surface forms | Excludes function words + inflections ⇒ extreme false negatives | **NOT SUITABLE** |
| **Alternate 12Dicts** | `wordlist.aspell.net/12dicts`; `en-wl/wordlist` | A specific list file (e.g. `2of12`, `2of12inf`) | Pinnable via dated release / commit | Core lists **DIRECT public domain**; inflection files carry an **AGID** qualification | Public-domain acknowledgment; AGID files need artifact-specific review | Moderate — clean lists are common/base-word-leaning | Best (inflected) file has the AGID qualification; subsumed by ESDB | **PROMISING BUT REQUIRES MORE EVIDENCE** |

## Evidence Matrix
| Candidate | Evidence source | Exact path/ref | What it explicitly establishes | What remains unresolved | Confidence |
| --------- | --------------- | -------------- | ------------------------------ | ----------------------- | ---------- |
| Direct SCOWL / ESDB | Repo metadata | `api.github.com/repos/en-wl/wordlist` | Official project; default branch `v2`; homepage `wordlist.aspell.net`; license `NOASSERTION` | Which exact `v2` commit to pin | DIRECT |
| Direct SCOWL / ESDB | `Copyright` file | `en-wl/wordlist/v2/Copyright` | Permission covers "any part of the ESDB" **and** "word lists created from it"; primary notice before `===` suffices for a non-Australian speller dictionary; components (Titze, Beresford, WordNet, COCA, 12dicts/ENABLE2K) all permissive/PD; **no GPL** | Exact notice bundle for the chosen output | DIRECT |
| Direct SCOWL / ESDB | `README.md` | `en-wl/wordlist/v2/README.md` | ESDB/v2 is a **generated** system (`scowl.txt` + `scowl.db`); American extraction `./scowl --db scowl.db word-list 60 A 1 > wl.txt`; sizes 35/50/60/70/80/85 (60 recommended); dialect `A/B/Z/C/D`; variant `0–9`; inflection + POS incl. `s: contraction` | Exact extraction options + reproducibility for the chosen artifact | DIRECT |
| Direct SCOWL / ESDB | Release channel | SourceForge ESDB (historical SCOWLv1 dated releases exist) | Dated SCOWLv1 releases exist historically | ESDB/**v2** is generated and **not** the same as a static SCOWLv1 `2020.12.07` tarball | STRONG |
| Princeton WordNet | License notice | `en/WordNet_license.txt` @ pinned LibreOffice snapshot (verified this session) | Permissive WordNet/Princeton notice; warranty disclaimer; name restriction | Fresh Princeton license page (fetch returned 403 this pass) | DIRECT (notice) |
| Princeton WordNet | Official documentation | `wordnet.princeton.edu` (Morphy / glossary) | WordNet is organized around nouns/verbs/adjectives/adverbs and provides morphology **exception** lists for base-form lookup | Fresh page fetch blocked (403); relied on documented WordNet design | NO EXPLICIT EVIDENCE FOUND (fresh fetch); STRONG (documented design) |
| Alternate 12Dicts | Official readme | `wordlist.aspell.net/alt12dicts-readme/` | "All of these files have been explicitly placed in the Public Domain by Alan Beale" | Which exact list file to adopt | DIRECT |
| Alternate 12Dicts | Project docs | `wordlist.aspell.net/12dicts/` (README‑infl) | Inflection-rich `2of12inf` derives from **AGID**, requiring artifact-specific review | The inflected file's exact usable status | STRONG |
| All candidates | Loader/validator code | `src/cslm/data/callhome_lexicon_loader.py`, `…/callhome_lexicon_validation.py` | Plain/`.dic` raw entries; no affix expansion; exact-surface match; false-negative bias | — | DIRECT |

## Comparative Finding
Direct ESDB is **stronger than the selected LibreOffice package** because:

- its **permission explicitly reaches generated wordlists** ("word lists created
  from" the ESDB);
- it does **not** rely on an **unmapped package-level GPLv2 file** (the exact issue
  that blocks the LibreOffice candidate);
- it is **designed for speller dictionaries** and includes **inflection
  information** (and a contraction POS category);
- it provides **explicit American-dialect and size controls**;
- it can **generate a plain wordlist compatible with the current loader**.

It is **not yet selected** because:

- an **exact immutable v2 commit has not been chosen**;
- the **extraction command and options have not been finalized**;
- the **resulting artifact has not been defined**;
- **contraction, abbreviation, compound, proper-name, category, and diacritic
  policies have not been governed**;
- **no output hash or notice bundle has been approved**.

## Final Conclusion
```text
Category B — a promising candidate exists but needs another evidence pass
```

Strongest candidate:
```text
Direct SCOWL / English Speller Database (ESDB)
```

**The existing LibreOffice selection is not replaced by this branch.**

## Approval Matrix
| Gate                                    | Status            |
| --------------------------------------- | ----------------- |
| Alternative candidate scan completed    | YES / RECORDED    |
| Strongest alternative identified        | YES / ESDB        |
| Exact ESDB artifact defined             | NO / NOT YET      |
| Immutable ESDB v2 pin selected          | NO / NOT YET      |
| ESDB extraction policy selected         | NO / NOT YET      |
| ESDB notice pathway finalized           | NO / NOT YET      |
| Existing LibreOffice selection replaced | NO                |
| English license-and-notice pathway      | NO / NOT APPROVED |
| Download approval                       | NO / NOT APPROVED |
| Local placement                         | NO / NOT APPROVED |
| Hash computation                        | NO / NOT APPROVED |
| Loader use                              | NO / NOT APPROVED |
| Aggregate dry run                       | NO / NOT APPROVED |
| Real CALLHOME validation                | NO / NOT APPROVED |
| Clean promotion                         | NO / NOT APPROVED |
| Condition construction                  | NO / NOT APPROVED |
| Tokenization                            | NO / NOT APPROVED |
| Model training                          | NO / NOT APPROVED |

## Pipeline and Safety State
```text
CALLHOME English
→ potentially EnglishMono
→ potentially the English portion of MonoCont
→ never CsCont
```

- **Bangor remains the only final source for `CsCont`.**
- **No CALLHOME content or CALLHOME-derived evidence was used.**
- **No lexical artifact was downloaded or saved.**
- **All 88,404 CALLHOME rows remain `not_validated`.**
- **`validated`, `lexicon_exact_match`, `clean`, and all condition candidate counts
  remain zero.**

## Next Step
The next branch should be:
```text
callhome-english-scowl-candidate-evidence
```

Its purpose will be to define and evaluate:

- one **exact immutable ESDB/v2 commit**;
- one **exact American-English extraction command**;
- **size threshold**;
- **variant level**;
- **category handling**;
- **contraction handling**;
- **abbreviation handling**;
- **hyphenated / open compounds**;
- **diacritic policy**;
- **proper-name policy**;
- **required notice bundle**;
- **deterministic output identity**.

That future branch remains **evidence-only** and does **not** approve download,
placement, loading, or CALLHOME validation.
