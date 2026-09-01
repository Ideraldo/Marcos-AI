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
  router/        regex + embeddings intent matching
  local/         timers, alarms, reminders (SQLite + scheduler)
  stt/           faster-whisper: transcription happens before the wire (D1)
  tts/          Piper: the assistant's own voice, synthesised locally
  face/          web app served locally, state over WS
  ws_client.py   the single connection to the gateway
  state.py       state machine
gateway/     runs in Docker on localhost now, on a VPS later
  api/           WebSocket, token auth, the turn loop
  llm/           interface + swappable implementations
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
