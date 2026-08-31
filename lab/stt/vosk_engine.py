"""Vosk: small, offline, streaming-native. The lightest realistic candidate.

Where Whisper transcribes a finished utterance, Vosk emits partial results while
you are still speaking -- which is what a wake-word device actually wants, and
what makes it worth testing despite the lower accuracy. The pt-BR model is
~50 MB against faster-whisper's 464 MB.

Install: pip install vosk
Model:   https://alphacephei.com/vosk/models -> vosk-model-small-pt-0.3
"""

from __future__ import annotations

import json
import wave
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

MODEL_DIR = Path(__file__).resolve().parents[1] / "models" / "vosk"

MODELS = {
    "small": ("vosk-model-small-pt-0.3", "https://alphacephei.com/vosk/models/vosk-model-small-pt-0.3.zip"),
    "big": ("vosk-model-pt-fb-v0.1.1-20220516_2113", "https://alphacephei.com/vosk/models/vosk-model-pt-fb-v0.1.1-20220516_2113.zip"),
}


class Vosk:
    kind = "local"
    setup = "pip install vosk (o modelo baixa sozinho na primeira execucao)"

    def __init__(self, size: str = "small") -> None:
        if size not in MODELS:
            raise SystemExit(f"tamanho desconhecido: {size} (use {'|'.join(MODELS)})")
        self.size = size
        self.name = f"vosk:{size}"
        self._model = None

    def _ensure_model(self) -> Path:
        folder, url = MODELS[self.size]
        path = MODEL_DIR / folder
        if not path.exists():
            MODEL_DIR.mkdir(parents=True, exist_ok=True)
            archive = MODEL_DIR / f"{folder}.zip"
            print(f"  baixando {folder}...", flush=True)
            urlretrieve(url, archive)
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(MODEL_DIR)
            archive.unlink()
        return path

    def _load(self):
        if self._model is None:
            from vosk import Model, SetLogLevel

            SetLogLevel(-1)
            self._model = Model(str(self._ensure_model()))
        return self._model

    def transcribe(self, wav: Path) -> str:
        from vosk import KaldiRecognizer

        model = self._load()
        with wave.open(str(wav), "rb") as handle:
            recognizer = KaldiRecognizer(model, handle.getframerate())
            words: list[str] = []
            while frames := handle.readframes(4000):
                if recognizer.AcceptWaveform(frames):
                    words.append(json.loads(recognizer.Result()).get("text", ""))
            words.append(json.loads(recognizer.FinalResult()).get("text", ""))
        return " ".join(w for w in words if w).strip()
