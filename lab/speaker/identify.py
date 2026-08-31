"""Speaker enrolment and identification with ECAPA-TDNN embeddings.

The model (``speechbrain/spkrec-ecapa-voxceleb``, ~80 MB) was trained on
VoxCeleb to tell voices apart, not to understand words -- so it works on
Portuguese despite being trained mostly on English. It runs comfortably on CPU
and would run on the Pi.

Enrolment lives in lab/speaker/voices.json as plain numbers: no audio is kept
after the vector is computed.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

MODEL_DIR = Path(__file__).resolve().parents[1] / "models" / "ecapa"
BOOK = Path(__file__).resolve().parent / "voices.json"

#: Cosine similarity above which two recordings are called the same person.
#: Measured on this project's own data: the same speaker across seven phrases
#: scored 0.69-1.00 against their own average, while three synthetic voices
#: scored 0.02-0.26. 0.45 sits in the middle of that gap with room on both
#: sides. Raise it if strangers get let in, lower it if you get rejected by
#: your own assistant -- `run_speaker who` prints the score so you can see where
#: you land.
THRESHOLD = 0.45


class SpeakerBook:
    def __init__(self, path: Path = BOOK, threshold: float = THRESHOLD) -> None:
        self.path = path
        self.threshold = threshold
        self._model = None
        self.voices: dict[str, np.ndarray] = {}
        if path.exists():
            raw = json.loads(path.read_text())
            self.voices = {name: np.array(vector) for name, vector in raw.items()}

    def _load(self):
        if self._model is None:
            from speechbrain.inference.speaker import EncoderClassifier

            self._model = EncoderClassifier.from_hparams(
                source="speechbrain/spkrec-ecapa-voxceleb",
                savedir=str(MODEL_DIR),
                run_opts={"device": "cpu"},
            )
        return self._model

    def embed(self, wav: Path) -> np.ndarray:
        import torch

        from lab.audio import read_wav

        samples, _ = read_wav(wav)
        signal = torch.tensor(samples.astype("float32") / 32768.0).unsqueeze(0)
        vector = self._load().encode_batch(signal).squeeze().detach().numpy()
        return vector / np.linalg.norm(vector)

    def enroll(self, name: str, wavs: list[Path]) -> np.ndarray:
        """Average several takes: one recording captures one mood, not a voice."""
        vectors = [self.embed(wav) for wav in wavs]
        mean = np.mean(vectors, axis=0)
        mean = mean / np.linalg.norm(mean)
        self.voices[name] = mean
        self.save()
        return mean

    def forget(self, name: str) -> None:
        self.voices.pop(name, None)
        self.save()

    def save(self) -> None:
        self.path.write_text(
            json.dumps({name: vector.tolist() for name, vector in self.voices.items()}, indent=1)
        )

    def scores(self, wav: Path) -> list[tuple[str, float]]:
        vector = self.embed(wav)
        ranked = [(name, float(vector @ known)) for name, known in self.voices.items()]
        return sorted(ranked, key=lambda pair: pair[1], reverse=True)

    def identify(self, wav: Path) -> tuple[str | None, float]:
        """Return the best match, or None when nobody is close enough.

        Answering "desconhecido" matters as much as answering a name: an
        assistant that confidently greets a stranger by your name is worse than
        one that admits it does not know.
        """
        ranked = self.scores(wav)
        if not ranked:
            return None, 0.0
        name, score = ranked[0]
        return (name if score >= self.threshold else None), score
