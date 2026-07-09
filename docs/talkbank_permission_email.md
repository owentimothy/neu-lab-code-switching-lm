# TalkBank / CABank Permission Email (Draft)

## Status
- **Email draft only.** No emails are sent by this repo or this PR.
- No parser run on real files; no real CALLHOME-derived outputs produced.
- No committed aggregate manifests or summaries (Decision C still in force).
- No tokenization, monolingual screening, condition datasets, or training.
- Placeholders (**TODO**) are left where the sender must fill in
  institution/identity or confirm exact bibliographic strings — do not guess.

## Purpose
Move from **Decision C** (aggregate-summary permission unclear → do not commit
CALLHOME-derived summaries) toward **Decision B** (commit aggregate-only,
non-transcript summaries with proper citation + license notes), and separately
clarify the training-phase question, by getting explicit written confirmation
from TalkBank / CABank.

See `docs/callhome_ground_rules.md` for the underlying policy review and the
C→B upgrade path this email is meant to trigger.

## Two questions we need answered
1. **Committing derived aggregates.** May **non-transcript, aggregate
   structural / count summaries** derived from CALLHOME (English + Spanish) —
   e.g. file counts, utterance counts, header-key counts, dependent-tier-prefix
   counts, language-composition percentages — be **committed to a public GitHub
   repository**, with TalkBank + LDC citation and a compatible license note,
   under CC BY-NC-SA 3.0? These summaries contain **no transcript text, no
   header values, no participant names, and no speaker IDs**.
2. **Non-commercial research MLM training.** Is **non-commercial academic
   masked-language-model / small research-LM training** on TalkBank transcripts
   (CALLHOME and Bangor Miami) permitted under CC BY-NC-SA 3.0, given the
   license's explicit statement precluding "inclusion of the data in LLMs
   (e.g. ChatGPT)"? We want to distinguish **non-commercial academic research
   training** from **commercial LLM productization**.

## Recipient / route (to confirm before sending)
- **Primary route**: the TalkBank contact / help address listed on
  `https://talkbank.org/` (contact page). Exact address: **TODO — confirm on the
  official site before sending.**
- **CC (optional)**: the CABank maintainers / corpus contacts listed on the
  CABank CallHome corpus pages, if a corpus-specific contact is given.
- Do **not** send to LDC for the TalkBank-route question; LDC terms are a
  separate path (see `docs/callhome_access_verification.md`). If the project
  later uses the LDC-licensed distribution instead, ask LDC separately.

## Draft email

> **Subject:** Permission question — committing aggregate (non-transcript)
> statistics and non-commercial MLM research training for CALLHOME (CABank)

> Dear TalkBank / CABank team,
>
> I am a researcher at the Neuroscience of Multilingualism Lab at NYU working on a
> **non-commercial academic** study of bilingual and code-switched syntax using
> masked language models. We are hoping to use the CABank corpora — **CALLHOME American
> English** and **CALLHOME Spanish** for monolingual conditions, and **Bangor
> Miami** for code-switched data — under CC BY-NC-SA 3.0, with full citation of
> the corpus-specific references and the TalkBank / CABank database citation.
>
> Raw transcripts are kept strictly local and are never redistributed. I have
> two questions about what is permitted:
>
> 1. **Committing derived aggregate statistics.** May we publish, in a public
>    academic code repository (GitHub), **aggregate, non-transcript summaries**
>    computed from these corpora — for example counts of files, utterances, and
>    format markers (CHAT header keys and dependent-tier prefixes), and
>    language-composition percentages? These outputs contain **no transcript
>    text, no header values, no participant names, and no speaker IDs** — only
>    counts and structural markers. We would include the required corpus and
>    database citations and a note that the underlying data is CC BY-NC-SA 3.0.
>    Is committing such aggregate-only derivatives consistent with TalkBank's
>    data-usage rules and the CC BY-NC-SA (attribution / non-commercial /
>    share-alike) terms?
>
> 2. **Non-commercial research model training.** The license text notes that
>    the data may not be included in LLMs such as ChatGPT. We want to confirm
>    the scope of that restriction for **non-commercial academic research**:
>    is training small masked / research language models on these transcripts,
>    purely for a published non-commercial linguistics study (no commercial
>    product, no public model release of the data), a permitted research use?
>    If there are conditions under which such research training is acceptable
>    (e.g. no redistribution of the trained weights, citation, restriction to
>    non-commercial use), we would like to follow them.
>
> We want to be fully compliant before committing any derived output or
> beginning any training, so any guidance — including pointers to existing
> policy we may have missed — is greatly appreciated.
>
> Thank you for maintaining these resources and for your time.
>
> Best regards,
> Timothy Owen
> Research Assistant, NEU Lab @ NYU | tlo5892@nyu.edu

## What we already checked (so we don't ask redundantly)
Per `docs/callhome_ground_rules.md` (official TalkBank policy pages, checked
2026-07-08):
- Non-password CABank data "may be freely distributed"; citation required;
  CALLHOME appears publicly downloadable without login.
- License is **CC BY-NC-SA 3.0**, explicitly non-commercial and share-alike,
  with an explicit clause against including the data in LLMs.
- **Not** explicitly addressed by the written rules: (a) redistribution of
  **derived statistics**, and (b) the boundary between prohibited "LLM
  inclusion" and permitted **non-commercial research training** — which is
  exactly what this email asks.

## What a "yes" unblocks vs. stays blocked
- **Q1 "yes"** → upgrade **Decision C → B**: commit **aggregate-only,
  non-transcript** CALLHOME summaries with TalkBank + LDC citation and a license
  note. Raw transcripts still never committed.
- **Q2 "yes" (with any stated conditions)** → clears the training-phase
  licensing flag for **non-commercial research MLM training**; record the exact
  conditions before the training milestone.
- **Regardless of answers**, still blocked here and unchanged by this PR: no
  committing raw `.cha` / ZIP / transcript excerpts / header values / speaker
  IDs; no condition JSONL; no tokenizer; no training in the current phase.

## Follow-ups once a reply arrives (not done in this PR)
- Record the response verbatim (or summarized) in `docs/callhome_ground_rules.md`
  and update the Decision (C → B) if granted.
- Fill in the still-open **TODO** citation strings (exact CALLHOME English /
  Spanish references, Spanish DOI `10.21415/T51K54`, TalkBank/CABank database
  citn) confirmed against the corpus manuals.
- Only then add a scoped `.gitignore`/commit path for local vs. committable
  CALLHOM-derived aggregates.
