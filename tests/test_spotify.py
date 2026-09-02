"""Spotify sem Spotify: o cliente contra um HTTP falso.

Não há conta nem rede aqui. O que se testa é o que costuma quebrar de verdade
num cliente de API: o token que vence, o 403 do Premium, o 204 sem corpo, e o
aparelho que ninguém abriu. São exatamente os casos que só aparecem em uso, e
sempre no pior momento.
"""

from __future__ import annotations

import json
import time

import httpx
import pytest

from gateway.tools.spotify import (
    SPOTIFY_DISPATCH,
    SPOTIFY_TOOLS,
    SpotifyClient,
    SpotifyError,
    executar_spotify,
)

FAIXA = {
    "uri": "spotify:track:1",
    "name": "Construcao",
    "artists": [{"name": "Chico Buarque"}],
    "album": {"uri": "spotify:album:9", "name": "Construcao"},
}


class FakeSpotify:
    """Um Spotify de mentira. Registra o que recebeu, para o teste conferir."""

    def __init__(self) -> None:
        self.chamadas: list[tuple[str, str]] = []
        self.devices = [{"id": "dev1", "is_active": True, "name": "Quarto"}]
        self.busca = [FAIXA]
        self.tocando = FAIXA
        self.status = 200
        self.erro_body: dict | None = None
        self.tokens_emitidos = 0
        #: corpo do ultimo PUT /play, para conferir COMO mandamos tocar
        self.corpo_play: dict = {}

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.chamadas.append((request.method, path))

        if "accounts.spotify.com" in request.url.host:
            self.tokens_emitidos += 1
            return httpx.Response(
                200,
                json={"access_token": f"tok{self.tokens_emitidos}", "expires_in": 3600},
            )
        if path.endswith("/me/player/play") and request.content:
            self.corpo_play = json.loads(request.content)
        if self.status != 200:
            return httpx.Response(self.status, json=self.erro_body or {"error": {}})
        if path.endswith("/me/player/devices"):
            return httpx.Response(200, json={"devices": self.devices})
        if path.endswith("/search"):
            return httpx.Response(200, json={"tracks": {"items": self.busca}})
        if path.endswith("/currently-playing"):
            if self.tocando is None:
                return httpx.Response(204)
            return httpx.Response(200, json={"item": self.tocando})
        return httpx.Response(200, json={})


@pytest.fixture
def fake(monkeypatch, tmp_path):
    api = FakeSpotify()
    transport = httpx.MockTransport(api.handler)
    original = httpx.AsyncClient.__init__

    def patched(self, *args, **kwargs):
        kwargs["transport"] = transport
        original(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched)

    token_path = tmp_path / "spotify_token.json"
    token_path.write_text(json.dumps({"refresh_token": "refresh-abc"}), encoding="utf-8")
    return api, SpotifyClient("id", "secret", token_path)


class TestAutorizacao:
    def test_sem_token_em_disco_nao_esta_autorizado(self, tmp_path):
        assert SpotifyClient("id", "secret", tmp_path / "nao-existe.json").authorized is False

    def test_com_token_esta_autorizado(self, fake):
        _, client = fake
        assert client.authorized is True

    @pytest.mark.asyncio
    async def test_reaproveita_o_access_token(self, fake):
        api, client = fake
        await client.pausar()
        await client.pausar()
        # Duas ações, um único token pedido: renovar a cada chamada seria uma
        # ida de rede a mais em todo comando de voz.
        assert api.tokens_emitidos == 1

    @pytest.mark.asyncio
    async def test_renova_quando_o_token_vence(self, fake):
        api, client = fake
        await client.pausar()
        client._expires_at = time.time()  # vencido agora
        await client.pausar()
        assert api.tokens_emitidos == 2


class TestTocar:
    @pytest.mark.asyncio
    async def test_busca_e_toca(self, fake):
        api, client = fake
        assert await client.tocar("construcao") == "Tocando Construcao, de Chico Buarque."
        assert ("GET", "/v1/search") in api.chamadas
        assert ("PUT", "/v1/me/player/play") in api.chamadas

    @pytest.mark.asyncio
    async def test_toca_no_contexto_do_album(self, fake):
        # Com `uris` a fila tem um item so, e o primeiro "proxima" acaba com a
        # musica em silencio -- aconteceu de verdade, com o aparelho ainda
        # dizendo "Proxima". Com o album como contexto, pedir uma musica comeca
        # nela e segue no disco.
        api, client = fake
        await client.tocar("construcao")
        assert api.corpo_play.get("context_uri") == "spotify:album:9"
        assert api.corpo_play.get("offset") == {"uri": "spotify:track:1"}
        assert "uris" not in api.corpo_play

    @pytest.mark.asyncio
    async def test_sem_album_cai_para_faixa_solta(self, fake):
        # Podcast e episodio nao tem album; a busca ainda pode devolver algo sem
        # esse campo, e ai tocar a faixa avulsa e melhor que nao tocar nada.
        api, client = fake
        api.busca = [{"uri": "spotify:track:2", "name": "X", "artists": [{"name": "Y"}]}]
        assert await client.tocar("x") == "Tocando X, de Y."
        assert api.corpo_play.get("uris") == ["spotify:track:2"]

    @pytest.mark.asyncio
    async def test_busca_sem_resultado_nao_toca_nada(self, fake):
        api, client = fake
        api.busca = []
        resposta = await client.tocar("musica que nao existe")
        assert "Nao achei" in resposta
        assert ("PUT", "/v1/me/player/play") not in api.chamadas

    @pytest.mark.asyncio
    async def test_sem_aparelho_aberto(self, fake):
        api, client = fake
        api.devices = []
        with pytest.raises(SpotifyError, match="abra o Spotify"):
            await client.tocar("construcao")

    @pytest.mark.asyncio
    async def test_prefere_o_aparelho_ativo(self, fake):
        api, client = fake
        api.devices = [
            {"id": "parado", "is_active": False},
            {"id": "tocando", "is_active": True},
        ]
        assert await client._device_id() == "tocando"

    @pytest.mark.asyncio
    async def test_sem_nenhum_ativo_usa_o_primeiro(self, fake):
        api, client = fake
        api.devices = [{"id": "a", "is_active": False}, {"id": "b", "is_active": False}]
        assert await client._device_id() == "a"


class TestTocandoAgora:
    @pytest.mark.asyncio
    async def test_diz_o_que_toca(self, fake):
        _, client = fake
        assert await client.tocando_agora() == "Construcao, de Chico Buarque."

    @pytest.mark.asyncio
    async def test_204_sem_corpo_nao_explode(self, fake):
        # O 204 é o caso que derruba cliente ingênuo: `r.json()` sem corpo.
        api, client = fake
        api.tocando = None
        assert await client.tocando_agora() == "Nao tem nada tocando."


class TestOs403QueSignificamCoisasDiferentes:
    """O Spotify usa 403 para falta de Premium **e** para comando invalido.

    Isto nasceu errado: todo 403 virava "precisa de Premium". A primeira
    execucao com conta real pausou o que ja estava pausado, levou 403
    "Restriction violated", e o aparelho disse a quem tem Premium que precisava
    comprar Premium.
    """

    @pytest.mark.asyncio
    async def test_premium_pelo_reason(self, fake):
        api, client = fake
        api.status = 403
        api.erro_body = {"error": {"status": 403, "reason": "PREMIUM_REQUIRED", "message": "x"}}
        with pytest.raises(SpotifyError, match="Premium"):
            await client.pausar()

    @pytest.mark.asyncio
    async def test_premium_pela_mensagem(self, fake):
        api, client = fake
        api.status = 403
        api.erro_body = {"error": {"status": 403, "message": "Premium required"}}
        with pytest.raises(SpotifyError, match="Premium"):
            await client.pausar()

    @pytest.mark.asyncio
    async def test_restricao_nao_fala_em_premium(self, fake):
        # O caso real: pausar o que ja esta pausado.
        api, client = fake
        api.status = 403
        api.erro_body = {
            "error": {
                "status": 403,
                "message": "Player command failed: Restriction violated",
                "reason": "UNKNOWN",
            }
        }
        with pytest.raises(SpotifyError) as exc:
            await client.pausar()
        assert "premium" not in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_sem_aparelho_ativo_pelo_reason(self, fake):
        api, client = fake
        api.status = 403
        api.erro_body = {"error": {"status": 403, "reason": "NO_ACTIVE_DEVICE"}}
        with pytest.raises(SpotifyError, match="abra o Spotify"):
            await client.pausar()

    @pytest.mark.asyncio
    async def test_403_sem_corpo_util_nao_inventa_motivo(self, fake):
        api, client = fake
        api.status = 403
        api.erro_body = {"error": {}}
        with pytest.raises(SpotifyError, match="recusou o comando"):
            await client.pausar()


class TestErrosQueOUsuarioOuve:
    @pytest.mark.asyncio
    async def test_429_pede_para_esperar(self, fake):
        api, client = fake
        api.status = 429
        with pytest.raises(SpotifyError, match="esperar"):
            await client.pausar()

    @pytest.mark.asyncio
    async def test_erro_nunca_sobe_como_excecao_pelo_despacho(self, fake):
        api, client = fake
        api.status = 403
        api.erro_body = {"error": {"reason": "PREMIUM_REQUIRED"}}
        resposta = await executar_spotify(client, "pausar_musica", {})
        # Vira frase, e em português: o turno de voz não pode morrer aqui.
        assert "premium" in resposta.lower()
        assert resposta.endswith(".")

    @pytest.mark.asyncio
    async def test_ferramenta_inventada(self, fake):
        _, client = fake
        assert "desconhecida" in await executar_spotify(client, "tocar_video", {})

    @pytest.mark.asyncio
    async def test_tocar_sem_dizer_o_que(self, fake):
        _, client = fake
        assert "falhou" in await executar_spotify(client, "tocar_musica", {"busca": "  "})


class TestDeclaracao:
    def test_toda_ferramenta_declarada_tem_despacho(self):
        assert {t.name for t in SPOTIFY_TOOLS} == set(SPOTIFY_DISPATCH)

    def test_descricoes_dizem_quando_nao_usar(self):
        # "toca um alarme pra mim" não pode virar busca no Spotify.
        tocar = next(t for t in SPOTIFY_TOOLS if t.name == "tocar_musica")
        assert "alarme" in tocar.description.lower()

    def test_despacho_nao_expoe_metodo_arbitrario(self):
        # Se o despacho fosse getattr(client, nome), um nome inventado pelo
        # modelo viraria chamada de método qualquer do cliente.
        assert "_access_token" not in SPOTIFY_DISPATCH.values()
        assert "_save_refresh" not in SPOTIFY_DISPATCH.values()


class TestSessaoSemSpotify:
    def test_ferramentas_de_musica_nao_sao_declaradas(self):
        from gateway.api.session import Session

        sessao = Session(websocket=None, llm=None, expected_token="x", spotify=None)
        nomes = {t.name for t in sessao._tools}
        assert "tocar_musica" not in nomes
        assert "criar_timer" in nomes  # as do dispositivo continuam

    def test_com_spotify_as_duas_familias_aparecem(self, fake):
        from gateway.api.session import Session

        _, client = fake
        sessao = Session(websocket=None, llm=None, expected_token="x", spotify=client)
        nomes = {t.name for t in sessao._tools}
        assert {"tocar_musica", "criar_timer"} <= nomes
