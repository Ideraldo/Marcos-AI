"""Gateway process entrypoint: uvicorn gateway.main:app"""

from __future__ import annotations

# TODO(phase-0): FastAPI app exposing /ws -- token auth, STT -> LLM -> TTS,
# with per-stage timestamps from day one (plan section 11).
