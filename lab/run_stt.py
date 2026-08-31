"""Compare STT engines, on synthetic audio or on your own voice.

    # transcribe what a TTS engine produced, scored against the known text
    python -m lab.run_stt --engine faster-whisper --size small --source edge

    # the test that actually matters: your voice, your microphone, your room
    python -m lab.run_stt --engine faster-whisper --size small --record

Synthetic audio is clean and flatters every engine -- treat it as a smoke test
and a way to rank models cheaply. The plan is explicit that the simulation does
not validate the microphone in a real room (section 2).
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from lab.audio import duration_seconds, record, write_wav
from lab.metrics import cer, wer
from lab.phrases import PHRASES
from lab.stt import ENGINES

OUT = Path(__file__).resolve().parent / "out"


def collect_from_tts(source: str) -> list[tuple[str, Path, str]]:
    directory = OUT / "tts" / source
    if not directory.exists():
        raise SystemExit(f"nada em {directory} -- rode primeiro: python -m lab.run_tts --engine {source}")
    items = []
    for key, text in PHRASES.items():
        wav = directory / f"{key}.wav"
        if wav.exists():
            items.append((key, wav, text))
    return items


def collect_from_mic(keys: list[str], seconds: float) -> list[tuple[str, Path, str]]:
    items = []
    for key in keys:
        text = PHRASES[key]
        print(f"\n  [{key}] leia em voz alta:\n    \"{text}\"")
        input("  ENTER para gravar... ")
        print(f"  gravando {seconds:.0f}s...", flush=True)
        pcm = record(seconds)
        wav = OUT / "voice" / f"{key}.wav"
        write_wav(wav, pcm)
        print(f"  salvo em {wav}")
        items.append((key, wav, text))
    return items


def main() -> None:
    parser = argparse.ArgumentParser(description="STT bench")
    parser.add_argument("--engine", required=True, choices=sorted(ENGINES))
    parser.add_argument("--size", help="model size, engine-specific")
    parser.add_argument("--source", default="edge", help="TTS engine whose output to transcribe")
    parser.add_argument("--record", action="store_true", help="use your microphone instead")
    parser.add_argument("--phrase", default="all", help=f"{'|'.join(PHRASES)}|all")
    parser.add_argument("--seconds", type=float, default=8.0, help="recording length")
    args = parser.parse_args()

    keys = list(PHRASES) if args.phrase == "all" else [args.phrase]
    items = collect_from_mic(keys, args.seconds) if args.record else [
        item for item in collect_from_tts(args.source) if item[0] in keys
    ]

    engine = ENGINES[args.engine](args.size) if args.size else ENGINES[args.engine]()
    origin = "microfone" if args.record else f"tts:{args.source}"
    print(f"\n{engine.name}  [{engine.kind}]  fonte: {origin}")
    print("  (a primeira execucao baixa o modelo)\n")

    total_wer = total_cer = total_time = total_audio = 0.0
    for key, wav, reference in items:
        started = time.perf_counter()
        hypothesis = engine.transcribe(wav)
        elapsed = time.perf_counter() - started
        seconds = duration_seconds(wav)

        w, c = wer(reference, hypothesis), cer(reference, hypothesis)
        total_wer += w
        total_cer += c
        total_time += elapsed
        total_audio += seconds

        flag = "ok " if w == 0 else "ERR"
        print(f"[{flag}] {key}  WER {w:5.1%}  CER {c:5.1%}  {elapsed:.2f}s  (RTF {elapsed / seconds:.2f})")
        if w:
            print(f"        esperado: {reference}")
            print(f"        ouviu:    {hypothesis}")

    n = len(items)
    if n:
        print(
            f"\nmedia: WER {total_wer / n:.1%}  CER {total_cer / n:.1%}  "
            f"RTF {total_time / total_audio:.2f}  ({n} frases)"
        )
    print("\nanote em lab/RESULTS.md\n")


if __name__ == "__main__":
    main()
