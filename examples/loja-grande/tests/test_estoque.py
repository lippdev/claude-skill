import unittest

from loja.modelos import ItemPedido
from loja.servicos.estoque import EstoqueInsuficiente
from tests.fabricas import app_com_catalogo


class TestEstoque(unittest.TestCase):
    def test_reserva_e_devolve(self):
        app = app_com_catalogo()
        app.estoque.reservar([ItemPedido("CAN-01", 3, 0)])
        self.assertEqual(app.produtos.obter("CAN-01").estoque, 47)
        app.estoque.devolver("CAN-01", 2)
        self.assertEqual(app.produtos.obter("CAN-01").estoque, 49)

    def test_nao_reserva_parcial(self):
        app = app_com_catalogo()
        with self.assertRaises(EstoqueInsuficiente):
            app.estoque.reservar([ItemPedido("CAN-01", 1, 0), ItemPedido("JAQ-01", 6, 0)])
        self.assertEqual(app.produtos.obter("CAN-01").estoque, 50)
