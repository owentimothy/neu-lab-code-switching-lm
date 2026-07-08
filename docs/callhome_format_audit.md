# CALLHOME Format Audit

## Status
- Format audit only.
- Raw files remain local / gitignored.
- No transcript excerpts.
- No parser implementation.
- No ingestion.
- No condition JSONL.
- No training.

## Purpose
Before building a CALLHOME parser we need to understand the `.cha` file
structure well enough to design a parser **contract** (not to implement it).
Specifically:
- header lines
- participant metadata
- main speaker tiers
- dependent tiers
- media / timing tiers if present
- utterance / turn boundaries
- continuation-line conventions
- encoding concerns
- differences between the English and Spanish files

## What was inspected

**No local CALLHOME `.cha` files are present in the repo**, and per the branch's
safety rules nothing was auto-downloaded. This audit is therefore based on the
public **CHAT / CA-CHAT format specification** (TalkBank/CLAN), described at the
level of **structural markers only** — header-key names and tier prefixes — with
**no transcript content**. Every structural expectation below is marked as
*spec-expected* and must be **verified against local files** once they are placed
under the gitignored `data/raw/callhome/` path (see "Local audit inputs needed").

Allowed structural facts this audit relies on (format markers, not content):
- **File extension**: `.cha` (CHAT transcripts); archives arrive as `.zip`.
- **Header lines** begin with `@`, e.g. `@UTF8` (encoding declaration),
  `@Begin`, `@Languages`, `@Participants`, `@ID` (one per participant),
  `@Media`, `@Options`, `@Date`, `@Comment`, `@End`.
- **Main (speaker) tiers** begin with `*` + a short speaker code + `:`
  (e.g. `*ABC:`), followed by the utterance.
- **Dependent tiers** begin with `%`, e.g. `%mor`, `%gra`, `%com`, `%wor`,
  `%snd` (media/time alignment).
- **CHAT vs CA-CHAT**: CABank uses the Conversation-Analysis flavor (CA-CHAT),
  which adds CA notation (overlap, latching, intonation markers) on the main
  tier — to be confirmed per file.
- **Media / timing** may appear as `%snd`/`%mov` tiers or as time-alignment
  "bullets" attached to the end of a main tier.
- **English vs Spanish**: expected to share the same CHAT header/tier **family**
  (differing in `@Languages: eng` vs `spa`), but possibly differing in which
  dependent tiers are present and in **encoding** (see below).

Forbidden (and not done): no utterance text, no participant names beyond the
generic speaker-code *structure*, no copied transcript lines, no raw examples
from actual files. Any examples in this note or in future tests are **synthetic**
(e.g. a made-up `*AAA:` line), never drawn from CALLHOME.

## Local audit inputs needed
To run the actual (Phase-4) structural inspection, the following must be placed
locally under the **gitignored** raw path (they will not be committed):
- `data/raw/callhome/eng/…*.cha` — CALLHOME English transcripts (TalkBank ZIP).
- `data/raw/callhome/spa/…*.cha` — CALLHOME Spanish transcripts (TalkBank ZIP).

Once present, allowed checks are structure-only: count `.cha` files, list
**distinct header keys without values**, list **distinct tier prefixes without
text**, check whether `%snd`/media tiers appear, and compare whether English and
Spanish use the same structural conventions — never `head`/`cat` of content.

## Expected parser contract

Mirror the Bangor design: a **source-faithful** intermediate object, kept
strictly separate from experiment-facing projection.

Future source-faithful object (sketch — not implemented):

```
CallhomeUtterance:
  conversation_id: str          # e.g. derived from source file stem
  source_file: str              # .cha filename (local; not committed)
  speaker_id: str               # normalized from the *XYZ: speaker code
  turn_index: int               # ordered within the conversation
  raw_main_tier_text: str       # verbatim main-tier text (sensitive; local only)
  dependent_tiers: dict[str,str]# %mor/%gra/%com/... captured verbatim
  language: str                 # from @Languages (eng / spa)
  media_time: tuple|None        # optional start/end from %snd / bullets
  parser_warnings: list[str]    # continuation/encoding/anomaly flags
```

A **later, separate** projection step maps `CallhomeUtterance` →
`UtteranceRow` (tokens, token language labels, category, condition candidates),
exactly as `bangor_project.py` projects `BangorUtterance`. Source-faithful
parsing and experiment-facing projection stay in different modules, as with
Bangor.

## Likely parsing challenges
- **CHAT / CA-CHAT conventions** on the main tier (CA overlap `[<]`/`[>]`,
  latching, retracing `[/]` `[//]`, pauses) that must be handled or preserved.
- **Continuation lines** (a main/dependent tier wrapped across physical lines,
  typically tab-indented) must be joined before parsing.
- **Dependent tiers** (`%mor`, `%gra`, …) — capture verbatim; decide later which
  are useful (parallels the Bangor `auto` POS discussion).
- **Speaker-code normalization** (`*ABC:` → stable `speaker_id`), and mapping to
  `@Participants` / `@ID` metadata.
- **Timing / media references** (`%snd`, bullets) — optional, capture if present.
- **Disfluencies / transcription markers** — preserve, don't delete (consistent
  with the Bangor "preserve naturalistic input" stance).
- **Spanish encoding / diacritics** — LDC CALLHOME Spanish is ISO-8859-1;
  TalkBank CHAT is typically UTF-8 (`@UTF8`). Confirm per source; normalize.
- **Incidental code-switching / borrowing in Spanish** — CALLHOME Spanish may
  contain English material; a monolingual screen is needed before it is used as
  a clean `SpanishMono` / `MonoCont` baseline.
- **No token-level language labels**: unlike Bangor CG-words, CALLHOME `.cha`
  is not per-word language-tagged, so language is utterance/corpus-level and any
  token labeling would require a **separate screening/labeling step**.

## Safety policy for future ingestion
- Raw CALLHOME archives and transcripts stay under `data/raw/callhome/`
  (and `data/raw/callhome_*/`) and remain **gitignored** (added this PR).
- **No raw transcript excerpts** in committed docs, tests, PR bodies, or terminal
  output.
- Tests use **synthetic `.cha` snippets only** (hand-written, never from
  CALLHOME).
- Committed summaries must be **aggregate-only**, and only after **TalkBank
  ground rules for derived outputs are confirmed** (open item from the access
  verification note).

## Recommendation
Smallest next PR after this one:

- **Option A — implement a synthetic-only CHAT parser scaffold** *(recommended
  first)*: a `.cha` structural parser producing `CallhomeUtterance`, developed
  and tested entirely against **synthetic** `.cha` fixtures, with **no committed
  raw CALLHOME content** and no projection yet. This makes progress without
  depending on access/ground-rule confirmations.
- **Option B — verify TalkBank ground rules for aggregate summaries**: required
  **before** committing any CALLHOME-derived aggregate output; can run in
  parallel with A and **gates** any real-data summary.
- **Option C — local monolingual-screening design**: design the Spanish
  incidental-CS screen; naturally follows once the parser exists.

**Recommendation: Option A first** (synthetic tests only, no raw CALLHOME
committed), with **Option B** pursued in parallel as the gate for any future
real-data aggregate, and **Option C** sequenced after the parser scaffold.
