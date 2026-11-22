"""File helpers for the stimulus generator: strict JSON loading, hashing, and swapping a
staged directory into place."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class DuplicateKeyError(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict:
    # json.load would otherwise silently keep the last of two equal keys,
    # dropping a factor (or a field) without any error.
    out = {}
    for k, v in pairs:
        if k in out:
            raise DuplicateKeyError(f"duplicate key {k!r}")
        out[k] = v
    return out


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing factor file: {path}")
    with open(path, encoding="utf-8") as f:
        try:
            return json.load(f, object_pairs_hook=_reject_duplicate_keys)
        except DuplicateKeyError as e:
            raise ValueError(f"{path.name}: {e}") from None


def swap_in_dir(new: Path, dest: Path, trash: Path) -> None:
    """Replace dest with new. The old dest is moved into trash and deleted with it."""
    old = None
    if dest.exists():
        old = trash / "previous-images"
        os.replace(dest, old)
    try:
        os.replace(new, dest)
    except BaseException:
        if old is not None:
            os.replace(old, dest)
        raise
