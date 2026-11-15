"""Diagnóstico complementar da reprovação do RANDU R16 no teste de frequência em blocos.

Compara a variância do número de uns em blocos de 128 bits (parâmetro padrão
do STS) com a variância binomial (32) e mede a correlação entre as contagens
de uns de palavras de 16 bits separadas por 1 a 7 posições (as que dividem um
mesmo bloco). Usa sequências novas, com sementes de `secrets` registradas.

  python -m avaliacao.diagnostico_r16 --saida resultados
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .geradores import GeradorHMAC, GeradorRANDU

M = 128


def medidas(bits: bytes) -> tuple[float, list[float]]:
    b = np.unpackbits(np.frombuffer(bits, dtype=np.uint8)).astype(np.int64)
    blocos = b[: len(b) // M * M].reshape(-1, M).sum(axis=1)
    palavras = b.reshape(-1, 16).sum(axis=1).astype(float)
    corr = [float(np.corrcoef(palavras[:-k], palavras[k:])[0, 1]) for k in range(1, 8)]
    return float(blocos.var() / (M / 4)), corr


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--saida", default="resultados")
    p.add_argument("--sequencias", type=int, default=100)
    args = p.parse_args(argv)
    resultado, sementes = {}, []
    for nome, fabrica, kw in (("G-RANDU-R16", GeradorRANDU, {"representacao": "R16"}),
                              ("G-HMAC", GeradorHMAC, {})):
        razoes, correlacoes = [], []
        for _ in range(args.sequencias):
            g = fabrica()
            sementes.append({"gerador": nome, **g.semente()})
            r, c = medidas(g.bits(**kw))
            razoes.append(r)
            correlacoes.append(c)
        resultado[nome] = {"razao_variancia_bloco": float(np.mean(razoes)),
                           "erro_padrao": float(np.std(razoes, ddof=1) / np.sqrt(len(razoes))),
                           "correlacao_palavras_defasagem_1_a_7": np.mean(correlacoes, axis=0).round(5).tolist()}
    resultado["sementes"] = sementes
    destino = Path(args.saida) / "diagnostico_r16.json"
    destino.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
    for nome in ("G-RANDU-R16", "G-HMAC"):
        print(nome, {k: v for k, v in resultado[nome].items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
