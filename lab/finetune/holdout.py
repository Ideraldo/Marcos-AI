"""Frases que NUNCA foram gravadas -- o teste de generalização.

Um fine-tune com 15 minutos corre um risco concreto: em vez de aprender o seu
timbre, o modelo decora as suas 203 frases. Ele soaria ótimo lendo "Timer de dez
minutos" e desmoronaria em qualquer texto novo — que é justamente o que o
assistente vai falar o dia inteiro, já que a resposta do LLM nunca é uma frase
pré-escrita.

Nada aqui aparece no corpus de treino, e é de propósito. Cada frase sonda algo
que o modelo tem que fazer sem nunca ter visto:

* palavras raras e nomes próprios que não estão nas gravações
* números e horas em formatos diferentes dos treinados
* estrangeirismos que a fonética do português não cobre
* frases muito mais longas do que qualquer uma do corpus
* construções de pergunta e exclamação pouco frequentes no treino

Se soar bem aqui, aprendeu a falar. Se soar bem só no corpus, decorou.
"""

from __future__ import annotations

HOLDOUT: dict[str, str] = {
    "nomes": "Bartolomeu e Guilhermina viajaram de Petrópolis até Florianópolis.",
    "raras": "O arqueólogo catalogou hieróglifos numa estela de quartzo translúcido.",
    "numeros": "Faltam vinte e sete minutos para as dezoito e quarenta e cinco.",
    "moeda": "O orçamento subiu de oitocentos e noventa para dois mil e trezentos reais.",
    "ingles": "Abra o dashboard do GitHub e faça deploy do backend em background.",
    "pergunta": "Será que amanhã, apesar de tudo, ainda conseguiremos chegar a tempo?",
    "exclamacao": "Que absurdo! Ninguém avisou que o prazo tinha mudado?",
    "sequencia": "Zero, um, dois, três, quatro, cinco, seis, sete, oito, nove, dez.",
    "trava": "O rato roeu a roupa do rei de Roma e a rainha remendou com raiva.",
    "sibilantes": "Seis cisnes sussurravam sob o chuvisco enquanto o xerife assobiava.",
    "nasais": "Amanhã de manhã, cem homens comuns comeram pão com manteiga em Campinas.",
    "longa": (
        "Ainda que ninguém tivesse previsto aquele desfecho, a comissão decidiu, "
        "por unanimidade e depois de quase quatro horas de debate acalorado, "
        "que o projeto seria arquivado até que surgissem evidências novas."
    ),
    "tecnica": "A latência do WebSocket ficou em cento e cinquenta milissegundos.",
    "abreviacao": "O Dr. Almeida atende na Av. Paulista, nº 1500, 3º andar.",
    "sigla": "A ONU e o BNDES assinaram um acordo com o IBGE nesta quinta-feira.",
}
