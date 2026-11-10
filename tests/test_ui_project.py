"""Tela "Projeto e operação": documentação, casos de teste ao vivo e backup (RNF10)."""

from __future__ import annotations

from pathlib import Path

from mercadofacil.ui import ct_runner, docs_content
from tests.ui_harness import UiApp

ROOT = Path(__file__).resolve().parent.parent


def test_documentacao_reproduz_o_documento_do_projeto(app: UiApp) -> None:
    app.render("project", "operador")
    assert app.contains("Grupo 4 — Thomaz, Victor, Lucas, Yago")
    assert app.contains("3.1 Requisitos funcionais", "RF01", "RF16", "RNF11", "RB12")
    assert app.contains("5.1 Diagrama de casos de uso", "5.2 Diagrama de classes")
    assert app.contains("9.1 Treinamento recomendado", "9.2 Limites do protótipo")
    assert app.contains("Abrir", "Status do cabeçalho deve mostrar Caixa aberto.")
    assert "uml_casos_de_uso.png" in app.raw() and "uml_classes.png" in app.raw()
    for case in docs_content.TEST_CASES:
        assert app.contains(case.id, case.scenario, case.expected)


def test_imagens_dos_diagramas_existem() -> None:
    assets = ROOT / "mercadofacil" / "ui" / "assets"
    for name in ("uml_casos_de_uso.png", "uml_classes.png"):
        assert (assets / name).stat().st_size > 10_000


def test_interpretacao_da_saida_do_pytest() -> None:
    saida = (
        "tests/test_casos_de_teste.py::test_ct01_cadastrar_barcode_ativo_duplicado PASSED  [  8%]\n"
        "tests/test_casos_de_teste.py::test_ct02_campo_obrigatorio_vazio FAILED [ 16%]\n"
        "linha qualquer\n"
    )
    assert ct_runner.parse_results(saida) == {"CT01": "PASSED", "CT02": "FAILED"}


def test_executar_casos_de_teste_ao_vivo_ct01_a_ct12(app: UiApp) -> None:
    app.render("project", "gestor")
    assert app.contains("Não executado")
    app.click("project_run_ct")
    app.render("project", "gestor")  # a mesma execução que trata o clique já mostra o resultado
    assert app.contains("Todos os casos passaram", "✔ Passou")
    assert not app.contains("Não executado")
    run = app.st.session_state["project_ct_run"]
    assert run.all_passed and sorted(run.results) == [c.id for c in docs_content.TEST_CASES]


def test_execucao_sem_arquivos_de_teste_informa_o_motivo(tmp_path: Path) -> None:
    resultado = ct_runner.run_case_tests(tmp_path)
    assert resultado.error is not None and not resultado.all_passed


def test_somente_o_gestor_gera_backup_pela_tela(app: UiApp) -> None:
    app.render("project", "operador")
    assert app.contains("Somente o gestor pode gerar a cópia de segurança")
    assert not app.st.downloads
    app.click("project_backup_prepare")
    app.render("project", "gestor")
    assert app.contains("Backup gerado", ".db")
    (download,) = app.st.downloads
    assert download["file_name"].startswith("mercado_facil_backup_")
    assert download["data"].startswith(b"SQLite format 3")
