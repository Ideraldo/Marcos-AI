"""What is on the bench, and how each candidate relates to Portuguese.

    python -m lab.list
"""

from __future__ import annotations

from lab.registry import LANGS
from lab.stt import ENGINES as STT
from lab.tts import ENGINES as TTS


def show(title: str, engines: dict) -> None:
    print(f"\n{title}")
    print(f"  {'':4} {'motor':<16} {'tipo':<7} {'idioma':<12} nota")
    print("  " + "-" * 74)
    for name, entry in engines.items():
        print(f"  {entry.flag} {name:<16} {entry.kind:<7} {entry.lang:<12} {entry.note}")


def main() -> None:
    show("TTS", TTS)
    show("STT", STT)
    print(f"\n  [PT] = {LANGS['pt']}\n")


if __name__ == "__main__":
    main()
