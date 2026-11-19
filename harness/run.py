"""CLI: config + manifest -> Inspect run -> runs/<date>_<name>/ (Inspect logs, meta.json).

  python -m harness.run harness/configs/qwen3vl-8b-ollama.yaml
  python -m harness.run CFG --limit 5 --filter category=natural --ids a,b
  python -m harness.run --resume runs/2026-11-05_qwen3vl-8b-ollama   # rerun errored/unfinished rows only
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

import yaml
from inspect_ai import eval as inspect_eval
from inspect_ai.log import read_eval_log
from inspect_ai.model import GenerateConfig

from .task import DEFAULT_SYSTEM_PROMPT, build_task


def _git_hash() -> str | None:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return None


def _logs(run_dir: Path) -> list[Path]:
    logs = sorted((run_dir / "inspect_logs").glob("*.eval"))  # filenames start with a timestamp
    if not logs:
        raise SystemExit(f"no .eval log in {run_dir}/inspect_logs")
    return logs


def _done_ids(run_dir: Path, epochs: int) -> set[str]:
    clean = Counter()
    for lp in _logs(run_dir):
        for s in read_eval_log(str(lp)).samples or []:
            if not s.error:
                clean[s.id] += 1
    return {i for i, c in clean.items() if c >= epochs}


def _run(cfg: dict, meta: dict, run_dir: Path, model: str, exclude_ids: set[str] | None = None):
    task = build_task(
        meta["manifest"],
        ids=meta["ids"],
        where=meta["filter"],
        system_prompt=cfg.get("system_prompt", DEFAULT_SYSTEM_PROMPT),
        image_root=cfg.get("image_root"),
        name=meta["name"],
        limit=meta["limit"],
        exclude_ids=exclude_ids,
    )
    gen = GenerateConfig(**(cfg.get("generate") or {}))
    run = {"fail_on_error": False, "retry_on_error": 3, **(cfg.get("run") or {})}
    print(f"running {len(task.dataset)} rows with {model}")
    inspect_eval(
        task,
        model=model,
        model_base_url=cfg.get("base_url"),
        log_dir=str(run_dir / "inspect_logs"),
        log_format="eval",
        display="plain",
        **run,
        **gen.model_dump(exclude_none=True),
    )


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("config", nargs="?")
    ap.add_argument("--resume", help="existing run dir: rerun errored/unfinished rows only")
    ap.add_argument("--manifest")
    ap.add_argument("--model", help="override model, e.g. mockllm/model for a dry run")
    ap.add_argument("--limit", type=int, help="first N rows after filtering")
    ap.add_argument("--ids", help="comma-separated row ids")
    ap.add_argument("--filter", action="append", default=[], help="field=value on top-level manifest fields")
    ap.add_argument("--runs-dir", default="runs")
    args = ap.parse_args(argv)

    if args.resume:
        run_dir = Path(args.resume)
        cfg = yaml.safe_load((run_dir / "config.yaml").read_text())
        meta = json.loads((run_dir / "meta.json").read_text())
        epochs = (cfg.get("run") or {}).get("epochs", 1)
        done = _done_ids(run_dir, epochs)
        try:
            _run(cfg, meta, run_dir, meta["model"], exclude_ids=done)
        except ValueError as e:
            if "no manifest rows left" not in str(e):
                raise
            print("nothing to resume: every row already finished cleanly")
    else:
        if not args.config:
            ap.error("config required unless --resume")
        cfg = yaml.safe_load(Path(args.config).read_text())
        name = cfg.get("name") or Path(args.config).stem
        manifest = args.manifest or cfg["manifest"]
        run_dir = Path(args.runs_dir) / f"{dt.date.today().isoformat()}_{name}"
        if run_dir.exists():
            run_dir = Path(f"{run_dir}_{dt.datetime.now():%H%M%S}")
        (run_dir / "inspect_logs").mkdir(parents=True)
        shutil.copy(args.config, run_dir / "config.yaml")
        meta = {
            "name": name,
            "model": args.model or cfg["model"],
            "base_url": cfg.get("base_url"),
            "manifest": str(manifest),
            "manifest_sha256": hashlib.sha256(Path(manifest).read_bytes()).hexdigest(),
            "ids": args.ids.split(",") if args.ids else None,
            "filter": dict(f.split("=", 1) for f in args.filter),
            "limit": args.limit,
            "git_commit": _git_hash(),
            "started": dt.datetime.now().isoformat(),
            "argv": sys.argv,
        }
        (run_dir / "meta.json").write_text(json.dumps(meta, indent=2))
        _run(cfg, meta, run_dir, meta["model"])

    n = export_results(_logs(run_dir), run_dir / "results.jsonl")
    print(f"\n{n} rows -> {run_dir}/results.jsonl")
    print(f"view logs: inspect view --log-dir {run_dir}/inspect_logs")


if __name__ == "__main__":
    main()