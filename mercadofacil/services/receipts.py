"""Comprovante de venda em texto (sem valor fiscal — emissão de NF fora do escopo, RNF11)."""

from __future__ import annotations

from .. import clock, config
from ..models import PAYMENT_METHOD_LABELS, SaleDetail
from ..money import format_brl
from ..validators import mask_cpf

WIDTH = 44


def _line(left: str, right: str) -> str:
    gap = max(1, WIDTH - len(left) - len(right))
    return f"{left}{' ' * gap}{right}"


def build_receipt(detail: SaleDetail) -> str:
    sale = detail.sale
    rule = "-" * WIDTH
    lines = [
        config.APP_NAME.upper().center(WIDTH),
        "Comprovante de venda — sem valor fiscal".center(WIDTH),
        rule,
        f"Venda: {sale.id}",
        f"Data: {clock.format_datetime(sale.created_at)}",
        f"Operador: {sale.operator}",
    ]
    if detail.customer is not None:
        lines.append(f"Cliente: {detail.customer.name} (CPF {mask_cpf(detail.customer.cpf)})")
    lines.append(rule)
    for item in detail.items:
        name = item.product_name or f"Produto {item.product_id}"
        lines.append(name[:WIDTH])
        lines.append(
            _line(
                f"  {item.quantity} x {format_brl(item.unit_price_cents)}",
                format_brl(item.subtotal_cents),
            )
        )
        if item.cancelled_qty or item.returned_qty:
            lines.append(
                f"  (cancelado: {item.cancelled_qty} · devolvido/trocado: {item.returned_qty})"
            )
    lines.append(rule)
    lines.append(_line("Subtotal", format_brl(sale.subtotal_cents)))
    if sale.cashback_used_cents:
        lines.append(_line("Cashback utilizado", f"-{format_brl(sale.cashback_used_cents)}"))
    lines.append(_line("TOTAL", format_brl(sale.total_cents)))
    lines.append(_line("Forma de pagamento", PAYMENT_METHOD_LABELS.get(sale.payment_method, "")))
    if sale.payment_method == "dinheiro" and detail.payment is not None:
        lines.append(_line("Valor recebido", format_brl(detail.payment.received_cents)))
        lines.append(_line("TROCO", format_brl(sale.change_cents)))
    if detail.customer is not None:
        lines.append(rule)
        lines.append(_line("Cashback acumulado", format_brl(sale.cashback_earned_cents)))
        lines.append(_line("Saldo de cashback", format_brl(detail.customer.cashback_cents)))
    lines.append(rule)
    lines.append(f"Status: {sale.status_label}")
    lines.append("Obrigado pela preferência!".center(WIDTH))
    return "\n".join(lines) + "\n"
