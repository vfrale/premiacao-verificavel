"""Experimento 2: aderência às probabilidades declaradas (Capítulo 4, subseção 4.6.2)."""

from __future__ import annotations

import numpy as np
from scipy import stats

from premiacao.mecanismos import Mecanismo



def frequencias(gerador, mecanismo: Mecanismo, eventos: int) -> np.ndarray:
    """Frequência de cada resultado em um ciclo de `eventos` eventos."""
    # G-HMAC: Algoritmo 1 para n = 0..E-1; G-MT e G-RANDU: descarte sobre os bits altos
    inteiros = gerador.inteiros(eventos, mecanismo.intervalo)
    resultados = [mecanismo.resultado(u) for u in inteiros]
    return np.bincount(resultados, minlength=mecanismo.categorias)


def teste_aderencia(obs: np.ndarray, mecanismo: Mecanismo) -> float:
    """Equação (10): qui-quadrado entre frequências observadas e declaradas."""
    p = np.array(mecanismo.probabilidades)
    esp = obs.sum() * p
    usar = esp > 0  # itens de probabilidade nula não entram na estatística
    v = ((obs[usar] - esp[usar]) ** 2 / esp[usar]).sum()
    return float(stats.chi2.sf(v, usar.sum() - 1))


def poder_minimo(graus: int, n: int, alfa: float = 0.01, poder: float = 0.8) -> float:
    """Menor tamanho de efeito w detectado com o poder dado (qui-quadrado não central)."""
    critico = stats.chi2.ppf(1 - alfa, graus)
    lo, hi = 0.0, 1000.0
    for _ in range(100):
        meio = (lo + hi) / 2
        if stats.ncx2.sf(critico, graus, meio) < poder:
            lo = meio
        else:
            hi = meio
    return (hi / n) ** 0.5
