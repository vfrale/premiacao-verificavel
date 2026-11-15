"""Os três geradores comparados (Capítulo 4, Quadro 5).

Cada gerador oferece as três formas de dado usadas nos experimentos:
bits (bateria NIST), uniformes U_j em [0, 1) (testes da Portaria) e
inteiros em {0, ..., N-1} (mecanismos de premiação).
"""

from __future__ import annotations

import random
import secrets

import numpy as np

from premiacao.protocolo import amostra, converter

TAM_SEQ_BYTES = 125_000  # 10^6 bits


class GeradorHMAC:
    """G-HMAC: saídas HMAC-SHA256(s_S, s_C || ':' || n || ':' || 0), n = 0, 1, ..."""

    nome = "G-HMAC"

    def __init__(self, semente_servidor: bytes | None = None,
                 semente_participante: str | None = None) -> None:
        self.semente_servidor = semente_servidor or secrets.token_bytes(32)
        self.semente_participante = semente_participante or secrets.token_hex(16)

    def semente(self) -> dict:
        return {"semente_servidor": self.semente_servidor.hex(),
                "semente_participante": self.semente_participante}

    def _bloco(self, n: int) -> bytes:
        return amostra(self.semente_servidor, self.semente_participante, n, 0)

    def bytes_(self, quantidade: int) -> bytes:
        blocos = -(-quantidade // 32)
        return b"".join(self._bloco(n) for n in range(blocos))[:quantidade]

    def palavras(self, k: int) -> np.ndarray:
        return np.frombuffer(self.bytes_(4 * k), dtype=">u4").astype(np.uint64)

    def bits(self, n_bits: int = 1_000_000) -> bytes:
        return self.bytes_(n_bits // 8)

    def uniformes(self, k: int) -> np.ndarray:
        return self.palavras(k) / 2.0**32

    def inteiro_evento(self, evento: int, intervalo: int) -> int:
        """Algoritmo 1 (b = 32): exatamente o que o protótipo usa."""
        return converter(self.semente_servidor, self.semente_participante, evento, intervalo, 32)

    def inteiros(self, k: int, intervalo: int) -> list[int]:
        return [self.inteiro_evento(n, intervalo) for n in range(k)]


class GeradorMT:
    """G-MT: MT19937 do módulo random (getrandbits(32))."""

    nome = "G-MT"

    def __init__(self, semente: int | None = None) -> None:
        self.semente_int = semente if semente is not None else secrets.randbits(128)
        self._rng = random.Random(self.semente_int)

    def semente(self) -> dict:
        return {"semente": str(self.semente_int)}

    def palavras(self, k: int) -> np.ndarray:
        g = self._rng.getrandbits
        return np.fromiter((g(32) for _ in range(k)), dtype=np.uint64, count=k)

    def bits(self, n_bits: int = 1_000_000) -> bytes:
        return self.palavras(n_bits // 32).astype(">u4").tobytes()

    def uniformes(self, k: int) -> np.ndarray:
        return self.palavras(k) / 2.0**32

    def inteiros(self, k: int, intervalo: int) -> list[int]:
        """Descarte sobre os bits mais significativos (igual a random.randrange)."""
        largura = intervalo.bit_length()
        g = self._rng.getrandbits
        saida = []
        while len(saida) < k:
            v = g(32) >> (32 - largura)
            if v < intervalo:
                saida.append(v)
        return saida


class GeradorRANDU:
    """G-RANDU: x_{i+1} = 65539 x_i mod 2^31, semente ímpar; saídas x_1, x_2, ..."""

    nome = "G-RANDU"
    A = 65539
    M = 1 << 31
    _potencias: np.ndarray | None = None

    def __init__(self, semente: int | None = None) -> None:
        s = semente if semente is not None else secrets.randbits(31)
        self.semente_int = (s | 1) % self.M
        self._estado = self.semente_int

    def semente(self) -> dict:
        return {"semente": str(self.semente_int)}

    @classmethod
    def _tabela(cls, k: int) -> np.ndarray:
        """a^i mod 2^31, i = 1..k (calculado uma vez e reutilizado)."""
        if cls._potencias is None or len(cls._potencias) < k:
            p = np.empty(k, dtype=np.uint64)
            v = 1
            for i in range(k):
                v = (v * cls.A) % cls.M
                p[i] = v
            cls._potencias = p
        return cls._potencias[:k]

    def saidas(self, k: int) -> np.ndarray:
        """Próximas k saídas (31 bits), vetorizadas por x_i = a^i x_0 mod 2^31."""
        p = self._tabela(k)
        x = (p * np.uint64(self._estado)) % np.uint64(self.M)
        self._estado = int(x[-1])
        return x

    def bits(self, n_bits: int = 1_000_000, representacao: str = "R31") -> bytes:
        if representacao == "R31":
            k = -(-n_bits // 31)
            x = self.saidas(k)
            desloc = np.arange(30, -1, -1, dtype=np.uint64)
            matriz = ((x[:, None] >> desloc) & np.uint64(1)).astype(np.uint8)
            return np.packbits(matriz.ravel()[:n_bits]).tobytes()
        if representacao == "R16":
            x = self.saidas(n_bits // 16)
            return (x >> np.uint64(15)).astype(">u2").tobytes()
        raise ValueError("representação deve ser R31 ou R16")

    def uniformes(self, k: int) -> np.ndarray:
        return self.saidas(k) / float(self.M)

    def inteiros(self, k: int, intervalo: int) -> list[int]:
        """Descarte sobre os bits mais significativos de x (evita o bit constante)."""
        largura = intervalo.bit_length()
        saida: list[int] = []
        while len(saida) < k:
            v = (self.saidas(max(2 * (k - len(saida)), 16)) >> np.uint64(31 - largura)).astype(np.int64)
            saida.extend(int(t) for t in v[v < intervalo])
        return saida[:k]


GERADORES = {"G-HMAC": GeradorHMAC, "G-MT": GeradorMT, "G-RANDU": GeradorRANDU}
