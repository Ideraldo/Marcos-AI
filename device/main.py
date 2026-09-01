"""Device process entrypoint. Run alongside the gateway: python -m device.main

O turno inteiro do lado do usuário mora aqui: o microfone ouve, o VAD decide
onde a frase acabou, o STT transcreve **no dispositivo** (D1) e só então a frase
sobe para o gateway. A resposta volta como texto, uma frase por vez, e o Piper
fala. Nenhum áudio cruza a rede em nenhuma direção.

    python -m device.main              # microfone
    python -m device.main --text       # digitando, sem carregar o STT

O modo texto continua existindo porque ele isola: se a resposta está errada com
o texto digitado, o problema não é o microfone.
"""

from __future__ import annotations

import argparse
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
from device.audio.capture import Microphone  # noqa: E402
from device.audio.playback import Speaker  # noqa: E402
from device.config import config, voice_path  # noqa: E402
from device.state import StateMachine  # noqa: E402
from device.tts import PiperVoiceEngine  # noqa: E402
from device.ws_client import ConnectionLost, GatewayClient  # noqa: E402

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


async def listen_and_transcribe(microphone: Microphone, stt, machine: StateMachine) -> str:
    """Uma fala: grava até o silêncio, transcreve, devolve o texto.

    As duas etapas bloqueiam e vão para threads pela mesma razão da síntese: o
    laço de eventos tem que continuar atendendo o socket.
    """
    machine.transition(State.LISTENING)
    print("  [fale]", end="", flush=True)
    pcm = await asyncio.to_thread(
        microphone.listen, lambda: print("\r  [ouvindo...]", end="", flush=True)
    )
    if not pcm:
        print("\r  [silencio]      ")
        machine.transition(State.IDLE)
        return ""

    started = time.perf_counter()
    text = await asyncio.to_thread(stt.transcribe, pcm)
    print(f"\r  [transcrito em {time.perf_counter() - started:.2f}s]")
    if not text:
        machine.transition(State.IDLE)
    return text


async def handle_incoming(client: GatewayClient, machine: StateMachine, voice, speaker) -> None:
    """Aplica o que o gateway manda: estado, texto para falar, chamadas de ferramenta."""
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
            if message.value is State.IDLE:
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


async def run(text_mode: bool) -> None:
    machine = StateMachine()

    voice = PiperVoiceEngine(voice_path())
    print(f"voz: {voice.name} ({voice.sample_rate} Hz)")

    stt = None
    if not text_mode:
        from device.stt import FasterWhisperSTT

        # Carregar aqui, antes do primeiro turno: são segundos de carga que não
        # podem cair em cima da primeira pergunta.
        print("carregando o STT...", end="", flush=True)
        stt = FasterWhisperSTT(
            size=config.stt_model,
            compute_type=config.stt_compute_type,
            model_dir=config.stt_model_dir,
        )
        print(f"\rstt: {stt.name}      ")

    with Speaker(voice.sample_rate, config.output_device) as speaker:
        async with GatewayClient() as client:
            if text_mode:
                print("Marcos -- modo texto (fase 0). Ctrl+C para sair.\n")
                await text_loop(client, machine, voice, speaker)
            else:
                print("Marcos -- fale quando quiser. Ctrl+C para sair.\n")
                with Microphone(
                    device=config.input_device,
                    silence_ms=config.vad_silence_ms,
                    aggressiveness=config.vad_aggressiveness,
                ) as microphone:
                    await voice_loop(client, machine, microphone, stt, voice, speaker)


async def answer(client, machine, voice, speaker, text: str) -> None:
    """Manda a frase e conduz o turno até o fim.

    Se a conexão cair no meio, o cliente já reconectou sozinho -- mas a resposta
    daquele turno se perdeu com a `Session` do gateway. Dizer isso em voz alta e
    voltar a ouvir é melhor que morrer com traceback numa prateleira.
    """
    await client.send_utterance(text)
    try:
        await handle_incoming(client, machine, voice, speaker)
    except ConnectionLost as exc:
        print(f"  [conexao caiu: {exc}; pode repetir]")
        if machine.state is not State.IDLE:
            machine.transition(State.IDLE)


async def text_loop(client, machine, voice, speaker) -> None:
    while True:
        text = (await read_line("voce: ")).strip()
        if not text:
            continue
        # O aparelho esteve ouvindo o tempo todo -- aqui foi o teclado, mas o
        # estado é o mesmo, e é o que mantém a máquina válida nos dois modos.
        machine.transition(State.LISTENING)
        await answer(client, machine, voice, speaker, text)


async def voice_loop(client, machine, microphone, stt, voice, speaker) -> None:
    while True:
        text = await listen_and_transcribe(microphone, stt, machine)
        if not text:
            continue
        await answer(client, machine, voice, speaker, text)


def main() -> None:
    parser = argparse.ArgumentParser(description="dispositivo do Marcos")
    parser.add_argument(
        "--text",
        action="store_true",
        help="digitar em vez de falar; nao carrega o STT",
    )
    parser.add_argument("--verbose", action="store_true", help="log do STT e da captura")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(name)s %(message)s",
    )
    try:
        asyncio.run(run(args.text))
    except (KeyboardInterrupt, EOFError):
        print("\ntchau.")
        sys.exit(0)


if __name__ == "__main__":
    main()
