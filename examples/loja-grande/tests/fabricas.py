"""Dados de teste prontos."""

from decimal import Decimal

from loja.app import App
from loja.modelos import Cliente, Cupom, Produto


def app_com_catalogo():
    app = App.para_testes()
    for p in [
        Produto("CAN-01", "Caneca", Decimal("39.90"), 50, "casa"),
        Produto("PRT-01", "Prato fundo", Decimal("24.50"), 40, "casa"),
        Produto("MEIA-3", "Meia esportiva", Decimal("30.00"), 90, "promo3"),
        Produto("JAQ-01", "Jaqueta", Decimal("250.00"), 5, "outlet"),
        Produto("LIV-01", "Livro de receitas", Decimal("89.00"), 12, "livros"),
    ]:
        app.produtos.salvar(p)
    app.clientes.salvar(Cliente("C1", "Ana", "ana@exemplo.com", "Recife", "PE"))
    app.clientes.salvar(Cliente("C2", "Bruno", "bruno@exemplo.com", "Curitiba", "PR"))
    app.cupons.salvar(Cupom("DEZ", Decimal("10")))
    app.cupons.salvar(Cupom("VIP50", Decimal("15"), minimo=Decimal("50.00")))
    app.cupons.salvar(Cupom("VELHO", Decimal("30"), validade="2025-12-31"))
    return app
