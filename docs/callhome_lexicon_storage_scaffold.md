# CALLHOME Lexicon Storage Scaffold

## Status
- **Storage scaffold only, not resource adoption.** No code changes to the
  validator, no downloads, no lexicon files added, no derived wordlists added, no
  upstream license files added, no long license texts pasted.
- **No resource is adopted, downloaded, committed, loaded, or used.**
- **No clean promotion is enabled.** No condition JSONL construction. No model
  training.
- This PR only (a) ignores a future local resource path and (b) documents the
  storage rule. No `data/resources/local_lexicons/` directory with real contents
  is created.
- No transcript excerpts, tokens, header values, participant names, speaker IDs,
  or filenames appear here.
- Permission state: **Decision B** (see `docs/callhome_ground_rules.md`).

## Purpose
The resource manifest (`docs/callhome_lexicon_resource_manifest.md`) chose a
future local resource path and required that full dictionary files stay
**local / gitignored** until license/notice and approval gates clear. This note
adds the **guardrail** that protects that path from accidental commits, and
records the storage rule — before any resource exists locally.

## Ignored local resource path
- **Path:** `data/resources/local_lexicons/`
- It is added to `.gitignore` in this PR so any future local lexicon files placed
  there are never accidentally committed.
- **No files are added to it in this PR**, and the directory is not created with
  real contents. (Per the manifest, a `.gitkeep` is intentionally **not** added
  inside the ignored directory.)

## What may live there later
Only **after** the license/notice and approval gates are satisfied, the ignored
path may hold **local** copies of:

- **English** SCOWL/LibreOffice `en_US` Hunspell files,
- **Spanish** RLA-ES/LibreOffice Hunspell files,
- **derived normalized wordlists** produced from those dictionaries.

Nothing lives there yet. Placement is a future implementation step, not this PR.

## What must never be committed
- **Full dictionary files** (`.dic` / `.aff`) — stay **local / gitignored** at
  first.
- **Derived wordlists** — stay **local / gitignored** unless a later PR
  **explicitly approves** committing them (with documented license/notice
  treatment).
- **Upstream license files** copied into the repo, or **long license texts**.
- **Any transcript-bearing data** or **real-data token strings**.

Only **aggregate, non-transcript diagnostics** may be committed later (under
Decision B).

## Derived wordlist storage rule
- **Full dictionary files stay local / gitignored at first.**
- **Derived wordlists also stay local / gitignored** unless a later PR explicitly
  approves committing them.
- A derived wordlist inherits the **license/notice obligations** of its source
  dictionary; it is not automatically safe to commit.
- **CALLHOME-derived token lists must never shape, filter, expand, or modify**
  lexicons or derived wordlists.

## Attribution/notice relationship
- **Any local or derived file must be paired with attribution/notice
  documentation before use** — see `docs/callhome_lexicon_attribution_notices.md`
  for the notices to preserve and the future verbatim appendix plan.
- The mapping from each stored/derived file → its required notices must be
  explicit; nothing is used without its notice obligations recorded.

## Diagnostics rule
- Only **aggregate, non-transcript** diagnostics may be committed later (e.g.
  validated vs `not_validated`, method/reason counts, and optional
  coverage/unknown/ambiguous counts).
- **No token strings, source lines, speaker IDs, filenames, or per-row
  transcript-bearing data** may be emitted or committed.

## Interaction with real pipeline
- **This PR does not wire the lexicon validator into the real-data script**
  (`scripts/summarize_callhome_projection_local.py`); it still uses
  `default_source_validation` only.
- **Clean promotion remains disabled**; real CALLHOME behavior is unchanged
  (every row stays `not_validated`; `clean` count stays zero).
- **CALLHOME text must never be uploaded externally.**
- A future positive lexicon validation may permit clean rows to serve their
  language-matched baseline, matching `MonoCont` role, and future
  language-matched `CsCont` monolingual-filler role selected only from that
  `MonoCont` material. CALLHOME never receives generic `CsCont` candidacy or
  qualifies as genuine code-switched, mixed-language, or switching-quota evidence.

## Out of scope
- Adopting, downloading, or loading any resource; adding lexicon, derived-wordlist,
  or license files; creating the resource directory with real contents.
- Implementing a real lexicon loader or wiring the validator into the real-data
  script.
- Exact normalization thresholds and the borrowing/cognate resolution policy.
- **Condition JSONL construction** — remains out of scope.
- Sampling proportions, train/dev/test splitting, tokenizer choice.
- **Model training** — remains out of scope.
- Any Bangor / `CsCont` logic.

## Next steps
1. When a resource is approved for local use, place the licensed files under
   `data/resources/local_lexicons/` (local/gitignored) and record their
   attribution/notice documentation.
2. Keep derived wordlists local/gitignored unless a later PR explicitly approves
   committing them.
3. Proceed only through the resource policy's remaining gates (normalization
   tests → local-only loader scaffold → local-only dry run → aggregate-only
   diagnostics review → explicit approval) before any clean promotion.

Guardrails that hold regardless: **CALLHOME text must never be uploaded
externally**; **CALLHOME-derived token lists must never shape the lexicon or
derived wordlists**; **CALLHOME never receives generic `CsCont` or
switching-evidence candidacy**; and until the gates clear, no real lexicon is
loaded, every CALLHOME row stays `not_validated`, and the `clean` count stays
zero.
