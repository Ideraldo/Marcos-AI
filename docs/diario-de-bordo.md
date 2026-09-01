# Diário de bordo

Registro narrativo do desenvolvimento do Marcos-AI: as dúvidas, as decisões, o
que foi tentado e o que deu errado. Material para o vídeo de documentação do
projeto.

Diferente do [`decisions.md`](decisions.md), que é seco e registra só o *quê* e o
*porquê* de cada decisão fechada. Aqui fica o caminho até ela — inclusive os
becos sem saída, que costumam ser a parte mais interessante de contar.

---

## Dia 1 — O plano, e a primeira dúvida grande

O projeto nasceu de uma frustração concreta: substituir a Alexa do quarto, mas
sem abrir mão de poder levar o aparelho junto. Portabilidade como requisito, não
como enfeite.

A primeira dúvida foi a que mais mudou tudo depois: **onde roda o LLM?**

### Tentativa 1: modelo local no próprio dispositivo

A ideia inicial era rodar tudo no Raspberry Pi, com um acelerador. O AI HAT+ 2
(Hailo-10H, 40 TOPS, ~US$130) existe e funciona. Mas os modelos que ele suporta
são da faixa de 1 a 1,5 bilhão de parâmetros — Llama 3.2 1B, Qwen 2.5 1.5B — a
20–50 tokens/s.

Rápido, e limitado demais. Para uma busca fundamentada na internet, com síntese
de vários resultados, esse tamanho de modelo não entrega. **Descartado.**

### Tentativa 2: modelo local numa VPS sem GPU

Se não cabe na Pi, poderia caber num servidor barato. Duas barreiras derrubaram
a ideia:

A geração já é lenta — como referência, Llama 3.1 8B quantizado em Q4 num EPYC
bare-metal de 32 núcleos entrega ~14 tokens/s, e uma VPS comum tem 8 vCPU
compartilhadas.

Mas o pior nem é a geração. É o **prompt processing**: digerir 6 a 8 mil tokens
de resultados de busca na CPU leva dezenas de segundos *antes da primeira
palavra sair*. Para voz, inviável. **Descartado.**

### Tentativa 3: GPU na nuvem, ligada o tempo todo

A partir de ~US$200/mês. Contra poucos dólares mensais de API para uso pessoal.
Não fecha a conta. **Descartado** — a reavaliar só se privacidade virar requisito
duro, e aí o STT também teria que ser local.

### O que ficou

**LLM via API, orquestrado por um gateway numa VPS em São Paulo.** Poucos dólares
por mês, cancelável, e entrega a qualidade necessária para busca e visão.

E aí veio a segunda decisão, que economizou dinheiro de verdade:

> **Construir tudo localmente antes de comprar qualquer coisa.**

O gateway roda em Docker no localhost; o "dispositivo" é um processo separado
usando o microfone e o alto-falante do PC. Se o software não funciona no PC, não
vai funcionar na Pi — e aí o dinheiro do hardware teria sido gasto à toa.

**VPS antes do hardware**, quando chegar a hora. Custa poucos dólares, é
cancelável, e entrega o número de latência real Brasil → gateway → LLM. Hardware
é dinheiro que não volta.

---

## Dia 2 — O primeiro código, e uma contradição no plano

### O esqueleto e a Fase 0

Duas regras foram tratadas como inegociáveis desde o primeiro commit:

1. **Dois processos separados**, conversando só por WebSocket. Migrar para a VPS
   tem que ser trocar uma URL, nada mais. Chamada de função direta entre as duas
   partes: proibida.
2. **Alarme e timer executam sempre no dispositivo.** O gateway nunca pode ser
   responsável por me acordar.

O loop completo fechou em modo texto: o que se digita viaja pelo mesmo canal
binário que vai levar PCM depois. Tudo depois do microfone é o caminho real —
protocolo, máquina de estados, autenticação, latência simulada.

Rodou com Ollama local (llama3.1:8b) respondendo. Dois turnos, com memória entre
eles funcionando.

**Primeiro número desconfortável:** 52 segundos para o primeiro token com o
modelo frio, 1,2 s quente. O orçamento é 300–800 ms.

### Uma pergunta minha que virou uma correção de arquitetura

Perguntei uma coisa que parecia boba: *"como o gateway ia processar o áudio e me
responder em áudio? Ia ficar transitando arquivos mp3 entre a Pi e a VPS?"*

A resposta era não — é streaming de PCM cru, sem arquivo nenhum, uns 0,25 MB por
interação. Mas a pergunta abriu outra: se STT e TTS estão no gateway, **o que
acontece com a internet caída?**

E aí apareceu a contradição. O plano diz duas coisas que não podem ser verdade ao
mesmo tempo:

- Seção 5: o nível 0 (timer, alarme, hora, volume) **não usa rede**.
- Seção 1: o roteador de intenções fica no dispositivo, mas o **STT fica no
  gateway**.

Só que o roteador casa regex e embeddings sobre **texto**. Sem transcrição local,
um comando de timer com a internet fora nunca chega a ser classificado. **Nível 0
offline só existe com STT local.**

Isso virou a decisão D1: STT e TTS migram para o dispositivo. Pela rede sobe só
texto — alguns KB em vez de 250. Mais barato, mais rápido, e o despertador toca
com a internet fora.

---

## Dia 2 (continuação) — A bancada: da nuvem para o local

### Começamos pela nuvem, e foi bom começar errado

Os dois primeiros motores testados foram de nuvem: **edge-tts** (Microsoft, sem
chave de API) e **faster-whisper** (esse local).

O edge-tts era enganador — não pede chave nenhuma, então *parece* local. Mas cada
frase vai por WebSocket até a Microsoft. E o número entregou o problema: RTF 0,62
no conjunto, com **uma frase dando pico de 11,6 segundos** contra 1,3 s das
outras. Não foi a síntese, foi a rede.

Um aparelho que depende da nuvem para falar não consegue nem dizer "timer de dez
minutos" com a internet fora.

**Decisão: só offline.** O edge-tts continuou na bancada, mas rebaixado a teto de
qualidade para comparação — não é mais candidato.

### O erro de medição que quase enviesou tudo

A primeira tabela de STT acusou **13,5% de WER**. Olhando os erros um por um,
quase todos eram do tipo:

```
esperado: Timer de dez minutos.
ouviu:    Timer de 10 minutos.
```

Isso não é erro de reconhecimento. É hábito de formatação. E estava fazendo a
métrica ranquear os modelos pelo jeito que escrevem número, não pelo que
entendem.

Escrevi um soletrador de números pt-BR e passei a normalizar antes de pontuar. O
WER caiu de 13,5% para **4,1%** — sem mudar uma linha do modelo. Só medindo
direito.

*Lição para o vídeo: métrica errada é pior que métrica nenhuma, porque dá
confiança.*

### O TTS que pulava todos os números

Testando o MMS-TTS da Meta (especializado em português), a frase dos números saiu
com 3,55 s de áudio onde o Piper gastava 7,21 s. Suspeito.

Transcrevi o áudio do MMS de volta com o Whisper:

```
esperado: O CEP é 04538-133 e o valor deu R$ 1.249,90.
ouviu:    O sepé, ele e o valor deus, e...
```

Os dígitos **sumiam em silêncio**, sem erro nenhum. O tokenizer uroman não tem
normalizador numérico. Um TTS que não lê número é inútil para "são sete e
quinze".

Consertado reaproveitando o mesmo soletrador que a métrica já usava — o áudio da
frase foi de 3,55 s para 9,41 s.

### A tabela que não servia para escolher

Depois de medir cinco modelos de STT sobre áudio sintético, um detalhe estragou
tudo: o **mesmo** faster-whisper small deu **4,1% de WER no áudio do edge-tts** e
**17,6% no do Piper**.

O modelo não mudou. O material mudou. A voz do Piper articula pior, e o Whisper
comia sílabas: "Timer" virava "Tame", "quarto" virava "4".

Ou seja: a tabela media tanto a dicção do TTS quanto o ouvido do modelo. Servia
para ranquear, não para escolher. **O número honesto só sai da voz real.**

---

## Dia 2 (continuação) — O microfone que não ouvia

Rodei o teste de gravação e não veio nada. Nenhum áudio.

O Fifine estava conectado e funcionando — mas o dispositivo *padrão* do Windows
era o microfone de um headset HyperX. O script gravava do headset, mudo.

Isso virou três correções:

1. **Seletor de dispositivo** com teste de 3 segundos que diz na hora se está
   mudo, saturado ou ok. A lista mostra um item por hardware, não os 28 que o
   `sounddevice` devolve — o mesmo Fifine aparece sob quatro APIs de áudio, e é
   isso que faz escolher errado.
2. **Gravação que para sozinha**, com VAD. Tempo fixo erra nos dois sentidos:
   corta frase longa e enche frase curta de ruído — e é o ruído que faz o modelo
   alucinar palavras que ninguém disse.
3. Um tropeço no caminho: o `webrtcvad` importa `pkg_resources`, que o
   `setuptools` 81 removeu. Fixado em `<81`.

**E o VAD sozinho não bastou.** No primeiro teste ele disparou no ruído da sala e
gravou 30 segundos de nada — um condensador como o Fifine tem piso de ruído
suficiente para o VAD chamar de voz. A solução foi medir o ruído de fundo nos
primeiros 300 ms e só aceitar um quadro como fala se o VAD concordar **e** o som
estiver acima desse piso.

---

## Dia 2 (continuação) — Os números que decidiram o STT

Com a voz real, microfone Fifine, sete frases:

| Motor | WER | CER | RTF |
|---|---|---|---|
| **faster-whisper small** | **9,0%** | 6,4% | 0,43 |
| faster-whisper base | 24,7% | 7,6% | 0,14 |
| wav2vec2 XLSR pt-BR | 29,4% | 16,0% | 0,18 |
| Vosk pt | 37,2% | 33,0% | 0,37 |
| faster-whisper tiny | 45,6% | 24,7% | 0,12 |

Mas o número agregado escondia o que importa: **todo o erro do small estava nas
duas frases que menos parecem um comando** (um CEP e uma previsão do tempo).

Nas cinco frases parecidas com uso real, o small deu **2,2% de WER**. O base, nas
mesmas cinco, deu 18,9% — errando "Timer" e "Toca", exatamente as palavras que o
roteador precisa casar.

Surpresas:

- **O Vosk decepcionou.** Perde nos dois eixos para o base, e erra perigoso:
  "acender a luz do **quarto**" virou "luz do **quadro**". Modelo pt de 2020.
- **O tiny piorou com voz humana** (31,7% no sintético → 45,6% no real), o
  oposto do que se quer.
- **O wav2vec2 confirmou o que se esperava dele:** erra fonema, nunca frase.
  "taimer", "poeha açúcar" — sempre reconhecível, nunca inventado, porque não tem
  decoder de linguagem adivinhando a próxima palavra.

### A tensão que ficou aberta

O small acerta, mas RTF 0,43 no PC vira algo entre 1,3 e 2,2 na Pi 5 — acima do
tempo real. O base cabe com folga mas erra os comandos.

Três saídas registradas, nenhuma decidida sem medir na Pi:
whisper.cpp/sherpa-onnx (mais rápidos em ARM), ou base na Pi para o roteador +
small no gateway para o LLM, ou aceitar a latência.

---

## Dia 2 (continuação) — A voz, e uma rejeição

Ouvi os dois primeiros TTS e reprovei os dois: **o Piper faber soava arrastado, o
MMS soava robótico**.

Isso mudou o rumo. Entrou o **Kokoro** (StyleTTS2, 82M, três vozes pt-BR), e
foram geradas as outras vozes do Piper que eu não tinha ouvido.

E aí veio um achado por acaso. Procurando checkpoints de treino, descobri que **o
repositório oficial de checkpoints do Piper saiu do ar** (erro 401). Os que
sobreviveram estão no OpenVoiceOS — e são de vozes **"high"**, uma qualidade que
**nem aparece na lista oficial de download**: `pt_BR-miro-high` e `pt_BR-dii-high`.

Das sete vozes ouvidas, aprovei **jeff-medium** e **cadu-medium**.

Mas a pergunta que eu queria mesmo fazer era outra.

---

## Dia 2 (final) — Clonar a minha voz, e reconhecer quem fala

Perguntei duas coisas que pareciam a mesma: dá para o STT saber que sou eu
falando? E dá para o TTS falar com a minha voz?

**São problemas completamente diferentes.**

### Quem fala não é trabalho do STT

O Whisper transforma áudio em palavras e joga fora a identidade junto. Quem sabe
disso é outro modelo, em paralelo: o ECAPA-TDNN mapeia alguns segundos de fala
num vetor de 192 números, e vozes da mesma pessoa ficam próximas.

Isso significa que **não existe treino** — cadastrar alguém é gravar quatro
frases. Minha mãe entra depois sem tocar no que já existe.

Medido com as minhas gravações:

| Comparação | Similaridade |
|---|---|
| Minha voz × minha própria média | **0,69 – 1,00** |
| Minha voz × Piper faber | 0,21 |
| Minha voz × edge Francisca | 0,24 |
| Minha voz × MMS | 0,02 |

Separação enorme. O limiar ficou em 0,45, no meio do vazio entre os dois grupos.

### Voz própria: dois caminhos, um só serve

**Clonagem zero-shot** (XTTS-v2, F5-TTS): 6 a 30 segundos e pronto, sem treino.
Impressionante — e inútil aqui, porque são modelos de 1,5 a 2 GB que precisam de
GPU. Na Pi não roda.

*Mas tem um uso legítimo:* as frases fixas ("Timer de dez minutos", "Alarme
criado") podem ser sintetizadas **uma vez no PC** com voz clonada e copiadas
como arquivo. Custo zero em execução.

**Fine-tune do Piper** é a resposta de verdade: 15 a 30 minutos da minha voz,
algumas horas de GPU, e sai um modelo de 60 MB com o meu timbre rodando a **RTF
0,05** na Pi. Único caminho que entrega timbre próprio **e** velocidade.

Escolhi esse.

---

## Dia 2 (final) — Gravar 15 minutos, e o erro do corpus

Gravei as 95 frases do corpus. O resultado:

```
95 de 95 frases gravadas
4.9 minutos de audio
ainda pouco: mire em pelo menos 15 min
```

**Muitos arquivos, poucos minutos.** As frases eram curtas demais. O que falta
num fine-tune não é quantidade de arquivos, é *minutos*.

A análise mostrou que a leitura estava boa — 13 caracteres/segundo, ritmo
natural, nenhum corte de final de frase, pico médio 65%. O erro era do corpus,
não da leitura.

Entrou um bloco 2 com 108 frases **longas** (~89 caracteres contra ~40), que
rendem o dobro de áudio com a mesma paciência e ainda carregam prosódia que frase
curta não tem: vírgula, subordinada, respiração no meio.

Um detalhe que virou comentário no código: o bloco novo entra **no fim**, porque
o índice da frase é o nome do arquivo `.wav`. Reordenar casaria gravação velha
com texto novo, e o modelo aprenderia a dizer outra coisa — um erro que só
apareceria ouvindo a voz falar bobagem sem explicação.

Também criei um conferidor de dataset, que achou quatro gravações truncadas — 1
segundo para frases de 40 caracteres. O modelo aprenderia a parar no meio da
frase.

**Resultado final: 203 gravações, 15,2 minutos, zero problemas.**

---

## Dia 2 (final) — Quatro bugs entre mim e o treino

Antes de deixar a GPU rodando a noite toda, testei o treino com **uma única
época**. Foi a melhor decisão do dia: quatro coisas quebravam, todas silenciosas
até o momento errado.

**1. PosixPath.** Os checkpoints foram salvos no Linux e guardam objetos
`pathlib` dentro. O Windows não consegue nem abrir o arquivo.

**2. weights_only.** O torch 2.6 passou a recusar checkpoints com objetos por
padrão — e é exatamente assim que o Lightning carrega.

**3. O contador de época.** Essa é a que teria custado uma tarde inteira. O
`--ckpt_path` do Lightning significa *retomar*, então ele restaura a época junto.
O checkpoint do dii parou na **época 3908**. Pedir 2000 épocas faria o treino
**encerrar na hora sem fazer absolutamente nada** — e eu só descobriria olhando
um `.onnx` idêntico ao original, horas depois.

**4. monotonic_align.** A wheel do `piper-tts[train]` para Windows vem **sem a
extensão Cython** do Monotonic Alignment Search. E nem o `.pyx` está lá, então
não dá nem para compilar. O treino morria no primeiro batch.

Reimplementei o algoritmo com numba. É a busca em programação dinâmica no coração
do VITS: dado o custo de alinhar cada posição do texto com cada quadro de áudio,
achar o único caminho monotônico de custo mínimo — que é como o modelo aprende,
**sem nenhum alinhamento rotulado**, quanto tempo dura cada fonema.

Ainda apareceram dois menores: hiperparâmetros obsoletos no checkpoint (o modelo
atual não aceita mais `sample_bytes`), e o exportador que escreve só o `.onnx`
sem o `.onnx.json` — sem o config ao lado, o modelo exportado nem carrega.

Com tudo resolvido, o ciclo rodou ponta a ponta: checkpoint preparado → treino na
GPU → export → síntese a RTF 0,06.

**22 batches por época, ~15 s cada.** 1000 épocas ≈ 4h, 2000 ≈ 8h.

---

## Dia 3 — O treino rodou, e o modelo decorou

Deixei o fine-tune rodando e fui acompanhando. Este foi o dia em que uma intuição
minha se confirmou com número — e em que a ferramenta que eu mandei construir
para medir isso estava, ela mesma, errada na primeira versão.

### Ouvindo o treino crescer

Por volta da época 100 exportei um checkpoint intermediário para ouvir. Descobri
no caminho que **não precisava fazer nada para gerá-lo**: o Lightning já salva
sozinho a cada época, então era só exportar num segundo terminal, sem parar o
treino.

Primeira impressão, época 113: **timbre reconhecível, mas bem robótico**. Achei
normal para o começo.

Os números do treino apoiavam:

| | Época 113 | Época 322 |
|---|---|---|
| `val_mel` (menor = melhor) | 0,4646 | 0,4324 |
| `val_mos` (maior = melhor) | 2,89 | 3,12 |

Estava aprendendo. Não tinha estagnado.

### A dúvida que virou o assunto do dia

Ouvindo a época 318, falei uma coisa que estava me incomodando desde o começo:

> *"Só vamos precisar tomar cuidado para que ele não fique totalmente
> especializado em dizer as mesmas palavras ou frases, mas que consiga ler
> qualquer texto do mesmo jeito."*

Era exatamente o risco de um fine-tune com 15 minutos e 203 frases: em vez de
aprender o meu **timbre**, o modelo decorar as minhas **frases**. Soaria ótimo
dizendo "Timer de dez minutos" e desmoronaria em texto novo — que é o que o
assistente vai falar o dia inteiro, já que a resposta do LLM nunca é uma frase
pré-escrita.

Isso virou uma ferramenta: sintetizar 15 frases **que nunca foram gravadas** —
nomes próprios, siglas, estrangeirismos, trava-línguas, uma frase de três linhas
— e **transcrever o resultado de volta** com o Whisper. Se a voz articula, o STT
entende. Se desmonta, o WER sobe e mostra onde.

### A ferramenta errada, e o erro que ela quase causou

A primeira versão olhou só o holdout, viu WER 45,1% contra 22,3% da base e
concluiu:

```
ATENCAO: bem pior que a base em texto novo -- sinal de overfitting.
Volte para um checkpoint anterior e pare o treino mais cedo.
```

**Estava errada.** E o erro era grave, porque mandava fazer o oposto do certo.

WER alto em texto novo não distingue duas doenças opostas:

| | Corpus | Holdout | O que fazer |
|---|---|---|---|
| **Decorou** | baixo | alto | Voltar checkpoint; passou do ponto |
| **Ainda cru** | alto | alto | **Treinar mais** |

A diferença está na *distância* entre as colunas, não no valor de nenhuma delas.
Na época 113 o modelo ia mal nos dois igualmente — tinha saído da articulação
limpa da base e ainda não chegado na minha. Era exatamente o que eu tinha ouvido:
robótico. Seguir aquele aviso teria abortado um treino saudável.

Refeita, medindo as duas colunas, o diagnóstico na época 113 virou **"ainda
cru — continue treinando"**.

*Lição para o vídeo: uma ferramenta de diagnóstico que só mede metade do
problema dá o conselho oposto ao correto, com toda a confiança do mundo.*

### Ouvi a 318 e não tinha mudado quase nada

Foi aí que a coisa ficou clara. Exportei a época 318, ouvi, e **os defeitos eram
os mesmos da 113**. Perguntei se mais épocas resolveriam.

Com a ferramenta consertada, o número respondeu:

| | Época 113 | Época 318 |
|---|---|---|
| Corpus (frases treinadas) | 26,3% | **11,3%** |
| Holdout (texto novo) | 39,2% | **39,7%** |
| Distância | +12,8% | **+28,4%** |

O corpus melhorou muito. O texto novo **não saiu do lugar**. A distância dobrou.

Essa é a assinatura de decorar: o modelo ficando cada vez melhor em dizer
exatamente as minhas 203 frases, e nem um pouco melhor em ler qualquer outra
coisa. A base `dii-high` faz 22,9% no mesmo holdout; a minha voz travou em 39,7%.

Uma ressalva honesta que registrei junto: o VITS tem amostragem estocástica, e a
mesma época 113 mediu 39,2% numa rodada e 34,4% noutra. Há uns ±5 pontos de
ruído. Mas a queda do corpus de 26,3% para 11,3% está muito além disso, e o
holdout está plano dentro do ruído.

### Não era falta de tempo, era falta de material

O que fecha o diagnóstico: **14.828 passos** já rodados. A base tinha 1,9 milhão.
Não é treino imaturo — é que 203 frases são poucas para o modelo ter o que
generalizar. Ele esgotou o que dava para extrair delas e passou a memorizá-las.

Foi por isso que os defeitos não mudaram entre a 113 e a 318. Não eram
imaturidade: eram o teto dos dados.

**Decisão: parar o treino e gravar mais.**

### Frases longas ou parágrafos?

Perguntei se podia gravar parágrafos inteiros, para render mais minuto por
gravação, ou se áudio grande atrapalha o treino.

A resposta veio do código do Piper, não de opinião. **Não há filtro de
comprimento** — parágrafos não seriam descartados. Mas há dois tetos:

- **O padding.** O `collate` preenche todas as amostras do batch até a mais
  longa. Um trecho de 30 s força os outros sete do batch a 30 s — VRAM
  desperdiçada numa placa de 6 GB.
- **Na inferência o Piper divide por sentença de qualquer jeito.** Treinar em
  parágrafos ensina uma prosódia que ele nunca vai usar.

Ficou em **10 a 15 segundos**: dois ou três períodos encadeados. Rende mais
minuto por ENTER apertado, cabe no batch, e mantém muitas amostras distintas.

O bloco 3 tem 112 trechos, ~15 min, levando o corpus a **315 frases e ~30
minutos**. O que variei foi o *ritmo*, não só as palavras — diálogo, enumeração,
instrução técnica, narrativa, opinião — porque o que faltava era diversidade de
construção, não mais do mesmo.

### O que ainda pode dar errado

30 minutos é o dobro, mas não é garantia. A referência prática para
generalização confortável é 40 a 60 minutos. Se o holdout continuar empacado
depois do retreino, vem um bloco 4.

A diferença é que agora dá para saber sem adivinhar. E foi a medição que pegou o
problema **antes** de gastar as oito horas completas de GPU.

### Também hoje

- **Export por época.** `--list` mostra os checkpoints disponíveis, `--epoch N`
  exporta uma específica com a época no nome, para poder ouvir duas lado a lado
  nas mesmas frases.
- **A skill `/documentar`**, para fechar o dia sem depender de eu lembrar de
  tudo.
- Confirmado que **dá para retomar o treino se o PC desligar** — o `last.ckpt` é
  reescrito a cada época e o `--resume` volta com otimizador e época intactos. É
  o mesmo mecanismo que tive que desativar no primeiro arranque, quando ele
  restaurava a época 3908 do checkpoint alheio.

---

## Dia 3 (continuação) — Arrumar a casa antes do segundo treino

Entre condenar o v1 e iniciar o v2, um bloco de trabalho que não era sobre
modelo nenhum: guardar o que valia do treino velho, consertar o que estava
quebrado na gravação, e revisar como o treino é feito.

### O que sobrou do v1 (menos do que eu queria)

Pedi para guardar as gerações 0, 50, 100, 150, 200, 250 e a última, para poder
mostrar a evolução no vídeo. **Metade não existia mais.**

O `ModelCheckpoint` do Lightning guarda apenas os cinco melhores por métrica e
vai apagando os antigos conforme treina. Quando fui arquivar, a época mais antiga
que restava era a **247**. A 113 só sobreviveu por acaso: eu tinha exportado o
`.onnx` naquele dia para ouvir.

Ficaram seis gerações — 113, 247, 292, 318, 330 e 361 — em `.onnx`, somando 363
MB contra os 8,7 GB dos checkpoints. Depois disso, apagar os 9,2 GB do run velho
foi indolor.

*Lição, e virou recomendação no `comandos.md`: exportar `.onnx` ao longo do
treino, não só no fim. São 60 MB contra 845 MB, e é o único formato que se ouve.*

### O gravador cortava no meio da frase

Comecei a gravar o bloco 3 e a gravação **encerrava sozinha antes da hora**, em
pausas naturais — depois de um ponto final ou de uma vírgula longa.

Erro meu: eu tinha posto **700 ms** de silêncio como limite para encerrar, valor
escolhido quando o corpus só tinha frases curtas. Os trechos do bloco 3 têm dois
ou três períodos, e a pausa depois de um ponto no meio passa fácil de um segundo.

As duas primeiras gravações saíram com 3,8 s e 3,1 s onde precisavam de uns 8 s.
Se tivesse passado despercebido, o modelo aprenderia a parar no meio da frase.

Padrão subiu para **1600 ms**, com `--silence` para ajustar. O `check` pegou as
duas na hora — 32,8 e 42,5 caracteres por segundo contra o limite de 20 — então o
estrago foi regravar duas frases.

Ao longo da sessão o mesmo detector pegou mais seis: cinco truncadas e uma
arrastada, com 15,5 s para uma frase de 108 caracteres. **Resultado final: 315
gravações, 30,9 minutos, zero problemas.**

### Revisando como o treino é feito

Antes de começar o v2, perguntei se havia estratégias contra overfitting além de
gravar mais. Descobri que estávamos **nos padrões do Piper o tempo todo** — e que
esses padrões são para *treinar do zero* com dezenas de milhares de amostras.

**O learning rate era o problema silencioso.** O padrão é `2e-4`. Num fine-tune
de meia hora isso é agressivo: o modelo se afasta rápido demais dos pesos da
base, que já sabem falar português, e passa a ajustar as poucas frases que tem.
Isso é literalmente a definição de decorar. Caiu para `1e-4`.

Tem um agravante que só apareceu olhando os números junto: o `lr_decay` do Piper
é `0.999875` **por época**, calibrado para épocas grandes. As nossas têm ~40
passos em vez de centenas — então a taxa cai muito mais devagar por passo do que
o autor imaginou. Na prática treinávamos quase a taxa constante.

**E épocas não eram a unidade certa.** Uma época aqui é minúscula. O v1 rodou 368
épocas, que são só **14.828 passos**; fine-tunes de VITS costumam pedir 10 a 30
mil. O padrão caiu de 2000 para 1000 épocas.

### Uma tentativa que não deu

Quis usar `accumulate_grad_batches` para aumentar o batch efetivo sem gastar
VRAM — mais amostras por atualização é uma das formas mais baratas de segurar a
memorização.

**Não funciona aqui.** O VITS treina com otimização manual (dois otimizadores,
gerador e discriminador) e o Lightning recusa acumulação nesse modo:

```
__verify_manual_optimization_support
```

Descobri num smoke test de uma época, não em produção. Removido e documentado —
inclusive porque é o tipo de coisa que eu tentaria de novo daqui a três meses.

### A pergunta sobre treino e validação

Perguntei uma coisa que me incomodava: *não deveríamos separar parte dos áudios
para validação?*

A resposta é que **já existe, em três níveis** — e é a distinção entre eles que
explica por que a validação do Piper sozinha não teria pego o problema do v1:

| Conjunto | O que é | O que pergunta |
|---|---|---|
| `validation_split = 0.1` | ~31 gravações minhas que não entram no treino | "você reproduz bem um áudio meu que não treinou?" |
| Holdout (`generalize`) | 15 frases que **ninguém nunca gravou** | "você sabe ler um texto que nunca viu?" |
| Amostra do corpus | 6 frases treinadas | serve de referência para medir a distância |

A validação do Piper mede reprodução de áudio. O holdout mede leitura de texto
novo — que é o que o assistente faz o dia inteiro, já que a resposta do LLM nunca
é uma frase pré-escrita. Foi a comparação entre os dois que condenou o v1.

### Para não perder a evolução de novo

Escrevi um vigia que roda ao lado do treino e exporta um `.onnx` a cada 100
épocas. Processo separado, exporta na CPU, só lê arquivos — não toca no treino. Se
o Lightning estiver escrevendo o checkpoint naquele instante, ele avisa e tenta no
ciclo seguinte em vez de morrer.

Testei contra um run descartável de uma época antes de confiar nele para a noite
inteira. Vale registrar que testar isso gerou um mal-entendido de dez segundos:
achei que ele fosse rodar o meu treino de verdade.

### v2 iniciado

- 30,9 min de áudio (contra 15,2 do v1)
- learning rate 1e-4 (contra 2e-4)
- 1000 épocas planejadas
- exportando sozinho a cada 100 épocas

Fica rodando a noite. De manhã, ouvir a série e rodar o `generalize`: o que se
quer ver são **as duas colunas caindo juntas**.

---

## Dia 4 — O treino que parecia lento e estava morto

Acordei com o treino "na época 539" e a sensação de que tinha estagnado. Tinha
travado — sete horas antes.

### Diagnóstico: parado, não lento

A diferença importa, porque leva a ações opostas: treino lento se espera, treino
travado se mata e retoma.

Três evidências convergiram:

- **Nada escrito em disco desde 03:40.** Eram 10h33. Se estivesse rodando
  devagar, ainda estaria salvando checkpoint.
- **O processo usava 148 MB de RAM.** Um modelo de 70 milhões de parâmetros em
  treino ocupa gigabytes. Ele tinha sido descarregado da memória.
- **O `taskkill` respondeu "não há ocorrência da tarefa em execução"** — processo
  zumbi: o registro existe, a execução não.

É o quadro clássico de **suspensão do PC durante treino em GPU**: o contexto CUDA
se perde e o processo fica preso numa chamada de driver que nunca retorna. Nem
`Stop-Process` nem `taskkill /F` derrubam, porque não há o que interromper.

### A recuperação

Matei a árvore inteira — treino, dataloaders, lançadores e o vigia —, desliguei a
suspensão na tomada (`powercfg /change standby-timeout-ac 0`) e retomei do
`last.ckpt`, época 535. Perdi 4 épocas e sete horas de relógio, mas nenhum
progresso real: nas sete horas ele não treinou nada.

O vigia tinha feito o trabalho dele: **seis gerações exportadas durante a noite**
— 0, 107, 214, 317, 422 e 531 — antes do travamento. Se eu dependesse dos
checkpoints, teria as cinco melhores do Lightning e nada do começo.

### Um falso alarme meu, logo depois

Confirmei que o treino tinha voltado medindo o crescimento do log a cada 45
segundos. Deu zero, e eu quase declarei que tinha travado de novo.

Não tinha: o Lightning só escreve no log **ao fim de cada época**, e a época
agora leva 60 segundos. Eu estava amostrando dentro do intervalo de silêncio
normal. A medida honesta era contar épocas, não bytes — 3 épocas em 181 s.

*Lição pequena e útil: escolher o sinal errado transforma comportamento normal em
alarme.*

### O preço que sobrou

A época passou de ~19 s para **60 s**, com a GPU em 15% de uso — gargalo de CPU,
não de placa. O zumbi antigo continua no sistema, ocupando 674 MB e uma fatia da
GPU. Não impediu o treino novo de subir, mas atrapalha.

Nesse ritmo as épocas restantes levariam ~7,5 h em vez de ~2,5. Um reboot resolve;
com a suspensão já desligada, não deve repetir.

### Enquanto isso: a medição estava mentindo

Antes de tudo isso, li os resultados do `generalize` na época 531 e achei dois
defeitos na própria medição.

**A pontuação contava erro que não existia.** "18h45" virava `dezoitohquarenta` e
"R$ 2.300" virava `dois trezentos` em vez de `dois mil e trezentos`. Eu removia a
pontuação antes de soletrar os números, mas ponto de milhar e marcador de hora
significam algo *dentro* de um número.

**A amostra do corpus era pequena demais.** Duas medições **do mesmo modelo**
deram 17,4% e 26,9%: o VITS sintetiza com amostragem estocástica, e seis frases
não seguram uma média. O diagnóstico virou de lado por puro ruído — passou de
"em transição" para "ainda cru" sem nada ter mudado no modelo. Subi para 20
frases.

*É a segunda vez que a ferramenta de diagnóstico erra antes do modelo. Vale
lembrar disso no vídeo: medir é código, e código tem bug.*

### O v2 está melhor, e o ouvido concorda

Com a métrica corrigida, época 531:

| | v1 (ep318) | **v2 (ep531)** |
|---|---|---|
| Corpus | 11,3% | 14,6% |
| Holdout | 39,7% | **26,8%** |
| Distância | +28,4% | **+12,2%** |
| Base, no mesmo holdout | 22,9% | 19,1% |

O holdout caiu 13 pontos e a distância caiu pela metade. **Não é mais o padrão de
fuga do v1**, em que o corpus despencava e o texto novo ficava parado.

Ouvindo, achei a voz "ainda um pouco robótica, não muito natural" — e os números
concordam: onde ele mais perde para a base é em **nasais, sibilantes e siglas**.
"Seis-se nisso surravam", "sei o mês como os comeram". São erros de articulação,
não de memorização. Isso é subtreino, que se resolve treinando; não overfit, que
se resolveria parando.

Era esperado: com metade do learning rate, o timbre demora mais a assentar. Foi o
preço pago de propósito.

### Uma armadilha nas frases de teste

Perguntei se o comando de ouvir usava frases novas. Não usava: são as sete fixas
da bancada — e **duas delas estão no corpus de treino**. Um modelo que decorou
soa bem nelas, que é exatamente o que se quer detectar.

Ganhou um `--text` para falar qualquer coisa digitada na hora. Para julgar de
verdade, o caminho continua sendo o `generalize --play`, que toca as 15 frases
que ninguém nunca gravou.

---

## Dia 4 (continuação) — O Marcos ganhou voz, e a régua estava torta

O dia que começou com um treino morto terminou com o assistente falando comigo
com a minha própria voz. No meio, a ferramenta de medição me enganou pela
terceira vez — e dessa foi a pior.

### Ouvindo o treino, e uma armadilha nas frases de teste

Perguntei se o comando de ouvir usava frases novas. Não usava: são as sete fixas
da bancada, e **duas delas estão no corpus de treino**. Um modelo que decorou soa
bem justamente nessas.

Ganhou um `--phrase novas`, que filtra comparando com o corpus de verdade — se um
dia eu gravar mais frases, a lista se ajusta sozinha.

### O assistente fala

Esse foi o marco do dia. Até então o Marcos respondia por texto na tela; agora
responde **falando, com a voz treinada**.

O desenho segue a decisão D1: o gateway manda a resposta **frase por frase**,
conforme o LLM escreve, e o dispositivo sintetiza e toca. Nenhum áudio atravessa
a rede — uma interação custa alguns KB em vez dos ~250 KB que o plano previa.

Três detalhes que decidiram a implementação:

- **A síntese roda em thread separada.** Piper e a placa de som bloqueiam, e
  travar o laço de eventos enquanto fala impediria o barge-in — que depende
  justamente de continuar ouvindo durante a fala.
- **O stream de áudio abre uma vez, não por fala.** Abrir o dispositivo a cada
  enunciado custa centenas de milissegundos em alguns drivers, fatia grande de um
  orçamento medido em centenas de milissegundos.
- **A voz vem de configuração**, nunca do código. No PC aponta para a bancada; na
  Pi vai apontar para o diretório dela.

Medido: **primeiro chunk de áudio 0,32 s depois do texto chegar**, dentro dos
150–400 ms do orçamento e com folga para a Pi.

### O teste ponta a ponta que matou o treino

Quis testar o loop completo e o Ollama estourou o tempo limite — a GPU estava
ocupada treinando. Tornei o limite configurável (`LLM_TIMEOUT`), subi para 600 s,
e funcionou:

```
voce: oi, quem e voce? responda em uma frase curta
  marcos> Sou o BMO, o assistente de voz pessoal, aqui para ajudar...
```

Funcionou — e **matou o treino**. Uns minutos depois, `CUDA error: out of
memory`: o `llama3.1:8b` tinha entrado na mesma placa de 6 GB. O treino morreu na
época 828.

`ollama stop llama3.1:8b` devolveu a GPU (5510 → 919 MiB) e o `--resume` retomou
da 828. Custou umas 50 épocas e uma lição óbvia em retrospecto: **não rodar o
Ollama enquanto o fine-tune trabalha**.

A decomposição de latência daquele teste, ainda assim, foi reveladora:

```
turn stt=0ms llm_first_token=25776ms primeira_frase=4747ms resposta=221ms
```

Tudo que não é LLM custou **221 ms**. O gargalo é inteiramente o modelo — e
aquele número era CPU, com a GPU ocupada.

### Ele disse "Sou o BMO"

Foi ouvindo isso que decidi o nome. O repositório se chama Marcos-AI e o código
ainda dizia BMO, herdado do plano. Renomeado: `device_id`, loggers, e o system
prompt.

Junto vieram três decisões que estavam paradas: **STT começa pelo mais rápido** e
troca se doer; **sem VPS por enquanto**, porque nada do que falta depende dela; e
**LLM segue open source** via Ollama, com a interface `LLMProvider` como ponto de
troca.

Perguntei também como a Pi saberia o que processar local e o que mandar para o
servidor. A resposta é a peça que ainda não existe: o **roteador de intenções**.
Ele trabalha sobre texto — por isso o STT precisa ser local. É a mesma
contradição do plano que a minha pergunta sobre mp3 destravou no Dia 2, vista de
outro ângulo.

### Gravar mais não custa recomeçar

Perguntei se gravar mais áudio obrigaria a retreinar do zero. Não obriga — e a
ferramenta já existia, só apontava para o lugar errado.

O `prepare`, que arruma um checkpoint publicado, faz o mesmo trabalho com o meu
próprio treino: mantém os pesos, zera o contador de época, descarta o otimizador.
`--from-run` foi tudo que faltou.

Isso muda o cálculo de gravar mais: em vez de "vale a pena refazer 11 horas de
GPU por 15 minutos de áudio?", vira "vale a pena gravar 15 minutos?".

### A régua torta

E aí veio o pior erro do dia, que era meu há três dias sem eu saber.

Com o treino terminado, medi a época final para escolher a voz oficial. O
veredito: **DECOROU**. Corpus 10,4%, holdout 30,6%, distância +20,3%. Parecia
claro — treinou demais e memorizou.

Por precaução, remedi a época 734 nas mesmas condições. Ela tinha medido 26,6% de
holdout algumas horas antes. Deu **35,7%**.

Nove pontos de diferença no mesmo modelo, no mesmo arquivo, sem nada ter mudado.
O ruído estava dominando tudo, e foi ele que condenou a época 996.

A causa: o VITS **amostra ruído a cada geração**. É o que faz a voz soar viva em
vez de robótica — e o que torna impossível comparar duas versões dela. Zerando
`noise_scale` e `noise_w_scale`, a síntese vira reprodutível.

A prova de que funcionou está na coluna da base, que antes oscilava entre 14,6% e
23,6% e passou a medir **14,6% em todas as cinco rodadas**.

### O resultado, medindo direito

| Época | Corpus | Holdout | Distância |
|---|---|---|---|
| 531 | 13,8% | 25,7% | +11,9% |
| 734 | 15,7% | 29,3% | +13,6% |
| 859 | 15,6% | 28,4% | +12,8% |
| 933 | 10,5% | 27,5% | +17,0% |
| **996** | 14,6% | **23,8%** | **+9,2%** |

**A época final ganha nos dois critérios.** O oposto do que eu tinha dito vinte
minutos antes. Treinar até o fim valeu.

Ela virou a voz oficial do Marcos. Meu veredito ouvindo: *não ficou perfeito, mas
está convincente*.

*Terceira vez que a medição erra antes do modelo: no Dia 3 ela mandou parar um
treino saudável, de manhã contava "18h45" como erro, e agora condenou a melhor
época. Fica a regra: **medir com determinismo, ouvir com o ruído normal.***

### Também hoje

- **Auditoria da referência de comandos** contra o `--help` real de cada script.
  Todos os flags apareciam, mas três só de passagem.
- **D12: modelos e gravações ficam fora do repositório.** São 32 GB contra 496 KB
  de histórico versionado — mas o motivo que pesa mais é outro: o `.onnx` treinado
  **é a minha voz**, e o dataset são 30 minutos dela limpos e transcritos. O
  repositório é público. Fica em aberto o backup privado do dataset, que hoje
  existe só no meu disco.

---

## Dia 5 — O microfone entrou no fio, e o fio aprendeu a cair

Hoje foi o dia em que o Marcos deixou de depender de mim digitando.

O stub de STT no gateway morreu. `device/audio/capture.py` grava, o VAD corta a
fala, `device/stt/faster_whisper.py` transcreve, e o que sobe pela rede é uma
mensagem `utterance` com a frase pronta. `gateway/stt/` foi deletado inteiro.
Isso virou [D13](decisions.md), e é o D1 finalmente chegando no código: o áudio
nunca entra no fio.

**A primeira coisa que me pegou foi boba e cara.** Com o modelo em disco, o
faster-whisper ainda saía consultando o Hugging Face na carga. Num aparelho que
existe justamente para funcionar com a internet caída, isso é uma contradição
com a razão de ser do projeto. `local_files_only=True` primeiro, download só
como fallback explícito.

E o número da bancada não sobreviveu ao mundo real:

| | RTF |
|---|---|
| Bancada (`lab/`, dia 2) | 0,43 |
| Dispositivo, PC, `small/int8` | 0,6 – 0,9 |

Frases de 2,5 a 3,8 s levando ~2,2 s cada, e 2,0 s de carga do modelo. A bancada
media o motor aquecido; o dispositivo paga também o `beam_size=5` e o resto do
processo. Não é erro de ninguém — é a diferença entre medir um componente e medir
um sistema. Mas é o número que a Pi vai ter que bater, e ele piorou.

### O fio que ninguém tinha testado cair

Depois vim para a reconexão, que não existia. Qualquer oscilação de Wi-Fi ou
restart do gateway terminava o processo do dispositivo com traceback. Na minha
mesa isso quase nunca acontece — mas o modo de falha de um aparelho de
prateleira é ficar mudo até alguém notar, que é o pior que um assistente de voz
consegue fazer.

Virou [D14](decisions.md). Dois erros no caminho, e os dois foram do mesmo tipo:
a coisa certa no lugar errado.

**A retentativa estava dentro do `receive()`.** Parecia óbvio — caiu, reconecta
ali mesmo. Só que o dispositivo ficava preso no laço de espera em vez de voltar
a ouvir o microfone. Um aparelho travado esperando o gateway não é melhor que um
aparelho morto. Movi a reconexão para o envio: `receive()` só avisa que caiu, e
a reconexão acontece quando existe uma frase de verdade para entregar.

**E o `AuthRejected` herdava de `OSError`.** Herdando, ele caía no `except` da
retentativa — ou seja, um token errado virava espera infinita em vez de erro na
cara. Bug perfeito: silencioso, e disfarçado de resiliência. O teste é o que
fixa isso agora.

`tests/test_reconnect.py` sobe um gateway WebSocket real e derruba ele no meio do
turno. E em campo, matando o uvicorn entre dois turnos: o turno seguinte
funcionou **2,7 s** depois de o gateway voltar, sem eu religar nada.

### Ouvir os dois projetos conversando

Fiquei bem feliz hoje. Rodar os dois lados ao mesmo tempo — o dispositivo que me
ouve, o gateway que processa, e o dispositivo me respondendo com a minha própria
voz — é a primeira vez que isso pareceu um aparelho e não um monte de scripts.
Estou animado pra continuar.

**Mas ficou uma preocupação, e ela é honesta:** será que isso roda mesmo no
hardware? Tudo até aqui foi medido no PC. Pensei em emular para ter uma ideia
antes. E, no pior dos casos, se não rodar, eu uso a Raspberry para outros
projetos que já tenho em mente — o que não é derrota nenhuma, mas é bom ter dito
em voz alta antes de comprar mais coisa.

### A pergunta do fim do dia: e se ele traduzisse?

Perguntei uma coisa que não estava no plano: dá para eu falar em português e o
aparelho falar em inglês ou chinês, e vice-versa? Um tradutor portátil. E dá para
funcionar sem internet?

A resposta foi melhor do que eu esperava: **duas das três peças já existem.** O
faster-whisper é multilíngue de nascença — o mesmo modelo que transcreve
português transcreve inglês e chinês. O Piper é o oposto: uma voz por idioma,
~60 MB cada, mas isso é só disco. Falta só a tradução no meio.

Dois candidatos offline, e a comparação matou um deles na mesa:

| | opus-mt (int8) | NLLB-200 600M (int8) |
|---|---|---|
| Disco, por direção | ~75 MB | ~600 MB (um só, 200 idiomas) |
| RAM residente | ~100 MB | ~700–800 MB |
| Latência estimada na Pi 5, frase curta | ~0,1–0,3 s | ~1,5–4 s |
| Qualidade | boa nos pares comuns | melhor, sobretudo em pares raros |

O que derruba o NLLB não é a RAM — 8 GB aguentam. É ele ser encoder-decoder
autorregressivo: gera token a token, cada token atravessando 600M de parâmetros
em quatro núcleos Cortex-A76 sem acelerador. **É exatamente o problema da
Tentativa 2 do dia 1**, e o veredito de lá continua valendo: para voz, inviável.
Somado ao Whisper na frente, uma frase de 4 s viraria uns 10 s até sair som.

O opus-mt ganha por outro motivo, que é quase administrativo: ele roda em
**CTranslate2**, o mesmo runtime que o `faster_whisper` já usa. Tem wheel para
`aarch64` e usa o backend Ruy para GEMM int8 em ARM — não é caminho emulado. Se o
Whisper roda na Pi, o CTranslate2 já está lá. Adicionar tradução vira adicionar
um modelo, não uma stack — e numa Pi que o D1 já deixou apertada, isso pesa.

**Dois detalhes que só apareceriam na prática, e que anotei antes de esquecer:**

- **Os dois vão brigar por núcleos.** São quatro na Pi 5. O pipeline é serial
  (STT termina, depois MT começa), então dá para dar os quatro a cada um na sua
  vez — mas isso é configuração explícita de `intra_threads`, não default.
- **Detecção de turno é o buraco de verdade.** Um tradutor de conversa precisa
  saber quem está falando em qual idioma. Autodetecção do Whisper erra em frases
  curtas ("ok", "no"). Botão físico — segura para falar, solta para ouvir — é o
  que o Pocketalk faz, e é o que eu faria primeiro. É um problema de UX
  disfarçado de problema de ML.

Nada disso virou decisão. **Não medi nada na Pi ainda** — nem o Whisper, e o
`RTF 1,3–2,2` do dia 2 continua sendo extrapolação. Registrar o NLLB aqui é o
mesmo que fizemos com o `edge-tts`: teto de comparação, marcado como
não-candidato no dispositivo. Se um dia o modo tradutor puder usar o gateway
quando houver rede, ele volta à mesa.

O tradutor entra como marco planejado depois da Fase 2, e o primeiro passo dele
é um experimento em `lab/` no formato dos outros: opus-mt pt↔en sobre as minhas
gravações reais, medindo latência e olhando a tradução. Aí vira número, e número
vira decisão.

---

## Dia 5 (continuação) — A Fase 1 que parecia pronta

Perguntei se a Fase 1 já estava implementada. A resposta honesta foi: **dois
terços, e o terço que falta estava escrito mas nunca tinha sido executado.**

Autenticação por token: feita. Latência simulada: feita. Gateway
containerizado: o `Dockerfile` e o `docker-compose.yml` existiam desde cedo — e
justamente por existirem, pareciam prontos. Mas o critério de aceite do plano é
`docker compose up` subindo tudo, e não há registro em lugar nenhum de isso ter
sido rodado uma vez sequer.

Olhando os dois arquivos com atenção, eles não subiriam. Três problemas, e os
três da mesma família: **decisões posteriores passaram por cima deles e ninguém
voltou ali.**

**1. O container não acharia o Ollama.** O `.env` diz
`OLLAMA_URL=http://localhost:11434`. Dentro do container, `localhost` é o
próprio container. Isso é o D11 (trocar o LLM por Ollama) atravessando um
compose escrito antes dele.

**2. A imagem instalaria o `requirements.txt` inteiro** — `torch`,
`transformers`, `speechbrain`, `vosk`, `piper-tts[train]`. Vários GB para um
processo que, depois do D13, não tem modelo nenhum. Rodei o levantamento das
importações de `gateway/` e `common/` e o resultado foi minúsculo:

```
fastapi  httpx  dotenv  + biblioteca padrão
```

É só isso. Virou `requirements-gateway.txt`, e o `requirements.txt` passou a ser
o ambiente de desenvolvimento, incluindo o outro por referência. [D15](decisions.md).

**3. Não havia `.dockerignore`.** Esse é o que mais teria doído na prática. O
contexto de build é a raiz do projeto — precisa ser, porque `common/` é o
contrato compartilhado e tem que entrar na imagem. Sem ignorar nada, o Docker
empacota `.venv` e `lab/models/` e manda tudo para o daemon **antes da primeira
linha do Dockerfile rodar**. Medi o que iria junto:

```
5.8G  .venv
7.0G  lab/models
 28G  lab/finetune
```

**41 GB** viajando para o daemon para construir uma imagem que não usa um byte
de nenhum deles. E o `.gitignore` não ajuda aqui: o Docker não lê aquele arquivo.

De quebra, o processo rodava como root, o que é indiferente na minha mesa e não
é indiferente numa VPS exposta. Agora tem usuário próprio e um `HEALTHCHECK` que
bate no `/health` com o Python da própria imagem — a `python:3.12-slim` não tem
curl.

E `gateway/stt/` ainda estava no disco: o D13 apagou os `.py`, o git registrou,
e a pasta vazia ficou para trás com um `__pycache__` dentro.

### O que eu não consigo afirmar

**Não rodei.** Esta máquina não tem Docker nem WSL2 — `wsl -l -v` responde que o
subsistema não está instalado. Então o que existe agora é código escrito com
cuidado, não comportamento observado, e está marcado assim no D15.

Tentei resolver: `wsl --install`. O Windows respondeu que o subsistema não está
instalado — a mesma mensagem que ele dá para qualquer argumento quando a feature
está desligada. Achei que fosse falta de administrador. Não era:

```
Requisitos do Hyper-V:  Extensão de Modo de Monitor VM: Sim
                        Virtualização Habilitada no Firmware: Não
```

**A virtualização está desligada na BIOS**, e vai continuar. Com ela ligada, o
Vanguard não deixa o Valorant abrir, e esta máquina também é de jogo. Sem
virtualização não há WSL2, sem WSL2 não há Docker Desktop, e o backend Hyper-V
não é saída porque exige exatamente a mesma coisa.

Então o Docker fica para a VPS ([D16](decisions.md)), que é onde ele existe para
rodar de qualquer forma — Linux, Docker Engine, nada disso se aplica lá. O custo
disso é honesto e vale escrever: **o primeiro `docker compose up` da vida desses
arquivos vai ser no dia do deploy**, que é o pior dia possível para descobrir um
erro de digitação no YAML.

Isso me incomoda menos do que o estado anterior, e por um motivo específico:
antes, a Fase 1 *parecia* pronta porque os arquivos existiam. Agora ela está
escrita e **declarada não verificada**. Arquivo que existe não é entrega — a
diferença entre os dois é alguém ter rodado uma vez.

*Lição para o vídeo: o pior tipo de dívida técnica não é o código feio. É o
arquivo plausível que ninguém executou, porque ele passa em toda revisão visual
e só falha no dia em que você precisa dele.*

---

## Dia 5 (final) — O nível 0, e três bugs que só a execução mostrou

A Fase 2 é o núcleo da substituição da Alexa: timer, alarme e hora, funcionando
com a internet fora. O plano coloca ela antes do rosto e do wake word de
propósito, e depois de escrever isso eu entendo por quê — é a primeira parte que
não pode falhar.

Saíram três peças: `device/local/` (SQLite + agendador), `device/router/`
(regex com extração de slots) e a mudança no laço do dispositivo que consulta o
roteador **antes** da rede. Virou [D17](decisions.md).

### O roteador recusa mais do que aceita, e isso é o ponto

A regra 1 do plano diz que roteador que chuta é pior que roteador nenhum. Então
metade do teste de roteador é sobre o que ele **não** pode reconhecer:

```
"põe um timer de 10 minutos"        -> criar_timer, 600s
"me acorda daqui a vinte e cinco minutos" -> criar_timer, 1500s
"alarme pras 6h15"                  -> criar_alarme, 6:15
"põe um timer de banana minutos"    -> None  (sobe pro LLM)
"me acorda às 30"                   -> None  (hora impossível)
"que horas são em Tóquio"           -> None  (não é a hora local)
```

O primeiro padrão que escrevi tinha um erro sutil: `_NUM` aceitava
`[a-z]+`, qualquer palavra. Em *"põe um alarme para as 6 e 30"*, o `as` casava
como candidato a número, a conversão devolvia `None`, e a frase inteira caía
para o LLM — uma frase perfeitamente reconhecível. Troquei o curinga pela lista
literal de números por extenso. **Regex permissiva demais não erra reconhecendo
errado; erra deixando de reconhecer, que é mais difícil de notar.**

### Três bugs, e nenhum deles apareceu nos testes

Escrevi 61 testes, todos passando, e aí rodei o aparelho de verdade. Três coisas
quebraram.

**1. `illegal transition State.IDLE -> State.THINKING`.** No caminho de gateway
fora do ar eu forçava a máquina de estados para IDLE e depois para THINKING
direto. Ela recusou — e estava certa: as transições legais são as do plano, e
IDLE só vai para LISTENING. A máquina de estados do Dia 2 pegou um bug meu do
Dia 5. É o tipo de coisa que só se descobre gostando de ter escrito a validação
quando ela te contraria.

**2. O timer não tocava.** Esse foi o bom. O serviço gravava certo. O agendador
disparava certo. Os testes dos dois passavam. E mesmo assim:

```
voce:   marcos> Timer de 5 segundos.   [nivel 0, local]
voce: (silêncio)
```

Fui olhar o banco:

```
{'id': '948a070b', 'kind': 'timer', 'fire_at': ..., 'fired_at': None}
```

Gravado, pendente, nunca disparado. **Ninguém acordava o agendador.** Ele dorme
até o próximo disparo conhecido — e quando não há nada agendado, dorme os 30
segundos do `MAX_SLEEP`. Um timer novo, mais curto que isso, só seria notado na
soneca seguinte. O método `notify()` existia desde o começo e nunca era chamado.

Isso é o defeito clássico de teste de unidade: as duas peças estavam certas, o
**elo** entre elas não existia, e nenhum teste olhava para o elo. O teste novo
reproduz exatamente isso — deixa o agendador adormecer com a fila vazia, cria um
timer curto, e falha se ele não tocar.

**3. "São 20 e 1."** Ouvi o aparelho falar isso e ficou óbvio. Escrito, `20:01`
está certo; falado, ninguém diz "vinte e um" para uma da noite passada de um
minuto. Com minuto abaixo de dez a pessoa fala a unidade inteira: *"são vinte
horas e um minuto"*. É a mesma lição do Dia 2 com o `edge-tts` — o texto que vai
para o TTS não é o texto que se escreve.

### A prova de que a Fase 2 está de pé

Gateway desligado, do começo ao fim:

```
marcos.ws gateway fora do ar; subindo em modo local
gateway: fora do ar -- timer, alarme e hora continuam

voce:   marcos> Sao 20 horas e 2 minutos.   [nivel 0, local]
voce:   marcos> Timer de 5 segundos.        [nivel 0, local]
voce:
  marcos> Seu timer acabou.                 [timer]
  marcos> Nao tem nada marcado.             [nivel 0, local]
```

O timer tocou sozinho, cinco segundos depois, sem nenhum servidor no ar. Esse é
o critério de aceite da Fase 2, e é a primeira vez que o aparelho faz algo útil
sem depender de nada além dele mesmo.

### O que deixei de fora, e por quê

**Embeddings.** O plano quer regex *e* similaridade. Só o regex existe, o que
cobre formato rígido e não cobre paráfrase. Deixei de fora de propósito: as 5–10
frases de exemplo por intenção teriam que ser inventadas por mim, e eu estaria
adivinhando como *eu* falaria, não como eu falo. O log do nível 2 já está
gravando as frases que sobem — em um mês ele diz quais paráfrases são reais.

**Volume.** Está no nível 0 do plano. Depende do mixer do sistema operacional,
que é código por plataforma e não se testa na mesa como o resto se testou.

Nos dois casos o comportamento sem eles é o correto: o que não casa sobe para o
LLM. Uma lacuna que degrada bem não é dívida — é escopo.

*Lição para o vídeo: 61 testes verdes e três bugs em dois minutos de uso real. Os
testes provaram que cada peça funcionava. Nenhum deles perguntava se as peças
estavam ligadas uma na outra.*

---

## Onde estamos agora

**O Marcos me ouve, pensa, responde com a minha voz — e agora também resolve
sozinho o que não precisa de ninguém.** Timer, alarme e hora funcionam com o
gateway desligado e com a internet fora.

**O Marcos me ouve, pensa e responde com a minha voz — sem eu digitar nada.** O
microfone captura, o VAD corta, o faster-whisper transcreve no próprio
dispositivo, o gateway consulta o LLM e devolve a resposta frase por frase, e o
Piper sintetiza. Pela rede sobe e desce só texto. E se o fio cair no meio, o
aparelho volta sozinho.

A voz oficial é a **época 996** do fine-tune v2, com 30,9 min de áudio e learning
rate 1e-4. Medida com síntese determinística: holdout 23,8% contra 14,6% da base.

Fechado até aqui:

| | Escolha | Por quê |
|---|---|---|
| Nome | Marcos (D8) | o repositório já se chamava assim |
| Arquitetura | Dois processos, WebSocket | migrar = trocar URL |
| Rede | só texto, nos dois sentidos (D7, D13) | alguns KB por interação, e fala offline |
| LLM | open source via Ollama (D11) | preferência; `LLMProvider` é o ponto de troca |
| STT | faster-whisper no dispositivo, tamanho a decidir na Pi (D9, D13) | nível 0 offline não existe sem isso |
| TTS | Piper, voz própria treinada (D4) | RTF 0,05, offline, timbre próprio |
| Locutor | ECAPA-TDNN | cadastro, não treino |
| Queda de rede | reconexão com espera crescente (D14) | ficar mudo é o pior modo de falha |
| VPS | adiada (D10) | nada do que falta depende dela |
| Binários | fora do git (D12) | 32 GB, e o `.onnx` é a minha voz |
| Imagem do gateway | só `requirements-gateway.txt` (D15) | sem STT, sobrou fastapi + httpx |
| Nível 0 | regex + SQLite no dispositivo (D17) | o despertador não pode depender do Wi-Fi |
| Boot | sobe sem o gateway (D17) | senão o critério da Fase 2 é impossível |

**Fase 0 cumprida por inteiro, e além.** O critério era o loop em dois processos;
temos LLM real, voz própria e o STT fora do stub.

**Fase 1 escrita, verificação adiada para a VPS (D16).** Token e latência
simulada funcionam. O container foi corrigido (D15) — imagem enxuta,
`.dockerignore`, Ollama alcançável de dentro, usuário não-root — mas
`docker compose up` **nunca rodou e não vai rodar aqui**: a virtualização fica
desligada na BIOS por causa do Valorant, e sem ela não há WSL2 nem Docker
Desktop. Na VPS é Linux, e o problema não existe.

**Fase 2 entregue no essencial.** Timer, alarme, hora, listar e cancelar rodam
no dispositivo, sem rede e sem LLM, e o aparelho liga com o gateway desligado. O
critério de aceite — "timer funciona com o gateway desligado" — foi verificado
rodando, não só em teste.

Falta da Fase 2, e é escopo consciente (D17): a similaridade por **embeddings**,
que espera o log real de nível 2 dizer quais paráfrases as pessoas usam; e o
**volume**, que depende do mixer do sistema operacional.

Próximo marco: **Fase 3 — ferramentas no gateway** (busca web, Spotify, Home
Assistant), ou a Fase 4 (o rosto). Nenhuma das duas depende de hardware.

Marco seguinte, planejado: **modo tradutor portátil.** Falar português e o
aparelho falar inglês ou chinês, e o contrário. Duas das três peças já existem —
o Whisper é multilíngue, o Piper tem voz por idioma. Falta a tradução no meio, e
o candidato é **opus-mt em CTranslate2**, que é o runtime que o `faster_whisper`
já usa. O NLLB-200 600M fica registrado como teto de comparação e
**não-candidato no dispositivo** — autorregressivo demais para quatro núcleos
ARM, o mesmo motivo que derrubou o LLM local no dia 1. Primeiro passo: um
experimento em `lab/` medindo opus-mt pt↔en sobre as gravações reais. Detalhes e
números estimados no [Dia 5](#dia-5--o-microfone-entrou-no-fio-e-o-fio-aprendeu-a-cair).

Em aberto:

- **Se o container sobe** — só se descobre na VPS (D15, D16). Se aparecer
  qualquer máquina com Docker antes disso, rodar o build ali se paga.
- **Se tudo isso cabe na Pi** — nada foi medido lá ainda, nem o Whisper. O
  RTF do dispositivo já subiu de 0,43 para 0,6–0,9 só saindo da bancada para o
  código real. É a maior incerteza do projeto hoje.
- Qual tamanho de STT cabe na Pi, quando houver Pi para medir (D9)
- Backup privado do dataset, que hoje existe só num disco
- Se um modelo aberto de 8B dá conta de busca fundamentada (D11)
- Se um bloco 4 de gravações vale a pena (o `prepare --from-run` já deixa barato)
- Se o gateway deve re-transcrever com um modelo maior — a pergunta de D1 que
  D13 deixou sem caminho, porque o áudio não sobe mais

Ainda não começou: embeddings no roteador, volume, ferramentas do gateway, modo
tradutor, rosto, wake word, VPS, hardware.

---
## Como continuar preenchendo

No fim de cada sessão, rode:

```
/documentar
```

A skill está em `.claude/skills/documentar/`. Ela lê o que mudou, pergunta o que
só você sabe (as dúvidas, o que você achou que ia funcionar e não funcionou),
escreve a entrada nova e propaga para os outros documentos.

Uma seção por sessão de trabalho. O que vale registrar, em ordem de
interesse para quem assiste:

1. **O que deu errado e por quê** — é o que ninguém publica e todo mundo passa.
2. **A dúvida antes da decisão** — a decisão sozinha não ensina nada; o que
   ensina é o que estava em jogo.
3. **Números medidos**, com a data. Número sem contexto envelhece mal.
4. **O que foi descartado**, e o motivo. Evita refazer o mesmo caminho.

As decisões formais, secas, continuam em [`decisions.md`](decisions.md). Os
números de bancada, em [`lab/RESULTS.md`](../lab/RESULTS.md). Aqui é a história.
