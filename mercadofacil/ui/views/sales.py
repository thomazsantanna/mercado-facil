"""Vendas e pós-venda (RF11 a RF15, RB08 a RB10, RB12).

Consulta de vendas, itens, pagamentos e ocorrências; cancelamento de item, devolução,
troca e cancelamento da venda inteira. O operador precisa da autorização de um gestor.
"""

from __future__ import annotations

import zlib
from datetime import timedelta

import streamlit as st

from ... import clock
from ...models import (
    PAYMENT_METHOD_LABELS,
    PAYMENT_METHODS,
    SALE_STATUS_LABELS,
    PostSaleOperation,
    SaleDetail,
    SaleItem,
    User,
)
from ...money import format_brl
from ...services import catalog, permissions, post_sale, receipts, sales
from ...validators import mask_cpf
from .. import compat, components, formatting, state

K_PERIOD = "sales_period"
K_STATUS = "sales_status"
K_PAYMENT = "sales_payment"
K_TEXT = "sales_text"
K_SELECTED = "sales_selected"
ALL = ""


def render(user: User) -> None:
    today = clock.today()
    c1, c2, c3, c4 = st.columns([1.3, 1.1, 1.1, 1.5])
    period = c1.date_input(
        "Período",
        value=(today - timedelta(days=6), today),
        key=K_PERIOD,
        format="DD/MM/YYYY",
    )
    status = c2.selectbox(
        "Status",
        [ALL, *SALE_STATUS_LABELS],
        format_func=lambda s: "Todos" if s == ALL else SALE_STATUS_LABELS[s],
        key=K_STATUS,
    )
    method = c3.selectbox(
        "Pagamento",
        [ALL, *PAYMENT_METHOD_LABELS],
        format_func=lambda m: "Todos" if m == ALL else PAYMENT_METHOD_LABELS[m],
        key=K_PAYMENT,
    )
    text = c4.text_input(
        "ID, cliente ou CPF", key=K_TEXT, placeholder="Ex.: V20261027-0001 ou Maria"
    )
    start, end = formatting.date_range_iso(period)

    with state.db() as conn:
        found = sales.list_sales(
            conn,
            user,
            start=start,
            end=end,
            status=status or None,
            payment_method=method or None,
            text=text,
            limit=300,
        )
    st.caption(f"{len(found)} venda(s) encontrada(s).")
    components.table(
        formatting.sale_rows(found),
        empty="Nenhuma venda encontrada.",
        hint="Amplie o período ou limpe os filtros.",
        height=min(420, 60 + 35 * max(len(found), 1)),
    )
    if not found:
        return

    components.section_title("Detalhe da venda")
    signature = zlib.crc32(",".join(s.id for s in found).encode())
    by_id = {s.id: s for s in found}
    sale_id = st.selectbox(
        "Venda",
        [None, *by_id],
        format_func=lambda sid: (
            "— escolha uma venda —" if sid is None else formatting.sale_label(by_id[sid])
        ),
        key=f"{K_SELECTED}_{signature}",
    )
    if sale_id is None:
        st.caption(
            "Escolha uma venda para ver itens, pagamento, ocorrências e registrar pós-venda."
        )
        return

    with state.db() as conn:
        detail = sales.get_sale_detail(conn, user, sale_id)
    _detail_panel(user, detail)


# ----------------------------------------------------------------------------- detalhe
def _detail_panel(user: User, detail: SaleDetail) -> None:
    sale = detail.sale
    tone = {"concluida": "ok", "parcial": "warn", "cancelada": "danger", "devolvida": "info"}.get(
        sale.status, "neutral"
    )
    customer = (
        f"{detail.customer.name} (CPF {mask_cpf(detail.customer.cpf)})"
        if detail.customer
        else "não identificado"
    )
    components.html(
        f'<div class="mf-card"><strong>Venda {components.esc(sale.id)}</strong> '
        f"{components.badge_markup(sale.status_label, tone)}<br>"
        f"{components.esc(clock.format_datetime(sale.created_at))} · operador {components.esc(sale.operator)}"
        f" · cliente {components.esc(customer)}</div>"
    )
    components.metrics(
        [
            ("Subtotal", format_brl(sale.subtotal_cents), ""),
            ("Cashback utilizado", format_brl(sale.cashback_used_cents), ""),
            ("Total pago", format_brl(sale.total_cents), f"em {sale.payment_label}"),
            (
                "Troco",
                format_brl(sale.change_cents) if sale.payment_method == "dinheiro" else "—",
                "Somente dinheiro (RB05)",
            ),
            (
                "Cashback gerado",
                format_brl(sale.cashback_earned_cents),
                "1% do total líquido (RB07)",
            ),
        ],
        per_row=3,
    )

    st.markdown("**Itens**")
    components.table(formatting.sale_item_rows(detail.items))
    if detail.payment is not None:
        pay = detail.payment
        st.caption(
            components.md_escape(
                f"Pagamento: {formatting.payment_label(pay.method)} · valor {format_brl(pay.amount_cents)}"
                f" · recebido {format_brl(pay.received_cents)} · troco {format_brl(pay.change_cents)}"
                f" · {pay.status}"
            )
        )
    st.markdown("**Ocorrências de pós-venda**")
    components.table(
        formatting.operation_rows(detail.operations),
        empty="Nenhuma ocorrência registrada nesta venda.",
    )
    with st.expander("Comprovante"):
        components.receipt_block(receipts.build_receipt(detail))

    _actions(user, detail)


def _actions(user: User, detail: SaleDetail) -> None:
    sale = detail.sale
    if not permissions.can(user, permissions.POSTSALE_REGISTER):
        return
    components.section_title("Pós-venda")
    if not sale.accepts_post_sale:
        components.alert(
            "neutral",
            f"A venda está “{sale.status_label}” e não aceita novas operações. O histórico é preservado (RB12).",
        )
        return
    if user.role != "gestor":
        st.caption(
            "Como operador, cada operação exige a autorização de um gestor (usuário e senha)."
        )
    has_active = any(item.active_qty > 0 for item in detail.items)
    if not has_active:
        components.alert(
            "neutral", "Todos os itens desta venda já foram cancelados, devolvidos ou trocados."
        )
        return
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if compat.stretch(st.button, "Cancelar item", key=f"sales_cancel_item_{sale.id}"):
            _cancel_item_dialog(user, sale.id)
    with c2:
        if compat.stretch(st.button, "Devolver", key=f"sales_return_{sale.id}"):
            _return_dialog(user, sale.id)
    with c3:
        if compat.stretch(st.button, "Trocar", key=f"sales_exchange_{sale.id}"):
            _exchange_dialog(user, sale.id)
    with c4:
        if compat.stretch(st.button, "Cancelar venda inteira", key=f"sales_cancel_{sale.id}"):
            _cancel_sale_dialog(user, sale.id)


# ------------------------------------------------------------------------------ diálogos
def _load_detail(user: User, sale_id: str) -> SaleDetail:
    with state.db() as conn:
        return sales.get_sale_detail(conn, user, sale_id)


def _item_choices(detail: SaleDetail) -> dict[int, SaleItem]:
    return {item.id: item for item in detail.items if item.active_qty > 0}


def _pick_item(detail: SaleDetail, key: str) -> SaleItem:
    choices = _item_choices(detail)
    item_id = st.selectbox(
        "Item da venda",
        list(choices),
        format_func=lambda iid: formatting.item_label(choices[iid]),
        key=key,
    )
    return choices[item_id]


@compat.dialog("Cancelar item da venda")
def _cancel_item_dialog(user: User, sale_id: str) -> None:
    detail = _load_detail(user, sale_id)
    prefix = f"cancel_item_{sale_id}"
    st.caption(
        "RF12 — o item cancelado volta ao estoque e o valor é devolvido proporcionalmente (RB08)."
    )
    with st.form(f"{prefix}_form"):
        item = _pick_item(detail, f"{prefix}_item")
        quantity = int(
            st.number_input(
                "Quantidade a cancelar", min_value=1, step=1, value=1, key=f"{prefix}_qty"
            )
        )
        notes = st.text_area("Motivo do cancelamento *", key=f"{prefix}_notes")
        sup_user, sup_pass = components.supervisor_credentials(user, prefix)
        submitted = compat.stretch(st.form_submit_button, "Cancelar item", type="primary")
    if not submitted:
        return

    def action() -> PostSaleOperation:
        with state.db() as conn:
            return post_sale.cancel_item(
                conn,
                user,
                sale_id,
                item.id,
                quantity,
                notes=notes,
                supervisor_username=sup_user,
                supervisor_password=sup_pass,
            )

    ok, _ = components.run_action(action, success=formatting.describe_operation)
    if ok:
        compat.rerun()


@compat.dialog("Devolver item")
def _return_dialog(user: User, sale_id: str) -> None:
    detail = _load_detail(user, sale_id)
    prefix = f"return_{sale_id}"
    st.caption(
        "RF13 — devolução parcial; não pode superar a quantidade ainda disponível do item (RB09)."
    )
    with st.form(f"{prefix}_form"):
        item = _pick_item(detail, f"{prefix}_item")
        quantity = int(
            st.number_input(
                "Quantidade a devolver", min_value=1, step=1, value=1, key=f"{prefix}_qty"
            )
        )
        restock = st.checkbox(
            "Item em condição de revenda (volta ao estoque)", value=True, key=f"{prefix}_restock"
        )
        notes = st.text_area("Motivo da devolução *", key=f"{prefix}_notes")
        sup_user, sup_pass = components.supervisor_credentials(user, prefix)
        submitted = compat.stretch(st.form_submit_button, "Registrar devolução", type="primary")
    if not submitted:
        return

    def action() -> PostSaleOperation:
        with state.db() as conn:
            return post_sale.return_item(
                conn,
                user,
                sale_id,
                item.id,
                quantity,
                notes=notes,
                restock=restock,
                supervisor_username=sup_user,
                supervisor_password=sup_pass,
            )

    ok, _ = components.run_action(action, success=formatting.describe_operation)
    if ok:
        compat.rerun()


@compat.dialog("Trocar item")
def _exchange_dialog(user: User, sale_id: str) -> None:
    detail = _load_detail(user, sale_id)
    prefix = f"exchange_{sale_id}"
    st.caption("RF14 — movimenta os dois produtos; o substituto precisa ter saldo (RB10).")
    item = _pick_item(detail, f"{prefix}_item")
    with state.db() as conn:
        replacements = [p for p in catalog.search_products(conn) if p.id != item.product_id]
    by_id = {p.id: p for p in replacements}
    if not by_id:
        components.alert("warn", "Não há outro produto ativo para a troca.")
        return
    replacement_id = st.selectbox(
        "Produto que o cliente leva",
        list(by_id),
        format_func=lambda pid: formatting.product_label(by_id[pid]),
        key=f"{prefix}_replacement",
    )
    replacement = by_id[replacement_id]
    quantity = int(
        st.number_input(
            "Quantidade a trocar", min_value=1, step=1, value=1, key=f"{prefix}_qty_{item.id}"
        )
    )
    difference = quantity * (replacement.price_cents - item.unit_price_cents)
    settlement: str | None = None
    if difference > 0:
        components.alert(
            "warn",
            f"O cliente paga a diferença de {format_brl(difference)}.",
            title="Produto mais caro",
        )
        settlement = st.radio(
            "Forma de pagamento da diferença",
            list(PAYMENT_METHODS),
            format_func=PAYMENT_METHODS.__getitem__,
            horizontal=True,
            key=f"{prefix}_settlement",
        )
    elif difference < 0:
        components.alert(
            "info",
            f"O cliente recebe {format_brl(-difference)} pela forma de pagamento original ({detail.sale.payment_label}).",
            title="Produto mais barato",
        )
    else:
        components.alert("neutral", "Sem diferença de valor.")
    notes = st.text_area("Motivo da troca *", key=f"{prefix}_notes")
    sup_user, sup_pass = components.supervisor_credentials(user, prefix)

    if not compat.stretch(st.button, "Registrar troca", key=f"{prefix}_submit", type="primary"):
        return

    def action() -> PostSaleOperation:
        with state.db() as conn:
            return post_sale.exchange_item(
                conn,
                user,
                sale_id,
                item.id,
                replacement.id,
                quantity,
                notes=notes,
                settlement_method=settlement,
                supervisor_username=sup_user,
                supervisor_password=sup_pass,
            )

    ok, _ = components.run_action(action, success=formatting.describe_operation)
    if ok:
        compat.rerun()


@compat.dialog("Cancelar venda inteira")
def _cancel_sale_dialog(user: User, sale_id: str) -> None:
    prefix = f"cancel_sale_{sale_id}"
    components.alert(
        "warn",
        "Todos os itens ainda ativos voltam ao estoque e o valor é devolvido ao cliente. "
        "A venda não é apagada: ela passa a constar como cancelada (RB08, RB12).",
        title=f"Cancelar a venda {sale_id}?",
    )
    with st.form(f"{prefix}_form"):
        notes = st.text_area("Motivo do cancelamento *", key=f"{prefix}_notes")
        confirmed = st.checkbox("Confirmo o cancelamento desta venda", key=f"{prefix}_confirm")
        sup_user, sup_pass = components.supervisor_credentials(user, prefix)
        submitted = compat.stretch(st.form_submit_button, "Cancelar venda", type="primary")
    if not submitted:
        return
    if not confirmed:
        components.alert(
            "danger", "Marque a confirmação para cancelar a venda.", title="Confirmação necessária"
        )
        return

    def action() -> PostSaleOperation:
        with state.db() as conn:
            return post_sale.cancel_sale(
                conn,
                user,
                sale_id,
                notes=notes,
                supervisor_username=sup_user,
                supervisor_password=sup_pass,
            )

    ok, _ = components.run_action(action, success=formatting.describe_operation)
    if ok:
        compat.rerun()
