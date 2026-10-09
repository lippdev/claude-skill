"""Mensagens para o cliente."""

from loja.utils.dinheiro import formatar


class ServicoNotificacoes:
    def __init__(self, notificador, clientes):
        self.notificador = notificador
        self.clientes = clientes

    def pedido_pago(self, pedido):
        cliente = self.clientes.obter(pedido.cliente_id)
        self.notificador.enviar(cliente.email, f"Pedido {pedido.id} confirmado",
                                f"Olá, {cliente.nome}! Recebemos {formatar(pedido.total)}.")

    def pedido_cancelado(self, pedido, valor):
        cliente = self.clientes.obter(pedido.cliente_id)
        self.notificador.enviar(cliente.email, f"Pedido {pedido.id} cancelado",
                                f"Olá, {cliente.nome}! Estornamos {formatar(valor)}.")
