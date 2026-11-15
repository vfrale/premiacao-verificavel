import random

import numpy as np
import pytest
from scipy import stats

from avaliacao import cenarios, portaria, segundo_nivel
from avaliacao.geradores import GeradorHMAC, GeradorMT, GeradorRANDU
from premiacao import CAIXA, SORTEIO


# ---------------------------------------------------------------- geradores
def test_randu_valores_conhecidos_e_planos():
    x = GeradorRANDU(1).saidas(5).tolist()
    assert x == [65539, 393225, 1769499, 7077969, 26542323]
    y = GeradorRANDU(12345).saidas(1000).astype(object)
    assert all((y[i + 2] - 6 * y[i + 1] + 9 * y[i]) % 2**31 == 0 for i in range(998))
    assert all(v % 2 == 1 for v in y)  # bit menos significativo constante


def test_tamanhos_das_sequencias_binarias():
    assert len(GeradorHMAC().bits()) == 125_000
    assert len(GeradorMT().bits()) == 125_000
    assert len(GeradorRANDU().bits(representacao="R31")) == 125_000
    assert len(GeradorRANDU().bits(representacao="R16")) == 125_000


def test_randu_bits_baixos_constantes():
    # a = 65539 = 3 (mod 8): x mod 8 alterna entre {1, 3} ou entre {5, 7};
    # logo os bits 0 e 2 são constantes, e o bit 1 alterna
    for semente, bit2 in ((1, 0), (5, 1)):
        x = GeradorRANDU(semente).saidas(1000)
        assert set((x & 1).tolist()) == {1} and set(((x >> 2) & 1).tolist()) == {bit2}
        bits = np.unpackbits(np.frombuffer(GeradorRANDU(semente).bits(representacao="R31"), np.uint8))
        assert abs(bits.mean() - (15.5 + bit2) / 31) < 0.003


def test_mt_inteiros_coincidem_com_randrange():
    g = GeradorMT(2026)
    r = random.Random(2026)
    assert g.inteiros(5000, 100) == [r.randrange(100) for _ in range(5000)]


def test_mt_previsto_a_partir_de_624_saidas():
    from avaliacao.previsao_mt import clonar
    palavras = GeradorMT(31337).palavras(2000).tolist()
    clone = clonar(palavras[:624])
    assert [clone.getrandbits(32) for _ in range(2000 - 624)] == palavras[624:]


def test_hmac_inteiros_coincidem_com_o_prototipo():
    from premiacao.protocolo import converter
    g = GeradorHMAC(bytes(32), "p")
    assert g.inteiros(50, 100) == [converter(bytes(32), "p", n, 100) for n in range(50)]


# ---------------------------------------------------------- testes da Portaria
@pytest.mark.parametrize("teste", list(portaria.TESTES))
def test_portaria_valores_p_uniformes_para_fonte_ideal(teste):
    rng = np.random.default_rng(20261105)
    pv = [portaria.TESTES[teste](rng.random(100_000)) for _ in range(60)]
    assert stats.kstest(pv, "uniform").pvalue > 0.001


def test_portaria_p2_detecta_os_planos_do_randu():
    assert portaria.p2_sobreposicao(GeradorRANDU().uniformes(100_000)) < 1e-10


def test_p7_valor_p_exato_e_uniforme_e_o_planejado_nao():
    # contagens de colisões sorteadas da distribuição exata sob H0
    pmf = portaria.distribuicao_colisoes(2**14, 2**20)
    assert abs(pmf.sum() - 1) < 1e-9 and abs((np.arange(len(pmf)) * pmf).sum() - 127.328) < 0.001
    rng = np.random.default_rng(7)
    x = np.searchsorted(np.cumsum(pmf), rng.random(50_000))
    corrigido = [portaria.valor_p_aleatorizado(int(c), pmf, v) for c, v in zip(x, rng.random(50_000))]
    assert stats.kstest(corrigido, "uniform").pvalue > 0.001
    media = 2**14 - 2**20 + 2**20 * (1 - 2**-20) ** (2**14)
    planejado = np.minimum(1, 2 * np.minimum(stats.poisson.cdf(x, media), stats.poisson.sf(x - 1, media)))
    assert np.mean(planejado >= 0.9) > 0.12  # excesso na classe superior: P_T falha por acaso


# ------------------------------------------------------------ regra de decisão
def test_intervalo_q_e_tolerancias():
    lo, hi = segundo_nivel.intervalo_proporcao(1000)
    assert round(lo, 4) == 0.9806 and round(hi, 4) == 0.9994
    q = segundo_nivel.q_falha(1000)
    assert abs(q - 0.0034) < 0.0001
    assert [segundo_nivel.tolerancia(k, q) for k in (1, 2, 8, 18, 148)] == [0, 0, 1, 1, 3]


def test_reprovacao_exige_replicacao():
    ruim = segundo_nivel.decidir("T", [segundo_nivel.Estatistica("T", 900, 1000, 0.5)])
    boa = segundo_nivel.decidir("T", [segundo_nivel.Estatistica("T", 990, 1000, 0.5)])
    assert not ruim.aprovado and boa.aprovado
    assert segundo_nivel.reprovacao_sistematica(ruim, ruim)
    assert not segundo_nivel.reprovacao_sistematica(ruim, boa)


# ------------------------------------------------------------------- cenários
@pytest.mark.parametrize("cen,mec,esperado", [
    ("C0", SORTEIO, False), ("C1", CAIXA, True), ("C2", SORTEIO, True), ("C2", CAIXA, True)])
def test_cenarios_posteriores_e_controle(cen, mec, esperado):
    assert all(cenarios.executar(cen, mec).detectada is esperado for _ in range(20))


def test_cenario_c5_nao_detectado_e_semente_recuperada():
    tabela = cenarios.tabela_atacante_c5()
    e = cenarios.executar("C5", CAIXA, tabela)
    assert not e.detectada and e.medidas["semente_recuperada"] and e.medidas["resultados_previstos"]


# ------------------------------------------------------------- integração STS
def test_leitura_do_relatorio_do_sts(tmp_path):
    from avaliacao import nist_sts
    # linhas no formato impresso por assess.c (STS 2.1.2): "%3d " x10, P-VALUE, PROPORTION
    linhas = [
        " C1  C2  C3  C4  C5  C6  C7  C8  C9 C10  P-VALUE  PROPORTION  STATISTICAL TEST",
        " 98 102  95 101 104  99 100  97 103 101  0.996335    990/1000     Frequency",
        "120  80 100 100 100 100 100 100 100 100  0.000000 *  950/1000 *  Runs",
        " 61  60  62  59  61  62  60  61  60  61  0.999999    607/613      RandomExcursions",
        " 61  60  62  59  61  62  60  61  60  61  0.999999    608/613      RandomExcursions",
        # nenhuma sequência elegível (m' = 0): assess.c imprime "----" e "------"
        "  0   0   0   0   0   0   0   0   0   0     ----     ------     RandomExcursionsVariant",
    ]
    arq = tmp_path / "finalAnalysisReport.txt"
    arq.write_text("\n".join(linhas))
    r = nist_sts.ler_relatorio(arq)
    assert set(r) == {"Frequency", "Runs", "RandomExcursions", "RandomExcursionsVariant"}
    assert r["Frequency"][0].aprovada and not r["Runs"][0].aprovada
    assert [e.total for e in r["RandomExcursions"]] == [613, 613]
    vazia = r["RandomExcursionsVariant"][0]
    assert vazia.total == 0 and not vazia.aprovada
    assert not segundo_nivel.decidir("RandomExcursionsVariant", [vazia]).aprovado


def test_combinacao_de_partes_e_exata():
    a = segundo_nivel.Estatistica("T", 495, 500, 0.0, (50,) * 10)
    b = segundo_nivel.Estatistica("T", 492, 500, 0.0, (45, 55) * 5)
    c = segundo_nivel.combinar([a, b])
    assert (c.aprovadas, c.total, c.contagens) == (987, 1000, (95, 105) * 5)
    assert abs(c.p_t - segundo_nivel.uniformidade_de_contagens((95, 105) * 5)) < 1e-12
