"""The device's only outbound connection: one WebSocket to the gateway.

Rule of thumb from the plan: the device knows exactly one endpoint. Direct
function calls between device and gateway code are forbidden -- migrating to the
VPS must be nothing more than changing GATEWAY_URL.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator

import websockets

from common.messages import AudioEnd, SessionStart
from common.serialization import decode, encode
from device.config import config

log = logging.getLogger("marcos.ws")


class GatewayClient:
    """Thin wrapper over the socket, with the simulated link delay built in.

    The delay is not cosmetic: designing against localhost's zero latency means
    designing for a network that will never exist (plan section 2, rule 3).
    """

    def __init__(self, url: str | None = None, latency_ms: int | None = None) -> None:
        self._url = url or config.gateway_url
        self._latency = (latency_ms if latency_ms is not None else config.simulated_latency_ms) / 1000
        self._ws: Any = None

    async def __aenter__(self) -> "GatewayClient":
        self._ws = await websockets.connect(self._url, max_size=None)
        await self.send(SessionStart(device_id=config.device_id, token=config.token))
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._ws is not None:
            await self._ws.close()
            self._ws = None

    async def send(self, message: object) -> None:
        await self._delay()
        await self._ws.send(encode(message))

    async def send_audio(self, chunk: bytes) -> None:
        await self._delay()
        await self._ws.send(chunk)

    async def end_audio(self) -> None:
        await self.send(AudioEnd())

    async def receive(self) -> AsyncIterator[Any]:
        """Yield decoded control messages and raw audio frames as they arrive."""
        async for packet in self._ws:
            await self._delay()
            if isinstance(packet, bytes):
                yield packet
                continue
            try:
                yield decode(packet)
            except ValueError as exc:
                log.warning("dropping malformed message: %s", exc)

    async def _delay(self) -> None:
        if self._latency:
            await asyncio.sleep(self._latency)
