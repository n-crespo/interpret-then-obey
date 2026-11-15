"""GPU-free checks of manifest loading, tools, scorer and export, using Inspect's
mock model. Everything is written under pytest's tmp_path. Run from repo root:  just test"""

import json

from inspect_ai import eval as inspect_eval
from inspect_ai.model import ModelOutput, ModelUsage, get_model

from harness.export import export_results
from harness.fixtures.make_fixtures import make_fixtures
from harness.obey import check_obeyed
from harness.task import build_task

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

