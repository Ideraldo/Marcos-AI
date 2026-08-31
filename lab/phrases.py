"""The fixed pt-BR test set. Every engine speaks and transcribes exactly these.

Comparing engines only means something if the input is identical, so this list
is the constant. Each phrase probes something specific -- numbers, hours,
foreign words, prosody -- because those are where pt-BR engines usually break.
"""

from __future__ import annotations

PHRASES: dict[str, str] = {
    "curta": "Timer de dez minutos.",
    "hora": "Já são quinze para as sete, hora de acordar.",
    "numeros": "O CEP é 04538-133 e o valor deu R$ 1.249,90.",
    "estrangeirismo": "Toca a playlist Discover Weekly no Spotify da sala.",
    "pergunta": "Você pode acender a luz do quarto e baixar o volume, por favor?",
    "longa": (
        "Segundo a previsão, amanhã vai chover à tarde em São Paulo, "
        "com máxima de vinte e três graus e mínima de dezessete. "
        "Quer que eu programe o despertador mais cedo?"
    ),
    "acentos": "O avô do José põe açúcar no pão às três da manhã.",
}

#: Sanity check for STT: short, unambiguous, no proper nouns.
WARMUP = "curta"
