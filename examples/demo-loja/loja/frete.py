"""Regras de frete."""

FRETE_GRATIS_A_PARTIR = 100.00


def calcular_frete(subtotal, cep):
    if subtotal >= FRETE_GRATIS_A_PARTIR:
        return 0.0
    return 15.00 if cep.startswith("0") else 25.00
