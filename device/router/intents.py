"""Os padrões do nível 0: formatos rígidos, casados por regex, com slots.

Escopo deliberado. Aqui entra só o que é **determinístico e fechado** —
duração, horário, "cancela", "que horas são". Paráfrase livre ("me lembra de
tirar o bolo quando der uma meia horinha") não é problema de regex, é o que a
similaridade por embeddings vai cobrir depois. Enquanto ela não existe, o que
não casa aqui sobe para o LLM, que é exatamente o comportamento correto: um
roteador que chuta é pior que roteador nenhum (plano, seção 5, regra 1).

Português falado, não escrito. As transcrições do Whisper vêm sem pontuação
confiável e com as variações que as pessoas realmente usam: "põe", "poe",
"bota", "coloca", "marca".
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

#: Números por extenso que aparecem em duração e horário falados. A lista é
#: curta de propósito: cobre o que se fala, não o que existe.
NUMEROS: dict[str, int] = {
    "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4,
    "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9, "dez": 10,
    "onze": 11, "doze": 12, "treze": 13, "quatorze": 14, "catorze": 14,
    "quinze": 15, "dezesseis": 16, "dezessete": 17, "dezoito": 18,
    "dezenove": 19, "vinte": 20, "trinta": 30, "quarenta": 40,
    "cinquenta": 50, "sessenta": 60, "noventa": 90,
    # "meia hora" e "meia dúzia" resolvem-se sozinhos; "meia" isolada é 30
    # só em contexto de minuto, tratado na conversão.
    "meia": 30,
}

SEGUNDOS_POR_UNIDADE = {"segundo": 1, "minuto": 60, "hora": 3600}


@dataclass(frozen=True)
class Intent:
    """O que o roteador entendeu. `slots` já vem convertido, não em texto cru."""

    name: str
    slots: dict[str, Any] = field(default_factory=dict)
    #: A frase original, para o log do nível 2 (plano, seção 5, regra 4).
    text: str = ""


def normalize(text: str) -> str:
    """Minúsculas, sem acento, sem pontuação, espaço único.

    Os padrões são escritos sem acento por causa disto: o Whisper acentua bem,
    mas nem sempre igual, e "tres" e "três" não podem ser intenções diferentes.
    """
    text = unicodedata.normalize("NFD", text.lower())
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^\w\s:]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def to_int(token: str) -> int | None:
    """Converte "15" ou "quinze". Devolve None se não for número."""
    token = token.strip()
    if token.isdigit():
        return int(token)
    if token in NUMEROS:
        return NUMEROS[token]
    # "vinte e cinco", "quarenta e cinco"
    partes = token.split(" e ")
    if len(partes) == 2 and all(p in NUMEROS for p in partes):
        dezena, unidade = NUMEROS[partes[0]], NUMEROS[partes[1]]
        if dezena >= 20 and unidade < 10:
            return dezena + unidade
    return None


# Um número: dígitos, ou palavra, ou "vinte e cinco". As palavras vêm do
# dicionário em vez de `[a-z]+` porque um curinga casaria com qualquer coisa --
# em "alarme para as 6", o "as" viraria candidato a número e derrubaria a frase
# inteira antes de o 6 ser visto.
_PALAVRA_NUM = "|".join(sorted(NUMEROS, key=len, reverse=True))
_NUM = rf"(?:\d{{1,4}}|(?:{_PALAVRA_NUM})(?: e (?:{_PALAVRA_NUM}))?)"
_VERBO_CRIAR = r"(?:poe|poem|bota|coloca|marca|liga|cria|criar|colocar|botar|marcar|por)"
_ARTIGO = r"(?:o |a |um |uma )?"
#: "para as", "pras", "de" -- preposições empilhadas antes do horário. Falando,
#: elas vêm em qualquer combinação, e nenhuma delas muda o sentido.
_PREP = r"(?:(?: (?:para|pra|pras|pro|as|a|ao|de|das|do|meio))*)"


@dataclass(frozen=True)
class Pattern:
    name: str
    regex: re.Pattern[str]


PATTERNS: list[Pattern] = [
    # -- timer: duração relativa ------------------------------------------
    Pattern(
        "criar_timer",
        re.compile(
            rf"^(?:{_VERBO_CRIAR} )?{_ARTIGO}(?:timer|cronometro|temporizador)"
            rf"{_PREP} ({_NUM}) (segundos?|minutos?|horas?)$"
        ),
    ),
    Pattern(
        "criar_timer",
        re.compile(
            rf"^(?:me )?(?:acorda|avisa|chama|lembra|desperta)"
            rf" (?:daqui a|em|daqui) ({_NUM}) (segundos?|minutos?|horas?)$"
        ),
    ),
    Pattern(
        "criar_timer",
        re.compile(rf"^conta ({_NUM}) (segundos?|minutos?|horas?)(?: pra mim| para mim)?$"),
    ),
    # -- alarme: horário absoluto -----------------------------------------
    Pattern(
        "criar_alarme",
        re.compile(
            rf"^(?:{_VERBO_CRIAR} )?{_ARTIGO}(?:alarme|despertador)"
            rf"{_PREP} ({_NUM})(?::| e |h)?({_NUM})?$"
        ),
    ),
    Pattern(
        "criar_alarme",
        re.compile(
            rf"^(?:me )?(?:acorda|acorde|desperta){_PREP} ({_NUM})(?::| e |h)?({_NUM})?$"
        ),
    ),
    # -- consultas ---------------------------------------------------------
    Pattern("que_horas", re.compile(r"^(?:que horas sao|que hora e|me di[sz] as horas|horas)$")),
    Pattern(
        "listar",
        re.compile(
            r"^(?:quais|que|quantos)? ?(?:timers?|alarmes?|cronometros?)"
            r"(?: eu tenho| estao ativos| tem| ativos)?$"
        ),
    ),
    # -- cancelamento ------------------------------------------------------
    Pattern(
        "cancelar",
        re.compile(
            r"^(?:cancela|cancelar|para|parar|desliga|desligar|tira|remove)"
            r"(?: (?:o|a|os|as))?(?: (timer|timers|alarme|alarmes|cronometro))?$"
        ),
    ),
]


def match(text: str) -> Intent | None:
    """Casa a frase contra os padrões. Devolve None se nada casar (→ LLM).

    Slots inválidos (um "timer de banana minutos") derrubam o casamento em vez
    de virarem uma intenção pela metade: os slots todos preenchidos fazem parte
    da confiança, não são detalhe (plano, seção 5, regra 1).
    """
    normalized = normalize(text)
    for pattern in PATTERNS:
        m = pattern.regex.match(normalized)
        if not m:
            continue
        slots = _extract(pattern.name, m)
        if slots is None:
            continue
        return Intent(name=pattern.name, slots=slots, text=text)
    return None


def _extract(name: str, m: re.Match[str]) -> dict[str, Any] | None:
    if name == "criar_timer":
        quantidade = to_int(m.group(1))
        if quantidade is None or quantidade <= 0:
            return None
        unidade = m.group(2).rstrip("s")
        return {
            "segundos": quantidade * SEGUNDOS_POR_UNIDADE[unidade],
            "quantidade": quantidade,
            "unidade": unidade,
        }

    if name == "criar_alarme":
        hora = to_int(m.group(1))
        if hora is None or not 0 <= hora <= 23:
            return None
        minuto = 0
        if m.group(2):
            minuto = to_int(m.group(2)) or 0
            if not 0 <= minuto <= 59:
                return None
        return {"hora": hora, "minuto": minuto}

    if name == "cancelar":
        alvo = (m.group(1) or "").rstrip("s")
        # "cancela" sozinho não diz o quê; o serviço resolve se houver só um
        # pendente, e devolve a pergunta se houver mais.
        return {"alvo": {"cronometro": "timer"}.get(alvo, alvo) or None}

    return {}
