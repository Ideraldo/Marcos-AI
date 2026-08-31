"""What an STT candidate must provide.

Mirrors ``gateway/stt/base.py`` in spirit, but takes a whole WAV instead of a
stream: judging accuracy does not need streaming, and every candidate can do
files. Streaming is a separate question, answered when one of these wins.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class STTCandidate(Protocol):
    name: str
    kind: str  # local | cloud
    setup: str

    def transcribe(self, wav: Path) -> str: ...
