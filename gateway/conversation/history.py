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
    "frases, sem listas, sem markdown, sem emoji. Se nao souber, diga que nao sabe. "
    "Timers e alarmes sao executados pelo proprio aparelho, pelas ferramentas: "
    "chame a ferramenta e depois confirme em uma frase curta o que foi feito. "
    "Nunca diga que marcou algo sem ter chamado a ferramenta."
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

    def add_tool_result(self, name: str, result: str) -> None:
        """O que a ferramenta devolveu, para o modelo formular a resposta.

        Entra como papel `tool` e não como `user`: o modelo precisa saber que
        isto é resultado de uma ação que ele pediu, não uma coisa nova que a
        pessoa disse. Confundir os dois faz o modelo responder ao resultado como
        se fosse uma pergunta.
        """
        self._turns.append(Message(role="tool", content=f"{name}: {result}"))
        self._trim()

    def prompt(self) -> list[Message]:
        return [Message(role="system", content=SYSTEM_PROMPT), *self._turns]

    def _trim(self) -> None:
        excess = len(self._turns) - self._max_turns * 2
        if excess > 0:
            del self._turns[:excess]
