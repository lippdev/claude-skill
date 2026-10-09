"""Ciclo de vida do pedido: criar, fechar (cobrar) e cancelar."""

from loja.modelos import ItemPedido, Pedido
from loja.servicos import cupons, frete, promocoes
from loja.utils.dinheiro import ZERO, arredondar
from loja.utils.validacao import quantidade_valida


class ServicoPedidos:
    def __init__(self, pedidos, produtos, clientes, cupons_repo, estoque, pagamentos, notificacoes, hoje):
        self.pedidos = pedidos
        self.produtos = produtos
        self.clientes = clientes
        self.cupons = cupons_repo
        self.estoque = estoque
        self.pagamentos = pagamentos
        self.notificacoes = notificacoes
        self.hoje = hoje

    def obter(self, pedido_id):
        return self.pedidos.obter(pedido_id)

    def criar(self, cliente_id, itens, cupom=None):
        """`itens` é um dict {sku: quantidade}."""
        self.clientes.obter(cliente_id)
        pedido = Pedido(self.pedidos.proximo_id(), cliente_id, cupom=cupom)
        for sku, qtd in itens.items():
            if not quantidade_valida(qtd):
                raise ValueError(f"quantidade inválida para {sku}: {qtd}")
            pedido.itens.append(ItemPedido(sku, qtd, self.produtos.obter(sku).preco))
        return self.pedidos.salvar(pedido)

    def calcular_totais(self, pedido):
        pedido.subtotal = arredondar(sum((i.preco_unitario * i.quantidade for i in pedido.itens), ZERO))
        pedido.desconto_promocao = promocoes.aplicar(pedido, self.produtos)
        cupom = self.cupons.obter(pedido.cupom) if pedido.cupom else None
        base = pedido.subtotal
        if cupom:
            cupons.validar(cupom, base, self.hoje())
        pedido.desconto_cupom = cupons.calcular(cupom, base)
        produtos_liquido = pedido.subtotal - pedido.desconto_promocao - pedido.desconto_cupom
        uf = self.clientes.obter(pedido.cliente_id).uf
        pedido.frete = frete.calcular(uf, produtos_liquido)
        pedido.total = arredondar(produtos_liquido + pedido.frete)
        return pedido

    def fechar(self, pedido_id):
        pedido = self.pedidos.obter(pedido_id)
        if pedido.status != "aberto":
            raise ValueError(f"pedido {pedido_id} já está {pedido.status}")
        self.calcular_totais(pedido)
        self.estoque.reservar(pedido.itens)
        pagamento = self.pagamentos.cobrar(pedido)
        pedido.pagamento_id = pagamento.id
        pedido.status = "pago"
        self.notificacoes.pedido_pago(pedido)
        return pedido

    def cancelar(self, pedido_id):
        """Cancela um pedido pago: devolve todo o estoque e estorna o valor inteiro."""
        pedido = self.pedidos.obter(pedido_id)
        if pedido.status != "pago":
            raise ValueError(f"só dá para cancelar pedido pago; {pedido_id} está {pedido.status}")
        for item in pedido.itens:
            self.estoque.devolver(item.sku, item.quantidade)
        valor = self.pagamentos.estornar(pedido.pagamento_id, pedido.total)
        pedido.status = "cancelado"
        self.notificacoes.pedido_cancelado(pedido, valor)
        return valor
