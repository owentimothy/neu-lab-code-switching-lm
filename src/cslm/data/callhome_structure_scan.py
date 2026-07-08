"""Local-only, content-free structural scan of CALLHOME CHAT transcripts.

Aggregates **structural facts only** from parsed :class:`CallhomeTranscript`
objects — counts, header *keys* (never values), dependent-tier *prefixes* (never
values), and broad booleans. It deliberately exposes **no** transcript text,
header values, participant names, or speaker IDs, so its output is safe to print
locally.

Under CALLHOME ground-rules Decision C (see ``docs/callhome_ground_rules.md``),
CALLHOME-derived aggregate summaries are **not** committed yet. Accordingly this
module **writes no files**; producing/committing summaries is the caller's
responsibility and remains local/gitignored until TalkBank permission is
confirmed.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from cslm.data.callhome_chat import CallhomeTranscript, parse_chat_file


@dataclass
class CallhomeStructureSummary:
    """Structural-only summary for one language group. No content fields."""

    language_label: str
    n_files: int
    n_transcripts_parsed: int
    n_utterances: int
    n_parser_warnings: int
    # ``header_key_counts``: number of transcripts containing each header KEY
    # (e.g. "@Languages"); no header values are stored.
    header_key_counts: dict[str, int] = field(default_factory=dict)
    # ``dependent_tier_prefix_counts``: total dependent-tier lines per PREFIX
    # (e.g. "%mor"); no tier values are stored.
    dependent_tier_prefix_counts: dict[str, int] = field(default_factory=dict)
    n_files_with_languages_header: int = 0
    n_files_with_media_header: int = 0
    n_files_with_dependent_tiers: int = 0
    n_utterances_with_media_id: int = 0


def summarize_transcripts(
    transcripts: list[CallhomeTranscript],
    *,
    language_label: str,
    n_files: int | None = None,
) -> CallhomeStructureSummary:
    """Aggregate structural facts from already-parsed transcripts.

    ``n_files`` is the number of files *attempted* (defaults to the number of
    transcripts); ``n_transcripts_parsed`` is how many parsed successfully.
    """
    header_key_counts: Counter[str] = Counter()
    dependent_tier_prefix_counts: Counter[str] = Counter()
    n_utterances = 0
    n_parser_warnings = 0
    n_files_with_languages_header = 0
    n_files_with_media_header = 0
    n_files_with_dependent_tiers = 0
    n_utterances_with_media_id = 0

    for transcript in transcripts:
        # Header KEYS only (presence per transcript); values are never read.
        for key in transcript.headers:
            header_key_counts[key] += 1
        if "@Languages" in transcript.headers:
            n_files_with_languages_header += 1
        if "@Media" in transcript.headers:
            n_files_with_media_header += 1

        n_parser_warnings += len(transcript.parser_warnings)

        file_has_dependent_tier = False
        for utterance in transcript.utterances:
            n_utterances += 1
            if utterance.media_id is not None:
                n_utterances_with_media_id += 1
            for tier in utterance.dependent_tiers:
                dependent_tier_prefix_counts[tier.prefix] += 1
                file_has_dependent_tier = True
        if file_has_dependent_tier:
            n_files_with_dependent_tiers += 1

    return CallhomeStructureSummary(
        language_label=language_label,
        n_files=len(transcripts) if n_files is None else n_files,
        n_transcripts_parsed=len(transcripts),
        n_utterances=n_utterances,
        n_parser_warnings=n_parser_warnings,
        header_key_counts=dict(sorted(header_key_counts.items())),
        dependent_tier_prefix_counts=dict(sorted(dependent_tier_prefix_counts.items())),
        n_files_with_languages_header=n_files_with_languages_header,
        n_files_with_media_header=n_files_with_media_header,
        n_files_with_dependent_tiers=n_files_with_dependent_tiers,
        n_utterances_with_media_id=n_utterances_with_media_id,
    )


def scan_callhome_transcripts(
    paths: list[Path],
    *,
    language_label: str,
) -> CallhomeStructureSummary:
    """Parse each ``.cha`` path and return a structural-only summary.

    Files that fail to parse (e.g. an encoding error) are counted via the gap
    between ``n_files`` and ``n_transcripts_parsed`` rather than raising, so a
    scan over a mixed directory still completes. No file content is retained.
    """
    parsed: list[CallhomeTranscript] = []
    for path in paths:
        try:
            parsed.append(parse_chat_file(path))
        except (OSError, UnicodeDecodeError, ValueError):
            # Count as a non-parsed file; never surface the file or its content.
            continue
    return summarize_transcripts(
        parsed, language_label=language_label, n_files=len(paths)
    )


def flatten_structure_summary(summary: CallhomeStructureSummary) -> dict[str, object]:
    """Flatten to a single scalar row (structural facts only; no content)."""
    flat: dict[str, object] = {
        "language_label": summary.language_label,
        "n_files": summary.n_files,
        "n_transcripts_parsed": summary.n_transcripts_parsed,
        "n_utterances": summary.n_utterances,
        "n_parser_warnings": summary.n_parser_warnings,
        "n_files_with_languages_header": summary.n_files_with_languages_header,
        "n_files_with_media_header": summary.n_files_with_media_header,
        "n_files_with_dependent_tiers": summary.n_files_with_dependent_tiers,
        "n_utterances_with_media_id": summary.n_utterances_with_media_id,
    }
    for key, value in summary.header_key_counts.items():
        flat[f"header_key__{key}"] = value
    for prefix, value in summary.dependent_tier_prefix_counts.items():
        flat[f"dep_tier__{prefix}"] = value
    return flat
