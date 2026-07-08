# Bangor POS / Probe-Item Plan

## Status
- Branch: bangor-pos-preservation
- This is documentation only.
- No UtteranceRow schema change.
- No model training.
- No full-corpus processing.
- No transcript-bearing outputs.

## Why this matters
POS (part-of-speech) labels may matter for the Declerck **Bilingual Sentence
Superiority Effect (BSSE)** probe, where controlled stimuli may need target-POS
selection or validation. However, POS labels are **not** currently needed for
the model-training condition rows: `UtteranceRow` exists to represent training
conditions (EnglishMono / SpanishMono / MonoCont / CsCont), and none of those
conditions consume POS information today. POS handling is therefore a
probe-side concern, kept out of the training-facing schema for now.

## Audit summary
Safe aggregate audit over the **two-file sample only**
(`herring1_cgwords.tsv`, `herring2_cgwords.tsv`); no transcript rows inspected.

- 13,961 word rows (footer lines excluded).
- `auto`: 12,001 non-empty (86.0%), 1,885 unique values.
- `fix`, `eng`, `com`, `clause`, `clauseno`: empty in this sample.
- `langid`: 13,961 non-empty, 6 unique values.
- `auto` appears to contain **POS + morphosyntactic gloss** information
  (CLAN/MOR-style `lemma.POS.feature...`).
- Full `auto` strings are **lemma/gloss-bearing** and should be treated as
  **sensitive** (the word can be reconstructed from them).
- A **tag-head view is safer**: the lemma prefix (before the first `.`) can be
  stripped, leaving only uppercase POS/feature codes.
- **421** `auto` values contain `[or]` multi-analysis ambiguity.
- Compound / portmanteau heads (e.g. `PREP+DET`, `PRON+BE`) should **not** be
  silently simplified.

(No corpus transcript examples are included in this note by design.)

## Decision
Use **Option C**:
- Do **not** add `token_pos_labels`, `source_token_pos_labels`, or
  `pos_label_scheme` to `UtteranceRow` yet.
- Keep `UtteranceRow` as the training-condition representation.
- Put POS parsing in a future probe / POS utility layer.

Rationale: no information is at risk — `BangorWord.auto` is already preserved
losslessly in the source-faithful layer, so a probe pipeline can parse it later
without reprocessing, and without coupling contested POS decisions into the
training schema.

## Future module proposal
Future module:

    src/cslm/data/bangor_pos.py

Possible API:
- `PosParse` dataclass
- `parse_auto_pos_head(auto: str | None) -> PosParse`
- `parse_auto_pos_sequence(words: list[BangorWord]) -> list[PosParse]`
  (order-aligned with the utterance's tokens)

`PosParse` fields:
- `raw_auto: str | None`
- `pos_head: str | None`
- `pos_features: list[str]`
- `is_empty: bool`
- `is_bare_marker: bool`
- `is_ambiguous: bool`
- `is_compound_head: bool`
- `needs_review_pos: bool`
- `pos_label_scheme: str = "bangor_autoglosser"`

`raw_auto` is lemma-bearing and therefore sensitive; only the tag-only
`pos_head` / `pos_features` views are safe for committed or printed output.

## Parsing policy
Conservative, deterministic rules:
- **empty `auto`** -> empty parse (`is_empty=True`; no review; e.g. punctuation).
- **no dot** (bare marker such as `name` / `unk` / `www`) -> `is_bare_marker=True`,
  `needs_review_pos=True`.
- **contains `[or]`** -> `is_ambiguous=True`, `needs_review_pos=True`; do **not**
  silently resolve the competing analyses.
- **head contains `+`** -> `is_compound_head=True`, preserve the head verbatim,
  `needs_review_pos=True`.
- **simple `lemma.HEAD.feature...`** -> strip the lemma prefix, preserve `HEAD`
  as `pos_head` and the remaining tokens as `pos_features`.

## Future tests
Synthetic inputs only (placeholder stems such as `STEM`, never corpus words):
- empty `auto`.
- bare `name` / `unk` marker.
- `STEM.N.M.PL` -> `pos_head="N"`, features `["M","PL"]`.
- `STEM.PRON.OBL.1S` -> `pos_head="PRON"`.
- `STEM.PREP+DET` -> compound head preserved, `needs_review_pos=True`.
- ambiguous `[or]` -> `is_ambiguous=True`, `needs_review_pos=True`.
- safety test ensuring `pos_head` / `pos_features` do not leak lowercase lemma
  content.

## Future use for Declerck BSSE
- POS parsing can help **select or validate target POS** in controlled probe
  stimuli.
- Bangor POS should **not** be treated as gold labels without human review;
  `needs_review_pos` gates the ambiguous / compound / bare cases.
- POS labels are **not** used for training conditions yet.

## Caveats
- The two-file sample may not reveal populated `fix` / `eng` / `com` / `clause`
  / `clauseno` behavior; they are empty here but may carry data in other files.
- `eng` may contain **translations** in other files and should be re-audited
  before any preservation decision.
- Do **not** commit `raw_auto`-bearing outputs unless they are explicitly
  approved and confirmed safe.
