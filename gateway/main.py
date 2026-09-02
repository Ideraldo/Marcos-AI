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
from gateway.tools import SpotifyClient  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

app = FastAPI(title="Marcos gateway")


def build_llm() -> LLMProvider:
    """The only place that knows which provider is active (plan section 6)."""
    if config.llm_provider == "ollama":
        return OllamaProvider(
            base_url=config.ollama_url,
            model=config.llm_model,
            timeout=config.llm_timeout,
            think=config.llm_think,
        )
    raise ValueError(f"unknown LLM_PROVIDER {config.llm_provider!r}")


def build_spotify() -> SpotifyClient | None:
    """O cliente do Spotify, ou None se não houver como usá-lo.

    Duas condições, e as duas importam: credenciais no `.env` **e** o refresh
    token em disco (`python -m gateway.tools.spotify_auth`). Faltando qualquer
    uma, as ferramentas de música não são declaradas ao modelo -- oferecer uma
    ferramenta que vai falhar é pior que não ter ferramenta.
    """
    if not (config.spotify_client_id and config.spotify_client_secret):
        logging.info("spotify: sem credenciais no .env; ferramentas de musica desligadas")
        return None
    client = SpotifyClient(
        client_id=config.spotify_client_id,
        client_secret=config.spotify_client_secret,
        token_path=config.spotify_token_path,
        market=config.spotify_market,
        preferido=config.spotify_device,
    )
    if not client.authorized:
        logging.warning(
            "spotify: falta autorizar -- rode `python -m gateway.tools.spotify_auth`"
        )
        return None
    logging.info("spotify: ferramentas de musica ligadas")
    return client


spotify = build_spotify()


@app.get("/health")
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "llm": f"{config.llm_provider}:{config.llm_model}",
        "spotify": "on" if spotify is not None else "off",
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    session = Session(
        websocket=websocket,
        llm=build_llm(),
        expected_token=config.device_token,
        spotify=spotify,
    )
    await session.run()
