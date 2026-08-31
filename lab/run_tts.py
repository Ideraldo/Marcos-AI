"""Compare TTS engines on the fixed pt-BR phrase set.

    python -m lab.run_tts --engine edge
    python -m lab.run_tts --engine edge --voice pt-BR-AntonioNeural --play
    python -m lab.run_tts --engine piper --phrase hora --play

Writes lab/out/tts/<engine>/<phrase>.wav and prints the objective half of the
comparison. The other half is you listening -- write that down in lab/RESULTS.md.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from common.messages import SAMPLE_RATE
from lab.audio import play, resample, write_wav
from lab.phrases import PHRASES
from lab.tts import ENGINES

OUT = Path(__file__).resolve().parent / "out" / "tts"


def main() -> None:
    parser = argparse.ArgumentParser(description="TTS bench")
    parser.add_argument("--engine", required=True, choices=sorted(ENGINES))
    parser.add_argument("--voice", help="engine-specific voice/model id")
    parser.add_argument("--phrase", default="all", help=f"{'|'.join(PHRASES)}|all")
    parser.add_argument("--play", action="store_true", help="play each result")
    parser.add_argument(
        "--keep-rate",
        action="store_true",
        help="skip the downsample to 16 kHz (judge the engine's native quality)",
    )
    args = parser.parse_args()

    engine = ENGINES[args.engine](args.voice) if args.voice else ENGINES[args.engine]()
    keys = list(PHRASES) if args.phrase == "all" else [args.phrase]

    print(f"\n{engine.name}  [{engine.kind}]\n")
    print(f"{'frase':<16} {'sintese':>9} {'audio':>8} {'RTF':>6}  arquivo")
    print("-" * 74)

    total_synth = total_audio = 0.0
    for key in keys:
        text = PHRASES[key]
        started = time.perf_counter()
        samples, rate = engine.synthesize(text)
        elapsed = time.perf_counter() - started

        seconds = len(samples) / rate
        if not args.keep_rate:
            samples, rate = resample(samples, rate, SAMPLE_RATE), SAMPLE_RATE

        path = OUT / args.engine / f"{key}.wav"
        write_wav(path, samples.tobytes(), rate)

        total_synth += elapsed
        total_audio += seconds
        # RTF < 1 means it synthesises faster than real time -- the bar for a Pi.
        print(
            f"{key:<16} {elapsed:>8.2f}s {seconds:>7.2f}s "
            f"{elapsed / seconds:>6.2f}  {path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path}"
        )
        if args.play:
            print(f"   \"{text}\"")
            play(path)

    if len(keys) > 1:
        print("-" * 74)
        print(f"{'TOTAL':<16} {total_synth:>8.2f}s {total_audio:>7.2f}s {total_synth / total_audio:>6.2f}")
    print(f"\nagora ouca e anote em lab/RESULTS.md\n")


if __name__ == "__main__":
    main()
