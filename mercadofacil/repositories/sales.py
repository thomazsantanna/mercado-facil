"""Vendas, itens, pagamentos e ocorrências de pós-venda."""

from __future__ import annotations

import sqlite3
from typing import Any

from ..models import Payment, PostSaleOperation, Sale, SaleItem, build, build_all
from ..validators import fold, only_digits

_SALE_SELECT = """
    SELECT s.*, c.name AS customer_name
      FROM sales s
      LEFT JOIN customers c ON c.cpf = s.customer_cpf
"""

_ITEM_SELECT = """
    SELECT i.*, p.name AS product_name, p.barcode AS product_barcode, p.unit AS product_unit
      FROM sale_items i
      JOIN products p ON p.id = i.product_id
"""

_OPERATION_SELECT = """
    SELECT o.*, p.name AS product_name, r.name AS replacement_name
      FROM post_sale_operations o
      LEFT JOIN products p ON p.id = o.product_id
      LEFT JOIN products r ON r.id = o.replacement_product_id
"""


def _escape_like(token: str) -> str:
    return token.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ------------------------------------------------------------------------ Vendas
def count_sales_with_prefix(conn: sqlite3.Connection, prefix: str) -> int:
    like = f"{_escape_like(prefix)}%"
    return int(
        conn.execute("SELECT COUNT(*) FROM sales WHERE id LIKE ? ESCAPE '\\'", (like,)).fetchone()[
            0
        ]
    )


def insert_sale(
    conn: sqlite3.Connection,
    *,
    sale_id: str,
    register_id: int,
    customer_cpf: str | None,
    subtotal_cents: int,
    cashback_used_cents: int,
    total_cents: int,
    payment_method: str,
    change_cents: int,
    cashback_earned_cents: int,
    operator: str,
    created_at: str,
) -> None:
    conn.execute(
        """INSERT INTO sales
               (id, register_id, customer_cpf, subtotal_cents, cashback_used_cents, total_cents,
                payment_method, change_cents, cashback_earned_cents, status, operator, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'concluida', ?, ?)""",
        (
            sale_id,
            register_id,
            customer_cpf,
            subtotal_cents,
            cashback_used_cents,
            total_cents,
            payment_method,
            change_cents,
            cashback_earned_cents,
            operator,
            created_at,
        ),
    )


def get_sale(conn: sqlite3.Connection, sale_id: str) -> Sale | None:
    row = conn.execute(_SALE_SELECT + " WHERE s.id = ?", (sale_id,)).fetchone()
    return build(Sale, row)


def set_sale_status(conn: sqlite3.Connection, sale_id: str, status: str) -> None:
    conn.execute("UPDATE sales SET status = ? WHERE id = ?", (status, sale_id))


def list_sales(
    conn: sqlite3.Connection,
    *,
    start: str | None = None,
    end: str | None = None,
    status: str | None = None,
    payment_method: str | None = None,
    text: str = "",
    operator: str | None = None,
    limit: int = 500,
) -> list[Sale]:
    clauses = ["1 = 1"]
    params: list[Any] = []
    if start:
        clauses.append("substr(s.created_at, 1, 10) >= ?")
        params.append(start)
    if end:
        clauses.append("substr(s.created_at, 1, 10) <= ?")
        params.append(end)
    if status:
        clauses.append("s.status = ?")
        params.append(status)
    if payment_method:
        clauses.append("s.payment_method = ?")
        params.append(payment_method)
    if operator:
        clauses.append("s.operator = ?")
        params.append(operator)
    for token in fold(text).split():
        like = f"%{_escape_like(token)}%"
        digits = only_digits(token)
        cpf_clause = "s.customer_cpf LIKE ? ESCAPE '\\'" if digits else "0"
        clauses.append(
            f"(fold(s.id) LIKE ? ESCAPE '\\' OR fold(c.name) LIKE ? ESCAPE '\\' OR {cpf_clause})"
        )
        params.extend([like, like])
        if digits:
            params.append(f"%{digits}%")
    sql = (
        _SALE_SELECT
        + " WHERE "
        + " AND ".join(clauses)
        + " ORDER BY s.created_at DESC, s.id DESC LIMIT ?"
    )
    params.append(limit)
    return build_all(Sale, conn.execute(sql, params).fetchall())


# ------------------------------------------------------------------------- Itens
def insert_item(
    conn: sqlite3.Connection,
    *,
    sale_id: str,
    product_id: int,
    quantity: int,
    unit_price_cents: int,
) -> int:
    cursor = conn.execute(
        "INSERT INTO sale_items (sale_id, product_id, quantity, unit_price_cents) "
        "VALUES (?, ?, ?, ?)",
        (sale_id, product_id, quantity, unit_price_cents),
    )
    return int(cursor.lastrowid or 0)


def get_items(conn: sqlite3.Connection, sale_id: str) -> list[SaleItem]:
    rows = conn.execute(_ITEM_SELECT + " WHERE i.sale_id = ? ORDER BY i.id", (sale_id,)).fetchall()
    return build_all(SaleItem, rows)


def get_item(conn: sqlite3.Connection, item_id: int) -> SaleItem | None:
    row = conn.execute(_ITEM_SELECT + " WHERE i.id = ?", (item_id,)).fetchone()
    return build(SaleItem, row)


def add_item_adjustment(
    conn: sqlite3.Connection, item_id: int, *, cancelled: int = 0, returned: int = 0
) -> None:
    conn.execute(
        "UPDATE sale_items SET cancelled_qty = cancelled_qty + ?, returned_qty = returned_qty + ? "
        "WHERE id = ?",
        (cancelled, returned, item_id),
    )


# --------------------------------------------------------------------- Pagamentos
def insert_payment(
    conn: sqlite3.Connection,
    *,
    sale_id: str,
    method: str,
    amount_cents: int,
    received_cents: int,
    change_cents: int,
    status: str,
    created_at: str,
) -> int:
    cursor = conn.execute(
        """INSERT INTO payments
               (sale_id, method, amount_cents, received_cents, change_cents, status, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (sale_id, method, amount_cents, received_cents, change_cents, status, created_at),
    )
    return int(cursor.lastrowid or 0)


def get_payment(conn: sqlite3.Connection, sale_id: str) -> Payment | None:
    row = conn.execute(
        "SELECT * FROM payments WHERE sale_id = ? ORDER BY id LIMIT 1", (sale_id,)
    ).fetchone()
    return build(Payment, row)


# ----------------------------------------------------------- Ocorrências de pós-venda
def insert_operation(
    conn: sqlite3.Connection,
    *,
    sale_id: str,
    op_type: str,
    product_id: int | None,
    replacement_product_id: int | None,
    quantity: int,
    amount_cents: int,
    gross_cents: int,
    settlement_method: str,
    cashback_restored_cents: int,
    cashback_reversed_cents: int,
    register_id: int | None,
    operator: str,
    authorized_by: str,
    notes: str,
    created_at: str,
) -> int:
    cursor = conn.execute(
        """INSERT INTO post_sale_operations
               (sale_id, type, product_id, replacement_product_id, quantity, amount_cents,
                gross_cents, settlement_method, cashback_restored_cents, cashback_reversed_cents,
                register_id, operator, authorized_by, notes, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            sale_id,
            op_type,
            product_id,
            replacement_product_id,
            quantity,
            amount_cents,
            gross_cents,
            settlement_method,
            cashback_restored_cents,
            cashback_reversed_cents,
            register_id,
            operator,
            authorized_by,
            notes,
            created_at,
        ),
    )
    return int(cursor.lastrowid or 0)


def get_operation(conn: sqlite3.Connection, operation_id: int) -> PostSaleOperation | None:
    row = conn.execute(_OPERATION_SELECT + " WHERE o.id = ?", (operation_id,)).fetchone()
    return build(PostSaleOperation, row)


def list_operations(
    conn: sqlite3.Connection,
    *,
    sale_id: str | None = None,
    start: str | None = None,
    end: str | None = None,
    op_type: str | None = None,
    limit: int = 500,
) -> list[PostSaleOperation]:
    clauses = ["1 = 1"]
    params: list[Any] = []
    if sale_id:
        clauses.append("o.sale_id = ?")
        params.append(sale_id)
    if start:
        clauses.append("substr(o.created_at, 1, 10) >= ?")
        params.append(start)
    if end:
        clauses.append("substr(o.created_at, 1, 10) <= ?")
        params.append(end)
    if op_type:
        clauses.append("o.type = ?")
        params.append(op_type)
    sql = _OPERATION_SELECT + " WHERE " + " AND ".join(clauses) + " ORDER BY o.id DESC LIMIT ?"
    params.append(limit)
    return build_all(PostSaleOperation, conn.execute(sql, params).fetchall())


def gross_reverted(conn: sqlite3.Connection, sale_id: str) -> int:
    """Valor bruto (preço original) já cancelado/devolvido, sem contar trocas."""
    return int(
        conn.execute(
            "SELECT COALESCE(SUM(gross_cents), 0) FROM post_sale_operations "
            "WHERE sale_id = ? "
            "AND type IN ('cancelamento_venda', 'cancelamento_item', 'devolucao')",
            (sale_id,),
        ).fetchone()[0]
    )
