"""Cadastro de produtos (RF08, RB02)."""

from __future__ import annotations

import sqlite3

from .. import clock
from ..database import transaction
from ..errors import BusinessRuleError, NotFoundError, ValidationError
from ..models import Product, User
from ..repositories import catalog as catalog_repo
from ..validators import (
    normalize_barcode,
    optional_text,
    require_non_negative_int,
    require_text,
)
from . import permissions, stock

UNITS = ["un", "kg", "g", "l", "ml", "pct", "cx", "dz"]
DEFAULT_CATEGORIES = [
    "Mercearia",
    "Bebidas",
    "Hortifruti",
    "Açougue",
    "Laticínios",
    "Padaria",
    "Limpeza",
    "Higiene",
    "Congelados",
    "Geral",
]


def _check_price(price_cents: int) -> int:
    if not isinstance(price_cents, int) or isinstance(price_cents, bool) or price_cents <= 0:
        raise ValidationError("O preço deve ser maior que zero.")
    return price_cents


def _check_cost(cost_cents: int) -> int:
    if not isinstance(cost_cents, int) or isinstance(cost_cents, bool) or cost_cents < 0:
        raise ValidationError("O custo não pode ser negativo.")
    return cost_cents


def _check_unit(unit: str) -> str:
    value = require_text(unit, "a unidade", max_length=10).lower()
    if value not in UNITS:
        raise ValidationError(f"Unidade inválida. Use uma destas: {', '.join(UNITS)}.")
    return value


def _ensure_barcode_free(
    conn: sqlite3.Connection, barcode: str, *, ignore_product_id: int | None = None
) -> None:
    """RB02: dois produtos ativos não podem ter o mesmo código de barras."""
    existing = catalog_repo.get_active_product_by_barcode(conn, barcode)
    if existing is not None and existing.id != ignore_product_id:
        raise BusinessRuleError(
            f"Cadastro bloqueado: já existe um produto ativo com o código de barras {barcode} "
            f"(“{existing.name}”). Use outro código ou inative o produto existente.",
            rule="RB02",
        )


def create_product(
    conn: sqlite3.Connection,
    actor: User,
    *,
    barcode: str,
    name: str,
    price_cents: int,
    cost_cents: int = 0,
    unit: str = "un",
    category: str = "Geral",
    location: str = "",
    min_stock: int = 0,
    initial_stock: int = 0,
) -> Product:
    """RF08: cadastra produto com preço, custo, unidade e localização."""
    permissions.ensure_permission(actor, permissions.PRODUCT_MANAGE)
    code = normalize_barcode(barcode)
    product_name = require_text(name, "o nome do produto")
    product_category = require_text(category or "Geral", "a categoria", max_length=60)
    product_unit = _check_unit(unit)
    price = _check_price(price_cents)
    cost = _check_cost(cost_cents)
    minimum = require_non_negative_int(min_stock, "O estoque mínimo")
    opening = require_non_negative_int(initial_stock, "O estoque inicial")
    shelf = optional_text(location, "a localização", max_length=60)

    with transaction(conn):
        _ensure_barcode_free(conn, code)
        product_id = catalog_repo.insert_product(
            conn,
            barcode=code,
            name=product_name,
            category=product_category,
            unit=product_unit,
            price_cents=price,
            cost_cents=cost,
            min_stock=minimum,
            location=shelf,
            created_at=clock.now_iso(),
        )
        if opening > 0:
            stock.apply_movement(
                conn,
                product_id=product_id,
                movement_type="entrada",
                quantity=opening,
                reason=stock.REASON_INITIAL,
                reference="Cadastro do produto",
                operator=actor.username,
            )
        product = catalog_repo.get_product(conn, product_id)
    assert product is not None
    return product


def update_product(
    conn: sqlite3.Connection,
    actor: User,
    product_id: int,
    *,
    barcode: str,
    name: str,
    price_cents: int,
    cost_cents: int,
    unit: str,
    category: str,
    location: str,
    min_stock: int,
) -> Product:
    """Edita os dados cadastrais. O saldo só muda por movimentação (RNF04)."""
    permissions.ensure_permission(actor, permissions.PRODUCT_MANAGE)
    code = normalize_barcode(barcode)
    fields = {
        "barcode": code,
        "name": require_text(name, "o nome do produto"),
        "category": require_text(category or "Geral", "a categoria", max_length=60),
        "unit": _check_unit(unit),
        "price_cents": _check_price(price_cents),
        "cost_cents": _check_cost(cost_cents),
        "min_stock": require_non_negative_int(min_stock, "O estoque mínimo"),
        "location": optional_text(location, "a localização", max_length=60),
    }
    with transaction(conn):
        product = catalog_repo.get_product(conn, product_id)
        if product is None:
            raise NotFoundError("Produto não encontrado.")
        if product.is_active:
            _ensure_barcode_free(conn, code, ignore_product_id=product_id)
        catalog_repo.update_product(conn, product_id, **fields)
        updated = catalog_repo.get_product(conn, product_id)
    assert updated is not None
    return updated


def update_price(
    conn: sqlite3.Connection, actor: User, product_id: int, new_price_cents: int
) -> Product:
    """atualizarPreco(novoPreco)."""
    permissions.ensure_permission(actor, permissions.PRODUCT_MANAGE)
    price = _check_price(new_price_cents)
    with transaction(conn):
        if catalog_repo.get_product(conn, product_id) is None:
            raise NotFoundError("Produto não encontrado.")
        catalog_repo.update_product(conn, product_id, price_cents=price)
        product = catalog_repo.get_product(conn, product_id)
    assert product is not None
    return product


def set_active(conn: sqlite3.Connection, actor: User, product_id: int, active: bool) -> Product:
    """Inativa ou reativa um produto (produtos nunca são apagados — RB12)."""
    permissions.ensure_permission(actor, permissions.PRODUCT_MANAGE)
    with transaction(conn):
        product = catalog_repo.get_product(conn, product_id)
        if product is None:
            raise NotFoundError("Produto não encontrado.")
        if active and not product.is_active:
            _ensure_barcode_free(conn, product.barcode, ignore_product_id=product_id)
        catalog_repo.update_product(conn, product_id, active=1 if active else 0)
        updated = catalog_repo.get_product(conn, product_id)
    assert updated is not None
    return updated


# ----------------------------------------------------------------------- Consultas
def get_product(conn: sqlite3.Connection, product_id: int) -> Product:
    product = catalog_repo.get_product(conn, product_id)
    if product is None:
        raise NotFoundError("Produto não encontrado.")
    return product


def find_by_barcode(conn: sqlite3.Connection, barcode: str) -> Product | None:
    """RF03: leitura de código de barras."""
    return catalog_repo.get_active_product_by_barcode(conn, normalize_barcode(barcode))


def search_products(
    conn: sqlite3.Connection,
    *,
    term: str = "",
    category: str | None = None,
    include_inactive: bool = False,
    only_below_minimum: bool = False,
    limit: int | None = None,
) -> list[Product]:
    """RF03: localização manual por nome, código, categoria ou localização."""
    return catalog_repo.find_products(
        conn,
        term=term,
        category=category,
        include_inactive=include_inactive,
        only_below_minimum=only_below_minimum,
        limit=limit,
    )


def count_products(
    conn: sqlite3.Connection,
    *,
    term: str = "",
    category: str | None = None,
    include_inactive: bool = False,
    only_below_minimum: bool = False,
) -> int:
    return catalog_repo.count_products(
        conn,
        term=term,
        category=category,
        include_inactive=include_inactive,
        only_below_minimum=only_below_minimum,
    )


def list_categories(conn: sqlite3.Connection) -> list[str]:
    existing = catalog_repo.list_categories(conn)
    return sorted({*DEFAULT_CATEGORIES, *existing}, key=str.casefold)
