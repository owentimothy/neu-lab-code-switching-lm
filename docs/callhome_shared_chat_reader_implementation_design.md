# Shared TalkBank CHAT Reader — Implementation Design

**Status:** Design only. No code, tests, corpus access, or execution.
**Source decision (fixed upstream):** TalkBank CABank CHAT is the canonical
CALLHOME source distribution for the English and Spanish pilot reader. The LDC
legacy distributions are excluded from the pilot path.
**Reader-format preflight:** complete. R-1 (encoding), R-2 (continuation lines),
and R-3 (warning policy) are resolved and are treated here as fixed invariants,
not open questions.

---

## A. Objective

Provide one shared, reliable TalkBank CHAT reader for **both** English and
Spanish that supplies faithful main-tier utterance text for future construction
of the four local conditions:

```text
EnglishMono   SpanishMono   MonoCont   CsCont
```

The reader is the earliest blocking artifact on the first-pilot path: no
condition dataset can be built until CHAT transcripts can be read faithfully.
Silent encoding corruption or dropped continuation text would alter the actual
model-training data and inject a preprocessing confound directly into the
principal `CsCont − MonoCont` comparison. The reader exists to make that class
of corruption impossible by failing closed instead of guessing.

## B. Non-goals

This gate explicitly excludes:

- corpus access and corpus-content inspection;
- condition sampling; train/validation splitting; dataset freezing;
- tokenizer training; model training; Hunspell or Docker execution;
- a generalized parser framework, plugin system, reader registry, or source
  abstraction;
- configuration-driven or per-call encoding options;
- support for the excluded LDC legacy (ISO-8859-1) format.

## C. Exact implementation scope

Smallest proposed change set — **two files, both already present**:

```text
src/cslm/data/callhome_chat.py      # add strict entry point + shared internals
tests/test_callhome_chat.py         # add synthetic strict-reader tests
```

No third file is justified by inspection. The strict reader reuses the existing
dataclasses (`CallhomeTier`, `CallhomeUtterance`, `CallhomeTranscript`) and the
existing tier-dispatch logic, so no new module, no separate English/Spanish
parser, and no change to consumer signatures is required.

## D. API decision — add one strict entry point, reuse shared internals

**Chosen: option 2** (a new strict production entry point over shared parsing
internals), **not** option 1 (mutating the existing permissive parser in place).

Current public surface of `callhome_chat.py`:

- `parse_chat_lines(lines, *, source_file) -> CallhomeTranscript`
- `parse_chat_file(path) -> CallhomeTranscript` — hard-codes `encoding="utf-8"`,
  records TAB/space continuations as warnings and **drops** their text, never
  requires `@UTF8`, and never rejects BOM or `U+FFFD`.

Consumers and their coupling to permissive behavior:

| Consumer | Uses | Depends on permissive warnings? |
|---|---|---|
| `callhome_project.project_transcript` | transcript/utterance objects | No |
| `callhome_screening.screen_utterance` | `utterance.parser_warnings` (count→bool) | Reads warnings, tolerates zero |
| `callhome_structure_scan.summarize_transcripts` / `scan_directory` | `n_parser_warnings`; **swallows** `OSError/UnicodeDecodeError/ValueError` per file | **Yes** — it is the permissive survey tool |
| `callhome_lexicon_validation`, `english_scowl_coverage` | `utterance.raw_main_tier_text` | No |
| `scripts/dry_run_english_scowl_coverage.py` | `parse_file: Callable = parse_chat_file` injection seam | No (seam already exists) |
| `scripts/summarize_callhome_projection_local.py` | `parse_chat_file(path)` directly | No |

Rationale for option 2: the structure-scan diagnostic exists **specifically** to
complete a permissive survey over messy input and to count warnings. Making the
existing `parse_chat_file` fail closed would silently change that diagnostic's
semantics and regress its tests. Adding a distinct strict entry point:

- gives future dataset construction one fail-closed reader;
- leaves the permissive survey path intact and separately named;
- shares one reconstruction + tier-dispatch implementation, so the two paths can
  never drift into "two readers" with different notions of a main tier.

Proposed new public function (name illustrative, to be finalized in review):

```text
read_chat_transcript(path: str | Path) -> CallhomeTranscript
```

## E. Shared logical-line reconstruction

One shared internal converts physical lines to logical tiers **before** any
filtering, normalization, or tokenization. A `strict` flag selects fail-closed
versus the existing permissive behavior; the reconstruction itself is shared.

```text
reconstruct_logical_lines(physical_lines, *, strict):
    logical = []          # list of (owner_line, [continuation, ...])
    current = None
    for raw in physical_lines:
        line = raw without trailing CR/LF
        if line == "":                      # blank
            if strict: current = None       # blank ends a logical tier
            else:      record permissive warning as today
            continue
        if line starts with TAB:            # continuation
            if current is None:
                fail_closed("orphan continuation")     # strict
                # permissive: record "unmerged continuation" warning, skip
            else:
                current.continuations.append(line without leading TAB)
            continue
        if line[0] in {"@", "*", "%"}:      # new logical tier owner
            current = new_owner(line); logical.append(current)
            continue
        # any other line (incl. space-prefixed continuation-looking line)
        fail_closed("malformed / space-prefixed line")  # strict
        # permissive: record "unknown structural line" warning, skip

    for owner in logical:
        owner.text = join(owner.raw, owner.continuations, sep=" ")  # exactly one U+0020
    return logical

parse_logical_tiers(logical, ...):          # existing dispatch, unchanged
    @  -> header (setdefault list); @Languages seeds nullable language
    *  -> new main tier / CallhomeUtterance (turn_index increments)
    %  -> dependent tier on current utterance; %snd/%mov set media_id
```

Required strict behavior (R-2): a physical TAB begins a continuation; it attaches
to the immediately preceding logical `@`/`*`/`%` tier; joins with **exactly one**
`U+0020`; multiple continuations are allowed; reconstruction happens before tier
filtering; no continuation is ever emitted as an independent object; a
space-prefixed continuation-looking line fails; an orphan continuation fails; any
malformed structure fails.

## F. Strict TalkBank file loading (R-1)

`read_chat_transcript` performs, in order, with no fallback and no retry:

1. read raw **bytes**;
2. reject a UTF-8 BOM (`b"\xef\xbb\xbf"` prefix) → fail closed;
3. one strict `bytes.decode("utf-8")` (strict errors) → decode failure is fail
   closed;
4. reject any literal `U+FFFD` replacement character in the decoded text → fail
   closed;
5. require `@UTF8` as the **first logical line** → otherwise fail closed;
6. no encoding sniffing, no per-call encoding option, no alternate decoder.

## G. Failure model

Proportional to a pilot reader — no container/snapshot/authorization/recovery
machinery.

- No silent file, line, tier, or utterance skipping in the strict path.
- A failed file yields **no** partial transcript object — the function raises
  instead of returning a truncated result.
- Exceptions carry **fixed, non-content** messages. Public error text must not
  contain transcript text, filename, path, conversation ID, speaker ID, line
  number, or byte sequence. (Category is allowed, e.g. "strict UTF-8 decode
  failed"; specifics are not.)
- `KeyboardInterrupt` and `SystemExit` propagate exactly and are never caught,
  wrapped, or reclassified.

For future multi-file dataset construction: the **dataset builder** — not this
low-level parser — owns atomic publication of the final combined output. The
parser reads one file at a time and must not be required to buffer the entire
corpus before yielding.

## H. Traversal boundary

Directory traversal stays **out** of this reader change. This gate is limited to
correctly parsing one file. Multi-file iteration and any per-file
error-aggregation policy belong to the later four-condition dataset builder,
where the atomic-publication and fail-vs-skip policy can be decided together. The
existing `callhome_structure_scan.scan_directory` remains the only traversal
helper and is untouched here. No population authorization is opened by this
design.

## I. Compatibility and migration

- `parse_chat_lines` / `parse_chat_file` keep their current permissive behavior
  and signatures. No existing consumer or test changes in this gate.
- `callhome_structure_scan.scan_directory` still swallows per-file
  `OSError/UnicodeDecodeError/ValueError` to complete its survey. This is the one
  permissive behavior that must remain available **temporarily**. It is named
  here as a migration item: when the dataset builder is written, condition
  construction must use `read_chat_transcript` (fail-closed), and the builder —
  not the survey scanner — decides file-level disposition. This survey path is
  **not** silently broken by the current gate.
- The `parse_file` injection seam in `dry_run_english_scowl_coverage.py` already
  allows a strict reader to be substituted later without a signature change.

## J. Synthetic test matrix

All fixtures use invented content only (`syn_*` tokens, `AAA`/`BBB` speakers) —
no real transcript text. New strict-reader cases:

- **Encoding:** valid UTF-8; accented multibyte characters decode intact;
  invalid UTF-8 bytes fail; missing `@UTF8`; `@UTF8` not first; BOM present
  fails; literal `U+FFFD` fails; no fallback/retry occurs on any failure.
- **Continuations:** one continuation joins with a single space; multiple
  continuations join in order; continuations on main / dependent / header tiers;
  one-space join exactly; punctuation preserved across the join; orphan
  continuation (before any tier) fails; continuation immediately after a blank
  line fails (blank ends the logical tier); space-prefixed continuation-looking
  line fails; malformed tier fails.
- **Tier semantics:** main tier included; dependent/header tiers excluded from
  main-tier utterance text; no continuation emitted as an independent object; no
  main-tier text silently dropped.
- **Failure model:** failures raise fixed, non-sensitive messages containing no
  path/text/id/line/byte; `KeyboardInterrupt` and `SystemExit` propagate exactly.
- **Compatibility:** existing permissive `parse_chat_file` / `parse_chat_lines`
  behavior and warning counts unchanged; existing consumer tests still pass.

## K. Definition of done (for the later implementation gate)

- synthetic tests pass; complete test suite passes; Ruff passes;
- independent review finds no blocking defects;
- code merged and synchronized on `main`;
- no real corpus access occurred; no dataset, tokenizer, or model was created.

## L. Exact next gate

One bounded **implementation** gate changing only:

```text
src/cslm/data/callhome_chat.py
tests/test_callhome_chat.py
```

using **synthetic transcripts only**, adding the strict `read_chat_transcript`
entry point and shared reconstruction internals, with the test matrix in
section J. It opens no corpus, dataset, tokenizer, model, or execution gate.
