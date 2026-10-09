"""Promoções automáticas por categoria."""

from decimal import Decimal

from loja.utils.dinheiro import ZERO, arredondar

# Categorias com "leve 3, pague 2": a cada 3 unidades do mesmo item, uma sai de graça.
LEVE3_PAGUE2 = {"promo3"}
# Desconto percentual fixo por categoria.
PERCENTUAL = {"outlet": Decimal("20")}


def desconto_item(item, categoria):
    """Desconto de promoção de um item do pedido, já arredondado."""
    if categoria in LEVE3_PAGUE2:
        return arredondar(item.preco_unitario * (item.quantidade // 3))
    if categoria in PERCENTUAL:
        return arredondar(item.preco_unitario * item.quantidade * PERCENTUAL[categoria] / 100)
    return ZERO


def aplicar(pedido, produtos):
    """Preenche o desconto de promoção de cada item e devolve o total de desconto."""
    total = ZERO
    for item in pedido.itens:
        item.desconto_promocao = desconto_item(item, produtos.obter(item.sku).categoria)
        total += item.desconto_promocao
    return total
