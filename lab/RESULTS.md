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

## STT

Sobre áudio sintético do Piper — ver o alerta grande logo abaixo.

| | Motor | Modelo | WER | CER | RTF | Tamanho |
|---|---|---|---|---|---|---|
| | **faster-whisper** | small / int8 | **17,6%** | **10,1%** | 0,65 | 464 MB |
| | faster-whisper | base / int8 | 28,3% | 14,7% | 0,21 | 145 MB |
| | faster-whisper | tiny / int8 | 31,7% | 15,2% | **0,12** | 75 MB |
| `[PT]` | wav2vec2 XLSR | large-pt | 32,6% | 16,6% | 0,24 | 1,2 GB |
| `[PT]` | Vosk | small-pt-0.3 | 33,1% | 26,0% | 0,42 | 50 MB |

**A curva do Whisper é clara:** cada degrau compra acerto e custa tempo. `small`
erra metade do que `tiny` e leva 5x mais.

**wav2vec2 é o especialista interessante.** O WER parece ruim, mas olhe o CER:
16,6% contra 26,0% do Vosk com WER quase igual. Ele erra *fonemas*, não frases —
"acordar" virou "acudar", "três graus" virou "têis galos". Nunca inventa uma
frase fluente que não foi dita, porque não tem decoder de linguagem tentando
adivinhar a próxima palavra. Para um roteador que casa regex e embeddings, errar
uma letra é bem menos grave que o Whisper alucinar uma frase inteira e plausível.

E é **2,7x mais rápido que o Whisper small** com precisão de caractere parecida.

> Rodou sem modelo de linguagem: o `kenlm` não está instalado, então caiu para
> CTC puro. Com o decoder de LM esse número melhora bastante. Compilar kenlm no
> Windows é briga; vale tentar direto na Pi, onde é mais fácil.

**Vosk perde nos dois eixos** — erra mais que o `base` e é o dobro mais lento.
E erra perigoso: "acender a luz do **quarto**" virou "luz do **quadro**". O
modelo pt dele é de 2020 e mostra a idade. Continua na lista por um motivo só:
é o único nativamente streaming, que é o que um aparelho com wake word quer.

### ⚠️ Estes números estão contaminados

O **mesmo** `faster-whisper small` deu **4,1% de WER no áudio do edge-tts** e
**17,6% no áudio do Piper**. O modelo não mudou — o material mudou. A voz do
Piper articula pior, e o STT come sílabas: "Timer" virou "Tame", "quarto" virou
"4".

Esta tabela mede tanto a dicção do Piper quanto o ouvido de cada modelo. Serve
para ranquear os modelos entre si e como aviso de que o TTS local custa
inteligibilidade. **Não serve para escolher o STT.**

O número que decide sai daqui:

```powershell
.\.venv\Scripts\python.exe -m lab.run_stt --engine faster-whisper --size tiny,base,small --record
.\.venv\Scripts\python.exe -m lab.run_stt --engine wav2vec2 --size large --record
```

---

## Fila de testes

1. ~~Piper~~ · ~~MMS~~ · ~~faster-whisper tiny/base/small~~ · ~~wav2vec2 pt~~ · ~~Vosk~~
2. **Gravar sua voz** e refazer a varredura de STT — é o que decide
3. Ouvir Piper × MMS lado a lado e escolher a voz
4. wav2vec2 com decoder kenlm, direto na Pi
5. whisper.cpp / sherpa-onnx — melhores em ARM que o faster-whisper
6. Medir o vencedor com streaming, cronometrando o primeiro chunk
