# Decisões tomadas depois do plano

Registro seco: o quê e o porquê de cada decisão fechada. O caminho até ela — as
dúvidas, as tentativas, o que quebrou — está no [diário de bordo](diario-de-bordo.md).

O [ultraplan v3](ultraplan-v3-assistente-voz-portatil.md) é a especificação e
**não é reescrito** — ele registra o que se sabia quando foi escrito. Este
arquivo registra onde a construção divergiu dele, e por quê. Se o código
contradiz o plano, a explicação tem que estar aqui.

---

## D1 — STT e TTS rodam no dispositivo, não no gateway

**Data:** 2026-08-31
**O plano diz:** seção 1 coloca `STT → CLASSIFICADOR → LLM → TTS` inteiramente no
gateway, e o dispositivo só transmite áudio.

**O que mudou:** os dois passam para a Pi. Pela rede sobe só texto.

**Por quê:** o plano tem uma contradição interna. A seção 5 exige que o nível 0
(timer, alarme, hora, volume) funcione **sem rede**, e a seção 1 coloca o
roteador de intenções no dispositivo. Mas o roteador casa regex e embeddings
sobre *texto* — ele precisa de uma transcrição para decidir qualquer coisa. Com
o STT no gateway, um comando de timer com a internet caída nunca chega a ser
classificado. Nível 0 offline só existe com STT local.

O TTS veio junto por consequência: se o aparelho entende offline mas não
consegue falar, ele não confirma o timer que acabou de criar. O Piper mede
RTF 0,05, o que torna o custo dessa decisão quase nulo.

**Consequências:**
- A Pi carrega dois modelos além do wake word. Orçamento de CPU e RAM ficou mais
  apertado; a seção 8 do plano precisa ser relida com isso em mente.
- O tráfego por interação cai de ~0,25 MB para alguns KB (seção 12 fica
  desatualizada, para melhor).
- Fica em aberto se o gateway deve **re-transcrever** o áudio com um modelo maior
  quando a pergunta vai para o LLM, protegendo contra o modelo pequeno errar um
  nome próprio. Decidir com o WER da voz real na mão.

---

## D2 — Nada de STT/TTS de nuvem

**Data:** 2026-08-31
**O plano diz:** seção 9 escolhe "API de nuvem (trocável por faster-whisper)"
para STT, e "Piper ou TTS de nuvem" para TTS.

**O que mudou:** só candidatos offline. O `edge-tts` continua em `lab/` como teto
de qualidade para comparação, marcado como não-candidato.

**Por quê:** decorre de D1 e de preferência explícita. Um motor de nuvem não pode
ser o que diz "timer de dez minutos" com a internet fora.

---

## D3 — Modo texto na Fase 0, antes do microfone

**Data:** 2026-08-31
**O plano diz:** a Fase 0 entrega `mic → STT → LLM → TTS`.

**O que mudou:** o loop dos dois processos foi fechado primeiro em modo texto,
com o que se digita viajando pelo mesmo canal binário que levará PCM.

**Por quê:** valida protocolo, máquina de estados, autenticação e latência
simulada sem depender da escolha de STT, que ainda está aberta em `lab/`. A
captura de áudio substitui só a entrada; nada do caminho já validado muda.

---

## Em aberto

- **Nome do assistente.** O código usa "BMO", herdado do plano, enquanto o
  repositório se chama Marcos-AI. Renomear ou manter?
- **LLM de produção.** O plano fixa `deepseek-v4-flash`; hoje roda Ollama local
  em dev. Falta confirmar id e preço na documentação oficial antes de codar o
  provedor de nuvem.

---

## D4 — Voz própria por fine-tune do Piper, não por clonagem zero-shot

**Data:** 2026-08-31
**O plano diz:** seção 9 escolhe "Piper ou TTS de nuvem", sem tratar de voz
personalizada.

**O que mudou:** a voz do assistente passa a ser a do usuário, obtida por
fine-tune de um checkpoint pt-BR.

**Por quê:** clonagem zero-shot (XTTS-v2, F5-TTS) entrega timbre sem treino, mas
são modelos de 1,5 a 2 GB que exigem GPU — na Pi não rodam. O fine-tune do Piper
entrega um modelo de 60 MB a RTF 0,05, que é o único caminho com timbre próprio
**e** velocidade de Pi.

Clonagem zero-shot continua útil para uma coisa: pré-gerar o cache de frases
fixas da regra 2 da seção 5, uma vez no PC, sem custo em execução.

**Consequências:**
- Os checkpoints de treino pt-BR não estão mais no repositório oficial do Piper
  (saiu do ar). Os que sobreviveram estão no OpenVoiceOS, e são de vozes "high"
  que nem aparecem na lista oficial de download.
- Exige 30 a 60 min de gravação do usuário — que servem também para o wake word
  da seção 9.

---

## D5 — Dataset de voz precisa de mais de 15 minutos

**Data:** 2026-08-31
**O que mudou:** o primeiro treino, com 15,2 min e 203 frases, foi descartado. O
corpus subiu para 315 frases (~30 min).

**Por quê:** medido, não suposto. Na época 318 o WER do corpus tinha caído para
11,3% enquanto o de texto novo ficava parado em 39,7% — a assinatura de
memorização. Não era falta de épocas: 14.828 passos já haviam rodado. Era falta
de material para generalizar.

Uma voz que só sabe dizer as frases gravadas é inútil aqui, porque a resposta do
LLM nunca é uma frase pré-escrita.

**Consequências:**
- Todo treino passa a ser validado com `lab.finetune.generalize`, que mede WER
  em frases nunca gravadas *e* no corpus. A distância entre as duas é o que
  distingue "decorou" de "ainda cru" — diagnósticos com decisões opostas.
- Trechos de 10–15 s viraram o formato padrão: o `collate` do Piper preenche o
  batch até a amostra mais longa, e na inferência ele divide por sentença de
  qualquer forma.
- Se 30 min não bastarem, um bloco 4. A medição responde sem adivinhação.
