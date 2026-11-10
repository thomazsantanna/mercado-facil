"""Abertura e fechamento de caixa (RF01, RF02, RB01, RB11)."""

from __future__ import annotations

import sqlite3

from .. import clock
from ..database import transaction
from ..errors import BusinessRuleError, NotFoundError, PermissionDeniedError, ValidationError
from ..models import Register, RegisterSummary, User
from ..repositories import registers as registers_repo
from ..validators import require_non_negative_int
from . import permissions


def get_open_register(conn: sqlite3.Connection, username: str) -> Register | None:
    return registers_repo.get_open_register(conn, username)


def require_open_register(
    conn: sqlite3.Connection, username: str, message: str | None = None
) -> Register:
    """RB01: uma venda somente pode ser concluída com caixa aberto."""
    register = registers_repo.get_open_register(conn, username)
    if register is None:
        raise BusinessRuleError(
            message or "Caixa fechado. Abra o caixa em “Abertura e fechamento” antes de vender.",
            rule="RB01",
        )
    return register


def calculate_difference(expected_cents: int, counted_cents: int) -> int:
    """calcularDiferenca(): contado − esperado (negativo = falta, positivo = sobra)."""
    return counted_cents - expected_cents


def summarize(conn: sqlite3.Connection, register_id: int) -> RegisterSummary:
    register = registers_repo.get_register(conn, register_id)
    if register is None:
        raise NotFoundError("Caixa não encontrado.")
    totals = registers_repo.cash_totals(conn, register_id)
    by_method = registers_repo.sales_by_method(conn, register_id)
    expected = (
        register.opening_cents + totals["cash_sales"] + totals["cash_in"] - totals["cash_out"]
    )
    return RegisterSummary(
        register=register,
        cash_sales_cents=totals["cash_sales"],
        cash_in_cents=totals["cash_in"],
        cash_out_cents=totals["cash_out"],
        expected_cents=expected,
        sales_count=sum(count for count, _ in by_method.values()),
        sales_total_cents=sum(total for _, total in by_method.values()),
        by_method=by_method,
    )


def open_register(conn: sqlite3.Connection, actor: User, opening_cents: int) -> Register:
    """RF01: abre o caixa com fundo inicial."""
    permissions.ensure_permission(actor, permissions.REGISTER_MANAGE)
    opening = require_non_negative_int(opening_cents, "O fundo inicial")
    with transaction(conn):
        current = registers_repo.get_open_register(conn, actor.username)
        if current is not None:
            raise BusinessRuleError(
                f"Você já possui um caixa aberto desde {clock.format_datetime(current.opened_at)}. "
                "Feche-o antes de abrir outro."
            )
        register_id = registers_repo.insert_register(
            conn, operator=actor.username, opening_cents=opening, opened_at=clock.now_iso()
        )
        register = registers_repo.get_register(conn, register_id)
    assert register is not None
    return register


def close_register(
    conn: sqlite3.Connection,
    actor: User,
    counted_cents: int,
    *,
    register_id: int | None = None,
) -> Register:
    """RF02/RB11: fecha o caixa registrando esperado, contado e diferença."""
    permissions.ensure_permission(actor, permissions.REGISTER_MANAGE)
    if counted_cents is None:
        raise ValidationError("Informe o valor contado na gaveta.")
    counted = require_non_negative_int(counted_cents, "O valor contado")
    with transaction(conn):
        if register_id is None:
            register = registers_repo.get_open_register(conn, actor.username)
            if register is None:
                raise BusinessRuleError("Não há caixa aberto para fechar.")
        else:
            register = registers_repo.get_register(conn, register_id)
            if register is None:
                raise NotFoundError("Caixa não encontrado.")
            if not register.is_open:
                raise BusinessRuleError("Este caixa já está fechado.")
            if register.operator != actor.username and not permissions.can(
                actor, permissions.REGISTER_VIEW_ALL
            ):
                raise PermissionDeniedError(
                    "Somente o operador do caixa ou um gestor pode fechá-lo."
                )
        summary = summarize(conn, register.id)
        difference = calculate_difference(summary.expected_cents, counted)
        registers_repo.close_register(
            conn,
            register.id,
            expected_cents=summary.expected_cents,
            counted_cents=counted,
            difference_cents=difference,
            closed_at=clock.now_iso(),
        )
        closed = registers_repo.get_register(conn, register.id)
    assert closed is not None
    return closed


def list_registers(conn: sqlite3.Connection, actor: User, *, limit: int = 200) -> list[Register]:
    """Gestor vê todos os caixas; os demais, apenas os próprios."""
    permissions.ensure_permission(actor, permissions.REGISTER_MANAGE)
    if permissions.can(actor, permissions.REGISTER_VIEW_ALL):
        return registers_repo.list_registers(conn, limit=limit)
    return registers_repo.list_registers(conn, operator=actor.username, limit=limit)
