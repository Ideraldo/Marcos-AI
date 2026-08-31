"""WAV helpers for the lab: read, write, play, record.

The gateway speaks PCM 16 kHz mono (``common.messages``), so everything here
normalises to that -- an engine that only emits 24 kHz is resampled before it is
judged, otherwise you are comparing sample rates instead of voices.
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

from common.messages import CHANNELS, SAMPLE_RATE, SAMPLE_WIDTH


def write_wav(path: Path, pcm: bytes, rate: int = SAMPLE_RATE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(CHANNELS)
        handle.setsampwidth(SAMPLE_WIDTH)
        handle.setframerate(rate)
        handle.writeframes(pcm)


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as handle:
        rate = handle.getframerate()
        channels = handle.getnchannels()
        raw = handle.readframes(handle.getnframes())
    samples = np.frombuffer(raw, dtype=np.int16)
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1).astype(np.int16)
    return samples, rate


def resample(samples: np.ndarray, source_rate: int, target_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Linear resampling -- enough to compare engines, not a mastering chain."""
    if source_rate == target_rate:
        return samples
    count = int(len(samples) * target_rate / source_rate)
    positions = np.linspace(0, len(samples) - 1, count)
    return np.interp(positions, np.arange(len(samples)), samples).astype(np.int16)


def duration_seconds(path: Path) -> float:
    samples, rate = read_wav(path)
    return len(samples) / rate


def play(path: Path) -> None:
    import sounddevice as sd

    samples, rate = read_wav(path)
    sd.play(samples, rate)
    sd.wait()


def record(seconds: float, rate: int = SAMPLE_RATE) -> bytes:
    """Record from the default microphone. Used to judge STT on your own voice."""
    import sounddevice as sd

    frames = sd.rec(int(seconds * rate), samplerate=rate, channels=CHANNELS, dtype="int16")
    sd.wait()
    return frames.tobytes()
