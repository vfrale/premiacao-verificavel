"""Testes listados na Portaria SPA/MF nº 722/2024 (Capítulo 4, Quadro 7).

Cada função recebe uma sequência U_0, ..., U_{n-1} de uniformes em [0, 1)
e devolve o valor-p de primeiro nível. Operacionalização baseada nos testes
empíricos de Knuth (1997, seção 3.3.2), em Good (1953) e em Box e Pierce (1970).
"""

from __future__ import annotations

from functools import lru_cache
from math import comb, factorial, sqrt

import numpy as np
from scipy import stats


def p1_equidistribuicao(u: np.ndarray, d: int = 100) -> float:
    """P1 - distribuição total / qui-quadrado: Y = floor(d U) em d categorias."""
    y = np.floor(u * d).astype(np.int64)
    obs = np.bincount(y, minlength=d)
    esp = len(u) / d
    return float(stats.chi2.sf(((obs - esp) ** 2 / esp).sum(), d - 1))


def _psi2(indices: np.ndarray, celulas: int) -> float:
    obs = np.bincount(indices, minlength=celulas)
    esp = len(indices) / celulas
    return float(((obs - esp) ** 2 / esp).sum())


def p2_sobreposicao(u: np.ndarray, d: int = 16) -> float:
    """P2 - teste serial com triplas sobrepostas (circulares); estatística de Good."""
    y = np.floor(u * d).astype(np.int64)
    y1, y2 = np.roll(y, -1), np.roll(y, -2)
    psi3 = _psi2(y * d * d + y1 * d + y2, d ** 3)
    psi2 = _psi2(y * d + y1, d ** 2)
    return float(stats.chi2.sf(psi3 - psi2, d ** 3 - d ** 2))


def _stirling2(n: int, k: int) -> int:
    return sum((-1) ** i * comb(k, i) * (k - i) ** n for i in range(k + 1)) // factorial(k)


def _prob_coletor(d: int, t: int) -> np.ndarray:
    p = [factorial(d) / d ** r * _stirling2(r - 1, d - 1) for r in range(d, t)]
    p.append(1 - factorial(d) / d ** (t - 1) * _stirling2(t - 1, d))
    return np.array(p)


def p3_coletor(u: np.ndarray, d: int = 5, t: int = 20) -> float:
    """P3 - coletor de cupons: comprimentos de segmento d..t-1 e >= t."""
    y = np.floor(u * d).astype(np.int64)
    n = len(y)
    posicoes = np.arange(n)
    # proxima[v][i] = menor índice >= i em que y == v (n se não houver)
    proxima = []
    for v in range(d):
        idx = np.where(y == v, posicoes, n)
        proxima.append(np.minimum.accumulate(idx[::-1])[::-1])
    fim_segmento = np.max(np.vstack(proxima), axis=0)
    contagem = np.zeros(t - d + 1, dtype=np.int64)
    i = 0
    while i < n:
        fim = int(fim_segmento[i])
        if fim >= n:
            break  # segmento incompleto no fim da sequência
        r = fim - i + 1
        contagem[min(r, t) - d] += 1
        i = fim + 1
    total = contagem.sum()
    esp = total * _prob_coletor(d, t)
    return float(stats.chi2.sf(((contagem - esp) ** 2 / esp).sum(), t - d))


# Constantes do teste de corridas ascendentes (Knuth, 1997, seção 3.3.2).
_A = np.array([
    [4529.4, 9044.9, 13568, 18091, 22615, 27892],
    [9044.9, 18097, 27139, 36187, 45234, 55789],
    [13568, 27139, 40721, 54281, 67852, 83685],
    [18091, 36187, 54281, 72414, 90470, 111580],
    [22615, 45234, 67852, 90470, 113262, 139476],
    [27892, 55789, 83685, 111580, 139476, 172860],
])
_B = np.array([1 / 6, 5 / 24, 11 / 120, 19 / 720, 29 / 5040, 1 / 840])


def p4_corridas(u: np.ndarray) -> float:
    """P4 - corridas ascendentes de comprimento 1..5 e >= 6 (forma quadrática de Knuth)."""
    n = len(u)
    quebras = np.flatnonzero(u[1:] <= u[:-1]) + 1  # início de cada nova corrida
    limites = np.concatenate(([0], quebras, [n]))
    comprimentos = np.minimum(np.diff(limites), 6)
    r = np.bincount(comprimentos, minlength=7)[1:7].astype(float)
    desvio = r - n * _B
    v = float(desvio @ _A @ desvio) / (n - 6)
    return float(stats.chi2.sf(v, 6))


def _autocorrelacao(u: np.ndarray, k: int) -> float:
    """Coeficiente de correlação serial (Equação 11) na defasagem k, circular."""
    n = len(u)
    s, s2 = u.sum(), (u * u).sum()
    return float((n * (u * np.roll(u, -k)).sum() - s * s) / (n * s2 - s * s))


def p5_correlacao_interacao(u: np.ndarray, defasagens: range = range(2, 11)) -> float:
    """P5 - correlação de interação: Q = n * soma(C_k^2), k = 2..10 (Box; Pierce, 1970)."""
    n = len(u)
    q = n * sum(_autocorrelacao(u, k) ** 2 for k in defasagens)
    return float(stats.chi2.sf(q, len(defasagens)))


def p6_correlacao_serial(u: np.ndarray) -> float:
    """P6 - correlação serial na defasagem 1, com média e desvio de Knuth."""
    n = len(u)
    c = _autocorrelacao(u, 1)
    mu = -1 / (n - 1)
    sigma = sqrt(n * (n - 3) / (n + 1)) / (n - 1)
    return float(2 * stats.norm.sf(abs((c - mu) / sigma)))


def _colisoes(u: np.ndarray, bolas: int, d: int, t: int) -> int:
    y = np.floor(u[: bolas * t] * d).astype(np.int64).reshape(bolas, t)
    indices = y @ (d ** np.arange(t - 1, -1, -1))
    return bolas - len(np.unique(indices))


def p7_duplicacao_poisson(u: np.ndarray, bolas: int = 2 ** 14, d: int = 32, t: int = 4) -> float:
    """P7 na versão planejada (Quadro 7): aproximação de Poisson, valor-p bilateral.

    Mantida para registro. Por ser discreto e bilateral, esse valor-p não é
    uniforme sob H0 (excesso na classe [0,9; 1]), o que faz o critério de
    uniformidade P_T falhar por acaso em cerca de 38% das amostras de
    1.000 sequências (Capítulo 6). A versão usada é p7_duplicacao.
    """
    colisoes = _colisoes(u, bolas, d, t)
    urnas = d ** t
    media = bolas - urnas + urnas * (1 - 1 / urnas) ** bolas
    p = 2 * min(stats.poisson.cdf(colisoes, media), stats.poisson.sf(colisoes - 1, media))
    return float(min(1.0, p))


@lru_cache(maxsize=None)
def distribuicao_colisoes(bolas: int, urnas: int, limite: int = 1024) -> np.ndarray:
    """Distribuição exata do número de colisões de `bolas` bolas em `urnas` urnas.

    Recorrência sobre as bolas: com t bolas lançadas e c colisões, há t - c
    urnas ocupadas, e a bola seguinte colide com probabilidade (t - c)/urnas.
    """
    dist = np.zeros(limite)
    dist[0] = 1.0
    c = np.arange(limite)
    for t in range(bolas):
        pcol = np.clip((t - c) / urnas, 0.0, 1.0)
        nova = dist * (1 - pcol)
        nova[1:] += dist[:-1] * pcol[:-1]
        dist = nova
    return dist


def valor_p_aleatorizado(x: int, pmf: np.ndarray, v: float) -> float:
    """Valor-p bilateral exatamente uniforme sob H0 para estatística discreta.

    V = F(x - 1) + v P(X = x), com v uniforme em [0, 1), é uniforme sob H0
    (transformação integral aleatorizada); o valor-p bilateral é 2 min(V, 1 - V).
    """
    acum = float(pmf[:x].sum()) if x > 0 else 0.0
    w = acum + v * float(pmf[x]) if x < len(pmf) else 1.0
    return float(min(1.0, 2 * min(w, 1 - w)))


def p7_duplicacao(u: np.ndarray, bolas: int = 2 ** 14, d: int = 32, t: int = 4) -> float:
    """P7 - colisões de t-uplas de floor(d U) em d^t urnas; distribuição exata.

    O valor-p é aleatorizado (valor_p_aleatorizado) para que seja uniforme sob
    H0; o desempate v é o valor U seguinte aos usados na contagem, que não
    participa do teste.
    """
    colisoes = _colisoes(u, bolas, d, t)
    return valor_p_aleatorizado(colisoes, distribuicao_colisoes(bolas, d ** t),
                                float(u[bolas * t]))


TESTES = {
    "P1": p1_equidistribuicao,
    "P2": p2_sobreposicao,
    "P3": p3_coletor,
    "P4": p4_corridas,
    "P5": p5_correlacao_interacao,
    "P6": p6_correlacao_serial,
    "P7": p7_duplicacao,
}


def aplicar(u: np.ndarray) -> dict[str, float]:
    """Aplica os sete testes a uma sequência e devolve os valores-p."""
    return {nome: f(u) for nome, f in TESTES.items()}
