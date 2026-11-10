"""Modelos de domínio (diagrama de classes, seção 5.2).

Os métodos do diagrama (cadastrar, finalizar, cancelar, abrir, fechar…) vivem
nos serviços (`mercadofacil.services`); aqui ficam os dados e as propriedades
derivadas (calcularSubtotal, verificarEstoqueMinimo, calcularDiferenca…).
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field, fields
from typing import Any, TypeVar

T = TypeVar("T")


def build(cls: type[T], row: sqlite3.Row | None) -> T | None:
    """Cria um modelo a partir de uma linha SQL (campos ausentes usam o default)."""
    if row is None:
        return None
    keys = set(row.keys())
    values: dict[str, Any] = {f.name: row[f.name] for f in fields(cls) if f.name in keys}  # type: ignore[arg-type]
    return cls(**values)


def build_all(cls: type[T], rows: list[sqlite3.Row]) -> list[T]:
    return [build(cls, row) for row in rows]  # type: ignore[misc]


# --------------------------------------------------------------------- Constantes
PAYMENT_METHODS = {
    "dinheiro": "Dinheiro",
    "pix": "Pix",
    "debito": "Débito",
    "credito": "Crédito",
}
PAYMENT_METHOD_LABELS = {**PAYMENT_METHODS, "cashback": "Cashback"}

SALE_STATUS_LABELS = {
    "concluida": "Concluída",
    "parcial": "Parcialmente alterada",
    "cancelada": "Cancelada",
    "devolvida": "Devolvida/trocada",
}
SALE_STATUS_ACTIVE = ("concluida", "parcial")

OPERATION_LABELS = {
    "cancelamento_venda": "Cancelamento de venda",
    "cancelamento_item": "Cancelamento de item",
    "devolucao": "Devolução",
    "troca": "Troca",
}

ROLE_LABELS = {"operador": "Operador de caixa", "estoquista": "Estoquista", "gestor": "Gestor"}


# --------------------------------------------------------------------- Entidades
@dataclass(frozen=True)
class User:
    id: int
    username: str
    name: str
    role: str
    active: int = 1

    @property
    def role_label(self) -> str:
        return ROLE_LABELS.get(self.role, self.role)


@dataclass(frozen=True)
class Product:
    id: int
    barcode: str
    name: str
    price_cents: int
    stock: int
    min_stock: int
    active: int
    category: str = "Geral"
    unit: str = "un"
    cost_cents: int = 0
    location: str = ""
    created_at: str = ""

    @property
    def is_active(self) -> bool:
        return bool(self.active)

    @property
    def is_below_minimum(self) -> bool:
        """verificarEstoqueMinimo(): RF10."""
        return self.stock <= self.min_stock

    @property
    def stock_status(self) -> str:
        if self.stock <= 0:
            return "sem_estoque"
        if self.stock <= self.min_stock:
            return "repor"
        return "ok"

    @property
    def margin_cents(self) -> int:
        return self.price_cents - self.cost_cents


@dataclass(frozen=True)
class Customer:
    cpf: str
    name: str
    cashback_cents: int = 0
    created_at: str = ""


@dataclass(frozen=True)
class Register:
    """Caixa (turno)."""

    id: int
    operator: str
    status: str
    opening_cents: int
    opened_at: str
    expected_cents: int | None = None
    counted_cents: int | None = None
    difference_cents: int | None = None
    closed_at: str | None = None

    @property
    def is_open(self) -> bool:
        return self.status == "aberto"


@dataclass(frozen=True)
class Sale:
    id: str
    register_id: int
    subtotal_cents: int
    cashback_used_cents: int
    total_cents: int
    payment_method: str
    change_cents: int
    cashback_earned_cents: int
    status: str
    operator: str
    created_at: str
    customer_cpf: str | None = None
    customer_name: str | None = None

    @property
    def status_label(self) -> str:
        return SALE_STATUS_LABELS.get(self.status, self.status)

    @property
    def payment_label(self) -> str:
        return PAYMENT_METHOD_LABELS.get(self.payment_method, self.payment_method)

    @property
    def accepts_post_sale(self) -> bool:
        return self.status in SALE_STATUS_ACTIVE


@dataclass(frozen=True)
class SaleItem:
    id: int
    sale_id: str
    product_id: int
    quantity: int
    unit_price_cents: int
    cancelled_qty: int = 0
    returned_qty: int = 0
    product_name: str = ""
    product_barcode: str = ""
    product_unit: str = ""

    @property
    def active_qty(self) -> int:
        """Quantidade ainda ativa (RB08/RB09)."""
        return self.quantity - self.cancelled_qty - self.returned_qty

    @property
    def subtotal_cents(self) -> int:
        """calcularSubtotal()."""
        return self.quantity * self.unit_price_cents

    @property
    def active_subtotal_cents(self) -> int:
        return self.active_qty * self.unit_price_cents


@dataclass(frozen=True)
class Payment:
    id: int
    sale_id: str
    method: str
    amount_cents: int
    received_cents: int
    change_cents: int
    status: str
    created_at: str


@dataclass(frozen=True)
class StockMovement:
    id: int
    product_id: int
    type: str
    quantity: int
    balance_after: int
    reason: str
    reference: str
    operator: str
    created_at: str
    product_name: str = ""
    product_barcode: str = ""


@dataclass(frozen=True)
class PostSaleOperation:
    id: int
    sale_id: str
    type: str
    quantity: int
    amount_cents: int
    gross_cents: int
    settlement_method: str
    cashback_restored_cents: int
    cashback_reversed_cents: int
    operator: str
    authorized_by: str
    notes: str
    created_at: str
    product_id: int | None = None
    replacement_product_id: int | None = None
    register_id: int | None = None
    product_name: str = ""
    replacement_name: str = ""

    @property
    def type_label(self) -> str:
        return OPERATION_LABELS.get(self.type, self.type)


# ---------------------------------------------------------------- Valores calculados
@dataclass(frozen=True)
class CartLine:
    product: Product
    quantity: int

    @property
    def unit_price_cents(self) -> int:
        return self.product.price_cents

    @property
    def subtotal_cents(self) -> int:
        return self.quantity * self.product.price_cents

    @property
    def has_stock_issue(self) -> bool:
        return self.quantity > self.product.stock


@dataclass(frozen=True)
class CartSummary:
    lines: list[CartLine]
    subtotal_cents: int
    cashback_used_cents: int
    total_cents: int
    cashback_earned_cents: int
    customer: Customer | None = None

    @property
    def has_stock_issue(self) -> bool:
        return any(line.has_stock_issue for line in self.lines)

    @property
    def units(self) -> int:
        return sum(line.quantity for line in self.lines)


@dataclass(frozen=True)
class SaleDetail:
    sale: Sale
    items: list[SaleItem]
    payment: Payment | None
    operations: list[PostSaleOperation] = field(default_factory=list)
    customer: Customer | None = None

    @property
    def active_units(self) -> int:
        return sum(item.active_qty for item in self.items)


@dataclass(frozen=True)
class RegisterSummary:
    """Valores do turno de caixa (RF02, RB11)."""

    register: Register
    cash_sales_cents: int
    cash_in_cents: int  # dinheiro recebido em trocas (diferença paga pelo cliente)
    cash_out_cents: int  # dinheiro devolvido em cancelamentos/devoluções/trocas
    expected_cents: int
    sales_count: int
    sales_total_cents: int
    by_method: dict[str, tuple[int, int]]  # método -> (quantidade, total)


@dataclass(frozen=True)
class OverviewKPIs:
    sales_count: int
    gross_cents: int
    refunds_cents: int
    net_cents: int
    average_ticket_cents: int
    items_sold: int
    cancelled_count: int
    low_stock_count: int
    out_of_stock_count: int
    cashback_outstanding_cents: int
