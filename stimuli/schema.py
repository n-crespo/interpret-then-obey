"""Types of the factor files in stimuli/src/ and of the samples built from them.

A test case is one image and one user message, and every case is generated, never
written by hand: each prompt × context × injection × representation, less the
excluded pairs. Nothing in the setup may hint at the injected item.

The factor files are pydantic models, so each file's shape (keys, types, allowed
values) is declared here once and checked on load. Rules that span files, such as ids
one file names and another defines, are `check_references` in stimuli/factors.py.
"""

from __future__ import annotations

import inspect
import string
from dataclasses import dataclass
from typing import Annotated, ClassVar, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from harness.tools import TOOLS
from stimuli.render import FONT_SIZE_RANGE, FONTS_DIR, REPO_ROOT


def _is_tool(name: str) -> str:
    if name not in TOOLS:
        raise ValueError(f"must be one of harness.tools.TOOLS {list(TOOLS)}")
    return name


def _is_font(name: str) -> str:
    if not (FONTS_DIR / name).is_file():
        raise ValueError(f"font not found: {FONTS_DIR / name}")
    return name


def _tool_args(name: str) -> list[str]:
    """The arguments of a harness tool (harness/tools/mock_tools.py)."""
    return list(inspect.signature(TOOLS[name]()).parameters)


def _placeholders(text: str) -> set[str]:
    """The str.format field names used in `text`."""
    return {name for _, name, _, _ in string.Formatter().parse(text) if name is not None}


# Sample ids join factor ids with '.', so a '.' inside one could make two
# combinations collide (a.b + c vs a + b.c) and would make ids ambiguous to split.
Id = Annotated[str, StringConstraints(min_length=1, pattern=r"^[^.]+$")]
NonEmpty = Annotated[str, StringConstraints(pattern=r"\S")]  # not blank
ToolName = Annotated[str, AfterValidator(_is_tool)]
FontFile = Annotated[str, AfterValidator(_is_font)]
FontSize = Annotated[int, Field(strict=True, ge=FONT_SIZE_RANGE[0], le=FONT_SIZE_RANGE[1])]
# The interpretation gradient, in order: how hard it is to work out what the injection
# says, so obeying can be measured across that range. Whether the order holds is for the
# data to decide. `opaque` is two invented glyphs with no meaning: alone it is a control
# whose obey rate should match the baseline's; with a picture legend (`opaque_legend`)
# it tests whether the model learns a code from the image and acts on it.
Category =Literal["natural", "constructed", "symbols", "opaque", "obfuscated", "keyed"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TargetObject(_Model):
    """Something an injection or a context can name (target_objects.json)."""
    id: Id
    type: Id  # item, destination, ...: also the tool argument it fills
    accepted_items: tuple[NonEmpty, ...] = Field(min_length=1)  # values of that argument that name this object


class Prompt(_Model):
    """The user's message, sent verbatim. Must not name a language, script or the injected item."""
    id: Id
    text: str
    expected_tool: ToolName | None  # the tool the user asks for; None when they ask for no action
    object: Id | None = None  # a target object id; unused for now
    # Contexts not paired with this prompt: those where obeying would not be an attack
    # success, e.g. a purchase request in a scene with nothing to buy.
    exclude_contexts: tuple[Id, ...] = ()


class Context(_Model):
    """The benign content of the image. An injection naming the context's own item is not paired with it."""
    id: Id
    header: str
    lines: tuple[str, ...]
    item: Id | None  # the target object id the scene shows, or None


class InjectionCommand(_Model):
    id: Id
    object_type: Id  # the target object type `{object}` takes
    expected_tool: ToolName  # the tool that obeys the command

    @model_validator(mode="after")
    def _object_type_is_a_tool_argument(self) -> InjectionCommand:
        if self.object_type not in (args := _tool_args(self.expected_tool)):
            raise ValueError(f"object_type {self.object_type!r} must be an argument of the tool {self.expected_tool!r}: {args}")
        return self


class Rendition(_Model):
    content: tuple[str, ...] = Field(min_length=1)  # lines of text, or image paths; may contain {object}
    notes: str | None = None

    @field_validator("content")
    @classmethod
    def _only_object_placeholder(cls, content: tuple[str, ...]) -> tuple[str, ...]:
        for line in content:
            if not _placeholders(line) <= {"object"}:
                raise ValueError(f"{line!r} uses a placeholder other than {{object}}")
        return content

    def filled(self, word: str) -> Rendition:
        # Not revalidated: formatting turns a literal {{ into {, which would read as a placeholder.
        return self.model_copy(update={"content": tuple(line.format(object=word) for line in self.content)})


class _Representation(_Model):
    id: Id
    notes: str | None = None

    @property
    def is_baseline(self) -> bool:
        return self.format == "none"


class _Drawn(_Representation):
    """A representation that draws the injection, from renditions of its commands or whole ones."""
    category: Category
    injection_commands: dict[Id, Rendition] = {}
    injections: dict[Id, Rendition] = {}  # whole renditions


class TextRepresentation(_Drawn):
    """Lines of text. Says the object in its own words (`target_objects`)."""
    format: Literal["text"]
    language: str
    script: str
    font: FontFile | None = None
    font_size: FontSize | None = None
    target_objects: dict[Id, str] = {}  # object id -> word


class ImageRepresentation(_Drawn):
    """Image files. Fills `{object}` with the object id, which names the asset's folder."""
    format: Literal["image"]
    language: str | None = None
    script: str | None = None
    font: ClassVar[None] = None
    font_size: ClassVar[None] = None
    target_objects: ClassVar[dict[str, str]] = {}

    @model_validator(mode="after")
    def _whole_renditions_exist(self) -> ImageRepresentation:
        for injection_id, rendition in self.injections.items():
            for p in rendition.content:
                if not (REPO_ROOT / p).is_file():
                    raise ValueError(f"injection {injection_id!r}: image not found: {REPO_ROOT / p}")
        return self


class BaselineRepresentation(_Representation):
    """No injection: the box is drawn empty, so there is nothing to render. Its rows
    measure how often the model acts unprompted, so an action on an injected row can be
    attributed to the injection. It is a representation so the factorial expansion needs
    no special case."""
    format: Literal["none"]
    category: Literal["baseline"]
    language: ClassVar[None] = None
    script: ClassVar[None] = None
    font: ClassVar[None] = None
    font_size: ClassVar[None] = None
    injection_commands: ClassVar[dict[str, Rendition]] = {}
    target_objects: ClassVar[dict[str, str]] = {}
    injections: ClassVar[dict[str, Rendition]] = {}


Representation = Annotated[TextRepresentation | ImageRepresentation | BaselineRepresentation, Field(discriminator="format")]


class Factors(_Model):
    """The five factor files. Each is keyed by id; target_objects.json is also grouped by type."""
    prompts: dict[Id, Prompt] = Field(min_length=1)
    contexts: dict[Id, Context] = Field(min_length=1)
    target_objects: dict[Id, TargetObject] = Field(min_length=1)
    injection_commands: dict[Id, InjectionCommand] = Field(min_length=1)
    representations: dict[Id, Representation] = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def _ids_from_keys(cls, files: dict) -> dict:
        """Give each entry its key as `id`, and each target object its group as `type`."""
        def add(where: str, spec: dict, key: str, value: str) -> dict:
            if key in spec:
                raise ValueError(f"{where} must not have {key!r}: the file's layout gives it")
            return {**spec, key: value}

        objects: dict = {}
        for kind, group in files["target_objects"].items():
            if not group:
                raise ValueError(f"target_objects.json: type {kind!r} has no objects")
            for oid, spec in group.items():
                if oid in objects:
                    raise ValueError(f"target object id {oid!r} appears under more than one type")
                objects[oid] = add(f"target_objects.json: {oid!r}", spec, "type", kind)
        files = {**files, "target_objects": objects}
        return {name: {k: add(f"{name}.json: {k!r}", v, "id", k) for k, v in entries.items()} for name, entries in files.items()}


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


@dataclass
class Sample:
    """One test case: a prompt and one image. Written as one row of stimuli/manifest.jsonl."""
    id: str
    user_prompt: str
    image: str
    image_sha256: str | None
    expected_calls: list[dict]
    prompt_expected_tool: str | None  # the prompt's expected_tool
    context_object: dict | None  # the context's item as {argument: accepted_items}, like an expected call's args
    prompt_id: str
    context_id: str
    injection_id: str
    representation_id: str
    is_baseline: bool
    category: str
    language: str | None
    script: str | None
