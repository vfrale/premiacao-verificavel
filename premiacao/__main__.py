"""Demonstração de um ciclo do lado do operador.

Uso: python -m premiacao --mecanismo caixa --eventos 10 --saida registro.json
"""

from __future__ import annotations

import argparse
import json
import sys

from . import CAIXA, SORTEIO, Operador, gerar_semente_participante, registro_publico


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Executa um ciclo do protocolo provably fair.")
    p.add_argument("--mecanismo", choices=["sorteio", "caixa"], default="caixa")
    p.add_argument("--eventos", type=int, default=10)
    p.add_argument("--semente-participante", default=None,
                   help="semente do participante (padrão: aleatória)")
    p.add_argument("--saida", default="registro.json")
    args = p.parse_args(argv)

    mecanismo = CAIXA if args.mecanismo == "caixa" else SORTEIO
    operador = Operador(mecanismo)
    print(f"1. compromisso publicado: {operador.compromisso}")
    s_c = args.semente_participante or gerar_semente_participante()
    print(f"2. semente do participante: {s_c}")
    eventos = operador.executar_ciclo(s_c, args.eventos)
    print("3. resultados publicados:", " ".join(f"{n}:{y}" for n, y in eventos))
    semente = operador.revelar()
    print(f"4. semente revelada: {semente.hex()}")
    registro = registro_publico(operador.compromisso, semente, s_c, mecanismo, eventos)
    with open(args.saida, "w", encoding="utf-8") as f:
        json.dump(registro, f, indent=2)
    print(f"registro público gravado em {args.saida}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
