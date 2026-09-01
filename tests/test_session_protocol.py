"""O gateway manda texto, nunca áudio.

É a decisão D1 virada em teste: depois que a síntese passou para o dispositivo,
qualquer `send_bytes` no gateway é regressão — significa que voltamos a gastar
250 KB por interação e que o aparelho deixou de conseguir falar offline.

O teste também fixa o comportamento de streaming: as frases saem conforme
completam, não de uma vez no fim. Sem isso a latência percebida dobra, e é o
tipo de coisa que se perde numa refatoração sem ninguém notar.
"""

from __future__ import annotations

import json

import pytest

from gateway.api.session import Session
from gateway.llm.base import Delta


class FakeLLM:
    """Devolve a resposta em pedaços, como um provedor real faria."""

    def __init__(self, pedacos: list[str]) -> None:
        self._pedacos = pedacos

    async def respond(self, history, tools):
        for pedaco in self._pedacos:
            yield Delta(text=pedaco)


class FakeSocket:
    """Registra o que foi enviado, separando texto de binário."""

    def __init__(self) -> None:
        self.textos: list[dict] = []
        self.binarios: list[bytes] = []

    async def send_text(self, raw: str) -> None:
        self.textos.append(json.loads(raw))

    async def send_bytes(self, data: bytes) -> None:
        self.binarios.append(data)


def build(pedacos: list[str]) -> tuple[Session, FakeSocket]:
    socket = FakeSocket()
    session = Session(
        websocket=socket,
        llm=FakeLLM(pedacos),
        expected_token="t",
    )
    return session, socket


@pytest.mark.asyncio
async def test_nao_manda_audio_pela_rede():
    from gateway.timing import Turn

    session, socket = build(["Oi. ", "Tudo bem?"])
    await session._speak_response(Turn())

    assert socket.binarios == [], "o gateway voltou a mandar audio pela rede"


@pytest.mark.asyncio
async def test_manda_uma_frase_por_vez():
    from gateway.timing import Turn

    session, socket = build(["Bom dia.", " Ja sao sete horas.", " Quer levantar?"])
    await session._speak_response(Turn())

    parciais = [m["text"] for m in socket.textos if m["type"] == "transcript" and not m["final"]]
    assert parciais == ["Bom dia.", "Ja sao sete horas.", "Quer levantar?"]


@pytest.mark.asyncio
async def test_manda_a_resposta_inteira_no_fim():
    from gateway.timing import Turn

    session, socket = build(["Bom dia.", " Tudo certo."])
    resposta = await session._speak_response(Turn())

    finais = [m["text"] for m in socket.textos if m["type"] == "transcript" and m["final"]]
    assert finais == ["Bom dia. Tudo certo."]
    assert resposta == "Bom dia. Tudo certo."


@pytest.mark.asyncio
async def test_anuncia_que_esta_falando_antes_da_primeira_frase():
    from gateway.timing import Turn

    session, socket = build(["Oi."])
    await session._speak_response(Turn())

    tipos = [(m["type"], m.get("value") or m.get("final")) for m in socket.textos]
    assert tipos[0] == ("state", "speaking"), "o rosto precisa saber antes do audio comecar"


class FakeReceiveSocket(FakeSocket):
    """Entrega pacotes já no formato do Starlette, um por chamada."""

    def __init__(self, pacotes: list[dict]) -> None:
        super().__init__()
        self._pacotes = list(pacotes)

    async def receive(self) -> dict:
        return self._pacotes.pop(0)


@pytest.mark.asyncio
async def test_recebe_frase_transcrita_pelo_dispositivo():
    """Depois de D1 o gateway lê texto: o STT rodou antes do fio."""
    socket = FakeReceiveSocket([{"text": '{"type": "utterance", "text": " que horas sao? "}'}])
    session = Session(websocket=socket, llm=FakeLLM([]), expected_token="t")

    assert await session._receive_utterance() == "que horas sao?"


@pytest.mark.asyncio
async def test_recusa_audio_subindo_pelo_fio():
    """Áudio do dispositivo para o gateway é regressão de D1, não um formato aceito."""
    socket = FakeReceiveSocket(
        [{"bytes": b"\x00\x01"}, {"text": '{"type": "utterance", "text": "oi"}'}]
    )
    session = Session(websocket=socket, llm=FakeLLM([]), expected_token="t")

    assert await session._receive_utterance() == "oi"
    assert [m["type"] for m in socket.textos] == ["error"]
