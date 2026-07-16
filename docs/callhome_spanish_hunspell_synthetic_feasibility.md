# CALLHOME Spanish Hunspell Synthetic Feasibility Evidence

## Status

```text
Pinned synthetic container environment:                 VERIFIED / SELECTED
Pinned Hunspell offline build:                           PASS
Invented rule-shape generation:                          PASS
Two independent invented generation runs:               PASS
Direct Hunspell parity over bounded invented universe:   PASS
Bounded repeated-use probe (1,024 invented bases):       PASS
Fail-closed dependency and unsupported-mode checks:      PASS

RLA-ES license-and-notice pathway:                       CLOSED
RLA-ES download or local placement:                      CLOSED
RLA-ES capability inspection or surface generation:      CLOSED
Spanish loader or coverage adapter:                      CLOSED
Real Spanish CALLHOME coverage run:                      CLOSED
Validation, clean promotion, or condition routing:       CLOSED
Corpus, tokenizer, model, or probe work:                 CLOSED
```

This record executes only the synthetic environment and feasibility gates approved
by `docs/callhome_spanish_rla_es_general_operationalization_design.md`. It uses
public Hunspell source code and invented fixtures. It does not acquire, extract,
inspect, hash, load, or generate any RLA-ES resource. It does not access CALLHOME,
Bangor, ignored lexical bundles, private logs, or corpus paths.

## Plain-Language Result

The selected tool chain can be built without network access inside a pinned
container. With a tiny made-up dictionary, the upstream `wordforms` utility
generated the expected prefix, suffix, prefix-plus-suffix, character-removal, and
conditional forms. A separately invoked Hunspell executable accepted exactly the
expected invented forms and rejected the fixed invented negative case.

The complete generation was then repeated in a second fresh container. The two
outputs were byte-for-byte identical. A larger but still invented dictionary with
1,024 flagged bases also produced two identical outputs and exact direct-Hunspell
parity.

This establishes **synthetic feasibility**, not Spanish lexical validity. The real
RLA-ES dictionary may use additional Hunspell directives or flag modes that were
not present in the invented fixture. Such a capability mismatch must stop a future
execution rather than being ignored.

## Public Source Identity

### Hunspell

```text
Project:                 hunspell/hunspell
Release:                 v1.7.3
Immutable source commit: c5f98152a274e25b5107101104bef632b83a0cc9
Official release asset:  hunspell-1.7.3.tar.gz
Release asset identity:  verified against GitHub's public digest
Observed executable:     Hunspell 1.7.3
Installed generator:     wordforms
```

The official release archive was used because it includes the release-generated
`configure` script. The selected base image does not contain `autopoint`, so a raw
Git checkout cannot follow the upstream `autoreconf -vfi` path without installing
another package. Using the official release archive avoids an unpinned package
installation while preserving the selected Hunspell release.

Public references:

- <https://github.com/hunspell/hunspell/releases/tag/v1.7.3>
- <https://github.com/hunspell/hunspell/tree/c5f98152a274e25b5107101104bef632b83a0cc9>

### Container

```text
Repository:                        docker.io/library/buildpack-deps
Human-readable tag:                bookworm (provenance only; mutable)
Multi-platform index digest:       sha256:5bfacbc6611775f980cf283fbc86b999517878d39723510687135a0d6366bbee
Canonical platform:                linux/arm64/v8
Platform-specific canonical digest: sha256:a60c415ba968e9accc8795332295eca29c58968ef95d45616e90e2a5da40f498
```

The platform-specific digest, together with the explicit `linux/arm64` execution
flag, is the canonical container identity. The tag and multi-platform index are
recorded for traceability but are not substitutes for that identity.

## Observed Environment

The following public software identities were observed inside a temporary,
network-disabled container:

```text
architecture:      aarch64
operating system:  Debian GNU/Linux 12
bash:              5.2.15(1)-release
grep:              GNU grep 3.8
awk:               mawk 1.3.4
sort/coreutils:    9.1
locale:            C.UTF-8 (UTF-8 charmap)
gcc:               12.2.0
g++:               12.2.0
GNU Make:          4.3
Hunspell:          1.7.3
wordforms:         installed and executable
```

The locale was set explicitly. The image's default locale was not relied upon.

## Execution Boundary

The tracked runner is:

```text
scripts/run_synthetic_hunspell_feasibility.py
```

It has one opt-in flag and no path, dictionary, corpus, resource, output, subset,
limit, language, or filtering argument. Without the opt-in, it refuses before
downloading source, resolving any data location, or starting Docker.

With the opt-in, it:

1. creates one temporary work area;
2. downloads only the fixed official Hunspell release asset;
3. verifies the asset against the public GitHub digest;
4. safely extracts only regular files and directories;
5. validates the invented fixture before tool execution;
6. pulls the canonical container by platform-specific digest;
7. compiles and installs Hunspell with container networking disabled;
8. verifies the complete expected environment identity;
9. executes each generation run in a separate fresh container;
10. disables networking and drops container capabilities;
11. makes the container root filesystem read-only;
12. gives each run an isolated temporary filesystem;
13. mounts only temporary public-source, invented-fixture, installation, and
    output directories—not the repository or any corpus/resource directory;
14. captures all generated forms and tool diagnostics in temporary files;
15. prints only the fixed aggregate result bundle; and
16. deletes the temporary work area on exit.

The runner adds base forms explicitly because upstream `wordforms` emits derived
forms only. It invokes `wordforms` serially because the upstream script uses fixed
`/tmp/wordforms.aff` and `/tmp/wordforms.dic` names.

## Invented Rule-Shape Probe

The bounded fixture contains six invented bases. It tests:

- an unflagged base form;
- a prefix rule;
- a suffix rule;
- a cross-product prefix-plus-suffix rule;
- a suffix rule that removes one character before adding another;
- a suffix rule with a final-character condition; and
- one fixed rejected form.

Only aggregate results are recorded:

```text
invented base count:                         6
expected generated-set entry count:         13
independent generation runs:                 2
two generated outputs byte-identical:        true
generated output equals expected set:        true
direct Hunspell acceptance equals expected:  true
fixed invented rejected form rejected:       true
```

No invented entry or generated form is printed by the runner. The transparent
invented constants are materialized as dictionary files only in the runner's
temporary work area.

## Bounded Repeated-Use Probe

The scale probe uses 1,024 deterministically invented, safely encoded base forms,
each carrying one simple suffix flag. It is deliberately bounded and does not
claim to reproduce RLA-ES size or rule complexity.

```text
invented base count:                         1,024
expected generated-set entry count:         2,048
independent generation runs:                 2
two generated outputs byte-identical:        true
generated output equals expected set:        true
direct Hunspell acceptance equals expected:  true
```

This shows that repeated serial `wordforms` invocation works deterministically at
the tested bounded scale. It does not prove acceptable runtime at the unknown full
RLA-ES scale. A future controlled execution must report aggregate input size and
completion status and must stop on timeouts or resource exhaustion.

## Fail-Closed Evidence

The runner actively constructed and rejected temporary invented variants for:

```text
missing affix file:                 true
missing dictionary file:            true
malformed affix rule count:         true
malformed dictionary entry count:   true
unsupported flag mode:              true
unsupported affix directive:        true
```

The ordinary unit suite also covers invalid encodings, non-LF input, unsafe entry
characters, undeclared flags, repeated flags, inconsistent expected/candidate
sets, unexpected fixture entries, unsafe tar paths, forbidden CLI arguments,
default refusal, and fixed non-sensitive failure output.

## Aggregate Execution Result

```text
environment identity matched:                 true
offline Hunspell build completed:             true
invented rule-shape generation runs:          2
invented generated entry count:               13
rule-shape outputs byte-identical:             true
rule-shape expected-set match:                 true
rule-shape direct-Hunspell parity:             true
invented rejected form rejected:              true
scale-probe invented base count:               1,024
scale-probe generated entry count:             2,048
scale-probe outputs byte-identical:            true
scale-probe expected-set match:                true
scale-probe direct-Hunspell parity:            true
all dependency/malformed/unsupported checks:   true
real resource or corpus access:                false
```

## What This Proves

- One immutable ARM64 container identity can compile the official Hunspell 1.7.3
  release without network access during the build.
- The compiled Hunspell and installed `wordforms` identities match the approved
  synthetic candidate.
- The isolated serial wrapper represents the required invented prefix, suffix,
  cross-product, strip, and condition behaviors exactly.
- Two independent runs are deterministic for both the rule-shape fixture and the
  bounded repeated-use fixture.
- Direct Hunspell verification agrees with the generated sets over both bounded
  candidate universes.
- Missing, malformed, and unsupported synthetic inputs stop closed.

## What This Does Not Prove

- It does not establish that unseen RLA-ES rules fit the supported capability
  subset.
- It does not establish full-RLA-ES runtime or memory requirements.
- It does not approve a license pathway, notices, bundle layout, acquisition, or
  local resource placement.
- It does not approve a Spanish loader, coverage adapter, or real-data run.
- It does not validate Spanish source language, promote rows, route conditions,
  construct corpora, train a tokenizer, or train a model.

## Decision

```text
SYNTHETIC HUNSPELL FEASIBILITY PASS:
the pinned environment and isolated serial wordforms mechanism are approved as a
conditional candidate for the later controlled RLA-ES generation gate.

The next gate is license, notice, and exact local-bundle approval. RLA-ES
acquisition remains closed until that gate is reviewed and merged.
```
