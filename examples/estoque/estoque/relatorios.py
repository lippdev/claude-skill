"""Relatórios do estoque."""

from estoque.movimentos import saldo


def estoque_baixo(produtos, movimentos):
    """Produtos que precisam de reposição (saldo menor ou igual ao mínimo)."""
    return sorted(sku for sku, p in produtos.items() if saldo(movimentos, sku) < p.minimo)


def resumo(produtos, movimentos):
    linhas = []
    for sku, p in sorted(produtos.items()):
        linhas.append(f"{sku:<8} {p.nome:<24} saldo {saldo(movimentos, sku):>4}  mínimo {p.minimo:>3}")
    return "\n".join(linhas)
