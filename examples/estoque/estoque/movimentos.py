"""Entradas e saídas de estoque."""


def registrar(movimentos, sku, tipo, quantidade, data):
    if tipo not in ("entrada", "saida"):
        raise ValueError(f"tipo inválido: {tipo}")
    if quantidade <= 0:
        raise ValueError("quantidade deve ser positiva")
    movimentos.append({"sku": sku, "tipo": tipo, "quantidade": quantidade, "data": data})
    return movimentos


def saldo(movimentos, sku):
    """Aplica os movimentos em ordem cronológica. Saídas sem saldo suficiente são recusadas."""
    atual = 0
    doproduto = [m for m in movimentos if m["sku"] == sku]
    for m in sorted(doproduto, key=lambda m: m["data"]):  # datas no formato dd/mm/aaaa
        if m["tipo"] == "entrada":
            atual += m["quantidade"]
        elif m["quantidade"] <= atual:
            atual -= m["quantidade"]
    return atual
