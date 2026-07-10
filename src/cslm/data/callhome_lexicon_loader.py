"""Local-only lexicon loader scaffold (caller-provided files only).

A minimal, dependency-free loader for **caller-provided local** word-list or
Hunspell-style ``.dic`` files. It is deliberately small and does **not**:

* download anything,
* know about or read CALLHOME files (or ``data/raw/callhome``),
* wire into the real-data summary script,
* expand Hunspell affixes or read ``.aff`` files,
* commit or ship any real lexical resource.

Real dictionaries stay **local / gitignored** under
``data/resources/local_lexicons/`` per ``docs/callhome_lexicon_storage_scaffold.md``;
this loader only reads an **explicit path** the caller passes in. It returns
**raw** entries (no normalization) so the validator can normalize lexicon entries
and utterance tokens *identically* — see
``docs/callhome_lexicon_normalization_policy.md`` and
``cslm.data.callhome_lexicon_validation``.

This is a **raw-entry loading scaffold only**; it is not sufficient for final
real resources (no morphology, no affix expansion).
"""

from __future__ import annotations

from pathlib import Path

# Lines whose stripped form starts with this marker are treated as comments and
# skipped. (A scaffold convention; real .dic files do not use it.)
_COMMENT_PREFIX = "#"


def load_plain_wordlist(path: Path | str) -> set[str]:
    """Load a plain one-entry-per-line word list into a set of **raw** entries.

    Blank lines and ``#`` comment lines are ignored. Entries are returned
    verbatim (whitespace-trimmed only); normalization is the validator's job.
    """
    entries: set[str] = set()
    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith(_COMMENT_PREFIX):
            continue
        entries.add(line)
    return entries


def load_hunspell_dic_wordlist(path: Path | str) -> set[str]:
    """Load raw entries from a Hunspell-style ``.dic`` file (no affix expansion).

    Scaffold behavior only:

    * If the **first line** is all digits, it is treated as the Hunspell count
      line and ignored.
    * Affix flags after a ``/`` are stripped (``"hello/AB"`` -> ``"hello"``).
    * Blank lines and ``#`` comment lines are ignored.

    Affixes are **not** expanded and ``.aff`` files are **not** read; entries are
    returned raw (before-slash form only). Normalization is the validator's job.
    """
    entries: set[str] = set()
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    for index, raw_line in enumerate(lines):
        line = raw_line.strip()
        if index == 0 and line.isdigit():
            # Hunspell count line.
            continue
        if not line or line.startswith(_COMMENT_PREFIX):
            continue
        entry = line.split("/", 1)[0].strip()
        if entry:
            entries.add(entry)
    return entries


def load_wordlist(path: Path | str, *, hunspell_dic: bool = False) -> set[str]:
    """Dispatch to the plain or Hunspell-``.dic`` loader (caller-provided path)."""
    if hunspell_dic:
        return load_hunspell_dic_wordlist(path)
    return load_plain_wordlist(path)
