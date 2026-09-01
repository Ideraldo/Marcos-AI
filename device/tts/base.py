"""Text-to-speech interface, on the device side.

Mirrors ``gateway/tts/base.py`` on purpose, but the device version takes text
rather than producing bytes for the wire: after decision D1 the audio never
crosses the network. The gateway sends what to say; the device says it.
"""

from __future__ import annotations

from typing import Iterator, Protocol


class TextToSpeech(Protocol):
    #: Sample rate of the audio this engine produces.
    sample_rate: int

    def synthesize(self, text: str) -> Iterator[bytes]:
        """Stream int16 mono PCM for the given text, in chunks."""
        ...
