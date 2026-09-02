"""Gateway configuration. Secrets live here and never leave the VPS."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class GatewayConfig:
    host: str = os.getenv("GATEWAY_HOST", "0.0.0.0")
    port: int = int(os.getenv("GATEWAY_PORT", "8000"))
    device_token: str = os.getenv("DEVICE_TOKEN", "dev-token")
    llm_provider: str = os.getenv("LLM_PROVIDER", "ollama")
    llm_model: str = os.getenv("LLM_MODEL", "qwen3:8b")
    # Raciocinar antes de responder custa latencia e pode vazar para a fala.
    # Medido em D20: com isso ligado o turno passa de 2,8s para 10,3s.
    llm_think: bool = os.getenv("LLM_THINK", "false").lower() in ("1", "true", "sim")
    ollama_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    # Um modelo local sem GPU livre responde em minutos, nao em segundos. O
    # limite existe para nao pendurar a sessao para sempre, mas ele precisa ser
    # ajustavel: o valor certo depende de onde o modelo esta rodando.
    llm_timeout: float = float(os.getenv("LLM_TIMEOUT", "120"))
    llm_api_key: str | None = os.getenv("LLM_API_KEY")
    # Spotify: segredos moram aqui e nunca descem para o dispositivo (plano,
    # secao 3). Sem eles, as ferramentas de musica simplesmente nao existem --
    # o modelo nao ve o que nao pode usar.
    spotify_client_id: str | None = os.getenv("SPOTIFY_CLIENT_ID")
    spotify_client_secret: str | None = os.getenv("SPOTIFY_CLIENT_SECRET")
    # 127.0.0.1 e nao localhost: o Spotify recusa `localhost` desde 2025.
    spotify_redirect_uri: str = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")
    spotify_token_path: str = os.getenv("SPOTIFY_TOKEN_PATH", "gateway/data/spotify_token.json")
    spotify_market: str = os.getenv("SPOTIFY_MARKET", "BR")
    stt_api_key: str | None = os.getenv("STT_API_KEY")
    tts_api_key: str | None = os.getenv("TTS_API_KEY")


config = GatewayConfig()
