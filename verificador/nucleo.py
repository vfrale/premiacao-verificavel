"""Verificador independente (Algoritmo 2 do Capítulo 2).

Este módulo NÃO importa o pacote `premiacao`: a especificação do protocolo é
reimplementada aqui a partir do texto do TCC, de modo que um defeito comum ao
gerador e ao verificador não passe despercebido. Usa apenas a biblioteca padrão.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass


@dataclass(frozen=True)
class Resultado:
    valido: bool
    motivo: str
    evento: int | None = None
    conferidos: int = 0


class RegistroInvalido(ValueError):
    """O registro não segue o formato esperado (não é uma manipulação detectada)."""


def _resultado_esperado(s_s: bytes, s_c: str, n: int, intervalo: int,
                        pesos: list[int] | None, bits: int) -> int:
    limite = ((1 << bits) // intervalo) * intervalo
    j = 0
    while True:
        msg = f"{s_c}:{n}:{j}".encode("utf-8")
        r = int.from_bytes(hmac.digest(s_s, msg, "sha256")[: bits // 8], "big")
        if r < limite:
            u = r % intervalo
            break
        j += 1
    if pesos is None:
        return u
    acumulado = 0
    for item, peso in enumerate(pesos):
        acumulado += peso
        if u < acumulado:
            return item
    raise RegistroInvalido("tabela de pesos inconsistente")


def _ler(registro: dict) -> tuple:
    try:
        c = str(registro["compromisso"]).lower()
        s_s = bytes.fromhex(registro["semente_servidor"])
        s_c = str(registro["semente_participante"])
        mec = registro["mecanismo"]
        intervalo = int(mec["intervalo"])
        pesos = None if mec.get("pesos") is None else [int(p) for p in mec["pesos"]]
        bits = int(registro.get("bits", 32))
        eventos = [(int(n), int(y)) for n, y in registro["eventos"]]
    except (KeyError, TypeError, ValueError) as e:
        raise RegistroInvalido(f"registro malformado: {e}") from e
    if len(c) != 64:
        raise RegistroInvalido("o compromisso deve ter 64 dígitos hexadecimais")
    if intervalo < 2 or bits % 8 != 0 or not 8 <= bits <= 256:
        raise RegistroInvalido("parâmetros de conversão inválidos")
    if pesos is not None and (any(p < 0 for p in pesos) or sum(pesos) != intervalo):
        raise RegistroInvalido("os pesos declarados devem somar o intervalo")
    return c, s_s, s_c, intervalo, pesos, bits, eventos


def verificar(registro: dict) -> Resultado:
    """Confere o compromisso e recalcula cada resultado a partir de dados públicos."""
    c, s_s, s_c, intervalo, pesos, bits, eventos = _ler(registro)
    if hashlib.sha256(s_s).hexdigest() != c:
        return Resultado(False, "semente revelada não corresponde ao compromisso")
    vistos: set[int] = set()
    for i, (n, y) in enumerate(eventos):
        if n in vistos:
            return Resultado(False, f"número de evento repetido: {n}", n, i)
        vistos.add(n)
        esperado = _resultado_esperado(s_s, s_c, n, intervalo, pesos, bits)
        if esperado != y:
            return Resultado(False, f"resultado divergente no evento {n}: "
                                    f"publicado {y}, recalculado {esperado}", n, i)
    return Resultado(True, f"{len(eventos)} eventos conferidos", None, len(eventos))
