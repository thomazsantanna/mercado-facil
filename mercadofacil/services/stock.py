"""Controle de estoque e movimentações (RF09, RF10, RF16, RB03, RNF04)."""

from __future__ import annotations

import sqlite3

from .. import clock
from ..database import transaction
from ..errors import BusinessRuleError, NotFoundError, ValidationError
from ..models import Product, StockMovement, User
from ..repositories import catalog as catalog_repo
from ..validators import (
    optional_text,
    require_non_negative_int,
    require_positive_int,
    require_text,
)
from . import permissions

# Motivos pré-definidos por tipo de operação (a tela usa "Outro" + detalhe).
OTHER_REASON = "Outro"
ENTRY_REASONS = [
    "Reposição de mercadoria",
    "Compra de fornecedor",
    "Transferência recebida",
    OTHER_REASON,
]
EXIT_REASONS = ["Consumo interno", "Transferência enviada", OTHER_REASON]
LOSS_REASONS = ["Produto vencido", "Avaria", "Furto ou extravio", OTHER_REASON]
ADJUST_REASONS = ["Contagem de inventário", "Correção de lançamento", OTHER_REASON]

# Tipos de operação manual -> (tipo persistido, rótulo)
MANUAL_KINDS = {
    "entrada": ("entrada", "Entrada"),
    "saida": ("saida", "Saída"),
    "perda": ("saida", "Perda"),
}
REASONS_BY_KIND = {
    "entrada": ENTRY_REASONS,
    "saida": EXIT_REASONS,
    "perda": LOSS_REASONS,
    "ajuste": ADJUST_REASONS,
}

# Motivos gerados pelo sistema (referência = ID da venda).
REASON_SALE = "Venda"
REASON_SALE_CANCEL = "Cancelamento de venda"
REASON_ITEM_CANCEL = "Cancelamento de item"
REASON_RETURN = "Devolução de cliente"
REASON_EXCHANGE_IN = "Troca — produto devolvido"
REASON_EXCHANGE_OUT = "Troca — produto entregue"
REASON_INITIAL = "Estoque inicial"


def compose_reason(preset: str, detail: str = "") -> str:
    """Monta o motivo: 'Outro' exige detalhe; os demais aceitam detalhe opcional."""
    preset_text = optional_text(preset, "o motivo", max_length=80)
    detail_text = optional_text(detail, "o detalhe do motivo", max_length=200)
    if not preset_text or preset_text == OTHER_REASON:
        if not detail_text:
            raise ValidationError("Informe o motivo da movimentação.")
        return detail_text
    return f"{preset_text} — {detail_text}" if detail_text else preset_text


def apply_movement(
    conn: sqlite3.Connection,
    *,
    product_id: int,
    movement_type: str,
    quantity: int,
    reason: str,
    reference: str,
    operator: str,
) -> StockMovement:
    """Aplica a variação ao saldo e grava a movimentação (sem checar permissão).

    Uso interno dos serviços de venda e pós-venda; precisa rodar dentro de uma
    transação. RB03: o estoque não pode ficar negativo.
    """
    if movement_type not in ("entrada", "saida"):
        raise ValidationError("Tipo de movimentação inválido.")
    qty = require_positive_int(quantity, "A quantidade")
    motive = require_text(reason, "o motivo da movimentação", max_length=250)
    product = catalog_repo.get_product(conn, product_id)
    if product is None:
        raise NotFoundError("Produto não encontrado.")
    new_stock = product.stock + qty if movement_type == "entrada" else product.stock - qty
    if new_stock < 0:
        raise BusinessRuleError(
            f"Estoque negativo impedido: “{product.name}” tem saldo {product.stock} e a saída "
            f"solicitada é de {qty}. O estoque não pode ficar negativo.",
            rule="RB03",
        )
    catalog_repo.update_stock(conn, product_id, new_stock)
    movement_id = catalog_repo.insert_movement(
        conn,
        product_id=product_id,
        movement_type=movement_type,
        quantity=qty,
        balance_after=new_stock,
        reason=motive,
        reference=optional_text(reference, "a referência", max_length=120),
        operator=operator,
        created_at=clock.now_iso(),
    )
    movement = catalog_repo.get_movement(conn, movement_id)
    assert movement is not None
    return movement


def register_movement(
    conn: sqlite3.Connection,
    actor: User,
    *,
    product_id: int,
    kind: str,
    quantity: int,
    reason: str,
    reference: str = "",
) -> StockMovement:
    """RF09: registra entrada, saída ou perda com motivo e referência."""
    permissions.ensure_permission(actor, permissions.STOCK_MOVE)
    if kind not in MANUAL_KINDS:
        raise ValidationError("Tipo de operação inválido. Use entrada, saída ou perda.")
    movement_type, label = MANUAL_KINDS[kind]
    motive = require_text(reason, "o motivo da movimentação", max_length=200)
    if kind == "perda":
        motive = f"Perda: {motive}"
    with transaction(conn):
        return apply_movement(
            conn,
            product_id=product_id,
            movement_type=movement_type,
            quantity=require_positive_int(quantity, f"A quantidade de {label.lower()}"),
            reason=motive,
            reference=reference,
            operator=actor.username,
        )


def adjust_stock(
    conn: sqlite3.Connection,
    actor: User,
    *,
    product_id: int,
    counted_quantity: int,
    reason: str,
    reference: str = "",
) -> StockMovement:
    """ajustarEstoque(): define o saldo para a contagem física informada."""
    permissions.ensure_permission(actor, permissions.STOCK_MOVE)
    counted = require_non_negative_int(counted_quantity, "A contagem")
    motive = require_text(reason, "o motivo do ajuste", max_length=200)
    with transaction(conn):
        product = catalog_repo.get_product(conn, product_id)
        if product is None:
            raise NotFoundError("Produto não encontrado.")
        difference = counted - product.stock
        if difference == 0:
            raise BusinessRuleError(
                "A contagem informada é igual ao saldo atual; não há o que ajustar."
            )
        return apply_movement(
            conn,
            product_id=product_id,
            movement_type="entrada" if difference > 0 else "saida",
            quantity=abs(difference),
            reason=f"Ajuste de inventário: {motive}",
            reference=reference,
            operator=actor.username,
        )


# ----------------------------------------------------------------------- Consultas
def products_to_restock(conn: sqlite3.Connection) -> list[Product]:
    """RF10: produtos ativos com saldo igual ou abaixo do mínimo (mais críticos primeiro)."""
    products = catalog_repo.find_products(conn, only_below_minimum=True)
    return sorted(products, key=lambda p: (p.stock - p.min_stock, p.name.casefold()))


def list_movements(
    conn: sqlite3.Connection,
    actor: User,
    *,
    start: str | None = None,
    end: str | None = None,
    movement_type: str | None = None,
    product_id: int | None = None,
    text: str = "",
    limit: int = 1000,
) -> list[StockMovement]:
    """RF16: histórico de movimentações."""
    permissions.ensure_permission(actor, permissions.STOCK_HISTORY)
    return catalog_repo.list_movements(
        conn,
        start=start,
        end=end,
        movement_type=movement_type,
        product_id=product_id,
        text=text,
        limit=limit,
    )
