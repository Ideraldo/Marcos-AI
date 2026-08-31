# Resultados — STT e TTS

Registro vivo. Cada motor testado ganha uma linha; a coluna **Ouvido** é sua e
vale mais que as outras.

**Escopo fechado: só offline.** STT e TTS rodam na Pi, porque o roteador de
intenções trabalha sobre texto — sem STT local não existe nível 0, e nível 0 com
a internet caída é requisito. Para a VPS sobe só texto.

**`[PT]` marca modelo especializado em português** (treinado ou ajustado só nele),
contra os multilíngues que apenas suportam pt. Veja tudo com `python -m lab.list`.

Medidas em: Windows 11, Python 3.12, CPU (sem GPU). Conjunto: as sete frases de
`lab/phrases.py`. **Na Pi 5, conte com 3 a 5 vezes esses tempos.**

---

## TTS

| | Motor | Voz | RTF | Carga | Nativo | Tamanho | Ouvido |
|---|---|---|---|---|---|---|---|
| `[PT]` | **Piper** | faber-medium | **0,05** | 2,7 s | 22050 Hz | 60 MB | *a preencher* |
| `[PT]` | Piper | cadu / jeff / edresson | — | — | 22050 Hz | 60 MB | *não testado* |
| `[PT]` | MMS (Meta) | por | 0,27 | ~15 s | 16000 Hz | ~145 MB | *a preencher* |
| | ~~edge-tts~~ | Francisca | 0,62 | — | 24000 Hz | nuvem | *só referência* |

**Piper faber-medium** — RTF 0,05, constante em todas as frases: 20x mais rápido
que o tempo real. Carrega em 2,7 s, uma vez no boot. Lê números corretamente sem
ajuda. Mesmo com a folga de 5x da Pi, fica muito abaixo dos 150–400 ms do
orçamento. **É o candidato a bater.**

**MMS-TTS (facebook/mms-tts-por)** — também especializado, linhagem diferente
(VITS da Meta). RTF 0,27: 5x mais lento que o Piper, ainda dentro do orçamento,
mas com muito menos margem para a Pi. Sai a 16 kHz, exatamente a taxa do
pipeline, então não perde nada no resample.

> ⚠️ **Ele pulava todos os números.** "O CEP é 04538-133" saía como "O sepé, ele"
> — os dígitos sumiam sem erro nenhum. O tokenizer uroman não tem normalizador
> numérico. Corrigido soletrando os dígitos antes da síntese (`lab/numbers.py`,
> o mesmo soletrador que a pontuação de WER já usava). O áudio da frase foi de
> 3,55 s para 9,41 s depois do conserto. Fica o registro: um TTS que não lê
> número é inútil para "são sete e quinze".

*Sua avaliação (por voz):* naturalidade ___/5 · prosódia de pergunta ___/5 ·
números e horas ___/5 · cansa depois de 10 usos? ___

---

## STT — sua voz, microfone Fifine (o que decide)

Uma única gravação de cada frase, pontuada por todos os modelos. Mesma tomada,
mesmas hesitações, mesmo ruído: é a comparação justa.

| | Motor | Modelo | WER | CER | RTF | Tamanho |
|---|---|---|---|---|---|---|
| | **faster-whisper** | **small / int8** | **9,0%** | **6,4%** | 0,43 | 464 MB |
| | faster-whisper | base / int8 | 24,7% | 7,6% | 0,14 | 145 MB |
| `[PT]` | wav2vec2 XLSR | large-pt | 29,4% | 16,0% | 0,18 | 1,2 GB |
| `[PT]` | Vosk | small-pt-0.3 | 37,2% | 33,0% | 0,37 | 50 MB |
| | faster-whisper | tiny / int8 | 45,6% | 24,7% | **0,12** | 75 MB |

**O `small` ganha, e ganha limpo.** Mas o número agregado esconde o que importa:
**todo o erro dele está nas duas frases que menos parecem um comando.**

| Frase | small |
|---|---|
| `curta` "Timer de dez minutos" | 0% |
| `pergunta` "acender a luz do quarto e baixar o volume" | 0% |
| `estrangeirismo` "playlist Discover Weekly no Spotify" | 0% |
| `acentos` "o avô do José põe açúcar" | 0% |
| `hora` "quinze para as sete" | 11,1% (comeu o "as") |
| `numeros` CEP e moeda | 25% |
| `longa` previsão do tempo | 26,7% |

Nas cinco frases que se parecem com o que você vai falar com o aparelho, o
`small` dá **2,2% de WER**. O `base`, nas mesmas cinco, dá 18,9% — erra
"Timer" ("Time-er"), erra "Toca" ("Taca"). Para um roteador que casa regex,
isso é a diferença entre acertar e não acionar.

**wav2vec2 confirmou o padrão previsto:** erra fonema, nunca frase. "Timer"
virou "taimer", "põe" virou "poeha" — sempre reconhecível, nunca inventado. E
o CER (16,0%) é metade do Vosk (33,0%) com WER parecido. Continua rodando sem
modelo de linguagem (`kenlm` não instala no Windows); com ele o número melhora.

**Vosk piorou na voz real** — 37,2% de WER, 33,0% de CER. Está fora.

**tiny está fora também:** 45,6% na voz real contra 31,7% no áudio sintético. É
o modelo que mais sofre com voz humana, exatamente o oposto do que se quer.

### A tensão que sobra

`small` acerta, mas RTF 0,43 no PC vira algo entre 1,3 e 2,2 na Pi 5 — acima do
tempo real, fora dos 200–500 ms da seção 11. `base` cabe com folga (RTF 0,14),
mas erra os comandos.

Três saídas, em ordem de preferência:

1. **whisper.cpp ou sherpa-onnx** com o mesmo `small`. São muito mais rápidos
   que o faster-whisper em ARM — é provável que isso resolva sozinho.
2. **`base` na Pi só para o roteador, `small` no gateway para o LLM.** Responde
   a pergunta que a decisão [D1](../docs/decisions.md) deixou em aberto: o nível
   0 só precisa casar "põe um timer", e para isso o `base` basta; a pergunta que
   vai para o LLM sobe como áudio e é transcrita direito no servidor.
3. **Aceitar o `small` na Pi** e gastar a latência, se as duas primeiras falharem.

Nenhuma decide sem medir na Pi. Mas já dá para comprar o hardware sabendo que o
software funciona.

---

## STT — áudio sintético (só para referência)

Ranqueia modelos entre si de forma barata, mas **não escolhe o vencedor**: o
mesmo `small` deu 4,1% no áudio do edge-tts, 17,6% no do Piper e 9,0% na sua
voz. Mede tanto a dicção do TTS quanto o ouvido do modelo.

| Motor | Modelo | WER (Piper) | CER | RTF |
|---|---|---|---|---|
| faster-whisper | small | 17,6% | 10,1% | 0,65 |
| faster-whisper | base | 28,3% | 14,7% | 0,21 |
| faster-whisper | tiny | 31,7% | 15,2% | 0,12 |
| wav2vec2 | large-pt | 32,6% | 16,6% | 0,24 |
| Vosk | small-pt | 33,1% | 26,0% | 0,42 |

Repetir sobre a sua voz:

```powershell
.\.venv\Scripts\python.exe -m lab.run_stt --engine faster-whisper --size tiny,base,small --source voice
.\.venv\Scripts\python.exe -m lab.run_stt --engine wav2vec2 --size large --source voice
```

`--source voice` pontua as gravações já feitas, sem regravar.

---

## Fila de testes

1. ~~Piper~~ · ~~MMS~~ · ~~whisper tiny/base/small~~ · ~~wav2vec2 pt~~ · ~~Vosk~~
2. ~~Gravar a voz real e refazer a varredura de STT~~ — **feito, o `small` ganhou**
3. **Ouvir Piper × MMS e escolher a voz** — a única escolha ainda em aberto
4. whisper.cpp / sherpa-onnx com o `small`: se forem rápidos o bastante em ARM,
   resolvem a tensão da seção acima sem concessão de qualidade
5. wav2vec2 com decoder kenlm, direto na Pi
6. Medir o vencedor com streaming, cronometrando o primeiro chunk
