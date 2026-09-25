"""Simula um mês de operação do estoque e imprime o log de cada movimento."""

import random

from estoque import movimentos as mov, repositorio

random.seed(7)
produtos = repositorio.carregar_produtos()
movimentos = repositorio.carregar_movimentos()
skus = sorted(produtos)

for dia in range(1, 31):
    if dia == 24:
        skus.append("FIL-009")  # pedido antigo de um filtro que saiu do cadastro
    for _ in range(12):
        sku = random.choice(skus)
        tipo = random.choice(["entrada", "saida", "saida"])
        qtd = random.randint(1, 8)
        data = f"{dia:02d}/03/2026"
        mov.registrar(movimentos, sku, tipo, qtd, data)
        produto = produtos[sku]
        print(f"[{data}] INFO {tipo:<7} {qtd:>2} x {produto.nome:<22} saldo agora {mov.saldo(movimentos, sku):>4}")
print("Simulação concluída.")
