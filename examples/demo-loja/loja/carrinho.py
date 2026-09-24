"""Carrinho de compras."""

from loja.catalogo import preco
from loja.frete import calcular_frete


class Carrinho:
    def __init__(self):
        self.itens = {}

    def adicionar(self, codigo, quantidade=1):
        if quantidade <= 0:
            raise ValueError("quantidade deve ser positiva")
        self.itens[codigo] = self.itens.get(codigo, 0) + quantidade

    def remover(self, codigo):
        self.itens.pop(codigo, None)

    def subtotal(self):
        # BUG proposital: ignora a quantidade de cada item.
        return round(sum(preco(c) for c in self.itens), 2)

    def total(self, cep):
        sub = self.subtotal()
        return round(sub + calcular_frete(sub, cep), 2)
