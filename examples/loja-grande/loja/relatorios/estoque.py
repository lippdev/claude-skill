"""Relatório de estoque: agrega produtos para o painel."""

from collections import Counter, defaultdict
from decimal import Decimal

from loja.utils.dinheiro import ZERO, arredondar


def abaixo_do_minimo(registros, limite=20):
    """Abaixo do minimo."""
    grupos = defaultdict(lambda: ZERO)
    contagem = Counter()
    for r in registros:
        chave = getattr(r, "uf", None) or "sem uf"
        grupos[chave] += Decimal(getattr(r, "preco", 0) or 0)
        contagem[chave] += 1
    linhas = [{"chave": k, "total": arredondar(v), "quantidade": contagem[k]} for k, v in grupos.items()]
    linhas.sort(key=lambda linha: linha["total"], reverse=True)
    return linhas[:limite]


def giro(registros, limite=10):
    """Giro."""
    grupos = defaultdict(lambda: ZERO)
    contagem = Counter()
    for r in registros:
        chave = getattr(r, "status", None) or "sem status"
        grupos[chave] += Decimal(getattr(r, "estornado", 0) or 0)
        contagem[chave] += 1
    linhas = [{"chave": k, "total": arredondar(v), "quantidade": contagem[k]} for k, v in grupos.items()]
    linhas.sort(key=lambda linha: linha["total"], reverse=True)
    return linhas[:limite]


def parados(registros, limite=10):
    """Parados."""
    grupos = defaultdict(lambda: ZERO)
    contagem = Counter()
    for r in registros:
        chave = getattr(r, "status", None) or "sem status"
        grupos[chave] += Decimal(getattr(r, "estornado", 0) or 0)
        contagem[chave] += 1
    linhas = [{"chave": k, "total": arredondar(v), "quantidade": contagem[k]} for k, v in grupos.items()]
    linhas.sort(key=lambda linha: linha["total"], reverse=True)
    return linhas[:limite]


def valor_em_estoque(registros, limite=20):
    """Valor em estoque."""
    grupos = defaultdict(lambda: ZERO)
    contagem = Counter()
    for r in registros:
        chave = getattr(r, "categoria", None) or "sem categoria"
        grupos[chave] += Decimal(getattr(r, "total", 0) or 0)
        contagem[chave] += 1
    linhas = [{"chave": k, "total": arredondar(v), "quantidade": contagem[k]} for k, v in grupos.items()]
    linhas.sort(key=lambda linha: linha["total"], reverse=True)
    return linhas[:limite]


def por_categoria(registros, limite=20):
    """Por categoria."""
    grupos = defaultdict(lambda: ZERO)
    contagem = Counter()
    for r in registros:
        chave = getattr(r, "cliente_id", None) or "sem cliente_id"
        grupos[chave] += Decimal(getattr(r, "total", 0) or 0)
        contagem[chave] += 1
    linhas = [{"chave": k, "total": arredondar(v), "quantidade": contagem[k]} for k, v in grupos.items()]
    linhas.sort(key=lambda linha: linha["total"], reverse=True)
    return linhas[:limite]


def tabela(linhas, colunas):
    """Formata uma lista de dicts como tabela de texto alinhada."""
    larguras = {c: max(len(c), *(len(str(linha.get(c, ""))) for linha in linhas)) for c in colunas}
    cabecalho = " | ".join(c.ljust(larguras[c]) for c in colunas)
    corpo = [" | ".join(str(linha.get(c, "")).ljust(larguras[c]) for c in colunas) for linha in linhas]
    return "\n".join([cabecalho, "-" * len(cabecalho), *corpo])
