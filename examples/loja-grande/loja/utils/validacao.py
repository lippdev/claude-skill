"""Validações de entrada."""

import re

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
UFS = {"AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR",
       "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"}


def email_valido(email):
    return bool(EMAIL.match(email or ""))


def uf_valida(uf):
    return (uf or "").upper() in UFS


def quantidade_valida(qtd):
    return isinstance(qtd, int) and qtd > 0
