"""Phase-0 stub: no real speech recognition yet.

The device in text mode encodes what you typed as UTF-8 and sends it through the
same binary channel real PCM will use, so the whole pipeline downstream of STT
is exercised for real. Swap this for a cloud API or faster-whisper without
touching anything outside this package.
"""

from __future__ import annotations

from typing import AsyncIterator


class TextPassthroughSTT:
    async def transcribe(self, audio: AsyncIterator[bytes]) -> str:
        chunks = [chunk async for chunk in audio]
        return b"".join(chunks).decode("utf-8", errors="replace").strip()
