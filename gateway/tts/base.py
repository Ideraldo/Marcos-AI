"""Text-to-speech interface, with a cache slot for fixed phrases (plan section 5)."""

from __future__ import annotations

from typing import AsyncIterator, Protocol


class TextToSpeech(Protocol):
    def synthesize(self, text: str) -> AsyncIterator[bytes]:
        """Stream PCM 16 kHz mono audio for the given text."""
        ...
