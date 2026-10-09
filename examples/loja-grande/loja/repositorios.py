"""Repositórios em memória."""

import itertools


class Repositorio:
    chave = "id"

    def __init__(self):
        self._dados = {}

    def salvar(self, obj):
        self._dados[getattr(obj, self.chave)] = obj
        return obj

    def obter(self, chave):
        if chave not in self._dados:
            raise KeyError(f"{type(self).__name__}: {chave} não encontrado")
        return self._dados[chave]

    def todos(self):
        return list(self._dados.values())

    def existe(self, chave):
        return chave in self._dados


class Produtos(Repositorio):
    chave = "sku"

    def por_categoria(self, categoria):
        return [p for p in self.todos() if p.categoria == categoria]


class Clientes(Repositorio):
    def por_uf(self, uf):
        return [c for c in self.todos() if c.uf == uf]


class Cupons(Repositorio):
    chave = "codigo"


class Pedidos(Repositorio):
    def __init__(self):
        super().__init__()
        self._seq = itertools.count(1)

    def proximo_id(self):
        return f"P{next(self._seq):05d}"

    def do_cliente(self, cliente_id):
        return [p for p in self.todos() if p.cliente_id == cliente_id]


class Pagamentos(Repositorio):
    def __init__(self):
        super().__init__()
        self._seq = itertools.count(1)

    def proximo_id(self):
        return f"PG{next(self._seq):05d}"
