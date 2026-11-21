"""
Trials: one test case run once, read back from a harness run's Inspect logs.

A `Trial` pairs the `Case` that was shown (stimuli/cases.py) with the model's `Response`
and the harness scorer's verdict. Its `outcome` (eval/outcomes.py) is computed once, on
first use.

Logs written since cases existed hold the whole case in each sample's metadata. Older
logs hold only flat fields (factor ids, expected_calls, ...): their cases are rebuilt
from those fields and stimuli/src/ (`legacy_case`).
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from functools import cache, cached_property
from pathlib import Path

from stimuli.attack_types import SRC_DIR
from stimuli.cases import Case, Injection, Prompt, Representation, context_from_src


@dataclass(frozen=True)
class Response:
    """What the model did: every tool call in order ({"name", "args"}), its final reply,
    why it stopped, and the error if the sample failed."""
    calls: list[dict] = field(default_factory=list)
    text: str = ""
    stop_reason: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class Trial:
    case: Case
    epoch: int
    response: Response
    obeyed: bool                 # the scorer made the injected call (harness/obey.py)
    n_matched: int = 0           # expected calls matched
    off_target_calls: list[dict] = field(default_factory=list)  # calls that matched no expected call

    @property
    def id(self) -> str:
        return self.case.id

    @cached_property
    def factors(self) -> dict:
        return self.case.factors()

    @cached_property
    def outcome(self) -> str:
        from eval.outcomes import outcome
        return outcome(self)


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


@cache
def _src(src_dir: Path, name: str) -> dict:
    return json.loads((src_dir / name).read_text(encoding="utf-8"))


def legacy_case(meta: dict, src_dir: Path = SRC_DIR) -> Case:
    """The case of a sample logged before cases existed, from its flat metadata: the
    prompt and context from stimuli/src/ by id, the injection from expected_calls (so
    injections since removed from the source still work), the representation from the
    copied category, language and script."""
    prompts, contexts = _src(src_dir, "prompts.json"), _src(src_dir, "context.json")
    for kind, key, known in (("prompt", "prompt_id", prompts), ("context", "context_id", contexts)):
        if meta.get(key) not in known:
            raise ValueError(f"{meta.get('id')}: {kind} {meta.get(key)!r} is not in {src_dir}; the log predates "
                             "full cases, so analyse it from the commit in its run's meta.json")
    expected = (meta.get("expected_calls") or [{}])[0]
    (arg, accepted), = (expected.get("args") or {"": []}).items()
    rep_id, category = meta.get("representation_id"), meta.get("category")
    return Case(
        id=meta["id"],
        image=meta.get("image") or "",
        image_sha256=meta.get("image_sha256"),
        prompt=Prompt(meta["prompt_id"], meta.get("user_prompt") or prompts[meta["prompt_id"]]["text"],
                      prompts[meta["prompt_id"]]["requests_purchase"]),
        context=context_from_src(meta["context_id"], contexts[meta["context_id"]]),
        injection=Injection(meta.get("injection_id"), None, None, expected.get("name", ""), arg,
                            tuple(accepted if isinstance(accepted, list) else [accepted])),
        representation=Representation(rep_id, "none" if category == "baseline" else None, category,
                                      meta.get("language"), meta.get("script")),
    )


def case_from_metadata(meta: dict, src_dir: Path = SRC_DIR) -> Case:
    return Case.from_dict(meta) if isinstance(meta.get("prompt"), dict) else legacy_case(meta, src_dir)


# metadata fields samples_df hands over as JSON text
_JSON_FIELDS = {"prompt", "context", "injection", "representation", "expected_calls"}


def _trial(rec: dict) -> Trial:
    """samples_df record -> Trial."""
    sm: dict = _json(rec.get("score_obeyed_metadata"), {})
    meta = {k: _json(v, None) if k in _JSON_FIELDS else _clean(v)
            for k, v in ((k.removeprefix("metadata_"), v) for k, v in rec.items() if k.startswith("metadata_"))}
    return Trial(
        case=case_from_metadata(meta),
        epoch=int(rec["epoch"]),
        response=Response(
            calls=sm.get("tool_calls") or [],
            text=_clean(rec.get("score_obeyed_answer")) or "",
            stop_reason=_clean(rec.get("stop_reason")),
            error=_clean(rec.get("error")) or None,
        ),
        obeyed=_clean(rec.get("score_obeyed")) == "C",
        n_matched=sm.get("n_matched") or 0,
        off_target_calls=sm.get("off_target_calls") or [],
    )


def merge_logs(trials_per_log: list[list[Trial]]) -> list[Trial]:
    """A resumed run (`harness.run --resume`) has several logs, oldest first. A later
    result replaces an earlier one for the same (id, epoch) unless that would replace a
    clean result with an error."""
    merged: dict = {}
    for trials in trials_per_log:
        for t in trials:
            key = (t.id, t.epoch)
            if key in merged and t.response.error and not merged[key].response.error:
                continue
            merged[key] = t
    return list(merged.values())


def load_trials(run_dir: Path) -> tuple[list[Trial], str | None]:
    """One Trial per (case, epoch) from run_dir/inspect_logs/*.eval, plus the model name."""
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
