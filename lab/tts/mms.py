"""MMS-TTS: Meta's VITS, one model per language. The pt checkpoint speaks only pt.

The counterweight to Piper on the specialist side. Same idea -- a small
language-specific model -- but a different lineage, so the failure modes differ.
Worth hearing before settling on a voice you will hear ten times a day.

Install: pip install torch transformers
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from lab.numbers import spell_digits

MODEL_DIR = Path(__file__).resolve().parents[1] / "models" / "hf"
MODEL = "facebook/mms-tts-por"


class MMSTTS:
    kind = "local"
    setup = "pip install torch transformers"

    def __init__(self) -> None:
        self.name = "mms:por"
        self._model = None
        self._tokenizer = None

    def _load(self):
        if self._model is None:
            from transformers import AutoTokenizer, VitsModel

            self._tokenizer = AutoTokenizer.from_pretrained(MODEL, cache_dir=str(MODEL_DIR))
            self._model = VitsModel.from_pretrained(MODEL, cache_dir=str(MODEL_DIR))
            self._model.eval()
        return self._model, self._tokenizer

    def synthesize(self, text: str) -> tuple[np.ndarray, int]:
        import torch

        model, tokenizer = self._load()
        # The uroman tokenizer has no number normaliser and drops digits
        # silently -- "04538" comes out as nothing at all. Spell them first.
        inputs = tokenizer(spell_digits(text), return_tensors="pt")
        with torch.no_grad():
            waveform = model(**inputs).waveform[0].numpy()
        samples = np.clip(waveform, -1.0, 1.0) * 32767
        return samples.astype(np.int16), model.config.sampling_rate
