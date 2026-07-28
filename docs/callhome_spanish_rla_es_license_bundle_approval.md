# CALLHOME Spanish RLA-ES License, Notice, and Local Bundle Approval

## Status

```text
RLA-ES v2.9 general coverage identity:                   APPROVED / CARRIED FORWARD
Synthetic Hunspell feasibility:                          PASS / CARRIED FORWARD
Project license pathway for spelling resources:          MPL 1.1-OR-LATER / SELECTED
Required local notice set:                               APPROVED
Exact ignored local bundle layout:                       APPROVED

Resource acquisition in this docs branch:                NO / NOT EXECUTED
Surface-form generation in this docs branch:             NO / NOT EXECUTED
Future controlled acquisition/generation branch:         AUTHORIZED AFTER MERGE
Loader or coverage-adapter use:                           CLOSED
Real Spanish CALLHOME coverage run:                       CLOSED
Source-language validation / clean promotion:            CLOSED
Condition routing / dataset construction:                CLOSED
Tokenizer training / model training / probes:            CLOSED
```

This is a **docs-only governance decision**. It selects the project license
pathway, fixes the exact notice set and local bundle layout, and defines the
requirements for a later controlled acquisition/generation branch. It does not
download `es.oxt`, open or extract a package, inspect an RLA-ES lexical entry,
compute a resource hash, create a resource directory, generate a surface form,
load a resource, or access CALLHOME or Bangor.

This record is not legal advice. It records the project's conservative operational
choice from the alternatives the upstream publisher expressly offers. Public
redistribution remains unapproved and requires separate legal/notice review.

## Plain-Language Decision

RLA-ES lets users choose among three licenses for the spelling dictionary. The
project chooses the MPL 1.1-or-later pathway, matching the repository's earlier
working preference. The original package, extracted spelling files, generated
surface list, and every relevant notice will remain together in one private,
Git-ignored bundle.

The choice means:

- the project has one explicit license pathway instead of an unresolved menu;
- the exact upstream declaration and full selected license text travel with the
  extracted and generated spelling artifacts;
- all other license texts embedded in the original package are also preserved for
  package-level provenance and the separately licensed thesaurus context;
- no resource or derivative may be committed or publicly redistributed under this
  approval; and
- a future sharing decision must perform a separate legal and notice review.

## Approved Public Resource Identity

```text
Resource ID:             spanish_rla_es_v2_9_general
Project:                 RLA-ES / Recursos Lingüísticos Abiertos del Español
Release:                 v2.9
Annotated tag object:    c67eae826908d05a8dfabf3f7a012ce280678208
Immutable source commit: ea82c1214ead57740798acf66a1e18e5ac874c41
Publisher asset:         es.oxt
GitHub release asset ID: 217140315
Public asset size:       1,475,270 bytes
Public content type:     application/vnd.openofficeorg.extension
Permitted project role:  broad pan-regional lexical-coverage diagnostic only
```

Canonical public sources:

- <https://github.com/sbosio/rla-es/releases/tag/v2.9>
- <https://github.com/sbosio/rla-es/tree/ea82c1214ead57740798acf66a1e18e5ac874c41>
- <https://github.com/sbosio/rla-es/blob/ea82c1214ead57740798acf66a1e18e5ac874c41/LICENSE.md>
- <https://github.com/sbosio/rla-es/blob/ea82c1214ead57740798acf66a1e18e5ac874c41/herramientas/make_dict.sh>

The human-readable release and asset name are not enough by themselves. A future
execution must verify the live tag, source commit, release asset ID, asset name,
content type, public size, and publisher URL before saving bytes. The asset's
cryptographic identity is verified and stored locally during execution; it is not
printed or committed here.

## License Pathway Decision

The pinned upstream `LICENSE.md` states that the spelling dictionaries are
available under any one of these disjunctive choices:

```text
GNU GPL version 3 or later
GNU LGPL version 3 or later
Mozilla Public License version 1.1 or later
```

The upstream declaration says the user may choose freely. The project selects:

```text
SELECTED PATHWAY: Mozilla Public License version 1.1 or later
```

Reasons for the project-policy choice:

- it is an explicit upstream-offered pathway, not a license inferred by the
  project;
- the pinned v2.9 source contains the complete `MPL-1.1.txt` text;
- the publisher's build procedure copies that text and `LICENSE.md` into the
  built `es.oxt` package;
- it matches the repository's earlier recorded working preference; and
- all artifacts remain local-only, so this decision does not attempt to settle
  public redistribution obligations.

The selected pathway applies to the extracted spelling dictionary, affix rules,
and generated spelling surface-form list for project governance. The generated
list is treated as carrying the same selected pathway and notice mapping as its
source. This is a conservative project rule, not an independent legal conclusion
about derivative-work doctrine.

The upstream declaration separately identifies the synonym/thesaurus dictionary
under LGPL v2.1. This project does not extract, generate from, load, or use the
thesaurus. The original `es.oxt` is nevertheless preserved byte-for-byte, and the
embedded `LGPLv2.1.txt` is preserved separately in the bundle so the original
package's license context remains complete.

## Redistribution Decision

```text
Local download and Git-ignored storage after this approval merges: APPROVED
Local deterministic derivation after this approval merges:         APPROVED
Commit original or extracted resource files:                        NO
Commit generated surface forms:                                    NO
Publicly redistribute original package:                             NO / NOT REVIEWED
Publicly redistribute extracted files:                              NO / NOT REVIEWED
Publicly redistribute generated surface list:                       NO / NOT REVIEWED
```

`NO / NOT REVIEWED` is not a claim that upstream forbids redistribution. It means
this project has not completed the separate legal, source-disclosure, attribution,
and notice review required before sharing. Local-only storage remains the approved
conservative boundary.

## Required Public Notice Files

The pinned build procedure copies `LICENSE.md` plus every file under the upstream
`LICENSE/` directory into `es.oxt`. It also generates the spelling-dictionary
attribution file as `README.txt` from the publisher's template.

The later controlled extraction must preserve these exact root-level package
members byte-for-byte:

```text
LICENSE.md
GPLv3.txt
LGPLv2.1.txt
LGPLv3.txt
MPL-1.1.txt
README.txt
```

No notice content is copied into this tracked record. No notice may be rewritten,
normalized, translated, line-ending-converted, or regenerated locally.

Notice roles:

| File | Local role |
| --- | --- |
| `LICENSE.md` | publisher's disjunctive license declaration and pathway context |
| `MPL-1.1.txt` | full text for the project's selected spelling-resource pathway |
| `README.txt` | spelling-dictionary attribution and publisher/source context |
| `GPLv3.txt` | preserved alternative package license context |
| `LGPLv3.txt` | preserved alternative package license context |
| `LGPLv2.1.txt` | preserved context for the separately licensed thesaurus component in the original package |

Required notice mapping:

| Stored artifact | Required accompanying notices |
| --- | --- |
| original `es.oxt` | original embedded notices, plus all six separately preserved notice files |
| extracted `es.dic` | `LICENSE.md`, `MPL-1.1.txt`, `README.txt` |
| extracted `es.aff` | `LICENSE.md`, `MPL-1.1.txt`, `README.txt` |
| generated surface list | `LICENSE.md`, `MPL-1.1.txt`, `README.txt` |
| local provenance | records the mapping and preservation checks; it does not replace a notice |

If any required member is absent, duplicated, non-regular, encrypted, unsafe to
extract, or fails byte-preservation checks, acquisition stops and no bundle is
promoted.

## Exact Approved Local Bundle

Approved ignored directory:

```text
data/resources/local_lexicons/spanish/spanish_rla_es_v2_9_general/
```

The existing `.gitignore` rule for `data/resources/local_lexicons/` covers this
path. This branch does not create the directory.

The final directory must contain **exactly eleven immediate filesystem entries**:

```text
es.oxt
es.dic
es.aff
rla_es_v2_9_general_surface_forms.txt
LICENSE.md
GPLv3.txt
LGPLv2.1.txt
LGPLv3.txt
MPL-1.1.txt
README.txt
provenance.json
```

Filesystem requirements:

- the bundle path must be a directory and not a symlink;
- every one of the eleven entries must be a regular file and not a symlink;
- no nested directory is permitted in the promoted bundle;
- no twelfth file, temporary file, log, lock file, hidden file, or backup file is
  permitted;
- unexpected local filenames are reported only as an aggregate count;
- the entire directory must remain Git-ignored, untracked, and unstaged; and
- the target must be absent before atomic promotion—no overwrite or merge into an
  existing directory is permitted.

The original `es.oxt` remains intact even though only an allowlisted subset is
extracted. This preserves the publisher artifact independently of the project's
derivative.

## Approved Package Extraction Boundary

The future acquisition branch may inspect the package archive structure only far
enough to enforce safe extraction. It may extract exactly these root-level members:

```text
es.dic
es.aff
LICENSE.md
GPLv3.txt
LGPLv2.1.txt
LGPLv3.txt
MPL-1.1.txt
README.txt
```

It must not extract thesaurus, hyphenation, icons, extension metadata, or any other
package member. It must not print the complete archive listing. Unexpected package
members are expected in the publisher package and may be reported only as one
aggregate count; they are ignored, not extracted.

Before extraction, the implementation must reject:

- duplicate archive member names;
- absolute paths or parent-directory traversal;
- symbolic links, hard links, devices, or other non-regular member types;
- encrypted members;
- a required member that is absent or appears more than once;
- a required member whose uncompressed size violates a separately fixed bound;
- an archive whose aggregate uncompressed size violates a separately fixed bound;
- a declared file encoding that cannot be handled by the approved procedure; or
- any attempt to write outside a fresh private staging directory.

Package inspection and extraction may not print dictionary entries, affix-rule
contents, notice text, hashes, package listings, or local paths.

## Local Provenance Contract

`provenance.json` remains local and Git-ignored. It must use deterministic UTF-8
JSON with sorted keys, two-space indentation, LF line endings, and exactly one
final LF. It must contain no self-hash, lexical entry, corpus material, personal
path, notice text, or private log.

Required field groups:

```text
schema_version
resource_id
resource_role
upstream_project
upstream_release
upstream_tag_object
upstream_source_commit
release_asset_id
release_asset_name
release_asset_url
release_asset_content_type
release_asset_public_size
selected_license_pathway
required_notice_filenames
notice_mapping
container_platform
container_reference
hunspell_release
hunspell_source_commit
generation_runner_commit
character_encoding
sort_locale
source_download_results
source_asset_hashes
source_exact_byte_identity
package_safety_results
extracted_file_hashes
notice_byte_preservation_results
affix_capability_results
generation_run_results
generated_artifact_hashes
generated_exact_byte_identity
aggregate_structural_results
bundle_layout_results
git_ignore_results
atomic_promotion_results
procedure_document_commit
```

Hash values are stored only in this local record. External output and tracked
documentation may state only that hashes were computed and whether required
equalities passed.

## Controlled Acquisition and Generation Procedure

Only after this document is reviewed and merged may a separate execution branch:

1. reconfirm clean synchronized `main` and the merged procedure commit;
2. reconfirm the ignored target path without creating it;
3. verify the live public v2.9 tag, peeled source commit, release asset ID, asset
   name, public size, content type, and publisher URL;
4. download `es.oxt` twice independently into two fresh private work areas;
5. compute local SHA-256 values and require both downloads to match exactly by
   hash and bytes;
6. compare the local asset identity with the live publisher-provided digest when
   available, storing the result locally without printing the digest;
7. validate archive safety and the required allowlisted members independently in
   both work areas;
8. extract only the eight approved members independently from both packages;
9. require exact byte identity for each corresponding extracted file;
10. preserve all six notice files without modification;
11. perform a content-free affix-capability audit before generation;
12. stop if any unsupported flag mode, continuation behavior, affix directive, or
    other unreviewed Hunspell behavior is detected;
13. compile the pinned Hunspell environment through the merged synthetic procedure;
14. generate two independent surface lists in separate network-disabled,
    read-only containers with private temporary filesystems;
15. require both generated lists to match by local SHA-256 and exact bytes;
16. feed the complete generated list back through the same pinned Hunspell build,
    require the aggregate accepted count to equal the generated-entry count, and
    retain any rejected forms only in private temporary storage;
17. require all canonical structural checks;
18. assemble exactly the eleven approved files in a same-filesystem staging
    directory;
19. create and validate deterministic local provenance;
20. recheck notice mapping, ignore coverage, untracked/unstaged state, and target
    absence; and
21. promote the complete staged directory with one atomic rename.

Step 12 is a real stop gate. The future branch may report only an aggregate count
of unsupported capabilities. It may not silently ignore an untested behavior or
weaken the expected semantics. If the count is nonzero, no surface list or bundle
is promoted and a new design decision is required.

## Canonical Generated-List Requirements

The generated `rla_es_v2_9_general_surface_forms.txt` must be:

- non-empty strict UTF-8;
- LF-only with exactly one final LF;
- one surface form per line;
- bytewise sorted with `LC_ALL=C`, independently of the strict UTF-8 encoding
  requirement;
- duplicate-free;
- free of blank entries, NUL bytes, and leading/trailing whitespace;
- produced from only the approved `es.dic` and `es.aff`;
- generated independently twice with identical bytes;
- unmodified by CALLHOME, Bangor, coverage results, or model outcomes; and
- local, Git-ignored, untracked, and unstaged.

Any policy concerning digits, spaces, apostrophes, hyphens, names, or regional
forms must come from the publisher artifact and the already-approved generation
mechanism. The execution branch may not invent a lexical filter. If the canonical
one-entry-per-line format cannot represent a publisher form without modification,
execution stops.

## Safe External Output

The later execution may print only:

- public approved filenames;
- public project/release/tool identities and Git commit IDs;
- aggregate entry, byte, archive-member, and unsupported-capability counts;
- Boolean environment, download, extraction, notice, generation, structural,
  ignore, and promotion results; and
- one final gate result.

It must not print lexical entries, affix-rule contents, notice text, hashes,
provenance values, archive listings, unexpected filenames, local paths, build
logs, corpus material, or per-row results.

## What This Approval Opens

After this decision is merged, a separate execution branch may:

- acquire the exact public `es.oxt` asset locally;
- extract the approved spelling and notice members;
- compute and store local integrity/provenance hashes;
- run the content-free capability audit;
- perform two independent surface-form generations if the capability audit
  passes; and
- atomically promote the complete eleven-file ignored bundle.

## Gates That Remain Closed

This decision does not approve:

- loading the eventual bundle through repository code;
- changing the English coverage evaluator;
- implementing or running a Spanish coverage adapter;
- opening CALLHOME or Bangor during resource generation;
- treating coverage as source-language validation;
- marking any row `validated` or `clean`;
- routing any CALLHOME row into a condition;
- constructing a final corpus or split;
- training a tokenizer or model; or
- public redistribution of any original, extracted, or generated RLA-ES file.

Eligible CALLHOME English and Spanish remain monolingual-source candidates and
may later serve language-matched `CsCont` monolingual filler selected only from
the corresponding `MonoCont` material. They never receive generic `CsCont`
candidacy or qualify as genuine code-switched, mixed-language, or
switching-quota evidence. Bangor remains the primary current source of genuine
code-switched evidence and cannot shape this resource.

## Failure and Stop Conditions

Stop if any step would:

- use a license pathway other than the selected MPL 1.1-or-later pathway without a
  new review;
- omit, rename, rewrite, or normalize a required notice;
- download an asset whose public identity does not match the approved release;
- expose a resource hash or local provenance value;
- extract a non-allowlisted package member;
- follow a symlink or unsafe archive path;
- proceed past unsupported affix behavior;
- produce non-identical independent downloads or generations;
- generate or filter forms using CALLHOME or Bangor evidence;
- create or merge into the final target before every check passes;
- place a partial bundle;
- stage or commit any file under the ignored local resource path;
- load the resource or run Spanish coverage in the acquisition branch;
- validate, clean, route, construct datasets, tokenize, train, or probe; or
- make a public redistribution claim.

## Approval Matrix

| Gate | Status after this decision |
| --- | --- |
| broad RLA-ES v2.9 general coverage identity | APPROVED |
| pinned Hunspell synthetic feasibility | PASS |
| MPL 1.1-or-later project pathway | APPROVED FOR LOCAL SPELLING-RESOURCE USE |
| exact six-file notice set | APPROVED |
| exact eleven-file ignored bundle | APPROVED |
| controlled acquisition/generation execution branch | AUTHORIZED AFTER MERGE |
| current-branch resource download or placement | NO / NOT EXECUTED |
| unsupported real-affix behavior | STOP / NEW DECISION REQUIRED |
| loader implementation or use | NO / NOT APPROVED |
| aggregate Spanish CALLHOME coverage run | NO / NOT APPROVED |
| source-language validation | NO / NOT APPROVED |
| `validated` / `clean` promotion | NO / NOT APPROVED |
| condition routing or corpus construction | NO / NOT APPROVED |
| tokenizer/model/probe execution | NO / NOT APPROVED |
| public redistribution | NO / NOT REVIEWED |

## Next Approved Step

After this docs-only decision is reviewed and merged, the next branch may perform
the controlled local acquisition, two-download verification, allowlisted
extraction, capability audit, two independent surface-form generations, local
provenance construction, and atomic bundle promotion described above.

That execution must stop before loader use or any real CALLHOME/Bangor access.

## Final Gate Result

```text
RLA-ES LICENSE/NOTICE/BUNDLE DESIGN PASS:
MPL 1.1-or-later is the selected local spelling-resource pathway; the six-file
notice set and exact eleven-file ignored bundle are approved. Resource bytes were
not acquired in this branch. A separate controlled acquisition/generation branch
is authorized only after this decision is reviewed and merged.
```
