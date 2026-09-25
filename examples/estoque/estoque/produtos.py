"""Cadastro de produtos."""

from dataclasses import dataclass


@dataclass
class Produto:
    sku: str
    nome: str
    preco: float
    minimo: int  # abaixo ou igual a isso, o produto precisa de reposição
