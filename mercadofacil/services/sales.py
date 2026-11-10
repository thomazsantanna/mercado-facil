"""Frente de caixa: carrinho, pagamento e conclusão da venda (RF03–RF07, RB01–RB07)."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from datetime import datetime

from .. import clock
from ..database import transaction
from ..errors import BusinessRuleError, NotFoundError
from ..models import (
    CartLine,
    CartSummary,
    Customer,
    Sale,
    SaleDetail,
    User,
)
from ..repositories import catalog as catalog_repo
from ..repositories import customers as customers_repo
from ..repositories import sales as sales_repo
from ..validators import normalize_cpf, require_non_negative_int, require_positive_int
from . import cash_register, customers, payments, permissions, stock

CartInput = Sequence[tuple[int, int]]  # (product_id, quantidade)


def _merge_lines(lines: CartInput) -> dict[int, int]:
    merged: dict[int, int] = {}
    for product_id, quantity in lines:
        qty = require_positive_int(quantity, "A quantidade")
        merged[int(product_id)] = merged.get(int(product_id), 0) + qty
    return merged


def _stock_message(name: str, available: int, requested: int) -> str:
    return (
        f"Venda bloqueada: estoque insuficiente para “{name}” (disponível {available}, "
        f"solicitado {requested}). A venda não pode superar o saldo em estoque."
    )


def price_cart(
    conn: sqlite3.Connection,
    lines: CartInput,
    *,
    customer_cpf: str | None = None,
    cashback_to_use: int = 0,
    check_stock: bool = True,
) -> CartSummary:
    """Calcula subtotal, cashback, total líquido e cashback a acumular.

    Com `check_stock=False` (exibição na tela) a quantidade acima do saldo é
    sinalizada em `CartLine.has_stock_issue` em vez de gerar erro (RB03).
    """
    merged = _merge_lines(lines)
    if not merged:
        raise BusinessRuleError("O carrinho está vazio. Adicione ao menos um item.")

    cart_lines: list[CartLine] = []
    for product_id, quantity in merged.items():
        product = catalog_repo.get_product(conn, product_id)
        if product is None:
            raise NotFoundError("Produto não encontrado.")
        if not product.is_active:
            raise BusinessRuleError(
                f"O produto “{product.name}” está inativo e não pode ser vendido."
            )
        if check_stock and quantity > product.stock:
            raise BusinessRuleError(
                _stock_message(product.name, product.stock, quantity), rule="RB03"
            )
        cart_lines.append(CartLine(product=product, quantity=quantity))

    subtotal = sum(line.subtotal_cents for line in cart_lines)

    customer: Customer | None = None
    if customer_cpf:
        customer = customers_repo.get_customer(conn, normalize_cpf(customer_cpf))
        if customer is None:
            raise NotFoundError("Cliente não cadastrado. Cadastre o CPF antes de continuar.")

    used = require_non_negative_int(cashback_to_use, "O cashback utilizado")
    customers.validate_cashback_use(customer, used, subtotal)

    total = subtotal - used
    earned = customers.calculate_cashback_earned(total) if customer is not None else 0
    return CartSummary(
        lines=cart_lines,
        subtotal_cents=subtotal,
        cashback_used_cents=used,
        total_cents=total,
        cashback_earned_cents=earned,
        customer=customer,
    )


def _next_sale_id(conn: sqlite3.Connection, moment: datetime) -> str:
    prefix = f"V{moment.strftime('%Y%m%d')}-"
    sequence = sales_repo.count_sales_with_prefix(conn, prefix) + 1
    return f"{prefix}{sequence:04d}"


def finalize_sale(
    conn: sqlite3.Connection,
    actor: User,
    lines: CartInput,
    *,
    payment_method: str,
    received_cents: int | None = None,
    customer_cpf: str | None = None,
    cashback_to_use: int = 0,
    electronic_approved: bool = True,
) -> SaleDetail:
    """finalizar(): conclui a venda de forma atômica.

    Valida caixa aberto (RB01), estoque (RB03), pagamento (RB04/RB05) e
    cashback (RB06/RB07); baixa o estoque com movimentações referenciando a venda.
    """
    permissions.ensure_permission(actor, permissions.SALE_CREATE)
    with transaction(conn):
        register = cash_register.require_open_register(
            conn,
            actor.username,
            "Venda não autorizada: o caixa está fechado. "
            "Abra o caixa em “Abertura e fechamento” antes de vender.",
        )
        summary = price_cart(
            conn,
            lines,
            customer_cpf=customer_cpf,
            cashback_to_use=cashback_to_use,
            check_stock=True,
        )

        method = payment_method
        received = 0
        change = 0
        if summary.total_cents == 0:
            method = "cashback"  # compra quitada integralmente com o saldo de cashback
        else:
            payments.validate_method(method)
            if method == "dinheiro":
                if received_cents is None:
                    raise BusinessRuleError("Informe o valor recebido em dinheiro.", rule="RB04")
                received = require_non_negative_int(received_cents, "O valor recebido")
                change = payments.calculate_change(summary.total_cents, received, method)
            else:
                payments.authorize_electronic_payment(
                    method, summary.total_cents, approved=electronic_approved
                )
                received = summary.total_cents

        moment = clock.now()
        created_at = moment.strftime(clock.DATETIME_FORMAT)
        sale_id = _next_sale_id(conn, moment)
        customer = summary.customer

        sales_repo.insert_sale(
            conn,
            sale_id=sale_id,
            register_id=register.id,
            customer_cpf=customer.cpf if customer else None,
            subtotal_cents=summary.subtotal_cents,
            cashback_used_cents=summary.cashback_used_cents,
            total_cents=summary.total_cents,
            payment_method=method,
            change_cents=change,
            cashback_earned_cents=summary.cashback_earned_cents,
            operator=actor.username,
            created_at=created_at,
        )
        for line in summary.lines:
            sales_repo.insert_item(
                conn,
                sale_id=sale_id,
                product_id=line.product.id,
                quantity=line.quantity,
                unit_price_cents=line.unit_price_cents,
            )
            stock.apply_movement(
                conn,
                product_id=line.product.id,
                movement_type="saida",
                quantity=line.quantity,
                reason=stock.REASON_SALE,
                reference=sale_id,
                operator=actor.username,
            )
        sales_repo.insert_payment(
            conn,
            sale_id=sale_id,
            method=method,
            amount_cents=summary.total_cents,
            received_cents=received,
            change_cents=change,
            status="aprovado",
            created_at=created_at,
        )
        if customer is not None:
            net_change = summary.cashback_earned_cents - summary.cashback_used_cents
            if net_change:
                customers_repo.adjust_cashback(conn, customer.cpf, net_change)

        detail = load_detail(conn, sale_id)
    return detail


# --------------------------------------------------------------------- Consultas
def load_detail(conn: sqlite3.Connection, sale_id: str) -> SaleDetail:
    """Monta a venda completa (sem checar permissão; uso interno)."""
    sale = sales_repo.get_sale(conn, sale_id)
    if sale is None:
        raise NotFoundError(f"Venda {sale_id} não encontrada.")
    customer = customers_repo.get_customer(conn, sale.customer_cpf) if sale.customer_cpf else None
    return SaleDetail(
        sale=sale,
        items=sales_repo.get_items(conn, sale_id),
        payment=sales_repo.get_payment(conn, sale_id),
        operations=sales_repo.list_operations(conn, sale_id=sale_id),
        customer=customer,
    )


def get_sale_detail(conn: sqlite3.Connection, actor: User, sale_id: str) -> SaleDetail:
    """RF15: itens, pagamentos e ocorrências de uma venda."""
    permissions.ensure_permission(actor, permissions.SALE_VIEW)
    return load_detail(conn, sale_id.strip())


def list_sales(
    conn: sqlite3.Connection,
    actor: User,
    *,
    start: str | None = None,
    end: str | None = None,
    status: str | None = None,
    payment_method: str | None = None,
    text: str = "",
    limit: int = 500,
) -> list[Sale]:
    """RF15: consulta de vendas com filtros."""
    permissions.ensure_permission(actor, permissions.SALE_VIEW)
    return sales_repo.list_sales(
        conn,
        start=start,
        end=end,
        status=status,
        payment_method=payment_method,
        text=text,
        limit=limit,
    )
