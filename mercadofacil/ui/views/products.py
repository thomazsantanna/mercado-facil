"""Produtos e estoque (RF08, RF09, RF10, RB02, RB03)."""

from __future__ import annotations

import zlib
from typing import Any

import streamlit as st

from ... import errors
from ...models import Product, StockMovement, User
from ...money import format_brl, format_input, parse_money
from ...services import catalog, permissions, stock
from .. import compat, components, formatting, state

K_SEARCH = "products_search"
K_CATEGORY = "products_category"
K_STATUS = "products_status"
K_SELECTED = "products_selected"
ALL_CATEGORIES = "Todas as categorias"
STATUS_FILTERS = {
    "ativos": "Somente ativos",
    "repor": "Abaixo do mínimo (repor)",
    "inativos": "Inclui inativos",
}
KIND_LABELS = {
    "entrada": "Entrada",
    "saida": "Saída",
    "perda": "Perda",
    "ajuste": "Ajuste de inventário",
}
NEW_CATEGORY_LABEL = "Nova categoria (opcional — substitui a seleção acima)"


# ------------------------------------------------------------------------------- tela
def render(user: User) -> None:
    can_manage = permissions.can(user, permissions.PRODUCT_MANAGE)
    can_move = permissions.can(user, permissions.STOCK_MOVE)

    with state.db() as conn:
        to_restock = stock.products_to_restock(conn)
        categories = catalog.list_categories(conn)
    _restock_alert(to_restock)

    top_left, top_right = st.columns([3, 1], vertical_alignment="bottom")
    with top_left:
        components.section_title("Catálogo")
    with top_right:
        if can_manage and compat.stretch(
            st.button, "＋ Novo produto", key="products_new", type="primary"
        ):
            _new_product_dialog(user)

    f1, f2, f3 = st.columns([2, 1.2, 1.2])
    term = f1.text_input(
        "Buscar", key=K_SEARCH, placeholder="Nome, código, categoria ou localização"
    )
    category = f2.selectbox("Categoria", [ALL_CATEGORIES, *categories], key=K_CATEGORY)
    status = f3.selectbox(
        "Situação", list(STATUS_FILTERS), format_func=STATUS_FILTERS.__getitem__, key=K_STATUS
    )

    with state.db() as conn:
        products = catalog.search_products(
            conn,
            term=term,
            category=None if category == ALL_CATEGORIES else category,
            include_inactive=status == "inativos",
            only_below_minimum=status == "repor",
        )
    st.caption(f"{len(products)} produto(s) encontrado(s).")
    components.table(
        formatting.product_rows(products),
        empty="Nenhum produto encontrado.",
        hint="Ajuste os filtros ou cadastre um novo produto.",
        height=min(560, 60 + 35 * max(len(products), 1)),
    )
    _selection_panel(user, products, can_manage=can_manage, can_move=can_move)


def _restock_alert(to_restock: list[Product]) -> None:
    """RF10: alerta de estoque mínimo."""
    if not to_restock:
        components.alert(
            "ok", "Todos os produtos ativos estão acima do estoque mínimo.", title="Estoque em dia"
        )
        return
    empty = sum(1 for p in to_restock if p.stock <= 0)
    names = [f"{p.name} — saldo {p.stock} (mínimo {p.min_stock})" for p in to_restock[:5]]
    more = len(to_restock) - len(names)
    if more > 0:
        names.append(f"… e mais {more} produto(s). Filtre por “Abaixo do mínimo” para ver todos.")
    components.alert(
        "warn" if not empty else "danger",
        f"{len(to_restock)} produto(s) no estoque mínimo ou abaixo dele, {empty} sem estoque.",
        title="Reposição necessária",
        items=names,
    )


# ------------------------------------------------------------------ seleção e ações
def _selection_panel(
    user: User, products: list[Product], *, can_manage: bool, can_move: bool
) -> None:
    components.section_title("Ações sobre um produto")
    if not products:
        return
    by_id = {p.id: p for p in products}
    # A chave muda quando a lista muda: a seleção nunca "escorrega" para outro produto.
    signature = zlib.crc32(",".join(str(pid) for pid in by_id).encode())
    selected_id = st.selectbox(
        "Produto selecionado",
        [None, *by_id],
        format_func=lambda pid: (
            "— escolha um produto —" if pid is None else formatting.product_label(by_id[pid])
        ),
        key=f"{K_SELECTED}_{signature}",
    )
    if selected_id is None or selected_id not in by_id:
        st.caption("Selecione um produto para movimentar o estoque, editar ou inativar.")
        return
    product = by_id[selected_id]
    status_tone = "ok" if product.is_active else "neutral"
    components.html(
        f'<div class="mf-card"><strong>{components.esc(product.name)}</strong> '
        f"{components.badge_markup('Ativo' if product.is_active else 'Inativo', status_tone)} "
        f"{components.stock_badge_markup(product)}<br>"
        f"Código {components.esc(product.barcode)} · {components.esc(product.category)} · "
        f"local {components.esc(product.location or '—')}<br>"
        f"Preço {components.esc(format_brl(product.price_cents))} · custo {components.esc(format_brl(product.cost_cents))} · "
        f"mínimo {product.min_stock} {components.esc(product.unit)}</div>"
    )
    c1, c2, c3 = st.columns(3)
    with c1:
        if can_move and compat.stretch(
            st.button,
            "Movimentar",
            key="products_move",
            type="primary",
            disabled=not product.is_active,
        ):
            _move_dialog(user, product.id)
        if can_move and not product.is_active:
            st.caption("Reative o produto para movimentar o estoque.")
    with c2:
        if can_manage and compat.stretch(st.button, "Editar dados", key="products_edit"):
            _edit_product_dialog(user, product.id)
    with c3:
        if can_manage:
            label = "Inativar produto" if product.is_active else "Reativar produto"
            compat.stretch(
                st.button,
                label,
                key="products_toggle",
                on_click=_toggle_active,
                args=(product.id, not product.is_active),
            )


def _toggle_active(product_id: int, active: bool) -> None:
    user = state.current_user()
    if user is None:
        return
    try:
        with state.db() as conn:
            product = catalog.set_active(conn, user, product_id, active)
    except errors.MercadoFacilError as exc:
        state.flash("danger", str(exc))
        return
    verb = "reativado" if active else "inativado"
    state.flash("ok", f"Produto “{product.name}” {verb}. O histórico foi preservado (RB12).")


# ----------------------------------------------------------------- formulário de produto
def _money(text: str, label: str, *, required: bool) -> int:
    value = str(text or "").strip()
    if not value:
        if required:
            raise errors.ValidationError(f"Informe {label}.")
        return 0
    try:
        return parse_money(value)
    except errors.ValidationError as exc:
        raise errors.ValidationError(f"{label[0].upper()}{label[1:]}: {exc}") from None


def _product_fields(categories: list[str], product: Product | None, prefix: str) -> dict[str, Any]:
    """Campos do formulário de cadastro/edição (RF08). Devolve os valores digitados."""
    values: dict[str, Any] = {}
    values["barcode"] = st.text_input(
        "Código de barras *", value=product.barcode if product else "", key=f"{prefix}_barcode"
    )
    values["name"] = st.text_input(
        "Nome do produto *", value=product.name if product else "", key=f"{prefix}_name"
    )
    c1, c2 = st.columns(2)
    current = product.category if product else categories[0]
    options = categories if current in categories else [current, *categories]
    values["category"] = c1.selectbox(
        "Categoria", options, index=options.index(current), key=f"{prefix}_category"
    )
    new_category = c2.text_input(NEW_CATEGORY_LABEL, key=f"{prefix}_new_category")
    if new_category.strip():
        values["category"] = new_category
    c3, c4, c5 = st.columns(3)
    values["unit"] = c3.selectbox(
        "Unidade",
        catalog.UNITS,
        index=catalog.UNITS.index(product.unit) if product and product.unit in catalog.UNITS else 0,
        key=f"{prefix}_unit",
    )
    values["price"] = c4.text_input(
        "Preço de venda (R$) *",
        value=format_input(product.price_cents) if product else "",
        key=f"{prefix}_price",
        placeholder="0,00",
    )
    values["cost"] = c5.text_input(
        "Custo (R$)",
        value=format_input(product.cost_cents) if product else "",
        key=f"{prefix}_cost",
        placeholder="0,00",
    )
    c6, c7, c8 = st.columns(3)
    values["location"] = c6.text_input(
        "Localização",
        value=product.location if product else "",
        key=f"{prefix}_location",
        placeholder="Corredor, prateleira…",
    )
    values["min_stock"] = c7.number_input(
        "Estoque mínimo",
        min_value=0,
        step=1,
        value=product.min_stock if product else 0,
        key=f"{prefix}_min_stock",
        help="Abaixo (ou igual) a este saldo, o produto aparece no alerta de reposição.",
    )
    if product is None:
        values["initial_stock"] = c8.number_input(
            "Estoque inicial", min_value=0, step=1, value=0, key=f"{prefix}_initial_stock"
        )
    else:
        c8.text_input(
            "Saldo atual (somente leitura)",
            value=str(product.stock),
            disabled=True,
            key=f"{prefix}_stock_view",
        )
    return values


@compat.dialog("Novo produto")
def _new_product_dialog(user: User) -> None:
    with state.db() as conn:
        categories = catalog.list_categories(conn)
    with st.form("new_product_form"):
        values = _product_fields(categories, None, "new_product")
        submitted = compat.stretch(st.form_submit_button, "Cadastrar produto", type="primary")
    if not submitted:
        return

    def create() -> Product:
        with state.db() as conn:
            return catalog.create_product(
                conn,
                user,
                barcode=values["barcode"],
                name=values["name"],
                price_cents=_money(values["price"], "o preço de venda", required=True),
                cost_cents=_money(values["cost"], "o custo", required=False),
                unit=values["unit"],
                category=values["category"],
                location=values["location"],
                min_stock=int(values["min_stock"]),
                initial_stock=int(values["initial_stock"]),
            )

    ok, _ = components.run_action(
        create,
        success=lambda p: f"Produto “{p.name}” cadastrado com saldo inicial de {p.stock} {p.unit}.",
    )
    if ok:
        compat.rerun()


@compat.dialog("Editar produto")
def _edit_product_dialog(user: User, product_id: int) -> None:
    with state.db() as conn:
        product = catalog.get_product(conn, product_id)
        categories = catalog.list_categories(conn)
    st.caption("O saldo do estoque só muda por movimentação (Movimentar), nunca por edição.")
    with st.form(f"edit_product_form_{product.id}"):
        values = _product_fields(categories, product, f"edit_product_{product.id}")
        submitted = compat.stretch(st.form_submit_button, "Salvar alterações", type="primary")
    if not submitted:
        return

    def update() -> Product:
        with state.db() as conn:
            return catalog.update_product(
                conn,
                user,
                product.id,
                barcode=values["barcode"],
                name=values["name"],
                price_cents=_money(values["price"], "o preço de venda", required=True),
                cost_cents=_money(values["cost"], "o custo", required=False),
                unit=values["unit"],
                category=values["category"],
                location=values["location"],
                min_stock=int(values["min_stock"]),
            )

    ok, _ = components.run_action(update, success=lambda p: f"Produto “{p.name}” atualizado.")
    if ok:
        compat.rerun()


# -------------------------------------------------------------------------- movimentar
@compat.dialog("Movimentar estoque")
def _move_dialog(user: User, product_id: int) -> None:
    """RF09: entrada, saída, perda ou ajuste, sempre com motivo; referência opcional."""
    with state.db() as conn:
        product = catalog.get_product(conn, product_id)
    components.alert("info", f"Saldo atual: {product.stock} {product.unit}.", title=product.name)

    prefix = f"move_{product.id}"
    kind = st.radio(
        "Operação",
        list(KIND_LABELS),
        format_func=KIND_LABELS.__getitem__,
        horizontal=True,
        key=f"{prefix}_kind",
    )
    reasons = stock.REASONS_BY_KIND[kind]
    preset = st.selectbox("Motivo", reasons, key=f"{prefix}_reason_{kind}")
    needs_detail = preset == stock.OTHER_REASON
    detail = st.text_input(
        "Detalhe do motivo (obrigatório)" if needs_detail else "Detalhe do motivo (opcional)",
        key=f"{prefix}_detail_{kind}",
    )
    if kind == "ajuste":
        quantity = int(
            st.number_input(
                "Quantidade contada (novo saldo)",
                min_value=0,
                step=1,
                value=product.stock,
                key=f"{prefix}_counted",
                help="Informe o saldo físico encontrado; o sistema calcula a diferença.",
            )
        )
        new_balance = quantity
    else:
        quantity = int(
            st.number_input("Quantidade", min_value=1, step=1, value=1, key=f"{prefix}_qty_{kind}")
        )
        new_balance = product.stock + (quantity if kind == "entrada" else -quantity)
    reference = st.text_input(
        "Referência (nota fiscal, pedido, ocorrência…)", key=f"{prefix}_reference"
    )

    if new_balance < 0:
        components.alert(
            "danger",
            f"O saldo ficaria em {new_balance}. O estoque não pode ficar negativo (RB03).",
            title="Estoque negativo impedido",
        )
    else:
        components.alert("neutral", f"Novo saldo previsto: {new_balance} {product.unit}.")

    if not compat.stretch(
        st.button, "Registrar movimentação", key=f"{prefix}_submit", type="primary"
    ):
        return

    def register() -> StockMovement:
        with state.db() as conn:
            motive = stock.compose_reason(preset, detail)
            if kind == "ajuste":
                return stock.adjust_stock(
                    conn,
                    user,
                    product_id=product.id,
                    counted_quantity=quantity,
                    reason=motive,
                    reference=reference,
                )
            return stock.register_movement(
                conn,
                user,
                product_id=product.id,
                kind=kind,
                quantity=quantity,
                reason=motive,
                reference=reference,
            )

    ok, movement = components.run_action(
        register,
        success=lambda m: (
            f"{formatting.movement_type_label(m.type)} de {m.quantity} registrada em “{product.name}”. "
            f"Novo saldo: {m.balance_after}."
        ),
    )
    if ok and movement is not None:
        compat.rerun()
