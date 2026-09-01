"""Gateway process entrypoint: uvicorn gateway.main:app"""

from __future__ import annotations

import logging

from dotenv import load_dotenv

load_dotenv()  # before the config dataclasses read the environment

from fastapi import FastAPI, WebSocket  # noqa: E402

from gateway.api.session import Session  # noqa: E402
from gateway.config import config  # noqa: E402
from gateway.llm.base import LLMProvider  # noqa: E402
from gateway.llm.ollama import OllamaProvider  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

app = FastAPI(title="Marcos gateway")


def build_llm() -> LLMProvider:
    """The only place that knows which provider is active (plan section 6)."""
    if config.llm_provider == "ollama":
        return OllamaProvider(
            base_url=config.ollama_url,
            model=config.llm_model,
            timeout=config.llm_timeout,
        )
    raise ValueError(f"unknown LLM_PROVIDER {config.llm_provider!r}")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "llm": f"{config.llm_provider}:{config.llm_model}"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    session = Session(
        websocket=websocket,
        llm=build_llm(),
        expected_token=config.device_token,
    )
    await session.run()
