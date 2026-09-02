# Marcos-AI — portable voice assistant

Client-server voice assistant, built to replace a bedroom Alexa without giving
up portability.

- `docs/ultraplan-v3-assistente-voz-portatil.md` — the specification
- `docs/decisions.md` — where the build diverged from it, and why
- `docs/diario-de-bordo.md` — the narrative: doubts, attempts, what broke
- `lab/RESULTS.md` — measured numbers for every STT and TTS candidate
- `lab/docs/comandos.md` — every bench command and flag, in one place

## Layout

```
device/      runs on the PC now, on a Pi 5 later
  audio/         capture (mic + VAD), playback
  activation/    wake word, GPIO button, power-source detection
  router/        level-0 intent matching: regex + slot extraction
  local/         timers, alarms, the clock -- SQLite + scheduler, no network
  stt/           faster-whisper: transcription happens before the wire (D1)
  tts/          Piper: the assistant's own voice, synthesised locally
  face/          web app served locally, state over WS
  ws_client.py   the single connection to the gateway
  state.py       state machine
gateway/     runs with uvicorn today, in Docker on a VPS later
  api/           WebSocket, token auth, the turn loop
  llm/           interface + swappable implementations
  tools/         spotify, home_assistant, web_search
  conversation/  history and context assembly
  Dockerfile     gateway-only image; see requirements-gateway.txt (D15)
common/      shared message schemas -- the contract, never logic
lab/         bench for picking the STT and TTS engines (not production)
docs/        the plan, the structure guide, the decision log, the diary
.claude/     project skills: /documentar closes a work session
```

Two non-negotiables from the plan: **two separate processes from the first
commit**, and **alarms/timers always execute on the device**.

## Setup

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Every command below assumes the project root as the working directory.

## Phase 0 — the loop, end to end

Goal: mic -> STT -> LLM -> TTS round trip, two processes, WebSocket on localhost.
Accepted when 10 consecutive turns transcribe reliably in pt-BR.

**Wired end to end.** You speak; the mic records until the VAD hears you stop;
faster-whisper transcribes **on the device**; the gateway asks Ollama and streams
the answer back one sentence at a time; Piper speaks it with the owner's own
voice. No audio crosses the network in either direction -- only text (D1, D7,
D13). The acceptance criterion -- 10 consecutive turns transcribing reliably --
is the next thing to check with a real microphone.

```powershell
ollama serve                                            # or the Ollama app
.\.venv\Scripts\python.exe -m uvicorn gateway.main:app  # terminal 2
.\.venv\Scripts\python.exe -m device.main               # terminal 3
```

`--text` swaps the microphone for the keyboard and skips loading the STT: if the
answer is wrong with typed input, the problem is not the microphone. `--verbose`
prints what was heard and how long each stage took.

Pick the microphone with `AUDIO_INPUT_DEVICE` (a name fragment is enough) --
whatever Windows picked by default is often a headset that is not plugged in,
and a silent recording looks exactly like a broken model.

If the gateway goes away mid-conversation, the device does not: it reconnects
with growing backoff and goes back to listening (D14). What it does not get back
is the answer to that turn -- history lives in the gateway's session and dies
with the connection. A rejected token is the one failure that is not retried.

Swapping the LLM later touches one function, `build_llm` in `gateway/main.py`.

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Phase 1 -- the gateway in a container

Goal: containerised gateway, token auth, simulated link latency.
Accepted when `docker compose up` brings everything up.

Token auth and the simulated delay work today (`SIMULATED_LATENCY_MS` in `.env`;
80 is wifi, 150 is 4G). **The container is written but unverified**, and will
stay that way until the VPS: firmware virtualisation is off on this machine by
choice, so there is no WSL2 and no Docker Desktop (D16). The VPS runs Docker
Engine on Linux, where none of that applies. Treat the command below as
untested:

```powershell
docker compose -f gateway/docker-compose.yml up --build
python -m device.main      # unchanged: it still connects to ws://localhost:8000/ws
```

The image installs `requirements-gateway.txt`, not `requirements.txt`. After
D13 the gateway holds no model at all -- `gateway/` and `common/` import
fastapi, httpx, dotenv and the standard library -- so the full file would drag
torch, transformers and the whole bench into a container that never uses them
(D15). A new gateway dependency goes in that file, and only if `gateway/`
imports it.

Two things that only bite inside a container, both handled in the compose file:
`localhost` means the container itself, so `OLLAMA_URL` is overridden with
`host.docker.internal`; and that name only resolves on Docker Engine for Linux
-- the VPS case -- because of the `extra_hosts` line.

## Phase 2 -- what works with the internet down

Goal: local timers, alarms and reminders behind an intent router.
Accepted when a timer works with the gateway switched off.

**Done, and verified by running it.** The router looks at the sentence before
anything touches the network: if it is level 0 -- a timer, an alarm, the time,
"cancel", "what do I have" -- the device answers on its own, offline, with no
LLM. Anything it does not recognise goes up to the gateway (D17).

```powershell
# no gateway running at all
.\.venv\Scripts\python.exe -m device.main --text
```
```
gateway: fora do ar -- timer, alarme e hora continuam
voce:   marcos> Sao 20 horas e 2 minutos.   [nivel 0, local]
voce:   marcos> Timer de 5 segundos.        [nivel 0, local]
  marcos> Seu timer acabou.                 [timer]
```

Schedules live in SQLite (`SCHEDULES_DB`) because an alarm has to survive the
process -- the Pi reboots, and waking you up is the one job that cannot depend
on anything else being alive. One thing the router deliberately does **not** do
is guess: an unmatched sentence goes to the LLM, because a router that guesses
is worse than no router at all (plan section 5, rule 1).

Still missing from this phase, on purpose: embedding similarity for paraphrases
(waiting on a real level-2 log to say which paraphrases people actually use),
and volume control (OS mixer, platform-specific).

## Phase 3 -- tools (in progress)

Goal: tools on the gateway. Accepted when the LLM calls the right ones and does
not invent calls that do not exist.

**Done: the tools that run back on the device.** The gateway declares
`criar_timer`, `criar_alarme`, `listar_agendamentos` and `cancelar_agendamento`,
but executes none of them -- it carries the call to the device and waits for the
result. Execution lands in the same `device/local/` code the regex router
already used, so a sentence understood by the regex and one understood only by
the LLM end up identical (D18).

```
voce> me lembra de tirar o bolo quando der uma hora e meia
  [ferramenta criar_timer {'segundos': '5400'}]
marcos> Timer de 1 hora e meia.
```

A device tool's result **is** the answer: it is spoken as returned, with no
second LLM round. That started as a latency win (3.7s -> 2.1s) and turned out to
be a correctness fix -- asked to list two schedules, the model rewrote the list
and dropped one.

**The model had to change for this to work.** With tools declared, llama3.1:8b
stops answering general knowledge -- same prompt, same question, "Não sei" with
tools and "Canberra" without (D19). Measured across three candidates:

| | llama3.1:8b | qwen3:4b | qwen3:8b |
|---|---|---|---|
| Right tool | 4/5 | 5/5 | **5/5** |
| General knowledge | 0/7 | 3/7 | **6/7** |
| Median turn | **1.7s** | 5.5s | 2.8s |

`qwen3:8b` is the default now, with `LLM_THINK=false` (D20). Thinking is off
because qwen3 reasons by default, which costs latency and can leak: qwen3:4b
returned its draft as content, and on a voice assistant that means the device
**says** "Okay, the user is asking..." out loud. Run `ollama pull qwen3:8b`.

Still open: grounding. An 8B hallucinates -- it once attributed Dom Casmurro to
the wrong author. That is what web search is for, and it is next.

**Spotify: written, not verified.** Six music tools, and the first ones the
gateway executes itself rather than forwarding -- the client secret and refresh
token live on the server and never travel the wire (D21). Setup is one-time:

```powershell
# 1. https://developer.spotify.com/dashboard -> Create app
#    Redirect URI must be exactly http://127.0.0.1:8888/callback
#    (Spotify rejects "localhost"; 127.0.0.1 only)
# 2. Put the client id and secret in .env
# 3. Authorise once; the refresh token lands in gateway/data/ (gitignored)
.\.venv\Scripts\python.exe -m gateway.tools.spotify_auth
```

Playback control needs **Spotify Premium** -- the API answers 403 without it,
and the client turns that into a spoken sentence rather than a traceback.

With no credentials configured the music tools are **not declared to the model
at all**, and `/health` reports `"spotify": "off"`. That follows from D19: a
small model that sees an unavailable tool tries to use it anyway. What it does
instead is admit it cannot:

```
voce> toca chico buarque
marcos> Nao sei tocar Chico Buarque.
        Posso ajudar com timers, alarmes ou listar/agendar coisas?
```

**Verified against a real account.** The first real run found three things the
mocked tests could not: Spotify answers 403 both for "no Premium" and for
"command not valid right now", so the message no longer blames Premium blindly;
playing a bare track leaves a one-item queue, so a track now plays in its
**album context** and "skip" continues the record; and the model claimed to have
paused without calling the tool -- caused by history that recorded only the
spoken sentence, fixed in D22.

```
voce> toca construcao do chico buarque  -> Tocando Construcao, de Chico Buarque.
voce> que musica e essa                 -> Construcao, de Chico Buarque.
voce> pula essa                         -> Proxima.
voce> pausa a musica                    -> Pausado.
```

Home Assistant is out of scope -- one smart bulb does not justify Tailscale and
phase 5.

```powershell
ollama pull qwen3:8b     # once; the .env points at it
```

## Choosing STT and TTS

`lab/` is where engines are measured before becoming an implementation under
`gateway/` or `device/`. It ranks them on the same pt-BR phrase set, reports
RTF and WER/CER, and flags which models are Portuguese specialists.

```powershell
.\.venv\Scripts\python.exe -m lab.devices                           # pick mic and speaker
.\.venv\Scripts\python.exe -m lab.list                              # what is on the bench
.\.venv\Scripts\python.exe -m lab.run_tts --engine piper --play     # hear it
.\.venv\Scripts\python.exe -m lab.run_stt --engine faster-whisper --size tiny,base,small --record
```

Current standings and the open questions live in `lab/RESULTS.md`.

Speaker recognition (who is talking) and the path to a custom voice are covered
in `docs/voz-e-locutor.md`:

```powershell
.\.venv\Scripts\python.exe -m lab.run_speaker enroll Ideraldo
.\.venv\Scripts\python.exe -m lab.run_speaker who
```

## What comes next

**Phase 1's container is written but never executed** (D15), and its first real
run will be on the VPS (D16). Nothing else waits on it.

**Web search** -- the last piece of phase 3, and the one that matters most: it
is the answer to an 8B model that hallucinates (D20).

**Then: portable translator mode.** Speak Portuguese, have the device speak
English or Chinese, and the reverse. Two of the three pieces already exist --
Whisper is multilingual by nature, Piper has a voice per language -- so what is
missing is machine translation in the middle. The candidate is **opus-mt on
CTranslate2**, the same runtime `faster_whisper` already uses. NLLB-200 600M is
recorded as a quality ceiling and a **non-candidate on the device**: it is
autoregressive over 600M parameters on four ARM cores, which is what ruled out a
local LLM on day 1.

**The biggest open question is the hardware.** Every number so far was measured
on a PC. Nothing has run on a Pi yet -- not even Whisper -- and moving from the
bench to real device code already pushed RTF from 0.43 to 0.6-0.9.

The reasoning behind all of it is in `docs/diario-de-bordo.md`.
