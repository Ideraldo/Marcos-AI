# Reconhecer quem fala, e falar com uma voz própria

Duas perguntas que parecem uma só e não são. Nenhuma das duas se resolve
"treinando o STT" — o Whisper transforma áudio em palavras e joga fora tudo que
sobra, inclusive a identidade de quem falou.

---

## 1. Saber quem está falando

### Não é treino, é cadastro

O modelo usado (`speechbrain/spkrec-ecapa-voxceleb`, ECAPA-TDNN, ~80 MB) mapeia
alguns segundos de fala num vetor de 192 números. Vetores da mesma pessoa ficam
próximos; de pessoas diferentes, distantes. Comparar duas vozes é calcular o
cosseno entre dois vetores — uma multiplicação, microssegundos.

Isso muda tudo na prática: **cadastrar alguém é gravar quatro frases**, não
treinar nada. Sua mãe entra depois sem tocar no que já existe, e nada precisa ser
reprocessado.

Foi treinado em VoxCeleb, majoritariamente inglês, e funciona igual em português
— ele aprende timbre, não idioma.

### Medido neste projeto

Com as sete gravações da bancada:

| Comparação | Similaridade |
|---|---|
| Sua voz × sua própria média | **0,69 a 1,00** |
| Sua voz × Piper faber | 0,21 (máx 0,24) |
| Sua voz × edge Francisca | 0,24 (máx 0,26) |
| Sua voz × MMS | 0,02 (máx 0,08) |

A separação é enorme: o pior caso seu (0,69) está muito acima do melhor caso de
um impostor (0,26). O limiar ficou em **0,45**, no meio do vazio entre os dois
grupos.

### Como usar

```powershell
py -m lab.run_speaker enroll Ideraldo    # grava 4 frases variadas
py -m lab.run_speaker enroll Mae
py -m lab.run_speaker who                # grava uma e adivinha
py -m lab.run_speaker test               # pontua as gravações já feitas
py -m lab.run_speaker list
```

O `who` imprime a pontuação de todos os cadastrados, não só o vencedor — é assim
que se ajusta o limiar com dados em vez de palpite.

Responder **"desconhecido"** importa tanto quanto acertar o nome. Um aparelho que
chama um estranho pelo seu nome é pior que um que admite não saber.

### O que dá para fazer com isso

Perfis por pessoa (seus alarmes não são os da sua mãe), histórico de conversa
separado, e comandos restritos a quem tem permissão. Só não confunda com
segurança: um vetor de voz é reconhecimento, não autenticação — grava-se uma voz
com um celular.

Nada disso está integrado ao `device/` ainda. A bancada só responde se funciona.

---

## 2. Voz própria no TTS

Aqui há dois caminhos, e a diferença entre eles é o que roda na Pi.

### Clonagem zero-shot (XTTS-v2, F5-TTS)

Você dá 6 a 30 segundos da sua voz e o modelo fala com ela, sem treino. É
impressionante e imediato.

O problema é o tamanho: são modelos de 1,5 a 2 GB que precisam de GPU para
chegar perto do tempo real. Numa Pi 5 não roda — RTF muito acima de 1.

**Mas há um uso legítimo dele mesmo assim.** A regra 2 da seção 5 do plano diz
que frases fixas devem ser pré-geradas e guardadas em disco: "Timer de dez
minutos", "Alarme criado", "Não entendi". Essas podem ser sintetizadas **uma vez
no PC**, com a sua voz clonada, e copiadas para a Pi como arquivos. Não custa
nada em tempo de execução.

O que não dá é usar clonagem para uma resposta livre do LLM, que só existe na
hora.

### Fine-tune do Piper (a resposta de verdade)

Partindo de um checkpoint pt-BR e treinando com **30 a 60 minutos** da sua voz
gravada, sai um modelo Piper de 60 MB com o seu timbre, rodando em RTF 0,05 na
Pi. É o único caminho que entrega voz personalizada **e** velocidade.

Custo: gravar meia hora de fala limpa e transcrita, mais algumas horas de GPU. A
RTX 2060 de 6 GB dá conta.

### Estado atual

Você reprovou os dois primeiros candidatos — o Piper soa arrastado, o MMS soa
robótico. Foi por isso que o **Kokoro** entrou (StyleTTS2, 82M, três vozes pt-BR),
e as outras três vozes do Piper foram geradas para comparação.

Se nenhuma agradar, o fine-tune deixa de ser luxo e vira o caminho — e nesse caso
a meia hora de gravação serve para as duas coisas, porque as mesmas amostras
também alimentam o wake word (o plano já pede 150–200 gravações na seção 9).
