"""Inspect .eval log(s) -> results.jsonl, one row per (sample, epoch), for person 4."""

from __future__ import annotations

import json
from pathlib import Path

from inspect_ai.log import read_eval_log


def _msg_to_dict(msg) -> dict:
    d = msg.model_dump(exclude_none=True)
    content = d.get("content")
    if isinstance(content, list):
        for part in content:
            if part.get("type") == "image":
                part["image"] = "<image omitted>" if str(part.get("image", "")).startswith("data:") else part.get("image")
    return d


def export_results(log_paths, out_path: str | Path) -> int:
    """log_paths: one path or a list (oldest first). A resumed run has several logs;
    a later result replaces an earlier one for the same (id, epoch) unless that would
    replace a clean result with an error."""
    if isinstance(log_paths, (str, Path)):
        log_paths = [log_paths]
    merged: dict = {}
    for lp in log_paths:
        log = read_eval_log(str(lp))
        for s in log.samples or []:
            key = (s.id, s.epoch)
            if key in merged and s.error and not merged[key][1].error:
                continue
            merged[key] = (log, s)
    n = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for log, s in merged.values():
            score = next(iter((s.scores or {}).values()), None)
            sm = (score.metadata or {}) if score else {}
            has_out = bool(s.output and s.output.choices)  # errored samples have no output
            row = {
                "id": s.id,
                "epoch": s.epoch,
                "model": log.eval.model,
                "run_status": log.status,
                "manifest_row": s.metadata,  # everything persons 1/2 put in the row
                "response": s.output.completion if has_out else None,
                "stop_reason": s.output.stop_reason if has_out else None,
                "tool_calls": sm.get("tool_calls", []),
                "obeyed": bool(score and score.value == "C"),
                "n_expected": sm.get("n_expected"),
                "n_matched": sm.get("n_matched"),
                "off_target_calls": sm.get("off_target_calls", []),
                "interpreted": sm.get("interpreted"),  # None = row has no interpretation_keywords
                "interpretation_missing": sm.get("interpretation_missing", []),
                "error": s.error.message if s.error else None,
                "total_time_s": s.total_time,
                "usage": {k: v.model_dump(exclude_none=True) for k, v in (s.model_usage or {}).items()},
                "messages": [_msg_to_dict(m) for m in s.messages],
            }
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
            n += 1
    return n