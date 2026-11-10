"""Caixas (turnos)."""

from __future__ import annotations

import sqlite3

from ..models import Register, build, build_all


def get_open_register(conn: sqlite3.Connection, operator: str) -> Register | None:
    row = conn.execute(
        "SELECT * FROM registers WHERE operator = ? AND status = 'aberto'", (operator,)
    ).fetchone()
    return build(Register, row)


def get_register(conn: sqlite3.Connection, register_id: int) -> Register | None:
    row = conn.execute("SELECT * FROM registers WHERE id = ?", (register_id,)).fetchone()
    return build(Register, row)


def insert_register(
    conn: sqlite3.Connection, *, operator: str, opening_cents: int, opened_at: str
) -> int:
    cursor = conn.execute(
        "INSERT INTO registers (operator, status, opening_cents, opened_at) "
        "VALUES (?, 'aberto', ?, ?)",
        (operator, opening_cents, opened_at),
    )
    return int(cursor.lastrowid or 0)


def close_register(
    conn: sqlite3.Connection,
    register_id: int,
    *,
    expected_cents: int,
    counted_cents: int,
    difference_cents: int,
    closed_at: str,
) -> None:
    conn.execute(
        """UPDATE registers
              SET status = 'fechado', expected_cents = ?, counted_cents = ?,
                  difference_cents = ?, closed_at = ?
            WHERE id = ?""",
        (expected_cents, counted_cents, difference_cents, closed_at, register_id),
    )


def list_registers(
    conn: sqlite3.Connection, *, operator: str | None = None, limit: int = 200
) -> list[Register]:
    if operator:
        rows = conn.execute(
            "SELECT * FROM registers WHERE operator = ? ORDER BY id DESC LIMIT ?",
            (operator, limit),
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM registers ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return build_all(Register, rows)


def cash_totals(conn: sqlite3.Connection, register_id: int) -> dict[str, int]:
    """Movimento de dinheiro físico do turno.

    - cash_sales: total das vendas pagas em dinheiro (valor recebido menos troco);
    - cash_out: dinheiro devolvido a clientes em pós-venda (amount_cents > 0);
    - cash_in: diferença paga em dinheiro pelo cliente em trocas (amount_cents < 0).
    """
    sales = conn.execute(
        "SELECT COALESCE(SUM(total_cents), 0) FROM sales "
        "WHERE register_id = ? AND payment_method = 'dinheiro'",
        (register_id,),
    ).fetchone()[0]
    out_row = conn.execute(
        "SELECT COALESCE(SUM(amount_cents), 0) FROM post_sale_operations "
        "WHERE register_id = ? AND settlement_method = 'dinheiro' AND amount_cents > 0",
        (register_id,),
    ).fetchone()[0]
    in_row = conn.execute(
        "SELECT COALESCE(-SUM(amount_cents), 0) FROM post_sale_operations "
        "WHERE register_id = ? AND settlement_method = 'dinheiro' AND amount_cents < 0",
        (register_id,),
    ).fetchone()[0]
    return {"cash_sales": int(sales), "cash_out": int(out_row), "cash_in": int(in_row)}


def sales_by_method(conn: sqlite3.Connection, register_id: int) -> dict[str, tuple[int, int]]:
    rows = conn.execute(
        "SELECT payment_method, COUNT(*) AS n, COALESCE(SUM(total_cents), 0) AS total "
        "FROM sales WHERE register_id = ? GROUP BY payment_method",
        (register_id,),
    ).fetchall()
    return {row["payment_method"]: (int(row["n"]), int(row["total"])) for row in rows}
