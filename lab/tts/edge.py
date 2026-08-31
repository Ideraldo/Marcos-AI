"""Microsoft Edge TTS: cloud, free, no key, strong pt-BR neural voices.

The obvious baseline -- if a local engine cannot get close to this, the quality
gap is what you are paying for by going local. Needs the internet, so it can
never be what says "timer de dez minutos" (plan section 5, rule 2).

Install: pip install edge-tts soundfile
Voices:  edge-tts --list-voices | findstr pt-BR
"""

from __future__ import annotations

import asyncio
import io

import numpy as np

from lab.audio import read_wav

#: Common pt-BR neural voices. Francisca is the usual default.
VOICES = [
    "pt-BR-FranciscaNeural",
    "pt-BR-AntonioNeural",
    "pt-BR-ThalitaMultilingualNeural",
]


class EdgeTTS:
    kind = "cloud"
    setup = "pip install edge-tts soundfile"

    def __init__(self, voice: str = VOICES[0], rate: str = "+0%") -> None:
        self.voice = voice
        self.rate = rate
        self.name = f"edge:{voice.removeprefix('pt-BR-').removesuffix('Neural')}"

    def synthesize(self, text: str) -> tuple[np.ndarray, int]:
        return asyncio.run(self._synthesize(text))

    async def _synthesize(self, text: str) -> tuple[np.ndarray, int]:
        import edge_tts
        import soundfile

        communicate = edge_tts.Communicate(text, self.voice, rate=self.rate)
        mp3 = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                mp3.extend(chunk["data"])

        # libsndfile decodes mp3 directly -- no ffmpeg needed on Windows.
        samples, rate = soundfile.read(io.BytesIO(bytes(mp3)), dtype="int16", always_2d=True)
        return samples.mean(axis=1).astype(np.int16), rate
