"""Encoding/decoding of control messages as JSON."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any


def encode(message: Any) -> str:
    if not is_dataclass(message):
        raise TypeError(f"expected a message dataclass, got {type(message)!r}")
    return json.dumps(asdict(message), ensure_ascii=False)


def decode(raw: str) -> dict[str, Any]:
    payload = json.loads(raw)
    if "type" not in payload:
        raise ValueError("message has no 'type' field")
    return payload
