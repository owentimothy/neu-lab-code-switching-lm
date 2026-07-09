"""Source-language validation scaffold for CALLHOME clean admission.

Per ``docs/callhome_clean_admission_policy.md``, structural cleanliness is
**necessary but not sufficient** for ``clean``: a row may only be promoted to
``clean`` once it also passes **source-language validation** (the load-bearing
"is this row confidently in its source language?" check). Real language ID is
**not** implemented here; this module only provides the *interface* and a
controlled, explicit validation signal for tests / future use.

Everything here is content-free: decisions carry booleans, a language label, and
labels from fixed vocabularies — never transcript text, tokens, or free notes.
Source directory alone (``eng``/``spa``) never implies validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from cslm.data.callhome_screening import (
    SUPPORTED_LANGUAGE_LABELS,
    CallhomeScreeningDecision,
)

# Fixed, safe vocabularies (no transcript-derived content).
VALIDATION_METHODS: frozenset[str] = frozenset({"explicit_override", "not_validated"})
VALIDATION_REASON_CODES: frozenset[str] = frozenset(
    {"explicit_source_validation", "not_validated"}
)

# Screening reason codes that block clean promotion even when a row is
# source-validated. Empty/non-lexical and unsupported-language rows are already
# ``excluded`` upstream, but they are listed here as defense in depth.
_CLEAN_BLOCKING_REASONS: frozenset[str] = frozenset(
    {
        "parser_warning",
        "ambiguous_foreign_material",
        "possible_code_switching",
        "empty_or_nonlexical",
        "unsupported_language_label",
    }
)


@dataclass
class CallhomeSourceValidationDecision:
    """Whether a row has positive source-language validation. Content-free."""

    is_validated: bool
    expected_language: str  # "eng" or "spa"
    validation_method: str  # one of VALIDATION_METHODS
    reason_codes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.expected_language not in SUPPORTED_LANGUAGE_LABELS:
            raise ValueError(f"unsupported expected_language: {self.expected_language!r}")
        if self.validation_method not in VALIDATION_METHODS:
            raise ValueError(f"unknown validation_method: {self.validation_method!r}")
        if not self.reason_codes:
            raise ValueError("reason_codes must not be empty")
        unknown = set(self.reason_codes) - VALIDATION_REASON_CODES
        if unknown:
            raise ValueError(f"unknown validation reason codes: {sorted(unknown)}")
        # The boolean, method, and reason codes must agree.
        if self.is_validated:
            if self.validation_method != "explicit_override":
                raise ValueError(
                    "is_validated=True requires validation_method 'explicit_override'"
                )
            if "explicit_source_validation" not in self.reason_codes:
                raise ValueError(
                    "is_validated=True requires reason code 'explicit_source_validation'"
                )
            if "not_validated" in self.reason_codes:
                raise ValueError("is_validated=True must not include reason 'not_validated'")
        else:
            if self.validation_method != "not_validated":
                raise ValueError(
                    "is_validated=False requires validation_method 'not_validated'"
                )
            if "not_validated" not in self.reason_codes:
                raise ValueError("is_validated=False requires reason code 'not_validated'")
            if "explicit_source_validation" in self.reason_codes:
                raise ValueError(
                    "is_validated=False must not include reason 'explicit_source_validation'"
                )


def default_source_validation(language_label: str) -> CallhomeSourceValidationDecision:
    """The conservative default: **not** source-validated.

    This is the state of every CALLHOME row until real validation exists, so no
    row is promoted to ``clean`` by default.
    """
    if language_label not in SUPPORTED_LANGUAGE_LABELS:
        raise ValueError(f"unsupported language_label: {language_label!r}")
    return CallhomeSourceValidationDecision(
        is_validated=False,
        expected_language=language_label,
        validation_method="not_validated",
        reason_codes=["not_validated"],
    )


def explicit_source_validation(language_label: str) -> CallhomeSourceValidationDecision:
    """A **controlled**, explicit positive validation (tests / future use only).

    This is the deliberate, opt-in signal that a caller asserts a row is
    monolingual in its source language. It is intentionally the *only* way to
    obtain ``is_validated=True`` in this scaffold; no automatic validation exists.
    """
    if language_label not in SUPPORTED_LANGUAGE_LABELS:
        raise ValueError(f"unsupported language_label: {language_label!r}")
    return CallhomeSourceValidationDecision(
        is_validated=True,
        expected_language=language_label,
        validation_method="explicit_override",
        reason_codes=["explicit_source_validation"],
    )


def is_structurally_eligible_for_clean(
    screening_decision: CallhomeScreeningDecision,
) -> bool:
    """True if a screening decision leaves the door open to ``clean``.

    A row is structurally eligible when it is not ``excluded`` and carries no
    clean-blocking review reason (parser warning, possible foreign material /
    code-switching). ``default_unscreened`` is structurally eligible — it is
    exactly the "structurally fine but unvalidated" state.
    """
    if screening_decision.outcome == "excluded":
        return False
    return not any(r in _CLEAN_BLOCKING_REASONS for r in screening_decision.reason_codes)


def combine_screening_and_validation(
    screening_decision: CallhomeScreeningDecision,
    validation: CallhomeSourceValidationDecision,
) -> str:
    """Return the final screening outcome from screening + source validation.

    * ``excluded`` stays ``excluded``.
    * ``clean`` only if structurally eligible **and** source-validated.
    * otherwise ``needs_review`` (structurally eligible but unvalidated, or a
      review reason such as parser_warning / possible_code_switching that
      validation cannot rescue).
    """
    if screening_decision.outcome == "excluded":
        return "excluded"
    if is_structurally_eligible_for_clean(screening_decision) and validation.is_validated:
        return "clean"
    return "needs_review"
