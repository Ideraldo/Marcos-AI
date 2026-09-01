"""Compare TTS engines on the fixed pt-BR phrase set.

    python -m lab.run_tts --engine piper
    python -m lab.run_tts --engine piper --voice pt_BR-cadu-medium --play
    python -m lab.run_tts --engine piper --phrase hora --play

Writes lab/out/tts/<engine_voice>/<phrase>.wav and prints the objective half of
the comparison. The other half is you listening -- write that down in RESULTS.md.
"""

from __future__ import annotations

import argparse
import re
import time
from pathlib import Path

from common.messages import SAMPLE_RATE
from lab.audio import play, resample, write_wav
from lab.devices import describe, ensure
from lab.phrases import PHRASES, WARMUP
from lab.tts import ENGINES

OUT = Path(__file__).resolve().parent / "out" / "tts"


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def main() -> None:
    parser = argparse.ArgumentParser(description="TTS bench")
    parser.add_argument("--engine", required=True, choices=sorted(ENGINES))
    parser.add_argument("--voice", help="engine-specific voice/model id")
    parser.add_argument("--phrase", default="all", help=f"{'|'.join(PHRASES)}|all")
    parser.add_argument(
        "--text",
        help="falar um texto qualquer em vez do conjunto fixo (use aspas)",
    )
    parser.add_argument("--play", action="store_true", help="play each result")
    parser.add_argument("--speaker", help="output device: index or part of the name")
    parser.add_argument("--pick", action="store_true", help="choose the speaker interactively")
    parser.add_argument(
        "--keep-rate",
        action="store_true",
        help="skip the downsample to 16 kHz (judge the engine's native quality)",
    )
    args = parser.parse_args()

    entry = ENGINES[args.engine]
    engine = entry.factory(args.voice)

    speaker = None
    if args.play:
        speaker = ensure("output", args.speaker, ask=args.pick)
        print(f"\nalto-falante: {describe(speaker)}")
    # Texto livre entra como se fosse mais uma frase do conjunto: o resto do
    # runner nao precisa saber a diferenca. Serve para ouvir a voz em algo que
    # ela nunca treinou -- duas das sete frases fixas estao no corpus do
    # fine-tune, entao elas sozinhas lisonjeiam um modelo que decorou.
    phrases = dict(PHRASES)
    if args.text:
        phrases = {"texto": args.text}
        keys = ["texto"]
    else:
        keys = list(PHRASES) if args.phrase == "all" else [args.phrase]

    # Load the model on a throwaway phrase. Otherwise the first row carries the
    # startup cost and looks like the engine is slow -- on the Pi the model is
    # loaded once at boot and never again.
    started = time.perf_counter()
    engine.synthesize(PHRASES[WARMUP])
    load = time.perf_counter() - started

    print(f"\n{entry.flag} {engine.name}  [{engine.kind}/{entry.lang}]   carga: {load:.2f}s\n")
    print(f"{'frase':<16} {'sintese':>9} {'audio':>8} {'RTF':>6}  arquivo")
    print("-" * 74)

    directory = OUT / slug(engine.name)
    total_synth = total_audio = 0.0
    for key in keys:
        text = phrases[key]
        started = time.perf_counter()
        samples, rate = engine.synthesize(text)
        elapsed = time.perf_counter() - started

        seconds = len(samples) / rate
        native_rate = rate
        if not args.keep_rate:
            samples, rate = resample(samples, rate, SAMPLE_RATE), SAMPLE_RATE

        path = directory / f"{key}.wav"
        write_wav(path, samples.tobytes(), rate)

        total_synth += elapsed
        total_audio += seconds
        # RTF < 1 means faster than real time. On a Pi 5, budget roughly 3-5x
        # this number -- that is the only figure that decides anything.
        print(f"{key:<16} {elapsed:>8.2f}s {seconds:>7.2f}s {elapsed / seconds:>6.2f}  {path}")
        if args.play:
            print(f'   "{text}"')
            play(path, device=speaker)

    if len(keys) > 1:
        print("-" * 74)
        print(
            f"{'TOTAL':<16} {total_synth:>8.2f}s {total_audio:>7.2f}s "
            f"{total_synth / total_audio:>6.2f}   ({native_rate} Hz nativo)"
        )
    print(f"\nsaida: {directory}\nanote o que ouviu em lab/RESULTS.md\n")


if __name__ == "__main__":
    main()
