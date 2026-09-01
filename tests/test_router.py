"""O roteador de intenções: o que ele reconhece, e o que ele recusa.

A metade que recusa importa tanto quanto a que aceita. A regra 1 do plano diz
que roteador que chuta é pior que roteador nenhum, então "não casou" é resultado
correto, não falha -- e é o que manda a frase para o LLM.
"""

from __future__ import annotations

import pytest

from device.router.intents import match, normalize, to_int


class TestNormalizacao:
    @pytest.mark.parametrize(
        "entrada, esperado",
        [
            ("Põe um TIMER de 10 minutos!", "poe um timer de 10 minutos"),
            ("Que horas são?", "que horas sao"),
            ("  espaço   demais  ", "espaco demais"),
            ("às 6h30", "as 6h30"),
        ],
    )
    def test_tira_acento_pontuacao_e_caixa(self, entrada, esperado):
        assert normalize(entrada) == esperado

    def test_dois_pontos_sobrevive(self):
        # "6:30" precisa continuar inteiro: é o separador de horário.
        assert normalize("alarme 6:30") == "alarme 6:30"


class TestNumeros:
    @pytest.mark.parametrize(
        "token, esperado",
        [("15", 15), ("quinze", 15), ("vinte e cinco", 25), ("meia", 30), ("uma", 1)],
    )
    def test_converte(self, token, esperado):
        assert to_int(token) == esperado

    @pytest.mark.parametrize("token", ["banana", "", "e", "cinco e vinte"])
    def test_recusa_o_que_nao_e_numero(self, token):
        assert to_int(token) is None


class TestTimer:
    @pytest.mark.parametrize(
        "frase, segundos",
        [
            ("põe um timer de 10 minutos", 600),
            ("poe um timer de 10 minutos", 600),  # sem acento, como o STT às vezes entrega
            ("bota um timer de 30 segundos", 30),
            ("timer de quinze minutos", 900),
            ("marca um cronômetro de 2 horas", 7200),
            ("me acorda daqui a 5 minutos", 300),
            ("conta 30 segundos pra mim", 30),
            ("me avisa em vinte e cinco minutos", 1500),
        ],
    )
    def test_reconhece_e_converte_para_segundos(self, frase, segundos):
        intent = match(frase)
        assert intent is not None, frase
        assert intent.name == "criar_timer"
        assert intent.slots["segundos"] == segundos

    def test_guarda_a_frase_original(self):
        # O log do nível 2 precisa da frase como ela foi dita (regra 4).
        assert match("põe um timer de 10 minutos").text == "põe um timer de 10 minutos"


class TestAlarme:
    @pytest.mark.parametrize(
        "frase, hora, minuto",
        [
            ("põe um alarme para as 6 e 30", 6, 30),
            ("alarme pras 6h15", 6, 15),
            ("me acorda às 7", 7, 0),
            ("me acorda às 7 e 30", 7, 30),
            ("põe o despertador para as sete", 7, 0),
            ("alarme 6:45", 6, 45),
        ],
    )
    def test_reconhece_horario(self, frase, hora, minuto):
        intent = match(frase)
        assert intent is not None, frase
        assert intent.name == "criar_alarme"
        assert (intent.slots["hora"], intent.slots["minuto"]) == (hora, minuto)

    @pytest.mark.parametrize("frase", ["me acorda às 30", "alarme para as 7 e 90"])
    def test_recusa_horario_impossivel(self, frase):
        # Slot fora da faixa não vira intenção pela metade: cai para o LLM.
        assert match(frase) is None


class TestOutrasIntencoes:
    def test_que_horas(self):
        assert match("que horas são").name == "que_horas"

    def test_listar(self):
        assert match("quais timers eu tenho").name == "listar"

    def test_cancelar_com_alvo(self):
        assert match("cancela o alarme").slots["alvo"] == "alarme"

    def test_cancelar_sem_alvo(self):
        # "cancela" sozinho é ambíguo de propósito; quem resolve é o serviço.
        assert match("cancela").slots["alvo"] is None


class TestOQueDeveSubirParaOLLM:
    @pytest.mark.parametrize(
        "frase",
        [
            "qual a capital da França",
            "toca uma música",
            "me lembra de tirar o bolo quando der uma meia horinha",
            "põe um timer de banana minutos",
            "que horas são em Tóquio",
            "",
        ],
    )
    def test_nao_casa(self, frase):
        assert match(frase) is None
