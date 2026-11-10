"""Componentes reutilizáveis: alertas, tabelas, entradas e tratamento de erros (RNF06)."""

from __future__ import annotations

import sqlite3

import pytest

from mercadofacil import errors
from tests.ui_harness import UiApp


@pytest.fixture
def components(app: UiApp):
    return app.module("components")


def test_dolar_e_html_nunca_chegam_crus_ao_markdown(app: UiApp, components) -> None:
    markup = components.alert_markup("danger", "Faltam R$ 8,90 e R$ 2,00 <b>x</b>", title="A & B")
    assert "$" not in markup  # '$' vira entidade: o markdown do Streamlit o trataria como LaTeX
    assert "&#36;" in markup and "&lt;b&gt;" in markup and "A &amp; B" in markup
    assert components.md_escape("R$ 10 *negrito* _it_") == r"R\$ 10 \*negrito\* \_it\_"


def test_alerta_tem_papel_acessivel_e_tom_valido(components) -> None:
    assert 'role="alert"' in components.alert_markup("danger", "x")
    assert 'role="status"' in components.alert_markup("ok", "x")
    assert "mf-alert-neutral" in components.alert_markup("inventado", "x")
    assert "<li>um</li><li>dois</li>" in components.alert_markup("warn", "x", items=["um", "dois"])


def test_erros_de_regra_aparecem_como_alerta_claro(app: UiApp, components) -> None:
    def acao() -> None:
        raise errors.BusinessRuleError("Estoque negativo impedido: saldo 5.", rule="RB03")

    app.run(lambda: components.run_action(acao))
    assert app.contains("Regra de negócio RB03", "Estoque negativo impedido: saldo 5.")
    assert "mf-alert-danger" in app.raw()


@pytest.mark.parametrize(
    ("erro", "titulo"),
    [
        (errors.ValidationError("x"), "Confira os dados informados"),
        (errors.BusinessRuleError("x"), "Operação não permitida"),
        (errors.PermissionDeniedError("x"), "Acesso negado"),
        (errors.AuthenticationError("x"), "Acesso negado"),
        (errors.NotFoundError("x"), "Registro não encontrado"),
        (errors.MercadoFacilError("x"), "Não foi possível concluir"),
    ],
)
def test_titulo_do_erro(components, erro: Exception, titulo: str) -> None:
    assert components.error_title(erro) == titulo


def test_acao_bem_sucedida_guarda_confirmacao_para_depois_do_rerun(app: UiApp, components) -> None:
    resultado: list[object] = []
    app.run(
        lambda: resultado.append(components.run_action(lambda: 42, success=lambda n: f"ok {n}"))
    )
    assert resultado == [(True, 42)]
    app.run(components.render_flashes)
    assert app.contains("ok 42")
    app.run(components.render_flashes)
    assert not app.contains("ok 42")  # a confirmação aparece uma única vez


def test_falha_do_banco_vira_mensagem_amigavel(app: UiApp, components) -> None:
    def acao() -> None:
        raise sqlite3.OperationalError("database is locked")

    app.run(lambda: components.run_action(acao))
    assert app.contains("Falha temporária", "Aguarde alguns segundos")


def test_tabela_vazia_mostra_estado_vazio(app: UiApp, components) -> None:
    app.run(lambda: components.table([], empty="Nada aqui.", hint="Tente outro filtro."))
    assert app.contains("Nada aqui.", "Tente outro filtro.")
    assert app.st.dataframes == []


def test_tabela_com_linhas_usa_dataframe_sem_indice(app: UiApp, components) -> None:
    app.run(lambda: components.table([{"A": 1, "B": "x"}]))
    assert len(app.st.dataframes) == 1 and list(app.st.dataframes[0].columns) == ["A", "B"]


def test_campo_de_dinheiro(app: UiApp, components) -> None:
    leituras: list[object] = []

    def tela() -> None:
        leituras.append(components.money_field("Valor", key="v", default="1,50"))

    app.run(tela)
    app.type("v", "R$ 1.234,56")
    app.run(tela)
    app.type("v", "abc")
    app.run(tela)
    app.type("v", "")
    app.run(tela)
    assert leituras[0] == (150, None)
    assert leituras[1] == (123456, None)
    assert leituras[2][0] is None and "Valor inválido" in str(leituras[2][1])
    assert leituras[3] == (None, None)


def test_selos_e_metricas_escapam_o_conteudo(components) -> None:
    assert "&lt;script&gt;" in components.badge_markup("<script>", "ok")
    card = components.metric_markup("Total", "R$ 10,00", "dica & mais")
    assert "&#36;" in card and "dica &amp; mais" in card


def test_cabecalho_mostra_estado_do_caixa_so_para_quem_opera_caixa(components) -> None:
    from mercadofacil.models import Register, User

    aberto = Register(1, "ana", "aberto", 10000, "2026-10-27 08:00:00")
    operador = User(1, "ana", "Ana", "operador")
    estoquista = User(2, "eva", "Eva", "estoquista")
    assert "Caixa aberto" in components.header_markup("Tela", operador, aberto)
    assert "Caixa fechado" in components.header_markup("Tela", operador, None)
    cabecalho = components.header_markup("Tela", estoquista, None)
    assert "Caixa" not in cabecalho and "Estoquista" in cabecalho
