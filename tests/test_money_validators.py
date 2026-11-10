"""Valores em centavos (6.1) e validações de entrada."""

from __future__ import annotations

import pytest

from mercadofacil import validators as v
from mercadofacil.errors import ValidationError
from mercadofacil.money import format_brl, format_input, parse_money


@pytest.mark.parametrize(
    ("cents", "text"),
    [
        (0, "R$ 0,00"),
        (5, "R$ 0,05"),
        (1750, "R$ 17,50"),
        (12345, "R$ 123,45"),
        (1234567, "R$ 12.345,67"),
        (-350, "-R$ 3,50"),
        (None, "R$ 0,00"),
    ],
)
def test_format_brl(cents: int | None, text: str) -> None:
    assert format_brl(cents) == text


def test_format_input_preenche_campos() -> None:
    assert format_input(12345) == "123,45"
    assert format_input(5) == "0,05"


@pytest.mark.parametrize(
    ("text", "cents"),
    [
        ("12,50", 1250),
        ("12.50", 1250),
        ("R$ 1.234,56", 123456),
        ("1234", 123400),
        ("0", 0),
        ("0,5", 50),
        ("1.234", 123400),  # ponto como separador de milhar
        ("1.234.567", 123456700),
        ("  7 ", 700),
        (1250, 125000),  # inteiros são tratados como reais
    ],
)
def test_parse_money_aceita_formatos_brasileiros(text: str | int, cents: int) -> None:
    assert parse_money(text) == cents


@pytest.mark.parametrize(
    "text", [None, "", "   ", "-5", "abc", "1,234", "1e2", "NaN", "1,2,3", "R$"]
)
def test_parse_money_rejeita_valores_invalidos(text: str | None) -> None:
    with pytest.raises(ValidationError):
        parse_money(text)


def test_parse_money_zero_proibido_quando_pedido() -> None:
    assert parse_money("0", allow_zero=True) == 0
    with pytest.raises(ValidationError):
        parse_money("0,00", allow_zero=False)


def test_parse_money_nao_usa_ponto_flutuante() -> None:
    # 0,1 + 0,2 em float daria 0.30000000000000004.
    assert parse_money("0,10") + parse_money("0,20") == parse_money("0,30") == 30
    assert parse_money(1.1) == 110  # 1.1 em float binário é 1.100000000000000088…


@pytest.mark.parametrize("cpf", ["529.982.247-25", "52998224725", "111.444.777-35"])
def test_cpf_valido(cpf: str) -> None:
    assert v.is_valid_cpf(cpf)
    assert v.normalize_cpf(cpf) == v.only_digits(cpf)


@pytest.mark.parametrize("cpf", ["", None, "111.111.111-11", "123.456.789-00", "5299822472", "abc"])
def test_cpf_invalido(cpf: str | None) -> None:
    assert not v.is_valid_cpf(cpf)
    with pytest.raises(ValidationError, match="CPF inválido"):
        v.normalize_cpf(cpf)


def test_cpf_formatacao_e_mascara() -> None:
    assert v.format_cpf("52998224725") == "529.982.247-25"
    assert v.mask_cpf("52998224725") == "***.982.247-**"
    assert v.mask_cpf(None) == "—"
    assert v.mask_cpf("123") == "—"


def test_codigo_de_barras_normalizado() -> None:
    assert v.normalize_barcode("  abc-1234 ") == "ABC-1234"
    assert v.normalize_barcode("7891000000017") == "7891000000017"


@pytest.mark.parametrize("code", ["", "   ", None, "ab", "abc 123", "a" * 21, "123#456"])
def test_codigo_de_barras_invalido(code: str | None) -> None:
    with pytest.raises(ValidationError):
        v.normalize_barcode(code)


def test_textos() -> None:
    assert v.require_text("  Arroz   Tipo  1 ", "o nome") == "Arroz Tipo 1"
    with pytest.raises(ValidationError, match="Informe o nome"):
        v.require_text("   ", "o nome")
    with pytest.raises(ValidationError, match="no máximo 5"):
        v.require_text("123456", "o nome", max_length=5)
    assert v.optional_text(None, "a nota") == ""


def test_inteiros() -> None:
    assert v.require_positive_int("3", "A quantidade") == 3
    assert v.require_positive_int(2.0, "A quantidade") == 2
    assert v.require_non_negative_int(0, "O saldo") == 0
    for bad in ("0", -1, "1.5", 1.5, True, None, "x"):
        with pytest.raises(ValidationError):
            v.require_positive_int(bad, "A quantidade")
    with pytest.raises(ValidationError, match="não pode ser negativo"):
        v.require_non_negative_int(-1, "O saldo")


def test_busca_sem_acentos() -> None:
    assert v.fold("Açúcar Refinado") == "acucar refinado"
    assert v.fold(None) == ""
