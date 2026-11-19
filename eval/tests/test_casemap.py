"""eval/casemap.py: the per-case records, run labels and factor order behind the case map page.
Run from repo root: python -m pytest eval/tests -q"""

import json
from pathlib import Path

from eval.casemap import load_factors, run_labels, write_casemap
from eval.tests.trials import BEAR, MUG, trial


def test_write_casemap_has_one_case_per_id_with_a_strip_per_run(tmp_path):
    kept, dropped = trial("english", BEAR), trial("pictograms", [MUG], prompt="read")
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(json.dumps({"id": kept["id"]}) + "\n", encoding="utf-8")
    runs = {Path("runs/2026-11-17_m"): [trial("english", [MUG]), dropped], Path("runs/2026-11-16_m"): [kept]}
    page = write_casemap(runs, tmp_path / "casemap.html", manifest).read_text(encoding="utf-8")

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
