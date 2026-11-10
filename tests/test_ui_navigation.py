"""Páginas, permissões de acesso e tela inicial de cada perfil (7, RNF08)."""

from __future__ import annotations

import pytest

from mercadofacil.models import User
from mercadofacil.ui import docs_content, navigation


def usuario(role: str) -> User:
    return User(id=1, username=role, name=role.title(), role=role)


ESPERADO = {
    "operador": ["overview", "pos", "sales", "register", "project"],
    "estoquista": ["overview", "products", "movements", "project"],
    "gestor": ["overview", "pos", "products", "sales", "register", "movements", "project"],
}


@pytest.mark.parametrize(("role", "slugs"), ESPERADO.items())
def test_cada_perfil_ve_somente_as_suas_telas(role: str, slugs: list[str]) -> None:
    assert [p.slug for p in navigation.visible_pages(usuario(role))] == slugs


def test_sem_usuario_nao_ha_telas() -> None:
    assert navigation.visible_pages(None) == []


def test_sete_telas_na_ordem_do_documento() -> None:
    assert [p.title for p in navigation.PAGES] == [
        "Visão geral",
        "Frente de caixa",
        "Produtos e estoque",
        "Vendas e pós-venda",
        "Abertura e fechamento",
        "Movimentações",
        "Projeto e operação",
    ]
    assert [p.objective for p in navigation.PAGES] == [
        "Acompanhar operação",
        "Registrar venda",
        "Organizar catálogo",
        "Atender ocorrências",
        "Controlar turno",
        "Auditar estoque",
        "Apoiar treinamento",
    ]
    assert set(docs_content.SCREEN_CONTROLS) == {p.slug for p in navigation.PAGES}


@pytest.mark.parametrize(
    ("role", "inicial"), [("operador", "pos"), ("estoquista", "products"), ("gestor", "overview")]
)
def test_tela_inicial_e_a_tarefa_principal_do_perfil(role: str, inicial: str) -> None:
    assert navigation.default_page(usuario(role)).slug == inicial


def test_get_page() -> None:
    assert navigation.get_page("pos") is not None
    assert navigation.get_page("inexistente") is None
