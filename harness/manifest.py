"""Manifest loader. Provisional schema (agree final fields with persons 1/2).

One JSON object per line (manifest.jsonl); a plain .json array also works.

Required:  id (unique), user_prompt (sent verbatim as the final user turn)
Optional:  image            path to the frame shown with user_prompt (null = text-only row)
           image_sha256     checked against the file if present
           context          earlier turns, e.g. a legend already in context:
                            [{"role":"user","text":"Legend: ...","image":"legend.png"},
                             {"role":"assistant","text":"Understood."}]
           expected_calls   [{"name":"add_to_cart","args":{"item":"banana"}}]
                            empty/missing = control (nothing counts as obeyed)
           tools            subset of harness.tools.TOOLS (default: all)
           system_prompt    per-row override of the config's system prompt
           section, mode, medium, encoding, payload_id, ...  anything else is kept
                            as metadata and passed through to the results export.
"""

from __future__ import annotations

import hashlib
import json
import warnings
from pathlib import Path

REQUIRED = ("id", "user_prompt")

# stimuli/images/ is build output (gitignored); point people at the render step.
RENDER_CMD = "just build-stimuli (or: pip install -r stimuli/requirements.txt && python stimuli/render/generate_fictional_stimuli.py)"
PINNED_PILLOW_NOTE = "hashes are only reproducible with the Pillow version pinned in stimuli/requirements.txt"


def _is_generated(p: str) -> bool:
    return "stimuli/images/" in p.replace("\\", "/")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _resolve(p: str, roots: list[Path], where: str) -> str:
    cand = Path(p)
    if cand.is_absolute():
        if cand.exists():
            return str(cand)
    else:
        for root in roots:
            if (root / cand).exists():
                return str((root / cand).resolve())
    msg = f"{where}: image {p!r} not found (looked in {[str(r) for r in roots]})"
    if _is_generated(p):
        msg += f". Stimulus images are generated, not committed; run from the repo root: {RENDER_CMD}"
    raise FileNotFoundError(msg)


def _fix_image(item: dict, roots: list[Path], where: str, verify: bool) -> None:
    if not item.get("image"):
        return
    item["image"] = _resolve(item["image"], roots, where)
    want = item.get("image_sha256")
    if verify and want:
        got = sha256_file(Path(item["image"]))
        if got != want:
            msg = f"{where}: sha256 mismatch for {item['image']} (manifest {want[:12]}.. file {got[:12]}..)"
            if _is_generated(item["image"]):
                msg += f". Re-render with {RENDER_CMD}; {PINNED_PILLOW_NOTE}"
            raise ValueError(msg)
    elif verify:
        warnings.warn(f"{where}: no image_sha256 for {item['image']}", stacklevel=2)


def load_manifest(path: str | Path, image_root: str | Path | None = None, verify_hashes: bool = True) -> list[dict]:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        raw = [(i + 1, r) for i, r in enumerate(json.loads(text))]
    else:
        raw = []
        for n, line in enumerate(text.splitlines(), 1):
            line = line.strip()
            if line and not line.startswith("#"):
                try:
                    raw.append((n, json.loads(line)))
                except json.JSONDecodeError as e:
                    raise ValueError(f"{path}:{n}: invalid JSON ({e})") from e

    # relative image paths: --image-root, manifest dir, its parent (stimuli/), then repo root
    mdir = path.resolve().parent
    roots = [Path(image_root)] if image_root else []
    roots += [mdir, mdir.parent, mdir.parent.parent, Path.cwd()]

    rows, seen = [], set()
    for n, row in raw:
        where = f"{path.name}:{n}"
        missing = [k for k in REQUIRED if not row.get(k)]
        if missing:
            raise ValueError(f"{where}: missing required field(s) {missing}")
        if row["id"] in seen:
            raise ValueError(f"{where}: duplicate id {row['id']!r}")
        seen.add(row["id"])
        _fix_image(row, roots, where, verify_hashes)
        for m in row.get("context") or []:
            if m.get("role") not in ("user", "assistant", "system"):
                raise ValueError(f"{where}: context role must be user/assistant/system, got {m.get('role')!r}")
            _fix_image(m, roots, where, verify_hashes)
        for ec in row.get("expected_calls") or []:
            if "name" not in ec:
                raise ValueError(f"{where}: expected_calls entry needs a 'name'")
        rows.append(row)
    return rows


def filter_rows(rows: list[dict], ids: list[str] | None = None, where: dict[str, str] | None = None) -> list[dict]:
    """ids: keep only these ids. where: keep rows whose top-level field == value (string compare)."""
    out = rows
    if ids:
        out = [r for r in out if r["id"] in set(ids)]
    for k, v in (where or {}).items():
        out = [r for r in out if str(r.get(k)) == v]
    return out