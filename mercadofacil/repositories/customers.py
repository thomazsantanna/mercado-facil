"""Clientes (identificados por CPF) e saldo de cashback."""

from __future__ import annotations

import sqlite3

from ..models import Customer, build, build_all


def get_customer(conn: sqlite3.Connection, cpf: str) -> Customer | None:
    row = conn.execute("SELECT * FROM customers WHERE cpf = ?", (cpf,)).fetchone()
    return build(Customer, row)


def insert_customer(conn: sqlite3.Connection, *, cpf: str, name: str, created_at: str) -> None:
    conn.execute(
        "INSERT INTO customers (cpf, name, cashback_cents, created_at) VALUES (?, ?, 0, ?)",
        (cpf, name, created_at),
    )


def adjust_cashback(conn: sqlite3.Connection, cpf: str, delta_cents: int) -> None:
    """Soma `delta_cents` ao saldo. O CHECK do banco impede saldo negativo."""
    conn.execute(
        "UPDATE customers SET cashback_cents = cashback_cents + ? WHERE cpf = ?",
        (delta_cents, cpf),
    )


def set_cashback(conn: sqlite3.Connection, cpf: str, cashback_cents: int) -> None:
    conn.execute("UPDATE customers SET cashback_cents = ? WHERE cpf = ?", (cashback_cents, cpf))


def list_customers(conn: sqlite3.Connection) -> list[Customer]:
    rows = conn.execute("SELECT * FROM customers ORDER BY fold(name)").fetchall()
    return build_all(Customer, rows)
