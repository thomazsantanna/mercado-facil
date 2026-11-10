"""Fixtures e fábrica de cenários para os testes.

`World` monta rapidamente um mercado com usuários dos três perfis, produtos,
clientes e caixa, usando sempre os serviços reais (as regras de negócio valem
nos testes do mesmo jeito que valem na aplicação).
"""

from __future__ import annotations

import itertools
import sqlite3
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest

from mercadofacil import config

config.PBKDF2_ITERATIONS = 1_000  # hashing rápido nos testes (produção usa 200 mil)

from mercadofacil import database  # noqa: E402
from mercadofacil.models import Customer, Product, Register, SaleDetail, User  # noqa: E402
from mercadofacil.repositories import customers as customers_repo  # noqa: E402
from mercadofacil.services import (  # noqa: E402
    auth,
    cash_register,
    catalog,
    customers,
    sales,
)

# CPFs com dígitos verificadores válidos (usados apenas em testes e na demonstração).
CPF_A = "52998224725"
CPF_B = "11144477735"
CPF_C = "39053344705"

PASSWORDS = {"gestor": "gestor123", "operador": "operador123", "estoquista": "estoque123"}


class World:
    """Cenário de teste com usuários, produtos, clientes e vendas."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self._sequence = itertools.count(1)
        self.manager = self._user("gestor", "Gestora de Teste", config.ROLE_MANAGER)
        self.operator = self._user("operador", "Operador de Teste", config.ROLE_OPERATOR)
        self.stocker = self._user("estoquista", "Estoquista de Teste", config.ROLE_STOCKER)

    def _user(self, username: str, name: str, role: str) -> User:
        return auth.create_user(
            self.conn, username=username, name=name, role=role, password=PASSWORDS[username]
        )

    # ------------------------------------------------------------------ fábricas
    def product(
        self,
        *,
        name: str | None = None,
        price: int = 1000,
        cost: int = 500,
        stock: int = 10,
        min_stock: int = 2,
        barcode: str | None = None,
        category: str = "Mercearia",
        location: str = "Corredor 1",
        unit: str = "un",
    ) -> Product:
        number = next(self._sequence)
        return catalog.create_product(
            self.conn,
            self.stocker,
            barcode=barcode or f"789000{number:06d}",
            name=name or f"Produto {number}",
            price_cents=price,
            cost_cents=cost,
            unit=unit,
            category=category,
            location=location,
            min_stock=min_stock,
            initial_stock=stock,
        )

    def customer(self, cpf: str = CPF_A, name: str = "Maria Teste", cashback: int = 0) -> Customer:
        created = customers.register_customer(self.conn, self.operator, cpf, name)
        if cashback:
            customers_repo.set_cashback(self.conn, created.cpf, cashback)
        found = customers_repo.get_customer(self.conn, created.cpf)
        assert found is not None
        return found

    def open_cash(self, user: User | None = None, opening: int = 10_000) -> Register:
        return cash_register.open_register(self.conn, user or self.operator, opening)

    def sell(
        self,
        lines: Sequence[tuple[Product | int, int]],
        *,
        method: str = "dinheiro",
        received: int | None = None,
        cpf: str | None = None,
        cashback: int = 0,
        user: User | None = None,
    ) -> SaleDetail:
        """Conclui uma venda. Em dinheiro, sem `received`, paga o valor exato."""
        pairs = [(p.id if isinstance(p, Product) else p, q) for p, q in lines]
        if method == "dinheiro" and received is None:
            summary = sales.price_cart(self.conn, pairs, customer_cpf=cpf, cashback_to_use=cashback)
            received = summary.total_cents
        return sales.finalize_sale(
            self.conn,
            user or self.operator,
            pairs,
            payment_method=method,
            received_cents=received,
            customer_cpf=cpf,
            cashback_to_use=cashback,
        )

    # ------------------------------------------------------------------ consultas
    def stock_of(self, product: Product) -> int:
        return catalog.get_product(self.conn, product.id).stock

    def balance_of(self, customer: Customer) -> int:
        found = customers_repo.get_customer(self.conn, customer.cpf)
        assert found is not None
        return found.cashback_cents

    def count(self, table: str) -> int:
        return int(self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    connection = database.get_connection(tmp_path / "teste.db")
    database.init_schema(connection)
    yield connection
    connection.close()


@pytest.fixture
def world(conn: sqlite3.Connection) -> World:
    return World(conn)


# Fixtures da interface (Streamlit simulado): disponíveis para todos os testes.
from tests.ui_harness import app, modern_app, ui_db  # noqa: E402, F401
