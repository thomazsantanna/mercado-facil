"""Pós-venda: cancelamento, devolução e troca (RF11–RF14, RB08–RB10, RB12).

Modelo financeiro
-----------------
Uma venda pode ter parte do valor paga com cashback (`cashback_used`). Para
manter o dinheiro e o cashback coerentes em estornos parciais, o valor devolvido
é proporcional ao que foi pago em dinheiro/cartão/Pix:

    reembolso_acumulado(G) = round(total_líquido × G / subtotal)

onde G é o valor bruto (preço original) já cancelado ou devolvido. Cada operação
reembolsa a diferença entre o acumulado novo e o anterior, de modo que a soma
das operações sempre fecha exatamente no total líquido. A parte do bruto que não
foi reembolsada em dinheiro é devolvida ao cliente como cashback, e o cashback
acumulado na venda é estornado na mesma proporção (limitado ao saldo atual).

Trocas usam o preço original do item devolvido contra o preço atual do produto
substituto; o cashback da venda original não é recalculado.

Operações feitas por operador exigem autorização de um gestor (usuário e senha
do gestor); o gestor se autoriza automaticamente.
"""

from __future__ import annotations

import sqlite3

from .. import clock
from ..config import ROLE_MANAGER
from ..database import transaction
from ..errors import BusinessRuleError, NotFoundError, PermissionDeniedError, ValidationError
from ..models import PAYMENT_METHODS, PostSaleOperation, Sale, SaleItem, User
from ..money import format_brl
from ..repositories import catalog as catalog_repo
from ..repositories import customers as customers_repo
from ..repositories import registers as registers_repo
from ..repositories import sales as sales_repo
from ..validators import optional_text, require_positive_int, require_text
from . import auth, customers, permissions, stock


# ----------------------------------------------------------------------- Cálculos
def proportional_amount(net_total_cents: int, subtotal_cents: int, gross_cents: int) -> int:
    """round_half_up(net × gross / subtotal) em aritmética inteira."""
    if subtotal_cents <= 0 or gross_cents <= 0:
        return 0
    return (2 * net_total_cents * gross_cents + subtotal_cents) // (2 * subtotal_cents)


def recompute_status(items: list[SaleItem]) -> str:
    """Status da venda a partir das quantidades ativas (RB12: o status é o resultado)."""
    active = sum(item.active_qty for item in items)
    cancelled = sum(item.cancelled_qty for item in items)
    returned = sum(item.returned_qty for item in items)
    if active == 0:
        return "devolvida" if returned > 0 else "cancelada"
    if cancelled or returned:
        return "parcial"
    return "concluida"


# --------------------------------------------------------------------- Auxiliares
def _resolve_authorizer(
    conn: sqlite3.Connection,
    actor: User,
    supervisor_username: str | None,
    supervisor_password: str | None,
) -> str:
    """Gestor autoriza a si mesmo; operador precisa das credenciais de um gestor."""
    permissions.ensure_permission(actor, permissions.POSTSALE_REGISTER)
    if actor.role == ROLE_MANAGER:
        return actor.username
    if not (supervisor_username or "").strip() or not supervisor_password:
        raise PermissionDeniedError(
            "Esta operação exige autorização de um gestor. Informe o usuário e a senha do gestor."
        )
    return auth.authorize_manager(conn, supervisor_username or "", supervisor_password).username


def _load_open_sale(conn: sqlite3.Connection, sale_id: str) -> tuple[Sale, list[SaleItem]]:
    sale = sales_repo.get_sale(conn, sale_id)
    if sale is None:
        raise NotFoundError(f"Venda {sale_id} não encontrada.")
    if not sale.accepts_post_sale:
        raise BusinessRuleError(
            f"A venda {sale.id} está “{sale.status_label}” e não aceita novas operações "
            "de pós-venda."
        )
    return sale, sales_repo.get_items(conn, sale_id)


def _load_item(conn: sqlite3.Connection, sale: Sale, item_id: int) -> SaleItem:
    item = sales_repo.get_item(conn, item_id)
    if item is None or item.sale_id != sale.id:
        raise NotFoundError("Item não encontrado nesta venda.")
    return item


def _financials(conn: sqlite3.Connection, sale: Sale, gross_new: int) -> tuple[int, int, int]:
    """(dinheiro a devolver, cashback a restituir, cashback a estornar — teórico)."""
    gross_old = sales_repo.gross_reverted(conn, sale.id)
    refund_old = proportional_amount(sale.total_cents, sale.subtotal_cents, gross_old)
    refund_new = proportional_amount(sale.total_cents, sale.subtotal_cents, gross_old + gross_new)
    money = refund_new - refund_old
    restored = gross_new - money
    earned = sale.cashback_earned_cents
    reversed_new = min(earned, customers.calculate_cashback_earned(refund_new))
    reversed_old = min(earned, customers.calculate_cashback_earned(refund_old))
    return money, restored, reversed_new - reversed_old


def _apply_cashback(
    conn: sqlite3.Connection, sale: Sale, restored_cents: int, reversed_cents: int
) -> int:
    """Ajusta o saldo do cliente e devolve o estorno efetivamente aplicado."""
    if sale.customer_cpf is None:
        return 0
    customer = customers_repo.get_customer(conn, sale.customer_cpf)
    if customer is None:
        return 0
    applied_reversal = min(reversed_cents, customer.cashback_cents + restored_cents)
    delta = restored_cents - applied_reversal
    if delta:
        customers_repo.adjust_cashback(conn, customer.cpf, delta)
    return applied_reversal


def _require_register_for_cash(
    conn: sqlite3.Connection, actor: User, method: str, amount_cents: int
) -> int | None:
    """Devolução ou recebimento em dinheiro mexe na gaveta: exige caixa aberto."""
    register = registers_repo.get_open_register(conn, actor.username)
    if method == "dinheiro" and amount_cents != 0 and register is None:
        raise BusinessRuleError(
            "Abra o caixa para registrar movimentação em dinheiro "
            "(devolução ou diferença de troca).",
            rule="RB01",
        )
    return register.id if register else None


def _record(
    conn: sqlite3.Connection,
    *,
    sale: Sale,
    op_type: str,
    product_id: int | None,
    replacement_product_id: int | None,
    quantity: int,
    amount_cents: int,
    gross_cents: int,
    method: str,
    restored: int,
    reversed_applied: int,
    register_id: int | None,
    actor: User,
    authorized_by: str,
    notes: str,
) -> PostSaleOperation:
    operation_id = sales_repo.insert_operation(
        conn,
        sale_id=sale.id,
        op_type=op_type,
        product_id=product_id,
        replacement_product_id=replacement_product_id,
        quantity=quantity,
        amount_cents=amount_cents,
        gross_cents=gross_cents,
        settlement_method=method,
        cashback_restored_cents=restored,
        cashback_reversed_cents=reversed_applied,
        register_id=register_id,
        operator=actor.username,
        authorized_by=authorized_by,
        notes=notes,
        created_at=clock.now_iso(),
    )
    sales_repo.set_sale_status(conn, sale.id, recompute_status(sales_repo.get_items(conn, sale.id)))
    operation = sales_repo.get_operation(conn, operation_id)
    assert operation is not None
    return operation


def _reverse_items(
    conn: sqlite3.Connection,
    actor: User,
    authorized_by: str,
    sale: Sale,
    removals: list[tuple[SaleItem, int]],
    *,
    op_type: str,
    reason: str,
    notes: str,
    restock: bool,
    product_id: int | None,
    as_return: bool,
) -> PostSaleOperation:
    """Núcleo de cancelamento/devolução: ajusta itens, estoque, cashback e caixa."""
    gross = sum(qty * item.unit_price_cents for item, qty in removals)
    quantity = sum(qty for _, qty in removals)
    money, restored, reversed_theoretical = _financials(conn, sale, gross)
    register_id = _require_register_for_cash(conn, actor, sale.payment_method, money)

    for item, qty in removals:
        if as_return:
            sales_repo.add_item_adjustment(conn, item.id, returned=qty)
        else:
            sales_repo.add_item_adjustment(conn, item.id, cancelled=qty)
        if restock:
            stock.apply_movement(
                conn,
                product_id=item.product_id,
                movement_type="entrada",
                quantity=qty,
                reason=reason,
                reference=sale.id,
                operator=actor.username,
            )
    reversed_applied = _apply_cashback(conn, sale, restored, reversed_theoretical)
    return _record(
        conn,
        sale=sale,
        op_type=op_type,
        product_id=product_id,
        replacement_product_id=None,
        quantity=quantity,
        amount_cents=money,
        gross_cents=gross,
        method=sale.payment_method,
        restored=restored,
        reversed_applied=reversed_applied,
        register_id=register_id,
        actor=actor,
        authorized_by=authorized_by,
        notes=notes,
    )


# ------------------------------------------------------------------------ RF11
def cancel_sale(
    conn: sqlite3.Connection,
    actor: User,
    sale_id: str,
    *,
    notes: str,
    supervisor_username: str | None = None,
    supervisor_password: str | None = None,
) -> PostSaleOperation:
    """Cancela a venda completa e devolve ao estoque só a quantidade ainda ativa (RB08)."""
    authorized_by = _resolve_authorizer(conn, actor, supervisor_username, supervisor_password)
    reason_notes = require_text(notes, "o motivo do cancelamento", max_length=250)
    with transaction(conn):
        sale, items = _load_open_sale(conn, sale_id)
        removals = [(item, item.active_qty) for item in items if item.active_qty > 0]
        if not removals:
            raise BusinessRuleError("A venda não possui itens ativos para cancelar.", rule="RB08")
        return _reverse_items(
            conn,
            actor,
            authorized_by,
            sale,
            removals,
            op_type="cancelamento_venda",
            reason=stock.REASON_SALE_CANCEL,
            notes=reason_notes,
            restock=True,
            product_id=None,
            as_return=False,
        )


# ------------------------------------------------------------------------ RF12
def cancel_item(
    conn: sqlite3.Connection,
    actor: User,
    sale_id: str,
    item_id: int,
    quantity: int,
    *,
    notes: str,
    supervisor_username: str | None = None,
    supervisor_password: str | None = None,
) -> PostSaleOperation:
    """Cancela um item (ou parte da quantidade) de venda concluída."""
    authorized_by = _resolve_authorizer(conn, actor, supervisor_username, supervisor_password)
    reason_notes = require_text(notes, "o motivo do cancelamento", max_length=250)
    qty = require_positive_int(quantity, "A quantidade a cancelar")
    with transaction(conn):
        sale, _ = _load_open_sale(conn, sale_id)
        item = _load_item(conn, sale, item_id)
        if qty > item.active_qty:
            raise BusinessRuleError(
                f"Operação bloqueada: a quantidade a cancelar ({qty}) supera a quantidade ainda "
                f"ativa de “{item.product_name}” ({item.active_qty}).",
                rule="RB08",
            )
        return _reverse_items(
            conn,
            actor,
            authorized_by,
            sale,
            [(item, qty)],
            op_type="cancelamento_item",
            reason=stock.REASON_ITEM_CANCEL,
            notes=reason_notes,
            restock=True,
            product_id=item.product_id,
            as_return=False,
        )


# ------------------------------------------------------------------------ RF13
def return_item(
    conn: sqlite3.Connection,
    actor: User,
    sale_id: str,
    item_id: int,
    quantity: int,
    *,
    notes: str,
    restock: bool = True,
    supervisor_username: str | None = None,
    supervisor_password: str | None = None,
) -> PostSaleOperation:
    """Registra devolução parcial. `restock=False` para item sem condição de revenda."""
    authorized_by = _resolve_authorizer(conn, actor, supervisor_username, supervisor_password)
    reason_notes = require_text(notes, "o motivo da devolução", max_length=250)
    qty = require_positive_int(quantity, "A quantidade a devolver")
    with transaction(conn):
        sale, _ = _load_open_sale(conn, sale_id)
        item = _load_item(conn, sale, item_id)
        if qty > item.active_qty:
            raise BusinessRuleError(
                f"Operação bloqueada: a devolução ({qty}) não pode superar a quantidade "
                f"disponível de “{item.product_name}” ({item.active_qty}).",
                rule="RB09",
            )
        return _reverse_items(
            conn,
            actor,
            authorized_by,
            sale,
            [(item, qty)],
            op_type="devolucao",
            reason=stock.REASON_RETURN,
            notes=reason_notes if restock else f"{reason_notes} (item não retornou ao estoque)",
            restock=restock,
            product_id=item.product_id,
            as_return=True,
        )


# ------------------------------------------------------------------------ RF14
def exchange_item(
    conn: sqlite3.Connection,
    actor: User,
    sale_id: str,
    item_id: int,
    replacement_product_id: int,
    quantity: int,
    *,
    notes: str,
    settlement_method: str | None = None,
    supervisor_username: str | None = None,
    supervisor_password: str | None = None,
) -> PostSaleOperation:
    """Troca o item por outro produto, movimentando os dois estoques (RB10).

    Se o substituto custar mais, o cliente paga a diferença por `settlement_method`;
    se custar menos, a diferença é devolvida pela forma de pagamento original.
    """
    authorized_by = _resolve_authorizer(conn, actor, supervisor_username, supervisor_password)
    reason_notes = require_text(notes, "o motivo da troca", max_length=250)
    qty = require_positive_int(quantity, "A quantidade a trocar")
    with transaction(conn):
        sale, _ = _load_open_sale(conn, sale_id)
        item = _load_item(conn, sale, item_id)
        if qty > item.active_qty:
            raise BusinessRuleError(
                f"Operação bloqueada: a troca ({qty}) não pode superar a quantidade "
                f"disponível de “{item.product_name}” ({item.active_qty}).",
                rule="RB09",
            )
        replacement = catalog_repo.get_product(conn, replacement_product_id)
        if replacement is None:
            raise NotFoundError("Produto substituto não encontrado.")
        if not replacement.is_active:
            raise BusinessRuleError(f"O produto “{replacement.name}” está inativo.")
        if replacement.id == item.product_id:
            raise BusinessRuleError(
                "Escolha um produto diferente na troca. "
                "Para item com defeito, registre uma devolução."
            )
        if replacement.stock < qty:
            raise BusinessRuleError(
                f"Troca bloqueada: o produto substituto “{replacement.name}” tem saldo "
                f"{replacement.stock}, menor que a quantidade da troca ({qty}).",
                rule="RB10",
            )

        gross = qty * item.unit_price_cents
        replacement_value = qty * replacement.price_cents
        difference = replacement_value - gross  # > 0: cliente paga; < 0: cliente recebe
        restored = 0
        if difference > 0:
            if settlement_method not in PAYMENT_METHODS:
                raise ValidationError(
                    f"Informe como o cliente pagará a diferença de {format_brl(difference)}."
                )
            method = settlement_method
            amount = -difference
        elif difference < 0:
            if sale.payment_method == "cashback":
                if sale.customer_cpf is None:
                    raise BusinessRuleError(
                        "A venda não tem cliente para receber o crédito de cashback."
                    )
                method, amount, restored = "cashback", 0, -difference
            else:
                method, amount = sale.payment_method, -difference
        else:
            method, amount = "", 0

        register_id = _require_register_for_cash(conn, actor, method, amount)

        sales_repo.add_item_adjustment(conn, item.id, returned=qty)
        stock.apply_movement(
            conn,
            product_id=item.product_id,
            movement_type="entrada",
            quantity=qty,
            reason=stock.REASON_EXCHANGE_IN,
            reference=sale.id,
            operator=actor.username,
        )
        stock.apply_movement(
            conn,
            product_id=replacement.id,
            movement_type="saida",
            quantity=qty,
            reason=stock.REASON_EXCHANGE_OUT,
            reference=sale.id,
            operator=actor.username,
        )
        if restored:
            customers_repo.adjust_cashback(conn, sale.customer_cpf or "", restored)

        return _record(
            conn,
            sale=sale,
            op_type="troca",
            product_id=item.product_id,
            replacement_product_id=replacement.id,
            quantity=qty,
            amount_cents=amount,
            gross_cents=gross,
            method=method,
            restored=restored,
            reversed_applied=0,
            register_id=register_id,
            actor=actor,
            authorized_by=authorized_by,
            notes=optional_text(reason_notes, "as observações", max_length=250),
        )


# ----------------------------------------------------------------------- Consultas
def list_operations(
    conn: sqlite3.Connection,
    actor: User,
    *,
    sale_id: str | None = None,
    start: str | None = None,
    end: str | None = None,
    op_type: str | None = None,
    limit: int = 500,
) -> list[PostSaleOperation]:
    """RF15: ocorrências de pós-venda."""
    permissions.ensure_permission(actor, permissions.SALE_VIEW)
    return sales_repo.list_operations(
        conn, sale_id=sale_id, start=start, end=end, op_type=op_type, limit=limit
    )
