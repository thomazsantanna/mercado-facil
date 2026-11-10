"""Casos de teste da documentação (seção 8): CT01 a CT12.

Cada teste leva o ID do caso no nome (`test_ct01_…`). A tela "Projeto e operação"
executa este arquivo e associa cada resultado ao CT correspondente.
Os valores de CT05 e CT06 são os mesmos da documentação.
"""

from __future__ import annotations

import pytest

from mercadofacil.errors import BusinessRuleError, ValidationError
from mercadofacil.services import cash_register, catalog, post_sale, sales, stock
from tests.conftest import PASSWORDS, World


def test_ct01_cadastrar_barcode_ativo_duplicado(world: World) -> None:
    """Resultado esperado: cadastro bloqueado e mensagem clara."""
    world.product(barcode="7891234567895", name="Original")
    with pytest.raises(BusinessRuleError, match=r"Cadastro bloqueado.*7891234567895") as caught:
        world.product(barcode="7891234567895", name="Duplicado")
    assert caught.value.rule == "RB02"
    assert world.count("products") == 1


def test_ct02_cadastrar_com_campo_obrigatorio_vazio(world: World) -> None:
    """Resultado esperado: requisição rejeitada."""
    with pytest.raises(ValidationError):
        catalog.create_product(
            world.conn, world.stocker, barcode="7891234567895", name="", price_cents=100
        )
    with pytest.raises(ValidationError):
        catalog.create_product(
            world.conn, world.stocker, barcode="", name="Sem código", price_cents=100
        )
    assert world.count("products") == 0


def test_ct03_registrar_saida_maior_que_o_saldo(world: World) -> None:
    """Resultado esperado: estoque negativo impedido."""
    product = world.product(stock=5)
    with pytest.raises(BusinessRuleError, match="Estoque negativo impedido") as caught:
        stock.register_movement(
            world.conn,
            world.stocker,
            product_id=product.id,
            kind="saida",
            quantity=6,
            reason="Teste CT03",
        )
    assert caught.value.rule == "RB03"
    assert world.stock_of(product) == 5


def test_ct04_finalizar_venda_com_caixa_fechado(world: World) -> None:
    """Resultado esperado: venda não autorizada."""
    product = world.product(stock=5)
    with pytest.raises(BusinessRuleError, match="Venda não autorizada") as caught:
        world.sell([(product, 1)])
    assert caught.value.rule == "RB01"
    assert world.count("sales") == 0
    assert world.stock_of(product) == 5


def test_ct05_receber_r30_em_venda_de_r50(world: World) -> None:
    """Resultado esperado: pagamento bloqueado."""
    world.open_cash()
    product = world.product(price=5_000, stock=5)
    with pytest.raises(BusinessRuleError, match="Pagamento bloqueado") as caught:
        world.sell([(product, 1)], received=3_000)  # R$ 30,00 recebidos; total R$ 50,00
    assert caught.value.rule == "RB04"
    assert world.count("sales") == 0
    assert world.stock_of(product) == 5


def test_ct06_receber_r50_em_venda_de_r32_50(world: World) -> None:
    """Resultado esperado: troco calculado em R$ 17,50."""
    world.open_cash()
    product = world.product(price=3_250, stock=5)
    detail = world.sell([(product, 1)], received=5_000)  # R$ 50,00 recebidos; total R$ 32,50
    assert detail.sale.total_cents == 3_250
    assert detail.sale.change_cents == 1_750  # R$ 17,50
    assert world.stock_of(product) == 4


def test_ct07_utilizar_cashback_maior_que_o_saldo(world: World) -> None:
    """Resultado esperado: uso bloqueado."""
    world.open_cash()
    customer = world.customer(cashback=500)  # saldo R$ 5,00
    product = world.product(price=2_000)
    with pytest.raises(BusinessRuleError, match="Uso bloqueado") as caught:
        world.sell([(product, 1)], cpf=customer.cpf, cashback=600)  # pede R$ 6,00
    assert caught.value.rule == "RB06"
    assert world.balance_of(customer) == 500
    assert world.count("sales") == 0


def test_ct08_vender_quantidade_maior_que_o_estoque(world: World) -> None:
    """Resultado esperado: venda bloqueada."""
    world.open_cash()
    product = world.product(stock=3)
    with pytest.raises(BusinessRuleError, match="Venda bloqueada") as caught:
        world.sell([(product, 4)])
    assert caught.value.rule == "RB03"
    assert world.count("sales") == 0
    assert world.stock_of(product) == 3


def test_ct09_cancelar_venda_concluida(world: World) -> None:
    """Resultado esperado: itens retornam e a venda fica cancelada."""
    world.open_cash()
    product = world.product(price=1_000, stock=10)
    sale = world.sell([(product, 4)])
    assert world.stock_of(product) == 6

    post_sale.cancel_sale(
        world.conn,
        world.operator,
        sale.sale.id,
        notes="CT09",
        supervisor_username="gestor",
        supervisor_password=PASSWORDS["gestor"],
    )

    assert world.stock_of(product) == 10  # itens retornam
    final = sales.get_sale_detail(world.conn, world.manager, sale.sale.id)
    assert final.sale.status == "cancelada"
    assert final.sale.status_label == "Cancelada"


def test_ct10_devolver_mais_itens_que_o_disponivel(world: World) -> None:
    """Resultado esperado: operação bloqueada."""
    world.open_cash()
    product = world.product(stock=10)
    sale = world.sell([(product, 3)])
    with pytest.raises(BusinessRuleError, match="Operação bloqueada") as caught:
        post_sale.return_item(
            world.conn,
            world.operator,
            sale.sale.id,
            sale.items[0].id,
            4,
            notes="CT10",
            supervisor_username="gestor",
            supervisor_password=PASSWORDS["gestor"],
        )
    assert caught.value.rule == "RB09"
    assert world.stock_of(product) == 7


def test_ct11_trocar_por_produto_sem_estoque(world: World) -> None:
    """Resultado esperado: troca bloqueada."""
    world.open_cash()
    original = world.product(stock=10)
    replacement = world.product(stock=0, name="Sem estoque")
    sale = world.sell([(original, 1)])
    with pytest.raises(BusinessRuleError, match="Troca bloqueada") as caught:
        post_sale.exchange_item(
            world.conn,
            world.operator,
            sale.sale.id,
            sale.items[0].id,
            replacement.id,
            1,
            notes="CT11",
            supervisor_username="gestor",
            supervisor_password=PASSWORDS["gestor"],
        )
    assert caught.value.rule == "RB10"
    assert world.stock_of(original) == 9


def test_ct12_fechar_com_contado_menor_que_o_esperado(world: World) -> None:
    """Resultado esperado: falta registrada com valor negativo."""
    world.open_cash(opening=10_000)
    product = world.product(price=2_500)
    world.sell([(product, 2)])  # esperado na gaveta: 10.000 + 5.000 = R$ 150,00
    closed = cash_register.close_register(world.conn, world.operator, 14_500)  # contou R$ 145,00
    assert closed.expected_cents == 15_000
    assert closed.counted_cents == 14_500
    assert closed.difference_cents == -500  # falta de R$ 5,00 registrada
