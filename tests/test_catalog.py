"""Cadastro de produtos (RF08, RB02) e consulta (RF03)."""

from __future__ import annotations

import sqlite3

import pytest

from mercadofacil.errors import BusinessRuleError, NotFoundError, ValidationError
from mercadofacil.services import catalog, stock
from tests.conftest import World


def test_cadastro_completo(world: World) -> None:
    product = catalog.create_product(
        world.conn,
        world.stocker,
        barcode=" 7891000000017 ",
        name="  Arroz   Tipo 1 ",
        price_cents=2790,
        cost_cents=2150,
        unit="pct",
        category="Mercearia",
        location="Corredor 1 · A",
        min_stock=15,
        initial_stock=60,
    )
    assert product.barcode == "7891000000017"
    assert product.name == "Arroz Tipo 1"
    assert (product.price_cents, product.cost_cents) == (2790, 2150)
    assert (product.unit, product.location, product.min_stock) == ("pct", "Corredor 1 · A", 15)
    assert product.stock == 60
    assert product.is_active
    assert product.margin_cents == 640


def test_estoque_inicial_gera_movimentacao_rastreavel(world: World) -> None:
    product = world.product(stock=25)
    [movement] = stock.list_movements(world.conn, world.manager, product_id=product.id)
    assert (movement.type, movement.quantity, movement.balance_after) == ("entrada", 25, 25)
    assert movement.reason == stock.REASON_INITIAL
    assert movement.operator == "estoquista"


def test_produto_sem_estoque_inicial_nao_gera_movimentacao(world: World) -> None:
    product = world.product(stock=0)
    assert stock.list_movements(world.conn, world.manager, product_id=product.id) == []


def test_codigo_de_barras_duplicado_e_bloqueado_rb02(world: World) -> None:
    first = world.product(barcode="7891234567895", name="Original")
    with pytest.raises(BusinessRuleError, match=r"7891234567895.*Original") as caught:
        world.product(barcode="7891234567895", name="Clone")
    assert caught.value.rule == "RB02"
    assert world.count("products") == 1
    assert catalog.find_by_barcode(world.conn, "7891234567895") == first


def test_duplicidade_ignora_caixa_alta(world: World) -> None:
    world.product(barcode="abc-1234")
    with pytest.raises(BusinessRuleError):
        world.product(barcode="ABC-1234")


def test_indice_unico_do_banco_protege_mesmo_sem_a_regra_do_servico(world: World) -> None:
    world.product(barcode="7891234567895")
    with pytest.raises(sqlite3.IntegrityError):
        world.conn.execute(
            "INSERT INTO products (barcode, name, price_cents, created_at) "
            "VALUES ('7891234567895', 'Via SQL', 100, '2026-01-01 00:00:00')"
        )


def test_barcode_de_produto_inativo_pode_ser_reutilizado(world: World) -> None:
    old = world.product(barcode="7891234567895", name="Antigo")
    catalog.set_active(world.conn, world.stocker, old.id, False)
    new = world.product(barcode="7891234567895", name="Novo")
    assert catalog.find_by_barcode(world.conn, "7891234567895") == new
    # Reativar o antigo criaria dois ativos com o mesmo código.
    with pytest.raises(BusinessRuleError, match="Novo") as caught:
        catalog.set_active(world.conn, world.stocker, old.id, True)
    assert caught.value.rule == "RB02"


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"name": "   "}, "Informe o nome do produto"),
        ({"barcode": ""}, "Informe o código de barras"),
        ({"price_cents": 0}, "preço deve ser maior que zero"),
        ({"price_cents": -1}, "preço deve ser maior que zero"),
        ({"cost_cents": -1}, "custo não pode ser negativo"),
        ({"initial_stock": -1}, "não pode ser negativo"),
        ({"min_stock": -3}, "não pode ser negativo"),
        ({"unit": "galão"}, "Unidade inválida"),
        ({"location": "x" * 61}, "no máximo 60"),
    ],
)
def test_campos_obrigatorios_e_invalidos_sao_rejeitados(
    world: World, override: dict[str, object], message: str
) -> None:
    data: dict[str, object] = {
        "barcode": "7891234567895",
        "name": "Produto",
        "price_cents": 100,
    }
    data.update(override)
    with pytest.raises(ValidationError, match=message):
        catalog.create_product(world.conn, world.stocker, **data)  # type: ignore[arg-type]
    assert world.count("products") == 0


def test_cadastro_e_atomico_ao_falhar_o_estoque_inicial(world: World) -> None:
    with pytest.raises(ValidationError):
        catalog.create_product(
            world.conn,
            world.stocker,
            barcode="7891234567895",
            name="X",
            price_cents=100,
            initial_stock="abc",  # type: ignore[arg-type]
        )
    assert world.count("products") == 0


def test_editar_nao_altera_o_saldo(world: World) -> None:
    product = world.product(stock=9)
    updated = catalog.update_product(
        world.conn,
        world.stocker,
        product.id,
        barcode=product.barcode,
        name="Nome novo",
        price_cents=1500,
        cost_cents=700,
        unit="kg",
        category="Bebidas",
        location="Corredor 9",
        min_stock=4,
    )
    assert updated.name == "Nome novo"
    assert updated.price_cents == 1500
    assert updated.stock == 9


def test_editar_para_codigo_ja_usado_e_bloqueado(world: World) -> None:
    world.product(barcode="1111-0001")
    other = world.product(barcode="1111-0002")
    with pytest.raises(BusinessRuleError):
        catalog.update_product(
            world.conn,
            world.stocker,
            other.id,
            barcode="1111-0001",
            name=other.name,
            price_cents=other.price_cents,
            cost_cents=other.cost_cents,
            unit=other.unit,
            category=other.category,
            location=other.location,
            min_stock=other.min_stock,
        )


def test_atualizar_preco(world: World) -> None:
    product = world.product(price=1000)
    assert catalog.update_price(world.conn, world.manager, product.id, 1099).price_cents == 1099
    with pytest.raises(ValidationError):
        catalog.update_price(world.conn, world.manager, product.id, 0)
    with pytest.raises(NotFoundError):
        catalog.update_price(world.conn, world.manager, 9999, 100)


def test_inativar_e_reativar_preserva_historico(world: World) -> None:
    product = world.product()
    inactive = catalog.set_active(world.conn, world.stocker, product.id, False)
    assert not inactive.is_active
    assert catalog.find_by_barcode(world.conn, product.barcode) is None
    assert catalog.get_product(world.conn, product.id).name == product.name  # ainda existe
    assert catalog.set_active(world.conn, world.stocker, product.id, True).is_active


def test_produto_inexistente(world: World) -> None:
    with pytest.raises(NotFoundError):
        catalog.get_product(world.conn, 12345)
    with pytest.raises(NotFoundError):
        catalog.set_active(world.conn, world.manager, 12345, False)


def test_busca_manual_ignora_acentos_e_caixa(world: World) -> None:
    sugar = world.product(
        name="Açúcar Refinado 1kg", category="Mercearia", location="Corredor 1 · C"
    )
    world.product(name="Água Mineral 1,5L", category="Bebidas", location="Corredor 3")
    names = lambda **kw: [p.name for p in catalog.search_products(world.conn, **kw)]  # noqa: E731
    assert names(term="acucar") == [sugar.name]
    assert names(term="ÁGUA") == ["Água Mineral 1,5L"]
    assert names(term="refinado 1kg") == [sugar.name]  # vários termos: todos precisam casar
    assert names(term="corredor 3") == ["Água Mineral 1,5L"]
    assert names(term=sugar.barcode) == [sugar.name]
    assert names(term="inexistente") == []
    assert len(names(term="")) == 2
    assert names(category="Bebidas") == ["Água Mineral 1,5L"]
    assert catalog.count_products(world.conn, term="acucar") == 1
    assert len(catalog.search_products(world.conn, limit=1)) == 1


def test_busca_trata_caracteres_especiais_do_like(world: World) -> None:
    world.product(name="Desconto 50% off")
    world.product(name="Produto qualquer")
    assert [p.name for p in catalog.search_products(world.conn, term="50%")] == ["Desconto 50% off"]
    assert catalog.search_products(world.conn, term="_") == []


def test_busca_exclui_inativos_por_padrao(world: World) -> None:
    gone = world.product(name="Descontinuado")
    catalog.set_active(world.conn, world.stocker, gone.id, False)
    assert catalog.search_products(world.conn, term="descontinuado") == []
    found = catalog.search_products(world.conn, term="descontinuado", include_inactive=True)
    assert [p.id for p in found] == [gone.id]


def test_filtro_de_estoque_minimo_rf10(world: World) -> None:
    ok = world.product(name="Cheio", stock=10, min_stock=2)
    at_min = world.product(name="No mínimo", stock=2, min_stock=2)
    empty = world.product(name="Zerado", stock=0, min_stock=2)
    below = [p.name for p in catalog.search_products(world.conn, only_below_minimum=True)]
    assert set(below) == {"No mínimo", "Zerado"}
    assert ok.stock_status == "ok"
    assert at_min.stock_status == "repor"
    assert empty.stock_status == "sem_estoque"
    assert at_min.is_below_minimum
    assert catalog.count_products(world.conn, only_below_minimum=True) == 2


def test_categorias_incluem_padroes_e_novas(world: World) -> None:
    world.product(category="Pet Shop")
    categories = catalog.list_categories(world.conn)
    assert "Pet Shop" in categories
    assert "Mercearia" in categories
    assert categories == sorted(categories, key=str.casefold)


def test_leitura_de_codigo_de_barras_rf03(world: World) -> None:
    product = world.product(barcode="abc-123")
    assert catalog.find_by_barcode(world.conn, "  ABC-123 ") == product  # leitor: espaços e caixa
    assert catalog.find_by_barcode(world.conn, "NAO-EXISTE") is None
    with pytest.raises(ValidationError):
        catalog.find_by_barcode(world.conn, "ab")  # curto demais para ser um código
