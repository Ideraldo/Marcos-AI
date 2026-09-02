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
  `common/` precisa entrar junto. Sem ignorar nada, iriam para o daemon **41 GB**
  (medido: 5,8 GB de `.venv`, 7,0 GB de `lab/models`, 28 GB de `lab/finetune`)
  antes de a primeira linha do Dockerfile rodar. O `.gitignore` não vale aqui —
  o Docker não lê aquele arquivo.
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

---

## D16 — O Docker fica para a VPS; a virtualização segue desligada aqui

**Data:** 2026-09-01
**O plano diz:** a Fase 1 aceita quando `docker compose up` sobe tudo, na
máquina de desenvolvimento.

**O que mudou:** o critério de aceite da Fase 1 fica **adiado até a Fase 5**, e
será verificado na VPS. Nesta máquina, o gateway continua rodando com `uvicorn`
direto.

**Por quê:** a virtualização está desligada no firmware — confirmado por duas
fontes independentes (`Win32_Processor.VirtualizationFirmwareEnabled` e
`systeminfo`: *"Virtualização Habilitada no Firmware: Não"*). O processador
suporta; é escolha de BIOS. E é escolha deliberada: com ela ligada, o Vanguard
do Valorant não deixa o jogo abrir. Esta máquina também é de jogo.

Sem virtualização não há WSL2, e sem WSL2 não há Docker Desktop. Não é
contornável por elevação nem por configuração do Docker.

**Por que isso custa pouco:** a imagem existe para rodar **na VPS**, que é Linux
com Docker Engine — onde nada disso se aplica. Verificar aqui seria conveniente,
não necessário. E o que o container mudaria no desenvolvimento é nada: o
`uvicorn` sobe o mesmo `gateway.main:app`.

**O que fica em aberto, e é preciso lembrar:** o `Dockerfile`, o
`docker-compose.yml` e o `.dockerignore` de [D15](#d15--a-imagem-do-gateway-não-instala-o-requirementstxt)
**nunca foram executados**. O primeiro `docker compose up` da vida deles vai ser
na VPS, no dia do deploy — que é o pior dia para descobrir um erro de sintaxe.
Se aparecer qualquer outra máquina com Docker antes disso (um notebook, um
runner de CI, a Pi), rodar o build ali é meia hora que se paga.

**Alternativa considerada e descartada:** Docker Desktop com backend Hyper-V em
vez de WSL2. Não resolve — o Hyper-V exige a mesma virtualização de firmware.

---

## D17 — O aparelho liga sem o gateway, e tenta o nível 0 antes da rede

**Data:** 2026-09-01
**O plano diz:** a seção 2 trata a conexão com o gateway como o canal que o
dispositivo abre ao subir. A seção 5 exige que o nível 0 funcione sem rede, mas
não diz o que acontece no momento do boot.

**O que mudou:** duas coisas, e elas são a mesma decisão vista de dois lados.

1. `GatewayClient.__aenter__` tenta conectar **uma vez** e segue mesmo falhando.
   Sem gateway, o aparelho sobe em modo local e avisa. A retentativa infinita de
   [D14](#d14--o-dispositivo-reconecta-sozinho-o-turno-perdido-não-volta)
   continua existindo para quedas em segundo plano, mas o envio de uma frase
   passa a ter orçamento (`CONNECT_BUDGET`, 8 s): quem está esperando resposta
   merece um "não deu" em vez de silêncio.
2. `answer()` consulta o roteador **antes** de tocar na rede. Casou no nível 0,
   resolve e fala; não casou, sobe.

**Por quê:** o critério de aceite da Fase 2 é "timer funciona com o gateway
desligado", e um aparelho que não liga sem o servidor nunca cumpriria isso.
A ordem no `answer()` é o que dá ao timer a latência que a seção 11 orça
(< 200 ms) — consultar a rede primeiro para depois descobrir que a intenção era
local seria pagar o pior caso em todo comando bom.

**Consequências:**
- Com o gateway fora, uma pergunta de nível 2 é respondida com voz: *"não
  consigo falar com o servidor agora; timer e alarme continuam funcionando"*.
  Silêncio seria indistinguível de microfone quebrado.
- `device/local/` e `device/router/` não importam `ws_client` nem `websockets`,
  e há um teste que falha se alguém importar. Não é estilo: é o que impede que,
  um dia, o caminho do despertador passe a depender do Wi-Fi.
- As frases que não casam vão para o log como `nivel 2`. Em um mês esse log diz
  quais intenções promover (plano, seção 5, regra 4).

**O que ficou de fora, e é consciente:** a similaridade por embeddings. Hoje o
nível 0 é só regex, o que cobre formato rígido — duração, horário, "cancela" — e
não cobre paráfrase ("me lembra de tirar o bolo quando der uma meia horinha").
Isso não é uma lacuna silenciosa: o que não casa sobe para o LLM, que é o
comportamento correto pela regra 1. Os embeddings entram quando houver log real
dizendo quais paráfrases as pessoas usam de verdade nesta casa — escolher as
frases de exemplo por adivinhação seria treinar contra um usuário imaginário.

**Também de fora:** volume ("aumenta o volume") está no nível 0 do plano e não
foi implementado. Ele depende do mixer do sistema operacional, que é
código específico de plataforma e não se testa na mesa do jeito que o resto se
testou.

---

## D18 — Ferramentas do dispositivo: o LLM pede, o Pi executa, e o resultado é a resposta

**Data:** 2026-09-01
**O plano diz:** a seção 4, linha 149: *"quando o LLM interpreta 'me acorda às 7',
quem grava e dispara é o Pi, não o gateway"*. A Fase 3 entrega ferramentas no
gateway, aceita quando *"o LLM chama as ferramentas certas e não inventa chamadas
inexistentes"*.

**O que mudou:** `gateway/tools/device_tools.py` declara quatro ferramentas —
`criar_timer`, `criar_alarme`, `listar_agendamentos`, `cancelar_agendamento` —
que o gateway **não executa**. Ele transporta a chamada até o dispositivo, espera
o `tool_result` e segue. A execução acontece em `device/local/`, o mesmo código
que o roteador de regex já usava antes de existir LLM no caminho.

Até aqui o gateway mandava `tool_call` pelo fio e ninguém esperava resposta; do
outro lado, o dispositivo respondia `not implemented` a tudo.

**Por quê:** é a regra 3 da seção 5 (a execução é sempre local) encontrando a
Fase 2. Uma frase que o regex reconhece e uma que só o LLM entende terminam no
**mesmo** `LocalServices`, com os mesmos slots. Se divergissem, o aparelho teria
dois comportamentos para a mesma frase, dependendo de a internet estar de pé.

**Ferramentas terminais.** O resultado do dispositivo já é uma frase redigida
para ser falada, e ela vai ao ar como está — sem uma segunda rodada de LLM.
Começou como economia de latência e virou correção: perguntando *"o que eu tenho
marcado"* com um timer e um alarme na fila, o modelo recebeu os dois e respondeu
só o alarme. Resumir uma lista é perder item. Tentar consertar pelo prompt
("repita sem omitir") saiu pior — o modelo passou a narrar que ia chamar a
ferramenta em vez de responder.

| Turno | Com 2ª rodada de LLM | Com ferramenta terminal |
|---|---|---|
| `listar_agendamentos` | 3,7 s, lista incompleta | **2,1 s**, lista completa |
| `criar_alarme` | 4,1 s | **2,3 s** |

**Consequências:**
- `ToolResult` ganhou `value`: nem toda ferramenta é só "deu certo", e `listar`
  precisa devolver conteúdo. Continua sendo texto — o gateway não conhece as
  estruturas do dispositivo e não deve conhecer.
- Argumentos são convertidos com tolerância no dispositivo. Não é zelo
  gratuito: o llama3.1:8b mandou `{"segundos": "5400"}`, string, com o schema
  dizendo `integer`. Recusar isso seria recusar uma chamada correta.
- Ferramenta inventada volta como falha explícita, nunca como traceback — é
  metade do critério de aceite da fase.
- `MAX_TOOL_ROUNDS = 3`: um modelo pequeno que erra os argumentos repete a mesma
  chamada para sempre, e sem teto o turno nunca termina, com o aparelho parado
  em THINKING.

**O critério de aceite está cumprido pela metade, e a metade que falta é do
modelo, não do código.** Ver [D19](#d19--o-llama-318b-nao-faz-as-duas-coisas).

---

## D19 — O llama3.1:8b não faz as duas coisas

**Data:** 2026-09-01
**O plano diz:** a seção 6 já previa isto — *"modelo pequeno **classifica**,
modelo grande **responde**"* — e a [D11](#d11) escolheu um modelo aberto local
deixando em aberto se um 8B dá conta.

**O que foi medido:** com as quatro ferramentas declaradas, o llama3.1:8b passa
a recusar conhecimento geral. Mesma pergunta, mesmo prompt de sistema, a única
diferença sendo a presença das ferramentas na chamada:

| | "qual a capital da Austrália" |
|---|---|
| **Com** ferramentas | "Não sei a resposta para essa pergunta." |
| **Sem** ferramentas | "A capital da Austrália é Canberra." |

Repetido sobre dez frases, cinco de agenda e cinco de conhecimento geral:

| | Resultado |
|---|---|
| Chamou a ferramenta certa | 4 de 5 |
| Inventou chamada inexistente | 0 de 5 |
| Respondeu conhecimento geral | **0 de 5** — as cinco viraram "não sei" |

**Três variantes testadas, todas piores:**

1. **Tirar a instrução "se não souber, diga que não sabe".** O modelo passou a
   **inventar ferramenta**: cuspiu `{"name": "pesquisar", "parameters": {...}}`
   como texto — uma ferramenta que não existe — e chamou `criar_timer` para
   *"quem escreveu Dom Casmurro"*. É literalmente o modo de falha que o critério
   de aceite da Fase 3 nomeia.
2. **Instruir no prompt que ferramentas servem só para timer e alarme.** Sem
   efeito: as recusas continuaram.
3. **Separar em duas chamadas** (uma decide, outra responde), que é a arquitetura
   da seção 6 com um modelo só. Ficou muito pior — com prompt de decisão, o
   modelo chama ferramenta para tudo: *"qual a capital da Austrália"* virou
   `criar_alarme(hora=0, minuto=0)`.

**O que fica:** a variante atual, que é a melhor das quatro medidas — ferramentas
funcionando, nada inventado, conhecimento geral perdido.

**Um portão por palavra-chave foi considerado e não implementado.** Abrir as
ferramentas só quando a frase menciona timer/alarme/acorda/lembra restaura a
maior parte do conhecimento geral, mas erra nos dois sentidos: fecha em
*"desmarca o que eu agendei"* (perde a intenção) e **abre** em *"me conta uma
piada"*, por causa do "conta" — e ferramenta aberta numa frase dessas é um timer
falso sendo criado. Trocar uma regressão total por uma silenciosa não é troca boa
o bastante para ser feita sem decidir.

**A decisão que isto força:** a D11 deixou em aberto *"se um modelo aberto de 8B
dá conta de busca fundamentada"*. A resposta chegou antes da busca existir, e por
um caminho que ninguém esperava: **ele não dá conta de ter ferramentas e
conhecimento ao mesmo tempo.** As saídas são um modelo maior, um modelo melhor em
ferramentas, ou o modelo de nuvem que a seção 6 sempre apontou — todas atrás da
mesma interface `LLMProvider`, que é o ponto de troca e continua intacto.

---

## D20 — O modelo passa a ser o qwen3:8b, com o raciocínio desligado

**Data:** 2026-09-01
**O plano diz:** a seção 6 escolhe modelo aberto local e prevê trocar por um de
nuvem atrás da mesma interface. A [D11](#d11) escolheu o llama3.1:8b via Ollama.

**O que mudou:** `LLM_MODEL` passa a ser `qwen3:8b`, e o provedor manda
`think: false` na chamada.

**Por quê:** a [D19](#d19--o-llama-318b-nao-faz-as-duas-coisas) mediu que o
llama3.1:8b não tem ferramentas e conhecimento ao mesmo tempo. Repetindo a mesma
bancada de doze frases nos candidatos:

| | llama3.1:8b | qwen3:4b | qwen3:8b |
|---|---|---|---|
| Ferramenta certa | 4/5 | 5/5 | **5/5** |
| Conhecimento geral | 0/7 | 3/7 | **6/7** |
| Mediana por turno | **1,7 s** | 5,5 s | 2,8 s |

O llama chegou a chamar `listar_agendamentos` para *"cancela o alarme que eu
marquei"*. O qwen3:8b acertou as cinco.

**Por que o raciocínio fica desligado.** A pergunta óbvia é se ele não resolveria
a alucinação. Medido no 8b, dezesseis perguntas factuais, metade fáceis e metade
obscuras, duas repetições cada:

| | `think=false` | `think=true` |
|---|---|---|
| Acertos | 11/16 | 12/16 |
| **Erros com confiança** | **1** | **0** |
| "Não sei" | 4 | 5 |
| Mediana | **1,6 s** | **17,1 s** |

Ele **ajuda**, e de um jeito específico: não passou a saber mais, passou a
admitir que não sabe. *"Grande Sertão: Veredas foi escrito por José de Alencar"*
virou *"não sei quem escreveu"*. Recuperou um fato real (o segundo presidente do
Brasil, que sem raciocínio era "não sei" nas duas tentativas).

**Mas custa dez vezes mais tempo, e a seção 11 orça 1,5 s para o nível 2.**
Dezessete segundos de espera para ouvir "não sei" é pior que a alucinação, porque
acontece em *toda* pergunta e não em uma a cada seis.

O argumento decisivo não é a latência, é a causa: o modelo não errou por falta de
raciocínio, errou por não ter o fato. Pensar mais sobre um fato ausente produz
uma justificativa melhor para a mesma resposta errada. O que ataca a causa é
fundamentar — buscar, ler, responder com fonte —, e é por isso que a busca web
importa mais do que parecia quando a ordem das ferramentas foi escolhida.

Fica em `LLM_THINK` para não ser uma escolha trancada no código.

**Vazamento é problema só do 4b.** O 8b respeita `think: false` e não devolveu
rascunho em nenhum dos dois modos. O qwen3:4b devolveu o rascunho como conteúdo:

```
marcos> Okay, the user is asking for the capital of Australia...
```

Num assistente de voz isso não é um log feio: é o aparelho **falando** isso em
voz alta, com a minha voz. O 4b foi descartado por esse motivo, não pela nota.

**Consequências:**
- `OllamaProvider` ganhou o parâmetro `think`, e `LLM_THINK` no `.env`. Fica
  configurável porque um modelo sem raciocínio ignora o campo, e porque a
  medição acima mostra que ligar é uma troca real (menos mentira, muito mais
  espera) e não um erro.
- Turnos de conhecimento geral ficaram em ~1,2 s ponta a ponta, dentro do
  orçamento de 1,5 s da seção 11. Os de ferramenta ficam em ~2,4 s.
- A pergunta em aberto da D11 — *"se um modelo aberto de 8B dá conta"* — vira:
  **dá, para ferramentas e conversa curta.** Para busca fundamentada continua em
  aberto, e agora por um motivo concreto: ele alucina. Perguntado quem escreveu
  Dom Casmurro, respondeu *"Mario Quintana"* uma vez em seis. Achei que fosse
  efeito do histórico da conversa e fui medir: não se reproduziu, 5/5 corretas
  depois. É alucinação avulsa de modelo pequeno, e é o argumento mais forte a
  favor da busca web ser a próxima ferramenta.

**Nota de operação:** o modelo tem 5,2 GB e a placa aqui tem 6 GB. Cabe, mas sem
folga. Quem rodar isto com o fine-tune do Piper ao mesmo tempo vai repetir o
`CUDA out of memory` que já está registrado no `comandos.md`.

---

## D21 — Spotify é a primeira ferramenta que o gateway executa

**Data:** 2026-09-01
**O plano diz:** a seção 3 põe `Ferramentas · Segredos · Histórico` no gateway, e
a Fase 3 entrega "busca web, Spotify, Home Assistant".

**O que mudou:** `gateway/tools/spotify.py` controla playback pela Web API do
Spotify. É a **primeira ferramenta executada no gateway** — as quatro de agenda
([D18](#d18--ferramentas-do-dispositivo-o-llm-pede-o-pi-executa-e-o-resultado-é-a-resposta))
são declaradas lá e executadas no dispositivo.

**Por quê a assimetria:** aqui há segredo. O `client_secret` e o refresh token
ficam no servidor e não descem pelo fio. O dispositivo só ouve *"Tocando
Construção, de Chico Buarque."* — que é, aliás, a mesma regra do
[D7](#d7--pela-rede-sobe-só-texto-o-áudio-nasce-no-dispositivo) vista do outro
lado: pela rede desce texto, não credencial.

**Home Assistant fica de fora da Fase 3.** Uma lâmpada Elgin, hoje controlada
pela Alexa, é todo o parque instalado. Não paga o Tailscale, a instância do HA e
a Fase 5 que o plano exige para chegar nele. Se a casa crescer, volta.

**Degradação é comportamento, não detalhe.** Sem credenciais no `.env` **ou** sem
o refresh token em disco, as ferramentas de música **não são declaradas** ao
modelo. Isso decorre direto do [D19](#d19--o-llama-318b-nao-faz-as-duas-coisas):
um modelo pequeno que vê uma ferramenta indisponível tenta usar mesmo assim.
Verificado com o Spotify desligado:

```
voce> toca chico buarque
marcos> Nao sei tocar Chico Buarque.
        Posso ajudar com timers, alarmes ou listar/agendar coisas?
```

Nenhuma chamada inventada, e o `/health` responde `"spotify": "off"`.

**Detalhes que a documentação atual obrigou a mudar** — o plano avisava na seção
14 que houve remoção de endpoints em fev/2026, então tudo foi conferido contra a
referência viva em vez de escrito de memória:

- Os endpoints de player (`/me/player/play`, `/pause`, `/next`, `/previous`,
  `/devices`, `/currently-playing`) continuam de pé e **não** estão depreciados.
- O `limit` do `/search` hoje é **0–10**. Era 50.
- O `redirect_uri` precisa ser `127.0.0.1`; o Spotify recusa `localhost` desde
  2025. Um `localhost` no dashboard é meia hora de erro `INVALID_CLIENT`.

**Quatro modos de falha tratados, porque são os que acontecem:**

- **403** — todo controle de playback exige Premium. A API não diz "compre
  Premium", diz 403. Vira *"o controle de música precisa de Spotify Premium"*.
- **404 / nenhum aparelho** — mandar tocar com o Spotify fechado em todo lugar
  não faz nada. O cliente lê `/me/player/devices` antes, prefere o que está
  ativo, e se não houver nenhum diz *"abra o Spotify em algum aparelho
  primeiro"*.
- **204 sem corpo** — "nada tocando" responde 204, e `r.json()` num corpo vazio
  derruba cliente ingênuo.
- **Refresh token rotacionado** — o Spotify às vezes devolve um token novo na
  renovação. Ignorar isso mata a conexão semanas depois, longe da causa.

**Uma escolha de segurança que parece detalhe:** o despacho nome → método é um
dicionário explícito, não `getattr(client, nome)`. Com `getattr`, um nome
inventado pelo modelo viraria chamada de método arbitrário do cliente. Há teste
para isso.

**Escopos pedidos:** só `user-read-playback-state` e
`user-modify-playback-state`. Sem playlists, biblioteca, e-mail ou histórico.

**Não verificado ponta a ponta:** não há conta do Spotify aqui. Os vinte testes
rodam contra um `httpx.MockTransport`, o que cobre a lógica — token que vence,
403, 204, escolha de aparelho — e **não** cobre o formato real das respostas nem
o fluxo de consentimento no navegador. A primeira execução com conta de verdade
ainda pode revelar diferença de campo, e deve ser tratada como estreia.
