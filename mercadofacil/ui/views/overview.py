"""Visão geral: indicadores, vendas recentes e alertas de reposição (RF10, seção 7)."""

from __future__ import annotations

import streamlit as st

from ... import clock
from ...models import Product, Sale, User
from ...money import format_brl
from ...services import permissions, reports, stock
from .. import components, formatting, state, theme

K_PERIOD = "overview_period"


def render(user: User) -> None:
    label = st.radio("Período", formatting.PERIODS, horizontal=True, key=K_PERIOD)
    start, end = formatting.period_range(label)
    can_see_sales = permissions.can(user, permissions.SALE_VIEW)

    with state.db() as conn:
        kpis = reports.overview(conn, user, start, end)
        to_restock = stock.products_to_restock(conn)
        payments = reports.payment_breakdown(conn, user, start, end)
        daily = reports.daily_sales(conn, user, start, end)
        top = reports.top_products(conn, user, start, end)
        recent = reports.recent_sales(conn, user, 8) if can_see_sales else []

    components.metrics(
        [
            (
                "Vendas concluídas",
                str(kpis.sales_count),
                f"{kpis.cancelled_count} cancelada(s) no período",
            ),
            (
                "Faturamento líquido",
                format_brl(kpis.net_cents),
                f"Bruto {format_brl(kpis.gross_cents)} · estornos {format_brl(kpis.refunds_cents)}",
            ),
            ("Ticket médio", format_brl(kpis.average_ticket_cents), "Faturamento líquido ÷ vendas"),
            ("Itens vendidos", str(kpis.items_sold), "Unidades ainda ativas nas vendas"),
            (
                "Produtos para repor",
                str(kpis.low_stock_count + kpis.out_of_stock_count),
                f"{kpis.out_of_stock_count} sem estoque · {kpis.low_stock_count} no mínimo",
            ),
            (
                "Cashback em aberto",
                format_brl(kpis.cashback_outstanding_cents),
                "Saldo total dos clientes",
            ),
        ]
    )

    left, right = st.columns(2, gap="large")
    with left:
        _restock_panel(to_restock)
    with right:
        _recent_panel(user, recent, can_see_sales)

    components.section_title("Vendas no período")
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("**Faturamento por dia**")
        _daily_chart(daily)
    with c2:
        st.markdown("**Por forma de pagamento**")
        components.table(
            [
                {
                    "Forma de pagamento": formatting.payment_label(method),
                    "Vendas": count,
                    "Total": format_brl(total),
                }
                for method, count, total in payments
            ],
            empty="Sem vendas no período.",
        )
    st.markdown("**Produtos mais vendidos**")
    components.table(
        [
            {"Produto": name, "Unidades": units, "Faturamento": format_brl(total)}
            for name, units, total in top
        ],
        empty="Sem vendas no período.",
    )


def _restock_panel(to_restock: list[Product]) -> None:
    components.section_title("Alertas de reposição")
    if not to_restock:
        components.alert("ok", "Nenhum produto abaixo do estoque mínimo.", title="Estoque em dia")
        return
    components.table(
        formatting.restock_rows(to_restock[:10]), height=min(420, 60 + 35 * len(to_restock[:10]))
    )
    if len(to_restock) > 10:
        st.caption(f"Mostrando 10 de {len(to_restock)}. Veja todos em Produtos e estoque.")


def _recent_panel(user: User, recent: list[Sale], can_see_sales: bool) -> None:
    components.section_title("Vendas recentes")
    if not can_see_sales:
        components.alert("neutral", f"O perfil “{user.role_label}” não consulta vendas.")
        return
    components.table(
        formatting.sale_rows(recent),
        empty="Nenhuma venda registrada ainda.",
        hint="As vendas aparecem aqui assim que forem concluídas na Frente de caixa.",
    )


def _daily_chart(daily: list[tuple[str, int, int]]) -> None:
    if not daily:
        components.empty_state("Sem vendas no período.")
        return
    import pandas as pd

    frame = pd.DataFrame(
        {
            "Dia": [clock.format_date(day) for day, _, _ in daily],
            "Faturamento (R$)": [total / 100 for _, _, total in daily],
        }
    ).set_index("Dia")
    st.bar_chart(frame, color=theme.PRIMARY)
