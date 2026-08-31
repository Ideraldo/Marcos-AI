"""Registry of STT candidates. Factories stay lazy, same reason as in lab/tts."""

from __future__ import annotations

from lab.registry import Entry


def _faster_whisper(size: str | None = None):
    from lab.stt.faster_whisper import FasterWhisper

    return FasterWhisper(size or "small")


def _wav2vec2(size: str | None = None):
    from lab.stt.wav2vec2 import Wav2Vec2

    return Wav2Vec2(size or "large")


def _vosk(size: str | None = None):
    from lab.stt.vosk_engine import Vosk

    return Vosk(size or "small")


ENGINES: dict[str, Entry] = {
    "faster-whisper": Entry(
        _faster_whisper, lang="multi", kind="local", note="tiny|base|small|medium|large-v3"
    ),
    "wav2vec2": Entry(
        _wav2vec2, lang="pt", kind="local", note="XLSR ajustado em pt-BR (large|1b)"
    ),
    "vosk": Entry(_vosk, lang="pt", kind="local", note="modelo pt-BR proprio (small|big)"),
}
