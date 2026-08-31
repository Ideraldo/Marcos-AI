"""Device configuration -- audio devices and display mode come from the env,
so the same code runs on the PC (jack + windowed browser) and on the Pi
(USB speakerphone + Chromium kiosk)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DeviceConfig:
    device_id: str = os.getenv("DEVICE_ID", "bmo-01")
    token: str = os.getenv("DEVICE_TOKEN", "dev-token")
    gateway_url: str = os.getenv("GATEWAY_URL", "ws://localhost:8000/ws")
    input_device: str | None = os.getenv("AUDIO_INPUT_DEVICE")
    output_device: str | None = os.getenv("AUDIO_OUTPUT_DEVICE")
    display_mode: str = os.getenv("DISPLAY_MODE", "window")  # window | kiosk
    simulated_latency_ms: int = int(os.getenv("SIMULATED_LATENCY_MS", "0"))


config = DeviceConfig()
