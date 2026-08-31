# Ultraplan v3 — Assistente de Voz Portátil ("BMO")

**Plano final.** Documento de especificação, escrito para ser lido inteiro no início do desenvolvimento. Substitui as versões 1 e 2.

> Este documento registra o que se sabia quando foi escrito e **não é reescrito**.
> As decisões que divergiram dele durante a construção estão em
> [decisions.md](decisions.md) — notadamente **D1**, que move STT e TTS do
> gateway para o dispositivo.

---

## 0. Resumo executivo

Assistente de voz pessoal para substituir a Alexa do quarto, com portabilidade mantida como requisito. Arquitetura cliente-servidor: hardware portátil captura áudio e exibe interface; gateway em VPS orquestra STT, LLM e ferramentas externas.

**Decisões fechadas:**

| Decisão | Escolha |
|---|---|
| Portabilidade | Requisito, não opcional |
| Gateway | VPS (não há máquina 24h em casa) |
| Alarme, timer, lembrete | No escopo, executados **localmente** no dispositivo |
| Ativação | Wake word na tomada, botão na bateria, troca automática |
| LLM | Híbrido: modelo pequeno classifica, API responde |
| Ordem de desenvolvimento | Tudo local no PC → VPS → hardware |

**Requisitos funcionais principais:** conversa geral, busca na internet com resposta fundamentada, interpretação de imagens, alarmes e timers, controle de música (Spotify) e casa (Home Assistant).

---

## 1. Arquitetura

```
┌──────────────────────── DISPOSITIVO (Pi 5) ─────────────────────────┐
│                                                                     │
│  Ativação:  wake word (na tomada)  |  botão (na bateria)           │
│      │                                                              │
│      ▼                                                              │
│  ROTEADOR DE INTENÇÕES  ──── casou? ────> executa local            │
│      │                                    (timer, alarme, volume)   │
│      │ não casou                                                    │
│      ▼                                                              │
│  streaming de áudio ─────────────────────┐                          │
│                                          │                          │
│  Serviços locais: agenda de alarmes, SQLite, rosto (Chromium)       │
└──────────────────────────────────────────┼──────────────────────────┘
                                           │ WebSocket / TLS
                                           │ (Wi-Fi em casa, 4G na rua)
┌──────────────────────────────────────────▼──────────────────────────┐
│                    GATEWAY (VPS, São Paulo)                         │
│                                                                     │
│   STT  →  CLASSIFICADOR  →  [ MÓDULO LLM ]  →  TTS                  │
│           (modelo pequeno,    interface fixa,                       │
│            CPU, prompt curto)  implementação trocável               │
│                                ├── API (padrão)                     │
│                                └── Ollama local (futuro, exige GPU) │
│                                                                     │
│   Ferramentas · Segredos · Histórico de conversa                    │
└───────┬──────────────────────────────────────────┬──────────────────┘
        ▼                                          ▼
   Spotify Web API                    Home Assistant (via Tailscale)
```

**Regra de ouro:** o dispositivo só conhece um endpoint — o gateway. Nenhuma chave de API viaja num aparelho que sai de casa.

**Máquina de estados do dispositivo** (é isso que a animação do rosto reflete):

```
IDLE ──wake/botão──> LISTENING ──fim de fala (VAD)──> THINKING
  ▲                      │                               │
  │                      └──timeout──> IDLE              ▼
  └──────────fim do áudio───────────── SPEAKING <── streaming TTS
                                          │
                                     (barge-in: wake word durante
                                      SPEAKING → corta e volta a LISTENING)
```

---

## 2. Estratégia de desenvolvimento: local primeiro

Todo o sistema é construído e validado no computador pessoal antes de qualquer compra. O gateway roda em Docker no localhost; o "dispositivo" é um processo separado usando o microfone e o alto-falante do PC.

### Cinco regras que tornam a migração barata

1. **Dois processos desde o primeiro commit.** `dispositivo/` e `gateway/` conversam por WebSocket em `localhost`. Migrar = trocar a URL. Chamada de função direta entre as duas partes é proibida.
2. **Gateway em Docker desde o início.** Deploy na VPS vira `docker compose up`, não uma tarde de reinstalação.
3. **Latência de rede simulada.** Atraso artificial configurável no cliente (~80 ms Wi-Fi, ~150 ms 4G). Sem isso você projeta em cima de uma latência que nunca vai existir.
4. **O lado do dispositivo precisa caber num Pi 5.** Seu PC é muito mais rápido. Na dúvida sobre onde colocar um processamento, empurre para o gateway.
5. **Áudio e display abstraídos por configuração.** Dispositivo de entrada, de saída e modo de exibição em variáveis de ambiente. PC tem P2 e navegador em janela; Pi não tem P2 e roda kiosk.

### O que a simulação NÃO valida

Qualidade do microfone no ambiente real, taxa de falso positivo do wake word com o hardware final, autonomia de bateria e comportamento do 4G. Fase local verde significa **software validado**, não **projeto validado**.

### Ordem de compra

**VPS antes do hardware.** Custa poucos dólares por mês, é cancelável, e entrega o número de latência real Brasil → gateway → LLM que decide se a experiência é aceitável. Hardware é dinheiro que não volta.

---

## 3. Estrutura do repositório

```
bmo/
├── dispositivo/
│   ├── audio/           captura, playback, VAD, seleção de device
│   ├── ativacao/        wake word, botão GPIO, detecção de energia
│   ├── roteador/        regex + embeddings, casamento de intenções
│   ├── local/           timers, alarmes, lembretes (SQLite + scheduler)
│   ├── rosto/           app web servida localmente, estado via WS
│   ├── cliente_ws.py    conexão única com o gateway
│   └── estado.py        máquina de estados
├── gateway/
│   ├── api/             WebSocket, autenticação por token
│   ├── stt/             interface + implementações
│   ├── llm/             interface ProvedorLLM + implementações
│   ├── tts/             interface + cache de frases fixas
│   ├── ferramentas/     spotify, home_assistant, busca_web
│   ├── conversa/        histórico e montagem de contexto
│   └── docker-compose.yml
├── comum/               esquemas de mensagem compartilhados
└── docs/                este plano
```

Cada camada com interface externa (`stt`, `llm`, `tts`) é um Protocol com implementações intercambiáveis. Nada fora do módulo sabe qual está ativa.

---

## 4. Protocolo dispositivo ↔ gateway

WebSocket único, mensagens JSON para controle e frames binários para áudio. Streaming nas duas direções desde o início — bufferizar tudo dobra a latência percebida e é caro consertar depois.

```jsonc
// dispositivo → gateway
{"type": "session_start", "device_id": "bmo-01", "token": "..."}
// ... frames binários: PCM 16 kHz, 16-bit, mono ...
{"type": "audio_end"}
{"type": "tool_result", "id": "...", "ok": true}   // resultado de ação local

// gateway → dispositivo
{"type": "state", "value": "thinking"}
{"type": "transcript", "text": "..."}              // para exibir na tela
{"type": "tool_call", "name": "criar_alarme", "args": {...}}
// ... frames binários de áudio TTS ...
{"type": "state", "value": "idle"}
```

Note o `tool_call` de volta para o dispositivo: quando o LLM interpreta "me acorda às 7", quem grava e dispara é o Pi, não o gateway.

---

## 5. Roteador de intenções

A maior parte do que se pede a uma assistente de quarto é repetitiva e determinística. Mandar isso ao LLM custa latência, token e um ponto de falha.

### Três níveis

| Nível | Resolve | Rede? | LLM? | Latência alvo |
|---|---|---|---|---|
| **0 — Local puro** | timer, alarme, lembrete, hora, volume, "para", "cancela" | Não | Não | < 200 ms |
| **1 — Rede, sem LLM** | luzes e cenas (HA), play/pause/próxima (Spotify) | Sim | Não | < 600 ms |
| **2 — LLM** | conversa, busca na internet, imagens, comandos ambíguos | Sim | Sim | < 1,5 s |

Nível 0 é o que garante que o despertador toca com a internet caída. É requisito, não otimização.

### Técnicas de casamento

**Regex com extração de slots** para formatos rígidos — durações, horários, números:
```
/^(põe|coloca|bota|liga) um timer de (\d+) (segundos?|minutos?|horas?)$/
   → criar_timer(duracao=10, unidade="minutos")
```

**Similaridade por embeddings** para o resto: 5–10 frases de exemplo por intenção, vetores pré-calculados, comparação por cosseno na hora. Cobre paráfrases que regex não pega ("me acorda daqui a 10 minutos", "conta 10 minutos pra mim"). Modelo multilíngue pequeno, milissegundos na CPU do Pi.

**Motor de intenções do Home Assistant** para dispositivos da casa. Já traz templates em português e conhece as suas entidades. Não reimplemente.

### As quatro regras

1. **Na dúvida, manda pro LLM.** Só age com confiança alta (similaridade acima do limiar E todos os slots preenchidos). Roteador que chuta é pior que roteador nenhum — "apaga a luz da sala" virando "apaga tudo" destrói a confiança no aparelho.
2. **Respostas fixas usam áudio pré-gerado.** "Timer de 10 minutos." não passa por TTS toda vez. Sintetize uma vez, guarde em disco. É isso que faz o aparelho parecer instantâneo.
3. **A execução é sempre local**, venha a intenção de onde vier. O gateway nunca é responsável por te acordar.
4. **Toda falha vira dado.** Registre as frases que caíram no nível 2 e qual ferramenta o LLM acabou chamando. Em um mês esse log diz exatamente quais intenções promover ao nível 0 — o LLM é o professor do roteador.

---

## 6. Estratégia de LLM

### O que ficou descartado, e por quê

**Modelo local no Pi com acelerador.** O AI HAT+ 2 (Hailo-10H, 40 TOPS, 8 GB próprios, ~US$130) existe e funciona, mas os modelos suportados são da faixa de 1 a 1,5 bilhão de parâmetros — Llama 3.2 1B, Qwen 2.5 1.5B, DeepSeek R1 1.5B, a 20–50 tokens/s. Rápidos e limitados demais para busca fundamentada.

**Modelo local na VPS sem GPU.** Duas barreiras. A geração já é lenta (referência: Llama 3.1 8B Q4 em EPYC bare-metal de 32 núcleos entrega ~14 tok/s, e uma VPS comum tem 8 vCPU compartilhadas). Pior que isso é o *prompt processing*: digerir 6–8 mil tokens de resultados de busca na CPU leva dezenas de segundos antes da primeira palavra. Inviável para voz.

**GPU na nuvem 24/7.** A partir de ~US$200/mês, contra poucos dólares mensais de API em uso pessoal. Só reavalie se privacidade virar requisito real — e aí o STT também precisa ser local.

### O desenho escolhido

Modelo pequeno **classifica**, modelo grande **responde**. Classificação usa prompt curto e saída de poucos tokens, exatamente onde CPU se sai bem. Busca fundamentada, síntese e visão vão para a API.

Interface única no gateway:

```python
class ProvedorLLM(Protocol):
    async def responder(
        self,
        historico: list[Mensagem],
        ferramentas: list[Ferramenta],
    ) -> AsyncIterator[Delta]:  # streaming de texto e chamadas de ferramenta
        ...
```

**Modelo inicial:** `deepseek-v4-flash`. Para imagens existe variante com suporte a visão na mesma família. Confirme os IDs e preços na documentação oficial antes de codar — os aliases antigos `deepseek-chat` e `deepseek-reasoner` foram aposentados em julho de 2026.

**Regra de custo:** system prompt estável e no início da requisição. O cache de prefixo pesa mais na conta final que a escolha do modelo.

---

## 7. Ativação dupla por detecção de energia

| Estado | Ativação | Justificativa |
|---|---|---|
| Na tomada | Wake word contínuo (+ botão como reserva) | Sem custo de bateria |
| Na bateria | Só botão, tela apaga em `IDLE`, CPU limitada | Wake word always-on é o maior consumidor ocioso |

**Como detectar:** módulos UPS decentes expõem o estado da alimentação por sinal *power-good* num pino GPIO ou por medidor de carga no I²C. **Confirme isso antes de comprar o módulo de bateria** — é um critério que quase ninguém verifica e que decide se essa funcionalidade existe.

Anuncie a troca de modo na interface. Um aparelho que "para de ouvir" sem avisar parece quebrado.

---

## 8. Hardware

### Correções sobre a lista original

| Item | Situação |
|---|---|
| Saída P2 | **Não existe no Pi 5** (removida para dar lugar ao PCIe). Use speakerphone USB, placa de som USB ou DAC I2S |
| Microfone | Speakerphone USB com AEC resolve entrada, saída e eco de uma vez — crítico para wake word |
| Display | Confirmar se é DSI (Pi 5 usa FPC de **22 pinos**, não 15) ou HDMI+USB touch |
| Empilhamento | No máximo **um HAT**. Bateria, modem e áudio disputam o mesmo GPIO |
| Fonte | Oficial 27W. Genéricas causam limitação de corrente USB |
| Botão | Momentâneo no GPIO. R$ 5, resolve o modo bateria |
| Cartão SD | Compre dois: um estável, um de experimentos |
| Módulo UPS | Precisa expor estado da alimentação (ver seção 7) |
| Conectividade | Comece com hotspot do celular. Modem 4G só na Fase 7 |

### Energia

Pi 5 ocioso ~3 W, sob carga 7–10 W; display 2–3 W; modem em pico 1–2 W. Com 2×18650 (~20 Wh úteis), espere **2 a 3 horas** reais. Meça com medidor USB antes de fechar o gabinete.

Se não bastar: desligar wake word na bateria, apagar tela em `IDLE`, limitar frequência da CPU, ou pack de 4×18650.

---

## 9. Stack

| Camada | Escolha |
|---|---|
| SO | Raspberry Pi OS Bookworm 64-bit (PipeWire; não instale PulseAudio junto) |
| Agente | Python, serviço systemd com restart automático |
| Wake word | openWakeWord, modelo ONNX treinado com sua voz (150–200 gravações) |
| VAD | webrtcvad ou Silero |
| Roteador | regex + embeddings multilíngues, CPU |
| Persistência local | SQLite (alarmes, timers, lembretes, cache de TTS) |
| Agendador | APScheduler ou timers do systemd |
| Rosto | HTML/CSS/JS em Chromium kiosk, estado via WebSocket local |
| Gateway | FastAPI + WebSocket, Docker, VPS em São Paulo |
| STT | API de nuvem (trocável por faster-whisper) |
| LLM | `deepseek-v4-flash` atrás da interface `ProvedorLLM` |
| TTS | Piper ou TTS de nuvem; frases fixas pré-geradas em cache |
| Rede privada | Tailscale entre VPS e Home Assistant |

Sobre TTS: Piper foi arquivado em outubro de 2025 mas continua funcional; Kokoro é a alternativa mais citada para projetos novos.

---

## 10. Roadmap

### Etapa A — Local (computador pessoal, sem comprar nada)

| Fase | Entrega | Critério de aceite |
|---|---|---|
| **0** | Loop completo: mic → STT → LLM → TTS, dois processos, WebSocket em localhost | 10 turnos seguidos com transcrição confiável em PT-BR |
| **1** | Gateway containerizado, autenticação por token, latência simulada | `docker compose up` sobe tudo; atraso configurável funcionando |
| **2** | Serviços locais: timer, alarme, lembrete + roteador de intenções | Timer funciona com o gateway desligado |
| **3** | Ferramentas no gateway: busca web, Spotify, Home Assistant | LLM chama as ferramentas certas e não inventa chamadas inexistentes |
| **4** | Rosto: app web com os quatro estados animados | Sem travar durante o áudio |

### Etapa B — VPS

| Fase | Entrega | Critério de aceite |
|---|---|---|
| **5** | Deploy do gateway na VPS, TLS, Tailscale até o Home Assistant | Latência real medida e dentro do orçamento da seção 11 |

### Etapa C — Hardware

| Fase | Entrega | Critério de aceite |
|---|---|---|
| **6** | Pi 5 rodando o lado dispositivo: áudio, botão, display, rosto | Aperta, fala, ouve, e o rosto reage |
| **7** | Wake word + barge-in | < 1 falso positivo/hora; dá para interromper a fala |
| **8** | Mobilidade: bateria, detecção de energia, modem, gabinete | 2h fora de casa, troca de modo automática, reconecta sozinho |

A Fase 2 vem antes do rosto e do wake word de propósito: alarme e timer são o núcleo da substituição da Alexa e a única parte que precisa sobreviver a uma queda de internet.

---

## 11. Orçamento de latência

Meta: **abaixo de 1,5 s** entre o fim da fala e o início do áudio. Acima de ~2,5 s deixa de parecer conversa.

| Etapa | Alvo |
|---|---|
| Detecção de fim de fala (VAD) | 200–300 ms |
| Upload do áudio | 100–300 ms |
| STT | 200–500 ms |
| LLM até o primeiro token | 300–800 ms |
| TTS até o primeiro chunk | 150–400 ms |

Estimativas de projeto, não medições. Instrumente cada etapa com timestamps desde a Fase 0 e trate isso como métrica de produto.

Dois maiores ganhos: **streaming de TTS** (falar antes de o LLM terminar) e **resolver o nível 0 sem sair do dispositivo**.

---

## 12. Custos e consumo

**Dados por interação:** PCM 16 kHz mono ≈ 32 KB/s. Pergunta de 5 s ≈ 160 KB, resposta comprimida ≈ 30–60 KB. Cerca de **0,25 MB por interação** — 100 por dia dão ~25 MB. Irrelevante.

**O vilão é a música.** Streaming de áudio pelo 4G consome mais que a assistente inteira. Se o Spotify tocar no dispositivo fora de casa, o plano de dados vira o custo dominante.

**Fixos mensais:** VPS + chip de dados + Spotify Premium (exigido tanto pela Web API quanto pelo librespot). O hardware é gasto único.

---

## 13. Riscos

| Risco | Mitigação |
|---|---|
| Wake word disparando sozinho | Speakerphone com AEC; palavra incomum; ajuste de threshold |
| Roteador interpretando errado | Limiar de confiança alto; na dúvida, LLM |
| Undervoltage com bateria + periféricos | Medir antes de montar; desenvolver sempre na fonte |
| Módulo UPS não expor estado da alimentação | **Verificar antes de comprar** |
| Endpoints do Spotify alterados | Validar na doc atual (houve remoção em fev/2026); fallback para librespot |
| Conflito físico entre HATs | Um HAT só; resto por USB |
| Latência real acima do orçamento | Medida na Fase 5, antes de qualquer compra de hardware |
| Travar na estética do gabinete | v1 feia e funcional; caixa bonita depois |

---

## 14. Como usar este documento

Ele é a especificação do projeto, não um tutorial. A ordem de leitura para começar a codar: seção 1 (arquitetura), seção 3 (estrutura), seção 4 (protocolo), depois a Fase 0 da seção 10.

Duas coisas que não devem ser negociadas durante a implementação, porque consertar depois é reescrita: **os dois processos separados desde o começo** e **a execução local de alarmes e timers**.
