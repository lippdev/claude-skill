"""Cobrança e estorno pelo gateway de pagamento."""

from loja.modelos import Pagamento
from loja.utils.dinheiro import arredondar


class PagamentoRecusado(Exception):
    pass


class ServicoPagamentos:
    def __init__(self, repositorio, gateway):
        self.repositorio = repositorio
        self.gateway = gateway

    def cobrar(self, pedido):
        if not self.gateway.cobrar(pedido.id, pedido.total):
            raise PagamentoRecusado(pedido.id)
        pagamento = Pagamento(self.repositorio.proximo_id(), pedido.id, pedido.total, self.gateway.nome)
        return self.repositorio.salvar(pagamento)

    def estornar(self, pagamento_id, valor):
        pagamento = self.repositorio.obter(pagamento_id)
        valor = arredondar(valor)
        if pagamento.estornado + valor > pagamento.valor:
            raise ValueError("estorno maior que o valor pago")
        self.gateway.estornar(pagamento_id, valor)
        pagamento.estornado += valor
        if pagamento.estornado == pagamento.valor:
            pagamento.status = "estornado"
        return valor
