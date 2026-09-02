"""As ferramentas que o LLM pode pedir, mas que **o dispositivo** executa.

Esta é a linha 149 do plano virando código: *"quando o LLM interpreta 'me acorda
às 7', quem grava e dispara é o Pi, não o gateway"*. O gateway só declara que
elas existem e transporta a chamada; a execução acontece do outro lado do fio,
em `device/local/`, no mesmo lugar onde o roteador de regex já executa.

A simetria é proposital: uma frase que o regex reconhece e uma frase que só o
LLM entende terminam no **mesmo** código, com os mesmos slots. O que muda é
quem interpretou, não quem executa. Se um dia divergirem, o aparelho passa a ter
dois comportamentos para a mesma frase, dependendo de a internet estar de pé.
"""

from __future__ import annotations

from gateway.llm.base import Tool

#: Descrições em português porque o modelo é instruído em português e a decisão
#: de chamar a ferramenta é tomada lendo isto. Cada uma diz também **quando não**
#: usar: sem isso, "que horas são em Tóquio" vira um alarme.
DEVICE_TOOLS: list[Tool] = [
    Tool(
        name="criar_timer",
        description=(
            "Cria um timer de contagem regressiva no aparelho, para avisar depois de "
            "uma duracao. Use para pedidos como 'me avisa daqui a uma hora e meia'. "
            "Nao use para um horario do relogio -- para isso use criar_alarme."
        ),
        parameters={
            "type": "object",
            "properties": {
                "segundos": {
                    "type": "integer",
                    "description": "Duracao total em segundos. 'Uma hora e meia' = 5400.",
                }
            },
            "required": ["segundos"],
        },
    ),
    Tool(
        name="criar_alarme",
        description=(
            "Marca um alarme para um horario do relogio. Use para 'me acorda as sete "
            "e meia'. Se o horario ja passou hoje, o aparelho marca para amanha "
            "sozinho -- nao tente calcular a data."
        ),
        parameters={
            "type": "object",
            "properties": {
                "hora": {"type": "integer", "description": "Hora em formato 24h, 0 a 23."},
                "minuto": {"type": "integer", "description": "Minuto, 0 a 59."},
            },
            "required": ["hora", "minuto"],
        },
    ),
    Tool(
        name="listar_agendamentos",
        description=(
            "Lista os timers e alarmes que estao marcados. Use quando perguntarem o "
            "que esta marcado, quanto falta, ou se existe algum alarme."
        ),
        parameters={"type": "object", "properties": {}},
    ),
    Tool(
        name="cancelar_agendamento",
        description=(
            "Cancela um timer ou alarme marcado. Se houver mais de um e o pedido nao "
            "disser qual, o aparelho responde perguntando -- nao escolha por conta."
        ),
        parameters={
            "type": "object",
            "properties": {
                "alvo": {
                    "type": "string",
                    "enum": ["timer", "alarme"],
                    "description": "Omita se o pedido nao disser qual dos dois.",
                }
            },
        },
    ),
]

#: Ferramentas cujo resultado **é** a resposta: o dispositivo já devolve uma
#: frase redigida para ser falada ("Timer de 10 minutos."), e o gateway a entrega
#: como está, sem uma segunda rodada de LLM.
#:
#: Não é otimização, é correção. Perguntando "o que eu tenho marcado" com um
#: timer e um alarme na fila, o llama3.1:8b recebeu os dois e respondeu só o
#: alarme -- resumir uma lista é perder item. A tentativa de consertar isso pelo
#: prompt ("repita sem omitir") saiu pior: o modelo passou a narrar que ia
#: chamar a ferramenta em vez de responder.
#:
#: De quebra, a frase falada passa a ser idêntica venha ela do regex ou do LLM,
#: e o turno economiza uma rodada inteira do modelo.
TERMINAL_TOOLS: frozenset[str] = frozenset(
    {"criar_timer", "criar_alarme", "listar_agendamentos", "cancelar_agendamento"}
)

#: Nome da ferramenta -> nome da intenção que `device/local/` já sabe executar.
#: O dicionário existe para que os nomes possam divergir: o LLM lê
#: "listar_agendamentos", que é descritivo, e o dispositivo executa "listar",
#: que é o que o roteador de regex já produzia antes de existir LLM nenhum.
TOOL_TO_INTENT: dict[str, str] = {
    "criar_timer": "criar_timer",
    "criar_alarme": "criar_alarme",
    "listar_agendamentos": "listar",
    "cancelar_agendamento": "cancelar",
}
