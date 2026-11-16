#!/usr/bin/env python3
"""
Interpret-Then-Obey analysis of one harness run.

Reads the Inspect logs in runs/<dir>/inspect_logs/*.eval (through
`inspect_ai.analysis.samples_df`), groups trials by the stimulus factors in
stimuli/manifest.jsonl (docs/SPEC.md section 7) and writes runs/<dir>/analysis/:

- outcomes.html            interactive: one mark per trial, outcome on the y axis,
                           prompt on the x axis, colour = context, shape =
                           representation; hover a mark for its details
- tables.tex               booktabs tables: by representation, by factor, and
                           baseline vs injected per prompt x context

Terms:
- Obeyed (attack success): the scorer saw the expected call, buy(<injected item>).
  Computed on injected rows only.
- Off-target call: a tool call that matched no expected call, e.g. buying the
  product shown in the scene.
- Baseline: representation `none` (category `baseline`), no injection. Reported on
  its own: how often the model bought the injected item anyway, and how often it
  called the tool at all (the reference for off-target calls).

Only P(obey) is measurable: nothing yet labels whether the model interpreted the
payload, so P(interpret) and P(obey | interpret) are not computed.

Usage:
    python eval/analyze_results.py runs/<date>_<name>
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

FACTORS = ["prompt_id", "context_id", "injection_id", "representation_id", "category", "language", "script"]
BASELINE = "baseline"  # manifest `category` of the no-injection control rows

# Factor table in tables.tex: (manifest field, label)
FACTOR_ROWS = [("category", "Category"), ("script", "Script"), ("prompt_id", "Prompt"), ("context_id", "Context")]
LEVEL_ORDER = ["natural", "constructed", "symbols", "latin", "non_latin", "read", "help", "buy"]


# ----------------------------------------------------------------------------
# Loading


def _clean(v):
    """pandas NA/NaN -> None."""
    try:
        import pandas as pd

        if v is None or (not isinstance(v, (list, dict)) and pd.isna(v)):
            return None
    except (TypeError, ValueError):
        pass
    return v


def _json(v, default):
    v = _clean(v)
    if v is None:
        return default
    return json.loads(v) if isinstance(v, str) else v


def _stop_reason(sample):
    out = sample.output
    return out.stop_reason if out and out.choices else None


def merge_logs(trials_per_log: list[list[dict]]) -> list[dict]:
    """A resumed run (`harness.run --resume`) has several logs, oldest first. A later
    result replaces an earlier one for the same (id, epoch) unless that would replace a
    clean result with an error (the same rule harness/export.py uses for results.jsonl)."""
    merged: dict = {}
    for trials in trials_per_log:
        for t in trials:
            key = (t["id"], t["epoch"])
            if key in merged and t["error"] and not merged[key]["error"]:
                continue
            merged[key] = t
    return list(merged.values())


def _trial(rec: dict) -> dict:
    """samples_df record -> trial dict."""
    sm: dict = _json(rec.get("score_obeyed_metadata"), {})
    return {
        "id": rec["id"],
        "epoch": int(rec["epoch"]),
        **{f: _clean(rec.get(f"metadata_{f}")) for f in FACTORS},
        "obeyed": _clean(rec.get("score_obeyed")) == "C",
        "n_matched": sm.get("n_matched") or 0,
        "tool_calls": sm.get("tool_calls") or [],
        "off_target_calls": sm.get("off_target_calls") or [],
        "stop_reason": _clean(rec.get("stop_reason")),
        "error": _clean(rec.get("error")) or None,
        "response": _clean(rec.get("score_obeyed_answer")) or "",
    }


def load_trials(run_dir: Path) -> tuple[list[dict], str | None]:
    """One dict per (sample, epoch) from run_dir/inspect_logs/*.eval, plus the model name."""
    from inspect_ai.analysis import SampleColumn, SampleScores, SampleSummary, samples_df
    from inspect_ai.log import read_eval_log

    log_dir = run_dir / "inspect_logs"
    # Oldest first: filenames start with a timestamp (the order harness/run.py uses too)
    logs = sorted(log_dir.glob("*.eval"))
    if not logs:
        sys.exit(f"Error: no .eval logs in {log_dir}. Run the harness first: just run <config.yaml>")

    columns = SampleSummary + SampleScores + [SampleColumn("stop_reason", path=_stop_reason, full=True)]
    per_log = [[_trial(rec) for rec in samples_df(str(lp), columns=columns, quiet=True).to_dict("records")]
               for lp in logs]
    model = read_eval_log(str(logs[-1]), header_only=True).eval.model
    return merge_logs(per_log), model


# ----------------------------------------------------------------------------
# Statistics


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for k successes out of n."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def is_baseline(t: dict) -> bool:
    return t.get("category") == BASELINE or t.get("representation_id") == "none"


def is_cut_off(t: dict) -> bool:
    return t.get("stop_reason") == "max_tokens"


def outcome(t: dict) -> str:
    if t["error"]:
        return "error"
    if t["obeyed"]:
        return "obeyed"
    if t["off_target_calls"]:
        return "off_target"
    if is_cut_off(t):
        return "cut_off"
    return "no_call"


def summarize(trials: list[dict]) -> dict:
    """Counts for a group of trials."""
    return {
        "n": len(trials),
        "obeyed": sum(t["obeyed"] for t in trials),
        "target_call": sum(t["n_matched"] > 0 for t in trials),
        "off_target": sum(bool(t["off_target_calls"]) for t in trials),
        "any_call": sum(bool(t["tool_calls"]) for t in trials),
        "no_call": sum(not t["tool_calls"] for t in trials),
        "cut_off": sum(is_cut_off(t) for t in trials),
    }


def group_by(trials: list[dict], *fields: str) -> dict:
    """Trials keyed by one field value, or by a tuple of values for several fields."""
    groups: dict = defaultdict(list)
    for t in trials:
        groups[tuple(t.get(f) for f in fields) if len(fields) > 1 else t.get(fields[0])].append(t)
    return dict(groups)


def split(trials: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """(injected, baseline, errored); errored trials are left out of both rates."""
    ok = [t for t in trials if not t["error"]]
    return ([t for t in ok if not is_baseline(t)], [t for t in ok if is_baseline(t)],
            [t for t in trials if t["error"]])


def _order(keys, preferred: list | None = None):
    rank = {k: i for i, k in enumerate(preferred or [])}
    return sorted(keys, key=lambda k: (rank.get(k, len(rank)), str(k)))


def _call_label(calls: list[dict]) -> str:
    """The item for buy calls (the only tool rows get), name(args) for anything else."""
    if not calls:
        return "no call"
    labels = []
    for c in calls:
        args = ", ".join(str(v) for v in (c.get("args") or {}).values())
        labels.append(args if c["name"] == "buy" else f"{c['name']}({args})")
    return ", ".join(labels)


# ----------------------------------------------------------------------------
# Terminal


def pct(k: int, n: int) -> str:
    return f"{k}/{n} ({100 * k / n:.0f}%)" if n else "-"


def headline(trials: list[dict], model: str | None, run_dir: Path) -> str:
    injected, baseline, errored = split(trials)
    si, sb = summarize(injected), summarize(baseline)
    lo, hi = wilson(si["obeyed"], si["n"])
    lines = [
        f"{run_dir}  ({model})",
        f"  injected  {si['n']:>3} trials   obeyed {pct(si['obeyed'], si['n'])}, 95% CI {100 * lo:.0f}-{100 * hi:.0f}%"
        f"   off-target {pct(si['off_target'], si['n'])}",
        f"  baseline  {sb['n']:>3} trials   bought injected item {pct(sb['target_call'], sb['n'])}"
        f"   any call {pct(sb['any_call'], sb['n'])}",
    ]
    if errored:
        lines.append(f"  {len(errored)} errored trial(s) left out")
    lines.append("  P(obey) only: no interpretation label yet, so no P(interpret) or P(obey | interpret).")
    return "\n".join(lines)


# ----------------------------------------------------------------------------
# LaTeX


def _tex(s) -> str:
    s = "--" if s is None else str(s)
    for a, b in [("\\", "\\textbackslash{}"), ("&", "\\&"), ("%", "\\%"), ("_", "\\_"), ("#", "\\#"),
                 ("$", "\\$"), ("{", "\\{"), ("}", "\\}")]:
        s = s.replace(a, b) if a != "\\" else s.replace(a, "\x00")
    return s.replace("\x00", "\\textbackslash{}")


def _rate(k: int, n: int) -> str:
    return f"{k}/{n} ({100 * k / n:.0f}\\%)" if n else "--"


def _ci(k: int, n: int) -> str:
    lo, hi = wilson(k, n)
    return f"{100 * lo:.0f}--{100 * hi:.0f}" if n else "--"


def latex_tables(trials: list[dict], model: str | None, rep_order: list | None = None) -> str:
    """Three booktabs tables. Needs \\usepackage{booktabs} in the preamble."""
    injected, baseline, _ = split(trials)
    m = _tex(model)
    out = [f"% Generated by eval/analyze_results.py for {m}. Needs \\usepackage{{booktabs}}.", ""]

    # 1. By representation
    out += [
        "\\begin{table}[ht]", "\\centering", "\\small",
        f"\\caption{{Attack success by representation ({m}). Obeyed: the model bought the injected item. "
        "Off-target: it called a tool, but not for the injected item. CI: 95\\% Wilson interval. "
        "Baseline: no injection; the first rate is buying the injected item anyway, the second any tool call.}",
        "\\label{tab:by-representation}",
        "\\begin{tabular}{lllrlll}", "\\toprule",
        "Representation & Category & Script & $N$ & Obeyed & 95\\% CI & Off-target \\\\", "\\midrule",
    ]
    groups = group_by(injected, "representation_id")
    for rep in _order(groups, rep_order):
        ts, s = groups[rep], summarize(groups[rep])
        out.append(f"{_tex(rep)} & {_tex(ts[0]['category'])} & {_tex(ts[0]['script'])} & {s['n']} & "
                   f"{_rate(s['obeyed'], s['n'])} & {_ci(s['obeyed'], s['n'])} & {_rate(s['off_target'], s['n'])} \\\\")
    if injected:
        s = summarize(injected)
        out += ["\\midrule", f"All injected & & & {s['n']} & {_rate(s['obeyed'], s['n'])} & "
                f"{_ci(s['obeyed'], s['n'])} & {_rate(s['off_target'], s['n'])} \\\\"]
    if baseline:
        s = summarize(baseline)
        out += ["\\midrule", f"none (baseline) & baseline & -- & {s['n']} & {_rate(s['target_call'], s['n'])} & "
                f"{_ci(s['target_call'], s['n'])} & {_rate(s['any_call'], s['n'])} \\\\"]
    out += ["\\bottomrule", "\\end{tabular}", "\\end{table}", ""]

    # 2. By factor (injected rows)
    out += [
        "\\begin{table}[ht]", "\\centering", "\\small",
        f"\\caption{{Attack success on injected rows by factor ({m}). Script leaves out rows without one "
        "(symbol representations).}",
        "\\label{tab:by-factor}",
        "\\begin{tabular}{llrlll}", "\\toprule",
        "Factor & Level & $N$ & Obeyed & 95\\% CI & Off-target \\\\",
    ]
    for field, label in FACTOR_ROWS:
        groups = group_by(injected, field)
        groups.pop(None, None)
        if not groups:
            continue
        out.append("\\midrule")
        for i, key in enumerate(_order(groups, LEVEL_ORDER)):
            s = summarize(groups[key])
            out.append(f"{label if i == 0 else ''} & {_tex(key)} & {s['n']} & {_rate(s['obeyed'], s['n'])} & "
                       f"{_ci(s['obeyed'], s['n'])} & {_rate(s['off_target'], s['n'])} \\\\")
    out += ["\\bottomrule", "\\end{tabular}", "\\end{table}", ""]

    # 3. Baseline vs injected per prompt x context
    if baseline:
        b_groups, i_groups = group_by(baseline, "prompt_id", "context_id"), group_by(injected, "prompt_id", "context_id")
        out += [
            "\\begin{table}[ht]", "\\centering", "\\small",
            f"\\caption{{Baseline (no injection) against injected rows, per prompt and context ({m}). "
            "Off-target calls on injected rows that the baseline also makes come from the scene or the "
            "request, not the injection.}",
            "\\label{tab:baseline}",
            "\\begin{tabular}{lllll}", "\\toprule",
            "Prompt & Context & Baseline bought & Injected: obeyed & Injected: off-target \\\\", "\\midrule",
        ]
        prev = None
        for key in _order(set(b_groups) | set(i_groups), LEVEL_ORDER):
            b, si = b_groups.get(key, []), summarize(i_groups.get(key, []))
            calls = "; ".join(sorted({_call_label(t["tool_calls"]) for t in b})) or "--"
            prompt = _tex(key[0]) if key[0] != prev else ""
            prev = key[0]
            out.append(f"{prompt} & {_tex(key[1])} & {_tex(calls)} & {_rate(si['obeyed'], si['n'])} & "
                       f"{_rate(si['off_target'], si['n'])} \\\\")
        out += ["\\bottomrule", "\\end{tabular}", "\\end{table}", ""]
    return "\n".join(out)


# ----------------------------------------------------------------------------
# Interactive figure


TEMPLATE = Path(__file__).with_name("outcomes_template.html")


def _js_json(obj) -> str:
    """JSON safe to inline in a <script> block (model replies can contain '</script>')."""
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")


def outcomes_html(trials: list[dict], rep_order: list, model: str | None, run_dir: Path) -> str:
    """Interactive page: one mark per trial. Y is the outcome (closest to success at the
    top), X is the prompt, colour is the context and shape the representation; hovering
    a mark shows the trial's details. Self-contained, no network needed."""
    injected, baseline, errored = split(trials)
    si, sb = summarize(injected), summarize(baseline)
    lo, hi = wilson(si["obeyed"], si["n"])
    stats = [
        [pct(si["obeyed"], si["n"]), f"injected trials obeyed (95% CI {100 * lo:.0f}–{100 * hi:.0f}%)"],
        [pct(si["off_target"], si["n"]), "injected trials with an off-target call"],
        [pct(sb["target_call"], sb["n"]), "baseline trials that bought the injected item"],
        [pct(sb["any_call"], sb["n"]), "baseline trials with any tool call"],
    ]
    if errored:
        stats.append([str(len(errored)), "errored trials (left out of the rates)"])
    data = [
        {
            "id": t["id"], "epoch": t["epoch"], "prompt": t["prompt_id"], "context": t["context_id"],
            "rep": t["representation_id"], "outcome": outcome(t), "stop": t["stop_reason"], "error": t["error"],
            "calls": [_call_label([c]) for c in t["tool_calls"]], "response": (t.get("response") or "")[:2000],
        }
        for t in sorted(trials, key=lambda t: (t["id"], t["epoch"]))
    ]
    meta = {
        "model": model, "run": run_dir.name, "stats": stats,
        "prompts": _order({t["prompt_id"] for t in trials}, LEVEL_ORDER),
        "contexts": _order({t["context_id"] for t in trials}),
        "reps": _order({t["representation_id"] for t in trials}, rep_order),
        "epochs": max(t["epoch"] for t in trials),
    }
    page = TEMPLATE.read_text(encoding="utf-8")
    return page.replace("__DATA__", _js_json(data)).replace("__META__", _js_json(meta))


# ----------------------------------------------------------------------------
# Main


def manifest_order(path: Path) -> list:
    """representation_id order as it appears in the manifest (english first, none last)."""
    order: list = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rep = json.loads(line).get("representation_id")
                if rep not in order:
                    order.append(rep)
    except OSError:
        pass
    return sorted(order, key=lambda r: r == "none")  # stable: keeps manifest order, baseline last


def analyze(run_dir: Path, manifest: Path | None = None) -> list[Path]:
    """Print the headline and write the figures and tables; returns the written paths."""
    trials, model = load_trials(run_dir)
    if not any(not t["error"] for t in trials):
        sys.exit(f"No successful samples in {run_dir / 'inspect_logs'} ({len(trials)} errored)")
    if manifest is None:
        meta = run_dir / "meta.json"
        manifest = Path(json.loads(meta.read_text())["manifest"]) if meta.exists() else Path("stimuli/manifest.jsonl")
    rep_order = manifest_order(manifest)

    out_dir = run_dir / "analysis"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "tables.tex").write_text(latex_tables(trials, model, rep_order), encoding="utf-8")
    (out_dir / "outcomes.html").write_text(outcomes_html(trials, rep_order, model, run_dir), encoding="utf-8")
    written = [out_dir / "outcomes.html", out_dir / "tables.tex"]

    print(headline(trials, model, run_dir))
    print("\nWrote " + ", ".join(str(p.relative_to(run_dir)) for p in written))
    print("Open outcomes.html in a browser; hover a mark for the trial's details.")
    return written


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", type=Path, help="harness run directory, e.g. runs/2026-11-15_qwen3vl-8b-ollama")
    ap.add_argument("--manifest", type=Path, help="manifest for representation order (default: the one in meta.json)")
    args = ap.parse_args()
    analyze(args.run_dir, args.manifest)
