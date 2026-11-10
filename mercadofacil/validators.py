"""Validação e normalização de dados de entrada (CPF, código de barras, textos)."""

from __future__ import annotations

import re
import unicodedata

from .errors import ValidationError


def only_digits(value: object) -> str:
    return re.sub(r"\D", "", str(value or ""))


def fold(text: object) -> str:
    """Minúsculas e sem acentos, para buscas tolerantes ('acucar' acha 'Açúcar')."""
    normalized = unicodedata.normalize("NFKD", str(text or ""))
    stripped = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return stripped.casefold()


# --------------------------------------------------------------------------- CPF
def is_valid_cpf(value: object) -> bool:
    cpf = only_digits(value)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for length in (9, 10):
        total = sum(int(d) * w for d, w in zip(cpf[:length], range(length + 1, 1, -1), strict=True))
        if (total * 10) % 11 % 10 != int(cpf[length]):
            return False
    return True


def normalize_cpf(value: object) -> str:
    """Retorna só os 11 dígitos ou levanta ValidationError."""
    cpf = only_digits(value)
    if not is_valid_cpf(cpf):
        raise ValidationError("CPF inválido. Confira os 11 dígitos informados.")
    return cpf


def format_cpf(cpf: str) -> str:
    digits = only_digits(cpf)
    if len(digits) != 11:
        return str(cpf)
    return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"


def mask_cpf(cpf: str | None) -> str:
    """Mascara o CPF em comprovantes: ***.456.789-**."""
    digits = only_digits(cpf)
    if len(digits) != 11:
        return "—"
    return f"***.{digits[3:6]}.{digits[6:9]}-**"


# ----------------------------------------------------------------- Código de barras
_BARCODE_PATTERN = re.compile(r"^[0-9A-Za-z\-]{4,20}$")


def normalize_barcode(value: object) -> str:
    code = str(value or "").strip()
    if not code:
        raise ValidationError("Informe o código de barras.")
    if not _BARCODE_PATTERN.match(code):
        raise ValidationError(
            "Código de barras inválido: use de 4 a 20 caracteres entre letras, números e hífen."
        )
    return code.upper()


# ----------------------------------------------------------------------- Textos
def require_text(value: object, label: str, *, max_length: int = 120) -> str:
    """`label` é um sintagma como 'o nome do produto'."""
    text = " ".join(str(value or "").split())
    if not text:
        raise ValidationError(f"Informe {label}.")
    if len(text) > max_length:
        raise ValidationError(f"Use no máximo {max_length} caracteres em {label}.")
    return text


def optional_text(value: object, label: str, *, max_length: int = 120) -> str:
    text = " ".join(str(value or "").split())
    if len(text) > max_length:
        raise ValidationError(f"Use no máximo {max_length} caracteres em {label}.")
    return text


# ----------------------------------------------------------------------- Inteiros
def _to_int(value: object, label: str) -> int:
    if isinstance(value, bool):
        raise ValidationError(f"{label} deve ser um número inteiro.")
    if isinstance(value, float):
        if not value.is_integer():
            raise ValidationError(f"{label} deve ser um número inteiro.")
        return int(value)
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        raise ValidationError(f"{label} deve ser um número inteiro.") from None


def require_positive_int(value: object, label: str) -> int:
    """`label` começa com maiúscula: 'A quantidade'."""
    number = _to_int(value, label)
    if number <= 0:
        raise ValidationError(f"{label} deve ser maior que zero.")
    return number


def require_non_negative_int(value: object, label: str) -> int:
    number = _to_int(value, label)
    if number < 0:
        raise ValidationError(f"{label} não pode ser negativo.")
    return number
