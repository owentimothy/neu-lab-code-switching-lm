"""Dry-run ingestion for Bangor Miami CG-words TSV exports.

Word-level TSV rows -> grouped :class:`BangorUtterance` objects. This is a
deliberately small, Bangor-local intermediate layer:

* It preserves the original source columns (``surface``, ``langid``, ``auto``,
  ``speaker``, ``filename``, ``utterance_id``, ``location``) on every word.
* It derives only *Bangor-local* token labels and utterance categories from the
  source ``langid`` column. It never runs the toy word-list classifier on
  Bangor text.
* It does **not** construct :class:`cslm.data.schema.UtteranceRow` or mutate that
  already-tested schema. Projection into ``UtteranceRow`` is a later, explicitly
  scoped step, so contested labels (``eng+spa``, ``spa+eng``, ``eng&spa+eng``,
  ``www``) are not forced into the central 6-label vocabulary yet.

The CG-words export is one row per word. Rows are grouped by
``(filename, utterance_id)`` and sorted by ``location`` to reconstruct
utterances. ``filename`` is used as ``conversation_id`` and a globally unique
id such as ``herring1_000001`` is minted per utterance.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from cslm.data.schema import LANGUAGE_CATEGORIES

# Source TSV columns, in order, for the CG-words export.
CGWORDS_COLUMNS: tuple[str, ...] = (
    "word_id",
    "utterance_id",
    "location",
    "surface",
    "auto",
    "fix",
    "eng",
    "com",
    "speaker",
    "langid",
    "filename",
    "clause",
    "clauseno",
)

# Bangor-local token labels derived from the source ``langid`` column. These are
# intentionally richer than ``UtteranceRow.TOKEN_LANGUAGE_LABELS``: ``metadata``
# (``www``) and ``mixed_morpheme`` (``eng+spa`` / ``spa+eng`` / ``eng&spa+eng``)
# are kept distinct instead of being silently collapsed into ``other``.
BANGOR_TOKEN_LABELS: frozenset[str] = frozenset(
    {"eng", "spa", "eng&spa", "punct", "metadata", "mixed_morpheme", "other"}
)

# Utterance-level categories this module can emit. Guarded against the central
# schema so a divergence surfaces at import time rather than silently.
_EMITTED_CATEGORIES: frozenset[str] = frozenset(
    {
        "en_only",
        "es_only",
        "cs_within_utterance",
        "neutral_or_bivalent",
        "punctuation_or_empty",
        "mixed_or_uncertain",
        "metadata_or_noise",
    }
)
assert _EMITTED_CATEGORIES <= LANGUAGE_CATEGORIES

# CG-words files end with a non-data footer line like ``(7590 rows)``.
_FOOTER_RE = re.compile(r"^\(\d+ rows\)$")
# A surface made up entirely of non-word, non-space characters (``.``, ``?``,
# ``!``, ``¿``, ``¡`` ...). Used to sanity-check ``999`` punctuation rows.
_PUNCT_RE = re.compile(r"^[^\w\s]+$", re.UNICODE)


def map_langid_to_token_label(langid: str, surface: str) -> str:
    """Map a source Bangor ``langid`` to a Bangor-local token label.

    Policy for the contested / special labels (see project docs):

    * ``eng`` / ``spa`` -> ``eng`` / ``spa``.
    * ``eng&spa`` -> ``eng&spa`` (bivalent / undetermined / proper name).
    * ``999`` with a punctuation surface -> ``punct``; a ``999`` row whose
      surface is *not* punctuation is not silently trusted and becomes
      ``other``.
    * a ``www`` surface, or a ``www`` ``langid`` -> ``metadata``
      (non-consenting / unrepresented speech marker). The surface check wins
      even when the export mislabels the ``langid`` (e.g. ``www`` tagged
      ``eng&spa``), so redacted speech is never treated as bivalent material.
    * anything containing ``+`` (``eng+spa``, ``spa+eng``, ``eng&spa+eng``, ...)
      -> ``mixed_morpheme``. Within-word morpheme mixing is contested and is not
      treated as clean English/Spanish material.
    * empty / unknown -> ``other``.
    """
    if (surface or "").strip().lower() == "www":
        return "metadata"
    lang = (langid or "").strip()
    if lang == "eng":
        return "eng"
    if lang == "spa":
        return "spa"
    if lang == "eng&spa":
        return "eng&spa"
    if lang == "www":
        return "metadata"
    if lang == "999":
        return "punct" if _PUNCT_RE.match(surface or "") else "other"
    if "+" in lang:
        return "mixed_morpheme"
    return "other"


def derive_language_category(token_labels: list[str]) -> str:
    """Derive an utterance ``language_category`` from Bangor-local token labels.

    The derivation uses only clean ``eng`` / ``spa`` labels to decide monolingual
    vs. intra-sentential code-switched status. ``eng&spa`` (bivalent) and
    ``mixed_morpheme`` never contribute English/Spanish presence, so contested
    material is never silently promoted to a code-switching decision.
    """
    labels = list(token_labels)
    label_set = set(labels)

    # ``www`` marks non-consenting / unrepresented speech. An utterance that is
    # entirely metadata (plus punctuation) is noise; metadata mixed with real
    # material is uncertain rather than silently kept.
    if "metadata" in label_set:
        if all(label in ("metadata", "punct") for label in labels):
            return "metadata_or_noise"
        return "mixed_or_uncertain"

    non_punct = [label for label in labels if label != "punct"]
    if not non_punct:
        return "punctuation_or_empty"

    has_eng = "eng" in label_set
    has_spa = "spa" in label_set
    if has_eng and has_spa:
        return "cs_within_utterance"
    if has_eng:
        return "en_only"
    if has_spa:
        return "es_only"

    # No clean eng/spa tokens remain. mixed_morpheme / other -> uncertain; only
    # bivalent (eng&spa) material -> neutral_or_bivalent.
    if label_set & {"mixed_morpheme", "other"}:
        return "mixed_or_uncertain"
    return "neutral_or_bivalent"


@dataclass(frozen=True)
class BangorWord:
    """A single CG-words TSV row, with all source columns preserved."""

    word_id: int
    utterance_id: int
    location: int
    surface: str
    auto: str
    fix: str
    eng: str
    com: str
    speaker: str
    langid: str
    filename: str
    clause: str
    clauseno: str

    @property
    def token_label(self) -> str:
        """Bangor-local token label derived from ``langid`` and ``surface``."""
        return map_langid_to_token_label(self.langid, self.surface)


@dataclass
class BangorUtterance:
    """Words grouped by ``(filename, utterance_id)`` and ordered by ``location``.

    Source fields are preserved on the constituent :class:`BangorWord` objects;
    derived views (token labels, category, counts) are computed on demand so the
    stored data stays faithful to the export.
    """

    conversation_id: str
    source_utterance_id: int
    utterance_id: str
    speaker_id: str
    words: list[BangorWord] = field(default_factory=list)

    @property
    def surfaces(self) -> list[str]:
        return [w.surface for w in self.words]

    @property
    def locations(self) -> list[int]:
        return [w.location for w in self.words]

    @property
    def langids(self) -> list[str]:
        return [w.langid for w in self.words]

    @property
    def token_labels(self) -> list[str]:
        return [w.token_label for w in self.words]

    @property
    def text(self) -> str:
        return " ".join(self.surfaces)

    @property
    def language_category(self) -> str:
        return derive_language_category(self.token_labels)

    @property
    def needs_review_mixed_morpheme(self) -> bool:
        return "mixed_morpheme" in self.token_labels

    def to_dict(self) -> dict:
        return {
            "utterance_id": self.utterance_id,
            "conversation_id": self.conversation_id,
            "source_utterance_id": self.source_utterance_id,
            "speaker_id": self.speaker_id,
            "text": self.text,
            "surfaces": self.surfaces,
            "locations": self.locations,
            "langids": self.langids,
            "token_labels": self.token_labels,
            "language_category": self.language_category,
            "needs_review_mixed_morpheme": self.needs_review_mixed_morpheme,
            "n_words": len(self.words),
        }


@dataclass
class ParsedCgwords:
    """Result of parsing one CG-words file, with skip diagnostics."""

    filename: str
    words: list[BangorWord] = field(default_factory=list)
    n_skipped_footer: int = 0
    n_skipped_blank: int = 0


def parse_cgwords_file(path: str | Path) -> ParsedCgwords:
    """Parse one CG-words TSV file into ordered :class:`BangorWord` rows.

    Skips the header row, any blank lines, and the trailing ``(N rows)`` footer.
    Rows are returned in file order (grouping/sorting happens in
    :func:`group_utterances`). Reads the raw file read-only.
    """
    path = Path(path)
    words: list[BangorWord] = []
    n_footer = 0
    n_blank = 0
    filename = path.stem.replace("_cgwords", "")

    with path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.rstrip("\r\n")
            stripped = line.strip()
            if not stripped:
                n_blank += 1
                continue
            if _FOOTER_RE.match(stripped):
                n_footer += 1
                continue

            fields = line.split("\t")
            if fields[0] == CGWORDS_COLUMNS[0]:  # header row
                continue
            if len(fields) < len(CGWORDS_COLUMNS):
                fields = fields + [""] * (len(CGWORDS_COLUMNS) - len(fields))

            record = dict(zip(CGWORDS_COLUMNS, fields, strict=False))
            words.append(
                BangorWord(
                    word_id=int(record["word_id"]),
                    utterance_id=int(record["utterance_id"]),
                    location=int(record["location"]),
                    surface=record["surface"],
                    auto=record["auto"],
                    fix=record["fix"],
                    eng=record["eng"],
                    com=record["com"],
                    speaker=record["speaker"],
                    langid=record["langid"],
                    filename=record["filename"] or filename,
                    clause=record["clause"],
                    clauseno=record["clauseno"],
                )
            )

    if words:
        filename = words[0].filename
    return ParsedCgwords(
        filename=filename,
        words=words,
        n_skipped_footer=n_footer,
        n_skipped_blank=n_blank,
    )


def global_utterance_id(filename: str, source_utterance_id: int) -> str:
    """Mint a globally unique utterance id such as ``herring1_000001``."""
    return f"{filename}_{source_utterance_id:06d}"


def group_utterances(words: list[BangorWord]) -> list[BangorUtterance]:
    """Group words by ``(filename, utterance_id)`` and sort each by ``location``.

    Utterances are returned in first-seen order (which matches the source file's
    utterance order). ``speaker_id`` is taken from the first word of the
    utterance; CG-words utterances do not mix speakers.
    """
    grouped: dict[tuple[str, int], list[BangorWord]] = {}
    order: list[tuple[str, int]] = []
    for word in words:
        key = (word.filename, word.utterance_id)
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append(word)

    utterances: list[BangorUtterance] = []
    for filename, source_uid in order:
        ordered = sorted(grouped[(filename, source_uid)], key=lambda w: w.location)
        utterances.append(
            BangorUtterance(
                conversation_id=filename,
                source_utterance_id=source_uid,
                utterance_id=global_utterance_id(filename, source_uid),
                speaker_id=ordered[0].speaker,
                words=ordered,
            )
        )
    return utterances


def summarize_ingestion(
    results: list[tuple[ParsedCgwords, list[BangorUtterance]]],
) -> dict:
    """Build an exploratory ingestion summary over one or more parsed files.

    Reports source ``langid`` counts, derived token-label and category counts,
    word/utterance/file totals, speakers, skipped footer lines, and the number
    of utterances flagged for mixed-morpheme review. No sampling or condition
    assignment happens here; this is a dry-run inventory only.
    """
    per_file: list[dict] = []
    langid_total: Counter[str] = Counter()
    label_total: Counter[str] = Counter()
    category_total: Counter[str] = Counter()
    speakers_total: set[str] = set()
    n_words = 0
    n_utterances = 0
    n_footer = 0
    n_mixed_review = 0

    for parsed, utterances in results:
        langid_counts = Counter(w.langid for w in parsed.words)
        label_counts = Counter(w.token_label for w in parsed.words)
        category_counts = Counter(u.language_category for u in utterances)
        file_speakers = sorted({w.speaker for w in parsed.words})
        file_mixed_review = sum(1 for u in utterances if u.needs_review_mixed_morpheme)

        per_file.append(
            {
                "conversation_id": parsed.filename,
                "n_word_rows": len(parsed.words),
                "n_utterances": len(utterances),
                "n_skipped_footer_lines": parsed.n_skipped_footer,
                "speakers": file_speakers,
                "source_langid_counts": dict(sorted(langid_counts.items())),
                "token_label_counts": dict(sorted(label_counts.items())),
                "language_category_counts": dict(sorted(category_counts.items())),
                "n_needs_review_mixed_morpheme": file_mixed_review,
            }
        )

        langid_total.update(langid_counts)
        label_total.update(label_counts)
        category_total.update(category_counts)
        speakers_total.update(file_speakers)
        n_words += len(parsed.words)
        n_utterances += len(utterances)
        n_footer += parsed.n_skipped_footer
        n_mixed_review += file_mixed_review

    return {
        "n_files": len(results),
        "conversation_ids": [f["conversation_id"] for f in per_file],
        "n_word_rows": n_words,
        "n_utterances": n_utterances,
        "n_skipped_footer_lines": n_footer,
        "speakers": sorted(speakers_total),
        "source_langid_counts": dict(sorted(langid_total.items())),
        "token_label_counts": dict(sorted(label_total.items())),
        "language_category_counts": dict(sorted(category_total.items())),
        "n_needs_review_mixed_morpheme": n_mixed_review,
        "per_file": per_file,
    }


def flatten_ingestion_summary(summary: dict) -> dict:
    """Flatten an ingestion summary into a single row for CSV output."""
    flat: dict[str, object] = {
        "n_files": summary["n_files"],
        "n_word_rows": summary["n_word_rows"],
        "n_utterances": summary["n_utterances"],
        "n_skipped_footer_lines": summary["n_skipped_footer_lines"],
        "n_speakers": len(summary["speakers"]),
        "n_needs_review_mixed_morpheme": summary["n_needs_review_mixed_morpheme"],
    }
    for key, value in summary["source_langid_counts"].items():
        flat[f"langid_{key}"] = value
    for key, value in summary["token_label_counts"].items():
        flat[f"label_{key}"] = value
    for key, value in summary["language_category_counts"].items():
        flat[f"category_{key}"] = value
    return flat
