"""Pós-venda: cancelamento, devolução e troca (RF11–RF14, RB08–RB10, RB12)."""

from __future__ import annotations

import pytest

from mercadofacil.errors import (
    AuthenticationError,
    BusinessRuleError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from mercadofacil.models import SaleItem
from mercadofacil.services import cash_register, post_sale, sales, stock
from tests.conftest import PASSWORDS, World


def sup() -> dict[str, str]:
    """Credenciais do gestor para autorizar a operação feita pelo operador."""
    return {"supervisor_username": "gestor", "supervisor_password": PASSWORDS["gestor"]}


def _detail(world: World, sale_id: str):  # type: ignore[no-untyped-def]
    return sales.get_sale_detail(world.conn, world.manager, sale_id)


# --------------------------------------------------------------------------- RF11 / RB08
def test_cancelar_venda_devolve_itens_e_marca_cancelada_rf11(world: World) -> None:
    world.open_cash()
    product = world.product(price=1_000, stock=10)
    sale = world.sell([(product, 3)])
    assert world.stock_of(product) == 7

    operation = post_sale.cancel_sale(
        world.conn, world.operator, sale.sale.id, notes="Cliente desistiu", **sup()
    )

    detail = _detail(world, sale.sale.id)
    assert world.stock_of(product) == 10
    assert detail.sale.status == "cancelada"
    assert detail.items[0].cancelled_qty == 3
    assert detail.items[0].active_qty == 0
    assert operation.type == "cancelamento_venda"
    assert (operation.quantity, operation.amount_cents) == (3, 3_000)
    assert (operation.operator, operation.authorized_by) == ("operador", "gestor")
    assert operation.notes == "Cliente desistiu"
    latest = stock.list_movements(world.conn, world.manager, text=sale.sale.id)[0]
    assert (latest.type, latest.quantity, latest.reason) == (
        "entrada",
        3,
        stock.REASON_SALE_CANCEL,
    )
    assert latest.reference == sale.sale.id


def test_cancelamento_devolve_somente_a_quantidade_ainda_ativa_rb08(world: World) -> None:
    world.open_cash()
    product = world.product(price=1_000, stock=10)
    sale = world.sell([(product, 5)])
    item = sale.items[0]
    post_sale.cancel_item(
        world.conn, world.operator, sale.sale.id, item.id, 2, notes="Erro", **sup()
    )
    assert world.stock_of(product) == 7
    assert _detail(world, sale.sale.id).sale.status == "parcial"

    post_sale.cancel_sale(world.conn, world.operator, sale.sale.id, notes="Desistência", **sup())

    assert world.stock_of(product) == 10  # 5 baixados − 2 − 3 devolvidos = sem dupla devolução
    entries = [
        m.quantity
        for m in stock.list_movements(world.conn, world.manager, text=sale.sale.id)
        if m.type == "entrada"
    ]
    assert sorted(entries) == [2, 3]
    assert _detail(world, sale.sale.id).sale.status == "cancelada"


def test_venda_cancelada_nao_aceita_novas_operacoes(world: World) -> None:
    world.open_cash()
    product = world.product()
    sale = world.sell([(product, 1)])
    post_sale.cancel_sale(world.conn, world.operator, sale.sale.id, notes="x", **sup())
    with pytest.raises(BusinessRuleError, match="não aceita novas operações"):
        post_sale.cancel_sale(world.conn, world.operator, sale.sale.id, notes="x", **sup())
    with pytest.raises(BusinessRuleError, match="não aceita novas operações"):
        post_sale.return_item(
            world.conn, world.operator, sale.sale.id, sale.items[0].id, 1, notes="x", **sup()
        )
    assert world.stock_of(product) == 10


# ---------------------------------------------------------------------------- RF12
def test_cancelar_item_de_venda_concluida_rf12(world: World) -> None:
    world.open_cash()
    a = world.product(price=1_000, stock=10)
    b = world.product(price=500, stock=10)
    sale = world.sell([(a, 2), (b, 4)])
    item_b = next(i for i in sale.items if i.product_id == b.id)

    operation = post_sale.cancel_item(
        world.conn, world.operator, sale.sale.id, item_b.id, 3, notes="Item avariado", **sup()
    )

    detail = _detail(world, sale.sale.id)
    assert world.stock_of(b) == 10 - 4 + 3
    assert world.stock_of(a) == 8  # o outro item não é afetado
    assert detail.sale.status == "parcial"
    assert next(i for i in detail.items if i.id == item_b.id).cancelled_qty == 3
    assert (operation.type, operation.quantity, operation.product_id) == (
        "cancelamento_item",
        3,
        b.id,
    )
    assert operation.amount_cents == 1_500


def test_cancelar_item_alem_da_quantidade_ativa_e_bloqueado(world: World) -> None:
    world.open_cash()
    product = world.product()
    sale = world.sell([(product, 2)])
    with pytest.raises(BusinessRuleError, match="supera a quantidade ainda ativa") as caught:
        post_sale.cancel_item(
            world.conn, world.operator, sale.sale.id, sale.items[0].id, 3, notes="x", **sup()
        )
    assert caught.value.rule == "RB08"
    assert world.stock_of(product) == 8


def test_cancelar_todos_os_itens_um_a_um_cancela_a_venda(world: World) -> None:
    world.open_cash()
    a, b = world.product(), world.product()
    sale = world.sell([(a, 1), (b, 1)])
    for item in sale.items:
        post_sale.cancel_item(
            world.conn, world.operator, sale.sale.id, item.id, 1, notes="x", **sup()
        )
    assert _detail(world, sale.sale.id).sale.status == "cancelada"


# ----------------------------------------------------------------------- RF13 / RB09
def test_devolucao_parcial_rf13(world: World) -> None:
    world.open_cash()
    product = world.product(price=1_000, stock=10)
    sale = world.sell([(product, 3)])
    item = sale.items[0]

    operation = post_sale.return_item(
        world.conn, world.operator, sale.sale.id, item.id, 2, notes="Não gostou", **sup()
    )
    detail = _detail(world, sale.sale.id)
    assert world.stock_of(product) == 9
    assert detail.items[0].returned_qty == 2
    assert detail.items[0].active_qty == 1
    assert detail.sale.status == "parcial"
    assert operation.type == "devolucao"
    assert operation.amount_cents == 2_000

    latest = stock.list_movements(world.conn, world.manager, text=sale.sale.id)[0]
    assert latest.reason == stock.REASON_RETURN


def test_devolucao_maior_que_o_disponivel_e_bloqueada_rb09(world: World) -> None:
    world.open_cash()
    product = world.product(stock=10)
    sale = world.sell([(product, 3)])
    item = sale.items[0]
    operations_before = world.count("post_sale_operations")
    with pytest.raises(BusinessRuleError, match=r"não pode superar.*\(3\)") as caught:
        post_sale.return_item(
            world.conn, world.operator, sale.sale.id, item.id, 4, notes="x", **sup()
        )
    assert caught.value.rule == "RB09"
    assert world.stock_of(product) == 7
    assert world.count("post_sale_operations") == operations_before

    post_sale.return_item(world.conn, world.operator, sale.sale.id, item.id, 2, notes="x", **sup())
    with pytest.raises(BusinessRuleError, match=r"\(1\)"):  # só resta 1 disponível
        post_sale.return_item(
            world.conn, world.operator, sale.sale.id, item.id, 2, notes="x", **sup()
        )
    post_sale.return_item(world.conn, world.operator, sale.sale.id, item.id, 1, notes="x", **sup())
    assert _detail(world, sale.sale.id).sale.status == "devolvida"


def test_devolucao_sem_condicao_de_revenda_nao_repoe_estoque(world: World) -> None:
    world.open_cash()
    product = world.product(stock=10)
    sale = world.sell([(product, 2)])
    operation = post_sale.return_item(
        world.conn,
        world.operator,
        sale.sale.id,
        sale.items[0].id,
        1,
        notes="Defeito",
        restock=False,
        **sup(),
    )
    assert world.stock_of(product) == 8
    assert "não retornou ao estoque" in operation.notes


def test_item_de_outra_venda_e_recusado(world: World) -> None:
    world.open_cash()
    product = world.product(stock=10)
    first = world.sell([(product, 1)])
    second = world.sell([(product, 1)])
    with pytest.raises(NotFoundError, match="Item não encontrado"):
        post_sale.return_item(
            world.conn, world.operator, first.sale.id, second.items[0].id, 1, notes="x", **sup()
        )
    with pytest.raises(NotFoundError):
        post_sale.cancel_sale(world.conn, world.operator, "V-INEXISTENTE", notes="x", **sup())


# ----------------------------------------------------------------------- RF14 / RB10
def test_troca_movimenta_os_dois_produtos_rf14(world: World) -> None:
    world.open_cash()
    original = world.product(price=1_000, stock=10, name="Suco de uva")
    replacement = world.product(price=1_000, stock=6, name="Suco de laranja")
    sale = world.sell([(original, 2)])

    operation = post_sale.exchange_item(
        world.conn,
        world.operator,
        sale.sale.id,
        sale.items[0].id,
        replacement.id,
        2,
        notes="Prefere outro sabor",
        **sup(),
    )

    assert world.stock_of(original) == 10  # 10 − 2 vendidos + 2 devolvidos
    assert world.stock_of(replacement) == 4  # saiu 2
    detail = _detail(world, sale.sale.id)
    assert detail.items[0].returned_qty == 2
    assert detail.sale.status == "devolvida"
    assert (operation.type, operation.product_id, operation.replacement_product_id) == (
        "troca",
        original.id,
        replacement.id,
    )
    assert operation.replacement_name == "Suco de laranja"
    assert operation.amount_cents == 0  # mesmo valor: nada a pagar nem a devolver
    reasons = {
        m.reason: m.type for m in stock.list_movements(world.conn, world.manager, text=sale.sale.id)
    }
    assert reasons[stock.REASON_EXCHANGE_IN] == "entrada"
    assert reasons[stock.REASON_EXCHANGE_OUT] == "saida"


def test_troca_por_produto_sem_saldo_e_bloqueada_rb10(world: World) -> None:
    world.open_cash()
    original = world.product(stock=10)
    replacement = world.product(stock=1, name="Raro")
    sale = world.sell([(original, 2)])
    with pytest.raises(BusinessRuleError, match=r"Troca bloqueada.*“Raro”.*saldo 1") as caught:
        post_sale.exchange_item(
            world.conn,
            world.operator,
            sale.sale.id,
            sale.items[0].id,
            replacement.id,
            2,
            notes="x",
            **sup(),
        )
    assert caught.value.rule == "RB10"
    assert (world.stock_of(original), world.stock_of(replacement)) == (8, 1)  # nada mudou
    assert _detail(world, sale.sale.id).sale.status == "concluida"


def test_troca_exige_produto_diferente_ativo_e_existente(world: World) -> None:
    world.open_cash()
    original = world.product(stock=10)
    sale = world.sell([(original, 1)])
    item = sale.items[0]
    with pytest.raises(BusinessRuleError, match="produto diferente"):
        post_sale.exchange_item(
            world.conn, world.operator, sale.sale.id, item.id, original.id, 1, notes="x", **sup()
        )
    with pytest.raises(NotFoundError, match="substituto"):
        post_sale.exchange_item(
            world.conn, world.operator, sale.sale.id, item.id, 9999, 1, notes="x", **sup()
        )


def test_troca_maior_que_a_quantidade_disponivel(world: World) -> None:
    world.open_cash()
    original = world.product(stock=10)
    other = world.product(stock=10)
    sale = world.sell([(original, 1)])
    with pytest.raises(BusinessRuleError, match="não pode superar") as caught:
        post_sale.exchange_item(
            world.conn,
            world.operator,
            sale.sale.id,
            sale.items[0].id,
            other.id,
            2,
            notes="x",
            **sup(),
        )
    assert caught.value.rule == "RB09"


def test_troca_por_produto_mais_caro_cliente_paga_a_diferenca(world: World) -> None:
    register = world.open_cash(opening=10_000)
    original = world.product(price=1_000, stock=10)
    pricier = world.product(price=1_500, stock=10)
    sale = world.sell([(original, 2)])  # R$ 20,00 em dinheiro
    item = sale.items[0]
    with pytest.raises(
        ValidationError, match="Informe como o cliente pagará a diferença de R\\$ 10,00"
    ):
        post_sale.exchange_item(
            world.conn, world.operator, sale.sale.id, item.id, pricier.id, 2, notes="x", **sup()
        )

    operation = post_sale.exchange_item(
        world.conn,
        world.operator,
        sale.sale.id,
        item.id,
        pricier.id,
        2,
        notes="x",
        settlement_method="dinheiro",
        **sup(),
    )
    assert operation.amount_cents == -1_000  # negativo: o cliente pagou
    assert operation.settlement_method == "dinheiro"
    summary = cash_register.summarize(world.conn, register.id)
    assert summary.cash_in_cents == 1_000
    assert summary.expected_cents == 10_000 + 2_000 + 1_000


def test_troca_por_produto_mais_caro_pago_no_pix_nao_mexe_na_gaveta(world: World) -> None:
    register = world.open_cash(opening=0)
    original = world.product(price=1_000)
    pricier = world.product(price=1_500)
    sale = world.sell([(original, 2)])
    post_sale.exchange_item(
        world.conn,
        world.operator,
        sale.sale.id,
        sale.items[0].id,
        pricier.id,
        2,
        notes="x",
        settlement_method="pix",
        **sup(),
    )
    assert cash_register.summarize(world.conn, register.id).expected_cents == 2_000


def test_troca_por_produto_mais_barato_devolve_a_diferenca(world: World) -> None:
    register = world.open_cash(opening=0)
    original = world.product(price=1_000)
    cheaper = world.product(price=400)
    sale = world.sell([(original, 2)])
    operation = post_sale.exchange_item(
        world.conn,
        world.operator,
        sale.sale.id,
        sale.items[0].id,
        cheaper.id,
        2,
        notes="x",
        **sup(),
    )
    assert operation.amount_cents == 1_200  # 20,00 − 8,00 devolvidos em dinheiro
    assert operation.settlement_method == "dinheiro"
    assert cash_register.summarize(world.conn, register.id).expected_cents == 2_000 - 1_200


def test_troca_mais_barata_de_venda_paga_com_cashback_credita_cashback(world: World) -> None:
    world.open_cash()
    customer = world.customer(cashback=2_000)
    original = world.product(price=1_000)
    cheaper = world.product(price=400)
    sale = world.sell([(original, 2)], cpf=customer.cpf, cashback=2_000, method="pix")
    assert sale.sale.payment_method == "cashback"
    operation = post_sale.exchange_item(
        world.conn,
        world.operator,
        sale.sale.id,
        sale.items[0].id,
        cheaper.id,
        2,
        notes="x",
        **sup(),
    )
    assert operation.cashback_restored_cents == 1_200
    assert world.balance_of(customer) == 1_200


# ----------------------------------------------------------------------- autorização
def test_operador_precisa_da_autorizacao_de_um_gestor(world: World) -> None:
    world.open_cash()
    product = world.product()
    sale = world.sell([(product, 1)])
    with pytest.raises(PermissionDeniedError, match="autorização de um gestor"):
        post_sale.cancel_sale(world.conn, world.operator, sale.sale.id, notes="x")
    with pytest.raises(AuthenticationError, match="Autorização negada"):
        post_sale.cancel_sale(
            world.conn,
            world.operator,
            sale.sale.id,
            notes="x",
            supervisor_username="gestor",
            supervisor_password="errada",
        )
    with pytest.raises(PermissionDeniedError, match="somente um gestor"):
        post_sale.cancel_sale(
            world.conn,
            world.operator,
            sale.sale.id,
            notes="x",
            supervisor_username="operador",
            supervisor_password=PASSWORDS["operador"],
        )
    assert _detail(world, sale.sale.id).sale.status == "concluida"  # nada foi feito


def test_gestor_autoriza_a_si_mesmo(world: World) -> None:
    world.open_cash()
    product = world.product()
    sale = world.sell([(product, 1)], method="pix")
    operation = post_sale.cancel_sale(world.conn, world.manager, sale.sale.id, notes="Fraude")
    assert (operation.operator, operation.authorized_by) == ("gestor", "gestor")


def test_estoquista_nao_registra_pos_venda(world: World) -> None:
    world.open_cash()
    product = world.product()
    sale = world.sell([(product, 1)])
    with pytest.raises(PermissionDeniedError):
        post_sale.cancel_sale(world.conn, world.stocker, sale.sale.id, notes="x", **sup())


def test_motivo_do_cancelamento_e_obrigatorio(world: World) -> None:
    world.open_cash()
    product = world.product()
    sale = world.sell([(product, 1)])
    with pytest.raises(ValidationError, match="motivo"):
        post_sale.cancel_sale(world.conn, world.operator, sale.sale.id, notes="  ", **sup())


# ---------------------------------------------------------------- dinheiro e a gaveta
def test_estorno_em_dinheiro_sai_da_gaveta(world: World) -> None:
    register = world.open_cash(opening=10_000)
    product = world.product(price=1_000, stock=10)
    sale = world.sell([(product, 3)])
    assert cash_register.summarize(world.conn, register.id).expected_cents == 13_000
    post_sale.cancel_sale(world.conn, world.operator, sale.sale.id, notes="x", **sup())
    summary = cash_register.summarize(world.conn, register.id)
    assert summary.cash_out_cents == 3_000
    assert summary.expected_cents == 10_000


def test_estorno_em_dinheiro_exige_caixa_aberto(world: World) -> None:
    world.open_cash()
    product = world.product()
    sale = world.sell([(product, 1)])
    cash_register.close_register(world.conn, world.operator, 11_000)
    with pytest.raises(BusinessRuleError, match="Abra o caixa") as caught:
        post_sale.cancel_sale(world.conn, world.operator, sale.sale.id, notes="x", **sup())
    assert caught.value.rule == "RB01"
    assert world.stock_of(product) == 9  # nada mudou


def test_estorno_no_pix_nao_exige_caixa_nem_mexe_na_gaveta(world: World) -> None:
    register = world.open_cash(opening=0)
    product = world.product()
    sale = world.sell([(product, 1)], method="pix")
    cash_register.close_register(world.conn, world.operator, 0)
    operation = post_sale.cancel_sale(world.conn, world.operator, sale.sale.id, notes="x", **sup())
    assert operation.register_id is None
    assert cash_register.summarize(world.conn, register.id).expected_cents == 0


# -------------------------------------------------------- cálculo proporcional / cashback
@pytest.mark.parametrize(
    ("net", "subtotal", "gross", "expected"),
    [
        (899, 999, 333, 300),
        (899, 999, 666, 599),
        (899, 999, 999, 899),
        (1_000, 1_000, 250, 250),
        (1, 2, 1, 1),  # meio centavo arredonda para cima
        (0, 1_000, 500, 0),
        (500, 0, 100, 0),
        (500, 1_000, 0, 0),
    ],
)
def test_valor_proporcional(net: int, subtotal: int, gross: int, expected: int) -> None:
    assert post_sale.proportional_amount(net, subtotal, gross) == expected


def test_estornos_parciais_somam_exatamente_o_total_pago(world: World) -> None:
    """Venda de R$ 9,99 com R$ 1,00 de cashback: 3 estornos de itens fecham em R$ 8,99."""
    world.open_cash()
    customer = world.customer(cashback=100)
    products = [world.product(price=333) for _ in range(3)]
    sale = world.sell([(p, 1) for p in products], cpf=customer.cpf, cashback=100, method="pix")
    assert (sale.sale.subtotal_cents, sale.sale.total_cents) == (999, 899)
    assert sale.sale.cashback_earned_cents == 8
    assert world.balance_of(customer) == 8  # 100 − 100 + 8

    operations = [
        post_sale.cancel_item(
            world.conn, world.operator, sale.sale.id, item.id, 1, notes="x", **sup()
        )
        for item in sale.items
    ]
    assert [op.amount_cents for op in operations] == [300, 299, 300]
    assert sum(op.amount_cents for op in operations) == 899  # dinheiro devolvido = o que foi pago
    assert sum(op.cashback_restored_cents for op in operations) == 100  # cashback usado volta
    assert sum(op.cashback_reversed_cents for op in operations) == 8  # cashback ganho é estornado
    assert world.balance_of(customer) == 100
    assert _detail(world, sale.sale.id).sale.status == "cancelada"


def test_cancelamento_total_estorna_o_cashback_ganho(world: World) -> None:
    world.open_cash()
    customer = world.customer(cashback=0)
    product = world.product(price=10_000)
    sale = world.sell([(product, 1)], cpf=customer.cpf, method="pix")
    assert world.balance_of(customer) == 100
    post_sale.cancel_sale(world.conn, world.operator, sale.sale.id, notes="x", **sup())
    assert world.balance_of(customer) == 0


def test_estorno_de_cashback_nao_deixa_saldo_negativo(world: World) -> None:
    world.open_cash()
    customer = world.customer(cashback=0)
    product = world.product(price=10_000, stock=10)
    first = world.sell([(product, 1)], cpf=customer.cpf, method="pix")  # ganha 100
    world.sell([(product, 1)], cpf=customer.cpf, cashback=100, method="pix")  # gasta o saldo
    assert world.balance_of(customer) == 99  # 100 − 100 + 99 (1% de 99,00)
    post_sale.cancel_sale(world.conn, world.operator, first.sale.id, notes="x", **sup())
    assert world.balance_of(customer) == 0  # estorno limitado ao saldo existente


# ------------------------------------------------------------------------ status (RB12)
def test_status_da_venda_representa_o_resultado() -> None:
    def item(qty: int, cancelled: int = 0, returned: int = 0) -> SaleItem:
        return SaleItem(
            id=1,
            sale_id="V",
            product_id=1,
            quantity=qty,
            unit_price_cents=100,
            cancelled_qty=cancelled,
            returned_qty=returned,
        )

    assert post_sale.recompute_status([item(3)]) == "concluida"
    assert post_sale.recompute_status([item(3, cancelled=1)]) == "parcial"
    assert post_sale.recompute_status([item(3, returned=1)]) == "parcial"
    assert post_sale.recompute_status([item(3, cancelled=3)]) == "cancelada"
    assert post_sale.recompute_status([item(3, returned=3)]) == "devolvida"
    assert post_sale.recompute_status([item(3, cancelled=1, returned=2)]) == "devolvida"
    assert post_sale.recompute_status([item(1), item(2, cancelled=2)]) == "parcial"


def test_ocorrencias_sao_listadas_e_nunca_apagadas_rb12(world: World) -> None:
    world.open_cash()
    product = world.product(stock=10)
    sale = world.sell([(product, 3)])
    post_sale.return_item(
        world.conn, world.operator, sale.sale.id, sale.items[0].id, 1, notes="a", **sup()
    )
    post_sale.cancel_item(
        world.conn, world.operator, sale.sale.id, sale.items[0].id, 1, notes="b", **sup()
    )

    operations = post_sale.list_operations(world.conn, world.manager, sale_id=sale.sale.id)
    assert [op.type for op in operations] == [
        "cancelamento_item",
        "devolucao",
    ]  # mais recente primeiro
    assert [op.type_label for op in operations] == ["Cancelamento de item", "Devolução"]
    assert len(post_sale.list_operations(world.conn, world.manager, op_type="devolucao")) == 1
    assert len(_detail(world, sale.sale.id).operations) == 2
    with pytest.raises(PermissionDeniedError):
        post_sale.list_operations(world.conn, world.stocker)
