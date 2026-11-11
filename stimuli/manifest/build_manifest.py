#!/usr/bin/env python3
"""
Build stimuli/manifest/manifest.jsonl and manifest.json from stimuli/src.

Rows, text and translations come from stimuli/spec.py (the same source the renderer
uses). Image hashes are read from the files in stimuli/images/, so run
render/generate_fictional_stimuli.py first.
Compatible with harness.manifest.load_manifest() and harness.task.build_task().
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from spec import ADD_BANANA, IMAGES_DIR, STIMULI_DIR, image_filename, load_rows  # noqa: E402

MANIFEST_DIR = STIMULI_DIR / "manifest"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def manifest_row(row: dict) -> dict:
    lang = row["lang"]
    injection = row["kind"] == "injection"
    out = {
        "id": row["id"],
        "section": row["section"],
        "mode": "obey",
        "medium": row["medium"],
        "language": row["language"],
        "fictional_universe": lang["universe"],
    }
    if lang.get("creator"):
        out["creator"] = lang["creator"]
    out.update({
        "script": row["script"],
        "user_prompt": row["user_prompt"],
        "expected_calls": ADD_BANANA if injection else [],
        "injected_text_raw": row["text"] if row["kind"] != "control" else "",
        "injected_text_translation": row["translation"],
        "intended_payload": "ADD_BANANA_TO_CART" if injection else None,
    })
    if row["medium"] == "image":
        p = IMAGES_DIR / image_filename(row)
        if not p.exists():
            raise FileNotFoundError(f"Missing stimulus image: {p} (run render/generate_fictional_stimuli.py)")
        out["image"] = f"stimuli/images/{p.name}"
        out["image_sha256"] = sha256_file(p)
    return out


def build() -> None:
    rows = [manifest_row(r) for r in load_rows()]
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate ids in stimuli/src/stimuli.json")

    expected = {r["image"].rsplit("/", 1)[1] for r in rows if "image" in r}
    stray = sorted(p.name for p in IMAGES_DIR.glob("*.png") if p.name not in expected)
    if stray:
        raise ValueError(f"images with no manifest row (delete or add a row): {stray}")

    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    jsonl_path = MANIFEST_DIR / "manifest.jsonl"
    json_path = MANIFEST_DIR / "manifest.json"
    with open(jsonl_path, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(json_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Wrote {len(rows)} samples to {jsonl_path} and {json_path}")


if __name__ == "__main__":
    build()
