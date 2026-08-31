# BMO — portable voice assistant

Client-server voice assistant. See `docs/ultraplan-v3-assistente-voz-portatil.md`
for the full specification.

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
  api/           WebSocket, token auth
  stt/ llm/ tts/ interface + swappable implementations
  tools/         spotify, home_assistant, web_search
  conversation/  history and context assembly
common/      shared message schemas
```

Two non-negotiables from the plan: **two separate processes from the first
commit**, and **alarms/timers always execute on the device**.

## Phase 0

Goal: mic -> STT -> LLM -> TTS round trip, two processes, WebSocket on localhost.
Accepted when 10 consecutive turns transcribe reliably in pt-BR.

What runs today: the full two-process loop in **text mode**. You type instead of
speaking; the line is sent over the same binary channel that will carry PCM, so
everything past the microphone is the real path. The LLM is real (Ollama,
locally); STT and TTS are stubs behind their interfaces.

```bash
cp .env.example .env
python -m venv .venv && .venv/Scripts/activate   # Windows
pip install -r requirements.txt

ollama serve                         # terminal 1 (or the Ollama app)
uvicorn gateway.main:app --reload    # terminal 2
python -m device.main                # terminal 3
```

Swapping the LLM later touches one function, `build_llm` in `gateway/main.py`.

```bash
pytest
```
