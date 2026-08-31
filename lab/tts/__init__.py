"""Registry of TTS candidates.

Factories are lazy: a candidate whose package is not installed must not stop the
others from running.
"""

from __future__ import annotations

from lab.registry import Entry


def _piper(voice: str | None = None):
    from lab.tts.piper import VOICES, PiperTTS

    return PiperTTS(voice or VOICES[0])


def _mms(_: str | None = None):
    from lab.tts.mms import MMSTTS

    return MMSTTS()


def _edge(voice: str | None = None):
    from lab.tts.edge import VOICES, EdgeTTS

    return EdgeTTS(voice or VOICES[0])


ENGINES: dict[str, Entry] = {
    "piper": Entry(_piper, lang="pt", kind="local", note="um modelo por voz pt-BR, 60 MB"),
    "mms": Entry(_mms, lang="pt", kind="local", note="VITS da Meta treinado so em portugues"),
    "edge": Entry(_edge, lang="multi", kind="cloud", note="so referencia de qualidade"),
}
