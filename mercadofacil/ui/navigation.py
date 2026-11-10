"""Páginas do sistema e permissões de acesso (seção 7: telas implementadas)."""

from __future__ import annotations

from dataclasses import dataclass

from ..config import ROLE_MANAGER, ROLE_OPERATOR, ROLE_STOCKER
from ..models import User
from ..services import permissions


@dataclass(frozen=True)
class Page:
    slug: str
    title: str
    icon: str
    permission: str
    objective: str  # coluna "Objetivo" da tabela da seção 7


PAGES: tuple[Page, ...] = (
    Page("overview", "Visão geral", "📊", permissions.DASHBOARD_VIEW, "Acompanhar operação"),
    Page("pos", "Frente de caixa", "🛒", permissions.SALE_CREATE, "Registrar venda"),
    Page("products", "Produtos e estoque", "📦", permissions.PRODUCT_MANAGE, "Organizar catálogo"),
    Page("sales", "Vendas e pós-venda", "🧾", permissions.SALE_VIEW, "Atender ocorrências"),
    Page("register", "Abertura e fechamento", "💰", permissions.REGISTER_MANAGE, "Controlar turno"),
    Page("movements", "Movimentações", "🔁", permissions.STOCK_HISTORY, "Auditar estoque"),
    Page("project", "Projeto e operação", "📘", permissions.DOCS_VIEW, "Apoiar treinamento"),
)

_BY_SLUG = {page.slug: page for page in PAGES}

# Primeira tela de cada perfil: a tarefa principal antes do conteúdo explicativo (7.1).
_LANDING = {ROLE_OPERATOR: "pos", ROLE_STOCKER: "products", ROLE_MANAGER: "overview"}


def get_page(slug: str) -> Page | None:
    return _BY_SLUG.get(slug)


def visible_pages(user: User | None) -> list[Page]:
    """Páginas que o perfil do usuário pode abrir (RNF08)."""
    return [page for page in PAGES if permissions.can(user, page.permission)]


def default_page(user: User) -> Page:
    visible = visible_pages(user)
    preferred = _BY_SLUG[_LANDING.get(user.role, "overview")]
    return preferred if preferred in visible else visible[0]
