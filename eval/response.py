"""What the model did on one sample (docs/architecture.md section 4), as a thin view over
the Inspect TaskState a scorer gets. No log parsing."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ToolCall:
    name: str
    args: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Response:
    text: str
    tool_calls: tuple[ToolCall, ...] = ()  # every call the model made, in order
    stop_reason: str | None = None
    error: str | None = None

    @classmethod
    def from_state(cls, state) -> Response:
        out = state.output
        done = out if out is not None and out.choices else None  # None: the model never answered
        return cls(
            text=done.completion if done else "",
            tool_calls=tuple(
                ToolCall(tc.function, dict(tc.arguments or {}))
                for m in state.messages if m.role == "assistant"
                for tc in (m.tool_calls or [])
            ),
            stop_reason=done.stop_reason if done else None,
            error=out.error if out is not None else None,
        )
