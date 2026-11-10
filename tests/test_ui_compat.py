"""Camada de compatibilidade: a interface funciona antes e depois da troca de API do Streamlit."""

from __future__ import annotations

import json

import pytest

from tests.ui_harness import UiApp


def test_largura_total_em_versao_antiga_usa_use_container_width(app: UiApp) -> None:
    compat = app.module("compat")
    assert compat.PREFERS_WIDTH_STRETCH is False
    app.run(lambda: compat.stretch(app.st.button, "Ok", key="ok"))  # não deve levantar erro
    assert app.st.labels("button") == ["Ok"]


def test_largura_total_em_versao_nova_usa_width_stretch(modern_app: UiApp) -> None:
    compat = modern_app.module("compat")
    assert compat.PREFERS_WIDTH_STRETCH is True
    modern_app.run(lambda: compat.stretch(modern_app.st.button, "Ok", key="ok"))
    assert modern_app.st.labels("button") == ["Ok"]


def test_largura_total_cai_para_use_container_width_se_stretch_nao_for_aceito(
    modern_app: UiApp,
) -> None:
    """Versão >= 1.50 que ainda não aceita width="stretch" naquele elemento."""
    compat = modern_app.module("compat")
    chamadas: list[dict[str, object]] = []

    def elemento(label: str, **kwargs: object) -> None:
        chamadas.append(kwargs)
        if kwargs.get("width") == "stretch":
            raise TypeError("sem suporte")

    compat.stretch(elemento, "x")
    assert chamadas == [{"width": "stretch"}, {"use_container_width": True}]


@pytest.mark.parametrize("version", ["1.40.0", "1.55.0"])
def test_telas_funcionam_nas_duas_geracoes_da_api(version: str, ui_db) -> None:
    from tests.ui_harness import make_app

    for application in make_app(version, ui_db):
        for view, user in (("pos", "operador"), ("products", "gestor"), ("project", "gestor")):
            application.render(view, user)
            assert application.contains("Erro inesperado") is False
        assert application.st.dataframes is not None


def test_dialogo_usa_a_api_disponivel(app: UiApp) -> None:
    compat = app.module("compat")
    chamadas: list[str] = []

    @compat.dialog("Título")
    def corpo(valor: str) -> None:
        chamadas.append(valor)

    app.run(lambda: corpo("a"))
    assert chamadas == ["a"]
    assert app.st.labels("dialog") == ["Título"]


def test_dialogo_sem_suporte_do_streamlit_abre_painel_na_pagina(
    app: UiApp,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delattr(
        type(app.st), "dialog"
    )  # simula Streamlit sem st.dialog/experimental_dialog
    compat = app.module("compat")

    @compat.dialog("Painel")
    def corpo() -> None:
        app.st.caption("conteúdo")

    app.run(corpo)
    assert app.contains("Painel", "conteúdo")


def test_foco_no_leitor_de_codigo_de_barras_e_opcional(app: UiApp) -> None:
    compat = app.module("compat")
    app.run(lambda: compat.focus_input("Código de barras ou nome do produto", nonce=3))
    (html,) = [t for k, t, _ in app.st.elements if k == "iframe"]
    assert json.dumps("Código de barras ou nome do produto") in html and "/* 3 */" in html
    assert "window.parent.document" in html
