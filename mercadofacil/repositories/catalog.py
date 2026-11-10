"""Produtos e movimentações de estoque."""

from __future__ import annotations

import sqlite3
from typing import Any

from ..models import Product, StockMovement, build, build_all
from ..validators import fold

PRODUCT_UPDATABLE = {
    "barcode",
    "name",
    "category",
    "unit",
    "price_cents",
    "cost_cents",
    "min_stock",
    "location",
    "active",
}


# ----------------------------------------------------------------------- Produtos
def get_product(conn: sqlite3.Connection, product_id: int) -> Product | None:
    row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    return build(Product, row)


def get_active_product_by_barcode(conn: sqlite3.Connection, barcode: str) -> Product | None:
    row = conn.execute(
        "SELECT * FROM products WHERE barcode = ? AND active = 1", (barcode,)
    ).fetchone()
    return build(Product, row)


def _escape_like(token: str) -> str:
    return token.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _product_filters(
    *, term: str, category: str | None, include_inactive: bool, only_below_minimum: bool
) -> tuple[str, list[Any]]:
    clauses = ["1 = 1"]
    params: list[Any] = []
    if not include_inactive:
        clauses.append("active = 1")
    if category:
        clauses.append("category = ?")
        params.append(category)
    if only_below_minimum:
        clauses.append("stock <= min_stock")
    for token in fold(term).split():
        like = f"%{_escape_like(token)}%"
        clauses.append(
            "(fold(name) LIKE ? ESCAPE '\\' OR fold(barcode) LIKE ? ESCAPE '\\' "
            "OR fold(category) LIKE ? ESCAPE '\\' OR fold(location) LIKE ? ESCAPE '\\')"
        )
        params.extend([like, like, like, like])
    return " AND ".join(clauses), params


def find_products(
    conn: sqlite3.Connection,
    *,
    term: str = "",
    category: str | None = None,
    include_inactive: bool = False,
    only_below_minimum: bool = False,
    limit: int | None = None,
) -> list[Product]:
    where, params = _product_filters(
        term=term,
        category=category,
        include_inactive=include_inactive,
        only_below_minimum=only_below_minimum,
    )
    sql = f"SELECT * FROM products WHERE {where} ORDER BY fold(name), id"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    return build_all(Product, conn.execute(sql, params).fetchall())


def count_products(
    conn: sqlite3.Connection,
    *,
    term: str = "",
    category: str | None = None,
    include_inactive: bool = False,
    only_below_minimum: bool = False,
) -> int:
    where, params = _product_filters(
        term=term,
        category=category,
        include_inactive=include_inactive,
        only_below_minimum=only_below_minimum,
    )
    return int(conn.execute(f"SELECT COUNT(*) FROM products WHERE {where}", params).fetchone()[0])


def list_categories(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT DISTINCT category FROM products ORDER BY fold(category)").fetchall()
    return [row["category"] for row in rows]


def list_locations(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT DISTINCT location FROM products WHERE location <> '' ORDER BY fold(location)"
    ).fetchall()
    return [row["location"] for row in rows]


def insert_product(
    conn: sqlite3.Connection,
    *,
    barcode: str,
    name: str,
    category: str,
    unit: str,
    price_cents: int,
    cost_cents: int,
    min_stock: int,
    location: str,
    created_at: str,
) -> int:
    cursor = conn.execute(
        """INSERT INTO products
               (barcode, name, category, unit, price_cents, cost_cents,
                stock, min_stock, location, active, created_at)
           VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, 1, ?)""",
        (barcode, name, category, unit, price_cents, cost_cents, min_stock, location, created_at),
    )
    return int(cursor.lastrowid or 0)


def update_product(conn: sqlite3.Connection, product_id: int, **fields: Any) -> None:
    unknown = set(fields) - PRODUCT_UPDATABLE
    if unknown:
        raise ValueError(f"Campos não atualizáveis: {sorted(unknown)}")
    if not fields:
        return
    assignments = ", ".join(f"{column} = ?" for column in fields)
    conn.execute(
        f"UPDATE products SET {assignments} WHERE id = ?",
        [*fields.values(), product_id],
    )


def update_stock(conn: sqlite3.Connection, product_id: int, new_stock: int) -> None:
    conn.execute("UPDATE products SET stock = ? WHERE id = ?", (new_stock, product_id))


# ------------------------------------------------------------------ Movimentações
_MOVEMENT_SELECT = """
    SELECT m.*, p.name AS product_name, p.barcode AS product_barcode
      FROM stock_movements m
      JOIN products p ON p.id = m.product_id
"""


def insert_movement(
    conn: sqlite3.Connection,
    *,
    product_id: int,
    movement_type: str,
    quantity: int,
    balance_after: int,
    reason: str,
    reference: str,
    operator: str,
    created_at: str,
) -> int:
    cursor = conn.execute(
        """INSERT INTO stock_movements
               (product_id, type, quantity, balance_after, reason, reference, operator, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            product_id,
            movement_type,
            quantity,
            balance_after,
            reason,
            reference,
            operator,
            created_at,
        ),
    )
    return int(cursor.lastrowid or 0)


def get_movement(conn: sqlite3.Connection, movement_id: int) -> StockMovement | None:
    row = conn.execute(_MOVEMENT_SELECT + " WHERE m.id = ?", (movement_id,)).fetchone()
    return build(StockMovement, row)


def list_movements(
    conn: sqlite3.Connection,
    *,
    start: str | None = None,
    end: str | None = None,
    movement_type: str | None = None,
    product_id: int | None = None,
    text: str = "",
    operator: str | None = None,
    limit: int = 1000,
) -> list[StockMovement]:
    clauses = ["1 = 1"]
    params: list[Any] = []
    if start:
        clauses.append("substr(m.created_at, 1, 10) >= ?")
        params.append(start)
    if end:
        clauses.append("substr(m.created_at, 1, 10) <= ?")
        params.append(end)
    if movement_type:
        clauses.append("m.type = ?")
        params.append(movement_type)
    if product_id:
        clauses.append("m.product_id = ?")
        params.append(product_id)
    if operator:
        clauses.append("m.operator = ?")
        params.append(operator)
    for token in fold(text).split():
        like = f"%{_escape_like(token)}%"
        clauses.append(
            "(fold(m.reason) LIKE ? ESCAPE '\\' OR fold(m.reference) LIKE ? ESCAPE '\\' "
            "OR fold(p.name) LIKE ? ESCAPE '\\')"
        )
        params.extend([like, like, like])
    sql = _MOVEMENT_SELECT + " WHERE " + " AND ".join(clauses) + " ORDER BY m.id DESC LIMIT ?"
    params.append(limit)
    return build_all(StockMovement, conn.execute(sql, params).fetchall())
