"""faster-whisper: Whisper on CTranslate2, the plan's named local option.

Size is the whole trade-off. tiny and base run anywhere and mangle pt-BR proper
nouns; small is usually the sweet spot on a PC; medium and large are accurate
and far too slow for a 200-500 ms budget. Measure all of them once, then stop
guessing.

Install: pip install faster-whisper
"""

from __future__ import annotations

from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parents[1] / "models" / "faster-whisper"

SIZES = ["tiny", "base", "small", "medium", "large-v3"]


class FasterWhisper:
    kind = "local"
    setup = "pip install faster-whisper"

    def __init__(self, size: str = "small", compute_type: str = "int8") -> None:
        self.size = size
        self.compute_type = compute_type
        self.name = f"faster-whisper:{size}/{compute_type}"
        self._model = None

    def _load(self):
        if self._model is None:
            from faster_whisper import WhisperModel

            # int8 on CPU is what a VPS without a GPU would actually run.
            self._model = WhisperModel(
                self.size,
                device="cpu",
                compute_type=self.compute_type,
                download_root=str(MODEL_DIR),
            )
        return self._model

    def transcribe(self, wav: Path) -> str:
        segments, _ = self._load().transcribe(str(wav), language="pt", beam_size=5)
        return " ".join(segment.text.strip() for segment in segments).strip()
