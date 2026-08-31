"""Ollama provider: a model running locally, no API key and no network.

Good enough to build the whole pipeline against. The plan's target is a cloud
model behind this same interface (section 6) -- when that arrives, only
``build_provider`` changes.
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx

from gateway.llm.base import Delta, Message, Tool


class OllamaProvider:
    def __init__(self, base_url: str, model: str, timeout: float = 120.0) -> None:
        self._url = base_url.rstrip("/") + "/api/chat"
        self._model = model
        self._timeout = timeout

    async def respond(
        self,
        history: list[Message],
        tools: list[Tool],
    ) -> AsyncIterator[Delta]:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in history],
            "stream": True,
        }
        if tools:
            payload["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description,
                        "parameters": t.parameters,
                    },
                }
                for t in tools
            ]

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream("POST", self._url, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.strip():
                        continue
                    chunk = json.loads(line)
                    if chunk.get("error"):
                        raise RuntimeError(f"ollama: {chunk['error']}")

                    message = chunk.get("message") or {}
                    for call in message.get("tool_calls") or []:
                        function = call.get("function") or {}
                        args = function.get("arguments") or {}
                        if isinstance(args, str):
                            args = json.loads(args)
                        yield Delta(tool_name=function.get("name"), tool_args=args)

                    text = message.get("content")
                    if text:
                        yield Delta(text=text)

                    if chunk.get("done"):
                        break
