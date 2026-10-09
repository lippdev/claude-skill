#!/usr/bin/env python3
"""Sincroniza o catálogo com o export do ERP (data/erp_export.csv) e registra cada passo no log."""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loja.modelos import Produto  # noqa: E402
from loja.repositorios import Produtos  # noqa: E402
from loja.utils.dinheiro import parse_valor  # noqa: E402
from loja.utils.logs import log  # noqa: E402

EXPORT = Path(__file__).resolve().parent.parent / "data" / "erp_export.csv"


def sincronizar(caminho=EXPORT):
    catalogo = Produtos()
    with open(caminho, encoding="utf-8") as f:
        linhas = list(csv.DictReader(f, delimiter=";"))
    log("INFO", "início da sincronização", arquivo=caminho.name, linhas=len(linhas))
    for n, linha in enumerate(linhas, 1):
        sku = linha["sku"].strip()
        log("INFO", "lendo linha", n=n, sku=sku)
        log("DEBUG", "campos brutos", nome=linha["nome"], preco=linha["preco"], estoque=linha["estoque"])
        log("DEBUG", "consultando cache local", sku=sku, encontrado=catalogo.existe(sku))
        log("DEBUG", "normalizando categoria", sku=sku, categoria=linha["categoria"].strip().lower())
        preco = parse_valor(linha["preco"])
        log("DEBUG", "preço convertido", sku=sku, preco=preco)
        estoque = int(linha["estoque"])
        log("DEBUG", "estoque convertido", sku=sku, estoque=estoque)
        produto = Produto(sku, linha["nome"].strip(), preco, estoque, linha["categoria"].strip().lower())
        catalogo.salvar(produto)
        log("INFO", "produto gravado", sku=sku)
        log("DEBUG", "fila de eventos", evento="produto.atualizado", sku=sku)
        log("DEBUG", "fim da linha", n=n)
    total = len(catalogo.todos())
    log("INFO", "fim da sincronização", gravados=total)
    print(f"Sincronizados: {total} de {len(linhas)}")
    return total


if __name__ == "__main__":
    sincronizar()
