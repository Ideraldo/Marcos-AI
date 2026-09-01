# Fine-tune do Piper com a sua voz

> Referência rápida de comandos e parâmetros: [`../docs/comandos.md`](../docs/comandos.md).

Objetivo: um modelo Piper de ~60 MB com o seu timbre, rodando a RTF 0,05 na Pi.
É o único caminho que entrega voz personalizada **e** velocidade — clonagem
zero-shot (XTTS, F5) dá timbre mas não roda em ARM.

Não é treinar do zero. O checkpoint base já fala português; suas gravações mudam
o timbre. Por isso uma hora de áudio basta onde uma voz do zero pediria dezenas.

---

## 1. Gravar

```powershell
py -m lab.devices                     # confirme o microfone antes
py -m lab.finetune.record
py -m lab.finetune.record --status    # quanto já tem
py -m lab.finetune.check              # procura takes ruins antes de treinar
py -m lab.finetune.generalize --voice pt_BR-ideraldo-medium --against pt_BR-dii-high
py -m lab.finetune.record --review 12 # ouvir e refazer a frase 12
py -m lab.finetune.record --redo 1-10  # apagar as 10 primeiras e regravar
py -m lab.finetune.record --reset     # apagar tudo e comecar de novo
```

São 315 frases (ver "Quanto é suficiente" abaixo). O gravador retoma sempre de
onde parou, então dá para fazer em várias sessões.

Para sozinha após 1600 ms de silêncio. Pode parar com `q` e continuar depois:
retoma de onde ficou. Recusa automaticamente takes baixos demais ou saturados.

O limiar é generoso de propósito. Os trechos do bloco 3 têm dois ou três
períodos, e a pausa natural depois de um ponto final passa fácil de um segundo —
com os 700 ms que eu tinha posto no começo, a gravação encerrava no meio da
frase e o modelo aprenderia a parar ali. Trocar um pouco de silêncio no fim do
arquivo por não perder metade do texto é troca fácil: o treino ignora silêncio,
mas não inventa o que faltou. Se ainda cortar, `--silence 2200`.

Se as primeiras saírem ruins, `--redo 1-10` apaga só aquele intervalo e mantém o
resto. `--reset` apaga tudo, e pede confirmação digitada — gravação é a parte
cara, um engano aqui custa uma hora de leitura, não uma re-execução de script.

**O que mais importa não é configuração:** uma sessão só, uma distância do
microfone, um humor só. O modelo copia o seu ritmo e a sua energia — se a segunda
metade sair cansada, a voz soa cansada metade do tempo. Leia como quer que o
assistente soe.

Grava a 48 kHz e reamostra para 22050 com filtro band-limited, porque o dataset
carrega para dentro do modelo qualquer artefato que tiver.

### Quanto é suficiente

O corpus tem 315 frases em três blocos:

| Bloco | Frases | Áudio | O que é |
|---|---|---|---|
| 1 (1–95) | 95 | ~5 min | domínio do assistente + varredura fonética, frases curtas |
| 2 (96–203) | 108 | ~10 min | frases longas, com vírgula, subordinada e respiração no meio |
| 3 (204–315) | 112 | ~15 min | trechos de dois ou três períodos, 10–15 s cada |

**Os blocos 2 e 3 nasceram de erros de estimativa, e vale registrar os dois.**

O bloco 1 rendeu 95 arquivos e só 5 minutos: o que falta num fine-tune não é
quantidade de arquivos, é **minutos**.

O bloco 3 nasceu de um erro maior. Com os 15 minutos dos blocos 1 e 2, o treino
**decorou**: na época 318 o WER do corpus tinha caído para 11,3% enquanto o de
texto novo ficava parado em 39,7%. O modelo estava ficando ótimo em dizer
exatamente aquelas frases e nada melhor em ler qualquer outra coisa. Não era
falta de épocas — eram 14.828 passos já — era falta de material para generalizar.

### Por que trechos de 10–15 s, e não parágrafos

Trecho longo rende mais minuto por ENTER apertado. Mas existe um teto:

- **O padding.** O `collate` do Piper preenche todas as amostras do batch até a
  mais longa. Um trecho de 30 s força os outros sete do batch a 30 s — VRAM
  desperdiçada numa placa de 6 GB, e computação gasta em silêncio.
- **Na inferência o Piper divide por sentença de qualquer jeito.** Treinar em
  parágrafos ensina uma prosódia longa que ele nunca vai usar.

Dez a quinze segundos é onde se ganha minuto sem pagar nenhum dos dois preços. E
mantém muitas amostras distintas, que é o que ensina começo e fim de frase.

Não há filtro de comprimento no Piper — trechos longos não seriam descartados, só
sairiam caros.

## 2. Treinar

```powershell
py -m lab.finetune.train --base pt_BR-dii-high --name ideraldo
py -m lab.finetune.train --name ideraldo --resume    # se interromper
```

Base padrão é `pt_BR-dii-high` — qualidade "high", que soa melhor que as
"medium". `pt_BR-miro-high` é a alternativa. Nenhuma das duas está na lista
oficial do Piper; vieram do OpenVoiceOS, que é onde os checkpoints de treino
sobreviveram depois que o repositório oficial saiu do ar.

Na RTX 2060 (6 GB), `--batch-size 8` com precisão 16-mixed. Se faltar VRAM,
`--batch-size 4` — custa tempo, não qualidade.

### Quanto demora

Medido nesta máquina com as 203 gravações: **22 batches por época, ~15 s cada**.

| Épocas | Tempo | O que esperar |
|---|---|---|
| 300 | ~1h15 | já dá para ouvir para onde o timbre está indo |
| 1000 | ~4h | normalmente já convincente |
| 2000 | ~8h | o padrão do comando; rode dormindo |

Dá para interromper com Ctrl+C e continuar com `--resume` sem perder nada.
Também dá para exportar um checkpoint intermediário e ouvir antes de decidir se
vale continuar.

### O que o preparo do checkpoint resolve

Rodar `train` chama `lab.finetune.prepare` sozinho na primeira vez. Ele existe
porque três coisas separam um checkpoint publicado de um fine-tune que roda:

- **PosixPath** — foram salvos no Linux e guardam objetos `pathlib` dentro. O
  Windows não consegue nem abrir o arquivo.
- **weights_only** — o torch 2.6 passou a recusar checkpoints com objetos, e é
  assim que o Lightning carrega.
- **O contador de época** — essa é a que custaria uma tarde. `--ckpt_path`
  significa *retomar*, então ele restaura a época também: o checkpoint do dii
  parou na época 3908, e pedir 2000 faria o treino encerrar na hora sem fazer
  nada. Zerar o contador é o que transforma "retomar o treino dos outros" em
  "começar o meu a partir dos pesos deles".

O estado do otimizador é descartado pelo mesmo motivo: pertence ao treino deles,
com a voz deles, e carregá-lo adiante atrapalha a voz nova em vez de ajudar.

### O monotonic_align que falta na wheel

A wheel do `piper-tts[train]` para Windows vem sem a extensão Cython do
Monotonic Alignment Search — nem o `.pyx` está lá, então não dá nem para
compilar. O treino morreria no primeiro batch.

`lab/finetune/monotonic_align.py` reimplementa esse algoritmo com numba e se
instala sozinho quando o treino começa. É a busca em programação dinâmica no
coração do VITS: dado o custo de alinhar cada posição do texto com cada quadro
de áudio, achar o único caminho monotônico de custo mínimo — que é como o modelo
aprende, sem nenhum alinhamento rotulado, quanto tempo dura cada fonema.

## 3. Exportar e ouvir

```powershell
py -m lab.finetune.train --list --name ideraldo            # o que da para exportar
py -m lab.finetune.train --export --name ideraldo          # o mais recente
py -m lab.finetune.train --export --epoch 318 --name ideraldo   # uma epoca especifica
py -m lab.run_tts --engine piper --voice pt_BR-ideraldo-medium --play
```

Exportar uma época específica dá o nome `pt_BR-ideraldoep318-medium`, com a época
embutida. É de propósito: exportar duas não sobrescreve uma a outra, e as duas
ficam na bancada para serem ouvidas lado a lado nas mesmas frases. `--as <nome>`
muda isso se você quiser outro nome.

O Lightning grava um checkpoint por métrica monitorada, então uma mesma época
pode ter dois arquivos (`val_mel` e `val_mos`). São o mesmo modelo — qualquer um
serve, e o comando avisa qual escolheu. Para apontar um arquivo exato,
`--checkpoint "epoch=318-val_mos=3.1173.ckpt"`.

O `.onnx` cai direto em `lab/models/piper/`, junto com o `.onnx.json` copiado da
voz base — o exportador do Piper só escreve o `.onnx`, e sem o config ao lado o
modelo nem carrega. Entra na bancada como qualquer outra voz e pode ser
comparado com as demais nas mesmas frases.

**Todo esse caminho já foi testado ponta a ponta** com uma época de treino: o
checkpoint preparado carrega, o treino roda na GPU, o export sai e a voz
resultante sintetiza a RTF 0,06.

---

## 4. O risco real: decorar em vez de aprender

Com 15 minutos de áudio e 203 frases, existe um risco concreto: em vez de
aprender o seu **timbre**, o modelo decora as suas **frases**. Ele soaria ótimo
dizendo "Timer de dez minutos" e desmoronaria em qualquer texto novo — que é
exatamente o que o assistente vai falar o dia inteiro, já que a resposta do LLM
nunca é uma frase pré-escrita.

```powershell
py -m lab.finetune.generalize --voice pt_BR-ideraldo-medium --against pt_BR-dii-high
py -m lab.finetune.generalize --voice pt_BR-ideraldo-medium --play   # ouvir também
```

### Como funciona

Sintetiza 15 frases que **nunca foram gravadas** (`holdout.py` — nomes próprios,
siglas, estrangeirismos, trava-línguas, uma frase de três linhas) e transcreve o
resultado **de volta** com o Whisper. Se a voz articula, o STT entende; se
desmonta em texto novo, o WER sobe e mostra onde.

Não substitui o ouvido: um modelo pode soar metálico e ainda ser transcrito
perfeitamente. Mas pega o que o ouvido deixa passar — uma sílaba comida no meio
de uma palavra longa, um número lido errado, um nome próprio virando outra coisa
— e dá um número comparável entre épocas.

### Por que ele mede o corpus também

Esse foi um erro de projeto que só apareceu ao rodar. A primeira versão olhava só
o WER do holdout e gritava "overfitting" — mas **WER alto em texto novo não
distingue duas doenças opostas**:

| | Corpus | Holdout | O que fazer |
|---|---|---|---|
| **Decorou** | baixo | alto | Voltar a um checkpoint anterior; passou do ponto |
| **Ainda cru** | alto | alto | **Treinar mais**; é o estado normal no começo |

A diferença entre as duas está na *distância* entre as colunas, não no valor de
nenhuma. E as decisões são opostas: uma manda parar, a outra manda continuar.

Medido na época 113 deste treino:

```
corpus (frases treinadas):  WER 26.3%
holdout (nunca gravadas):   WER 39.2%
distancia entre os dois:    +12.8%
a base, no mesmo holdout:   WER 20.9%

=> AINDA CRU
```

Vai mal nos dois, com distância moderada. O modelo já saiu da articulação limpa
da base e ainda não chegou na do usuário — que é exatamente o que se ouve: timbre
reconhecível, mas robótico.

### O que vigiar ao longo do treino

Rode a cada algumas centenas de épocas e guarde a série. O padrão saudável é as
duas colunas caindo juntas. O sinal de parada é a **distância abrindo**: corpus
continua caindo e holdout empaca ou sobe.

O `val_mel` que aparece no nome dos checkpoints ajuda, porque o Lightning já
calcula sobre uma fatia separada do dataset — quando ele para de cair e começa a
subir, é o mesmo aviso. Mas ele mede semelhança com as suas gravações, não se a
voz lê bem um texto qualquer. Por isso o teste de holdout existe.

---

## Bônus: as gravações servem duas vezes

A seção 9 do plano pede 150–200 gravações da sua voz para treinar o wake word.
São as mesmas amostras. Gravar uma vez resolve as duas coisas.
