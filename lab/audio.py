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


def play(path: Path, device: int | None = None) -> None:
    import sounddevice as sd

    samples, rate = read_wav(path)
    sd.play(samples, rate, device=device)
    sd.wait()


def record(seconds: float, device: int | None = None, rate: int = SAMPLE_RATE) -> bytes:
    """Record a fixed length. Prefer ``record_until_silence`` for real phrases."""
    import sounddevice as sd

    frames = sd.rec(
        int(seconds * rate), samplerate=rate, channels=CHANNELS, dtype="int16", device=device
    )
    sd.wait()
    return frames.tobytes()


def record_until_silence(
    device: int | None = None,
    silence_ms: int = 900,
    max_seconds: float = 30.0,
    start_timeout: float = 20.0,
    aggressiveness: int = 3,
) -> bytes:
    """Record until you stop talking, using the same VAD the device will use.

    A fixed duration is wrong in both directions -- it clips a long sentence and
    pads a short one with room noise, and that padding is what makes an engine
    hallucinate words nobody said. webrtcvad works on 10/20/30 ms frames of
    16 kHz mono, exactly the format the whole project speaks.

    webrtcvad alone is not enough: on a sensitive condenser mic it calls the
    room tone speech and the recording never starts. So the first 300 ms measure
    the noise floor, and a frame only counts as speech when the VAD says so *and*
    it is meaningfully louder than that floor.

    ``silence_ms`` is the knob the plan budgets 200-300 ms for in a real turn
    (section 11); it is longer here because reading a written phrase aloud has
    pauses that a spoken command does not.
    """
    import numpy as np
    import sounddevice as sd
    import webrtcvad

    frame_ms = 30
    frame_samples = int(SAMPLE_RATE * frame_ms / 1000)
    needed_silence = silence_ms // frame_ms
    needed_speech = 3  # consecutive speech frames before we commit
    calibration_frames = 10
    # Keep audio from just before the trigger: the first consonant lands ahead
    # of the first voiced frame and cutting it costs a whole word.
    preroll: list[bytes] = [b""] * (300 // frame_ms)

    vad = webrtcvad.Vad(aggressiveness)
    collected: list[bytes] = []
    voiced = silent = 0
    started = False
    elapsed = 0.0
    floor = 0.0
    threshold = 0.0

    def rms(frame: bytes) -> float:
        samples = np.frombuffer(frame, dtype=np.int16).astype(np.float32)
        return float(np.sqrt(np.mean(samples**2))) if len(samples) else 0.0

    with sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        blocksize=frame_samples,
        device=device,
        dtype="int16",
        channels=CHANNELS,
    ) as stream:
        for index in range(calibration_frames):
            frame, _ = stream.read(frame_samples)
            floor += rms(bytes(frame)) / calibration_frames
        # Four times the noise floor, but never so low that hum passes for a
        # voice, nor so high that a quiet speaker is ignored.
        threshold = min(max(floor * 4, 250.0), 1500.0)

        while True:
            frame, _ = stream.read(frame_samples)
            frame = bytes(frame)
            elapsed += frame_ms / 1000
            loud = rms(frame) > threshold

            if vad.is_speech(frame, SAMPLE_RATE) and loud:
                voiced += 1
                silent = 0
            else:
                silent += 1
                voiced = 0

            if not started:
                preroll.append(frame)
                preroll.pop(0)
                if voiced >= needed_speech:
                    started = True
                    collected.extend(f for f in preroll if f)
                    print("  ouvindo...", flush=True)
                elif elapsed > start_timeout:
                    return b""
                continue

            collected.append(frame)
            if silent >= needed_silence or elapsed > max_seconds:
                break

    return b"".join(collected)
