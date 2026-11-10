"""Apresentação dos dados: linhas de tabela, rótulos e mensagens (sem Streamlit).

Tudo aqui é função pura e, por isso, testável sem abrir a interface.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date
from typing import Any

from .. import clock
from ..models import (
    PAYMENT_METHOD_LABELS,
    Product,
    Register,
    Sale,
    SaleItem,
    StockMovement,
)
from ..models import PostSaleOperation as Operation
from ..money import format_brl
from ..validators import format_cpf

Row = dict[str, Any]

# ----------------------------------------------------------------------------- períodos
PERIOD_TODAY = "Hoje"
PERIOD_7_DAYS = "Últimos 7 dias"
PERIOD_30_DAYS = "Últimos 30 dias"
PERIODS = (PERIOD_TODAY, PERIOD_7_DAYS, PERIOD_30_DAYS)
_PERIOD_DAYS = {PERIOD_TODAY: 0, PERIOD_7_DAYS: 6, PERIOD_30_DAYS: 29}


def period_range(label: str) -> tuple[str, str]:
    """Intervalo (início, fim) em 'AAAA-MM-DD', inclusivo, para o rótulo escolhido."""
    days = _PERIOD_DAYS.get(label, 0)
    return clock.days_ago_iso(days), clock.today_iso()


def date_range_iso(value: Any) -> tuple[str | None, str | None]:
    """Normaliza o retorno de `st.date_input` (data única, tupla de 0, 1 ou 2 datas)."""
    if value is None:
        return None, None
    if isinstance(value, date):
        iso = value.strftime(clock.DATE_FORMAT)
        return iso, iso
    items: Sequence[Any] = list(value)
    if not items:
        return None, None
    start = items[0].strftime(clock.DATE_FORMAT)
    end = items[-1].strftime(clock.DATE_FORMAT)
    return start, end


# ------------------------------------------------------------------------------ valores
def signed_money(cents: int) -> str:
    """'+R$ 5,00', '-R$ 5,00' ou 'R$ 0,00'."""
    if cents > 0:
        return f"+{format_brl(cents)}"
    return format_brl(cents)


def payment_label(method: str) -> str:
    return PAYMENT_METHOD_LABELS.get(method, method or "—")


def customer_label(cpf: str | None, name: str | None) -> str:
    if not cpf:
        return "—"
    return f"{name or 'Cliente'} ({format_cpf(cpf)})"


# ----------------------------------------------------------------------------- produtos
def stock_status_label(product: Product) -> str:
    if not product.is_active:
        return "Inativo"
    return {
        "sem_estoque": "⛔ Sem estoque",
        "repor": "⚠ Repor",
        "ok": "✔ Em estoque",
    }[product.stock_status]


def product_label(product: Product) -> str:
    return (
        f"{product.name} · {product.barcode} · {format_brl(product.price_cents)}"
        f" · estoque {product.stock} {product.unit}"
    )


def product_rows(products: Iterable[Product]) -> list[Row]:
    return [
        {
            "Código": p.barcode,
            "Produto": p.name,
            "Categoria": p.category,
            "Localização": p.location or "—",
            "Un.": p.unit,
            "Preço": format_brl(p.price_cents),
            "Custo": format_brl(p.cost_cents),
            "Estoque": p.stock,
            "Mínimo": p.min_stock,
            "Situação": stock_status_label(p),
        }
        for p in products
    ]


def restock_rows(products: Iterable[Product]) -> list[Row]:
    return [
        {
            "Produto": p.name,
            "Localização": p.location or "—",
            "Estoque": p.stock,
            "Mínimo": p.min_stock,
            "Situação": stock_status_label(p),
        }
        for p in products
    ]


# -------------------------------------------------------------------------- movimentações
def movement_type_label(movement_type: str) -> str:
    return "▲ Entrada" if movement_type == "entrada" else "▼ Saída"


def movement_rows(movements: Iterable[StockMovement]) -> list[Row]:
    return [
        {
            "Data/hora": clock.format_datetime(m.created_at),
            "Produto": m.product_name,
            "Código": m.product_barcode,
            "Tipo": movement_type_label(m.type),
            "Quantidade": m.quantity,
            "Saldo após": m.balance_after,
            "Motivo": m.reason,
            "Referência": m.reference or "—",
            "Operador": m.operator,
        }
        for m in movements
    ]


# ------------------------------------------------------------------------------- vendas
def sale_label(sale: Sale) -> str:
    who = f" · {sale.customer_name}" if sale.customer_name else ""
    return (
        f"{sale.id} · {clock.format_datetime(sale.created_at)} · {format_brl(sale.total_cents)}"
        f" · {sale.status_label}{who}"
    )


def sale_rows(sales: Iterable[Sale]) -> list[Row]:
    return [
        {
            "Venda": s.id,
            "Data/hora": clock.format_datetime(s.created_at),
            "Cliente": customer_label(s.customer_cpf, s.customer_name),
            "Pagamento": s.payment_label,
            "Total": format_brl(s.total_cents),
            "Troco": format_brl(s.change_cents) if s.payment_method == "dinheiro" else "—",
            "Cashback ganho": format_brl(s.cashback_earned_cents),
            "Status": s.status_label,
            "Operador": s.operator,
        }
        for s in sales
    ]


def sale_item_rows(items: Iterable[SaleItem]) -> list[Row]:
    return [
        {
            "Produto": i.product_name,
            "Código": i.product_barcode,
            "Preço un.": format_brl(i.unit_price_cents),
            "Vendida": i.quantity,
            "Cancelada": i.cancelled_qty,
            "Devolvida/trocada": i.returned_qty,
            "Ativa": i.active_qty,
            "Subtotal ativo": format_brl(i.active_subtotal_cents),
        }
        for i in items
    ]


def item_label(item: SaleItem) -> str:
    return (
        f"{item.product_name} — {item.active_qty} disponível(is) de {item.quantity}"
        f" · {format_brl(item.unit_price_cents)} cada"
    )


def operation_rows(operations: Iterable[Operation]) -> list[Row]:
    rows: list[Row] = []
    for op in operations:
        product = op.product_name or "—"
        if op.replacement_name:
            product = f"{product} → {op.replacement_name}"
        rows.append(
            {
                "Data/hora": clock.format_datetime(op.created_at),
                "Venda": op.sale_id,
                "Ocorrência": op.type_label,
                "Produto": product,
                "Quantidade": op.quantity or "—",
                "Valor": operation_money_text(op),
                "Cashback": operation_cashback_text(op),
                "Motivo": op.notes or "—",
                "Operador": op.operator,
                "Autorizado por": op.authorized_by,
            }
        )
    return rows


def operation_money_text(op: Operation) -> str:
    """Quem pagou a quem: valor devolvido ao cliente ou recebido dele (troca)."""
    if op.amount_cents > 0:
        return f"Devolvido {format_brl(op.amount_cents)} ({payment_label(op.settlement_method)})"
    if op.amount_cents < 0:
        return f"Recebido {format_brl(-op.amount_cents)} ({payment_label(op.settlement_method)})"
    return "—"


def operation_cashback_text(op: Operation) -> str:
    parts = []
    if op.cashback_restored_cents:
        parts.append(f"devolvido {format_brl(op.cashback_restored_cents)}")
    if op.cashback_reversed_cents:
        parts.append(f"estornado {format_brl(op.cashback_reversed_cents)}")
    return "; ".join(parts) or "—"


def describe_operation(op: Operation) -> str:
    """Mensagem de confirmação após registrar uma ocorrência de pós-venda."""
    headline = {
        "cancelamento_venda": f"Venda {op.sale_id} cancelada; itens ativos devolvidos ao estoque.",
        "cancelamento_item": f"Item cancelado na venda {op.sale_id}.",
        "devolucao": f"Devolução registrada na venda {op.sale_id}.",
        "troca": f"Troca registrada na venda {op.sale_id}; os dois estoques foram movimentados.",
    }.get(op.type, f"{op.type_label} registrada na venda {op.sale_id}.")
    details = []
    if (money := operation_money_text(op)) != "—":
        details.append(money)
    if (cashback := operation_cashback_text(op)) != "—":
        details.append(f"Cashback {cashback}")
    return headline + (" " + " · ".join(details) + "." if details else "")


# -------------------------------------------------------------------------------- caixa
def register_status_text(register: Register | None) -> str:
    return "Caixa aberto" if register is not None and register.is_open else "Caixa fechado"


def difference_summary(difference_cents: int, *, registered: bool = False) -> tuple[str, str]:
    """(tom, texto) para a diferença do fechamento (RB11, CT12)."""
    suffix = "registrada" if registered else "será registrada"
    if difference_cents < 0:
        return "danger", f"Falta de {format_brl(-difference_cents)} {suffix}."
    if difference_cents > 0:
        return "warn", f"Sobra de {format_brl(difference_cents)} {suffix}."
    return "ok", "Caixa conferido: sem diferença."


def register_difference_text(register: Register) -> str:
    if register.difference_cents is None:
        return "—"
    if register.difference_cents < 0:
        return f"Falta {format_brl(-register.difference_cents)}"
    if register.difference_cents > 0:
        return f"Sobra {format_brl(register.difference_cents)}"
    return "Sem diferença"


def register_rows(registers: Iterable[Register]) -> list[Row]:
    return [
        {
            "Caixa": f"#{r.id}",
            "Operador": r.operator,
            "Situação": "Aberto" if r.is_open else "Fechado",
            "Abertura": clock.format_datetime(r.opened_at),
            "Fechamento": clock.format_datetime(r.closed_at),
            "Fundo inicial": format_brl(r.opening_cents),
            "Esperado": format_brl(r.expected_cents) if r.expected_cents is not None else "—",
            "Contado": format_brl(r.counted_cents) if r.counted_cents is not None else "—",
            "Diferença": register_difference_text(r),
        }
        for r in registers
    ]


# ---------------------------------------------------------------------------------- CSV
def rows_to_csv(rows: Sequence[Row]) -> bytes:
    """CSV para planilhas brasileiras: separador ';' e UTF-8 com BOM (abre direto no Excel)."""
    import csv
    import io

    if not rows:
        return b""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), delimiter=";", lineterminator="\r\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


def file_size(size: int) -> str:
    """Tamanho legível: '12,3 KB'."""
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB".replace(".", ",")
    return f"{size / 1024 / 1024:.1f} MB".replace(".", ",")
