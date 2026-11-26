"""Merge the Inspect logs of runs that together cover one manifest into one run folder,
so `just analyze` reads them as a single run.

Each source log is rewritten into <out>/inspect_logs/ (the sources are only read):
- Ids and context_id of contexts renamed since the run (eval/rescore.py RENAMED_CONTEXTS)
  take today's name.
- Samples whose id the manifest doesn't have are dropped, so the merged run holds exactly
  the manifest's rows. The full source run stays in its own folder.
- Each kept sample's metadata becomes its manifest row, and it is re-scored with today's
  scorer (eval/scorer.py). Errored samples stay unscored, so they remain harness_error.

A row that more than one source run holds is an error: the runs must not overlap.
<out>/meta.json names the manifest (eval/analyze.py reads it) and the source runs.

Usage:
    python -m eval.merge_runs runs/<out> runs/<a> runs/<b> [--manifest stimuli/manifest.jsonl]
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

from eval.rescore import RENAMED_CONTEXTS

MANIFEST = Path("stimuli/manifest.jsonl")


def renamed(sample_id: str) -> str:
    prompt, context, rest = sample_id.split(".", 2)
    return f"{prompt}.{RENAMED_CONTEXTS.get(context, context)}.{rest}"


def merge_runs(out: Path, sources: list[Path], manifest: Path = MANIFEST) -> dict[str, Counter]:
    """Write the merged run to `out`; returns {source run: Counter of kept/dropped samples}."""
    from inspect_ai import score
    from inspect_ai.log import read_eval_log, write_eval_log

    from eval.scorer import outcome

    rows = {r["id"]: r for r in (json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()
                                 if line.strip())}
    if (out / "inspect_logs").exists():
        sys.exit(f"Error: {out}/inspect_logs already exists")
    (out / "inspect_logs").mkdir(parents=True)

    owner: dict[str, str] = {}  # row id -> the source run that holds it
    counts: dict[str, Counter] = {}
    for src in sources:
        counts[src.name] = c = Counter()
        logs = sorted((src / "inspect_logs").glob("*.eval"))
        if not logs:
            sys.exit(f"Error: no .eval logs in {src}/inspect_logs")
        for lp in logs:
            log = read_eval_log(str(lp))
            kept = []
            for s in log.samples or []:
                new_id = renamed(str(s.id))
                if new_id not in rows:
                    c["dropped"] += 1
                    continue
                if owner.setdefault(new_id, src.name) != src.name:
                    sys.exit(f"Error: {new_id} is in both {owner[new_id]} and {src.name}")
                s.id, s.metadata = new_id, {**(s.metadata or {}), **rows[new_id]}
                kept.append(s)
                c["kept"] += 1
            if not kept:
                continue
            log.samples = kept
            log = score(log, outcome(), action="overwrite", display="none")
            for s in log.samples:  # score() scores errored samples too; unscored, they stay harness_error
                if s.error:
                    s.scores = None
            write_eval_log(log, out / "inspect_logs" / lp.name)

    meta = {
        "name": out.name,
        "manifest": manifest.as_posix(),
        "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "merged": dt.datetime.now().isoformat(timespec="seconds"),
        "sources": [{"run": src.as_posix(), **{k: v for k, v in _meta(src).items() if k in (
            "model", "git_commit", "manifest_sha256", "started")}} for src in sources],
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    missing = sorted(set(rows) - set(owner))
    if missing:
        print(f"WARNING: {len(missing)} manifest rows are in no source run, e.g. {missing[0]}", file=sys.stderr)
    return counts


def _meta(run_dir: Path) -> dict:
    path = run_dir / "meta.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out", type=Path)
    ap.add_argument("sources", type=Path, nargs="+")
    ap.add_argument("--manifest", type=Path, default=MANIFEST)
    args = ap.parse_args(argv)
    for run, c in merge_runs(args.out, args.sources, args.manifest).items():
        print(f"{run}: kept {c['kept']} samples, dropped {c['dropped']} not in {args.manifest}")
    print(f"Analyse with: just analyze {args.out.as_posix()}")


if __name__ == "__main__":
    main()
