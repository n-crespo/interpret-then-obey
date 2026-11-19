"""eval/casemap.py: the per-case records, run labels and factor order behind the case map page.
Run from repo root: python -m pytest eval/tests -q"""

import json
from pathlib import Path

from eval.casemap import casemap_html, build_cases, load_factors, run_labels
from eval.tests.test_analyze_results import BEAR, MUG, trial


def _case(cases, id_):
    return next(c for c in cases if c["id"] == id_)


def test_build_cases_one_record_per_case_with_an_outcome_per_run():
    hijack_ok = trial("english", BEAR)                     # buy x product_info: hijack row
    hijack_no = trial("english", [MUG])
    esc = trial("pictograms", [MUG], prompt="read")        # escalation, bought the scene's mug
    cut = trial("none", prompt="help", stop_reason="max_tokens")
    hijack_ok["response"] = "x" * 1000
    cases = build_cases({"a": [hijack_ok, esc, cut], "b": [hijack_no]}, in_manifest={hijack_ok["id"], esc["id"]})

    assert [c["id"] for c in cases] == sorted({hijack_ok["id"], esc["id"], cut["id"]})
    h = _case(cases, hijack_ok["id"])
    assert {k: h[k] for k in ("prompt_id", "context_id", "representation_id", "category", "attack_type")} == {
        "prompt_id": "buy", "context_id": "product_info", "representation_id": "english",
        "category": "natural", "attack_type": "hijack"}
    assert h["in_manifest"] is True
    assert [t["o"] for t in h["runs"]["a"]] == ["hijack"]
    assert h["runs"]["b"] == [{"e": 1, "o": "followed_user", "d": "Thermal Ceramic Travel Mug", "r": ""}]
    assert len(h["runs"]["a"][0]["r"]) == 280
    assert _case(cases, esc["id"])["runs"]["a"][0]["o"] == "context_driven"
    c = _case(cases, cut["id"])
    assert c["in_manifest"] is False and set(c["runs"]) == {"a"}
    assert c["runs"]["a"][0] == {"e": 1, "o": "cut_off", "d": "no call", "r": ""}


def test_build_cases_lists_epochs_in_order():
    cases = build_cases({"a": [trial("english", epoch=2), trial("english", BEAR, epoch=1)]}, set())
    assert [(t["e"], t["o"]) for t in cases[0]["runs"]["a"]] == [(1, "hijack"), (2, "no_buy")]


def test_run_labels_drop_the_parts_every_run_shares():
    dirs = [Path("runs/2026-11-16_qwen3vl-8b-ollama_074940"), Path("runs/2026-11-17_qwen3vl-8b-ollama")]
    assert run_labels(dirs) == ["2026-11-16_074940", "2026-11-17"]
    assert run_labels(dirs[:1]) == ["2026-11-16_qwen3vl-8b-ollama_074940"]
    same = [Path("a/2026-11-16_x"), Path("b/2026-11-16_x")]
    assert run_labels(same) == [str(p) for p in same]


def test_load_factors_keeps_the_order_of_stimuli_src(tmp_path):
    (tmp_path / "prompts.json").write_text(json.dumps(
        {"z": {"text": "Zed.", "requests_purchase": False}, "a": {"text": "Ay.", "requests_purchase": True}}))
    (tmp_path / "context.json").write_text(json.dumps({"ctx2": {"item": None}, "ctx1": {"item": "mug"}}))
    (tmp_path / "representations.json").write_text(json.dumps({"r2": {}, "r1": {}}))
    assert load_factors(tmp_path) == {
        "prompts": [{"id": "z", "text": "Zed."}, {"id": "a", "text": "Ay."}],
        "contexts": ["ctx2", "ctx1"],
        "reps": ["r2", "r1"],
    }


def test_casemap_html_embeds_cases_and_escapes_script_tags():
    t = trial("english", [MUG])
    t["response"] = "</script><script>alert(1)</script>"
    page = casemap_html(build_cases({"a": [t]}, set()), ["a"], load_factors(), ["hijack"])
    assert page.count("</script>") == 2  # d3's and the page's own
    assert "__DATA__" not in page and "__META__" not in page
    meta = json.loads(page.split("const META = ", 1)[1].split(";\n", 1)[0])
    assert meta["runs"] == ["a"] and meta["lock"] == ["hijack"]
