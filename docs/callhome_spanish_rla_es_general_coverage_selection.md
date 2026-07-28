# CALLHOME Spanish RLA-ES General Coverage Selection

## Status

```text
Research construct for Spanish coverage:                 APPROVED
Resource identity for future coverage design:            APPROVED

Resource download / local placement:                     CLOSED
Canonical extraction or affix expansion:                 CLOSED
Loader or adapter implementation:                        CLOSED
Real Spanish coverage run:                               CLOSED
Source-language validation / clean promotion:            CLOSED
Condition routing / dataset construction:                CLOSED
Tokenizer training / model training / probes:            CLOSED
```

This is a research-policy decision only. It selects an independently published
resource identity for the next **design gate**. It does not download, save,
extract, hash, load, or run that resource. It changes no code and changes no
CALLHOME row state.

## Decision

The project approves the following resource identity for designing a future
Spanish lexical-coverage diagnostic:

```text
Resource family:       RLA-ES (Recursos Lingüísticos Abiertos del Español)
Release:               v2.9
Immutable source:      ea82c1214ead57740798acf66a1e18e5ac874c41
Publisher-built asset: es.oxt
Permitted role:        aggregate lexical-coverage diagnostic only
```

The approved construct is:

> Broad, pan-regional Spanish lexical coverage across the regional vocabularies
> supported by the publisher.

The resource must not be described as a neutral common core or as a model of one
national variety. The upstream build procedure states that the general `es`
dictionary includes every supported localization when no single localization is
selected. The v2.9 release publishes that general dictionary as `es.oxt`.

## Plain-Language Meaning

RLA-ES maintains Spanish spelling dictionaries for many regions. Its general
dictionary combines their vocabulary into one larger list. For this project, it
may eventually answer only:

> How many retained lexical tokens are recognized by this broad Spanish
> spelling resource?

Recognition is not proof that a token or utterance is Spanish. A large combined
dictionary has more opportunities to recognize regional words, but it can also
recognize names, borrowings, or forms that overlap with English. Therefore this
decision supports measurement, not admission into a training corpus.

## Why This Construct Was Selected

CALLHOME Spanish is officially documented as conversations between native
Spanish speakers, with calls audited for language, dialect, and region. The
official description does not define the corpus as one national Spanish
variety. A broad diagnostic therefore avoids using a single national standard as
the initial descriptive measuring instrument.

This reasoning uses only official corpus-level documentation and public upstream
resource documentation. It does not use CALLHOME transcript content, tokens,
unknown-token lists, participant geography, speaker metadata, validation yields,
or coverage results. Bangor Miami did not influence the selection and remains
the primary current source of genuine code-switched evidence for `CsCont`.

## Upstream Evidence

The selection is based on these public upstream facts:

- The RLA-ES README describes the project as supporting Spanish across its major
  regional variants and lists `es` as general/international Spanish.
- The immutable v2.9 build script defines `es` alongside the national variants.
  For the general build, it includes the localization-specific vocabulary from
  all supported regions.
- The official v2.9 release publishes a publisher-built `es.oxt` asset in
  addition to the national-variant assets.
- The v2.9 tag resolves to the immutable source commit recorded above.

Public references:

- <https://github.com/sbosio/rla-es/tree/v2.9>
- <https://github.com/sbosio/rla-es/releases/tag/v2.9>
- <https://github.com/sbosio/rla-es/blob/ea82c1214ead57740798acf66a1e18e5ac874c41/herramientas/make_dict.sh>
- <https://catalog.ldc.upenn.edu/LDC2026S04>

## Scientific Interpretation Boundary

The broad general artifact is appropriate for a first **coverage diagnostic**
because regional breadth is the quantity being described. It is not approved as
a conservative source-language validator.

This decision does not establish that:

- every recognized token is Spanish;
- every fully covered utterance is monolingual Spanish;
- an unrecognized token is not Spanish;
- the general resource is safer than a single variant for row admission;
- a covered row may become `validated` or `clean`;
- a covered row may enter `SpanishMono` or `MonoCont`.

In particular, the all-region construction can increase recognition
opportunities relative to a single national dictionary. Whether that breadth is
acceptable for later validation is a separate scientific decision that remains
closed.

## Technical Boundary

The selected release asset is a packaged Hunspell resource, not the normalized
plain word set consumed by the existing English coverage adapter.

The current generic raw-entry loader does not read Hunspell `.aff` rules or
generate inflected surface forms. Reading only the base entries from the `.dic`
file would therefore answer a narrower and potentially misleading question.
Raw-entry-only use is not approved by this decision.

Before any resource is downloaded or placed, a separate operationalization
design must choose and review one deterministic approach:

1. use a pinned Hunspell implementation for token membership; or
2. generate a canonical surface-form wordlist from the pinned `.dic` and `.aff`
   files in a pinned environment.

That later design must specify the exact extraction procedure, tool and version,
encoding, initialization checks, reproducibility checks, local bundle layout,
notice handling, and failure semantics. It must not inspect CALLHOME or Bangor.

## License, Notice, and Storage Boundary

RLA-ES states a multi-license arrangement. Existing repository documentation
records the available pathways but has not completed the project-specific
license-and-notice approval.

Accordingly:

- no license pathway is finalized here;
- no redistribution conclusion is made here;
- no notice text is copied here;
- no resource file or derived wordlist is placed or committed;
- future full resources and derivatives default to local, Git-ignored storage;
- exact attribution and notice preservation must be approved before placement.

## Privacy and Independence Boundary

No CALLHOME or Bangor content, identifier, filename, token, example, or private
log was inspected or emitted for this decision. No RLA-ES artifact lexical entry
was inspected or printed. No artifact, notice, provenance value, or hash was
saved or computed.

Future resource behavior must remain independent of corpus outcomes. In
particular, the project must not:

- add or remove entries after observing CALLHOME results;
- change normalization to improve apparent retention;
- compare resource alternatives using CALLHOME yields;
- inspect unknown tokens to tune the resource;
- use Bangor outcomes to shape a monolingual resource.

## Approval State

| Gate | Status |
| --- | --- |
| broad pan-regional coverage construct | APPROVED |
| RLA-ES v2.9 general `es.oxt` identity for coverage design | APPROVED |
| validation locale or admission lexicon | NO / NOT APPROVED |
| license-and-notice pathway | NO / NOT APPROVED |
| resource download or local placement | NO / NOT APPROVED |
| canonical extraction / affix handling | NO / NOT APPROVED |
| loader or adapter implementation | NO / NOT APPROVED |
| synthetic execution tests | NO / NOT APPROVED |
| real aggregate Spanish coverage run | NO / NOT APPROVED |
| source-language validation | NO / NOT APPROVED |
| `validated` / `clean` promotion | NO / NOT APPROVED |
| condition routing or dataset construction | NO / NOT APPROVED |
| tokenizer or model training | NO / NOT APPROVED |

## Failure and Stop Conditions

Stop if any proposed next step would:

- treat coverage as source-language validation;
- describe the general artifact as a neutral common core;
- silently use raw `.dic` base entries as full Spanish surface coverage;
- download or place the asset without a reviewed operationalization and notice
  plan;
- choose implementation behavior from CALLHOME or Bangor outcomes;
- print lexical entries, corpus material, identifiers, private paths, hashes,
  notices, provenance values, or private logs;
- mark a row `validated` or `clean`;
- give CALLHOME generic `CsCont` or switching-evidence candidacy, sample future
  CALLHOME filler outside the matching `MonoCont` material, or route Bangor into
  a monolingual condition;
- construct datasets, tokenize, or train.

## Next Approved Step

The next approved step is a **docs-only operationalization design** for turning
the pinned publisher asset into a deterministic, locally controlled Spanish
coverage dependency.

That design must compare pinned Hunspell membership with canonical surface-form
generation, recommend one approach, define a reproducibility protocol analogous
to the English SCOWL resource process, and keep every operational and real-data
gate closed pending separate review.

## Final Gate Result

```text
SPANISH COVERAGE RESOURCE-SELECTION PASS:
RLA-ES v2.9 general es.oxt is selected for future broad coverage design only.
No resource was acquired or used, and no validation or downstream gate opened.
```
