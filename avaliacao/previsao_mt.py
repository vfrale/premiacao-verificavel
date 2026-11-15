"""Demonstração complementar a H2: previsão do G-MT a partir de 624 saídas.

A têmpera do MT19937 é inversível, e cada saída de 32 bits corresponde a uma
palavra do estado (Capítulo 2). Observadas 624 saídas consecutivas, o estado
é reconstruído e as saídas seguintes são previstas. A demonstração é aplicada
às sequências do G-MT avaliadas pela bateria NIST, regeneradas do registro.

  python -m avaliacao.previsao_mt --saida resultados
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

from .geradores import GeradorMT

N = 624


def _desfazer_xor_direita(y: int, k: int) -> int:
    x = y
    for _ in range(32 // k + 1):
        x = y ^ (x >> k)
    return x & 0xFFFFFFFF


def _desfazer_xor_esquerda(y: int, k: int, mascara: int) -> int:
    x = y
    for _ in range(32 // k + 1):
        x = y ^ ((x << k) & mascara)
    return x & 0xFFFFFFFF


def destemperar(y: int) -> int:
    """Inverte a têmpera do MT19937 (MATSUMOTO; NISHIMURA, 1998)."""
    y = _desfazer_xor_direita(y, 18)
    y = _desfazer_xor_esquerda(y, 15, 0xEFC60000)
    y = _desfazer_xor_esquerda(y, 7, 0x9D2C5680)
    return _desfazer_xor_direita(y, 11)


def clonar(saidas: list[int]) -> random.Random:
    """Gerador com o estado reconstruído a partir de 624 saídas consecutivas."""
    if len(saidas) != N:
        raise ValueError("são necessárias exatamente 624 saídas")
    clone = random.Random()
    clone.setstate((3, tuple(destemperar(y) for y in saidas) + (N,), None))
    return clone


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--saida", default="resultados")
    p.add_argument("--palavras", type=int, default=31_250, help="palavras de 32 bits por sequência")
    args = p.parse_args(argv)
    saida = Path(args.saida)
    sementes = [json.loads(t) for t in open(saida / "sementes_hmac_mt.jsonl", encoding="utf-8")]
    sementes = [d for d in sementes if d["gerador"] == "G-MT"]
    acertos = total = sequencias_exatas = 0
    for d in sementes:
        palavras = GeradorMT(int(d["semente"])).palavras(args.palavras).tolist()
        clone = clonar(palavras[:N])
        previstas = [clone.getrandbits(32) for _ in range(len(palavras) - N)]
        certas = sum(a == b for a, b in zip(previstas, palavras[N:]))
        acertos += certas
        total += len(previstas)
        sequencias_exatas += certas == len(previstas)
    resultado = {"sequencias": len(sementes), "palavras_observadas": N,
                 "palavras_previstas": total, "palavras_corretas": acertos,
                 "sequencias_previstas_integralmente": sequencias_exatas}
    (saida / "previsao_mt.json").write_text(json.dumps(resultado, indent=2, ensure_ascii=False),
                                            encoding="utf-8")
    print(resultado)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
