"""Movimentações de estoque (RF16, RNF04): auditoria por data, operador, motivo e referência."""

from __future__ import annotations

from datetime import timedelta

import streamlit as st

from ... import clock
from ...models import User
from ...services import catalog, stock
from .. import components, formatting, state

TYPE_FILTERS = {"": "Entradas e saídas", "entrada": "Somente entradas", "saida": "Somente saídas"}
HISTORY_LIMIT = 1000


def render(user: User) -> None:
    today = clock.today()
    with state.db() as conn:
        all_products = catalog.search_products(conn, include_inactive=True)
    names = {p.id: p.name for p in all_products}

    st.caption(
        "Todo ajuste de saldo — venda, cancelamento, devolução, troca ou movimentação manual — fica registrado aqui."
    )
    c1, c2, c3, c4 = st.columns([1.3, 1.1, 1.4, 1.6])
    period = c1.date_input(
        "Período",
        value=(today - timedelta(days=29), today),
        key="movements_period",
        format="DD/MM/YYYY",
    )
    kind = c2.selectbox(
        "Tipo", list(TYPE_FILTERS), format_func=TYPE_FILTERS.__getitem__, key="movements_type"
    )
    product_id = c3.selectbox(
        "Produto",
        [None, *names],
        format_func=lambda pid: "Todos os produtos" if pid is None else names[pid],
        key="movements_product",
    )
    text = c4.text_input(
        "Motivo, referência ou operador", key="movements_text", placeholder="Ex.: V20261027-0001"
    )
    start, end = formatting.date_range_iso(period)

    with state.db() as conn:
        movements = stock.list_movements(
            conn,
            user,
            start=start,
            end=end,
            movement_type=kind or None,
            product_id=product_id,
            text=text,
            limit=HISTORY_LIMIT,
        )

    entries = sum(m.quantity for m in movements if m.type == "entrada")
    exits = sum(m.quantity for m in movements if m.type == "saida")
    components.metrics(
        [
            ("Movimentações", str(len(movements)), "No filtro atual"),
            ("Unidades que entraram", f"▲ {entries}", "Entradas, devoluções e trocas"),
            ("Unidades que saíram", f"▼ {exits}", "Vendas, perdas e saídas"),
        ]
    )
    if len(movements) >= HISTORY_LIMIT:
        components.alert(
            "warn",
            f"Mostrando as {HISTORY_LIMIT} movimentações mais recentes. Reduza o período para ver as demais.",
        )
    rows = formatting.movement_rows(movements)
    components.table(
        rows,
        empty="Nenhuma movimentação encontrada.",
        hint="Amplie o período ou limpe os filtros.",
        height=min(600, 60 + 35 * max(len(rows), 1)),
    )
    if rows:
        st.download_button(
            "Baixar histórico (.csv)",
            data=formatting.rows_to_csv(rows),
            file_name=f"movimentacoes_{clock.today_iso()}.csv",
            mime="text/csv",
            key="movements_csv",
        )
