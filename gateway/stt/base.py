"""Speech-to-text interface. Nothing outside this package knows the implementation."""

from __future__ import annotations

from typing import AsyncIterator, Protocol


class SpeechToText(Protocol):
    async def transcribe(self, audio: AsyncIterator[bytes]) -> str:
        """Consume PCM 16 kHz mono frames and return the final transcript."""
        ...
