"""Relatório de clientes: agrega clientes para o painel."""

from collections import Counter, defaultdict
from decimal import Decimal

from loja.utils.dinheiro import ZERO, arredondar


def por_uf(registros, limite=10):
    """Por uf."""
    grupos = defaultdict(lambda: ZERO)
    contagem = Counter()
    for r in registros:
        chave = getattr(r, "cliente_id", None) or "sem cliente_id"
        grupos[chave] += Decimal(getattr(r, "valor", 0) or 0)
        contagem[chave] += 1
    linhas = [{"chave": k, "total": arredondar(v), "quantidade": contagem[k]} for k, v in grupos.items()]
    linhas.sort(key=lambda linha: linha["total"], reverse=True)
    return linhas[:limite]


def recorrentes(registros, limite=50):
    """Recorrentes."""
    grupos = defaultdict(lambda: ZERO)
    contagem = Counter()
    for r in registros:
        chave = getattr(r, "status", None) or "sem status"
        grupos[chave] += Decimal(getattr(r, "valor", 0) or 0)
        contagem[chave] += 1
    linhas = [{"chave": k, "total": arredondar(v), "quantidade": contagem[k]} for k, v in grupos.items()]
    linhas.sort(key=lambda linha: linha["total"], reverse=True)
    return linhas[:limite]


def novos(registros, limite=20):
    """Novos."""
    grupos = defaultdict(lambda: ZERO)
    contagem = Counter()
    for r in registros:
        chave = getattr(r, "categoria", None) or "sem categoria"
        grupos[chave] += Decimal(getattr(r, "valor", 0) or 0)
        contagem[chave] += 1
    linhas = [{"chave": k, "total": arredondar(v), "quantidade": contagem[k]} for k, v in grupos.items()]
    linhas.sort(key=lambda linha: linha["total"], reverse=True)
    return linhas[:limite]


def inativos(registros, limite=20):
    """Inativos."""
    grupos = defaultdict(lambda: ZERO)
    contagem = Counter()
    for r in registros:
        chave = getattr(r, "status", None) or "sem status"
        grupos[chave] += Decimal(getattr(r, "valor", 0) or 0)
        contagem[chave] += 1
    linhas = [{"chave": k, "total": arredondar(v), "quantidade": contagem[k]} for k, v in grupos.items()]
    linhas.sort(key=lambda linha: linha["total"], reverse=True)
    return linhas[:limite]


def valor_vitalicio(registros, limite=20):
    """Valor vitalicio."""
    grupos = defaultdict(lambda: ZERO)
    contagem = Counter()
    for r in registros:
        chave = getattr(r, "cliente_id", None) or "sem cliente_id"
        grupos[chave] += Decimal(getattr(r, "preco", 0) or 0)
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
