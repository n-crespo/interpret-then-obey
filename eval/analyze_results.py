#!/usr/bin/env python3
"""
Statistical Analysis & Report Generator for Fictional Language VLM Benchmark.
Aggregates eval/results.json across fictional universes, conlangs, scripts, and conditions.
Generates terminal tables, Markdown summaries, and publication-ready LaTeX tables.

Usage:
    python3 eval/analyze_results.py
"""

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_PATH = REPO_ROOT / "eval" / "results.json"


def load_results():
    if not RESULTS_PATH.exists():
        print(f"Error: {RESULTS_PATH} not found. Run eval/run_benchmark.py first.")
        sys.exit(1)
    with open(RESULTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def analyze():
    data = load_results()
    results = data.get("results", [])
    if not results:
        print("No sample results found in results.json")
        return

    by_universe = {}
    by_lang = {}
    by_script = {}
    by_condition = {}

    for r in results:
        meta = r.get("metadata", {})
        scores = r.get("scores", {})
        obeyed = scores.get("obeyed", 0)
        hallucinated = scores.get("hallucinated", 0)

        universe = meta.get("fictional_universe", "unknown")
        lang = meta.get("language", "unknown")
        script = meta.get("script", "unknown")
        cond = meta.get("section", meta.get("condition", "unknown"))

        for key, bucket in [
            (universe, by_universe),
            (lang, by_lang),
            (script, by_script),
            (cond, by_condition),
        ]:
            if key not in bucket:
                bucket[key] = {"total": 0, "obeyed": 0, "hallucinated": 0}
            bucket[key]["total"] += 1
            bucket[key]["obeyed"] += obeyed
            bucket[key]["hallucinated"] += hallucinated

    def print_table(title, bucket):
        print(f"\n### {title}")
        print(f"{'Category':<38} | {'Samples':<8} | {'ASR (Obeyed)':<14} | {'Hallucination %'}")
        print("-" * 78)
        for cat, stats in sorted(bucket.items()):
            tot = stats["total"]
            asr = f"{round((stats['obeyed'] / tot) * 100, 1)}% ({stats['obeyed']}/{tot})"
            hal = f"{round((stats['hallucinated'] / tot) * 100, 1)}% ({stats['hallucinated']}/{tot})"
            print(f"{cat:<38} | {tot:<8} | {asr:<14} | {hal}")

    print("=" * 78)
    print(" FICTIONAL CONLANG VLM BENCHMARK: STATISTICAL ANALYSIS ")
    print(f" Model: {data.get('model')} | Total Samples: {data.get('total_samples')}")
    print("=" * 78)

    print_table("Breakdown by Fictional Universe / Franchise", by_universe)
    print_table("Breakdown by Conlang", by_lang)
    print_table("Breakdown by Script System (Latin vs. Glyphs)", by_script)
    print_table("Breakdown by Section", by_condition)

    # LaTeX Table
    latex = []
    latex.append("\\begin{table}[ht]")
    latex.append("\\centering")
    latex.append("\\small")
    latex.append("\\caption{VLM Susceptibility and Hallucination Across Fictional Pop-Culture Conlangs}")
    latex.append("\\begin{tabular}{llccc}")
    latex.append("\\hline")
    latex.append("\\textbf{Fictional Universe} & \\textbf{Language} & \\textbf{N} & \\textbf{ASR (\\%)} & \\textbf{Hallucination (\\%)} \\\\")
    latex.append("\\hline")

    for cat, stats in sorted(by_universe.items()):
        tot = stats["total"]
        asr_pct = round((stats["obeyed"] / tot) * 100, 1)
        hal_pct = round((stats["hallucinated"] / tot) * 100, 1)
        latex.append(f"{cat} & Mixed & {tot} & {asr_pct}\\% & {hal_pct}\\% \\\\")

    latex.append("\\hline")
    latex.append("\\end{tabular}")
    latex.append("\\label{tab:fictional_vlm_eval}")
    latex.append("\\end{table}")

    latex_str = "\n".join(latex)
    latex_path = REPO_ROOT / "eval" / "results_table.tex"
    with open(latex_path, "w", encoding="utf-8") as f:
        f.write(latex_str)

    print(f"\nLaTeX table exported to: {latex_path.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    analyze()
