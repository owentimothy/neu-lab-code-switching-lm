"""Aggregate-only diagnostics for CALLHOME projected rows.

Summarizes a list of :class:`cslm.data.callhome_project.CallhomeProjectedRow`
into **counts only**. Every output is aggregate and non-transcript: no utterance
text, header values, participant names, speaker ids, or filenames appear here or
in the flattened summary. This is what Decision B permits committing (see
``docs/callhome_ground_rules.md`` / ``docs/callhome_projection_policy.md``).

The module intentionally **writes no files** and exposes **no real-data CLI**;
producing/committing summaries from real (gitignored) rows stays the caller's
local responsibility.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from cslm.data.callhome_monolingual_eligibility import (
    CSCONT_ENGLISH_MONOLINGUAL_FILLER_ROLE,
    CSCONT_SPANISH_MONOLINGUAL_FILLER_ROLE,
    ENGLISH_MONO_ROLE,
    MONOCONT_ENGLISH_ROLE,
    MONOCONT_SPANISH_ROLE,
    SPANISH_MONO_ROLE,
)
from cslm.data.callhome_project import (
    CallhomeProjectedRow,
    validate_projected_condition_candidates,
)

# Ordered tuples (not sets): iteration order fixes the key order of the dicts
# that get serialized to JSON, and frozenset order is not stable across runs.
CALLHOME_SOURCES: tuple[str, ...] = ("callhome_eng", "callhome_spa")
SCREENING_OUTCOMES: tuple[str, ...] = ("clean", "needs_review", "excluded")
# Compatibility aggregate: callers historically consumed one combined MonoCont
# bucket. Canonical rows now carry language-explicit MonoCont roles, which are
# folded back into this stable aggregate view.
MONOLINGUAL_CONDITIONS: tuple[str, ...] = ("EnglishMono", "SpanishMono", "MonoCont")
CSCONT_MONOLINGUAL_FILLER_ROLES: tuple[str, ...] = (
    CSCONT_ENGLISH_MONOLINGUAL_FILLER_ROLE,
    CSCONT_SPANISH_MONOLINGUAL_FILLER_ROLE,
)
_MONOCONT_ROLES: frozenset[str] = frozenset(
    {"MonoCont", MONOCONT_ENGLISH_ROLE, MONOCONT_SPANISH_ROLE}
)


def _check_row_invariants(rows: list[CallhomeProjectedRow]) -> None:
    """Raise on any row that violates CALLHOME projection invariants.

    Guards the aggregate output against malformed rows (e.g. constructed elsewhere
    or mutated after construction): the source and screening outcome must be
    known; explicit language-matched filler candidacy is accepted only with its
    matching MonoCont role, while generic CsCont and evidence roles fail closed.
    """
    for row in rows:
        validate_projected_condition_candidates(
            source=row.source,
            screening_outcome=row.screening_outcome,
            condition_candidates=row.condition_candidates,
        )
        if row.qualifies_as_genuine_code_switched_evidence:
            raise ValueError("CALLHOME row cannot qualify as code-switched evidence")


@dataclass
class CallhomeProjectionSummary:
    """Aggregate, non-transcript summary of projected CALLHOME rows."""

    n_rows: int
    rows_by_source: dict[str, int] = field(default_factory=dict)
    rows_by_screening_outcome: dict[str, int] = field(default_factory=dict)
    # Rows *eligible for* each condition. A clean English row counts toward both
    # EnglishMono and MonoCont, so these buckets overlap by design.
    rows_by_condition_candidate: dict[str, int] = field(default_factory=dict)
    rows_by_cscont_monolingual_filler_candidate: dict[str, int] = field(
        default_factory=dict
    )
    n_cscont_monolingual_filler_candidates: int = 0
    n_callhome_rows_qualified_as_code_switched_evidence: int = 0
    n_needs_review: int = 0
    n_blocked_from_all_conditions: int = 0

    def to_dict(self) -> dict[str, object]:
        """Nested, JSON-compatible view (aggregate counts only)."""
        return {
            "n_rows": self.n_rows,
            "rows_by_source": dict(self.rows_by_source),
            "rows_by_screening_outcome": dict(self.rows_by_screening_outcome),
            "rows_by_condition_candidate": dict(self.rows_by_condition_candidate),
            "rows_by_cscont_monolingual_filler_candidate": dict(
                self.rows_by_cscont_monolingual_filler_candidate
            ),
            "n_cscont_monolingual_filler_candidates": (
                self.n_cscont_monolingual_filler_candidates
            ),
            "n_callhome_rows_qualified_as_code_switched_evidence": (
                self.n_callhome_rows_qualified_as_code_switched_evidence
            ),
            "n_needs_review": self.n_needs_review,
            "n_blocked_from_all_conditions": self.n_blocked_from_all_conditions,
        }


def summarize_projected_rows(
    rows: list[CallhomeProjectedRow],
) -> CallhomeProjectionSummary:
    """Aggregate projected rows into counts, enforcing row invariants first."""
    _check_row_invariants(rows)

    source_counts: Counter[str] = Counter(row.source for row in rows)
    screening_counts: Counter[str] = Counter(row.screening_outcome for row in rows)
    condition_counts: Counter[str] = Counter()
    filler_counts: Counter[str] = Counter()
    for row in rows:
        roles = set(row.condition_candidates)
        if ENGLISH_MONO_ROLE in roles:
            condition_counts[ENGLISH_MONO_ROLE] += 1
        if SPANISH_MONO_ROLE in roles:
            condition_counts[SPANISH_MONO_ROLE] += 1
        if roles & _MONOCONT_ROLES:
            condition_counts["MonoCont"] += 1
        for filler_role in CSCONT_MONOLINGUAL_FILLER_ROLES:
            if filler_role in roles:
                filler_counts[filler_role] += 1

    # Initialize known keys to 0 for stable, complete output, then fill in.
    rows_by_source = {src: source_counts.get(src, 0) for src in CALLHOME_SOURCES}
    rows_by_screening_outcome = {
        outcome: screening_counts.get(outcome, 0) for outcome in SCREENING_OUTCOMES
    }
    rows_by_condition_candidate = {
        cond: condition_counts.get(cond, 0) for cond in MONOLINGUAL_CONDITIONS
    }
    rows_by_cscont_monolingual_filler_candidate = {
        role: filler_counts.get(role, 0)
        for role in CSCONT_MONOLINGUAL_FILLER_ROLES
    }

    return CallhomeProjectionSummary(
        n_rows=len(rows),
        rows_by_source=rows_by_source,
        rows_by_screening_outcome=rows_by_screening_outcome,
        rows_by_condition_candidate=rows_by_condition_candidate,
        rows_by_cscont_monolingual_filler_candidate=(
            rows_by_cscont_monolingual_filler_candidate
        ),
        n_cscont_monolingual_filler_candidates=sum(filler_counts.values()),
        n_callhome_rows_qualified_as_code_switched_evidence=0,
        n_needs_review=sum(1 for row in rows if row.needs_review),
        n_blocked_from_all_conditions=sum(
            1 for row in rows if not row.condition_candidates
        ),
    )


def flatten_projection_summary(
    summary: CallhomeProjectionSummary,
) -> dict[str, int]:
    """Flatten to a single scalar-valued row (aggregate counts only).

    Every value is an ``int`` count; no transcript-bearing field can appear.
    """
    flat: dict[str, int] = {"n_rows": summary.n_rows}
    for src in CALLHOME_SOURCES:
        flat[f"source__{src}"] = summary.rows_by_source.get(src, 0)
    for outcome in SCREENING_OUTCOMES:
        flat[f"screening__{outcome}"] = summary.rows_by_screening_outcome.get(outcome, 0)
    for cond in MONOLINGUAL_CONDITIONS:
        flat[f"condition__{cond}"] = summary.rows_by_condition_candidate.get(cond, 0)
    for role in CSCONT_MONOLINGUAL_FILLER_ROLES:
        flat[f"cscont_monolingual_filler_candidate__{role}"] = (
            summary.rows_by_cscont_monolingual_filler_candidate.get(role, 0)
        )
    flat["n_cscont_monolingual_filler_candidates"] = (
        summary.n_cscont_monolingual_filler_candidates
    )
    flat["n_callhome_rows_qualified_as_code_switched_evidence"] = (
        summary.n_callhome_rows_qualified_as_code_switched_evidence
    )
    flat["n_needs_review"] = summary.n_needs_review
    flat["n_blocked_from_all_conditions"] = summary.n_blocked_from_all_conditions
    return flat
