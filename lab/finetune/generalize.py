"""Mede se a voz treinada aprendeu a falar ou apenas decorou o corpus.

    python -m lab.finetune.generalize --voice pt_BR-ideraldo-medium
    python -m lab.finetune.generalize --voice pt_BR-ideraldo-medium --play
    python -m lab.finetune.generalize --voice pt_BR-ideraldo-medium --against pt_BR-dii-high

A ideia: sintetizar frases que nunca foram gravadas e **transcrever o resultado
de volta** com o Whisper. Se a voz articula bem, o STT entende; se decorou o
corpus e desmonta em texto novo, o WER sobe e mostra exatamente onde.

Não substitui o ouvido — um modelo pode soar metálico e ainda assim ser
transcrito perfeitamente. Mas pega o que o ouvido deixa passar: uma sílaba comida
no meio de uma palavra longa, um número lido errado, um nome próprio virando
outra coisa. E dá um número comparável entre épocas, que é o que permite
responder "melhorou ou piorou?" sem depender de memória auditiva.

Compare sempre contra a voz base (``--against``). O que interessa não é o WER
absoluto — o Whisper erra sozinho, e o teste inclui armadilhas de propósito —
mas a **diferença** entre a voz treinada e a que lhe deu origem.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from common.messages import SAMPLE_RATE
from lab.audio import play, resample, write_wav
from lab.devices import ensure
from lab.finetune.holdout import HOLDOUT
from lab.metrics import cer, wer
from lab.tts.piper import PiperTTS

OUT = Path(__file__).resolve().parent / "out" / "generalize"


def synthesize(voice: str, keys: list[str]) -> dict[str, Path]:
    engine = PiperTTS(voice)
    engine.synthesize("aquecimento")  # carrega o modelo fora da medição

    paths = {}
    for key in keys:
        samples, rate = engine.synthesize(HOLDOUT[key])
        path = OUT / voice / f"{key}.wav"
        write_wav(path, resample(samples, rate, SAMPLE_RATE).tobytes(), SAMPLE_RATE)
        paths[key] = path
    return paths


def transcribe_all(paths: dict[str, Path]) -> dict[str, str]:
    from lab.stt.faster_whisper import FasterWhisper

    stt = FasterWhisper("small")
    return {key: stt.transcribe(path) for key, path in paths.items()}


def score(voice: str, keys: list[str], verbose: bool) -> tuple[float, dict[str, float]]:
    started = time.perf_counter()
    paths = synthesize(voice, keys)
    print(f"  sintetizadas {len(paths)} frases em {time.perf_counter() - started:.1f}s")
    print("  transcrevendo de volta com whisper small...")

    heard = transcribe_all(paths)
    per_phrase = {}
    for key in keys:
        reference, hypothesis = HOLDOUT[key], heard[key]
        value = wer(reference, hypothesis)
        per_phrase[key] = value
        if verbose:
            flag = "ok " if value < 0.05 else "ERR"
            print(f"  [{flag}] {key:<12} WER {value:5.1%}  CER {cer(reference, hypothesis):5.1%}")
            if value >= 0.05:
                print(f"        texto:  {reference[:88]}")
                print(f"        ouviu:  {hypothesis[:88]}")

    return sum(per_phrase.values()) / len(per_phrase), per_phrase


def diagnose(in_domain: float, holdout: float, base_holdout: float | None) -> None:
    """Separar decorou de ainda-não-aprendeu.

    O WER alto em texto novo, sozinho, não distingue as duas doenças:

    * **decorou** -- vai bem nas frases treinadas e mal nas novas. O sintoma é a
      *diferença* entre as duas, não o valor de nenhuma delas.
    * **ainda cru** -- vai mal nas duas. O modelo saiu da articulação limpa da
      base e ainda não chegou na sua. É o estado normal no começo do treino, e
      não se resolve parando mais cedo -- se resolve treinando mais.

    Confundir uma com a outra leva à decisão oposta da correta, então o
    diagnóstico olha o par.
    """
    gap = holdout - in_domain
    print(f"\n  corpus (frases treinadas):  WER {in_domain:.1%}")
    print(f"  holdout (nunca gravadas):   WER {holdout:.1%}")
    print(f"  distancia entre os dois:    {gap:+.1%}")

    if base_holdout is not None:
        print(f"  a base, no mesmo holdout:   WER {base_holdout:.1%}")

    if gap > 0.15 and in_domain < 0.15:
        print("\n  => DECOROU. Vai bem no que treinou e mal em texto novo.")
        print("     Volte para um checkpoint anterior; o treino passou do ponto.")
    elif in_domain > 0.20 and gap < 0.15:
        print("\n  => AINDA CRU. Vai mal nos dois igualmente, o que e o esperado")
        print("     no comeco: saiu da articulacao da base e ainda nao chegou na sua.")
        print("     Continue treinando e meca de novo mais adiante.")
    elif base_holdout is not None and holdout - base_holdout < 0.05:
        print("\n  => SAUDAVEL. Generaliza tao bem quanto a base.")
    else:
        print("\n  => EM TRANSICAO. Sem sinal claro dos dois lados; repita mais adiante")
        print("     e compare a serie, que e o que responde 'melhorou ou piorou'.")


#: Frases do corpus usadas como referência "dentro do domínio", espalhadas pelos
#: três blocos.
#:
#: Eram seis, e seis é pouco: o VITS sintetiza com amostragem estocástica, e duas
#: medições do mesmo modelo deram 17,4% e 26,9% — variação suficiente para virar
#: o diagnóstico de lado. Vinte frases custam meio minuto a mais e tiram a
#: decisão das mãos do acaso.
IN_DOMAIN_KEYS = [0, 12, 25, 40, 55, 70, 85, 96, 115, 135, 155, 175, 195, 210, 230, 250, 270, 290, 300, 310]


def score_in_domain(voice: str, verbose: bool) -> float:
    """Mesma medição, mas sobre frases que o modelo treinou."""
    from lab.finetune.corpus import SENTENCES
    from lab.stt.faster_whisper import FasterWhisper

    engine = PiperTTS(voice)
    engine.synthesize("aquecimento")
    stt = FasterWhisper("small")

    total = 0.0
    for index in IN_DOMAIN_KEYS:
        text = SENTENCES[index]
        samples, rate = engine.synthesize(text)
        path = OUT / voice / f"corpus_{index}.wav"
        write_wav(path, resample(samples, rate, SAMPLE_RATE).tobytes(), SAMPLE_RATE)
        value = wer(text, stt.transcribe(path))
        total += value
        if verbose:
            print(f"  [corpus {index:>3}] WER {value:5.1%}")
    return total / len(IN_DOMAIN_KEYS)


def main() -> None:
    parser = argparse.ArgumentParser(description="teste de generalizacao da voz treinada")
    parser.add_argument("--voice", required=True, help="voz a testar (ex: pt_BR-ideraldo-medium)")
    parser.add_argument("--against", help="voz base para comparar (ex: pt_BR-dii-high)")
    parser.add_argument("--play", action="store_true", help="tocar cada frase do holdout")
    parser.add_argument("--quiet", action="store_true", help="so as medias")
    args = parser.parse_args()

    keys = list(HOLDOUT)
    print(f"\n{args.voice}")
    print(f"  {len(keys)} frases nunca gravadas + {len(IN_DOMAIN_KEYS)} do corpus\n")

    holdout_mean, per_phrase = score(args.voice, keys, verbose=not args.quiet)
    in_domain_mean = score_in_domain(args.voice, verbose=not args.quiet)

    base_mean = None
    base_per_phrase = None
    if args.against:
        print(f"\n{args.against} (base), no mesmo holdout:")
        base_mean, base_per_phrase = score(args.against, keys, verbose=False)

    diagnose(in_domain_mean, holdout_mean, base_mean)

    if base_per_phrase:
        piores = sorted(
            ((key, per_phrase[key] - base_per_phrase[key]) for key in keys),
            key=lambda pair: pair[1],
            reverse=True,
        )[:3]
        print("\n  onde mais perdeu para a base:")
        for key, gap in piores:
            print(f"    {key:<12} {gap:+.1%}")

    if args.play:
        speaker = ensure("output")
        for key in keys:
            print(f'\n  [{key}] "{HOLDOUT[key][:70]}"')
            play(OUT / args.voice / f"{key}.wav", device=speaker)

    print(f"\n  audio em {OUT / args.voice}\n")


if __name__ == "__main__":
    main()
