"""Critérios de segundo nível e regra de decisão (Capítulo 4, subseção 4.6.4)."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

import numpy as np
from scipy import stats

ALFA = 0.01
LIMIAR_UNIFORMIDADE = 0.0001
NIVEL_TOLERANCIA = 0.01


def intervalo_proporcao(m: int, alfa: float = ALFA) -> tuple[float, float]:
    """Equação (8): p ± 3 sqrt(p(1-p)/m), com p = 1 - alfa."""
    p = 1 - alfa
    meia = 3 * sqrt(p * (1 - p) / m)
    return p - meia, p + meia


def uniformidade(pvalores: np.ndarray) -> float:
    """Equação (9): qui-quadrado em 10 classes de [0, 1]; P_T = igamc(9/2, chi2/2)."""
    pv = np.asarray(pvalores, dtype=float)
    classes = np.minimum((pv * 10).astype(int), 9)
    obs = np.bincount(classes, minlength=10)
    esp = len(pv) / 10
    return float(stats.chi2.sf(((obs - esp) ** 2 / esp).sum(), 9))


@dataclass(frozen=True)
class Estatistica:
    nome: str
    aprovadas: int
    total: int
    p_t: float
    contagens: tuple[int, ...] | None = None  # 10 classes de valores-p (relatório do STS)

    @property
    def proporcao(self) -> float:
        return self.aprovadas / self.total if self.total else float("nan")

    @property
    def aprovada(self) -> bool:
        if self.total == 0:  # m' = 0: o critério de proporção não pode ser satisfeito
            return False
        lo, hi = intervalo_proporcao(self.total)
        return lo <= self.proporcao <= hi and self.p_t >= LIMIAR_UNIFORMIDADE


def uniformidade_de_contagens(contagens) -> float:
    """Equação (9) a partir das contagens das 10 classes."""
    obs = np.asarray(contagens, dtype=float)
    esp = obs.sum() / 10
    return float(stats.chi2.sf(((obs - esp) ** 2 / esp).sum(), 9)) if esp > 0 else 0.0


def combinar(partes: list[Estatistica]) -> Estatistica:
    """Soma estatísticas de subconjuntos disjuntos de sequências (exato)."""
    contagens = tuple(int(v) for v in np.sum([e.contagens for e in partes], axis=0))
    return Estatistica(partes[0].nome, sum(e.aprovadas for e in partes),
                       sum(e.total for e in partes), uniformidade_de_contagens(contagens),
                       contagens)


def estatistica_de_pvalores(nome: str, pvalores, alfa: float = ALFA) -> Estatistica:
    pv = np.asarray(pvalores, dtype=float)
    return Estatistica(nome, int((pv >= alfa).sum()), len(pv), uniformidade(pv))


def q_falha(m: int, alfa: float = ALFA) -> float:
    """Equação (13): probabilidade de uma estatística falhar por acaso sob H0."""
    lo, hi = intervalo_proporcao(m, alfa)
    x = np.arange(m + 1)
    pmf = stats.binom.pmf(x, m, 1 - alfa)
    q_prop = float(pmf[(x / m < lo) | (x / m > hi)].sum())
    return q_prop + LIMIAR_UNIFORMIDADE - q_prop * LIMIAR_UNIFORMIDADE


def tolerancia(k: int, q: float, nivel: float = NIVEL_TOLERANCIA) -> int:
    """Equação (14): menor c tal que P(Binomial(K, q) > c) <= nivel.

    Limitado a K - 1 para que o teste possa ser reprovado mesmo em amostras
    pequenas (com m = 1.000, o limite nunca é atingido).
    """
    for c in range(k):
        if stats.binom.sf(c, k, q) <= nivel:
            return c
    return k - 1


@dataclass(frozen=True)
class DecisaoTeste:
    teste: str
    estatisticas: tuple[Estatistica, ...]
    q: float
    c_k: int

    @property
    def reprovadas(self) -> int:
        return sum(not e.aprovada for e in self.estatisticas)

    @property
    def aprovado(self) -> bool:
        return self.reprovadas <= self.c_k


def decidir(teste: str, estatisticas: list[Estatistica]) -> DecisaoTeste:
    """Segundo passo da regra: o teste é aprovado se F <= c_K."""
    m = max(1, min(e.total for e in estatisticas))  # m' nos testes de excursões aleatórias
    q = q_falha(m)
    return DecisaoTeste(teste, tuple(estatisticas), q, tolerancia(len(estatisticas), q))


def reprovacao_sistematica(primeira: DecisaoTeste, replicacao: DecisaoTeste | None) -> bool:
    """Terceiro passo: só há reprovação se ela se repetir na amostra independente."""
    if primeira.aprovado:
        return False
    if replicacao is None:
        raise ValueError("teste reprovado: a replicação é obrigatória")
    return not replicacao.aprovado
