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
  audio/         capture, playback, VAD, device selection
  activation/    wake word, GPIO button, power-source detection
  router/        regex + embeddings intent matching
  local/         timers, alarms, reminders (SQLite + scheduler)
  face/          web app served locally, state over WS
  ws_client.py   the single connection to the gateway
  state.py       state machine
gateway/     runs in Docker on localhost now, on a VPS later
  api/           WebSocket, token auth, the turn loop
  stt/ llm/ tts/ interface + swappable implementations
  tools/         spotify, home_assistant, web_search
  conversation/  history and context assembly
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

**Working today** in text mode: you type instead of speaking, and the line is
sent over the same binary channel that will carry PCM, so everything past the
microphone is the real path -- state machine, wire protocol, simulated link
delay. The LLM is real (Ollama, local); STT and TTS are stubs behind their
interfaces while `lab/` decides who replaces them.

```powershell
ollama serve                                            # or the Ollama app
.\.venv\Scripts\python.exe -m uvicorn gateway.main:app  # terminal 2
.\.venv\Scripts\python.exe -m device.main               # terminal 3
```

Swapping the LLM later touches one function, `build_llm` in `gateway/main.py`.

```powershell
.\.venv\Scripts\python.exe -m pytest
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
