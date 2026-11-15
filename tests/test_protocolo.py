import hashlib
import hmac
from collections import Counter

import pytest

from premiacao import CAIXA, SORTEIO, Mecanismo, Operador, registro_publico
from premiacao.protocolo import amostra, compromisso, converter, mensagem, reduzir


def test_vetores_conhecidos_sha256_e_hmac():
    # FIPS 180-4 (exemplo "abc") e RFC 4231, caso de teste 2
    assert hashlib.sha256(b"abc").hexdigest() == \
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert hmac.digest(b"Jefe", b"what do ya want for nothing?", "sha256").hex() == \
        "5bdcc146bf60754e6a042426089575c75a003f089d2739839dec58b964ec3843"


def test_compromisso_e_mensagem():
    s = bytes(range(32))
    assert compromisso(s) == hashlib.sha256(s).hexdigest()
    assert mensagem("abc", 7, 0) == b"abc:7:0"
    # injetividade: s_C com ":" não colide com outro (s_C, n, j)
    assert mensagem("a:1", 2, 0) != mensagem("a", 1, 20)


def test_amostra_corresponde_a_equacao():
    s = bytes(32)
    assert amostra(s, "x", 3, 1) == hmac.new(s, b"x:3:1", hashlib.sha256).digest()


def test_descarte_e_exatamente_uniforme():
    # Com b = 8 e N = 100: 200 valores aceitos, exatamente 2 por resultado
    aceitos = Counter(r for v in range(256) if (r := reduzir(v, 100, 8)) is not None)
    assert len(aceitos) == 100 and set(aceitos.values()) == {2}
    assert sum(reduzir(v, 100, 8) is None for v in range(256)) == 56


def test_conversao_deterministica_e_no_intervalo():
    s = bytes(32)
    valores = [converter(s, "cliente", n, 100) for n in range(2000)]
    assert valores == [converter(s, "cliente", n, 100) for n in range(2000)]
    assert min(valores) >= 0 and max(valores) <= 99


@pytest.mark.parametrize("bits", [7, 0, 264])
def test_conversao_rejeita_bits_invalidos(bits):
    with pytest.raises(ValueError):
        converter(bytes(32), "c", 0, 100, bits)


def test_inversao_da_caixa():
    assert [CAIXA.resultado(u) for u in (0, 49, 50, 79, 80, 94, 95, 98, 99)] == \
        [0, 0, 1, 1, 2, 2, 3, 3, 4]
    assert SORTEIO.resultado(42) == 42
    with pytest.raises(ValueError):
        Mecanismo("errado", 100, (50, 30))


def test_ciclo_do_operador_gera_registro_publico():
    op = Operador(CAIXA)
    eventos = op.executar_ciclo("participante", 5)
    reg = registro_publico(op.compromisso, op.revelar(), "participante", CAIXA, eventos)
    assert reg["compromisso"] == compromisso(op.revelar())
    assert [n for n, _ in reg["eventos"]] == [0, 1, 2, 3, 4]
