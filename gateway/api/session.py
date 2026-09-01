"""One WebSocket connection = one device session.

The turn loop: collect audio frames until ``audio_end``, transcribe, ask the
LLM, speak the answer back as it is generated. State messages drive the face on
the device, so they are sent as the state actually changes, never in a batch at
the end.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import AsyncIterator

from fastapi import WebSocket, WebSocketDisconnect

from common.messages import Error, SessionStart, State, StateMessage, ToolCall, Transcript
from common.serialization import decode, encode
from gateway.conversation.history import Conversation
from gateway.llm.base import LLMProvider
from gateway.stt.base import SpeechToText
from gateway.timing import Turn

log = logging.getLogger("marcos.session")

#: Sentence enders that are safe places to start speaking (plan section 11:
#: streaming TTS is one of the two biggest latency wins).
BREAKS = ".!?\n"


class Session:
    def __init__(
        self,
        websocket: WebSocket,
        stt: SpeechToText,
        llm: LLMProvider,
        expected_token: str,
    ) -> None:
        self._ws = websocket
        self._stt = stt
        self._llm = llm
        self._expected_token = expected_token
        self._conversation = Conversation()
        self._frames: asyncio.Queue[bytes | None] = asyncio.Queue()

    async def run(self) -> None:
        await self._ws.accept()
        if not await self._authenticate():
            return

        try:
            while True:
                await self._turn()
        except WebSocketDisconnect:
            log.info("device disconnected")

    async def _authenticate(self) -> bool:
        raw = await self._ws.receive_text()
        try:
            message = decode(raw)
        except ValueError as exc:
            await self._send(Error(message=str(exc)))
            await self._ws.close(code=1008)
            return False

        if not isinstance(message, SessionStart) or message.token != self._expected_token:
            await self._send(Error(message="invalid session_start or token"))
            await self._ws.close(code=1008)
            return False

        log.info("session started: %s", message.device_id)
        await self._send(StateMessage(value=State.IDLE))
        return True

    async def _turn(self) -> None:
        """Collect one utterance, answer it, speak the answer."""
        await self._collect_audio()
        if self._frames.empty():
            return

        turn = Turn()
        await self._send(StateMessage(value=State.THINKING))

        text = await self._stt.transcribe(self._drain())
        turn.mark("stt")
        if not text:
            await self._send(StateMessage(value=State.IDLE))
            return
        await self._send(Transcript(text=text, role="user"))

        self._conversation.add_user(text)
        answer = await self._speak_response(turn)
        if answer:
            self._conversation.add_assistant(answer)

        await self._send(StateMessage(value=State.IDLE))
        turn.report()

    async def _collect_audio(self) -> None:
        """Buffer binary frames until the device says the utterance ended."""
        await self._send(StateMessage(value=State.LISTENING))
        while True:
            packet = await self._ws.receive()
            if packet.get("type") == "websocket.disconnect":
                raise WebSocketDisconnect(packet.get("code", 1000))

            if (chunk := packet.get("bytes")) is not None:
                await self._frames.put(chunk)
                continue

            raw = packet.get("text")
            if raw is None:
                continue
            try:
                message = decode(raw)
            except ValueError as exc:
                await self._send(Error(message=str(exc)))
                continue
            if message.type == "audio_end":
                await self._frames.put(None)
                return
            log.debug("ignoring %s while listening", message.type)

    async def _drain(self) -> AsyncIterator[bytes]:
        while (chunk := await self._frames.get()) is not None:
            yield chunk

    async def _speak_response(self, turn: Turn) -> str:
        """Stream the answer to the device, one sentence at a time.

        Sentences go out as they complete, not at the end. The device starts
        speaking the first while the LLM is still writing the third, which is one
        of the two biggest latency wins the plan names (section 11).

        Only text crosses the network. After decision D1 the synthesis happens on
        the device, so a turn costs a few KB instead of the ~250 KB of PCM the
        original design assumed -- and the device can still speak with the
        connection down.
        """
        spoken = False
        first_sentence = True
        pending = ""
        full = ""
        first_token = True

        async def flush(sentence: str) -> None:
            nonlocal spoken, first_sentence
            if not sentence.strip():
                return
            if not spoken:
                await self._send(StateMessage(value=State.SPEAKING))
                spoken = True
            if first_sentence:
                turn.mark("primeira_frase")
                first_sentence = False
            # final=False: mais frases vêm em seguida nesta mesma resposta.
            await self._send(Transcript(text=sentence.strip(), role="assistant", final=False))

        async for delta in self._llm.respond(self._conversation.prompt(), tools=[]):
            if delta.tool_name:
                # Local execution is the device's job, always (plan section 5).
                await self._send(
                    ToolCall(id=str(uuid.uuid4()), name=delta.tool_name, args=delta.tool_args or {})
                )
                continue
            if not delta.text:
                continue

            if first_token:
                turn.mark("llm_first_token")
                first_token = False

            pending += delta.text
            full += delta.text
            if pending[-1] in BREAKS:
                await flush(pending)
                pending = ""

        await flush(pending)

        if full.strip():
            # A resposta inteira, marcada como final: serve para a tela e para o
            # histórico, e diz ao dispositivo que não vem mais nada.
            await self._send(Transcript(text=full.strip(), role="assistant", final=True))
        turn.mark("resposta")
        return full.strip()

    async def _send(self, message: object) -> None:
        await self._ws.send_text(encode(message))
