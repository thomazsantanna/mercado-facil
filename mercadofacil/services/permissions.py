"""Permissões por perfil (RNF08).

Perfis detalhados de permissão estão fora do escopo (seção 9.2); o protótipo
usa três papéis fixos que refletem as responsabilidades da seção 3.
"""

from __future__ import annotations

from ..config import ROLE_MANAGER, ROLE_OPERATOR, ROLE_STOCKER
from ..errors import PermissionDeniedError
from ..models import User

# Ações
DASHBOARD_VIEW = "dashboard.view"
SALE_CREATE = "sale.create"  # frente de caixa e cadastro rápido de cliente
REGISTER_MANAGE = "register.manage"  # abrir/fechar o próprio caixa
REGISTER_VIEW_ALL = "register.view_all"
SALE_VIEW = "sale.view"
POSTSALE_REGISTER = "postsale.register"  # exige autorização do gestor
PRODUCT_MANAGE = "product.manage"
STOCK_MOVE = "stock.move"
STOCK_HISTORY = "stock.history"
BACKUP_RUN = "backup.run"
DOCS_VIEW = "docs.view"

ROLE_ACTIONS: dict[str, frozenset[str]] = {
    ROLE_OPERATOR: frozenset(
        {DASHBOARD_VIEW, SALE_CREATE, REGISTER_MANAGE, SALE_VIEW, POSTSALE_REGISTER, DOCS_VIEW}
    ),
    ROLE_STOCKER: frozenset({DASHBOARD_VIEW, PRODUCT_MANAGE, STOCK_MOVE, STOCK_HISTORY, DOCS_VIEW}),
    ROLE_MANAGER: frozenset(
        {
            DASHBOARD_VIEW,
            SALE_CREATE,
            REGISTER_MANAGE,
            REGISTER_VIEW_ALL,
            SALE_VIEW,
            POSTSALE_REGISTER,
            PRODUCT_MANAGE,
            STOCK_MOVE,
            STOCK_HISTORY,
            BACKUP_RUN,
            DOCS_VIEW,
        }
    ),
}


def can(user: User | None, action: str) -> bool:
    return (
        user is not None
        and bool(user.active)
        and action in ROLE_ACTIONS.get(user.role, frozenset())
    )


def ensure_permission(user: User | None, action: str) -> User:
    if user is None:
        raise PermissionDeniedError("Entre no sistema para continuar.")
    if not can(user, action):
        raise PermissionDeniedError(
            f"O perfil “{user.role_label}” não tem permissão para esta operação."
        )
    return user
