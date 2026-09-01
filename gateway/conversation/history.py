"""Conversation history and prompt assembly.

Deliberately outside ``llm/``: the system prompt and the history do not change
when the provider does. The system prompt is built once and always sits first,
because prefix caching weighs more on the bill than the model choice
(plan section 6).
"""

from __future__ import annotations

from gateway.llm.base import Message

SYSTEM_PROMPT = (
    "Voce e o Marcos, um assistente de voz pessoal que responde em portugues do Brasil. "
    "Suas respostas sao lidas em voz alta, entao seja curto e direto: uma ou duas "
    "frases, sem listas, sem markdown, sem emoji. Se nao souber, diga que nao sabe."
)


class Conversation:
    """A single device's rolling history, trimmed by turn count."""

    def __init__(self, max_turns: int = 12) -> None:
        self._max_turns = max_turns
        self._turns: list[Message] = []

    def add_user(self, text: str) -> None:
        self._turns.append(Message(role="user", content=text))
        self._trim()

    def add_assistant(self, text: str) -> None:
        self._turns.append(Message(role="assistant", content=text))
        self._trim()

    def prompt(self) -> list[Message]:
        return [Message(role="system", content=SYSTEM_PROMPT), *self._turns]

    def _trim(self) -> None:
        excess = len(self._turns) - self._max_turns * 2
        if excess > 0:
            del self._turns[:excess]
