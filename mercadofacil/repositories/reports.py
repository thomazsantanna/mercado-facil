"""Consultas agregadas para os indicadores operacionais (seção 1)."""

from __future__ import annotations

import sqlite3


def sales_totals(conn: sqlite3.Connection, start: str, end: str) -> dict[str, int]:
    """Totais de vendas criadas no período (datas 'AAAA-MM-DD', inclusivas)."""
    sales = conn.execute(
        """SELECT
               COALESCE(SUM(CASE WHEN status IN ('concluida', 'parcial') THEN 1 ELSE 0 END), 0)
                   AS valid_count,
               COALESCE(SUM(CASE WHEN status IN ('cancelada', 'devolvida') THEN 1 ELSE 0 END), 0)
                   AS cancelled_count,
               COALESCE(SUM(total_cents), 0) AS gross
             FROM sales
            WHERE substr(created_at, 1, 10) BETWEEN ? AND ?""",
        (start, end),
    ).fetchone()
    ops = conn.execute(
        """SELECT COALESCE(SUM(amount_cents), 0) AS net_out,
                  COALESCE(SUM(CASE WHEN amount_cents > 0 THEN amount_cents ELSE 0 END), 0)
                      AS refunds
             FROM post_sale_operations
            WHERE substr(created_at, 1, 10) BETWEEN ? AND ?""",
        (start, end),
    ).fetchone()
    items = conn.execute(
        """SELECT COALESCE(SUM(i.quantity - i.cancelled_qty - i.returned_qty), 0)
             FROM sale_items i JOIN sales s ON s.id = i.sale_id
            WHERE substr(s.created_at, 1, 10) BETWEEN ? AND ?""",
        (start, end),
    ).fetchone()[0]
    return {
        "valid_count": int(sales["valid_count"]),
        "cancelled_count": int(sales["cancelled_count"]),
        "gross": int(sales["gross"]),
        "net_out": int(ops["net_out"]),
        "refunds": int(ops["refunds"]),
        "items_sold": int(items),
    }


def sales_by_payment(conn: sqlite3.Connection, start: str, end: str) -> list[tuple[str, int, int]]:
    rows = conn.execute(
        """SELECT payment_method, COUNT(*) AS n, COALESCE(SUM(total_cents), 0) AS total
             FROM sales
            WHERE substr(created_at, 1, 10) BETWEEN ? AND ?
              AND status IN ('concluida', 'parcial')
            GROUP BY payment_method ORDER BY total DESC""",
        (start, end),
    ).fetchall()
    return [(row["payment_method"], int(row["n"]), int(row["total"])) for row in rows]


def sales_by_day(conn: sqlite3.Connection, start: str, end: str) -> list[tuple[str, int, int]]:
    rows = conn.execute(
        """SELECT substr(created_at, 1, 10) AS day, COUNT(*) AS n,
                  COALESCE(SUM(total_cents), 0) AS total
             FROM sales
            WHERE substr(created_at, 1, 10) BETWEEN ? AND ?
              AND status IN ('concluida', 'parcial')
            GROUP BY day ORDER BY day""",
        (start, end),
    ).fetchall()
    return [(row["day"], int(row["n"]), int(row["total"])) for row in rows]


def top_products(
    conn: sqlite3.Connection, start: str, end: str, limit: int = 5
) -> list[tuple[str, int, int]]:
    rows = conn.execute(
        """SELECT p.name AS name,
                  SUM(i.quantity - i.cancelled_qty - i.returned_qty) AS qty,
                  SUM((i.quantity - i.cancelled_qty - i.returned_qty) * i.unit_price_cents) AS total
             FROM sale_items i
             JOIN sales s ON s.id = i.sale_id
             JOIN products p ON p.id = i.product_id
            WHERE substr(s.created_at, 1, 10) BETWEEN ? AND ?
            GROUP BY p.id
           HAVING qty > 0
            ORDER BY qty DESC, total DESC
            LIMIT ?""",
        (start, end, limit),
    ).fetchall()
    return [(row["name"], int(row["qty"]), int(row["total"])) for row in rows]


def stock_alert_counts(conn: sqlite3.Connection) -> tuple[int, int]:
    """(produtos ativos com saldo <= mínimo e > 0, produtos ativos sem estoque)."""
    row = conn.execute(
        """SELECT
               COALESCE(SUM(CASE WHEN stock > 0 AND stock <= min_stock THEN 1 ELSE 0 END), 0)
                   AS low,
               COALESCE(SUM(CASE WHEN stock <= 0 THEN 1 ELSE 0 END), 0) AS empty
             FROM products WHERE active = 1"""
    ).fetchone()
    return int(row["low"]), int(row["empty"])


def cashback_outstanding(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COALESCE(SUM(cashback_cents), 0) FROM customers").fetchone()[0])
