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

---

## D6 — Hiperparâmetros de fine-tune, não os padrões do Piper

**Data:** 2026-08-31
**O que mudou:** learning rate do gerador de `2e-4` para `1e-4`, e o alvo de
épocas de 2000 para 1000.

**Por quê:** os padrões do Piper são calibrados para **treinar do zero** com
dezenas de milhares de amostras. Num fine-tune de meia hora, `2e-4` afasta o
modelo rápido demais dos pesos da base — que já sabem falar português — e o leva
a ajustar as poucas frases disponíveis, que é a definição de decorar.

Agrava no nosso caso que o `lr_decay` do Piper é `0.999875` **por época**,
pensado para épocas de centenas de passos. As nossas têm ~40, então a taxa quase
não decai ao longo do treino.

Sobre as épocas: a unidade que importa é **passo**, não época. O v1 rodou 368
épocas, que são apenas 14.828 passos; fine-tunes de VITS costumam pedir 10 a 30
mil.

**Consequências:**
- O timbre demora mais a aparecer. É o preço de não memorizar.
- `--lr` fica exposto: se o v2 ainda decorar, `5e-5` é o próximo degrau, antes de
  gravar mais.
- `accumulate_grad_batches` **não é uma opção aqui**: o VITS treina com
  otimização manual (dois otimizadores) e o Lightning recusa acumulação nesse
  modo. Para batch maior, só subindo `--batch-size`.
- Early stopping automático segue descartado, seguindo o aviso dos autores do
  Piper: o mel L1 satura cedo enquanto as perdas adversariais ainda removem
  artefatos audíveis.

---

## D7 — Pela rede sobe só texto; o áudio nasce no dispositivo

**Data:** 2026-09-01
**O plano diz:** seção 4 especifica frames binários de TTS indo do gateway para o
dispositivo.

**O que mudou:** o gateway envia a resposta como texto, uma frase por vez
(`Transcript` com `final=false`), e o dispositivo sintetiza e toca. Nenhum áudio
atravessa a rede em nenhuma direção — no sentido dispositivo→gateway isso ainda
está pendente, junto com o STT local.

**Por quê:** é a consequência prática de [D1](#d1--stt-e-tts-rodam-no-dispositivo-não-no-gateway).
Se a síntese roda na Pi, mandar áudio pronto pelo fio seria pagar duas vezes.

**Consequências:**
- Uma interação custa alguns KB em vez dos ~0,25 MB estimados na seção 12.
- O aparelho fala com a internet caída, que é requisito para confirmar timer e
  alarme.
- `gateway/tts/` continua existindo como interface, mas sem uso no caminho
  principal. A implementação que vale mora em `device/tts/`.
- O streaming por frase foi preservado e virou teste: `tests/test_session_protocol.py`
  falha se alguém voltar a mandar bytes ou a esperar a resposta inteira.

**Medido:** primeiro chunk de áudio em 0,32 s depois do texto chegar, com a voz
`pt_BR-ideraldo-medium` — dentro dos 150–400 ms da seção 11, com folga para a Pi.

---

## D8 — O assistente se chama Marcos

**Data:** 2026-09-01
**O plano diz:** o ultraplan o chama de "BMO" no título e nos exemplos.

**O que mudou:** o nome no código passa a ser Marcos, alinhado ao repositório.
`device_id` vira `marcos-01`, os loggers viram `marcos.*`, e o system prompt
agora diz "Você é o Marcos".

**Por quê:** o aparelho já responde falando, e ouvi-lo dizer "Sou o BMO" deixou a
inconsistência concreta. Renomear agora custa uma varredura; depois de o nome
aparecer em logs, configurações e gravações, custa mais.

**Consequências:** o `DEVICE_ID` padrão mudou. Um `.env` antigo com `bmo-01`
continua funcionando — é só um identificador —, mas convém atualizar.

---

## D9 — STT: começar pelo mais rápido e trocar se doer

**Data:** 2026-09-01
**A tensão:** o `small` acerta (9,0% de WER, 2,2% em comandos) e provavelmente
não cabe no orçamento da Pi; o `base` cabe com folga e erra os comandos.

**O que ficou:** começar com o mais rápido que for aceitável e só subir de
tamanho se a qualidade doer no uso real. Medir na Pi antes de decidir em
definitivo; testar whisper.cpp e sherpa-onnx, que são bem mais rápidos em ARM e
podem tornar a escolha desnecessária.

**Por quê:** é mais barato descobrir que um modelo pequeno bastava do que
descobrir que o grande não cabia depois de construir em cima dele.

**Sobre a divisão local/remoto:** quem decide não é o STT, é o **roteador de
intenções**, e ele trabalha sobre texto — por isso o STT precisa ser local
([D1](#d1--stt-e-tts-rodam-no-dispositivo-não-no-gateway)). O fluxo é o da seção
5 do plano: o dispositivo transcreve, o roteador tenta casar a frase com uma
intenção conhecida, e só manda para a VPS o que não casou.

---

## D10 — Sem VPS por enquanto; tudo local

**Data:** 2026-09-01
**O plano diz:** seção 2 recomenda comprar a VPS antes do hardware, porque é
cancelável e entrega o número de latência real.

**O que mudou:** adiado. O desenvolvimento segue inteiramente local.

**Por quê:** nada do que falta construir depende dela. Roteador, alarmes locais,
rosto e wake word são todos do lado do dispositivo. A VPS entra quando houver o
que medir.

**Consequência:** a Fase 5 continua sendo o primeiro gasto, quando chegar a hora.

---

## D11 — LLM open source, sem provedor de nuvem

**Data:** 2026-09-01
**O plano diz:** seção 6 escolhe `deepseek-v4-flash` via API.

**O que mudou:** o projeto segue em modelo aberto, rodando local via Ollama. A
interface `LLMProvider` continua sendo o ponto de troca, então migrar depois é
escrever uma implementação nova e mudar `build_llm`.

**Por quê:** preferência do usuário, e o Ollama já cobre o desenvolvimento.

**Consequências:**
- A busca fundamentada na internet, que motivou a escolha da API na seção 6,
  continua sendo o teste difícil. Um modelo de 8B pode não dar conta.
- Some a dependência de chave de API e o custo mensal.
- Se a qualidade doer, a troca é localizada — não é reescrita.
