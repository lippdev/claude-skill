"""Gateway de pagamento em memória, usado em testes e desenvolvimento."""


class GatewayFake:
    nome = "fake"

    def __init__(self, recusar=False):
        self.recusar = recusar
        self.cobrancas = []
        self.estornos = []

    def cobrar(self, referencia, valor):
        if self.recusar:
            return False
        self.cobrancas.append((referencia, valor))
        return True

    def estornar(self, pagamento_id, valor):
        self.estornos.append((pagamento_id, valor))
