import unittest
from decimal import Decimal

from loja.utils.dinheiro import arredondar, formatar, parse_valor, proporcional


class TestDinheiro(unittest.TestCase):
    def test_arredonda_meio_para_cima(self):
        self.assertEqual(arredondar(Decimal("2.345")), Decimal("2.35"))

    def test_parse(self):
        self.assertEqual(parse_valor(" 12.5 "), Decimal("12.50"))

    def test_formatar(self):
        self.assertEqual(formatar(Decimal("1234.5")), "R$ 1234,50")

    def test_proporcional(self):
        self.assertEqual(proporcional(Decimal("90"), 1, 3), Decimal("30.00"))
        self.assertEqual(proporcional(Decimal("90"), 1, 0), Decimal("0.00"))
