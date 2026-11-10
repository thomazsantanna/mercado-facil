"""Frente de caixa: carrinho, pagamento, troco, cashback e conclusão (RF03–RF07, RB01–RB07)."""

from __future__ import annotations

import pytest

from mercadofacil import clock
from mercadofacil.errors import (
    BusinessRuleError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from mercadofacil.services import catalog, customers, payments, sales, stock
from tests.conftest import CPF_A, CPF_B, World


# ----------------------------------------------------------------------------- carrinho
def test_precificar_carrinho_agrupa_linhas_repetidas(world: World) -> None:
    a = world.product(price=1000)
    b = world.product(price=250)
    summary = sales.price_cart(world.conn, [(a.id, 2), (b.id, 4), (a.id, 1)])
    assert len(summary.lines) == 2
    assert summary.units == 7
    assert summary.subtotal_cents == 3 * 1000 + 4 * 250
    assert summary.total_cents == summary.subtotal_cents
    assert summary.cashback_earned_cents == 0  # sem cliente identificado
    assert summary.customer is None


def test_carrinho_vazio_e_recusado(world: World) -> None:
    with pytest.raises(BusinessRuleError, match="carrinho está vazio"):
        sales.price_cart(world.conn, [])


def test_quantidade_do_carrinho_deve_ser_positiva(world: World) -> None:
    a = world.product()
    for bad in (0, -1, "x"):
        with pytest.raises(ValidationError):
            sales.price_cart(world.conn, [(a.id, bad)])  # type: ignore[arg-type]


def test_exibicao_sinaliza_estoque_insuficiente_sem_levantar_erro(world: World) -> None:
    a = world.product(stock=2)
    summary = sales.price_cart(world.conn, [(a.id, 5)], check_stock=False)
    assert summary.has_stock_issue
    assert summary.lines[0].has_stock_issue
    with pytest.raises(BusinessRuleError, match="estoque insuficiente"):
        sales.price_cart(world.conn, [(a.id, 5)], check_stock=True)


def test_produto_inativo_nao_pode_ser_vendido(world: World) -> None:
    a = world.product()
    catalog.set_active(world.conn, world.stocker, a.id, False)
    with pytest.raises(BusinessRuleError, match="inativo"):
        sales.price_cart(world.conn, [(a.id, 1)])


def test_produto_inexistente_no_carrinho(world: World) -> None:
    with pytest.raises(NotFoundError):
        sales.price_cart(world.conn, [(999, 1)])


def test_cliente_precisa_estar_cadastrado_e_ter_cpf_valido(world: World) -> None:
    a = world.product()
    with pytest.raises(NotFoundError, match="Cliente não cadastrado"):
        sales.price_cart(world.conn, [(a.id, 1)], customer_cpf=CPF_A)
    with pytest.raises(ValidationError, match="CPF inválido"):
        sales.price_cart(world.conn, [(a.id, 1)], customer_cpf="123")


# ------------------------------------------------------------------------ venda e troco
def test_venda_em_dinheiro_calcula_o_troco_rf06(world: World) -> None:
    world.open_cash()
    product = world.product(price=3_250, stock=5)
    detail = world.sell([(product, 1)], received=5_000)
    assert detail.sale.total_cents == 3_250
    assert detail.sale.change_cents == 1_750
    assert detail.payment is not None
    assert (detail.payment.received_cents, detail.payment.change_cents) == (5_000, 1_750)
    assert detail.payment.status == "aprovado"
    assert detail.sale.status == "concluida"
    assert world.stock_of(product) == 4


def test_dinheiro_exato_nao_gera_troco(world: World) -> None:
    world.open_cash()
    product = world.product(price=999)
    assert world.sell([(product, 1)], received=999).sale.change_cents == 0


def test_valor_recebido_menor_que_o_total_e_bloqueado_rb04(world: World) -> None:
    world.open_cash()
    product = world.product(price=2_500, stock=5)
    with pytest.raises(
        BusinessRuleError, match=r"R\$ 30,00.*R\$ 50,00.*Faltam R\$ 20,00"
    ) as caught:
        world.sell([(product, 2)], received=3_000)
    assert caught.value.rule == "RB04"
    assert world.stock_of(product) == 5
    assert world.count("sales") == 0
    assert world.count("payments") == 0


def test_dinheiro_exige_o_valor_recebido(world: World) -> None:
    world.open_cash()
    product = world.product()
    with pytest.raises(BusinessRuleError, match="valor recebido"):
        sales.finalize_sale(
            world.conn, world.operator, [(product.id, 1)], payment_method="dinheiro"
        )


@pytest.mark.parametrize("method", ["pix", "debito", "credito"])
def test_troco_so_existe_para_dinheiro_rb05(world: World, method: str) -> None:
    world.open_cash()
    product = world.product(price=1_000)
    detail = world.sell(
        [(product, 1)], method=method, received=99_999
    )  # valor informado é ignorado
    assert detail.sale.change_cents == 0
    assert detail.payment is not None
    assert detail.payment.received_cents == 1_000
    assert detail.sale.payment_method == method
    assert payments.calculate_change(1_000, 5_000, method) == 0
    assert payments.calculate_change(1_000, 5_000, "dinheiro") == 4_000


def test_forma_de_pagamento_invalida(world: World) -> None:
    world.open_cash()
    product = world.product()
    with pytest.raises(ValidationError, match="Forma de pagamento inválida"):
        world.sell([(product, 1)], method="boleto")


def test_pagamento_eletronico_recusado_nao_registra_a_venda(world: World) -> None:
    world.open_cash()
    product = world.product(stock=5)
    with pytest.raises(BusinessRuleError, match="não aprovado"):
        sales.finalize_sale(
            world.conn,
            world.operator,
            [(product.id, 1)],
            payment_method="pix",
            electronic_approved=False,
        )
    assert world.stock_of(product) == 5
    assert world.count("sales") == 0


# --------------------------------------------------------------------------- RB01 / RB03
def test_venda_exige_caixa_aberto_rb01(world: World) -> None:
    product = world.product(stock=5)
    with pytest.raises(BusinessRuleError, match="Venda não autorizada") as caught:
        world.sell([(product, 1)])
    assert caught.value.rule == "RB01"
    assert world.stock_of(product) == 5
    assert world.count("sales") == 0


def test_caixa_aberto_de_outro_operador_nao_vale(world: World) -> None:
    world.open_cash(world.manager)
    product = world.product()
    with pytest.raises(BusinessRuleError, match="Venda não autorizada"):
        world.sell([(product, 1)])  # operador sem o próprio caixa
    assert world.sell([(product, 1)], user=world.manager).sale.operator == "gestor"


def test_nao_vende_mais_que_o_estoque_rb03(world: World) -> None:
    world.open_cash()
    product = world.product(stock=3, name="Leite")
    with pytest.raises(BusinessRuleError, match=r"“Leite”.*disponível 3.*solicitado 4") as caught:
        world.sell([(product, 4)])
    assert caught.value.rule == "RB03"
    assert world.stock_of(product) == 3
    assert world.count("sales") == 0


def test_venda_do_ultimo_item_zera_o_estoque_sem_negativar(world: World) -> None:
    world.open_cash()
    product = world.product(stock=3)
    world.sell([(product, 3)])
    assert world.stock_of(product) == 0


def test_venda_e_atomica_se_uma_linha_falha(world: World) -> None:
    world.open_cash()
    ok = world.product(stock=10)
    short = world.product(stock=1)
    movements_before = world.count("stock_movements")
    with pytest.raises(BusinessRuleError):
        world.sell([(ok, 2), (short, 5)])
    assert world.stock_of(ok) == 10  # a primeira linha não foi baixada
    assert world.count("sales") == 0
    assert world.count("sale_items") == 0
    assert world.count("stock_movements") == movements_before


# ----------------------------------------------------------------- rastreabilidade
def test_venda_baixa_estoque_com_movimentacao_referenciada(world: World) -> None:
    world.open_cash()
    a = world.product(stock=10)
    b = world.product(stock=4)
    detail = world.sell([(a, 3), (b, 1)])
    movements = stock.list_movements(world.conn, world.manager, text=detail.sale.id)
    assert len(movements) == 2
    for movement in movements:
        assert (movement.type, movement.reason, movement.reference) == (
            "saida",
            stock.REASON_SALE,
            detail.sale.id,
        )
        assert movement.operator == "operador"
    assert world.stock_of(a) == 7
    assert world.stock_of(b) == 3
    by_product = {m.product_id: m for m in movements}
    assert by_product[a.id].balance_after == 7


def test_numeracao_da_venda_e_sequencial_no_dia(world: World) -> None:
    world.open_cash()
    product = world.product(stock=10)
    prefix = f"V{clock.today().strftime('%Y%m%d')}-"
    assert world.sell([(product, 1)]).sale.id == f"{prefix}0001"
    assert world.sell([(product, 1)]).sale.id == f"{prefix}0002"


def test_item_guarda_o_preco_da_epoca_da_venda(world: World) -> None:
    world.open_cash()
    product = world.product(price=1_000)
    detail = world.sell([(product, 2)])
    catalog.update_price(world.conn, world.manager, product.id, 1_500)
    reloaded = sales.get_sale_detail(world.conn, world.operator, detail.sale.id)
    assert reloaded.items[0].unit_price_cents == 1_000
    assert reloaded.sale.total_cents == 2_000


# ----------------------------------------------------------------------------- cashback
def test_cliente_identificado_recebe_1_por_cento_rb07(world: World) -> None:
    world.open_cash()
    customer = world.customer(CPF_A, cashback=0)
    product = world.product(price=5_000)
    detail = world.sell([(product, 1)], cpf=customer.cpf)
    assert detail.sale.cashback_earned_cents == 50
    assert world.balance_of(customer) == 50
    assert detail.customer is not None
    assert detail.customer.cashback_cents == 50


def test_cashback_e_calculado_sobre_o_total_liquido(world: World) -> None:
    world.open_cash()
    customer = world.customer(CPF_A, cashback=500)
    product = world.product(price=2_000)
    detail = world.sell([(product, 1)], cpf=customer.cpf, cashback=300)
    assert detail.sale.subtotal_cents == 2_000
    assert detail.sale.cashback_used_cents == 300
    assert detail.sale.total_cents == 1_700
    assert detail.sale.cashback_earned_cents == 17  # 1% de 17,00, e não de 20,00
    assert world.balance_of(customer) == 500 - 300 + 17


@pytest.mark.parametrize(
    ("total", "earned"), [(99, 0), (100, 1), (199, 1), (250, 2), (0, 0), (-5, 0)]
)
def test_arredondamento_do_cashback_e_para_baixo(total: int, earned: int) -> None:
    assert customers.calculate_cashback_earned(total) == earned


def test_sem_cliente_nao_ha_cashback(world: World) -> None:
    world.open_cash()
    product = world.product(price=10_000)
    detail = world.sell([(product, 1)])
    assert detail.sale.customer_cpf is None
    assert detail.sale.cashback_earned_cents == 0


def test_cashback_maior_que_o_saldo_e_bloqueado_rb06(world: World) -> None:
    world.open_cash()
    customer = world.customer(cashback=500)
    product = world.product(price=2_000)
    with pytest.raises(BusinessRuleError, match=r"R\$ 6,00.*maior que o saldo.*R\$ 5,00") as caught:
        world.sell([(product, 1)], cpf=customer.cpf, cashback=600)
    assert caught.value.rule == "RB06"
    assert world.balance_of(customer) == 500
    assert world.count("sales") == 0


def test_cashback_maior_que_o_valor_da_compra_e_bloqueado_rb06(world: World) -> None:
    world.open_cash()
    customer = world.customer(cashback=5_000)
    product = world.product(price=1_000)
    with pytest.raises(BusinessRuleError, match="maior que o valor da compra"):
        world.sell([(product, 1)], cpf=customer.cpf, cashback=2_000)


def test_cashback_exige_cliente_identificado(world: World) -> None:
    world.open_cash()
    product = world.product(price=1_000)
    with pytest.raises(BusinessRuleError, match="identifique o cliente"):
        world.sell([(product, 1)], cashback=100)


def test_compra_quitada_com_cashback_nao_pede_pagamento(world: World) -> None:
    world.open_cash()
    customer = world.customer(cashback=1_000)
    product = world.product(price=1_000)
    detail = world.sell([(product, 1)], cpf=customer.cpf, cashback=1_000, method="pix")
    assert detail.sale.total_cents == 0
    assert detail.sale.payment_method == "cashback"
    assert detail.sale.change_cents == 0
    assert detail.sale.cashback_earned_cents == 0
    assert world.balance_of(customer) == 0


def test_limite_de_cashback_utilizavel() -> None:
    from mercadofacil.models import Customer

    maria = Customer(cpf=CPF_A, name="Maria", cashback_cents=800)
    assert customers.max_usable_cashback(maria, 5_000) == 800  # limitado pelo saldo
    assert customers.max_usable_cashback(maria, 300) == 300  # limitado pela compra
    assert customers.max_usable_cashback(None, 300) == 0


# ------------------------------------------------------------------------------ clientes
def test_cadastro_minimo_de_cliente(world: World) -> None:
    customer = customers.register_customer(
        world.conn, world.operator, "529.982.247-25", " Maria  Silva "
    )
    assert (customer.cpf, customer.name, customer.cashback_cents) == (CPF_A, "Maria Silva", 0)
    with pytest.raises(BusinessRuleError, match="já está cadastrado"):
        customers.register_customer(world.conn, world.operator, CPF_A, "Outra")
    with pytest.raises(ValidationError):
        customers.register_customer(world.conn, world.operator, CPF_B, "  ")
    with pytest.raises(ValidationError, match="CPF inválido"):
        customers.register_customer(world.conn, world.operator, "000.000.000-00", "X")
    with pytest.raises(PermissionDeniedError):
        customers.register_customer(world.conn, world.stocker, CPF_B, "X")


def test_busca_de_cliente_por_cpf(world: World) -> None:
    world.customer(CPF_A, "Maria")
    assert customers.find_customer(world.conn, "529.982.247-25") is not None
    assert customers.find_customer(world.conn, CPF_B) is None
    assert customers.get_customer(world.conn, CPF_A).name == "Maria"
    with pytest.raises(NotFoundError):
        customers.get_customer(world.conn, CPF_B)


# ------------------------------------------------------------------------- permissões
def test_somente_perfis_de_venda_finalizam(world: World) -> None:
    world.open_cash()
    product = world.product()
    with pytest.raises(PermissionDeniedError):
        sales.finalize_sale(world.conn, world.stocker, [(product.id, 1)], payment_method="pix")
    assert world.sell([(product, 1)], method="pix", user=world.operator)


# ------------------------------------------------------------------------------ consulta
def test_consulta_de_vendas_com_filtros_rf15(world: World) -> None:
    world.open_cash()
    customer = world.customer(CPF_A, "Maria Silva")
    product = world.product(price=1_000, stock=50)
    cash_sale = world.sell([(product, 1)])
    pix_sale = world.sell([(product, 2)], method="pix", cpf=customer.cpf)

    listing = lambda **kw: [s.id for s in sales.list_sales(world.conn, world.operator, **kw)]  # noqa: E731
    assert listing() == [pix_sale.sale.id, cash_sale.sale.id]  # mais recente primeiro
    assert listing(payment_method="pix") == [pix_sale.sale.id]
    assert listing(status="concluida") == [pix_sale.sale.id, cash_sale.sale.id]
    assert listing(status="cancelada") == []
    assert listing(text="maria") == [pix_sale.sale.id]
    assert listing(text="529.982") == [pix_sale.sale.id]  # por CPF
    assert listing(text=cash_sale.sale.id.lower()) == [cash_sale.sale.id]
    today = clock.today_iso()
    assert len(listing(start=today, end=today)) == 2
    assert listing(start="2999-01-01") == []
    assert listing(limit=1) == [pix_sale.sale.id]

    detail = sales.get_sale_detail(world.conn, world.operator, f" {pix_sale.sale.id} ")
    assert detail.customer is not None and detail.customer.name == "Maria Silva"
    assert [i.quantity for i in detail.items] == [2]
    assert detail.items[0].product_name == product.name
    assert detail.payment is not None and detail.payment.method == "pix"
    assert detail.operations == []
    assert detail.active_units == 2


def test_consulta_de_venda_inexistente_ou_sem_permissao(world: World) -> None:
    with pytest.raises(NotFoundError, match="V0 não encontrada"):
        sales.get_sale_detail(world.conn, world.operator, "V0")
    with pytest.raises(PermissionDeniedError):
        sales.list_sales(world.conn, world.stocker)
    with pytest.raises(PermissionDeniedError):
        sales.get_sale_detail(world.conn, world.stocker, "V0")
