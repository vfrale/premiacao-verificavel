"""Primitivas do protocolo provably fair.

Correspondem à Equação (6) e ao Algoritmo 1 do Capítulo 2 do TCC:
o compromisso c = SHA256(s_S) e a derivação de cada resultado por
HMAC-SHA256(s_S, s_C || ":" || n || ":" || j), com conversão sem viés
pelo método de descarte (NIST SP 800-90A, apêndice A.5.1).
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

TAMANHO_SEMENTE = 32  # bytes (256 bits)
SEPARADOR = ":"


def gerar_semente_servidor() -> bytes:
    """Gera a semente secreta do servidor com o CSPRNG do sistema."""
    return secrets.token_bytes(TAMANHO_SEMENTE)


def gerar_semente_participante() -> str:
    """Simula a semente que o participante fornece após o compromisso."""
    return secrets.token_hex(16)


def compromisso(semente_servidor: bytes) -> str:
    """Compromisso publicado antes do ciclo: SHA-256 da semente, em hexadecimal."""
    return hashlib.sha256(semente_servidor).hexdigest()


def mensagem(semente_participante: str, evento: int, subcontador: int) -> bytes:
    """Codifica s_C || ":" || n || ":" || j em UTF-8.

    A codificação é injetiva mesmo que s_C contenha ":", pois n e j são
    inteiros decimais sem separador: lida da direita para a esquerda, a
    cadeia determina j, n e s_C de forma única.
    """
    if evento < 0 or subcontador < 0:
        raise ValueError("evento e subcontador devem ser não negativos")
    return f"{semente_participante}{SEPARADOR}{evento}{SEPARADOR}{subcontador}".encode("utf-8")


def amostra(semente_servidor: bytes, semente_participante: str,
            evento: int, subcontador: int = 0) -> bytes:
    """Saída de 256 bits do HMAC-SHA256 para o evento n e o subcontador j."""
    return hmac.digest(semente_servidor,
                       mensagem(semente_participante, evento, subcontador),
                       "sha256")


def reduzir(valor: int, intervalo: int, bits: int) -> int | None:
    """Passo do método de descarte: devolve valor mod N ou None se descartado."""
    limite = ((1 << bits) // intervalo) * intervalo
    return valor % intervalo if valor < limite else None


def converter(semente_servidor: bytes, semente_participante: str, evento: int,
              intervalo: int, bits: int = 32) -> int:
    """Algoritmo 1: inteiro uniforme em {0, ..., intervalo - 1} para o evento n."""
    if intervalo < 2:
        raise ValueError("o intervalo deve ter ao menos dois valores")
    if bits % 8 != 0 or not 8 <= bits <= 256:
        raise ValueError("bits deve ser múltiplo de 8, entre 8 e 256")
    if intervalo > (1 << bits):
        raise ValueError("intervalo maior que o número de valores representáveis")
    subcontador = 0
    while True:
        bruto = amostra(semente_servidor, semente_participante, evento, subcontador)
        valor = int.from_bytes(bruto[: bits // 8], "big")
        resultado = reduzir(valor, intervalo, bits)
        if resultado is not None:
            return resultado
        subcontador += 1  # valor descartado: nova amostra com j + 1
