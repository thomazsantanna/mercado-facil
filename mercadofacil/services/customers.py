"""Clientes identificados por CPF e cashback (RF07, RB06, RB07)."""

from __future__ import annotations

import sqlite3

from .. import clock, config
from ..database import transaction
from ..errors import BusinessRuleError, NotFoundError
from ..models import Customer, User
from ..money import format_brl
from ..repositories import customers as customers_repo
from ..validators import normalize_cpf, require_text
from . import permissions


def find_customer(conn: sqlite3.Connection, cpf_text: str) -> Customer | None:
    """Busca pelo CPF (valida os dígitos). Retorna None se não cadastrado."""
    return customers_repo.get_customer(conn, normalize_cpf(cpf_text))


def get_customer(conn: sqlite3.Connection, cpf_text: str) -> Customer:
    customer = find_customer(conn, cpf_text)
    if customer is None:
        raise NotFoundError("Cliente não cadastrado. Cadastre o CPF para usar o cashback.")
    return customer


def register_customer(conn: sqlite3.Connection, actor: User, cpf_text: str, name: str) -> Customer:
    """Cadastro mínimo: apenas CPF e nome (coleta só dos dados necessários — 2.2)."""
    permissions.ensure_permission(actor, permissions.SALE_CREATE)
    cpf = normalize_cpf(cpf_text)
    customer_name = require_text(name, "o nome do cliente", max_length=80)
    with transaction(conn):
        if customers_repo.get_customer(conn, cpf) is not None:
            raise BusinessRuleError("Este CPF já está cadastrado.")
        customers_repo.insert_customer(
            conn, cpf=cpf, name=customer_name, created_at=clock.now_iso()
        )
        customer = customers_repo.get_customer(conn, cpf)
    assert customer is not None
    return customer


def calculate_cashback_earned(net_total_cents: int) -> int:
    """RB07: 1% do total líquido, truncado para o centavo inferior."""
    return max(0, net_total_cents) * config.CASHBACK_RATE_PERCENT // 100


def max_usable_cashback(customer: Customer | None, subtotal_cents: int) -> int:
    """RB06: o cashback utilizado não pode superar o saldo nem o valor da compra."""
    if customer is None:
        return 0
    return max(0, min(customer.cashback_cents, subtotal_cents))


def validate_cashback_use(
    customer: Customer | None, requested_cents: int, subtotal_cents: int
) -> None:
    """Levanta BusinessRuleError (RB06) se o uso solicitado for inválido."""
    if requested_cents <= 0:
        return
    if customer is None:
        raise BusinessRuleError(
            "Uso bloqueado: identifique o cliente pelo CPF para utilizar cashback.", rule="RB06"
        )
    if requested_cents > customer.cashback_cents:
        raise BusinessRuleError(
            f"Uso bloqueado: o cashback solicitado ({format_brl(requested_cents)}) é maior que o "
            f"saldo do cliente ({format_brl(customer.cashback_cents)}).",
            rule="RB06",
        )
    if requested_cents > subtotal_cents:
        raise BusinessRuleError(
            f"Uso bloqueado: o cashback solicitado ({format_brl(requested_cents)}) é maior que o "
            f"valor da compra ({format_brl(subtotal_cents)}).",
            rule="RB06",
        )
