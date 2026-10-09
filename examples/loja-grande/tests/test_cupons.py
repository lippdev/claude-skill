import unittest
from datetime import date
from decimal import Decimal

from loja.modelos import Cupom
from loja.servicos import cupons


class TestCupons(unittest.TestCase):
    def test_calcula_percentual(self):
        self.assertEqual(cupons.calcular(Cupom("X", Decimal("10")), Decimal("80.00")), Decimal("8.00"))

    def test_minimo(self):
        with self.assertRaises(cupons.CupomInvalido):
            cupons.validar(Cupom("X", Decimal("10"), minimo=Decimal("50")), Decimal("49.99"), date(2026, 3, 1))

    def test_vencido(self):
        with self.assertRaises(cupons.CupomInvalido):
            cupons.validar(Cupom("X", Decimal("10"), validade="2025-12-31"), Decimal("100"), date(2026, 3, 1))
