"""Dados iniciais de demonstração.

São inseridos SOMENTE quando a base está vazia (decisão de implementação 6.1).
"""

from __future__ import annotations

import sqlite3

from . import clock, config
from .database import transaction
from .repositories import catalog as catalog_repo
from .repositories import customers as customers_repo
from .services import auth, stock

SYSTEM_OPERATOR = "sistema"

DEMO_USERS = [
    # (usuário, nome, perfil, senha)
    ("gestor", "Gestor de Demonstração", config.ROLE_MANAGER, "gestor123"),
    ("operador", "Operador de Demonstração", config.ROLE_OPERATOR, "operador123"),
    ("estoquista", "Estoquista de Demonstração", config.ROLE_STOCKER, "estoque123"),
]

# (CPF válido de teste, nome, saldo inicial de cashback em centavos)
DEMO_CUSTOMERS = [
    ("52998224725", "Maria Silva", 1234),
    ("11144477735", "João Pereira", 0),
    ("39053344705", "Ana Souza", 4850),
]

# (nome, categoria, unidade, preço, custo, saldo, mínimo, localização) — valores em centavos
DEMO_PRODUCTS = [
    ("Arroz Tipo 1 5kg", "Mercearia", "pct", 2790, 2150, 60, 15, "Corredor 1 · A"),
    ("Feijão Carioca 1kg", "Mercearia", "pct", 799, 560, 80, 20, "Corredor 1 · B"),
    ("Açúcar Refinado 1kg", "Mercearia", "pct", 459, 320, 70, 20, "Corredor 1 · C"),
    ("Sal Refinado 1kg", "Mercearia", "pct", 249, 150, 50, 10, "Corredor 1 · C"),
    ("Café Torrado 500g", "Mercearia", "pct", 1890, 1400, 8, 12, "Corredor 2 · A"),
    ("Macarrão Espaguete 500g", "Mercearia", "pct", 489, 310, 90, 25, "Corredor 2 · B"),
    ("Óleo de Soja 900ml", "Mercearia", "un", 749, 560, 0, 15, "Corredor 2 · C"),
    ("Refrigerante Cola 2L", "Bebidas", "un", 949, 640, 48, 12, "Corredor 3 · A"),
    ("Água Mineral 1,5L", "Bebidas", "un", 229, 130, 120, 30, "Corredor 3 · B"),
    ("Suco de Laranja 1L", "Bebidas", "un", 859, 590, 24, 10, "Corredor 3 · C"),
    ("Cerveja Pilsen Lata 350ml", "Bebidas", "un", 349, 240, 150, 48, "Corredor 3 · D"),
    ("Banana Prata", "Hortifruti", "kg", 599, 380, 35, 10, "Hortifruti · 1"),
    ("Tomate", "Hortifruti", "kg", 749, 480, 28, 10, "Hortifruti · 2"),
    ("Maçã Fuji", "Hortifruti", "kg", 1199, 800, 5, 8, "Hortifruti · 3"),
    ("Peito de Frango Congelado 1kg", "Açougue", "kg", 1790, 1300, 22, 8, "Freezer · 1"),
    ("Leite Integral 1L", "Laticínios", "un", 549, 410, 96, 36, "Refrigerados · A"),
    ("Queijo Mussarela Fatiado 200g", "Laticínios", "pct", 1490, 1050, 18, 8, "Refrigerados · B"),
    ("Iogurte Natural 170g", "Laticínios", "un", 229, 150, 40, 15, "Refrigerados · C"),
    ("Manteiga 200g", "Laticínios", "un", 1290, 950, 25, 10, "Refrigerados · D"),
    ("Pão Francês", "Padaria", "kg", 1590, 900, 15, 5, "Padaria · 1"),
    ("Bolo de Cenoura", "Padaria", "un", 1290, 800, 6, 3, "Padaria · 2"),
    ("Detergente Líquido 500ml", "Limpeza", "un", 259, 150, 80, 20, "Corredor 5 · A"),
    ("Sabão em Pó 1kg", "Limpeza", "pct", 1190, 820, 30, 10, "Corredor 5 · B"),
    ("Água Sanitária 1L", "Limpeza", "un", 449, 280, 3, 10, "Corredor 5 · C"),
    ("Sabonete 90g", "Higiene", "un", 259, 150, 100, 30, "Corredor 6 · A"),
    ("Creme Dental 90g", "Higiene", "un", 599, 380, 45, 15, "Corredor 6 · B"),
    ("Papel Higiênico 12 rolos", "Higiene", "pct", 2490, 1800, 40, 12, "Corredor 6 · C"),
]


def ean13(body12: str) -> str:
    """Acrescenta o dígito verificador EAN-13 a 12 dígitos."""
    total = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(body12))
    return body12 + str((10 - total % 10) % 10)


def demo_barcode(index: int) -> str:
    return ean13(f"7891000{index:05d}")


def is_database_empty(conn: sqlite3.Connection) -> bool:
    tables = ("users", "products", "customers", "sales", "registers")
    return all(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0 for table in tables)


def ensure_initial_data(conn: sqlite3.Connection) -> bool:
    """Popula a base vazia. Retorna True se inseriu algo."""
    with transaction(conn):
        if not is_database_empty(conn):
            return False
        for username, name, role, password in DEMO_USERS:
            auth.create_user(conn, username=username, name=name, role=role, password=password)
        if not config.seed_demo_data_enabled():
            return True
        for cpf, name, cashback in DEMO_CUSTOMERS:
            customers_repo.insert_customer(conn, cpf=cpf, name=name, created_at=clock.now_iso())
            if cashback:
                customers_repo.set_cashback(conn, cpf, cashback)
        for index, (name, category, unit, price, cost, quantity, minimum, location) in enumerate(
            DEMO_PRODUCTS, start=1
        ):
            product_id = catalog_repo.insert_product(
                conn,
                barcode=demo_barcode(index),
                name=name,
                category=category,
                unit=unit,
                price_cents=price,
                cost_cents=cost,
                min_stock=minimum,
                location=location,
                created_at=clock.now_iso(),
            )
            if quantity > 0:
                stock.apply_movement(
                    conn,
                    product_id=product_id,
                    movement_type="entrada",
                    quantity=quantity,
                    reason=f"{stock.REASON_INITIAL} (demonstração)",
                    reference="Carga inicial",
                    operator=SYSTEM_OPERATOR,
                )
    return True
