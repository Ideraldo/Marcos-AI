# v1 — o treino que decorou

Primeira tentativa de fine-tune, guardada para o vídeo. **Descartada por
overfitting**, não por bug: o pipeline funcionou, o dataset é que era pequeno.

- **Base:** `pt_BR-dii-high`
- **Dataset:** 203 frases, 15,2 minutos
- **Parou em:** época ~368, 14.828 passos
- **Motivo do descarte:** ver [D5](../../../../docs/decisions.md) e o
  [Dia 3 do diário](../../../../docs/diario-de-bordo.md)

## As gerações guardadas

| Arquivo | Época | O que dá para ouvir |
|---|---|---|
| `v1-ep113.onnx` | 113 | timbre já reconhecível, bem robótico |
| `v1-ep247.onnx` | 247 | — |
| `v1-ep292.onnx` | 292 | — |
| `v1-ep318.onnx` | 318 | os mesmos defeitos da 113; foi aqui que percebi |
| `v1-ep330.onnx` | 330 | — |
| `v1-ep361.onnx` | 361 | o melhor `val_mel` do run (0,4199) |

**As épocas 0, 50, 100, 150 e 200 não existem.** O `ModelCheckpoint` do Lightning
guarda apenas os melhores e apaga os antigos conforme treina — quando fui
arquivar, a mais antiga que restava era a 247. A 113 só sobreviveu porque eu
tinha exportado o `.onnx` na hora, para ouvir.

*Lição, se for repetir: exportar `.onnx` a cada N épocas durante o treino. São 60
MB contra 845 MB de um checkpoint, e é o único formato que se ouve.*

## Como ouvir

Copie a voz que quiser para `lab/models/piper/` com o nome no formato que a
bancada espera:

```powershell
Copy-Item lab\finetune\arquivo\v1-decorou\v1-ep318.onnx      lab\models\piper\pt_BR-v1ep318-medium.onnx
Copy-Item lab\finetune\arquivo\v1-decorou\v1-ep318.onnx.json lab\models\piper\pt_BR-v1ep318-medium.onnx.json

.\.venv\Scripts\python.exe -m lab.run_tts --engine piper --voice pt_BR-v1ep318-medium --play
```

Para comparar com a voz nova depois de retreinar, as duas ficam na bancada ao
mesmo tempo e leem as mesmas sete frases.

## Os números que condenaram este treino

| | Época 113 | Época 318 |
|---|---|---|
| WER no corpus (frases treinadas) | 26,3% | **11,3%** |
| WER em texto novo (holdout) | 39,2% | **39,7%** |
| Distância | +12,8% | **+28,4%** |

A base `dii-high` faz 22,9% no mesmo holdout. O corpus melhorou muito, o texto
novo não saiu do lugar: o modelo estava decorando as 203 frases em vez de
aprender a falar.

Reproduzir a medição:

```powershell
.\.venv\Scripts\python.exe -m lab.finetune.generalize --voice pt_BR-v1ep318-medium --against pt_BR-dii-high
```

> O VITS tem amostragem estocástica: a mesma época mediu 39,2% numa rodada e
> 34,4% noutra. Espere ±5 pontos de variação.

## O que foi apagado

Os checkpoints `.ckpt` (8,7 GB, 845 MB cada). Não vale guardar: o `.onnx` é o que
se ouve, e retreinar do zero com o dataset maior é o caminho de qualquer forma.

O dataset de gravações **não** foi apagado — ele continua em
`lab/finetune/dataset/` e é a base do v2, com o bloco 3 somado por cima.
