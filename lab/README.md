# lab — bancada de testes de STT e TTS

Não roda em produção. É onde os motores são medidos antes de virarem uma
implementação de verdade. Pela decisão [D1](../docs/decisions.md), o vencedor de
cada lado vai morar no `device/`, não no `gateway/`: o roteador de intenções
precisa de texto para classificar, então o STT tem que existir na Pi para o
nível 0 funcionar com a internet caída.

O plano deixa STT e TTS em aberto ("API de nuvem, trocável por faster-whisper";
"Piper ou TTS de nuvem"). Esta pasta existe para fechar essas duas escolhas com
número e com ouvido, não com opinião.

```
lab/
  phrases.py     as frases de teste — a constante de toda comparação
  run_tts.py     sintetiza o conjunto e mede tempo e RTF
  run_stt.py     transcreve e pontua com WER/CER
  tts/  stt/     um arquivo por motor candidato
  registry.py    quais motores existem e a flag [PT]
  list.py        python -m lab.list -- mostra a bancada inteira
  metrics.py     normalização + WER/CER
  numbers.py     "10" e "dez" precisam pontuar igual
  devices.py     escolha de microfone e alto-falante, guardada em .devices.json
  audio.py       wav, playback, gravação com fim de fala automático (VAD)
  out/           áudio gerado (fora do git)
  models/        modelos baixados (fora do git)
  RESULTS.md     o veredito — preencha depois de ouvir
```

## Como usar

Sempre a partir da raiz do projeto (o `-m` já coloca a raiz no `sys.path`;
não precisa de `PYTHONPATH`). Nos exemplos, `py` é `.\.venv\Scripts\python.exe`.

```powershell
# 0. o que esta na bancada, com a flag [PT]
py -m lab.list

# 1. gerar e ouvir — toca cada frase e mostra o texto antes
py -m lab.run_tts --engine edge --play
py -m lab.run_tts --engine edge --voice pt-BR-AntonioNeural --play
py -m lab.run_tts --engine edge --phrase hora --play        # só uma frase

# 2. transcrever o que foi gerado (barato, ranqueia modelos entre si)
py -m lab.run_stt --engine faster-whisper --size small --source edge
py -m lab.run_stt --engine faster-whisper --size tiny --source edge

# 3. o teste que vale: sua voz, seu microfone, seu quarto
#    (escolha o microfone antes com: py -m lab.devices)
py -m lab.run_stt --engine faster-whisper --size small --record

# 4. repontuar as gravacoes ja feitas, sem regravar
py -m lab.run_stt --engine wav2vec2 --size large --source voice
```

## Escolher microfone e alto-falante

O dispositivo padrão do Windows raramente é o que você quer — se for um headset
desligado, a gravação sai muda e parece que o modelo é que falhou. Escolha uma
vez e fica guardado em `lab/.devices.json`:

```powershell
py -m lab.devices
```

Ele lista os dispositivos, salva a escolha e faz um teste de 3 segundos dizendo
se o microfone está mudo, saturado ou ok.

Depois disso todo runner usa o que foi salvo. Para desviar pontualmente:

```powershell
py -m lab.run_stt --engine faster-whisper --record --mic fifine   # por nome
py -m lab.run_stt --engine faster-whisper --record --mic 2        # por índice
py -m lab.run_stt --engine faster-whisper --record --pick         # escolher agora
py -m lab.run_tts --engine piper --play --speaker "Fone"
```

## Gravação que para sozinha

Por padrão a gravação termina quando você para de falar — 900 ms de silêncio
encerram a frase. Duração fixa erra nos dois sentidos: corta a frase longa e
enche a curta de ruído de sala, e é justamente esse ruído que faz o modelo
alucinar palavras que ninguém disse.

Usa o `webrtcvad`, o mesmo que vai rodar na Pi, com um portão de energia por
cima: os primeiros 300 ms medem o ruído de fundo e um quadro só conta como fala
se o VAD concordar **e** o som estiver acima desse piso. Sem isso, um condensador
sensível como o Fifine faz o VAD tratar o ruído da sala como voz e a gravação
nunca começa.

Se quiser o comportamento antigo, `--seconds 8` volta a gravar por tempo fixo.

## Como ler os números

**RTF** (real-time factor) = tempo de processamento ÷ duração do áudio.
Abaixo de 1 significa mais rápido que tempo real. No PC isso é folgado; a
pergunta que importa é se sobra margem para a Pi 5, que é bem mais lenta.

**WER/CER** = taxa de erro por palavra e por caractere. A normalização ignora
maiúsculas, acentos, pontuação e a diferença entre `10` e `dez` — nada disso
muda o que o assistente entende. Um WER que sobra depois disso é erro de
verdade.

**O que os números não dizem:** se a voz é agradável de ouvir dez vezes por dia,
se a prosódia de pergunta soa natural, se o áudio sintético engana o STT de um
jeito que a sua voz não engana. Por isso o `RESULTS.md` tem coluna subjetiva.

## Regra de aceite

Um motor só entra no gateway se couber no orçamento da seção 11 do plano:
**STT em 200–500 ms** e **TTS até o primeiro chunk em 150–400 ms**. Note que o
que importa no TTS é o *primeiro chunk*, não o áudio inteiro — falar antes de
terminar de gerar é um dos dois maiores ganhos de latência do projeto.

## A flag `[PT]`

`python -m lab.list` marca com `[PT]` os modelos **especializados em português**
— treinados ou ajustados só nele — contra os multilíngues, que apenas suportam
pt entre dezenas de idiomas.

A distinção importa por dois motivos. Um especialista costuma entregar a mesma
precisão num modelo bem menor, e tamanho é o que decide o que cabe na Pi. E ele
não tem para onde escapar: não vai tentar decidir se você falou espanhol, o que
é exatamente o comportamento certo para um aparelho que só ouve pt-BR.

O que ele perde é robustez fora do idioma — um nome próprio em inglês no meio da
frase ("Discover Weekly") tende a sair pior. Por isso os dois grupos convivem na
bancada em vez de um substituir o outro.
