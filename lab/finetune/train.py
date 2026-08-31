"""Fine-tune a Piper voice on your dataset, then export it as a usable .onnx.

    python -m lab.finetune.train --base pt_BR-dii-high --name ideraldo
    python -m lab.finetune.train --base pt_BR-dii-high --name ideraldo --resume
    python -m lab.finetune.train --export --name ideraldo

Fine-tuning, not training from scratch: the base checkpoint already speaks
Portuguese, and what your recordings change is the timbre. That is why an hour
of audio is enough where a voice from zero would need dozens.

The RTX 2060 has 6 GB, so batch size 8 with 16-bit precision is the safe
starting point. If it runs out of memory, halve it -- that costs time, not
quality.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "dataset"
CHECKPOINTS = ROOT.parent / "models" / "piper_ckpt"
VOICES = ROOT.parent / "models" / "piper"
OUTPUT = ROOT / "runs"

#: espeak voice for the phonemiser. Must match the base voice's language.
ESPEAK_VOICE = "pt-br"


def base_files(base: str) -> tuple[Path, Path]:
    checkpoint = CHECKPOINTS / f"{base}.ckpt"
    config = VOICES / f"{base}.onnx.json"
    if not checkpoint.exists():
        raise SystemExit(f"checkpoint nao encontrado: {checkpoint}")
    if not config.exists():
        raise SystemExit(f"config nao encontrada: {config}")
    return checkpoint, config


def train(base: str, name: str, epochs: int, batch_size: int, resume: bool) -> None:
    checkpoint, config = base_files(base)
    run = OUTPUT / name
    run.mkdir(parents=True, exist_ok=True)

    if not (DATASET / "metadata.csv").exists():
        raise SystemExit("grave o dataset primeiro: python -m lab.finetune.record")

    command = [
        sys.executable, "-m", "piper.train", "fit",
        "--data.voice_name", name,
        "--data.csv_path", str(DATASET / "metadata.csv"),
        "--data.audio_dir", str(DATASET / "wav"),
        "--data.config_path", str(config),
        "--data.cache_dir", str(run / "cache"),
        "--data.espeak_voice", ESPEAK_VOICE,
        "--data.batch_size", str(batch_size),
        "--model.sample_rate", "22050",
        "--trainer.max_epochs", str(epochs),
        "--trainer.default_root_dir", str(run),
        "--trainer.accelerator", "gpu",
        "--trainer.devices", "1",
        # 16-bit halves the memory a 6 GB card has to find.
        "--trainer.precision", "16-mixed",
    ]
    # Fine-tuning and resuming use the same flag: piper.train loads whatever
    # checkpoint it is given. The difference is only which one -- the pt-BR base
    # the first time, your own interrupted run afterwards.
    start_from = latest_run_checkpoint(run) if resume else checkpoint
    command += ["--ckpt_path", str(start_from)]
    print(f"  partindo de: {start_from.name}")

    print("  " + " ".join(command) + "\n")
    subprocess.run(command, check=True)


def latest_run_checkpoint(run: Path) -> Path:
    found = sorted(run.rglob("*.ckpt"), key=lambda p: p.stat().st_mtime)
    if not found:
        raise SystemExit(f"nenhum checkpoint em {run} para retomar")
    return found[-1]


def export(name: str) -> None:
    run = OUTPUT / name
    checkpoint = latest_run_checkpoint(run)
    destination = VOICES / f"pt_BR-{name}-medium.onnx"

    print(f"  exportando {checkpoint.name} -> {destination.name}")
    subprocess.run(
        [sys.executable, "-m", "piper.train.export_onnx",
         "--checkpoint", str(checkpoint), "--output-file", str(destination)],
        check=True,
    )
    print(f"\n  pronto. ouca com:")
    print(f"    python -m lab.run_tts --engine piper --voice pt_BR-{name}-medium --play")


def main() -> None:
    parser = argparse.ArgumentParser(description="fine-tune do Piper")
    parser.add_argument("--name", default="ideraldo", help="nome da voz resultante")
    parser.add_argument("--base", default="pt_BR-dii-high", help="voz base do fine-tune")
    parser.add_argument("--epochs", type=int, default=2000)
    parser.add_argument("--batch-size", type=int, default=8, help="baixe se faltar VRAM")
    parser.add_argument("--resume", action="store_true", help="retomar um treino interrompido")
    parser.add_argument("--export", action="store_true", help="so exportar o .onnx")
    args = parser.parse_args()

    if args.export:
        export(args.name)
    else:
        train(args.base, args.name, args.epochs, args.batch_size, args.resume)


if __name__ == "__main__":
    main()
