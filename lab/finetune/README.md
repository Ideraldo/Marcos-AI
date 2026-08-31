# Fine-tune do Piper com a sua voz

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
py -m lab.finetune.record --review 12 # ouvir e refazer a frase 12
py -m lab.finetune.record --redo 1-10  # apagar as 10 primeiras e regravar
py -m lab.finetune.record --reset     # apagar tudo e comecar de novo
```

São 203 frases (ver "Quanto é suficiente" abaixo). O gravador retoma sempre de
onde parou, então dá para fazer em várias sessões.

Para sozinha quando você para de falar. Pode parar com `q` e continuar depois:
retoma de onde ficou. Recusa automaticamente takes baixos demais ou saturados.

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

O corpus tem 203 frases em dois blocos:

| Bloco | Frases | Áudio | O que é |
|---|---|---|---|
| 1 (1–95) | 95 | ~5 min | domínio do assistente + varredura fonética, frases curtas |
| 2 (96–203) | 108 | ~12 min | frases longas, com vírgula, subordinada e respiração no meio |

O bloco 1 rendeu menos áudio do que parecia: 95 arquivos, mas só 5 minutos. O
que falta num fine-tune não é quantidade de arquivos, é **minutos**. Por isso o
bloco 2 é de frases longas — rende o dobro de áudio com a mesma paciência, e
carrega prosódia que frase curta não tem.

Os dois juntos dão uns **17 minutos**, que é onde o timbre fica convincente.

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

## 3. Exportar e ouvir

```powershell
py -m lab.finetune.train --export --name ideraldo
py -m lab.run_tts --engine piper --voice pt_BR-ideraldo-medium --play
```

O `.onnx` cai direto em `lab/models/piper/`, então entra na bancada como
qualquer outra voz e pode ser comparado com as demais nas mesmas frases.

---

## Bônus: as gravações servem duas vezes

A seção 9 do plano pede 150–200 gravações da sua voz para treinar o wake word.
São as mesmas amostras. Gravar uma vez resolve as duas coisas.
