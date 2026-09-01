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

---

## D12 — Modelos e gravações ficam fora do repositório

**Data:** 2026-09-01
**O que ficou:** nada de binário grande no git. Versionamos código, os corpora de
frases e os números medidos — o suficiente para refazer qualquer modelo.

**Por quê:** são 32 GB fora do git contra 496 KB de histórico versionado. E há um
motivo mais forte que tamanho: **o `.onnx` treinado é a voz do usuário**, e o
dataset são 30 minutos da voz dele limpos e transcritos. Qualquer um dos dois
clona a voz numa ferramenta moderna. O repositório é público.

**O que existe hoje, e onde:**

| Item | Tamanho | Reproduzível? |
|---|---|---|
| `lab/finetune/dataset/` | 79 MB | **Não** — é uma hora de leitura |
| `lab/models/piper/*.onnx` | 1,3 GB | Sim, a partir do dataset |
| `lab/models/piper_ckpt/` | 2,2 GB | Sim, baixando de novo |
| `lab/finetune/runs/` | 28 GB | Sim, e não vale guardar |
| `lab/finetune/arquivo/` | 364 MB | Não — gerações já apagadas do run |

**O risco que fica em aberto:** o dataset existe só no disco do usuário. Perdê-lo
custa regravar tudo. Backup privado resolve; publicar não é necessário para isso.

**Se um dia for publicar**, as rotas avaliadas:

- **GitHub Releases** — até 2 GB por arquivo, fora do histórico do git, bom para
  "a voz final da versão N".
- **Hugging Face** — feito para modelos, repositório privado grátis. É de lá que
  vieram os checkpoints pt-BR do Piper.
- **Git LFS** — evitar: 1 GB de cota grátis, e cada versão nova de um `.onnx` de
  61 MB consome de novo.

**Falta, e vale fazer antes de publicar qualquer coisa:** um manifesto versionado
dizendo de que época veio cada `.onnx`, com quais hiperparâmetros e qual WER
mediu. Hoje o nome do arquivo é a única pista.

---

## D13 — O áudio nunca entra no fio: o dispositivo transcreve antes de falar

**Data:** 2026-09-01
**O plano diz:** seção 4 especifica frames binários de PCM subindo do
dispositivo para o gateway, e `audio_end` fechando a fala.

**O que mudou:** o dispositivo grava, corta pelo VAD, transcreve com
faster-whisper e manda uma mensagem nova, `utterance`, com a frase pronta.
`audio_end` e os frames binários deixaram de existir no protocolo.

**Por quê:** é [D1](#d1--stt-e-tts-rodam-no-dispositivo-não-no-gateway) chegando
no código. Enquanto o STT era um stub no gateway, o canal binário servia para
carregar o texto digitado e exercitar o protocolo (D3). Com o STT real no
dispositivo, manter os frames seria manter um caminho que ninguém usa — e o
teste que garante que áudio não desce ([D7](#d7--pela-rede-sobe-só-texto-o-áudio-nasce-no-dispositivo))
não tinha simétrico para a subida.

**Consequências:**
- `gateway/stt/` foi removido. A pergunta em aberto de D1 — o gateway
  re-transcrever com um modelo maior — continua em aberto, mas ela precisaria do
  áudio no fio, que é exatamente o que esta decisão tira. Se voltar, volta como
  decisão nova e explícita.
- O gateway não fala mais `listening`: quem sabe que está ouvindo é o
  dispositivo, porque a captura é dele. A máquina de estados passou a ser
  dirigida dos dois lados.
- O modo texto virou `--text` em `device/main.py`, e continua útil: se a resposta
  está errada com o texto digitado, o problema não é o microfone.
- O modelo do STT carrega com `local_files_only` primeiro. Sem isso, o
  faster-whisper consulta o Hugging Face na carga mesmo com o modelo em disco —
  um aparelho que não abre o microfone com a internet caída contradiz a razão de
  D1 existir.

**Medido (PC, `small/int8`, CPU):** carga de 2,0 s; frases de 2,5 a 3,8 s
transcritas em ~2,2 s cada — RTF entre 0,6 e 0,9, contra os 0,43 da bancada, que
media com o modelo já aquecido e sem beam completo em disputa. Cabe no PC; na Pi
é o número que decide entre `small` e `base` (D9).

---

## D14 — O dispositivo reconecta sozinho; o turno perdido não volta

**Data:** 2026-09-01
**O plano diz:** seção 2 trata o WebSocket como um canal que existe. Não diz o
que acontece quando ele deixa de existir.

**O que mudou:** `GatewayClient` reconecta com espera crescente (0,5 s dobrando
até 30 s, com dispersão aleatória) e tenta indefinidamente. A queda no meio de
um turno vira `ConnectionLost`, que o laço do dispositivo trata voltando a
ouvir. Token recusado levanta `AuthRejected` e **não** entra em retentativa.

**Por quê:** não havia nada. Qualquer queda — Wi-Fi oscilando, gateway
reiniciando — terminava o processo do dispositivo com traceback. Na mesa isso
quase nunca acontece; num aparelho de prateleira o modo de falha é ficar mudo
até alguém notar, que é o pior que um assistente de voz pode fazer.

**O que a reconexão não recupera:** a resposta daquele turno. O histórico da
conversa vive na `Session` do gateway, que morre com a conexão; a sessão nova
começa sem memória. Reconectar devolve o aparelho, não o assunto. Persistir
histórico é outra decisão, e não foi tomada.

**Duas escolhas que não são óbvias:**

- **A retentativa mora no envio, não na recepção.** A primeira versão
  reconectava dentro de `receive()`, antes de levantar `ConnectionLost` — e o
  aparelho ficava preso no laço de espera em vez de voltar a ouvir. Agora
  `receive()` só avisa que caiu, e a reconexão acontece quando há uma frase de
  verdade para entregar.
- **`AuthRejected` não herda de `OSError`.** Herdando, ela cairia no `except`
  da retentativa e um token errado viraria espera infinita em vez de erro. Foi
  exatamente o que aconteceu na primeira versão, e o teste é o que fixa isso.

**Verificado:** `tests/test_reconnect.py` sobe um gateway WebSocket real e o
derruba no meio do turno. Em campo, matando o uvicorn entre dois turnos: o turno
seguinte funcionou 2,7 s depois de o gateway voltar, sem religar nada.

---

## D15 — A imagem do gateway não instala o `requirements.txt`

**Data:** 2026-09-01
**O plano diz:** a Fase 1 entrega "gateway containerizado, autenticação por
token, latência simulada", com aceite em `docker compose up` subindo tudo.

**O que mudou:** as dependências do gateway saíram para
`requirements-gateway.txt`, e é só ele que entra na imagem. O `requirements.txt`
passa a ser o ambiente de desenvolvimento — os dois lados mais a bancada — e
inclui o outro por referência.

**Por quê:** o `Dockerfile` foi escrito quando o gateway ainda tinha STT. Depois
de [D13](#d13--o-áudio-nunca-entra-no-fio-o-dispositivo-transcreve-antes-de-falar)
ele não tem modelo nenhum: as importações de `gateway/` e `common/` são
`fastapi`, `httpx`, `dotenv` e biblioteca padrão. Instalar o arquivo inteiro
levaria `torch`, `transformers`, `speechbrain`, `vosk` e `piper-tts[train]` para
dentro da imagem — vários GB para um processo que só fala HTTP e WebSocket, num
container que um dia sobe numa VPS pequena.

**Três coisas que estavam quebradas e não apareciam porque ninguém rodou:**

- **O container não achava o Ollama.** O `.env` tem
  `OLLAMA_URL=http://localhost:11434`, correto para o dispositivo e errado
  dentro do container, onde `localhost` é ele mesmo. O compose agora sobrescreve
  com `host.docker.internal`, e declara `host-gateway` em `extra_hosts` — o
  Docker Desktop resolve esse nome sozinho, o Docker Engine em Linux (o caso da
  VPS) não.
- **Não havia `.dockerignore`.** O contexto de build é a raiz do projeto, porque
  `common/` precisa entrar junto. Sem ignorar nada, o `.venv` e os modelos de
  `lab/` iriam para o daemon antes de a primeira linha do Dockerfile rodar.
- **O processo rodava como root.** Corrigido: usuário `marcos`, uid 1000.

**Consequências:**
- Uma dependência nova do gateway tem que ser adicionada em
  `requirements-gateway.txt`, não no outro. A regra é literal: entra ali se
  `gateway/` importa.
- `gateway/stt/` sumiu do disco também — o D13 apagou os `.py` e a pasta ficou
  para trás com um `__pycache__` dentro.

**Não verificado:** `docker compose up` **não foi executado**. Esta máquina não
tem Docker nem WSL2. O critério de aceite da Fase 1 continua em aberto, e o que
está aqui é código escrito com cuidado, não comportamento observado. A primeira
pessoa a rodar isso deve tratar como não testado.
