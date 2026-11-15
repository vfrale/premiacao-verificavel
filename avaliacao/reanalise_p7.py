"""Reanálise do teste P7 (duplicação) com valor-p exato e aleatorizado.

O P7 planejado (Quadro 7) usa a aproximação de Poisson e um valor-p bilateral
discreto, que não é uniforme sob H0: o critério de uniformidade P_T falha por
acaso em cerca de 42% das amostras de 1.000 sequências de um gerador ideal.
Este módulo regenera, a partir do registro de sementes, as mesmas sequências
do Experimento 1, confere que a versão planejada reproduz os resultados
registrados em portaria.json e aplica a versão corrigida (portaria.p7_duplicacao)
com a mesma regra de decisão.

  python -m avaliacao.reanalise_p7 --saida resultados
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from . import portaria, segundo_nivel
from .executar import _decisao_json
from .geradores import GeradorHMAC, GeradorMT, GeradorRANDU


def regenerar(linha: dict):
    """Reconstrói o gerador de uma linha do registro de sementes."""
    if linha["gerador"] == "G-HMAC":
        return GeradorHMAC(bytes.fromhex(linha["semente_servidor"]), linha["semente_participante"])
    if linha["gerador"] == "G-MT":
        return GeradorMT(int(linha["semente"]))
    return GeradorRANDU(int(linha["semente"]))


def amostras_registradas(arquivo: Path) -> dict[tuple[str, int], list[list[dict]]]:
    """Agrupa as sementes do Experimento 1 por (gerador, amostra), em blocos de 1.000.

    No G-RANDU houve três segundas amostras, uma por teste reprovado (P2, P4 e
    P7, nessa ordem); a de P7 é a terceira.
    """
    blocos: dict[tuple[str, int], list[list[dict]]] = {}
    for texto in open(arquivo, encoding="utf-8"):
        d = json.loads(texto)
        if d.get("experimento") != "portaria":
            continue
        lista = blocos.setdefault((d["gerador"], d["amostra"]), [])
        if d["indice"] == 0:
            lista.append([])
        lista[-1].append(d)
    return blocos


def avaliar(bloco: list[dict], valores: int) -> tuple[list[float], list[float], list[int]]:
    planejado, corrigido, colisoes = [], [], []
    for linha in bloco:
        u = regenerar(linha).uniformes(valores)
        planejado.append(portaria.p7_duplicacao_poisson(u))
        corrigido.append(portaria.p7_duplicacao(u))
        colisoes.append(portaria._colisoes(u, 2 ** 14, 32, 4))
    return planejado, corrigido, colisoes


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--saida", default="resultados")
    p.add_argument("--valores", type=int, default=100_000)
    args = p.parse_args(argv)
    saida = Path(args.saida)
    registrados = json.loads((saida / "portaria.json").read_text(encoding="utf-8"))["resultados"]
    blocos = amostras_registradas(saida / "sementes.jsonl")

    resultado: dict = {}
    pmf = portaria.distribuicao_colisoes(2 ** 14, 2 ** 20)
    for nome in ("G-HMAC", "G-MT", "G-RANDU-R31"):
        rotulo = "G-RANDU" if nome.startswith("G-RANDU") else nome
        reg = registrados[rotulo]["P7"]
        plan1, corr1, col1 = avaliar(blocos[(nome, 1)][0], args.valores)
        d_plan = segundo_nivel.decidir("P7", [segundo_nivel.estatistica_de_pvalores("P7", plan1)])
        e_reg = reg["amostra1"]["estatisticas"][0]
        reproduz = (abs(d_plan.estatisticas[0].proporcao - e_reg["proporcao"]) < 1e-12
                    and abs(d_plan.estatisticas[0].p_t - e_reg["p_t"]) < 1e-9)
        d1 = segundo_nivel.decidir("P7", [segundo_nivel.estatistica_de_pvalores("P7", corr1)])
        d2 = None
        if not d1.aprovado:
            # mesma segunda amostra usada para o P7 no experimento original
            bloco2 = blocos[(nome, 2)][-1] if reg["amostra2"] else None
            if bloco2 is None:
                raise RuntimeError("não há segunda amostra registrada para o P7")
            _, corr2, _ = avaliar(bloco2, args.valores)
            d2 = segundo_nivel.decidir("P7", [segundo_nivel.estatistica_de_pvalores("P7", corr2)])
        resultado[rotulo] = {
            "planejado_reproduz_registro": reproduz,
            "colisoes_amostra1": {"media": float(np.mean(col1)), "minimo": int(min(col1)),
                                  "maximo": int(max(col1)),
                                  "esperado": float((np.arange(len(pmf)) * pmf).sum())},
            "planejado_amostra1": _decisao_json(d_plan),
            "corrigido": {"amostra1": _decisao_json(d1),
                          "amostra2": _decisao_json(d2) if d2 else None,
                          "reprovacao_sistematica": segundo_nivel.reprovacao_sistematica(d1, d2)},
        }
        print(rotulo, "reproduz:", reproduz, "| corrigido aprovado:", d1.aprovado,
              "| sistemática:", resultado[rotulo]["corrigido"]["reprovacao_sistematica"])
    destino = saida / "portaria_p7_corrigido.json"
    destino.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"resultados em {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
