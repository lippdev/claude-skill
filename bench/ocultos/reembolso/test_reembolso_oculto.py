"""Testes ocultos da tarefa "reembolso": copiados para o projeto só na verificação."""

import unittest
from decimal import Decimal

from loja.app import App
from loja.modelos import Cliente, Cupom, Produto


class TestReembolsoParcial(unittest.TestCase):
    def setUp(self):
        self.app = App.para_testes()
        self.app.produtos.salvar(Produto("A", "Caneca", Decimal("100.00"), 10, "casa"))
        self.app.produtos.salvar(Produto("B", "Prato", Decimal("50.00"), 10, "casa"))
        self.app.clientes.salvar(Cliente("c1", "Ana", "ana@x.com", "Recife", "PE"))
        self.app.cupons.salvar(Cupom("DEZ", Decimal("10")))
        self.pedido = self.app.pedidos.criar("c1", {"A": 2, "B": 1}, cupom="DEZ")
        self.app.pedidos.fechar(self.pedido.id)

    def test_estorna_valor_pago_pelos_itens(self):
        valor = self.app.pedidos.reembolsar(self.pedido.id, {"A": 1})
        self.assertEqual(valor, Decimal("90.00"))  # 100 com 10% do cupom
        self.assertEqual(self.app.gateway.estornos[-1], (self.pedido.pagamento_id, Decimal("90.00")))

    def test_devolve_estoque_e_marca_status(self):
        self.app.pedidos.reembolsar(self.pedido.id, {"A": 1})
        self.assertEqual(self.app.produtos.obter("A").estoque, 9)
        self.assertEqual(self.app.pedidos.obter(self.pedido.id).status, "reembolsado_parcial")

    def test_notifica_cliente(self):
        self.app.pedidos.reembolsar(self.pedido.id, {"B": 1})
        self.assertEqual(self.app.notificador.enviadas[-1][0], "ana@x.com")

    def test_nao_reembolsa_mais_do_que_comprou(self):
        with self.assertRaises(ValueError):
            self.app.pedidos.reembolsar(self.pedido.id, {"A": 3})
        self.app.pedidos.reembolsar(self.pedido.id, {"A": 2})
        with self.assertRaises(ValueError):
            self.app.pedidos.reembolsar(self.pedido.id, {"A": 1})

    def test_nao_reembolsa_pedido_aberto(self):
        aberto = self.app.pedidos.criar("c1", {"B": 1})
        with self.assertRaises(ValueError):
            self.app.pedidos.reembolsar(aberto.id, {"B": 1})
