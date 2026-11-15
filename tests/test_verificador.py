import ast
import json
import pathlib
import subprocess
import sys

import pytest

from premiacao import CAIXA, SORTEIO, Operador, registro_publico
from verificador import RegistroInvalido, verificar

RAIZ = pathlib.Path(__file__).resolve().parents[1]


def _registro(mecanismo=CAIXA, eventos=50):
    op = Operador(mecanismo)
    ev = op.executar_ciclo("semente-do-participante", eventos)
    return registro_publico(op.compromisso, op.revelar(), "semente-do-participante", mecanismo, ev)


@pytest.mark.parametrize("mecanismo", [SORTEIO, CAIXA])
def test_ciclo_honesto_e_valido(mecanismo):
    assert verificar(_registro(mecanismo)).valido


def test_detecta_semente_substituida():
    reg = _registro()
    reg["semente_servidor"] = "00" * 32
    r = verificar(reg)
    assert not r.valido and "compromisso" in r.motivo


def test_detecta_resultado_alterado():
    reg = _registro(SORTEIO)
    n, y = reg["eventos"][7]
    reg["eventos"][7] = [n, (y + 1) % 100]
    r = verificar(reg)
    assert not r.valido and r.evento == 7


def test_detecta_tabela_divergente_quando_se_manifesta():
    from premiacao import Mecanismo
    from premiacao.protocolo import converter
    s_s = bytes(range(32))
    # procura uma semente do participante em que o evento 0 tenha u = 99
    s_c = next(f"p{i}" for i in range(100_000) if converter(s_s, f"p{i}", 0, 100) == 99)
    divergente = Mecanismo("caixa", 100, (50, 30, 15, 5, 0))
    op = Operador(divergente, s_s)
    reg = registro_publico(op.compromisso, s_s, s_c, CAIXA, op.executar_ciclo(s_c, 1))
    r = verificar(reg)  # o registro declara a tabela correta
    assert not r.valido and r.evento == 0


def test_rejeita_registro_malformado():
    reg = _registro()
    reg["mecanismo"]["pesos"] = [1, 2]
    with pytest.raises(RegistroInvalido):
        verificar(reg)


def test_evento_repetido_e_invalido():
    reg = _registro(eventos=3)
    reg["eventos"].append(reg["eventos"][0])
    assert not verificar(reg).valido


def test_verificador_nao_importa_o_prototipo():
    for arq in (RAIZ / "verificador").glob("*.py"):
        arvore = ast.parse(arq.read_text(encoding="utf-8"))
        modulos = {a.name for n in ast.walk(arvore) if isinstance(n, ast.Import) for a in n.names}
        modulos |= {n.module for n in ast.walk(arvore) if isinstance(n, ast.ImportFrom) and n.module}
        assert not any(m and m.startswith("premiacao") for m in modulos), arq


def test_interface_de_linha_de_comando(tmp_path):
    arq = tmp_path / "registro.json"
    reg = _registro()
    arq.write_text(json.dumps(reg))
    ok = subprocess.run([sys.executable, "-m", "verificador", str(arq)], cwd=RAIZ,
                        capture_output=True, text=True)
    assert ok.returncode == 0 and ok.stdout.startswith("VÁLIDO")
    reg["eventos"][0][1] = (reg["eventos"][0][1] + 1) % 5
    arq.write_text(json.dumps(reg))
    falha = subprocess.run([sys.executable, "-m", "verificador", str(arq)], cwd=RAIZ,
                           capture_output=True, text=True)
    assert falha.returncode == 1 and falha.stdout.startswith("INVÁLIDO")
