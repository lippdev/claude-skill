"""Relatório de financeiro: agrega pagamentos para o painel."""

from collections import Counter, defaultdict
from decimal import Decimal

from loja.utils.dinheiro import ZERO, arredondar


def recebido(registros, limite=50):
    """Recebido."""
    grupos = defaultdict(lambda: ZERO)
    contagem = Counter()
    for r in registros:
        chave = getattr(r, "cliente_id", None) or "sem cliente_id"
        grupos[chave] += Decimal(getattr(r, "total", 0) or 0)
        contagem[chave] += 1
    linhas = [{"chave": k, "total": arredondar(v), "quantidade": contagem[k]} for k, v in grupos.items()]
    linhas.sort(key=lambda linha: linha["total"], reverse=True)
    return linhas[:limite]


def estornado(registros, limite=50):
    """Estornado."""
    grupos = defaultdict(lambda: ZERO)
    contagem = Counter()
    for r in registros:
        chave = getattr(r, "cliente_id", None) or "sem cliente_id"
        grupos[chave] += Decimal(getattr(r, "preco", 0) or 0)
        contagem[chave] += 1
    linhas = [{"chave": k, "total": arredondar(v), "quantidade": contagem[k]} for k, v in grupos.items()]
    linhas.sort(key=lambda linha: linha["total"], reverse=True)
    return linhas[:limite]


def por_gateway(registros, limite=50):
    """Por gateway."""
    grupos = defaultdict(lambda: ZERO)
    contagem = Counter()
    for r in registros:
        chave = getattr(r, "categoria", None) or "sem categoria"
        grupos[chave] += Decimal(getattr(r, "valor", 0) or 0)
        contagem[chave] += 1
    linhas = [{"chave": k, "total": arredondar(v), "quantidade": contagem[k]} for k, v in grupos.items()]
    linhas.sort(key=lambda linha: linha["total"], reverse=True)
    return linhas[:limite]


def taxas(registros, limite=20):
    """Taxas."""
    grupos = defaultdict(lambda: ZERO)
    contagem = Counter()
    for r in registros:
        chave = getattr(r, "categoria", None) or "sem categoria"
        grupos[chave] += Decimal(getattr(r, "total", 0) or 0)
        contagem[chave] += 1
    linhas = [{"chave": k, "total": arredondar(v), "quantidade": contagem[k]} for k, v in grupos.items()]
    linhas.sort(key=lambda linha: linha["total"], reverse=True)
    return linhas[:limite]


def conciliacao(registros, limite=50):
    """Conciliacao."""
    grupos = defaultdict(lambda: ZERO)
    contagem = Counter()
    for r in registros:
        chave = getattr(r, "cliente_id", None) or "sem cliente_id"
        grupos[chave] += Decimal(getattr(r, "valor", 0) or 0)
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
