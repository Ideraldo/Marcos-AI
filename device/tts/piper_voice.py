"""Piper on the device. This is what the assistant sounds like.

Chosen because it is the only engine measured that gives a custom timbre *and*
fits the latency budget: RTF 0.05 on this machine, roughly 0.25 even allowing
for a Pi being five times slower, against a budget of 150-400 ms to first chunk
(plan section 11).

``synthesize`` streams: Piper yields one chunk per sentence, so playback can
start on the first sentence while the rest is still being generated. That is one
of the two biggest latency wins the plan names.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator


class PiperVoiceEngine:
    def __init__(self, model_path: Path) -> None:
        if not model_path.exists():
            raise FileNotFoundError(
                f"voz nao encontrada: {model_path}\n"
                f"  defina TTS_VOICE e TTS_VOICE_DIR no .env"
            )
        if not model_path.with_suffix(".onnx.json").exists():
            raise FileNotFoundError(
                f"config ao lado do modelo nao encontrada: "
                f"{model_path.with_suffix('.onnx.json')}"
            )

        from piper import PiperVoice

        self._voice = PiperVoice.load(str(model_path))
        self.name = model_path.stem
        self.sample_rate = self._voice.config.sample_rate

    def synthesize(self, text: str) -> Iterator[bytes]:
        for chunk in self._voice.synthesize(text):
            yield chunk.audio_int16_bytes
