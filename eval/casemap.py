#!/usr/bin/env python3
"""
Test case map: one interactive treemap over one or more harness runs.

Each test case is one block, nested prompt -> context -> representation, with one
outcome strip per run (split by epoch when a run has several). Outcomes come from
`outcome` in eval/analyze_results.py, trials from its `load_trials` (the Inspect logs).
Prompt and context order and prompt text come from stimuli/src/; cases missing from the
manifest are dimmed. Click a block or group header to flag it; flagged ids are listed for
copying.

Usage:
    python eval/casemap.py runs/<a> [runs/<b> ...] [--out page.html]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eval.analyze_results import _call_label, _js_json, fill_attack_type, load_trials, manifest_order, outcome  # noqa: E402
from stimuli.attack_types import SRC_DIR  # noqa: E402

TEMPLATE = Path(__file__).with_name("casemap_template.html")
CASE_FIELDS = ("id", "prompt_id", "context_id", "representation_id", "category", "attack_type")
RESPONSE_CHARS = 280


def run_labels(run_dirs: list[Path]) -> list[str]:
    """Short, unique label per run: the dir name without the `_`-separated parts every
    run shares (e.g. the config name). Falls back to the full names when that leaves an
    empty or repeated label."""
    names = [d.name for d in run_dirs]
    if len(names) > 1:
        parts = [n.split("_") for n in names]
        shared = set.intersection(*(set(p) for p in parts))
        short = ["_".join(x for x in p if x not in shared) for p in parts]
        if all(short) and len(set(short)) == len(short):
            return short
    if len(set(names)) == len(names):
        return names
    return [str(d) for d in run_dirs]


def load_factors(src_dir: Path = SRC_DIR) -> dict:
    """Prompt order and text, context order and representation order from stimuli/src/."""
    def load(name):
        return json.loads((src_dir / name).read_text(encoding="utf-8"))

    prompts = load("prompts.json")
    return {
        "prompts": [{"id": k, "text": v.get("text", "")} for k, v in prompts.items()],
        "contexts": list(load("context.json")),
        "reps": list(load("representations.json")),
    }


def manifest_ids(path: Path) -> set[str]:
    return {json.loads(line)["id"] for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def build_cases(runs: dict[str, list[dict]], in_manifest: set[str]) -> list[dict]:
    """One record per test case id seen in any run: its manifest factors, whether it is in
    the manifest, and per run label a list (by epoch) of {e, o, d, r}: epoch, outcome, tool
    call text and the start of the reply."""
    cases: dict[str, dict] = {}
    for label, trials in runs.items():
        for t in sorted(trials, key=lambda t: (t["id"], t["epoch"])):
            case = cases.setdefault(t["id"], {
                **{f: t.get(f) for f in CASE_FIELDS},
                "in_manifest": t["id"] in in_manifest,
                "runs": {},
            })
            case["runs"].setdefault(label, []).append({
                "e": t["epoch"],
                "o": outcome(t),
                "d": _call_label(t["tool_calls"]),
                "r": (t.get("response") or "")[:RESPONSE_CHARS],
            })
    return sorted(cases.values(), key=lambda c: c["id"])


def casemap_html(cases: list[dict], labels: list[str], factors: dict, lock: list[str]) -> str:
    """Fill the template. `lock`: attack types whose cases cannot be flagged."""
    meta = {**factors, "runs": labels, "lock": lock, "resp_chars": RESPONSE_CHARS}
    page = TEMPLATE.read_text(encoding="utf-8")
    return page.replace("__DATA__", _js_json(cases)).replace("__META__", _js_json(meta))


def casemap(run_dirs: list[Path], out: Path, manifest: Path, src_dir: Path = SRC_DIR,
          lock: list[str] | None = None) -> Path:
    labels = run_labels(run_dirs)
    runs = {}
    for label, d in zip(labels, run_dirs):
        trials, _ = load_trials(d)
        fill_attack_type(trials, src_dir)
        runs[label] = trials
    factors = load_factors(src_dir)
    seen = {c["representation_id"] for ts in runs.values() for c in ts}
    factors["reps"] += [r for r in manifest_order(manifest) if r not in factors["reps"] and r in seen]
    cases = build_cases(runs, manifest_ids(manifest))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(casemap_html(cases, labels, factors, ["hijack"] if lock is None else lock), encoding="utf-8")
    print(f"Wrote {out} ({len(cases)} cases, runs: {', '.join(labels)})")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dirs", type=Path, nargs="+", help="harness run directories, one outcome strip each")
    ap.add_argument("--out", type=Path, help="output page (default: <last run>/analysis/casemap.html)")
    ap.add_argument("--manifest", type=Path, default=Path("stimuli/manifest.jsonl"),
                    help="manifest that decides which cases are current (default: %(default)s)")
    ap.add_argument("--no-lock", action="store_true", help="let hijack cases be flagged too")
    args = ap.parse_args()
    casemap(args.run_dirs, args.out or args.run_dirs[-1] / "analysis" / "casemap.html", args.manifest,
          lock=[] if args.no_lock else None)
