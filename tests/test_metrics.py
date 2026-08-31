"""The scoring must measure recognition, not formatting habits."""

import pytest

from lab.metrics import cer, normalize, wer
from lab.numbers import spell


@pytest.mark.parametrize(
    "number,expected",
    [
        (0, "zero"), (7, "sete"), (10, "dez"), (15, "quinze"), (17, "dezessete"),
        (23, "vinte e tres"), (30, "trinta"), (100, "cem"), (133, "cento e trinta e tres"),
        (249, "duzentos e quarenta e nove"), (1000, "mil"), (1249, "mil e duzentos e quarenta e nove"),
    ],
)
def test_spell(number, expected):
    assert spell(number) == expected


def test_digits_and_words_score_the_same():
    assert wer("Timer de dez minutos.", "Timer de 10 minutos.") == 0.0
    assert cer("Timer de dez minutos.", "Timer de 10 minutos.") == 0.0


def test_case_accents_and_punctuation_are_ignored():
    assert normalize("Já são QUINZE, para as sete!") == "ja sao quinze para as sete"


def test_real_error_is_still_counted():
    assert wer("acende a luz do quarto", "apaga a luz do quarto") == pytest.approx(0.2)
