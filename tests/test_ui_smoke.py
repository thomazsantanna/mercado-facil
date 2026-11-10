"""Fumaça: toda tela abre, para cada perfil, sem erro e com o conteúdo essencial."""

from __future__ import annotations

import pytest

from tests.ui_harness import UiApp


def test_login_mostra_formulario_e_credenciais_de_demonstracao(app: UiApp) -> None:
    app.shell()
    assert app.contains("Entrar", "Usuário", "Senha", "Credenciais de demonstração")
    assert app.contains("gestor123", "operador123", "estoque123")


@pytest.mark.parametrize(
    ("view", "username", "esperado"),
    [
        ("overview", "gestor", ["Vendas concluídas", "Alertas de reposição"]),
        ("pos", "operador", ["Adicionar produtos", "Carrinho"]),
        ("products", "estoquista", ["Catálogo", "Reposição necessária"]),
        ("sales", "gestor", ["venda(s) encontrada(s)", "Nenhuma venda encontrada"]),
        ("register", "operador", ["Abrir caixa", "Histórico de caixas"]),
        ("movements", "gestor", ["Movimentações", "Unidades que entraram"]),
        ("project", "operador", ["Visão geral do projeto", "Manual operacional"]),
    ],
)
def test_cada_tela_abre(app: UiApp, view: str, username: str, esperado: list[str]) -> None:
    app.render(view, username)
    assert app.contains(*esperado), app.text()[:1500]
