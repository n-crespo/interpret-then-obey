"""Types of the factor files in stimuli/src/ and of the samples built from them
(docs/SPEC.md). stimuli/factors.py loads and validates the files into these."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TargetObject:
    """Something an injection or a context can name (target_objects.json)."""
    id: str
    type: str  # item, destination, ...: also the tool argument it fills
    accepted_items: tuple[str, ...]  # values of that argument that name this object


@dataclass(frozen=True)
class Prompt:
    id: str
    text: str
    expected_tool: str | None  # the tool the user asks for; None when they ask for no action
    object: str | None = None  # a target object id; unused for now
    exclude_contexts: tuple[str, ...] = ()


@dataclass(frozen=True)
class Context:
    id: str
    header: str
    lines: tuple[str, ...]
    item: str | None  # the target object id the scene shows, or None


@dataclass(frozen=True)
class InjectionCommand:
    id: str
    object_type: str  # the target object type `{object}` takes
    expected_tool: str  # the tool that obeys the command


@dataclass(frozen=True)
class Injection:
    """One injection command applied to one target object of its type."""
    command: InjectionCommand
    object: TargetObject

    @property
    def id(self) -> str:
        return f"{self.command.id}_{self.object.id}"

    @property
    def expected_calls(self) -> list[dict]:
        """The call that obeys it, in the harness's `expected_calls` format."""
        return [{"name": self.command.expected_tool, "args": {self.object.type: list(self.object.accepted_items)}}]


@dataclass(frozen=True)
class Rendition:
    content: tuple[str, ...]  # lines of text, or image paths; may contain {object}
    notes: str | None = None

    def filled(self, word: str) -> Rendition:
        return Rendition(tuple(line.format(object=word) for line in self.content), self.notes)


@dataclass(frozen=True)
class Representation:
    id: str
    format: str  # text, image or none (the baseline)
    category: str
    language: str | None = None
    script: str | None = None
    font: str | None = None
    font_size: int | None = None
    notes: str | None = None
    injection_commands: dict[str, Rendition] = field(default_factory=dict)
    target_objects: dict[str, str] = field(default_factory=dict)  # object id -> word (text only)
    injections: dict[str, Rendition] = field(default_factory=dict)  # whole renditions

    @property
    def is_baseline(self) -> bool:
        return self.format == "none"


@dataclass(frozen=True)
class Factors:
    prompts: dict[str, Prompt]
    contexts: dict[str, Context]
    target_objects: dict[str, TargetObject]
    injection_commands: dict[str, InjectionCommand]
    representations: dict[str, Representation]
