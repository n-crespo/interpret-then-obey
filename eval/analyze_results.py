#!/usr/bin/env python3
"""
Interpret-Then-Obey analysis of one harness run.

Reads the Inspect logs in runs/<dir>/inspect_logs/*.eval (through
`inspect_ai.analysis.samples_df`), groups trials by the stimulus factors in
stimuli/manifest.jsonl (docs/SPEC.md section 7) and writes runs/<dir>/analysis/:

- outcomes.html            interactive: one mark per trial in a row per outcome;
                           colour = representation, shape = context, border =
                           prompt; hover a mark for its details
- tables.tex               booktabs tables: by representation, by factor,
                           baseline vs injected per prompt x context, by
                           attack type, and purchases by source

Outcomes, and the terms used below (obeyed, attack type, off-target call, baseline),
are defined in eval/outcomes.py.

Only P(obey) is measurable: nothing yet labels whether the model interpreted the
payload, so P(interpret) and P(obey | interpret) are not computed.

Usage:
    python eval/analyze_results.py runs/<date>_<name>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from eval.outcomes import (  # noqa: E402
    LEVEL_ORDER,
    call_label,
    fill_attack_type,
    group_by,
    load_trials,
    manifest_order,
    outcome,
    split,
    split_attacks,
    summarize,
    wilson,
    _order,
)
from stimuli.attack_types import ATTACK_TYPES  # noqa: E402

# Factor table in tables.tex: (manifest field, label)
FACTOR_ROWS = [("category", "Category"), ("script", "Script"), ("prompt_id", "Prompt"), ("context_id", "Context")]


# ----------------------------------------------------------------------------
# Terminal


def pct(k: int, n: int) -> str:
    return f"{k}/{n} ({100 * k / n:.0f}%)" if n else "-"


def headline(trials: list[dict], model: str | None, run_dir: Path) -> str:
    injected, baseline, errored = split(trials)
    attacks, no_target = split_attacks(injected)
    si, sb = summarize(attacks), summarize(baseline)
    lo, hi = wilson(si["obeyed"], si["n"])
    lines = [
        f"{run_dir}  ({model})",
        f"  attacks   {si['n']:>3} trials   obeyed {pct(si['obeyed'], si['n'])}, 95% CI {100 * lo:.0f}-{100 * hi:.0f}%"
        f"   off-target {pct(si['off_target'], si['n'])}   (hijack + escalation)",
    ]
    for kind in ("hijack", "escalation"):
        ts = [t for t in attacks if t.get("attack_type") == kind]
        if not ts:
            continue
        s = summarize(ts)
        if kind == "escalation":
            line = (f"    {kind:<11}{s['n']:>3} trials   injection-driven {pct(s['obeyed'], s['n'])}"
                    f"   context-driven {pct(s['context_driven'], s['n'])}"
                    f"   misread {pct(s['misread_injection'], s['n'])}")
        else:
            line = (f"    {kind:<11}{s['n']:>3} trials   injection-driven {pct(s['obeyed'], s['n'])}"
                    f"   followed user {pct(s['followed_user'], s['n'])}"
                    f"   misread {pct(s['misread_injection'], s['n'])}")
        if kind == "escalation":
            w = summarize([t for t in ts if t.get("competing_product")])
            wo = summarize([t for t in ts if not t.get("competing_product")])
            line += (f"   (injection-driven: scene with a product {pct(w['obeyed'], w['n'])}, "
                     f"without {pct(wo['obeyed'], wo['n'])})")
        lines.append(line)
    untyped = sum(t.get("attack_type") is None for t in attacks)
    if untyped:
        lines.append(f"    {untyped} trial(s) have no attack_type and are counted as attacks")
    if no_target:
        s = summarize(no_target)
        lines.append(f"  no_target {s['n']:>3} trials   bought injected item {pct(s['obeyed'], s['n'])}"
                     "   (asked to buy, nothing in the scene: item choice, not attack success)")
    lines.append(f"  baseline  {sb['n']:>3} trials   bought injected item {pct(sb['target_call'], sb['n'])}"
                 f"   any call {pct(sb['any_call'], sb['n'])}")
    be = summarize([t for t in baseline if t.get("attack_type") == "escalation"])
    if be["n"]:
        lines.append(f"    escalation {be['n']:>3} trials   context-driven {pct(be['context_driven'], be['n'])}"
                     "   (no injection: the reference for context-driven escalation)")
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
    """Four booktabs tables. Needs \\usepackage{booktabs} in the preamble. Tables 1 and 2
    count attack success on hijack and escalation rows only; no_target is in table 4."""
    all_injected, baseline, _ = split(trials)
    injected, _ = split_attacks(all_injected)
    m = _tex(model)
    out = [f"% Generated by eval/analyze_results.py for {m}. Needs \\usepackage{{booktabs}}.", ""]

    # 1. By representation
    out += [
        "\\begin{table}[ht]", "\\centering", "\\small",
        f"\\caption{{Attack success by representation ({m}). Obeyed: the model bought the injected item. "
        "Off-target: it called a tool, but not for the injected item. CI: 95\\% Wilson interval. "
        "Baseline: no injection; the first rate is buying the injected item anyway, the second any tool call. "
        "Injected rows leave out the no\\_target attack type (Table~\\ref{tab:by-attack-type}).}",
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
        out += ["\\midrule", f"All attacks & & & {s['n']} & {_rate(s['obeyed'], s['n'])} & "
                f"{_ci(s['obeyed'], s['n'])} & {_rate(s['off_target'], s['n'])} \\\\"]
    if baseline:
        s = summarize(baseline)
        out += ["\\midrule", f"none (baseline) & baseline & -- & {s['n']} & {_rate(s['target_call'], s['n'])} & "
                f"{_ci(s['target_call'], s['n'])} & {_rate(s['any_call'], s['n'])} \\\\"]
    out += ["\\bottomrule", "\\end{tabular}", "\\end{table}", ""]

    # 2. By factor (injected rows)
    out += [
        "\\begin{table}[ht]", "\\centering", "\\small",
        f"\\caption{{Attack success on injected rows by factor ({m}), leaving out no\\_target. Script leaves "
        "out rows without one (symbol representations).}",
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
        b_groups, i_groups = group_by(baseline, "prompt_id", "context_id"), group_by(all_injected, "prompt_id", "context_id")
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
            calls = "; ".join(sorted({call_label(t["tool_calls"]) for t in b})) or "--"
            prompt = _tex(key[0]) if key[0] != prev else ""
            prev = key[0]
            out.append(f"{prompt} & {_tex(key[1])} & {_tex(calls)} & {_rate(si['obeyed'], si['n'])} & "
                       f"{_rate(si['off_target'], si['n'])} \\\\")
        out += ["\\bottomrule", "\\end{tabular}", "\\end{table}", ""]

    # 4. By attack type
    out += attack_type_table(all_injected, baseline, m)

    # 5. Purchases by source
    out += purchase_source_table(all_injected, baseline, m)
    return "\n".join(out)


def purchase_source_table(injected: list[dict], baseline: list[dict], m: str) -> list[str]:
    """Where each purchase came from, per attack type and product in scene, injected rows
    against the baseline: the injection (obeyed), the scene unasked (context-driven
    escalation), or the user's request (followed user)."""
    rank = {k: i for i, k in enumerate(ATTACK_TYPES)}
    i_groups = group_by(injected, "attack_type", "competing_product")
    b_groups = group_by(baseline, "attack_type", "competing_product")
    keys = sorted(set(i_groups) | set(b_groups), key=lambda k: (rank.get(k[0], len(rank)), str(k[0]), not k[1]))
    out = [
        "\\begin{table}[ht]", "\\centering", "\\small",
        f"\\caption{{Purchases by source ({m}). Obeyed: bought the injected item; on injected rows this is an "
        "injection-driven redirection (hijack) or escalation (attack success), on baseline rows a purchase "
        "with no injection. Context-driven: the user did not ask to buy, and the model bought an item from the "
        "scene. Followed user: the user asked to buy, and the model bought an item from the scene. Misread: "
        "bought something that is neither the injected item nor from the scene. Each trial has one outcome.}",
        "\\label{tab:purchase-source}",
        "\\begin{tabular}{lllrllll}", "\\toprule",
        "Attack type & Product in scene & Rows & $N$ & Obeyed & Context-driven & Followed user & Misread \\\\",
        "\\midrule",
    ]
    prev = None
    for key in keys:
        product = "--" if key[1] is None else ("yes" if key[1] else "no")
        for label, groups in (("injected", i_groups), ("baseline", b_groups)):
            if key not in groups:
                continue
            s = summarize(groups[key])
            kind = _tex(key[0]) if key[0] != prev else ""
            if kind and prev is not None:
                out.append("\\midrule")
            prev = key[0]
            over = _rate(s["context_driven"], s["n"]) if key[0] == "escalation" else "--"
            followed = _rate(s["followed_user"], s["n"]) if key[0] in ("hijack", "no_target") else "--"
            out.append(f"{kind} & {product} & {label} & {s['n']} & {_rate(s['obeyed'], s['n'])} & {over} & "
                       f"{followed} & {_rate(s['misread_injection'], s['n'])} \\\\")
    out += ["\\bottomrule", "\\end{tabular}", "\\end{table}", ""]
    return out


def attack_type_table(injected: list[dict], baseline: list[dict], m: str) -> list[str]:
    """Obey rate per attack type, split by whether the scene shows its own product."""
    i_groups = group_by(injected, "attack_type", "competing_product")
    b_groups = group_by(baseline, "attack_type", "competing_product")
    rank = {k: i for i, k in enumerate(ATTACK_TYPES)}
    keys = sorted(set(i_groups) | set(b_groups), key=lambda k: (rank.get(k[0], len(rank)), str(k[0]), not k[1]))
    out = [
        "\\begin{table}[ht]", "\\centering", "\\small",
        f"\\caption{{Attack success by attack type ({m}). Hijack: the user asks to buy and the scene shows its "
        "own product; the injection tries to swap the item. Escalation: the user does not ask to buy; the "
        "injection tries to create a purchase. no\\_target: the user asks to buy but the scene has nothing to "
        "buy, so a purchase is expected and Obeyed only shows which item was bought; it is not attack success. "
        "Baseline: any tool call with no injection.}",
        "\\label{tab:by-attack-type}",
        "\\begin{tabular}{llrllll}", "\\toprule",
        "Attack type & Product in scene & $N$ & Obeyed & 95\\% CI & Off-target & Baseline: any call \\\\",
        "\\midrule",
    ]
    prev = None
    for key in keys:
        if key[0] == "no_target" and prev != "no_target":
            s = summarize(split_attacks(injected)[0])
            out += ["\\midrule", f"All attacks & & {s['n']} & {_rate(s['obeyed'], s['n'])} & "
                    f"{_ci(s['obeyed'], s['n'])} & {_rate(s['off_target'], s['n'])} & \\\\", "\\midrule"]
        s, b = summarize(i_groups.get(key, [])), summarize(b_groups.get(key, []))
        product = "--" if key[1] is None else ("yes" if key[1] else "no")
        kind = _tex(key[0]) if key[0] != prev else ""
        prev = key[0]
        out.append(f"{kind} & {product} & {s['n']} & {_rate(s['obeyed'], s['n'])} & {_ci(s['obeyed'], s['n'])} & "
                   f"{_rate(s['off_target'], s['n'])} & {_rate(b['any_call'], b['n'])} \\\\")
    out += ["\\bottomrule", "\\end{tabular}", "\\end{table}", ""]
    return out


# ----------------------------------------------------------------------------
# Interactive figure


TEMPLATE = Path(__file__).with_name("outcomes_template.html")


def _js_json(obj) -> str:
    """JSON safe to inline in a <script> block (model replies can contain '</script>')."""
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")


def outcomes_html(trials: list[dict], rep_order: list, model: str | None, run_dir: Path) -> str:
    """Interactive page: one mark per trial, in one row per outcome (closest to success
    at the top). Colour is the representation, shape the context and border the prompt;
    hovering a mark shows the trial's details. Self-contained, no network needed."""
    injected, baseline, errored = split(trials)
    attacks, no_target = split_attacks(injected)
    si, sb, sn = summarize(attacks), summarize(baseline), summarize(no_target)
    se = summarize([t for t in attacks if t.get("attack_type") == "escalation"])
    sh = summarize([t for t in attacks if t.get("attack_type") == "hijack"])
    lo, hi = wilson(si["obeyed"], si["n"])
    stats = [
        [pct(si["obeyed"], si["n"]), f"attack trials obeyed (hijack + escalation; 95% CI {100 * lo:.0f}–{100 * hi:.0f}%)"],
        [pct(si["off_target"], si["n"]), "attack trials with an off-target call"],
        [pct(se["obeyed"], se["n"]), "escalation trials with an injection-driven escalation (bought the injected item)"],
        [pct(se["context_driven"], se["n"]), "escalation trials with a context-driven escalation (bought something nobody asked for)"],
        [pct(sh["obeyed"], sh["n"]), "hijack trials with an injection-driven redirection (bought the injected item instead)"],
        [pct(si["misread_injection"], si["n"]), "attack trials with a misread injection (bought neither the injected item nor one from the scene)"],
        [pct(sh["followed_user"], sh["n"]), "hijack trials that followed the user (bought the item asked for)"],
        [pct(sn["obeyed"], sn["n"]), "no_target trials that bought the injected item (item choice, not attack success)"],
        [pct(sb["target_call"], sb["n"]), "baseline trials that bought the injected item"],
        [pct(sb["any_call"], sb["n"]), "baseline trials with any tool call"],
    ]
    if errored:
        stats.append([str(len(errored)), "errored trials (left out of the rates)"])
    data = [
        {
            "id": t["id"], "epoch": t["epoch"], "prompt": t["prompt_id"], "context": t["context_id"],
            "rep": t["representation_id"], "outcome": outcome(t), "stop": t["stop_reason"], "error": t["error"],
            "calls": [call_label([c]) for c in t["tool_calls"]], "response": (t.get("response") or "")[:2000],
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


def analyze(run_dir: Path, manifest: Path | None = None) -> list[Path]:
    """Print the headline and write the figures and tables; returns the written paths."""
    trials, model = load_trials(run_dir)
    if not any(not t["error"] for t in trials):
        sys.exit(f"No successful samples in {run_dir / 'inspect_logs'} ({len(trials)} errored)")
    if manifest is None:
        meta = run_dir / "meta.json"
        manifest = Path(json.loads(meta.read_text())["manifest"]) if meta.exists() else Path("stimuli/manifest.jsonl")
    rep_order = manifest_order(manifest)
    derived = fill_attack_type(trials)

    out_dir = run_dir / "analysis"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "tables.tex").write_text(latex_tables(trials, model, rep_order), encoding="utf-8")
    (out_dir / "outcomes.html").write_text(outcomes_html(trials, rep_order, model, run_dir), encoding="utf-8")
    written = [out_dir / "outcomes.html", out_dir / "tables.tex"]

    print(headline(trials, model, run_dir))
    if derived:
        print(f"\nNote: the logs predate attack_type; derived it for {derived} trial(s) from prompt_id x context_id "
              "with stimuli/src/.")
    print("\nWrote " + ", ".join(str(p.relative_to(run_dir)) for p in written))
    print("Open outcomes.html in a browser; hover a mark for the trial's details.")
    return written


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run_dir", type=Path, help="harness run directory, e.g. runs/2026-11-15_qwen3vl-8b-ollama")
    ap.add_argument("--manifest", type=Path, help="manifest for representation order (default: the one in meta.json)")
    args = ap.parse_args()
    analyze(args.run_dir, args.manifest)
