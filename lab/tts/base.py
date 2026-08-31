"""What a TTS candidate must provide to be comparable.

Same shape as ``gateway/tts/base.py`` on purpose: whatever wins here can move
into the gateway as an implementation of ``TextToSpeech`` without a rewrite.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np


class TTSCandidate(Protocol):
    #: Shown in the results table.
    name: str
    #: local | cloud -- decides whether it can speak with the internet down.
    kind: str
    #: What to install/download before it runs.
    setup: str

    def synthesize(self, text: str) -> tuple[np.ndarray, int]:
        """Return int16 mono samples and their sample rate."""
        ...
