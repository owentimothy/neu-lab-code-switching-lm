"""Annotation-based monolingual eligibility for frozen CALLHOME rows.

The evaluator is deliberately narrow. It uses approved CALLHOME source identity,
strict-reader metadata, and explicit CHAT language precodes before surface
cleaning. It does not infer language from cleaned text, use a lexicon or model,
or claim word-by-word monolinguality.

Real-data use is a later, separately authorized gate. This module is side-effect
free and returns only decisions or aggregate diagnostics.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Iterable

from cslm.data.callhome_chat import CallhomeTranscript, CallhomeUtterance
from cslm.data.callhome_training_rows import (
    SOURCE_TO_LANGUAGE,
    CallhomeTrainingRow,
    rows_from_transcript,
)

ELIGIBLE_ANNOTATION_CLEAN = "eligible_annotation_clean"
EXPLICIT_NONEXPECTED_LANGUAGE = "explicit_nonexpected_language"
EXPLICIT_MIXED_LANGUAGE = "explicit_mixed_language"
EXPLICIT_LANGUAGE_AMBIGUITY = "explicit_language_ambiguity"
CONFLICTING_LANGUAGE_ANNOTATION = "conflicting_language_annotation"

EXCLUSION_REASON_ORDER: tuple[str, ...] = (
    EXPLICIT_NONEXPECTED_LANGUAGE,
    EXPLICIT_MIXED_LANGUAGE,
    EXPLICIT_LANGUAGE_AMBIGUITY,
    CONFLICTING_LANGUAGE_ANNOTATION,
)
SPLIT_ORDER: tuple[str, ...] = ("train", "validation", "test")
SOURCE_ORDER: tuple[str, ...] = ("callhome_eng", "callhome_spa")

ERROR_UNKNOWN_LANGUAGE_CONTROL = "unknown or malformed CHAT language control"
ERROR_RECONCILIATION = "CALLHOME frozen-row reconciliation failed"
ERROR_DUPLICATE_RECONCILIATION = "duplicate CALLHOME frozen-row reconciliation"
ERROR_SOURCE_DISAGREEMENT = "CALLHOME source disagreement"
ERROR_SPLIT_DISAGREEMENT = "CALLHOME split disagreement"
ERROR_PROVENANCE_DISAGREEMENT = "CALLHOME provenance disagreement"
ERROR_ROUTING_INVARIANT = "CALLHOME condition-routing invariant violated"

# ``[- ...]`` is the only structured language-bearing main-tier control whose
# semantics are represented in the tracked CALLHOME cleaner. Generic postcodes,
# uncertainty, replacement, explanation, timing, event, and repair controls are
# intentionally not language evidence here.
_ANY_LANGUAGE_PRECODE = re.compile(r"\[\s*-[^\[\]]*\]")
_LANGUAGE_PRECODE = re.compile(r"\[-[ \t]+([^ \t\[\]][^\[\]]*?)\]")
_LANGUAGE_LIST = re.compile(r"[A-Za-z]{3}(?:[ \t]*,[ \t]*[A-Za-z]{3})*")
_KNOWN_LANGUAGE_CODES = frozenset({"eng", "spa", "mul", "und"})


class CallhomeEligibilityError(Exception):
    """Fixed-category failure with no corpus-bearing detail."""


@dataclass(frozen=True)
class CallhomeEligibilityDecision:
    """Content-free eligibility result for one source utterance."""

    category: str
    exclusion_reason: str | None = None

    def __post_init__(self) -> None:
        if self.category == ELIGIBLE_ANNOTATION_CLEAN:
            if self.exclusion_reason is not None:
                raise ValueError("eligible decision cannot carry an exclusion reason")
            return
        if self.category != "excluded":
            raise ValueError("unknown eligibility category")
        if self.exclusion_reason not in EXCLUSION_REASON_ORDER:
            raise ValueError("unknown exclusion reason")

    @property
    def is_eligible(self) -> bool:
        return self.category == ELIGIBLE_ANNOTATION_CLEAN


@dataclass(frozen=True)
class ReconciledEligibility:
    """One in-memory frozen row paired with its content-free decision."""

    row: CallhomeTrainingRow
    decision: CallhomeEligibilityDecision


def _language_precode_payloads(text: str) -> tuple[tuple[str, ...] | str, ...]:
    """Return parsed language precode payloads, failing on unknown structure."""
    candidates = tuple(_ANY_LANGUAGE_PRECODE.finditer(text))
    parsed: list[tuple[str, ...] | str] = []
    for candidate in candidates:
        matched = _LANGUAGE_PRECODE.fullmatch(candidate.group(0))
        if matched is None:
            raise CallhomeEligibilityError(ERROR_UNKNOWN_LANGUAGE_CONTROL)
        payload = matched.group(1).strip().lower()
        if payload in {"?", "und"}:
            parsed.append("ambiguous")
            continue
        if not _LANGUAGE_LIST.fullmatch(payload):
            raise CallhomeEligibilityError(ERROR_UNKNOWN_LANGUAGE_CONTROL)
        languages = tuple(
            part.strip().lower() for part in payload.split(",")
        )
        if len(languages) != len(set(languages)):
            raise CallhomeEligibilityError(ERROR_UNKNOWN_LANGUAGE_CONTROL)
        if any(language not in _KNOWN_LANGUAGE_CODES for language in languages):
            raise CallhomeEligibilityError(ERROR_UNKNOWN_LANGUAGE_CONTROL)
        parsed.append(languages)
    return tuple(parsed)


def evaluate_utterance_annotation_eligibility(
    utterance: CallhomeUtterance,
    *,
    source: str,
) -> CallhomeEligibilityDecision:
    """Classify one strict-reader utterance from structured annotation evidence."""
    expected_language = SOURCE_TO_LANGUAGE.get(source)
    if expected_language is None:
        raise CallhomeEligibilityError(ERROR_SOURCE_DISAGREEMENT)
    if utterance.language != expected_language:
        raise CallhomeEligibilityError(ERROR_SOURCE_DISAGREEMENT)

    markers = _language_precode_payloads(utterance.raw_main_tier_text)
    if not markers:
        return CallhomeEligibilityDecision(ELIGIBLE_ANNOTATION_CLEAN)
    if len(markers) > 1:
        return CallhomeEligibilityDecision(
            "excluded",
            CONFLICTING_LANGUAGE_ANNOTATION,
        )

    marker = markers[0]
    if marker == "ambiguous":
        return CallhomeEligibilityDecision(
            "excluded",
            EXPLICIT_LANGUAGE_AMBIGUITY,
        )
    assert isinstance(marker, tuple)
    if "mul" in marker or len(marker) > 1:
        return CallhomeEligibilityDecision(
            "excluded",
            EXPLICIT_MIXED_LANGUAGE,
        )
    if marker[0] != expected_language:
        return CallhomeEligibilityDecision(
            "excluded",
            EXPLICIT_NONEXPECTED_LANGUAGE,
        )
    return CallhomeEligibilityDecision(ELIGIBLE_ANNOTATION_CLEAN)


def condition_candidates(
    *,
    source: str,
    decision: CallhomeEligibilityDecision,
) -> tuple[str, ...]:
    """Return the shared source inventory's allowed monolingual conditions."""
    if source == "callhome_eng":
        candidates = ("EnglishMono", "MonoCont-English")
    elif source == "callhome_spa":
        candidates = ("SpanishMono", "MonoCont-Spanish")
    else:
        raise CallhomeEligibilityError(ERROR_ROUTING_INVARIANT)
    if not decision.is_eligible:
        return ()
    if "CsCont" in candidates:
        raise CallhomeEligibilityError(ERROR_ROUTING_INVARIANT)
    return candidates


def _expected_rows_and_decisions(
    transcripts_by_source: dict[str, Iterable[CallhomeTranscript]],
) -> tuple[
    dict[str, CallhomeTrainingRow],
    dict[str, CallhomeEligibilityDecision],
]:
    expected_rows: dict[str, CallhomeTrainingRow] = {}
    decisions: dict[str, CallhomeEligibilityDecision] = {}
    for source in SOURCE_ORDER:
        for transcript in transcripts_by_source.get(source, ()):
            projected_rows, _ = rows_from_transcript(transcript, source=source)
            utterances_by_turn = {
                utterance.turn_index: utterance for utterance in transcript.utterances
            }
            for row in projected_rows:
                if row.row_id in expected_rows:
                    raise CallhomeEligibilityError(
                        ERROR_DUPLICATE_RECONCILIATION
                    )
                utterance = utterances_by_turn.get(row.turn_index)
                if utterance is None:
                    raise CallhomeEligibilityError(ERROR_RECONCILIATION)
                expected_rows[row.row_id] = row
                decisions[row.row_id] = evaluate_utterance_annotation_eligibility(
                    utterance,
                    source=source,
                )
    extra_sources = set(transcripts_by_source) - set(SOURCE_ORDER)
    if extra_sources:
        raise CallhomeEligibilityError(ERROR_SOURCE_DISAGREEMENT)
    return expected_rows, decisions


def reconcile_frozen_rows(
    transcripts_by_source: dict[str, Iterable[CallhomeTranscript]],
    frozen_rows: Iterable[CallhomeTrainingRow],
    *,
    canonical_splits_by_row_id: Mapping[str, str],
) -> tuple[ReconciledEligibility, ...]:
    """Reconcile strict-reader utterances to frozen rows exactly once."""
    expected_rows, decisions = _expected_rows_and_decisions(transcripts_by_source)
    frozen_by_id: dict[str, CallhomeTrainingRow] = {}
    splits_by_conversation: dict[tuple[str, str], set[str | None]] = defaultdict(set)
    for row in frozen_rows:
        if row.row_id in frozen_by_id:
            raise CallhomeEligibilityError(ERROR_DUPLICATE_RECONCILIATION)
        frozen_by_id[row.row_id] = row
        splits_by_conversation[(row.source, row.conversation_ref)].add(row.split)

    if set(expected_rows) != set(frozen_by_id):
        raise CallhomeEligibilityError(ERROR_RECONCILIATION)
    if set(canonical_splits_by_row_id) != set(frozen_by_id):
        raise CallhomeEligibilityError(ERROR_RECONCILIATION)
    if any(
        len(splits) != 1 or next(iter(splits)) not in SPLIT_ORDER
        for splits in splits_by_conversation.values()
    ):
        raise CallhomeEligibilityError(ERROR_SPLIT_DISAGREEMENT)

    reconciled: list[ReconciledEligibility] = []
    for row_id in sorted(expected_rows):
        expected = expected_rows[row_id]
        frozen = frozen_by_id[row_id]
        if frozen.source != expected.source:
            raise CallhomeEligibilityError(ERROR_SOURCE_DISAGREEMENT)
        canonical_split = canonical_splits_by_row_id[row_id]
        if canonical_split not in SPLIT_ORDER or frozen.split != canonical_split:
            raise CallhomeEligibilityError(ERROR_SPLIT_DISAGREEMENT)
        if (
            frozen.conversation_ref != expected.conversation_ref
            or frozen.speaker_ref != expected.speaker_ref
            or frozen.turn_index != expected.turn_index
            or frozen.row_id != expected.row_id
            or frozen.text != expected.text
        ):
            raise CallhomeEligibilityError(ERROR_PROVENANCE_DISAGREEMENT)
        decision = decisions[row_id]
        candidates = condition_candidates(source=frozen.source, decision=decision)
        if "CsCont" in candidates:
            raise CallhomeEligibilityError(ERROR_ROUTING_INVARIANT)
        reconciled.append(ReconciledEligibility(frozen, decision))
    return tuple(reconciled)


def _approximate_lexical_tokens(text: str) -> int:
    return sum(
        1 for token in text.split() if any(character.isalpha() for character in token)
    )


def _empty_bucket() -> dict[str, object]:
    return {
        "source_rows": 0,
        "approximate_lexical_tokens": 0,
        "eligible_rows": 0,
        "eligible_tokens": 0,
        "excluded_rows_by_reason": {
            reason: 0 for reason in EXCLUSION_REASON_ORDER
        },
        "excluded_tokens_by_reason": {
            reason: 0 for reason in EXCLUSION_REASON_ORDER
        },
        "ambiguous_rows": 0,
        "ambiguous_tokens": 0,
        "affected_conversations": 0,
        "rows_removed_percent": 0.0,
        "tokens_removed_percent": 0.0,
        "conversations_with_zero_eligible_rows": 0,
        "maximum_conversation_eligible_token_percent": 0.0,
    }


def summarize_reconciled_eligibility(
    reconciled: Iterable[ReconciledEligibility],
) -> dict[str, object]:
    """Return deterministic aggregate-only diagnostics."""
    materialized = tuple(reconciled)
    buckets: dict[tuple[str, str], dict[str, object]] = {
        (source, split): _empty_bucket()
        for source in SOURCE_ORDER
        for split in SPLIT_ORDER
    }
    all_conversations: dict[tuple[str, str], set[str]] = defaultdict(set)
    eligible_conversation_tokens: Counter[tuple[str, str, str]] = Counter()
    excluded_conversations: dict[tuple[str, str], set[str]] = defaultdict(set)

    for item in materialized:
        row = item.row
        if row.source not in SOURCE_ORDER:
            raise CallhomeEligibilityError(ERROR_SOURCE_DISAGREEMENT)
        if row.split not in SPLIT_ORDER:
            raise CallhomeEligibilityError(ERROR_SPLIT_DISAGREEMENT)
        candidates = condition_candidates(source=row.source, decision=item.decision)
        if "CsCont" in candidates:
            raise CallhomeEligibilityError(ERROR_ROUTING_INVARIANT)

        key = (row.source, row.split)
        bucket = buckets[key]
        tokens = _approximate_lexical_tokens(row.text)
        bucket["source_rows"] = int(bucket["source_rows"]) + 1
        bucket["approximate_lexical_tokens"] = (
            int(bucket["approximate_lexical_tokens"]) + tokens
        )
        all_conversations[key].add(row.conversation_ref)
        if item.decision.is_eligible:
            bucket["eligible_rows"] = int(bucket["eligible_rows"]) + 1
            bucket["eligible_tokens"] = int(bucket["eligible_tokens"]) + tokens
            eligible_conversation_tokens[
                (row.source, row.split, row.conversation_ref)
            ] += tokens
        else:
            reason = item.decision.exclusion_reason
            assert reason is not None
            excluded_rows = bucket["excluded_rows_by_reason"]
            excluded_tokens = bucket["excluded_tokens_by_reason"]
            assert isinstance(excluded_rows, dict)
            assert isinstance(excluded_tokens, dict)
            excluded_rows[reason] = int(excluded_rows[reason]) + 1
            excluded_tokens[reason] = int(excluded_tokens[reason]) + tokens
            excluded_conversations[key].add(row.conversation_ref)
            if reason == EXPLICIT_LANGUAGE_AMBIGUITY:
                bucket["ambiguous_rows"] = int(bucket["ambiguous_rows"]) + 1
                bucket["ambiguous_tokens"] = int(bucket["ambiguous_tokens"]) + tokens

    for key, bucket in buckets.items():
        source_rows = int(bucket["source_rows"])
        source_tokens = int(bucket["approximate_lexical_tokens"])
        eligible_rows = int(bucket["eligible_rows"])
        eligible_tokens = int(bucket["eligible_tokens"])
        bucket["affected_conversations"] = len(excluded_conversations[key])
        bucket["rows_removed_percent"] = (
            round(100.0 * (source_rows - eligible_rows) / source_rows, 6)
            if source_rows
            else 0.0
        )
        bucket["tokens_removed_percent"] = (
            round(100.0 * (source_tokens - eligible_tokens) / source_tokens, 6)
            if source_tokens
            else 0.0
        )
        eligible_conversations = {
            conversation
            for source, split, conversation in eligible_conversation_tokens
            if (source, split) == key
        }
        bucket["conversations_with_zero_eligible_rows"] = len(
            all_conversations[key] - eligible_conversations
        )
        conversation_token_counts = [
            count
            for (source, split, _), count in eligible_conversation_tokens.items()
            if (source, split) == key
        ]
        bucket["maximum_conversation_eligible_token_percent"] = (
            round(100.0 * max(conversation_token_counts) / eligible_tokens, 6)
            if eligible_tokens and conversation_token_counts
            else 0.0
        )

    return {
        "sources": {
            source: {
                split: buckets[(source, split)] for split in SPLIT_ORDER
            }
            for source in SOURCE_ORDER
        },
        "reconciliation": {
            "source_rows": len(materialized),
            "matched_rows": len(materialized),
            "unmatched_rows": 0,
            "duplicate_rows": 0,
        },
        "cross_split_leakage_count": 0,
        "callhome_to_cscont_routing_count": 0,
    }


def audit_callhome_monolingual_eligibility(
    transcripts_by_source: dict[str, Iterable[CallhomeTranscript]],
    frozen_rows: Iterable[CallhomeTrainingRow],
    *,
    canonical_splits_by_row_id: Mapping[str, str],
) -> dict[str, object]:
    """Reconcile and summarize; no partial aggregate exists after an error."""
    reconciled = reconcile_frozen_rows(
        transcripts_by_source,
        frozen_rows,
        canonical_splits_by_row_id=canonical_splits_by_row_id,
    )
    return summarize_reconciled_eligibility(reconciled)
