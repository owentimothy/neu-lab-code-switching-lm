"""First synthetic-only projection scaffold for CALLHOME.

Consumes the source-faithful parser objects from :mod:`cslm.data.callhome_chat`
and produces experiment-facing *projected rows*. This mirrors the Bangor
``bangor_cgwords`` -> ``bangor_project`` split: parsing stays verbatim, and all
derived/experiment-facing decisions live here.

Scope (deliberately minimal; see ``docs/callhome_projection_policy.md``):

* It does **not** tokenize, clean, language-label tokens, or run language ID.
  Screening outcomes are *inputs* to projection, not computed here.
* It emits a CALLHOME-local :class:`CallhomeProjectedRow` rather than
  :class:`cslm.data.schema.UtteranceRow`, because ``UtteranceRow`` requires
  token/count reconciliation that only exists after tokenization (out of scope).
  The row deliberately reuses ``UtteranceRow`` field *vocabulary* so a later PR
  can map it onto the shared schema.

Safety invariants enforced here:

* Provenance is preserved but **de-identified**: raw speaker ids and raw source
  filenames are hashed into opaque references; the raw path never leaks.
* Raw utterance text is retained **in memory only** (``keep_text=True``) for
  future local processing and is **excluded** from :meth:`to_provenance_dict`,
  the only serialization surface here. No transcript-bearing artifact is written.
* Annotation-clean CALLHOME rows may be candidates for an explicit future
  ``CsCont`` monolingual-filler role, but never for generic ``CsCont`` or any
  code-switched-evidence role.
* A filler candidate must also carry its language-matched ``MonoCont`` role.
* Non-clean rows are **never** silently admitted to any condition.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass, field

from cslm.data.callhome_chat import CallhomeTranscript, CallhomeUtterance
from cslm.data.callhome_monolingual_eligibility import (
    CALLHOME_CODE_SWITCHED_EVIDENCE_ROLES,
    CSCONT_ENGLISH_MONOLINGUAL_FILLER_ROLE,
    CSCONT_SPANISH_MONOLINGUAL_FILLER_ROLE,
    ENGLISH_MONO_ROLE,
    MONOCONT_ENGLISH_ROLE,
    MONOCONT_SPANISH_ROLE,
    SPANISH_MONO_ROLE,
)

# Language directories we accept, mapped to a provenance ``source`` tag.
_LANGUAGE_LABEL_TO_SOURCE: dict[str, str] = {
    "eng": "callhome_eng",
    "spa": "callhome_spa",
}

# Screening dispositions from docs/callhome_monolingual_screening.md. ``clean``
# is the only outcome that can make a row condition-eligible; the default is the
# conservative ``needs_review`` so nothing is admitted without an explicit
# screening decision.
SCREENING_OUTCOMES: frozenset[str] = frozenset({"clean", "needs_review", "excluded"})
_DEFAULT_SCREENING_OUTCOME = "needs_review"

# Roles a *clean* CALLHOME row of each source may hold. The explicit CsCont
# roles represent future monolingual-filler candidacy, not selected filler
# membership and never code-switched evidence.
_SOURCE_CLEAN_CONDITIONS: dict[str, tuple[str, ...]] = {
    "callhome_eng": (
        ENGLISH_MONO_ROLE,
        MONOCONT_ENGLISH_ROLE,
        CSCONT_ENGLISH_MONOLINGUAL_FILLER_ROLE,
    ),
    "callhome_spa": (
        SPANISH_MONO_ROLE,
        MONOCONT_SPANISH_ROLE,
        CSCONT_SPANISH_MONOLINGUAL_FILLER_ROLE,
    ),
}

# Historical synthetic callers used the unsplit label ``MonoCont``. Accept it
# when validating old in-memory rows, but canonical projection now emits the
# language-explicit role needed to enforce the filler-subset invariant.
_LEGACY_MONOCONT_ROLE = "MonoCont"
_SOURCE_COMPATIBLE_CONDITIONS: dict[str, frozenset[str]] = {
    source: frozenset((*conditions, _LEGACY_MONOCONT_ROLE))
    for source, conditions in _SOURCE_CLEAN_CONDITIONS.items()
}
_FILLER_REQUIRES_MONOCONT: dict[str, str] = {
    CSCONT_ENGLISH_MONOLINGUAL_FILLER_ROLE: MONOCONT_ENGLISH_ROLE,
    CSCONT_SPANISH_MONOLINGUAL_FILLER_ROLE: MONOCONT_SPANISH_ROLE,
}


def _safe_ref(raw: str, *, prefix: str, salt: str = "") -> str:
    """Hash ``raw`` into an opaque, stable, de-identified reference.

    Same input (within the same salt) always maps to the same reference, so
    provenance/ordering is preserved, but the raw value (speaker code, filename)
    cannot be recovered from the output.
    """
    digest = hashlib.sha1(f"{salt}\x00{raw}".encode()).hexdigest()[:12]
    return f"{prefix}_{digest}"


def callhome_condition_candidates(source: str, screening_outcome: str) -> list[str]:
    """Permitted role candidates for a CALLHOME row, honoring source + screening.

    Only ``clean`` rows are eligible. Their explicit future CsCont role denotes
    monolingual-filler candidacy only; it is coupled to the corresponding
    language-specific MonoCont role. Non-clean rows return ``[]``.
    """
    if source not in _SOURCE_CLEAN_CONDITIONS:
        raise ValueError(f"unknown CALLHOME source: {source!r}")
    if screening_outcome not in SCREENING_OUTCOMES:
        raise ValueError(f"unknown screening_outcome: {screening_outcome!r}")
    if screening_outcome != "clean":
        return []
    return list(_SOURCE_CLEAN_CONDITIONS[source])


def validate_projected_condition_candidates(
    *,
    source: str,
    screening_outcome: str,
    condition_candidates: Iterable[str],
) -> tuple[str, ...]:
    """Validate CALLHOME projection roles without conflating filler and evidence."""
    allowed = _SOURCE_COMPATIBLE_CONDITIONS.get(source)
    if allowed is None:
        raise ValueError(f"unknown CALLHOME source: {source!r}")
    if screening_outcome not in SCREENING_OUTCOMES:
        raise ValueError(f"unknown screening_outcome: {screening_outcome!r}")

    materialized = tuple(condition_candidates)
    if len(materialized) != len(set(materialized)):
        raise ValueError("duplicate CALLHOME condition candidate")
    if screening_outcome != "clean":
        if materialized:
            raise ValueError("non-clean CALLHOME row cannot carry condition candidates")
        return ()

    forbidden_evidence = set(materialized) & CALLHOME_CODE_SWITCHED_EVIDENCE_ROLES
    if forbidden_evidence:
        raise ValueError(
            "CALLHOME row cannot qualify as generic CsCont or code-switched evidence"
        )
    unknown_or_wrong_language = set(materialized) - allowed
    if unknown_or_wrong_language:
        raise ValueError(
            "CALLHOME row has unknown or wrong-language condition candidates"
        )
    for filler_role, required_monocont_role in _FILLER_REQUIRES_MONOCONT.items():
        if filler_role in materialized and required_monocont_role not in materialized:
            raise ValueError(
                "CALLHOME CsCont monolingual-filler candidacy requires the "
                "matching MonoCont role"
            )
    return materialized


@dataclass
class CallhomeProjectedRow:
    """An experiment-facing CALLHOME row (pre-tokenization scaffold).

    Reuses ``UtteranceRow`` field vocabulary where it applies. ``raw_text`` is an
    in-memory-only convenience for future local processing and is never
    serialized by :meth:`to_provenance_dict`.
    """

    source: str  # "callhome_eng" | "callhome_spa"
    conversation_id: str
    turn_index: int
    speaker_ref: str  # de-identified; not the raw CHAT speaker code
    source_file_ref: str  # de-identified; not a raw path/filename
    screening_outcome: str  # one of SCREENING_OUTCOMES
    condition_candidates: list[str] = field(default_factory=list)
    needs_review: bool = False
    # In-memory only; excluded from every serialization surface here.
    raw_text: str | None = None

    def __post_init__(self) -> None:
        validate_projected_condition_candidates(
            source=self.source,
            screening_outcome=self.screening_outcome,
            condition_candidates=self.condition_candidates,
        )

    @property
    def qualifies_as_genuine_code_switched_evidence(self) -> bool:
        """CALLHOME rows never satisfy a code-switched-exposure quota."""
        return False

    def to_provenance_dict(self) -> dict[str, object]:
        """Safe, non-transcript provenance view (no raw text, no raw ids)."""
        return {
            "source": self.source,
            "conversation_id": self.conversation_id,
            "turn_index": self.turn_index,
            "speaker_ref": self.speaker_ref,
            "source_file_ref": self.source_file_ref,
            "screening_outcome": self.screening_outcome,
            "condition_candidates": list(self.condition_candidates),
            "needs_review": self.needs_review,
        }


def project_utterance(
    utterance: CallhomeUtterance,
    *,
    language_label: str,
    screening_outcome: str = _DEFAULT_SCREENING_OUTCOME,
    keep_text: bool = False,
) -> CallhomeProjectedRow:
    """Project one :class:`CallhomeUtterance` into a :class:`CallhomeProjectedRow`.

    ``language_label`` is the source language directory (``"eng"``/``"spa"``).
    ``screening_outcome`` is supplied by the (future) screening step; the default
    ``needs_review`` ensures nothing is admitted without an explicit decision.
    ``keep_text=True`` retains the raw main-tier text in memory only.
    """
    if language_label not in _LANGUAGE_LABEL_TO_SOURCE:
        raise ValueError(f"unknown language_label: {language_label!r}")
    if screening_outcome not in SCREENING_OUTCOMES:
        raise ValueError(f"unknown screening_outcome: {screening_outcome!r}")

    source = _LANGUAGE_LABEL_TO_SOURCE[language_label]
    return CallhomeProjectedRow(
        source=source,
        conversation_id=utterance.conversation_id,
        turn_index=utterance.turn_index,
        speaker_ref=_safe_ref(
            utterance.speaker_id, prefix="spk", salt=utterance.conversation_id
        ),
        source_file_ref=_safe_ref(utterance.source_file, prefix="file"),
        screening_outcome=screening_outcome,
        condition_candidates=callhome_condition_candidates(source, screening_outcome),
        needs_review=(screening_outcome == "needs_review"),
        raw_text=utterance.raw_main_tier_text if keep_text else None,
    )


def project_transcript(
    transcript: CallhomeTranscript,
    *,
    language_label: str,
    screening_by_turn: dict[int, str] | None = None,
    keep_text: bool = False,
) -> list[CallhomeProjectedRow]:
    """Project every utterance in a transcript, preserving order.

    ``screening_by_turn`` optionally maps ``turn_index`` -> screening outcome;
    turns absent from the map default to ``needs_review`` (never auto-admitted).
    """
    screening_by_turn = screening_by_turn or {}
    rows: list[CallhomeProjectedRow] = []
    for utterance in transcript.utterances:
        outcome = screening_by_turn.get(utterance.turn_index, _DEFAULT_SCREENING_OUTCOME)
        rows.append(
            project_utterance(
                utterance,
                language_label=language_label,
                screening_outcome=outcome,
                keep_text=keep_text,
            )
        )
    return rows
