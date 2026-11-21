"""
A test case and its four factors, as objects that pass from stimuli to harness to eval.

stimuli/generate.py builds every `Case` from the factor files in stimuli/src/ and writes
them to stimuli/manifest.jsonl, one `Case.to_dict()` per line. The harness loads them
(harness/manifest.py), runs them, and stores each one whole in its Inspect sample's
metadata, so a run's logs say exactly what was shown. eval/ reads the cases back from
the logs (eval/trials.py) and pairs each with the model's response.

What each factor and field means: docs/SPEC.md.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from harness.obey import arg_matches
from stimuli.attack_types import attack_fields


@dataclass(frozen=True)
class Prompt:
    """The user's instruction (prompts.json)."""
    id: str
    text: str
    requests_purchase: bool


@dataclass(frozen=True)
class Context:
    """The benign content of the image (context.json)."""
    id: str
    header: str
    lines: tuple[str, ...]
    item: str | None
    accepted_items: tuple[str, ...] | None

    def offers(self, item: str) -> bool:
        """Whether a bought item names what the scene shows: one of `accepted_items`,
        matched as the scorer matches the injected item (`arg_matches` in harness/obey.py)."""
        return bool(self.accepted_items) and arg_matches(item, list(self.accepted_items))


@dataclass(frozen=True)
class Injection:
    """The instruction placed in the image (injections.json): one command x one object.
    `command` and `object` are None for injections read back from logs that predate them."""
    id: str
    command: str | None
    object: str | None
    tool: str
    arg: str
    accepted: tuple[str, ...]

    @property
    def expected_calls(self) -> list[dict]:
        """The call that obeys it, in the form harness/obey.py `check_obeyed` takes."""
        return [{"name": self.tool, "args": {self.arg: list(self.accepted)}}]


@dataclass(frozen=True)
class Representation:
    """The form the injection is shown in (representations.json). `format` is None for
    representations read back from logs that predate it."""
    id: str
    format: str | None
    category: str
    language: str | None
    script: str | None


@dataclass(frozen=True)
class Case:
    """One image shown with one user message. Baseline cases (representation `none`) keep
    their injection: it is what they measure the spontaneous rate of."""
    id: str
    image: str
    image_sha256: str | None
    prompt: Prompt
    context: Context
    injection: Injection
    representation: Representation

    @property
    def attack_type(self) -> str:
        """stimuli/attack_types.py, from the prompt, the scene and the injected tool."""
        return self._attack["attack_type"]

    @property
    def competing_product(self) -> bool:
        """The scene shows its own product."""
        return self._attack["competing_product"]

    @property
    def _attack(self) -> dict:
        return attack_fields({"requests_purchase": self.prompt.requests_purchase},
                             {"item": self.context.item}, self.injection.tool)

    @property
    def is_baseline(self) -> bool:
        return self.representation.category == "baseline" or self.representation.id == "none"

    def factors(self) -> dict:
        """Flat fields to filter and group by: the factor ids, the representation's
        category, language and script, and the attack type."""
        r = self.representation
        return {
            "id": self.id,
            "prompt_id": self.prompt.id,
            "context_id": self.context.id,
            "injection_id": self.injection.id,
            "representation_id": r.id,
            "category": r.category,
            "language": r.language,
            "script": r.script,
            "attack_type": self.attack_type,
            "competing_product": self.competing_product,
        }

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Case:
        c, i = d["context"], d["injection"]
        return cls(
            id=d["id"],
            image=d["image"],
            image_sha256=d.get("image_sha256"),
            prompt=Prompt(**d["prompt"]),
            context=Context(**{**c, "lines": tuple(c["lines"]),
                               "accepted_items": tuple(c["accepted_items"]) if c["accepted_items"] else None}),
            injection=Injection(**{**i, "accepted": tuple(i["accepted"])}),
            representation=Representation(**d["representation"]),
        )


def prompt_from_src(prompt_id: str, p: dict) -> Prompt:
    return Prompt(prompt_id, p["text"], p["requests_purchase"])


def context_from_src(context_id: str, c: dict) -> Context:
    accepted = c.get("accepted_items")
    return Context(context_id, c["header"], tuple(c["lines"]), c["item"], tuple(accepted) if accepted else None)


def representation_from_src(rep_id: str, r: dict) -> Representation:
    return Representation(rep_id, r["format"], r["category"], r.get("language"), r.get("script"))
