import unittest
from decimal import Decimal

from loja.servicos.cupons import CupomInvalido
from tests.fabricas import app_com_catalogo


class TestPedidos(unittest.TestCase):
    def setUp(self):
        self.app = app_com_catalogo()

    def test_fechar_simples(self):
        p = self.app.pedidos.criar("C1", {"CAN-01": 2})
        self.app.pedidos.fechar(p.id)
        self.assertEqual(p.total, Decimal("114.70"))  # 79.80 + frete NE 34.90
        self.assertEqual(p.status, "pago")
        self.assertEqual(self.app.produtos.obter("CAN-01").estoque, 48)
        self.assertEqual(self.app.notificador.enviadas[-1][0], "ana@exemplo.com")

    def test_cupom_simples(self):
        p = self.app.pedidos.criar("C2", {"LIV-01": 2}, cupom="DEZ")
        self.app.pedidos.fechar(p.id)
        self.assertEqual(p.desconto_cupom, Decimal("17.80"))
        self.assertEqual(p.total, Decimal("185.10"))  # 178 - 17.80 + frete S 24.90

    def test_cupom_sobre_preco_promocional(self):
        # 3 meias em "leve 3 pague 2": 90.00 - 30.00 = 60.00; o cupom vale sobre os 60.00.
        p = self.app.pedidos.criar("C1", {"MEIA-3": 3}, cupom="DEZ")
        self.app.pedidos.fechar(p.id)
        self.assertEqual(p.desconto_promocao, Decimal("30.00"))
        self.assertEqual(p.desconto_cupom, Decimal("6.00"))
        self.assertEqual(p.total, Decimal("88.90"))  # 60 - 6 + frete NE 34.90

    def test_minimo_do_cupom_usa_valor_com_promocao(self):
        # Outlet: 250 - 20% = 200; VIP50 exige 50 e vale 15% sobre 200.
        p = self.app.pedidos.criar("C2", {"JAQ-01": 1}, cupom="VIP50")
        self.app.pedidos.fechar(p.id)
        self.assertEqual(p.desconto_cupom, Decimal("30.00"))

    def test_cupom_vencido(self):
        p = self.app.pedidos.criar("C1", {"CAN-01": 1}, cupom="VELHO")
        with self.assertRaises(CupomInvalido):
            self.app.pedidos.fechar(p.id)

    def test_frete_gratis_usa_valor_com_descontos(self):
        p = self.app.pedidos.criar("C2", {"LIV-01": 4})  # 356.00, sem desconto
        self.app.pedidos.fechar(p.id)
        self.assertEqual(p.frete, Decimal("0.00"))

    def test_cancelar_estorna_tudo(self):
        p = self.app.pedidos.criar("C1", {"CAN-01": 1})
        self.app.pedidos.fechar(p.id)
        valor = self.app.pedidos.cancelar(p.id)
        self.assertEqual(valor, p.total)
        self.assertEqual(self.app.produtos.obter("CAN-01").estoque, 50)
        self.assertEqual(p.status, "cancelado")
