"""Path resolution utilities for the cslm project."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_MARKER_FILES = ("pyproject.toml", ".git")


@lru_cache(maxsize=1)
def project_root() -> Path:
    """Return the project root directory.

    Walks upward from this file until a directory containing one of
    ``_MARKER_FILES`` is found, so the result does not depend on the
    current working directory or any hard-coded absolute path.
    """
    here = Path(__file__).resolve()
    for candidate in (here, *here.parents):
        if any((candidate / marker).exists() for marker in _MARKER_FILES):
            return candidate
    raise RuntimeError(
        f"Could not locate project root from {here}; "
        f"expected one of {_MARKER_FILES} in a parent directory."
    )
