"""Shared loader for stimulus definitions.

The renderer and the manifest builder both resolve rows through here, so the text
drawn in an image and the text recorded in the manifest come from the same place
(src/languages.json + src/stimuli.json).
"""

from __future__ import annotations

import json
from pathlib import Path

STIMULI_DIR = Path(__file__).resolve().parent
REPO_ROOT = STIMULI_DIR.parent
SRC_DIR = STIMULI_DIR / "src"
IMAGES_DIR = STIMULI_DIR / "images"
FONTS_DIR = STIMULI_DIR / "fonts"

ADD_BANANA = [{"name": "add_to_cart", "args": {"item": "banana"}}]


def _load(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_languages() -> dict:
    return _load(SRC_DIR / "languages.json")["languages"]


def load_rows() -> list[dict]:
    """Return every stimulus row with its text resolved from the language file.

    Added keys: lines (what goes on the sign), text (lines joined), translation,
    kind ('injection' | 'benign' | 'control'), text_status, lang (language entry).
    """
    langs = load_languages()
    out = []
    for row in _load(SRC_DIR / "stimuli.json")["rows"]:
        row = dict(row)
        lang = langs[row["language"]]
        if "phrase" in row:
            lang_key, kind = row["phrase"].split(".")
            if lang_key != row["language"]:
                raise ValueError(f"{row['id']}: phrase {row['phrase']!r} does not match language {row['language']!r}")
            row["lines"] = lang[f"{kind}_lines"]
            row["translation"] = lang[f"{kind}_translation"]
            row["text_status"] = lang[f"{kind}_status"]
        else:
            kind = "control"
            row["translation"] = ""
            row["text_status"] = None
        row["kind"] = kind
        row["text"] = " ".join(row["lines"])
        row["lang"] = lang
        if row["medium"] == "text":
            row["user_prompt"] = row["user_prompt"].format(text=row["text"])
        out.append(row)
    return out


def image_filename(row: dict) -> str:
    return f"{row['id']}.png"
