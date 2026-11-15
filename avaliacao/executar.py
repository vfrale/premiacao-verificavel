"""Execução dos experimentos 1 a 3 (Capítulo 4).

Exemplos:
  python -m avaliacao.executar portaria   --sequencias 1000 --saida resultados/
  python -m avaliacao.executar nist       --sequencias 1000 --sts /opt/sts-2.1.2 --saida resultados/
  python -m avaliacao.executar aderencia  --ciclos 1000 --eventos 10000 --saida resultados/
  python -m avaliacao.executar cenarios   --execucoes 1000 --saida resultados/

Todas as sementes são obtidas do módulo secrets e registradas em sementes.jsonl.
Valores menores de --sequencias, --ciclos e --execucoes servem a execuções de teste.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

import numpy as np

from premiacao.mecanismos import CAIXA, SORTEIO

from . import aderencia, cenarios, nist_sts, portaria, segundo_nivel
from .geradores import GeradorHMAC, GeradorMT, GeradorRANDU

MECANISMOS = {"sorteio": SORTEIO, "caixa": CAIXA}
FONTES = {  # (nome, fábrica do gerador, argumentos de bits())
    "G-HMAC": (GeradorHMAC, {}),
    "G-MT": (GeradorMT, {}),
    "G-RANDU-R31": (GeradorRANDU, {"representacao": "R31"}),
    "G-RANDU-R16": (GeradorRANDU, {"representacao": "R16"}),
}


class Registro:
    """Registro de sementes (uma linha JSON por sequência, ciclo ou execução)."""

    def __init__(self, saida: Path, rotulo: str | None = None) -> None:
        nome = f"sementes_{rotulo}.jsonl" if rotulo else "sementes.jsonl"
        self.arquivo = open(saida / nome, "a", encoding="utf-8", buffering=1)

    def anotar(self, **dados) -> None:
        self.arquivo.write(json.dumps(dados, ensure_ascii=False) + "\n")


def _decisao_json(d: segundo_nivel.DecisaoTeste) -> dict:
    return {"teste": d.teste, "aprovado": d.aprovado, "reprovadas": d.reprovadas,
            "c_k": d.c_k, "q": d.q,
            "estatisticas": [{"nome": e.nome, "proporcao": e.proporcao, "p_t": e.p_t,
                              "total": e.total, "aprovada": e.aprovada}
                             for e in d.estatisticas]}


def _amostra_portaria(nome: str, sequencias: int, valores: int, reg: Registro,
                      amostra: int) -> dict[str, list[float]]:
    fabrica = FONTES[nome][0]
    pvalores: dict[str, list[float]] = {t: [] for t in portaria.TESTES}
    for i in range(sequencias):
        g = fabrica()
        reg.anotar(experimento="portaria", gerador=nome, amostra=amostra, indice=i, **g.semente())
        for t, p in portaria.aplicar(g.uniformes(valores)).items():
            pvalores[t].append(p)
    return pvalores


def experimento_portaria(args, reg: Registro) -> dict:
    saida = {}
    for nome in ("G-HMAC", "G-MT", "G-RANDU-R31"):  # U_j = x_j / 2^31 não depende de R31/R16
        rotulo = "G-RANDU" if nome.startswith("G-RANDU") else nome
        decisoes = {}
        primeira = _amostra_portaria(nome, args.sequencias, args.valores, reg, 1)
        for t, pv in primeira.items():
            d1 = segundo_nivel.decidir(t, [segundo_nivel.estatistica_de_pvalores(t, pv)])
            d2 = None
            if not d1.aprovado:  # terceiro passo: replicação em amostra independente
                rep = _amostra_portaria(nome, args.sequencias, args.valores, reg, 2)
                d2 = segundo_nivel.decidir(t, [segundo_nivel.estatistica_de_pvalores(t, rep[t])])
            decisoes[t] = {"amostra1": _decisao_json(d1),
                           "amostra2": _decisao_json(d2) if d2 else None,
                           "reprovacao_sistematica": segundo_nivel.reprovacao_sistematica(d1, d2)}
        saida[rotulo] = decisoes
    return saida


def _amostra_nist(nome: str, args, reg: Registro, amostra: int):
    """Gera m sequências, grava os arquivos binários e, se houver STS, executa a bateria.

    Com k diretórios em --sts, as sequências são divididas em k partes disjuntas,
    avaliadas em paralelo e combinadas pela soma exata das contagens.
    """
    fabrica, kw = FONTES[nome]
    dirs = [Path(d) for d in (args.sts or [])]
    k = max(1, len(dirs))
    tamanhos = [args.sequencias // k + (1 if i < args.sequencias % k else 0) for i in range(k)]
    base = Path(args.saida) / f"{nome}_amostra{amostra}"
    arquivos, indice = [], 0
    for parte, tam in enumerate(tamanhos):
        geradores = []
        for _ in range(tam):
            g = fabrica()
            reg.anotar(experimento="nist", gerador=nome, amostra=amostra, indice=indice,
                       parte=parte + 1, **g.semente())
            geradores.append(g)
            indice += 1
        arq = base.with_name(f"{base.name}_parte{parte + 1}.bin")
        nist_sts.gravar_binario(geradores, arq, **kw)
        arquivos.append(arq)
    if not dirs:
        return [str(a) for a in arquivos], None
    return [str(a) for a in arquivos], nist_sts.executar_em_paralelo(dirs, arquivos, tamanhos, base)


def experimento_nist(args, reg: Registro) -> dict:
    """Bateria NIST com a regra de três passos, incluída a replicação dos testes reprovados."""
    saida = {}
    for nome in args.fontes:
        arquivo, por_teste = _amostra_nist(nome, args, reg, 1)
        saida[nome] = {"arquivos_amostra1": arquivo}
        if por_teste is None:
            continue
        d1 = {t: segundo_nivel.decidir(t, est) for t, est in por_teste.items()}
        d2 = None
        if any(not d.aprovado for d in d1.values()):  # terceiro passo
            arquivo2, por_teste2 = _amostra_nist(nome, args, reg, 2)
            saida[nome]["arquivos_amostra2"] = arquivo2
            d2 = {t: segundo_nivel.decidir(t, est) for t, est in por_teste2.items()}
        saida[nome]["decisoes"] = {
            t: {"amostra1": _decisao_json(d),
                "amostra2": _decisao_json(d2[t]) if d2 and not d.aprovado else None,
                "reprovacao_sistematica": segundo_nivel.reprovacao_sistematica(
                    d, d2[t] if d2 and not d.aprovado else None)}
            for t, d in d1.items()}
    return saida


def experimento_aderencia(args, reg: Registro) -> dict:
    saida: dict = {}
    for nome in ("G-HMAC", "G-MT", "G-RANDU-R31"):
        if nome not in args.fontes:
            continue
        rotulo = "G-RANDU" if nome.startswith("G-RANDU") else nome
        saida[rotulo] = {}
        for mnome, mec in MECANISMOS.items():
            if mnome not in args.mecanismos:
                continue
            pvalores, agregado = [], np.zeros(mec.categorias, dtype=np.int64)
            for i in range(args.ciclos):
                g = FONTES[nome][0]()
                reg.anotar(experimento="aderencia", gerador=rotulo, mecanismo=mnome,
                           indice=i, **g.semente())
                obs = aderencia.frequencias(g, mec, args.eventos)
                agregado += obs
                pvalores.append(aderencia.teste_aderencia(obs, mec))
            d = segundo_nivel.decidir("aderencia", [segundo_nivel.estatistica_de_pvalores(mnome, pvalores)])
            saida[rotulo][mnome] = {"segundo_nivel": _decisao_json(d),
                                    "p_agregado": aderencia.teste_aderencia(agregado, mec),
                                    "frequencias_agregadas": agregado.tolist()}
    return saida


def experimento_cenarios(args, reg: Registro) -> dict:
    tabela = cenarios.tabela_atacante_c5()
    saida: dict = {}
    for cen, mecs in cenarios.CENARIOS.items():
        for mnome in mecs:
            execucoes = []
            for i in range(args.execucoes):
                e = cenarios.executar(cen, MECANISMOS[mnome], tabela)
                execucoes.append(e)
                reg.anotar(experimento="cenarios", cenario=cen, mecanismo=mnome, indice=i,
                           detectada=e.detectada, **e.medidas["sementes"])
            detec = sum(e.detectada for e in execucoes)
            resumo = {"execucoes": len(execucoes), "deteccoes": detec,
                      "taxa": detec / len(execucoes), "esperado": cenarios.ESPERADO[cen],
                      "motivos": Counter(e.motivo.split(":")[0] for e in execucoes).most_common(3)}
            if cen in ("C4a", "C4b"):
                chave = "itens_raros" if mnome == "caixa" else "contemplacoes_controlado"
                resumo["vantagem_media"] = float(np.mean([e.medidas[chave] for e in execucoes]))
                obs = np.bincount([y for e in execucoes for y in e.medidas["resultados"]],
                                  minlength=MECANISMOS[mnome].categorias)
                resumo["p_aderencia_agregado"] = aderencia.teste_aderencia(obs, MECANISMOS[mnome])
            if cen == "C3":
                resumo["media_eventos_alterados"] = float(np.mean([e.medidas["eventos_alterados"] for e in execucoes]))
            if cen == "C5":
                resumo["sementes_recuperadas"] = sum(e.medidas["semente_recuperada"] for e in execucoes)
                resumo["resultados_previstos"] = sum(e.medidas.get("resultados_previstos", False) for e in execucoes)
            saida[f"{cen}/{mnome}"] = resumo
    return saida


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Experimentos do TCC")
    p.add_argument("experimento", choices=["portaria", "nist", "aderencia", "cenarios"])
    p.add_argument("--saida", default="resultados")
    p.add_argument("--sequencias", type=int, default=1000)
    p.add_argument("--valores", type=int, default=100_000)
    p.add_argument("--ciclos", type=int, default=1000)
    p.add_argument("--eventos", type=int, default=10_000)
    p.add_argument("--execucoes", type=int, default=1000)
    p.add_argument("--sts", nargs="+", default=None,
                   help="diretório(s) do STS 2.1.2 compilado; vários = execução em paralelo")
    p.add_argument("--fontes", nargs="+", choices=list(FONTES), default=list(FONTES),
                   help="fontes avaliadas nos experimentos nist e aderencia")
    p.add_argument("--mecanismos", nargs="+", choices=list(MECANISMOS), default=list(MECANISMOS),
                   help="mecanismos avaliados no experimento aderencia")
    p.add_argument("--rotulo", default=None,
                   help="sufixo dos arquivos de saida (execuções em paralelo)")
    args = p.parse_args(argv)

    Path(args.saida).mkdir(parents=True, exist_ok=True)
    reg = Registro(Path(args.saida), args.rotulo)
    inicio = time.time()
    funcao = {"portaria": experimento_portaria, "nist": experimento_nist,
              "aderencia": experimento_aderencia, "cenarios": experimento_cenarios}[args.experimento]
    resultado = {"parametros": vars(args), "resultados": funcao(args, reg),
                 "duracao_s": round(time.time() - inicio, 1)}
    sufixo = f"_{args.rotulo}" if args.rotulo else ""
    destino = Path(args.saida) / f"{args.experimento}{sufixo}.json"
    destino.write_text(json.dumps(resultado, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"{args.experimento}: concluído em {resultado['duracao_s']} s; resultados em {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
