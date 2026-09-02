"""Spotify: as únicas ferramentas que o **gateway** executa, e não o dispositivo.

A diferença com `device_tools.py` é a razão de o gateway existir: aqui há
segredo. O `client_secret` e o refresh token ficam no servidor e nunca descem
pelo fio -- é a seção 3 do plano ("Ferramentas · Segredos · Histórico") sendo
levada a sério. O dispositivo só ouve "Tocando tal música".

Exige **Spotify Premium**: todos os endpoints de controle de playback
(`/me/player/play`, `/pause`, `/next`) respondem 403 para conta gratuita. Ler o
que está tocando funciona sem Premium.

Autorização: Authorization Code com refresh token, obtido uma única vez por
`python -m gateway.tools.spotify_auth`. O access token dura uma hora e é
renovado aqui dentro, sem intervenção.
"""

from __future__ import annotations

import base64
import json
import logging
import time
from pathlib import Path
from typing import Any

import httpx

from gateway.llm.base import Tool

log = logging.getLogger("marcos.spotify")

API = "https://api.spotify.com/v1"
TOKEN_URL = "https://accounts.spotify.com/api/token"

#: O que pedimos ao usuário na autorização. Nada além disto: `playback-state`
#: para saber o que toca e em que aparelho, `modify-playback-state` para mandar
#: tocar. Sem acesso a playlists, biblioteca, e-mail ou histórico.
SCOPES = "user-read-playback-state user-modify-playback-state"


class SpotifyError(Exception):
    """Falha que o usuário precisa ouvir, já em português."""


class SpotifyClient:
    """Cliente mínimo: buscar, tocar, pausar, pular, e dizer o que toca."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        token_path: str | Path,
        market: str = "BR",
        timeout: float = 10.0,
    ) -> None:
        self._id = client_id
        self._secret = client_secret
        self._token_path = Path(token_path)
        self._market = market
        self._timeout = timeout
        self._access: str | None = None
        self._expires_at = 0.0

    # -- credenciais -------------------------------------------------------

    @property
    def authorized(self) -> bool:
        """Se existe refresh token em disco. Sem ele não há o que oferecer."""
        return self._token_path.exists()

    def _refresh_token(self) -> str:
        data = json.loads(self._token_path.read_text(encoding="utf-8"))
        token = data.get("refresh_token")
        if not token:
            raise SpotifyError("nao estou conectado ao Spotify")
        return token

    async def _access_token(self) -> str:
        """Devolve um access token válido, renovando se faltar pouco.

        A margem de 60 s existe porque o token pode vencer entre a checagem e a
        chamada -- e o custo de renovar cedo demais é uma requisição, enquanto o
        de renovar tarde é a música não tocar.
        """
        if self._access and time.time() < self._expires_at - 60:
            return self._access

        auth = base64.b64encode(f"{self._id}:{self._secret}".encode()).decode()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.post(
                TOKEN_URL,
                data={"grant_type": "refresh_token", "refresh_token": self._refresh_token()},
                headers={"Authorization": f"Basic {auth}"},
            )
        if r.status_code != 200:
            raise SpotifyError(f"o Spotify recusou a renovacao do acesso ({r.status_code})")

        payload = r.json()
        self._access = payload["access_token"]
        self._expires_at = time.time() + payload.get("expires_in", 3600)
        # O Spotify às vezes devolve um refresh token novo. Ignorar isso faz a
        # conexão morrer semanas depois, longe da causa.
        if payload.get("refresh_token"):
            self._save_refresh(payload["refresh_token"])
        return self._access

    def _save_refresh(self, token: str) -> None:
        self._token_path.parent.mkdir(parents=True, exist_ok=True)
        self._token_path.write_text(
            json.dumps({"refresh_token": token}, indent=2), encoding="utf-8"
        )

    # -- chamadas ----------------------------------------------------------

    async def _call(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        token = await self._access_token()
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.request(
                method, f"{API}{path}", headers={"Authorization": f"Bearer {token}"}, **kwargs
            )
        if r.status_code == 403:
            # O modo de falha mais provável, e o mais confuso se não for
            # traduzido: a API não diz "compre Premium", diz 403.
            raise SpotifyError("o controle de musica precisa de Spotify Premium")
        if r.status_code == 404:
            raise SpotifyError("nao encontrei nenhum aparelho tocando Spotify")
        if r.status_code >= 400:
            raise SpotifyError(f"o Spotify respondeu {r.status_code}")
        return r

    async def _device_id(self) -> str | None:
        """Onde tocar. Prefere o que já está ativo; senão, o primeiro da lista.

        Sem isto, mandar tocar com o Spotify fechado em todo lugar devolve 404 e
        nada acontece -- que é o comportamento mais comum na vida real.
        """
        r = await self._call("GET", "/me/player/devices")
        devices = r.json().get("devices", [])
        if not devices:
            raise SpotifyError("abra o Spotify em algum aparelho primeiro")
        ativo = next((d for d in devices if d.get("is_active")), None)
        return (ativo or devices[0]).get("id")

    async def tocar(self, busca: str) -> str:
        r = await self._call(
            "GET", "/search", params={"q": busca, "type": "track", "limit": 1, "market": self._market}
        )
        itens = r.json().get("tracks", {}).get("items", [])
        if not itens:
            return f"Nao achei nada no Spotify para {busca}."

        faixa = itens[0]
        device = await self._device_id()
        await self._call(
            "PUT",
            "/me/player/play",
            params={"device_id": device} if device else None,
            json={"uris": [faixa["uri"]]},
        )
        artistas = ", ".join(a["name"] for a in faixa.get("artists", []))
        return f"Tocando {faixa['name']}, de {artistas}."

    async def pausar(self) -> str:
        await self._call("PUT", "/me/player/pause")
        return "Pausado."

    async def retomar(self) -> str:
        await self._call("PUT", "/me/player/play")
        return "Voltando a tocar."

    async def proxima(self) -> str:
        await self._call("POST", "/me/player/next")
        return "Proxima."

    async def anterior(self) -> str:
        await self._call("POST", "/me/player/previous")
        return "Voltando uma."

    async def tocando_agora(self) -> str:
        r = await self._call("GET", "/me/player/currently-playing", params={"market": self._market})
        # 204: ninguém está tocando nada. Sem corpo, e `r.json()` explodiria.
        if r.status_code == 204 or not r.content:
            return "Nao tem nada tocando."
        faixa = r.json().get("item")
        if not faixa:
            return "Nao tem nada tocando."
        artistas = ", ".join(a["name"] for a in faixa.get("artists", []))
        return f"{faixa['name']}, de {artistas}."


#: As ferramentas como o modelo as vê. Cada descrição diz **quando não** usar:
#: sem isso, "toca um alarme pra mim" vira uma busca no Spotify.
SPOTIFY_TOOLS: list[Tool] = [
    Tool(
        name="tocar_musica",
        description=(
            "Toca uma musica, artista ou album no Spotify. Use para 'toca Chico "
            "Buarque', 'poe Construcao'. Nao use para timer, alarme ou lembrete."
        ),
        parameters={
            "type": "object",
            "properties": {
                "busca": {
                    "type": "string",
                    "description": "O que procurar: nome da musica, do artista, ou os dois.",
                }
            },
            "required": ["busca"],
        },
    ),
    Tool(
        name="pausar_musica",
        description="Pausa o que esta tocando no Spotify. Use para 'pausa', 'para a musica'.",
        parameters={"type": "object", "properties": {}},
    ),
    Tool(
        name="retomar_musica",
        description="Volta a tocar o que estava pausado no Spotify. Use para 'continua', 'volta a tocar'.",
        parameters={"type": "object", "properties": {}},
    ),
    Tool(
        name="proxima_musica",
        description="Pula para a proxima musica da fila do Spotify.",
        parameters={"type": "object", "properties": {}},
    ),
    Tool(
        name="musica_anterior",
        description="Volta para a musica anterior do Spotify.",
        parameters={"type": "object", "properties": {}},
    ),
    Tool(
        name="musica_tocando",
        description=(
            "Diz qual musica esta tocando agora no Spotify e de quem e. Use para "
            "'que musica e essa', 'quem canta isso'."
        ),
        parameters={"type": "object", "properties": {}},
    ),
]

#: Nome da ferramenta -> método do cliente. Explícito, e não `getattr`, para que
#: um nome inventado pelo modelo não vire chamada de método arbitrário.
SPOTIFY_DISPATCH: dict[str, str] = {
    "tocar_musica": "tocar",
    "pausar_musica": "pausar",
    "retomar_musica": "retomar",
    "proxima_musica": "proxima",
    "musica_anterior": "anterior",
    "musica_tocando": "tocando_agora",
}


async def executar_spotify(client: SpotifyClient, name: str, args: dict) -> str:
    """Executa uma ferramenta do Spotify e devolve a frase a falar.

    Erro nunca sobe como exceção: vira frase. Um assistente de voz que engasga
    porque o Premium venceu é pior que um que diz que o Premium venceu.
    """
    metodo = SPOTIFY_DISPATCH.get(name)
    if metodo is None:
        return f"falhou: ferramenta desconhecida {name}"
    try:
        if metodo == "tocar":
            busca = str(args.get("busca") or "").strip()
            if not busca:
                return "falhou: nao disseram o que tocar"
            return await getattr(client, metodo)(busca)
        return await getattr(client, metodo)()
    except SpotifyError as exc:
        return str(exc).capitalize() + "."
    except httpx.HTTPError as exc:
        log.warning("spotify inacessivel: %s", exc)
        return "Nao consegui falar com o Spotify agora."
