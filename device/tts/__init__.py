"""Device-side speech synthesis. Nothing outside this package knows the engine."""

from device.tts.base import TextToSpeech
from device.tts.piper_voice import PiperVoiceEngine

__all__ = ["TextToSpeech", "PiperVoiceEngine"]
