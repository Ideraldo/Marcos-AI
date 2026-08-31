# Resultados — STT e TTS

Registro vivo. Cada motor testado ganha uma linha; a coluna **Ouvido** é sua e
vale mais que as outras.

Medidas em: Windows 11, Python 3.12, CPU (sem GPU). Áudio de teste: as sete
frases de `lab/phrases.py`.

---

## TTS

| Motor | Voz | Tipo | RTF médio | Ouvido | Veredito |
|---|---|---|---|---|---|
| edge-tts | Francisca | nuvem | 0,62 | *a preencher* | *a preencher* |
| edge-tts | Antonio | nuvem | — | *não testado* | |
| edge-tts | Thalita | nuvem | — | *não testado* | |
| Piper | faber-medium | local | — | *não instalado* | |
| Kokoro | — | local | — | *não instalado* | |

### Notas por motor

**edge-tts (Francisca)** — RTF 0,62 no conjunto todo. A primeira frase custou
2,6 s e `estrangeirismo` deu um pico de 11,6 s: é rede, não síntese, e é
exatamente o risco de depender da nuvem para falar. Precisa ser medido de novo
com streaming ligado, porque o número que importa é o primeiro chunk, não o
arquivo pronto.

*Sua avaliação:* naturalidade ___/5 · prosódia de pergunta ___/5 ·
números e horas ___/5 · cansa depois de 10 usos? ___

---

## STT

| Motor | Modelo | Tipo | WER | CER | RTF | Ouvido |
|---|---|---|---|---|---|---|
| faster-whisper | small / int8 | local | 4,1% | 2,6% | 0,61 | *áudio sintético* |
| faster-whisper | tiny | local | — | — | — | *não testado* |
| faster-whisper | base | local | — | — | — | *não testado* |
| faster-whisper | medium | local | — | — | — | *não testado* |
| Vosk | pt-br | local | — | — | — | *não instalado* |

### Notas por motor

**faster-whisper small/int8** — sobre áudio sintético do edge-tts, WER 4,1%.
Os dois erros restantes:

- `hora`: "para as sete" → "para 7", come o artigo. Cosmético.
- `numeros`: "CEP" → "CEPI" e quebra o número do CEP. Sequência longa de dígitos
  é o ponto fraco, o que importa pouco para comandos de quarto.

Primeira transcrição levou 5,2 s (modelo frio); as seguintes ficaram em ~2,7 s
para 3–4 s de áudio. **Ainda longe** dos 200–500 ms da seção 11 — mas isso é
áudio inteiro, não streaming, e o modelo ainda não foi medido nas variantes
menores.

⚠️ **Estes números são de áudio sintético, que é limpo demais.** Só valem para
ranquear modelos entre si. O número real sai de `--record`, com sua voz e o seu
ruído de quarto.

---

## Fila de testes

1. ~~edge-tts~~ · faster-whisper small — feito, falta seu ouvido
2. Piper (local, escolha do plano) — o candidato que roda na Pi
3. faster-whisper nos tamanhos tiny/base/medium — a curva custo × acerto
4. Kokoro (alternativa citada no plano) e Vosk (leve, offline)
5. Reteste do vencedor com streaming e medindo o primeiro chunk
