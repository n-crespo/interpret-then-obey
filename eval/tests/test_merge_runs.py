"""eval/merge_runs: two mock-model runs merged into one folder that load_trials reads as one
run, with a renamed context mapped and a row the manifest lacks dropped.
Run from repo root: python -m pytest eval/tests -q"""

import json

from inspect_ai import eval as inspect_eval
from inspect_ai.model import ModelOutput, get_model

from eval.merge_runs import merge_runs
from eval.tests.test_analyze import _manifest, _out
from eval.trials import load_trials
from harness.task import build_task

OLD = "read.library_board.buy_shoe.english"  # ran as info_board
GONE = "read.library_board.buy_shoe.spanish"  # stands in for a row today's manifest lacks
NEW = "buy.product_info.buy_shoe.english"


def _run(run_dir, rows):
    manifest = run_dir / "manifest.jsonl"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    outputs = [_out(ModelOutput.from_content("mockllm/model", "Done.")) for _ in rows]
    inspect_eval(build_task(str(manifest), verify_hashes=False), model=get_model("mockllm/model", custom_outputs=outputs),
                 log_dir=str(run_dir / "inspect_logs"), max_connections=1, display="none")


def test_merged_runs_read_as_one_run_of_the_manifest(tmp_path):
    rows = {r["id"]: r for r in map(json.loads, _manifest(tmp_path, [OLD, GONE, NEW]).read_text().splitlines())}
    old = [{**rows[i], "id": i.replace("library_board", "info_board"), "context_id": "info_board"} for i in (OLD, GONE)]
    _run(tmp_path / "runs/a", old)
    _run(tmp_path / "runs/b", [rows[NEW]])
    manifest = tmp_path / "today.jsonl"
    manifest.write_text("\n".join(json.dumps(rows[i]) for i in (OLD, NEW)), encoding="utf-8")

    counts = merge_runs(tmp_path / "runs/merged", [tmp_path / "runs/a", tmp_path / "runs/b"], manifest)
    assert counts == {"a": {"kept": 1, "dropped": 1}, "b": {"kept": 1}}

    trials, _ = load_trials(tmp_path / "runs/merged")
    assert {(t["id"], t["context_id"]) for t in trials} == {(OLD, "library_board"), (NEW, "product_info")}
    assert all(t["outcome"] != "harness_error" for t in trials)
