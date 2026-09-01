"""pt-BR number spelling, used only to normalise before scoring.

Whisper writes "10 minutos" where the reference says "dez minutos". That is not
a recognition error -- the assistant understands both equally -- but a raw WER
counts it as one and ends up ranking engines by their formatting habits.
Spelling every digit run out puts both spellings in the same form first.
"""

from __future__ import annotations

import re

UNITS = "zero um dois tres quatro cinco seis sete oito nove".split()
TEENS = (
    "dez onze doze treze quatorze quinze dezesseis dezessete dezoito dezenove".split()
)
TENS = "_ _ vinte trinta quarenta cinquenta sessenta setenta oitenta noventa".split()
HUNDREDS = (
    "_ cento duzentos trezentos quatrocentos quinhentos "
    "seiscentos setecentos oitocentos novecentos"
).split()


def spell(number: int) -> str:
    if number < 0:
        return "menos " + spell(-number)
    if number < 10:
        return UNITS[number]
    if number < 20:
        return TEENS[number - 10]
    if number < 100:
        tens, unit = divmod(number, 10)
        return TENS[tens] + (f" e {UNITS[unit]}" if unit else "")
    if number < 1000:
        hundreds, rest = divmod(number, 100)
        if number == 100:
            return "cem"
        return HUNDREDS[hundreds] + (f" e {spell(rest)}" if rest else "")
    if number < 1_000_000:
        thousands, rest = divmod(number, 1000)
        head = "mil" if thousands == 1 else f"{spell(thousands)} mil"
        return head + (f" e {spell(rest)}" if rest else "")
    # Beyond this the assistant is reading an id, not a quantity: digit by digit.
    return " ".join(UNITS[int(d)] for d in str(number))


def spell_digits(text: str) -> str:
    """Replace every run of digits with its spelled form."""

    def replace(match: re.Match[str]) -> str:
        digits = match.group()
        # A long run is an identifier (a postcode, a phone): read it out loud.
        if len(digits) > 6:
            return " ".join(UNITS[int(d)] for d in digits)
        return spell(int(digits))

    return re.sub(r"\d+", replace, text)


def normalize_numeric_formats(text: str) -> str:
    """Põe as convenções numéricas do português na mesma forma antes de soletrar.

    O Whisper escreve "18h45" e "R$ 2.300" onde a referência diz "dezoito e
    quarenta e cinco" e "dois mil e trezentos". Sem tratar isso, a pontuação some
    junto com os pontos e vírgulas e sobra "dezoitohquarenta" ou "dois trezentos"
    — erros que a métrica conta e que ninguém escutando notaria.
    """
    # Separador de milhar: 2.300 -> 2300, 1.249.999 -> 1249999
    text = re.sub(r"\b(\d{1,3}(?:\.\d{3})+)\b", lambda m: m.group().replace(".", ""), text)
    # Vírgula decimal: 1249,90 -> 1249 vírgula 90
    text = re.sub(r"(\d),(\d)", r"\1 vírgula \2", text)
    # Marcador de hora: 18h45 -> 18 e 45, 7h -> 7
    text = re.sub(r"(\d)\s*[hH]\s*(\d)", r"\1 e \2", text)
    return re.sub(r"(\d)\s*[hH]\b", r"\1", text)
