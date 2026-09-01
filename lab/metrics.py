"""Objective scoring for STT: word and character error rate.

Numbers do not replace listening, but they stop a comparison from turning into
"this one felt better". Normalisation is deliberately aggressive -- casing,
punctuation and accents are not what decides whether the assistant understood
"põe um timer de dez minutos".
"""

from __future__ import annotations

import re
import unicodedata

from lab.numbers import normalize_numeric_formats, spell_digits


def normalize(text: str) -> str:
    # Antes de tirar a pontuação: ponto e vírgula ainda significam algo dentro
    # de um número, e perdê-los inventa erro que ninguém ouviria.
    text = normalize_numeric_formats(text.lower())
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^\w\s]", " ", text)
    # "10 minutos" and "dez minutos" are the same answer to this assistant.
    text = spell_digits(text)
    return re.sub(r"\s+", " ", text).strip()


def _edit_distance(reference: list, hypothesis: list) -> int:
    previous = list(range(len(hypothesis) + 1))
    for i, r in enumerate(reference, start=1):
        current = [i]
        for j, h in enumerate(hypothesis, start=1):
            current.append(
                previous[j - 1] if r == h else 1 + min(previous[j - 1], previous[j], current[j - 1])
            )
        previous = current
    return previous[-1]


def wer(reference: str, hypothesis: str) -> float:
    ref = normalize(reference).split()
    if not ref:
        return 0.0
    return _edit_distance(ref, normalize(hypothesis).split()) / len(ref)


def cer(reference: str, hypothesis: str) -> float:
    ref = list(normalize(reference).replace(" ", ""))
    if not ref:
        return 0.0
    return _edit_distance(ref, list(normalize(hypothesis).replace(" ", ""))) / len(ref)
