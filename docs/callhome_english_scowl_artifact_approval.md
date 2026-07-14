# CALLHOME English SCOWL Artifact Approval Record
## 1. Decision Status
Decision:                         APPROVED FOR FUTURE CONTROLLED PIPELINE USE

Artifact generation:              COMPLETED
Artifact reproducibility:         VERIFIED
Artifact promotion:               COMPLETED
Repository approval:              APPROVED

Loader integration:               CLOSED
CALLHOME validation:              CLOSED
Condition construction:           CLOSED
Tokenizer training:               CLOSED
Model training:                   CLOSED
This document records the approval decision for the locally generated English SCOWL artifact produced through the controlled execution documented in:
docs/callhome_english_scowl_canonical_artifact_build_record.md
The approval applies only to the verified local artifact and does not authorize any downstream pipeline execution.
## 2. Approved Resource
Resource ID:
english_scowl_esdb_en_us

Resource family:
Direct SCOWL / English Speller Database (ESDB)

Upstream:
https://github.com/en-wl/wordlist.git

Release tag:
rel-2026.02.25

Immutable commit:
7e99edab8e32f9f9ea2b15f249ca8d4d67237410

Extraction:
word-list 60 A 1
The approved artifact consists of the locally generated bundle:
scowl_en_US_size60_var1.txt
SCOWL-COPYRIGHT.txt
provenance.json
## 3. Evidence Basis
Approval is based on the following completed checks:
Two independent source checkouts:      PASS
Two independent canonical builds:      PASS
Artifact SHA-256 equality:             PASS
Artifact exact byte identity:           PASS
Aggregate structural checks:            PASS
Notice byte identity:                   PASS
Provenance validation:                  PASS
Atomic local promotion:                 PASS
Final bundle audit:                     PASS
The artifact was not approved based on a single build, manual inspection, or an unverified local output.
## 4. Pipeline Permissions
The artifact may be used only for future controlled pipeline steps.
Approved future use:
English lexicon validation:
YES

EnglishMono candidate validation:
YES (after separate validation implementation)

MonoCont candidate validation:
YES (after separate validation implementation)
Not approved:
CALLHOME content modification:
NO

CALLHOME row promotion:
NO

CsCont construction:
NO

Dataset generation:
NO

Tokenizer training:
NO

Model training:
NO
## 5. Safety and Routing Constraints
The following constraints remain active:
CALLHOME English
→ potentially EnglishMono
→ potentially English portion of MonoCont
→ never CsCont

CALLHOME Spanish
→ separate Spanish resource pipeline
→ never affected by this artifact

Bangor Miami
→ CsCont only
The SCOWL artifact was generated independently of CALLHOME.
CALLHOME-derived material did not influence:
resource selection;
artifact construction;
filtering decisions;
normalization decisions;
artifact contents.
## 6. Repository Boundary
The following remain local and Git-ignored:
Generated lexicon artifact
Preserved notice
Provenance JSON
Full hashes
Build logs
Source checkouts
The repository contains only documentation records describing the controlled process.
## 7. Final Decision
The English SCOWL artifact is:
APPROVED FOR FUTURE CONTROLLED PIPELINE USE
This approval closes the English lexicon-resource selection phase.
The next development phase is:
CALLHOME validation pipeline
        |
        v
Condition dataset construction
        |
        v
Tokenizer training
        |
        v
Small encoder LM training
All downstream gates remain closed until separately implemented and reviewed.
