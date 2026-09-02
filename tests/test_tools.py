"""Ferramentas: o LLM pede, o dispositivo executa.

O critério de aceite da Fase 3 tem duas metades, e a segunda é a que costuma
ficar sem teste: *"o LLM chama as ferramentas certas **e não inventa chamadas
inexistentes**"*. Uma ferramenta inventada não pode virar traceback nem silêncio
-- tem que voltar como falha, para o modelo poder se corrigir.
"""

from __future__ import annotations

import pytest

from common.messages import ToolCall, ToolResult
from common.serialization import decode, encode
from device.local.service import LocalServices
from device.local.store import ScheduleStore
from device.main import FERRAMENTAS, executar_ferramenta
from gateway.tools import DEVICE_TOOLS, TOOL_TO_INTENT


@pytest.fixture
def services(tmp_path):
    store = ScheduleStore(tmp_path / "schedules.db")
    yield LocalServices(store)
    store.close()


class TestOsDoisLadosConcordam:
    """Gateway e dispositivo mantêm a mesma tabela. Se divergirem, o modelo
    chama uma ferramenta que o aparelho não conhece -- e só se descobre em uso."""

    def test_mesma_tabela_dos_dois_lados(self):
        assert FERRAMENTAS == TOOL_TO_INTENT

    def test_toda_ferramenta_declarada_e_executavel(self):
        declaradas = {t.name for t in DEVICE_TOOLS}
        assert declaradas == set(FERRAMENTAS)

    def test_toda_ferramenta_tem_descricao_util(self):
        # A descrição é o que o modelo lê para decidir. Uma linha vaga aqui é a
        # causa mais comum de ferramenta chamada na hora errada.
        for tool in DEVICE_TOOLS:
            assert len(tool.description) > 40, tool.name
            assert tool.parameters["type"] == "object"


class TestExecucaoNoDispositivo:
    def test_criar_timer_com_segundos_crus(self, services):
        # O LLM manda segundos; o regex mandaria quantidade + unidade.
        result = executar_ferramenta(
            services, ToolCall(id="1", name="criar_timer", args={"segundos": 5400})
        )
        assert result.ok
        assert result.value == "Timer de 1 hora e meia."

    @pytest.mark.parametrize(
        "segundos, esperado",
        [
            (60, "Timer de 1 minuto."),
            (600, "Timer de 10 minutos."),
            (3600, "Timer de 1 hora."),
            (7200, "Timer de 2 horas."),
            (90, "Timer de 90 segundos."),
        ],
    )
    def test_duracao_falada_a_partir_de_segundos(self, services, segundos, esperado):
        # "timer de cinco mil e quatrocentos segundos" não é português falado.
        result = executar_ferramenta(
            services, ToolCall(id="1", name="criar_timer", args={"segundos": segundos})
        )
        assert result.value == esperado

    def test_criar_alarme(self, services):
        result = executar_ferramenta(
            services, ToolCall(id="1", name="criar_alarme", args={"hora": 7, "minuto": 30})
        )
        assert result.ok
        assert "7 e meia" in result.value

    def test_listar_depois_de_criar(self, services):
        executar_ferramenta(
            services, ToolCall(id="1", name="criar_timer", args={"segundos": 600})
        )
        result = executar_ferramenta(
            services, ToolCall(id="2", name="listar_agendamentos", args={})
        )
        assert result.ok
        assert "timer" in result.value

    def test_o_resultado_volta_com_o_mesmo_id(self, services):
        # O gateway casa a resposta pelo id; trocar isso faria uma chamada
        # antiga e atrasada ser lida como resposta da atual.
        result = executar_ferramenta(
            services, ToolCall(id="abc123", name="listar_agendamentos", args={})
        )
        assert result.id == "abc123"


class TestOModeloErrando:
    """A metade do critério de aceite que fala de chamadas inventadas."""

    def test_ferramenta_que_nao_existe(self, services):
        result = executar_ferramenta(
            services, ToolCall(id="1", name="acender_a_luz", args={})
        )
        assert result.ok is False
        assert "desconhecida" in result.error

    def test_argumento_faltando(self, services):
        result = executar_ferramenta(services, ToolCall(id="1", name="criar_timer", args={}))
        assert result.ok is False
        assert "invalidos" in result.error

    def test_numero_como_string_e_aceito(self, services):
        # Não é hipótese: o llama3.1:8b mandou {"segundos": "5400"} na primeira
        # execução real, com o schema dizendo `integer`. Modelo pequeno erra o
        # tipo com frequência, e recusar isso seria recusar uma chamada correta.
        result = executar_ferramenta(
            services, ToolCall(id="1", name="criar_timer", args={"segundos": "5400"})
        )
        assert result.ok
        assert result.value == "Timer de 1 hora e meia."

    def test_argumento_com_tipo_errado(self, services):
        result = executar_ferramenta(
            services, ToolCall(id="1", name="criar_timer", args={"segundos": "dez minutos"})
        )
        assert result.ok is False

    def test_horario_impossivel(self, services):
        result = executar_ferramenta(
            services, ToolCall(id="1", name="criar_alarme", args={"hora": 25, "minuto": 0})
        )
        assert result.ok is False

    def test_duracao_negativa(self, services):
        result = executar_ferramenta(
            services, ToolCall(id="1", name="criar_timer", args={"segundos": -60})
        )
        assert result.ok is False

    def test_erro_nao_derruba_o_processo(self, services):
        # O aparelho tem que continuar de pé depois de o modelo errar.
        executar_ferramenta(services, ToolCall(id="1", name="criar_timer", args={}))
        bom = executar_ferramenta(
            services, ToolCall(id="2", name="criar_timer", args={"segundos": 60})
        )
        assert bom.ok


class TestProtocolo:
    def test_tool_result_com_valor_atravessa_o_fio(self):
        original = ToolResult(id="1", ok=True, value="Timer de 10 minutos.")
        assert decode(encode(original)) == original

    def test_tool_result_de_falha_atravessa_o_fio(self):
        original = ToolResult(id="1", ok=False, error="ferramenta desconhecida: x")
        assert decode(encode(original)) == original


class TestFerramentasTerminais:
    """O resultado da ferramenta é a resposta, sem segunda rodada de LLM.

    Isto começou como otimização e virou correção: com o modelo reescrevendo a
    lista, "o que eu tenho marcado" com dois itens na fila voltava com um só.
    """

    def test_todas_as_ferramentas_do_dispositivo_sao_terminais(self):
        from gateway.tools import TERMINAL_TOOLS

        # Todas devolvem frase pronta para falar. Se alguém adicionar uma que
        # precise de interpretação do modelo, este teste é o lembrete de decidir
        # conscientemente em vez de herdar o comportamento.
        assert TERMINAL_TOOLS == set(TOOL_TO_INTENT)

    def test_a_frase_do_dispositivo_ja_e_falavel(self, services):
        # Sem LLM depois dela, ela vai ao ar como está: tem que ser uma frase
        # inteira, com maiúscula e ponto, e sem formato de tela.
        executar_ferramenta(
            services, ToolCall(id="1", name="criar_timer", args={"segundos": 600})
        )
        result = executar_ferramenta(
            services, ToolCall(id="2", name="listar_agendamentos", args={})
        )
        assert result.value[0].isupper()
        assert result.value.endswith(".")
        assert ":" not in result.value

    def test_lista_nao_perde_item(self, services):
        for segundos in (300, 600, 900):
            executar_ferramenta(
                services, ToolCall(id="x", name="criar_timer", args={"segundos": segundos})
            )
        result = executar_ferramenta(
            services, ToolCall(id="2", name="listar_agendamentos", args={})
        )
        assert result.value.count("timer") == 3
