"""Persistência relacional (SQLite): conexão, transações e esquema (seção 6).

Valores monetários são inteiros em centavos. O histórico nunca é apagado
(RB12): gatilhos do banco bloqueiam DELETE nas tabelas de domínio e UPDATE nas
tabelas de log (movimentações, pagamentos e ocorrências de pós-venda).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from . import config
from .validators import fold

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE,
    name          TEXT    NOT NULL,
    role          TEXT    NOT NULL CHECK (role IN ('operador', 'estoquista', 'gestor')),
    password_hash TEXT    NOT NULL,
    active        INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    barcode     TEXT    NOT NULL,
    name        TEXT    NOT NULL,
    category    TEXT    NOT NULL DEFAULT 'Geral',
    unit        TEXT    NOT NULL DEFAULT 'un',
    price_cents INTEGER NOT NULL CHECK (price_cents > 0),
    cost_cents  INTEGER NOT NULL DEFAULT 0 CHECK (cost_cents >= 0),
    stock       INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
    min_stock   INTEGER NOT NULL DEFAULT 0 CHECK (min_stock >= 0),
    location    TEXT    NOT NULL DEFAULT '',
    active      INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at  TEXT    NOT NULL
);
-- RB02: dois produtos ATIVOS não podem ter o mesmo código de barras.
CREATE UNIQUE INDEX IF NOT EXISTS ux_products_barcode_active
    ON products (barcode) WHERE active = 1;
CREATE INDEX IF NOT EXISTS ix_products_name ON products (name);

CREATE TABLE IF NOT EXISTS customers (
    cpf            TEXT PRIMARY KEY,
    name           TEXT    NOT NULL,
    cashback_cents INTEGER NOT NULL DEFAULT 0 CHECK (cashback_cents >= 0),
    created_at     TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS registers (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    operator         TEXT    NOT NULL,
    status           TEXT    NOT NULL CHECK (status IN ('aberto', 'fechado')),
    opening_cents    INTEGER NOT NULL CHECK (opening_cents >= 0),
    expected_cents   INTEGER,
    counted_cents    INTEGER CHECK (counted_cents IS NULL OR counted_cents >= 0),
    difference_cents INTEGER,
    opened_at        TEXT    NOT NULL,
    closed_at        TEXT
);
-- Um caixa aberto por operador.
CREATE UNIQUE INDEX IF NOT EXISTS ux_registers_open_per_operator
    ON registers (operator) WHERE status = 'aberto';

CREATE TABLE IF NOT EXISTS sales (
    id                    TEXT PRIMARY KEY,
    register_id           INTEGER NOT NULL REFERENCES registers (id),
    customer_cpf          TEXT REFERENCES customers (cpf),
    subtotal_cents        INTEGER NOT NULL CHECK (subtotal_cents > 0),
    cashback_used_cents   INTEGER NOT NULL DEFAULT 0 CHECK (cashback_used_cents >= 0),
    total_cents           INTEGER NOT NULL CHECK (total_cents >= 0),
    payment_method        TEXT    NOT NULL
        CHECK (payment_method IN ('dinheiro', 'pix', 'debito', 'credito', 'cashback')),
    change_cents          INTEGER NOT NULL DEFAULT 0 CHECK (change_cents >= 0),
    cashback_earned_cents INTEGER NOT NULL DEFAULT 0 CHECK (cashback_earned_cents >= 0),
    status                TEXT    NOT NULL
        CHECK (status IN ('concluida', 'parcial', 'cancelada', 'devolvida')),
    operator              TEXT    NOT NULL,
    created_at            TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_sales_created ON sales (created_at);
CREATE INDEX IF NOT EXISTS ix_sales_customer ON sales (customer_cpf);
CREATE INDEX IF NOT EXISTS ix_sales_register ON sales (register_id);

CREATE TABLE IF NOT EXISTS sale_items (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id          TEXT    NOT NULL REFERENCES sales (id),
    product_id       INTEGER NOT NULL REFERENCES products (id),
    quantity         INTEGER NOT NULL CHECK (quantity > 0),
    unit_price_cents INTEGER NOT NULL CHECK (unit_price_cents > 0),
    cancelled_qty    INTEGER NOT NULL DEFAULT 0 CHECK (cancelled_qty >= 0),
    returned_qty     INTEGER NOT NULL DEFAULT 0 CHECK (returned_qty >= 0),
    CHECK (cancelled_qty + returned_qty <= quantity)
);
CREATE INDEX IF NOT EXISTS ix_sale_items_sale ON sale_items (sale_id);

CREATE TABLE IF NOT EXISTS payments (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id        TEXT    NOT NULL REFERENCES sales (id),
    method         TEXT    NOT NULL,
    amount_cents   INTEGER NOT NULL CHECK (amount_cents >= 0),
    received_cents INTEGER NOT NULL CHECK (received_cents >= 0),
    change_cents   INTEGER NOT NULL DEFAULT 0 CHECK (change_cents >= 0),
    status         TEXT    NOT NULL CHECK (status IN ('aprovado', 'recusado')),
    created_at     TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_payments_sale ON payments (sale_id);

CREATE TABLE IF NOT EXISTS stock_movements (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id    INTEGER NOT NULL REFERENCES products (id),
    type          TEXT    NOT NULL CHECK (type IN ('entrada', 'saida')),
    quantity      INTEGER NOT NULL CHECK (quantity > 0),
    balance_after INTEGER NOT NULL CHECK (balance_after >= 0),
    reason        TEXT    NOT NULL CHECK (length(trim(reason)) > 0),
    reference     TEXT    NOT NULL DEFAULT '',
    operator      TEXT    NOT NULL,
    created_at    TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_movements_product ON stock_movements (product_id, created_at);
CREATE INDEX IF NOT EXISTS ix_movements_created ON stock_movements (created_at);

CREATE TABLE IF NOT EXISTS post_sale_operations (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id                 TEXT    NOT NULL REFERENCES sales (id),
    type                    TEXT    NOT NULL
        CHECK (type IN ('cancelamento_venda', 'cancelamento_item', 'devolucao', 'troca')),
    product_id              INTEGER REFERENCES products (id),
    replacement_product_id  INTEGER REFERENCES products (id),
    quantity                INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    -- amount_cents: valor financeiro líquido. Positivo = dinheiro devolvido ao cliente;
    -- negativo = valor pago pelo cliente (diferença de troca).
    amount_cents            INTEGER NOT NULL DEFAULT 0,
    -- gross_cents: valor dos itens envolvidos, ao preço original da venda.
    gross_cents             INTEGER NOT NULL DEFAULT 0 CHECK (gross_cents >= 0),
    settlement_method       TEXT    NOT NULL DEFAULT '',
    cashback_restored_cents INTEGER NOT NULL DEFAULT 0 CHECK (cashback_restored_cents >= 0),
    cashback_reversed_cents INTEGER NOT NULL DEFAULT 0 CHECK (cashback_reversed_cents >= 0),
    register_id             INTEGER REFERENCES registers (id),
    operator                TEXT    NOT NULL,
    authorized_by           TEXT    NOT NULL,
    notes                   TEXT    NOT NULL DEFAULT '',
    created_at              TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_postsale_sale ON post_sale_operations (sale_id);
CREATE INDEX IF NOT EXISTS ix_postsale_register ON post_sale_operations (register_id);

-- RB12: históricos não são apagados; o status representa o resultado.
CREATE TRIGGER IF NOT EXISTS trg_users_no_delete BEFORE DELETE ON users
BEGIN SELECT RAISE(ABORT, 'Usuários não podem ser apagados; inative-os (RB12).'); END;
CREATE TRIGGER IF NOT EXISTS trg_products_no_delete BEFORE DELETE ON products
BEGIN SELECT RAISE(ABORT, 'Produtos não podem ser apagados; inative-os (RB12).'); END;
CREATE TRIGGER IF NOT EXISTS trg_customers_no_delete BEFORE DELETE ON customers
BEGIN SELECT RAISE(ABORT, 'Clientes não podem ser apagados (RB12).'); END;
CREATE TRIGGER IF NOT EXISTS trg_registers_no_delete BEFORE DELETE ON registers
BEGIN SELECT RAISE(ABORT, 'Caixas não podem ser apagados (RB12).'); END;
CREATE TRIGGER IF NOT EXISTS trg_sales_no_delete BEFORE DELETE ON sales
BEGIN SELECT RAISE(ABORT, 'Vendas não podem ser apagadas; o status é o resultado (RB12).'); END;
CREATE TRIGGER IF NOT EXISTS trg_sale_items_no_delete BEFORE DELETE ON sale_items
BEGIN SELECT RAISE(ABORT, 'Itens de venda não podem ser apagados (RB12).'); END;

CREATE TRIGGER IF NOT EXISTS trg_payments_no_delete BEFORE DELETE ON payments
BEGIN SELECT RAISE(ABORT, 'Pagamentos não podem ser apagados (RB12).'); END;
CREATE TRIGGER IF NOT EXISTS trg_payments_no_update BEFORE UPDATE ON payments
BEGIN SELECT RAISE(ABORT, 'Pagamentos não podem ser alterados (RB12).'); END;

CREATE TRIGGER IF NOT EXISTS trg_movements_no_delete BEFORE DELETE ON stock_movements
BEGIN SELECT RAISE(ABORT, 'Movimentações de estoque não podem ser apagadas (RB12).'); END;
CREATE TRIGGER IF NOT EXISTS trg_movements_no_update BEFORE UPDATE ON stock_movements
BEGIN SELECT RAISE(ABORT, 'Movimentações de estoque não podem ser alteradas (RB12).'); END;

CREATE TRIGGER IF NOT EXISTS trg_postsale_no_delete BEFORE DELETE ON post_sale_operations
BEGIN SELECT RAISE(ABORT, 'Ocorrências de pós-venda não podem ser apagadas (RB12).'); END;
CREATE TRIGGER IF NOT EXISTS trg_postsale_no_update BEFORE UPDATE ON post_sale_operations
BEGIN SELECT RAISE(ABORT, 'Ocorrências de pós-venda não podem ser alteradas (RB12).'); END;
"""


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Abre uma conexão (modo autocommit; transações são explícitas)."""
    path = str(db_path) if db_path is not None else str(config.get_db_path())
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.create_function("fold", 1, fold, deterministic=True)
    return conn


@contextmanager
def connect(db_path: str | Path | None = None) -> Iterator[sqlite3.Connection]:
    conn = get_connection(db_path)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Transação atômica. Se já houver uma aberta, participa dela."""
    if conn.in_transaction:
        yield conn
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def init_schema(conn: sqlite3.Connection) -> None:
    """Cria tabelas, índices e gatilhos (idempotente)."""
    conn.executescript(SCHEMA)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
