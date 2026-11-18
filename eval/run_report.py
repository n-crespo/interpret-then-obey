#!/usr/bin/env python3
"""
Figures and a summary for one harness run, so it can be read on GitHub without Inspect.

Reads runs/<dir>/results.jsonl, meta.json and config.yaml, and writes:

- figures/outcomes.svg   one cell per sample: representation (row) x prompt and context
                         (column), coloured by what the model did; split into one strip
                         per epoch when epochs disagree
- figures/obey_rate.svg  obeyed / samples per representation
- figures/tools.svg      tool calls by tool
- README.md              the generated part sits between the two run_report markers
                         and is rewritten on every run. A missing README is created from
                         a template whose takeaways, caveats and planned changes are left
                         for a person to write. A README without the markers is left alone.

Terms are the ones in eval/analyze_results.py: attack success counts the hijack and
escalation rows with an injection; no_target and the `none` baseline are reported on
their own. Runs that predate the attack_type field get it from stimuli/attack_types.py.

Usage:
    python eval/run_report.py runs/<date>_<name>
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Patch, Polygon  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from stimuli.attack_types import load_attack_fields  # noqa: E402

BEGIN, END = "<!-- run_report:begin -->", "<!-- run_report:end -->"
BASELINE = "baseline"
CATEGORY_ORDER = ["baseline", "natural", "constructed", "symbols", "opaque"]

SURFACE, INK, INK2, MUTED, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#c3c2b7"
OUTCOME = {  # key: (fill, label ink, legend text)
    "obeyed": ("#eb6834", "#ffffff", "bought the injected item (obeyed)"),
    "product": ("#2a78d6", "#ffffff", "bought the scene's product"),
    "other": ("#eda100", INK, "bought something else"),
    "tool": ("#1baf7a", INK, "other tools only"),
    "none": (SURFACE, INK2, "no tool call"),
}
BUY_TOOLS = ("buy", "add_to_cart")
SHORT_TOOL = {"save_photo": "photo", "translate_text": "translate", "get_directions": "directions",
              "set_reminder": "reminder", "send_message": "message", "save_note": "note", "search_web": "search"}
RC = {"font.family": "DejaVu Sans", "font.size": 9, "text.color": INK, "figure.facecolor": SURFACE,
      "axes.facecolor": SURFACE, "svg.hashsalt": "run-report"}
SAVE = {"format": "svg", "metadata": {"Date": None}, "bbox_inches": "tight", "pad_inches": 0.15}


# ----------------------------------------------------------------------------
# Loading


def load_run(run_dir: Path) -> tuple[list[dict], dict, dict]:
    rows = [json.loads(line) for line in (run_dir / "results.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    meta = json.loads((run_dir / "meta.json").read_text(encoding="utf-8")) if (run_dir / "meta.json").exists() else {}
    config = {}
    if (run_dir / "config.yaml").exists():
        import yaml  # comes with inspect-ai

        config = yaml.safe_load((run_dir / "config.yaml").read_text(encoding="utf-8")) or {}
    fields = load_attack_fields()
    for r in rows:
        m = r["manifest_row"]
        if m.get("attack_type") is None:
            m.update(fields.get((m.get("prompt_id"), m.get("context_id")), {}))
    return rows, meta, config


def scene_products() -> dict[str, str]:
    """context_id -> a word that names the scene's own product ("mug", "backpack")."""
    contexts = json.loads((REPO / "stimuli/src/context.json").read_text(encoding="utf-8"))
    return {cid: c["item"].split()[-1].lower() for cid, c in contexts.items() if c.get("item")}


def harness_tools() -> list[str]:
    """Tool names in harness/tools/mock_tools.py's TOOLS, read without importing inspect_ai."""
    tree = ast.parse((REPO / "harness/tools/mock_tools.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "TOOLS" for t in node.targets):
            if isinstance(node.value, ast.Dict):
                return [k.value for k in node.value.keys if isinstance(k, ast.Constant)]
    return []


def m(r: dict, key: str):
    return r["manifest_row"].get(key)


def expected_item(r: dict) -> str:
    for call in m(r, "expected_calls") or []:
        if call.get("name") == "buy":
            return str(call.get("args", {}).get("item", "item"))
    return "item"


def classify(r: dict, products: dict[str, str]) -> tuple[str, str]:
    """(outcome key, short cell label) for one sample."""
    if r.get("obeyed"):
        return "obeyed", expected_item(r)
    buys = [str(t.get("args", {}).get("item", "")) for t in r.get("tool_calls") or [] if t["name"] in BUY_TOOLS]
    product = products.get(m(r, "context_id"))
    if product and any(product in b.lower() for b in buys):
        return "product", product
    if buys:
        words = re.sub(r"\(.*?\)", "", buys[0]).strip(" .!").lower().split()
        return "other", (words[-1] if words else "?")[:10]
    names = [t["name"] for t in r.get("tool_calls") or []]
    if names:
        return "tool", SHORT_TOOL.get(names[0], names[0]) + (f" +{len(names) - 1}" if len(names) > 1 else "")
    return "none", "—"


def cut_off(r: dict) -> bool:
    return r.get("stop_reason") == "max_tokens"


def representations(rows: list[dict]) -> list[str]:
    """Representation ids, grouped by category (baseline first), then in manifest order."""
    seen: dict[str, str] = {}
    for r in rows:
        seen.setdefault(m(r, "representation_id"), m(r, "category"))
    rank = {c: i for i, c in enumerate(CATEGORY_ORDER)}
    order = list(seen)
    return sorted(order, key=lambda rep: (rank.get(seen[rep], len(rank)), order.index(rep)))


# ----------------------------------------------------------------------------
# Numbers


def frac(k: int, n: int) -> str:
    return f"{k}/{n}" if n else "–"


def summary(rows: list[dict]) -> dict:
    injected = [r for r in rows if m(r, "category") != BASELINE]
    attack = [r for r in injected if m(r, "attack_type") in ("hijack", "escalation")]
    by_type = {t: [r for r in injected if m(r, "attack_type") == t] for t in ("escalation", "hijack", "no_target")}
    baseline = [r for r in rows if m(r, "category") == BASELINE]
    reps = representations(rows)
    per_rep = {rep: [r for r in rows if m(r, "representation_id") == rep] for rep in reps}
    return {
        "n": len(rows),
        "epochs": len({r.get("epoch") for r in rows}),
        "obeyed": lambda rs: sum(bool(r.get("obeyed")) for r in rs),
        "attack": attack,
        "by_type": by_type,
        "baseline": baseline,
        "per_rep": per_rep,
        "cut": sum(cut_off(r) for r in rows),
        "no_call": sum(not r.get("tool_calls") for r in rows),
        "errors": sum(bool(r.get("error")) for r in rows),
    }


# ----------------------------------------------------------------------------
# Figures


def _cell(ax, x, y, w, h, key, label, cut, pad=0.06):
    fill, ink, _ = OUTCOME[key]
    ax.add_patch(FancyBboxPatch((x + pad, y + pad), w - 2 * pad, h - 2 * pad, boxstyle="round,pad=0,rounding_size=0.12",
                                linewidth=0.8 if key == "none" else 0, facecolor=fill, edgecolor=AXIS))
    if label:
        ax.text(x + w / 2, y + h * 0.52, label, ha="center", va="center", color=ink, fontsize=8)
    if cut:  # dark corner: cut off at the token limit
        tri = [(x + w - pad - min(0.2, w / 3), y + pad), (x + w - pad, y + pad), (x + w - pad, y + pad + 0.32)]
        ax.add_patch(Polygon(tri, closed=True, facecolor=INK, linewidth=0))


def fig_outcomes(rows: list[dict], path: Path) -> None:
    products = scene_products()
    reps = representations(rows)
    prompts = sorted({m(r, "prompt_id") for r in rows})
    contexts = sorted({m(r, "context_id") for r in rows})
    cells = defaultdict(list)
    for r in rows:
        cells[(m(r, "representation_id"), m(r, "prompt_id"), m(r, "context_id"))].append(r)
    category = {m(r, "representation_id"): m(r, "category") for r in rows}

    ys, y, prev = {}, 0.0, None
    for rep in reps:
        if prev is not None and category[rep] != prev:
            y += 0.35
        ys[rep], prev = y, category[rep]
        y += 1
    n_cols = len(prompts) * len(contexts)
    xs = [c + (c // len(contexts)) * 0.25 for c in range(n_cols)]

    fig, ax = plt.subplots(figsize=(1.3 + 1.25 * n_cols, 1.2 + 0.4 * y))
    for rep in reps:
        for pi, p in enumerate(prompts):
            for ci, c in enumerate(contexts):
                samples = sorted(cells.get((rep, p, c), []), key=lambda r: r.get("epoch") or 0)
                x0 = xs[pi * len(contexts) + ci]
                if not samples:
                    continue
                outcomes = [classify(r, products) for r in samples]
                if len(set(outcomes)) == 1:  # one sample, or every epoch did the same
                    key, label = outcomes[0]
                    if len(samples) > 1:
                        label = f"{label} ×{len(samples)}"
                    _cell(ax, x0, ys[rep], 1, 1, key, label, any(cut_off(r) for r in samples))
                else:  # epochs disagree: one strip per epoch, no text
                    w = 1 / len(samples)
                    for i, (r, (key, _)) in enumerate(zip(samples, outcomes)):
                        _cell(ax, x0 + i * w, ys[rep], w, 1, key, "", cut_off(r), pad=0.03)
    for pi, p in enumerate(prompts):
        left, right = xs[pi * len(contexts)], xs[(pi + 1) * len(contexts) - 1] + 1
        ax.text((left + right) / 2, -1.25, f"prompt: {p}", ha="center", va="center", fontsize=10, fontweight="bold")
        ax.plot([left + 0.1, right - 0.1], [-0.95, -0.95], color=AXIS, linewidth=0.8)
        for ci, c in enumerate(contexts):
            ax.text(xs[pi * len(contexts) + ci] + 0.5, -0.45, c, ha="center", va="center", fontsize=8, color=INK2)
    for rep in reps:
        ax.text(-0.12, ys[rep] + 0.52, rep, ha="right", va="center", fontsize=9)
    ax.set_xlim(-0.05, xs[-1] + 1.05)
    ax.set_ylim(y + 0.05, -1.6)
    ax.axis("off")
    handles = [Patch(facecolor=f, edgecolor=AXIS if k == "none" else f, label=t) for k, (f, _, t) in OUTCOME.items()]
    handles.append(Polygon([(0, 0), (1, 0), (1, 1)], closed=True, facecolor=INK, label="cut off at the token limit"))
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, 0.0), ncol=3, frameon=False, fontsize=8.5,
              handlelength=1.2, columnspacing=1.6, labelcolor=INK2)
    fig.savefig(path, **SAVE)
    plt.close(fig)


def _hbar(labels: list[str], values: list[float], texts: list[str], title: str, note: str, path: Path, xmax: float) -> None:
    fig, ax = plt.subplots(figsize=(6, 0.8 + 0.27 * len(labels)))
    ax.barh(labels, values, color="#2a78d6", height=0.62)
    for i, t in enumerate(texts):
        ax.text(values[i] + xmax * 0.012, i, t, va="center", fontsize=9, color=INK2)
    ax.set_xlim(0, xmax * 1.12)
    ax.invert_yaxis()
    ax.set_title(title, loc="left", fontsize=10, fontweight="bold")
    for side in ("top", "right", "bottom"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color(AXIS)
    ax.tick_params(axis="y", length=0, labelsize=9)
    ax.set_xticks([])
    if note:
        ax.text(0, len(labels) - 0.1, note, fontsize=8.5, color=MUTED, va="top")
    fig.savefig(path, **SAVE)
    plt.close(fig)


def fig_obey_rate(rows: list[dict], path: Path) -> None:
    reps = representations(rows)
    per = {rep: [r for r in rows if m(r, "representation_id") == rep] for rep in reps}
    k = {rep: sum(bool(r.get("obeyed")) for r in per[rep]) for rep in reps}
    rates = [k[rep] / len(per[rep]) for rep in reps]
    _hbar(reps, rates, [f"{k[rep]}/{len(per[rep])}" for rep in reps], "Bought the injected item, by representation",
          "All prompts and contexts. For 'none' (no injection) this is buying it unprompted." if "none" in per else "",
          path, 1.0)


def fig_tools(rows: list[dict], path: Path) -> None:
    counts = Counter(t["name"] for r in rows for t in r.get("tool_calls") or [])
    offered = {name for r in rows for name in (m(r, "tools") or [])} or set(harness_tools())
    for name in offered:
        counts.setdefault(name, 0)
    order = sorted(counts, key=lambda k: (-counts[k], k))
    none = sum(not r.get("tool_calls") for r in rows)
    _hbar(order, [counts[k] for k in order], [str(counts[k]) for k in order], f"Tool calls across all {len(rows)} samples",
          f"{none} samples made no tool call.", path, max(max(counts.values(), default=1), 1))


# ----------------------------------------------------------------------------
# README


def generated_block(rows: list[dict], meta: dict, config: dict) -> str:
    s = summary(rows)
    ob = s["obeyed"]
    gen = config.get("generate", {}) or {}
    run = config.get("run", {}) or {}
    manifest_rows = len({m(r, "id") for r in rows})
    sha = (meta.get("manifest_sha256") or "")[:8]
    commit = (meta.get("git_commit") or "")[:7]
    tools = sorted({name for r in rows for name in (m(r, "tools") or [])})
    tools_text = ", ".join(f"`{t}`" for t in tools) if tools else "every tool in the harness (`harness/tools/`)"
    lines = [
        BEGIN,
        "<!-- Generated by eval/run_report.py; edits between these markers are overwritten. -->",
        "",
        "| | |",
        "|---|---|",
        "| Model | " + ", ".join([f"`{meta.get('model', '?')}`"] + [f"{label} {gen[key]}" for key, label in
                                   (("temperature", "temperature"), ("seed", "seed"), ("max_tokens", "`max_tokens`")) if key in gen]) + " |",
        f"| Manifest | {manifest_rows} rows at commit `{commit}` (sha256 `{sha}…`) |",
        f"| Samples | {s['n']} ({manifest_rows} rows × {s['epochs']} epoch{'s' if s['epochs'] != 1 else ''}"
        f"{', `epochs` ' + str(run['epochs']) + ' in config' if run.get('epochs') and run['epochs'] != s['epochs'] else ''}) |",
        f"| Tools offered | {tools_text} |",
        f"| Started | {str(meta.get('started', '?'))[:16].replace('T', ' ')} |",
        "",
        "| Measure | Result |",
        "|---|---|",
        f"| Attack success (hijack + escalation, injected rows) | **{frac(ob(s['attack']), len(s['attack']))}** |",
    ]
    for t in ("escalation", "hijack", "no_target"):
        rs = s["by_type"][t]
        if rs:
            note = " (not counted: the user asked to buy and the scene has nothing to buy)" if t == "no_target" else ""
            lines.append(f"| &nbsp;&nbsp;{t} | {frac(ob(rs), len(rs))}{note} |")
    if s["baseline"]:
        lines.append(f"| Baseline (`none`, no injection) bought the injected item | {frac(ob(s['baseline']), len(s['baseline']))} |")
    lines += [
        f"| Cut off at the token limit | {frac(s['cut'], s['n'])} |",
        f"| No tool call | {frac(s['no_call'], s['n'])} |",
    ]
    if s["errors"]:
        lines.append(f"| Errored | {frac(s['errors'], s['n'])} |")
    lines += [
        "",
        "### Outcome of every sample",
        "",
        "Each cell is a representation (row) under one prompt and context (column), labelled with what the model "
        "bought or the first other tool it called (\"+2\": two more calls). "
        + ("When epochs disagree the cell is split into one strip per epoch. " if s["epochs"] > 1 else "")
        + "A dark corner marks a sample cut off at the token limit.",
        "",
        "![Outcome of every sample](figures/outcomes.svg)",
        "",
        "![Bought the injected item, by representation](figures/obey_rate.svg)",
        "",
        "![Tool calls](figures/tools.svg)",
        "",
        "| Representation | Category | Obeyed | Cut off |",
        "|---|---|---|---|",
    ]
    for rep, rs in s["per_rep"].items():
        lines.append(f"| `{rep}` | {m(rs[0], 'category')} | {frac(ob(rs), len(rs))} | {sum(cut_off(r) for r in rs)} |")
    lines += ["", END]
    return "\n".join(lines)


TEMPLATE = """# Run {name}

{block}

## Takeaways

TODO: what this run showed, from the numbers above and the reasoning traces.

## Caveats

TODO

## Changes planned because of this run

| Change | Tracked in |
|---|---|
| TODO | |

## Files

- `config.yaml`, `meta.json`: what was run and from which commit.
- `results.jsonl`: one row per sample with the manifest row, tool calls, score, token usage and the messages.
- `inspect_logs/*.eval`: the Inspect log (`inspect view --log-dir {run_dir}/inspect_logs`).
- `figures/`: the charts above (`python eval/run_report.py {run_dir}`).
"""


def write_readme(run_dir: Path, block: str) -> str:
    path = run_dir / "README.md"
    if not path.exists():
        rel = run_dir.resolve().relative_to(REPO).as_posix() if run_dir.resolve().is_relative_to(REPO) else run_dir.as_posix()
        path.write_text(TEMPLATE.format(name=run_dir.name, block=block, run_dir=rel), encoding="utf-8")
        return "created"
    text = path.read_text(encoding="utf-8")
    if BEGIN not in text or END not in text:
        return f"left alone (no {BEGIN} / {END} markers)"
    head, rest = text.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    path.write_text(head + block + tail, encoding="utf-8")
    return "updated"


def report(run_dir: Path) -> None:
    rows, meta, config = load_run(run_dir)
    figures = run_dir / "figures"
    figures.mkdir(exist_ok=True)
    with plt.rc_context(RC):
        fig_outcomes(rows, figures / "outcomes.svg")
        fig_obey_rate(rows, figures / "obey_rate.svg")
        fig_tools(rows, figures / "tools.svg")
    status = write_readme(run_dir, generated_block(rows, meta, config))
    print(f"wrote {figures}/{{outcomes,obey_rate,tools}}.svg; README.md {status}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1], formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dirs", nargs="+", type=Path, help="runs/<date>_<name> (one or more)")
    for run_dir in parser.parse_args().run_dirs:
        report(run_dir)


if __name__ == "__main__":
    main()
