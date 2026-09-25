import unittest

from estoque import movimentos as mov, precos, relatorios, repositorio


class TestMovimentos(unittest.TestCase):
    def test_saldo_simples(self):
        m = []
        mov.registrar(m, "X", "entrada", 10, "01/02/2026")
        mov.registrar(m, "X", "saida", 3, "02/02/2026")
        self.assertEqual(mov.saldo(m, "X"), 7)

    def test_saida_sem_saldo_e_recusada(self):
        m = []
        mov.registrar(m, "X", "saida", 3, "01/02/2026")
        mov.registrar(m, "X", "entrada", 2, "02/02/2026")
        self.assertEqual(mov.saldo(m, "X"), 2)

    def test_saldo_respeita_ordem_cronologica_entre_meses(self):
        m = []
        mov.registrar(m, "X", "entrada", 10, "28/01/2026")
        mov.registrar(m, "X", "saida", 4, "03/02/2026")
        self.assertEqual(mov.saldo(m, "X"), 6)

    def test_quantidade_invalida(self):
        with self.assertRaises(ValueError):
            mov.registrar([], "X", "entrada", 0, "01/02/2026")


class TestRelatorios(unittest.TestCase):
    def setUp(self):
        self.produtos = repositorio.carregar_produtos()
        self.movimentos = repositorio.carregar_movimentos()

    def test_estoque_baixo_inclui_quem_esta_no_minimo(self):
        # CAF-001 tem saldo 5 e mínimo 5: precisa de reposição.
        self.assertIn("CAF-001", relatorios.estoque_baixo(self.produtos, self.movimentos))

    def test_valor_total(self):
        self.assertEqual(precos.valor_total(self.produtos, self.movimentos), 1119.2)


if __name__ == "__main__":
    unittest.main()
