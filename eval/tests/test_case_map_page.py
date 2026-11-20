"""eval/case_map_page.py: the per-case records, run labels and factor order behind the case map page.
Run from repo root: python -m pytest eval/tests -q"""

import json
import re
from pathlib import Path

from eval.case_map_page import TEMPLATE, load_factors, run_labels, write_case_map
from eval.summary_page import TEMPLATE as SUMMARY_TEMPLATE, write_summary
from eval.tests.trials import BEAR, MUG, trial


def test_write_case_map_has_one_case_per_id_with_a_strip_per_run(tmp_path):
    kept, dropped = trial("english", BEAR), trial("pictograms", [MUG], prompt="read")
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({"id": kept["id"]}) + "\n", encoding="utf-8")
    runs = {Path("runs/2026-11-17_m"): [trial("english", [MUG]), dropped], Path("runs/2026-11-16_m"): [kept]}
    page = write_case_map(runs, tmp_path / "case_map.html", manifest).read_text(encoding="utf-8")

    meta = json.loads(page.split("const META = ", 1)[1].split(";\n", 1)[0])
    cases = {c["id"]: c for c in json.loads(page.split("const DATA = ", 1)[1].split(";\nconst META", 1)[0])}
    assert meta["runs"] == ["2026-11-17", "2026-11-16"]  # in the order given
    assert {r: [x["o"] for x in ts] for r, ts in cases[kept["id"]]["runs"].items()} == {
        "2026-11-17": ["followed_user"], "2026-11-16": ["hijack"]}
    assert (cases[kept["id"]]["in_manifest"], cases[dropped["id"]]["in_manifest"]) == (True, False)


def test_run_labels_drop_the_parts_every_run_shares():
    dirs = [Path("runs/2026-11-16_qwen3vl-8b-ollama_074940"), Path("runs/2026-11-17_qwen3vl-8b-ollama")]
    assert run_labels(dirs) == ["2026-11-16_074940", "2026-11-17"]


def test_load_factors_keeps_the_order_of_stimuli_src(tmp_path):
    (tmp_path / "prompts.json").write_text(json.dumps({"z": {"text": "Zed."}, "a": {"text": "Ay."}}))
    (tmp_path / "context.json").write_text(json.dumps({"ctx2": {}, "ctx1": {}}))
    (tmp_path / "representations.json").write_text(json.dumps({"r2": {}, "r1": {}}))
    f = load_factors(tmp_path)
    assert ([p["id"] for p in f["prompts"]], f["contexts"], f["reps"]) == (["z", "a"], ["ctx2", "ctx1"], ["r2", "r1"])


def test_page_escapes_script_tags_in_replies(tmp_path):
    t = trial("english", [MUG])
    t["response"] = "ignore </script><script>alert(1)</script>"
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({"id": t["id"]}) + "\n", encoding="utf-8")
    page = write_case_map({Path("runs/x"): [t]}, tmp_path / "case_map.html", manifest).read_text(encoding="utf-8")
    assert page.count("</script>") == TEMPLATE.read_text(encoding="utf-8").count("</script>")  # only the page's own


def test_summary_gives_every_trial_an_outcome_the_page_knows(tmp_path):
    trials = [trial("english", BEAR), trial("english", [MUG]), trial("english"), trial("english", prompt="read"),
              trial("english", BEAR, prompt="buy", context="info_board"), trial("english", error="boom"),
              trial("english", prompt="read", stop_reason="max_tokens")]
    page = write_summary(trials, "m", Path("runs/x"), tmp_path / "summary.html").read_text(encoding="utf-8")
    rows = json.loads(page.split("const DATA = ", 1)[1].split(";\n", 1)[0])["rows"]
    known = set(re.findall(r'\{id: "(\w+)", v:', SUMMARY_TEMPLATE.read_text(encoding="utf-8")))
    assert len(rows) == len(trials) and all(r["k"] in known for r in rows)
    assert {r["k"] for r in rows} >= {"hijack", "followed_user", "no_buy_asked", "declined", "injected_choice"}
