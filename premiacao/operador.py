"""Lado do operador: compromisso, ciclo de eventos, revelação e publicação."""

from __future__ import annotations

from .mecanismos import Mecanismo
from .protocolo import compromisso, converter, gerar_semente_servidor

VERSAO_REGISTRO = 1


class Operador:
    """Executa um ciclo do protocolo para um mecanismo de premiação."""

    def __init__(self, mecanismo: Mecanismo, semente_servidor: bytes | None = None,
                 bits: int = 32) -> None:
        self.mecanismo = mecanismo
        self.bits = bits
        self._semente = semente_servidor if semente_servidor is not None else gerar_semente_servidor()
        self.compromisso = compromisso(self._semente)  # publicado antes do ciclo

    def resultado(self, semente_participante: str, evento: int) -> int:
        u = converter(self._semente, semente_participante, evento,
                      self.mecanismo.intervalo, self.bits)
        return self.mecanismo.resultado(u)

    def executar_ciclo(self, semente_participante: str, eventos: int) -> list[tuple[int, int]]:
        return [(n, self.resultado(semente_participante, n)) for n in range(eventos)]

    def revelar(self) -> bytes:
        """Revela a semente ao fim do ciclo."""
        return self._semente


def registro_publico(compromisso_publicado: str, semente_revelada: bytes,
                     semente_participante: str, mecanismo: Mecanismo,
                     eventos: list[tuple[int, int]], bits: int = 32) -> dict:
    """Dados públicos que o participante recebe e entrega ao verificador."""
    return {
        "versao": VERSAO_REGISTRO,
        "compromisso": compromisso_publicado,
        "semente_servidor": semente_revelada.hex(),
        "semente_participante": semente_participante,
        "mecanismo": mecanismo.como_dict(),
        "bits": bits,
        "eventos": [[n, y] for n, y in eventos],
    }
