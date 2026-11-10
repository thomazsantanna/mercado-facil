"""Pagamentos e troco (RF05, RF06, RB04, RB05).

A aprovação de Pix, débito e crédito é simulada no protótipo (seção 9.2).
"""

from __future__ import annotations

from ..errors import BusinessRuleError, ValidationError
from ..models import PAYMENT_METHODS
from ..money import format_brl


def validate_method(method: str) -> str:
    if method not in PAYMENT_METHODS:
        raise ValidationError("Forma de pagamento inválida. Use dinheiro, Pix, débito ou crédito.")
    return method


def calculate_change(total_cents: int, received_cents: int, method: str = "dinheiro") -> int:
    """Troco da venda.

    RB05: troco só existe para dinheiro. RB04: o valor recebido em dinheiro não
    pode ser menor que o total.
    """
    if method != "dinheiro":
        return 0
    if received_cents < total_cents:
        missing = total_cents - received_cents
        raise BusinessRuleError(
            f"Pagamento bloqueado: o valor recebido ({format_brl(received_cents)}) é menor que "
            f"o total ({format_brl(total_cents)}). Faltam {format_brl(missing)}.",
            rule="RB04",
        )
    return received_cents - total_cents


def authorize_electronic_payment(method: str, total_cents: int, *, approved: bool = True) -> None:
    """Simula a resposta do sistema de pagamento (Pix, débito, crédito)."""
    validate_method(method)
    if method == "dinheiro":
        return
    if not approved:
        raise BusinessRuleError(
            f"Pagamento de {format_brl(total_cents)} via {PAYMENT_METHODS[method]} não aprovado. "
            "A venda não foi registrada; tente novamente ou escolha outra forma de pagamento."
        )
