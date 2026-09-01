"""Device process entrypoint. Run alongside the gateway: python -m device.main

Phase 0, text mode: you type instead of speaking. The typed line is encoded and
sent through the same binary channel that will carry PCM, so everything past the
microphone is the real path -- including the state machine, the wire protocol
and the simulated link delay. Audio capture replaces only the input here.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import time

from dotenv import load_dotenv

load_dotenv()

from common.messages import (  # noqa: E402
    Error,
    State,
    StateMessage,
    ToolCall,
    ToolResult,
    Transcript,
)
from device.audio.playback import Speaker  # noqa: E402
from device.config import config, voice_path  # noqa: E402
from device.state import StateMachine  # noqa: E402
from device.tts import PiperVoiceEngine  # noqa: E402
from device.ws_client import GatewayClient  # noqa: E402

log = logging.getLogger("marcos.device")


async def read_line(prompt: str) -> str:
    """Read stdin without blocking the event loop (and thus the socket)."""
    return await asyncio.to_thread(input, prompt)


async def speak(voice, speaker, text: str) -> float:
    """Sintetiza e toca, fora do laço de eventos.

    Piper e a placa de som bloqueiam a thread. Rodar isso direto no laço travaria
    o WebSocket enquanto o aparelho fala — e é justamente enquanto ele fala que
    precisa continuar ouvindo, porque o barge-in depende disso (plan section 1).
    """
    started = time.perf_counter()
    await asyncio.to_thread(speaker.play, voice.synthesize(text))
    return time.perf_counter() - started


async def handle_incoming(client: GatewayClient, machine: StateMachine, voice, speaker) -> None:
    """Aplica o que o gateway manda: estado, texto para falar, chamadas de ferramenta."""
    started = False  # o IDLE do início de sessão não encerra o turno
    spoke_at = None

    async for message in client.receive():
        if isinstance(message, bytes):
            # Depois da decisão D1 o gateway não manda mais áudio. Se chegar,
            # é versão antiga do outro lado -- melhor dizer do que ignorar.
            print("  [aviso: recebi audio do gateway; a sintese agora e local]")
            continue

        if isinstance(message, StateMessage):
            if message.value != machine.state:
                machine.transition(message.value)
            if message.value is not State.IDLE:
                started = True
            elif started:
                return  # turno terminou; volta para o prompt

        elif isinstance(message, Transcript):
            if message.role == "user":
                print(f"  voce> {message.text}")
                continue

            # Resposta do assistente. As parciais são as frases conforme saem do
            # LLM -- falar cada uma na hora é o que evita esperar a resposta
            # inteira. A final é a mesma coisa junta, só para a tela.
            if message.final:
                continue
            print(f"  marcos> {message.text}")
            elapsed = await speak(voice, speaker, message.text)
            if spoke_at is None:
                spoke_at = elapsed
                print(f"        [primeira fala em {elapsed:.2f}s]")

        elif isinstance(message, ToolCall):
            # A execução é sempre local, venha a intenção de onde vier
            # (plan section 5, rule 3). device/local/ vai assumir isso.
            print(f"  [tool_call {message.name} {message.args} -- nao implementado]")
            await client.send(ToolResult(id=message.id, ok=False, error="not implemented"))

        elif isinstance(message, Error):
            print(f"  [erro do gateway: {message.message}]")
            return


async def run() -> None:
    machine = StateMachine()

    voice = PiperVoiceEngine(voice_path())
    print(f"voz: {voice.name} ({voice.sample_rate} Hz)")

    with Speaker(voice.sample_rate, config.output_device or None) as speaker:
        async with GatewayClient() as client:
            print("Marcos -- modo texto, voz local (fase 0). Ctrl+C para sair.\n")
            while True:
                text = (await read_line("voce: ")).strip()
                if not text:
                    continue

                await client.send_audio(text.encode("utf-8"))
                await client.end_audio()
                await handle_incoming(client, machine, voice, speaker)


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(name)s %(message)s")
    try:
        asyncio.run(run())
    except (KeyboardInterrupt, EOFError):
        print("\ntchau.")
        sys.exit(0)


if __name__ == "__main__":
    main()
