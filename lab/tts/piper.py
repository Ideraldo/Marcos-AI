"""Piper: the plan's first choice (section 9). Local, ONNX, fast on CPU.

Archived in October 2025 but still working. Runs on the Pi, which is the whole
point -- fixed phrases can be pre-generated and cached to disk (section 5).

Install: pip install piper-tts
Voices:  python -m piper.download_voices pt_BR-faber-medium
         (models land in lab/models/piper/)
"""

from __future__ import annotations

import io
import wave
from pathlib import Path

import numpy as np

MODEL_DIR = Path(__file__).resolve().parents[1] / "models" / "piper"

#: The pt-BR voices on Hugging Face, quality low -> medium.
VOICES = [
    "pt_BR-jeff-medium",
    "pt_BR-cadu-medium",
    "pt_BR-miro-high",   # nao esta na lista oficial; veio do OpenVoiceOS
    "pt_BR-dii-high",    # idem
    "pt_BR-faber-medium",
    "pt_BR-edresson-low",
]


class PiperTTS:
    kind = "local"
    setup = "pip install piper-tts && python -m piper.download_voices <voz>"

    def __init__(self, voice: str = VOICES[0]) -> None:
        self.voice = voice
        self.name = f"piper:{voice.removeprefix('pt_BR-')}"
        self._model = None

    def _load(self):
        if self._model is None:
            from piper import PiperVoice

            path = MODEL_DIR / f"{self.voice}.onnx"
            if not path.exists():
                raise FileNotFoundError(
                    f"voz nao baixada: {path}\n"
                    f"  python -m piper.download_voices {self.voice} --data-dir {MODEL_DIR}"
                )
            self._model = PiperVoice.load(str(path))
        return self._model

    def synthesize(self, text: str) -> tuple[np.ndarray, int]:
        voice = self._load()
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as handle:
            voice.synthesize_wav(text, handle)
        buffer.seek(0)
        with wave.open(buffer, "rb") as handle:
            rate = handle.getframerate()
            raw = handle.readframes(handle.getnframes())
        return np.frombuffer(raw, dtype=np.int16), rate
