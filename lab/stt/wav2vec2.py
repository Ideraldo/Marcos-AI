"""wav2vec2 XLSR fine-tuned on Brazilian Portuguese. A specialist, not a polyglot.

Different family from Whisper: it is a plain acoustic model with a character
head, no language model and no decoder guessing the next word. That cuts both
ways -- it never hallucinates a fluent sentence out of noise the way Whisper
does, and it never punctuates or fixes grammar either. For an intent router
reading raw words, that trade is arguably the right one.

Install: pip install torch transformers
"""

from __future__ import annotations

from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parents[1] / "models" / "hf"

MODELS = {
    "large": "jonatasgrosman/wav2vec2-large-xlsr-53-portuguese",  # ~1.2 GB
    "1b": "jonatasgrosman/wav2vec2-xls-r-1b-portuguese",  # ~3.9 GB
}


class Wav2Vec2:
    kind = "local"
    setup = "pip install torch transformers"

    def __init__(self, size: str = "large") -> None:
        if size not in MODELS:
            raise SystemExit(f"tamanho desconhecido: {size} (use {'|'.join(MODELS)})")
        self.size = size
        self.name = f"wav2vec2:{size}"
        self._pipe = None

    def _load(self):
        if self._pipe is None:
            from transformers import pipeline

            self._pipe = pipeline(
                "automatic-speech-recognition",
                model=MODELS[self.size],
                device="cpu",
                model_kwargs={"cache_dir": str(MODEL_DIR)},
            )
        return self._pipe

    def transcribe(self, wav: Path) -> str:
        from lab.audio import read_wav

        samples, rate = read_wav(wav)
        # The model wants float32 in [-1, 1] at 16 kHz.
        audio = samples.astype("float32") / 32768.0
        result = self._load()({"raw": audio, "sampling_rate": rate})
        return result["text"].strip()
