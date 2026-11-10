"""Controle de estoque e movimentações (RF09, RF10, RF16, RB03, RNF04)."""

from __future__ import annotations

import sqlite3

import pytest

from mercadofacil import clock
from mercadofacil.errors import (
    BusinessRuleError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from mercadofacil.services import stock
from tests.conftest import World


def test_entrada_aumenta_o_saldo_e_registra_a_origem(world: World) -> None:
    product = world.product(stock=5)
    movement = stock.register_movement(
        world.conn,
        world.stocker,
        product_id=product.id,
        kind="entrada",
        quantity=20,
        reason="Reposição de mercadoria",
        reference="NF 1234",
    )
    assert world.stock_of(product) == 25
    assert (movement.type, movement.quantity, movement.balance_after) == ("entrada", 20, 25)
    assert movement.reason == "Reposição de mercadoria"
    assert movement.reference == "NF 1234"
    assert movement.operator == "estoquista"
    assert movement.created_at.startswith(clock.today_iso())  # data/hora (RNF04)


def test_saida_reduz_o_saldo(world: World) -> None:
    product = world.product(stock=10)
    movement = stock.register_movement(
        world.conn,
        world.stocker,
        product_id=product.id,
        kind="saida",
        quantity=4,
        reason="Consumo interno",
    )
    assert world.stock_of(product) == 6
    assert (movement.type, movement.balance_after) == ("saida", 6)


def test_perda_e_uma_saida_com_motivo_identificado(world: World) -> None:
    product = world.product(stock=10)
    movement = stock.register_movement(
        world.conn,
        world.stocker,
        product_id=product.id,
        kind="perda",
        quantity=3,
        reason="Produto vencido",
    )
    assert movement.type == "saida"
    assert movement.reason == "Perda: Produto vencido"
    assert world.stock_of(product) == 7


def test_saida_maior_que_o_saldo_e_bloqueada_rb03(world: World) -> None:
    product = world.product(stock=5)
    with pytest.raises(BusinessRuleError, match="não pode ficar negativo") as caught:
        stock.register_movement(
            world.conn,
            world.stocker,
            product_id=product.id,
            kind="saida",
            quantity=6,
            reason="Teste",
        )
    assert caught.value.rule == "RB03"
    assert world.stock_of(product) == 5
    assert len(stock.list_movements(world.conn, world.manager, product_id=product.id)) == 1


def test_saida_exatamente_igual_ao_saldo_zera_sem_ficar_negativo(world: World) -> None:
    product = world.product(stock=5)
    stock.register_movement(
        world.conn, world.stocker, product_id=product.id, kind="saida", quantity=5, reason="Teste"
    )
    assert world.stock_of(product) == 0


def test_banco_tambem_impede_saldo_negativo(world: World) -> None:
    product = world.product(stock=1)
    with pytest.raises(sqlite3.IntegrityError):
        world.conn.execute("UPDATE products SET stock = -1 WHERE id = ?", (product.id,))


@pytest.mark.parametrize("quantity", [0, -3, "abc", 1.5, None])
def test_quantidade_invalida(world: World, quantity: object) -> None:
    product = world.product()
    with pytest.raises(ValidationError):
        stock.register_movement(
            world.conn,
            world.stocker,
            product_id=product.id,
            kind="entrada",
            quantity=quantity,  # type: ignore[arg-type]
            reason="Teste",
        )


def test_motivo_e_obrigatorio_rf09(world: World) -> None:
    product = world.product()
    with pytest.raises(ValidationError, match="motivo"):
        stock.register_movement(
            world.conn,
            world.stocker,
            product_id=product.id,
            kind="entrada",
            quantity=1,
            reason="   ",
        )


def test_tipo_de_operacao_invalido(world: World) -> None:
    product = world.product()
    with pytest.raises(ValidationError, match="Tipo de operação"):
        stock.register_movement(
            world.conn, world.stocker, product_id=product.id, kind="roubo", quantity=1, reason="x"
        )


def test_produto_inexistente(world: World) -> None:
    with pytest.raises(NotFoundError):
        stock.register_movement(
            world.conn, world.stocker, product_id=999, kind="entrada", quantity=1, reason="x"
        )


def test_operador_de_caixa_nao_movimenta_estoque(world: World) -> None:
    product = world.product()
    with pytest.raises(PermissionDeniedError):
        stock.register_movement(
            world.conn,
            world.operator,
            product_id=product.id,
            kind="entrada",
            quantity=1,
            reason="x",
        )


def test_ajuste_define_o_saldo_pela_contagem(world: World) -> None:
    product = world.product(stock=10)
    up = stock.adjust_stock(
        world.conn, world.stocker, product_id=product.id, counted_quantity=14, reason="Inventário"
    )
    assert (up.type, up.quantity, up.balance_after) == ("entrada", 4, 14)
    down = stock.adjust_stock(
        world.conn, world.stocker, product_id=product.id, counted_quantity=9, reason="Inventário"
    )
    assert (down.type, down.quantity, down.balance_after) == ("saida", 5, 9)
    assert down.reason.startswith("Ajuste de inventário")
    assert world.stock_of(product) == 9


def test_ajuste_sem_diferenca_e_recusado(world: World) -> None:
    product = world.product(stock=10)
    with pytest.raises(BusinessRuleError, match="igual ao saldo"):
        stock.adjust_stock(
            world.conn, world.stocker, product_id=product.id, counted_quantity=10, reason="x"
        )


def test_ajuste_para_zero_e_permitido_e_negativo_nao(world: World) -> None:
    product = world.product(stock=3)
    stock.adjust_stock(
        world.conn, world.stocker, product_id=product.id, counted_quantity=0, reason="x"
    )
    assert world.stock_of(product) == 0
    with pytest.raises(ValidationError):
        stock.adjust_stock(
            world.conn, world.stocker, product_id=product.id, counted_quantity=-1, reason="x"
        )


def test_compor_motivo() -> None:
    assert stock.compose_reason("Avaria", "caixa molhada") == "Avaria — caixa molhada"
    assert stock.compose_reason("Avaria") == "Avaria"
    assert stock.compose_reason(stock.OTHER_REASON, "Doação") == "Doação"
    with pytest.raises(ValidationError):
        stock.compose_reason(stock.OTHER_REASON, "")
    with pytest.raises(ValidationError):
        stock.compose_reason("", "")


def test_alerta_de_reposicao_ordenado_por_urgencia(world: World) -> None:
    world.product(name="Cheio", stock=50, min_stock=5)
    world.product(name="Quase", stock=5, min_stock=5)
    world.product(name="Zero", stock=0, min_stock=5)
    names = [p.name for p in stock.products_to_restock(world.conn)]
    assert names == ["Zero", "Quase"]


def test_historico_filtra_por_tipo_produto_texto_e_data(world: World) -> None:
    a = world.product(name="Arroz", stock=10)
    b = world.product(name="Feijão", stock=10)
    stock.register_movement(
        world.conn,
        world.stocker,
        product_id=a.id,
        kind="saida",
        quantity=2,
        reason="Consumo interno",
        reference="OS-77",
    )
    stock.register_movement(
        world.conn,
        world.stocker,
        product_id=b.id,
        kind="entrada",
        quantity=5,
        reason="Compra de fornecedor",
    )
    history = lambda **kw: stock.list_movements(world.conn, world.manager, **kw)  # noqa: E731
    assert len(history()) == 4
    assert {m.type for m in history(movement_type="saida")} == {"saida"}
    assert next(m.product_name for m in history(product_id=a.id)) == "Arroz"
    assert [m.reference for m in history(text="os-77")] == ["OS-77"]
    assert len(history(text="fornecedor")) == 1
    assert len(history(text="feijao")) == 2  # busca também pelo nome, sem acento
    today = clock.today_iso()
    assert len(history(start=today, end=today)) == 4
    assert history(start="2999-01-01") == []
    assert history(end="2000-01-01") == []
    # mais recente primeiro
    ids = [m.id for m in history()]
    assert ids == sorted(ids, reverse=True)


def test_historico_exige_permissao(world: World) -> None:
    with pytest.raises(PermissionDeniedError):
        stock.list_movements(world.conn, world.operator)
