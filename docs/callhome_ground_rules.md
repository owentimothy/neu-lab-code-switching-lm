# CALLHOME Ground Rules Verification

## Status
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
can stay local/gitignored regardless, but the open question is **derived
aggregate outputs**: may counts/statistics computed from CALLHOME be committed
to this (public) repo, and under what attribution/license terms?

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

## Decision

**C — Aggregate-summary permission is unclear; do not commit CALLHOME-derived
summaries yet.**

Rationale: the evidence actually leans **permissive** — CC BY-NC-SA 3.0 allows
non-commercial derivatives with attribution and share-alike, and non-password
CABank data "may be freely distributed," so aggregate, non-transcript counts are
very likely shareable (this is essentially option **B**). **But** TalkBank does
**not explicitly** address redistributing derived statistics, and the
**share-alike (SA)** and **non-commercial (NC)** terms have unresolved
implications for committing derived data to a public GitHub repo (repo licensing
/ downstream reuse). Given genuine uncertainty and zero cost to waiting (the
parser can still produce **local, gitignored** summaries), we default to **C**.

Upgrade path: a single confirmation email to TalkBank/CABank (see Open
questions) would likely move us to **B** — commit aggregate-only summaries with
TalkBank + LDC citation and a compatible license note.

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
- **CALLHOME-derived aggregate manifests are NOT committed** under Decision C.
- If aggregates cannot (yet) be committed, the code can still generate **local,
  gitignored** summaries (e.g. under `data/processed/callhome_*/` — add to
  `.gitignore` when that step arrives), keeping the workflow unblocked.

## Cross-cutting flag (out of scope here, but important)
The **CC BY-NC-SA 3.0 non-commercial / "no data in LLMs"** clause applies to
**all TalkBank corpora — including Bangor Miami**, not just CALLHOME. This may
constrain the eventual **model-training** phase (training masked LMs on this
data). Non-commercial academic research is a permitted use, but the explicit
mention of "LLMs such as ChatGPT" warrants confirming that **non-commercial
research MLM training** is permitted **before** the training phase begins. This
is flagged for the training milestone; it does not affect this docs-only PR.

## Open questions
- Are **aggregate counts/statistics** considered derived data that may be shared
  publicly under CC BY-NC-SA (attribution + NC + SA)?
- Are **short transcript excerpts** ever allowed in publications, and under what
  limits?
- Do **CALLHOME English and Spanish** have different citation requirements
  (confirm exact strings + the Spanish DOI)?
- Should we **email TalkBank / CABank** for explicit confirmation before
  committing any aggregate summaries (recommended before upgrading C → B)?
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
