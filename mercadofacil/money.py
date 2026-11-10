"""Valores monetários em centavos inteiros (decisão de implementação 6.1)."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from .errors import ValidationError


def format_brl(cents: int | None) -> str:
    """12345 -> 'R$ 123,45'; -350 -> '-R$ 3,50'."""
    value = int(cents or 0)
    sign = "-" if value < 0 else ""
    reais, centavos = divmod(abs(value), 100)
    return f"{sign}R$ {reais:,}".replace(",", ".") + f",{centavos:02d}"


def format_input(cents: int) -> str:
    """12345 -> '123,45' (para preencher campos de texto)."""
    reais, centavos = divmod(abs(int(cents)), 100)
    return f"{'-' if cents < 0 else ''}{reais},{centavos:02d}"


def parse_money(text: str | int | float | Decimal | None, *, allow_zero: bool = True) -> int:
    """Converte texto em centavos.

    Aceita '12,50', '12.50', 'R$ 1.234,56', '1234' e '0'. Rejeita negativos,
    texto não numérico e mais de duas casas decimais.
    """
    if text is None:
        raise ValidationError("Informe um valor em reais (ex.: 12,50).")
    raw = str(text).strip().replace("R$", "").replace(" ", "")
    if not raw:
        raise ValidationError("Informe um valor em reais (ex.: 12,50).")
    if raw.startswith("-"):
        raise ValidationError("O valor não pode ser negativo.")

    if "," in raw:
        normalized = raw.replace(".", "").replace(",", ".")
    elif "." in raw:
        parts = raw.split(".")
        if len(parts) == 2 and len(parts[1]) <= 2:
            normalized = raw  # ponto como separador decimal
        else:
            normalized = raw.replace(".", "")  # ponto como milhar
    else:
        normalized = raw

    # Somente dígitos e no máximo um separador decimal (rejeita '1e2', 'NaN', '1..5').
    if not re.fullmatch(r"\d*\.?\d+|\d+\.", normalized):
        raise ValidationError(f"Valor inválido: “{text}”. Use o formato 12,50.")
    try:
        amount = Decimal(normalized)
    except InvalidOperation:
        raise ValidationError(f"Valor inválido: “{text}”. Use o formato 12,50.") from None
    if amount != amount.quantize(Decimal("0.01")):
        raise ValidationError("Use no máximo duas casas decimais (centavos).")

    cents = int(amount * 100)
    if cents == 0 and not allow_zero:
        raise ValidationError("O valor deve ser maior que zero.")
    return cents
