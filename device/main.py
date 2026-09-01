"""Device process entrypoint. Run alongside the gateway: python -m device.main

O turno inteiro do lado do usuário mora aqui: o microfone ouve, o VAD decide
onde a frase acabou, o STT transcreve **no dispositivo** (D1) e só então a frase
sobe para o gateway. A resposta volta como texto, uma frase por vez, e o Piper
fala. Nenhum áudio cruza a rede em nenhuma direção.

    python -m device.main              # microfone
    python -m device.main --text       # digitando, sem carregar o STT

O modo texto continua existindo porque ele isola: se a resposta está errada com
o texto digitado, o problema não é o microfone.

Desde a Fase 2 o turno tem dois caminhos. O roteador de intenções olha a frase
primeiro: se ela é nível 0 -- timer, alarme, hora, cancelar -- o próprio
dispositivo resolve, sem rede e sem LLM. Só o que ele não reconhece sobe para o
gateway. É por isso que o aparelho liga e funciona com o gateway desligado.
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
from device.local import LocalServices, Scheduler, ScheduleStore  # noqa: E402
from device.router import match as match_intent  # noqa: E402
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


async def handle_incoming(client: GatewayClient, machine: StateMachine, voice, speaker, falando) -> None:
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
            async with falando:
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

    # Timers e alarmes vivem em disco e sobem antes de tudo: eles não dependem
    # nem do STT nem do gateway, e são o que tem que funcionar sempre.
    store = ScheduleStore(config.schedules_db)
    services = LocalServices(store)  # o aviso ao agendador é ligado abaixo

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
        # Um alarme não espera o turno acabar, mas também não fala por cima da
        # resposta: o cadeado serializa a placa de som entre o agendador e o
        # laço do usuário.
        falando = asyncio.Lock()

        async def anunciar(item) -> None:
            async with falando:
                texto = services.anunciar(item)
                print(f"\n  marcos> {texto}   [{item.kind}]")
                await speak(voice, speaker, texto)

        scheduler = Scheduler(store, anunciar)
        # Fecha o ciclo: criar ou cancelar acorda o agendador na hora, em vez de
        # esperar ele reavaliar por conta própria.
        services.on_change = scheduler.notify
        scheduler.start()
        if store.pending():
            print(f"agendado: {services.listar({})}")

        try:
            async with GatewayClient() as client:
                if not client.online:
                    print("gateway: fora do ar -- timer, alarme e hora continuam")
                if text_mode:
                    print("Marcos -- modo texto. Ctrl+C para sair.\n")
                    await text_loop(client, machine, voice, speaker, services, falando)
                else:
                    print("Marcos -- fale quando quiser. Ctrl+C para sair.\n")
                    with Microphone(
                        device=config.input_device,
                        silence_ms=config.vad_silence_ms,
                        aggressiveness=config.vad_aggressiveness,
                    ) as microphone:
                        await voice_loop(
                            client, machine, microphone, stt, voice, speaker, services, falando
                        )
        finally:
            await scheduler.stop()
            store.close()


def _ate_falar(machine: StateMachine) -> None:
    """Leva a máquina até SPEAKING pelo caminho que ela permite.

    Sem isto, o atalho óbvio (`IDLE -> THINKING`) levanta `ValueError`: as
    transições legais são as do plano, e IDLE só vai para LISTENING. A máquina
    está certa e o atalho é que estava errado -- foi assim que este caminho
    quebrou na primeira execução com o gateway desligado.
    """
    if machine.state is State.IDLE:
        machine.transition(State.LISTENING)
    if machine.state is State.LISTENING:
        machine.transition(State.THINKING)
    if machine.state is State.THINKING:
        machine.transition(State.SPEAKING)


async def answer(client, machine, voice, speaker, services, falando, text: str) -> None:
    """Conduz o turno: nível 0 aqui, o resto no gateway.

    A ordem importa. Tentar o roteador antes da rede é o que dá ao timer a
    latência que o plano orça (< 200 ms) e o que faz o alarme continuar
    existindo quando o Wi-Fi não existe.

    Se a conexão cair no meio, o cliente já reconectou sozinho -- mas a resposta
    daquele turno se perdeu com a `Session` do gateway. Dizer isso em voz alta e
    voltar a ouvir é melhor que morrer com traceback numa prateleira.
    """
    intent = match_intent(text)
    if intent is not None:
        resposta = services.handle(intent)
        if resposta is not None:
            print(f"  marcos> {resposta}   [nivel 0, local]")
            _ate_falar(machine)
            async with falando:
                await speak(voice, speaker, resposta)
            machine.transition(State.IDLE)
            return

    # Nível 2: o que o roteador não reconheceu. Registrar a frase é o que, em um
    # mês, diz quais intenções merecem virar nível 0 (plano, seção 5, regra 4).
    log.info("nivel 2 (subiu para o LLM): %r", text)
    try:
        await client.send_utterance(text)
        await handle_incoming(client, machine, voice, speaker, falando)
    except ConnectionLost as exc:
        log.warning("turno perdido: %s", exc)
        # Com o gateway fora, o nível 0 continua de pé -- e dizer isso é melhor
        # que um silêncio que parece defeito do microfone.
        _ate_falar(machine)
        async with falando:
            await speak(
                voice, speaker,
                "Nao consigo falar com o servidor agora. Timer e alarme continuam funcionando.",
            )
        machine.transition(State.IDLE)


async def text_loop(client, machine, voice, speaker, services, falando) -> None:
    while True:
        text = (await read_line("voce: ")).strip()
        if not text:
            continue
        # O aparelho esteve ouvindo o tempo todo -- aqui foi o teclado, mas o
        # estado é o mesmo, e é o que mantém a máquina válida nos dois modos.
        machine.transition(State.LISTENING)
        await answer(client, machine, voice, speaker, services, falando, text)


async def voice_loop(client, machine, microphone, stt, voice, speaker, services, falando) -> None:
    while True:
        text = await listen_and_transcribe(microphone, stt, machine)
        if not text:
            continue
        await answer(client, machine, voice, speaker, services, falando, text)


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
