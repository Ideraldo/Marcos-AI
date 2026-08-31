"""Kokoro: 82M-parameter StyleTTS2, the alternative the plan names for Piper.

Small enough to be a real Pi candidate and generally judged more natural than
Piper. Brazilian Portuguese arrived in v1.0 as language code ``p``, with three
voices -- fewer than Piper, but the ceiling is higher.

Install: pip install kokoro (espeak-ng comes bundled via espeakng-loader)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

MODEL_DIR = Path(__file__).resolve().parents[1] / "models" / "kokoro"

#: pt-BR voices. pf_ is female, pm_ is male.
VOICES = ["pf_dora", "pm_alex", "pm_santa"]

SAMPLE_RATE = 24_000


class KokoroTTS:
    kind = "local"
    setup = "pip install kokoro"

    def __init__(self, voice: str = VOICES[0]) -> None:
        self.voice = voice
        self.name = f"kokoro:{voice}"
        self._pipeline = None

    def _load(self):
        if self._pipeline is None:
            import os

            os.environ.setdefault("HF_HOME", str(MODEL_DIR))
            from kokoro import KPipeline

            # "p" is Brazilian Portuguese; the pipeline phonemises with espeak-ng.
            self._pipeline = KPipeline(lang_code="p")
        return self._pipeline

    def synthesize(self, text: str) -> tuple[np.ndarray, int]:
        pipeline = self._load()
        chunks = [audio for _, _, audio in pipeline(text, voice=self.voice)]
        if not chunks:
            raise RuntimeError("kokoro nao gerou audio")
        waveform = np.concatenate([chunk.numpy() for chunk in chunks])
        return (np.clip(waveform, -1.0, 1.0) * 32767).astype(np.int16), SAMPLE_RATE
