# CALLHOME Spanish RLA-ES Bundle Execution Safe Stop

## Status

```text
Approved public RLA-ES identity:                    PASS
Two-download controlled acquisition:                PASS
Archive safety and allowlisted extraction:           PASS
Notice preservation boundary:                       PASS
Real dictionary/affix capability audit:              STOP
Pinned Hunspell build:                               NOT RUN
Surface-form generation:                             NOT RUN
Private eleven-file bundle promotion:                NOT RUN
Real CALLHOME or Bangor access:                       NOT RUN
```

This record reports one controlled local execution attempt on 2026-07-16. It
contains only public identities, Git commit IDs, aggregate counts, Booleans, and
fixed safe labels. It contains no lexical entry, affix-rule content, notice text,
resource hash, provenance value, archive listing, unexpected filename, private
log, corpus material, or local path.

The stop is a successful safety result. The real publisher package uses valid
Hunspell structures that exceed the synthetic assumptions of the approved flat
surface-form generation method. The implementation refused to merge, drop, or
reinterpret those structures and promoted no bundle.

## Execution Identity

```text
Execution branch:             spanish-rla-es-bundle-acquisition
Execution runner commit:      8b226743c9aeea2cea1ea8ba3008575d58957023
Approval document commit:     665fa722995ebf0ac3febf51197b03703bc6b83e
Approval merge commit:        74330b0712497f9bb6d00ed2026e66409848d745
RLA-ES release:               v2.9
RLA-ES immutable source:      ea82c1214ead57740798acf66a1e18e5ac874c41
Selected license pathway:     MPL 1.1-or-later
```

The runner began from a clean committed branch. The approved target bundle was
absent before execution and remained absent afterward.

## Plain-Language Result

The package itself was authentic and intact. The obstacle is not a broken
download or a bad Spanish dictionary.

The obstacle is that the real dictionary is more linguistically structured than
the invented test dictionary:

- some affix rules can activate additional affix rules;
- many written base forms have multiple distinct dictionary records; and
- a very small number of entries use shapes the upstream `wordforms` wrapper
  cannot query safely through its regular-expression lookup.

The approved generator had proved only one-layer prefix/suffix behavior over one
record per invented base form. Flattening the newly observed structures would
require a new semantic rule. Silently choosing one record, merging flags, or
ignoring continuation behavior could add or remove Spanish forms. The runner
therefore stopped before building Hunspell or generating a surface list.

## Controlled Attempt Results

```text
Public release/tag/asset identity verified:           true
Controlled source download runs:                      2
Both downloads matched the approved public size:     true
Both downloads were exactly byte-identical:           true
Archive safety checks passed:                         true
Approved extracted member count:                     8
Unexpected archive member count:                     11
Independent extracted bytes were identical:          true
Required notice count:                               6
Required notices preserved without modification:     true
Capability parser accepted real entry structure:      false
Bundle promoted:                                      false
```

The initial command emitted its fixed non-sensitive operational-abort message.
It did not expose the private value that triggered the stop.

## Content-Free Diagnostic Replay

After the safe abort, read-only diagnostic replays localized the failure using
only aggregate counts. Four additional ephemeral retrievals were performed in
fresh temporary workspaces. Together with the controlled attempt, six ephemeral
asset retrievals occurred. Every retrieval passed the same public identity and
size boundary. No retrieved bytes were retained.

### Package and encoding structure

```text
Affix strict UTF-8 parse:                              true
Expected first affix encoding directive:              true
Affix line count:                                    6,994
Dictionary strict UTF-8 parse:                         true
Dictionary header numeric:                            true
Dictionary declared entry count:                    71,198
Dictionary observed entry count:                    71,198
Dictionary declared/observed count equality:          true
Empty dictionary entry count:                            0
```

### Dictionary entry-shape aggregates

```text
Flagged dictionary entry count:                     51,839
Unflagged dictionary entry count:                   19,359
Outer-whitespace entry count:                           12
Whitespace-bearing base-form count:                     14
Multiple-slash entry count:                              1
Empty-flag entry count:                                  0
Empty-base entry count:                                  0
Backslash-bearing entry count:                           0
Regular-expression-sensitive base count:                 2
```

These counts describe structure only. No entry was printed, sampled, recorded,
or committed.

### Repeated-base aggregates

```text
Repeated base-form group count:                      2,572
Extra occurrences beyond one per base:              2,668
Maximum records for one base:                            4
Exact duplicate complete-entry count:                    0
```

The absence of exact duplicate complete entries is important: the repeated base
forms are not simply identical lines that could be removed without judgment.
They carry distinct publisher information. The project has not approved any rule
for merging or selecting among them.

### Affix capability aggregates

```text
Affix rule count:                                    6,865
Blocked-or-unknown directive line count:                 0
Continuation affix rule count:                         189
```

The 189 continuation rules are the decisive mismatch. A continuation rule can
make one generated form eligible for another rule. The approved synthetic proof
covered only one prefix, one suffix, and their direct cross-product. It did not
prove recursive or chained expansion.

## Why Upstream `wordforms` Cannot Be Used Unchanged

The pinned upstream wrapper creates a temporary one-entry dictionary for each
query and locates that query with a regular-expression match. The real package
contains multiple distinct records for many base forms, while the wrapper fixes
the temporary dictionary header at one. It also generates direct prefix/suffix
combinations rather than proving exhaustive continuation chains.

Therefore the project cannot claim that unchanged `wordforms` produces a complete
or semantics-preserving flat RLA-ES surface list. Deduplicating bases, merging
flags, dropping repeated records, or ignoring continuation rules remains
unapproved.

## Filesystem and Privacy Result

```text
Final bundle directory present:                       false
Partial bundle promoted:                              false
Original asset persisted:                             false
Extracted resource persisted:                         false
Generated surface list persisted:                     false
Local provenance created:                             false
Docker/Hunspell generation started:                   false
CALLHOME accessed:                                    false
Bangor accessed:                                      false
Lexical content printed:                              false
Notice or provenance content printed:                 false
Resource hash printed:                                false
Worktree clean after execution:                       true
```

All controlled and diagnostic resource bytes remained in temporary storage and
were removed when their processes ended.

## Scientific Interpretation

This stop does not change the selected broad pan-regional diagnostic role of
RLA-ES. It changes only the proposed execution mechanism.

Coverage remains a lexical diagnostic, not proof that an utterance is
monolingual Spanish. No CALLHOME row was validated, marked `clean`, or routed to
`SpanishMono` or `MonoCont`. CALLHOME remains excluded from `CsCont`, and Bangor
remains `CsCont`-only.

## Gates That Remain Closed

This result does not approve:

- modifying or flattening RLA-ES dictionary records;
- implementing an independent recursive Hunspell expander;
- substituting deprecated `unmunch`;
- direct runtime Hunspell checking over CALLHOME tokens;
- a Spanish coverage adapter or real Spanish coverage run;
- source-language validation or `clean` promotion;
- condition routing, corpus construction, or corpus freezing;
- tokenizer or model training; or
- public redistribution of RLA-ES or a derivative.

## Recommended Next Design Gate

The recommended fallback is a separately reviewed, local-only direct Hunspell
coverage adapter:

1. preserve the publisher `.dic` and `.aff` semantics without flattening them;
2. run pinned Hunspell locally and offline;
3. keep every token-bearing query and response private and temporary;
4. export only fixed aggregate coverage outcomes;
5. prohibit validation, `clean` promotion, routing, and corpus use; and
6. prove the interface first with invented Spanish-like fixtures.

Alternative directions—a new recursively complete expander or a different
pre-expanded Spanish resource—require separate scientific, licensing, and
engineering review.

## Final Gate Result

```text
RLA-ES BUNDLE EXECUTION GATE STOP:
public identity, two-download equality, archive safety, allowlisted extraction,
and notice preservation passed. The real resource contains repeated base records
and continuation-affix behavior outside the approved flat-generation proof. No
bundle was promoted, no corpus was accessed, and no private value was exposed.
```
