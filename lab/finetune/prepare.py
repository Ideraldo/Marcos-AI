"""Turn a published Piper checkpoint into one you can fine-tune from, on Windows.

    python -m lab.finetune.prepare --base pt_BR-dii-high

Three problems stand between a downloaded checkpoint and a fine-tune, and all
three are silent until they are not:

1. **PosixPath.** The checkpoints were saved on Linux and carry `pathlib` objects
   inside. Unpickling one on Windows raises "cannot instantiate 'PosixPath'".
   Fixed by pointing PosixPath at WindowsPath while loading, then replacing every
   path with a plain string so the problem never comes back.

2. **weights_only.** torch 2.6 changed `torch.load` to refuse anything but plain
   tensors by default, and Lightning loads checkpoints that way. A checkpoint
   holding only tensors and numbers passes without needing an exemption.

3. **The epoch counter.** This is the one that would waste an afternoon.
   `--ckpt_path` in Lightning means *resume*, so it restores the epoch too: the
   dii checkpoint stopped at epoch 3908, and asking for 2000 epochs would make
   training exit immediately having done nothing. Resetting the counter to zero
   is what turns "resume someone else's run" into "start mine from their
   weights".

The optimizer state is dropped for the same reason: it belongs to their training
run, on their data, and carrying it over fights the new voice instead of helping.
"""

from __future__ import annotations

import argparse
import pathlib
from pathlib import Path
from typing import Any

CHECKPOINTS = Path(__file__).resolve().parents[1] / "models" / "piper_ckpt"


def stringify(value: Any) -> Any:
    """Replace every Path anywhere in the structure with its text form."""
    if isinstance(value, pathlib.PurePath):
        return str(value)
    if isinstance(value, dict):
        return {key: stringify(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return type(value)(stringify(item) for item in value)
    return value


def load_posix_checkpoint(path: Path) -> dict:
    """Load a checkpoint pickled on Linux while running on Windows."""
    import torch

    original = pathlib.PosixPath
    if not hasattr(pathlib.PosixPath, "_flavour") or original is not pathlib.WindowsPath:
        pathlib.PosixPath = pathlib.WindowsPath  # type: ignore[misc,assignment]
    try:
        return torch.load(path, weights_only=False, map_location="cpu")
    finally:
        pathlib.PosixPath = original  # type: ignore[misc]


def accepted_hyperparameters() -> set[str]:
    """Which hyperparameters the installed VitsModel still takes.

    The published checkpoints predate the current piper.train, and Lightning
    rebuilds the model from whatever the checkpoint saved. One stale key --
    ``sample_bytes``, in these -- aborts the run before the first batch. Asking
    the class itself is the only version-proof answer.
    """
    import inspect

    from piper.train.vits.lightning import VitsModel

    return {
        name
        for name in inspect.signature(VitsModel.__init__).parameters
        if name not in ("self", "args", "kwargs")
    }


def prepare(base: str) -> Path:
    import torch

    source = CHECKPOINTS / f"{base}.ckpt"
    if not source.exists():
        raise SystemExit(f"nao encontrei {source}")

    destination = CHECKPOINTS / f"{base}-finetune.ckpt"
    checkpoint = load_posix_checkpoint(source)

    epoch = checkpoint.get("epoch")
    step = checkpoint.get("global_step")
    print(f"  origem: epoch {epoch}, step {step}")

    allowed = accepted_hyperparameters()
    saved = stringify(checkpoint.get("hyper_parameters", {}))
    dropped = sorted(set(saved) - allowed)
    hyper = {key: value for key, value in saved.items() if key in allowed}

    clean = {
        "state_dict": stringify(checkpoint["state_dict"]),
        "hyper_parameters": hyper,
        "pytorch-lightning_version": checkpoint.get("pytorch-lightning_version", "2.0.0"),
        "epoch": 0,
        "global_step": 0,
        # Lightning refuses a checkpoint with no optimizer state -- ckpt_path
        # means "resume" to it. Empty lists satisfy the check and then iterate
        # over nothing, which is precisely what fine-tuning wants: their weights,
        # a fresh optimizer. Carrying their optimizer over would fight the new
        # voice, since its momentum was accumulated on another speaker.
        "optimizer_states": [],
        "lr_schedulers": [],
    }
    torch.save(clean, destination)
    size = destination.stat().st_size / 1e6
    print(f"  pronto: {destination.name}  ({size:.0f} MB, epoch 0)")
    print("  descartado: estado do otimizador e do loop de treino de origem")
    if dropped:
        print(f"  hiperparametros obsoletos removidos: {', '.join(dropped)}")
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description="preparar checkpoint base para fine-tune")
    parser.add_argument("--base", default="pt_BR-dii-high")
    args = parser.parse_args()
    prepare(args.base)


if __name__ == "__main__":
    main()
