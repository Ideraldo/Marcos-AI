"""Registry of TTS candidates.

Imports are lazy: a candidate whose package is not installed must not stop the
others from running.
"""

from __future__ import annotations

from typing import Callable

from lab.tts.base import TTSCandidate


def _edge(voice: str | None = None) -> TTSCandidate:
    from lab.tts.edge import VOICES, EdgeTTS

    return EdgeTTS(voice or VOICES[0])


def _piper(voice: str | None = None) -> TTSCandidate:
    from lab.tts.piper import VOICES, PiperTTS

    return PiperTTS(voice or VOICES[0])


ENGINES: dict[str, Callable[..., TTSCandidate]] = {
    "edge": _edge,
    "piper": _piper,
}
