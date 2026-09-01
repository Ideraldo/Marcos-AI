"""Device configuration -- audio devices and display mode come from the env,
so the same code runs on the PC (jack + windowed browser) and on the Pi
(USB speakerphone + Chromium kiosk)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DeviceConfig:
    device_id: str = os.getenv("DEVICE_ID", "marcos-01")
    token: str = os.getenv("DEVICE_TOKEN", "dev-token")
    gateway_url: str = os.getenv("GATEWAY_URL", "ws://localhost:8000/ws")
    input_device: str | None = os.getenv("AUDIO_INPUT_DEVICE")
    output_device: str | None = os.getenv("AUDIO_OUTPUT_DEVICE")
    display_mode: str = os.getenv("DISPLAY_MODE", "window")  # window | kiosk
    # A voz do assistente. Fica fora do pacote de proposito: no PC ela vem da
    # bancada, na Pi virá de um diretório próprio, e nenhum dos dois deveria
    # estar escrito no código.
    tts_voice: str = os.getenv("TTS_VOICE", "pt_BR-ideraldo-medium")
    tts_voice_dir: str = os.getenv("TTS_VOICE_DIR", "lab/models/piper")
    simulated_latency_ms: int = int(os.getenv("SIMULATED_LATENCY_MS", "0"))


config = DeviceConfig()


def voice_path() -> Path:
    """Onde está o .onnx da voz, montado a partir da configuração."""
    return Path(config.tts_voice_dir) / f"{config.tts_voice}.onnx"
