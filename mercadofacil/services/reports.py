"""Indicadores de vendas e reposição (relatórios operacionais, seção 1; alerta RF10)."""

from __future__ import annotations

import sqlite3

from .. import clock
from ..models import OverviewKPIs, Sale, User
from ..repositories import reports as reports_repo
from ..repositories import sales as sales_repo
from . import permissions


def overview(conn: sqlite3.Connection, actor: User, start: str, end: str) -> OverviewKPIs:
    """Indicadores do período (datas 'AAAA-MM-DD' inclusivas).

    Faturamento líquido = total das vendas criadas no período − estornos líquidos
    pagos aos clientes no período (diferenças de troca pagas pelo cliente entram
    como receita).
    """
    permissions.ensure_permission(actor, permissions.DASHBOARD_VIEW)
    totals = reports_repo.sales_totals(conn, start, end)
    low, empty = reports_repo.stock_alert_counts(conn)
    net = totals["gross"] - totals["net_out"]
    valid = totals["valid_count"]
    return OverviewKPIs(
        sales_count=valid,
        gross_cents=totals["gross"],
        refunds_cents=totals["refunds"],
        net_cents=net,
        average_ticket_cents=net // valid if valid else 0,
        items_sold=totals["items_sold"],
        cancelled_count=totals["cancelled_count"],
        low_stock_count=low,
        out_of_stock_count=empty,
        cashback_outstanding_cents=reports_repo.cashback_outstanding(conn),
    )


def payment_breakdown(
    conn: sqlite3.Connection, actor: User, start: str, end: str
) -> list[tuple[str, int, int]]:
    permissions.ensure_permission(actor, permissions.DASHBOARD_VIEW)
    return reports_repo.sales_by_payment(conn, start, end)


def daily_sales(
    conn: sqlite3.Connection, actor: User, start: str, end: str
) -> list[tuple[str, int, int]]:
    permissions.ensure_permission(actor, permissions.DASHBOARD_VIEW)
    return reports_repo.sales_by_day(conn, start, end)


def top_products(
    conn: sqlite3.Connection, actor: User, start: str, end: str, limit: int = 5
) -> list[tuple[str, int, int]]:
    permissions.ensure_permission(actor, permissions.DASHBOARD_VIEW)
    return reports_repo.top_products(conn, start, end, limit)


def recent_sales(conn: sqlite3.Connection, actor: User, limit: int = 10) -> list[Sale]:
    permissions.ensure_permission(actor, permissions.SALE_VIEW)
    return sales_repo.list_sales(conn, limit=limit)


def today_range() -> tuple[str, str]:
    today = clock.today_iso()
    return today, today
