"""Análise complementar do Experimento 3 a partir do registro de sementes.

Recalcula, para C0, C4a e C4b, a medida de vantagem de cada execução (itens
raros na caixa; contemplações do participante controlado no sorteio), confere
as médias registradas em cenarios.json, compara-as com os valores teóricos e
calcula os intervalos de 95% de Clopper-Pearson das taxas de detecção.

  python -m avaliacao.analise_cenarios --saida resultados
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

from premiacao.mecanismos import CAIXA, SORTEIO

from . import cenarios

MECANISMOS = {"sorteio": SORTEIO, "caixa": CAIXA}


def clopper_pearson(x: int, n: int, nivel: float = 0.95) -> tuple[float, float]:
    a = 1 - nivel
    lo = 0.0 if x == 0 else float(stats.beta.ppf(a / 2, x, n - x + 1))
    hi = 1.0 if x == n else float(stats.beta.ppf(1 - a / 2, x + 1, n - x))
    return lo, hi


def teoricos(mecanismo: str, k: int = cenarios.CANDIDATAS, eventos: int = cenarios.EVENTOS) -> dict:
    """Distribuição da medida sob execução honesta e sob escolha entre k candidatas."""
    p = 0.01 if mecanismo == "sorteio" else 0.05  # participante 0; itens de 4% e 1%
    x = np.arange(eventos + 1)
    honesta = stats.binom.pmf(x, eventos, p)
    cdf = stats.binom.cdf(x, eventos, p)
    if mecanismo == "sorteio":   # o operador maximiza: máximo de k binomiais
        escolhida = np.diff(np.concatenate([[0.0], cdf ** k]))
    else:                        # o operador minimiza: mínimo de k binomiais
        sobrev = 1 - np.concatenate([[0.0], cdf[:-1]])   # P(X >= x)
        escolhida = sobrev ** k - np.concatenate([sobrev[1:], [0.0]]) ** k
    return {"honesta": honesta, "escolhida": escolhida,
            "media_honesta": float((x * honesta).sum()),
            "media_escolhida": float((x * escolhida).sum())}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--saida", default="resultados")
    args = p.parse_args(argv)
    saida = Path(args.saida)
    resumo = json.loads((saida / "cenarios.json").read_text(encoding="utf-8"))["resultados"]

    medidas: dict[str, list[int]] = defaultdict(list)
    c3 = {"execucoes": 0, "alterados": [], "deteccao_coincide": 0}
    for texto in open(saida / "sementes.jsonl", encoding="utf-8"):
        d = json.loads(texto)
        if d.get("experimento") != "cenarios":
            continue
        mec = MECANISMOS[d["mecanismo"]]
        if d["cenario"] == "C3":  # eventos em que w' produziu item diferente do declarado
            s_s = bytes.fromhex(d["servidor"])
            usados = cenarios._resultados(s_s, d["participante"], mec, cenarios.PESOS_DIVERGENTES)
            declarados = cenarios._resultados(s_s, d["participante"], mec)
            alterados = sum(a != b for a, b in zip(usados, declarados))
            c3["execucoes"] += 1
            c3["alterados"].append(alterados)
            c3["deteccao_coincide"] += d["detectada"] == (alterados > 0)
            continue
        if d["cenario"] not in ("C0", "C4a", "C4b"):
            continue
        res = cenarios._resultados(bytes.fromhex(d["servidor"]), d["participante"], mec)
        medida = cenarios._medidas_vantagem(res, mec)
        medidas[f'{d["cenario"]}/{d["mecanismo"]}'].append(next(iter(medida.values())))

    saida_json: dict = {"deteccao": {}, "vantagem": {}}
    for chave, r in resumo.items():
        lo, hi = clopper_pearson(r["deteccoes"], r["execucoes"])
        saida_json["deteccao"][chave] = {"deteccoes": r["deteccoes"], "execucoes": r["execucoes"],
                                         "taxa": r["taxa"], "ic95": [lo, hi], "esperado": r["esperado"]}
    for chave, valores in sorted(medidas.items()):
        cen, mec = chave.split("/")
        teo = teoricos(mec)
        registrada = resumo[chave].get("vantagem_media")
        saida_json["vantagem"][chave] = {
            "media": float(np.mean(valores)),
            "confere_com_registro": bool(registrada is None or abs(np.mean(valores) - registrada) < 1e-12),
            "distribuicao": dict(sorted(Counter(valores).items())),
            "media_teorica_honesta": teo["media_honesta"],
            "media_teorica_escolha": teo["media_escolhida"] if cen == "C4a" else None,
        }
    saida_json["c3"] = {"execucoes": c3["execucoes"],
                        "media_eventos_alterados": float(np.mean(c3["alterados"])),
                        "ciclos_sem_alteracao": int(sum(a == 0 for a in c3["alterados"])),
                        "deteccao_coincide_com_alteracao": c3["deteccao_coincide"]}
    inicio = time.time()
    cenarios.tabela_atacante_c5()
    saida_json["c5_tempo_tabela_s"] = round(time.time() - inicio, 2)

    destino = saida / "cenarios_analise.json"
    destino.write_text(json.dumps(saida_json, indent=2, ensure_ascii=False), encoding="utf-8")
    for chave, v in saida_json["vantagem"].items():
        print(chave, round(v["media"], 3), "confere:", v["confere_com_registro"],
              "| teórico honesto", round(v["media_teorica_honesta"], 3),
              "| teórico escolha", v["media_teorica_escolha"] and round(v["media_teorica_escolha"], 3))
    print("C3:", saida_json["c3"])
    print("tabela C5:", saida_json["c5_tempo_tabela_s"], "s; resultados em", destino)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
