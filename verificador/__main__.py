"""Interface de linha de comando do verificador.

Uso: python -m verificador registro.json
Códigos de saída: 0 = válido; 1 = manipulação detectada; 2 = registro malformado.
"""

from __future__ import annotations

import argparse
import json
import sys

from .nucleo import RegistroInvalido, verificar


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Verifica um ciclo do protocolo provably fair "
                                            "a partir do registro público.")
    p.add_argument("registro", help="arquivo JSON com compromisso, sementes, mecanismo e eventos")
    args = p.parse_args(argv)
    try:
        with open(args.registro, encoding="utf-8") as f:
            resultado = verificar(json.load(f))
    except (OSError, json.JSONDecodeError, RegistroInvalido) as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 2
    if resultado.valido:
        print(f"VÁLIDO: {resultado.motivo}")
        return 0
    print(f"INVÁLIDO: {resultado.motivo}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
