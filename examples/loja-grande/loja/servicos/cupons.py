"""Cupons de desconto percentual."""

from loja.utils.dinheiro import ZERO, arredondar


class CupomInvalido(Exception):
    pass


def validar(cupom, base, hoje):
    if cupom.validade and hoje.isoformat() > cupom.validade:
        raise CupomInvalido(f"cupom {cupom.codigo} vencido")
    if base < cupom.minimo:
        raise CupomInvalido(f"cupom {cupom.codigo} exige mínimo de {cupom.minimo}")


def calcular(cupom, base):
    """Desconto do cupom sobre `base` (o valor dos produtos já com as promoções aplicadas)."""
    if cupom is None or base <= 0:
        return ZERO
    return arredondar(base * cupom.percentual / 100)
