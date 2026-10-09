"""Entidades da loja."""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional


@dataclass
class Produto:
    sku: str
    nome: str
    preco: Decimal
    estoque: int
    categoria: str


@dataclass
class Cliente:
    id: str
    nome: str
    email: str
    cidade: str
    uf: str


@dataclass
class Cupom:
    codigo: str
    percentual: Decimal
    minimo: Decimal = Decimal("0")
    validade: Optional[str] = None  # "AAAA-MM-DD" ou None para sem validade


@dataclass
class ItemPedido:
    sku: str
    quantidade: int
    preco_unitario: Decimal
    desconto_promocao: Decimal = Decimal("0.00")


@dataclass
class Pedido:
    id: str
    cliente_id: str
    itens: list = field(default_factory=list)
    status: str = "aberto"  # aberto, pago, cancelado
    cupom: Optional[str] = None
    subtotal: Decimal = Decimal("0.00")
    desconto_promocao: Decimal = Decimal("0.00")
    desconto_cupom: Decimal = Decimal("0.00")
    frete: Decimal = Decimal("0.00")
    total: Decimal = Decimal("0.00")
    pagamento_id: Optional[str] = None


@dataclass
class Pagamento:
    id: str
    pedido_id: str
    valor: Decimal
    gateway: str
    status: str = "aprovado"
    estornado: Decimal = Decimal("0.00")
