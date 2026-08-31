# Resultados — STT e TTS

Registro vivo. Cada motor testado ganha uma linha; a coluna **Ouvido** é sua e
vale mais que as outras.

**Escopo fechado: só offline.** STT e TTS rodam na Pi, porque o roteador de
intenções trabalha sobre texto — sem STT local não existe nível 0, e nível 0 com
a internet caída é requisito. Para a VPS sobe só texto. O edge-tts fica no
arquivo apenas como teto de qualidade para comparação, não como candidato.

Medidas em: Windows 11, Python 3.12, CPU (sem GPU). Conjunto: as sete frases de
`lab/phrases.py`. **Na Pi 5, conte com 3 a 5 vezes esses tempos.**

---

## TTS

| Motor | Voz | Tipo | RTF | Carga | Tamanho | Ouvido |
|---|---|---|---|---|---|---|
| **Piper** | faber-medium | local | **0,05** | 2,7 s | 60 MB | *a preencher* |
| Piper | cadu-medium | local | — | — | 60 MB | *não testado* |
| Piper | jeff-medium | local | — | — | 60 MB | *não testado* |
| Piper | edresson-low | local | — | — | 60 MB | *não testado* |
| ~~edge-tts~~ | Francisca | nuvem | 0,62 | — | — | *só referência* |

**Piper faber-medium** — RTF 0,05, constante em todas as frases: sintetiza 20x
mais rápido que o tempo real. Carrega em 2,7 s uma única vez, no boot. Saída
nativa a 22050 Hz. Mesmo com a folga de 5x da Pi, fica muito abaixo dos
150–400 ms do orçamento da seção 11. **É o candidato.**

Contra o edge-tts: 12x mais rápido, sem rede, e sem o pico de 11,6 s que a
nuvem deu numa frase. O que falta é o seu ouvido decidir se a qualidade paga.

*Sua avaliação (por voz):* naturalidade ___/5 · prosódia de pergunta ___/5 ·
números e horas ___/5 · cansa depois de 10 usos? ___

---

## STT

Sobre áudio sintético do Piper — ver o alerta grande logo abaixo.

| Motor | Modelo | WER | CER | RTF | Tamanho |
|---|---|---|---|---|---|
| **faster-whisper** | small / int8 | **17,6%** | 10,1% | 0,65 | 464 MB |
| faster-whisper | base / int8 | 28,3% | 14,7% | **0,21** | 145 MB |
| faster-whisper | tiny / int8 | 31,7% | 15,2% | 0,12 | 75 MB |
| Vosk | small-pt-0.3 | 33,1% | 26,0% | 0,42 | 50 MB |

**A curva é clara:** cada degrau de tamanho compra acerto e custa tempo. `small`
erra metade do que `tiny` e leva 5x mais.

**Vosk perde nos dois eixos** — erra mais que o `base` e é o dobro mais lento
que ele. E erra de um jeito perigoso: "acender a luz do **quarto**" virou "luz do
**quadro**", e a frase do Spotify virou "eles descobriram que não se pode sair da
sala". O modelo pt-BR dele é de 2020 e mostra a idade. Continua interessante por
um motivo só: é o único nativamente streaming, que é o que um aparelho com wake
word realmente quer. Vale reavaliar se o modelo grande (1,6 GB) mudar o quadro.

### ⚠️ Estes números estão contaminados

O **mesmo** `faster-whisper small` deu **4,1% de WER no áudio do edge-tts** e
**17,6% no áudio do Piper**. O modelo não mudou — o material mudou. A voz do
Piper articula pior, e o STT come sílabas: "Timer" virou "Tame", "quarto" virou
"4".

Ou seja, esta tabela mede tanto a dicção do Piper quanto o ouvido do Whisper.
Serve para ranquear os modelos entre si, e serve como aviso de que o TTS local
tem custo de inteligibilidade. **Não serve para escolher o STT.**

O número que decide sai daqui:

```powershell
.\.venv\Scripts\python.exe -m lab.run_stt --engine faster-whisper --size tiny,base,small --record
```

---

## Fila de testes

1. ~~Piper (4 vozes baixadas)~~ · ~~faster-whisper tiny/base/small~~ · ~~Vosk~~ — falta seu ouvido e sua voz
2. **Gravar sua voz** e refazer a varredura de STT — é o que decide
3. Kokoro (local, alternativa citada no plano) como desafiante do Piper
4. whisper.cpp / sherpa-onnx — melhores em ARM que o faster-whisper
5. Medir o vencedor com streaming, cronometrando o primeiro chunk
