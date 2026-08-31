"""Gateway configuration. Secrets live here and never leave the VPS."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class GatewayConfig:
    host: str = os.getenv("GATEWAY_HOST", "0.0.0.0")
    port: int = int(os.getenv("GATEWAY_PORT", "8000"))
    device_token: str = os.getenv("DEVICE_TOKEN", "dev-token")
    llm_model: str = os.getenv("LLM_MODEL", "deepseek-v4-flash")
    llm_api_key: str | None = os.getenv("LLM_API_KEY")
    stt_api_key: str | None = os.getenv("STT_API_KEY")
    tts_api_key: str | None = os.getenv("TTS_API_KEY")


config = GatewayConfig()
