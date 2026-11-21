"""Manifest loader: stimuli/manifest.jsonl -> list[Case] (stimuli/cases.py).

One `Case.to_dict()` per line, written by stimuli/generate.py. `read_cases` only parses
them (eval uses it; the images are gitignored, so it must not need them).
`load_cases` also resolves each image path and checks it against image_sha256: the
harness uses it before a run.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path

from stimuli.cases import Case


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
    raise FileNotFoundError(f"{where}: image {p!r} not found (looked in {[str(r) for r in roots]})")


def read_cases(path: str | Path) -> list[Case]:
    """The cases in a manifest, in order. Fails on invalid JSON, a row that is not a
    case (e.g. from a manifest written before cases existed) and duplicate ids."""
    path = Path(path)
    cases, seen = [], set()
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        where = f"{path.name}:{n}"
        try:
            row = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(f"{where}: invalid JSON ({e})") from e
        try:
            case = Case.from_dict(row)
        except (KeyError, TypeError) as e:
            raise ValueError(f"{where}: not a test case ({e!r}). Regenerate the manifest: just build-stimuli") from e
        if case.id in seen:
            raise ValueError(f"{where}: duplicate id {case.id!r}")
        seen.add(case.id)
        cases.append(case)
    return cases


def load_cases(path: str | Path, image_root: str | Path | None = None, verify_hashes: bool = True) -> list[Case]:
    """`read_cases`, with each image resolved to an absolute path and, with verify_hashes,
    checked against its image_sha256. Relative image paths are looked up in image_root,
    the manifest's folder, its parent (stimuli/), the repo root, then the working directory."""
    path = Path(path)
    mdir = path.resolve().parent
    roots = [Path(image_root)] if image_root else []
    roots += [mdir, mdir.parent, mdir.parent.parent, Path.cwd()]
    out = []
    for case in read_cases(path):
        where = f"{path.name}: {case.id}"
        image = _resolve(case.image, roots, where)
        if verify_hashes:
            if not case.image_sha256:
                raise ValueError(f"{where}: no image_sha256")
            got = sha256_file(Path(image))
            if got != case.image_sha256:
                raise ValueError(f"{where}: sha256 mismatch for {image} "
                                 f"(manifest {case.image_sha256[:12]}.. file {got[:12]}..)")
        out.append(dataclasses.replace(case, image=image))
    return out


def filter_cases(cases: list[Case], ids: list[str] | None = None, where: dict[str, str] | None = None) -> list[Case]:
    """ids: keep only these ids. where: keep cases whose `Case.factors()` field == value
    (string compare), e.g. {"category": "natural"}."""
    out = cases
    if ids:
        out = [c for c in out if c.id in set(ids)]
    for k, v in (where or {}).items():
        out = [c for c in out if str(c.factors().get(k)) == v]
    return out
