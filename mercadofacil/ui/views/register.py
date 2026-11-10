"""Abertura e fechamento de caixa (RF01, RF02, RB11)."""

from __future__ import annotations

import streamlit as st

from ... import clock
from ...models import Register, RegisterSummary, User
from ...money import format_brl
from ...services import cash_register
from .. import compat, components, formatting, state


def render(user: User) -> None:
    with state.db() as conn:
        register = cash_register.get_open_register(conn, user.username)
        summary = cash_register.summarize(conn, register.id) if register else None
        history = cash_register.list_registers(conn, user)

    if register is None or summary is None:
        _open_panel(user)
    else:
        _summary_panel(summary)
        _close_panel(user, register, summary)

    components.section_title("Histórico de caixas")
    if user.role == "gestor":
        st.caption("Como gestor, você vê o histórico de todos os operadores.")
    else:
        st.caption("Seus turnos de caixa, do mais recente ao mais antigo.")
    components.table(
        formatting.register_rows(history),
        empty="Nenhum caixa foi aberto ainda.",
        hint="Use “Abrir caixa” acima para iniciar o primeiro turno.",
    )


# ------------------------------------------------------------------------------ abertura
def _open_panel(user: User) -> None:
    components.alert(
        "warn",
        "Informe o fundo inicial (dinheiro na gaveta para troco) e abra o caixa para começar a vender.",
        title="Caixa fechado",
    )
    components.section_title("Abrir caixa")
    with st.form("open_register_form"):
        opening, error = components.money_field(
            "Fundo inicial (R$)",
            key="open_register_fund",
            help="Valor em dinheiro colocado na gaveta no início do turno. Pode ser 0,00.",
            show_error=False,
        )
        submitted = compat.stretch(st.form_submit_button, "Abrir caixa", type="primary")
    if not submitted:
        return
    if error is not None:
        components.alert("danger", error, title="Valor inválido")
        return
    if opening is None:
        components.alert(
            "danger", "Informe o fundo inicial (use 0,00 se não houver).", title="Campo obrigatório"
        )
        return

    def open_it() -> Register:
        with state.db() as conn:
            return cash_register.open_register(conn, user, opening)

    ok, opened = components.run_action(
        open_it,
        success=lambda r: f"Caixa aberto com fundo inicial de {format_brl(r.opening_cents)}.",
    )
    if ok and opened is not None:
        compat.rerun()


# ------------------------------------------------------------------------------ resumo
def _summary_panel(summary: RegisterSummary) -> None:
    register = summary.register
    components.alert(
        "ok",
        f"Aberto em {clock.format_datetime(register.opened_at)} "
        f"por {register.operator}. Caixa #{register.id}.",
        title="Caixa aberto",
    )
    components.metrics(
        [
            ("Fundo inicial", format_brl(summary.register.opening_cents), "Dinheiro na abertura"),
            (
                "Vendas em dinheiro",
                format_brl(summary.cash_sales_cents),
                f"{summary.sales_count} venda(s) no turno · {format_brl(summary.sales_total_cents)}",
            ),
            (
                "Recebido em trocas",
                format_brl(summary.cash_in_cents),
                "Diferenças pagas em dinheiro",
            ),
            (
                "Devolvido a clientes",
                format_brl(summary.cash_out_cents),
                "Cancelamentos, devoluções e trocas",
            ),
            (
                "Esperado na gaveta",
                format_brl(summary.expected_cents),
                "Fundo + vendas + trocas − devoluções (em dinheiro)",
            ),
        ],
        per_row=3,
    )
    if summary.by_method:
        components.section_title("Vendas do turno por forma de pagamento")
        components.lines_table(
            ["Forma de pagamento", "Vendas", "Total"],
            [
                (formatting.payment_label(method), str(count), format_brl(total))
                for method, (count, total) in sorted(summary.by_method.items())
            ],
            numeric=(1, 2),
        )


# ---------------------------------------------------------------------------- fechamento
def _close_panel(user: User, register: Register, summary: RegisterSummary) -> None:
    components.section_title("Fechar caixa")
    st.caption("Conte o dinheiro da gaveta, informe o valor e confirme o fechamento.")
    counted, _ = components.money_field(
        "Valor contado na gaveta (R$)",
        key="close_register_counted",
        help="Pressione Enter para conferir a diferença antes de confirmar.",
    )
    if counted is not None:
        difference = cash_register.calculate_difference(summary.expected_cents, counted)
        tone, text = formatting.difference_summary(difference)
        components.alert(
            tone,
            f"Esperado {format_brl(summary.expected_cents)} · contado {format_brl(counted)}. {text}",
            title="Conferência",
        )
    confirm = compat.stretch(
        st.button,
        "Confirmar fechamento",
        key="close_register_confirm",
        type="primary",
        disabled=counted is None,
    )
    if counted is None:
        st.caption("Informe o valor contado para liberar o fechamento.")
    if not confirm or counted is None:
        return

    def close_it() -> Register:
        with state.db() as conn:
            return cash_register.close_register(conn, user, counted, register_id=register.id)

    def message(closed: Register) -> str:
        _, text = formatting.difference_summary(closed.difference_cents or 0, registered=True)
        return (
            f"Caixa #{closed.id} fechado. Esperado {format_brl(closed.expected_cents)}, "
            f"contado {format_brl(closed.counted_cents)}. {text}"
        )

    ok, closed = components.run_action(close_it)
    if ok and closed is not None:
        tone, _ = formatting.difference_summary(closed.difference_cents or 0, registered=True)
        state.flash(tone, message(closed))
        compat.rerun()
