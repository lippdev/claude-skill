"""Valores em reais, sempre com Decimal e duas casas."""

from decimal import ROUND_HALF_UP, Decimal

CENTAVO = Decimal("0.01")
ZERO = Decimal("0.00")


def arredondar(valor):
    return Decimal(valor).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def parse_valor(texto):
    """Converte o texto de um preço ("12.50") em Decimal com duas casas."""
    return arredondar(Decimal(texto.strip()))


def formatar(valor):
    return f"R$ {arredondar(valor):.2f}".replace(".", ",")


def proporcional(total, parte, todo):
    """Fatia de `total` correspondente a `parte` de `todo`."""
    if not todo:
        return ZERO
    return arredondar(Decimal(total) * Decimal(parte) / Decimal(todo))
