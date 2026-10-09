import unittest
from decimal import Decimal

from tests.fabricas import app_com_catalogo


class TestPagamentos(unittest.TestCase):
    def test_estorno_nao_passa_do_valor_pago(self):
        app = app_com_catalogo()
        p = app.pedidos.criar("C2", {"LIV-01": 1})
        app.pedidos.fechar(p.id)
        app.pagamentos.estornar(p.pagamento_id, Decimal("50.00"))
        with self.assertRaises(ValueError):
            app.pagamentos.estornar(p.pagamento_id, Decimal("100.00"))
