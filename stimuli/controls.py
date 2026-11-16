"""Which representations are controls (docs/SPEC.md sections 6 and 7).

A control is shown in place of the injection but is not an attack, so analysis keeps it
out of attack success and reports it beside the baseline. A representation is a control
when its category is `control`, or when it declares `"control": true` (which keeps a
control in the category of the representation it is paired with).

Plain Python with no dependencies, so stimuli/generate.py (which writes `control` into
each manifest row) and eval/analyze_results.py (which derives it for runs whose logs
predate the field) apply the same rule.
"""

from __future__ import annotations

import json
from pathlib import Path

CONTROL_CATEGORY = "control"
SRC_DIR = Path(__file__).resolve().parent / "src"


def is_control(rep: dict) -> bool:
    """True for a representations.json entry that is a control."""
    return rep.get("category") == CONTROL_CATEGORY or rep.get("control") is True


def load_controls(src_dir: Path = SRC_DIR) -> dict[str, bool]:
    """representation_id -> is_control, from representations.json in src_dir."""
    with open(src_dir / "representations.json", encoding="utf-8") as f:
        representations = json.load(f)
    return {rep_id: is_control(rep) for rep_id, rep in representations.items()}
