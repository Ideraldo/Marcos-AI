"""Nível 0: timers e alarmes que precisam funcionar com a rede fora.

O critério de aceite da Fase 2 é literalmente "timer funciona com o gateway
desligado". Nada aqui importa `device.ws_client` -- e isso é proposital: se um
dia alguém acoplar os dois, estes testes continuam passando e o de baixo,
`test_sobrevive_sem_gateway`, é o que quebra.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta

import pytest

from device.local.scheduler import GRACE, Scheduler
from device.local.service import LocalServices
from device.local.store import ScheduleStore
from device.router.intents import match


@pytest.fixture
def store(tmp_path):
    s = ScheduleStore(tmp_path / "schedules.db")
    yield s
    s.close()


@pytest.fixture
def services(store):
    return LocalServices(store)


class TestArmazenamento:
    def test_sobrevive_ao_processo(self, tmp_path):
        # O motivo de existir SQLite aqui: a Pi reinicia, o alarme continua.
        caminho = tmp_path / "schedules.db"
        primeiro = ScheduleStore(caminho)
        primeiro.add("alarme", fire_at=time.time() + 3600)
        primeiro.close()

        segundo = ScheduleStore(caminho)
        assert len(segundo.pending()) == 1
        segundo.close()

    def test_pendentes_saem_em_ordem_de_disparo(self, store):
        store.add("timer", fire_at=time.time() + 300)
        store.add("timer", fire_at=time.time() + 60)
        assert [s.seconds_left() for s in store.pending()] == pytest.approx(
            [60, 300], abs=1
        )

    def test_cancelado_some_dos_pendentes(self, store):
        item = store.add("timer", fire_at=time.time() + 60)
        assert store.cancel(item.id) is True
        assert store.pending() == []

    def test_cancelar_duas_vezes_nao_mente(self, store):
        item = store.add("timer", fire_at=time.time() + 60)
        store.cancel(item.id)
        assert store.cancel(item.id) is False


class TestServicos:
    def test_criar_timer_responde_e_agenda(self, services, store):
        resposta = services.handle(match("põe um timer de 10 minutos"))
        assert resposta == "Timer de 10 minutos."
        assert store.pending()[0].seconds_left() == pytest.approx(600, abs=2)

    def test_singular_no_timer_de_um_minuto(self, services):
        assert services.handle(match("timer de um minuto")) == "Timer de 1 minuto."

    def test_alarme_sempre_cai_no_futuro(self, services, store):
        # Qualquer hora do relógio, o alarme tem que ser depois de agora.
        for hora in range(0, 24, 3):
            store._db.execute("DELETE FROM schedules")
            services.handle(match(f"me acorda às {hora}"))
            alvo = datetime.fromtimestamp(store.pending()[0].fire_at)
            assert alvo > datetime.now(), f"alarme das {hora}h nasceu vencido"

    @pytest.mark.parametrize(
        "agora, hora_pedida, dia_esperado",
        [
            # A regra: hoje se ainda não passou, amanhã se já passou.
            ("2026-09-01 08:00", 22, 1),   # de manhã, para as 22h -> hoje
            ("2026-09-01 23:00", 7, 2),    # à noite, para as 7h -> amanhã
            ("2026-09-01 07:00", 7, 2),    # na hora exata -> amanhã, não agora
            # O caso que quebrou o teste antigo: às 00h02, "22h" ainda é hoje.
            ("2026-09-02 00:02", 22, 2),
            ("2026-09-02 00:02", 0, 3),    # 00:00 ja passou por dois minutos
        ],
    )
    def test_proxima_ocorrencia_nao_depende_do_relogio(
        self, agora, hora_pedida, dia_esperado
    ):
        from device.local.service import _proxima_ocorrencia

        momento = datetime.strptime(agora, "%Y-%m-%d %H:%M")
        alvo = _proxima_ocorrencia(hora_pedida, 0, agora=momento)
        assert alvo.day == dia_esperado
        assert alvo > momento

    def test_cancelar_sem_nada_marcado(self, services):
        assert services.handle(match("cancela")) == "Nao tem nada marcado."

    def test_cancelar_com_um_pendente(self, services, store):
        services.handle(match("põe um timer de 10 minutos"))
        assert services.handle(match("cancela")) == "Timer cancelado."
        assert store.pending() == []

    def test_cancelar_ambiguo_pergunta_em_vez_de_chutar(self, services, store):
        # Cancelar o errado destrói a confiança no aparelho (plano, regra 1).
        services.handle(match("põe um timer de 10 minutos"))
        services.handle(match("me acorda às 7"))
        assert "Qual" in services.handle(match("cancela"))
        assert len(store.pending()) == 2

    def test_cancelar_com_alvo_escolhe_certo(self, services, store):
        services.handle(match("põe um timer de 10 minutos"))
        services.handle(match("me acorda às 7"))
        assert services.handle(match("cancela o alarme")) == "Alarme cancelado."
        assert [s.kind for s in store.pending()] == ["timer"]

    def test_listar_vazio(self, services):
        assert services.handle(match("quais timers eu tenho")) == "Nao tem nada marcado."

    def test_listar_junta_com_e(self, services):
        services.handle(match("põe um timer de 10 minutos"))
        services.handle(match("me acorda às 7"))
        resposta = services.handle(match("quais timers eu tenho"))
        assert " e " in resposta

    def test_que_horas_sai_por_extenso(self, services):
        # O aparelho fala; "07:05" viraria "zero sete zero cinco" no TTS.
        resposta = services.handle(match("que horas são"))
        assert resposta.startswith("Sao ")
        assert ":" not in resposta

    def test_intencao_desconhecida_nao_e_minha(self, services):
        from device.router.intents import Intent

        assert services.handle(Intent(name="tocar_musica")) is None


class TestAgendador:
    @pytest.mark.asyncio
    async def test_dispara_no_tempo(self, store):
        disparos = []

        async def on_fire(item):
            disparos.append(item)

        scheduler = Scheduler(store, on_fire)
        scheduler.start()
        store.add("timer", fire_at=time.time() + 0.15)
        scheduler.notify()
        await asyncio.sleep(0.5)
        await scheduler.stop()

        assert len(disparos) == 1
        assert store.pending() == []  # marcado como disparado, some dos pendentes

    @pytest.mark.asyncio
    async def test_cancelado_nao_dispara(self, store):
        disparos = []

        async def on_fire(item):
            disparos.append(item)

        item = store.add("timer", fire_at=time.time() + 0.15)
        store.cancel(item.id)

        scheduler = Scheduler(store, on_fire)
        scheduler.start()
        await asyncio.sleep(0.4)
        await scheduler.stop()

        assert disparos == []

    @pytest.mark.asyncio
    async def test_atrasado_demais_fica_calado(self, store):
        # Anunciar "seu timer de 10 minutos acabou" às três da manhã, porque o
        # aparelho estava desligado, é pior que ficar quieto.
        disparos = []

        async def on_fire(item):
            disparos.append(item)

        store.add("timer", fire_at=time.time() - GRACE - 10)
        scheduler = Scheduler(store, on_fire)
        scheduler.start()
        await asyncio.sleep(0.2)
        await scheduler.stop()

        assert disparos == []
        assert store.pending() == []  # mas some da fila: não fica pendurado


def test_sobrevive_sem_gateway():
    """O nível 0 não pode depender do módulo que fala com a rede.

    Não é teste de estilo. Se `device/local/` ou `device/router/` importarem o
    cliente do gateway, um dia alguém chama a rede no caminho do alarme, e o
    despertador passa a depender do Wi-Fi.
    """
    import device.local.service
    import device.local.store
    import device.router.intents

    for modulo in (device.local.service, device.local.store, device.router.intents):
        fonte = modulo.__file__
        with open(fonte, encoding="utf-8") as f:
            texto = f.read()
        assert "ws_client" not in texto, f"{fonte} importa o cliente do gateway"
        assert "websockets" not in texto, f"{fonte} fala com a rede"


class TestAvisoAoAgendador:
    """O elo que faltava: agendar tem que acordar o agendador.

    Nada disto aparecia nos testes de unidade -- o serviço gravava certo, o
    agendador disparava certo, e mesmo assim o timer não tocava, porque ninguém
    avisava ninguém. Só apareceu rodando o aparelho de verdade.
    """

    def test_criar_avisa(self, store):
        avisos = []
        services = LocalServices(store, on_change=lambda: avisos.append(1))
        services.handle(match("põe um timer de 10 minutos"))
        assert avisos == [1]

    def test_cancelar_avisa(self, store):
        avisos = []
        services = LocalServices(store, on_change=lambda: avisos.append(1))
        services.handle(match("põe um timer de 10 minutos"))
        services.handle(match("cancela"))
        assert len(avisos) == 2

    @pytest.mark.asyncio
    async def test_timer_criado_com_o_agendador_dormindo_ainda_dispara(self, store):
        # A reprodução exata do defeito: o agendador dorme (nada agendado), o
        # usuário cria um timer curto, e ele tem que tocar na hora -- não na
        # próxima soneca.
        disparos = []

        async def on_fire(item):
            disparos.append(item)

        scheduler = Scheduler(store, on_fire)
        services = LocalServices(store, on_change=scheduler.notify)
        scheduler.start()
        await asyncio.sleep(0.1)  # deixa o laço adormecer sem nada na fila

        store.add("timer", fire_at=time.time() + 0.15)
        services.on_change()
        await asyncio.sleep(0.5)
        await scheduler.stop()

        assert len(disparos) == 1, "o agendador dormiu apesar do aviso"
