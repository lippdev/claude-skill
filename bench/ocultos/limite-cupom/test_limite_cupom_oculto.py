"""Testes ocultos da tarefa "limite de uso de cupom": copiados para o projeto só na verificação."""

import unittest
from decimal import Decimal

from loja.app import App
from loja.modelos import Cliente, Cupom, Produto
from loja.servicos.cupons import CupomInvalido


class TestLimiteCupom(unittest.TestCase):
    def setUp(self):
        self.app = App.para_testes()
        self.app.produtos.salvar(Produto("A", "Caneca", Decimal("100.00"), 50, "casa"))
        self.app.clientes.salvar(Cliente("c1", "Ana", "ana@x.com", "Recife", "PE"))
        self.app.clientes.salvar(Cliente("c2", "Bia", "bia@x.com", "Curitiba", "PR"))
        self.app.cupons.salvar(Cupom("LIVRE", Decimal("10")))
        self.app.cupons.salvar(Cupom("DOIS", Decimal("10"), limite_total=2))
        self.app.cupons.salvar(Cupom("UM", Decimal("10"), limite_por_cliente=1))

    def comprar(self, cliente, cupom):
        pedido = self.app.pedidos.criar(cliente, {"A": 1}, cupom=cupom)
        return self.app.pedidos.fechar(pedido.id)

    def test_sem_limite_continua_ilimitado(self):
        for _ in range(5):
            self.assertEqual(self.comprar("c1", "LIVRE").status, "pago")

    def test_limite_total_bloqueia_sem_cobrar_nem_reservar(self):
        self.comprar("c1", "DOIS")
        self.comprar("c2", "DOIS")
        cobrancas = len(self.app.gateway.cobrancas)
        estoque = self.app.produtos.obter("A").estoque
        pedido = self.app.pedidos.criar("c1", {"A": 1}, cupom="DOIS")
        with self.assertRaises(CupomInvalido):
            self.app.pedidos.fechar(pedido.id)
        self.assertEqual(len(self.app.gateway.cobrancas), cobrancas)
        self.assertEqual(self.app.produtos.obter("A").estoque, estoque)
        self.assertEqual(self.app.pedidos.obter(pedido.id).status, "aberto")

    def test_limite_por_cliente(self):
        self.comprar("c1", "UM")
        with self.assertRaises(CupomInvalido):
            self.comprar("c1", "UM")
        self.assertEqual(self.comprar("c2", "UM").status, "pago")

    def test_pedido_aberto_nao_conta_uso(self):
        self.app.pedidos.criar("c1", {"A": 1}, cupom="UM")
        self.assertEqual(self.comprar("c1", "UM").status, "pago")

    def test_cancelamento_devolve_uso(self):
        self.comprar("c1", "DOIS")
        segundo = self.comprar("c2", "DOIS")
        self.app.pedidos.cancelar(segundo.id)
        self.assertEqual(self.comprar("c2", "DOIS").status, "pago")


if __name__ == "__main__":
    unittest.main()
