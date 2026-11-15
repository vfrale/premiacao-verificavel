"""Integração com a implementação de referência da bateria NIST SP 800-22 (STS 2.1.2).

O STS não é distribuído com este repositório: deve ser obtido no sítio do NIST
e compilado (make) no diretório indicado em --sts. Este módulo (i) grava as
sequências no formato binário aceito pelo STS, (ii) executa o programa `assess`
respondendo aos seus menus e (iii) lê o relatório finalAnalysisReport.txt,
recalculando os critérios de segundo nível com a regra da subseção 4.6.4.
"""

from __future__ import annotations

import re
import subprocess
from collections import defaultdict
from pathlib import Path

from .segundo_nivel import Estatistica, combinar, uniformidade_de_contagens

N_BITS = 1_000_000


def gravar_binario(geradores, caminho: Path, **kwargs) -> None:
    """Grava as sequências concatenadas (10^6 bits = 125.000 bytes cada)."""
    with open(caminho, "wb") as f:
        for g in geradores:
            dados = g.bits(N_BITS, **kwargs)
            assert len(dados) == N_BITS // 8
            f.write(dados)


def executar_assess(dir_sts: Path, arquivo: Path, sequencias: int) -> Path:
    """Executa `assess` com todos os testes e parâmetros padrão; leitura binária."""
    respostas = "\n".join([
        "0",                      # gerador: arquivo de entrada
        str(arquivo.resolve()),   # caminho do arquivo
        "1",                      # aplicar todos os testes
        "0",                      # manter os parâmetros padrão
        str(sequencias),          # número de sequências
        "1",                      # formato binário
    ]) + "\n"
    relatorio = dir_sts / "experiments" / "AlgorithmTesting" / "finalAnalysisReport.txt"
    relatorio.unlink(missing_ok=True)
    # o assess do STS 2.1.2 termina com código 1 mesmo em execução normal;
    # o sucesso é aferido pela presença do relatório
    subprocess.run([str(dir_sts / "assess"), str(N_BITS)], input=respostas, text=True,
                   cwd=dir_sts, check=False, stdout=subprocess.DEVNULL)
    if not relatorio.exists():
        raise RuntimeError("o STS não gerou o finalAnalysisReport.txt")
    return relatorio


# "------" no lugar da proporção: nenhuma sequência elegível (m' = 0) nos testes
# de excursões aleatórias
_LINHA = re.compile(r"^\s*((?:\d+\s+){10})\S+\s+\*?\s*(?:(\d+)\s*/\s*(\d+)|-{6})\s*\*?\s+(\w+)")


def ler_relatorio(caminho: Path) -> dict[str, list[Estatistica]]:
    """Lê o finalAnalysisReport.txt e devolve as estatísticas agrupadas por teste.

    P_T é recalculado a partir das 10 contagens (Equação 9), e a proporção a
    partir de aprovadas/total, sem depender das marcações do próprio STS.
    """
    por_teste: dict[str, list[Estatistica]] = defaultdict(list)
    for linha in Path(caminho).read_text(errors="replace").splitlines():
        m = _LINHA.match(linha)
        if not m:
            continue
        contagens = tuple(int(v) for v in m.group(1).split())
        aprovadas, total, teste = int(m.group(2) or 0), int(m.group(3) or 0), m.group(4)
        nome = f"{teste}#{len(por_teste[teste]) + 1}"
        por_teste[teste].append(Estatistica(nome, aprovadas, total,
                                            uniformidade_de_contagens(contagens), contagens))
    return dict(por_teste)


def executar_em_paralelo(dirs_sts: list[Path], arquivos: list[Path], sequencias: list[int],
                         destino_base: Path) -> dict[str, list[Estatistica]]:
    """Executa o STS em partes disjuntas (uma cópia do STS por parte) e combina os relatórios."""
    from concurrent.futures import ThreadPoolExecutor

    def tarefa(i: int) -> dict[str, list[Estatistica]]:
        rel = executar_assess(dirs_sts[i], arquivos[i], sequencias[i])
        copia = destino_base.with_name(f"{destino_base.name}_parte{i + 1}_finalAnalysisReport.txt")
        copia.write_text(rel.read_text(errors="replace"))
        return ler_relatorio(copia)

    with ThreadPoolExecutor(max_workers=len(dirs_sts)) as ex:
        partes = list(ex.map(tarefa, range(len(dirs_sts))))
    return {t: [combinar([p[t][k] for p in partes]) for k in range(len(partes[0][t]))]
            for t in partes[0]}
