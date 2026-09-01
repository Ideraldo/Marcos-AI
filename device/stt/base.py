"""Speech-to-text interface, on the device side.

Mirrors ``device/tts/base.py``: depois da decisão D1 a transcrição também roda
aqui, porque o roteador de intenções decide sobre *texto* e precisa funcionar com
a internet caída. Pela rede sobe a frase pronta, nunca o PCM.

Toma o áudio inteiro de uma vez, não um fluxo: o VAD já decidiu onde a fala
terminou, e o `faster-whisper` transcreve o arquivo fechado de qualquer jeito.
Streaming é outra pergunta, para quando o orçamento da Pi exigir.
"""

from __future__ import annotations

from typing import Protocol


class SpeechToText(Protocol):
    #: Como aparece no log e no diário; inclui tamanho e quantização.
    name: str

    def transcribe(self, pcm: bytes) -> str:
        """Recebe PCM 16 kHz mono int16 e devolve o que foi dito."""
        ...
