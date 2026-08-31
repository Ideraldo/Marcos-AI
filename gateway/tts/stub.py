"""Phase-0 stub: emits silence instead of speech.

Keeps the shape of the real thing -- streamed PCM 16 kHz mono chunks, roughly
proportional to how long the sentence takes to say -- so the device's playback
path and the latency instrumentation are exercised before a real voice exists.
"""

from __future__ import annotations

import asyncio
from typing import AsyncIterator

from common.messages import CHANNELS, SAMPLE_RATE, SAMPLE_WIDTH

#: Rough pt-BR speaking rate, used to size the silence.
CHARS_PER_SECOND = 15.0
CHUNK_MS = 100


class SilenceTTS:
    async def synthesize(self, text: str) -> AsyncIterator[bytes]:
        seconds = max(len(text) / CHARS_PER_SECOND, 0.2)
        chunk = b"\x00" * int(SAMPLE_RATE * SAMPLE_WIDTH * CHANNELS * CHUNK_MS / 1000)
        for _ in range(int(seconds * 1000 / CHUNK_MS)):
            # Pace it like a real synthesiser so latency numbers stay honest.
            await asyncio.sleep(CHUNK_MS / 1000)
            yield chunk
