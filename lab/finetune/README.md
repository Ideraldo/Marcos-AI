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
py -m lab.finetune.record --review 12 # ouvir e refazer a frase 12
```

São 95 frases: 45 do domínio do assistente ("Timer de dez minutos", "Acendi a luz
do quarto") e 50 escolhidas para varrer sons que as primeiras não cobrem —
nasais, encontros consonantais, perguntas, estrangeirismos.

Para sozinha quando você para de falar. Pode parar com `q` e continuar depois:
retoma de onde ficou. Recusa automaticamente takes baixos demais ou saturados.

**O que mais importa não é configuração:** uma sessão só, uma distância do
microfone, um humor só. O modelo copia o seu ritmo e a sua energia — se a segunda
metade sair cansada, a voz soa cansada metade do tempo. Leia como quer que o
assistente soe.

Grava a 48 kHz e reamostra para 22050 com filtro band-limited, porque o dataset
carrega para dentro do modelo qualquer artefato que tiver.

### Quanto é suficiente

As 95 frases dão uns 9 minutos. Isso já produz um timbre reconhecível partindo
de um checkpoint bom, mas **15 a 30 minutos** é onde fica convincente. Rodar o
corpus duas vezes, em dias diferentes, também ajuda: dá variação de entonação em
vez de mais do mesmo.

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
