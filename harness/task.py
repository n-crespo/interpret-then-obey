"""Inspect AI task: manifest rows -> samples, mock tools, the deterministic outcome scorer (eval/scorer.py)."""

from __future__ import annotations

from inspect_ai import Epochs, Task, task
from inspect_ai.dataset import Sample
from inspect_ai.model import (
    ChatMessageAssistant,
    ChatMessageSystem,
    ChatMessageUser,
    ContentImage,
    ContentText,
)
from inspect_ai.solver import generate, use_tools

from eval.scorer import outcome

from .manifest import filter_rows, load_manifest
from .tools import TOOLS


def _user_content(text: str | None, image: str | None):
    parts = []
    if image:
        parts.append(ContentImage(image=image))
    if text:
        parts.append(ContentText(text=text))
    return parts


def row_to_sample(row: dict, default_system_prompt: str | None) -> Sample:
    msgs = []
    system = row.get("system_prompt", default_system_prompt)
    if system:
        msgs.append(ChatMessageSystem(content=system))
    for m in row.get("context") or []:
        if m["role"] == "assistant":
            msgs.append(ChatMessageAssistant(content=m.get("text", "")))
        elif m["role"] == "system":
            msgs.append(ChatMessageSystem(content=m.get("text", "")))
        else:
            msgs.append(ChatMessageUser(content=_user_content(m.get("text"), m.get("image"))))
    msgs.append(ChatMessageUser(content=_user_content(row["user_prompt"], row.get("image"))))
    return Sample(id=row["id"], input=msgs, target="", metadata=row)


def build_task(
    manifest: str,
    system_prompt: str | None,
    ids: list[str] | None = None,
    where: dict[str, str] | None = None,
    image_root: str | None = None,
    verify_hashes: bool = True,
    name: str = "interpret_then_obey",
    limit: int | None = None,
    exclude_ids: set[str] | None = None,
) -> Task:
    rows = filter_rows(load_manifest(manifest, image_root, verify_hashes), ids, where)
    if limit:
        rows = rows[:limit]
    if exclude_ids:  # used by --resume: skip rows that already finished cleanly
        rows = [r for r in rows if r["id"] not in exclude_ids]
    if not rows:
        raise ValueError("no manifest rows left after filtering")
    return Task(
        name=name,
        dataset=[row_to_sample(r, system_prompt) for r in rows],
        solver=[use_tools([make() for make in TOOLS.values()]), generate(tool_calls="loop")],
        scorer=outcome(),
        epochs=Epochs(1, "mode"),  # outcomes are strings; a run config's epochs keep this reducer
    )


@task
def interpret_then_obey(system_prompt: str, manifest: str = "stimuli/manifest.jsonl"):
    """`inspect eval harness/task.py -T system_prompt=... -T manifest=...` also works, but harness.run is preferred."""
    return build_task(manifest, system_prompt)