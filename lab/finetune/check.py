"""Inspect the recorded dataset before spending hours of GPU on it.

    python -m lab.finetune.check

Every problem found here is cheap: re-read a sentence. The same problem found
after training is expensive, and usually invisible until you hear the voice do
something strange and cannot explain why.

What it looks for:

* **truncadas** -- audio far shorter than its text needs. The VAD cut in early,
  or the sentence was not finished. The model would learn to stop mid-phrase.
* **saturadas** -- peaks against the ceiling. Clipping is distortion, and a
  vocoder reproduces distortion faithfully.
* **baixas** -- so quiet that the noise floor is a large part of the signal.
* **ritmo** -- characters per second, per take. A dataset where half was read
  fast and half slow teaches an inconsistent pace.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from lab.audio import read_wav
from lab.finetune.corpus import SENTENCES

WAVS = Path(__file__).resolve().parent / "dataset" / "wav"

#: Reading pace in characters per second. Below 8 is unnaturally slow; above 20
#: the audio cannot possibly contain the whole sentence.
SLOW, FAST = 8.0, 20.0


def main() -> None:
    if not WAVS.exists():
        raise SystemExit(f"nada em {WAVS}")

    takes = []
    for path in sorted(WAVS.glob("*.wav")):
        index = int(path.stem)
        samples, rate = read_wav(path)
        text = SENTENCES[index - 1]
        seconds = len(samples) / rate
        peak = int(np.abs(samples).max())
        takes.append((index, seconds, peak, len(text) / seconds, text))

    if not takes:
        raise SystemExit("nenhuma gravacao")

    total = sum(t[1] for t in takes)
    pace = sum(len(t[4]) for t in takes) / total
    print(f"\n  {len(takes)} gravacoes, {total / 60:.1f} min de audio")
    print(f"  ritmo medio: {pace:.1f} caracteres/segundo")
    print(f"  pico medio:  {np.mean([t[2] for t in takes]) / 32768:.0%}")

    problems = {
        "truncadas (audio curto demais para o texto)": [t for t in takes if t[3] > FAST],
        "arrastadas (leitura muito lenta)": [t for t in takes if t[3] < SLOW],
        "saturadas (clipping)": [t for t in takes if t[2] > 32000],
        "baixas demais": [t for t in takes if t[2] < 3000],
    }

    found = False
    for label, items in problems.items():
        if not items:
            continue
        found = True
        print(f"\n  {label}: {len(items)}")
        for index, seconds, peak, chars, text in items[:10]:
            print(f"    {index:>3}  {seconds:>4.1f}s  pico {peak / 32768:>3.0%}  {chars:>4.1f} c/s  {text[:52]}")
        if items[:10] != items:
            print(f"    ... e mais {len(items) - 10}")
        print(f"    regravar:  python -m lab.finetune.record --redo {','.join(str(t[0]) for t in items[:10])}")

    if not found:
        print("\n  nenhum problema encontrado.")

    if total < 900:
        print(f"\n  {total / 60:.1f} min gravados. 15 min ou mais deixa o timbre convincente;")
        print("  o bloco 2 do corpus (frases longas) existe justamente para chegar la.")


if __name__ == "__main__":
    main()
