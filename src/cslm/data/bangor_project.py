"""Project the source-faithful Bangor layer into central ``UtteranceRow`` rows.

This is the experiment-facing projection described in
``docs/bangor_projection_policy.md``. It reads :class:`BangorUtterance` objects
(which preserve the raw CG-words export) and produces validated
:class:`UtteranceRow` rows, applying the agreed policies:

* Raw Bangor ``langid`` is preserved per token in
  ``source_token_language_labels`` (lossless / auditable).
* Token labels come from the Bangor-derived normalization, never the toy
  word-list classifier.
* A conservative, surface-only disfluency list is neutralized to ``neutral``
  *after* the source labels are captured.
* ``language_category`` is re-derived from the projected (post-neutralization)
  labels so labels and category always agree.
* Token counts are computed from the projected labels.
* ``needs_review_mixed_morpheme`` rows are withheld from ``EnglishMono``,
  ``SpanishMono``, and ``MonoCont`` (``CsCont``-only) via the row-aware
  condition helper.

Switch-site localization (bivalent bridges, morpheme-level mixed sites) is
deliberately out of scope here; the preserved source labels let a later PR add
those diagnostics without reprocessing.
"""

from __future__ import annotations

from collections import OrderedDict

from cslm.data.bangor_cgwords import BangorUtterance, derive_language_category
from cslm.data.classify import inter_sentential_switch
from cslm.data.conditions import condition_candidates_for_row
from cslm.data.schema import UtteranceRow

DEFAULT_SOURCE = "bangor_cgwords"

# Conservative, surface-only v1 disfluency / backchannel list. Only exact
# normalized-surface matches on an ``eng``/``spa`` token are neutralized to
# ``neutral``. This never touches ``.IM`` glosses directly, never deletes a
# token, and never maps to ``metadata``.
DISFLUENCY_SURFACES: frozenset[str] = frozenset(
    {
        "um",
        "uh",
        "er",
        "erm",
        "hm",
        "hmm",
        "mm",
        "mhm",
        "mmhm",
        "mm-hm",
        "uh-huh",
        "uhuh",
    }
)


def _normalize_surface(surface: str) -> str:
    return surface.strip().lower()


def is_disfluency_surface(surface: str) -> bool:
    """True when ``surface`` is an exact (normalized) match in the v1 list."""
    return _normalize_surface(surface) in DISFLUENCY_SURFACES


def project_token_labels(
    surfaces: list[str],
    bangor_labels: list[str],
    *,
    neutralize_disfluencies: bool = True,
) -> list[str]:
    """Map Bangor-local token labels to projected ``token_language_labels``.

    Labels pass through unchanged except that, when ``neutralize_disfluencies``
    is set, an ``eng``/``spa`` token whose surface is an exact disfluency match
    is relabeled ``neutral``. The raw source labels are captured separately by
    the caller before this runs, so neutralization is non-destructive.
    """
    projected: list[str] = []
    for surface, label in zip(surfaces, bangor_labels):
        if (
            neutralize_disfluencies
            and label in ("eng", "spa")
            and is_disfluency_surface(surface)
        ):
            projected.append("neutral")
        else:
            projected.append(label)
    return projected


def _token_counts(labels: list[str]) -> dict[str, int]:
    n_eng = labels.count("eng")
    n_spa = labels.count("spa")
    n_neutral_bivalent = labels.count("neutral") + labels.count("eng&spa")
    n_other = labels.count("other")
    n_mixed = labels.count("mixed_morpheme")
    n_metadata = labels.count("metadata")
    n_punct = labels.count("punct")
    n_word = n_eng + n_spa + n_neutral_bivalent + n_other + n_mixed
    return {
        "n_english_word_tokens": n_eng,
        "n_spanish_word_tokens": n_spa,
        "n_neutral_bivalent_word_tokens": n_neutral_bivalent,
        "n_other_word_tokens": n_other,
        "n_mixed_morpheme_word_tokens": n_mixed,
        "n_punctuation_tokens": n_punct,
        "n_metadata_tokens": n_metadata,
        "n_word_tokens_excluding_punctuation": n_word,
        "n_tokens_including_punctuation": n_word + n_punct + n_metadata,
    }


def project_utterance(
    bu: BangorUtterance,
    *,
    split: str = "train",
    source: str = DEFAULT_SOURCE,
    utterance_index: int | None = None,
    previous_row: UtteranceRow | None = None,
    neutralize_disfluencies: bool = True,
    include_neutral_or_bivalent: bool = False,
) -> UtteranceRow:
    """Project a single :class:`BangorUtterance` into an :class:`UtteranceRow`.

    ``previous_row`` (the already-projected predecessor in the same conversation)
    supplies the ordered-conversation and conservative inter-sentential switch
    metadata. Pass ``None`` for the first utterance in a conversation.
    """
    surfaces = bu.surfaces
    source_labels = list(bu.langids)  # raw Bangor langid, preserved verbatim
    projected_labels = project_token_labels(
        surfaces, bu.token_labels, neutralize_disfluencies=neutralize_disfluencies
    )
    category = derive_language_category(projected_labels)
    needs_review_mixed = "mixed_morpheme" in projected_labels
    counts = _token_counts(projected_labels)

    condition_candidates = condition_candidates_for_row(
        category,
        needs_review_mixed_morpheme=needs_review_mixed,
        include_neutral_or_bivalent=include_neutral_or_bivalent,
    )

    if previous_row is None:
        previous_utterance_id = None
        previous_speaker_id = None
        previous_category = None
        same_speaker_as_previous = None
    else:
        previous_utterance_id = previous_row.utterance_id
        previous_speaker_id = previous_row.speaker_id
        previous_category = previous_row.language_category
        same_speaker_as_previous = bu.speaker_id == previous_row.speaker_id

    is_inter_switch, inter_direction = inter_sentential_switch(previous_category, category)

    return UtteranceRow(
        utterance_id=bu.utterance_id,
        text=bu.text,
        source=source,
        conversation_id=bu.conversation_id,
        speaker_id=bu.speaker_id,
        split=split,
        language_category=category,
        condition_candidates=condition_candidates,
        tokens=list(surfaces),
        token_language_labels=projected_labels,
        source_token_language_labels=source_labels,
        utterance_index=utterance_index,
        previous_utterance_id=previous_utterance_id,
        previous_speaker_id=previous_speaker_id,
        previous_language_category=previous_category,
        same_speaker_as_previous=same_speaker_as_previous,
        is_inter_sentential_switch_from_previous=is_inter_switch,
        inter_sentential_switch_direction_from_previous=inter_direction,
        needs_review_mixed_morpheme=needs_review_mixed,
        **counts,
    )


def project_utterances(
    utterances: list[BangorUtterance],
    *,
    split: str = "train",
    source: str = DEFAULT_SOURCE,
    neutralize_disfluencies: bool = True,
    include_neutral_or_bivalent: bool = False,
) -> list[UtteranceRow]:
    """Project many utterances, threading per-conversation ordered metadata.

    Utterances are grouped by ``conversation_id`` in first-seen order; within a
    conversation, ``utterance_index`` and the previous-utterance / inter-
    sentential fields are populated from the projected predecessor.
    """
    by_conversation: "OrderedDict[str, list[BangorUtterance]]" = OrderedDict()
    for bu in utterances:
        by_conversation.setdefault(bu.conversation_id, []).append(bu)

    rows: list[UtteranceRow] = []
    for conversation in by_conversation.values():
        previous_row: UtteranceRow | None = None
        for index, bu in enumerate(conversation):
            row = project_utterance(
                bu,
                split=split,
                source=source,
                utterance_index=index,
                previous_row=previous_row,
                neutralize_disfluencies=neutralize_disfluencies,
                include_neutral_or_bivalent=include_neutral_or_bivalent,
            )
            rows.append(row)
            previous_row = row
    return rows
