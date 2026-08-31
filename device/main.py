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

from dotenv import load_dotenv

load_dotenv()

from common.messages import (  # noqa: E402
    CHANNELS,
    SAMPLE_RATE,
    SAMPLE_WIDTH,
    Error,
    State,
    StateMessage,
    ToolCall,
    ToolResult,
    Transcript,
)
from device.state import StateMachine  # noqa: E402
from device.ws_client import GatewayClient  # noqa: E402

log = logging.getLogger("bmo.device")


async def read_line(prompt: str) -> str:
    """Read stdin without blocking the event loop (and thus the socket)."""
    return await asyncio.to_thread(input, prompt)


async def handle_incoming(client: GatewayClient, machine: StateMachine) -> None:
    """Apply everything the gateway sends: state, text, audio, tool calls."""
    audio_bytes = 0
    started = False  # the session-start IDLE must not end the turn

    async for message in client.receive():
        if isinstance(message, bytes):
            audio_bytes += len(message)
            continue

        if isinstance(message, StateMessage):
            if message.value != machine.state:
                machine.transition(message.value)
            if message.value is not State.IDLE:
                started = True
            elif started:
                if audio_bytes:
                    seconds = audio_bytes / (SAMPLE_RATE * SAMPLE_WIDTH * CHANNELS)
                    print(f"  [audio: {audio_bytes} bytes, {seconds:.1f}s]")
                return  # turn finished; back to the prompt

        elif isinstance(message, Transcript):
            who = "voce" if message.role == "user" else "bmo "
            print(f"  {who}> {message.text}")

        elif isinstance(message, ToolCall):
            # Execution is always local, wherever the intent came from
            # (plan section 5, rule 3). device/local/ will own this.
            print(f"  [tool_call {message.name} {message.args} -- nao implementado]")
            await client.send(ToolResult(id=message.id, ok=False, error="not implemented"))

        elif isinstance(message, Error):
            print(f"  [erro do gateway: {message.message}]")
            return


async def run() -> None:
    machine = StateMachine()

    async with GatewayClient() as client:
        print("BMO -- modo texto (fase 0). Ctrl+C para sair.\n")
        while True:
            text = (await read_line("voce: ")).strip()
            if not text:
                continue

            await client.send_audio(text.encode("utf-8"))
            await client.end_audio()
            await handle_incoming(client, machine)


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(name)s %(message)s")
    try:
        asyncio.run(run())
    except (KeyboardInterrupt, EOFError):
        print("\ntchau.")
        sys.exit(0)


if __name__ == "__main__":
    main()
