"""How a tool-call argument is matched against an object's accepted names
(eval/classify.py uses it). Pure functions: no LLM, no model access."""

from __future__ import annotations

import re


def _norm(x) -> str:
    return " ".join(str(x).casefold().split())


def _contains_words(got: str, want: str) -> bool:
    """want appears in got as whole words, optionally pluralised with -s/-es:
    "hat" matches "a top hat" and "hats", not "that"; "tv" matches "TVs"."""
    if not want:
        return True
    pattern = r"(?<!\w)" + re.escape(want) + r"(?:e?s)?(?!\w)"
    return re.search(pattern, got) is not None


def arg_matches(actual, want) -> bool:
    """want is a string, or a list of strings where any one is enough
    (e.g. ["television", "tv"]). Each is matched as whole words after _norm."""
    got = _norm(actual)
    options = want if isinstance(want, list) else [want]
    return any(_contains_words(got, _norm(w)) for w in options)
