import unittest

from loja.carrinho import Carrinho


class TestCarrinho(unittest.TestCase):
    def test_subtotal_considera_quantidade(self):
        c = Carrinho()
        c.adicionar("cafe", 2)
        c.adicionar("filtro")
        self.assertEqual(c.subtotal(), 57.30)

    def test_frete_gratis_acima_de_100(self):
        c = Carrinho()
        c.adicionar("caneca", 3)
        self.assertEqual(c.total("01000-000"), 117.00)

    def test_frete_capital(self):
        c = Carrinho()
        c.adicionar("filtro")
        self.assertEqual(c.total("01000-000"), 22.50)

    def test_quantidade_invalida(self):
        with self.assertRaises(ValueError):
            Carrinho().adicionar("cafe", 0)


if __name__ == "__main__":
    unittest.main()
