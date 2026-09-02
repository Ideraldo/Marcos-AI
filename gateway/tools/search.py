"""Busca na internet: a ferramenta que existe para o modelo parar de inventar.

Esta é a resposta ao defeito medido em [D20]: o qwen3:8b atribuiu *Dom Casmurro*
ao Mario Quintana, com confiança total. Um modelo de 8 bilhões de parâmetros
sabe conversar; **fundamentar é outra coisa**, e não se resolve com um modelo
maior nem com mais raciocínio (D20 mediu os dois). Resolve-se dando texto de
verdade para ele ler antes de responder.

É a **primeira ferramenta não-terminal** do projeto. As de agenda e as do
Spotify devolvem uma frase pronta que vai ao ar como está (D18); aqui não existe
frase pronta -- existem cinco trechos de páginas, e a resposta falada tem que ser
sintetizada a partir deles. É o caminho de segunda rodada de LLM, que até agora
nenhuma ferramenta usava.

O provedor é trocável pelo mesmo motivo que o LLM é (`LLMProvider`, seção 6 do
plano): o padrão não exige chave nem conta de ninguém, e quem quiser qualidade
melhor troca por variável de ambiente.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Protocol

import httpx

from gateway.llm.base import Tool

log = logging.getLogger("marcos.busca")

#: Quantos resultados pedir. Cinco é o suficiente para o modelo cruzar duas
#: fontes e pouco o bastante para não inchar o prompt -- e prompt inchado, num
#: modelo local, é latência direta.
RESULTADOS = 5

#: Trecho de cada resultado. Textos longos empurram o modelo para copiar em vez
#: de responder, e a resposta vai ser **falada**: uma ou duas frases.
MAX_TRECHO = 400


@dataclass(frozen=True)
class Resultado:
    titulo: str
    trecho: str
    url: str


class SearchProvider(Protocol):
    """Uma fonte de resultados. Trocável, como o `LLMProvider`."""

    nome: str

    async def buscar(self, consulta: str, limite: int) -> list[Resultado]: ...


class DuckDuckGo:
    """Padrão: sem chave, sem conta, sem cadastro.

    A biblioteca é síncrona e faz rede, então roda numa thread -- se rodasse no
    laço de eventos, travaria o WebSocket do dispositivo durante a busca, e é
    exatamente durante a busca que o aparelho deveria continuar respondendo.
    """

    nome = "duckduckgo"

    def __init__(self, regiao: str = "br-pt", timeout: float = 12.0) -> None:
        self._regiao = regiao
        self._timeout = timeout

    async def buscar(self, consulta: str, limite: int) -> list[Resultado]:
        from ddgs import DDGS

        def _sincrono() -> list[dict]:
            with DDGS(timeout=self._timeout) as ddgs:
                return list(ddgs.text(consulta, region=self._regiao, max_results=limite))

        bruto = await asyncio.to_thread(_sincrono)
        return [
            Resultado(
                titulo=(r.get("title") or "").strip(),
                trecho=(r.get("body") or "").strip()[:MAX_TRECHO],
                url=(r.get("href") or "").strip(),
            )
            for r in bruto
            if r.get("body")
        ]


class Brave:
    """Alternativa com chave: resultados mais estáveis, cota gratuita mensal.

    Existe porque o DuckDuckGo sem chave é o primeiro a sofrer quando o
    provedor aperta o cerco a automação -- e aí a busca cai sem aviso. Trocar é
    uma variável de ambiente.
    """

    nome = "brave"
    URL = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, api_key: str, pais: str = "br", timeout: float = 12.0) -> None:
        self._key = api_key
        self._pais = pais
        self._timeout = timeout

    async def buscar(self, consulta: str, limite: int) -> list[Resultado]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.get(
                self.URL,
                params={"q": consulta, "count": limite, "country": self._pais},
                headers={"X-Subscription-Token": self._key, "Accept": "application/json"},
            )
        r.raise_for_status()
        itens = (r.json().get("web") or {}).get("results", []) or []
        return [
            Resultado(
                titulo=(i.get("title") or "").strip(),
                trecho=(i.get("description") or "").strip()[:MAX_TRECHO],
                url=(i.get("url") or "").strip(),
            )
            for i in itens
        ]


SEARCH_TOOLS: list[Tool] = [
    Tool(
        name="buscar_na_internet",
        description=(
            "Procura na internet e devolve trechos de paginas. Use SEMPRE que a "
            "resposta depender de fato que voce nao tem certeza absoluta, de algo "
            "recente, de preco, noticia, resultado, horario de funcionamento, ou "
            "de qualquer numero especifico. Melhor buscar do que arriscar errar. "
            "Nao use para timer, alarme ou musica, que tem ferramentas proprias."
        ),
        parameters={
            "type": "object",
            "properties": {
                "consulta": {
                    "type": "string",
                    "description": (
                        "O que procurar, como se digitaria num buscador: poucas "
                        "palavras, sem 'por favor' e sem frase inteira."
                    ),
                }
            },
            "required": ["consulta"],
        },
    ),
]


def formatar(resultados: list[Resultado]) -> str:
    """Os resultados como o modelo vai lê-los.

    Numerado e com o domínio à vista: o modelo precisa poder dizer "segundo a
    Wikipédia" sem ler uma URL inteira em voz alta, o que seria insuportável.
    """
    if not resultados:
        return "A busca nao devolveu nada."
    linhas = []
    for i, r in enumerate(resultados, 1):
        dominio = r.url.split("/")[2] if "//" in r.url else r.url
        linhas.append(f"[{i}] {r.titulo} ({dominio})\n{r.trecho}")
    return "\n\n".join(linhas)


async def executar_busca(provider: SearchProvider | None, name: str, args: dict) -> str:
    """Executa a busca e devolve o material bruto para o modelo sintetizar.

    Diferente das outras ferramentas, o que volta daqui **não** é a resposta: é
    o que a resposta deve usar. Quem redige a frase falada é o modelo, na rodada
    seguinte.
    """
    if name != "buscar_na_internet":
        return f"falhou: ferramenta desconhecida {name}"
    if provider is None:
        return "falhou: a busca na internet nao esta configurada"

    consulta = str(args.get("consulta") or "").strip()
    if not consulta:
        return "falhou: nao disseram o que procurar"

    try:
        resultados = await provider.buscar(consulta, RESULTADOS)
    except Exception as exc:  # noqa: BLE001 -- a busca não pode derrubar o turno
        # Rede, cota, bloqueio, mudança de HTML do provedor: tudo dá no mesmo
        # para quem está falando com o aparelho, e nada disso pode virar
        # traceback no meio de um turno de voz.
        log.warning("busca falhou (%s): %s", provider.nome, exc)
        return "falhou: nao consegui buscar na internet agora"

    log.info("busca %r (%s): %d resultados", consulta, provider.nome, len(resultados))
    return formatar(resultados)
