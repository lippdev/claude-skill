"""Valores do estoque."""

from estoque.movimentos import saldo


def valor_total(produtos, movimentos):
    return round(sum(p.preco * saldo(movimentos, sku) for sku, p in produtos.items()), 2)
