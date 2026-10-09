import unittest
from decimal import Decimal

from loja.servicos.frete import calcular


class TestFrete(unittest.TestCase):
    def test_por_regiao(self):
        self.assertEqual(calcular("PE", Decimal("100")), Decimal("34.90"))
        self.assertEqual(calcular("sp", Decimal("100")), Decimal("19.90"))

    def test_gratis_acima_de_300(self):
        self.assertEqual(calcular("AM", Decimal("300.00")), Decimal("0.00"))
