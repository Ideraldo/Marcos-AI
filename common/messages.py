"""Device <-> gateway wire protocol (plan section 4).

Single source of truth: neither side defines messages on its own.
Control travels as JSON; audio travels as binary frames (PCM 16 kHz, 16-bit, mono).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

# Audio format agreed by both ends.
SAMPLE_RATE = 16_000
CHANNELS = 1
SAMPLE_WIDTH = 2  # bytes (16-bit)


class State(str, Enum):
    """Device state machine (plan section 1)."""

    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"


# ---------- device -> gateway ----------


@dataclass
class SessionStart:
    device_id: str
    token: str
    type: Literal["session_start"] = "session_start"


@dataclass
class AudioEnd:
    type: Literal["audio_end"] = "audio_end"


@dataclass
class ToolResult:
    id: str
    ok: bool
    error: str | None = None
    type: Literal["tool_result"] = "tool_result"


# ---------- gateway -> device ----------


@dataclass
class StateMessage:
    value: State
    type: Literal["state"] = "state"


@dataclass
class Transcript:
    text: str
    final: bool = True
    type: Literal["transcript"] = "transcript"


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict[str, Any] = field(default_factory=dict)
    type: Literal["tool_call"] = "tool_call"
