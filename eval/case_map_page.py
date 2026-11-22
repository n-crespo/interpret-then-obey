"""
Case map page: one interactive treemap over one or more harness runs, written by
`analyze` in eval/analyze_results.py (case_map.html).

Each test case is one block, nested prompt -> context -> representation, with one
outcome strip per run (split by epoch when a run has several). Outcomes come from
`outcome` in eval/outcomes.py.
Prompt and context order and prompt text come from stimuli/src/; cases missing from the
manifest are dimmed. Click a block or group header to flag it; flagged ids are listed for
copying.
"""

from __future__ import annotations

import json
from pathlib import Path

from eval.outcomes import call_label, manifest_order, outcome
from stimuli.attack_types import SRC_DIR

TEMPLATE = Path(__file__).with_name("case_map_template.html")
CASE_FIELDS = ("id", "prompt_id", "context_id", "representation_id", "category", "attack_type")
RESPONSE_CHARS = 280


def _js_json(obj) -> str:
    """JSON safe to inline in a <script> block (model replies can contain '</script>')."""
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")


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
        "contexts": list(load("contexts.json")),
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
                "d": call_label(t["tool_calls"]),
                "r": (t.get("response") or "")[:RESPONSE_CHARS],
            })
    return sorted(cases.values(), key=lambda c: c["id"])


def case_map_html(cases: list[dict], labels: list[str], factors: dict, lock: list[str]) -> str:
    """Fill the template. `lock`: attack types whose cases cannot be flagged."""
    meta = {**factors, "runs": labels, "lock": lock, "resp_chars": RESPONSE_CHARS}
    page = TEMPLATE.read_text(encoding="utf-8")
    return page.replace("__DATA__", _js_json(cases)).replace("__META__", _js_json(meta))


def write_case_map(runs: dict[Path, list[dict]], out: Path, manifest: Path, src_dir: Path = SRC_DIR,
                  lock: tuple[str, ...] = ("hijack",)) -> Path:
    """Write the page for {run dir: its trials (attack_type filled in)}, one strip per run in
    the given order. `manifest`: the cases that are current; others are dimmed."""
    labels = run_labels(list(runs))
    factors = load_factors(src_dir)
    seen = {t["representation_id"] for ts in runs.values() for t in ts}
    factors["reps"] += [r for r in manifest_order(manifest) if r not in factors["reps"] and r in seen]
    cases = build_cases(dict(zip(labels, runs.values())), manifest_ids(manifest))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(case_map_html(cases, labels, factors, list(lock)), encoding="utf-8")
    return out
