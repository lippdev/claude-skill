"""Monta os serviços da loja com suas dependências."""

from datetime import date

from loja import repositorios
from loja.integracoes.gateway_fake import GatewayFake
from loja.integracoes.notificador_fake import NotificadorFake
from loja.servicos.estoque import ServicoEstoque
from loja.servicos.notificacoes import ServicoNotificacoes
from loja.servicos.pagamentos import ServicoPagamentos
from loja.servicos.pedidos import ServicoPedidos


class App:
    def __init__(self, gateway, notificador, hoje=date.today):
        self.produtos = repositorios.Produtos()
        self.clientes = repositorios.Clientes()
        self.cupons = repositorios.Cupons()
        self.gateway = gateway
        self.notificador = notificador
        self.estoque = ServicoEstoque(self.produtos)
        self.pagamentos = ServicoPagamentos(repositorios.Pagamentos(), gateway)
        self.notificacoes = ServicoNotificacoes(notificador, self.clientes)
        self.pedidos = ServicoPedidos(repositorios.Pedidos(), self.produtos, self.clientes, self.cupons,
                                      self.estoque, self.pagamentos, self.notificacoes, hoje)

    @classmethod
    def para_testes(cls, hoje=date(2026, 3, 1)):
        return cls(GatewayFake(), NotificadorFake(), hoje=lambda: hoje)
