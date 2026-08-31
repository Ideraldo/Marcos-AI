"""Enrol voices and test whether the assistant can tell them apart.

    python -m lab.run_speaker enroll Ideraldo        # records 4 takes
    python -m lab.run_speaker enroll Mae --takes 5
    python -m lab.run_speaker who                    # records once and guesses
    python -m lab.run_speaker test                   # scores existing recordings
    python -m lab.run_speaker list

Enrolment takes about a minute per person and never needs repeating: adding
somebody later does not touch the voices already enrolled.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from lab.audio import record_until_silence, write_wav
from lab.devices import describe, ensure
from lab.speaker import SpeakerBook

OUT = Path(__file__).resolve().parent / "out" / "speaker"

#: Enrolment sentences. Varied on purpose -- a voice recorded saying one thing
#: in one tone gives a vector that only matches that tone.
ENROLL_PROMPTS = [
    "Bom dia, tudo bem com você?",
    "Põe um timer de cinco minutos, por favor.",
    "Não sei se hoje vai chover aqui em casa.",
    "Um, dois, três, quatro, cinco, seis, sete.",
    "Apaga a luz do quarto e toca uma música calma.",
]


def capture(prompt: str, path: Path, device: int | None) -> Path | None:
    print(f'\n  diga:  "{prompt}"')
    input("  ENTER e pode falar... ")
    pcm = record_until_silence(device=device)
    if not pcm:
        print("  nao ouvi nada")
        return None
    write_wav(path, pcm)
    print(f"  ok ({len(pcm) / 32000:.1f}s)")
    return path


def do_enroll(book: SpeakerBook, name: str, takes: int, device: int | None) -> None:
    folder = OUT / "enroll" / name.lower()
    recorded = []
    for index in range(takes):
        prompt = ENROLL_PROMPTS[index % len(ENROLL_PROMPTS)]
        path = capture(prompt, folder / f"{index}.wav", device)
        if path:
            recorded.append(path)

    if len(recorded) < 2:
        raise SystemExit("preciso de pelo menos 2 gravacoes")

    book.enroll(name, recorded)
    print(f"\n  {name} cadastrado com {len(recorded)} amostras")
    print(f"  vozes conhecidas: {', '.join(book.voices)}")


def do_who(book: SpeakerBook, device: int | None) -> None:
    if not book.voices:
        raise SystemExit("nenhuma voz cadastrada -- rode: python -m lab.run_speaker enroll <nome>")

    path = capture("fale qualquer coisa", OUT / "probe.wav", device)
    if not path:
        return

    name, score = book.identify(path)
    print(f"\n  => {name or 'DESCONHECIDO'}  (similaridade {score:.2f}, limiar {book.threshold})")
    print("\n  todos os candidatos:")
    for other, value in book.scores(path):
        print(f"    {other:<16} {value:.3f}")


def do_test(book: SpeakerBook) -> None:
    """Score every phrase already recorded in lab/out/voice."""
    folder = Path(__file__).resolve().parent / "out" / "voice"
    wavs = sorted(folder.glob("*.wav")) if folder.exists() else []
    if not wavs:
        raise SystemExit(f"nada em {folder}")

    print(f"\n  {len(wavs)} gravacoes em {folder.name}\n")
    for wav in wavs:
        name, score = book.identify(wav)
        print(f"    {wav.stem:<16} -> {name or 'DESCONHECIDO':<16} {score:.3f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="reconhecimento de locutor")
    parser.add_argument("action", choices=["enroll", "who", "test", "list", "forget"])
    parser.add_argument("name", nargs="?", help="nome, para enroll e forget")
    parser.add_argument("--takes", type=int, default=4, help="gravacoes por pessoa")
    parser.add_argument("--mic", help="microfone: indice ou parte do nome")
    parser.add_argument("--threshold", type=float, help="limiar de similaridade")
    args = parser.parse_args()

    book = SpeakerBook()
    if args.threshold:
        book.threshold = args.threshold

    if args.action == "list":
        print("\n  vozes cadastradas:", ", ".join(book.voices) or "(nenhuma)")
        return

    if args.action == "forget":
        if not args.name:
            raise SystemExit("forget precisa de um nome")
        book.forget(args.name)
        print(f"  {args.name} removido")
        return

    if args.action == "test":
        do_test(book)
        return

    device = ensure("input", args.mic)
    print(f"microfone: {describe(device)}")

    if args.action == "enroll":
        if not args.name:
            raise SystemExit("enroll precisa de um nome")
        do_enroll(book, args.name, args.takes, device)
    else:
        do_who(book, device)


if __name__ == "__main__":
    main()
