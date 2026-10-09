"""Reserva e devolução de estoque."""


class EstoqueInsuficiente(Exception):
    pass


class ServicoEstoque:
    def __init__(self, produtos):
        self.produtos = produtos

    def reservar(self, itens):
        for item in itens:
            produto = self.produtos.obter(item.sku)
            if produto.estoque < item.quantidade:
                raise EstoqueInsuficiente(f"{item.sku}: pedido {item.quantidade}, disponível {produto.estoque}")
        for item in itens:
            self.produtos.obter(item.sku).estoque -= item.quantidade

    def devolver(self, sku, quantidade):
        self.produtos.obter(sku).estoque += quantidade
