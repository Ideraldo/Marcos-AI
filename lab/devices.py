"""Choosing the microphone and the speaker, and remembering the choice.

The default device is whatever Windows decided, which on this machine is a
headset that may not even be plugged in -- a silent recording that looks like a
broken model. Picking explicitly removes a whole class of confusing results.

    python -m lab.devices          # pick, then verify the mic actually hears you

The choice is saved to lab/.devices.json and reused by every runner. It is a
local preference, not project configuration, so it stays out of git.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

STORE = Path(__file__).resolve().parent / ".devices.json"

#: MME is the Windows default and the most forgiving; WASAPI gives lower
#: latency but refuses more format combinations. Prefer MME unless told
#: otherwise -- the bench measures models, not audio stacks.
PREFERRED_HOSTAPI = "MME"


def _devices(kind: str) -> list[tuple[int, dict[str, Any]]]:
    import sounddevice as sd

    channels = "max_input_channels" if kind == "input" else "max_output_channels"
    return [(i, d) for i, d in enumerate(sd.query_devices()) if d[channels] > 0]


def _hostapi(device: dict[str, Any]) -> str:
    import sounddevice as sd

    return sd.query_hostapis(device["hostapi"])["name"]


def load() -> dict[str, int]:
    if STORE.exists():
        try:
            return json.loads(STORE.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save(kind: str, index: int) -> None:
    chosen = load()
    chosen[kind] = index
    STORE.write_text(json.dumps(chosen, indent=2))


def describe(index: int) -> str:
    import sounddevice as sd

    device = sd.query_devices(index)
    return f"[{index}] {device['name'].strip()} ({_hostapi(device)})"


def resolve(kind: str, spec: str | int | None = None) -> int | None:
    """Turn a name fragment, an index, or a saved choice into a device index.

    Returns None to mean "let the system decide", which is only reasonable when
    nothing was ever chosen.
    """
    if spec is None:
        return load().get(kind)

    if isinstance(spec, int) or str(spec).isdigit():
        return int(spec)

    needle = str(spec).lower()
    matches = [i for i, d in _devices(kind) if needle in d["name"].lower()]
    if not matches:
        raise SystemExit(f"nenhum dispositivo de {kind} com '{spec}' no nome")
    # Several host APIs expose the same hardware; prefer the friendly one.
    for index in matches:
        import sounddevice as sd

        if _hostapi(sd.query_devices(index)) == PREFERRED_HOSTAPI:
            return index
    return matches[0]


def choose(kind: str) -> int:
    """Interactive picker. Lists one row per device and returns the index."""
    label = "microfone" if kind == "input" else "alto-falante"
    options = _devices(kind)
    if not options:
        raise SystemExit(f"nenhum dispositivo de {kind} encontrado")

    # One entry per physical device: the same mic appears under every host API,
    # and a list of 28 rows for 4 devices is what makes people pick wrong.
    seen: dict[str, int] = {}
    for index, device in options:
        name = device["name"].strip()
        if name not in seen or _hostapi(device) == PREFERRED_HOSTAPI:
            seen[name] = index

    current = load().get(kind)
    print(f"\n  escolha o {label}:\n")
    entries = list(seen.items())
    for position, (name, index) in enumerate(entries, start=1):
        mark = " <- atual" if index == current else ""
        print(f"    {position}) {name}{mark}")

    while True:
        answer = input(f"\n  numero (ENTER mantem o atual): ").strip()
        if not answer and current is not None:
            return current
        if answer.isdigit() and 1 <= int(answer) <= len(entries):
            index = entries[int(answer) - 1][1]
            save(kind, index)
            print(f"  usando {describe(index)}")
            return index
        print("  opcao invalida")


def ensure(kind: str, spec: str | int | None = None, ask: bool = False) -> int | None:
    """Resolve a device, asking only when there is nothing saved to fall back on."""
    index = resolve(kind, spec)
    if index is None or ask:
        index = choose(kind)
    return index


def main() -> None:
    import numpy as np

    from lab.audio import record

    microphone = choose("input")
    choose("output")

    print("\n  teste rapido: fale alguma coisa por 3 segundos...")
    samples = np.frombuffer(record(3.0, device=microphone), dtype=np.int16)
    peak = int(np.abs(samples).max())
    level = peak / 32768

    print(f"  pico: {peak} ({level:.0%} da escala)")
    if peak < 500:
        print("  SILENCIO -- o microfone esta mudo, desligado ou e o dispositivo errado")
    elif level > 0.95:
        print("  SATURADO -- abaixe o ganho ou afaste-se do microfone")
    else:
        print("  ok, esta ouvindo")


if __name__ == "__main__":
    main()
