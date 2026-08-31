"""Record the dataset that will teach Piper your voice.

    python -m lab.finetune.record              # continues where you stopped
    python -m lab.finetune.record --review 12  # listen to and redo one take
    python -m lab.finetune.record --redo 1-10  # drop a range and record it again
    python -m lab.finetune.record --reset      # start the dataset over
    python -m lab.finetune.record --status

Produces the layout piper.train expects:

    lab/finetune/dataset/
      wav/0001.wav ...        22050 Hz mono, the rate the base voice trains at
      metadata.csv            id|texto

Recording is captured at 48 kHz -- the highest rate the VAD accepts -- and
band-limited down to 22050, because a dataset carries every artefact into the
model that learns from it.

Advice that matters more than any setting: one session, one distance from the
microphone, one mood. The model copies your pace and your energy, so a tired
second half gives a voice that sounds tired half the time.
"""

from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path

import numpy as np

from lab.audio import play, read_wav, record_until_silence, resample_hq, write_wav
from lab.devices import describe, ensure
from lab.finetune.corpus import SENTENCES

ROOT = Path(__file__).resolve().parent / "dataset"
WAVS = ROOT / "wav"
METADATA = ROOT / "metadata.csv"

CAPTURE_RATE = 48_000  # what the VAD accepts
TARGET_RATE = 22_050  # what the piper medium/high voices train at


def take_path(index: int) -> Path:
    return WAVS / f"{index:04d}.wav"


def done() -> set[int]:
    return {int(p.stem) for p in WAVS.glob("*.wav")} if WAVS.exists() else set()


def write_metadata() -> int:
    """Rebuild metadata.csv from whatever is on disk, so it can never drift."""
    recorded = sorted(done())
    METADATA.parent.mkdir(parents=True, exist_ok=True)
    with METADATA.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="|", quoting=csv.QUOTE_NONE, escapechar="\\")
        for index in recorded:
            writer.writerow([f"{index:04d}", SENTENCES[index - 1]])
    return len(recorded)


def capture(index: int, device: int | None) -> bool:
    text = SENTENCES[index - 1]
    print(f"\n  [{index:>3}/{len(SENTENCES)}]  {text}")
    answer = input("  ENTER para gravar, 'p' para pular, 'q' para sair: ").strip().lower()
    if answer == "q":
        return False
    if answer == "p":
        return True

    pcm = record_until_silence(device=device, rate=CAPTURE_RATE, silence_ms=700)
    if not pcm:
        print("  nao ouvi nada -- repetindo")
        return capture(index, device)

    samples = np.frombuffer(pcm, dtype=np.int16)
    peak = int(np.abs(samples).max())
    seconds = len(samples) / CAPTURE_RATE

    if peak < 1500:
        print(f"  BAIXO DEMAIS (pico {peak / 32768:.0%}) -- aproxime-se e repita")
        return capture(index, device)
    if peak > 32000:
        print(f"  SATURADO (pico {peak / 32768:.0%}) -- abaixe o ganho e repita")
        return capture(index, device)

    write_wav(take_path(index), resample_hq(samples, CAPTURE_RATE, TARGET_RATE).tobytes(), TARGET_RATE)
    print(f"  ok  {seconds:.1f}s  pico {peak / 32768:.0%}")
    return True


def reset() -> None:
    """Throw the dataset away and start over.

    Confirmed out loud because the recordings are the expensive part: a wrong
    keystroke here costs an hour of reading, not a re-run of a script.
    """
    recorded = done()
    if not recorded:
        print("\n  nada gravado ainda.")
        return

    seconds = sum(len(read_wav(take_path(i))[0]) / TARGET_RATE for i in recorded)
    print(f"\n  isso apaga {len(recorded)} gravacoes ({seconds / 60:.1f} min) em {WAVS}")
    if input("  digite APAGAR para confirmar: ").strip() != "APAGAR":
        print("  cancelado.")
        return

    shutil.rmtree(ROOT)
    print("  dataset apagado. pode comecar de novo.")


def redo(spec: str) -> None:
    """Delete specific phrases so the next run records them again.

    Accepts "7", "1-10", or "2,7,15" -- the last is what `lab.finetune.check`
    prints when it finds bad takes, so its output pastes straight back in.

    Cheaper than --reset when only some takes went wrong: everything that was
    already good stays.
    """
    wanted: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            first, last = (int(bound) for bound in part.split("-", 1))
            wanted.update(range(first, last + 1))
        else:
            wanted.add(int(part))

    removed = 0
    for index in sorted(wanted):
        path = take_path(index)
        if path.exists():
            path.unlink()
            removed += 1

    write_metadata()
    print(f"\n  {removed} gravacoes apagadas. Rode de novo para regravar.")

def status() -> None:
    recorded = done()
    seconds = sum(len(read_wav(take_path(i))[0]) / TARGET_RATE for i in recorded)
    print(f"\n  {len(recorded)} de {len(SENTENCES)} frases gravadas")
    print(f"  {seconds / 60:.1f} minutos de audio")
    if seconds < 600:
        print("  ainda pouco: mire em pelo menos 15 min para um timbre convincente")
    missing = [i for i in range(1, len(SENTENCES) + 1) if i not in recorded]
    if missing:
        print(f"  faltam: {missing[:12]}{' ...' if len(missing) > 12 else ''}")


def review(index: int, device: int | None, speaker: int | None) -> None:
    path = take_path(index)
    if not path.exists():
        raise SystemExit(f"{path} nao existe")
    print(f'\n  [{index}] "{SENTENCES[index - 1]}"')
    play(path, device=speaker)
    if input("  regravar? (s/N): ").strip().lower() == "s":
        capture(index, device)
        write_metadata()


def main() -> None:
    parser = argparse.ArgumentParser(description="gravar dataset para fine-tune do Piper")
    parser.add_argument("--mic", help="microfone: indice ou parte do nome")
    parser.add_argument("--speaker", help="alto-falante, para --review")
    parser.add_argument("--review", type=int, metavar="N", help="ouvir e refazer uma frase")
    parser.add_argument("--status", action="store_true", help="quanto ja foi gravado")
    parser.add_argument("--reset", action="store_true", help="apagar tudo e recomecar")
    parser.add_argument(
        "--redo",
        metavar="SPEC",
        help="apagar frases para regravar: 7, 1-10 ou 2,7,15",
    )
    parser.add_argument("--from", dest="start", type=int, default=1, help="comecar da frase N")
    args = parser.parse_args()

    if args.status:
        status()
        return

    if args.reset:
        reset()
        return

    if args.redo:
        redo(args.redo)
        return

    device = ensure("input", args.mic)
    print(f"microfone: {describe(device)}")

    if args.review:
        review(args.review, device, ensure("output", args.speaker))
        return

    recorded = done()
    pending = [i for i in range(args.start, len(SENTENCES) + 1) if i not in recorded]
    if not pending:
        print("\n  tudo gravado.")
        status()
        return

    print(f"\n  {len(pending)} frases pela frente. Leia naturalmente, sem pressa.")
    print("  A gravacao para sozinha quando voce para de falar.\n")

    for index in pending:
        if not capture(index, device):
            break

    total = write_metadata()
    print(f"\n  metadata.csv escrito com {total} linhas")
    status()


if __name__ == "__main__":
    main()
