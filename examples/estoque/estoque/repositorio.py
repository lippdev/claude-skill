"""Leitura e gravação dos dados em JSON."""

import json
from pathlib import Path

from estoque.produtos import Produto

DADOS = Path(__file__).resolve().parent.parent / "dados"


def carregar_produtos(pasta=DADOS):
    with open(Path(pasta) / "produtos.json", encoding="utf-8") as f:
        return {p["sku"]: Produto(**p) for p in json.load(f)}


def carregar_movimentos(pasta=DADOS):
    with open(Path(pasta) / "movimentos.json", encoding="utf-8") as f:
        return json.load(f)


def salvar_movimentos(movimentos, pasta=DADOS):
    with open(Path(pasta) / "movimentos.json", "w", encoding="utf-8") as f:
        json.dump(movimentos, f, ensure_ascii=False, indent=2)
