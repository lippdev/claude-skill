import unittest
from decimal import Decimal

from loja.modelos import ItemPedido
from loja.servicos.promocoes import desconto_item


class TestPromocoes(unittest.TestCase):
    def test_leve3_pague2(self):
        self.assertEqual(desconto_item(ItemPedido("M", 7, Decimal("30.00")), "promo3"), Decimal("60.00"))

    def test_outlet_20_por_cento(self):
        self.assertEqual(desconto_item(ItemPedido("J", 1, Decimal("250.00")), "outlet"), Decimal("50.00"))

    def test_sem_promocao(self):
        self.assertEqual(desconto_item(ItemPedido("C", 3, Decimal("39.90")), "casa"), Decimal("0.00"))
