"""Compare STT engines, on synthetic audio or on your own voice.

    # rank models cheaply against audio a TTS engine produced
    python -m lab.run_stt --engine faster-whisper --size tiny,base,small --source piper_faber_medium

    # the test that actually decides: your voice, your microphone, your room
    python -m lab.run_stt --engine faster-whisper --size small --record

Synthetic audio is clean and flatters every engine -- treat it as a smoke test.
The plan is explicit that the simulation does not validate a microphone in a
real room (section 2).
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from common.messages import SAMPLE_RATE
from lab.audio import duration_seconds, record, record_until_silence, write_wav
from lab.devices import describe, ensure
from lab.metrics import cer, wer
from lab.phrases import PHRASES, WARMUP
from lab.stt import ENGINES

OUT = Path(__file__).resolve().parent / "out"

Item = tuple[str, Path, str]


def available_sources() -> list[str]:
    directory = OUT / "tts"
    return sorted(p.name for p in directory.iterdir() if p.is_dir()) if directory.exists() else []


def collect_from_tts(source: str, keys: list[str]) -> list[Item]:
    directory = OUT / "tts" / source
    if not directory.exists():
        options = "\n  ".join(available_sources()) or "(nenhuma -- rode lab.run_tts primeiro)"
        raise SystemExit(f"nao encontrei {directory}\n\nfontes disponiveis:\n  {options}")
    return [
        (key, directory / f"{key}.wav", PHRASES[key])
        for key in keys
        if (directory / f"{key}.wav").exists()
    ]


def collect_from_mic(keys: list[str], seconds: float | None, device: int | None) -> list[Item]:
    """One take per phrase, stopping on its own when you stop talking."""
    import numpy as np

    items: list[Item] = []
    for key in keys:
        text = PHRASES[key]
        print(f'\n  [{key}] leia em voz alta:\n    "{text}"')
        input("  ENTER e pode falar... ")

        if seconds:
            print(f"  gravando {seconds:.0f}s...", flush=True)
            pcm = record(seconds, device=device)
        else:
            pcm = record_until_silence(device=device)
            if not pcm:
                print("  nao ouvi nada -- confira com: python -m lab.devices")
                continue

        samples = np.frombuffer(pcm, dtype=np.int16)
        peak = int(np.abs(samples).max()) if len(samples) else 0
        wav = OUT / "voice" / f"{key}.wav"
        write_wav(wav, pcm)
        print(f"  {len(samples) / SAMPLE_RATE:.1f}s, pico {peak / 32768:.0%}  ->  {wav.name}")
        if peak < 500:
            print("  SILENCIO -- microfone mudo ou dispositivo errado")
        items.append((key, wav, text))
    return items


def evaluate(engine, items: list[Item], verbose: bool) -> tuple[float, float, float]:
    """Return mean WER, mean CER and the overall real-time factor."""
    # Load the model on one phrase first: startup is paid once at boot, not per
    # utterance, and folding it into the first row makes every model look slow.
    started = time.perf_counter()
    engine.transcribe(items[0][1])
    load = time.perf_counter() - started
    print(f"  carga do modelo: {load:.2f}s")

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

        if verbose:
            flag = "ok " if w == 0 else "ERR"
            print(f"  [{flag}] {key:<16} WER {w:5.1%}  CER {c:5.1%}  RTF {elapsed / seconds:.2f}")
            if w:
                print(f"        esperado: {reference}")
                print(f"        ouviu:    {hypothesis}")

    n = len(items)
    return total_wer / n, total_cer / n, total_time / total_audio


def main() -> None:
    parser = argparse.ArgumentParser(description="STT bench")
    parser.add_argument("--engine", required=True, choices=sorted(ENGINES))
    parser.add_argument("--size", help="model size(s), comma separated")
    parser.add_argument("--source", default="piper_faber_medium", help="folder under lab/out/tts")
    parser.add_argument("--record", action="store_true", help="use your microphone instead")
    parser.add_argument("--phrase", default="all", help=f"{'|'.join(PHRASES)}|all")
    parser.add_argument(
        "--seconds",
        type=float,
        help="fixed recording length; omitted means stop when you stop talking",
    )
    parser.add_argument("--mic", help="microphone: index or part of the name (ex: fifine)")
    parser.add_argument("--pick", action="store_true", help="choose the microphone interactively")
    parser.add_argument("--quiet", action="store_true", help="only the summary line per model")
    args = parser.parse_args()

    keys = list(PHRASES) if args.phrase == "all" else [args.phrase]
    if WARMUP not in keys:
        keys = [WARMUP, *keys]

    if args.record:
        microphone = ensure("input", args.mic, ask=args.pick)
        print(f"\nmicrofone: {describe(microphone)}")
        items = collect_from_mic(keys, args.seconds, microphone)
    else:
        items = collect_from_tts(args.source, keys)
    if not items:
        raise SystemExit("nenhum audio para transcrever")

    sizes = args.size.split(",") if args.size else [None]
    origin = "microfone" if args.record else f"tts:{args.source}"
    print(f"\nfonte: {origin}   {len(items)} frases")

    results = []
    for size in sizes:
        engine = ENGINES[args.engine].factory(size)
        entry = ENGINES[args.engine]
        print(f"\n{entry.flag} {engine.name}  [{entry.kind}/{entry.lang}]")
        w, c, rtf = evaluate(engine, items, verbose=not args.quiet)
        results.append((engine.name, w, c, rtf))
        print(f"  media: WER {w:.1%}  CER {c:.1%}  RTF {rtf:.2f}")

    if len(results) > 1:
        print(f"\n{'modelo':<28} {'WER':>7} {'CER':>7} {'RTF':>7}")
        print("-" * 52)
        for name, w, c, rtf in sorted(results, key=lambda r: r[1]):
            print(f"{name:<28} {w:>6.1%} {c:>6.1%} {rtf:>7.2f}")

    print("\nanote em lab/RESULTS.md\n")


if __name__ == "__main__":
    main()
