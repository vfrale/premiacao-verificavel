"""Experimento 3: cenários de manipulação C0-C5 (Capítulo 4, Quadro 6 e Algoritmo 3)."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field

from premiacao.mecanismos import CAIXA, Mecanismo
from premiacao.operador import registro_publico
from premiacao.protocolo import compromisso, converter, gerar_semente_participante
from verificador import verificar

EVENTOS = 100
CANDIDATAS = 1000
SEMENTE_PADRAO = "0"               # valor padrão do participante em C4a
PESOS_DIVERGENTES = (50, 30, 15, 5, 0)  # C3: item de 1% transferido ao de 4%
BITS_BAIXA_ENTROPIA = 20           # C5
PARTICIPANTE_CONTROLADO = 0        # C4, sorteio
ITENS_RAROS = (3, 4)               # C4, caixa: itens de 4% e 1%


@dataclass
class Execucao:
    cenario: str
    mecanismo: str
    detectada: bool
    motivo: str
    medidas: dict = field(default_factory=dict)


def _resultados(s_s: bytes, s_c: str, mecanismo: Mecanismo,
                pesos: tuple[int, ...] | None = None) -> list[int]:
    m = mecanismo if pesos is None else Mecanismo(mecanismo.nome, mecanismo.intervalo, pesos)
    return [m.resultado(converter(s_s, s_c, n, m.intervalo)) for n in range(EVENTOS)]


def _pontuacao(resultados: list[int], mecanismo: Mecanismo) -> int:
    """Quanto maior, mais favorável ao operador."""
    if mecanismo.pesos is None:
        return sum(y == PARTICIPANTE_CONTROLADO for y in resultados)
    return -sum(y in ITENS_RAROS for y in resultados)


def _medidas_vantagem(resultados: list[int], mecanismo: Mecanismo) -> dict:
    if mecanismo.pesos is None:
        return {"contemplacoes_controlado": sum(y == PARTICIPANTE_CONTROLADO for y in resultados)}
    return {"itens_raros": sum(y in ITENS_RAROS for y in resultados)}


def _verificar(c: str, revelada: bytes, s_c: str, mecanismo: Mecanismo,
               resultados: list[int]) -> tuple[bool, str]:
    reg = registro_publico(c, revelada, s_c, mecanismo, list(enumerate(resultados)))
    r = verificar(reg)
    return (not r.valido), r.motivo


def executar(cenario: str, mecanismo: Mecanismo, tabela_c5: dict | None = None) -> Execucao:
    """Uma execução do Algoritmo 3 para o cenário dado."""
    medidas: dict = {}
    if cenario == "C5":
        k = secrets.randbelow(1 << BITS_BAIXA_ENTROPIA)
        s_s = k.to_bytes(32, "big")
    elif cenario in ("C4a", "C4b"):
        palpite = SEMENTE_PADRAO  # o operador simula com a semente que espera receber
        candidatas = [secrets.token_bytes(32) for _ in range(CANDIDATAS)]
        s_s = max(candidatas, key=lambda s: _pontuacao(_resultados(s, palpite, mecanismo), mecanismo))
    else:
        s_s = secrets.token_bytes(32)
    c = compromisso(s_s)

    s_c = SEMENTE_PADRAO if cenario == "C4a" else gerar_semente_participante()

    if cenario == "C1":
        s_usada = secrets.token_bytes(32)
        resultados = _resultados(s_usada, s_c, mecanismo)
        revelada = s_usada
    elif cenario == "C3":
        resultados = _resultados(s_s, s_c, mecanismo, PESOS_DIVERGENTES)
        declarados = _resultados(s_s, s_c, mecanismo)
        medidas["eventos_alterados"] = sum(a != b for a, b in zip(resultados, declarados))
        revelada = s_s
    else:
        resultados = _resultados(s_s, s_c, mecanismo)
        revelada = s_s

    if cenario == "C2":
        n = secrets.randbelow(EVENTOS)
        alternativas = [v for v in range(mecanismo.categorias) if v != resultados[n]]
        resultados[n] = alternativas[secrets.randbelow(len(alternativas))]
        medidas["evento_alterado"] = n

    if cenario in ("C4a", "C4b"):
        medidas.update(_medidas_vantagem(resultados, mecanismo))
        medidas["resultados"] = resultados
    if cenario == "C5":
        if tabela_c5 is None:
            raise ValueError("C5 exige a tabela pré-calculada do atacante")
        k_rec = tabela_c5.get(bytes.fromhex(c))
        recuperada = k_rec is not None and k_rec.to_bytes(32, "big") == s_s
        medidas["semente_recuperada"] = recuperada
        if recuperada:  # o terceiro prevê todos os resultados antes da revelação
            medidas["resultados_previstos"] = _resultados(k_rec.to_bytes(32, "big"), s_c, mecanismo) == resultados

    medidas["sementes"] = {"servidor": s_s.hex(), "revelada": revelada.hex(),
                           "participante": s_c}
    detectada, motivo = _verificar(c, revelada, s_c, mecanismo, resultados)
    return Execucao(cenario, mecanismo.nome, detectada, motivo, medidas)


def tabela_atacante_c5() -> dict[bytes, int]:
    """Pré-cálculo do terceiro: SHA-256 de todas as 2^20 sementes possíveis."""
    return {hashlib.sha256(k.to_bytes(32, "big")).digest(): k
            for k in range(1 << BITS_BAIXA_ENTROPIA)}


CENARIOS = {
    "C0": ("sorteio", "caixa"), "C1": ("sorteio", "caixa"), "C2": ("sorteio", "caixa"),
    "C3": ("caixa",), "C4a": ("sorteio", "caixa"), "C4b": ("sorteio", "caixa"), "C5": ("caixa",),
}
ESPERADO = {"C0": 0.0, "C1": 1.0, "C2": 1.0, "C3": 1 - 0.99 ** EVENTOS,
            "C4a": 0.0, "C4b": 0.0, "C5": 0.0}
