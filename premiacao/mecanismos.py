"""Mecanismos de premiação simulados (Capítulo 2, Equação 1; Delimitação)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Mecanismo:
    """Associa a um inteiro u em {0, ..., intervalo - 1} um resultado.

    Sem pesos, o resultado é o próprio u (sorteio entre `intervalo`
    participantes). Com pesos inteiros, o item é escolhido pelo método da
    inversão, e os pesos devem somar `intervalo`.
    """

    nome: str
    intervalo: int
    pesos: tuple[int, ...] | None = None

    def __post_init__(self) -> None:
        if self.intervalo < 2:
            raise ValueError("o intervalo deve ter ao menos dois valores")
        if self.pesos is not None:
            if any(p < 0 for p in self.pesos) or sum(self.pesos) != self.intervalo:
                raise ValueError("os pesos devem ser não negativos e somar o intervalo")

    @property
    def categorias(self) -> int:
        return self.intervalo if self.pesos is None else len(self.pesos)

    @property
    def probabilidades(self) -> list[float]:
        if self.pesos is None:
            return [1 / self.intervalo] * self.intervalo
        return [p / self.intervalo for p in self.pesos]

    def resultado(self, u: int) -> int:
        """Equação (1): item j tal que soma(w_1..w_{j-1}) <= u < soma(w_1..w_j)."""
        if not 0 <= u < self.intervalo:
            raise ValueError("u fora do intervalo")
        if self.pesos is None:
            return u
        acumulado = 0
        for item, peso in enumerate(self.pesos):
            acumulado += peso
            if u < acumulado:
                return item
        raise AssertionError("inalcançável: os pesos somam o intervalo")

    def como_dict(self) -> dict:
        return {"nome": self.nome, "intervalo": self.intervalo,
                "pesos": list(self.pesos) if self.pesos is not None else None}


# Mecanismos definidos na Delimitação (Capítulo 1). Itens numerados a partir de 0:
# item 0 = 50%, 1 = 30%, 2 = 15%, 3 = 4%, 4 = 1%.
SORTEIO = Mecanismo("sorteio", 100)
CAIXA = Mecanismo("caixa", 100, (50, 30, 15, 4, 1))
