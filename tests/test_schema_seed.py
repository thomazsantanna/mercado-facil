"""Regras do banco (RB12, RNF02), dados de demonstração e bootstrap (6.1)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from mercadofacil import bootstrap, config, database, seed
from mercadofacil.services import auth, post_sale
from mercadofacil.validators import is_valid_cpf
from tests.conftest import PASSWORDS, World

ALL_TABLES = [
    "users",
    "products",
    "customers",
    "registers",
    "sales",
    "sale_items",
    "payments",
    "stock_movements",
    "post_sale_operations",
]


def _build_history(world: World) -> None:
    world.open_cash()
    product = world.product(stock=10)
    customer = world.customer()
    sale = world.sell([(product, 2)], cpf=customer.cpf)
    post_sale.return_item(
        world.conn,
        world.operator,
        sale.sale.id,
        sale.items[0].id,
        1,
        notes="x",
        supervisor_username="gestor",
        supervisor_password=PASSWORDS["gestor"],
    )


@pytest.mark.parametrize("table", ALL_TABLES)
def test_historico_nunca_e_apagado_rb12(world: World, table: str) -> None:
    _build_history(world)
    with pytest.raises(sqlite3.IntegrityError, match="RB12"):
        world.conn.execute(f"DELETE FROM {table}")
    assert world.count(table) > 0


@pytest.mark.parametrize("table", ["payments", "stock_movements", "post_sale_operations"])
def test_registros_de_log_nao_podem_ser_alterados(world: World, table: str) -> None:
    _build_history(world)
    column = {
        "payments": "amount_cents",
        "stock_movements": "quantity",
        "post_sale_operations": "quantity",
    }[table]
    with pytest.raises(sqlite3.IntegrityError, match="RB12"):
        world.conn.execute(f"UPDATE {table} SET {column} = {column} + 1")


def test_status_da_venda_e_o_unico_campo_que_evolui(world: World) -> None:
    _build_history(world)
    world.conn.execute("UPDATE sales SET status = 'cancelada'")  # permitido: é o "resultado"
    assert world.conn.execute("SELECT status FROM sales").fetchone()[0] == "cancelada"


def test_restricoes_de_integridade_do_modelo(world: World) -> None:
    world.open_cash()
    product = world.product(stock=5)
    sale = world.sell([(product, 2)])
    item_id = sale.items[0].id
    with pytest.raises(sqlite3.IntegrityError):  # cancelado + devolvido > vendido
        world.conn.execute(
            "UPDATE sale_items SET cancelled_qty = 2, returned_qty = 1 WHERE id = ?", (item_id,)
        )
    with pytest.raises(sqlite3.IntegrityError):  # valor monetário fracionário não existe: preço > 0
        world.conn.execute("UPDATE products SET price_cents = 0 WHERE id = ?", (product.id,))
    with pytest.raises(sqlite3.IntegrityError):  # status inválido
        world.conn.execute("UPDATE sales SET status = 'inventado'")
    with pytest.raises(sqlite3.IntegrityError):  # chave estrangeira
        world.conn.execute(
            "INSERT INTO sale_items (sale_id, product_id, quantity, unit_price_cents) "
            "VALUES ('NAO-EXISTE', 1, 1, 100)"
        )


def test_esquema_e_idempotente_e_versionado(conn: sqlite3.Connection) -> None:
    database.init_schema(conn)
    database.init_schema(conn)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == database.SCHEMA_VERSION
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    # tabelas da seção 6 + usuários (RNF08) + pagamentos (classe Pagamento, 5.2)
    assert {
        "products",
        "customers",
        "registers",
        "sales",
        "sale_items",
        "stock_movements",
        "post_sale_operations",
        "users",
        "payments",
    } <= tables


def test_transacao_faz_rollback_em_erro(conn: sqlite3.Connection) -> None:
    database.init_schema(conn)
    with pytest.raises(RuntimeError), database.transaction(conn):
        conn.execute(
            "INSERT INTO customers (cpf, name, cashback_cents, created_at) "
            "VALUES ('1', 'x', 0, 'x')"
        )
        raise RuntimeError("falha no meio")
    assert conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0] == 0


def test_transacao_aninhada_participa_da_externa(conn: sqlite3.Connection) -> None:
    database.init_schema(conn)
    with database.transaction(conn):
        with database.transaction(conn):
            conn.execute(
                "INSERT INTO customers (cpf, name, cashback_cents, created_at) "
                "VALUES ('1', 'x', 0, 'x')"
            )
        assert conn.in_transaction  # a interna não confirmou sozinha
    assert not conn.in_transaction
    assert conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0] == 1


# ---------------------------------------------------------------------------------- seed
def test_dados_de_demonstracao_so_entram_com_base_vazia(conn: sqlite3.Connection) -> None:
    database.init_schema(conn)
    assert seed.is_database_empty(conn)
    assert seed.ensure_initial_data(conn) is True
    counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ALL_TABLES}
    assert counts["users"] == 3
    assert counts["customers"] == len(seed.DEMO_CUSTOMERS)
    assert counts["products"] == len(seed.DEMO_PRODUCTS)
    assert counts["sales"] == 0
    assert seed.ensure_initial_data(conn) is False  # segunda chamada: nada a fazer
    assert conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == len(seed.DEMO_PRODUCTS)


def test_seed_nao_toca_em_base_com_dados(conn: sqlite3.Connection) -> None:
    database.init_schema(conn)
    auth.create_user(
        conn, username="existente", name="Já existia", role="gestor", password="123456"
    )
    assert seed.ensure_initial_data(conn) is False
    assert conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1


def test_seed_pode_criar_somente_os_usuarios(
    conn: sqlite3.Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MERCADO_FACIL_SEED", "0")
    database.init_schema(conn)
    assert seed.ensure_initial_data(conn) is True
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 3
    assert conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0


def test_usuarios_de_demonstracao_conseguem_entrar(conn: sqlite3.Connection) -> None:
    database.init_schema(conn)
    seed.ensure_initial_data(conn)
    for username, _, role, password in seed.DEMO_USERS:
        assert auth.authenticate(conn, username, password).role == role


def test_dados_de_demonstracao_sao_coerentes(conn: sqlite3.Connection) -> None:
    database.init_schema(conn)
    seed.ensure_initial_data(conn)
    assert all(is_valid_cpf(cpf) for cpf, _, _ in seed.DEMO_CUSTOMERS)
    barcodes = [r[0] for r in conn.execute("SELECT barcode FROM products")]
    assert len(set(barcodes)) == len(barcodes)
    for code in barcodes:
        assert len(code) == 13 and code.isdigit()
        assert seed.ean13(code[:12]) == code  # dígito verificador EAN-13 correto
    # Há produtos para exercitar os alertas de reposição (RF10).
    low = conn.execute(
        "SELECT COUNT(*) FROM products WHERE stock > 0 AND stock <= min_stock"
    ).fetchone()[0]
    empty = conn.execute("SELECT COUNT(*) FROM products WHERE stock = 0").fetchone()[0]
    assert low >= 1 and empty >= 1
    # O saldo inicial de cada produto está registrado como movimentação (RNF04).
    stocked = conn.execute("SELECT COUNT(*) FROM products WHERE stock > 0").fetchone()[0]
    entries = conn.execute(
        "SELECT COUNT(*) FROM stock_movements WHERE operator = ?", (seed.SYSTEM_OPERATOR,)
    ).fetchone()[0]
    assert entries == stocked
    total = conn.execute("SELECT SUM(stock) FROM products").fetchone()[0]
    assert total == conn.execute("SELECT SUM(quantity) FROM stock_movements").fetchone()[0]


def test_ean13() -> None:
    # 7·1 + 8·3 + 9·1 + 1·3 + 0… + 1·3 = 46  →  dígito verificador (10 − 46 mod 10) mod 10 = 4
    assert seed.ean13("789100000001") == "7891000000014"
    assert seed.ean13("400638133393") == "4006381333931"  # exemplo clássico de EAN-13


def test_bootstrap_cria_banco_com_demonstracao_uma_unica_vez(tmp_path: Path) -> None:
    target = tmp_path / "dados" / "mf.db"
    assert bootstrap.initialize(target) == target
    assert target.exists()
    with database.connect(target) as conn:
        first = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        assert first == len(seed.DEMO_PRODUCTS)
        conn.execute("UPDATE products SET stock = stock + 1 WHERE id = 1")
    bootstrap.initialize(target)  # reiniciar o sistema não repete a carga
    with database.connect(target) as conn:
        assert conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == first
        assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 3


def test_caminho_do_banco_vem_da_variavel_de_ambiente(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("MERCADO_FACIL_DB", str(tmp_path / "custom.db"))
    assert config.get_db_path() == tmp_path / "custom.db"
    monkeypatch.delenv("MERCADO_FACIL_DB")
    assert config.get_db_path().name == "mercado_facil.db"
