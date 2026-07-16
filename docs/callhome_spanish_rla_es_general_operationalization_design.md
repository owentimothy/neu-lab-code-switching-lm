# CALLHOME Spanish RLA-ES General Operationalization Design

## Status

```text
Option 4 design direction:                              APPROVED
Pinned RLA-ES resource identity:                       CARRIED FORWARD
Pinned Hunspell candidate identity:                    SELECTED FOR SYNTHETIC REVIEW

Canonical container/environment:                       UNRESOLVED / CLOSED
Synthetic expansion-versus-Hunspell feasibility proof: NOT RUN / CLOSED
License-and-notice pathway:                            UNRESOLVED / CLOSED
Resource download or local placement:                  CLOSED
Canonical Spanish surface-form generation:             CLOSED
Loader or adapter implementation:                      CLOSED
Real Spanish CALLHOME coverage run:                    CLOSED
Source-language validation / clean promotion:          CLOSED
Condition routing / dataset construction:              CLOSED
Tokenizer training / model training / probes:          CLOSED
```

This is a **docs-only design record**. It converts the approved Option 4 direction
into small, fail-closed gates. It does not download, save, extract, hash, build,
load, or run RLA-ES. It does not build Hunspell, create a container, inspect a
lexical entry, access CALLHOME or Bangor, or change any row state.

## Decision Carried Forward

The project will first attempt **controlled surface-form expansion with direct
Hunspell verification**:

```text
Pinned publisher resource
        ↓
Pinned offline Hunspell environment
        ↓
Two independent surface-form generation runs
        ↓
Exact reproducibility and aggregate structural checks
        ↓
Synthetic parity evidence against direct Hunspell
        ↓
Immutable local word set for the existing coverage architecture
```

Direct Hunspell checking during a real CALLHOME run is the fallback only if the
synthetic feasibility gate shows that controlled expansion cannot represent the
required dictionary behavior safely or reproducibly. No fallback activates
automatically.

## Plain-Language Problem

The English SCOWL artifact already lists the forms that the coverage evaluator
compares with transcript tokens. The selected Spanish resource is a Hunspell
package. Its `.dic` file stores base forms plus rule flags, while its `.aff` file
defines how permitted prefixes, suffixes, and related spelling changes work.

Reading only the base forms would make ordinary derived or inflected forms appear
uncovered. Asking a live spell checker about every private transcript token would
represent the publisher's intended behavior more closely, but would add a runtime
dependency and a token-bearing process boundary. Option 4 attempts to do the
linguistic expansion **before** any corpus run, keep the resulting resource local,
and reuse the existing content-free set-membership coverage machinery.

## Fixed Public Identities

### RLA-ES resource

```text
Project:               RLA-ES / Recursos Lingüísticos Abiertos del Español
Release:               v2.9
Immutable source:      ea82c1214ead57740798acf66a1e18e5ac874c41
Publisher-built asset: es.oxt
Selected role:         broad pan-regional coverage diagnostic only
```

These values are carried forward from
`docs/callhome_spanish_rla_es_general_coverage_selection.md`. The general asset
combines the publisher's supported regional vocabularies. It is not a neutral
common core and remains unapproved for source-language validation.

### Hunspell candidate

```text
Project:               hunspell/hunspell
Release:               v1.7.3
Immutable source:      c5f98152a274e25b5107101104bef632b83a0cc9
Release date:          2026-05-05
Candidate generator:   src/tools/wordforms
Direct-check reference: Hunspell spell-checking engine at the same pin
```

The Hunspell identity is selected only for the next **synthetic environment and
feasibility review**. It is not approved for resource generation or real-data
execution until a canonical platform-specific container digest and exact in-image
tool versions are separately inspected and approved.

Public references:

- <https://github.com/sbosio/rla-es/releases/tag/v2.9>
- <https://github.com/sbosio/rla-es/blob/ea82c1214ead57740798acf66a1e18e5ac874c41/herramientas/make_dict.sh>
- <https://github.com/hunspell/hunspell/releases/tag/v1.7.3>
- <https://github.com/hunspell/hunspell/tree/c5f98152a274e25b5107101104bef632b83a0cc9>

## Important Upstream Tool Constraint

The pinned `wordforms` utility is not a one-command, whole-dictionary exporter.
It is a shell wrapper that:

- accepts one query word at a time;
- uses the `.aff` and `.dic` inputs plus the pinned Hunspell executable;
- depends on shell, `grep`, and `awk` behavior;
- uses fixed temporary names under `/tmp`;
- invokes Hunspell to filter generated candidates;
- is installed as a script, not built as a standalone expansion binary.

The upstream README calls `wordforms` the Hunspell replacement for the deprecated
`unmunch` tool. The older `unmunch` implementation is therefore **not** approved
as a silent substitute. Its whole-dictionary convenience does not establish
equivalence with current Hunspell behavior.

Consequences for this project:

- expansion must be single-process and isolated unless a reviewed wrapper removes
  the fixed-temporary-path collision risk;
- host `grep`, `awk`, shell, sort, locale, and Hunspell versions are part of the
  generation identity and must be pinned;
- no claim of full-dictionary equivalence is allowed before synthetic testing;
- no RLA-ES resource may be acquired merely to discover whether the approach
  works; feasibility must be established first with invented fixtures.

## Gate 1 — Canonical Environment Selection

A separate read-only/inspection gate must select one immutable,
platform-specific container image and record:

```text
container repository and human-readable tag
multi-platform index digest (provenance only)
platform-specific image digest (canonical identity)
canonical platform and explicit platform flag
operating system and architecture
shell implementation and version
grep version
awk implementation and version
sort/coreutils version
locale implementation and exact charmap
C/C++ compiler and build-tool versions
Hunspell source tag and commit
observed Hunspell version after the synthetic build
wordforms script identity
```

The environment must support a UTF-8 locale and an offline Hunspell build. Image
inspection may not mount the repository, corpus directories, or private resource
paths. Selecting an image does not prove that expansion is deterministic.

## Gate 2 — Synthetic Feasibility and Parity

This gate occurs before any RLA-ES download. It may use only invented dictionary
stems and invented surface forms in temporary fixtures.

The synthetic fixture set must exercise, at minimum:

- an unflagged base form;
- one prefix rule;
- one suffix rule;
- a cross-product prefix-plus-suffix rule;
- a rule with character removal;
- a rule with a conditional character pattern;
- a form that direct Hunspell rejects;
- an unavailable or malformed `.dic` dependency;
- an unavailable or malformed `.aff` dependency;
- an unsupported rule or flag mode that must stop rather than be ignored.

The feasibility driver must:

1. run only inside the selected offline container;
2. use a fresh private temporary directory rather than shared host `/tmp` state;
3. run the pinned generator serially;
4. include base forms explicitly as well as generated forms;
5. normalize no entry during generation;
6. produce a deterministic UTF-8/LF, bytewise-sorted, unique candidate list;
7. compare the generated set with a bounded, explicitly enumerated expected
   synthetic set;
8. query the pinned Hunspell engine over the same bounded synthetic candidate
   universe;
9. require exact set equality for the supported synthetic behaviors;
10. capture any token-bearing tool output only in temporary synthetic work files;
11. print only aggregate counts, Boolean results, fixed synthetic labels, and
    public tool identities.

Required pass conditions:

```text
two synthetic generation runs are byte-identical              == true
generated set equals expected supported synthetic set         == true
generated supported forms are accepted by direct Hunspell     == true
synthetic rejected forms remain rejected                      == true
unknown/unsupported semantics trigger a closed failure        == true
no real resource or corpus path was accessed                  == true
```

If exact parity fails, the project must stop. It may revise the expansion driver
or open a separate decision comparing direct runtime Hunspell with another
controlled mechanism. It must not weaken the expected synthetic set, omit the
failing rule silently, or proceed to RLA-ES acquisition.

## Gate 3 — License, Notice, and Bundle Approval

Before downloading the publisher asset, a separate decision must finalize:

- which upstream-offered RLA-ES license pathway the project relies on;
- the exact notice and attribution files that must be preserved;
- how the original `es.oxt`, extracted `.dic`/`.aff`, generated wordlist, and
  provenance are stored locally;
- whether every derivative remains local and Git-ignored;
- the exact bundle directory and exact approved public filenames.

Provisional shape only — **not an approved layout**:

```text
data/resources/local_lexicons/spanish/<approved-resource-id>/
  <original publisher asset>
  <extracted dictionary file>
  <extracted affix file>
  <generated surface-form wordlist>
  <required public notice files>
  provenance.json
```

The final bundle must be a non-symlink directory containing only its approved
regular non-symlink files. It must be covered by the existing local-resource Git
ignore boundary. Unexpected filenames are reported only as an aggregate count.

## Gate 4 — Controlled Acquisition and Two Independent Generations

Only after Gates 1–3 are merged may a separately approved execution branch:

1. verify the live v2.9 release identity without changing repository refs;
2. acquire the publisher asset through the approved public URL;
3. preserve the original bytes locally;
4. extract only the approved public files into two separate fresh work areas;
5. verify expected file types, encoding declarations, and package layout without
   printing contents;
6. run two independent offline surface-form generations in separate work areas;
7. compare local SHA-256 values and exact bytes;
8. require byte-for-byte identity;
9. run aggregate structural checks on each generated result;
10. preserve approved notices without rewriting them;
11. assemble the complete candidate bundle in a same-filesystem staging
    directory;
12. create deterministic local provenance;
13. atomically promote the complete bundle only if every check passes.

The two runs may share the same verified input asset and canonical tool identity,
but they must not share temporary directories, generated files, or process state.
Fixed `/tmp` filenames inside one container must never be visible to the other
run.

## Canonical Surface-List Requirements

The eventual generated list must be:

- non-empty;
- strict UTF-8;
- LF-only with one final LF;
- one surface form per line;
- bytewise sorted under the approved fixed locale;
- duplicate-free;
- free of blank entries, NUL bytes, and leading/trailing whitespace;
- generated from the approved `.dic` and `.aff` pair only;
- independent of CALLHOME and Bangor;
- local and Git-ignored.

No rule about digits, hyphens, apostrophes, spaces, names, or regional forms may
be invented during execution. Any such lexical-content policy must be fixed
independently before generation. If the source contains a form the approved
format cannot represent, execution stops rather than silently dropping it.

Structural diagnostics may include only aggregate counts and Booleans. Lexical
entries, first/last entries, samples, failed forms, hashes, notice text,
provenance values, and personal paths must not enter tracked documentation or
external output.

## Runtime Architecture After a Successful Build

If the generated artifact is later approved, runtime coverage should remain
set-based:

```text
approved Spanish local bundle
        ↓ controlled loader
raw frozen surface-form set
        ↓ shared documented normalization, once
prepared immutable membership set
        ↓ already-normalized CALLHOME lexical tokens
content-free coverage outcomes and aggregate counts
```

The coverage counting logic should remain shared with the existing English
coverage implementation rather than being copied. A later code-design gate must
decide whether to extract a language-neutral internal membership core or add a
Spanish evaluator behind the same narrow result contract.

The future Spanish result must still contain counts and a fixed outcome only. It
must not contain tokens, paths, free-form notes, `is_validated`, `clean`, a
condition, or routing eligibility.

## Reproducibility Evidence Required

The eventual provenance must record, locally:

- RLA-ES release, immutable source commit, and public asset identity;
- exact acquired asset identity;
- exact extracted public filenames;
- Hunspell release and immutable source commit;
- canonical platform and platform-specific container digest;
- actual observed tool versions from both runs;
- exact generation-driver identity and command;
- fixed locale, encoding, and sort behavior;
- two independent source/input verification results;
- two build/generation success flags;
- local artifact hashes and exact-byte-identity result;
- aggregate structural results for both outputs and the staged output;
- notice-preservation checks;
- atomic-promotion checks;
- procedure-document commit used for execution.

The provenance remains local and Git-ignored. It contains no lexical entry,
corpus material, or self-hash.

## Privacy and Scientific Boundaries

At every gate:

- CALLHOME may not choose, filter, expand, or tune the Spanish resource;
- Bangor may not influence the monolingual resource and remains `CsCont`-only;
- no transcript text, token, identifier, filename, example, or private log may
  leave the local environment;
- no lexical entry, complete local hash, notice text, provenance value, or
  personal path may be printed or committed;
- only separately reviewed aggregate, non-reconstructive output may enter Git;
- coverage remains a diagnostic and cannot validate, clean, or route a row.

The broad general resource can create more recognition opportunities than a
single regional dictionary. Surface-form expansion increases those opportunities
further by realizing affixed forms. Neither fact is evidence that a recognized
token or covered utterance is monolingual Spanish.

## Approval Matrix

| Gate | Status after this design |
| --- | --- |
| Option 4 design direction | APPROVED |
| RLA-ES v2.9 general resource identity | APPROVED FOR COVERAGE DESIGN ONLY |
| Hunspell v1.7.3 candidate pin | APPROVED FOR SYNTHETIC REVIEW ONLY |
| canonical container/environment | NO / NOT APPROVED |
| synthetic feasibility/parity execution | NO / NOT APPROVED |
| license-and-notice pathway | NO / NOT APPROVED |
| final local bundle layout | NO / NOT APPROVED |
| resource acquisition | NO / NOT APPROVED |
| surface-list generation | NO / NOT APPROVED |
| resource placement or loader use | NO / NOT APPROVED |
| real aggregate Spanish coverage run | NO / NOT APPROVED |
| source-language validation | NO / NOT APPROVED |
| `validated` / `clean` promotion | NO / NOT APPROVED |
| condition routing or dataset construction | NO / NOT APPROVED |
| tokenizer or model training | NO / NOT APPROVED |

## Failure and Stop Conditions

Stop if any step would:

- use unpinned host Hunspell, shell, grep, awk, sort, or locale behavior;
- substitute deprecated `unmunch` without a new decision;
- run `wordforms` concurrently against shared fixed temporary paths;
- assume one-word generation scales or preserves full Hunspell semantics without
  synthetic evidence;
- acquire RLA-ES before environment, synthetic, and notice gates permit it;
- inspect or emit RLA-ES lexical entries;
- drop forms silently because the driver cannot represent them;
- normalize during generation;
- print token-bearing direct-Hunspell output;
- use CALLHOME or Bangor outcomes to change the generator or resource;
- promote a non-reproducible or partially verified bundle;
- validate, clean, route, construct datasets, tokenize, or train.

## Next Approved Step

The next branch is a **canonical Hunspell environment inspection and synthetic
feasibility design/approval**. It may inspect candidate container software and
write invented `.dic`/`.aff` fixtures, but it may not acquire RLA-ES or access
CALLHOME/Bangor.

That gate must resolve whether the pinned `wordforms` wrapper can be used safely
and deterministically at the required scale. A passing result authorizes only the
later license/bundle gate; it does not authorize Spanish resource acquisition or
real-data execution.

## Final Gate Result

```text
OPTION 4 DESIGN PASS:
controlled Spanish surface-form expansion with direct Hunspell verification is
the approved conditional direction. Expansion remains blocked until the pinned
environment and synthetic feasibility/parity gates pass.
```
