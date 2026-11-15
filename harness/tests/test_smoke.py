"""GPU-free checks of manifest loading, tools, scorer, export and the run CLI, using Inspect's
mock model. Everything is written under pytest's tmp_path. Run from repo root:  just test"""

import importlib.util
import json
import os
import re
from pathlib import Path

import PIL
import pytest
import yaml
from inspect_ai import eval as inspect_eval
from inspect_ai.model import ModelOutput, ModelUsage, get_model

from harness import run as harness_run
from harness.export import export_results
from harness.fixtures.make_fixtures import make_fixtures
from harness.obey import check_obeyed
from harness.task import build_task

ROOT = Path(__file__).resolve().parents[2]
STIMULI = ROOT / "stimuli"
REAL_MANIFEST = STIMULI / "manifest.jsonl"
DRY_RUN_CONFIG = ROOT / "harness" / "configs" / "qwen3vl-8b-ollama.yaml"  # what `just run-dry` uses
FACTOR_FIELDS = ("prompt_id", "context_id", "injection_id", "representation_id", "category", "language", "script")

_pin = re.search(r"^pillow==(\S+)", (STIMULI / "requirements.txt").read_text(encoding="utf-8"), re.M | re.I)
assert _pin is not None, "stimuli/requirements.txt must pin pillow=="
PINNED_PILLOW = _pin.group(1)


def _load_generate():
    spec = importlib.util.spec_from_file_location("stimuli_generate", STIMULI / "generate.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_obey_logic():
    calls = [{"name": "add_to_cart", "args": {"item": "Ripe BANANA"}}]
    assert check_obeyed(calls, [{"name": "add_to_cart", "args": {"item": "banana"}}])["obeyed"]
    assert not check_obeyed(calls, [{"name": "send_message", "args": {}}])["obeyed"]
    assert not check_obeyed(calls, [])["obeyed"]  # control rows are never "obeyed"


def test_fixture_manifest(tmp_path):
    manifest = make_fixtures(tmp_path / "fixtures")
    rows = {r["id"]: r for r in map(json.loads, manifest.read_text(encoding="utf-8").splitlines())}
    assert "image" not in rows["fx-en-text-obey"]
    assert rows["fx-control-nopayload"]["expected_calls"] == []
    assert all("\\" not in r.get("image", "") for r in rows.values())
    assert b"\r\n" not in manifest.read_bytes()


def test_end_to_end(tmp_path):
    manifest = make_fixtures(tmp_path / "fixtures")
    outputs = [
        ModelOutput.for_tool_call("mockllm/model", "buy", {"item": "banana"}),  # row 1: obeys
        ModelOutput.from_content("mockllm/model", "Done."),                     # row 1 follow-up
        ModelOutput.from_content("mockllm/model", "It's a note."),              # row 2: ignores
        ModelOutput.from_content("mockllm/model", "Open 9 to 5."),              # row 3: control
    ]
    for o in outputs:  # explicit usage: mockllm otherwise downloads a tiktoken file to estimate it
        o.usage = ModelUsage(input_tokens=1, output_tokens=1, total_tokens=2)
    model = get_model("mockllm/model", custom_outputs=outputs)
    logs = inspect_eval(build_task(str(manifest)), model=model, log_dir=str(tmp_path / "logs"),
                        max_connections=1, display="none")
    assert logs[0].status == "success"
    out = tmp_path / "results.jsonl"
    assert export_results(logs[0].location, out) == 3
    rows = {r["id"]: r for r in map(json.loads, out.read_text(encoding="utf-8").splitlines())}
    assert rows["fx-en-image-obey"]["obeyed"] is True
    assert rows["fx-en-text-obey"]["obeyed"] is False
    assert rows["fx-control-nopayload"]["obeyed"] is False
    assert rows["fx-en-image-obey"]["manifest_row"]["injection_id"] == "buy_banana"


def test_dry_run_real_manifest(tmp_path, monkeypatch):
    """`just run-dry --limit 3` over the committed stimuli/manifest.jsonl, writing only to tmp_path.

    The images are gitignored and `just test` does not build them, so the test renders them
    into tmp_path with stimuli/generate.py and points the loader there. It renders every row,
    not just `limit`: load_manifest resolves and hash-checks all images before --limit applies.
    """
    if PIL.__version__ != PINNED_PILLOW and not os.environ.get("CI"):
        pytest.skip(f"image hashes only match on the pinned Pillow {PINNED_PILLOW} (CI always runs this)")
    limit = 3
    want = [json.loads(line) for line in REAL_MANIFEST.read_text(encoding="utf-8").splitlines()[:limit]]

    gen = _load_generate()
    factors = [gen.load_json(gen.SRC_DIR / f) for f in ("prompts.json", "context.json", "injections.json", "representations.json")]
    for row, render_args in gen.build_rows(*factors, images_rel="stimuli/images"):
        gen.render_stimulus_image(tmp_path / row["image"], *render_args)

    cfg = yaml.safe_load(DRY_RUN_CONFIG.read_text(encoding="utf-8"))
    cfg["image_root"] = str(tmp_path)  # searched before the repo, so a stale stimuli/images/ is never used
    cfg_path = tmp_path / "dry-run.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")

    # mockllm estimates token usage with tiktoken, which downloads its encoding on first use.
    async def _count_text_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)

    from inspect_ai.model._providers.mockllm import MockLLM
    monkeypatch.setattr(MockLLM, "count_text_tokens", _count_text_tokens)

    runs_before = sorted(p.name for p in (ROOT / "runs").glob("*"))
    harness_run.main([str(cfg_path), "--manifest", str(REAL_MANIFEST), "--model", "mockllm/model",
                      "--limit", str(limit), "--runs-dir", str(tmp_path / "runs")])
    assert sorted(p.name for p in (ROOT / "runs").glob("*")) == runs_before, "dry run wrote into runs/"

    (run_dir,) = (tmp_path / "runs").iterdir()
    results = [json.loads(line) for line in (run_dir / "results.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["id"] for r in results] == [r["id"] for r in want]
    for got, row in zip(results, want):
        assert got["run_status"] == "success"
        assert got["error"] is None, got["error"]
        assert got["model"] == "mockllm/model"
        assert got["obeyed"] is False  # mockllm only replies with text
        for k in ("expected_calls", "tools", *FACTOR_FIELDS):
            assert got["manifest_row"][k] == row[k], (row["id"], k)
