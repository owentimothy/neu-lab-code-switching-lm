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
of the four local conditions (`EnglishMono`, `SpanishMono`, `MonoCont`,
`CsCont`).

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
shared tier-dispatch logic, so no new module, no separate English/Spanish
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
| `callhome_structure_scan.summarize_transcripts` / `scan_callhome_transcripts` | `n_parser_warnings`; **swallows** `OSError/UnicodeDecodeError/ValueError` per file | **Yes** — it is the permissive survey tool |
| `callhome_lexicon_validation`, `english_scowl_coverage` | `utterance.raw_main_tier_text` | No |
| `scripts/dry_run_english_scowl_coverage.py` | `parse_file: Callable = parse_chat_file` injection seam | No (seam already exists) |
| `scripts/summarize_callhome_projection_local.py` | `parse_chat_file(path)` directly | No |

Rationale for option 2: the structure-scan diagnostic exists **specifically** to
complete a permissive survey over messy input and to count warnings. Making the
existing `parse_chat_file` fail closed would silently change that diagnostic's
semantics and regress its tests. Adding a distinct strict entry point:

- gives future dataset construction one fail-closed reader;
- leaves the permissive survey path intact and separately named;
- shares only tier **dispatch** (not reconstruction policy), so the two paths
  agree on what a main tier is without collapsing into one ambiguous branch.

Proposed new public function (name illustrative, to be finalized in review):
`read_chat_transcript(path: str | Path) -> CallhomeTranscript`.

## E. Logical-line reconstruction — two separate wrappers

The permissive and strict paths do **not** share one reconstruction algorithm
controlled by an internal `strict` flag. They are two functions that may share
only small content-neutral helpers (e.g. stripping trailing CR/LF); they do not
pretend to implement one identical reconstruction policy.

```text
_reconstruct_permissive_lines(physical_lines)      -> logical tiers  # exact current behavior
_reconstruct_strict_logical_lines(physical_lines)  -> logical tiers  # fail-closed
```

### Permissive path (unchanged — preserves current `parse_chat_lines` semantics)

```text
blank / whitespace-only line          : silently skipped
TAB- or space-prefixed content line   : warning "unmerged continuation line" + text dropped
unknown structural line               : warning "unknown structural line" + dropped
@ / * / % owner                       : dispatched exactly as today
orphan dependent tier (% before main) : warning + skipped
```

The permissive parser never reconstructs continuations — it drops them. This is
verbatim current behavior and must not change in this docs-only gate.

### Strict path

```text
exact empty physical line : ends continuation ownership (current = None)
TAB-prefixed line         : continuation — attach to current owner; orphan (no owner) → abort
space-prefixed line       : malformed → abort (a SPACE-first line is never blank)
@ / * / % owner            : begins a new logical tier owner
any other line            : abort ("unknown structural line")
```

Blank vs. malformed is decided by exact physical emptiness, never
`line.strip() == ""`: a SPACE-only line is malformed, not blank.

### Strict continuation boundary grammar (R-2, exact)

```text
physical continuation line := single leading TAB + payload
after the one required leading TAB:
    payload must NOT begin with TAB or SPACE
    payload must contain at least one non-whitespace character
```

The join is applied **only** at the physical continuation boundary:

```text
owner_fragment := owner_fragment.rstrip(" \t")   # remove only trailing horizontal layout ws
continuation   := line[1:]                        # remove exactly the one required leading TAB
reject if continuation begins with " " or "\t"    # no extra leading horizontal whitespace
reject if continuation.strip() == ""              # empty / whitespace-only payload
joined := owner_fragment + " " + continuation  # exactly one U+0020
```

Invariants: punctuation is never changed; interior whitespace is not normalized;
only the physical continuation boundary is normalized; the output boundary
contains exactly one `U+0020`. No bare `rstrip()` appears anywhere in
reconstruction — only the explicit `rstrip(" \t")` above, whose removed
characters are defined as physical layout whitespace.

### Strict logical-tier validation (R-3 precondition)

Before shared tier dispatch, the strict path validates each reconstructed owner
and aborts on any malformed tier. Malformed tiers — **each aborts the strict
read**:

```text
colonless main tier                        (* line with no ':')
empty main-tier speaker marker             (marker between '*' and ':' is empty)
main tier missing required TAB after colon
colonless dependent tier                   (% line with no ':')
empty dependent-tier marker                (marker between '%' and ':' is empty)
dependent tier missing required TAB after colon
orphan dependent tier                      (% before any main tier)
unknown structural line
```

### Shared tier dispatch (reused after reconstruction)

```text
parse_logical_tiers(logical, ...):   # existing dispatch semantics, reused by both paths
    @ -> header (setdefault list); @Languages seeds nullable language
    * -> new main tier / CallhomeUtterance (turn_index increments)
    % -> dependent tier on current utterance; %snd/%mov set media_id
```

Reusing dispatch keeps both paths agreeing on what a main tier is without making
them share a reconstruction policy.

## F. Strict read pipeline — `read_chat_transcript` (R-1 loading + R-3 enforcement)

`read_chat_transcript(path)` runs, in order, with no fallback and no retry:

1. read raw **bytes**;
2. reject a UTF-8 BOM (`b"\xef\xbb\xbf"` prefix) → abort;
3. one strict `bytes.decode("utf-8")` (strict errors) → decode failure aborts;
4. reject any literal `U+FFFD` replacement character in the decoded text → abort;
5. split the decoded text into physical lines;
6. `_reconstruct_strict_logical_lines(...)` (section E) — build logical lines;
7. require the **first reconstructed logical line** to equal exactly `@UTF8` — no
   trailing colon, no trailing space, no trailing TAB, no continuation payload,
   and it must be first → otherwise abort;
8. strict logical-tier validation (section E) — abort on any malformed tier;
9. shared tier dispatch (section E);
10. **mandatory post-parse assertion (R-3):** `transcript.parser_warnings` must be
    empty **and** every `utterance.parser_warnings` must be empty; otherwise abort
    with a sanitized strict-reader error. No warning-bearing strict transcript is
    ever returned;
11. return the warning-free transcript.

Ordering rationale: BOM / UTF-8 checks (2–4) precede reconstruction because bytes
must decode before any line exists; header equality (7) follows reconstruction
because `@UTF8` is a reconstructed logical line — so a continuation-bearing `@UTF8`
reconstructs to a non-exact header and fails step 7; validation and dispatch (8–9)
run only after header verification.

No encoding sniffing, no per-call encoding option, no alternate decoder. Step 10
closes the R-3 gap: even though tier dispatch is reused, any warning it or
validation could surface becomes an immediate strict failure, so a strict
transcript that reaches the caller is warning-free **by construction**.

## G. Failure model and exception sanitization (R-3)

All strict-path failures raise one dedicated exception,
`StrictChatReaderError(Exception)`, with a closed set of fixed, content-free
messages (category only), e.g.
`"strict CHAT read failed"`, `"strict UTF-8 decode failed"`,
`"CHAT continuation grammar violated"`, `"malformed CHAT tier"`,
`"missing or malformed @UTF8 header"`.

`raise ... from None` alone is insufficient: it hides the *display* of the chain,
but raising inside an active `except` block still sets `__context__` to the caught
exception, which stays reachable and may carry a protected path, bytes, or offset.
The strict reader instead catches in an inner helper, records only a content-free
category (sentinel), exits the handler, then raises `StrictChatReaderError`
**outside** any active exception handler:

```python
def _read_and_decode_strict(path: Path) -> str:
    failure = decoded = None
    try:
        decoded = path.read_bytes().decode("utf-8")  # strict; no fallback
    except Exception:                 # never BaseException
        failure = "strict CHAT read failed"
    if failure is not None:           # raised only after the except block exits
        raise StrictChatReaderError(failure)
    return decoded  # decoded is not None on this path
```

Syntax is illustrative; the required property is that **`StrictChatReaderError` is
raised only after the caught exception handler has exited**, never from inside the
caught `except` block. Rules:

- catch `Exception`, never `BaseException`;
- `KeyboardInterrupt` / `SystemExit` propagate exactly — never caught or wrapped;
- the public exception satisfies both `__cause__ is None` and `__context__ is
  None`, storing no supplied path, original exception, traceback detail, offending
  bytes, filename, or byte offset;
- no filename, path, transcript fragment, speaker, line number, byte offset, or
  byte sequence appears in any public surface — `str`, `repr`, `args`,
  `__cause__`, `__context__`, or anything printed to stdout/stderr;
- filesystem errors (`FileNotFoundError`, `PermissionError`, generic `OSError`)
  convert to a fixed-category `StrictChatReaderError` raised after the handler
  exits, exposing no path.

Precedent for this raise-after-exit pattern (pattern only, not its unrelated
lifecycle machinery): `src/cslm/data/spanish_hunspell_diagnostic.py`.

A failed file yields **no** partial transcript object — the function raises
instead of returning a truncated result. For future multi-file dataset
construction the **dataset builder** — not this low-level parser — owns atomic
publication; the parser reads one file at a time.

## H. Traversal boundary

Directory traversal stays **out** of this reader change: this gate parses one
file. Multi-file iteration and per-file error-aggregation policy belong to the
later four-condition dataset builder, where atomic-publication and fail-vs-skip
policy are decided together. The existing
`callhome_structure_scan.scan_callhome_transcripts` remains the only traversal
helper and is untouched here; no population authorization is opened by this
design.

## I. Compatibility and migration

- `parse_chat_lines` / `parse_chat_file` keep their current permissive behavior
  and signatures. No existing consumer or test changes in this gate.
- `callhome_structure_scan.scan_callhome_transcripts` still swallows per-file
  `OSError/UnicodeDecodeError/ValueError` to complete its survey. This is the one
  permissive behavior that must remain available **temporarily**. It is named
  here as a migration item: when the dataset builder is written, condition
  construction must use `read_chat_transcript` (fail-closed), and the builder —
  not the survey scanner — decides file-level disposition. This survey path is
  **not** silently broken by the current gate.
- The future four-condition **condition builder must use only**
  `read_chat_transcript` and must **never** call the permissive
  `parse_chat_file` / `parse_chat_lines`. When the implementation gate lands,
  this prohibition must be stated in the `callhome_chat.py` module docstring, in
  the `parse_chat_file` / `parse_chat_lines` docstrings (permissive: survey /
  diagnostic use only), and in the `read_chat_transcript` docstring (the sole
  reader for condition construction).
- The `parse_file` injection seam in `dry_run_english_scowl_coverage.py` already
  allows a strict reader to be substituted later without a signature change.

## J. Synthetic test matrix

All fixtures use invented content only (`syn_*` tokens, `AAA`/`BBB` speakers,
unique sentinel strings for the privacy tests) — no real transcript text.

### Encoding / `@UTF8` header exactness

- valid UTF-8; accented multibyte characters decode intact; invalid UTF-8 bytes
  abort; BOM present aborts; literal `U+FFFD` aborts; no fallback/retry on any
  failure;
- `@UTF8` acceptance is exact equality of the **first reconstructed logical line**
  with `@UTF8`, checked after reconstruction. Reject each of: `@UTF8:`, `@UTF8 `
  (trailing space), `@UTF8<TAB>`, continuation-bearing `@UTF8` (reconstructs to a
  non-exact header), `@UTF8` not the first logical line, and missing `@UTF8`.

### Tier structure (every warning-producing legacy condition becomes a strict abort)

- orphan dependent tier; colonless main tier; empty main-tier speaker marker;
  main tier missing TAB; colonless dependent tier; empty dependent-tier marker;
  dependent tier missing TAB; unknown structural line.

### Continuation boundaries

- owner ends with SPACE; owner ends with TAB (both: single `U+0020` at the
  boundary, no doubling); continuation begins TAB+SPACE+text → abort;
  continuation begins TAB+TAB+text → abort; TAB-only continuation → abort;
  TAB + spaces-only continuation → abort; valid TAB + text → joins with exactly
  one `U+0020`; multiple continuations join in order; punctuation preserved
  across the join; interior whitespace not normalized.
- **SPACE-only physical line** (one or more spaces, no other content) → strict
  abort with sanitized `StrictChatReaderError`; malformed space-prefixed line, must
  **not** be classified blank via `line.strip() == ""`.
- **exact empty physical line ends ownership**: valid owner line, then an exact
  empty physical line, then a TAB-prefixed continuation → the empty line ends
  ownership, the continuation is orphaned, and the strict read aborts (ownership
  never survives an exact blank physical line).

### Failure privacy (all surfaces)

Inject a unique sentinel into each of: path, filename, transcript text, speaker
marker, invalid byte payload; then assert the sentinel appears in **none** of:
`str(exc)`, `repr(exc)`, `exc.args`, `exc.__cause__`, `exc.__context__`, stdout,
stderr.

### Filesystem failures (synthetic / mocked)

- missing file (`FileNotFoundError`); permission failure (`PermissionError`);
  generic `OSError` — each raises a fixed sanitized `StrictChatReaderError`
  exposing no path.

### Compatibility (behavior parity, unchanged legacy)

- permissive TAB/space continuation still: warning + dropped text;
- permissive blank line still: silently skipped;
- permissive unknown structural line still: warning + dropped;
- existing permissive warning counts and consumer tests unchanged;
- the same inputs on the strict path abort or reconstruct per the strict rules
  above.

## K. Definition of done (for the later implementation gate)

- synthetic tests pass; complete test suite passes; Ruff passes;
- independent review finds no blocking defects;
- code merged and synchronized on `main`;
- no real corpus access occurred; no dataset, tokenizer, or model was created.

## L. Exact next gate

One bounded **implementation** gate changing only `src/cslm/data/callhome_chat.py`
and `tests/test_callhome_chat.py`, using **synthetic transcripts only**, adding
the strict `read_chat_transcript`
entry point, the separate `_reconstruct_strict_logical_lines` reconstruction,
strict logical-tier validation, the `StrictChatReaderError` contract, and the
post-parse warning assertion, with the test matrix in section J. It opens no
corpus, dataset, tokenizer, model, or execution gate.
