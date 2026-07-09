# CALLHOME Access Verification

## Status
- Planning / access verification only.
- No corpus downloads committed.
- No ingestion.
- No training.
- No condition JSONL.

Verification method: official catalog / index pages only, checked 2026-07-08.
**Metadata only** was inspected (titles, counts, format, access terms) — no
transcript content was fetched, downloaded, or quoted.

## Why this matters
CALLHOME English + CALLHOME Spanish are the primary candidate pair for
`EnglishMono`, `SpanishMono`, and `MonoCont` because they are spoken,
spontaneous, adult, conversational, and **collection-parallel** across the two
languages (same CALLHOME telephone-call protocol) — matching Bangor Miami's
register far better than written/news/web text. Before any parser work we must
confirm three things: (1) that transcripts (not just audio) are actually
obtainable, (2) the transcript **format**, and (3) the **licensing / access**
path and what may be committed.

## Official sources verified

### TalkBank CABank (public)
- **CABank CallHome index** — lists CallHome corpora in Chinese, English,
  German, Japanese, and Spanish, all contributed by LDC. Transcripts are
  downloadable ("the second link will download the transcripts"); the whole
  CABank is also browsable online.
- **CABank English CallHome** — English; transcripts downloadable (browsable +
  ZIP); media available; **no login explicitly required**; usage governed by
  TalkBank rules with a **citation requirement** (LDC 2008 or Canavan et al.
  1997). ~120 unscripted telephone conversations.
- **CABank Spanish CallHome** — Spanish; transcripts downloadable (ZIP);
  browsable; media available; **no login required for download**; citation
  requirement (LDC 2008 or Canavan & Zipperlen 1996); DOI `10.21415/T51K54`.
- **Format**: TalkBank CABank distributes **CHAT / CA-CHAT** (`.cha`) — the
  Conversation-Analysis flavor of the CHAT format. (Bangor Miami is itself a
  TalkBank corpus, so this format family is already familiar to the project.)

### LDC catalog (licensed)
- **LDC97T14 — CALLHOME American English Transcripts**: transcripts (text),
  ~56 hours, 120 unscripted telephone conversations; standard orthography,
  **time-stamped by speaker turn**. LDC User Agreement for Non-Members; via
  subscription/standard membership or non-member purchase (fee; login to view).
- **LDC96T17 — CALLHOME Spanish Transcripts**: transcripts (text), ~38 hours,
  120 conversations; standard orthography, time-stamped by turn; **encoded
  ISO-8859-1** (UTF-8 conversion needed). Same LDC access terms.
- **LDC97S42 — CALLHOME American English Speech** and **LDC96S35 — CALLHOME
  Spanish Speech**: audio only (8 kHz telephone), same LDC access terms. Not
  needed — this project uses transcripts, not audio.

## Access matrix

| Row | Language | Source / provider | Transcripts | Format | Access status | Action needed | Risk |
|---|---|---|---|---|---|---|---|
| CALLHOME English via TalkBank | English | TalkBank CABank (LDC-contributed) | Yes (ZIP + browse) | CHAT / CA-CHAT `.cha` | **Public download, no login**; citation required | Confirm `.cha`/CA conventions; cite Canavan et al. 1997 / LDC 2008 | CA-CHAT parsing complexity; raw not committable |
| CALLHOME Spanish via TalkBank | Spanish | TalkBank CABank (LDC-contributed) | Yes (ZIP + browse) | CHAT / CA-CHAT `.cha` | **Public download, no login**; citation required; DOI 10.21415/T51K54 | Confirm encoding (UTF-8 on TalkBank); screen incidental CS/borrowing | Incidental code-switching in Spanish; raw not committable |
| CALLHOME English via LDC | English | LDC (LDC97T14) | Yes | LDC transcript (standard orthography, turn-timestamped) | Licensed: membership or non-member purchase (fee, login) | Only if TalkBank insufficient; use institutional membership | Cost / licensing; redistribution limits |
| CALLHOME Spanish via LDC | Spanish | LDC (LDC96T17) | Yes | LDC transcript; ISO-8859-1 | Licensed: membership or non-member purchase (fee, login) | Only if TalkBank insufficient; convert encoding | Cost / licensing; encoding conversion |
| NYU / LDC institutional path | Both | NYU library ↔ LDC membership | Yes (if NYU is an LDC member) | LDC transcript | **Unverified** — depends on NYU LDC membership | Confirm NYU LDC membership + data-use terms | Access/approval latency; internal agreement |

## Decision criteria (what counts as sufficient access)
- **Transcript files** available, not just audio. — ✅ met (TalkBank).
- **Legal / allowed** use for research preprocessing. — ✅ likely (TalkBank
  public + citation); LDC path also allowed under its agreement.
- **Format parseable** into utterance / turn rows. — ✅ CHAT/CA-CHAT is
  structured and turn-based (needs a new parser; well-documented).
- **Raw transcript files can remain local / gitignored.** — ✅ required; mirror
  the Bangor policy (raw never committed).
- **Aggregate summaries** can be committed or at least safely discussed. — ⚠️
  to confirm against TalkBank ground rules (assume aggregate counts are fine, as
  with Bangor, but verify before committing any CALLHOME-derived summary).

## Recommendation

**Do not implement ingestion until access is confirmed** — but access **is**
effectively confirmed for the transcript path.

**Recommendation A — CALLHOME via TalkBank is accessible and parseable.**
TalkBank CABank offers **public, login-free** transcript downloads for both
CALLHOME English and CALLHOME Spanish (CHAT/CA-CHAT), governed by a citation
requirement rather than a paywall. This is the preferred path. The next PR can
safely **inspect the transcript format** (structure/headers/tiers only — not
content) to design a CHAT parser, keeping raw `.cha` files local/gitignored.

- **Primary**: TalkBank CABank (free, no login, citation-governed).
- **Fallback (B)**: LDC transcripts (LDC97T14 / LDC96T17) via NYU/LDC
  institutional membership if the canonical LDC transcripts, turn timestamps, or
  a specific train/dev/test partition are needed and not present in the TalkBank
  release.
- **(C)** is not required — CALLHOME is accessible — but Fisher English/Spanish
  remains the documented backup if a larger corpus is later wanted.

## Open questions
- Can transcripts be **directly downloaded from TalkBank**? — **Yes** (public
  ZIP + browsable), per the CABank CallHome pages. *Confirm exact download link
  and that no click-through agreement blocks scripted download.*
- Does TalkBank require **login or agreement**? — **No login** for download; a
  **citation requirement** applies (Canavan et al. 1997 / Canavan & Zipperlen
  1996 / LDC 2008). Confirm TalkBank "ground rules" for derived outputs.
- Does **NYU provide LDC access** to CALLHOME English/Spanish transcripts? —
  **Unverified**; only needed if we fall back to the LDC path.
- Are **English and Spanish transcripts in the same format**? — Via TalkBank,
  **yes** (both CHAT/CA-CHAT). Via LDC they are both "standard orthography,
  turn-timestamped" but Spanish is ISO-8859-1 (encoding difference).
- Are **timestamps / speaker turns** available? — Turn structure: yes (both
  paths). Turn-level timestamps: stated for the LDC transcripts; confirm whether
  the TalkBank `.cha` release carries the alignment/`%snd` timing.
- Are there **restrictions on derived aggregate summaries**? — To verify against
  TalkBank ground rules before committing any CALLHOME-derived aggregate.
- Does the **Spanish corpus contain incidental code-switching** needing
  screening before use as a clean monolingual baseline? — Likely some; plan a
  light monolingual screen (reuse Bangor-style token language ideas).

## Guardrails honored by this note
- No transcript archives downloaded into the repo.
- No raw corpus files committed.
- No transcript excerpts pasted (only catalog/index metadata was inspected).
- Download links were checked for **access/path/metadata only**, not content.
- This PR is **docs-only**.

## Sources (official pages, metadata only)
- TalkBank CABank CallHome index: https://talkbank.org/ca/access/CallHome/
- TalkBank CABank English CallHome: https://talkbank.org/ca/access/CallHome/eng.html
- TalkBank CABank Spanish CallHome: https://talkbank.org/ca/access/CallHome/spa.html
- LDC97T14 CALLHOME American English Transcripts: https://catalog.ldc.upenn.edu/LDC97T14
- LDC96T17 CALLHOME Spanish Transcripts: https://catalog.ldc.upenn.edu/LDC96T17
- LDC97S42 CALLHOME American English Speech: https://catalog.ldc.upenn.edu/LDC97S42
- LDC96S35 CALLHOME Spanish Speech: https://catalog.ldc.upenn.edu/LDC96S35
