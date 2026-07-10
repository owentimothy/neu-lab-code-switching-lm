"""Guardrail test: the local-only lexicon resource path stays gitignored.

Protects against a future regression where lexicon files could be committed. No
lexicon files, real resources, or CALLHOME data are involved.
"""

from cslm.utils.paths import project_root

_IGNORED_LEXICON_PATH = "data/resources/local_lexicons/"


def test_gitignore_ignores_local_lexicon_path():
    gitignore = (project_root() / ".gitignore").read_text(encoding="utf-8")
    assert _IGNORED_LEXICON_PATH in gitignore
