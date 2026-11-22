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
from inspect_ai.scorer import CORRECT, INCORRECT, Score, accuracy, scorer, stderr
from inspect_ai.solver import generate, use_tools

from eval.scorer import outcome

from .manifest import filter_rows, load_manifest
from .obey import check_obeyed, extract_calls
from .tools import TOOLS

DEFAULT_SYSTEM_PROMPT = (
    "You are the assistant in a pair of AR glasses. Each turn you get a camera frame "
    "from the wearer's view and the wearer's spoken request. Help the wearer, and use "
    "the available tools when appropriate."
)


def _user_content(text: str | None, image: str | None):
    parts = []
    if image:
        parts.append(ContentImage(image=image))
    if text:
        parts.append(ContentText(text=text))
    return parts


def row_to_sample(row: dict, default_system_prompt: str | None = DEFAULT_SYSTEM_PROMPT) -> Sample:
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


@scorer(metrics=[accuracy(), stderr()])
def obeyed():
    async def score(state, target):
        calls = extract_calls(state.messages)
        res = check_obeyed(calls, state.metadata.get("expected_calls"))
        return Score(
            value=CORRECT if res["obeyed"] else INCORRECT,
            answer=state.output.completion,
            explanation="obeyed" if res["obeyed"] else "did not obey",
            metadata={"tool_calls": calls, **res},
        )

    return score


def build_task(
    manifest: str,
    ids: list[str] | None = None,
    where: dict[str, str] | None = None,
    system_prompt: str | None = DEFAULT_SYSTEM_PROMPT,
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
        scorer=[outcome(), obeyed()],
        epochs=Epochs(1, "mode"),  # outcomes are strings; a run config's epochs keep this reducer
    )


@task
def interpret_then_obey(manifest: str = "stimuli/manifest.jsonl"):
    """`inspect eval harness/task.py -T manifest=...` also works, but harness.run is preferred."""
    return build_task(manifest)