"""Linha de comando: python3 -m estoque.cli [resumo|baixo|valor]"""

import sys

from estoque import precos, relatorios, repositorio


def main(argv):
    produtos = repositorio.carregar_produtos()
    movimentos = repositorio.carregar_movimentos()
    comando = argv[0] if argv else "resumo"
    if comando == "resumo":
        print(relatorios.resumo(produtos, movimentos))
    elif comando == "baixo":
        print("\n".join(relatorios.estoque_baixo(produtos, movimentos)) or "Nenhum produto em falta.")
    elif comando == "valor":
        print(f"R$ {precos.valor_total(produtos, movimentos):.2f}")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
