"""Exporta o modelo sozinho ao longo do treino, para você ter a evolução de manhã.

    python -m lab.finetune.watch --name ideraldo

Roda num segundo terminal, ao lado do treino. A cada verificação olha o
checkpoint mais recente e, se ele avançou 100 épocas desde o último export,
gera um `.onnx` novo.

**Por que isso existe.** O `ModelCheckpoint` do Lightning guarda apenas os cinco
melhores por métrica e vai apagando os antigos. No treino v1, quando fui
arquivar, as épocas anteriores à 247 já não existiam — perdi o começo inteiro da
evolução. O `.onnx` tem 60 MB contra 845 MB de um checkpoint, e é o único formato
que se ouve.

Não toca no treino: roda em outro processo, exporta na CPU e só lê os arquivos.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from lab.finetune.train import OUTPUT, all_checkpoints, epoch_of, export


def newest(run: Path) -> tuple[Path, int] | None:
    """O checkpoint mais recente que tem época no nome (o last.ckpt não tem)."""
    for path in reversed(all_checkpoints(run)):
        epoch = epoch_of(path)
        if epoch is not None:
            return path, epoch
    return None


def watch(name: str, base: str, every: int, interval: int) -> None:
    run = OUTPUT / name
    if not run.exists():
        raise SystemExit(f"{run} nao existe -- o treino ja comecou?")

    print(f"\n  observando {run}")
    print(f"  exporta a cada {every} epocas, verificando de {interval}s em {interval}s")
    print("  Ctrl+C para parar (nao afeta o treino)\n")

    exported: set[int] = set()
    next_target = 0

    while True:
        found = newest(run)
        if found is None:
            time.sleep(interval)
            continue

        path, epoch = found
        if epoch >= next_target and epoch not in exported:
            voice = f"{name}ep{epoch}"
            try:
                # Passa o arquivo pelo nome: a época exata pode não ter sido
                # salva, e o que importa é exportar a mais recente que existe.
                export(name, base, None, path.name, voice)
                exported.add(epoch)
                # Próximo alvo a partir da época real, não do alvo teórico, para
                # não disparar duas vezes seguidas quando o treino pula épocas.
                next_target = epoch + every
                print(f"  [{time.strftime('%H:%M')}] epoca {epoch} exportada\n")
            except Exception as error:
                # Quase sempre é o Lightning escrevendo o arquivo neste instante.
                # Não vale abortar a vigília por isso: tenta de novo no próximo ciclo.
                print(f"  [{time.strftime('%H:%M')}] epoca {epoch} falhou ({error}); tentando depois")

        time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="exporta o modelo a cada N epocas")
    parser.add_argument("--name", default="ideraldo", help="nome do run em andamento")
    parser.add_argument("--base", default="pt_BR-dii-high", help="voz base, para copiar o config")
    parser.add_argument("--every", type=int, default=100, help="intervalo em epocas")
    parser.add_argument("--interval", type=int, default=180, help="segundos entre verificacoes")
    args = parser.parse_args()

    try:
        watch(args.name, args.base, args.every, args.interval)
    except KeyboardInterrupt:
        print("\n  parou de observar. o treino continua.\n")


if __name__ == "__main__":
    main()
