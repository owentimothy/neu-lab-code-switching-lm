"""Aggregate-only diagnostics for CALLHOME source-validation decisions.

Summarizes a list of
:class:`cslm.data.callhome_source_validation.CallhomeSourceValidationDecision`
into **counts only** — by validated status, validation method, and reason code.
Every output is aggregate and non-transcript: no utterance text, tokens, header
values, participant names, speaker ids, filenames, refs, or free notes appear
here. (Validation decisions are content-free by construction, but this module
still emits counts only.)

The module intentionally **writes no files** and exposes **no real-data CLI**.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from cslm.data.callhome_source_validation import (
    VALIDATION_METHODS,
    VALIDATION_REASON_CODES,
    CallhomeSourceValidationDecision,
)

# Ordered tuples (not sets): iteration order fixes serialized key order, and
# frozenset order is not stable across runs. Method/reason orders are asserted
# to cover the authoritative frozensets so drift is caught at import time.
VALIDATED_STATUS_ORDER: tuple[str, ...] = ("validated", "not_validated")
VALIDATION_METHOD_ORDER: tuple[str, ...] = ("explicit_override", "not_validated")
VALIDATION_REASON_CODE_ORDER: tuple[str, ...] = (
    "explicit_source_validation",
    "not_validated",
)

assert set(VALIDATION_METHOD_ORDER) == set(VALIDATION_METHODS), "method order drift"
assert set(VALIDATION_REASON_CODE_ORDER) == set(VALIDATION_REASON_CODES), "reason order drift"


def _check_decision_invariants(
    decisions: list[CallhomeSourceValidationDecision],
) -> None:
    """Raise on any decision with an unknown method or empty/unknown reasons.

    The decision class guards these at construction; re-checking here protects
    the aggregate output from decisions mutated after construction.
    """
    for decision in decisions:
        if decision.validation_method not in VALIDATION_METHODS:
            raise ValueError(f"unknown validation_method: {decision.validation_method!r}")
        if not decision.reason_codes:
            raise ValueError("reason_codes must not be empty")
        unknown = set(decision.reason_codes) - VALIDATION_REASON_CODES
        if unknown:
            raise ValueError(f"unknown validation reason codes: {sorted(unknown)}")
        # Boolean, method, and reason codes must agree (guards mutated decisions).
        if decision.is_validated:
            if decision.validation_method != "explicit_override":
                raise ValueError(
                    "is_validated=True requires validation_method 'explicit_override'"
                )
            if "explicit_source_validation" not in decision.reason_codes:
                raise ValueError(
                    "is_validated=True requires reason code 'explicit_source_validation'"
                )
            if "not_validated" in decision.reason_codes:
                raise ValueError("is_validated=True must not include reason 'not_validated'")
        else:
            if decision.validation_method != "not_validated":
                raise ValueError(
                    "is_validated=False requires validation_method 'not_validated'"
                )
            if "not_validated" not in decision.reason_codes:
                raise ValueError("is_validated=False requires reason code 'not_validated'")
            if "explicit_source_validation" in decision.reason_codes:
                raise ValueError(
                    "is_validated=False must not include reason 'explicit_source_validation'"
                )


@dataclass
class CallhomeSourceValidationSummary:
    """Aggregate, non-transcript summary of source-validation decisions."""

    n_decisions: int
    decisions_by_validated_status: dict[str, int] = field(default_factory=dict)
    decisions_by_validation_method: dict[str, int] = field(default_factory=dict)
    decisions_by_reason_code: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """Nested, JSON-compatible view (aggregate counts only)."""
        return {
            "n_decisions": self.n_decisions,
            "decisions_by_validated_status": dict(self.decisions_by_validated_status),
            "decisions_by_validation_method": dict(self.decisions_by_validation_method),
            "decisions_by_reason_code": dict(self.decisions_by_reason_code),
        }


def summarize_source_validation_decisions(
    decisions: list[CallhomeSourceValidationDecision],
) -> CallhomeSourceValidationSummary:
    """Aggregate validation decisions into counts, enforcing invariants first."""
    _check_decision_invariants(decisions)

    status_counts: Counter[str] = Counter(
        "validated" if d.is_validated else "not_validated" for d in decisions
    )
    method_counts: Counter[str] = Counter(d.validation_method for d in decisions)
    reason_counts: Counter[str] = Counter()
    for decision in decisions:
        reason_counts.update(decision.reason_codes)

    decisions_by_validated_status = {
        status: status_counts.get(status, 0) for status in VALIDATED_STATUS_ORDER
    }
    decisions_by_validation_method = {
        method: method_counts.get(method, 0) for method in VALIDATION_METHOD_ORDER
    }
    decisions_by_reason_code = {
        code: reason_counts.get(code, 0) for code in VALIDATION_REASON_CODE_ORDER
    }

    return CallhomeSourceValidationSummary(
        n_decisions=len(decisions),
        decisions_by_validated_status=decisions_by_validated_status,
        decisions_by_validation_method=decisions_by_validation_method,
        decisions_by_reason_code=decisions_by_reason_code,
    )


def flatten_source_validation_summary(
    summary: CallhomeSourceValidationSummary,
) -> dict[str, int]:
    """Flatten to a single scalar-valued row (aggregate counts only)."""
    flat: dict[str, int] = {"n_decisions": summary.n_decisions}
    for status in VALIDATED_STATUS_ORDER:
        flat[f"status__{status}"] = summary.decisions_by_validated_status.get(status, 0)
    for method in VALIDATION_METHOD_ORDER:
        flat[f"method__{method}"] = summary.decisions_by_validation_method.get(method, 0)
    for code in VALIDATION_REASON_CODE_ORDER:
        flat[f"reason__{code}"] = summary.decisions_by_reason_code.get(code, 0)
    return flat
