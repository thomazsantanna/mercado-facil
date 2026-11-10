"""Abertura e fechamento de caixa (RF01, RF02, RB01, RB11)."""

from __future__ import annotations

import sqlite3

import pytest

from mercadofacil.errors import BusinessRuleError, PermissionDeniedError, ValidationError
from mercadofacil.models import User
from mercadofacil.services import auth, cash_register
from tests.conftest import World


def _second_operator(world: World) -> User:
    return auth.create_user(
        world.conn,
        username="operador2",
        name="Segundo Operador",
        role="operador",
        password="senha-123",
    )


def test_abrir_caixa_com_fundo_inicial_rf01(world: World) -> None:
    register = world.open_cash(opening=15_000)
    assert register.is_open
    assert register.status == "aberto"
    assert register.opening_cents == 15_000
    assert register.operator == "operador"
    assert cash_register.get_open_register(world.conn, "operador") == register


@pytest.mark.parametrize("opening", [-1, "abc", None, 1.5])
def test_fundo_inicial_invalido(world: World, opening: object) -> None:
    with pytest.raises(ValidationError):
        cash_register.open_register(world.conn, world.operator, opening)  # type: ignore[arg-type]


def test_fundo_inicial_zero_e_permitido(world: World) -> None:
    assert world.open_cash(opening=0).opening_cents == 0


def test_um_caixa_aberto_por_operador(world: World) -> None:
    world.open_cash()
    with pytest.raises(BusinessRuleError, match="já possui um caixa aberto"):
        world.open_cash()
    assert world.open_cash(world.manager).operator == "gestor"  # cada operador tem o seu


def test_banco_tambem_garante_um_caixa_aberto_por_operador(world: World) -> None:
    world.open_cash()
    with pytest.raises(sqlite3.IntegrityError):
        world.conn.execute(
            "INSERT INTO registers (operator, status, opening_cents, opened_at) "
            "VALUES ('operador', 'aberto', 0, '2026-01-01 08:00:00')"
        )


def test_estoquista_nao_abre_caixa(world: World) -> None:
    with pytest.raises(PermissionDeniedError):
        cash_register.open_register(world.conn, world.stocker, 1000)


def test_fechar_sem_diferenca_rb11(world: World) -> None:
    world.open_cash(opening=10_000)
    product = world.product(price=2500)
    world.sell([(product, 2)])  # R$ 50,00 em dinheiro
    closed = cash_register.close_register(world.conn, world.operator, 15_000)
    assert closed.status == "fechado"
    assert (closed.expected_cents, closed.counted_cents, closed.difference_cents) == (
        15_000,
        15_000,
        0,
    )
    assert closed.closed_at is not None
    assert cash_register.get_open_register(world.conn, "operador") is None


def test_falta_e_sobra_ficam_registradas_com_sinal(world: World) -> None:
    world.open_cash(opening=10_000)
    short = cash_register.close_register(world.conn, world.operator, 9_000)
    assert (short.expected_cents, short.counted_cents, short.difference_cents) == (
        10_000,
        9_000,
        -1_000,
    )

    world.open_cash(opening=10_000)
    over = cash_register.close_register(world.conn, world.operator, 10_350)
    assert over.difference_cents == 350


def test_calcular_diferenca() -> None:
    assert cash_register.calculate_difference(10_000, 9_500) == -500
    assert cash_register.calculate_difference(10_000, 10_500) == 500
    assert cash_register.calculate_difference(10_000, 10_000) == 0


def test_esperado_considera_apenas_dinheiro(world: World) -> None:
    register = world.open_cash(opening=10_000)
    product = world.product(price=1000, stock=50)
    world.sell([(product, 3)])  # dinheiro R$ 30,00
    world.sell([(product, 2)], method="pix")
    world.sell([(product, 1)], method="debito")
    world.sell([(product, 1)], method="credito")
    summary = cash_register.summarize(world.conn, register.id)
    assert summary.cash_sales_cents == 3_000
    assert summary.expected_cents == 13_000  # fundo + dinheiro; Pix e cartões não entram na gaveta
    assert summary.sales_count == 4
    assert summary.sales_total_cents == 7_000
    assert summary.by_method == {
        "dinheiro": (1, 3_000),
        "pix": (1, 2_000),
        "debito": (1, 1_000),
        "credito": (1, 1_000),
    }


def test_troco_nao_infla_o_esperado(world: World) -> None:
    register = world.open_cash(opening=0)
    product = world.product(price=3_250)
    world.sell([(product, 1)], received=5_000)  # recebeu 50,00, devolveu 17,50
    assert cash_register.summarize(world.conn, register.id).expected_cents == 3_250


def test_nao_fecha_duas_vezes_nem_sem_caixa(world: World) -> None:
    with pytest.raises(BusinessRuleError, match="Não há caixa aberto"):
        cash_register.close_register(world.conn, world.operator, 0)
    register = world.open_cash()
    cash_register.close_register(world.conn, world.operator, 10_000)
    with pytest.raises(BusinessRuleError, match="já está fechado"):
        cash_register.close_register(world.conn, world.operator, 10_000, register_id=register.id)


@pytest.mark.parametrize("counted", [-1, None, "x"])
def test_valor_contado_invalido(world: World, counted: object) -> None:
    world.open_cash()
    with pytest.raises(ValidationError):
        cash_register.close_register(world.conn, world.operator, counted)  # type: ignore[arg-type]
    assert cash_register.get_open_register(world.conn, "operador") is not None  # continua aberto


def test_gestor_fecha_caixa_de_outro_operador_mas_operador_nao(world: World) -> None:
    register = world.open_cash()
    other = _second_operator(world)
    with pytest.raises(PermissionDeniedError, match="Somente o operador do caixa ou um gestor"):
        cash_register.close_register(world.conn, other, 0, register_id=register.id)
    closed = cash_register.close_register(
        world.conn, world.manager, 10_000, register_id=register.id
    )
    assert closed.status == "fechado"


def test_depois_de_fechar_pode_abrir_outro(world: World) -> None:
    world.open_cash()
    cash_register.close_register(world.conn, world.operator, 10_000)
    assert world.open_cash(opening=5_000).opening_cents == 5_000
    assert world.count("registers") == 2


def test_historico_por_perfil(world: World) -> None:
    other = _second_operator(world)
    world.open_cash()
    world.open_cash(other, opening=500)
    own = cash_register.list_registers(world.conn, world.operator)
    assert [r.operator for r in own] == ["operador"]
    everything = cash_register.list_registers(world.conn, world.manager)
    assert {r.operator for r in everything} == {"operador", "operador2"}
    with pytest.raises(PermissionDeniedError):
        cash_register.list_registers(world.conn, world.stocker)


def test_exige_caixa_aberto(world: World) -> None:
    with pytest.raises(BusinessRuleError, match="Caixa fechado") as caught:
        cash_register.require_open_register(world.conn, "operador")
    assert caught.value.rule == "RB01"
    world.open_cash()
    assert cash_register.require_open_register(world.conn, "operador").is_open
