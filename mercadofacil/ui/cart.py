"""Carrinho do PDV (RF04): operações puras sobre um mapa {produto_id: quantidade}.

O dicionário preserva a ordem de inclusão, que é a ordem exibida na tela.
"""

from __future__ import annotations

Cart = dict[int, int]


def add(cart: Cart, product_id: int, quantity: int = 1) -> Cart:
    """Adiciona unidades; se o produto já está no carrinho, soma à quantidade."""
    if quantity <= 0:
        raise ValueError("A quantidade a adicionar deve ser positiva.")
    updated = dict(cart)
    updated[product_id] = updated.get(product_id, 0) + quantity
    return updated


def set_quantity(cart: Cart, product_id: int, quantity: int) -> Cart:
    """Altera a quantidade de um item; zero ou menos remove o item."""
    if product_id not in cart:
        return dict(cart)
    if quantity <= 0:
        return remove(cart, product_id)
    updated = dict(cart)
    updated[product_id] = quantity
    return updated


def remove(cart: Cart, product_id: int) -> Cart:
    return {pid: qty for pid, qty in cart.items() if pid != product_id}


def as_lines(cart: Cart) -> list[tuple[int, int]]:
    """Formato aceito pelos serviços de venda: [(produto_id, quantidade)]."""
    return list(cart.items())


def units(cart: Cart) -> int:
    return sum(cart.values())
