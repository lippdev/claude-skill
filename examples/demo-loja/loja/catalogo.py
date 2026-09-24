"""Catálogo de produtos da loja de demonstração."""

PRODUTOS = {
    "cafe": {"nome": "Café 500g", "preco": 24.90},
    "caneca": {"nome": "Caneca", "preco": 39.00},
    "filtro": {"nome": "Filtro de papel", "preco": 7.50},
}


def preco(codigo):
    if codigo not in PRODUTOS:
        raise KeyError(f"produto desconhecido: {codigo}")
    return PRODUTOS[codigo]["preco"]
