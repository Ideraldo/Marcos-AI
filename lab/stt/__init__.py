"""Registry of STT candidates. Imports stay lazy, same reason as in lab/tts."""

from __future__ import annotations

from typing import Callable

from lab.stt.base import STTCandidate


def _faster_whisper(size: str | None = None) -> STTCandidate:
    from lab.stt.faster_whisper import FasterWhisper

    return FasterWhisper(size or "small")


ENGINES: dict[str, Callable[..., STTCandidate]] = {
    "faster-whisper": _faster_whisper,
}
