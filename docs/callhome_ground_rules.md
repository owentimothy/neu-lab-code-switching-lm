# CALLHOME Ground Rules Verification

## Current decision (read this first)

**Decision B is current.** Aggregate-only, non-transcript CALLHOME summaries may
be committed with the required citation/license notes and the safety
restrictions recorded below. Decision B covers **aggregate reporting only**.

Per-row records and per-row provenance were **not covered** by the question put
to TalkBank/CABank or by the response to it. That exchange addressed aggregate,
non-transcript summaries; it neither permitted nor prohibited per-row material,
because per-row material was not asked about. Under this project's conservative
default — keep material uncommitted unless it is covered by permission — per-row
records and per-row provenance therefore remain **blocked from commit** and stay
local and gitignored. This is a project-policy restriction, not a TalkBank
denial.

Raw corpus material, transcript text, header values, participant information,
speaker identifiers, filenames, and conversation identifiers remain blocked.

The earlier **Decision C is historical and superseded**. Its original reasoning
is preserved verbatim in the "Historical: superseded Decision C" subsection under
`## Decision` below. Note that the sections between here and there are **not**
uniformly historical: they include both the original 2026-07-08 policy review and
the 2026-07-09 TalkBank/CABank response that established current Decision B. Each
section states which state it describes.

## Status (as of the original 2026-07-08 verification)
- Ground-rules verification only.
- No transcript downloads.
- No raw files.
- No parser run.
- No aggregate summaries yet.
- No ingestion.
- No condition JSONL.
- No training.

Verification method: official TalkBank policy pages, checked 2026-07-08.
**Policy pages only** — no transcript content was inspected or downloaded.

## Why this matters
Before committing any CALLHOME-derived summary or manifest (even
aggregate-only counts), we need to know what TalkBank permits. Raw transcripts
can stay local/gitignored regardless, but the question that motivated this
review was **derived aggregate outputs**: may counts/statistics computed from
CALLHOME be committed to this (public) repo, and under what attribution/license
terms? That question was subsequently answered — see "Current decision" above.

## Sources checked (official pages only)

### TalkBank — Basic Rules for Data Usage (`/0share/rules.html`)
- **Access**: non-password-protected data "may be freely distributed";
  password-protected clinical banks are restricted; identifiable data must stay
  local.
- **Citation**: required in publications.
- **Redistribution**: freely distributable for non-password data; do not repost
  password-protected data or share with unauthorized users.
- **Derived outputs / statistics**: **not explicitly addressed.** The page does
  not state whether derived analyses/statistics may be redistributed; the
  non-commercial + share-alike constraints imply derivatives inherit the same
  terms.
- **License**: **Creative Commons CC BY-NC-SA 3.0** — attribution,
  **non-commercial**, **share-alike**. Explicitly **precludes commercial
  products and inclusion of the data in LLMs** (e.g. ChatGPT). Rule is
  **explicit** on license and commercial/LLM prohibition; **unclear** on derived
  statistics.

### TalkBank — Rules for Data Citation (`/0share/citation.html`)
- Cite the **corpus-specific references** listed in the corpus documentation
  manual (primary method).
- A **DOI** may be used when a corpus has no article to cite.
- Additionally include the **general database citation** (e.g. CABank/TalkBank)
  "for grant reporting purposes."
- Some databases require **grant acknowledgments**.
- Rule is **explicit**.

### TalkBank — Data Access Levels (`/0share/access.html`)
- Four levels: **open**, **registration-required**, **approved** (email
  agreement), **controlled** (interview + CITI).
- The page does **not** explicitly classify **CABank / CallHome**. Our earlier
  access verification found CABank CallHome transcripts are **publicly
  downloadable without login**, consistent with open/registration. Rule is
  **explicit** on levels, **unclear** on CABank's exact level.

### TalkBank — Principles / Code of Ethics (`/0share/`, `/0share/ethics.html`)
- Cite sources carefully; do not publish criticism of the transcription/
  collection methods of corpora you analyze. Rule is **explicit** (ethics).

### CABank CallHome corpus pages (from prior access-verification PR)
- English and Spanish CallHome transcripts downloadable; **citation required**
  (English: Canavan et al. 1997 / LDC 2008; Spanish: Canavan & Zipperlen 1996 /
  LDC 2008); Spanish DOI `10.21415/T51K54`.

## Provisional policy for this repo
Unless official rules explicitly say otherwise, adopt this conservative policy:

- **Raw CALLHOME transcripts**: never commit.
- **CALLHOME ZIP archives**: never commit.
- **Transcript excerpts**: never paste into committed docs, tests, PRs, or logs.
- **Synthetic examples**: allowed.
- **Parser code**: allowed.
- **Local parsing for research**: allowed once access rules are satisfied
  (non-commercial academic use, with citation).
- **Derived aggregate summaries**: only commit if TalkBank ground rules permit
  it or we obtain explicit confirmation.
- **If unclear**: keep CALLHOME-derived summaries **local/uncommitted** until
  confirmed.


## TalkBank / CABank permission response — 2026-07-09

On 2026-07-09, after the project sent a permission-confirmation email to the TalkBank / CABank support route, Brian MacWhinney replied that the proposed use "seems fine" and instructed us to stick with the described guidelines.

We interpret this as conditional written approval for the two uses described in the email:

1. committing aggregate, non-transcript CALLHOME summaries to the public repository, provided they contain no transcript text, no header values, no participant names, and no speaker IDs, and include the required citation/license notes;
2. using TalkBank/CABank transcripts for non-commercial academic masked-LM / small research-LM training, provided the project follows the stated non-commercial research restrictions and does not redistribute the underlying transcript data.

Decision update:

- Previous decision: Decision C — do not commit CALLHOME-derived aggregate summaries because permission was unclear.
- New decision: Decision B — aggregate-only, non-transcript CALLHOME summaries may be committed with proper citation/license notes and the safety restrictions above.
- Raw transcripts, ZIP archives, transcript excerpts, header values, participant names, speaker IDs, and transcript-bearing JSONL remain blocked from commit.

### Scope of the permission response

The question put to TalkBank/CABank asked about **aggregate, non-transcript
summaries** (counts and structural markers). The response answered that question.

The following were **not covered by that exchange** — neither the question nor
the response addressed them:

- **per-row** records of any kind, even when each field looks individually
  harmless;
- **conversation identifiers**, source filenames, or any reference from which a
  source row could be re-identified or reconstructed;
- per-row provenance views (for example a serialized projected-row provenance
  record).

Not covered is **not** the same as denied. TalkBank was not asked about per-row
material and did not rule on it. The consequence follows from **this project's
conservative default**, recorded in the "Provisional policy for this repo"
section above: if the official rules and correspondence do not cover an output,
keep it local and uncommitted until they do. Applying that default, per-row
records and per-row provenance are **blocked from commit** and stay **local and
gitignored**.

**Aggregate reporting permission and per-row provenance permission are separate
questions.** Only the first has been asked and answered. The second remains open,
and per-row material — including local, de-identified-looking per-row output —
stays out of the repository until it is asked and separately answered.

## Decision

**B — Aggregate-only, non-transcript CALLHOME summaries may be committed, with
citation/license notes and the safety restrictions recorded above.**

This is the **current** decision, adopted after the TalkBank/CABank response of
2026-07-09 recorded above.

Scope, stated precisely:

- **Permitted to commit — the expressly reviewed examples.** These are the
  output types actually described in the question and covered by the response
  (see `docs/talkbank_permission_email.md`), and they may be committed with the
  required TalkBank + LDC citation and a compatible license note:
  - file counts;
  - utterance counts;
  - aggregate structural-marker counts, such as header-key counts and
    dependent-tier-prefix counts;
  - language-composition percentages.
- **Blocked from commit**: raw transcripts, ZIP archives, transcript excerpts,
  header values, participant names, speaker identifiers, filenames, conversation
  identifiers, transcript-bearing JSONL, per-row records, and any per-row
  provenance or reconstructive material.

**Other aggregate diagnostic categories are not automatically approved merely by
name.** Decision B is not a blanket licence for anything labelled "aggregate".
Category tallies, condition-eligibility tallies, exclusion/flag reason counts,
validation-method or reason-code counts, and any similar output are **not**
covered simply because they sound aggregate. Such an output may be committed only
after confirming, for that specific output, that it is:

- aggregate-only (no per-row records);
- non-transcript (no transcript text, tokens, or header values);
- non-reconstructive (no field or combination of fields from which a source row,
  conversation, speaker, or file could be re-identified);
- free of prohibited identifiers (participant names, speaker identifiers,
  filenames, conversation identifiers);

and after it passes a repository safety review under Decision B. A low
cardinality can itself be reconstructive — a count broken down finely enough can
single out one row — so the review is per-output, not per-category.

Decision B does **not** extend to per-row records. See "Scope of the permission
response" above.

### Historical: superseded Decision C

The following was the project's decision **before** the 2026-07-09 response. It
is retained for context and is **no longer current**; it was superseded by
Decision B above.

> **C — Aggregate-summary permission is unclear; do not commit CALLHOME-derived
> summaries yet.**
>
> Rationale: the evidence actually leans **permissive** — CC BY-NC-SA 3.0 allows
> non-commercial derivatives with attribution and share-alike, and non-password
> CABank data "may be freely distributed," so aggregate, non-transcript counts are
> very likely shareable (this is essentially option **B**). **But** TalkBank does
> **not explicitly** address redistributing derived statistics, and the
> **share-alike (SA)** and **non-commercial (NC)** terms have unresolved
> implications for committing derived data to a public GitHub repo (repo licensing
> / downstream reuse). Given genuine uncertainty and zero cost to waiting (the
> parser can still produce **local, gitignored** summaries), we default to **C**.
>
> Upgrade path: a single confirmation email to TalkBank/CABank (see Open
> questions) would likely move us to **B** — commit aggregate-only summaries with
> TalkBank + LDC citation and a compatible license note.

That upgrade path was taken: the confirmation email was sent, a response was
received on 2026-07-09, and the decision moved C → B.

## Citation requirements
Record obligations; mark unresolved exact reference strings as TODO (do not
guess full bibliographic entries):

- **CALLHOME English** — corpus-specific reference from the CallHome English
  manual (Canavan, Graff & Zipperlen, 1997, LDC97T14/LDC97S42) and/or LDC 2008.
  Exact citation string: **TODO** (confirm from the manual).
- **CALLHOME Spanish** — corpus-specific reference (Canavan & Zipperlen, 1996,
  LDC96T17/LDC96S35) and/or LDC 2008; DOI `10.21415/T51K54`. Exact citation
  string: **TODO**.
- **TalkBank / CABank** — general database citation required for grant
  reporting. Exact string (MacWhinney; CABank): **TODO**.
- **LDC** — if cited as contributor/source, follow the LDC catalog citation for
  the specific catalog IDs. **TODO**.
- **English vs Spanish** — likely **different** corpus-specific references (and
  the Spanish DOI); confirm both. **TODO**.

## Repository implications
- The **parser scaffold stays committed** (`src/cslm/data/callhome_chat.py`) — it
  contains no corpus data.
- The **synthetic parser tests stay committed** — no real transcript text.
- **Real CALLHOME files** stay under `data/raw/callhome/` and remain
  **gitignored** (added in the format-audit PR).
- **Real CALLHOME parser runs are local only.**
- **CALLHOME-derived aggregate, non-transcript summaries MAY be committed** under
  Decision B, with the required citation/license notes and the safety
  restrictions recorded above. (This line previously stated the opposite under
  the superseded Decision C.) The expressly reviewed examples are listed under
  `## Decision`; other aggregate categories require a per-output safety review
  and are not approved merely by being called aggregate.
- **Per-row CALLHOME material is NOT committed.** Decision B covers aggregate
  reporting only. Per-row records, per-row provenance views, conversation
  identifiers, and any reconstructive reference were not covered by the
  permission exchange, so under this repo's conservative default they remain
  **local and gitignored** regardless of how de-identified they appear.
- Local, gitignored per-row output remains available for research (e.g. under
  `data/processed/callhome_*/` — add to `.gitignore` when that step arrives),
  keeping the workflow unblocked without committing per-row material.

## Cross-cutting flag (out of scope here, but important)
The **CC BY-NC-SA 3.0 non-commercial / "no data in LLMs"** clause applies to
**all TalkBank corpora — including Bangor Miami**, not just CALLHOME. This may
constrain the eventual **model-training** phase (training masked LMs on this
data). Non-commercial academic research is a permitted use, but the explicit
mention of "LLMs such as ChatGPT" warrants confirming that **non-commercial
research MLM training** is permitted **before** the training phase begins. This
is flagged for the training milestone; it does not affect this docs-only PR.

## Open questions

Answered (see the 2026-07-09 response above):

- ~~Are **aggregate counts/statistics** considered derived data that may be
  shared publicly under CC BY-NC-SA (attribution + NC + SA)?~~ — answered for
  the reviewed aggregate, non-transcript examples; this is what moved the
  decision C → B. Aggregate categories beyond those examples still need a
  per-output safety review.
- ~~Should we **email TalkBank / CABank** for explicit confirmation before
  committing any aggregate summaries (recommended before upgrading C → B)?~~ —
  done; the email was sent and a response was received on 2026-07-09.

Still open:

- May **per-row** CALLHOME-derived records (including per-row provenance views
  and conversation identifiers) be committed? **Not asked, so not answered** —
  the 2026-07-09 exchange covered aggregate summaries only and did not rule on
  per-row material either way. Pending a separate question and answer, this
  repo's conservative default keeps per-row material local and gitignored.
- Are **short transcript excerpts** ever allowed in publications, and under what
  limits?
- Do **CALLHOME English and Spanish** have different citation requirements
  (confirm exact strings + the Spanish DOI)?
- Does **NYU / LDC** access impose **stricter** terms than the TalkBank CABank
  route (e.g. LDC User Agreement redistribution limits)?
- Does **non-commercial research MLM training** on TalkBank data fall within the
  permitted-use scope of CC BY-NC-SA 3.0 given the "no LLM" language? (Training
  milestone.)

## Sources (official pages, policy text only)
- TalkBank Principles: https://talkbank.org/0share/
- TalkBank Basic Rules for Data Usage: https://talkbank.org/0share/rules.html
- TalkBank Rules for Data Citation: https://talkbank.org/0share/citation.html
- TalkBank Data Access Levels: https://talkbank.org/0share/access.html
- TalkBank Code of Ethics: https://talkbank.org/0share/ethics.html
- CABank CallHome (English/Spanish) corpus pages: https://talkbank.org/ca/access/CallHome/
