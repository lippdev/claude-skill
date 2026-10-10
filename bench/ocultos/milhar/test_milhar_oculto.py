"""Testes ocultos da tarefa "separador de milhar": copiados para o projeto só na verificação."""

import unittest
from decimal import Decimal

from loja.utils.dinheiro import formatar


class TestMilhar(unittest.TestCase):
    def test_valores(self):
        self.assertEqual(formatar(Decimal("1234.5")), "R$ 1.234,50")
        self.assertEqual(formatar(Decimal("1234567.891")), "R$ 1.234.567,89")
        self.assertEqual(formatar(Decimal("999.99")), "R$ 999,99")
        self.assertEqual(formatar(Decimal("0")), "R$ 0,00")


if __name__ == "__main__":
    unittest.main()
