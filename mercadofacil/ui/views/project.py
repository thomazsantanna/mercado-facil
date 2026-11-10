"""Projeto e operação: manual, requisitos, modelagem e casos de teste (seção 7)."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from ...models import User
from ...services import backup, permissions
from .. import compat, components, ct_runner, docs_content, formatting, state
from ..navigation import PAGES

ASSETS = Path(__file__).resolve().parent.parent / "assets"
K_CT_RUN = "project_ct_run"

TABS = [
    "Visão geral",
    "Requisitos",
    "Modelagem",
    "Telas",
    "Casos de teste",
    "Manual operacional",
    "Backup e recuperação",
]


def render(user: User) -> None:
    components.html(
        f"<div class='mf-card'><strong>{components.esc(docs_content.TITLE)}</strong><br>"
        f"{components.esc(docs_content.SUBTITLE)}<br>{components.esc(docs_content.GROUP)}</div>"
    )
    tabs = st.tabs(TABS)
    with tabs[0]:
        _overview_tab()
    with tabs[1]:
        _requirements_tab()
    with tabs[2]:
        _modeling_tab()
    with tabs[3]:
        _screens_tab()
    with tabs[4]:
        _tests_tab()
    with tabs[5]:
        _manual_tab()
    with tabs[6]:
        _backup_tab(user)


def _bullets(items: list[str]) -> None:
    components.html("<ul>" + "".join(f"<li>{components.esc(i)}</li>" for i in items) + "</ul>")


# ---------------------------------------------------------------------------- visão geral
def _overview_tab() -> None:
    components.section_title("1. Visão geral do projeto")
    components.lines_table(["Item", "Definição"], docs_content.OVERVIEW)
    components.section_title("1.1 Identificação do problema")
    components.lines_table(["Aspecto", "Descrição"], docs_content.IDENTIFICATION)
    components.section_title("1.2 Critérios de sucesso")
    components.alert("info", docs_content.SUCCESS_CRITERIA)
    components.section_title("2. Estudo de viabilidade")
    components.lines_table(["Dimensão", "Análise", "Decisão"], docs_content.FEASIBILITY)
    components.section_title("2.1 Recursos e custos indicativos")
    components.lines_table(["Recurso", "Necessidade", "Observação"], docs_content.RESOURCES)
    components.section_title("2.2 Proteção e segurança das informações")
    components.alert("neutral", docs_content.PROTECTION)
    components.section_title("3. Atores e funcionalidades")
    components.lines_table(["Ator", "Responsabilidades"], docs_content.ACTORS)


# ----------------------------------------------------------------------------- requisitos
def _requirements_table(requirements: tuple[docs_content.Requirement, ...]) -> None:
    components.lines_table(
        ["ID", "Requisito", "Implementado em", "Verificado por"],
        [
            (
                r.id,
                r.text,
                "; ".join(ref.split(":")[-1] for ref in r.code),
                "; ".join(t.split("::")[-1] for t in r.tests),
            )
            for r in requirements
        ],
    )


def _requirements_tab() -> None:
    st.caption(
        "Cada requisito aponta a função que o implementa e os testes automatizados que o verificam "
        "(a matriz completa, com caminhos de arquivo, está em docs/RASTREABILIDADE.md)."
    )
    components.section_title("3.1 Requisitos funcionais")
    _requirements_table(docs_content.FUNCTIONAL)
    components.section_title("4. Requisitos não funcionais")
    _requirements_table(docs_content.NON_FUNCTIONAL)
    components.section_title("4.2 Regras de negócio")
    _requirements_table(docs_content.BUSINESS_RULES)


# ------------------------------------------------------------------------------ modelagem
def _modeling_tab() -> None:
    components.section_title("5. Modelagem UML")
    st.markdown("**5.1 Diagrama de casos de uso**")
    compat.stretch(
        st.image, str(ASSETS / "uml_casos_de_uso.png"), caption="Diagrama de casos de uso"
    )
    st.markdown("**5.2 Diagrama de classes**")
    compat.stretch(st.image, str(ASSETS / "uml_classes.png"), caption="Diagrama de classes")
    components.section_title("6. Arquitetura e modelo de dados")
    components.lines_table(["Tabela", "Finalidade", "Campos"], docs_content.DATA_MODEL)
    st.caption(components.md_escape(docs_content.DATA_MODEL_EXTRA.replace("`", "")))
    components.section_title("6.1 Decisões de implementação")
    _bullets(docs_content.IMPLEMENTATION_DECISIONS)


# ---------------------------------------------------------------------------------- telas
def _screens_tab() -> None:
    components.section_title("7. Protótipos e telas implementadas")
    components.lines_table(
        ["Tela", "Objetivo", "Controles"],
        [(p.title, p.objective, docs_content.SCREEN_CONTROLS[p.slug]) for p in PAGES],
    )
    components.section_title("7.1 Princípios de usabilidade")
    _bullets(docs_content.USABILITY)


# ----------------------------------------------------------------------------- testes
OUTCOME_LABELS = {
    "PASSED": "✔ Passou",
    "FAILED": "✖ Falhou",
    "ERROR": "✖ Erro",
    "SKIPPED": "— Ignorado",
}


def _tests_tab() -> None:
    components.section_title("8. Plano e casos de teste")
    # O botão vem antes da tabela: o clique é tratado durante a execução do script, então a
    # tabela abaixo já nasce com o resultado novo (e não só na interação seguinte).
    if compat.stretch(
        st.button, "Executar os casos de teste agora", key="project_run_ct", type="primary"
    ):
        with st.spinner("Executando CT01–CT12…"):
            st.session_state[K_CT_RUN] = ct_runner.run_case_tests()
    run: ct_runner.CaseRun | None = st.session_state.get(K_CT_RUN)
    results = run.results if run else {}
    if run is not None:
        if run.error:
            components.alert("warn", run.error, title="Não foi possível executar")
        elif run.all_passed:
            components.alert(
                "ok", "Os 12 casos de teste passaram.", title="Todos os casos passaram"
            )
        else:
            components.alert(
                "danger", "Há casos de teste com falha. Veja a saída abaixo.", title="Atenção"
            )
    rows = [
        (
            case.id,
            case.scenario,
            case.expected,
            OUTCOME_LABELS.get(results.get(case.id, ""), "Não executado"),
        )
        for case in docs_content.TEST_CASES
    ]
    components.lines_table(["ID", "Cenário", "Resultado esperado", "Execução"], rows)
    if run is not None and run.output:
        with st.expander("Saída do pytest"):
            st.code(run.output, language="text")
    components.section_title("8.1 Testes automatizados implementados")
    st.markdown(components.md_escape(docs_content.AUTOMATED_TESTS.replace("`", "")))


# ----------------------------------------------------------------------------- manual
def _manual_tab() -> None:
    components.section_title("9. Manual operacional")
    components.lines_table(["Passo", "Procedimento", "Conferência"], docs_content.MANUAL)
    components.section_title("9.1 Treinamento recomendado")
    st.markdown(components.md_escape(docs_content.TRAINING))
    components.section_title("9.2 Limites do protótipo")
    components.alert("warn", docs_content.LIMITS)


def _backup_tab(user: User) -> None:
    components.section_title("Backup e recuperação (RNF10)")
    _bullets(docs_content.BACKUP_STEPS)
    if not permissions.can(user, permissions.BACKUP_RUN):
        components.alert("neutral", "Somente o gestor pode gerar a cópia de segurança.")
        return
    if compat.stretch(st.button, "Preparar cópia de segurança", key="project_backup_prepare"):

        def make() -> tuple[str, bytes]:
            with state.db() as conn:
                return backup.backup_bytes(conn, user)

        ok, result = components.run_action(make)
        if ok and result is not None:
            filename, content = result
            components.alert(
                "ok",
                f"Cópia pronta: {filename} ({formatting.file_size(len(content))}).",
                title="Backup gerado",
            )
            st.download_button(
                "Baixar cópia de segurança (.db)",
                data=content,
                file_name=filename,
                mime="application/octet-stream",
                key="project_backup_download",
            )
