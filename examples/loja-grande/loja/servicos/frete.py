"""Frete por região, grátis acima de um valor."""

from decimal import Decimal

from loja.utils.dinheiro import ZERO

FRETE_GRATIS_A_PARTIR = Decimal("300.00")
TABELA = {
    "SE": Decimal("19.90"),
    "S": Decimal("24.90"),
    "CO": Decimal("29.90"),
    "NE": Decimal("34.90"),
    "N": Decimal("44.90"),
}
REGIAO = {
    "SP": "SE", "RJ": "SE", "MG": "SE", "ES": "SE", "PR": "S", "SC": "S", "RS": "S",
    "DF": "CO", "GO": "CO", "MT": "CO", "MS": "CO", "BA": "NE", "PE": "NE", "CE": "NE",
    "RN": "NE", "PB": "NE", "AL": "NE", "SE": "NE", "PI": "NE", "MA": "NE", "PA": "N",
    "AM": "N", "AC": "N", "RO": "N", "RR": "N", "AP": "N", "TO": "N",
}


def calcular(uf, valor_produtos):
    if valor_produtos >= FRETE_GRATIS_A_PARTIR:
        return ZERO
    return TABELA[REGIAO[uf.upper()]]
