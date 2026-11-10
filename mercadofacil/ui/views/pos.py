"""Frente de caixa — PDV (RF03 a RF07, RB01 a RB07).

Padrão de funcionamento: as ações do operador (bipar, alterar quantidade, finalizar…)
são *callbacks* que alteram o estado da sessão antes de a tela ser desenhada; a tela
apenas lê esse estado. Isso evita conflito com widgets já criados e garante que a
resposta apareça imediatamente (7.1).
"""

from __future__ import annotations

import sqlite3

import streamlit as st

from ... import errors
from ...models import PAYMENT_METHODS, CartSummary, Customer, Product, SaleDetail, User
from ...money import format_brl, format_input, parse_money
from ...services import cash_register, catalog, customers, payments, receipts, sales
from ...validators import format_cpf, mask_cpf, normalize_cpf
from .. import cart as cart_ops
from .. import compat, components, state

SCAN_LABEL = "Código de barras ou nome do produto"
GRID_LIMIT = 12
GRID_COLUMNS = 3
BILLS = (2_000, 5_000, 10_000)  # atalhos de cédulas no recebimento em dinheiro

K_CART = "pos_cart"
K_CPF = "pos_customer_cpf"
K_PENDING_CPF = "pos_pending_cpf"
K_LAST_SALE = "pos_last_sale_id"
K_ERROR = "pos_finalize_error"
K_FOCUS = "pos_focus_nonce"
K_SCAN = "pos_scan"
K_SEARCH = "pos_search"
K_CATEGORY = "pos_category"
K_METHOD = "pos_method"
K_RECEIVED = "pos_received"
K_USE_CASHBACK = "pos_use_cashback"
K_CASHBACK_AMOUNT = "pos_cashback_amount"
K_DECLINE = "pos_decline_payment"
K_CPF_INPUT = "pos_cpf_input"
K_NAME_INPUT = "pos_name_input"
ALL_CATEGORIES = "Todas as categorias"


# ------------------------------------------------------------------------------ estado
def _cart() -> cart_ops.Cart:
    value = st.session_state.get(K_CART)
    return dict(value) if isinstance(value, dict) else {}


def _qty_key(product_id: int) -> str:
    return f"pos_qty_{product_id}"


def _bump_focus() -> None:
    st.session_state[K_FOCUS] = int(st.session_state.get(K_FOCUS, 0)) + 1


def _reset_sale_inputs() -> None:
    """Limpa os dados da venda em andamento (carrinho, cliente, pagamento)."""
    for key in list(st.session_state.keys()):
        if str(key).startswith("pos_qty_"):
            del st.session_state[key]
    for key in (
        K_CART,
        K_CPF,
        K_PENDING_CPF,
        K_RECEIVED,
        K_USE_CASHBACK,
        K_CASHBACK_AMOUNT,
        K_DECLINE,
        K_ERROR,
    ):
        st.session_state.pop(key, None)


# ----------------------------------------------------------------------------- callbacks
def _add_product(conn: sqlite3.Connection, product_id: int, quantity: int = 1) -> bool:
    """Adiciona ao carrinho validando o saldo do produto (RB03). Devolve se adicionou."""
    cart = _cart()
    updated = cart_ops.add(cart, product_id, quantity)
    try:
        sales.price_cart(conn, [(product_id, updated[product_id])], check_stock=True)
        product = catalog.get_product(conn, product_id)
    except errors.MercadoFacilError as exc:
        state.flash("danger", str(exc))
        return False
    st.session_state[K_CART] = updated
    st.session_state.pop(_qty_key(product_id), None)  # o campo volta a refletir o carrinho
    st.session_state.pop(K_LAST_SALE, None)
    state.flash("ok", f"“{product.name}” adicionado: {updated[product_id]} no carrinho.")
    return True


def _on_scan() -> None:
    """RF03: leitor de código de barras (digita como teclado) ou busca por nome."""
    text = str(st.session_state.get(K_SCAN, "")).strip()
    _bump_focus()
    if not text:
        return
    with state.db() as conn:
        try:
            product = catalog.find_by_barcode(conn, text)
        except errors.ValidationError:
            product = None  # não parece um código de barras: trata como busca por nome
        if product is not None:
            _add_product(conn, product.id)
            return
        matches = catalog.search_products(conn, term=text, limit=2)
    if len(matches) == 1:
        with state.db() as conn:
            _add_product(conn, matches[0].id)
    elif not matches:
        state.flash(
            "warn",
            f"Nenhum produto ativo encontrado para “{text}”. "
            "Confira o código ou procure pelo nome na lista.",
        )
    else:
        st.session_state[K_SEARCH] = text
        state.flash("info", f"Vários produtos correspondem a “{text}”. Escolha na lista abaixo.")


def _on_add_click(product_id: int) -> None:
    _bump_focus()
    with state.db() as conn:
        _add_product(conn, product_id)


def _on_qty_change(product_id: int) -> None:
    """RF04: alterar quantidade no carrinho (acima do saldo é sinalizado, não apagado)."""
    value = st.session_state.get(_qty_key(product_id))
    try:
        quantity = int(value)
    except (TypeError, ValueError):
        return
    st.session_state[K_CART] = cart_ops.set_quantity(_cart(), product_id, quantity)


def _on_remove(product_id: int) -> None:
    """RF04: cancelar item no carrinho."""
    st.session_state[K_CART] = cart_ops.remove(_cart(), product_id)
    st.session_state.pop(_qty_key(product_id), None)
    state.flash("info", "Item removido do carrinho.")


def _on_clear_cart() -> None:
    _reset_sale_inputs()
    state.flash("info", "Venda em andamento descartada.")


def _on_new_sale() -> None:
    st.session_state.pop(K_LAST_SALE, None)
    _bump_focus()


def _on_identify() -> None:
    """RF07: identificar o cliente pelo CPF."""
    raw = str(st.session_state.get(K_CPF_INPUT, "")).strip()
    if not raw:
        state.flash("warn", "Informe o CPF do cliente.")
        return
    try:
        cpf = normalize_cpf(raw)
        with state.db() as conn:
            customer = customers.find_customer(conn, cpf)
    except errors.MercadoFacilError as exc:
        state.flash("danger", str(exc))
        return
    if customer is None:
        st.session_state[K_PENDING_CPF] = cpf
        state.flash(
            "warn",
            f"O CPF {format_cpf(cpf)} ainda não está cadastrado. Informe o nome para cadastrar.",
        )
        return
    st.session_state[K_CPF] = customer.cpf
    st.session_state.pop(K_PENDING_CPF, None)
    state.flash(
        "ok",
        f"Cliente identificado: {customer.name}. Saldo de cashback {format_brl(customer.cashback_cents)}.",
    )


def _on_register_customer() -> None:
    user = state.current_user()
    cpf = st.session_state.get(K_PENDING_CPF)
    name = str(st.session_state.get(K_NAME_INPUT, ""))
    if user is None or not cpf:
        return
    try:
        with state.db() as conn:
            customer = customers.register_customer(conn, user, cpf, name)
    except errors.MercadoFacilError as exc:
        state.flash("danger", str(exc))
        return
    st.session_state[K_CPF] = customer.cpf
    st.session_state.pop(K_PENDING_CPF, None)
    state.flash("ok", f"Cliente {customer.name} cadastrado e identificado.")


def _on_clear_customer() -> None:
    for key in (K_CPF, K_PENDING_CPF, K_USE_CASHBACK, K_CASHBACK_AMOUNT):
        st.session_state.pop(key, None)
    state.flash("info", "Cliente removido da venda.")


def _on_cancel_register() -> None:
    st.session_state.pop(K_PENDING_CPF, None)


def _on_use_max_cashback(cents: int) -> None:
    st.session_state[K_CASHBACK_AMOUNT] = format_input(cents)


def _on_set_received(cents: int) -> None:
    st.session_state[K_RECEIVED] = format_input(cents)


def _on_finalize() -> None:
    """RF05/RF06: finaliza a venda; qualquer erro de regra volta à tela sem perder o carrinho."""
    user = state.current_user()
    st.session_state.pop(K_ERROR, None)
    if user is None:
        return
    method = str(st.session_state.get(K_METHOD, "dinheiro"))
    cpf = st.session_state.get(K_CPF) or None
    try:
        requested = _parse_optional_money(
            st.session_state.get(K_CASHBACK_AMOUNT, "")
            if st.session_state.get(K_USE_CASHBACK)
            else "",
            "cashback a utilizar",
        )
        received = (
            _parse_optional_money(st.session_state.get(K_RECEIVED, ""), "valor recebido")
            if method == "dinheiro"
            else None
        )
        with state.db() as conn:
            detail = sales.finalize_sale(
                conn,
                user,
                cart_ops.as_lines(_cart()),
                payment_method=method,
                received_cents=received,
                customer_cpf=cpf,
                cashback_to_use=requested or 0,
                electronic_approved=not st.session_state.get(K_DECLINE, False),
            )
    except errors.MercadoFacilError as exc:
        st.session_state[K_ERROR] = exc
        return
    except sqlite3.Error:
        st.session_state[K_ERROR] = errors.MercadoFacilError(
            "O banco de dados não respondeu. Aguarde alguns segundos e tente novamente."
        )
        return
    _reset_sale_inputs()
    st.session_state[K_LAST_SALE] = detail.sale.id
    _bump_focus()


def _parse_optional_money(text: object, label: str) -> int | None:
    value = str(text or "").strip()
    if not value:
        return None
    try:
        return parse_money(value)
    except errors.ValidationError as exc:
        raise errors.ValidationError(f"{label.capitalize()}: {exc}") from None


# ------------------------------------------------------------------------------ tela
def render(user: User) -> None:
    with state.db() as conn:
        register = cash_register.get_open_register(conn, user.username)

    if register is None:
        _closed_register_notice()
    last_sale = st.session_state.get(K_LAST_SALE)
    if last_sale:
        _done_panel(str(last_sale))

    left, right = st.columns([1.3, 1], gap="large")
    with left:
        _catalog_panel()
    with right:
        _cart_panel(user)
    compat.focus_input(SCAN_LABEL, nonce=int(st.session_state.get(K_FOCUS, 0)))


def _closed_register_notice() -> None:
    components.alert(
        "danger",
        "Você pode montar o carrinho, mas a venda só será concluída com o caixa aberto (RB01).",
        title="Caixa fechado",
    )
    st.button(
        "Ir para Abertura e fechamento",
        key="pos_goto_register",
        on_click=state.goto,
        args=("register",),
    )


# --------------------------------------------------------------------- catálogo e leitura
def _catalog_panel() -> None:
    components.section_title("Adicionar produtos")
    with st.form("pos_scan_form", clear_on_submit=True):
        st.text_input(
            SCAN_LABEL, key=K_SCAN, placeholder="Bipe o código ou digite o nome e tecle Enter"
        )
        compat.stretch(
            st.form_submit_button, "Adicionar ao carrinho", type="primary", on_click=_on_scan
        )

    left, right = st.columns([2, 1])
    term = left.text_input(
        "Buscar na lista de produtos", key=K_SEARCH, placeholder="Nome, código ou local"
    )
    with state.db() as conn:
        categories = catalog.list_categories(conn)
        category = right.selectbox("Categoria", [ALL_CATEGORIES, *categories], key=K_CATEGORY)
        selected = None if category == ALL_CATEGORIES else category
        found = catalog.search_products(conn, term=term, category=selected, limit=GRID_LIMIT)
        total = catalog.count_products(conn, term=term, category=selected)

    if not found:
        components.empty_state(
            "Nenhum produto encontrado.",
            "Altere a busca ou a categoria. Produtos inativos não aparecem no caixa.",
        )
        return
    st.caption(
        f"Mostrando {len(found)} de {total} produto(s)."
        + (" Refine a busca para ver outros." if total > len(found) else "")
    )
    for start in range(0, len(found), GRID_COLUMNS):
        row = found[start : start + GRID_COLUMNS]
        for column, product in zip(st.columns(GRID_COLUMNS), row, strict=False):
            with column:
                _product_card(product)


def _product_card(product: Product) -> None:
    with st.container(border=True):
        components.html(
            f"<strong>{components.esc(product.name)}</strong><br>"
            f"{components.esc(format_brl(product.price_cents))} / {components.esc(product.unit)}<br>"
            f"{components.stock_badge_markup(product)}<br>"
            f"<small>{components.esc(product.location or '—')}</small>"
        )
        compat.stretch(
            st.button,
            "Sem estoque" if product.stock <= 0 else "Adicionar",
            key=f"pos_add_{product.id}",
            disabled=product.stock <= 0,
            on_click=_on_add_click,
            args=(product.id,),
        )


# ---------------------------------------------------------------------------- carrinho
def _cart_panel(user: User) -> None:
    cart = _cart()
    components.section_title(f"Carrinho ({cart_ops.units(cart)} un.)" if cart else "Carrinho")
    with state.db() as conn:
        customer = _customer_panel(conn)
        if not cart:
            components.empty_state(
                "O carrinho está vazio.", "Bipe um produto ou escolha na lista ao lado."
            )
            return
        summary = _price(conn, cart, customer)
    if summary is None:
        compat.stretch(
            st.button, "Descartar venda", key="pos_clear_broken", on_click=_on_clear_cart
        )
        return
    _cart_lines(summary)
    _totals_and_payment(summary)


def _price(
    conn: sqlite3.Connection, cart: cart_ops.Cart, customer: Customer | None
) -> CartSummary | None:
    """Calcula o resumo para exibição; erros de regra viram avisos (a validação final é do servidor)."""
    lines = cart_ops.as_lines(cart)
    cpf = customer.cpf if customer else None
    try:
        base = sales.price_cart(conn, lines, customer_cpf=cpf, check_stock=False)
        requested = _requested_cashback()
        if requested:
            try:
                customers.validate_cashback_use(base.customer, requested, base.subtotal_cents)
            except errors.MercadoFacilError as exc:
                components.show_error(exc)  # RB06 (CT07)
                requested = 0
        return sales.price_cart(
            conn, lines, customer_cpf=cpf, cashback_to_use=requested, check_stock=False
        )
    except errors.MercadoFacilError as exc:
        components.show_error(exc)
        return None


def _requested_cashback() -> int:
    if not st.session_state.get(K_USE_CASHBACK):
        return 0
    try:
        return (
            _parse_optional_money(
                st.session_state.get(K_CASHBACK_AMOUNT, ""), "cashback a utilizar"
            )
            or 0
        )
    except errors.ValidationError as exc:
        components.alert("warn", str(exc), title="Valor inválido")
        return 0


def _cart_lines(summary: CartSummary) -> None:
    if summary.has_stock_issue:
        components.alert(
            "warn",
            "Há item acima do saldo disponível. Ajuste a quantidade para concluir a venda (RB03).",
            title="Estoque insuficiente",
        )
    for line in summary.lines:
        product = line.product
        name_col, qty_col, total_col, remove_col = st.columns(
            [3, 1.4, 1.5, 0.8], vertical_alignment="center"
        )
        with name_col:
            issue = (
                components.badge_markup(f"Disponível: {product.stock}", "danger")
                if line.has_stock_issue
                else ""
            )
            components.html(
                f"<strong>{components.esc(product.name)}</strong><br>"
                f"<small>{components.esc(format_brl(line.unit_price_cents))} / {components.esc(product.unit)}</small> {issue}"
            )
        with qty_col:
            st.number_input(
                f"Quantidade de {product.name}",
                min_value=1,
                value=line.quantity,
                step=1,
                key=_qty_key(product.id),
                label_visibility="collapsed",
                on_change=_on_qty_change,
                args=(product.id,),
            )
        with total_col:
            components.html(f"<strong>{components.esc(format_brl(line.subtotal_cents))}</strong>")
        with remove_col:
            st.button(
                "✕",
                key=f"pos_remove_{product.id}",
                help=f"Remover {product.name} do carrinho",
                on_click=_on_remove,
                args=(product.id,),
            )


# --------------------------------------------------------------------- cliente e cashback
def _customer_panel(conn: sqlite3.Connection) -> Customer | None:
    components.html("<strong>Cliente (opcional)</strong>")
    cpf = st.session_state.get(K_CPF)
    customer = customers.find_customer(conn, str(cpf)) if cpf else None
    if customer is not None:
        components.alert(
            "ok",
            f"{customer.name} · CPF {mask_cpf(customer.cpf)} · saldo de cashback "
            f"{format_brl(customer.cashback_cents)}",
            title="Cliente identificado",
        )
        st.button("Remover cliente", key="pos_remove_customer", on_click=_on_clear_customer)
        return customer
    if cpf:  # cliente desapareceu da base: descarta a referência
        st.session_state.pop(K_CPF, None)

    pending = st.session_state.get(K_PENDING_CPF)
    if pending:
        components.alert(
            "warn",
            f"O CPF {format_cpf(str(pending))} ainda não está cadastrado. Informe o nome para cadastrar (apenas CPF e nome são coletados).",
            title="Cliente novo",
        )
        with st.form("pos_register_form", clear_on_submit=True):
            st.text_input("Nome do cliente", key=K_NAME_INPUT)
            compat.stretch(
                st.form_submit_button,
                "Cadastrar e identificar",
                type="primary",
                on_click=_on_register_customer,
            )
        st.button("Cancelar cadastro", key="pos_cancel_register", on_click=_on_cancel_register)
        return None

    with st.form("pos_customer_form", clear_on_submit=True):
        st.text_input("CPF do cliente", key=K_CPF_INPUT, placeholder="000.000.000-00")
        compat.stretch(st.form_submit_button, "Identificar cliente", on_click=_on_identify)
    return None


def _cashback_section(summary: CartSummary) -> None:
    customer = summary.customer
    if customer is None:
        return
    base_subtotal = summary.subtotal_cents
    maximum = customers.max_usable_cashback(customer, base_subtotal)
    if customer.cashback_cents <= 0:
        st.caption("Este cliente ainda não tem saldo de cashback para usar.")
        return
    st.checkbox(
        f"Usar cashback nesta compra (saldo {format_brl(customer.cashback_cents)})",
        key=K_USE_CASHBACK,
    )
    if st.session_state.get(K_USE_CASHBACK):
        components.money_field(
            "Cashback a utilizar (R$)",
            key=K_CASHBACK_AMOUNT,
            default=format_input(maximum),
            help=f"Máximo permitido nesta compra: {format_brl(maximum)}.",
            show_error=False,
        )
        st.button(
            f"Usar o máximo ({format_brl(maximum)})",
            key="pos_cashback_max",
            on_click=_on_use_max_cashback,
            args=(maximum,),
        )


# ----------------------------------------------------------------- totais e pagamento
def _totals_and_payment(summary: CartSummary) -> None:
    _cashback_section(summary)
    rows = [("Subtotal", format_brl(summary.subtotal_cents))]
    if summary.cashback_used_cents:
        rows.append(("Cashback utilizado", f"-{format_brl(summary.cashback_used_cents)}"))
    components.lines_table(["Resumo", "Valor"], rows, numeric=(1,))
    components.html(
        components.highlight_markup("total", "TOTAL A PAGAR", format_brl(summary.total_cents))
    )
    if summary.customer is not None:
        st.caption(
            components.md_escape(
                f"Cashback a receber nesta compra (1% do total): {format_brl(summary.cashback_earned_cents)}"
            )
        )

    if summary.total_cents == 0:
        components.alert(
            "info", "Compra quitada integralmente com o saldo de cashback.", title="Sem pagamento"
        )
    else:
        _payment_section(summary.total_cents)

    error = st.session_state.pop(K_ERROR, None)
    if error is not None:
        components.show_error(error)
    compat.stretch(
        st.button, "Finalizar venda", key="pos_finalize", type="primary", on_click=_on_finalize
    )
    compat.stretch(st.button, "Descartar venda", key="pos_clear", on_click=_on_clear_cart)


def _payment_section(total_cents: int) -> None:
    method = st.radio(
        "Forma de pagamento",
        list(PAYMENT_METHODS),
        format_func=lambda m: PAYMENT_METHODS[m],
        horizontal=True,
        key=K_METHOD,
    )
    if method == "dinheiro":
        received, _ = components.money_field(
            "Valor recebido (R$)",
            key=K_RECEIVED,
            help="Informe quanto o cliente entregou em dinheiro.",
        )
        shortcuts = [("Valor exato", total_cents)] + [
            (format_brl(b), b) for b in BILLS if b > total_cents
        ]
        for column, (label, cents) in zip(st.columns(len(shortcuts)), shortcuts, strict=False):
            with column:
                compat.stretch(
                    st.button,
                    label,
                    key=f"pos_cash_{cents}",
                    on_click=_on_set_received,
                    args=(cents,),
                )
        if received is None:
            st.caption("Informe o valor recebido para calcular o troco automaticamente.")
            return
        try:
            change = payments.calculate_change(total_cents, received, "dinheiro")
        except errors.BusinessRuleError as exc:
            components.show_error(exc)  # RB04 (CT05)
            return
        components.html(components.highlight_markup("change", "TROCO", format_brl(change)))
    else:
        with st.expander("Simulação do sistema de pagamento"):
            st.caption("No protótipo, a aprovação de Pix, débito e crédito é simulada (9.2).")
            st.checkbox("Simular pagamento recusado", key=K_DECLINE)


# ------------------------------------------------------------------- venda concluída
def _done_panel(sale_id: str) -> None:
    with state.db() as conn:
        try:
            detail = sales.load_detail(conn, sale_id)
        except errors.NotFoundError:
            st.session_state.pop(K_LAST_SALE, None)
            return
    _receipt_summary(detail)
    text = receipts.build_receipt(detail)
    with st.expander("Comprovante da venda", expanded=True):
        components.receipt_block(text)
        st.download_button(
            "Baixar comprovante (.txt)",
            data=text,
            file_name=f"comprovante_{detail.sale.id}.txt",
            mime="text/plain",
            key="pos_download_receipt",
        )
    compat.stretch(
        st.button, "Nova venda", key="pos_new_sale", type="primary", on_click=_on_new_sale
    )
    st.divider()


def _receipt_summary(detail: SaleDetail) -> None:
    sale = detail.sale
    components.alert(
        "ok",
        f"Venda {sale.id} registrada em {sale.payment_label}. O estoque foi atualizado.",
        title="Venda concluída",
    )
    left, right = st.columns(2)
    with left:
        components.html(components.highlight_markup("total", "TOTAL", format_brl(sale.total_cents)))
    with right:
        if sale.payment_method == "dinheiro":
            components.html(
                components.highlight_markup("change", "TROCO", format_brl(sale.change_cents))
            )
    if detail.customer is not None:
        components.alert(
            "info",
            f"Cashback gerado: {format_brl(sale.cashback_earned_cents)} · "
            f"novo saldo de {detail.customer.name}: {format_brl(detail.customer.cashback_cents)}.",
            title="Cashback",
        )
