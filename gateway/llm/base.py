"""LLM provider interface (plan section 6)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Protocol


@dataclass
class Message:
    role: str  # "system" | "user" | "assistant" | "tool"
    content: str
    #: Presente só na mensagem do assistente que **pediu** uma ferramenta.
    #: Guardar isto no histórico não é enfeite: sem ele o modelo relê a conversa,
    #: vê ações viraram prosa, e para de chamar ferramenta no turno seguinte.
    #: Medido: com o registro completo, 3/3 chamadas; sem ele, 0/3 (D22).
    tool_calls: list[dict[str, Any]] | None = None


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class Delta:
    """One streamed chunk: either text or a tool call."""

    text: str | None = None
    tool_name: str | None = None
    tool_args: dict[str, Any] | None = None


class LLMProvider(Protocol):
    def respond(
        self,
        history: list[Message],
        tools: list[Tool],
    ) -> AsyncIterator[Delta]: ...
