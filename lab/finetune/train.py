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
import json
import re
import time
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
    """The prepared checkpoint and the voice config to fine-tune from.

    The published checkpoint is never used directly: it carries Linux paths that
    Windows cannot unpickle and an epoch counter that would end training before
    it began. ``lab.finetune.prepare`` fixes both, and runs here automatically
    the first time.
    """
    from lab.finetune.monotonic_align import install
    from lab.finetune.prepare import prepare

    # The Windows wheel ships this package without its compiled extension.
    if install():
        print("  instalado o monotonic_align que faltava na wheel do Windows")

    config = VOICES / f"{base}.onnx.json"
    if not config.exists():
        raise SystemExit(f"config nao encontrada: {config}")

    checkpoint = CHECKPOINTS / f"{base}-finetune.ckpt"
    if not checkpoint.exists():
        print(f"  preparando o checkpoint base ({base})...")
        checkpoint = prepare(base)
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


def epoch_of(checkpoint: Path) -> int | None:
    """A época que o Lightning gravou no nome do arquivo, se houver."""
    match = re.search(r"epoch=(\d+)", checkpoint.name)
    return int(match.group(1)) if match else None


def all_checkpoints(run: Path) -> list[Path]:
    return sorted(run.rglob("*.ckpt"), key=lambda p: p.stat().st_mtime)


def latest_run_checkpoint(run: Path) -> Path:
    found = all_checkpoints(run)
    if not found:
        raise SystemExit(f"nenhum checkpoint em {run}")
    return found[-1]


def list_checkpoints(name: str) -> None:
    """Mostra o que dá para exportar, mais novo por último."""
    found = all_checkpoints(OUTPUT / name)
    if not found:
        raise SystemExit(f"nenhum checkpoint em {OUTPUT / name}")

    print(f"\n  {len(found)} checkpoints em {OUTPUT / name}\n")
    for path in found:
        stamp = time.strftime("%H:%M", time.localtime(path.stat().st_mtime))
        print(f"    {stamp}  {path.name}")
    print("\n  exporte um com:  --export --epoch N   ou   --export --checkpoint <arquivo>\n")


def pick_checkpoint(run: Path, epoch: int | None, explicit: str | None) -> Path:
    """Escolhe qual checkpoint exportar: explícito, por época, ou o mais recente."""
    if explicit:
        path = Path(explicit)
        if not path.is_absolute():
            matches = [p for p in all_checkpoints(run) if p.name == explicit]
            path = matches[0] if matches else path
        if not path.exists():
            raise SystemExit(f"nao encontrei {explicit}")
        return path

    if epoch is None:
        return latest_run_checkpoint(run)

    matches = [p for p in all_checkpoints(run) if epoch_of(p) == epoch]
    if not matches:
        disponiveis = sorted({e for p in all_checkpoints(run) if (e := epoch_of(p)) is not None})
        raise SystemExit(
            f"nenhum checkpoint da epoca {epoch}.\n"
            f"  epocas salvas: {disponiveis}\n"
            f"  veja tudo com: --list --name <nome>"
        )

    # O Lightning guarda uma cópia por métrica monitorada (val_mel e val_mos),
    # e as duas são o mesmo modelo daquela época -- qualquer uma serve.
    chosen = matches[-1]
    if len(matches) > 1:
        print(f"  epoca {epoch} tem {len(matches)} arquivos; usando {chosen.name}")
    return chosen


def export(name: str, base: str, epoch: int | None, explicit: str | None, as_name: str | None) -> None:
    run = OUTPUT / name
    checkpoint = pick_checkpoint(run, epoch, explicit)

    # Exportar uma época específica normalmente é para comparar com outra, então
    # o nome de saída carrega a época -- exportar duas não sobrescreve uma a
    # outra, e as duas podem ser ouvidas lado a lado na bancada.
    if as_name:
        voice = as_name
    elif epoch is not None or explicit:
        found = epoch_of(checkpoint)
        voice = f"{name}ep{found}" if found is not None else f"{name}-snapshot"
    else:
        voice = name

    destination = VOICES / f"pt_BR-{voice}-medium.onnx"
    print(f"  exportando {checkpoint.name} -> {destination.name}")
    subprocess.run(
        [sys.executable, "-m", "piper.train.export_onnx",
         "--checkpoint", str(checkpoint), "--output-file", str(destination)],
        check=True,
    )

    # O exportador escreve só o .onnx, mas PiperVoice.load exige o config ao
    # lado. A tabela de fonemas e a taxa de amostragem vêm da voz base e não
    # mudam com o fine-tune, então copiar é correto.
    config = json.loads((VOICES / f"{base}.onnx.json").read_text(encoding="utf-8"))
    config.setdefault("dataset", voice)
    (VOICES / f"pt_BR-{voice}-medium.onnx.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("\n  pronto. ouca com:")
    print(f"    python -m lab.run_tts --engine piper --voice pt_BR-{voice}-medium --play")
    print(f"    python -m lab.finetune.generalize --voice pt_BR-{voice}-medium --against {base}")


def main() -> None:
    parser = argparse.ArgumentParser(description="fine-tune do Piper")
    parser.add_argument("--name", default="ideraldo", help="nome do run / da voz")
    parser.add_argument("--base", default="pt_BR-dii-high", help="voz base do fine-tune")
    parser.add_argument("--epochs", type=int, default=2000)
    parser.add_argument("--batch-size", type=int, default=8, help="baixe se faltar VRAM")
    parser.add_argument("--resume", action="store_true", help="retomar um treino interrompido")
    parser.add_argument("--export", action="store_true", help="so exportar o .onnx")
    parser.add_argument("--list", action="store_true", help="listar os checkpoints do run")
    parser.add_argument(
        "--epoch",
        type=int,
        help="exportar uma epoca especifica em vez da mais recente",
    )
    parser.add_argument("--checkpoint", help="exportar um arquivo .ckpt nomeado")
    parser.add_argument(
        "--as",
        dest="as_name",
        help="nome da voz de saida (padrao: <name>ep<N> quando a epoca e escolhida)",
    )
    args = parser.parse_args()

    if args.list:
        list_checkpoints(args.name)
    elif args.export or args.epoch is not None or args.checkpoint:
        export(args.name, args.base, args.epoch, args.checkpoint, args.as_name)
    else:
        train(args.base, args.name, args.epochs, args.batch_size, args.resume)


if __name__ == "__main__":
    main()
