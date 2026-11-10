"""Indicadores (relatórios operacionais do gestor, seção 1), backup (RNF10) e comprovante."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from mercadofacil import clock
from mercadofacil.errors import PermissionDeniedError
from mercadofacil.services import backup, post_sale, receipts, reports
from tests.conftest import CPF_A, PASSWORDS, World


# ------------------------------------------------------------------------- indicadores
def _scenario(world: World):  # type: ignore[no-untyped-def]
    world.open_cash(opening=0)
    product = world.product(name="Arroz", price=1_000, stock=20, min_stock=5)
    cash_sale = world.sell([(product, 3)])  # R$ 30,00 em dinheiro
    pix_sale = world.sell([(product, 2)], method="pix")  # R$ 20,00 em Pix
    post_sale.cancel_sale(world.conn, world.manager, pix_sale.sale.id, notes="Desistência")
    return product, cash_sale, pix_sale


def test_indicadores_de_vendas_do_dia_rf17(world: World) -> None:
    _scenario(world)
    start, end = reports.today_range()
    kpis = reports.overview(world.conn, world.manager, start, end)
    assert kpis.sales_count == 1  # a venda cancelada não conta
    assert kpis.cancelled_count == 1
    assert kpis.gross_cents == 5_000
    assert kpis.refunds_cents == 2_000
    assert kpis.net_cents == 3_000
    assert kpis.average_ticket_cents == 3_000
    assert kpis.items_sold == 3


def test_indicadores_sem_vendas_nao_dividem_por_zero(world: World) -> None:
    start, end = reports.today_range()
    kpis = reports.overview(world.conn, world.manager, start, end)
    assert (kpis.sales_count, kpis.net_cents, kpis.average_ticket_cents) == (0, 0, 0)


def test_indicadores_de_reposicao(world: World) -> None:
    world.product(name="Cheio", stock=50, min_stock=5)
    world.product(name="Baixo", stock=3, min_stock=5)
    world.product(name="Zerado", stock=0, min_stock=5)
    world.customer(cashback=1_234)
    start, end = reports.today_range()
    kpis = reports.overview(world.conn, world.manager, start, end)
    assert kpis.low_stock_count == 1
    assert kpis.out_of_stock_count == 1
    assert kpis.cashback_outstanding_cents == 1_234


def test_vendas_por_pagamento_dia_e_produtos_mais_vendidos(world: World) -> None:
    _scenario(world)
    start, end = reports.today_range()
    assert reports.payment_breakdown(world.conn, world.manager, start, end) == [
        ("dinheiro", 1, 3_000)
    ]
    assert reports.daily_sales(world.conn, world.manager, start, end) == [
        (clock.today_iso(), 1, 3_000)
    ]
    assert reports.top_products(world.conn, world.manager, start, end) == [("Arroz", 3, 3_000)]
    assert reports.top_products(world.conn, world.manager, "2000-01-01", "2000-01-02") == []


def test_vendas_recentes(world: World) -> None:
    _, cash_sale, pix_sale = _scenario(world)
    recent = reports.recent_sales(world.conn, world.operator, limit=10)
    assert [s.id for s in recent] == [pix_sale.sale.id, cash_sale.sale.id]
    assert len(reports.recent_sales(world.conn, world.operator, limit=1)) == 1
    with pytest.raises(PermissionDeniedError):
        reports.recent_sales(world.conn, world.stocker)


def test_todos_os_perfis_veem_o_painel(world: World) -> None:
    start, end = reports.today_range()
    for user in (world.operator, world.stocker, world.manager):
        assert reports.overview(world.conn, user, start, end).sales_count == 0


# ----------------------------------------------------------------------------- backup
def test_backup_gera_copia_consistente_e_restauravel(world: World, tmp_path: Path) -> None:
    world.open_cash()
    product = world.product(name="Café", stock=7)
    world.sell([(product, 2)])

    filename, content = backup.backup_bytes(world.conn, world.manager)
    assert filename.startswith("mercado_facil_backup_") and filename.endswith(".db")
    assert content.startswith(b"SQLite format 3")

    # Alteração posterior ao backup não aparece na cópia.
    world.product(name="Criado depois")
    restored_path = tmp_path / "restaurado.db"
    restored_path.write_bytes(content)
    restored = sqlite3.connect(restored_path)
    try:
        names = {row[0] for row in restored.execute("SELECT name FROM products")}
        assert names == {"Café"}
        assert restored.execute("SELECT stock FROM products").fetchone()[0] == 5
        assert restored.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == 1
        assert restored.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        restored.close()


def test_backup_para_arquivo(world: World, tmp_path: Path) -> None:
    world.product()
    target = backup.backup_to_file(world.conn, tmp_path / "sub" / "copia.db")
    assert target.exists()


def test_so_gestor_faz_backup(world: World) -> None:
    for user in (world.operator, world.stocker):
        with pytest.raises(PermissionDeniedError):
            backup.backup_bytes(world.conn, user)


# -------------------------------------------------------------------------- comprovante
def test_comprovante_em_dinheiro_mostra_total_troco_e_cashback(world: World) -> None:
    world.open_cash()
    customer = world.customer(CPF_A, "Maria Silva", cashback=500)
    product = world.product(price=3_250, name="Queijo")
    detail = world.sell([(product, 1)], cpf=customer.cpf, cashback=250, received=5_000)
    text = receipts.build_receipt(detail)
    assert detail.sale.id in text
    assert "Queijo" in text
    assert "TOTAL" in text and "R$ 30,00" in text
    assert "TROCO" in text and "R$ 20,00" in text
    assert "Cashback utilizado" in text and "-R$ 2,50" in text
    assert "***.982.247-**" in text  # CPF mascarado
    assert "529.982.247-25" not in text and CPF_A not in text
    assert "sem valor fiscal" in text
    assert all(len(line) <= receipts.WIDTH for line in text.splitlines())


def test_comprovante_em_pix_nao_tem_troco(world: World) -> None:
    world.open_cash()
    product = world.product(price=1_000)
    text = receipts.build_receipt(world.sell([(product, 1)], method="pix"))
    assert "Pix" in text
    assert "TROCO" not in text
    assert "Cliente:" not in text


def test_comprovante_indica_itens_cancelados(world: World) -> None:
    world.open_cash()
    product = world.product(stock=10)
    sale = world.sell([(product, 3)])
    post_sale.cancel_item(
        world.conn,
        world.operator,
        sale.sale.id,
        sale.items[0].id,
        1,
        notes="x",
        supervisor_username="gestor",
        supervisor_password=PASSWORDS["gestor"],
    )
    from mercadofacil.services import sales

    text = receipts.build_receipt(sales.get_sale_detail(world.conn, world.manager, sale.sale.id))
    assert "cancelado: 1" in text
    assert "Parcialmente alterada" in text
